"""The Prometheus reload outcome reaches the operator (W-cc9b0532).

The four target functions used to call ``_reload_prometheus()`` bare, so a scrape config written but never
loaded still read ``created``. Now the adds return ``reload: <outcome>`` on create AND on exists (a re-run
re-checks), the removes return the reload's success, ``fabrik apply`` fails on ``refused`` (promtool rejected
the on-disk config — the next restart crash-loops Prometheus, D-513) and warns on ``unavailable``, and
``fabrik vultr provision`` prints a spoke whose registration did not load.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from fabrik.drivers import prometheus as prom
from fabrik.orchestrator import vultr_provision as vprov
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.infrastructure import InfrastructureProvisioner

_OUTCOMES = ["reloaded", "restarted", "refused", "unavailable"]


def _aro_cfg(with_spoke: bool = False) -> dict:
    static = [{"targets": ["10.0.1.1:8201"], "labels": {"host": "vps1", "role": "hub"}}]
    if with_spoke:
        static.append({"targets": ["10.99.0.4:8201"], "labels": {"host": "vps4", "role": "spoke"}})
    return {"scrape_configs": [{"job_name": "aro-wake", "static_configs": static}]}


def _wire(monkeypatch, cfg: dict, outcome: str) -> list[dict]:
    written: list[dict] = []
    monkeypatch.setattr(prom, "_read_config", lambda: cfg)
    monkeypatch.setattr(prom, "_write_config", lambda d: written.append(d))
    monkeypatch.setattr(prom, "_reload_prometheus_outcome", lambda: outcome)
    return written


# ── the adds return the outcome on create and on exists ─────────────────────────────── #


@pytest.mark.parametrize("outcome", _OUTCOMES)
def test_add_scrape_target_returns_the_reload_outcome_on_create(monkeypatch, outcome) -> None:
    written = _wire(monkeypatch, {"scrape_configs": []}, outcome)
    r = prom.add_scrape_target("svc", domain="svc.example.com")
    assert r["status"] == "created" and r["reload"] == outcome
    assert len(written) == 1


@pytest.mark.parametrize("outcome", _OUTCOMES)
def test_add_scrape_target_reloads_and_reports_on_exists(monkeypatch, outcome) -> None:
    # a job already matching the spec (an incomplete one now reads `updated`, W-01815aee)
    job = {
        "job_name": f"{prom.JOB_PREFIX}svc",
        "scheme": "https",
        "metrics_path": "/metrics",
        "static_configs": [{"targets": ["svc.example.com:443"]}],
    }
    written = _wire(monkeypatch, {"scrape_configs": [job]}, outcome)
    r = prom.add_scrape_target("svc", domain="svc.example.com")
    assert r["status"] == "exists" and r["reload"] == outcome
    assert written == []  # nothing rewritten, but the reload re-checks what is on disk


def test_a_dry_run_add_reloads_nothing(monkeypatch) -> None:
    def _boom():
        raise AssertionError("a dry run must not reload")

    monkeypatch.setattr(prom, "_reload_prometheus_outcome", _boom)
    assert "reload" not in prom.add_scrape_target("svc", domain="svc.example.com", dry_run=True)
    assert "reload" not in prom.add_aro_wake_target("vps4", "10.99.0.4", dry_run=True)


@pytest.mark.parametrize("outcome", _OUTCOMES)
@pytest.mark.parametrize("with_spoke", [False, True], ids=["create", "exists"])
def test_add_aro_wake_target_returns_the_reload_outcome(monkeypatch, outcome, with_spoke) -> None:
    _wire(monkeypatch, _aro_cfg(with_spoke), outcome)
    r = prom.add_aro_wake_target("vps4", "10.99.0.4")
    assert r["status"] == ("exists" if with_spoke else "created")
    assert r["reload"] == outcome


# ── the removes return the reload's success after a rewrite ─────────────────────────── #


@pytest.mark.parametrize(
    ("outcome", "ok"),
    [("reloaded", True), ("restarted", True), ("refused", False), ("unavailable", False)],
)
def test_remove_scrape_target_returns_the_reload_success(monkeypatch, outcome, ok) -> None:
    _wire(monkeypatch, {"scrape_configs": [{"job_name": f"{prom.JOB_PREFIX}svc"}]}, outcome)
    assert prom.remove_scrape_target("svc") is ok


@pytest.mark.parametrize(
    ("outcome", "ok"),
    [("reloaded", True), ("restarted", True), ("refused", False), ("unavailable", False)],
)
def test_remove_aro_wake_target_returns_the_reload_success(monkeypatch, outcome, ok) -> None:
    _wire(monkeypatch, _aro_cfg(with_spoke=True), outcome)
    assert prom.remove_aro_wake_target("vps4") is ok


def test_a_remove_with_nothing_to_remove_stays_true_without_a_reload(monkeypatch) -> None:
    written = _wire(monkeypatch, _aro_cfg(), "unavailable")
    assert prom.remove_aro_wake_target("vps4") is True
    _wire(monkeypatch, {"scrape_configs": []}, "unavailable")
    assert prom.remove_scrape_target("svc") is True
    assert written == []


# ── fabrik apply: refused fails, unavailable warns ──────────────────────────────────── #


def _apply(outcome: str | None) -> DeploymentContext:
    prov = InfrastructureProvisioner(deployer=mock.MagicMock())
    ctx = DeploymentContext(spec_path=Path("specs/services/svc.yaml"))
    result = {"status": "created", "job": "fabrik-svc", "target": "svc.example.com:443"}
    if outcome is not None:
        result["reload"] = outcome
    with mock.patch("fabrik.drivers.prometheus.add_scrape_target", return_value=result):
        prov._provision_prometheus("svc", "svc.example.com", {}, ctx, False)
    return ctx


def _status(ctx: DeploymentContext) -> list[str]:
    return [r.metadata.get("status") for r in ctx.get_resources_by_type("prometheus")]


@pytest.mark.parametrize("outcome", ["reloaded", "restarted", None])
def test_a_loaded_config_adds_no_failure_and_no_warning(outcome) -> None:
    ctx = _apply(outcome)
    assert ctx.registrar_failures == [] and ctx.registrar_warnings == []
    assert _status(ctx) == ["created"]


def test_a_refused_config_fails_the_apply() -> None:
    ctx = _apply("refused")
    assert len(ctx.registrar_failures) == 1
    assert ctx.registrar_failures[0].startswith("prometheus: ")
    assert "promtool" in ctx.registrar_failures[0]
    assert ctx.registrar_warnings == []
    assert _status(ctx) == ["failed"]  # never recorded created (review B-1)


def test_an_unavailable_prometheus_warns_once() -> None:
    ctx = _apply("unavailable")
    assert ctx.registrar_failures == []
    assert len(ctx.registrar_warnings) == 1
    assert ctx.registrar_warnings[0].startswith("prometheus: ")
    assert "svc" in ctx.registrar_warnings[0]
    assert _status(ctx) == ["created"]


# ── the spoke path: recorded and printed ────────────────────────────────────────────── #


@pytest.mark.parametrize(
    ("outcome", "shown"),
    [
        ("reloaded", "created"),
        ("refused", "created (prometheus refused)"),
        ("unavailable", "created (prometheus unavailable)"),
    ],
)
def test_register_observability_marks_an_unloaded_registration(monkeypatch, outcome, shown) -> None:
    monkeypatch.setattr(
        "fabrik.drivers.prometheus.add_aro_wake_target",
        lambda name, ip, **k: {"status": "created", "reload": outcome},
    )
    monkeypatch.setattr(
        "fabrik.drivers.gatus.add_aro_wake_endpoint", lambda name, ip, **k: {"status": "created"}
    )
    report: dict = {}
    vprov._register_observability("vps4", "10.99.0.4", report)
    assert report["observability"]["prometheus"] == shown


@pytest.mark.parametrize(
    ("obs", "warned"),
    [
        ({"prometheus": "created", "gatus": "exists"}, 0),
        ({"prometheus": "created (prometheus unavailable)", "gatus": "created"}, 1),
        ({"prometheus": "error: boom", "gatus": "error: x"}, 2),
    ],
)
def test_vultr_provision_prints_every_observability_entry_that_did_not_land(
    monkeypatch, obs, warned
) -> None:
    from fabrik import cli as fabrik_cli

    rep = {
        "success": True,
        "ip": "1.2.3.4",
        "mesh_ip": "10.99.0.4",
        "bootstrap_rc": 0,
        "observability": obs,
    }
    monkeypatch.setenv("VULTR_SSHKEY_ID", "k")
    with (
        mock.patch("fabrik.drivers.vultr.VultrClient"),
        mock.patch("fabrik.orchestrator.vultr_provision.provision", return_value=rep),
    ):
        result = CliRunner().invoke(
            fabrik_cli.cli, ["vultr", "provision", "vps4", "--yes"], catch_exceptions=False
        )
    lines = [ln for ln in result.output.splitlines() if ln.startswith("⚠ observability ")]
    assert len(lines) == warned, result.output
    assert result.exit_code == 0
