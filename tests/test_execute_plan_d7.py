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
_D7_SOURCE = Path(__file__).resolve().parents[1] / "commands" / "_sources" / "fabrik-execute-plan.md"


def _d7_section(text: str) -> str:
    """Extract the D7 section from the execute-plan markdown text.
    
    The section starts at the D7 heading and ends at the next section header (### or ##)
    or the end of the file.
    """
    lines = text.split('\n')
    d7_start = None
    d7_end = None
    
    for i, line in enumerate(lines):
        if '### D7 — Final validation + terminal states' in line:
            d7_start = i
            # Find next section header (### or ##)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith('### ') or lines[j].startswith('## '):
                    d7_end = j
                    break
            break
    
    if d7_start is None:
        return ''
    
    if d7_end is None:
        d7_end = len(lines)
    
    return '\n'.join(lines[d7_start:d7_end])


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
    lines = mutated.split('\n')
    filtered_lines = [
        line for line in lines 
        if not (re.search(r'live', line, re.IGNORECASE) and re.search(r'request', line, re.IGNORECASE))
        and '## Evidence' not in line
    ]
    mutated = '\n'.join(filtered_lines)
    
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
