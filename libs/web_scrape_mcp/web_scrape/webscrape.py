"""Deterministic web-scrape primitive — httpx for static/SSR, vps1 browserless
for JS-rendered, with built-in __NEXT_DATA__ / Apollo / React-props parsers.

Vendor this folder (copy), don't import. No LLM extraction, no bundled headless
browser, no managed scraping service, no async — see SPEC.md.
"""

from __future__ import annotations

import contextlib
import hashlib
import html
import ipaddress
import json
import re
import socket
import time
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from threading import Semaphore
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

__all__ = [
    "WebScraper",
    "extract_nextjs_data",
    "extract_apollo_state",
    "extract_react_props",
    "is_bot_wall",
    "WebScrapeError",
    "FetchError",
    "ParseError",
    "RobotsError",
    "ScopeError",
    "AddressRefused",
    "SsrfSafeTransport",
    "FetchResult",
]

# G10: the Accept a markdown-first caller sends (only when it asks: `accept_markdown=True`).
_ACCEPT_MARKDOWN = "text/markdown, text/html;q=0.9"

_DEFAULT_UA = "fabrik-lib/web-scrape (+contact@ocoron.com)"
# A realistic desktop-Chrome UA for the stealth render path (a bot UA defeats stealth).
_STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Cloudflare / WAF interstitial signatures (each tuple = all substrings must appear).
_BOT_WALL_SIGNATURES: tuple[tuple[str, ...], ...] = (
    ("just a moment", "challenge-platform"),
    ("cf-browser-verification",),
    ("enable javascript and cookies",),
    ("checking your browser",),
    ("ddos protection by",),
    ("please wait", "cloudflare"),
    ("access denied", "cloudflare"),
    ("var dd=", "captcha-delivery.com"),  # DataDome's challenge page (G11; a g2.com 403, 2026-10-21)
)


def is_bot_wall(html: str) -> bool:
    """True if `html` looks like a Cloudflare/WAF bot-wall interstitial (not the
    real page). Scans only the first ~4 KB. Use it to decide whether to escalate
    to `fetch_rendered(..., stealth=True)`.
    """
    low = html[:4000].lower()
    return any(all(s in low for s in sig) for sig in _BOT_WALL_SIGNATURES)


def _extract_function_html(resp: httpx.Response) -> str:
    """Pull the rendered HTML out of a browserless /function JSON envelope
    (`{"data": "<html>…", "type": …}`). Raises FetchError on an unexpected shape.
    """
    try:
        payload = resp.json()
        data = payload["data"]
    except (ValueError, KeyError, TypeError) as exc:
        raise FetchError(
            "browserless /function returned an unexpected payload",
            status=resp.status_code,
            body=resp.text[:500],
        ) from exc
    if not isinstance(data, str):
        raise FetchError(
            "browserless /function 'data' was not a string",
            status=resp.status_code,
            body=resp.text[:500],
        )
    return data


# ── Errors ──────────────────────────────────────────────────────────────────
class WebScrapeError(Exception):
    """Base for every error this module raises."""


class FetchError(WebScrapeError):
    """An HTTP fetch failed after all retries (5xx / 429 / connection error).

    `headers` are the last response's (lower-cased keys; empty for a connection error), so a caller can read a
    wall signal such as `x-datadome` off a failed fetch.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        body: str = "",
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.headers: dict[str, str] = {k.lower(): v for k, v in (headers or {}).items()}


class ParseError(WebScrapeError):
    """An extract_* helper's target was absent or malformed."""


class RobotsError(WebScrapeError):
    """robots.txt forbids this user-agent on this URL (and the caller did not opt out)."""


class ScopeError(WebScrapeError):
    """A response's FINAL hop left ``allowed_hosts`` — i.e. a redirect escaped the caller's scope.

    Its own type, not a ``FetchError``: a caller that swallows fetch failures (very common — a
    dead link is routine) would otherwise silently swallow an SSRF refusal too, and the whole
    point of the guard is that it is LOUD. ``except FetchError`` must not catch this.
    """

    def __init__(self, message: str, *, requested: str = "", final_host: str = "") -> None:
        super().__init__(message)
        self.requested = requested
        self.final_host = final_host


# ── Address guard (G7) ──────────────────────────────────────────────────────
class AddressRefused(httpx.ConnectError):
    """`SsrfSafeTransport` refused a hop whose host is, or resolves to, a non-public address.

    A `ConnectError` so httpx propagates it unchanged; `WebScraper` turns it into `ScopeError` at once (never a
    retry, never a `FetchError`). A host that does not resolve at all raises a plain `httpx.ConnectError` instead —
    an outage or a typo is not a scope refusal.
    """


# `ipaddress.is_global` is not an SSRF denylist: these read as global yet reach internal or metadata services.
_EXTRA_DENY = (
    ipaddress.ip_network("168.63.129.16/32"),  # Azure WireServer / host endpoint
    # NAT64 local-use (RFC 8215): a network may use any prefix length from /48 to /96 inside it, and for a
    # /48 the IPv4 is not in the low 32 bits (RFC 6052), so it is refused outright, never decoded.
    ipaddress.ip_network("64:ff9b:1::/48"),
)
# IPv6 forms whose low 32 bits are an IPv4 a translating network reaches: NAT64 (the RFC 6052 well-known /96
# prefix), SIIT IPv4-translated (RFC 2765) and IPv4-compatible (deprecated). Kept identical to watchdog's
# `research.py` (fabrik-lib W-0df68427): a change here is a change there.
_EMBEDS_IPV4 = (
    ipaddress.ip_network("64:ff9b::/96"),
    ipaddress.ip_network("::ffff:0:0:0/96"),
    ipaddress.ip_network("::/96"),
)


def _is_public(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True only for a global, non-multicast address whose every embedded IPv4 is public too: IPv4-mapped, 6to4,
    Teredo (server and client), NAT64, SIIT and IPv4-compatible forms all carry an IPv4 a network may route to (a NAT64
    gateway turns `64:ff9b::a9fe:a9fe` into 169.254.169.254). Site-local `fec0::/10` is refused too."""
    if not addr.is_global or addr.is_multicast:
        return False
    if any(addr in net for net in _EXTRA_DENY if net.version == addr.version):
        return False
    if isinstance(addr, ipaddress.IPv4Address):
        return True
    if addr.is_site_local:  # fec0::/10: deprecated, still routed inside a site; ipaddress calls it global
        return False
    embedded: list[ipaddress.IPv4Address] = []
    if addr.ipv4_mapped is not None:
        embedded.append(addr.ipv4_mapped)
    if addr.sixtofour is not None:
        embedded.append(addr.sixtofour)
    if addr.teredo is not None:
        embedded.extend(addr.teredo)
    if any(addr in net for net in _EMBEDS_IPV4):
        embedded.append(ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF))
    return all(_is_public(v4) for v4 in embedded)


def _first_public_ip(host: str) -> str | None:
    """The first address of `host` when EVERY address is public (`_is_public`), else None. An IP-literal host is
    checked as itself (never resolved). Raises `httpx.ConnectError` when the host does not resolve. The every-address
    rule also rejects a split DNS answer (one public + one private record)."""
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal = None
    if literal is not None:
        return str(literal) if _is_public(literal) else None
    name = host.lower().rstrip(".")
    if name == "localhost" or name.endswith(".localhost"):
        return None  # loopback by definition (RFC 6761), whatever a resolver answers
    try:
        infos = socket.getaddrinfo(host, None)
    except (OSError, UnicodeError) as exc:
        raise httpx.ConnectError(f"{host} did not resolve: {exc}") from exc
    first: str | None = None
    for info in infos:
        try:
            addr = ipaddress.ip_address(str(info[4][0]))
        except ValueError:
            return None
        if not _is_public(addr):
            return None
        first = first or str(addr)
    return first


class SsrfSafeTransport(httpx.HTTPTransport):
    """An httpx transport that refuses loopback, private, link-local and cloud-metadata addresses on EVERY hop and
    pins each connection to the address it validated (no re-resolution between check and connect — DNS rebinding).

    Pass it as `WebScraper(cache_dir, transport=SsrfSafeTransport())`. httpx calls `handle_request` once per hop,
    redirects included; the client's request is never mutated (a fresh request goes on the wire, the IP in its URL,
    the original `Host` and TLS SNI), so every redirect is built from — and checked against — the hostname, and
    `resp.url` keeps it. Connections are never kept alive and HTTP/2 is off, whatever the caller passes: the wire
    host is the pinned IP and httpcore pools by origin, setting SNI only at connect, so a pooled TLS connection
    verified for one hostname would otherwise serve another hostname on the same IP unverified.

    `allow=(host, port)` exempts one exact authority (e.g. a browserless control endpoint) for POST requests only —
    the scraper's browserless calls are POSTs, and a redirect to that authority (a GET) meets the guard. The `_send` method is
    the seam a test overrides so no socket opens. Built from `watchdog/watchdog_sidecar/research.py`'s transport,
    which checks only the FIRST hop (its pinned mark rides httpx's copied redirect extensions).
    """

    def __init__(
        self,
        *,
        allow: tuple[str, int | None] | None = None,
        limits: httpx.Limits | None = None,
        **kwargs: Any,
    ) -> None:
        base = limits or httpx.Limits()
        kwargs["http2"] = False
        super().__init__(
            limits=httpx.Limits(
                max_connections=base.max_connections,
                max_keepalive_connections=0,
                keepalive_expiry=base.keepalive_expiry,
            ),
            **kwargs,
        )
        self._allow = None if allow is None else (allow[0].lower().rstrip("."), allow[1])

    @staticmethod
    def _port_of(url: httpx.URL) -> int | None:
        return url.port or {"http": 80, "https": 443}.get(url.scheme)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.raw_host.decode("ascii")  # httpx's IDNA2008 A-label, never the IDNA2003 "idna" codec
        # The exemption covers only the scraper's own browserless calls, which are all POSTs (`_do_request`): a
        # redirect from a fetched page arrives as a GET, so it can never ride the exemption to the internal service.
        if (
            self._allow is not None
            and request.method == "POST"
            and host == self._allow[0]
            and self._port_of(request.url) == (self._allow[1] or {"http": 80, "https": 443}.get(request.url.scheme))
        ):
            return self._send(request)
        ip = _first_public_ip(host)
        if ip is None:
            raise AddressRefused(f"{host} is, or resolves to, a non-public address", request=request)
        headers = httpx.Headers(request.headers)
        headers["Host"] = request.url.netloc.decode("ascii")  # keeps an IPv6 literal's brackets and the port
        wire = httpx.Request(
            request.method,
            request.url.copy_with(host=ip),
            headers=headers,
            stream=request.stream,
            extensions={**request.extensions, "sni_hostname": host},
        )
        # The client re-attaches its own request (the hostname URL) to whatever this returns, so `resp.url` and the
        # next redirect are built from the hostname, never from the wire IP.
        return self._send(wire)

    def _send(self, request: httpx.Request) -> httpx.Response:
        return super().handle_request(request)


# ── Fetch result (G5) ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class FetchResult:
    """What `fetch_static_result` returns: the body plus the facts a caller needs to classify it.

    `headers` has lower-cased keys (a repeated header is joined by httpx). `title` is the `<title>` text of an HTML
    body, else None. `fetched_at` is the UTC ISO-8601 time the body was fetched (the cache entry's write time on a
    hit). Only a `status < 400`, non-wall body is ever cached, so a 4xx result is never `from_cache`.
    """

    status: int
    final_url: str
    headers: dict[str, str]
    content_type: str
    text: str
    title: str | None
    fetched_at: str
    from_cache: bool


_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def _title_of(text: str, content_type: str) -> str | None:
    if "html" not in content_type.lower() and not text.lstrip()[:15].lower().startswith(("<!doctype", "<html")):
        return None
    # A linear scan, never a backtracking regex: `<title` repeated with no close made `(.*?)</title>` quadratic.
    # ASCII-only lowering keeps every index valid for `text` (`str.lower` turns "İ" into two characters).
    head = text[:200_000]
    low = head.translate(_ASCII_LOWER)
    start = low.find("<title")
    while start >= 0 and low[start + 6 : start + 7] not in (">", "/", " ", "\t", "\n", "\r", "\f"):
        start = low.find("<title", start + 6)  # `<titles>` is another element
    if start < 0:
        return None
    gt = low.find(">", start)
    end = low.find("</title", gt) if gt >= 0 else -1
    while end >= 0 and low[end + 7 : end + 8] not in (">", " ", "\t", "\n", "\r", "\f"):
        end = low.find("</title", end + 7)  # `</titles>` does not close a title
    if end < 0:
        return None
    return " ".join(html.unescape(head[gt + 1 : end]).split()) or None


# ── Parser helpers (pure, no I/O) ───────────────────────────────────────────
_NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>(.*?)</script>',
    re.S,
)
_REACT_PROPS_RE = re.compile(
    r'<script[^>]*id="[^"]*{prefix}[^"]*"[^>]*type="application/json"[^>]*>(.*?)</script>',
    re.S,
)


def _balanced_json(text: str, open_idx: int) -> str:
    """Return the balanced `{...}` JSON object that starts at text[open_idx]."""
    depth = 0
    in_str = False
    esc = False
    for i in range(open_idx, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx : i + 1]
    raise ParseError("unbalanced JSON object")


def extract_nextjs_data(html: str) -> dict[str, Any]:
    """Parse `<script id="__NEXT_DATA__" type="application/json">…</script>`.

    Raises ParseError if the tag is absent or its body is not valid JSON.
    """
    m = _NEXT_DATA_RE.search(html)
    if m is None:
        raise ParseError("no <script id=__NEXT_DATA__> found")
    try:
        data = json.loads(m.group(1))
    except (ValueError, TypeError) as exc:
        raise ParseError(f"__NEXT_DATA__ is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ParseError("__NEXT_DATA__ did not decode to an object")
    return data


def extract_apollo_state(html: str) -> dict[str, Any]:
    """Parse `window.__APOLLO_STATE__ = {…};` from a <script> body.

    Raises ParseError if the marker is absent or the object is malformed.
    """
    marker = html.find("__APOLLO_STATE__")
    if marker == -1:
        raise ParseError("no window.__APOLLO_STATE__ found")
    brace = html.find("{", marker)
    if brace == -1:
        raise ParseError("__APOLLO_STATE__ assignment has no object")
    raw = _balanced_json(html, brace)
    try:
        data = json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ParseError(f"__APOLLO_STATE__ is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ParseError("__APOLLO_STATE__ did not decode to an object")
    return data


def extract_react_props(
    html: str, component_id_prefix: str = "react-component-props-"
) -> dict[str, Any]:
    """Parse the first `<script id="…react-component-props…" type="application/json">`
    block (Replicate's Next.js hydration pattern). Raises ParseError if absent/invalid.
    """
    pattern = re.compile(
        _REACT_PROPS_RE.pattern.replace("{prefix}", re.escape(component_id_prefix)),
        re.S,
    )
    m = pattern.search(html)
    if m is None:
        raise ParseError(f"no <script id=…{component_id_prefix}…> found")
    try:
        data = json.loads(m.group(1))
    except (ValueError, TypeError) as exc:
        raise ParseError(f"react-props block is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ParseError("react-props block did not decode to an object")
    return data


# ── Scraper ─────────────────────────────────────────────────────────────────
class WebScraper:
    """Synchronous fetcher: static (httpx) or rendered (browserless), cached,
    robots-aware, with retry/backoff. See SPEC.md for the full contract.
    """

    def __init__(
        self,
        cache_dir: Path,
        *,
        browserless_url: str | None = None,
        browserless_token: str | None = None,
        user_agent: str = _DEFAULT_UA,
        timeout_s: int = 30,
        respect_robots_txt: bool = True,
        max_retries: int = 3,
        cache_ttl_s: int = 86_400,
        max_concurrent: int = 1,
        allowed_hosts: Iterable[str] | None = None,
        transport: httpx.BaseTransport | None = None,  # test seam (httpx.MockTransport)
    ) -> None:
        self._cache_dir = Path(cache_dir)
        # SSRF scope guard. `None` (default) = OFF, so every existing caller is unchanged.
        # Hosts are lower-cased once here; httpx already lower-cases `resp.url.host`.
        self._allowed_hosts: set[str] | None = (
            {h.strip().lower() for h in allowed_hosts if h and h.strip()}
            if allowed_hosts is not None
            else None
        )
        self._browserless_url = browserless_url.rstrip("/") if browserless_url else None
        self._browserless_token = browserless_token or None
        self._user_agent = user_agent
        self._timeout_s = timeout_s
        self._respect_robots = respect_robots_txt
        self._max_retries = max_retries
        self._cache_ttl_s = cache_ttl_s
        self._sem = Semaphore(max_concurrent) if max_concurrent > 1 else None
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout_s,
            follow_redirects=True,
            transport=transport,
        )
        # With the address guard, a rendered TARGET is checked too: it travels inside the POST body to browserless,
        # which the transport cannot see (and exempts), so `fetch_rendered` checks it before the POST.
        self._guarded = isinstance(transport, SsrfSafeTransport)
        self._robots: dict[str, tuple[RobotFileParser, float]] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> WebScraper:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── public fetch API ──────────────────────────────────────────────────
    def fetch_static(
        self, url: str, *, ignore_cache: bool = False, accept_markdown: bool = False
    ) -> str:
        """httpx.get with no JS execution. Cached, robots-aware, retried.

        `accept_markdown=True` sends `Accept: text/markdown, text/html;q=0.9` (a site that serves markdown answers
        with it as-is) and caches under its own key; the default sends no Accept and keeps today's key.
        """
        return self.fetch_static_result(
            url, ignore_cache=ignore_cache, accept_markdown=accept_markdown
        ).text

    def fetch_static_result(
        self, url: str, *, ignore_cache: bool = False, accept_markdown: bool = False
    ) -> FetchResult:
        """`fetch_static` with the response facts: status, final URL, headers, content type, title, fetch time.

        A 4xx (not 429) is RETURNED with its status, as `fetch_static` returns its body; a 5xx or 429 still raises
        `FetchError` (with `status`, `body`, `headers`) after the retries.
        """
        return self._fetch_result(
            url,
            method="GET",
            body=None,
            ignore_cache=ignore_cache,
            accept=_ACCEPT_MARKDOWN if accept_markdown else None,
        )

    def fetch_rendered(
        self,
        url: str,
        *,
        wait_for_selector: str | None = None,
        stealth: bool = False,
        ignore_cache: bool = False,
    ) -> str:
        """browserless executes JS and returns the DOM.

        `stealth=False` → POST `/content` (fast). `stealth=True` → POST `/function`
        with a stealth init script (masks `navigator.webdriver`/`languages`, sets
        `sec-ch-ua` + a real Chrome UA) to get past basic Cloudflare/WAF bot walls.
        """
        if not self._browserless_url:
            raise FetchError("fetch_rendered requires browserless_url to be set")
        if self._guarded:
            url = self._checked_render_target(url)
        if stealth:
            # /function returns {"data": "<html>", "type": ...}; verified live vs vps1.
            js = self._stealth_function_js(url, wait_for_selector)
            return self._fetch(
                url,
                method="FUNCTION",
                body=js,
                ignore_cache=ignore_cache,
                success_only=True,
                extract=_extract_function_html,
            )
        # browserless v2 /content rejects a string `userAgent` ("must be of type
        # object"); it renders with its own Chrome UA. Verified live against vps1.
        payload: dict[str, object] = {"url": url}
        if wait_for_selector is not None:
            payload["waitForSelector"] = {
                "selector": wait_for_selector,
                "timeout": 10_000,
            }
        body = json.dumps(payload, sort_keys=True)
        # browserless contract (SPEC §browserless): only 200 is success; anything
        # else is a FetchError — an error page must never be returned as "HTML".
        return self._fetch(
            url,
            method="CONTENT",
            body=body,
            ignore_cache=ignore_cache,
            success_only=True,
        )

    @staticmethod
    def _checked_render_target(url: str) -> str:
        """The render target, address-checked and normalised — the string browserless receives is the one checked.

        Chrome parses a URL by the WHATWG rules (a `\\` is a `/`, tabs and newlines are stripped) and httpx does not,
        so `http://127.0.0.1\\@pub.example/` would pass as `pub.example` here and load 127.0.0.1 there. A backslash,
        control character or whitespace anywhere is refused, and the payload carries `str(httpx.URL(url))`. Checked at
        call time only: browserless resolves the host again itself, so DNS rebinding is not covered (README).
        """
        if any(c == "\\" or c.isspace() or ord(c) < 0x20 or ord(c) == 0x7F for c in url):
            raise ScopeError(f"{url!r}: a render target may not hold a backslash, whitespace or control character",
                             requested=url)
        try:
            parsed = httpx.URL(url)
        except (httpx.InvalidURL, UnicodeError) as exc:
            raise ScopeError(f"{url}: not a valid render target ({exc})", requested=url) from exc
        if parsed.scheme not in ("http", "https") or not parsed.raw_host:
            raise ScopeError(f"{url}: a render target must be an http(s) URL with a host", requested=url)
        if b"%" in parsed.raw_host:
            # httpx resolves a percent-encoded host literally; Chrome percent-decodes it first, so the two would
            # resolve different names (and it also drops an IPv6 zone id, which Chrome refuses anyway).
            raise ScopeError(f"{url}: a render target's host may not be percent-encoded", requested=url)
        try:
            ip = _first_public_ip(parsed.raw_host.decode("ascii"))
        except httpx.ConnectError as exc:  # does not resolve: a connection failure, as on the static path
            raise FetchError(f"{url}: {exc}") from exc
        if ip is None:
            raise ScopeError(f"{url}: the render target is not a public address", requested=url)
        return str(parsed)

    def _stealth_function_js(self, url: str, wait_for_selector: str | None) -> str:
        """ESM default-export function for browserless v2 `/function` (verified live).
        Values are json.dumps-embedded so a URL/selector can't break out of the JS.
        """
        selector = wait_for_selector or "h1,h2,h3,article,main,.content,.docs"
        timeout_ms = self._timeout_s * 1000
        return (
            "export default async function ({ page }) {\n"
            "  await page.setViewport({ width: 1280, height: 900 });\n"
            f"  await page.setUserAgent({json.dumps(_STEALTH_UA)});\n"
            "  await page.setExtraHTTPHeaders({\n"
            '    "sec-ch-ua": "\\"Chromium\\";v=\\"124\\", \\"Google Chrome\\";v=\\"124\\"",\n'
            '    "sec-ch-ua-mobile": "?0",\n'
            '    "sec-ch-ua-platform": "\\"Windows\\""\n'
            "  });\n"
            "  await page.evaluateOnNewDocument(() => {\n"
            "    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });\n"
            "    Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] });\n"
            "  });\n"
            f"  await page.goto({json.dumps(url)}, "
            f'{{ waitUntil: "networkidle0", timeout: {timeout_ms} }});\n'
            f"  try {{ await page.waitForSelector({json.dumps(selector)}, "
            "{ timeout: 15000 }); } catch (e) {}\n"
            "  await new Promise(r => setTimeout(r, 2000));\n"
            '  return { data: await page.content(), type: "text/html" };\n'
            "}\n"
        )

    # ── internals ─────────────────────────────────────────────────────────
    def _fetch(
        self,
        url: str,
        *,
        method: str,
        body: str | None,
        ignore_cache: bool,
        success_only: bool = False,
        extract: Callable[[httpx.Response], str] | None = None,
    ) -> str:
        return self._fetch_result(
            url,
            method=method,
            body=body,
            ignore_cache=ignore_cache,
            success_only=success_only,
            extract=extract,
        ).text

    def _fetch_result(
        self,
        url: str,
        *,
        method: str,
        body: str | None,
        ignore_cache: bool,
        success_only: bool = False,
        extract: Callable[[httpx.Response], str] | None = None,
        accept: str | None = None,
    ) -> FetchResult:
        if method == "GET":
            self._assert_fetchable(url)
        key = self._cache_key(url, method, body, accept)
        if not ignore_cache:
            env = self._cache_envelope(key)
            if env is not None:
                return self._result_from_envelope(env, url)
        # robots only matters on a real fetch; a cache hit already returned above.
        if self._respect_robots and not self._can_fetch(url):
            raise RobotsError(f"robots.txt forbids {self._user_agent!r} on {url}")

        if self._sem is not None:
            self._sem.acquire()
        try:
            resp = self._send_with_retry(url, method=method, body=body, accept=accept)
        finally:
            if self._sem is not None:
                self._sem.release()

        # SSRF scope guard — BEFORE the success check, the extract, and the cache write.
        # The client follows redirects, so an in-scope URL can answer `302 Location:
        # http://169.254.169.254/…` and this method would otherwise return the cloud
        # metadata body attributed to the in-scope URL the caller asked for. The final URL
        # never leaves this module, so the check is not expressible from outside it.
        # Reported by web-ecommerce-factory 2026-08-16 with a working reproduction.
        self._assert_host_allowed(resp, requested=url, method=method)

        if success_only and resp.status_code != 200:
            raise FetchError(
                f"{method} {url} -> HTTP {resp.status_code}",
                status=resp.status_code,
                body=resp.text,
            )
        # `extract` transforms the response into the value we cache + return (e.g.
        # pulling `.data` out of a browserless /function JSON envelope).
        value = extract(resp) if extract is not None else resp.text
        # Cache poisoning guard (2026-06-30): a Cloudflare/WAF challenge page
        # arrives as HTTP 200 with an interstitial body. Without this guard,
        # the bot-wall HTML gets stored in the on-disk cache and every fetch
        # for the next ~24h returns the poisoned page — caller escalates to
        # stealth on every call, paying the tax repeatedly. Better: don't
        # cache the poisoned page at all, so the next fetch retries from
        # scratch (and the caller's stealth escalation only runs when actually
        # needed). Surfaced by the fabrik adversarial review (M5 finding).
        fetched_at = datetime.now(UTC).isoformat()
        if resp.status_code < 400 and not is_bot_wall(value):
            self._cache_put(
                key,
                url=url,
                method=method,
                status=resp.status_code,
                body=value,
                headers=resp.headers,
                final_host=(resp.url.host or "").lower(),
                final_url=str(resp.url),
                fetched_at=fetched_at,
            )
        # static 4xx (except 429, handled in retry) returns the body for the caller.
        content_type = resp.headers.get("content-type", "")
        return FetchResult(
            status=resp.status_code,
            final_url=str(resp.url),
            headers={k.lower(): v for k, v in resp.headers.items()},
            content_type=content_type,
            text=value,
            title=_title_of(value, content_type),
            fetched_at=fetched_at,
            from_cache=False,
        )

    @staticmethod
    def _assert_fetchable(url: str) -> None:
        """A URL this module cannot fetch is refused as a `ScopeError` before any request (an invalid IPv4 or IPv6
        literal, no scheme, no host), so every error out of a GET is a `WebScrapeError`."""
        try:
            parsed = httpx.URL(url)
            ok = parsed.scheme in ("http", "https") and bool(parsed.raw_host)
            urlparse(url).hostname  # noqa: B018 — the robots path parses with urllib; an invalid URL raises here
        except (httpx.InvalidURL, ValueError, UnicodeError) as exc:
            raise ScopeError(f"{url!r}: not a valid URL ({exc})", requested=url) from exc
        if not ok:
            raise ScopeError(f"{url!r}: only http(s) URLs with a host are fetched", requested=url)

    def _assert_host_allowed(
        self, resp: httpx.Response, *, requested: str, method: str
    ) -> None:
        """Refuse a response whose FINAL hop is outside ``allowed_hosts``.

        Checks ``resp.url.host`` — the last hop after redirects — which is the entire point:
        the caller host-checks the URL it is ABOUT to request and can never see where the
        bytes actually came from.

        ⚠ **Only the GET path is protectable here.** `fetch_rendered` POSTs to *browserless*,
        so `resp.url.host` is browserless's host and the target's redirects happen server-side,
        invisible to us. Checking it would compare browserless against the site allow-list and
        refuse every rendered fetch. That path is therefore skipped and documented as an
        uncovered gap in the README rather than given a guard that only looks like one.
        """
        if self._allowed_hosts is None or method != "GET":
            return
        final_host = (resp.url.host or "").lower()
        if final_host in self._allowed_hosts:
            return
        raise ScopeError(
            f"{requested} redirected off-scope to {final_host!r} — refused "
            f"(allowed_hosts={sorted(self._allowed_hosts)})",
            requested=requested,
            final_host=final_host,
        )

    def _send_with_retry(
        self, url: str, *, method: str, body: str | None, accept: str | None = None
    ) -> httpx.Response:
        last_status: int | None = None
        last_body = ""
        last_headers: Mapping[str, str] = {}
        # attempt 0 + up to max_retries retries; backoff 1s/2s/4s between attempts.
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._do_request(url, method=method, body=body, accept=accept)
            except AddressRefused as exc:
                # A non-public address is a scope refusal: LOUD, at once, never retried (see ScopeError).
                raise ScopeError(f"{url}: {exc}", requested=url) from exc
            except UnicodeError as exc:
                # A redirect to a malformed IDN fails inside httpx's redirect builder, before any transport runs.
                raise ScopeError(f"{url}: a hop names an invalid host ({exc})", requested=url) from exc
            except httpx.RequestError as exc:
                last_status, last_body, last_headers = None, str(exc), {}
            else:
                if resp.status_code < 500 and resp.status_code != 429:
                    return resp  # success or a non-retryable 4xx
                last_status, last_body, last_headers = resp.status_code, resp.text, resp.headers
            if attempt < self._max_retries:
                time.sleep(2**attempt)
        raise FetchError(
            f"{method} {url} failed after {self._max_retries} retries",
            status=last_status,
            body=last_body,
            headers=last_headers,
        )

    def _do_request(
        self, url: str, *, method: str, body: str | None, accept: str | None = None
    ) -> httpx.Response:
        if method == "GET":
            return self._client.get(url, headers={"Accept": accept} if accept else None)
        # browserless POST. Token via Authorization: Bearer header (v2-accepted,
        # verified live) — keeps the secret out of the URL/query log. /content takes
        # JSON; /function takes the JS function body (application/javascript).
        headers = {}
        if self._browserless_token:
            headers["Authorization"] = f"Bearer {self._browserless_token}"
        if method == "CONTENT":
            headers["Content-Type"] = "application/json"
            return self._client.post(
                f"{self._browserless_url}/content", content=body, headers=headers
            )
        if method == "FUNCTION":
            headers["Content-Type"] = "application/javascript"
            return self._client.post(
                f"{self._browserless_url}/function", content=body, headers=headers
            )
        raise FetchError(f"unknown request method {method!r}")

    # ── cache (self-contained; SPEC envelope + sha256 + <first-2>/<key>.json) ──
    @staticmethod
    def _cache_key(url: str, method: str, body: str | None, accept: str | None = None) -> str:
        h = hashlib.sha256()
        h.update(url.encode())
        h.update(method.encode())
        if body is not None:
            h.update(hashlib.sha256(body.encode()).hexdigest().encode())
        if accept is not None:  # only a non-default Accept joins the key: every existing entry stays warm
            h.update(b"\x00accept:" + accept.encode())
        return h.hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self._cache_dir / key[:2] / f"{key}.json"

    def _cache_get(self, key: str) -> str | None:
        env = self._cache_envelope(key)
        return None if env is None else env["body"]

    def _result_from_envelope(self, env: dict[str, Any], url: str) -> FetchResult:
        headers = env.get("headers")
        hdrs = {str(k).lower(): str(v) for k, v in headers.items()} if isinstance(headers, dict) else {}
        final_url = env.get("final_url")
        content_type = env.get("content_type")
        ctype = content_type if isinstance(content_type, str) else hdrs.get("content-type", "")
        status = env.get("status")
        text: str = env["body"]
        return FetchResult(
            status=status if isinstance(status, int) and not isinstance(status, bool) else 200,
            final_url=final_url if isinstance(final_url, str) and final_url else url,
            headers=hdrs,
            content_type=ctype,
            text=text,
            title=_title_of(text, ctype),
            fetched_at=str(env.get("fetched_at", "")),
            from_cache=True,
        )

    def _cache_envelope(self, key: str) -> dict[str, Any] | None:
        """The cached envelope for `key` (body a str), or None — stale, corrupt, absent, or off-scope."""
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            env = json.loads(path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(env["fetched_at"])
            # TypeError guards a naive/foreign timestamp (aware - naive -> TypeError).
            age = (datetime.now(UTC) - fetched).total_seconds()
        except (ValueError, KeyError, OSError, TypeError):
            return None  # corrupt/unreadable envelope -> treat as a miss, never crash
        if age > self._cache_ttl_s:
            return None  # stale
        # ⚠ The scope guard MUST be re-applied on the cache path, and this is the half a
        # guard placed only after `_send_with_retry` misses entirely: `_fetch` returns from
        # cache BEFORE it ever sends, so a body written off-scope keeps being served for the
        # whole TTL with no network call and no check. Worse, the entry is keyed on the
        # REQUESTED url, so the off-scope body sits under the in-scope key. Reproduced.
        #
        # Entries written before this field existed have no `final_host`; with an allow-list
        # set they are treated as a MISS and refetched (fail-closed — a one-time cache
        # warm-up, never a silently-trusted legacy body). With no allow-list, unchanged.
        if self._allowed_hosts is not None:
            final_host = env.get("final_host")
            if not isinstance(final_host, str) or final_host.lower() not in self._allowed_hosts:
                return None
        body = env.get("body")
        if not isinstance(body, str) or not isinstance(env, dict):
            return None
        if not env.get("final_url") and env.get("method", "GET") == "GET":
            # Written before `final_url` existed: trusted only when its body came from the requested host, so a
            # `FetchResult.final_url` read from it is never the requested URL standing in for a redirect target.
            final_host = env.get("final_host")
            try:
                requested = (urlparse(str(env.get("url", ""))).hostname or "").lower()
            except ValueError:
                return None  # an unreadable stored URL: treat as a miss
            if isinstance(final_host, str) and final_host and final_host.lower() != requested:
                return None
        return env

    def _cache_put(
        self,
        key: str,
        *,
        url: str,
        method: str,
        status: int,
        body: str,
        headers: httpx.Headers,
        final_host: str = "",
        final_url: str = "",
        fetched_at: str | None = None,
    ) -> None:
        path = self._cache_path(key)
        env = {
            "url": url,
            "method": method,
            # The host the bytes ACTUALLY came from (last hop). Recorded so `_cache_get`
            # can enforce `allowed_hosts` without a network round-trip — see the guard there.
            "final_host": final_host,
            "final_url": final_url or url,
            "content_type": headers.get("content-type", ""),
            "fetched_at": fetched_at or datetime.now(UTC).isoformat(),
            "status": status,
            "body": body,  # the value we return (extracted html, not the raw envelope)
            "headers": dict(headers),
        }
        # Per-write unique temp name so concurrent writers of the SAME key don't
        # race on a shared temp path (else the 2nd replace() hits FileNotFoundError).
        tmp = path.with_name(f"{key}.{uuid.uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(env), encoding="utf-8")
            tmp.replace(path)  # atomic on the same filesystem
        except OSError:
            # The cache is best-effort: a write failure must NOT fail a fetch that
            # already succeeded. Drop any partial temp and move on.
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)

    # ── robots.txt (urllib.robotparser; fetched via httpx so it's testable) ──
    def _can_fetch(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc
        now = time.time()
        cached = self._robots.get(domain)
        if cached is None or (now - cached[1]) > 3600:  # cache 1h per domain
            rp = self._load_robots(f"{parsed.scheme}://{domain}/robots.txt")
            self._robots[domain] = (rp, now)
        else:
            rp = cached[0]
        return rp.can_fetch(self._user_agent, url)

    def _load_robots(self, robots_url: str) -> RobotFileParser:
        rp = RobotFileParser()
        try:
            resp = self._client.get(robots_url)
        except (httpx.RequestError, UnicodeError):
            rp.parse([])  # fetch failed -> empty ruleset -> default allowed
            return rp
        # ⚠ The robots fetch goes through `self._client` DIRECTLY, not through `_fetch`, so it
        # never met the scope guard. Found reviewing the guard 2026-08-23: with
        # `allowed_hosts={"client.example"}`, a `/robots.txt` answering
        # `302 → http://169.254.169.254/…` had the scraper contact the metadata endpoint and then
        # PARSE its response as a crawl ruleset — attacker-controlled robots rules from a host the
        # caller had explicitly excluded, and the page fetch proceeded normally.
        #
        # Treated as a failed fetch (the module's existing fail-open for robots) rather than
        # raising: robots is politeness, and refusing the whole page because its robots redirected
        # would punish the caller for the target's behaviour. What must NOT happen is parsing rules
        # from an off-scope origin.
        if self._allowed_hosts is not None and (resp.url.host or "").lower() not in self._allowed_hosts:
            rp.parse([])
            return rp
        if resp.status_code >= 400:
            rp.parse([])  # 404/timeout/auth -> default allowed (per SPEC)
        else:
            rp.parse(resp.text.splitlines())
        return rp
