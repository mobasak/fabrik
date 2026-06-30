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


# ============================================================
# Adversarial Pass-1 regression tests (Phase 1 review)
# ============================================================

def test_cartesia_anchors_on_sonic_skips_voice_agents() -> None:
    """Adversarial Pass-1 finding #1: a previous version of the cartesia
    parser used a bare $-per-minute regex and would match the FIRST per-minute
    price on the page — which is not guaranteed to be Sonic-2's. If Cartesia
    surfaces Voice Agents pricing before Sonic-2, the parser must IGNORE the
    Voice Agents number and find Sonic-2's price."""
    html = (
        "<html>"
        "<section><h3>Voice Agents</h3><p>$0.05 per minute</p></section>"
        "<section><h3>Sonic-2 TTS</h3><p>$0.06 per minute</p></section>"
        "</html>"
    )
    rows = _load("cartesia").extract(html, "https://cartesia.ai/pricing")
    assert len(rows) == 1
    # 0.06/min normalized = 1000.0 (per_minute_to_M_audio_min); 0.05 = 833.33.
    # If the regex grabbed the WRONG product, we'd see 833.33 here.
    assert abs(rows[0].input_price_per_M - 1000.0) < 0.5
    assert rows[0].raw_price_text.startswith("$0.06")


def test_speechmatics_anchors_on_advanced_skips_standard() -> None:
    """Adversarial Pass-1 finding #2: previous version matched the FIRST
    $-per-hour price on the page. If Speechmatics lists a Standard tier
    first ($0.10/hour) before Advanced ($0.24/hour), the parser must
    anchor on "Advanced features for professional use" and pick the right
    price."""
    html = (
        "<html>"
        '<div>Standard tier: <span>$0.10 per hour</span></div>'
        '<div>Advanced features for professional use ($0.24 per hour)</div>'
        "</html>"
    )
    rows = _load("speechmatics").extract(html, "https://www.speechmatics.com/pricing")
    assert len(rows) == 1
    # 0.24/hour normalized = 66.67. 0.10/hour = 27.78. If the anchor failed,
    # we'd see 27.78.
    assert abs(rows[0].input_price_per_M - 66.67) < 0.1
    assert "0.24" in rows[0].raw_price_text


def test_cartesia_equidistant_prices_tie_breaker() -> None:
    """Adversarial Pass-2 finding: when two prices are equidistant from a
    Sonic mention, the parser MUST be deterministic. Documented tie-breaker:
    prefer the textually-earlier price (leftmost on the page).

    Construction (positions calculated to be EXACTLY equidistant):
      "$0.05 per minute" (16 chars) at offset 0
      30-char pad
      "Sonic-2" (7 chars) at offset 46
      39-char pad (= 30 + 9 to compensate for the asymmetry of
                    16-char-price-text vs 7-char-anchor)
      "$0.06 per minute" at offset 92
    Distance($0.05 start -> Sonic start) = 46 - 0 = 46.
    Distance($0.06 start -> Sonic start) = 92 - 46 = 46. Equal."""
    # Surround "Sonic-2" with spaces so the anchor regex's trailing \b
    # matches (the regex requires a word boundary after the optional "2").
    # Compensate the padding to keep the EQUAL distance: -2 chars per side.
    pad_before = "x" * 29
    pad_after = "x" * 38
    html = f"$0.05 per minute{pad_before} Sonic-2 {pad_after}$0.06 per minute"
    rows = _load("cartesia").extract(html, "https://cartesia.ai/pricing")
    assert len(rows) == 1
    # 0.05/min normalized = 833.33 (per_minute_to_M_audio_min)
    assert abs(rows[0].input_price_per_M - 833.33) < 0.5, (
        f"tie-breaker should prefer textually-earlier price (0.05); "
        f"got {rows[0].input_price_per_M} from {rows[0].raw_price_text!r}"
    )
    assert "0.05" in rows[0].raw_price_text


# ============================================================
# Anthropic parser (Phase-3 deliverable, added 2026-06-30)
# ============================================================

def test_anthropic_extracts_canonical_4x_models() -> None:
    """Anthropic docs page lists 4.x family in a standard
    [input, batch_w5, batch_w1h, cache_hit, output] table-row layout."""
    rows = _load("anthropic").extract(
        _html("anthropic"),
        "https://docs.anthropic.com/en/docs/about-claude/pricing",
    )
    by_slug = {r.model_slug: r for r in rows}
    # Canonical Claude 4.x family must all be present
    for model in ("Claude Opus 4.8", "Claude Sonnet 4.6", "Claude Haiku 4.5", "Claude Fable 5"):
        assert model in by_slug, f"missing {model}: got {sorted(by_slug)}"
    # Pin the actual prices so a future page change breaks loudly
    assert by_slug["Claude Opus 4.8"].input_price_per_M == 5.0
    assert by_slug["Claude Sonnet 4.6"].input_price_per_M == 3.0
    assert by_slug["Claude Haiku 4.5"].input_price_per_M == 1.0
    assert by_slug["Claude Fable 5"].input_price_per_M == 10.0
    # All rows must report M-tokens unit (sanity)
    assert all(r.pricing_unit == "M-tokens" for r in rows)


def test_anthropic_rejects_output_lt_input_sanity() -> None:
    """If a hypothetical table layout puts output BEFORE input, the sanity
    check `output > input` rejects the parse — Anthropic ALWAYS charges
    output > input (typically 5x). Construct a synthetic HTML with the
    "Mythos preview" non-standard layout and assert it's silently filtered."""
    html = (
        r'\"children\":[\"Claude Mythos 5\"] '
        r'$$7.50 / MTok $$37.50 / MTok $$1.50 / MTok $$7.50 / MTok $$1.50 / MTok'
    )
    rows = _load("anthropic").extract(html, "https://example.com/")
    # Output (1.50) < input (7.50) — sanity check rejects this row
    assert rows == [], f"expected empty list, got {[r.model_slug for r in rows]}"


def test_anthropic_rejects_unknown_claude_phrase() -> None:
    """Anchor only matches Claude {Opus|Sonnet|Haiku|Fable|Mythos} <version>.
    Phrases like 'Claude API pricing', 'Claude Console', 'Claude Platform'
    must NOT trigger the parser (they would grab random nearby prices)."""
    html = (
        r'\"children\":[\"Claude API pricing\"] $$10 / MTok $$50 / MTok '
        r'$$5 / MTok $$25 / MTok $$2.50 / MTok'
    )
    rows = _load("anthropic").extract(html, "https://example.com/")
    assert rows == []


def test_anthropic_empty_html_returns_empty() -> None:
    rows = _load("anthropic").extract("<html></html>", "https://example.com/")
    assert rows == []


def test_anthropic_rejects_dict_payload() -> None:
    import pytest
    with pytest.raises(TypeError):
        _load("anthropic").extract({"foo": "bar"}, "https://example.com/")


# ============================================================
# OpenAI parser (Phase-3 deliverable, added 2026-06-30)
# ============================================================

def test_openai_extracts_canonical_audio_models() -> None:
    """OpenAI's platform.openai.com/docs/pricing has HTML-encoded JSON
    chunks like {"model":[0,"<NAME>"],"rows":[...,"$X / unit"]}.
    The 6 DB-mapped models must all parse with PERFECT seed-matching
    prices (these prices have been stable for >12 months)."""
    rows = _load("openai").extract(
        _html("openai"),
        "https://platform.openai.com/docs/pricing",
    )
    by_slug = {r.model_slug: r for r in rows}
    # 6 canonical audio models that map to existing DB rows
    expected = {
        "Whisper": (100.0, "audio-min"),
        "gpt-4o-transcribe": (100.0, "audio-min"),
        "gpt-4o-mini-transcribe": (50.0, "audio-min"),
        "tts-1": (15.0, "M-chars"),
        "tts-1-hd": (30.0, "M-chars"),
        "gpt-4o-mini-tts": (15.0, "M-chars"),
    }
    for name, (price, unit) in expected.items():
        assert name in by_slug, f"missing {name}: got {sorted(by_slug)}"
        assert abs(by_slug[name].input_price_per_M - price) < 0.01, (
            f"{name}: expected ${price}/M, got {by_slug[name].input_price_per_M}"
        )
        assert by_slug[name].pricing_unit == unit


def test_openai_normalize_per_minute_matches_seed() -> None:
    """$0.006/min → 100/M-audio-min. This is the same conversion the seed uses
    (per_min in seed_direct_vendors.py)."""
    rows = _load("openai").extract(
        _html("openai"), "https://platform.openai.com/docs/pricing"
    )
    whisper = next(r for r in rows if r.model_slug == "Whisper")
    assert whisper.input_price_per_M == 100.0
    assert whisper.raw_price_text == "$0.006 / minute"


def test_openai_normalize_per_1M_chars_matches_seed() -> None:
    """$15/1M chars → 15/M-chars. Same as seed's per_1k_chars(0.015)."""
    rows = _load("openai").extract(
        _html("openai"), "https://platform.openai.com/docs/pricing"
    )
    tts1 = next(r for r in rows if r.model_slug == "tts-1")
    assert tts1.input_price_per_M == 15.0


def test_openai_empty_html_returns_empty() -> None:
    rows = _load("openai").extract("<html></html>", "https://example.com/")
    assert rows == []


def test_openai_rejects_dict_payload() -> None:
    import pytest
    with pytest.raises(TypeError):
        _load("openai").extract({"foo": "bar"}, "https://example.com/")


def test_openai_skips_per_second_unit() -> None:
    """OpenAI lists some realtime models in '$X / second' — we don't have a
    seed unit for that, so the parser SKIPS those rows rather than emitting
    a corrupt ParsedRow. Construct a synthetic minimal fixture."""
    # Verbatim escape-style "model" object with only a per-second price
    html_fragment = '"model":[0,"hypothetical-per-sec-model"],"rows":[1,[[1,[[0,"x"],[0,1],[0,2],[0,"$0.00028 / second"]]]]]}'
    rows = _load("openai").extract(html_fragment, "https://example.com/")
    assert rows == [], "per-second prices have no seed unit; must be skipped"


def test_openai_window_size_handles_multi_row_models() -> None:
    """Pass-8 regression: _WINDOW_BYTES must be large enough that a model
    with several rows (e.g. Image + Audio + Text + Cached + Output ~ 1500
    chars after the anchor) still finds its FIRST price before walking into
    the next model's price. Synthetic fixture: model "test-multi-row" has
    1700 chars of filler before its $X/minute, then "next-model" follows."""
    filler = "x" * 1700
    html_fragment = (
        f'"model":[0,"test-multi-row"]' + filler +
        '[0,"$0.999 / minute"],"model":[0,"next-model"],"rows":[1,[[1,[[0,"x"],[0,1],[0,2],[0,"$0.001 / minute"]]]]]}'
    )
    rows = _load("openai").extract(html_fragment, "https://example.com/")
    by_slug = {r.model_slug: r for r in rows}
    # test-multi-row must report ITS price ($0.999/min → 16650/M), NOT next-model's.
    assert "test-multi-row" in by_slug, "window too small — model lost"
    assert abs(by_slug["test-multi-row"].input_price_per_M - 16650.0) < 1.0, (
        f"window walked into next model: got {by_slug['test-multi-row'].input_price_per_M}"
    )


def test_openai_per_second_skip_logs_to_stderr(capsys) -> None:
    """Pass-8 regression: per-second prices skip silently — verify they now
    emit a stderr WARN line so operators see the filter in cron output."""
    html_fragment = '"model":[0,"hypothetical-per-sec"],"rows":[1,[[1,[[0,"x"],[0,1],[0,2],[0,"$0.00028 / second"]]]]]}'
    _load("openai").extract(html_fragment, "https://example.com/")
    captured = capsys.readouterr()
    assert "hypothetical-per-sec" in captured.err
    assert "WARN" in captured.err


def test_anthropic_output_lt_input_filter_logs_to_stderr(capsys) -> None:
    """Pass-8 regression: sanity-check filter (output <= input) now emits
    a stderr WARN line."""
    html = (
        r'\"children\":[\"Claude Mythos 5\"] '
        r'$$7.50 / MTok $$37.50 / MTok $$1.50 / MTok $$7.50 / MTok $$1.50 / MTok'
    )
    _load("anthropic").extract(html, "https://example.com/")
    captured = capsys.readouterr()
    assert "Mythos 5" in captured.err
    assert "WARN" in captured.err


# ============================================================
# subscription_monitor parser (Phase 3 deliverable, added 2026-06-30)
# ============================================================

def test_subscription_monitor_returns_empty_for_sub_only_html() -> None:
    """The canonical case: rendered HTML with only tier-card prices ($N/mo,
    $N/yr) returns an empty list = subscription-only confirmed."""
    html = '<html><body>Free $0/mo · Pro $99/mo · Enterprise $999/yr</body></html>'
    rows = _load("subscription_monitor").extract(html, "https://example.com/pricing")
    assert rows == []


def test_subscription_monitor_emits_alert_when_per_call_pattern_appears() -> None:
    """If a vendor flips from subscription to per-call API pricing, the
    monitor must detect it and emit an alert row that the orchestrator's
    unit-validator catches as `missing` (no DB row matches the alert slug)."""
    html = '<html><body>Pro $99/mo · NEW API: $5 / 1M tokens</body></html>'
    rows = _load("subscription_monitor").extract(html, "https://elevenlabs.io/pricing")
    assert len(rows) == 1
    (r,) = rows
    assert r.model_slug.endswith(":per-call-pricing-emergence-alert")
    assert "elevenlabs.io" in r.model_slug
    assert r.pricing_unit == "alert"
    assert "ALERT" in r.raw_price_text
    assert "1M tokens" in r.raw_price_text


def test_subscription_monitor_ignores_nextjs_framework_artifacts() -> None:
    """Next.js renders strings like `$undefined`, `$L15` in the page source —
    these are NOT prices. Must not false-positive."""
    html = (
        '<html><body>'
        '{"key":"$undefined","other":"$L15","x":"$3","y":"$1c"}'
        ' bare $5 button with no per-unit qualifier'
        '</body></html>'
    )
    rows = _load("subscription_monitor").extract(html, "https://example.com/")
    assert rows == []


def test_subscription_monitor_detects_per_minute_pricing() -> None:
    """Audio TTS vendors quote per-minute rates. If a sub-only vendor flips
    to per-minute API pricing, alert must fire."""
    html = '<html>Suno API: $0.05 / minute (new!)</html>'
    rows = _load("subscription_monitor").extract(html, "https://suno.com/pricing")
    assert len(rows) == 1
    assert "$0.05 / minute" in rows[0].raw_price_text


def test_subscription_monitor_detects_per_image_pricing() -> None:
    html = '<html>HeyGen API: $0.10 per image generated</html>'
    rows = _load("subscription_monitor").extract(html, "https://www.heygen.com/pricing")
    assert len(rows) == 1
    assert "image" in rows[0].raw_price_text.lower()


def test_subscription_monitor_rejects_dict_payload() -> None:
    import pytest
    with pytest.raises(TypeError):
        _load("subscription_monitor").extract({}, "https://example.com/")


def test_subscription_monitor_caps_at_3_hits_for_alert() -> None:
    """If 100 per-call patterns appear, we still emit only 1 alert row with
    the first 3 hits in raw_price_text. Bounded output."""
    html = '<html>' + (' $1 / 1M tokens') * 100 + '</html>'
    rows = _load("subscription_monitor").extract(html, "https://example.com/")
    assert len(rows) == 1
    # Alert raw text should contain at most 3 hit samples
    assert rows[0].raw_price_text.count("$1 / 1M tokens") <= 3
