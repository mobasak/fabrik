"""Behavior Contract — derive_cost three-number model (①/②/③). Fixtures only, no network."""

import datetime
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import derive_cost as dc  # noqa: E402


def _ratios(tmp_path):
    p = tmp_path / "ratios.json"
    p.write_text(
        json.dumps(
            {
                "claude-code/opus": {"in": 5.0, "out": 25.0},
                "claude-code/haiku": {"in": 1.0, "out": 5.0},
                "_cache": {"read": 0.1, "write_5m": 1.25, "write_1h": 2.0},
            }
        )
    )
    return p


def test_api_equiv_input_only(tmp_path):
    u = {"input_tokens": 1_000_000, "output_tokens": 0}
    assert dc.api_equiv(u, "claude-code/opus", _ratios(tmp_path)) == pytest.approx(5.0)


def test_api_equiv_cache_read(tmp_path):
    assert dc.api_equiv(
        {"cache_read_input_tokens": 1_000_000}, "claude-code/opus", _ratios(tmp_path)
    ) == pytest.approx(0.5)  # 1e6 * 5 * 0.1 / 1e6


def test_api_equiv_cache_write_defaults_5min(tmp_path):
    assert dc.api_equiv(
        {"cache_creation_input_tokens": 1_000_000}, "claude-code/opus", _ratios(tmp_path)
    ) == pytest.approx(6.25)  # 1e6 * 5 * 1.25 / 1e6


def test_api_equiv_unknown_model_raises(tmp_path):
    with pytest.raises(KeyError):
        dc.api_equiv({}, "claude-code/ghost", _ratios(tmp_path))


def test_amortized_cost_is_rate_times_total_tokens():
    usage = {
        "input_tokens": 9,
        "output_tokens": 142,
        "cache_read_input_tokens": 20215,
        "cache_creation_input_tokens": 26030,
    }
    expected = dc.amortized_rate() * sum(usage.values())
    assert dc.amortized_cost(usage) == pytest.approx(expected)


def test_amortized_cost_zero_usage_is_zero():
    assert dc.amortized_cost({}) == pytest.approx(0.0)


def test_env_float_falls_back_on_malformed_value():
    assert dc._env_float("NONEXISTENT_ENV_VAR_XYZ", 200.0) == pytest.approx(200.0)


def test_env_float_parses_real_override(monkeypatch):
    monkeypatch.setenv("NONEXISTENT_ENV_VAR_XYZ", "250")
    assert dc._env_float("NONEXISTENT_ENV_VAR_XYZ", 200.0) == pytest.approx(250.0)


def test_env_float_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("NONEXISTENT_ENV_VAR_XYZ", "garbage")
    assert dc._env_float("NONEXISTENT_ENV_VAR_XYZ", 200.0) == pytest.approx(200.0)


def _hist(tmp_path, day: str, tokens: dict):
    hist = tmp_path / "usage-history.json"
    hist.write_text(
        json.dumps({"version": 1, "days": {day: {"byModel": {"claude-opus-4-8": tokens}}}})
    )
    return hist


def _accounts(tmp_path, n: int):
    acc = tmp_path / "accounts"
    for i in range(n):
        (acc / f"acct{i}").mkdir(parents=True)
    return acc


def test_amortized_rate_from_fixture(tmp_path):
    # assert against the LIVE module constant, not a hardcoded 200.0 — it's frozen at import time from
    # CLAUDE_MAX_PRICE_USD (possibly already overridden in this process's env before the module loaded),
    # so a hardcoded literal would spuriously fail whenever an operator has that env var set.
    today = datetime.date.today().isoformat()  # inside the 30-day window regardless of run date
    hist = _hist(
        tmp_path, today, {"input": 100, "output": 50, "cacheRead": 1000, "cacheCreation": 200}
    )
    assert dc.amortized_rate(hist, _accounts(tmp_path, 3)) == pytest.approx(
        (dc._SUBSCRIPTION_USD_PER_ACCOUNT * 3) / 1350
    )  # $/token


def test_amortized_rate_ignores_days_outside_30d_window(tmp_path):
    old = (
        datetime.date.today() - datetime.timedelta(days=45)
    ).isoformat()  # gapped/stale → excluded
    hist = _hist(
        tmp_path, old, {"input": 100, "output": 50, "cacheRead": 1000, "cacheCreation": 200}
    )
    # only stale days present → window total 0 → fail-soft to the anchor, NOT $600/1350.
    assert dc.amortized_rate(hist, _accounts(tmp_path, 3)) == pytest.approx(9.3e-8)


def test_amortized_rate_empty_history_falls_back(tmp_path):
    hist = tmp_path / "usage-history.json"
    hist.write_text(json.dumps({"version": 1, "days": {}}))
    acc = tmp_path / "accounts"
    acc.mkdir()
    assert dc.amortized_rate(hist, acc) == pytest.approx(9.3e-8)


def test_quota_snapshot_from_fixture(tmp_path):
    sl = tmp_path / "statusline.json"
    sl.write_text(json.dumps({"rateLimits": {"sevenDay": {"usedPercent": 75}}}))
    assert dc.quota_snapshot(sl) == pytest.approx(75.0)


def test_quota_snapshot_missing_file(tmp_path):
    assert dc.quota_snapshot(tmp_path / "nope.json") == 0.0


def test_amortized_rate_ignores_non_date_keys(tmp_path):
    today = datetime.date.today().isoformat()
    hist = tmp_path / "usage-history.json"
    hist.write_text(
        json.dumps(
            {
                "version": 1,
                "days": {
                    # a non-ISO key sorts >= cutoff lexicographically — must be excluded, not summed.
                    "latest": {
                        "byModel": {
                            "m": {
                                "input": 9_999_999,
                                "output": 0,
                                "cacheRead": 0,
                                "cacheCreation": 0,
                            }
                        }
                    },
                    today: {
                        "byModel": {
                            "m": {
                                "input": 100,
                                "output": 50,
                                "cacheRead": 1000,
                                "cacheCreation": 200,
                            }
                        }
                    },
                },
            }
        )
    )
    # only today's 1350 tokens count; the 'latest' key is rejected (else the rate would be ~1000x off).
    # (live module constant, not a hardcoded 200.0 — see test_amortized_rate_from_fixture for why)
    assert dc.amortized_rate(hist, _accounts(tmp_path, 1)) == pytest.approx(
        dc._SUBSCRIPTION_USD_PER_ACCOUNT / 1350
    )


def test_amortized_rate_ignores_future_dated_keys(tmp_path):
    # a clock-skewed source could carry a future-dated key — k >= cutoff alone never excludes it,
    # so the window must also cap at today (k <= today_iso) or it would inflate the denominator.
    today = datetime.date.today().isoformat()
    future = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
    hist = tmp_path / "usage-history.json"
    hist.write_text(
        json.dumps(
            {
                "version": 1,
                "days": {
                    future: {
                        "byModel": {
                            "m": {"input": 9_999_999, "output": 0, "cacheRead": 0, "cacheCreation": 0}
                        }
                    },
                    today: {
                        "byModel": {
                            "m": {"input": 100, "output": 50, "cacheRead": 1000, "cacheCreation": 200}
                        }
                    },
                },
            }
        )
    )
    # only today's 1350 tokens count; the future-dated key is excluded (else the rate would be ~1000x off).
    assert dc.amortized_rate(hist, _accounts(tmp_path, 1)) == pytest.approx(
        dc._SUBSCRIPTION_USD_PER_ACCOUNT / 1350
    )


def test_amortized_rate_malformed_history_fails_soft(tmp_path):
    # non-object top level + a null byModel entry must fail soft, not crash (AttributeError guard).
    acc = _accounts(tmp_path, 1)
    for bad in (
        "[]",
        "5",
        '"x"',
        json.dumps({"days": {"2026-07-21": None}}),
        json.dumps({"days": {"2026-07-21": {"byModel": {"m": None}}}}),
    ):
        p = tmp_path / "h.json"
        p.write_text(bad)
        assert dc.amortized_rate(p, acc) == pytest.approx(9.3e-8)


def test_quota_snapshot_malformed_fails_soft(tmp_path):
    for bad in ("[]", "5", '"x"', json.dumps({"rateLimits": []})):
        p = tmp_path / "s.json"
        p.write_text(bad)
        assert dc.quota_snapshot(p) == 0.0
