# AFTER-EDIT: capture_golden.py, docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md
"""Phase A.2 — prove the structural oracle is STABLE across churn AND still bites on loss.

Both properties are required. A stable oracle that catches nothing is worse than no oracle,
because it certifies safety it never checked. So every stability assertion here is paired with
a loss assertion.

The stability half is measured against REAL day-over-day regenerations taken from git history,
not synthetic strings — an earlier revision asserted normalisation using hand-written inputs
the pipeline never emits, and stayed green while 23 of 29 artifacts still drifted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import capture_golden as cg  # noqa: E402

# Two consecutive daily auto-commits — the real churn that killed the byte-oracle.
DAY_A, DAY_B = "8b1f077c", "400ca5bb"


def _at(rev: str, path: str) -> str | None:
    r = subprocess.run(
        ["git", "-C", str(cg.FABRIK_ROOT), "show", f"{rev}:{path}"],
        capture_output=True,
        text=True,
    )
    return r.stdout if r.returncode == 0 else None


@pytest.fixture(autouse=True)
def _require_snapshot():
    if not cg.MANIFEST.exists():
        pytest.skip("no structure.json — run capture_golden.py --snapshot first")


# ── stability ────────────────────────────────────────────────────────────────
def test_verify_is_green_on_the_live_tree():
    assert cg.verify() == 0, "the oracle reports drift on an unmodified tree"


def test_structure_survives_a_real_daily_regeneration():
    """THE test the byte-oracle failed — real artifacts from two consecutive daily commits."""
    drifted = []
    for rel in cg.SELECTION_DOCS + [cg.CAPABILITIES_DOC]:
        a, b = _at(DAY_A, rel), _at(DAY_B, rel)
        if not a or not b:
            continue
        if rel == cg.CAPABILITIES_DOC:
            a = cg.strip_marker(a, "EMBEDDING_CATALOG")
            b = cg.strip_marker(b, "EMBEDDING_CATALOG")
        if cg.md_shape(a) != cg.md_shape(b):
            drifted.append(rel)
    assert not drifted, f"structure churns day-over-day (the byte-oracle's fatal flaw): {drifted}"


def test_a_new_provider_section_is_not_drift():
    """Catalog growth is not lost functionality. Measured: 66 -> 68 `###` headings in one day."""
    base = "# Doc\n\n## Providers\n\n### OPENAI (87 models)\n\n### GOOGLE (30 models)\n"
    grown = base + "\n### DEEPGRAM (2 models)\n\n### ASSEMBLYAI (1 models)\n"
    assert cg.md_shape(base) == cg.md_shape(grown)


def test_changing_values_is_not_drift():
    """Scores, counts and prices move every night; none of them is a contract change."""
    a = "# D\n\n## S\n\n| model | score | n |\n|---|---|---|\n| glm | 2.55 | 67 |\n"
    b = "# D\n\n## S\n\n| model | score | n |\n|---|---|---|\n| glm | 2.57 | 75 |\n"
    assert cg.md_shape(a) == cg.md_shape(b)


# ── it must still bite ───────────────────────────────────────────────────────
def test_a_lost_table_column_is_drift():
    """Losing a column is exactly what 'functionality lost' looks like."""
    a = "# D\n\n## S\n\n| model | score | cost |\n|---|---|---|\n| x | 1 | 2 |\n"
    b = "# D\n\n## S\n\n| model | score |\n|---|---|\n| x | 1 |\n"
    assert cg.md_shape(a) != cg.md_shape(b)


def test_a_lost_section_is_drift():
    a = "# D\n\n## Rankings\n\n## Methodology\n"
    b = "# D\n\n## Rankings\n"
    assert cg.md_shape(a) != cg.md_shape(b)


def test_a_lost_json_field_is_drift():
    a = json.dumps({"models": [{"id": "x", "score": 1, "provider": "p"}]})
    b = json.dumps({"models": [{"id": "x", "score": 1}]})
    assert cg.json_shape(a) != cg.json_shape(b)


def test_an_artifact_that_stops_being_produced_is_drift(monkeypatch):
    """The headline failure: the extraction silently stops emitting a consumed artifact."""
    real = cg.observe

    def gone():
        o = real()
        o["artifacts"]["docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"] = {
            "present": False,
            "reason": "MISSING",
        }
        return o

    monkeypatch.setattr(cg, "observe", gone)
    assert cg.verify() == 1, "an artifact that stopped being produced must RED the oracle"


def test_a_marker_that_stops_being_injected_is_drift(monkeypatch):
    real = cg.observe

    def gone():
        o = real()
        for k in list(o["markers"]):
            if "EMBEDDING_WINNERS" in k:
                o["markers"][k] = False
        return o

    monkeypatch.setattr(cg, "observe", gone)
    assert cg.verify() == 1, "a marker that stopped being injected must RED the oracle"


def test_a_shape_change_is_drift(monkeypatch):
    real = cg.observe

    def mutated():
        o = real()
        o["artifacts"]["docs/reference/kilo/TTS_SELECTION.md"]["shape"] = {"skeleton": ["# X"]}
        return o

    monkeypatch.setattr(cg, "observe", mutated)
    assert cg.verify() == 1


# ── environment / hygiene ────────────────────────────────────────────────────
def test_gitignored_artifacts_do_not_red_a_fresh_clone(monkeypatch):
    """4 consumed artifacts are gitignored; treating their absence as drift would make the
    oracle permanently RED on every fresh clone, CI run and worktree."""
    real = cg.observe

    def fresh_clone():
        o = real()
        o["artifacts"]["scripts/kilo_47_agents_final.json"] = {
            "present": False,
            "reason": "absent-by-gitignore",
        }
        return o

    monkeypatch.setattr(cg, "observe", fresh_clone)
    assert cg.verify() == 0, "a gitignored artifact's absence must not be reported as drift"


def test_bare_invocation_refuses_to_refreeze():
    """A destructive default on an oracle is a trap: hit drift, re-run 'the gate', bless it."""
    r = subprocess.run(
        [sys.executable, str(cg.__file__)], capture_output=True, text=True, cwd=str(cg.FABRIK_ROOT)
    )
    assert r.returncode == 2 and "--snapshot" in r.stderr


def test_db_queries_come_from_the_module_not_prose():
    """Read live, so it cannot drift into fiction — and it must be the INTERPOLATED query."""
    q = cg._db_queries()
    fw = q["rank_task_subagents.flywheel"]
    assert "subagent_runs" in fw, "not interpolated — a source regex would give `FROM {TABLE}`"
    assert "INTERVAL" in fw and "HAVING" in fw, "the real window/HAVING clauses are missing"


def test_db_queries_survive_a_missing_engine():
    """Phase E deletes the engine scripts while RETAINING tests/golden/** — the oracle must
    not crash afterwards."""
    real_dir = cg.SCRIPT_DIR
    try:
        cg.SCRIPT_DIR = Path("/nonexistent-engine-dir")
        q = cg._db_queries()
        assert any("UNAVAILABLE" in v for v in q.values())
    finally:
        cg.SCRIPT_DIR = real_dir


def test_hand_authored_docs_are_excluded():
    frozen = set(cg.SELECTION_DOCS + cg.REGISTRY_JSONS + cg.OTHER_OUTPUTS)
    assert not any("AGGREGATOR_ROADMAP" in f or "BENCHMARK_SOURCES" in f for f in frozen)
    assert not any("kilo_all_models" in f for f in frozen), (
        "produced by the repo-root kilo_model_sync.py — it never moves with the engine"
    )
