"""The review grader must accept the exit condition the review CONTRACT states — D-048 form.

Contract history, both turns load-bearing. 2026-08-27 (transdoc): the exit demanded `found: 0`
COUNTING re-raises of standing rows, making termination unreachable — the exit was re-keyed on
`new: 0`, and this file then pinned a `new:`-preferring advisory. 2026-08-31 (D-048): re-raises of
already-adjudicated standing rows are CITED in their disposition rows, never counted — `found:`
counts only candidates NEEDING adjudication, so the honest converged round reads `found: 0` again
and the BLOCKING reader (`check_file`, which grades `founds[-1]` only) is correct. The
`new:`-preference this file used to assert had become the divergence: the same `found: 3 | new: 0`
report was refused uncommitted and accepted once committed — `_committed_nonquiet`'s own founding
enemy. Both readers now grade the same `found:` counter; these tests pin that alignment.

`_ledger_shapes` is deliberately NOT touched: its docstring records three parallel ledger readers
each hardened separately until the stall breaker named the triple implementation as the foundation
error.
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


def test_a_nonzero_found_final_fires_even_with_new_zero_matching_the_blocking_reader(tmp_path):
    """D-048: re-raises are cited, never counted, so a final `found: 3` means three candidates
    still NEED adjudication — non-quiet to BOTH readers. Under the pre-D-048 `new:`-preference
    this exact report was refused uncommitted and accepted committed (the divergence)."""
    root = _repo(tmp_path, "| Pass 1 | finders | found: 3 | new: 0 | fixed: 0 |\n")
    out = crc._committed_nonquiet(root, set())
    assert out and "non-quiet" in out[0], out



def test_a_row_with_fresh_candidates_is_still_rejected(tmp_path):
    """The gate must not go soft: `new: 3` means the loop is still learning."""
    root = _repo(tmp_path, "| Pass 1 | finders | found: 3 | new: 3 | fixed: 0 |\n")
    out = crc._committed_nonquiet(root, set())
    assert out and "non-quiet" in out[0], out


def test_a_row_with_no_new_counter_grades_on_found(tmp_path):
    """`found:` grading is unconditional post-D-048 (no `new:` fallback exists any more) — legacy
    reports carrying only `found:`/`fixed:` grade exactly as they always did."""
    root = _repo(tmp_path, "| Pass 1 | finders | found: 2 | fixed: 0 |\n")
    out = crc._committed_nonquiet(root, set())
    assert out and "non-quiet" in out[0], out


def test_a_legacy_quiet_row_still_passes(tmp_path):
    root = _repo(tmp_path, "| Pass 1 | finders | found: 0 | fixed: 0 |\n")
    assert crc._committed_nonquiet(root, set()) == []


def test_check_file_blocks_the_same_nonquiet_report_the_advisory_flags(tmp_path):
    """THE alignment guard: both readers must grade the same counter. A `found: 3 | new: 0` final
    row is non-quiet to the committed advisory AND to the blocking reader — a future edit that
    re-diverges either one reds this test."""
    root = _repo(tmp_path, "| Pass 1 | finders | found: 3 | new: 0 | fixed: 0 |\n")
    advisory = crc._committed_nonquiet(root, set())
    assert advisory and "non-quiet" in advisory[0], advisory
    report = root / "docs" / "development" / "reviews" / "2026-08-27-x-review.md"
    blocking = crc.check_file(report)
    assert any("final ledger round raised 3" in e for e in blocking), blocking


def test_the_last_row_decides_not_an_earlier_quiet_one(tmp_path):
    root = _repo(
        tmp_path,
        "| Pass 1 | f | found: 0 | new: 0 | fixed: 0 |\n"
        "| Pass 2 | f | found: 5 | new: 5 | fixed: 1 |\n",
    )
    out = crc._committed_nonquiet(root, set())
    assert out and "non-quiet" in out[0], out
