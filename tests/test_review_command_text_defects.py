"""/fabrik-review queue — the text defects (D-711: a verdict showing the command text WRONG is edited).

Each test asserts the corrected sentence, and where the sentence describes a tool, drives that tool to show the
behaviour the sentence now states (the old text promised more than the tool does).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "commands" / "_sources" / "fabrik-review.md"
FRAG = REPO / "commands" / "_fragments"


def _norm(p: Path) -> str:
    return " ".join(p.read_text(encoding="utf-8").split())


def test_the_closing_pass_confirms_defects_still_present_not_claims_executed_true() -> None:
    """Ledger claims state DEFECTS (STILL_TRUE = the defect persists), so 'every claim executed true' read as
    'every defect still there' (rows 1791354017, 1791146542)."""
    tc = _norm(FRAG / "term-coverage.md")
    assert ("in which those seats RE-EXECUTED every claim of their slice ledgers and CONFIRMED zero code or doc "
            "defects still present") in tc
    assert "executed true and zero code or doc defects" not in tc


def test_a_fix_touched_slice_with_no_candidate_is_added_by_hand(tmp_path: Path) -> None:
    """Row 1791235921: `next` builds slices only from the ids passed, so a slice whose file a fix edited but
    which raised nothing gets no ledger unless the lead adds it."""
    tc = _norm(FRAG / "term-coverage.md")
    assert ("a slice a fix hunk touched holds one even when it raised no candidate, and "
            "`review_loop_ledger.py next` builds slices only from the `--ids` passed, so add that slice's ledger "
            "by hand") in tc
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        import review_loop_ledger as rl
    finally:
        sys.path.pop(0)
    doc = {"candidates": [{"id": "A-1", "file": "a.py", "line": 3, "claim": "x"}]}
    assert [s["name"] for s in rl.next_ledger(doc, ["A-1"])] == ["A"], "slice B (fix-touched, no id) is absent"


def test_the_pre_pin_sweep_lists_the_pinned_literal_term_only(tmp_path: Path) -> None:
    """Rows 1790688796, 1790913510, 1791083066: `--claim` walks the --surface files for the literal term, so a
    mirror outside the pin or reworded is not listed — the text now says so and orders the repo grep."""
    tc = _norm(FRAG / "term-coverage.md")
    assert ("lists every line of the pinned surface where a rewritten claim's literal term occurs (case- and "
            "wrap-tolerant); a mirror outside the pin or in other words is not in that list, so also grep the repo "
            "for the term and two rewordings of the claim") in tc
    (tmp_path / "in.md").write_text("alpha\nthe stop key fires here\n", encoding="utf-8")
    (tmp_path / "out.md").write_text("the stop key fires too\n", encoding="utf-8")
    (tmp_path / "re.md").write_text("the halt key triggers\n", encoding="utf-8")
    p = subprocess.run([sys.executable, str(REPO / "scripts" / "enforcement" / "check_review_hygiene.py"),
                        "--surface", "in.md", "--surface", "re.md", "--claim", "stop key"],
                       cwd=tmp_path, capture_output=True, text=True, check=False)
    assert "in.md:2" in p.stdout, p.stdout
    assert "out.md" not in p.stdout and "re.md:" not in p.stdout, p.stdout


def test_a_trimmed_round_one_sweeps_its_unread_slices_before_any_delta_pass() -> None:
    """Row 1790926480: round 1 is the only full pass, so unread slices were never 'next round' work."""
    sc = _norm(FRAG / "subagents-core.md")
    assert ("the receipt names the unread slices, and a further full-pass wave over those slices alone runs before "
            "any delta pass, since round 1 is not complete until every slice is read.") in sc
    assert "re-sweeps them next round" not in sc


def test_recorded_measured_carries_a_routed_out_of_round_defect() -> None:
    """Row 1790952423: receipts file a real out-of-hop or post-stop defect as RECORDED — measured, which the old
    definition ('making no code or doc claim') forbade."""
    t = _norm(SRC)
    assert ("executed and shown TRUE but not a defect this round fixes: a prevalence figure, or a real defect "
            "outside the round's bounded hop or past the scope-growth stop, its named destination in the reason "
            "(`term-coverage` D4).") in t


def test_the_decision_row_lands_after_the_code_with_its_id_reserved_in_that_shell() -> None:
    """Rows 1790187513, 1790232519: close-chain commits code first and the ledgers through the private index."""
    t = _norm(SRC)
    assert ("mint its `docs/DECISIONS.md` row in the same change as the fix, classified at mint, its id reserved "
            "(`decisions.py --reserve-id`) in the shell that commits the row after the code (the close's "
            "private-index step)") in t
    assert "staged in the fix commit" not in t


def test_a_sync_or_revendor_commit_is_reviewed_as_an_adoption_never_reverted() -> None:
    """Row 1790455114: on a re-vendor diff every synced file is in the diff by design."""
    t = _norm(SRC)
    assert ("The exception is a sync or re-vendor commit, whose synced files ARE the intended change: review it as "
            "an adoption — the repo's own code, hooks and in-flight records still pair with the new copies — and "
            "never revert it.") in t


def test_the_gate_scope_sentence_names_what_the_static_checks_read() -> None:
    """Row 1790907152: get_changed_files scopes the static checks to unpushed commits plus the working tree."""
    t = _norm(SRC)
    assert ("`final_gate` takes no surface argument — its static checks read only what this session will push "
            "(unpushed commits plus the working tree, so code pushed before the review is never linted: run those "
            "checks on its paths by hand) and its repo checks read the whole tree") in t
    gate = (REPO / "scripts" / "final_gate.py").read_text(encoding="utf-8")
    assert 'f"{base}...HEAD"' in gate and '"--cached"' in gate, "the scoping the sentence describes"
