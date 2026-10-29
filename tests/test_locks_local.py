"""Concurrency + correctness tests for fabrik.locks_local.file_lock."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

# what tests/conftest.py set for the whole process, read before any fixture of this file overrides it
_PROCESS_LOCK_DIR = os.environ.get("FABRIK_LOCK_DIR", "")


# Redirect lock dir to a tmpdir BEFORE importing the module so the
# LOCK_DIR module-level constant is honored. Caller of file_lock will
# still create the directory.
@pytest.fixture(autouse=True)
def _isolate_lock_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FABRIK_LOCK_DIR", str(tmp_path / "locks"))
    # Re-import to pick up the env var (LOCK_DIR is module-scope)
    import importlib

    import fabrik.locks_local

    importlib.reload(fabrik.locks_local)
    yield
    # undo then reload, so no later test inherits this test's deleted tmp LOCK_DIR (W-019e468b's shape)
    monkeypatch.undo()
    importlib.reload(fabrik.locks_local)


def _reload_with(monkeypatch, **env):
    """Reload locks_local under ``env`` (a None value deletes the variable) and return the module."""
    import importlib

    import fabrik.locks_local

    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return importlib.reload(fabrik.locks_local)


def test_default_lock_dir_is_private_per_user_cache(tmp_path, monkeypatch):
    """With no override the lock dir is ``~/.cache/fabrik-locks``, made 0700 — never a fixed /tmp name another
    local user could pre-create (W-1f70f2e9). The umask is pinned so a dropped ``mode=`` cannot hide behind 077."""
    home = tmp_path / "home"
    home.mkdir()
    mod = _reload_with(monkeypatch, FABRIK_LOCK_DIR=None, HOME=str(home))
    expected = home / ".cache" / "fabrik-locks"
    assert expected == mod.LOCK_DIR
    old = os.umask(0o022)
    try:
        with mod.file_lock("default-dir"):
            pass
    finally:
        os.umask(old)
    assert mod.LOCK_DIR.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize(
    "home",
    [None, "", "relative/home", "/", "//", "/..", "/home/.."],
    ids=[
        "unset",
        "empty",
        "relative",
        "root",
        "double-slash-root",
        "root-parent",
        "dotdot-to-root",
    ],
)
def test_default_lock_dir_without_an_absolute_home_uses_the_passwd_home(monkeypatch, home):
    """Cron and other HOME-less callers resolve the same dir through the passwd entry. An empty HOME would
    otherwise mean ``/`` (a fixed ``/.cache`` path as root), as would ``//`` or ``/..``, and a relative one the cwd."""
    import pwd

    mod = _reload_with(monkeypatch, FABRIK_LOCK_DIR=None, HOME=home)
    expected = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".cache" / "fabrik-locks"
    assert expected == mod.LOCK_DIR


@pytest.mark.parametrize("via", ["link", "link-dotdot"])
def test_a_home_that_resolves_to_root_through_a_symlink_is_refused(tmp_path, monkeypatch, via):
    """A lexical check passes ``<dir>/toroot`` and ``<dir>/l/x/..`` (x -> /); the kernel lands both on ``/``."""
    import pwd

    (tmp_path / "toroot").symlink_to("/")
    (tmp_path / "l").mkdir()
    (tmp_path / "l" / "x").symlink_to("/")
    home = tmp_path / "toroot" if via == "link" else tmp_path / "l" / "x" / ".."
    mod = _reload_with(monkeypatch, FABRIK_LOCK_DIR=None, HOME=str(home))
    expected = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".cache" / "fabrik-locks"
    assert expected == mod.LOCK_DIR


def test_an_empty_override_counts_as_unset(tmp_path, monkeypatch):
    """``FABRIK_LOCK_DIR=""`` used to mean ``Path("")`` — the caller's cwd."""
    home = tmp_path / "home"
    mod = _reload_with(monkeypatch, FABRIK_LOCK_DIR="", HOME=str(home))
    expected = home / ".cache" / "fabrik-locks"
    assert expected == mod.LOCK_DIR


@pytest.mark.parametrize(
    "pw_dir",
    ["", "relative/home", "/", "//", "/.."],
    ids=["empty", "relative", "root", "double-slash-root", "root-parent"],
)
def test_an_unusable_passwd_home_is_refused_too(monkeypatch, pw_dir):
    """The passwd home is held to HOME's rule: never a cwd-relative dir, never the fixed ``/.cache``."""
    import pwd

    class _Entry:
        def __init__(self, d):
            self.pw_dir = d

    monkeypatch.setattr(pwd, "getpwuid", lambda uid: _Entry(pw_dir))
    mod = _reload_with(monkeypatch, FABRIK_LOCK_DIR=None, HOME=None)
    assert mod.LOCK_DIR is None


def test_no_resolvable_home_imports_cleanly_and_refuses_to_lock(monkeypatch):
    """No absolute HOME and no passwd entry: the import still succeeds (seven modules import this one) and
    ``file_lock`` refuses with OSError, never falling back to a shared fixed path."""
    import pwd

    def no_entry(uid):
        raise KeyError(uid)

    monkeypatch.setattr(pwd, "getpwuid", no_entry)
    mod = _reload_with(monkeypatch, FABRIK_LOCK_DIR=None, HOME=None)
    assert mod.LOCK_DIR is None
    with pytest.raises(OSError, match="FABRIK_LOCK_DIR"):
        with mod.file_lock("no-home"):
            pass


def test_the_suite_never_locks_in_the_real_default_dir():
    """tests/conftest.py pins FABRIK_LOCK_DIR for the whole process, so a test that takes the default lock
    writes a tmp dir, never the operator's ~/.cache (the five state-*.lock leftovers in /tmp/fabrik-locks)."""
    assert Path(_PROCESS_LOCK_DIR).name.startswith("pytest-lock-dir-"), _PROCESS_LOCK_DIR


def _import_file_lock():
    from fabrik.locks_local import file_lock

    return file_lock


def test_basic_acquire_and_release(tmp_path):
    file_lock = _import_file_lock()
    with file_lock("test-basic") as path:
        assert Path(path).exists()
    # After release, lock file still exists (we don't delete it), but
    # another process can re-acquire.
    with file_lock("test-basic"):
        pass


def test_two_threads_serialize():
    file_lock = _import_file_lock()
    order: list[str] = []
    barrier = threading.Barrier(2)

    def worker(label: str, hold_seconds: float):
        barrier.wait()  # ensure both threads race for the lock
        with file_lock("test-serial", timeout_seconds=5.0):
            order.append(f"{label}-start")
            time.sleep(hold_seconds)
            order.append(f"{label}-end")

    t1 = threading.Thread(target=worker, args=("A", 0.2))
    t2 = threading.Thread(target=worker, args=("B", 0.2))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    # Whichever thread won the race, the other must wait for it to fully
    # release. So we should see a complete start-end pair before the
    # second thread enters.
    assert order[0].endswith("-start")
    assert order[1].endswith("-end")
    assert order[0][0] == order[1][0]  # same letter (start, then end)
    assert order[2].endswith("-start")
    assert order[3].endswith("-end")
    assert order[2][0] == order[3][0]


def test_timeout_raises():
    file_lock = _import_file_lock()
    # Hold the lock in one thread, try to acquire it in another with a
    # short timeout, assert TimeoutError.
    holder_acquired = threading.Event()
    holder_release = threading.Event()
    error: list[Exception] = []

    def holder():
        with file_lock("test-timeout", timeout_seconds=5.0):
            holder_acquired.set()
            holder_release.wait(timeout=2.0)

    def contender():
        holder_acquired.wait(timeout=2.0)
        try:
            with file_lock("test-timeout", timeout_seconds=0.3, poll_interval=0.05):
                pass
        except TimeoutError as e:
            error.append(e)

    t1 = threading.Thread(target=holder)
    t2 = threading.Thread(target=contender)
    t1.start()
    t2.start()
    t2.join()
    holder_release.set()
    t1.join()
    assert len(error) == 1
    assert isinstance(error[0], TimeoutError)
    assert "test-timeout" in str(error[0])


def test_exception_inside_with_still_releases():
    file_lock = _import_file_lock()

    class BoomError(RuntimeError):
        pass

    with pytest.raises(BoomError):
        with file_lock("test-exception"):
            raise BoomError("oops")

    # If the lock weren't released, this would timeout
    with file_lock("test-exception", timeout_seconds=1.0):
        pass


def test_name_sanitization(tmp_path):
    file_lock = _import_file_lock()
    # Path traversal attempt + special chars: the safety property we care
    # about is that the resolved lock file lives INSIDE LOCK_DIR — a
    # literal '..' substring in the filename itself is harmless because
    # the path separators got stripped.
    with file_lock("../../etc/passwd") as path:
        lock_dir = Path(os.environ["FABRIK_LOCK_DIR"]).resolve()
        assert Path(path).resolve().parent == lock_dir
        assert "/" not in Path(path).name


def test_empty_name_falls_back_to_underscore():
    file_lock = _import_file_lock()
    with file_lock("///") as path:
        # All slashes get sanitized; name becomes '_'
        assert Path(path).name == "_.lock"


def test_different_names_dont_block_each_other():
    file_lock = _import_file_lock()
    # Holding lock A should not block lock B
    with file_lock("name-A", timeout_seconds=5.0):
        with file_lock("name-B", timeout_seconds=1.0):
            pass
