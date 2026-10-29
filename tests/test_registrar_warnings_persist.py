"""W-0c60d86e — registrar warnings persist into ``.fabrik/state`` and reach every reader.

A registrar WARNING (a payments grant left ``pending``, a Prometheus target not loaded) used to reach only the
summary of the run that produced it. These tests pin that the warnings survive into the state record, that
``fabrik status`` and ``fabrik audit-registrars`` show them, and that ``fabrik reconcile-all`` reads the
refresh ctx it used to discard: registrar FAILURES fail the row, WARNINGS print under the table.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

import fabrik.cli as cli_module

# The autouse state-dir isolation and the orchestrator stub come from the state tests; the reconcile harness
# from the reconcile-all tests (helpers only — no test_* name is imported, so nothing is collected twice).
from tests.test_reconcile_all_deployed_set import (  # noqa: F401
    R1_PROJECTS,
    Harness,
    _row,
    _run,
    _spec,
    specs_dir,
)
from tests.test_state import _import, _isolate_state_dir, _orchestrator  # noqa: F401

_WARN = (
    "payments-ingest-role: grant pending — svc has not applied the fabrik-lib payments schema yet"
)


def test_warnings_round_trip_and_default():
    state = _import()
    common = {
        "spec_path": "/x.yaml",
        "spec_hash": "h",
        "coolify_uuid": None,
        "coolify_app_name": "svc",
        "registrars_applied": [],
        "git_sha": "a" * 40,
    }
    state.save("svc", registrar_warnings=[_WARN], **common)
    assert state.load("svc")["registrar_warnings"] == [_WARN]
    state.save("svc", **common)
    assert state.load("svc")["registrar_warnings"] == []


def test_warnings_are_sanitised():
    state = _import()
    state.save(
        "svc",
        spec_path="/x.yaml",
        spec_hash="h",
        coolify_uuid=None,
        coolify_app_name="svc",
        registrars_applied=[],
        git_sha="a" * 40,
        registrar_warnings=["prometheus: postgresql://u:hunter2@db/x unreachable"],
    )
    assert "hunter2" not in json.dumps(state.load("svc"))


def test_persist_state_writes_warnings(tmp_path):
    from fabrik.orchestrator.context import DeploymentContext

    state = _import()
    ctx = DeploymentContext(spec_path=tmp_path / "svc.yaml")
    ctx.registrar_warnings.append(_WARN)
    _orchestrator()._persist_state(ctx, {"id": "svc", "name": "svc"})
    assert state.load("svc")["registrar_warnings"] == [_WARN]


def _status_output(tmp_path, record):
    state = _import()
    state.STATE_DIR.mkdir(parents=True, exist_ok=True)
    (state.STATE_DIR / "demo.json").write_text(json.dumps(record))
    spec = tmp_path / "demo.yaml"
    spec.write_text("id: demo\ntemplate: python-api\ndomain: demo.example.com\n")
    probe = {"exists": False, "ps": "", "error": None}
    with patch("fabrik.orchestrator.deployer_ssh.SSHDeployer.probe_app", return_value=probe):
        return CliRunner().invoke(cli_module.cli, ["status", str(spec)])


def test_status_prints_recorded_warnings(tmp_path):
    result = _status_output(tmp_path, {"applied_at": "t", "registrar_warnings": [_WARN]})
    assert f"registrar_warning: {_WARN}" in result.output, result.output


def test_status_tolerates_record_without_warnings(tmp_path):
    result = _status_output(tmp_path, {"applied_at": "t", "registrar_warnings": "one scalar"})
    assert "registrar_warning: one scalar" in result.output, result.output
    result = _status_output(tmp_path, {"applied_at": "t"})
    assert result.exit_code == 0, result.output
    assert "registrar_warning" not in result.output


def _ctx(failures=(), warnings=()):
    ctx = MagicMock()
    ctx.registrar_failures = list(failures)
    ctx.registrar_warnings = list(warnings)
    return ctx


class _CtxHarness(Harness):
    def __init__(self, hosts, ctx):
        super().__init__(hosts)
        self.ctx = ctx

    def refresh(self, spec_path, dry_run=False, target_vps=None):
        super().refresh(spec_path, dry_run=dry_run, target_vps=target_vps)
        return self.ctx


def test_reconcile_all_failures_fail_the_row(specs_dir):  # noqa: F811
    _spec(specs_dir, "a")
    result = _run(
        _CtxHarness({"vps1": R1_PROJECTS}, _ctx(failures=["redis: REDIS_URL injection failed"])),
        ["--yes"],
    )
    assert _row(result.output, "a") == "registrar-failed — redis", result.output
    assert result.exit_code == 1


def test_reconcile_all_failures_dry_run_row_exits_0(specs_dir):  # noqa: F811
    _spec(specs_dir, "a")
    result = _run(_CtxHarness({"vps1": R1_PROJECTS}, _ctx(failures=["redis: boom"])), [])
    assert _row(result.output, "a") == "registrar-failed — redis", result.output
    assert result.exit_code == 0


def test_reconcile_all_prints_warnings_keeps_status(specs_dir):  # noqa: F811
    _spec(specs_dir, "a")
    result = _run(_CtxHarness({"vps1": R1_PROJECTS}, _ctx(warnings=[_WARN])), ["--yes"])
    assert _row(result.output, "a") == "reconciled", result.output
    assert f"⚠ a: {_WARN}" in result.output
    assert result.exit_code == 0


def test_audit_registrars_names_recorded_warnings(tmp_path):
    state = _import()
    state.save(
        "svc",
        spec_path="/x.yaml",
        spec_hash="h",
        coolify_uuid=None,
        coolify_app_name="svc",
        registrars_applied=[],
        git_sha="a" * 40,
        registrar_warnings=[_WARN],
    )
    from fabrik.cli import _report_recorded_registrar_problems

    lines: list[str] = []
    _report_recorded_registrar_problems(["svc"], lines.append)
    assert any("svc" in line and "1 registrar warning(s)" in line for line in lines), lines
