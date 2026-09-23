"""The self-watch arm wrapper (D-356): one background Bash task per arm, exiting on the watcher's first line.

Driven against a stub watcher that takes the same per-sid flock the real one does and, like it, keeps a child
`sleep` holding the lock fd — the shape that made a naive wrapper leave the lock held past the wake.
"""

from __future__ import annotations

import fcntl
import os
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARM = ROOT / "scripts" / "sysadmin" / "selfwatch_arm.sh"

STUB = """#!/usr/bin/env bash
exec 9>"$LOCKDIR/$1.selfwatch.lock"
flock -n 9 || { echo "self-watch already armed for $1 — this duplicate exits; the standing watch stays"; exit 0; }
while [ ! -f "$LOCKDIR/$1.errparked" ]; do sleep 0.1; done
rm -f "$LOCKDIR/$1.errparked"; echo "RESUME: woke $1 — this self-watch STAYS ARMED (standing watch: do NOT re-arm; a duplicate arm exits at once)"
while :; do sleep 30; done
"""


def _env(tmp: Path) -> dict:
    stub = tmp / "watch.sh"
    stub.write_text(STUB)
    return {
        "PATH": "/usr/bin:/bin",
        "LOCKDIR": str(tmp),
        "SELFWATCH_BIN": str(stub),
        "HOME": str(tmp),
    }


def _held(lock: Path) -> bool:
    with lock.open("a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fh, fcntl.LOCK_UN)
        return False


def _arm(tmp: Path) -> subprocess.Popen:
    return subprocess.Popen(
        ["bash", str(ARM), "S1"],
        env=_env(tmp),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def _stop(proc: subprocess.Popen) -> None:
    """Kill the arm's whole process group — the wrapper, the watcher and its sleep — so no stub outlives the test."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.communicate(timeout=10)


def _wait_held(lock: Path) -> None:
    for _ in range(50):
        if lock.exists() and _held(lock):
            return
        time.sleep(0.1)
    raise AssertionError("the watcher never took its lock")


def test_a_wake_exits_the_arm_prints_the_wake_and_the_re_arm_order_and_frees_the_lock(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "S1.selfwatch.lock"
    proc = _arm(tmp_path)
    _wait_held(lock)
    (tmp_path / "S1.errparked").touch()
    out, _ = proc.communicate(timeout=20)
    assert proc.returncode == 0, out
    lines = out.splitlines()
    assert lines[0] == "RESUME: woke S1", (
        lines
    )  # the watcher's "STAYS ARMED — do NOT re-arm" clause is false here
    assert "selfwatch_arm.sh S1" in lines[1] and "re-arm" in lines[1], lines
    assert not _held(lock), (
        "the lock must be free the moment the arm exits, or a re-arm reads 'already armed'"
    )
    again = _arm(tmp_path)
    _wait_held(lock)
    _stop(again)


def test_a_duplicate_arm_exits_with_the_watchers_line_and_no_re_arm_order(tmp_path: Path) -> None:
    lock = tmp_path / "S1.selfwatch.lock"
    first = _arm(tmp_path)
    _wait_held(lock)
    dup = subprocess.run(
        ["bash", str(ARM), "S1"],
        env=_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=20,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert dup.returncode == 0 and dup.stdout.startswith("self-watch already armed"), dup.stdout
    assert "re-arm" not in dup.stdout, "the standing arm still holds the lock; no re-arm is owed"
    assert _held(lock), "the duplicate must not kill the standing watch"
    _stop(first)


def test_a_missing_watcher_refuses_loudly(tmp_path: Path) -> None:
    env = {**_env(tmp_path), "SELFWATCH_BIN": str(tmp_path / "absent.sh")}
    r = subprocess.run(
        ["bash", str(ARM), "S1"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert r.returncode == 1 and "NOT armed" in r.stdout, r.stdout


def test_terminating_the_arm_takes_the_watcher_down_and_frees_the_lock(tmp_path: Path) -> None:
    """An orphaned watcher holds the lock (the arm nag reads it as armed) and prints its wake into a dead pipe;
    a TERM to the background task must end both."""
    lock = tmp_path / "S1.selfwatch.lock"
    proc = _arm(tmp_path)
    _wait_held(lock)
    proc.terminate()
    proc.communicate(timeout=20)
    for _ in range(30):
        if not _held(lock):
            break
        time.sleep(0.1)
    assert not _held(lock), "the watcher outlived its arm"


def test_a_sigkill_of_the_arm_alone_still_takes_the_watcher_down(tmp_path: Path) -> None:
    """Review of D-356, A-S1/A-S4: a SIGKILL runs no trap; the watcher dies with its parent (pdeathsig), so
    the lock frees within one of its sleeps instead of being held by an orphan forever."""
    lock = tmp_path / "S1.selfwatch.lock"
    proc = _arm(tmp_path)
    _wait_held(lock)
    os.kill(proc.pid, signal.SIGKILL)
    proc.communicate(timeout=10)
    for _ in range(150):
        if not _held(lock):
            break
        time.sleep(0.1)
    free = not _held(lock)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    assert free, "an orphaned watcher still holds the lock"


def test_without_setpriv_the_arm_still_arms_and_wakes(tmp_path: Path) -> None:
    """Review of D-356 pass 2, A-S4: `setpriv` is util-linux; where it is absent the arm must still work (it
    only loses the SIGKILL guard), never exit at once and ask to be re-armed forever."""
    import shutil

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("bash", "pkill", "seq", "sleep", "flock", "rm"):
        (bin_dir / tool).symlink_to(shutil.which(tool))
    env = {**_env(tmp_path), "PATH": str(bin_dir)}
    lock = tmp_path / "S1.selfwatch.lock"
    proc = subprocess.Popen(
        [str(bin_dir / "bash"), str(ARM), "S1"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    try:
        _wait_held(lock)
        (tmp_path / "S1.errparked").touch()
        out, _ = proc.communicate(timeout=20)
    finally:
        _stop(proc)
    assert out.splitlines()[0] == "RESUME: woke S1", out


def test_a_watcher_that_exits_without_a_line_is_not_armed_and_orders_no_re_arm(
    tmp_path: Path,
) -> None:
    """Review of D-356 pass 2, A-S4: EOF is not a wake — printing the re-arm order there loops the agent
    through an arm that can never hold."""
    silent = tmp_path / "silent.sh"
    silent.write_text("#!/usr/bin/env bash\nexit 3\n")
    env = {**_env(tmp_path), "SELFWATCH_BIN": str(silent)}
    r = subprocess.run(
        ["bash", str(ARM), "S1"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert r.returncode == 1 and "NOT armed" in r.stdout and "re-arm it" not in r.stdout, r.stdout


def test_a_final_line_without_a_newline_is_still_the_wake(tmp_path: Path) -> None:
    """Review of D-356 pass 3, A-S5: `read` fills the variable and returns non-zero at EOF; a fallback keyed
    on that status wiped a delivered wake and reported the watcher silent."""
    partial = tmp_path / "partial.sh"
    partial.write_text('#!/usr/bin/env bash\nprintf "RESUME: woke S1"\n')
    env = {**_env(tmp_path), "SELFWATCH_BIN": str(partial)}
    r = subprocess.run(
        ["bash", str(ARM), "S1"],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    lines = r.stdout.splitlines()
    assert r.returncode == 0 and lines[0] == "RESUME: woke S1" and "re-arm it" in lines[1], r.stdout


def test_an_in_place_rewrite_while_the_arm_waits_never_executes_the_new_bytes(
    tmp_path: Path,
) -> None:
    """bash reads a script incrementally, so an arm waiting at `read` for up to an hour resumes at its old byte
    offset in whatever the file NOW holds — an in-place edit ran the new file's comments as commands
    (mail 01M36FPTT9YS7ADH3CYQ5MQ1P3). The whole body must be parsed before any of it runs."""
    arm = tmp_path / "arm.sh"
    arm.write_text(ARM.read_text())
    env = _env(tmp_path)
    proc = subprocess.Popen(
        ["bash", str(arm), "S1"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    try:
        lock = tmp_path / "S1.selfwatch.lock"
        deadline = time.time() + 10
        while time.time() < deadline and not (lock.exists() and _held(lock)):
            time.sleep(0.05)
        assert _held(lock), "the stub watcher never took its lock"
        with arm.open("w") as fh:  # truncate + write in place, as an editor does
            fh.write(":; echo MUTATED\n" * 400)
        (tmp_path / "S1.errparked").write_text("")
        out, err = proc.communicate(timeout=15)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
    assert "MUTATED" not in out + err, out + err
    assert "RESUME: woke S1" in out
