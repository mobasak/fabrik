"""The real composition, in fabrik-lib only: this module's contract over the sibling `web-scrape` and `doc-crawl`
modules, wired the way the README's `serve.py` wires a consumer's vendored copies. Skipped in a vendored copy (the
siblings are not beside it). No network: the address guard runs through its `_send` hook and a patched resolver.
"""

from __future__ import annotations

import os
import socket
import sys

import httpx
import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = os.path.dirname(os.path.dirname(_HERE))
_WS, _DC = os.path.join(_LIB, "web-scrape"), os.path.join(_LIB, "doc-crawl")
if not (os.path.isdir(os.path.join(_WS, "web_scrape")) and os.path.isdir(os.path.join(_DC, "doc_crawl"))):
    pytest.skip("web-scrape / doc-crawl are not beside this module (a vendored copy)", allow_module_level=True)
pytest.importorskip("bs4")
for p in (os.path.dirname(_HERE), _WS, _DC):
    sys.path.insert(0, p)

import web_scrape  # noqa: E402
from doc_crawl.readability import html_to_markdown  # noqa: E402
from web_scrape_mcp import Deps, scrape  # noqa: E402

_TABLE = {"docs.test": "93.184.216.34", "loop.test": "127.0.0.1"}
_PAGE = "<html><head><title>Guide</title></head><body><main><h1>Guide</h1><p>" + "Real words here. " * 80 + "</p></main></body></html>"


class _Canned(web_scrape.SsrfSafeTransport):
    def _send(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/hop":
            return httpx.Response(302, headers={"location": "http://loop.test/admin"})
        return httpx.Response(200, text=_PAGE, headers={"content-type": "text/html; charset=utf-8"})


@pytest.fixture
def _deps(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Deps:  # noqa: ANN001
    def gai(host: str, *_a: object, **_k: object) -> list[tuple[object, ...]]:
        if host not in _TABLE:
            raise socket.gaierror(-2, "Name or service not known")
        return [(2, 1, 6, "", (_TABLE[host], 0))]

    monkeypatch.setattr(web_scrape.webscrape.socket, "getaddrinfo", gai)
    scraper = web_scrape.WebScraper(tmp_path, transport=_Canned())
    return Deps(fetch=scraper.fetch_static_result, to_markdown=html_to_markdown, is_bot_wall=web_scrape.is_bot_wall,
                robots_error=web_scrape.RobotsError, scope_error=web_scrape.ScopeError,
                fetch_error=web_scrape.FetchError, url_errors=(httpx.InvalidURL, httpx.UnsupportedProtocol, UnicodeError))


def test_an_html_page_becomes_markdown_through_the_real_modules(_deps: Deps) -> None:
    r = scrape("http://docs.test/guide", deps=_deps)
    assert r["path"] == "static" and "Real words here." in r["markdown"] and "<p>" not in r["markdown"]
    assert r["title"] == "Guide" and r["final_url"] == "http://docs.test/guide" and r["status"] == 200


def test_a_redirect_to_loopback_comes_back_scope(_deps: Deps) -> None:
    assert scrape("http://docs.test/hop", deps=_deps) == {"blocked": True, "reason": "scope", "status": None}
