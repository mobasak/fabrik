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
import os
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import httpx

from . import _transport
from ._client import ContentStallError
from .mcp_tools import McpProvider, build_mcp_provider
from .select import _MAX_POOL_PRICE_PER_MTOK, provider_max_price
from .tools import TOOL_SCHEMAS, execute_tool
from .web_tools import WEB_TOOL_NAMES, WEB_TOOL_SCHEMAS, execute_web_tool

RunFn = Callable[..., _transport.Result]


def _apply_max_price(merged: dict, model: str) -> None:
    """U1 — merge the model's `provider.max_price` (same-price ceiling) into the outgoing body,
    IN PLACE, unless the caller already set one. Writes a NEW provider dict (never mutates the
    caller's nested `provider` object — `merged` is only a shallow copy of `extra_body`). NEVER
    adds `provider.sort` (it would disable OR's health-aware default routing). Fail-open: an
    unpriced model leaves the body untouched."""
    mp = provider_max_price(model)
    if mp is None:
        return
    # BUGFIX (utilize-all reachability): cap at the POLICY (≤$1.5/Mtok output) with headroom over the
    # model's rate — NOT the model's EXACT listed price. A provider serves a model at-or-slightly-ABOVE
    # its canonical rate (provider variance), and the vendored price can be stale-low (e.g. m2.5 vendored
    # $0.48 vs live $0.90) — so the exact price as a HARD ceiling makes OpenRouter reject EVERY provider
    # ("No endpoints found that satisfy the max price"), leaving the model UNCALLABLE (proven: v4-pro /
    # m2.5 / v3.2 all 200 without the cap, 404 with it). 3× headroom tolerates staleness + variance; the
    # policy caps gross overpay. OR still routes cheapest-first — this only blocks a >policy fallback.
    price = mp.get("completion")
    if isinstance(price, (int, float)):
        mp = {"completion": min(price * 3.0, _MAX_POOL_PRICE_PER_MTOK)}
    prov = merged.get("provider")
    if prov is not None and not isinstance(prov, dict):
        return  # malformed caller `provider` (non-dict) — leave it AS-IS (never silently discard the
        # caller's value); OR will reject a malformed provider, which is the caller's bug to see.
    prov = dict(prov) if isinstance(prov, dict) else {}
    if "max_price" in prov:  # caller-set ceiling / opt-out wins
        return
    prov["max_price"] = mp
    merged["provider"] = prov


def _apply_latency_prefs(merged: dict) -> None:
    """L2 (plan-2 stall-resilience) — opt-in, env-driven provider LATENCY preferences merged into the
    outgoing body IN PLACE. ``SUBAGENT_PREFERRED_MAX_LATENCY_S`` → ``provider.preferred_max_latency`` and
    ``SUBAGENT_PREFERRED_MIN_THROUGHPUT`` → ``provider.preferred_min_throughput`` — each added ONLY when its
    knob is > 0 (default 0 = OFF, so no fleet-wide routing change ships unopted). Per OpenRouter these
    DEPRIORITIZE slow/low-throughput endpoints (never exclude, never prevent execution) — the SAFE analog
    to ``provider.sort``, which this NEVER adds (sort would disable OR's health-aware default routing).
    Caller-override-safe (a caller-set pref wins); a malformed non-dict caller ``provider`` is left AS-IS."""
    max_latency = _env_float("SUBAGENT_PREFERRED_MAX_LATENCY_S", 0.0)
    min_throughput = _env_float("SUBAGENT_PREFERRED_MIN_THROUGHPUT", 0.0)
    if max_latency <= 0 and min_throughput <= 0:
        return  # opt-in: neither knob set → body untouched (backward-compatible default)
    prov = merged.get("provider")
    if prov is not None and not isinstance(prov, dict):
        return  # malformed caller `provider` (non-dict) — leave AS-IS (mirror _apply_max_price)
    prov = dict(prov) if isinstance(prov, dict) else {}
    if max_latency > 0 and "preferred_max_latency" not in prov:  # caller-set pref wins
        prov["preferred_max_latency"] = max_latency
    if min_throughput > 0 and "preferred_min_throughput" not in prov:
        prov["preferred_min_throughput"] = min_throughput
    merged["provider"] = prov


def _with_ignore(body: dict | None, excluded: list[str]) -> dict | None:
    """A COPY of ``body`` with ``provider.ignore`` extended to skip the stalled ``excluded`` providers
    (merged with any caller-supplied ignore). Never mutates the caller's body / provider dict. This is
    how U2 tells OpenRouter's health-aware routing to route AROUND a provider that content-stalled."""
    merged = dict(body or {})
    prov = merged.get("provider")
    prov = dict(prov) if isinstance(prov, dict) else {}
    existing = prov.get("ignore")
    existing = list(existing) if isinstance(existing, list) else []
    prov["ignore"] = existing + [p for p in excluded if p not in existing]
    merged["provider"] = prov
    return merged or None


def _env_int(name: str, default: int) -> int:
    """A non-negative int env knob; any missing/garbage/negative value → ``default`` (fail-safe)."""
    try:
        v = int(os.environ[name])
    except (KeyError, ValueError):
        return default
    return v if v >= 0 else default


def _env_float(name: str, default: float) -> float:
    """A non-negative float env knob; missing/garbage/negative → ``default`` (fail-safe)."""
    try:
        v = float(os.environ[name])
    except (KeyError, ValueError):
        return default
    return v if v >= 0 else default


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
    out_tokens: int = (
        0  # summed completion (output) tokens across turns (value/report metric)
    )


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
                name,
                parsed,
                workdir=workdir,
                allowed_commands=allowed_commands,
                sandbox_on=sandbox_on,
            )
            if result.ok:
                content = result.output
                _executed()
            else:
                content = f"error: {result.error}"
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _partial_fallback(base: str, exc: object) -> str:
    """``base`` when it has content, else the transport exception's streamed ``.partial`` text.

    The client's ``ConsultError`` family (``HardTimeoutError``/``ContentStallError``/…) carries the text
    streamed BEFORE the timeout/failure. On a cap/error we surface it ONLY to fill an empty ``base`` — so
    a worker whose one call ran past ``wall_clock_s`` mid-stream returns its partial output instead of ""
    ("capped, no output"), WITHOUT ever replacing a completed prior turn's ``base`` (multi-turn-safe: a
    late-turn partial never clobbers an earlier turn's real answer). Fully defensive — this runs inside
    the loop's "never crash" handler, so a non-str/absent ``.partial`` (an exotic caller exception caught
    by the blanket ``except``) yields "" rather than a ``len()``/compare ``TypeError``."""
    if base:
        return base
    partial = getattr(exc, "partial", "")
    return partial if isinstance(partial, str) else ""


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
        merged.pop("tools", None)  # single-shot / no web tools ⇒ advertise none
    _apply_max_price(
        merged, model
    )  # U1: same-price ceiling (no `sort`), caller-override-safe
    _apply_latency_prefs(merged)  # L2: opt-in latency-aware routing (deprioritize-safe, no `sort`)
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
        stall_retry_max = _env_int("SUBAGENT_STALL_RETRY_MAX", 2)
        # L1 (plan-2): 20s (down from 60s) so a never-served/congested provider is detected fast, leaving
        # budget for reroutes within wall_clock. This does NOT clip a slow-but-healthy model: the window is
        # idle-since-last-OUTPUT and resets on ANY frame incl. streamed reasoning (see _client.py + the
        # test_reasoning_stream_is_not_a_stall / test_content_before_deadline_no_stall guards), so a model
        # streaming its chain-of-thought never false-stalls — only a provider silent for the full window
        # (congestion, the intended reroute target) trips. Raise the env var for a known heavy-reasoning
        # On-request model that can go silent past 20s before its first frame.
        first_token_timeout_s = _env_float("SUBAGENT_FIRST_TOKEN_TIMEOUT_S", 20.0)
        for _ in range(max_turns):
            # Each turn = one transport call with U2 stall-retry. On a CONTENT stall (the provider
            # heart-beats but streams no output — ContentStallError, which the client does NOT retry),
            # exclude the stalled provider (when known — OR sends it in chunk 0) via provider.ignore
            # and re-dispatch, so OR's health-aware default routing picks a DIFFERENT same-price
            # provider; a zero-chunk hang (provider unknown) retries blind. Bounded by BOTH
            # stall_retry_max AND wall_clock — each attempt's first-token deadline is short and
            # hard_timeout_s=remaining is recomputed, so the 2×-budget trap the old restart_max=0
            # avoided stays closed. restart_max stays 0 (the transport's own retry off) so THIS loop
            # owns retry and can update provider.ignore between attempts.
            attempt_body = body
            excluded: list[str] = []
            stalls = 0
            while True:
                remaining = wall_clock_s - (time.monotonic() - start)
                if remaining <= 0:
                    return _finish(last_text, "capped")
                liveness = _transport.Liveness(
                    hard_timeout_s=remaining,
                    idle_timeout_s=min(_defaults.idle_timeout_s, remaining),
                    connect_timeout_s=min(_defaults.connect_timeout_s, remaining),
                    first_token_timeout_s=(
                        min(first_token_timeout_s, remaining)
                        if first_token_timeout_s > 0
                        else 0.0
                    ),
                    restart_max=0,
                )
                try:
                    result = call(model, messages, body=attempt_body, liveness=liveness)
                    break
                except ContentStallError as exc:
                    if stalls >= stall_retry_max:
                        # kept content-stalling → cap (partial-tolerant; NOT scored — status !=
                        # "done" ⇒ record_run nulls the quality, see U3). Surface any text streamed
                        # before the stall (exc.partial) so a capped worker isn't silently empty.
                        return _finish(_partial_fallback(last_text, exc), "capped")
                    stalls += 1
                    if exc.provider and exc.provider not in excluded:
                        excluded.append(
                            exc.provider
                        )  # nameable → exclude it and re-route
                        attempt_body = _with_ignore(body, excluded)
                    # else: zero-chunk hang, provider unknown → blind retry (attempt_body unchanged)
                    continue
                except Exception as exc:  # noqa: BLE001 — transport must never crash the loop
                    # The transport's ConsultError carries `.partial` — the text streamed before the
                    # timeout/failure. Surface it (esp. for a single-shot finder whose ONE call ran
                    # past wall_clock mid-stream) so the worker returns its partial output, not "".
                    text = _partial_fallback(last_text, exc)
                    # a failure only after the budget is spent is a cap; a fast failure with budget
                    # remaining is a genuine error
                    if time.monotonic() - start >= wall_clock_s:
                        return _finish(text, "capped")
                    return _finish(text, "error", error=str(exc))
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
                total_out_tokens += int(
                    (result.usage or {}).get("completion_tokens") or 0
                )
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
                                (tc.get("function") or {}).get("name", "")
                                for tc in tool_calls
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
