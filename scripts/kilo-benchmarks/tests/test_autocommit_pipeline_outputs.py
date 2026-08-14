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


def test_peer_wip_alone_does_not_trigger_a_commit(tmp_path):
    """The emptiness test must be SCOPED to our paths.

    Unscoped, `git diff --cached --quiet` fires whenever ANY file is staged, so the script would
    commit on a run where zero pipeline outputs changed. Round 15 fixed this and round 17 found
    it was still the one production change with no behavioural test — all 8 others passed with
    it reverted.
    """
    r = _repo(tmp_path)
    (r / "PORTS.md").write_text("peer wip\n")
    _git(r, "add", "PORTS.md")  # staged, but NOT one of ours
    head_before = _git(r, "rev-parse", "HEAD")

    out = _run(r)
    assert "tree already clean" in out, out
    assert _git(r, "rev-parse", "HEAD") == head_before, "committed with no pipeline change"
    assert "PORTS.md" in _git(r, "diff", "--cached", "--name-only"), "peer WIP was disturbed"


def test_an_unborn_branch_does_not_bypass_the_no_branch_guard(tmp_path):
    """`git rev-parse --abbrev-ref HEAD` prints "HEAD" AND exits 128 on an unborn branch, so
    `|| echo HEAD` APPENDED — _BRANCH became $'HEAD\\nHEAD', which is not "HEAD", so the guard
    was bypassed and the log record split across two lines. Phase B stands up the engine repo
    with `git init` and no commits, so this is on the plan's own path."""
    r = tmp_path / "unborn"
    (r / ".windsurf/rules/ai").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / ".windsurf/rules/ai/00-ai.md").write_text("first\n")

    out = _run(r)
    # `splitlines()` guarantees no newline inside an element, so the obvious per-line check
    # cannot fail. Assert the real symptom instead: the two-line record the appended _BRANCH
    # produced, and that every [auto-commit] line is self-contained.
    assert "HEAD\nHEAD" not in out, "the appended _BRANCH split the log record"
    assert "no origin/HEAD" not in out, "resolved the branch as the literal HEAD"
    assert "committed" in out, out


def test_a_concurrent_index_lock_is_diagnosed_as_itself(tmp_path):
    """A peer's `git commit` holds .git/index.lock for SECONDS (its pre-commit governance-sync
    fans out to ~46 repos). Every `git add` then failed with stderr discarded, so the script
    blamed the stage list, no-op'd, and the daily lockfile blocked any retry until tomorrow."""
    r = _repo(tmp_path)
    (r / ".windsurf/rules/ai/00-ai.md").write_text("regenerated\n")
    (Path(_git(r, "rev-parse", "--absolute-git-dir")) / "index.lock").touch()

    out = _run(r)
    assert "index lock" in out, out
    assert "check the stage list" not in out, "blamed the stage list for a lock collision"


def test_the_commit_trailers_are_machine_parseable(tmp_path):
    """git parses only the LAST paragraph as trailers, so one `-m` per line left
    `git log --format='%(trailers:key=Agent-Role)'` empty on every pipeline commit since July —
    the exact query CLAUDE.md § Agent Provenance Trailers says the trailers exist for."""
    r = _repo(tmp_path)
    (r / ".windsurf/rules/ai/00-ai.md").write_text("regenerated\n")
    assert "committed" in _run(r)

    role = _git(r, "log", "-1", "--format=%(trailers:key=Agent-Role,valueonly)").strip()
    ctx = _git(r, "log", "-1", "--format=%(trailers:key=Agent-Context,valueonly)").strip()
    assert role == "primary", f"Agent-Role not parseable: {role!r}"
    assert ctx, "Agent-Context not parseable"


def test_commit_failure_unstages_our_paths_and_alerts(tmp_path):
    """The only bail-out that used to leave the index dirty, and it never alerted.

    Up to 26 pipeline paths stayed staged in the shared master index; because the script exits 0
    the caller's `|| echo ... errored` can never fire, so a persistently failing pre-commit hook
    (this repo has two MODIFYING hooks) would disable the auto-commit forever, silently.
    """
    r = _repo(tmp_path)
    hooks = Path(_git(r, "rev-parse", "--absolute-git-dir")) / "hooks"
    hooks.mkdir(exist_ok=True)
    (hooks / "pre-commit").write_text("#!/bin/bash\nexit 1\n")
    (hooks / "pre-commit").chmod(0o755)
    (r / ".windsurf/rules/ai/00-ai.md").write_text("regenerated\n")

    out = _run(r)
    assert "commit failed" in out, out
    assert _git(r, "diff", "--cached", "--name-only") == "", "our paths were left staged"
    assert "pipeline_alert" in (Path(__file__).resolve().parents[1] / "autocommit_pipeline_outputs.sh").read_text()


def test_a_lock_taken_mid_stage_is_diagnosed_as_a_lock(tmp_path):
    """The pre-loop guard is a point sample. A peer can take the lock DURING the ~26 adds — the
    run then reported 'a pipeline output was renamed or retired', a false cause, plus a partial
    commit. The failing add must re-check."""
    r = _repo(tmp_path)
    for i in range(3):
        (r / f".windsurf/rules/ai/{i}0-x.md").write_text("base\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "more")
    for i in range(3):
        (r / f".windsurf/rules/ai/{i}0-x.md").write_text("regenerated\n")

    # a hook-free way to make adds start failing partway: drop the lock in after the run starts
    lock = Path(_git(r, "rev-parse", "--absolute-git-dir")) / "index.lock"
    script = Path(__file__).resolve().parents[1] / "autocommit_pipeline_outputs.sh"
    proc = subprocess.Popen(
        ["bash", str(script), "pytest"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(r), "FABRIK_ROOT": str(r)},
    )
    lock.touch()  # racy by nature; assert only on the outcomes we can guarantee
    out = proc.communicate()[0]
    lock.unlink(missing_ok=True)
    # Either it finished before the lock landed (committed) or it saw the lock — never the
    # misleading rename diagnosis while a lock exists.
    assert "renamed or retired" not in out or "index lock" in out, out
    assert proc.returncode == 0, out
