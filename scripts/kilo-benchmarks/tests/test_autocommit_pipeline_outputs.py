# AFTER-EDIT: autocommit_pipeline_outputs.sh, wsl_startup_hook.sh
"""Behavioural tests for the pipeline auto-commit — it RUNS the script, it does not read it.

Round 15 shipped three production fixes with no test at all (the "3/3 red on revert" claim in
that commit was true of the test rewrites, not the behaviour changes), and round 16 then found
two of them defective. Every test here drives the real script against a real throwaway git repo
via FABRIK_ROOT, because the defects in this file have all been behavioural:

  * `git add` on a conflicted path marks it RESOLVED, staging `<<<<<<<` markers into the index
  * REBASE_HEAD survives a COMPLETED rebase, so a ref-based guard is a permanent kill switch
  * a bail placed after the stage still leaves the index dirty

None of those is visible by grepping the source.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "autocommit_pipeline_outputs.sh"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    (r / ".windsurf/rules/ai").mkdir(parents=True)
    (r / "docs/reference/kilo").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / ".windsurf/rules/ai/00-ai.md").write_text("base\n")
    (r / "docs/reference/kilo/TTS_SELECTION.md").write_text("base\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "base")
    return r


def _run(repo: Path) -> str:
    p = subprocess.run(
        ["bash", str(SCRIPT), "pytest"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(repo), "FABRIK_ROOT": str(repo)},
    )
    return p.stdout + p.stderr


def test_it_commits_only_its_own_paths_and_leaves_peer_wip_staged(tmp_path):
    """The HARD STOP: commit with a pathspec, never the index."""
    r = _repo(tmp_path)
    (r / "PORTS.md").write_text("peer wip\n")
    _git(r, "add", "PORTS.md")  # a peer stages unrelated work
    (r / ".windsurf/rules/ai/00-ai.md").write_text("regenerated\n")

    out = _run(r)
    assert "committed" in out, out
    committed = _git(r, "show", "--name-only", "--format=", "HEAD").split()
    assert committed == [".windsurf/rules/ai/00-ai.md"], committed
    assert "PORTS.md" in _git(r, "diff", "--cached", "--name-only")


def test_a_sticky_rebase_head_does_not_disable_it_forever(tmp_path):
    """git leaves REBASE_HEAD in place after a CONFLICTED rebase COMPLETES.

    CLAUDE.md's push ladder mandates `git pull --rebase=merges`, so a ref-based guard meant the
    first agent to resolve a rebase conflict disabled this script permanently and silently.
    """
    r = _repo(tmp_path)
    _git(r, "checkout", "-qb", "side")
    (r / "docs/reference/kilo/TTS_SELECTION.md").write_text("side\n")
    _git(r, "commit", "-qam", "side")
    _git(r, "checkout", "-q", "main")
    (r / "docs/reference/kilo/TTS_SELECTION.md").write_text("main\n")
    _git(r, "commit", "-qam", "main")
    subprocess.run(["git", "-C", str(r), "rebase", "side"], capture_output=True)
    (r / "docs/reference/kilo/TTS_SELECTION.md").write_text("resolved\n")
    _git(r, "add", "-A")
    subprocess.run(
        ["git", "-C", str(r), "rebase", "--continue"],
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "GIT_EDITOR": "true", "HOME": str(r)},
    )
    assert subprocess.run(
        ["git", "-C", str(r), "rev-parse", "-q", "--verify", "REBASE_HEAD"],
        capture_output=True,
    ).returncode == 0, "this test is vacuous unless REBASE_HEAD is actually sticky"

    (r / ".windsurf/rules/ai/00-ai.md").write_text("regenerated\n")
    out = _run(r)
    assert "committed" in out, f"a completed rebase disabled the auto-commit:\n{out}"


def test_it_refuses_to_touch_a_mid_merge_index(tmp_path):
    """`git add` on a conflicted path marks it RESOLVED — staging the `<<<<<<<` markers. The
    commit then fails, but `git diff --diff-filter=U` reports clean and the sibling's next
    commit writes markers into master."""
    r = _repo(tmp_path)
    _git(r, "checkout", "-qb", "side")
    (r / "docs/reference/kilo/TTS_SELECTION.md").write_text("side\n")
    _git(r, "commit", "-qam", "side")
    _git(r, "checkout", "-q", "main")
    (r / "docs/reference/kilo/TTS_SELECTION.md").write_text("main\n")
    _git(r, "commit", "-qam", "main")
    subprocess.run(["git", "-C", str(r), "merge", "side"], capture_output=True)
    assert _git(r, "ls-files", "--unmerged"), "no conflict — test is vacuous"

    out = _run(r)
    assert "mid-operation" in out, out
    assert _git(r, "ls-files", "--unmerged"), "the conflict was silently resolved by git add"


def test_a_real_mid_rebase_still_refuses(tmp_path):
    """The mirror of the sticky-ref test: an ACTUAL in-progress rebase must still bail."""
    r = _repo(tmp_path)
    _git(r, "checkout", "-qb", "side")
    (r / "docs/reference/kilo/TTS_SELECTION.md").write_text("side\n")
    _git(r, "commit", "-qam", "side")
    _git(r, "checkout", "-q", "main")
    (r / "docs/reference/kilo/TTS_SELECTION.md").write_text("main\n")
    _git(r, "commit", "-qam", "main")
    subprocess.run(["git", "-C", str(r), "rebase", "side"], capture_output=True)
    # `--git-path` returns a path relative to the REPO, so resolve it there — the script does
    # the same implicitly by `cd`-ing to FABRIK_ROOT before checking.
    assert (r / _git(r, "rev-parse", "--git-path", "rebase-merge")).exists(), "not mid-rebase"

    out = _run(r)
    assert "mid-rebase" in out, out


def test_detached_head_stages_nothing(tmp_path):
    """The bail moved above the COMMIT in round 15 but not above the ADD, so it still left
    pipeline files staged while printing 'refusing' — breaking the file's own contract."""
    r = _repo(tmp_path)
    _git(r, "checkout", "-q", "--detach")
    (r / ".windsurf/rules/ai/00-ai.md").write_text("regenerated\n")

    out = _run(r)
    assert "DETACHED HEAD" in out, out
    assert _git(r, "diff", "--cached", "--name-only") == "", "the index was touched anyway"
    assert _git(r, "log", "--oneline", "HEAD", "^main") == "", "committed onto no branch"


def test_a_retired_path_does_not_disable_the_whole_run(tmp_path):
    """`git add` is all-or-nothing: one missing path exited 128 with NOTHING staged, and the
    guard then reported 'tree already clean'. Phase B copies this into a repo where most of
    these paths do not exist."""
    r = _repo(tmp_path)
    (r / ".windsurf/rules/ai/00-ai.md").write_text("regenerated\n")
    out = _run(r)
    assert "WARNING" in out and "stage paths matched" in out, out
    assert "committed" in out, out


@pytest.mark.parametrize("subdir", ["", "docs"])
def test_it_never_exits_nonzero(tmp_path, subdir):
    """Every path must exit 0 — this runs inside a boot hook that must not be abortable."""
    r = _repo(tmp_path)
    if subdir:
        (r / subdir).mkdir(exist_ok=True)
    p = subprocess.run(
        ["bash", str(SCRIPT), "pytest"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(r), "FABRIK_ROOT": str(r / subdir)},
    )
    assert p.returncode == 0, f"exit {p.returncode}: {p.stdout}{p.stderr}"
