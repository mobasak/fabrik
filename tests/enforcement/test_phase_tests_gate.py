"""Behavior Contract tests for check_phase_tests.py (plan-2 Phase C).

Fixture = a real throwaway git repo per test: a plan with bulleted Given rows, an active lock
with baseline_commit, and commits shaping the window. The script is run as a subprocess from the
fixture root (it reads Path.cwd()), so these are end-to-end behavior tests, not unit shims.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "enforcement" / "check_phase_tests.py"
ENFORCE_DIR = SCRIPT.parent


def _git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert r.returncode == 0, f"git {args}: {r.stderr}"
    return r.stdout.strip()


def _run(repo: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, cwd=repo,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(ENFORCE_DIR)},
    )
    return r.returncode, r.stdout + r.stderr


def _repo(tmp_path: Path, given_rows: int = 2) -> tuple[Path, str]:
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    plan_dir = repo / "docs/development/plans"
    plan_dir.mkdir(parents=True)
    rows = "\n".join(
        f"- **Given** state {i}, **When** action, **Then** outcome {i}" for i in range(given_rows)
    )
    (plan_dir / "p.md").write_text(f"# Plan\n\nStatus: IN-PROGRESS\n\n## Behavior Contract\n{rows}\n")
    (repo / "src").mkdir()
    (repo / "src/app.py").write_text("A = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline")
    baseline = _git(repo, "rev-parse", "HEAD")
    locks = repo / ".fabrik/plan-locks"
    locks.mkdir(parents=True)
    (locks / "p.json").write_text(json.dumps({
        "plan": "docs/development/plans/p.md", "status": "active",
        "baseline_commit": baseline, "owned_paths": ["src/"],
    }))
    return repo, baseline


def test_declared_rows_source_changes_zero_tests_warns(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / "src/app.py").write_text("A = 2\nB = 3\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "behavior shipped, no tests")
    rc, out = _run(repo)
    assert rc == 0, out  # ADVISORY: exit 0 even when warning
    assert "WARNING" in out and "ZERO test changes" in out, out
    assert "declared:" in out, out  # the rows are listed for the reviewer


def test_tests_accompanying_the_window_silences(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / "src/app.py").write_text("A = 2\n")
    t = repo / "tests"
    t.mkdir()
    (t / "test_app.py").write_text("def test_a():\n    assert True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "behavior + tests")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_docs_only_window_is_silent(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / "README.md").write_text("docs only\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-qm", "docs only")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_no_declared_rows_is_silent_by_construction(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path, given_rows=0)
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "no declared behaviors")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_no_lock_exits_zero_silent(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / ".fabrik/plan-locks/p.json").unlink()
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "ad-hoc work")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_released_lock_is_ignored(tmp_path: Path) -> None:
    repo, base = _repo(tmp_path)
    lock = repo / ".fabrik/plan-locks/p.json"
    d = json.loads(lock.read_text())
    d["status"] = "released"
    lock.write_text(json.dumps(d))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "post-release work")
    rc, out = _run(repo)
    assert rc == 0 and "WARNING" not in out, out


def test_broken_lock_json_fails_soft(tmp_path: Path) -> None:
    repo, _ = _repo(tmp_path)
    (repo / ".fabrik/plan-locks/p.json").write_text("{not json")
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "broken lock")
    rc, out = _run(repo)
    assert rc == 0, out  # an advisory never breaks a commit


def test_deleted_test_does_not_satisfy_accompaniment(tmp_path: Path) -> None:
    # Review finding (live-reproduced): a window that DELETES a test while shipping source must
    # WARN — a deleted tests/ path in the unfiltered diff must never count as accompaniment.
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    plan_dir = repo / "docs/development/plans"
    plan_dir.mkdir(parents=True)
    (plan_dir / "p.md").write_text(
        "# Plan\n\n## Behavior Contract\n- **Given** s, **When** a, **Then** o\n")
    (repo / "src").mkdir()
    (repo / "src/app.py").write_text("A = 1\n")
    t = repo / "tests"
    t.mkdir()
    (t / "test_app.py").write_text("def test_a():\n    assert True\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline with a test")
    baseline = _git(repo, "rev-parse", "HEAD")
    locks = repo / ".fabrik/plan-locks"
    locks.mkdir(parents=True)
    (locks / "p.json").write_text(json.dumps({
        "plan": "docs/development/plans/p.md", "status": "active",
        "baseline_commit": baseline, "owned_paths": ["src/"]}))
    (repo / "src/app.py").write_text("A = 2\n")
    (t / "test_app.py").unlink()
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "ship behavior, DELETE the test")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "WARNING" in out and "ZERO test changes" in out, out


def test_absolute_plan_path_in_lock_is_confined(tmp_path: Path) -> None:
    # Review finding: PROJECT_ROOT / "/abs/path" discards the root — a lock pointing outside the
    # repo must be ignored, never read.
    repo, _ = _repo(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("- **Given** leaked, **When** read, **Then** bad\n")
    lock = repo / ".fabrik/plan-locks/p.json"
    d = json.loads(lock.read_text())
    d["plan"] = str(outside)  # absolute, escapes the repo
    lock.write_text(json.dumps(d))
    (repo / "src/app.py").write_text("A = 2\n")
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "source change")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "leaked" not in out and "WARNING" not in out, out
