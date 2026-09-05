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


def test_api_equiv_applies_the_per_model_cache_rate():
    """Cache reads are 10% of base input on every model EXCEPT Fable 5.1, which is 2.5%.

    The `claude-code/fable` family key covers both `claude-fable-5` (10%) and `claude-fable-5-1`
    (2.5%), so the exception is keyed on the full model id. An ambiguous bare alias gets the default.
    """
    u = _usage(cr=1_000_000)  # 1M cache-read, fable input = $10/M
    assert cpc.api_equiv(u, "claude-fable-5-1") == pytest.approx(0.25, abs=1e-6)  # 10 × 0.025
    assert cpc.api_equiv(u, "claude-fable-5") == pytest.approx(1.0, abs=1e-6)  # 10 × 0.1
    assert cpc.api_equiv(u, "claude-opus-5") == pytest.approx(0.5, abs=1e-6)  # 5 × 0.1, untouched


def test_the_override_survives_every_id_form_the_fleet_actually_carries():
    """Price lookup and cache lookup must share ONE key space.

    They did not: `_norm_model` matched the family by substring while the override matched the raw
    string exactly, so a vendor-qualified or dotted id got the right family PRICE and silently missed
    its cache rate — correct on the small term, 4× wrong on the dominant one. These are the real
    shapes: suffixed ids live in `usage-history.json`, `[1m]` is a live session id, and `anthropic/`
    is how the pool names the same model.
    """
    u = _usage(cr=1_000_000)
    for form in (
        "claude-fable-5-1",
        "anthropic/claude-fable-5-1",
        "claude-fable-5.1",
        "claude-fable-5-1[1m]",
        "claude-fable-5-1-20260815",
        "  CLAUDE-Fable-5-1  ",
    ):
        assert cpc.api_equiv(u, form) == pytest.approx(0.25, abs=1e-6), (
            f"{form!r} missed its override"
        )


def test_a_bare_tier_alias_stays_at_the_default_because_it_is_ambiguous():
    """`fable` names a tier running BOTH models, so it CANNOT resolve — the figure is an upper bound.

    This is the standing limit, asserted so nobody "fixes" it by moving 0.025 onto the family: that
    would 4× UNDERprice `claude-fable-5`, which is 76% of live fable-tier volume.
    """
    u = _usage(cr=1_000_000)
    assert cpc.api_equiv(u, "fable") == pytest.approx(1.0, abs=1e-6)
    assert cpc.api_equiv(u, "claude-code/fable") == pytest.approx(1.0, abs=1e-6)


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


def test_measure_rejects_a_payload_that_is_not_an_object():
    """The module's own documented entry point died with a bare AttributeError on a JSON list.

    `refresh()` was hardened against exactly this shape on the sidecar it READS; `measure()` — reached
    by `claude -p … --output-format json | python scripts/claude_p_cost.py` — was not, so an error
    envelope or a stream-style message list produced a traceback instead of `main()`'s documented
    exit 2.
    """
    for payload in ([1, 2, 3], "hello", 5, None, True):
        with pytest.raises(TypeError, match="expected a JSON object"):
            cpc.measure(payload, "opus")


def test_a_malformed_price_knob_does_not_kill_the_module_at_import():
    """`CLAUDE_MAX_PRICE_USD=abc` used to raise ValueError at IMPORT, before refresh() could run.

    Phase C puts `--refresh` on a 06:00 cron, where an import-time raise means the rate silently
    fossilises — the failure this whole plan exists to end. `derive_cost` has guarded this knob all
    along with `_env_float`; the vendored twin called bare `float()`.
    """
    import importlib.util
    import os

    # The defect is at MODULE SCOPE, so the guard has to be exercised by an IMPORT — asserting on
    # `_env_float` alone passes even when the constant is still built with a bare `float()`.
    previous = os.environ.get("CLAUDE_MAX_PRICE_USD")
    os.environ["CLAUDE_MAX_PRICE_USD"] = "not-a-number"
    try:
        spec = importlib.util.spec_from_file_location("cpc_bad_knob", _MOD)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # must NOT raise
        assert module._SUBSCRIPTION_USD_PER_ACCOUNT == 200.0
        os.environ["CLAUDE_MAX_PRICE_USD"] = "12.5"
        spec2 = importlib.util.spec_from_file_location("cpc_good_knob", _MOD)
        module2 = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(module2)
        assert module2._SUBSCRIPTION_USD_PER_ACCOUNT == 12.5  # a VALID override still applies
    finally:
        if previous is None:
            os.environ.pop("CLAUDE_MAX_PRICE_USD", None)
        else:
            os.environ["CLAUDE_MAX_PRICE_USD"] = previous
