"""The Stop decider's lock-dir prune must never delete a file another process holds a flock on.

Measured 2026-09-07 (heavy review of the relief-wake plan): `acquire_lock()` prunes EVERY file in
the lock dir older than two hours by mtime. A self-watch's `<sid>.selfwatch.lock` is a 0-byte file
whose mtime never changes while the watcher holds its flock, so every watch older than two hours
lost its lock file at the next Stop of ANY session — 25 of the 30 live watcher processes on the box
held a deleted inode, invisible to the rotation tick's armed census (the relief wake could not
reach them) and to `selfwatch_check.py` (which then ordered a duplicate arm every two hours).
The rule: a flock-held file is LIVE, whatever its mtime — probe with LOCK_SH|LOCK_NB and skip it.
"""

from __future__ import annotations

import fcntl
import importlib.util
import os
import sys
import time
from pathlib import Path


def _load_decider(lock_dir: Path):
    os.environ["CLAUDE_SOUND_LOCKDIR"] = str(lock_dir)
    src = Path.home() / ".claude" / "bin" / "claude-stop-decider.py"
    spec = importlib.util.spec_from_file_location("claude_stop_decider_prune_probe", src)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules.pop("claude_stop_decider_prune_probe", None)
    spec.loader.exec_module(mod)
    return mod


def _old(path: Path) -> None:
    path.touch()
    stale = time.time() - 3 * 3600
    os.utime(path, (stale, stale))


def test_the_prune_spares_a_flock_held_lock_but_still_prunes_litter(tmp_path):
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    mod = _load_decider(lock_dir)
    held = lock_dir / "abc.selfwatch.lock"
    litter = lock_dir / "old.recheck"
    _old(held)
    _old(litter)
    fd = os.open(held, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # the watcher's shape: exec 9>lock; flock -n 9
        mod.acquire_lock("prune-probe")
    finally:
        os.close(fd)
    assert held.exists(), "a flock-held lock file older than 2h was pruned — the orphaned-watch class"
    assert not litter.exists(), "an unheld stale file must still be pruned"


def test_an_unheld_stale_selfwatch_lock_is_still_litter(tmp_path):
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    mod = _load_decider(lock_dir)
    stale = lock_dir / "gone.selfwatch.lock"
    _old(stale)
    mod.acquire_lock("prune-probe")
    assert not stale.exists(), "a lock file nobody holds is litter and must go"
