"""Behavior contract for scripts/enforcement/check_test_proposal.py (the STRUCTURE gate).

The plan must carry a `## Behavior Contract` that enumerates a behavior (Given/When/Then) per
acceptance criterion — not a single One-Test Rule. A plan with fewer behaviors than its stated
acceptance criteria fails; a plan with no criteria section passes on structure alone; no plans dir
skips (pass).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "scripts" / "enforcement" / "check_test_proposal.py"
sys.path.insert(0, str(ROOT))
from scripts.enforcement.check_test_proposal import evaluate_plan  # noqa: E402


def test_contract_meets_criteria_passes():
    content = """# Plan
## Behavior Contract
- **Given** X, **When** Y, **Then** Z.
- **Given** A, **When** B, **Then** C.
## Success criteria (testable)
1. does X
2. does A
"""
    ok, msg = evaluate_plan(content)
    assert ok, msg


def test_fewer_behaviors_than_criteria_fails():
    content = """# Plan
## Behavior Contract
- **Given** X, **When** Y, **Then** Z.
## Success criteria (testable)
1. does X
2. does A
3. does B
"""
    ok, msg = evaluate_plan(content)
    assert not ok
    assert "behavior" in msg.lower() and "criteri" in msg.lower()


def test_no_behavior_contract_fails():
    content = """# Plan
## One-Test Rule
- **Given** X, **When** Y, **Then** Z.
"""
    ok, msg = evaluate_plan(content)
    assert not ok
    assert "behavior contract" in msg.lower()


def test_missing_given_when_then_fails():
    content = """# Plan
## Behavior Contract
Some prose with no triple.
"""
    ok, msg = evaluate_plan(content)
    assert not ok


def test_no_criteria_section_structure_only_passes():
    # a Behavior Contract with >=1 behavior and no parseable criteria section → structure-only pass
    content = """# Plan
## Behavior Contract
- **Given** X, **When** Y, **Then** Z.
"""
    ok, msg = evaluate_plan(content)
    assert ok, msg


def test_no_plans_dir_skips(tmp_path):
    # run the script from a dir with no docs/development/plans/ → skip (exit 0)
    r = subprocess.run([sys.executable, str(CHECK)], capture_output=True, text=True, cwd=str(tmp_path))
    assert r.returncode == 0, r.stderr
