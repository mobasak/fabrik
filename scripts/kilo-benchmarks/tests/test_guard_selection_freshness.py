# AFTER-EDIT: ../guard_selection_freshness.py
"""Freshness guard tests — the load-bearing behavior is REFUSING a doc that goes backwards.

Real-DB/real-git policy: these drive an actual throwaway git repo, not a mocked `git show`.
A substring assertion on the helper's SQL/CLI would stay green if the comparison inverted;
running it against real commits cannot be fooled.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent))

from guard_selection_freshness import (  # noqa: E402
    head_text,
    is_regression,
    refresh_date,
)

DOC = "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"


def _repo(tmp_path: Path, committed: str, worktree: str | None) -> Path:
    r = tmp_path / "r"
    (r / "docs/reference/kilo").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(r), "config", "user.name", "t"], check=True)
    (r / DOC).write_text(committed, encoding="utf-8")
    subprocess.run(["git", "-C", str(r), "add", DOC], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-qm", "base"], check=True)
    if worktree is not None:
        (r / DOC).write_text(worktree, encoding="utf-8")
    return r


def _doc(date: str, body: str = "spec n=6") -> str:
    return f"Last refresh: {date}\nFormula: …\n\n### spec\n{body}\n"


def test_older_worktree_doc_is_a_regression(tmp_path):
    """THE incident: the auto-commit landed a 2026-08-19 doc over a 2026-08-29 one, reverting a
    fixed aggregation for four days under a message claiming 'regenerated'."""
    r = _repo(tmp_path, committed=_doc("2026-08-29"), worktree=_doc("2026-08-19", "spec n=155"))
    regressed, why = is_regression(DOC, repo=r)
    assert regressed, "an older worktree doc MUST be refused"
    assert "2026-08-19" in why and "2026-08-29" in why


def test_newer_worktree_doc_is_allowed(tmp_path):
    r = _repo(tmp_path, committed=_doc("2026-08-19"), worktree=_doc("2026-08-29"))
    assert is_regression(DOC, repo=r)[0] is False


def test_same_date_is_allowed(tmp_path):
    """A same-day re-run legitimately rewrites content without bumping the date."""
    r = _repo(tmp_path, committed=_doc("2026-08-29", "a"), worktree=_doc("2026-08-29", "b"))
    assert is_regression(DOC, repo=r)[0] is False


def test_fail_open_when_either_side_has_no_refresh_line(tmp_path):
    """Most pipeline outputs carry no date — the guard must not block them."""
    r = _repo(tmp_path, committed="no date here\n", worktree=_doc("2026-08-19"))
    assert is_regression(DOC, repo=r)[0] is False
    r2 = _repo(tmp_path / "b", committed=_doc("2026-08-29"), worktree="no date here\n")
    assert is_regression(DOC, repo=r2)[0] is False


def test_fail_open_for_a_new_untracked_doc(tmp_path):
    """The doc must EXIST on disk or this never reaches the `committed is None` branch it names —
    it returns at the OSError guard instead, and a mutation of the new-file branch survives
    (review 2026-09-02, finding 7: proven by mutating each branch separately)."""
    r = _repo(tmp_path, committed=_doc("2026-08-29"), worktree=None)
    new_doc = "docs/reference/kilo/BRAND_NEW.md"
    (r / new_doc).write_text(_doc("2020-01-01"), encoding="utf-8")  # dated, ANCIENT, but untracked
    assert (r / new_doc).exists(), "precondition: the new-file branch needs a readable file"
    assert is_regression(new_doc, repo=r)[0] is False, "a doc absent from HEAD cannot be a rewind"


def test_fail_open_when_the_worktree_file_is_unreadable(tmp_path):
    """The OSError branch, tested for itself rather than by accident."""
    r = _repo(tmp_path, committed=_doc("2026-08-29"), worktree=None)
    assert is_regression("docs/reference/kilo/DOES_NOT_EXIST.md", repo=r)[0] is False


def test_fail_open_when_git_itself_fails(tmp_path):
    """`head_text` swallows any git error → KEEP. Untested before; two mutants survived
    (review 2026-09-02, finding 8). Point it at a directory that is not a git repo."""
    not_a_repo = tmp_path / "plain"
    (not_a_repo / "docs/reference/kilo").mkdir(parents=True)
    (not_a_repo / DOC).write_text(_doc("2020-01-01"), encoding="utf-8")
    assert head_text(DOC, repo=not_a_repo) is None
    assert is_regression(DOC, repo=not_a_repo)[0] is False


def test_refresh_date_returns_a_real_date_and_ignores_non_headers():
    """Returns a `date`, not a string — string compare accepted `2026-13-45` (finding 12).
    A commented-out or prose mention is still not a header."""
    assert refresh_date("Last refresh: 2026-08-29\n") == datetime.date(2026, 8, 29)
    assert refresh_date("# Last refresh: 2026-08-29 (stale)\n") is None
    assert refresh_date("Last refresh: not-a-date\n") is None
    assert refresh_date("") is None


def test_cli_prints_survivors_and_drops_the_regression(tmp_path):
    """End-to-end through the real CLI: the shell consumes STDOUT as its stage list, so a dropped
    path must be absent there and explained on STDERR."""
    r = _repo(tmp_path, committed=_doc("2026-08-29"), worktree=_doc("2026-08-19"))
    other = "docs/reference/kilo/OTHER.md"
    (r / other).write_text("no date\n", encoding="utf-8")
    env = dict(os.environ, GUARD_REPO=str(r))
    p = subprocess.run(
        [sys.executable, str(TESTS_DIR.parent / "guard_selection_freshness.py"), DOC, other],
        capture_output=True, text=True, env=env,
    )
    assert p.returncode == 0
    staged = p.stdout.split()
    assert DOC not in staged, "the regressing doc must NOT reach the stage list"
    assert other in staged, "an undated pipeline output must still be committed"
    assert "DROP" in p.stderr and "2026-08-19" in p.stderr


def test_trailing_text_after_the_date_still_parses(tmp_path):
    r"""Finding 6: the old `\s*$` anchor meant ANY trailing text silently switched the guard off,
    diverging from the sibling checker (check_daily_refresh_freshness.py:63). Mutant M3 survived."""
    assert refresh_date("Last refresh: 2026-08-29 (stale)\n") == datetime.date(2026, 8, 29)
    assert refresh_date("Last refresh: 2026-08-29  n=1092\n") == datetime.date(2026, 8, 29)


def test_all_three_generator_header_shapes_are_recognised():
    """Finding 5: guarding only `Last refresh:` left the FLEET-SYNCED ai-render packs
    (`Last content verification:`) and CODING_SUBAGENT_SELECTION.md (`**Generated:**`) unguarded —
    the highest-blast-radius half of the stage list."""
    assert refresh_date("Last refresh: 2026-08-29\n") == datetime.date(2026, 8, 29)
    assert refresh_date("Last content verification: 2026-08-29\n") == datetime.date(2026, 8, 29)
    assert refresh_date("**Generated:** 2026-08-29 · **Source:** x\n") == datetime.date(2026, 8, 29)


def test_a_bom_does_not_blind_the_guard():
    """A UTF-8 BOM made the header unparseable → fail-open → a stale BOM'd doc sailed through."""
    assert refresh_date("\ufeffLast refresh: 2026-08-29\n") == datetime.date(2026, 8, 29)


def test_a_calendar_invalid_date_fails_open_rather_than_pinning_the_guard_shut():
    """Finding 12: `2026-13-45` is shape-valid and string-sorts above every real 2026 date, so a
    corrupted HEAD copy would have DROPPED every later regeneration forever."""
    assert refresh_date("Last refresh: 2026-13-45\n") is None


def test_a_one_generation_rewind_is_caught(tmp_path):
    """A 1-day tolerance was added, then WITHDRAWN by the closing review (finding 2): both dates
    come from the SAME generator, so there is no cross-convention skew to absorb — and because the
    generator runs DAILY, "one day behind" is the MOST likely rewind, not an edge case."""
    r = _repo(tmp_path, committed=_doc("2026-08-29"), worktree=_doc("2026-08-28"))
    assert is_regression(DOC, repo=r)[0] is True, "one generation behind IS a rewind"
    same = _repo(tmp_path / "c", committed=_doc("2026-08-29"), worktree=_doc("2026-08-29"))
    assert is_regression(DOC, repo=same)[0] is False, "same day is a legitimate re-run"
    newer = _repo(tmp_path / "d", committed=_doc("2026-08-29"), worktree=_doc("2026-08-30"))
    assert is_regression(DOC, repo=newer)[0] is False, "newer is the normal publish path"


def test_fail_open_when_subprocess_itself_raises(monkeypatch, tmp_path):
    """The `except Exception` in head_text guards a git invocation that never returns (timeout,
    missing binary). A non-git DIRECTORY does not reach it — git exits non-zero and the
    returncode check handles that — so this drives the raise directly (mutant M4 survived without
    it: `except Exception: raise` passed the whole suite)."""
    import guard_selection_freshness as g

    def boom(*a, **k):
        raise OSError("git vanished")

    # build the repo FIRST: `subprocess` is a module singleton, so patching its `run` also
    # breaks the fixture's own git calls if done in the other order
    r = _repo(tmp_path, committed=_doc("2026-08-29"), worktree=_doc("2020-01-01"))
    monkeypatch.setattr(g.subprocess, "run", boom)
    assert g.head_text(DOC, repo=r) is None
    assert g.is_regression(DOC, repo=r)[0] is False, "a git failure must KEEP, never drop"



def test_a_quoted_header_deeper_in_the_doc_cannot_be_read_as_the_real_one():
    """The dangerous direction: relaxing the trailing anchor widened what can match, and an
    unbounded search takes the FIRST hit — so a fenced/quoted example before the real header made
    the guard read an OLDER date and DROP a fresh doc. Bounded to the document head."""
    body = "\n".join(["filler"] * 40)
    doc = f"Last refresh: 2026-09-02\n{body}\n```\nLast refresh: 2020-01-01\n```\n"
    assert refresh_date(doc) == datetime.date(2026, 9, 2), "the real header wins"
    assert refresh_date(f"{body}\nLast refresh: 2020-01-01\n") is None, "past the head bound"


def test_the_head_bound_still_reaches_the_ai_pack_position():
    """The ai-render packs put `Last content verification:` on lines 14-16 — the bound must clear
    them or the FLEET-SYNCED half of the stage list silently loses its guard."""
    doc = "\n".join(["preamble"] * 15) + "\nLast content verification: 2026-08-29\n"
    assert refresh_date(doc) == datetime.date(2026, 8, 29)
