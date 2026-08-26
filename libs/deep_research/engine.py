"""A generic, headless staged-research engine — plan → search → shortlist → verify → deliver.

DOMAIN-FREE by construction: the prompts, the card schema, the leg set (names/caps/args), the fallback
query templates, and the brief-field access all live in an INJECTED :class:`Pack` (data, not code). The
engine's ``brief`` is OPAQUE — it never does ``brief.get("<domain key>")``; it asks the pack. Swap the pack
and the engine researches a different domain with no edit.

VENDORABLE-ALONE: the engine imports no ``web-tools`` and no ``cost-budget`` module. The search/scrape
executors, their ``LegResult``/``Row``/config, and the money ceiling are all typed via LOCAL structural
Protocols and INJECTED via :class:`ResearchDeps` — unit-1's real executors and unit-2's ceiling duck-type in.

Deterministic workflow, NOT an agentic loop (the step count is bounded/hardcodable — the fit case for
workflows, per Anthropic's "Building Effective Agents"). Each stage checkpoints atomically; a re-run resumes
from the last completed stage and re-bills nothing; a ceiling breach degrades to ``truncated``, never a raise.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger(__name__)

LlmFn = Callable[..., Awaitable[str]]


# ── LOCAL structural Protocols (unit-1 / unit-2 duck-type in — NO import of those modules) ──────────


class Row(Protocol):
    """One structured search hit. Attribute access only (unit-1's ``SearchRow`` dataclass satisfies
    it) — the engine NEVER does ``row.get(...)``."""

    @property
    def title(self) -> str: ...
    @property
    def url(self) -> str: ...
    @property
    def text(self) -> str: ...


class LegResult(Protocol):
    ok: bool
    rows: Sequence[Row]
    cost_usd: Decimal
    credits: int


#: A search/scrape executor: ``leg(args, *, config, client) -> LegResult`` (unit-1's async ``a_*`` shape).
LegExecutor = Callable[..., Awaitable[LegResult]]


class LegSpec(Protocol):
    """One leg's declaration in the pack: its name (the key into ``deps.legs``/``deps.leg_estimates``),
    its per-run call cap, whether it is the FREE reallocation target, and which args to build."""

    @property
    def name(self) -> str: ...
    @property
    def cap(self) -> int: ...
    @property
    def is_free(self) -> bool: ...
    @property
    def include_market(self) -> bool: ...
    @property
    def num_results(self) -> int | None: ...


class Pack(Protocol):
    """The injected worldview. Everything domain-specific the engine needs, as data + tiny pure fns.
    Members are READ-ONLY (properties) so a frozen ``PackData`` dataclass satisfies the Protocol."""

    @property
    def query_plan_prompt(self) -> str: ...
    @property
    def shortlist_prompt(self) -> str: ...
    @property
    def verify_prompt(self) -> str: ...
    @property
    def shortlist_cap(self) -> int: ...
    @property
    def verify_cap(self) -> int: ...
    @property
    def legs(self) -> Sequence[LegSpec]: ...
    def coerce_card(self, raw: Mapping[str, Any]) -> dict[str, Any]: ...
    def subject(self, brief: Mapping[str, Any]) -> str: ...
    def subject_name(self, brief: Mapping[str, Any]) -> str: ...
    def fallback_plan(self, brief: Mapping[str, Any], market: str) -> dict[str, list[str]]: ...


# ── the injected deps ──────────────────────────────────────────────────────────────────────────────


@dataclass
class ResearchDeps:
    """Everything injected. The consumer wires the LLM, the search/scrape executors + their per-leg cost
    ESTIMATES (only the consumer knows its vendor pricing), an opaque config + http client, the money
    bounds, and the checkpoint file + job id. cost-budget is OPTIONAL — no reservation ⇒ pass a large
    ``reserved_estimate``."""

    llm: LlmFn
    legs: Mapping[str, LegExecutor]
    scrape: LegExecutor
    leg_estimates: Mapping[str, Decimal]
    scrape_estimate: Decimal
    config: Any  # opaque — passed to the executors, never read by the engine
    client: Any  # opaque http client — passed through
    reserved_estimate: Decimal
    ceiling_factor: Decimal
    checkpoint_file: Path
    #: REQUIRED (no default) — the owning job. The checkpoint's double-book guard keys on it; a shared
    #: default ("") would let two runs sharing a checkpoint path resume each other's completed file.
    job_id: str
    spent_usd: Decimal = field(default=Decimal("0"), init=False)
    credits: int = field(default=0, init=False)
    ceiling_hit: bool = field(default=False, init=False)
    checkpoint_state: dict[str, Any] = field(default_factory=dict, init=False)


# ── checkpointing (ported generic; the double-book job-id guard is load-bearing) ────────────────────


def load_checkpoint(path: Path, *, job_id: str = "") -> tuple[int, dict[str, Any]]:
    """(last completed stage, state) — or (0, {}) when the file is missing/corrupt. Corruption shapes are
    DISCARDED, not raised (the resume path must absorb a bad file, never crash the worker): unparseable
    JSON, a missing/non-int ``stage``, a missing ``spend_usd``, a stage claiming data it lacks (a
    truncated/edited file with ``stage>=1`` but no ``plan``, ``>=2`` no ``rows``, ``>=3`` no ``shortlist``).
    A checkpoint carrying a DIFFERENT ``job_id`` is discarded (the double-book guard: without it a second
    run 'resumes' the first's completed file and settles at its spend having called nothing). ``job_id=""``
    skips the ownership check (a spend-only read)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, {}
    if not isinstance(raw, dict) or not isinstance(raw.get("stage"), int):
        return 0, {}
    if "spend_usd" not in raw:
        return 0, {}
    try:
        Decimal(str(raw["spend_usd"]))
    except InvalidOperation:
        return 0, {}
    if job_id and raw.get("job_id") != job_id:
        return 0, {}
    # the resume path reads state["plan"]/["rows"]/["shortlist"] at the stage that consumes them —
    # a stage claiming completion it can't back up is corruption, not a resumable state.
    stage = raw["stage"]
    if raw.get("status") != "complete" and (
        (stage >= 1 and "plan" not in raw)
        or (stage >= 2 and "rows" not in raw)
        or (stage >= 3 and "shortlist" not in raw)
    ):
        return 0, {}
    return stage, raw


def _write_checkpoint(path: Path, doc: dict[str, Any]) -> None:
    """Atomic: a PID-unique sibling tempfile + ``os.replace`` (only atomic within one filesystem, and the
    checkpoint dir may be a mounted volume — so the temp must be a sibling; a PID-unique name stops two
    racers tearing one file)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


# ── LLM plumbing + the money ceiling ─────────────────────────────────────────────────────────────


def _parse_json_block(reply: str) -> Any:
    """Tolerant of a fenced or prefixed reply; returns None rather than raising."""
    text = reply.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start = min((i for i in (text.find("["), text.find("{")) if i >= 0), default=-1)
    if start > 0:
        text = text[start:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _charge(deps: ResearchDeps, result: LegResult) -> LegResult:
    """Add ``cost_usd`` + ``credits`` (never re-estimate), and re-persist the spend into the last stage
    checkpoint NOW so a crash between a paid call and its stage checkpoint loses at most ONE call. Best-
    effort — a failed write must not turn a successful paid call into a raise."""
    deps.spent_usd += result.cost_usd
    deps.credits += result.credits
    if deps.checkpoint_state:
        try:
            _write_checkpoint(
                deps.checkpoint_file,
                {**deps.checkpoint_state, "spend_usd": str(deps.spent_usd), "credits": deps.credits},
            )
        except OSError:
            log.warning("deep_research_spend_persist_failed")
    return result


def _ceiling_allows(deps: ResearchDeps, next_leg_estimate: Decimal) -> bool:
    """False forecloses the call AND marks the run truncated — a ceiling stop is visible in the delivery,
    not silently absorbed as 'fewer results'. A FREE call (estimate ≤ 0) NEVER breaches the budget and is
    always allowed — even after a paid leg hit the ceiling — so the free reallocation leg keeps running."""
    if next_leg_estimate <= 0:
        return True
    allowed = deps.spent_usd + next_leg_estimate <= deps.reserved_estimate * deps.ceiling_factor
    if not allowed and not deps.ceiling_hit:
        deps.ceiling_hit = True
        log.warning(
            "deep_research_ceiling_reached spent=%s reserved=%s factor=%s",
            deps.spent_usd,
            deps.reserved_estimate,
            deps.ceiling_factor,
        )
    return allowed


def _row_to_dict(row: Row) -> dict[str, Any]:
    """The engine's internal row shape (built explicitly via the Row attribute Protocol — never by
    dumping a raw executor row, which may be a dataclass with no ``.get``)."""
    return {"name": str(row.title), "url": str(row.url), "text": str(row.text)}


def _safe_int(value: Any, default: int = 0) -> int:
    """A tolerant int — a corrupt checkpoint value reads as ``default`` (never a raise on resume)."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _leg_args(leg: LegSpec, query: str, market: str) -> dict[str, Any]:
    args: dict[str, Any] = {"query": query}
    if leg.include_market:
        args["market"] = market
    if leg.num_results is not None:
        args["num_results"] = leg.num_results
    return args


# ── stages (pack-driven, leg-agnostic) ─────────────────────────────────────────────────────────────


async def _stage1_query_plan(
    brief: Mapping[str, Any], market: str, *, pack: Pack, deps: ResearchDeps
) -> dict[str, list[str]]:
    reply = await deps.llm(
        pack.query_plan_prompt,
        json.dumps({"brief": dict(brief), "home_market": market}, ensure_ascii=False),
    )
    parsed = _parse_json_block(reply)
    leg_names = [leg.name for leg in pack.legs]
    if not isinstance(parsed, dict) or not any(
        isinstance(parsed.get(n), list) and parsed[n] for n in leg_names
    ):
        log.warning("deep_research_plan_unusable — deterministic fallback plan in use")
        parsed = pack.fallback_plan(brief, market)
    return {
        name: [str(q) for q in (parsed.get(name) or []) if str(q).strip()] for name in leg_names
    }


async def _run_leg(
    leg: LegSpec, plan: Mapping[str, list[str]], market: str, budget: int, deps: ResearchDeps
) -> tuple[str, list[LegResult]]:
    out: list[LegResult] = []
    est = deps.leg_estimates[leg.name]
    for q in list(plan.get(leg.name, []))[:budget]:
        if not _ceiling_allows(deps, est):
            break
        result = await deps.legs[leg.name](_leg_args(leg, q, market), config=deps.config, client=deps.client)
        out.append(_charge(deps, result))
    return leg.name, out


async def _stage2_search(
    plan: Mapping[str, list[str]], market: str, *, pack: Pack, deps: ResearchDeps
) -> tuple[list[dict[str, Any]], list[str]]:
    """Every paid leg concurrently (per-leg cap), then the FREE leg with the reallocated budget. Returns
    (rows, degraded_legs). A leg is degraded when it produced no successful call at all."""
    paid = [leg for leg in pack.legs if not leg.is_free]
    free = next((leg for leg in pack.legs if leg.is_free), None)

    settled = await asyncio.gather(
        *[_run_leg(leg, plan, market, leg.cap, deps) for leg in paid], return_exceptions=True
    )
    results: dict[str, list[LegResult]] = {}
    degraded: list[str] = []
    for leg, item in zip(paid, settled, strict=True):
        if isinstance(item, BaseException):
            # a RAISED leg is the hardest failure — surface it in degraded_legs (a soft ok=False leg is
            # flagged below; a raised one used to be invisible).
            log.warning("deep_research_leg_raised %s %s", leg.name, type(item).__name__)
            degraded.append(leg.name)
            continue
        _name, leg_results = item
        results[leg.name] = leg_results

    def _ok(rs: list[LegResult]) -> int:
        return sum(1 for r in rs if r.ok)

    if free is not None:
        # unspent budget from every non-free leg (a raised leg = 0 spent → its full cap) → the free leg.
        free_budget = free.cap + sum(leg.cap - _ok(results.get(leg.name, [])) for leg in paid)
        try:
            _name, free_results = await _run_leg(free, plan, market, free_budget, deps)
            results[free.name] = free_results
        except Exception as exc:  # noqa: BLE001 — the free leg degrades too, never crashes the run
            log.warning("deep_research_leg_raised %s %s", free.name, type(exc).__name__)
            degraded.append(free.name)

    rows: list[dict[str, Any]] = []
    for leg_results in results.values():
        for r in leg_results:
            rows.extend(_row_to_dict(row) for row in r.rows)
    degraded += [name for name, rs in results.items() if rs and _ok(rs) == 0]
    return rows, degraded


async def _stage3_shortlist(
    rows: list[dict[str, Any]], brief: Mapping[str, Any], *, pack: Pack, deps: ResearchDeps
) -> list[dict[str, Any]]:
    if not rows:
        return []
    # NB: a targeted token replace, NOT str.format — the prompt legitimately contains literal JSON
    # braces (e.g. {"name": ..}) that .format would try to interpolate.
    reply = await deps.llm(
        pack.shortlist_prompt.replace("{cap}", str(pack.shortlist_cap)),
        json.dumps({"subject": pack.subject_name(brief), "rows": rows[:120]}, ensure_ascii=False),
    )
    parsed = _parse_json_block(reply)
    if not isinstance(parsed, list):
        log.warning("deep_research_shortlist_unusable — shipping zero candidates")
        return []
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name, url = str(item.get("name", "")).strip(), str(item.get("url", "")).strip()
        key = (name.casefold(), url.casefold())
        if not name or key in seen:
            continue
        seen.add(key)
        out.append({"name": name, "url": url})
        if len(out) >= pack.shortlist_cap:
            break
    return out


def _usable_text(candidate: Mapping[str, Any], rows: list[dict[str, Any]]) -> str:
    url = candidate.get("url", "")
    for row in rows:
        if row.get("url") == url and len(row.get("text") or "") >= 200:
            return str(row["text"])
    return ""


async def _stage4_verify_extract(
    candidates: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    brief: Mapping[str, Any],
    *,
    pack: Pack,
    deps: ResearchDeps,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    fetches = 0
    for cand in candidates:
        text = _usable_text(cand, rows)
        if not text and cand.get("url") and fetches < pack.verify_cap:
            if not _ceiling_allows(deps, deps.scrape_estimate):
                # Stop FETCHING, not shipping: an unverifiable candidate ships flagged, never dropped
                # (a `break` here delivered an EMPTY card set on a truncated run — measured regression).
                fetches = pack.verify_cap
                evidence.append({**cand, "page_text": ""})
                continue
            fetches += 1
            try:
                fetched = _charge(
                    deps, await deps.scrape({"url": cand["url"]}, config=deps.config, client=deps.client)
                )
                if fetched.ok and fetched.rows:
                    text = str(fetched.rows[0].text)
            except Exception as exc:  # noqa: BLE001 — a raising scrape degrades (ships unverified), never crashes
                log.warning("deep_research_scrape_raised %s", type(exc).__name__)
        evidence.append({**cand, "page_text": text[:4000]})

    if not evidence:
        return []
    reply = await deps.llm(
        pack.verify_prompt,
        json.dumps({"subject": pack.subject_name(brief), "candidates": evidence}, ensure_ascii=False),
    )
    parsed = _parse_json_block(reply)
    if not isinstance(parsed, list):
        log.warning("deep_research_extract_unusable — shipping zero cards")
        return []
    return [pack.coerce_card(item) for item in parsed if isinstance(item, dict)]


# ── the run ──────────────────────────────────────────────────────────────────────────────────────


def _validate_deps(pack: Pack, deps: ResearchDeps) -> None:
    """Entry-time wiring check (before stage 1): every pack leg has an executor AND an estimate, and the
    scrape leg is wired. A gap is a WIRING bug (a missing estimate would silently disable the ceiling ->
    unbounded spend), so fail LOUD here — the never-raise contract governs money/staging degradation ONCE
    staging begins, not config wiring."""
    leg_names = {leg.name for leg in pack.legs}
    problems: list[str] = []
    missing_exec = leg_names - set(deps.legs)
    missing_est = leg_names - set(deps.leg_estimates)
    if missing_exec:
        problems.append(f"deps.legs missing executors for {sorted(missing_exec)}")
    if missing_est:
        problems.append(f"deps.leg_estimates missing {sorted(missing_est)}")
    if deps.scrape is None:
        problems.append("deps.scrape is required")
    # the free reallocation leg is chosen by the pack's is_free flag, but "always runs even past the
    # ceiling" depends on its ESTIMATE being ≤ 0 — bind the two so a free leg wired with a positive
    # estimate can't be silently foreclosed. And the engine runs exactly one free leg.
    free = [leg for leg in pack.legs if leg.is_free]
    if len(free) != 1:
        problems.append(f"pack must declare exactly ONE is_free leg (the reallocation target), found {len(free)}")
    elif free[0].name in deps.leg_estimates and deps.leg_estimates[free[0].name] > 0:
        problems.append(
            f"the free leg {free[0].name!r} must have leg_estimate ≤ 0 "
            f"(it is the free reallocation target); got {deps.leg_estimates[free[0].name]}"
        )
    if problems:
        raise ValueError("deep-research deps wiring error: " + "; ".join(problems))


async def run_research(
    brief: Mapping[str, Any], market: str, *, pack: Pack, deps: ResearchDeps
) -> dict[str, Any]:
    """The whole pipeline; returns the final result doc (also the checkpoint). Never raises for a money/
    staging reason (the job layer decides what a raise means). ``deps.spent_usd`` holds the true actual on
    return. A wiring bug (missing executor/estimate) DOES raise ``ValueError`` at entry, before any stage."""
    _validate_deps(pack, deps)

    stage_done, state = load_checkpoint(deps.checkpoint_file, job_id=deps.job_id)
    resumed = Decimal(str(state.get("spend_usd", "0")))
    if not resumed.is_finite() or resumed < 0:  # a NaN poisons every ceiling compare; a negative re-runs
        resumed = Decimal("0")
    deps.spent_usd = resumed
    deps.credits = _safe_int(state.get("credits", 0))
    deps.checkpoint_state = state if state else {"stage": 0, "status": "running", "spend_usd": "0"}

    def _doc(stage: int, **extra: Any) -> dict[str, Any]:
        return {
            **state,
            "job_id": deps.job_id,
            "stage": stage,
            "spend_usd": str(deps.spent_usd),
            "credits": deps.credits,
            "status": "running",
            **extra,
        }

    if state.get("status") == "complete":
        return state  # already delivered — a resumed run re-bills nothing

    if stage_done < 1:
        state = _doc(1, plan=await _stage1_query_plan(brief, market, pack=pack, deps=deps))
        _write_checkpoint(deps.checkpoint_file, state)
        deps.checkpoint_state = state
    if stage_done < 2:
        rows, degraded = await _stage2_search(state["plan"], market, pack=pack, deps=deps)
        state = _doc(2, rows=rows, degraded_legs=degraded)
        _write_checkpoint(deps.checkpoint_file, state)
        deps.checkpoint_state = state
    if stage_done < 3:
        state = _doc(
            3, shortlist=await _stage3_shortlist(state["rows"], brief, pack=pack, deps=deps)
        )
        _write_checkpoint(deps.checkpoint_file, state)
        deps.checkpoint_state = state
    if stage_done < 4:
        cards = await _stage4_verify_extract(
            state["shortlist"], state.get("rows", []), brief, pack=pack, deps=deps
        )
        state = _doc(4, cards=cards)
        _write_checkpoint(deps.checkpoint_file, state)
        deps.checkpoint_state = state

    final = {
        **state,
        "job_id": deps.job_id,
        "stage": 5,
        "status": "complete",
        "truncated": deps.ceiling_hit,
        "cards": state.get("cards", []),
        "degraded_legs": state.get("degraded_legs", []),
        "spend_usd": str(deps.spent_usd),
        "credits": deps.credits,
    }
    final.pop("rows", None)  # the poll route reads this — keep it lean (rows were working state)
    _write_checkpoint(deps.checkpoint_file, final)
    return final
