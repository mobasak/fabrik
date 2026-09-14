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
    ) == [(1, 3.0)]  # floored lo, close second whole (R2)


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


def test_edits_older_than_the_ledgers_birth_are_not_re_judged():
    # The covered ledger was born at ff887758; a long-lived session's earlier edits were
    # adjudicated by the per-session rule of their day and no ledger holds their closes, so
    # the sixth cause re-blocked 16 already-reviewed edits three times per turn (2026-09-07).
    epoch = fgs._LEDGER_EPOCH
    assert epoch == 1788713768.0, (
        "pinned to ff887758's commit epoch — a moved epoch widens the hole"
    )
    assert fgs._sixth_cause_floor(epoch - 100_000) == epoch, "an older baseline is raised"
    assert fgs._sixth_cause_floor(epoch + 5) == epoch + 5, "a newer baseline stands"
    assert fgs._sixth_cause_floor(0.0) == epoch, "no baseline still floors at the ledger"
    mine = fgs._this_sessions_edits(
        {"old.py": epoch - 1, "new.py": epoch + 1}, fgs._sixth_cause_floor(epoch - 100_000)
    )
    assert mine == {"new.py": epoch + 1}, "pre-ledger edit dropped, post-ledger edit judged"


def test_the_ledger_floor_is_wired_at_the_sixth_causes_call_site():
    # The helper grader above cannot see the wiring: reverting the call-site edit alone keeps
    # every assertion green. Pin the one line that applies the floor.
    #
    # T5.2 moved the composition into `_unreviewed_spontaneous` (which APPLIES the floor and is
    # graded on it behaviourally, floor-empties-the-count, in
    # test_the_sixth_cause_counts_through_one_composed_reader). What no behavioural test can see
    # is whether `main` hands it the REAL baseline, so that is what stays pinned here — plus the
    # absence of both earlier shapes, so a revert to either is caught rather than silently green.
    src = (REPO / ".claude" / "hooks" / "final_gate_stop.py").read_text(encoding="utf-8")
    assert src.count("_unreviewed_spontaneous(_rec, authored_map, _floor, sid)") == 1
    assert src.count("_this_sessions_edits(authored_map, _floor)") == 0, (
        "the unfloored call is gone"
    )
    assert src.count("_unreviewed_code_files(\n                    _this_sessions_edits(") == 0, (
        "the inline composition is gone — it is the shape that bypassed the surface exemption"
    )
    assert "_sixth_cause_floor(session_floor)" in src, "the floor still rides the composed reader"


def test_a_legacy_sub_second_pair_written_before_the_writer_floored_is_read_whole():
    # F7 (non-author pass, 2026-09-07): the reader floored lo AFTER testing lo <= hi, so a pair a
    # pre-R2 writer left as [100.7, 100] was still dropped — fail-closed, but the commit claimed
    # the reader "covers the close second whole" for existing ledgers too.
    wins = fgs._review_windows({"state": "done", "covered": [[100.7, 100]]})
    assert wins == [(100, 101.0)], wins
    assert fgs._review_windows({"state": "done", "covered": [[102.2, 100]]}) == [], "still junk"


def test_a_parked_parents_window_still_covers_during_a_nested_child(monkeypatch):
    """T5.1 (01M288YHD, 01M25Y93RB, 01M1YB2AK): the sixth cause asks "inside ANY window this
    session held" — and during a NESTED child it was not asking about the parent's.

    `command_run.py::start` parks the running parent on `stack` and gives the child an EMPTY
    `covered` ledger on purpose (copying the parent's down and joining it back up doubled the
    ledger per nest cycle — its closing review C-4/E1). The cost was never paid on the hook side:
    `_review_windows` read `covered` plus the CURRENT record only, so for the whole life of a
    nested `/fabrik-review` BOTH the parent's live window AND every window the session had
    already closed were invisible, and code authored minutes earlier under the parent's own
    contract read as UNREVIEWED SPONTANEOUS WORK. Measured before the fix: an edit at t0+60 under
    a parent started at t0 counted 1 unreviewed once a child started at t0+120, and 0 with the
    same parent live — the nesting was the whole difference."""
    t0, t1, t2 = 1_757_000_000.0, 1_757_000_060.0, 1_757_000_120.0
    parked = {
        "command": "fabrik-execute-plan",
        "state": "running",
        "started_epoch": t0,
        "covered": [[1_756_000_000, 1_756_000_500]],  # an earlier command of the same session
    }
    child = {
        "command": "fabrik-review",
        "state": "running",
        "started_epoch": t2,
        "covered": [],
        "stack": [parked],
    }
    wins = fgs._review_windows(child)
    assert (t0, float("inf")) in wins, ("the parked parent's live window", wins)
    assert (1_756_000_000.0, 1_756_000_501.0) in wins, ("the parent's carried ledger", wins)
    assert fgs._unreviewed_code_files({"scripts/x.py": int(t1)}, wins) == 0
    # the control that makes this a nesting bug and not a window bug: parent live, same edit
    assert (
        fgs._unreviewed_code_files(
            {"scripts/x.py": int(t1)}, fgs._review_windows({**parked, "covered": []})
        )
        == 0
    )
    # an edit BEFORE the parent started is still spontaneous — the fix widens nothing else
    assert fgs._unreviewed_code_files({"scripts/x.py": int(t0) - 1}, wins) == 1

    # a malformed frame is ignored, never a crash (the `covered` reader's own contract)
    junk = fgs._review_windows(
        {"state": "running", "started_epoch": t2, "stack": ["x", {}, {"started_epoch": 0}, None]}
    )
    assert junk == [(t2, float("inf"))], junk

    # MIRROR — the stale hatch: when the LIVE record is too old for the fifth cause to act on,
    # `_review_window` returns None so the sixth cause cannot arm on it. The frames ride the same
    # file and must fail the same way, or a stale nested record would launder its parent's span.
    # the asymmetry is the one the non-nested path already has: a CLOSED window is a historical
    # fact and survives staleness; only the live claims (the child's and the parent's) are dropped.
    monkeypatch.setattr(fgs, "_run_record", lambda _sid: None)
    monkeypatch.setattr(fgs, "_stale_bound_s", lambda: 43200.0)
    assert fgs._review_windows(child, "some-sid") == [(1_756_000_000.0, 1_756_000_501.0)]
    assert (
        fgs._unreviewed_code_files({"scripts/x.py": int(t1)}, fgs._review_windows(child, "s")) == 1
    )


def test_the_review_family_set_is_not_a_fifth_hand_kept_copy():
    """`_CLOSED_STATES` was the fourth hand-kept copy of a set the writer owns, and a parity
    grader is what stopped the drift (closing review C-3). T5.2 needs the review-family set on the
    hook side too; it gets the same binding rather than a new copy to drift."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("cr", "/opt/fabrik/scripts/command_run.py")
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    assert fgs._REVIEW_FAMILY == cr.REVIEW_FAMILY


def test_a_running_reviews_own_surface_files_are_not_spontaneous_work():
    """T5.2 (01M28YN1F): the sixth cause fired on the very files a RUNNING /fabrik-review-scoped
    record already names as its `--surface`.

    A review's window opens at its `start`, so code authored BEFORE it — which is the only code a
    review can possibly be reviewing — sat outside every window until the record closed `done` and
    the reach-back applied. Between those two moments the hook blocked the session for not
    reviewing what it was at that moment reviewing. The reach-back cannot move earlier (a `blocked`
    or `handoff` close must not certify the gap — reach-back reader F1), so the running record
    exempts by NAME instead: exactly the paths its surface spells, and only while it runs."""
    surf = "the working-tree diff over `scripts/a.py`, tests/b.py:44 and ./docs/c.md"
    rec = {
        "command": "fabrik-review-scoped",
        "state": "running",
        "started_epoch": 9000,
        "surface": surf,
    }
    authored = {"scripts/a.py": 100, "tests/b.py": 200, "docs/c.md": 300, "scripts/other.py": 400}
    named = fgs._surface_reviewed(rec, authored)
    assert named == {"scripts/a.py", "tests/b.py", "docs/c.md"}, named
    # the file the surface does NOT name is still spontaneous — the exemption is by name, not by run
    assert (
        fgs._unreviewed_code_files(
            {k: v for k, v in authored.items() if k not in named}, fgs._review_windows(rec)
        )
        == 1
    )

    # a parked parent review counts too — the T5.1 frames carry state and surface alike
    nested = {
        "command": "fabrik-execute-plan",
        "state": "running",
        "started_epoch": 9500,
        "stack": [dict(rec)],
    }
    assert fgs._surface_reviewed(nested, authored) == named

    # ...and the three ways this must NOT launder:
    assert fgs._surface_reviewed({**rec, "command": "fabrik-spec"}, authored) == set(), (
        "a non-review command naming files in its surface reviews nothing"
    )
    assert fgs._surface_reviewed({**rec, "state": "done"}, authored) == set(), (
        "a CLOSED record is the reach-back's business, and a blocked close must not reach back"
    )
    assert (
        fgs._surface_reviewed({**rec, "surface": "everything under scripts/ and tests/"}, authored)
        == set()
    ), "a directory is not a file: equality only, never a prefix"

    # malformed records and surfaces are inert, never a crash
    for bad in (
        None,
        {},
        {"command": "fabrik-review", "state": "running", "surface": None},
        {"command": "fabrik-review", "state": "running", "surface": 7},
        {"command": "fabrik-review", "state": "running", "stack": ["x", None]},
    ):
        assert fgs._surface_reviewed(bad, authored) == set(), bad


def test_the_sixth_cause_counts_through_one_composed_reader(monkeypatch):
    """The call site is ~40 lines inside `main`, so the composition is graded here instead —
    otherwise T5.2's exemption could be deleted with a green suite (D-252 round 3's lesson: a
    fix whose wiring no test reaches is a fix nothing guards). All three filters are exercised."""
    monkeypatch.setattr(fgs, "_LEDGER_EPOCH", 0.0)
    rec = {
        "command": "fabrik-review",
        "state": "running",
        "started_epoch": 5000,
        "surface": "`scripts/named.py` and nothing else",
        "covered": [[1000, 1200]],
    }
    authored = {
        "scripts/named.py": 3000,  # outside every window, but the running review NAMES it
        "scripts/inwindow.py": 1100,  # inside the closed ledger window
        "scripts/live.py": 5500,  # inside the running window
        "scripts/old.py": 10,  # below the floor — not this session's
        "scripts/loose.py": 3000,  # outside every window and named by nobody
    }
    assert fgs._unreviewed_spontaneous(rec, authored, 100.0) == 1
    # drop the surface and the named file joins the loose one
    assert fgs._unreviewed_spontaneous({**rec, "surface": ""}, authored, 100.0) == 2
    # raise the floor past everything and the count empties
    assert fgs._unreviewed_spontaneous(rec, authored, 9e9) == 0
    # no record at all: every edit above the floor is spontaneous
    assert fgs._unreviewed_spontaneous(None, authored, 100.0) == 4


def test_the_first_review_of_a_session_can_still_cover_work_that_preceded_it(monkeypatch):
    """T5.3 (01M21JAET): "the sixth cause is permanently unclearable after a fleet-quota
    interruption — mtimes are historical, windows are not retroactive."

    28ca7443 closed the PRE-LEDGER half of this (edits older than the ledger's birth) and is
    transitional by construction. The other half was still open and is not transitional. A review's
    window reaches BACK to the previous covered window's close (`command_run.py`, done-only per
    reach-back reader F1) — but with an EMPTY ledger there is nothing to reach back TO, so the
    writer falls back to the review's own `started_epoch`. A session interrupted before any command
    closed therefore carries edits with historical mtimes above the SessionStart baseline and below
    its first review's start, and NO review can ever cover them: measured at 1 unreviewed file
    after a clean `done` close, unchanged for every later round.

    The missing piece is the base case of the rule the writer already applies: a review's contract
    is "this session's work SINCE THE LAST RUN", and with no last run that is the session's work,
    whose lower bound is the session floor. The floor lives only on this side — it is the
    SessionStart baseline's mtime — so the base case is applied here, once, as an ADDED window
    rather than a mutated pair."""
    monkeypatch.setattr(fgs, "_LEDGER_EPOCH", 0.0)
    base, edit, start, close = 1000.0, 2000.0, 9000.0, 9100.0
    authored = {"scripts/interrupted.py": int(edit)}
    done = {
        "command": "fabrik-review-scoped",
        "state": "done",
        "started_epoch": start,
        "updated_ts": int(close),
        "covered": [[int(start), int(close)]],  # what the writer appends with an empty ledger
    }
    assert fgs._unreviewed_spontaneous(done, authored, base) == 0, (
        "the first review of a session covers the session up to its own start"
    )
    # an edit BELOW the session floor is not this session's work and is not swept in
    assert fgs._unreviewed_spontaneous(done, {"scripts/x.py": int(base) - 5}, base) == 0
    assert fgs._this_sessions_edits({"scripts/x.py": int(base) - 5}, base) == {}

    # the three ways this base case must NOT fire:
    assert fgs._unreviewed_spontaneous({**done, "state": "blocked"}, authored, base) == 1, (
        "F1: a blocked or handoff close certifies nothing — the laundering hatch stays shut"
    )
    assert fgs._unreviewed_spontaneous({**done, "command": "fabrik-spec"}, authored, base) == 1, (
        "only a review's contract is 'this session's work'"
    )
    # a ledger with an earlier run is the WRITER's reach-back to do; this side stands down. The
    # fixture hand-writes the pair WITHOUT the reach-back the writer would have applied, so an edit
    # in the gap (above the floor, below the review's start) must stay uncovered.
    with_prior = {**done, "covered": [[1100, 1200], [int(start), int(close)]]}
    assert fgs._first_review_base_case(with_prior, base) == []
    assert fgs._unreviewed_spontaneous(with_prior, {"scripts/y.py": 5000}, base) == 1
    # and the same edit IS covered once the writer's reach-back is present, which is the real shape
    reached = {**done, "covered": [[1100, 1200], [1200, int(close)]]}
    assert fgs._unreviewed_spontaneous(reached, {"scripts/y.py": 5000}, base) == 0
