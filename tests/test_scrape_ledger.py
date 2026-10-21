"""scripts/scrape_ledger.py — the fabrik-scrape probe, the researcher-URL harvest and the capability ledger (W-10146d20).

The MCP server is faked with an httpx.MockTransport that speaks streamable-HTTP JSON-RPC, so no socket opens. One test
per behaviour of plan 3 Phase B: the probe reads serverInfo and the tool list; a ledger row's fact strings come back
byte-identical; PASS needs every fact AND a clean ratio of at least 0.6; a blocked row passes only on its expected
reason; a row without `expected` is refused before any fetch; the harvest keeps fabrik-researcher seats only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("scrape_ledger", ROOT / "scripts" / "scrape_ledger.py")
assert _spec and _spec.loader
sl = importlib.util.module_from_spec(_spec)
sys.modules["scrape_ledger"] = sl
_spec.loader.exec_module(sl)

PAGES = {
    "https://good.example/": {
        "status": 200,
        "final_url": "https://good.example/",
        "content_type": "text/html",
        "title": "Good",
        "markdown": "The bisect module provides support for maintaining a list in sorted order.",
        "truncated": False,
        "short": True,
        "path": "static",
        "fetched_at": "2026-10-21T00:00:00Z",
    },
    "https://noisy.example/": {
        "status": 200,
        "final_url": "https://noisy.example/",
        "content_type": "text/html",
        "title": "Noisy",
        "markdown": "sorted order {{{}}} <<<>>> ###### ****** ////// |||||| ~~~~~~ ^^^^^^ %%%%%% @@@@@@",
        "truncated": False,
        "short": True,
        "path": "static",
        "fetched_at": "2026-10-21T00:00:00Z",
    },
    "https://wall.example/": {"blocked": True, "reason": "bot-wall", "status": 403},
}


def _fake_server(sse: bool = False) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        msg = json.loads(request.content)
        if "id" not in msg:  # a notification
            return httpx.Response(202)
        if msg["method"] == "initialize":
            result = {"protocolVersion": "2025-06-18", "serverInfo": {"name": "fabrik-scrape", "version": "1"}, "capabilities": {}}
        elif msg["method"] == "tools/list":
            assert request.headers.get("mcp-session-id") == "s1", "the session id must be sent back"
            result = {"tools": [{"name": "scrape", "inputSchema": {}}]}
        elif msg["method"] == "tools/call":
            page = PAGES[msg["params"]["arguments"]["url"]]
            result = {"content": [{"type": "text", "text": json.dumps(page)}], "structuredContent": page, "isError": False}
        else:
            return httpx.Response(400)
        body = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        headers = {"mcp-session-id": "s1"}
        if sse:
            return httpx.Response(200, text=f"event: message\ndata: {json.dumps(body)}\n\n",
                                  headers={**headers, "content-type": "text/event-stream"})
        return httpx.Response(200, json=body, headers=headers)

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("sse", [False, True])
def test_probe_reads_server_info_and_the_scrape_tool(sse: bool) -> None:
    out = sl.probe("http://127.0.0.1:8034/mcp", transport=_fake_server(sse))
    assert out["serverInfo"]["name"] == "fabrik-scrape"
    assert out["tools"] == ["scrape"]


def test_ledger_row_passes_on_every_fact_and_a_clean_ratio_and_keeps_fact_strings_byte_identical() -> None:
    facts = ["maintaining a list in sorted order", "The bisect module"]
    row = {"id": "U1", "url": "https://good.example/", "kind": "docs page", "expected": "pass", "facts": list(facts),
           "fact_source": "WebFetch 2026-10-21"}
    client = sl.McpClient("http://127.0.0.1:8034/mcp", transport=_fake_server())
    [res] = sl.run_ledger([row], client)
    assert res["grade"] == "PASS"
    assert res["facts"] == facts and res["facts_found"] == 2 and res["facts_total"] == 2
    assert res["clean_ratio"] >= 0.6
    for key in ("id", "url", "kind", "expected", "facts", "fact_source", "path", "status", "blocked_reason", "missing"):
        assert key in res


def test_ledger_row_fails_on_a_missing_fact_or_a_low_clean_ratio() -> None:
    client = sl.McpClient("http://127.0.0.1:8034/mcp", transport=_fake_server())
    missing = {"id": "A", "url": "https://good.example/", "kind": "docs page", "expected": "pass",
               "facts": ["not on this page"], "fact_source": "x"}
    noisy = {"id": "B", "url": "https://noisy.example/", "kind": "docs page", "expected": "pass",
             "facts": ["sorted order"], "fact_source": "x"}
    a, b = sl.run_ledger([missing, noisy], client)
    assert a["grade"] == "FAIL" and a["missing"] == ["not on this page"]
    assert b["grade"] == "FAIL" and b["facts_found"] == 1 and b["clean_ratio"] < 0.6


def test_a_blocked_row_passes_only_on_its_expected_reason() -> None:
    client = sl.McpClient("http://127.0.0.1:8034/mcp", transport=_fake_server())
    right = {"id": "U6", "url": "https://wall.example/", "kind": "review site", "expected": "bot-wall", "facts": [],
             "fact_source": "x"}
    wrong = {**right, "id": "U6b", "expected": "pass"}
    other = {**right, "id": "U6c", "expected": "unsupported"}
    r, w, o = sl.run_ledger([right, wrong, other], client)
    assert r["grade"] == "PASS" and r["blocked_reason"] == "bot-wall" and r["status"] == 403
    assert w["grade"] == "FAIL" and o["grade"] == "FAIL"


def test_a_row_without_expected_is_refused_before_any_fetch(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500)

    path = tmp_path / "in.json"
    path.write_text(json.dumps([{"id": "X", "url": "https://good.example/", "facts": ["a"], "fact_source": "x"}]))
    with pytest.raises(SystemExit) as exc:
        sl.load_rows(path)
    assert exc.value.code == 2
    assert calls == []


def test_harvest_keeps_researcher_seats_and_extracts_each_fetch_url(tmp_path: Path) -> None:
    sub = tmp_path / "projects" / "-opt-x" / "sess" / "subagents"
    sub.mkdir(parents=True)

    def seat(name: str, agent_type: str, calls: list[tuple[str, dict]], ts: str) -> None:
        (sub / f"agent-{name}.meta.json").write_text(json.dumps({"agentType": agent_type}))
        lines = [json.dumps({"timestamp": ts, "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": n, "input": i} for n, i in calls]}})]
        (sub / f"agent-{name}.jsonl").write_text("\n".join(lines) + "\n")

    seat("r1", "fabrik-researcher", [("mcp__firecrawl__firecrawl_scrape", {"url": "https://a.example/"}),
                                     ("mcp__exa__web_fetch_exa", {"urls": ["https://b.example/", "https://a.example/"]}),
                                     ("WebFetch", {"url": "https://c.example/", "prompt": "p"}),
                                     ("Read", {"file_path": "/x"})], "2026-10-05T10:00:00Z")
    seat("r2", "fabrik-researcher", [("WebFetch", {"url": "https://old.example/"})], "2026-09-20T10:00:00Z")
    seat("f1", "fabrik-reviewer", [("WebFetch", {"url": "https://reviewer.example/"})], "2026-10-05T10:00:00Z")
    rows = sl.harvest([tmp_path / "projects"], since="2026-10-01")
    assert sorted(r["url"] for r in rows) == ["https://a.example/", "https://b.example/", "https://c.example/"]
    assert {r["tool"] for r in rows} == {"mcp__firecrawl__firecrawl_scrape", "mcp__exa__web_fetch_exa", "WebFetch"}
