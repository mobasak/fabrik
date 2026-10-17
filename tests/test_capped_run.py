"""The box-wide test caps (W-162398ef): a test run is bounded by kernel cgroup ceilings, never by trust.

Two WSL out-of-memory crashes on 2026-10-17 came from one test process growing to ~32 GB (an
unpatched `ssh()` handing `yaml.safe_load` a MagicMock; replayed, ~300 MB/s). These tests drive the
real `scripts/capped_run.sh` under `systemd-run --user`, each in its OWN throwaway slice: the shared
`fabrik-tests.slice` total is a box-wide value other sessions' runs depend on, so no test ever sets
it. Every allocation here is bounded far below the box (a few hundred MB at most).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
import time
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CAPPED = REPO / "scripts" / "capped_run.sh"
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "tests"))

ALLOC = "b = bytearray(300 * 1024 * 1024)\nprint('survived', len(b))\n"


def _user_manager() -> bool:
    if not shutil.which("systemd-run"):
        return False
    probe = subprocess.run(
        ["systemd-run", "--user", "--scope", "-q", "--", "true"],
        capture_output=True,
        timeout=20,
        check=False,
    )
    return probe.returncode == 0


needs_scope = pytest.mark.skipif(not _user_manager(), reason="no reachable user systemd manager")


@pytest.fixture
def slice_env(monkeypatch):
    """A slice of this test's own, stopped afterwards, so no test touches the shared slice."""
    name = f"fabrik-tests-probe-{uuid.uuid4().hex[:8]}.slice"
    monkeypatch.setenv("FABRIK_TEST_SLICE", name)
    monkeypatch.setenv("FABRIK_TEST_SLICE_MAX", "2G")
    yield name
    subprocess.run(
        ["systemctl", "--user", "stop", name], capture_output=True, timeout=20, check=False
    )


def _capped(*args: str, timeout: int = 60, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(CAPPED), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )


@needs_scope
def test_capped_run_kills_a_command_past_its_ceiling(tmp_path, slice_env):
    script = tmp_path / "alloc.py"
    script.write_text(ALLOC, encoding="utf-8")
    run = _capped("--mem", "64M", "--", sys.executable, str(script))
    assert run.returncode == 137, (run.returncode, run.stdout, run.stderr)
    assert "survived" not in run.stdout
    assert "killed at the memory ceiling (64M per run" in run.stderr, run.stderr
    assert "Killed" not in run.stderr.replace("killed at", ""), run.stderr  # no bash job noise


@needs_scope
def test_capped_run_passes_rc_and_output_through(slice_env):
    run = _capped(
        "--mem", "256M", "--", sys.executable, "-c", "print('hello'); raise SystemExit(3)"
    )
    assert run.returncode == 3, (run.returncode, run.stderr)
    assert run.stdout.strip() == "hello"
    assert "WARNING" not in run.stderr


@needs_scope
def test_capped_run_ends_a_hang_and_its_tree(tmp_path, slice_env):
    marker = f"{61 + uuid.uuid4().int % 1000 / 1000:.3f}"  # a sleep length no other process uses
    hang = tmp_path / "hang.sh"
    hang.write_text(f"#!/bin/bash\nsetsid sleep {marker} &\nsleep {marker}\n", encoding="utf-8")
    hang.chmod(0o755)
    started = time.monotonic()
    run = _capped("--mem", "128M", "--timeout", "2", "--", str(hang), timeout=60)
    assert run.returncode == 124, (run.returncode, run.stderr)
    # the scope's own RuntimeMaxSec (2 s) ended it, not the outer backstop (2 + 30 s) — the limit
    # that still holds when the runner itself is SIGKILLed by its caller
    assert time.monotonic() - started < 20
    assert "stopped at the 2s time limit" in run.stderr, run.stderr
    time.sleep(1)
    left = subprocess.run(
        ["pgrep", "-f", f"sleep {marker}"], capture_output=True, text=True, check=False
    )
    assert left.stdout.strip() == "", f"orphans survived the timeout: {left.stdout}"


@pytest.mark.parametrize(
    "args",
    [
        ("--mem", "0", "--", "true"),
        ("--mem", "0M", "--", "true"),
        ("--mem", "12X", "--", "true"),
        ("--mem", "512K", "--", "true"),  # below the 1M floor
        ("--timeout", "-1", "--", "true"),
        ("--timeout", "0", "--", "true"),
        ("--mem", "1G"),  # no command
    ],
)
def test_capped_run_refuses_a_malformed_bound(args):
    run = _capped(*args)
    assert run.returncode == 2, (args, run.returncode, run.stderr)
    assert "capped_run:" in run.stderr


def test_capped_run_refuses_a_malformed_env_bound(monkeypatch):
    env = {**os.environ, "FABRIK_TEST_SLICE_MAX": "lots"}
    run = _capped("--", "true", env=env)
    assert run.returncode == 2 and "FABRIK_TEST_SLICE_MAX" in run.stderr, run.stderr


@needs_scope
def test_the_slice_bounds_a_nested_run(tmp_path, slice_env, monkeypatch):
    """Each run has a 1G ceiling of its own; the slice holds 200M for all of them together, so
    the inner run is killed even though its own ceiling would let it live."""
    monkeypatch.setenv("FABRIK_TEST_SLICE_MAX", "200M")
    script = tmp_path / "alloc.py"
    script.write_text(ALLOC, encoding="utf-8")
    inner = f"{CAPPED} --mem 1G -- {sys.executable} {script}; echo inner_rc=$?"
    run = _capped("--mem", "1G", "--", "bash", "-c", inner, timeout=90)
    assert "survived" not in run.stdout, run.stdout
    assert "inner_rc=137" in run.stdout, (run.stdout, run.stderr)


def test_capped_run_without_a_user_manager_runs_uncapped_and_says_so(tmp_path):
    """A box with no systemd tools: a PATH holding only what the runner needs besides them."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("bash", "timeout", "cat", "id"):
        (bin_dir / tool).symlink_to(shutil.which(tool))
    env = {**os.environ, "PATH": str(bin_dir)}
    run = _capped("--", sys.executable, "-c", "print('ran')", env=env)
    assert run.returncode == 0 and run.stdout.strip() == "ran", run.stderr
    assert "WARNING" in run.stderr and "UNCAPPED" in run.stderr, run.stderr


# ── the automatic launchers ──────────────────────────────────────────────────────────


@needs_scope
def test_automatic_launchers_run_pytest_capped(tmp_path, slice_env, monkeypatch):
    import final_gate as fg

    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_big.py").write_text(
        "def test_big():\n    b = bytearray(300 * 1024 * 1024)\n    assert b\n", encoding="utf-8"
    )
    monkeypatch.setattr(fg, "PROJECT_ROOT", root)
    monkeypatch.setattr(fg, "PYTHON", sys.executable)
    monkeypatch.chdir(root)
    monkeypatch.setenv("FABRIK_TEST_MEM_MAX", "64M")
    name, ok, text = fg._run_pytest_suite()
    assert not ok and "KILLED AT THE MEMORY CEILING" in text, (name, text)
    assert "not a host outage" in text, text

    argv, note = fg._capped_argv(["pytest"], 30)
    assert (
        argv[:4] == [str(CAPPED), "--timeout", "30", "--"] and note == ""
    )  # this tree's own runner
    monkeypatch.setenv("FABRIK_CAPPED_RUN", str(tmp_path / "absent.sh"))
    argv, note = fg._capped_argv(["pytest"], 30)
    assert argv == ["pytest"] and "uncapped" in note
    monkeypatch.delenv("FABRIK_CAPPED_RUN")

    import merge_request as mr

    assert mr._capped(["python", "-m", "pytest"], 60)[:4] == [str(CAPPED), "--timeout", "60", "--"]

    sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))
    import kaizen_outcomes as ko

    assert ko._capped(["python", "-m", "pytest"], 60.4)[:4] == [
        str(CAPPED),
        "--timeout",
        "60",
        "--",
    ]


# ── the hub suite's own guard ────────────────────────────────────────────────────────


@needs_scope
def test_memguard_kills_a_runaway_and_reports_it(tmp_path, slice_env):
    """A runaway inside pytest (default capture ON) is killed past FABRIK_TEST_RSS_MAX, and the
    traceback naming the test reaches the CALLER's stderr. The whole run sits inside a 1G scope,
    so a broken guard costs this box nothing."""
    (tmp_path / "test_runaway.py").write_text(
        textwrap.dedent(
            """
            import time

            def test_grows_forever():
                hoard = []
                for _ in range(40):
                    hoard.append(bytearray(25 * 1024 * 1024))
                    time.sleep(0.05)
                time.sleep(30)
            """
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "FABRIK_TEST_RSS_MAX": "200M", "PYTHONPATH": str(REPO / "tests")}
    run = _capped(
        "--mem",
        "1G",
        "--",
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "-p",
        "memguard",
        "-p",
        "no:cacheprovider",
        "--rootdir",
        str(tmp_path),
        str(tmp_path / "test_runaway.py"),
        env=env,
        timeout=90,
    )
    assert run.returncode == 137, (run.returncode, run.stdout[-500:], run.stderr[-500:])
    assert "memguard:" in run.stderr and "200M" in run.stderr, run.stderr[-800:]
    assert "test_grows_forever" in run.stderr, run.stderr[-800:]


def test_this_hub_session_is_capped(request):
    import memguard

    assert memguard.WATCHDOG is not None and memguard.WATCHDOG.poll() is None, "no live watchdog"
    assert request.config.pluginmanager.hasplugin("timeout"), "pytest-timeout is not loaded"
    assert request.config.getini("timeout") == "600"
