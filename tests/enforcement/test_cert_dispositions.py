# AFTER-EDIT: scripts/enforcement/check_review_coverage.py
"""Certification disposition gate — HANDOFF rows must be provable, not prose."""

import subprocess
import sys
from pathlib import Path

CHECK = Path("/opt/fabrik/scripts/enforcement/check_review_coverage.py")


def _run(repo: Path, name: str, content: str, repro: str | None = None) -> int:
    (repo / "docs/development/reviews").mkdir(parents=True, exist_ok=True)
    (repo / f"docs/development/reviews/{name}").write_text(content)
    if repro:
        (repo / repro).parent.mkdir(parents=True, exist_ok=True)
        (repo / repro).write_text("def test_x(): assert True\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, timeout=15, capture_output=True)
    return subprocess.run(
        [sys.executable, str(CHECK), "--root", str(repo)],
        capture_output=True, text=True, timeout=30,
    ).returncode


import pytest


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    return tmp_path


def test_closed_row_with_existing_repro_and_proof_passes(repo: Path) -> None:
    rc = _run(repo, "2026-08-03-user-test-app.md",
              "# cert\nHANDOFF P1 CLOSED login bug — repro: tests/ui/test_login.py — proof: 1 passed in 0.4s\n",
              repro="tests/ui/test_login.py")
    assert rc == 0


def test_closed_row_missing_repro_fails(repo: Path) -> None:
    rc = _run(repo, "2026-08-03-user-test-app.md",
              "# cert\nHANDOFF P1 CLOSED login bug — proof: passed\n")
    assert rc == 1


def test_closed_row_nonexistent_repro_fails(repo: Path) -> None:
    rc = _run(repo, "2026-08-03-service-test-api.md",
              "# cert\nHANDOFF P0 CLOSED oops — repro: tests/nope.py — proof: passed\n")
    assert rc == 1


def test_closed_row_missing_proof_fails(repo: Path) -> None:
    rc = _run(repo, "2026-08-03-user-test-app.md",
              "# cert\nHANDOFF P2 CLOSED x — repro: tests/ui/t.py\n", repro="tests/ui/t.py")
    assert rc == 1


def test_open_row_without_notquiet_or_resume_fails(repo: Path) -> None:
    rc = _run(repo, "2026-08-03-user-test-app.md",
              "# cert\nHANDOFF P1 OPEN backend bug — repro: tests/ui/t.py — route: /fabrik-review src/x\n",
              repro="tests/ui/t.py")
    assert rc == 1


def test_open_row_with_notquiet_and_resume_passes(repo: Path) -> None:
    rc = _run(repo, "2026-08-03-service-test-api.md",
              "# cert\nHANDOFF P1 OPEN backend bug — repro: tests/t.py — route: /fabrik-review src/x\n"
              "ledger: NOT-QUIET (routes outstanding)\n\n## RESUME\n- the row above; re-invoke /fabrik-service-test\n",
              repro="tests/t.py")
    assert rc == 0


def test_notquiet_without_resume_fails(repo: Path) -> None:
    rc = _run(repo, "2026-08-03-user-test-app.md", "# cert\nNOT-QUIET (routes outstanding)\n")
    assert rc == 1


def test_design_gap_rows_may_stay_open(repo: Path) -> None:
    rc = _run(repo, "2026-08-03-user-test-app.md",
              "# cert\nDESIGN-GAP missing export screen — brief: docs/development/reviews/2026-08-03-design-gap-export.md\n")
    assert rc == 0


def test_prose_report_without_grammar_rows_passes(repo: Path) -> None:
    # zero-false-positive: a report using no grammar rows is not failed by this gate
    rc = _run(repo, "2026-08-03-user-test-app.md", "# cert\nAll green, nothing handed off.\n")
    assert rc == 0
