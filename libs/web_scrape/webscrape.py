"""Deterministic web-scrape primitive — httpx for static/SSR, vps1 browserless
for JS-rendered, with built-in __NEXT_DATA__ / Apollo / React-props parsers.

Vendor this folder (copy), don't import. No LLM extraction, no bundled headless
browser, no managed scraping service, no async — see SPEC.md.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
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
]

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
    """An HTTP fetch failed after all retries (5xx / 429 / connection error)."""

    def __init__(
        self, message: str, *, status: int | None = None, body: str = ""
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class ParseError(WebScrapeError):
    """An extract_* helper's target was absent or malformed."""


class RobotsError(WebScrapeError):
    """robots.txt forbids this user-agent on this URL (and the caller did not opt out)."""


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


def extract_nextjs_data(html: str) -> dict:
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


def extract_apollo_state(html: str) -> dict:
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
) -> dict:
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
        transport: httpx.BaseTransport | None = None,  # test seam (httpx.MockTransport)
    ) -> None:
        self._cache_dir = Path(cache_dir)
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
        self._robots: dict[str, tuple[RobotFileParser, float]] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> WebScraper:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── public fetch API ──────────────────────────────────────────────────
    def fetch_static(self, url: str, *, ignore_cache: bool = False) -> str:
        """httpx.get with no JS execution. Cached, robots-aware, retried."""
        return self._fetch(url, method="GET", body=None, ignore_cache=ignore_cache)

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
        key = self._cache_key(url, method, body)
        if not ignore_cache:
            cached = self._cache_get(key)
            if cached is not None:
                return cached
        # robots only matters on a real fetch; a cache hit already returned above.
        if self._respect_robots and not self._can_fetch(url):
            raise RobotsError(f"robots.txt forbids {self._user_agent!r} on {url}")

        if self._sem is not None:
            self._sem.acquire()
        try:
            resp = self._send_with_retry(url, method=method, body=body)
        finally:
            if self._sem is not None:
                self._sem.release()

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
        if resp.status_code < 400 and not is_bot_wall(value):
            self._cache_put(
                key,
                url=url,
                method=method,
                status=resp.status_code,
                body=value,
                headers=resp.headers,
            )
        # static 4xx (except 429, handled in retry) returns the body for the caller.
        return value

    def _send_with_retry(
        self, url: str, *, method: str, body: str | None
    ) -> httpx.Response:
        last_status: int | None = None
        last_body = ""
        # attempt 0 + up to max_retries retries; backoff 1s/2s/4s between attempts.
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._do_request(url, method=method, body=body)
            except httpx.RequestError as exc:
                last_status, last_body = None, str(exc)
            else:
                if resp.status_code < 500 and resp.status_code != 429:
                    return resp  # success or a non-retryable 4xx
                last_status, last_body = resp.status_code, resp.text
            if attempt < self._max_retries:
                time.sleep(2**attempt)
        raise FetchError(
            f"{method} {url} failed after {self._max_retries} retries",
            status=last_status,
            body=last_body,
        )

    def _do_request(self, url: str, *, method: str, body: str | None) -> httpx.Response:
        if method == "GET":
            return self._client.get(url)
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
    def _cache_key(url: str, method: str, body: str | None) -> str:
        h = hashlib.sha256()
        h.update(url.encode())
        h.update(method.encode())
        if body is not None:
            h.update(hashlib.sha256(body.encode()).hexdigest().encode())
        return h.hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self._cache_dir / key[:2] / f"{key}.json"

    def _cache_get(self, key: str) -> str | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            env = json.loads(path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(env["fetched_at"])
            # TypeError guards a naive/foreign timestamp (aware - naive -> TypeError).
            age = (datetime.now(timezone.utc) - fetched).total_seconds()
        except (ValueError, KeyError, OSError, TypeError):
            return None  # corrupt/unreadable envelope -> treat as a miss, never crash
        if age > self._cache_ttl_s:
            return None  # stale
        body = env.get("body")
        return body if isinstance(body, str) else None

    def _cache_put(
        self,
        key: str,
        *,
        url: str,
        method: str,
        status: int,
        body: str,
        headers: httpx.Headers,
    ) -> None:
        path = self._cache_path(key)
        env = {
            "url": url,
            "method": method,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
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
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

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
        except httpx.RequestError:
            rp.parse([])  # fetch failed -> empty ruleset -> default allowed
            return rp
        if resp.status_code >= 400:
            rp.parse([])  # 404/timeout/auth -> default allowed (per SPEC)
        else:
            rp.parse(resp.text.splitlines())
        return rp
