"""W-5985e74a — the payments fulfilment role against a REAL PostgreSQL and fabrik-lib's schema.

Plan docs/development/plans/2026-10-08-plan-2-payments-fulfilment-role.md Phase A (spec
docs/superpowers/specs/2026-09-30-payments-fulfilment-role-design.md § The delta items 2-4, 6).
The driver mints the role (``mint_payments_role``), the caller delivers its DSN, and only then
``grant_payments_role`` runs the grant batch, so a raising grant never strands the password.
The fulfilment grant is fabrik-lib's ``payments_grant_fulfilment``, never a hub-written
fallback. The schema is read from the box's fabrik-lib checkout; without it (or without docker)
these rows skip, and ``FABRIK_REQUIRE_REAL_PG=1`` turns either skip into a failure.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

import fabrik.drivers.postgres as pg
from tests.test_app_role_real_pg import ScratchPg, scratch_pg

_PAYMENTS = Path(os.getenv("FABRIK_LIB_ROOT", "/opt/fabrik-lib")) / "payments"
_PAYMENTS_DB = _PAYMENTS / "db"
_MIGRATION = _PAYMENTS_DB / "migrations" / "2026-09-29-scoped-service-roles.sql"
DB = "ti"
FULFIL = "ti_payments_fulfilment"
INGEST = "ti_payments_ingest"
ORG = "11111111-1111-1111-1111-111111111111"
# the refusal names its recovery; the foreign-role test then follows it
_RECOVERY = (
    r"refusing to re-assert its attributes\. Narrow it by hand \(ALTER ROLE "
    rf"{FULFIL} NOSUPERUSER; give each database it owns another owner\) or drop it once it "
    r"owns none, then re-apply"
)
_FN_BEGIN = "-- BEGIN payments grant functions"
_FN_END = "-- END payments grant functions"


def _schema() -> str:
    if not (_PAYMENTS_DB / "schema.sql").is_file() or not _MIGRATION.is_file():
        reason = f"fabrik-lib payments schema not found under {_PAYMENTS_DB}"
        if os.environ.get("FABRIK_REQUIRE_REAL_PG") == "1":
            pytest.fail(f"FABRIK_REQUIRE_REAL_PG=1 but {reason}")
        pytest.skip(reason)
    return (_PAYMENTS_DB / "schema.sql").read_text()


def _grant_functions() -> str:
    """The migration's grant-function block: what applying fabrik-lib's migration adds."""
    text = _MIGRATION.read_text()
    return text[text.index(_FN_BEGIN) : text.index(_FN_END) + len(_FN_END)]


def _in_db(s: ScratchPg, sql: str) -> str:
    """Run ``sql`` as the superuser inside the app DB; return its last output line."""
    out = s.run_sql(f"\\set ON_ERROR_STOP on\n\\c {DB}\n{sql}")
    return out.splitlines()[-1] if out else ""


def _owner_db(s: ScratchPg) -> None:
    s.run_sql(
        f"\\set ON_ERROR_STOP on\nCREATE ROLE {DB} WITH LOGIN;\nCREATE DATABASE {DB} OWNER {DB};\n"
    )


def _database(s: ScratchPg, schema: str, *, with_jobs: bool = True, functions: bool = True) -> None:
    """Owner ``ti`` owning fabrik-lib's payments schema and the project's ``jobs`` queue."""
    _owner_db(s)
    jobs = (
        "CREATE TABLE jobs (id bigserial PRIMARY KEY, org_id uuid NOT NULL, "
        "status text NOT NULL DEFAULT 'queued');\n"
        if with_jobs
        else ""
    )
    s.run_sql(f"\\set ON_ERROR_STOP on\n\\c {DB}\nSET ROLE {DB};\n{schema}\n{jobs}")
    if not functions:
        _in_db(
            s,
            "DROP FUNCTION payments_grant_ingest(pg_catalog.regrole);\n"
            "DROP FUNCTION payments_grant_fulfilment(pg_catalog.regrole);",
        )


def _mint(s: ScratchPg, lane: str) -> dict:
    with s.as_driver():
        return pg.mint_payments_role(DB, lane)


def _grant(s: ScratchPg, lane: str) -> str:
    with s.as_driver():
        return pg.grant_payments_role(DB, lane)["grants"]


def _can(s: ScratchPg, check: str) -> bool:
    return _in_db(s, f"SELECT {check};") == "t"


def _container_ip(s: ScratchPg) -> str:
    out = subprocess.run(
        [
            "docker",
            "inspect",
            "-f",
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            s.container,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return out.stdout.strip()


def test_the_function_path_grants_and_the_worker_claims_then_scopes() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema)
        minted = _mint(s, "fulfilment")
        assert minted["user"] == FULFIL and minted["password"] and minted["status"] == "created"
        assert _grant(s, "fulfilment") == "module"
        _in_db(s, f"INSERT INTO jobs (org_id) VALUES ('{ORG}');")
        # the worker claims across orgs with NO tenant GUC, then scopes to the job's org
        out = s.login_sql(
            FULFIL,
            minted["password"],
            "BEGIN;\n"
            "SELECT org_id FROM jobs WHERE status = 'queued' ORDER BY id "
            "FOR UPDATE SKIP LOCKED LIMIT 1;\n"
            "UPDATE jobs SET status = 'running' WHERE id = 1;\n"
            f"SELECT set_config('app.tenant_id', '{ORG}', true);\n"
            "INSERT INTO purchases (org_id, provider, provider_ref, plan_id, amount_cents, currency) "
            f"VALUES ('{ORG}', 'paytr', 'oid-1', 'pro', 1000, 'TRY');\n"
            "COMMIT;\n",
            db=DB,
        )
        assert ORG in out
        assert _in_db(s, "SELECT count(*) FROM purchases;") == "1"
        assert _in_db(s, "SELECT status FROM jobs WHERE id = 1;") == "running"


def test_the_fulfilment_login_passes_verify_service_role_and_bypasses_nothing() -> None:
    schema = _schema()
    try:
        import psycopg
    except ImportError:
        if os.environ.get("FABRIK_REQUIRE_REAL_PG") == "1":
            pytest.fail("FABRIK_REQUIRE_REAL_PG=1 but psycopg is not installed")
        pytest.skip("psycopg is not installed")
    sys.path.insert(0, str(_PAYMENTS))
    try:
        from payments.store import verify_service_role  # type: ignore[import-not-found]
    finally:
        sys.path.remove(str(_PAYMENTS))
    with scratch_pg() as s:
        _database(s, schema)
        minted = _mint(s, "fulfilment")
        assert _grant(s, "fulfilment") == "module"
        flags = s.login_sql(
            FULFIL,
            minted["password"],
            "SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user;",
            db=DB,
        )
        assert flags == "f|f"
        with psycopg.connect(
            host=_container_ip(s), dbname=DB, user=FULFIL, password=minted["password"]
        ) as conn:
            verify_service_role(conn, lane="fulfilment")


def test_payments_tables_without_jobs_raise_naming_jobs() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema, with_jobs=False)
        _mint(s, "fulfilment")
        with pytest.raises(RuntimeError, match="jobs does not"):
            _grant(s, "fulfilment")
        assert not _can(s, f"has_table_privilege('{FULFIL}', 'purchases', 'INSERT')")


def test_no_schema_and_a_partial_schema_both_defer() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _owner_db(s)
        _mint(s, "fulfilment")
        assert _grant(s, "fulfilment") == "pending"  # no schema at all
        _in_db(s, f"SET ROLE {DB};\n{_grant_functions()}")
        assert _grant(s, "fulfilment") == "pending"  # the functions, no tables yet
    with scratch_pg() as s:
        _database(s, schema)
        _in_db(s, "DROP TABLE payments_audit_log CASCADE;")
        _mint(s, "fulfilment")
        assert _grant(s, "fulfilment") == "pending"  # five of the six tables


def test_a_pre_migration_install_raises_naming_the_migration() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema, functions=False)
        _mint(s, "fulfilment")
        with pytest.raises(RuntimeError, match="2026-09-29-scoped-service-roles.sql"):
            _grant(s, "fulfilment")


def test_a_changed_signature_raises_the_signature_error_not_the_migration_one() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema)
        _in_db(
            s,
            "DROP FUNCTION payments_grant_fulfilment(pg_catalog.regrole);\n"
            "CREATE FUNCTION payments_grant_fulfilment(r pg_catalog.regrole, x text DEFAULT '') "
            "RETURNS void LANGUAGE sql AS $$ SELECT $$;",
        )
        _mint(s, "fulfilment")
        with pytest.raises(
            RuntimeError, match="payments_grant_fulfilment\\(pg_catalog.regrole\\)"
        ) as e:
            _grant(s, "fulfilment")
        assert "2026-09-29-scoped-service-roles.sql" not in str(e.value)
        # spec item 3.2 precedes 3.3: a changed signature raises even on a partial schema
        _in_db(s, "DROP TABLE payments_audit_log CASCADE;")
        with pytest.raises(RuntimeError, match="the signature the hub calls"):
            _grant(s, "fulfilment")


def test_a_public_fulfilment_insert_policy_refuses() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema)
        _in_db(
            s,
            "CREATE POLICY payments_fulfilment_ins ON purchases AS PERMISSIVE FOR INSERT TO PUBLIC "
            "WITH CHECK (org_id = ( SELECT payments_current_org_id() ));",
        )
        _mint(s, "fulfilment")
        with pytest.raises(RuntimeError, match="applies to PUBLIC"):
            _grant(s, "fulfilment")


def test_a_legacy_ingest_install_migrated_grants_both_lanes_ingest_first() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema, functions=False)
        _mint(s, "ingest")
        assert _grant(s, "ingest") == "legacy"  # table-level SELECT, the pre-migration path
        _in_db(s, f"SET ROLE {DB};\n{_grant_functions()}")  # fabrik-lib's migration lands
        _mint(s, "fulfilment")
        # granted first, fulfilment's postcondition refuses the still-widened ingest role
        with pytest.raises(RuntimeError, match="reach the cross-tenant ingest policy"):
            _grant(s, "fulfilment")
        assert _grant(s, "ingest") == "module"  # narrows the ingest role to its columns
        assert _grant(s, "fulfilment") == "module"


def test_the_fulfilment_role_is_not_a_member_of_the_ingest_role() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema)
        _mint(s, "ingest")
        _mint(s, "fulfilment")
        assert _grant(s, "ingest") == "module"
        assert _grant(s, "fulfilment") == "module"
        assert not _can(s, f"pg_has_role('{FULFIL}', '{INGEST}', 'MEMBER')")
        assert not _can(s, f"pg_has_role('{INGEST}', '{FULFIL}', 'MEMBER')")


@pytest.mark.parametrize("lane", ["ingest", "fulfilment"])
def test_a_failing_grant_leaves_the_minted_password_with_the_caller(lane: str) -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema, with_jobs=False)
        # without PUBLIC's default CONNECT, only the grant batch's own CONNECT lets the login in
        s.run_sql(f"REVOKE CONNECT ON DATABASE {DB} FROM PUBLIC;")
        minted = _mint(s, lane)
        assert minted["password"]  # held BEFORE the grant runs
        with pytest.raises(RuntimeError, match="jobs does not"):
            _grant(s, lane)
        # the credential the caller holds still logs in
        assert s.login_sql(minted["user"], minted["password"], "SELECT 1;", db=DB) == "1"


@pytest.mark.parametrize("exists", [True, False], ids=["database-exists", "orphan-roles"])
def test_drop_database_drops_both_payments_roles(exists: bool) -> None:
    sqls: list[str] = []

    def _capture(sql: str, container: str = pg.POSTGRES_CONTAINER, dry_run: bool = False) -> str:
        sqls.append(sql)
        return "1" if exists and "SELECT 1 FROM pg_database" in sql else ""

    from unittest.mock import patch

    with (
        patch.object(pg, "_run_sql", side_effect=_capture),
        patch.object(pg, "unregister_allocation"),
        patch.object(pg, "unregister_postgres_plan"),
    ):
        pg.drop_database(DB)
    joined = "\n".join(sqls)
    assert f'DROP ROLE IF EXISTS "{INGEST}"' in joined
    assert f'DROP ROLE IF EXISTS "{FULFIL}"' in joined


def test_a_role_altered_out_of_band_is_narrowed_again_on_re_mint() -> None:
    """mint re-asserts every attribute on an existing role and resets its role-level settings."""
    with scratch_pg() as s:
        _owner_db(s)
        minted = _mint(s, "fulfilment")
        s.run_sql(
            f'ALTER ROLE "{FULFIL}" BYPASSRLS CREATEDB CREATEROLE REPLICATION NOINHERIT '
            "CONNECTION LIMIT 0 VALID UNTIL '2000-01-01';\n"
            f'ALTER ROLE "{FULFIL}" SET row_security = off;\n'
            f'ALTER ROLE "{FULFIL}" IN DATABASE {DB} SET row_security = off;\n'
            # a setting in ANOTHER database (a no-connection template) is reset too (W-3c302832)
            f'ALTER ROLE "{FULFIL}" IN DATABASE template0 SET row_security = off;'
        )
        again = _mint(s, "fulfilment")
        assert again["status"] == "exists" and again["password"] is None
        flags = s.run_sql(
            "SELECT rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolinherit, "
            f"rolconnlimit, rolvaliduntil = 'infinity' FROM pg_roles WHERE rolname = '{FULFIL}';"
        )
        assert flags == "f|f|f|f|t|-1|t", flags
        assert (
            s.run_sql(
                f"SELECT count(*) FROM pg_db_role_setting WHERE setrole = '{FULFIL}'::regrole;"
            )
            == "0"
        )
        # and the login the caller holds works again
        assert s.login_sql(FULFIL, minted["password"], "SELECT 1;") == "1"


def test_a_foreign_superuser_role_of_the_same_name_is_refused_not_altered() -> None:
    """A role the registrar never minted (a superuser, or a database owner) is never stripped."""
    with scratch_pg() as s:
        _owner_db(s)
        s.run_sql(f'CREATE ROLE "{FULFIL}" WITH LOGIN SUPERUSER;')
        with pytest.raises(RuntimeError, match=_RECOVERY):
            _mint(s, "fulfilment")
        assert _can(s, f"(SELECT rolsuper FROM pg_roles WHERE rolname = '{FULFIL}')")
        # the recovery the message names works: narrowed by hand, the re-apply succeeds
        s.run_sql(f'ALTER ROLE "{FULFIL}" NOSUPERUSER;')
        assert _mint(s, "fulfilment")["status"] == "exists"
    with scratch_pg() as s:
        _owner_db(s)
        s.run_sql(
            f'CREATE ROLE "{FULFIL}" WITH LOGIN CREATEDB;\nCREATE DATABASE other OWNER "{FULFIL}";'
        )
        # the shared foreign-role guard (W-f599a88c) refuses it before the mint's DO block
        with pytest.raises(RuntimeError, match="not this registrar.s.*owns database other"):
            _mint(s, "fulfilment")
        assert _can(s, f"(SELECT rolcreatedb FROM pg_roles WHERE rolname = '{FULFIL}')")
        s.run_sql("ALTER DATABASE other OWNER TO postgres;")
        assert _mint(s, "fulfilment")["status"] == "exists"
        assert not _can(s, f"(SELECT rolcreatedb FROM pg_roles WHERE rolname = '{FULFIL}')")
