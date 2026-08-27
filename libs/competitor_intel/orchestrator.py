"""The orchestrator — drives the injected ``deep-research`` engine across stages under a SINGLE money
ceiling, a never-raise boundary, and an orchestrator-level checkpoint.

Phase A ships the discover -> mine-reviews half (stages 1-2); the synthesis tail + optional stages are
Phase B. Everything domain-specific is injected DATA (:class:`Deps`, the YAML packs, the source profile);
no originating-project vocabulary lives here.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from .adapters import enabled_adapters
from .dossier import Dossier, Signal, Tier, Us
from .protocols import Deps, Pack
from .stages import PricingBlock, WhiteSpaceBlock, price_wedge, white_space
from .synth import LlmMeter, align_features, build_matrix, extract_features, gap_synthesis

logger = logging.getLogger(__name__)

_PACKS_DIR = Path(__file__).parent / "packs"

# Map common fabrik scaffold-type strings to the module's source-profile keys, so a consumer passing its
# `project.yaml::type` verbatim resolves to a real profile instead of silently getting an empty one.
_PRODUCT_TYPE_ALIASES: dict[str, str] = {
    "saas-skeleton": "saas",
    "chrome-extension": "extension",
    "desktop-app": "desktop",
    "python-api": "headless-api",
    "python-api-gpu": "headless-api",
    "node-api": "headless-api",
    "file-api": "headless-api",
    "file-worker": "headless-api",
    "static-site": "website",
    "docusaurus": "docs",
}


#: No USD figure this module handles is a real number of dollars beyond this. The bound exists to keep
#: absurd magnitudes OUT of the budget arithmetic: `Decimal("1E+1000000")` constructs fine and reports
#: `is_finite() == True`, but `total - spent` then raises `decimal.Overflow` — which is an
#: `ArithmeticError`, NOT a `ValueError`, so it escaped `run()` past a consumer's documented
#: `except ValueError:`. Reachable from a corrupt persisted total or a consumer-supplied one.
#: Compared via ``Decimal.adjusted()`` — the decimal exponent — and NEVER via ``abs()`` or any other
#: arithmetic. ``abs()`` consults the decimal context, so asking "is this magnitude absurd?" with
#: ``abs(d) > _MAX_USD`` raises the very ``Overflow`` the bound exists to prevent: the guard becomes the
#: trap. ``adjusted()`` is pure. (Caught by testing the fix rather than reading it.)
_MAX_USD_ADJUSTED = 12  # 1e12 USD


def _to_decimal(value: Any) -> Decimal:
    """A safe, FINITE, BOUNDED Decimal from whatever a caller/engine left behind (a Decimal, a
    stringified one, a float, None, garbage). NaN/inf/garbage/absurd-magnitude returns 0 rather than
    poisoning a compare or a total.

    ⚠️ Returning 0 is the right failure for a *total* (fail-closed: no budget, nothing runs) and the
    WRONG one for a restored *spend* (fail-open: the ceiling is re-granted). One helper cannot serve
    both, so the spend-restore path uses :func:`_decimal_or_none` and its ledger floor instead."""
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
    return d if d.is_finite() and d.adjusted() <= _MAX_USD_ADJUSTED else Decimal("0")


def _decimal_or_none(value: Any) -> Decimal | None:
    """``_to_decimal``'s honest sibling: ``None`` when the value could not be read at all, instead of a
    ``0`` that is indistinguishable from a real zero. Use this wherever "unreadable" and "zero" must lead
    to DIFFERENT behaviour — on the money path they almost always must."""
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not d.is_finite() or d.adjusted() > _MAX_USD_ADJUSTED:
        return None
    return d


def _is_finite_decimal(value: Any) -> bool:
    return isinstance(value, Decimal) and value.is_finite()


#: Lower is more trustworthy. Used only to break a dedupe tie, never to rank output.
_TIER_RANK = {"A": 0, "B": 1, "C": 2}


#: Fallback when a consumer's per-call synthesis estimate is unusable. Small, positive, and NOT zero —
#: see :func:`_synth_estimate`.
_SYNTH_ESTIMATE_FALLBACK = Decimal("0.01")


def _synth_estimate(value: Any) -> Decimal:
    """A POSITIVE per-synthesis-call charge, whatever the consumer wired.

    The injected LLM returns no cost, so this estimate is the only thing metering the synthesis tail
    against ``total_budget_usd``. A ``0`` / ``None`` / garbage estimate charges nothing per call, which
    silently switches the ceiling off for the entire tail — unbounded spend reported as a clean run.

    Extracted from ``run()`` deliberately: inline, the clamp was a local with no observable and its test
    asserted only that ``run()`` returned something. A guard that cannot be observed cannot be defended,
    and this one is load-bearing on money."""
    est = _to_decimal(value)
    return est if est > 0 else _SYNTH_ESTIMATE_FALLBACK


def _canonical_signal(sig: Signal) -> Signal:
    """Normalize a Signal ONCE, at ingest, so no downstream consumer can disagree about its identity.

    ⚠️ THIS IS A ROOT-CAUSE FIX, and it exists because patching the sites did not work. FIVE consecutive
    review rounds each found a different *normalization divergence* — the dedupe key normalized a field
    one way while a consumer read it another, and every time the merge silently deleted or duplicated
    evidence:

      * ``aspect``      — the key omitted it entirely; `gap_synthesis` groups BEAT themes by it
      * ``sentiment``   — the key omitted it; `gap_synthesis` filters on it
      * the tier merge  — replaced the whole Signal, erasing the loser's sentiment
      * ``sentiment``   — the key stripped, the consumer's filter did not
      * ``competitor``  — the key strips, the trust-domain lookup and the extraction match did not

    Each fix was correct and each left the NEXT site divergent, because the identity contract was
    re-derived independently at four places. Whitespace-stripping every string field at INGEST makes the
    divergence structurally impossible: there is one canonical form and every consumer sees it.

    Case is deliberately NOT folded — ``aspect`` is rendered to the reader, so lowering it here would
    change the brief. Both the key and the consumers that group already lower for comparison; that is a
    comparison concern, not a storage one."""
    return replace(
        sig,
        competitor=sig.competitor.strip(),
        aspect=sig.aspect.strip(),
        sentiment=sig.sentiment.strip(),
        quote=sig.quote.strip(),
        source_url=sig.source_url.strip(),
    )


def _signal_key(s: Signal) -> tuple[str, str, str, str, str]:
    """The identity of a piece of review evidence, for de-duplication.

    ⚠️ ``aspect`` is IN the key, and that is the whole correction. Keying on
    ``(competitor, quote, source_url)`` alone looked right and silently destroyed data: the reviews pack
    asks the extractor for *the feature/topic the user is talking about*, so ONE quote covering two
    topics is its normal output — and `gap_synthesis` buckets BEAT themes BY ASPECT. Dropping the second
    aspect erased a whole BEAT opening inside a single run, `partial=False`, no cause. A dedupe key must
    contain every field a downstream consumer groups by, or the dedupe IS the data loss.
    ``sentiment`` is in it for the SAME reason, one round later: ``gap_synthesis`` filters on
    ``s.sentiment.lower() != "negative"`` — another group-by — and the reviews pack asks for a sentiment
    per card, so two cards over one quote differing only in sentiment is ordinary extractor output. The
    rule generalises: **every field a downstream consumer groups or filters by belongs in the key.**

    ``tier`` is deliberately NOT in the key — two tiers of the same evidence are one source, and
    ``source_weight`` sums over entries, so keeping both would double-count. The tie is broken by
    provenance instead (see :func:`_extend_signals`)."""
    # ⚠️ NORMALIZED exactly as `gap_synthesis` normalizes — `(aspect or "").strip().lower()` and
    # `sentiment.lower()`. Matching the field NAME is not enough; the VALUE must match too. Deduping on
    # the RAW values while the consumer groups on the normalized ones means `"Pricing"` and `"pricing "`
    # survive as distinct entries here and then re-merge downstream, DOUBLE-COUNTING: measured
    # weight 1.6 -> 3.2 from the SAME two source urls, which `beat.sort(key=-weight)` then promotes over
    # genuinely better-corroborated themes, with `partial=False` and no cause. That is the very
    # double-count this function's `tier` exclusion exists to prevent, re-entering through the field
    # round 5 added to stop a different data loss.
    # ⚠️ The `.strip()` calls here are now REDUNDANT — `_canonical_signal` strips at ingest and
    # `_extend_signals` is the only path in, so every Signal reaching this function is already canonical.
    # Their mutants therefore survive, BY CONSTRUCTION and by design: that redundancy is the root-cause
    # fix working. They are kept as a local invariant for any future caller that keys a Signal without
    # going through the ingest path — but this comment exists so the survival is not mistaken for a
    # coverage gap, which is the failure this file has been wrong about eight times.
    return (
        s.competitor.strip(),
        (s.aspect or "").strip().lower(),
        (s.sentiment or "").strip().lower(),
        s.quote.strip(),
        s.source_url.strip(),
    )


def _is_usable_signal(value: Any) -> bool:
    """A `Signal` whose FIELDS are the types the synthesis tail will call methods on.

    ⚠️ ``isinstance(value, Signal)`` proves the type of the OBJECT, not of its fields — and `Signal` is a
    plain dataclass with no runtime validation, so a consumer adapter (the documented extension point)
    returning `Signal(sentiment=None, …)` passed that filter, was appended to `review_signal`, survived
    the adapter's own `except`, and detonated LATER outside every boundary: `gap_synthesis` does
    `s.sentiment.lower()`, `trust` does `s.source_url.strip()`, and `extract_features` joins `s.quote`.
    Three of nine probed field shapes escaped `run()` as `AttributeError`/`TypeError` — none of them a
    `ValueError`, so the documented `except ValueError:` missed all three.

    The seam's promise was "filtering to real Signals here keeps that failure at the seam"; it held for
    exactly one failure mode (an unhashable field) and not for the others. Checking the fields is what
    makes the promise true."""
    if not isinstance(value, Signal):
        return False
    return all(
        isinstance(getattr(value, f), str)
        for f in ("competitor", "aspect", "sentiment", "quote", "source_url", "tier")
    ) and (
        # ⚠️ DELEGATE to `_safe_rating` — do not re-implement its check. An earlier round wrote a bare
        # `float(value.rating)` here, which is precisely the call `_safe_rating` exists to wrap: a JSON
        # integer too large for a C double raises `OverflowError`, and raising HERE aborts the whole
        # `_extend_signals` loop, destroying every remaining signal in that adapter's batch AND skipping
        # the `dropped` append, so the run reports `OverflowError` instead of `MalformedAdapterSignal`.
        # The clean rejection path loses one signal; the raising path loses the rest of the batch.
        value.rating is None or _safe_rating(value.rating) is not None
    )


def _extend_signals(target: list[Signal], incoming: Any, rejected: list[Any] | None = None) -> None:
    """Append signals IDEMPOTENTLY, keyed on the evidence itself (competitor, quote, source_url).

    Two independent needs meet here. (1) `review_signal` is persisted and restored, so any re-run leg
    would otherwise duplicate its evidence and inflate the BEAT ranking, which sums `source_weight` over
    entries. (2) The adapter seam is a documented CONSUMER extension point returning arbitrary objects; a
    plain dict among them detonated later inside `_persist` (`'dict' object has no attribute 'to_dict'`),
    outside every boundary. Filtering to real `Signal`s here keeps that failure at the seam."""
    rejected = rejected if rejected is not None else []
    index = {_signal_key(s): i for i, s in enumerate(target)}
    for sig in incoming or []:
        if not _is_usable_signal(sig):
            # ⚠️ REPORTED, not a bare `continue`. Round 5 widened this reject set from "not a Signal at
            # all" (obviously broken wiring) to "a real Signal with one field of the wrong type" — which
            # is what a careful adapter author actually writes: a `rating` read straight out of JSON as
            # a string, an `aspect` that came back None. Every signal from such an adapter was dropped
            # with no log, no cause and no `partial`, producing a silent empty dossier: the exact
            # "empty market vs broken wiring" ambiguity a consumer reported and `degrade_causes` exists
            # to end. Its sibling twelve lines down flags an adapter EXCEPTION; this twin flagged nothing.
            logger.warning("competitor_intel.malformed_signal_dropped kind=%s", type(sig).__name__)
            rejected.append(sig)
            continue
        # ⚠️ CLAMP an out-of-range tier, do not DISCARD it — its restore twin (`_rehydrate_signals`)
        # clamps to "C" and keeps the signal, and an earlier round's comment claimed parity while the
        # seam deleted it instead. Opposite directions described as the same thing. Discarding is also a
        # breaking change to the documented adapter seam: `tier="a"` silently lost its evidence.
        if sig.tier not in _TIER_RANK:
            sig = replace(sig, tier="C")
        sig = _canonical_signal(sig)
        key = _signal_key(sig)
        at = index.get(key)
        if at is None:
            index[key] = len(target)
            target.append(sig)
        elif _TIER_RANK.get(sig.tier, 9) < _TIER_RANK.get(target[at].tier, 9):
            # Same evidence AND same sentiment, better provenance — take the higher tier, but MERGE
            # rather than overwrite.
            # ⚠️ A bare `target[at] = sig` was a data-loss regression. The module's own shipped adapter
            # hardcodes `sentiment="neutral"` (HN comments are unclassified), so a Tier-A unclassified
            # signal replaced a Tier-C NEGATIVE one and deleted a BEAT opening outright — measured
            # end-to-end: enabling a RICHER source made `beat_list` go from one corroborated opening to
            # empty, `partial=False`, no cause. Sentiment is now part of the key, so those two are
            # separate entries and this branch only fires for genuinely identical evidence; the merge is
            # the belt-and-braces that keeps a field the winner happens to lack.
            target[at] = replace(sig, rating=sig.rating if sig.rating is not None else target[at].rating)


def _safe_rating(value: Any) -> float | None:
    """A rating from a checkpoint, or ``None``. ``float()`` on a JSON integer too large for a C double
    raises ``OverflowError`` — an ``ArithmeticError``, not a ``ValueError`` — so a bare `float(rating)`
    escaped `run()` from inside a restore block whose docstring promises "*never a raise*"."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (OverflowError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


def _is_usable_usd(value: Any) -> bool:
    """Finite AND within the money bound — the gate for any Decimal this module is about to do
    ARITHMETIC on. ``_is_finite_decimal`` alone is not enough: `Decimal("1E+1000000")` is finite, and
    subtracting it traps `decimal.Overflow`. ``adjusted()`` is used rather than ``abs()`` because ``abs()``
    consults the decimal context and would raise on exactly the values being screened."""
    return _is_finite_decimal(value) and cast(Decimal, value).adjusted() <= _MAX_USD_ADJUSTED


# ── money: ONE orchestrator-level ceiling across ALL sub-calls ───────────────────────────────────────
#
# deep-research enforces its ceiling PER ``ResearchDeps`` as ``spent + est <= reserved_estimate x
# ceiling_factor`` (engine.py:216). This orchestrator makes MANY paid sub-calls, so N independent per-call
# ceilings would MULTIPLY spend. The cumulative total therefore lives HERE, is PERSISTED in the progress
# checkpoint (so a crash-resume does not re-grant the whole budget), and each sub-call is reserved
# ``remaining / ceiling_factor`` so the deep-research ceiling (reserved x factor) equals the true remaining
# — making ``total_budget_usd`` a HARD cap even with a >1 factor.
class _Budget:
    """The single injected USD total + a running-spend accountant, shared by every stage and persisted."""

    def __init__(self, total: Any) -> None:
        t = _to_decimal(total)
        self.total: Decimal = t if t > 0 else Decimal("0")
        self.spent: Decimal = Decimal("0")

    def remaining(self) -> Decimal:
        left = self.total - self.spent
        return left if left > 0 else Decimal("0")

    def charge(self, amount: Decimal) -> None:
        # ⚠️ MIXED coverage, stated per-clause because a whole-line claim was already stale once.
        #   * `amount > 0` is LIVE and TESTED — a leg reporting a credit/refund drives a negative delta
        #     here, and without this clause `spent` moves DOWNWARD and re-grants the ceiling
        #     (`test_a_NEGATIVE_engine_cumulative_cannot_refund_the_budget`).
        #   * `is_finite()` and the magnitude bound are defence-in-depth and currently UNKILLABLE: every
        #     caller is bounded upstream — the delta by `_is_usable_usd(shim.spent_usd)`, the worst-case
        #     charge by the total, `LlmMeter`'s estimate by `_to_decimal`. They stay because `spent` feeds
        #     `remaining()`, where an unbounded finite amount traps `decimal.Overflow` out of `run()`; one
        #     new unbounded caller makes them load-bearing.
        # An earlier version of this comment called the WHOLE line unkillable and marked that
        # "verified-by-mutation" — it was true when written and went stale the moment a later round added
        # the negative-refund test. A coverage claim in a comment decays; per-clause is the honest form.
        if amount.is_finite() and amount > 0 and amount.adjusted() <= _MAX_USD_ADJUSTED:
            self.spent += amount


# ── the duck-typed research deps shim (NOT a real deep_research.ResearchDeps) ─────────────────────────
#
# ``run_research`` reads its deps by attribute access only (``_validate_deps`` is attribute-based, no
# isinstance — engine.py:415), so this structural shim satisfies it. The last four fields are the ones
# ``run_research`` MUTATES in place (engine.py:457-459, :503): the true actual spend, credits, the
# ceiling-hit flag, and the checkpoint state.
@dataclass
class _ResearchDepsShim:
    llm: Any
    legs: Mapping[str, Any]
    scrape: Any
    leg_estimates: Mapping[str, Decimal]
    scrape_estimate: Decimal
    config: Any
    client: Any
    reserved_estimate: Decimal
    ceiling_factor: Decimal
    checkpoint_file: Path
    job_id: str
    spent_usd: Decimal = Decimal("0")
    credits: int = 0
    ceiling_hit: bool = False
    checkpoint_state: dict[str, Any] = field(default_factory=dict)


def _shim(
    deps: Deps, *, reserved: Decimal, ceiling_factor: Decimal, checkpoint_file: Path, job_id: str
) -> _ResearchDepsShim:
    # ``ceiling_factor`` is the CLAMPED factor the reservation was computed with — the engine must use the
    # SAME one (its ceiling is reserved x factor), else reserved x factor != remaining and the cap breaks.
    return _ResearchDepsShim(
        llm=deps.llm,
        legs=deps.legs,
        scrape=deps.scrape,
        leg_estimates=deps.leg_estimates,
        scrape_estimate=deps.scrape_estimate,
        config=deps.config,
        client=deps.client,
        reserved_estimate=reserved,
        ceiling_factor=ceiling_factor,
        checkpoint_file=checkpoint_file,
        job_id=job_id,
    )


# ── wiring pre-flight: fail LOUD before any research call ─────────────────────────────────────────────
#: The positional arities ``deps.llm`` is called at, and by whom. ``synth.py`` calls it with ONE part;
#: the injected deep-research engine calls it with TWO (``engine.py:257``/``:337``/``:401``). A callable
#: that cannot take both is the defect :func:`_preflight_llm_arity` exists to catch.
_LLM_ARITIES: tuple[tuple[int, str], ...] = ((1, "this module's synthesis tail"), (2, "the deep-research engine"))


def _preflight_llm_arity(llm: Any) -> str | None:
    """Return a problem string if ``llm`` cannot be called at BOTH arities the module uses, else None.

    Purely introspective — it never CALLS the callable, so it costs nothing and cannot spend money.
    ``inspect.signature`` fails on some builtins/C callables; that is not evidence of a defect, so an
    un-introspectable callable passes (fail-open on introspection, fail-closed on a proven mismatch).

    This exists because the failure it catches is invisible: a one-positional ``llm`` raises ``TypeError``
    *inside* :func:`_safe_research`'s never-raise boundary, so the run completes and returns an EMPTY
    dossier with ``partial=True`` — which reads as "this market has no competitors" rather than "your
    wiring is wrong". A consumer hit exactly that on a real, money-spending run (2026-08-26).
    """
    if not callable(llm):
        return f"deps.llm must be callable; got {type(llm).__name__}"
    if inspect.isclass(llm):
        # `callable(SomeClass)` is True and `signature(SomeClass)` describes `__init__`, so a class wired
        # where an instance belongs would be measured against the wrong signature and the message would
        # talk about `*parts` to someone whose actual mistake was forgetting the `()`.
        return f"deps.llm is the CLASS {llm.__name__}, not an instance — wire {llm.__name__}(...)"
    try:
        # ⚠️ `follow_wrapped=False` is load-bearing. The default follows `__wrapped__`, so a
        # `@functools.wraps` decorator reports the INNER signature — and the arity-ADAPTING wrapper this
        # module's own README recommends (`async def wrapper(*parts): return await fn("\n\n".join(parts))`)
        # was therefore REJECTED at entry while working perfectly at runtime. Breaking a working
        # deployment is a worse failure than missing one: this guard exists to catch the naive
        # `def my_llm(prompt)` that was actually reported, and it still does. Introspect the callable that
        # is actually invoked.
        sig = inspect.signature(llm, follow_wrapped=False)
    except Exception:  # noqa: BLE001 — see below; fail-open on ANY introspection failure
        # NOT `(TypeError, ValueError)`: `signature()` touches `__wrapped__`/`__signature__`/`__call__`,
        # and a lazy or DI-injected proxy raises whatever it likes from `__getattr__` (a real one raised
        # RuntimeError). A narrow catch let that escape `run()`, breaking the documented contract that
        # "the ONLY raise is a ValueError at entry" — and a consumer's `except ValueError:` would miss it.
        return None
    bad = [
        f"{n} ({who})" for n, who in _LLM_ARITIES if not _accepts_positionals(sig, n)
    ]
    if not bad:
        return None
    return (
        f"deps.llm cannot be called with {' or '.join(bad)} positional arg(s); its signature is "
        f"{sig}. Wire `async def my_llm(*parts: str, **kwargs) -> str` — ONE callable is used at both "
        f"arities. Left unchecked this raises inside the never-raise boundary and returns an EMPTY "
        f"dossier with partial=True."
    )


def _accepts_positionals(sig: inspect.Signature, n: int) -> bool:
    """True if ``sig`` binds EXACTLY ``n`` positional arguments and nothing else is owed.

    ``bind`` (not ``bind_partial``) on purpose: ``bind_partial`` tolerates MISSING arguments, so
    ``async def llm(prompt, payload)`` — two REQUIRED positionals — would pass a 1-arity probe and still
    blow up on ``synth.py``'s one-part call. ``bind`` rejects both too-many and too-few, which is the
    pair of directions that actually break.

    A required keyword-only parameter (``def llm(*parts, model)``) fails here too, and correctly so: the
    module never passes ``model``, so that callable cannot be driven by this module at any arity.
    """
    try:
        sig.bind(*(("",) * n))
    except TypeError:
        return False
    return True


def _preflight_research_fn(research_fn: Any) -> str | None:
    """Return a problem string if ``research_fn`` cannot take the module's call shape, else None.

    ``deps.llm`` was not the only injected callable in this failure class — it was just the one a consumer
    reported. ``research_fn`` is called exactly once, one way (``research_fn(brief, market, pack=…,
    deps=…)``), and a mismatch degrades EXACTLY the same way: ``TypeError`` inside the never-raise
    boundary, empty dossier, ``partial=True``. The realistic trigger is the one
    :func:`_preflight_wiring`'s docstring already names — vendoring a deep-research revision whose
    ``run_research`` signature has drifted.

    Same policy as the llm check: fail-open on any introspection failure, fail-closed on a proven
    mismatch, and never CALL the callable.
    """
    if not callable(research_fn):
        return f"deps.research_fn must be callable; got {type(research_fn).__name__}"
    if inspect.isclass(research_fn):
        # Same mistake, same bespoke message as the llm check — an asymmetric guard is how one of two
        # identical failure modes stays invisible.
        return (
            f"deps.research_fn is the CLASS {research_fn.__name__}, not an instance — "
            f"wire {research_fn.__name__}(...) or the module's `run_research` function"
        )
    try:
        sig = inspect.signature(research_fn, follow_wrapped=False)
    except Exception:  # noqa: BLE001 — fail-open on introspection; see _preflight_llm_arity
        return None
    try:
        sig.bind({}, "", pack=object(), deps=object())
    except TypeError as exc:
        return (
            f"deps.research_fn cannot be called as research_fn(brief, market, pack=…, deps=…) — {exc}. "
            f"Its signature is {sig}. Wire deep-research's `run_research`; if you vendored a newer "
            f"deep-research whose signature drifted, reconcile it (see the README Gotcha on revision sync)."
        )
    return None


def _preflight_wiring(pack: Pack, deps: Deps) -> None:
    """Mirror ``deep_research._validate_deps`` (engine.py:415) as a DETERMINISTIC pre-flight: every pack
    leg has an executor AND an estimate, scrape is wired, exactly ONE ``is_free`` leg, that free leg's
    estimate is a finite value <= 0 (the invariant that keeps the ceiling armed → bounds spend), and
    ``deps.llm`` accepts both arities the module calls it at (:func:`_preflight_llm_arity`).

    Run BEFORE any research call and OUTSIDE the never-raise boundary: a wiring gap is a caller bug that
    must fail loud (a missing estimate would silently disable the ceiling → unbounded spend), and doing it
    here — rather than re-raising a mid-staging ``ValueError`` — avoids mis-classifying an injected LLM's
    own ``ValueError`` (``run_research`` leaves the stage-1/3 ``deps.llm`` calls unwrapped) as wiring.

    ⚠ This is a hand-mirror of a SPECIFIC deep-research revision. If you vendor a newer deep-research whose
    ``_validate_deps`` adds a check, that check fires inside ``run_research`` and is caught+degraded here as
    a staging failure (masking a wiring bug). Keep the two in sync (README Gotcha)."""
    leg_names = {leg.name for leg in pack.legs}
    problems: list[str] = []
    if missing_exec := leg_names - set(deps.legs):
        problems.append(f"deps.legs missing executors for {sorted(missing_exec)}")
    if missing_est := leg_names - set(deps.leg_estimates):
        problems.append(f"deps.leg_estimates missing {sorted(missing_est)}")
    if deps.scrape is None:
        problems.append("deps.scrape is required")
    if llm_problem := _preflight_llm_arity(deps.llm):
        problems.append(llm_problem)
    if rf_problem := _preflight_research_fn(deps.research_fn):
        problems.append(rf_problem)
    free = [leg for leg in pack.legs if leg.is_free]
    if len(free) != 1:
        problems.append(f"pack must declare exactly ONE is_free leg, found {len(free)}")
    else:
        free_est = deps.leg_estimates.get(free[0].name)
        if free_est is not None:
            # accept Decimal | int | float (all engine-usable), reject only NaN/inf/garbage or a POSITIVE
            # estimate — don't false-positive a valid `0` / `0.0` free estimate (the engine does `est > 0`).
            try:
                est_d = free_est if isinstance(free_est, Decimal) else Decimal(str(free_est))
            except (InvalidOperation, ValueError, TypeError):
                problems.append(f"the free leg {free[0].name!r} estimate must be a number <= 0; got {free_est!r}")
            else:
                if not est_d.is_finite():
                    problems.append(f"the free leg {free[0].name!r} estimate must be finite and <= 0; got {free_est!r}")
                elif est_d > 0:
                    problems.append(f"the free leg {free[0].name!r} must have leg_estimate <= 0; got {free_est}")
    if problems:
        raise ValueError("competitor-intel deps wiring error: " + "; ".join(problems))


def _pack(deps: Deps, name: str) -> Pack:
    """Load a shipped pack via the injected ``load_pack`` (yields a method-bearing ``PackData``) and
    wiring-check it. Both a load failure and a wiring gap fail LOUD as ``ValueError`` here, OUTSIDE the
    never-raise boundary (a broken pack/wiring is a caller bug, not a staging degradation)."""
    try:
        pack = deps.load_pack(_PACKS_DIR / f"{name}.yaml")
    except ValueError:
        raise  # PackError (a ValueError) or an explicit ValueError — already the right shape
    except Exception as exc:  # normalize FileNotFoundError / YAMLError / etc. → the documented ValueError
        raise ValueError(f"competitor-intel: pack {name!r} failed to load: {exc}") from exc
    _preflight_wiring(pack, deps)
    return pack


# ── never-raise research boundary ────────────────────────────────────────────────────────────────────
async def _safe_research(
    deps: Deps, brief: Mapping[str, Any], market: str, *, pack: Pack, shim: _ResearchDepsShim, label: str
) -> tuple[dict[str, Any], bool, str]:
    """Wrap ONE ``run_research`` call so a staging failure (network/LLM/parse — incl. a ``ValueError`` the
    injected LLM raises, which ``run_research`` does not wrap) degrades to a flagged-empty result rather
    than raising. Wiring is already proven by :func:`_preflight_wiring`, so catching ``ValueError`` here is
    correct (it can only be staging). Returns ``(doc, ok, cause)``; ``ok`` is False on degradation and
    ``cause`` is the exception CLASS NAME (``""`` when ok) so the caller can surface it on the Dossier —
    a log line alone is invisible to a consumer running with logging off, which is how the reported
    defect stayed undiagnosable."""
    try:
        doc = await deps.research_fn(brief, market, pack=pack, deps=shim)
        # ⚠️ Validate the RETURN SHAPE, not only the signature. `_preflight_wiring` proves the callable can
        # be CALLED; nothing proved what it hands back. Every consumer of this result then does
        # `res.doc.get("cards", …)` and iterates it, at four sites, all OUTSIDE any boundary — so a
        # wrapper that forgot its `return` (the README recommends wrappers) escaped `run()` as
        # `AttributeError: 'NoneType' object has no attribute 'get'`, AFTER the leg was billed and BEFORE
        # any checkpoint write, losing the spend record entirely. `{"cards": 7}` escaped as `TypeError`.
        # Neither is a `ValueError`, so the documented `except ValueError:` misses both.
        # A drifted shape is a DEGRADE with a named cause, exactly like a network failure.
        if not isinstance(doc, dict) or not isinstance(doc.get("cards", []), list):
            logger.warning(
                "competitor_intel.research_degraded label=%s cause=%s", label, "MalformedResearchDoc"
            )
            return {"cards": []}, False, "MalformedResearchDoc"
        return doc, True, ""
    except Exception as exc:  # noqa: BLE001 — the never-raise boundary is the whole point (deep-research idiom)
        # The exception TYPE, deliberately — never `exc` / `repr(exc)`. A degraded leg's message can carry
        # a scraped page, an API key echoed by a client library, or an unprintable payload; the class name
        # is bounded, safe, and is the one bit that separates a wiring bug (TypeError/AttributeError) from
        # a network blip (httpx.*) from a bad key (HTTPStatusError). Logging only the label made a real
        # consumer defect undiagnosable — they could not tell an empty market from a broken wiring.
        logger.warning(
            "competitor_intel.research_degraded label=%s cause=%s", label, type(exc).__name__
        )
        return (
            {"cards": [], "degraded_legs": ["all"], "truncated": False, "status": "error"},
            False,
            type(exc).__name__,
        )


@dataclass
class _StageResult:
    doc: dict[str, Any]
    ok: bool
    truncated: bool  # skipped for budget, OR the sub-call hit its ceiling
    #: True when the ENGINE was actually invoked. ``truncated`` cannot answer this — it conflates two
    #: opposite states: *skipped for budget, never called* (retry it, nothing was paid for) and *called,
    #: delivered cards, hit the engine's per-call ceiling* (do NOT retry — it ran and was billed). Phase B
    #: keyed the done-flags on ``not truncated`` and so retried BOTH, which duplicated review signal and
    #: let a later budget-exhausted resume overwrite a paid-for competitor list with ``[]``.
    #:
    #: ⚠️ REQUIRED, deliberately — no default. Both construction sites already pass it explicitly, so any
    #: default is dead code that no test can kill; but the wrong default is a money bug waiting for the
    #: third construction site. `True` would mean "assume we spent" → the done-flag marks a leg complete
    #: that never ran; `False` would mean "assume we did not" → a billed leg is retried and re-charged.
    #: Neither is safe to guess, so the field forces the author to answer.
    ran: bool
    cause: str = ""  # exception CLASS NAME when this leg degraded, else "" (never a message)
    #: True when this sub-call's ledger watermark was ABOVE its reported cumulative — i.e. the engine's
    #: checkpoint reset and it restarted from zero. Carries the reset to `run()` for the MANDATORY legs;
    #: the optional stages use their `causes` sink instead (they never return a _StageResult to `run()`).
    ledger_reset: bool = False


async def _run_leg(
    deps: Deps,
    budget: _Budget,
    brief: Mapping[str, Any],
    market: str,
    *,
    pack: Pack,
    stage: str,
    slug: str,
    charged: dict[str, str],
) -> _StageResult:
    """One budgeted, checkpointed, never-raising research sub-call. Reserves ``remaining / ceiling_factor``
    (so the engine's ceiling ``reserved x factor`` equals the true remaining → total is a HARD cap even
    with a >1 factor), charges the true actual afterward, and flags truncation. A non-finite reported spend
    is charged at the full reservation (conservative — never under-count real dollars)."""
    remaining = budget.remaining()
    if remaining <= 0:
        # exhausted — skip, don't call. `ran=False` is what tells `run()` this leg was never billed, so
        # the done-flags retry it and the caller must NOT treat its empty `cards` as a real result.
        return _StageResult(doc={"cards": []}, ok=True, truncated=True, ran=False)
    # factor must be a sane finite multiplier; an out-of-range value (incl. a pathological tiny one that
    # would overflow the division) falls back to 1 rather than raising out of the never-raise contract.
    cf = deps.ceiling_factor
    factor = cf if _is_finite_decimal(cf) and Decimal("0.000001") <= cf <= Decimal("1000000") else Decimal("1")
    reserved = remaining / factor
    shim = _shim(
        deps,
        reserved=reserved,
        ceiling_factor=factor,  # SAME clamped factor the engine multiplies by → reserved x factor == remaining
        # ⚠️ JOB-SCOPED. The ownership guard below already carries the job, but the FILENAME did not —
        # so two jobs sharing one `checkpoint_dir` wrote the same file, each discarding and overwriting
        # the other's. That reset is what makes a reported cumulative come back BELOW our watermark.
        # `_ck`, not `_slug`: `_slug` collapses every non-ASCII-alphanumeric job_id to "x", which would
        # let two distinct jobs share a filename and defeat the scoping this line exists for.
        # Migration: an in-flight sub-call checkpoint orphans ONCE, re-runs, and is correctly charged.
        checkpoint_file=deps.checkpoint_dir / f"{_ck(deps.job_id, '')}-{stage}-{slug}.json",
        job_id=f"{deps.job_id}:{stage}:{slug}",
    )
    doc, ok, cause = await _safe_research(
        deps, brief, market, pack=pack, shim=shim, label=f"{stage}:{slug}"
    )
    # ⚠️ `reset` MUST be initialized here, not only in the branch that sets it. This block runs AFTER
    # `_safe_research` returns — i.e. OUTSIDE the never-raise boundary — so an unbound name would raise
    # `UnboundLocalError` straight out of `run()` on every normal call. Neither ruff nor mypy --strict
    # flags possibly-unbound here.
    reset = False
    # ⚠️ MAGNITUDE, not just finiteness. `shim.spent_usd` is the ONE money value that arrives from
    # outside this module — the engine sets it from its own on-disk sub-call checkpoint behind only an
    # `is_finite()`/`< 0` guard (`engine.py:453-457`), so a corrupt file's `"1E+1000000"` flows straight
    # in. Two defects lived in the gap between "finite" and "usable", and BOTH were introduced by the
    # magnitude screen added earlier in this same review, which covered every other Decimal entry point
    # and missed this one:
    #   * `delta = reported - prev` trapped `decimal.Overflow` — an `ArithmeticError`, so it escaped
    #     `run()` past a consumer's documented `except ValueError:`; and
    #   * for a merely absurd (sub-`Emax`) value, `_Budget.charge` silently refused the amount while
    #     `charged[key] = str(reported)` still advanced the watermark — an under-charge, which is an
    #     over-spend primitive. Measured `spend_usd=0, partial=False, status="ok"` for three billed legs.
    # Routing an unusable magnitude down the SAME branch as a non-finite report restores one rule for the
    # whole class: an unreadable spend report is charged at the full reservation and named as a cause.
    if _is_usable_usd(shim.spent_usd):
        # ⚠️ INSIDE the finite guard, never before it: `Decimal("NaN") >= x` RAISES InvalidOperation.
        # The engine's `spent_usd` is that sub-call's CUMULATIVE (engine.py:454-458), and a completed
        # checkpoint returns it early having spent nothing (:472) — so charging it whole re-bills the
        # entire history every resume. Charge the DELTA against what we already charged for this key.
        key = f"{stage}:{slug}"
        reported = shim.spent_usd
        # Clamped at 0, exactly as the engine clamps its own resumed value (`engine.py:455`).
        # `_to_decimal` neutralises NaN/garbage but NOT a negative: a corrupt `-99` watermark would make
        # `reported - prev` charge `reported + 99`, exhausting the whole budget from one bad key. An
        # over-charge is the fail-safe direction only while it is BOUNDED by what was really reported.
        raw_prev = charged.get(key, "0")
        # ⚠️ NOW UNREACHABLE FROM `run()`, and said so rather than left reading as live. A later round
        # added a run()-level `ledger_entry_unreadable` sweep that fails the whole job closed BEFORE any
        # leg executes, so an unreadable watermark is caught one level up and this branch never parses
        # it. Verified: with a corrupted `charged` entry, deleting this branch produces byte-identical
        # output (`partial=True`, `causes=['LedgerReset','SpendTotalUnreadable']`) and
        # `competitor_intel.ledger_unreadable` logs in NEITHER. It is kept as defence for a future
        # caller of `_run_leg` that does not go through that sweep — but a comment describing a dead
        # branch as the thing that catches the corruption is exactly the false-coverage claim this file
        # has now been wrong about eight times.
        #
        # An UNPARSEABLE watermark is a LOST ledger entry, not "never charged" — a bare `_to_decimal`
        # returns 0 for junk, which silently re-bills that sub-call's whole history with `partial=False`
        # and no cause: the exact 0.20 -> 0.30 -> 0.40 regression this ledger exists to end, made
        # invisible. Treat it as a reset, which is what it is.
        #
        # ⚠️ Ask whether it PARSED, never whether its STRING matches a list of zeros. This was
        # `str(raw_prev) not in {"0", "0.0", "0.00"}`, and `charged[key] = str(reported)` stores whatever
        # the engine's Decimal accumulation produced — `"0.000"`, `"0.0000"`, `"0E-7"` are all reachable
        # from a free or zero-cost leg and none are in that list. Every such job was flagged
        # `LedgerReset` + `partial=True` on EVERY resume, permanently, pointing an investigating consumer
        # at a money bug that never happened. A value question answered with a string test.
        parsed_prev = _decimal_or_none(raw_prev)
        if parsed_prev is None:
            prev = Decimal("0")
            if key in charged:
                reset = True
                logger.warning("competitor_intel.ledger_unreadable label=%s:%s", stage, slug)
        elif parsed_prev < 0:
            # NOT necessarily corruption: a leg executor returning a credit/refund drives the engine's
            # cumulative negative, and THIS module then writes the negative watermark itself. It is
            # perfectly readable, so it must not be logged as unreadable. Clamp so `reported - prev`
            # cannot inflate the charge by |prev|, and say what actually happened.
            prev = Decimal("0")
            logger.warning("competitor_intel.ledger_negative label=%s:%s", stage, slug)
        else:
            prev = parsed_prev
        if reported >= prev:
            delta = reported - prev
        else:
            # Reported BELOW our watermark ⇒ the sub-call's checkpoint reset and the engine restarted
            # from zero, spending real money. A `max(…, 0)` clamp here would charge NOTHING — an
            # over-spend primitive, the opposite of the bug this fixes. When the ledger is ambiguous,
            # OVER-charge: the budget is a safety bound.
            delta = reported
            reset = True
            logger.warning("competitor_intel.ledger_reset label=%s:%s", stage, slug)
        # ⚠️ DETECTABILITY LIMIT — and the bound is NOT "once". A reset is visible only when the restart
        # spends LESS than the watermark; a restart spending the SAME or MORE reports `reported >= prev`
        # and is indistinguishable from a normal resume. If the reset cause RECURS — an ephemeral
        # checkpoint volume, a retention sweeper, a partial restore — the same sub-call re-spends the same
        # amount every run, `reported == prev` every time, and the under-charge is UNBOUNDED and silent:
        # no reset is logged, no cause is recorded, `partial` stays False, and `total_budget_usd` stops
        # bounding real spend. Job-scoping removed the in-module cause (a sibling clobbering the file);
        # what remains needs an external deleter, which this module cannot observe without reading the
        # engine's private checkpoint format — deliberately rejected (it would couple us to a layout the
        # engine owns). **A consumer whose checkpoint_dir is not durable must not rely on the ceiling.**
        budget.charge(delta)
        charged[key] = str(reported)  # the ledger holds only ENGINE-REPORTED cumulatives
        degraded_spend = False
    else:
        budget.charge(remaining)  # broken/NaN spend report → assume worst case (it could have spent it all)
        degraded_spend = True
        logger.warning("competitor_intel.nonfinite_spend label=%s:%s", stage, slug)
        # A SYNTHETIC cause: research succeeded, so `cause` is empty, but this path sets `ok=False` and
        # charges the FULL remaining budget — the most expensive degradation in the module, and it was
        # producing a `partial=True` with nothing to explain it.
        cause = cause or "NonFiniteSpendReport"
    return _StageResult(
        doc=doc,
        ok=(ok and not degraded_spend),
        truncated=bool(shim.ceiling_hit),
        cause=cause,
        ledger_reset=reset,
        ran=True,  # past the budget short-circuit ⇒ the engine WAS invoked and this leg was billed
    )


# ── orchestrator-level progress checkpoint (top-level; distinct from each sub-call's own) ──────────────
def _hash(value: str) -> str:
    # non-security file-name/dedup key; usedforsecurity=False clears BOTH ruff S324 AND bandit B324
    # (a bare ruff-suppression comment silences ruff only, leaving the module gate red on bandit B324).
    # ⚠️ `errors="surrogatepass"`, not a bare encode. A lone surrogate in a consumer-supplied `job_id`
    # (routine from `bytes.decode(..., "surrogateescape")` or `os.fsdecode`) makes a plain encode raise
    # UnicodeEncodeError — which IS a ValueError subclass, so it escapes `run()` and a consumer's
    # `except ValueError:` mis-reads it as the documented entry-time WIRING bug. Every other `_hash` call
    # site sits inside a try/except; the checkpoint-filename one added in this change did not.
    return hashlib.sha1(
        value.encode("utf-8", errors="surrogatepass"), usedforsecurity=False
    ).hexdigest()[:8]


def _progress_file(deps: Deps) -> Path:
    # job_id hash makes the filename distinct even when two job_ids slug identically.
    return deps.checkpoint_dir / f"{_slug(deps.job_id)}-{_hash(deps.job_id)}-progress.json"


def _load_progress(deps: Deps) -> dict[str, Any]:
    """Load this job's progress, discarding a corrupt file OR one owned by a different job_id (the
    ownership guard mirrors deep-research's checkpoint double-book guard). Never raises.

    ⚠️ A file that EXISTS but cannot be read returns ``{"_unreadable": True}``, not a bare ``{}``. An
    empty dict says "fresh job, nothing spent"; a torn file says "this job spent an unknown amount and
    the record is gone". Collapsing the two was a money-laundering path: the sticky
    ``spend_baseline_lost`` marker lives IN the file, so tearing the file cleared the marker, the causes,
    `partial` and the whole ledger, and the next run re-entered every leg reporting `status="ok"`.
    Round 4 closed the "a smaller total redefines the guess" path and left this one — which is the
    SUPERSET, and likelier, since one bad byte anywhere in the JSON reaches it. Same
    ``_to_decimal``-vs-``_decimal_or_none`` distinction this file already makes one level down: unknown
    is not zero.

    A MISSING file still returns ``{}`` — that genuinely is a fresh job, and treating it as a lost
    baseline would brick every first run."""
    path = _progress_file(deps)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        try:
            existed = path.exists()
        except OSError:  # pragma: no cover - a stat failure is itself "cannot read"
            existed = True
        return {"_unreadable": True} if existed else {}
    if not isinstance(data, dict):
        return {"_unreadable": True}  # a valid-JSON non-dict is a written file we cannot use
    if data.get("job_id") != deps.job_id:
        return {}  # a DIFFERENT job's file — ours is simply absent, which is a fresh job
    # sanitize sub-fields so a tampered / version-migrated OWNED file can't crash run() (never-raise):
    # competitors must be a list, reviews_done a dict; spent_usd/discovery_done are coerced at use.
    # ⚠️ Record what we are about to SANITIZE AWAY, before we do it. `_load_progress` repairs
    # `competitors` and `reviews_done` in place, so a shape check performed by `run()` afterwards sees
    # already-clean values and can never report the loss — the detection has to live where the
    # destruction happens.
    data["_dropped_fields"] = sorted(
        k for k, typ in (("competitors", list), ("reviews_done", dict))
        if k in data and data.get(k) is not None and not isinstance(data.get(k), typ)
    )
    comps = data.get("competitors")
    # ⚠️ NOT `comps is not None`. An explicit `null` and an absent key are two of the four corruption
    # shapes, and both produced exactly the failure this guard was written to stop: discovery skipped,
    # the engine never called, `competitors: []` written BACK and permanent for that job_id. An explicit
    # empty LIST is different — that is a legitimately empty market and must be preserved.
    if not isinstance(comps, list) and data.get("discovery_done") is True:
        # ⚠️ Its partner flag `discovery_done` is deliberately fail-CLOSED (`is True` ⇒ anything else
        # re-runs), and nothing reconciled the two: a corrupt `competitors` with `discovery_done=True`
        # skipped discovery, iterated no reviews, and `_persist()` wrote `competitors: []` BACK — making
        # the loss permanent for that job_id and reporting `status="empty"`, `partial=False`, i.e. "this
        # market has no competitors" for a rival list the consumer was already billed for.
        # Its two sanitizer siblings (`reviews_done`, the per-entry `charged` guard) both fail closed;
        # this was the odd one out. Clearing the done-flag makes the corruption RECOVERABLE by re-running
        # discovery rather than durable.
        data["discovery_done"] = False
    data["competitors"] = comps if isinstance(comps, list) else []
    rd = data.get("reviews_done")
    data["reviews_done"] = rd if isinstance(rd, dict) else {}
    return cast(dict[str, Any], data)


def _save_progress(deps: Deps, state: Mapping[str, Any]) -> str:
    try:
        deps.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        # ATOMIC: temp file + os.replace, mirroring deep-research's own checkpoint writer. A bare
        # write_text can tear on a crash or a full disk, and `_load_progress` fails OPEN on a corrupt
        # file — so a torn write silently re-grants the WHOLE budget on the next resume, which is the
        # opposite of what this file exists to guarantee (and of what the README promises). The
        # The PID-unique temp name separates two racing PROCESSES. It gives ZERO isolation between two
        # racers in the SAME process (async tasks / threads), which necessarily share both the target and
        # the PID: measured 380 of 800 concurrent saves failing with FileNotFoundError as they unlink
        # each other's temp file. `os.replace` still keeps the published file un-torn — that guarantee
        # holds — but a lost save is a lost spend record, so one live `run()` per job_id is a caller
        # obligation this module cannot enforce (README Gotchas).
        target = _progress_file(deps)
        tmp = target.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(state), encoding="utf-8")
        os.replace(tmp, target)
    except (OSError, TypeError, ValueError) as exc:
        # Log-only is a real gap on the MONEY path — a read-only volume or a full disk silently disables
        # the module's one cumulative-spend record, and a consumer running without logging sees nothing.
        # The caller has no dossier here, so the cause is returned for the caller to record.
        logger.warning("competitor_intel.progress_save_failed cause=%s", type(exc).__name__)
        return type(exc).__name__
    return ""


def _netloc(url: str) -> str:
    """The registrable host of a url, or "" — never raises (``urlparse`` raises ValueError on a malformed
    IPv6-looking netloc, and card urls come from the LLM-influenced research engine, not caller wiring)."""
    try:
        return urlparse(url).netloc
    except ValueError:
        return ""


def _slug(value: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "-", value.strip().lower()).strip("-")
    return s[:80] or "x"


def _ck(name: str, url: str) -> str:
    """A STABLE, collision-safe key for a competitor (checkpoint slug + reviews_done key + the money
    ledger). ``_slug`` alone collapses punctuation variants AND every non-ASCII-alphanumeric name to
    ``"x"`` (silent data loss when two rivals collide); the name+url hash disambiguates while staying
    deterministic across resumes.

    ⚠️ The hash input is **LENGTH-PREFIXED**, and that prefix is the whole point. A bare ``name + "|" +
    url`` separator is AMBIGUOUS — ``("Foo|", "")`` and ``("Foo", "|")`` are different competitors whose
    concatenation is byte-identical, so they collided into one key. That key drives ``reviews_done``, the
    sub-call checkpoint filename AND (since the delta ledger) the ``charged`` entry, so the collision
    silently dropped one rival's review mining inside a SINGLE run — ``partial`` False, no cause, output
    indistinguishable from a correct run. This module's own README already names ``|`` as a separator that
    *"routinely"* occurs in scraped competitor names and enforces a safe one in ``synth.key_safe``; ``_ck``
    was the last key namespace still trusting a bare delimiter. The prefix states where ``name`` ends, so
    no other split can reproduce the input.

    *Migration:* the key changes, so an in-flight job's sub-call checkpoints orphan ONCE, re-run and are
    correctly charged — the same one-time cost as the job-scoped filenames, and taken in the same release
    so a consumer pays it once rather than twice."""
    return f"{_slug(name)}-{_hash(f'{len(name)}|{name}|{url}')}"


def _load_source_profile(product_type: str) -> dict[str, Any]:
    """The product-type source profile (review venues + query-site patterns) — DATA, not code. Resolves a
    common fabrik scaffold-type alias first. A missing file, malformed YAML, or unknown type degrades to an
    empty profile (Tier-C with no venue hint) with a warning — never a raise."""
    key = _PRODUCT_TYPE_ALIASES.get(product_type, product_type)
    try:
        import yaml  # type: ignore[import-untyped, unused-ignore]  # local: PyYAML is the only core dep

        raw = yaml.safe_load((_PACKS_DIR / "source-profiles.yaml").read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — best-effort loader; a malformed profile must NOT break the run
        logger.warning("competitor_intel.source_profiles_load_failed cause=%s", type(exc).__name__)
        return {}
    if not isinstance(raw, dict):
        return {}
    profile = raw.get(key)
    if not isinstance(profile, dict):
        logger.warning("competitor_intel.unknown_product_type type=%s", product_type)
        return {}
    return profile


# ── public entrypoint ─────────────────────────────────────────────────────────────────────────────────
async def run(
    us: Us | None,
    market: str,
    *,
    product_type: str,
    deps: Deps,
    enable_pricing: bool = False,  # Phase B stage — accepted here, wired in Phase B
    enable_white_space: bool = False,  # Phase B stage — accepted here, wired in Phase B
) -> Dossier:
    """Produce a match-then-beat :class:`Dossier` for ``market`` (Phase A: discover + mine reviews).

    ``us`` OPTIONAL: a defined product drives us-vs-them (Phase B); ``us=None`` is greenfield
    (category landscape). Never raises for a money/staging reason — a failed leg/competitor degrades the
    dossier to partial-with-flag, money exhaustion sets ``truncated``. The ONLY raise is a ``ValueError``
    at entry on a caller WIRING bug (bad/missing leg estimate, missing executor, malformed pack).
    """
    # wiring validation at ENTRY — checkpoint_dir/job_id are load-bearing (the progress file + double-book
    # guard key on them); a bad type would raise TypeError deep in run(), so fail LOUD as the documented
    # ValueError here instead.
    if not isinstance(deps.checkpoint_dir, Path) or not isinstance(deps.job_id, str) or not deps.job_id.strip():
        raise ValueError(
            "competitor-intel deps wiring error: checkpoint_dir must be a Path and job_id a non-empty str"
        )
    progress = _load_progress(deps)  # job_id-verified; {} if absent/foreign/corrupt
    budget = _Budget(deps.total_budget_usd)
    # ⚠️ The LEDGER is restored before the TOTAL, because it is the only honest floor under the total.
    # `charged` holds per-sub-call engine-reported cumulatives, so their sum is a real lower bound on
    # money already spent. This ordering is what closes the asymmetry below.
    raw_charged = progress.get("charged")
    charged: dict[str, str] = (
        # `and k`: an empty key can never be produced by `f"{stage}:{slug}"`, but a hand-edit or a
        # migration can put one in the file, where it would shadow nothing and confuse the floor.
        {k: str(v) for k, v in raw_charged.items() if isinstance(k, str) and k}
        if isinstance(raw_charged, dict)
        else {}
    )
    # ⚠️ A corrupt CONTAINER is a strictly LARGER corruption than a corrupt VALUE, and it failed OPEN
    # while the value failed CLOSED — the ninth sibling pair in this file. Replacing a non-dict `charged`
    # with `{}` makes `ledger_floor` 0, which is precisely the floor `max(parsed_spent, ledger_floor)`
    # relies on to catch a `spent_usd` torn downward: measured 1.20 of real spend against a 0.60 ceiling,
    # reported `partial=False`, `status="ok"`, no causes. A ledger we cannot read is a baseline we do not
    # have — the same sentence the per-value branch already acts on.
    ledger_container_unreadable = raw_charged is not None and not isinstance(raw_charged, dict)
    _ledger_container_lost = ledger_container_unreadable  # read by `_persist`'s no-clobber guard
    ledger_floor = Decimal("0")
    ledger_entry_unreadable = False
    for _v in charged.values():
        _d = _decimal_or_none(_v)
        if _d is None:
            # ⚠️ Flagged, not silently skipped. The IDENTICAL corruption inside `_run_leg` fires
            # `LedgerReset` + `partial`; here it just vanished from the floor — and when that key's leg
            # is already done-flagged, `_run_leg` never runs, so the twin can never surface it. Measured:
            # real spend 0.90, floor restored as 0.60, `partial=False`, no cause — 0.30 forgiven.
            # ⚠️ The MONEY direction, not just the flag. Round 4 added the cause and left the floor
            # forgiving the entry: it contributed 0, so a corrupted entry made 0.30 of real spend
            # SPENDABLE again — measured, the corrupted case ran a billable leg the intact case refused,
            # for 0.90 of real spend against a 0.60 ceiling. Meanwhile the IDENTICAL corruption inside
            # `_run_leg` charges the full reported cumulative. Same file, same torn write, opposite
            # directions — the seventh such sibling pair found in this review. A ledger we cannot read is
            # a baseline we do not have, which is exactly the `spent_usd` case one field over.
            ledger_entry_unreadable = True
            continue
        if _d > 0:
            ledger_floor += _d
    # ⚠️ An UNREADABLE total must not read as "spent nothing". `_to_decimal` returns 0 for junk, so a
    # single corrupt byte in `spent_usd` re-granted the ENTIRE budget — and because the `charged` ledger
    # survived intact, every already-paid sub-call then charged a delta of 0, so the run sailed past
    # `total_budget_usd` reporting `partial=False`, `status="ok"` and no cause. Measured: 0.90 of real
    # spend against a 0.60 ceiling, reported clean.
    #
    # The ledger one level down already treats an unreadable watermark as a reset (fail-CLOSED); this
    # field is far more load-bearing and was the one left failing OPEN. Same corruption population, same
    # torn write, opposite direction. Now: fall back to the ledger floor and SAY so.
    raw_spent = progress.get("spent_usd", "0")
    parsed_spent = _decimal_or_none(raw_spent)
    # ⚠️ Recorded on the DOSSIER, not merely logged — the same doctrine every sibling corruption path in
    # this module already follows (`ledger_unreadable` → `LedgerReset` + `partial`; a `_save_progress`
    # failure → `partial` + a cause). This one shipped log-ONLY, and it is the most load-bearing of them:
    # a consumer whose budget baseline was just silently reset to the ledger floor got a dossier
    # indistinguishable from a clean run. A consumer running without logging had no way to know at all.
    # ⚠️ STICKY. `budget.spent = budget.total` is a GUESS pinned to THIS run's total, and `_persist()`
    # then writes it out as `spent_usd` — a guess recorded as a measurement. A smaller intervening total
    # silently redefines it DOWNWARD and the budget is re-granted: measured 1.00 spent, resumed at
    # total=0.10 (a bad env parse is enough), persisted 0.10, and the next run at 1.00 re-billed every
    # leg. The fail-closed guard survived exactly one run and was revisable downward.
    # So the LOST-BASELINE condition itself is persisted, and it outranks any number in the file.
    # Recovery is a FRESH job_id, not a raised budget — see the README. That costs a re-run; laundering
    # costs unbounded silent spend, and "an under-charge is an over-spend primitive" decides it.
    spend_total_unreadable = (
        progress.get("spend_baseline_lost") is True
        # a checkpoint that EXISTS but could not be read is a lost baseline, not a fresh job — see
        # `_load_progress`. Distinguishing "absent" from "unreadable" is the same `_to_decimal` vs
        # `_decimal_or_none` doctrine this file states one level down, applied one level up.
        or progress.get("_unreadable") is True
    )
    if ledger_entry_unreadable or ledger_container_unreadable:
        spend_total_unreadable = True
    if parsed_spent is None:  # the `is None` test stays INLINE so mypy narrows the else-branch
        spend_total_unreadable = True
        # ⚠️ EXHAUSTED, not the ledger floor. The previous round made the floor load-bearing here without
        # making it COMPLETE, and it is structurally incapable of being a floor on total spend:
        #   * `charged[key] = str(reported)` REPLACES rather than accumulates, so a reset rewrites a
        #     watermark DOWNWARD — measured 0.50 of real spend forgotten by the ledger;
        #   * synthesis spend never enters `charged` at all (`LlmMeter` charges the budget directly);
        #   * the worst-case charge on the unusable-report branch is not recorded either — the single
        #     most expensive charge in the module leaves no trace in the ledger.
        # All three fail OPEN, and the floor is weakest exactly when it becomes load-bearing: the same
        # incident that loses a checkpoint is what damages this file. When the total is unreadable this
        # module genuinely does not know what was spent, and "an under-charge is an over-spend primitive"
        # is the doctrine everywhere else in this file. So: assume the budget is gone, say so on the
        # dossier, and let the consumer decide (raise the budget, or start a fresh job_id).
        budget.spent = budget.total
        # No `if progress:` guard — it was DEAD. `parsed_spent is None` requires the key to be present,
        # which requires a real checkpoint, so `progress` is necessarily truthy here. The guard could
        # never be False, and its comment asserted a case that cannot occur.
        logger.warning("competitor_intel.spend_total_unreadable job=%s", _slug(deps.job_id))
    elif spend_total_unreadable:
        # readable NUMBER, but the file records that the baseline was lost — the marker wins.
        budget.spent = budget.total
    else:
        # `max`, not the parsed value: this also catches a total corrupted DOWNWARD (or one written by an
        # older build that predates the ledger) without ever crediting money back.
        budget.spent = max(parsed_spent if parsed_spent > 0 else Decimal("0"), ledger_floor)
    dossier = Dossier(market=market, product_type=product_type)
    # restore the mined review signal + degradation flags across a resume — else a resumed run skips
    # already-done competitors (reviews_done) and synthesizes on an EMPTY signal → a hollow BEAT/matrix.
    # ⚠️ Restored THROUGH `_extend_signals`, not assigned raw. Its sibling six lines down already states
    # the doctrine — *"A restore must re-establish the invariant, not assume the file on disk already
    # satisfies it"* — and this line did exactly what that comment forbids. A checkpoint written before
    # the append became idempotent carries the documented 2->4->6->8 duplication, and `_extend_signals`
    # cannot remove what is ALREADY in `target`: the inflated BEAT weight was re-persisted every run and
    # would have been permanent for every consumer mid-job at upgrade time.
    _restore_dropped: list[Any] = []
    _extend_signals(
        dossier.review_signal, _rehydrate_signals(progress.get("review_signal")), _restore_dropped
    )
    dossier.partial = bool(progress.get("partial"))
    # …and the causes behind that flag. `isinstance`-guarded per element: the checkpoint is a file on
    # disk that a crash can truncate or a hand-edit can corrupt, and a restore must never raise.
    # (The per-sub-call `charged` ledger is restored ABOVE, before the spend total, because it is the
    # floor that total falls back to. Its container-type guard comes FIRST, then the per-element filter:
    # a checkpoint carrying `"charged": ["abc"]` would make `dict(...)` raise ValueError mid-run AFTER
    # money is spent, and a consumer's `except ValueError:` would mis-read that as the documented
    # entry-time wiring bug. Absent key ⇒ `{}`: a pre-upgrade checkpoint resumes, it does not crash.)
    # ⚠️ A SYSTEMIC guard, not another one-at-a-time patch. Enumerating every corruptible checkpoint
    # field (36 shapes across 9 fields, executed) showed the money fields flagging 8/8 while the STATE
    # fields flagged 0/24 — every one silently sanitized. Three of those lose something real:
    # `review_signal` (the mined evidence), `degrade_causes` (the diagnostic record of WHY a prior run
    # degraded), and `truncated` (a knowingly-incomplete dossier then reports itself complete).
    # This module's own doctrine, stated at every money guard, is that a lost record is reported rather
    # than absorbed. The state fields were the half that never adopted it.
    # ELEVEN sibling pairs were found one at a time before this; the population was never enumerated.
    _shape_expect = {
        "degrade_causes": list, "review_signal": list, "competitors": list,
        "reviews_done": dict, "charged": dict,
        "truncated": bool, "partial": bool, "discovery_done": bool,
    }
    checkpoint_field_dropped = sorted(
        {
            k for k, typ in _shape_expect.items()
            if k in progress and progress.get(k) is not None and not isinstance(progress.get(k), typ)
        }
        # …plus the ones `_load_progress` already repaired in place, which this check cannot see
        | set(progress.get("_dropped_fields") or [])
    )
    restored_causes = progress.get("degrade_causes")
    if isinstance(restored_causes, list):
        # `dict.fromkeys` to DEDUPE while preserving first-seen order — every append site upholds that
        # invariant and the field documents it, but the restore path did not: a checkpoint hand-edited,
        # partially written, or produced by a build without the dedup came back with repeats, and the
        # brief rendered "Degraded by: `Real`, `Real`". A restore must re-establish the invariant, not
        # assume the file on disk already satisfies it.
        dossier.degrade_causes = list(
            dict.fromkeys(c for c in restored_causes if isinstance(c, str) and c)
        )
    # ⚠️ AFTER the restore above, never before: that block ASSIGNS `degrade_causes` from the checkpoint,
    # so an append made earlier is silently discarded. Caught by the test failing on correct code.
    if spend_total_unreadable:
        dossier.partial = True
        if "SpendTotalUnreadable" not in dossier.degrade_causes:
            dossier.degrade_causes.append("SpendTotalUnreadable")
    if _restore_dropped:
        # ⚠️ The rejection sink was wired to the ADAPTER call site only. The RESTORE site drops evidence
        # too — and round 5's field-type validation changed that failure's CHARACTER: before it, a torn
        # checkpoint entry detonated loudly downstream (`s.sentiment.lower()`); after it, the entry is
        # silently discarded. Losing restored review evidence with `partial=False` and no cause is the
        # same silent-empty-dossier failure the adapter sink was added to end, one call site over.
        dossier.partial = True
        if "MalformedSignalRestored" not in dossier.degrade_causes:
            dossier.degrade_causes.append("MalformedSignalRestored")
    if checkpoint_field_dropped:
        # named, not merely flagged — a consumer needs to know WHICH record was lost
        logger.warning(
            "competitor_intel.checkpoint_field_dropped fields=%s", ",".join(sorted(checkpoint_field_dropped))
        )
        dossier.partial = True
        if "CheckpointFieldDropped" not in dossier.degrade_causes:
            dossier.degrade_causes.append("CheckpointFieldDropped")
    if ledger_entry_unreadable or ledger_container_unreadable:
        dossier.partial = True
        if "LedgerReset" not in dossier.degrade_causes:
            dossier.degrade_causes.append("LedgerReset")
    dossier.truncated = bool(progress.get("truncated"))
    profile = _load_source_profile(product_type)

    # ⚠️ `is True`, not `bool(...)`. These two flags gate whether a PAID leg runs at all, and they were
    # the only restored fields in this function without an element-level type guard — `bool("false")` is
    # True, so a hand-edited or migrated checkpoint carrying the STRING "false" skipped discovery forever
    # and silently dropped a rival's review mining, with `partial=False` and no cause: output
    # indistinguishable from a correct run. Same shape as the `_ck` collision fixed earlier this round.
    # Only a real JSON boolean counts as done; anything else means "not proven done" → re-run, which
    # fails toward re-charging real work rather than toward skipping it.
    discovery_done: bool = progress.get("discovery_done") is True
    discovered: list[dict[str, Any]] = [
        c for c in (progress.get("competitors") or []) if isinstance(c, dict)  # resume: filter corrupt cards
    ]
    _raw_reviews_done = progress.get("reviews_done")
    reviews_done: dict[str, bool] = (
        {k: v for k, v in _raw_reviews_done.items() if isinstance(k, str) and k and v is True}
        if isinstance(_raw_reviews_done, dict)
        else {}
    )

    def _persist() -> None:
        # ⚠️ NEVER write over state we could not READ. `read_text` failing is not evidence the bytes are
        # bad — `os.replace` needs only DIRECTORY write permission, so this module can always clobber a
        # file it cannot read. A transient read error (a UID change across a redeploy, a chmod, an EIO)
        # therefore made the run fail CLOSED on the read and fail OPEN on the write: it overwrote an
        # intact, paid-for ledger + competitor list with empties, and — because the round-5 sticky
        # `spend_baseline_lost` marker went out in the same write — the job was then dead FOREVER, with
        # the record needed to audit the real spend destroyed by the run that declared it lost.
        # Measured: run 1 paid for 1 rival; run 2 (file unreadable) wrote charged={} competitors=[];
        # run 3 with the file readable again made ZERO engine calls. A one-way door built by a fix.
        # Failing closed on money is right; taking the evidence down with it is not.
        if progress.get("_unreadable") is True or _ledger_container_lost:
            # ⚠️ BOTH lost-ledger conditions. This guard covered only `_unreadable`, so the run that
            # declared a corrupt ledger CONTAINER lost also ERASED it — the same lesson as the one-way
            # door above, one condition over, and its own per-VALUE twin already preserves the record.
            # Failing closed on money is right; taking the audit evidence down with it is not.
            return
        # A failed save is recorded on the DOSSIER, not merely logged: it silently disables the module's
        # one cumulative-spend record, so the next resume re-grants the whole budget. A consumer running
        # with logging off would have no way to know.
        save_cause = _save_progress(
            deps,
            {
                "job_id": deps.job_id,
                "discovery_done": discovery_done,
                "competitors": discovered,
                "reviews_done": reviews_done,
                "review_signal": [s.to_dict() for s in dossier.review_signal],
                "partial": dossier.partial,
                # ⚠️ The CAUSES are persisted alongside the flag they explain. Without this a resumed run
                # restores `partial=True` and an EMPTY `degrade_causes` — precisely the "partial with no
                # cause" state this field exists to end, on the most likely path to hit it: the failure
                # that motivates a resume is usually the failure that set the cause.
                "degrade_causes": list(dossier.degrade_causes),
                # ⚠️ INVARIANT: `charged` and `spent_usd` are written by the SAME `_persist()`. Splitting
                # them into separate writes would be a silent money bug — a persisted ledger with an
                # unpersisted total forgives real spend on the next resume.
                "charged": dict(charged),
                "truncated": dossier.truncated,
                "spent_usd": str(budget.spent),
                # persisted so the fail-closed state cannot be laundered by a later, smaller total
                "spend_baseline_lost": spend_total_unreadable,
            },
        )
        if save_cause:
            dossier.partial = True
            if save_cause not in dossier.degrade_causes:
                dossier.degrade_causes.append(save_cause)

    # Load + wiring-check BOTH packs at ENTRY (before any spend) so a malformed pack / wiring bug fails
    # LOUD as ValueError at entry — never after discovery has already spent (the "only raise is at entry"
    # contract). Cheap on resume (a YAML read); both packs share the same leg wiring.
    disc_pack = _pack(deps, "competitor-discovery")
    reviews_pack = _pack(deps, "competitor-reviews")
    pricing_pack = _pack(deps, "pricing") if enable_pricing else None  # only when the stage is on
    white_space_pack = _pack(deps, "white-space") if enable_white_space else None

    # ── stage 1: discover competitors ────────────────────────────────────────────────────────────────
    if not discovery_done:
        disc_brief = {
            "industry": (us.category if us else "") or market,
            "brand_name": us.name if us else "",
        }
        res = await _run_leg(
            deps, budget, disc_brief, market, pack=disc_pack, stage="discover", slug="all", charged=charged
        )
        # ⚠️ ONLY when the leg actually RAN. A budget short-circuit returns `cards: []` without calling
        # anything, and this used to be an unconditional reassignment — so a resume whose budget was
        # exhausted overwrote an already-PAID-FOR competitor list with `[]`, `_persist()` made the loss
        # durable, and the dossier returned `status="empty"` with `partial=False`: "this market has no
        # competitors". That is the exact mis-read the whole degrade-cause machinery exists to prevent,
        # and it destroyed data the consumer had already been billed for.
        fresh = [c for c in res.doc.get("cards", []) if isinstance(c, dict)]
        # Four states, and only ONE may erase a paid-for list. `res.ran` alone was too weak and
        # `res.ran and res.ok` is too strong — it throws away cards a DEGRADED leg really delivered
        # (a broken spend report sets `ok=False` while the doc still holds real, billed rivals):
        #   never ran (budget short-circuit)      -> keep: nothing was called
        #   ran, FAILED, returned nothing         -> keep: a transient error is not "the market is empty"
        #   ran, degraded, but DELIVERED cards    -> replace: that data is real and was paid for
        #   ran, succeeded (cards or none)        -> replace: an empty result from a healthy leg is a fact
        if res.ran and (res.ok or fresh):
            discovered = fresh
        if not res.ok:
            dossier.partial = True
            dossier.degrade_causes.extend(
                c for c in [res.cause] if c and c not in dossier.degrade_causes
            )
        if res.ledger_reset:
            # `partial` from the reset FLAG, never from a length delta on degrade_causes: the causes list
            # is persisted and restored, so a SECOND reset finds "LedgerReset" already present, appends
            # nothing, and a length check would miss it entirely.
            # ⚠️ LOAD-BEARING and, until this round, UNTESTED — the third comment in this file to make a
            # false claim about its own coverage, and the second to be written by a reviewer fixing the
            # previous one. Round 2's version of this comment asserted "defended by a test"; deleting the
            # line survived all 194. It is now defended by
            # `test_a_ledger_reset_on_EITHER_mandatory_leg_sets_partial`. The lesson is the recurring one:
            # a claim about coverage is a claim to VERIFY BY MUTATION, never to assert from reading. The
            # earlier argument it replaced ran the other way — that
            # every path here had already set `partial` (leg FAILED, or budget-SKIPPED), so "a mutant
            # deleting this line cannot be killed by a behavioural test." That reasoning enumerated two
            # prior states and missed a third that the SAME change had just created: a leg that SUCCEEDED
            # but hit the engine ceiling leaves a real watermark with `partial` still False (ceiling
            # truncation sets `truncated`, never `partial`). The line was load-bearing the moment it was
            # written, and the comment is why it shipped with no test. An argument that a line cannot be
            # tested is a claim to verify by mutation, never a reason to skip the test.
            dossier.partial = True
            if "LedgerReset" not in dossier.degrade_causes:
                dossier.degrade_causes.append("LedgerReset")
        if res.truncated:
            dossier.truncated = True
        # Only on SUCCESS. Marking a FAILED discovery done poisoned the job_id permanently: every future
        # resume skipped discovery and returned an empty dossier forever, so one transient network blip
        # became a permanent dead job. (Pre-existing since Phase A; a one-line correctness fix in a file
        # this change already touches.)
        # ⚠️ `res.ok and res.ran`, NOT `res.ok` and NOT `res.ok and not res.truncated`. Three states, and
        # only one of them may be retried:
        #   * RAISED           → `ok=False`             → retry (`05ada8c` closed this one)
        #   * budget-SKIPPED   → `ok=True,  ran=False`  → retry: nothing was called, nothing was billed
        #   * CEILING-hit      → `ok=True,  ran=True`   → DONE: it ran, delivered cards and was billed
        # Phase B keyed on `not truncated`, which retried the last two together — so a successful
        # ceiling-truncated discovery stayed un-done, and the next budget-exhausted resume wiped the
        # paid-for competitor list (see the `res.ran` guard above). `truncated` describes the OUTPUT;
        # `ran` describes whether we spent money. The done-flag is a question about spending.
        discovery_done = res.ok and res.ran
        _persist()
    dossier.competitors = discovered

    # ── stage 2: mine reviews per competitor (product-type-aware; Tier-C default) ─────────────────────
    env = os.environ
    adapters = enabled_adapters(product_type, env)  # Phase A: [] → Tier-C search-excerpts only

    for card in discovered:
        name = str(card.get("name") or "").strip()
        url = str(card.get("url") or "").strip()
        if not name:
            dossier.partial = True  # a nameless discovered card is a degraded result, flag it
            # …with a NAMED cause. Every `partial = True` owes one, or the brief says "some sources
            # degraded" and gives the reader nothing to act on — the ambiguity this field exists to end.
            if "MalformedCard" not in dossier.degrade_causes:
                dossier.degrade_causes.append("MalformedCard")
            continue
        # Collision-safe only because `_ck`'s hash input is LENGTH-PREFIXED. This comment used to assert
        # "two names never share a checkpoint/skip key" while the bare `|` separator made that false.
        key = _ck(name, url)
        if reviews_done.get(key):
            continue  # resumed — this competitor's reviews already mined; re-bill nothing

        review_brief = {
            "competitor_name": name,
            "competitor_url": url,
            "review_venues": profile.get("review_venues", []),
            "site_patterns": profile.get("site_patterns", []),
        }
        res = await _run_leg(
            deps, budget, review_brief, market, pack=reviews_pack, stage="reviews", slug=key, charged=charged
        )
        if not res.ok:
            dossier.partial = True
            dossier.degrade_causes.extend(
                c for c in [res.cause] if c and c not in dossier.degrade_causes
            )
        if res.ledger_reset:
            # `partial` from the reset FLAG, never from a length delta on degrade_causes:
            # the causes list is persisted and restored, so a SECOND reset finds "LedgerReset"
            # already present, appends nothing, and a length check would miss it entirely.
            dossier.partial = True
            if "LedgerReset" not in dossier.degrade_causes:
                dossier.degrade_causes.append("LedgerReset")
        if res.truncated:
            dossier.truncated = True
        # ⚠️ EXTEND-DEDUPED, never a bare extend. `review_signal` is restored from the checkpoint and then
        # extended, so any leg that re-runs appends the same evidence again. The done-flag fix closed the
        # ceiling-hit door; the `ok=False`-with-cards door stayed open (a corrupt sub-call checkpoint, or
        # simply RAISING total_budget_usd between resumes) and measured a linear inflation:
        # signals 2 -> 4 -> 6 -> 8, BEAT weight 1.6 -> 3.2 -> 4.8 -> 6.4 from the SAME two sources,
        # because `synth` sums `source_weight` over entries rather than distinct urls.
        # Making the append IDEMPOTENT fixes the whole class instead of one door at a time.
        _extend_signals(dossier.review_signal, _cards_to_signals(name, res.doc.get("cards", []), tier="C"))

        # opt-in adapters (empty registry → this loop body never runs). Gate on the budget: don't keep
        # hitting external APIs after the ceiling is exhausted (and paid follow-on adapters must not spend
        # outside the total — they read the remaining budget from config; see README).
        for adapter in (adapters if budget.remaining() > 0 else []):
            try:
                dropped: list[Any] = []
                _extend_signals(
                    dossier.review_signal,
                    await adapter.fetch(name, client=deps.client, config=deps.config),
                    dropped,
                )
                if dropped:
                    # a malformed RETURN is as diagnosable as a raised exception, and until now only the
                    # exception had a cause. An adapter emitting `rating="4.5"` had every signal silently
                    # discarded and the consumer saw an empty dossier with `status="ok"`.
                    dossier.partial = True
                    if "MalformedAdapterSignal" not in dossier.degrade_causes:
                        dossier.degrade_causes.append("MalformedAdapterSignal")
            except Exception as exc:  # noqa: BLE001 — an adapter must never break the run
                logger.warning(
                    "competitor_intel.adapter_failed name=%s cause=%s",
                    getattr(adapter, "name", "?"),
                    type(exc).__name__,
                )
                # …and onto the DOSSIER, not only the log. This path sets `partial = True` below, and a
                # partial flag with no cause is exactly the ambiguity `degrade_causes` exists to remove —
                # the threading covered the research legs and the optional stages but missed this loop.
                dossier.note_degraded(exc)
                dossier.partial = True

        # Same rule as `discovery_done` above, same reason — and the same correction. Keying on
        # `not truncated` also retried a CEILING-hit reviews leg, which the engine then answered from its
        # own completed checkpoint with the same cards; `review_signal` is restored from the checkpoint
        # and then EXTENDED, so every resume appended a duplicate of the same quotes. `synth` sums
        # `source_weight` over entries (not distinct urls), so the duplicate silently doubled that
        # theme's BEAT weight and re-ordered the brief — a paid-for run reporting corrupted ranking.
        reviews_done[key] = res.ok and res.ran
        _persist()

    # ── synthesis tail (Phase B): extract → align → matrix → gap (MATCH/BEAT) ─────────────────────────
    # LLM stages are metered against the SAME budget (skip → degrade when exhausted); pure stages assemble
    # with the trust rails. Not checkpointed — re-runs on resume (cheap; the total ceiling still caps it).
    # clamp the synthesis estimate to a positive default — a 0/None/garbage estimate would charge nothing
    # per LLM call, silently disabling synthesis metering (uncounted spend vs the total ceiling).
    synth_est = _synth_estimate(deps.synth_call_estimate)
    meter = LlmMeter(deps.llm, budget.remaining, budget.charge, synth_est)

    if discovered:
        feature_sets = []
        for card in discovered:
            cname = str(card.get("name") or "").strip()
            if not cname:
                continue
            feature_sets.append(
                await extract_features(cname, meter=meter, sources=_rival_sources(cname, card, dossier.review_signal))
            )
        _persist()  # persist synth spend accrued so far — a crash mid-tail must not lose the accounting
        taxonomy = await align_features(feature_sets, us, meter=meter)
        matrix = build_matrix(taxonomy, feature_sets, us)
        # competitor → registrable domain, so the source-weight can discount a rival's self-published reviews.
        subject_domains = {
            str(c.get("name") or "").strip(): _netloc(str(c.get("url") or ""))
            for c in discovered
            if str(c.get("name") or "").strip()
        }
        match, beat = gap_synthesis(matrix, dossier.review_signal, us, subject_domains=subject_domains)
        dossier.feature_matrix = matrix
        dossier.match_list = match
        dossier.beat_list = beat
        if pricing_pack is not None:  # pricing needs rivals → gated on `discovered`
            before = len(dossier.degrade_causes)
            hit: list[bool] = []
            def _persist_pricing() -> None:
                # ⚠️ Translate the stage's flags BEFORE saving. The per-rival save was handed `_persist`
                # directly, so it durably wrote `degrade_causes` WITHOUT the `partial`/`truncated` that
                # make them reachable — the exact "recorded cause that never sets partial is UNREACHABLE"
                # state the comment below names. Worse, it survived the resume: `run()` detects new causes
                # by a LENGTH DELTA against `before`, and the restored cause makes that delta zero, so a
                # resumed run reported `partial=False, status="ok"` while `to_markdown` still printed the
                # ⚠️ degraded banner. The machine-readable dossier and the human brief disagreed.
                # Its white-space twin already persists AFTER its flags; this is that pair made symmetric.
                if hit:
                    dossier.truncated = True
                if len(dossier.degrade_causes) > before:
                    dossier.partial = True
                _persist()

            dossier.pricing = await _pricing_stage(
                deps, budget, discovered, market, pricing_pack, meter, dossier.degrade_causes, hit,
                charged, _persist_pricing,
            )
            # An optional leg hitting the ENGINE's per-call ceiling is a different condition from the
            # orchestrator total being exhausted (the only one checked at the end of the run), so a
            # silently-incomplete block was landing on a dossier reporting `truncated=False`.
            # ⚠️ These two lines are now REDUNDANT — `_persist_pricing` above applies the identical
            # translation before each save, so by the time control reaches here the flags are already
            # set, and a mutant deleting them survives. Verified equivalent, not assumed: with zero
            # rivals the callback never fires, but `hit`/`causes` are then empty too, so there is nothing
            # to translate. They stay as the authoritative end-of-stage statement; the callback exists
            # only because the mid-loop CHECKPOINT must not record a cause without its flag.
            if hit:
                dossier.truncated = True
            # A recorded cause that never sets `partial` is UNREACHABLE: the brief hides it and `status`
            # still says "ok", so an enabled stage can fail completely and the consumer sees a clean,
            # silently-incomplete dossier. The threading reached this stage but stopped one line short.
            if len(dossier.degrade_causes) > before:
                dossier.partial = True
            _persist()  # persist the pricing legs' + synth spend

    # white-space is DEMAND-side (category-level, competitor-independent) → runs even with zero rivals,
    # which is exactly the greenfield case where it matters most.
    if white_space_pack is not None:
        before = len(dossier.degrade_causes)
        hit_ws: list[bool] = []
        dossier.white_space = await _white_space_stage(
            deps, budget, market, white_space_pack, meter, dossier.degrade_causes, hit_ws, charged
        )
        if hit_ws:
            dossier.truncated = True
        if len(dossier.degrade_causes) > before:
            dossier.partial = True
        _persist()  # persist the white-space leg + synth spend

    if meter.degraded:  # an LLM synthesis call FAILED (not merely budget-skipped) → the dossier is partial
        dossier.partial = True
        # The CAUSES too, not just the flag. The synthesis tail is where a ONE-arity mis-wiring actually
        # breaks (it calls `llm(prompt)`), so this is the most diagnostic path in the module.
        dossier.degrade_causes.extend(c for c in meter.causes if c not in dossier.degrade_causes)
    if budget.total > 0 and budget.remaining() <= 0:
        dossier.truncated = True
    # ⚠️ REPORT what this module can attest; the BUDGET decision is separate.
    # When the baseline is lost, `budget.spent` is deliberately set to `budget.total` — a fail-closed
    # GUESS that stops further spending, which is correct. Reporting that guess as `spend_usd` is not:
    # it is the caller's own `total_budget_usd` echoed back as if it were a measurement, so a consumer
    # aggregating `spend_usd` into a cost ledger records a fabricated figure that scales with whatever
    # budget they passed (999.00 for a run that made ZERO engine calls, measured). That is the same
    # "guess recorded as a measurement" error already fixed for the PERSISTED field — reaching the
    # consumer's books instead of the next resume.
    # The attestable number is the ledger floor. It is a LOWER bound, not a total (a reset rewrites a
    # watermark downward, synthesis never enters it), and `SpendTotalUnreadable` + `partial` are already
    # on the dossier to say the figure cannot be trusted as complete.
    dossier.spend_usd = ledger_floor if spend_total_unreadable else budget.spent
    # "empty" means nothing found — but a white-space-only greenfield run (no rivals, real unmet-need
    # content) is NOT empty, so a consumer keying on status doesn't discard it.
    has_content = bool(discovered) or bool(dossier.white_space and dossier.white_space.needs)
    dossier.status = "partial" if dossier.partial else ("empty" if not has_content else "ok")
    _persist()  # final flush (captures the terminal spend + flags)
    return dossier


def _rival_sources(name: str, card: Mapping[str, Any], signals: list[Signal]) -> list[tuple[str, str]]:
    """The ``(text, url)`` sources available for one rival's feature extraction: the discovery card's own
    words (paired with the card url) + that rival's review quotes (paired with each quote's source url).
    Thin by design (no dedicated feature-fetch pack) — a documented limitation; feature quality tracks the
    richness of what discovery + reviews surfaced. Real urls let extraction attach true provenance."""
    curl = str(card.get("url") or "")
    out: list[tuple[str, str]] = []
    for key in ("positioning", "evidence"):
        value = card.get(key)
        if value:
            out.append((str(value), curl))
    # ⚠️ `.strip()` on BOTH sides — `_signal_key` normalizes `competitor`, so a padded name is the
    # SAME rival to the dedupe and must be the same rival here. Reading it raw meant a padded
    # signal contributed nothing to its own rival's feature extraction.
    out += [(s.quote, s.source_url) for s in signals if s.competitor.strip() == name.strip() and s.quote]
    return out


async def _pricing_stage(
    deps: Deps,
    budget: _Budget,
    discovered: list[dict[str, Any]],
    market: str,
    pack: Pack,
    meter: LlmMeter,
    causes: list[str],
    truncated: list[bool],
    charged: dict[str, str],
    persist: Callable[[], None],
) -> PricingBlock:
    """Run the pricing research leg per rival (metered, checkpointed, never-raising) → synthesize the
    price-wedge. Degrades to an empty block when the budget is exhausted.

    ``persist`` is called after EACH rival's leg. The reviews loop already did this; this loop billed one
    paid leg per rival and saved once, after all of them — so a crash mid-loop lost every pricing leg's
    spend record and the next resume re-granted it (measured: 3 legs billed, ledger recorded none). The
    same sibling-pair shape as the rest of this file: one loop careful, its twin not."""
    rival_sources: dict[str, list[tuple[str, str]]] = {}
    for card in discovered:
        name = str(card.get("name") or "").strip()
        url = str(card.get("url") or "").strip()
        if not name:
            continue
        res = await _run_leg(
            deps, budget, {"competitor_name": name, "competitor_url": url}, market,
            pack=pack, stage="pricing", slug=_ck(name, url), charged=charged,
        )
        # an optional stage degrades just as silently as a mandatory one — its cause is owed too
        if res.cause and res.cause not in causes:
            causes.append(res.cause)
        # A reset reaches `run()` from HERE via the causes sink — these stages return a Block, never the
        # _StageResult, so `ledger_reset` cannot travel the way it does for the mandatory legs.
        if res.ledger_reset and "LedgerReset" not in causes:
            causes.append("LedgerReset")
        if res.truncated:
            truncated.append(True)
        persist()  # per rival — the money for THIS leg is already spent
        texts = [
            (str(c.get("snippet") or ""), str(c.get("source_url") or ""))
            for c in res.doc.get("cards", [])
            if isinstance(c, dict) and c.get("snippet")
        ]
        if texts:
            rival_sources[name] = texts
    return await price_wedge(rival_sources, meter=meter)


async def _white_space_stage(
    deps: Deps,
    budget: _Budget,
    market: str,
    pack: Pack,
    meter: LlmMeter,
    causes: list[str],
    truncated: list[bool],
    charged: dict[str, str],
) -> WhiteSpaceBlock:
    """Run the white-space demand research leg (subject = the market/category) → synthesize corroborated
    unmet needs. Degrades to an empty block when the budget is exhausted."""
    res = await _run_leg(
        deps, budget, {"category": market, "market": market}, market,
        pack=pack, stage="white-space", slug="all", charged=charged,
    )
    if res.cause and res.cause not in causes:
        causes.append(res.cause)
    if res.ledger_reset and "LedgerReset" not in causes:
        causes.append("LedgerReset")
    if res.truncated:
        truncated.append(True)
    sources = [
        (str(c.get("snippet") or ""), str(c.get("source_url") or ""))
        for c in res.doc.get("cards", [])
        if isinstance(c, dict) and c.get("snippet")
    ]
    return await white_space(sources, meter=meter)


def _rehydrate_signals(raw: Any) -> list[Signal]:
    """Rebuild `review_signal` from a persisted progress file (a list of `Signal.to_dict()` dicts). Tolerant
    of a corrupt/partial file — a malformed entry is skipped, never a raise."""
    out: list[Signal] = []
    if not isinstance(raw, list):
        return out
    for d in raw:
        if not isinstance(d, dict):
            continue
        tier = d.get("tier")
        rating = d.get("rating")
        out.append(
            Signal(
                competitor=str(d.get("competitor") or ""),
                aspect=str(d.get("aspect") or ""),
                sentiment=str(d.get("sentiment") or "neutral"),
                quote=str(d.get("quote") or ""),
                source_url=str(d.get("source_url") or ""),
                tier=cast(Tier, tier if tier in ("A", "B", "C") else "C"),
                rating=_safe_rating(rating),
            )
        )
    return out


def _cards_to_signals(competitor: str, cards: Any, *, tier: str) -> list[Signal]:
    """Map deep-research review cards → tier-tagged :class:`Signal`s. Tolerant of missing fields (a garbage
    card contributes an empty-quote signal, never a raise)."""
    out: list[Signal] = []
    if not isinstance(cards, list):
        return out
    for card in cards:
        if not isinstance(card, dict):
            continue
        out.append(
            Signal(
                competitor=competitor,
                aspect=str(card.get("aspect") or ""),
                sentiment=str(card.get("sentiment") or "neutral"),
                quote=str(card.get("verbatim_quote") or ""),
                source_url=str(card.get("source_url") or ""),
                tier=cast(Tier, tier),
            )
        )
    return out
