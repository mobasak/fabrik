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


def test_the_two_stale_bound_parses_agree_on_every_bad_value(monkeypatch):
    """R8: the Stop hook hand-copies quota_stop's `_stale_after_s`; nothing bound them. This does."""
    import importlib.util as _ilu

    hooks = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
    mods = {}
    for name in ("quota_stop", "final_gate_stop"):
        spec = _ilu.spec_from_file_location(name, hooks / f"{name}.py")
        m = _ilu.module_from_spec(spec)
        spec.loader.exec_module(m)
        mods[name] = m
    qs = mods["quota_stop"]
    for raw in ("", "0", "-1", "abc", "nan", "inf", "-inf", "900", "15m"):
        monkeypatch.setenv("QUOTA_STOP_TICK_STALE_S", raw)
        a = qs._stale_after_s()
        try:
            b = float(raw)
        except ValueError:
            b = 900.0
        if not __import__("math").isfinite(b):
            b = 900.0
        assert a == b, (raw, a, b)  # the hook inlines exactly this shape


# --- W-37003fa1: the urgent-90 tier enforces the checkpoint, once per episode ----------------------
#
# D-306 split the stamp into two tiers and only `walled` denies the tools that clear these causes.
# At `urgent-90` every tool works and the tier ORDERS commit, push and a current run record — so the
# hook blocks ONCE per session per urgent episode with every true checkpoint item listed, and stands
# every other cause down with its debt named. A counter at cap 1 per cause would not do that: each
# warn-through re-arms the counter (7 blocks in a row, executed by the design critique).

_GATE_MARK = """#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path(os.environ["GATE_RAN"]).write_text("ran")
fails = [f for f in os.environ.get("FAKE_FAILS", "").split(",") if f]
print(json.dumps({"status": "failure" if fails else "success", "failures": [{"check": c} for c in fails]}))
sys.exit(1 if fails else 0)
"""


def _git(p: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=p,
        check=True,
        timeout=15,
        capture_output=True,
    )


def _later_iso() -> str:
    import datetime as _dt

    return (_dt.datetime.now(_dt.UTC) + _dt.timedelta(seconds=60)).isoformat()


def _transcript(p: Path, *files: str) -> Path:
    """A transcript in which THIS session wrote `files` — stamped a minute ahead, so the session
    floor (an edit older than the baseline is a resumed transcript's) keeps them."""
    tr = p / "transcript.jsonl"
    rows = [
        json.dumps(
            {
                "type": "assistant",
                "timestamp": _later_iso(),
                "message": {
                    "content": [
                        {"type": "tool_use", "name": "Write", "input": {"file_path": str(p / f)}}
                    ]
                },
            }
        )
        for f in files
    ]
    tr.write_text("\n".join(rows) + "\n")
    return tr


class _Urgent:
    """One project, one quota state, one session id; `stop()` runs the real hook as a subprocess."""

    def __init__(self, tmp_path: Path, sid: str) -> None:
        self.tmp = tmp_path
        self.sid = sid
        self.p = tmp_path / "proj"
        (self.p / "scripts").mkdir(parents=True)
        (self.p / "scripts" / "final_gate.py").write_text(_GATE_MARK)
        _git(self.p, "init", "-q", "-b", "master")
        self.state = tmp_path / "state"
        self.state.mkdir()
        self.runs = tmp_path / "runs"
        self.runs.mkdir()
        self.events = tmp_path / "events"
        self.gate_ran = tmp_path / "gate-ran"
        self.tick = self.state / "rotate-tick.log"
        self.tick.write_text("tick\n")
        self.tier("0\nurgent-90\n")
        import tempfile

        self.bl = Path(tempfile.gettempdir()) / f"fabrik-gate-baseline-{sid}.json"
        self.ctr = Path(tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.attempts"
        self.side = Path(tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.urgent"
        for f in (self.ctr, self.side):
            f.unlink(missing_ok=True)

    def tier(self, body: str, *, fresh: bool = True) -> None:
        stamp = self.state / "fleet-exhausted"
        if stamp.is_dir():
            stamp.rmdir()
        stamp.write_text(body)
        old = time.time() - (0 if fresh else 4000)
        os.utime(self.tick, (old, old))

    def baseline(self, checks: list[str]) -> None:
        self.bl.write_text(json.dumps(checks))

    def stop(self, *, fails: str = "", transcript: Path | None = None) -> tuple[str, str]:
        self.gate_ran.unlink(missing_ok=True)
        env = {
            **os.environ,
            "FAKE_FAILS": fails,
            "GATE_RAN": str(self.gate_ran),
            "ROTATE_STATE_DIR": str(self.state),
            "QUOTA_STOP_TICK_LOG": str(self.tick),
            "COMMAND_RUN_DIR": str(self.runs),
            "KAIZEN_EVENTS_DIR": str(self.events),
        }
        env.pop("QUOTA_STOP_TICK_STALE_S", None)
        payload = {"session_id": self.sid, "cwd": str(self.p), "hook_event_name": "Stop"}
        if transcript is not None:
            payload["transcript_path"] = str(transcript)
        r = subprocess.run(
            [sys.executable, str(_HOOK)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        return r.stdout.strip(), r.stderr

    def events_of(self) -> list[dict]:
        f = self.events / f"{self.sid}.jsonl"
        return (
            [json.loads(x) for x in f.read_text().splitlines() if x.strip()] if f.exists() else []
        )

    def close(self) -> None:
        for f in (self.bl, self.ctr, self.side):
            f.unlink(missing_ok=True)


@pytest.fixture
def urgent(tmp_path: Path, request):
    u = _Urgent(tmp_path, f"urg-{request.node.name[-40:]}")
    yield u
    u.close()


def test_urgent_tier_blocks_uncommitted_once_per_episode(urgent) -> None:
    """The tier orders a commit: a file this session wrote and never committed blocks ONCE — with
    the urgent prefix and the file named — then the next two stops end the turn. A new episode
    (the hold left the urgent tier, then came back) blocks once again."""
    urgent.baseline([])
    (urgent.p / "mine.py").write_text("session work")
    tr = _transcript(urgent.p, "mine.py")
    out, _ = urgent.stop(transcript=tr)
    assert out, "uncommitted work must block at the urgent tier"
    reason = json.loads(out)["reason"]
    assert reason.startswith("FLEET QUOTA AT THE URGENT TIER"), reason
    assert "mine.py" in reason and "commit" in reason.lower(), reason
    assert urgent.stop(transcript=tr)[0] == "", (
        "one block per episode — the second stop ends the turn"
    )
    assert urgent.stop(transcript=tr)[0] == "", (
        "and the third (a re-arming counter would block here)"
    )
    urgent.tier("0\nwalled\n")
    assert urgent.stop(transcript=tr)[0] == "", "the wall yields everything"
    urgent.tier("0\nurgent-90\n")
    assert urgent.stop(transcript=tr)[0], "a new urgent episode blocks once again"


def test_urgent_tier_record_remedy_is_step_not_finish(urgent) -> None:
    """The tier orders a CURRENT run record (`command_run.py step|round`), not a finished one — the
    normal run-record reason ('run it to that terminal condition') would order the very quota burn
    the tier exists to stop."""
    urgent.baseline([])
    rec = {
        "session_id": urgent.sid,
        "command": "fabrik-review",
        "phases": 5,
        "phase": 4,
        "phase_title": "Converge",
        "terminal": "found:0",
        "state": "running",
        "rounds": [],
        "classes": {},
        "updated_ts": int(time.time()),
    }
    (urgent.runs / f"{urgent.sid}.json").write_text(json.dumps(rec))
    out, _ = urgent.stop()
    assert out, "a running record must be named at the urgent tier"
    reason = json.loads(out)["reason"]
    assert reason.startswith("FLEET QUOTA AT THE URGENT TIER"), reason
    assert "command_run.py step" in reason and "/fabrik-review" in reason, reason
    assert "run it to that terminal condition" not in reason, reason
    assert urgent.stop()[0] == "", "one block per episode"


def test_urgent_tier_blocks_unpushed_once(urgent, tmp_path: Path) -> None:
    """The tier orders a push: a commit this session authored that is not on origin blocks once."""
    p = urgent.p
    (p / "base.txt").write_text("x")
    _git(p, "add", "base.txt", "scripts/final_gate.py")
    _git(p, "commit", "-qm", "base")
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "master", str(bare)], check=True, timeout=15
    )
    _git(p, "remote", "add", "origin", str(bare))
    _git(p, "push", "-qu", "origin", "master")
    (p / "mine.py").write_text("session work")
    _git(p, "add", "mine.py")
    _git(p, "commit", "-qm", "mine")
    tr = _transcript(p, "mine.py")
    urgent.baseline([])
    out, _ = urgent.stop(transcript=tr)
    assert out and "push" in out.lower(), out
    assert json.loads(out)["reason"].startswith("FLEET QUOTA AT THE URGENT TIER"), out
    assert urgent.stop(transcript=tr)[0] == ""


def test_urgent_tier_stands_heavy_causes_down_without_running_the_gate(urgent) -> None:
    """Nothing the checkpoint orders is true — only a red gate and unreviewed work — so the turn
    ends, the gate (a full subprocess) is never run, and the unreviewed work is recorded as
    `stood_down` with the tier. A stale tick (the hold is OFF) is the control: it enforces."""
    urgent.baseline(["A"])
    (urgent.p / "dirt.txt").write_text("someone else's")  # a dirty tree, authored by nobody here
    out, _ = urgent.stop(fails="A,B")
    assert out == "", f"urgent-90 must not block on a red gate: {out!r}"
    assert not urgent.gate_ran.exists(), "the gate was run at the urgent tier"
    urgent.tier("0\nurgent-90\n", fresh=False)
    out, _ = urgent.stop(fails="A,B")
    assert out and "DEFINITION OF DONE" in out, f"control: a stale tick holds nothing: {out!r}"


def test_urgent_tier_records_stood_down_causes(urgent, tmp_path: Path) -> None:
    """Committed AND pushed work this session never reviewed: no checkpoint item, so no block — but
    the review it still owes is a kaizen `stood_down` with the tier, not silence."""
    p = urgent.p
    (p / "mine.py").write_text("session work")
    _git(p, "add", "mine.py", "scripts/final_gate.py")
    _git(p, "commit", "-qm", "mine")
    bare = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "master", str(bare)], check=True, timeout=15
    )
    _git(p, "remote", "add", "origin", str(bare))
    _git(p, "push", "-qu", "origin", "master")
    tr = _transcript(p, "mine.py")
    urgent.baseline([])
    out, _ = urgent.stop(transcript=tr)
    assert out == "", out
    rows = urgent.events_of()
    assert any(
        r.get("event") == "stop_block"
        and r.get("cause") == "unreviewed-spontaneous"
        and r.get("outcome") == "stood_down"
        and r.get("tier") == "urgent-90"
        for r in rows
    ), rows
    assert not any(r.get("event") == "stop_allowed_quota_hold" for r in rows), (
        "that event is the wall's"
    )


def test_walled_and_unreadable_tiers_still_yield_everything(urgent) -> None:
    """The wall keeps D-158's full yield, and so does every stamp that does not PLAINLY say urgent:
    pre-tier, a wrong case, a directory. The yield event is the wall's alone."""
    urgent.baseline(["A"])
    (urgent.p / "dirt.txt").write_text("x")
    for body in ("0\nwalled\n", "0", "0\nUrgent-90\n"):
        urgent.tier(body)
        assert urgent.stop(fails="A,B")[0] == "", body
    stamp = urgent.state / "fleet-exhausted"
    stamp.unlink()
    stamp.mkdir()
    assert urgent.stop(fails="A,B")[0] == "", "an unreadable stamp reads as the wall"
    assert any(r.get("event") == "stop_allowed_quota_hold" for r in urgent.events_of())


def _hook_module():
    import importlib.util as _iu

    spec = _iu.spec_from_file_location("final_gate_stop_urgent_probe", _HOOK)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def checkpoint(tmp_path: Path, monkeypatch):
    """`_urgent_checkpoint` with every probe stubbed: only a RUNNING record is true, and the
    sidecar lives in tmp_path — so each grader below varies exactly one input."""
    mod = _hook_module()
    monkeypatch.setenv("KAIZEN_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setattr(mod, "_dirty_paths", lambda root: set())
    monkeypatch.setattr(mod, "_ahead_of_upstream", lambda *a, **k: 0)
    monkeypatch.setattr(
        mod, "_run_record", lambda sid: {"state": "running", "command": "fabrik-review"}
    )
    monkeypatch.setattr(mod, "_seats_in_flight", lambda rec, tp: False)
    monkeypatch.setattr(mod, "_unreviewed_spontaneous_files", lambda *a, **k: [])
    monkeypatch.setattr(mod, "_merge_owner_duty", lambda root, sid: None)
    monkeypatch.setattr(mod, "_run_record_raw", lambda sid: None)
    side = tmp_path / "side.urgent"
    monkeypatch.setattr(mod, "_urgent_sidecar", lambda sid: side)

    def run(sid: str = "s-real") -> str | None:
        return mod._urgent_checkpoint(tmp_path, sid, sid, {}, [], None, "")

    return mod, run, side, monkeypatch


def test_urgent_checkpoint_honours_seats_in_flight(checkpoint) -> None:
    """Review A-S2: a running record whose own seats are verifiably in flight is not owed a step
    this turn — the same `run_blocks` predicate `_stall_gate` uses (W-4c7edc74)."""
    mod, run, side, mp = checkpoint
    mp.setattr(mod, "_seats_in_flight", lambda rec, tp: True)
    assert run() is None, "seats in flight: the record is not a checkpoint item"
    mp.setattr(mod, "_seats_in_flight", lambda rec, tp: False)
    assert run(), "control: with no seats out the running record blocks"


def test_urgent_checkpoint_fails_open_when_the_sidecar_cannot_be_written(
    checkpoint, tmp_path
) -> None:
    """Review A-H2: an unwritable sidecar must not turn "once per episode" into "every stop"."""
    mod, run, side, mp = checkpoint
    mp.setattr(mod, "_urgent_sidecar", lambda sid: tmp_path / "no-such-dir" / "side.urgent")
    assert run() is None, (
        "the block fired with no sidecar to remember it — it would fire every stop"
    )


def test_urgent_checkpoint_never_blocks_an_id_less_session(checkpoint) -> None:
    """Review A-S3: every id-less payload is `nosession`, so its sidecar would be SHARED — one
    session's block would silently stand down another's. An id-less stop never blocks here."""
    mod, run, side, mp = checkpoint
    assert run("nosession") is None
    assert not side.exists()
    assert run("s-real"), "control: a real session id blocks"


# --- W-117b1916: the checkpoint verifies the relief wake's precondition — an ARMED self-watch -----
#
# The tick's relief wake (`.holdlifted`) reaches only a session whose selfwatch.lock is held, and one
# arm is one wake (D-356). So at urgent-90 and at the wall the Stop orders the background arm,
# once per consumption, while the lock is free.

_REPO = Path(__file__).resolve().parents[1]


class _Armable(_Urgent):
    def __init__(self, tmp_path: Path, sid: str) -> None:
        super().__init__(tmp_path, sid)
        self.home = tmp_path / "home"
        (self.home / ".claude" / "bin").mkdir(parents=True)
        (self.home / ".claude" / "bin" / "claude-selfwatch.sh").write_text("#!/bin/sh\n")
        self.locks = tmp_path / "locks"
        self.locks.mkdir()
        self.hub = str(_REPO)
        self.fd: int | None = None
        import tempfile

        self.arm_side = Path(tempfile.gettempdir()) / f"fabrik-gate-stop-{sid}.urgent-arm"
        self.arm_side.unlink(missing_ok=True)

    def hold(self) -> None:
        import fcntl

        self.fd = os.open(str(self.locks / f"{self.sid}.selfwatch.lock"), os.O_WRONLY | os.O_CREAT)
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def stop(self, *, fails: str = "", transcript: Path | None = None) -> tuple[str, str]:
        extra = {
            "HOME": str(self.home),
            "CLAUDE_SOUND_LOCKDIR": str(self.locks),
            "FABRIK_HUB_ROOT": self.hub,
            "SELFWATCH_OPT_ROOT": str(self.tmp),
        }
        saved = {k: os.environ.get(k) for k in extra}
        for k in ("CLAUDE_MESH_HEADLESS", "FABRIK_HEADLESS", "CLAUDE_MESH_AUTONOMOUS"):
            saved.setdefault(k, os.environ.get(k))
            os.environ.pop(k, None)
        os.environ.update(extra)
        try:
            return super().stop(fails=fails, transcript=transcript)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def close(self) -> None:
        self.release()
        self.arm_side.unlink(missing_ok=True)
        super().close()


@pytest.fixture
def armable(tmp_path: Path, request):
    a = _Armable(tmp_path, f"arm-{request.node.name[-40:]}")
    a.baseline([])
    yield a
    a.close()


def test_urgent_tier_orders_the_self_watch_arm_when_unarmed(armable) -> None:
    out, _ = armable.stop()
    assert out, "an unarmed session at urgent-90 must be told to arm before it pauses"
    assert "selfwatch_arm.sh" in out and armable.sid in out and "run_in_background" in out, out
    assert armable.stop()[0] == "", "once per consumption — the next stop ends the turn"


def test_urgent_tier_is_silent_about_the_arm_when_armed(armable) -> None:
    armable.hold()
    assert armable.stop()[0] == "", "an armed clean session ends its turn"
    armable.release()
    assert "selfwatch_arm.sh" in armable.stop()[0], "the arm was consumed: one more block"
    armable.hold()
    assert armable.stop()[0] == "" and not armable.arm_side.exists(), "armed clears the arm sidecar"


def test_a_consumed_arm_blocks_once_more_in_the_same_episode(armable) -> None:
    armable.hold()
    (armable.p / "mine.py").write_text("session work")
    tr = _transcript(armable.p, "mine.py")
    first, _ = armable.stop(transcript=tr)
    assert "COMMIT" in first and "selfwatch_arm.sh" not in first, first
    armable.release()  # the watch woke on something else and died — one wake per arm
    second, _ = armable.stop(transcript=tr)
    assert "selfwatch_arm.sh" in second and "COMMIT" not in second, second
    assert armable.stop(transcript=tr)[0] == ""


def test_the_wall_orders_the_arm_once_then_yields(armable) -> None:
    armable.tier("0\nwalled\n")
    out, _ = armable.stop()
    assert "selfwatch_arm.sh" in out and armable.sid in out, out
    assert armable.stop()[0] == "", "then the D-158 yield"


def test_the_arm_check_fails_open(armable) -> None:
    armable.hub = str(armable.tmp / "no-hub")
    assert armable.stop()[0] == "", "an unloadable hub module adds nothing"


def test_an_unarmed_session_with_work_owed_gets_one_block_naming_both(armable) -> None:
    """The arm rides the episode's one checkpoint block — commit AND arm in a single block, then
    silence; never a second block for the arm alone."""
    (armable.p / "mine.py").write_text("session work")
    tr = _transcript(armable.p, "mine.py")
    first, _ = armable.stop(transcript=tr)
    assert "COMMIT" in first and "selfwatch_arm.sh" in first, first
    assert armable.stop(transcript=tr)[0] == "", "both items were in the one block"


def test_a_hub_module_that_exits_at_import_never_costs_the_checkpoint(armable) -> None:
    hub = armable.tmp / "bad-hub"
    (hub / "scripts" / "sysadmin").mkdir(parents=True)
    (hub / "scripts" / "sysadmin" / "selfwatch_check.py").write_text("raise SystemExit(3)\n")
    armable.hub = str(hub)
    (armable.p / "mine.py").write_text("session work")
    out, _ = armable.stop(transcript=_transcript(armable.p, "mine.py"))
    assert "COMMIT" in out, out


def test_the_arm_debt_is_always_in_the_kaizen_stream(armable) -> None:
    """The arm rides the block's `items`; an arm-only block still records the other debts as stood
    down; a spent arm at the wall records `stood_down cause=unarmed`."""
    (armable.p / "mine.py").write_text("session work")
    tr = _transcript(armable.p, "mine.py")
    armable.stop(transcript=tr)
    first = [e for e in armable.events_of() if e.get("cause") == "urgent-checkpoint"]
    assert first and "unarmed" in first[-1].get("items", []), first
    armable.side.unlink()  # a later episode-block spent, the arm still owed: arm-only
    armable.arm_side.unlink()
    armable.side.write_text("x")
    armable.stop(transcript=tr)
    ev = armable.events_of()
    assert any(e.get("cause") == "uncommitted" and e.get("outcome") == "stood_down" for e in ev), ev
    armable.tier("0\nwalled\n")
    armable.stop(transcript=tr)
    assert any(
        e.get("cause") == "unarmed"
        and e.get("outcome") == "stood_down"
        and e.get("tier") == "walled"
        for e in armable.events_of()
    ), armable.events_of()


def test_a_session_that_never_arms_keeps_the_episode_text_unchanged(urgent) -> None:
    """Round-2 review N1: the arm-only clause describes a block only an armable session can earn; a
    skipped session (real HOME, cwd outside /opt) keeps HEAD's episode sentence byte for byte."""
    (urgent.p / "mine.py").write_text("session work")
    out, _ = urgent.stop(transcript=_transcript(urgent.p, "mine.py"))
    reason = json.loads(out)["reason"]
    assert "This block fires ONCE per episode — after the checkpoint" in reason, reason


def test_an_arm_only_block_after_a_failed_sidecar_records_the_arm_once(armable) -> None:
    """Round-2 review N2: when the episode sidecar cannot be written the arm falls to the arm-only
    block — `unarmed` is recorded once, as blocked, never also as stood down."""
    armable.side.unlink(missing_ok=True)
    armable.side.symlink_to(armable.tmp / "no-such-dir" / "side")
    try:
        (armable.p / "mine.py").write_text("session work")
        out, _ = armable.stop(transcript=_transcript(armable.p, "mine.py"))
        assert "selfwatch_arm.sh" in out, out
        unarmed = [e for e in armable.events_of() if e.get("cause") == "unarmed"]
        assert [e.get("outcome") for e in unarmed] == ["blocked"], unarmed
    finally:
        armable.side.unlink(missing_ok=True)


@pytest.mark.parametrize(
    "line2,oauth,blocked",
    [
        ("walled", "", True),
        ("urgent-90", "", True),
        ("battery", "", False),
        ("walled", "sk-ant-oat01-x", False),
    ],
)
def test_an_api_key_session_keeps_its_stop_causes_at_a_quota_tier(
    held_project, monkeypatch, line2, oauth, blocked
):
    """W-effb7141: the quota hold does not bind an API-key session, so the session keeps editing —
    and its definition-of-done causes stay armed (the NORMAL path), never the wall's yield. The
    battery hold binds it, so there the yield stands."""
    project, state = held_project
    (state / "fleet-exhausted").write_text(f"0\n{line2}\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-x")
    if oauth:  # a plan login beside the key: held, so the wall's yield stands
        monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", oauth)
    out = _run_stop(project, state, f"s_key_{line2}_{bool(oauth)}", "A,B")
    assert (out != "") is blocked, out
