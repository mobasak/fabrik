"""Concurrency + correctness tests for fabrik.locks_local.file_lock."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest


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

    class Boom(RuntimeError):
        pass

    with pytest.raises(Boom):
        with file_lock("test-exception"):
            raise Boom("oops")

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
