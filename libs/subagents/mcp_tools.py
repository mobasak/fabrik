"""MCP-client research tools for tool-looping subagents (opt-in, OUTSIDE the sandbox).

Connect a pool agent to the fleet's Model Context Protocol servers (the same
``exa`` / ``brave-search`` / ``firecrawl`` / ``context7`` servers Claude Code uses) and
expose their tools to the OpenRouter tool-loop — the **MCP analogue of** ``web_tools``,
superseding per-provider HTTP wrappers, auto-syncing with the fleet's Claude Code MCP set.

⚠️ **Security (load-bearing).** MCP tool calls run in **THIS process, OUTSIDE the bubblewrap
``run_command`` sandbox** (they need the network + an ``npx`` subprocess). A filesystem /
shell / exec MCP server would hand an untrusted pool model unsandboxed I/O — a full bypass
of the sandbox this package ships. So this module enforces a **fail-safe allowlist**
(:data:`SAFE_RESEARCH_SERVERS`): a server NOT in that set is **refused** unless the caller
passes ``allow_unlisted=True`` (a conscious opt-out, like ``AgentSpec.sandbox=False``). The
gate validates the server **name** — the threat model is the untrusted **model** choosing
which advertised tools to call, NOT an untrusted ``mcp_config`` (that is the hub-provisioned
``/opt/fabrik/mcp.json``, trusted); a caller who binds a safe name to a dangerous ``command``
in the config has already trusted that config, exactly as with any tool wiring.

The ``mcp`` SDK **and** Node/``npx`` are **OPTIONAL / lazy-imported** (like ``psycopg`` in
``pg_ledger``): a host without them makes :func:`build_mcp_provider` return ``None`` and the
caller falls back to ``web_tools``. Keys come from the process env — an ``mcp_config`` ``env``
value like ``${EXA_API_KEY}`` is expanded from ``os.environ``, never inlined.

**Async→sync bridge.** The MCP SDK's stdio/http clients use ``anyio`` task groups whose
cancel scopes are bound to the task that entered them, so opening, calling, and closing a
session MUST all happen in the **same task**. :class:`McpProvider` therefore runs a
**dedicated thread with a persistent event loop** and a **single long-lived serve task**
that opens the sessions, services every ``call_tool`` from a queue, then closes them — all
in one task. ``call()`` / ``close()`` marshal work onto that task (thread-safe), so the
sync tool-loop never touches the loop directly. (An earlier one-loop /
``run_until_complete``-per-op design orphaned the ``npx`` subprocess — ``aclose`` raised
"exit cancel scope in a different task"; proven live against mcp 1.28.1.)

Grounded live 2026-07-07 against **mcp 1.28.1**:
    ``ClientSession`` / ``StdioServerParameters`` (``mcp``), ``stdio_client`` (``mcp.client.stdio``),
    ``streamablehttp_client`` (``mcp.client.streamable_http``); ``session.list_tools().tools`` →
    ``tool.name`` / ``tool.description`` / ``tool.inputSchema`` (**camelCase**, a JSON-Schema dict);
    ``session.call_tool(name, args)`` → ``CallToolResult.content`` [``TextContent(type=="text", text)``]
    / ``.isError``.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
import os
import re
import threading
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from typing import Any

from .tools import ToolResult, _truncate

logger = logging.getLogger(__name__)

# Read-only research servers safe to expose to an UNTRUSTED pool model (they reach the
# web only — no filesystem/shell/exec). Matches /opt/fabrik/mcp.json + the hub
# `using-subagents` rules pack. Anything else needs an explicit allow_unlisted=True.
SAFE_RESEARCH_SERVERS: frozenset[str] = frozenset(
    {"exa", "brave-search", "firecrawl", "context7"}
)

_FN_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")
_FN_NAME_MAX = 64  # OpenAI/OpenRouter function-name cap (grounded 2026-07-07)
_BUILD_TIMEOUT_S = (
    60.0  # bound session opening so a hung npx/connect can't hang the agent
)
_CALL_TIMEOUT_S = (
    120.0  # bound one MCP call so a hung server can't hang the agent forever
)
_CLOSE_TIMEOUT_S = 30.0  # bound session teardown

# a connector opens ALL sessions on the given stack and returns
# (name_map {fn_name -> (session, real_tool)}, schemas, usable_tool_count)
Connector = Callable[[AsyncExitStack], Awaitable[tuple[dict, list[dict], int]]]


def sanitize_fn_name(server: str, tool: str) -> str:
    """``{server}__{tool}`` cleaned to the OpenAI/OpenRouter function-name charset
    ``^[a-zA-Z0-9_-]{1,64}$`` (grounded live 2026-07-07: community.openai.com /
    portkey.ai — "a-z, A-Z, 0-9, underscores and dashes, max length 64"). Hyphens pass
    (so ``brave-search__web_search`` is unchanged); any other char → ``_``; truncated to 64."""
    return _FN_NAME_RE.sub("_", f"{server}__{tool}")[:_FN_NAME_MAX]


def load_mcp_config(mcp_config: dict | str) -> dict[str, dict]:
    """Return the ``{server_name: server_def}`` map.

    * a **path (str)** → the standard Claude Code file with a top-level ``mcpServers``
      wrapper (``/opt/fabrik/mcp.json``, **non-dot**); we read ``["mcpServers"]``.
    * a **dict** → the **bare, unwrapped** server map, returned as-is.

    Raises :class:`ValueError` on a non-object, or a path whose file lacks the
    ``mcpServers`` object (``OSError`` / :class:`json.JSONDecodeError` propagate to the caller)."""
    if isinstance(mcp_config, str):
        with open(mcp_config, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"mcp_config file {mcp_config!r} is not a JSON object")
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            raise ValueError(
                f"mcp_config file {mcp_config!r} lacks a 'mcpServers' object"
            )
        return servers
    if isinstance(mcp_config, dict):
        return mcp_config
    raise ValueError(
        f"mcp_config must be a path or dict, got {type(mcp_config).__name__}"
    )


def _resolve_env(env: Any) -> dict[str, str] | None:
    """Expand ``${VAR}`` / ``$VAR`` in an ``mcp_config`` ``env`` map from ``os.environ``
    (keys travel via env, never inlined). ``None``/empty ⇒ ``None`` (SDK default env). An
    UNSET variable is left as its literal ``${VAR}`` (expandvars' behavior) and warned about,
    so the later "server failed to connect" is traceable to a missing key, not a mystery."""
    if not isinstance(env, dict) or not env:
        return None
    out: dict[str, str] = {}
    for k, v in env.items():
        expanded = os.path.expandvars(str(v))
        if "${" in expanded or (
            expanded.startswith("$") and expanded[1:].isidentifier()
        ):
            logger.warning(
                "mcp env var %r appears unset (value %r unexpanded) — the server will "
                "likely fail auth; check the key is provisioned in the process env.",
                k,
                v,
            )
        out[str(k)] = expanded
    return out


def _extract_text(result: Any) -> str:
    """Concatenate the text of the text blocks in a ``CallToolResult.content``; a
    non-text block (image / embedded-resource) is **labelled**, not silently dropped.
    A structured-output tool MAY return only ``structuredContent`` (the text block is
    only a SHOULD in the spec) — fall back to the JSON of that so the model isn't handed
    an empty "(no content)" for a call that actually succeeded."""
    parts: list[str] = []
    content = getattr(result, "content", None)
    for block in (
        content if isinstance(content, list) else []
    ):  # non-list ⇒ no text blocks
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", "") or "")
        else:
            parts.append(
                f"[non-text {getattr(block, 'type', 'unknown')} block omitted]"
            )
    text = "\n".join(parts)
    if not text.strip():
        structured = getattr(result, "structuredContent", None)
        if structured:
            try:
                text = json.dumps(structured, default=str)
            except Exception:  # noqa: BLE001 — TOTAL: RecursionError/etc. must not escape
                pass  # _extract_text runs outside call()'s try; it must never raise
    return text


def _mcp_tool_schema(name: str, description: str, input_schema: Any) -> dict:
    """Wrap an MCP tool as an OpenRouter function schema. An MCP ``inputSchema`` IS a
    JSON Schema, so it is passed through **verbatim** as ``function.parameters`` —
    reprojecting via the module's flat ``_fn`` helper would drop root-level keywords
    (``$defs`` / ``$ref`` / ``anyOf`` / ``additionalProperties``) and force
    ``additionalProperties: false``, producing a dangling reference or a wrong contract
    for tools with a non-trivial schema (e.g. firecrawl scrape/extract). Only a proper
    **object**-typed schema (the MCP-spec shape) is passed through — that preserves the rich
    keywords — while a non-object / empty / non-dict schema falls back to a safe default.
    NOTE: a structurally-object schema that is itself invalid (a dangling ``$ref``, a bad
    keyword) is still forwarded verbatim and could make OpenRouter reject the tools array;
    validating arbitrary JSON Schema is out of scope (the trusted research servers emit
    valid schemas), so this guards the common non-object case, not every malformed schema."""
    params = (
        input_schema
        if isinstance(input_schema, dict) and input_schema.get("type") == "object"
        else {"type": "object", "properties": {}}
    )
    return {
        "type": "function",
        "function": {"name": name, "description": description, "parameters": params},
    }


class McpProvider:
    """Live MCP sessions for ONE agent, exposing their tools to the sync tool-loop.

    Runs a dedicated thread with a persistent event loop and a **single serve task** that
    owns the whole session lifecycle (open → service calls → close) so the ``anyio`` cancel
    scopes are always entered and exited in the same task. Every public method is **sync +
    TOTAL** (never raises into the loop)."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._thread_main, name="mcp-provider", daemon=True
        )
        self._req_q: asyncio.Queue | None = None  # created inside the serve task
        self._name_map: dict[
            str, tuple[Any, str]
        ] = {}  # fn_name -> (session, real_tool)
        self._schemas: list[dict] = []
        self._serve_future: concurrent.futures.Future | None = None
        self._started = False
        self._closed = False

    def _thread_main(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _start(self, connect: Connector) -> int:
        """Spin up the thread + serve task; block until every session is opened (or an
        error/`0 usable tools` is reported). Returns the usable-tool count (0 ⇒ the caller
        closes + falls back). Raises if the connector itself raised (caller turns into ``None``)."""
        self._thread.start()
        self._started = True
        build_fut: concurrent.futures.Future = concurrent.futures.Future()
        self._serve_future = asyncio.run_coroutine_threadsafe(
            self._serve(connect, build_fut), self._loop
        )
        # +10s over the in-task wait_for, so the serve task self-cancels a hung connect
        # (unwinding the stack cleanly) BEFORE this caller-side backstop fires.
        return build_fut.result(timeout=_BUILD_TIMEOUT_S + 10)

    async def _serve(
        self, connect: Connector, build_fut: concurrent.futures.Future
    ) -> None:
        """The one task that owns the sessions. Opens them, signals ``build_fut``, then
        services ``(session, tool, args, result_fut)`` requests until a ``None`` sentinel,
        then exits the stack — all in THIS task (anyio-safe)."""
        stack = AsyncExitStack()
        try:
            self._req_q = asyncio.Queue()
            try:
                # Bound the open IN-TASK: a hung connect (e.g. `initialize()` never
                # returns) is cancelled here, so the stack unwinds — reaping any partial
                # `npx` child — in THIS task, rather than orphaning it. (Exception, not
                # BaseException, to match build_mcp_provider's `except Exception`.)
                name_map, schemas, connected = await asyncio.wait_for(
                    connect(stack), timeout=_BUILD_TIMEOUT_S
                )
            except Exception as exc:  # noqa: BLE001 — surface build failure to _start
                build_fut.set_exception(exc)
                return
            self._name_map, self._schemas = name_map, schemas
            build_fut.set_result(connected)
            if connected == 0:
                return  # stack (any partial contexts) exits in the finally, same task
            while True:
                item = await self._req_q.get()
                if item is None:  # close sentinel
                    return
                session, tool, args, fut = item
                try:
                    # Bound the call IN-TASK so a hung server can't wedge the serve task
                    # (a caller-side timeout alone would leave it blocked, starving every
                    # later call). `except Exception` matches call()'s handler (TOTAL).
                    res = await asyncio.wait_for(
                        session.call_tool(tool, args), timeout=_CALL_TIMEOUT_S
                    )
                except Exception as exc:  # noqa: BLE001 — report to the caller's future
                    if not fut.done():
                        fut.set_exception(exc)
                else:
                    if not fut.done():
                        fut.set_result(res)
        except Exception as exc:  # noqa: BLE001 — a pre-build error unblocks _start at once.
            # (A true BaseException falls through to the `finally` below + propagates; _start
            # then times out on build_fut and build_mcp_provider's `except Exception` degrades
            # to None — a BaseException must NOT land in build_fut, which that catch would miss.)
            if not build_fut.done():
                build_fut.set_exception(exc)
        finally:
            # Bound the TEARDOWN too: only connect + call were time-bounded before, but the
            # stack unwind (`aclose`, which SIGTERMs + reaps `npx`) on the close/sentinel edge
            # was not — a server that hangs on shutdown would wedge the thread/loop. Bounding
            # it frees our thread/loop even if a pathological `npx` ignores the signal.
            try:
                await asyncio.wait_for(stack.aclose(), timeout=_CLOSE_TIMEOUT_S)
            except Exception:  # noqa: BLE001 — best-effort; a truly-hung child is abandoned
                pass

    def tool_schemas(self) -> list[dict]:
        """The advertised OpenRouter function schemas (a copy)."""
        return list(self._schemas)

    def tool_names(self) -> frozenset[str]:
        """The advertised (sanitized) function names — the loop's routing gate."""
        return frozenset(self._name_map)

    def call(self, fn_name: str, arguments: dict) -> ToolResult:
        """Proxy one model tool-call to its owning MCP server (marshalled onto the serve
        task). TOTAL — every failure returns ``ToolResult(ok=False, …)``."""
        if self._closed or self._req_q is None:
            return ToolResult(ok=False, output="", error="mcp provider is closed")
        entry = self._name_map.get(fn_name)
        if entry is None:
            return ToolResult(
                ok=False, output="", error=f"unknown mcp tool {fn_name!r}"
            )
        session, real_tool = entry
        fut: concurrent.futures.Future = concurrent.futures.Future()
        try:
            self._loop.call_soon_threadsafe(
                self._req_q.put_nowait, (session, real_tool, arguments, fut)
            )
            result = fut.result(
                timeout=_CALL_TIMEOUT_S + 10
            )  # in-task wait_for fires first
        except Exception as exc:  # noqa: BLE001 — TOTAL: an escape would unwind the loop
            return ToolResult(ok=False, output="", error=f"mcp call failed: {exc}")
        text = _extract_text(result)
        if getattr(result, "isError", False):
            return ToolResult(
                ok=False, output="", error=f"mcp tool error: {text[:500]}"
            )
        return ToolResult(ok=True, output=_truncate(text or "(no content)"))

    def close(self) -> None:
        """Tear down all sessions (via the serve task) + the loop/thread. Idempotent +
        best-effort — never masks the agent's real outcome."""
        if self._closed:
            return
        self._closed = True
        if not self._started:  # never spun up (build failed before _start)
            self._loop.close()
            return
        try:
            if (
                self._req_q is not None
            ):  # signal the serve task to exit → in-task aclose
                self._loop.call_soon_threadsafe(self._req_q.put_nowait, None)
            if self._serve_future is not None:
                self._serve_future.result(timeout=_CLOSE_TIMEOUT_S)
        except Exception:  # noqa: BLE001 — best-effort teardown
            pass
        finally:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._thread.join(timeout=5)
            except Exception:  # noqa: BLE001
                pass
            try:
                self._loop.close()
            except Exception:  # noqa: BLE001
                pass


async def _open_session(server_def: dict, stack: AsyncExitStack, sdk: dict) -> Any:
    """Open one MCP session on ``stack``. ``url``-shaped def → Streamable HTTP;
    ``command``-shaped def → stdio via ``npx``. Returns an initialized ``ClientSession``."""
    if "url" in server_def:
        transport = await stack.enter_async_context(
            sdk["streamablehttp_client"](server_def["url"])
        )
        read, write = transport[0], transport[1]  # (read, write[, get_session_id])
    else:
        params = sdk["StdioServerParameters"](
            command=server_def["command"],
            args=list(server_def.get("args", []) or []),
            env=_resolve_env(server_def.get("env")),
        )
        read, write = await stack.enter_async_context(sdk["stdio_client"](params))
    session = await stack.enter_async_context(sdk["ClientSession"](read, write))
    await session.initialize()
    return session


def build_mcp_provider(
    mcp_servers: frozenset[str] | None,
    mcp_config: dict | str | None,
    *,
    allow_unlisted: bool = False,
    _connect: Any = None,
) -> McpProvider | None:
    """Build a connected :class:`McpProvider`, or ``None`` (⇒ caller falls back to
    ``web_tools``) when: ``mcp_servers`` is empty; the ``mcp`` SDK is absent; ``mcp_config``
    is missing/unreadable; or **every** requested server fails to connect.

    **Fail-safe:** a server in ``mcp_servers`` but not in :data:`SAFE_RESEARCH_SERVERS`
    raises :class:`PermissionError` unless ``allow_unlisted=True`` — checked BEFORE any
    connect/import (and, since the caller builds this at loop start, before the first paid
    LLM turn), so a refused config wastes no money. ``_connect`` is a test hook
    ``async (name, server_def, stack) -> session`` that bypasses the real SDK."""
    if not mcp_servers:
        return None

    # fail-safe allowlist gate — BEFORE any connect / import (no money spent on refusal)
    for name in mcp_servers:
        if name not in SAFE_RESEARCH_SERVERS and not allow_unlisted:
            raise PermissionError(
                f"mcp server {name!r} is not in SAFE_RESEARCH_SERVERS "
                f"{sorted(SAFE_RESEARCH_SERVERS)}; pass mcp_allow_unlisted=True to enable it. "
                "Unlisted MCP servers run OUTSIDE the sandbox — a filesystem/shell/exec "
                "server would bypass containment for an untrusted pool model."
            )

    sdk: dict = {}
    if _connect is None:
        try:  # optional dependency — absent ⇒ web_tools fallback
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError:
            logger.warning(
                "mcp SDK not installed; MCP tools disabled (web_tools fallback)."
            )
            return None
        sdk = {
            "ClientSession": ClientSession,
            "StdioServerParameters": StdioServerParameters,
            "stdio_client": stdio_client,
            "streamablehttp_client": streamablehttp_client,
        }

    if mcp_config is None:
        logger.warning("mcp_servers set but mcp_config is None; MCP tools disabled.")
        return None
    try:
        config = load_mcp_config(mcp_config)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        logger.warning("mcp_config unreadable (%s); MCP tools disabled.", exc)
        return None

    async def _connect_all(stack: AsyncExitStack) -> tuple[dict, list[dict], int]:
        name_map: dict[str, tuple[Any, str]] = {}
        schemas: list[dict] = []
        for name in sorted(mcp_servers):
            server_def = config.get(name)
            if not isinstance(server_def, dict):
                logger.warning(
                    "mcp server %r not present in mcp_config; skipped.", name
                )
                continue
            try:
                if _connect is not None:
                    session = await _connect(name, server_def, stack)
                else:
                    session = await _open_session(server_def, stack, sdk)
                tools = (await session.list_tools()).tools
            except Exception as exc:  # noqa: BLE001 — one bad server is skipped, not fatal
                logger.warning(
                    "mcp server %r failed to connect (%s); skipped.", name, exc
                )
                continue
            for tool in tools:
                # one malformed tool must not take down the whole server (or every OTHER
                # server) — skip it, keep the rest.
                tool_name = getattr(tool, "name", None)
                if not isinstance(tool_name, str) or not tool_name:
                    logger.warning(
                        "mcp server %r advertised a tool with a bad name (%r); skipped.",
                        name,
                        tool_name,
                    )
                    continue
                try:
                    fn = sanitize_fn_name(name, tool_name)
                    if fn in name_map:  # sanitize collision — keep both, disambiguate
                        # reserve room for `_<suffix>` so the result STAYS within the 64-char
                        # cap even for a multi-digit suffix (a 2-digit suffix on a 62-char base
                        # would otherwise be 65 chars → OpenRouter 400 on the tools array).
                        suffix = 1
                        while True:
                            cand = (
                                f"{fn[: _FN_NAME_MAX - 1 - len(str(suffix))]}_{suffix}"
                            )
                            if cand not in name_map:
                                break
                            suffix += 1
                        fn = cand
                    # build the schema BEFORE mutating name_map so the (name→route) and
                    # (advertised schema) pair stays consistent even if a build ever raised.
                    schema = _mcp_tool_schema(
                        fn,
                        getattr(tool, "description", "") or "",
                        getattr(tool, "inputSchema", None),
                    )
                    name_map[fn] = (session, tool_name)
                    schemas.append(schema)
                except Exception as exc:  # noqa: BLE001 — skip a bad tool, not the server
                    logger.warning(
                        "mcp server %r tool %r skipped (%s).", name, tool_name, exc
                    )
                    continue
        # Return the count of USABLE TOOLS, not connected servers: a server that connects
        # but exposes zero valid tools contributes nothing, so build_mcp_provider closes the
        # (useless) provider and falls back to web_tools instead of holding an idle npx open.
        return name_map, schemas, len(name_map)

    provider = McpProvider()
    try:
        connected = provider._start(_connect_all)
    except Exception as exc:  # noqa: BLE001 — build must never raise into the loop
        logger.warning("mcp provider build failed (%s); MCP tools disabled.", exc)
        provider.close()
        return None
    if connected == 0:
        provider.close()  # cleans up any partially-entered stack context (in-task)
        return None
    return provider


__all__ = [
    "SAFE_RESEARCH_SERVERS",
    "McpProvider",
    "build_mcp_provider",
    "load_mcp_config",
    "sanitize_fn_name",
]
