# AFTER-EDIT: scripts/sysadmin/mcp_health.py | none
"""D-033 forcing pair — mcp_health probes the ASSIGNED set (repo .mcp.json) for real
liveness (initialize handshake / HTTP reach), reports assigned-vs-live, always exit 0."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts/sysadmin/mcp_health.py"
_spec = importlib.util.spec_from_file_location("mcp_health", _SCRIPT)
health = importlib.util.module_from_spec(_spec)
sys.modules["mcp_health"] = health
_spec.loader.exec_module(health)


@pytest.fixture(autouse=True)
def _no_box_unit_dir(tmp_path, monkeypatch):
    """`main()` reads the emitter's unit dir: never the box's /etc/systemd/system. An empty dir by default —
    a test that wants units installed sets its own."""
    monkeypatch.setenv("FABRIK_SYSTEMD_UNIT_DIR", str(tmp_path / "unit-dir-unset"))


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
    repo = _mk(
        tmp_path,
        {"fake-ok": {"type": "stdio", "command": sys.executable, "args": ["-c", FAKE_OK_SERVER]}},
    )
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
    repo = _mk(
        tmp_path,
        {
            "slow": {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-c", FAKE_SLOW_SERVER.format(delay=2)],
            }
        },
    )
    report = health.check(repo, timeout=20)
    assert report["slow"] == "CONNECTED", "a slow-but-answering server is not dead"


def test_server_that_exits_after_answering_is_connected(tmp_path):
    """The frame is the evidence — not the exit code, not waiting for EOF."""
    repo = _mk(
        tmp_path,
        {
            "exiter": {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-c", FAKE_SLOW_SERVER.format(delay=0)],
            }
        },
    )
    assert health.check(repo, timeout=20)["exiter"] == "CONNECTED"


def test_skipped_is_not_counted_as_not_live(tmp_path, capsys):
    """A docker-run entry is deliberately NOT PROBED — reporting it as 'NOT live' is
    asserting a negative from a non-measurement (denominator honesty). It must be
    reported as unprobed, and must not inflate the NOT-live count."""
    repo = _mk(
        tmp_path,
        {
            "dockerish": {"type": "stdio", "command": "docker", "args": ["run", "--rm", "-i", "x"]},
            "fake-ok": {"type": "stdio", "command": sys.executable, "args": ["-c", FAKE_OK_SERVER]},
        },
    )
    rc = health.main(["--repo", str(repo), "--timeout", "20"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1/2 assigned server(s) NOT live" not in out, "SKIPPED must not count as NOT live"
    assert "NOT live" not in out, "nothing here is provably dead"
    assert "unprobed" in out.lower(), "the skip must still be VISIBLE, not silently green"


def test_real_dead_server_still_reported_with_skip_present(tmp_path, capsys):
    """The skip fix must not mute a genuine failure (fail-open, not fail-blind)."""
    repo = _mk(
        tmp_path,
        {
            "dockerish": {"type": "stdio", "command": "docker", "args": ["run", "--rm", "-i", "x"]},
            "corpse": {"type": "stdio", "command": "/bin/false", "args": []},
        },
    )
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
    "    sys.stdin.read()\n"  # blocks while stdin stays OPEN; returns at EOF
    "    os._exit(1)\n"  # exited without ever answering
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
    repo = _mk(
        tmp_path,
        {
            "jvm-ish": {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-c", FAKE_STDIN_SENSITIVE_SERVER],
            }
        },
    )
    assert health.check(repo, timeout=20)["jvm-ish"] == "CONNECTED"


# ── W-3350006b: the key check — a connected server whose provider refuses its key is NOT live ─────────────────
import contextlib  # noqa: E402
import http.server  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402

EXA_REFUSED = b'{"requestId":"r1","error":"Invalid API key","tag":"INVALID_API_KEY"}'
FIRECRAWL_REFUSED = b'{"success":false,"error":"Unauthorized: Invalid token"}'


@pytest.fixture(autouse=True)
def _no_real_provider(monkeypatch):
    """Every test in this file: no proxy, no box key, and both probe URLs pointed at a closed local port, so no test
    can present a real key to a real provider (a test below repoints a URL at its own stand-in)."""
    import os

    for var in list(os.environ):
        if var.lower().endswith("_proxy"):
            monkeypatch.delenv(var, raising=False)
    for probe in health._AUTH_PROBES.values():
        monkeypatch.delenv(probe["env"], raising=False)
        monkeypatch.setitem(probe, "url", "http://127.0.0.1:9/closed")


@contextlib.contextmanager
def _provider(status, body=b"", *, ctype="application/json", trickle=0.0, location=None):
    """A stand-in provider on 127.0.0.1: answers every GET with ``status`` and ``body``; yields (base url, seen), where
    ``seen`` lists each request's (path, the auth headers it carried). ``trickle`` sends the body one byte per that
    many seconds — each read returns in time, so only a wall-clock deadline can cut it."""
    seen = []
    stop = threading.Event()  # set on exit: a trickling handler stops instead of outliving its test

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 — http.server's own name
            seen.append(
                (self.path, self.headers.get("x-api-key"), self.headers.get("authorization"))
            )
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if location:
                self.send_header("Location", location)
            self.end_headers()
            if not trickle:
                self.wfile.write(body)
                return
            for i in range(len(body)):
                if stop.wait(trickle):
                    return
                self.wfile.write(body[i : i + 1])
                self.wfile.flush()

        def log_message(self, *_a):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", seen
    finally:
        stop.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _keyed(tmp_path, name, *, key="k-test-0123456789", command=None):
    """A repo whose one server, named ``name``, answers the handshake and carries ``key`` in its env."""
    entry = {
        "type": "stdio",
        "command": command or sys.executable,
        "args": [] if command else ["-c", FAKE_OK_SERVER],
    }
    if key is not None:
        entry["env"] = {health._AUTH_PROBES[name]["env"]: key}
    return _mk(tmp_path, {name: entry})


@pytest.mark.parametrize(
    "name,status,body,word",
    [
        ("exa", 401, EXA_REFUSED, "HTTP 401"),
        ("firecrawl", 401, FIRECRAWL_REFUSED, "HTTP 401"),
        ("firecrawl", 402, b'{"success":false,"error":"Payment required"}', "HTTP 402"),
        (
            "exa",
            402,
            b'{"requestId":"r2","error":"No credits","tag":"NO_MORE_CREDITS"}',
            "HTTP 402",
        ),
    ],
)
def test_a_refused_key_reads_unauthorized(name, status, body, word, tmp_path, monkeypatch):
    """The 2026-10-07 incident (mail 01M49YT4T5): the transport connects, the provider refuses the key."""
    with _provider(status, body) as (base, seen):
        monkeypatch.setitem(health._AUTH_PROBES[name], "url", base + "/probe")
        report = health.check(_keyed(tmp_path, name), timeout=8)
    assert report[name].startswith(f"UNAUTHORIZED ({word}")
    assert len(seen) == 1, "exactly one call presents the key"


@pytest.mark.parametrize(
    "status,body,ctype,reason",
    [
        (
            403,
            b"<!DOCTYPE html><title>Attention Required! | Cloudflare</title>",
            "text/html",
            "HTTP 403",
        ),
        (401, b"<html>captive portal</html>", "text/html", "HTTP 401"),
        (401, b'{"message":"gateway says no"}', "application/json", "HTTP 401"),
        (401, b"not json at all", "application/json", "HTTP 401"),
        (503, b'{"success":false,"error":"overloaded"}', "application/json", "HTTP 503"),
    ],
    ids=["cloudflare-html-403", "html-401", "gateway-json-401", "fake-json-401", "json-503"],
)
def test_a_network_or_gateway_answer_is_unverified(
    status, body, ctype, reason, tmp_path, monkeypatch
):
    """What a blocked egress, a portal or an interposed gateway sends is never a refused key."""
    notes: dict = {}
    with _provider(status, body, ctype=ctype) as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES["firecrawl"], "url", base + "/probe")
        report = health.check(_keyed(tmp_path, "firecrawl"), timeout=8, notes=notes)
    assert report["firecrawl"] == "CONNECTED"
    assert notes["firecrawl"] == f"unverified ({reason})"


@pytest.mark.parametrize(
    "name,body,note",
    [
        ("firecrawl", b'{"success":true,"data":{"remaining_credits":420}}', "accepted"),
        (
            "firecrawl",
            b'{"success":true,"data":{"remaining_credits":0}}',
            "accepted (0 credits left)",
        ),
        ("exa", b'{"data":[],"hasMore":false,"nextCursor":null}', "accepted"),
    ],
)
def test_an_accepted_key_stays_connected(name, body, note, tmp_path, monkeypatch):
    notes: dict = {}
    with _provider(200, body) as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES[name], "url", base + "/probe")
        report = health.check(_keyed(tmp_path, name), timeout=8, notes=notes)
    assert report[name] == "CONNECTED" and notes[name] == note


def test_a_redirect_never_forwards_the_key(tmp_path, monkeypatch):
    """urllib's default redirect handler re-sends every header to the Location host (both critiques executed it)."""
    notes: dict = {}
    with _provider(200, b'{"data":[]}') as (elsewhere, seen_there):
        with _provider(302, b"", ctype="text/html", location=elsewhere + "/grab") as (base, _seen):
            monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
            report = health.check(_keyed(tmp_path, "exa"), timeout=8, notes=notes)
    assert seen_there == [], "the Location host never sees a request, let alone the key"
    assert report["exa"] == "CONNECTED" and notes["exa"] == "unverified (redirect)"


def test_a_slow_provider_is_cut_at_the_deadline(tmp_path, monkeypatch):
    """urllib's timeout is per socket operation, so a body trickling one byte every 0.4 s never trips it (30 bytes:
    12 s); the key check holds a wall-clock deadline of min(timeout, 5)."""
    notes: dict = {}
    body = b'{"data":[],"hasMore":false,"x":1}'[:30]
    with _provider(200, body, trickle=0.4) as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        t0 = time.monotonic()
        report = health.check(_keyed(tmp_path, "exa"), timeout=8, notes=notes)
        elapsed = time.monotonic() - t0
    assert notes["exa"] == "unverified (timeout)" and report["exa"] == "CONNECTED"
    assert elapsed < 7, f"the probe waited {elapsed:.1f}s for a provider past its 5s deadline"


@pytest.mark.parametrize("key", [None, "", "${EXA_API_KEY}"], ids=["unset", "empty", "placeholder"])
def test_a_key_is_never_sent_without_a_real_key(key, tmp_path, monkeypatch):
    notes: dict = {}
    with _provider(401, EXA_REFUSED) as (base, seen):
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        report = health.check(_keyed(tmp_path, "exa", key=key), timeout=8, notes=notes)
    assert seen == [], "no request is made without a real key"
    assert report["exa"] == "CONNECTED" and notes["exa"] == "unverified (no key)"


def test_no_key_or_body_reaches_stdout_or_the_cache(tmp_path, monkeypatch, capsys):
    key = "k-secret-0123456789abcdef"
    echo = b'{"requestId":"r1","error":"Invalid API key k-secret-0123456789abcdef","tag":"INVALID_API_KEY"}'
    cache = tmp_path / "cache.json"
    with _provider(401, echo) as (base, seen):
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        repo = _keyed(tmp_path, "exa", key=key)
        assert health.main(["--repo", str(repo), "--timeout", "8", "--cache-out", str(cache)]) == 0
    out = capsys.readouterr().out + cache.read_text()
    assert seen and seen[0][1] == key, "the key was presented to the provider"
    assert "exa: UNAUTHORIZED (HTTP 401" in out
    assert key not in out and "Invalid API key" not in out


def test_a_dead_transport_wins_over_the_key_check(tmp_path, monkeypatch):
    with _provider(401, EXA_REFUSED) as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        report = health.check(_keyed(tmp_path, "exa", command="/bin/false"), timeout=5)
    assert report["exa"] == "DEAD"


def test_main_prints_the_key_check_line(tmp_path, monkeypatch, capsys):
    """An unverified key check is visible under its CONNECTED verdict, and never counted as a death."""
    with _provider(403, b"<html>blocked</html>", ctype="text/html") as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        assert health.main(["--repo", str(_keyed(tmp_path, "exa")), "--timeout", "8"]) == 0
    out = capsys.readouterr().out
    assert "exa: CONNECTED" in out
    assert "MCP-HEALTH: exa key check — unverified (HTTP 403)" in out
    assert "MCP-HEALTH: all 1 probed servers live" in out


@contextlib.contextmanager
def _garbage_server(reply=b"GARBAGE\r\n\r\n"):
    """A raw TCP stand-in that answers any request with ``reply`` — not HTTP at all."""
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(4)
    stop = threading.Event()

    def serve():
        sock.settimeout(0.2)
        while not stop.is_set():
            try:
                conn, _ = sock.accept()
            except OSError:
                continue
            with conn:
                conn.recv(4096)
                conn.sendall(reply)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        stop.set()
        thread.join(timeout=5)
        sock.close()


def test_a_garbled_reply_is_unverified_not_a_crash(tmp_path, monkeypatch, capsys):
    """A malformed status line raised BadStatusLine (an HTTPException, no OSError) out of the daemon thread: a
    traceback on stderr and a false `timeout` (review pass 1, both slice-A seats)."""
    notes: dict = {}
    with _garbage_server() as base:
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        report = health.check(_keyed(tmp_path, "exa"), timeout=8, notes=notes)
    assert report["exa"] == "CONNECTED" and notes["exa"] == "unverified (malformed reply)"
    assert "Traceback" not in capsys.readouterr().err


def test_a_gateways_bare_json_401_is_not_exas_refusal(tmp_path, monkeypatch):
    """Exa's error body carries a machine `tag`; a gateway's {"error": "…"} 401 is not exa refusing the key."""
    notes: dict = {}
    with _provider(401, b'{"error":"gateway auth required"}') as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        report = health.check(_keyed(tmp_path, "exa"), timeout=8, notes=notes)
    assert report["exa"] == "CONNECTED" and notes["exa"] == "unverified (HTTP 401)"


def test_a_refused_key_under_a_dead_transport_is_still_said(tmp_path, monkeypatch):
    notes: dict = {}
    with _provider(401, EXA_REFUSED) as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        report = health.check(_keyed(tmp_path, "exa", command="/bin/false"), timeout=5, notes=notes)
    assert report["exa"] == "DEAD" and notes["exa"] == "refused (HTTP 401)"


def test_a_connect_timeout_reads_timeout(monkeypatch):
    """urllib wraps a CONNECT timeout in URLError(reason=TimeoutError); only a read timeout arrives bare."""
    import urllib.error

    class _Opener:
        def open(self, *_a, **_k):
            raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr(health.urllib.request, "build_opener", lambda *_a: _Opener())
    entry = {"env": {"EXA_API_KEY": "k-test-0123456789"}}
    assert health._probe_auth("exa", entry, 1) == ("unverified", "timeout")


def test_a_broken_check_is_a_reason_never_an_escape():
    """Anything unexpected inside the check is reported by its type alone — never raised, never the key."""
    assert health._probe_auth("exa", {"env": ["not", "a", "dict"]}, 1) == (
        "unverified",
        "error (AttributeError)",
    )


@pytest.mark.parametrize(
    "name,status,body,expected",
    [
        # a status and a shape that disagree are never a verdict
        ("exa", 200, EXA_REFUSED, ("unverified", "HTTP 200")),
        ("firecrawl", 401, b'{"success":true,"data":{}}', ("unverified", "HTTP 401")),
        # a provider-shaped refusal needs the WHOLE documented shape
        ("firecrawl", 401, b'{"success":false}', ("unverified", "HTTP 401")),
        # a 2xx that is not the provider's success shape proves nothing
        ("exa", 200, b'{"websets":[]}', ("unverified", "HTTP 200")),
        ("firecrawl", 200, b'{"data":{"remaining_credits":5}}', ("unverified", "HTTP 200")),
        # a boolean is not a credit count
        (
            "firecrawl",
            200,
            b'{"success":true,"data":{"remaining_credits":false}}',
            ("accepted", "accepted"),
        ),
    ],
    ids=[
        "exa-200-error-shape",
        "fc-401-success-shape",
        "fc-401-no-error",
        "exa-200-other",
        "fc-200-no-success",
        "fc-bool-credit",
    ],
)
def test_each_row_of_the_outcome_table(name, status, body, expected, monkeypatch):
    """Review pass 1 (B-sonnet): ten single-clause mutants of the outcome table survived the whole file."""
    with _provider(status, body) as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES[name], "url", base + "/probe")
        entry = {"env": {health._AUTH_PROBES[name]["env"]: "k-test-0123456789"}}
        assert health._probe_auth(name, entry, 5) == expected


def test_a_refused_connection_is_unreachable_not_a_refused_key(monkeypatch):
    """A connection the network refuses is never the provider refusing the key. (A stand-in opener, not a closed
    port: on this box's WSL loopback a closed port times out instead of refusing.)"""
    import urllib.error

    class _Opener:
        def open(self, *_a, **_k):
            raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    monkeypatch.setattr(health.urllib.request, "build_opener", lambda *_a: _Opener())
    entry = {"env": {"EXA_API_KEY": "k-test-0123456789"}}
    assert health._probe_auth("exa", entry, 5) == ("unverified", "unreachable")


def test_a_read_timeout_reads_timeout(monkeypatch):
    class _Opener:
        def open(self, *_a, **_k):
            raise TimeoutError("timed out")

    monkeypatch.setattr(health.urllib.request, "build_opener", lambda *_a: _Opener())
    entry = {"env": {"FIRECRAWL_API_KEY": "k-test-0123456789"}}
    assert health._probe_auth("firecrawl", entry, 1) == ("unverified", "timeout")


def test_the_key_falls_back_to_the_process_environment(tmp_path, monkeypatch):
    """A server with no key in its own env inherits the process environment (`_probe_stdio` spawns with env=None),
    so the check presents that key — as a Bearer token for firecrawl."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "k-from-the-shell-0123")
    with _provider(200, b'{"success":true,"data":{"remaining_credits":3}}') as (base, seen):
        monkeypatch.setitem(health._AUTH_PROBES["firecrawl"], "url", base + "/probe")
        entry = {"type": "stdio", "command": sys.executable, "args": ["-c", FAKE_OK_SERVER]}
        notes: dict = {}
        report = health.check(_mk(tmp_path, {"firecrawl": entry}), timeout=8, notes=notes)
    assert seen and seen[0][2] == "Bearer k-from-the-shell-0123" and seen[0][1] is None
    assert report["firecrawl"] == "CONNECTED" and notes["firecrawl"] == "accepted"


@pytest.mark.parametrize(
    "timeout,bound", [(8, 6.0), (2, 3.5)], ids=["deadline-5s", "deadline-follows-timeout"]
)
def test_the_key_check_deadline_is_min_of_timeout_and_5s(timeout, bound, tmp_path, monkeypatch):
    """5 s keeps the check inside command_run's `--timeout 6` start probe; a smaller --timeout shrinks it too."""
    notes: dict = {}
    body = b'{"data":[],"hasMore":false,"x":1}'[:30]
    with _provider(200, body, trickle=0.4) as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        t0 = time.monotonic()
        health.check(_keyed(tmp_path, "exa"), timeout=timeout, notes=notes)
        elapsed = time.monotonic() - t0
    assert notes["exa"] == "unverified (timeout)"
    assert elapsed < bound, f"{elapsed:.1f}s for a {min(timeout, 5)}s deadline"


@pytest.mark.parametrize(
    "tag",
    ["gateway says no", "invalid_api_key", "INVALID-API-KEY", "X" + "Y" * 70],
    ids=["prose", "lower", "hyphen", "overlong"],
)
def test_only_a_machine_tag_makes_an_exa_refusal(tag, monkeypatch):
    """Exa's tags are machine codes (INVALID_API_KEY, NO_MORE_CREDITS, X402_…); any other string is a gateway's."""
    body = json.dumps({"error": "x", "tag": tag}).encode()
    with _provider(401, body) as (base, _seen):
        monkeypatch.setitem(health._AUTH_PROBES["exa"], "url", base + "/probe")
        entry = {"env": {"EXA_API_KEY": "k-test-0123456789"}}
        assert health._probe_auth("exa", entry, 5) == ("unverified", "HTTP 401")


def test_a_bare_socket_error_is_unreachable(monkeypatch):
    """An OSError that urllib does not wrap (a reset mid-handshake) is the network, never a refused key."""

    class _Opener:
        def open(self, *_a, **_k):
            raise ConnectionResetError(104, "Connection reset by peer")

    monkeypatch.setattr(health.urllib.request, "build_opener", lambda *_a: _Opener())
    entry = {"env": {"EXA_API_KEY": "k-test-0123456789"}}
    assert health._probe_auth("exa", entry, 5) == ("unverified", "unreachable")


def test_an_error_body_cut_short_is_read_as_empty(monkeypatch):
    """A 401 whose body breaks mid-read is a status with no provider shape — unverified, not a probe `error`."""
    import http.client
    import urllib.error

    class _CutBody:
        def read(self, *_a):
            raise http.client.IncompleteRead(b"{")

        def close(self):
            pass

    class _Opener:
        def open(self, req, *_a, **_k):
            raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, _CutBody())

    monkeypatch.setattr(health.urllib.request, "build_opener", lambda *_a: _Opener())
    entry = {"env": {"EXA_API_KEY": "k-test-0123456789"}}
    assert health._probe_auth("exa", entry, 5) == ("unverified", "HTTP 401")


def _hub(tmp_path: Path, servers: dict | None) -> Path:
    """A hub-class repo (named `fabrik`, so the emitter rules it the full catalog)."""
    repo = tmp_path / "fabrik"
    repo.mkdir()
    if servers is not None:
        (repo / ".mcp.json").write_text(json.dumps({"mcpServers": servers}))
    return repo


def test_health_names_withheld_and_stale_services(tmp_path, monkeypatch, capsys):
    """W-07298e38: the emitter withholds a service MCP whose unit is not installed and enabled, which
    would hide a forgotten install from the fix-first signal. Health names it — `withheld` when the file
    lacks it, `stale entry` when the file still carries it (the hub on 2026-10-24) — outside the report,
    so the mcp_watch cache never counts it as a death."""
    monkeypatch.setenv("FABRIK_SYSTEMD_UNIT_DIR", str(tmp_path / "no-units"))
    monkeypatch.setattr(health, "check", lambda *a, **k: {"fabrik-scrape": "DEAD"})
    cache = tmp_path / "cache.json"
    health.main(["--repo", str(_hub(tmp_path, {"fabrik-scrape": {}})), "--cache-out", str(cache)])
    out = capsys.readouterr().out
    assert (
        "MCP-HEALTH: fabrik-scrape is emitted but its unit fabrik-scrape-mcp.service is not installed"
        " and enabled — a stale entry; install the unit (/opt/fabrik/docs/reference/fabrik-scrape-mcp.md"
        " § Build, install, update), or remove the entry from " in out
    ), out  # not a git repo: the emitter would SKIP it, so a re-run is never the advice
    assert json.loads(cache.read_text())["report"] == {"fabrik-scrape": "DEAD"}

    (tmp_path / "fabrik" / ".mcp.json").write_text(json.dumps({"mcpServers": {}}))
    monkeypatch.setattr(health, "check", lambda *a, **k: {})
    health.main(["--repo", str(tmp_path / "fabrik")])
    out = capsys.readouterr().out
    assert (
        "MCP-HEALTH: fabrik-scrape withheld — unit fabrik-scrape-mcp.service not installed and"
        " enabled; install it (/opt/fabrik/docs/reference/fabrik-scrape-mcp.md § Build, install, update),"
        " then re-run python3 /opt/fabrik/scripts/sysadmin/emit_mcp_project_config.py --repo "
        in out
    ), out
    assert (
        "fabrik-citation-verifier withheld — unit fabrik-mcp-http.service not installed and enabled; install"
        " it (/opt/fabrik/docs/workstation/MCP_HTTP_TRANSPORT.md § Operations)" in out
    ), out  # its unit is absent from the tmp dir too


def test_a_stale_entry_in_an_emitter_owned_file_says_re_run(tmp_path, monkeypatch, capsys):
    """A plain, git-ignored `.mcp.json` is one the emitter rewrites, so there the advice is the re-run."""
    monkeypatch.setenv("FABRIK_SYSTEMD_UNIT_DIR", str(tmp_path / "no-units"))
    empty = tmp_path / "empty.gitconfig"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    repo = _hub(tmp_path, {"fabrik-scrape": {}})
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text(".mcp.json\n")
    monkeypatch.setattr(health, "check", lambda *a, **k: {"fabrik-scrape": "DEAD"})
    health.main(["--repo", str(repo)])
    out = capsys.readouterr().out
    assert "a stale entry; install the unit (" in out and "), or re-run python3 " in out, out


def test_a_failed_probe_still_names_withheld_services(tmp_path, monkeypatch, capsys):
    """`check()` raising (a corrupt `.mcp.json`) returned before the withheld lines."""
    monkeypatch.setenv("FABRIK_SYSTEMD_UNIT_DIR", str(tmp_path / "no-units"))

    def _boom(*_a, **_k):
        raise ValueError("corrupt")

    monkeypatch.setattr(health, "check", _boom)
    assert health.main(["--repo", str(_hub(tmp_path, {}))]) == 0
    out = capsys.readouterr().out
    assert "probe failed open (ValueError)" in out and "fabrik-scrape withheld" in out, out


def test_every_service_unit_names_an_install_doc_that_exists():
    em = health._load_emitter()
    assert set(health.INSTALL_DOCS) == set(em.SERVICE_UNITS.values())
    for where in health.INSTALL_DOCS.values():
        path, _, section = where.partition(" § ")
        assert Path(path).is_file(), path
        assert f"## {section}" in Path(path).read_text(), where


def test_health_names_a_withheld_service_with_no_mcp_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("FABRIK_SYSTEMD_UNIT_DIR", str(tmp_path / "no-units"))
    assert health.main(["--repo", str(_hub(tmp_path, None))]) == 0
    out = capsys.readouterr().out
    assert "fabrik-scrape withheld" in out and "no .mcp.json" in out, out


def test_health_is_silent_when_every_unit_is_enabled(tmp_path, monkeypatch, capsys):
    units = tmp_path / "units"
    (units / "multi-user.target.wants").mkdir(parents=True)
    for unit in ("fabrik-scrape-mcp.service", "fabrik-mcp-http.service"):
        (units / unit).write_text("[Unit]\n")
        (units / "multi-user.target.wants" / unit).symlink_to(units / unit)
    monkeypatch.setenv("FABRIK_SYSTEMD_UNIT_DIR", str(units))
    assert health.main(["--repo", str(_hub(tmp_path, None))]) == 0
    assert "withheld" not in capsys.readouterr().out
    # positive control: the same repo with one wants link gone does print, so the silence above is the guard's
    (units / "multi-user.target.wants" / "fabrik-scrape-mcp.service").unlink()
    health.main(["--repo", str(tmp_path / "fabrik")])
    assert "fabrik-scrape withheld" in capsys.readouterr().out


@pytest.mark.parametrize("broken", ["missing", "exits"])
def test_health_withheld_read_fails_open(tmp_path, monkeypatch, capsys, broken):
    """A broken sibling emitter — gone, or one that raises SystemExit at import as `_load_defs` would —
    prints its reason and never breaks the probe or its exit code."""
    emitter = tmp_path / "emit.py"
    if broken == "exits":
        emitter.write_text("raise SystemExit('boom')\n")
    monkeypatch.setattr(health, "EMITTER_PATH", emitter)
    assert health.main(["--repo", str(_hub(tmp_path, None))]) == 0
    out = capsys.readouterr().out
    assert "mcp-health: withheld check failed open (" in out, out
