"""mail.py's mailbox name in git layouts where `git worktree list` names the git dir (W-7317befc).

`_current_repo()` used the first `worktree` line of `git worktree list --porcelain`. A repo made with
`--separate-git-dir` reports its GIT DIR there, and a `core.worktree` repo reports the git dir's
parent, so mail.py sent, listed, claimed and acked against a mailbox no other repo addresses.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_MAIL_PY = _REPO / "scripts" / "mail.py"

spec = importlib.util.spec_from_file_location("fabrik_mail_sepgit", _MAIL_PY)
mail = importlib.util.module_from_spec(spec)
sys.modules["fabrik_mail_sepgit"] = mail
spec.loader.exec_module(mail)

_ID = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, env={**os.environ, **_ID}
    )


@pytest.fixture
def separate(tmp_path):
    """`git init --separate-git-dir`: working tree `myproject`, git dir `store/gitdir`, plus a
    linked worktree `linked`."""
    work = tmp_path / "myproject"
    gitdir = tmp_path / "store" / "gitdir"
    gitdir.parent.mkdir()
    _git("init", "-q", "-b", "main", "--separate-git-dir", str(gitdir), str(work), cwd=tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=work)
    _git("worktree", "add", "-q", "-b", "wt", str(tmp_path / "linked"), cwd=work)
    return work, tmp_path / "linked"


def test_the_main_worktree_of_a_separate_git_dir_repo_names_its_working_tree(separate, monkeypatch):
    work, _linked = separate
    monkeypatch.chdir(work)
    assert mail._current_repo() == "myproject", "the mailbox was named after the git dir"


def test_a_linked_worktree_of_a_separate_git_dir_repo_refuses_instead_of_guessing(
    separate, monkeypatch
):
    """git records the main working tree nowhere in this layout, so a linked worktree cannot know
    the hub's mailbox; acting on `gitdir` would be silent mis-delivery."""
    _work, linked = separate
    monkeypatch.chdir(linked)
    with pytest.raises(SystemExit) as refused:
        mail._current_repo()
    assert refused.value.code not in (0, None)
    assert "separate git dir" in str(refused.value.code)


def test_a_core_worktree_repo_names_its_working_tree(tmp_path, monkeypatch):
    holder = tmp_path / "cw.git"
    work = tmp_path / "cwproject"
    work.mkdir()
    _git("init", "-q", "-b", "main", str(holder), cwd=tmp_path)
    _git("--git-dir", str(holder / ".git"), "config", "core.worktree", str(work), cwd=tmp_path)
    (work / ".git").write_text(f"gitdir: {holder / '.git'}\n")
    monkeypatch.chdir(work)
    assert mail._current_repo() == "cwproject", "the mailbox was named after the git dir's parent"


def test_a_normal_repo_and_its_linked_worktree_still_name_the_main_checkout(tmp_path, monkeypatch):
    main = tmp_path / "hubrepo"
    _git("init", "-q", "-b", "main", str(main), cwd=tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=main)
    _git("worktree", "add", "-q", "-b", "wt", str(tmp_path / "side"), cwd=main)
    for cwd in (main, tmp_path / "side"):
        monkeypatch.chdir(cwd)
        assert mail._current_repo() == "hubrepo", cwd


def test_a_cwd_inside_a_normal_repos_git_dir_still_names_the_repo(tmp_path, monkeypatch):
    """`rev-parse --show-toplevel` fails inside `.git`; asking it unconditionally would have sent this
    case to the cwd fallback and named the mailbox `.git` (Opus critique C1)."""
    main = tmp_path / "hubrepo"
    _git("init", "-q", "-b", "main", str(main), cwd=tmp_path)
    monkeypatch.chdir(main / ".git")
    assert mail._current_repo() == "hubrepo"


def test_a_per_worktree_core_worktree_does_not_rename_the_hub(tmp_path, monkeypatch):
    """core.worktree is read from the COMMON dir's config: a linked worktree's own
    `config --worktree core.worktree` must not make it name itself (Opus critique C2)."""
    main = tmp_path / "hubrepo"
    _git("init", "-q", "-b", "main", str(main), cwd=tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "x", cwd=main)
    side = tmp_path / "side"
    _git("worktree", "add", "-q", "-b", "wt", str(side), cwd=main)
    _git("config", "extensions.worktreeConfig", "true", cwd=main)
    _git("config", "--worktree", "core.worktree", str(side), cwd=side)
    monkeypatch.chdir(side)
    assert mail._current_repo() == "hubrepo"


def test_the_work_store_lookup_treats_an_unplaceable_repo_as_not_ours(separate, monkeypatch):
    """`claim`/`ack --repo X` from a linked worktree git cannot place: no store, no stray error
    line from the item hooks (Opus critique C6)."""
    _work, linked = separate
    monkeypatch.chdir(linked)
    assert mail._mail_store("myproject") is None
