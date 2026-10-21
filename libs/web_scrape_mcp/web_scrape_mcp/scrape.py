"""The `scrape` contract — pure, over injected dependencies (no sibling module is imported here).

One call reads one page and returns either its markdown or `{blocked: true, reason, status}`; it never returns empty
markdown. The rules are the hub design's (own-scrape-tools, § Chosen approach 1, hub D-1100), slice 1a: static and
markdown paths only, rendering OFF. The consumer injects its vendored `web_scrape` and `doc_crawl` through `Deps`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

RENDER_MODES = ("auto", "always", "never")
SHORT_CHARS = 800  # an HTML page whose converted text is shorter is returned with `short: true`
EMPTY_CHARS = 50  # an HTML body (or a 4xx/5xx body) with less text than this is `blocked: empty`
_MARKDOWN_TYPES = ("text/markdown", "text/x-markdown")
_TEXT_TYPES = (
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "application/javascript",
    "application/ecmascript",
)  # plus any `text/*` that is not HTML or markdown, and any `+json` / `+xml` type


class FetchedPage(Protocol):
    """What `Deps.fetch` returns — `web_scrape.FetchResult` satisfies it."""

    status: int
    final_url: str
    headers: Mapping[str, str]
    content_type: str
    text: str
    title: str | None
    fetched_at: str
    from_cache: bool


@dataclass(frozen=True)
class Deps:
    """The consumer's vendored pieces.

    `fetch(url, *, ignore_cache, accept_markdown)` is `WebScraper.fetch_static_result` (built with
    `transport=SsrfSafeTransport()`); `to_markdown` is `doc_crawl`'s `html_to_markdown`; `is_bot_wall` is
    `web_scrape.is_bot_wall`. The three error classes are matched with `isinstance`, so a subclass still matches.
    `url_errors` are the exceptions an unparseable URL raises (e.g. `httpx.InvalidURL`, `httpx.UnsupportedProtocol`);
    they map to `blocked: scope`. Any other exception propagates — a tool error, never a silent `blocked`.
    """

    fetch: Callable[..., FetchedPage]
    to_markdown: Callable[[str], str]
    is_bot_wall: Callable[[str], bool]
    robots_error: type[BaseException]
    scope_error: type[BaseException]
    fetch_error: type[BaseException]
    url_errors: tuple[type[BaseException], ...] = field(default=(UnicodeError,))


def _blocked(reason: str, status: int | None) -> dict[str, Any]:
    return {"blocked": True, "reason": reason, "status": status}


def _base_type(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _looks_html(text: str, ctype: str) -> bool:
    if ctype in ("text/html", "application/xhtml+xml"):
        return True
    return not ctype and text.lstrip()[:1] == "<"


def _wall(deps: Deps, text: str, headers: Mapping[str, str]) -> bool:
    return deps.is_bot_wall(text) or any(k.lower() == "x-datadome" for k in headers)


def _classify_error(deps: Deps, status: int, text: str, headers: Mapping[str, str]) -> dict[str, Any]:
    """A 4xx or 5xx, in the design's order: wall → 404/410 → 429 → near-empty or non-HTML → http-<status>."""
    if _wall(deps, text, headers):
        return _blocked("bot-wall", status)
    if status in (404, 410):
        return _blocked(f"http-{status}", status)
    if status == 429:
        return _blocked("http-429", status)  # never `empty`: an empty page goes to another fetcher; a rate limit never
    ctype = _base_type(next((v for k, v in headers.items() if k.lower() == "content-type"), ""))
    if not _looks_html(text, ctype) or len(deps.to_markdown(text).strip()) < EMPTY_CHARS:
        return _blocked("empty", status)
    return _blocked(f"http-{status}", status)


def _age_s(fetched_at: str, now: datetime) -> float:
    try:
        age = (now - datetime.fromisoformat(fetched_at)).total_seconds()
    except (ValueError, TypeError):
        return float("inf")  # an unreadable time is treated as too old
    return age if age >= 0 else float("inf")  # a time in the future is not trusted either


def scrape(
    url: str,
    *,
    deps: Deps,
    render: str = "auto",
    max_length: int = 20_000,
    start_index: int = 0,
    max_age_s: int = 0,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Read one page. Returns `{status, final_url, content_type, title, markdown, truncated, short, path, fetched_at}`
    or `{blocked: true, reason, status}`.

    Raises `ValueError` for an invalid argument, before any fetch: `render` outside auto/always/never,
    `max_length < 1`, `start_index < 0`, `max_age_s < 0`; and, after a successful read only, `start_index` at or past
    the end of the markdown (a `blocked` result is returned whatever `start_index` says).
    """
    if render not in RENDER_MODES:
        raise ValueError(f"render must be one of {RENDER_MODES}, not {render!r}")
    if max_length < 1 or start_index < 0 or max_age_s < 0:
        raise ValueError("max_length must be >= 1, start_index >= 0 and max_age_s >= 0")
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
    except ValueError:  # e.g. an unclosed IPv6 bracket, an NFKC-invalid netloc
        return _blocked("scope", None)
    if parts.scheme.lower() not in ("http", "https") or not hostname:
        return _blocked("scope", None)
    if render == "always":
        return _blocked("render-unavailable", None)  # rendering is off until slice 1c proves it safe

    def fetch(live: bool) -> FetchedPage:
        return deps.fetch(url, ignore_cache=live, accept_markdown=True)

    try:
        page = fetch(max_age_s == 0)
        if max_age_s > 0 and page.from_cache and _age_s(page.fetched_at, now()) > max_age_s:
            page = fetch(True)
    except deps.robots_error:
        return _blocked("robots", None)
    except deps.scope_error:
        return _blocked("scope", None)
    except deps.url_errors:
        return _blocked("scope", None)
    except deps.fetch_error as exc:
        status = getattr(exc, "status", None)
        if not isinstance(status, int):
            return _blocked("empty", None)  # no response after every attempt (a connection failure)
        return _classify_error(deps, status, str(getattr(exc, "body", "") or ""), getattr(exc, "headers", {}) or {})

    if page.status >= 400:
        return _classify_error(deps, page.status, page.text, page.headers)
    if _wall(deps, page.text, page.headers):
        return _blocked("bot-wall", page.status)

    ctype = _base_type(page.content_type)
    short = False
    if not page.text.strip():
        return _blocked("empty", page.status)  # a blank body (a 204, a blank file) has no readable text
    if ctype in _MARKDOWN_TYPES:
        markdown, path = page.text, "markdown"
    elif _looks_html(page.text, ctype):
        markdown, path = deps.to_markdown(page.text), "static"
        if len(markdown.strip()) < EMPTY_CHARS:
            return _blocked("empty", page.status)
        short = len(markdown.strip()) < SHORT_CHARS
    elif ctype.startswith("text/") or ctype in _TEXT_TYPES or ctype.endswith(("+json", "+xml")) or not ctype:
        markdown, path = page.text, "static"
    else:
        return _blocked("unsupported", page.status)  # a PDF (slice 1b), an image, octet-stream

    if start_index >= len(markdown):
        raise ValueError(f"start_index {start_index} is at or past the end ({len(markdown)} characters)")
    end = start_index + max_length
    if not markdown[start_index:end].strip():
        # A chunk inside a whitespace run would be blank: extend it to the next character with text, so the
        # markdown is never blank and `start_index + len(markdown)` is still where the next chunk begins.
        rest = markdown[end:]
        gap = len(rest) - len(rest.lstrip())
        if gap == len(rest):
            raise ValueError(f"start_index {start_index} is past the last text ({len(markdown)} characters)")
        end += gap + 1
    chunk = markdown[start_index:end]
    return {
        "status": page.status,
        "final_url": page.final_url,
        "content_type": page.content_type,
        "title": page.title,
        "markdown": chunk,
        "truncated": bool(markdown[end:].strip()),  # only whitespace left is not more text
        "short": short,
        "path": path,
        "fetched_at": page.fetched_at,
    }
