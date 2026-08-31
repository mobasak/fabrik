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


def test_failed_shared_analytics_is_recorded():
    # Unconditional platform step — the watchdog's cost_ledger depends on it;
    # it was the one swallow the first rewire left invisible (review pass 1,
    # finder 3's dying finding).
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
        patch(
            "fabrik.drivers.postgres.ensure_shared_analytics_db",
            side_effect=RuntimeError("pg down"),
        ),
        patch("fabrik.drivers.gatus.add_endpoint", return_value={"status": "created"}),
        patch("fabrik.drivers.glitchtip.create_project", return_value={"status": "created", "dsn": "http://x@h/1"}),
        patch("fabrik.drivers.glitchtip.verify_dsn_injection", return_value=True),
        patch("fabrik.drivers.grafana.post_deployment_annotation", return_value={"status": "created"}),
    ):
        prov.provision(ctx)

    assert ctx.registrar_failures == ["shared-analytics: pg down"]


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


def _invoke_apply(ctx: DeploymentContext):
    from fabrik import cli as fabrik_cli

    orch = MagicMock()
    orch.deploy.return_value = ctx
    runner = CliRunner()
    with (
        patch.object(fabrik_cli, "DeploymentOrchestrator", return_value=orch),
        patch.object(fabrik_cli, "_emit_glitchtip_webhook_reminder"),
        patch.object(fabrik_cli, "_post_deploy_sync"),
    ):
        return runner.invoke(fabrik_cli.cli, ["apply", "specs/services/tryton-crm.yaml"])


def test_cli_exits_2_and_names_the_failed_registrar():
    result = _invoke_apply(_completed_ctx(["redis: boom"]))
    assert result.exit_code == 2
    assert "registrar(s) FAILED" in result.output
    assert "redis: boom" in result.output
    assert "✅ Deployment complete" not in result.output


def test_cli_stays_green_without_failures():
    result = _invoke_apply(_completed_ctx([]))
    assert result.exit_code == 0
    assert "✅ Deployment complete" in result.output


def _invoke_refresh(ctx: DeploymentContext):
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
            ["redeploy", "--refresh-infra", "--spec", "specs/services/tryton-crm.yaml"],
        )


def test_refresh_infra_exits_2_on_failed_registrar():
    # The refresh path is exactly how failed registrars get RE-RUN — a green
    # banner here would re-swallow the very failure being retried (found by
    # the review of the apply-path fix; same contract, second exit).
    ctx = _completed_ctx(["redis: boom"])
    result = _invoke_refresh(ctx)
    assert result.exit_code == 2
    assert "redis: boom" in result.output
    assert "✅ Infrastructure refreshed" not in result.output


def test_refresh_infra_green_without_failures():
    result = _invoke_refresh(_completed_ctx([]))
    assert result.exit_code == 0
    assert "✅ Infrastructure refreshed" in result.output
