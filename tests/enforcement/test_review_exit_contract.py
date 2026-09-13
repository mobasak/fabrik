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
    for args in (
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "r"],
    ):
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


def test_both_readers_agree_on_the_confirmed_grammar_too(tmp_path):
    """The same alignment, on D7's V1 row (D-206). The divergence this file exists to prevent is
    per-reader hardening, so the NEW grammar is proven on both readers the day it lands: a row
    that is quiet by `confirmed: 0` although `found:` is 4 must be quiet to BOTH, and the same
    row with a confirmed defect must be non-quiet to BOTH."""
    quiet = "| Pass 19 | opus×1 | found: 4, new: 2, confirmed: 0, fixed: 0, unexecuted: 0 | d |\n"
    root = _repo(tmp_path, quiet)
    report = root / "docs" / "development" / "reviews" / "2026-08-27-x-review.md"
    assert crc._committed_nonquiet(root, set()) == []
    assert not [e for e in crc.check_file(report) if "final ledger round" in e]

    loud = quiet.replace("confirmed: 0, fixed: 0", "confirmed: 1, fixed: 1")
    report.write_text(HEAD + loud, encoding="utf-8")
    advisory = crc._committed_nonquiet(root, set())
    assert advisory and "confirmed: 1" in advisory[0], advisory
    blocking = [e for e in crc.check_file(report) if "final ledger round" in e]
    assert blocking and "confirmed: 1" in blocking[0], blocking


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
        (
            ln
            for ln in te.splitlines()
            if "method:" in ln and "re-deriv" in ln and ln.startswith("| Pass")
        ),
        None,
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
    # round-2 tightenings: a one-token slug never fuzzy-matches (supersets into
    # unrelated reviews), and undated names fall back to exact-stem only (an
    # undated side made the date guard a no-op).
    assert not ccv._cite_matches_plan("2026-01-05-mail-fixes-review.md", "2026-01-01-plan-2-mail")
    # an UNDATED plan stem cannot use the fuzzy path (its date guard would be a
    # no-op) — only the exact-substring rule remains available to it
    assert not ccv._cite_matches_plan("2026-01-01-cleanup-phase5-review.md", "phase5-cleanup")
    assert not ccv._cite_matches_plan("tryton-crm-deploy-review.md", plan)


def test_both_fragments_carry_the_bounded_hop_the_delta_budget_and_the_round_zero_rules():
    """Review-family pass 3 (D-229, D-230, D-231): D4's counting sentence, D5's budget — the ONE
    number, bound to `dispatch_headroom.DELTA_BUDGET` by this test — and D10's three rule phrases
    live in BOTH termination fragments; `term-coverage` reads the `confirmed:` exit row and carries
    no retired `found: 0 · new: 0 · fixed: 0` literal (D2)."""
    _dh_spec = importlib.util.spec_from_file_location(
        "dh", REPO / "scripts" / "sysadmin" / "dispatch_headroom.py"
    )
    assert _dh_spec and _dh_spec.loader
    dh = importlib.util.module_from_spec(_dh_spec)
    _dh_spec.loader.exec_module(dh)
    frag = REPO / "commands" / "_fragments"
    te = (frag / "term-edit.md").read_text(encoding="utf-8")
    tc = (frag / "term-coverage.md").read_text(encoding="utf-8")
    for name, text in (("term-edit", te), ("term-coverage", tc)):
        assert "INSIDE the previous round's fix hunks" in text, name  # D4
        assert f"at or under {dh.DELTA_BUDGET} changed lines" in text, name  # D5
        for phrase in ("probe script", "--claim", "class rewrite"):  # D10 (1)–(3)
            assert phrase in text, (name, phrase)
    assert "confirmed: 0 · fixed: 0 · unexecuted: 0" in tc
    assert "found: 0 · new: 0 · fixed: 0" not in tc
    # the canonical row template the fragment ships PARSES through both graders in the stated
    # order (round-1 finding: the prose said "`found:` before `fixed:`", and a row honouring only
    # that — `confirmed:` after `fixed:` — is refused by `_pass_counters_ext` and misses QUIET_PASS)
    import re as _re

    tmpl = next(
        s for s in _re.findall(r"`([^`\n]*)`", tc) if "method: citation|re-derivation|gate" in s
    )
    row = tmpl.replace("citation|re-derivation|gate", "re-derivation").replace("Pass k", "Pass 2")
    assert isinstance(crc._pass_counters_ext(row), tuple), crc._pass_counters_ext(row)
    _cc = importlib.util.spec_from_file_location(
        "ccv2", REPO / "scripts" / "enforcement" / "check_convergence.py"
    )
    ccv2 = importlib.util.module_from_spec(_cc)
    _cc.loader.exec_module(ccv2)
    assert ccv2.QUIET_PASS.search(row), row
    displaced = row.replace("confirmed: 0, fixed: 0", "fixed: 0, confirmed: 0")
    assert isinstance(crc._pass_counters_ext(displaced), str)  # refused by name, as the text says


_MAIL_TRIAGE_FRAGMENT_SENTENCES = {
    # mail-triage plan Phase A (T2.4, T2.6, T2.8, T2.14, T2.20): the fragments' new rules
    "commands/_fragments/term-coverage.md": (
        "under an explicit `timeout` at or above its own measured runtime",  # T2.4 (01M25Y93M)
        "Scope-growth stop",  # T2.6 (01M2AJG97)
        "the previous seat's REFUTED list verbatim",  # T2.8 — in BOTH termination fragments
    ),
    "commands/_fragments/term-edit.md": (
        "Scope-growth stop",  # T2.6
        "the previous seat's REFUTED list verbatim",  # T2.8 — in BOTH termination fragments
        "verify the check CAN fail",  # T2.14 (01M1SNGE4)
        "taken BEFORE the ledger row is written",  # T4.14 (01M1RFN3)
    ),
    "commands/_fragments/subagents-core.md": (
        "pins a commit SHA beside them",  # T2.20 (01M206NBV)
    ),
}


def test_the_mail_triage_fragment_sentences_are_present_once_at_their_source():
    """One sentence per mailed rule, in the fragment that every consumer includes; a fragment
    that drops or doubles it changes every review loop at the next render."""
    repo = Path(__file__).resolve().parents[2]
    bad = []
    for rel, needles in _MAIL_TRIAGE_FRAGMENT_SENTENCES.items():
        text = (repo / rel).read_text(encoding="utf-8")
        for needle in needles:
            if text.count(needle) != 1:
                bad.append((rel, needle, text.count(needle)))
    assert not bad, bad


def test_command_run_mirrors_the_delta_budget_of_dispatch_headroom() -> None:
    """Review round 1 (Phase B): `command_run.DELTA_BUDGET` says it mirrors dispatch_headroom's
    but nothing bound the two — the oscillation suppression would diverge from the seat budget
    silently."""
    mods = {}
    for name, rel in (
        ("dh_mirror", "scripts/sysadmin/dispatch_headroom.py"),
        ("cr_mirror", "scripts/command_run.py"),
    ):
        spec = importlib.util.spec_from_file_location(name, REPO / rel)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mods[name] = mod
    assert mods["cr_mirror"].DELTA_BUDGET == mods["dh_mirror"].DELTA_BUDGET == 20
