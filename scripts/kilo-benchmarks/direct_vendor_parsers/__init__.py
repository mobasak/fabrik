"""Per-vendor pricing parsers for fetch_direct_vendor_prices.py.

Each parser exposes a pure function `extract(payload: str | dict, source_url: str)
-> list[ParsedRow]`. No HTTP. No DB writes. No filesystem I/O. The orchestrator
owns all I/O; parsers transform `payload` (HTML string or pre-parsed dict) into
a list of `ParsedRow` records.

Test fixtures live at `tests/kilo_benchmarks/fixtures/direct_vendor_parsers/<vendor>.html`
so re-runs are deterministic and pytest doesn't hit the network.

Per docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md (Phase 1).
"""

# ruff: noqa: N802, N803, N815 — `_M`/`_per_M` are intentional "per-million" unit
# names (the DB's normalized $/M-billable-units axis), not mixedCase style slips.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedRow:
    """A single (model, price) pair extracted from a vendor's pricing page.

    Fields:
        model_slug: opaque identifier the orchestrator maps to `agents.id` via
            the registry's `slug_on_page` field. NOT necessarily the vendor's
            internal model ID; just whatever the parser uses to identify the
            row on the page.
        input_price_per_M: price normalized to "$ per million billable units"
            where the unit matches `pricing_unit`. The seeder pattern (see
            seed_direct_vendors.py:per_1k_chars) uses this normalization:
              - M-tokens     -> $ per million tokens
              - M-chars      -> $ per million characters
              - audio-min    -> $ per million audio minutes (so $0.06/min = $60_000/M)
              - image        -> $ per million images
              - video-sec    -> $ per million video seconds
              - page         -> $ per million pages
        pricing_unit: must match the DB row's `pricing_unit`. The orchestrator
            REFUSES to write when this differs from what the DB expects
            (likely parse bug).
        raw_price_text: the vendor's verbatim price string ("$0.075/min") for
            audit + alert messages.
        source_url: the vendor URL the price was scraped from (audit trail).
    """

    model_slug: str
    input_price_per_M: float
    pricing_unit: str
    raw_price_text: str
    source_url: str


# Conversion helpers - vendor prices commonly come per-minute, per-hour, per-1K
# chars, etc. The DB stores normalized $/M-billable-units to keep the sort axis
# uniform across heterogeneous services. These mirror the inverse of
# seed_direct_vendors.py's per_1k_chars()/per_image() helpers.


def per_minute_to_M_audio_min(price_per_minute: float) -> float:
    """$0.0036/min -> 60.0 (matches seed's per_min at seed_direct_vendors.py:58).

    The schema column is `pricing_unit='audio-min'` BUT the normalized axis is
    actually `$ per million audio-SECONDS` (the seed divides by 60 after the
    million-multiply; the browser's fmtCost reverses this with
    `perMin = v / 1_000_000 * 60`). This helper matches that convention so a
    re-scraped price is byte-identical to what the seeder originally wrote.
    """
    return price_per_minute * 1_000_000 / 60


def per_hour_to_M_audio_min(price_per_hour: float) -> float:
    """$0.30/hour -> 83.33 (same axis as per_minute_to_M_audio_min)."""
    return price_per_hour * 1_000_000 / 3600


def per_1k_chars_to_M_chars(price_per_1k: float) -> float:
    """$0.18/1K chars -> 180 ($ per million chars)."""
    return price_per_1k * 1000


def per_image_to_M_image(price_per_image: float) -> float:
    """$0.04/image -> 40_000 ($ per million images)."""
    return price_per_image * 1_000_000


def per_second_to_M_video_sec(price_per_second: float) -> float:
    """$0.05/sec -> 50_000 ($ per million video-seconds)."""
    return price_per_second * 1_000_000


def per_page_to_M_page(price_per_page: float) -> float:
    """$0.001/page -> 1000 ($ per million pages)."""
    return price_per_page * 1_000_000


def per_M_tokens(price_per_M: float) -> float:
    """LLMs already quote in $/M-tokens; identity for symmetry."""
    return float(price_per_M)


__all__ = [
    "ParsedRow",
    "per_minute_to_M_audio_min",
    "per_hour_to_M_audio_min",
    "per_1k_chars_to_M_chars",
    "per_image_to_M_image",
    "per_second_to_M_video_sec",
    "per_page_to_M_page",
    "per_M_tokens",
]
