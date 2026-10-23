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
