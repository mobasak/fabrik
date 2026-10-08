"""Tests for the D7 live-request requirement in fabrik-execute-plan.

This test verifies that D7 (Final validation + terminal states) requires at least one
live request/response against a running service, pasted into `## Evidence`, for any
plan whose tickets ship HTTP surface.

The test follows the watched-fail-first pattern:
1. First run: test is RED because the live-request requirement is missing
2. Edit D7 to add the requirement
3. Second run: test is GREEN because the requirement is present
"""

from __future__ import annotations

import re
from pathlib import Path

# Resolve from THIS file, never cwd: `pytest tests/...` from the repo root and
# `pytest test_execute_plan_d7.py` from inside tests/ must both work. A cwd-relative
# path made the second form die with FileNotFoundError (review finding, 2026-08-25).
_D7_SOURCE = (
    Path(__file__).resolve().parents[1] / "commands" / "_sources" / "fabrik-execute-plan.md"
)


def _d7_section(text: str) -> str:
    """Extract the D7 section from the execute-plan markdown text.

    The section starts at the D7 heading and ends at the next section header (### or ##)
    or the end of the file.
    """
    lines = text.split("\n")
    d7_start = None
    d7_end = None

    for i, line in enumerate(lines):
        if "### D7 — Final validation + terminal states" in line:
            d7_start = i
            # Find next section header (### or ##)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith("### ") or lines[j].startswith("## "):
                    d7_end = j
                    break
            break

    if d7_start is None:
        return ""

    if d7_end is None:
        d7_end = len(lines)

    return "\n".join(lines[d7_start:d7_end])


def _pins_live_request(section: str) -> bool:
    """Does this D7 section carry the live-request requirement AS A REQUIREMENT?

    Two conditions. The second is the one that matters, and it is deliberately a
    SINGLE ADJACENT PHRASE rather than a co-occurrence window.

    Two earlier predicates failed here, both by asking whether signals appeared
    NEAR each other (verified 2026-08-25):
      * "do 'live request' and '## Evidence' both appear?" -> True on a section
        gutted to "is fine on green suites alone; a live request is nice to have".
      * "do they appear in the same SENTENCE?" -> also True on that text, because
        the clause ends `LIVE REQUEST.**` (markdown bold, no space after the stop),
        so sentence-splitting ran on and borrowed "requires" from the next sentence.

    Presence near modality is not force. So the pin requires the modal verb and its
    object ADJACENT: `<normative verb> at least one live request`. Gutting the
    clause to optional necessarily breaks that phrase; no neighbouring sentence can
    lend it. The verb set is small and open by design — widen it deliberately when a
    reword genuinely needs it, which is the review conversation this pin exists to force.
    """
    if "## Evidence" not in section:
        return False
    return bool(
        re.search(
            r"\b(owes?|requires?|must\s+(?:include|carry|paste))\s+"
            r"(?:at\s+least\s+)?(?:one|1|>=\s*1|\u22651)\s+"
            r"(?:real\s+|genuine\s+)?live\s+request",
            section,
            re.IGNORECASE,
        )
    )


def test_d7_section_contains_live_request_requirement():
    """Assert that D7 names the live-request requirement.

    This is the primary pin test: it reads the actual D7 section from the
    execute-plan markdown and asserts it contains the live-request requirement.
    """
    content = _D7_SOURCE.read_text()

    d7 = _d7_section(content)

    # The section should not be empty
    assert d7, "D7 section should be extracted from the file"

    # The section should contain the live-request requirement
    assert _pins_live_request(d7), (
        "D7 section must contain the live-request requirement with 'live request' "
        "and '## Evidence' reference"
    )


def test_d7_pin_is_not_vacuous():
    """Assert that the pin actually detects the absence of the requirement.

    This test mutates the D7 section by removing the requirement sentence and
    verifies that the pin's predicate returns False. This proves the pin is real
    and not vacuously passing.

    The ticket's second Behavior-Contract row - it is not optional.
    """
    content = _D7_SOURCE.read_text()

    d7 = _d7_section(content)

    # Verify the requirement is present first (sanity check)
    assert _pins_live_request(d7), "Test setup: D7 should contain the requirement before mutation"

    # Mutate by removing the live-request requirement text
    # Find and remove sentences containing "live request" and "## Evidence"
    mutated = d7

    # Remove lines that contain both "live" and "request" (case-insensitive)
    # and lines that contain "## Evidence"
    lines = mutated.split("\n")
    filtered_lines = [
        line
        for line in lines
        if not (
            re.search(r"live", line, re.IGNORECASE) and re.search(r"request", line, re.IGNORECASE)
        )
        and "## Evidence" not in line
    ]
    mutated = "\n".join(filtered_lines)

    # The mutated section should NOT satisfy the requirement
    assert not _pins_live_request(mutated), (
        "Mutated D7 section (with requirement removed) should NOT satisfy the pin predicate"
    )


def test_pin_requires_the_live_request_phrase_independently():
    """Strip ONLY the live-request phrase; the pin must go False.

    test_d7_pin_is_not_vacuous strips BOTH signals in one mutation, so it cannot
    show WHICH signal the predicate depends on — a pin keyed solely on
    `## Evidence` would pass it unchanged. These two tests isolate each signal.
    (Review finding, 2026-08-25.)
    """
    section = _d7_section(_D7_SOURCE.read_text())
    assert _pins_live_request(section)
    stripped = re.sub(r"live\s+request", "", section, flags=re.IGNORECASE)
    assert not _pins_live_request(stripped), (
        "pin still passes with every 'live request' removed — it is not keyed on that phrase"
    )


def test_pin_requires_the_evidence_reference_independently():
    """Strip ONLY the `## Evidence` reference; the pin must go False."""
    section = _d7_section(_D7_SOURCE.read_text())
    assert _pins_live_request(section)
    stripped = section.replace("## Evidence", "the spine")
    assert not _pins_live_request(stripped), (
        "pin still passes with the '## Evidence' reference removed — it is not keyed on it"
    )


def test_pin_rejects_a_gutted_requirement():
    """The clause reworded from mandatory to OPTIONAL must fail the pin.

    Presence of the words is not the requirement; normative force is. An earlier
    predicate that only asked "do 'live request' and '## Evidence' both appear?"
    returned True for a section saying the opposite (Opus review finding,
    2026-08-25). This is the control the other mutation tests could not supply:
    they delete signals, this one INVERTS the meaning while leaving both in place.
    """
    section = _d7_section(_D7_SOURCE.read_text())
    assert _pins_live_request(section)
    gutted = section.replace(
        "does not reach a terminal state on green suites alone — it owes",
        "is fine on green suites alone; a live request is nice to have and",
    )
    assert "live request" in gutted and "## Evidence" in gutted, (
        "the gutted text must still contain BOTH signals — otherwise this test "
        "proves nothing beyond the deletion tests"
    )
    assert not _pins_live_request(gutted), (
        "pin accepts an OPTIONAL live request — it checks presence, not force"
    )


def test_the_whole_plan_receipt_is_named_by_the_plan_stem_so_check_convergence_matches_it():
    """/fabrik-execute-plan queue: Finish rediscovered how to name and close the whole-plan receipt.
    An undated `--init --scope <plan-slug>` dates the file TODAY, and check_convergence's fuzzy match needs
    two distinctive slug tokens, so a `plan-3-mail` reviewed after its plan's date was not counted;
    `--out <plan>-review.md` keeps the plan's own dated stem and matches by the exact rule."""
    import importlib.util

    text = " ".join(_D7_SOURCE.read_text(encoding="utf-8").split())
    review = " ".join((_D7_SOURCE.parent / "fabrik-review.md").read_text(encoding="utf-8").split())
    start = "review_receipt.py --init --out docs/development/reviews/<plan>-review.md"
    assert text.count(start) == 2, "D7 and Finish step 1 both start the receipt by the plan's stem"
    assert "--init --scope <plan-slug>" not in text
    for phrase in (
        "`<plan>` is the plan file's (a set's spine's) own dated stem",
        "an undated `--scope <plan-slug>` is dated the day it is made, and a later date with one distinctive slug "
        "token (`plan-3-mail`) matches nothing",
        "--range <baseline>..HEAD --plan <the plan file>",
        "two gate runs, one embedded while the receipt reads `IN-PROGRESS`, one after the `CONVERGED` flip "
        "embedded in its place; it is the file step 5 cites",
    ):
        assert phrase in text, phrase
    assert (
        "a plan's whole-plan receipt takes `--out docs/development/reviews/<plan>-review.md` instead" in review
    ), "/fabrik-review § Reporting points a plan's receipt at D7's naming"
    spec = importlib.util.spec_from_file_location(
        "cc_d7", _D7_SOURCE.parents[2] / "scripts" / "enforcement" / "check_convergence.py"
    )
    cc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cc)
    plan = "2026-10-01-plan-3-mail"
    assert cc._cite_matches_plan(f"{plan}-review.md", plan)
    assert not cc._cite_matches_plan("2026-10-08-plan-3-mail-review.md", plan), (
        "the later-dated --scope form is the failure the text names; if this flips, re-word the reason"
    )


def test_the_archive_step_never_edits_a_ledger_row_and_leaves_a_ledger_cited_plan_to_the_merge_owner():
    """/fabrik-execute-plan queue: Finish step 6 ordered a repoint of existing `docs/DECISIONS.md` rows, which
    the ledger merge refuses when either side edits a line beside an insertion (LESSONS 2026-10-01). The step
    now lists referrers BEFORE any move, never edits an existing row, and leaves a plan such a row cites to
    the merge owner (D-484, a90b35a3b)."""
    import importlib.util

    text = " ".join(_D7_SOURCE.read_text(encoding="utf-8").split())
    step6 = text[text.index("6. **Archive the plan") : text.index("7. **Gate, push, then name")]
    grep_at = step6.index("BEFORE any move, list the REFERRERS:")
    assert grep_at < step6.index("git mv docs/development/plans/<plan>.md"), "the referrer list precedes the move"
    for phrase in (
        "A `docs/DECISIONS.md` row already on `BASE` that cites a file of the plan by its pre-archive path "
        "decides WHO archives",
        "Never repoint that row: the ledger merge refuses any conflict where EITHER side edits an existing line",
        "it stays where it is with `Status: EXECUTED`, your Finish row cites it at that path and says the archive "
        "is owed, and the hand-over names it — the merge request from an agent window, the OWED report, or, from "
        "the main checkout, a work item or mail addressed to the repo's merge owner",
        "`BASE` here is the branch your work finally merges into",
        "The archive is the merge owner's, with every referrer in one commit, timed so no open request inserts "
        "beside the rows it repoints",
        "No such row → archive now",
    ):
        assert phrase in step6, phrase
    assert "flip the plan and archive it as step 6 allows" in text, "step 4's OWED path defers to step 6"
    assert "a plan an existing DECISIONS row cites stays EXECUTED for the merge owner to archive" in text
    spec = importlib.util.spec_from_file_location(
        "cdl_d7", _D7_SOURCE.parents[2] / "scripts" / "enforcement" / "check_doc_links.py"
    )
    cdl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cdl)
    ledger = cdl.REPO / "docs" / "DECISIONS.md"
    moved = "docs/development/plans/2026-01-01-plan-0-moved-away.md"
    assert ledger in cdl._tracked_md_sources(), "the link check reads the ledger"
    row = f"| D-1 | 2026-01-01 | infra | executed | measured | `{moved}` |"
    assert moved in [target for target, _kind in cdl._iter_refs(row)], "a ledger row's plan path is extracted"
    assert not cdl._resolves(moved, ledger), (
        "a ledger row citing a moved plan no longer breaks the gate — the stay-in-place clause is unneeded"
    )
