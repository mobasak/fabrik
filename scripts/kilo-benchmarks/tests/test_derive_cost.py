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
    today = datetime.date.today().isoformat()  # inside the 30-day window regardless of run date
    hist = _hist(
        tmp_path, today, {"input": 100, "output": 50, "cacheRead": 1000, "cacheCreation": 200}
    )
    assert dc.amortized_rate(hist, _accounts(tmp_path, 3)) == pytest.approx(
        (200.0 * 3) / 1350
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
                    "latest": {"byModel": {"m": {"input": 9_999_999, "output": 0, "cacheRead": 0, "cacheCreation": 0}}},
                    today: {"byModel": {"m": {"input": 100, "output": 50, "cacheRead": 1000, "cacheCreation": 200}}},
                },
            }
        )
    )
    # only today's 1350 tokens count; the 'latest' key is rejected (else the rate would be ~1000x off).
    assert dc.amortized_rate(hist, _accounts(tmp_path, 1)) == pytest.approx(200.0 / 1350)


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
