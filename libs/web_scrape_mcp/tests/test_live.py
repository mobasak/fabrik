"""The hub design's three live acceptance cases, over the real composition and the real network. Skipped unless
`FABRIK_LIVE_NET=1` (and, like test_composition, outside fabrik-lib). Never part of a normal run: the pages change.

Run: FABRIK_LIVE_NET=1 python -m pytest tests/test_live.py -q   (from web-scrape-mcp/)
"""

from __future__ import annotations

import os
import sys

import pytest

if os.getenv("FABRIK_LIVE_NET") != "1":
    pytest.skip("live network cases: set FABRIK_LIVE_NET=1", allow_module_level=True)

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(os.path.dirname(_HERE))
_WS, _DC = os.path.join(_LIB, "web-scrape"), os.path.join(_LIB, "doc-crawl")
if not (os.path.isdir(os.path.join(_WS, "web_scrape")) and os.path.isdir(os.path.join(_DC, "doc_crawl"))):
    pytest.skip("web-scrape / doc-crawl are not beside this module (a vendored copy)", allow_module_level=True)
pytest.importorskip("bs4")
for p in (os.path.dirname(_HERE), _WS, _DC):
    sys.path.insert(0, p)

import httpx  # noqa: E402
import web_scrape  # noqa: E402
from doc_crawl.readability import html_to_markdown  # noqa: E402
from web_scrape_mcp import Deps, scrape  # noqa: E402


@pytest.fixture
def _deps(tmp_path) -> Deps:  # noqa: ANN001
    scraper = web_scrape.WebScraper(tmp_path, transport=web_scrape.SsrfSafeTransport())  # the README's serve.py wiring
    return Deps(fetch=scraper.fetch_static_result, to_markdown=html_to_markdown, is_bot_wall=web_scrape.is_bot_wall,
                robots_error=web_scrape.RobotsError, scope_error=web_scrape.ScopeError,
                fetch_error=web_scrape.FetchError, url_errors=(httpx.InvalidURL, httpx.UnsupportedProtocol, UnicodeError))


def test_live_example_com_is_a_short_static_page(_deps: Deps) -> None:
    r = scrape("https://example.com/", deps=_deps)
    print(r)
    assert r.get("blocked") is not True and r["status"] == 200 and r["path"] == "static" and r["short"] is True


def test_live_a_docs_page_answers_markdown_when_asked(_deps: Deps) -> None:
    r = scrape("https://platform.claude.com/docs/en/api/messages", deps=_deps)
    print({k: v for k, v in r.items() if k != "markdown"}, len(r.get("markdown", "")))
    assert r.get("blocked") is not True and "anthropic-version" in r["markdown"]


def test_live_g2_is_a_bot_wall(_deps: Deps) -> None:
    r = scrape("https://www.g2.com/products/notion/reviews", deps=_deps)
    print(r)
    assert r == {"blocked": True, "reason": "bot-wall", "status": r["status"]} and r["status"] in (403, 200)
