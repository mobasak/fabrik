"""Speechmatics pricing parser.

Page: https://www.speechmatics.com/pricing
Method: static (schema.org JSON-LD product description carries the price
as "Advanced features for professional use ($0.24 per hour)").

Known models on the page (2026-06):
  enhanced: "$0.24 per hour" (the "Advanced" tier maps to the DB's
            speechmatics/enhanced row)

Registry slug_on_page values:
  speechmatics/enhanced -> "enhanced"
"""

from __future__ import annotations

import re

from . import ParsedRow, per_hour_to_M_audio_min

# Adversarial Pass-1 finding (Phase 1 review): a bare $-per-hour regex would
# match the FIRST per-hour price on the page, which may not be the Enhanced/
# Advanced tier. Anchor on Speechmatics' Advanced-tier description phrase
# ("Advanced features for professional use") and take the price WITHIN the
# parenthesised phrase that follows.
_ADVANCED_ANCHOR = re.compile(r"Advanced\s+features\s+for\s+professional\s+use", re.I)
_PRICE_RE = re.compile(
    r"\$(\d+\.\d{1,3})\s*per\s+hour",
    re.I,
)


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"speechmatics parser expects str HTML, got {type(payload).__name__}")
    rows: list[ParsedRow] = []
    anchor = _ADVANCED_ANCHOR.search(payload)
    if anchor is None:
        return rows
    # The price appears within a short parenthesised phrase right after the
    # anchor — restrict the search window to 200 chars so a different per-hour
    # price elsewhere in the page can't accidentally hijack the match.
    window = payload[anchor.end() : anchor.end() + 200]
    m = _PRICE_RE.search(window)
    if m is None:
        return rows
    price = float(m.group(1))
    rows.append(
        ParsedRow(
            model_slug="enhanced",
            input_price_per_M=per_hour_to_M_audio_min(price),
            pricing_unit="audio-min",
            raw_price_text=m.group(0),
            source_url=source_url,
        )
    )
    return rows
