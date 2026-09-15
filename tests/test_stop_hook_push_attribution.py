"""The UNPUSHED cause counts only commits THIS SESSION authored (T13.4, mail 01M20E1QN).

The block's own text says "push YOUR work" while the count was every commit in
`@{upstream}..HEAD` — so on a tree three sessions commit to, it ordered a SIBLING's unpushed
commit published. Publishing someone else's commit is not a smaller mistake than leaving your
own unpushed; it is the one the push law never asked for.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

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
    Executed on the live repo (`git -C /opt/fabrik log -200 --name-only`, population = 200):
    **109** of the last 200 commits touch one of these SEVEN names — 91 via the five listed
    originally, 54 via `docs/DECISIONS.md` / `docs/STRATEGIC_BACKLOG.md`, which were missing until
    round 2 of this review. The 109 was cited while only five were implemented, so the number was
    measured over a population the code did not have.

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


def test_an_ancient_edit_does_not_make_a_siblings_commit_mine(tmp_path):
    """The floor, applied at the CALL SITE, is what keeps this cause out of the trapping
    direction. `_ahead_of_upstream` is handed `distinctive` — the files this session edited —
    and on a RESUMED transcript the unfloored map is every file the session ever touched
    (454 code files over 116 days in one sid, measured). A sibling committing to any of them
    then reads as my unpushed work, and the hook blocks a session behind someone else's commit.
    """
    work = _repo_with_upstream(tmp_path)
    (work / "old_file.py").write_text("# a sibling's edit to a file I touched weeks ago\n")
    _git(work, "add", "old_file.py")
    _git(work, "commit", "-qm", "sibling's commit")

    ancient, recent = 1_000_000_000, 2_000_000_000
    authored_map = {"old_file.py": ancient}

    # unfloored — the shape that trapped: the ancient edit still counts as distinctive
    assert hook._ahead_of_upstream(work, set(authored_map)) == 1

    # floored at a baseline NEWER than the edit — the edit drops, nothing is distinctive,
    # and an indeterminate answer (None) never blocks
    floored = set(hook._this_sessions_edits(authored_map, recent))
    assert floored == set()
    assert hook._ahead_of_upstream(work, floored) is None

    # and an edit INSIDE the window still counts, or the fix would have disabled the cause
    live = set(hook._this_sessions_edits({"old_file.py": recent}, ancient))
    assert live == {"old_file.py"}
    assert hook._ahead_of_upstream(work, live) == 1


def test_both_push_call_sites_pass_the_floored_set(tmp_path):
    """A structural guard beside the behavioural one: the fix lives at the CALL SITES, so a
    future edit could revert either one and every behavioural test above would still pass —
    they exercise `_ahead_of_upstream` directly, not the callers."""
    src = _HOOK.read_text(encoding="utf-8")
    assert "def _baseline_floor(" in src
    # no call site may hand it the raw lifetime map again
    assert "_ahead_of_upstream(root, set(authored_map))" not in src
    assert src.count("_ahead_of_upstream(") == 3  # the def + exactly two call sites
    for call in ("ahead = _ahead_of_upstream(", "push_attempts if _ahead_of_upstream("):
        i = src.index(call)
        window = src[i : i + 240]
        assert "_this_sessions_edits(authored_map, _baseline_floor(sid))" in window, window


def test_a_missing_baseline_does_not_restore_the_lifetime_edit_set():
    """`_this_sessions_edits` reads a FALSY floor as "no floor" and keeps every entry, so a
    `_baseline_floor` returning 0.0 on an unreadable baseline silently restored the LIFETIME set —
    the exact defect the helper was added to close, in the case this hook elsewhere calls routine
    ("No baseline (SessionStart didn't run / older session)"). The sibling `_sixth_cause_floor`
    never had the hole because it takes a `max()` with the edit-age window."""
    import time as _t

    floor = hook._baseline_floor("nonexistent-probe-sid-zzz-88888")
    assert floor > 0, "a falsy floor disables the filter it is supposed to apply"
    assert abs(floor - (_t.time() - hook._SIXTH_CAUSE_MAX_EDIT_AGE_S)) < 5.0

    # ancient edits drop (nothing distinctive -> indeterminate -> never blocks)
    assert hook._this_sessions_edits({"old.py": 1_000_000_000.0}, floor) == {}
    # and the fallback must not disarm the cause for work this session really did
    assert set(hook._this_sessions_edits({"mine.py": _t.time()}, floor)) == {"mine.py"}


def test_an_old_baseline_is_bounded_not_trusted(tmp_path, monkeypatch):
    """The headline line of the floor fix — `_sixth_cause_floor(baseline mtime)` — had NO grader:
    reverting it to the raw mtime left 379 tests green. The missing-baseline test below exercises
    only the `except OSError` arm; this one exercises the arm that actually fires, because
    `main()` keeps the ORIGINAL baseline across a resume BY DESIGN, so the 116-day transcript the
    docstring cites goes through the TRY branch with a real, ancient mtime."""
    import time as _t

    baseline = tmp_path / "fabrik-gate-baseline-oldsid.json"
    baseline.write_text("{}", encoding="utf-8")
    ancient = _t.time() - 116 * 86_400
    os.utime(baseline, (ancient, ancient))
    monkeypatch.setattr(hook, "_baseline_path", lambda sid: baseline)

    floor = hook._baseline_floor("oldsid")
    # the raw mtime would be 116 days old and filter nothing; the bound pulls it to the window
    assert floor > ancient + 86_400, "a 116-day baseline was trusted raw"
    assert floor == pytest.approx(_t.time() - hook._SIXTH_CAUSE_MAX_EDIT_AGE_S, abs=5)

    # and the consequence the bound exists for: an edit from 100 days ago is no longer "mine"
    assert hook._this_sessions_edits({"old.py": _t.time() - 100 * 86_400}, floor) == {}
    assert set(hook._this_sessions_edits({"mine.py": _t.time()}, floor)) == {"mine.py"}
