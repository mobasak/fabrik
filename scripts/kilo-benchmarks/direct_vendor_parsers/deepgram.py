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


# Adversarial review C4 (2026-06-30): tightened anchor scoping.
#
# Pre-fix: parser grabbed the FIRST `$X/(min|hour)` within 4 KB of any Nova-N
# mention. If Deepgram reordered the FAQ table or added a new card between the
# Nova-N anchor and its real price, the parser silently picked the wrong tier's
# price (e.g., Enhanced's $0.99/hour for nova-2). Direct invariant #1 violation.
#
# Post-fix: window shrunk from 4096 → 600 chars (must be tightly adjacent).
# AND we require the model name to appear in the same 600-char window as the
# price — eliminates "anchor at FAQ header → price 5 KB later" failures.
_MAX_PRICE_WINDOW_BYTES = 600


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"deepgram parser expects str HTML, got {type(payload).__name__}")
    rows: list[ParsedRow] = []
    for slug, anchors in _MODEL_ANCHORS.items():
        # Find ALL anchor positions in the payload (multiple Nova-N mentions on
        # the FAQ + table; we want to try each and pick the first one whose
        # nearby window also contains the model name + price together).
        all_positions: list[int] = []
        for anchor_re in anchors:
            for m in anchor_re.finditer(payload):
                all_positions.append(m.end())
        if not all_positions:
            continue

        # For each anchor occurrence, scan a 600-byte window and accept the
        # first price tightly adjacent. Tighter than the original 4 KB.
        # Adversarial review C4: this prevents Enhanced's $0.99/hour from
        # being assigned to nova-2 when they're > 600 chars apart.
        emitted = False
        for anchor_pos in all_positions:
            window = payload[anchor_pos : anchor_pos + _MAX_PRICE_WINDOW_BYTES]
            price_match = _PRICE_RE.search(window)
            if price_match is None:
                continue
            # Defense-in-depth: the slug must appear in the IMMEDIATE 80 chars
            # before the price — this catches "Nova-2 streaming at $0.35/hour"
            # (nova-2 → 13 chars → $) but rejects "Nova-2 family </span><tr><td>
            # Enhanced</td><td>$0.99/hour" (nova-2 → 50+ chars of HTML with
            # OTHER model names between anchor and price). The anchor itself
            # counts: the 80-char buffer includes the anchor position.
            price_offset_in_window = price_match.start()
            # Build a 80-char snippet that ends at the price.
            slug_proximity_start = max(0, price_offset_in_window - 80)
            slug_proximity = window[slug_proximity_start:price_offset_in_window]
            slug_re = re.compile(rf"\b{re.escape(slug)}\b", re.I)
            # The anchor itself is at window[0]; include the buffer chars
            # BEFORE the price to check if there's a nearby reaffirmation of
            # the slug. If the price is within 80 chars of window-start, the
            # anchor counts as the "reaffirmation".
            anchor_in_buffer = price_offset_in_window <= 80
            if not (anchor_in_buffer or slug_re.search(slug_proximity)):
                continue
            # Additional defense: reject if a COMPETING Deepgram model name
            # ("Enhanced", "Base", "Flux") appears between the anchor and the
            # price — strongest signal of a mis-anchored grab.
            other_model_re = re.compile(r"\b(Enhanced|Base|Flux)\b", re.I)
            if other_model_re.search(window[:price_offset_in_window]):
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
            emitted = True
            break  # one row per slug
        if not emitted:
            # No tightly-anchored price found for this slug. Better to be
            # silent than wrong — operator audit will show 0 writes for this
            # vendor, prompting investigation, vs. a wrong price written.
            continue
    return rows
