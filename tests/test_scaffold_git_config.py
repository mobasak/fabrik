"""A scaffolded repo comes out of `git init` with the two config keys the fleet's workflow needs.

Mail 01M1NX7FS39E8999W2R6VSE5XD (intel → fleet): `grep -n 'git config\\|rerere\\|autoSetupRemote'
src/fabrik/scaffold.py` returned ZERO lines, and neither key is set globally on this box or in any
existing project (`/opt/seo`, `/opt/youtube`, `/opt/transdoc` — all unset), so every repo the
scaffolder makes starts without them:

* `push.autoSetupRemote` — without it the first `git push` from a new branch fails on "no upstream",
  which is every scaffolded project's first push and every worktree branch's first push under the
  approved multi-agent model (D-113).
* `rerere.enabled` — without it a merge conflict resolved once must be resolved again by hand on
  every replay, which is the whole point of the three-window merge flow.

Scoped deliberately to what scaffold OWNS: a repo it creates. The same keys on the ~46 EXISTING
projects ride the sync, which is the multi-agent build plan's job (Owner: infra, D-114), not this.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from fabrik.scaffold import _configure_git_repo


def _init(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def _cfg(repo: Path, key: str) -> str | None:
    out = subprocess.run(
        ["git", "config", "--local", "--get", key], cwd=repo, capture_output=True, text=True
    )
    return out.stdout.strip() if out.returncode == 0 else None


def test_a_scaffolded_repo_can_push_a_new_branch_without_set_upstream(tmp_path: Path):
    repo = _init(tmp_path)
    assert _cfg(repo, "push.autoSetupRemote") is None, "guard: git init leaves it unset"

    _configure_git_repo(repo)

    assert _cfg(repo, "push.autoSetupRemote") == "true"


def test_a_scaffolded_repo_remembers_a_conflict_resolution(tmp_path: Path):
    repo = _init(tmp_path)
    assert _cfg(repo, "rerere.enabled") is None, "guard: git init leaves it unset"

    _configure_git_repo(repo)

    assert _cfg(repo, "rerere.enabled") == "true"


def test_it_writes_local_config_only_and_never_touches_the_users_global(tmp_path: Path):
    """The blast radius is the repo being created. A `--global` write here would reach every
    repository on the box, including the hub and the other agents' checkouts."""
    repo = _init(tmp_path)
    _configure_git_repo(repo)
    body = (repo / ".git" / "config").read_text()
    assert "autosetupremote" in body.lower() and "rerere" in body.lower(), (
        "both keys must land in the repo's OWN config file"
    )


def test_an_existing_operator_choice_is_never_overwritten(tmp_path: Path):
    """A project that deliberately turned a key off keeps its answer — the scaffolder seeds a
    default, it does not enforce a policy."""
    repo = _init(tmp_path)
    subprocess.run(
        ["git", "config", "--local", "rerere.enabled", "false"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    _configure_git_repo(repo)

    assert _cfg(repo, "rerere.enabled") == "false"
    assert _cfg(repo, "push.autoSetupRemote") == "true", "the unset key is still seeded"


def test_it_never_raises_when_the_directory_is_not_a_git_repo(tmp_path: Path):
    """A scaffold that otherwise succeeded must not die here — `git init` is best-effort in
    scaffold.py (`capture_output=True`, no `check`), so this must be too."""
    _configure_git_repo(tmp_path / "does-not-exist")
    _configure_git_repo(tmp_path)  # exists, but no .git


def test_the_scaffolder_actually_calls_it_right_after_git_init(tmp_path: Path):
    """The assertion that matters: a helper nobody calls is dead code. This runs the real
    `_scaffold_shared` — the function that owns `git init` — and reads the resulting repo's
    config, rather than grepping the source for the call."""
    from fabrik import scaffold

    project_dir = tmp_path / "svc"
    project_dir.mkdir()

    scaffold._scaffold_shared(project_dir, "svc", "Test service", "2026-09-04", 8099, "python-api")

    assert (project_dir / ".git").is_dir(), "guard: the scaffolder really did init a repo here"
    assert _cfg(project_dir, "push.autoSetupRemote") == "true"
    assert _cfg(project_dir, "rerere.enabled") == "true"
