"""Soniox pricing parser.

Page: https://soniox.com/pricing/
Method: static (clean text; prices appear as `$X.XX/hour` in marketing copy
+ schema.org JSON-LD; need /hour -> normalized-axis conversion).

Known models on the page (2026-06):
  stt-async-v4:    "$0.10/hour for async (file uploads)"
  stt-realtime-v4: "$0.12/hour for real-time (streaming)"
  tts:             "$4 per 1M tokens" (TTS is token-billed not char-billed
                   on this product — Phase 1 only writes stt-* prices to
                   avoid changing the row's pricing_unit; tts handled in P2)

Registry slug_on_page values (only stt-* in Phase 1):
  soniox/stt-async-v4    -> "stt-async-v4"
  soniox/stt-realtime-v4 -> "stt-realtime-v4"
"""

from __future__ import annotations

import re

from . import ParsedRow, per_hour_to_M_audio_min

# Soniox marketing copy is consistent: "$0.10/hour for async" + "$0.12/hour for real-time".
# Anchor on the explicit phrasing for each — strict so a page redesign breaks loudly.
_ASYNC_RE = re.compile(
    r"\$(\d+\.\d{1,3})/hour\s+for\s+async",
    re.I,
)
_REALTIME_RE = re.compile(
    r"\$(\d+\.\d{1,3})/hour\s+for\s+real[\s-]?time",
    re.I,
)


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"soniox parser expects str HTML, got {type(payload).__name__}")
    rows: list[ParsedRow] = []

    m = _ASYNC_RE.search(payload)
    if m is not None:
        price = float(m.group(1))
        rows.append(
            ParsedRow(
                model_slug="stt-async-v4",
                input_price_per_M=per_hour_to_M_audio_min(price),
                pricing_unit="audio-min",
                raw_price_text=f"${price}/hour",
                source_url=source_url,
            )
        )

    m = _REALTIME_RE.search(payload)
    if m is not None:
        price = float(m.group(1))
        rows.append(
            ParsedRow(
                model_slug="stt-realtime-v4",
                input_price_per_M=per_hour_to_M_audio_min(price),
                pricing_unit="audio-min",
                raw_price_text=f"${price}/hour",
                source_url=source_url,
            )
        )

    return rows
