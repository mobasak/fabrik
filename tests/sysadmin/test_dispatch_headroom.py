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
    assert r["seats"] == 3 and any("could not be identified" in x for x in r["reasons"])


def test_the_drain_band_comes_from_the_rotation_picture_not_a_second_constant():
    r = dh.budget(8, False, BOX_OK, dict(Q_OK, hottest_pct=70.0, drain_band=60.0))
    assert r["seats"] == 3 and any("drain band 60.0%" in x for x in r["reasons"])
    assert dh.budget(8, False, BOX_OK, dict(Q_OK, hottest_pct=70.0, drain_band=85.0))["seats"] == 17


def test_seats_live_in_sibling_sessions_are_subtracted_from_the_box(tmp_path):
    """TOCTOU on the box: three sessions reading the same free memory in one minute would each
    take all of it. The last round's `seats` of every fresh `running` record is subtracted."""
    now = 1_000_000.0
    (tmp_path / "a.json").write_text(
        json.dumps({"state": "running", "updated_ts": now - 60, "rounds": [{"seats": 5}]})
    )
    (tmp_path / "b.json").write_text(
        json.dumps(
            {"state": "running", "updated_ts": now - 60, "rounds": [{"seats": 2}, {"seats": 4}]}
        )
    )
    (tmp_path / "stale.json").write_text(  # abandoned 3 h ago — must not hold the box hostage
        json.dumps({"state": "running", "updated_ts": now - 3 * 3600, "rounds": [{"seats": 9}]})
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
    # the exact freshness edge: a record touched precisely SIBLING_FRESH_S ago still counts, one
    # second older does not (a `>=` slip here would drop a live sibling at the boundary)
    edge = tmp_path / "edge"
    edge.mkdir()
    (edge / "x.json").write_text(
        json.dumps(
            {"state": "running", "updated_ts": now - dh.SIBLING_FRESH_S, "rounds": [{"seats": 2}]}
        )
    )
    assert dh.siblings(now=now, runs_dir=edge)["seats"] == 2
    (edge / "x.json").write_text(
        json.dumps(
            {
                "state": "running",
                "updated_ts": now - dh.SIBLING_FRESH_S - 1,
                "rounds": [{"seats": 2}],
            }
        )
    )
    assert dh.siblings(now=now, runs_dir=edge)["seats"] == 0
    r = dh.budget(12, True, BOX_OK, Q_OK, s)  # box allows 12 heavy, minus 9 live elsewhere
    assert r["caps"]["box_cap"] == 3 and r["seats"] == 3
    assert any("minus 9 seat(s) live in 2 running record(s)" in x for x in r["reasons"])


def test_the_floor_is_three_even_for_a_one_unit_surface():
    r = dh.budget(1, False, BOX_OK, Q_OK)
    assert r["seats"] == dh.FLOOR == 3  # one unit: 1 sonnet + 1 haiku + 1 opus IS the floor
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
    assert r["seats"] == 17 and any("NO eligible standby" in x for x in r["reasons"])
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
    assert dh.cheapest_mix(6) == {"opus": 1, "sonnet": 5} and dh.cheapest_mix(1) == {"opus": 1}
    assert dh.cheapest_mix(0) == {}
    # role-legal, surface-aware: trivia on Haiku, risk on Opus (>=1), the rest Sonnet
    assert dh.cheapest_mix(6, trivial=2) == {"opus": 1, "haiku": 2, "sonnet": 3}
    assert dh.cheapest_mix(6, risky=3) == {"opus": 3, "sonnet": 3}
    assert dh.cheapest_mix(3, trivial=5, risky=0) == {"opus": 1, "haiku": 2}  # clamped to seats
    assert dh.cost(dh.cheapest_mix(12, trivial=11))["units"] == 16  # vs 27 for 1 opus + 11 sonnet
    assert dh.parse_mix("opus=1, sonnet=5") == {"opus": 1, "sonnet": 5}
    import pytest

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
    assert dh.trim(dh.full_mix(3, risky=3), 2) == {"opus": 2}
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
