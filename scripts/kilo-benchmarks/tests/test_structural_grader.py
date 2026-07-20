"""Behavior Contract for the plan/spec structural grader + the correlated cold-start prior.

Hermetic — no network, no paid generation. path:line resolution is pointed at a
temp `repo_root`; the correlated prior runs against a temp sqlite seeded in-test.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@dataclass
class _G:
    """Minimal _Gen stand-in — the structural grader only touches `.text`."""

    text: str | None


def _gens(text: str | None) -> dict[str, list[_G]]:
    return {"m/model": [_G(text=text)]}


# A well-formed plan: phases + a fenced gate + a resolving citation + a test/behavior + evidence.
# `{cite}` is filled per-test so we can point it at a real (or missing) temp-repo line.
_GOOD_PLAN = """\
## Phase A — setup

Do the setup work.

Gate:
```
python -m pytest tests/ -q
```

Grounded in {cite}

Behavior: add a regression test for the new path.

## Evidence
- command output proving it green
"""

_GOOD_SPEC = """\
## Overview
What this service does.

## Acceptance criteria
- it works

## Interface
`GET /health`

shape:
  needs_database: true
  status_enum: [active, paused, archived]

Grounded in {cite}
"""


def _seed_repo(tmp_path: Path) -> Path:
    """A temp repo_root with one cite-able file (≥3 lines)."""
    (tmp_path / "target.py").write_text("line1\nline2\nline3\n")
    return tmp_path


# ── (a) TDD FIRST — the HARD-FAIL branch: a text passing OTHER checks but with no phases+gates → 0 ──
def test_plan_without_gates_is_disqualified(tmp_path):
    """A text that PASSES citations+test+evidence (3/5 checks) but has NO phases AND NO runnable gate is
    disqualified to 0.0 — proving the hard-fail OVERRIDES the would-be 3/5×5=3.0 (reviewer S3: the old
    fixture failed all 5 checks, so it scored 0 whether or not the hard-fail branch existed)."""
    from structural_grader import structural_grade

    root = _seed_repo(tmp_path)  # target.py:2 resolves
    text = "Notes grounded in target.py:2\nBehavior: add a regression test.\n## Evidence\n- proof\n"
    s = structural_grade(_gens(text), [], "plan", repo_root=root)["m/model"]
    assert s.score5 == 0.0, (
        f"hard-fail (no phases AND no gate) must be 0.0 despite 3 passing checks, got {s.score5}"
    )
    assert s.n_graded == 1


# ── (b) an unresolvable path:line lowers the score vs an identical resolving one ──
def test_unresolvable_citation_penalizes(tmp_path):
    from structural_grader import structural_grade

    root = _seed_repo(tmp_path)
    good = structural_grade(
        _gens(_GOOD_PLAN.format(cite="target.py:2")), [], "plan", repo_root=root
    )
    bad = structural_grade(
        _gens(_GOOD_PLAN.format(cite="target.py:9999")), [], "plan", repo_root=root
    )
    g, b = good["m/model"], bad["m/model"]
    assert g.score5 == 5.0, (
        f"a fully-formed plan with a resolving cite should be 5.0, got {g.score5}"
    )
    assert b.score5 < g.score5, "an unresolvable path:line must lower the score"


def test_out_of_repo_citation_is_rejected(tmp_path):
    """A ../ escape to a file that REALLY EXISTS outside repo_root must NOT resolve — only the containment
    guard stops it (reviewer S2: the old `../../../etc/passwd:1` had no extension, so it never matched the
    citation regex and was rejected via the empty-cites path, never exercising the guard). Here the escape
    target has a .py extension AND exists, so a missing guard would resolve it."""
    from structural_grader import structural_grade

    root = tmp_path / "repo"
    root.mkdir()
    (root / "target.py").write_text("l1\nl2\nl3\n")
    (tmp_path / "outside.py").write_text("s1\ns2\ns3\n")  # a REAL file OUTSIDE root
    escaped = structural_grade(
        _gens(_GOOD_PLAN.format(cite="../outside.py:1")), [], "plan", repo_root=root
    )
    assert escaped["m/model"].score5 < 5.0  # containment guard rejected the escaping cite


# ── (c) a spec missing a required section is penalized (but not disqualified) ──
def test_spec_missing_section_penalized(tmp_path):
    from structural_grader import structural_grade

    root = _seed_repo(tmp_path)
    full = structural_grade(
        _gens(_GOOD_SPEC.format(cite="target.py:2")), [], "spec", repo_root=root
    )
    missing = _GOOD_SPEC.format(cite="target.py:2").replace("## Interface\n`GET /health`\n", "")
    partial = structural_grade(_gens(missing), [], "spec", repo_root=root)
    f, p = full["m/model"], partial["m/model"]
    assert f.score5 == 5.0, f"a complete spec should be 5.0, got {f.score5}"
    assert 0.0 < p.score5 < f.score5, "a missing section must penalize, not disqualify"


# ── (d) correlated_prior.build seeds a plan prior from code+review, idempotently ──
def _seed_metrics_db(db: Path) -> None:
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE model_coding_metrics (
            model_id TEXT, grade TEXT, pass_at_1 REAL, score5 REAL,
            cost_per_1k REAL, p50_latency_s REAL, n_err INTEGER, built_at TEXT);
        CREATE TABLE model_review_metrics (
            model_id TEXT, grade TEXT, score5 REAL, recall REAL, precision REAL,
            cost_per_1k REAL, p50_latency_s REAL, cost_usd REAL, built_at TEXT);
        """
    )
    conn.execute(
        "INSERT INTO model_coding_metrics VALUES ('x/model','A',0.9,4.0,1.0,2.0,0,'2026-07-19')"
    )
    conn.execute(
        "INSERT INTO model_review_metrics VALUES ('x/model','B',3.0,0.6,1.0,0.5,2.0,0.004,'2026-07-19')"
    )
    conn.commit()
    conn.close()


def test_correlated_prior_seeds_plan_from_code_and_review(tmp_path):
    from correlated_prior import build

    db = tmp_path / "kilo_agents.db"
    _seed_metrics_db(db)
    n = build(db_path=db)
    assert n >= 1

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT baseline, source FROM model_task_baseline WHERE model_id='x/model' AND task_type='plan'"
    ).fetchone()
    conn.close()
    assert row is not None, "a plan prior row must be written for a model with code+review scores"
    assert row[0] == 3.5, f"plan prior should be mean(code=4.0, review=3.0)=3.5, got {row[0]}"
    assert row[1] == "correlated:code+review"

    # idempotent — a re-run must not duplicate or drift the row
    build(db_path=db)
    conn = sqlite3.connect(db)
    cnt, baseline = conn.execute(
        "SELECT COUNT(*), MAX(baseline) FROM model_task_baseline "
        "WHERE model_id='x/model' AND task_type='plan'"
    ).fetchone()
    conn.close()
    assert cnt == 1, f"build must be idempotent (one row per model,task), got {cnt}"
    assert baseline == 3.5


# ── (e) both graders registered; the flywheel-primary / PoLL-deferred note present ──
def test_graders_registered_and_flywheel_note_present():
    import structural_grader  # noqa: F401 — import registers the graders
    from microbench_judged import GRADERS

    assert "plan" in GRADERS and "spec" in GRADERS, "structural grader must register plan + spec"
    note = structural_grader.FLYWHEEL_PRIMARY_NOTE.lower()
    assert "flywheel" in note and "defer" in note, (
        "must state the flywheel is primary + PoLL deferred"
    )


def test_correlated_prior_never_clobbers_a_measured_baseline(tmp_path):
    """A6: a MEASURED `microbench_judged:*` plan/spec baseline must survive a daily correlated run —
    _write_priors skips a (model, task) that already has a measured source."""
    import sqlite3

    import correlated_prior as cp
    from build_task_baselines import ensure_table

    db = tmp_path / "k.db"
    ensure_table(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO model_task_baseline (model_id, task_type, baseline, pass_rate, n_tasks, n_trials, source, built_at) "
        "VALUES ('m/measured','plan',4.8,0.96,10,10,'microbench_judged:plan','2026-07-20')"
    )
    conn.commit()
    conn.close()
    # a correlated run tries to write plan priors for both models
    n = cp._write_priors(
        db, "plan", {"m/measured": 3.0, "m/cold": 3.2}, "correlated:code+review", 5.0
    )
    assert n == 1  # only m/cold written; m/measured skipped (measured wins)
    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT baseline, source FROM model_task_baseline WHERE model_id='m/measured'"
    ).fetchone()
    conn.close()
    assert row == (
        4.8,
        "microbench_judged:plan",
    )  # untouched — the correlated 3.0 did NOT clobber it
