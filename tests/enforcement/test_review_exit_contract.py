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


def test_a_report_written_to_the_fragments_own_spec_passes_check_file(tmp_path):
    """The corpus-vs-grader fixture guard (promoted 2026-08-31 after its backlog trigger fired
    twice: the two-token QUIET sentence, then the missing re-derivation mandate). A report built
    exactly to term-coverage's termination contract must satisfy the blocking reader — a spec the
    gate refuses is a corpus defect, and this test is where that class now reds first."""
    report = (
        "# Review\n\nStatus: CLOSED\n\n**Surface:** `HEAD abc` · diff md5 `x`\n\n"
        "Rubric: `python scripts/review_rubric.py --changed a.py` (output fenced below)\n\n"
        "```\n# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)\nrubric body\n```\n\n"
        "## Coverage Checklist\n\n| # | Class | Verdict | Evidence |\n|---|---|---|---|\n"
        "| 1 | fail-open vs fail-closed | CLEAN | probed a.py guards + callers |\n"
        "| 2 | cost/quota accounting | CLEAN | hunted a.py cost paths |\n"
        "| 3 | boundary/sentinel/prefix | CLEAN | hunted a.py parsers |\n"
        "| 4 | behavior-without-a-test | CLEAN | hunted tests/test_a.py + a.py handlers |\n\n"
        "## Pass Ledger\n\n"
        # the CANONICAL row shape term-coverage.md pins verbatim: method FIRST, counters adjacent,
        # finders after — D-053: the graders bind same-line only; no char windows remain
        "| Pass 1 | method: citation | found: 3 | new: 3 | fixed: 3 | finders: pool-a, native-opus |\n"
        "| Pass 2 | method: re-derivation | found: 0 | new: 0 | fixed: 0 | finders: native-opus (non-author) |\n"
    )
    d = tmp_path / "docs" / "development" / "reviews"
    d.mkdir(parents=True)
    p = d / "2026-08-31-fixture-review.md"
    p.write_text(report, encoding="utf-8")
    errs = crc.check_file(p)
    assert errs == [], errs
    # red direction: strip the method cells — the re-derivation gate must refuse the same report
    stripped = report.replace("| method: citation ", "").replace("| method: re-derivation ", "")
    p.write_text(stripped, encoding="utf-8")
    errs2 = crc.check_file(p)
    assert any("re-derivation" in e for e in errs2), errs2


def test_d053_window_caps_removed_ordering_no_longer_load_bearing(tmp_path):
    """D-053 re-grounding: the 40-char QUIET_PASS and 160-char _REDERIVATION_ROW windows made
    cell ORDERING load-bearing — a compliant row with a long finder manifest before the method
    cell (measured 179-char gap) was reported absent. Same-line is the constraint; the gap is not."""
    import importlib.util as ilu

    spec2 = ilu.spec_from_file_location(
        "ccv", REPO / "scripts" / "enforcement" / "check_convergence.py"
    )
    assert spec2 and spec2.loader
    ccv = ilu.module_from_spec(spec2)
    spec2.loader.exec_module(ccv)

    long_manifest_row = (
        "| Pass 2 | found: 0 | new: 0 | fixed: 0 | finders: pool-deepseek-v3.2-exp, "
        "pool-gemini-3-flash-preview, pool-qwen3-max, native-fabrik-reviewer-opus (non-author), "
        "dispatched: 5, returned: 4, partitions re-covered: 1 | method: re-derivation |"
    )
    gap = long_manifest_row.index("re-derivation") - long_manifest_row.index("Pass")
    assert gap > 160, f"fixture must exceed the old cap to discriminate (gap={gap})"
    assert ccv._REDERIVATION_ROW.search(long_manifest_row), "179-char gap must match post-D-053"
    assert crc._REDERIVATION_ROW.search(long_manifest_row), "lockstep twin must agree"
    wide_quiet_row = (
        "| Pass 3 | found: 0 | new: 0 | interim-notes: sixty more characters of cell content "
        "sit between the two counters here | fixed: 0 |"
    )
    assert ccv.QUIET_PASS.search(wide_quiet_row), "same-line quiet pair must match at any gap"


def test_d053_amendment_anchors_on_the_method_cell_not_prose():
    """Round-14/15 guard: the first uncapped regex matched bare prose and lost the hard block;
    the amendment anchors on the METHOD CELL. Both directions + twin identity + the two
    fragments' own example rows (the dual-specification class: a fragment's shipped example
    must satisfy the grader that its own prose invokes)."""
    import importlib.util as ilu

    spec2 = ilu.spec_from_file_location(
        "ccv3", REPO / "scripts" / "enforcement" / "check_convergence.py"
    )
    assert spec2 and spec2.loader
    ccv = ilu.module_from_spec(spec2)
    spec2.loader.exec_module(ccv)

    for prose in (
        "| Pass 1 | 1 native verifier: 4 candidates adjudicated + 9 anchors re-derived (all landed) | 3 | 3 | 3 |",
        "Round 2: 9 anchors re-derived from primary source",
    ):
        assert not crc._REDERIVATION_ROW.search(prose), prose
        assert not ccv._REDERIVATION_ROW.search(prose), prose
    for good in (
        "| Pass 2 | method: re-derivation | found: 0 | new: 0 | fixed: 0 | finders: x |",
        "| Round 3 | **method:** re-derivation | found: 0 | new: 0 | fixed: 0 |",
        "Pass 3 — method: re-derivation | found: 0 | new: 0 | fixed: 0 | finders: y",
    ):
        assert crc._REDERIVATION_ROW.search(good), good
        assert ccv._REDERIVATION_ROW.search(good), good
    assert crc._REDERIVATION_ROW.pattern == ccv._REDERIVATION_ROW.pattern
    assert crc._REDERIVATION_ROW.flags == ccv._REDERIVATION_ROW.flags
    # the two fragments' SHIPPED example rows must satisfy the grader their prose invokes
    frag = REPO / "commands" / "_fragments"
    te = (frag / "term-edit.md").read_text(encoding="utf-8")
    tc = (frag / "term-coverage.md").read_text(encoding="utf-8")
    te_row = next(
        (ln for ln in te.splitlines()
         if "method:" in ln and "re-deriv" in ln and ln.startswith("| Pass")), None
    )
    assert te_row is not None, "term-edit's shipped example re-derivation row not found"
    assert crc._REDERIVATION_ROW.search(te_row), te_row
    import re as _re

    tc_row = next(
        (s for s in _re.findall(r"`([^`\n]*)`", tc) if "method: citation|re-derivation|gate" in s),
        None,
    )
    assert tc_row is not None, "term-coverage's canonical row template not found"
    literal = tc_row.replace("citation|re-derivation|gate", "re-derivation")
    assert crc._REDERIVATION_ROW.search(literal), literal
    assert ccv._REDERIVATION_ROW.search(literal), literal


def test_01m1djyh_verify_review_named_by_service_satisfies_the_flip():
    """01M1DJYH: a deploy plan's verify review is named by service+verify-date, not plan
    stem — the stem-substring discriminator blocked a legitimate EXECUTED flip and the only
    workarounds were fabricating a round or deleting a true citation. Token-subset + the
    not-older-than-the-plan date guard admit the plan's own validation while still refusing
    the 3-week-old readiness review (same tokens, older date) and unrelated reviews."""
    import importlib.util as ilu

    spec = ilu.spec_from_file_location(
        "ccv_cite", REPO / "scripts" / "enforcement" / "check_convergence.py"
    )
    assert spec and spec.loader
    ccv = ilu.module_from_spec(spec)
    spec.loader.exec_module(ccv)

    plan = "2026-08-31-plan-deploy-tryton-crm"
    # the live pair from the finding, verbatim
    assert ccv._cite_matches_plan("2026-09-01-tryton-crm-deploy-verify-review.md", plan)
    assert not ccv._cite_matches_plan("2026-08-10-tryton-crm-deploy-readiness-review.md", plan)
    # the original rule survives (retro-safety: every archived EXECUTED plan stem-matches)
    assert ccv._cite_matches_plan(f"{plan}-review.md", plan)
    # an unrelated quiet review must never certify this plan (accidental-satisfaction guard)
    assert not ccv._cite_matches_plan("2026-09-01-mail-fixes-review.md", plan)
    # same-day validation is legitimate (>=, not >)
    assert ccv._cite_matches_plan("2026-08-31-deploy-tryton-crm-review.md", plan)
