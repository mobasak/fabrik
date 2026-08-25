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


# ── Phase C — resolve_applicability + _provision_postgres wiring ──
from pathlib import Path  # noqa: E402
from unittest import mock as _mock  # noqa: E402

from fabrik.orchestrator.infrastructure import (  # noqa: E402
    DeploymentContext,
    InfrastructureProvisioner,
    resolve_applicability,
)


def test_resolve_applicability_payments_ingest() -> None:
    on = resolve_applicability({"shape": {"needs_database": True, "needs_payments_ingest": True}})
    assert on["payments_ingest"][0] is True
    off = resolve_applicability({"shape": {"needs_database": True}})
    assert off["payments_ingest"][0] is False
    # set without a DB → not applicable (defensive; the Shape validator also blocks it)
    bad = resolve_applicability({"shape": {"needs_payments_ingest": True, "needs_database": False}})
    assert bad["payments_ingest"][0] is False and "needs_database=false" in bad["payments_ingest"][1]


def _prov_with(pi_result, flag=True):
    prov = InfrastructureProvisioner(deployer=_mock.MagicMock())
    ctx = DeploymentContext(spec_path=Path("specs/services/x.yaml"))
    with (
        _mock.patch("fabrik.drivers.postgres.create_database",
                    side_effect=lambda db, *a, **k: {"status": "exists", "database": db}),
        _mock.patch("fabrik.drivers.postgres.database_exists", side_effect=lambda *a, **k: False),
        _mock.patch("fabrik.drivers.postgres.create_payments_ingest_role",
                    side_effect=lambda db, dry_run=False, **k: pi_result(db)) as m,
    ):
        prov._provision_postgres("ti", {}, ctx, dry_run=False, provision_payments_ingest=flag)
    return prov, ctx, m


def test_provision_injects_dsn_and_records_resource_on_fresh_create() -> None:
    prov, ctx, m = _prov_with(lambda db: {"user": f"{db}_payments_ingest", "password": "PW", "status": "created"})
    m.assert_called_once()
    injected = dict(kw for c in prov.deployer.inject_env.call_args_list for kw in c.args[1].items())
    assert "PAYMENTS_INGEST_DATABASE_URL" in injected
    assert injected["PAYMENTS_INGEST_DATABASE_URL"].startswith("postgresql://ti_payments_ingest:PW@")
    assert ctx.get_resources_by_type("payments-ingest-role")[0].metadata.get("status") == "provisioned"


def test_no_dsn_injected_when_role_already_exists() -> None:
    prov, ctx, m = _prov_with(lambda db: {"user": f"{db}_payments_ingest", "password": None, "status": "exists"})
    m.assert_called_once()
    injected_keys = [k for c in prov.deployer.inject_env.call_args_list for k in c.args[1]]
    assert "PAYMENTS_INGEST_DATABASE_URL" not in injected_keys  # None password → no fresh DSN


def test_not_provisioned_when_flag_false() -> None:
    prov, _ctx, m = _prov_with(lambda db: {"user": "x", "password": "PW", "status": "created"}, flag=False)
    m.assert_not_called()


# ── Phase B/review: drop_database must not orphan the payments-ingest role ──
_PI_DB = "ti"
_PI_ROLE = "ti_payments_ingest"


def test_drop_database_also_drops_payments_ingest_role() -> None:
    """drop+recreate must not orphan the ingest role — else the next apply sees it
    existing, mints no fresh password, and .env is stuck without a working DSN."""
    calls: list[str] = []

    def fake_run_sql(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        return "1" if "pg_database" in sql else ""  # DB exists → proceed to drop

    with (
        patch.object(pg, "_run_sql", side_effect=fake_run_sql),
        patch.object(pg, "unregister_allocation"),
        patch.object(pg, "unregister_postgres_plan"),
    ):
        pg.drop_database(_PI_DB)
    drop_sql = next(c for c in calls if "DROP DATABASE" in c)
    assert f'DROP ROLE IF EXISTS "{_PI_ROLE}";' in drop_sql


def test_drop_database_cleans_orphan_payments_ingest_role_when_db_absent() -> None:
    calls: list[str] = []

    def fake_run_sql(sql, container=pg.POSTGRES_CONTAINER, dry_run=False):
        calls.append(sql)
        return ""  # DB does NOT exist

    with patch.object(pg, "_run_sql", side_effect=fake_run_sql):
        result = pg.drop_database(_PI_DB)
    assert result["status"] == "not_found"
    assert any(f'"{_PI_ROLE}"' in c for c in calls if "DROP ROLE IF EXISTS" in c)
