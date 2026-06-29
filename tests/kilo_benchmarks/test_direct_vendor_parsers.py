"""Parser unit tests for the 5 Phase 1 direct-vendor parsers.

Tests use cached HTML fixtures at
tests/kilo_benchmarks/fixtures/direct_vendor_parsers/<vendor>.html — fetched
live on 2026-06-30 + checked in so re-runs are deterministic and pytest never
hits the network. When a vendor redesigns their pricing page, replace the
fixture and update the expected values in this file.

Per docs/development/plans/2026-06-29-plan-direct-vendor-pricing.md (Phase 1).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "kilo-benchmarks"
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "direct_vendor_parsers"

if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _load(vendor: str) -> object:
    return importlib.import_module(f"direct_vendor_parsers.{vendor}")


def _html(vendor: str) -> str:
    return (FIXTURE_DIR / f"{vendor}.html").read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# AssemblyAI: 1 model
# ---------------------------------------------------------------------------
def test_assemblyai_universal2() -> None:
    rows = _load("assemblyai").extract(_html("assemblyai"), "https://www.assemblyai.com/pricing")
    assert len(rows) == 1
    (r,) = rows
    assert r.model_slug == "universal-2"
    assert r.pricing_unit == "audio-min"
    # $0.075/min normalized: 0.075 * 1_000_000 / 60 = 1250
    assert abs(r.input_price_per_M - 1250.0) < 0.5
    assert r.raw_price_text == "$0.075/min"
    assert r.source_url == "https://www.assemblyai.com/pricing"


def test_assemblyai_empty_html() -> None:
    rows = _load("assemblyai").extract("<html></html>", "https://www.assemblyai.com/pricing")
    assert rows == []


def test_assemblyai_rejects_dict_payload() -> None:
    import pytest
    with pytest.raises(TypeError):
        _load("assemblyai").extract({"foo": "bar"}, "https://www.assemblyai.com/pricing")


# ---------------------------------------------------------------------------
# Deepgram: 2 models (one /min, one /hour — exercises the dual-unit regex)
# ---------------------------------------------------------------------------
def test_deepgram_both_models() -> None:
    rows = _load("deepgram").extract(_html("deepgram"), "https://deepgram.com/pricing")
    assert len(rows) == 2
    by_slug = {r.model_slug: r for r in rows}
    assert "nova-2" in by_slug
    assert "nova-3" in by_slug
    # nova-3 should be /min in the fixture; nova-2 in the FAQ /hour form
    assert "/min" in by_slug["nova-3"].raw_price_text
    assert "/hour" in by_slug["nova-2"].raw_price_text
    # Sanity: both prices are positive realistic floats
    for r in rows:
        assert r.input_price_per_M > 0
        assert r.pricing_unit == "audio-min"


def test_deepgram_missing_models_returns_empty() -> None:
    """If neither Nova-2 nor Nova-3 anchors appear, parser returns empty list."""
    rows = _load("deepgram").extract("<html>no models here</html>", "https://deepgram.com/pricing")
    assert rows == []


# ---------------------------------------------------------------------------
# Soniox: 2 STT models (async + realtime), both /hour
# ---------------------------------------------------------------------------
def test_soniox_async_and_realtime() -> None:
    rows = _load("soniox").extract(_html("soniox"), "https://soniox.com/pricing/")
    by_slug = {r.model_slug: r for r in rows}
    assert "stt-async-v4" in by_slug
    assert "stt-realtime-v4" in by_slug
    # $0.10/hour = 100/3600 ≈ 27.78
    assert abs(by_slug["stt-async-v4"].input_price_per_M - 27.78) < 0.1
    # $0.12/hour ≈ 33.33
    assert abs(by_slug["stt-realtime-v4"].input_price_per_M - 33.33) < 0.1
    for r in rows:
        assert r.pricing_unit == "audio-min"


def test_soniox_missing_returns_empty() -> None:
    rows = _load("soniox").extract("<html>no soniox pricing</html>", "https://soniox.com/pricing/")
    assert rows == []


# ---------------------------------------------------------------------------
# Cartesia: 1 model (the parser catches the prominently-displayed per-min price;
# DB has this row as M-chars so the orchestrator's unit-mismatch refusal kicks
# in — that's deliberate, exercised in test_orchestrator.py)
# ---------------------------------------------------------------------------
def test_cartesia_sonic2() -> None:
    rows = _load("cartesia").extract(_html("cartesia"), "https://cartesia.ai/pricing")
    assert len(rows) == 1
    (r,) = rows
    assert r.model_slug == "sonic-2"
    assert r.pricing_unit == "audio-min"
    # $0.06/minute → 1000
    assert abs(r.input_price_per_M - 1000.0) < 0.5


# ---------------------------------------------------------------------------
# Speechmatics: 1 model, /hour
# ---------------------------------------------------------------------------
def test_speechmatics_enhanced() -> None:
    rows = _load("speechmatics").extract(_html("speechmatics"), "https://www.speechmatics.com/pricing")
    assert len(rows) == 1
    (r,) = rows
    assert r.model_slug == "enhanced"
    # $0.24/hour ≈ 66.67
    assert abs(r.input_price_per_M - 66.67) < 0.1
    assert r.pricing_unit == "audio-min"


# ---------------------------------------------------------------------------
# Helper math: pin the seed-compat conversion so a refactor can't drift it.
# ---------------------------------------------------------------------------
def test_helper_per_minute_matches_seed_per_min() -> None:
    """The seed's per_min(0.0036) returns 60.0; our parser helper must match."""
    from direct_vendor_parsers import per_minute_to_M_audio_min
    assert abs(per_minute_to_M_audio_min(0.0036) - 60.0) < 1e-6


def test_helper_per_hour_round_trip() -> None:
    """$0.30/hour normalized then re-displayed should round-trip via the
    browser's fmtCost formula (v/1_000_000*60)."""
    from direct_vendor_parsers import per_hour_to_M_audio_min
    v = per_hour_to_M_audio_min(0.30)
    # Browser displays as $/min; 0.30/hour = 0.005/min
    per_min_back = v / 1_000_000 * 60
    assert abs(per_min_back - 0.005) < 1e-6
