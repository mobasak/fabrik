"""The hub suite's own memory guard (W-162398ef): a runaway test is killed, never the host.

On 2026-10-17 one test process grew to ~32 GB (an unpatched `ssh()` handing `yaml.safe_load` a
MagicMock; replayed, ~300 MB/s) and took the whole WSL box, and every session on it, down twice.
`scripts/capped_run.sh` bounds a run from OUTSIDE; this guard bounds the hub suite from INSIDE,
however it was launched — bare, backgrounded, or by a test that spawns pytest.

A watchdog PROCESS (a thread would starve while C code holds the GIL) sums PSS (VmRSS where
smaps_rollup is unreadable) over the pytest process and its descendants every 0.25 s. Past
`FABRIK_TEST_RSS_MAX` (default 3G, below capped_run.sh's 4G) it sends SIGUSR1 — faulthandler,
registered here, dumps every thread's traceback into a file (a stderr dump would land in pytest's
capture and die with it) — then copies the dump, with a one-line verdict, to the ORIGINAL stderr it
inherited while capture was suspended, deletes the dump, and SIGKILLs the tree. Its stdin and
stdout are /dev/null and it dies with its parent (PR_SET_PDEATHSIG), so it never holds a caller's
pipe open. The hub conftest calls `start`/`stop`; `-p memguard` loads it as a plugin elsewhere.

Cobra (D-253): the cheapest way to "pass" this guard is a limit so high it never fires; the default
sits ~28x above the dashboard suite's measured 110 MB peak, and a bad value falls back to it.
"""

from __future__ import annotations

import contextlib
import faulthandler
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

# 3G, below capped_run.sh's 4G per-run ceiling: under the runner the kernel would otherwise kill first
# and the traceback naming the runaway test would never be printed.
DEFAULT_LIMIT = "3G"
WATCHDOG: subprocess.Popen | None = None
_DUMP = None  # the open faulthandler file; kept so the registration stays valid
_DUMP_PATH: Path | None = None

_UNITS = {"K": 1024, "M": 1024**2, "G": 1024**3}

_WATCH = r"""
import ctypes, os, signal, sys, time
ppid, limit, label, dump = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3], sys.argv[4]
try:
    ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL)  # PR_SET_PDEATHSIG
except Exception:
    pass
me = os.getpid()

def tree(root):
    out, i = [root], 0
    while i < len(out):
        pid, i = out[i], i + 1
        try:
            for task in os.listdir(f"/proc/{pid}/task"):
                with open(f"/proc/{pid}/task/{task}/children") as fh:
                    out += [int(c) for c in fh.read().split() if int(c) != me]
        except OSError:
            pass
    return out

def rss(pid):
    # PSS, not VmRSS: forked children share pages, and summing RSS over a tree counts each shared
    # page once per process, killing a legitimate multi-process suite as a "runaway"
    for path, key in ((f"/proc/{pid}/smaps_rollup", "Pss:"), (f"/proc/{pid}/status", "VmRSS:")):
        try:
            with open(path) as fh:
                for line in fh:
                    if line.startswith(key):
                        return int(line.split()[1]) * 1024
        except OSError:
            pass
    return 0

while os.getppid() == ppid:
    total = sum(rss(p) for p in tree(ppid))
    if total > limit:
        try:
            os.kill(ppid, signal.SIGUSR1)
        except OSError:
            pass
        time.sleep(0.5)  # faulthandler writes in microseconds; at ~300 MB/s every second costs 300 MB
        msg = (f"memguard: killing pytest pid {ppid} — its process tree reached {total // 2**20} MB, "
               f"past FABRIK_TEST_RSS_MAX={label} (W-162398ef). A test is allocating without bound "
               "(an unpatched mock read in a loop is the usual cause). Traceback at the kill:\n")
        try:
            with open(dump, errors="replace") as fh:
                msg += fh.read()
            os.unlink(dump)  # the parent dies before its own cleanup can run
        except OSError:
            msg += "(no traceback was written)\n"
        # The verdict goes out BEFORE the kill, and PDEATHSIG is cleared first: the kernel fires it
        # when the parent exits, which would cut this write short.
        sys.stderr.write(msg)
        sys.stderr.flush()
        try:
            ctypes.CDLL(None, use_errno=True).prctl(1, 0)
        except Exception:
            pass
        for pid in reversed(tree(ppid)):  # re-walked: a pid from before the wait may be reused
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        sys.exit(0)
    time.sleep(0.25)
"""


def limit_bytes(raw: str | None) -> tuple[int, str, str]:
    """(bytes, label, note) for a `<digits><K|M|G>` limit of at least 1M; a bad value → the default."""
    value = (raw or DEFAULT_LIMIT).strip()
    m = re.fullmatch(r"([1-9][0-9]*)([KMG])", value)
    if m and int(m.group(1)) * _UNITS[m.group(2)] >= _UNITS["M"]:
        return int(m.group(1)) * _UNITS[m.group(2)], value, ""
    n = int(DEFAULT_LIMIT[:-1]) * _UNITS[DEFAULT_LIMIT[-1]]
    return (
        n,
        DEFAULT_LIMIT,
        f"memguard: FABRIK_TEST_RSS_MAX={value!r} is not a size like 4G — using {DEFAULT_LIMIT}",
    )


def start(config=None) -> None:
    """Start this process's watchdog once; the report goes to the stderr pytest found at startup."""
    global WATCHDOG, _DUMP, _DUMP_PATH
    if WATCHDOG is not None and WATCHDOG.poll() is None:
        return
    limit, label, note = limit_bytes(os.environ.get("FABRIK_TEST_RSS_MAX"))
    _DUMP_PATH = Path(tempfile.gettempdir()) / f"fabrik-memguard-{os.getpid()}.txt"
    _DUMP = open(_DUMP_PATH, "w", encoding="utf-8")  # noqa: SIM115 — must outlive this call
    faulthandler.register(signal.SIGUSR1, file=_DUMP, all_threads=True)
    capman = config.pluginmanager.getplugin("capturemanager") if config is not None else None
    ctx = capman.global_and_fixture_disabled() if capman is not None else contextlib.nullcontext()
    with ctx:  # the real stderr is fd 2 only while capture is suspended
        WATCHDOG = subprocess.Popen(  # noqa: S603 — fixed argv, this interpreter
            [sys.executable, "-c", _WATCH, str(os.getpid()), str(limit), label, str(_DUMP_PATH)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            close_fds=True,
        )
        if note:
            print(note, file=sys.stderr)


def stop() -> None:
    """End the watchdog and drop the dump file (a clean session leaves nothing behind)."""
    global WATCHDOG, _DUMP
    if WATCHDOG is not None:
        WATCHDOG.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            WATCHDOG.wait(timeout=5)
        WATCHDOG = None
    with contextlib.suppress(RuntimeError, ValueError):
        faulthandler.unregister(signal.SIGUSR1)
    if _DUMP is not None:
        _DUMP.close()
        _DUMP = None
    if _DUMP_PATH is not None:
        with contextlib.suppress(OSError):
            _DUMP_PATH.unlink()


def pytest_configure(config) -> None:  # the `-p memguard` plugin form
    start(config)


def pytest_unconfigure(config) -> None:  # noqa: ARG001 — pytest hook signature
    stop()
