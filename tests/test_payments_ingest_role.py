"""The payments registrar roles (mint_payments_role + grant_payments_role, both lanes).

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


def test_the_fulfilment_role_name_guard_refuses_at_its_own_boundary() -> None:
    """The fulfilment suffix is 4 characters longer than the ingest one, so its guard trips first."""
    longest_ok = "d" * (63 - len("_payments_fulfilment"))
    assert pg._payments_role_name(longest_ok, "fulfilment") == f"{longest_ok}_payments_fulfilment"
    with pytest.raises(ValueError, match="63-char"):
        pg._payments_role_name(longest_ok + "d", "fulfilment")
    assert pg._payments_role_name(longest_ok + "d", "ingest").endswith("_payments_ingest")
    with pytest.raises(ValueError, match="lane"):
        pg._payments_role_name("ti", "billing")


def test_the_shape_refuses_the_fulfilment_flag_without_a_database() -> None:
    from pydantic import ValidationError

    from fabrik.spec_loader import Shape

    assert Shape(needs_database=True, needs_payments_fulfilment=True).needs_payments_fulfilment
    with pytest.raises(ValidationError, match="needs_payments_fulfilment requires needs_database"):
        Shape(needs_payments_fulfilment=True)


def test_create_role_sql_is_non_bypassrls() -> None:
    """The security invariant: the CREATE ROLE must be NOBYPASSRLS and must NOT grant BYPASSRLS."""
    for lane in ("ingest", "fulfilment"):
        with (
            patch.object(pg, "_role_exists", return_value=False),
            patch.object(pg, "_run_sql") as run,
        ):
            pg.mint_payments_role("ti", lane)
        create_sql = run.call_args_list[0].args[0]
        assert "CREATE ROLE" in create_sql and "NOBYPASSRLS" in create_sql
        assert "NOSUPERUSER" in create_sql
        # never grant the bypass — a bare 'BYPASSRLS' without the NO prefix would be the bug
        assert " BYPASSRLS" not in create_sql.replace("NOBYPASSRLS", "")
        # the mint grants CONNECT and USAGE only, and never a membership
        mint_sql = run.call_args_list[1].args[0]
        assert 'GRANT CONNECT ON DATABASE "ti"' in mint_sql
        assert "GRANT USAGE ON SCHEMA public" in mint_sql
        assert " IN ROLE " not in create_sql and "GRANT ti_" not in mint_sql


def test_grant_batch_pins_the_three_tables_readwrite() -> None:
    with patch.object(pg, "_run_sql", return_value="module") as run:
        pg.grant_payments_role("ti", "ingest")
    grant_sql = run.call_args_list[0].args[0]  # the grant+policy batch
    # READ tables: SELECT + a permissive SELECT policy, guarded on existence
    for t in ("customers", "subscriptions"):
        assert f"to_regclass('public.{t}')" in grant_sql
        assert f"GRANT SELECT ON {t}" in grant_sql
        assert (
            f"CREATE POLICY payments_ingest_sel ON {t} FOR SELECT" in grant_sql
            and "USING (true)" in grant_sql
        )
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


def test_legacy_block_stands_down_when_the_module_grant_function_exists() -> None:
    """W-90784c3b: with fabrik-lib's payments_grant_ingest installed, the batch delegates to it."""
    with patch.object(pg, "_run_sql", return_value="module") as run:
        pg.grant_payments_role("ti", "ingest")
    grant_sql = run.call_args_list[0].args[0]
    fn = "to_regprocedure('payments_grant_ingest(pg_catalog.regrole)')"
    # every legacy DROP+CREATE block is gated on the function's ABSENCE
    legacy = [b for b in grant_sql.split("DO $$") if "DROP POLICY" in b]
    assert len(legacy) == 3 and all(f"{fn} IS NULL" in b for b in legacy)
    assert f"{fn} IS NOT NULL" in grant_sql
    assert (
        "PERFORM payments_grant_ingest('\"ti_payments_ingest\"'::pg_catalog.regrole)" in grant_sql
    )
    # and only once all seven tables the function requires resolve
    for t in (
        "plans",
        "customers",
        "subscriptions",
        "webhook_events",
        "purchases",
        "payments_audit_log",
        "jobs",
    ):
        assert f"to_regclass('{t}') IS NOT NULL" in grant_sql


def test_the_fulfilment_batch_delegates_to_the_module_and_has_no_fallback() -> None:
    with patch.object(pg, "_run_sql", return_value="module") as run:
        pg.grant_payments_role("ti", "fulfilment")
    grant_sql = run.call_args_list[0].args[0]
    assert (
        "PERFORM payments_grant_fulfilment('\"ti_payments_fulfilment\"'::pg_catalog.regrole)"
        in grant_sql
    )
    assert "to_regprocedure('payments_grant_fulfilment(pg_catalog.regrole)')" in grant_sql
    # delegate-only: the hub writes no grant or policy of its own for the fulfilment lane
    assert "GRANT " not in grant_sql.replace("payments_grant_fulfilment", "")
    assert "CREATE POLICY" not in grant_sql


@pytest.mark.parametrize(
    ("lane", "last_line", "expected"),
    [
        ("ingest", "module", "module"),
        ("ingest", "legacy", "legacy"),
        ("ingest", "pending", "pending"),
        ("fulfilment", "module", "module"),
        ("fulfilment", "pending", "pending"),
    ],
)
def test_the_reported_grant_path_is_the_batch_last_line(
    lane: str, last_line: str, expected: str
) -> None:
    """The batch's final SELECT names the path."""
    with patch.object(pg, "_run_sql", return_value=f"GRANT\nDO\n{last_line}\n"):
        assert pg.grant_payments_role("ti", lane)["grants"] == expected


@pytest.mark.parametrize(
    ("lane", "out"),
    [
        ("ingest", "GRANT\n"),
        ("ingest", ""),
        ("fulfilment", "GRANT\nlegacy\n"),  # legacy is no fulfilment path
        ("fulfilment", "DO\n"),
    ],
)
def test_an_unreadable_path_raises_never_guesses(lane: str, out: str) -> None:
    """Anything but a known path is `unknown`, and an unverified grant RAISES (spec item 4)."""
    with patch.object(pg, "_run_sql", return_value=out):
        with pytest.raises(RuntimeError, match="unreadable"):
            pg.grant_payments_role("ti", lane)


def test_fresh_password_only_on_create() -> None:
    with patch.object(pg, "_role_exists", return_value=False), patch.object(pg, "_run_sql"):
        assert pg.mint_payments_role("ti", "ingest")["password"] is not None
    with patch.object(pg, "_role_exists", return_value=True), patch.object(pg, "_run_sql") as run:
        res = pg.mint_payments_role("ti", "ingest")
    assert res["password"] is None and res["status"] == "exists"
    # re-apply still re-runs the idempotent CONNECT/USAGE grants, but skips CREATE ROLE
    assert not any("CREATE ROLE" in c.args[0] for c in run.call_args_list)


def test_dry_run_touches_nothing() -> None:
    with patch.object(pg, "_run_sql") as run:
        res = pg.mint_payments_role("ti", "ingest", dry_run=True)
        granted = pg.grant_payments_role("ti", "ingest", dry_run=True)
    assert res == {"user": "ti_payments_ingest", "password": None, "status": "dry_run"}
    assert granted == {"grants": "dry_run"}
    run.assert_not_called()


def test_drop_role_sql_and_invalid_name() -> None:
    assert pg._payments_drop_roles_sql("ti") == (
        'DROP ROLE IF EXISTS "ti_payments_ingest";\nDROP ROLE IF EXISTS "ti_payments_fulfilment";\n'
    )
    # too long for the fulfilment suffix but not the ingest one → only the ingest role drops
    ingest_only = "d" * (63 - len("_payments_fulfilment") + 1)
    assert pg._payments_drop_roles_sql(ingest_only) == (
        f'DROP ROLE IF EXISTS "{ingest_only}_payments_ingest";\n'
    )
    assert pg._payments_drop_roles_sql("x" * 60) == ""  # too long for both → nothing to drop


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
    assert (
        bad["payments_ingest"][0] is False and "needs_database=false" in bad["payments_ingest"][1]
    )


def _prov_with(pi_result, flag=True):
    prov = InfrastructureProvisioner(deployer=_mock.MagicMock())
    ctx = DeploymentContext(spec_path=Path("specs/services/x.yaml"))
    with (
        _mock.patch(
            "fabrik.drivers.postgres.create_database",
            side_effect=lambda db, *a, **k: {"status": "exists", "database": db},
        ),
        _mock.patch("fabrik.drivers.postgres.database_exists", side_effect=lambda *a, **k: False),
        _mock.patch(
            "fabrik.drivers.postgres.mint_payments_role",
            side_effect=lambda db, lane, dry_run=False, **k: pi_result(db),
        ) as m,
        _mock.patch(
            "fabrik.drivers.postgres.grant_payments_role",
            side_effect=lambda db, lane, dry_run=False, **k: {"grants": "module"},
        ),
    ):
        prov._provision_postgres("ti", {}, ctx, dry_run=False, provision_payments_ingest=flag)
    return prov, ctx, m


def test_provision_injects_dsn_and_records_resource_on_fresh_create() -> None:
    prov, ctx, m = _prov_with(
        lambda db: {"user": f"{db}_payments_ingest", "password": "PW", "status": "created"}
    )
    m.assert_called_once()
    injected = dict(kw for c in prov.deployer.inject_env.call_args_list for kw in c.args[1].items())
    assert "PAYMENTS_INGEST_DATABASE_URL" in injected
    assert injected["PAYMENTS_INGEST_DATABASE_URL"].startswith(
        "postgresql://ti_payments_ingest:PW@"
    )
    assert (
        ctx.get_resources_by_type("payments-ingest-role")[0].metadata.get("status") == "provisioned"
    )


def test_no_dsn_injected_when_role_already_exists() -> None:
    prov, ctx, m = _prov_with(
        lambda db: {"user": f"{db}_payments_ingest", "password": None, "status": "exists"}
    )
    m.assert_called_once()
    injected_keys = [k for c in prov.deployer.inject_env.call_args_list for k in c.args[1]]
    assert "PAYMENTS_INGEST_DATABASE_URL" not in injected_keys  # None password → no fresh DSN


def test_not_provisioned_when_flag_false() -> None:
    prov, _ctx, m = _prov_with(
        lambda db: {"user": "x", "password": "PW", "status": "created"}, flag=False
    )
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
