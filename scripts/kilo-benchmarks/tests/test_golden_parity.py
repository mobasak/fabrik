# AFTER-EDIT: capture_golden.py, docs/development/plans/2026-07-26-plan-1-ai-model-catalog-extraction.md
"""Phase A.2 — prove the golden harness reproduces live output AND bites on divergence.

Green-by-construction on a clean tree is worthless on its own: the golden IS the live output,
so a passing test proves nothing until you show it goes RED on a real difference. Every
assertion here is paired with its mutation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import capture_golden as cg  # noqa: E402


@pytest.fixture(autouse=True)
def _require_snapshot():
    if not cg.MANIFEST.exists():
        pytest.skip("no golden manifest — run capture_golden.py --snapshot first")


def test_selection_docs_match_current():
    """The oracle reproduces live output on a clean tree."""
    assert cg.verify() == 0, "golden verify reported drift on an unmutated tree"


def test_verify_goes_red_on_a_mutated_artifact(monkeypatch):
    """THE PROOF: change one byte of a hashed artifact and verify must FAIL."""
    real = cg.snapshot_hashes

    def mutated():
        h = dict(real())
        key = "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
        assert key in h, "expected the task-selection doc in the live hash set"
        h[key] = "0" * 64
        return h

    monkeypatch.setattr(cg, "snapshot_hashes", mutated)
    assert cg.verify() == 1, "verify stayed GREEN on a mutated artifact — the oracle does not bite"


def test_verify_reports_a_missing_artifact(monkeypatch):
    """An artifact that vanishes is drift, not a silent skip."""
    real = cg.snapshot_hashes

    def dropped():
        h = dict(real())
        h.pop("docs/reference/kilo/TTS_SELECTION.md", None)
        return h

    monkeypatch.setattr(cg, "snapshot_hashes", dropped)
    assert cg.verify() == 1, "a missing consumed artifact must register as drift"


def test_volatile_date_is_normalized_not_drift():
    """A changed 'Last refresh:' / 'last-refreshed:' date is NOT contract drift.

    These artifacts are rewritten daily by cron with a date inside the frozen region. Without
    normalisation the first verify after midnight reports drift on ~9 docs and 11 marker
    blocks for reasons unrelated to the extraction.
    """
    a = "Last refresh: 2026-08-12\nrows: 5\n"
    b = "Last refresh: 2026-09-01\nrows: 5\n"
    assert cg.sha(a) == cg.sha(b), (
        "the volatile date leaks into the hash — verify will false-flag daily"
    )

    c = "<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-08-12 -->x"
    d = "<!-- GATEWAY_COUNTS:START — last-refreshed: 2026-12-31 -->x"
    assert cg.sha(c) == cg.sha(d), "marker-opener date leaks into the hash"


def test_real_content_change_is_still_drift():
    """The mirror of normalisation: a real change must NOT be normalised away."""
    a = "Last refresh: 2026-08-12\nrows: 5\n"
    b = "Last refresh: 2026-08-12\nrows: 6\n"
    assert cg.sha(a) != cg.sha(b), "normalisation swallowed a real content change"


def test_capabilities_golden_strips_the_injected_block():
    """KILO_MODEL_CAPABILITIES is hashed as the generator's BASE, without EMBEDDING_CATALOG.

    The generator writes the whole file; embedding_export_markdown injects EMBEDDING_CATALOG
    into the live file afterwards. The decoupled engine will emit only the base, so the
    whole-file golden must be the base or B.3 parity false-flags on every run.
    """
    text = "head\n<!-- EMBEDDING_CATALOG:START (auto) -->body<!-- EMBEDDING_CATALOG:END -->\ntail\n"
    stripped = cg.strip_marker(text, "EMBEDDING_CATALOG")
    assert "body" not in stripped and "head" in stripped and "tail" in stripped


def test_hand_authored_docs_are_excluded():
    """AGGREGATOR_ROADMAP / BENCHMARK_SOURCES have no generator — freezing them would report
    a human's edit as extraction drift."""
    frozen = set(cg.SELECTION_DOCS)
    assert not any("AGGREGATOR_ROADMAP" in f for f in frozen)
    assert not any("BENCHMARK_SOURCES" in f for f in frozen)


def test_db_queries_are_captured():
    """The contract covers the query shape, not just rendered output (spec Phase-0)."""
    assert cg.DB_QUERIES.exists(), "db_queries.json missing — the spec's Phase-0 capture"
    q = json.loads(cg.DB_QUERIES.read_text())
    assert q, "db_queries.json is empty"
    assert any("subagent_runs" in v for v in q.values()), "the flywheel query is not recorded"


def test_date_bump_over_the_real_corpus_produces_zero_drift():
    """The test the synthetic version should have been.

    An earlier revision asserted normalisation using hand-written strings the pipeline never
    emits ("Last refresh: ..." at line-start, and a marker OPENER — which extract_block
    excludes by construction). Both passed while 23 of 29 real goldens still embedded a date,
    so the oracle would have gone RED on the next cron run. This drives the REAL artifacts.
    """
    import re as _re

    def bump(text: str) -> str:
        text = _re.sub(r"\d{4}-\d{2}-\d{2}", "2099-12-31", text)
        return _re.sub(r"\d{2}:\d{2}:\d{2}(\.\d+)?", "23:59:59.999999", text)

    still = []
    for rel in cg.SELECTION_DOCS + cg.REGISTRY_JSONS + cg.OTHER_ENGINE_OUTPUTS:
        f = cg.FABRIK_ROOT / rel
        if not f.exists():
            continue
        raw = f.read_text(encoding="utf-8", errors="replace")
        if cg.sha(raw) != cg.sha(bump(raw)):
            still.append(rel)
    for host in cg.ai_pack_hosts():
        text = host.read_text(encoding="utf-8")
        for marker in cg.AI_PACK_MARKERS:
            body = cg.extract_block(text, marker)
            if body is not None and cg.sha(body) != cg.sha(bump(body)):
                still.append(f"{host.name}.{marker}")
    assert not still, f"these REAL artifacts still drift on a pure date bump: {still}"


def test_bare_invocation_refuses_to_refreeze():
    """A destructive default on an oracle is a trap: hit DRIFT, re-run 'the gate', and the
    drifted state gets blessed as the new contract with exit 0."""
    import subprocess

    r = subprocess.run(
        [__import__("sys").executable, str(cg.__file__)],
        capture_output=True,
        text=True,
        cwd=str(cg.FABRIK_ROOT),
    )
    assert r.returncode == 2, "a bare invocation must REFUSE, not silently re-freeze"
    assert "--snapshot" in r.stderr


def test_kilo_all_models_is_not_frozen():
    """It is produced by the repo-root kilo_model_sync.py, which does not move with the
    engine — freezing it would put a permanently unmatchable key in the contract."""
    assert not any("kilo_all_models" in f for f in cg.REGISTRY_JSONS)


def test_db_queries_match_source_not_prose():
    """db_queries.json is extracted from source, so it cannot drift into fiction."""
    import json as _json

    q = _json.loads(cg.DB_QUERIES.read_text())
    fw = q.get("rank_task_subagents.flywheel", "")
    assert "INTERVAL" in fw, "the 90-day window is missing — this is not the real query"
    assert "HAVING" in fw, "the MIN_RUNS HAVING clause is missing"
    assert "success_rate" in fw, "the success_rate expression is missing"
