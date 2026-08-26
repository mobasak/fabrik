"""The output shapes — :class:`Signal` (a tier-tagged review/demand signal) and :class:`Dossier` (the
returned match-then-beat document).

Both are defined here in Phase A so ``Signal`` exists before its Phase-A consumer (the reviews stage) and
its Phase-C producers (the adapters import it). Phase B EXTENDS ``Dossier`` (feature matrix, MATCH/BEAT
lists, optional pricing/white-space blocks + ``to_markdown``); the Phase-A skeleton stays valid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:  # annotations only — avoids the runtime cycle (synth/stages import dossier)
    from .stages import PricingBlock, WhiteSpaceBlock
    from .synth import BeatItem, MatchItem, Matrix

@dataclass(frozen=True)
class Us:
    """*Our* product, as the caller describes it — a shipped feature list, a hypothesis, or the category
    to enter. OPTIONAL at the entrypoint: absent (``us=None``) is the greenfield / run-before-``/fabrik-spec``
    mode (category-landscape matrix + category-table-stakes MATCH, Phase B). ``category`` seeds competitor
    discovery; ``features`` seed the us-vs-them alignment."""

    name: str = ""
    category: str = ""
    features: tuple[str, ...] = ()
    positioning: str = ""


#: The provenance tier of a signal — the reliability/legal posture of the source that produced it.
#: ``A`` official/clean feed (Apple RSS, HN Algolia) · ``B`` grey scraper (opt-in, health-gated) ·
#: ``C`` search-excerpt (the ToS-clean default the core ships). Every emitted signal carries its tier so
#: the consumer knows how much to trust it.
Tier = Literal["A", "B", "C"]


@dataclass(frozen=True)
class Signal:
    """One review/demand signal about a competitor: an aspect + sentiment + the verbatim quote that
    grounds it + the source URL + the tier that produced it. ``competitor`` names which rival it is about
    (empty for a category-wide demand signal)."""

    competitor: str
    aspect: str
    sentiment: str  # 'positive' | 'negative' | 'neutral' | 'mixed'
    quote: str
    source_url: str
    tier: Tier
    rating: float | None = None  # a star rating when the source carries one (Apple RSS) — feeds source_weight

    def to_dict(self) -> dict[str, Any]:
        return {
            "competitor": self.competitor,
            "aspect": self.aspect,
            "sentiment": self.sentiment,
            "quote": self.quote,
            "source_url": self.source_url,
            "tier": self.tier,
            "rating": self.rating,
        }


@dataclass
class Dossier:
    """The match-then-beat dossier (Phase-A skeleton). ``competitors`` are the discovered rival cards
    (deep-research's closed card shape); ``review_signal`` is the mined per-competitor signal. ``partial``
    flags any degraded sub-call; ``truncated`` flags money-ceiling exhaustion (whatever completed is
    returned — never overspent, never raised). Phase B folds in the feature matrix + MATCH/BEAT + optional
    blocks."""

    market: str
    product_type: str
    competitors: list[dict[str, Any]] = field(default_factory=list)
    review_signal: list[Signal] = field(default_factory=list)
    # Phase B — the synthesis tail (None/empty until synthesis runs)
    feature_matrix: Matrix | None = None
    match_list: list[MatchItem] = field(default_factory=list)
    beat_list: list[BeatItem] = field(default_factory=list)
    pricing: PricingBlock | None = None  # optional price-wedge stage
    white_space: WhiteSpaceBlock | None = None  # optional white-space stage
    truncated: bool = False
    partial: bool = False
    spend_usd: Decimal = Decimal("0")
    status: str = "ok"  # 'ok' | 'partial' | 'empty'

    def to_dict(self) -> dict[str, Any]:
        return {
            "market": self.market,
            "product_type": self.product_type,
            "competitors": self.competitors,
            "review_signal": [s.to_dict() for s in self.review_signal],
            "feature_matrix": self.feature_matrix.to_dict() if self.feature_matrix else None,
            "match_list": [
                {"feature": m.feature, "rivals_having": m.rivals_having, "universal": m.universal}
                for m in self.match_list
            ],
            "beat_list": [
                {"theme": b.theme, "weight": b.weight, "source_urls": b.source_urls, "quotes": b.quotes}
                for b in self.beat_list
            ],
            "pricing": self.pricing.to_dict() if self.pricing else None,
            "white_space": self.white_space.to_dict() if self.white_space else None,
            "truncated": self.truncated,
            "partial": self.partial,
            "spend_usd": str(self.spend_usd),
            "status": self.status,
        }

    def to_markdown(self) -> str:
        """The rendered 'match-then-beat' brief. Every claim carries its quote + source URL (trust rails)."""
        lines: list[str] = [f"# Competitor dossier — {self.market}", ""]
        flags = []
        if self.partial:
            flags.append("partial (some sources degraded)")
        if self.truncated:
            flags.append("truncated (budget ceiling reached)")
        if flags:
            lines.append(f"> ⚠️ {'; '.join(flags)}")
            lines.append("")
        lines.append(f"**Competitors found:** {len(self.competitors)}  ·  **Spend:** ${self.spend_usd}")
        lines.append("")

        if self.match_list:
            lines.append("## MATCH — table-stakes rivals have")
            for m in self.match_list:
                star = " ★ universal gap" if m.universal else ""
                lines.append(f"- **{m.feature}**{star} — {len(m.rivals_having)} rival(s): {', '.join(m.rivals_having)}")
            lines.append("")
        if self.beat_list:
            lines.append("## BEAT — rivals' corroborated weaknesses (your openings)")
            for b in self.beat_list:
                lines.append(f"- **{b.theme}** (weight {b.weight}, {len(b.source_urls)} sources)")
                for q in b.quotes[:2]:
                    lines.append(f"  - \"{q}\"")
            lines.append("")
        if self.pricing and self.pricing.wedge:
            lines.append("## PRICING WEDGE")
            for w in self.pricing.wedge:
                lines.append(f"- {w}")
            lines.append("")
        if self.white_space and self.white_space.needs:
            lines.append("## WHITE SPACE — corroborated unmet demand")
            for n in self.white_space.needs:
                lines.append(f"- **{n.need}** (weight {n.weight}, {len(n.source_urls)} sources)")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
