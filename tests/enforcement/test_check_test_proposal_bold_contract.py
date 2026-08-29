"""check_test_proposal must accept BOTH Behavior Contract forms check_phase_tests accepts.

tryton-crm 01M17EKV: the two synced checks parsed the same construct with different
grammars — a plan carrying 13 valid rows under `**Behavior Contract (Phase A)**` bold
labels (the form check_phase_tests:95 documents and /fabrik-plan-after-chat's per-phase
guidance uses) blocking-FAILED check_test_proposal with a CONTENT verdict ("enumerates
no behavior") for what was a pure SYNTAX mismatch.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "ctp_probe", REPO / "scripts" / "enforcement" / "check_test_proposal.py"
)
ctp = importlib.util.module_from_spec(_spec)
sys.modules["ctp_probe"] = ctp
_spec.loader.exec_module(ctp)

_BOLD_PLAN = (
    "# Plan — X\n\n## Phase A\n\n"
    "**Behavior Contract (Phase A):**\n"
    "- **Given** a staged review **When** the hook runs **Then** it grades\n"
    "- **Given** a clean artifact **When** graded **Then** exit 0\n\n"
    "Prose resumes here, ending the block.\n"
)

_HEADING_PLAN = (
    "# Plan — X\n\n## Behavior Contract\n\n"
    "- **Given** a **When** b **Then** c\n\n## Next section\n"
)


def test_bold_label_contract_passes():
    ok, msg = ctp.evaluate_plan(_BOLD_PLAN)
    assert ok, f"bold-form contract must pass (check_phase_tests accepts it): {msg}"


def test_heading_contract_still_passes():
    ok, msg = ctp.evaluate_plan(_HEADING_PLAN)
    assert ok, msg


def test_zero_row_message_names_the_accepted_forms():
    # the old message reported a CONTENT verdict for a SYNTAX miss, sending the
    # reader hunting for rows that were present all along
    ok, msg = ctp.evaluate_plan(
        "# P\n\nbehavior contract discussed in prose, given when then words present\n"
    )
    assert not ok
    assert "bold label" in msg and "##" in msg, f"message must name both accepted forms: {msg}"
