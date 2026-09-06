"""Behavior Contract — the Stop hook must NOT block a session the quota hold has frozen.

Incident 2026-09-06: the fleet ran out of quota, `quota_stop.py` held every write tool, and
infra ran on until "You've hit your session limit" instead of stopping. The hold was not
missing — it fires at the 90% drain tier — and it was not late. The gap is that the two hooks
do not know about each other:

  * `quota_stop.py` DENIES the tools needed to clear the Stop hook's causes. `final_gate.py`
    is not in its allowed Bash set at all, so the "gate red on session-authored files" cause
    can never be cleared while the hold stands; `/fabrik-review-scoped` needs tools too.
  * `final_gate_stop.py` BLOCKS end-of-turn on those causes and knew nothing about the stamp.

So a held session with a red gate or unreviewed edits was blocked from stopping and blocked
from fixing. Every block emits another assistant turn, and turns burn quota even when every
tool is denied — the session talks its way into the wall while obeying the hold.

The hold has ALREADY ordered a graceful stop and the agent has already been told to commit and
push. Once the stamp is up, letting the turn END is the whole point.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_HOOK = REPO / ".claude" / "hooks" / "final_gate_stop.py"

_FAKE_GATE = """#!/usr/bin/env python3
import json, os, sys
fails = [f for f in os.environ.get("FAKE_FAILS", "").split(",") if f]
if not fails:
    print(json.dumps({"status": "success", "failures": []})); sys.exit(0)
print(json.dumps({"status": "failure", "failures": [{"check": c} for c in fails]}))
sys.exit(1)
"""


@pytest.fixture
def held_project(tmp_path: Path) -> tuple[Path, Path]:
    p = tmp_path / "proj"
    (p / "scripts").mkdir(parents=True)
    (p / "scripts" / "final_gate.py").write_text(_FAKE_GATE)
    subprocess.run(["git", "init", "-q"], cwd=p, check=True, timeout=15)
    (p / "work.txt").write_text("uncommitted")  # a dirty tree = a blocking cause
    state = tmp_path / "state"
    state.mkdir()
    return p, state


def _run_stop(project: Path, state: Path, sid: str, fails: str, tick: str | None = None) -> str:
    """A BASELINE must exist or the hook fails open on attribution and never blocks — which is
    how the control below caught this fixture being vacuous the first time."""
    import tempfile

    bl = Path(tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
    ctr = Path(tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
    ctr.unlink(missing_ok=True)
    bl.write_text(json.dumps(["A"]))  # A is inherited; anything else is NEW → blocks
    env = {**os.environ, "FAKE_FAILS": fails, "ROTATE_STATE_DIR": str(state)}
    # P1-5: after A-F1 the yield needs a FRESH tick log; without one of its own this suite
    # silently depended on the host's live rotation cron (green only while the cron ran within
    # 900 s). A test's own fresh tick, unless the test set one deliberately (the A-F1 graders).
    if tick is None:
        fresh = state / "tick.log"
        fresh.write_text("fresh")
        tick = str(fresh)
    env["QUOTA_STOP_TICK_LOG"] = tick  # never the host's — a dead cron must not red this suite
    try:
        proc = subprocess.run(
            [sys.executable, str(_HOOK)],
            input=json.dumps({"session_id": sid, "cwd": str(project), "hook_event_name": "Stop"}),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        return proc.stdout.strip()
    finally:
        bl.unlink(missing_ok=True)
        ctr.unlink(missing_ok=True)


def test_the_stop_hook_blocks_normally_when_no_hold_is_in_force(held_project):
    """The control. Without this the exemption test cannot tell 'exempted' from 'never blocked'."""
    project, state = held_project
    assert not (state / "fleet-exhausted").exists()
    out = _run_stop(project, state, "s_nohold", "A,B")
    assert out != "", "the Stop hook must still block a red gate when no hold is in force"


def test_a_quota_held_session_is_allowed_to_stop(held_project):
    """THE FIX. With the stamp up, the session cannot run final_gate.py (quota_stop denies it),
    so the cause is unclearable — blocking only produces more turns, and turns cost the quota
    that is already gone."""
    project, state = held_project
    (state / "fleet-exhausted").write_text("0")
    out = _run_stop(project, state, "s_held", "A,B")
    assert out == "", f"a quota-held session was blocked from stopping: {out}"


def test_a_stale_stamp_with_a_dead_tick_does_not_yield(held_project, monkeypatch):
    """A-F1 (CRITICAL, fleet-wide): quota_stop fails OPEN when the tick log is older than
    QUOTA_STOP_TICK_STALE_S (900 s) — tools come back — but this hook yielded on the stamp's mere
    EXISTENCE, so a dead cron + a leftover stamp disabled all six Stop causes indefinitely while no
    hold was in force. Yield only when the hold is genuinely in force: stamp AND a fresh tick."""
    project, state = held_project
    (state / "fleet-exhausted").write_text("0")
    tick = state / "rotate-tick.log"
    tick.write_text("tick\n")
    import os as _os

    old = time.time() - 2000
    _os.utime(tick, (old, old))
    out = _run_stop(project, state, "s_stale", "A,B", tick=str(tick))
    assert out != "", "a stale stamp (hold OFF) must not disable the Stop hook"


def test_a_stamp_with_a_fresh_tick_yields(held_project, monkeypatch):
    project, state = held_project
    (state / "fleet-exhausted").write_text("0")
    tick = state / "rotate-tick.log"
    tick.write_text("tick\n")
    assert _run_stop(project, state, "s_fresh", "A,B", tick=str(tick)) == ""


def test_a_nan_stale_bound_reads_as_held_on_both_sides(held_project, monkeypatch):
    """P1-6: `quota_stop.py` decides "off" with `age > stale`, which is False under NaN — the hold
    stays IN FORCE (tools denied). This hook's `age <= stale` was also False under NaN → no yield
    → every cause armed while nothing could run: the exact deadlock A-F1 exists to end. Same
    expression shape on both sides now."""
    project, state = held_project
    (state / "fleet-exhausted").write_text("0")
    monkeypatch.setenv("QUOTA_STOP_TICK_STALE_S", "nan")
    out = _run_stop(project, state, "s_nan", "A,B")
    assert out == "", f"a held session (NaN bound) was blocked from stopping: {out}"


def test_a_nan_stale_bound_with_a_dead_tick_does_not_yield(held_project, monkeypatch):
    """P3-6: under a NaN bound the earlier P1-6 fix made BOTH sides read the hold as in force
    forever — a dead cron froze the fleet AND disarmed the Stop hook. Non-finite is the 900 s
    default on both sides: a stale tick is a hold OFF, and this hook does not yield."""
    import os as _os

    project, state = held_project
    (state / "fleet-exhausted").write_text("0")
    tick = state / "old-tick.log"
    tick.write_text("tick\n")
    old = 10**9
    _os.utime(tick, (old, old))
    monkeypatch.setenv("QUOTA_STOP_TICK_STALE_S", "nan")
    assert _run_stop(project, state, "s_nan_dead", "A,B", tick=str(tick)) != ""
