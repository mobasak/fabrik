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

# Speechmatics embeds the price inside schema.org metadata. Pattern is the
# parenthesized "(\$0.24 per hour)" string which the page consistently uses
# for the Advanced product description.
_PRICE_RE = re.compile(
    r"\$(\d+\.\d{1,3})\s*per\s+hour",
    re.I,
)


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"speechmatics parser expects str HTML, got {type(payload).__name__}")
    rows: list[ParsedRow] = []
    m = _PRICE_RE.search(payload)
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
