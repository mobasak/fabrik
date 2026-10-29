#!/usr/bin/env python3
# AFTER-EDIT: tests/test_scrape_ledger.py, docs/reference/fabrik-scrape-mcp.md
"""Probe the fabrik-scrape MCP server, harvest the URLs research seats fetch, and grade a capability ledger.

Three modes (W-10146d20, plan 3 Phase B; spec docs/superpowers/specs/2026-10-21-own-scrape-tools-design.md § Test
ledger):

  --probe <url>                          MCP `initialize` + `tools/list`; prints serverInfo and the tool names.
                                         Exit 0 when `scrape` is listed, 1 otherwise or when the server is down.
  --harvest [--since <YYYY-MM-DD>] --out every URL a `fabrik-researcher` seat passed to a raw fetch
                                         (firecrawl_scrape, web_fetch_exa, WebFetch) in a subagent transcript.
  <input.json> [--server <url>] --out    runs each row's URL through `scrape` and grades it.

A ledger row is ``{id, url, kind, expected, facts, fact_source}``. ``expected`` is fixed BEFORE the run: ``pass`` or
the ``blocked`` reason the spec predicts (``bot-wall``, ``unsupported``, ``http-404`` …). The whole input is refused
(exit 2) before any fetch when a row lacks a field, names an unknown outcome, or expects ``pass`` without at least one
non-blank fact string, so no outcome is judged after the fact and no PASS is vacuous. A long page is read to its end,
chunk by chunk. PASS for ``expected: pass`` = every fact string found in the markdown (case-insensitive,
whitespace-normalised substring) AND a clean ratio — ASCII letters, digits and spaces over all characters — of at least
0.6; both are the spec's ``ledger2_run.py`` measures, so a row here grades as the spec's own ledger did. A fact that
straddles inline markup (``**x**``, a link) is not found: pick facts that sit in one plain run of text. PASS for a
blocked expectation = the result is blocked with exactly that reason. A row whose fetch errors is a FAIL carrying the
error; the other rows still run. Fact strings are copied to the output unchanged.

It speaks MCP streamable-HTTP as plain JSON-RPC over httpx, so it runs under the hub `.venv` (MCP SDK 1.x) as well as
under the server's own venv; there is no SDK dependency.

COBRA (D-253): the cheapest way to make a ledger all-pass without the tool reading the pages is to choose facts the
page boilerplate carries, or to set ``expected`` to the reason a page already returns. The counter is outside this
script: ``fact_source`` names the independent read the facts came from, and the plan fixes every ``expected`` from a
spec cite before the run — both stay reviewable in the input file the ledger result cites.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

CLEAN_FLOOR = 0.6
MAX_CHUNKS = 25  # 25 x 20 000 characters: past this a page is graded on what was read, with `chunks_capped` set
BLOCKED_REASONS = ("robots", "scope", "empty", "bot-wall", "unsupported", "render-unavailable")
FETCH_TOOLS = ("mcp__firecrawl__firecrawl_scrape", "mcp__exa__web_fetch_exa", "WebFetch")
DEFAULT_SERVER = os.getenv("FABRIK_SCRAPE_MCP_URL", "http://127.0.0.1:8034/mcp")
_ACCEPT = "application/json, text/event-stream"


class McpError(RuntimeError):
    """The server answered with a JSON-RPC error or a body this client cannot read."""


def _sse_events(text: str) -> list[str]:
    """Each SSE event's data: its `data:` lines joined with newlines, events split at blank lines."""
    events: list[str] = []
    lines: list[str] = []
    for line in [*text.splitlines(), ""]:
        if not line:
            if lines:
                events.append("\n".join(lines))
            lines = []
        elif line.startswith("data:"):
            lines.append(line[5:].removeprefix(" "))
    return events


def _decode(resp: httpx.Response, req_id: int) -> dict[str, Any]:
    """The JSON-RPC response to `req_id` in a streamable-HTTP reply: a JSON body, or that id's SSE event."""
    try:
        if "text/event-stream" in resp.headers.get("content-type", ""):
            msgs = [json.loads(data) for data in _sse_events(resp.text)]
        else:
            msgs = [resp.json()]
    except json.JSONDecodeError as exc:
        raise McpError(f"a reply this client cannot read: {exc}") from exc
    msg = next(
        (
            m
            for m in msgs
            if isinstance(m, dict) and m.get("id") == req_id and ("result" in m or "error" in m)
        ),
        None,
    )
    if msg is None:
        raise McpError(f"no JSON-RPC response to request {req_id} in the reply")
    if "error" in msg:
        raise McpError(f"JSON-RPC error: {msg['error']}")
    return msg


class McpClient:
    """A minimal MCP streamable-HTTP client: initialize, list tools, call a tool."""

    def __init__(
        self, url: str, *, transport: httpx.BaseTransport | None = None, timeout_s: float = 120.0
    ) -> None:
        self.url = url
        self._http = httpx.Client(transport=transport, timeout=timeout_s)
        self._session: str | None = None
        self._next_id = 0
        self._initialized = False
        self._protocol: str | None = None
        self.server_info: dict[str, Any] = {}

    def close(self) -> None:
        self._http.close()

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        headers = {"accept": _ACCEPT, "content-type": "application/json"}
        if self._session:
            headers["mcp-session-id"] = self._session
        if self._protocol:
            headers["mcp-protocol-version"] = self._protocol
        resp = self._http.post(self.url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        resp = self._post(
            {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params}
        )
        if self._session is None and resp.headers.get("mcp-session-id"):
            self._session = resp.headers["mcp-session-id"]
        result = _decode(resp, self._next_id).get("result", {})
        return result if isinstance(result, dict) else {}

    def initialize(self) -> dict[str, Any]:
        result = self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "scrape_ledger", "version": "1"},
            },
        )
        self.server_info = result.get("serverInfo") or {}
        self._protocol = result.get("protocolVersion") or "2025-06-18"
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True
        return result

    def list_tools(self) -> list[str]:
        if not self._initialized:
            self.initialize()
        tools = self._request("tools/list", {}).get("tools", [])
        return [t["name"] for t in tools if isinstance(t, dict) and isinstance(t.get("name"), str)]

    def scrape(self, url: str, **args: Any) -> dict[str, Any]:
        if not self._initialized:
            self.initialize()
        result = self._request("tools/call", {"name": "scrape", "arguments": {"url": url, **args}})
        if result.get("isError"):
            text = " ".join(c.get("text", "") for c in result.get("content", []))
            raise McpError(f"tool error: {text}")
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and structured:
            return structured
        for item in result.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    parsed = json.loads(item["text"])
                except json.JSONDecodeError as exc:
                    raise McpError(f"a tool result whose text is not JSON: {exc}") from exc
                if isinstance(parsed, dict):
                    return parsed
        raise McpError("a tool result with no readable content")

    def read_page(self, url: str) -> dict[str, Any]:
        """`scrape` to the page's end: later chunks come from the server's cache of the first read."""
        first = self.scrape(url)
        if first.get("blocked") or not first.get("truncated"):
            return first
        parts = [first.get("markdown", "")]
        page = dict(first)
        while page.get("truncated") and len(parts) < MAX_CHUNKS:
            page = self.scrape(url, start_index=sum(map(len, parts)), max_age_s=3600)
            if page.get("blocked"):
                raise McpError(
                    f"chunk {len(parts) + 1} blocked mid-read ({page.get('reason')}); the page is incomplete"
                )
            parts.append(page.get("markdown", ""))
        return {
            **first,
            "markdown": "".join(parts),
            "truncated": bool(page.get("truncated")),
            "chunks": len(parts),
            "chunks_capped": len(parts) >= MAX_CHUNKS and bool(page.get("truncated")),
        }


def probe(url: str, *, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    client = McpClient(url, transport=transport)
    try:
        client.initialize()
        return {"serverInfo": client.server_info, "tools": client.list_tools()}
    finally:
        client.close()


def clean_ratio(text: str) -> float:
    """ASCII letters, digits and spaces over all characters — `ledger2_run.py`'s measure; 0.0 for empty text."""
    if not text:
        return 0.0
    return len(re.findall(r"[A-Za-z0-9 ]", text)) / len(text)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


def grade(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """One ledger row's verdict; the row's own fields, fact strings included, are carried unchanged."""
    out = dict(row)
    facts: list[str] = list(row.get("facts", []))
    if result.get("blocked"):
        out.update(
            path=None,
            status=result.get("status"),
            blocked_reason=result.get("reason"),
            facts_found=0,
            facts_total=len(facts),
            missing=facts,
            clean_ratio=0.0,
        )
        out["grade"] = "PASS" if row["expected"] == result.get("reason") else "FAIL"
        return out
    text = _norm(result.get("markdown", ""))
    missing = [f for f in facts if _norm(f) not in text]
    ratio = round(clean_ratio(result.get("markdown", "")), 3)
    out.update(
        path=result.get("path"),
        status=result.get("status"),
        blocked_reason=None,
        facts_found=len(facts) - len(missing),
        facts_total=len(facts),
        missing=missing,
        clean_ratio=ratio,
        truncated=result.get("truncated"),
        short=result.get("short"),
        chunks=result.get("chunks", 1),
        chunks_capped=result.get("chunks_capped", False),
    )
    out["grade"] = (
        "PASS" if row["expected"] == "pass" and not missing and ratio >= CLEAN_FLOOR else "FAIL"
    )
    return out


def run_ledger(rows: list[dict[str, Any]], client: McpClient) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        try:
            out.append(grade(row, client.read_page(row["url"])))
        except (McpError, httpx.HTTPError) as exc:
            facts = list(row["facts"])
            out.append(
                {
                    **row,
                    "path": None,
                    "status": None,
                    "blocked_reason": None,
                    "facts_found": 0,
                    "facts_total": len(facts),
                    "missing": facts,
                    "clean_ratio": 0.0,
                    "grade": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return out


def _row_problem(row: Any) -> str | None:
    if not isinstance(row, dict):
        return "not an object"
    missing = [k for k in ("id", "url", "expected", "facts", "fact_source") if k not in row]
    if missing:
        return f"missing {'/'.join(missing)}"
    expected, facts = row["expected"], row["facts"]
    if not isinstance(row["id"], str) or not row["id"].strip():
        return "id must be a non-blank string"
    if not isinstance(row["url"], str) or not re.match(r"https?://\S", row["url"]):
        return "url must be an http(s) URL"
    if not isinstance(facts, list) or not all(isinstance(f, str) and f.strip() for f in facts):
        return "facts must be a list of non-blank strings"
    if expected == "pass":
        return None if facts else "expected pass needs at least one fact"
    if expected in BLOCKED_REASONS or (
        isinstance(expected, str) and re.fullmatch(r"http-[45]\d\d", expected)
    ):
        return None
    return f"unknown expected {expected!r} (pass, {', '.join(BLOCKED_REASONS)} or an http-4xx/5xx status)"


def load_rows(path: Path) -> list[dict[str, Any]]:
    """The ledger input; refused whole (exit 2) when it is not a non-empty list of valid rows (`_row_problem`)."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"refused: {path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    if not isinstance(rows, list) or not rows:
        print(f"refused: {path}: the input must be a non-empty JSON list of rows", file=sys.stderr)
        raise SystemExit(2)
    bad = [
        f"{r.get('id', f'#{i}') if isinstance(r, dict) else f'#{i}'}: {problem}"
        for i, r in enumerate(rows)
        if (problem := _row_problem(r))
    ]
    ids = [r["id"] for r in rows if isinstance(r, dict) and isinstance(r.get("id"), str)]
    bad += [f"{dup}: duplicate id" for dup in sorted({i for i in ids if ids.count(i) > 1})]
    if bad:
        print("refused (fix the rows BEFORE the run): " + "; ".join(bad), file=sys.stderr)
        raise SystemExit(2)
    return rows


def _urls_of(tool_input: dict[str, Any]) -> list[str]:
    urls = tool_input.get("urls")
    if isinstance(urls, list):
        return [u for u in urls if isinstance(u, str)]
    url = tool_input.get("url")
    return [url] if isinstance(url, str) else []


def harvest(roots: list[Path], *, since: str) -> list[dict[str, Any]]:
    """Distinct URLs `fabrik-researcher` seats passed to a raw fetch on or after `since` (YYYY-MM-DD)."""
    seen: dict[str, dict[str, Any]] = {}
    for root in dict.fromkeys(
        r.resolve() for r in roots
    ):  # the fleet's projects dirs are symlinks to one tree
        for meta in sorted(root.glob("*/*/subagents/agent-*.meta.json")):
            try:
                if (
                    json.loads(meta.read_text(encoding="utf-8")).get("agentType")
                    != "fabrik-researcher"
                ):
                    continue
            except (OSError, json.JSONDecodeError, AttributeError):
                continue
            transcript = meta.with_name(meta.name.replace(".meta.json", ".jsonl"))
            if not transcript.exists():
                continue
            for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict) or str(rec.get("timestamp", ""))[:10] < since:
                    continue
                content = (rec.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") not in FETCH_TOOLS or not isinstance(
                        block.get("input"), dict
                    ):
                        continue
                    for url in _urls_of(block["input"]):
                        seen.setdefault(
                            url,
                            {
                                "url": url,
                                "tool": block["name"],
                                "transcript": str(transcript),
                                "timestamp": rec.get("timestamp"),
                            },
                        )
    return sorted(seen.values(), key=lambda r: r["url"])


def _default_roots() -> list[Path]:
    home = Path.home()
    return [home / ".claude" / "projects", *sorted((home / ".claude-fleet").glob("*/projects"))]


def _write(out: str | None, payload: Any) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    print(text)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "input", nargs="?", help="ledger input JSON (rows with expected outcomes fixed beforehand)"
    )
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--probe", metavar="URL", help="initialize + tools/list against this MCP endpoint"
    )
    mode.add_argument(
        "--harvest", action="store_true", help="list researcher-seat fetch URLs from transcripts"
    )
    ap.add_argument(
        "--since",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=30),
        help="harvest: keep calls on or after this date, YYYY-MM-DD (default: 30 days ago)",
    )
    ap.add_argument("--server", default=DEFAULT_SERVER, help="ledger: the fabrik-scrape endpoint")
    ap.add_argument("--out", help="also write the JSON result to this path")
    args = ap.parse_args(argv)
    if (args.probe or args.harvest) and args.input:
        ap.error("an input file runs the ledger; it cannot be combined with --probe or --harvest")
    if args.probe:
        try:
            result = probe(args.probe)
        except (McpError, httpx.HTTPError) as exc:
            print(f"probe failed: {args.probe}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        _write(args.out, result)
        return 0 if "scrape" in result["tools"] else 1
    if args.harvest:
        _write(args.out, harvest(_default_roots(), since=args.since.isoformat()))
        return 0
    if not args.input:
        ap.error("give --probe URL, --harvest, or a ledger input file")
    rows = load_rows(Path(args.input))
    client = McpClient(args.server)
    try:
        results = run_ledger(rows, client)
    finally:
        client.close()
    _write(
        args.out,
        {
            "ran_at": datetime.now(UTC).isoformat(),
            "server": args.server,
            "rows": results,
            "passed": sum(r["grade"] == "PASS" for r in results),
            "total": len(results),
        },
    )
    return 0 if all(r["grade"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
