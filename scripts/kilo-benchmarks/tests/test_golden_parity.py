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
import re
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
def test_verify_is_green_on_the_live_tree(monkeypatch):
    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    assert cg.verify() == 0, "the oracle reports drift on an unmodified tree"


def test_structure_survives_a_real_daily_regeneration():
    """THE test the byte-oracle failed — real artifacts from two consecutive daily commits."""
    drifted, compared = [], 0
    for rel in cg.SELECTION_DOCS + [cg.CAPABILITIES_DOC]:
        a, b = _at(DAY_A, rel), _at(DAY_B, rel)
        if not a or not b:
            continue
        compared += 1
        if rel == cg.CAPABILITIES_DOC:
            a = cg.strip_marker(a, "EMBEDDING_CATALOG")
            b = cg.strip_marker(b, "EMBEDDING_CATALOG")
        if not cg.shapes_equal(cg.md_shape(a), cg.md_shape(b)):
            drifted.append(rel)
    # Without this the test passes VACUOUSLY the moment the shas stop resolving — a shallow
    # clone, or Phase B copying tests/ into the engine repo (its explicit design goal). That
    # is the same silently-green pattern this test was written to replace.
    assert compared >= 6, f"only {compared} real day-over-day pairs resolved — test is vacuous"
    assert not drifted, f"structure churns day-over-day (the byte-oracle's fatal flaw): {drifted}"


def test_a_new_provider_section_is_not_drift():
    """Catalog growth is not lost functionality. Measured: 66 -> 68 `###` headings in one day."""
    base = "# Doc\n\n## Providers\n\n### OPENAI (87 models)\n\n### GOOGLE (30 models)\n"
    grown = base + "\n### DEEPGRAM (2 models)\n\n### ASSEMBLYAI (1 models)\n"
    assert cg.shapes_equal(cg.md_shape(base), cg.md_shape(grown))


def test_changing_values_is_not_drift():
    """Scores, counts and prices move every night; none of them is a contract change."""
    a = "# D\n\n## S\n\n| model | score | n |\n|---|---|---|\n| glm | 2.55 | 67 |\n"
    b = "# D\n\n## S\n\n| model | score | n |\n|---|---|---|\n| glm | 2.57 | 75 |\n"
    assert cg.shapes_equal(cg.md_shape(a), cg.md_shape(b))


# ── it must still bite ───────────────────────────────────────────────────────
def test_a_lost_table_column_is_drift():
    """Losing a column is exactly what 'functionality lost' looks like."""
    a = "# D\n\n## S\n\n| model | score | cost |\n|---|---|---|\n| x | 1 | 2 |\n"
    b = "# D\n\n## S\n\n| model | score |\n|---|---|\n| x | 1 |\n"
    assert not cg.shapes_equal(cg.md_shape(a), cg.md_shape(b))


def test_a_lost_section_is_drift():
    a = "# D\n\n## Rankings\n\n## Methodology\n"
    b = "# D\n\n## Rankings\n"
    assert not cg.shapes_equal(cg.md_shape(a), cg.md_shape(b))


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

    # Explicit: once daily_refresh.sh exports this on the pipeline host, an inherited value
    # would red this test (and test_verify_is_green_on_the_live_tree) for environmental
    # reasons. The paired loss test sets it deliberately.
    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
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


def test_db_queries_survive_a_missing_engine(monkeypatch):
    """Phase E deletes the engine scripts while RETAINING tests/golden/** — the oracle must
    not crash afterwards.

    Asserts the FLYWHEEL key specifically. `any("UNAVAILABLE" ...)` was satisfied by the two
    file-read guards alone, so it stayed green even with the import guard removed — it did
    not catch its own revert. `rank_task_subagents` is also evicted from sys.modules, since a
    full-suite run leaves it imported and the import then succeeds regardless of SCRIPT_DIR.
    """
    monkeypatch.setattr(cg, "SCRIPT_DIR", Path("/nonexistent-engine-dir"))
    monkeypatch.delitem(sys.modules, "rank_task_subagents", raising=False)
    # Reproduce the condition deterministically instead of depending on test ORDER: sibling
    # test modules put the real engine dir on sys.path, which is what let a bare
    # `import rank_task_subagents` succeed while SCRIPT_DIR pointed nowhere. Without this the
    # revert is only caught in a full-suite run and passes when the test runs alone.
    monkeypatch.syspath_prepend(str(cg.FABRIK_ROOT / "scripts/kilo-benchmarks"))
    before = list(sys.path)
    q = cg._db_queries()
    assert "UNAVAILABLE" in q.get("rank_task_subagents.flywheel", ""), (
        "the import guard is not what produced the fallback — this test cannot catch its revert"
    )
    assert sys.path == before, "_db_queries leaked a bogus dir onto sys.path for the session"


def test_hand_authored_docs_are_excluded():
    frozen = set(cg.SELECTION_DOCS + cg.REGISTRY_JSONS + cg.OTHER_OUTPUTS)
    assert not any("AGGREGATOR_ROADMAP" in f or "BENCHMARK_SOURCES" in f for f in frozen)
    assert not any("kilo_all_models" in f for f in frozen), (
        "produced by the repo-root kilo_model_sync.py — it never moves with the engine"
    )


def test_gutted_tables_are_drift_even_with_perfect_structure():
    """Total gutting: every data row deleted, headings and column headers intact.

    This is the EASY half. The realistic failure is partial — only the routing tables
    emptied — which a doc-wide row count misses entirely; that is covered by
    test_partial_gutting_of_only_the_routing_tables_is_drift, and it is the case that
    actually drove magnitudes from a scalar to a per-table map.

    Deleting every data row while keeping headings and column headers left skeleton and
    columns byte-identical (measured: TASK_SUBAGENT_SELECTION.md 181 rows -> 24). Without a
    magnitude invariant the oracle would certify "no functionality lost" for an extraction
    that emitted a correct-looking husk with zero data — the most likely extraction failure
    of all (engine copied, DB wiring wrong).
    """
    import re as _re

    doc = cg.FABRIK_ROOT / "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
    if not doc.exists():
        pytest.skip("selection doc absent")
    real = doc.read_text()
    if "AGGREGATION FAILED" in real:
        pytest.skip("selection doc is the failure stub — nothing to gut (pipeline is broken)")
    gutted = _re.sub(r"(\|[^\n]*\|\n\|[\s:|-]+\|\n)(?:\|[^\n]*\|\n)+", r"\1", real)
    assert not cg.shapes_equal(cg.md_shape(real), cg.md_shape(gutted)), (
        "a doc stripped of every data row still matches — the oracle is too weak"
    )


def test_an_entirely_empty_table_is_drift():
    a = "# D\n\n## S\n\n| m | s |\n|---|---|\n| x | 1 |\n| y | 2 |\n"
    b = "# D\n\n## S\n\n| m | s |\n|---|---|\n"
    assert not cg.shapes_equal(cg.md_shape(a), cg.md_shape(b)), "an emptied table must be drift"
    assert cg.md_shape(b)["magnitudes"] == {"m|s": 0}


def _rows(n: int) -> str:
    return "# D\n\n## S\n\n| m | s |\n|---|---|\n" + "| x | 1 |\n" * n


def test_magnitude_tolerates_ordinary_growth():
    """Churn moves counts ~8% (n_total 274 -> 296); the band must not react to that."""
    assert cg.shapes_equal(cg.md_shape(_rows(100)), cg.md_shape(_rows(108)))  # +8%, real churn
    assert cg.shapes_equal(cg.md_shape(_rows(100)), cg.md_shape(_rows(130)))  # +30%
    assert cg.shapes_equal(cg.md_shape(_rows(100)), cg.md_shape(_rows(70)))  # -30% shrink
    # Growth stays cheap on purpose: Phase A freezes the contract for the whole B->E
    # extraction, and models_browser.html grew 1.41x in 26 days, so any tight ceiling would
    # red on pure catalog growth. See test_large_collection_growth_survives_a_long_extraction.


def test_magnitude_catches_an_order_of_magnitude_loss():
    assert not cg.shapes_equal(cg.md_shape(_rows(180)), cg.md_shape(_rows(20)))


def test_html_payload_collapse_is_drift():
    """The browser page is 3.8MB of embedded model data; the skeleton is 95KB of it.

    Without a row count the catch is incidental — it only fires because the payload happens
    to contain `id="` substrings. Assert the DESIGNED invariant instead.
    """
    page = cg.FABRIK_ROOT / "scripts/kilo-benchmarks/models_browser.html"
    if not page.exists():
        pytest.skip("models_browser.html is gitignored and absent in this tree")
    real = page.read_text(errors="replace")
    m = re.search(r'(<script[^>]*id="payload"[^>]*>)(.*?)(</script>)', real, re.S)
    assert m, "the page no longer carries an id=payload blob — html_shape must be re-derived"
    blanked = real[: m.start(2)] + "[]" + real[m.end(2) :]
    assert not cg.shapes_equal(cg.html_shape(real), cg.html_shape(blanked)), (
        "emptying the 3.7MB model payload left the shape identical — the page renders from "
        "this blob, not from markup, so no markup-derived field can see the data loss"
    )


def test_html_row_growth_is_not_drift():
    """New models land as new rows every night — growth must not red the oracle."""

    def page(n: int) -> str:
        return (
            '<html><script id="payload">'
            + "x" * n
            + "</script><table>"
            + "<tr><td>x</td></tr>" * 100
            + "</table></html>"
        )

    assert cg.shapes_equal(cg.html_shape(page(10_000)), cg.html_shape(page(13_000)))


# ── the invariants must be ON, not merely present ────────────────────────────
def test_a_stale_golden_refuses_to_verify_instead_of_passing(monkeypatch, tmp_path):
    """A golden frozen by an older observer lacks the newer invariants.

    `shapes_equal` skips a magnitude side it cannot find, so an old golden made verify()
    print "OK — N contract elements intact" for a doc gutted to zero rows: the check was
    silently OFF while claiming to be on. Worse than no oracle. Must exit 2, not 0.
    """
    old = json.loads(cg.MANIFEST.read_text())
    old["oracle_version"] = cg.ORACLE_VERSION - 1
    stale = tmp_path / "structure.json"
    stale.write_text(json.dumps(old))
    monkeypatch.setattr(cg, "MANIFEST", stale)
    assert cg.verify() == 2, "a stale golden must refuse to run, never report OK"


def test_a_changed_db_query_is_drift(monkeypatch):
    """15 SQL queries were frozen into the golden and compared by nothing.

    Changing WINDOW_DAYS, MIN_RUNS, the HAVING clause or the table name left the oracle
    green — defeating the module's stated purpose (read live so it cannot drift into fiction).
    """
    real = cg.observe

    def tampered():
        o = real()
        k = next(iter(o["db_queries"]))
        o["db_queries"][k] = "SELECT 1 -- rewritten"
        return o

    monkeypatch.setattr(cg, "observe", tampered)
    assert cg.verify() == 1, "a rewritten consumer query must RED the oracle"


def test_gitignored_artifact_loss_is_drift_on_the_pipeline_host(monkeypatch):
    """The PAIRED loss assertion the fresh-clone tolerance was missing.

    4 of 13 artifacts are gitignored, so `absent-by-gitignore` exempted 31% of the inventory
    from "NO LONGER PRODUCED" — precisely the headline class the oracle exists to catch. On
    the box that RUNS the pipeline, absence means it stopped being produced.
    """
    real = cg.observe

    def stopped():
        o = real()
        o["artifacts"]["scripts/kilo_47_agents_final.json"] = {
            "present": False,
            "reason": "absent-by-gitignore",
        }
        return o

    monkeypatch.setattr(cg, "observe", stopped)
    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    assert cg.verify() == 0, "a fresh clone must stay green"
    monkeypatch.setenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", "1")
    assert cg.verify() == 1, "on the pipeline host a gitignored artifact's loss IS drift"


def test_partial_gutting_of_only_the_routing_tables_is_drift():
    """The v1 magnitude invariant's real failure, closed.

    A doc-wide row count is nearly useless here: the routing tables `pick_models` consumes
    are 35 of 157 rows, and the tables labelled "display only; not parsed for routing" are
    122. Emptying EVERY routing table left 78% of rows — inside any doc-wide tolerance — so
    the husk that breaks routing passed green.
    """
    doc = cg.FABRIK_ROOT / "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
    if not doc.exists() or "AGGREGATION FAILED" in doc.read_text():
        pytest.skip("selection doc absent or is the failure stub")
    real = doc.read_text()
    cut = real.find("## Full review benchmark results")
    assert cut > 0, "the display-only section moved — re-derive this test's split point"
    gutted = (
        re.sub(r"(\|[^\n]*\|\n\|[\s:|-]+\|\n)(?:\|[^\n]*\|\n)+", r"\1", real[:cut]) + real[cut:]
    )
    assert not cg.shapes_equal(cg.md_shape(real), cg.md_shape(gutted)), (
        "every routing table emptied but the oracle is green — magnitudes are not per-table"
    )


def test_json_list_truncation_is_drift():
    """`walk` renders a list as one element regardless of length, so shrinking every
    collection (a registry going 40 assignments -> 13) was byte-identical in the schema.
    Dropping a whole key was caught; shrinking every collection was not."""
    a = json.dumps({"roles": {"coding": [{"m": "x"}] * 40}})
    b = json.dumps({"roles": {"coding": [{"m": "x"}] * 13}})
    assert not cg.shapes_equal(cg.json_shape(a), cg.json_shape(b))
    grown = json.dumps({"roles": {"coding": [{"m": "x"}] * 44}})
    assert cg.shapes_equal(cg.json_shape(a), cg.json_shape(grown)), "growth is not drift"


# ── round-4 fixes ────────────────────────────────────────────────────────────
def test_tiny_collections_tolerate_ordinary_churn():
    """A ratio is meaningless on a 1-row table, and 20+ frozen collections are tiny.

    CANDIDATE_SIGNUPS.md is frozen at 1 row and has already halved 2 -> 1 in-window; the
    natural end-state of a signup queue is 0. Under a [0.5, 4.0] band an emptied queue reads
    as COLLAPSE and a 5th candidate as FAN-OUT — both ordinary churn. A false-red oracle gets
    ignored, which is the failure mode this whole safety net exists to avoid.
    """
    one, five = {"t": 1}, {"t": 5}
    assert cg.magnitudes_ok(one, five)[0], "growth on a tiny collection must not be drift"
    assert cg.magnitudes_ok({"t": 3}, {"t": 1})[0], "3 -> 1 on a tiny collection is churn"
    # ...but total loss is unambiguous at any size.
    assert not cg.magnitudes_ok(one, {"t": 0})[0], "a tiny collection emptying IS drift"


def test_large_collection_growth_survives_a_long_extraction():
    """Phase A freezes the contract for the whole B->E extraction.

    models_browser.html's row count grew 1.41x in 26 days, so a 4x ceiling would trip on pure
    catalog growth in ~104 days. Growth must stay cheap; collapse must stay caught.
    """
    assert cg.magnitudes_ok({"t": 157}, {"t": 600})[0], "pure catalog growth is not drift"
    assert not cg.magnitudes_ok({"t": 157}, {"t": 20})[0], "an 87% collapse is still drift"


def test_adjacent_tables_are_keyed_separately():
    """A table not separated by a blank line swallowed its neighbour's header + rows.

    The count was inflated by 2 + the neighbour's rows AND the neighbour was never keyed, so
    gutting the second table was silently green.
    """
    doc = "# D\n\n## S\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| c | d |\n|---|---|\n| 3 | 4 |\n"
    shape = cg.md_shape(doc)
    assert set(shape["magnitudes"]) == {"a|b", "c|d"}, shape["magnitudes"]
    assert shape["magnitudes"] == {"a|b": 1, "c|d": 1}
    gutted = "# D\n\n## S\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| c | d |\n|---|---|\n"
    assert not cg.shapes_equal(shape, cg.md_shape(gutted)), "second table gutted, still green"


def test_magnitude_keys_match_the_table_inventory_on_every_real_artifact():
    """The structural invariant behind the fix: one magnitude key per column contract."""
    for rel in cg.SELECTION_DOCS + [cg.CAPABILITIES_DOC]:
        text = cg._read(rel)
        if text is None:
            continue
        shape = cg.md_shape(text)
        cols = {"|".join(c) for c in shape["table_columns"]}
        assert set(shape["magnitudes"]) == cols, f"{rel}: keyset mismatch"


def test_verify_names_the_collection_that_collapsed(monkeypatch, capsys):
    """A generic "SHAPE CHANGED" cannot distinguish a data collapse from a renderer edit."""
    real = cg.observe

    def collapsed():
        o = real()
        a = o["artifacts"]["docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"]
        a["shape"]["magnitudes"] = dict.fromkeys(a["shape"]["magnitudes"], 0)
        return o

    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    monkeypatch.setattr(cg, "observe", collapsed)
    assert cg.verify() == 1
    err = capsys.readouterr().err
    assert "EMPTIED" in err or "COLLAPSE" in err, f"reason not reported: {err}"


def test_an_excised_engine_does_not_produce_spurious_query_drift(monkeypatch):
    """Phase E deletes the engine while RETAINING tests/golden/**.

    The tolerance guard read the GOLDEN side, so it could never fire in normal operation and,
    when it did, tolerated any observed value. Post-excise the oracle emitted 15 spurious
    QUERY CHANGED/GONE lines instead of staying quiet.
    """
    real = cg.observe

    def excised():
        o = real()
        o["db_queries"] = {"rank_task_subagents.flywheel": "<UNAVAILABLE: FileNotFoundError>"}
        return o

    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    monkeypatch.setattr(cg, "observe", excised)
    assert cg.verify() == 0, "an excised engine must not read as consumer-query drift"


def test_a_genuinely_rewritten_query_is_still_drift(monkeypatch):
    """The mirror of the tolerance above — it must not become a blanket exemption."""
    real = cg.observe

    def tampered():
        o = real()
        k = next(iter(o["db_queries"]))
        o["db_queries"][k] = "SELECT 1 -- rewritten"
        return o

    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    monkeypatch.setattr(cg, "observe", tampered)
    assert cg.verify() == 1


def test_the_oracle_has_a_production_caller():
    """The fix that made every other fix real.

    verify() ran ONLY under pytest, in permissive mode, so ORACLE_REQUIRE_LOCAL_ARTIFACTS was
    set nowhere and the 4 gitignored artifacts stayed exempt from "NO LONGER PRODUCED" in
    every real execution.
    """
    sh = (cg.SCRIPT_DIR / "daily_refresh.sh").read_text()
    assert "capture_golden.py" in sh, "the oracle has no production caller"
    line = next(
        ln
        for ln in sh.splitlines()
        if "capture_golden.py" in ln and "--verify" in ln and not ln.lstrip().startswith("#")
    )
    assert "ORACLE_REQUIRE_LOCAL_ARTIFACTS=1" in line, (
        "the pipeline host must run the oracle STRICT, or gitignored artifact loss is invisible"
    )
