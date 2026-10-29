"""The MCP server: one tool, `scrape`, with the design's parameters. Needs the MCP SDK v2 (`mcp>=2.3,<3`); skipped
where it is absent or older (`mcp.server.mcpserver` is v2's module).

Run: python -m pytest tests -q   (from web-scrape-mcp/, in a venv holding mcp 2.x)
"""

from __future__ import annotations

import asyncio
from typing import Any
import os
import sys

import pytest

pytest.importorskip("mcp.server.mcpserver")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from web_scrape_mcp import Deps, build_server  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_scrape import LONG, FakeFetch, Page, deps  # noqa: E402


def _server(fetch: FakeFetch) -> object:
    d: Deps = deps(fetch)
    return build_server(d)


def test_the_server_lists_exactly_one_tool_with_the_design_parameters() -> None:
    server = _server(FakeFetch(Page(text=LONG, content_type="text/plain")))
    tools = asyncio.run(server.list_tools())  # type: ignore[attr-defined]
    assert [t.name for t in tools] == ["scrape"]
    props = tools[0].input_schema["properties"]
    assert set(props) == {"url", "render", "max_length", "start_index", "max_age_s"}
    assert props["render"].get("default") == "auto" and props["max_length"].get("default") == 20_000
    assert props["start_index"].get("default") == 0 and props["max_age_s"].get("default") == 0
    assert tools[0].input_schema.get("required") == ["url"]


def test_a_call_returns_the_contract_dict() -> None:
    server = _server(FakeFetch(Page(text=LONG, content_type="text/plain")))
    result = asyncio.run(server.call_tool("scrape", {"url": "https://docs.test/p"}))  # type: ignore[attr-defined]
    payload = result.structured_content
    if payload is not None and "result" in payload and isinstance(payload["result"], dict):
        payload = payload["result"]
    assert payload["status"] == 200 and payload["path"] == "static" and payload["markdown"].startswith("word")


def test_a_blocked_page_comes_back_as_the_blocked_dict() -> None:
    server = _server(FakeFetch(Page(status=404, text="gone")))
    result = asyncio.run(server.call_tool("scrape", {"url": "https://docs.test/p"}))  # type: ignore[attr-defined]
    payload = result.structured_content
    if payload is not None and "result" in payload and isinstance(payload["result"], dict):
        payload = payload["result"]
    assert payload == {"blocked": True, "reason": "http-404", "status": 404}


def test_b1_the_payload_is_the_bare_contract_dict() -> None:
    from test_scrape import SUCCESS_KEYS

    server = _server(FakeFetch(Page(text=LONG, content_type="text/plain")))
    result = asyncio.run(server.call_tool("scrape", {"url": "https://docs.test/p"}))  # type: ignore[attr-defined]
    assert set(result.structured_content) == SUCCESS_KEYS


def test_b1_a_value_error_reaches_the_agent_with_its_message() -> None:
    """Over the protocol (the SDK's in-memory client), as an agent sees it: an error result carrying the message."""
    from mcp.client.client import Client

    server = _server(FakeFetch(Page(text="a short page of text", content_type="text/plain")))

    async def call() -> Any:
        async with Client(server) as client:
            return await client.call_tool("scrape", {"url": "https://docs.test/p", "start_index": 99_999})

    result = asyncio.run(call())
    text = " ".join(getattr(c, "text", "") for c in result.content)
    assert result.is_error is True and "past the end" in text


def test_b1_the_server_carries_its_instructions() -> None:
    from web_scrape_mcp import INSTRUCTIONS

    server = _server(FakeFetch(Page()))
    assert server.instructions == INSTRUCTIONS and "bot-wall" in INSTRUCTIONS  # type: ignore[attr-defined]
