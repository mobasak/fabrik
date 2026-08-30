#!/usr/bin/env python3
# AFTER-EDIT: tests/test_mcp_health.py · docs/workstation/mcp-roster.md (§ fix-first) | none
"""Assigned-vs-LIVE MCP diff for the current repo (D-033 forcing pair, advisory).

Reads the repo's emitted ``.mcp.json`` (the ASSIGNED set — D-032's contract) and
probes each server for real liveness: stdio → spawn + one JSON-RPC initialize
with a hard timeout; http/sse → TCP+HTTP reach. A server that cannot answer
within the timeout IS dead for Claude's purposes (its own connect timeout is
30s; postgres-mcp's blocked-handshake class measured 2026-08-30).

ADVISORY CONTRACT: always exits 0 — it reports, run records cite it, nothing
blocks on it until its fire rate earns promotion (the measured-rollout law).

Usage: python3 /opt/fabrik/scripts/sysadmin/mcp_health.py [--repo <path>] [--timeout N]
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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
        out, _err = proc.communicate(input=_INIT.encode(), timeout=timeout)
        return "CONNECTED" if b'"jsonrpc"' in out else "DEAD"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except OSError:
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


def check(repo: Path, timeout: int = 8) -> dict[str, str]:
    """{server: CONNECTED|DEAD|TIMEOUT} for every ASSIGNED server of ``repo``."""
    servers = json.loads((repo / ".mcp.json").read_text()).get("mcpServers", {})

    def one(item: tuple[str, dict]) -> tuple[str, str]:
        name, entry = item
        kind = entry.get("type", "stdio")
        probe = _probe_http if kind in ("http", "streamable-http", "sse") else _probe_stdio
        return name, probe(entry, timeout)

    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(one, servers.items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".", help="repo root (default: cwd)")
    ap.add_argument("--timeout", type=int, default=8)
    ap.add_argument("--cache-out", help="also write {ts, report} JSON here (the mcp_watch hook's cache)")
    args = ap.parse_args(argv)
    repo = Path(args.repo)
    if not (repo / ".mcp.json").is_file():
        print(f"mcp-health: no .mcp.json in {repo} — universal user-level set only, nothing to diff")
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
            Path(args.cache_out).write_text(json.dumps({"ts": _time.time(), "report": report}) + "\n")
        except OSError:
            pass  # cache write is best-effort; the printed report stands
    bad = {n: v for n, v in report.items() if v != "CONNECTED"}
    for name, verdict in sorted(report.items()):
        print(f"{name}: {verdict}")
    if bad:
        print(
            f"MCP-HEALTH: {len(bad)}/{len(report)} assigned server(s) NOT live ({', '.join(sorted(bad))})"
            " — fix-first duty applies (known classes: docs/workstation/mcp-roster.md)"
        )
    else:
        print(f"MCP-HEALTH: all {len(report)} assigned servers live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
