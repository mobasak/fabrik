"""Phase A — web_tools.py: Exa/Firecrawl/Context7 HTTP tool executors (opt-in).

Highest-risk: the executors are env-keyed + hit the internet, and MUST stay total
(never raise) + bounded. All tests run OFFLINE via httpx.MockTransport (built-in,
no new dep) injected through the `client=` param.
"""

from __future__ import annotations

import httpx
import pytest

from subagents.web_tools import (
    WEB_TOOL_NAMES,
    WEB_TOOL_SCHEMAS,
    execute_web_tool,
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_web_search_missing_key_returns_error_and_no_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unset key → ok=False mentioning the env var, and NO HTTP call is made."""
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json={})

    res = execute_web_tool("web_search", {"query": "x"}, client=_client(handler))
    assert res.ok is False
    assert "EXA_API_KEY" in (res.error or "")
    assert calls == [], "made a network call without a key"


def test_web_search_parses_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXA_API_KEY", "k")

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["x-api-key"] == "k"
        assert str(req.url) == "https://api.exa.ai/search"
        return httpx.Response(
            200,
            json={
                "results": [{"title": "T", "url": "http://u", "text": "snippet here"}]
            },
        )

    res = execute_web_tool("web_search", {"query": "q"}, client=_client(handler))
    assert res.ok is True
    assert "T" in res.output and "http://u" in res.output and "snippet" in res.output


def test_web_search_brave_missing_key_returns_error_and_no_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    called: list = []

    def handler(req: httpx.Request) -> httpx.Response:
        called.append(1)
        return httpx.Response(200, json={})

    res = execute_web_tool("web_search_brave", {"query": "x"}, client=_client(handler))
    assert res.ok is False
    assert "BRAVE_API_KEY" in (res.error or "")
    assert called == []  # key checked first — no network call


def test_web_search_brave_parses_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRAVE_API_KEY", "bk")

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["X-Subscription-Token"] == "bk"  # key in header, not URL
        assert req.url.host == "api.search.brave.com"
        assert req.url.params["q"] == "q"
        return httpx.Response(
            200,
            json={"web": {"results": [{"title": "BT", "url": "http://b", "description": "d"}]}},
        )

    res = execute_web_tool("web_search_brave", {"query": "q"}, client=_client(handler))
    assert res.ok is True
    assert "BT" in res.output and "http://b" in res.output and "d" in res.output


def test_web_scrape_returns_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-k")

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer fc-k"
        assert str(req.url) == "https://api.firecrawl.dev/v2/scrape"
        return httpx.Response(
            200, json={"success": True, "data": {"markdown": "# Hello"}}
        )

    res = execute_web_tool("web_scrape", {"url": "http://x"}, client=_client(handler))
    assert res.ok is True and "# Hello" in res.output


def test_docs_lookup_two_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTEXT7_API_KEY", "c7")

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["authorization"] == "Bearer c7"
        if req.url.path.endswith("/libs/search"):
            return httpx.Response(200, json={"results": [{"id": "/facebook/react"}]})
        assert req.url.path.endswith("/context")
        return httpx.Response(200, text="useState is a hook")

    res = execute_web_tool(
        "docs_lookup",
        {"library": "react", "query": "useState"},
        client=_client(handler),
    )
    assert res.ok is True and "useState" in res.output


def test_web_crawl_polls_to_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-k")

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"id": "job-1"})
        assert req.url.path.endswith("/crawl/job-1")
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "data": [
                    {"markdown": "page one", "metadata": {"sourceURL": "http://a"}}
                ],
            },
        )

    res = execute_web_tool(
        "web_crawl", {"url": "http://x", "limit": 5}, client=_client(handler)
    )
    assert res.ok is True and "page one" in res.output


def test_web_crawl_polls_through_in_progress_then_completes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the actual poll loop: a 'scraping' status then 'completed'."""
    import subagents.web_tools as wt

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-k")
    monkeypatch.setattr(wt, "_CRAWL_POLL_INTERVAL", 0.0)  # don't really sleep
    state = {"polls": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"id": "job-9"})
        state["polls"] += 1
        if state["polls"] == 1:
            return httpx.Response(200, json={"status": "scraping"})
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "data": [{"markdown": "final", "metadata": {}}],
            },
        )

    res = execute_web_tool("web_crawl", {"url": "http://x"}, client=_client(handler))
    assert res.ok is True and "final" in res.output
    assert state["polls"] >= 2  # actually polled through the in-progress state


def test_http_error_returns_ok_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXA_API_KEY", "k")
    res = execute_web_tool(
        "web_search",
        {"query": "q"},
        client=_client(lambda req: httpx.Response(500, text="boom")),
    )
    assert res.ok is False and res.error is not None


def test_timeout_returns_ok_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXA_API_KEY", "k")

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    res = execute_web_tool("web_search", {"query": "q"}, client=_client(handler))
    assert res.ok is False and res.error is not None


def test_unknown_web_tool_is_error() -> None:
    res = execute_web_tool("nope", {}, client=_client(lambda r: httpx.Response(200)))
    assert res.ok is False


def test_execute_web_tool_total_on_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-HTTPError from the transport (e.g. httpx.InvalidURL) must NOT escape —
    the catch-all keeps execute_web_tool total (else it'd unwind the loop + lose
    tool_calls provenance)."""
    monkeypatch.setenv("EXA_API_KEY", "k")

    def handler(req: httpx.Request) -> httpx.Response:
        raise RuntimeError("weird transport failure")

    res = execute_web_tool("web_search", {"query": "q"}, client=_client(handler))
    assert res.ok is False and res.error is not None


def test_client_none_path_builds_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real client=None path (constructs + closes its own httpx.Client) works —
    exercised via a missing key so no network is needed."""
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    res = execute_web_tool("web_search", {"query": "q"})  # no client injected
    assert res.ok is False and "EXA_API_KEY" in (res.error or "")


def test_unexpected_response_shape_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-dict element in `results` (F1) must NOT crash — total contract."""
    monkeypatch.setenv("EXA_API_KEY", "k")
    res = execute_web_tool(
        "web_search",
        {"query": "q"},
        client=_client(
            lambda r: httpx.Response(200, json={"results": ["not-a-dict", 42]})
        ),
    )
    assert res.ok is True  # non-dict elements skipped, no raise
    assert "no results" in res.output


def test_non_dict_arguments_do_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-dict `arguments` (F2) → ok=False, never raises (self-total contract)."""
    monkeypatch.setenv("EXA_API_KEY", "k")
    res = execute_web_tool(
        "web_search",
        "just a string",
        client=_client(lambda r: httpx.Response(200)),  # type: ignore[arg-type]
    )
    assert res.ok is False and res.error is not None


def test_error_never_leaks_the_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """The key must never reach output/error (shown to the model + logged)."""
    monkeypatch.setenv("EXA_API_KEY", "sk-SECRET-EXA-KEY")
    res = execute_web_tool(
        "web_search",
        {"query": "q"},
        client=_client(lambda r: httpx.Response(500, text="server error")),
    )
    assert res.ok is False
    assert "sk-SECRET-EXA-KEY" not in (res.error or "")
    assert "sk-SECRET-EXA-KEY" not in res.output


@pytest.mark.parametrize(
    ("name", "env", "args"),
    [
        ("web_scrape", "FIRECRAWL_API_KEY", {"url": "http://x"}),
        ("web_crawl", "FIRECRAWL_API_KEY", {"url": "http://x"}),
        ("docs_lookup", "CONTEXT7_API_KEY", {"library": "react", "query": "q"}),
    ],
)
def test_all_tools_no_network_without_key(
    monkeypatch: pytest.MonkeyPatch, name: str, env: str, args: dict
) -> None:
    """Every web tool checks its key BEFORE any HTTP call (not just web_search)."""
    monkeypatch.delenv(env, raising=False)
    calls: list[httpx.Request] = []
    res = execute_web_tool(
        name,
        args,
        client=_client(lambda req: calls.append(req) or httpx.Response(200, json={})),
    )
    assert res.ok is False and env in (res.error or "")
    assert calls == [], f"{name} hit the network without {env}"


def test_crawl_terminal_failure_is_surfaced(monkeypatch: pytest.MonkeyPatch) -> None:
    """A crawl `status:"failed"` (F5) returns promptly, not after the 60s timeout."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-k")

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            return httpx.Response(200, json={"id": "job-2"})
        return httpx.Response(200, json={"status": "failed"})

    res = execute_web_tool("web_crawl", {"url": "http://x"}, client=_client(handler))
    assert res.ok is False and "failed" in (res.error or "")


def test_crawl_limit_negative_is_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A negative `limit` (F4) must not produce a negative slice / drop pages."""
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-k")
    sent: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "POST":
            import json as _j

            sent.update(_j.loads(req.content))
            return httpx.Response(200, json={"id": "j"})
        return httpx.Response(
            200,
            json={"status": "completed", "data": [{"markdown": "p", "metadata": {}}]},
        )

    res = execute_web_tool(
        "web_crawl", {"url": "http://x", "limit": -3}, client=_client(handler)
    )
    assert res.ok is True and "p" in res.output
    assert sent["limit"] >= 1  # clamped, not sent as -3


def test_schemas_cover_all_names() -> None:
    names = {s["function"]["name"] for s in WEB_TOOL_SCHEMAS}
    assert names == set(WEB_TOOL_NAMES)
    for s in WEB_TOOL_SCHEMAS:
        assert s["type"] == "function" and "parameters" in s["function"]
