"""dispatch_headroom — the seat budget is min(units x angles + the Opus seat(s), cap, box, quota), floor three.

The operator's full objective (2026-09-08): the maximum count of viable seats, no OOMs, the fastest
finish, affordable tokens, the right model per role. Five constraints cannot live in prose at
dispatch time; this script prints the number, and these tests pin its arithmetic with the probes
stubbed so no test reads the live box or the live fleet.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "dispatch_headroom", REPO / "scripts" / "sysadmin" / "dispatch_headroom.py"
)
assert _spec and _spec.loader
dh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dh)

BOX_OK = {"ok": True, "mem_available_gb": 25.0, "mem_total_gb": 47.0, "cores": 24, "load1": 1.0}
Q_OK_BAND = 85.0
Q_OK = {
    "ok": True,
    "active": "a@x",
    "hottest_pct": 40.0,
    "eligible": 3,
    "hold": False,
    "drain_band": 85.0,
}


def test_read_only_seats_follow_the_unit_count_up_to_the_cli_cap():
    assert dh.budget(6, False, BOX_OK, Q_OK)["seats"] == 13  # 6 units x 2 angles + 1 opus (D-191)
    assert dh.budget(40, False, BOX_OK, Q_OK)["seats"] == dh.CONCURRENCY_CAP  # refused past it


def test_read_only_seats_are_bounded_by_the_box_too_a_finder_still_runs_pytest():
    """Round-1 (authoritative seat): a "read-only" fabrik-reviewer ran `pytest tests/enforcement`
    through Bash at 1.19 GB max RSS — the label is self-declared, the tools load the box the same.
    1 GB planned per read-only seat, against min(MemAvailable, CommitLimit − Committed_AS)."""
    r = dh.budget(12, False, dict(BOX_OK, mem_available_gb=4.0), Q_OK)
    assert r["caps"]["box_cap"] == 4 and r["seats"] == 4
    r = dh.budget(12, False, dict(BOX_OK, commit_headroom_gb=2.5), Q_OK)
    assert r["caps"]["box_cap"] == 2 and r["seats"] == 2  # the commit limit binds first


def test_the_cli_concurrency_cap_is_hard_and_the_floor_never_raises_past_it(monkeypatch):
    """`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=2` — the runtime REFUSES the third seat ("Do not
    retry"); the first draft printed 3 anyway."""
    monkeypatch.setattr(dh, "CONCURRENCY_CAP", 2)
    r = dh.budget(6, False, BOX_OK, Q_OK)
    assert r["seats"] == 2 and any("concurrency_cap=2" in x for x in r["reasons"])


def test_an_unidentifiable_active_account_reads_as_hot_never_cool():
    """`claude_rotate.py` can return `active: None` on a broken pointer; `hottest_pct` is then None.
    The first draft's `is not None and ...` made that COOL and lifted the only affordability guard."""
    r = dh.budget(8, False, BOX_OK, dict(Q_OK, active=None, hottest_pct=None))
    assert r["seats"] == 3 and any("NO active account in the picture" in x for x in r["reasons"])
    # identified but unreadable is the OTHER fact (round-7 Opus finding: the old line said
    # "could not be identified ('a')" — naming the account it claimed not to have identified)
    r = dh.budget(8, False, BOX_OK, dict(Q_OK, hottest_pct=None))
    assert r["seats"] == 3 and any("has NO usable reading" in x for x in r["reasons"])


def test_the_drain_band_comes_from_the_rotation_picture_not_a_second_constant():
    r = dh.budget(8, False, BOX_OK, dict(Q_OK, hottest_pct=70.0, drain_band=60.0))
    assert r["seats"] == 3 and any("drain band (60.0%" in x for x in r["reasons"])
    assert dh.budget(8, False, BOX_OK, dict(Q_OK, hottest_pct=70.0, drain_band=85.0))["seats"] == 17


def test_seats_live_in_sibling_sessions_are_subtracted_from_the_box(tmp_path):
    """TOCTOU on the box: three sessions reading the same free memory in one minute would each
    take all of it. The last round's `seats` of every fresh `running` record is subtracted."""
    now = 1_000_000.0
    (tmp_path / "a.json").write_text(
        json.dumps(
            {"state": "running", "updated_ts": now - 60, "rounds": [{"seats": 5, "ts": now - 60}]}
        )
    )
    (tmp_path / "b.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now - 60,
                "rounds": [{"seats": 2}, {"seats": 4, "ts": now - 60}],
            }
        )
    )
    (tmp_path / "stale.json").write_text(  # abandoned 3 h ago — must not hold the box hostage
        json.dumps(
            {
                "state": "running",
                "updated_ts": now - 3 * 3600,
                "rounds": [{"seats": 9, "ts": now - 3 * 3600}],
            }
        )
    )
    (tmp_path / "done.json").write_text(json.dumps({"state": "done", "rounds": [{"seats": 9}]}))
    (tmp_path / "junk.json").write_text("{not json")
    # malformed FIELDS are skipped and named too — the first draft guarded only the JSON parse,
    # and a record with seats "abc" crashed the whole CLI (round-1 finding)
    (tmp_path / "bad.json").write_text(
        json.dumps({"state": "running", "updated_ts": now, "rounds": [{"seats": "abc"}]})
    )
    (tmp_path / "shape.json").write_text(
        json.dumps({"state": "running", "updated_ts": now, "rounds": ["not a dict"]})
    )
    s = dh.siblings(now=now, runs_dir=tmp_path)
    assert s["ok"] and s["seats"] == 9 and s["sessions"] == 2
    assert sorted(s["skipped"]) == ["bad.json", "junk.json", "shape.json"]
    # two shapes the narrower tuple let through (round-3 finding): rounds as an object (KeyError),
    # Infinity seats (OverflowError); and a NaN stamp must not read as forever-fresh
    (tmp_path / "obj.json").write_text(
        json.dumps({"state": "running", "updated_ts": now, "rounds": {"seats": 4}})
    )
    (tmp_path / "inf.json").write_text(
        f'{{"state": "running", "updated_ts": {now!r}, "rounds": [{{"seats": Infinity}}]}}'
    )
    (tmp_path / "nan.json").write_text(
        '{"state": "running", "updated_ts": NaN, "rounds": [{"seats": 7}]}'
    )
    s = dh.siblings(now=now, runs_dir=tmp_path)
    assert s["seats"] == 9 and sorted(s["skipped"]) == [
        "bad.json",
        "inf.json",
        "junk.json",
        "obj.json",
        "shape.json",
    ]
    # the DISPATCH stamp is the reservation: written BEFORE the seats go out, it counts while they
    # run; a record whose last round closed long ago but dispatched a minute ago reserves
    (tmp_path / "disp.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now - 3600,
                "rounds": [{"seats": 0}],
                "dispatch": {"ts": now - 60, "seats": 11},
            }
        )
    )
    assert dh.siblings(now=now, runs_dir=tmp_path)["seats"] == 20
    # the exact freshness edge: a record touched precisely SIBLING_FRESH_S ago still counts, one
    # second older does not (a `>=` slip here would drop a live sibling at the boundary)
    edge = tmp_path / "edge"
    edge.mkdir()
    (edge / "x.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now,
                "rounds": [{"seats": 2, "ts": now - dh.SIBLING_FRESH_S}],
            }
        )
    )
    assert dh.siblings(now=now, runs_dir=edge)["seats"] == 2
    (edge / "x.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now - dh.SIBLING_FRESH_S - 1,
                "rounds": [{"seats": 2, "ts": now - dh.SIBLING_FRESH_S - 1}],
            }
        )
    )
    assert dh.siblings(now=now, runs_dir=edge)["seats"] == 0
    r = dh.budget(12, True, BOX_OK, Q_OK, s)  # box allows 12 heavy, minus 9 live elsewhere
    assert r["caps"]["box_cap"] == 3 and r["seats"] == 3
    assert any(
        "minus 9 seat(s) dispatched < 25 min ago in 2 running record(s)" in x for x in r["reasons"]
    )


def test_the_floor_is_three_even_for_a_one_unit_surface():
    r = dh.budget(1, False, BOX_OK, Q_OK)
    assert r["seats"] == dh.FLOOR == 3  # one unit: 1 sonnet + 1 haiku + 1 opus IS the floor
    # the floor branch is REACHABLE for a real input: one judgement unit wants 2 (opus + sonnet)
    # and is raised to three seats on different angles (D-188)
    # a one-unit judgement surface has two angles; the floor is three REAL seats, so the mix pads
    # a second breadth reader — SEATS and the mix agree (round-3 finding: "SEATS: 3" over 2 seats)
    r = dh.budget(1, False, BOX_OK, Q_OK, mechanical=0)
    assert r["seats"] == 3 and r["caps"]["wanted"] == 3
    assert dh.full_mix(1, mechanical=0) == {"opus": 1, "sonnet": 2}
    assert sum(dh.trim(dh.full_mix(1, mechanical=0), 3).values()) == 3
    assert not any("raised to the floor" in x for x in r["reasons"])
    # no surface: no phantom floor — "SEATS: 3" beside a mix of {} recorded three seats that were
    # never dispatched (round-1 finding); zero units means zero seats and says why
    r = dh.budget(0, False, BOX_OK, Q_OK)
    assert r["seats"] == 0 and any("nothing to partition" in x for x in r["reasons"])
    # risky beyond the surface is clamped AND named, like every other clamp in the file
    r = dh.budget(2, False, BOX_OK, Q_OK, risky=5)
    assert r["caps"]["wanted"] == 6 and any("risky=5 exceeds units=2" in x for x in r["reasons"])


def test_heavy_seats_are_bounded_by_memory_and_cpu_never_the_unit_count_alone():
    # a HARD cap is never overridden by the floor — the first draft raised a box_cap of 2 (and even
    # 0) back to 3 heavy seats, the exact OOM this script exists to prevent (round-1 finding)
    tight = dict(BOX_OK, mem_available_gb=5.0)  # 5 GB / 2 GB per seat = 2
    r = dh.budget(12, True, tight, Q_OK)
    assert r["caps"]["box_cap"] == 2 and r["seats"] == 2
    assert any("HARD cap" in x and "box_cap=2" in x for x in r["reasons"])
    busy = dict(BOX_OK, load1=22.5)  # (24 - 22.5) / 1.5 = 1 core-share left
    assert dh.budget(12, True, busy, Q_OK)["seats"] == 1
    empty = dict(BOX_OK, mem_available_gb=0.0)
    r = dh.budget(12, True, empty, Q_OK)
    assert r["seats"] == 0 and any("never dispatch past a hard cap" in x for x in r["reasons"])
    assert dh.budget(12, True, dict(BOX_OK, mem_available_gb=25.0), Q_OK)["seats"] == 12
    roomy = dh.budget(12, True, BOX_OK, Q_OK)
    assert roomy["caps"]["box_cap"] == 12 and roomy["seats"] == 12


def test_quota_pressure_holds_the_round_at_the_floor_and_names_which_band_tripped():
    hot = dict(Q_OK, hottest_pct=91.0)
    r = dh.budget(8, False, BOX_OK, hot)
    assert r["seats"] == 3 and any("91.0%" in x for x in r["reasons"])
    # `eligible` counts STANDBYS (the active account is state=active): one fresh standby is a
    # fallback, so it must NOT collapse the round — the first draft's "< 2" did exactly that
    assert dh.budget(8, False, BOX_OK, dict(Q_OK, eligible=1))["seats"] == 17
    # NO standby at all is a WARNING, not a cap — the operator asked for the maximum, and a fresh
    # active account with no fallback still runs; the reason names the risk
    thin = dict(Q_OK, eligible=0)
    r = dh.budget(8, False, BOX_OK, thin)
    assert r["seats"] == 17 and any("NO standby account at all" in x for x in r["reasons"])
    # the exact boundaries, so a mutation of `>=` or `<` is caught
    assert dh.budget(8, False, BOX_OK, dict(Q_OK, hottest_pct=85.0))["seats"] == 3
    assert dh.budget(8, False, BOX_OK, dict(Q_OK, hottest_pct=84.9))["seats"] == 17


def test_the_fleet_hold_dispatches_nothing():
    r = dh.budget(8, False, BOX_OK, dict(Q_OK, hold=True))
    assert r["seats"] == 0 and any("HOLD" in x for x in r["reasons"])


def test_a_failed_probe_falls_to_the_floor_and_says_why_never_a_silent_twenty():
    r = dh.budget(
        8,
        True,
        {"ok": False, "why": "box probe failed: x"},
        {"ok": False, "why": "quota probe failed: y"},
    )
    assert r["seats"] == 3  # both unknown caps are held AT the floor, so the floor still reaches
    assert any("box probe failed" in x for x in r["reasons"])
    assert any("quota probe failed" in x for x in r["reasons"])


def test_price_multipliers_make_affordable_a_number():
    """Operator ruling D-190 (2026-09-08): haiku 1x, sonnet 2x, opus 5x, fable 10x. Cost is the sum
    of seats x multiplier in haiku-units; an unknown model is refused by name, never priced at 0."""
    assert dh.PRICE == {"haiku": 1, "sonnet": 2, "opus": 5, "fable": 10}
    assert dh.cost({"opus": 1, "sonnet": 5}) == {"units": 15, "parts": {"opus": 5, "sonnet": 10}}
    assert dh.cost({"fable": 1, "haiku": 3})["units"] == 13
    # a risky unit carries THREE angles (authoritative + breadth + mechanical) and costs 8
    assert dh.cost(dh.full_mix(1, risky=1))["units"] == 8

    with pytest.raises(ValueError, match="unknown model"):
        dh.cost({"gpt": 2})
    # a non-positive count is refused, never silently dropped from the sum (round-1 finding)
    with pytest.raises(ValueError, match="seat count must be >= 1"):
        dh.cost({"opus": -1, "sonnet": 5})
    with pytest.raises(ValueError, match="seat count must be >= 1"):
        dh.cost({"sonnet": 0})
    # the parser is strict: name=count, nothing implied
    for bad in ("opus", "opus=", "=3", "opus=1,sonnet=x"):
        with pytest.raises(ValueError, match="not name=count"):
            dh.parse_mix(bad)
    assert dh.parse_mix(" OPUS = 1 ,sonnet=2") == {"opus": 1, "sonnet": 2}


def test_a_malformed_mix_exits_2_with_a_message_never_a_traceback(monkeypatch, capsys):
    """Round-1 finding: `parse_mix` ran OUTSIDE the try that guards `cost`, so `--mix opus=1,sonnet=x`
    crashed with a traceback (exit 1) while `--mix gpt=2` was refused cleanly (exit 2)."""
    monkeypatch.setattr(dh, "box", lambda: BOX_OK)
    monkeypatch.setattr(dh, "quota", lambda: Q_OK)
    monkeypatch.setattr(
        dh, "siblings", lambda: {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    )
    assert dh.main(["--units", "6", "--mix", "opus=1,sonnet=x"]) == 2
    assert "not name=count" in capsys.readouterr().err
    assert dh.main(["--units", "6", "--mix", "opus=-1,sonnet=5"]) == 2
    assert "seat count must be >= 1" in capsys.readouterr().err
    # an empty mix (the HOLD path, seats 0) prints a sentence, not "for  ("
    monkeypatch.setattr(dh, "quota", lambda: dict(Q_OK, hold=True))
    assert dh.main(["--units", "6"]) == 0
    out = capsys.readouterr().out
    assert "COST: 0 haiku-units — nothing to dispatch" in out and "for  (" not in out


def test_the_box_is_the_ceiling_and_the_units_are_the_partition():
    """D-191 (the operator's third statement): before it, `units` capped the count — the box allowed
    23 and a 3-unit review dispatched 3. Now WANTED = one Sonnet + one Haiku per unit + the Opus
    authoritative seat(s), trimmed to the box cheapest angle first; every seat a distinct
    unit x angle brief."""
    assert dh.full_mix(3) == {"opus": 1, "sonnet": 3, "haiku": 3}
    assert dh.full_mix(6, risky=2) == {"opus": 2, "sonnet": 6, "haiku": 6}
    assert dh.full_mix(0) == {}
    assert dh.trim(dh.full_mix(3), 7) == {"opus": 1, "sonnet": 3, "haiku": 3}  # nothing to cut
    assert dh.trim(dh.full_mix(3), 5) == {"opus": 1, "sonnet": 3, "haiku": 1}  # haiku first
    assert dh.trim(dh.full_mix(3), 2) == {"opus": 1, "sonnet": 1}  # then sonnet, never below 1 opus
    # COVERAGE over cost (round-2 finding): the old order gave {opus: 2} here — two Opus seats on two
    # units (cost 10) with one unit read by nobody; {opus: 1, sonnet: 1} covers the same two for 7
    assert dh.trim(dh.full_mix(3, risky=3), 2) == {"opus": 1, "sonnet": 1}
    assert dh.trim(dh.full_mix(3, risky=3), 5) == {
        "opus": 2,
        "sonnet": 3,
    }  # extra opus before sonnet
    # the mechanical angle is GLOBAL: `mechanical` is the number of grep-able classes, 0 for a
    # judgement surface (grounding/adjudication) — no Haiku seat is manufactured there
    assert dh.full_mix(4, mechanical=2) == {"opus": 1, "sonnet": 4, "haiku": 2}
    assert dh.full_mix(4, mechanical=0) == {"opus": 1, "sonnet": 4}
    assert dh.budget(4, False, BOX_OK, Q_OK, mechanical=0)["caps"]["wanted"] == 5
    assert dh.trim(dh.full_mix(3), 0) == {}  # the HOLD path dispatches nothing
    r = dh.budget(3, False, BOX_OK, Q_OK)
    assert r["caps"]["wanted"] == 7 and r["seats"] == 7  # not 3
    r = dh.budget(3, True, dict(BOX_OK, mem_available_gb=8.0), Q_OK)  # box allows 4 heavy
    assert r["seats"] == 4 and any(
        "wanted 7" in x and "bound to 4 by box_cap" in x for x in r["reasons"]
    )


def test_every_operator_named_model_has_exactly_one_role():
    assert set(dh.TIERS) == {"fable", "opus", "sonnet", "haiku"}
    assert all(v for v in dh.TIERS.values())


def test_json_output_carries_the_budget_and_both_probes(monkeypatch, capsys):
    monkeypatch.setattr(dh, "box", lambda: BOX_OK)
    monkeypatch.setattr(dh, "quota", lambda: Q_OK)
    monkeypatch.setattr(
        dh, "siblings", lambda: {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    )
    assert dh.main(["--units", "5", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert (
        out["seats"] == 11 and out["box"]["ok"] and out["quota"]["ok"] and "fable" in out["tiers"]
    )
    assert out["caps"] == {"wanted": 11, "concurrency_cap": dh.CONCURRENCY_CAP, "box_cap": 23}
    assert out["reasons"] == [
        "box allows 23 read-only seats (mem 25.0GB/1.0GB=25, cores 24-load 1.0=23)"
    ]
    assert out["siblings"] == {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    assert (
        out["mix"] == {"opus": 1, "sonnet": 5, "haiku": 5} and out["cost"]["units"] == 20
    )  # 5+10+5
    assert out["adjudicator"] == {"model": "fable", "units": 10, "counted_in_seats": False}


def test_the_cost_line_an_agent_reads_is_graded_not_only_the_json(monkeypatch, capsys):
    """Round-1 (authoritative seat): deleting the whole human-readable COST block left every test
    green — the one thing a dispatching agent reads had no grader. And a mix whose seat count
    disagrees with the budget must say so: SEATS and COST describe the same round."""
    monkeypatch.setattr(dh, "box", lambda: BOX_OK)
    monkeypatch.setattr(dh, "quota", lambda: Q_OK)
    monkeypatch.setattr(
        dh, "siblings", lambda: {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    )
    assert dh.main(["--units", "5"]) == 0
    out = capsys.readouterr().out
    assert "SEATS: 11" in out
    assert (
        "COST: 20 haiku-units for 1 opus x5 + 5 sonnet x2 + 5 haiku x1 — the MAXIMUM useful mix"
        in out
    )
    assert "+ 10 for the orchestrator/adjudicator on fable x10" in out
    assert "RELATIVE and dimensionless" in out
    assert dh.main(["--units", "5", "--risky", "2"]) == 0
    assert (
        "COST: 25 haiku-units for 2 opus x5 + 5 sonnet x2 + 5 haiku x1" in capsys.readouterr().out
    )
    assert dh.main(["--units", "3", "--mix", "sonnet=99"]) == 0
    assert "mix has 99 seat(s) but the budget is 7" in capsys.readouterr().out


def test_siblings_reserve_but_never_starve_a_session_below_the_floor():
    """Round-2 finding: with the 30-minute window three hub sessions each at 13 seats left the third
    at box_cap=0 on a read-only review — colliding with D-188 and the Stop hook. A sibling's seats are
    reserved only while too young to show in the box probe, and never below the floor the box has."""
    sib = {"ok": True, "seats": 26, "sessions": 2, "skipped": []}
    r = dh.budget(6, False, BOX_OK, Q_OK, sib)
    assert r["caps"]["box_cap"] == 3 and r["seats"] == 3
    assert any("never below the floor of 3" in x for x in r["reasons"])
    assert dh.budget(6, False, BOX_OK, Q_OK, dict(sib, seats=13))["seats"] == 10
    assert dh.SIBLING_FRESH_S == 25 * 60
    # a box that is ITSELF below the floor keeps the reservation in full — three sessions must not
    # each claim a 2-seat box (round-3 finding)
    low = dict(BOX_OK, mem_available_gb=2.0)
    assert dh.budget(6, False, low, Q_OK, dict(sib, seats=20))["caps"]["box_cap"] == 0
    assert dh.budget(6, False, low, Q_OK)["caps"]["box_cap"] == 2


def test_the_cost_story_describes_the_mix_it_prints_never_the_per_unit_sentence(
    monkeypatch, capsys
):
    """Round-2 finding: "one Sonnet + one Haiku seat per unit" was printed beside a TRIMMED mix; an
    agent reading it literally dispatches past a hard cap."""
    monkeypatch.setattr(dh, "box", lambda: BOX_OK)
    monkeypatch.setattr(
        dh, "siblings", lambda: {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    )
    monkeypatch.setattr(dh, "quota", lambda: dict(Q_OK, hottest_pct=90.0))  # the floor binds
    assert dh.main(["--units", "5"]) == 0
    out = capsys.readouterr().out
    assert "SEATS: 3" in out and "TRIMMED from 11 wanted" in out
    assert "no Haiku seat left" in out and "2 unit(s) have NO seat at all this round" in out
    assert "one Sonnet breadth seat per unit" not in out
    monkeypatch.setattr(dh, "quota", lambda: Q_OK)
    assert dh.main(["--units", "16"]) == 0
    out = capsys.readouterr().out
    assert "SEATS: 20" in out and "TRIMMED from 33 wanted" in out
    assert "3 Haiku seat(s) left — each sweeps ONE grep-able class across every unit" in out
    assert dh.main(["--units", "2", "--mechanical", "0"]) == 0
    out = capsys.readouterr().out
    assert "SEATS: 3" in out and "no mechanical seat (--mechanical 0" in out
    assert dh.main(["--units", "3", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["box_caps"] == {"read_only": 23, "heavy": 12} and d["full_mix"] == d["mix"]
    assert d["floor"] == dh.FLOOR and d["box_caps_floored"] == {"read_only": False, "heavy": False}
    # the True case through main() (round 10: the wiring could be hardcoded False and stay green)
    monkeypatch.setattr(
        dh, "siblings", lambda: {"ok": True, "seats": 21, "sessions": 2, "skipped": []}
    )
    assert dh.main(["--units", "3", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["box_caps_floored"] == {"read_only": True, "heavy": True} and d["floor_granted"] == 1
    assert any("floor granted" in x for x in d["heavy_reasons"])  # the heavy half rides too
    assert dh.main(["--units", "0"]) == 0  # the phantom-floor path end to end (round-8 finding)
    out = capsys.readouterr().out
    assert "SEATS: 0" in out


def test_negative_counts_are_refused_and_the_angles_table_matches_the_mix(capsys):
    """A negative --mechanical was silently floored to 0 and the story then claimed the operator
    had declared a judgement surface (round-3 finding); `ANGLES` had no grader."""
    with pytest.raises(SystemExit) as e:
        dh.main(["--units", "4", "--mechanical", "-5"])
    assert e.value.code == 2 and "is not a count" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        dh.main(["--units", "4", "--risky", "-1"])
    assert set(dh.ANGLES.values()) <= set(dh.TIERS)
    assert set(dh.full_mix(3, risky=1)) == set(dh.ANGLES.values())


def test_the_trimmed_story_is_graded_for_judgement_surfaces_and_risky_units(monkeypatch, capsys):
    """Round-4 mutation finding: both halves of the F74 fix survived every test. A judgement surface
    trimmed to the floor must not be told its mechanical classes "wait"; an Opus seat on a risky unit
    counts as coverage."""
    monkeypatch.setattr(dh, "box", lambda: BOX_OK)
    monkeypatch.setattr(
        dh, "siblings", lambda: {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    )
    monkeypatch.setattr(dh, "quota", lambda: dict(Q_OK, hottest_pct=90.0))  # the floor binds
    assert dh.main(["--units", "5", "--risky", "2", "--mechanical", "0"]) == 0
    out = capsys.readouterr().out
    assert "TRIMMED from 7 wanted" in out and "mechanical classes wait" not in out
    assert "no Haiku seat" not in out
    monkeypatch.setattr(dh, "quota", lambda: Q_OK)
    monkeypatch.setattr(dh, "CONCURRENCY_CAP", 2)
    assert dh.main(["--units", "3", "--risky", "3"]) == 0
    out = capsys.readouterr().out
    # a trimmed round puts the Opus seat on a risky unit WITHOUT a Sonnet seat: one of three unread
    assert "1 unit(s) have NO seat at all" in out


def test_a_dispatch_stamp_without_ts_is_named_and_a_double_dash_count_is_refused(tmp_path):
    now = 1_000_000.0
    (tmp_path / "d.json").write_text(
        json.dumps({"state": "running", "updated_ts": now, "rounds": [], "dispatch": {"seats": 5}})
    )
    s = dh.siblings(now=now, runs_dir=tmp_path)
    assert s["seats"] == 0 and s["skipped"] == ["d.json"]
    with pytest.raises(ValueError, match="not name=count"):
        dh.parse_mix("opus=--5")


def test_siblings_exclude_the_callers_own_record_and_prefer_the_dispatch_stamp(
    tmp_path, monkeypatch
):
    """Round-4/5 findings: a session subtracted its OWN stamp on round N+1; the dispatch stamp (written
    before the seats went out, released when they returned) is the reservation and a round row is only
    the fallback for a record without one, dated by the round's own stamp; `dispatch --seats 0` reserves
    nothing."""
    now = 1_000_000.0
    (tmp_path / "me.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now,
                "rounds": [{"seats": 13, "ts": now - 30}],
                "dispatch": {"ts": now - 60, "seats": 13, "round": 1},
            }
        )
    )
    (tmp_path / "round-only.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now - 7200,
                "rounds": [{"seats": 10, "ts": now - 60}],
            }
        )
    )
    (tmp_path / "zero-stamp.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now - 60,
                "rounds": [{"seats": 12, "ts": now - 60}],
                "dispatch": {"ts": now - 30, "seats": 0, "round": 1},
            }
        )
    )
    (tmp_path / "stale-stamp.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now,
                "rounds": [],
                "dispatch": {"ts": now - 2000, "seats": 20, "round": 0},
            }
        )
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="me")
    assert s["seats"] == 10 and s["sessions"] == 1 and s["excluded_own"] is True
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "me")
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    assert dh.siblings(now=now, runs_dir=tmp_path)["seats"] == 10  # the default is this session
    assert dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="")["seats"] == 23


def test_the_pad_and_the_coverage_gap_are_told_honestly(monkeypatch, capsys):
    """Round-4 findings: two Sonnet seats on one unit were described as "one per unit"; an Opus seat
    on a risky unit that keeps its Sonnet seat was counted as covering a second unit."""
    monkeypatch.setattr(dh, "box", lambda: BOX_OK)
    monkeypatch.setattr(
        dh, "siblings", lambda: {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    )
    monkeypatch.setattr(dh, "quota", lambda: Q_OK)
    assert dh.main(["--units", "1", "--mechanical", "0"]) == 0
    out = capsys.readouterr().out
    assert "SECOND breadth reader" in out and "duplicate brief" in out
    monkeypatch.setattr(dh, "CONCURRENCY_CAP", 2)
    assert dh.main(["--units", "2", "--risky", "2"]) == 0
    out = capsys.readouterr().out
    assert "NO seat at all" not in out  # opus on one risky unit, sonnet on the other: both read
    with pytest.raises(SystemExit):
        dh.main(["--units", "-3"])


def test_own_session_id_is_command_runs_own_ladder_including_the_nosession_key(monkeypatch):
    """Round-5 finding: an id-less shell made `own_session_id()` "" and the own record
    (`nosession-<repo>.json`) was subtracted again. The name comes from command_run.py itself."""
    import importlib.util as iu

    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    spec = iu.spec_from_file_location("command_run", REPO / "scripts" / "command_run.py")
    cr = iu.module_from_spec(spec)
    spec.loader.exec_module(cr)
    assert dh.own_session_id()[0] == cr._session_id(None) and dh.own_session_id()[0].startswith(
        "nosession-"
    )
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc-123")
    assert dh.own_session_id() == ("abc-123", "command_run")


def test_a_malformed_quota_picture_falls_to_the_floor_never_a_traceback(monkeypatch):
    """Round-5 finding: quota() caught four exception classes; a picture whose account row is a
    string raised AttributeError through main()."""

    class _P:
        stdout = json.dumps({"picture": {"accounts": ["not-a-dict"], "active": None}})
        returncode = 0

    monkeypatch.setattr(dh.subprocess, "run", lambda *a, **k: _P())
    q = dh.quota()
    assert q["ok"] is False and "quota probe failed" in q["why"]
    assert dh.budget(4, False, BOX_OK, q)["seats"] == 3


def test_the_round_fallback_is_dated_by_the_rounds_own_stamp_and_unrecorded_siblings_are_named(
    tmp_path,
):
    """Round-5 findings: `updated_ts` is a generic last-touch — a bare `step` re-reserved a two-hour-old
    round; a running record with no seat figure at all was silently 0 and absent from the count; a raw
    sid with a dot never matched its `_safe_sid` file stem."""
    now = 1_000_000.0
    (tmp_path / "touched.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now - 10,
                "rounds": [{"seats": 13, "ts": now - 7200}],
            }
        )
    )
    (tmp_path / "fresh-round.json").write_text(
        json.dumps(
            {"state": "running", "updated_ts": now - 7200, "rounds": [{"seats": 4, "ts": now - 60}]}
        )
    )
    (tmp_path / "silent.json").write_text(
        json.dumps({"state": "running", "updated_ts": now, "rounds": []})
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="nobody")
    assert s["seats"] == 4 and s["sessions"] == 1 and s["unrecorded"] == 1
    r = dh.budget(6, False, BOX_OK, Q_OK, s)
    assert any("1 running sibling session(s) carry NO seat figure" in x for x in r["reasons"])
    # the common case — a sibling that has just started, nothing else live — must be named too
    # (the clause was nested under `taken`, round-6 finding); an EMPTY stamp is unrecorded, not 0
    (tmp_path / "touched.json").unlink()
    (tmp_path / "fresh-round.json").unlink()
    (tmp_path / "silent.json").write_text(
        json.dumps({"state": "running", "updated_ts": now, "rounds": [], "dispatch": {}})
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="nobody")
    assert s["seats"] == 0 and s["unrecorded"] == 1
    r = dh.budget(6, False, BOX_OK, Q_OK, s)
    assert any("1 running sibling session(s) carry NO seat figure" in x for x in r["reasons"])
    env_reasons = dh.budget(6, False, BOX_OK, Q_OK, dict(s, own_source="env"))["reasons"]
    assert any("own-session id came from the env" in x for x in env_reasons)
    # a sid that is not filename-safe still finds its own record
    import importlib.util as iu

    spec = iu.spec_from_file_location("command_run", REPO / "scripts" / "command_run.py")
    cr = iu.module_from_spec(spec)
    spec.loader.exec_module(cr)
    stem = cr._safe_sid("sess.one")
    (tmp_path / f"{stem}.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now,
                "rounds": [],
                "dispatch": {"ts": now, "seats": 9, "round": 0},
            }
        )
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="sess.one")
    assert s["excluded_own"] is True and s["seats"] == 0  # its own 9 excluded; nothing else fresh


def test_a_none_reading_is_unknown_never_cool_and_a_lone_opus_seat_counts_as_coverage(
    monkeypatch, capsys
):
    class _P:
        stdout = json.dumps(
            {
                "picture": {
                    "accounts": [
                        {"state": "active", "email": "a@x", "session_pct": None, "weekly_pct": None}
                    ],
                    "active": "a@x",
                    "hold": False,
                    "thresholds": {"drain_band": 85.0},
                }
            }
        )
        returncode = 0

    monkeypatch.setattr(dh.subprocess, "run", lambda *a, **k: _P())
    q = dh.quota()
    assert q["ok"] is True and q["hottest_pct"] is None
    assert dh.budget(8, False, BOX_OK, q)["seats"] == 3  # unknown reads as HOT
    monkeypatch.setattr(dh, "box", lambda: BOX_OK)
    monkeypatch.setattr(
        dh, "siblings", lambda: {"ok": True, "seats": 0, "sessions": 0, "skipped": []}
    )
    monkeypatch.setattr(dh, "quota", lambda: Q_OK)
    monkeypatch.setattr(dh, "CONCURRENCY_CAP", 1)
    assert dh.main(["--units", "3"]) == 0
    assert (
        "2 unit(s) have NO seat at all" in capsys.readouterr().out
    )  # the lone Opus seat reads one


def test_a_standby_in_the_drain_band_is_no_fallback_and_a_release_marker_is_a_known_zero(
    monkeypatch, tmp_path
):
    """Round-6 findings: the only standby sat AT the band and `eligible` still read 1; the picture
    publishes `in_drain_band` per row — read it. A round row at the CLI default (`--seats` 0 = not
    recorded) is unrecorded; a RELEASE marker (seats 0, released) is a known zero."""

    class _P:
        stdout = json.dumps(
            {
                "picture": {
                    "accounts": [
                        {
                            "state": "active",
                            "email": "a@x",
                            "session_pct": 17.0,
                            "weekly_pct": 56.0,
                            "in_drain_band": False,
                        },
                        {
                            "state": "eligible",
                            "email": "b@x",
                            "session_pct": 85.0,
                            "weekly_pct": 17.0,
                            "in_drain_band": True,
                        },
                    ],
                    "active": "a@x",
                    "hold": False,
                    "thresholds": {"drain_band": 85.0},
                }
            }
        )
        returncode = 0

    monkeypatch.setattr(dh.subprocess, "run", lambda *a, **k: _P())
    q = dh.quota()
    assert q["eligible"] == 0 and q["eligible_raw"] == 1 and q["active_in_band"] is False
    r = dh.budget(
        6, False, BOX_OK, q
    )  # no COOL standby: the caution fires (it stayed silent before)
    assert r["seats"] == 13 and any("0 of 1 standby(s) are COOL" in x for x in r["reasons"])
    hot = dict(q, active_in_band=True, eligible=3)
    assert dh.budget(6, False, BOX_OK, hot)["seats"] == 3  # the picture's own predicate, not ours
    now = 1_000_000.0
    (tmp_path / "zero-round.json").write_text(
        json.dumps({"state": "running", "updated_ts": now, "rounds": [{"seats": 0, "ts": now}]})
    )
    (tmp_path / "released.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now,
                "rounds": [{"seats": 0, "ts": now}],  # the shape `round` really leaves behind
                "dispatch": {"ts": now, "seats": 0, "round": 1, "released": True},
            }
        )
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="nobody")
    assert (
        s["seats"] == 0 and s["unrecorded"] == 1
    )  # the zero-round is unrecorded; the release is a known zero


def test_round7_shapes_a_release_beside_a_count_a_standby_without_a_grade_and_the_own_id_source(
    tmp_path, monkeypatch
):
    """Round-7 findings: (1) `released: true, seats: 5` (a hand-edited record) counted 5 in flight
    — the release wins; (2) a standby row WITHOUT `in_drain_band` was counted cool (`not None`) —
    an ungraded standby is unknown, never a fallback; (3) the own-id source was a module global
    that ratcheted to "env" on one failed import and never reset — it is a return value now."""
    now = 1_000_000.0
    (tmp_path / "contradictory.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now,
                "rounds": [{"seats": 5, "ts": now}],
                "dispatch": {"ts": now, "seats": 5, "round": 1, "released": True},
            }
        )
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="nobody")
    assert s["seats"] == 0 and s["unrecorded"] == 0 and s["sessions"] == 0  # no seat in flight
    pic = {
        "hold": False,
        "thresholds": {"drain_band": 85.0},
        "accounts": [
            {"email": "a@x", "state": "active", "session_pct": 10, "weekly_pct": 10},
            {"email": "b@x", "state": "eligible"},  # no grade at all
            {"email": "c@x", "state": "eligible", "in_drain_band": False},
        ],
    }

    class _P:
        stdout = json.dumps({"picture": pic})

    monkeypatch.setattr(dh.subprocess, "run", lambda *a, **k: _P())
    q = dh.quota()
    assert q["eligible_raw"] == 2 and q["eligible"] == 1  # the ungraded standby is not cool

    def boom():
        raise ImportError("no command_run here")

    monkeypatch.setattr(dh, "_import_command_run", boom)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-sid")
    assert dh.own_session_id() == ("env-sid", "env")
    assert dh.siblings(now=now, runs_dir=tmp_path)["own_source"] == "env"
    monkeypatch.undo()
    sid, src = dh.own_session_id()
    assert src == "command_run"  # a later success is not poisoned by the earlier failure


def test_a_parked_parent_frame_keeps_its_reservation_and_the_two_no_standby_facts_differ(
    tmp_path, monkeypatch
):
    """Round-7 Opus findings: (1) a nested `start` parks the parent on `stack` and its live stamp
    vanished from `siblings()` — /fabrik-execute-plan nesting /fabrik-review at a phase boundary
    hid 7 running seats; every frame is read now. (2) "NO eligible standby" printed the same words
    whether no standby EXISTS or the only one is merely warm — `--status` named a flip target
    while this said none; the two facts print differently. (3) an active account with no usable
    reading was reported as "could not be identified" — it was identified, it had no reading."""
    now = 1_000_000.0
    (tmp_path / "nested.json").write_text(
        json.dumps(
            {
                "state": "running",
                "command": "fabrik-review",
                "updated_ts": now,
                "rounds": [],
                "stack": [
                    {
                        "command": "fabrik-execute-plan",
                        "rounds": [],
                        "dispatch": {"ts": now, "seats": 7, "round": 0},
                    }
                ],
            }
        )
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="nobody")
    # the stamped parent + an unstamped child is a RECORDED session (round 9: it wore a
    # permanent LOWER-bound caveat in the ordinary execute-plan → review shape)
    assert s["seats"] == 7 and s["sessions"] == 1 and s["unrecorded"] == 0
    # round 9: one malformed NESTED frame must not drop the record's live parent reservation
    # (10 seats vanished in the over-dispatch direction); the bad frame is named `<file>#<n>`,
    # a non-dict stack entry too, and `unrecorded` is a SESSION count — one per record
    (tmp_path / "combo.json").write_text(
        json.dumps(
            {
                "state": "running",
                "rounds": [],
                "dispatch": {"ts": now, "seats": 10, "round": 0},
                "stack": ["not-a-frame", {"rounds": [], "dispatch": {"ts": now, "seats": -3}}],
            }
        )
    )
    (tmp_path / "two-empty-frames.json").write_text(
        json.dumps({"state": "running", "rounds": [], "stack": [{"rounds": []}]})
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="nobody")
    assert s["seats"] == 17 and s["sessions"] == 2  # 7 (parked parent) + 10 (combo's parent)
    assert sorted(s["skipped"]) == ["combo.json#1", "combo.json#2"]
    # a `stack` that is not a list is NAMED (round 10) — it was silently read as absent
    (tmp_path / "dict-stack.json").write_text(
        json.dumps(
            {
                "state": "running",
                "rounds": [],
                "dispatch": {"ts": now, "seats": 2},
                "stack": {"x": 1},
            }
        )
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="nobody")
    assert "dict-stack.json#stack" in s["skipped"] and s["seats"] == 19
    (tmp_path / "dict-stack.json").unlink()
    assert s["unrecorded"] == 1  # two-empty-frames only, once — nested.json carries a figure
    (tmp_path / "combo.json").unlink()
    (tmp_path / "two-empty-frames.json").unlink()
    # a NEGATIVE seat count is a malformed record — named as skipped, never silently ignored
    (tmp_path / "negative.json").write_text(
        json.dumps({"state": "running", "rounds": [], "dispatch": {"ts": now, "seats": -5}})
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="nobody")
    assert s["skipped"] == ["negative.json"] and s["seats"] == 7
    # the floor past the remainder is bounded and SAID (round-8 finding)
    r = dh.budget(6, False, BOX_OK, Q_OK, {"ok": True, "seats": 21, "unrecorded": 0})
    assert r["caps"]["box_cap"] == dh.FLOOR and r["floor_granted"] == 1
    assert any("floor granted: 1 seat(s) past what the box has left" in x for x in r["reasons"])
    # an honest remainder that equals the floor is NOT the floor (round-9 Opus finding)
    r = dh.budget(6, False, BOX_OK, Q_OK, {"ok": True, "seats": 20, "unrecorded": 0})
    assert r["caps"]["box_cap"] == 3 and r["floor_granted"] == 0
    # the guarantee is stated only where it holds: a box with no room says no "never below"
    low = dh.budget(
        6,
        True,
        {"ok": True, "mem_available_gb": 3.0, "cores": 16, "load1": 1.0},
        Q_OK,
        {"ok": True, "seats": 14, "unrecorded": 0},
    )
    assert low["caps"]["box_cap"] == 0
    assert not any("never below the floor" in x for x in low["reasons"])
    # an unreadable sibling record is SAID, in the over-dispatch direction (round-8 Opus)
    r = dh.budget(6, False, BOX_OK, Q_OK, {"ok": True, "seats": 0, "skipped": ["sib.json"]})
    assert any(
        "1 sibling record(s) carry 1 unreadable frame(s) (sib.json) — the seats those frames" in x
        for x in r["reasons"]
    )
    # frames vs records (round-10 Opus): three bad frames of ONE record are one record
    r = dh.budget(
        6,
        False,
        BOX_OK,
        Q_OK,
        {"ok": True, "seats": 6, "skipped": ["one.json#1", "one.json#2", "one.json#3"]},
    )
    assert any("1 sibling record(s) carry 3 unreadable frame(s)" in x for x in r["reasons"])
    # a RELEASE marker without a `seats` key is still a known zero (round-10 Opus)
    (tmp_path / "released-no-seats.json").write_text(
        json.dumps(
            {
                "state": "running",
                "rounds": [{"n": 1, "seats": 9, "ts": now}],
                "dispatch": {"ts": now, "released": True, "round": 1},
            }
        )
    )
    s = dh.siblings(now=now, runs_dir=tmp_path, exclude_sid="nobody")
    assert s["seats"] == 7 and s["unrecorded"] == 0
    (tmp_path / "released-no-seats.json").unlink()
    warm = dict(Q_OK, eligible=0, eligible_raw=2)
    r = dh.budget(6, False, BOX_OK, warm)
    assert any("0 of 2 standby(s) are COOL" in x for x in r["reasons"])
    assert not any("NO standby account at all" in x for x in r["reasons"])
    none_at_all = dict(Q_OK, eligible=0, eligible_raw=0)
    assert any(
        "NO standby account at all" in x
        for x in dh.budget(6, False, BOX_OK, none_at_all)["reasons"]
    )
    no_active = dict(Q_OK, active=None, hottest_pct=None)
    assert any(
        "NO active account in the picture" in x
        for x in dh.budget(6, False, BOX_OK, no_active)["reasons"]
    )
