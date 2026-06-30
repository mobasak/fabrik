"""Subscription-monitor parser pattern.

Used by vendors that are confirmed SUBSCRIPTION-ONLY today (no per-call API pricing
published). Suno, Udio, HeyGen, ElevenLabs, LlamaIndex, DeepL all fall in this bucket.

Behavior:
  - Successfully fetch the rendered URL (proves vendor URL still reachable + parses).
  - Scan the rendered HTML for per-call pricing indicators ($/M-tokens, $/char,
    $/minute, $/image, $/second). Tier-card prices like "$0/mo", "$99/mo", "$1,200/yr"
    are EXCLUDED (those are subscription tier prices, not per-call rates).
  - If 0 per-call indicators found: return empty list. The orchestrator logs
    `parsed=0 wrote=0` → subscription-only confirmed → last_scraped updated, no
    `input_cost_per_m` write. Operator audit sees this as "successfully verified
    subscription-only on YYYY-MM-DD" rather than as a stale unscraped row.
  - If any per-call indicators found: emit an ALERT ParsedRow with
    `model_slug='<vendor>:per-call-pricing-emergence-alert'`. The orchestrator's
    unit-mismatch refuser catches it (no DB row matches that slug) and logs as
    `missing` action — operator sees the vendor MAY have started offering per-call
    pricing and should re-classify.

Why this matters: today operators have NO daily signal when a subscription-only
vendor flips to per-call pricing. This parser turns the daily refresh into that
signal source.

False-positive guard: we EXCLUDE per-month / per-year / tier-card patterns
(`$<N>/mo`, `$<N>/year`, etc.) because those are tier prices, not per-call. We
also exclude bare `$N` without a per-unit qualifier (likely button labels or
JSON framework artifacts like Next.js `$undefined`).
"""

from __future__ import annotations

import re

from . import ParsedRow

# Per-call price indicators we hunt for. Each pattern requires a price AND a
# per-unit qualifier (anchored to the canonical units the catalog tracks).
# We deliberately match the strict shape `$<digits>.<digits> / <unit>` so we
# don't false-positive on JSON framework strings or per-month tier prices.
# Adversarial review H5+H6 (2026-06-30): tightened patterns.
#   - Each per-unit qualifier now uses (?![-\w]) instead of \b to reject hyphenated
#     compound words ("hour-long", "minute-by-minute") that bare \b allows.
#   - Pattern 7 (formerly catch-all $0.NNN) split into a per-K pattern (H6) and
#     dropped the overbroad version (H5: was false-positiving on "$0.025 / month",
#     "$0.999 per credit", etc.).
_PER_CALL_PATTERNS = [
    # $X / M-tokens, $X / 1M tokens, $X per million tokens
    r"\$\d+(?:\.\d+)?\s*(?:/|per)\s*(?:1\s*)?M(?:Tok|illion)?\s*tokens?(?![-\w])",
    # $X / 1M characters, $X / M-chars
    r"\$\d+(?:\.\d+)?\s*(?:/|per)\s*(?:1\s*)?M(?:illion)?\s*characters?(?![-\w])",
    # H6: $X / 1K tokens, $X per 1k chars, $X per thousand tokens — per-K is
    # a real flip signal (Claude/GPT used to quote per-K). Was previously only
    # caught accidentally by the dropped overbroad pattern.
    r"\$\d+(?:\.\d+)?\s*(?:/|per)\s*(?:1\s*)?[Kk]\s*(?:tokens?|chars?|characters?)(?![-\w])",
    r"\$\d+(?:\.\d+)?\s*(?:/|per)\s*thousand\s*(?:tokens?|chars?|characters?)(?![-\w])",
    # $X / minute, $X per min (audio). (?![-\w]) blocks "minute-by-minute" etc.
    r"\$\d+(?:\.\d+)?\s*(?:/|per)\s*(?:audio[\s-])?(?:minute|min)(?![-\w])",
    # $X / hour. (?![-\w]) blocks "hour-long", "hourly" — those are video runtimes,
    # not API billing units.
    r"\$\d+(?:\.\d+)?\s*(?:/|per)\s*hour(?![-\w])",
    # $X / image, $X per image, $X / generation
    r"\$\d+(?:\.\d+)?\s*(?:/|per)\s*(?:image|generation|gen|render)(?![-\w])",
    # $X / second (realtime audio). (?![-\w]) blocks "seconds-old" etc.
    r"\$\d+(?:\.\d+)?\s*(?:/|per)\s*second(?![-\w])",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PER_CALL_PATTERNS]


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    """Run the subscription-only confirmation scan.

    Returns:
        - Empty list: 0 per-call patterns matched. Subscription-only confirmed.
        - 1+ ParsedRow with `model_slug` ending in `:per-call-pricing-emergence-alert`:
          per-call pricing may have appeared on the page. Operator should re-check.
          The alert row uses pricing_unit='alert' which the orchestrator's
          unit-validator will refuse — flagged as `missing` in the per-vendor
          summary, surfaced in the daily refresh log.
    """
    if not isinstance(payload, str):
        raise TypeError(f"subscription_monitor expects str HTML, got {type(payload).__name__}")

    hits: list[str] = []
    for pat in _COMPILED:
        for m in pat.finditer(payload):
            hits.append(m.group(0).strip())
            if len(hits) >= 3:  # cap — first 3 are enough to signal
                break
        if len(hits) >= 3:
            break

    if not hits:
        return []  # subscription-only confirmed; orchestrator records last_scraped

    # Per-call pricing detected — emit alert row(s). Vendor slug derived from URL
    # for the alert label so the operator can quickly identify which vendor flipped.
    vendor_label = source_url.split("//")[-1].split("/")[0].replace("www.", "")
    sample_hits = " | ".join(hits[:3])
    return [
        ParsedRow(
            model_slug=f"{vendor_label}:per-call-pricing-emergence-alert",
            input_price_per_M=0.0,
            pricing_unit="alert",
            raw_price_text=f"ALERT: per-call pattern(s) detected — {sample_hits}",
            source_url=source_url,
        )
    ]
