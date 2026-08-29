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
    def fallback_plan(
        self, brief: Mapping[str, Any], market: str
    ) -> dict[str, list[str]]: ...


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
        spend = Decimal(str(raw["spend_usd"]))
    except InvalidOperation:
        return 0, {}
    # `Decimal("NaN")`/`Decimal("Infinity")` PARSE — they do not raise — so the try/except alone let a
    # poisoned spend through, while this docstring promised corruption is DISCARDED and the README
    # advertises this function for reading a crashed run's spend directly (a billing display would
    # have shown "NaN" with no signal it was junk).
    #
    # But DISCARDING THE WHOLE FILE over a junk spend is the wrong trade, and review caught the first
    # version doing exactly that: a checkpoint written by a pre-guard version of this module can hold
    # a NaN spend beside perfectly valid stage/plan/rows/shortlist data, and throwing it away
    # re-runs — and RE-BILLS — every paid stage already completed. That is the double-bill this
    # module's checkpoint design exists to prevent, reintroduced by a corruption check.
    # So: neutralise the poisoned FIELD, keep the resumable STAGE — the same clamp `run_research`
    # already applies one level up, moved to where a direct caller sees it too.
    if not spend.is_finite():
        # ⚠️ NOT zero. Zeroing keeps the stages (good — no re-bill) but restarts the CEILING from
        # nothing, so the run can spend a SECOND full budget on top of the spend it just lost.
        # Measured: a resume from a poisoned checkpoint made 2 more paid calls against a fresh $0.25
        # ceiling. That trades a re-bill for an unbounded-ish overspend, which is not an improvement.
        #
        # The true prior spend is unrecoverable, and a money guard may not assume the cheapest
        # possibility. So assume the reservation is SPENT: the paid stages are not re-run, no new
        # paid call is authorised, and the run completes `truncated` — the module's existing honest
        # degradation — on its free leg. Costly-but-correct beats cheap-and-wrong for money.
        log.warning(
            "deep_research_checkpoint_spend_unusable — spend_usd=%r is not finite. The accumulated "
            "spend for this run is LOST, so it is assumed EXHAUSTED: paid stages are not re-run and "
            "no new paid call is authorised; the run will finish truncated on its free leg. Re-run "
            "with a fresh job_id to authorise a new budget.",
            raw["spend_usd"],
        )
        raw = {**raw, "spend_usd": "0", "spend_unknown": True}
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


def _parse_json_block(reply: Any) -> Any:
    """Tolerant of a fenced or prefixed reply; returns None rather than raising.

    ``reply`` is typed ``Any``, NOT ``str``, and deliberately so: it is whatever an **injected**
    ``LlmFn`` handed back, and nothing enforces that Protocol's ``-> str`` at runtime. Typing it
    ``str`` would make the guard below statically unreachable (mypy ``--warn-unreachable`` says so),
    which is the type system asserting a guarantee the injection seam cannot give.

    The violation that prompted this was ``None`` — reported by the hub on 2026-08-29, on the first
    vendored run, and attributed there to OpenRouter returning ``content: null`` when a reasoning
    model burns its whole budget in the reasoning channel (their diagnosis of the upstream cause; we
    have not verified it, and the guard does not depend on it). ``None.strip()`` raised
    AttributeError straight out of ``run_research``, piercing the never-raise posture from inside a
    stage. Absorbing it here is what makes the first sentence literally true rather than merely
    intended.

    Logged under its OWN key: the callers' ``*_unusable`` warnings send an operator to the PROMPT,
    while this cause lives in the caller's ``llm`` wiring or model choice.
    """
    if not isinstance(reply, str):
        log.warning(
            "deep_research_llm_contract_violation — injected llm returned %s, not str; "
            "treating as unparseable (check the llm fn / model, not the prompt)",
            type(reply).__name__,
        )
        return None
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


async def _ask_llm(deps: ResearchDeps, prompt: str, payload: str) -> Any:
    """Call the injected ``llm`` and return its reply, or ``""`` if it RAISED.

    The sibling of ``_parse_json_block``'s guard, and the more common half in practice: a provider
    timeout, a 429, or a 5xx surfaces as an EXCEPTION, not a malformed string. ``deps.legs`` and
    ``deps.scrape`` are already exception-guarded (``return_exceptions=True`` / ``except Exception``);
    ``deps.llm`` was not, so a raising client pierced the never-raise posture exactly like the
    ``None`` return did. Absorbing both means every caller's "unusable" branch — which already
    exists — is the single degradation path for a misbehaving llm.

    **Returns ``""``, NOT ``None``, and that choice is load-bearing.** ``None`` would flow into
    ``_parse_json_block`` and fire *its* ``deep_research_llm_contract_violation`` warning too — so a
    RAISE would be reported as "your llm returned None", which is a different defect with a
    different remedy. An empty ``str`` is a real ``str``: it takes the ordinary unparseable path and
    leaves this function's own key as the single, correct diagnosis. (Caught by the regression test
    for this very guard — the first version returned ``None`` and logged both causes.)
    """
    try:
        return await deps.llm(prompt, payload)
    except Exception as exc:  # noqa: BLE001 — an injected callable may raise anything
        log.warning(
            "deep_research_llm_raised — injected llm raised %s: %s; treating as unparseable "
            "(check the llm fn / provider, not the prompt)",
            type(exc).__name__,
            exc,
        )
        return ""


def _safe_pack_call(
    what: str,
    fn: Callable[..., Any],
    /,
    *args: Any,
    default: Any = None,
    want: type | tuple[type, ...] | None = None,
) -> Any:
    """Call an injected ``Pack`` method, absorbing BOTH failure halves into ``default``.

    The ``Pack`` is an injected dependency like ``llm``/``legs``/``scrape``, and it is the one a
    consumer writes themselves, so it misbehaves the same two ways an injected ``llm`` does:

    * it **raises** — ``coerce_card`` on a malformed LLM row is the likely thrower; and
    * it **returns something its own Protocol type hint forbids**, without raising — a
      ``fallback_plan`` missing a ``return`` on one branch yields ``None``; a ``subject_name`` that
      forgot to stringify yields an object ``json.dumps`` then refuses.

    ``want`` closes the second half, and it is not decoration: the return value escapes this
    function before it is used, so a bad one crashes at the USE site (``parsed.get(...)``,
    ``json.dumps(...)``) *outside* any try/except — piercing never-raise from inside a stage, which
    is the exact defect this module was patched for one seam up. Guarding only the raise here would
    have rebuilt the same asymmetry ``_ask_llm`` + ``_parse_json_block`` exist to avoid. Found by
    review, after the raise-only version shipped in this same change.
    """
    try:
        got = fn(*args)
    except Exception as exc:  # noqa: BLE001 — an injected callable may raise anything
        log.warning(
            "deep_research_pack_raised — pack.%s raised %s: %s; degrading",
            what,
            type(exc).__name__,
            exc,
        )
        return default
    if want is not None and not isinstance(got, want):
        log.warning(
            "deep_research_pack_contract_violation — pack.%s returned %s, expected %s; degrading "
            "(check the pack, not the prompt)",
            what,
            type(got).__name__,
            getattr(want, "__name__", want),
        )
        return default
    return got


def _json_safe(what: str, value: Any) -> bool:
    """Is ``value`` JSON-serializable? Checked because the checkpoint write is NOT guarded.

    Type-checking the container is not enough: ``{"score": Decimal("1.5")}`` is a perfectly good
    ``dict`` that ``json.dumps`` refuses, so a card can pass every type guard above and still blow
    up at the checkpoint write — after three PAID stages, uncaught.

    ⚠️ An earlier version of this docstring claimed a card was *the one* pack-controlled object
    reaching ``_write_checkpoint``. That was false, and review caught it: leg **names** come from
    ``pack.legs`` (an unguarded Protocol property) and become checkpoint **keys**, where a non-``str``
    is equally fatal — and earlier, in stage 1, before any paid call. Those are REJECTED, not
    coerced: ``_validate_deps`` raises a wiring ``ValueError`` for a non-``str`` (or duplicate) leg
    name before any paid call. (This sentence itself said "coerced with ``str()``" for one round
    after the coercion was deleted — the same stale-claim defect it sits directly beneath, which is
    a fair measure of how easily prose outlives the code it describes.)
    ``allow_nan=False`` because ``json.dumps`` emits bare ``NaN``/
    ``Infinity`` by default: Python round-trips those, every strict JSON reader rejects them.
    """
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        log.warning(
            "deep_research_pack_unserialisable — pack.%s produced a value JSON cannot represent "
            "(%s); dropping the row (it would crash the checkpoint write, or emit invalid JSON)",
            what,
            exc,
        )
        return False
    return True


def _charge(deps: ResearchDeps, result: LegResult) -> LegResult:
    """Add ``cost_usd`` + ``credits`` (never re-estimate), and re-persist the spend into the last stage
    checkpoint NOW so a crash between a paid call and its stage checkpoint loses at most ONE call. Best-
    effort — a failed write must not turn a successful paid call into a raise."""
    # `LegResult` is an INJECTED boundary like `llm` and `Pack`, and it was the last one still
    # trusted. A `cost_usd` of NaN/Infinity (a divide-by-zero-duration timer, a mis-parsed vendor
    # response) poisons `spent_usd` permanently, and every later Decimal comparison against it raises
    # `decimal.InvalidOperation` — which stage 2 happens to absorb via `gather(return_exceptions=True)`
    # but stage 4's `_ceiling_allows` call does NOT, so it leaves `run_research` uncaught. Same shape
    # as the `llm`-returns-None report that started this module's hardening: an injected value
    # piercing never-raise from inside a stage. Guarded here, at the ONE place a cost enters the
    # ledger, rather than at every comparison downstream.
    # `credits` is the 8th and last injected numeric boundary. It is typed `int` in the Protocol, but
    # nothing enforces that: a float NaN from a mis-computed credit calculation is written RAW into
    # both the checkpoint and the returned doc (unlike `spend_usd`, which is `str()`-ed, and unlike
    # cards, which go through `_json_safe`). `json.dumps` emits it as a bare `NaN` token — valid to
    # Python, rejected by every strict JSON reader, i.e. the caller's billing client.
    credits = getattr(result, "credits", None)
    if not isinstance(credits, int) or isinstance(credits, bool):
        log.warning(
            "deep_research_leg_credits_unusable — executor reported credits=%r (%s, not int); "
            "counting 0 (the run's credit total will UNDERSTATE this call)",
            credits,
            type(credits).__name__,
        )
        credits = 0
    cost = getattr(result, "cost_usd", None)
    if not isinstance(cost, Decimal) or not cost.is_finite() or cost < 0:
        log.warning(
            "deep_research_leg_cost_unusable — executor reported cost_usd=%r; charging 0 instead "
            "(check the executor's cost calculation; spend_usd will UNDERSTATE this call)",
            cost,
        )
        cost = Decimal("0")
    deps.spent_usd += cost
    deps.credits += credits
    if deps.checkpoint_state:
        try:
            _write_checkpoint(
                deps.checkpoint_file,
                {
                    **deps.checkpoint_state,
                    "spend_usd": str(deps.spent_usd),
                    "credits": deps.credits,
                },
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
    allowed = (
        deps.spent_usd + next_leg_estimate
        <= deps.reserved_estimate * deps.ceiling_factor
    )
    if not allowed and not deps.ceiling_hit:
        deps.ceiling_hit = True
        log.warning(
            "deep_research_ceiling_reached spent=%s reserved=%s factor=%s",
            deps.spent_usd,
            deps.reserved_estimate,
            deps.ceiling_factor,
        )
    return allowed


def _row_to_dict(row: Row) -> dict[str, Any] | None:
    """The engine's internal row shape, or ``None`` if ``row`` is not Row-shaped.

    Built explicitly via the Row attribute Protocol — never by dumping a raw executor row, which may
    be a dataclass with no ``.get``. The ``getattr`` guard is the ELEMENT half of the rows check one
    layer up: that one validates the CONTAINER's type, which `range(3)` and `[1, 2, 3]` both pass —
    a Sequence of ints, whose elements then died on ``row.title`` with an ``AttributeError`` out of
    ``run_research``. Checking the container's type is not checking its contents; both are needed,
    and the container guard alone left this standing for exactly one commit.
    """
    title, url, text = (getattr(row, a, None) for a in ("title", "url", "text"))
    if title is None or url is None or text is None:
        log.warning(
            "deep_research_leg_row_unusable — a row of type %s lacks title/url/text; dropping it",
            type(row).__name__,
        )
        return None
    return {"name": str(title), "url": str(url), "text": str(text)}


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
    reply = await _ask_llm(
        deps,
        pack.query_plan_prompt,
        json.dumps({"brief": dict(brief), "home_market": market}, ensure_ascii=False),
    )
    parsed = _parse_json_block(reply)
    # No coercion here, deliberately: `_validate_deps` has already REJECTED any non-str leg name
    # (loudly, at entry, before a penny is spent), so these are str by the time this runs. Three
    # earlier attempts to coerce here instead all shipped a worse bug than the crash they removed —
    # a leg silently running zero queries while the run reported "complete".
    leg_names = [leg.name for leg in pack.legs]
    if not isinstance(parsed, dict) or not any(
        isinstance(parsed.get(n), list) and parsed[n] for n in leg_names
    ):
        log.warning("deep_research_plan_unusable — deterministic fallback plan in use")
        parsed = _safe_pack_call(
            "fallback_plan", pack.fallback_plan, brief, market, default={}, want=dict
        )
    return {
        name: [str(q) for q in (parsed.get(name) or []) if str(q).strip()]
        for name in leg_names
    }


async def _run_leg(
    leg: LegSpec,
    plan: Mapping[str, list[str]],
    market: str,
    budget: int,
    deps: ResearchDeps,
) -> tuple[str, list[LegResult], int]:
    """(name, results, failed_call_count).

    ``failed`` is the RESIDUAL of per-call isolation, and it is returned rather than swallowed for
    the same reason ``dropped_cards`` is published: a leg that half-failed reports
    ``degraded_legs: []`` — correctly, since ``degraded`` means "produced no successful call at
    all" — so without this count a consumer polling the doc cannot tell a clean run from one where
    half its planned queries died. A bound that does not publish its residual is a bound nobody can
    audit.
    """
    out: list[LegResult] = []
    failed = 0
    est = deps.leg_estimates[leg.name]
    for q in list(plan.get(leg.name, []))[:budget]:
        if not _ceiling_allows(deps, est):
            break
        # PER-CALL, not per-leg. Without this, one bad call anywhere in the loop raised out of the
        # whole task, `gather(return_exceptions=True)` returned the exception INSTEAD of the list,
        # and every EARLIER call's rows were discarded — rows that were already fetched, already
        # charged, and already paid for. Measured: call 1 returns a good billable row, call 2 returns
        # a malformed result, and the good row is absent from the final doc while the leg is
        # reported wholesale as "raised". Isolating the failure keeps what the money already bought.
        try:
            result = await deps.legs[leg.name](
                _leg_args(leg, q, market), config=deps.config, client=deps.client
            )
        except Exception as exc:  # noqa: BLE001 — an injected executor may raise anything
            failed += 1
            log.warning(
                "deep_research_leg_call_raised — %s raised %s on one query; keeping this leg's "
                "earlier results (%d so far)",
                leg.name,
                type(exc).__name__,
                len(out),
            )
            continue
        out.append(_charge(deps, result))
    # NOTE: total failure does NOT re-raise. It did, so that the caller's
    # `gather(return_exceptions=True)` would record the leg as degraded — but an exception carries
    # only itself, so the `failed` count went into the void with it: a leg whose every call died
    # reported `failed_calls: 0` while `degraded_legs` named it. An under-reported residual is worse
    # than none, because it reads as authoritative. Returning normally keeps BOTH signals; the
    # caller degrades on `not out` explicitly, which is also more honest than inferring failure from
    # an exception type. The gather's `return_exceptions=True` still stands for a genuine bug inside
    # this function (a missing estimate key, say) — that is a different thing and stays a raise.
    return leg.name, out, failed


async def _stage2_search(
    plan: Mapping[str, list[str]], market: str, *, pack: Pack, deps: ResearchDeps
) -> tuple[list[dict[str, Any]], list[str], int]:
    """Every paid leg concurrently (per-leg cap), then the FREE leg with the reallocated budget. Returns
    (rows, degraded_legs). A leg is degraded when it produced no successful call at all."""
    paid = [leg for leg in pack.legs if not leg.is_free]
    free = next((leg for leg in pack.legs if leg.is_free), None)

    settled = await asyncio.gather(
        *[_run_leg(leg, plan, market, leg.cap, deps) for leg in paid],
        return_exceptions=True,
    )
    results: dict[str, list[LegResult]] = {}
    degraded: list[str] = []
    failed_calls = 0
    for leg, item in zip(paid, settled, strict=True):
        if isinstance(item, BaseException):
            # a RAISED leg is the hardest failure — surface it in degraded_legs (a soft ok=False leg is
            # flagged below; a raised one used to be invisible).
            log.warning("deep_research_leg_raised %s %s", leg.name, type(item).__name__)
            degraded.append(leg.name)
            continue
        _name, leg_results, n_failed = item
        results[leg.name] = leg_results
        failed_calls += n_failed
        if not leg_results and n_failed:
            # every call died: degraded, AND its residual counted. Previously this leg re-raised, so
            # it landed in `degraded_legs` but contributed 0 to `failed_calls`.
            log.warning(
                "deep_research_leg_raised %s all %d call(s) failed", leg.name, n_failed
            )
            degraded.append(leg.name)

    def _ok(rs: list[LegResult]) -> int:
        # `getattr` for EXISTENCE (an injected result may lack the attribute entirely, and this
        # runs before the free leg's own try/except) — but TRUTHINESS for the test, not `is True`.
        # Narrowing it to the `True` singleton was a regression of my own: an executor returning
        # `ok=1` or a `numpy.bool_` — both perfectly ordinary — had its healthy, already-BILLED calls
        # counted as failures, which reported the leg `degraded` and made the free-leg reallocation
        # over-steal its budget. Measured: 2 successful billed calls, `degraded_legs: ["alpha"]`.
        return sum(1 for r in rs if getattr(r, "ok", False))

    if free is not None:
        # unspent budget from every non-free leg (a raised leg = 0 spent → its full cap) → the free leg.
        free_budget = free.cap + sum(
            leg.cap - _ok(results.get(leg.name, [])) for leg in paid
        )
        try:
            _name, free_results, n_failed = await _run_leg(
                free, plan, market, free_budget, deps
            )
            results[free.name] = free_results
            failed_calls += n_failed
            if not free_results and n_failed:
                log.warning(
                    "deep_research_leg_raised %s all %d call(s) failed",
                    free.name,
                    n_failed,
                )
                degraded.append(free.name)
        except Exception as exc:  # noqa: BLE001 — the free leg degrades too, never crashes the run
            log.warning("deep_research_leg_raised %s %s", free.name, type(exc).__name__)
            degraded.append(free.name)

    rows: list[dict[str, Any]] = []
    for leg_results in results.values():
        for r in leg_results:
            # THREE distinct ways an injected LegResult goes wrong, and each needed its own answer:
            #   the attribute is MISSING      -> `r.rows` raises AttributeError  (getattr, here)
            #   the container is wrong-typed  -> `rows=None` raises TypeError    (isinstance, here)
            #   the ELEMENTS are wrong-typed  -> `row.title` raises              (`_row_to_dict`)
            # Each was fixed in a separate round, and each earlier fix carried a comment claiming it
            # was the last one. `getattr` with a default is the only form that survives all three, so
            # it is used for EVERY read of an injected result — value-checking presumes existence.
            rows_val = getattr(r, "rows", None)
            if not isinstance(rows_val, Sequence) or isinstance(rows_val, (str, bytes)):
                log.warning(
                    "deep_research_leg_rows_unusable — executor returned rows=%r (%s, not a "
                    "sequence); dropping this leg's rows (the call was already charged)",
                    rows_val,
                    type(rows_val).__name__,
                )
                continue
            rows.extend(d for row in rows_val if (d := _row_to_dict(row)) is not None)
    degraded += [name for name, rs in results.items() if rs and _ok(rs) == 0]
    return rows, degraded, failed_calls


async def _stage3_shortlist(
    rows: list[dict[str, Any]],
    brief: Mapping[str, Any],
    *,
    pack: Pack,
    deps: ResearchDeps,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    # NB: a targeted token replace, NOT str.format — the prompt legitimately contains literal JSON
    # braces (e.g. {"name": ..}) that .format would try to interpolate.
    reply = await _ask_llm(
        deps,
        pack.shortlist_prompt.replace("{cap}", str(pack.shortlist_cap)),
        json.dumps(
            {
                "subject": _safe_pack_call(
                    "subject_name", pack.subject_name, brief, default="", want=str
                ),
                "rows": rows[:120],
            },
            ensure_ascii=False,
        ),
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
) -> tuple[list[dict[str, Any]], int]:
    """(cards, dropped) — ``dropped`` is the residual: rows a misbehaving pack cost us."""
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
                    deps,
                    await deps.scrape(
                        {"url": cand["url"]}, config=deps.config, client=deps.client
                    ),
                )
                if fetched.ok and fetched.rows:
                    text = str(fetched.rows[0].text)
            except Exception as exc:  # noqa: BLE001 — a raising scrape degrades (ships unverified), never crashes
                log.warning("deep_research_scrape_raised %s", type(exc).__name__)
        evidence.append({**cand, "page_text": text[:4000]})

    if not evidence:
        return [], 0
    reply = await _ask_llm(
        deps,
        pack.verify_prompt,
        json.dumps(
            {
                "subject": _safe_pack_call(
                    "subject_name", pack.subject_name, brief, default="", want=str
                ),
                "candidates": evidence,
            },
            ensure_ascii=False,
        ),
    )
    parsed = _parse_json_block(reply)
    if not isinstance(parsed, list):
        log.warning("deep_research_extract_unusable — shipping zero cards")
        return [], 0
    cards = [
        _safe_pack_call("coerce_card", pack.coerce_card, item, want=dict)
        for item in parsed
        if isinstance(item, dict)
    ]
    # a raising / wrong-typed coerce_card yields None for THAT row only — drop it, keep the rest.
    # Then the deeper check: `want=dict` validates the CONTAINER, not its VALUES, and a card is the
    # only pack-controlled payload that reaches `_write_checkpoint`'s json.dumps. A well-typed dict
    # holding a Decimal/datetime/set therefore passed every guard above and blew up at the CHECKPOINT
    # WRITE — after three paid stages, uncaught, with no log key at all. Rejecting it here (rather
    # than making the checkpoint write best-effort) is deliberate: a silently-failed checkpoint would
    # make a resume RE-RUN a paid stage, turning a crash into a double-bill.
    kept = [c for c in cards if c is not None and _json_safe("coerce_card", c)]
    # Publish the residual. `degraded_legs` exists precisely so a job layer polling the CHECKPOINT
    # sees a leg failure without reading logs; a silently shrinking `cards` had no such signal, so a
    # dropped card was invisible to the module's own documented consumption pattern. A bound that
    # does not publish its residual is a bound nobody can audit.
    return kept, len(cards) - len(kept)


# ── the run ──────────────────────────────────────────────────────────────────────────────────────


def _validate_deps(pack: Pack, deps: ResearchDeps) -> None:
    """Entry-time wiring check (before stage 1): every pack leg has an executor AND an estimate, and the
    scrape leg is wired. A gap is a WIRING bug (a missing estimate would silently disable the ceiling ->
    unbounded spend), so fail LOUD here — the never-raise contract governs money/staging degradation ONCE
    staging begins, not config wiring."""
    problems: list[str] = []
    # A leg name becomes a KEY in the checkpoint JSON, in the LLM's query plan, and in the pack's own
    # fallback_plan. The engine cannot make those three agree for an arbitrary object: it would have
    # to guess what key the LLM and the pack author will independently produce. Coercion was tried
    # and failed twice — `str()` on a plain Enum gives "Leg.ALPHA", not "alpha", so every leg matched
    # nothing and silently ran ZERO queries while reporting status "complete". That is a WIRING bug
    # wearing a degradation's clothes, so it belongs here with the other wiring bugs: loud, at entry,
    # before a penny is spent. A str SUBCLASS (StrEnum, `class Leg(str, Enum)`) is fine — json.dumps
    # serialises it by its data and it hashes equal to its value.
    non_str = sorted(
        (leg.name for leg in pack.legs if not isinstance(leg.name, str)), key=repr
    )
    if non_str:
        problems.append(
            f"leg names must be str — they are checkpoint JSON keys and query-plan keys; got "
            f"{[repr(n) for n in non_str]}. A plain Enum will NOT do: str(Leg.ALPHA) is 'Leg.ALPHA', "
            f"not its value. Pass the value (leg.value), a plain str, or a str-mixin "
            f"(class Leg(str, Enum) / StrEnum)."
        )
    # Built AFTER the non-str check, and from str names ONLY. A set comprehension over raw names
    # hashes them — so an UNHASHABLE name (a list) raised a bare `TypeError: unhashable type` from
    # this line, one statement before the check written to give exactly this wiring bug a clean
    # message. Loud, but the wrong exception and no remedy text, which breaks the contract the
    # docstring above states. Filtering here also stops a bad name compounding into a spurious
    # missing-executor complaint.
    leg_names = {leg.name for leg in pack.legs if isinstance(leg.name, str)}
    # Duplicate names collapse EVERYWHERE the engine keys by name: the `leg_names` set below, the
    # `plan` dict, and `results[leg.name]` in stage 2 — where the second leg's assignment OVERWRITES
    # the first's. Measured: two legs named "search" made 4 billed calls costing $0.04, and the paid
    # leg's rows vanished under the free leg's, with `degraded_legs: []` and `status: "complete"`.
    # Paid work discarded with no residual published is the precise failure this module has spent
    # ten review rounds eliminating; a copy-pasted leg block in a YAML pack is all it takes.
    str_names = [leg.name for leg in pack.legs if isinstance(leg.name, str)]
    dupes = sorted({n for n in str_names if str_names.count(n) > 1})
    if dupes:
        problems.append(
            f"duplicate leg names {dupes} — names key the plan, the executors and the results, so a "
            f"duplicate silently overwrites the other leg's (already billed) results"
        )
    # EVERY consumer-wired Decimal, not just the estimates. Guarding them one field at a time is what
    # this module has already done wrong repeatedly: the `cost_usd` fix left `reserved_estimate`,
    # `ceiling_factor` and `scrape_estimate` untouched, and all three still raised
    # `decimal.InvalidOperation` straight out of `run_research` — the crash RELOCATING rather than
    # closing. NaN is contagious through comparison, so the whole set is checked in one place.
    bad_dec = sorted(
        [
            n
            for n, v in deps.leg_estimates.items()
            if isinstance(n, str) and not v.is_finite()
        ]
        + [
            name
            for name, val in (
                ("reserved_estimate", deps.reserved_estimate),
                ("ceiling_factor", deps.ceiling_factor),
                ("scrape_estimate", deps.scrape_estimate),
            )
            if not val.is_finite()
        ]
    )
    if bad_dec:
        problems.append(
            f"these must be finite Decimals: {bad_dec} — a NaN/Infinity poisons the ceiling "
            f"arithmetic and raises decimal.InvalidOperation mid-run, after paid calls"
        )
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
        problems.append(
            f"pack must declare exactly ONE is_free leg (the reallocation target), found {len(free)}"
        )
    elif (
        # isinstance FIRST: `x in dict` hashes x, and an unhashable name would raise TypeError from
        # here — which is exactly where the previous version of this fix moved the crash it removed
        # three lines up. A non-str name is already recorded in `problems`; this check simply has
        # nothing to say about it.
        isinstance(free[0].name, str)
        and free[0].name in deps.leg_estimates
        # `.is_finite()` BEFORE the comparison: `Decimal("NaN") > 0` raises InvalidOperation, so a
        # mistyped estimate crashed this validator with a bare decimal error instead of the clean,
        # aggregated wiring ValueError it exists to produce — the same wrong-exception-at-the-wiring-
        # boundary defect the unhashable-name fix closed for a sibling field.
        and deps.leg_estimates[free[0].name].is_finite()
        and deps.leg_estimates[free[0].name] > 0
    ):
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
    if (
        not resumed.is_finite() or resumed < 0
    ):  # a corrupt/negative spend must not disable the ceiling
        resumed = Decimal("0")
    if state.get("spend_unknown"):
        # `load_checkpoint` found the persisted spend unusable and kept the STAGE rather than
        # discarding it (which would re-bill the paid work). The true spend is unrecoverable, so it
        # is treated as EXHAUSTED, never as zero: zeroing would authorise a second full budget on
        # top of the spend just lost — measured at 2 extra paid calls against a fresh ceiling.
        # Assuming exhaustion re-runs nothing and authorises nothing; the free leg still runs and the
        # doc ships `truncated`, which is this module's existing honest degradation.
        resumed = deps.reserved_estimate * deps.ceiling_factor
        log.warning(
            "deep_research_resume_spend_assumed_exhausted — the persisted spend was unusable; "
            "treating the reservation as spent. No new PAID call will be made this run; use a fresh "
            "job_id to authorise a new budget."
        )
    deps.spent_usd = resumed
    deps.credits = _safe_int(state.get("credits", 0))
    deps.checkpoint_state = (
        state if state else {"stage": 0, "status": "running", "spend_usd": "0"}
    )

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
        state = _doc(
            1, plan=await _stage1_query_plan(brief, market, pack=pack, deps=deps)
        )
        _write_checkpoint(deps.checkpoint_file, state)
        deps.checkpoint_state = state
    if stage_done < 2:
        rows, degraded, failed_calls = await _stage2_search(
            state["plan"], market, pack=pack, deps=deps
        )
        state = _doc(2, rows=rows, degraded_legs=degraded, failed_calls=failed_calls)
        _write_checkpoint(deps.checkpoint_file, state)
        deps.checkpoint_state = state
    if stage_done < 3:
        state = _doc(
            3,
            shortlist=await _stage3_shortlist(
                state["rows"], brief, pack=pack, deps=deps
            ),
        )
        _write_checkpoint(deps.checkpoint_file, state)
        deps.checkpoint_state = state
    if stage_done < 4:
        cards, dropped = await _stage4_verify_extract(
            state["shortlist"], state.get("rows", []), brief, pack=pack, deps=deps
        )
        state = _doc(4, cards=cards, dropped_cards=dropped)
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
        "dropped_cards": state.get("dropped_cards", 0),
        # the per-call residual of leg isolation — a half-failed leg is NOT `degraded` (it did
        # produce a successful call), so without this a consumer cannot tell it from a clean run.
        "failed_calls": state.get("failed_calls", 0),
        "spend_usd": str(deps.spent_usd),
        "credits": deps.credits,
    }
    final.pop(
        "rows", None
    )  # the poll route reads this — keep it lean (rows were working state)
    _write_checkpoint(deps.checkpoint_file, final)
    return final
