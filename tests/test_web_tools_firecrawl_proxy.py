"""W-6f71fc4e (hub W-10146d20 slice 1a, D-1100): every Firecrawl payload pins ``proxy`` to ``"basic"`` unless the caller
chooses one — scrape (sync and async) top-level, crawl and search in ``scrapeOptions``. The LLM tools
(``execute_web_tool``) never read a proxy from the model's ``arguments``: a direct caller passes ``firecrawl_proxy=``.
Firecrawl's own default is ``"auto"``. Hermetic: httpx.MockTransport, a fake key."""

# Vendored from fabrik-lib web-tools/test_web_tools_firecrawl_proxy.py at c7ab67e4, retargeted at the hub's
# libs/web_tools.py: a later re-vendor that drops the basic-proxy pin turns this file red (W-10146d20, plan 3
# Phase B step 2). Re-copy it with the module on every web-tools re-vendor.

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

# The hub's vendored copy, loaded under a private name: a bare `import web_tools` could bind the frozen pool copy
# `libs/subagents/web_tools.py` (D-547) when another test put that directory on sys.path first.
_PATH = Path(__file__).resolve().parents[1] / "libs" / "web_tools.py"
_spec = importlib.util.spec_from_file_location("hub_libs_web_tools", _PATH)
assert _spec and _spec.loader
_wt = importlib.util.module_from_spec(_spec)
sys.modules["hub_libs_web_tools"] = _wt
_spec.loader.exec_module(_wt)
WebToolsConfig, a_firecrawl_scrape = _wt.WebToolsConfig, _wt.a_firecrawl_scrape
a_firecrawl_search, execute_web_tool = _wt.a_firecrawl_search, _wt.execute_web_tool

Handler = Callable[[httpx.Request], httpx.Response]
TOOLS = ["web_scrape", "web_crawl", "a_scrape", "a_search"]


def _recorder() -> tuple[list[dict[str, Any]], Handler]:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            bodies.append(json.loads(request.content))
        if request.url.path.endswith("/crawl"):
            return httpx.Response(200, json={"id": "j"})
        if "/crawl/" in request.url.path:
            return httpx.Response(200, json={"status": "completed", "data": []})
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"data": {"web": []}})
        return httpx.Response(200, json={"data": {"markdown": "x"}})

    return bodies, handler


def _call(tool: str, proxy: Any, handler: Handler) -> Any:
    """The caller's choice of proxy, through each entry point's own channel: `firecrawl_proxy=` for the LLM tools,
    `args["proxy"]` for the async helpers."""
    cfg = WebToolsConfig(firecrawl_api_key="fk")
    if tool.startswith("web_"):
        return execute_web_tool(
            tool,
            {"url": "https://example.com"},
            client=httpx.Client(transport=httpx.MockTransport(handler)),
            firecrawl_proxy=proxy,
        )
    if tool == "a_scrape":
        return asyncio.run(
            a_firecrawl_scrape(
                {"url": "https://example.com", "proxy": proxy},
                config=cfg,
                client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
            )
        )
    return asyncio.run(
        a_firecrawl_search(
            {"query": "q", "market": "Germany", "proxy": proxy},
            config=cfg,
            client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        )
    )


def _sent_proxy(tool: str, body: dict[str, Any]) -> Any:
    return body["proxy"] if tool in ("web_scrape", "a_scrape") else body["scrapeOptions"]["proxy"]


def test_a_scrape_sends_proxy_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    bodies, handler = _recorder()
    actions = [{"type": "wait", "milliseconds": 1}]
    res = execute_web_tool(
        "web_scrape",
        {"url": "https://example.com", "formats": ["links"], "actions": actions},
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert res.ok, res
    assert [b.get("proxy") for b in bodies] == ["basic"]
    # whole-plan review: the payload was rebuilt — its other fields still go out as before
    assert bodies[0]["url"] == "https://example.com" and bodies[0]["formats"] == ["links"]
    assert bodies[0]["actions"] == actions


def test_a_crawl_sends_scrape_options_proxy_basic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    bodies, handler = _recorder()
    res = execute_web_tool(
        "web_crawl",
        {"url": "https://example.com"},
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert res.ok, res
    # formats named beside the proxy: the poll reads `markdown`, whatever Firecrawl does with a partial scrapeOptions
    assert [b.get("scrapeOptions") for b in bodies] == [{"formats": ["markdown"], "proxy": "basic"}]
    assert "proxy" not in bodies[0]  # the crawl body has no top-level proxy field
    # whole-plan review: the body was rebuilt — url and the clamped default limit still go out
    assert bodies[0]["url"] == "https://example.com" and bodies[0]["limit"] == 20


@pytest.mark.parametrize(
    ("limit", "sent"), [(0, 1), (5, 5), (10**9, 20)], ids=["below", "inside", "above"]
)
def test_a_crawl_s_limit_is_still_clamped(
    monkeypatch: pytest.MonkeyPatch, limit: int, sent: int
) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    bodies, handler = _recorder()
    res = execute_web_tool(
        "web_crawl",
        {"url": "https://example.com", "limit": limit},
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert res.ok, res
    assert bodies[0]["limit"] == sent


@pytest.mark.parametrize("tool", TOOLS)
def test_a_refused_proxy_writes_no_log_line(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch, tool: str
) -> None:
    # whole-plan review: the payload (and its proxy) is built before the call is logged, so a refusal is no line
    import logging

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    caplog.set_level(logging.WARNING, logger="web_tools.firecrawl")
    _, handler = _recorder()
    assert not _call(tool, 5, handler).ok
    assert [r for r in caplog.records if r.name == "web_tools.firecrawl"] == []


def test_an_async_scrape_sends_proxy_basic() -> None:
    bodies, handler = _recorder()
    assert _call("a_scrape", None, handler).ok
    assert [b.get("proxy") for b in bodies] == ["basic"]


def test_a_search_still_sends_scrape_options_proxy_basic() -> None:
    bodies, handler = _recorder()
    assert _call("a_search", None, handler).ok
    assert [b["scrapeOptions"]["proxy"] for b in bodies] == ["basic"]


@pytest.mark.parametrize("tool", ["web_scrape", "web_crawl"])
@pytest.mark.parametrize("model_proxy", ["auto", "enhanced", "stealth", 5])
def test_the_model_s_proxy_argument_is_ignored(
    monkeypatch: pytest.MonkeyPatch, tool: str, model_proxy: Any
) -> None:
    # design panel: the tool schemas do not declare `proxy`, and execute_web_tool does not enforce them — a model's
    # extra key (or a prompt-injected page's) must not choose the proxy, nor fail a call that ignored it before
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    bodies, handler = _recorder()
    res = execute_web_tool(
        tool,
        {"url": "https://example.com", "proxy": model_proxy},
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert res.ok, res
    assert _sent_proxy(tool, bodies[0]) == "basic"


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize(
    ("given", "sent"),
    [
        ("enhanced", "enhanced"),
        (None, "basic"),
        ("", "basic"),
        ("   ", "basic"),
        (" Enhanced ", "enhanced"),
        ("stealth", "stealth"),
        (0, "basic"),
        (False, "basic"),
    ],
    ids=["explicit", "none", "empty", "blank", "normalised", "unknown-string", "zero", "false"],
)
def test_a_caller_s_proxy_passes_through_normalised_and_a_falsy_or_blank_one_falls_back(
    monkeypatch: pytest.MonkeyPatch, tool: str, given: Any, sent: str
) -> None:
    # a string is the API's to judge (as `formats` is): no frozen enum to re-vendor when Firecrawl renames a value
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    bodies, handler = _recorder()
    assert _call(tool, given, handler).ok
    assert _sent_proxy(tool, bodies[0]) == sent


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("bad", [5, True, ["basic"]], ids=["int", "bool", "list"])
def test_a_non_string_proxy_is_refused_with_no_request(
    monkeypatch: pytest.MonkeyPatch, tool: str, bad: Any
) -> None:
    # plan review round 1: any value was str()-ed and sent to the paid API
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"data": {"markdown": "x"}})

    res = _call(tool, bad, handler)
    assert not res.ok and sent == [], (res, sent)
    assert "proxy must be a string" in (res.error or ""), res


@pytest.mark.parametrize("tool", ["web_scrape", "web_crawl"])
@pytest.mark.parametrize("arguments", [None, ["x"], "s"], ids=["none", "list", "str"])
def test_an_unset_key_is_still_reported_first(
    monkeypatch: pytest.MonkeyPatch, tool: str, arguments: Any
) -> None:
    # Phase A scoped review: copying `arguments` to add the proxy ran before the key check, so an unset key with bad
    # arguments said "bad response/args" instead of the documented "FIRECRAWL_API_KEY not set"
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    _, handler = _recorder()
    res = execute_web_tool(
        tool, arguments, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert not res.ok and res.error == "FIRECRAWL_API_KEY not set", res


@pytest.mark.parametrize("tool", ["web_scrape", "web_crawl"])
def test_arguments_reach_the_tool_as_given(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    # Phase A scoped review: a dict subclass's own lookup (here a default url) was lost when `arguments` was copied
    from collections import defaultdict

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    bodies, handler = _recorder()
    arguments: defaultdict[str, Any] = defaultdict(lambda: "https://example.com")
    res = execute_web_tool(
        tool, arguments, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert res.ok, res
    assert bodies[0]["url"] == "https://example.com"
