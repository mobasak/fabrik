"""scripts/merge_request.py — one owner-test leg on the box at a time (W-fbd1d4b9).

Two repos' merge legs together pushed the load average to 19-25 on 24 cores and a 2-file hub merge to
1344 s (MR 01M670WHMM). `_run_owner_leg` holds a box-wide flock (`_box_leg_lock`) around the leg; the
conftest pins its path per test (FABRIK_MERGE_LEG_LOCK), so these drive a private lock file.
"""

from __future__ import annotations

import fcntl
import importlib.util
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "merge_request.py"


def _load():
    spec = importlib.util.spec_from_file_location("merge_request_leg_lock", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load()


def _ctx(tmp_path: Path):
    return mod._Ctx(tmp_path, tmp_path / ".git", "infra")


def _hold(path: Path, text: str = "pid 1 in /opt/other\n"):
    """Another leg holding the box's lock: an fd with the flock and the holder line, as the lock writes it."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    fcntl.flock(fd, fcntl.LOCK_EX)
    os.pwrite(fd, text.encode(), 0)
    return fd


def test_the_lock_path_is_box_wide_unless_pinned(monkeypatch):
    monkeypatch.delenv(mod.LEG_LOCK_ENV, raising=False)
    assert mod._leg_lock_path() == Path.home() / ".claude" / "state" / "merge-test-leg.lock"


def test_a_second_leg_waits_for_the_first_then_runs(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(mod, "LEG_LOCK_POLL_S", 0.05)
    fd = _hold(mod._leg_lock_path())
    entered = threading.Event()

    def leg():
        with mod._box_leg_lock(_ctx(tmp_path)):
            entered.set()

    t = threading.Thread(target=leg)
    t.start()
    time.sleep(0.3)
    assert not entered.is_set()  # held elsewhere: the second leg waits
    os.close(fd)
    t.join(5)
    assert entered.is_set()
    assert (
        "waiting for the box's one test leg — held by pid 1 in /opt/other"
        in capsys.readouterr().err
    )
    # the holder line names the run that now holds it
    assert mod._leg_lock_path().read_text().startswith(f"pid {os.getpid()} in {tmp_path}")


def test_a_wait_that_spends_the_budget_is_not_a_test_verdict(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "LEG_LOCK_POLL_S", 0.05)
    fd = _hold(mod._leg_lock_path())
    ctx = _ctx(tmp_path)
    ctx.test_deadline = time.monotonic() + mod.LEG_FLOOR_S + 0.2
    try:
        with pytest.raises(mod.BudgetSpentError, match="waiting for the box's one test leg"):
            with mod._box_leg_lock(ctx):
                pytest.fail("entered a lock another leg holds")
    finally:
        os.close(fd)


def test_inside_a_leg_the_lock_is_not_taken_again(tmp_path, monkeypatch):
    fd = _hold(mod._leg_lock_path())
    monkeypatch.setenv(mod.LEG_HELD_ENV, "1")
    try:
        with mod._box_leg_lock(_ctx(tmp_path)):
            pass  # would wait out the budget if it took the lock its parent leg holds
    finally:
        os.close(fd)


@pytest.mark.parametrize("script", ["echo $FABRIK_MERGE_LEG_HELD", ""])
def test_the_leg_runs_under_the_lock_and_tells_its_children(tmp_path, monkeypatch, script):
    seen = {}

    def fake_run(argv, timeout, cwd=None, env=None):
        probe = os.open(mod._leg_lock_path(), os.O_RDWR)
        try:
            with pytest.raises(BlockingIOError):  # the leg holds the box's lock while it runs
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(probe)
        seen["held"] = (env or {}).get(mod.LEG_HELD_ENV)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(mod, "_run", fake_run)
    monkeypatch.setattr(mod, "_capped", lambda argv, timeout, mem=None: argv)
    touched = [] if script else ["tests/test_x.py"]
    mod._run_owner_leg(_ctx(tmp_path), tmp_path, script, touched)
    assert seen["held"] == "1"
    # released after: the next leg takes it at once
    fd = os.open(mod._leg_lock_path(), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    finally:
        os.close(fd)


def test_a_child_that_outlives_the_leg_does_not_keep_the_lock(tmp_path):
    """The lock's fd is close-on-exec: a leg's straggler would otherwise hold the box's lock after it."""
    with mod._box_leg_lock(_ctx(tmp_path)):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"], close_fds=False
        )
    try:
        fd = os.open(mod._leg_lock_path(), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # BlockingIOError if the child kept it
        finally:
            os.close(fd)
    finally:
        child.kill()
        child.wait()
