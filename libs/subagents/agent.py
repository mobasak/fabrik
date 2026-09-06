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
import math
import os
import re
import shutil
import sys
import threading
import time
import uuid
import weakref
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from . import lanes, sandbox, spend_cap, workspace
from ._dotenv import load_env
from ._repo import resolve_repo as _resolve_repo
from .lanes import FailureCause
from .ledger import Ledger, agent_record
from .loop import LoopOutcome, run_loop
from .nvidia_models import NVIDIA_TOOL_CALLERS, nvidia_supports_tools
from .pg_ledger import record_agent_run
from .providers import (
    ProviderConfig,
    UnknownProviderError,
    known_providers,
    resolve_provider,
)
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
        want = float(os.getenv("SUBAGENT_OUTER_GRACE_S", "30"))
        # ⚠️ `float("nan")` parses fine and every NaN comparison is False — so a NaN here silently
        # DISABLES the backstop (`grace > 0` False ⇒ no deadline) while the spend sweep's own
        # `grace <= 0` guard ALSO reads False and lets it run. Unbounded runs plus an armed sweep is
        # the exact money bug this review closed, reachable through a neighbouring variable; and
        # `max(21600, nan)` returning 21600 collapses the age floor on top of it.
        return want if math.isfinite(want) else 30.0
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


def _settle_result(fut: asyncio.Future[Any], value: Any) -> None:  # noqa: ANN401
    if not fut.done():
        fut.set_result(value)


def _settle_exc(fut: asyncio.Future[Any], exc: BaseException) -> None:
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
    fut: asyncio.Future[LoopOutcome] = loop.create_future()

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
    body: dict[str, object] | None = None
    # ⚠️ G3 (2026-09-02): 8 is LOW for tool-enabled work and this default is why. Measured over the
    # real capped population: turn-exhausted runs averaged 14.1 turns against ceilings of 8 (25×),
    # 20 (21×), 6 (14×) and 24 (8×) — i.e. we routinely paid for TRUNCATED work and recorded it as
    # `capped`, indistinguishable from a provider stall until `failure_reason` landed. The default
    # stays 8 because a single-shot read-only unit genuinely needs no more and raising it globally
    # would convert a truncation into unbounded spend; the fix is that a caller doing multi-turn
    # tool work MUST set it (the module's own guidance says ≈20+), and `failure_reason =
    # 'turn-budget-exhausted'` now makes the cases where it was too low COUNTABLE instead of
    # invisible. Re-derive from the distribution before changing this number.
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
    mcp_config: dict[str, dict[str, object]] | str | None = None
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
    # which upstream provider to DISPATCH to (registry key in `providers._REGISTRY`).
    # Default "openrouter" = the pre-seam behavior, byte-identical. Set "nvidia" to route
    # THIS unit to NVIDIA Build (its own base_url + NVIDIA_API_KEY); a mixed fan-out may
    # carry different providers per unit. Capabilities (tools/web/MCP) are provider-agnostic.
    # NVIDIA ids never enter `pick_models`/`_TABLE` — a NVIDIA unit is chosen by explicit
    # `model=` + `provider="nvidia"`.
    provider: str = "openrouter"

    def __post_init__(self) -> None:
        # Fail LOUD at CONSTRUCTION on an unknown provider — before any worktree clone or
        # paid dispatch, for EVERY entry path (run_agents / arun_agents / fanout). Resolving
        # it deep in the transport instead would be caught by the loop's blanket `except` and
        # degraded into a generic "error" AgentResult, hiding a fleet-wide `provider=` typo
        # one wasted worktree at a time.
        resolve_provider(self.provider)


class FanoutBatch:
    """What :func:`fanout` returns: still ``(results, table)``, plus the dispatch context.

    **Unpacking is unchanged** — ``results, table = fanout(...)`` works exactly as before, across
    every vendored copy, because ``__iter__`` yields the same two values in the same order.

    Why not a ``NamedTuple``: its fields ARE its tuple, so a third field would break every
    two-value unpack in the fleet. This class keeps the 2-tuple shape and carries the dispatch
    context as attributes instead. (``isinstance(batch, tuple)`` is therefore False; nothing in
    the module or its callers relies on that — checked before the change.)

    **What the context is FOR.** ``fanout`` can hand back a result whose dispatch row was never
    written — the ``record_agent_run`` failure is deliberately swallowed so a record failure never
    loses results, and when ``project`` is None nothing is recorded at all. Scoring such a run
    creates an ORPHAN: an INSERT-only ``scored`` delta with no run behind it, carrying a real model
    name into the flywheel. Seven such rows exist in ``fabrik_analytics`` (5 with real models, 4 of
    them zeros); two are traceable to a disclosed incident. ``.score()`` refuses them by name.
    """

    __slots__ = (
        "results", "table", "_recorded", "_task_type", "_project", "_models",
        "_state_dir",
        # ⚠️ T06: a REAL slot. `FanoutBatch` uses `__slots__`, so `b.degradation_events = []`
        # raises AttributeError without this — prototyped before the ticket was written.
        "degradation_events",
        # ⚠️ T11: likewise a REAL slot, APPENDED LAST. Same rule as above, and same rule as every
        # new AgentResult field: additive, defaulted, and it MUST NOT enter `__iter__`.
        "dead_units",
    )

    def __init__(
        self,
        results: list[AgentResult],
        table: str,
        *,
        _recorded: dict[str, bool] | None = None,
        _task_type: str = "",
        _project: str | None = None,
        _models: dict[str, str] | None = None,
        _state_dir: str | None = None,
        degradation_events: list[dict[str, object]] | None = None,
        dead_units: int | None = None,
    ) -> None:
        self.results = results
        self.table = table
        self._recorded = _recorded or {}
        self._task_type = _task_type
        self._project = _project
        self._models = _models or {}
        # ⚠️ **T06 — the events are an ATTRIBUTE, never a third yielded value.** `__iter__` must
        # keep yielding exactly two items so `results, table = fanout(...)` survives in every one of
        # the ~48 vendored copies; a consumer who wants the detail reads `batch.degradation_events`.
        self.degradation_events: list[dict[str, object]] = degradation_events or []
        # ⚠️ **T11 — how many units came back with NOTHING USABLE.** Same attribute-not-a-third-value
        # rule as above. A caller that reads "11 dispatched" and gets 5 usable reports currently has
        # to notice the gap themselves; the reporter did not, and *"an agent that trusted
        # '11 dispatched' would have converged on 45% recall"*. Dead units STAY in `results` — they
        # are counted, never dropped, because silently shrinking the list is how the gap becomes
        # invisible in the other direction.
        # ⚠️ `None` DERIVES the count from `results` rather than defaulting to a comfortable 0.
        # `FanoutBatch` is PUBLIC and hand-constructible (this suite does it), and a field whose
        # whole purpose is to stop a gap being invisible must not re-hide it on the very path
        # that skips `fanout`. A default of 0 on a batch holding two failed units is not a safe
        # default, it is a wrong answer. `fanout` still passes the value it already computed.
        self.dead_units: int = (
            sum(1 for r in results if _is_dead_unit(r)) if dead_units is None else dead_units
        )
        # The repo-anchored .tmp/subagents that `fanout` outboxed the dispatch rows to.
        # `score()` MUST look in the same place; resolved CWD-relative it finds nothing
        # pending and discards the verdict as a genuine orphan.
        self._state_dir = _state_dir

    def __iter__(self) -> Iterator[Any]:
        """Preserve ``results, table = fanout(...)`` — the whole point of not using a 3-field type.

        ⚠️ THIS YIELDS TWO ITEMS: the results LIST and the table STRING — never the results one by
        one. ``for r in batch:`` therefore binds ``r`` to a list and then to a string, and
        ``r.text`` is an AttributeError or an empty repr rather than an agent's output. That reads
        as "the agents returned nothing" instead of "you used the wrong shape", which is how it
        cost a consuming session three misfires in one day, one of them double-paying a dispatch
        (web-ecommerce-factory, ``01M1CDZYR4``). **Iterate ``batch.results``, never the batch.**
        """
        yield self.results
        yield self.table

    def __len__(self) -> int:
        """**2 — the TUPLE arity, not the number of agents.**

        This object stands in for the ``(results, table)`` 2-tuple, so ``len()`` reports 2 however
        many agents ran. ``f"dispatched {len(batch)} agents"`` therefore logs 2 forever; the count
        you want is ``len(batch.results)``. Kept at 2 deliberately: it is correct for the tuple
        identity every fleet consumer unpacks, and changing it would silently alter behaviour in
        ~46 vendored copies to fix a docstring problem.
        """
        return 2

    def __getitem__(self, index: object) -> Any:
        """Refuse indexing with an error that NAMES the fix.

        ``batch[0]`` used to raise a bare ``'FanoutBatch' object is not subscriptable``, which says
        nothing about what to do instead. The reporter proposed delegating to ``.results`` so that
        indexing "just works" — **deliberately not done**, and this is the mirror worth stating:
        ``__iter__`` must keep yielding the 2-tuple (that contract ships to ~46 copies), so a
        delegating ``__getitem__`` would make ``batch[0]`` the first RESULT while ``list(batch)[0]``
        stayed the results LIST. Index and iterate would disagree — a fresh silent trap of exactly
        the class being reported. A loud, teaching refusal costs the caller one edit and can never
        mislead.
        """
        raise TypeError(
            "FanoutBatch is not indexable — it stands in for the `(results, table)` 2-tuple. "
            f"Use `batch.results[{index!r}]` for one AgentResult, `batch.results` to iterate, "
            "or `results, table = fanout(...)` to unpack. (Indexing is refused rather than "
            "delegated because `__iter__` yields the 2-tuple, so delegating would make indexing "
            "and iteration disagree.)"
        )
        # ⚠️ ONE PROTOCOL SIDE-EFFECT, measured rather than assumed. `__len__` + `__getitem__`
        # together ARE the old-style sequence protocol, so `reversed(batch)` now reaches this
        # raise instead of the interpreter's "'FanoutBatch' object is not reversible". Both are
        # TypeError — a caller catching TypeError is unaffected — and this message is the more
        # useful of the two. `x in batch` and `list(batch)` are untouched: both prefer `__iter__`,
        # which still yields the 2-tuple.

    def __repr__(self) -> str:
        n = len(self.results)
        unrecorded = sum(1 for v in self._recorded.values() if not v)
        return (
            f"FanoutBatch({n} result(s), {unrecorded} unrecorded, "
            f"task_type={self._task_type!r}, project={self._project!r})"
        )

    def score(self, result_or_agent_id: AgentResult | str, quality: float) -> bool:
        """Back-fill a quality score, with the bucket bound from the DISPATCH, not the caller.

        The caller supplies only *which* run and *how good*; model / task_type / project come from
        what was actually dispatched, so a mistyped or stale bucket cannot misattribute the score.

        Raises ``ValueError`` for an ``agent_id`` not in this batch, or for one whose dispatch row
        was never recorded — the second is the orphan case, refused HERE because this is the last
        point at which the cause is still known. Downstream all that survives is a scored row with
        nothing behind it.
        """
        agent_id = (
            result_or_agent_id.agent_id
            if isinstance(result_or_agent_id, AgentResult)
            else result_or_agent_id
        )
        if agent_id not in self._recorded:
            raise ValueError(
                f"score(): {agent_id!r} is not in this batch — scoring a foreign agent_id is how "
                f"a bogus score reaches a real model's ranking. Batch: {sorted(self._recorded)}"
            )
        if not self._recorded[agent_id]:
            raise ValueError(
                f"score(): {agent_id!r} has NO dispatch row, so scoring it would create an orphan "
                f"delta. Likely causes, in the order they are cheapest to CHECK:\n"
                f"  0. the psycopg DRIVER is not installed here — pg_ledger imports it LAZILY as "
                f"an optional dependency, so the sink fail-opens on EVERY record and no DSN or "
                f"database state can matter until it is present. Cheapest check of all: "
                f"`python -c 'import psycopg'`.\n"
                f"  1. SUBAGENT_RUNS_DSN is not set (process env or <repo>/.env) — record_agent_run "
                f"fail-opens to False without it. A fleet survey found it absent in half the repos "
                f"sampled.\n"
                f"  2. the DSN IS set but the database was unreachable — the row is NOT lost, it is "
                f"in .tmp/subagents/pg_outbox.jsonl awaiting replay. Nothing to re-dispatch; flush "
                f"the outbox, then score.\n"
                f"  3. the fanout ran with project=None (the auto-record is gated on a project).\n"
                f"  4. the record raised — check the WARNING fanout logged at dispatch.\n"
                f"⚠️ The store consulted here is the POSTGRES DISPATCH ROW, not the local "
                f".tmp/subagents/ledger.jsonl. A ledger row DOES exist for this run, and its missing "
                f"`project` key is NOT the cause — reading it as the cause has already cost one caller "
                f"a session and produced a wrong upstream report."
            )
        # Refuse an empty bucket rather than forwarding one. set_quality documents project /
        # task_type / model as REQUIRED and non-empty because an empty bucket silently
        # misattributes the score — the failure mode this whole class exists to prevent. fanout
        # cannot produce this state (project=None marks every run unrecorded, so the guard above
        # already fired), but FanoutBatch is public and hand-constructible, so it is checked here
        # rather than trusted.
        model = self._models.get(agent_id, "")
        project = self._project or ""
        missing = [
            n
            for n, v in (
                ("project", project),
                ("task_type", self._task_type),
                ("model", model),
            )
            if not v
        ]
        if missing:
            raise ValueError(
                f"score(): cannot score {agent_id!r} — the dispatch context is incomplete "
                f"({', '.join(missing)} empty). An empty bucket misattributes the score."
            )
        from .pg_ledger import set_quality

        # ⚠ Pass the SAME repo-anchored dir the dispatch row was outboxed to. Without it
        # `set_quality` resolves `_outbox_path(None)` CWD-relative, looks for the pending
        # dispatch row in a DIFFERENT directory, concludes "genuine orphan", and DISCARDS
        # the verdict — re-creating on the scoring side the exact split just closed on the
        # dispatch side.
        return set_quality(
            agent_id,
            quality,
            project=project,
            task_type=self._task_type,
            model=model,
            receipt_dir=self._state_dir,
            outbox_dir=self._state_dir,
        )

    def unscored(self) -> list[str]:
        """This batch's recorded ``agent_id``s that carry no quality score yet.

        Reads the LEDGER rather than tracking ``.score()`` calls in-process: the hub's round-close
        currently back-fills via ``set_quality`` directly, and an in-process tracker would report
        those correctly-scored runs as still owed. Unrecorded runs are excluded — they are not
        "unscored", they are un-dispatched, and :meth:`score` refuses them.

        Fail-open: an unreachable ledger yields ``[]`` rather than raising, matching the writer's
        contract. A caller asserting "nothing owed" must therefore treat DB availability as part
        of its own check, not infer it from an empty list.
        """
        from .pg_ledger import unscored_agent_ids

        candidates = [a for a, ok in self._recorded.items() if ok]
        if not candidates:
            return []
        try:
            return unscored_agent_ids(candidates)
        except Exception:  # noqa: BLE001 — fail-open, mirroring the writer
            logger.warning("FanoutBatch.unscored(): ledger unreachable; returning []")
            return []


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
    # F2 (2026-09-02): seconds this unit spent WAITING on the provider sub-cap + global semaphore,
    # before any model work began. `latency_s` measures dispatch→completion and therefore CONTAINS
    # this; recording it separately is what lets a consumer recover model time without changing a
    # field 48 vendored copies already read. None when the run never reached the acquisition.
    queue_s: float | None = None
    model: str = (
        ""  # the model that produced this result (from the spec) — set by _run_one so a
    )
    # caller who only holds the results (e.g. from fanout) can score it via set_quality(model=…)
    # T02b: the structured `lanes.FailureCause` CARRIED verbatim from `LoopOutcome.failure` —
    # this ticket only threads it through, never routes/branches on it (T05a) and never
    # reclassifies it (the cause arrives already built by `loop.classify`). `None` for a "done"
    # run, a budget-exhausted cap with nothing to classify, or any pre-dispatch/infra refusal that
    # never reached a `LoopOutcome` at all. Appended LAST, after `model`, with a `None` default so
    # an existing positional `AgentResult(...)` construction (13 args, the pre-T02b arity) still
    # succeeds. Mirror (review round 2, evidence-checked — see the module README's Gotchas):
    #   * `astuple(r)`/`fields(r)` — the tuple/field list grows 13→14.
    #   * `r == <hand-built 13-arg instance>` — now compares 14 fields and can return False.
    #   * `astuple(r)[-1]` / `asdict(r)["failure"]` do NOT hand back a `FailureCause` — the
    #     former is a plain tuple, the latter a plain dict; `asdict(r)["failure"].cause` raises
    #     `AttributeError`. A distinct footgun from "a key merely appeared".
    #   * `asdict(r)`/JSON gaining a `"failure"` key: under `additionalProperties: false` this is
    #     SCHEMA REJECTION, not a serialization crash — a vendoring agent expecting a `TypeError`
    #     will not get one; the payload is just refused downstream.
    #   * pickle — the hazard runs NEW → OLD, not the reverse: an old pickle loaded by new code
    #     reads `failure` as its class-level `None` default (safe). A NEW pickle carrying a
    #     non-`None` cause embeds a reference to `subagents.lanes.FailureCause`; a PRE-T01
    #     vendored copy (whose `lanes.py` has no such class) raises `AttributeError` unpickling
    #     it — real, in a module hand-copied into ~48 repos at mixed versions.
    #   * a subclass is affected ONLY if it redeclares `model` to control field ordering —
    #     `model`/`queue_s`/`latency_s` already had defaults before this change, so a subclass
    #     merely adding a new trailing field already required a default (dataclass field-
    #     ordering rules), same as always.
    #   * the ledger is UNAFFECTED: `ledger.agent_record` reads a `_RESULT_FIELDS` whitelist via
    #     `getattr`, `failure` is not in it, so the JSONL/Postgres row shape is unchanged and
    #     there is no `json.dumps` risk on the nested dataclass — T04 must add it deliberately.
    failure: FailureCause | None = None
    # NOTE: `out_of_scope` is computed only for `done`/`capped` runs. An `error`
    # run may still carry a partial `diff` (earlier turns wrote before it failed) —
    # ALWAYS review an error run's diff before applying it; it is not scope-guarded.

    @property
    def content(self) -> str:
        """Alias for :attr:`text` — every major LLM SDK calls this field ``content``.

        Reported by transdoc (2026-08-22) with receipts: three fanout harvests in one session read
        ``getattr(r, "content", "")``, the near-universal name. The default made **22 paid,
        successful runs look empty** — status ``done``, ``cost_usd > 0``, caller sees ``""``. It was
        mis-diagnosed twice (once as a sandbox path problem, once as a drained quota), 17 outputs
        were destroyed (the ledger scrubs text by design), and 45 rows were wrongly scored 0.

        ⚠ Their *other* suggestion — a ``__getattr__`` raising ``AttributeError("did you mean
        .text?")`` — does NOT fix that call site, and it is worth knowing why: ``getattr(obj, name,
        default)`` **swallows AttributeError and returns the default**. The hint only ever reaches
        someone writing a bare ``r.content``, which is not the pattern that cost them the runs. An
        alias is the only form that fixes both.

        Residual, stated rather than implied away: this closes ``content`` specifically. ANY other
        wrong name under ``getattr(r, <name>, "")`` is still silently empty — that is a property of
        ``getattr``'s default, not something this module can close. Harvest with ``r.text``.
        """
        return self.text

    @property
    def output(self) -> str:
        """Alias for :attr:`text` — the OTHER name callers guess, and the residual `content` predicted.

        ⚠️ THE `content` DOCSTRING ABOVE NAMED THIS EXACT RESIDUAL and it came true six days later.
        It closed ``content`` and said plainly: "ANY other wrong name under ``getattr(r, <name>, "")``
        is still silently empty". On 2026-08-28 `brand-identiy-creator` wrote ``result.output`` after a
        paid 3-model fanout and got ``AttributeError`` **only once the batch had completed** — the
        crash cost a full re-run, because outputs are not persisted anywhere readable.

        Note the two failures differ: ``getattr(r, "content", "")`` was SILENT (22 paid runs looked
        empty); a bare ``r.output`` is LOUD but arrives after the money is spent. Both are the same
        root cause — a canonical field with guessable aliases — and an alias is one line.

        `.text` remains canonical. This does not close the class: the next guess is still open, which
        is why the residual is restated rather than declared solved."""
        return self.text

    @property
    def empty_output(self) -> bool:
        """True when a ``done`` run produced NO usable payload — the "$0.18 for nothing" seam.

        A run whose ``status`` is ``done`` but whose ``text`` is blank AND whose ``diff`` is blank
        SUCCEEDED with nothing gradeable — indistinguishable from a clean success at every layer until a
        human reads the (empty) output. It is not necessarily a low-quality answer: a model can burn its
        whole ``max_tokens`` on a reasoning channel and return an empty completion (measured for
        ``minimax-m2.7`` at 1500 and 4000 tokens, intel 2026-08-29). Callers use this to flag it LOUDLY
        (``results_table`` shows ``⚠EMPTY``). Detection is ``done`` + blank text + blank diff: the ``diff``
        clause is load-bearing — a ``mode="write"`` coder's value is its diff, so a non-empty diff is NOT
        empty even if ``text`` is blank. Scoped to ``done`` only: ``capped``/``error``/``out_of_scope`` are already-loud states the
        ranker's ``success_rate`` handles, so they are not this silent-success seam.

        An empty ``done`` is left UNSCORED (NULL) by ``record_agent_run`` — NOT auto-0'd (intel's
        2026-08-29 policy call): an empty completion is usually output-budget burn, so a 0 is a false
        zero. This property DETECTS + surfaces (⚠EMPTY); the record path leaves the verdict unknown."""
        if self.status != "done":
            return False
        return not (self.text or "").strip() and not (self.diff or "").strip()

    @property
    def ok(self) -> bool:
        """True iff this run completed cleanly — ``status == "done"``. The first thing every consumer
        reaches for after a fanout ("did it work?"), so it is provided rather than left to a guess.

        Reported as a measured CLASS across three independent consumers (intel 2026-08-29, `01M17XKJXM`):
        the shape of the API made the wrong reach the default one, and none failed until AFTER the spend.
        ``ok`` is a strict success test — ``capped`` (hit the turn cap, partial), ``error`` and
        ``out_of_scope`` are all NOT ``ok``. A ``done`` run can still be empty (see :attr:`empty_output`),
        so ``ok`` means "ran to completion", not "produced usable payload" — check ``empty_output`` when the
        payload is what you're grading."""
        return self.status == "done"


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
        # The `provider.only` pin is an OpenRouter routing object — useless (and body-hygiene-stripped)
        # for a non-OR provider like NVIDIA, whose 0-turn cap is a rate-limit exhaustion after the
        # blind-429 backoff. Give provider-appropriate advice, not the OR pin. Guarded: an unknown
        # provider (post-construction mutation) must not raise out of the hint builder and discard the
        # capped unit's partial work — default to the OR-style advice.
        try:
            sends_or_object = resolve_provider(spec.provider).sends_or_provider_object
        except UnknownProviderError:
            sends_or_object = True
        pin_advice = (
            "or pin a provider via body={'provider': {'only': ['<name>']}}"
            if sends_or_object
            else "or lower concurrency / retry later (a free-tier rate-limit exhaustion)"
        )
        return (
            f"capped with 0 turns / $0 — the provider STALLED (streamed nothing before "
            f"wall_clock_s={spec.wall_clock_s:.0f}s); this is NOT a too-small budget, so raising "
            f"max_turns won't help. Re-dispatch this agent (the batch is partial-tolerant) {pin_advice}."
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
    on_progress: Callable[[dict[str, object]], None] | None = None,
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
        # non-default only, so an injected fixed-arity `loop_fn` still works on the default path
        **({} if spec.provider == "openrouter" else {"provider": spec.provider}),
    )


def _provider_concurrency_cap(
    provider: str, cfg: ProviderConfig, global_cap: int
) -> int | None:
    """Effective per-provider in-flight sub-cap: the registry default, overridable via
    ``SUBAGENT_<PROVIDER>_MAX_CONCURRENCY``, never above the global cap. ``None`` = no sub-cap."""
    cap = cfg.max_concurrency
    env = os.getenv(f"SUBAGENT_{provider.upper()}_MAX_CONCURRENCY")
    if env is not None:
        try:
            v = int(env)
        except ValueError:
            v = -1
        if v > 0:
            cap = v
    # A non-positive cap (a stray registry 0, meant as "disable") would make asyncio.Semaphore(0)
    # hang every unit forever — treat any non-positive value as "no sub-cap" instead.
    return None if cap is None or cap <= 0 else min(cap, global_cap)


def _build_provider_sems(
    specs: list[AgentSpec], global_cap: int
) -> dict[str, asyncio.Semaphore]:
    """One semaphore per provider that declares a sub-cap, so a mixed fan-out caps (e.g.)
    NVIDIA below OR — a single global semaphore cannot. The global sem still bounds the total."""
    sems: dict[str, asyncio.Semaphore] = {}
    for s in specs:
        if s.provider in sems:
            continue
        # Partial-tolerant: an unknown provider here (only reachable via a post-construction
        # mutation that bypassed AgentSpec.__post_init__'s validation) must NOT raise out of the
        # batch setup and sink EVERY unit — skip its sub-cap and let that one unit fail per-unit
        # inside its own _run_one (caught by the loop's blanket except → a per-unit error result).
        try:
            cfg = resolve_provider(s.provider)
        except UnknownProviderError:  # a bad provider is that unit's error, not the batch's
            continue
        cap = _provider_concurrency_cap(s.provider, cfg, global_cap)
        if cap is not None:
            sems[s.provider] = asyncio.Semaphore(cap)
    return sems


#: Reason tokens for the cap decision — a bare bool cannot say WHICH of these happened, and this
#: module's own rule is that a return value collapsing several states is a defect.
CAP_NO_CAP_CONFIGURED = "no-cap-configured"
CAP_RESERVED = "cap-reserved"
CAP_EXCEEDED = "cap-exceeded"
CAP_UNVERIFIABLE = "cap-unverifiable"
CAP_FAIL_OPEN = "cap-fail-open"


@dataclass
class _CapHold:
    """What the cap decided for one run, and what the release path needs to act on it."""

    reason: str
    reservation: str | None = None  # the job_id actually reserved; None ⇒ nothing to release
    provider: str = ""
    estimate: Decimal | None = None
    refusal: AgentResult | None = None  # set ⇒ do NOT dispatch; return this


def _cap_dsn() -> str | None:
    """The cap's DSN — the SAME store as the run ledger, resolved the same way.

    The cap tables live beside ``subagent_runs`` on the shared Postgres, not in a second store, so
    there is deliberately no second env var to configure or forget.
    """
    dsn = os.getenv("SUBAGENT_RUNS_DSN")
    return dsn or None


#: Bounds how many cap connections can be open at once, and how long a connect may block.
#:
#: ⚠️ BOTH bounds are load-bearing, and the module already learned each of them elsewhere.
#: `pg_ledger` connects with ``connect_timeout=5`` for exactly this reason. Without a timeout, a
#: BLACKHOLED postgres (a dropped route or a firewall DROP — not a refused connection, which fails
#: fast) blocks on TCP retransmit for as long as the OS allows. The reclaim sweep runs
#: pre-dispatch and OUTSIDE the outer wall-clock backstop, which wraps only the per-unit loop —
#: so an unbounded connect there stalls the entire batch before a single agent starts.
_CAP_CONNECT_TIMEOUT_S = 5
#: And a concurrency bound: `fanout()` defaults `max_concurrency` to `len(specs)`, so a 50-unit
#: capped batch would otherwise open 50 simultaneous fresh connections to the SHARED postgres-main
#: — on top of the ledger's own. The cap's connections are short-lived (one statement each), so a
#: small ceiling costs nothing and removes the amplification.
_CAP_MAX_CONNECTIONS = 4
#: A settle that fails is RETRIED, because the module's own docstring said "a settle that raises
#: must be retried, not dropped" while nothing in the code retried it. An admission is not a
#: mitigation: the reclaim sweep releases a stranded reservation at $0, so a run that ACTUALLY
#: SPENT and whose settle died at commit had its spend erased from the cap — the one direction
#: money must never err. A brief retry converts a transient blip (the common case) into a correct
#: settle; the loud warning below covers what a retry cannot.
#: A cap statement blocked on a lock must not outlive the batch — see _cap_arm_timeouts.
def _cap_int_env(name: str, default: int) -> int:
    """An operator lever for each cap bound. These create a NEW refusal path — a merely-slow
    Postgres now aborts the reserve and the run is REFUSED — so a loaded shared instance needs a
    way to widen them without editing a vendored file."""
    try:
        got = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return got if got > 0 else default


_CAP_LOCK_TIMEOUT_MS = _cap_int_env("SUBAGENT_CAP_LOCK_TIMEOUT_MS", 5000)
_CAP_STATEMENT_TIMEOUT_MS = _cap_int_env("SUBAGENT_CAP_STATEMENT_TIMEOUT_MS", 15000)
#: The hard lower bound on the reclaim age — 6h. Neither the env var nor the current batch may go
#: below it, because the rows being swept belong to runs this process never saw.
_CAP_RECLAIM_FLOOR_S = 21600.0
_CAP_SETTLE_ATTEMPTS = 3
_CAP_SETTLE_BACKOFF_S = 0.5
#: WeakKeyDictionary, not a plain dict: `run_agents` creates a NEW event loop per call
#: (`asyncio.run`), so a strong-keyed map would retain one entry — and one dead loop — per batch,
#: forever, in any long-lived process that dispatches repeatedly. Weak keys let a finished loop and
#: its semaphore be collected together.
_cap_sems: weakref.WeakKeyDictionary[Any, asyncio.Semaphore] = weakref.WeakKeyDictionary()


def _cap_sem() -> asyncio.Semaphore:
    """A per-event-loop connection semaphore.

    Keyed by the running loop rather than created at import: a module-level ``asyncio.Semaphore``
    binds to whichever loop imported it, and this module is driven from several (``run_agents``
    creates one per call via ``asyncio.run``). A semaphore from a dead loop is not merely useless,
    it raises when awaited.
    """
    loop = asyncio.get_running_loop()
    sem = _cap_sems.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(_CAP_MAX_CONNECTIONS)
        _cap_sems[loop] = sem
    return sem


async def _cap_arm_timeouts(conn: Any) -> None:
    """Bound the STATEMENT, not just the connect — `pg_ledger` does this on every path.

    `connect_timeout` bounds only the TCP handshake. A cap statement can still block indefinitely
    on a LOCK: the reclaim sweep holds every aggregate lock until its final commit, so a reserve
    waiting on that row waits as long as the sweep runs — and `_cap_acquire` is awaited BEFORE the
    outer wall-clock backstop, so nothing else bounds it. Four such waits exhaust
    `_CAP_MAX_CONNECTIONS` and the whole batch hangs at dispatch, which is the exact symptom the
    backstop was built for.
    """
    # ⚠️ `SET LOCAL` scopes to the OPEN TRANSACTION, and psycopg's `autocommit` is False by
    # default — verified live: a later cursor on the same connection reports lock_timeout=5s /
    # statement_timeout=15s, and both correctly expire after commit. So arming here does reach the
    # reserve/settle statements that follow on this connection.
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SET LOCAL lock_timeout = '{_CAP_LOCK_TIMEOUT_MS}ms'; "
                f"SET LOCAL statement_timeout = '{_CAP_STATEMENT_TIMEOUT_MS}ms'"
            )
    except Exception as exc:  # noqa: BLE001 — a driver without SET must still work…
        # …but NOT silently. Swallowing this leaves the guard absent while everything looks fine,
        # which is the failure mode the guard exists to prevent, one level up.
        logger.warning(
            "subagent_cap_timeouts_unarmed cause=%s — cap statements are running WITHOUT a "
            "lock/statement timeout and can block indefinitely",
            _cap_scrub(f"{type(exc).__name__}: {exc}"),
        )


def _cap_scrub(text: str) -> str:
    """Remove the DSN — and therefore its password — from anything about to be surfaced.

    ⚠️ NOT hypothetical. Verified against psycopg 3.3.3: a MALFORMED connection string is echoed
    back verbatim in the exception text (``missing "=" after "not-a-dsn-..." in connection info
    string``). ``SUBAGENT_RUNS_DSN`` normally carries ``user:password@host``, and the cap's refusal
    interpolates the exception into ``AgentResult.error`` — which is ledgered, logged, and handed
    to the caller. One typo'd DSN would publish the database password three ways.

    A connection-refused error does NOT leak it, which is exactly why this is worth a helper
    rather than a judgement call at each site: the leak depends on WHICH failure occurred, so the
    safe move is to scrub unconditionally.
    """
    dsn = os.getenv("SUBAGENT_RUNS_DSN") or ""
    out = text
    if dsn and dsn in out:
        out = out.replace(dsn, "<SUBAGENT_RUNS_DSN redacted>")
    # Also catch a password embedded in any URL-shaped fragment the driver may have reformatted.
    return re.sub(r"(?i)(://[^\s:/@]+:)[^\s@]+(@)", r"\1<redacted>\2", out)


def _cap_estimate(spec: AgentSpec, provider: str) -> Decimal:
    """What to reserve up front. ``max_cost_usd`` when the caller set one, else a configured default.

    ``AgentSpec.max_cost_usd`` is unset on the common path, so this needs a real default rather
    than a promise of one. $0.05 is roughly a mid-model unit and is deliberately GENEROUS: it
    over-reserves and the settle corrects downward, which errs toward the cap.
    """
    if spec.max_cost_usd is not None:
        return spend_cap.money(spec.max_cost_usd, field="max_cost_usd")
    env = f"SUBAGENT_{provider.upper()}_DEFAULT_ESTIMATE_USD"
    raw = os.getenv(env)
    if raw and raw.strip():
        try:
            return spend_cap.money(raw, field=env)
        except ValueError:
            # Name the variable, never its contents — the same guarantee `cap_env_value` makes,
            # which was applied there and not to this sibling read three lines away. An operator
            # can point either variable at the wrong thing.
            raise ValueError(
                f"{env} is not a usable estimate (value not shown): expected a non-negative "
                f"decimal amount of USD, e.g. '0.05'"
            ) from None
    return Decimal("0.05")


async def _cap_acquire(spec: AgentSpec, agent_id: str) -> _CapHold:
    """Decide whether this run may spend, and reserve its estimate if so.

    THE FAIL-DIRECTION TABLE, and every branch of it is deliberate:

    * no ``monthly_cap_env`` on the provider row ⇒ ``no-cap-configured``. Nothing is opened,
      nothing is reserved, and the dispatch path is byte-identical to before the cap existed.
    * the env var is absent/blank ⇒ also uncapped. A cap is an explicit operator opt-in.
    * reserved successfully ⇒ ``cap-reserved``.
    * the server CONFIRMED the refusal (the conditional upsert returned no row) ⇒ ``cap-exceeded``,
      and no paid call is made.
    * **anything else — driver missing, connection refused, a bad cap value, an exception nobody
      anticipated — is ``cap-unverifiable`` and REFUSES.** A capped provider whose ledger cannot be
      read is a provider whose spend cannot be bounded, and "we could not check" must never resolve
      to "so go ahead". The unknown case fails toward refusal because over-spending is the one
      error that is not recoverable by re-running.
    * ``SUBAGENT_CAP_FAIL=open`` is the narrow, explicit escape for an operator who would rather
      dispatch than stall — it downgrades ONLY the unverifiable case, never ``cap-exceeded``.
    """
    cfg = None
    try:
        cfg = resolve_provider(spec.provider)
    except UnknownProviderError:
        # An unknown provider has no cap by definition, and the transport rejects it anyway.
        return _CapHold(CAP_NO_CAP_CONFIGURED)
    except Exception as exc:  # noqa: BLE001 — anything ELSE is "unknown", and unknown refuses
        # The fail-direction table says every unanticipated failure is `cap-unverifiable`. A blanket
        # suppress here was the one branch that failed OPEN: a registry that can fail transiently
        # (the documented extension seam) would silently uncap a capped provider.
        return _CapHold(
            CAP_UNVERIFIABLE,
            # ⚠ T03: stamp `model=spec.model` — this refusal never dispatches, so nothing else
            # will ever set `.model`, and a bare `r.model` downstream would regress this unit to
            # an empty model name (the very regression `or spec.model` exists to cover; belt AND
            # suspenders, since a caller reading `r.model` directly — bypassing `fanout` — gets
            # no fallback at all).
            refusal=AgentResult(
                agent_id, "", "", "error", None, None, 0,
                error=_cap_scrub(
                    f"could not resolve provider {spec.provider!r} to check its cap "
                    f"({type(exc).__name__}); refusing rather than spending unbounded"
                ),
                model=spec.model,
            ),
        )
    cap_env = getattr(cfg, "monthly_cap_env", None) if cfg is not None else None
    if not cap_env:
        return _CapHold(CAP_NO_CAP_CONFIGURED)

    def _refuse(reason: str, detail: str) -> _CapHold:
        # ⚠ T03: same stamp — every `_refuse(...)` call site in this function (cap-exceeded,
        # cap-unverifiable, the $0 kill switch) is a refusal that never dispatched, so `model`
        # must be set here or it is never set at all.
        return _CapHold(
            reason,
            refusal=AgentResult(
                agent_id, "", "", "error", None, None, 0, error=detail, model=spec.model
            ),
        )

    # ⚠️ The ESTIMATE is resolved OUTSIDE the try, deliberately. It is derived from the caller's own
    # `max_cost_usd` (or an env default), so a bad value is a CALLER bug, not an infrastructure
    # failure — and inside the try it would be caught by the catch-all and reported as
    # `cap-unverifiable`, whose message tells the operator to "set SUBAGENT_CAP_FAIL=open". That
    # advice is actively wrong here: following it would silently dispatch the malformed spec
    # UNCAPPED instead of surfacing the real bug. A caller error must raise like a caller error.
    # ⚠️ SCOPED TO THE UNIT, not left to escape. The estimate comes from the caller's own
    # `max_cost_usd` or an env default, so a bad figure IS a caller/config error — but `_run_one`
    # calls this unguarded and `run_agents` gathers without `return_exceptions`, so raising here
    # killed the ENTIRE batch: one mistyped `SUBAGENT_<P>_DEFAULT_ESTIMATE_USD` (say `0,05`) made
    # every capped batch on the box die, discarding the results of units that had already
    # dispatched and PAID. Measured by a closing-round finder. `_run_one`'s own docstring says it
    # must never raise into the batch; this was the one path that did.
    reserved = False
    try:
        estimate = _cap_estimate(spec, spec.provider)
    except ValueError as exc:
        return _refuse(
            CAP_UNVERIFIABLE,
            f"the cap estimate for provider {spec.provider!r} is unusable: {exc}. This is a "
            f"caller/config error — fix the figure. SUBAGENT_CAP_FAIL=open would dispatch it "
            f"UNCAPPED and is NOT the remedy.",
        )
    try:
        cap = spend_cap.cap_env_value(cap_env)
        if cap is None:
            return _CapHold(CAP_NO_CAP_CONFIGURED)
        if cap == 0:
            # A $0 cap is documented as a KILL SWITCH, and a kill switch that admits runs is not
            # one. Left to the upsert, `est <= budget` passes for an estimate of exactly 0 (a spec
            # with max_cost_usd=0), the run dispatches, and its ACTUAL can still be billed — the
            # cap having authorised it. Refusing here makes "zero dollars" mean zero dispatches,
            # which is what the operator asked for and the only reading that errs toward the cap.
            logger.warning(
                "subagent_cap_kill_switch provider=%s agent=%s — %s is 0",
                spec.provider, agent_id, cap_env,
            )
            return _refuse(
                CAP_EXCEEDED,
                f"{cap_env} is 0 — a zero monthly cap is a kill switch; no run is dispatched for "
                f"provider {spec.provider!r}. Unset the variable to remove the cap.",
            )
        dsn = _cap_dsn()
        if dsn is None:
            raise RuntimeError(
                "SUBAGENT_RUNS_DSN is unset, so the joint monthly cap cannot be checked"
            )
        import psycopg  # lazy: the driver stays OPTIONAL for every uncapped consumer

        async with _cap_sem(), await psycopg.AsyncConnection.connect(
            dsn, connect_timeout=_CAP_CONNECT_TIMEOUT_S
        ) as conn:
            await _cap_arm_timeouts(conn)
            await spend_cap.reserve(
                conn,
                provider=spec.provider,
                job_id=agent_id,
                estimate_usd=estimate,
                monthly_cap_usd=cap,
                now=datetime.now(UTC),
            )
            # ⚠️ Set the INSTANT the reserve returns, INSIDE the `async with`. If the context exit
            # then raises (a close/rollback failure), the money is ALREADY reserved server-side —
            # reporting "unreserved" would leave the row with nothing that ever settles it, and
            # the sweep would later release it at $0 while the run was billing.
            reserved = True
    except spend_cap.CapExceededError as exc:
        # SERVER-CONFIRMED refusal — the only branch that means "over budget". Never downgraded by
        # SUBAGENT_CAP_FAIL=open: the cap was checked and it said no.
        logger.warning("subagent_cap_exceeded provider=%s agent=%s", spec.provider, agent_id)
        return _refuse(CAP_EXCEEDED, f"monthly spend cap reached for {spec.provider!r}: {exc}")
    except Exception as exc:  # noqa: BLE001 — EVERY other failure is "unknown", and unknown refuses
        if reserved:
            # The reservation LANDED; only the teardown failed. Proceed as reserved so the release
            # path runs — the alternative strands committed money that nothing will ever settle.
            logger.warning(
                "subagent_cap_reserved_then_teardown_failed provider=%s agent=%s cause=%s — "
                "the reservation is committed, so the run proceeds and WILL be settled",
                spec.provider, agent_id, _cap_scrub(type(exc).__name__),
            )
            return _CapHold(
                CAP_RESERVED, reservation=agent_id, provider=spec.provider, estimate=estimate
            )
        if (os.getenv("SUBAGENT_CAP_FAIL") or "").strip().lower() == "open":
            logger.warning(
                "subagent_cap_fail_open provider=%s agent=%s cause=%s — dispatching UNCAPPED",
                spec.provider, agent_id, type(exc).__name__,
            )
            return _CapHold(CAP_FAIL_OPEN)
        logger.warning(
            "subagent_cap_unverifiable provider=%s agent=%s cause=%s",
            spec.provider, agent_id, type(exc).__name__,
        )
        return _refuse(
            CAP_UNVERIFIABLE,
            _cap_scrub(
                f"monthly spend cap for {spec.provider!r} could not be verified "
                f"({type(exc).__name__}: {exc}); refusing rather than spending unbounded. "
                f"Set SUBAGENT_CAP_FAIL=open to dispatch anyway."
            ),
        )
    return _CapHold(
        CAP_RESERVED, reservation=agent_id, provider=spec.provider, estimate=estimate
    )


async def _cap_finalize(
    hold: _CapHold, cap_state: dict[str, object], result: AgentResult | None
) -> None:
    """Release the reservation — settle at the actual, or abandon, per what actually happened.

    ⚠️ NEVER RAISES. ``_run_one`` must not raise into the batch, and by this point the money is
    already spent — refusing is not available. A failure here logs and leaves the estimate
    RETAINED (an over-count the reclaim sweep reconciles), because under-counting spend is the one
    direction this module must not err in.
    """
    if hold.reservation is None:
        return
    last: Exception = RuntimeError("no attempt ran")
    for attempt in range(_CAP_SETTLE_ATTEMPTS):
        try:
            await _cap_finalize_once(hold, cap_state, result)
            return
        except _AlreadyRecordedError:
            return  # committed; the teardown failure is not this run's problem
        except asyncio.CancelledError:
            # ⚠️ NOT an Exception — `except Exception` misses it entirely, so without this branch a
            # Ctrl-C or a cancelled task strands a reservation whose money was already spent.
            #
            # ⚠️⚠️ BEST EFFORT, NOT A GUARANTEE — and the earlier comment here claimed otherwise.
            # `asyncio.shield` protects the INNER task from THIS cancellation, but if the
            # cancellation is re-delivered (or the loop is shutting down under `asyncio.run`) the
            # outer await raises again and the shielded task is left detached and destroyed
            # pending: the release never lands. A test written to prove the strong claim DISPROVED
            # it. So the honest contract is: one attempt is made, it usually completes, and when it
            # does not the reclaim sweep is the reconciliation path — which releases at $0, so a
            # cancelled run that had already spent has that spend erased. Cancel a capped batch and
            # you may under-count; that is the residual, stated rather than implied.
            with contextlib.suppress(Exception):
                await asyncio.shield(_cap_finalize_once(hold, cap_state, result))
            raise
        except Exception as exc:  # noqa: BLE001 — must never discard an otherwise-good result
            last = exc
            if attempt + 1 < _CAP_SETTLE_ATTEMPTS:
                await asyncio.sleep(_CAP_SETTLE_BACKOFF_S * (attempt + 1))
    logger.warning(
        "subagent_cap_settle_failed agent=%s attempts=%d cause=%s — the estimate stays RESERVED "
        "and is reconciled by the startup reclaim sweep, which releases it at $0. If this run DID "
        "spend, that spend is now invisible to the cap: re-run the settle by hand, or raise "
        "SUBAGENT_CAP_RECLAIM_AGE_S so the sweep does not reach it first.",
        hold.reservation, _CAP_SETTLE_ATTEMPTS, _cap_scrub(f"{type(last).__name__}: {last}"),
    )


def _cap_check_recorded(moved: bool, job_id: str, amount: Any) -> None:
    """`settle`/`abandon` return False to say THE SPEND WAS NOT RECORDED. Never discard that.

    False means one of exactly two things, and both are money going unaccounted: the reservation
    row is gone, or it was already terminal — including *already zeroed by the reclaim sweep*
    while the run was still billing. Left unchecked, that is invisible in production: no log line,
    no metric, and the aggregate is simply wrong.
    """
    if not moved:
        logger.warning(
            "subagent_cap_not_recorded agent=%s amount=%s — the reservation was missing or already "
            "terminal, so this spend is NOT counted against the cap. Most likely the reclaim sweep "
            "released it while the run was still going: raise SUBAGENT_CAP_RECLAIM_AGE_S.",
            job_id, amount,
        )


class _AlreadyRecordedError(Exception):
    """The settle/abandon COMMITTED; only the teardown failed. Not a failure to retry.

    The mirror of `_cap_acquire`'s `reserved` flag, which this originally lacked: without it a
    committed settle whose `__aexit__` raised was retried three times and then reported — three
    times — as money that was never recorded, with the final line telling the operator to raise
    SUBAGENT_CAP_RECLAIM_AGE_S, which actively delays real reclaims. Every one of those lines was
    false. Found by a pass-2 finder that EXECUTED the scenario rather than reading it.
    """


async def _cap_finalize_once(
    hold: _CapHold, cap_state: dict[str, object], result: AgentResult | None
) -> None:
    """One settle/abandon attempt. RAISES on failure so the caller can retry."""
    job_id = hold.reservation
    if job_id is None:  # unreachable via _cap_finalize, which guards; keeps this callable alone
        return
    recorded = False
    try:
        dsn = _cap_dsn()
        if dsn is None:  # cannot happen if the reserve succeeded, but do not assume it
            raise RuntimeError("SUBAGENT_RUNS_DSN vanished between reserve and settle")
        import psycopg

        async with _cap_sem(), await psycopg.AsyncConnection.connect(
            dsn, connect_timeout=_CAP_CONNECT_TIMEOUT_S
        ) as conn:
            await _cap_arm_timeouts(conn)
            cost = getattr(result, "cost_usd", None) if result is not None else None
            if cap_state.get("backstop"):
                # The paid call may STILL be running and will still be billed. Retain the estimate
                # (or the known partial, whichever is larger) rather than release it.
                keep = hold.estimate or Decimal(0)
                if cost is not None:
                    keep = max(keep, spend_cap.money(cost, field="cost_usd"))
                _cap_check_recorded(await spend_cap.abandon(conn, job_id=job_id, checkpoint_usd=keep), job_id, keep)
            elif not cap_state.get("dispatched"):
                # No paid call can have happened — a pre-flight/infra refusal. A true full refund.
                _cap_check_recorded(await spend_cap.abandon(conn, job_id=job_id, checkpoint_usd=0), job_id, 0)
            elif cost is None:
                # Dispatched, but the cost is unknown. Retain the estimate: an unknown spend must
                # not be assumed to be the cheapest possibility.
                _cap_check_recorded(
                    await spend_cap.abandon(
                        conn, job_id=job_id, checkpoint_usd=hold.estimate or Decimal(0)
                    ), job_id, hold.estimate or Decimal(0),
                )
            else:
                _cap_check_recorded(await spend_cap.settle(conn, job_id=job_id, actual_usd=cost), job_id, cost)
            recorded = True
    except _AlreadyRecordedError:
        raise
    except Exception:
        if recorded:
            # The money IS recorded; only the teardown blew up. Retrying would re-log a false
            # "not recorded" each time and end on advice that makes things worse.
            raise _AlreadyRecordedError from None
        # RE-RAISE, deliberately. This used to swallow-and-log here, which made the retry loop in
        # `_cap_finalize` inert — the wrapper could never see a failure to retry. The
        # never-raises contract is honoured by `_cap_finalize`, which is the only caller and
        # catches everything; keeping a second handler here just hid the error from the retry.
        raise


def _cap_reclaim_age_s(max_wall_clock_s: float = 0.0) -> float:
    """How old a ``pending`` reservation must be before the sweep may release it.

    ⚠️ THE FLOOR MUST EXCEED THE ACTUAL BACKSTOP, and the backstop is
    ``spec.wall_clock_s + grace`` (see ``_run_one``), **not** ``grace``. Flooring on the grace
    alone — which is what this did — makes the floor ~1h regardless of how long runs really are,
    so a batch of 2-hour runs has its budget reclaimed at 61 minutes WHILE IT IS STILL SPENDING.
    The docstring and the README both claimed "floored at the outer backstop + 1h"; both were
    false, and the guarding test asserted a constant (``>= 3600``) rather than the relation, so it
    could never have caught it. The sibling ``_worktree_max_age_s`` documents the same rule
    correctly ("MUST exceed the longest wall_clock_s in use") — this now matches it.

    A non-finite env value is REJECTED rather than passed to ``max()``: ``max(21600, nan)``
    returns 21600 silently, which reads as a safe default while the operator's intent is lost.
    """
    raw = os.getenv("SUBAGENT_CAP_RECLAIM_AGE_S", "21600")
    try:
        want = float(raw)
    except ValueError:
        want = 21600.0
    if not math.isfinite(want) or want <= 0:
        want = 21600.0
    grace = _outer_grace_s()
    # ⚠️ THE CURRENT BATCH IS A LOWER BOUND, NEVER THE BOUND. The sweep releases PRE-EXISTING rows
    # — reservations made by other batches, other processes, possibly hours ago — and their safe
    # age is the wall-clock bound of the run that CREATED them, which is not in `specs` and cannot
    # be known here. A first fix derived the floor from this batch alone; a 60-second batch would
    # then have swept a still-running 2-hour reservation, releasing its budget mid-spend. Measured
    # by a pass-2 finder against the pass-1 fix.
    #
    # So the floor is the CONSERVATIVE fleet-wide default, which this batch can only RAISE:
    # `SUBAGENT_CAP_RECLAIM_AGE_S` sets an operator bound, the current batch's own backstop pushes
    # it up if this batch runs longer, and neither may take it below `_CAP_RECLAIM_FLOOR_S`. Same
    # contract as `_worktree_max_age_s`, whose docstring says it "MUST exceed the longest
    # wall_clock_s in use" — for the cap that is not housekeeping, it is money.
    batch_backstop = max_wall_clock_s + max(grace, 0.0)
    return max(want, batch_backstop + 3600.0, _CAP_RECLAIM_FLOOR_S)


def _any_cap_configured() -> bool:
    """Is ANY provider actually capped right now? Cheap, env-only, no I/O.

    ⚠️ This gate is what stops the sweep from being a tax on every consumer who never wanted a cap.
    Without it, `_cap_reclaim_stale` runs on EVERY batch for anyone with `SUBAGENT_RUNS_DSN` set —
    which is most of them, because that is the flywheel's variable, not the cap's. They have never
    applied `schema_spend_cap.sql`, so the sweep would hit `UndefinedTable`, get caught, and log a
    warning on every single run, forever, in ~46 vendored copies. A warning nobody can act on is
    worse than silence: it trains people to ignore the log.
    """
    for name in known_providers():
        try:
            cfg = resolve_provider(name)
        except Exception:  # noqa: BLE001 — a bad row must not break dispatch
            continue
        cap_env = getattr(cfg, "monthly_cap_env", None)
        if cap_env and (os.getenv(cap_env) or "").strip():
            return True
    return False


async def _cap_reclaim_stale(max_wall_clock_s: float = 0.0) -> None:
    """Release reservations stranded past the age gate. Best-effort; NEVER fails the batch.

    ``max_wall_clock_s`` is the longest bound in THIS batch — the age floor is derived from it, so
    the sweep can never reach a run that could still be alive.
    """
    reasons: list[str] = []
    try:
        if not _any_cap_configured():
            return  # nobody is capped — do not touch Postgres, do not log
        if _outer_grace_s() <= 0:
            # The outer backstop is disabled, so a run has no upper bound and NO age gate can be
            # proven safe. Refuse to sweep rather than guess: a retained estimate errs toward the
            # cap, a wrongly-released one does not.
            logger.warning(
                "subagent_cap_reclaim_skipped — SUBAGENT_OUTER_GRACE_S disables the backstop, so "
                "no reclaim age can be proven safe; stranded reservations are NOT being released"
            )
            return
        dsn = _cap_dsn()
        if dsn is None:
            return  # no DSN ⇒ no cap tables to sweep, exactly like the ledger's own no-op
        import psycopg

        cutoff = datetime.now(UTC) - timedelta(seconds=_cap_reclaim_age_s(max_wall_clock_s))
        async with _cap_sem(), await psycopg.AsyncConnection.connect(
            dsn, connect_timeout=_CAP_CONNECT_TIMEOUT_S
        ) as conn:
            await _cap_arm_timeouts(conn)
            n = await spend_cap.reclaim_stale(conn, cutoff=cutoff, reason_sink=reasons)
        if n:
            logger.info("subagent_cap_reclaimed count=%d reasons=%s", n, reasons or ["none"])
    except Exception as exc:  # noqa: BLE001 — a reclaim failure must never sink a batch
        logger.warning(
            "subagent_cap_reclaim_failed cause=%s: %s",
            type(exc).__name__, _cap_scrub(str(exc)),
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
    prov_sem: asyncio.Semaphore | None = None,
    on_progress: Callable[[dict[str, object]], None] | None = None,
) -> AgentResult:
    """Run one agent, bounded by its provider's JOINT monthly USD cap when one is configured.

    A thin cap wrapper around :func:`_run_one_uncapped`, which holds the whole original body.

    ⚠️ **Why a wrapper and not a ``try/finally`` inside the body.** The reserve→settle span has to
    survive every exit, and the body has FIVE ``return result`` paths plus a blanket
    ``except Exception`` safety net and a ``finally``. Wrapping it in place would mean re-indenting
    ~230 lines of the most safety-critical function in this module — an enormous diff in which a
    single mis-indented line silently changes which handler owns which failure. A wrapper gets the
    same guarantee from a few lines that can actually be read.

    The one behavioural consequence, stated rather than discovered: the reservation is taken BEFORE
    the body's pre-flight refusals (sandbox-unavailable, ungrounded-single-shot) rather than after
    them. A refused run therefore reserves and then immediately abandons at ZERO, which nets to no
    change in the aggregate — correct, at the cost of one extra round trip on a path that was
    already failing. **Uncapped providers do none of this**: no cap env, no connection, no reserve,
    and the call below is the original function unchanged.
    """
    # Generated ONCE, here, and threaded into both the reservation and the run. Generating it in
    # each would produce two different uuid4s, so the settle would look up a job_id that was never
    # reserved and silently no-op — the reservation would then be held until the reclaim sweep.
    agent_id = f"agent-{idx:03d}-{uuid.uuid4().hex[:6]}"
    hold = await _cap_acquire(spec, agent_id)
    if hold.refusal is not None:
        return hold.refusal
    if hold.reservation is None:
        return await _run_one_uncapped(  # uncapped — byte-identical to the pre-cap path
            spec, idx, repo=repo, ledger=ledger, loop_fn=loop_fn, sem=sem, git_lock=git_lock,
            prov_sem=prov_sem, on_progress=on_progress, agent_id=agent_id, cap_state=None,
        )
    cap_state: dict[str, object] = {"dispatched": False}
    result: AgentResult | None = None
    try:
        result = await _run_one_uncapped(
            spec, idx, repo=repo, ledger=ledger, loop_fn=loop_fn, sem=sem, git_lock=git_lock,
            prov_sem=prov_sem, on_progress=on_progress, agent_id=agent_id, cap_state=cap_state,
        )
        return result
    finally:
        # NEVER raises: `_run_one` must not raise into the batch (the body's own safety net says so),
        # and the money is already spent by the time we get here — refusing is not on the table.
        await _cap_finalize(hold, cap_state, result)


async def _run_one_uncapped(
    spec: AgentSpec,
    idx: int,
    *,
    repo: str,
    ledger: Ledger,
    loop_fn: LoopFn,
    sem: asyncio.Semaphore,
    git_lock: asyncio.Lock,
    prov_sem: asyncio.Semaphore | None = None,
    on_progress: Callable[[dict[str, object]], None] | None = None,
    agent_id: str | None = None,
    cap_state: dict[str, object] | None = None,
) -> AgentResult:
    # Supplied by the cap wrapper so the reservation and the run share ONE id; generated here when
    # this function is called directly (tests, and any consumer that kept the old entry point).
    agent_id = agent_id or f"agent-{idx:03d}-{uuid.uuid4().hex[:6]}"
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
    # Pre-flight FAIL-CLOSED: a NVIDIA tools_enabled unit on a model that does NOT support OpenAI
    # tool-calling would have its tool schemas silently ignored (text-only) — the loop would spend
    # turns that can never call a tool. Refuse UP FRONT (no call) rather than pin an inert model;
    # it is still valid as a single-shot finder (tools_enabled=False).
    if (
        spec.provider == "nvidia"
        and spec.tools_enabled
        and not nvidia_supports_tools(spec.model)
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
                f"NVIDIA model {spec.model!r} is not a verified tool-caller — its tool schemas "
                f"would be silently ignored. Use a tool-caller {sorted(NVIDIA_TOOL_CALLERS)} for "
                "tools_enabled=True, or set tools_enabled=False to run it as a single-shot finder."
            ),
        )
        result.latency_s = time.monotonic() - t0
        result.model = spec.model
        await asyncio.to_thread(_safe_ledger, ledger, spec, result)
        return result
    # Acquire the per-provider sub-cap FIRST, then the global concurrency sem. Order matters:
    # taking the sub-cap first means a rate-limited provider's queued unit waits WITHOUT holding
    # a global permit, so it never starves another provider's units on the global sem — and a
    # provider's global footprint is bounded by its own sub-cap. The global still bounds the total.
    async with contextlib.AsyncExitStack() as stack:
        if prov_sem is not None:
            await stack.enter_async_context(prov_sem)
        await stack.enter_async_context(sem)
        # ── F2 (2026-09-02): the QUEUE WAIT, measured, without changing what latency_s means. ──
        # `t0` is set at the top of this function, ~100 lines above, while these two semaphores are
        # acquired HERE — so `latency_s` has always been dispatch-to-completion with the wait inside
        # it. Under a wide fan-out that wait dominates: the SAME model measured 1051s in a
        # concurrent benchmark sweep and 61s in production, and the flywheel read the difference as
        # the model being slow. 48 vendored copies consume `latency_s`, so it keeps its meaning and
        # the wait is recorded ALONGSIDE it; a consumer that wants model time subtracts.
        #
        # ⚠️ Into a LOCAL, not onto `result` — at this point `result` is still `None` (declared
        # `AgentResult | None` and built further down, on several branches), so assigning through it
        # would raise AttributeError on every dispatch. Caught by reading the declaration rather than
        # by the traceback it would have produced in production.
        _queue_s = time.monotonic() - t0
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
            result.queue_s = _queue_s  # F2 — the wait that is INSIDE latency_s above
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
                # ⚠️ THE MOMENT MONEY CAN START BEING SPENT. Set BEFORE the await, because the
                # cap's `finally` cannot tell a pre-flight refusal from a post-dispatch failure by
                # looking at `result`: both are status="error", cost_usd=None. Keying the release
                # on `result` would zero-abandon a run that had already started paying.
                if cap_state is not None:
                    cap_state["dispatched"] = True
                outcome = await _await_loop_with_backstop(
                    lambda: _invoke_loop(loop_fn, spec, wt, prog), deadline
                )
            except TimeoutError:
                # ⚠️ NOT a zero-refund for the spend cap. This coroutine returns, but the loop
                # THREAD keeps running (a Python thread cannot be cancelled), so the paid call may
                # still be in flight and WILL still be billed. Releasing the estimate here would
                # make that spend invisible to the cap forever — in precisely the runaway case most
                # likely to blow a budget. The flag makes the release RETAIN instead.
                if cap_state is not None:
                    cap_state["backstop"] = True
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
                    diff_capture_err = f"diff capture failed (scope unverified): {exc}"
                    if outcome.error:
                        # T02b FIXUP 4 (review round 2): the loop's OWN error explains WHY
                        # `outcome.failure` (carried below) says what it says — dropping it left
                        # `error`/`failure` telling contradictory stories (a rate_limited failure
                        # with an `error` string that never mentions a provider at all).
                        diff_capture_err += f" | loop error: {outcome.error}"
                    result = AgentResult(
                        agent_id,
                        outcome.text,
                        "",
                        "error",
                        outcome.provider,
                        outcome.cost_usd,
                        outcome.turns,
                        error=diff_capture_err,
                        tool_calls=outcome.tool_calls,
                        out_tokens=outcome.out_tokens,
                        failure=outcome.failure,  # T02b: carry, never reclassify
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
                        failure=outcome.failure,  # T02b: carry, never reclassify
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
        # attribute=True: this is the post-DISPATCH chokepoint (the loop ran) — the ONLY path where
        # provider attribution is correct (pre-flight/infra refusals above ledger unattributed).
        await asyncio.to_thread(_safe_ledger, ledger, spec, result, attribute=True)
        return result


def _attribute_provider(spec: AgentSpec, result: AgentResult) -> None:
    """Flywheel attribution, applied to the RESULT (so the returned AgentResult AND the ledger
    agree) — ONLY for a run that actually DISPATCHED to the provider (the loop ran). A non-OR
    provider (NVIDIA) never emits a served-provider name in-stream, so ``result.provider`` would be
    None. Attribute the REQUEST provider ONLY when nothing was served — NEVER overwrite a
    legitimately-served OR provider (the two-``provider`` semantics: ``AgentResult.provider`` is
    served-upstream, ``AgentSpec.provider`` is the request target). A free-tier provider with unknown
    cost is recorded as $0 (accurate; NVIDIA ids are absent from the pricing table, so this can't
    corrupt OR selection).

    ⚠ Caller MUST gate this on a real dispatch. A PRE-dispatch refusal (sandbox / ungrounded /
    tool-caller-allowlist) or an INFRA failure (worktree creation) never contacted the provider, so
    attributing its provider name + $0 would pollute that provider's ledger/flywheel error-rate with
    a fault it had nothing to do with. Hence ``_safe_ledger(..., attribute=True)`` is passed ONLY at
    the post-loop chokepoint; the pre-dispatch ledger writes leave ``provider`` unattributed."""
    if result.provider is not None or spec.provider == "openrouter":
        return
    try:
        cfg = resolve_provider(spec.provider)
    except UnknownProviderError:
        # an unknown provider (only reachable via a post-construction mutation that bypassed
        # __post_init__) → do NOT attribute a bogus name (that would corrupt result.provider and,
        # unguarded, would raise into _safe_ledger's blanket except and SILENTLY DROP the record).
        return
    result.provider = spec.provider  # set ONLY after a successful resolve
    if cfg.free_tier and result.cost_usd is None:
        result.cost_usd = 0.0


def _safe_ledger(
    ledger: Ledger, spec: AgentSpec, result: AgentResult, *, attribute: bool = False
) -> None:
    try:
        if attribute:  # only a DISPATCHED run — never a pre-flight/infra refusal (see docstring)
            _attribute_provider(spec, result)
        ledger.append(agent_record(spec, result))
    except Exception:  # noqa: BLE001 — a ledger write failure must NEVER fail/sink an agent run
        pass


def _subagent_state_dir(repo: str) -> str:
    """The ONE directory the ledger, receipts and outbox all live in, anchored on the repo.

    `_default_ledger_path` anchors on `repo`; the receipt/outbox defaults anchor on the CWD.
    Anything that resolves them independently can drift, and everything that correlates the
    three (audit_unrecorded, the strict-mode outbox guard) then reads an empty set as fact.
    """
    return str(Path(repo) / ".tmp" / "subagents")


def _default_ledger_path(repo: str) -> str:
    return str(Path(repo) / ".tmp" / "subagents" / "ledger.jsonl")


def _warn_unrecorded_backlog(
    ledger_path: str, current_ids: set[str | None]
) -> None:
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
    on_progress: Callable[[dict[str, object]], None] | None = None,
    load_dotenv: bool = True,
    warn_unrecorded: bool = True,
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
    # ⚠️ BEFORE `load_env`, before the ledger, before any mkdir — and deliberately before the
    # `not specs` early return, so an empty batch cannot launder a bad `repo=` past the one place
    # that checks it. Same reasoning as `AgentSpec.__post_init__` resolving `provider` at
    # construction: fail LOUD at the entry seam, for every path (run_agents / arun_agents / fanout),
    # rather than deep in a helper where the loop's blanket `except` degrades it into a generic
    # "error" AgentResult and hides a fleet-wide caller mistake one wasted worktree at a time.
    repo = _resolve_repo(repo)
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
    # Spend-cap reclaim, beside the worktree sweep and for the same reason: a reservation stranded
    # by a backstop timeout or a settle-time DB failure is released on the NEXT pool run instead of
    # accumulating. Without this the retained estimates pile up until the provider refuses
    # everything for the rest of the month — a cap that ratchets shut while looking like it works,
    # which is worse than no cap. Never fails the batch (same contract as the sweep above).
    await _cap_reclaim_stale(max((s.wall_clock_s for s in specs), default=0.0))
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
    prov_sems = _build_provider_sems(list(specs), max_concurrency)
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
                prov_sem=prov_sems.get(specs[idx].provider),
                on_progress=on_progress,
            )

    await asyncio.gather(*(run_group(g) for g in groups))
    ordered = [results[i] for i in range(len(specs))]
    # Point-of-use flywheel nudge (the fix for the 25%-record-rate footgun): every run is durably
    # ledgered, but SCORING it (record_agent_run) is a deferred, manual, silently-forgettable step —
    # a caller can accumulate a large unrecorded pile with ZERO signal, and pick_models then learns
    # nothing. Surface any EARLIER unrecorded runs here (never THIS batch — you score it AFTER
    # adjudication), so the backlog can't grow unseen across dispatches.
    if warn_unrecorded:
        # ⚠️ **T05b — the cascade's re-dispatches must NOT trigger this, and the fix is a caller
        # signal rather than a smarter heuristic.** This warns when EARLIER pool runs were ledgered
        # but never scored+recorded, computing `current_ids` from THIS call only. `fanout`'s walk
        # re-dispatches one spec at a time and records later, so every rung reported the whole
        # in-flight batch as an unrecorded backlog — up to 40 false lines, against the module's own
        # standard that "a warning nobody can act on is worse than silence".
        #
        # ⚠️ **PUBLIC API, additive-with-default.** `warn_unrecorded` is a new keyword on two of
        # this module's most-called functions, shipping to ~48 vendored copies. The mirror: a
        # consumer that SUBCLASSES or WRAPS either with a fixed signature sees the change; every
        # positional and keyword call site keeps working, and the default preserves today's
        # behaviour exactly. Suppression is opt-IN, so a consumer who never passes it never loses
        # the signal — which is the half that matters, because the warning is the only thing that
        # makes a forgotten `record_agent_run` visible.
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
    on_progress: Callable[[dict[str, object]], None] | None = None,
    load_dotenv: bool = True,
    warn_unrecorded: bool = True,
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
            warn_unrecorded=warn_unrecorded,
        )
    )


def _is_dead_unit(r: AgentResult) -> bool:
    """A unit that returned NOTHING THE CALLER CAN USE — the count `batch.dead_units` reports.

    ⚠️ **DELIBERATE REFINEMENT OF T11's LITERAL WORDING, and the reason is measured.** The ticket
    says ``status == "error" or out_tokens == 0``. `out_tokens` is wrong in BOTH directions:

    * it MISSES the reasoning-burn case — a `done` run can spend its whole ``max_tokens`` on a
      reasoning channel and return an empty completion, so ``out_tokens > 0`` while the payload is
      blank. That is precisely the "$0.18 for nothing" seam :attr:`AgentResult.empty_output` exists
      for, and the results table has marked it ``⚠EMPTY`` all along — keyed on the payload, NOT the
      token count, with a comment saying exactly why. A dead-unit count that disagreed with the
      ⚠EMPTY column on a ``done`` unit would be worse than no count.

      ⚠️ PRECISELY — the looser version of that sentence was challenged in review and deserved to
      be. For a ``done`` unit, dead and ``⚠EMPTY`` coincide EXACTLY. For an ``error`` they
      deliberately do NOT: ``empty_output`` is defined only for ``done``, so an error that emitted
      partial output before failing shows an ordinary ``Out`` value in the table and is still
      counted dead. The count is a SUPERSET of ⚠EMPTY, never a mirror of it, and that is the
      intended relationship — "produced something before it died" is not "produced something you
      can rely on".
    * it OVER-COUNTS a provider that does not report usage: text and diff present, ``out_tokens``
      absent → 0 → the ticket's rule calls a perfectly good report DEAD. The whole point of this
      count is that a caller must ADJUDICATE a partial batch; a count that cries wolf gets ignored,
      which is the failure mode the reporter is trying to escape.

    So: dead = an ``error``, or no usable payload at all. This is what the ticket ASKS FOR — the
    reporter's line is *"6 of 11 review partitions silently un-swept … an agent that trusted
    '11 dispatched' would have converged on 45% recall"* — and a swept-but-empty partition is
    un-swept however many tokens it burned.

    The rows the ticket pins all still hold: a ``capped`` unit with PARTIAL output is ALIVE (it has
    a payload), an ``out_of_scope`` unit with output is ALIVE (which is why this is not
    ``status != "done"``), and a unit that RECOVERED on the `recover_caps` retry is ALIVE because
    the count runs after the replacement.
    """
    if r.status == "error":
        return True
    return not (_payload_present(r.text) or _payload_present(r.diff))


def _payload_present(v: object) -> bool:
    """Is there something a caller could read? Total — this must NEVER raise.

    ⚠️ `_is_dead_unit` runs at the very END of `fanout`, after every unit has dispatched and been
    BILLED, so anything that raises here discards work the operator already paid for. That is the
    same batch-killer class as T06's degradation label, in the code meant to REPORT on the batch —
    which is exactly why it is guarded rather than reasoned about. `(v or "").strip()` looks safe and
    is not: a non-str truthy payload (a list, an int from a hand-built or vendored-fork
    `AgentResult`) survives the `or` and then `AttributeError`s on `.strip()`. Measured, not feared.

    DIRECTION, stated: a payload we cannot judge counts as PRESENT (alive), never dead. Over-counting
    dead is the cry-wolf failure this whole feature exists to avoid — a count nobody trusts is worse
    than no count — so the unjudgeable case errs toward "there is something here, go look".
    """
    # ⚠️ FALSY FIRST, and this order is the fix for a real hole in the rule below. `b""`, `[]` and
    # `0` are not UNJUDGEABLE — they are judgeably EMPTY, and the earlier `isinstance(v, str)`
    # version fell through to `return True` and called them a payload. A vendored fork that carries
    # `text` as bytes would then have counted every genuinely empty output ALIVE, which is the
    # under-reporting direction this whole feature exists to remove.
    if not v:
        return False
    if isinstance(v, str):
        return bool(v.strip())
    # ⚠️ BYTES ARE STRIPPED TOO, and leaving them out was a real inconsistency with this module's
    # own stated invariant. Round 4 hardened the FALSY half (`b""`, `[]`, `0`) and left
    # truthy-but-BLANK bytes (`b" "`, `b"\n"`) falling through to "present" — so a `done` unit with
    # `text=b" "` counted ALIVE while `AgentResult.empty_output` (which does `(self.text or "")
    # .strip()`) called it ⚠EMPTY. `_is_dead_unit`'s docstring says those two "coincide EXACTLY" for
    # a `done` unit; they did not. Found by the T09 integration pass.
    if isinstance(v, (bytes, bytearray)):
        return bool(v.strip())
    # Truthy and not a str: genuinely unjudgeable → PRESENT. Direction stated above.
    return True


def results_table(entries: list[dict[str, object]], *, dead_units: int | None = None) -> str:
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
    # LOUD, NAMING guard for the measured trap (intel 2026-08-29, `01M17XKJXM`): consumers reach for
    # `results_table(batch.results)`, but `.results` is a list of AgentResults while this wants the richer
    # dict rows (the unit name + your quality verdict + a fixes summary live on the BATCH, not the result).
    # A bare AgentResult has no `.get`, so the old failure was a cryptic `AttributeError('get')` AFTER the
    # spend, naming neither shape. Fail loud + actionable instead — and point at the render that already exists.
    if entries and not isinstance(entries[0], dict):
        raise TypeError(
            f"results_table() wants list[dict] rows with keys (unit, model, result, quality, fixes), "
            f"not a list of {type(entries[0]).__name__}. If you passed a FanoutBatch's `.results`, use "
            f"`batch.table` — it is already rendered for you. `results_table()` is for HAND-BUILT rows that "
            f"add the unit name + your 0–5 quality verdict + a one-line fixes summary the result cannot carry."
        )
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
        # ⚠EMPTY is LOUD and UNMISSABLE: a `done` run with no usable payload. NOT out_tok==0 (a done run
        # can burn max_tokens on reasoning and still emit nothing — out_tok>0, text blank), so it keys on
        # `empty_output`, not the token count. An ⚠EMPTY unit is left UNSCORED, never auto-0'd (intel
        # 2026-08-29) — an empty is usually output-budget burn, so investigate (retry with a larger
        # max_tokens before blaming the model), do not read it as a graded result.
        out = "⚠EMPTY" if bool(getattr(r, "empty_output", False)) else (f"{out_tok / 1000:.1f}k" if out_tok else "—")
        rows.append(
            f"| {e.get('unit', '—')} | {e.get('model', '—')} | {prov} | {cost} | {lat} | "
            f"{out} | {e.get('quality', '—')}/5 | {e.get('fixes', '')} |"
        )
    # ⚠️ T11: a footer line, NOT a column — a column would change the shape of every row in ~48
    # vendored copies and break anything parsing the table. `None` (the default for a hand-built
    # call) renders nothing at all, so an existing `results_table(rows)` is byte-identical.
    # `and entries` because this footer annotates THIS table: with no rows there is nothing to
    # annotate, and the denominator would render the nonsense "3 of 0 unit(s)". `fanout` cannot
    # produce that (the count is derived from the same list the rows are), but `results_table`
    # is PUBLIC and documented for hand-built rows, and this module's rule for that surface is
    # to stay total and render sensibly rather than raise.
    # The leading "\n" is DELIBERATE: it renders a blank line between the table and the footer,
    # which is what closes a markdown table. Without it a renderer can absorb the footer into the
    # table body. Row-counting parsers are unaffected — the footer has no leading `|`.
    if dead_units and entries:
        rows.append(
            f"\n⚠️  {min(dead_units, len(entries))} of {len(entries)} unit(s) returned NOTHING USABLE "
            f"(error, or an empty payload). They are still in `batch.results` — adjudicate the "
            f"batch as PARTIAL rather than reading the dispatch count as coverage."
        )
    return "\n".join(rows)


# ── T05a: the lane walk — rung selection and re-dispatch for a failed fan-out unit ──────────────
#
# ⚠️ `_ROUTABLE_CAUSES` IS AN ALLOWLIST, DELIBERATELY. A cause that `lanes.classify` (or `loop`)
# starts emitting later is NOT routed until someone triages it here. That is the fail-closed
# direction: an un-triaged cause that should route merely leaves the cascade inert for it (today's
# behaviour), whereas an un-triaged cause that should NOT route burns every rung in the chain
# discovering the same answer. A denylist would fail the other way.
#
# The verdict per cause, with the reason — this is the whole design decision, so it is written down
# rather than implied by the set literal:
#
#   * ``rate-limited`` (429, provider-scoped)  — ROUTE. A DIFFERENT provider is precisely the point.
#   * ``unavailable``  (503, provider-scoped)  — ROUTE. The endpoint is down; its siblings are not.
#   * ``model-gone``   (404/410, model-scoped) — ROUTE. The model was pulled or renamed; another
#     model (even on the same provider) is fine, which is why `apply_bench` scopes this to the MODEL.
#   * ``priced-out``   (our own ``provider.max_price`` 404) — ROUTE. OUR ceiling, not the model's
#     fault; a cheaper rung may sit under it.
#   * ``request-too-large`` (413) — ROUTE. Another rung may have a bigger context window.
#   * ``content-stall`` (loop-tagged: the provider accepted, then went silent) — ROUTE. The loop has
#     ALREADY excluded that upstream and retried in-process (`loop.py`'s U2 arm); a different lane is
#     the only move left.
#   * ``auth`` (401/402; scope ``provider``/``key``) — ROUTE, and this is the one worth arguing.
#     Inside an all-OpenRouter batch every rung shares one ``OPENROUTER_API_KEY``, so routing a 402
#     around cannot help — but `SUBAGENT_LANES` is explicitly MULTI-provider ("groq:…,cerebras:…"),
#     and a different provider has a different key and different credit, which is exactly the case a
#     fallback chain exists for. The pointless half is already foreclosed by the applier, not by us:
#     `auth` is PERMANENT, so `apply_bench` benches that provider on the FIRST occurrence and the
#     rung-skip below drops every remaining rung on it without a dispatch. So routing it is
#     *useful across providers* and *free within one* — never "actively wasteful". Not routing it
#     would strand a unit on a spent free tier with a healthy paid lane configured one rung down.
#   * ``error`` (5xx, a transport timeout, or anything unclassified) — ROUTE. A 5xx is genuinely
#     transient and `error` is ALSO the catch-all for connection resets and timeouts — the single
#     most common thing a fallback chain is for. What stops an infinite-ish walk over a systemic
#     fault: this is ONE forward pass over a finite, deduped chain (never a loop), bounded by
#     `SUBAGENT_MAX_FALLBACKS` dispatches AND by one total wall-clock/cost budget for the whole
#     walk. It is the weakest rung in the set precisely because `scope="none"` means it benches
#     NOTHING, so N units each rediscover a systemic outage; the total-wall-clock clamp is what
#     keeps that bounded by the budget the unit already had rather than N × it.
#   * ``bad-request`` (400/422) — **NOT routed.** Our own malformed body 400s IDENTICALLY on every
#     model of every provider, so the walk would burn the whole chain to learn nothing. `classify`
#     reaches the same verdict from the other side and says so at its 400/422 arm ("the cascade then
#     burned each sibling rung rediscovering the same 400"), and it is the same reasoning C3
#     (`58-resilience.md`) applies to 4xx generally.
_ROUTABLE_CAUSES = frozenset(
    {
        "rate-limited",
        "unavailable",
        "model-gone",
        "priced-out",
        "request-too-large",
        "content-stall",
        "auth",
        "error",
    }
)
#: The causes TRIAGED AND REJECTED above. Kept as its own named set (rather than left implicit in
#: the complement) so the drift test can assert every cause the taxonomy can emit has been LOOKED
#: AT — a cause in neither set is one nobody has decided about yet, which is the failure this pair
#: exists to make visible.
_NON_ROUTABLE_CAUSES = frozenset({"bad-request"})

# ⚠️ **T05b's CAP ZERO-RECLAIM WAS REVERTED — read this before re-attempting it.**
#
# The row asked for a rung that never billed to have its cap reservation reclaimed at ZERO instead
# of retaining the estimate. Real problem: `_cap_finalize_once` retains the estimate whenever
# `cost_usd is None`, which under a 5-rung walk books ~$2.00 of phantom spend for an 8-unit batch.
#
# TWO attempts, both wrong, both caught by review:
#   1. "a classified failure with no OUTPUT tokens cannot have billed" — false. The cap books TOTAL
#      spend and most vendors charge for INPUT as soon as the prompt is read.
#   2. "...restricted to gateway-rejection causes, which never reach inference" — also false, and
#      proven by execution. `_client.call_model` restarts up to `restart_max=2` on
#      `(StuckError, TruncatedError, TransientError, HardTimeoutError)`; EACH attempt is a separate
#      BILLED request, and `loop.py` accumulates `total_out_tokens` only from a RETURNED usage, so a
#      discarded attempt contributes 0. Attempt 1 can stream 3000 tokens (billed) and die, attempt 2
#      can be refused by the gateway with a 429 — and the unit then presents as
#      `rate-limited`/`out_tokens=0`/`cost_usd=None`, indistinguishable from a request that never ran.
#
# **The missing signal EXISTS but does not reach here.** `_client.py` records `partial_len` per
# discarded attempt and attaches the chain to the raised exception (`exc.attempts`). Nothing carries
# it through `lanes.classify` -> `FailureCause` -> `LoopOutcome`, so `_run_one` cannot see it. A
# correct fix threads "did ANY attempt stream content" to this seam and requires it; that touches
# `loop.py`/`lanes.py`, outside this ticket's Touches.
#
# **Reverted rather than half-fixed, because the two failure directions are not symmetric:** the
# ratchet OVER-books (the cap trips early — wasteful, safe), while a wrong reclaim UNDER-books (real
# spend invisible, the cap blown — unsafe). For a money path shipping to ~48 vendored copies, the
# safe direction wins until the signal is real.

#: Recovery dispatches ONE unit may make, across the whole walk. 5 is the field norm cited in the
#: design spec's § External grounding. ``SUBAGENT_MAX_FALLBACKS=0`` is a kill switch that disables
#: the walk entirely — INCLUDING the pre-existing same-model second chance, which is rung 1 of the
#: walk (`recover_caps=False` remains the parameter-level off switch).
_DEFAULT_MAX_FALLBACKS = 5
#: A rung with less than this much wall-clock left "cannot fund another attempt" — dispatching it
#: buys a connection that caps before a first token. Applied from the SECOND rung onward only: the
#: first rung is funded by the unit's own budget exactly as the pre-cascade retry always was, so a
#: caller with a deliberately tiny ``wall_clock_s`` keeps today's behaviour.
_MIN_RUNG_WALL_CLOCK_S = 1.0


def _max_fallbacks() -> int:
    """Recovery dispatches allowed per unit (``SUBAGENT_MAX_FALLBACKS``, default 5).

    Read at CALL time, never at import (12F-III). Defensive like `lanes._env_int`: a malformed or
    negative value falls back to the default rather than raising — a typo in a bound must not take
    a fan-out down. ``0`` is a valid, deliberate value (the kill switch).
    """
    raw = os.getenv("SUBAGENT_MAX_FALLBACKS")
    if not raw:
        return _DEFAULT_MAX_FALLBACKS
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return _DEFAULT_MAX_FALLBACKS
    return val if val >= 0 else _DEFAULT_MAX_FALLBACKS


def _cascade_enabled() -> bool:
    """Is `fanout`'s fallback cascade switched ON? (``SUBAGENT_FANOUT_CASCADE``, default OFF.)

    A SECOND switch, required IN ADDITION to ``SUBAGENT_LANES`` — see `_fallback_rungs` for why the
    chain variable alone must not activate it. Read at CALL time, never at import (12F-III).
    """
    return os.getenv("SUBAGENT_FANOUT_CASCADE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _payload_chars(r: AgentResult) -> int:
    """How much USABLE work this result carries: the text a reader grades plus the diff a caller
    applies. Whitespace-stripped, so a result whose "output" is a newline counts as nothing.

    ⚠️ **Chars of payload, NOT ``out_tokens``, and the choice is load-bearing** (review round 2,
    fixup 3). ``out_tokens`` is PROVIDER TELEMETRY, and the providers a fallback chain routes to are
    exactly the ones that omit it — `loop.py:450-452` has to inject ``stream_options
    {"include_usage": True}`` for non-OpenRouter endpoints precisely because they do not send usage
    unless asked, and the module already documents that an unreported usage dict leaves this at 0.
    Judging "did this rung do better" on a field a free lane routinely reports as 0 would rank every
    such rung below a reporting incumbent and discard genuinely better work. It is also the WRONG
    UNIT for a ``mode="write"`` unit, whose deliverable is the diff and which has no token count for
    it at all. ``out_tokens`` is kept only as a tiebreak, below, where it cannot outrank payload.
    """
    return len((r.text or "").strip()) + len((r.diff or "").strip())


def _usable_payload_chars(r: AgentResult) -> int:
    """`_payload_chars`, except that an UN-APPLIABLE result is worth ZERO.

    ⚠️ **ROUND 5, C1 — the root fix that F4 and round-5/A were both circling.** Both were written
    as a VETO on `out_of_scope` REPLACING something, which left the other direction open: with a
    zero-payload origin (the canonical capped+0 shape) the guard is correctly silent, the refusal
    BECOMES the incumbent, and its 6000 chars of explanation are then what every later rung must
    beat — so a rung returning a real 200-char diff lost, and the unit's verdict was the refusal
    with ``diff=""``. Measured: the coder's patch discarded on rung 2 of 2.

    `out_of_scope` text is the scope guard's own message about work it DELIBERATELY WITHHELD
    (`:1597`); there is nothing in it a caller can apply. Counting it as zero states that once, in
    the unit both comparisons share, instead of as a growing list of vetoes.
    """
    return 0 if r.status == "out_of_scope" else _payload_chars(r)


def _replaces(cand: AgentResult, incumbent: AgentResult) -> bool:
    """May this rung's result REPLACE the failed original?

    ⚠️ **ROUND 9 — REWRITTEN AS ONE STATED POLICY, because patching it locally was the ticket's
    single largest defect source.** Rounds 4, 5, 6, 8 and 9 each fixed a case here, and FOUR of
    those fixes were themselves defective, because the ticket never specified how to rank a
    COMPLETED-but-small result against a TRUNCATED-but-large one. Three rounds encoded three
    incompatible answers (R4/F2: payload wins · R5/B: a losing `done` must not end the walk ·
    R9/F3: four working `done` lanes discarded and the verdict left `capped`). R9/F3 is the direct
    consequence of R5/B, which is the direct consequence of R4/F2. So the policy is written down
    ONCE, here, and the code is its direct expression:

    1. A rung that **COMPLETED** (`done`) with usable payload is a SUCCESS: it wins, and it ends
       the walk — **UNLESS** the incumbent carries a larger ``diff``. In ``mode="write"`` the diff
       IS the deliverable and must never be traded for prose (R4/F2, R6/C1).
    2. Otherwise the larger USABLE payload wins, with ``out_tokens`` only as a tiebreak.
    3. ``out_of_scope`` carries ZERO usable payload (`_usable_payload_chars`) and can never win —
       including on a tiebreak, which is how R9/F6 slipped a refusal past an empty incumbent.

    This DELIBERATELY overrules the expectation `test_a_done_rung_that_loses_does_not_end_the_walk`
    asserted in round 5. Under the stated policy a completed answer beats a truncated one in read
    mode, so that rung SHOULD win and SHOULD stop the walk. The old expectation encoded a policy
    that had never been stated, and keeping both was the contradiction generating the defects.

    ⚠️ **THE MIRROR, MEASURED — not "exactly one sub-case", which is what this said before round 11
    counted them.** Executed with BOTH env vars unset, HEAD against `git show main:`, over 8 origin
    shapes x 11 rung-answer shapes = **88 cells: 79 identical, 9 divergent, and the DISPATCH COUNT
    is identical in all 88** — no unit gains or loses a retry. All 9 differ only in WHICH result is
    kept, and each is a deliberate policy decision above:

    - **4 cells** (any origin x an `out_of_scope` rung): `main` installs the refusal as the unit's
      verdict; here it can never win (rule 3). A consumer reading `status` sees `capped` where
      `main` said `out_of_scope`, and the honest verdict is the congestion, not the accusation.
    - **4 cells** (a partial-payload origin x a `done` rung that produced less): `main` adopts the
      `done` on `out_tokens > 0 or status == "done"`; here the larger payload survives (rules 1-2).
    - **1 cell** (a 300-char-diff origin x a `done` carrying a 200-char diff): `main` takes the
      smaller diff; rule 1 keeps the larger.

    A consumer relying on *"the retry's result always replaces a zero-output cap"* gets the ORIGINAL
    back whenever the retry produced strictly less. The surviving discriminator is that the
    original's ``text``/``diff`` are non-empty. For the canonical case — a zero-output cap with EMPTY
    text and diff, the only shape reachable with no chain configured AND no partial output — this is
    byte-identical to the pre-change test.
    """
    if cand.status == "out_of_scope":
        # Rule 3: an un-appliable result is worth zero. `>` (never `>=`) so it cannot win a TIE.
        return _usable_payload_chars(cand) > _usable_payload_chars(incumbent)
    if cand.status == "done" and _usable_payload_chars(cand) > 0:
        # Rule 1: a success wins on KIND, but may not shed a larger diff.
        return len((cand.diff or "").strip()) >= len((incumbent.diff or "").strip())
    if cand.status == "done":
        # an EMPTY `done` may only fill a result that produced nothing at all
        return _usable_payload_chars(incumbent) == 0
    # Rule 2.
    return (_usable_payload_chars(cand), cand.out_tokens) > (
        _usable_payload_chars(incumbent),
        incumbent.out_tokens,
    )


#: Body keys a rung must not inherit: the three that decide WHICH upstream or model serves the
#: request — i.e. the only ones that fight the cascade's own job.
#:
#: ⚠️ **T05b ROUND 2 — THIS SET WAS TOO BIG, AND ITS CITATION WAS MISATTRIBUTED.** It also listed
#: `transforms`, `response_format`, `logit_bias`, `stream_options` and `reasoning`, citing
#: `providers.py:130-131`. Those lines say, verbatim, *"an unknown `provider` object is ignored at
#: best and a 400 at worst"* — a claim about the **`provider` object alone**. One citation was
#: carrying five keys it does not cover. Measured consequences of the over-drop:
#:   * `response_format` is a FIRST-CLASS parameter of this module's own transport
#:     (`_client.py:338`, set at `:358`). Dropping it made a rung return prose where the caller
#:     demanded JSON — no error, no log line, the caller's parser blaming the model. That is exactly
#:     the *"a DROPPED knob fails QUIETLY, the worse failure"* class this filter's first version was
#:     rewritten to avoid.
#:   * `stream_options` is INJECTED by `loop.py:451-452` for non-OpenRouter providers precisely
#:     because their streams report no usage without it — and that line says *"a caller-set
#:     stream_options still wins"*. Dropping the caller's was backwards.
#:
#: **Residual, stated rather than implied away:** a CARRIED vendor-specific key that a lane rejects
#: with a 400 is `bad-request`, which T05a's C3 treats as a chain-ending veto — so one bad key can
#: still cost the rest of the chain. That is the LOUD failure, and it is the one the operator can
#: see and fix; the alternative is silently different output. `README.md` § Gotchas carries it.
_RUNG_DROPPED_BODY_KEYS = frozenset({"provider", "models", "route"})

# Degradation kinds whose `reason` is drawn from a CLOSED set and so may enter the
# batch-summary group key. `unit-exhausted` is deliberately absent: its reason is prose.
_REASON_KEYED_KINDS = frozenset({"rung-skipped"})


def _rung_body(spec_body: dict[str, object] | None) -> dict[str, object] | None:
    """The unit's ``body`` as a DIFFERENT model may receive it.

    Drops only the routing directives (`_RUNG_DROPPED_BODY_KEYS`): `provider` pins an upstream
    chosen for the ORIGINAL model, and `models`/`route` are OpenRouter's own fallback machinery,
    which would fight this cascade for control of what runs. Everything else is the caller's
    semantic intent — sampling knobs, response shape, per-model required hints — and is CARRIED,
    because losing it is silent while a rejection is loud.

    ⚠️ Callers get this ONLY on a real model swap; see `_walk_lanes`, which does not filter the
    origin's own retry.
    """
    if not spec_body:
        return spec_body
    kept = {k: v for k, v in spec_body.items() if k not in _RUNG_DROPPED_BODY_KEYS}
    return kept or None


def _rung_is_free(provider: str) -> bool:
    """Is this rung's provider a free tier — i.e. can a dispatch to it spend money?

    ⚠️ **ROUND 9, F2.** Unknown provider -> ``False`` (assume it meters): an unknown spend must not
    be assumed to be the cheapest possibility, which is `_rung_cost`'s own stated doctrine.
    """
    try:
        return bool(resolve_provider(provider).free_tier)
    except ValueError:
        return False


def _rung_cost(cand: AgentResult | None, provider: str, budget_left: float | None) -> float:
    """What to CHARGE this rung against the walk's ONE cost total.

    ⚠️ **REVIEW ROUND 2, FIXUP 4 — a bare ``cand.cost_usd or 0.0`` made the cost budget VOID.**
    `loop._finish` reports ``cost_usd=None`` whenever the provider sent no in-stream cost, so
    against a cost-silent endpoint the decrement never fired and every rung was handed the FULL
    budget: five rungs at $0.50 each where the caller asked for $0.50 total, i.e. a worst case of
    ``(1 + max_fallbacks) × X`` against a pre-cascade ``2 × X``.

    The rule, and note it is assembled from decisions this module has ALREADY made rather than
    invented here:

    * a REPORTED cost is charged as reported;
    * an UNKNOWN cost on a ``free_tier`` endpoint is charged **$0.00** — the registry row means
      "bills $0 for ALL runs, including a hung one", and `_attribute_provider` (`agent.py:1679`) and
      `lanes.py:828` already convert exactly this None into exactly this zero. In practice a
      dispatched free-tier rung has already been normalised to 0.0 before the walk sees it; this
      arm covers the pre-dispatch-refusal shape, which `_attribute_provider` never touches;
    * an UNKNOWN cost on a METERED endpoint is charged the **whole remaining budget**, which zeroes
      the remainder and ENDS the walk. This is `_cap_finalize_once`'s principle verbatim — *"an
      unknown spend must not be assumed to be the cheapest possibility"* (`agent.py:1154-1155`) —
      and the two options the review offered converge here rather than competing: the module's own
      estimator, `_cap_estimate`, returns ``spec.max_cost_usd`` whenever the caller set one, and the
      rung's ``max_cost_usd`` IS the remainder, so "charge the caller's estimate" and "stop the walk
      when cost is unknowable" are the SAME number. Charging it is the honest framing of both.

    The cost of the metered arm is small and worth naming: the realistic chain population is free
    tiers (that is what `lanes.py` is for), which take the $0 arm and keep walking. The residual is
    the reverse: a rung that never dispatched (a pre-flight refusal on a METERED provider) is
    charged the estimate for a run that spent nothing, ending the walk early. That errs toward the
    budget, which is the direction a spend guard must err.

    ``budget_left is None`` means the caller set no ``max_cost_usd`` at all, so there is no cost
    total to charge against and the return value is never read — 0.0 keeps the accumulator honest.
    """
    # ⚠️ **ROUND 8, F2 — `cand is None` means the rung RAISED, and a raise is the most unknown
    # spend there is.** Round 7's guard skipped this call entirely on the exception path, so a rung
    # that raised AFTER the transport billed was charged $0.00 and the next rung was handed the
    # caller's full cap again — measured 5 rungs x $0.50 = $2.50 against a $0.50 ceiling. That is
    # precisely the assumption this function exists to forbid, arriving through the new arm.
    if cand is not None and cand.cost_usd is not None:
        return cand.cost_usd
    try:
        if resolve_provider(provider).free_tier:
            return 0.0
    except ValueError:
        pass  # unknown provider — the `replace` guard owns that case; charge conservatively below
    # ⚠️ **ROUND 9, F2 — this used to return `budget_left`, charging the whole remainder as a
    # placeholder for an unknown metered spend. It ended the walk for EVERY later rung, free lanes
    # included. The pessimism now lives in `_walk_lanes`' `metered_unknown` flag, which bars further
    # METERED rungs only; a charge must reflect money, not caution.
    return 0.0


def _rung_credential_missing(provider: str) -> bool:
    """Is this rung's API key absent, so dispatching it can only fail for a config reason?

    ⚠️ **REVIEW ROUND 2, FIXUP 6.** A rung whose key is unset raises a STATUS-LESS ``ConsultError``
    from `_transport._resolve_client` (`_transport.py:136-141`), which `lanes.classify` can only
    flatten to the ``error`` catch-all — ``scope="none"``, so it benches NOTHING and is re-dialled
    by every unit of every batch, forever, at first-token-timeout cost each. A one-character typo in
    `SUBAGENT_LANES` is otherwise silently permanent. The transport's own message already draws the
    distinction the cascade was discarding: *"This is an env/onboarding gap, NOT 'the provider is
    unavailable'."*

    Checked BEFORE the dispatch and from the REGISTRY (``key_env`` / ``key_optional``), never by
    matching the failure's message: the fact is knowable for free, and a rung skipped here costs
    nothing at all rather than one wasted call per unit. ``key_optional`` providers (Kilo's
    anonymous ``:free`` tier) are exempt — an absent key is a supported mode for them.

    ⚠️ **The empty-``key_env`` guard is HARDENING, not a live bug, and both halves of that matter.**
    All seven shipped registry rows carry a non-empty ``key_env`` and the field is annotated ``str``,
    so `os.getenv(cfg.key_env)` cannot raise here TODAY. It is guarded anyway because (a) this module
    ships by being COPIED into ~48 repos and ``providers._REGISTRY`` is a module-level dict a
    vendored copy can add a row to, while Python enforces no annotation; and (b) this runs INSIDE
    the recovery path, where `_run_one`'s contract is *"must NEVER raise into the batch"* — a
    ``TypeError`` from `os.getenv(None)` would not degrade one rung, it would sink the unit. A row
    with no key env names a provider that needs no key, which is the ``key_optional`` answer.
    """
    try:
        cfg = resolve_provider(provider)
    except ValueError:
        return False  # an unknown provider is the `replace` guard's case, not this one
    if cfg.key_optional or not cfg.key_env:
        return False
    return not (os.getenv(cfg.key_env) or "").strip()


def _fallback_rungs() -> tuple[list[tuple[str, str]], bool]:
    """The ordered ``(provider, model)`` rungs a failed unit may advance to — ``[]`` when the
    cascade is not configured.

    ⚠️ **INERT-SAFE IS A HARD RULE HERE.** `lanes._resolve_chain` RAISES when no chain is
    configured — correct for `lane_chain`, whose whole job is the chain, and fatal for `fanout`,
    whose job is the batch. With `SUBAGENT_LANES` unset this returns ``[]`` and `fanout` behaves
    exactly as it did before the cascade existed: no probe, no bench write, nothing raised. A
    resilience feature whose UNCONFIGURED state is a crash is a regression in every one of the ~48
    repos that vendor this module, none of which set the variable.

    A MALFORMED chain is the second raise site (`_resolve_chain` calls `resolve_provider` for the
    WHOLE chain, so one bad provider name fails at parse time rather than per-rung). It degrades to
    "no cascade" with a loud warning rather than sinking a batch whose results are already in hand —
    the batch's completed work is worth more than the misconfigured recovery.
    """
    if not _cascade_enabled():
        # ⚠️ REVIEW ROUND 2, FIXUP 7 — THE BLAST RADIUS, and the reason `SUBAGENT_LANES` alone is
        # NOT the switch. `README.md:645` documents that variable as "Default chain for
        # `lane_chain`", which is the only reason any existing consumer has ever set it; `lanes.py`
        # § "When NOT to use it" says those lanes are FREE TIERS for dev/eval/batch work and "not a
        # production request path" (NVIDIA's is ToS-restricted to internal testing); and `fanout`
        # HARD-REFUSES a non-OpenRouter `provider` in `**spec_kwargs` a few dozen lines below.
        # Activating off `SUBAGENT_LANES` alone would therefore make an operator's PRE-EXISTING env
        # var silently achieve, on upgrade and with no opt-in, exactly what this function's own API
        # refuses: `mode="write"`, `tools_enabled=True` coding agents routed onto free,
        # ToS-restricted lanes. So the cascade needs its OWN switch, and with it unset every one of
        # the ~48 vendored copies keeps today's same-model retry, chain or no chain. SILENT here on
        # purpose — a log line would fire on every batch in every repo that set the chain for
        # `lane_chain`, which is the population this guard exists to leave alone.
        return [], False
    if not os.getenv("SUBAGENT_LANES", "").strip():
        # The opt-in IS set and there is no chain to walk — that is a misconfiguration nobody can
        # see from the outside, and warning about it cannot reach a consumer who never opted in.
        logger.warning(
            "fanout: SUBAGENT_FANOUT_CASCADE is on but SUBAGENT_LANES is empty — there are no "
            "fallback rungs to walk, so recovery is the same-model second chance only. Set "
            "SUBAGENT_LANES to a comma-separated 'provider:model' chain, or unset the opt-in."
        )
        return [], False
    try:
        # Reuse `lanes`' own parser: it splits `provider:model` on the FIRST colon only (free model
        # ids legitimately contain one), validates every provider against the registry, and dedups
        # to the first (best) position. Re-implementing any of that here is how the two drift.
        chain = lanes._resolve_chain(None)
    except Exception as exc:  # noqa: BLE001 — a bad chain must never sink a completed batch
        logger.warning(
            "fanout: SUBAGENT_LANES is misconfigured (%s) — the fallback cascade is DISABLED for "
            "this batch; results are unaffected. Fix the chain to re-enable rung recovery.",
            exc,
        )
        return [], False
    # ⚠️ **ROUND 10, F3 — the SECOND element says a chain actually RESOLVED, and it is NOT
    # `bool(rungs)`.** Two different things produce an empty rung list and they need OPPOSITE
    # answers: a chain that resolved but whose every rung was dropped for a missing key must keep
    # the cascade ON (R6/C2 — deriving it from `bool(rungs)` silently killed the ORIGIN bench, so
    # every unit re-dialled a provider that had just returned a permanent 401), while NO chain at
    # all — unset, empty or malformed — must leave NO TRACE, which is exactly what the warning
    # above promises when it says the cascade is DISABLED. `fanout` computed `cascade_on` from the
    # env var alone, so a malformed chain still wrote process-global bench state that `lane_chain`
    # reads, and still applied the `bad-request` veto that costs a unit its same-model retry — in a
    # state with nothing to walk, so the veto bought nothing and cost a dispatch.
    return [(provider, model) for provider, model, _cap in chain], True


def _re_routable(r: AgentResult, *, cascade: bool) -> bool:
    """Is this failed unit worth another rung?

    ``r.failure is not None`` IS the discriminator, and it is the reason T02b is a hard dependency
    of the walk rather than a convenience. A TRANSPORT failure carries a `lanes.FailureCause`; a
    STRUCTURAL refusal (sandbox unavailable, an ungrounded single-shot, a worktree failure, the
    NVIDIA non-tool-caller refusal) carries ``failure=None`` because it never reached the transport
    at all. The module already decided the second must never be retried — "a retry can't fix a
    host/config problem and would burn the pool" — and a bare ``status == "error"`` test cannot tell
    the two apart.

    The second arm is today's gate, unchanged: a ZERO-OUTPUT cap is provider CONGESTION, not model
    quality. It is an OR, not an ``elif``, deliberately — narrowing it to "only when `failure` is
    None" would drop a capped, zero-output unit whose cause happens to be routable-but-unlisted.

    ⚠️ **REVIEW ROUND 2, FIXUP 1 — THE ALLOWLIST HAS TO VETO *BOTH* ARMS, and guarding only arm 1
    was a real hole, not a theoretical one.** A 400 raised after the unit's wall clock is spent does
    NOT arrive as ``status == "error"``: `loop._transport_failure` (`loop.py:507-508`) turns a
    budget-exhausted transport failure into ``_finish(text, "capped", failure=_safe_classify(exc))``
    — i.e. ``status="capped", out_tokens=0, failure.cause="bad-request"``. Arm 2 then fired
    regardless of the allowlist and the walk dialled the origin plus every rung, which is verbatim
    the waste `_NON_ROUTABLE_CAUSES` exists to prevent. Proved by execution against a real
    `run_loop`, not against a fixture: four rungs dialled for one malformed body. So a TRIAGED-OUT
    cause is a veto over the whole predicate, evaluated first.
    """
    if cascade and r.failure is not None and r.failure.cause in _NON_ROUTABLE_CAUSES:
        # ⚠️ **ROUND 9, F1 — THE VETO IS CASCADE-GATED, and leaving it ungated broke INERT-SAFETY.**
        # Round 8 swept the in-walk BREAK for cascade-gating and left this ENTRY predicate ungated,
        # so a `capped`+0 origin whose cause is `bad-request` (the shape `loop.py:507-508` produces
        # from a budget-exhausted 400) lost its same-model retry with BOTH env vars unset: `main`
        # dispatches twice, HEAD dispatched once. Measured 24 divergent cells of 96 in the
        # origin x rung-answer cross product.
        #
        # This SUPERSEDES the third deviation recorded in D-094, which reasoned that the retry was
        # "always a wasted dispatch" and accepted the change. That reasoning is sound about COST and
        # wrong about PRECEDENCE: `_walk_lanes` already states that inert-safety outranks a tighter
        # reading of C3, and ~48 vendored copies upgrade into exactly this unconfigured state. With
        # the cascade ON the triage still applies and a 400 buys no rungs; with it OFF the unit gets
        # the same second chance it gets today.
        return False
    return (r.failure is not None and r.failure.cause in _ROUTABLE_CAUSES) or (
        r.status == "capped" and r.out_tokens == 0
    )


def _unit_label(spec: AgentSpec) -> str:
    """A short, ALWAYS-SAFE label for a unit in a degradation event.

    ⚠️ **T06 REVIEW ROUND 2 — `spec.task[:80]` was a batch-killer, and it was mine.** `AgentSpec.task`
    is annotated `str`, but `fanout` reads a dict unit's task through `cast(str, unit["task"])` — a
    type-checker hint, NOT a runtime check — so a caller passing `{"task": None}` reaches here with
    `None` and the slice raises `TypeError` straight out of `fanout`, discarding every unit's
    results INCLUDING the ones already dispatched and PAID for. Measured, not reasoned.

    That is verbatim the failure this module records at `_cap_acquire` ("raising here killed the
    ENTIRE batch"), reintroduced by the observability code meant to prevent silent loss. A label for
    a log line must never be able to cost a batch, so it coerces instead of assuming.
    """
    task = getattr(spec, "task", None)
    if isinstance(task, str):
        return task[:80]
    # ⚠️ **ROUND 3 — `repr(task)` was a SECRET-LEAK path, and it was round 2's own fix.** A repr
    # carries whatever the object holds: a caller passing an object with an `api_key` attribute got
    # it written verbatim into a degradation event, which is exactly what this module forbids
    # ("keys must never reach a log, a ledger row, an error message or a dossier"). I chose `repr`
    # for diagnostic richness and handed it a leak. The TYPE is what an operator needs to fix a
    # malformed unit; the CONTENTS are what they must not receive.
    return f"<non-str task: {type(task).__name__}>"


#: ⚠️ **THE HOOK-SAFETY POLICY, STATED ONCE — because patching it instance-by-instance produced
#: FIVE consecutive defects, each inside the fix for the one before it.**
#:
#:   round 1  the label `spec.task[:80]` raised TypeError out of `fanout` on a malformed unit,
#:            discarding results already dispatched and PAID for;
#:   round 2  the fix's `dict(event)` was SHALLOW, so a caller could still mutate the
#:            `never_dialled` LIST in place and reach the batch's stored copy;
#:   round 3  the fix's `repr(task)` fallback wrote an object's contents — including a live
#:            `api_key` — into a degradation event;
#:   round 3  `on_exhausted` received the LIVE `AgentResult` and could rewrite what the caller
#:            got back;
#:   round 3  and the snapshot that fixed THAT broke identity against `batch.results`, which is a
#:            contract change owed to ~48 vendored copies.
#:
#: **The policy, from which each of those follows:** a caller-supplied hook is UNTRUSTED CODE
#: running inside a batch that has already been dispatched and PAID for. It must not be able to
#: (a) RAISE into it, (b) MUTATE anything the caller will later read, or (c) RECEIVE anything the
#: module would not put in a log. Therefore every hook gets: its own dict, its own copy of every
#: CONTAINER value in that dict, a snapshot of any dataclass, a label that names a TYPE rather than
#: reprs an object, and a `try/except Exception` around the call. When adding a hook or a field to
#: an existing one, satisfy all five — do not reason about which apply.
#:
#: **How to check, rather than assume:** enumerate the value types by introspection
#: (`{k: type(v).__name__ for k, v in event.items()}`) and the dataclass fields by
#: `dataclasses.fields(...)`. Round 2's shallow copy and round 3's `tool_calls` alias were both
#: "I copied the container I was thinking about"; the enumeration is what makes the claim checkable.
#:
#: **SCOPE, AUDITED — the three CALLER-SUPPLIED hooks that reach `fanout`, not "every callback".**
#: The first draft of this note said "every hook", which was a sweeping phrase written before it was
#: checked. Audited:
#:   * `on_progress` — own dict (`{**ev, "agent_id": …}` at `:1504`) and guarded downstream at
#:     `loop.py:683`, whose comment already says "Guarded so a bad callback can never crash the
#:     agent loop". Pre-dates this ticket and complies.
#:   * `on_degrade`  — own dict + copied containers via `_own`, wrapped here.
#:   * `on_exhausted` — own dict, fresh `never_dialled`, dataclass SNAPSHOT, wrapped.
#: DELIBERATELY OUT OF SCOPE: `_client._emit`'s `cb(event, model, attempt)` is unguarded, but it is
#: internal plumbing carrying three scalars — not a caller-supplied hook reaching `fanout`, and not
#: this module's surface to widen. Named here so the omission is a decision rather than an oversight.
def _emit_degradation(
    events: list[dict[str, object]],
    sink: Callable[[dict[str, object]], None] | None,
    **event: object,
) -> None:
    """Record ONE degradation on the batch, and hand it to the caller's sink.

    See the HOOK-SAFETY POLICY note above this function — it is the rule this obeys.

    ⚠️ **stderr, NEVER stdout, NEVER a file.** `fanout`'s write-mode notice a few hundred lines
    below states the rule and its cost: this module ships into ~48 repos, so a `print` here is *"a
    gate failure in every one of them, for a warning that is not even theirs"*, and
    `core/10-python.md` bans a file handler outright. `_client._emit` follows the same rule.

    ⚠️ **The default is deliberately NOT one line per event.** D-041's reading (B) asks for every
    degradation to be visible, and a channel that emits three lines for a batch that re-routed twice
    is one people learn to ignore — the exact failure the requirement exists to prevent, arriving by
    another road. So: the EVENT is always recorded on `batch.degradation_events` (detail on demand,
    and what a caller's `on_degrade` receives), while the DEFAULT stderr output is ONE aggregated
    line per batch, emitted by `_flush_degradations` at close. Aggregation is the mitigation, not
    silence.
    """
    # ⚠️ **T06 REVIEW ROUND 1 — the sink gets its OWN dict, and so does the batch.** Three finders
    # converged on this: handing the SAME object to the caller and storing it meant a logging
    # callback could silently rewrite what `batch.degradation_events` later reports. This module
    # already wraps both hooks so they cannot RAISE into a batch that has been paid for; being able
    # to MUTATE it is the same exposure by another route, and the symmetric protection is one
    # `dict()` per call.
    def _own(e: dict[str, object]) -> dict[str, object]:
        # ⚠️ **ROUND 2 — `dict(event)` is SHALLOW and one value is a LIST.** Round 1 closed the
        # dict-REBINDING vector and left the list-MUTATION one open: a caller doing
        # `ev["never_dialled"].append(...)` still reached the batch's stored copy. PROVED by
        # execution before it was fixed — `['INJECTED-BY-CALLER']` appeared in both stored events.
        # Same "fixed the instance, missed the neighbourhood" shape this plan keeps producing, so
        # copy the containers too. Values are str/int/list-of-str; no deeper nesting exists.
        return {k: (list(v) if isinstance(v, list) else v) for k, v in e.items()}

    events.append(_own(event))
    if sink is not None:
        try:
            sink(_own(event))
        except Exception as exc:  # noqa: BLE001 — a caller's sink must never sink the batch
            logger.warning(
                "fanout: on_degrade raised %s: %s. The event is still on "
                "batch.degradation_events; the batch is unaffected.",
                type(exc).__name__,
                exc,
            )


def _flush_degradations(
    events: list[dict[str, object]], sink: Callable[[dict[str, object]], None] | None
) -> None:
    """ONE aggregated structured line on stderr per batch — suppressed when the caller took the sink.

    A caller who passed `on_degrade=` has already received every event and does not need the module
    writing to their stderr as well.
    """
    if not events or sink is not None:
        return
    # ⚠️ **ROUND 7 — group by (kind, REASON) where the reason is enumerable.** Grouping on `kind`
    # alone reported `rung-skipped=3` whether all three lanes were BENCHED or one was benched and
    # two were missing credentials — and those demand opposite operator actions (wait/unbench vs
    # provision a key). A summary that cannot distinguish the actions it should trigger is the
    # "line people learn to ignore" arriving by another road, which is the same defect the stop
    # reason went through four rounds to fix. Only `rung-skipped` has a short enumerable reason;
    # `unit-exhausted` carries a full sentence, so it stays grouped by kind alone.
    # Group by what changes the ACTION, not by every field. "rung-skipped=3" reads
    # identically whether the lanes were benched (wait) or keyless (provision a key), so
    # that kind carries its reason. "unit-exhausted" does NOT: its reason is a free-form
    # stop sentence (see the reason=stop_reason emission below), and keying on it would
    # make the group set unbounded and the summary one line per unit. Any NEW kind that
    # joins the reason key must have an ENUMERABLE reason, or this line stops summarising.
    kinds: dict[str, int] = {}
    for e in events:
        kind = str(e.get("kind", "?"))
        key = f"{kind}/{e.get('reason')}" if kind in _REASON_KEYED_KINDS else kind
        kinds[key] = kinds.get(key, 0) + 1
    detail = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
    sys.stderr.write(
        f"⚠️  fanout: {len(events)} degradation event(s) this batch ({detail}). "
        "Read batch.degradation_events for the per-unit detail, or pass on_degrade= to take "
        "them yourself.\n"
    )


def _drop_keyless_rungs(rungs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Drop rungs whose provider key is unset, warning ONCE PER RUNG for the whole batch.

    ⚠️ **REVIEW ROUND 4, F6.** The check used to live only inside `_walk_lanes`, which runs once
    per FAILED UNIT — so two keyless rungs across six failed units emitted TWELVE lines carrying
    two distinct facts. `fanout` documents exactly this shape as a defect a few hundred lines
    below (the once-per-batch recording warning: *"12 identical lines … train the reader to ignore
    them"*), and this function was violating its own neighbour's standard. The rung list is
    computed ONCE per batch and the condition is a pure env read, so the duplication was
    deterministic, not incidental.
    """
    kept: list[tuple[str, str]] = []
    for provider, model in rungs:
        if _rung_credential_missing(provider):
            logger.warning(
                "fanout: skipping fallback rung %s:%s for this batch — %s is not set. This is an "
                "env/onboarding gap, not a provider outage: a keyless dispatch fails with a "
                "status-less error that benches nothing, so every unit would re-dial it forever.",
                provider,
                model,
                resolve_provider(provider).key_env,
            )
            continue
        kept.append((provider, model))
    return kept


def _walk_lanes(
    spec: AgentSpec,
    result: AgentResult,
    *,
    repo: str,
    rungs: list[tuple[str, str]],
    max_fallbacks: int,
    cascade: bool,
    events: list[dict[str, object]] | None = None,
    on_degrade: Callable[[dict[str, object]], None] | None = None,
    on_exhausted: Callable[[dict[str, object]], None] | None = None,
) -> AgentResult:
    """Walk the rungs for ONE failed unit and return the recovered result, or ``result`` unchanged.

    **Rung 1 is the SAME (provider, model)** when — and only when — the unit hit today's
    zero-output congestion cap. That is not a special case bolted on: it IS the pre-cascade
    behaviour expressed as a rung, which is what makes the unconfigured path structurally identical
    to the old code rather than identical by inspection.

    ⚠️ **C3 AND THE ORIGIN RUNG — the honest version (review round 2, fixup 2).** This docstring
    used to claim the arm "cannot violate" C3's ban on re-dialling a rung that answered a 4xx,
    "because a 4xx never arrives as ``status == "capped"``". **That claim is false**, and a future
    editor would have relied on it: `loop._transport_failure` turns a budget-exhausted transport
    failure into a CAP carrying the classified cause (`loop.py:507-508`), and the finalize arm does
    the same (`loop.py:787`). So a 4xx-caused ``capped`` with zero output DOES exist, and for the
    causes that bench nothing (``request-too-large``, ``priced-out``) or a sub-threshold transient,
    the origin IS re-dialled exactly once. ``bad-request`` is no longer among them — `_re_routable`
    now vetoes it on both arms — and the behaviour is UNCHANGED from before this ticket (the
    pre-cascade retry did the same), so it is a residual, not a regression: one extra attempt on the
    unit's own model, bounded at one, which is the price of keeping the unconfigured path identical.
    Narrowing it would change behaviour for consumers with no chain configured, and inert-safety
    outranks a tighter reading of C3 here. C3 still binds the part that is this ticket's to control:
    the walk never re-dials a CHAIN rung it has already dialled.

    **Rungs are SEQUENTIAL within a unit** — hedging a saturated pool amplifies load. Recovery is
    also SERIAL ACROSS units (this is a synchronous ``for`` inside a synchronous ``fanout``), and
    that is a stated cost, not an oversight: parallel unit recovery needs threads or a move into
    ``arun_agents``. It is exactly why the wall-clock clamp below is not optional — F serially
    recovering units after the batch has finished is the shape that produces a hung batch.

    **The walk WRITES the bench, it does not only read it.** `lanes._bench` has ONE call site,
    inside `lane_chain`, which `fanout` never calls — so without the `apply_bench` below the bench
    stays empty for the life of the process, the rung-skip never skips, and every unit
    independently rediscovers the same dead lane up to N × ``max_fallbacks`` times. The cascade
    would AMPLIFY the waste it exists to remove.

    ⚠️ **The bench key is `AgentSpec.provider` — the REQUEST provider — never a provider read off a
    result.** ``AgentResult.provider`` is the SERVED upstream ("Fireworks", "Together"); the bench
    maps and `bench_remaining` are keyed by the REGISTRY name ("openrouter", "groq"). Benching the
    served name writes ``_bench_provider["Fireworks"]`` while ``bench_remaining("openrouter")`` stays
    0.0 forever — a silent no-op bench, after which the walk re-dials a rung it believes it benched.

    **The threshold is `lanes`'.** This function never counts failures; `apply_bench` owns the
    grace period (`_DEFAULT_FAIL_THRESHOLD`, `SUBAGENT_LANE_FAIL_THRESHOLD`) and the permanent-vs-
    transient split. Duplicating that counting here is how the two would disagree about when a lane
    is dead.

    **Budgets: ONE total across rungs for BOTH axes** — each rung is handed the REMAINDER, and the
    walk stops when the remainder cannot fund another attempt. ``max_turns`` stays PER-RUNG: it
    bounds one agent's reasoning depth, and a fresh rung needs its own turns to do the work at all.
    The time axis bites everyone — ``max_cost_usd`` defaults to ``None`` (opt-in) but
    ``wall_clock_s`` defaults to 1800.0, so five unclamped rungs is 2.5 hours after the batch has
    already finished. Residual, stated rather than implied away: the total is across the WALK, not
    across the unit — the original dispatch had its own budget and is not charged against this one,
    which is precisely what keeps the unconfigured same-model retry identical to today's.
    """
    # ⚠️ **ROUND 5/C2 — `cascade` is PASSED, never derived from `bool(rungs)`.** Round-4's F6 moved
    # the keyless-rung filter to batch level, which can legitimately EMPTY `rungs` — precisely the
    # onboarding gap `_drop_keyless_rungs` exists to describe. Deriving the flag from the list then
    # silently switched the ORIGIN bench off too, so every unit re-dialled a provider that had just
    # returned a PERMANENT 401 (measured: 8 dispatches and a 0.0s bench where the pre-F6 call site
    # gave 4 and 900s). "Is the cascade on" and "did any rung survive filtering" are two different
    # questions, and only the first may gate the bench write.
    origin = (spec.provider, spec.model)
    plan: list[tuple[str, str]] = []
    if result.status == "capped" and result.out_tokens == 0:
        plan.append(origin)
    # C3: a failure caused by a 4xx may only ADVANCE to a different rung, never re-dial the one
    # that answered. The chain is already deduped by `_resolve_chain`, so dropping the origin is
    # the only repeat left to drop.
    plan.extend(rung for rung in rungs if rung != origin)

    if max_fallbacks <= 0:
        # ⚠️ **ROUND 5/LOW — the documented kill switch (`SUBAGENT_MAX_FALLBACKS=0`) disables the
        # walk ENTIRELY, and that has to include the bench write.** `apply_bench` used to run
        # before the loop's `walked >= max_fallbacks` guard, so a switch advertised as "disables
        # the walk" still left 900s of process-global state that `lane_chain` reads. Either the
        # side effect or the docstring was wrong; the docstring is the contract.
        return result

    if cascade and result.failure is not None:
        # The ORIGINAL dispatch's verdict is evidence too — bench it so the NEXT unit in this batch
        # skips the lane instead of rediscovering it. Gated on `cascade`: with no chain configured
        # the walk must leave no trace at all, and `_bench_provider`/`_bench_model` are process-wide
        # state that `lane_chain` also reads.
        lanes.apply_bench(result.failure, spec.provider, spec.model)

    walked = 0
    wall_used = 0.0
    cost_used = 0.0
    best = result  # the incumbent; a rung only displaces it via `_replaces`
    # ⚠️ T05b REVIEW ROUND 1: an explicit flag, NOT `best is result`. Identity happens to be
    # true today only because `best` starts as the same object and is never copied; any
    # future normalisation of the result would silently stop the exhaustion warning firing.
    improved = False
    # ⚠️ T05b REVIEW ROUND 1: the loop has FOUR exits and only one is "the chain ran out". Saying
    # "exhausted the fallback chain" for all of them tells an operator to provision more lanes when
    # the real answer may be "fix the malformed body" or "raise the budget" — different actions.
    stop_reason = "every rung in the chain was tried"
    # ⚠️ **ROUND 5, THE CLASS RATHER THAN THE INSTANCE.** Three consecutive rounds each found one
    # more actionable fact this message dropped — which exit fired, which budget, how many rungs
    # were skipped. So enumerate what an operator can ACT on and carry all of it: why the walk
    # stopped, how many of how many planned rungs ran, WHICH lanes were never dialled (a count says
    # two were skipped; the names say which provider to unbench or key), and the original failure.
    skipped_lanes: list[str] = []  # rungs passed over WITHOUT a dispatch (benched / no credential)
    # ⚠️ **ROUND 9, F2.** An unknown cost on a METERED rung used to be CHARGED the whole remaining
    # budget. That is a pessimistic placeholder, not a spend, and it zeroed `cost_left` — which
    # denied every LATER rung, including free-tier lanes that cannot spend a cent. Measured: a
    # caller who set `max_cost_usd` and configured three FREE lanes reached NONE of them. Setting a
    # cost cap is the responsible thing and it disabled the feature it was protecting. The pessimism
    # is now a FLAG that bars further METERED rungs, leaving real reported spend to the real budget.
    metered_unknown = False
    for provider, model in plan:
        if walked >= max_fallbacks:
            stop_reason = "the per-unit attempt bound (SUBAGENT_MAX_FALLBACKS) was reached"
            break
        if cascade and lanes.bench_remaining(provider, model) > 0.0:
            skipped_lanes.append(f"{provider}:{model} (benched)")
            if events is not None:
                _emit_degradation(
                    events, on_degrade, kind="rung-skipped", reason="benched",
                    provider=provider, model=model, unit=_unit_label(spec),
                )
            continue  # a benched rung is skipped WITHOUT a dispatch — that is the whole point
        if cascade and _rung_credential_missing(provider):
            # Gated on `cascade` like the bench: with no chain the only rung is the unit's OWN
            # model, and refusing to re-dial it on a missing key would change the unconfigured path.
            # SILENT here by design — `_drop_keyless_rungs` already warned ONCE for the batch
            # (ROUND 4, F6). This stays as the guard for a direct caller who assembled `rungs`
            # themselves and never went through that filter.
            skipped_lanes.append(f"{provider}:{model} (no credential)")
            if events is not None:
                _emit_degradation(
                    events, on_degrade, kind="rung-skipped", reason="no-credential",
                    provider=provider, model=model, unit=_unit_label(spec),
                )
            continue
        wall_left = spec.wall_clock_s - wall_used
        cost_left = (
            None if spec.max_cost_usd is None else spec.max_cost_usd - cost_used
        )
        # ⚠️ **ROUND 9, F2 — a rung that CANNOT SPEND must not be denied by an exhausted cost
        # budget.** `openrouter` is the only `free_tier=False` row of the 7-provider registry, and
        # it is the ORIGIN's provider — so a metered origin rung reporting no cost (or raising,
        # per R8/F2) is charged the whole remainder, `cost_left` hits 0.0, and this guard used to
        # `break` the ENTIRE walk. Measured: a caller who sets `max_cost_usd` and configures a
        # chain of three FREE lanes reached NONE of them. Setting a cost cap is the responsible
        # thing to do and it disabled the feature it was protecting.
        #
        # `free_tier` is trusted here exactly as `_rung_cost` already trusts it to charge $0.
        if walked and (
            wall_left <= _MIN_RUNG_WALL_CLOCK_S
            or (cost_left is not None and cost_left <= 0.0)
            or (metered_unknown and not _rung_is_free(provider))
        ):
            # ⚠️ **T05b ROUND 3 — name WHICH budget, which is the whole point of `stop_reason`.**
            # One string for three distinct exits sends an operator to raise the wrong thing: told
            # "cost" when the WALL CLOCK ran out, they lift `max_cost_usd` and nothing changes.
            # ⚠️ **ROUND 6 — the GENERAL form, because the special cases kept missing one.**
            # Round 3 split this into three branches; round 4 found the both-budgets case; round 6
            # found that the wall clock also masks `metered_unknown`. Three rounds of enumerating
            # PAIRS. So enumerate the CONSTRAINTS and report every one that actually holds — an
            # operator who lifts the only budget they were told about, and hits the next one
            # immediately, was misled by an incomplete answer rather than a wrong one.
            blockers = []
            if wall_left <= _MIN_RUNG_WALL_CLOCK_S:
                blockers.append(f"the wall-clock remainder ({wall_left:.1f}s)")
            if cost_left is not None and cost_left <= 0.0:
                blockers.append("the cost remainder (max_cost_usd)")
            if metered_unknown and not _rung_is_free(provider):
                blockers.append(
                    "a metered rung reported an unknowable cost, barring further metered rungs"
                )
            stop_reason = (
                f"{len(blockers)} budget constraint(s) were hit — " + "; ".join(blockers)
                if len(blockers) > 1
                else (blockers[0] + " could not fund another attempt")
            )
            break  # the remainder cannot fund another attempt
        try:
            # A FRESH AgentSpec per rung, never a mutation of `spec`. Five consumers read the model
            # off the SPEC — the results table, the score-feed map, `record_agent_run`, and
            # `_safe_ledger` -> `ledger.agent_record` on all five of `_run_one_uncapped`'s exit
            # paths — and they are correct today only because `result.model == spec.model` on every
            # exit. THIS WALK is what makes them able to diverge: a fresh spec keeps
            # `_run_one_uncapped`'s `result.model = spec.model` stamp true of the rung that RAN, so
            # the local JSONL row and the Postgres flywheel row cannot disagree about which model
            # did the work. Mutating `spec.model` at dispatch would break that quietly — nothing
            # errors, the two ledgers just tell different stories, and the JSONL is the one an
            # operator greps.
            #
            # `replace` RE-RUNS `__post_init__` -> `resolve_provider`, so a rung naming an unknown
            # provider raises here. `UnknownProviderError` subclasses `ValueError`, so one `except`
            # covers both. (`_resolve_chain` validates the whole chain at parse time, so this is the
            # belt to that braces — a rung reaching here bad means the registry changed underneath.)
            rung_spec = replace(
                spec,
                model=model,
                provider=provider,
                wall_clock_s=wall_left,
                max_cost_usd=cost_left,
                # ⚠️ **T05b ROUND 2, F1 — INERT-SAFETY. Filter ONLY on a real swap.** This was
                # unconditional, while every sibling guard in this loop is cascade-gated for the
                # same reason (`apply_bench`, `_rung_credential_missing`, the C3 break, the
                # `_re_routable` veto). With no chain configured the ONLY rung is the unit's own
                # model, so there is no swap to protect against — yet the caller's body was being
                # stripped anyway. Measured: 16 of 64 cross-product cells diverged from `main`,
                # which retries WITH the caller's upstream pin while HEAD retried unpinned, in the
                # state every vendored copy upgrades into. Keyed on the SWAP, not on `cascade`,
                # because that is the actual reason the filter exists.
                body=(
                    spec.body
                    if (provider, model) == origin
                    else _rung_body(spec.body)
                ),
            )
        except ValueError as exc:
            logger.warning(
                "fanout: skipping fallback rung %s:%s — %s. The batch's completed results are "
                "unaffected.",
                provider,
                model,
                exc,
            )
            continue
        walked += 1
        started = time.monotonic()
        try:
            candidates = run_agents([rung_spec], repo=repo, warn_unrecorded=False)
        except Exception as exc:  # noqa: BLE001 — a rung must never cost the caller the BATCH
            # ⚠️ **ROUND 7 — PRE-EXISTING exposure that THIS TICKET multiplies ~5x.** `main`'s
            # `recover_caps` called `run_agents([spec], repo=repo)` equally unguarded in this same
            # post-batch loop, so this is not a regression the walk introduced. What the walk
            # changes is the ODDS: one retry dispatch per capped unit became up to
            # `SUBAGENT_MAX_FALLBACKS` (default 5) against a WIDER re-routable predicate. A raise
            # from any of them propagates out of `fanout` and discards every COMPLETED unit's
            # result in the batch — the outcome the recovery path exists to prevent, arriving
            # through the recovery path itself.
            #
            # Degrade the RUNG, never the batch: warn (never silent — `58-resilience.md:491`) and
            # walk on. The unit keeps `best`, which is at worst its original failure, so the
            # caller's floor is exactly the no-cascade outcome.
            logger.warning(
                "fanout: fallback rung %s:%s raised %s: %s. Degrading this rung; the batch's "
                "completed results are unaffected.",
                provider,
                model,
                type(exc).__name__,
                exc,
            )
            cost_used += _rung_cost(None, provider, cost_left)  # ROUND 8, F2
            if not _rung_is_free(provider):
                metered_unknown = True  # ROUND 9, F2: a raise is the most unknown spend there is
            continue
        finally:
            wall_used += time.monotonic() - started
        if not candidates:
            # ⚠️ **ROUND 10, F2 — an empty return is the SAME unknown-spend shape as a raise, and
            # round 8's fix covered only the raise.** The rung WAS dispatched (`walked` counted it,
            # the `finally` charged its wall clock), so a metered provider may well have billed;
            # falling through to `continue` charged it $0.00 and left `metered_unknown` clear, so
            # the caller's full remaining cap was handed to the next metered rung. Same treatment
            # as `cand is None`.
            cost_used += _rung_cost(None, provider, cost_left)
            if not _rung_is_free(provider):
                metered_unknown = True
            continue
        cand = candidates[0]
        cost_used += _rung_cost(cand, provider, cost_left)
        if cand.cost_usd is None and not _rung_is_free(provider):
            metered_unknown = True
        if cascade and cand.failure is not None:
            lanes.apply_bench(cand.failure, provider, model)
        if _replaces(cand, best):
            best = cand
            improved = True
        if cand.failure is not None and cand.failure.cause in _NON_ROUTABLE_CAUSES:
            # ⚠️ **ROUND 5, C3 — the allowlist vetoed the ORIGIN and was never consulted for a
            # RUNG.** Round-2 fixup 1's whole rationale is "four rungs dialled for one malformed
            # body … verbatim the waste `_NON_ROUTABLE_CAUSES` exists to prevent" — and inside the
            # walk that cause was ignored, so the asymmetry was total: an origin `bad-request`
            # buys ZERO rungs, a rung `bad-request` bought ALL of them. `bad-request` also carries
            # `scope="none"`, so `apply_bench` records nothing and the next batch repeats it
            # (measured: 18 rung dispatches for a 6-unit batch, bench 0.0). Our own malformed body
            # fails identically on every lane, so the chain is over.
            #
            # ⚠️ **ROUND 8, F1 — THIS BREAK MOVED BELOW `_replaces`, AND THE BUG WAS INERT-SAFETY.**
            # It used to fire BEFORE the payload comparison, so a rung answering `bad-request`
            # WITH payload (`loop.py:507-508` and `:787` both build a 400/422 result carrying the
            # tokens and text already streamed) was thrown away and the unit returned its empty
            # origin — "the walk discards a better result", re-entering through C3's own fix. And
            # the break is NOT gated on `cascade` while the origin rung IS planned for any
            # `capped`+0 unit, so it fired with both env vars unset: `main` adopts a retry on
            # `out_tokens > 0`, HEAD returned the empty origin. Keep the payload, THEN stop the
            # chain.
            stop_reason = "a rung answered bad-request, which fails identically on every lane"
            break
        if best is cand and cand.status == "done" and _usable_payload_chars(cand) > 0:
            # ⚠️ **ROUND 5, DEFECT B — the break must also require that the `done` actually WON.**
            # Without `best is cand`, a `done` rung producing LESS than the incumbent (reachable:
            # an origin that streamed partial text before stalling has `out_tokens == 0` and is
            # re-routable by arm 2) neither replaced it NOR let the walk continue — the worst of
            # both, returning a FAILURE while a working lane had just been found and discarded.
            #
            # ⚠️ **REVIEW ROUND 4, F3 — the walk stops on a SUCCESS, never merely on an
            # IMPROVEMENT.** `_replaces` answers "which result survives"; it was doubling as this
            # loop's continuation condition, and the two are different questions. A lateral move
            # between two FAILURE statuses satisfies "improvement": a `content-stall` cap carrying
            # ONE more character than the origin ended the walk and left the rung that would have
            # answered `done` undialled. `content-stall` is the partial-tolerant cause
            # (`loop.py:578`), so that is the COMMON rung failure, not an edge case.
            break
    if cascade and walked and not improved:
        if skipped_lanes and stop_reason != "every rung in the chain was tried":
            # ⚠️ **ROUND 5** — the skipped count is ACTIONABLE whatever ended the walk, and it was
            # being dropped whenever a more specific reason had been set. An operator told only
            # "the attempt bound was reached" raises `SUBAGENT_MAX_FALLBACKS` and meets the same
            # benched lanes on the next batch; they needed to know two rungs were never dialled.
            stop_reason += f" (also never dialled: {', '.join(skipped_lanes)})"
        elif skipped_lanes:
            # ⚠️ **T05b ROUND 2, F3.** Both `continue` paths fall through to the default reason, so
            # a unit whose chain rungs were all BENCHED (or keyless) was reported as having tried
            # them. Measured: "every rung in the chain was tried. 1 dispatch(es) attempted" when the
            # single dispatch was the origin's own retry and neither lane was dialled. That is the
            # mis-routing this message exists to prevent — the lanes are there, they are benched.
            stop_reason = (
                f"these rungs were never dialled: {', '.join(skipped_lanes)}; the rest were tried"
            )
        # ⚠️ **T05b — the attempt count must not vanish.** The ticket originally demanded the walk
        # return "the LAST rung's" result so an operator could tell that N attempts happened. That
        # remedy now CONTRADICTS D-097 (the stated selection policy): returning the last rung
        # unconditionally discards a better earlier one, which is the exact class rounds 4-9 spent
        # 35 defects closing. The CONCERN survives without it — it is an OBSERVABILITY gap, not a
        # selection rule — so the count is logged instead of changing what is returned.
        #
        # Fires only when the cascade actually walked AND nothing displaced the origin: with no
        # chain configured `cascade` is False and this is silent, so the unconfigured path is
        # untouched. `on_degrade` is T06's; this uses the module logger deliberately.
        logger.warning(
            "fanout: unit recovery stopped — %s. %d of %d planned rung(s) dispatched (the "
            "same-model retry counts as one), none improved on the original %s result "
            "(cause=%s). The original stands; see the ledger rows for each attempt.",
            stop_reason,
            walked,
            len(plan),
            result.status,
            getattr(result.failure, "cause", None),
        )
        if events is not None:
            # ⚠️ **T06 — exhaustion is a per-UNIT outcome, and NOTHING propagates out of `fanout`.**
            # `_walk_lanes` runs AFTER every unit has dispatched and been PAID for; raising here
            # would discard the whole `results` list, which this module already records as measured
            # ("raising here killed the ENTIRE batch"). The unit keeps `best` per D-097 — the row
            # that once said "the last rung's" was amended, because returning the last rung
            # discards a better earlier one, the class thirty-five defects were spent closing.
            _emit_degradation(
                events, on_degrade, kind="unit-exhausted", reason=stop_reason,
                dispatched=walked, planned=len(plan),
                never_dialled=list(skipped_lanes), unit=_unit_label(spec),
            )
            if on_exhausted is not None:
                # ⚠️ **ROUND 5 — the SNAPSHOT is built BEFORE the try, and defensively.**
                # A finder claimed `dict(best.tool_calls)` sat OUTSIDE the guard and would kill the
                # batch. That mechanism is wrong — argument evaluation happens inside the enclosing
                # `try`, proved by execution: the batch survived. But the scenario exposed a REAL
                # defect underneath. With `tool_calls=None` the snapshot raised, so:
                #   * the caller's handler was NEVER CALLED — an operator who asked to be told about
                #     exhaustion silently was not, which is the failure `on_exhausted` exists to
                #     prevent; and
                #   * the log said "on_exhausted raised TypeError", which is FALSE. Their handler
                #     never ran; MY snapshot raised. They would debug an innocent callback.
                # So the policy's "a snapshot of any dataclass" must mean a snapshot that CANNOT
                # raise — not merely one wrapped in a guard. The `except` below is now reserved for
                # the HANDLER's own failures, which makes its message truthful.
                # ⚠️ **ROUND 6 — why `dict()` is a COMPLETE copy here, stated rather than assumed.**
                # A finder argued this needs `deepcopy`, because a shallow dict copy shares its
                # VALUES: `ev["result"].tool_calls["args"].append(...)` would reach `batch.results`.
                # True in general, unreachable here: `tool_calls` is a name→COUNT map, built by the
                # module itself at `loop.py:483` (`dict(tool_counts)`) and documented at `loop.py:230`
                # as *"counts (name→int) … incremented ONLY for"* a completed call. Every value is an
                # `int` — immutable — so there is nothing beneath the top level to alias.
                # The invariant this relies on is therefore: **VALUES ARE SCALARS.** If a future
                # change ever makes a value a container, this needs a recursive copy and the
                # hook-safety policy above is violated until it gets one. `deepcopy` was rejected
                # rather than overlooked: it costs an arbitrary walk on every exhausted unit to
                # defend against a shape the module cannot produce.
                _tc = getattr(best, "tool_calls", None)
                _snapshot = replace(best, tool_calls=dict(_tc) if isinstance(_tc, dict) else {})
                try:
                    # ⚠️ **ROUND 3 — `result` is a SNAPSHOT, not the live object.** It used to be
                    # live, justified as "a handler routing on it needs the real thing". But this
                    # module already guarantees a hook cannot RAISE into a paid-for batch and
                    # cannot MUTATE its events; leaving one mutable `AgentResult` reachable was the
                    # odd one out, and a buggy handler assigning `ev["result"].text = ""` would
                    # rewrite what the caller gets back. A snapshot costs one `replace()` plus one
                    # `dict()` — `tool_calls` is the ONLY container on `AgentResult` (enumerated by
                    # introspection, not assumed); every other field is str/int/float/None or the
                    # FROZEN `FailureCause`. A handler that genuinely needs the live object reads
                    # `batch.results`, which stays authoritative.
                    on_exhausted(
                        {
                            "unit": _unit_label(spec), "reason": stop_reason,
                            "dispatched": walked, "planned": len(plan),
                            "never_dialled": list(skipped_lanes),
                            "result": _snapshot,
                        }
                    )
                except Exception as exc:  # noqa: BLE001 — a handler must never sink the batch
                    logger.warning(
                        "fanout: on_exhausted raised %s: %s. The batch is unaffected and the "
                        "unit keeps its best result.",
                        type(exc).__name__,
                        exc,
                    )
    return best


class InsufficientCreditsError(Exception):
    """Raised by `fanout` BEFORE dispatching anything when the account's remaining credit is
    below ``SUBAGENT_CREDIT_FLOOR``.

    ⚠️ NOT a ``ConsultError``, deliberately. Two reasons, and the second is the load-bearing one:
    nothing was consulted (no unit dispatched, no model called), and a consumer that wraps its
    dispatch loop in ``except ConsultError`` — a reasonable way to tolerate per-unit failures —
    would SWALLOW this refusal, which is exactly the "loud" this gate exists to be. It inherits
    ``Exception`` so it is caught only by a handler that means to catch everything.

    ⚠️ This is the one thing `fanout` raises for a RUNTIME condition rather than a config error,
    and that is deliberate: nothing has dispatched and nothing has been paid for, so there is no
    batch result to degrade. Contrast the exhaustion path, which never propagates — by the time a
    unit exhausts, every unit has already dispatched and been BILLED, so raising there would throw
    away work the operator paid for.
    """


def _credit_floor() -> float | None:
    """The configured floor, or ``None`` meaning NO FLOOR — the gate is disarmed.

    ⚠️ UNSET, EMPTY and UNPARSEABLE ARE ONE STATE, and that is the whole point. An empty
    ``SUBAGENT_CREDIT_FLOOR=`` in a `.env` is common, and if it reached ``float()`` it would raise,
    get swallowed by the probe's fail-open path, and emit a degradation event — so an operator who
    configured NOTHING would see the cascade report a degradation on every batch. Only a value that
    parses to a POSITIVE number arms the gate; zero and negatives disarm it, because a floor of 0 is
    indistinguishable from no floor and a negative one can never trip.
    """
    raw = os.getenv("SUBAGENT_CREDIT_FLOOR", "").strip()
    if not raw:
        return None
    try:
        floor = float(raw)
    except ValueError:
        return None
    # ⚠️ NON-FINITE IS NO FLOOR. `float("inf")` PARSES and is > 0, so a typo'd
    # `SUBAGENT_CREDIT_FLOOR=inf` would arm a floor no balance can ever satisfy and refuse EVERY
    # batch forever — with a message quoting a floor of `$inf`. Found by a mutation round: the
    # mutant was equivalent, but enumerating the inputs to prove that surfaced this one. A floor
    # that cannot be met is not a floor; an operator who wants to stop dispatching has clearer ways.
    # (`nan` is already excluded — every comparison with nan is False — but it is covered by the
    # same predicate rather than left to that coincidence.)
    if not math.isfinite(floor):
        return None
    return floor if floor > 0.0 else None


def _fetch_credits() -> float | None:
    """Remaining account credit in USD, or ``None`` on ANY failure (fail-OPEN).

    Module-level ON PURPOSE: `fanout` takes no injectable client, so this name is the test seam —
    the same idiom the existing tests use for ``run_agents``/``pick_models``.

    Shape copied from ``select._fetch_openrouter_prices`` rather than invented: ``import httpx``
    INSIDE the try so a missing dep also fails open, an explicit timeout, ``raise_for_status()``,
    and a bare ``except Exception`` because a billing endpoint must NEVER crash a dispatch.

    ⚠️ FAIL-OPEN, and it is the OPPOSITE of the joint spend cap's fail-closed rule (D-021) — on
    purpose. The cap refuses when it cannot verify because that is money the OPERATOR ceilinged.
    This is a courtesy floor on the VENDOR's balance API: refusing a paid-up batch because
    `/credits` timed out would be a self-inflicted outage. Different question, different direction.

    The endpoint returns ``data.total_credits`` / ``data.total_usage``; remaining is the difference.
    Account-wide, so ONE call serves a whole batch — never call it per unit.
    """
    try:
        import httpx  # inside the try so a missing dep also fails OPEN

        key = os.getenv("OPENROUTER_API_KEY", "")
        resp = httpx.get(
            "https://openrouter.ai/api/v1/credits",
            timeout=15.0,
            headers={"Authorization": f"Bearer {key}"} if key else {},
        )
        resp.raise_for_status()
        data = resp.json()
        payload = data.get("data", {}) if isinstance(data, dict) else {}
        if not isinstance(payload, dict):
            return None
        remaining = float(payload["total_credits"]) - float(payload["total_usage"])
        # ⚠️ A NON-FINITE remaining is NOT a balance — it is a malformed answer, and it must fail
        # OPEN like any other malformed answer rather than reach the comparison. `inf - inf` is
        # `nan`, and EVERY comparison with nan is False, so `nan < floor` would be False and the
        # gate would SILENTLY ALLOW the batch — the one outcome a credit gate must never produce by
        # accident. (Found in review. It is the exact mirror of the non-finite guard on the FLOOR
        # side: I closed that vector and left its neighbour open, one variable away.)
        return remaining if math.isfinite(remaining) else None
    except Exception:  # noqa: BLE001 — a billing endpoint must NEVER crash a dispatch
        return None


def fanout(
    task_type: str,
    units: list[str | dict[str, object]],
    *,
    repo: str,
    project: str | None = None,
    mode: Literal["read_only", "write"] = "read_only",
    k: int | None = None,
    prefer: Literal["quality", "value"] = "quality",
    max_concurrency: int | None = None,
    record: bool = True,
    recover_caps: bool = True,
    # ⚠️ **T06 — these MUST be explicit parameters, not `**spec_kwargs`.** Left implicit they are
    # forwarded into `AgentSpec(**spec_kwargs)` and raise `TypeError`, and the reserved-kwarg guard
    # below names only fanout's OWN owned fields so it would not catch them. Self-correcting on the
    # first run, at the cost of a debugging cycle nobody needs.
    on_degrade: Callable[[dict[str, object]], None] | None = None,
    on_exhausted: Callable[[dict[str, object]], None] | None = None,
    **spec_kwargs: Any,
) -> FanoutBatch:
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

    ``recover_caps`` ALSO drives the **fallback cascade** (T05a), which is **default-OFF and needs
    TWO variables, not one**: ``SUBAGENT_FANOUT_CASCADE=1`` (the opt-in) AND ``SUBAGENT_LANES`` (the
    same comma-separated ``provider:model`` chain :func:`lanes.lane_chain` reads). ⚠️ The chain
    variable alone is deliberately NOT enough — it predates this feature, is documented as
    `lane_chain`'s default chain, and names FREE, sometimes ToS-restricted lanes; activating off it
    would route a consumer's existing ``mode="write"`` coding agents onto those lanes on upgrade
    with no opt-in, which is what the ``provider=`` guard below already refuses to let a caller do
    explicitly. With the opt-in unset, `fanout` behaves exactly as the paragraph above describes,
    chain or no chain. With both set, a unit whose dispatch failed with a ROUTABLE transport cause —
    429/503/404/410/413,
    a content stall, an auth/credit wall, a 5xx — walks that chain, rung by rung, until one answers.
    Each rung is a FRESH :class:`AgentSpec` carrying the unit's own ``task``/``owned_paths``/tools,
    so the worktree, the scope check and the sandbox gate are re-created by construction. A rung
    whose lane is benched is skipped WITHOUT a dispatch, one whose provider key is unset is skipped
    without a dispatch, and a rung that fails WITH A TRANSPORT CAUSE is benched via
    :func:`lanes.apply_bench` so the NEXT unit skips it too. A rung that fails STRUCTURALLY
    (``failure is None`` — sandbox unavailable, a worktree failure, an ungrounded single-shot)
    benches NOTHING, deliberately: those are host/config problems, not lane problems, and pinning
    one to a ``(provider, model)`` would blacklist an innocent lane while every other rung fails
    identically. A rung's result replaces the original only when it is a STRICT IMPROVEMENT
    (more payload, or a clean ``done``), so a re-route can never discard a better partial answer —
    or, in ``mode="write"``, a diff. Bounded by ``SUBAGENT_MAX_FALLBACKS`` (default 5) dispatches
    per unit and by ONE TOTAL ``wall_clock_s``/``max_cost_usd`` across the whole walk (``max_turns``
    stays per-rung); an unknown cost on a metered endpoint is charged as the remaining budget and
    ends the walk. A 400/422 is NOT routed — our own malformed body fails identically on every rung.
    **With ``SUBAGENT_FANOUT_CASCADE`` unset nothing above happens at all**: no chain is resolved, no
    bench is written, nothing is logged, and the only recovery is the same-model second chance
    described in the paragraph above, exactly as before.
    """
    # Resolved HERE too, not only in `run_agents` below. fanout reads `_subagent_state_dir(repo)`
    # for the receipt/outbox dirs and the returned `_state_dir` AFTER dispatch, so validating only at
    # the inner seam would leave those three reads on the caller's raw string — and would refuse the
    # bad repo only after `pick_models` and the spec build had already run. Resolving at both entries
    # keeps every anchor in one batch pointing at the same absolute directory.
    repo = _resolve_repo(repo)
    if mode not in ("read_only", "write"):
        raise ValueError(f"fanout: mode must be 'read_only' or 'write', got {mode!r}")
    if not units:
        raise ValueError("fanout: units is empty — nothing to dispatch")
    if mode == "write" and task_type in _WRITE_STEER_TASK_TYPES:
        # Loud, actionable, NON-blocking (like record_run's footgun warning). Never raises — a genuine
        # exploration review that must read files to discover what's relevant is a valid write-mode use.
        # stderr.write, NOT print(): library code stays print-free so a consuming project's
        # print-ban gate never trips on a vendored copy — the identical rule `_client._emit`
        # already follows and states (`_client.py:373-375`). This site missed it, and since the
        # module ships into ~46 repos that is a gate failure in every one of them, for a warning
        # that is not even theirs. Same stream, same behaviour, explicit newline.
        sys.stderr.write(
            f"⚠️  fanout({task_type!r}, mode='write'): review/grounding whose code you can INLINE is "
            "cheaper + can't cap as mode='read_only' (single-shot). write-mode is for EXPLORATION that "
            "must discover files; if that's you, you're fine — capped runs now return a partial report.\n"
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
        # ⚠️ `task` and `model` were MISSING, and the docstring above already promised they would not
        # be: the guard exists so a reserved field is not "left to Python's per-branch duplicate-kwarg
        # TypeError". `fanout` sets both itself (task from `units`, model from `pick_models`), so
        # passing either produced exactly the raw error the guard was written to replace —
        # `TypeError: AgentSpec() got multiple values for keyword argument 'model'`, from inside a
        # list comprehension, naming no remedy. Found by tripping over it while pinning a model for a
        # review run; same defect class as T06's `on_degrade`/`on_exhausted`.
        "task",
        "model",
    } & spec_kwargs.keys()
    if reserved:
        raise ValueError(
            f"fanout: {sorted(reserved)} are set by fanout itself — don't pass them in **spec_kwargs"
        )
    # fanout's model SELECTION is OpenRouter-ranked (pick_models), so a non-OR `provider` would pair
    # an OR-ranked model id with the wrong endpoint — guaranteed to fail every unit. A non-OR unit is
    # chosen EXPLICITLY, never auto-selected: dispatch it via run_agents([AgentSpec(model=…, provider=…)]).
    if spec_kwargs.get("provider", "openrouter") != "openrouter":
        raise ValueError(
            f"fanout selects OpenRouter-ranked models (pick_models), so provider="
            f"{spec_kwargs['provider']!r} would pair an OR model id with the wrong endpoint. "
            "Dispatch a non-OR unit explicitly: run_agents([AgentSpec(model=…, provider=…)])."
        )
    if k is not None and k <= 0:
        raise ValueError(f"fanout: k must be a positive int (or None), got {k}")
    if max_concurrency is not None and max_concurrency <= 0:
        raise ValueError(
            f"fanout: max_concurrency must be a positive int (or None), got {max_concurrency}"
        )

    # ── T10: pre-flight credits, ONE probe per batch, refuse loudly below the floor ──────────
    # The reporter's PRIMARY failure was not a dead provider, it was an EMPTY ACCOUNT: "the first
    # units consumed the tail, the rest 402'd", 6 of 11 units lost. The lane walk cannot fix that —
    # every OpenRouter rung draws on the SAME credential, so there is nothing to route to.
    #
    # ⚠️ `load_env` FIRST, and this call is why. The loader normally runs inside `arun_agents`,
    # which fanout does not reach until after this point — so a probe placed here would run BEFORE
    # any credential was loaded, 401, and make the fail-open escape the default path on EVERY batch.
    # Safe to call twice: `_dotenv.load_env` is non-overriding (a value already in the real env
    # always wins) and documented never to raise.
    #
    # ⚠️ `load_env` BEFORE `_credit_floor()`, not just before the probe. THE FLOOR ITSELF comes from
    # `.env`, so reading it first meant a floor configured through the DOCUMENTED channel parsed as
    # None and the gate silently never armed. My first cut had exactly that bug and only the `.env`
    # behaviour row caught it — an exported shell var makes every other test pass while the
    # documented channel stays dead, which is the same defect class as the missing DOTENV_KEYS entry.
    # ⚠️ SCOPED TO ONE KEY, and the narrowness is the whole point. The floor itself comes from
    # `.env`, so it must be loaded before `_credit_floor()` reads it — but loading the FULL
    # `DOTENV_KEYS` here would be a behaviour change for every caller, floor or no floor:
    # `arun_agents` normally loads the env, and it runs AFTER `pick_models` (:3344 vs :3447).
    # A blanket `load_env(repo)` here would make `SUBAGENT_SELECTION_DOC` / `SUBAGENT_LIVE_PRICING`
    # from a project `.env` visible to model SELECTION for the first time — silently changing which
    # models ~48 vendored copies dispatch to. Loading only the floor key keeps this feature inert
    # when it is unconfigured, which is the property the whole upgrade rests on.
    # (`arun_agents` still guards its own load behind `load_dotenv=`; `fanout` never forwards that,
    # so no caller can opt out and nothing here overrides one.)
    degradation_events: list[dict[str, object]] = []
    load_env(repo, keys=("SUBAGENT_CREDIT_FLOOR",))
    _floor = _credit_floor()
    if _floor is not None:
        # ⚠️ THE KEY, and ONLY once the gate is actually armed. Round 1's comment above forbids a
        # probe that runs before any credential is loaded; round 4 then narrowed the load to the
        # floor key alone — correctly, to keep the full `.env` out of model SELECTION — and thereby
        # reintroduced exactly that: floor armed from `.env`, key absent, so the probe 401s and
        # `credit-probe-failed` fires on EVERY batch while the gate never does. The feature was
        # inert in the configuration its own README documents. Found by the T09 integration pass;
        # every other test of this feature stubs `_fetch_credits`, so none of them touched the
        # credential path.
        #
        # Loading it HERE rather than beside the floor keeps both invariants: the unconfigured path
        # is still untouched (no floor ⇒ this never runs), and an armed gate gets an authenticated
        # probe. `load_env` is non-overriding, so a real env key still wins.
        load_env(repo, keys=("OPENROUTER_API_KEY",))
        _remaining = _fetch_credits()
        if _remaining is None:
            # FAIL-OPEN: an unreachable billing endpoint must never stop a paid-up account working.
            _emit_degradation(
                degradation_events,
                on_degrade,
                kind="credit-probe-failed",
                reason="unreachable",
                unit="(batch)",
            )
        elif _remaining < _floor:
            raise InsufficientCreditsError(
                f"fanout: refusing to dispatch {len(units)} unit(s) — OpenRouter credit "
                f"${_remaining:.2f} is below the SUBAGENT_CREDIT_FLOOR of ${_floor:.2f}. "
                "Nothing was dispatched and nothing was billed. Top up, or lower/unset the floor. "
                "⚠️ This is a START gate, not a running balance: it cannot see a drain that happens "
                "DURING a batch."
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
                task = cast(str, unit["task"])
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
            tasks.append(cast(str, unit["task"]))
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
    #
    # ⚠️ T05a WIDENED THIS from "one more chance on the SAME model" into a bounded WALK over
    # `(provider, model)` rungs read from `SUBAGENT_LANES` (see `_walk_lanes`). The paragraph above
    # is unchanged and still describes rung 1 of that walk exactly — the same-model second chance is
    # the FIRST rung, taken only for a zero-output congestion cap. With no chain configured there
    # are no other rungs, so the walk IS the old behaviour, structurally rather than by inspection.
    # The ENTRY condition is what changed: `_re_routable` also admits a unit whose structured
    # `failure` names a routable transport cause, because a 410/413/429/402 arrives as
    # `status == "error"` (loop.py's `_finish(text, "error", …)`), not as `"capped"` — the old gate
    # could NEVER fire for any of them, so widening the loop without widening the predicate would
    # have shipped a cascade that passes every fixture and never fires in production.
    if recover_caps:
        rungs, chain_resolved = _fallback_rungs()
        rungs = _drop_keyless_rungs(rungs)
        # ROUND 10, F3: opting in is not enough — a chain must have RESOLVED. Deliberately not
        # `bool(rungs)`, which is the R6/C2 defect this pair of flags exists to keep apart:
        # `chain_resolved` survives the keyless filter emptying `rungs`.
        cascade_on = _cascade_enabled() and chain_resolved
        max_fallbacks = _max_fallbacks()
        for i, (spec, r) in enumerate(zip(specs, results, strict=True)):
            # A structural "error" (sandbox-unavailable / ungrounded / worktree-failure / NVIDIA
            # non-tool-caller refusal) is still NOT recovered — it carries `failure=None` because it
            # never reached the transport, and a retry can't fix a host/config problem; it would
            # just burn the pool. A capped run that produced partial output (out_tokens > 0) is not
            # wasted and is left alone. Both live in `_re_routable`, with the reasoning.
            if _re_routable(r, cascade=cascade_on):
                results[i] = _walk_lanes(
                    spec,
                    r,
                    repo=repo,
                    rungs=rungs,
                    max_fallbacks=max_fallbacks,
                    cascade=cascade_on,
                    events=degradation_events,
                    on_degrade=on_degrade,
                    on_exhausted=on_exhausted,
                )

    # agent_id → was its dispatch row actually written? See FanoutBatch for why this is kept.
    recorded: dict[str, bool] = {}
    if record and project:
        # ── D + H (2026-09-02): make the DROP and the UNSCORED count LOUD at dispatch close. ──
        # D: the flywheel could fail silently. `record_agent_run` is fail-open, the reason travels
        # only through a caller-supplied sink nobody passed, and the banner said nothing — so a dead
        # flywheel and a working one were byte-identical to the operator. 3,578 rows accumulated on
        # disk across 10 repos before anyone noticed, and `check_subagent_flywheel.py` graded agents
        # on a duty the machinery was silently dropping.
        # H: the checker WARNs on an unrecorded run but a recorded-but-UNSCORED one passes silently,
        # and it cannot see otherwise — it reconciles a local ledger against receipts that carry no
        # score, and `set_quality` writes the SAME receipt shape as `record_agent_run`. The ratio is
        # therefore computed HERE, where the scores are in hand. Reported only; nothing blocks until
        # the fire rate has been measured for a week (FIX DIRECTIVE 5 — an unmeasured detector that
        # fires on legitimate patterns is wallpaper, and wallpaper is how enforcement dies).
        _reasons: list[str] = []
        for spec, r in zip(specs, results, strict=True):
            # ⚠ T03 (2026-09-05): build the CORRECTED spec OUTSIDE the `try`. `recover_caps` is
            # safe only because it re-dispatches the SAME model, so `spec.model` stays true of `r`
            # today — but that invariant is not guaranteed by this call site, and any future
            # re-router (the cascade this ticket is independent of) would silently misattribute
            # every re-routed unit to the model it was ORIGINALLY sent to, poisoning the flywheel
            # via `ledger._SPEC_FIELDS` (which pulls "model" off the spec, not the result). Fixing
            # it here — not in `ledger.agent_record` — keeps `ledger.py` untouched.
            # ⚠ T03 FIXUP 3 (review round 2): OUTSIDE the try, deliberately. `replace(...)` re-runs
            # `AgentSpec.__post_init__` -> `resolve_provider` once per unit — a pure lookup that
            # cannot raise for a fanout-built spec today, but INSIDE the try its failure would be
            # swallowed by the very `except Exception` below that also catches a `record_agent_run`
            # failure, and reported identically as "record_agent_run failed for model %s" — an
            # operator reading that investigates the DATABASE, not a spec copy, because
            # `record_agent_run` is documented to NEVER raise (pg_ledger.py:643). Skips the copy
            # entirely in the common case (`r.model` empty or already equal to `spec.model`) rather
            # than allocating one every unit; `r.model` is empty for a cap-refused/unverifiable unit
            # (`_cap_acquire`'s refusal `AgentResult`s never dispatched), so this still falls back to
            # the spec's model in that case.
            _rec_spec = (
                spec if not r.model or r.model == spec.model else replace(spec, model=r.model)
            )
            try:
                # ⚠ USE the return value. `record_agent_run` is documented FAIL-OPEN —
                # "returns False on any error and NEVER raises" — so the `except` below is
                # dead for exactly the failure it exists to catch, and `recorded[...] = True`
                # measured only "a never-raising function did not raise". That made
                # `FanoutBatch.score()`'s orphan guard vacuous: a DB blip at dispatch
                # outboxed the row, `recorded` still said True, and the guard whose whole
                # purpose is refusing to score an orphan waved it through.
                # ⚠ Pass the REPO-ANCHORED dir. Left to default, `receipt_dir`/`outbox_dir`
                # resolve CWD-relative (`Path(".tmp")/"subagents"`) while the ledger is
                # `Path(repo)/.tmp/subagents` — so running from any subdirectory (or with
                # SUBAGENT_OUTBOX_DIR set) split them apart. `audit_unrecorded` then found
                # ZERO receipts (every run "unrecorded") and the strict-mode OUTBOX guard
                # found ZERO pending (nothing excluded), which under FABRIK_FLYWHEEL_STRICT
                # escalates every run of the session. The guard that exists to stop an
                # outage becoming a work stoppage was defeated by a path convention.
                recorded[r.agent_id] = bool(
                    record_agent_run(  # unscored — set_quality later
                        _rec_spec,
                        r,
                        project=project,
                        receipt_dir=_subagent_state_dir(repo),
                        outbox_dir=_subagent_state_dir(repo),
                    )
                )
            except Exception:  # noqa: BLE001 — a record failure NEVER loses the returned results
                recorded[r.agent_id] = False
                _reasons.append("record-raised")
                # ⚠ Name the agent_id, not just the model. The old message said only
                # "failed for model X", so the ONE identifier needed to trace or refuse the
                # later score was absent from the only signal this failure produces.
                # ⚠ T03: name the model that RAN via `_rec_spec.model` (== `r.model or spec.model`),
                # not `spec.model` — this is the only signal a dropped flywheel row produces, so it
                # must name the model that RAN, not the one the spec was built for (they diverge
                # under any re-router; the empty-`r.model` case already folded into `_rec_spec`
                # above, so this can never regress to an empty string either).
                logger.warning(
                    "fanout: record_agent_run failed for model %s (agent_id=%s) — "
                    "this run has NO dispatch row; scoring it would orphan the score",
                    _rec_spec.model,
                    r.agent_id,
                )
        # ── D: the drop is now VISIBLE at dispatch time, not discoverable weeks later. ──
        _n = len(results)
        _dropped = sum(1 for v in recorded.values() if not v)
        if _dropped:
            logger.warning(
                "fanout: FLYWHEEL DROPPED %d/%d dispatch row(s) — they are in the local outbox, not "
                "the database, so pick_models cannot learn from this batch until it is flushed "
                "(scripts/kilo-benchmarks/flush_subagent_outboxes.py runs daily). reasons=%s",
                _dropped, _n, sorted(set(_reasons)) or ["record-returned-false"],
            )
        # ── H: the scored-vs-dispatched ratio, ADVISORY, computed where the scores exist. ──
        # `review` is 91% of all flywheel volume and only ~half of it carries a verdict; a run that
        # records but is never scored teaches the ranking nothing, and no gate could see it.
        _scored = sum(1 for r in results if getattr(r, "quality_score", None) is not None)
        if _n and _scored < _n:
            logger.info(
                "fanout: %d/%d unit(s) carry a quality verdict. An unscored run is recorded but "
                "teaches pick_models nothing — back-fill with set_quality(agent_id, score, …) after "
                "you adjudicate. (Advisory: fire rate is being measured before anything blocks.)",
                _scored, _n,
            )
    else:
        # Recording was never attempted: record=False, or project=None (the auto-record is
        # gated on a project). Every result here lacks a dispatch row by construction.
        for r in results:
            recorded[r.agent_id] = False

    # ⚠️ ONE warning per BATCH when recording fail-opened — not one per unit: a 12-unit fan-out with no
    # DSN would emit 12 identical lines and train the reader to ignore them. Emitted HERE because this
    # is where the cause is still known; without it the first symptom is `score()` refusing every unit
    # minutes later, and that message sent one caller hunting the wrong cause entirely. Fail-open is
    # unchanged — this warns, it never raises and never drops a result.
    if record and project and not all(recorded.values()):
        _lost = [a for a, ok in recorded.items() if not ok]
        # ⚠️ Two DIFFERENT states produce False, and saying the wrong one is the bug this warning
        # exists to prevent. No DSN → nothing was captured. DSN set but DB unreachable → the row IS
        # durably captured in the outbox and only awaits replay. Calling the second "unrecordable"
        # sends a caller whose DSN is set hunting the wrong cause — exactly what happened to the
        # reporter, one message over. So: check for the outbox and name the state that is true.
        _outbox = Path(_subagent_state_dir(repo)) / "pg_outbox.jsonl"
        if _outbox.is_file():
            logger.warning(
                "fanout: %d/%d unit(s) have no dispatch row IN THE DATABASE, so score() will refuse "
                "them — but the rows are NOT lost: %s holds them for replay. Flush the outbox, then "
                "score — and if the flush also returns 0, pass `reason_sink=[]` to see WHY; a missing "
                "psycopg driver makes the flush fail identically to an unreachable DB. Affected: %s",
                len(_lost), len(recorded), _outbox, _lost,
            )
        else:
            logger.warning(
                "fanout: %d/%d unit(s) have NO dispatch row, so score() will refuse them. Check in "
                "this order — (0) is the psycopg DRIVER installed here? `python -c \"import psycopg\"` "
                "— pg_ledger imports it lazily, so without it the sink fail-opens on EVERY record and "
                "no DSN or database state can matter. (1) is SUBAGENT_RUNS_DSN set (process env or "
                "%s/.env)? record_agent_run fail-opens to False without it. Affected: %s",
                len(_lost), len(recorded), repo, _lost,
            )

    # ⚠EMPTY loud harvest warning — the "$0.18 for nothing" seam. A `done` unit whose text AND diff are
    # both blank succeeded with nothing gradeable (a model can burn max_tokens on a reasoning channel and
    # emit an empty completion) — indistinguishable from success until a human reads the (empty) output,
    # so warn the way `capped` is loud. record_agent_run leaves these UNSCORED (never auto-0'd — intel
    # 2026-08-29): an empty is usually output-budget burn, so investigate rather than blame the model.
    # Unit labels match the results-table rows (task_type[i]) so the operator can find them.
    _empty = [f"{task_type}[{i}]" for i, r in enumerate(results) if getattr(r, "empty_output", False)]
    if _empty:
        logger.warning(
            "fanout: %d/%d unit(s) returned EMPTY output on a `done` status (⚠EMPTY in the results "
            "table, left UNSCORED) — an empty is usually output-budget burn, so retry with a larger "
            "max_tokens and investigate before blaming the model. Affected: %s",
            len(_empty), len(results), _empty,
        )

    # ⚠ T03: `r.model or s.model`, not `s.model` — both the results table and the score-feed map
    # below must name the model that RAN, not the one the spec was built for. `recover_caps` is
    # safe only because it re-dispatches the SAME model (so `specs[i].model` stays true of
    # `results[i]` today), but that invariant is not this function's to assume for good; a
    # cap-refused/unverifiable `r` has an empty `.model` (`_cap_acquire` never dispatched it), so
    # `or s.model` falls back to the spec's model rather than regressing it to an empty string.
    entries = [
        {"unit": f"{task_type}[{i}]", "model": r.model or s.model, "result": r}
        for i, (s, r) in enumerate(zip(specs, results, strict=True))
    ]
    # ⚠️ T06: ONE aggregated line, and only when the caller did NOT take the sink. Emitted here,
    # at batch close, because per-event stderr is the chatty channel people learn to ignore.
    try:
        _flush_degradations(degradation_events, on_degrade)
    except Exception as exc:  # noqa: BLE001 — a SUMMARY LINE must never cost a paid-for batch
        # ⚠️ **ROUND 4 — the HOOK-SAFETY POLICY applied to its own flush path.** This runs at the
        # very END of `fanout`, after every unit has dispatched and been billed, so anything that
        # raises here discards all of it — the same batch-killer class as round 1's label, in the
        # code meant to REPORT degradations. Unreachable today (every `kind` is a module-owned
        # string literal and the events are the module's own copies), which is exactly why it is
        # worth guarding: the policy says do not reason about which protections apply, and an
        # unguarded formatting path in the observability layer is how the first one got in.
        logger.warning(
            "fanout: the degradation summary failed to render (%s: %s). The batch and "
            "batch.degradation_events are unaffected.",
            type(exc).__name__,
            exc,
        )
    # ⚠️ **T11 — counted HERE, after the `recover_caps` replacement, and that placement IS the
    # contract.** A unit that recovered on its retry has already been substituted into `results` by
    # this point, so it counts ALIVE; counting earlier would report the pre-recovery state and
    # over-report exactly the units the module just rescued.
    _dead = sum(1 for r in results if _is_dead_unit(r))
    return FanoutBatch(
        results,
        results_table(entries, dead_units=_dead),
        _recorded=recorded,
        _task_type=task_type,
        _project=project,
        _models={r.agent_id: (r.model or s.model) for s, r in zip(specs, results, strict=True)},
        _state_dir=_subagent_state_dir(repo),
        degradation_events=degradation_events,
        dead_units=_dead,
    )


__all__ = [
    "run_agents",
    "arun_agents",
    "AgentSpec",
    "AgentResult",
    "AgentStatus",
    "results_table",
    "fanout",
]
