"""A run's persistent scratch dir (kaizen 01M4V0B03B): `start` gives every run a scratch dir under the
MAIN checkout's `.tmp/runs/`, which survives a WSL /tmp wipe, and prints `SCRATCH: <path>`.

The unit tests drive the helpers against throwaway git repos; the subprocess tests drive `start`
through the `COMMAND_RUN_DIR` seam, which keeps every suite out of a live checkout.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "command_run.py"
DAY = 86400


def _load():
    spec = importlib.util.spec_from_file_location("command_run_scratch_ut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cr = _load()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _repo(tmp_path: Path, gitignore: str | None = None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    if gitignore is not None:
        (repo / ".gitignore").write_text(gitignore, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")
    return repo


def _ignored(repo: Path) -> bool:
    return _git(repo, "check-ignore", "-q", "--", ".tmp/runs/x").returncode == 0


def _cr(run_dir: Path, *args: str, sid: str = "s1", cwd: Path | None = None):
    env = {
        "PATH": "/usr/bin:/bin",
        "COMMAND_RUN_DIR": str(run_dir),
        "KAIZEN_EVENTS_DIR": str(run_dir.parent / "events"),
        "CLAUDE_SESSION_ID": sid,
    }
    return subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.fixture
def no_seam(monkeypatch):
    monkeypatch.delenv("COMMAND_RUN_DIR", raising=False)


def test_start_scratch_lands_in_the_main_checkout(tmp_path: Path, no_seam) -> None:
    """Behaviour 1: the root is <main checkout>/.tmp/runs, and the dir is keyed by session and command."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    path, notes = cr._make_scratch(
        str(repo), "abc", "fabrik-task", "2026-10-14T01:46:01+0300", None
    )
    assert path is not None, notes
    assert path == repo / ".tmp" / "runs" / "abc" / "fabrik-task-2026-10-14T01-46-01-0300"
    assert path.is_dir() and _ignored(repo)


def test_exclude_is_added_once_or_no_scratch(tmp_path: Path, no_seam) -> None:
    """Behaviour 2: an un-ignored repo gets ONE info/exclude line; a negation keeps it unignored → no dir."""
    repo = _repo(tmp_path)
    assert not _ignored(repo)
    for key in ("k1", "k2"):
        path, notes = cr._make_scratch(str(repo), "abc", "fabrik-review", key, None)
        assert path is not None and path.is_dir(), notes
    exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert exclude.splitlines().count("/.tmp/runs/") == 1, exclude
    assert _ignored(repo)
    assert _git(repo, "status", "--porcelain").stdout == ""

    (tmp_path / "neg").mkdir()
    neg = _repo(tmp_path / "neg", gitignore="!/.tmp/runs/\n")
    path, notes = cr._make_scratch(str(neg), "abc", "fabrik-review", "k1", None)
    assert path is None and notes, notes
    assert not (neg / ".tmp" / "runs").exists()


def _age(path: Path, days: float) -> None:
    t = time.time() - days * DAY
    for dirpath, _dirnames, filenames in os.walk(path):
        for name in filenames:
            os.utime(Path(dirpath) / name, (t, t))
        os.utime(dirpath, (t, t))


def test_prune_ages_by_newest_file_and_spares_live_dirs(tmp_path: Path, no_seam) -> None:
    """Behaviour 3: age is the NEWEST mtime in the tree; current, referenced and worktree dirs survive."""
    root = tmp_path / "runs"
    stale = root / "old" / "fabrik-task-a"
    nested_fresh = root / "old" / "fabrik-task-b"
    referenced = root / "other" / "fabrik-review-c"
    worktree = root / "other" / "fabrik-review-d"
    current = root / "me" / "fabrik-task-e"
    for d in (stale, nested_fresh / "pin", referenced, worktree, current):
        d.mkdir(parents=True)
        (d / "f.md").write_text("x", encoding="utf-8")
    (worktree / ".git").write_text("gitdir: /nowhere\n", encoding="utf-8")
    for d in (stale, nested_fresh, referenced, worktree, current):
        _age(d, 20)
    (nested_fresh / "pin" / "brief.md").write_text("today", encoding="utf-8")  # a write deep inside

    gone_sid = root / "emptied" / "fabrik-task-f"
    gone_sid.mkdir(parents=True)
    _age(gone_sid, 20)

    notes = cr._prune_scratch(root, keep={current.resolve(), referenced.resolve()})
    assert not stale.exists()
    assert nested_fresh.exists(), "a write in a subdir keeps the run"
    assert referenced.exists() and current.exists() and worktree.exists()
    assert any("fabrik-review-d" in n for n in notes), notes
    assert not (root / "emptied").exists(), "an emptied <sid> dir is removed"


def test_worktree_run_scratch_lives_in_the_main_checkout(tmp_path: Path, no_seam) -> None:
    """Behaviour 4: a run started inside a linked worktree writes to the MAIN checkout's .tmp/runs."""
    repo = _repo(tmp_path)
    wt = tmp_path / "wt"
    assert _git(repo, "worktree", "add", "-q", "--detach", str(wt)).returncode == 0
    path, notes = cr._make_scratch(str(wt), "abc", "fabrik-task", "k", None)
    assert path is not None, notes
    assert path.is_relative_to(repo / ".tmp" / "runs"), path
    assert _ignored(repo) and _ignored(wt)
    assert _git(repo, "worktree", "remove", "--force", str(wt)).returncode == 0
    assert path.is_dir(), "removing the worktree leaves the run's scratch"


def test_resumed_run_in_a_new_session_reuses_the_seed_scratch(tmp_path: Path, no_seam) -> None:
    """Behaviour 5: a resume after a restart runs in a NEW session; it keeps the seed's dir."""
    repo = _repo(tmp_path, gitignore=".tmp/\n")
    first, _ = cr._make_scratch(
        str(repo), "old-sid", "fabrik-task", "2026-10-13T10:00:00+0300", None
    )
    assert first is not None
    (first / "design.md").write_text("kept", encoding="utf-8")
    seed = {
        "scratch": str(first),
        "session_id": "old-sid",
        "started_at": "2026-10-13T10:00:00+0300",
    }
    again, _ = cr._make_scratch(
        str(repo), "new-sid", "fabrik-task", "2026-10-13T10:00:00+0300", seed
    )
    assert again == first and (again / "design.md").read_text(encoding="utf-8") == "kept"

    seed_gone = {"session_id": "old-sid", "scratch": str(tmp_path / "vanished")}
    derived, _ = cr._make_scratch(
        str(repo), "new-sid", "fabrik-task", "2026-10-13T10:00:00+0300", seed_gone
    )
    assert derived == first, "a seed whose dir is gone derives the path from the SEED's session"


def test_scratch_failure_never_refuses_start(tmp_path: Path) -> None:
    """Behaviour 6: start prints SCRATCH under the COMMAND_RUN_DIR seam, and a scratch failure never refuses."""
    run_dir = tmp_path / "runs"
    out = _cr(run_dir, "start", "--command", "fabrik-review", "--phases", "2", "--terminal", "t")
    assert out.returncode == 0, out.stdout + out.stderr
    lines = [ln for ln in out.stdout.splitlines() if ln.startswith("SCRATCH: ")]
    assert len(lines) == 1, out.stdout
    path = Path(lines[0][len("SCRATCH: ") :])
    assert path.is_dir() and path.is_relative_to(run_dir / "scratch"), path
    rec = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))
    assert rec["scratch"] == str(path)

    blocked = tmp_path / "runs2"
    blocked.mkdir()
    (blocked / "scratch").write_text("a file where the dir should be", encoding="utf-8")
    out = _cr(blocked, "start", "--command", "fabrik-review", "--phases", "2", "--terminal", "t")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "SCRATCH: " not in out.stdout and "scratch" in out.stderr.lower(), (
        out.stdout + out.stderr
    )
    rec = json.loads((blocked / "s1.json").read_text(encoding="utf-8"))
    assert rec["state"] == "running" and "scratch" not in rec
    # the HOME-override isolation style (no COMMAND_RUN_DIR) run from INSIDE a repo: the scratch goes
    # beside the isolated records, never into the checkout (it once landed in /opt/fabrik/.tmp/runs)
    home = tmp_path / "home"
    (tmp_path / "homecase").mkdir()
    repo = _repo(tmp_path / "homecase")
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "KAIZEN_EVENTS_DIR": str(tmp_path / "events3"),
        "CLAUDE_SESSION_ID": "s3",
        "PYTEST_CURRENT_TEST": os.environ.get("PYTEST_CURRENT_TEST", "x"),
    }
    out = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "start",
            "--command",
            "fabrik-review",
            "--phases",
            "2",
            "--terminal",
            "t",
        ],
        cwd=str(repo),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert not (repo / ".tmp").exists(), "a test start never writes into the checkout it runs from"
    assert f"SCRATCH: {home / '.claude' / 'state' / 'command-runs' / 'scratch'}" in out.stdout, (
        out.stdout
    )


def test_a_resume_keeps_scratch_across_sessions_and_an_ignore_change(
    tmp_path: Path, no_seam
) -> None:
    """Review A1+A3: a wall-blocked run resumed in a NEW session says its scratch is kept (never "belongs
    to a dead session"), and a seed dir that already exists is reused even if the repo stopped ignoring it."""
    run_dir = tmp_path / "runs"
    assert (
        _cr(
            run_dir, "start", "--command", "fabrik-review", "--phases", "2", "--terminal", "t"
        ).returncode
        == 0
    )
    first = json.loads((run_dir / "s1.json").read_text(encoding="utf-8"))["scratch"]
    out = _cr(
        run_dir,
        "blocked",
        "--command",
        "fabrik-review",
        "--wall",
        "--reason",
        "quota wall",
        "--feedback",
        "confusion: none · waste: none · change: none · filed: none — surfaces exercised: test harness wall block",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    seed = re.search(r"--resume-from (\S+)", out.stdout).group(1)
    out = _cr(
        run_dir,
        "start",
        "--command",
        "fabrik-review",
        "--phases",
        "2",
        "--terminal",
        "t",
        "--resume-from",
        seed,
        sid="s2",
    )
    assert out.returncode == 0, out.stdout + out.stderr
    assert f"SCRATCH: {first}" in out.stdout and "dead session" not in out.stdout, out.stdout

    repo = _repo(tmp_path, gitignore=".tmp/\n")
    path, _ = cr._make_scratch(str(repo), "old", "fabrik-task", "k", None)
    assert path is not None
    (path / "design.md").write_text("kept", encoding="utf-8")
    (repo / ".gitignore").write_text(".tmp/\n!/.tmp/\n!/.tmp/runs/\n", encoding="utf-8")
    assert not _ignored(repo)
    again, notes = cr._make_scratch(
        str(repo), "new", "fabrik-task", "k", {"scratch": str(path), "session_id": "old"}
    )
    assert again == path and notes, (again, notes)


def test_a_seed_scratch_outside_the_root_is_never_reused(tmp_path: Path, no_seam) -> None:
    """Closing pass A: a seed naming a dir OUTSIDE the current root (another repo, or a live checkout
    while the test seam is on) is not reused — the run gets its own dir under the root and a NOTE."""
    elsewhere = tmp_path / "other" / ".tmp" / "runs" / "sid" / "fabrik-task-k"
    elsewhere.mkdir(parents=True)
    seam = tmp_path / "seam"
    path, notes = cr._make_scratch(
        "", "new", "fabrik-task", "k", {"scratch": str(elsewhere), "session_id": "sid"}, root=seam
    )
    assert path is not None and path.is_relative_to(seam), path
    assert any("outside" in n for n in notes), notes

    repo = _repo(tmp_path, gitignore=".tmp/\n")
    path, notes = cr._make_scratch(
        str(repo), "new", "fabrik-task", "k", {"scratch": str(elsewhere), "session_id": "sid"}
    )
    assert path is not None and path.is_relative_to(repo / ".tmp" / "runs"), path
