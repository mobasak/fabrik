"""Anthropic pricing parser.

Page: https://docs.anthropic.com/en/docs/about-claude/pricing
Method: rendered (browserless v2; the page is server-rendered React via Mintlify
+ Next.js — no Cloudflare wall, no stealth needed, ~722 KB rendered).

Page structure (after Pass-7 investigation):
  Each Claude 4.x model gets a table row inside a React-flight chunk like:
    \"children\":[\"Claude Opus 4.8\"]}],[\"$\",\"td\",\"1\",{...\"children\":[\"$$5 / MTok\"]}]
  And the row continues with 5 cells in order:
    [input, cache_write_5min, cache_write_1h, cache_hit, output]
  So for each model we take prices[0] = input, prices[4] = output.

Known models on the page (2026-06-30):
  Claude Opus 4.8  → $5  in / $25  out
  Claude Opus 4.7  → $5  in / $25  out  (same; legacy in catalog)
  Claude Opus 4.6  → $5  in / $25  out
  Claude Opus 4.5  → $5  in / $25  out
  Claude Sonnet 4.6 → $3  in / $15  out
  Claude Sonnet 4.5 → $3  in / $15  out
  Claude Haiku 4.5 → $1  in / $5   out
  Claude Fable 5   → $10 in / $50  out

Registry slug_on_page values map to the page-side model name verbatim
(e.g. "Claude Opus 4.8").
"""

from __future__ import annotations

import re
import sys

from . import ParsedRow, per_M_tokens

# The escaped JSON in the React-flight chunk looks like:
#   \"children\":[\"Claude Opus 4.8\"]
# We anchor on that exact escaped form AND restrict to known Claude family
# tokens (Opus/Sonnet/Haiku/Fable/Mythos) followed by an explicit version
# number — this rejects FAQ mentions like "Claude API pricing", "Claude
# Console", "Claude Platform on AWS", which would otherwise grab the next
# 5 prices and write garbage values.
_MODEL_ANCHOR = re.compile(
    r'\\"children\\":\[\\"(Claude\s+(?:Opus|Sonnet|Haiku|Fable|Mythos)(?:\s+(?:Preview|\d+(?:\.\d+)?))?)\\"\]'
)

# Price tokens: literal "$$X / MTok" (the double-$ is the Next.js template
# marker that survived rendering; the X is the price). The "/ MTok" suffix
# rules out matches in unrelated currency mentions.
_PRICE_RE = re.compile(r"\$\$(\d+(?:\.\d+)?)\s*/\s*MTok")


# Case-normalized model names where output ≤ input is a DOCUMENTED billing
# shape (e.g. Claude Mythos-tier has a low output price for cache-hit paths)
# — the pre-Mythos "output > input" invariant does not hold for these.
# Add sparingly; each entry is a per-model attestation that we verified the
# layout on Anthropic's page (plan-4 Phase C, 2026-07-08).
MYTHOS_OUTPUT_LESS_THAN_INPUT_OK = frozenset(
    {
        "claude mythos 5",
        "claude mythos preview",
    }
)


def _model_key(model_name: str) -> str:
    """Case- and whitespace-normalize a model name for whitelist lookup."""
    return " ".join(model_name.lower().split())


def extract(payload: str, source_url: str) -> list[ParsedRow]:
    if not isinstance(payload, str):
        raise TypeError(f"anthropic parser expects str HTML, got {type(payload).__name__}")

    # First pass: collect every (position, price) pair on the page.
    all_prices = [(m.start(), float(m.group(1))) for m in _PRICE_RE.finditer(payload)]
    if not all_prices:
        return []

    rows: list[ParsedRow] = []
    seen_models: set[str] = set()

    # Second pass: each model anchor → 5 consecutive prices after it.
    # We dedupe by model name (the page mentions each model name many times
    # in subsequent FAQ blocks, but only the FIRST occurrence is in the
    # canonical pricing table).
    for m in _MODEL_ANCHOR.finditer(payload):
        model_name = m.group(1).strip()
        if model_name in seen_models:
            continue
        anchor_pos = m.end()
        # Take the next 5 prices after this anchor (must be ≥5 to be a
        # complete pricing-table row; otherwise the "model" is a FAQ mention).
        after = [p for pos, p in all_prices if pos > anchor_pos][:5]
        if len(after) < 5:
            continue
        seen_models.add(model_name)
        input_price, _w5, _w1h, _cache_hit, output_price = after
        # Sanity: Anthropic ALWAYS charges output > input (typically 5x).
        # If the parser hits a model in a non-standard table layout
        # (e.g. the Mythos preview rows have a different column order),
        # output ends up < input — refuse to emit a corrupt ParsedRow.
        if output_price <= input_price:
            # F1 defense: the Mythos whitelist bypasses the "output > input"
            # guard by MODEL NAME only. Add a price-floor sanity so a genuine
            # parser regression that lands output=$0 (or negative) doesn't
            # slip through under a Mythos-tier name.
            if (
                _model_key(model_name) in MYTHOS_OUTPUT_LESS_THAN_INPUT_OK
                and output_price >= 0.1  # cheapest documented Mythos output is $1.5
                and input_price >= 0.1
            ):
                # Documented Mythos-tier billing layout — allow through.
                pass
            else:
                # Pass-8 review: silent filter is fail-closed (right call) but
                # operators skimming cron stderr should see what was dropped.
                sys.stderr.write(
                    f"[anthropic parser] WARN: skipping '{model_name}' — "
                    f"output ${output_price} <= input ${input_price} "
                    "(impossible for Anthropic; likely non-standard table layout)\n"
                )
                continue
        rows.append(
            ParsedRow(
                model_slug=model_name,
                input_price_per_M=per_M_tokens(input_price),
                pricing_unit="M-tokens",
                raw_price_text=f"${input_price} / MTok input, ${output_price} / MTok output",
                source_url=source_url,
            )
        )
    return rows
