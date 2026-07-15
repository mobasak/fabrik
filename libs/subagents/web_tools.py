"""Web-research / browser tool executors for tool-looping subagents (opt-in).

Env-keyed HTTP tools that call the **hosted** Exa / Firecrawl / Context7 APIs. They
are **OFF by default** — a caller enables them per agent via ``AgentSpec.web_tools``
(they cost money + reach the internet). Each executor is a thin ``httpx`` call:

* the env key is read FIRST — unset ⇒ ``ToolResult(ok=False, "<X>_API_KEY not set")``
  and **no network call** is made;
* the response body is read with a **streaming byte cap** (:func:`_fetch`) so a
  giant body can't OOM the worker, and text output is ``_truncate``-bounded;
* it is **TOTAL** — every failure (HTTP status, timeout, bad JSON, non-dict shape,
  bad args) returns ``ToolResult(ok=False, …)``, never raises, so the loop feeds
  the error back to the model.

No new pip dependency: uses the vendored ``httpx``; no vendor SDKs. Keys travel in
HEADERS only (never a URL/query) so they cannot leak into output/error. Endpoints +
auth grounded live 2026-07-05 (see the module spec):

    Exa       POST https://api.exa.ai/search                    header  x-api-key: $EXA_API_KEY
    Brave     GET  https://api.search.brave.com/res/v1/web/search  header  X-Subscription-Token: $BRAVE_API_KEY
    Firecrawl POST https://api.firecrawl.dev/v2/{scrape,crawl}  header  Authorization: Bearer $FIRECRAWL_API_KEY
    Context7  GET  https://context7.com/api/v2/{libs/search,context}  header  Authorization: Bearer $CONTEXT7_API_KEY
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from .tools import ToolResult, _fn, _truncate

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
    headers: dict,
    timeout_s: float,
    json_body: dict | None = None,
    params: dict | None = None,
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


def _obj(body: bytes) -> dict:
    data = json.loads(body or b"{}")
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    return data


def _dicts(seq: Any) -> list[dict]:
    """The dict elements of a sequence (non-dicts skipped — defensive against an
    unexpected response shape, so a stray string can't crash an executor)."""
    return [x for x in seq if isinstance(x, dict)] if isinstance(seq, list) else []


def _exa_search(args: dict, client: httpx.Client, timeout_s: float) -> ToolResult:
    key = _need("EXA_API_KEY")
    n = int(args.get("num_results", 10))
    body = _fetch(
        client,
        "POST",
        _EXA_URL,
        headers={"x-api-key": key},
        timeout_s=timeout_s,
        json_body={
            "query": str(args["query"]),
            "numResults": min(max(n, 1), 100),
            "contents": {"text": True},
        },
    )
    lines = [
        f"{r.get('title', '')}\n{r.get('url', '')}\n{(r.get('text') or '')[:_SNIPPET]}"
        for r in _dicts(_obj(body).get("results", []))
    ]
    return ToolResult(ok=True, output=_truncate("\n\n".join(lines) or "(no results)"))


def _brave_search(args: dict, client: httpx.Client, timeout_s: float) -> ToolResult:
    # Brave Web Search API: GET …/web/search?q=&count=  header X-Subscription-Token.
    # Response: {"web": {"results": [{title, url, description}]}}. Count max 20.
    key = _need("BRAVE_API_KEY")
    n = int(args.get("num_results", 10))
    body = _fetch(
        client,
        "GET",
        _BRAVE_URL,
        headers={"X-Subscription-Token": key, "Accept": "application/json"},
        timeout_s=timeout_s,
        params={"q": str(args["query"]), "count": min(max(n, 1), 20)},
    )
    web = _obj(body).get("web")
    results = _dicts((web or {}).get("results", []) if isinstance(web, dict) else [])
    lines = [
        f"{r.get('title', '')}\n{r.get('url', '')}\n{(r.get('description') or '')[:_SNIPPET]}"
        for r in results
    ]
    return ToolResult(ok=True, output=_truncate("\n\n".join(lines) or "(no results)"))


def _firecrawl_scrape(args: dict, client: httpx.Client, timeout_s: float) -> ToolResult:
    key = _need("FIRECRAWL_API_KEY")
    payload: dict = {"url": str(args["url"]), "formats": ["markdown"]}
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
    data = _obj(body).get("data")
    md = data.get("markdown", "") if isinstance(data, dict) else ""
    return ToolResult(ok=True, output=_truncate(md or "(empty)"))


def _firecrawl_crawl(args: dict, client: httpx.Client, timeout_s: float) -> ToolResult:
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


def _context7_docs(args: dict, client: httpx.Client, timeout_s: float) -> ToolResult:
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
    arguments: dict,
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
        # the tool loop and lose earlier turns' tool_calls provenance (e.g.
        # httpx.InvalidURL / httpx.CookieConflict are NOT httpx.HTTPError subclasses)
        return ToolResult(ok=False, output="", error=f"unexpected error: {exc}")
    finally:
        if owns_client:
            try:
                cli.close()
            except Exception:  # noqa: BLE001 — cleanup MUST be total: a raising close()
                pass  # would replace the returned ToolResult with an exception (not "never raises")


_STR = {"type": "string"}
_INT = {"type": "integer"}

WEB_TOOL_SCHEMAS: list[dict] = [
    _fn(
        "web_search",
        "Search the web (Exa) for current information; returns ranked title/url/snippet.",
        {"query": _STR, "num_results": _INT},
        ["query"],
    ),
    _fn(
        "web_search_brave",
        "Search the web (Brave) for current information; returns ranked title/url/snippet. "
        "An alternative engine to `web_search` (Exa) — enable either or both.",
        {"query": _STR, "num_results": _INT},
        ["query"],
    ),
    _fn(
        "web_scrape",
        "Fetch a URL as markdown (Firecrawl). Optional `actions` (click/write/press/"
        "scroll/screenshot) drive browser interaction.",
        {"url": _STR, "actions": {"type": "array"}},
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
