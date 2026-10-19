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

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
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


def test_dead_spoke_target_fails_after_the_hub_answers():
    orch = _orchestrator(target_vps="vps2")
    answers = [
        MagicMock(returncode=0, stdout="", stderr=""),
        MagicMock(returncode=255, stdout="", stderr="ssh: connect to host vps2: No route to host"),
    ]
    with (
        patch("subprocess.run", side_effect=answers) as run,
        patch.object(orch, "_load_secrets") as secrets,
    ):
        ctx = orch.deploy(Path("/tmp/unused.yaml"))
    assert ctx.state == DeploymentState.FAILED
    assert ctx.error_step == "validation"
    assert "'vps2'" in ctx.error and "No route to host" in ctx.error
    assert "FABRIK_SSH_JUMP_VPS2=" in ctx.error
    assert run.call_count == 2
    secrets.assert_not_called()


def test_dry_run_still_refuses_a_malformed_jump(monkeypatch):
    monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "-oProxyCommand=x")
    orch = _orchestrator()
    with patch("subprocess.run") as run, patch.object(orch, "_load_secrets") as secrets:
        ctx = orch.deploy(Path("/tmp/unused.yaml"), dry_run=True)
    assert ctx.state == DeploymentState.FAILED
    assert ctx.error_step == "validation"
    assert "FABRIK_SSH_JUMP_VPS" in ctx.error
    run.assert_not_called()
    secrets.assert_not_called()


def test_dry_run_refuses_a_non_alias_host(monkeypatch):
    monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "-oProxyCommand=x")
    orch = _orchestrator()
    with patch("subprocess.run") as run:
        ctx = orch.deploy(Path("/tmp/unused.yaml"), dry_run=True)
    assert ctx.state == DeploymentState.FAILED
    assert "not an ssh alias" in ctx.error
    run.assert_not_called()


def test_dns_step_never_falls_back_to_cloudflare_on_a_malformed_jump():
    """`_provision_dns` falls back to Cloudflare on ANY DNS-manager error; a bad jump is config."""
    from fabrik.drivers.ssh import JumpConfigError
    from fabrik.orchestrator.context import DeploymentContext

    orch = _orchestrator()
    ctx = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    ctx.target_vps = "vps1"
    spec = {"id": "demo", "name": "demo", "domain": "demo.example.com"}
    with (
        patch(
            "fabrik.orchestrator.DNSClient.add_subdomain",
            side_effect=JumpConfigError("FABRIK_SSH_JUMP_VPS='-x' is not a ProxyJump value"),
        ),
        patch("fabrik.orchestrator.CloudflareClient") as cloudflare,
    ):
        with pytest.raises(JumpConfigError):
            orch._provision_dns(ctx, spec)
    cloudflare.assert_not_called()


def _dns_ctx():
    from fabrik.orchestrator.context import DeploymentContext

    ctx = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    ctx.target_vps = "vps1"
    return ctx


def _direct_status_error(status: int):
    request = httpx.Request("POST", "https://dns.example/api/cloudflare/dns/example.com/subdomain")
    try:  # httpx's own raise, so the error carries its real (two-line) text
        httpx.Response(status, request=request).raise_for_status()
    except httpx.HTTPStatusError as err:
        return err
    raise AssertionError(f"httpx did not raise on {status}")


_SPEC = {"id": "demo", "name": "demo", "domain": "demo.example.com"}


@pytest.mark.parametrize("status", [400, 401, 422, 429])
def test_dns_step_refuses_a_provisioner_refusal_without_cloudflare(status):
    """W-1086d295: a refusal the site-provisioner emits on its subdomain route (401 API key, 422 body,
    429 limiter; 400 the sibling route's zone mapping, requested for this one) is a gate — the record
    is never written straight to Cloudflare."""
    from fabrik.drivers.dns import ProvisionerHTTPError
    from fabrik.orchestrator.exceptions import ProvisioningError

    ctx = _dns_ctx()
    refusal = ProvisionerHTTPError(
        f"returned HTTP {status}: refused", status=status, body="refused"
    )
    with (
        patch("fabrik.orchestrator.DNSClient.add_subdomain", side_effect=refusal),
        patch("fabrik.orchestrator.CloudflareClient") as cloudflare,
    ):
        with pytest.raises(
            ProvisioningError, match=rf"^DNS Manager refused demo\.example\.com \(HTTP {status}\): "
        ):
            _orchestrator()._provision_dns(ctx, _SPEC)
    cloudflare.assert_not_called()
    assert ctx.created_resources == []  # rollback has nothing to delete through Cloudflare
    assert ctx.dns_record_id is None


def test_dns_step_refuses_a_direct_path_refusal_without_cloudflare():
    """The direct (public URL) transport raises httpx.HTTPStatusError — the same refusal rule."""
    from fabrik.orchestrator.exceptions import ProvisioningError

    ctx = _dns_ctx()
    with (
        patch("fabrik.orchestrator.DNSClient.add_subdomain", side_effect=_direct_status_error(401)),
        patch("fabrik.orchestrator.CloudflareClient") as cloudflare,
    ):
        with pytest.raises(
            ProvisioningError, match=r"^DNS Manager refused demo\.example\.com \(HTTP 401\): "
        ) as refused:
            _orchestrator()._provision_dns(ctx, _SPEC)
    cloudflare.assert_not_called()
    assert ctx.created_resources == []
    assert "\n" not in str(refused.value)  # httpx's two-line text is folded to one


@pytest.mark.parametrize("status", [0, 301, 403, 404, 500, 502])
def test_dns_step_falls_back_when_the_provisioner_did_not_refuse(status):
    """A status the provisioner app does not emit as a refusal still falls back: 403/404 are the
    reverse proxy (allowlist, no route mid-restart), 3xx a misroute, 5xx an outage, 0 a rebuilt error."""
    from fabrik.drivers.dns import ProvisionerHTTPError

    ctx = _dns_ctx()
    failure = ProvisionerHTTPError(f"returned HTTP {status}", status=status, body="")
    with (
        patch("fabrik.orchestrator.DNSClient.add_subdomain", side_effect=failure),
        patch("fabrik.orchestrator.CloudflareClient") as cloudflare,
    ):
        _orchestrator()._provision_dns(ctx, _SPEC)
    cloudflare.return_value.add_subdomain.assert_called_once_with(
        "example.com", "demo", "172.93.160.197"
    )
    assert ctx.dns_record_id == "demo.example.com"


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("SSH proxy request failed (rc=255)"),
        subprocess.TimeoutExpired(["ssh", "vps"], 30),
        httpx.ConnectError("connection refused"),
    ],
    ids=["ssh-rc", "timeout", "connect"],
)
def test_dns_step_falls_back_on_a_transport_failure(failure):
    """A failure that carries no HTTP status never reached the provisioner — the fallback stands."""
    ctx = _dns_ctx()
    with (
        patch("fabrik.orchestrator.DNSClient.add_subdomain", side_effect=failure),
        patch("fabrik.orchestrator.CloudflareClient") as cloudflare,
    ):
        _orchestrator()._provision_dns(ctx, _SPEC)
    cloudflare.return_value.add_subdomain.assert_called_once()
    assert ctx.dns_record_id == "demo.example.com"


def test_this_module_opts_in_to_the_real_preflight():
    """W-6a96f699 (review P1-17): LIVE_REACHABILITY_PREFLIGHT leaves the real function bound, so the
    tests above exercise it rather than the conftest stub."""
    import fabrik.orchestrator as orch
    from fabrik.drivers import preflight

    assert orch.verify_host_reachable is preflight.verify_host_reachable
