# AFTER-EDIT: ../guard_selection_freshness.py
"""Freshness guard tests — the load-bearing behavior is REFUSING a doc that goes backwards.

Real-DB/real-git policy: these drive an actual throwaway git repo, not a mocked `git show`.
A substring assertion on the helper's SQL/CLI would stay green if the comparison inverted;
running it against real commits cannot be fooled.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR.parent))

from guard_selection_freshness import (  # noqa: E402
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
    r = _repo(tmp_path, committed=_doc("2026-08-29"), worktree=None)
    assert is_regression("docs/reference/kilo/BRAND_NEW.md", repo=r)[0] is False


def test_refresh_date_parses_only_the_exact_line():
    assert refresh_date("Last refresh: 2026-08-29\n") == "2026-08-29"
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
