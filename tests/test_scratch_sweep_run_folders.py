"""Run-bound scratch: the ONE classifier and the marker (scratch lifecycle plan, Phase A).

`classify_run_folder` is the only function that answers ACTIVE or CONSUMED for a `run-*` folder
(plan P2). These tests pin the operator's bar — "do not cause active scrathcpads to be removed but be
sure the ones consumed will be done so" — as a partition: every marker state is exactly one of the
two, and no INV-1 condition ever reads CONSUMED.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "scratch_sweep.py"


def _load():
    spec = importlib.util.spec_from_file_location("scratch_sweep_runfolders_ut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(mod)
    return mod


sw = _load()

NOW = 1_800_000_000.0
MIN = 60
HOUR = 3600
DAY = 86400

# A CONSUMED baseline: a `done` run closed 40 h ago, nothing holding it.
BASE = sw.RunFacts(
    state="done",
    closed_at=NOW - 40 * HOUR,
    heartbeat_age_s=40 * HOUR,
    session_dead=False,
    held=False,
    gaps=False,
    probe_ok=True,
    worktree=False,
    keep=False,
    sid_matches=True,
    seat_write_after_close=False,
)

# Each spec § Invariants INV-1 condition ALONE (on top of a baseline that would otherwise be CONSUMED).
ACTIVE_CASES = {
    "running, live session": replace(BASE, state="running", closed_at=None, session_dead=False),
    "running, dead signal but fresh heartbeat": replace(
        BASE, state="running", closed_at=None, session_dead=True, heartbeat_age_s=DAY
    ),
    "resumable": replace(BASE, state="resumable"),
    "done 10 min ago, no seat write": replace(BASE, closed_at=NOW - 10 * MIN),
    "done 2 h ago, a seat wrote after the close": replace(
        BASE, closed_at=NOW - 2 * HOUR, seat_write_after_close=True
    ),
    "done 2 h ago, the seat check unreadable": replace(
        BASE, closed_at=NOW - 2 * HOUR, seat_write_after_close=None
    ),
    "a holder (fd or cwd) inside": replace(BASE, held=True),
    "a non-empty proc gaps list": replace(BASE, gaps=True),
    "the holder probe did not complete": replace(BASE, probe_ok=False),
    "a registered worktree inside": replace(BASE, worktree=True),
    "a top-level .keep": replace(BASE, keep=True),
    "no marker": replace(BASE, state=None),
    "an unknown state string": replace(BASE, state="paused"),
    "done with closed_at missing": replace(BASE, closed_at=None),
    "D3: marker sid differs from its directory": replace(BASE, sid_matches=False),
}

CONSUMED_CASES = {
    "done 40 min ago, no seat write": replace(BASE, closed_at=NOW - 40 * MIN),
    "done 37 h ago, a seat wrote after the close": replace(
        BASE, closed_at=NOW - 37 * HOUR, seat_write_after_close=True
    ),
    "running, dead session, heartbeat 8 days old": replace(
        BASE, state="running", closed_at=None, session_dead=True, heartbeat_age_s=8 * DAY
    ),
}


@pytest.mark.parametrize("name", sorted(ACTIVE_CASES))
def test_each_active_condition_alone_reads_active(name: str) -> None:
    verdict, reason = sw.classify_run_folder(ACTIVE_CASES[name], NOW)
    assert verdict == "active", (name, reason)
    assert reason, name


@pytest.mark.parametrize("name", sorted(CONSUMED_CASES))
def test_consumed_cases_read_consumed(name: str) -> None:
    verdict, reason = sw.classify_run_folder(CONSUMED_CASES[name], NOW)
    assert verdict == "consumed", (name, reason)


def _inv1_holds(f) -> bool:
    """Spec INV-1, restated independently of the implementation (the oracle)."""
    if f.state not in ("running", "done", "resumable"):
        return True
    if f.state == "resumable":
        return True
    if f.state == "running" and not (f.session_dead and f.heartbeat_age_s > 7 * DAY):
        return True
    if f.state == "done":
        if f.closed_at is None:
            return True
        grace = 30 * MIN if f.seat_write_after_close is False else 36 * HOUR
        if NOW - f.closed_at < grace:
            return True
    return f.held or f.gaps or not f.probe_ok or f.worktree or f.keep or not f.sid_matches


def test_classifier_partitions_the_state_space() -> None:
    """Every combination reads exactly one verdict, `consumed` never coexists with an INV-1
    condition, and every non-INV-1 state with a `done` or dead-`running` marker is `consumed`."""
    states = ["running", "done", "resumable", None, "weird"]
    closed = [None, NOW - 10 * MIN, NOW - 2 * HOUR, NOW - 40 * HOUR]
    seat = [False, True, None]
    hb = [DAY, 8 * DAY]
    flags = list(itertools.product([False, True], repeat=7))
    seen = 0
    for st, ca, sw_after, hb_age in itertools.product(states, closed, seat, hb):
        for dead, held, gaps, probe, wt, keep, sidm in flags:
            f = sw.RunFacts(
                state=st,
                closed_at=ca,
                heartbeat_age_s=hb_age,
                session_dead=dead,
                held=held,
                gaps=gaps,
                probe_ok=probe,
                worktree=wt,
                keep=keep,
                sid_matches=sidm,
                seat_write_after_close=sw_after,
            )
            verdict, _ = sw.classify_run_folder(f, NOW)
            assert verdict in ("active", "consumed"), f
            assert (verdict == "active") == _inv1_holds(f), f
            seen += 1
    assert seen == 5 * 4 * 3 * 2 * 128


@pytest.mark.parametrize(
    ("facts", "want"),
    [
        # spec INV-1: ACTIVE while the close is LESS than the grace old → exactly at it, consumed
        (replace(BASE, closed_at=NOW - 30 * MIN), "consumed"),
        (replace(BASE, closed_at=NOW - 30 * MIN + 1), "active"),
        (replace(BASE, closed_at=NOW - 36 * HOUR, seat_write_after_close=True), "consumed"),
        (replace(BASE, closed_at=NOW - 36 * HOUR + 1, seat_write_after_close=True), "active"),
        # DEAD only on a heartbeat OLDER than 7 days → exactly 7 days is still active
        (
            replace(
                BASE, state="running", closed_at=None, session_dead=True, heartbeat_age_s=7 * DAY
            ),
            "active",
        ),
        (
            replace(
                BASE,
                state="running",
                closed_at=None,
                session_dead=True,
                heartbeat_age_s=7 * DAY + 1,
            ),
            "consumed",
        ),
    ],
)
def test_threshold_boundaries(facts, want: str) -> None:
    """The comparison operators themselves, pinned at each threshold (a `<` turned `<=` reads red)."""
    assert sw.classify_run_folder(facts, NOW)[0] == want


def test_the_threshold_seams_move_the_thresholds(monkeypatch) -> None:
    """P1: SCRATCH_RUN_GRACE_S and SCRATCH_RUN_HEARTBEAT_S really move the 36 h ceiling and the 7 d
    heartbeat (they are test seams; conftest unsets them for every other test)."""
    seat = replace(BASE, closed_at=NOW - 2 * HOUR, seat_write_after_close=True)
    dead = replace(
        BASE, state="running", closed_at=None, session_dead=True, heartbeat_age_s=2 * DAY
    )
    assert sw.classify_run_folder(seat, NOW)[0] == "active"
    assert sw.classify_run_folder(dead, NOW)[0] == "active"
    monkeypatch.setenv("SCRATCH_RUN_GRACE_S", str(HOUR))
    monkeypatch.setenv("SCRATCH_RUN_HEARTBEAT_S", str(DAY))
    assert sw.classify_run_folder(seat, NOW)[0] == "consumed"
    assert sw.classify_run_folder(dead, NOW)[0] == "consumed"


def test_read_owner_tolerates_missing_and_corrupt_markers(tmp_path: Path) -> None:
    folder = tmp_path / "run-x"
    folder.mkdir()
    assert sw.read_owner(folder) is None
    (folder / sw.OWNER_NAME).write_text("{not json", encoding="utf-8")
    assert sw.read_owner(folder) is None
    (folder / sw.OWNER_NAME).write_text("[1, 2]", encoding="utf-8")
    assert sw.read_owner(folder) is None
    (folder / sw.OWNER_NAME).write_text(json.dumps({"state": "done"}), encoding="utf-8")
    assert sw.read_owner(folder) == {"state": "done"}
