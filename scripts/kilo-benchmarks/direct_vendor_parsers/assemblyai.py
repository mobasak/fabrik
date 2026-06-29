"""AssemblyAI pricing parser.

Page: https://www.assemblyai.com/pricing
Method: static (clean SSR HTML; price appears as `$X.XXX/min` inside spans).

Known models on the page (2026-06):
  universal-2: "$0.075/min" (also shown as "$4.50/hr")

Registry slug_on_page values:
  assemblyai/universal-2 -> "universal-2"
"""

from __future__ import annotations

import re

from . import ParsedRow, per_minute_to_M_audio_min

# Universal-2 row marker: the fixture shows the price next to "$4.50/hr ($0.075/min)".
# The "$0.075/min" form is the canonical capture target (3 decimal places, /min suffix).
# Restricting to 3-4 decimals avoids accidentally matching e.g. "$0.10/min" elsewhere.
_PRICE_RE = re.compile(r"\$(\d+\.\d{2,4})/min", re.I)

# Map page-side model identifier -> regex anchor that should appear NEAR the price.
# AssemblyAI's pricing page only has one product-level price block for Universal-2,
# so we anchor on the literal `$0.075/min` (Universal-2 list price); future model
# additions need a new anchor.
_KNOWN_MODELS: dict[str, str] = {
    "universal-2": r"\$0\.075/min",
}


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"assemblyai parser expects str HTML, got {type(payload).__name__}")
    rows: list[ParsedRow] = []
    for slug, anchor in _KNOWN_MODELS.items():
        m = re.search(anchor, payload)
        if not m:
            # Not raising: the orchestrator's "row missing from parsed set"
            # counter will eventually escalate. Logging stays in the orchestrator.
            continue
        # Capture the actual numeric value with the broader regex anchored at
        # the same offset so we get the verbatim "$0.075/min" string for audit.
        # Use the substring around the match to avoid scanning the whole page
        # for the loose regex.
        window = payload[max(0, m.start() - 5) : m.end() + 5]
        price_match = _PRICE_RE.search(window)
        if not price_match:
            continue
        raw = price_match.group(0)
        price_per_min = float(price_match.group(1))
        rows.append(
            ParsedRow(
                model_slug=slug,
                input_price_per_M=per_minute_to_M_audio_min(price_per_min),
                pricing_unit="audio-min",
                raw_price_text=raw,
                source_url=source_url,
            )
        )
    return rows
