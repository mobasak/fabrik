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
    def test_timeout_never_carries_the_command(self, mock_run):
        """A TimeoutExpired's str/repr hold its argv; `_run_sql` puts a base64 SQL batch
        (``ALTER ROLE … PASSWORD``) there, and registrars log str(e) (T04 fixup O1)."""
        import base64

        payload = base64.b64encode(b"ALTER ROLE x_app PASSWORD 'hunter2secret';").decode()
        cmd = f"echo {payload} | base64 -d | sudo docker exec -i pg psql PASSWORD=hunter2secret"
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ssh", "vps", cmd], timeout=5)
        with pytest.raises(subprocess.TimeoutExpired) as info:
            ssh(cmd, timeout=5)
        exc = info.value
        surfaces = [str(exc), repr(exc), repr(exc.cmd), str(exc.__cause__), str(exc.__context__)]
        for text in surfaces:
            assert "hunter2secret" not in text
            assert payload not in text
        assert exc.__suppress_context__ is True
        assert exc.timeout == 5

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


class TestJump:
    """The opt-in per-host jump, FABRIK_SSH_JUMP_<ALIAS> (W-2b657bee): inert when unset,
    `-o ProxyJump=<v>` before the host when set, fail closed on a value outside the grammar."""

    @patch("subprocess.run")
    def test_unset_or_empty_leaves_argv_unchanged(self, mock_run, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        for value in (None, ""):
            if value is None:
                monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
            else:
                monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", value)
            ssh("true")
            assert mock_run.call_args[0][0] == ["ssh", "vps", "true"]
            scp_to_vps("/tmp/a", "/opt/b")
            assert mock_run.call_args[0][0] == ["scp", "/tmp/a", "vps:/opt/b"]

    @patch("subprocess.run")
    def test_jump_inserted_for_its_alias_only(self, mock_run, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ssh("true")
        assert mock_run.call_args[0][0] == ["ssh", "-o", "ProxyJump=vps2", "vps", "true"]
        scp_to_vps("/tmp/a", "/opt/b")
        assert mock_run.call_args[0][0] == ["scp", "-o", "ProxyJump=vps2", "/tmp/a", "vps:/opt/b"]
        mock_run.return_value = MagicMock(returncode=255, stdout="", stderr="boom")
        with pytest.raises(RuntimeError, match="via jump 'vps2'"):
            ssh("true")
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="write failed: API_TOKEN=hunter2secret"
        )
        with pytest.raises(RuntimeError, match="via jump 'vps2'") as info:
            scp_to_vps("/tmp/a", "/opt/b")
        assert "hunter2secret" not in str(info.value)
        # another alias's variable never applies to this one
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps2")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ssh("true")
        assert mock_run.call_args[0][0] == ["ssh", "vps2", "true"]
        assert ssh_mod.jump_env_name("vps-1.x") == "FABRIK_SSH_JUMP_VPS_1_X"

    @pytest.mark.parametrize(
        "value",
        [
            "-oProxyCommand=x",
            "a b",
            "a;b",
            ",a",
            "a,",
            "a,,b",
            "@h",
            "h:",
            "h:0",
            "a,-oX",
            "x@-h",
            "[::1]",
            "none",
            "a,NONE",
            "vps2\n",
            "ssh://u@h:22",
            "h:65536",
            "h:99999",
            "none:22",
            "a,none:22",
        ],
    )
    @patch("subprocess.run")
    def test_invalid_jump_fails_closed(self, mock_run, value, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", value)
        with pytest.raises(ssh_mod.JumpConfigError, match="FABRIK_SSH_JUMP_VPS"):
            ssh("true")
        with pytest.raises(ssh_mod.JumpConfigError, match="FABRIK_SSH_JUMP_VPS"):
            scp_to_vps("/tmp/a", "/opt/b")
        mock_run.assert_not_called()

    @pytest.mark.parametrize(
        "value", ["vps2", "ozgur@96.9.214.128:2222", "a,b", "h.example.com", "h:65535", "h:1"]
    )
    def test_valid_jump_values_accepted(self, value, monkeypatch):
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", value)
        assert ssh_mod.jump_args("vps") == ["-o", f"ProxyJump={value}"]

    def test_raw_argv_callers_honour_the_jump(self, monkeypatch):
        from fabrik import audit
        from fabrik.drivers.dns import DNSClient

        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        monkeypatch.delenv("FABRIK_AUDIT_VPS", raising=False)
        monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
        monkeypatch.delenv("SITE_PROVISIONER_INTERNAL_URL", raising=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            assert audit._ssh_check("true")[0] is True
            assert mock_run.call_args[0][0][:4] == ["ssh", "-o", "ProxyJump=vps2", "vps"]
            client = DNSClient(api_key="t", ssh_host="vps")
            client._request_via_ssh("GET", "http://x/y")
            assert mock_run.call_args[0][0][:4] == ["ssh", "-o", "ProxyJump=vps2", "vps"]
            mock_run.return_value = MagicMock(
                returncode=0, stdout="site-provisioner-1\n", stderr=""
            )
            client._resolve_container_url()
            for call in mock_run.call_args_list[-2:]:
                assert call[0][0][:4] == ["ssh", "-o", "ProxyJump=vps2", "vps"]
        # a bad value is not swallowed into dns's public-URL fallback
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "-oProxyCommand=x")
        with patch("subprocess.run") as mock_run:
            with pytest.raises(ValueError):
                DNSClient(api_key="t", ssh_host="vps")._resolve_container_url()
            mock_run.assert_not_called()
            ok, msg = audit._ssh_check("true")
            assert ok is False and "FABRIK_SSH_JUMP_VPS" in msg
