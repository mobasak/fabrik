"""final_gate.py's change set on a linked-worktree branch with no upstream (tryton-crm 01M3PKJP).

The multi-agent model puts agents 2..N on worktree branches that have no upstream, and a repo's
base branch need not be master/main. `_diff_base` then found nothing, the change set shrank to the
working tree, and a worktree whose code was COMMITTED read as docs-only — a false green that ran
no static tier. The base must fall back to the main checkout's branch.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import final_gate  # noqa: E402


def _git(cwd: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    return subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    ).stdout


def _layout(tmp_path: Path) -> tuple[Path, Path]:
    main = tmp_path / "main"
    _git(tmp_path, "init", "-q", "-b", "owner/trunk", str(main))
    (main / "README.md").write_text("seed\n", encoding="utf-8")
    _git(main, "add", "README.md")
    _git(main, "commit", "-q", "-m", "seed")
    wt = main / ".claude" / "worktrees" / "agent-2"
    _git(main, "worktree", "add", "-q", "-b", "worktree-agent-2", str(wt), "HEAD")
    return main, wt


def test_a_worktree_branch_with_no_upstream_diffs_against_the_main_checkouts_branch(
    tmp_path, monkeypatch
):
    main, wt = _layout(tmp_path)
    (wt / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(wt, "add", "code.py")
    _git(wt, "commit", "-q", "-m", "code")
    (wt / "README.md").write_text("seed\nedit\n", encoding="utf-8")  # the only uncommitted file
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", wt)
    assert final_gate._diff_base() == "owner/trunk"
    changed = final_gate.get_changed_files()
    assert "code.py" in changed, changed
    assert "README.md" in changed, changed


def test_a_worktree_of_a_bare_repository_diffs_against_the_bare_repos_branch(tmp_path, monkeypatch):
    main, _wt = _layout(tmp_path)
    bare = tmp_path / "bare.git"
    _git(tmp_path, "clone", "-q", "--bare", str(main), str(bare))
    wt = tmp_path / "wt"
    _git(bare, "worktree", "add", "-q", "-b", "feature", str(wt), "owner/trunk")
    (wt / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(wt, "add", "code.py")
    _git(wt, "commit", "-q", "-m", "code")
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", wt)
    assert final_gate._diff_base() == "owner/trunk"
    assert "code.py" in final_gate.get_changed_files()


def test_the_main_checkout_itself_keeps_no_base_when_nothing_is_remote(tmp_path, monkeypatch):
    main, _wt = _layout(tmp_path)
    monkeypatch.setattr(final_gate, "PROJECT_ROOT", main)
    assert final_gate._diff_base() is None
