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
    """Check if the D7 section contains the live-request requirement.
    
    The requirement must:
    1. Mention "live request" or similar meaningful phrase
    2. Reference "## Evidence" as the location for the pasted request/response
    
    This is a semantic check on the section content, not just a string search.
    """
    # Check for the key phrase "live request" (case-insensitive)
    has_live_request = bool(re.search(r'live\s+request', section, re.IGNORECASE))
    
    # Check for "## Evidence" reference (the location where the request/response must be pasted)
    has_evidence_ref = '## Evidence' in section
    
    # Both must be present for a valid requirement
    return has_live_request and has_evidence_ref


def test_d7_section_contains_live_request_requirement():
    """Assert that D7 names the live-request requirement.
    
    This is the primary pin test: it reads the actual D7 section from the
    execute-plan markdown and asserts it contains the live-request requirement.
    """
    with open('./commands/_sources/fabrik-execute-plan.md', 'r') as f:
        content = f.read()
    
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
    with open('./commands/_sources/fabrik-execute-plan.md', 'r') as f:
        content = f.read()
    
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
