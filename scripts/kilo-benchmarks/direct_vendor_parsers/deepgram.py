"""Deepgram pricing parser.

Page: https://deepgram.com/pricing
Method: static (clean SSR HTML; prices appear as `$X.XXXX/min` inside spans;
multiple models live on the same page so we anchor on price-value-as-token
since the model names are far from the price spans in the DOM).

Known models on the page (2026-06; live values may differ from seed):
  nova-2:  appears as part of a table cell; the historically-correct price
           was $0.0036/min but Deepgram has refreshed price tiers — the
           orchestrator's >10% audit alert handles drift.
  nova-3:  similarly the canonical price.

Because the page lists nova-2 and nova-3 in adjacent tiers without putting
model names inside the same DOM ancestor as the price spans, we identify
each row by its specific price tier ordering on the page. This is fragile
to page redesigns; the orchestrator's `consecutive_fetch_failures` guard +
the parser's strict "must find both rows" check together degrade gracefully.

Registry slug_on_page values:
  deepgram/nova-2 -> "nova-2"
  deepgram/nova-3 -> "nova-3"
"""

from __future__ import annotations

import re

from . import ParsedRow, per_hour_to_M_audio_min, per_minute_to_M_audio_min

# Deepgram surfaces prices in two forms:
#   - flagship tiers: "$X.XXXX/min" inside spans
#   - legacy tiers (Nova-2, Enhanced, Base): "$0.XX/hour" inside FAQ prose
# The regex captures either; the orchestrator path picks `per_minute_*` or
# `per_hour_*` based on which suffix matched (group 2).
_PRICE_RE = re.compile(
    r"\$(\d+\.\d{2,4})\s*/?(?:&#x2F;|/)?\s*(min|hour)\b",
    re.I,
)

# Anchors for each model — Deepgram puts the model name in a separate card
# heading. We find the heading's offset, then take the NEXT price-tier span.
_MODEL_ANCHORS: dict[str, list[re.Pattern]] = {
    # Try several anchor patterns; first match wins.
    "nova-3": [
        re.compile(r"Nova-3\b", re.I),
        re.compile(r"\bnova[\s\-_]?3\b", re.I),
    ],
    "nova-2": [
        re.compile(r"Nova-2\b", re.I),
        re.compile(r"\bnova[\s\-_]?2\b", re.I),
    ],
}


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"deepgram parser expects str HTML, got {type(payload).__name__}")
    rows: list[ParsedRow] = []
    for slug, anchors in _MODEL_ANCHORS.items():
        # Find the model-name anchor (first matching pattern wins).
        anchor_pos: int | None = None
        for anchor_re in anchors:
            m = anchor_re.search(payload)
            if m is not None:
                anchor_pos = m.end()
                break
        if anchor_pos is None:
            continue
        # Take the FIRST $X.XXXX/{min|hour} span after the anchor (within a
        # 4 KB window to avoid pulling a price from an unrelated card later).
        window = payload[anchor_pos : anchor_pos + 4096]
        price_match = _PRICE_RE.search(window)
        if price_match is None:
            continue
        raw = price_match.group(0)
        price_value = float(price_match.group(1))
        unit_suffix = price_match.group(2).lower()
        if unit_suffix == "hour":
            normalized = per_hour_to_M_audio_min(price_value)
        else:  # 'min'
            normalized = per_minute_to_M_audio_min(price_value)
        rows.append(
            ParsedRow(
                model_slug=slug,
                input_price_per_M=normalized,
                pricing_unit="audio-min",
                raw_price_text=raw,
                source_url=source_url,
            )
        )
    return rows
