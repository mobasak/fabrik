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
import shutil
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from . import sandbox, workspace
from ._dotenv import load_env
from .ledger import Ledger, agent_record
from .loop import LoopOutcome, run_loop

AgentStatus = Literal["done", "capped", "error", "out_of_scope"]


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
    # NOTE: `out_of_scope` is computed only for `done`/`capped` runs. An `error`
    # run may still carry a partial `diff` (earlier turns wrote before it failed) —
    # ALWAYS review an error run's diff before applying it; it is not scope-guarded.


# type of an injectable loop function (real: loop.run_loop)
LoopFn = Callable[..., LoopOutcome]


def _capped_hint(spec: AgentSpec) -> str:
    """The actionable message stamped onto a capped ``AgentResult.error`` — WHY the run is partial +
    the fix, IN the result the orchestrator always inspects (it won't re-read docs after compaction).
    The usual culprit is too-low ``max_turns`` for tool-enabled multi-file work (the default 8 caps
    mid-task)."""
    base = (
        f"capped: hit the run budget (max_turns={spec.max_turns}, "
        f"wall_clock_s={spec.wall_clock_s:.0f}s) before finishing — the output/diff is PARTIAL. "
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
    if spec.tools_enabled and spec.sandbox is not False and not sandbox.sandbox_available():
        result = AgentResult(
            agent_id, "", "", "error", None, None, 0,
            error=(
                "sandbox unavailable: install bubblewrap (`apt install bubblewrap`) with "
                "unprivileged user namespaces, or set AgentSpec.sandbox=False for a "
                "trusted agent. Refusing to run a tool-enabled agent unsandboxed."
            ),
        )
        result.latency_s = time.monotonic() - t0  # match every other exit path's provenance
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
                outcome = await asyncio.to_thread(_invoke_loop, loop_fn, spec, wt, prog)
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
                    if status in ("done", "capped") and not workspace.paths_in_scope(
                        paths, spec.owned_paths
                    ):
                        status = "out_of_scope"
                    err = outcome.error
                    if status == "capped" and not err:
                        # A cap means the diff/text is PARTIAL. Put WHY + the fix IN the result —
                        # the orchestrator always inspects AgentResult, but won't re-read the docs
                        # (limited context / compaction). The usual culprit is too-low max_turns for
                        # tool-enabled multi-file work (the default 8 caps mid-task).
                        err = _capped_hint(spec)
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
            except Exception:  # noqa: BLE001 — best-effort cleanup; never mask the real result
                pass

        result.latency_s = time.monotonic() - t0
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
    ledger = Ledger(ledger_path or _default_ledger_path(repo))
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
    return [results[i] for i in range(len(specs))]


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


__all__ = [
    "run_agents",
    "arun_agents",
    "AgentSpec",
    "AgentResult",
    "AgentStatus",
    "results_table",
]
