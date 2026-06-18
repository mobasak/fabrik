"""Tests for scripts/enforcement/check_convergence.py — the convergence-evidence gate.

A markdown artifact that CLAIMS convergence must embed its proof, or the gate
fails. These tests drive the real script over a throwaway git repo (it discovers
artifacts via ``git status``), so they exercise the actual code path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHECK = Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_convergence.py"

COMPLIANT_PLAN = """# Plan for X

**Status:** CONVERGED

## Evidence

## Phase 1 — wiring
Grounded in src/app/handler.py:42 (the request handler) and db/schema.sql:10.

```
$ python scripts/final_gate.py --lean
{"status": "success", "passed": 15, "failed": 0}
```

## Self-audit
Every claim above traces to a path:line citation and the gate output. No
runtime-only assumptions remain.
"""

PLAN_NO_EVIDENCE = """# Plan for X

**Status:** CONVERGED

## Phase 1
We will change the handler. It is converged, trust me.
"""

PLAN_NO_CLAIM = """# Plan for X

**Status:** DRAFT

## Phase 1
Exploratory notes; no convergence claimed yet. src/app/handler.py:42
"""

COMPLIANT_REVIEW = """# Review of plan X

## Phase 1 verdict
Mirrors the plan; no deviation.

reviewed — sign-off.

```
$ python scripts/final_gate.py --json
{"status": "success", "tier": 1, "passed": 15, "failed": 0}
```
"""

REVIEW_NO_GATE = """# Review of plan X

This was reviewed and looks converged to me.
No gate output, no phase verdicts.
"""


def _run(repo: Path, relpath: str, content: str) -> int:
    (repo / relpath).parent.mkdir(parents=True, exist_ok=True)
    (repo / relpath).write_text(content)
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--project-root", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    return tmp_path


def test_compliant_plan_passes(repo: Path) -> None:
    assert _run(repo, "docs/development/plans/2026-06-18-plan-x.md", COMPLIANT_PLAN) == 0


def test_converged_plan_without_evidence_fails(repo: Path) -> None:
    assert _run(repo, "docs/development/plans/2026-06-18-plan-x.md", PLAN_NO_EVIDENCE) == 1


def test_plan_not_claiming_convergence_is_ignored(repo: Path) -> None:
    assert _run(repo, "docs/development/plans/2026-06-18-plan-x.md", PLAN_NO_CLAIM) == 0


def test_compliant_review_passes(repo: Path) -> None:
    assert _run(repo, "docs/development/reviews/2026-06-18-plan-x-review.md", COMPLIANT_REVIEW) == 0


def test_review_without_embedded_success_fails(repo: Path) -> None:
    assert _run(repo, "docs/development/reviews/2026-06-18-plan-x-review.md", REVIEW_NO_GATE) == 1


def test_no_artifacts_passes(repo: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(CHECK), "--project-root", str(repo)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
