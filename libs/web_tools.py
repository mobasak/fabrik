"""Web-research / browser tool executors — standalone, vendorable, no pool behind it.

Env-keyed HTTP tools that call the **hosted** Exa / Brave / Firecrawl / Context7 APIs.
Extracted from the `subagents` pool so a product can vendor JUST this at runtime — it
depends on nothing but `httpx` (no OpenRouter client, no ledger, no sandbox). Each
executor is a thin ``httpx`` call:

* the env key is read FIRST — unset ⇒ ``ToolResult(ok=False, "<X>_API_KEY not set")``
  and **no network call** is made;
* the response body is read with a **streaming byte cap** (:func:`_fetch`) so a
  giant body can't OOM the caller, and text output is ``_truncate``-bounded;
* it is **TOTAL** — every failure (HTTP status, timeout, bad JSON, non-dict shape,
  bad args) returns ``ToolResult(ok=False, …)``, never raises, so a tool loop can
  feed the error back to the model.

No vendor SDKs. Keys travel in HEADERS only (never a URL/query) so they cannot leak
into output/error. Endpoints + auth grounded live 2026-07-05:

    Exa       POST https://api.exa.ai/search                    header  x-api-key: $EXA_API_KEY
    Brave     GET  https://api.search.brave.com/res/v1/web/search  header  X-Subscription-Token: $BRAVE_API_KEY
    Firecrawl POST https://api.firecrawl.dev/v2/{scrape,crawl}  header  Authorization: Bearer $FIRECRAWL_API_KEY
    Context7  GET  https://context7.com/api/v2/{libs/search,context}  header  Authorization: Bearer $CONTEXT7_API_KEY
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

# --- inlined from the pool's tools.py (vendor, don't import — no cross-module runtime dep) --------

_MAX_OUTPUT = 20_000  # cap captured text so a runaway response can't blow up context


@dataclass
class ToolResult:
    """One tool call's outcome. ``ok`` gates whether a caller treats it as a
    success; ``output`` is fed back to the model; ``error`` is set on failure."""

    ok: bool
    output: str
    error: str | None = None


# --- the NEW async / structured / injected surface (Approach B — shared request core) -------------
#
# The legacy sync ``execute_web_tool``/``ToolResult`` surface above stays byte-identical (pinned by
# ``test_web_tools.py``). The surface below adds, WITHOUT touching it: structured rows instead of a
# text blob, per-call cost telemetry, an INJECTED ``WebToolsConfig`` (no module-level env reads), and
# an ``httpx.AsyncClient`` transport for async consumers. Both surfaces share the request-building
# helpers (``_exa_body`` / ``_brave_params`` / the endpoints) so the query shape can never fork.


@dataclass(frozen=True)
class SearchRow:
    """One structured search hit. ``text`` is bounded by the caller's text budget;
    ``extra`` carries leg-specific fields (e.g. a description, published date)."""

    title: str
    url: str
    text: str
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class LegResult:
    """One async leg's outcome — NEVER an exception. ``rows`` is the structured hits,
    ``cost_usd`` the per-call money (Exa ``costDollars``), ``credits`` the vendor credits
    (Firecrawl ``creditsUsed``), ``error`` set on any failure (unset key / 402 / timeout /
    malformed JSON)."""

    ok: bool
    rows: list[SearchRow]
    cost_usd: Decimal = Decimal("0")
    credits: int = 0
    error: str | None = None


@dataclass(frozen=True)
class WebToolsConfig:
    """Injected config for the async surface — no ``os.environ`` reads. Keys travel in
    headers only. ``text_budget`` bounds each row's text; the ``*_price_usd`` fields let
    the caller value Exa cost when the response omits ``costDollars``."""

    exa_api_key: str | None = None
    brave_api_key: str | None = None
    firecrawl_api_key: str | None = None
    text_budget: int = 1000
    timeout_s: float = 30.0
    exa_search_price_usd: Decimal = Decimal("0")
    exa_page_price_usd: Decimal = Decimal("0")


def _truncate(text: str) -> str:
    return text if len(text) <= _MAX_OUTPUT else text[:_MAX_OUTPUT] + "\n…[truncated]"


def _fn(
    name: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    """An OpenRouter/OpenAI function-tool schema entry (the shape a tool-looping
    model is shown). Reused verbatim so `WEB_TOOL_SCHEMAS` drops into any loop that
    speaks the OpenAI tools format."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


# --------------------------------------------------------------------------------------------------

WEB_TOOL_NAMES: frozenset[str] = frozenset(
    {"web_search", "web_search_brave", "web_scrape", "web_crawl", "docs_lookup"}
)

_EXA_URL = "https://api.exa.ai/search"
_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
_FC_BASE = "https://api.firecrawl.dev/v2"
_C7_BASE = "https://context7.com/api/v2"
_DEFAULT_TIMEOUT = 30.0
_CRAWL_MAX_WAIT = 60.0  # total seconds to wait for an async crawl
_CRAWL_POLL_INTERVAL = 2.0
_CRAWL_MAX_PAGES = 20
_CRAWL_TERMINAL_FAIL = frozenset({"failed", "cancelled", "canceled", "error"})
_MAX_RESP_BYTES = 2_000_000  # streaming read aborts past this — bounds peak memory
_SNIPPET = 1000  # per-result text cap before the overall _truncate


class _MissingKeyError(Exception):
    """A required *_API_KEY env var is unset."""


class _HttpError(Exception):
    """A non-2xx status (kept separate so the key/headers are never in the message)."""


def _need(env: str) -> str:
    val = os.getenv(env)
    if not val:
        raise _MissingKeyError(env)
    return val


def _fetch(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    timeout_s: float,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> bytes:
    """Stream the response body, aborting past ``_MAX_RESP_BYTES`` (true memory
    bound — httpx would otherwise buffer the whole body before we could check).
    Raises :class:`_HttpError` on a non-2xx status (message carries only the code,
    never the key/headers)."""
    with client.stream(
        method, url, headers=headers, json=json_body, params=params, timeout=timeout_s
    ) as resp:
        buf = bytearray()
        for chunk in resp.iter_bytes():
            buf.extend(chunk)
            if len(buf) > _MAX_RESP_BYTES:
                raise ValueError(f"response exceeds {_MAX_RESP_BYTES} bytes")
        if resp.status_code >= 400:
            raise _HttpError(f"http {resp.status_code}")
        return bytes(buf)


def _obj(body: bytes) -> dict[str, Any]:
    data = json.loads(body or b"{}")
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def _dicts(seq: Any) -> list[dict[str, Any]]:
    """The dict elements of a sequence (non-dicts skipped — defensive against an
    unexpected response shape, so a stray string can't crash an executor)."""
    return [x for x in seq if isinstance(x, dict)] if isinstance(seq, list) else []


# --- shared request-building + pure parsers (both surfaces call these — one query shape) ----------


def _exa_body(args: dict[str, Any]) -> dict[str, Any]:
    """The Exa /search request JSON — shared by the sync and async executors so the
    query shape (numResults clamp, contents) can never diverge.

    Optional geo/filter fields are ADDITIVE and truthiness-gated: an absent/falsy value leaves the
    payload byte-identical to the base request, so this is backward-compatible for every caller.
    Grounded live 2026-08-29 against https://exa.ai/docs/reference/search :
    - ``category`` → top-level ``category`` (company/publication/news/people/… — other strings are hints);
    - ``include_domains`` → ``includeDomains`` (camelCase; ≤1200 entries; a ``*.example.com`` wildcard or a
      ``host/path`` prefix is accepted);
    - ``user_location`` → ``userLocation`` (two-letter ISO country code, e.g. ``US``);
    - ``search_type`` → ``type`` (``auto`` default / ``fast`` / ``instant`` at base rate;
      ``deep-lite`` / ``deep`` / ``deep-reasoning`` cost MORE — the caller's cost estimate must account for it).
    """
    n = int(args.get("num_results", 10))
    body: dict[str, Any] = {
        "query": str(args["query"]),
        "numResults": min(max(n, 1), 100),
        "contents": {"text": True},
    }
    if args.get("category"):
        body["category"] = str(args["category"])
    include_domains = args.get("include_domains")
    if include_domains:
        # Normalize DEFENSIVELY to a list of non-empty domain strings — this is a vendored module, so a
        # programmatic caller passing the wrong type must get a predictable result, never a silent-wrong
        # filter: a str is ONE domain (never iterated char-by-char); a list/tuple keeps its truthy entries
        # as strings (so a None/'' in the list is dropped, not sent as the literal "None"); anything else
        # (a dict whose keys would silently become domains, an int, bytes iterated as code points) is NOT a
        # domain list and is ignored rather than turned into a garbage filter. Only send the field if a real
        # domain survived — so a degenerate value stays byte-identical to the base payload. The rule:
        # a str is ONE domain; ANY OTHER iterable (list/tuple/set/frozenset/generator) keeps its truthy
        # entries as strings; but bytes (would iterate as code points) and a Mapping (whose KEYS would
        # silently become domains) are NOT domain lists and are rejected; a non-iterable (int) likewise.
        if isinstance(include_domains, str):
            domains = [include_domains]
        elif isinstance(include_domains, (bytes, bytearray, Mapping)):
            domains = []
        elif isinstance(include_domains, Iterable):
            domains = [str(d) for d in include_domains if d]
        else:
            domains = []
        if domains:
            body["includeDomains"] = domains
    if args.get("user_location"):
        body["userLocation"] = str(args["user_location"])
    if args.get("search_type"):
        body["type"] = str(args["search_type"])
    return body


def _brave_params(args: dict[str, Any]) -> dict[str, Any]:
    """The Brave /web/search query params — shared by both surfaces (count max 20).

    Optional geo/language fields are ADDITIVE + truthiness-gated (absent/falsy → byte-identical payload).
    Grounded live 2026-08-29 against the Brave Web Search API query-params doc:
    - ``country`` → ``country`` (two-character country code, e.g. ``DE``);
    - ``search_lang`` → ``search_lang`` (a content-language code, e.g. ``de``).
    """
    n = int(args.get("num_results", 10))
    params: dict[str, Any] = {"q": str(args["query"]), "count": min(max(n, 1), 20)}
    if args.get("country"):
        params["country"] = str(args["country"])
    if args.get("search_lang"):
        params["search_lang"] = str(args["search_lang"])
    return params


def _decimal(value: Any) -> Decimal:
    """A tolerant Decimal — a malformed/absent figure reads as 0 (never a raise)."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _exa_cost(obj: dict[str, Any]) -> Decimal | None:
    """Exa self-reports ``costDollars: {total, ...}`` — read ``total``. Returns ``None`` when the
    field is ABSENT/malformed (distinct from a genuine 0) so the caller can fall back to its
    configured per-call estimate instead of silently booking $0 for a paid call."""
    cost = obj.get("costDollars")
    if not isinstance(cost, dict) or "total" not in cost:
        return None
    try:
        return Decimal(str(cost["total"]))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_exa(body: bytes, *, text_budget: int) -> tuple[list[SearchRow], Decimal | None]:
    """Structured Exa rows + per-call cost (``None`` when ``costDollars`` is absent — the caller
    supplies the fallback estimate). Each row's text is bounded by ``text_budget``."""
    obj = _obj(body)
    rows = [
        SearchRow(
            title=str(r.get("title", "")),
            url=str(r.get("url", "")),
            text=(r.get("text") or "")[:text_budget],
        )
        for r in _dicts(obj.get("results", []))
    ]
    return rows, _exa_cost(obj)


def _parse_brave(body: bytes, *, text_budget: int) -> list[SearchRow]:
    """Structured Brave rows (the nested ``web.results``); the description becomes ``text``."""
    web = _obj(body).get("web")
    results = _dicts((web or {}).get("results", []) if isinstance(web, dict) else [])
    return [
        SearchRow(
            title=str(r.get("title", "")),
            url=str(r.get("url", "")),
            text=(r.get("description") or "")[:text_budget],
            extra={"description": str(r.get("description") or "")},
        )
        for r in results
    ]


def _exa_search(args: dict[str, Any], client: httpx.Client, timeout_s: float) -> ToolResult:
    key = _need("EXA_API_KEY")
    body = _fetch(
        client,
        "POST",
        _EXA_URL,
        headers={"x-api-key": key},
        timeout_s=timeout_s,
        json_body=_exa_body(args),
    )
    lines = [
        f"{r.get('title', '')}\n{r.get('url', '')}\n{(r.get('text') or '')[:_SNIPPET]}"
        for r in _dicts(_obj(body).get("results", []))
    ]
    return ToolResult(ok=True, output=_truncate("\n\n".join(lines) or "(no results)"))


def _brave_search(args: dict[str, Any], client: httpx.Client, timeout_s: float) -> ToolResult:
    # Brave Web Search API: GET …/web/search?q=&count=  header X-Subscription-Token.
    # Response: {"web": {"results": [{title, url, description}]}}. Count max 20.
    key = _need("BRAVE_API_KEY")
    body = _fetch(
        client,
        "GET",
        _BRAVE_URL,
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
        timeout_s=timeout_s,
        params=_brave_params(args),
    )
    web = _obj(body).get("web")
    results = _dicts((web or {}).get("results", []) if isinstance(web, dict) else [])
    lines = [
        f"{r.get('title', '')}\n{r.get('url', '')}\n{(r.get('description') or '')[:_SNIPPET]}"
        for r in results
    ]
    return ToolResult(ok=True, output=_truncate("\n\n".join(lines) or "(no results)"))


# ── Firecrawl `formats` ───────────────────────────────────────────────────────────────────────
# `formats` was hardcoded to ["markdown"], which discards exactly what a structure-reading
# consumer needs — JSON-LD blocks, <img> src/alt, meta/og tags, <link rel=stylesheet>, hreflang.
# Reported by web-ecommerce-factory (2026-08-16) from a real site-intake crawler.
#
# The response field is the format's own name for nearly every format — but NOT all, and a
# `data[fmt]` lookup silently returns nothing for the exceptions. Verified against the live docs
# 2026-08-16 (docs.firecrawl.dev /api-reference/endpoint/scrape + /features/scrape):
_FC_RESULT_FIELD: dict[str, str] = {"question": "answer"}

# ⚠ There is deliberately NO allowlist of valid formats. Firecrawl shipped 16 at the time of
# writing and adds more; a frozen set here would reject a brand-new format and force the exact
# local fork this module exists to prevent. Unknown names are passed through and read back by
# name — the API is the authority on what is valid, not this file.


def _fc_format_names(formats: list[Any]) -> list[str]:
    """The response-field name for each requested format.

    A format is a plain string (``"rawHtml"``) or an object carrying options
    (``{"type": "json", "schema": {...}}``) — both are live API shapes, and rejecting the
    object form would block `json`, `question`, and `screenshot`-with-options outright.
    """
    names = []
    for f in formats:
        raw = f.get("type") if isinstance(f, dict) else f
        if isinstance(raw, str) and raw:
            names.append(_FC_RESULT_FIELD.get(raw, raw))
    return names


def _fc_payload_formats(args: dict[str, Any]) -> list[Any]:
    """Caller's `formats`, defaulting to ``["markdown"]`` — the pre-existing behaviour, so no
    existing caller changes. A bare string is accepted and wrapped: `formats="rawHtml"` is the
    obvious thing to try, and JSON-encoding it as-is makes Firecrawl 400 on a list of letters."""
    raw = args.get("formats") or ["markdown"]
    return [raw] if isinstance(raw, str) else list(raw)


def _fc_render(data: Any, formats: list[Any]) -> str:
    """Join the requested fields out of ``data``.

    Only `markdown`/`html`/`rawHtml` are strings; `links`/`images` are arrays and
    `json`/`branding`/`product` are objects, so non-strings are JSON-encoded rather than
    stringified into Python `repr` (which is not machine-readable on the other side).
    Multiple formats are labelled — unlabelled concatenation is unparseable by the consumer.
    """
    if not isinstance(data, dict):
        return ""
    names = _fc_format_names(formats)
    parts = []
    for name in names:
        val = data.get(name)
        if val in (None, "", [], {}):
            continue
        text = val if isinstance(val, str) else json.dumps(val, ensure_ascii=False)
        parts.append(text if len(names) == 1 else f"## {name}\n{text}")
    return "\n\n".join(parts)


def _firecrawl_scrape(args: dict[str, Any], client: httpx.Client, timeout_s: float) -> ToolResult:
    key = _need("FIRECRAWL_API_KEY")
    formats = _fc_payload_formats(args)
    payload: dict[str, Any] = {"url": str(args["url"]), "formats": formats}
    if args.get("actions"):
        payload["actions"] = args["actions"]
    body = _fetch(
        client,
        "POST",
        f"{_FC_BASE}/scrape",
        headers={"Authorization": f"Bearer {key}"},
        timeout_s=timeout_s,
        json_body=payload,
    )
    out = _fc_render(_obj(body).get("data"), formats)
    return ToolResult(ok=True, output=_truncate(out or "(empty)"))


def _firecrawl_crawl(args: dict[str, Any], client: httpx.Client, timeout_s: float) -> ToolResult:
    key = _need("FIRECRAWL_API_KEY")
    hdr = {"Authorization": f"Bearer {key}"}
    limit = min(max(int(args.get("limit", _CRAWL_MAX_PAGES)), 1), _CRAWL_MAX_PAGES)
    start = _fetch(
        client,
        "POST",
        f"{_FC_BASE}/crawl",
        headers=hdr,
        timeout_s=timeout_s,
        json_body={"url": str(args["url"]), "limit": limit},
    )
    job = _obj(start).get("id")
    if not job:
        return ToolResult(ok=False, output="", error="crawl: no job id returned")
    deadline = time.monotonic() + _CRAWL_MAX_WAIT
    while time.monotonic() < deadline:
        sd = _obj(
            _fetch(
                client,
                "GET",
                f"{_FC_BASE}/crawl/{job}",
                headers=hdr,
                timeout_s=timeout_s,
            )
        )
        state = sd.get("status")
        if state == "completed":
            pages = _dicts(sd.get("data", []))[:limit]
            out = "\n\n".join(
                f"{(p.get('metadata') or {}).get('sourceURL', '')}\n{(p.get('markdown') or '')[:_SNIPPET]}"
                for p in pages
            )
            return ToolResult(ok=True, output=_truncate(out or "(no pages)"))
        if state in _CRAWL_TERMINAL_FAIL:
            return ToolResult(ok=False, output="", error=f"crawl {state}")
        time.sleep(_CRAWL_POLL_INTERVAL)
    return ToolResult(
        ok=False, output="", error=f"crawl: not complete within {_CRAWL_MAX_WAIT}s"
    )


def _context7_docs(args: dict[str, Any], client: httpx.Client, timeout_s: float) -> ToolResult:
    key = _need("CONTEXT7_API_KEY")
    hdr = {"Authorization": f"Bearer {key}"}
    query = str(args.get("query", ""))
    results = _dicts(
        _obj(
            _fetch(
                client,
                "GET",
                f"{_C7_BASE}/libs/search",
                headers=hdr,
                timeout_s=timeout_s,
                params={"libraryName": str(args["library"]), "query": query},
            )
        ).get("results", [])
    )
    if not results:
        return ToolResult(
            ok=False,
            output="",
            error=f"docs_lookup: no library matching {args['library']!r}",
        )
    body = _fetch(
        client,
        "GET",
        f"{_C7_BASE}/context",
        headers=hdr,
        timeout_s=timeout_s,
        params={"libraryId": results[0].get("id"), "query": query, "type": "txt"},
    )
    return ToolResult(
        ok=True, output=_truncate(body.decode("utf-8", errors="replace") or "(no docs)")
    )


def execute_web_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    timeout_s: float = _DEFAULT_TIMEOUT,
    client: httpx.Client | None = None,
) -> ToolResult:
    """Dispatch one web tool. NEVER raises — every failure (unset key, HTTP status,
    timeout, bad JSON, non-dict response/args) returns ``ToolResult(ok=False, …)``.
    ``client`` is injectable (tests pass ``httpx.Client(transport=httpx.MockTransport(...))``);
    when omitted a short-lived client is created and closed."""
    owns_client = client is None
    cli = client if client is not None else httpx.Client(timeout=timeout_s)
    try:
        if name == "web_search":
            return _exa_search(arguments, cli, timeout_s)
        if name == "web_search_brave":
            return _brave_search(arguments, cli, timeout_s)
        if name == "web_scrape":
            return _firecrawl_scrape(arguments, cli, timeout_s)
        if name == "web_crawl":
            return _firecrawl_crawl(arguments, cli, timeout_s)
        if name == "docs_lookup":
            return _context7_docs(arguments, cli, timeout_s)
        return ToolResult(ok=False, output="", error=f"unknown web tool {name!r}")
    except _MissingKeyError as exc:
        return ToolResult(ok=False, output="", error=f"{exc.args[0]} not set")
    except (httpx.HTTPError, _HttpError) as exc:  # status/timeout/connect/transport
        return ToolResult(ok=False, output="", error=f"http error: {exc}")
    except (
        KeyError,
        ValueError,
        TypeError,
        AttributeError,
        json.JSONDecodeError,
    ) as exc:
        # AttributeError: a non-dict arguments or response element subscripted/.get()'d
        return ToolResult(ok=False, output="", error=f"bad response/args: {exc}")
    except Exception as exc:  # noqa: BLE001 — MUST be total: an escape would unwind
        # a tool loop and lose earlier turns' tool_calls provenance (e.g.
        # httpx.InvalidURL / httpx.CookieConflict are NOT httpx.HTTPError subclasses)
        return ToolResult(ok=False, output="", error=f"unexpected error: {exc}")
    finally:
        if owns_client:
            try:
                cli.close()
            except Exception:  # noqa: BLE001 — cleanup MUST be total: a raising close()
                pass  # would replace the returned ToolResult with an exception (not "never raises")


# --- async structured executors (injected config, never-raise, cost telemetry) --------------------


async def _a_fetch(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict[str, str],
    timeout_s: float,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> bytes:
    """Async twin of :func:`_fetch` — same streaming byte cap, same non-2xx → ``_HttpError``
    (the message carries only the status code, never the key/headers)."""
    async with client.stream(
        method, url, headers=headers, json=json_body, params=params, timeout=timeout_s
    ) as resp:
        buf = bytearray()
        async for chunk in resp.aiter_bytes():
            buf.extend(chunk)
            if len(buf) > _MAX_RESP_BYTES:
                raise ValueError(f"response exceeds {_MAX_RESP_BYTES} bytes")
        if resp.status_code >= 400:
            raise _HttpError(f"http {resp.status_code}")
        return bytes(buf)


def _leg_error(exc: Exception) -> LegResult:
    """Map any executor exception to a never-raise ``LegResult`` (mirrors ``execute_web_tool``'s
    exception taxonomy so the async surface degrades identically)."""
    if isinstance(exc, (httpx.HTTPError, _HttpError)):
        return LegResult(ok=False, rows=[], error=f"http error: {exc}")
    if isinstance(
        exc, (KeyError, ValueError, TypeError, AttributeError, json.JSONDecodeError)
    ):
        return LegResult(ok=False, rows=[], error=f"bad response/args: {exc}")
    return LegResult(ok=False, rows=[], error=f"unexpected error: {exc}")


async def a_exa_search(
    args: dict[str, Any], *, config: WebToolsConfig, client: httpx.AsyncClient
) -> LegResult:
    """Async Exa search → structured rows + Exa ``costDollars`` telemetry. NEVER raises; an
    unset key returns ``ok=False`` with **no network call** (the security invariant)."""
    if not config.exa_api_key:
        return LegResult(ok=False, rows=[], error="EXA_API_KEY not set")
    try:
        body = await _a_fetch(
            client,
            "POST",
            _EXA_URL,
            headers={"x-api-key": config.exa_api_key},
            timeout_s=config.timeout_s,
            json_body=_exa_body(args),
        )
        rows, cost = _parse_exa(body, text_budget=config.text_budget)
        if cost is None:  # costDollars absent → the configured per-call estimate (0 if unset)
            cost = config.exa_search_price_usd + Decimal(len(rows)) * config.exa_page_price_usd
        return LegResult(ok=True, rows=rows, cost_usd=cost)
    except Exception as exc:  # noqa: BLE001 — total: every failure maps to a LegResult
        return _leg_error(exc)


async def a_brave_search(
    args: dict[str, Any], *, config: WebToolsConfig, client: httpx.AsyncClient
) -> LegResult:
    """Async Brave search → structured rows (Brave is freemium — ``cost_usd`` stays 0). NEVER
    raises; an unset key returns ``ok=False`` with **no network call**."""
    if not config.brave_api_key:
        return LegResult(ok=False, rows=[], error="BRAVE_API_KEY not set")
    try:
        body = await _a_fetch(
            client,
            "GET",
            _BRAVE_URL,
            headers={
                "X-Subscription-Token": config.brave_api_key,
                "Accept": "application/json",
            },
            timeout_s=config.timeout_s,
            params=_brave_params(args),
        )
        return LegResult(ok=True, rows=_parse_brave(body, text_budget=config.text_budget))
    except Exception as exc:  # noqa: BLE001 — total
        return _leg_error(exc)


# --- Firecrawl geo-targeted SEARCH (market→ISO, refuse-on-unmapped) --------------------------------
#
# The market-scoping primitive the sync surface lacks. Firecrawl v2 /search combines search + a
# per-result scrape; `country` DEFAULTS TO US when omitted, so an unmappable market must REFUSE (a
# silent US search presented as the customer's market is the footgun this closes) — never a guess.

#: Market name → ISO 3166-1 alpha-2 for Firecrawl's ``country``. Deliberately small + static; an
#: unknown OR ambiguous name makes the leg REFUSE (see :func:`market_to_iso`). Extend as needed.
_MARKET_ISO: dict[str, str] = {
    "turkey": "TR", "türkiye": "TR", "turkiye": "TR",
    "united states": "US", "usa": "US", "us": "US", "united states of america": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB", "england": "GB",
    "germany": "DE", "deutschland": "DE", "france": "FR",
    "spain": "ES", "españa": "ES", "italy": "IT", "italia": "IT",
    "netherlands": "NL", "belgium": "BE", "poland": "PL", "polska": "PL",
    "sweden": "SE", "norway": "NO", "denmark": "DK", "finland": "FI",
    "ireland": "IE", "portugal": "PT", "austria": "AT", "switzerland": "CH",
    "greece": "GR", "czechia": "CZ", "czech republic": "CZ", "romania": "RO",
    "canada": "CA", "australia": "AU", "new zealand": "NZ",
    "japan": "JP", "south korea": "KR", "china": "CN",
    # qualified forms (incl. the Factbook "Korea, South" comma-ordering, normalised to "korea south")
    # resolve to the CORRECT country via the whole-string branch, BEFORE the directional-ambiguity guard.
    "korea south": "KR", "north korea": "KP", "korea north": "KP",
    "northern ireland": "GB", "ireland northern": "GB",
    "india": "IN", "singapore": "SG", "hong kong": "HK", "taiwan": "TW",
    "brazil": "BR", "brasil": "BR", "mexico": "MX", "méxico": "MX",
    "argentina": "AR", "chile": "CL", "colombia": "CO",
    "united arab emirates": "AE", "uae": "AE", "saudi arabia": "SA",
    "israel": "IL", "south africa": "ZA", "egypt": "EG", "nigeria": "NG", "kenya": "KE",
}
_MARKET_ISO_NORMALISED: dict[str, str] = {}
#: A bare directional qualifier in a comma-part makes the combined market ambiguous — "Ireland, Northern"
#: (GB) is NOT Ireland (IE), "Korea, North" is not South Korea. Refuse rather than resolve to the base
#: country, the same wrong-country footgun the refuse-on-ambiguous design exists to prevent.
_DIRECTIONS = frozenset(
    {"north", "south", "east", "west", "northern", "southern", "eastern", "western"}
)


def _normalise(text: str) -> str:
    """Casefold + NFKC-normalise, keep only alnum/whitespace (whitespace is load-bearing for
    multi-word keys). Strips the Turkish dotted-İ combining mark so ``TÜRKİYE`` matches ``türkiye``."""
    folded = unicodedata.normalize("NFKC", text or "").casefold()
    return "".join(ch for ch in folded if ch.isalnum() or ch.isspace()).strip()


def market_to_iso(market: str | None) -> str | None:
    """The ISO alpha-2 for a free-text market name, or ``None`` when unknown OR ambiguous (BOTH are
    refusals by design). ``'Istanbul, Turkey'`` → ``TR`` (a city-first single market resolves), but a
    LIST like ``'Germany, France'`` → ``None`` (the parts disagree — refusing beats a confidently
    wrong-country billed search). ``None`` means *do not run a geo search*, never *default to US*."""
    if not market:
        return None
    if not _MARKET_ISO_NORMALISED:
        _MARKET_ISO_NORMALISED.update({_normalise(k): v for k, v in _MARKET_ISO.items()})
    whole = _normalise(market)
    if whole in _MARKET_ISO_NORMALISED:
        return _MARKET_ISO_NORMALISED[whole]
    parts = [_normalise(p) for p in market.split(",")]
    if any(p in _DIRECTIONS for p in parts):
        return None  # a directional qualifier flips the country → ambiguous, refuse
    found = {_MARKET_ISO_NORMALISED[p] for p in parts if p and p in _MARKET_ISO_NORMALISED}
    return found.pop() if len(found) == 1 else None


def _int(value: Any) -> int:
    """A tolerant int — a malformed/absent figure reads as 0 (never a raise)."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _firecrawl_search_body(args: dict[str, Any], iso: str, market: str) -> dict[str, Any]:
    """The Firecrawl v2 /search request JSON. ``scrapeOptions.formats`` is the v2 ARRAY-OF-OBJECTS
    shape; ``country`` is REQUIRED (resolved, never defaulted); ``proxy`` defaults to search-time
    ``basic``. ``includeDomains``/``excludeDomains`` are mutually exclusive (caller-guarded upstream)."""
    limit = min(max(int(args.get("num_results", 5)), 1), 20)
    body: dict[str, Any] = {
        "query": str(args["query"]),
        "limit": limit,
        "location": market,
        "country": iso,
        "scrapeOptions": {
            "formats": [{"type": "markdown"}],
            "proxy": str(args.get("proxy") or "basic"),  # `or`: a None value falls back, not "None"
            "parsers": [],
        },
    }
    if "maxAge" in args:
        body["maxAge"] = args["maxAge"]
    inc, exc = args.get("includeDomains"), args.get("excludeDomains")
    if inc:
        body["includeDomains"] = list(inc)
    elif exc:
        body["excludeDomains"] = list(exc)
    return body


def _parse_firecrawl_search(
    obj: dict[str, Any], *, text_budget: int
) -> tuple[list[SearchRow], int]:
    """Structured rows + ``creditsUsed``. v2 /search returns ``data`` as an OBJECT
    (``{"web": [...], ...}``); a bare list is tolerated so a rolled-back shape degrades not empties."""
    payload = obj.get("data")
    hits = _dicts(payload.get("web", [])) if isinstance(payload, dict) else _dicts(payload)
    rows = [
        SearchRow(
            title=str(r.get("title") or ""),
            url=str(r.get("url") or ""),
            text=(r.get("markdown") or r.get("description") or "")[:text_budget],
            extra={"source": "firecrawl"},
        )
        for r in hits
    ]
    return rows, _int(obj.get("creditsUsed"))


async def a_firecrawl_search(
    args: dict[str, Any], *, config: WebToolsConfig, client: httpx.AsyncClient
) -> LegResult:
    """Async geo-targeted Firecrawl search → structured rows + ``creditsUsed`` telemetry (raw
    credits on ``LegResult.credits``; the credit→USD conversion stays the CONSUMER's). NEVER raises.
    REFUSES (``ok=False``, **no network call**) when: the key is unset, ``market`` is not a string,
    ``market`` is not geo-mappable (never a silent US search), or both domain filters are supplied."""
    if not isinstance(args, dict):
        return LegResult(ok=False, rows=[], error=f"args must be a dict, got {type(args).__name__}")
    if not config.firecrawl_api_key:
        return LegResult(ok=False, rows=[], error="FIRECRAWL_API_KEY not set")
    market = args.get("market")
    if not isinstance(market, str):
        return LegResult(
            ok=False, rows=[], error=f"market must be a string, got {type(market).__name__}"
        )
    iso = market_to_iso(market)
    if not iso:
        return LegResult(
            ok=False,
            rows=[],
            error=f"market {market!r} is not geo-mappable; refusing rather than running a "
            "US-default search (Firecrawl defaults country to US)",
        )
    if args.get("includeDomains") and args.get("excludeDomains"):
        return LegResult(
            ok=False, rows=[], error="includeDomains and excludeDomains are mutually exclusive"
        )
    try:
        body = await _a_fetch(
            client,
            "POST",
            f"{_FC_BASE}/search",
            headers={"Authorization": f"Bearer {config.firecrawl_api_key}"},
            timeout_s=config.timeout_s,
            json_body=_firecrawl_search_body(args, iso, market),
        )
        rows, credits = _parse_firecrawl_search(_obj(body), text_budget=config.text_budget)
        return LegResult(ok=True, rows=rows, credits=credits)
    except Exception as exc:  # noqa: BLE001 — total
        return _leg_error(exc)


async def a_firecrawl_scrape(
    args: dict[str, Any], *, config: WebToolsConfig, client: httpx.AsyncClient
) -> LegResult:
    """Async single-page Firecrawl scrape → one structured markdown row. NEVER raises; an unset key
    returns ``ok=False`` with **no network call**. Firecrawl /scrape reports no ``creditsUsed`` — so
    ``credits`` stays 0 (the consumer prices a scrape at its own worst-case estimate)."""
    if not config.firecrawl_api_key:
        return LegResult(ok=False, rows=[], error="FIRECRAWL_API_KEY not set")
    try:
        formats = _fc_payload_formats(args)
        payload: dict[str, Any] = {"url": str(args["url"]), "formats": formats}
        if args.get("actions"):
            payload["actions"] = args["actions"]
        body = await _a_fetch(
            client,
            "POST",
            f"{_FC_BASE}/scrape",
            headers={"Authorization": f"Bearer {config.firecrawl_api_key}"},
            timeout_s=config.timeout_s,
            json_body=payload,
        )
        # Shares `_fc_payload_formats`/`_fc_render` with the sync twin ON PURPOSE: these two
        # functions drifted apart once already, and fixing `formats` in only one of them would
        # have handed the async callers the same bug the report was about.
        text = _fc_render(_obj(body).get("data"), formats)
        rows = (
            [
                SearchRow(
                    title="",
                    url=str(args.get("url", "")),
                    text=text[: config.text_budget],
                    extra={"source": "firecrawl_scrape"},
                )
            ]
            if text
            else []
        )
        return LegResult(ok=True, rows=rows, credits=0)
    except Exception as exc:  # noqa: BLE001 — total
        return _leg_error(exc)


_STR = {"type": "string"}
_INT = {"type": "integer"}

WEB_TOOL_SCHEMAS: list[dict[str, Any]] = [
    _fn(
        "web_search",
        "Search the web (Exa) for current information; returns ranked title/url/snippet. "
        "Optional market-scoping: `category` (company/publication/news/people/…), `include_domains` "
        "(restrict to these hosts; `*.example.com` wildcard ok), `user_location` (ISO-2 country), "
        "`search_type` (auto/fast/instant at base rate; deep-lite/deep/deep-reasoning cost more).",
        {
            "query": _STR,
            "num_results": _INT,
            "category": _STR,
            "include_domains": {"type": "array", "items": {"type": "string"}},
            "user_location": _STR,
            "search_type": _STR,
        },
        ["query"],
    ),
    _fn(
        "web_search_brave",
        "Search the web (Brave) for current information; returns ranked title/url/snippet. "
        "An alternative engine to `web_search` (Exa) — enable either or both. Optional market-scoping: "
        "`country` (2-char country code), `search_lang` (content-language code).",
        {"query": _STR, "num_results": _INT, "country": _STR, "search_lang": _STR},
        ["query"],
    ),
    _fn(
        "web_scrape",
        "Fetch a URL (Firecrawl). Defaults to markdown. Set `formats` to keep structure that "
        "markdown discards — e.g. [\"rawHtml\"] for JSON-LD / meta+og tags / img src+alt / "
        "hreflang, [\"links\"], [\"images\"], or several at once. Optional `actions` "
        "(click/write/press/scroll/screenshot) drive browser interaction.",
        {
            "url": _STR,
            "formats": {"type": "array", "items": {"type": "string"}},
            "actions": {"type": "array"},
        },
        ["url"],
    ),
    _fn(
        "web_crawl",
        "Crawl a site (Firecrawl) up to a page limit; returns page urls + markdown.",
        {"url": _STR, "limit": _INT},
        ["url"],
    ),
    _fn(
        "docs_lookup",
        "Look up up-to-date library documentation (Context7) by library name + question.",
        {"library": _STR, "query": _STR},
        ["library", "query"],
    ),
]
