"""The UNPUSHED cause counts only commits THIS SESSION authored (T13.4, mail 01M20E1QN).

The block's own text says "push YOUR work" while the count was every commit in
`@{upstream}..HEAD` — so on a tree three sessions commit to, it ordered a SIBLING's unpushed
commit published. Publishing someone else's commit is not a smaller mistake than leaving your
own unpushed; it is the one the push law never asked for.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

_HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "final_gate_stop.py"
_spec = importlib.util.spec_from_file_location("fgs_push_attr", _HOOK)
hook = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(hook)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def _repo_with_upstream(tmp_path: Path) -> Path:
    """A repo whose branch has an upstream, so the cause is determinate at all."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    work = tmp_path / "work"
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(work, "config", *cfg)
    (work / "seed.txt").write_text("seed\n")
    _git(work, "add", "seed.txt")
    _git(work, "commit", "-qm", "seed")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-q", "-u", "origin", "HEAD")
    return work


def _commit(repo: Path, rel: str, body: str) -> None:
    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
    (repo / rel).write_text(body)
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", f"touch {rel}")


def test_a_siblings_unpushed_commit_is_not_counted_as_mine(tmp_path: Path) -> None:
    """The defect, reproduced: one unpushed commit, authored by someone else."""
    repo = _repo_with_upstream(tmp_path)
    _commit(repo, "theirs.py", "SIBLING = 1\n")
    assert _git(repo, "rev-list", "--count", "@{upstream}..HEAD") == "1"
    # this session edited a DIFFERENT file
    assert hook._ahead_of_upstream(repo, {"mine.py"}) == 0, (
        "a sibling's commit counted as this session's unpushed work"
    )


def test_my_own_unpushed_commit_is_counted(tmp_path: Path) -> None:
    """...and the cause must still FIRE, or scoping it has simply disabled the push law."""
    repo = _repo_with_upstream(tmp_path)
    _commit(repo, "mine.py", "MINE = 1\n")
    assert hook._ahead_of_upstream(repo, {"mine.py"}) == 1


def test_a_mixed_range_counts_only_mine(tmp_path: Path) -> None:
    repo = _repo_with_upstream(tmp_path)
    _commit(repo, "theirs.py", "SIBLING = 1\n")
    _commit(repo, "mine.py", "MINE = 1\n")
    _commit(repo, "theirs2.py", "SIBLING = 2\n")
    assert _git(repo, "rev-list", "--count", "@{upstream}..HEAD") == "3"
    assert hook._ahead_of_upstream(repo, {"mine.py"}) == 1


def test_no_authored_set_is_indeterminate_never_everything(tmp_path: Path) -> None:
    """⚠️ THE FAIL DIRECTION. This cause BLOCKS an exit, so an unattributable range must let the
    stop through, never trap the session behind work it cannot prove is its own. Empty and None
    both mean "cannot attribute", which is `None` — the value `decide_stall` reads as false."""
    repo = _repo_with_upstream(tmp_path)
    _commit(repo, "theirs.py", "SIBLING = 1\n")
    assert hook._ahead_of_upstream(repo, set()) is None
    assert hook._ahead_of_upstream(repo) is None


def test_a_clean_range_is_zero_not_none(tmp_path: Path) -> None:
    """Nothing to push is a real answer, and distinct from "cannot tell"."""
    repo = _repo_with_upstream(tmp_path)
    assert hook._ahead_of_upstream(repo, {"mine.py"}) == 0


def test_no_upstream_stays_indeterminate(tmp_path: Path) -> None:
    """Throwaway repos and mid-plan worktree branches have no upstream by design."""
    work = tmp_path / "solo"
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    for cfg in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        _git(work, "config", *cfg)
    (work / "a.py").write_text("A = 1\n")
    _git(work, "add", "a.py")
    _git(work, "commit", "-qm", "solo")
    assert hook._ahead_of_upstream(work, {"a.py"}) is None
