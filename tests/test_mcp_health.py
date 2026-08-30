# AFTER-EDIT: scripts/sysadmin/mcp_health.py | none
"""D-033 forcing pair — mcp_health probes the ASSIGNED set (repo .mcp.json) for real
liveness (initialize handshake / HTTP reach), reports assigned-vs-live, always exit 0."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts/sysadmin/mcp_health.py"
_spec = importlib.util.spec_from_file_location("mcp_health", _SCRIPT)
health = importlib.util.module_from_spec(_spec)
sys.modules["mcp_health"] = health
_spec.loader.exec_module(health)

FAKE_OK_SERVER = (
    "import sys,json\n"
    "line=sys.stdin.readline()\n"
    "req=json.loads(line)\n"
    "print(json.dumps({'jsonrpc':'2.0','id':req['id'],'result':{'ok':True}}),flush=True)\n"
)


def _mk(tmp_path: Path, servers: dict) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".mcp.json").write_text(json.dumps({"mcpServers": servers}))
    return repo


def test_live_stdio_server_reports_connected(tmp_path):
    repo = _mk(tmp_path, {"fake-ok": {"type": "stdio", "command": sys.executable,
                                      "args": ["-c", FAKE_OK_SERVER]}})
    report = health.check(repo, timeout=8)
    assert report["fake-ok"] == "CONNECTED"


def test_dead_command_reports_dead(tmp_path):
    repo = _mk(tmp_path, {"corpse": {"type": "stdio", "command": "/bin/false", "args": []}})
    report = health.check(repo, timeout=5)
    assert report["corpse"] == "DEAD"


def test_unreachable_http_reports_dead(tmp_path):
    repo = _mk(tmp_path, {"dead-http": {"type": "http", "url": "http://127.0.0.1:9/mcp"}})
    report = health.check(repo, timeout=5)
    assert report["dead-http"] == "DEAD"


def test_no_mcp_json_and_exit_zero_always(tmp_path, capsys):
    bare = tmp_path / "bare"
    bare.mkdir()
    rc = health.main(["--repo", str(bare)])
    assert rc == 0, "advisory contract: NEVER blocks"
    assert "no .mcp.json" in capsys.readouterr().out
