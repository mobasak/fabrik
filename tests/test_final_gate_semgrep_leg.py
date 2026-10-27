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
    monkeypatch.setattr(fg, "semgrep_env_with_token", lambda: None)
    return tmp_path


class _Runner:
    """Stands in for the process-group runner: records each call, answers a scripted result."""

    def __init__(self, result: tuple[int | None, str] | Exception = (0, "")) -> None:
        self.result = result
        self.calls: list[tuple[list[str], int]] = []

    def __call__(self, cmd: list[str], timeout: int, env: object = None) -> tuple[int | None, str]:
        self.calls.append((cmd, timeout))
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
    """The leg is wired into Tier 2: running all of `run_static_checks` here would run mypy and
    bandit, so the wiring is read from the source, between the function and the pytest leg."""
    body = Path(fg.__file__).read_text(encoding="utf-8").split("def run_static_checks")[1]
    assert "results.append(_semgrep_row(changed))" in body.split("# Pytest — CI parity")[0]
