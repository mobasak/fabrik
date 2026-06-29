"""Cartesia pricing parser.

Page: https://cartesia.ai/pricing
Method: static (SSR; price text appears as `$0.06 per minute` AND `$0.06/minute`
in different DOM positions for the same product — Sonic-2).

Known models on the page (2026-06):
  sonic-2: "$0.06 per minute" (also rendered as "$0.06/minute" in tables)

Registry slug_on_page values:
  cartesia/sonic-2 -> "sonic-2"
"""

from __future__ import annotations

import re

from . import ParsedRow, per_minute_to_M_audio_min

# Cartesia's pricing page consistently shows "$0.06 per minute" for Sonic-2.
# Pattern handles both "per minute" and "/minute"; whichever appears first wins.
_PRICE_RE = re.compile(
    r"\$(\d+\.\d{1,3})\s*(?:per minute|/minute|/min)",
    re.I,
)


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"cartesia parser expects str HTML, got {type(payload).__name__}")
    rows: list[ParsedRow] = []
    m = _PRICE_RE.search(payload)
    if m is None:
        return rows
    price = float(m.group(1))
    rows.append(
        ParsedRow(
            model_slug="sonic-2",
            input_price_per_M=per_minute_to_M_audio_min(price),
            pricing_unit="audio-min",
            raw_price_text=m.group(0),
            source_url=source_url,
        )
    )
    return rows
