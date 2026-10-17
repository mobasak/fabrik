"""The quota-dashboard tests' shared isolation: no network, no real home (plan 2026-10-17-plan-1).

Every `tests/test_quota_dashboard*.py` file imports `no_network` (an autouse fixture: importing it
into a test module is what activates it there — no repo-wide conftest change) and every loader of
`scripts/sysadmin/quota_dashboard.py` calls `isolate` before the import and `after_load` after it.

- `no_network` cuts the network at the socket: a connect or a name lookup off loopback is refused
  AND recorded, and the test that tried one fails at teardown — even when the code under test caught
  the refusal (every provider probe fails soft, which is how a live call to Brave went unnoticed).
- `isolate` points HOME at an empty directory, removes the provider keys and every proxy variable
  (a loopback proxy would carry a provider call past the guard: urllib connects to 127.0.0.1 and the
  proxy resolves the host), and sets NO_PROXY="*".
- `after_load` empties the module's MCP config list — the repo's own `.mcp.json` may carry a real key.

Cobra check (D-253): the cheapest way to pass "no test reaches the network" is a guard that only
covers the file it lives in; this module is the one copy, and
`test_every_quota_dashboard_test_file_activates_the_network_guard` (tests/test_quota_dashboard.py)
fails when any `test_quota_dashboard*.py` file stops importing `no_network`.
"""

# AFTER-EDIT: none

from __future__ import annotations

import socket
from pathlib import Path

import pytest

PROVIDER_KEYS = ("BRAVE_API_KEY", "FIRECRAWL_API_KEY", "EXA_API_KEY", "OPENROUTER_API_KEY")
PROXY_VARS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy")
NET_DENIED: list[str] = []


def isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Before a dashboard module is imported: an empty HOME, no provider key, no proxy."""
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    for var in PROVIDER_KEYS + PROXY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv("no_proxy", "*")


def after_load(mod, monkeypatch: pytest.MonkeyPatch) -> None:
    """After the import: the module reads no MCP config (the repo's `.mcp.json` included)."""
    monkeypatch.setattr(mod, "_MCP_CONFIGS", ())


def loopback(address: object) -> bool:
    if not isinstance(address, tuple):  # an AF_UNIX path: never the network
        return True
    host = str(address[0])
    return host in ("localhost", "::1") or host.startswith("127.")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_lookup = socket.getaddrinfo

    def connect(self, address, *a, **k):
        if not loopback(address):
            NET_DENIED.append(repr(address))
            raise OSError(f"test network guard: no connect to {address!r}")
        return real_connect(self, address, *a, **k)

    def connect_ex(self, address, *a, **k):
        if not loopback(address):
            NET_DENIED.append(repr(address))
            raise OSError(f"test network guard: no connect to {address!r}")
        return real_connect_ex(self, address, *a, **k)

    def lookup(host, *a, **k):  # a name lookup is network traffic too (and names the provider)
        if host is not None and not loopback((host, 0)):
            NET_DENIED.append(f"lookup {host!r}")
            raise OSError(f"test network guard: no lookup of {host!r}")
        return real_lookup(host, *a, **k)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    del NET_DENIED[:]
    yield
    denied, NET_DENIED[:] = list(NET_DENIED), []
    assert denied == [], f"the test opened a non-loopback socket: {denied}"
