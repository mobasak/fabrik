"""The output shapes — :class:`Signal` (a tier-tagged review/demand signal) and :class:`Dossier` (the
returned match-then-beat document).

Both are defined here in Phase A so ``Signal`` exists before its Phase-A consumer (the reviews stage) and
its Phase-C producers (the adapters import it). Phase B EXTENDS ``Dossier`` (feature matrix, MATCH/BEAT
lists, optional pricing/white-space blocks + ``to_markdown``); the Phase-A skeleton stays valid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Final, Literal

if TYPE_CHECKING:  # annotations only — avoids the runtime cycle (synth/stages import dossier)
    from .stages import PricingBlock, WhiteSpaceBlock
    from .synth import BeatItem, MatchItem, Matrix

#: Link schemes `to_markdown` will emit. Everything else — `javascript:`, `data:`, `vbscript:`, `file:` —
#: is rendered as inert text, because a competitor `url` comes from an LLM reading a scraped page and the
#: dossier is routinely pasted into a markdown viewer that turns links into clickable HTML.
_SAFE_URL_SCHEMES: Final = ("https://", "http://")

#: Characters that must never survive into rendered output un-escaped. `|` corrupts a markdown TABLE
#: silently (see the renderer note below); the newline family escapes a bullet and can forge headings.
_LINE_BREAKS: Final = str.maketrans({"\n": " ", "\r": " ", " ": " ", " ": " "})

#: A dangling head-of-entity left by truncation (`&`, `&a`, `&am`, `&amp`, `&l`, `&lt`, …) — i.e. an `&`
#: plus up to a few name chars with no closing `;` at the end of a string.
_PARTIAL_ENTITY: Final = re.compile(r"&[a-zA-Z]{0,5}$")


def _inline(text: str) -> str:
    """Untrusted text for an INLINE position (a bullet, a heading, a quote).

    Collapses the newline family so a field cannot break out of its bullet and forge a section;
    neutralises the backslash+backtick pair so it cannot open a code span that swallows the rest; and
    escapes `[`/`]` so untrusted text cannot construct a LINK or an IMAGE. The image case is the one
    with teeth: a scraped `positioning` of `![](https://tracker.example/p.png)` renders as a tracking
    beacon that fires — revealing the reader's IP and the fact that they are researching this market —
    the moment anyone opens the brief. Links are built by :func:`_link`, never by the text itself.

    Deliberately NOT a full markdown escaper: this is a human brief, and escaping every `*` and `_`
    would make ordinary product copy unreadable for no security gain.
    """
    cleaned = text.translate(_LINE_BREAKS).replace("\\", "＼").replace("`", "'")
    # `<`/`>` BEFORE the bracket escaping: markdown passes raw HTML straight through, so escaping only
    # the `![]()` image form left its strictly more powerful twin untouched — `<img src=https://tracker/…>`
    # fires the same beacon, and `<script>` is stored XSS in any renderer that emits HTML. As entities they
    # stay VISIBLE to the reader (a renderer prints `<script>`) while being inert.
    cleaned = cleaned.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return cleaned.replace("[", "\\[").replace("]", "\\]").strip()


def _cell(text: str) -> str:
    """Untrusted text for a markdown TABLE CELL — `_inline` plus the pipe, which is the load-bearing one.

    A `|` inside a cell ends that cell: the row grows a column, every value after it shifts left, and the
    reader sees a well-formed table containing the WRONG answers. That is strictly worse than a broken
    table, which is why this is escaped rather than stripped.
    """
    return _inline(text).replace("|", "\\|")


def _link(label: str, url: str) -> str:
    """A markdown link, or inert text when the url is absent or its scheme is not http(s).

    Two hazards, both from LLM-derived urls: a `javascript:`/`data:` target becomes a live XSS vector the
    moment the brief is rendered to HTML, and a `)` in the url terminates the markdown link early,
    spilling the remainder into the document as text. Angle-bracket form fixes the second; the scheme
    allowlist fixes the first. ``label`` must already be `_inline`-escaped.
    """
    # `|` percent-encoded in BOTH branches: this helper's output goes into the pricing table's Source
    # cell, so an unescaped pipe in an LLM-derived url corrupts the row exactly as `_cell` exists to
    # prevent — and `_cell` is never applied to a link (it would escape the markdown syntax itself).
    if not url.lower().startswith(_SAFE_URL_SCHEMES):
        return f"{label} (`{_inline(url).replace('|', '%7C')}`)" if url else label
    # BOTH angle brackets percent-encoded: the `<...>` link-destination form is terminated by an
    # unescaped `>` AND is invalid with an unescaped `<`, so encoding only one still lets a crafted url
    # break out of the destination.
    safe = (
        url.translate(_LINE_BREAKS).replace("<", "%3C").replace(">", "%3E").replace("|", "%7C")
    )
    return f"[{label}](<{safe}>)"


def _clip(text: str, limit: int) -> str:
    """Truncate with a VISIBLE marker.

    A silent cut is a correctness problem, not a cosmetic one: an evidence quote clipped mid-sentence can
    invert its meaning (``"does not support bulk export"`` cut early reads as a capability claim), and the
    reader has no way to know text was removed.
    """
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip()
    # Never end on a trailing backslash. `_inline` has already replaced every literal backslash with a
    # fullwidth `＼`, so the only backslashes left are the escapes it emits (`\[`, `\]`) — always single
    # and always followed by a bracket. A trailing one is therefore always an orphan half-escape, which
    # would escape the ellipsis instead of the bracket it was written for.
    cut = cut.removesuffix("\\")
    # …and never end mid-ENTITY. `_inline` emits `&amp;`/`&lt;`/`&gt;`, and clipping between the `&` and
    # the `;` is not merely cosmetic: **`&lt` without its semicolon is in HTML5's legacy named-reference
    # list**, so a lenient renderer turns the truncated escape back into a literal `<` — re-enabling the
    # character the escaper had just neutralised. Drop any dangling head-of-entity.
    return _PARTIAL_ENTITY.sub("", cut) + "…"


def _state_glyph(state: Any) -> str:
    """A matrix cell's state, or ❓ when it is not a renderable string.

    ``MatrixCell.state`` is typed ``str``, but ``Matrix``/``MatrixCell`` are exported — a consumer can
    hand-build or deserialize one. Rendering the literal text ``"None"`` would read as a real verdict;
    ❓ is the module's own "unknown", which is what an unrenderable state actually means.
    """
    return state if isinstance(state, str) and state else "❓"


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
    #: Exception CLASS NAMES (never messages) of everything that degraded this run, de-duplicated in
    #: first-seen order. This is the SECOND LINE of defence behind the wiring pre-flight, and it exists
    #: because the pre-flight provably cannot catch every mis-wiring: it introspects a signature, so a
    #: `(*a, **k)` wrapper forwarding to a narrow inner — or a `def` where an `async def` belongs — sails
    #: through and then raises inside the never-raise boundary. Without this, the ONLY evidence was a log
    #: line, and a consumer with logs off could not tell a wiring bug from an empty market. A run whose
    #: `degrade_causes` contains `TypeError` is a wiring bug essentially every time.
    degrade_causes: list[str] = field(default_factory=list)

    def note_degraded(self, exc: BaseException) -> None:
        """Record the CLASS NAME of a degradation. Never the message — it can carry scraped page text or
        an API key echoed by a client library, and this field is returned to the caller and serialized."""
        name = type(exc).__name__
        if name not in self.degrade_causes:
            self.degrade_causes.append(name)

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
            "degrade_causes": self.degrade_causes,
        }

    def to_markdown(self) -> str:
        """The rendered 'match-then-beat' brief — the HUMAN deliverable, and a full rendering of the
        dossier rather than a summary of it.

        **Provenance, stated precisely** (the blanket "every claim carries its quote + source URL" this
        docstring used to open with was not true of the COMPETITORS section it now renders): feature,
        pricing and white-space claims are RE-GROUNDED — the quote must be a verbatim substring of a real
        fetched source and the url comes from that source. Discovery cards are NOT re-grounded, so the
        COMPETITORS section renders the card's own ``source_urls`` and its ``verified`` flag and asks the
        reader to weigh them; BEAT is Tier-C (corroboration-gated, see the README).

        ⚠️ It renders the RIVALS, the feature matrix and the pricing models as well as MATCH/BEAT. It did
        not until 2026-08-26: a consumer measured **404 bytes** on a 12-rival scan whose ``to_dict()``
        payload was 8.9 KB, and wrote their own renderer off the dict. A deliverable that silently omits
        the thing it was commissioned to produce is worse than no deliverable — the reader cannot tell
        "12 rivals, none noteworthy" from "the rivals are in the payload and nobody printed them".

        ``to_dict()`` remains the complete machine-readable form; this is complete for a READER, which
        means it truncates per-item detail (quotes, source lists) rather than dropping whole sections.
        """
        lines: list[str] = [f"# Competitor dossier — {_inline(self.market)}", ""]
        flags = []
        if self.partial:
            flags.append("partial (some sources degraded)")
        if self.truncated:
            flags.append("truncated (budget ceiling reached)")
        if flags or self.degrade_causes:
            if flags:
                lines.append(f"> ⚠️ {'; '.join(flags)}")
            if self.degrade_causes:
                # Naming the cause in the BRIEF, not only the logs: "partial" alone is what a consumer
                # could not distinguish from "this market has no competitors".
                causes = ", ".join(f"`{_inline(c)}`" for c in self.degrade_causes)
                lines.append(">")
                lines.append(f"> Degraded by: {causes}. A `TypeError` here is almost always a `deps` "
                             f"wiring bug, not an empty market.")
            lines.append("")
        # `isinstance` guard, not a bare `.get`: a malformed card must not crash the RENDER after the
        # money is already spent. `_competitor_lines` flags it visibly rather than dropping it.
        # `is True`, not truthiness: `verified` is produced by the INJECTED engine, and a JSON/YAML
        # round-trip that yields the STRING "false" is truthy — which would both inflate this count and
        # drop the ❓ *unverified* flag below, on the one field that states evidentiary confidence.
        verified = sum(1 for c in self.competitors if isinstance(c, dict) and c.get("verified") is True)
        lines.append(
            f"**Competitors found:** {len(self.competitors)} ({verified} verified)  ·  "
            f"**Signals:** {len(self.review_signal)}  ·  **Spend:** ${self.spend_usd}"
        )
        lines.append("")
        lines.extend(self._competitor_lines())
        lines.extend(self._matrix_lines())

        if self.match_list:
            lines.append("## MATCH — table-stakes rivals have")
            for m in self.match_list:
                star = " ★ universal gap" if m.universal else ""
                rivals = ", ".join(_inline(str(r)) for r in m.rivals_having)
                lines.append(f"- **{_inline(m.feature)}**{star} — {len(m.rivals_having)} rival(s): {rivals}")
            lines.append("")
        if self.beat_list:
            lines.append("## BEAT — rivals' corroborated weaknesses (your openings)")
            for b in self.beat_list:
                lines.append(f"- **{_inline(b.theme)}** (weight {b.weight}, {len(b.source_urls)} sources)")
                for q in b.quotes[:2]:
                    lines.append(f"  - \"{_clip(_inline(str(q)), 300)}\"")
                if len(b.quotes) > 2:
                    lines.append(f"  - *(+{len(b.quotes) - 2} more quotes in `to_dict()`)*")
            lines.append("")
        if self.pricing and (self.pricing.wedge or self.pricing.models):
            lines.append("## PRICING")
            # The MODELS are the evidence the wedge is derived FROM; rendering only the wedge asked the
            # reader to trust a conclusion whose inputs were in the payload they were not shown.
            if self.pricing.models:
                lines.append("")
                lines.append("| Rival | Model | Free tier | Source |")
                lines.append("|---|---|---|---|")
                for pm in self.pricing.models:
                    src = _link("link", str(pm.source_url or "")) if pm.source_url else "—"
                    # `free_tier` is a display STRING ("yes"/"no"/"❓"), never a bool — and it is never
                    # empty (`stages.py:88` defaults it to ❓). A truthiness test therefore printed "yes"
                    # on EVERY row, including the rivals the wedge two lines below correctly called
                    # free-tier-less: the table and the wedge contradicted each other in one section, and
                    # the table was the wrong one. Render the value.
                    lines.append(
                        f"| {_cell(str(pm.competitor))} | {_cell(str(pm.model or '')) or '❓'} | "
                        f"{_cell(str(pm.free_tier or '')) or '❓'} | {src} |"
                    )
                lines.append("")
            if self.pricing.wedge:
                lines.append("**Wedge:**")
                for w in self.pricing.wedge:
                    lines.append(f"- {_inline(str(w))}")
                lines.append("")
        if self.white_space and self.white_space.needs:
            lines.append("## WHITE SPACE — corroborated unmet demand")
            for n in self.white_space.needs:
                lines.append(f"- **{_inline(n.need)}** (weight {n.weight}, {len(n.source_urls)} sources)")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    # ── to_markdown section renderers ────────────────────────────────────────────────────────────────
    #
    # ⚠️ EVERYTHING rendered below is UNTRUSTED. Competitor names, feature names, positioning, evidence,
    # price tiers and every url originate from an LLM reading SCRAPED WEB PAGES — i.e. text an adversary
    # can influence by publishing a page. Two consequences, both proven against this renderer:
    #
    #   * a `|` in a name silently CORRUPTS a markdown table (the header claims one column count, the
    #     separator declares another, and every cell after it shifts into the wrong column — the reader
    #     sees a plausible table with the wrong answers, which is worse than no table);
    #   * a newline in any field escapes its bullet and can forge headings/sections beneath it.
    #
    # So no untrusted value reaches the output un-escaped. `_cell` for table cells, `_inline` for inline
    # text, `_link` for urls.

    def _competitor_lines(self) -> list[str]:
        """The rivals themselves. Unverified ones are RENDERED, flagged ❓ — never dropped: the discovery
        pack ships them deliberately ("Unverifiable candidates ship with verified=false — never dropped"),
        and hiding them here would silently re-impose the filter the pack refuses to apply."""
        if not self.competitors:
            return []
        # Display names go through the SAME sanitize+de-duplicate pipeline the matrix uses, so all three
        # sections (COMPETITORS / FEATURE MATRIX / MATCH) name a rival identically. Rendering the raw card
        # name here while the matrix showed "Acme (2)" left the reader — and any consumer joining the
        # sections by string off `to_dict()` — unable to tell which rival was which.
        # Imported locally: `synth` imports `dossier`, so a top-level import is a cycle.
        from .synth import _uniquify, key_safe

        display = _uniquify(
            key_safe(str(c.get("name") or "")) if isinstance(c, dict) else ""
            for c in self.competitors
        )
        lines = ["## COMPETITORS", ""]
        for display_name, c in zip(display, self.competitors, strict=True):
            # A card that is not a dict is degenerate input, not a reason to crash a RENDER — the whole
            # module is never-raise, and `to_markdown()` blowing up would take the dossier down after the
            # money was already spent.
            if not isinstance(c, dict):
                lines.extend([f"### {_inline(str(c))} ❓ *malformed card*", ""])
                continue
            name = _inline(display_name) or "❓ unnamed"
            mark = "" if c.get("verified") is True else " ❓ *unverified*"
            lines.append(f"### {_link(name, str(c.get('url') or ''))}{mark}")
            if pos := _inline(str(c.get("positioning") or "")):
                lines.append(f"- *\"{pos}\"*")
            if tier := _inline(str(c.get("price_tier") or "")):
                lines.append(f"- **Price tier:** {tier}")
            presence = c.get("market_presence")
            if isinstance(presence, list) and presence:
                joined = ", ".join(_inline(str(p)) for p in presence[:5])
                more = f" (+{len(presence) - 5} more)" if len(presence) > 5 else ""
                lines.append(f"- **Presence:** {joined}{more}")
            if ev := _inline(str(c.get("evidence") or "")):
                lines.append(f"- **Evidence:** {_clip(ev, 300)}")
            # Discovery evidence is NOT re-grounded (the trust rails cover feature-extraction, pricing
            # and white-space — the sections where this module holds the source text). Rendering the
            # card's own `source_urls` is what keeps this section attributable rather than a bare
            # unattributed claim; without them it was the one rendered claim with no provenance at all.
            srcs = c.get("source_urls")
            if isinstance(srcs, list) and srcs:
                shown = ", ".join(_link(f"[{i + 1}]", str(u)) for i, u in enumerate(srcs[:3]))
                more = f" (+{len(srcs) - 3})" if len(srcs) > 3 else ""
                lines.append(f"- **Sources:** {shown}{more}")
            lines.append("")
        return lines

    def _matrix_lines(self) -> list[str]:
        """The feature matrix as a real markdown table. ``us`` (when present) is rendered LAST so the
        us-vs-them read is a single left-to-right scan ending on our own column."""
        m = self.feature_matrix
        if m is None or not m.rows or not m.columns:
            return []
        # Gate the reorder on `has_us`, NOT on the mere presence of the string "us" in `columns`.
        # `gap_synthesis` already guards this way (`synth.py` `not (matrix.has_us and c == "us")`). On a
        # GREENFIELD run (`us=None`, `has_us=False`) a rival literally NAMED "us" would otherwise be
        # promoted into the final column that this section labels "our own" — presenting a rival's
        # feature states as the caller's.
        if m.has_us and "us" in m.columns:
            cols = [c for c in m.columns if c != "us"] + ["us"]
        else:
            cols = list(m.columns)
        lines = ["## FEATURE MATRIX", ""]
        lines.append("| Feature | " + " | ".join(_cell(c) for c in cols) + " |")
        lines.append("|---" * (len(cols) + 1) + "|")
        for row in m.rows:
            # `MatrixCell.state` is TYPED `str`, but `Matrix`/`MatrixCell` are PUBLIC — a consumer can
            # hand-build or deserialize one with a None/empty state, and a render must not raise on it
            # (proven: `" | ".join` over a None state → TypeError). An unrenderable state degrades to the
            # module's own ❓ rather than the literal text "None", which would read as a real verdict.
            cells = " | ".join(_cell(_state_glyph(m.cell(row, col).state)) for col in cols)
            lines.append(f"| {_cell(row)} | {cells} |")
        lines.append("")
        # Imported HERE, not at module scope: synth imports dossier, so a top-level import is a cycle.
        # Derived rather than hardcoded so the legend cannot drift from the glyphs actually rendered —
        # a hand-written legend claiming "🟡 partial" against a "⚠️" cell is a quiet lie to the reader.
        from .synth import HAS, MISSING, PARTIAL, UNKNOWN

        lines.append(
            f"Legend: {HAS} has · {MISSING} missing · {PARTIAL} partial · {UNKNOWN} unknown/unverified"
        )
        lines.append("")
        return lines
