"""Phase C, C13: the board shows the same burn and forecast the prompt line does.

The per-window cell's sub-line already reads "N% used · resets <when>". Where the posture has a
reading it gains the tick's own burn rate and whichever of the wall or the reset comes FIRST — the
same two facts, from the same file, as the `QUOTA:` line every agent sees. The board does not
re-derive them: two derivations of one number are two things to drift.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "quota_dashboard.py"


def _load():
    spec = importlib.util.spec_from_file_location("quota_dashboard_posture_probe", _SRC)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _posture(*, burn=0.6, verdict="wall_first", mtw=48.0, mtr=130.0, util=71.0):
    return {
        "schema": 1,
        "ts": 1.0,
        "active": {
            "slug": "mob",
            "windows": {
                "five_hour": {
                    "utilization": util,
                    "burn_per_min": burn,
                    "minutes_to_wall": mtw,
                    "minutes_to_reset": mtr,
                    "verdict": verdict,
                }
            },
        },
    }


def test_the_board_renders_burn_and_wall_vs_reset_from_the_posture():
    """C13 — the burn and the nearer of wall-or-reset, taken from the posture, not re-derived."""
    mod = _load()
    sub = mod._posture_sub(_posture(), "five_hour")
    assert sub == " · 0.60%/m, wall in ~48m", sub
    sub = mod._posture_sub(_posture(verdict="reset_first"), "five_hour")
    assert sub == " · 0.60%/m, reset in ~130m", sub


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"burn": None}, " · no burn yet"),
        ({"burn": float("nan")}, " · no burn yet"),
        ({"burn": True}, " · no burn yet"),
        ({"mtw": None}, " · 0.60%/m"),
        ({"mtw": float("inf")}, " · 0.60%/m"),
        ({"util": None}, ""),
    ],
)
def test_the_board_says_nothing_it_cannot_derive(kwargs, expected):
    """C13b — every arm of the escape: no burn yet, a burn with no usable horizon, no reading.

    `True` is in this list because `isinstance(True, int)` is True in Python, so a bool would
    otherwise render as a burn rate of 1.00%/m.
    """
    mod = _load()
    assert mod._posture_sub(_posture(**kwargs), "five_hour") == expected


def test_a_missing_or_malformed_posture_renders_nothing():
    """C13c — the board predates the posture and must render without one, forever."""
    mod = _load()
    for bad in (None, {}, [], "posture", {"active": None}, {"active": {"windows": None}}):
        assert mod._posture_sub(bad, "five_hour") == "", bad
    assert mod._posture_sub(_posture(), "fable") == "", "a window with no entry says nothing"


def test_only_the_active_account_gets_a_forecast():
    """C13d — a standby is not burning fleet quota, so a forecast for it is a number with nothing
    behind it. The row renderer gates on `is_active`."""
    mod = _load()
    src = _SRC.read_text(encoding="utf-8")
    assert src.count("_posture_sub(posture, 'five_hour') if is_active else ''") == 1
    assert src.count("_posture_sub(posture, 'seven_day') if is_active else ''") == 1
    assert src.count("_posture_sub(posture, 'fable') if is_active else ''") == 1
