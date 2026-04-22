"""Unit tests for fabrik.drivers.ssh — mocked subprocess, no VPS required."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from fabrik.drivers import ssh as ssh_mod
from fabrik.drivers.ssh import scp_to_vps, ssh


class TestSshHost:
    """Verify FABRIK_VPS_SSH_HOST override behavior (function-level lookup)."""

    def test_default_host_is_vps_alias(self, monkeypatch):
        monkeypatch.delenv("FABRIK_VPS_SSH_HOST", raising=False)
        assert ssh_mod._ssh_host() == "vps"

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "test-vps-alias")
        assert ssh_mod._ssh_host() == "test-vps-alias"

    def test_override_is_dynamic_not_cached_at_import(self, monkeypatch):
        """Regression: module-level os.getenv would capture at import time."""
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "first")
        assert ssh_mod._ssh_host() == "first"
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "second")
        assert ssh_mod._ssh_host() == "second"


class TestSsh:
    """Tests for the ssh() wrapper."""

    def test_dry_run_does_not_invoke_subprocess(self):
        with patch("subprocess.run") as mock_run:
            result = ssh("uname -m", dry_run=True)
            assert result == ""
            mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_success_returns_stripped_stdout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="x86_64\n", stderr="")
        result = ssh("uname -m")
        assert result == "x86_64"

    @patch("subprocess.run")
    def test_nonzero_exit_raises_runtimeerror_with_stderr(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="ssh: connect to host vps: Network is unreachable\n",
        )
        with pytest.raises(RuntimeError, match="Network is unreachable"):
            ssh("uname -m")

    @patch("subprocess.run")
    def test_timeout_propagates(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ssh", timeout=60)
        with pytest.raises(subprocess.TimeoutExpired):
            ssh("sleep 999", timeout=60)

    @patch("subprocess.run")
    def test_uses_ssh_host_env_var(self, mock_run, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "staging-vps")
        mock_run.return_value = MagicMock(returncode=0, stdout="ok\n", stderr="")
        ssh("echo hi")
        args = mock_run.call_args[0][0]
        assert args[0] == "ssh"
        assert args[1] == "staging-vps"
        assert args[2] == "echo hi"

    @patch("subprocess.run")
    def test_cmd_passed_as_single_arg_not_split(self, mock_run):
        """Remote shell handles word splitting; we pass the command verbatim."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ssh("echo 'hello world' | grep hello")
        args = mock_run.call_args[0][0]
        assert args[2] == "echo 'hello world' | grep hello"

    @patch("subprocess.run")
    def test_check_false_disables_subprocess_raise(self, mock_run):
        """We handle non-zero ourselves to include stderr in the message."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ssh("true")
        kwargs = mock_run.call_args.kwargs
        assert kwargs["check"] is False


class TestScpToVps:
    """Tests for scp_to_vps()."""

    def test_dry_run_does_not_invoke_subprocess(self):
        with patch("subprocess.run") as mock_run:
            scp_to_vps("/tmp/x.yml", "/opt/y.yml", dry_run=True)
            mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_success_invokes_scp_with_host_prefix(self, mock_run, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        scp_to_vps("/tmp/src.yml", "/opt/dst.yml")
        args = mock_run.call_args[0][0]
        assert args[0] == "scp"
        assert args[1] == "/tmp/src.yml"
        assert args[2] == "vps:/opt/dst.yml"

    @patch("subprocess.run")
    def test_nonzero_exit_raises_runtimeerror(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="scp: /opt/dst.yml: Permission denied\n"
        )
        with pytest.raises(RuntimeError, match="Permission denied"):
            scp_to_vps("/tmp/x", "/opt/y")
