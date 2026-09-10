# AFTER-EDIT: commands/_fragments/term-edit.md docs/workflows/FINAL_GATE_WORKFLOW.md
"""The flip-gate invocation MATRIX — a gate run counts only when the artifact is provably in the
gate's examined set (review-family adoption plan, Phase A; spec D7).

Four invocation shapes were measured to return GREEN OVER NOTHING on 2026-09-10 (the adoption spec's
§ Machinery report): a committed-clean scratch copy is invisible to ``check_convergence`` (its target
discovery reads ``git status --porcelain`` and skips ``??``); ``check_plan_quality`` has no CLI and binds
``PLAN_DIR`` to the cwd at import; ``check_citations_resolve --root <scratch>`` ticks green over 0
examined anchors; ``check_plan_tickets --plan-dir <non-dated>`` refuses. ``MATRIX`` is the documented
form (``docs/workflows/FINAL_GATE_WORKFLOW.md``); every row is pinned by a test that plants a minimal
fixture and asserts the gate's OWN examined marker names it (the ``check_plan_quality`` row, whose gate
prints nothing, asserts its findings and their severity instead), plus the negative control the row exists
to avoid. Characterisation tests: every gate already behaves this way — the watched-fail half is a
MUTANT per row on a scratch copy of ``scripts/enforcement/`` (``FLIP_GATE_MATRIX_ENFORCEMENT_DIR``),
asserted on disk and kept in the plan's receipt.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
# The gate directory under test — the real one by default; the mutant proofs point it at a copy.
ENF = Path(
    os.environ.get("FLIP_GATE_MATRIX_ENFORCEMENT_DIR", str(REPO / "scripts" / "enforcement"))
)

# (gate, invocation, tree, examined marker) — one row per flip gate the `term-edit` loops run.
MATRIX: list[tuple[str, str, str, str]] = [
    (
        "check_spec_convergence.py",
        "--root <scratch>",
        "scratch root; the flipped spec copy under docs/superpowers/specs/",
        "1 CONVERGED spec(s) examined",
    ),
    (
        "check_rule_grounding.py",
        "--root <scratch>",
        "scratch root with scripts/ and .windsurf/ linked in; the flipped plan copy (dated >= the "
        "floor cutoff) carrying a Constraints digest",
        "1 CONVERGED in-window plan(s) examined",
    ),
    (
        "check_plan_tickets.py",
        "--plan-dir <set> --project-root <scratch>",
        "scratch root; the set under docs/development/plans/<dated dir>/ (a non-dated dir is "
        "REFUSED: `✗ … not a dated plan directory`, exit 1)",
        "graded 1 ticket(s)",
    ),
    (
        "check_convergence.py",
        "--project-root <scratch> — targets from _converged_targets(root)",
        "scratch GIT root; the flipped spine TRACKED-AND-UNCOMMITTED (`git add -N`); a "
        "committed-clean or untracked copy is NOT examined",
        "the spine path is in _converged_targets(root)",
    ),
    (
        "check_plan_quality.py",
        "no CLI — check_file() through its import (the gate reaches it via validate_conventions "
        "--strict --git-diff from the REAL tree; advisory)",
        "a scratch plans dir with BOTH PLAN_DIR bindings patched (this test's own method — the gate "
        "binds PLAN_DIR to the cwd at import, so the real tree is only the unpatched default); the "
        "fixture inside it is FLIPPED (the gate reads Status: a DRAFT is graded to WARN, a CONVERGED "
        "to ERROR); a path outside it returns []",
        "check_file() returns the missing-section finding inside PLAN_DIR (a DRAFT's WARN is "
        "--strict-exempt; a CONVERGED's ERROR fails validate_conventions)",
    ),
]


def _load(name: str, enf: Path = ENF):
    """Import a gate module from ``enf`` by file, so a mutant copy is what the test grades.

    The gates reach their siblings through a bare ``sys.path`` fallback import, and Python caches
    bare modules — so every sibling of ``enf`` is purged from ``sys.modules`` and ``enf`` is put
    first on ``sys.path`` before the load, or a second load would keep the FIRST directory's
    siblings (a mutant proof would read green over the real module). A gate whose fallback is the
    DOTTED ``from scripts.enforcement.X import`` cannot be isolated this way at all (the cached
    package resolves X from the real directory), so a copy of one is REFUSED here — such a gate's
    mutant runs in a fresh process (``FLIP_GATE_MATRIX_ENFORCEMENT_DIR`` + ``PYTHONPATH=<root>``).
    """
    source = (enf / f"{name}.py").read_text()
    if enf != ENF and "from scripts.enforcement" in source:
        raise RuntimeError(
            f"{name} falls back to a dotted `from scripts.enforcement.X import` — the cached "
            "`scripts.enforcement` package resolves X from the REAL directory, so a copy cannot be "
            "isolated in-process; run it in a fresh process with PYTHONPATH=<root> instead"
        )
    for sibling in enf.glob("*.py"):
        sys.modules.pop(sibling.stem, None)
    sys.path.insert(0, str(enf))
    spec = importlib.util.spec_from_file_location(name, enf / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _run(script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ENF / script), *args],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(cwd) if cwd else None,
        check=False,
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=a@b", "-c", "user.name=a", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout


SPEC_FIXTURE = """# Fixture design

Status: CONVERGED (fixture)

## Goal

Purely internal — no external facts.

## Convergence & residuals

Resolved: none open.
"""

PLAN_STEM = "2026-09-10-plan-1-matrix-fixture"

PLAN_FIXTURE = """# Matrix fixture plan

Status: CONVERGED (fixture)

## Goal

Pin the examined set.

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| core/10-python.md | uv | :21 |

## File Scope (owned paths)

- scripts/enforcement/check_convergence.py

## Constraints digest

| Verbatim quote | Source | Applies to |
|---|---|---|
| "**`uv`** is the mandated Python package manager." | `.windsurf/rules/core/10-python.md:21` | the gate |

## Phase A

Step. scripts/enforcement/check_convergence.py:1

## Evidence

```
$ echo probe
probe
```

## Self-audit

Grounding passes.
"""

SPINE_FIXTURE = """# Matrix fixture set

Status: CONVERGED (fixture)

## Goal

Pin the examined set.

## Ticket Board

| Ticket | Title | State |
|---|---|---|
| T01 | fixture | ⚪ |

## Phase A

Step. scripts/enforcement/check_convergence.py:1

## Evidence

```
$ echo probe
probe
```
"""

TICKET_FIXTURE = """# T01 — fixture

## Scope
A fixture ticket. DO-NOT: touch anything else.

Depends: —
Parallel: ⚡
Complexity: simple
Gate: python -m pytest tests/enforcement -q
Docs: none

## Touches
- scripts/enforcement/check_convergence.py — PRIMARY PATH

## Context Files
- .windsurf/rules/core/10-python.md
"""


def _plant_set(root: Path, dirname: str) -> Path:
    d = root / "docs" / "development" / "plans" / dirname
    d.mkdir(parents=True)
    (d / f"{dirname}.md").write_text(SPINE_FIXTURE)
    (d / "T01-fixture.md").write_text(TICKET_FIXTURE)
    return d


@pytest.mark.parametrize("gate", [row[0] for row in MATRIX], ids=[row[0] for row in MATRIX])
def test_the_pinned_artifact_is_in_the_gates_examined_set(gate: str, tmp_path: Path, monkeypatch):
    row = next(r for r in MATRIX if r[0] == gate)
    marker = row[3]

    if gate == "check_spec_convergence.py":
        specs = tmp_path / "docs" / "superpowers" / "specs"
        specs.mkdir(parents=True)
        (specs / "2026-09-10-matrix-fixture-design.md").write_text(SPEC_FIXTURE)
        out = _run(gate, "--root", str(tmp_path))
        assert marker in out.stdout, out.stdout + out.stderr
        # negative control: an empty root prints NOTHING — a green with no census examined nothing
        empty = tmp_path / "empty"
        empty.mkdir()
        assert "examined" not in _run(gate, "--root", str(empty)).stdout

    elif gate == "check_rule_grounding.py":
        (tmp_path / "docs" / "development" / "plans").mkdir(parents=True)
        (tmp_path / "docs" / "development" / "plans" / f"{PLAN_STEM}.md").write_text(PLAN_FIXTURE)
        (tmp_path / "scripts").symlink_to(REPO / "scripts")
        (tmp_path / ".windsurf").symlink_to(REPO / ".windsurf")
        out = _run(gate, "--root", str(tmp_path))
        assert marker in out.stdout, out.stdout + out.stderr
        # negative control: a plan dated before the floor cutoff is silently out of window
        old = tmp_path / "old"
        (old / "docs" / "development" / "plans").mkdir(parents=True)
        (old / "docs" / "development" / "plans" / "2026-08-01-plan-1-old.md").write_text(
            PLAN_FIXTURE
        )
        assert "examined" not in _run(gate, "--root", str(old)).stdout

    elif gate == "check_plan_tickets.py":
        d = _plant_set(tmp_path, PLAN_STEM)
        out = _run(gate, "--plan-dir", str(d), "--project-root", str(tmp_path), cwd=tmp_path)
        assert marker in out.stdout, out.stdout + out.stderr
        # negative control: a non-dated directory is refused with the marker AND exit 1
        bad = tmp_path / "docs" / "development" / "plans" / "matrix-fixture"
        bad.mkdir()
        (bad / "matrix-fixture.md").write_text(SPINE_FIXTURE)
        neg = _run(gate, "--plan-dir", str(bad), "--project-root", str(tmp_path), cwd=tmp_path)
        assert "not a dated plan directory" in neg.stdout, neg.stdout
        assert neg.returncode == 1, neg.returncode

    elif gate == "check_convergence.py":
        cc = _load("check_convergence")
        _git(tmp_path, "init", "-q")
        _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "root")
        d = _plant_set(tmp_path, PLAN_STEM)
        spine = d / f"{PLAN_STEM}.md"
        rel = str(spine.relative_to(tmp_path))
        # untracked → NOT examined (a `??` in-flight draft is checked at staging)
        assert cc._converged_targets(tmp_path) == []
        # tracked-and-uncommitted → examined
        _git(tmp_path, "add", "-N", "--", rel)
        assert [p.resolve() for p in cc._converged_targets(tmp_path)] == [spine.resolve()]
        # the gate REFUSES the fixture once its Evidence is gone — proof the target was graded
        spine.write_text(SPINE_FIXTURE.replace("## Evidence", "## Notes"))
        out = _run(gate, "--project-root", str(tmp_path))
        assert "Convergence gate FAILED" in out.stdout and "Evidence" in out.stdout, out.stdout
        assert out.returncode == 1
        # committed-clean → NOT examined (settled at HEAD)
        spine.write_text(SPINE_FIXTURE)
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "pin")
        assert cc._converged_targets(tmp_path) == []

    elif gate == "check_plan_quality.py":
        cpq = _load("check_plan_quality")
        plans = tmp_path / "docs" / "development" / "plans"
        plans.mkdir(parents=True)
        monkeypatch.setattr(cpq, "PLAN_DIR", plans)
        # `check_plans` (the naming pre-check `check_file` runs FIRST) binds its OWN cwd-bound
        # `PLAN_DIR`; left unpatched it early-outs on every scratch path and reads as "validly named"
        monkeypatch.setitem(cpq._check_plans_naming.__globals__, "PLAN_DIR", plans)
        inside = plans / f"{PLAN_STEM}.md"
        inside.write_text(PLAN_FIXTURE.replace("## Evidence", "## Notes"))
        findings = cpq.check_file(inside)
        assert any("Evidence" in f.message for f in findings), [f.message for f in findings]
        # the severity contract the row states: the gate reads Status — CONVERGED grades the gap ERROR
        # (fails validate_conventions), a DRAFT grades it WARN (--strict-exempt)
        assert "WARN" in marker and "ERROR" in marker, marker  # the row text states what is asserted below
        evidence = [f for f in findings if "Evidence" in f.message]
        assert evidence[0].severity is cpq.Severity.ERROR, [(f.message, f.severity) for f in findings]
        inside.write_text(inside.read_text().replace("Status: CONVERGED (fixture)", "Status: DRAFT (fixture)"))
        draft = [f for f in cpq.check_file(inside) if "Evidence" in f.message]
        assert draft and draft[0].severity is cpq.Severity.WARN, [(f.message, f.severity) for f in draft]
        inside.write_text(inside.read_text().replace("Status: DRAFT (fixture)", "Status: CONVERGED (fixture)"))
        # the naming pre-check is LIVE for the scratch dir: a mis-named plan inside it is
        # check_plans' finding, so this gate returns [] for it (precedence 0) — not the section finding
        misnamed = plans / "notes.md"
        misnamed.write_text(inside.read_text())
        assert cpq.check_file(misnamed) == []
        # negative control: the same file outside PLAN_DIR is silently out of scope
        outside = tmp_path / "elsewhere" / f"{PLAN_STEM}.md"
        outside.parent.mkdir()
        outside.write_text(inside.read_text())
        assert cpq.check_file(outside) == []

    else:  # pragma: no cover - a MATRIX row without a test is exactly the gap this file closes
        raise AssertionError(f"no test for matrix row {gate}")


def test_load_resolves_a_gates_sibling_imports_from_the_enforcement_dir_under_test(tmp_path):
    """`check_plan_quality.py` reaches `check_plans` through a bare `sys.path` fallback import, and
    Python caches bare modules in `sys.modules` — so a second `_load()` from a scratch copy would keep
    the FIRST directory's `check_plans` and a mutant there would be invisible (a false-green mutant
    proof). `_load` purges the gate's sibling modules first; this test loads the real gate, then a
    copy whose `check_plans` is marked, and asserts the copy's sibling is the one bound."""
    _load("check_plan_quality")  # the real one first — the cache the second load must not inherit
    root = tmp_path / "scripts" / "enforcement"
    shutil.copytree(REPO / "scripts" / "enforcement", root)
    marker = root / "check_plans.py"
    marker.write_text(marker.read_text() + "\nMATRIX_MARKER = 'copy'\n")
    cpq = _load("check_plan_quality", enf=root)
    bound = cpq._check_plans_naming.__globals__
    assert bound.get("MATRIX_MARKER") == "copy", bound.get("__file__")
    # a gate whose fallback is the DOTTED `from scripts.enforcement.X import` resolves X through the
    # cached `scripts.enforcement` package — the REAL directory — however the purge is shaped, so an
    # in-process load of such a gate from a copy can never isolate it: `_load` refuses, and the copy
    # runs in a fresh process instead (`FLIP_GATE_MATRIX_ENFORCEMENT_DIR` + `PYTHONPATH=<root>`)
    with pytest.raises(RuntimeError, match="dotted"):
        _load("check_convergence", enf=root)


def test_every_matrix_row_names_a_gate_that_exists():
    for gate, _invocation, _tree, _marker in MATRIX:
        assert (ENF / gate).is_file(), gate
