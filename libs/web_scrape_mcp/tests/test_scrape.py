"""The `scrape` contract over injected fakes (no network, no sibling module, no MCP SDK).

Run: python -m pytest tests -q   (from web-scrape-mcp/)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from web_scrape_mcp import Deps, scrape  # noqa: E402

NOW = datetime(2026, 10, 21, 12, 0, tzinfo=UTC)
SUCCESS_KEYS = {"status", "final_url", "content_type", "title", "markdown", "truncated", "short", "path", "fetched_at"}
LONG = "word " * 300  # 1 500 characters of text


class RobotsErr(Exception):
    pass


class ScopeErr(Exception):
    pass


class FetchErr(Exception):
    def __init__(self, status: int | None, body: str = "", headers: dict[str, str] | None = None) -> None:
        super().__init__("fetch failed")
        self.status, self.body, self.headers = status, body, headers or {}


class SubFetchErr(FetchErr):
    pass


@dataclass
class Page:
    status: int = 200
    text: str = ""
    content_type: str = "text/html"
    headers: dict[str, str] = field(default_factory=dict)
    final_url: str = "https://docs.test/p"
    title: str | None = "T"
    fetched_at: str = NOW.isoformat()
    from_cache: bool = False


def html(body: str) -> str:
    return f"<html><head><title>T</title></head><body>{body}</body></html>"


class FakeFetch:
    def __init__(self, *results: Any) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []

    def __call__(self, url: str, *, ignore_cache: bool, accept_markdown: bool) -> Page:
        self.calls.append({"url": url, "ignore_cache": ignore_cache, "accept_markdown": accept_markdown})
        r = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(r, BaseException):
            raise r
        return r


def strip_tags(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", " ", text)


def wall(text: str) -> bool:
    return "captcha-delivery.com" in text or "just a moment" in text.lower()


def deps(fetch: FakeFetch) -> Deps:
    return Deps(fetch=fetch, to_markdown=strip_tags, is_bot_wall=wall, robots_error=RobotsErr,
                scope_error=ScopeErr, fetch_error=FetchErr, url_errors=(UnicodeError, ValueError))


def run(*results: Any, **kw: Any) -> tuple[dict[str, Any], FakeFetch]:
    f = FakeFetch(*results)
    return scrape("https://docs.test/p", deps=deps(f), now=lambda: NOW, **kw), f


def assert_blocked(r: dict[str, Any], reason: str, status: int | None) -> None:
    assert r == {"blocked": True, "reason": reason, "status": status}


# ── success paths ────────────────────────────────────────────────────────────
def test_a_markdown_answer_is_used_as_is() -> None:
    r, f = run(Page(text="# Messages\n\n" + LONG, content_type="text/markdown; charset=utf-8"))
    assert set(r) == SUCCESS_KEYS and r["path"] == "markdown" and r["markdown"].startswith("# Messages")
    assert f.calls[0]["accept_markdown"] is True


def test_an_html_answer_is_converted() -> None:
    r, _ = run(Page(text=html("<p>" + LONG + "</p>")))
    assert r["path"] == "static" and "<p>" not in r["markdown"] and r["short"] is False and r["title"] == "T"


def test_a_short_html_page_is_returned_with_short_true() -> None:
    r, _ = run(Page(text=html("<p>" + "word " * 40 + "</p>")))
    assert r["short"] is True and r["markdown"].strip()


def test_an_html_page_under_50_characters_is_empty() -> None:
    assert_blocked(run(Page(text=html("<p>hi</p>")))[0], "empty", 200)


def test_plain_text_and_json_are_returned_as_is_never_short() -> None:
    for text, ctype in (("1.2.3", "text/plain"), ('{"ok":true}', "application/json"), ("<a/>", "application/xml")):
        r, _ = run(Page(text=text, content_type=ctype))
        assert r["markdown"] == text and r["short"] is False and r["path"] == "static"


def test_a_blank_non_html_body_is_empty() -> None:
    assert_blocked(run(Page(text="   ", content_type="text/plain"))[0], "empty", 200)


def test_a_success_carries_fetched_at_and_final_url() -> None:
    r, _ = run(Page(text=LONG, content_type="text/plain", final_url="https://docs.test/final"))
    assert r["fetched_at"] == NOW.isoformat() and r["final_url"] == "https://docs.test/final"


# ── render ───────────────────────────────────────────────────────────────────
def test_render_always_is_unavailable_and_never_fetches() -> None:
    r, f = run(Page(text=LONG, content_type="text/plain"), render="always")
    assert_blocked(r, "render-unavailable", None)
    assert f.calls == []


@pytest.mark.parametrize("mode", ["auto", "never"])
def test_render_auto_and_never_return_the_static_result(mode: str) -> None:
    r, _ = run(Page(text=html("<p>" + "word " * 40 + "</p>")), render=mode)
    assert r["path"] == "static" and r["short"] is True


# ── blocked reasons ──────────────────────────────────────────────────────────
def test_robots() -> None:
    assert_blocked(run(RobotsErr())[0], "robots", None)


def test_scope_from_the_fetcher_and_from_the_url() -> None:
    assert_blocked(run(ScopeErr())[0], "scope", None)
    assert_blocked(run(UnicodeError("bad idn"))[0], "scope", None)
    f = FakeFetch(Page())
    for bad in ("file:///etc/passwd", "ftp://x.test/", "https:///nohost", "javascript:alert(1)"):
        assert_blocked(scrape(bad, deps=deps(f), now=lambda: NOW), "scope", None)
    assert f.calls == []


@pytest.mark.parametrize("status", [404, 410])
def test_404_and_410_whatever_the_body(status: int) -> None:
    assert_blocked(run(Page(status=status, text="404: Not Found", content_type="text/plain"))[0], f"http-{status}", status)
    assert_blocked(run(Page(status=status, text=html("<p>" + LONG + "</p>")))[0], f"http-{status}", status)


def test_a_429_is_http_429_even_when_near_empty() -> None:
    assert_blocked(run(FetchErr(429, ""))[0], "http-429", 429)
    assert_blocked(run(FetchErr(429, html("<p>" + LONG + "</p>")))[0], "http-429", 429)


def test_another_4xx_or_5xx_with_text_is_http_status() -> None:
    assert_blocked(run(Page(status=403, text=html("<p>" + LONG + "</p>")))[0], "http-403", 403)
    assert_blocked(run(FetchErr(502, html("<p>" + LONG + "</p>"), {"content-type": "text/html"}))[0], "http-502", 502)


def test_near_empty_or_non_html_4xx_5xx_is_empty() -> None:
    assert_blocked(run(Page(status=403, text=html("<p>no</p>")))[0], "empty", 403)
    assert_blocked(run(Page(status=400, text='{"error":"bad request"}', content_type="application/json"))[0], "empty", 400)
    assert_blocked(run(FetchErr(503, "down", {"content-type": "text/plain"}))[0], "empty", 503)


def test_a_connection_failure_is_empty_with_no_status() -> None:
    assert_blocked(run(FetchErr(None, "connect failed"))[0], "empty", None)


def test_bot_wall_on_every_body() -> None:
    page = html('<script src="https://ct.captcha-delivery.com/c.js"></script>' + LONG)
    assert_blocked(run(Page(text=page))[0], "bot-wall", 200)
    assert_blocked(run(Page(status=403, text=page))[0], "bot-wall", 403)
    assert_blocked(run(FetchErr(503, page))[0], "bot-wall", 503)
    assert_blocked(run(FetchErr(503, "", {"x-datadome": "protected"}))[0], "bot-wall", 503)
    assert_blocked(run(Page(status=404, text=page))[0], "bot-wall", 404)  # a wall wins over 404


def test_the_saved_datadome_403_is_a_bot_wall() -> None:
    fixture = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "web-scrape", "fixtures", "datadome-403.html")
    if not os.path.exists(fixture):
        pytest.skip("the web-scrape fixture is not beside this module (a vendored copy)")
    with open(fixture, encoding="utf-8") as fh:
        assert_blocked(run(Page(status=403, text=fh.read()))[0], "bot-wall", 403)


def test_unsupported_content_types() -> None:
    assert_blocked(run(Page(text="%PDF-1.7", content_type="application/pdf"))[0], "unsupported", 200)
    assert_blocked(run(Page(text="\x89PNG", content_type="image/png"))[0], "unsupported", 200)


def test_a_subclass_of_the_injected_error_is_still_classified() -> None:
    assert_blocked(run(SubFetchErr(404, "x"))[0], "http-404", 404)


def test_an_unexpected_exception_propagates() -> None:
    with pytest.raises(KeyError):
        run(KeyError("boom"))


def test_markdown_is_never_empty_without_blocked() -> None:
    cases = [Page(text=""), Page(text="   ", content_type="text/markdown"), Page(text=html("")), Page(text="",
             content_type="text/plain")]
    for page in cases:
        r, _ = run(page)
        assert r.get("blocked") is True or r["markdown"].strip()


# ── paging, cache age, arguments ─────────────────────────────────────────────
def test_start_index_and_max_length_page_the_markdown() -> None:
    text = "abcdefghij" * 10
    first, _ = run(Page(text=text, content_type="text/plain"), max_length=30)
    second, _ = run(Page(text=text, content_type="text/plain"), max_length=30, start_index=90)
    assert first["markdown"] == text[:30] and first["truncated"] is True
    assert second["markdown"] == text[90:] and second["truncated"] is False


def test_max_age_zero_fetches_live() -> None:
    _, f = run(Page(text=LONG, content_type="text/plain"))
    assert f.calls[0]["ignore_cache"] is True


def test_a_fresh_cached_copy_is_used_and_a_stale_one_refetched() -> None:
    fresh = Page(text=LONG, content_type="text/plain", from_cache=True, fetched_at=(NOW - timedelta(seconds=30)).isoformat())
    r, f = run(fresh, max_age_s=60)
    assert len(f.calls) == 1 and f.calls[0]["ignore_cache"] is False and r["fetched_at"] == fresh.fetched_at
    stale = Page(text=LONG, content_type="text/plain", from_cache=True, fetched_at=(NOW - timedelta(seconds=600)).isoformat())
    live = Page(text=LONG, content_type="text/plain", fetched_at=NOW.isoformat())
    r, f = run(stale, live, max_age_s=60)
    assert [c["ignore_cache"] for c in f.calls] == [False, True] and r["fetched_at"] == NOW.isoformat()


@pytest.mark.parametrize("kw", [{"max_length": 0}, {"start_index": -1}, {"render": "x"}, {"max_age_s": -1}])
def test_range_errors_raise_before_any_fetch(kw: dict[str, Any]) -> None:
    f = FakeFetch(Page(text=LONG, content_type="text/plain"))
    with pytest.raises(ValueError):
        scrape("https://docs.test/p", deps=deps(f), now=lambda: NOW, **kw)
    assert f.calls == []


def test_start_index_past_the_end_raises_only_on_a_successful_read() -> None:
    with pytest.raises(ValueError, match="past the end"):
        run(Page(text="short text here, longer than nothing", content_type="text/plain"), start_index=5000)
    assert_blocked(run(Page(status=404, text="gone"), start_index=5000)[0], "http-404", 404)


# ── Gate B review round 1 ────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", ["http://[::1", "http://a℀.com/"])
def test_b1_an_unparseable_url_is_scope_not_an_error(bad: str) -> None:
    f = FakeFetch(Page())
    assert_blocked(scrape(bad, deps=deps(f), now=lambda: NOW), "scope", None)
    assert f.calls == []


def test_b1_scope_wins_over_render_always() -> None:
    f = FakeFetch(Page())
    assert_blocked(scrape("ftp://x.test/", deps=deps(f), render="always", now=lambda: NOW), "scope", None)


@pytest.mark.parametrize("ctype", ["text/yaml", "application/yaml", "application/javascript", "text/css",
                                   "text/csv", "text/x-markdown", "application/ld+json", "application/atom+xml",
                                   "text/json", "text/xml"])
def test_b1_text_types_are_returned_as_is(ctype: str) -> None:
    r, _ = run(Page(text=LONG, content_type=ctype))
    assert r["markdown"] == LONG[:20_000] and r["short"] is False


def test_b1_a_body_with_no_content_type_is_returned_as_is() -> None:
    r, _ = run(Page(text="plain words " * 20, content_type=""))
    assert r["path"] == "static" and r["markdown"].startswith("plain words")


@pytest.mark.parametrize("ctype", ["", "application/pdf", "text/plain"])
def test_b1_a_blank_2xx_is_empty_whatever_its_type(ctype: str) -> None:
    assert_blocked(run(Page(status=204, text="", content_type=ctype))[0], "empty", 204)


def _html_with_text(n: int) -> str:
    return "<p>" + "x" * n + "</p>"  # strip_tags leaves exactly n characters


@pytest.mark.parametrize(("n", "short"), [(799, True), (800, False)])
def test_b1_the_short_threshold_is_800(n: int, short: bool) -> None:
    r, _ = run(Page(text=_html_with_text(n)))
    assert r["short"] is short


@pytest.mark.parametrize(("n", "blocked"), [(49, True), (50, False)])
def test_b1_the_empty_threshold_is_50(n: int, blocked: bool) -> None:
    r, _ = run(Page(text=_html_with_text(n)))
    assert bool(r.get("blocked")) is blocked
    e, _ = run(Page(status=403, text=_html_with_text(n)))
    assert e["reason"] == ("empty" if blocked else "http-403")


def test_b1_xhtml_is_html() -> None:
    r, _ = run(Page(text=_html_with_text(900), content_type="application/xhtml+xml"))
    assert r["path"] == "static" and "<p>" not in r["markdown"]


def test_b1_a_mixed_case_content_type_header_on_an_error_is_read() -> None:
    body = "Upstream down. " + _html_with_text(900)  # does not open with `<`: only the header marks it HTML
    assert_blocked(run(FetchErr(502, body, {"Content-Type": "text/html"}))[0], "http-502", 502)


def test_b1_x_markdown_takes_the_markdown_path() -> None:
    r, _ = run(Page(text=LONG, content_type="text/x-markdown; charset=utf-8"))
    assert r["path"] == "markdown"


def test_b1_a_wall_wins_over_429() -> None:
    page = html('<script src="https://ct.captcha-delivery.com/c.js"></script>')
    assert_blocked(run(FetchErr(429, page))[0], "bot-wall", 429)


def test_b1_start_index_at_the_end_raises_and_an_exact_fit_is_not_truncated() -> None:
    text = "abcdefghij" * 3
    with pytest.raises(ValueError, match="past the end"):
        run(Page(text=text, content_type="text/plain"), start_index=len(text))
    r, _ = run(Page(text=text, content_type="text/plain"), max_length=len(text))
    assert r["truncated"] is False and r["markdown"] == text


def test_b1_max_age_boundary_and_a_future_fetch_time() -> None:
    at_limit = Page(text=LONG, content_type="text/plain", from_cache=True,
                    fetched_at=(NOW - timedelta(seconds=60)).isoformat())
    _, f = run(at_limit, max_age_s=60)
    assert len(f.calls) == 1  # exactly max_age_s old is still fresh
    future = Page(text=LONG, content_type="text/plain", from_cache=True,
                  fetched_at=(NOW + timedelta(days=1)).isoformat())
    _, f = run(future, Page(text=LONG, content_type="text/plain"), max_age_s=60)
    assert [c["ignore_cache"] for c in f.calls] == [False, True]


def test_b1_http_urls_are_fetched() -> None:
    f = FakeFetch(Page(text=LONG, content_type="text/plain"))
    assert scrape("http://docs.test/p", deps=deps(f), now=lambda: NOW)["status"] == 200


def test_b1_the_default_clock_is_utc() -> None:
    import inspect

    from web_scrape_mcp import scrape as fn

    assert inspect.signature(fn).parameters["now"].default().tzinfo is not None


def test_b1_a_chunk_inside_a_whitespace_run_is_never_blank() -> None:
    text = "a" * 10 + " " * 30 + "b" * 10
    r, _ = run(Page(text=text, content_type="text/plain"), start_index=10, max_length=5)
    assert r["markdown"].strip() == "b" and r["markdown"] == " " * 30 + "b" and r["truncated"] is True
    with pytest.raises(ValueError, match="past the last text"):
        run(Page(text="abc" + " " * 20, content_type="text/plain"), start_index=5, max_length=3)


def test_b2_only_whitespace_after_the_chunk_is_not_truncated() -> None:
    r, _ = run(Page(text="abc" + " " * 50, content_type="text/plain"), max_length=5)
    assert r["markdown"] == "abc  " and r["truncated"] is False
