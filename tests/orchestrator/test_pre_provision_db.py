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
from unittest.mock import patch

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
