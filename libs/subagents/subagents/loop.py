"""The per-subagent executor: run ONE subagent to completion.

Two modes, selected by ``tools_enabled``:

* **single-shot** — one OpenRouter call, return the model's prose. (research /
  docs / text tasks.)
* **tool-loop** — call the model with :data:`tools.TOOL_SCHEMAS`; while it returns
  ``tool_calls``, execute each in the agent's ``workdir`` via
  :func:`tools.execute_tool`, append the results, and call again — until the model
  stops or a cap (turns / cost / wall-clock) trips.

Vendors ai-consult's transport (``_transport.run`` → :class:`_transport.Result`);
the tool-execution turn is the enhancement this module adds. The transport is
injectable (``run_fn``) so the loop is testable offline with a fake model.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import httpx

from . import _transport
from .mcp_tools import McpProvider, build_mcp_provider
from .tools import TOOL_SCHEMAS, execute_tool
from .web_tools import WEB_TOOL_NAMES, WEB_TOOL_SCHEMAS, execute_web_tool

RunFn = Callable[..., _transport.Result]

LoopStatus = Literal["done", "capped", "error"]


@dataclass
class LoopOutcome:
    """One subagent run's outcome. ``transcript`` is the full message list
    (system/user/assistant/tool) for provenance; ``provider`` is the served
    upstream provider of the last transport call (None if no call succeeded)."""

    text: str
    status: LoopStatus
    turns: int
    cost_usd: float | None
    transcript: list[dict]
    error: str | None = None
    provider: str | None = None
    tool_calls: dict[str, int] = field(
        default_factory=dict
    )  # name → call count (provenance)
    out_tokens: int = 0  # summed completion (output) tokens across turns (value/report metric)


def _normalize_tool_calls(result: _transport.Result) -> list[dict]:
    """The result's tool calls as a list (never None), each guaranteed a non-empty,
    UNIQUE ``id``. Some providers stream a function name without an id; without one
    the resent assistant message + tool results would carry mismatched/None ids and
    the next request would 400. A missing id gets a random ``call_<hex>`` that is
    checked against ids already present, so a synthetic id can never collide with a
    real ordinal id (e.g. a provider's own ``call_1``)."""
    calls = result.tool_calls or []
    seen_ids = {tc.get("id") for tc in calls if isinstance(tc, dict) and tc.get("id")}
    out: list[dict] = []
    for tc in calls:
        if not isinstance(tc, dict):
            continue  # skip a malformed non-dict tool_call entry — never crash the loop
        norm = dict(tc)  # shallow copy — never mutate the transport's dict
        if not norm.get("id"):
            new_id = f"call_{uuid.uuid4().hex[:8]}"
            while new_id in seen_ids:
                new_id = f"call_{uuid.uuid4().hex[:8]}"
            norm["id"] = new_id
            seen_ids.add(new_id)
        out.append(norm)
    return out


def _execute_one_tool_call(
    tc: dict,
    workdir: str,
    *,
    tools_enabled: bool,
    allowed_commands: frozenset[str] | None,
    web_tools: frozenset[str] | None = None,
    web_client: httpx.Client | None = None,
    mcp_provider: McpProvider | None = None,
    counts: dict[str, int] | None = None,
    sandbox_on: bool = True,
) -> dict:
    """Run a single tool call and return the `role:"tool"` message to append.

    Bad/malformed calls never raise — the error is fed back to the model so it can
    correct course (execute_tool / execute_web_tool are total; we guard arg parsing
    here). Both tool families are gated **two ways** (not advertised in the schema
    AND rejected here) so a `tools_enabled=False` / not-in-`web_tools` name the model
    hallucinates is refused, not executed. ``tc`` is id-normalized by
    :func:`_normalize_tool_calls`. ``counts`` (name→int) is incremented ONLY for a
    tool that executed AND SUCCEEDED (`ok=True`) — a rejected/blocked/malformed call,
    or one the executor ran but returned an error for (e.g. an unset key, an HTTP
    error), is NOT counted — so the ledger records tools the agent actually used to
    effect, not mere attempts.
    """
    fn = tc.get("function") or {}
    name = str(fn.get("name", ""))
    raw_args = fn.get("arguments") or "{}"
    call_id = tc.get("id", "")
    enabled_web = web_tools or frozenset()

    def _executed() -> None:
        if counts is not None:
            counts[name] = counts.get(name, 0) + 1

    try:
        parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        content = f"error: could not parse tool arguments as JSON: {exc}"
    else:
        # a valid-JSON NON-object (list/str/int) would crash the executors' dict
        # indexing (TypeError) — feed the error back instead of sinking the run
        if not isinstance(parsed, dict):
            content = f"error: tool arguments must be a JSON object, got {type(parsed).__name__}"
        elif name in WEB_TOOL_NAMES:
            if name not in enabled_web:
                content = f"error: web tool {name!r} is not enabled for this agent"
            else:
                res = execute_web_tool(name, parsed, client=web_client)
                if res.ok:
                    content = res.output
                    _executed()  # count only a real, successful call
                else:
                    content = f"error: {res.error}"
        elif mcp_provider is not None and name in mcp_provider.tool_names():
            # MCP branch — MUST precede the `not tools_enabled` refusal: the research
            # config is tools_enabled=False + tools, so an MCP call would otherwise be
            # rejected as a "file/command tool" and never run. Gated two ways (advertised
            # + name-checked here); the provider's call() is TOTAL (never raises).
            res = mcp_provider.call(name, parsed)
            if res.ok:
                content = res.output
                _executed()  # count only a real, successful call
            else:
                content = f"error: {res.error}"
        elif not tools_enabled:
            # file/command tools disabled → refuse even if the model asks (matches
            # the web-tool gate; important now that tools_enabled=False + web_tools
            # is the recommended research config)
            content = f"error: file/command tool {name!r} is disabled for this agent"
        else:
            result = execute_tool(
                name, parsed, workdir=workdir, allowed_commands=allowed_commands,
                sandbox_on=sandbox_on,
            )
            if result.ok:
                content = result.output
                _executed()
            else:
                content = f"error: {result.error}"
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def run_loop(
    *,
    model: str,
    system: str,
    task: str,
    workdir: str,
    tools_enabled: bool,
    max_turns: int,
    max_cost_usd: float | None,
    wall_clock_s: float,
    allowed_commands: frozenset[str] | None = None,
    web_tools: frozenset[str] | None = None,
    web_client: httpx.Client | None = None,
    run_fn: RunFn | None = None,
    sandbox: bool = True,
    extra_body: dict | None = None,
    on_progress: Callable[[dict], None] | None = None,
    mcp_servers: frozenset[str] | None = None,
    mcp_config: dict | str | None = None,
    mcp_allow_unlisted: bool = False,
    mcp_provider: McpProvider | None = None,
) -> LoopOutcome:
    """Drive one subagent. ``run_fn`` defaults to the vendored OpenRouter transport
    (:func:`_transport.run`); inject a fake for offline tests.

    ``allowed_commands`` overrides the ``run_command`` binary allow-list (``None``
    = the tools default; ``frozenset()`` forbids all execution). ``web_tools`` names
    the web tools (web_search/web_scrape/web_crawl/docs_lookup) advertised + runnable
    for this agent — off unless named (they cost money + reach the internet).
    ``web_client`` is an injectable httpx client for the web tools (tests only).

    Caps: ``max_turns`` is HARD. ``wall_clock_s`` bounds each call
    (``hard_timeout_s=remaining``) and disables the transport's retry loop
    (``restart_max=0``), so overrun is limited to at most one internal
    empty-content bump (~2× on a reasoning-model turn) before the next
    between-turn cap — set ``max_turns`` as the firm backstop. ``max_cost_usd`` is
    BEST-EFFORT — it can only trip when the provider reports cost; against a
    cost-silent provider ``max_turns`` is the real spend backstop. NOTE: caps bound
    the transport turns, NOT tool execution — a single tool call (e.g. a
    ``web_crawl``, bounded by its max-wait plus one in-flight poll timeout) can run
    past ``wall_clock_s`` before the next between-turn cap; keep ``max_turns`` tight
    for tool-heavy agents.
    """
    call = run_fn if run_fn is not None else _transport.run
    _defaults = _transport.Liveness()

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": task})

    enabled_web = web_tools or frozenset()
    # ``extra_body`` is a per-agent OpenRouter passthrough (provider pin, reasoning,
    # max_tokens, …). The loop OWNS ``tools`` — a caller body must never advertise or
    # clobber the tool schemas. Flatten a nested OpenAI-SDK-style ``extra_body`` dict
    # HERE (the transport's ``_client._body`` would too, but AFTER we set tools — so a
    # nested ``extra_body.tools`` would otherwise survive). We do this BEFORE building the
    # MCP provider, so a malformed ``extra_body`` (a raise here) can't leak an open provider.
    merged: dict = dict(extra_body or {})
    # Flatten nested OpenAI-SDK-style ``extra_body`` to a FIXED POINT (bounded, so a
    # self-referential dict can't loop) — one level isn't enough: the transport flattens
    # one level too, so a leftover nested ``extra_body.tools`` would survive our guard and
    # get merged over ``tools`` downstream. After this, no ``extra_body`` key remains.
    for _ in range(16):
        inner = merged.get("extra_body")
        if not isinstance(inner, dict):
            break
        merged.pop("extra_body")
        merged.update(inner)

    # MCP provider: injected (a trusted caller / tests — bypasses the allowlist, like
    # ``run_fn``; the enforced public path is ``AgentSpec.mcp_servers`` → build_mcp_provider)
    # or built from the agent's mcp_servers/mcp_config. Built AFTER the flatten (so a body
    # error can't leak it) but BEFORE the first transport call, so an unlisted-server
    # PermissionError refuses at $0 cost; caught here so run_loop stays TOTAL. A None build
    # (SDK/Node absent, or all servers failed) ⇒ web_tools fallback. ``_finish`` closes it.
    mcp_prov = mcp_provider
    if mcp_prov is None and mcp_servers:
        try:
            mcp_prov = build_mcp_provider(
                mcp_servers, mcp_config, allow_unlisted=mcp_allow_unlisted
            )
        except PermissionError as exc:
            return LoopOutcome("", "error", 0, None, messages, error=str(exc))
    advertised = (
        (list(TOOL_SCHEMAS) if tools_enabled else [])
        + [s for s in WEB_TOOL_SCHEMAS if s["function"]["name"] in enabled_web]
        + (mcp_prov.tool_schemas() if mcp_prov is not None else [])
    )
    if advertised:
        merged["tools"] = advertised  # the loop OWNS tools — authoritative
    else:
        merged.pop("tools", None)     # single-shot / no web tools ⇒ advertise none
    body: dict | None = merged or None
    total_cost = 0.0
    cost_known = False
    total_out_tokens = 0
    provider: str | None = None
    last_text = ""
    tool_counts: dict[str, int] = {}
    start = time.monotonic()
    turns = 0

    def _finish(text: str, status: LoopStatus, error: str | None = None) -> LoopOutcome:
        if mcp_prov is not None:
            mcp_prov.close()  # tear down MCP sessions on EVERY exit path (done/capped/error)
        cost = total_cost if cost_known else None
        return LoopOutcome(
            text,
            status,
            turns,
            cost,
            messages,
            error=error,
            provider=provider,
            tool_calls=dict(tool_counts),
            out_tokens=total_out_tokens,
        )

    # The whole turn loop is wrapped so the MCP provider is ALWAYS torn down: `_finish`
    # closes it on every normal return, but an unguarded raise in the loop (e.g. a
    # malformed transport result in `_normalize_tool_calls`) would otherwise skip that and
    # orphan the provider's thread + `npx` child. close() is idempotent, so the finally is
    # a safe backstop even when `_finish` already closed.
    try:
        for _ in range(max_turns):
            remaining = wall_clock_s - (time.monotonic() - start)
            if remaining <= 0:
                return _finish(last_text, "capped")

            # Bound the single call to the REMAINING wall-clock budget AND disable the
            # transport's retry loop (restart_max=0): its per-attempt deadline RESETS,
            # so a retry would let one turn run up to ~2× the budget. wall_clock is then
            # near-hard (one internal empty-content bump can still overrun ~2× before
            # this loop's next between-turn cap — max_turns is the firm backstop). A
            # transient error ends the agent as status="error", and the partial-tolerant
            # batch lets the caller re-run just that agent.
            liveness = _transport.Liveness(
                hard_timeout_s=remaining,
                idle_timeout_s=min(_defaults.idle_timeout_s, remaining),
                connect_timeout_s=min(_defaults.connect_timeout_s, remaining),
                restart_max=0,
            )
            try:
                result = call(model, messages, body=body, liveness=liveness)
            except Exception as exc:  # noqa: BLE001 — transport must never crash the loop
                # a failure only after the budget is spent is a cap; a fast failure with
                # budget remaining is a genuine error
                if time.monotonic() - start >= wall_clock_s:
                    return _finish(last_text, "capped")
                return _finish(last_text, "error", error=str(exc))
            turns += 1
            provider = result.provider or provider

            if result.error:
                return _finish(last_text, "error", error=result.error)
            if result.cost_usd is not None:
                total_cost += result.cost_usd
                cost_known = True
            # sum output (completion) tokens across turns — a value/report metric; total,
            # never crashes on a missing/oddly-shaped usage dict.
            try:
                total_out_tokens += int((result.usage or {}).get("completion_tokens") or 0)
            except (TypeError, ValueError, AttributeError):
                pass
            if result.text:
                last_text = result.text

            tool_calls = _normalize_tool_calls(result)

            # Live progress for a babysitting caller: fire ONCE per completed transport turn
            # with the running cost/turns + the tools the model just requested (empty ⇒ it's
            # finishing). Guarded so a bad callback can never crash the agent loop.
            if on_progress is not None:
                try:
                    on_progress(
                        {
                            "turns": turns,
                            "cost_usd": total_cost if cost_known else None,
                            "provider": provider,
                            "tools": [
                                (tc.get("function") or {}).get("name", "") for tc in tool_calls
                            ],
                        }
                    )
                except Exception:  # noqa: BLE001 — observability must never break execution
                    pass

            if not tool_calls:
                messages.append({"role": "assistant", "content": result.text})
                return _finish(result.text, "done")

            messages.append(
                {"role": "assistant", "content": result.text, "tool_calls": tool_calls}
            )
            for tc in tool_calls:
                messages.append(
                    _execute_one_tool_call(
                        tc,
                        workdir,
                        tools_enabled=tools_enabled,
                        allowed_commands=allowed_commands,
                        web_tools=enabled_web,
                        web_client=web_client,
                        mcp_provider=mcp_prov,
                        counts=tool_counts,
                        sandbox_on=sandbox,
                    )
                )

            if max_cost_usd is not None and total_cost > max_cost_usd:
                return _finish(last_text, "capped")

        return _finish(last_text, "capped")
    finally:
        if mcp_prov is not None:
            mcp_prov.close()


__all__ = ["run_loop", "LoopOutcome", "LoopStatus", "RunFn"]
