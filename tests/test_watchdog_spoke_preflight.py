"""A watchdog alerts from any host and is provisioned only after its login preflight passes (W-5dcafaef).

A spoke sidecar posts to vps1's Apprise through the mesh-only gate (`10.99.0.1:8202`, D-1166), so the D-1153
spoke refusal is lifted. Before the driver runs, one ssh call checks the Claude login files the sidecar mounts
(and, on a spoke, that the gate answers); any failure is recorded non-fatally, names the target and the ssh
alias it hit, and the driver never runs.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.infrastructure import InfrastructureProvisioner

HOME = "/home/ozgur/.claude"
CFG = f"{HOME}.json"
CREDS = f"{HOME}/.credentials.json"
OK = f"present {CFG}\npresent {CREDS}"
OK_SPOKE = OK + "\ngate reachable"


@pytest.fixture(autouse=True)
def _claude_home(monkeypatch):
    monkeypatch.setattr("fabrik.drivers.watchdog.VPS_CLAUDE_HOME", HOME)
    monkeypatch.delenv("FABRIK_VPS_SSH_HOST", raising=False)


def _ctx(
    target_vps: str | None, *, dry_run: bool, watchdog: dict | None = None
) -> DeploymentContext:
    c = DeploymentContext(spec_path=Path("/tmp/unused.yaml"))
    c.spec = {"id": "spoke-app", "watchdog": {"enabled": True, **(watchdog or {})}}
    c.dry_run = dry_run
    c.target_vps = target_vps
    c.app_name = "spoke-app"
    return c


def _wd_failures(ctx):
    return [f for f in ctx.registrar_failures if f.startswith("watchdog:")]


def _run(ctx, *, stdout=None, raises=None):
    """Run the real (non-dry) registrar with ssh stubbed; return (driver mock, ssh mock, hosts ssh saw)."""
    hosts: list[str | None] = []

    def fake_ssh(cmd, timeout=30, **_):
        hosts.append(os.environ.get("FABRIK_VPS_SSH_HOST"))
        if raises is not None:
            raise raises
        return stdout

    prov = InfrastructureProvisioner(deployer=MagicMock())
    with (
        patch("fabrik.drivers.ssh.ssh", side_effect=fake_ssh) as ssh,
        patch(
            "fabrik.drivers.watchdog.WatchdogDriver.provision", return_value={"status": "ok"}
        ) as provision,
    ):
        prov._provision_watchdog("spoke-app", ctx, dry_run=False)
    return provision, ssh, hosts


def test_a_spoke_watchdog_runs_the_driver_after_a_passing_preflight():
    ctx = _ctx("vps2", dry_run=False)
    provision, ssh, hosts = _run(ctx, stdout=OK_SPOKE)
    provision.assert_called_once()
    assert not ctx.registrar_failures
    assert hosts == ["vps2"]
    cmd = ssh.call_args.args[0]
    assert "sudo -n" in cmd and CFG in cmd and CREDS in cmd and "/dev/tcp/10.99.0.1/8202" in cmd


@pytest.mark.parametrize("target", ["vps1", None])
def test_a_vps1_watchdog_checks_the_login_files_but_no_gate(target):
    prov = InfrastructureProvisioner(deployer=MagicMock())
    dry = _ctx(target, dry_run=True)
    prov._provision_watchdog("spoke-app", dry, dry_run=True)
    assert [r.metadata.get("status") for r in dry.get_resources_by_type("watchdog")] == ["dry-run"]
    real = _ctx(target, dry_run=False)
    provision, ssh, hosts = _run(real, stdout=OK)
    provision.assert_called_once()
    assert not real.registrar_failures
    assert hosts == [None]
    assert "/dev/tcp/" not in ssh.call_args.args[0]


def test_a_spoke_named_only_in_the_spec_is_probed_on_that_spoke():
    ctx = _ctx(None, dry_run=False)
    ctx.spec = {**ctx.spec, "target_vps": "vps2"}
    provision, _, hosts = _run(ctx, stdout=OK_SPOKE)
    provision.assert_called_once()
    assert hosts == ["vps2"]


@pytest.mark.parametrize(
    "target, stdout, expect",
    [
        ("vps1", f"present {CFG}\nmissing {CREDS}", [f"missing {CREDS}"]),
        ("vps1", f"missing {CFG}\nmissing {CREDS}", [f"missing {CFG}", f"missing {CREDS}"]),
        ("vps2", OK + "\ngate unreachable", ["gate unreachable from vps2"]),
        (
            "vps2",
            f"missing {CFG}\npresent {CREDS}\ngate unreachable",
            [f"missing {CFG}", "gate unreachable from vps2"],
        ),
        ("vps1", "", ["could not check vps1", "unexpected output"]),
        ("vps1", OK + "\nWelcome!", ["could not check vps1", "unexpected output"]),
        ("vps1", f"present {CFG}", ["could not check vps1", "unexpected output"]),
        ("vps1", f"present {CFG}\npresent /etc/x", ["could not check vps1", "unexpected output"]),
        (
            "vps1",
            f"present {CFG}\nmissing {CFG}\npresent {CREDS}",
            ["could not check vps1", "unexpected output"],
        ),
        ("vps1", OK + "\ngate unreachable", ["could not check vps1", "unexpected output"]),
        ("vps2", OK, ["could not check vps2", "unexpected output"]),
        (
            "vps2",
            OK + "\ngate reachable\ngate unreachable",
            ["could not check vps2", "unexpected output"],
        ),
        (
            "vps1",
            f"present {CFG}\npresent {CFG}\npresent {CREDS}",
            ["could not check vps1", "unexpected output"],
        ),
        ("vps2", OK_SPOKE + "\ngate reachable", ["could not check vps2", "unexpected output"]),
    ],
)
def test_a_failed_preflight_records_one_failure_and_skips_the_driver(target, stdout, expect):
    ctx = _ctx(target, dry_run=False)
    provision, _, _ = _run(ctx, stdout=stdout)
    provision.assert_not_called()
    failures = _wd_failures(ctx)
    assert len(failures) == 1, ctx.registrar_failures
    alias = "vps" if target == "vps1" else target
    assert target in failures[0] and f"({alias})" in failures[0]
    for part in expect:
        assert part in failures[0], failures[0]
    assert not ctx.get_resources_by_type("watchdog")


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("ssh vps2 exited 1: sudo: a password is required"),
        subprocess.TimeoutExpired(cmd="ssh", timeout=30),
        __import__("fabrik.drivers.ssh", fromlist=["JumpConfigError"]).JumpConfigError("bad jump"),
    ],
)
def test_an_ssh_error_reads_could_not_check_never_missing(exc):
    ctx = _ctx("vps2", dry_run=False)
    provision, _, _ = _run(ctx, raises=exc)
    provision.assert_not_called()
    failures = _wd_failures(ctx)
    assert len(failures) == 1 and "could not check vps2 (vps2)" in failures[0]
    assert "missing" not in failures[0]


def test_a_missing_driver_module_is_skipped_before_any_preflight(monkeypatch):
    """The driver module failing to import keeps its graceful skip; the preflight never imports it first."""
    import sys

    monkeypatch.setitem(sys.modules, "fabrik.drivers.watchdog", None)
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx("vps2", dry_run=False)
    with patch("fabrik.drivers.ssh.ssh") as ssh:
        prov._provision_watchdog("spoke-app", ctx, dry_run=False)
    ssh.assert_not_called()
    assert not ctx.get_resources_by_type("watchdog")


def test_an_openrouter_only_watchdog_makes_no_ssh_call():
    ctx = _ctx(
        "vps2",
        dry_run=False,
        watchdog={"llm_provider_primary": "openrouter", "llm_provider_fallback": "openrouter"},
    )
    provision, ssh, _ = _run(ctx, stdout="")
    ssh.assert_not_called()
    provision.assert_called_once()
    assert not ctx.registrar_failures


@pytest.mark.parametrize(
    "watchdog",
    [
        {},
        {"llm_provider_primary": "claude-code", "llm_provider_fallback": "openrouter"},
        {"llm_provider_primary": "openrouter", "llm_provider_fallback": "claude-code"},
    ],
)
def test_either_claude_code_lane_runs_the_preflight(watchdog):
    ctx = _ctx("vps2", dry_run=False, watchdog=watchdog)
    provision, ssh, _ = _run(ctx, stdout=OK_SPOKE)
    ssh.assert_called_once()
    provision.assert_called_once()


@pytest.mark.parametrize("dry_run", [True, False])
def test_a_non_mapping_watchdog_block_never_escapes_the_registrar(dry_run):
    """A raw spec whose ``watchdog:`` is not a mapping is checked with the provider defaults, never raised."""
    ctx = _ctx("vps2", dry_run=dry_run)
    ctx.spec = {**ctx.spec, "watchdog": "on"}
    if dry_run:
        with patch("fabrik.drivers.ssh.ssh") as ssh:
            InfrastructureProvisioner(deployer=MagicMock())._provision_watchdog(
                "spoke-app", ctx, dry_run=True
            )
        ssh.assert_not_called()
    else:
        _, ssh, _ = _run(ctx, stdout=OK_SPOKE)
        ssh.assert_called_once()


@pytest.mark.parametrize("target", ["vps1", "vps2"])
def test_the_preflight_command_runs_under_sh_and_its_output_parses(target, tmp_path, monkeypatch):
    """The generated shell (``sudo -n`` stripped) runs, quotes a path with a space, and its real output parses."""
    home = tmp_path / "claude home"
    home.mkdir()
    (tmp_path / "claude home.json").write_text("{}")
    monkeypatch.setattr("fabrik.drivers.watchdog.VPS_CLAUDE_HOME", str(home))
    _, ssh, _ = _run(_ctx(target, dry_run=False), stdout="")
    cmd = ssh.call_args.args[0]
    assert cmd.startswith("sudo -n ")
    # The gate host is the hub's mesh IP; a closed local port keeps the run deterministic off the mesh.
    local = cmd[len("sudo -n ") :].replace("/dev/tcp/10.99.0.1/8202", "/dev/tcp/0.0.0.0/1")
    out = subprocess.run(["sh", "-c", local], capture_output=True, text=True, timeout=30).stdout
    ctx = _ctx(target, dry_run=False)
    provision, _, _ = _run(ctx, stdout=out)
    provision.assert_not_called()
    failure = _wd_failures(ctx)[0]
    assert f"missing {home}/.credentials.json" in failure and "unexpected output" not in failure
    # the present file, its path holding a space, reads present
    assert f"missing {home}.json" not in failure
    assert ("gate unreachable from vps2" in failure) is (target == "vps2")


@pytest.mark.parametrize(
    "watchdog, logs_check",
    [
        ({}, True),
        ({"llm_provider_primary": "openrouter", "llm_provider_fallback": "openrouter"}, False),
    ],
)
def test_a_dry_run_makes_no_ssh_call(watchdog, logs_check, caplog):
    prov = InfrastructureProvisioner(deployer=MagicMock())
    ctx = _ctx("vps2", dry_run=True, watchdog=watchdog)
    with (
        patch("fabrik.drivers.ssh.ssh") as ssh,
        caplog.at_level("INFO", logger="fabrik.orchestrator.infrastructure"),
    ):
        prov._provision_watchdog("spoke-app", ctx, dry_run=True)
    ssh.assert_not_called()
    assert not ctx.registrar_failures
    assert ("would check the Claude login files on vps2" in caplog.text) is logs_check


@pytest.mark.parametrize("target", ["vps2", "vps1"])
def test_provision_provisions_the_watchdog_roles_and_analytics_on_every_target(target):
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
    assert analytics.call_args.kwargs["record_failure"] is True
    assert postgres.call_args.kwargs["provision_watchdog_roles"] is True


def test_plan_no_longer_names_a_spoke_refusal():
    from fabrik.orchestrator.infrastructure import resolve_applicability

    spoke = resolve_applicability({"id": "x", "target_vps": "vps2", "watchdog": {"enabled": True}})[
        "watchdog"
    ]
    assert spoke[0] is True
    assert "refused" not in spoke[1] and "D-1153" not in spoke[1]


def test_plan_does_not_call_a_switched_off_registrar_refused():
    from fabrik.orchestrator.infrastructure import resolve_applicability

    off = resolve_applicability(
        {
            "id": "x",
            "target_vps": "vps2",
            "watchdog": {"enabled": True},
            "infra": {"watchdog": False},
        }
    )["watchdog"]
    assert off[0] is False and "refused" not in off[1]


@pytest.mark.parametrize(
    "url, target, expected",
    [
        ("http://apprise:8000/notify/alerts", "vps2", "http://10.99.0.1:8202/notify/alerts"),
        ("http://apprise:8000/notify/alerts", "vps1", "http://apprise:8000/notify/alerts"),
        ("http://apprise:8000/notify/alerts", None, "http://apprise:8000/notify/alerts"),
        ("http://other:8000/notify/alerts", "vps2", "http://other:8000/notify/alerts"),
        (
            "http://u:p@apprise:8000/notify/alerts",
            "vps2",
            "http://u:p@apprise:8000/notify/alerts",
        ),
        ("", "vps2", ""),
    ],
)
def test_the_mesh_gated_url_rewrite(url, target, expected):
    from fabrik.orchestrator.infrastructure import _rewrite_mesh_gated_url

    assert _rewrite_mesh_gated_url(url, target) == expected
