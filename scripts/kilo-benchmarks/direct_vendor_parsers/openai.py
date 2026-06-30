"""OpenAI pricing parser.

Page: https://platform.openai.com/docs/pricing
Method: rendered (browserless v2; the page is server-rendered React with
HTML-encoded JSON inside <script> tags — no Cloudflare wall on platform
subdomain unlike openai.com/api/pricing which IS Cloudflare-walled even
with stealth=True).

Page structure (after Pass-7+ investigation):
  The pricing tables are HTML-encoded JSON inside React-component props:
    {"model":[0,"<MODEL_NAME>"],"rows":[1,[[1,[
        [0,"<row_label>"],[0,<num1>],[0,<num2>],[0,"$X / <unit>"]
    ]]]]}
  Each model is followed by 1+ row arrays; the LAST item per row is the
  price string. Multiple price units appear: "$X / minute" (transcription
  + realtime audio), "$X / 1M characters" (TTS), "$X / 1M tokens" (LLM),
  "$X / second" (realtime per-second).

Known models on the page (2026-06-30):
  gpt-4o-transcribe          → $0.006 / minute (STT)
  gpt-4o-mini-transcribe     → $0.003 / minute (STT mini)
  gpt-4o-transcribe-diarize  → $0.006 / minute (STT + diarization)
  Whisper                    → $0.006 / minute (legacy STT)
  tts-1                      → $15.00 / 1M characters
  tts-1-hd                   → $30.00 / 1M characters
  gpt-4o-mini-tts            → $15.00 / 1M characters
  gpt-audio                  → $15.00 / 1M characters (audio I/O)
  gpt-realtime-2             → $0.034 / minute (realtime)
  gpt-realtime-whisper       → $0.017 / minute (streaming STT)

Each registry mapping uses the page-side model name verbatim as slug_on_page.
Prices on the page are PRE-NORMALIZED: $0.006/min = 100/M-audio-min via the
seed's per_min helper (verified: matches seed exactly for whisper-large-v3,
gpt-4o-transcribe, gpt-4o-mini-transcribe, tts-1, tts-1-hd, gpt-4o-mini-tts).
"""

from __future__ import annotations

import html as html_mod
import re
import sys

from . import (
    ParsedRow,
    per_1k_chars_to_M_chars,
    per_M_tokens,
    per_minute_to_M_audio_min,
)

# Each model is anchored by `"model":[0,"<NAME>"]` in the page's React-flight chunks.
# The page is HTML-encoded so we decode entities first (`&quot;` → `"`) before matching.
_MODEL_ANCHOR = re.compile(r'"model":\[0,"([a-zA-Z0-9\-_. ]+)"\]')

# Price tokens inside row arrays. Restrict the unit suffix to the canonical
# OpenAI units to reject false positives (tier card prices like "$0/month").
_PRICE_RE = re.compile(
    r'"\$([0-9]+(?:\.[0-9]+)?)\s*/\s*(minute|1M characters|1M tokens|MTok|hour|second)"'
)

# How many chars after the anchor to scan for the FIRST price.
# Sized at 2000 (was 1200) after Pass-8 review caught gpt-4o-realtime-preview
# at offset 1112 in the live fixture — only 88 chars of headroom. If OpenAI
# adds another row (image-modality pricing) to that model's block, the parser
# would have walked into the NEXT model's first price. 2000 gives us 900+
# chars of slack while still being smaller than the gap between adjacent
# pricing tables (~3KB) so we don't cross table boundaries.
_WINDOW_BYTES = 2000


def _normalize(price: float, unit: str) -> tuple[float, str] | None:
    """Map a (price, vendor_unit_string) to (normalized_price, db_unit)."""
    unit = unit.lower().strip()
    if unit == "minute":
        return per_minute_to_M_audio_min(price), "audio-min"
    if unit == "hour":
        # 1 hour = 60 minutes; reuse per_min after dividing by 60
        return per_minute_to_M_audio_min(price / 60), "audio-min"
    if unit in ("1m characters", "m-chars"):
        # Vendor quotes $X/1M chars → seed's per_1k_chars does *1000 from $/1K.
        # $15/1M chars = $0.015/1K chars → per_1k_chars(0.015) = 15. So pass
        # the per-1M value through per_1k_chars(/1000) for symmetry.
        return per_1k_chars_to_M_chars(price / 1000), "M-chars"
    if unit in ("1m tokens", "mtok"):
        return per_M_tokens(price), "M-tokens"
    # "second" is realtime per-second pricing; not a seed unit — skip
    return None


# Adversarial review C5 (2026-06-30): allowlist of OpenAI slugs whose price is
# (a) in the registry mapping today (whisper/tts-1/etc.) OR (b) a future-safe
# model from the same TTS/STT family the registry will likely add. Slugs OUTSIDE
# this allowlist are skipped — the parser was previously emitting 14 unmapped
# rows (gpt-realtime-2, gpt-audio-mini, etc.) that the orchestrator silently
# treated as `missing`, polluting the audit MD with spurious entries.
#
# To onboard a new OpenAI model, add its slug here. Operator confidence test:
# scripts/kilo-benchmarks/test_add_vendor_roundtrip.sh.
_ALLOWED_OPENAI_SLUGS = frozenset(
    {
        # Registry-mapped today
        "Whisper",
        "gpt-4o-transcribe",
        "gpt-4o-mini-transcribe",
        "tts-1",
        "tts-1-hd",
        "gpt-4o-mini-tts",
        # Variants that may become registry-mapped (intentionally narrow)
        "gpt-4o-transcribe-diarize",
    }
)


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"openai parser expects str HTML, got {type(payload).__name__}")
    # The fixture is HTML-encoded; decode entities once so the regex can match
    # the canonical JSON form (`"` not `&quot;`).
    decoded = html_mod.unescape(payload)
    rows: list[ParsedRow] = []
    seen: set[str] = set()
    for m in _MODEL_ANCHOR.finditer(decoded):
        name = m.group(1).strip()
        if name in seen:
            continue
        # C5: drop unmapped slugs early so the parser never emits ParsedRows
        # the orchestrator will discard as `missing`. Whitelist is the cheap
        # way to keep this deterministic; adding a new OpenAI model is a
        # 2-line change (registry mapping + add to _ALLOWED_OPENAI_SLUGS).
        if name not in _ALLOWED_OPENAI_SLUGS:
            continue
        window = decoded[m.end() : m.end() + _WINDOW_BYTES]
        price_match = _PRICE_RE.search(window)
        if price_match is None:
            continue
        seen.add(name)
        try:
            price = float(price_match.group(1))
        except ValueError:
            continue
        unit_text = price_match.group(2)
        normalized = _normalize(price, unit_text)
        if normalized is None:
            # Pass-8 review: per-second prices (or any unrecognized unit) get
            # silently filtered. Log so the daily-refresh stderr captures it
            # — an operator skimming the cron output sees what dropped.
            sys.stderr.write(
                f"[openai parser] WARN: skipping '{name}' — unit '{unit_text}' "
                "has no normalization to a seed unit\n"
            )
            continue
        # noqa: N806 — `price_per_m_value` would be misleading; the M is the
        # semantic unit (per-million-billable-units), not a mixedCase style flag.
        price_per_m_value, db_unit = normalized  # noqa: N806
        rows.append(
            ParsedRow(
                model_slug=name,
                input_price_per_M=price_per_m_value,
                pricing_unit=db_unit,
                raw_price_text=f"${price} / {unit_text}",
                source_url=source_url,
            )
        )
    return rows
