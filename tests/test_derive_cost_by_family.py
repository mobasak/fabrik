# AFTER-EDIT: scripts/kilo-benchmarks/derive_cost.py
"""Behavior contract for derive_cost's per-family amortized rates (② split by model family).

Allocation rule under test: the pooled subscription $ is allocated across families by
API-equivalent VALUE (cache-aware list prices), so each family's amortized $/Mtok =
its effective list rate × one global discount ratio — naive token-share would price
every family identically and is exactly what these tests must reject.
"""

import importlib.util
import json
from pathlib import Path

import pytest

_MOD = (
    Path(__file__).resolve().parent.parent / "scripts" / "kilo-benchmarks" / "derive_cost.py"
)
_spec = importlib.util.spec_from_file_location("derive_cost", _MOD)
dc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dc)


def _history(tmp_path: Path, by_model: dict) -> Path:
    import datetime

    today = datetime.date.today().isoformat()
    p = tmp_path / "usage-history.json"
    p.write_text(json.dumps({"version": 1, "days": {today: {"byModel": by_model}}}))
    return p


def _accounts(tmp_path: Path, n: int) -> Path:
    d = tmp_path / "manager-accounts"
    for i in range(n):
        (d / f"acct-{i}").mkdir(parents=True)
    return d


def test_family_rates_scale_by_value_not_token_share(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "_SUBSCRIPTION_USD_PER_ACCOUNT", 200.0)
    hist = _history(
        tmp_path,
        {
            "claude-opus-4-8": {"input": 1_000_000, "output": 500_000},
            "claude-haiku-4-5-20251001": {"input": 2_000_000, "output": 1_000_000},
            "<synthetic>": {"input": 5_000_000, "output": 5_000_000},  # noise: excluded
        },
    )
    acc = _accounts(tmp_path, 2)
    rates = dc.amortized_by_family(usage_history_path=hist, accounts_dir=acc)
    assert set(rates) == {"opus", "haiku"}
    # value: opus 1×5 + 0.5×25 = $17.5 · haiku 2×1 + 1×5 = $7 → discount = 400/24.5
    # eff list $/M: opus 17.5/1.5 ≈ 11.667 · haiku 7/3 ≈ 2.333
    discount = 400.0 / 24.5
    assert rates["opus"] == pytest.approx(17.5 / 1.5 * discount, rel=1e-6)
    assert rates["haiku"] == pytest.approx(7.0 / 3.0 * discount, rel=1e-6)
    # the defining property: per-family rates preserve the effective-list ratio —
    # a token-share implementation would make these equal and MUST fail here
    assert rates["opus"] / rates["haiku"] == pytest.approx((17.5 / 1.5) / (7.0 / 3.0), rel=1e-6)


def test_cache_tokens_priced_cache_aware_in_family_value(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "_SUBSCRIPTION_USD_PER_ACCOUNT", 100.0)
    hist = _history(
        tmp_path,
        {"claude-fable-5": {"input": 0, "output": 0, "cacheRead": 10_000_000, "cacheCreation": 1_000_000}},
    )
    acc = _accounts(tmp_path, 1)
    rates = dc.amortized_by_family(usage_history_path=hist, accounts_dir=acc)
    # value = 10M×$10×0.1 + 1M×$10×1.25 = $10 + $12.5 = $22.5; raw = 11M
    # eff list = 22.5/11 $/M; discount = 100/22.5
    assert rates["fable"] == pytest.approx((22.5 / 11.0) * (100.0 / 22.5), rel=1e-6)


def test_synthetic_only_history_fails_soft_to_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "_SUBSCRIPTION_USD_PER_ACCOUNT", 200.0)
    hist = _history(tmp_path, {"<synthetic>": {"input": 1_000_000}})
    acc = _accounts(tmp_path, 1)
    assert dc.amortized_by_family(usage_history_path=hist, accounts_dir=acc) == {}


def test_sidecar_carries_by_family(tmp_path, monkeypatch):
    monkeypatch.setattr(dc, "_SUBSCRIPTION_USD_PER_ACCOUNT", 200.0)
    hist = _history(tmp_path, {"claude-sonnet-5": {"input": 1_000_000, "output": 1_000_000}})
    acc = _accounts(tmp_path, 1)
    monkeypatch.setattr(dc, "_USAGE_HISTORY", hist)
    monkeypatch.setattr(dc, "_MANAGER_ACCOUNTS", acc)
    out = tmp_path / "sidecar.json"
    data = dc.write_cost_sidecar(0.0, 1.0, path=out)
    assert "amortized_per_mtok_by_family" in data
    assert set(data["amortized_per_mtok_by_family"]) == {"sonnet"}
    assert json.loads(out.read_text())["amortized_per_mtok_by_family"]["sonnet"] > 0
