"""The gate must not lose its test suite when a repo retires GitHub Actions.

`final_gate`'s local pytest used to run if and only if a workflow file mentioned "pytest".
That proxy inverts during a CI cutover: deleting `.github/workflows/` silently DISARMS local
pytest, so a move meant to keep the same checks quietly removes one. Measured 2026-08-29:
10 /opt repos run pytest locally today for no reason other than that workflow text.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


def _decider(root: Path):
    """Rebuild the gate's decision predicate against an arbitrary PROJECT_ROOT.

    `_ci_runs_pytest` is a closure inside `run_checks`, so it cannot be imported. This mirrors
    it exactly; `test_the_mirror_matches_the_real_source` pins the mirror to the real code so
    this file cannot drift into testing a fiction.
    """
    if (root / ".fabrik" / "run-pytest").exists():
        return True
    wf = root / ".github" / "workflows"
    if not wf.is_dir():
        return False
    return any(
        "pytest" in f.read_text(encoding="utf-8", errors="ignore") for f in wf.glob("*.y*ml")
    )


def test_deleting_workflows_disarms_pytest_without_the_marker(tmp_path: Path):
    """The trap, reproduced: CI mentions pytest -> runs; delete the workflows -> stops."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("jobs:\n  t:\n    steps:\n      - run: pytest -q\n")
    assert _decider(tmp_path) is True
    (wf / "ci.yml").unlink()
    assert _decider(tmp_path) is False, "this is the regression the marker exists to prevent"


def test_the_marker_keeps_pytest_running_with_no_workflows_at_all(tmp_path: Path):
    """The fix: a repo that retired Actions keeps its suite by declaring it."""
    (tmp_path / ".fabrik").mkdir(parents=True)
    (tmp_path / ".fabrik" / "run-pytest").touch()
    assert _decider(tmp_path) is True


def test_absent_marker_and_absent_ci_still_means_no(tmp_path: Path):
    """The false-positive side — the marker must be opt-IN, not a default-on that would newly
    switch pytest on in 29 repos with unproven suites."""
    assert _decider(tmp_path) is False


def test_the_mirror_matches_the_real_source():
    """Pin the mirror above to the shipped predicate, so this file cannot pass while the gate
    behaves differently — a vacuous test is worse than none."""
    src = (REPO / "scripts" / "final_gate.py").read_text(encoding="utf-8")
    assert 'if (PROJECT_ROOT / ".fabrik" / "run-pytest").exists():' in src, (
        "the marker check is gone from final_gate.py — this test is now a fiction"
    )
    assert "def _ci_runs_pytest() -> bool:" in src


@pytest.mark.parametrize("marker_first", [True, False])
def test_marker_wins_regardless_of_workflow_state(tmp_path: Path, marker_first: bool):
    """Order-independence: the marker is authoritative whether or not CI also says so."""
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    if marker_first:
        (tmp_path / ".fabrik").mkdir()
        (tmp_path / ".fabrik" / "run-pytest").touch()
    (wf / "ci.yml").write_text("jobs:\n  t:\n    steps:\n      - run: echo no-tests-here\n")
    if not marker_first:
        (tmp_path / ".fabrik").mkdir()
        (tmp_path / ".fabrik" / "run-pytest").touch()
    assert _decider(tmp_path) is True


def _should_run(root: Path, changed: set[str]) -> bool:
    """Mirror of the gate's ENCLOSING condition (the prefix leg), pinned to the source below."""
    armed = (root / ".fabrik" / "run-pytest").exists()
    return (
        (root / "tests").is_dir()
        and _decider(root)
        and (
            armed
            or not changed
            or any(f.startswith("src/") for f in changed)
            or any(f.startswith("tests/") for f in changed)
            or any(f.startswith("scripts/") for f in changed)
        )
    )


def test_the_marker_runs_the_suite_on_a_diff_outside_the_three_prefixes(tmp_path: Path):
    """The armed leg was ANDed with `src/|tests/|scripts/`: a repo whose code lives under `api/`
    armed the sentinel on infra's instruction and still ran no tests on an `api/`-only diff —
    green, invisibly (site-provisioner 01M1QS9527Y8K0P9VPE9XF5MYB; its suite found 2 real
    failures when finally run). The sentinel is the opt-in: any change runs the suite."""
    (tmp_path / "tests").mkdir()
    (tmp_path / ".fabrik").mkdir()
    (tmp_path / ".fabrik" / "run-pytest").touch()
    assert _should_run(tmp_path, {"api/routes.py"})
    assert _should_run(tmp_path, {"docs/x.md"})


def test_the_legacy_ci_text_fallback_keeps_the_prefix_gate(tmp_path: Path):
    (tmp_path / "tests").mkdir()
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("run: pytest\n")
    assert not _should_run(tmp_path, {"api/routes.py"})
    assert _should_run(tmp_path, {"src/x.py"})


def test_the_enclosing_condition_mirror_matches_the_real_source():
    src = (REPO / "scripts" / "final_gate.py").read_text(encoding="utf-8")
    assert '_armed = (PROJECT_ROOT / ".fabrik" / "run-pytest").exists()' in src
    assert "            _armed\n            or not changed\n" in src
