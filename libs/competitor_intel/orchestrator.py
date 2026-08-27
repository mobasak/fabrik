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
from collections.abc import Mapping
from dataclasses import dataclass, field
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


def _to_decimal(value: Any) -> Decimal:
    """A safe, FINITE Decimal from whatever a caller/engine left behind (a Decimal, a stringified one, a
    float, None, garbage). A NaN/inf/garbage value returns 0 rather than poisoning a compare or a total."""
    try:
        d = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
    return d if d.is_finite() else Decimal("0")


def _is_finite_decimal(value: Any) -> bool:
    return isinstance(value, Decimal) and value.is_finite()


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
        if amount.is_finite() and amount > 0:
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
    cause: str = ""  # exception CLASS NAME when this leg degraded, else "" (never a message)


async def _run_leg(
    deps: Deps, budget: _Budget, brief: Mapping[str, Any], market: str, *, pack: Pack, stage: str, slug: str
) -> _StageResult:
    """One budgeted, checkpointed, never-raising research sub-call. Reserves ``remaining / ceiling_factor``
    (so the engine's ceiling ``reserved x factor`` equals the true remaining → total is a HARD cap even
    with a >1 factor), charges the true actual afterward, and flags truncation. A non-finite reported spend
    is charged at the full reservation (conservative — never under-count real dollars)."""
    remaining = budget.remaining()
    if remaining <= 0:
        return _StageResult(doc={"cards": []}, ok=True, truncated=True)  # exhausted — skip, don't call
    # factor must be a sane finite multiplier; an out-of-range value (incl. a pathological tiny one that
    # would overflow the division) falls back to 1 rather than raising out of the never-raise contract.
    cf = deps.ceiling_factor
    factor = cf if _is_finite_decimal(cf) and Decimal("0.000001") <= cf <= Decimal("1000000") else Decimal("1")
    reserved = remaining / factor
    shim = _shim(
        deps,
        reserved=reserved,
        ceiling_factor=factor,  # SAME clamped factor the engine multiplies by → reserved x factor == remaining
        checkpoint_file=deps.checkpoint_dir / f"{stage}-{slug}.json",
        job_id=f"{deps.job_id}:{stage}:{slug}",
    )
    doc, ok, cause = await _safe_research(
        deps, brief, market, pack=pack, shim=shim, label=f"{stage}:{slug}"
    )
    if _is_finite_decimal(shim.spent_usd):
        budget.charge(shim.spent_usd)  # the Decimal run_research mutated, not the return str
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
        doc=doc, ok=(ok and not degraded_spend), truncated=bool(shim.ceiling_hit), cause=cause
    )


# ── orchestrator-level progress checkpoint (top-level; distinct from each sub-call's own) ──────────────
def _hash(value: str) -> str:
    # non-security file-name/dedup key; usedforsecurity=False clears BOTH ruff S324 AND bandit B324
    # (a bare ruff-suppression comment silences ruff only, leaving the module gate red on bandit B324).
    return hashlib.sha1(value.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]


def _progress_file(deps: Deps) -> Path:
    # job_id hash makes the filename distinct even when two job_ids slug identically.
    return deps.checkpoint_dir / f"{_slug(deps.job_id)}-{_hash(deps.job_id)}-progress.json"


def _load_progress(deps: Deps) -> dict[str, Any]:
    """Load this job's progress, discarding a corrupt file OR one owned by a different job_id (the
    ownership guard mirrors deep-research's checkpoint double-book guard). Never raises."""
    try:
        data = json.loads(_progress_file(deps).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("job_id") != deps.job_id:
        return {}
    # sanitize sub-fields so a tampered / version-migrated OWNED file can't crash run() (never-raise):
    # competitors must be a list, reviews_done a dict; spent_usd/discovery_done are coerced at use.
    comps = data.get("competitors")
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
        # PID-unique temp name stops two racers tearing one file.
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
    """A STABLE, collision-safe key for a competitor (checkpoint slug + reviews_done key). ``_slug`` alone
    collapses punctuation variants AND every non-ASCII-alphanumeric name to ``"x"`` (silent data loss when
    two rivals collide); the name+url hash disambiguates while staying deterministic across resumes."""
    return f"{_slug(name)}-{_hash(name + '|' + url)}"


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
    restored = _to_decimal(progress.get("spent_usd", "0"))  # restore cumulative spend across a resume
    budget.spent = restored if restored > 0 else Decimal("0")  # clamp a corrupt negative (would inflate remaining → overspend)
    dossier = Dossier(market=market, product_type=product_type)
    # restore the mined review signal + degradation flags across a resume — else a resumed run skips
    # already-done competitors (reviews_done) and synthesizes on an EMPTY signal → a hollow BEAT/matrix.
    dossier.review_signal = _rehydrate_signals(progress.get("review_signal"))
    dossier.partial = bool(progress.get("partial"))
    # …and the causes behind that flag. `isinstance`-guarded per element: the checkpoint is a file on
    # disk that a crash can truncate or a hand-edit can corrupt, and a restore must never raise.
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
    dossier.truncated = bool(progress.get("truncated"))
    profile = _load_source_profile(product_type)

    discovery_done: bool = bool(progress.get("discovery_done"))
    discovered: list[dict[str, Any]] = [
        c for c in (progress.get("competitors") or []) if isinstance(c, dict)  # resume: filter corrupt cards
    ]
    reviews_done: dict[str, bool] = dict(progress.get("reviews_done") or {})

    def _persist() -> None:
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
                "truncated": dossier.truncated,
                "spent_usd": str(budget.spent),
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
        res = await _run_leg(deps, budget, disc_brief, market, pack=disc_pack, stage="discover", slug="all")
        discovered = [c for c in res.doc.get("cards", []) if isinstance(c, dict)]
        if not res.ok:
            dossier.partial = True
            dossier.degrade_causes.extend(
                c for c in [res.cause] if c and c not in dossier.degrade_causes
            )
        if res.truncated:
            dossier.truncated = True
        # Only on SUCCESS. Marking a FAILED discovery done poisoned the job_id permanently: every future
        # resume skipped discovery and returned an empty dossier forever, so one transient network blip
        # became a permanent dead job. (Pre-existing since Phase A; a one-line correctness fix in a file
        # this change already touches.)
        discovery_done = res.ok
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
        key = _ck(name, url)  # collision-safe: two names never share a checkpoint/skip key
        if reviews_done.get(key):
            continue  # resumed — this competitor's reviews already mined; re-bill nothing

        review_brief = {
            "competitor_name": name,
            "competitor_url": url,
            "review_venues": profile.get("review_venues", []),
            "site_patterns": profile.get("site_patterns", []),
        }
        res = await _run_leg(deps, budget, review_brief, market, pack=reviews_pack, stage="reviews", slug=key)
        if not res.ok:
            dossier.partial = True
            dossier.degrade_causes.extend(
                c for c in [res.cause] if c and c not in dossier.degrade_causes
            )
        if res.truncated:
            dossier.truncated = True
        dossier.review_signal.extend(_cards_to_signals(name, res.doc.get("cards", []), tier="C"))

        # opt-in adapters (empty registry → this loop body never runs). Gate on the budget: don't keep
        # hitting external APIs after the ceiling is exhausted (and paid follow-on adapters must not spend
        # outside the total — they read the remaining budget from config; see README).
        for adapter in (adapters if budget.remaining() > 0 else []):
            try:
                dossier.review_signal.extend(
                    await adapter.fetch(name, client=deps.client, config=deps.config)
                )
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

        reviews_done[key] = True
        _persist()

    # ── synthesis tail (Phase B): extract → align → matrix → gap (MATCH/BEAT) ─────────────────────────
    # LLM stages are metered against the SAME budget (skip → degrade when exhausted); pure stages assemble
    # with the trust rails. Not checkpointed — re-runs on resume (cheap; the total ceiling still caps it).
    # clamp the synthesis estimate to a positive default — a 0/None/garbage estimate would charge nothing
    # per LLM call, silently disabling synthesis metering (uncounted spend vs the total ceiling).
    synth_est = _to_decimal(deps.synth_call_estimate)
    if synth_est <= 0:
        synth_est = Decimal("0.01")
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
            dossier.pricing = await _pricing_stage(
                deps, budget, discovered, market, pricing_pack, meter, dossier.degrade_causes, hit
            )
            # An optional leg hitting the ENGINE's per-call ceiling is a different condition from the
            # orchestrator total being exhausted (the only one checked at the end of the run), so a
            # silently-incomplete block was landing on a dossier reporting `truncated=False`.
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
            deps, budget, market, white_space_pack, meter, dossier.degrade_causes, hit_ws
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
    dossier.spend_usd = budget.spent
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
    out += [(s.quote, s.source_url) for s in signals if s.competitor == name and s.quote]
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
) -> PricingBlock:
    """Run the pricing research leg per rival (metered, checkpointed, never-raising) → synthesize the
    price-wedge. Degrades to an empty block when the budget is exhausted."""
    rival_sources: dict[str, list[tuple[str, str]]] = {}
    for card in discovered:
        name = str(card.get("name") or "").strip()
        url = str(card.get("url") or "").strip()
        if not name:
            continue
        res = await _run_leg(
            deps, budget, {"competitor_name": name, "competitor_url": url}, market,
            pack=pack, stage="pricing", slug=_ck(name, url),
        )
        # an optional stage degrades just as silently as a mandatory one — its cause is owed too
        if res.cause and res.cause not in causes:
            causes.append(res.cause)
        if res.truncated:
            truncated.append(True)
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
) -> WhiteSpaceBlock:
    """Run the white-space demand research leg (subject = the market/category) → synthesize corroborated
    unmet needs. Degrades to an empty block when the budget is exhausted."""
    res = await _run_leg(
        deps, budget, {"category": market, "market": market}, market,
        pack=pack, stage="white-space", slug="all",
    )
    if res.cause and res.cause not in causes:
        causes.append(res.cause)
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
                rating=float(rating) if isinstance(rating, (int, float)) and not isinstance(rating, bool) else None,
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
