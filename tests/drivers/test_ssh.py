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
        assert args == ["scp", "--", "/tmp/src.yml", "vps:/opt/dst.yml"]

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
            assert mock_run.call_args[0][0] == ["scp", "--", "/tmp/a", "vps:/opt/b"]

    @patch("subprocess.run")
    def test_jump_inserted_for_its_alias_only(self, mock_run, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ssh("true")
        assert mock_run.call_args[0][0] == ["ssh", "-o", "ProxyJump=vps2", "vps", "true"]
        scp_to_vps("/tmp/a", "/opt/b")
        assert mock_run.call_args[0][0] == [
            "scp",
            "-o",
            "ProxyJump=vps2",
            "--",
            "/tmp/a",
            "vps:/opt/b",
        ]
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

    def test_failure_text_names_the_jump_the_call_used(self, monkeypatch):
        """One read per call: an env change mid-call never makes the message name another jump."""
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")

        def run(argv, **_kw):
            monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps3")
            return MagicMock(returncode=255, stdout="", stderr="boom")

        with patch("subprocess.run", side_effect=run):
            with pytest.raises(RuntimeError, match="via jump 'vps2'"):
                ssh("true")
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        with patch("subprocess.run", side_effect=run):
            with pytest.raises(RuntimeError, match="via jump 'vps2'"):
                scp_to_vps("/tmp/a", "/opt/b")

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
            mock_run.return_value = MagicMock(returncode=0, stdout="{}\n200", stderr="")
            assert audit._ssh_check("true")[0] is True
            assert mock_run.call_args[0][0][:4] == ["ssh", "-o", "ProxyJump=vps2", "vps"]
            client = DNSClient(api_key="t", ssh_host="vps")
            client._request_via_ssh("GET", "http://x/y")
            assert mock_run.call_args[0][0][:5] == ["ssh", "-T", "-o", "ProxyJump=vps2", "vps"]
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


_HOSTILE_HOSTS = [
    "",
    "-oProxyCommand=x",
    "x@-J",
    "a@b@c",
    "a b",
    "a;b",
    "$(x)",
    "a\nb",
    "vps:22",
    "ssh://vps",
    "vps\n",  # a `$`-anchored match would accept it (review A-S2)
    "2001:db8::1",  # an IPv6 literal: name the host by an alias
]
_VALID_HOSTS = ["vps", "deploy@vps", "10.0.0.1", "vps-2.x_y"]


class TestSshHostAlias:
    """W-6a96f699 (review P1-08): the host from FABRIK_VPS_SSH_HOST / FABRIK_AUDIT_VPS lands in ssh's
    argv, so it must be an ssh alias — the `[user@]host` half of the ProxyJump hop grammar."""

    @pytest.mark.parametrize("host", _VALID_HOSTS)
    def test_an_alias_reaches_the_argv(self, host, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", host)
        monkeypatch.delenv(ssh_mod.jump_env_name(host), raising=False)
        assert ssh_mod.is_alias(host)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            ssh("true")
            assert mock_run.call_args[0][0] == ["ssh", host, "true"]
            scp_to_vps("/tmp/a", "/tmp/b")
            assert mock_run.call_args[0][0] == ["scp", "--", "/tmp/a", f"{host}:/tmp/b"]

    @pytest.mark.parametrize("host", _HOSTILE_HOSTS)
    def test_a_non_alias_never_reaches_a_subprocess(self, host, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", host)
        assert not ssh_mod.is_alias(host)
        with patch("subprocess.run") as mock_run:
            with pytest.raises(ssh_mod.SshHostError, match="FABRIK_VPS_SSH_HOST"):
                ssh("true")
            with pytest.raises(ssh_mod.SshHostError, match="FABRIK_VPS_SSH_HOST"):
                scp_to_vps("/tmp/a", "/tmp/b")
            mock_run.assert_not_called()

    def test_the_refusal_is_never_read_as_an_ssh_failure(self):
        """`except RuntimeError` sites read an ssh failure as "absent" (destroyer `not_found`,
        `find_existing` → None); a bad host must pass through them, like JumpConfigError."""
        assert issubclass(ssh_mod.SshHostError, ValueError)
        assert not issubclass(ssh_mod.SshHostError, RuntimeError)

    def test_a_dry_run_checks_nothing_and_runs_nothing(self, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "-oProxyCommand=x")
        with patch("subprocess.run") as mock_run:
            assert ssh("true", dry_run=True) == ""
            mock_run.assert_not_called()

    @pytest.mark.parametrize("host", _HOSTILE_HOSTS)
    def test_the_audit_probe_refuses_a_non_alias_without_raising(self, host, monkeypatch):
        from fabrik import audit

        monkeypatch.setenv("FABRIK_AUDIT_VPS", host)
        with patch("subprocess.run") as mock_run:
            ok, msg = audit._ssh_check("true")
            mock_run.assert_not_called()
        assert ok is False and "FABRIK_AUDIT_VPS" in msg and "not an ssh alias" in msg

    def test_a_user_qualified_alias_takes_its_hosts_jump(self, monkeypatch):
        """Review A-H1: `deploy@vps` keyed FABRIK_SSH_JUMP_DEPLOY_VPS, so the jump set for `vps`
        was ignored and ssh took the dead direct path in silence."""
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "deploy@vps")
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        assert ssh_mod.jump_env_name("deploy@vps") == "FABRIK_SSH_JUMP_VPS"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            ssh("true")
            assert mock_run.call_args[0][0] == ["ssh", "-o", "ProxyJump=vps2", "deploy@vps", "true"]

    def test_a_timeout_names_the_jump_it_went_through(self, monkeypatch):
        """Review C-S3: a dead jump times out; the command-free TimeoutExpired still says how."""
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["x"], 5)):
            with pytest.raises(subprocess.TimeoutExpired) as info:
                ssh("echo DB_PASSWORD=hunter2secret", timeout=5)
        assert info.value.cmd == ["ssh", "-o", "ProxyJump=vps2", "vps", "<command redacted>"]
        assert "hunter2secret" not in str(info.value)


class TestEmptyStderrAndScpOptions:
    """W-894fdc5f: scp reads a local path starting with `-` as an option without `--`; an empty
    stderr read as a dangling `failed (rc=N): `."""

    def test_scp_ends_options_before_the_local_path(self, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            scp_to_vps("-oProxyCommand=x", "/opt/b")
        assert mock_run.call_args[0][0] == ["scp", "--", "-oProxyCommand=x", "vps:/opt/b"]

    @pytest.mark.parametrize("call", ["ssh", "scp"])
    def test_an_empty_stderr_says_so(self, call, monkeypatch):
        monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=255, stdout="", stderr="  ")
            with pytest.raises(RuntimeError, match=r"failed \(rc=255\): no stderr$"):
                ssh("true") if call == "ssh" else scp_to_vps("/a", "/b")


@pytest.mark.parametrize("call", ["ssh", "scp"])
def test_ssh_and_scp_failures_carry_stderr_on_one_line(call, monkeypatch):
    """W-9a560686: a CR/LF in ssh's stderr split the RuntimeError, so the remote side could forge a log line."""
    from fabrik.drivers.ssh import scp_to_vps, ssh

    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
    hostile = "denied TOKEN=abc\r\nINJECTED API_TOKEN=hunter2secret café\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=255, stdout="", stderr=hostile)
        with pytest.raises(RuntimeError) as info:
            ssh("true") if call == "ssh" else scp_to_vps("/tmp/a", "/opt/b")
    msg = str(info.value)
    assert len(msg.splitlines()) == 1 and "TOKEN=<redacted>\\r\\nINJECTED" in msg, repr(msg)
    assert "hunter2secret" not in msg and "café" in msg


# W-5597922e: subprocess.run(text=True) decoded strictly with the LOCALE codec, before the driver read
# the return code, so a byte a person typed into a VPS .env raised UnicodeDecodeError (a ValueError the
# RuntimeError-catching callers let through), carrying the byte and, in `.object`, the whole output.
def _decoding_run(stdout: bytes, stderr: bytes = b"", rc: int = 0):
    """A `subprocess.run` stand-in that decodes as subprocess does: `text`/`encoding`/`errors`, else the
    locale codec — so the driver's own decode choice is what the test exercises."""
    import locale

    def run(argv, **kw):
        out, err = stdout, stderr
        if kw.get("text") or kw.get("encoding") or kw.get("errors"):
            codec = kw.get("encoding") or locale.getpreferredencoding(False)
            errors = kw.get("errors") or "strict"
            out, err = stdout.decode(codec, errors), stderr.decode(codec, errors)
        return subprocess.CompletedProcess(argv, rc, out, err)

    return run


def test_an_undecodable_answer_is_a_runtime_error_without_the_bytes(monkeypatch):
    monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    import traceback

    from fabrik.drivers.ssh import UndecodableAnswerError

    with patch("subprocess.run", _decoding_run(b"TOKEN=s3cr\xe9t\n")):
        with pytest.raises(UndecodableAnswerError) as info:
            ssh("sudo cat /opt/x/.env")
    msg = str(info.value)
    assert isinstance(info.value, RuntimeError)
    assert "'vps'" in msg and "not valid UTF-8" in msg
    assert "s3cr" not in msg and "0xe9" not in msg and "\\xe9" not in msg
    assert info.value.__cause__ is None and info.value.__context__ is None
    # nor does the raising frame keep the output alive for a locals-capturing reporter
    frames = [
        f for f, _ in traceback.walk_tb(info.value.__traceback__) if f.f_code.co_name == "ssh"
    ]
    assert frames and not any("s3cr" in repr(v) for f in frames for v in f.f_locals.values())


@pytest.mark.parametrize("call", ["ssh", "scp"])
def test_undecodable_stderr_never_hides_the_exit_code(call, monkeypatch):
    monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)

    def go():
        return ssh("cat /opt/x/.env") if call == "ssh" else scp_to_vps("/tmp/a", "/opt/b")

    failed = _decoding_run(b"", b"cat: /opt/x/.env: Datei nicht gefunden \xe9 TOKEN=ab\xe9cd", rc=2)
    with patch("subprocess.run", failed):
        with pytest.raises(
            RuntimeError, match=r"failed \(rc=2\): 'cat: /opt/x/\.env: Datei nicht gefunden"
        ) as info:
            go()
    msg = str(info.value)
    # the escaped byte is SHOWN, never left as a lone surrogate a UTF-8 log sink cannot encode,
    # and the secret mask still covers a value holding one
    assert "\\xe9" in msg and "TOKEN=<redacted>" in msg and "cd" not in msg.split("TOKEN=")[1]
    msg.encode("utf-8")
    with patch("subprocess.run", _decoding_run(b"ok\n", b"warning: caf\xe9", rc=0)):
        assert go() == ("ok" if call == "ssh" else None)


_LOCALE_PROBE = """
import sys
sys.path.insert(0, sys.argv[1])
from fabrik.drivers.ssh import ssh
sys.stdout.buffer.write(ssh("cat /opt/x/name").encode("utf-8"))
"""


def test_utf8_output_decodes_under_an_ascii_locale(tmp_path):
    """The real driver, in a child Python whose locale codec is ASCII, over a fake `ssh` first on PATH."""
    import os
    import sys
    from pathlib import Path

    fake = tmp_path / "ssh"
    fake.write_text("#!/bin/sh\nprintf 'caf\\303\\251\\n'\n")
    fake.chmod(0o755)
    src = str(Path(__file__).resolve().parents[2] / "src")
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("LC_", "LANG", "PYTHONUTF8", "FABRIK_SSH_JUMP_"))
    }
    env.update(
        LC_ALL="C",
        PYTHONCOERCECLOCALE="0",
        PYTHONUTF8="0",
        FABRIK_VPS_SSH_HOST="vps",
        PATH=f"{tmp_path}{os.pathsep}{env.get('PATH', '')}",
    )
    run = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", _LOCALE_PROBE, src],
        env=env,
        capture_output=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr.decode("utf-8", "replace")[-500:]
    assert run.stdout.decode("utf-8") == "café"


def test_an_undecodable_env_read_fails_the_read_and_persist_stays_open(monkeypatch, caplog):
    from fabrik.orchestrator import deployer_ssh
    from fabrik.orchestrator.exceptions import DeployError

    monkeypatch.setenv("FABRIK_VPS_SSH_HOST", "vps")
    monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
    probe, cat = _decoding_run(b"present\n"), _decoding_run(b"TOKEN=s3cr\xe9t\n")

    def run(argv, **kw):
        return (probe if "echo present" in argv[-1] else cat)(argv, **kw)

    writes: list[str] = []
    monkeypatch.setattr(deployer_ssh, "_write_file_to_vps", lambda *a: writes.append(a[1]))
    with patch("subprocess.run", run):
        with pytest.raises(DeployError, match=r"cannot read /opt/x/\.env: .*not valid UTF-8"):
            deployer_ssh._read_env_file("/opt/x", ssh)
        deployer_ssh._persist_git_sha("x", "a" * 40, ssh)
    assert writes == []
    assert "GIT_SHA not updated for x" in caplog.text and "s3cr" not in caplog.text
