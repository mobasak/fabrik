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
from dataclasses import dataclass, field
from typing import Any

from .synth import LlmMeter, _parse_json
from .trust import CONSTRAIN_TO_SOURCES, UNVERIFIED, corroborated, grounded_source, source_weight

# pricing model vocabulary (generic — a consumer's rivals map onto these)
_MODELS = ("freemium", "usage-based", "seat-based", "flat", "tiered", "enterprise-only")


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
                    "competitor": m.competitor,
                    "model": m.model,
                    "free_tier": m.free_tier,
                    "evidence": m.evidence,
                    "source_url": m.source_url,
                }
                for m in self.models
            ],
            "wedge": self.wedge,
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


@dataclass
class WhiteSpaceBlock:
    needs: list[UnmetNeed] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "needs": [
                {"need": n.need, "weight": n.weight, "source_urls": n.source_urls, "quotes": n.quotes}
                for n in self.needs
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
    for item in parsed:
        if not isinstance(item, dict):
            continue
        need = str(item.get("need") or "").strip()
        evidence = str(item.get("evidence") or "")
        url = grounded_source(evidence, sources)  # the REAL source url, or None if ungrounded
        if not need or url is None:
            continue
        grouped.setdefault(need.lower(), []).append({"need": need, "quote": evidence, "url": url})
    needs: list[UnmetNeed] = []
    for entries in grouped.values():
        urls = [e["url"] for e in entries if e["url"]]
        if not corroborated(urls, min_sources=2):
            continue  # one wish is not a market need
        needs.append(
            UnmetNeed(
                need=entries[0]["need"],
                weight=round(sum(source_weight(u) for u in set(urls)), 4),
                source_urls=sorted(set(urls)),
                quotes=[e["quote"] for e in entries if e["quote"]][:5],
            )
        )
    needs.sort(key=lambda n: -n.weight)
    return WhiteSpaceBlock(needs=needs)
