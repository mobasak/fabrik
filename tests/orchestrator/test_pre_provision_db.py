"""Behavior contract for `deploy.db_before_boot` — provision-before-deploy.

Init-at-boot images (e.g. Zitadel `start-from-init`) require the database reachable at the
container's FIRST boot, but fabrik's postgres registrar injects `DATABASE_URL` only AFTER
`deployer.deploy` (`orchestrator/__init__.py:163` deploy → `:173` registrar). Such a service
crashes on the empty DSN and the deploy rolls back before the registrar ever runs
(deploy-plan-review 2026-08-28 finding D1). `deploy.db_before_boot: true` makes the orchestrator
create the DB + seed `DATABASE_URL` into `ctx.secrets` BEFORE the first `up`, so `_build_env_content`
writes it into the initial `.env`. The post-deploy registrar's `create_database` is idempotent
(DB exists → no password → `.env` preserved), so this does not double-provision.

These tests pin: flag set + needs_database → DATABASE_URL seeded from the created role; flag absent
OR needs_database false → a strict no-op (every other service is byte-identical).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from fabrik.orchestrator import DeploymentOrchestrator
from fabrik.orchestrator.context import DeploymentContext


def _ctx(spec: dict) -> DeploymentContext:
    c = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    c.spec = spec
    c.dry_run = False
    return c


def _spec(**over: object) -> dict:
    s: dict = {
        "id": "zitadel",
        "name": "zitadel",
        "shape": {"needs_database": True},
        "depends": {"postgres": "zitadel"},
        "deploy": {"db_before_boot": True},
    }
    s.update(over)
    return s


def test_db_before_boot_seeds_database_url_into_secrets() -> None:
    orch = DeploymentOrchestrator()
    ctx = _ctx(_spec())
    with patch(
        "fabrik.drivers.postgres.create_database",
        return_value={"status": "created", "password": "SECRET123"},
    ) as pg:
        orch._pre_provision_db_for_boot(ctx, ctx.spec)
    pg.assert_called_once()
    # The DSN the initial .env must carry so start-from-init connects on first boot.
    assert (
        ctx.secrets.get("DATABASE_URL")
        == "postgresql://zitadel:SECRET123@postgres-main:5432/zitadel"
    )


def test_no_flag_is_a_strict_noop() -> None:
    orch = DeploymentOrchestrator()
    ctx = _ctx(_spec(deploy={}))
    with patch("fabrik.drivers.postgres.create_database") as pg:
        orch._pre_provision_db_for_boot(ctx, ctx.spec)
    pg.assert_not_called()
    assert "DATABASE_URL" not in ctx.secrets


def test_flag_without_needs_database_is_a_noop() -> None:
    orch = DeploymentOrchestrator()
    ctx = _ctx(_spec(shape={"needs_database": False}))
    with patch("fabrik.drivers.postgres.create_database") as pg:
        orch._pre_provision_db_for_boot(ctx, ctx.spec)
    pg.assert_not_called()
    assert "DATABASE_URL" not in ctx.secrets


def test_db_name_honors_depends_postgres_override() -> None:
    # depends.postgres pins the DB name (the registrar uses the same derivation), so the
    # pre-provisioned DSN targets the SAME DB the post-deploy registrar will see as existing.
    orch = DeploymentOrchestrator()
    ctx = _ctx(_spec(id="my-svc", name="my-svc", depends={"postgres": "custom_db"}))
    with patch(
        "fabrik.drivers.postgres.create_database",
        return_value={"status": "created", "password": "PW"},
    ) as pg:
        orch._pre_provision_db_for_boot(ctx, ctx.spec)
    assert pg.call_args.args[0] == "custom_db"
    assert ctx.secrets["DATABASE_URL"] == "postgresql://custom_db:PW@postgres-main:5432/custom_db"


def test_db_name_is_name_first_matching_the_registrar() -> None:
    # Finding #3: the pre-provision MUST use the registrar's precedence (name-first,
    # infrastructure.py:413 `spec.get("name") or spec.get("id")`). A service with
    # name != id and no depends.postgres would otherwise split-brain — pre-provision on
    # one DB, the post-deploy registrar on another. Assert the name wins.
    orch = DeploymentOrchestrator()
    ctx = _ctx(_spec(id="svc-id", name="svc_name", depends={}))
    with patch(
        "fabrik.drivers.postgres.create_database",
        return_value={"status": "created", "password": "PW"},
    ) as pg:
        orch._pre_provision_db_for_boot(ctx, ctx.spec)
    assert pg.call_args.args[0] == "svc_name", "db_name must derive from spec.name (registrar parity), not spec.id"
    assert ctx.secrets["DATABASE_URL"] == "postgresql://svc_name:PW@postgres-main:5432/svc_name"


def test_infra_postgres_false_override_skips_pre_provision() -> None:
    # Finding #1: the registrar gates postgres on `needs_database AND _enabled(infra,"postgres")`
    # (infrastructure.py:204). The pre-provision must honor the same `infra.postgres: false`
    # override ("I manage this DB myself"), else it creates a DB the operator opted out of.
    orch = DeploymentOrchestrator()
    ctx = _ctx(_spec(infra={"postgres": False}))
    with patch("fabrik.drivers.postgres.create_database") as pg:
        orch._pre_provision_db_for_boot(ctx, ctx.spec)
    pg.assert_not_called()
    assert "DATABASE_URL" not in ctx.secrets


def test_dry_run_does_not_seed_a_live_dsn() -> None:
    # Finding #2: the `if password and not ctx.dry_run` guard (else a `fabrik plan` preview
    # would seed a real DATABASE_URL). create_database is still called (existence check,
    # consistent with the registrar), but no DSN is layered into ctx.secrets.
    orch = DeploymentOrchestrator()
    ctx = _ctx(_spec())
    ctx.dry_run = True
    with patch(
        "fabrik.drivers.postgres.create_database",
        return_value={"status": "exists", "password": "PW"},
    ):
        orch._pre_provision_db_for_boot(ctx, ctx.spec)
    assert "DATABASE_URL" not in ctx.secrets, "dry-run must NOT seed a live DSN"


def test_create_database_failure_raises_provisioning_error() -> None:
    # Finding (author): create_database raises RuntimeError/ValueError (postgres.py:130),
    # which is NOT in deploy()'s caught tuple — so the pre-provision must re-raise it as
    # ProvisioningError for a clean abort + rollback instead of an uncaught traceback.
    from fabrik.orchestrator import ProvisioningError

    orch = DeploymentOrchestrator()
    ctx = _ctx(_spec())
    with patch(
        "fabrik.drivers.postgres.create_database",
        side_effect=RuntimeError("psql: could not connect to postgres-main"),
    ):
        try:
            orch._pre_provision_db_for_boot(ctx, ctx.spec)
        except ProvisioningError as e:
            assert "pre-provision failed" in str(e)
        else:  # pragma: no cover
            raise AssertionError("expected ProvisioningError on create_database failure")


def test_deploy_calls_pre_provision_before_deployer_deploy() -> None:
    # Finding #3: the whole point of the change is ORDERING — pre-provision must run before
    # deployer.deploy (the first `up`). Deleting/moving the call site passes every unit test
    # above, so pin the integration order here via a shared call-recorder.
    orch = DeploymentOrchestrator(
        validator=MagicMock(),
        deployer=MagicMock(),
        verifier=MagicMock(),
        rollback_manager=MagicMock(),
        infrastructure_provisioner=MagicMock(),
    )
    orch.validator.load_and_validate.return_value = (_spec(), "hash", [])
    order: list[str] = []
    orch.deployer.deploy.side_effect = lambda ctx: order.append("deploy")
    with (
        patch.object(orch, "_pre_provision_db_for_boot", side_effect=lambda ctx, spec: order.append("pre")),
        patch.object(orch, "_load_secrets"),
        patch.object(orch, "_provision_dns"),
        patch.object(orch, "_persist_state"),
    ):
        try:
            orch.deploy(Path("/tmp/x.yaml"))
        except Exception:  # noqa: BLE001 — downstream mocks may raise; we only assert order
            pass
    assert "pre" in order and "deploy" in order, f"both steps must run; got {order}"
    assert order.index("pre") < order.index("deploy"), f"pre-provision must precede deploy; got {order}"


def test_created_db_is_tracked_for_rollback() -> None:
    # Finding #4a: the pre-provisioned DB must be recorded so a failed-deploy rollback
    # WARNS about the orphan (postgres rollback is a manual-drop advisory), instead of
    # leaving a silently-created DB after a first-boot crash.
    orch = DeploymentOrchestrator()
    ctx = _ctx(_spec())
    with patch(
        "fabrik.drivers.postgres.create_database",
        return_value={"status": "created", "password": "PW"},
    ):
        orch._pre_provision_db_for_boot(ctx, ctx.spec)
    pg_resources = ctx.get_resources_by_type("postgres")
    assert any(r.resource_id == "zitadel" for r in pg_resources), "pre-provisioned DB not tracked in ctx.created_resources"
