"""W-90784c3b — the payments-ingest grants against a REAL PostgreSQL 16 and fabrik-lib's schema.

fabrik-lib's ``payments_grant_ingest`` (its D-337) extends the ingest policies and grants only
the three columns ``resolve_org`` reads. The driver's legacy block DROP+CREATEs the policies
(stripping every other role) and grants table-level SELECT (re-widening the role to
``email``), so it must stand down wherever the function exists. The schema is read from the
box's fabrik-lib checkout; without it (or without docker) these rows skip, and
``FABRIK_REQUIRE_REAL_PG=1`` turns either skip into a failure.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import fabrik.drivers.postgres as pg
from tests.test_app_role_real_pg import ScratchPg, scratch_pg

_PAYMENTS_DB = Path(os.getenv("FABRIK_LIB_ROOT", "/opt/fabrik-lib")) / "payments" / "db"
_MIGRATION = _PAYMENTS_DB / "migrations" / "2026-09-29-scoped-service-roles.sql"
DB = "ti"
ROLE = "ti_payments_ingest"


def _schema() -> str:
    if not (_PAYMENTS_DB / "schema.sql").is_file() or not _MIGRATION.is_file():
        reason = f"fabrik-lib payments schema not found under {_PAYMENTS_DB}"
        if os.environ.get("FABRIK_REQUIRE_REAL_PG") == "1":
            pytest.fail(f"FABRIK_REQUIRE_REAL_PG=1 but {reason}")
        pytest.skip(reason)
    return (_PAYMENTS_DB / "schema.sql").read_text()


def _in_db(s: ScratchPg, sql: str) -> str:
    """Run ``sql`` as the superuser inside the app DB; return its last output line."""
    out = s.run_sql(f"\\set ON_ERROR_STOP on\n\\c {DB}\n{sql}")
    return out.splitlines()[-1] if out else ""


def _database(s: ScratchPg, schema: str, *, with_jobs: bool = True, with_fn: bool = True) -> None:
    """Owner ``ti`` owning the payments schema; a second role already on the ingest policy."""
    s.run_sql(
        "\\set ON_ERROR_STOP on\n"
        f"CREATE ROLE {DB} WITH LOGIN;\nCREATE DATABASE {DB} OWNER {DB};\n"
        "CREATE ROLE other_reader NOLOGIN;\n"
    )
    jobs = "CREATE TABLE jobs (id bigserial PRIMARY KEY, kind text);\n" if with_jobs else ""
    s.run_sql(f"\\set ON_ERROR_STOP on\n\\c {DB}\nSET ROLE {DB};\n{schema}\n{jobs}")
    if not with_fn:
        _in_db(s, "DROP FUNCTION payments_grant_ingest(pg_catalog.regrole);")
    _in_db(
        s,
        "CREATE POLICY payments_ingest_sel ON customers AS PERMISSIVE FOR SELECT "
        "TO other_reader USING (true);\n"
        "GRANT SELECT (org_id, provider, provider_customer_id) ON customers TO other_reader;",
    )


def _apply(s: ScratchPg) -> str:
    """Run the driver's batch in the scratch DB; return the grant path it reports."""
    with s.as_driver():
        return pg.create_payments_ingest_role(DB)["grants"]


def _policy_roles(s: ScratchPg, table: str) -> str:
    return _in_db(
        s,
        "SELECT array_to_string(polroles::regrole[], ',') FROM pg_policy "
        f"WHERE polname = 'payments_ingest_sel' AND polrelid = '{table}'::regclass;",
    )


def _can(s: ScratchPg, check: str) -> bool:
    return _in_db(s, f"SELECT {check};") == "t"


def test_function_path_extends_policies_and_grants_columns_only() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema)
        assert _apply(s) == "module"
        # the pre-existing role survives: the policy is extended, not dropped and recreated
        assert _policy_roles(s, "customers") == f"other_reader,{ROLE}"
        assert not _can(s, f"has_table_privilege('{ROLE}', 'customers', 'SELECT')")
        assert not _can(s, f"has_column_privilege('{ROLE}', 'customers', 'email', 'SELECT')")
        assert _can(
            s, f"has_column_privilege('{ROLE}', 'customers', 'provider_customer_id', 'SELECT')"
        )
        _apply(s)  # re-apply converges: same roles, still column-level only
        assert _policy_roles(s, "customers") == f"other_reader,{ROLE}"
        assert not _can(s, f"has_table_privilege('{ROLE}', 'subscriptions', 'SELECT')")


def test_payments_tables_without_jobs_fail_the_step_then_grant() -> None:
    """The function requires `jobs`: its absence is a loud failure, never a silently empty role."""
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema, with_jobs=False)
        with pytest.raises(RuntimeError, match="jobs does not"):
            _apply(s)
        # neither path granted: the legacy block stood down, the function never ran
        assert _policy_roles(s, "customers") == "other_reader"
        assert not _can(s, f"has_table_privilege('{ROLE}', 'customers', 'SELECT')")
        _in_db(s, f"SET ROLE {DB};\nCREATE TABLE jobs (id bigserial PRIMARY KEY, kind text);")
        assert _apply(s) == "module"
        assert _policy_roles(s, "customers") == f"other_reader,{ROLE}"


def test_no_payments_schema_yet_defers_without_failing() -> None:
    """The first apply, before the app's schema lands, grants nothing and reports `pending`."""
    _schema()
    with scratch_pg() as s:
        s.run_sql(
            f"\\set ON_ERROR_STOP on\nCREATE ROLE {DB} WITH LOGIN;\nCREATE DATABASE {DB} OWNER {DB};\n"
        )
        assert _apply(s) == "pending"


def test_a_refusal_from_the_function_fails_the_step() -> None:
    """A PUBLIC ingest policy makes payments_grant_ingest refuse; the batch must raise, not pass."""
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema)
        _in_db(s, "ALTER POLICY payments_ingest_sel ON customers TO PUBLIC;")
        with pytest.raises(RuntimeError, match="applies to PUBLIC"):
            _apply(s)
        assert not _can(s, f"has_table_privilege('{ROLE}', 'customers', 'SELECT')")


def test_install_without_the_function_keeps_the_legacy_block() -> None:
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema, with_fn=False)
        assert _apply(s) == "legacy"
        # the pre-migration fallback: policies to the ingest role, table-level SELECT
        assert _policy_roles(s, "customers") == ROLE
        assert _can(s, f"has_table_privilege('{ROLE}', 'customers', 'SELECT')")


def test_upgrade_from_a_legacy_grant_narrows_the_role() -> None:
    """A DB granted by the legacy block, then migrated: the next apply revokes the table grant."""
    schema = _schema()
    with scratch_pg() as s:
        _database(s, schema, with_fn=False)
        _apply(s)
        assert _can(s, f"has_column_privilege('{ROLE}', 'customers', 'email', 'SELECT')")
        s.run_sql(f"\\set ON_ERROR_STOP on\n\\c {DB}\nSET ROLE {DB};\n{_MIGRATION.read_text()}")
        assert _apply(s) == "module"
        assert not _can(s, f"has_column_privilege('{ROLE}', 'customers', 'email', 'SELECT')")
        assert not _can(s, f"has_table_privilege('{ROLE}', 'customers', 'SELECT')")
