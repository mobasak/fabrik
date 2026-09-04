"""Behavior contract for scripts/claude_p_cost.py — per-call claude -p cost (① api-equivalent + ② real).

Covers the load-bearing behaviors: per-model ① pricing, cache-awareness, ② = tokens × amortized rate,
model-name normalization, unknown-model raise, and fail-soft when the amortized sidecar is absent.
"""

import importlib.util
import json
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "claude_p_cost.py"
_spec = importlib.util.spec_from_file_location("claude_p_cost", _MOD)
cpc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpc)


def _usage(i=0, o=0, cr=0, cc=0):
    return {
        "input_tokens": i,
        "output_tokens": o,
        "cache_read_input_tokens": cr,
        "cache_creation_input_tokens": cc,
    }


def test_api_equiv_opus_matches_list_price():
    # 1.3M in × $5 + 0.5M out × $25 = $6.50 + $12.50 = $19.00 (no cache)
    assert cpc.api_equiv(_usage(1_300_000, 500_000), "opus") == pytest.approx(19.0, abs=1e-6)


def test_api_equiv_per_model_spread():
    u = _usage(1_300_000, 500_000)
    assert cpc.api_equiv(u, "haiku") == pytest.approx(3.8, abs=1e-6)  # 1.3×1 + 0.5×5
    assert cpc.api_equiv(u, "sonnet") == pytest.approx(7.6, abs=1e-6)  # 1.3×2 + 0.5×10
    assert cpc.api_equiv(u, "fable") == pytest.approx(38.0, abs=1e-6)  # 1.3×10 + 0.5×50


def test_api_equiv_is_cache_aware():
    # 1M cache-read priced at 0.1× input; 1M cache-write at 1.25× input (opus in = $5/M)
    read_only = cpc.api_equiv(_usage(cr=1_000_000), "opus")
    write_only = cpc.api_equiv(_usage(cc=1_000_000), "opus")
    assert read_only == pytest.approx(5.0 * 0.1, abs=1e-6)  # $0.50
    assert write_only == pytest.approx(5.0 * 1.25, abs=1e-6)  # $6.25


def test_norm_model_accepts_three_forms():
    for form in ("opus", "claude-code/opus", "claude-opus-5", "OPUS"):
        assert cpc._norm_model(form) == "claude-code/opus"


def test_api_equiv_raises_on_unpriced_model():
    with pytest.raises(KeyError):
        cpc.api_equiv(_usage(100), "gpt-4o")


def test_real_usd_is_tokens_times_amortized_rate():
    u = _usage(1_300_000, 500_000)  # 1.8M total
    rate = cpc.cached_amortized_per_mtok()
    assert rate > 0
    assert cpc.real_usd(u) == pytest.approx(1_800_000 * rate / 1_000_000.0, rel=1e-9)


def test_cached_rate_failsoft_to_anchor_when_sidecar_missing(monkeypatch, tmp_path):
    # point the sidecar path at a nonexistent file → fail-soft to the $0.093/M research anchor
    monkeypatch.setenv("CLAUDE_P_COST", str(tmp_path / "nope.json"))
    assert cpc.cached_amortized_per_mtok() == pytest.approx(0.093, abs=1e-9)


def test_measure_returns_full_shape_from_cli_json():
    cli = {
        "result": "…",
        "total_cost_usd": 19.0,
        "usage": _usage(1_300_000, 500_000),
    }
    out = cpc.measure(cli, "opus")
    assert out["model"] == "claude-code/opus"
    assert out["tokens"]["total"] == 1_800_000
    assert out["api_equiv_usd"] == pytest.approx(19.0, abs=1e-6)
    assert out["cli_total_cost_usd"] == 19.0
    assert out["real_usd"] > 0
    # round-trips as JSON (the CLI prints this)
    json.dumps(out)


def test_measure_accepts_bare_usage_block():
    out = cpc.measure(_usage(1_000_000, 0), "haiku")  # no top-level usage key → treat obj as usage
    assert out["tokens"]["input_tokens"] == 1_000_000
    assert out["api_equiv_usd"] == pytest.approx(1.0, abs=1e-6)  # 1M in × $1/M haiku
