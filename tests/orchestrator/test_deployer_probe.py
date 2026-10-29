"""Tests for the deployer's read-only probe helpers (T01, Coolify-verb retirement).

Covers ``app_dir``, ``_host_env`` / ``_target_vps_env``, ``SSHDeployer.probe_app``,
``SSHDeployer.list_compose_projects`` and ``_parse_compose_ps`` — every ssh call is a
recording fake of ``fabrik.drivers.ssh.ssh`` (no network).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from types import SimpleNamespace
from unittest.mock import call, patch

import pytest

from fabrik.orchestrator.deployer_ssh import (
    SSHDeployer,
    _host_env,
    _parse_compose_ps,
    _target_vps_env,
    app_dir,
)
from fabrik.orchestrator.exceptions import ProvisioningError
from fabrik.spec_loader import Source, SourceType, Spec

_PATH = "/opt/my app"
_EXISTS_CMD = "sudo sh -c " + shlex.quote(
    "[ -f " + shlex.quote(_PATH + "/compose.yaml") + " ] && echo exists || echo absent"
)
_PS_CMD = "cd " + shlex.quote(_PATH) + " && sudo docker compose ps -a --format json"


# ======================================================================
# probe_app
# ======================================================================


class TestProbeApp:
    def test_records_both_commands_quoted_once_per_shell_layer(self):
        with patch("fabrik.drivers.ssh.ssh") as fake:
            fake.side_effect = ["exists", ""]
            result = SSHDeployer().probe_app(_PATH)

        assert fake.call_args_list == [
            call(_EXISTS_CMD, timeout=10),
            call(_PS_CMD, timeout=15),
        ]
        assert result == {"exists": True, "ps": "", "error": None}

    def test_absent_stops_after_first_command_without_error(self):
        with patch("fabrik.drivers.ssh.ssh", return_value="absent") as fake:
            result = SSHDeployer().probe_app(_PATH)

        assert fake.call_count == 1
        assert result == {"exists": False, "ps": "", "error": None}

    @pytest.mark.parametrize(
        "exc",
        [
            RuntimeError("SSH command failed (exit 255): host down"),
            subprocess.TimeoutExpired(cmd="ssh", timeout=10),
            FileNotFoundError(2, "No such file or directory", "ssh"),
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        ],
        ids=["runtime-error", "timeout", "no-ssh-binary", "undecodable-stdout"],
    )
    def test_first_call_exception_is_a_returned_host_error(self, exc):
        with patch("fabrik.drivers.ssh.ssh", side_effect=exc) as fake:
            result = SSHDeployer().probe_app(_PATH)

        assert fake.call_count == 1, "the ps command must never be sent"
        assert result["exists"] is False
        assert result["ps"] == ""
        assert result["error"]
        assert type(exc).__name__ in result["error"]

    @pytest.mark.parametrize(
        "stdout",
        ["", "Welcome to Ubuntu 24.04 LTS", "Welcome\nexists", "exists absent", "EXISTS"],
        ids=["empty", "banner", "banner-then-exists", "both-words", "upper"],
    )
    def test_first_call_unexpected_stdout_is_an_error(self, stdout):
        with patch("fabrik.drivers.ssh.ssh", return_value=stdout) as fake:
            result = SSHDeployer().probe_app(_PATH)

        assert fake.call_count == 1
        assert result["exists"] is False
        assert result["error"]

    def test_ps_timeout_keeps_exists_and_sets_error(self):
        with patch("fabrik.drivers.ssh.ssh") as fake:
            fake.side_effect = ["exists", subprocess.TimeoutExpired(cmd="ssh", timeout=15)]
            result = SSHDeployer().probe_app(_PATH)

        assert result["exists"] is True
        assert result["ps"] == ""
        assert "TimeoutExpired" in result["error"]

    @pytest.mark.parametrize(
        "exc",
        [
            FileNotFoundError(2, "No such file or directory", "ssh"),
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        ],
        ids=["no-ssh-binary", "undecodable-stdout"],
    )
    def test_ps_transport_exception_keeps_exists_and_sets_error(self, exc):
        """Spec D2: either call's exception is captured into ``error`` -- never a crash."""
        with patch("fabrik.drivers.ssh.ssh") as fake:
            fake.side_effect = ["exists", exc]
            result = SSHDeployer().probe_app(_PATH)

        assert result["exists"] is True
        assert result["ps"] == ""
        assert type(exc).__name__ in result["error"]

    def test_ps_pathologically_nested_body_is_an_error_not_a_crash(self):
        body = "[" * 100_000
        with patch("fabrik.drivers.ssh.ssh") as fake:
            fake.side_effect = ["exists", body]
            result = SSHDeployer().probe_app(_PATH)

        assert result["exists"] is True
        assert result["ps"] == body
        assert result["error"]

    def test_ps_non_json_keeps_raw_text_and_sets_error(self):
        with patch("fabrik.drivers.ssh.ssh") as fake:
            fake.side_effect = ["exists", "permission denied while trying to connect"]
            result = SSHDeployer().probe_app(_PATH)

        assert result["exists"] is True
        assert result["ps"] == "permission denied while trying to connect"
        assert result["error"]

    def test_ps_object_body_sets_error(self):
        """A valid-JSON body that is not a row list (``{}``) is reported, not swallowed."""
        with patch("fabrik.drivers.ssh.ssh") as fake:
            fake.side_effect = ["exists", "{}"]
            result = SSHDeployer().probe_app(_PATH)

        assert result["exists"] is True
        assert result["ps"] == "{}"
        assert result["error"] and "Service" in result["error"]

    def test_ps_valid_json_lines_has_no_error(self):
        body = json.dumps({"Service": "web", "State": "running", "Health": "", "ExitCode": 0})
        with patch("fabrik.drivers.ssh.ssh") as fake:
            fake.side_effect = ["exists", body]
            result = SSHDeployer().probe_app(_PATH)

        assert result == {"exists": True, "ps": body, "error": None}


# ======================================================================
# _parse_compose_ps
# ======================================================================

_TWENTY_KEYS = (
    "Command",
    "CreatedAt",
    "ExitCode",
    "Health",
    "ID",
    "Image",
    "Labels",
    "LocalVolumes",
    "Mounts",
    "Name",
    "Names",
    "Networks",
    "Ports",
    "Project",
    "Publishers",
    "RunningFor",
    "Service",
    "Size",
    "State",
    "Status",
)


def _row(service: str, state: str, health: str, exit_code: int) -> dict:
    row = {k: f"x-{k}" for k in _TWENTY_KEYS}
    row.update(
        {
            "Service": service,
            "State": state,
            "Health": health,
            "ExitCode": exit_code,
            "Publishers": [],
            "Engine": "unknown-21st-key",
        }
    )
    return row


_ROWS = [
    _row("web", "running", "healthy", 0),
    _row("worker", "exited", "", 137),
    _row("beat", "running", "", 0),
    _row("cache", "running", "none", 0),
]
_EXPECTED = [
    {"Service": "web", "State": "running", "Health": "healthy", "ExitCode": "0"},
    {"Service": "worker", "State": "exited", "Health": "", "ExitCode": "137"},
    {"Service": "beat", "State": "running", "Health": "", "ExitCode": "0"},
    {"Service": "cache", "State": "running", "Health": "none", "ExitCode": "0"},
]


class TestParseComposePs:
    def test_json_lines_yield_four_keys_per_row(self):
        assert len(_TWENTY_KEYS) == 20
        text = "\n".join(json.dumps(r) for r in _ROWS)
        assert _parse_compose_ps(text) == _EXPECTED

    def test_leading_array_yields_the_same_rows(self):
        text = json.dumps(_ROWS, indent=2)
        assert _parse_compose_ps(text) == _EXPECTED

    def test_empty_body_is_no_rows(self):
        assert _parse_compose_ps("") == []
        assert _parse_compose_ps("  \n") == []

    def test_blank_lines_are_skipped_and_null_or_missing_values_are_empty_strings(self):
        text = (
            '{"Service": "a", "State": "exited", "Health": "", "ExitCode": null}\n'
            "\n"
            '{"Service": "b", "State": "running"}\n'
        )
        assert _parse_compose_ps(text) == [
            {"Service": "a", "State": "exited", "Health": "", "ExitCode": ""},
            {"Service": "b", "State": "running", "Health": "", "ExitCode": ""},
        ]

    def test_non_json_raises_value_error(self):
        with pytest.raises(ValueError):
            _parse_compose_ps("not json at all")

    @pytest.mark.parametrize(
        "body",
        [
            "{}",
            '{"foo": "bar"}',
            "[{}]",
            '[{"State": "running"}]',
            '{"Service": null, "State": "running"}',
            '[{"Service": "", "State": "running"}]',
        ],
    )
    def test_object_without_a_service_is_not_a_row(self, body):
        """A JSON object without a non-empty Service is an error, never one phantom blank row."""
        with pytest.raises(ValueError, match="Service"):
            _parse_compose_ps(body)


# ======================================================================
# app_dir
# ======================================================================


class TestAppDir:
    def test_dict_without_source_gives_both_candidates(self):
        spec = {"name": "refresh-test", "id": "refresh-test"}
        assert app_dir(spec) == ["/opt/refresh-test", "/opt/fabrik-refresh-test"]

    def test_dict_id_only_falls_back_to_id(self):
        assert app_dir({"id": "only-id"}) == ["/opt/only-id", "/opt/fabrik-only-id"]

    def test_local_dict_strips_trailing_slash(self):
        spec = {
            "name": "fabrik-file-worker",
            "id": "fabrik-file-worker",
            "source": {"type": "local", "path": "/opt/file-worker/"},
        }
        assert app_dir(spec) == ["/opt/file-worker"]

    def test_local_model_same_as_dict(self):
        spec = Spec(
            id="fabrik-file-worker",
            template="file-worker",
            domain="file-worker.example.com",
            source=Source(type=SourceType.LOCAL, path="/opt/file-worker/"),
        )
        assert app_dir(spec) == ["/opt/file-worker"]

    def test_local_path_none_falls_back_to_opt_name(self):
        spec = {"name": "captcha", "id": "captcha", "source": {"type": "local", "path": None}}
        assert app_dir(spec) == ["/opt/captcha"]

    def test_fabrik_prefixed_id_has_no_double_prefix(self):
        spec = Spec(id="fabrik-citation-verifier", template="python-api", domain="cv.example.com")
        assert app_dir(spec) == ["/opt/fabrik-citation-verifier"]

    @pytest.mark.parametrize("path", ["/srv/x", "/opt/a/b", "/opt", "opt/x", "/opt/../srv"])
    def test_local_path_outside_opt_raises_naming_the_path(self, path):
        spec = {"id": "x", "source": {"type": "local", "path": path}}
        with pytest.raises(ProvisioningError, match=re.escape(repr(path))):
            app_dir(spec)

    @pytest.mark.parametrize("path", ["/opt/./x", "/opt//x", "/opt/x/", "/opt/a/../x"])
    def test_local_path_is_normalised_lexically(self, path):
        spec = {"id": "x", "source": {"type": "local", "path": path}}
        assert app_dir(spec) == ["/opt/x"]

    def test_dict_without_name_or_id_raises(self):
        with pytest.raises(ProvisioningError, match="neither name nor id"):
            app_dir({})

    @pytest.mark.parametrize("name", ["../etc", "Etc", "a b", "-x", 5], ids=repr)
    def test_name_failing_the_app_name_pattern_raises_before_any_candidate(self, name):
        """``/opt/<n>`` is built from ``name or id``; a value _validate_name would refuse never reaches a probe."""
        with pytest.raises(ProvisioningError, match="invalid app name"):
            app_dir({"id": name})


# ======================================================================
# _host_env / _target_vps_env
# ======================================================================


class TestHostEnv:
    @pytest.mark.parametrize("host", ["vps1", None, ""])
    def test_hub_and_falsy_are_noops(self, host, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "sentinel")
        with _host_env(host):
            assert os.environ["FABRIK_VPS_SSH_HOST"] == "sentinel"
        assert os.environ["FABRIK_VPS_SSH_HOST"] == "sentinel"

    def test_spoke_sets_and_restores_previous(self, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        with _host_env("vps2"):
            assert os.environ["FABRIK_VPS_SSH_HOST"] == "vps2"
        assert os.environ["FABRIK_VPS_SSH_HOST"] == "vps"

    def test_spoke_restores_previous_even_on_exception(self, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        with pytest.raises(KeyError), _host_env("vps2"):
            raise KeyError("boom")
        assert os.environ["FABRIK_VPS_SSH_HOST"] == "vps"

    def test_spoke_pops_when_unset_even_on_exception(self, monkeypatch):
        monkeypatch.delenv("FABRIK_VPS_SSH_HOST", raising=False)
        with pytest.raises(KeyError), _host_env("vps2"):
            assert os.environ["FABRIK_VPS_SSH_HOST"] == "vps2"
            raise KeyError("boom")
        assert "FABRIK_VPS_SSH_HOST" not in os.environ

    def test_target_vps_env_delegates(self, monkeypatch):
        monkeypatch.delenv("FABRIK_VPS_SSH_HOST", raising=False)
        with _target_vps_env(SimpleNamespace(target_vps="vps2")):
            assert os.environ["FABRIK_VPS_SSH_HOST"] == "vps2"
        assert "FABRIK_VPS_SSH_HOST" not in os.environ
        with _target_vps_env(SimpleNamespace()):
            assert "FABRIK_VPS_SSH_HOST" not in os.environ


# ======================================================================
# list_compose_projects
# ======================================================================


class TestListComposeProjects:
    def test_runs_under_host_swap_and_parses_array(self, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        body = [
            {
                "Name": "a",
                "Status": "running(2)",
                "ConfigFiles": "/opt/a/compose.yaml,/opt/a/compose.dev.yaml",
            }
        ]
        seen: list[str | None] = []

        def fake(cmd, timeout=60, dry_run=False):
            seen.append(os.environ.get("FABRIK_VPS_SSH_HOST"))
            return json.dumps(body)

        with patch("fabrik.drivers.ssh.ssh", side_effect=fake) as rec:
            result = SSHDeployer().list_compose_projects("vps2")

        assert rec.call_args_list == [call("sudo docker compose ls -a --format json", timeout=60)]
        assert seen == ["vps2"]
        assert os.environ["FABRIK_VPS_SSH_HOST"] == "vps"
        assert result == body

    @pytest.mark.parametrize(
        "text",
        ["oops not json", "null", "{}", '[1, "x", null]', '[{"Name": "a"}, "x"]'],
        ids=["junk", "null", "obj", "non-object-entries", "one-non-object"],
    )
    def test_non_array_of_objects_body_raises_naming_host(self, text):
        with (
            patch("fabrik.drivers.ssh.ssh", return_value=text),
            pytest.raises(RuntimeError, match="vps2"),
        ):
            SSHDeployer().list_compose_projects("vps2")
