"""The completion gate's semgrep leg: opt-in per repo, and honest about every way it does not run.

WHY (W-0bcc5f9e, iterative_image_editor's upstream proposal 2026-10-02). The leg hard-coded a 30 s
budget against a scan measured at 43-386 s on this box, so since its timeout row got its own name
(2026-09-14) it completed in 0 of the recorded gate runs and timed out 762 times. Each timeout
killed only `pysemgrep` and orphaned `semgrep-core` (~1.6 GB, ~6 cores) under init. With no
`--error` a finished scan could not report a finding, and in a repo with no `src/` an empty diff
handed semgrep a missing root (rc 2, a RED row) that only the 30 s timeout hid.

The panel's design (Opus + Fable, both C): the scan runs only where `.fabrik/run-semgrep` exists —
the `.fabrik/run-pytest` precedent — reads its budget from `TIMEOUTS`, scans the changed `src/`
files that still exist (every language: `--config auto` is multi-language), kills the whole
process group on expiry, and reports findings as an ADVISORY row until a repo opts into blocking.
"""

from __future__ import annotations

import ast
import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import final_gate as fg  # noqa: E402 — the path insert must precede the import


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repo with `src/` and the opt-in sentinel; tests remove what they need absent."""
    (tmp_path / "src").mkdir()
    (tmp_path / ".fabrik").mkdir()
    (tmp_path / ".fabrik" / "run-semgrep").touch()
    monkeypatch.setattr(fg, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(fg, "semgrep_env_with_token", lambda: _TOKEN_ENV)
    return tmp_path


# what `semgrep_env_with_token` hands the runner in these tests — a token-bearing env, so a leg
# that dropped it (and scanned unauthenticated) is visible
_TOKEN_ENV = {"SEMGREP_APP_TOKEN": "test-token"}


class _Runner:
    """Stands in for the process-group runner: records each call, answers a scripted result."""

    def __init__(self, result: tuple[int | None, str] | Exception = (0, "")) -> None:
        self.result = result
        self.calls: list[tuple[list[str], int]] = []
        self.envs: list[object] = []

    def __call__(self, cmd: list[str], timeout: int, env: object = None) -> tuple[int | None, str]:
        self.calls.append((cmd, timeout))
        self.envs.append(env)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _arm_runner(monkeypatch: pytest.MonkeyPatch, runner: _Runner) -> _Runner:
    monkeypatch.setattr(fg, "_run_process_group", runner)
    return runner


def test_a_repo_with_no_src_is_not_applicable_and_never_scans(repo, monkeypatch):
    """24 of 49 synced repos have no `src/`: the old leg handed semgrep `src/` there on an empty
    diff and got rc 2 `Invalid scanning root: src` — a red row a longer budget would have shown."""
    (repo / "src").rmdir()
    runner = _arm_runner(monkeypatch, _Runner())
    name, ok, _ = fg._semgrep_row(set())
    assert ok and "(N/A" in name
    assert runner.calls == []
    assert fg._summarize_skipped([(name, ok, "")])["skipped_checks"] == ["semgrep"]


def test_an_unarmed_repo_reports_the_opt_in_skip_and_names_how_to_arm_it(repo, monkeypatch):
    (repo / ".fabrik" / "run-semgrep").unlink()
    runner = _arm_runner(monkeypatch, _Runner())
    name, ok, out = fg._semgrep_row({"src/a.py"})
    assert ok and "(NOT RUN" in name and "opt-in" in name
    assert ".fabrik/run-semgrep" in out
    assert runner.calls == []
    assert fg._summarize_skipped([(name, ok, out)])["skipped"] == 1


def test_an_armed_diff_scans_only_its_src_files_that_still_exist(repo, monkeypatch):
    """Deleted paths are dropped (semgrep refuses a missing target), non-src paths are dropped,
    and NO extension filter: `--config auto` scans TypeScript and the rest as well as Python."""
    (repo / "src" / "a.py").write_text("x = 1\n")
    (repo / "src" / "b.ts").write_text("let x = 1;\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "x.md").write_text("# x\n")  # exists, so only the src/ test can drop it
    runner = _arm_runner(monkeypatch, _Runner((0, "")))
    name, ok, _ = fg._semgrep_row({"src/a.py", "src/b.ts", "src/gone.py", "docs/x.md"})
    assert (name, ok) == ("semgrep", True)
    ((cmd, timeout),) = runner.calls
    assert "--error" in cmd, "without --error a scan with findings exits 0 and reads as a pass"
    assert cmd[cmd.index("--error") + 1 :] == ["src/a.py", "src/b.ts"]
    assert timeout == fg.TIMEOUTS["semgrep"]
    assert runner.envs == [_TOKEN_ENV], "the token env must reach the scan, or it runs logged out"


def test_an_armed_diff_whose_src_files_were_all_deleted_is_a_skip_not_a_pass(repo, monkeypatch):
    """Panel Cobra check: an empty target list must never read as a clean scan."""
    runner = _arm_runner(monkeypatch, _Runner())
    name, ok, _ = fg._semgrep_row({"src/gone.py"})
    assert ok and "(diff-sensed skip" in name
    assert runner.calls == []


def test_an_empty_diff_scans_the_whole_src_tree(repo, monkeypatch):
    runner = _arm_runner(monkeypatch, _Runner((0, "")))
    fg._semgrep_row(set())
    ((cmd, _),) = runner.calls
    assert cmd[-1] == "src/"


def test_findings_are_an_advisory_row_that_carries_them_and_cannot_red_the_gate(repo, monkeypatch):
    _arm_runner(monkeypatch, _Runner((1, "src/a.py:3 rule.id finding text")))
    name, ok, out = fg._semgrep_row(set())
    assert ok and name in fg.WARN_ONLY_CHECKS
    assert "rule.id finding text" in out and out.startswith("⚠")
    # it RAN: it must not be summarised as a skip, and the roster calls it advisory
    assert fg._summarize_skipped([(name, ok, out)])["skipped"] == 0
    assert fg._check_roster([(name, ok, out)]) == [{"name": name, "outcome": "advisory"}]


def test_a_semgrep_error_exit_is_still_red(repo, monkeypatch):
    _arm_runner(monkeypatch, _Runner((2, "[ERROR] something fatal")))
    name, ok, out = fg._semgrep_row(set())
    assert (name, ok) == ("semgrep", False)
    assert "something fatal" in out


def test_a_timeout_names_the_real_budget_and_warns_because_the_repo_armed_it(repo, monkeypatch):
    """Panel Cobra check: an armed repo that always times out must not look like a scanned one —
    the row is a SKIP (marker) and its output is ⚠-prefixed, so `--json` `warnings` names it."""
    _arm_runner(monkeypatch, _Runner((None, "partial")))
    name, ok, out = fg._semgrep_row(set())
    assert ok and f"timed out after {fg.TIMEOUTS['semgrep']}s" in name
    assert fg._summarize_skipped([(name, ok, out)])["skipped"] == 1
    assert out.startswith("⚠")


def test_not_installed_and_not_authenticated_keep_their_marked_rows(repo, monkeypatch):
    _arm_runner(monkeypatch, _Runner(FileNotFoundError("semgrep")))
    assert fg._semgrep_row(set())[0] == "semgrep (NOT INSTALLED)"
    _arm_runner(monkeypatch, _Runner((2, "HTTP 401 — run semgrep login")))
    assert fg._semgrep_row(set())[0] == "semgrep (NOT RUN — not authenticated)"


@pytest.mark.parametrize(("code", "want"), [(0, "semgrep"), (1, fg.SEMGREP_FINDINGS_ROW)])
def test_a_finished_scan_that_quotes_semgrep_login_is_still_a_finished_scan(
    repo, monkeypatch, code, want
):
    """Exit 0 and 1 are a COMPLETED scan: the auth text check once ran first and turned a scan
    whose output merely mentioned `semgrep login` (a tip line, a quoted source line) into NOT RUN,
    dropping its findings."""
    _arm_runner(
        monkeypatch, _Runner((code, "src/a.py:1 finding\nTip: run `semgrep login` for Pro rules"))
    )
    assert fg._semgrep_row(set())[0] == want


def test_a_semgrep_that_cannot_start_is_a_red_row_not_a_crash(repo, monkeypatch):
    """Only FileNotFoundError is 'not installed'; any other OSError (not executable, an argv the
    kernel refuses) used to escape `_semgrep_row` and crash the whole gate with a traceback."""
    _arm_runner(monkeypatch, _Runner(PermissionError(13, "Permission denied", "semgrep")))
    name, ok, out = fg._semgrep_row(set())
    assert (name, ok) == ("semgrep", False)
    assert "could not start" in out and "Permission denied" in out


def test_a_scan_killed_by_a_signal_is_a_warned_skip_like_a_timeout(repo, monkeypatch):
    """An OOM kill (SIGKILL, rc -9) is a scan that never finished — the timeout's shape, never a
    red row that blames the change for the box's memory."""
    _arm_runner(monkeypatch, _Runner((-9, "")))
    name, ok, out = fg._semgrep_row(set())
    assert ok and name == "semgrep (NOT RUN — killed by signal 9)"
    assert fg._summarize_skipped([(name, ok, out)])["skipped"] == 1
    assert out.startswith("⚠")


def test_the_runner_kills_the_whole_process_group_on_timeout(tmp_path, monkeypatch):
    """`subprocess.run(timeout=)` kills only the direct child: probed live, `semgrep-core` survived
    `pysemgrep`'s kill, re-parented to init at ~1.6 GB. The runner must reap the grandchild too."""
    monkeypatch.setattr(fg, "PROJECT_ROOT", tmp_path)
    pidfile = tmp_path / "grandchild.pid"
    script = (
        "import subprocess, sys, time\n"
        f"g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"open({str(pidfile)!r}, 'w').write(str(g.pid))\n"
        "time.sleep(60)\n"
    )
    t0 = time.monotonic()
    code, _ = fg._run_process_group([sys.executable, "-c", script], 3)
    assert code is None, "a timeout is reported as None, never as an exit code"
    assert time.monotonic() - t0 < 30
    gpid = int(pidfile.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _alive(gpid):
        time.sleep(0.1)
    assert not _alive(gpid), "the grandchild outlived the timeout — the group was not killed"


def test_a_descendant_that_left_the_group_cannot_hold_the_budget_open(tmp_path, monkeypatch):
    """A `setsid` descendant escapes the group kill and still holds the pipes: the post-kill read
    once waited for it (probed: 8 s against a 2 s budget; unbounded for a longer-lived one)."""
    monkeypatch.setattr(fg, "PROJECT_ROOT", tmp_path)
    pidfile = tmp_path / "escaped.pid"
    cmd = ["sh", "-c", f"setsid sh -c 'echo $$ > {pidfile}; exec sleep 60' & sleep 60"]
    t0 = time.monotonic()
    try:
        code, _ = fg._run_process_group(cmd, 1)
        elapsed = time.monotonic() - t0
    finally:
        with contextlib.suppress(OSError, ValueError):
            os.kill(int(pidfile.read_text()), signal.SIGKILL)  # the escapee this test spawned
    assert code is None
    assert elapsed < 1 + fg._GROUP_DRAIN_S + 10, f"the read waited out the escapee: {elapsed:.1f}s"


def test_an_interrupt_while_waiting_kills_the_group_and_propagates(tmp_path, monkeypatch):
    """`subprocess.run` killed its child on ANY exception; the group runner must too — a Ctrl-C
    once left the whole scan running in its own session, out of the terminal's reach."""
    monkeypatch.setattr(fg, "PROJECT_ROOT", tmp_path)
    pidfile = tmp_path / "child.pid"

    def interrupt(*_: object) -> None:
        raise KeyboardInterrupt

    old = signal.signal(signal.SIGALRM, interrupt)
    signal.alarm(2)
    try:
        with pytest.raises(KeyboardInterrupt):
            fg._run_process_group(["sh", "-c", f"echo $$ > {pidfile}; exec sleep 60"], 60)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    pid = int(pidfile.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _alive(pid):
        time.sleep(0.1)
    alive = _alive(pid)
    if alive:
        os.kill(pid, signal.SIGKILL)
    assert not alive, "the child outlived the interrupt"


def test_a_child_left_behind_by_a_finished_scan_is_reaped(tmp_path, monkeypatch):
    """The group is killed on the NORMAL path too: a leader that exits 0 and leaves a backgrounded
    child behind (stdio redirected, so nothing holds the pipes) once returned with it alive."""
    monkeypatch.setattr(fg, "PROJECT_ROOT", tmp_path)
    pidfile = tmp_path / "left.pid"
    script = f"sleep 60 >/dev/null 2>&1 & echo $! > {pidfile}; echo scan-done"
    code, out = fg._run_process_group(["sh", "-c", script], 30)
    assert (code, out) == (0, "scan-done")
    pid = int(pidfile.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _alive(pid):
        time.sleep(0.1)
    alive = _alive(pid)
    if alive:
        os.kill(pid, signal.SIGKILL)
    assert not alive, "the finished scan's child outlived the runner"


def test_a_sigterm_to_the_gate_kills_the_group(tmp_path):
    """A SIGTERM's default action ends the process with no cleanup at all; while the runner waits
    it raises SystemExit instead, so the group dies with the gate (probed: it survived, rc -15)."""
    pidfile = tmp_path / "leader.pid"
    driver = (
        "import sys\n"
        f"sys.path.insert(0, {str(Path(fg.__file__).parent)!r})\n"
        "import final_gate as fg\n"
        f"fg._run_process_group(['sh', '-c', 'echo $$ > {pidfile}; exec sleep 60'], 120)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", driver], cwd=tmp_path)
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not pidfile.exists():
        time.sleep(0.1)
    time.sleep(0.5)
    proc.send_signal(signal.SIGTERM)
    rc = proc.wait(timeout=20)
    pid = int(pidfile.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _alive(pid):
        time.sleep(0.1)
    alive = _alive(pid)
    if alive:
        os.kill(pid, signal.SIGKILL)
    assert not alive, f"the scan outlived the gate's SIGTERM (gate rc {rc})"
    assert rc == 128 + signal.SIGTERM, "the SIGTERM must still end the gate"


def test_the_runner_returns_the_exit_code_and_puts_stdout_before_stderr(tmp_path, monkeypatch):
    """semgrep prints findings to stdout and pages of rule-deprecation notices to stderr — seen
    live, a merged stream buried the finding below the first 10 lines a row prints."""
    monkeypatch.setattr(fg, "PROJECT_ROOT", tmp_path)
    code, out = fg._run_process_group(
        [
            sys.executable,
            "-c",
            "import sys; print('NOISE', file=sys.stderr, flush=True); print('FINDING'); sys.exit(3)",
        ],
        30,
    )
    assert code == 3
    assert out.index("FINDING") < out.index("NOISE")


def _alive(pid: int) -> bool:
    """True while `pid` exists and is not a zombie (a killed, unreaped child reads as dead)."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return False
    return stat.rsplit(")", 1)[1].split()[0] != "Z"


def test_run_static_checks_appends_the_leg_row():
    """The leg is wired into Tier 2. Running all of `run_static_checks` here would run mypy and
    bandit, so the wiring is read from the AST — a comment or a string cannot satisfy it."""
    tree = ast.parse(Path(fg.__file__).read_text(encoding="utf-8"))
    func = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_static_checks"
    )
    wired = [
        n
        for n in ast.walk(func)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "append"
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "results"
        and n.args
        and isinstance(n.args[0], ast.Call)
        and isinstance(n.args[0].func, ast.Name)
        and n.args[0].func.id == "_semgrep_row"
    ]
    assert len(wired) == 1, (
        f"results.append(_semgrep_row(...)) calls in run_static_checks: {len(wired)}"
    )
