"""The review grader must accept the exit condition the review CONTRACT states.

Found by `/fabrik-review` on this session's own work, and it is the session's own defect reproduced
one layer out. transdoc filed (2026-08-27) that `/fabrik-user-test` could not terminate: the exit
demanded `found: 0` counting refuted candidates, while a standing DESIGN-GAP row is re-raised by
every future finder round for as long as it is true. The fix keyed the exit on `new: 0` in the
SHARED `term-coverage` fragment — five commands at once.

`check_review_coverage._committed_nonquiet` was left demanding `int(rows[-1]) != 0` on `found:`.
So the grader rejected the exact state the contract now calls converged: a final row reading
`found: 3, new: 0` is CONVERGED by the fragment and "a non-quiet exit round" to the gate. Two
clauses judging one state oppositely — the very defect the fix was for.

`_ledger_shapes` is deliberately NOT touched: its docstring records three parallel ledger readers
each hardened separately until the stall breaker named the triple implementation as the foundation
error. It already returns the raw LINE, so `new:` is read off that without disturbing extraction.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "crc", REPO / "scripts" / "enforcement" / "check_review_coverage.py"
)
assert _spec and _spec.loader
crc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crc)

# The non-mega branch only inspects a report that HAS a Coverage Checklist — without one the
# report is skipped and every assertion below would pass vacuously against an empty list.
HEAD = (
    "# Review\n\nStatus: CLOSED\n\n**Surface:** `HEAD abc` · diff md5 `x`\n\n"
    "## Coverage Checklist\n\n| # | Class | Verdict | Evidence |\n|---|---|---|---|\n"
    "| 1 | fail-open | CLEAN | probed |\n\n## Pass Ledger\n\n"
)


def _repo(tmp: Path, ledger: str) -> Path:
    """A committed report — the grader only polices reports that are already committed."""
    subprocess.run(["git", "init", "-q", str(tmp)], check=True)
    d = tmp / "docs" / "development" / "reviews"
    d.mkdir(parents=True)
    (d / "2026-08-27-x-review.md").write_text(HEAD + ledger, encoding="utf-8")
    for args in (["add", "-A"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "r"]):
        subprocess.run(["git", "-C", str(tmp), *args], check=True)
    return tmp


def test_a_row_with_new_zero_is_a_valid_exit_even_when_found_is_nonzero(tmp_path):
    """THE contract's exit: re-raised already-adjudicated candidates keep `found` above 0 forever,
    and `new: 0` is what says the loop stopped learning."""
    root = _repo(tmp_path, "| Pass 1 | finders | found: 3 | new: 0 | fixed: 0 |\n")
    assert crc._committed_nonquiet(root, set()) == []


def test_a_row_with_fresh_candidates_is_still_rejected(tmp_path):
    """The gate must not go soft: `new: 3` means the loop is still learning."""
    root = _repo(tmp_path, "| Pass 1 | finders | found: 3 | new: 3 | fixed: 0 |\n")
    out = crc._committed_nonquiet(root, set())
    assert out and "non-quiet" in out[0], out


def test_a_row_with_no_new_counter_falls_back_to_found(tmp_path):
    """Backward compatible: every report written before the contract change carries only `found:`,
    and those must keep grading exactly as they did — a silent re-grade of history is not a fix."""
    root = _repo(tmp_path, "| Pass 1 | finders | found: 2 | fixed: 0 |\n")
    out = crc._committed_nonquiet(root, set())
    assert out and "non-quiet" in out[0], out


def test_a_legacy_quiet_row_still_passes(tmp_path):
    root = _repo(tmp_path, "| Pass 1 | finders | found: 0 | fixed: 0 |\n")
    assert crc._committed_nonquiet(root, set()) == []


def test_new_is_token_anchored_so_a_decoy_cannot_forge_the_exit(tmp_path):
    """Same discipline the `found:`/`fixed:` tokens already carry: a narrative phrase must not be
    mistaken for the counter. `renewed: 0` is not `new: 0`."""
    root = _repo(tmp_path, "| Pass 1 | finders | found: 4 | renewed: 0 | fixed: 0 |\n")
    out = crc._committed_nonquiet(root, set())
    assert out and "non-quiet" in out[0], "a `renewed:` decoy must not satisfy the exit"


def test_the_last_row_decides_not_an_earlier_quiet_one(tmp_path):
    root = _repo(
        tmp_path,
        "| Pass 1 | f | found: 0 | new: 0 | fixed: 0 |\n"
        "| Pass 2 | f | found: 5 | new: 5 | fixed: 1 |\n",
    )
    out = crc._committed_nonquiet(root, set())
    assert out and "non-quiet" in out[0], out
