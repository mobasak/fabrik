"""PostgreSQL database + role provisioning on the shared ``postgres-main`` container.

Creates a database and (optionally) a dedicated role with a CSPRNG-generated
password on the shared ``postgres-main`` container. All mutations go through
:func:`fabrik.drivers.ssh.ssh` with ``sudo docker exec`` — there is no direct
PostgreSQL connection from the operator's machine, keeping credentials and
network exposure at zero.

Design notes
------------
* **SQL is passed to ``psql`` via stdin**, base64-encoded and decoded on the
  VPS before being piped to ``docker exec -i postgres-main psql``. This is
  the same escape-free pattern the ``backrest`` driver uses for JSON
  payloads (§Phase 5). Writing ``psql -c "DO $$ ..."`` instead would cause
  the outer remote shell to expand ``$$`` to its PID — verified 2026-04-19
  during the first live smoke of this driver (see CHANGELOG).
* **Container name is hard-coded** to the verified Coolify UUID for
  ``postgres-main``; overridable via the ``container`` kwarg for tests.
* **Idempotent** — :func:`create_database` checks ``pg_database`` before
  CREATE. Role creation is guarded by a ``pg_roles`` existence check
  inside a ``DO $$ ... $$`` block so repeated calls with the same
  ``db_user`` do not raise.
* **SQL identifiers are validated, not escaped.** A strict regex
  (``[a-zA-Z_][a-zA-Z0-9_]{0,62}``) enforces the conservative PostgreSQL
  identifier subset before any value reaches the shell. Invalid names
  raise :class:`ValueError` before a single ``ssh()`` call is made.
* **Password generation** uses :func:`secrets.choice` over
  ``string.ascii_letters + string.digits`` (62-char alphabet, 32 chars ≈
  190 bits of entropy). Returned in the result dict; caller owns storage.
* **No rollback handler for CREATE DATABASE.** Dropping a database
  mid-deploy is a dangerous destructive action on the shared
  ``postgres-main`` instance; the rollback strategy (plan §Rollback
  Strategy) leaves the empty DB in place and logs it for manual cleanup.
"""

from __future__ import annotations

import base64
import datetime as _dt
import json
import logging
import os
import re
import secrets
import shlex
import string
import time
import uuid
from pathlib import Path
from typing import Any

# Phase 6 of deploy-readiness-gaps (2026-06-30): per-DB Backrest plan
# registration. Importing here is safe — backrest.py doesn't import postgres,
# so no circular dependency. Module-level import keeps the test patch path
# `fabrik.drivers.postgres.register_postgres_plan` stable.
from fabrik.drivers.backrest import register_postgres_plan, unregister_postgres_plan
from fabrik.drivers.ssh import scp_to_vps, ssh
from fabrik.locks_local import file_lock

logger = logging.getLogger(__name__)

POSTGRES_CONTAINER = "postgres-main"
"""Verified container name on VPS (2026-05-30, post-Coolify migration).

Previously this hardcoded the Coolify-suffixed UUID
``postgres-main-l0k4gk0kggc8okcwk0s4c8s8``; that suffix died with the
Coolify→SSH+Compose migration (commits 6ae18ab and earlier). Live VPS
verification (``ssh vps "sudo docker ps --format '{{.Names}}'"``) shows
the container is plain ``postgres-main``. Overridable per-call via the
``container`` kwarg for tests and future container migrations."""

ALLOCATIONS_PATH = "/opt/monitoring/configs/postgres/allocations.json"
"""Source-of-truth registry mapping db_name → owner/spec_id/user/notes.

Lives on the VPS at the same path as other registry-style configs
(``/opt/monitoring/configs/redis/assignments.json`` etc.). The
``audit_postgres`` registrar cross-references this file against the live
``pg_database`` table to surface drift (registry says X exists but DB
doesn't, or vice-versa). T4-01 G-J4."""

_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")
"""PostgreSQL identifier validation.

Matches the conservative subset of the SQL standard: leading letter or
underscore, followed by up to 62 letters / digits / underscores. This is
deliberately stricter than Postgres's own rules (which allow quoted
identifiers with arbitrary content) — we never want the driver to need
to emit a quoted identifier that a shell might unquote.
"""

PASSWORD_ALPHABET = string.ascii_letters + string.digits
"""Alphabet for generated passwords. 62 characters = ~5.95 bits/char."""

PASSWORD_LENGTH = 32
"""Generated password length. 32 * 5.95 ≈ 190 bits of entropy."""


def _validate_identifier(value: str, what: str) -> None:
    """Raise :class:`ValueError` if ``value`` is not a safe SQL identifier."""
    if not isinstance(value, str) or not _IDENT_RE.match(value):
        raise ValueError(
            f"Invalid PostgreSQL {what} name {value!r}: must match [a-zA-Z_][a-zA-Z0-9_]{{0,62}}"
        )


def _generate_password() -> str:
    """Return a 32-char CSPRNG password drawn from ``[a-zA-Z0-9]``."""
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def _run_sql(sql: str, container: str, dry_run: bool = False) -> str:
    """Execute ``sql`` via stdin-piped psql inside the postgres container.

    Base64-encodes the SQL and decodes it on the VPS before piping to
    ``docker exec -i ... psql -U postgres``. This bypasses every shell
    quoting / expansion hazard (e.g., ``$$`` being interpreted as the
    shell's PID, embedded single quotes breaking argument parsing) that
    ``psql -c "..."`` patterns suffer from.

    Args:
        sql: Full SQL to execute. Multiple statements OK. Identifiers
            must be pre-validated by the caller.
        container: Postgres container name.
        dry_run: Skip execution and return empty string.

    Returns:
        psql's stdout with ``-tA`` formatting (tuples only, unaligned).

    Raises:
        RuntimeError: psql exited non-zero.
    """
    if dry_run:
        logger.info("[DRY RUN] Would run SQL (%d chars) on %s", len(sql), container)
        return ""
    payload = base64.b64encode(sql.encode()).decode()
    cmd = f"echo {payload} | base64 -d | sudo docker exec -i {container} psql -U postgres -tA"
    return ssh(cmd)


def database_exists(
    db_name: str, container: str = POSTGRES_CONTAINER, dry_run: bool = False
) -> bool:
    """True if a database named ``db_name`` exists on ``postgres-main``.

    Cheap idempotent ``pg_database`` lookup. Used by the orchestrator's Phase-1a
    rename guard (``orchestrator/infrastructure.py``) before switching a spec to a
    pinned ``depends.postgres`` name, so a rename never silently orphans existing
    data. In ``dry_run`` the underlying check is attempted read-only.
    """
    _validate_identifier(db_name, "database")
    # nosec B608 — db_name validated to alnum+underscore by _validate_identifier.
    check = _run_sql(
        f"SELECT 1 FROM pg_database WHERE datname='{db_name}';",  # nosec B608
        container=container,
        dry_run=dry_run,
    )
    return check.strip() == "1"


# ---------------------------------------------------------------------------
# Phase 5 of deploy-readiness-gaps plan (2026-06-30): DB seed auto-restore.
#
# When a spec carries `depends.postgres_seed: backups/<name>.sql.gz`, after
# create_database() finishes the role+grant, restore the dump into the new
# DB if (and only if) it has zero user tables. Idempotent.
# ---------------------------------------------------------------------------


def _resolve_seed_path(spec_dir: Path, seed_relpath: str) -> Path:
    """Resolve and validate a seed path.

    Security: must be a project-relative path (no absolute, no `..` escape).
    Must point at a file that exists and ends in `.sql.gz`.

    Raises ValueError on bad path; FileNotFoundError if the file is missing.
    """
    if not seed_relpath:
        raise ValueError("seed_relpath is empty")
    # SECURITY checks FIRST (before extension check), so an adversarial
    # path like `/etc/passwd` or `../../../etc/passwd` raises the
    # security-shaped error rather than a misleading "wrong extension".
    if os.path.isabs(seed_relpath):
        raise ValueError(f"seed path must be relative (got absolute {seed_relpath!r})")
    spec_dir = Path(spec_dir).resolve()
    candidate = (spec_dir / seed_relpath).resolve()
    if not candidate.is_relative_to(spec_dir):
        raise ValueError(
            f"seed path {seed_relpath!r} resolves outside spec_dir "
            f"({candidate} not under {spec_dir}) — directory traversal blocked"
        )
    if not seed_relpath.endswith(".sql.gz"):
        raise ValueError(
            f"seed path must end in `.sql.gz` (got {seed_relpath!r}); "
            "this prevents accidental restore from a raw .sql file"
        )
    if not candidate.is_file():
        raise FileNotFoundError(f"seed file not found: {candidate}")
    return candidate


def _count_user_tables(container: str, db_user: str, db_name: str) -> int:
    """Count BASE TABLE rows in `db_name`, excluding pg_catalog +
    information_schema (system schemas that pg_stat_statements or other
    extensions might populate even on a fresh DB).

    Returns 0 if psql output is unparseable — treats ambiguity as "empty"
    so the seed restore proceeds; the downstream `psql` will itself error
    if tables already exist, so worst case is a deferred failure not a
    silent corruption.
    """
    _validate_identifier(db_name, "database")
    sql = (
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_type='BASE TABLE' "
        "AND table_schema NOT IN ('pg_catalog', 'information_schema');"
    )
    # Connect as postgres superuser to the target DB. We do NOT use db_user
    # because the role's password isn't reused here — _run_sql is a
    # postgres-superuser path that bypasses RLS for introspection only.
    cmd_sql = f"\\c {db_name}\n{sql}"
    out = _run_sql(cmd_sql, container=container)
    try:
        return int(out.strip())
    except (ValueError, AttributeError):
        return 0


def _restore_seed(
    spec_dir: Path,
    seed_relpath: str,
    container: str,
    db_user: str,
    db_name: str,
) -> dict[str, Any]:
    """Ship the local dump to VPS /tmp/, restore via `gunzip | psql`, clean up.

    Idempotency: short-circuits with `status: skipped` if the DB already has
    user tables (the seed already ran, or the operator manually loaded data).
    Cleanup runs unconditionally (try/finally) — even on psql failure the
    sensitive dump is removed from /tmp/.

    Returns a status dict suitable for inclusion in the create_database
    result envelope.
    """
    local_seed = _resolve_seed_path(spec_dir, seed_relpath)
    user_tables = _count_user_tables(container, db_user, db_name)
    if user_tables > 0:
        return {
            "status": "skipped",
            "reason": "db_not_empty",
            "user_tables": user_tables,
        }

    # Per-run unique remote path so concurrent applies don't collide.
    suffix = f"{db_name}-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    remote_path = f"/tmp/fabrik-seed-{suffix}.sql.gz"  # nosec B108 — VPS-side staging path, per-run unique (ts+uuid), matches deployer_ssh/gatus convention

    try:
        scp_to_vps(local_path=str(local_seed), remote_path=remote_path)
        # `gunzip | psql` runs inside the postgres container; we pipe the
        # gz dump from VPS-side cat into docker exec -i, then through a
        # bash -c that runs gunzip|psql with the per-DB role identity.
        # The role uses no password because we're going through socket
        # auth inside the container as superuser (`-U postgres`).
        cmd = (
            f"cat {shlex.quote(remote_path)} | "
            f"sudo docker exec -i {container} bash -c "
            f"{shlex.quote(f'gunzip | psql -U postgres -d {db_name}')}"
        )
        ssh(cmd)
        return {
            "status": "restored",
            "seed": str(local_seed),
            "user_tables_before": 0,
        }
    finally:
        # Defense: the dump may contain sensitive seed data. Remove the
        # /tmp/ file regardless of restore success — operator-friendly.
        try:
            ssh(f"rm -f {shlex.quote(remote_path)}")
        except Exception as exc:  # noqa: BLE001 — cleanup must not raise
            logger.warning(
                "postgres seed: cleanup of %s failed (%s); operator should rm manually",
                remote_path,
                exc,
            )


def create_database(
    db_name: str,
    db_user: str | None = None,
    container: str = POSTGRES_CONTAINER,
    dry_run: bool = False,
    spec_id: str | None = None,
    owner: str = "fabrik",
    notes: str = "",
    spec_dir: Path | str | None = None,
    seed_relpath: str | None = None,
) -> dict:
    """Create a PostgreSQL database (and optional role) on ``postgres-main``.

    Idempotent: if the database already exists, returns without creating.
    Role creation is guarded by a ``pg_roles`` existence check inside a
    ``DO $$ ... $$`` block.

    Args:
        db_name: Database name. Must match ``[a-zA-Z_][a-zA-Z0-9_]{0,62}``.
        db_user: Optional dedicated role. If ``None`` or equal to ``"postgres"``,
            no role is created and the returned dict contains only ``database``.
        container: Override for the postgres container name. Defaults to the
            verified ``postgres-main-*`` UUID.
        dry_run: Skip all VPS mutations. Existence check is still attempted
            so the caller sees whether a real run would create or skip.

    Returns:
        ``{"status": "created" | "exists" | "dry_run", "database": db_name}``
        plus ``"user": db_user, "password": <32-char>`` when a new role was
        created. Existing databases return ``status=exists``.

    Raises:
        ValueError: ``db_name`` or ``db_user`` failed identifier validation.
        RuntimeError: The underlying ``ssh`` call failed (non-zero exit).

    Example:
        >>> create_database("my_project", "my_project_rw")  # doctest: +SKIP
        {'status': 'created', 'database': 'my_project', 'user': 'my_project_rw',
         'password': 'xY3...'}
    """
    _validate_identifier(db_name, "database")
    if db_user is not None and db_user != "postgres":
        _validate_identifier(db_user, "user")

    # Existence check — cheap, idempotent, safe in dry-run.
    # nosec B608 — db_name validated upstream by _validate_identifier (alnum+underscore only).
    check = _run_sql(
        f"SELECT 1 FROM pg_database WHERE datname='{db_name}';",  # nosec B608
        container=container,
        dry_run=dry_run,
    )
    if check.strip() == "1":
        logger.info("PostgreSQL database already exists: %s", db_name)
        return {"status": "exists", "database": db_name}

    if dry_run:
        logger.info("[DRY RUN] Would create PostgreSQL database: %s", db_name)
        result: dict = {"status": "dry_run", "database": db_name}
        if db_user and db_user != "postgres":
            result["user"] = db_user
        return result

    # Create database. Identifier safety is enforced by _validate_identifier.
    _run_sql(f'CREATE DATABASE "{db_name}";', container=container)
    logger.info("Created PostgreSQL database: %s", db_name)

    if not db_user or db_user == "postgres":
        # T4-01: record allocation. Only on status=created (new DB);
        # pre-existing DBs keep their seed/manual entries untouched.
        try:
            register_allocation(
                db_name,
                spec_id=spec_id,
                user="postgres",
                owner=owner,
                notes=notes,
                dry_run=False,
            )
        except Exception as exc:  # noqa: BLE001 — registry failure is non-fatal
            logger.warning(
                "postgres allocations: register %s failed (%s); DB exists but registry skipped",
                db_name,
                exc,
            )
        # Phase 6: per-DB Backrest plan. Non-fatal on failure — DB exists
        # already, operator can re-register the plan manually if backrest
        # is down at apply time.
        try:
            register_postgres_plan(db_name)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "backrest: register per-DB plan for %s failed (%s); operator must register manually",
                db_name,
                exc,
            )
        return {"status": "created", "database": db_name}

    # Dedicated role — generate CSPRNG password, create + grant in one SQL
    # batch. The DO block makes role creation idempotent against a partial
    # previous deploy where the role exists but the DB does not.
    password = _generate_password()

    role_and_grant = (
        f"DO $$ BEGIN\n"  # nosec B608 — db_user validated upstream by _validate_identifier; password is bcrypt-style generated
        f"  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{db_user}') THEN\n"
        f"    CREATE ROLE \"{db_user}\" LOGIN PASSWORD '{password}';\n"
        # Role already exists (e.g. the DB was dropped+recreated but the role was
        # left behind): reset its password to the freshly-generated one we return
        # and inject, otherwise the caller's DATABASE_URL would carry a password
        # that no longer matches the role -> "password authentication failed".
        f"  ELSE\n"
        f"    ALTER ROLE \"{db_user}\" WITH LOGIN PASSWORD '{password}';\n"
        f"  END IF;\n"
        f"END $$;\n"
        f'GRANT ALL PRIVILEGES ON DATABASE "{db_name}" TO "{db_user}";\n'
        # Make the dedicated role OWN the database so it can apply its own schema
        # (create tables/types, ALTER ... FORCE ROW LEVEL SECURITY) and own those
        # tables — required for multi-tenant RLS, which only applies to a
        # NON-superuser role. The app connects as this role (see the registrar's
        # injected DATABASE_URL), never as the postgres superuser (which bypasses RLS).
        f'ALTER DATABASE "{db_name}" OWNER TO "{db_user}";\n'
    )
    _run_sql(role_and_grant, container=container)
    logger.info("Created PostgreSQL role and granted privileges: %s -> %s", db_user, db_name)

    # Phase 5 of deploy-readiness-gaps (2026-06-30): seed restore. Runs AFTER
    # role+grant complete (so psql can connect) but BEFORE allocation
    # registration (so a registry write isn't created for a half-restored DB).
    # Idempotent: skipped if the DB already has user tables.
    seed_result: dict[str, Any] | None = None
    if seed_relpath and spec_dir and not dry_run:
        try:
            seed_result = _restore_seed(
                spec_dir=Path(spec_dir),
                seed_relpath=seed_relpath,
                container=container,
                db_user=db_user,
                db_name=db_name,
            )
            logger.info(
                "postgres seed: %s for %s (%s)",
                seed_result["status"],
                db_name,
                seed_result.get("reason") or seed_result.get("seed", ""),
            )
        except (ValueError, FileNotFoundError) as exc:
            logger.error(
                "postgres seed: validation/missing-file error for %s (%s) — "
                "DB+role created, no seed loaded; operator must investigate",
                db_name,
                exc,
            )
            seed_result = {"status": "failed", "reason": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "postgres seed: restore failed for %s (%s); DB+role exist, "
                "seed NOT loaded — operator must re-run manually",
                db_name,
                exc,
            )
            seed_result = {"status": "failed", "reason": str(exc)}

    # T4-01: record allocation with the dedicated role.
    try:
        register_allocation(
            db_name,
            spec_id=spec_id,
            user=db_user,
            owner=owner,
            notes=notes,
            dry_run=False,
        )
    except Exception as exc:  # noqa: BLE001 — registry failure is non-fatal
        logger.warning(
            "postgres allocations: register %s failed (%s); DB+role exist but registry skipped",
            db_name,
            exc,
        )

    # Phase 6: per-DB Backrest plan. Non-fatal on failure.
    try:
        register_postgres_plan(db_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "backrest: register per-DB plan for %s failed (%s); operator must register manually",
            db_name,
            exc,
        )

    result = {
        "status": "created",
        "database": db_name,
        "user": db_user,
        "password": password,
    }
    if seed_result is not None:
        result["seed"] = seed_result
    return result


# ---------------------------------------------------------------------------
# Watchdog per-project DB roles (fabrik-lib "product-aware watchdog" contract).
#
# When a spec has shape.needs_database AND the watchdog sidecar is applicable,
# the registrar mints two dedicated, PER-PROJECT roles on the app DB alongside
# the app's owner role:
#   {db}_wd_ro : SELECT-only  -> injected as WATCHDOG_DB_URL_RO (sidecar default,
#                                the diagnosis lane used across all tiers)
#   {db}_wd_rw : DML-only      -> injected as WATCHDOG_DB_URL_RW (Tier-C
#                                approved-write lane only)
# Per-project (NOT the shared, manual scripts/provision_watchdog_ro.py role):
# each sidecar's DSN reaches ONLY its own DB, so a compromised RO credential
# cannot read another tenant. RW carries no DDL/DROP and no ownership, so even
# the write lane cannot reshape the schema.
# ---------------------------------------------------------------------------

_WD_RO_SUFFIX = "_wd_ro"
_WD_RW_SUFFIX = "_wd_rw"


def _wd_role_names(db_name: str) -> tuple[str, str]:
    """Return ``(ro_role, rw_role)`` for ``db_name``; raise if either exceeds 63 chars.

    Postgres silently truncates identifiers past ``NAMEDATALEN`` (63), which would
    let two long db names collide on the same role — refuse loudly instead.
    """
    _validate_identifier(db_name, "database")
    ro = f"{db_name}{_WD_RO_SUFFIX}"
    rw = f"{db_name}{_WD_RW_SUFFIX}"
    for role in (ro, rw):
        if len(role) > 63:
            raise ValueError(
                f"watchdog role name {role!r} exceeds Postgres' 63-char identifier "
                f"limit — shorten depends.postgres for {db_name!r}"
            )
    return ro, rw


def _wd_drop_role_sql(db_name: str) -> str:
    """``DROP ROLE IF EXISTS`` for the two per-project watchdog roles.

    Empty string when the role names would be invalid / too long (they could
    never have been created, so nothing to drop). Idempotent: the roles own
    nothing and their grants live in the app DB, so a plain ``DROP ROLE IF
    EXISTS`` is a safe no-op when they are absent.
    """
    try:
        wd_ro, wd_rw = _wd_role_names(db_name)
    except ValueError:
        return ""
    return f'DROP ROLE IF EXISTS "{wd_ro}";\nDROP ROLE IF EXISTS "{wd_rw}";\n'


def _subagent_drop_role_sql(db_name: str) -> str:
    """``DROP ROLE IF EXISTS`` for the per-project subagent-ins role.

    Uses the same hyphen→underscore sanitization as `_provision_postgres` because
    the role was created against the sanitized identifier. Empty string when the
    sanitized name would be invalid / too long (the role could never have been
    created, so nothing to drop). Same wedge-cleanup motivation as watchdog: a
    drop+recreate cycle would leave the ins role behind with an out-of-band
    password → next apply's `_role_exists` returns True → no fresh DSN injected.
    Fixes Finder A#4.
    """
    sanitized = db_name.replace("-", "_")
    try:
        role = _subagent_ins_role_name(sanitized)
    except ValueError:
        return ""
    return f'DROP ROLE IF EXISTS "{role}";\n'


def _role_exists(role: str, container: str) -> bool:
    """True if a login role named ``role`` already exists on the cluster."""
    return (
        _run_sql(
            f"SELECT 1 FROM pg_roles WHERE rolname='{role}';",  # nosec B608 — role is a validated identifier, never free text
            container=container,
        ).strip()
        == "1"
    )


def _db_owner(db_name: str, container: str) -> str | None:
    """Return the role that OWNS ``db_name`` (validated), or ``None`` if unknown.

    ``ALTER DEFAULT PRIVILEGES FOR ROLE <owner>`` must name the role that CREATES
    future tables. Fabrik's convention is ``owner == db_name`` (see
    :func:`create_database`), but a legacy / manually-created / seed-restored DB
    can be owned by ``postgres`` or another role — assuming ``db_name`` there
    would make the ``ALTER DEFAULT PRIVILEGES`` statement reference a non-existent
    role and (under ``ON_ERROR_STOP``) abort the whole batch. Query the real owner
    from ``pg_database.datdba``. Return ``None`` when the lookup is empty (DB
    absent) or the name fails identifier validation — the caller then OMITS the
    default-privileges statements (existing tables are still granted; only
    auto-coverage of future tables is skipped) rather than emit a statement that
    references a role that may not exist.
    """
    # nosec B608 — db_name is validated by _wd_role_names before we get here.
    owner = _run_sql(
        f"SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname='{db_name}';",  # nosec B608
        container=container,
    ).strip()
    if not owner:
        logger.warning(
            "watchdog roles: could not resolve owner of DB %s (empty datdba lookup) — "
            "skipping DEFAULT PRIVILEGES; future tables won't auto-grant to RO/RW",
            db_name,
        )
        return None
    try:
        _validate_identifier(owner, "owner role")
    except ValueError:
        logger.warning(
            "watchdog roles: DB %s owner %r failed identifier validation — skipping "
            "DEFAULT PRIVILEGES (future tables won't auto-grant to RO/RW)",
            db_name,
            owner,
        )
        return None
    return owner


def create_watchdog_roles(
    db_name: str,
    container: str = POSTGRES_CONTAINER,
    dry_run: bool = False,
) -> dict:
    """Provision the watchdog RO + RW roles on an EXISTING app DB.

    Idempotent on the re-apply (existing-role) path; a fresh role is created with
    a plain ``CREATE ROLE`` (not a ``DO … IF NOT EXISTS`` block) *on purpose* — see
    the create-branch comment for why that's the safer choice under a create race.

    Password lifecycle mirrors :func:`create_database`'s ``DATABASE_URL``: a fresh
    CSPRNG password is generated and RETURNED **only when the role is newly
    created**; an already-existing role is left untouched and reports
    ``password=None``, so the caller does NOT re-inject its DSN and the value
    already in the project ``.env`` is preserved by :meth:`inject_env`'s merge.
    This is deliberate — rotating the password on every apply would break a
    running sidecar whenever a cached image build means Compose does not recreate
    the container to pick up the new ``.env`` (adversarial-review finding). The
    rare residual (a role orphaned by a partial failure mid-batch keeping an
    unrecoverable password) is the same accepted residual :func:`create_database`
    carries, and ``ON_ERROR_STOP`` makes any such failure loud rather than a false
    success.

    The batch runs under ``\\set ON_ERROR_STOP on`` so a failed GRANT / ``\\c``
    exits non-zero (``ssh`` raises) instead of psql's default continue-on-error
    that would report false success while leaving a role without its grants.
    Schema/table GRANTs are re-applied every call (idempotent, additive) so a
    watchdog enabled on a pre-existing DB — or tables added by a later migration —
    are covered; future tables are auto-covered via ``ALTER DEFAULT PRIVILEGES FOR
    ROLE <real-owner>`` (looked up, not assumed — see :func:`_db_owner`; omitted
    when the owner can't be resolved).

    Note: the roles are NON-owner, NON-superuser. On tables under ``FORCE ROW
    LEVEL SECURITY`` with no policy naming them, RLS default-denies — the RO
    diagnosis lane then reads only policy-permitted rows. A multi-tenant app that
    needs cross-tenant diagnosis must add a policy for ``{db}_wd_ro`` (or opt the
    role into ``BYPASSRLS`` upstream); least privilege is the default here.

    Args:
        db_name: The app DB. Must already exist (call after :func:`create_database`).
        container: Postgres container override.
        dry_run: Skip all VPS mutations; return markers with no passwords.

    Returns:
        ``{"ro": {"user", "password"|None, "status"}, "rw": {...}}``. ``password``
        is a fresh value only when the role was newly created (``None`` when the
        role already existed, or in dry-run) — the caller injects a DSN only when
        a fresh password is present.

    Raises:
        ValueError: a role name would exceed Postgres' 63-char identifier limit.
    """
    ro, rw = _wd_role_names(db_name)

    if dry_run:
        logger.info(
            "[DRY RUN] Would ensure watchdog roles %s (RO) + %s (RW) on %s", ro, rw, db_name
        )
        return {
            "ro": {"user": ro, "password": None, "status": "dry_run"},
            "rw": {"user": rw, "password": None, "status": "dry_run"},
        }

    ro_exists = _role_exists(ro, container)
    rw_exists = _role_exists(rw, container)
    pw_ro = None if ro_exists else _generate_password()
    pw_rw = None if rw_exists else _generate_password()
    owner = _db_owner(db_name, container)

    # Abort (non-zero exit) on the FIRST error rather than psql's default
    # continue-on-error-exit-0, which would report false success.
    sql_parts: list[str] = ["\\set ON_ERROR_STOP on"]
    # Create fresh roles only — an existing role is preserved (no password churn),
    # so its DSN in .env stays valid. LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE:
    # least privilege by construction. Plain CREATE (not a DO/IF-NOT-EXISTS block)
    # is deliberate: in the rare create race (two applies of one spec, or an
    # out-of-band role appearing between the _role_exists check and this batch),
    # a bare CREATE errors → ON_ERROR_STOP aborts → we DON'T inject a password that
    # wouldn't match the role. The winning apply injects a valid DSN; this one
    # fails loud and heals next apply. An IF-NOT-EXISTS create would instead
    # silently skip and let us inject a MISMATCHED password.
    if not ro_exists:
        sql_parts.append(
            f'CREATE ROLE "{ro}" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
            f"PASSWORD '{pw_ro}';"  # nosec B608 — pw is CSPRNG alnum, single-quote-safe
        )
    if not rw_exists:
        sql_parts.append(
            f'CREATE ROLE "{rw}" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
            f"PASSWORD '{pw_rw}';"  # nosec B608
        )
    # CONNECT is database-level; the rest must run INSIDE the app DB (\c), so ALL
    # TABLES / DEFAULT PRIVILEGES resolve against the app schema, not the
    # superuser's default `postgres` DB. Grants are idempotent → re-applied every
    # call so a newly-added table (or a watchdog enabled on a pre-existing DB) is
    # covered.
    sql_parts += [
        f'GRANT CONNECT ON DATABASE "{db_name}" TO "{ro}", "{rw}";',
        f"\\c {db_name}",
        f'GRANT USAGE ON SCHEMA public TO "{ro}", "{rw}";',
        # RO: SELECT only.
        f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{ro}";',
        # RW: DML only (no DDL, no ownership, no DROP) + sequence usage for INSERTs.
        f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{rw}";',
        f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{rw}";',
    ]
    if owner:
        # Future tables the owner creates auto-grant to the watchdog roles.
        sql_parts += [
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{owner}" IN SCHEMA public '
            f'GRANT SELECT ON TABLES TO "{ro}";',
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{owner}" IN SCHEMA public '
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{rw}";',
            f'ALTER DEFAULT PRIVILEGES FOR ROLE "{owner}" IN SCHEMA public '
            f'GRANT USAGE, SELECT ON SEQUENCES TO "{rw}";',
        ]
    # nosec B608 — every interpolated value (db_name, ro, rw, owner) is a role/DB
    # identifier already gated by _validate_identifier; passwords are CSPRNG alnum.
    _run_sql("\n".join(sql_parts) + "\n", container=container)  # nosec B608
    logger.info(
        "watchdog roles on %s (owner=%s): %s (RO, %s) + %s (RW, %s)",
        db_name,
        owner or "unknown",
        ro,
        "created" if not ro_exists else "exists",
        rw,
        "created" if not rw_exists else "exists",
    )
    return {
        "ro": {"user": ro, "password": pw_ro, "status": "created" if not ro_exists else "exists"},
        "rw": {"user": rw, "password": pw_rw, "status": "created" if not rw_exists else "exists"},
    }


# ── Subagent-runs telemetry: per-project INSERT-only role ─────────────────── #
#
# Every project vendoring `fabrik-lib/subagents` writes each run to the shared
# `subagent_runs` table on `fabrik_analytics`. Rather than sharing the postgres
# superuser DSN (which grants everything to every project), we mint a per-project
# `{project_id}_subagent_ins` role that can INSERT and nothing else. A compromised
# project key can only append rows tagged with its own SUBAGENT_PROJECT — no
# ability to read other projects' history, alter the schema, or delete anything.
#
# Password lifecycle mirrors :func:`create_watchdog_roles`: CSPRNG only on create,
# `password=None` on re-apply so the caller preserves the running project's `.env`.
# ---------------------------------------------------------------------------

_SUBAGENT_INS_SUFFIX = "_subagent_ins"


def _subagent_ins_role_name(project_id: str) -> str:
    """Return `{project_id}_subagent_ins`; raise if it exceeds 63 chars.

    Same 63-char guard as :func:`_wd_role_names` — Postgres silently truncates
    beyond ``NAMEDATALEN`` (63), which would let two long project names collide
    on the same role. Refuse loudly.
    """
    _validate_identifier(project_id, "project")
    role = f"{project_id}{_SUBAGENT_INS_SUFFIX}"
    if len(role) > 63:
        raise ValueError(
            f"subagent-ins role name {role!r} exceeds Postgres' 63-char identifier "
            f"limit — shorten the project id {project_id!r}"
        )
    return role


def create_subagent_ins_role(
    project_id: str,
    container: str = POSTGRES_CONTAINER,
    dry_run: bool = False,
) -> dict:
    """Provision a per-project INSERT-only role on `fabrik_analytics.subagent_runs`.

    Mirrors :func:`create_watchdog_roles` in discipline (CSPRNG-only-on-create,
    idempotent re-grant, ``\\set ON_ERROR_STOP on``, plain ``CREATE ROLE`` not
    IF-NOT-EXISTS so a create race errors loudly rather than injecting a
    mismatched password) but scoped per-PROJECT (not per-DB) since every project
    writes to the same shared table.

    Grants: ``CONNECT`` on ``fabrik_analytics``, ``USAGE`` on ``public``,
    ``INSERT`` on ``subagent_runs``, ``USAGE`` on ``subagent_runs_id_seq`` (needed
    because ``id BIGSERIAL`` allocates from that sequence). **No SELECT / UPDATE /
    DELETE** — a compromised project key cannot read other projects' rows,
    alter data, or delete history.

    Requires ``fabrik_analytics`` + ``subagent_runs`` to exist. Call after
    :func:`ensure_shared_analytics_db` has applied the ``SUBAGENT_RUNS_DDL``.

    Args:
        project_id: The project identifier (usually spec name / db_name).
        container: Postgres container override.
        dry_run: Skip all VPS mutations; return marker with no password.

    Returns:
        ``{"ins": {"user", "password"|None, "status"}}``. ``password`` is a fresh
        CSPRNG value only when the role was newly created (``None`` when the role
        already existed or in dry-run) — the caller injects a DSN only when a
        fresh password is present, so the .env of a running project is preserved.

    Raises:
        ValueError: role name would exceed Postgres' 63-char identifier limit.
    """
    role = _subagent_ins_role_name(project_id)

    if dry_run:
        logger.info(
            "[DRY RUN] Would ensure subagent-ins role %s on fabrik_analytics.subagent_runs",
            role,
        )
        return {"ins": {"user": role, "password": None, "status": "dry_run"}}

    role_exists = _role_exists(role, container)
    pw = None if role_exists else _generate_password()

    # Split into TWO psql invocations to avoid the wedge state the convergence
    # review flagged (Finder A#2 + A#3):
    #
    #   * Call 1 (postgres db): CREATE ROLE only, atomically. If this fails
    #     because a concurrent apply already created the role (CREATE race), the
    #     failure is loud, NO cleanup runs, the winner's role stays intact.
    #     Docstring's "fails loud and heals on next apply" contract is preserved.
    #
    #   * Call 2 (fabrik_analytics db): all GRANTs. Idempotent — re-applied every
    #     call, safe to re-run on the next apply if a mid-batch failure aborts
    #     this one. No transaction needed because the effect of "some grants
    #     applied, some not" is self-healing: the next apply re-issues them all.
    #
    # An earlier attempt used a single combined batch with a try/except drop-role
    # cleanup on partial failure. That cleanup was UNSAFE — it dropped the
    # role even when the failure was "CREATE ROLE already exists" from a race,
    # killing the winning apply's just-created role.
    if not role_exists:
        # nosec B608 — role name identifier-validated; pw is CSPRNG alnum.
        _run_sql(
            f'CREATE ROLE "{role}" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '  # nosec B608
            f"PASSWORD '{pw}';",
            container=container,
        )

    # Grants — always re-applied (idempotent, additive). Qualified with `public.`
    # to survive a future search_path drift (Finder A#9).
    grant_sql = (
        "\\set ON_ERROR_STOP on\n"
        f'GRANT CONNECT ON DATABASE "{FABRIK_ANALYTICS_DB}" TO "{role}";\n'
        f"\\c {FABRIK_ANALYTICS_DB}\n"
        f'GRANT USAGE ON SCHEMA public TO "{role}";\n'
        # INSERT only — least privilege. NO SELECT/UPDATE/DELETE on subagent_runs.
        f'GRANT INSERT ON public.subagent_runs TO "{role}";\n'
        # `id BIGSERIAL` needs sequence USAGE for INSERT to allocate the next id.
        f'GRANT USAGE ON SEQUENCE public.subagent_runs_id_seq TO "{role}";\n'
    )
    _run_sql(grant_sql, container=container)  # nosec B608

    logger.info(
        "subagent-ins role: %s (%s) on fabrik_analytics.subagent_runs",
        role,
        "created" if not role_exists else "exists",
    )
    return {
        "ins": {
            "user": role,
            "password": pw,
            "status": "created" if not role_exists else "exists",
        }
    }


def drop_database(
    db_name: str,
    db_user: str | None = None,
    container: str = POSTGRES_CONTAINER,
    dry_run: bool = False,
) -> dict:
    """Drop a PostgreSQL database (and optional role) on ``postgres-main``.

    Destructive — data loss is immediate and irreversible. The
    orchestrator's :class:`RollbackManager` intentionally does NOT call
    this; auto-rollback leaves databases in place by policy (see the
    module docstring and ``rollback.py::_rollback_postgres``). This
    function exists for **explicit, human-authorized** teardown paths:

    * ``fabrik destroy --drop-data <spec>`` — test-cleanup workflow
      after a throwaway deploy.
    * Direct operator invocation during post-mortem cleanup.

    Idempotent: ``DROP DATABASE IF EXISTS`` + ``DROP ROLE IF EXISTS``.

    Args:
        db_name: Database name. Must match identifier regex.
        db_user: Optional role to drop alongside the database.
        container: Override for the postgres container name.
        dry_run: Skip the actual DROP; log and return ``status=dry_run``.

    Returns:
        ``{"status": "dropped" | "not_found" | "dry_run", "database": db_name}``.

    Raises:
        ValueError: ``db_name`` or ``db_user`` failed identifier validation.
        RuntimeError: The underlying ``ssh`` call failed (non-zero exit).
    """
    _validate_identifier(db_name, "database")
    if db_user is not None and db_user != "postgres":
        _validate_identifier(db_user, "user")

    # Existence check so the caller can tell "really dropped now" from
    # "was already gone". Matches the idempotency contract of
    # ``create_database`` which returns ``status=exists`` vs ``created``.
    # nosec B608 — db_name pre-validated (alnum+underscore only); single-tenant VPS.
    check = _run_sql(
        f"SELECT 1 FROM pg_database WHERE datname='{db_name}';",  # nosec B608
        container=container,
        dry_run=dry_run,
    )
    exists = check.strip() == "1"

    if dry_run:
        logger.info(
            "[DRY RUN] Would DROP DATABASE %s (exists=%s)",
            db_name,
            exists,
        )
        return {"status": "dry_run", "database": db_name, "existed": exists}

    if not exists:
        logger.info("PostgreSQL database not found (nothing to drop): %s", db_name)
        # Still clean up any ORPHANED per-project watchdog + subagent roles: a
        # prior drop may have removed the DB but left these behind (or the DB
        # was dropped manually), which is the exact stuck state the cleanup
        # exists to prevent.
        orphan_sql = _wd_drop_role_sql(db_name) + _subagent_drop_role_sql(db_name)
        if orphan_sql:
            _run_sql(orphan_sql, container=container)
        return {"status": "not_found", "database": db_name}

    # DROP DATABASE cannot run inside a transaction; psql's ``-tA`` +
    # stdin pattern is autocommit per statement, so this is fine.
    # WITH (FORCE) kicks off any idle connections (Postgres 13+) so the
    # drop doesn't hang behind a stale connection from the just-destroyed
    # app container.
    sql = f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE);\n'
    if db_user and db_user != "postgres":
        sql += f'DROP ROLE IF EXISTS "{db_user}";\n'
    # Also drop the per-project watchdog + subagent-ins roles (created by
    # create_watchdog_roles + create_subagent_ins_role), AFTER the DB so their
    # grants/default-privileges are already gone. Without this a drop+recreate
    # cycle leaves them behind → the next apply sees them as existing → no
    # fresh password minted → .env stuck without WATCHDOG_DB_URL_*/SUBAGENT_RUNS_DSN.
    sql += _wd_drop_role_sql(db_name)
    sql += _subagent_drop_role_sql(db_name)
    _run_sql(sql, container=container)
    logger.info("Dropped PostgreSQL database: %s", db_name)

    # T4-01: remove allocation entry (idempotent — missing entry is a no-op).
    try:
        unregister_allocation(db_name, dry_run=False)
    except Exception as exc:  # noqa: BLE001 — registry failure is non-fatal
        logger.warning(
            "postgres allocations: unregister %s failed (%s); DB dropped but registry stale",
            db_name,
            exc,
        )

    # Phase 6: unregister per-DB Backrest plan + scrub the tracked-DBs file.
    # Non-fatal: if backrest is down, the orphaned plan is harmless (pre-
    # backup.sh skips DBs that no longer exist via pg_dump's own check).
    try:
        unregister_postgres_plan(db_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "backrest: unregister per-DB plan for %s failed (%s); operator may need to scrub",
            db_name,
            exc,
        )

    return {"status": "dropped", "database": db_name}


# ── Allocation registry (T4-01 G-J4) ────────────────────────────────────── #


def _load_remote_allocations() -> dict[str, Any]:
    """Read ``allocations.json`` from VPS via SSH. Returns the empty-shape dict
    ``{"version": 1, "allocations": {}}`` when the file is missing or empty
    (first-run on a fresh VPS). Raises ``json.JSONDecodeError`` on a corrupted
    file — caller decides whether to abort or overwrite.
    """
    try:
        raw = ssh(f"sudo cat {shlex.quote(ALLOCATIONS_PATH)}")
    except RuntimeError as e:
        logger.warning(
            "postgres allocations: cat %s failed (%s) — assuming empty registry",
            ALLOCATIONS_PATH,
            e,
        )
        return {"version": 1, "allocations": {}}
    if not raw.strip():
        return {"version": 1, "allocations": {}}
    return json.loads(raw)


def _write_remote_allocations(payload: dict[str, Any], *, dry_run: bool = False) -> None:
    """Atomic write of ``allocations.json`` via tee → /tmp → sudo mv.

    Mirrors the pattern in ``fabrik.orchestrator.coolify_alias`` — write
    to a tmp file, then chown/chmod/mv in a single ssh round. Concurrent
    writers (cron + manual) cannot leave the file half-written; the worst
    case is that one writer's payload overwrites the other's. WSL-side
    serialization is provided by ``file_lock`` in ``register_allocation``
    / ``unregister_allocation``.
    """
    payload = dict(payload)
    payload["last_updated"] = _dt.datetime.now(_dt.UTC).isoformat(timespec="seconds")
    new_content = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    quoted = shlex.quote(new_content)
    tmp_path = f"{ALLOCATIONS_PATH}.tmp"
    ssh(
        f"sudo mkdir -p {shlex.quote(ALLOCATIONS_PATH.rsplit('/', 1)[0])} && "
        f"sudo tee {shlex.quote(tmp_path)} > /dev/null <<< {quoted}",
        dry_run=dry_run,
    )
    ssh(
        f"sudo chown root:root {shlex.quote(tmp_path)} && "
        f"sudo chmod 644 {shlex.quote(tmp_path)} && "
        f"sudo mv {shlex.quote(tmp_path)} {shlex.quote(ALLOCATIONS_PATH)}",
        dry_run=dry_run,
    )


def list_allocations() -> dict[str, Any]:
    """Public read API. Returns the parsed registry payload.

    Empty-shape ``{"version": 1, "allocations": {}}`` when the file is
    missing — callers should treat that as "no allocations yet" rather
    than an error.
    """
    return _load_remote_allocations()


def register_allocation(
    db_name: str,
    *,
    spec_id: str | None,
    user: str = "postgres",
    owner: str = "fabrik",
    notes: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Insert / update an entry in the allocation registry.

    Read-modify-write under a local file lock so two concurrent
    ``fabrik apply`` invocations on the same workstation can't lose
    each other's writes (cross-host concurrency is out of scope on a
    solo-dev VPS).

    Args:
        db_name: The PostgreSQL database name (registry key).
        spec_id: The owning spec id (or ``None`` for infrastructure
            services like ``glitchtip`` that aren't Fabrik Applications).
        user: The DB owner role; defaults to ``postgres`` for shared
            roles, set to the dedicated role name when ``create_database``
            provisioned one.
        owner: ``fabrik`` (created by orchestrator), ``manual`` (created
            out-of-band; recorded for visibility), or ``infrastructure``
            (Coolify Service or VPS-bootstrap DB).
        notes: Free-text. The seed entries use this to record
            ``infra.postgres: false`` overrides and historical context.
        dry_run: Skip the actual VPS write. Local merge still happens
            so the caller's logs reflect the intended payload.

    Returns:
        The merged registry payload (post-update).
    """
    if dry_run:
        logger.info(
            "[DRY RUN] Would register postgres allocation: db=%s spec=%s owner=%s",
            db_name,
            spec_id,
            owner,
        )

    with file_lock("postgres-allocations", timeout_seconds=15.0):
        payload = _load_remote_allocations()
        allocations = payload.setdefault("allocations", {})
        allocations[db_name] = {
            "owner": owner,
            "spec_id": spec_id,
            "user": user,
            "notes": notes,
        }
        if not dry_run:
            _write_remote_allocations(payload)
        return payload


def unregister_allocation(db_name: str, *, dry_run: bool = False) -> dict[str, Any]:
    """Remove an entry from the allocation registry (idempotent).

    Returns the merged registry payload (post-update). Missing entries
    are a no-op; the caller does not need to pre-check existence.
    """
    if dry_run:
        logger.info("[DRY RUN] Would unregister postgres allocation: db=%s", db_name)

    with file_lock("postgres-allocations", timeout_seconds=15.0):
        payload = _load_remote_allocations()
        allocations = payload.setdefault("allocations", {})
        if db_name in allocations:
            del allocations[db_name]
            if not dry_run:
                _write_remote_allocations(payload)
        return payload


# ── Shared fabrik_analytics database (T-P1 watchdog platform) ───────────── #


FABRIK_ANALYTICS_DB = "fabrik_analytics"
"""Shared database on postgres-main backing cross-project analytics.

Provisioned by :func:`ensure_shared_analytics_db` once per cluster
(idempotent). Currently hosts the ``cost_ledger`` table (cost-budget
fabrik-lib module); future shared analytics tables land here too.
"""

COST_BUDGET_SCHEMA_PATH = "/opt/fabrik-lib/cost-budget/schema_pg.sql"

SUBAGENTS_MODULE_ROOT = "/opt/fabrik-lib/subagents"
"""Path to the vendored subagents fabrik-lib module. Home of `SUBAGENT_RUNS_DDL`
(read at apply-time via `python -c "from subagents import SUBAGENT_RUNS_DDL"`)
so schema changes to the module propagate on the next `fabrik apply` without
requiring a copy of the DDL to live here."""


def _read_subagent_runs_ddl() -> str:
    """Import SUBAGENT_RUNS_DDL from the vendored subagents module and return it.

    Runs `sys.executable -c` in a subprocess with cwd=/opt/fabrik-lib/subagents so we
    don't have to add that path to fabrik's sys.path at import time (would create a
    circular dep if fabrik-lib ever imports back). Raises RuntimeError on any failure
    so the caller can decide whether to bail or degrade.

    Two subtleties the convergence review caught:
      * Use `sys.executable` (fabrik's venv), NOT `python3` (system PATH). A lean
        orchestrator host may lack fabrik-lib's httpx / anthropic deps in system
        python; sys.executable reuses fabrik's own venv which HAS them.
      * Import from `subagents.pg_ledger` submodule directly, NOT via the package's
        `__init__.py`. The package's __init__ transitively imports httpx via
        `.agent → .loop → httpx`; even under sys.executable this is unnecessary
        weight for reading a plain string constant.
    """
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from subagents.pg_ledger import SUBAGENT_RUNS_DDL; print(SUBAGENT_RUNS_DDL)",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=SUBAGENTS_MODULE_ROOT,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"failed to import SUBAGENT_RUNS_DDL from {SUBAGENTS_MODULE_ROOT}: "
            f"{result.stderr.strip()}"
        )
    ddl = result.stdout.strip()
    if not ddl or "CREATE TABLE" not in ddl:
        raise RuntimeError(f"SUBAGENT_RUNS_DDL imported but content looks wrong: {ddl[:200]!r}")
    return ddl


"""Canonical DDL location read by :func:`ensure_shared_analytics_db`.

The fabrik-lib module is the single source of truth — change the DDL
there, the orchestrator picks it up on the next ``fabrik apply``."""


def ensure_shared_analytics_db(
    *,
    container: str = POSTGRES_CONTAINER,
    grant_to_role: str | None = None,
    schema_path: str = COST_BUDGET_SCHEMA_PATH,
    dry_run: bool = False,
) -> dict:
    """Idempotently provision the shared ``fabrik_analytics`` database +
    apply the canonical ``cost_ledger`` DDL from ``/opt/fabrik-lib/cost-budget/schema_pg.sql``.

    Steps:
      1. ``CREATE DATABASE fabrik_analytics`` if not exists (uses the same
         ``pg_database`` existence check as :func:`create_database`).
      2. Apply ``schema_path``'s DDL inside ``fabrik_analytics`` —
         ``CREATE TABLE IF NOT EXISTS cost_ledger`` + indexes.
      3. If ``grant_to_role`` is provided, ``GRANT INSERT, SELECT ON
         cost_ledger TO "<role>"``. (Currently v1 callers don't pass
         a role — projects use the ``postgres`` superuser, which already
         has all privileges. Parameter is future-proofed for when
         per-project roles are wired.)

    Called from :class:`InfrastructureProvisioner._provision_postgres`
    AFTER ``create_database(spec)``. Safe to call multiple times per
    ``fabrik apply`` (every call is idempotent at the DB level).

    Args:
        container:     Override for the postgres container name.
        grant_to_role: Optional role to grant INSERT, SELECT on
                       ``cost_ledger``. Validated via the same identifier
                       regex as ``create_database``.
        schema_path:   Path on the WSL/local side to the canonical DDL.
                       Read at call time (not import time).
        dry_run:       Skip the actual mutations. Existence check still
                       runs so the caller's logs reflect what would happen.

    Returns:
        ``{"status": "created" | "exists" | "dry_run",
           "database": "fabrik_analytics",
           "schema_applied": bool,
           "granted_to": role_or_None}``.

    Raises:
        ValueError:    ``grant_to_role`` failed identifier validation.
        FileNotFoundError: ``schema_path`` does not exist on the orchestrator.
        RuntimeError:  The underlying ``ssh`` call failed.
    """
    if grant_to_role is not None and grant_to_role != "postgres":
        _validate_identifier(grant_to_role, "role")

    # Step 1: existence check.
    # nosec B608 — FABRIK_ANALYTICS_DB is a module constant, not user input.
    check = _run_sql(
        f"SELECT 1 FROM pg_database WHERE datname='{FABRIK_ANALYTICS_DB}';",  # nosec B608
        container=container,
        dry_run=dry_run,
    )
    db_exists = check.strip() == "1"

    result: dict[str, Any] = {
        "database": FABRIK_ANALYTICS_DB,
        "schema_applied": False,
        "granted_to": grant_to_role,
    }

    if dry_run:
        logger.info(
            "[DRY RUN] Would ensure shared analytics DB: %s (exists=%s)",
            FABRIK_ANALYTICS_DB,
            db_exists,
        )
        result["status"] = "dry_run"
        return result

    if not db_exists:
        _run_sql(
            f'CREATE DATABASE "{FABRIK_ANALYTICS_DB}";',
            container=container,
        )
        logger.info("Created shared analytics database: %s", FABRIK_ANALYTICS_DB)
        result["status"] = "created"
        # Register in the allocation registry so audit / drift-detection
        # tooling sees fabrik_analytics as a known infrastructure DB,
        # not an orphan. Non-fatal: registry write failures must not
        # block the deploy (same pattern as create_database()).
        try:
            register_allocation(
                FABRIK_ANALYTICS_DB,
                spec_id=None,
                user="postgres",
                owner="infrastructure",
                notes="Shared cross-project analytics DB; hosts cost_ledger (cost-budget module).",
                dry_run=False,
            )
        except Exception as exc:  # noqa: BLE001 — registry failure is non-fatal
            logger.warning(
                "postgres allocations: register %s failed (%s); DB created but registry skipped",
                FABRIK_ANALYTICS_DB,
                exc,
            )
    else:
        result["status"] = "exists"

    # Step 2: apply schema. Read locally and pipe to psql -d fabrik_analytics.
    from pathlib import Path

    ddl = Path(schema_path).read_text(encoding="utf-8")  # raises FileNotFoundError if absent
    # Base64-encode and execute against the fabrik_analytics DB. Same
    # pattern as _run_sql but targeting a non-default DB.
    payload = base64.b64encode(ddl.encode()).decode()
    ssh(
        f"echo {payload} | base64 -d | sudo docker exec -i {container} "
        f"psql -U postgres -d {FABRIK_ANALYTICS_DB} -tA"
    )
    result["schema_applied"] = True
    logger.info("Applied cost_ledger DDL from %s", schema_path)

    # Step 2b (2026-07-06): also apply SUBAGENT_RUNS_DDL from the vendored subagents
    # module. The DDL is a Python string exported by pg_ledger.py — import it in a
    # subprocess so we don't have to add fabrik-lib/subagents to fabrik's sys.path.
    # Idempotent (`CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`).
    # Failure here is non-fatal (logged): a cluster missing subagent_runs falls back
    # to JSONL-only in vendored projects; the per-project subagent_ins role provisioning
    # in _provision_postgres will log a warning if the table isn't there.
    try:
        subagent_ddl = _read_subagent_runs_ddl()
    except Exception as exc:  # noqa: BLE001 — non-fatal
        logger.warning(
            "Could not read SUBAGENT_RUNS_DDL from /opt/fabrik-lib/subagents (%s); "
            "subagent_runs table NOT applied. Projects that vendor subagents will "
            "fall back to JSONL-only.",
            exc,
        )
    else:
        payload = base64.b64encode(subagent_ddl.encode()).decode()
        # Use ON_ERROR_STOP so mid-batch failures propagate as non-zero and get logged,
        # rather than psql's default continue-on-error (which returns 0 even on partial DDL).
        ssh(
            f"echo {payload} | base64 -d | sudo docker exec -i {container} "
            f"psql -U postgres -d {FABRIK_ANALYTICS_DB} -v ON_ERROR_STOP=1 -tA"
        )
        logger.info("Applied SUBAGENT_RUNS_DDL to %s", FABRIK_ANALYTICS_DB)

    # Step 3: optional GRANT.
    if grant_to_role and grant_to_role != "postgres":
        grant_sql = f'GRANT INSERT, SELECT ON cost_ledger TO "{grant_to_role}";'
        payload = base64.b64encode(grant_sql.encode()).decode()
        ssh(
            f"echo {payload} | base64 -d | sudo docker exec -i {container} "
            f"psql -U postgres -d {FABRIK_ANALYTICS_DB} -tA"
        )
        logger.info(
            "Granted INSERT,SELECT on cost_ledger to %s in %s",
            grant_to_role,
            FABRIK_ANALYTICS_DB,
        )

    return result


__all__ = (
    "POSTGRES_CONTAINER",
    "PASSWORD_ALPHABET",
    "PASSWORD_LENGTH",
    "ALLOCATIONS_PATH",
    "FABRIK_ANALYTICS_DB",
    "COST_BUDGET_SCHEMA_PATH",
    "create_database",
    "drop_database",
    "ensure_shared_analytics_db",
    "list_allocations",
    "register_allocation",
    "unregister_allocation",
)
