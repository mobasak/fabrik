"""Phase B — the payments-ingest registrar role (create_payments_ingest_role).

Mock-`_run_sql` unit tests (the repo's driver-test pattern) over the generated SQL +
control flow. The RLS *behavior* invariant (a non-BYPASSRLS role with these policies
reads/writes cross-tenant under FORCE RLS, and CANNOT reach a non-payments table) is
proven separately against a live PG — see the plan's Phase-B live proof.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

import fabrik.drivers.postgres as pg


def test_role_name_and_63_char_guard() -> None:
    assert pg._payments_ingest_role_name("ti") == "ti_payments_ingest"
    with pytest.raises(ValueError, match="63-char"):
        pg._payments_ingest_role_name("x" * 60)  # 60 + len('_payments_ingest')=16 > 63


def test_create_role_sql_is_non_bypassrls() -> None:
    """The security invariant: the CREATE ROLE must be NOBYPASSRLS and must NOT grant BYPASSRLS."""
    with patch.object(pg, "_role_exists", return_value=False), patch.object(pg, "_run_sql") as run:
        pg.create_payments_ingest_role("ti")
    create_sql = run.call_args_list[0].args[0]
    assert "CREATE ROLE" in create_sql and "NOBYPASSRLS" in create_sql
    assert "NOSUPERUSER" in create_sql
    # never grant the bypass — a bare 'BYPASSRLS' without the NO prefix would be the bug
    assert " BYPASSRLS" not in create_sql.replace("NOBYPASSRLS", "")


def test_grant_batch_pins_the_three_tables_readwrite() -> None:
    with patch.object(pg, "_role_exists", return_value=False), patch.object(pg, "_run_sql") as run:
        pg.create_payments_ingest_role("ti")
    grant_sql = run.call_args_list[1].args[0]  # 2nd call = the grant+policy batch
    # READ tables: SELECT + a permissive SELECT policy, guarded on existence
    for t in ("customers", "subscriptions"):
        assert f"to_regclass('public.{t}')" in grant_sql
        assert f"GRANT SELECT ON {t}" in grant_sql
        assert f"CREATE POLICY payments_ingest_sel ON {t} FOR SELECT" in grant_sql and "USING (true)" in grant_sql
    # WRITE table: INSERT+SELECT + BOTH policies (SELECT for RETURNING, INSERT WITH CHECK)
    assert "GRANT INSERT, SELECT ON webhook_events" in grant_sql
    assert "CREATE POLICY payments_ingest_sel ON webhook_events FOR SELECT" in grant_sql
    assert "CREATE POLICY payments_ingest_ins ON webhook_events FOR INSERT" in grant_sql
    assert "WITH CHECK (true)" in grant_sql
    # least privilege: never UPDATE/DELETE, never `plans`, never the project's `jobs` queue
    assert "UPDATE" not in grant_sql and "DELETE" not in grant_sql
    assert " plans " not in grant_sql and "ON jobs" not in grant_sql
    # idempotent
    assert "DROP POLICY IF EXISTS payments_ingest_sel ON webhook_events" in grant_sql


def test_fresh_password_only_on_create() -> None:
    with patch.object(pg, "_role_exists", return_value=False), patch.object(pg, "_run_sql"):
        assert pg.create_payments_ingest_role("ti")["password"] is not None
    with patch.object(pg, "_role_exists", return_value=True), patch.object(pg, "_run_sql") as run:
        res = pg.create_payments_ingest_role("ti")
    assert res["password"] is None and res["status"] == "exists"
    # re-apply still re-runs the idempotent grant batch, but skips CREATE ROLE
    assert not any("CREATE ROLE" in c.args[0] for c in run.call_args_list)


def test_dry_run_touches_nothing() -> None:
    with patch.object(pg, "_run_sql") as run:
        res = pg.create_payments_ingest_role("ti", dry_run=True)
    assert res == {"user": "ti_payments_ingest", "password": None, "status": "dry_run"}
    run.assert_not_called()


def test_drop_role_sql_and_invalid_name() -> None:
    assert pg._payments_ingest_drop_role_sql("ti") == 'DROP ROLE IF EXISTS "ti_payments_ingest";\n'
    assert pg._payments_ingest_drop_role_sql("x" * 60) == ""  # too long → nothing to drop
