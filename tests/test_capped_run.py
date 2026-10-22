"""The box-wide test caps (W-162398ef): a test run is bounded by kernel cgroup ceilings, never by trust.

Two WSL out-of-memory crashes on 2026-10-17 came from one test process growing to ~32 GB (an
unpatched `ssh()` handing `yaml.safe_load` a MagicMock; replayed, ~300 MB/s). These tests drive the
real `scripts/capped_run.sh` under `systemd-run --user`, each in its OWN throwaway slice: the shared
`fabrik-agents-tests.slice` total is a box-wide value other sessions' runs depend on, so no test ever sets
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
sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))

from test_merge_request_merge import world  # noqa: E402,F401 — the merge tests' own fixture

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
    # the tree ignores SIGTERM, so only the scope's TimeoutStopSec SIGKILL ends it in time
    hang.write_text(
        f'#!/bin/bash\ntrap "" TERM\nsetsid sleep {marker} &\nsleep {marker}\n', encoding="utf-8"
    )
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
        ("--timeout", "9223372036854775800", "--", "true"),  # would wrap the backstop's arithmetic
        ("--timeout", "604801", "--", "true"),  # past 7 days
        ("--mem", "99999999999999G", "--", "true"),  # overflows systemd's parser
        ("--mem", "01G", "--", "true"),
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


@pytest.mark.parametrize("name", ["badname", "-.slice", "a b.slice"])
def test_capped_run_refuses_a_bad_slice_name(name):
    """A bad slice name is refused (exit 2) — it once fell through to running UNCAPPED."""
    run = _capped("--", "true", env={**os.environ, "FABRIK_TEST_SLICE": name})
    assert run.returncode == 2 and "bad slice name" in run.stderr, run.stderr
    assert "UNCAPPED" not in run.stderr


@needs_scope
def test_capped_run_hands_stdin_through_and_survives_a_closed_one(slice_env):
    piped = subprocess.run(
        [str(CAPPED), "--mem", "64M", "--", "cat"],
        input="hello\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert piped.returncode == 0 and piped.stdout == "hello\n", (piped.stdout, piped.stderr)
    closed = subprocess.run(
        ["bash", "-c", f'{CAPPED} --mem 64M -- echo ran <&-; echo "rc=$?"'],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert "ran\nrc=0" in closed.stdout, (closed.stdout, closed.stderr)
    assert "UNCAPPED" not in closed.stderr, closed.stderr  # a closed stdin is not a missing manager


@needs_scope
def test_a_terminated_runner_leaves_no_scope_behind(slice_env):
    """SIGTERM to the runner (a caller giving up) exits 143 and stops the scope — no live unit, and no
    `failed` unit left in this test's slice."""
    proc = subprocess.Popen(
        [str(CAPPED), "--mem", "64M", "--", "sleep", "300"], stderr=subprocess.PIPE, text=True
    )
    time.sleep(2)
    proc.terminate()
    assert proc.wait(timeout=30) == 143
    time.sleep(1)
    units = subprocess.run(
        ["systemctl", "--user", "list-units", "--all", "--plain", "--no-legend", "fabrik-test-*"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.splitlines()
    mine = []
    for line in units:
        unit = line.split()[0]
        where = subprocess.run(
            ["systemctl", "--user", "show", unit, "-p", "Slice", "--value"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        if where == slice_env:
            mine.append(line)
    assert mine == [], mine


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

    # a project's synced copy has no runner beside it: it must take the hub's, never run uncapped
    import importlib.util

    synced = tmp_path / "project" / "scripts"
    synced.mkdir(parents=True)
    shutil.copy2(REPO / "scripts" / "merge_request.py", synced / "merge_request.py")
    spec = importlib.util.spec_from_file_location(
        "synced_merge_request", synced / "merge_request.py"
    )
    copy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copy)
    assert copy._capped_run() == "/opt/fabrik/scripts/capped_run.sh"

    sys.path.insert(0, str(REPO / "scripts" / "sysadmin"))
    import kaizen_outcomes as ko

    assert ko._capped(["python", "-m", "pytest"], 60.4)[:4] == [
        str(CAPPED),
        "--timeout",
        "60",
        "--",
    ]


def test_a_launcher_with_no_runner_says_it_runs_uncapped(tmp_path, monkeypatch, capsys):
    """No runner anywhere → the tests still run, and the launcher SAYS they run uncapped."""
    import kaizen_outcomes as ko
    import merge_request as mr

    monkeypatch.setenv("FABRIK_CAPPED_RUN", str(tmp_path / "absent.sh"))
    assert mr._capped(["pytest"], 60) == ["pytest"]
    assert ko._capped(["pytest"], 60) == ["pytest"]
    err = capsys.readouterr().err
    assert (
        err.count("UNCAPPED") == 2 and "merge_request: WARNING" in err and "kaizen_outcomes:" in err
    ), err


@needs_scope
def test_the_command_gets_no_extra_fd(slice_env):
    """The runner's stdin copy (fd 3) is closed for the command: a test must not inherit it."""
    run = _capped(
        "--mem", "64M", "--", "bash", "-c", "[ -e /proc/$$/fd/3 ] && echo LEAK || echo CLEAN"
    )
    assert run.stdout.strip() == "CLEAN", (run.stdout, run.stderr)


@needs_scope
def test_merge_and_sweep_call_sites_run_their_tests_inside_a_capped_scope(
    tmp_path, slice_env, monkeypatch
):
    """The two call sites, not just their helpers: the launched command records its own cgroup, and
    it must sit in a capped_run scope (`fabrik-test-…scope`) under this test's slice."""
    import kaizen_outcomes as ko  # noqa: PLC0415
    from test_kaizen_outcomes import (  # noqa: PLC0415 — the sweep's own fixture helpers
        _commit,
        _repo,
    )

    root = tmp_path / "opt"
    proj = _repo(root, "capped")
    _commit(proj, "pyproject.toml", "chore: pytest cfg", content="[tool.pytest.ini_options]\n")
    seen = tmp_path / "sweep.cgroup"
    fake = proj / ".venv" / "bin" / "python"
    fake.parent.mkdir(parents=True)
    fake.write_text(f'#!/bin/sh\ncat /proc/self/cgroup > "{seen}"\nexit 0\n', encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("KAIZEN_SWEEP_PROJECTS", "capped")
    monkeypatch.setenv("KAIZEN_SWEEP_TIMEOUT_S", "60")
    ko.run_sweep(root=root)
    text = seen.read_text(encoding="utf-8")
    assert "fabrik-test-" in text and slice_env in text, text


@needs_scope
def test_merge_owner_tests_run_inside_a_capped_scope(world, slice_env):  # noqa: F811
    seen = world.tmp / "owner.cgroup"
    world.write(".fabrik/merge-tests", f'cat /proc/self/cgroup > "{seen}"\n')
    world.commit_main("owner tests", ".fabrik/merge-tests")
    world.send(world.branch({"x.txt": "x\n"}))
    assert world.run("merge") == 0
    text = seen.read_text(encoding="utf-8")
    assert "fabrik-test-" in text and slice_env in text, text


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
    dumps = tmp_path / "tmpdir"
    dumps.mkdir()
    env = {
        **os.environ,
        "FABRIK_TEST_RSS_MAX": "200M",
        "PYTHONPATH": str(REPO / "tests"),
        "TMPDIR": str(dumps),
    }
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
    assert list(dumps.glob("fabrik-memguard-*")) == []  # the kill leaves no dump file behind


def test_the_gate_names_a_ceiling_kill_only_when_the_runner_reports_one(monkeypatch):
    """rc 137 plus the runner's own line in the tail is a ceiling kill; a failing test that merely
    QUOTES that line (rc 1) is an ordinary red."""
    import final_gate as fg

    mark = (
        "capped_run: killed at the memory ceiling (4G per run, 12G for fabrik-agents-tests.slice)"
        " — pytest"
    )
    for code, out, named in (
        (137, "F\n1 failed\n" + mark, True),
        (1, f"E   AssertionError: {mark!r}\n" + "x\n" * 10 + "1 failed", False),
        (1, "1 failed\n" + mark, False),
    ):
        monkeypatch.setattr(fg, "run_cmd", lambda *a, _c=code, _o=out, **k: (_c, _o))
        _, text = fg._run_capped_pytest(["pytest"], 30)
        assert ("KILLED AT THE MEMORY CEILING" in text) is named, (code, text)


def test_this_hub_session_is_capped(request):
    import memguard

    assert memguard.WATCHDOG is not None and memguard.WATCHDOG.poll() is None, "no live watchdog"
    assert request.config.pluginmanager.hasplugin("timeout"), "pytest-timeout is not loaded"
    assert request.config.getini("timeout") == "600"


# --- T05 (W-6e656dac): the nested slice and the admission band ---------------------------------------------------

FAKE_SYSTEMCTL = """#!/bin/sh
echo "$*" >> "$HOME/systemctl.log"
exit 0
"""
FAKE_SYSTEMD_RUN = """#!/bin/sh
echo "$*" >> "$HOME/systemd-run.log"
while [ $# -gt 0 ] && [ "$1" != "--" ]; do shift; done
shift
exec "$@"
"""


def _stub_home(tmp_path: Path) -> Path:
    """A HOME whose `systemctl`/`systemd-run` are logging stubs: no real slice is ever touched."""
    home = tmp_path / "stubhome"
    (home / "bin").mkdir(parents=True)
    for tool, text in (("systemctl", FAKE_SYSTEMCTL), ("systemd-run", FAKE_SYSTEMD_RUN)):
        (home / "bin" / tool).write_text(text, encoding="utf-8")
        (home / "bin" / tool).chmod(0o755)
    return home


def _proc(
    tmp_path: Path, avail_kb: int | None, psi: str | None = "0.00", name: str = "proc"
) -> Path:
    """A fake /proc root: MemAvailable and (optionally) the memory PSI line. None leaves the file out."""
    root = tmp_path / name
    (root / "pressure").mkdir(parents=True, exist_ok=True)
    if avail_kb is not None:
        (root / "meminfo").write_text(
            f"MemTotal:       28000000 kB\nMemAvailable:   {avail_kb} kB\n", encoding="utf-8"
        )
    if psi is not None:
        (root / "pressure" / "memory").write_text(
            f"some avg10={psi} avg60=0.00 avg300=0.00 total=1\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n",
            encoding="utf-8",
        )
    return root


def _admit_env(home: Path, proc: Path, wait: str) -> dict[str, str]:
    return {
        "PATH": f"{home}/bin:/usr/bin:/bin",
        "HOME": str(home),
        "FABRIK_PROC_ROOT": str(proc),
        "FABRIK_TEST_ADMIT_WAIT": wait,
    }


def test_the_run_nests_under_the_agents_slice(tmp_path):
    """The default slice is fabrik-agents-tests.slice — systemd nests it under fabrik-agents.slice by the dashed name,
    so the parent's ceiling bounds the test jobs — and the 12G cap on it is kept."""
    home = _stub_home(tmp_path)
    run = _capped("--", "true", env=_admit_env(home, _proc(tmp_path, 8_000_000), "0"))
    assert run.returncode == 0, run.stderr
    sysctl = (home / "systemctl.log").read_text(encoding="utf-8")
    assert (
        "set-property --runtime fabrik-agents-tests.slice MemoryMax=12G MemorySwapMax=0" in sysctl
    ), sysctl
    assert "--slice=fabrik-agents-tests.slice" in (home / "systemd-run.log").read_text(
        encoding="utf-8"
    )


def test_a_healthy_box_starts_at_once_and_says_nothing(tmp_path):
    home = _stub_home(tmp_path)
    t0 = time.monotonic()
    run = _capped("--", "true", env=_admit_env(home, _proc(tmp_path, 8_000_000), "30"))
    assert run.returncode == 0 and "admission" not in run.stderr, run.stderr
    assert time.monotonic() - t0 < 10


def test_low_memory_waits_up_to_the_bound_then_starts_and_says_so(tmp_path):
    """MemAvailable under 3 GiB holds the start for FABRIK_TEST_ADMIT_WAIT seconds, then the job runs anyway."""
    home = _stub_home(tmp_path)
    t0 = time.monotonic()
    run = _capped("--", "true", env=_admit_env(home, _proc(tmp_path, 2_000_000), "2"))
    took = time.monotonic() - t0
    assert run.returncode == 0, run.stderr
    assert took >= 2, took
    assert "admission: waiting" in run.stderr and "MemAvailable" in run.stderr, run.stderr
    assert "starting anyway after 2s" in run.stderr, run.stderr


def test_the_admission_wait_counts_against_the_runs_time_limit(tmp_path):
    """Callers bound the whole wrapper at timeout + 60 s, so the seconds waited come off the run's own limit
    (RuntimeMaxSec) and the wait line says so; the wait is itself bounded at half the limit, so a run keeps at least half."""
    home = _stub_home(tmp_path)
    env = _admit_env(home, _proc(tmp_path, 2_000_000), "2")
    run = _capped("--timeout", "100", "--", "true", env=env)
    assert run.returncode == 0, run.stderr
    assert "count against the 100s time limit" in run.stderr, run.stderr
    assert "RuntimeMaxSec=98 " in (home / "systemd-run.log").read_text(encoding="utf-8")
    (home / "systemd-run.log").unlink()
    # a wait as long as the limit would be a guaranteed time-out: the wait itself is bounded at half the limit
    long_wait = _admit_env(home, _proc(tmp_path, 2_000_000, name="busy"), "300")
    run = _capped("--timeout", "6", "--", "true", env=long_wait)
    assert run.returncode == 0, run.stderr
    assert "waiting up to 3s" in run.stderr and "starting anyway after 3s" in run.stderr, run.stderr
    assert "RuntimeMaxSec=3 " in (home / "systemd-run.log").read_text(encoding="utf-8")
    (home / "systemd-run.log").unlink()
    healthy = _admit_env(home, _proc(tmp_path, 8_000_000, name="ok"), "30")
    assert _capped("--timeout", "100", "--", "true", env=healthy).returncode == 0
    assert "RuntimeMaxSec=100 " in (home / "systemd-run.log").read_text(encoding="utf-8")


def test_memory_pressure_holds_the_start_too(tmp_path):
    """PSI `some avg10` over 10 is the second trigger, with MemAvailable healthy."""
    home = _stub_home(tmp_path)
    run = _capped("--", "true", env=_admit_env(home, _proc(tmp_path, 8_000_000, psi="42.50"), "1"))
    assert run.returncode == 0, run.stderr
    assert "admission: waiting" in run.stderr and "PSI" in run.stderr, run.stderr
    assert "starting anyway after 1s" in run.stderr, run.stderr


def test_the_wait_ends_as_soon_as_the_box_recovers(tmp_path):
    home = _stub_home(tmp_path)
    proc = _proc(tmp_path, 1_000_000)
    env = _admit_env(home, proc, "30")
    t0 = time.monotonic()
    child = subprocess.Popen(
        [str(CAPPED), "--", "true"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(2)
    (proc / "meminfo").write_text(
        "MemTotal: 28000000 kB\nMemAvailable: 9000000 kB\n", encoding="utf-8"
    )
    _, err = child.communicate(timeout=30)
    assert child.returncode == 0, err
    assert time.monotonic() - t0 < 20
    assert "admission: waiting" in err and "starting anyway" not in err, err


def test_an_unreadable_meminfo_or_psi_starts_at_once_and_says_so(tmp_path):
    home = _stub_home(tmp_path)
    for label, proc in (
        ("no-meminfo", _proc(tmp_path, None, name="p1")),
        ("no-psi", _proc(tmp_path, 1_000_000, psi=None, name="p2")),
    ):
        t0 = time.monotonic()
        run = _capped("--", "true", env=_admit_env(home, proc, "30"))
        assert run.returncode == 0, (label, run.stderr)
        assert time.monotonic() - t0 < 10, label
        assert "admission: unreadable" in run.stderr and "starting at once" in run.stderr, (
            label,
            run.stderr,
        )


def test_a_bad_admission_wait_exits_2(tmp_path):
    home = _stub_home(tmp_path)
    for bad in ("x", "-1", "99999"):
        run = _capped("--", "true", env=_admit_env(home, _proc(tmp_path, 8_000_000), bad))
        assert run.returncode == 2 and "FABRIK_TEST_ADMIT_WAIT" in run.stderr, (bad, run.stderr)
