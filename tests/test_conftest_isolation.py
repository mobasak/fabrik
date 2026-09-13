"""The test session must never touch the box's REAL resume-mesh lock dir.

Measured 2026-09-07 (the relief-wake plan's docs-review): a reader ran the rotate suites and three
LIVE sessions' `<sid>.holdlifted` files appeared in `/tmp/claude-sound-locks-<uid>/` with the tests'
fixed clock (`1800000000` — 2027-01-15) as the lift epoch, and the author's own freshly-armed
self-watch printed a bogus `RESUME: the fleet-quota hold LIFTED at 11:00` line. Cause: every fleet
test that reaches the relief/dwell unlink of `_fleet_active_wall_advisory` now calls
`_wake_held_sessions`, which enumerates `_selfwatch_lock_dir()` — the REAL dir unless
`CLAUDE_SOUND_LOCKDIR` is set — so the plan's own seven tests that set it (two setenv sites in the fleet suite,
three in rotate_v2) were the exception, not the rule.
The class fix is the autouse fixture in `tests/conftest.py` (same shape as its git-env scrub):
every test, existing and future, runs with the variable pinned to a per-test tmp dir. This grader
asserts that pin is in force for an arbitrary test and that the tick's resolver honours it.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

_REAL_LOCK_DIR = Path(f"/tmp/claude-sound-locks-{os.getuid()}")


def _load_rotate():
    src = Path(__file__).resolve().parents[1] / "scripts" / "sysadmin" / "claude_rotate.py"
    spec = importlib.util.spec_from_file_location("claude_rotate_isolation_probe", src)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_every_test_runs_with_an_isolated_sound_lock_dir(tmp_path_factory):
    pinned = os.environ.get("CLAUDE_SOUND_LOCKDIR")
    assert pinned, "CLAUDE_SOUND_LOCKDIR is unset inside a test — the conftest autouse pin is gone"
    assert Path(pinned).resolve() != _REAL_LOCK_DIR.resolve(), pinned
    assert Path(pinned).resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), pinned


def test_the_tick_resolves_the_lock_dir_to_the_pin_not_the_box(tmp_path_factory):
    cr = _load_rotate()
    resolved = cr._selfwatch_lock_dir().resolve()
    assert resolved != _REAL_LOCK_DIR.resolve(), resolved
    assert resolved.is_relative_to(tmp_path_factory.getbasetemp().resolve()), resolved


def test_every_bare_mkdtemp_lands_under_pytest_basetemp(tmp_path_factory):
    """Measured 2026-09-07: four hub tests call `tempfile.mkdtemp()` with no cleanup, and the
    suites run by three sessions and their readers left 4,072 `/tmp/tmp*` dirs (2.2 GB) in one
    day. The class fix is the conftest autouse pin of `tempfile.tempdir` under pytest's basetemp,
    which pytest prunes (it keeps the last three sessions) — no per-test edit, every existing and
    future bare `mkdtemp()`/`NamedTemporaryFile()` covered."""
    import tempfile

    made = Path(tempfile.mkdtemp())
    assert made.resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), made
    with tempfile.NamedTemporaryFile() as fh:
        assert Path(fh.name).resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), (
            fh.name
        )


def test_kaizen_events_dir_is_pinned_under_basetemp(tmp_path):
    """F349: a test that spawns command_run.py with a hand-built env inherits this pin, so no
    fabricated event reaches ~/.claude/state/events/<live sid>.jsonl."""
    import os
    from pathlib import Path

    d = os.environ.get("KAIZEN_EVENTS_DIR")
    assert d, "KAIZEN_EVENTS_DIR is not pinned"
    assert Path(d).resolve().is_relative_to(tmp_path.resolve().parent), d
    # the invariant, not the fixture (round-17 Opus finding): a hand-built env inherits the pin
    # and the writer honours it at call time — the event lands under tmp, nowhere else
    import subprocess
    import sys

    env = dict(os.environ, COMMAND_RUN_DIR=str(tmp_path / "runs"), CLAUDE_SESSION_ID="pin-probe")
    script = Path(__file__).resolve().parents[1] / "scripts" / "command_run.py"
    # the pin is already inherited (`dict(os.environ)`); what the grader's own RED path must sandbox
    # is the writer's FALLBACK — a child that ignores KAIZEN_EVENTS_DIR falls back to
    # `Path.home()/.claude/state/events`, so HOME goes under tmp too (D-191 review round 19: with a
    # writer mutated to ignore the env, the old explicit line still deposited pin-probe.jsonl in the
    # real dir before the assertion fired). HOME also relocates `.active-account`; the other two
    # seams a hand-built env must force are the transcript and an ambient CLAUDE_AGENT.
    env["HOME"] = str(tmp_path / "home")
    (tmp_path / "home").mkdir(exist_ok=True)
    env["COMMAND_RUN_TRANSCRIPT"] = str(tmp_path / "no-transcript.jsonl")
    env.pop("CLAUDE_AGENT", None)
    cp = subprocess.run(
        [
            sys.executable,
            str(script),
            "start",
            "--command",
            "fabrik-features",
            "--phases",
            "1",
            "--terminal",
            "t",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stderr
    written = list(Path(d).glob("*.jsonl"))
    assert written and any("pin-probe" in w.name for w in written), written


def test_the_suite_never_reads_the_operators_live_run_record(tmp_path) -> None:
    """Round 3 (B3-S1): the graders read the session's own run record, so the conftest pins a
    scratch COMMAND_RUN_DIR and a fixed fake session id for every test — a suite run inside a live
    Claude session must never grade fixtures against the operator's real record."""
    d = os.environ.get("COMMAND_RUN_DIR", "")
    assert d and Path(d).resolve().is_relative_to(tmp_path.resolve().parent), d  # under basetemp
    assert os.environ.get("CLAUDE_SESSION_ID") == "pytest-isolated"
    assert "CLAUDE_CODE_SESSION_ID" not in os.environ
