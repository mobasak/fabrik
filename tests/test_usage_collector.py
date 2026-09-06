"""Behavior contract for the transcript collector — the thing that outlives the Claude Manager extension.

WHY IT EXISTS, measured rather than assumed: `~/.claude/.claude-manager/usage-history.json` is written
by an EXTENSION, and on 2026-09-04 17:31 it stopped while usage carried on. The store froze with it.
Claude Code's own transcripts under `~/.claude/projects/**/*.jsonl` are the primary record — every
assistant message carries its own `usage` block — and they are written whether or not any extension
is installed.

THE ASYMMETRY THIS SUITE PINS. The two sources disagree and WHICH IS RIGHT IS UNSETTLED: on the 111
days both hold, this walk's DEDUPED totals are a median 0.54x the extension's while the same records
UNDEDUPED are 1.13x, so the extension's number sits between them — consistent with it summing replays
we collapse. An earlier version of this docstring blamed transcript pruning as fact; the tree spans
essentially the whole recorded period, so that was a guess. The merge therefore fills days the
extension never recorded and NEVER rewrites one it did — not because transcripts are known to be
worse, but because the extension's 111 days cannot be rebuilt if we are wrong about which is right.
The overlap is published as `_discrepancy`, and this collector must run daily: whatever the
explanation, it can only capture a day while that day's transcripts still hold it.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "claude_p_cost.py"
_spec = importlib.util.spec_from_file_location("claude_p_cost_collector", _MOD)
cpc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cpc)


def _msg(day: str, model: str, mid: str, req: str, tok: int, *, sidechain: bool = False) -> str:
    """One assistant record in Claude Code's transcript shape."""
    return json.dumps(
        {
            "timestamp": f"{day}T10:00:00.000Z",
            "requestId": req,
            "isSidechain": sidechain,
            "message": {
                "id": mid,
                "model": model,
                "usage": {
                    "input_tokens": 1,
                    "output_tokens": 1,
                    "cache_read_input_tokens": tok - 3,
                    "cache_creation_input_tokens": 1,
                },
            },
        }
    )


def _tree(tmp_path: Path, files: dict[str, list[str]]) -> Path:
    root = tmp_path / "projects"
    for name, lines in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def test_it_sums_per_day_per_model_from_the_transcripts(tmp_path):
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/a.jsonl": [
                _msg("2026-09-05", "claude-opus-5", "m1", "r1", 1000),
                _msg("2026-09-05", "claude-sonnet-5", "m2", "r2", 500),
                _msg("2026-09-06", "claude-opus-5", "m3", "r3", 700),
            ]
        },
    )
    got = cpc.collect_from_transcripts(root)
    assert got == {
        "2026-09-05": {"claude-opus-5": 1000, "claude-sonnet-5": 500},
        "2026-09-06": {"claude-opus-5": 700},
    }


def test_a_message_replayed_into_another_session_file_is_counted_once(tmp_path):
    """Resume and compaction copy earlier messages into a NEW file. Without the (id, requestId)
    dedup the same spend is counted per copy — the walk over-reports and every rate derived from it
    is wrong in the same direction."""
    line = _msg("2026-09-05", "claude-opus-5", "m1", "r1", 1000)
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/original.jsonl": [line],
            "-opt-fabrik/resumed.jsonl": [
                line,
                _msg("2026-09-05", "claude-opus-5", "m2", "r2", 40),
            ],
        },
    )
    assert cpc.collect_from_transcripts(root) == {"2026-09-05": {"claude-opus-5": 1040}}


def test_subagent_sidechain_tokens_are_counted(tmp_path):
    """They bill to the same subscription. The question this store answers is what the subscription
    was spent on, not what the operator typed — and fan-out is a large part of the answer."""
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/a.jsonl": [
                _msg("2026-09-05", "claude-opus-5", "m1", "r1", 100),
                _msg("2026-09-05", "claude-opus-5", "m2", "r2", 900, sidechain=True),
            ]
        },
    )
    assert cpc.collect_from_transcripts(root) == {"2026-09-05": {"claude-opus-5": 1000}}


def test_junk_lines_never_raise_and_never_count(tmp_path):
    """A transcript is appended to live: the tail can be a half-written line, and older records carry
    shapes this reader has never seen. Never raises is the contract."""
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/a.jsonl": [
                '{"message":{"usage":',  # truncated mid-write
                '{"message": {"usage": {"input_tokens": 5}}}',  # no timestamp
                '{"timestamp":"2026-09-05T10:00:00Z","message":{"usage":{"input_tokens":5}}}',  # no model
                '{"timestamp":"not-a-date","message":{"id":"x","model":"claude-opus-5","usage":{"input_tokens":5}}}',
                '{"timestamp":"2026-09-05T10:00:00Z","message":{"id":"z","model":"claude-opus-5","usage":{}}}',
                _msg("2026-09-05", "claude-opus-5", "ok", "rok", 10),
            ]
        },
    )
    assert cpc.collect_from_transcripts(root) == {"2026-09-05": {"claude-opus-5": 10}}


def test_a_missing_transcript_root_is_empty_not_an_error(tmp_path):
    assert cpc.collect_from_transcripts(tmp_path / "nope") == {}


def _store(
    tmp_path,
    monkeypatch,
    days: dict,
    source_by_day: dict | None = None,
    *,
    version: int | None = -1,
) -> Path:
    """A store in the STEADY state by default — stamped with the current collector version, so tests
    exercise the ongoing rules rather than the one-shot migration. Pass `version=None` for an
    unstamped (pre-migration) store."""
    p = tmp_path / "store.json"
    body: dict = {"days": days}
    if version == -1:
        body["collector_version"] = cpc._COLLECTOR_VERSION
    elif version is not None:
        body["collector_version"] = version
    if source_by_day is not None:
        body["source_by_day"] = source_by_day
    p.write_text(json.dumps(body), encoding="utf-8")
    monkeypatch.setenv("CLAUDE_USAGE_DAILY", str(p))
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", tmp_path / "no-extension-file.json")
    return p


def test_the_merge_fills_days_the_extension_never_recorded(tmp_path, monkeypatch):
    """The live failure this was built for: the extension's file stops, and without the transcripts
    the store simply stops gaining days."""
    _store(
        tmp_path, monkeypatch, {"2026-09-04": {"claude-opus-5": 111}}, {"2026-09-04": "extension"}
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-06", "claude-opus-5", "m9", "r9", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-06"] == {"claude-opus-5": 900}
    assert store["source_by_day"]["2026-09-06"] == "transcripts"
    assert store["_transcript_added"] == 1


def test_an_extension_recorded_day_is_not_rewritten_by_the_transcripts(tmp_path, monkeypatch):
    """The load-bearing one. The transcripts hold more for the same day, and adopting that silently
    would restate 111 days of the operator's dashboard by 2-3x with no decision taken. The overlap is
    PUBLISHED instead, so the re-derivation can be judged on measurement."""
    _store(
        tmp_path, monkeypatch, {"2026-09-04": {"claude-opus-5": 100}}, {"2026-09-04": "extension"}
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-04", "claude-opus-5", "m1", "r1", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-04"] == {"claude-opus-5": 100}, "history must stand untouched"
    assert store["source_by_day"]["2026-09-04"] == "extension"
    assert store["_discrepancy"]["2026-09-04"] == {"extension": 100, "transcripts": 900}


def test_a_transcript_sourced_day_keeps_refreshing(tmp_path, monkeypatch):
    """Today is partial all day. A day this collector wrote must keep being rewritten by it, or the
    first run of the day freezes that day at breakfast."""
    _store(
        tmp_path, monkeypatch, {"2026-09-06": {"claude-opus-5": 100}}, {"2026-09-06": "transcripts"}
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-06", "claude-opus-5", "m1", "r1", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-06"] == {"claude-opus-5": 900}
    assert store["_transcript_refreshed"] == 1


def test_a_day_with_no_recorded_source_is_treated_as_history(tmp_path, monkeypatch):
    """Every day already in the store predates `source_by_day` and came from the extension. An absent
    marker must therefore read as "leave it alone", never as "mine to overwrite" — the fail direction
    that protects data rather than the one that rewrites it."""
    _store(tmp_path, monkeypatch, {"2026-08-01": {"claude-opus-5": 100}})  # no source_by_day at all
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-08-01", "claude-opus-5", "m1", "r1", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-08-01"] == {"claude-opus-5": 100}


def test_the_calendar_reaches_today_once_the_collector_runs(tmp_path, monkeypatch):
    """End to end: the reason any of this exists is that the Usage tab stopped gaining days."""
    today = datetime.date.today().isoformat()
    _store(tmp_path, monkeypatch, {})
    monkeypatch.setattr(cpc, "_MANAGER_ACCOUNTS", tmp_path / "no-accounts")
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg(today, "claude-opus-5", "m1", "r1", 5_000_000)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    daily = cpc.per_model_spend()["daily"]

    assert daily[-1]["date"] == today and daily[-1]["tokens"] == 5_000_000


def test_a_day_is_the_operators_local_day_not_the_utc_one(tmp_path, monkeypatch):
    """Transcripts stamp UTC; this box runs +03:00, and 14.2% of usage records fall in UTC
    21:00-23:59 — already tomorrow where the operator lives. Slicing `timestamp[:10]` filed a seventh
    of every evening under the previous day's calendar cell, on a page whose every other date is
    local. Pinned with a fixed +03:00 zone so the assertion does not depend on the box."""
    monkeypatch.setenv("TZ", "Europe/Istanbul")  # +03:00, no DST
    import time as _t

    _t.tzset()
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/a.jsonl": [
                # 22:30 UTC on the 4th IS 01:30 local on the 5th
                json.dumps(
                    {
                        "timestamp": "2026-09-04T22:30:00.000Z",
                        "requestId": "r1",
                        "message": {
                            "id": "m1",
                            "model": "claude-opus-5",
                            "usage": {"output_tokens": 500},
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-09-04T09:00:00.000Z",
                        "requestId": "r2",
                        "message": {
                            "id": "m2",
                            "model": "claude-opus-5",
                            "usage": {"output_tokens": 7},
                        },
                    }
                ),
            ]
        },
    )
    got = cpc.collect_from_transcripts(root)
    assert got == {"2026-09-04": {"claude-opus-5": 7}, "2026-09-05": {"claude-opus-5": 500}}


def test_a_timestamp_with_no_zone_still_counts_rather_than_vanishing(tmp_path):
    """Dropping the record would lose real spend. The date slice is the documented fallback."""
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/a.jsonl": [
                json.dumps(
                    {
                        "timestamp": "2026-09-04T22:30:00",
                        "requestId": "r1",
                        "message": {
                            "id": "m1",
                            "model": "claude-opus-5",
                            "usage": {"output_tokens": 42},
                        },
                    }
                )
            ]
        },
    )
    assert cpc.collect_from_transcripts(root) == {"2026-09-04": {"claude-opus-5": 42}}


def test_a_repeated_message_contributes_its_largest_sighting(tmp_path):
    """Measured, not theorised: 1,240,230 usage records on this box collapse to 554,811 keys, and
    153,400 of the repeats DISAGREE on their totals — a message is re-serialised as its usage
    accrues, so the first sighting is a PARTIAL. First-wins banked 159,866,901 tokens fewer across
    the tree. Max-wins is identical wherever duplicates agree."""
    partial = json.dumps(
        {
            "timestamp": "2026-09-05T09:00:00.000Z",
            "requestId": "r1",
            "message": {
                "id": "m1",
                "model": "claude-opus-5",
                "usage": {"output_tokens": 10},
            },
        }
    )
    complete = json.dumps(
        {
            "timestamp": "2026-09-05T09:00:00.000Z",
            "requestId": "r1",
            "message": {
                "id": "m1",
                "model": "claude-opus-5",
                "usage": {"output_tokens": 900},
            },
        }
    )
    # partial FIRST, so first-wins would bank 10 and stop
    root = _tree(tmp_path, {"-opt-fabrik/a.jsonl": [partial, complete]})
    assert cpc.collect_from_transcripts(root) == {"2026-09-05": {"claude-opus-5": 900}}
    # and the order must not matter
    root2 = _tree(tmp_path, {"-opt-fabrik/b.jsonl": [complete, partial]})
    assert cpc.collect_from_transcripts(root2)["2026-09-05"]["claude-opus-5"] == 900


def test_a_fuller_sighting_is_booked_to_the_first_sighting_day(tmp_path, monkeypatch):
    """A message re-serialised after local midnight must not MOVE spend between calendar days: the
    delta lands where the call was first booked, or a day's total changes retroactively for a reason
    that has nothing to do with usage."""
    monkeypatch.setenv("TZ", "Europe/Istanbul")
    import time as _t

    _t.tzset()
    early = json.dumps(
        {
            "timestamp": "2026-09-05T20:00:00.000Z",  # 23:00 local on the 5th
            "requestId": "r1",
            "message": {"id": "m1", "model": "claude-opus-5", "usage": {"output_tokens": 10}},
        }
    )
    later = json.dumps(
        {
            "timestamp": "2026-09-05T22:00:00.000Z",  # 01:00 local on the 6th
            "requestId": "r1",
            "message": {"id": "m1", "model": "claude-opus-5", "usage": {"output_tokens": 900}},
        }
    )
    got = cpc.collect_from_transcripts(_tree(tmp_path, {"-opt-fabrik/a.jsonl": [early, later]}))
    assert got == {"2026-09-05": {"claude-opus-5": 900}}, "all 900 on the day it was first booked"


def test_a_stored_day_never_shrinks_when_its_transcripts_are_pruned(tmp_path, monkeypatch):
    """The erosion the daily re-read would otherwise cause. A transcript-sourced day is re-read every
    run so today can keep growing — but once that day's session files are pruned the walk returns
    LESS, and a plain assignment writes the smaller number over a total once measured in full. Usage
    cannot un-happen."""
    _store(
        tmp_path, monkeypatch, {"2026-09-05": {"claude-opus-5": 900}}, {"2026-09-05": "transcripts"}
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 100)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-05"] == {"claude-opus-5": 900}
    assert store["_transcript_refreshed"] == 0


def test_a_growing_day_still_refreshes(tmp_path, monkeypatch):
    """The other half of the same rule — today is partial all day and must keep climbing."""
    _store(
        tmp_path, monkeypatch, {"2026-09-05": {"claude-opus-5": 100}}, {"2026-09-05": "transcripts"}
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    assert cpc.merge_usage_store()["days"]["2026-09-05"] == {"claude-opus-5": 900}


def test_the_discrepancy_sample_states_its_own_population(tmp_path, monkeypatch):
    """A 7-row sample with no denominator reads as the whole comparison — the exact shape the
    contract's denominator rule exists to refuse."""
    days = {f"2026-08-{d:02d}": {"claude-opus-5": 100} for d in range(1, 12)}
    _store(tmp_path, monkeypatch, days, dict.fromkeys(days, "extension"))
    root = _tree(
        tmp_path,
        {
            "-opt-fabrik/a.jsonl": [
                _msg(k, "claude-opus-5", f"m{i}", f"r{i}", 50) for i, k in enumerate(days)
            ]
        },
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert len(store["_discrepancy"]) == 7, "the sample stays bounded"
    assert store["_discrepancy_days"] == 11, "and it says what it is a sample OF"


def test_a_rule_change_re_derives_transcript_days_but_never_extension_days(tmp_path, monkeypatch):
    """The interaction between the two guards. Local-day bucketing and max-wins can make a re-read
    legitimately SMALLER for a day whose old total was mis-bucketed, and never-shrinks would preserve
    that error forever. A version bump drops the re-derivable days — and only those."""
    _store(
        tmp_path,
        monkeypatch,
        {"2026-09-04": {"claude-opus-5": 999}, "2026-09-05": {"claude-opus-5": 999}},
        {"2026-09-04": "extension", "2026-09-05": "transcripts"},
        version=None,  # a store written before the rule change
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 100)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-05"] == {"claude-opus-5": 100}, "re-derived under the new rules"
    assert store["days"]["2026-09-04"] == {"claude-opus-5": 999}, "history is NOT re-derivable"
    assert store["collector_version"] == cpc._COLLECTOR_VERSION


def test_an_up_to_date_store_is_not_re_derived(tmp_path, monkeypatch):
    """Once stamped, the never-shrinks guard takes over again — otherwise every run would erase a
    completed day's fuller total the moment its transcripts start ageing out."""
    p = tmp_path / "store.json"
    p.write_text(
        json.dumps(
            {
                "days": {"2026-09-05": {"claude-opus-5": 999}},
                "source_by_day": {"2026-09-05": "transcripts"},
                "collector_version": cpc._COLLECTOR_VERSION,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CLAUDE_USAGE_DAILY", str(p))
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", tmp_path / "no-extension.json")
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 100)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    assert cpc.merge_usage_store()["days"]["2026-09-05"] == {"claude-opus-5": 999}


def test_shape_damage_degrades_instead_of_killing_the_daily_refresh(tmp_path, monkeypatch):
    """SHAPE damage — a hand edit, a half-restored backup — must not stop the producer. Measured
    before guarding: `collector_version: "two"` raised ValueError, a dict raised TypeError, and a
    `days` list raised AttributeError, each of which would end the 06:00 refresh and silently stop
    recording usage until somebody noticed.

    ⚠️ This is the SHAPE half only. PARSE damage takes the opposite branch and is REFUSED — see
    `test_an_unparseable_store_is_refused_not_overwritten`, which is the defect a /fabrik-review
    finder caught in the very guard this test was written for: degrading a file that exists but does
    not parse, and then WRITING that degraded value back, destroys the only copy of the history."""
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 500)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", tmp_path / "no-extension.json")
    p = tmp_path / "store.json"
    monkeypatch.setenv("CLAUDE_USAGE_DAILY", str(p))

    for corrupt in (
        {"days": {"2026-01-01": {"claude-opus-5": 5}}, "collector_version": "two"},
        {"days": {"2026-01-01": {"claude-opus-5": 5}}, "collector_version": {"a": 1}},
        # a day whose VALUE is a scalar — this one reached `sum(days[k].values())` in the
        # `_discrepancy` build and `dict(days[k])` in the per-model merge, and raised on both
        {"days": {"2026-01-01": 7}, "source_by_day": {"2026-01-01": "extension"}},
        {},
    ):
        p.write_text(json.dumps(corrupt), encoding="utf-8")
        store = cpc.merge_usage_store()  # must not raise
        assert store["days"]["2026-09-05"] == {"claude-opus-5": 500}


def test_a_refresh_that_loses_a_model_keeps_it(tmp_path, monkeypatch):
    """Never-shrinks at the RIGHT granularity. One session's transcript can prune while another
    grows, so a day's TOTAL rises while a model disappears from it — and replacing on the total would
    drop that model out of the tier split entirely. Each model's daily total can only be discovered."""
    _store(
        tmp_path,
        monkeypatch,
        {"2026-09-05": {"claude-opus-5": 100, "claude-haiku-4-5": 50}},
        {"2026-09-05": "transcripts"},
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    day = cpc.merge_usage_store()["days"]["2026-09-05"]

    assert day == {"claude-opus-5": 900, "claude-haiku-4-5": 50}, "opus grows, haiku survives"


def test_the_result_does_not_depend_on_which_file_is_read_first(tmp_path, monkeypatch):
    """Files are walked in sorted PATH order, which has nothing to do with time. If a call's copies
    straddle local midnight, booking to the first-TRAVERSED sighting would let filenames decide the
    day — the same tree totalling differently on two boxes. It is booked to its EARLIEST sighting."""
    monkeypatch.setenv("TZ", "Europe/Istanbul")
    import time as _t

    _t.tzset()

    def rec(ts, tok):
        return json.dumps(
            {
                "timestamp": ts,
                "requestId": "r1",
                "message": {"id": "m1", "model": "claude-opus-5", "usage": {"output_tokens": tok}},
            }
        )

    early, late = rec("2026-09-05T20:30:00.000Z", 10), rec("2026-09-05T21:30:00.000Z", 900)
    # 20:30Z is 23:30 local on the 5th; 21:30Z is 00:30 local on the 6th.
    a = cpc.collect_from_transcripts(_tree(tmp_path / "x", {"a.jsonl": [early], "z.jsonl": [late]}))
    b = cpc.collect_from_transcripts(_tree(tmp_path / "y", {"a.jsonl": [late], "z.jsonl": [early]}))
    assert a == b, "path order must not change the answer"
    assert a == {"2026-09-05": {"claude-opus-5": 900}}, "booked where the call started"


def test_a_non_numeric_token_value_is_dropped_not_raised(tmp_path, monkeypatch):
    """`int("abc")` inside the per-model merge would end the daily run. The sanitiser keeps the
    invariant in ONE place: a day is a mapping of model to NUMBER, and anything else never reaches
    the arithmetic."""
    _store(
        tmp_path,
        monkeypatch,
        {"2026-09-05": {"claude-opus-5-old": "abc", "claude-haiku-4-5": 50, "x": True}},
        {"2026-09-05": "transcripts"},
    )
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 900)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()
    day = store["days"]["2026-09-05"]

    # The ARITHMETIC never sees them — opus is merged, haiku survives untouched…
    assert day["claude-opus-5"] == 900 and day["claude-haiku-4-5"] == 50
    # …but the unusable entries are PRESERVED rather than deleted, and named. Dropping them would
    # mean the next cron run erases values no other copy holds, which is the same class of loss as
    # overwriting an unparseable store.
    assert day["claude-opus-5-old"] == "abc" and day["x"] is True
    assert "2026-09-05" in store["_unusable"]["days"]


def test_an_extension_day_never_shrinks_either(tmp_path, monkeypatch):
    """The mirror of the transcript rule, found by an author-blind reader. The extension file is
    re-read every run so a partial day keeps growing — and the same re-read shrinks the day if that
    file is ever truncated, reset, or restored from an older copy. One invariant for the whole
    store, whatever wrote the day."""
    _store(
        tmp_path, monkeypatch, {"2026-09-04": {"claude-opus-5": 900}}, {"2026-09-04": "extension"}
    )
    history = tmp_path / "usage-history.json"
    history.write_text(
        json.dumps({"days": {"2026-09-04": {"byModel": {"claude-opus-5": {"output": 100}}}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", history)
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", tmp_path / "no-transcripts")

    assert cpc.merge_usage_store()["days"]["2026-09-04"] == {"claude-opus-5": 900}


def test_an_extension_day_still_grows(tmp_path, monkeypatch):
    """The half that must keep working — today is partial all day in the upstream file too."""
    _store(
        tmp_path, monkeypatch, {"2026-09-04": {"claude-opus-5": 100}}, {"2026-09-04": "extension"}
    )
    history = tmp_path / "usage-history.json"
    history.write_text(
        json.dumps({"days": {"2026-09-04": {"byModel": {"claude-opus-5": {"output": 900}}}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", history)
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", tmp_path / "no-transcripts")

    assert cpc.merge_usage_store()["days"]["2026-09-04"] == {"claude-opus-5": 900}


def test_an_unparseable_store_is_refused_not_overwritten(tmp_path, monkeypatch):
    """THE defect this whole review escalation earned. An earlier version caught every read failure
    and continued with `days = {}`, then wrote that back — so a truncated file REPLACED 113 days and
    298 billion tokens with an empty object, and with the extension dead and transcripts pruned there
    was nothing to rebuild from. Reproduced before the guard: 28 seeded days in, 0 days out."""
    p = tmp_path / "store.json"
    real = {
        "days": {f"2026-05-{i:02d}": {"claude-opus-5": 1_000_000_000} for i in range(1, 29)},
        "source_by_day": {f"2026-05-{i:02d}": "extension" for i in range(1, 29)},
        "collector_version": cpc._COLLECTOR_VERSION,
    }
    text = json.dumps(real)
    p.write_text(text[: len(text) // 2], encoding="utf-8")  # genuinely unparseable
    monkeypatch.setenv("CLAUDE_USAGE_DAILY", str(p))
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", tmp_path / "no-extension.json")
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", tmp_path / "no-transcripts")

    with pytest.raises(cpc.StoreUnreadableError):
        cpc.merge_usage_store()

    assert p.read_text(encoding="utf-8") == text[: len(text) // 2], "the bytes must be untouched"

    # STRUCTURAL damage takes the same branch: a `days` that is not an object, or a store that is not
    # an object at all, is damage rather than absence and must not be written over either.
    for structural in ({"days": ["not-a-mapping"]}, ["not-an-object"]):
        p.write_text(json.dumps(structural), encoding="utf-8")
        with pytest.raises(cpc.StoreUnreadableError):
            cpc.merge_usage_store()
        assert json.loads(p.read_text(encoding="utf-8")) == structural


def test_an_absent_store_is_still_a_legitimate_fresh_start(tmp_path, monkeypatch):
    """ABSENCE is not DAMAGE. A first run on a fresh box has no file and must proceed."""
    p = tmp_path / "store.json"
    monkeypatch.setenv("CLAUDE_USAGE_DAILY", str(p))
    monkeypatch.setattr(cpc, "_USAGE_HISTORY", tmp_path / "no-extension.json")
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 500)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    assert cpc.merge_usage_store()["days"]["2026-09-05"] == {"claude-opus-5": 500}


def test_a_day_this_collector_cannot_read_is_preserved_not_deleted(tmp_path, monkeypatch):
    """Sanitise for USE, preserve for STORAGE. An entry whose shape the arithmetic cannot use is
    still somebody's recorded spend; dropping it would mean the next cron run erases data no other
    copy holds. It rides along untouched and is named under `_unusable` for a human to repair."""
    _store(
        tmp_path,
        monkeypatch,
        {"2026-05-01": 12345, "2026-05-02": {"claude-opus-5": 7, "bad": "x"}},
        {"2026-05-01": "extension", "2026-05-02": "extension"},
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", tmp_path / "no-transcripts")

    store = cpc.merge_usage_store()

    assert store["days"]["2026-05-01"] == 12345, "the scalar day survives verbatim"
    assert store["days"]["2026-05-02"] == {"claude-opus-5": 7, "bad": "x"}
    assert store["_unusable"]["days"] == ["2026-05-01", "2026-05-02"]


def test_the_fallback_is_only_for_a_naive_but_valid_stamp(tmp_path):
    """The docstring used to promise an unconditional fallback to the date slice. It is not: a stamp
    whose DATE is invalid fails the slice too and the record is DROPPED. Both halves pinned, because
    the difference is what tells the next reader where a missing token went."""
    assert cpc._local_day("2026-09-05T22:00:00") == "2026-09-05", "naive but valid → the slice"
    for impossible in ("2026-02-30T00:00:00Z", "2026-13-01T00:00:00Z", "not-a-date", "", None):
        assert cpc._local_day(impossible) == "", f"{impossible!r} has no derivable day"

    # …and a record with no derivable day is skipped rather than booked under an empty key, which is
    # what stops `min(prior_day, day)` ever selecting "" as the earliest day.
    def rec(ts, tok):
        return json.dumps(
            {
                "timestamp": ts,
                "requestId": "r1",
                "message": {"id": "m1", "model": "claude-opus-5", "usage": {"output_tokens": tok}},
            }
        )

    root = _tree(tmp_path, {"a.jsonl": [rec("2026-09-05T12:00:00.000Z", 100), rec("garbage", 900)]})
    got = cpc.collect_from_transcripts(root)
    assert got == {"2026-09-05": {"claude-opus-5": 100}}
    assert "" not in got


def test_the_largest_sightings_model_is_the_one_booked(tmp_path):
    """A per-model $ error, not a labelling one: every consumer prices per model. An earlier version
    kept the largest sighting's TOKENS and discarded its MODEL, booking a measured 1,000,000 opus
    tokens as haiku — 68 of 300 randomised trials lost the model and 65 of 300 were order-dependent.
    The whole booking triple (earliest day, largest sighting's model, largest tokens) must be
    order-independent or two boxes reading one tree disagree."""

    def rec(day, tok, model):
        return json.dumps(
            {
                "timestamp": f"{day}T10:00:00.000Z",
                "requestId": "r1",
                "message": {"id": "m1", "model": model, "usage": {"output_tokens": tok}},
            }
        )

    big = ("2026-09-02", 1_000_000, "claude-opus-5")
    small = ("2026-09-01", 300, "claude-haiku-4-5")
    want = {"2026-09-01": {"claude-opus-5": 1_000_000}}
    assert (
        cpc.collect_from_transcripts(
            _tree(tmp_path / "a", {"0.jsonl": [rec(*big)], "1.jsonl": [rec(*small)]})
        )
        == want
    )
    assert (
        cpc.collect_from_transcripts(
            _tree(tmp_path / "b", {"0.jsonl": [rec(*small)], "1.jsonl": [rec(*big)]})
        )
        == want
    )


def test_one_poisoned_record_cannot_stop_the_whole_walk(tmp_path):
    """The outage shape. `json.loads` accepts a bare NaN, `isinstance(v, (int, float))` admits it and
    `int()` raises; an unhashable `message.id` raises on the dedup lookup. Either killed the walk —
    and since the poisoned line stays on disk, every LATER file and every later run died with it,
    silently, behind a green cron. Files are walked in sorted order, so a bad line in `aaa.jsonl`
    took `zzz.jsonl` with it."""
    poison = (
        '{"timestamp":"2026-09-01T10:00:00Z","requestId":"r","message":'
        '{"id":{"unhashable":1},"model":"claude-opus-5","usage":{"output_tokens":5}}}'
    )
    nan = (
        '{"timestamp":"2026-09-01T10:00:00Z","requestId":"r2","message":'
        '{"id":"m2","model":"claude-opus-5","usage":{"output_tokens":NaN}}}'
    )
    root = _tree(
        tmp_path,
        {
            "aaa.jsonl": [poison, nan],
            "zzz.jsonl": [_msg("2026-09-02", "claude-opus-5", "m9", "r9", 900_000_000)],
        },
    )
    got = cpc.collect_from_transcripts(root)
    assert got["2026-09-02"] == {"claude-opus-5": 900_000_000}, "the later file must still be read"
    assert got["2026-09-01"] == {"claude-opus-5": 5}, "an unhashable id counts, undeduped"


def test_a_bool_is_not_a_token_count(tmp_path):
    rec = json.dumps(
        {
            "timestamp": "2026-09-01T10:00:00Z",
            "requestId": "r",
            "message": {
                "id": "m",
                "model": "claude-opus-5",
                "usage": {"input_tokens": True, "output_tokens": True},
            },
        }
    )
    assert cpc.collect_from_transcripts(_tree(tmp_path, {"a.jsonl": [rec]})) == {}


def test_the_migration_only_drops_a_day_it_can_actually_replace(tmp_path, monkeypatch):
    """The drop used to run BEFORE the walk, and the version stamp was written regardless — so a rule
    bump on a day whose transcripts had since pruned deleted it outright. Reproduced at 13 BILLION
    tokens lost, and one-shot, so the next run could not repair it. The premise that a transcript day
    is 're-derivable by construction' is contradicted by this module's own 0.54x pruning number."""
    _store(
        tmp_path,
        monkeypatch,
        {"2026-09-05": {"claude-opus-5": 9_000_000_000}, "2026-09-06": {"claude-opus-5": 4_000}},
        {"2026-09-05": "transcripts", "2026-09-06": "transcripts"},
        version=1,  # older than _COLLECTOR_VERSION: the migration will fire
    )
    # the tree still holds 09-06 but has PRUNED 09-05
    root = _tree(
        tmp_path, {"-opt-fabrik/a.jsonl": [_msg("2026-09-06", "claude-opus-5", "m1", "r1", 12_000)]}
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", root)

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-05"] == {"claude-opus-5": 9_000_000_000}, "pruned ⇒ keep it"
    assert store["days"]["2026-09-06"] == {"claude-opus-5": 12_000}, "re-derivable ⇒ replace it"


def test_the_run_counters_reach_the_file_not_just_the_return_value(tmp_path, monkeypatch):
    """They were attached to `store` AFTER `os.replace`, so the written file never carried them and a
    reader saw the PREVIOUS run's values — on a producer whose only in-file signal of what it did is
    these numbers, and which nobody watches because it runs at 06:00. `extension_source_present` is
    the same need: it is how a reader learns source 1 has stopped, the event that made this collector
    necessary and which nothing else in the file records."""
    p = _store(tmp_path, monkeypatch, {}, {})
    monkeypatch.setattr(
        cpc,
        "_TRANSCRIPT_ROOT",
        _tree(
            tmp_path,
            {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 500)]},
        ),
    )

    cpc.merge_usage_store()

    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert on_disk["_transcript_added"] == 1, "the file must carry THIS run's counts"
    assert on_disk["_total_days"] == 1
    assert on_disk["extension_source_present"] is False, "source 1 is gone and the file says so"


def test_the_migration_stamp_is_not_consumed_by_a_blind_run(tmp_path, monkeypatch):
    """A one-shot that consumes itself on a run where the transcript root was unmounted, unreadable
    or empty would skip the re-derivation FOREVER — the next run reads an up-to-date stamp and never
    retries. An empty walk with days still pending means "could not look", not "nothing to do", and
    those are opposite answers."""
    _store(
        tmp_path,
        monkeypatch,
        {"2026-09-05": {"claude-opus-5": 900}},
        {"2026-09-05": "transcripts"},
        version=1,
    )
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", tmp_path / "unmounted")  # the walk sees nothing

    store = cpc.merge_usage_store()

    assert store["days"]["2026-09-05"] == {"claude-opus-5": 900}, "the day survives"
    assert store["collector_version"] == 1, "the stamp must NOT advance on a blind run"

    # …and once the tree is readable again, the migration finally runs.
    monkeypatch.setattr(
        cpc,
        "_TRANSCRIPT_ROOT",
        _tree(
            tmp_path,
            {"-opt-fabrik/a.jsonl": [_msg("2026-09-05", "claude-opus-5", "m1", "r1", 4_000)]},
        ),
    )
    store = cpc.merge_usage_store()
    assert store["days"]["2026-09-05"] == {"claude-opus-5": 4_000}, "re-derived under the new rules"
    assert store["collector_version"] == cpc._COLLECTOR_VERSION


def test_a_fresh_store_still_stamps(tmp_path, monkeypatch):
    """Nothing pending ⇒ nothing to retry, so an empty walk must not pin a fresh box at version 0."""
    _store(tmp_path, monkeypatch, {}, {}, version=None)
    monkeypatch.setattr(cpc, "_TRANSCRIPT_ROOT", tmp_path / "empty")
    assert cpc.merge_usage_store()["collector_version"] == cpc._COLLECTOR_VERSION
