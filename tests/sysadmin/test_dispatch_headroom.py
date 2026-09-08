"""dispatch_headroom — the seat budget is min(units, cap, box, quota) with a floor of three.

The operator's full objective (2026-09-08): the maximum count of viable seats, no OOMs, the fastest
finish, affordable tokens, the right model per role. Five constraints cannot live in prose at
dispatch time; this script prints the number, and these tests pin its arithmetic with the probes
stubbed so no test reads the live box or the live fleet.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "dispatch_headroom", REPO / "scripts" / "sysadmin" / "dispatch_headroom.py"
)
assert _spec and _spec.loader
dh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dh)

BOX_OK = {"ok": True, "mem_available_gb": 25.0, "mem_total_gb": 47.0, "cores": 24, "load1": 1.0}
Q_OK = {"ok": True, "active": "a@x", "hottest_pct": 40.0, "eligible": 3, "hold": False}


def test_read_only_seats_follow_the_unit_count_up_to_the_cli_cap():
    assert dh.budget(6, False, BOX_OK, Q_OK)["seats"] == 6
    assert dh.budget(40, False, BOX_OK, Q_OK)["seats"] == dh.CONCURRENCY_CAP  # refused past it


def test_the_floor_is_three_even_for_a_one_unit_surface():
    r = dh.budget(1, False, BOX_OK, Q_OK)
    assert r["seats"] == dh.FLOOR == 3
    assert any("floor" in x for x in r["reasons"])


def test_heavy_seats_are_bounded_by_memory_and_cpu_never_the_unit_count_alone():
    tight = dict(BOX_OK, mem_available_gb=5.0)  # 5 GB / 2 GB per seat = 2 -> raised to the floor
    r = dh.budget(12, True, tight, Q_OK)
    assert r["caps"]["box_cap"] == 2 and r["seats"] == 3
    busy = dict(BOX_OK, load1=22.5)  # (24 - 22.5) / 1.5 = 1 core-share left
    assert dh.budget(12, True, busy, Q_OK)["caps"]["box_cap"] == 1
    roomy = dh.budget(12, True, BOX_OK, Q_OK)
    assert roomy["caps"]["box_cap"] == 12 and roomy["seats"] == 12


def test_quota_pressure_holds_the_round_at_the_floor_and_names_which_band_tripped():
    hot = dict(Q_OK, hottest_pct=91.0)
    r = dh.budget(8, False, BOX_OK, hot)
    assert r["seats"] == 3 and any("91.0%" in x for x in r["reasons"])
    thin = dict(Q_OK, eligible=1)
    r = dh.budget(8, False, BOX_OK, thin)
    assert r["seats"] == 3 and any("eligible" in x for x in r["reasons"])


def test_the_fleet_hold_dispatches_nothing():
    r = dh.budget(8, False, BOX_OK, dict(Q_OK, hold=True))
    assert r["seats"] == 0 and any("HOLD" in x for x in r["reasons"])


def test_a_failed_probe_falls_to_the_floor_and_says_why_never_a_silent_twenty():
    r = dh.budget(8, True, {"ok": False, "why": "box probe failed: x"}, {"ok": False, "why": "quota probe failed: y"})
    assert r["seats"] == 3
    assert any("box probe failed" in x for x in r["reasons"])
    assert any("quota probe failed" in x for x in r["reasons"])


def test_every_operator_named_model_has_exactly_one_role():
    assert set(dh.TIERS) == {"fable", "opus", "sonnet", "haiku"}
    assert all(v for v in dh.TIERS.values())


def test_json_output_carries_the_budget_and_both_probes(monkeypatch, capsys):
    monkeypatch.setattr(dh, "box", lambda: BOX_OK)
    monkeypatch.setattr(dh, "quota", lambda: Q_OK)
    assert dh.main(["--units", "5", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["seats"] == 5 and out["box"]["ok"] and out["quota"]["ok"] and "fable" in out["tiers"]
