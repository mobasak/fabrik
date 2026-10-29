"""The battery hold (W-83a8ee68, D-898): on battery at or below the hold line every agent stops like
at the quota wall, and mains power lifts it.

The hold rides the quota hold's own `fleet-exhausted` stamp with a third tier line, `battery`, so
every reader of that stamp holds on it with no change of its own; these tests drive the tick side —
`claude_rotate.py`'s arm, lift and the quota leg's clear — against fake BAT1/AC1 dirs.
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "claude_rotate_battery", REPO / "scripts" / "sysadmin" / "claude_rotate.py"
)
cr = importlib.util.module_from_spec(spec)
sys.modules["claude_rotate_battery"] = cr
spec.loader.exec_module(cr)

_HOOK = REPO / ".claude" / "hooks" / "quota_stop.py"
_hspec = importlib.util.spec_from_file_location("quota_stop_battery", _HOOK)
hook = importlib.util.module_from_spec(_hspec)
_hspec.loader.exec_module(hook)

NOW = 1_800_000_000.0


@pytest.fixture
def box(tmp_path, monkeypatch):
    """A fake box: state dir, self-watch lock dir, BAT1 and AC1 dirs; returns a setter."""
    state = tmp_path / "state"
    locks = tmp_path / "locks"
    bat = tmp_path / "BAT1"
    ac = tmp_path / "AC1"
    for d in (state, locks, bat, ac):
        d.mkdir()
    monkeypatch.setenv("ROTATE_STATE_DIR", str(state))
    monkeypatch.setenv("CLAUDE_SOUND_LOCKDIR", str(locks))
    monkeypatch.setenv("CLAUDE_BATTERY_DIR", str(bat))
    monkeypatch.setenv("CLAUDE_AC_DIR", str(ac))
    monkeypatch.delenv("CLAUDE_BATTERY_HOLD_PCT", raising=False)

    def set_power(status: str | None, pct: int | None, online: str | None = "0") -> None:
        for name, val in (("status", status), ("capacity", pct)):
            p = bat / name
            if val is None:
                p.unlink(missing_ok=True)
            else:
                p.write_text(f"{val}\n")
        if online is None:
            (ac / "online").unlink(missing_ok=True)
        else:
            (ac / "online").write_text(f"{online}\n")

    box = type("Box", (), {})()
    box.state, box.locks, box.set_power = state, locks, set_power
    box.stamp = state / "fleet-exhausted"
    return box


def _hold_lock(path: Path) -> int:
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd


def _ledger(state: Path) -> list[dict]:
    p = state / "rotate-ledger.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def _deny(stamp: Path) -> str:
    return hook.decide(
        "Edit", None, stamp_exists=stamp.exists(), tick_age_s=10.0, tier=hook._stamp_tier(stamp)
    )[0]


def test_low_battery_arms_the_hold(box):
    """Discharging at or below the line with no stamp, or with a softer `urgent-90` stamp, arms
    a battery-tier stamp, and the hook then holds an Edit."""
    box.set_power("Discharging", 7)
    cr._battery_arm(NOW)
    assert box.stamp.read_text() == "0\nbattery\n"
    assert _deny(box.stamp) == "deny"
    assert any(r.get("event") == "battery-hold" for r in _ledger(box.state))
    box.stamp.write_text("0\nurgent-90\n")  # the quota's LANE tier: no all-session hold
    assert (
        hook.decide("Edit", None, stamp_exists=True, tick_age_s=10.0, tier="urgent-90")[0] != "deny"
    )
    cr._battery_arm(NOW)
    assert box.stamp.read_text() == "0\nbattery\n", "the battery raises an urgent-90 stamp"
    box.stamp.unlink()
    box.set_power("Unknown", 5, online="0")  # a driver that says Unknown on battery
    cr._battery_arm(NOW)
    assert box.stamp.read_text() == "0\nbattery\n", "Unknown with AC offline is battery power"
    box.stamp.unlink()
    box.set_power("Discharging", 4, online="1")  # a stuck AC flag beside a draining battery
    cr._battery_arm(NOW)
    assert box.stamp.read_text() == "0\nbattery\n", "Discharging arms whatever AC1 says"


def test_no_hold_unless_discharging_at_the_line(box):
    """Charging at 5%, Discharging at 8%, an unreadable battery: no stamp. A standing `walled`
    quota stamp is left exactly as it is — it already holds."""
    for status, pct, online in (
        ("Charging", 5, "0"),
        ("Discharging", 8, "0"),
        (None, None, "0"),
        ("Discharging", None, "0"),
        ("Unknown", 5, None),  # Unknown with no AC reading: no evidence of battery power
        ("Unknown", 5, "1"),
    ):
        box.set_power(status, pct, online=online)
        cr._battery_arm(NOW)
        assert not box.stamp.exists(), (status, pct)
    box.set_power("Discharging", 3)
    box.stamp.write_text("1800000999\nwalled\n")
    cr._battery_arm(NOW)
    assert box.stamp.read_text() == "1800000999\nwalled\n"


def test_mains_power_lifts_and_wakes(box):
    """Mains — AC1 online, or a Charging/Full/Not charging status — clears the battery stamp and
    wakes every armed self-watch with a lift that names the battery; `Unknown` keeps the hold."""
    fd = _hold_lock(box.locks / "s1.selfwatch.lock")
    try:
        box.stamp.write_text("0\nbattery\n")
        box.set_power("Unknown", 6, online="0")
        cr._battery_lift(NOW)
        assert box.stamp.exists(), "Unknown is not mains — the hold keeps"
        assert not (box.locks / "s1.holdlifted").exists()
        box.set_power("Unknown", 6, online="1")
        cr._battery_lift(NOW)
        assert not box.stamp.exists()
        assert (box.locks / "s1.holdlifted").read_text() == f"{int(NOW)} battery\n"
        for status in ("Charging", "Full", "Not charging"):
            (box.locks / "s1.holdlifted").unlink()
            box.stamp.write_text("0\nbattery\n")
            box.set_power(status, 6, online="0")
            cr._battery_lift(NOW)
            assert not box.stamp.exists(), status
            assert (box.locks / "s1.holdlifted").exists(), status
        box.stamp.write_text("1800000999\nwalled\n")  # a QUOTA stamp is not the battery's to lift
        cr._battery_lift(NOW)
        assert box.stamp.read_text() == "1800000999\nwalled\n"
    finally:
        os.close(fd)


def test_arm_and_lift_never_disagree(box, monkeypatch):
    """The class behind two review rounds: the arm and the lift each kept their own power rule and
    disagreed, so a reading could arm the hold and lift it in the same tick. Over every status ×
    AC1 combination at 4%, one battery leg either holds or not — never both, and a lift only on
    mains."""
    monkeypatch.setattr(cr, "_QUOTA_HOT_THIS_TICK", None)
    # the EXPECTED power, written out — never `_power_state` itself, which would grade a wrong rule
    # against itself: a definite battery status wins, else AC1 decides (1 mains, 0 battery, else unknown)
    by_ac = {"1": "mains", "0": "battery", None: "unknown"}
    expected = {
        **{("Discharging", ac): "battery" for ac in by_ac},
        **{(s, ac): "mains" for s in ("Charging", "Full", "Not charging") for ac in by_ac},
        **{(s, ac): want for s in ("Unknown", "Odd") for ac, want in by_ac.items()},
    }
    for status in ("Discharging", "Charging", "Full", "Not charging", "Unknown", "Odd"):
        for online in ("0", "1", None):
            box.stamp.unlink(missing_ok=True)
            box.set_power(status, 4, online=online)
            cr._battery_leg(NOW, lift=True)
            power = expected[(status, online)]
            if power == "battery":
                assert box.stamp.read_text() == "0\nbattery\n", (status, online, "must hold")
            else:
                assert not box.stamp.exists(), (status, online, power, "must not hold")
            box.stamp.write_text("0\nbattery\n")
            cr._battery_lift(NOW)
            assert box.stamp.exists() == (power != "mains"), (status, online, power)


def test_quota_relief_keeps_a_battery_hold(box):
    """The quota leg's clears (relief and dwell both go through `_clear_stamp`) keep a battery
    stamp, and while the battery is low they turn a quota stamp into a battery stamp — neither
    tells the caller the hold went, so neither wakes anyone."""
    box.stamp.write_text("0\nbattery\n")
    box.set_power("Charging", 50, online="1")  # even on mains: only the battery lift lifts it
    assert cr._clear_stamp(box.stamp) is False
    assert box.stamp.read_text() == "0\nbattery\n"
    box.stamp.write_text("1800000999\nwalled\n")
    box.set_power("Discharging", 4)
    assert cr._clear_stamp(box.stamp) is False
    assert box.stamp.read_text() == "0\nbattery\n"
    box.set_power("Discharging", 40)
    box.stamp.write_text("1800000999\nwalled\n")
    assert cr._clear_stamp(box.stamp) is True, "a quota stamp on a healthy battery clears as before"
    assert not box.stamp.exists()


def test_battery_leg_survives_a_broken_tick(box, monkeypatch):
    """A quota tick that raises (the class `_cmd_tick`'s guard exists for) still arms the battery
    hold, and still lifts it."""

    def boom(*_a, **_k):
        raise RuntimeError("corrupt ledger")

    monkeypatch.setattr(cr, "_fleet_dirs", lambda: [Path("x")])
    monkeypatch.setattr(cr, "_fleet_tick_inner", boom)
    box.set_power("Discharging", 5)
    assert cr._cmd_tick() == 0
    assert box.stamp.read_text() == "0\nbattery\n"
    box.set_power("Charging", 5, online="1")
    assert cr._cmd_tick() == 0
    assert box.stamp.exists(), "a broken quota tick read nothing — the lift must not wake into it"

    def cool(_dirs):
        cr._QUOTA_HOT_THIS_TICK = None  # the advisory found the active account cool
        return 0

    monkeypatch.setattr(cr, "_fleet_tick_inner", cool)
    assert cr._cmd_tick() == 0
    assert not box.stamp.exists(), "a healthy tick on mains lifts it"


def test_lift_into_a_quota_wall_wakes_nobody(box, monkeypatch):
    """Mains while the quota leg found the active account walled THIS tick: the stamp becomes the
    quota's and nobody is woken into the wall; and a battery lift's `hold-lifted` row ends no
    open quota episode (it is skipped like `site: dwell`)."""
    fd = _hold_lock(box.locks / "s1.selfwatch.lock")
    try:
        box.stamp.write_text("0\nbattery\n")
        box.set_power("Charging", 30, online="1")
        # the quota leg never read the account this tick (a blackout, a raise): the hold KEEPS
        monkeypatch.setattr(cr, "_QUOTA_HOT_THIS_TICK", cr._QUOTA_UNKNOWN)
        cr._battery_lift(NOW)
        assert box.stamp.read_text() == "0\nbattery\n"
        assert not (box.locks / "s1.holdlifted").exists()
        monkeypatch.setattr(cr, "_QUOTA_HOT_THIS_TICK", cr._STAMP_TIER_WALLED)
        cr._battery_lift(NOW)
        assert cr._stamp_tier(box.stamp) == cr._STAMP_TIER_WALLED
        assert not cr._stamp_is_battery(box.stamp)
        assert not (box.locks / "s1.holdlifted").exists()
    finally:
        os.close(fd)
    led = box.state / "rotate-ledger.jsonl"
    led.write_text(
        json.dumps({"event": "fleet-active-wall", "ts": NOW - 60, "account": "a@x"})
        + "\n"
        + json.dumps({"event": "hold-lifted", "ts": NOW - 30, "site": "battery"})
        + "\n"
    )
    rows, ok = cr._open_wall_rows(NOW)
    assert ok and "a@x" in rows, "a battery lift is not the quota episode's end"


def _fleet_row(email: str, session: float | None, weekly: float | None) -> dict:
    return {
        "email": email,
        "slugs": [email.split("@")[0]],
        "source": "live",
        "weekly_cap": None,
        "five_hour": {"utilization": session, "resets_at_epoch": NOW + 3600},
        "seven_day": {"utilization": weekly, "resets_at_epoch": NOW + 86400},
    }


def test_a_wall_under_a_battery_hold_mails_once_and_sets_the_quota_flag(box, monkeypatch):
    """The real advisory, end to end: under a battery stamp a wall still mails ONCE (the episode's
    ledger row latches it, not the battery stamp's presence), the stamp stays the battery's while
    the battery is low, and the advisory tells the lift the quota's state — walled, cool on a real
    reading, or (a blackout) left unknown."""
    tg: list[str] = []
    monkeypatch.setattr(cr, "_resolve_active", lambda: "act")
    monkeypatch.setattr(cr, "_switch_paused", lambda: False)
    monkeypatch.setattr(cr, "_validated_pick", lambda accts, excl, **kw: None)
    monkeypatch.setattr(cr, "_tick_telegram", lambda m: tg.append(m))
    monkeypatch.setattr(cr, "_drain_mail", lambda repos, m: None)
    monkeypatch.setattr(cr, "_mailbox_repos", lambda: [])
    box.set_power("Discharging", 5)
    box.stamp.write_text("0\nbattery\n")
    os.utime(box.stamp, (NOW, NOW))  # a FRESH stamp: a presence latch would read it as latched
    walled = [_fleet_row("act@x", 100.0, 40.0)]
    monkeypatch.setattr(cr, "_QUOTA_HOT_THIS_TICK", cr._QUOTA_UNKNOWN)
    cr._fleet_active_wall_advisory(walled, NOW, threshold=95.0)
    assert len(tg) == 1, "the wall mails during a battery hold"
    assert cr._QUOTA_HOT_THIS_TICK == cr._STAMP_TIER_WALLED
    assert cr._stamp_is_battery(box.stamp), "on a low battery the stamp stays the battery's"
    cr._fleet_active_wall_advisory(walled, NOW + 60, threshold=95.0)
    assert len(tg) == 1, "the episode's ledger row latches it — one mail per wall"
    monkeypatch.setattr(cr, "_QUOTA_HOT_THIS_TICK", cr._QUOTA_UNKNOWN)
    cr._fleet_active_wall_advisory([_fleet_row("act@x", None, None)], NOW + 120, threshold=95.0)
    assert cr._QUOTA_HOT_THIS_TICK == cr._QUOTA_UNKNOWN, "a blackout is not a cool reading"
    cr._fleet_active_wall_advisory([_fleet_row("act@x", 20.0, 40.0)], NOW + 180, threshold=95.0)
    assert cr._QUOTA_HOT_THIS_TICK is None
    assert cr._stamp_is_battery(box.stamp), "quota relief keeps the battery hold"
