"""scripts/merge_request.py — box-wide admission of merge test legs (W-fbd1d4b9 part c, D-1381).

`_admitted` is driven in-process with a private lease directory (FABRIK_MERGE_LEG_DIR) and a short
poll; a second leg is a thread or a child process holding its own lease, so the flock semantics are
the kernel's own, never mocked.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "merge_request.py"


def _load():
    spec = importlib.util.spec_from_file_location("merge_request_admission", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mr = _load()


class _Ctx:
    def __init__(self, mem: str | None) -> None:
        self.leg_mem = mem
        self.main = Path("/nonexistent-repo")
        self.test_deadline = time.monotonic() + 100
        self.admit_spent = 0.0
        self.leg_t0 = 0.0


@pytest.fixture
def leases(tmp_path, monkeypatch):
    monkeypatch.setenv("FABRIK_MERGE_LEG_DIR", str(tmp_path / "legs"))
    monkeypatch.setenv("FABRIK_TEST_SLICE_MAX", "12G")
    monkeypatch.setenv("FABRIK_TEST_MEM_MAX", "4G")
    monkeypatch.setattr(mr, "LEG_ADMIT_POLL_S", 0.05)
    return tmp_path / "legs"


def _hold(mem: str, release: threading.Event, entered: threading.Event) -> threading.Thread:
    def run() -> None:
        with mr._admitted(_Ctx(mem)):
            entered.set()
            release.wait(10)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    assert entered.wait(5), "the first leg was never admitted"
    return t


def test_two_8g_legs_serialize_and_the_wait_moves_the_budget(leases):
    release, entered = threading.Event(), threading.Event()
    first = _hold("8192M", release, entered)
    threading.Timer(1.2, release.set).start()
    ctx = _Ctx("8192M")
    before = ctx.test_deadline
    t0 = time.monotonic()
    with mr._admitted(ctx) as note:
        waited = time.monotonic() - t0
    first.join(5)
    assert waited >= 0.5, f"the second 8G leg started beside the first ({waited:.2f}s)"
    # the wait is outside the budget clock: the deadline moved by it
    assert ctx.test_deadline - before >= 0.5
    assert "admitted after a 1s wait" in note, note  # the leg says it waited
    assert list(leases.glob("lease-*.json")) == []  # both leases removed at the leg's end


def test_an_8g_and_a_4g_leg_run_together(leases):
    release, entered = threading.Event(), threading.Event()
    first = _hold("8192M", release, entered)
    t0 = time.monotonic()
    with mr._admitted(_Ctx(None)):  # no declaration: capped_run's 4G default
        waited = time.monotonic() - t0
        assert len(list(leases.glob("lease-*.json"))) == 2
    release.set()
    first.join(5)
    assert waited < 2, f"a leg that fits the slice waited {waited:.2f}s"


def test_a_dead_holder_frees_its_slot(leases):
    leases.mkdir(parents=True)
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import importlib.util,sys,time,pathlib;"
            f"s=importlib.util.spec_from_file_location('m',{str(SCRIPT)!r});m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
            "class C:\n leg_mem='8192M'; main=pathlib.Path('/x'); test_deadline=0; admit_spent=0.0\n"
            "cm=m._admitted(C()); cm.__enter__(); print('held',flush=True); time.sleep(60)",
        ],
        env={**os.environ},
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout.readline().strip() == "held"
        assert len(list(leases.glob("lease-*.json"))) == 1
        holder.kill()
        holder.wait(5)
        t0 = time.monotonic()
        with mr._admitted(_Ctx("8192M")):
            waited = time.monotonic() - t0
        assert waited < 2, f"a dead holder's lease kept the slot for {waited:.2f}s"
        assert list(leases.glob("lease-*.json")) == []  # the stale lease was deleted
    finally:
        holder.kill()


def test_the_wait_is_bounded_and_said(leases, monkeypatch):
    monkeypatch.setattr(mr, "LEG_ADMIT_WAIT_S", 0.3)
    release, entered = threading.Event(), threading.Event()
    first = _hold("8192M", release, entered)
    try:
        t0 = time.monotonic()
        with mr._admitted(_Ctx("8192M")) as note:
            waited = time.monotonic() - t0
        assert 0.3 <= waited < 2, waited
        assert "admission: started after the" in note and "1 leg(s)" in note
    finally:
        release.set()
        first.join(5)


def test_a_forked_child_does_not_keep_the_parents_lease(leases):
    # Fable critique 4: the parent exits while its forked child lives on; the child must not hold the
    # lease (with the fork hook removed it does, and _held_leases still reports it)
    leases.mkdir(parents=True)
    code = (
        "import importlib.util,os,sys,time,pathlib;"
        f"s=importlib.util.spec_from_file_location('m',{str(SCRIPT)!r});m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
        "class C:\n leg_mem='8192M'; main=pathlib.Path('/x'); test_deadline=0; admit_spent=0.0\n"
        "cm=m._admitted(C()); cm.__enter__()\n"
        "if os.fork()==0:\n print('child',flush=True); time.sleep(3); os._exit(0)\n"
        "time.sleep(0.3); os._exit(0)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "child"
        proc.wait(5)  # the parent is gone; its child sleeps on
        time.sleep(0.2)
        assert mr._held_leases(leases) == []
    finally:
        proc.kill()


def test_a_hung_admission_lock_holder_cannot_outlast_the_bound(leases, monkeypatch):
    # Fable critique 2: the admission lock itself is taken without blocking
    import fcntl

    monkeypatch.setattr(mr, "LEG_ADMIT_WAIT_S", 0.3)
    leases.mkdir(parents=True)
    fd = os.open(leases / "admission.lock", os.O_RDWR | os.O_CREAT)
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        out: dict = {}

        def leg() -> None:
            with mr._admitted(_Ctx("8192M")) as note:
                out["note"] = note

        t = threading.Thread(target=leg, daemon=True)
        t.start()
        t.join(5)  # a blocking flock never returns: fail here instead of hanging the suite
        assert not t.is_alive(), "a held admission lock blocked the leg past its bound"
        assert "its lock was held past" in out["note"]
    finally:
        os.close(fd)


def test_an_undeletable_lease_entry_does_not_disable_admission(leases, monkeypatch):
    # Fable critique 5: a stale lease whose unlink is refused must not turn admission off box-wide
    # (a regular file, so the S_ISREG skip does not hide the unlink path this guards)
    leases.mkdir(parents=True)
    stale = leases / "lease-0-dead.json"
    stale.write_text('{"mib": 8192}')
    real = Path.unlink

    def refuse(self, *a, **k):
        if self.name == stale.name:
            raise PermissionError(13, "Permission denied")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "unlink", refuse)
    with mr._admitted(_Ctx("8192M")) as note:
        pass
    assert "not checked" not in note, note


def test_the_leg_label_carries_the_admission_note(leases, monkeypatch, tmp_path):
    monkeypatch.setattr(mr, "_admitted", lambda ctx: _Note("; admitted after a 7s wait"))
    monkeypatch.setattr(
        mr, "_run_owner_leg_admitted", lambda ctx, wt, script, touched: ("run", "label")
    )
    assert mr._run_owner_leg(_Ctx(None), tmp_path, "true", []) == (
        "run",
        "label; admitted after a 7s wait",
    )


class _Note:
    def __init__(self, note: str) -> None:
        self.note = note

    def __enter__(self) -> str:
        return self.note

    def __exit__(self, *exc) -> None:
        return None


def test_the_wait_allowance_is_per_invocation(leases):
    # Opus critique 1: every leg of one merge run shares LEG_ADMIT_WAIT_S, so the walls count it once
    release, entered = threading.Event(), threading.Event()
    first = _hold("8192M", release, entered)
    try:
        ctx = _Ctx("8192M")
        ctx.admit_spent = mr.LEG_ADMIT_WAIT_S  # an earlier leg of this run used it all
        t0 = time.monotonic()
        with mr._admitted(ctx) as note:
            waited = time.monotonic() - t0
        assert waited < 2, f"a run with no allowance left still waited {waited:.2f}s"
        assert "admission: started after the" in note
    finally:
        release.set()
        first.join(5)


def test_an_interrupt_while_taking_the_lease_frees_it(leases, monkeypatch):
    # Opus critique 2: a KeyboardInterrupt between creating the lease and the leg must not keep the slot
    real = mr.json.dumps

    def boom(*a, **k):
        monkeypatch.setattr(mr.json, "dumps", real)
        raise KeyboardInterrupt

    monkeypatch.setattr(mr.json, "dumps", boom)
    with pytest.raises(KeyboardInterrupt):
        with mr._admitted(_Ctx("8192M")):
            pass
    assert mr._LEASE_FDS == {}
    assert list(leases.glob("lease-*.json")) == []


def test_the_legs_runner_inherits_the_lease(leases):
    # Opus critique 3: the lease must live as long as the leg's tests, so the runner holds it too
    before = set(mr._LEASE_FDS)
    with mr._admitted(_Ctx("8192M")):
        (fd,) = set(mr._LEASE_FDS) - before
        run = mr._run(
            [sys.executable, "-c", "import os,sys; os.fstat(int(sys.argv[1]))", str(fd)], 30
        )
    assert run.returncode == 0, run.stderr


def test_a_refused_lease_unlink_keeps_the_legs_verdict(leases):
    # review A1: a lease dir that refuses the unlink must not raise out of the leg or keep the lock
    with mr._admitted(_Ctx("8192M")):
        os.chmod(leases, 0o555)
    try:
        assert mr._LEASE_FDS == {}
        t0 = time.monotonic()
        with mr._admitted(_Ctx("8192M")) as note:  # the leftover file is nobody's: no wait
            waited = time.monotonic() - t0
        assert waited < 2 and "admitted after" not in note
    finally:
        os.chmod(leases, 0o755)


def test_a_fifo_named_like_a_lease_does_not_hang_admission(leases):
    # review A-haiku 4: opening a FIFO blocks with the admission lock held
    leases.mkdir(parents=True)
    os.mkfifo(leases / "lease-0-fifo.json")

    def leg() -> None:
        with mr._admitted(_Ctx("8192M")):
            pass

    t = threading.Thread(target=leg, daemon=True)
    t.start()
    t.join(5)  # an open() on the FIFO never returns: fail here instead of hanging the suite
    assert not t.is_alive(), "a FIFO named like a lease hung admission"


def test_the_after_merge_runner_cap_covers_the_wait():
    # review A2: the runner's scope bound must hold the admission wait plus a whole budget
    assert mr.AFTER_RUNNER_MAX_S >= mr.MERGE_TEST_BUDGET_S + mr.LEG_ADMIT_WAIT_S + 300


def test_each_legs_wait_is_spent_from_one_allowance(leases, monkeypatch):
    # review B1: a second leg of the same invocation gets only what the first left
    monkeypatch.setattr(mr, "LEG_ADMIT_WAIT_S", 0.4)
    release, entered = threading.Event(), threading.Event()
    first = _hold("8192M", release, entered)
    try:
        ctx = _Ctx("8192M")
        with mr._admitted(ctx):
            pass
        assert ctx.admit_spent >= 0.4
        t0 = time.monotonic()
        with mr._admitted(ctx) as note:
            waited = time.monotonic() - t0
        assert waited < 0.3, f"the second leg got a fresh allowance ({waited:.2f}s)"
        assert "admission: started after the" in note
    finally:
        release.set()
        first.join(5)


def test_a_failed_lease_write_releases_the_lease(leases, monkeypatch):
    # review A-haiku 3 (A-5): an OSError after the lease is created must not keep it while the leg runs
    real = mr.json.dumps

    def full(*a, **k):
        monkeypatch.setattr(mr.json, "dumps", real)
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(mr.json, "dumps", full)
    with mr._admitted(_Ctx("8192M")) as note:
        assert mr._LEASE_FDS == {}, "the leg ran holding a half-written lease"
    assert "not checked" in note
    assert list(leases.glob("lease-*.json")) == []
