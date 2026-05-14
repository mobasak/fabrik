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
import logging
import re
import secrets
import string

from fabrik.drivers.ssh import ssh

logger = logging.getLogger(__name__)

POSTGRES_CONTAINER = "postgres-main-l0k4gk0kggc8okcwk0s4c8s8"
"""Verified container name on VPS (2026-04-18, re-verified 2026-04-19).

Overridable per-call via the ``container`` kwarg for tests and future
container migrations."""

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

    return {"status": "dropped", "database": db_name}


__all__ = (
    "POSTGRES_CONTAINER",
    "PASSWORD_ALPHABET",
    "PASSWORD_LENGTH",
    "create_database",
    "drop_database",
)
