"""Tests for the DNSClient site-provisioner driver — defaults + resolution paths."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from fabrik.drivers.dns import DNSClient


def test_default_container_network_is_fabrik(monkeypatch):
    """Default network is 'fabrik' (not Coolify-era 'coolify').

    Regression: until 2026-06-08, the default was 'coolify', which caused
    `docker inspect site-provisioner --format '{{...coolify...}}'` to return
    an empty value (template parse error: 'no entry for key "IPAddress"') —
    breaking `fabrik vultr destroy --reverse-fleet-add` DNS unwind in a fresh
    operator environment that hadn't set the env override. site-provisioner
    is on the `fabrik` network post-Coolify migration.
    """
    monkeypatch.delenv("SITE_PROVISIONER_CONTAINER_NETWORK", raising=False)
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    client = DNSClient(api_key="test", ssh_host="vps")
    assert client._container_network == "fabrik"


def test_container_network_env_override_wins(monkeypatch):
    """Operator can override the default network via env var."""
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER_NETWORK", "some-other-net")
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    client = DNSClient(api_key="test", ssh_host="vps")
    assert client._container_network == "some-other-net"


def test_container_resolution_uses_chosen_network(monkeypatch):
    """`_resolve_container_url` injects the configured network into the
    docker-inspect template — not a hardcoded value.
    """
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER_NETWORK", "fabrik")
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    captured_cmds: list[list[str]] = []

    class _Result:
        def __init__(self, stdout: str, rc: int = 0) -> None:
            self.stdout = stdout
            self.stderr = ""
            self.returncode = rc

    def _fake_run(argv, **kwargs):
        captured_cmds.append(argv)
        joined = " ".join(argv)
        # First subprocess call: container name listing; second: inspect template
        if "docker ps" in joined:
            return _Result("site-provisioner\n")
        if "docker inspect" in joined:
            return _Result("10.0.1.26\n")
        return _Result("")

    with patch("fabrik.drivers.dns.subprocess.run", side_effect=_fake_run):
        client = DNSClient(api_key="test", ssh_host="vps")
        url = client._resolve_container_url()

    assert url == "http://10.0.1.26:8001"
    # The configured network name must appear in the inspect template — not
    # 'coolify' (which was the Coolify-era default that broke post-migration).
    inspect_cmd = " ".join(
        next((cmd for cmd in captured_cmds if "docker inspect" in " ".join(cmd)), [])
    )
    assert "fabrik" in inspect_cmd
    assert "coolify" not in inspect_cmd


# ---------------------------------------------------------------------------
# G4: delete_record idempotency when site-provisioner returns
# `500 Internal Server Error` body for "record not found".
# Live regression from the vps4 drill 2026-06-08: the second destroy against
# already-cleaned vps4 emitted `dns: error: SSH proxy returned non-JSON:
# Internal Server Error` — even though `dig` confirmed the records were
# already gone. The fix swallows the specific shape inside `delete_record`.
# ---------------------------------------------------------------------------


def test_delete_record_swallows_internal_server_error_for_idempotency(monkeypatch):
    """The not-found case (site-provisioner returns 500 plaintext) is success."""
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    client = DNSClient(api_key="test", ssh_host="vps")

    def _boom(*a, **k):
        raise RuntimeError("SSH proxy returned non-JSON: Internal Server Error")

    with patch.object(client, "_request", side_effect=_boom):
        result = client.delete_record("ocoron.com", "A", "vps4")
    assert result == {"status": "absent"}


def test_delete_record_propagates_unrelated_ssh_errors(monkeypatch):
    """Anything that isn't the 'Internal Server Error + non-JSON' shape
    must still bubble up. A real SSH failure is NOT silently swallowed."""
    monkeypatch.setenv("SITE_PROVISIONER_CONTAINER", "site-provisioner")
    client = DNSClient(api_key="test", ssh_host="vps")

    def _real_failure(*a, **k):
        raise RuntimeError("SSH proxy request failed: connection refused")

    with patch.object(client, "_request", side_effect=_real_failure):
        with pytest.raises(RuntimeError, match="connection refused"):
            client.delete_record("ocoron.com", "A", "vps4")


class TestRequestViaSsh:
    """W-6a96f699 (review P2-13): the SSH proxy's failure and timeout text."""

    KEY = "s3cr3tvalue-api-key"

    def _client(self, monkeypatch):
        monkeypatch.delenv("SITE_PROVISIONER_CONTAINER", raising=False)
        return DNSClient(api_key=self.KEY, ssh_host="vps")

    def test_failure_names_host_and_jump_and_leaks_no_secret(self, monkeypatch):
        """The remote shell echoes a broken command line — `-H "X-API-Key: …"` included — and
        `_redact` cannot mask a header; the jump named is the one the call used."""
        import os
        from unittest.mock import MagicMock

        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        client = self._client(monkeypatch)
        stderr = (
            "bash: -c: line 1: syntax error near unexpected token `)'\n"
            f'bash: -c: line 1: `curl -s -X GET -H "X-API-Key: {self.KEY}" )\'\n'
            "DB_PASSWORD=hunter2secret\n"
        )

        def run(argv, **_kw):
            os.environ["FABRIK_SSH_JUMP_VPS"] = "vps3"  # a later read would name vps3
            return MagicMock(returncode=1, stdout="", stderr=stderr)

        with patch("subprocess.run", side_effect=run) as mock_run:
            with pytest.raises(RuntimeError) as info:
                client._request_via_ssh("GET", "http://x/y")
        assert mock_run.call_args[0][0][:4] == ["ssh", "-o", "ProxyJump=vps2", "vps"]
        msg = str(info.value)
        assert "'vps'" in msg and "via jump 'vps2'" in msg and "rc=1" in msg
        assert self.KEY not in msg and "hunter2secret" not in msg
        assert "syntax error" in msg  # the cause survives the cleaning

    def test_a_timeout_carries_no_command(self, monkeypatch):
        import subprocess

        client = self._client(monkeypatch)
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)

        def run(argv, **kw):
            raise subprocess.TimeoutExpired(argv, kw.get("timeout", 30))

        with patch("subprocess.run", side_effect=run):
            with pytest.raises(subprocess.TimeoutExpired) as info:
                client._request_via_ssh("GET", "http://x/y")
        e = info.value
        assert self.KEY not in str(e) and self.KEY not in repr(e)
        assert e.__context__ is None and e.__cause__ is None
        assert e.cmd == ["ssh", "vps", "<command redacted>"]

    def test_a_timeout_names_the_jump_and_keeps_a_fractional_budget(self, monkeypatch):
        """Review C-S3/C-H4: the command-free timeout still names the jump; 0.5 s stays 0.5 s
        (int() made it 0 — an instant timeout)."""
        import subprocess

        monkeypatch.setenv("FABRIK_SSH_JUMP_VPS", "vps2")
        monkeypatch.delenv("SITE_PROVISIONER_CONTAINER", raising=False)
        client = DNSClient(api_key=self.KEY, ssh_host="vps", timeout=0.5)
        seen = {}

        def run(argv, **kw):
            seen["timeout"] = kw["timeout"]
            raise subprocess.TimeoutExpired(argv, kw["timeout"])

        with patch("subprocess.run", side_effect=run):
            with pytest.raises(subprocess.TimeoutExpired) as info:
                client._request_via_ssh("GET", "http://x/y")
        assert seen["timeout"] == 0.5
        assert info.value.cmd == ["ssh", "-o", "ProxyJump=vps2", "vps", "<command redacted>"]

    @pytest.mark.parametrize(
        "url", ["https://h/api/domains/a'; id; echo 'b", "https://h/x$(id)", 'https://h/x"; id']
    )
    def test_the_remote_command_quotes_every_word(self, url, monkeypatch):
        """Review C-H1: a `'` in a domain broke out of the hand-quoted URL and the rest ran on the
        VPS; the remote shell must see the URL, each header and the body as one word each."""
        import shlex
        from unittest.mock import MagicMock

        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        client = self._client(monkeypatch)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            client._request_via_ssh("POST", url, body={"v": "it's; $(id)"})
        words = shlex.split(mock_run.call_args[0][0][-1])
        assert words[-1] == url
        assert words[words.index("-d") + 1] == json.dumps({"v": "it's; $(id)"})
        assert f"X-API-Key: {self.KEY}" in words

    def test_a_header_value_is_one_word_whatever_it_holds(self, monkeypatch):
        """The API key comes from the environment; a `"` in it must not end the header word."""
        import shlex
        from unittest.mock import MagicMock

        monkeypatch.delenv("SITE_PROVISIONER_CONTAINER", raising=False)
        monkeypatch.delenv("FABRIK_SSH_JUMP_VPS", raising=False)
        key = 'k"; id; echo "'
        client = DNSClient(api_key=key, ssh_host="vps")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
            client._request_via_ssh("GET", "https://h/x")
        assert f"X-API-Key: {key}" in shlex.split(mock_run.call_args[0][0][-1])

    def test_a_non_json_reply_leaks_no_secret(self, monkeypatch):
        """Review C-H3: an error page echoing the request reached the RuntimeError uncleaned."""
        from unittest.mock import MagicMock

        client = self._client(monkeypatch)
        page = f"<html>X-API-Key: {self.KEY} DB_PASSWORD=hunter2secret</html>"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=page, stderr="")
            with pytest.raises(RuntimeError) as info:
                client._request_via_ssh("GET", "http://x/y")
        assert self.KEY not in str(info.value) and "hunter2secret" not in str(info.value)
        assert "non-JSON" in str(info.value)
