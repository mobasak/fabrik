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
