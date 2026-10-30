"""The /hibernate hold on the rotation tick (W-6e656dac T06; spec 2026-10-21 § Chosen approach L1-L3).

The minute cron (`claude_rotate.py --battery-tick`) writes its heartbeat and arms the `hibernate` tier of the
`fleet-exhausted` stamp at T-3; only a hibernate lift ends it — the 5-minute tick's three lift paths (a) sleep,
(b) outage, (c) T+30, or the hub's `hibernate.py lift`, which the tick sees and clears. Plus the two
`command_run.py` pieces T06 owns: the step snapshot and `--abandoned-seat`. Every module is this worktree's copy,
loaded by path; the marker verbs run through this worktree's `hibernate.py` (the `CLAUDE_HIBERNATE_PY` seam).
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HIB_PY = REPO / "scripts" / "sysadmin" / "hibernate.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cr = _load("claude_rotate_hibernate_hold", REPO / "scripts" / "sysadmin" / "claude_rotate.py")
hib = _load("hibernate_hold_hib", HIB_PY)
hook = _load("quota_stop_hibernate_hold", REPO / ".claude" / "hooks" / "quota_stop.py")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_command_run import _PROBE, _cr, _start  # noqa: E402 — shared command_run harness

NOW = 1_800_000_000.0
MARK = NOW - 3600.0  # the pause was marked an hour ago …
T = MARK + 600.0  # … with `--deadline 10m`
T3 = T - 180.0


@pytest.fixture
def box(tmp_path, monkeypatch):
    """A fake box: state + lock dirs, a mains-powered battery, one armed self-watch, a settable clock, a stub
    fleet tick whose quota leg reads `box.hot` (None = cool), and a scripted API probe."""
    state, locks, bat, ac = (tmp_path / n for n in ("state", "locks", "BAT1", "AC1"))
    for d in (state, locks, bat, ac):
        d.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    monkeypatch.setenv("CLAUDE_BATTERY_DIR", str(bat))
    monkeypatch.setenv("CLAUDE_AC_DIR", str(ac))
    monkeypatch.setenv("CLAUDE_HIBERNATE_PY", str(HIB_PY))
    monkeypatch.delenv("CLAUDE_BATTERY_HOLD_PCT", raising=False)
    monkeypatch.delenv("CLAUDE_RESUME_GAP_MIN", raising=False)
    b = type("Box", (), {})()
    b.state, b.locks, b.stamp = state, locks, state / "fleet-exhausted"
    b.clock = {"now": NOW}
    b.hot = None
    b.answers: list[bool] = []
    monkeypatch.setattr(cr, "_now", lambda: b.clock["now"])
    monkeypatch.setattr(
        cr, "_api_answers", lambda: b.answers.pop(0) if b.answers else True, raising=False
    )

    def inner(_dirs):
        cr._QUOTA_HOT_THIS_TICK = b.hot
        return 0

    monkeypatch.setattr(cr, "_fleet_dirs", lambda: [tmp_path / "acct"])
    monkeypatch.setattr(cr, "_fleet_tick_inner", inner)

    def power(status: str, pct: int, online: str) -> None:
        (bat / "status").write_text(f"{status}\n")
        (bat / "capacity").write_text(f"{pct}\n")
        (ac / "online").write_text(f"{online}\n")

    b.power = power
    power("Charging", 80, "1")
    fd = os.open(str(locks / "pane1.selfwatch.lock"), os.O_WRONLY | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def mark(at=MARK, deadline=T, lifted=None, path=None):
        m = {"paused_at": at, "words": "test pause"}
        if deadline is not None:
            m["deadline_at"] = deadline
        if lifted is not None:
            m["lifted_at"], m["lift_path"] = lifted, path
        (state / "hibernate.json").write_text(json.dumps(m))

    b.mark = mark
    b.marker = lambda: json.loads((state / "hibernate.json").read_text())
    b.ledger = lambda: (
        [json.loads(x) for x in (state / "rotate-ledger.jsonl").read_text().splitlines()]
        if (state / "rotate-ledger.jsonl").exists()
        else []
    )
    b.lifted = locks / "pane1.holdlifted"

    def last_end(epoch: float) -> None:
        (state / "tick-last-end").write_text(f"{epoch}\n")

    b.last_end = last_end
    yield b
    os.close(fd)


def _tick(box, at: float) -> None:
    box.clock["now"] = at
    assert cr._cmd_tick() == 0


def _cron(box, at: float) -> None:
    box.clock["now"] = at
    assert cr._cmd_battery_tick() == 0


def _in_thread(fn, timeout: float = 20.0) -> None:
    """Run *fn* where a self-deadlock (a second LOCK_EX on the marker lock in one process) shows as a hang."""
    err: list[BaseException] = []

    def run():
        try:
            fn()
        except BaseException as e:  # noqa: BLE001 — re-raised below
            err.append(e)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout)
    assert not t.is_alive(), "the tick blocked on the marker's flock (a self-deadlock)"
    if err:
        raise err[0]


# ── Behavior rows 1-5: the arm and the keep ─────────────────────────────────────────────────────────────────────


def test_the_minute_cron_arms_at_t3_and_always_beats(box):
    """Row 1: T-3 reached, no sleep since the last tick end → the `hibernate` tier and the heartbeat; lifted, T
    past, before T-3, after a sleep, or with no hub `hibernate.py` → the heartbeat only."""
    beat = box.state / "battery-tick-last"
    box.last_end(T3 - 30)
    for name, kw, at, env in (
        ("lifted", {"lifted": MARK + 60, "path": "hub"}, T3 + 10, None),
        ("T past", {}, T + 1, None),
        ("before T-3", {}, T3 - 5, None),
        ("no hub hibernate.py", {}, T3 + 10, "/nonexistent/hibernate.py"),
    ):
        box.mark(**kw)
        if env:
            os.environ["CLAUDE_HIBERNATE_PY"] = env
        try:
            _cron(box, at)
        finally:
            os.environ["CLAUDE_HIBERNATE_PY"] = str(HIB_PY)
        assert not box.stamp.exists(), name
        assert float(beat.read_text()) == at, name
    box.mark()
    beat.write_text(
        f"{T3 + 10 - 10 * 60}\n"
    )  # the minute cron's last beat 10 min ago: the box slept
    _cron(box, T3 + 10)
    assert not box.stamp.exists(), "a box that slept before T-3 is never held after it wakes"
    box.last_end(T3 - 60)
    _cron(box, T3 + 20)  # the previous beat (T3 + 10) is 10 s old
    assert box.stamp.read_text() == "0\nhibernate\n"
    assert float(beat.read_text()) == T3 + 20
    assert any(r["event"] == "hibernate-hold" for r in box.ledger())


@pytest.mark.parametrize(
    "beat_age, armed", [(60, True), (None, True), (600, False)], ids=["fresh", "first", "slept"]
)
def test_the_arm_judges_the_sleep_by_the_minute_crons_own_beat(box, beat_age, armed):
    """F2 (review r1): a dead or wedged */5 tick (`tick-last-end` 16 min old) never stops the T-3 arm while the
    minute cron beat 60 s ago or never beat before; only a beat over 5 min old (the box slept) skips it."""
    box.mark()
    box.last_end(T3 + 10 - 16 * 60)
    beat = box.state / "battery-tick-last"
    if beat_age is not None:
        beat.write_text(f"{T3 + 10 - beat_age}\n")
    _cron(box, T3 + 10)
    assert box.stamp.exists() is armed
    assert float(beat.read_text()) == T3 + 10


@pytest.mark.parametrize(
    "before", ["1800000999\nwalled\n", "0\nbattery\n", "1800000777\nurgent-90\n"]
)
def test_a_standing_stamp_becomes_the_hibernate_tier_with_line_1_kept(box, before):
    """Row 2: a `walled`, `battery` (or `urgent-90`) stamp at T-3 becomes the `hibernate` tier, line 1 raw."""
    box.mark()
    box.last_end(T3 - 60)
    box.stamp.write_text(before)
    _cron(box, T3 + 10)
    assert box.stamp.read_text() == before.split("\n")[0] + "\nhibernate\n"


def test_every_other_clear_keeps_the_hibernate_tier(box, monkeypatch):
    """Row 3: the quota relief and the dwell (`_clear_stamp`), a low battery, and a promise come due all leave the
    `hibernate` tier standing; and a tier the minute cron writes while a clear waits for the marker's flock is
    re-read under that flock and kept, with no self-deadlock."""
    box.mark()
    box.stamp.write_text("1800000000\nhibernate\n")  # line 1 a promise already due
    assert cr._clear_stamp(box.stamp) is False
    box.power("Discharging", 3, "0")
    assert cr._clear_stamp(box.stamp) is False
    assert box.stamp.read_text() == "1800000000\nhibernate\n"
    box.power("Charging", 80, "1")
    # the race: the stamp reads `walled` at the first read; the cron arms while the clear waits for the lock
    box.stamp.write_text("0\nwalled\n")
    real = hib.update_marker

    def cron_wins(home, fn):
        box.stamp.write_text("0\nhibernate\n")
        return real(home, fn)

    monkeypatch.setattr(cr._hibernate_mod(), "update_marker", cron_wins)
    out: dict = {}
    _in_thread(lambda: out.setdefault("v", cr._clear_stamp(box.stamp)))
    assert out["v"] is False and box.stamp.read_text() == "0\nhibernate\n"


def test_the_wall_advisory_leaves_the_hibernate_tier(box, monkeypatch):
    """Row 4: a walled active account with no successor under the `hibernate` stamp — the stamp still reads
    `hibernate`, no broadcast goes out, and the quota leg still records the heat for the lift."""
    box.mark()
    box.stamp.write_text("1800000000\nhibernate\n")
    row = {"email": "a@x", "five_hour": {"utilization": 100.0}, "seven_day": {"utilization": 50.0}}
    sent: list = []
    monkeypatch.setattr(cr, "_active_account_walled", lambda *a, **k: (True, row))
    monkeypatch.setattr(cr, "_pause_state", lambda: None)
    monkeypatch.setattr(cr, "_validated_pick", lambda *a, **k: None)
    monkeypatch.setattr(cr, "_tick_telegram", lambda m: sent.append(m))
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    cr._fleet_active_wall_advisory([row], NOW, 99.0)
    assert box.stamp.read_text() == "1800000000\nhibernate\n"
    assert not sent
    assert cr._QUOTA_HOT_THIS_TICK == cr._STAMP_TIER_WALLED


def test_the_battery_lift_refuses_under_an_unlifted_mark(box):
    """Row 5: mains power and an unlifted mark — the `hibernate` tier stays, and a battery stamp is not lifted."""
    box.mark()
    cr._QUOTA_HOT_THIS_TICK = None
    box.stamp.write_text("0\nhibernate\n")
    cr._battery_lift(NOW)
    assert box.stamp.read_text() == "0\nhibernate\n"
    box.stamp.write_text("0\nbattery\n")
    cr._battery_lift(NOW)
    assert box.stamp.read_text() == "0\nbattery\n" and not box.lifted.exists()


# ── Behavior rows 6-12: the lift leg ────────────────────────────────────────────────────────────────────────────


def test_a_sleep_after_the_mark_lifts_by_a(box):
    """Row 6: a sleep under the hold writes a `resume-wake` row and lifts by (a) — `lifted_at`, `lift_path=sleep`,
    the tier cleared, `.holdlifted hibernate` — inside a thread that would hang on a self-deadlock."""
    box.mark()
    box.stamp.write_text("0\nhibernate\n")
    box.last_end(T3 + 30)  # the lid closed after T-3
    _in_thread(lambda: _tick(box, NOW))
    rows = [r for r in box.ledger() if r["event"] == "resume-wake"]
    assert rows and rows[-1]["site"] == "hibernate" and rows[-1]["gap_from"] == T3 + 30, rows
    m = box.marker()
    assert m["lifted_at"] == NOW and m["lift_path"] == "sleep", m
    assert not box.stamp.exists()
    assert box.lifted.read_text() == f"{int(NOW)} hibernate\n"
    assert any(r["event"] == "hibernate-lift" and r["lift_path"] == "sleep" for r in box.ledger())


def test_a_sleep_under_the_armed_tier_lifts_by_a_when_its_gap_began_before_the_mark(box):
    """F1 (review r1): `--deadline 3m` puts T-3 at the mark, so the last */5 tick before the sleep ended BEFORE
    `paused_at`; the `resume-wake` row written under the armed tier (`site: hibernate`) is still this pause's
    sleep, and the tick lifts by `sleep` — not 30 min past T as `cancelled`."""
    box.mark(deadline=MARK + 180)
    box.last_end(MARK - 60)
    box.stamp.write_text("0\nhibernate\n")
    _tick(box, MARK + 20 * 60)
    m = box.marker()
    assert m.get("lift_path") == "sleep", m
    assert not box.stamp.exists()


def test_a_nap_ending_before_t3_or_a_gap_from_before_the_mark_lifts_nothing(box):
    """Row 6, the other half: a gap that ended before T-3 is a nap; a gap that began before the mark is not this
    pause's sleep — neither lifts."""
    box.mark(deadline=MARK + 3 * 3600)  # T-3 is 2 h 57 min after the mark
    box.last_end(MARK + 30)
    _tick(box, MARK + 30 + 20 * 60)  # a 20-minute nap, ending long before T-3
    assert [r for r in box.ledger() if r["event"] == "resume-wake"], "the nap is still recorded"
    assert "lifted_at" not in box.marker(), "a nap during the drain lifts nothing"
    box.mark(at=MARK + 60, deadline=MARK + 60 + 600)
    (box.state / "rotate-ledger.jsonl").unlink()
    box.last_end(MARK)  # the gap began before this mark (and ends before T+30)
    _tick(box, MARK + 1660)
    assert "lifted_at" not in box.marker(), "a gap that began before the mark lifts nothing"


def test_an_outage_lifts_by_b_only_when_it_starts_at_or_after_t(box):
    """Row 7: an outage that starts and ends before T lifts nothing; one starting after T that lasts two slots
    and is answered three times lifts by (b) — on the third answer, not before."""
    box.mark(deadline=MARK + 2400)  # T = mark + 40 min, so the whole first outage sits before T
    t = MARK + 60
    box.last_end(t - 300)
    for ok in (False, False, True, True, True):  # down two slots, three answers — all before T
        box.answers.append(ok)
        _tick(box, t)
        t += 300
    assert "lifted_at" not in box.marker(), "a blip during the drain lifts nothing"
    t = MARK + 2400 + 60
    box.last_end(t - 300)
    for i, ok in enumerate((False, False, True, True, True)):
        box.answers.append(ok)
        _tick(box, t)
        if i < 4:
            assert "lifted_at" not in box.marker(), i
        t += 300
    m = box.marker()
    assert m["lift_path"] == "outage", m


@pytest.mark.parametrize("deadline", [T, None], ids=["deadline", "no-deadline"])
def test_t_plus_30_lifts_by_c(box, deadline):
    """Row 8: with neither a sleep nor an outage the pause lifts by (c) at T+30 — T the mark itself when no
    deadline was set — and not a tick before."""
    box.mark(deadline=deadline)
    t_ = deadline if deadline is not None else MARK
    box.last_end(t_ + 1500)
    _tick(box, t_ + 1790)
    assert "lifted_at" not in box.marker()
    _in_thread(lambda: _tick(box, t_ + 1800))
    m = box.marker()
    assert m["lift_path"] == "cancelled" and m["lifted_at"] == t_ + 1800, m
    assert box.lifted.read_text() == f"{int(t_ + 1800)} hibernate\n"


@pytest.mark.parametrize("hot, low, to", [("walled", False, "walled"), (None, True, "battery")])
def test_a_lift_into_a_hot_quota_or_a_low_battery_wakes_nobody(box, hot, low, to):
    """Row 9: the lift while the quota is hot or the battery low hands the stamp to that tier (line 1 kept), the
    marker still records the lift, and nobody is woken."""
    box.mark()
    box.stamp.write_text("1800000999\nhibernate\n")
    box.hot = hot
    if low:
        box.power("Discharging", 3, "0")
    box.last_end(T + 1800 - 60)
    _tick(box, T + 1800)
    assert box.marker()["lift_path"] == "cancelled"
    assert box.stamp.read_text() == f"1800000999\n{to}\n"
    assert not box.lifted.exists()


def test_a_hub_lift_clears_the_tier_within_one_tick(box):
    """Row 10 (and residue R2): the hub lifted the mark while the tier stands — before the tick quota_stop still
    reads HIBERNATE HOLD; one tick later the tier is gone and `.holdlifted hibernate` is written."""
    box.mark(lifted=NOW - 30, path="hub")
    box.stamp.write_text("0\nhibernate\n")
    action, reason = hook.decide(
        "Edit",
        None,
        stamp_exists=True,
        tick_age_s=10.0,
        tier=hook._stamp_tier(box.stamp),
        hibernate=hook._stamp_is_hibernate(box.stamp),
        pause_marked=hook._pause_marked(),
    )
    assert action == "deny" and "HIBERNATE HOLD" in reason  # R2, the before state
    box.last_end(NOW - 300)
    _in_thread(lambda: _tick(box, NOW))
    assert not box.stamp.exists()
    assert box.lifted.read_text() == f"{int(NOW)} hibernate\n"
    seen = [r for r in box.ledger() if r["event"] == "hibernate-lift"]
    assert seen and seen[-1]["lift_path"] == "hub" and seen[-1]["seen_by"] == "tick", seen
    assert hook.decide("Edit", None, stamp_exists=box.stamp.exists(), tick_age_s=10.0)[0] == "allow"


def test_a_migration_lift_clears_without_waking(box):
    """The migration marker (`lifted_at` = `paused_at`, `lift_path=migration`) wakes nobody."""
    box.mark(lifted=MARK, path="migration")
    box.stamp.write_text("0\nhibernate\n")
    box.last_end(NOW - 300)
    _tick(box, NOW)
    assert not box.stamp.exists() and not box.lifted.exists()


def test_the_hibernate_fan_out_replaces_a_pending_resume_only(box):
    """Row 11: a pending `.holdlifted resume` reads `hibernate` after the lift fans out; a pending battery lift is
    left as it was. The lid closed before T-3 here, so no tier was armed and the resume wake ran first."""
    box.mark()
    box.last_end(MARK + 120)
    _tick(box, NOW)  # the resume wake writes `<now> resume`, then the lift by (a) replaces it
    assert box.marker()["lift_path"] == "sleep"
    assert box.lifted.read_text() == f"{int(NOW)} hibernate\n"
    box.lifted.write_text("1 battery\n")
    cr._wake_held_sessions(NOW, cr._STAMP_TIER_HIBERNATE, True)
    assert box.lifted.read_text() == "1 battery\n"


def test_a_hibernate_lift_row_ends_no_quota_episode(box):
    """Row 12: a `hold-lifted` row with `site: hibernate` leaves the open `fleet-active-wall` episode open."""
    (box.state / "rotate-ledger.jsonl").write_text(
        json.dumps({"event": "fleet-active-wall", "ts": NOW - 60, "account": "a@x"}) + "\n"
    )
    cr._wake_held_sessions(NOW, cr._STAMP_TIER_HIBERNATE, True)
    assert any(r.get("site") == "hibernate" for r in box.ledger())
    assert cr._open_wall_episode("a@x", NOW)[0] is not None


# ── Interfaces S and H: the seam tests ──────────────────────────────────────────────────────────────────────────


def test_the_hooks_hold_on_the_tier_the_arm_writes(box):
    """Interface S (row 16): the stamp the minute cron writes holds a world-changing tool in `quota_stop`, a stale
    tick log included, with the HIBERNATE text."""
    box.mark()
    box.last_end(T3 - 60)
    _cron(box, T3 + 10)
    assert hook._stamp_is_hibernate(box.stamp) and hook._pause_marked()
    action, reason = hook.decide(
        "Edit",
        None,
        stamp_exists=box.stamp.exists(),
        tick_age_s=86400.0 * 3,  # days old: the fail-open would otherwise open it
        tier=hook._stamp_tier(box.stamp),
        hibernate=hook._stamp_is_hibernate(box.stamp),
        pause_marked=hook._pause_marked(),
    )
    assert action == "deny" and reason.startswith("HIBERNATE HOLD"), (action, reason)


def test_the_hibernate_hold_text_orders_the_pause_close_not_the_wall(box):
    """F5 (review r1): under the HIBERNATE head the close clause is `blocked --paused` (or `handoff`), as the pause
    banner and the posture hook say — never `blocked --wall`; it names the tick's lift, the pause verbs that stay
    allowed, and that T-3 has passed. The walled and battery heads keep `blocked --wall`."""
    text = hook._reason("Edit", None, hibernate=True)
    assert "blocked --paused" in text and "handoff" in text, text
    assert "blocked --wall" not in text, text
    assert "the tick" in text and "T-3 has passed" in text, text
    for verb in ("status", "woke", "paused"):
        assert f"hibernate.py {verb}`" in text, verb
    assert "blocked --wall" in hook._reason("Edit", None)
    assert "blocked --wall" in hook._reason("Edit", None, battery=True)


def test_status_reads_the_heartbeat_the_minute_cron_writes(box):
    """Interface H (row 17): `hibernate.py status`'s check passes on the heartbeat the cron just wrote and blocks on
    one 3 minutes old."""
    home = box.state.parent
    _cron(box, NOW)
    assert hib._minute_cron_alive(home, NOW + 5) is True
    assert hib._minute_cron_alive(home, NOW + 181) is False


# ── Behavior rows 13-14: command_run.py ─────────────────────────────────────────────────────────────────────────


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    d = tmp_path / "command-runs"
    d.mkdir()
    return d


def _snapshot_env(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    log = tmp_path / "snapshot.log"
    stub = tmp_path / "wip_backup_stub.sh"
    stub.write_text(f'#!/bin/sh\necho "only=$WIP_BACKUP_ONLY" >> {log}\n')
    stub.chmod(0o755)
    lock = tmp_path / "wip-backup.lock"
    return (
        {"FABRIK_STEP_SNAPSHOT_BIN": str(stub), "FABRIK_STEP_SNAPSHOT_LOCK": str(lock)},
        log,
        lock,
    )


def _wait_lines(log: Path, n: int, timeout: float = 10.0) -> list[str]:
    end = time.time() + timeout
    while time.time() < end:
        if log.exists() and len(log.read_text().splitlines()) >= n:
            break
        time.sleep(0.05)
    return log.read_text().splitlines() if log.exists() else []


def test_a_step_starts_one_detached_snapshot_per_two_minutes(run_dir, tmp_path):
    """Row 13: a `step` in a repo with a snapshot binary starts one detached single-repo `wip_backup.sh` run; a
    second step inside 2 minutes starts none; with the cron's lock held none starts."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=15)
    env, log, lock = _snapshot_env(tmp_path)
    _start(run_dir)
    rec_path = run_dir / "s1.json"
    rec = json.loads(rec_path.read_text())
    rec["repo_root"] = str(repo)
    rec_path.write_text(json.dumps(rec))
    out = _cr(run_dir, "step", "--phase", "2", "--title", "a", extra_env=env)
    assert out.returncode == 0, out.stdout + out.stderr
    assert _wait_lines(log, 1) == [f"only={repo}"]
    out = _cr(run_dir, "step", "--phase", "3", "--title", "b", extra_env=env)
    assert out.returncode == 0, out.stdout + out.stderr
    time.sleep(0.5)
    assert log.read_text().splitlines() == [f"only={repo}"], "at most once per 2 minutes per repo"
    for stamp in (run_dir / "step-snapshot").iterdir():
        os.utime(stamp, (time.time() - 300, time.time() - 300))
    fd = os.open(str(lock), os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        out = _cr(run_dir, "step", "--phase", "4", "--title", "c", extra_env=env)
        assert out.returncode == 0, out.stdout + out.stderr
        time.sleep(0.5)
        assert len(log.read_text().splitlines()) == 1, "the cron's lock held → no snapshot"
    finally:
        os.close(fd)


def test_a_step_without_the_seam_spawns_nothing_under_test(run_dir, tmp_path):
    """Row 13, the seam: with no `FABRIK_STEP_SNAPSHOT_BIN` a step under pytest never reaches the live script."""
    _start(run_dir)
    out = _cr(run_dir, "step", "--phase", "2", extra_env={"PYTEST_CURRENT_TEST": "x"})
    assert out.returncode == 0, out.stdout + out.stderr
    assert not (run_dir / "step-snapshot").exists()


def test_a_paused_close_records_its_abandoned_seats_in_record_and_seed(run_dir, tmp_path):
    """Row 14: `blocked --paused` with two `--abandoned-seat` values — the record and its seed both carry
    `abandoned_seats` with both entries, in the names `hibernate.py woke` reads (`pid`, `purpose`, `brief`,
    `output`, `procStart`); `procStart` is read from /proc for a live pid and null for a dead one."""
    _start(run_dir)
    live = os.getpid()
    out = _cr(
        run_dir,
        "blocked",
        "--command",
        _PROBE,
        "--paused",
        "--reason",
        "operator: hibernate",
        "--abandoned-seat",
        f"{live}|review seat A|/s/brief-a.md|/s/out-a.md",
        "--abandoned-seat",
        "999999999|review seat B|/s/brief-b.md|/s/out-b.md",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    rec = json.loads((run_dir / "s1.json").read_text())
    seed = json.loads(Path(rec["resume_seed"]).read_text())
    for doc in (rec, seed):
        seats = doc["abandoned_seats"]
        assert [s["purpose"] for s in seats] == ["review seat A", "review seat B"], seats
        assert set(seats[0]) == {"pid", "purpose", "brief", "output", "procStart"}
        assert seats[0]["pid"] == live and seats[0]["procStart"] == hib._proc_start(
            Path("/proc"), live
        )
        assert seats[1]["procStart"] is None and seats[1]["output"] == "/s/out-b.md"
    lines = hib._seed_lines(Path("/proc"), Path(rec["resume_seed"]))
    assert any("seat review seat A: still running" in x for x in lines), lines


@pytest.mark.parametrize("value", ["notapid|x", "²|x|y|z"], ids=["short", "unicode-digit"])
def test_a_malformed_abandoned_seat_is_refused(run_dir, value):
    """Row 14, the mirror: a value without four `|` fields, or a pid that is no decimal number (`²` passes
    `isdigit()`), refuses the close with the documented line and leaves the run running."""
    _start(run_dir)
    out = _cr(
        run_dir,
        "blocked",
        "--command",
        _PROBE,
        "--paused",
        "--reason",
        "operator: hibernate",
        "--abandoned-seat",
        value,
    )
    assert out.returncode != 0
    assert "REFUSED — --abandoned-seat" in out.stdout, out.stdout + out.stderr
    assert json.loads((run_dir / "s1.json").read_text())["state"] == "running"
