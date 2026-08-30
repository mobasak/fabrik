#!/usr/bin/env python3
# AFTER-EDIT: tests/test_mcp_health.py · docs/workstation/mcp-roster.md (§ fix-first) | none
"""Assigned-vs-LIVE MCP diff for the current repo (D-033 forcing pair, advisory).

Reads the repo's emitted ``.mcp.json`` (the ASSIGNED set — D-032's contract) and
probes each server for real liveness: stdio → spawn + one JSON-RPC initialize
with a hard timeout; http/sse → TCP+HTTP reach. A server that cannot answer
within the timeout IS dead for Claude's purposes (its own connect timeout is
30s; postgres-mcp's blocked-handshake class measured 2026-08-30).

THE PROBE MIRRORS CLAUDE'S HANDSHAKE, because anything stricter manufactures
false deaths. Three false-verdict classes were measured on 2026-08-30 (this probe
said 4/15 NOT live — grafana, maestro, media-engine, serena — while `claude mcp
list` said 15/15 Connected) and each is fixed here, not documented around:
  1. BUDGET: the default was 8s while Claude's connect timeout is 30s, so a
     slow-but-live server read as TIMEOUT (serena: TIMEOUT at 8s, CONNECTED at
     24.2s). The default now matches Claude's real budget.
  2. STDIN: communicate() closes stdin and waits for process EOF, so a server
     that exits on stdin-close never answered (maestro: DEAD at 8s AND at 45s —
     more time could never have fixed it). We now keep stdin OPEN and return on
     the FIRST JSON-RPC frame, which is what Claude does and what actually
     proves liveness — the frame is the evidence, not the exit code.
  3. CONTENTION: probing every server at once starved slow starters (media-engine
     TIMEOUT in a 15-server batch, CONNECTED in 4.4s alone). Concurrency is
     bounded so the probe measures the server, not the probe's own load.
A verdict this probe cannot MEASURE is never reported as a death — see main().

ADVISORY CONTRACT: always exits 0 — it reports, run records cite it, nothing
blocks on it until its fire rate earns promotion (the measured-rollout law).

Usage: python3 /opt/fabrik/scripts/sysadmin/mcp_health.py [--repo <path>] [--timeout N]
"""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import subprocess
import time as _time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Claude Code's own MCP connect budget. The probe exists to answer "is this server
# live FOR CLAUDE", so a shorter budget here can only invent deaths Claude does not see.
CLAUDE_CONNECT_TIMEOUT_S = 30

_INIT = (
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":'
    '"2024-11-05","capabilities":{},"clientInfo":{"name":"mcp-health","version":"0"}}}\n'
)


def _probe_stdio(entry: dict, timeout: int) -> str:
    cmd = [entry.get("command", "")] + list(entry.get("args", []))
    if not cmd[0]:
        return "DEAD"
    if Path(cmd[0]).name == "docker" or cmd[0] == "docker":
        # a docker-run entry would spawn a REAL container against live infra per
        # health check, and killing the CLI never stops the container — skip
        # honestly rather than probe destructively (author-blind review 2026-08-30)
        return "SKIPPED (docker-run entry — probe would launch a live container)"
    proc = None
    try:
        # own session per child so the kill reaches uvx/npx GRANDCHILDREN too —
        # stdio MCP servers outlive one initialize and reparent to 1 otherwise
        # (6 orphaned serena processes measured; author-blind review 2026-08-30)
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            env=None if not entry.get("env") else {**os.environ, **entry["env"]},
        )
        # Write the handshake but keep stdin OPEN — closing it kills servers that
        # treat EOF as shutdown (the maestro class), and then no timeout is long
        # enough. Read until the first JSON-RPC frame arrives: that frame is the
        # liveness evidence, so we neither wait for process EOF nor care that the
        # server exits right after answering.
        proc.stdin.write(_INIT.encode())
        proc.stdin.flush()
        deadline = _time.monotonic() + timeout
        buf = b""
        while _time.monotonic() < deadline:
            remaining = max(0.0, deadline - _time.monotonic())
            if not select.select([proc.stdout], [], [], min(0.5, remaining))[0]:
                if proc.poll() is not None and not buf:
                    return "DEAD"  # exited without ever answering
                continue
            chunk = (
                proc.stdout.read1(65536) if hasattr(proc.stdout, "read1") else proc.stdout.read(1)
            )
            if not chunk:  # EOF
                return "CONNECTED" if b'"jsonrpc"' in buf else "DEAD"
            buf += chunk
            if b'"jsonrpc"' in buf:
                return "CONNECTED"
        return "TIMEOUT"
    except (BrokenPipeError, OSError):
        return "DEAD"
    finally:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
            try:
                proc.wait(timeout=3)
            except Exception:
                pass


def _probe_http(entry: dict, timeout: int) -> str:
    url = entry.get("url", "")
    if not url:
        return "DEAD"
    try:
        urllib.request.urlopen(url, timeout=timeout)  # noqa: S310 — local health probe
        return "CONNECTED"
    except urllib.error.HTTPError:
        return "CONNECTED"  # ANY http response (406, 4xx) = the endpoint is alive
    except (urllib.error.URLError, OSError, TimeoutError):
        return "DEAD"


def check(repo: Path, timeout: int = CLAUDE_CONNECT_TIMEOUT_S) -> dict[str, str]:
    """{server: CONNECTED|DEAD|TIMEOUT|SKIPPED …} for every ASSIGNED server of ``repo``."""
    servers = json.loads((repo / ".mcp.json").read_text()).get("mcpServers", {})

    def one(item: tuple[str, dict]) -> tuple[str, str]:
        name, entry = item
        kind = entry.get("type", "stdio")
        probe = _probe_http if kind in ("http", "streamable-http", "sse") else _probe_stdio
        return name, probe(entry, timeout)

    # Bounded: spawning a whole roster at once starves the slow starters and the
    # probe ends up measuring its own contention (media-engine: TIMEOUT in a
    # 15-server batch, CONNECTED in 4.4s alone — measured 2026-08-30).
    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(one, servers.items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    ap.add_argument("--timeout", type=int, default=CLAUDE_CONNECT_TIMEOUT_S)
    ap.add_argument(
        "--cache-out", help="also write {ts, report} JSON here (the mcp_watch hook's cache)"
    )
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    if not (repo / ".mcp.json").is_file():
        print(
            f"mcp-health: no .mcp.json in {repo} — universal user-level set only, nothing to diff"
        )
        return 0
    try:
        report = check(repo, args.timeout)
    except Exception as exc:  # advisory: a broken probe never blocks anyone
        print(f"mcp-health: probe failed open ({type(exc).__name__}) — no verdict")
        return 0
    if args.cache_out:
        try:
            import time as _time

            Path(args.cache_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.cache_out).write_text(
                json.dumps({"ts": _time.time(), "report": report}) + "\n"
            )
        except OSError:
            pass  # cache write is best-effort; the printed report stands
    # A SKIPPED entry was deliberately NOT MEASURED (docker-run). Counting it as
    # "NOT live" asserts a death from a non-measurement — the same denominator
    # dishonesty the contract bans ("a bounded search returns 'not found in N',
    # never 'does not exist'"). It is reported as UNPROBED: visible, never silent,
    # and never inflating the dead count that drives the fix-first mandate.
    unprobed = {n: v for n, v in report.items() if v.startswith("SKIPPED")}
    bad = {n: v for n, v in report.items() if v != "CONNECTED" and n not in unprobed}
    for name, verdict in sorted(report.items()):
        print(f"{name}: {verdict}")
    probed = len(report) - len(unprobed)
    if bad:
        print(
            f"MCP-HEALTH: {len(bad)}/{probed} probed server(s) NOT live ({', '.join(sorted(bad))})"
            " — fix-first duty applies (known classes: docs/workstation/mcp-roster.md)"
        )
    else:
        print(f"MCP-HEALTH: all {probed} probed servers live")
    if unprobed:
        print(
            f"MCP-HEALTH: {len(unprobed)} server(s) UNPROBED, liveness unknown "
            f"({', '.join(sorted(unprobed))}) — verify with `claude mcp list`"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
