"""The public surface: recruit and run N subagents in parallel.

:func:`run_agents` is the one entrypoint. It composes the other units into the
full containment model:

1. **partition** the specs by ``owned_paths`` (``workspace.disjoint``): agents
   whose globs could overlap share a group and run **serially** (never race on a
   file); disjoint groups run in **parallel** (bounded by ``max_concurrency``).
2. each agent gets its **own git worktree** (``workspace.create_worktree``);
3. the agent runs there via the tool-loop (``loop.run_loop``, injectable);
4. its **diff is captured** (``workspace.worktree_diff``) and **never applied** to
   the caller's repo — the caller reviews it;
5. a **post-hoc scope check** (``workspace.changed_paths`` + ``paths_in_scope`` —
   the authoritative git ``--name-status`` list, so renames/quoted/mode changes
   can't slip past) flips a ``done``/``capped`` result to ``out_of_scope`` if the
   agent touched a path it did not own;
6. every run is recorded to the **ledger**, and the worktree is torn down.

Partial-tolerant: one agent raising or erroring never sinks the batch — its slot
comes back ``status="error"`` while the others complete.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from . import sandbox, workspace
from ._dotenv import load_env
from .ledger import Ledger, agent_record
from .loop import LoopOutcome, run_loop
from .pg_ledger import record_agent_run
from .select import pick_models

logger = logging.getLogger(__name__)

AgentStatus = Literal["done", "capped", "error", "out_of_scope"]

# Task_types that MUST read the REPO to be truthful — a single-shot (tools_enabled=False) worker on
# one of these asserts about code it can't see and hallucinates: `review` (bugs in code), `docs`
# (docs-vs-code), `plan` (grounds every ref at path:line — see methodology("plan")). NOT gated:
# `research`/`spec` ground against the WEB (via `web_tools`, not repo files), and `code` GENERATES
# (a self-contained "write function X" needs no repo grounding) — those set their own tools/keys.
_GROUNDED_TASK_KINDS = frozenset({"review", "docs", "plan"})

# A tool-enabled (write) fanout is turn-hungry for cheap pool models that read one file per turn — the
# module's own cap-advice says such work needs ≈20+ turns; default to it when the caller didn't set one.
_WRITE_DEFAULT_TURNS = 20
# The verification task_types whose code can usually be INLINED → read_only single-shot (cheaper, never
# caps). In write-mode they're the turn-hungry trap that stranded /opt/trade-intelligence, so warn (never
# refuse — an exploration review that must DISCOVER files is a valid write-mode case).
_WRITE_STEER_TASK_TYPES = frozenset({"review", "docs", "research"})


def _outer_grace_s() -> float:
    """Grace added to ``wall_clock_s`` for the OUTER dispatch backstop (see :func:`_run_one`).

    ``loop.run_loop`` already bounds each call by ``wall_clock_s`` (``hard_timeout_s=remaining``)
    plus a 20s first-token stall timeout — but that bound is only as good as the verbatim-vendored
    ``_transport.py``/``_client.py`` honoring it. A provider that accepts the connection then never
    streams a first token has been observed to hang the transport FAR past ``wall_clock_s`` (AFCL
    2026-07-11: a 260s-budget pool review finder hung >10min, forcing an all-native review with zero
    flywheel rows — the exact "pool hangs at pick_models/dispatch" symptom). Since the transport is
    vendored (a root-cause fix goes to ``ai-consult`` UPSTREAM_FEEDBACK, not a local fork),
    :func:`_run_one` wraps the loop in an OUTER asyncio deadline = ``wall_clock_s`` + this grace so a
    hung dispatch is force-capped and the BATCH proceeds (the pool degrades to native) instead of
    hanging forever. Env ``SUBAGENT_OUTER_GRACE_S`` (default 30s); ``<= 0`` disables the backstop."""
    try:
        return float(os.getenv("SUBAGENT_OUTER_GRACE_S", "30"))
    except ValueError:
        return 30.0


def _worktree_max_age_s() -> float:
    """Age (s) past which a leftover ``.tmp/subagents/agent-*`` worktree is treated as an ORPHAN and
    swept at batch startup (see :func:`~subagents.workspace.sweep_stale_worktrees`). MUST exceed the
    longest ``wall_clock_s`` in use so a live concurrent batch's fresh worktree is never reclaimed;
    the 2h default dwarfs the 600s pool default. Env ``SUBAGENT_WORKTREE_MAX_AGE_S``."""
    try:
        return float(os.getenv("SUBAGENT_WORKTREE_MAX_AGE_S", "7200"))
    except ValueError:
        return 7200.0


def _settle_result(fut: asyncio.Future, value: Any) -> None:  # noqa: ANN401
    if not fut.done():
        fut.set_result(value)


def _settle_exc(fut: asyncio.Future, exc: BaseException) -> None:
    if not fut.done():
        fut.set_exception(exc)


async def _await_loop_with_backstop(
    call: Callable[[], LoopOutcome], deadline_s: float | None
) -> LoopOutcome:
    """Run ``call`` (the tool-loop — a blocking, network-bound call) in a DAEMON thread and await
    it, but never longer than ``deadline_s``: on the deadline raise :class:`TimeoutError` and ABANDON
    the thread.

    Why a hand-rolled daemon thread instead of ``asyncio.to_thread`` + ``wait_for``: ``to_thread``
    uses the loop's DEFAULT executor whose workers are non-daemon, and ``asyncio.run`` JOINS that
    executor on teardown (``shutdown_default_executor``) — so a genuinely hung loop call would still
    block the whole process at shutdown, re-introducing the exact hang this backstop exists to kill
    (and ``wait_for`` itself awaits the un-cancellable thread). A **daemon** thread blocks neither the
    executor shutdown nor interpreter exit, so the batch truly returns. ``deadline_s`` None/``<=0`` =
    await unbounded (backstop disabled)."""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()

    def _worker() -> None:
        # If the backstop already abandoned this thread, the batch's event loop is closed by the
        # time we finish — settling the (discarded) future is then a silent no-op, NOT a crash.
        try:
            res = call()
        except BaseException as exc:  # noqa: BLE001 — ferry ANY failure back to the awaiter
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(_settle_exc, fut, exc)
        else:
            with contextlib.suppress(RuntimeError):
                loop.call_soon_threadsafe(_settle_result, fut, res)

    threading.Thread(target=_worker, name="subagent-loop", daemon=True).start()
    if deadline_s is None or deadline_s <= 0:
        return await fut
    # asyncio.wait does NOT cancel/await the pending future on timeout — so a still-running daemon
    # thread is simply abandoned and control returns immediately (unlike wait_for).
    done, _pending = await asyncio.wait({fut}, timeout=deadline_s)
    if not done:
        raise TimeoutError
    return fut.result()


@dataclass
class AgentSpec:
    """One subagent's assignment. ``owned_paths`` are the globs it is allowed to
    touch (empty = unrestricted); it drives both the disjointness partition and
    the post-hoc scope check."""

    task: str
    model: str
    system: str = ""
    owned_paths: list[str] = field(default_factory=list)
    tools_enabled: bool = True
    # run_command binary allow-list: None = the tools default (a minimal dev
    # toolchain); frozenset() = forbid ALL command execution while still allowing
    # file tools. This is the knob for "let it edit files but not run code".
    allowed_commands: frozenset[str] | None = None
    # OS-sandbox run_command inside the worktree (bubblewrap). Default True = FAIL
    # CLOSED: on a host without `bwrap`, command execution is refused rather than run
    # unconfined (an allow-listed `python`/`pytest` is arbitrary execution that could
    # escape the worktree via an absolute path — see UPSTREAM_FEEDBACK 2026-07-06).
    # Set False ONLY for a trusted agent on a host without bwrap (danger-full-access).
    sandbox: bool = True
    # web tools to enable for this agent (web_search/web_scrape/web_crawl/
    # docs_lookup). None/empty = none — they cost money + reach the internet, so
    # the assigning agent turns them on per task type (research → web_search+
    # docs_lookup; scraping → web_scrape/web_crawl). Needs the matching *_API_KEY.
    web_tools: frozenset[str] | None = None
    # per-agent OpenRouter request-body passthrough, merged UNDER the loop's tool
    # schemas (the loop always controls `tools`). Carries a model's REQUIRED hints —
    # e.g. `{"max_tokens": 20000}` (glm-5), `{"provider": {"only": ["Minimax"]}}`
    # (minimax provider pin), `{"reasoning": {"exclude": True}}` (deepseek). `None` =
    # the loop's default body (tools only). See CODING_SUBAGENT_SELECTION.md for the
    # per-model hints; `pick_models` does NOT auto-populate this — the caller sets it.
    body: dict | None = None
    max_turns: int = 8
    max_cost_usd: float | None = None
    wall_clock_s: float = 1800.0
    # what kind of work this is (spec/plan/code/review/docs/research). Purely a
    # provenance/selection tag — it does NOT change how the loop runs. Recorded to the
    # ledger so aggregating real runs by task_type sharpens `select.pick_models` over
    # time (the flywheel). See `select.TASK_KINDS`.
    task_type: str = "code"
    # MCP research servers to enable for this agent (names present in the mcp_config /
    # /opt/fabrik/mcp.json `mcpServers`). None/empty = none — scoped per task_type like
    # `web_tools`. MCP tools run OUTSIDE the bwrap sandbox, so they are gated by the
    # SAFE_RESEARCH_SERVERS allowlist (see mcp_tools); needs the servers' *_API_KEY in env.
    mcp_servers: frozenset[str] | None = None
    # the MCP server definitions: a **path** to the standard Claude Code file
    # (`{"mcpServers": {…}}`, e.g. `/opt/fabrik/mcp.json`) OR the **bare** `{name: def}`
    # dict. None (or an absent `mcp` SDK / unreadable config) ⇒ MCP disabled; the agent
    # then runs with whatever `web_tools` were enabled (or no tools).
    mcp_config: dict | str | None = None
    # conscious opt-out to enable a server NOT in SAFE_RESEARCH_SERVERS — an FS/shell/exec
    # MCP would hand an untrusted pool model unsandboxed I/O, so the default REFUSES it
    # (like sandbox=False for the OS sandbox). Leave False unless you trust the server.
    mcp_allow_unlisted: bool = False
    # A single-shot (tools_enabled=False) worker on a VERIFICATION task_type (review/docs) can't
    # read the repo, so it HALLUCINATES about files/code it can't see (empirically q0-1 vs q4-5 for
    # tool-enabled). The dispatch REFUSES that combo up-front (fail-closed, no paid call) unless you
    # set this True to acknowledge you've inlined the FULL content into `task` (the finder pattern).
    # Prefer tools_enabled=True for grounding. Like sandbox=False, treat True as a reviewable opt-out.
    allow_ungrounded: bool = False


@dataclass
class AgentResult:
    """One subagent's outcome. ``diff`` is the (unapplied) unified diff of its
    worktree; ``status`` is ``out_of_scope`` if that diff left ``owned_paths``."""

    agent_id: str
    text: str
    diff: str
    status: AgentStatus
    provider: str | None
    cost_usd: float | None
    turns: int
    error: str | None = None
    tool_calls: dict[str, int] = field(
        default_factory=dict
    )  # name → count (provenance)
    latency_s: float | None = (
        None  # wall-clock seconds for the run (provenance/value metric)
    )
    out_tokens: int = 0  # summed output (completion) tokens — value/report metric
    model: str = (
        ""  # the model that produced this result (from the spec) — set by _run_one so a
    )
    # caller who only holds the results (e.g. from fanout) can score it via set_quality(model=…)
    # NOTE: `out_of_scope` is computed only for `done`/`capped` runs. An `error`
    # run may still carry a partial `diff` (earlier turns wrote before it failed) —
    # ALWAYS review an error run's diff before applying it; it is not scope-guarded.


# type of an injectable loop function (real: loop.run_loop)
LoopFn = Callable[..., LoopOutcome]


def _capped_hint(spec: AgentSpec, turns: int) -> str:
    """The actionable message stamped onto a capped ``AgentResult.error`` — WHY the run is partial +
    the fix, IN the result the orchestrator always inspects (it won't re-read docs after compaction).

    Distinguishes the TWO cap causes, because the fix differs:
      * ``turns == 0`` → the model produced no turn at all: a PROVIDER STALL (it streamed nothing
        before the wall clock, ``$0``/no provider). Raising ``max_turns`` does NOT help — re-dispatch
        or pin a provider.
      * ``turns >= 1`` → genuine budget exhaustion (it did work and ran out): raise ``max_turns``
        (the default 8 is low for tool-enabled multi-file work)."""
    if turns == 0:
        return (
            f"capped with 0 turns / $0 — the provider STALLED (streamed nothing before "
            f"wall_clock_s={spec.wall_clock_s:.0f}s); this is NOT a too-small budget, so raising "
            "max_turns won't help. Re-dispatch this agent (the batch is partial-tolerant) or pin a "
            "provider via body={'provider': {'only': ['<name>']}}."
        )
    base = (
        f"capped: hit the run budget (max_turns={spec.max_turns}, "
        f"wall_clock_s={spec.wall_clock_s:.0f}s) after {turns} turn(s) — the output/diff is PARTIAL. "
    )
    if spec.tools_enabled:
        return base + (
            "Tool-enabled/multi-file work usually needs max_turns≈20+ (the default 8 is low for it); "
            "raise max_turns (and/or wall_clock_s) and re-run this agent — do NOT trust a capped diff."
        )
    return base + "Raise max_turns/wall_clock_s and re-run this agent."


def _invoke_loop(
    loop_fn: LoopFn,
    spec: AgentSpec,
    workdir: str,
    on_progress: Callable[[dict], None] | None = None,
) -> LoopOutcome:
    return loop_fn(
        model=spec.model,
        system=spec.system,
        task=spec.task,
        workdir=workdir,
        tools_enabled=spec.tools_enabled,
        allowed_commands=spec.allowed_commands,
        web_tools=spec.web_tools,
        max_turns=spec.max_turns,
        max_cost_usd=spec.max_cost_usd,
        wall_clock_s=spec.wall_clock_s,
        sandbox=spec.sandbox,
        extra_body=spec.body,
        on_progress=on_progress,
        mcp_servers=spec.mcp_servers,
        mcp_config=spec.mcp_config,
        mcp_allow_unlisted=spec.mcp_allow_unlisted,
    )


async def _run_one(
    spec: AgentSpec,
    idx: int,
    *,
    repo: str,
    ledger: Ledger,
    loop_fn: LoopFn,
    sem: asyncio.Semaphore,
    git_lock: asyncio.Lock,
    on_progress: Callable[[dict], None] | None = None,
) -> AgentResult:
    agent_id = f"agent-{idx:03d}-{uuid.uuid4().hex[:6]}"
    t0 = time.monotonic()
    # Pre-flight FAIL-CLOSED: a tool-enabled agent that wants the sandbox but can't have
    # it must not run (an allow-listed interpreter would be unconfined). Refuse UP FRONT —
    # before a worktree or any paid LLM call — with an actionable error, not a wall of
    # per-command refusals after the model has already burned turns + money.
    # `sandbox is not False` (not truthiness) so a falsy-but-not-False value (None/0 from a
    # dict/JSON-built spec) still triggers the refusal — matches `_run_command`'s guard, so
    # the two can't disagree and leak an unsandboxed run.
    # `allowed_commands == frozenset()` = NO command execution (file tools only, confined by
    # `_resolve_in_workdir`, not bwrap) — bwrap is irrelevant, so DON'T over-refuse it (else a
    # file-edit-only agent on a bwrap-less host is forced to the stronger `sandbox=False` opt-out).
    if (
        spec.tools_enabled
        and spec.allowed_commands != frozenset()
        and spec.sandbox is not False
        and not sandbox.sandbox_available()
    ):
        result = AgentResult(
            agent_id,
            "",
            "",
            "error",
            None,
            None,
            0,
            error=(
                "sandbox unavailable: install bubblewrap (`apt install bubblewrap`) with "
                "unprivileged user namespaces, or set AgentSpec.sandbox=False for a "
                "trusted agent. Refusing to run a tool-enabled agent unsandboxed."
            ),
        )
        result.latency_s = (
            time.monotonic() - t0
        )  # match every other exit path's provenance
        result.model = (
            spec.model
        )  # every exit path stamps model (AgentResult.model contract)
        await asyncio.to_thread(_safe_ledger, ledger, spec, result)
        return result
    # Pre-flight FAIL-CLOSED: a single-shot (tools_enabled=False) worker on a VERIFICATION task_type
    # can't read the repo, so it hallucinates about files/code it can't see (empirically q0-1). Refuse
    # UP FRONT (no paid call) unless the caller acknowledged it inlined the content (allow_ungrounded).
    if (
        not spec.tools_enabled
        # case-insensitive + None-safe: a safety guard must fail-safe — `task_type="Review"` from a
        # hand-built spec (which skips pick_models' lowercasing) must not slip past.
        and (spec.task_type or "").lower() in _GROUNDED_TASK_KINDS
        and not spec.allow_ungrounded
    ):
        result = AgentResult(
            agent_id,
            "",
            "",
            "error",
            None,
            None,
            0,
            error=(
                f"single-shot (tools_enabled=False) '{spec.task_type}' worker can't read the repo — "
                "it hallucinates about files/code it cannot see (empirically q0-1 vs q4-5 tool-"
                "enabled). Use tools_enabled=True so it reads the real files, OR inline the FULL "
                "content into `task` and set AgentSpec.allow_ungrounded=True to acknowledge it."
            ),
        )
        result.latency_s = time.monotonic() - t0
        result.model = (
            spec.model
        )  # every exit path stamps model (AgentResult.model contract)
        await asyncio.to_thread(_safe_ledger, ledger, spec, result)
        return result
    async with sem:
        try:
            # git worktree admin (add/remove) touches shared repo state — serialize
            # just the fast admin op so concurrent agents don't contend on git's lock.
            async with git_lock:
                wt = await asyncio.to_thread(workspace.create_worktree, repo, agent_id)
        except Exception as exc:  # noqa: BLE001 — a worktree failure is this agent's error, not the batch's
            # best-effort cleanup of a partial worktree dir + dangling registration
            partial = Path(repo) / ".tmp" / "subagents" / agent_id
            with contextlib.suppress(Exception):
                shutil.rmtree(partial, ignore_errors=True)
                async with git_lock:
                    await asyncio.to_thread(workspace.prune_worktrees, repo)
            result = AgentResult(
                agent_id, "", "", "error", None, None, 0, error=f"worktree: {exc}"
            )
            result.latency_s = time.monotonic() - t0
            result.model = (
                spec.model
            )  # every exit path stamps model (AgentResult.model contract)
            # offload the ledger write: its optional Postgres dual-write is a blocking network
            # call that must not run on the event loop (it would stall the whole batch).
            await asyncio.to_thread(_safe_ledger, ledger, spec, result)
            return result

        # tag every progress event with THIS agent's id so a batch-level callback can
        # tell the agents apart (the callback fires from the loop's worker thread).
        prog = (
            (lambda ev: on_progress({**ev, "agent_id": agent_id}))
            if on_progress is not None
            else None
        )
        try:
            try:
                # OUTER wall-clock BACKSTOP: run the loop in a thread, but never await it
                # unbounded. `run_loop` self-bounds by `wall_clock_s`, yet a vendored-transport
                # hang (a never-first-token provider) can blow past it — so cap the await at
                # `wall_clock_s + grace`. On timeout the loop THREAD keeps running (a Python thread
                # can't be cancelled) and finishes/cleans up on its own, but THIS coroutine returns,
                # so the batch proceeds instead of hanging (see `_outer_grace_s`). `grace <= 0`
                # disables the backstop (await unbounded — the pre-fix behavior).
                grace = _outer_grace_s()
                deadline = (spec.wall_clock_s + grace) if grace > 0 else None
                outcome = await _await_loop_with_backstop(
                    lambda: _invoke_loop(loop_fn, spec, wt, prog), deadline
                )
            except TimeoutError:
                # The loop overran its own `wall_clock_s` bound — the transport/provider hung without
                # honoring `hard_timeout_s`. Force-cap as `capped` (partial-tolerant, NOT scored:
                # status != "done", so a provider stall can't teach `pick_models` a false 0 — mirrors
                # the loop's own stall-cap). cost_usd=None: the call never returned, so the spend is
                # unknown; report it honestly rather than guess.
                result = AgentResult(
                    agent_id,
                    "",
                    "",
                    "capped",
                    None,
                    None,
                    0,
                    error=(
                        f"outer wall-clock backstop fired at wall_clock_s={spec.wall_clock_s:.0f}s "
                        f"+ grace {grace:.0f}s: the dispatch did not self-terminate (a provider "
                        "likely accepted the connection but never streamed a first token). The "
                        "batch continued; a fresh dispatch usually re-routes the provider "
                        "(fanout's recover_caps retries this SAME model once), or fall back to "
                        "native. Tune with SUBAGENT_OUTER_GRACE_S."
                    ),
                )
            except Exception as exc:  # noqa: BLE001 — the loop failed → error (no cost); batch survives
                result = AgentResult(
                    agent_id, "", "", "error", None, None, 0, error=str(exc)
                )
            else:
                # The loop SUCCEEDED (and may have spent real money). Capture the
                # diff separately so a diff-capture failure never discards the
                # cost/text/turns we already paid for.
                try:
                    async with git_lock:
                        diff = await asyncio.to_thread(workspace.worktree_diff, wt)
                        paths = await asyncio.to_thread(workspace.changed_paths, wt)
                except Exception as exc:  # noqa: BLE001 — preserve cost, but FAIL CLOSED
                    # We could not capture/scope-check the diff, so we cannot certify
                    # the run stayed in scope → status=error (never a bare "done").
                    # Cost/text/turns/provider are still preserved (paid work isn't lost).
                    result = AgentResult(
                        agent_id,
                        outcome.text,
                        "",
                        "error",
                        outcome.provider,
                        outcome.cost_usd,
                        outcome.turns,
                        error=f"diff capture failed (scope unverified): {exc}",
                        tool_calls=outcome.tool_calls,
                        out_tokens=outcome.out_tokens,
                    )
                else:
                    status: AgentStatus = outcome.status
                    # scope-check any run that produced work (done OR capped) — a
                    # capped agent can still have written outside its bounds. Uses
                    # the authoritative git path list (handles renames/quoted/mode).
                    stray: list[str] = []
                    if status in ("done", "capped"):
                        stray = workspace.out_of_scope_paths(paths, spec.owned_paths)
                        if stray:
                            status = "out_of_scope"
                    err = outcome.error
                    if status == "out_of_scope":
                        # FAIL-CLOSED: withhold the diff. A caller that applies `r.diff` without
                        # checking `r.status` then CANNOT contaminate its repo — which is exactly how
                        # an out-of-scope agent's helper scripts once landed in a real one. Name the
                        # offenders so the caller doesn't have to audit.
                        diff = ""
                        err = (
                            f"out_of_scope: wrote {stray} outside owned_paths={spec.owned_paths}. "
                            "Diff WITHHELD (nothing to apply). Re-run with corrected owned_paths or a "
                            "tighter task."
                        )
                    elif status == "capped" and not err:
                        # A cap means the diff/text is PARTIAL. Put WHY + the fix IN the result —
                        # the orchestrator always inspects AgentResult, but won't re-read the docs
                        # (limited context / compaction). `turns` distinguishes a provider stall
                        # (turns=0) from genuine budget exhaustion — the fix differs.
                        err = _capped_hint(spec, outcome.turns)
                    result = AgentResult(
                        agent_id,
                        outcome.text,
                        diff,
                        status,
                        outcome.provider,
                        outcome.cost_usd,
                        outcome.turns,
                        error=err,
                        tool_calls=outcome.tool_calls,
                        out_tokens=outcome.out_tokens,
                    )
        except Exception as exc:  # noqa: BLE001 — safety net: _run_one must NEVER raise into the batch
            result = AgentResult(
                agent_id, "", "", "error", None, None, 0, error=str(exc)
            )
        finally:
            try:
                async with git_lock:
                    await asyncio.to_thread(workspace.remove_worktree, repo, wt)
            except Exception:  # noqa: BLE001 — `git worktree remove` failed; force-reclaim the dir
                # so this run can't leak an orphan (the exact junk the startup sweep also cleans),
                # then prune the now-dangling registration. Best-effort; never mask the real result.
                with contextlib.suppress(Exception):
                    shutil.rmtree(wt, ignore_errors=True)
                    async with git_lock:
                        await asyncio.to_thread(workspace.prune_worktrees, repo)

        result.latency_s = time.monotonic() - t0
        result.model = (
            spec.model
        )  # stamp the model so a results-only holder can score it later
        # offload the ledger write off the event loop (its optional Postgres dual-write blocks).
        await asyncio.to_thread(_safe_ledger, ledger, spec, result)
        return result


def _safe_ledger(ledger: Ledger, spec: AgentSpec, result: AgentResult) -> None:
    try:
        ledger.append(agent_record(spec, result))
    except Exception:  # noqa: BLE001 — a ledger write failure must NEVER fail/sink an agent run
        pass


def _default_ledger_path(repo: str) -> str:
    return str(Path(repo) / ".tmp" / "subagents" / "ledger.jsonl")


def _warn_unrecorded_backlog(ledger_path: str, current_ids: set) -> None:
    """Loud one-line WARNING iff EARLIER pool runs were ledgered but never scored+recorded — the
    point-of-use signal that makes a forgotten `record_agent_run` visible instead of silent. Excludes
    ``current_ids`` (this batch, which the caller scores after adjudication). Best-effort: ANY failure
    here is swallowed — a flywheel nudge must never break a dispatch."""
    try:
        from .ledger import audit_unrecorded

        prior = [
            e
            for e in audit_unrecorded(ledger_path)
            if e.get("agent_id") not in current_ids
        ]
        if prior:
            logger.warning(
                "flywheel: %d earlier pool run(s) ran but were never recorded — score each with "
                "record_agent_run(spec, result, quality_score=…) (or record_run from the ledger if "
                "the results are gone); audit_unrecorded(%r) lists them. pick_models cannot learn "
                "from an unrecorded run.",
                len(prior),
                ledger_path,
            )
    except Exception:  # noqa: BLE001 — a nudge must NEVER break a dispatch
        pass


async def arun_agents(
    specs: list[AgentSpec],
    *,
    repo: str,
    ledger_path: str | None = None,
    max_concurrency: int = 4,
    loop_fn: LoopFn | None = None,
    on_progress: Callable[[dict], None] | None = None,
    load_dotenv: bool = True,
) -> list[AgentResult]:
    """Async core: run all ``specs`` with owned_paths-aware concurrency.

    Disjoint groups run in parallel (bounded by ``max_concurrency``); members of
    an overlapping group run serially in index order. Results are returned in the
    input order, one per spec (partial-tolerant).

    ``load_dotenv`` (default ``True``): populate the process env from ``<repo>/.env`` (the curated
    subagents keys only — ``OPENROUTER_API_KEY`` / ``SUBAGENT_RUNS_DSN`` / web-tool keys) for any
    that are not already set, so "use the pool" works with no manual ``export``. Real env vars
    always win; set ``False`` to opt out (e.g. an embedder that manages env itself).

    ``on_progress`` (opt-in) fires once per completed transport turn, per agent, with
    ``{"agent_id", "turns", "cost_usd", "provider", "tools"}`` — for a live babysitting
    view of cost/progress. It is called from a worker THREAD (keep it cheap + thread-safe,
    e.g. an append to a file); a raising callback is swallowed, never crashing a run."""
    if max_concurrency < 1:
        raise ValueError(f"max_concurrency must be >= 1, got {max_concurrency}")
    if not specs:
        return []
    # Autoload <repo>/.env FIRST (before any transport/flywheel env read) so a bare agent call from
    # the project root has OPENROUTER_API_KEY + SUBAGENT_RUNS_DSN without manual sourcing.
    if load_dotenv:
        load_env(repo)
    call = loop_fn if loop_fn is not None else run_loop
    resolved_ledger_path = ledger_path or _default_ledger_path(repo)
    ledger = Ledger(resolved_ledger_path)
    # Self-healing worktree GC (fleet-wide leak fix): reclaim orphaned worktrees a PRIOR run's
    # cleanup `finally` couldn't remove — an OOM/SIGKILL or the outer wall-clock backstop abandoning
    # the event-loop thread skips the `finally`, leaking the dir + registration. Sweeping here (best-
    # effort, age-gated so a live concurrent batch is never touched) means orphans are reclaimed on
    # the next pool run instead of piling up (~2.9 GB fleet-wide before this). Never fails the batch.
    with contextlib.suppress(Exception):
        await asyncio.to_thread(
            workspace.sweep_stale_worktrees, repo, max_age_s=_worktree_max_age_s()
        )
    # Read-only agents (tools_enabled=False → single-shot, they never write the tree) are ALWAYS
    # parallel-safe regardless of owned_paths — each is its own group. Only WRITER agents need
    # owned_paths serialization (empty owned_paths = "writes anywhere" ⇒ overlaps everything ⇒
    # must serialize). Without this split, a pool of single-shot readers (owned_paths=[], e.g. a
    # parallel review/research fan-out) all collapse into ONE overlapping group via disjoint() and
    # run SERIALLY — defeating the parallelism. (Upstreamed from trade-intelligence, 2026-07-08.)
    writer_ids = [i for i, s in enumerate(specs) if s.tools_enabled]
    groups = [
        {writer_ids[k] for k in g}
        for g in workspace.disjoint([list(specs[i].owned_paths) for i in writer_ids])
    ]
    groups += [{i} for i, s in enumerate(specs) if not s.tools_enabled]
    sem = asyncio.Semaphore(max_concurrency)
    git_lock = asyncio.Lock()
    results: dict[int, AgentResult] = {}

    async def run_group(group: set[int]) -> None:
        for idx in sorted(group):  # serial within an overlapping group
            results[idx] = await _run_one(
                specs[idx],
                idx,
                repo=repo,
                ledger=ledger,
                loop_fn=call,
                sem=sem,
                git_lock=git_lock,
                on_progress=on_progress,
            )

    await asyncio.gather(*(run_group(g) for g in groups))
    ordered = [results[i] for i in range(len(specs))]
    # Point-of-use flywheel nudge (the fix for the 25%-record-rate footgun): every run is durably
    # ledgered, but SCORING it (record_agent_run) is a deferred, manual, silently-forgettable step —
    # a caller can accumulate a large unrecorded pile with ZERO signal, and pick_models then learns
    # nothing. Surface any EARLIER unrecorded runs here (never THIS batch — you score it AFTER
    # adjudication), so the backlog can't grow unseen across dispatches.
    _warn_unrecorded_backlog(
        resolved_ledger_path, {getattr(r, "agent_id", None) for r in ordered}
    )
    return ordered


def run_agents(
    specs: list[AgentSpec],
    *,
    repo: str,
    ledger_path: str | None = None,
    max_concurrency: int = 4,
    loop_fn: LoopFn | None = None,
    on_progress: Callable[[dict], None] | None = None,
    load_dotenv: bool = True,
) -> list[AgentResult]:
    """Synchronous wrapper around :func:`arun_agents`.

    Raises ``RuntimeError`` if called from within a running event loop — use
    ``await arun_agents(...)`` there instead. ``load_dotenv`` / ``on_progress`` — see
    :func:`arun_agents`.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass  # no running loop → safe to own one
    else:
        raise RuntimeError(
            "run_agents() cannot be called from a running event loop; "
            "use `await arun_agents(...)` instead"
        )
    return asyncio.run(
        arun_agents(
            specs,
            repo=repo,
            ledger_path=ledger_path,
            max_concurrency=max_concurrency,
            loop_fn=loop_fn,
            on_progress=on_progress,
            load_dotenv=load_dotenv,
        )
    )


def results_table(entries: list[dict]) -> str:
    """Render the STANDARD post-run report table an orchestrator emits after a pool run.

    One row per unit; each ``entry`` is a dict:
      ``unit``    — the work unit name (str)
      ``model``   — the model id used (str)
      ``result``  — the :class:`AgentResult` (supplies provider / cost / latency / out_tokens / status)
      ``quality`` — YOUR 0–5 quality verdict (the same score you pass to ``record_agent_run``)
      ``fixes``   — one-line summary of confirmed fixes / output (str)

    This is the human-readable report; it does NOT replace the flywheel — the orchestrator must
    ALSO ``record_agent_run(spec, result, quality_score=…, project=…)`` per unit (NOT
    ``record_run(result, …)``, which silently no-ops on a raw AgentResult — see PROPOSED_RULE). Total:
    a missing/oddly-typed field renders as ``—`` rather than raising."""
    head = "| Unit | Model | Provider | Cost | Latency | Out | My quality score | Confirmed fixes |"
    rows = [head, "|---|---|---|---:|---:|---:|:--:|---|"]
    for e in entries:
        r = e.get("result")
        cost_v = getattr(r, "cost_usd", None)
        lat_v = getattr(r, "latency_s", None)
        out_tok = getattr(r, "out_tokens", 0) or 0
        prov = getattr(r, "provider", None) or "—"
        cost = f"${cost_v:.4f}" if cost_v is not None else "—"
        lat = f"{lat_v:.0f}s" if lat_v is not None else "—"
        out = f"{out_tok / 1000:.1f}k" if out_tok else "—"
        rows.append(
            f"| {e.get('unit', '—')} | {e.get('model', '—')} | {prov} | {cost} | {lat} | "
            f"{out} | {e.get('quality', '—')}/5 | {e.get('fixes', '')} |"
        )
    return "\n".join(rows)


def fanout(
    task_type: str,
    units: list[str | dict],
    *,
    repo: str,
    project: str | None = None,
    mode: Literal["read_only", "write"] = "read_only",
    k: int | None = None,
    prefer: Literal["quality", "value"] = "quality",
    max_concurrency: int | None = None,
    record: bool = True,
    recover_caps: bool = True,
    **spec_kwargs: Any,
) -> tuple[list[AgentResult], str]:
    """One call for a K-way, family-diverse, parallel-safe, auto-recorded pool fan-out — the
    "utilize the whole pool" vehicle that replaces hand-rolled ``run_agents`` boilerplate (and the
    forgotten-``record_agent_run`` footgun it invites).

    ``units`` is either ``list[str]`` — each a unit's ``task`` text (for a ``mode="read_only"``
    single-shot fan-out; you MUST have inlined what it needs to read into that text) — OR
    ``list[dict]`` ``{"task": …, "owned_paths": […]}`` for a ``mode="write"`` writer fan-out. (A
    read_only unit may also be a ``{"task": …}`` dict; any ``owned_paths`` on it is IGNORED — a
    single-shot reader writes nothing, so path scoping is meaningless and the sentinel is used.)

    What it does:
      1. Model selection under the ≤$1.5 cap (Phase-A ranking). **``prefer`` defaults to ``"quality"``,
         and fanout ENFORCES family diversity itself**: it draws a generous ``pick_models`` pool and
         reorders it distinct-family-FIRST, so the first ``min(draw, #families)`` units always get
         DISTINCT vendor families — the whole point of a recall fan-out (different families catch
         different bugs). This holds regardless of the ranking SOURCE: the vendored ``_TABLE`` is only
         family-diverse in its top-3, and an active synced ranking doc (``SUBAGENT_SELECTION_DOC``)
         orders by empirical value with NO family notion — fanout's own reorder makes the guarantee real
         in both. (The concrete top models differ per ``task_type``: judgment → v4-pro/m3/glm-4.5-air;
         code → v4-flash/qwen3-coder-next/glm-4.7-flash — always 3 families, different vendors.)
         ``prefer="value"`` instead takes ``pick_models``' cheapest-first order VERBATIM (no diversity
         reorder) — for cost-optimised BULK work where per-unit diversity doesn't matter. If fewer
         distinct models than units, models CYCLE distinct-first (never a crash, never a needless repeat
         while a distinct model is free).
      2. Builds parallel-safe specs:
         * ``read_only`` → ``tools_enabled=False, allow_ungrounded=True``, each a UNIQUE sentinel
           ``owned_paths`` so every unit is its own disjoint group (belt-and-suspenders with the
           single-shot always-parallel rule) — all run concurrently.
         * ``write`` → ``tools_enabled=True`` carrying each unit's ``owned_paths`` (**required,
           non-empty**), which MUST be pairwise-DISJOINT (checked via :func:`workspace.disjoint`) or
           this raises ``ValueError`` — a writer fan-out that would silently serialize is a bug, not a
           slow path.
      3. ``run_agents(specs, repo=…, max_concurrency=max_concurrency or len(specs))`` — full
         parallelism by default.
      4. If ``record and project``: ``record_agent_run(spec, r, project=project)`` per pair —
         UNSCORED (score after you adjudicate, via ``set_quality``). Fail-open: a record error never
         loses the returned results.

    Returns ``(results, results_table_markdown)`` — the results plus the standard report table.

    ``**spec_kwargs`` pass through to every :class:`AgentSpec` (e.g. ``system=``, ``max_cost_usd=``,
    ``wall_clock_s=``, ``max_turns=``, ``body=``). Do NOT pass ``tools_enabled`` / ``allow_ungrounded``
    / ``owned_paths`` / ``task_type`` there — ``fanout`` owns those and rejects them UP FRONT with a
    ``ValueError`` (uniformly across modes — not left to Python's per-branch duplicate-kwarg
    ``TypeError``, which would miss a field a given mode doesn't itself pass).

    ``recover_caps`` (default ``True``): a unit that returns a ZERO-OUTPUT cap (``status == "capped"`` with
    ``out_tokens == 0`` — provider CONGESTION, NOT model quality) is given ONE more chance on the **SAME
    model** — a FRESH dispatch, so OpenRouter's health-aware routing re-routes it to a healthy provider (it
    deprioritizes a provider with a recent outage). It is NOT a vendor swap: the cap is a transient provider
    stall, the model deserves a second chance, and the 20s first-token detection makes the retry cheap. A
    structural ``error`` (sandbox/ungrounded/worktree refusal) is NOT retried — a retry can't fix a host
    problem. Bounded 1× per unit, SEQUENTIAL (not a concurrent hedge), cost/wall-capped via ``run_agents``. If
    the retry ALSO zero-caps, the cap STANDS (the model's providers are saturated right now) and the flywheel
    down-ranks a PERSISTENTLY flaky model statistically over many runs — never reactively on one blip. A
    still-capped unit is recorded UNSCORED (the ledger nulls a non-``done`` quality — a congested provider is
    not a bad model). Set ``recover_caps=False`` to disable.
    """
    if mode not in ("read_only", "write"):
        raise ValueError(f"fanout: mode must be 'read_only' or 'write', got {mode!r}")
    if not units:
        raise ValueError("fanout: units is empty — nothing to dispatch")
    if mode == "write" and task_type in _WRITE_STEER_TASK_TYPES:
        # Loud, actionable, NON-blocking (like record_run's footgun warning). Never raises — a genuine
        # exploration review that must read files to discover what's relevant is a valid write-mode use.
        print(
            f"⚠️  fanout({task_type!r}, mode='write'): review/grounding whose code you can INLINE is "
            "cheaper + can't cap as mode='read_only' (single-shot). write-mode is for EXPLORATION that "
            "must discover files; if that's you, you're fine — capped runs now return a partial report.",
            file=sys.stderr,
        )
    # fanout OWNS these AgentSpec fields (mode/task_type/parallel-safety are its job). Reject them
    # in **spec_kwargs UNIFORMLY + up front — Python's own duplicate-kwarg TypeError only fires for
    # the fields a given branch happens to pass (e.g. write-mode never passes allow_ungrounded), so
    # relying on it would let allow_ungrounded slip through silently in write mode.
    reserved = {
        "tools_enabled",
        "allow_ungrounded",
        "owned_paths",
        "task_type",
    } & spec_kwargs.keys()
    if reserved:
        raise ValueError(
            f"fanout: {sorted(reserved)} are set by fanout itself — don't pass them in **spec_kwargs"
        )
    if k is not None and k <= 0:
        raise ValueError(f"fanout: k must be a positive int (or None), got {k}")
    if max_concurrency is not None and max_concurrency <= 0:
        raise ValueError(
            f"fanout: max_concurrency must be a positive int (or None), got {max_concurrency}"
        )

    draw = k if k is not None else len(units)
    if prefer == "value":
        # value = cheapest-first for BULK work; diversity is explicitly NOT the goal here, so take
        # pick_models' value order verbatim.
        models = pick_models(task_type, n=draw, prefer="value")
    else:
        # prefer="quality" is the RECALL fan-out: fanout OWNS the family-diversity guarantee rather
        # than trusting the source ranking's top-K — which is family-diverse in the vendored _TABLE but
        # NOT under an active synced ranking doc (SUBAGENT_SELECTION_DOC orders by empirical value with
        # no family notion) and, even in the default, only for the top-3. Draw a GENEROUS pool and
        # greedily reorder distinct-family-FIRST so the first min(draw, #families) models are always
        # distinct families regardless of the ranking source.
        ranked = pick_models(task_type, n=max(draw, 24), prefer="quality")
        seen: set[str] = set()
        diverse: list[str] = []
        rest: list[str] = []
        for m in ranked:
            fam = m.split("/")[0]
            if fam not in seen:
                seen.add(fam)
                diverse.append(m)
            else:
                rest.append(m)
        models = (diverse + rest)[:draw]
    if not models:
        raise ValueError(
            f"fanout: pick_models({task_type!r}) returned no models "
            "(empty ranking/table, or every candidate excluded by `exclude`/`max_cost_per_mtok`)"
        )

    specs: list[AgentSpec] = []
    if mode == "read_only":
        for i, unit in enumerate(units):
            if isinstance(unit, str):
                task = unit
            elif isinstance(unit, dict) and "task" in unit:
                task = unit["task"]
            else:
                raise ValueError(
                    f"fanout: read_only unit {i} must be a str or a dict with a 'task' key, "
                    f"got {type(unit).__name__}"
                )
            specs.append(
                AgentSpec(
                    task=task,
                    model=models[i % len(models)],
                    task_type=task_type,
                    tools_enabled=False,
                    allow_ungrounded=True,
                    # unique sentinel ⇒ each read-only unit is its own disjoint group (never
                    # matches a real path; a single-shot agent writes nothing, so it's inert).
                    owned_paths=[f"<fanout-ro-{i}>"],
                    **spec_kwargs,
                )
            )
    else:  # write — owned_paths required + must be disjoint, else the fan-out serializes silently
        owned_lists: list[list[str]] = []
        tasks: list[str] = []
        for i, unit in enumerate(units):
            if not isinstance(unit, dict) or not unit.get("owned_paths"):
                raise ValueError(
                    f"fanout(mode='write'): unit {i} must be a dict with a non-empty 'owned_paths' "
                    "(a writer with no owned_paths writes anywhere → overlaps everything → serializes)"
                )
            if "task" not in unit:
                raise ValueError(
                    f"fanout(mode='write'): unit {i} is missing the required 'task' key"
                )
            op = unit["owned_paths"]
            if not isinstance(op, list):
                # a bare str is truthy so it slips the guard above, then list("src/a.py") would
                # char-split into garbage single-char "paths" that disjoint() sees as non-overlapping
                raise ValueError(
                    f"fanout(mode='write'): unit {i} 'owned_paths' must be a list of globs, "
                    f'got {type(op).__name__} — wrap a single glob as ["..."]'
                )
            if not all(isinstance(g, str) and g.strip() for g in op):
                # a degenerate element (empty/whitespace-only str, None, int) would either match
                # nothing (silent fail-closed) or crash fnmatch inside disjoint() — reject it up front
                raise ValueError(
                    f"fanout(mode='write'): unit {i} 'owned_paths' must be NON-EMPTY glob strings, "
                    f"got {op!r}"
                )
            owned_lists.append(list(op))
            tasks.append(unit["task"])
        # Auto-tune the turn budget for tool work (see _WRITE_DEFAULT_TURNS) — only when the caller
        # didn't set one; a caller-supplied max_turns always wins.
        spec_kwargs.setdefault("max_turns", _WRITE_DEFAULT_TURNS)
        groups = workspace.disjoint(owned_lists)
        if len(groups) != len(units):
            raise ValueError(
                f"fanout(mode='write'): owned_paths overlap — {len(units)} units collapse to "
                f"{len(groups)} parallel group(s). Writers MUST be pairwise-disjoint or they "
                "serialize; split the work so no two units can touch the same path."
            )
        for i, task in enumerate(tasks):
            specs.append(
                AgentSpec(
                    task=task,
                    model=models[i % len(models)],
                    task_type=task_type,
                    tools_enabled=True,
                    owned_paths=owned_lists[i],
                    **spec_kwargs,
                )
            )

    results = run_agents(
        specs,
        repo=repo,
        max_concurrency=max_concurrency if max_concurrency is not None else len(specs),
    )

    # L4 (rethink 2026-07-12): recover a ZERO-OUTPUT CAP by giving the SAME model ONE more chance — a
    # FRESH dispatch, NOT a vendor swap. A zero-output cap is provider CONGESTION, not model quality: the
    # in-dispatch stall loop already excluded the stalled provider (`provider.ignore`) and exhausted its
    # retries, and OpenRouter's health-aware routing deprioritizes a provider with an outage in the last
    # 30s — so a fresh call re-routes the SAME model to a HEALTHY provider (the second chance the model
    # deserves; OR picks the best path, we don't second-guess the model). Our 20s first-token detection
    # makes it cheap: if it caps AGAIN the model's providers are genuinely saturated right now, so the cap
    # STANDS and the flywheel down-ranks a PERSISTENTLY flaky model statistically over many runs — never
    # reactively on one blip. Bounded 1× per unit, SEQUENTIAL (hedging a saturated pool amplifies load),
    # inheriting the same worktree/cost/wall caps via run_agents. The model is unchanged, so `specs[i]`
    # already names the model that ran; a still-capped unit stays status="capped" and is recorded UNSCORED
    # (the ledger's no-false-0 rule — a congested provider is not a bad model).
    if recover_caps:
        for i, (spec, r) in enumerate(zip(specs, results, strict=True)):
            # ONLY a genuine provider-congestion cap (status="capped", 0 output). NOT a structural "error"
            # (sandbox-unavailable / ungrounded / worktree-failure refusal): a retry can't fix a host/config
            # problem and would burn the pool. A capped run that produced partial output (out_tokens > 0)
            # is not wasted and is left alone.
            if r.status == "capped" and r.out_tokens == 0:
                # Re-dispatch the SAME spec (same model) — a fresh call lets OpenRouter route around the
                # provider that just congested. No model swap, no exclude bookkeeping.
                retry_list = run_agents([spec], repo=repo)
                if retry_list and (
                    retry_list[0].out_tokens > 0 or retry_list[0].status == "done"
                ):
                    results[i] = retry_list[
                        0
                    ]  # recovered on a healthy provider this time

    if record and project:
        for spec, r in zip(specs, results, strict=True):
            try:
                record_agent_run(
                    spec, r, project=project
                )  # unscored — set_quality later
            except Exception:  # noqa: BLE001 — a record failure NEVER loses the returned results
                logger.warning(
                    "fanout: record_agent_run failed for model %s", spec.model
                )

    entries = [
        {"unit": f"{task_type}[{i}]", "model": s.model, "result": r}
        for i, (s, r) in enumerate(zip(specs, results, strict=True))
    ]
    return results, results_table(entries)


__all__ = [
    "run_agents",
    "arun_agents",
    "AgentSpec",
    "AgentResult",
    "AgentStatus",
    "results_table",
    "fanout",
]
