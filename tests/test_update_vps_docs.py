"""Grader for scripts/update_vps_docs.py `_push_with_ladder` — the daily VPS-docs pipeline must PUSH
after it commits, else its commit sits off-box-unprotected on shared master and trips every
interactive session's Stop hook (finding 01M163KJFF, infra→fleet 2026-08-29). The push follows the
CLAUDE.md rejection ladder: on a concurrent rejection, `pull --rebase=merges` then retry ONCE, never
`--force`.
"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

_SPEC = importlib.util.spec_from_file_location(
    "update_vps_docs", Path(__file__).resolve().parents[1] / "scripts" / "update_vps_docs.py"
)
uvd = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(uvd)


def _run(returncodes):
    """A subprocess.run stub returning the given rc sequence; records the git subcommands seen."""
    calls = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        rc = returncodes[min(len(calls) - 1, len(returncodes) - 1)]
        return MagicMock(returncode=rc, stderr="", stdout="")

    return fake_run, calls


def test_push_succeeds_first_try_single_push():
    fake, calls = _run([0])
    with patch.object(uvd.subprocess, "run", side_effect=fake):
        assert uvd._push_with_ladder() is True
    assert len(calls) == 1
    assert calls[0][-1] == "push"  # exactly one push, no pull needed


def test_rejected_push_rebases_then_retries_and_never_forces():
    # push rejected (1) → pull --rebase=merges → push again (0). Ladder, no --force.
    fake, calls = _run([1, 0, 0])
    with patch.object(uvd.subprocess, "run", side_effect=fake):
        assert uvd._push_with_ladder() is True
    joined = [" ".join(c) for c in calls]
    assert any("pull --rebase=merges" in j for j in joined), "must rebase on rejection"
    assert sum(j.endswith("push") for j in joined) == 2, "one initial push + one retry"
    assert not any("--force" in j or c[-1] == "-f" for j, c in zip(joined, calls, strict=True)), (
        "NEVER --force"
    )


def test_push_still_failing_returns_false_leaves_commit_local():
    # both pushes fail → returns False (commit stays local for a session to push; not a crash).
    fake, calls = _run([1, 0, 1])  # push fail, pull, push fail
    with patch.object(uvd.subprocess, "run", side_effect=fake):
        assert uvd._push_with_ladder() is False


# ── The commit must carry a PATHSPEC — a bare commit takes the whole shared index ──────────────
# Found 2026-09-05 while reviewing an unrelated change: this script's `git add` was correctly
# scoped to three files, but the `git commit` that followed took NO pathspec, so it committed the
# entire index. On a tree with three concurrent Claude sessions that means every file any other
# session had staged. Commit 5b9c420d ("docs(auto): update VPS docs from live state") swept
# INDEX.md, a design spec, scripts/vps_apply_limits.sh and a 280-line new test file out of another
# session's in-flight work, under this script's automated message — and pushed them.
#
# The bite is worse than it first looks: STAGING is how an agent protects work from pre-commit's
# stash, so this defect specifically ate the work that was being handled most carefully.


def test_the_commit_is_scoped_to_a_pathspec_and_it_matches_what_was_staged():
    """Structural half: the argv this script builds must carry `--` plus exactly the paths it
    staged. Single-sourcing them through VPS_DOC_PATHS is what stops the two drifting apart."""
    src = (Path(__file__).resolve().parents[1] / "scripts" / "update_vps_docs.py").read_text()

    assert "VPS_DOC_PATHS" in src, "the staged path list is not single-sourced"
    assert len(uvd.VPS_DOC_PATHS) == 3
    assert all(p.startswith("docs/infrastructure/vps-") for p in uvd.VPS_DOC_PATHS)

    # The commit invocation must contain the pathspec separator followed by the same constant.
    commit_call = src[src.index('"commit",'):]
    commit_call = commit_call[: commit_call.index("check=True")]
    assert '"--",' in commit_call, "git commit has NO pathspec — it will take the whole index"
    assert "*VPS_DOC_PATHS" in commit_call, "the commit pathspec is not the list that was staged"


def test_a_bare_commit_really_does_steal_a_sibling_staged_file(tmp_path):
    """Behavioural half: prove the MECHANISM the structural test relies on, in a real repo, so the
    assertion above is not merely a spelling convention. Without a pathspec git takes the whole
    index; with one it takes only the named paths."""
    import subprocess

    def git(*a, cwd):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)

    for scoped in (False, True):
        repo = tmp_path / ("scoped" if scoped else "bare")
        repo.mkdir()
        git("init", "-q", cwd=repo)
        git("config", "user.email", "t@t", cwd=repo)
        git("config", "user.name", "t", cwd=repo)
        (repo / "mine.md").write_text("v1\n")
        (repo / "sibling.py").write_text("v1\n")
        git("add", ".", cwd=repo)
        git("commit", "-qm", "base", cwd=repo)

        # this script's file changes...
        (repo / "mine.md").write_text("v2\n")
        git("add", "mine.md", cwd=repo)
        # ...while ANOTHER session has staged its own in-flight work
        (repo / "sibling.py").write_text("SIBLING WIP\n")
        git("add", "sibling.py", cwd=repo)

        if scoped:
            git("commit", "-qm", "auto", "--", "mine.md", cwd=repo)
        else:
            git("commit", "-qm", "auto", cwd=repo)

        files = git("show", "--stat", "--format=", "--name-only", "HEAD", cwd=repo).stdout.split()
        if scoped:
            assert files == ["mine.md"], f"pathspec did not protect the sibling: {files}"
        else:
            assert "sibling.py" in files, (
                "expected the bare commit to steal the sibling's staged file — if this ever fails, "
                "git's semantics changed and the fix above needs revisiting"
            )
