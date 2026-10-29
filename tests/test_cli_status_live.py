"""T02 (Coolify-verb retirement, D2) — `fabrik status` prints the last apply + live containers.

The Coolify block in `fabrik.cli.status` is replaced by two read-only sections: "Last apply"
(from `fabrik.state.load`) and "Live containers" (`SSHDeployer.probe_app` over `app_dir(spec)`
candidates, parsed by `_parse_compose_ps`). Every ssh call is faked via
`SSHDeployer.probe_app` (never the network); `fabrik.state.STATE_DIR` is redirected to a
throwaway directory per test. `status` exits 0 in every probe outcome and exits 1 only for a
spec that fails to load or an `app_dir` `ProvisioningError` (spec D2, invariant 2).
"""

from __future__ import annotations

import inspect
import json
import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner

import fabrik.cli as cli_module
from fabrik.orchestrator.deployer_ssh import SSHDeployer

cli = cli_module.cli


def _write_spec(tmp_path, name="demo", *, target_vps=None, source_block="") -> str:
    lines = [f"id: {name}", "template: python-api", f"domain: {name}.example.com"]
    if target_vps:
        lines.append(f"target_vps: {target_vps}")
    if source_block:
        lines.append(source_block)
    path = tmp_path / f"{name}.yaml"
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def _write_state(state_dir, spec_id, payload):
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{spec_id}.json").write_text(json.dumps(payload))


@pytest.fixture(autouse=True)
def _state_dir(tmp_path, monkeypatch):
    """Redirect `fabrik.state.STATE_DIR` to a throwaway dir — never the real `.fabrik/state`."""
    import fabrik.state as state_module

    state_dir = tmp_path / "state"
    monkeypatch.setattr(state_module, "STATE_DIR", state_dir)
    return state_dir


class TestLastApply:
    def test_record_prints_timestamp_sha_vps_types_and_failure(self, tmp_path, _state_dir):
        spec_path = _write_spec(tmp_path, "demo")
        _write_state(
            _state_dir,
            "demo",
            {
                "applied_at": "2026-10-14T00:00:00+00:00",
                "git_sha": "a" * 40,
                "target_vps": "vps2",
                "registrars_applied": [
                    {"type": "postgres", "id": "demo", "status": "applied", "data_bearing": True},
                    {"type": "gatus", "id": "demo", "status": "applied", "data_bearing": False},
                ],
                "registrar_failures": [{"registrar": "redis", "error": "boom"}],
            },
        )
        with patch.object(
            SSHDeployer, "probe_app", return_value={"exists": False, "ps": "", "error": None}
        ):
            result = CliRunner().invoke(cli, ["status", spec_path])

        assert result.exit_code == 0
        assert "2026-10-14T00:00:00+00:00" in result.output
        assert f"git_sha: {'a' * 12}" in result.output
        assert "a" * 13 not in result.output  # the 40-char sha must be TRUNCATED, not raw
        assert "vps2" in result.output
        assert "registrars_applied: postgres, gatus" in result.output
        assert "registrar_failure: redis: boom" in result.output
        assert "redis" in result.output
        assert "boom" in result.output

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            (
                {"registrars_applied": [{"id": "x"}, "junk"], "registrar_failures": ["boom"]},
                ["registrars_applied: ?\n", "registrar_failure: ?: boom"],
            ),
            ({"applied_at": None, "git_sha": None, "target_vps": None}, ["git_sha: \n"]),
            (["not", "an", "object"], ["no state record"]),
            ({"registrar_failures": "boom"}, ["registrar_failure: ?: boom\n\nLive"]),
            ({"registrars_applied": "postgres"}, ["registrars_applied: \n"]),
            ({"registrar_failures": [{"registrar": "redis"}]}, ["registrar_failure: redis: \n"]),
            ({"git_sha": 1234567890123456}, ["git_sha: 123456789012\n"]),
        ],
        ids=[
            "rows-without-type",
            "null-fields",
            "record-not-an-object",
            "failures-is-a-string",
            "rows-is-a-string",
            "failure-without-error",
            "sha-is-an-int",
        ],
    )
    def test_odd_record_shapes_never_crash_the_verb(self, tmp_path, _state_dir, payload, expected):
        """A read-only verb tolerates every record shape (invariant 2): a non-object record reads as
        none, and a scalar where a list belongs is ONE row, never iterated character by character."""
        spec_path = _write_spec(tmp_path, "demo")
        _write_state(_state_dir, "demo", payload)
        with patch.object(
            SSHDeployer, "probe_app", return_value={"exists": False, "ps": "", "error": None}
        ):
            result = CliRunner().invoke(cli, ["status", spec_path])

        assert result.exit_code == 0, result.output
        assert "None" not in result.output
        assert "Live containers:" in result.output
        assert result.output.count("registrar_failure:") <= 1
        for needle in expected:
            assert needle in result.output, (needle, result.output)

    def test_no_record_prints_never_applied_and_exits_zero(self, tmp_path):
        spec_path = _write_spec(tmp_path, "demo")
        with patch.object(
            SSHDeployer, "probe_app", return_value={"exists": False, "ps": "", "error": None}
        ):
            result = CliRunner().invoke(cli, ["status", spec_path])

        assert result.exit_code == 0
        assert "no state record — never applied from this checkout" in result.output


class TestLiveContainers:
    def test_four_rows_print_with_health_labels(self, tmp_path):
        spec_path = _write_spec(tmp_path, "demo")
        rows = [
            {"Service": "web", "State": "running", "Health": "healthy", "ExitCode": 0},
            {"Service": "worker", "State": "exited", "Health": "", "ExitCode": 137},
            {"Service": "beat", "State": "running", "Health": "", "ExitCode": 0},
            {"Service": "cache", "State": "running", "Health": "none", "ExitCode": 0},
        ]
        ps_text = "\n".join(json.dumps(r) for r in rows)
        with patch.object(
            SSHDeployer,
            "probe_app",
            return_value={"exists": True, "ps": ps_text, "error": None},
        ) as fake:
            result = CliRunner().invoke(cli, ["status", spec_path])

        assert result.exit_code == 0
        assert fake.call_count == 1, "the walk stops at the first `exists` True candidate"
        assert "web · running · healthy · 0" in result.output
        assert "worker · exited · — · 137" in result.output
        assert "beat · running · no healthcheck · 0" in result.output
        assert (
            "cache · running · no healthcheck · 0" in result.output
        )  # moby's "none" (invariant 3)

    def test_every_candidate_absent_prints_one_line_each(self, tmp_path):
        spec_path = _write_spec(tmp_path, "demo")
        with patch.object(
            SSHDeployer, "probe_app", return_value={"exists": False, "ps": "", "error": None}
        ) as fake:
            result = CliRunner().invoke(cli, ["status", spec_path])

        assert result.exit_code == 0
        assert fake.call_count == 2  # /opt/demo, /opt/fabrik-demo
        assert "no /opt/demo/compose.yaml on vps1" in result.output
        assert "no /opt/fabrik-demo/compose.yaml on vps1" in result.output

    def test_host_unreachable_prints_warning_and_stops_the_walk(self, tmp_path):
        spec_path = _write_spec(tmp_path, "demo")
        with patch.object(
            SSHDeployer,
            "probe_app",
            return_value={"exists": False, "ps": "", "error": "connection refused"},
        ) as fake:
            result = CliRunner().invoke(cli, ["status", spec_path])

        assert result.exit_code == 0
        assert fake.call_count == 1, (
            "an unreachable host must never be read as 'no compose project'"
        )
        assert "⚠️ could not reach vps1: connection refused" in result.output

    def test_exists_true_with_error_prints_could_not_read_warning(self, tmp_path):
        spec_path = _write_spec(tmp_path, "demo")
        with patch.object(
            SSHDeployer,
            "probe_app",
            return_value={"exists": True, "ps": "", "error": "permission denied"},
        ) as fake:
            result = CliRunner().invoke(cli, ["status", spec_path])

        assert result.exit_code == 0
        assert fake.call_count == 1
        assert "⚠️ could not read containers on vps1: permission denied" in result.output


class TestHostMismatch:
    def test_differing_target_vps_prints_both_and_swaps_the_env(self, tmp_path, _state_dir):
        spec_path = _write_spec(tmp_path, "demo", target_vps="vps2")
        _write_state(_state_dir, "demo", {"target_vps": "vps1"})
        seen: list[str | None] = []

        def fake(path):
            seen.append(os.environ.get("FABRIK_VPS_SSH_HOST"))
            return {"exists": False, "ps": "", "error": None}

        with patch.object(SSHDeployer, "probe_app", side_effect=fake):
            result = CliRunner().invoke(cli, ["status", spec_path])

        assert result.exit_code == 0
        assert "host: vps2 (last apply recorded vps1)" in result.output
        assert seen == ["vps2", "vps2"]


class TestLocalSourceOutsideOpt:
    def test_errors_and_makes_no_ssh_call(self, tmp_path):
        spec_path = _write_spec(
            tmp_path, "demo", source_block="source:\n  type: local\n  path: /srv/x\n"
        )
        with patch.object(SSHDeployer, "probe_app") as fake:
            result = CliRunner().invoke(cli, ["status", spec_path])

        assert result.exit_code == 1
        assert result.stderr.startswith("Error: ")
        assert "/srv/x" in result.stderr
        assert "Status for:" not in result.output  # the guard fires before any output
        assert "Error:" not in result.stdout  # the error goes to stderr, like a load failure
        fake.assert_not_called()


class TestNoCoolifyWord:
    def test_rebased_status_names_neither_coolify_nor_capital_coolify(self):
        src = inspect.getsource(cli_module.status.callback)
        assert "coolify" not in src.lower()
