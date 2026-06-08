"""Tests for the DNSClient site-provisioner driver — defaults + resolution paths."""

from __future__ import annotations

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
