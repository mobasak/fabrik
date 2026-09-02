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
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, cast

from . import sandbox, spend_cap, workspace
from ._dotenv import load_env
from ._repo import resolve_repo as _resolve_repo
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
    ) -> None:
        self.results = results
        self.table = table
        self._recorded = _recorded or {}
        self._task_type = _task_type
        self._project = _project
        self._models = _models or {}
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
            refusal=AgentResult(
                agent_id, "", "", "error", None, None, 0,
                error=_cap_scrub(
                    f"could not resolve provider {spec.provider!r} to check its cap "
                    f"({type(exc).__name__}); refusing rather than spending unbounded"
                ),
            ),
        )
    cap_env = getattr(cfg, "monthly_cap_env", None) if cfg is not None else None
    if not cap_env:
        return _CapHold(CAP_NO_CAP_CONFIGURED)

    def _refuse(reason: str, detail: str) -> _CapHold:
        return _CapHold(
            reason,
            refusal=AgentResult(agent_id, "", "", "error", None, None, 0, error=detail),
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


def results_table(entries: list[dict[str, object]]) -> str:
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
    return "\n".join(rows)


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
                        spec,
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
                logger.warning(
                    "fanout: record_agent_run failed for model %s (agent_id=%s) — "
                    "this run has NO dispatch row; scoring it would orphan the score",
                    spec.model,
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

    entries = [
        {"unit": f"{task_type}[{i}]", "model": s.model, "result": r}
        for i, (s, r) in enumerate(zip(specs, results, strict=True))
    ]
    return FanoutBatch(
        results,
        results_table(entries),
        _recorded=recorded,
        _task_type=task_type,
        _project=project,
        _models={r.agent_id: s.model for s, r in zip(specs, results, strict=True)},
        _state_dir=_subagent_state_dir(repo),
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
