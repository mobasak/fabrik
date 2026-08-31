"""An applicable registrar's failure must not exit green (finding 01M1CKEK).

tryton-crm deployed with `shape.needs_cache: true`, the redis registrar crashed,
`fabrik apply` printed `✅ Deployment complete` and exited 0 — the service ran
with no REDIS_URL and nothing linked the runtime failure back to the deploy.
Pins: (1) a failing registrar lands on ctx.registrar_failures while the other
registrars still run and nothing raises (no rollback); (2) the CLI refuses the
✅ banner and exits 2 when the list is non-empty, still 0 when it is empty.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.infrastructure import InfrastructureProvisioner
from fabrik.orchestrator.states import DeploymentState


def _ctx(spec: dict) -> DeploymentContext:
    c = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    c.spec = spec
    c.dry_run = False
    return c


def test_failed_redis_registrar_is_recorded_and_others_still_run():
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx(
        {
            "name": "cache-svc",
            "domain": "cache.example.com",
            "shape": {"kind": "service", "is_public": True, "needs_cache": True},
            "watchdog": {"enabled": False},
        }
    )
    ctx.coolify_uuid = "cache-svc"

    with (
        patch.object(prov, "_provision_shared_analytics"),
        patch(
            "fabrik.drivers.redis.acquire_db_index",
            side_effect=RuntimeError("invalid literal for int() with base 10: '2026-05-15T11:52:05+03:00'"),
        ),
        patch("fabrik.drivers.gatus.add_endpoint", return_value={"status": "created"}) as gatus,
        patch("fabrik.drivers.glitchtip.create_project", return_value={"status": "created", "dsn": "http://x@h/1"}),
        patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=True),
        patch("fabrik.drivers.grafana.post_deployment_annotation", return_value={"status": "created"}),
    ):
        prov.provision(ctx)  # must NOT raise — non-fatal contract preserved

    assert len(ctx.registrar_failures) == 1
    assert ctx.registrar_failures[0].startswith("redis: ")
    gatus.assert_called_once()  # failure did not short-circuit later registrars


def _provision_with_analytics_down(watchdog_enabled: bool) -> DeploymentContext:
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx(
        {
            "name": "plain-svc",
            "domain": "plain.example.com",
            "shape": {"kind": "service", "is_public": True},
            "watchdog": {"enabled": watchdog_enabled},
        }
    )
    ctx.coolify_uuid = "plain-svc"
    with (
        patch(
            "fabrik.drivers.postgres.ensure_shared_analytics_db",
            side_effect=RuntimeError("pg down"),
        ),
        patch.object(prov, "_provision_watchdog"),
        patch("fabrik.drivers.gatus.add_endpoint", return_value={"status": "created"}),
        patch("fabrik.drivers.glitchtip.create_project", return_value={"status": "created", "dsn": "http://x@h/1"}),
        patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=True),
        patch("fabrik.drivers.grafana.post_deployment_annotation", return_value={"status": "created"}),
    ):
        prov.provision(ctx)
    return ctx


def test_failed_shared_analytics_records_when_watchdog_applicable():
    # The watchdog's cost_ledger depends on it — that dependency is what
    # makes the platform step required (review pass 1 finding, scope
    # narrowed in pass 2).
    ctx = _provision_with_analytics_down(watchdog_enabled=True)
    assert ctx.registrar_failures == ["shared-analytics: pg down"]


def test_failed_shared_analytics_warns_only_without_watchdog():
    # A watchdog-disabled spec has no cost_ledger consumer — its deploy must
    # not exit 2 over a shared-analytics blip (review pass 2 finding).
    ctx = _provision_with_analytics_down(watchdog_enabled=False)
    assert ctx.registrar_failures == []


def test_all_green_records_no_failures():
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx(
        {
            "name": "plain-svc",
            "domain": "plain.example.com",
            "shape": {"kind": "service", "is_public": True},
            "watchdog": {"enabled": False},
        }
    )
    ctx.coolify_uuid = "plain-svc"

    with (
        patch.object(prov, "_provision_shared_analytics"),
        patch("fabrik.drivers.gatus.add_endpoint", return_value={"status": "created"}),
        patch("fabrik.drivers.glitchtip.create_project", return_value={"status": "created", "dsn": "http://x@h/1"}),
        patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=True),
        patch("fabrik.drivers.grafana.post_deployment_annotation", return_value={"status": "created"}),
    ):
        prov.provision(ctx)

    assert ctx.registrar_failures == []


def _completed_ctx(failures: list[str]) -> DeploymentContext:
    c = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    c.spec = {"name": "x", "domain": "x.example.com"}
    c.state = DeploymentState.COMPLETE
    c.deployed_url = "https://x.example.com"
    c.registrar_failures = failures
    return c


def _tmp_spec(tmp_path) -> str:
    # click.Path(exists=True) converts BEFORE the (mocked) orchestrator runs —
    # a real production spec path here couples these tests to fleet churn
    # (review finding); any existing file satisfies the conversion.
    spec = tmp_path / "spec.yaml"
    spec.write_text("id: x\n")
    return str(spec)


def _invoke_apply(ctx: DeploymentContext, tmp_path):
    from fabrik import cli as fabrik_cli

    orch = MagicMock()
    orch.deploy.return_value = ctx
    runner = CliRunner()
    with (
        patch.object(fabrik_cli, "DeploymentOrchestrator", return_value=orch),
        patch.object(fabrik_cli, "_emit_glitchtip_webhook_reminder"),
        patch.object(fabrik_cli, "_post_deploy_sync"),
    ):
        return runner.invoke(fabrik_cli.cli, ["apply", _tmp_spec(tmp_path)])


def test_cli_exits_2_and_names_the_failed_registrar(tmp_path):
    result = _invoke_apply(_completed_ctx(["redis: boom"]), tmp_path)
    assert result.exit_code == 2
    assert "registrar(s) FAILED" in result.output
    assert "redis: boom" in result.output
    assert "✅ Deployment complete" not in result.output


def test_cli_stays_green_without_failures(tmp_path):
    result = _invoke_apply(_completed_ctx([]), tmp_path)
    assert result.exit_code == 0
    assert "✅ Deployment complete" in result.output


def _invoke_refresh(ctx: DeploymentContext, tmp_path):
    from fabrik import cli as fabrik_cli

    orch = MagicMock()
    orch.refresh_infrastructure.return_value = ctx
    runner = CliRunner()
    with (
        patch("fabrik.orchestrator.DeploymentOrchestrator", return_value=orch),
        patch.object(fabrik_cli, "_post_deploy_sync"),
    ):
        return runner.invoke(
            fabrik_cli.cli,
            ["redeploy", "--refresh-infra", "--spec", _tmp_spec(tmp_path)],
        )


def test_refresh_infra_exits_2_on_failed_registrar(tmp_path):
    # The refresh path is exactly how failed registrars get RE-RUN — a green
    # banner here would re-swallow the very failure being retried (found by
    # the review of the apply-path fix; same contract, second exit).
    ctx = _completed_ctx(["redis: boom"])
    result = _invoke_refresh(ctx, tmp_path)
    assert result.exit_code == 2
    assert "redis: boom" in result.output
    assert "✅ Infrastructure refreshed" not in result.output


def test_refresh_infra_green_without_failures(tmp_path):
    result = _invoke_refresh(_completed_ctx([]), tmp_path)
    assert result.exit_code == 0
    assert "✅ Infrastructure refreshed" in result.output


def test_glitchtip_no_dsn_degraded_return_is_recorded():
    # The project exists but SENTRY_DSN is never injected — the registrar's
    # main promise broken under a green banner (review pass 2 finding).
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx(
        {
            "name": "svc",
            "domain": "svc.example.com",
            "shape": {"kind": "service", "is_public": True},
            "watchdog": {"enabled": False},
        }
    )
    ctx.coolify_uuid = "svc"
    with (
        patch.object(prov, "_provision_shared_analytics"),
        patch("fabrik.drivers.gatus.add_endpoint", return_value={"status": "created"}),
        patch("fabrik.drivers.glitchtip.create_project", return_value={"status": "created", "dsn": None}),
        patch("fabrik.drivers.grafana.post_deployment_annotation", return_value={"status": "created"}),
    ):
        prov.provision(ctx)
    assert any(f.startswith("glitchtip: ") and "no DSN" in f for f in ctx.registrar_failures)


def test_glitchtip_config_error_records_instead_of_rolling_back():
    # A momentarily unset GLITCHTIP_AUTH_TOKEN raised RuntimeError, which the
    # old bare `except RuntimeError: raise` escalated to a FULL deploy
    # rollback; only the verified DSN-absence (DsnInjectionError) is fatal
    # (review pass 2 finding).
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx(
        {
            "name": "svc",
            "domain": "svc.example.com",
            "shape": {"kind": "service", "is_public": True},
            "watchdog": {"enabled": False},
        }
    )
    ctx.coolify_uuid = "svc"
    with (
        patch.object(prov, "_provision_shared_analytics"),
        patch("fabrik.drivers.gatus.add_endpoint", return_value={"status": "created"}),
        patch(
            "fabrik.drivers.glitchtip.create_project",
            side_effect=RuntimeError("GLITCHTIP_AUTH_TOKEN not set"),
        ),
        patch("fabrik.drivers.grafana.post_deployment_annotation", return_value={"status": "created"}),
    ):
        prov.provision(ctx)  # must NOT raise
    assert any(f.startswith("glitchtip: ") for f in ctx.registrar_failures)


def test_postgres_watchdog_role_failure_is_recorded():
    # The watchdog sidecar boots with no DB creds if role minting fails while
    # _provision_watchdog still reports ok (review pass 2 finding).
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx(
        {
            "name": "db-svc",
            "domain": "db.example.com",
            "shape": {"kind": "service", "is_public": True, "needs_database": True},
            "watchdog": {"enabled": True},
        }
    )
    ctx.coolify_uuid = "db-svc"
    with (
        patch.object(prov, "_provision_shared_analytics"),
        patch.object(prov, "_provision_watchdog"),
        patch("fabrik.drivers.postgres.create_database", return_value={"status": "created", "database": "db_svc"}),
        patch(
            "fabrik.drivers.postgres.create_watchdog_roles",
            side_effect=RuntimeError("SQL error minting roles"),
        ),
        patch("fabrik.drivers.gatus.add_endpoint", return_value={"status": "created"}),
        patch("fabrik.drivers.glitchtip.create_project", return_value={"status": "created", "dsn": "http://x@h/1"}),
        patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=True),
        patch("fabrik.drivers.grafana.post_deployment_annotation", return_value={"status": "created"}),
    ):
        prov.provision(ctx)
    assert any(f.startswith("postgres/watchdog-roles: ") for f in ctx.registrar_failures)


def test_deploy_router_denies_success_on_registrar_failures():
    # The alternate entry point must agree with `fabrik apply` (review pass 2).
    from fabrik import deploy_router

    ctx = _completed_ctx(["redis: boom"])
    orch = MagicMock()
    orch.deploy.return_value = ctx
    with (
        patch.object(deploy_router, "DeploymentOrchestrator", return_value=orch),
        patch.object(deploy_router, "resolve_service_spec_path", return_value=Path("/tmp/x.yaml")),
        patch.object(deploy_router, "notify_deploy") as notify,
    ):
        rc = deploy_router._deploy_generic(Path("/tmp/proj"), dry_run=False)
    assert rc == 1
    assert notify.call_args.kwargs.get("success") is False or notify.call_args.args and False in notify.call_args.args
