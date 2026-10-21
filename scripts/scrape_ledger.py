#!/usr/bin/env python3
# AFTER-EDIT: tests/test_scrape_ledger.py, docs/reference/fabrik-scrape-mcp.md
"""Probe the fabrik-scrape MCP server, harvest the URLs research seats fetch, and grade a capability ledger.

Three modes (W-10146d20, plan 3 Phase B; spec docs/superpowers/specs/2026-10-21-own-scrape-tools-design.md § Test
ledger):

  --probe <url>                          MCP `initialize` + `tools/list`; prints serverInfo and the tool names.
                                         Exit 0 when `scrape` is listed, 1 otherwise.
  --harvest --since <YYYY-MM-DD> --out   every URL a `fabrik-researcher` seat passed to a raw fetch
                                         (firecrawl_scrape, web_fetch_exa, WebFetch) in a subagent transcript.
  <input.json> [--server <url>] --out    runs each row's URL through `scrape` and grades it.

A ledger row is ``{id, url, kind, expected, facts, fact_source}``. ``expected`` is fixed BEFORE the run: ``pass`` or
the ``blocked`` reason the spec predicts (``bot-wall``, ``unsupported``, ``http-404`` …); a row without it is refused
(exit 2) before any fetch, so no outcome is judged after the fact. PASS for ``expected: pass`` = every fact string found
in the markdown (whitespace-normalised substring) AND a clean ratio — letters, digits and spaces over all characters —
of at least 0.6. PASS for a blocked expectation = the result is blocked with exactly that reason. Fact strings are
copied to the output unchanged.

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
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

CLEAN_FLOOR = 0.6
FETCH_TOOLS = ("mcp__firecrawl__firecrawl_scrape", "mcp__exa__web_fetch_exa", "WebFetch")
DEFAULT_SERVER = "http://127.0.0.1:8034/mcp"
_ACCEPT = "application/json, text/event-stream"


class McpError(RuntimeError):
    """The server answered with a JSON-RPC error or a body this client cannot read."""


def _decode(resp: httpx.Response) -> dict[str, Any]:
    """The JSON-RPC message in a streamable-HTTP reply: a JSON body, or the last `data:` event of an SSE stream."""
    if "text/event-stream" in resp.headers.get("content-type", ""):
        datas = [line[5:].strip() for line in resp.text.splitlines() if line.startswith("data:")]
        if not datas:
            raise McpError("an event stream with no data line")
        msg: dict[str, Any] = json.loads(datas[-1])
    else:
        msg = resp.json()
    if "error" in msg:
        raise McpError(f"JSON-RPC error: {msg['error']}")
    return msg


class McpClient:
    """A minimal MCP streamable-HTTP client: initialize, list tools, call a tool."""

    def __init__(self, url: str, *, transport: httpx.BaseTransport | None = None, timeout_s: float = 120.0) -> None:
        self.url = url
        self._http = httpx.Client(transport=transport, timeout=timeout_s)
        self._session: str | None = None
        self._next_id = 0
        self.server_info: dict[str, Any] = {}

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        headers = {"accept": _ACCEPT, "content-type": "application/json"}
        if self._session:
            headers["mcp-session-id"] = self._session
        resp = self._http.post(self.url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp

    def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._next_id += 1
        resp = self._post({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params})
        if self._session is None and resp.headers.get("mcp-session-id"):
            self._session = resp.headers["mcp-session-id"]
        result: dict[str, Any] = _decode(resp).get("result", {})
        return result

    def initialize(self) -> dict[str, Any]:
        result = self._request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "scrape_ledger", "version": "1"},
        })
        self.server_info = result.get("serverInfo", {})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result

    def list_tools(self) -> list[str]:
        if not self.server_info:
            self.initialize()
        return [t["name"] for t in self._request("tools/list", {}).get("tools", [])]

    def scrape(self, url: str, **args: Any) -> dict[str, Any]:
        if not self.server_info:
            self.initialize()
        result = self._request("tools/call", {"name": "scrape", "arguments": {"url": url, **args}})
        if result.get("isError"):
            text = " ".join(c.get("text", "") for c in result.get("content", []))
            raise McpError(f"tool error: {text}")
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and structured:
            return structured
        for item in result.get("content", []):
            if item.get("type") == "text":
                parsed: dict[str, Any] = json.loads(item["text"])
                return parsed
        raise McpError("a tool result with no readable content")


def probe(url: str, *, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    client = McpClient(url, transport=transport)
    client.initialize()
    return {"serverInfo": client.server_info, "tools": client.list_tools()}


def clean_ratio(text: str) -> float:
    """Letters, digits and spaces over all characters (the spec's markup-noise measure); 0.0 for empty text."""
    if not text:
        return 0.0
    return sum(1 for ch in text if ch.isalnum() or ch == " ") / len(text)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def grade(row: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """One ledger row's verdict; the row's own fields, fact strings included, are carried unchanged."""
    out = dict(row)
    facts: list[str] = list(row.get("facts", []))
    if result.get("blocked"):
        out.update(path=None, status=result.get("status"), blocked_reason=result.get("reason"),
                   facts_found=0, facts_total=len(facts), missing=facts, clean_ratio=0.0)
        out["grade"] = "PASS" if row["expected"] == result.get("reason") else "FAIL"
        return out
    text = _norm(result.get("markdown", ""))
    missing = [f for f in facts if _norm(f) not in text]
    ratio = round(clean_ratio(result.get("markdown", "")), 3)
    out.update(path=result.get("path"), status=result.get("status"), blocked_reason=None,
               facts_found=len(facts) - len(missing), facts_total=len(facts), missing=missing, clean_ratio=ratio,
               truncated=result.get("truncated"), short=result.get("short"))
    out["grade"] = "PASS" if row["expected"] == "pass" and not missing and ratio >= CLEAN_FLOOR else "FAIL"
    return out


def run_ledger(rows: list[dict[str, Any]], client: McpClient) -> list[dict[str, Any]]:
    return [grade(row, client.scrape(row["url"])) for row in rows]


def load_rows(path: Path) -> list[dict[str, Any]]:
    """The ledger input; a row without `expected` (or `id`, `url`, `facts`, `fact_source`) is refused, exit 2."""
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit(f"{path}: the input must be a JSON list of rows") from None
    bad = [r.get("id", f"#{i}") for i, r in enumerate(rows)
           if not all(k in r for k in ("id", "url", "expected", "facts", "fact_source"))]
    if bad:
        print(f"refused: rows missing id/url/expected/facts/fact_source (fix them BEFORE the run): {bad}",
              file=sys.stderr)
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
    for root in roots:
        for meta in sorted(root.glob("*/*/subagents/agent-*.meta.json")):
            try:
                if json.loads(meta.read_text(encoding="utf-8")).get("agentType") != "fabrik-researcher":
                    continue
            except (OSError, json.JSONDecodeError):
                continue
            transcript = meta.with_name(meta.name.replace(".meta.json", ".jsonl"))
            if not transcript.exists():
                continue
            for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(rec.get("timestamp", ""))[:10] < since:
                    continue
                content = (rec.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    if block.get("name") not in FETCH_TOOLS:
                        continue
                    for url in _urls_of(block.get("input") or {}):
                        seen.setdefault(url, {"url": url, "tool": block["name"], "transcript": str(transcript),
                                              "timestamp": rec.get("timestamp")})
    return sorted(seen.values(), key=lambda r: r["url"])


def _default_roots() -> list[Path]:
    home = Path.home()
    return [home / ".claude" / "projects", *sorted((home / ".claude-fleet").glob("*/projects"))]


def _write(out: str | None, payload: Any) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8")
    print(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input", nargs="?", help="ledger input JSON (rows with expected outcomes fixed beforehand)")
    ap.add_argument("--probe", metavar="URL", help="initialize + tools/list against this MCP endpoint")
    ap.add_argument("--harvest", action="store_true", help="list researcher-seat fetch URLs from transcripts")
    ap.add_argument("--since", default="2026-10-01", help="harvest: keep calls on or after this date")
    ap.add_argument("--server", default=DEFAULT_SERVER, help="ledger: the fabrik-scrape endpoint")
    ap.add_argument("--out", help="also write the JSON result to this path")
    args = ap.parse_args(argv)
    if args.probe:
        result = probe(args.probe)
        _write(args.out, result)
        return 0 if "scrape" in result["tools"] else 1
    if args.harvest:
        _write(args.out, harvest(_default_roots(), since=args.since))
        return 0
    if not args.input:
        ap.error("give --probe URL, --harvest, or a ledger input file")
    rows = load_rows(Path(args.input))
    results = run_ledger(rows, McpClient(args.server))
    _write(args.out, {"ran_at": datetime.now(UTC).isoformat(), "server": args.server, "rows": results,
                      "passed": sum(r["grade"] == "PASS" for r in results), "total": len(results)})
    return 0 if all(r["grade"] == "PASS" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
