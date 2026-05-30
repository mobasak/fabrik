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
import re
import secrets
import shlex
import string
from typing import Any

from fabrik.drivers.ssh import ssh
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


def create_database(
    db_name: str,
    db_user: str | None = None,
    container: str = POSTGRES_CONTAINER,
    dry_run: bool = False,
    spec_id: str | None = None,
    owner: str = "fabrik",
    notes: str = "",
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
        return {"status": "created", "database": db_name}

    # Dedicated role — generate CSPRNG password, create + grant in one SQL
    # batch. The DO block makes role creation idempotent against a partial
    # previous deploy where the role exists but the DB does not.
    password = _generate_password()

    role_and_grant = (
        f"DO $$ BEGIN\n"  # nosec B608 — db_user validated upstream by _validate_identifier; password is bcrypt-style generated
        f"  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{db_user}') THEN\n"
        f"    CREATE ROLE \"{db_user}\" LOGIN PASSWORD '{password}';\n"
        f"  END IF;\n"
        f"END $$;\n"
        f'GRANT ALL PRIVILEGES ON DATABASE "{db_name}" TO "{db_user}";\n'
    )
    _run_sql(role_and_grant, container=container)
    logger.info("Created PostgreSQL role and granted privileges: %s -> %s", db_user, db_name)

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

    return {
        "status": "created",
        "database": db_name,
        "user": db_user,
        "password": password,
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
        return {"status": "not_found", "database": db_name}

    # DROP DATABASE cannot run inside a transaction; psql's ``-tA`` +
    # stdin pattern is autocommit per statement, so this is fine.
    # WITH (FORCE) kicks off any idle connections (Postgres 13+) so the
    # drop doesn't hang behind a stale connection from the just-destroyed
    # app container.
    sql = f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE);\n'
    if db_user and db_user != "postgres":
        sql += f'DROP ROLE IF EXISTS "{db_user}";\n'
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
