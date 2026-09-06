"""Spontaneous code changes owe a review — and the hook now knows what "spontaneous" means.

Operator, 2026-08-29: work done in plain chat (no /fabrik-* command) changes the repo and nothing
triggers a review; typing /fabrik-review is heavy and gets forgotten. The mechanical insight: every
command opens a run record (corpus predicate 5, gate-enforced), so a session that authored CODE
with NO run record at all IS spontaneous work by construction. Commanded work exempts itself.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "final_gate_stop", REPO / ".claude" / "hooks" / "final_gate_stop.py"
)
fgs = importlib.util.module_from_spec(_spec)
sys.modules["final_gate_stop"] = fgs
_spec.loader.exec_module(fgs)


def test_code_edits_with_no_record_block_up_to_the_cap():
    a = 0
    for expect in (1, 2, 3):
        action, a = fgs.decide_review(3, a)
        assert action == "block_review" and a == expect
    action, a = fgs.decide_review(3, a)
    assert action == "allow_warn_review", "cap must warn through, never trap (anti-trap law)"


def test_code_authored_inside_a_commands_window_is_exempt():
    """An /fabrik-execute-plan turn commits code under ITS record; its own contract owns the
    review discipline — for edits INSIDE its [start, close] window (A-F5/A-F7 re-grounding)."""
    win = fgs._review_window({"state": "done", "started_epoch": 100, "updated_ts": 900})
    n = fgs._unreviewed_code_files({"src/a.py": 500, "src/b.py": 850}, win)
    action, a = fgs.decide_review(n, attempts=2)
    assert n == 0 and action == "allow" and a == 0, (
        "covered edits must exempt AND reset the counter"
    )


def test_doc_only_sessions_never_fire():
    action, a = fgs.decide_review(0, 2)
    assert action == "allow" and a == 0


def test_code_file_classifier():
    files = {"a.py": 1, "b.md": 2, "c.json": 3, "d.ts": 4, "e.txt": 5}
    assert fgs._unreviewed_code_files(files, None) == 3, "py + json + ts are code; md/txt are not"


def test_counters_extend_compatibly():
    """Old 5-slot counter files must read as 0 for the new slot — a synced hook meeting a
    pre-upgrade counter file must not crash or misattribute attempts."""
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        f.write("1,2,3,4,5")
        p = Path(f.name)
    vals = fgs._read_counters(p)
    assert vals == (1, 2, 3, 4, 5, 0), vals
    p.unlink()


# --- the checkpoint is PER CHANGE, not per session (operator, 2026-09-06) ------------------------
# `_run_record_exists` answered "did this session EVER open a record?" — a per-session boolean.
# Measured: a session ran /fabrik-review-scoped at 01:45, then made TEN plain-chat commits across
# the day, and never tripped the sixth cause because that one morning record exempted everything
# after it. The hook must ask "is there authored CODE newer than the last closed command?" — a
# closed command covers the edits made before its close and nothing after; a RUNNING record is
# the fifth cause's business and must not double-block here.

T = 1_800_000_000


def test_code_authored_after_the_last_closed_command_is_unreviewed():
    authored = {"src/a.py": T + 60, "src/b.py": T - 60, "docs/x.md": T + 600}
    window = fgs._review_window(
        {
            "command": "fabrik-review-scoped",
            "state": "done",
            "started_epoch": T - 3600,
            "updated_ts": T,
        }
    )
    assert window == (T - 3600, T + 1)  # the close second is covered whole (R2)
    assert fgs._unreviewed_code_files(authored, window) == 1, "only a.py is newer than the close"


def test_no_record_at_all_leaves_every_code_file_unreviewed():
    authored = {"src/a.py": T, "src/b.py": T - 9999}
    assert fgs._review_window(None) is None
    assert fgs._unreviewed_code_files(authored, None) == 2


def test_a_running_record_is_the_fifth_causes_business_not_this_ones():
    authored = {"src/a.py": T + 60}
    window = fgs._review_window(
        {
            "command": "fabrik-execute-plan",
            "state": "running",
            "started_epoch": T - 60,
            "updated_ts": T,
        }
    )
    assert fgs._unreviewed_code_files(authored, window) == 0, "never double-block a live command"


def test_a_blocked_close_covers_like_a_done_close():
    window = fgs._review_window(
        {"command": "fabrik-review", "state": "blocked", "started_epoch": T - 10, "updated_ts": T}
    )
    assert window == (T - 10, T + 1)


def test_malformed_record_reads_as_no_record():
    for rec in (
        {"state": "done"},
        {"updated_ts": "soon", "state": "done", "started_epoch": 1},
        "junk",
        42,
    ):
        assert fgs._review_window(rec) is None


def test_handoff_is_a_closed_state_that_covers_like_done():
    """A-F2: /fabrik-user-test and /fabrik-service-test MANDATE a `handoff` close; hand-writing
    {"done","blocked"} blocked every such session with 'NO command run record'."""
    win = fgs._review_window({"state": "handoff", "started_epoch": T - 100, "updated_ts": T})
    assert win == (T - 100, T + 1)
    assert (
        frozenset({"done", "blocked", "handoff"}) == fgs._CLOSED_STATES
    )  # agent closes only (C-2)


def test_code_authored_before_the_command_started_is_not_covered():
    """A-F5: a command's contract owns its scope from its START, not from the beginning of time.
    Plain-chat code edited at 12:00, then /fabrik-spec run 12:10-12:40 → the 12:00 edit is
    covered by nothing."""
    win = fgs._review_window({"state": "done", "started_epoch": T + 600, "updated_ts": T + 2400})
    assert fgs._unreviewed_code_files({"src/a.py": T}, win) == 1
    assert fgs._unreviewed_code_files({"src/a.py": T + 900}, win) == 0
    assert fgs._unreviewed_code_files({"src/a.py": T + 3000}, win) == 1


def test_a_stale_running_record_no_longer_covers(monkeypatch):
    """A-F3: `running` covered 'now' freshness-blind while the fifth cause fails OPEN past 12h — an
    abandoned `start` bought permanent immunity. Running covers only while the record is fresh."""
    monkeypatch.setattr(fgs, "_run_record", lambda sid: None)  # the fifth cause's verdict: stale
    assert (
        fgs._review_window({"state": "running", "started_epoch": T, "updated_ts": T}, sid="x")
        is None
    )
    monkeypatch.setattr(fgs, "_run_record", lambda sid: {"state": "running"})
    assert fgs._review_window(
        {"state": "running", "started_epoch": T, "updated_ts": T}, sid="x"
    ) == (T, float("inf"))


def test_non_finite_or_bool_timestamps_read_as_no_record():
    """A-F6: json.loads accepts bare NaN/Infinity; `Infinity` gave a permanent exemption, `true`
    read as 1970. The guard _run_record already carries is lifted here verbatim."""
    for bad in (float("inf"), float("nan"), True):
        assert fgs._review_window({"state": "done", "started_epoch": T, "updated_ts": bad}) is None
        assert fgs._review_window({"state": "done", "started_epoch": bad, "updated_ts": T}) is None


def test_warn_through_re_arms_like_every_other_cause():
    """A-F8: after three blocks the cause disarmed for the rest of the session."""
    action, a = fgs.decide_review(3, 3)
    assert action == "allow_warn_review" and a == 0, (
        "must reset so the next unreviewed stop blocks again"
    )


def test_an_edit_with_no_parseable_timestamp_counts_as_unreviewed():
    """A-F10: ts=0 (unparseable transcript timestamp) read as covered by any window."""
    assert fgs._unreviewed_code_files({"src/a.py": 0}, (T - 100, T)) == 1


def test_the_dead_per_session_helpers_are_gone():
    """A-F7: _run_record_exists / _count_code_files had zero production callers and a docstring
    that instructed the reverted contract; a green test certified the removed behaviour."""
    assert not hasattr(fgs, "_run_record_exists") and not hasattr(fgs, "_count_code_files")


def test_every_earlier_commands_window_stays_covered_across_a_start_overwrite():
    """P1-1 (CRITICAL, fleet-wide): one record per session, OVERWRITTEN by the next `start`. A
    single [started, closed] window destroyed the coverage of every command before the last one,
    and running another review only narrowed it further — a permanent 3-block/1-warn cycle. The
    `covered` ledger (appended at close, carried across `start`) keeps every window."""
    rec = {"state": "done", "started_epoch": 3000, "updated_ts": 3600, "covered": [[100, 900]]}
    wins = fgs._review_windows(rec)
    assert (100.0, 901.0) in wins and (3000.0, 3601.0) in wins, wins
    assert fgs._unreviewed_code_files({"src/a.py": 500, "src/b.py": 3300}, wins) == 0
    assert fgs._unreviewed_code_files({"src/c.py": 2000}, wins) == 1, (
        "between runs: nobody reviewed it"
    )
    # the single-window shape that produced P1-1, kept only for the mirror
    assert fgs._unreviewed_code_files({"src/a.py": 500}, fgs._review_window(rec)) == 1
    # a malformed ledger entry is ignored, never a crash
    assert fgs._review_windows(
        {
            "state": "done",
            "started_epoch": 1,
            "updated_ts": 2,
            "covered": [[float("nan"), 5], "x", [9, 1]],
        }
    ) == [(1.0, 2.0)]


def test_a_resumed_transcripts_ancient_edits_are_not_this_sessions():
    """P1-3: a session id can carry months of transcript (454 code files over 116 days measured);
    the sixth cause reads only edits at or after the SessionStart baseline, like attribution
    (`_failure_cites_session`) always did. Unknown timestamps (0) stay — they still count."""
    m = fgs._this_sessions_edits({"old.py": 100, "new.py": 5000, "unknown.py": 0}, 4000)
    assert m == {"new.py": 5000, "unknown.py": 0}
    assert fgs._this_sessions_edits({"old.py": 100}, 0.0) == {"old.py": 100}, (
        "no baseline → keep all"
    )


def test_the_operators_stale_opt_out_does_not_uncover_a_live_run(monkeypatch):
    """P1-2: `COMMAND_RUN_STALE_H<=0` is the fifth cause's "don't trap me" hatch; through
    `_run_record` it read as "no record" here and armed the SIXTH cause against a live run."""
    monkeypatch.setenv("COMMAND_RUN_STALE_H", "0")
    rec = {"state": "running", "started_epoch": 100, "updated_ts": 200}
    assert fgs._review_window(rec, "sid-with-no-store") == (100.0, float("inf"))


def test_coroner_reaped_records_cover_nothing():
    """C-2 (reversing P1-9): the coroner's `died`/`expired` close a run no agent reviewed — a 37 h
    abandoned plan sat in the live store; granting its span laundered every edit inside it. A
    reaped record reads as NO record, and the remedy is the review the run never had."""
    for st in ("died", "expired"):
        assert fgs._review_window({"state": st, "started_epoch": 100, "updated_ts": 900}) is None, (
            st
        )


def test_the_hooks_closed_states_equal_command_runs_agent_closes():
    """C-3: the fourth hand-kept copy of the closed-state set — bind it."""
    import importlib.util as _ilu

    spec = _ilu.spec_from_file_location("command_run", REPO / "scripts" / "command_run.py")
    cr = _ilu.module_from_spec(spec)
    spec.loader.exec_module(cr)
    assert fgs._CLOSED_STATES == cr.AGENT_CLOSED_STATES


def test_a_zero_started_epoch_covers_nothing_like_the_writer_refuses_it():
    """E8: `_finite(0)` is 0.0, not None — a record with started_epoch 0 read as "one command
    covered everything since the epoch"; the writer never records such a window."""
    assert fgs._review_window({"state": "done", "started_epoch": 0, "updated_ts": 900}) is None
