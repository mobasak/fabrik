# AFTER-EDIT: scripts/wip_backup.sh
"""WIP safety net — the snapshot must capture staged+unstaged+untracked WITHOUT
touching the repo's real index, HEAD, branches, or stash (concurrent agents
must be completely unaffected)."""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/wip_backup.sh"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True, timeout=15
    ).stdout.strip()


def _seed_repo(root: Path, name: str) -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-qm", "base")
    return repo


def _run(root: Path) -> str:
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        env={"PATH": "/usr/bin:/bin", "WIP_BACKUP_ROOT": str(root), "HOME": str(root)},
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_snapshot_captures_all_without_touching_agent_state(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, "proj")
    # An agent's in-flight state: one STAGED file, one unstaged edit, one untracked.
    (repo / "staged.txt").write_text("staged by sibling\n")
    _git(repo, "add", "staged.txt")
    (repo / "base.txt").write_text("unstaged edit\n")
    (repo / "untracked.txt").write_text("brand new\n")
    head_before = _git(repo, "rev-parse", "HEAD")

    _run(tmp_path)

    # Snapshot exists and contains all three states.
    tree_files = _git(repo, "ls-tree", "-r", "--name-only", "refs/wip/autobackup")
    assert {"base.txt", "staged.txt", "untracked.txt"} <= set(tree_files.splitlines())
    assert "unstaged edit" in _git(repo, "show", "refs/wip/autobackup:base.txt")
    # Agent state UNTOUCHED: HEAD same, staged file still (and only) staged.
    assert _git(repo, "rev-parse", "HEAD") == head_before
    staged = _git(repo, "diff", "--cached", "--name-only")
    assert staged.splitlines() == ["staged.txt"]
    assert _git(repo, "stash", "list") == ""


def test_clean_repo_and_unchanged_dirty_repo_are_skipped(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path, "clean")
    _run(tmp_path)
    assert subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "refs/wip/autobackup"],
        cwd=repo, capture_output=True,
    ).returncode != 0  # clean → no snapshot

    (repo / "x.txt").write_text("dirty\n")
    _run(tmp_path)
    first = _git(repo, "rev-parse", "refs/wip/autobackup")
    _run(tmp_path)  # dirty but unchanged → no new commit object
    assert _git(repo, "rev-parse", "refs/wip/autobackup") == first


def test_archived_dir_is_skipped(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path / "archived", "old")
    (repo / "y.txt").write_text("z\n")
    _run(tmp_path)
    assert subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "refs/wip/autobackup"],
        cwd=repo, capture_output=True,
    ).returncode != 0
