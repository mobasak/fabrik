"""Behavior contract for scripts/enforcement/check_test_proposal.py (the STRUCTURE gate).

The plan must carry a `## Behavior Contract` that enumerates a behavior (Given/When/Then) per
acceptance criterion — not a single One-Test Rule. A plan with fewer behaviors than its stated
acceptance criteria fails; a plan with no criteria section passes on structure alone; no plans dir
skips (pass).
"""

import os
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
    r = subprocess.run(
        [sys.executable, str(CHECK)], capture_output=True, text=True, cwd=str(tmp_path)
    )
    assert r.returncode == 0, r.stderr


# ── Shared-tree diff-scoping (2026-07-16): only a plan THIS change INTRODUCES is checked ──
CHECK_FILE = ROOT / "scripts" / "enforcement" / "check_test_proposal.py"
_NO_BC = "# Plan Foo\n## Success criteria\n1. does X\n"  # a plan with NO Behavior Contract
_OK_BC = "# Plan\n## Behavior Contract\n- **Given** X, **When** Y, **Then** Z.\n## Success criteria\n1. does X\n"


def _repo(tmp_path):
    def g(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    g("init", "-q")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    (tmp_path / "scripts" / "enforcement").mkdir(parents=True)
    (tmp_path / "scripts" / "enforcement" / "check_test_proposal.py").write_text(
        CHECK_FILE.read_text()
    )
    (tmp_path / "docs" / "development" / "plans").mkdir(parents=True)
    return tmp_path, g


def _run(repo):
    p = subprocess.run(
        [sys.executable, "scripts/enforcement/check_test_proposal.py"],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ},
    )
    return p.returncode, p.stdout + p.stderr


def test_sibling_pre_existing_plan_without_contract_does_not_fail(tmp_path):
    # THE bug: a sibling's committed draft with no Behavior Contract must NOT fail this agent's gate.
    repo, g = _repo(tmp_path)
    (repo / "docs/development/plans/2026-07-06-plan-5-sibling.md").write_text(_NO_BC)
    g("add", "-A")
    g("commit", "-qm", "baseline with sibling plan")
    # this agent changes something unrelated (no new plan)
    (repo / "README.md").write_text("x")
    rc, out = _run(repo)
    assert rc == 0, out
    assert "No new plan proposed" in out


def test_new_plan_without_contract_fails(tmp_path):
    # A plan THIS change adds still must carry a Behavior Contract.
    repo, g = _repo(tmp_path)
    g("add", "-A")
    g("commit", "-qm", "baseline")
    (repo / "docs/development/plans/2026-07-16-plan-1-mine.md").write_text(_NO_BC)
    rc, out = _run(repo)
    assert rc == 1, out
    assert "mine" in out


def test_new_plan_with_contract_passes(tmp_path):
    repo, g = _repo(tmp_path)
    g("add", "-A")
    g("commit", "-qm", "baseline")
    (repo / "docs/development/plans/2026-07-16-plan-1-mine.md").write_text(_OK_BC)
    rc, out = _run(repo)
    assert rc == 0, out


def test_archiving_exposes_sibling_draft_still_passes(tmp_path):
    # The exact tryton-crm scenario: archive an EXECUTED plan; the next-latest is a sibling draft.
    repo, g = _repo(tmp_path)
    (repo / "docs/development/plans/2026-07-06-plan-5-sibling.md").write_text(_NO_BC)
    (repo / "docs/development/plans/2026-07-12-plan-12-mine.md").write_text(_OK_BC)
    g("add", "-A")
    g("commit", "-qm", "baseline")
    # archive plan-12 (git mv into archived/)
    (repo / "docs/development/plans/archived").mkdir()
    g(
        "mv",
        "docs/development/plans/2026-07-12-plan-12-mine.md",
        "docs/development/plans/archived/2026-07-12-plan-12-mine.md",
    )
    rc, out = _run(repo)
    assert rc == 0, out  # must NOT fail on the exposed sibling draft
    assert "No new plan proposed" in out
