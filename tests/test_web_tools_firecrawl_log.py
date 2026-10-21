"""W-eadc4d0a (hub W-10146d20 slice 1a, intel 01M5FD81GW): every Firecrawl call web-tools makes logs its caller and
URL, so a billing period's spend can be attributed. Offline: every call goes through httpx.MockTransport."""

# Vendored from fabrik-lib web-tools/test_web_tools_firecrawl_log.py at c7ab67e4, retargeted at the hub's
# libs/web_tools.py (the string patch target became the loaded module object): a re-vendor that drops the
# per-call caller-and-URL log turns this file red (W-10146d20). Re-copy it with the module on every re-vendor.

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest

# The hub's vendored copy, loaded under a private name: a bare `import web_tools` could bind the frozen pool copy
# `libs/subagents/web_tools.py` (D-547) when another test put that directory on sys.path first.
_PATH = Path(__file__).resolve().parents[1] / "libs" / "web_tools.py"
_spec = importlib.util.spec_from_file_location("hub_libs_web_tools_log", _PATH)
assert _spec and _spec.loader
_wt = importlib.util.module_from_spec(_spec)
sys.modules["hub_libs_web_tools_log"] = _wt
_spec.loader.exec_module(_wt)
WebToolsConfig, a_firecrawl_scrape = _wt.WebToolsConfig, _wt.a_firecrawl_scrape
a_firecrawl_search, execute_web_tool = _wt.a_firecrawl_search, _wt.execute_web_tool

LOGGER = "web_tools.firecrawl"


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _aclient(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == LOGGER]


def test_a_scrape_logs_one_line_with_its_caller_and_url(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    res = execute_web_tool(
        "web_scrape",
        {"url": "https://example.com/page"},
        client=_client(lambda r: httpx.Response(200, json={"data": {"markdown": "# hi"}})),
    )
    assert res.ok, res
    lines = _lines(caplog)
    assert len(lines) == 1, lines
    assert lines[0].startswith("firecrawl scrape url=https://example.com/page caller="), lines
    # the caller is the code outside web_tools.py that made the call: this file, this function
    assert (
        __file__ in lines[0] and "test_a_scrape_logs_one_line_with_its_caller_and_url" in lines[0]
    ), lines
    # WARNING, so Python's last-resort handler prints it in a consumer that never configured logging
    assert [r.levelno for r in caplog.records if r.name == LOGGER] == [logging.WARNING]


def test_a_crawl_logs_its_start_once_not_every_status_poll(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    polls = iter([{"status": "scraping"}, {"status": "completed", "data": []}])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, json={"id": "job1"})
        return httpx.Response(200, json=next(polls))

    monkeypatch.setattr(_wt.time, "sleep", lambda s: None)
    res = execute_web_tool("web_crawl", {"url": "https://example.com"}, client=_client(handler))
    assert res.ok, res
    lines = _lines(caplog)
    assert lines == [lines[0]] and lines[0].startswith(
        "firecrawl crawl url=https://example.com caller="
    ), lines


def test_an_awaited_scrape_names_the_awaiting_coroutine_not_asyncio(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)
    cfg = WebToolsConfig(firecrawl_api_key="fk")

    async def research_leg() -> Any:
        return await a_firecrawl_scrape(
            {"url": "https://example.com/a"},
            config=cfg,
            client=_aclient(lambda r: httpx.Response(200, json={"data": {"markdown": "x"}})),
        )

    assert asyncio.run(research_leg()).ok
    lines = _lines(caplog)
    assert len(lines) == 1 and "in research_leg" in lines[0] and __file__ in lines[0], lines
    assert "asyncio" not in lines[0], lines


def test_a_search_logs_its_market_and_caller(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)
    cfg = WebToolsConfig(firecrawl_api_key="fk")

    async def search_leg() -> Any:
        return await a_firecrawl_search(
            {"query": "q", "market": "Spain"},
            config=cfg,
            client=_aclient(lambda r: httpx.Response(200, json={"data": {"web": []}})),
        )

    assert asyncio.run(search_leg()).ok
    lines = _lines(caplog)
    assert len(lines) == 1 and lines[0].startswith(
        "firecrawl search url=https://api.firecrawl.dev/v2/search"
    ), lines
    assert "market=Spain" in lines[0] and "in search_leg" in lines[0], lines


def test_no_key_means_no_call_and_no_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    caplog.set_level(logging.WARNING, logger=LOGGER)
    assert not execute_web_tool("web_scrape", {"url": "https://example.com"}).ok
    assert not asyncio.run(
        a_firecrawl_scrape(
            {"url": "https://example.com"},
            config=WebToolsConfig(),
            client=_aclient(lambda r: httpx.Response(500)),
        )
    ).ok
    assert _lines(caplog) == []


def test_credentials_in_a_url_are_never_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    secret = "s3cr" + "etpw"
    execute_web_tool(
        "web_scrape",
        {"url": "https://user:" + secret + "@example.com/p?q=1"},
        client=_client(lambda r: httpx.Response(200, json={"data": {"markdown": "x"}})),
    )
    lines = _lines(caplog)
    assert (
        len(lines) == 1 and secret not in lines[0] and "url=https://example.com/p?q=1" in lines[0]
    ), lines


@pytest.mark.parametrize(
    "url",
    [
        "https://u:{s}@example.com:abc/p",  # a non-numeric port: urlsplit's .port raises
        "https://u:{s}@example.com:99999/p",  # a port out of range
        "https://u:{s}@[::1/p",  # an unclosed IPv6 bracket
        "u:{s}@example.com/p",  # no scheme: urlsplit reads `u` as the scheme
        "https://u:{s}@example.com/a@b",  # an `@` in the path too
        "https://u:p@{s}@example.com/p",  # an `@` inside the password: the tail after the first `@` is password too
        " https://u:{s}@example.com/p",  # leading whitespace (str(args["url"]) keeps it)
    ],
    ids=[
        "bad-port",
        "port-range",
        "ipv6-open",
        "no-scheme",
        "at-in-path",
        "at-in-password",
        "leading-space",
    ],
)
def test_credentials_in_a_malformed_url_are_never_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, url: str
) -> None:
    # review: the parser-based strip fell back to the raw URL, password included, on every one of these
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    secret = "pw" + "9x"
    execute_web_tool(
        "web_scrape",
        {"url": url.format(s=secret)},
        client=_client(lambda r: httpx.Response(200, json={"data": {"markdown": "x"}})),
    )
    lines = _lines(caplog)
    assert len(lines) == 1 and secret not in lines[0], lines


def test_scrapes_run_as_tasks_name_the_code_that_started_the_loop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # review: a coroutine run as a task (gather) has only asyncio frames above it — the caller must skip them
    caplog.set_level(logging.WARNING, logger=LOGGER)
    cfg = WebToolsConfig(firecrawl_api_key="fk")
    client = _aclient(lambda r: httpx.Response(200, json={"data": {"markdown": "x"}}))

    async def both() -> list[Any]:
        return list(
            await asyncio.gather(
                a_firecrawl_scrape({"url": "https://example.com/1"}, config=cfg, client=client),
                a_firecrawl_scrape({"url": "https://example.com/2"}, config=cfg, client=client),
            )
        )

    assert all(r.ok for r in asyncio.run(both()))
    lines = _lines(caplog)
    assert len(lines) == 2, lines
    for line in lines:
        assert "asyncio" not in line.split("caller=", 1)[1], line
        assert "in test_scrapes_run_as_tasks_name_the_code_that_started_the_loop" in line, line


def test_a_call_from_a_worker_thread_never_names_a_library_frame(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import concurrent.futures

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    client = _client(lambda r: httpx.Response(200, json={"data": {"markdown": "x"}}))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        # the executor itself runs the call: no frame of this file is on the worker's stack
        res = pool.submit(
            execute_web_tool, "web_scrape", {"url": "https://example.com"}, client=client
        ).result()
    assert res.ok
    caller = _lines(caplog)[0].split("caller=", 1)[1]
    assert "concurrent" not in caller and "threading" not in caller and "(thread " in caller, caller


def test_a_url_cannot_forge_a_second_log_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    execute_web_tool(
        "web_scrape",
        {"url": "https://example.com/x\nfirecrawl scrape url=FORGED caller=nobody"},
        client=_client(lambda r: httpx.Response(200, json={"data": {"markdown": "x"}})),
    )
    lines = _lines(caplog)
    assert len(lines) == 1 and "\n" not in lines[0] and "\\n" in lines[0], lines


def test_a_search_that_cannot_be_built_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    # no request is sent, so there is no call to attribute
    caplog.set_level(logging.WARNING, logger=LOGGER)
    cfg = WebToolsConfig(firecrawl_api_key="fk")
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"data": {"web": []}})

    res = asyncio.run(
        a_firecrawl_search(
            {"query": "q", "market": "Spain", "num_results": "abc"},
            config=cfg,
            client=_aclient(handler),
        )
    )
    assert not res.ok and sent == [] and _lines(caplog) == [], (res, _lines(caplog))


def test_a_raising_log_handler_never_stops_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            raise RuntimeError("handler boom")

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    log = logging.getLogger(LOGGER)
    handler = Boom()
    log.addHandler(handler)
    sent: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"data": {"markdown": "x"}})

    try:
        res = execute_web_tool(
            "web_scrape", {"url": "https://example.com"}, client=_client(respond)
        )
    finally:
        log.removeHandler(handler)
    assert res.ok and len(sent) == 1, res


def test_an_empty_argv_never_silences_the_line(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # review: an embedded interpreter can have sys.argv == []; the thread fallback must still name something
    import concurrent.futures
    import sys

    monkeypatch.setenv("FIRECRAWL_API_KEY", "fk")
    monkeypatch.setattr(sys, "argv", [])
    caplog.set_level(logging.WARNING, logger=LOGGER)
    client = _client(lambda r: httpx.Response(200, json={"data": {"markdown": "x"}}))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        assert (
            pool.submit(
                execute_web_tool, "web_scrape", {"url": "https://example.com"}, client=client
            )
            .result()
            .ok
        )
    lines = _lines(caplog)
    assert len(lines) == 1 and "caller=? (thread " in lines[0], lines


def test_an_all_space_url_is_stripped_in_linear_time() -> None:
    # review: an overlapping `^\s*` took ~7s on 100k spaces (quadratic backtracking) before the call was made
    _log_fc = _wt._log_fc

    started = time.monotonic()
    _log_fc("scrape", " " * 100_000)
    assert time.monotonic() - started < 1.0
