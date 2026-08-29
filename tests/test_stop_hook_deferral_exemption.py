"""The Stop hook must not exempt a bare "operator decision" from the checkpoint-stall guard.

Operator raised this three times; prose lost twice because the hook REWARDED the deferral: any of
six magic phrases disarmed the guard outright. Measured over one session's 905 NEXT: lines before
the fix (92998479): 281 deferrals, only 15% naming a reason that genuinely required a human.

The contract now: self-naming gates exempt alone; bare deferral vocabulary must share its line
with a HARD-STOP class (cross-repo, deploy, spend, irreversible, policy, or rule-conflict citing
path:line). Found at the day's closing review: the fix had shipped with only a SCRATCHPAD probe —
this file is the permanent grader the FIX DIRECTIVE requires.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "final_gate_stop", REPO / ".claude" / "hooks" / "final_gate_stop.py"
)
fgs = importlib.util.module_from_spec(_spec)
sys.modules["final_gate_stop"] = fgs
_spec.loader.exec_module(fgs)


def exempt(line: str) -> bool:
    m = re.search(r"NEXT:", line)
    assert m, "test lines must carry NEXT:"
    return fgs._line_exempt(line, m)


@pytest.mark.parametrize(
    "line",
    [
        "NEXT: awaiting your go on measuring the 29 suites serially — that is read-only",
        "NEXT: operator decision — do the three repos with red suites get their tests fixed?",
        "NEXT: your call — extend the grader, or leave it deferred",
        "NEXT: operator decision — approve the design so C1/C2 can be planned",
        "NEXT: say the word and I will run the sweep",
    ],
)
def test_a_classless_deferral_no_longer_disarms_the_stall_guard(line):
    assert not exempt(line), f"bare deferral exempted again — the escape hatch reopened: {line!r}"


@pytest.mark.parametrize(
    "line",
    [
        "NEXT: operator decision [cross-repo] — write the marker into 39 repos I was not launched in",
        "NEXT: operator decision [gate 2] — dispatch /fabrik-deploy for the zitadel stack",
        "NEXT: operator decision [spend] — the full benchmark run costs ~$24 of real quota",
        "NEXT: operator decision [irreversible] — drop and recreate the production database",
        "NEXT: operator decision [rule-conflict] — CLAUDE.md:120 mandates X, core/30-ops.md:44 forbids it",
        "NEXT: Gate 2 — human approval; on the operator's explicit go: /fabrik-deploy",
        "NEXT: plan approval — your go dispatches the build",
    ],
)
def test_a_genuine_human_gate_still_exempts(line):
    """The false-positive half — over-blocking real gates is how THIS fix would die."""
    assert exempt(line), f"a genuine human gate was blocked: {line!r}"


def test_rule_conflict_without_a_citation_does_not_exempt():
    """The operator's carve-out must cite the contradiction, or it becomes the next escape hatch."""
    assert not exempt("NEXT: operator decision [rule-conflict] — two rules disagree, you pick")
