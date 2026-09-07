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
        assert Path(fh.name).resolve().is_relative_to(tmp_path_factory.getbasetemp().resolve()), fh.name
