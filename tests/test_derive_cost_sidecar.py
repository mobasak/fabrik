"""Behavior contract for the cost sidecar's PRODUCER — `scripts/claude_p_cost.py::refresh()`.

Named for the sidecar it writes (`claude_p_cost.json`), not for `derive_cost.py`: that module's
`write_cost_sidecar()` has zero call sites in this repo (its callers left with the catalog-engine
excision at `73bde59a`), and `refresh()` is the function that actually rewrites the hub's file.

Two behaviours are load-bearing here and neither had a guard before this file:

  1. **The window is emitted.** A rate with no window is indistinguishable from a fossil — the live
     file read $0.006310/M stamped 2026-08-10 while a recompute said $0.007386/M, 17% high and
     rendered as current. `refresh()` must publish the bounds and denominators it derived from.
  2. **`amortized_per_mtok_by_family` survives.** `refresh()` used to write three keys with a full
     `write_text`, silently destroying a key it never authored. Reproduced on disk before the fix.

Fixture dates are RELATIVE on purpose: `_live_amortized_per_mtok()` counts only days inside
`cutoff = today - _MONTHLY_DAYS` (`claude_p_cost.py`), so a hardcoded date drops out of the window
and reds this suite about a month after it is written.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "claude_p_cost.py"
_spec = importlib.util.spec_from_file_location("claude_p_cost_producer", _MOD)
cpc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpc)

_ACCOUNTS = 3
_SUBSCRIPTION = 200.0
_WINDOW_KEYS = ("window_start", "window_end", "accounts", "spend_usd", "tokens")


def _day(offset: int) -> str:
    """An ISO date `offset` days before today — always inside the 30-day window for small offsets."""
    return (datetime.date.today() - datetime.timedelta(days=offset)).isoformat()


def _history(days: dict[str, dict]) -> dict:
    return {"days": days}


def _model_usage(inp: int, out: int, cache_read: int = 0, cache_creation: int = 0) -> dict:
    return {"input": inp, "output": out, "cacheRead": cache_read, "cacheCreation": cache_creation}


@pytest.fixture
def rig(tmp_path, monkeypatch):
    """Point the producer at a fixture usage-history + accounts dir and a tmp output sidecar."""
    history = tmp_path / "usage-history.json"
    history.write_text(
        json.dumps(
            _history(
                {
                    _day(1): {"byModel": {"claude-opus-5": _model_usage(1_000, 2_000, 7_000)}},
                    _day(10): {"byModel": {"claude-fable-5": _model_usage(500, 500, 9_000)}},
                }
            )
        ),
        encoding="utf-8",
    )
    accounts = tmp_path / "manager-accounts"
    accounts.mkdir()
    for name in ("acct-a", "acct-b", "acct-c"):
        (accounts / name).mkdir()
    (accounts / ".hidden").mkdir()  # dotted entries are not accounts

    out = tmp_path / "claude_p_cost.json"
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", history)
    monkeypatch.setattr(cpc, "_MANAGER_ACCOUNTS", accounts)
    monkeypatch.setattr(cpc, "_SUBSCRIPTION_USD_PER_ACCOUNT", _SUBSCRIPTION)
    monkeypatch.setenv("CLAUDE_P_COST", str(out))
    return out


def test_refresh_emits_the_window_and_its_denominators(rig):
    """A reader can tell WHAT PERIOD, HOW MANY ACCOUNTS and HOW MUCH SPEND produced the rate."""
    data = cpc.refresh()

    for key in _WINDOW_KEYS:
        assert key in data, f"{key} missing — the rate still ships with no window"
        assert data[key] is not None, f"{key} is null on a window the producer could derive"

    assert data["window_start"] < data["window_end"], (data["window_start"], data["window_end"])
    assert data["tokens"] > 0
    assert data["accounts"] == _ACCOUNTS  # three real dirs; the dotted one is not an account
    assert data["spend_usd"] == pytest.approx(_SUBSCRIPTION * _ACCOUNTS)
    # the window is what the file says it is — same values land on disk
    assert json.loads(rig.read_text(encoding="utf-8"))["window_start"] == data["window_start"]


def test_the_published_rate_is_the_published_denominators(rig):
    """② is spend ÷ tokens over the SAME window the file publishes — not an unrelated number."""
    data = cpc.refresh()
    expected = data["spend_usd"] / data["tokens"] * 1_000_000.0
    assert data["amortized_per_mtok"] == pytest.approx(expected, rel=1e-9)


def test_refresh_preserves_the_by_family_split(rig):
    """THE DATA-LOSS GUARD: `refresh()` destroyed `amortized_per_mtok_by_family` on every run."""
    by_family = {"opus": 0.0054, "fable": 0.0107}
    rig.write_text(
        json.dumps(
            {
                "amortized_per_mtok": 1.0,
                "amortized_per_mtok_by_family": by_family,
                "quota_draw_pct": 4.2,
            }
        ),
        encoding="utf-8",
    )

    data = cpc.refresh()

    assert data["amortized_per_mtok_by_family"] == by_family, "the family split was destroyed"
    assert json.loads(rig.read_text(encoding="utf-8"))["amortized_per_mtok_by_family"] == by_family


def test_refresh_keeps_quota_draw_and_restamps_built_at(rig):
    """The pre-existing contract: ③ carries forward, ② and the stamp are rebuilt."""
    rig.write_text(
        json.dumps({"quota_draw_pct": 7.5, "built_at": "2000-01-01T00:00:00"}), encoding="utf-8"
    )

    data = cpc.refresh()

    assert data["quota_draw_pct"] == pytest.approx(7.5)
    assert data["built_at"] > "2000-01-01T00:00:00"
    assert data["amortized_per_mtok"] > 0


def test_window_is_null_when_the_rate_is_the_research_anchor(tmp_path, monkeypatch):
    """No fabricated denominators: the anchor was derived from no window, so the window is null.

    A zero-token history falls back to `_ANCHOR_USD_PER_TOKEN`. Publishing a window beside it would
    assert a derivation that never happened — the exact lie this reshape exists to end.
    """
    history = tmp_path / "usage-history.json"
    history.write_text(json.dumps(_history({})), encoding="utf-8")
    accounts = tmp_path / "manager-accounts"
    accounts.mkdir()
    out = tmp_path / "claude_p_cost.json"
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", history)
    monkeypatch.setattr(cpc, "_MANAGER_ACCOUNTS", accounts)
    monkeypatch.setenv("CLAUDE_P_COST", str(out))

    data = cpc.refresh()

    assert data["amortized_per_mtok"] == pytest.approx(cpc._ANCHOR_USD_PER_TOKEN * 1_000_000.0)
    for key in _WINDOW_KEYS:
        assert key in data, f"{key} must be present even when null — absence reads as an old file"
        assert data[key] is None, f"{key} = {data[key]!r} fabricates a window the anchor never had"
