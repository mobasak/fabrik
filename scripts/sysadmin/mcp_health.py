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

THE KEY CHECK (W-3350006b): a transport proves nothing about the credential — on 2026-10-07 exa and firecrawl
both answered `initialize` while refusing every call with their key (mail 01M49YT4T5). For the servers in
`_AUTH_PROBES` the probe also presents the configured key with one body-less, no-credit GET; only a
provider-shaped JSON 401/402 turns the verdict `UNAUTHORIZED (…)`. Everything a blocked egress, a portal or a
gateway produces (HTML, a 403, an unshaped JSON, a redirect, a timeout) is a `key check — unverified` note under a
transport verdict left as it was, never a death: the same answer comes back for a good key and a bad one.

ADVISORY CONTRACT: always exits 0 — it reports, run records cite it, nothing
blocks on it until its fire rate earns promotion (the measured-rollout law).

Usage: python3 /opt/fabrik/scripts/sysadmin/mcp_health.py [--repo <path>] [--timeout N]
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import select
import signal
import subprocess
import threading
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
            # read1: one buffered read of whatever has arrived, never blocking for a
            # full 64K. stdout is always a BufferedReader here (Popen + PIPE at the
            # default bufsize), so this attribute is guaranteed — verified, not assumed.
            chunk = proc.stdout.read1(65536)
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
            # communicate() used to close these for us; the hand-rolled read loop must
            # do it explicitly or every probe leaves pipes for the GC — harmless under
            # refcounting but it emits ResourceWarning per server, which is a hard
            # error under `-W error` (CI) and noise everywhere else.
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if stream is not None:
                        stream.close()
                except OSError:
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


# The key check, per server NAME (every config on the box names them so — 48 of 48 measured 2026-10-19; a server
# renamed away from these keeps its transport check and gets no key check). One body-less GET each, spending nothing:
# firecrawl's credit read (quota_dashboard.py's no-credit call) and exa's websets list — never exa /search (metered;
# D-337 keeps tier 2 "for a miss, never a habit") and never a body the provider might validate before the key.
_AUTH_PROBES: dict[str, dict] = {
    "firecrawl": {
        "env": "FIRECRAWL_API_KEY",
        "url": "https://api.firecrawl.dev/v1/team/credit-usage",
        "header": lambda key: {"Authorization": f"Bearer {key}"},
        # its documented error body: {"success": false, "error": "…"}
        "refused": lambda b: b.get("success") is False and isinstance(b.get("error"), str),
        "accepted": lambda b: b.get("success") is True,
    },
    "exa": {
        "env": "EXA_API_KEY",
        "url": "https://api.exa.ai/websets/v0/websets?limit=1",
        "header": lambda key: {"x-api-key": key},
        # its documented error body: {"requestId", "error", "tag"} — the tag a machine code such as
        # INVALID_API_KEY; a gateway's bare {"error": "…"} is not exa's and must not read as a refused key
        "refused": lambda b: (
            isinstance(b.get("error"), str)
            and isinstance(b.get("tag"), str)
            and _EXA_TAG.fullmatch(b["tag"]) is not None
        ),
        "accepted": lambda b: isinstance(b.get("data"), list),
    },
}
# A wall-clock bound on the key check: urllib's timeout is per socket operation (a trickling body held 11.9 s at a 1 s
# timeout) and does not cover DNS. 5 s fits inside command_run's `--timeout 6` start probe without adding a round.
_AUTH_DEADLINE_S = 5
_EXA_TAG = re.compile(r"[A-Z][A-Z0-9_]{1,63}")
_BODY_CAP = 65536


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every 30x: urllib's default handler re-sends the request's headers — the key — to the Location host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001 — urllib's signature
        return None


def _probe_auth(name: str, entry: dict, timeout: float) -> tuple[str, str]:
    """``(outcome, detail)``: ``refused`` with ``HTTP 401|402``, ``accepted`` with its note, or ``unverified`` with
    its reason. Never raises — an escape would kill the daemon thread and read as a false `timeout` — and never
    returns or logs the key or the body (the guard names only the exception's type)."""
    try:
        return _ask_provider(name, entry, timeout)
    except Exception as exc:  # noqa: BLE001 — the advisory contract: a broken check is a reason, never a crash
        return "unverified", f"error ({type(exc).__name__})"


def _ask_provider(name: str, entry: dict, timeout: float) -> tuple[str, str]:
    probe = _AUTH_PROBES[name]
    key = (entry.get("env") or {}).get(probe["env"]) or os.environ.get(probe["env"]) or ""
    # Claude expands a `${…}` placeholder; this probe does not, so it never sends one
    if not key or "${" in key:
        return "unverified", "no key"
    req = urllib.request.Request(
        probe["url"], headers={"accept": "application/json", **probe["header"](key)}
    )
    # built per call: build_opener reads the proxy environment when it runs, so an import-time opener would pin the
    # proxy settings of whoever imported the module first
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as resp:  # noqa: S310 — a fixed https provider URL
            status, raw = resp.status, resp.read(_BODY_CAP)
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            raw = exc.read(_BODY_CAP)
        except (OSError, http.client.HTTPException):
            raw = b""
    except TimeoutError:
        return "unverified", "timeout"
    # a garbled status line or a cut body — not a provider's answer
    except http.client.HTTPException:
        return "unverified", "malformed reply"
    except urllib.error.URLError as exc:  # a connect timeout arrives wrapped
        return "unverified", "timeout" if isinstance(exc.reason, TimeoutError) else "unreachable"
    except (OSError, ValueError):
        return "unverified", "unreachable"
    if 300 <= status < 400:
        return "unverified", "redirect"
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        body = None
    if not isinstance(body, dict):
        return "unverified", f"HTTP {status}"
    if status in (401, 402) and probe["refused"](body):
        return "refused", f"HTTP {status}"
    if 200 <= status < 300 and probe["accepted"](body):
        left = (
            (body.get("data") or {}).get("remaining_credits")
            if isinstance(body.get("data"), dict)
            else None
        )
        if isinstance(left, (int, float)) and not isinstance(left, bool) and left <= 0:
            return "accepted", "accepted (0 credits left)"
        return "accepted", "accepted"
    return "unverified", f"HTTP {status}"


_REFUSED_VERDICT = {
    "HTTP 401": "UNAUTHORIZED (HTTP 401: the provider refused the key)",
    "HTTP 402": "UNAUTHORIZED (HTTP 402: the provider refused the account — no credit)",
}


def _start_key_checks(servers: dict, timeout: int) -> dict[str, tuple[threading.Thread, dict]]:
    """One DAEMON thread per key-checked server, started before the transport probes: a daemon thread past the deadline
    is abandoned without holding process exit (a pool task held exit 5.0 s past a 0.5 s deadline, measured)."""
    started = {}
    for name, entry in servers.items():
        if name not in _AUTH_PROBES or not isinstance(entry, dict):
            continue
        box: dict = {}

        def run(name=name, entry=entry, box=box) -> None:
            box["result"] = _probe_auth(name, entry, min(timeout, _AUTH_DEADLINE_S))

        thread = threading.Thread(target=run, name=f"mcp-key-{name}", daemon=True)
        thread.start()
        started[name] = (thread, box)
    return started


def check(
    repo: Path, timeout: int = CLAUDE_CONNECT_TIMEOUT_S, notes: dict[str, str] | None = None
) -> dict[str, str]:
    """{server: CONNECTED|DEAD|TIMEOUT|SKIPPED|UNAUTHORIZED …} for every ASSIGNED server of ``repo``; ``notes`` (when
    given) receives each key-checked server's `accepted …` or `unverified (<reason>)`."""
    servers = json.loads((repo / ".mcp.json").read_text()).get("mcpServers", {})
    deadline = _time.monotonic() + min(timeout, _AUTH_DEADLINE_S)
    key_checks = _start_key_checks(servers, timeout)

    def one(item: tuple[str, dict]) -> tuple[str, str]:
        name, entry = item
        kind = entry.get("type", "stdio")
        probe = _probe_http if kind in ("http", "streamable-http", "sse") else _probe_stdio
        return name, probe(entry, timeout)

    # Bounded: spawning a whole roster at once starves the slow starters and the
    # probe ends up measuring its own contention (media-engine: TIMEOUT in a
    # 15-server batch, CONNECTED in 4.4s alone — measured 2026-08-30).
    with ThreadPoolExecutor(max_workers=4) as pool:
        report = dict(pool.map(one, servers.items()))
    for name, (thread, box) in key_checks.items():
        thread.join(max(0.0, deadline - _time.monotonic()))
        outcome, detail = box.get("result", ("unverified", "timeout"))
        if outcome == "refused" and report.get(name) == "CONNECTED":
            report[name] = _REFUSED_VERDICT[detail]
        elif outcome == "refused":
            # a dead transport is the louder fact and keeps the verdict; the refusal is still said
            if notes is not None:
                notes[name] = f"refused ({detail})"
        elif notes is not None:
            notes[name] = detail if outcome == "accepted" else f"unverified ({detail})"
    return report


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
    notes: dict[str, str] = {}
    try:
        report = check(repo, args.timeout, notes)
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
    for name, note in sorted(notes.items()):
        print(f"MCP-HEALTH: {name} key check — {note}")
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
