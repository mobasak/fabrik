"""`fabrik apply` probes the ssh path before anything else touches the fleet (W-2b657bee).

A dead path used to surface as a 60-120 s hang per call and an error that never said which
path was dead. `DeploymentOrchestrator.deploy` now calls `verify_host_reachable` for the hub
alias (and the target alias for a spoke) right after validation, so a dead path ends the run
FAILED in validation, naming it, before secrets, DNS or any registrar runs. A dry run probes
nothing.

This module opts out of the conftest no-op pin (`LIVE_REACHABILITY_PREFLIGHT`) and patches
`subprocess.run` itself, so the real `verify_host_reachable` runs against a fake ssh.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator import DeploymentOrchestrator
from fabrik.orchestrator.states import DeploymentState

LIVE_REACHABILITY_PREFLIGHT = True


def _orchestrator(target_vps: str = "vps1") -> DeploymentOrchestrator:
    validator = MagicMock()
    validator.load_and_validate.return_value = (
        {"id": "demo", "name": "demo", "domain": "demo.example.com", "target_vps": target_vps},
        "hash",
        [],
    )
    # every later component stubbed, so a regression that skips the probe fails fast
    return DeploymentOrchestrator(
        validator=validator,
        secrets_manager=MagicMock(),
        deployer=MagicMock(),
        verifier=MagicMock(),
        rollback_manager=MagicMock(),
        infrastructure_provisioner=MagicMock(),
    )


@pytest.fixture(autouse=True)
def _hub_alias(monkeypatch):
    monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS2", raising=False)


def test_dead_path_fails_in_validation_naming_it_before_any_later_step():
    orch = _orchestrator()
    dead = MagicMock(
        returncode=255, stdout="", stderr="Connection timed out during banner exchange"
    )
    with (
        patch("subprocess.run", return_value=dead) as run,
        patch.object(orch, "_load_secrets") as secrets,
        patch.object(orch, "_provision_dns") as dns,
    ):
        ctx = orch.deploy(Path("/tmp/unused.yaml"))
    assert ctx.state == DeploymentState.FAILED
    assert ctx.error_step == "validation"
    assert "'vps'" in ctx.error and "banner exchange" in ctx.error
    assert "FABRIK_SSH_JUMP_VPS=" in ctx.error
    secrets.assert_not_called()
    dns.assert_not_called()
    orch.deployer.deploy.assert_not_called()
    assert run.call_count == 1


def test_invalid_jump_value_fails_in_validation_not_as_an_unexpected_error(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "-oProxyCommand=x")
    orch = _orchestrator()
    with patch("subprocess.run") as run, patch.object(orch, "_load_secrets") as secrets:
        ctx = orch.deploy(Path("/tmp/unused.yaml"))
    assert ctx.state == DeploymentState.FAILED
    assert ctx.error_step == "validation"
    assert "FABRIK_SSH_JUMP_VPS" in ctx.error
    run.assert_not_called()
    secrets.assert_not_called()


def test_spoke_target_probes_hub_and_target_aliases():
    orch = _orchestrator(target_vps="vps2")
    ok = MagicMock(returncode=0, stdout="", stderr="")
    with (
        patch("subprocess.run", return_value=ok) as run,
        patch.object(orch, "_load_secrets", side_effect=RuntimeError("stop here")),
    ):
        orch.deploy(Path("/tmp/unused.yaml"))
    probed = [call[0][0][-2] for call in run.call_args_list]
    assert probed == ["vps", "vps2"]


def test_dry_run_probes_nothing():
    orch = _orchestrator()
    with (
        patch("subprocess.run") as run,
        patch.object(orch, "_load_secrets", side_effect=RuntimeError("stop here")),
    ):
        orch.deploy(Path("/tmp/unused.yaml"), dry_run=True)
    run.assert_not_called()
