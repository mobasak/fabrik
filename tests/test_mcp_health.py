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


# ── the false-verdict classes (measured live 2026-08-30: mcp_health said 4/15 NOT
#    live — grafana, maestro, media-engine, serena — while `claude mcp list` said
#    15/15 ✔ Connected) ───────────────────────────────────────────────────────────

# Answers the handshake only after a delay, and EXITS when stdin closes — the
# maestro (JVM) shape the docstring records as a known false DEAD.
FAKE_SLOW_SERVER = (
    "import sys,json,time\n"
    "line=sys.stdin.readline()\n"
    "req=json.loads(line)\n"
    "time.sleep({delay})\n"
    "print(json.dumps({{'jsonrpc':'2.0','id':req['id'],'result':{{'ok':True}}}}),flush=True)\n"
    "sys.exit(0)\n"
)


def test_slow_but_live_server_is_connected_not_timeout(tmp_path):
    """A server that answers within Claude's real 30s connect budget is LIVE.

    Regression for the false-TIMEOUT class: the probe used to wait for process EOF
    via communicate(), so a server slower than the probe's own (shorter) timeout was
    reported TIMEOUT even though Claude connects it fine.
    """
    repo = _mk(tmp_path, {"slow": {"type": "stdio", "command": sys.executable,
                                   "args": ["-c", FAKE_SLOW_SERVER.format(delay=2)]}})
    report = health.check(repo, timeout=20)
    assert report["slow"] == "CONNECTED", "a slow-but-answering server is not dead"


def test_server_that_exits_after_answering_is_connected(tmp_path):
    """The frame is the evidence — not the exit code, not waiting for EOF."""
    repo = _mk(tmp_path, {"exiter": {"type": "stdio", "command": sys.executable,
                                     "args": ["-c", FAKE_SLOW_SERVER.format(delay=0)]}})
    assert health.check(repo, timeout=20)["exiter"] == "CONNECTED"


def test_skipped_is_not_counted_as_not_live(tmp_path, capsys):
    """A docker-run entry is deliberately NOT PROBED — reporting it as 'NOT live' is
    asserting a negative from a non-measurement (denominator honesty). It must be
    reported as unprobed, and must not inflate the NOT-live count."""
    repo = _mk(tmp_path, {
        "dockerish": {"type": "stdio", "command": "docker", "args": ["run", "--rm", "-i", "x"]},
        "fake-ok": {"type": "stdio", "command": sys.executable, "args": ["-c", FAKE_OK_SERVER]},
    })
    rc = health.main(["--repo", str(repo), "--timeout", "20"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1/2 assigned server(s) NOT live" not in out, "SKIPPED must not count as NOT live"
    assert "NOT live" not in out, "nothing here is provably dead"
    assert "unprobed" in out.lower(), "the skip must still be VISIBLE, not silently green"


def test_real_dead_server_still_reported_with_skip_present(tmp_path, capsys):
    """The skip fix must not mute a genuine failure (fail-open, not fail-blind)."""
    repo = _mk(tmp_path, {
        "dockerish": {"type": "stdio", "command": "docker", "args": ["run", "--rm", "-i", "x"]},
        "corpse": {"type": "stdio", "command": "/bin/false", "args": []},
    })
    health.main(["--repo", str(repo), "--timeout", "10"])
    out = capsys.readouterr().out
    # the denominator is what was actually PROBED (1), never what was assigned (2)
    assert "1/1 probed server(s) NOT live" in out and "corpse" in out
    assert "UNPROBED" in out, "the skip stays visible on its own line, never silently green"
    assert "dockerish" not in out.split("NOT live")[1][:60], "the skip is not one of the dead"


# Models the maestro shape: dies the moment stdin reaches EOF, and needs a beat
# before it can answer. Measured live 2026-08-30: DEAD at timeout=8s AND at 45s,
# so no budget increase could ever have fixed it — only keeping stdin open.
FAKE_STDIN_SENSITIVE_SERVER = (
    "import sys,json,time,threading,os\n"
    "line=sys.stdin.readline()\n"
    "req=json.loads(line)\n"
    "def _die_on_eof():\n"
    "    sys.stdin.read()\n"          # blocks while stdin stays OPEN; returns at EOF
    "    os._exit(1)\n"               # exited without ever answering
    "threading.Thread(target=_die_on_eof,daemon=True).start()\n"
    "time.sleep(1.5)\n"
    "print(json.dumps({'jsonrpc':'2.0','id':req['id'],'result':{'ok':True}}),flush=True)\n"
)


def test_server_that_dies_on_stdin_close_is_connected(tmp_path):
    """Regression for the maestro false-DEAD: the probe must NOT close stdin.

    Closing stdin (what communicate() does) kills this class of server before it
    answers, so the probe manufactured a death Claude never sees. Claude keeps the
    stream open; so must we.
    """
    repo = _mk(tmp_path, {"jvm-ish": {"type": "stdio", "command": sys.executable,
                                      "args": ["-c", FAKE_STDIN_SENSITIVE_SERVER]}})
    assert health.check(repo, timeout=20)["jvm-ish"] == "CONNECTED"
