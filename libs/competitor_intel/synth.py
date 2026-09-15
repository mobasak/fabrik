"""The synthesis tail — the genuinely-new core: turn per-rival evidence into a feature matrix + a ranked
MATCH / BEAT gap analysis, with the trust rails wired into every step.

LLM stages (``extract_features`` / ``align_features``) go through :class:`LlmMeter` — a budget gate that
charges the shared orchestrator total per call, skips (→ degrade) when exhausted, and NEVER raises. Pure
stages (``build_matrix`` / ``gap_synthesis``) do trust-gated assembly with no LLM. ``us`` is OPTIONAL:
absent → a rival-vs-rival category landscape + category table-stakes MATCH.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Final

from ._ingest import Taken, take
from .dossier import Signal, Us
from .protocols import SynthLlm
from .trust import (
    CONSTRAIN_TO_SOURCES,
    UNVERIFIED,
    corroborated,
    grounded_source,
    source_weight,
)

logger = logging.getLogger(__name__)


def _feature_list(value: Any) -> list[Any]:
    """The caller's feature list, or empty. ⚠️ A TYPE check, not `or []` — `7 or []` is `7`, and a bare
    string iterates CHARACTER BY CHARACTER, which is worse than raising because it silently produces
    one-letter "features". The element guards on the comprehensions below only ever guarded half the
    shape; this is the other half."""
    # ⚠️ `range` BELONGS HERE, and its absence was SILENT DATA LOSS rather than a raise. Both `_seq`
    # twins were widened to every re-iterable container precisely because dropping one renders it as
    # NOTHING; this guard was not, so `features=range(3)` produced `kept=[] n_malformed=0` — identical
    # to a genuinely empty feature list — while `features=[0,1,2]` correctly reported 3 drops. A drop
    # that is indistinguishable from an empty market is the exact failure the ingestion seam exists to
    # end, reintroduced one container type over.
    # ⚠️ AND THE WHITELIST WAS STILL SHORT — `range` was the container found last time; `dict_keys`,
    # `dict_values` and a plain `dict` were the ones found this time, by an independent reviewer, and
    # `Us(features=my_features.keys())` is an ordinary caller shape. Each produced `kept=[]
    # n_malformed=0` against a perfectly HEALTHY taxonomy: a ❌ MISSING on every rival feature and a
    # MATCH list telling the operator to build what they already ship — the same published falsehood
    # the `degraded` work above exists to stop, reached without anything degrading at all.
    # So this stops enumerating TYPES and asks the PROPERTY that actually matters: is it re-iterable?
    # `Collection` is exactly that (`__len__`/`__contains__`/`__iter__`), which admits every container
    # named above plus any the next caller invents, while a one-shot ITERATOR is not a `Collection` and
    # stays out — deliberately, because `_us_features` runs TWICE (`align_features` and `build_matrix`)
    # and a generator would be empty on the second pass, making the false ❌ non-deterministic.
    # `str`/`bytes` stay out for the original reason: they iterate character by character.
    # ⚠️ ONE READER, TWO QUESTIONS. The elements and the READABILITY bit are now produced by a
    # single helper (`_read_features`) so `_feature_list` and `_us_unusable` cannot disagree —
    # they answered the same question from two code paths and a `Collection` whose iteration
    # RAISES was 'empty' to one and 'usable' to the other, which is how the sixth door opened.
    return _read_features(value)[0]


# cell states
HAS = "✅"
MISSING = "❌"
PARTIAL = "⚠️"
UNKNOWN = UNVERIFIED  # "❓"


@dataclass
class LlmMeter:
    """Budget-gated, never-raising wrapper around the injected synthesis LLM. ``remaining``/``charge`` are
    the shared orchestrator ``_Budget``'s methods (passed as callables so this module stays decoupled)."""

    llm: SynthLlm
    remaining: Callable[[], Decimal]
    charge: Callable[[Decimal], None]
    estimate: Decimal
    degraded: bool = False  # set True when a call FAILED (LLM raised) — distinct from a budget-exhausted skip
    #: Exception CLASS NAMES (never messages) of the failures behind ``degraded``, so the orchestrator can
    #: put them on the Dossier. The synthesis tail is where a ONE-arity mis-wiring actually breaks (it
    #: calls ``llm(prompt)``), so a bare boolean here loses the most diagnostic signal the module has.
    causes: list[str] = field(default_factory=list)
    #: ELEMENT DROPS, keyed by ``(site, subject)`` — a channel deliberately SEPARATE from ``causes``.
    #: ⚠️ ``causes`` is only ever read behind ``if meter.degraded:``, and ``degraded`` means "an LLM call
    #: RAISED". Putting a dropped-element cause there would be unreachable unless the implementer also
    #: set ``degraded`` — conflating a malformed element with a provider failure, which is the very
    #: distinction this seam exists to preserve. Measured with the naive wiring grafted on:
    #: ``drops={'extract_features': 3}`` yet ``dossier.partial=False causes=[]``.
    #: ⚠️ Keyed by SUBJECT as well as site because one ``LlmMeter`` instance is shared across the whole
    #: per-rival loop and all three stages. Without the subject, rival #1 losing two features and rival
    #: #3 losing none produce byte-identical state, and the operator cannot tell which rival's row in
    #: the matrix is thin because nothing was found versus thin because we dropped it.
    drops: dict[tuple[str, str], int] = field(default_factory=dict)

    def note_drops(self, site: str, subject: str, n: int) -> None:
        """Record ``n`` elements lost at ``site`` while processing ``subject``. Never sets ``degraded``:
        a malformed element is not a provider failure."""
        if n > 0:
            key = (site, subject)
            self.drops[key] = self.drops.get(key, 0) + n

    async def call(self, prompt: str) -> str | None:
        """Return the LLM's text, or None to signal 'skip/degrade' — when the budget is exhausted (before
        spending) or the call fails. Charges the per-call estimate against the shared total. A FAILURE
        (LLM raised) sets ``degraded`` so the orchestrator can flag the dossier partial; a budget-exhausted
        skip does NOT (that is ``truncated``, a different signal)."""
        if self.remaining() <= 0:
            return None
        self.charge(self.estimate)
        try:
            return await self.llm(prompt)
        except Exception as exc:  # noqa: BLE001 — a failed synthesis call degrades, never raises
            # The TYPE only (never the message — it can carry scraped text or a client-echoed key).
            # A wiring bug reads as `cause=TypeError` and is instantly separable from a network blip.
            name = type(exc).__name__
            logger.warning("competitor_intel.synth_llm_degraded cause=%s", name)
            self.degraded = True
            if name not in self.causes:
                self.causes.append(name)
            return None


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _parse_json(text: str | None) -> Any:
    """Best-effort JSON from an LLM reply (tolerates ```json fences / surrounding prose). None on failure."""
    if not text:
        return None
    body = _FENCE.sub("", text.strip())
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        # last resort: grab the first {...} or [...] block
        m = re.search(r"(\{.*\}|\[.*\])", body, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except (ValueError, TypeError):
                return None
        return None


# ── feature extraction ────────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Feature:
    name: str
    state: str  # HAS / MISSING / PARTIAL / UNKNOWN
    evidence: str  # verbatim quote (grounded) or "" when unverified
    source_url: str  # the REAL url the quote was found in (via grounded_source), "" when unverified
    freshness: str = ""  # ISO date if the extraction supplied one, else ""


@dataclass
class FeatureSet:
    competitor: str
    features: list[Feature] = field(default_factory=list)


async def extract_features(
    competitor: str, *, meter: LlmMeter, sources: Sequence[tuple[str, str]]
) -> FeatureSet:
    """Schema-first per-rival feature extraction from the available ``(text, url)`` sources, quote-grounded.
    The feature's ``source_url`` is the REAL url the quote was found in (via ``grounded_source``), never a
    url the LLM emits. An unverifiable feature (quote not in the sources) is emitted as ``❓`` with no
    evidence/url, never dropped. Degrades to an empty set when the budget is exhausted or the LLM fails."""
    if not sources:
        return FeatureSet(competitor=competitor)
    prompt = (
        f"{CONSTRAIN_TO_SOURCES}\n\n"
        f"Extract the product features of '{competitor}' from the sources. Output ONLY a JSON array, each "
        f'{{"name": .., "state": "has"|"missing"|"partial", "evidence": "<verbatim quote>", '
        f'"date": "<ISO date if the source states one, else empty>"}}.\n\nSOURCES:\n'
        + "\n---\n".join(t for t, _ in sources)
    )
    parsed = _parse_json(await meter.call(prompt))
    if not isinstance(parsed, list):
        return FeatureSet(competitor=competitor)
    _state_map = {"has": HAS, "missing": MISSING, "partial": PARTIAL}
    features: list[Feature] = []
    # THE SEAM on the meter lane: a malformed feature item is evidence loss, reported through
    # `meter.drops` (keyed by rival) rather than `meter.causes` — see `LlmMeter.drops` for why that
    # distinction is load-bearing and not stylistic.
    _taken = take(
        parsed,
        site="extract_features",
        shape=lambda it: isinstance(it, dict) and bool(str(it.get("name") or "").strip()),
    )
    meter.note_drops("extract_features", competitor, _taken.n_malformed)
    for item in _taken.kept:
        evidence = str(item.get("evidence") or "")
        url = grounded_source(evidence, sources)  # the REAL url, or None if ungrounded
        grounded = url is not None
        state = _state_map.get(str(item.get("state") or "").lower(), UNKNOWN)
        features.append(
            Feature(
                name=str(item["name"]).strip(),
                state=state if grounded else UNKNOWN,  # ungrounded → cannot verify
                evidence=evidence if grounded else "",
                source_url=url or "",
                freshness=str(item.get("date") or "") if grounded else "",
            )
        )
    return FeatureSet(competitor=competitor, features=features)


# ── alignment (canonical taxonomy) ──────────────────────────────────────────────────────────────────
@dataclass
class CanonicalTaxonomy:
    canonical: list[str]
    mapping: dict[str, str]  # raw feature name -> canonical name
    #: True when clustering did NOT happen AT ALL and this is the identity fallback (budget exhausted,
    #: the LLM failed, or it answered an unusable shape). Load-bearing for the `us` column: an identity
    #: taxonomy cannot merge "E2E encryption" with a rival's "end-to-end encryption", so a MISSING
    #: verdict on our own product would be an artefact of the degradation, not a fact about the product.
    degraded: bool = False
    #: The canonicals of names the LLM did NOT map, when it mapped the rest. ⚠️ THIS EXISTS BECAUSE
    #: `degraded` ALONE WAS TOO COARSE, and the cost was measured, not theorised: with 21 names, a model
    #: that maps 20 correctly and echoes ONE key back lower-cased marked the whole taxonomy degraded and
    #: suppressed **19 of 20 TRUE gaps** — while the one at-risk row was ✅ anyway. The at-risk set is
    #: exactly these canonicals, not the whole grid.
    unmapped: frozenset[str] = frozenset()
    #: True when one of OUR OWN names was unmapped. THIS one IS global: if our membership set is
    #: unreliable, ANY row could be its unmerged synonym, so the whole column must answer ❓.
    us_unmapped: bool = False

    def canon(self, raw: str) -> str:
        # `mapping` is a HINT on a public deserializable dataclass, not enforcement: `mapping=None`
        # raised `AttributeError` out of two stages documented pure and never-raising. An unusable
        # mapping means every name is its own canonical — which is exactly the identity fallback this
        # module already degrades to, so the honest answer is `raw`, never a crash.
        return self.mapping.get(raw, raw) if isinstance(self.mapping, dict) else raw


def _identity_taxonomy(raw_names: Iterable[str]) -> CanonicalTaxonomy:
    uniq = list(dict.fromkeys(n for n in raw_names if n))
    return CanonicalTaxonomy(canonical=uniq, mapping={n: n for n in uniq}, degraded=True)


def _read_features(value: Any) -> tuple[list[Any], bool]:
    """``(elements, unreadable)`` — the second bit is the one that was missing.

    ⚠️ THE WHOLE BODY IS GUARDED, for the same reason `_stripped`'s is: every branch below asks
    `isinstance`, and `isinstance` calls the object's `__class__`, which a consumer can make raise.
    An accessor whose entire contract is "never raise" may not have an unguarded edge — and each of the
    last three rounds found a hole exactly one step outside the previous round's `try`. An object we
    cannot even classify is UNREADABLE, which is the honest answer and the one that fails toward
    distrust.

    ⚠️ THE SIXTH DOOR, and this change's own `try/except` cut it. Widening the guard to any `Collection`
    meant `list(value)` runs the CALLER's `__iter__`, so I wrapped it — and the wrapper returned a bare
    `[]`, which is BYTE-IDENTICAL to a caller who genuinely ships nothing. `_us_unusable` then answered
    False (it IS a `Collection`), `n_malformed` stayed 0, `trust_us` held, and every row took the ❌
    branch: the original defect, whole, reached through the fix for a different one. Measured against a
    HEALTHY taxonomy: `partial=False causes=[] drops={} us=❌ MATCH=['e2e']`.
    A refused or BROKEN container is not an empty one, and the difference has to be carried out of here.
    """

    try:

        if isinstance(value, (str, bytes, bytearray)):
            # ⚠️ THE SEVENTH DOOR, and it was this line's own comment. It read "refused, but not
            # 'unreadable'" — a distinction with no meaning downstream, because `unreadable=False` is what
            # `trust_us` reads as "we looked at the list and it is genuinely empty". `Us(features="sso")` —
            # a bare string, the single most ordinary caller mistake, and reachable from any JSON round trip
            # since `features: tuple[str, ...]` is a HINT, not enforcement — therefore produced a confident
            # ❌ on every rival feature and a full false MATCH. Measured through `run()`:
            # `partial=False causes=[] us=❌ MATCH=['pricing transparency']` for a product that ships it.
            # A REFUSAL IS NOT AN EMPTY LIST. Same for `None`/`int` below.
            logger.warning(
                "competitor_intel.feature_list_is_not_a_list type=%s — a bare string iterates CHARACTER BY "
                "CHARACTER, so it is refused; pass a list/tuple/set",
                type(value).__name__,
            )
            return [], True
        if isinstance(value, Collection):
            try:
                return list(value), False
            except Exception as exc:  # noqa: BLE001 — a caller's container must never break the run
                logger.warning(
                    "competitor_intel.us_features_unreadable type=%s cause=%s — treated as UNREADABLE",
                    type(value).__name__,
                    type(exc).__name__,
                )
                return [], True
        if isinstance(value, Iterable):
            # a one-shot iterator: re-iterable is required because `_us_features` runs twice per dossier
            logger.warning(
                "competitor_intel.us_features_not_reiterable type=%s — pass a list/tuple/set, not a "
                "generator: it would be empty on the second read and the `us` column would be wrong",
                type(value).__name__,
            )
            return [], True
        # Not iterable at all (`None`, an int, an object) — a refusal, not an empty list, for the same
        # reason as the string branch above. ⚠️ `None` INCLUDED, deliberately: the "I ship nothing" signal
        # is `()` (the dataclass default) or `[]`, never `None`. An explicit `None` is a wrong-typed value —
        # a JSON `null` where a list belonged — and this file already records it as a real caller shape
        # ("a caller passing `Us(features=None)` raised TypeError straight out of `run()`"). Reading it as
        # an empty list would publish a confident ❌ on every rival feature from a type error, which is the
        # falsehood this whole change exists to stop. The ambiguous case fails toward distrust.
        logger.warning(
            "competitor_intel.feature_list_is_not_a_list type=%s — not iterable; pass a list/tuple/set",
            type(value).__name__,
        )
        return [], True
    except Exception:  # noqa: BLE001 — an unclassifiable container is unreadable, never a crash
        logger.warning("competitor_intel.feature_list_unclassifiable — treated as UNREADABLE")
        return [], True

def _us_unusable(value: object) -> bool:
    """Was the caller's `features` REFUSED or BROKEN, as opposed to genuinely empty? Now covers both the
    one-shot iterator and the `Collection` whose iteration raises — one predicate, one source of truth."""
    return _read_features(value)[1]


# ── the guarded accessor layer ────────────────────────────────────────────────────────────────────────
# ⚠️ THIS EXISTS BECAUSE FIXING THE SITES DID NOT WORK. Four review rounds each hardened one read and
# the next round found the read one step away: the container was guarded and the ELEMENT was not; the
# element's `name` was guarded and its `state`/`freshness` were not; the VALUE was guarded and the
# ATTRIBUTE READ that produced it was not; `.strip()` was guarded in `_feature_name` and left raw in
# `_us_features`, its sibling predicate on the other population in the same file. Findings per round did
# not fall (9 → 7 → 10 → 12) and a seat observed that half of each round's findings sat inside the
# PREVIOUS round's hunk. "Repairs land on the failing site, not the class" is this repo's own recorded
# diagnosis of exactly that shape.
# So: every read of consumer-supplied data on the never-raising stages goes through ONE of these, at
# EVERY depth — the object, its attribute, the container, the element, the element's fields. A new
# depth is a new helper here, not another `try` at a call site.


#: :func:`_stripped` could not strip the value at all — a `str` subclass whose `strip` raised. Distinct
#: from ``None`` (a genuinely blank name), because one is a SHAPE loss and the other a content filter.
#: ⚠️ Collapsing these two was the defect a seat found one round earlier in `_feature_name`, and the
#: first version of this helper reproduced it verbatim: a raising `.strip` came back as `None` and was
#: dropped as silently as an empty string. The suite caught it because that round's regression test
#: asserts the DROP, not merely the survival — which is why that test asserts the drop.
_UNSTRIPPABLE: Final = object()


def _stripped(value: Any) -> Any:
    """A non-blank stripped `str` · ``None`` (blank) · :data:`_UNSTRIPPABLE`. Never a raise. THE ONE STRIPPER. 

    `.strip()` is not safe to call just because the value is a `str`: a `str` SUBCLASS may override it,
    and `Feature.name` / `Us.features` are public and deserializable. Measured — a `str` subclass whose
    `strip` raises killed BOTH public stages through `_us_features`, twenty lines from the guard
    `_feature_name` had just been given for the identical hazard on the rival population.
    """
    # ⚠️ THE WHOLE BODY, not just the `.strip()` call. The first version wrapped only the strip and left
    # `bool(out)` outside — so a `strip()` RETURNING a hostile `str` subclass (raising `__len__`) made
    # THE ONE STRIPPER itself raise, killing both public stages. `isinstance` is inside too: a raising
    # `__class__` defeats it. An accessor whose job is "never raise" may not have an unguarded edge —
    # that is the whole of its contract, and three separate rounds found a hole one step outside the
    # previous round's `try`.
    try:
        if not isinstance(value, str):
            return None
        out = value.strip()
        return out if isinstance(out, str) and out else None
    except Exception:  # noqa: BLE001 — an unusable name is not a crash, but it IS a loss worth reporting
        return _UNSTRIPPABLE


def _norm(value: Any) -> str:
    """A consumer field as a stripped lowercase `str`, or ``""`` — never a raise. THE ONE NORMALISER.

    `Signal` is a public deserializable dataclass whose `sentiment`/`aspect`/`competitor`/`source_url`
    are `str` HINTS. `gap_synthesis` read all four with a bare `(x or "").strip().lower()`, so
    `Signal(sentiment=7)` raised `AttributeError` and a raising `@property` raised straight out of the
    THIRD pure stage — the one the accessor layer never reached, because the layer was built while
    fixing findings in the other two.
    """
    # ⚠️ REJECTS a non-`str`, never coerces — and the first version coerced, which turned a loud
    # failure into a FABRICATED competitive finding. Measured against HEAD, where each of these raised:
    #     aspect=["billing","cost"]  →  BEAT theme "['billing', 'cost']"
    #     aspect=7                   →  BEAT theme "7"
    #     aspect={"k":"v"}           →  BEAT theme "{'k': 'v'}"
    # A rendered BEAT theme is an opening the operator is told to attack. This file rules on that trade
    # three separate times — "a fabrication is indistinguishable from a finding", and "turned a loud
    # failure into a quiet one — the trade this module refuses" — and `_feature_name` / `_us_features`
    # both REJECT a non-str name for exactly this reason. One population, one verdict.
    if not isinstance(value, str):
        return ""
    _s = _stripped(value)
    if not _usable(_s):
        return ""
    try:
        return str(_s).lower()
    except Exception:  # noqa: BLE001 — an unusable field is empty, never a crash
        return ""


def _usable(stripped: Any) -> bool:
    """Is a :func:`_stripped` result a name we may USE? ONE definition of usable.

    `_stripped` has three outcomes and only one of them is usable, so `is not None` is a bug waiting to
    be written — and it was written, in the row lane, where it kept an `_UNSTRIPPABLE` canonical as a
    matrix row that could never match `us_canon`. Every lane asks THIS, so no lane can disagree.
    """
    return isinstance(stripped, str) and bool(stripped)


def _number_or_none(value: Any) -> float | None:
    """A real number, or ``None`` — never a raise. Guards the USE, not only the read.

    ⚠️ `Signal.rating` reaches `trust.source_weight`, which compares it (`rating <= 1.0`). Reading the
    attribute safely and then handing the value to `<=` moves the raise one function over: measured,
    `TypeError: '<=' not supported between instances of '_BoolBoom' and 'float'` at `trust.py:116`, out
    of `gap_synthesis`. `bool` is excluded deliberately — `True <= 1.0` is legal and would silently
    weight a source as if it were rated 1.0.

    ⚠️ RESIDUAL, REPORTED NOT FIXED HERE: `source_weight` is PUBLIC and its own neighbouring branch says
    "a scalar we cannot interpret → no self-published discount, never a raise", so its rating arm is
    inconsistent with its stated contract. `trust.py` is outside this change's surface; a consumer
    calling `source_weight(url, rating=<non-numeric>)` directly still gets the `TypeError`. Recorded in
    the review artifact rather than widened into unrelated work.
    """
    # ⚠️ REJECT BY TYPE, ACCEPT BY BEHAVIOUR. The first version allow-listed `(int, float)`, which
    # EXCLUDES `Decimal`, `Fraction` and numpy scalars — and HEAD passed `rating` through RAW, where
    # `2.0 <= rating <= 4.0` works on all of them. So the guard REGRESSED an answer that was right:
    #     ratings as Decimal("3.0") → BEAT [('billing', 1.6), ('support', 1.6)]   ← a TIE
    #     ratings as float 3.0      → BEAT [('billing', 2.0), ('support', 1.6)]   ← correct order
    # `json.loads(parse_float=Decimal)`, a SQLAlchemy `Numeric` column and pandas review mining all
    # produce these, `beat.sort` orders the "your openings" section, and `weight` ships in `to_dict()`.
    # A guard that silently reorders a published ranking is worse than the raise it replaced.
    # `bool` stays excluded deliberately (`True <= 1.0` is legal and would weight a source as if rated
    # 1.0); `str`/`bytes` stay excluded because `float("3")` would accept a string rating that no
    # producer in this module emits. Everything else is asked, not classified.
    if isinstance(value, bool) or isinstance(value, (str, bytes, bytearray)):
        return None
    try:
        out = float(value)   # int · float · Decimal · Fraction · numpy scalars · any __float__
    except Exception:  # noqa: BLE001 — an uninterpretable rating is absent, never a crash
        return None
    return out if out == out else None   # NaN is not a rating


def _truthy_attr(obj: Any, attr: str) -> bool:
    """``bool(getattr(obj, attr))`` that cannot raise — the READ and the TRUTHINESS TEST together.

    `bool(_safe_attr(...))` guards only the read: `__bool__` is overridable and raises at the caller's
    own line, outside the accessor. Measured on a `has_us` whose `__bool__` raises.
    """
    try:
        return bool(_safe_attr(obj, attr, False))
    except Exception:  # noqa: BLE001 — an unreadable flag is False, never a crash
        return False


def _safe_dget(mapping: Any, key: Any) -> Any:
    """``mapping.get(key)`` that cannot raise — a `dict` SUBCLASS may override `get`, and `key` may have
    a raising `__hash__`/`__eq__`. `dossier.py` records this exact archetype IN THIS SAME CHANGE
    ("a `dict` SUBCLASS whose `get()` raises defeats the `isinstance(c, dict)` check"); it had not been
    propagated one file over, where `subject_domains` and `CanonicalTaxonomy.mapping` are both
    consumer-supplied mappings read behind an `isinstance` that cannot see method behaviour."""
    try:
        return mapping.get(key)
    except Exception:  # noqa: BLE001 — an unreadable mapping answers nothing, never a crash
        return None


def _usable_str(stripped: Any) -> str:
    """:func:`_stripped`'s result as a usable `str`, or ``""``. The value form of :func:`_usable`.

    Exists because `_stripped(...) or ""` LOOKS like it collapses the three outcomes and does not:
    `_UNSTRIPPABLE` is a truthy sentinel and survives it.
    """
    return stripped if _usable(stripped) else ""


def _rank(state: Any) -> int:
    """`_STATE_RANK` lookup that cannot raise. A cell state is a HINT, not enforcement.

    Guarding the READ of `.state` and then handing the value to `dict.get` moves the raise one line
    down: `dict.get` raises `TypeError: unhashable type` on a list. Measured on `Feature(state=[])`.
    An unrankable state is the weakest state, which is what `UNKNOWN` already means.
    """
    # `Exception`, not `TypeError`: the guard was justified on `Feature(state=[])` (unhashable →
    # `TypeError`), which named the ARCHETYPE and not the CONTRACT. `__hash__` is overridable and may
    # raise anything at all — measured on a `__hash__` raising `ValueError`, which walked straight
    # through and out of `build_matrix`. An unrankable state ranks lowest whatever the reason.
    try:
        return _STATE_RANK.get(state, 0)
    except Exception:  # noqa: BLE001 — an unrankable state ranks lowest
        return 0


def _rival_features(rival: Any) -> list[Any]:
    """A rival's feature elements, through the attribute read AND the container guard. ONE READER.

    `_feature_list(r.features)` guards the CONTAINER while the attribute read that produces it is bare —
    so `SimpleNamespace(competitor="R1")` (the attrdict-deserializer shape this file already cites as the
    measured motivation for the element guard, one level up) raised `AttributeError`, and a raising
    `@property features` raised straight through both stages.
    """
    return _feature_list(_safe_attr(rival, "features", ()))


def _rival_name(rival: Any) -> str:
    """A rival's display name, through the attribute read AND the coercion. Coerced, not rejected —
    a nameless COLUMN still carries that rival's real measured cells, so dropping it would lose data."""
    return _safe_str(_safe_attr(rival, "competitor", ""))


def _us_source(us: Any) -> Any:
    """Whatever the caller put in `Us.features`, read without raising. The three call sites that reach
    for it — `_us_features`, and `_us_unusable` in each stage's `trust_us` — must read it identically."""
    return _safe_attr(us, "features", ())


#: Returned by :func:`_feature_name` for an element that is not a `Feature` AT ALL (no readable `name`),
#: and :data:`_BAD_NAME` for a `Feature` whose `name` is present but unusable (non-`str`, or a read that
#: raised). BOTH are SHAPE losses and both are reported; a `Feature` whose name is merely BLANK is a
#: CONTENT filter and is not. The module already draws exactly this line for `us`
#: (`take(shape=..., want=...)`), and collapsing the first two into one silent `None` is what let a real
#: rival capability vanish with `partial=False degrade_causes=[]`.
_NO_NAME: Final = object()
_BAD_NAME: Final = object()


def _feature_name(feat: Any) -> Any:
    """A rival feature's usable name · ``_NO_NAME`` · ``_BAD_NAME`` · ``None`` (blank, a content filter).

    ⚠️ THE ELEMENT HALF OF A CONTRACT THAT WAS ONLY HALF KEPT. `_feature_list` guards the CONTAINER —
    it is why `FeatureSet(features=None)` stopped raising — and both call sites then read `f.name`
    directly, which PRESUPPOSES the element is a `Feature`. Fuzzed, 120 of 800 calls raised
    `AttributeError` out of two stages whose docstrings say pure and never-raising, after discovery and
    every review leg had been billed:

        FeatureSet(features=["sso"])            → 'str' object has no attribute 'name'
        FeatureSet(features=[{"name": "sso"}])  → 'dict' object has no attribute 'name'

    A list of NAMES instead of `Feature`s is the most ordinary caller mistake, and a list of DICTS is
    what any hand-rolled JSON deserializer produces.

    ⚠️ AND FOUR RETURN VALUES, NOT THREE — the first version had three and collapsed the two that
    matter. `Feature(name=7)` returned the SAME `None` as `Feature(name="")`, so a shape loss was
    dropped as silently as a blank. Measured end to end, against the well-formed control:

        A0 well-formed          rows=['SSO','e2e encryption']  MATCH=['e2e encryption']  drops={}
        A1 Feature(name=7)      rows=['SSO','e2e encryption']  MATCH=[]                  drops={}
        A3 a bare str element   …                              MATCH=[]  drops={('rival_features','R1'):1}

    A1 loses a TRUE gap and reports nothing: `partial=False degrade_causes=[]`, so `/fabrik-spec` is fed
    "no gaps found" by a run that lost one. At HEAD that same input CRASHED (`"\n".join(raw_names)` on an
    int), so this change had turned a loud failure into a quiet one — the trade this module refuses.

    ⚠️ READS THROUGH `_safe_attr`, not `getattr`: bare `getattr` swallows only `AttributeError`, and a
    raising `__getattr__` or a raising `@property name` — the archetype `dossier._has` documents one file
    over — still escaped as `RuntimeError`/`ValueError`. `.strip()` is guarded for the same reason: a
    `str` SUBCLASS may override it.

    Drops, never coerces: `str(feat)` on a dict would FABRICATE the name `"{'name': 'sso'}"`, and this
    file has already ruled twice that "a fabrication is indistinguishable from a finding".
    """
    nm = _safe_attr(feat, "name", _NO_NAME)
    if nm is _NO_NAME:
        return _NO_NAME
    if not isinstance(nm, str):
        return _BAD_NAME
    _s = _stripped(nm)          # THE ONE STRIPPER — see `_stripped`
    return _BAD_NAME if _s is _UNSTRIPPABLE else _s


def _us_features(us: Us) -> Taken:
    """THE ONE PREDICATE for "which of the caller's own feature names are usable".

    ⚠️ There were TWO, and the file said so out loud: `align_features`' filter carried the comment
    "to MATCH build_matrix's `taxonomy.canon(uf.strip())` lookup", i.e. a manual sync between two
    independent normalizations of one population — the same class Phase B collapsed for `discovered`,
    documented rather than removed. Let them drift and `align_features` clusters a name that
    `build_matrix` then cannot find, so the `us` column reads ❌ MISSING for a feature we actually have
    and it is published as a MATCH gap: the tool tells you to build something you already shipped.

    A non-str entry is a SHAPE loss (a caller passing `Us(features=[1, 2, 3])` loses all of them), which
    is why the reporting caller hands it to the meter. A blank string is a content filter and reports
    nothing.
    """
    return take(
        _feature_list(_us_source(us)),   # the attribute read too — see `_us_source`
        site="us_features",
        # ⚠️ `_stripped`, not a bare `.strip()` — this is the SIBLING predicate of `_feature_name` on the
        # other population, and it called `.strip()` raw in all three lambdas. A `str` subclass whose
        # `strip` raises therefore killed BOTH public stages from here, twenty lines from the guard
        # `_feature_name` had just been given for the identical hazard. An unstrippable name is a SHAPE
        # loss (it fails `shape`, so it counts into `n_malformed` and reaches the meter), never a
        # content filter — the same three-way this file draws for a rival's `Feature.name`.
        shape=lambda uf: isinstance(uf, str) and _stripped(uf) is not _UNSTRIPPABLE,
        want=lambda uf: _stripped(uf) is not None,
        value=lambda uf: _stripped(uf) or "",
    )


async def _align_features_inner(
    rivals: Sequence[FeatureSet], us: Us | None, *, meter: LlmMeter
) -> CanonicalTaxonomy:
    """Cluster feature names across rivals (+ us) into a canonical taxonomy via lean LLM semantic
    clustering. Degrades to an identity taxonomy (each name its own canonical) when the budget is exhausted
    or the LLM fails — so the matrix still builds, just without synonym merging."""
    # ⚠️ REJECT, not coerce — the same ruling `build_matrix` makes below, and for the same reason: a
    # coerced name FABRICATES a feature. Unguarded, a non-str `Feature.name` raised out of a function
    # documented never-raising — `"\n".join(raw_names)` on an int, `dict.fromkeys` on a dict — with
    # discovery and every review leg already billed. `Feature` is public and deserializable.
    # `_feature_list` on `.features` too (this module's own re-iterability guard; `_seq` is dossier's): `FeatureSet.features` is the SIBLING FIELD of `competitor`, which this
    # same change guards twelve lines away under the note that "guarding one seam and not its sibling
    # twelve lines away is how the never-raise contract keeps almost holding". `features=None` or `=7`
    # raised `TypeError: not iterable` out of this documented never-raising stage.
    # ⚠️ `_feature_name`, not `f.name` — the guard above is on the CONTAINER; this is the ELEMENT. A
    # `FeatureSet(features=["sso"])` (names, not `Feature`s) raised `AttributeError` from inside this
    # very comprehension, because `isinstance(f.name, str)` checks the TYPE of `.name` while assuming
    # it EXISTS. A shape loss is reported on the meter lane — the same channel `us` element losses use —
    # so the dossier learns a rival's feature list was partly unreadable instead of silently shrinking.
    raw_names: list[str] = []
    for r in rivals:
        _n_shape = 0
        for f in _rival_features(r):
            _nm = _feature_name(f)
            if _nm is _NO_NAME or _nm is _BAD_NAME:
                _n_shape += 1          # a SHAPE loss — reported; a BLANK name is a content filter
            elif _nm:
                raw_names.append(_nm)
        if _n_shape:
            meter.note_drops("rival_features", _rival_name(r), _n_shape)
    #: OUR OWN usable names, seeded EMPTY so it is bound on every path — the `if us:` branch below is
    #: the only thing that fills it, and the return statement reads it unconditionally.
    _us_kept: set[str] = set()
    # `us is not None`, NOT truthiness — `build_matrix` gates on identity, and a subclass defining
    # `__len__` made the two diverge: `align_features` skipped our names entirely while `build_matrix`
    # still built a us column with `trust_us` satisfied. One population, one predicate.
    if us is not None:
        # stripped + str-guarded, to MATCH build_matrix's `taxonomy.canon(uf.strip())` lookup (a padded or
        # non-str us feature must not desync the two) and to stay never-raise on a bad caller tuple.
        # ⚠️ the CONTAINER, not only each element. `isinstance(uf, str)` guards the items and was
        # added to stay never-raise on a bad caller tuple — it guards half the shape. A caller
        # passing `Us(features=None)` raised TypeError straight out of `run()`, AFTER discovery
        # and every review leg had been billed, and past the documented `except ValueError:`.
        _us = _us_features(us)
        # a non-str `us` feature is evidence the CALLER gave us and we could not use — reported on the
        # meter lane (subject "us"), never as a provider failure. A blank one is a content filter.
        meter.note_drops("us_features", "us", _us.n_malformed)
        # ⚠️ AND the refusal itself, which `n_malformed` cannot express: a refused one-shot iterator
        # counts ZERO drops, so without this the dossier never learns our feature list was unreadable.
        if _us_unusable(_us_source(us)):
            meter.note_drops("us_features", "us", 1)
        raw_names += _us.kept
        _us_kept = set(_us.kept)  # reused at the return; see the note there
    raw_names = list(dict.fromkeys(n for n in raw_names if n))
    if not raw_names:
        return CanonicalTaxonomy(canonical=[], mapping={})

    prompt = (
        "Cluster these product-feature names into canonical features (merge synonyms like 'SSO' and "
        '\'single sign-on\'). Output ONLY JSON {"canonical": [..], "mapping": {"<raw>": "<canonical>"}}. '
        "Every input name must appear as a key in mapping.\n\nNAMES:\n"
        + "\n".join(raw_names)
    )
    parsed = _parse_json(await meter.call(prompt))
    if not isinstance(parsed, dict):
        return _identity_taxonomy(raw_names)
    canonical = parsed.get("canonical")
    mapping = parsed.get("mapping")
    if not isinstance(canonical, list) or not isinstance(mapping, dict):
        return _identity_taxonomy(raw_names)
    # every raw name must resolve; fall back to itself if the LLM dropped it.
    # ⚠️ REJECT a non-str / blank mapping value — do NOT `str()` it. This is the MIRROR of an element
    # drop: `str(mapping.get(n, n))` FABRICATES an element rather than losing one. An LLM answering
    # `{"SSO": null}` — a routine way to say "no canonical for this" — produced the literal canonical
    # feature name `"None"`, which then became a matrix ROW and a MATCH item titled `None`, reported to
    # the operator as a real competitive gap. A drop is visible as an absence; a fabrication is
    # indistinguishable from a finding, which is why it gets a reject and not a counter.
    def _canon_of(raw: str) -> str:
        mapped = mapping.get(raw, raw)
        if isinstance(mapped, str) and mapped.strip():
            return mapped.strip()
        return raw  # unusable mapping → the name is its own canonical, never `str(None)`

    clean_map = {n: _canon_of(n) for n in raw_names}
    # BOTH branches deduped: the `clean_map.values()` fallback (taken when the LLM returns an empty
    # `canonical`) maps several raw names onto one canonical, so an un-deduped fallback rendered the
    # SAME feature as two identical matrix rows and two identical MATCH items.
    # ⚠️ Same reject as `_canon_of`, on the sibling field: `str(c)` on a non-str entry FABRICATES a
    # canonical feature out of the LLM's own malformed output — a dict entry rendered as the literal
    # feature name `"{'name': 'SSO'}"`. Only real, non-blank strings become canonical names.
    canon_list = list(
        dict.fromkeys(c.strip() for c in canonical if isinstance(c, str) and c.strip())
    ) or list(dict.fromkeys(clean_map.values()))
    # ⚠️ WHAT THIS DOES **NOT** CATCH, stated because the first version of this comment implied it did:
    # an answer that maps EVERY name but clusters badly. `{"SSO":"SSO","single sign-on":"single
    # sign-on"}` leaves `unmapped` empty and every flag False, yet nothing merged — and the false ❌
    # returns in full. Echo-the-input is a common cheap-model failure. It is NOT closable by any
    # mapping-SHAPE property: a pure identity map is also the CORRECT answer for a market of genuinely
    # distinct features, so "identity ⇒ degraded" would false-alarm on every healthy diverse market
    # (verified against this change's own regression tests). Distinguishing the two requires knowing
    # whether two names MEAN the same thing — precisely the judgement the LLM was called for. Documented
    # as a residual in README § Gotchas rather than papered over.
    # ⚠️ `degraded` IS A PROPERTY OF THE MAPPING, NOT OF WHICH `return` WE REACHED. This line used to
    # ship `degraded=False` because it is the "success" path — but `_canon_of` falls back to `raw` for
    # every name the LLM failed to map, so a model that answers a well-formed dict while OMITTING names
    # (exactly what the prompt's "Every input name must appear as a key in mapping" exists to prevent,
    # i.e. the instruction models most often ignore) produced a byte-identical identity taxonomy that
    # called itself healthy. Measured, three real answer shapes — `{"canonical":[],"mapping":{}}`, a
    # mapping omitting only OUR name, and a canonical with an empty mapping — each reproduced the
    # original defect verbatim: ❌ MISSING for a feature we ship, published as a MATCH gap.
    # ⚠️ COST, stated rather than discovered later: this is deliberately COARSE — ONE unmapped name of
    # twenty marks the whole taxonomy degraded, so the entire `us` column answers ❓ and the MATCH list
    # empties. That widening is the price of never publishing a false ❌, and it is the direction this
    # module already chooses elsewhere ("the ambiguous case fails toward distrust"). It is not
    # per-row because an unmapped RIVAL name is equally capable of the false ❌: its row simply never
    # merges with our synonym. `TaxonomyDegraded` names it in the dossier, so the widening is visible.
    unmapped = [
        n for n in raw_names
        if not isinstance(mapping.get(n), str) or not str(mapping.get(n, "")).strip()
    ]
    # ⚠️ PER-ROW, NOT WHOLE-GRID — the coarse `degraded=bool(unmapped)` this replaces was measured
    # suppressing 19 of 20 TRUE gaps on a single echoed key. An unmapped name puts ITS canonical at
    # risk (it never merged with anyone), and that is a bounded set. The one genuinely global case is
    # an unmapped name of OURS: then `us_canon` itself is unreliable and any row could be its
    # unmerged synonym, so the whole column owes ❓.
    # ⚠️ REUSE `_us_kept`, do NOT re-call `_us_features(us)` here. My first version did, which was a
    # third call of the helper in one run AND depended on `us is not None` being re-evaluated
    # identically at two points in the same function — the exact two-predicates-for-one-population
    # shape `_us_features` exists to collapse. `_us_kept` is seeded empty above so it is bound on
    # every path.
    us_unmapped = any(n in _us_kept for n in unmapped)
    if unmapped:
        logger.warning(
            "competitor_intel.taxonomy_partial n_unmapped=%d of %d ours=%s",
            len(unmapped), len(raw_names), us_unmapped,
        )
    return CanonicalTaxonomy(
        canonical=canon_list,
        mapping=clean_map,
        unmapped=frozenset(key_safe(_canon_of(n)) for n in unmapped),
        us_unmapped=us_unmapped,
    )


# ── matrix ────────────────────────────────────────────────────────────────────────────────────────────
#: The separator joining ``(feature, column)`` into the flat string key ``to_dict()`` emits — U+241F
#: SYMBOL FOR UNIT SEPARATOR. Deliberately a character that cannot occur in a feature or competitor name
#: (unlike ``|`` or ``:``, which routinely do), so the key round-trips unambiguously through JSON.
#:
#: **Exported because guessing it fails QUIETLY.** A consumer that assumes ``"<row>|<col>"`` gets a miss on
#: every lookup, and since a missing cell legitimately means ``❓ UNKNOWN``, the result is a full grid of
#: ❓ that reads as "we learned nothing about this market" rather than "your key is wrong". Build keys with
#: :func:`cell_key`, or split on this constant. (Reported by a consumer, 2026-08-26.)
CELL_KEY_SEP: Final = "␟"

#: The reserved column key for *our* product. Pre-claimed in `build_matrix` so no rival can take it.
_US_COLUMN: Final = "us"


def _safe_str(value: object) -> str:
    """A JSON-safe string — never raising. See `stages._scalar` for why exported self-serializing
    types need their own guard rather than relying on `Dossier`'s trailing sweep."""
    if type(value) is str:
        return value
    try:
        return str(value)
    except Exception:  # noqa: BLE001 — serialization must never raise after the money is spent
        return f"<unrenderable {type(value).__name__}>"


def _safe_attr(obj: object, attr: str, default: Any = "") -> Any:
    """`getattr` that cannot raise — see `dossier._attr`.

    ⚠️ `default: Any`, widened from `str`, so a SENTINEL can be the default. `_feature_name` has to tell
    "no `name` attribute at all" from "a `name` that is the empty string", and only a distinct object
    can carry that. The return was already `Any`; the parameter was the narrower half of one signature.
    """
    try:
        return getattr(obj, attr, default)
    except Exception:  # noqa: BLE001 — serialization must never raise after the money is spent
        return default


def cell_key(feature: str, column: str) -> str:
    """The flat ``to_dict()['feature_matrix']['cells']`` key for one cell. Use this instead of formatting
    the separator by hand — see :data:`CELL_KEY_SEP` for why a guessed separator fails silently."""
    return f"{feature}{CELL_KEY_SEP}{column}"


def key_safe(name: str) -> str:
    """Strip :data:`CELL_KEY_SEP` out of a feature or competitor name, so :func:`cell_key` is genuinely
    unambiguous.

    ⚠️ This ENFORCES an invariant the README states. Without it the claim was merely a hope: feature names
    come from LLM JSON over scraped text and competitor names come from discovery cards, so a page can
    publish a U+241F and produce ``cell_key("a", "b␟C") == cell_key("a␟b", "C")`` — two distinct cells
    collapsing to ONE in ``to_dict()``, silently losing the other. Applied at ingest (:func:`build_matrix`)
    rather than inside ``cell_key``, so the sanitized name is what appears in ``rows``/``columns`` too and
    a consumer's lookup of the name they can SEE always hits.
    """
    return name.replace(CELL_KEY_SEP, " ")


@dataclass(frozen=True)
class MatrixCell:
    state: str  # HAS / MISSING / PARTIAL / UNKNOWN
    freshness: str = ""  # ISO date if known, else ""


@dataclass
class Matrix:
    columns: list[str]  # competitor names (+ "us" when us is defined)
    rows: list[str]  # canonical feature names
    cells: dict[tuple[str, str], MatrixCell] = field(default_factory=dict)
    has_us: bool = False

    def cell(self, feature: str, column: str) -> MatrixCell:
        return self.cells.get((feature, column), MatrixCell(state=UNKNOWN))

    def to_dict(self) -> dict[str, Any]:
        return {
            # ⚠️ JSON-safe here too: `Matrix` is exported, so a consumer calls this directly and gets
            # no `_json_safe` sweep from `Dossier`. A set of columns, or an `object()` element, made
            # `json.dumps` fail on the type's OWN method while the Dossier path silently rescued it.
            "columns": [_safe_str(c) for c in (self.columns if isinstance(self.columns, (list, tuple, set, frozenset)) else ())],
            "rows": [_safe_str(r) for r in (self.rows if isinstance(self.rows, (list, tuple, set, frozenset)) else ())],
            "has_us": bool(self.has_us) if isinstance(self.has_us, bool) else False,
            # ⚠️ `cells` is typed `dict[tuple[str, str], MatrixCell]` and NOT enforced — `Matrix` is
            # exported. A non-dict, or an entry whose key is not a 2-tuple or whose value is not a
            # cell, raised straight out of `to_dict()`. Found by a GENERATED cross-product test rather
            # than by a reviewer naming the field, which is the point of generating it.
            "cells": {
                # ⚠️ `getattr(..., default)` covers only `AttributeError` too — a raising @property
                # on a cell defeated it, while `to_markdown`'s twin (`_safe_cell`) was already safe.
                # The module's own comment says to_dict() gets the SAME guards; here it did not.
                cell_key(_safe_str(k[0]), _safe_str(k[1])): {"state": _safe_str(_safe_attr(v, "state")), "freshness": _safe_str(_safe_attr(v, "freshness"))}
                for k, v in (self.cells.items() if isinstance(self.cells, dict) else ())
                if isinstance(k, tuple) and len(k) == 2
            },
        }


def _build_matrix_inner(
    taxonomy: CanonicalTaxonomy, rivals: Sequence[FeatureSet], us: Us | None
) -> Matrix:
    """The comparison matrix. With ``us`` → us-vs-them (a ``us`` column of ✅/❌ — or ❓ when the
    taxonomy is ``degraded`` and membership cannot be trusted — per canonical feature,
    computed by canonicalizing ``us.features`` through the SAME taxonomy — exact set membership, no fragile
    substring match); without ``us`` → the rival-vs-rival category landscape. Cells default to ``❓`` (a
    rival that never mentioned a feature is unverified, not 'missing')."""
    # `key_safe` at ingest: rows/columns/cells all carry the sanitized name, so `cell_key` is
    # unambiguous and a consumer looking up the name they can SEE in `rows` always hits.
    # Rows are DE-DUPLICATED, not suffixed — see the warning on `_uniquify`. Cells are keyed by
    # `key_safe(taxonomy.canon(...))`, so a suffixed row is unreachable by construction: it renders as an
    # all-❓ phantom while both real features collapse into the first row and become one ★ universal gap.
    # ⚠️ THE TAXONOMY'S OWN TWO ORIGINAL FIELDS, guarded here for the reason this change already gave
    # for the THIRD one it added: "`taxonomy.unmapped` is a field this change ADDED to a public,
    # deserializable dataclass, and `x not in <non-iterable>` raises — the same premise used to justify
    # guarding `FeatureSet.competitor`, applied to my own new field." `canonical` and `mapping` are the
    # same shape of hint on the same dataclass and were left raw. Measured:
    #     canonical=None   → TypeError: 'NoneType' object is not iterable
    #     mapping=None     → AttributeError: 'NoneType' object has no attribute 'get'
    #     canonical="sso"  → rows=['s','o','sso']       ← SILENT, and the worst of the three
    # The last is the str-is-a-sequence trap this file documents four separate times: one matrix ROW per
    # CHARACTER, fabricated, with no cause and no flag. `_feature_list` already refuses `str`/`bytes`
    # for exactly this reason, so the fix is to reuse it rather than to add a fifth bespoke check.
    # ⚠️ `is not None` IS TRUE FOR `_UNSTRIPPABLE` — three lanes, and this one reached a different
    # verdict from the other two on the identical value. The rival lane drops an unstrippable name
    # (`_BAD_NAME`, reported); the us lane drops it (fails `shape`, counted); this lane KEPT it as a
    # row. Such a row can never match `us_canon`, which is built from plain `str`s — so it is a
    # guaranteed ❌/❓ on a capability we may well ship, which is the defect this whole change exists
    # to end. Three lanes over one population must agree, or the population has three meanings.
    rows = list(dict.fromkeys(
        key_safe(c) for c in _feature_list(taxonomy.canonical)
        if isinstance(c, str) and _usable(_stripped(c))
    ))
    # `columns[i]` is the rendered name of `rivals[i]`; the per-rival cell key below uses the SAME entry,
    # so a suffixed duplicate keeps its own cells instead of resolving to the first rival's.
    # `"us"` is reserved BEFORE rivals claim names: it is appended below, and without this a rival
    # literally named `us` produced a duplicate column whose lookup resolved to the us-cell — rendering
    # our ❌ in place of that rival's ✅ and dropping the rival from the matrix entirely.
    columns = _uniquify(
        # `_safe_str` here for the SAME reason as the feature name below — `FeatureSet.competitor` is
        # equally public and equally deserializable, and `key_safe` equally calls `.replace`. Guarding
        # one seam and not its sibling twelve lines away is how the never-raise contract keeps almost
        # holding. (Coerced, not rejected, unlike the feature name: a nameless COLUMN still carries the
        # rival's real cells, so dropping it would lose measured data — whereas a nameless ROW carries
        # nothing but its own fabricated title.)
        (key_safe(_rival_name(r)) for r in rivals), reserved=(_US_COLUMN,)
    )
    cells: dict[tuple[str, str], MatrixCell] = {}
    for column, r in zip(columns, rivals, strict=True):
        # a rival may list several raw features mapping to one canonical; strongest state wins.
        best: dict[str, str] = {}
        fresh: dict[str, str] = {}
        for feat in _rival_features(r):  # the SAME reader as align_features — see `_rival_features`
            # ⚠️ REJECT, DO NOT COERCE. `Feature` is PUBLIC and deserializable, so `name` is typed
            # `str` and is not guaranteed to be one; `key_safe` calls `.replace` on whatever arrives, so
            # a `None` name raised `AttributeError` out of a stage documented pure and never-raising,
            # after the money was spent. My first fix wrapped it in `_safe_str` — which FABRICATES the
            # row `"None"`, and `"None"` is truthy, so it sails past the blank guard below and lands in
            # the brief as `MATCH=[('None', universal=True)]`: a nameless ★ gap reported to the operator
            # as a real competitive hole. This module already ruled on exactly that trade 170 lines up:
            # "A drop is visible as an absence; a fabrication is indistinguishable from a finding, which
            # is why it gets a reject and not a counter." A crash and a fabrication are both wrong; the
            # fix for one must not be the other.
            # ⚠️ `_feature_name` reads the element THROUGH the same helper `align_features` uses, for
            # the same reason `_feature_list` is shared: two readers of one population drift. Here the
            # not-a-`Feature` case is merely SKIPPED — this stage is pure and holds no meter, and
            # `align_features` has already reported the loss on the run that produced this taxonomy.
            raw_name = _feature_name(feat)
            if raw_name is _NO_NAME or raw_name is _BAD_NAME or not raw_name:
                continue
            # ⚠️ AND THE CANON TOO, for the identical reason as the raw name two lines up. I rejected
            # `feat.name` BECAUSE coercing it fabricates a row — then coerced `taxonomy.canon(...)`,
            # whose value comes from an equally-unguarded public `dict[str, str]`. A mapping of
            # `{"end-to-end encryption": None}` gave `rows=['None'] us={'None':'❌'}
            # MATCH=[('None', universal=True)]`: the same nameless ★ gap, one line over. `_canon_of`
            # already rules this way at its own seam — an unusable mapping value means the name is its
            # own canonical, never `str(None)`.
            # ⚠️ `_stripped`, not a bare `.strip()`. The layer guarded the mapping CONTAINER
            # (`canon` checks `isinstance(self.mapping, dict)`) and read its VALUES raw — one level
            # deeper than the layer reached. A `mapping={"sso": RaisingStrip("sso")}` raised out of
            # this pure stage with the clustering call already billed.
            _mapped = taxonomy.canon(raw_name)
            if not _usable(_stripped(_mapped)):
                _mapped = raw_name
            canon = key_safe(_mapped)
            # ⚠️ A BLANK CANONICAL IS NOT A FEATURE, and this function used to disagree with its own
            # sibling about that. `align_features` filters falsy names out of `raw_names` (`if n`), so a
            # `Feature(name="")` leaves NOTHING to cluster — the no-raw-names early return, which is
            # honestly `degraded=False`. `build_matrix` then built a `''` row from that same feature
            # anyway, and the healthy-taxonomy branch marked it ❌ for us: a MATCH item with an EMPTY
            # feature name, i.e. the brief telling the operator to go build "". Executed:
            #   rows=[''] us cells={'': '❌'} MATCH=['']
            # The fix is agreement, not another `degraded` special case — the taxonomy is right that
            # there was nothing there. `extract_features` already strips and rejects blanks, so this is
            # only reachable from a hand-built `FeatureSet`; it is still a published falsehood.
            # ⚠️ DEFENCE-IN-DEPTH, NOT LIVE — stated honestly because the comment above used to present
            # a measured reproduction as THIS line's justification. It cannot fire: `raw_name` is already
            # `isinstance(str) and .strip()` (the reject above), `_mapped` likewise (or it falls back to
            # `raw_name`), and `key_safe` only substitutes U+241F for a space — it removes nothing. The
            # `Feature(name="")` reproduction is real but is prevented by the sibling guard added in this
            # same hunk, and `test_a_BLANK_feature_name_...` passes through THAT guard, not this one.
            # Deleting it changes no behaviour and kills no test; it stays as a floor for a future
            # `key_safe` that does remove characters. A guard that cannot fire must not claim it does.
            if not canon:
                continue
            if canon not in rows:
                rows.append(canon)
            prev = best.get(canon, UNKNOWN)
            # ⚠️ THE SIBLING ATTRIBUTES TOO. Guarding `name` and leaving `state`/`freshness` raw made the
            # two stages DISAGREE: `align_features` needs only `.name`, so it accepted an element that
            # `build_matrix` then crashed on — `run()` calls them in sequence, so the run died HERE with
            # the clustering call already billed. Measured on `SimpleNamespace(name="e2e encryption")`,
            # the shape any attrdict-style JSON deserializer produces:
            #     align_features: OK   →   build_matrix: AttributeError: no attribute 'state'
            # "Guarding one seam and not its sibling twelve lines away is how the never-raise contract
            # keeps almost holding" — this file, about this exact shape, twice before.
            new_state = _stronger(prev, _safe_attr(feat, "state", UNKNOWN))
            if (
                new_state != prev
            ):  # this feat strictly improved the state → ITS freshness wins (set OR clear)
                fresh[canon] = _safe_attr(feat, "freshness", "")
            best[canon] = new_state
        for canon, state in best.items():
            cells[(canon, column)] = MatrixCell(
                state=state, freshness=fresh.get(canon, "")
            )
    has_us = us is not None
    if us is not None:
        # "us" is the reserved us-column key. A rival literally named "us" would fold into it (a silent
        # treat-as-us on a degenerate input — no crash, no money error, no fabricated data).
        columns.append(_US_COLUMN)
        # canonicalize us features through the taxonomy → exact membership (a blank feature is skipped,
        # so it can't mark every cell HAS and silently empty the MATCH list).
        # THE SAME predicate `align_features` used — via the one helper, so the two cannot drift.
        # `build_matrix` is pure and has no meter, so it reports nothing; `align_features` already did.
        _us_taken = _us_features(us)
        # ⚠️ RECORDED, NOT DETECTED (C8): a consumer that calls `align_features` with one `us` and
        # `build_matrix` with a DIFFERENT one gets a fully-satisfied `trust_us` over a taxonomy built
        # for someone else's feature list — a confident ❌ on a feature it ships. The analogous
        # `build_matrix`/`gap_synthesis` disagreement IS caught (via `matrix.has_us`), but catching this
        # one needs the taxonomy to carry the `us` names it saw, i.e. another public field on a
        # deserializable dataclass. Reachable only by calling the pair directly with mismatched
        # arguments — `run()` passes the same object to both — so it is documented here rather than
        # paid for. ⚠️ C9, same paragraph: a `Collection` that grows during iteration makes `list()`
        # hang. `_read_features` keeps the never-raise contract but not liveness; there is no timeout
        # on a pure stage, and the money is already spent when it runs.
        # same guard as the rival side above — a mapping whose value for OUR name is non-str raised
        # `AttributeError` out of this pure stage. Guarding one seam and not its sibling inside ONE
        # function is the shape this file keeps re-learning.
        def _canon_str(name: str) -> str:
            # the us-lane mirror of the rival-lane guard above — same reader, same verdict
            m = taxonomy.canon(name)
            return m if _usable(_stripped(m)) else name

        us_canon = {key_safe(_canon_str(uf)) for uf in _us_taken.kept}
        # ⚠️ TRUST IS A CONJUNCTION, and the taxonomy was only ONE of its terms. A ❌ says "we looked at
        # our own feature list and this is not in it" — a claim that requires the list to have been
        # READ. Two ways it was not, both of which used to yield a confident ❌ anyway:
        #   * the container was REFUSED outright (a one-shot iterator) → `kept=[] n_malformed=0`,
        #     indistinguishable from genuinely shipping nothing;
        #   * some ELEMENTS were dropped (a non-str in the list) → `n_malformed > 0`, so the dossier
        #     hears about it, but the CELL still claimed certainty it did not have.
        # Same remedy as the degraded taxonomy, for the same reason: unknown is the honest cell.
        # ⚠️ REJECTED CANDIDATE, recorded so it is not re-proposed: "our canonical is absent from
        # `rows` ⇒ untrustworthy" (`us_canon - set(rows)`). It was offered as cheap and non-widening.
        # It is neither — this change's own arm-2 regression test disproved it in one run. A feature WE
        # have that NO rival mentions is also absent from `rows`, which is the ordinary healthy case, so
        # the rule ❓-s every genuine gap: `Us(features=("billing",))` against a rival shipping
        # end-to-end encryption went `❌ → ❓` and the true gap vanished. The A4 scenario (the LLM maps
        # our name but omits its canonical from the `canonical` list) is structurally IDENTICAL to that
        # healthy case from here — the two differ only by whether the two names MEAN the same thing,
        # which is the irreducible semantic residual documented in README § Gotchas. Not detectable by a
        # mapping-shape property, current or proposed.
        trust_us = (
            not taxonomy.degraded
            and not taxonomy.us_unmapped
            and _us_taken.n_malformed == 0
            and not _us_unusable(_us_source(us))
        )
        # ⚠️ NOT-IN-`us_canon` MEANS TWO DIFFERENT THINGS, and only one of them is a gap.
        # With a real taxonomy, synonyms are merged, so a row we do not hold is a genuine ❌ MISSING.
        # With the IDENTITY fallback (`taxonomy.degraded` — the budget was exhausted before synthesis, or
        # the LLM failed) nothing was clustered: our "E2E encryption" and a rival's "end-to-end encryption"
        # stay separate rows, and the rival's row resolves to MISSING for us. That publishes a ❌ about our
        # OWN product on a feature we ship — exactly the failure `_us_features` was written to end, arriving
        # through a second door: not two predicates drifting, but one predicate fed a taxonomy that could
        # not do its job. Unknown is the honest cell, and it is the same rule the rivals already get
        # ("never mentioned is unverified, not missing" — this docstring).
        for canon in rows:
            if canon in us_canon:
                state = HAS
            else:
                # per-ROW: this canonical never merged with anything, so we cannot say we lack it
                # `taxonomy.unmapped` is a field this change ADDED to a public, deserializable
                # dataclass, and `x not in <non-iterable>` raises — the same premise used to justify
                # guarding `FeatureSet.competitor`, applied to my own new field.
                _unmapped = (
                    taxonomy.unmapped
                    if isinstance(taxonomy.unmapped, (set, frozenset, list, tuple))
                    else ()
                )
                state = MISSING if (trust_us and canon not in _unmapped) else UNKNOWN
            cells[(canon, _US_COLUMN)] = MatrixCell(state=state)
    return Matrix(columns=columns, rows=rows, cells=cells, has_us=has_us)


_STATE_RANK = {UNKNOWN: 0, MISSING: 1, PARTIAL: 2, HAS: 3}


def _uniquify(names: Iterable[str], *, reserved: Iterable[str] = ()) -> list[str]:
    """De-duplicate a name list by SUFFIXING repeats — never by dropping them.

    Use this ONLY where each position keeps its own identity downstream (the matrix COLUMNS, which are
    zipped 1:1 with ``rivals`` so a suffixed column still keys its own cells). ``reserved`` pre-claims
    names that must not be taken — the ``"us"`` column is appended later and would otherwise collide with
    a rival literally named ``us``, converting that rival's ✅ into our ❌ and dropping its column.

    ⚠️ NOT for the matrix ROWS. A row's cells are keyed by ``key_safe(taxonomy.canon(name))``, which has no
    notion of "the second one" — so suffixing a row produced a PHANTOM row that nothing could ever
    populate, while both real features merged into the first. Rows are de-duplicated instead (see
    :func:`build_matrix`): two canonicals that sanitize to one string are genuinely indistinguishable
    downstream, and the honest rendering of that is one row, not two.
    """
    used: set[str] = set(reserved)
    out: list[str] = []
    for name in names:
        if name not in used:
            used.add(name)
            out.append(name)
            continue
        # The suffix must not collide with a REAL name. Naively appending `(n)` reintroduced the exact
        # duplicate this function removes: `["A", "A", "A (2)"]` produced `["A", "A (2)", "A (2)"]`,
        # because a rival can legitimately be called "A (2)". Advance until the candidate is genuinely
        # unused — and track EVERY emitted name, not just the originals.
        n = 2
        while f"{name} ({n})" in used:
            n += 1
        candidate = f"{name} ({n})"
        used.add(candidate)
        out.append(candidate)
    return out


def _stronger(a: Any, b: Any) -> Any:
    # `_rank`, not `_STATE_RANK.get` — a consumer's `Feature.state` is a HINT and `dict.get` raises on
    # an unhashable one. Guarding the attribute READ moved the raise here; see `_rank`.
    return a if _rank(a) >= _rank(b) else b


# ── gap synthesis: MATCH + BEAT ───────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class MatchItem:
    feature: str
    rivals_having: list[str]
    universal: bool  # ★ ALL rivals have it (highest-leverage table-stakes gap)


@dataclass(frozen=True)
class BeatItem:
    theme: str
    weight: float  # source-weighted, corroboration-gated ranking score
    source_urls: list[str]
    quotes: list[str]
    #: How many attributed quotes the ``[:5]`` bound discarded — 0 when nothing was cut.
    #: **A bound must publish its residual.** Without this, `quotes` silently caps at 5 and the
    #: markdown's "(+N more quotes in `to_dict()`)" points at a payload that never held them either,
    #: so the evidence is gone from BOTH channels with nothing saying so. `Dossier.to_markdown`'s
    #: three other bounds already publish theirs; these two did not.
    #: Defaulted so existing 4-positional construction keeps working — see README § Gotchas.
    quotes_omitted: int = 0


def _gap_synthesis_inner(
    matrix: Matrix,
    review_signal: Sequence[Signal],
    us: Us | None,
    *,
    subject_domains: Mapping[str, str | Collection[str]] | None = None,
    on_collapse: Callable[[str, int], None] | None = None,
) -> tuple[list[MatchItem], list[BeatItem]]:
    """MATCH: features rivals have that ``us`` lacks (or, ``us``-absent, the category table-stakes most
    rivals share) — flagged ``universal`` when ALL rivals have it. BEAT: rivals' negative-review themes,
    **cross-source-corroborated** and ranked by **source-weighted** frequency — the source-weight discounts
    a self-published source (``subject_domains[competitor]``) and the fake-polluted extreme-rating band
    (``Signal.rating``), trusting the independent 2–4★ band. Pure — no LLM."""
    # ⚠️ THE THIRD PURE STAGE, given the same accessor treatment as the other two. `Matrix` is a public
    # deserializable dataclass and its four fields are HINTS: `columns=None` / `rows=None` raised
    # `TypeError: 'NoneType' object is not iterable` and a cell whose `.state` raises took the stage
    # with it — all out of a function this module documents as pure and never-raising. The layer was
    # built while fixing the OTHER two stages, so it stopped at their boundary; `Matrix.to_dict`
    # already guards `isinstance(self.cells, dict)` while `Matrix.cell`, which this stage calls, does
    # not. Same file, same dataclass, one seam guarded and its sibling not.
    # ⚠️ COMPUTED ONCE AND USED EVERYWHERE. This guard was written carefully and then the SAME field was
    # read bare twice, 24 lines below — so the guard could not fire and the mutation removing it survived
    # 575/575 with byte-identical output. This module's own rule: "a guard that cannot fire must not
    # claim it does." `bool()` is inside `_truthy_attr` too, because a raising `__bool__` defeats it at
    # its own line.
    _has_us_col = _truthy_attr(matrix, "has_us")
    rival_cols = [c for c in _feature_list(_safe_attr(matrix, "columns", ()))
                  if not (_has_us_col and c == _US_COLUMN)]
    n_rivals = len(rival_cols) or 1

    def _cell_state(feature: Any, column: Any) -> Any:
        try:
            return _safe_attr(matrix.cell(feature, column), "state", UNKNOWN)
        except Exception:  # noqa: BLE001 — an unaddressable cell is UNKNOWN, which is what ❓ means
            return UNKNOWN

    match: list[MatchItem] = []
    for feature in _feature_list(_safe_attr(matrix, "rows", ())):
        having = [c for c in rival_cols if _cell_state(feature, c) == HAS]
        if not having:
            continue
        # ⚠️ `matrix.has_us` AS WELL AS `us`, because the two arguments can disagree and the `== MISSING`
        # predicate below made that disagreement SILENT. `Matrix.cell()` returns a DEFAULT `UNKNOWN` for
        # any key never written, so a `us` paired with a matrix built WITHOUT one yields ❓ for every row:
        # the old `!= HAS` then published every rival feature as a gap (loudly wrong), and `== MISSING`
        # alone would publish NONE (silently wrong, which is worse). A matrix with no us column cannot
        # support an us-vs-them verdict at all, so take the greenfield branch — the analysis the data
        # actually supports. `run()` always passes the same `us` to both, so this is unreachable from the
        # entrypoint; it is reachable from a consumer calling the pair directly.
        if us is not None and not _has_us_col:
            # The caller passed an `us` the MATRIX cannot support. Falling back is right, but doing it
            # SILENTLY is not: `match_list` changes meaning from "rivals have it and we demonstrably
            # lack it" to "most rivals share it", and `MatchItem` carries no field distinguishing the
            # two. (The rendered header — "MATCH — table-stakes rivals have" — is honest for BOTH, so
            # this is a programmatic-consumer hazard, not a rendering one.)
            logger.warning(
                "competitor_intel.us_without_us_column — `us` was given but the matrix has no `us` "
                "column; falling back to the greenfield table-stakes analysis, so MATCH means "
                "'most rivals share this', NOT 'you lack this'"
            )
        if us is not None and _has_us_col:
            # MATCH = a feature rivals have but WE demonstrably lack.
            # ⚠️ `== MISSING`, NOT `!= HAS`. Those were equivalent while the us column could only ever be
            # ✅ or ❌; the degraded-taxonomy fix above introduces ❓, and `!= HAS` would have swept every
            # unknown cell straight back into the MATCH list — re-publishing the same false "you lack this"
            # the cell fix exists to remove, one layer down. A gap we cannot verify is not a gap.
            # `_US_COLUMN`, not the literal: `Matrix.cell` returns a DEFAULT `UNKNOWN` for a key it
            # does not hold, so if the constant were ever retuned a literal here would silently read
            # that default, `== MISSING` would be False, and MATCH would empty with nothing raising.
            if _cell_state(feature, _US_COLUMN) == MISSING:
                match.append(
                    MatchItem(
                        feature=feature,
                        rivals_having=having,
                        universal=len(having) == n_rivals,
                    )
                )
        else:
            # greenfield: category table-stakes = a feature the MAJORITY of rivals share
            if len(having) * 2 >= n_rivals:
                match.append(
                    MatchItem(
                        feature=feature,
                        rivals_having=having,
                        universal=len(having) == n_rivals,
                    )
                )
    # universal gaps first (highest leverage), then by breadth
    match.sort(key=lambda m: (not m.universal, -len(m.rivals_having)))

    # BEAT: group negative signals by aspect (the theme), corroboration-gate, source-weight rank.
    by_theme: dict[str, list[Signal]] = {}
    for s in _feature_list(review_signal):   # `review_signal=None` raised straight out of this stage
        # ⚠️ `.strip().lower()`, matching `orchestrator._signal_key` EXACTLY. The key normalizes with
        # `.strip()`, so `"negative "` and `"negative"` merge into one entry there — and if the survivor
        # kept the stray whitespace, a bare `.lower()` here FILTERED IT OUT, dropping the corroborating
        # source and collapsing the whole BEAT theme below `min_sources=2`. `partial=False`, no cause.
        # A dedupe key and the filter it feeds must normalize identically or the merge silently deletes
        # evidence; matching the field name is not enough (see the key's docstring).
        # `_norm`, not a bare `(x or "").strip().lower()` — see `_norm`. The normalisation is
        # byte-identical to `orchestrator._signal_key`'s, which is the property this comment protects.
        if _norm(_safe_attr(s, "sentiment", "")) != "negative":
            continue
        aspect = _norm(_safe_attr(s, "aspect", ""))
        if not aspect:
            continue  # no aspect → no coherent theme; don't collapse unrelated complaints into "general"
        by_theme.setdefault(aspect, []).append(s)
    beat: list[BeatItem] = []
    for theme, sigs in by_theme.items():
        # normalize the url ONCE (stripped) so every rail — corroboration, weight, source_urls, quotes —
        # counts the SAME set. A whitespace-only url is not attribution (matches corroborated()'s strip).
        # ⚠️ `_usable`, NOT `or ""`. `_UNSTRIPPABLE` is a bare `object()` and therefore TRUTHY, so
        # `or ""` keeps it exactly as `is not None` would — the identical defect, for the third time,
        # at the ONE `_stripped` call site of eight that used neither `_usable` nor an identity test.
        # The sentinel then flowed into `corroborated()`, `source_weight()` and `sorted(set(urls))` and
        # died on `'object' object has no attribute 'strip'`. `_usable` exists precisely so that
        # "did this produce a name we may use?" has ONE answer; asking it any other way is the bug.
        entries = [(s, _usable_str(_stripped(_safe_attr(s, "source_url", "")))) for s in sigs]
        urls = [u for _, u in entries if u]
        if not corroborated(urls, min_sources=2):
            # ── THE AGGREGATION CLIFF ──────────────────────────────────────────────────────────────
            # A per-element loss is not proportional here. A theme survives iff >=2 elements survive
            # WITH DISTINCT non-blank urls, so dropping 2 of 8 costs a quarter of the evidence and
            # dropping 2 of 3 costs the ENTIRE theme. No per-element threshold can be right, which is
            # why this reports once per COLLAPSED GROUP at the gate rather than per dropped element.
            #
            # ⚠️ Reported ONLY when the group could have qualified. A theme with one voice was never a
            # BEAT finding — that is a business rule doing its job, and flagging it would rebuild the
            # permanent-false-alarm shape the whole seam exists to prevent. The collapse is worth
            # reporting only when there were ENOUGH signals and they lost their ATTRIBUTION.
            # ⚠️ MY FIRST CONDITION WAS `len(sigs) >= 2 and len(set(urls)) < 2`, and it fired on a
            # HEALTHY fixture: two quotes from the SAME review page are one voice, which is exactly
            # what the corroboration rule is for. Nothing had been dropped. That is the
            # false-alarm-on-routine-data shape that killed the seam's first design, rebuilt here in
            # the one phase that exists to handle aggregation carefully.
            # The real signal is LOST ATTRIBUTION: entries that carried no url at all, without which
            # the group WOULD have qualified. Same source twice reports nothing.
            unattributed = len(entries) - len(urls)
            if (
                on_collapse is not None
                and unattributed > 0
                and len(set(urls)) + unattributed >= 2
            ):
                on_collapse(theme, len(sigs))
            continue  # one voice is not a BEAT finding
        # rating + self-published domain feed the weighting so the extreme-band / vendor discounts actually
        # fire (a rating-bearing source e.g. Apple; a Tier-C signal has rating=None → url-marker weighting).
        # ⚠️ A TYPE check, not `or {}` — the rule `_feature_list`'s docstring states 400 lines above
        # ("A TYPE check, not `or []`") and this sibling did not follow. `or {}` guards FALSY, not
        # wrong-typed: a list or a str survived it and `.get` then raised `AttributeError` straight out
        # of a pure function this module documents as never-raising, after the legs were already billed.
        doms = subject_domains if isinstance(subject_domains, Mapping) else {}
        weight = sum(
            source_weight(
                # ⚠️ `.rating` and `.competitor` are `Signal` fields too. The round that gave this stage
                # the accessor layer reached `sentiment`, `aspect` and `source_url` and stopped — three
                # of six, in one dataclass, in one function. `doms` is consumer-supplied as well, so its
                # `.get` goes through the same floor as `mapping.get` one file over.
                u,
                rating=_number_or_none(_safe_attr(s, "rating", None)),
                subject_domain=_safe_dget(doms, _stripped(_safe_attr(s, "competitor", "")))
            )
            for s, u in entries
            if u
        )
        # only ATTRIBUTED quotes (a real, non-blank url) — the trust-rail promise that every
        # rendered claim carries its source.
        # ⚠️ `isinstance(q, str)` BEFORE the truthiness test — guarding the READ and then writing `if q`
        # invokes the consumer's `__bool__` at this line, which is the same one-step-outside shape three
        # rounds have now found. And a non-str quote is REJECTED, not coerced: a quote is rendered
        # VERBATIM into the brief as the evidence for a competitive claim, so `str()`-ing a dict here
        # would fabricate the very thing the trust rail exists to guarantee.
        attributed = [
            q for q in (_safe_attr(s, "quote", "") for s, u in entries if u)
            if isinstance(q, str) and q
        ]
        beat.append(
            BeatItem(
                theme=theme,
                weight=round(weight, 4),
                source_urls=sorted(set(urls)),
                quotes=attributed[:5],
                quotes_omitted=max(0, len(attributed) - 5),
            )
        )
    beat.sort(key=lambda b: -b.weight)
    return match, beat


# ── the stage boundary: the never-raise contract, made TRUE BY CONSTRUCTION ───────────────────────────
# ⚠️ WHY A BOUNDARY AND NOT MORE GUARDS. Five review rounds hardened these stages read-by-read, and each
# round the next one found a hole one step away — the container, then the element, then the element's
# siblings, then the attribute read that produced the value, then the accessor's own edge. The reason is
# arithmetic, not carelessness: `synth.py` alone contains WELL OVER A HUNDRED sites that implicitly
# invoke a dunder — comparisons, subscripts, `isinstance`, `len()`, `in` — and EVERY one of
# `__eq__` `__bool__` `__hash__` `__class__` `__len__` `__iter__` `__contains__` `__getitem__` is
# overridable and may raise. A contract of the form "this function never raises for any consumer object"
# cannot be established by enumerating call sites; there is always another dunder. Findings per round
# ran 9 → 7 → 10 → 12 → 10 → 10 and did not fall.
# ⚠️ NO EXACT COUNT IS STATED, deliberately. The first version of this comment gave one (144, with a
# five-way breakdown) and four of its five numbers were stale within the round, because the file kept
# growing underneath it — the same rot this module has now been burned by four separate times, here in
# the very comment arguing that enumeration does not converge. Re-derive with an AST walk if you want
# the number; the argument does not need it, and a wrong number would undermine it.
#
# So the promise is kept HERE, once, where it can actually be kept. The interior accessors stay and are
# still the right thing: they degrade GRACEFULLY, keeping the rows they could read instead of losing the
# lot. This is the FLOOR beneath them — the difference between "we return less" and "the caller's run
# dies after the money is spent".
#
# ⚠️ IT MUST NOT HIDE OUR OWN BUGS, and two things stop it. The exception CLASS NAME is logged at
# `error` with the stage that produced it (the same channel `_safe_research` uses), so a genuine
# regression is loud rather than silent. And every test drives the INNER function's real path, so an
# internal break shows up as a failing assertion, not as a quietly empty result.
def _stage_failed(stage: str, exc: BaseException) -> None:
    logger.error(
        "competitor_intel.stage_never_raise_floor stage=%s cause=%s — a documented never-raising stage "
        "was about to raise; returning a DEGRADED result. This is a floor, not an expected path: if the "
        "cause is not a hostile consumer object, it is a bug in this module.",
        stage,
        type(exc).__name__,
    )


async def align_features(
    rivals: Sequence[FeatureSet], us: Us | None, *, meter: LlmMeter
) -> CanonicalTaxonomy:
    """Cluster feature names into a canonical taxonomy. NEVER RAISES — see the stage-boundary note above.

    Degrades to an empty, `degraded=True` taxonomy, which every downstream consumer already treats as
    "nothing was clustered": the `us` column answers ❓ rather than ❌, and `TaxonomyDegraded` reaches
    the dossier. The honest outcome for a taxonomy we could not build.
    """
    try:
        return await _align_features_inner(rivals, us, meter=meter)
    except Exception as exc:  # noqa: BLE001 — the floor; see `_stage_failed`
        _stage_failed("align_features", exc)
        return CanonicalTaxonomy(canonical=[], mapping={}, degraded=True)


def build_matrix(
    taxonomy: CanonicalTaxonomy, rivals: Sequence[FeatureSet], us: Us | None
) -> Matrix:
    """Build the feature matrix. NEVER RAISES — see the stage-boundary note above.

    Degrades to an EMPTY grid that still records whether a `us` column was asked for — it invents no rows
    and claims no comparison. `has_us` is an identity test on the argument, which cannot raise.

    ⚠️ THIS FLOOR IS SILENT, and an earlier version of this docstring claimed otherwise ("so the renderer
    reports 'the feature grid is empty — nothing was measured'"). Measured by forcing the inner stage to
    raise, through `run()`: `rows=[] MATCH=[] partial=False causes=[] status='ok'`, and no section. The
    renderer's empty-grid sentence needs a DISCOVERED RIVAL to fire, and this floor returns
    `columns=[]` — it cannot safely read the `rivals` argument, since that argument is what raised.
    Carrying the degradation out of here needs a channel the return type does not have; recorded as a
    residual in README § Gotchas rather than papered over. The floor still does its job: the caller gets
    a valid, empty, non-fabricated grid instead of an exception after the money is spent.
    """
    try:
        return _build_matrix_inner(taxonomy, rivals, us)
    except Exception as exc:  # noqa: BLE001 — the floor; see `_stage_failed`
        _stage_failed("build_matrix", exc)
        return Matrix(columns=[], rows=[], cells={}, has_us=us is not None)


def gap_synthesis(
    matrix: Matrix,
    review_signal: Sequence[Signal],
    us: Us | None,
    *,
    subject_domains: Mapping[str, str | Collection[str]] | None = None,
    on_collapse: Callable[[str, int], None] | None = None,
) -> tuple[list[MatchItem], list[BeatItem]]:
    """MATCH + BEAT. NEVER RAISES — see the stage-boundary note above.

    Degrades to `([], [])`.

    ⚠️ AN EMPTY MATCH IS NOT SELF-EVIDENTLY "NO GAPS" — that conflation is the defect this whole change
    exists to end — and THIS FLOOR CANNOT SAY SO. An earlier version of this docstring claimed the run
    would be `partial` with a cause and the brief would render "MATCH — not computed". Measured by
    forcing the inner stage to raise, through `run()`: `MATCH=[] partial=False causes=[] status='ok'`,
    no section, no banner. `([], [])` carries no channel for the degradation, and giving it one is a
    public-shape change. Recorded as a residual in README § Gotchas. It remains the right floor — an
    exception here loses the whole dossier after every leg is billed — but it is a SILENT one, and the
    honest place to say that is here rather than in a claim the code does not keep.
    """
    try:
        return _gap_synthesis_inner(
            matrix, review_signal, us,
            subject_domains=subject_domains, on_collapse=on_collapse,
        )
    except Exception as exc:  # noqa: BLE001 — the floor; see `_stage_failed`
        _stage_failed("gap_synthesis", exc)
        return ([], [])
