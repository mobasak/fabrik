"""A spoke-targeted watchdog is refused, not shipped blind (W-37dda1e1).

On a spoke the sidecar cannot reach vps1's apprise (no mesh port; the Traefik route is 2FA-gated), and no legal
spec can point it elsewhere (WatchdogConfig has no apprise_url). The registrar records the refusal non-fatally on
real AND dry runs, never calls the driver, and leaves vps1 unchanged.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.infrastructure import InfrastructureProvisioner


def _ctx(target_vps: str | None, *, dry_run: bool) -> DeploymentContext:
    c = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    c.spec = {"id": "spoke-app", "watchdog": {"enabled": True}}
    c.dry_run = dry_run
    c.target_vps = target_vps
    c.app_name = "spoke-app"
    return c


@pytest.mark.parametrize("dry_run", [False, True])
def test_a_spoke_watchdog_is_refused_and_the_driver_never_runs(dry_run):
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx("vps2", dry_run=dry_run)
    with patch("fabrik.drivers.watchdog.WatchdogDriver.provision") as provision:
        prov._provision_watchdog("spoke-app", ctx, dry_run=dry_run)
    provision.assert_not_called()
    failures = [f for f in ctx.registrar_failures if f.startswith("watchdog:")]
    assert len(failures) == 1, ctx.registrar_failures
    assert (
        "vps2" in failures[0]
        and "apprise" in failures[0]
        and "watchdog.enabled: false" in failures[0]
    )
    assert not ctx.get_resources_by_type("watchdog")


@pytest.mark.parametrize("target", ["vps1", None])
def test_a_vps1_watchdog_is_unchanged(target):
    prov = InfrastructureProvisioner(deployer=MagicMock())
    dry = _ctx(target, dry_run=True)
    prov._provision_watchdog("spoke-app", dry, dry_run=True)
    assert [r.metadata.get("status") for r in dry.get_resources_by_type("watchdog")] == ["dry-run"]
    real = _ctx(target, dry_run=False)
    with patch(
        "fabrik.drivers.watchdog.WatchdogDriver.provision", return_value={"status": "ok"}
    ) as provision:
        prov._provision_watchdog("spoke-app", real, dry_run=False)
    provision.assert_called_once()
    assert not real.registrar_failures


def test_a_spoke_named_only_in_the_spec_is_refused_too():
    """The driver resolves ctx.target_vps, else the spec's; the registrar resolves the same way."""
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx(None, dry_run=False)
    ctx.spec = {**ctx.spec, "target_vps": "vps2"}
    with patch("fabrik.drivers.watchdog.WatchdogDriver.provision") as provision:
        prov._provision_watchdog("spoke-app", ctx, dry_run=False)
    provision.assert_not_called()
    assert any(f.startswith("watchdog:") and "vps2" in f for f in ctx.registrar_failures)


def test_the_spoke_refusal_never_imports_the_driver(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "fabrik.drivers.watchdog", None)
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx("vps2", dry_run=False)
    prov._provision_watchdog("spoke-app", ctx, dry_run=False)
    assert any(f.startswith("watchdog:") and "W-5dcafaef" in f for f in ctx.registrar_failures)


@pytest.mark.parametrize("target, lives", [("vps2", False), ("vps1", True)])
def test_provision_withholds_the_watchdog_roles_and_analytics_failure_on_a_spoke(target, lives):
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx(target, dry_run=False)
    ctx.spec = {
        **ctx.spec,
        "name": "spoke-app",
        "shape": {"needs_database": True},
        "target_vps": target,
    }
    with (
        patch.object(prov, "_provision_shared_analytics") as analytics,
        patch.object(prov, "_provision_postgres") as postgres,
        patch.object(prov, "_provision_watchdog"),
        patch("fabrik.drivers.grafana.post_deployment_annotation", return_value={}),
    ):
        prov.provision(ctx)
    assert analytics.call_args.kwargs["record_failure"] is lives
    assert postgres.call_args.kwargs["provision_watchdog_roles"] is lives


def test_plan_names_the_spoke_refusal():
    from fabrik.orchestrator.infrastructure import resolve_applicability

    spoke = resolve_applicability({"id": "x", "target_vps": "vps2", "watchdog": {"enabled": True}})[
        "watchdog"
    ]
    hub = resolve_applicability({"id": "x", "watchdog": {"enabled": True}})["watchdog"]
    assert "refused on spoke vps2" in spoke[1] and "D-1153" in spoke[1]
    assert "refused" not in hub[1]
