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
_spec = importlib.util.spec_from_file_location(
    "scrape_ledger", ROOT / "scripts" / "scrape_ledger.py"
)
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
            result = {
                "protocolVersion": "2025-06-18",
                "serverInfo": {"name": "fabrik-scrape", "version": "1"},
                "capabilities": {},
            }
        elif msg["method"] == "tools/list":
            assert request.headers.get("mcp-session-id") == "s1", "the session id must be sent back"
            result = {"tools": [{"name": "scrape", "inputSchema": {}}]}
        elif msg["method"] == "tools/call":
            page = PAGES[msg["params"]["arguments"]["url"]]
            result = {
                "content": [{"type": "text", "text": json.dumps(page)}],
                "structuredContent": page,
                "isError": False,
            }
        else:
            return httpx.Response(400)
        body = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        headers = {"mcp-session-id": "s1"}
        if sse:
            return httpx.Response(
                200,
                text=f"event: message\ndata: {json.dumps(body)}\n\n",
                headers={**headers, "content-type": "text/event-stream"},
            )
        return httpx.Response(200, json=body, headers=headers)

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("sse", [False, True])
def test_probe_reads_server_info_and_the_scrape_tool(sse: bool) -> None:
    out = sl.probe("http://127.0.0.1:8034/mcp", transport=_fake_server(sse))
    assert out["serverInfo"]["name"] == "fabrik-scrape"
    assert out["tools"] == ["scrape"]


def test_ledger_row_passes_on_every_fact_and_a_clean_ratio_and_keeps_fact_strings_byte_identical() -> (
    None
):
    facts = ["maintaining a list in sorted order", "The bisect module"]
    row = {
        "id": "U1",
        "url": "https://good.example/",
        "kind": "docs page",
        "expected": "pass",
        "facts": list(facts),
        "fact_source": "WebFetch 2026-10-21",
    }
    client = sl.McpClient("http://127.0.0.1:8034/mcp", transport=_fake_server())
    [res] = sl.run_ledger([row], client)
    assert res["grade"] == "PASS"
    assert res["facts"] == facts and res["facts_found"] == 2 and res["facts_total"] == 2
    assert res["clean_ratio"] >= 0.6
    for key in (
        "id",
        "url",
        "kind",
        "expected",
        "facts",
        "fact_source",
        "path",
        "status",
        "blocked_reason",
        "missing",
    ):
        assert key in res


def test_ledger_row_fails_on_a_missing_fact_or_a_low_clean_ratio() -> None:
    client = sl.McpClient("http://127.0.0.1:8034/mcp", transport=_fake_server())
    missing = {
        "id": "A",
        "url": "https://good.example/",
        "kind": "docs page",
        "expected": "pass",
        "facts": ["not on this page"],
        "fact_source": "x",
    }
    noisy = {
        "id": "B",
        "url": "https://noisy.example/",
        "kind": "docs page",
        "expected": "pass",
        "facts": ["sorted order"],
        "fact_source": "x",
    }
    a, b = sl.run_ledger([missing, noisy], client)
    assert a["grade"] == "FAIL" and a["missing"] == ["not on this page"]
    assert b["grade"] == "FAIL" and b["facts_found"] == 1 and b["clean_ratio"] < 0.6


def test_a_blocked_row_passes_only_on_its_expected_reason() -> None:
    client = sl.McpClient("http://127.0.0.1:8034/mcp", transport=_fake_server())
    right = {
        "id": "U6",
        "url": "https://wall.example/",
        "kind": "review site",
        "expected": "bot-wall",
        "facts": [],
        "fact_source": "x",
    }
    wrong = {**right, "id": "U6b", "expected": "pass"}
    other = {**right, "id": "U6c", "expected": "unsupported"}
    r, w, o = sl.run_ledger([right, wrong, other], client)
    assert r["grade"] == "PASS" and r["blocked_reason"] == "bot-wall" and r["status"] == 403
    assert w["grade"] == "FAIL" and o["grade"] == "FAIL"


LONG = (
    "alpha " * 5000 + "the needle fact sits deep in the page " + "omega " * 1000
)  # > 20 000 characters
STRADDLE = (
    "x" * 19_990 + " the fact across the chunk boundary " + "y" * 5_000
)  # spans characters 19 990-20 026


def _scripted_server(calls: list[dict], **mode: bool) -> httpx.MockTransport:
    """A fake with switchable faults: tool errors, JSON-RPC errors, text-only results, chunked pages, split SSE."""

    def handler(request: httpx.Request) -> httpx.Response:
        msg = json.loads(request.content)
        calls.append(
            {
                "method": msg.get("method"),
                "headers": dict(request.headers),
                "params": msg.get("params"),
            }
        )
        if "id" not in msg:
            return httpx.Response(202)
        if msg["method"] == "initialize":
            result = {
                "protocolVersion": "2025-06-18",
                "serverInfo": {"name": "fabrik-scrape"},
                "capabilities": {},
            }
        elif msg["method"] == "tools/call":
            args = msg["params"]["arguments"]
            if mode.get("rpc_error"):
                return httpx.Response(
                    200,
                    json={"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -1, "message": "x"}},
                )
            if mode.get("tool_error") and args["url"].endswith("bad/"):
                result = {
                    "content": [{"type": "text", "text": "Error executing tool scrape"}],
                    "isError": True,
                }
            elif mode.get("mid_block") and args.get("start_index", 0) > 0:
                page = {"blocked": True, "reason": "empty", "status": 200}
                result = {
                    "content": [{"type": "text", "text": json.dumps(page)}],
                    "structuredContent": page,
                }
            else:
                start, size = args.get("start_index", 0), 20_000
                source = STRADDLE if args["url"].endswith("straddle/") else LONG
                long_page = args["url"].endswith(("long/", "straddle/"))
                chunk = (
                    source[start : start + size]
                    if long_page
                    else PAGES["https://good.example/"]["markdown"]
                )
                page = {
                    **PAGES["https://good.example/"],
                    "markdown": chunk,
                    "truncated": bool(mode.get("endless"))
                    or (long_page and start + size < len(source)),
                }
                result = {"content": [{"type": "text", "text": json.dumps(page)}], "isError": False}
                if not mode.get("text_only"):
                    result["structuredContent"] = page
        else:
            result = {"tools": [{"name": "scrape"}]}
        body = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result})
        if mode.get("server_request_first"):
            # a server-to-client request that happens to reuse the id must not be taken for the response
            req = json.dumps({"jsonrpc": "2.0", "id": msg["id"], "method": "ping"})
            text = f"event: message\ndata: {req}\n\nevent: message\ndata: {body}\n\n"
            return httpx.Response(
                200,
                text=text,
                headers={"mcp-session-id": "s1", "content-type": "text/event-stream"},
            )
        if mode.get("split_sse"):
            # SSE joins data lines with a newline, so a server may split only where JSON allows whitespace
            text = (
                "event: message\ndata: "
                + body.replace(', "result": ', ',\ndata: "result": ', 1)
                + "\n\n"
            )
            assert text.count("data:") == 2
            return httpx.Response(
                200,
                text=text,
                headers={"mcp-session-id": "s1", "content-type": "text/event-stream"},
            )
        return httpx.Response(
            200, text=body, headers={"mcp-session-id": "s1", "content-type": "application/json"}
        )

    return httpx.MockTransport(handler)


def _row(rid: str, url: str, facts: object, expected: str = "pass") -> dict:
    return {
        "id": rid,
        "url": url,
        "kind": "k",
        "expected": expected,
        "facts": facts,
        "fact_source": "x",
    }


def test_a_failing_row_is_graded_fail_and_the_other_rows_still_run() -> None:
    client = sl.McpClient("http://h/mcp", transport=_scripted_server([], tool_error=True))
    good, bad = sl.run_ledger(
        [_row("G", "https://good/", ["sorted order"]), _row("B", "https://bad/", ["x"])], client
    )
    assert good["grade"] == "PASS"
    assert bad["grade"] == "FAIL" and "tool error" in bad["error"]


def test_a_json_rpc_error_is_a_row_fail_not_a_crash() -> None:
    client = sl.McpClient("http://h/mcp", transport=_scripted_server([], rpc_error=True))
    [res] = sl.run_ledger([_row("E", "https://good/", ["sorted order"])], client)
    assert res["grade"] == "FAIL" and "JSON-RPC error" in res["error"]


def test_a_result_without_structured_content_falls_back_to_its_text() -> None:
    client = sl.McpClient("http://h/mcp", transport=_scripted_server([], text_only=True))
    [res] = sl.run_ledger([_row("T", "https://good/", ["sorted order"])], client)
    assert res["grade"] == "PASS"


def test_an_sse_event_split_over_data_lines_is_joined() -> None:
    out = sl.probe("http://h/mcp", transport=_scripted_server([], split_sse=True))
    assert out["tools"] == ["scrape"]


def test_a_long_page_is_read_to_its_end_from_the_cache() -> None:
    calls: list[dict] = []
    client = sl.McpClient("http://h/mcp", transport=_scripted_server(calls))
    [res] = sl.run_ledger([_row("L", "https://long/", ["the needle fact sits deep"])], client)
    assert res["grade"] == "PASS" and res["chunks"] == 2 and res["truncated"] is False
    later = [c["params"]["arguments"] for c in calls if c["method"] == "tools/call"][1:]
    assert later and all(a["start_index"] > 0 and a["max_age_s"] > 0 for a in later)


def test_requests_after_initialize_carry_session_and_protocol_version() -> None:
    calls: list[dict] = []
    sl.probe("http://h/mcp", transport=_scripted_server(calls))
    after = [c["headers"] for c in calls[1:]]
    assert after and all(
        h.get("mcp-session-id") == "s1" and h.get("mcp-protocol-version") == "2025-06-18"
        for h in after
    )
    assert [c["method"] for c in calls].count("initialize") == 1


def test_initialize_runs_once_even_without_server_info() -> None:
    calls: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        msg = json.loads(request.content)
        calls.append(msg)
        if "id" not in msg:
            return httpx.Response(202)
        result = (
            {"protocolVersion": "2025-06-18"} if msg["method"] == "initialize" else {"tools": []}
        )
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": msg["id"], "result": result})

    sl.probe("http://h/mcp", transport=httpx.MockTransport(handler))
    assert [m.get("method") for m in calls].count("initialize") == 1


def test_fact_match_and_clean_ratio_follow_the_spec_harness() -> None:
    page = {"status": 200, "markdown": "The BISECT module", "path": "static"}
    assert sl.grade(_row("C", "https://x/", ["the bisect module"]), page)["grade"] == "PASS"
    assert sl.clean_ratio("Ã¢â‚¬â„¢ÃƒÂ©Ã‚Â°") == 0.0


@pytest.mark.parametrize(
    "rows, reason",
    [
        (
            [{"id": "X", "url": "https://x/", "facts": ["a"], "fact_source": "x"}],
            "missing expected",
        ),
        ([], "non-empty"),
        ({"a": 1}, "non-empty"),
        (["id url expected facts fact_source"], "not an object"),
        ([_row("F", "https://x/", [])], "at least one fact"),
        ([_row("F", "https://x/", [""])], "non-blank"),
        ([_row("F", "https://x/", "zq")], "non-blank"),
        ([_row("F", "https://x/", [], expected="Pass")], "unknown expected"),
        ([_row("F", "https://x/", [], expected="bot_wall")], "unknown expected"),
    ],
)
def test_the_input_is_refused_before_any_fetch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    rows: object,
    reason: str,
) -> None:
    built: list[str] = []
    monkeypatch.setattr(sl, "McpClient", lambda url, **kw: built.append(url))
    path = tmp_path / "in.json"
    path.write_text(json.dumps(rows))
    with pytest.raises(SystemExit) as exc:
        sl.main([str(path), "--out", str(tmp_path / "out.json")])
    assert exc.value.code == 2 and built == [] and reason in capsys.readouterr().err
    assert not (tmp_path / "out.json").exists()


def test_blocked_and_numbered_http_expectations_are_accepted(tmp_path: Path) -> None:
    path = tmp_path / "in.json"
    path.write_text(
        json.dumps(
            [
                _row("A", "https://x/", [], expected="bot-wall"),
                _row("B", "https://x/", [], expected="http-404"),
            ]
        )
    )
    assert len(sl.load_rows(path)) == 2


def test_probe_of_a_down_server_exits_1_with_a_message(capsys: pytest.CaptureFixture[str]) -> None:
    assert sl.main(["--probe", "http://127.0.0.1:9/mcp"]) == 1
    assert "probe failed" in capsys.readouterr().err


def test_an_input_file_cannot_be_combined_with_a_mode(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        sl.main([str(tmp_path / "in.json"), "--harvest"])
    assert exc.value.code == 2


def test_since_must_be_an_iso_date() -> None:
    with pytest.raises(SystemExit) as exc:
        sl.main(["--harvest", "--since", "2026-10-1"])
    assert exc.value.code == 2


def test_harvest_reads_a_symlinked_root_once_and_survives_odd_lines(tmp_path: Path) -> None:
    sub = tmp_path / "projects" / "-opt-x" / "sess" / "subagents"
    sub.mkdir(parents=True)
    (sub / "agent-r.meta.json").write_text(json.dumps({"agentType": "fabrik-researcher"}))
    good = {
        "timestamp": "2026-10-05T00:00:00Z",
        "message": {
            "content": [
                {"type": "tool_use", "name": "WebFetch", "input": {"url": "https://a.example/"}},
                {"type": "tool_use", "name": "WebFetch", "input": "not a dict"},
            ]
        },
    }
    (sub / "agent-r.jsonl").write_text(
        "\n".join([json.dumps([1, 2]), json.dumps(good), "{broken"]) + "\n"
    )
    (tmp_path / "alias").symlink_to(tmp_path / "projects")
    rows = sl.harvest([tmp_path / "alias", tmp_path / "projects"], since="2026-10-01")
    assert [r["url"] for r in rows] == ["https://a.example/"]
    # the alias is listed first: a harvest that walked it unresolved would cite the alias path
    assert rows[0]["transcript"].startswith(str((tmp_path / "projects").resolve()))


def test_a_chunk_blocked_mid_read_fails_the_row_as_incomplete() -> None:
    client = sl.McpClient("http://h/mcp", transport=_scripted_server([], mid_block=True))
    [res] = sl.run_ledger([_row("M", "https://long/", ["alpha"])], client)
    assert res["grade"] == "FAIL" and "incomplete" in res["error"]
    assert res["facts_found"] == 0 and res["missing"] == ["alpha"] and res["clean_ratio"] == 0.0


def test_a_fact_across_a_chunk_boundary_is_found() -> None:
    client = sl.McpClient("http://h/mcp", transport=_scripted_server([]))
    [res] = sl.run_ledger(
        [_row("S", "https://straddle/", ["the fact across the chunk boundary"])], client
    )
    assert res["grade"] == "PASS" and res["chunks"] == 2


def test_an_endlessly_truncated_page_stops_at_the_cap() -> None:
    client = sl.McpClient("http://h/mcp", transport=_scripted_server([], endless=True))
    page = client.read_page("https://good/")
    assert page["chunks"] == sl.MAX_CHUNKS and page["chunks_capped"] is True


def test_a_server_request_reusing_the_id_is_not_taken_for_the_response() -> None:
    out = sl.probe("http://h/mcp", transport=_scripted_server([], server_request_first=True))
    assert out["tools"] == ["scrape"]


@pytest.mark.parametrize(
    "rows, reason",
    [
        ([_row("A", None, ["a"])], "url must be"),
        ([_row("", "https://x/", ["a"])], "id must be"),
        ([_row("D", "https://x/", ["a"]), _row("D", "https://y/", ["b"])], "duplicate id"),
        ([_row("H", "https://x/", [], expected="http-200")], "unknown expected"),
    ],
)
def test_row_ids_urls_and_statuses_are_checked(
    tmp_path: Path, rows: list, reason: str, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "in.json"
    path.write_text(json.dumps(rows))
    with pytest.raises(SystemExit) as exc:
        sl.load_rows(path)
    assert exc.value.code == 2 and reason in capsys.readouterr().err


def test_harvest_keeps_researcher_seats_and_extracts_each_fetch_url(tmp_path: Path) -> None:
    sub = tmp_path / "projects" / "-opt-x" / "sess" / "subagents"
    sub.mkdir(parents=True)

    def seat(name: str, agent_type: str, calls: list[tuple[str, dict]], ts: str) -> None:
        (sub / f"agent-{name}.meta.json").write_text(json.dumps({"agentType": agent_type}))
        lines = [
            json.dumps(
                {
                    "timestamp": ts,
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "tool_use", "name": n, "input": i} for n, i in calls],
                    },
                }
            )
        ]
        (sub / f"agent-{name}.jsonl").write_text("\n".join(lines) + "\n")

    seat(
        "r1",
        "fabrik-researcher",
        [
            ("mcp__firecrawl__firecrawl_scrape", {"url": "https://a.example/"}),
            ("mcp__exa__web_fetch_exa", {"urls": ["https://b.example/", "https://a.example/"]}),
            ("WebFetch", {"url": "https://c.example/", "prompt": "p"}),
            ("Read", {"file_path": "/x"}),
        ],
        "2026-10-05T10:00:00Z",
    )
    seat(
        "r2",
        "fabrik-researcher",
        [("WebFetch", {"url": "https://old.example/"})],
        "2026-09-20T10:00:00Z",
    )
    seat(
        "f1",
        "fabrik-reviewer",
        [("WebFetch", {"url": "https://reviewer.example/"})],
        "2026-10-05T10:00:00Z",
    )
    rows = sl.harvest([tmp_path / "projects"], since="2026-10-01")
    assert sorted(r["url"] for r in rows) == [
        "https://a.example/",
        "https://b.example/",
        "https://c.example/",
    ]
    assert {r["tool"] for r in rows} == {
        "mcp__firecrawl__firecrawl_scrape",
        "mcp__exa__web_fetch_exa",
        "WebFetch",
    }
