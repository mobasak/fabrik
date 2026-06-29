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

# Adversarial Pass-1 finding (Phase 1 review): a bare $-per-minute regex would
# match the FIRST per-minute price on the page, which is not guaranteed to be
# Sonic-2's. Two-stage defensive strategy:
#
#   1. Confirm we're on a Cartesia *Sonic* page at all (any "Sonic" mention
#      anywhere on the page). If absent, return empty.
#   2. Enumerate all $X per minute occurrences. If they're all the SAME value
#      (single product priced uniformly — Cartesia's real case today), return
#      it as Sonic-2's price. If there are MULTIPLE distinct values, pick the
#      one closest to a "Sonic" mention by character distance — this is the
#      adversarial-test case ("Voice Agents $0.05" before "Sonic-2 $0.06").
_PRICE_RE = re.compile(
    r"\$(\d+\.\d{1,3})\s*(?:per minute|/minute|/min)",
    re.I,
)
_SONIC_RE = re.compile(r"\bsonic[\s\-_]?2?\b", re.I)


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"cartesia parser expects str HTML, got {type(payload).__name__}")
    # Stage 1: page must mention Sonic at all (cheap sanity check).
    sonic_positions = [m.start() for m in _SONIC_RE.finditer(payload)]
    if not sonic_positions:
        return []
    # Stage 2: collect all (position, price_float, raw) for per-minute matches.
    matches = []
    for m in _PRICE_RE.finditer(payload):
        try:
            matches.append((m.start(), float(m.group(1)), m.group(0)))
        except ValueError:
            continue
    if not matches:
        return []
    distinct_values = {round(v, 4) for _, v, _ in matches}
    if len(distinct_values) == 1:
        # Single product price on the page → that IS Sonic-2's price.
        pos, price, raw = matches[0]
    else:
        # Multiple distinct prices: pick the one whose start position is
        # closest to a Sonic mention.
        def distance_to_sonic(price_pos: int) -> int:
            return min(abs(price_pos - sp) for sp in sonic_positions)

        pos, price, raw = min(matches, key=lambda t: distance_to_sonic(t[0]))
    return [
        ParsedRow(
            model_slug="sonic-2",
            input_price_per_M=per_minute_to_M_audio_min(price),
            pricing_unit="audio-min",
            raw_price_text=raw,
            source_url=source_url,
        )
    ]
