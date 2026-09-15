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


def test_a_shared_append_file_never_attributes_a_commit_on_its_own(tmp_path: Path) -> None:
    """⚠️ THE HOLE THE FIRST CUT LEFT, and it was the common case rather than a corner.

    `authored` is the WHOLE transcript with no time filter, so on a multi-day resumed session it
    is every file the session ever touched — `CHANGELOG.md` included, because every task-end
    writes one. A sibling's task-end commit (their own file PLUS the shared CHANGELOG entry) was
    therefore attributed to any session that had ever touched CHANGELOG.md, which is all of them.
    Executed on the live repo: 109 of the last 200 commits touch one of these names.

    `_failure_cites_session` already carries this exact rule for the same reason — "every session
    writes them" — so this is the house pattern applied to the cause that was missing it."""
    repo = _repo_with_upstream(tmp_path)
    (repo / "CHANGELOG.md").write_text("### Fixed — their entry\n")
    (repo / "sibling_only.py").write_text("SIBLING = 1\n")
    _git(repo, "add", "CHANGELOG.md", "sibling_only.py")
    _git(repo, "commit", "-qm", "sibling task-end")

    # this session wrote a CHANGELOG entry at some point; it never touched sibling_only.py
    assert hook._ahead_of_upstream(repo, {"CHANGELOG.md"}) in (None, 0), (
        "a sibling's commit was attributed to this session through the shared CHANGELOG"
    )
    assert hook._ahead_of_upstream(repo, {"CHANGELOG.md", "mine.py"}) == 0

    # ...and a file that IS distinctively this session's still attributes, or the rule has simply
    # switched the cause off
    assert hook._ahead_of_upstream(repo, {"sibling_only.py"}) == 1


def test_a_non_ascii_path_is_not_lost_to_quotepath(tmp_path: Path) -> None:
    """git escapes a non-ASCII path (`"docs/caf\\303\\251.py"`) while `_session_files` stores it
    decoded, so the push law went silent on exactly the file the session authored. `_dirty_paths`
    already passes `core.quotePath=false` for the same reason."""
    repo = _repo_with_upstream(tmp_path)
    rel = "docs/café.py"
    (repo / "docs").mkdir(exist_ok=True)
    (repo / rel).write_text("CAFE = 1\n", encoding="utf-8")
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", "non-ascii")
    assert hook._ahead_of_upstream(repo, {rel}) == 1, (
        "the push law is silent on a non-ASCII path the session authored"
    )


def test_a_renamed_file_still_attributes_to_the_session_that_edited_it(tmp_path: Path) -> None:
    """Rename detection prints only the NEW path, so a session that edited `a.py` with Edit and
    then `git mv`-ed it in Bash attributed nothing. `--no-renames` prints both halves."""
    repo = _repo_with_upstream(tmp_path)
    _commit(repo, "a.py", "A = 1\n")
    _git(repo, "mv", "a.py", "b.py")
    _git(repo, "commit", "-qm", "rename")
    assert hook._ahead_of_upstream(repo, {"a.py"}) >= 1, "the pre-rename name attributed nothing"


def test_the_range_costs_one_subprocess_not_one_per_commit(tmp_path: Path, monkeypatch) -> None:
    """The per-commit form cost ~3 ms each with a `timeout=15` PER COMMIT, so a git stalled on
    `index.lock` — three sessions commit to this tree — gave a worst case of 15s x N inside a Stop
    hook. Counted, not timed: a timing assertion on a shared box is a flake."""
    repo = _repo_with_upstream(tmp_path)
    for i in range(5):
        _commit(repo, f"mine{i}.py", f"M = {i}\n")
    calls: list[list[str]] = []
    real = hook.subprocess.run

    def counting(cmd, *a, **k):
        calls.append(list(cmd))
        return real(cmd, *a, **k)

    monkeypatch.setattr(hook.subprocess, "run", counting)
    assert hook._ahead_of_upstream(repo, {"mine0.py", "mine3.py"}) == 2
    assert len(calls) == 1, f"{len(calls)} subprocesses for a 5-commit range: {calls}"
