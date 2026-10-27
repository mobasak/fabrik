"""`_merged_from` must not read a `Merged-From` trailer off a MERGE commit (W-69322546)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "scratch_sweep.py"


def _mod():
    spec = importlib.util.spec_from_file_location("scratch_sweep_merged_from_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=30, check=True
    )


def _commit(repo: Path, name: str, msg: str) -> None:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", msg)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _commit(repo, "base.txt", "base")
    return repo


def test_merge_commit_trailer_does_not_vouch_for_a_reused_branch_name(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(repo, "side.txt", "side")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "main.txt", "main")
    _git(repo, "merge", "-q", "--no-ff", "side", "-m", "hand merge\n\nMerged-From: worktree-x")
    _git(repo, "checkout", "-q", "-b", "worktree-x", "HEAD~1")
    _commit(repo, "x.txt", "unmerged work")
    _git(repo, "checkout", "-q", "main")
    assert _mod()._merged_from(repo, "main", "worktree-x") is False


def test_squash_commit_trailer_still_vouches(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "worktree-y")
    _commit(repo, "y.txt", "y work")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "y-squash.txt", "squash y\n\nMerged-From: worktree-y")
    assert _mod()._merged_from(repo, "main", "worktree-y") is True
