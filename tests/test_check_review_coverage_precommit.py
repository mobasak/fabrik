"""The commit-moment path of check_review_coverage (explicit staged paths).

Found live 2026-08-30: a phase review failing FOUR blocking rules was committed ungated —
the blocking path only scans `git status`, so a review committed without a gate run while
dirty escapes it forever (the advisory sweep checks a narrower class set and never saw it).
The class fix is a pre-commit hook that passes the STAGED review paths to the checker; this
tests the checker side: positional paths are graded with the full blocking battery and a
failing artifact exits non-zero at the moment it tries to enter history.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "enforcement" / "check_review_coverage.py"

_BAD_REVIEW = (
    "# R\n**Status:** CONVERGED\n**Surface:** abc\n\n"
    "Rubric: ran `python scripts/review_rubric.py --changed x.py` this pass.\n\n"
    "## Coverage Checklist\n\n| # | Class | Verdict | Evidence |\n|---|---|---|---|\n"
    "| 1 | fail-open/fail-closed | CLEAN | hunted x.py guards |\n"
    "| 2 | cost/quota accounting | CLEAN | limits in x.py:3 |\n"
    "| 3 | boundary/sentinel/prefix | CLEAN | prefixes in x.py:9 |\n"
    "| 4 | behavior-without-a-test | CLEAN | tests/test_x.py |\n\n"
    "## Pass Ledger\n\n"
    "- Pass 1 (WIDE) — method: citation — found: 1, fixed: 1\n"
    "- Pass 2 (CLOSING) — method: citation — found: 0, fixed: 0\n"
)

_GOOD_TAIL = "- Pass 2 (CLOSING) — method: re-derivation — found: 0, fixed: 0\n"


def _run_on(tmp_path: Path, text: str) -> subprocess.CompletedProcess:
    f = tmp_path / "2026-08-30-x-review.md"
    f.write_text(text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(f)],
        cwd=REPO, capture_output=True, text=True, timeout=120,
    )


def test_explicit_path_grades_with_the_full_blocking_battery(tmp_path):
    r = _run_on(tmp_path, _BAD_REVIEW)
    assert r.returncode == 1, f"rc={r.returncode} out={r.stdout!r} err={r.stderr!r}"
    assert "re-deriv" in r.stdout, r.stdout


def test_explicit_path_passes_a_clean_artifact(tmp_path):
    good = _BAD_REVIEW.replace(
        "- Pass 2 (CLOSING) — method: citation — found: 0, fixed: 0\n", _GOOD_TAIL
    )
    r = _run_on(tmp_path, good)
    assert r.returncode == 0, f"rc={r.returncode} out={r.stdout!r} err={r.stderr!r}"
