"""The two OPTIONAL, toggleable stages — price-wedge and white-space — that make the dossier a first-class
PRE-spec input. Both are budget-gated (via :class:`~competitor_intel.synth.LlmMeter`) and never-raising;
the orchestrator runs the metered research legs and hands the fetched source text here for synthesis.

- **price-wedge:** per-rival pricing model (quote-grounded) → the ranked opening in the category's pricing
  shape. Heuristic wedge over the extracted models (deterministic, so it is testable + explainable).
- **white-space:** demand-side unmet needs, **cross-source-corroborated** (one wish is not a market need),
  kept DISTINCT from BEAT (a rival's weakness) and MATCH (a feature we lack). Incumbent/discourse-anchored.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import operator
from dataclasses import dataclass, field
from typing import Any, Final

from .synth import LlmMeter, _parse_json
from .trust import CONSTRAIN_TO_SOURCES, UNVERIFIED, corroborated, grounded_source, source_weight

# pricing model vocabulary (generic — a consumer's rivals map onto these)
_MODELS = ("freemium", "usage-based", "seat-based", "flat", "tiered", "enterprise-only")


#: Upper magnitude for a number this module will serialize. Mirrors `dossier._MAX_RENDERED_NUMBER`;
#: beyond it a value is not a plausible count or weight, and Python 3.11+ caps int->str at
#: ``sys.get_int_max_str_digits()`` (4300) so rendering a big enough int RAISES rather than printing.
_MAX_SCALAR_NUMBER: Final = 10**12

#: What a number that cannot be serialized honestly becomes — never ``0``, which would be a false
#: claim in place of an absent one.
#:
#: ⚠️ THIS MUST EQUAL ``dossier._UNRENDERABLE_NUMBER``, and round 16 shipped it as ``"\u2753"`` (❓)
#: instead. Two separate defects in one wrong literal. First, ONE ``Dossier.to_dict()`` payload then
#: carried two different strings for the identical condition — a `beat_list` weight over the bound
#: read ``"n/a"`` while a `white_space` weight over the same bound read ``"❓"`` — so a consumer
#: matching dossier's documented sentinel silently missed every `pricing`/`white_space` field.
#: Second, and worse, ``❓`` is already this module's UNVERIFIED/UNKNOWN glyph (``trust.UNVERIFIED``,
#: aliased ``synth.UNKNOWN``, used for ungrounded pricing claims and unknown matrix cells), so
#: "too big to render" became textually indistinguishable from "the LLM could not ground this".
#: `dossier.py` documents exactly this hazard one line above its own constant — I reused an
#: already-overloaded glyph in the twin while copying the comment that warns against it.
_UNRENDERABLE_NUMBER: Final = "n/a"

def _scalar(value: object) -> Any:
    """A JSON-safe scalar for a type that serializes ITSELF.

    ⚠️ `Dossier.to_dict()` ends in a `_json_safe` walk, and that walk incidentally rescued every
    nested type — which is exactly why the inner gaps looked closed. These types are EXPORTED, so a
    consumer calls `PricingBlock.to_dict()` directly and gets no such sweep: one hostile SCALAR field
    on an otherwise well-formed `PricingModel` made `json.dumps` fail. No dunder trickery needed —
    a `Decimal`, an `object()`, anything JSON has no type for.
    """
    if value is None or type(value) is str or type(value) is bool:
        return value
    # ⚠️ WORSE THAN THE SIBLING SPOOF, because this branch does not merely return the liar — it CALLS
    # `int(value)` on it, which raises `TypeError` from INSIDE the guard, straight out of an exported
    # type's own `to_dict()`. Base-class dunders instead: `int.__int__` converts a REAL int subclass
    # (an `IntEnum`, a numpy int) and raises for anything only claiming to be one, so the honest
    # subclass keeps working and the liar degrades to text.
    # ⚠️ THE TWIN of `dossier._json_number`, and it must stay a twin: `int.__int__` refuses
    # `numpy.int64` (not an `int` subtype), which turned an honest weight into the STRING "3".
    # `operator.index` converts every honest integer and still raises for an object that only
    # CLAIMS `__class__ = int`, because CPython requires `__index__` to return a real `int`.
    # `__float__` is read off the TYPE, never the instance whose `__class__` is the thing lying.
    # The magnitude bound is here for the same reason as in the twin: Python 3.11+ caps int->str at
    # 4300 digits, so an oversized count makes `json.dumps` raise with nothing hostile in sight.
    if not isinstance(value, (str, bytes, bytearray)):
        try:
            as_int = operator.index(value)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 — not an integer; try the float lane
            pass
        else:
            return as_int if abs(as_int) <= _MAX_SCALAR_NUMBER else _UNRENDERABLE_NUMBER
        to_float = getattr(type(value), "__float__", None)
        if to_float is not None:
            try:
                as_float = to_float(value)
            except Exception:  # noqa: BLE001 — a raising __float__ is not a number
                as_float = None
            if type(as_float) is float:
                if as_float != as_float or as_float in (float("inf"), float("-inf")):
                    return str(as_float)
                return as_float if abs(as_float) <= _MAX_SCALAR_NUMBER else _UNRENDERABLE_NUMBER
    try:
        return str(value)
    except Exception:  # noqa: BLE001 — serialization must never raise after the money is spent
        return f"<unrenderable {type(value).__name__}>"


def _strs(value: object) -> list[str]:
    """A consumer-supplied string list, as real strings — never raising, always JSON-safe.

    ⚠️ These types serialize THEMSELVES and are exported, so `Dossier`'s `_json_safe` walk does not
    protect a consumer who calls `PricingBlock.to_dict()` directly. `_seq` fixes the CONTAINER; the
    ELEMENTS were still emitted raw, so `json.dumps(block.to_dict())` failed on a set, an object, or
    anything with a hostile `__str__`. Found by testing the exported type's own method rather than
    only the path through `Dossier` — which is what a consumer actually calls.
    """
    out: list[str] = []
    for item in _seq(value):
        # ⚠️ `type(...) is str`, NOT `isinstance`: an object declaring `__class__ = str` passes
        # `isinstance` and is not a str, so it was appended RAW and `json.dumps` failed one layer
        # later. Same hole `_text` was fixed for in `dossier.py`; the twin here kept it.
        if type(item) is str:
            out.append(item)
            continue
        try:
            out.append(str(item))
        except Exception:  # noqa: BLE001 — serialization must never raise after the money is spent
            out.append(f"<unrenderable {type(item).__name__}>")
    return out


def _has(obj: object, attr: str) -> bool:
    """`hasattr` that cannot raise — the twin of `dossier._has`; see it for why `hasattr` alone is not
    a guard (it swallows only `AttributeError`, so a raising `__getattr__`/property goes through)."""
    try:
        return hasattr(obj, attr)
    except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
        return False


def _seq(value: object) -> list[Any]:
    """A consumer-supplied "list" field, as a real list — or empty. Never a raise.

    ⚠️ The twin of `dossier._seq`, and it exists because the sweep there was not enough: these
    dataclasses serialize THEMSELVES, so `PricingBlock.to_dict()` and `WhiteSpaceBlock.to_dict()`
    iterate their own fields and crashed on a wrong-typed container even after every call site in
    `dossier.py` was guarded. Both types are exported and consumer-constructible; a `to_dict()` that
    raises breaks the machine-readable channel after the money is already spent.
    """
    # ⚠️ RE-ITERABLE containers only, and the exclusions are each for a different reason.
    # `list`/`tuple` were the original accept-set, and it silently rendered NOTHING for a `set`, a
    # `frozenset` or a `range` — legitimate containers a consumer can hold a `list[str]`-annotated
    # field in. Dropping them is data loss, which is the exact class this module exists to prevent, so
    # they are accepted now.
    # `str`/`bytes` stay refused: they are iterable, and accepting them explodes a name into
    # CHARACTERS — the same str-is-a-sequence trap `trust.source_weight` had to be fixed for.
    # ⚠️ A GENERATOR OR ITERATOR IS ALSO REFUSED, and that is deliberate rather than an oversight.
    # These guards are called MORE THAN ONCE on the same field (a truthiness gate, then the loop that
    # renders it), so consuming a one-shot iterator in the gate would leave the render empty — a
    # guard that destroys the data it was added to protect. Refusing is honest; half-rendering is not.
    # ⚠️ REDUNDANT TODAY, KEPT DELIBERATELY — a mutation sweep proved it so rather than my assuming
    # it. Deleting this branch kills no test, because the POSITIVE accept-list below already excludes
    # `str`/`bytes`. It stays because the day someone widens that list to `Iterable` — which is the
    # natural next edit, and would be correct-looking — this line is the only thing standing between a
    # rival name and being rendered one character per entry.
    if isinstance(value, (str, bytes)):
        return []
    # ⚠️ `list(value)` IS ITSELF A CALL INTO THE CONSUMER'S TYPE. CPython pre-sizes the result from
    # `__len__`, so a real `list` SUBCLASS with a raising `__len__` raised from INSIDE this guard —
    # the helper written to make the render never raise was the thing raising. It passes every check
    # above honestly: it IS a list. Nothing about the element types was ever the problem.
    # So the materialization is itself guarded, and a partial read keeps what it got: losing the tail
    # of a hostile container beats losing the whole render.
    if isinstance(value, (list, tuple, set, frozenset, range)):
        try:
            return list(value)
        except Exception:  # noqa: BLE001 — the render must never raise after the money is spent
            out: list[Any] = []
            try:
                for item in value:
                    out.append(item)
            except Exception:  # noqa: BLE001 — keep the prefix we successfully read
                pass
            return out
    return []


@dataclass(frozen=True)
class PricingModel:
    competitor: str
    model: str  # one of _MODELS, or "❓"
    free_tier: str  # "yes" | "no" | "❓"
    evidence: str
    source_url: str


@dataclass
class PricingBlock:
    models: list[PricingModel] = field(default_factory=list)
    wedge: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "models": [
                {
                    "competitor": _scalar(m.competitor),
                    "model": _scalar(m.model),
                    "free_tier": _scalar(m.free_tier),
                    "evidence": _scalar(m.evidence),
                    "source_url": _scalar(m.source_url),
                }
                for m in _seq(self.models) if all(_has(m, x) for x in ("competitor","model","free_tier","evidence","source_url"))
            ],
            "wedge": _strs(self.wedge),
        }


async def price_wedge(
    rival_sources: Mapping[str, Sequence[tuple[str, str]]], *, meter: LlmMeter
) -> PricingBlock:
    """Extract each rival's pricing model (quote-grounded against THAT rival's own ``(text, url)`` sources —
    fail-closed: a quote not in the named rival's sources → ``❓``, never grounded against another rival's
    text) then derive the ranked pricing WEDGE. ``source_url`` is the real url the quote was found in.
    Degrades to an empty block when the budget is exhausted or the LLM fails."""
    all_pairs = [p for pairs in rival_sources.values() for p in pairs]
    if not all_pairs:
        return PricingBlock()
    labeled = "\n".join(
        f"[{name}]\n" + "\n".join(t for t, _ in pairs) for name, pairs in rival_sources.items()
    )
    prompt = (
        f"{CONSTRAIN_TO_SOURCES}\n\nFrom the sources (grouped by competitor), extract each competitor's "
        f"pricing. Output ONLY a JSON array, each "
        f'{{"competitor": .., "model": "freemium|usage-based|seat-based|flat|tiered|enterprise-only", '
        f'"free_tier": "yes|no", "evidence": "<verbatim quote>"}}.\n\nSOURCES:\n{labeled}'
    )
    parsed = _parse_json(await meter.call(prompt))
    models: list[PricingModel] = []
    if isinstance(parsed, list):
        for item in parsed:
            if not isinstance(item, dict) or not str(item.get("competitor") or "").strip():
                continue
            competitor = str(item["competitor"]).strip()
            evidence = str(item.get("evidence") or "")
            url = grounded_source(evidence, rival_sources.get(competitor, []))  # fail-closed to this rival
            grounded = url is not None
            model = str(item.get("model") or "").lower().strip()
            models.append(
                PricingModel(
                    competitor=competitor,
                    model=model if (grounded and model in _MODELS) else UNVERIFIED,
                    free_tier=str(item.get("free_tier") or UNVERIFIED).lower().strip() if grounded else UNVERIFIED,
                    evidence=evidence if grounded else "",
                    source_url=url or "",
                )
            )
    return PricingBlock(models=models, wedge=_derive_wedge(models))


def _derive_wedge(models: Sequence[PricingModel]) -> list[str]:
    """Deterministic wedge heuristic from the extracted models: pricing shapes NO rival occupies + a
    free-tier gap. Explainable + testable; the consumer can refine with their own judgment."""
    present = {m.model for m in models if m.model in _MODELS}
    wedge: list[str] = []
    if models and all(m.free_tier == "no" for m in models if m.free_tier in ("yes", "no")):
        if any(m.free_tier == "no" for m in models):
            wedge.append("No rival offers a free/self-serve tier → a free entry tier is open.")
    for shape in ("usage-based", "freemium", "flat"):
        if present and shape not in present:
            wedge.append(f"No rival uses a {shape} model → a {shape} offering is an open pricing wedge.")
    return wedge


@dataclass(frozen=True)
class UnmetNeed:
    need: str
    weight: float
    source_urls: list[str]
    quotes: list[str]
    #: How many grounded quotes the ``[:5]`` bound discarded — 0 when nothing was cut.
    #: The sibling of ``BeatItem.quotes_omitted``; a bound must publish its residual, or the evidence
    #: vanishes from the machine-readable ``to_dict()`` as well as the rendered brief.
    #: Defaulted so existing 4-positional construction keeps working — see README § Gotchas.
    quotes_omitted: int = 0


@dataclass
class WhiteSpaceBlock:
    needs: list[UnmetNeed] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "needs": [
                {
                    "need": _scalar(n.need),
                    "weight": _scalar(n.weight),
                    "source_urls": _strs(n.source_urls),
                    "quotes": _strs(n.quotes),
                    "quotes_omitted": _scalar(n.quotes_omitted),
                }
                for n in _seq(self.needs) if all(_has(n, x) for x in ("need","weight","source_urls","quotes","quotes_omitted"))
            ]
        }


async def white_space(sources: Sequence[tuple[str, str]], *, meter: LlmMeter) -> WhiteSpaceBlock:
    """Mine demand-side unmet needs ('I wish X existed', 'switched away because no tool does Y') from the
    demand ``(text, url)`` sources, cross-source-corroborated (≥2 distinct REAL urls) and source-weight-
    ranked. Each need's provenance is the actual url the quote was found in (via ``grounded_source``) — NOT
    a url the LLM emits, so corroboration cannot be satisfied by fabricated provenance. Distinct from
    BEAT/MATCH; incumbent/discourse-anchored. Degrades to empty when the budget is exhausted or LLM fails."""
    if not sources:
        return WhiteSpaceBlock()
    prompt = (
        f"{CONSTRAIN_TO_SOURCES}\n\nFind DEMAND-SIDE unmet needs — things users wish existed or switched "
        f"away for — that NO current product serves. Output ONLY a JSON array, each "
        f'{{"need": .., "evidence": "<verbatim quote copied exactly from a source>"}}.\n\nSOURCES:\n'
        + "\n---\n".join(t for t, _ in sources)
    )
    parsed = _parse_json(await meter.call(prompt))
    if not isinstance(parsed, list):
        return WhiteSpaceBlock()
    # group by normalized need; attach the REAL grounding url; corroboration-gate; source-weight rank
    grouped: dict[str, list[dict[str, str]]] = {}
    #: per-need count of entries whose evidence could not be grounded, so the gate below can tell a
    #: group that COLLAPSED from one that simply never had a second voice.
    lost_attribution: dict[str, int] = {}
    for item in parsed:
        if not isinstance(item, dict):
            continue
        need = str(item.get("need") or "").strip()
        evidence = str(item.get("evidence") or "")
        url = grounded_source(evidence, sources)  # the REAL source url, or None if ungrounded
        if not need:
            continue
        if url is None:
            # ⚠️ COUNTED PER NEED, not merely skipped. The entry is discarded here — BEFORE grouping —
            # so without this the group at the corroboration gate below cannot tell it ever lost
            # anything, and the aggregation-cliff report is structurally unreachable on this lane.
            # Measured: an ungrounded second voice collapsed the need with `drops == {}`.
            lost_attribution[need.lower()] = lost_attribution.get(need.lower(), 0) + 1
            continue
        grouped.setdefault(need.lower(), []).append({"need": need, "quote": evidence, "url": url})
    needs: list[UnmetNeed] = []
    for need_key, entries in grouped.items():
        urls = [e["url"] for e in entries if e["url"]]
        if not corroborated(urls, min_sources=2):
            # THE AGGREGATION CLIFF, white-space's half — same reasoning as `gap_synthesis`' gate:
            # reported once per COLLAPSED GROUP, and only when the group had enough entries to qualify
            # and lost their attribution. A single wish was never a market need.
            # the same narrowing as `gap_synthesis`' gate: report LOST ATTRIBUTION, not a group that
            # simply never had two distinct voices — see that gate for the false alarm this avoids.
            unattributed = (len(entries) - len(urls)) + lost_attribution.get(need_key, 0)
            if unattributed > 0 and len(set(urls)) + unattributed >= 2:
                meter.note_drops("white_space_collapsed", need_key, len(entries))
            continue  # one wish is not a market need
        grounded_quotes = [e["quote"] for e in entries if e["quote"]]
        needs.append(
            UnmetNeed(
                need=entries[0]["need"],
                weight=round(sum(source_weight(u) for u in set(urls)), 4),
                source_urls=sorted(set(urls)),
                quotes=grounded_quotes[:5],
                quotes_omitted=max(0, len(grounded_quotes) - 5),
            )
        )
    # a need whose entries were ALL ungrounded never enters `grouped`, so it never reaches the gate.
    # It still collapsed, and for the same reason — report it here or it is silent by construction.
    for need_key, n_lost in lost_attribution.items():
        if need_key not in grouped and n_lost >= 2:
            meter.note_drops("white_space_collapsed", need_key, n_lost)
    needs.sort(key=lambda n: -n.weight)
    return WhiteSpaceBlock(needs=needs)
