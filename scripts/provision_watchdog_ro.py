#!/usr/bin/env python3
# AFTER-EDIT: none
"""Provision the ``watchdog_ro`` read-only Postgres role (deploy-readiness follow-on).

The watchdog sidecar's **direct-DB investigation tool** (used only when an operator
enables the investigation lane, ``WATCHDOG_INVESTIGATE=true``) needs a SELECT-only
role on ``postgres-main``. The HTTP observability tools (Prometheus/Loki/Gatus/
GlitchTip) need no DB access — this role is exclusively for the direct-DB read.

Least-privilege by construction: the role is ``LOGIN NOSUPERUSER NOCREATEDB
NOCREATEROLE`` with **no grants** until you explicitly grant read-only access on a
specific project DB. So a rogue autonomous diagnosis can only ``SELECT`` on the DBs
you opt in — never write, never DDL, never reach another tenant's DB.

Usage (run from /opt/fabrik on the hub; talks to postgres-main over SSH):
    python scripts/provision_watchdog_ro.py create          # ensure the role (no grants)
    python scripts/provision_watchdog_ro.py grant  <db>     # CONNECT + SELECT on one DB
    python scripts/provision_watchdog_ro.py revoke <db>     # remove that access
    python scripts/provision_watchdog_ro.py status          # show the role + its grants

Password: generated (32-char CSPRNG) on first ``create`` and stored in
``/opt/fabrik/.env.sysadmin`` as ``WATCHDOG_RO_PG_PASSWORD`` (0600, gitignored).
Deliver the DSN to a watchdog only when its project enables investigation:
    postgresql://watchdog_ro:<pw>@postgres-main:5432/<db>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fabrik.drivers.postgres import (  # noqa: E402
    POSTGRES_CONTAINER,
    _generate_password,
    _run_sql,
)

ROLE = "watchdog_ro"
SYSADMIN_ENV = Path("/opt/fabrik/.env.sysadmin")
_DB_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def _validate_db_name(db: str) -> str:
    """Return ``db`` iff it is a safe Postgres identifier; else raise.

    Highest-risk path: ``db`` is interpolated into GRANT/``\\c`` SQL, so an
    unvalidated value is an injection vector. Postgres identifiers are lowercase
    alnum + underscore (fabrik derives them from kebab spec ids). Reject anything
    else — no quotes, spaces, semicolons, or dashes.
    """
    if not _DB_NAME_RE.match(db or ""):
        raise ValueError(f"unsafe/invalid db name {db!r}: expected ^[a-z_][a-z0-9_]{{0,62}}$")
    return db


def _role_exists() -> bool:
    return (
        _run_sql(f"SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}';", POSTGRES_CONTAINER).strip()
        == "1"
    )


def _read_stored_password() -> str | None:
    if not SYSADMIN_ENV.exists():
        return None
    for line in SYSADMIN_ENV.read_text().splitlines():
        if line.startswith("WATCHDOG_RO_PG_PASSWORD="):
            return line.split("=", 1)[1].strip()
    return None


def _store_password(pw: str) -> None:
    existing = SYSADMIN_ENV.read_text() if SYSADMIN_ENV.exists() else ""
    if "WATCHDOG_RO_PG_PASSWORD=" in existing:
        return
    sep = "" if existing.endswith("\n") or not existing else "\n"
    SYSADMIN_ENV.write_text(f"{existing}{sep}WATCHDOG_RO_PG_PASSWORD={pw}\n")
    SYSADMIN_ENV.chmod(0o600)


def create() -> None:
    if _role_exists():
        # Idempotent: never churn the password of an existing role (would break
        # any watchdog already holding the DSN). Just re-assert read-only attrs.
        _run_sql(
            f'ALTER ROLE "{ROLE}" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;',
            POSTGRES_CONTAINER,
        )
        print(f"{ROLE} already exists — read-only attributes re-asserted, password unchanged.")
        return
    pw = _read_stored_password() or _generate_password()  # alnum only → single-quote safe
    _run_sql(
        f"CREATE ROLE \"{ROLE}\" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{pw}';",
        POSTGRES_CONTAINER,
    )
    _store_password(pw)
    print(f"{ROLE} created (LOGIN, read-only, NO grants). Password stored in {SYSADMIN_ENV}.")


def grant(db: str) -> None:
    db = _validate_db_name(db)
    # CONNECT is db-level; USAGE/SELECT + default-privileges must run inside the db.
    sql = (
        f'GRANT CONNECT ON DATABASE "{db}" TO "{ROLE}";\n'
        f"\\c {db}\n"
        f'GRANT USAGE ON SCHEMA public TO "{ROLE}";\n'
        f'GRANT SELECT ON ALL TABLES IN SCHEMA public TO "{ROLE}";\n'
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO "{ROLE}";\n'
    )
    _run_sql(sql, POSTGRES_CONTAINER)
    print(f"granted read-only (CONNECT + SELECT, incl. future tables) on {db!r} to {ROLE}")


def revoke(db: str) -> None:
    db = _validate_db_name(db)
    sql = (
        f"\\c {db}\n"
        f'REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM "{ROLE}";\n'
        f'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM "{ROLE}";\n'
        f'REVOKE USAGE ON SCHEMA public FROM "{ROLE}";\n'
        f"\\c postgres\n"
        f'REVOKE CONNECT ON DATABASE "{db}" FROM "{ROLE}";\n'
    )
    _run_sql(sql, POSTGRES_CONTAINER)
    print(f"revoked read-only access on {db!r} from {ROLE}")


def status() -> None:
    exists = _role_exists()
    print(f"{ROLE} exists: {exists}")
    if exists:
        grants = _run_sql(
            "SELECT datname FROM pg_database d "
            f"WHERE has_database_privilege('{ROLE}', d.datname, 'CONNECT') "
            "AND datistemplate = false ORDER BY 1;",
            POSTGRES_CONTAINER,
        )
        print(
            "  reachable via CONNECT (mostly PUBLIC default — CONNECT alone reads "
            "NOTHING; only `grant <db>` adds the USAGE+SELECT that permits reads):\n"
            + ("\n".join(f"    {g}" for g in grants.split()) or "    (none)")
        )


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {"create", "grant", "revoke", "status"}:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd in {"grant", "revoke"}:
        if len(argv) != 3:
            print(f"usage: provision_watchdog_ro.py {cmd} <db_name>", file=sys.stderr)
            return 2
        (grant if cmd == "grant" else revoke)(argv[2])
    else:
        {"create": create, "status": status}[cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
