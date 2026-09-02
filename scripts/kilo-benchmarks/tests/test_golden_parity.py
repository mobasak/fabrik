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
import tempfile
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
    """The block and its fences are gone entirely — distinct from an EMPTIED payload.

    The observer records `None` for an absent block. This test previously set `False`, which
    once markers became magnitudes compared equal to 0 and so exercised the EMPTIED branch
    instead: the test's name was false and the NO-LONGER-INJECTED branch was unpinned
    (verified — deleting that branch left the entire suite green).
    """
    real = cg.observe

    def gone():
        o = real()
        for k in list(o["markers"]):
            if "EMBEDDING_WINNERS" in k:
                o["markers"][k] = None
        return o

    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
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
    assert cg.md_shape(b)["magnitudes"][f"{cg.SECTION_KEY} S :: m|s"] == 0


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
    assert cg.magnitudes_ok({"t": 1}, {"t": 5})[0], "growth on a tiny collection is not drift"
    # One item of churn is cheap at every size...
    assert cg.magnitudes_ok({"t": 3}, {"t": 2})[0], "3 -> 2 is one item of churn"
    # ...but losing MOST of a small collection is not. A flat floor tolerated 3 -> 1, which is
    # the registry-truncation case json_shape exists to catch.
    assert not cg.magnitudes_ok({"t": 3}, {"t": 1})[0], "3 -> 1 must be drift"
    assert not cg.magnitudes_ok({"t": 2}, {"t": 0})[0], "2 -> 0 must be drift"
    # A collection emptying ENTIRELY is drift at every size — including n=1, which the
    # `min(wn-1, ...)` form silently exempted for 25 collections.
    assert not cg.magnitudes_ok({"t": 1}, {"t": 0})[0], "1 -> 0 is a total loss"
    # ...unless the artifact is a queue whose end-state is empty.
    assert cg.magnitudes_ok({"t": 1}, {"t": 0}, may_empty=True)[0]


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
    # 3 rows each: enough that emptying one is unambiguous (a 1-row collection emptying is
    # deliberately tolerated — see test_tiny_collections_tolerate_ordinary_churn).
    first = "| a | b |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n| 5 | 6 |\n"
    second = "| c | d |\n|---|---|\n| 7 | 8 |\n| 9 | 0 |\n| 1 | 1 |\n"
    doc = "# D\n\n## S\n\n" + first + second
    shape = cg.md_shape(doc)
    rows = {k: v for k, v in shape["magnitudes"].items() if k.startswith(cg.SECTION_KEY)}
    assert rows == {
        f"{cg.SECTION_KEY} S :: a|b": 3,
        f"{cg.SECTION_KEY} S :: c|d": 3,
    }, shape["magnitudes"]
    gutted = "# D\n\n## S\n\n" + first + "| c | d |\n|---|---|\n"
    assert not cg.shapes_equal(shape, cg.md_shape(gutted)), "second table gutted, still green"


def test_magnitude_keys_match_the_table_inventory_on_every_real_artifact():
    """The structural invariant behind the fix: one magnitude key per column contract."""
    for rel in cg.SELECTION_DOCS + [cg.CAPABILITIES_DOC]:
        text = cg._read(rel)
        if text is None:
            continue
        shape = cg.md_shape(text)
        cols = {"|".join(c) for c in shape["table_columns"]}
        # Every column contract must have a TABLES count, and every row-count key must end in
        # a known contract. (Keys are section-scoped, so they are a superset of the contracts.)
        for suffix in (":: TABLES", ":: ROWS"):
            assert {f"{c} {suffix}" for c in cols} <= set(shape["magnitudes"]), (
                f"{rel}: a column contract is missing its {suffix} aggregate"
            )
        for key in shape["magnitudes"]:
            assert any(key.endswith(f":: {c}") or key.startswith(f"{c} ::") for c in cols), (
                f"{rel}: magnitude key {key!r} matches no column contract"
            )


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
        # Every family degrades together when the engine dir is gone.
        o["db_queries"] = dict.fromkeys(o["db_queries"], "<UNAVAILABLE: FileNotFoundError>")
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


# ── round-5 fixes ────────────────────────────────────────────────────────────
def test_routing_sections_are_keyed_separately_from_each_other():
    """All six `### <task_type>` shortlists share ONE column contract.

    Keyed by contract alone they summed into a single 21-row bucket, so four of the six
    sections pick_models consumes could be emptied while the total stayed above threshold —
    the oracle printed OK while every vendored copy fell back to the baked-in _TABLE.
    """
    doc = cg.FABRIK_ROOT / "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
    if not doc.exists() or "AGGREGATION FAILED" in doc.read_text():
        pytest.skip("selection doc absent or is the failure stub")
    real = doc.read_text()
    keys = [
        k
        for k in cg.md_shape(real)["magnitudes"]
        if "shrunk_q" in k and k.startswith(cg.SECTION_KEY)
    ]
    assert len(keys) >= 6, f"routing sections collapsed into {len(keys)} key(s): {keys}"

    gutted, section, in_sep = [], None, False
    for ln in real.splitlines(keepends=True):
        head = re.match(r"^###\s+(\w+)", ln)
        if head:
            section, in_sep = head.group(1), False
        if re.match(r"^\|[\s:|-]*-{3,}", ln):
            in_sep = True
            gutted.append(ln)
            continue
        if in_sep and section in {"plan", "spec", "research", "review"} and ln.startswith("|"):
            continue
        if not ln.startswith("|"):
            in_sep = False
        gutted.append(ln)
    why = cg.shape_drift(cg.md_shape(real), cg.md_shape("".join(gutted)))
    assert "EMPTIED" in why or "COLLAPSE" in why, (
        f"4 of 6 routing sections emptied but not caught: {why!r}"
    )


def test_wholesale_section_removal_is_caught_by_the_table_count():
    """The complement: sections DELETED rather than emptied.

    A vanished section is tolerated (a delisted provider is catalog churn — measured over 24
    consecutive daily commits, the only key losses were INFLECTION and UNKNOWN). The `::
    TABLES` count per column contract is what stops that tolerance from swallowing a
    wholesale removal.
    """
    six = "# D\n\n" + "".join(
        f"## S{i}\n\n| m | s |\n|---|---|\n| x | 1 |\n| y | 2 |\n\n" for i in range(6)
    )
    two = "# D\n\n" + "".join(
        f"## S{i}\n\n| m | s |\n|---|---|\n| x | 1 |\n| y | 2 |\n\n" for i in range(2)
    )
    assert cg.md_shape(six)["magnitudes"]["m|s :: TABLES"] == 6
    assert not cg.shapes_equal(cg.md_shape(six), cg.md_shape(two))


def test_a_delisted_provider_section_is_not_drift():
    """The false-red this tolerance exists to prevent — measured on real history."""
    keep = "# D\n\n## Providers\n\n### OPENAI (87 models)\n\n| m | s |\n|---|---|\n| x | 1 |\n\n"
    both = keep + "### INFLECTION (2 models)\n\n| m | s |\n|---|---|\n| y | 2 |\n\n"
    assert cg.shapes_equal(cg.md_shape(both), cg.md_shape(keep)), (
        "a delisted provider must not red the oracle"
    )


def test_a_growing_provider_count_does_not_change_the_key():
    """`### OPENAI (87 models)` -> `(88 models)` must not read as a vanished collection."""
    a = "# D\n\n### OPENAI (87 models)\n\n| m | s |\n|---|---|\n| x | 1 |\n"
    b = "# D\n\n### OPENAI (88 models)\n\n| m | s |\n|---|---|\n| x | 1 |\n"
    assert set(cg.md_shape(a)["magnitudes"]) == set(cg.md_shape(b)["magnitudes"])


def test_small_collections_catch_a_truncation_to_one():
    """The flat SMALL_N floor left 41 of 65 collections (63%) protected against nothing.

    kilo_47_agents_final.json's 13 role LISTS are all 1-5 entries, so a floor at 10 re-opened
    the exact case json_shape was written to close (40 assignments -> 13, a 67% loss).
    """
    assert not cg.magnitudes_ok({"r": 3}, {"r": 1})[0], "3 -> 1 must be drift"
    assert not cg.magnitudes_ok({"r": 5}, {"r": 1})[0], "5 -> 1 must be drift"
    assert not cg.magnitudes_ok({"r": 2}, {"r": 0})[0], "2 -> 0 must be drift"
    # ...while a single item of churn stays cheap at every size.
    assert cg.magnitudes_ok({"r": 3}, {"r": 2})[0]
    # 1 -> 0 is a TOTAL loss, not churn: `min(wn-1, ...)` evaluated to 0 at wn=1 and so
    # exempted 25 collections — including the plan/spec routing shortlists and the only data
    # table in STT/TTS/TRANSLATION_SELECTION.md. Only a declared queue may empty.
    assert not cg.magnitudes_ok({"r": 1}, {"r": 0})[0], "1 -> 0 is a total loss"
    assert cg.magnitudes_ok({"r": 1}, {"r": 0}, may_empty=True)[0]


def test_the_fanout_ceiling_is_load_bearing():
    """Round 4 raised the ceiling 4.0 -> 10.0 and nothing tested it, so the claim that every
    fix was proven red-on-revert was false for this one."""
    assert cg.magnitudes_ok({"t": 100}, {"t": 900})[0], "9x growth is tolerated"
    assert not cg.magnitudes_ok({"t": 100}, {"t": 1100})[0], "11x is duplication, not growth"


def test_json_sizes_are_recorded_below_the_schema_depth_cutoff():
    """Round 4 moved the size recording above the depth-3 return; nothing covered it."""
    deep = {"a": {"b": {"c": {"d": list(range(100))}}}}
    small = {"a": {"b": {"c": {"d": list(range(2))}}}}
    assert not cg.shapes_equal(cg.json_shape(json.dumps(deep)), cg.json_shape(json.dumps(small))), (
        "a collection deeper than the schema cutoff is unmeasurable"
    )


def test_one_unavailable_query_does_not_mask_a_loss_in_another_module(monkeypatch):
    """The Phase-E tolerance was a global any(), so ONE unavailable query suppressed
    QUERY GONE for all 15 — including a genuinely dropped query in a module still present."""
    real = cg.observe

    def mixed():
        o = real()
        o["db_queries"]["rank_task_subagents.flywheel"] = "<UNAVAILABLE: FileNotFoundError>"
        for k in list(o["db_queries"]):
            if k.startswith("update_gateway_counts."):
                del o["db_queries"][k]
                break
        return o

    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    monkeypatch.setattr(cg, "observe", mixed)
    assert cg.verify() == 1, "a lost query in a present module was masked by an unrelated one"


def test_strict_mode_actually_runs_green_on_this_box(monkeypatch):
    """Nothing in the suite ever ran the mode production runs — every test delenv'd it."""
    # Strict mode treats the 4 gitignored artifacts' absence as NO LONGER PRODUCED, which is
    # correct on the box that produces them and wrong anywhere else. Phase B copies tests/ into
    # the engine repo, so guard rather than red for environmental reasons there.
    missing = [
        rel for rel in cg.REGISTRY_JSONS + cg.OTHER_OUTPUTS if not (cg.FABRIK_ROOT / rel).exists()
    ]
    if missing:
        pytest.skip(f"not the pipeline host — locally-produced artifacts absent: {missing}")
    monkeypatch.setenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", "1")
    assert cg.verify() == 0, "the production invocation reds on the pipeline host"


def test_the_oracle_runs_before_the_fleet_sync():
    """Ordering is the whole value here.

    Run after `sync_enforcement_to_projects.py`, a marker that stopped being injected or a doc
    collapsed to a husk is pushed to ~46 project repos and THEN alerted. The oracle is
    advisory by design (it must never abort a healthy refresh), so placement is the only lever
    that puts the alert ahead of the blast radius.
    """
    sh = (cg.SCRIPT_DIR / "daily_refresh.sh").read_text()
    lines = sh.splitlines()
    oracle = next(
        i
        for i, ln in enumerate(lines)
        if "capture_golden.py" in ln and "--verify" in ln and not ln.lstrip().startswith("#")
    )
    sync = next(
        i
        for i, ln in enumerate(lines)
        if "sync_enforcement_to_projects.py" in ln and not ln.lstrip().startswith("#")
    )
    assert oracle < sync, (
        f"the oracle runs at line {oracle + 1}, AFTER the fleet sync at {sync + 1} — drift "
        "would be distributed to ~46 repos before the operator is told"
    )


def test_both_entry_points_flush_before_they_rank():
    """A step wired into only ONE entry point is a step that usually does not run.

    `daily_refresh.sh` (06:00 cron) and `wsl_startup_hook.sh` (boot) both take
    /tmp/.fabrik_daily_<UTC>, so whichever wins the day, the other SKIPS ENTIRELY — the hook's
    own comment measured it at 7 boot-wins to 0. `flush_subagent_outboxes.py` was wired into
    daily_refresh alone on 2026-09-02, so on every boot-wins day the ranker published a
    selection doc derived from a ledger whose stranded rows had never been flushed. Both
    scripts must flush, and both must flush BEFORE they rank — flushing after ranking is the
    same defect with a tidier log.
    """
    for name in ("daily_refresh.sh", "wsl_startup_hook.sh"):
        path = (
            cg.SCRIPT_DIR / name
            if name == "daily_refresh.sh"
            else cg.FABRIK_ROOT / "scripts" / name
        )
        lines = [
            ln for ln in path.read_text().splitlines() if not ln.lstrip().startswith("#")
        ]
        flush = [i for i, ln in enumerate(lines) if "flush_subagent_outboxes.py" in ln]
        rank = [i for i, ln in enumerate(lines) if "rank_task_subagents.py" in ln]
        assert flush, (
            f"{name} never runs flush_subagent_outboxes.py — on the days this entry point wins "
            "the shared daily lock, stranded runs are never flushed and the ranker reads an "
            "incomplete ledger"
        )
        assert rank, f"{name} never runs rank_task_subagents.py"
        assert min(flush) < min(rank), (
            f"{name} flushes at line {min(flush) + 1} but ranks at {min(rank) + 1} — the ranker "
            "would publish a selection doc derived from rows the flush was about to add"
        )


def test_a_loose_separator_does_not_swallow_the_next_table():
    """Round 5 tightened the table-boundary separator to `-{3,}` and shipped no test for it.

    The loose `[\\s:|-]+` pattern also matches a DATA row of dashes or blanks, which splits a
    live table in two and freezes the real one at 0 rows. Every renderer in this tree emits
    `|---`, but `.windsurf/rules/ai/25-3d-generation.md` proves 2-dash separators occur, so a
    future renderer emitting `|:-:|--:|` would silently drop a whole table from magnitudes.
    """
    doc = "# D\n\n## S\n\n| a | b |\n|---|---|\n| 1 | 2 |\n| - | - |\n| 3 | 4 |\n| 5 | 6 |\n"
    rows = {k: v for k, v in cg.md_shape(doc)["magnitudes"].items() if k.startswith(cg.SECTION_KEY)}
    assert rows == {f"{cg.SECTION_KEY} S :: a|b": 4}, (
        f"a dashes-only DATA row split the table: {rows}"
    )


def test_an_emptied_marker_block_is_drift(monkeypatch):
    """18 of the 46 contract elements were presence-only booleans.

    `extract_block` returns "" for an emptied block, and "" is not None — so an injector that
    still writes its START/END fences with nothing between them read as fully intact. That is
    39% of the contract (ROSTER, EMBEDDING_ROSTER, EMBEDDING_CATALOG, EMBEDDING_WINNERS and
    14 ai-pack blocks) with no husk protection at all.
    """
    real = cg.observe

    def emptied():
        o = real()
        key = next(k for k, v in o["markers"].items() if v and v.get("rows"))
        o["markers"][key] = dict.fromkeys(o["markers"][key], 0)
        return o

    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    monkeypatch.setattr(cg, "observe", emptied)
    assert cg.verify() == 1, "a marker whose payload was emptied still read as injected"


def test_marker_content_churn_is_not_drift(monkeypatch):
    """The paired stability assertion: marker payloads are regenerated nightly."""
    real = cg.observe

    def churned():
        o = real()
        o["markers"] = {
            k: (None if v is None else {kk: int(vv * 1.08) for kk, vv in v.items()})
            for k, v in o["markers"].items()
        }
        return o

    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    monkeypatch.setattr(cg, "observe", churned)
    assert cg.verify() == 0, "ordinary marker-payload churn must not red the oracle"


def test_the_may_empty_exemption_is_wired_to_the_real_artifact(monkeypatch):
    """MAY_EMPTY is consulted in verify(), not in magnitudes_ok's signature.

    A test that passes `may_empty=True` by hand proves the parameter works, not that the
    exemption reaches the artifact it exists for — measured, CANDIDATE_SIGNUPS.md drained
    6 -> 2 rows in one real commit pair and would otherwise red the nightly oracle.
    """
    assert "docs/reference/kilo/CANDIDATE_SIGNUPS.md" in cg.MAY_EMPTY
    real = cg.observe

    def drained():
        o = real()
        a = o["artifacts"]["docs/reference/kilo/CANDIDATE_SIGNUPS.md"]
        if not a.get("present"):
            return o
        a["shape"]["magnitudes"] = dict.fromkeys(a["shape"]["magnitudes"], 0)
        return o

    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    monkeypatch.setattr(cg, "observe", drained)
    assert cg.verify() == 0, "the signup queue draining must not red the oracle"


def test_marker_sizes_are_observed_not_just_presence():
    """Guards the OBSERVER half of the marker fix.

    verify()'s comparison can distinguish emptied-from-present only if observe() records a
    SIZE; if it reverts to a boolean the whole check silently degrades, and a verify()-level
    test alone would not notice.
    """
    markers = cg.observe()["markers"]
    assert markers, "no markers observed"
    assert all(v is None or isinstance(v, dict) for v in markers.values()), (
        "markers look boolean/scalar — an emptied block would read as injected"
    )
    present = [v for v in markers.values() if v]
    assert present, "no marker payloads observed"
    # The DATA signals, not just a byte count: a character band certified 15 of 18 husks green.
    for v in present:
        assert "rows" in v and f"{cg.SECTION_KEY} nums" in v, (
            f"marker magnitude lacks a data signal: {sorted(v)}"
        )
    assert any(v["rows"] > 0 for v in present)


def test_a_marker_husk_that_keeps_its_table_is_drift():
    """The husk a row count CANNOT see — driven by the REAL renderer, not a mutation.

    `update_gateway_counts.render_block` emits a fixed table whose data IS its integers, so
    "every gateway reports 0" leaves rows, columns and ~98% of characters intact. The earlier
    version of this test built its husk with `re.sub(r"\\b\\d+\\b", "0", block)`, which also
    zeroed hardcoded prose constants ("+ 27 Qwen/...", "category 2", "GLM-5.2") that the real
    renderer PRESERVES — so it passed while 4 of the 7 real husks went undetected. Synthetic
    mutations flatter the oracle; drive the producer.
    """
    import importlib.util

    src = cg.SCRIPT_DIR / "update_gateway_counts.py"
    if not src.exists():
        pytest.skip("gateway renderer absent (engine excised)")
    spec = importlib.util.spec_from_file_location("_ugc", src)
    ugc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ugc)

    want = json.loads(cg.MANIFEST.read_text())["markers"]
    zero = dict.fromkeys(re.findall(r"counts\[[\"']([a-z_0-9]+)[\"']\]", src.read_text()), 0)
    checked, missed = 0, []
    for pack, category in (getattr(ugc, "PACK_TO_CATEGORY", {}) or {}).items():
        key = f".windsurf/rules/ai/{pack}::GATEWAY_COUNTS"
        if key not in want:
            continue
        husk = ugc.render_block(category, zero, "2026-01-01")
        checked += 1
        if cg.magnitudes_ok(want[key], cg.marker_shape(husk))[0]:
            missed.append(pack)
    assert checked >= 5, f"only {checked} gateway markers exercised — test is vacuous"
    assert not missed, f"all gateway counts zeroed but these read as healthy: {missed}"


def test_a_free_priced_routes_block_is_not_a_husk():
    """The mirror of the above, and why the signal must be BOLD integers.

    A routes block's only plain digits are prices, and `openrouter/auto` + `openrouter/fusion`
    are already live free routes — so a healthy block can legitimately render with zero price
    digits. Summing every integer made that fire the husk alarm on intact rows and columns.
    """
    checked = 0
    for rel, marker in [
        (f".windsurf/rules/ai/{h.name}", "OPENROUTER_ROUTES") for h in cg.ai_pack_hosts()
    ]:
        host = cg.FABRIK_ROOT / rel
        if not host.exists():
            continue
        block = cg.extract_block(host.read_text(errors="replace"), marker)
        if not block:
            continue
        free = re.sub(r"\$\d[\d.]*", "free", block)
        if free == block:
            continue  # already all-free; nothing to prove from this one
        checked += 1
        ok, why = cg.magnitudes_ok(cg.marker_shape(block), cg.marker_shape(free))
        assert ok, f"{rel}: a healthy free-priced block read as a husk: {why}"
    # Anti-vacuity: the sub is the identity once every live route is free, at which point this
    # asserts a block equals itself. Its sibling has this guard; this one did not.
    assert checked >= 3, f"only {checked} priced route blocks exercised — test is vacuous"


def test_marker_count_churn_is_not_drift():
    """The paired stability assertion for the counts signal.

    Measured over 666 real marker pairs, small route blocks moved 7 -> 3 and 10 -> 3
    legitimately; a proportional band on the integer sum called that a collapse.
    """
    base = "| Gateway | Models |\n|---|---|\n| **OpenRouter** | 384 |\n| **Kilo** | 349 |\n"
    moved = "| Gateway | Models |\n|---|---|\n| **OpenRouter** | 201 |\n| **Kilo** | 150 |\n"
    assert cg.magnitudes_ok(cg.marker_shape(base), cg.marker_shape(moved))[0], (
        "ordinary count movement must not red the oracle"
    )


def test_section_shrinkage_is_tolerated_but_emptying_is_not():
    """Pins the per-section rule, which nothing tested.

    The emptying-only tolerance is empirically justified — measured across real history it
    prevents 3 genuine false-reds (`review` 13 -> 4, `X-AI` 15 -> 4, the signup queue 6 -> 2).
    Without a test recording that, a later round tightening it would silently reintroduce a
    ~1.2%/pair false-red rate, which is how an oracle gets ignored.
    """
    k = f"{cg.SECTION_KEY} review :: rank|model"
    assert cg.magnitudes_ok({k: 13}, {k: 4})[0], "a section shrinking is catalog churn"
    assert not cg.magnitudes_ok({k: 13}, {k: 0})[0], "a section EMPTYING is a husk"


def test_a_golden_in_an_older_marker_format_refuses_to_run(monkeypatch, tmp_path):
    """Version-skew must refuse, not crash.

    ORACLE_VERSION was left at 2 across two shape-format changes (the section sentinel and
    markers int -> dict), so a round-6 golden met a round-7 observer and raised
    `AttributeError: 'int' object has no attribute 'items'` out of verify() — the production
    caller got a traceback instead of the designed "re-freeze with --snapshot" exit 2.
    """
    old = json.loads(cg.MANIFEST.read_text())
    old["markers"] = {k: (0 if v is None else 42) for k, v in old["markers"].items()}
    stale = tmp_path / "structure.json"
    stale.write_text(json.dumps(old))
    monkeypatch.setattr(cg, "MANIFEST", stale)
    assert cg.verify() == 2, "a pre-v3 marker format must refuse to run, not crash"


def test_drift_output_is_greppable(monkeypatch, capsys):
    """The section sentinel is a NUL; printed raw it makes the whole run log read as binary
    to grep, so "check the run log for the specific contract element" fails exactly when the
    operator needs it."""
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
    assert err.strip(), "drift reported nothing"
    assert "\x00" not in err, "raw NUL in operator output makes the run log un-greppable"


def test_marker_rows_count_every_table_not_just_sectioned_ones():
    """The fallback that fired exactly when it was needed least.

    rows summed section keys and fell back to the per-contract aggregate ONLY when that was 0
    — i.e. precisely when every sectioned table had emptied, at which point it silently
    reported a surviving heading-less table's rows instead.
    """
    headless = "| a | b |\n|---|---|\n| 1 | 2 |\n"
    section = "### {}\n\n| a | b |\n|---|---|\n" + "| x | y |\n" * 4
    block = headless + "\n" + section.format("one") + "\n" + section.format("two") + "\n"
    gutted = headless + "\n### one\n\n| a | b |\n|---|---|\n\n### two\n\n| a | b |\n|---|---|\n"
    # rows counts EVERY table, sectioned or not.
    assert cg.marker_shape(block)["rows"] == 9
    assert cg.marker_shape(gutted)["rows"] == 1
    # Under the old either/or fallback the gutted block reported the surviving heading-less
    # table's rows and read as unchanged.
    assert not cg.magnitudes_ok(cg.marker_shape(block), cg.marker_shape(gutted))[0]


def test_volatile_stripping_cannot_span_lines():
    """`\\(\\d+[^)]*\\)` matched across newlines, so one unbalanced `(` + digit would delete
    every heading and table header up to the next `)` — a loud structure-changed false red."""
    block = "| a | b |\n|---|---|\n| x (2 items | 1 |\n| y | 2 |\n| z | 3 ) |\n| w | 4 |\n"
    assert cg.marker_shape(block)["rows"] == 4, (
        f"volatile stripping ate rows across newlines: {cg.marker_shape(block)}"
    )
    # md_shape applies it per-heading, so it cannot span there — assert that too.
    doc = "# D (2 things\n\n## Real Section\n\n| m | s |\n|---|---|\n| x | 1 |\n\n## Other )\n"
    assert "Real Section" in " ".join(cg.md_shape(doc)["skeleton"])


# ── round-9 fixes ────────────────────────────────────────────────────────────
def test_a_partial_gateway_husk_is_drift():
    """A SUM cannot see a partial husk — this is why `live_counts` exists.

    The master gateway table renders its primary column as a PLAIN cell
    (`| **OpenRouter** | {or_total:,} |` — the bold is the label), so losing only the `via_*`
    flags while the capability counts still populate left the bold sum at 818/1551 and passed.
    That is the exact "Kilo has 235 models" staleness this script exists to prevent.
    """
    import importlib.util

    src = cg.SCRIPT_DIR / "update_gateway_counts.py"
    if not src.exists():
        pytest.skip("gateway renderer absent (engine excised)")
    spec = importlib.util.spec_from_file_location("_ugc9", src)
    ugc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ugc)

    keys = sorted(set(re.findall(r"counts\[[\"']([a-z_0-9]+)[\"']\]", src.read_text())))
    healthy = {k: 200 + i * 37 for i, k in enumerate(keys)}
    partial = dict(healthy)
    for k in keys:
        if k.startswith(("or_", "kilo_", "dashscope", "siliconflow", "modelscope")):
            partial[k] = 0

    base = cg.marker_shape(ugc.render_block("master", healthy, "2026-01-01"))
    husk = cg.marker_shape(ugc.render_block("master", partial, "2026-01-01"))
    assert husk["rows"] == base["rows"], "this husk deliberately keeps every row"
    assert husk[f"{cg.SECTION_KEY} nums"] > 0, "...and a non-zero integer sum"
    ok, why = cg.magnitudes_ok(base, husk)
    assert not ok, "every gateway count lost but the marker reads as healthy"
    assert "live_counts" in why, why


def test_a_bold_delimiter_does_not_crash_the_oracle():
    """`[\\d,]+` matches a bare comma; an unguarded int() raised out of verify()."""
    assert cg.marker_shape("x **,** y")["live_counts"] == 0
    assert cg.marker_shape("| a |\n|---|\n| **1,234** |\n")[f"{cg.SECTION_KEY} nums"] == 1234


def test_an_added_section_is_growth_but_a_removed_one_is_loss():
    """Three of the four frozen `##` sections in TASK_SUBAGENT_SELECTION.md are data-
    conditional — `_full_review_hard_results_table()` returns [] when its metrics are absent —
    so exact skeleton equality red-flagged a real pair of consecutive daily auto-commits. The
    golden is frozen for the whole B->E window, so that would have fired repeatedly.
    """
    base = "# D\n\n## Rankings\n\n| m | s |\n|---|---|\n| x | 1 |\n"
    grown = base + "\n## HARD benchmark\n\n| m | s |\n|---|---|\n| y | 2 |\n"
    assert not cg.shape_drift(cg.md_shape(base), cg.md_shape(grown)), "an added section is growth"
    assert cg.shape_drift(cg.md_shape(grown), cg.md_shape(base)), "a removed section is loss"


def test_the_real_conditional_section_pair_is_green():
    """Grounded in the exact commits, not a synthetic doc."""
    rel = "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
    a, b = _at("8b263799", rel), _at("69acc2b0", rel)
    if not a or not b:
        pytest.skip("historical revisions unavailable (shallow clone)")
    assert not cg.shape_drift(cg.md_shape(a), cg.md_shape(b)), (
        "two consecutive daily auto-commits still report drift"
    )
    assert cg.shape_drift(cg.md_shape(b), cg.md_shape(a)), (
        "...but losing that section must still be caught"
    )


# ── round-10 fixes ───────────────────────────────────────────────────────────
def test_a_golden_missing_a_magnitude_key_refuses_to_run(monkeypatch, tmp_path):
    """Version-skew, the SAME-version half.

    Round 9 added `live_counts` to the marker shape and left ORACLE_VERSION at 3, so a golden
    frozen one commit earlier passed the version gate — and `magnitudes_ok` iterates the
    GOLDEN's keys, so the new invariant was never checked. Executed at the time: a v3 golden
    certified the real partial gateway husk as "46 contract elements intact". The version
    number alone cannot see this; the key-set must be compared too.
    """
    old = json.loads(cg.MANIFEST.read_text())
    for v in old["markers"].values():
        if isinstance(v, dict):
            v.pop("live_counts", None)
    stale = tmp_path / "structure.json"
    stale.write_text(json.dumps(old))
    monkeypatch.setattr(cg, "MANIFEST", stale)
    assert cg.verify() == 2, "a golden missing a magnitude key must refuse, not silently skip"


def test_the_oracle_version_tracks_the_marker_shape():
    """A guard against forgetting the bump a third time.

    The key-set guard above is the real net, but it only fires against a golden that already
    exists. This pins the declared version to the shape the code emits, so adding a magnitude
    without bumping fails here at authoring time rather than in production.
    """
    assert set(cg.marker_shape("")) == {"chars", "rows", "live_counts", f"{cg.SECTION_KEY} nums"}
    assert cg.ORACLE_VERSION == 4, (
        "ORACLE_VERSION changed. If the MARKER key set above changed with it, update this "
        "assertion. If the bump was for another shape format (html/json/md), just update the "
        "number — the coupling asserted here is only to marker_shape."
    )


def test_snapshot_warns_about_inert_marker_magnitudes(tmp_path, monkeypatch, capsys):
    """The freeze-time 'can never red again' warning covered artifacts only.

    ⚠️ This test previously took `capsys`, never called `snapshot()` and never read stderr —
    deleting the entire warning loop left the whole suite green. It asserted a property of
    `observe()` while wearing this test's name. It now drives `snapshot()` for real, into
    tmp_path so the repo golden is never touched.

    Measured against the golden it describes: 10 of 18 markers freeze `live_counts: 0` — 7
    route blocks (no bold or whole-cell integers, by design) plus EMBEDDING_WINNERS,
    EMBEDDING_ROSTER and EMBEDDING_CATALOG, which are inert for the same reason without being
    route blocks. (An earlier docstring said "12 of 18 … route blocks", which was wrong on
    both counts.)
    """
    monkeypatch.setattr(cg, "GOLDEN_DIR", tmp_path)
    monkeypatch.setattr(cg, "MANIFEST", tmp_path / "structure.json")
    monkeypatch.setattr(cg, "DB_QUERIES", tmp_path / "db_queries.json")
    obs = cg.snapshot()
    err = capsys.readouterr().err

    inert = [
        k
        for k, v in obs["markers"].items()
        if isinstance(v, dict) and any(n == 0 for n in v.values())
    ]
    assert inert, "no inert marker magnitudes — this test no longer measures anything"
    assert "freezing EMPTY marker magnitudes" in err, (
        "snapshot() froze permanently-inert marker magnitudes without telling the operator"
    )
    # NOT asserted here: a raw-NUL leak. These keys are printed inside a list, and Python's
    # list repr escapes the sentinel — unlike verify()'s drift lines, which concatenate a bare
    # string and DO leak it (see test_drift_output_is_greppable). The `.replace` in snapshot()
    # is readability, not a leak guard; asserting otherwise would be a test that cannot fail.
    assert cg.MANIFEST.exists() and cg.DB_QUERIES.exists(), "snapshot wrote no golden"


def test_every_marker_retains_a_live_husk_signal():
    """`chars` does not count.

    The module's own measurement is that total data loss retained 53-100% of the characters
    in 15 of 18 markers, and 53% > COLLAPSE_RATIO — so a marker whose only non-zero magnitude
    is `chars` is unguarded against a total husk. The previous form of this assertion counted
    `chars`, which is > 0 for any non-empty block, so it could never fail.
    """
    for key, mag in cg.observe()["markers"].items():
        if not isinstance(mag, dict):
            continue
        live = {k: n for k, n in mag.items() if k != "chars" and n > 0}
        assert live, f"{key} has no husk signal beyond chars — it is unguarded"


def test_a_capability_only_gateway_husk_is_drift():
    """The MIRROR of the husk round 9 added live_counts to catch — which it did not cover.

    The five `with_*` capability columns going to zero while the gateway columns still
    populate left live_counts at 9 of 13, inside `_min_allowed(13) = 6.5`. So the oracle
    passed a block reading "reasoning **0** · tools **0** · vision **0**", which
    daily_refresh.sh fleet-syncs to ~46 repos. A POSITION count needs an absolute allowance,
    not a ratio.
    """
    import importlib.util

    src = cg.SCRIPT_DIR / "update_gateway_counts.py"
    if not src.exists():
        pytest.skip("gateway renderer absent (engine excised)")
    spec = importlib.util.spec_from_file_location("_ugc11", src)
    ugc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ugc)

    keys = sorted(set(re.findall(r"counts\[[\"']([a-z_0-9]+)[\"']\]", src.read_text())))
    healthy = {k: 200 + i * 37 for i, k in enumerate(keys)}
    caps_dead = {k: (0 if k.startswith("with_") else v) for k, v in healthy.items()}

    base = cg.marker_shape(ugc.render_block("master", healthy, "2026-01-01"))
    husk = cg.marker_shape(ugc.render_block("master", caps_dead, "2026-01-01"))
    assert husk["rows"] == base["rows"], "this husk keeps every row"
    assert husk[f"{cg.SECTION_KEY} nums"] > 0, "...and a non-zero integer sum"
    ok, why = cg.magnitudes_ok(base, husk)
    assert not ok, "every capability count zeroed but the marker reads as healthy"
    assert "live_counts" in why, why


def test_one_position_of_count_churn_is_still_tolerated():
    """The paired stability assertion for the absolute allowance.

    Over 727 real consecutive marker pairs `live_counts` fell exactly twice, both 14 -> 13.
    """
    assert cg.magnitudes_ok({"live_counts": 14}, {"live_counts": 13})[0]
    assert not cg.magnitudes_ok({"live_counts": 14}, {"live_counts": 12})[0]


def test_a_golden_missing_a_section_refuses_to_run(monkeypatch, tmp_path):
    """Tolerant `.get` alone turned a truncated golden from a crash into
    `OK — 28 contract elements intact` — strictly worse, because the crash at least surfaced.
    Both halves are needed: tolerant reads so verify() cannot raise, this guard so it cannot
    lie about how much it checked."""
    for section in ("artifacts", "markers", "db_queries"):
        g = json.loads(cg.MANIFEST.read_text())
        g.pop(section)
        stale = tmp_path / f"{section}.json"
        stale.write_text(json.dumps(g))
        monkeypatch.setattr(cg, "MANIFEST", stale)
        assert cg.verify() == 2, f"a golden missing '{section}' must refuse, not check less"


def test_a_golden_with_a_stale_html_key_set_refuses_to_run(monkeypatch, tmp_path):
    """The marker key-set guard's sibling.

    `html_shape`'s magnitude key set is fixed ({tr, payload_bytes}), so adding a third without
    a version bump would be silently skipped exactly as `live_counts` was — `magnitudes_ok`
    iterates the GOLDEN's keys, and `shape_drift` pops `magnitudes` before comparing the rest,
    so nothing else would red.
    """
    g = json.loads(cg.MANIFEST.read_text())
    html = [r for r, a in g["artifacts"].items() if r.endswith(".html") and a.get("present")]
    if not html:
        pytest.skip("no html artifact present locally")
    g["artifacts"][html[0]]["shape"]["magnitudes"].pop("payload_bytes", None)
    stale = tmp_path / "structure.json"
    stale.write_text(json.dumps(g))
    monkeypatch.setattr(cg, "MANIFEST", stale)
    assert cg.verify() == 2, "a stale html magnitude key set must refuse, not silently skip"


# ── round-12 fixes ───────────────────────────────────────────────────────────
def test_a_single_dead_column_is_drift_on_the_small_gateway_packs():
    """A flat `wn - 1` allowance was a 50% blind spot on 2-position blocks.

    `30-language` and `50-agentic` carry two counts each, so ONE dying —
    "tool/function-calling across all gateways: **0**" — sat inside the allowance while
    `chars` stayed byte-identical, `rows` frozen at 0 and `nums` non-zero. Measured over every
    revision of all 18 markers, the small packs have NEVER lost a position, so closing this
    costs nothing.
    """
    import importlib.util

    src = cg.SCRIPT_DIR / "update_gateway_counts.py"
    if not src.exists():
        pytest.skip("gateway renderer absent (engine excised)")
    spec = importlib.util.spec_from_file_location("_ugc12", src)
    ugc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ugc)

    keys = sorted(set(re.findall(r"counts\[[\"']([a-z_0-9]+)[\"']\]", src.read_text())))
    healthy = {k: 200 + i * 37 for i, k in enumerate(keys)}
    # Without this the `language` pack renders "language-tagged: **0**", its base live_counts is
    # 1 not 2, and the `< 2` guard below SKIPS it — so the test silently covered only `agentic`
    # while its docstring claimed both, and `checked >= 2` was satisfied by agentic alone.
    healthy.setdefault("categories", {})
    checked = 0
    for category in ("language", "agentic"):
        base = cg.marker_shape(ugc.render_block(category, healthy, "2026-01-01"))
        if base["live_counts"] < 2:
            continue
        for dead in [k for k in keys if k.startswith("with_")]:
            husk = cg.marker_shape(ugc.render_block(category, {**healthy, dead: 0}, "2026-01-01"))
            if husk["live_counts"] == base["live_counts"]:
                continue  # that count is not rendered for this category
            checked += 1
            assert not cg.magnitudes_ok(base, husk)[0], (
                f"{category}: {dead} died but the pack reads as healthy"
            )
    assert checked >= 2, f"only {checked} single-column husks exercised — test is vacuous"


def test_a_one_position_block_may_not_lose_its_only_position():
    """`wn - 1` silently re-opened the wn=1 hole that `_min_allowed`'s max(1.0, …) floor
    exists to prevent. Four markers are frozen at `live_counts: 1`."""
    assert not cg.magnitudes_ok({"live_counts": 1}, {"live_counts": 0})[0]
    assert not cg.magnitudes_ok({"live_counts": 2}, {"live_counts": 1})[0]
    # ...while the large master block keeps its one-position allowance, which real history
    # needs: it legitimately lost a position four times (a direct-vendor gateway going 1 -> 0).
    assert cg.magnitudes_ok({"live_counts": 14}, {"live_counts": 13})[0]
    assert not cg.magnitudes_ok({"live_counts": 14}, {"live_counts": 12})[0]


def test_an_unfrozen_marker_is_not_counted_as_intact(monkeypatch, capsys, tmp_path):
    """A marker frozen as `None` was never observed, so it is checked by nothing — counting it
    as an "intact contract element" overstates coverage, the module's own
    certifies-what-it-never-checked class. Reverting this left the whole suite green.
    """
    golden = json.loads(cg.MANIFEST.read_text())
    absent = sorted(golden["markers"])[:2]
    total = len(golden["artifacts"]) + len(golden["markers"]) + len(golden["db_queries"])

    real = cg.observe

    def with_absent():
        o = real()
        for k in absent:
            o["markers"][k] = None
        return o

    for k in absent:
        golden["markers"][k] = None
    stale = tmp_path / "structure.json"
    stale.write_text(json.dumps(golden))

    monkeypatch.delenv("ORACLE_REQUIRE_LOCAL_ARTIFACTS", raising=False)
    monkeypatch.setattr(cg, "observe", with_absent)
    monkeypatch.setattr(cg, "MANIFEST", stale)
    assert cg.verify() == 0
    out = capsys.readouterr().out
    assert "UNFROZEN" in out, f"absent markers reported as intact: {out}"
    assert f"{total - len(absent)} contract elements" in out, out


# ── round-13 fixes ───────────────────────────────────────────────────────────
def test_both_pipeline_entry_points_run_the_oracle_before_committing():
    """The ordering test that only looked at daily_refresh.sh could not see the real path.

    Both entry points share /tmp/.fabrik_daily_<UTC>, so whichever wins the race the other
    SKIPS ENTIRELY. Measured from update.log: 7 "Pipeline complete" (wsl_startup_hook) vs 0
    "Refresh complete" (daily_refresh) — a workstation booted after the 06:00 UTC cron always
    wins, so the oracle's only caller had not run at all. Meanwhile the hook's auto-commit
    matches the governance-sync pre-commit filter (^\\.windsurf/rules/), so it fans a husk out
    to ~46 repos. Assert the invariant on EVERY entry point, not just the one that documents it.
    """
    for rel in ("daily_refresh.sh", "../wsl_startup_hook.sh"):
        sh = (cg.SCRIPT_DIR / rel).read_text()
        lines = [ln for ln in sh.splitlines() if not ln.lstrip().startswith("#")]
        body = "\n".join(lines)
        assert "capture_golden.py" in body and "--verify" in body, f"{rel}: no oracle call"
        assert "autocommit_pipeline_outputs" in body, f"{rel}: no auto-commit call"
        assert body.index("capture_golden.py") < body.index("autocommit_pipeline_outputs"), (
            f"{rel}: commits/pushes BEFORE verifying the contract — a husk would fleet-sync"
        )


def test_the_autocommit_commits_a_pathspec_not_the_index():
    """CLAUDE.md § HARD STOPS: commit with a pathspec, never the index.

    The first version ran `git add -- <paths>` then a BARE `git commit`, which commits
    EVERYTHING staged — a peer's WIP rode along, defeating the exclusion list in the same file.
    A bare `final_gate.py` run auto-stages, so a non-empty index is the normal state here.
    """
    sh = (cg.SCRIPT_DIR / "autocommit_pipeline_outputs.sh").read_text()
    # Anchor on the COMMAND, not the word: the file's own comments discuss `git commit`, and
    # matching those made an earlier version of this assertion read the prose instead.
    lines = sh.splitlines()
    start = next(
        i
        for i, ln in enumerate(lines)
        if ln.strip().startswith("git commit") and not ln.lstrip().startswith("#")
    )
    # Widened from 10: a multi-line -m trailer block pushed the pathspec past the window, and
    # this assertion went red while the behavioural test caught the REAL regression (the
    # pathspec had actually been dropped). Read to the end of the command instead.
    end = next(
        (i for i in range(start, len(lines)) if 'echo "[auto-commit] committed"' in lines[i]),
        start + 20,
    )
    commit = "\n".join(lines[start : end + 1])
    assert '-- "${STAGED[@]}"' in commit, f"git commit has no pathspec:\n{commit}"
    assert 'git diff --cached --quiet -- "${STAGED[@]}"' in sh, (
        "the emptiness test is unscoped — it fires whenever ANY file is staged"
    )
    for protected in ("PORTS.md", "LOCAL_LLM_INFRASTRUCTURE.md", "libs/subagents", "plan-locks"):
        staged_block = sh[sh.index("PATHS=(") : sh.index(")", sh.index("PATHS=("))]
        assert protected not in staged_block, f"{protected} is in the stage list"


def test_the_autocommit_survives_a_retired_pipeline_path():
    """`git add` is all-or-nothing: ONE renamed path made it exit 128 with NOTHING staged,
    and the guard then logged "tree already clean" — reporting success for a total no-op.
    Phase B copies this into the engine repo where most paths will not exist."""
    sh = (cg.SCRIPT_DIR / "autocommit_pipeline_outputs.sh").read_text()
    assert 'for _p in "${PATHS[@]}"' in sh, "paths are still added in one all-or-nothing call"
    assert "no pipeline paths matched" in sh, "a total mismatch is not reported"
    assert "stage paths matched" in sh, "a partial mismatch is not warned"


# ── round-14 fixes ───────────────────────────────────────────────────────────
def _hook_prelude(src: str) -> str:
    """The variable assignments `_hook_inner_block` sources — ASSIGNMENTS ONLY.

    ⚠️ Its own function so the guard below asserts on THE STRING THAT IS ACTUALLY SOURCED. An
    earlier guard rebuilt this from an inline copy of the same filter, so reverting the real
    slice left the guard green — the fork-the-source class this plan exists to un-fork,
    reproduced inside the guard against it.

    Slicing to "# --- Persistent process" instead swept in the hook's LOG ROTATION loop, which
    `mv`s the REAL /opt/fabrik logs (FABRIK_ROOT is hardcoded there, so no override protects
    them). Every pytest and gate run would then have destroyed a generation of pipeline history
    the moment update.log crossed 500KB — the very log an operator reads while running this
    suite to diagnose the pipeline.
    """
    return "\n".join(
        ln
        for ln in src.splitlines()
        if re.match(r"^[A-Z_]+=", ln) and "$(" not in ln.split("=", 1)[1]
    )


def _hook_inner_block() -> str:
    """The wsl_startup_hook pipeline body EXACTLY as the child `bash -c` receives it.

    Produced by REAL BASH, not a Python model of it. The previous version reimplemented the
    outer shell's double-quote processing by hand and diverged in four ways — it did not join
    backslash-newline continuations, did not expand `$(date …)`, did not model quote removal,
    and knew only three variables. The first of those hid a defect: a dropped continuation
    backslash is a syntax error that kills the rest of the pipeline, and the hand model could
    not see it. Bash is available; modelling it is a needless source of false confidence.
    """
    hook = cg.SCRIPT_DIR.parent / "wsl_startup_hook.sh"
    src = hook.read_text()
    i = src.index('nohup bash -c "')
    j = src.index('\n    " &', i)
    quoted = src[i + len("nohup bash -c ") : j + len('\n    "')]
    # Run the hook's own assignment block so every variable resolves exactly as it would at
    # boot, then let BASH perform the quote processing and print the result.
    prelude = _hook_prelude(src)
    harness = prelude + "\nprintf '%s' " + quoted + "\n"
    r = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
    assert r.returncode == 0, f"could not materialise the child block: {r.stderr[:300]}"
    return r.stdout


def test_the_hook_child_block_is_syntactically_valid():
    """A dropped continuation backslash aborts the REST of the pipeline — including the
    auto-commit — and both behavioural tests stay green. Round 13 checked this ad hoc and
    round 14 did not preserve it as a test; nothing else validates this file's inner block.
    """
    inner = _hook_inner_block()
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(inner)
        path = fh.name
    try:
        r = subprocess.run(["bash", "-n", path], capture_output=True, text=True)
        assert r.returncode == 0, f"the child block does not parse:\n{r.stderr[:400]}"
    finally:
        Path(path).unlink(missing_ok=True)


def test_the_hook_pipeline_steps_are_actually_runnable():
    """EXECUTION-level, not textual — the gap that let a dead fix pass review.

    The round-13 ordering test asserted the oracle APPEARED before the auto-commit and passed
    while all three added steps were inert: they had been written with escaped `\\$VENV_PYTHON`,
    unlike the file's 22 other call sites, so the child received a literal `$VENV_PYTHON`, the
    variable was unset there, and every line died on `ambiguous redirect` — taking its own
    `|| echo` fallback with it, so nothing was even logged. The auto-commit below them still
    ran, committing and fleet-syncing unverified.
    """
    inner = _hook_inner_block()
    steps = [
        ln.strip()
        for ln in inner.splitlines()
        if "kilo-benchmarks" in ln
        and any(
            k in ln
            for k in (
                "rank_task_subagents",
                "capture_golden",
                "autocommit_",
                # These two were EXCLUDED by the original filter, so the round-14 defect class
                # (an escaped \$VAR -> "ambiguous redirect" -> the step and its own || echo both
                # die silently) was still live on exactly the lines round 15 added.
                "check_daily_refresh_freshness",
                "daily_refresh_last_success",
            )
        )
    ]
    assert len(steps) >= 3, f"expected the pipeline steps, found {len(steps)}"
    for step in steps:
        assert not re.search(r"\$[A-Za-z_]+", step), (
            f"unexpanded variable reaches the child shell — the step will not run:\n  {step}"
        )
    # ...and the interpreter/script each COMMAND line invokes must exist on disk. Continuation
    # lines (`|| { … }`) carry the failure path, not a command word, so they are checked for
    # unexpanded variables above but skipped here.
    # Check EVERY absolute path each line names, not just the command word: the previous form
    # validated `/opt/fabrik/.venv/bin/python` twice and one shell script, so moving or deleting
    # rank_task_subagents.py / capture_golden.py / pipeline_alert.sh left it green. Phase E
    # DELETES the engine scripts, so that blind spot is on the plan's own critical path.
    targets = set()
    for step in steps + [ln.strip() for ln in inner.splitlines() if "pipeline_alert.sh" in ln]:
        for word in step.split():
            w = word.strip("'\";&|()")
            # Skip anything under a gitignored cache dir: `cache/update.log` is a REDIRECT
            # TARGET, not an invoked path, and .gitignore:163 ignores it — pinning it reds this
            # test on every fresh clone, in CI, and in the Phase-B engine repo, which is the
            # exact environment this test exists to protect.
            if "/cache/" in w or w.endswith(".log"):
                continue
            if w.startswith("/opt/") and ("." in Path(w).name):
                targets.add(w)
    assert len(targets) >= 4, f"only {len(targets)} absolute targets found — test is vacuous"
    missing = sorted(w for w in targets if not Path(w).exists())
    assert not missing, f"the hook invokes paths that do not exist: {missing}"


def test_the_hook_alerts_on_a_broken_ranker_or_a_red_oracle():
    """A.0 gate 3, replicated onto the entry point that actually runs.

    test_daily_refresh_does_not_swallow_the_tripwire enforces this on daily_refresh.sh only —
    and daily_refresh.sh is the entry point that loses the lockfile race and never executes.
    A bare `|| echo` there is a line in a log the file's own comment says nobody tails.
    """
    inner = _hook_inner_block()
    for step_key in ("rank_task_subagents", "capture_golden.py --verify"):
        line = next(ln for ln in inner.splitlines() if step_key in ln and "||" in ln)
        assert "pipeline_alert.sh" in line, (
            f"{step_key} failure is swallowed into a log line, no alert:\n  {line[:160]}"
        )


def test_the_alert_helper_loads_dotenv_before_importing_alerting():
    """`alerting` reads TELEGRAM_BOT_TOKEN from the process env and does not load .env itself,
    so an invocation without load_dotenv is a SILENT no-op — the defect
    check_daily_refresh_freshness.py:39-43 documents."""
    # Strip comments FIRST: the file carries a "⚠️ load_dotenv BEFORE importing alerting"
    # warning, and matching that made an earlier version of this assertion pass against a
    # helper with both real dotenv lines deleted — a test asserting its own documentation.
    helper = (cg.SCRIPT_DIR / "pipeline_alert.sh").read_text()
    code = "\n".join(ln for ln in helper.splitlines() if not ln.lstrip().startswith("#"))
    assert "from dotenv import load_dotenv" in code, "the helper does not import load_dotenv"
    assert "load_dotenv(" in code, "the helper never CALLS load_dotenv"
    assert code.index("load_dotenv(") < code.index("from alerting import send_alert"), (
        "alerting is imported before dotenv is loaded — the alert is a silent no-op"
    )


def test_the_hook_prelude_slice_stays_side_effect_free():
    """Guards the class that made a TEST destroy production logs.

    Asserts on `_hook_prelude` — the string `_hook_inner_block` actually sources — so widening
    the slice back to the log-rotation loop reds here. A shim-based check does NOT work: the
    rotation only fires when the log exceeds 500KB, so it would pass whenever the log happens
    to be small, which is exactly the latent condition that made the original defect invisible.
    """
    src = (cg.SCRIPT_DIR.parent / "wsl_startup_hook.sh").read_text()
    prelude = _hook_prelude(src)
    assert prelude, "the prelude filter matched nothing"
    for danger in ("mv ", "rm ", "for ", "while ", "if ", "`", "$(", ">", "|"):
        assert danger not in prelude, (
            f"the prelude contains {danger!r} — sourcing it has side effects on the REAL repo "
            f"(FABRIK_ROOT is hardcoded in that file, so no override protects it)"
        )
    for var in ("FABRIK_ROOT=", "VENV_PYTHON=", "LOG_FILE="):
        assert var in prelude, f"{var} lost from the prelude — steps would expand to empty"
    # ...and the materialised block must still resolve, proving the prelude is sufficient.
    assert "/opt/fabrik/.venv/bin/python" in _hook_inner_block()


def test_every_commit_template_in_the_command_corpus_parses():
    """The execute-plan trailer templates regressed in THREE consecutive rounds and nothing in
    the tree guarded them — `assemble_commands.py --check` only proves the rendered copy matches
    the source, not that either is correct.

    Each template is committed for real and read back, because the failure modes are invisible
    to inspection: a blank line inside the block, an INDENTED trailer (git ignores those
    entirely), or an indented `EOF` that is not even valid shell.
    """
    src = cg.FABRIK_ROOT / "commands/_sources/fabrik-execute-plan.md"
    if not src.exists():
        pytest.skip("command corpus source absent")
    text = src.read_text()
    # ⚠️ Anchor the terminator at column 0 (`^EOF$`). The lazy `\nEOF` form re-anchors on the
    # NEXT unindented EOF when one site is indented, silently MERGING two templates into one
    # match — so a single indented `EOF` (a hard shell syntax error, since `<<-` strips tabs
    # only) slipped through while the count merely dropped 6 -> 5.
    blocks = [
        b for b in re.findall(r"cat <<'EOF'\n(.*?)\n^EOF$", text, re.S | re.M) if "Agent-Role:" in b
    ]
    expected = len(re.findall(r"cat <<'EOF'\n(?:(?!\ncat <<'EOF').)*?Agent-Role:", text, re.S))
    assert len(blocks) == expected, (
        f"{expected} templates carry Agent-Role but only {len(blocks)} parsed as complete "
        f"heredocs — an EOF terminator is indented, which is not valid shell"
    )
    assert len(blocks) >= 4, f"only {len(blocks)} trailer templates found — test is vacuous"

    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q", d], check=True)
        for k, v in (("user.email", "t@t"), ("user.name", "t")):
            subprocess.run(["git", "-C", d, "config", k, v], check=True)
        subprocess.run(["git", "-C", d, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        for i, body in enumerate(blocks):
            msg = Path(d) / "m.txt"
            msg.write_text(body)
            subprocess.run(
                ["git", "-C", d, "commit", "-q", "--allow-empty", "-F", str(msg)], check=True
            )
            role = subprocess.run(
                ["git", "-C", d, "log", "-1", "--format=%(trailers:key=Agent-Role,valueonly)"],
                capture_output=True,
                text=True,
            ).stdout.strip()
            assert role, (
                f"template #{i} yields an UNPARSEABLE Agent-Role — a blank line inside the "
                f"block, or an indented trailer:\n{body[:300]}"
            )
            # An indented SUBJECT still parses its trailers, so the assertion above cannot see
            # it — but it produces `git log --oneline` entries like "  feat(scope): …". This is
            # one of the three modes the docstring names and it regressed once already.
            subject = body.split("\n", 1)[0]
            assert subject == subject.lstrip(), (
                f"template #{i} has an INDENTED subject line — commits made from it carry the "
                f"leading whitespace: {subject!r}"
            )


def test_query_constant_discovery_catches_new_constants(tmp_path):
    """The freeze discovers *QUERY constants by NAME PATTERN — a new query constant added to
    rank_task_subagents.py must land in the snapshot (and thus the drift alarm) with NO
    capture_golden edit. Hardcoding keys is the class that let ec05a490's canary key ship
    only because a human remembered (infra relay 01M16TGP)."""
    mod_file = tmp_path / "fake_rts.py"
    mod_file.write_text(
        'QUERY = "SELECT 1"\n'
        'CANARY_QUERY = "SELECT 2"\n'
        'EXTRA_STATS_QUERY = "SELECT 3"\n'
        "NOT_A_QUERY_CONSTANT = 7\n"  # non-str with matching-ish name: ignored
        'lower_query = "SELECT 4"\n'  # lowercase: not a constant, ignored
    )
    import importlib.util

    spec = importlib.util.spec_from_file_location("fake_rts", mod_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = cg._query_constants(mod)
    assert out["rank_task_subagents.flywheel"] == "SELECT 1"  # legacy name kept (parity)
    assert out["rank_task_subagents.canary"] == "SELECT 2"  # legacy name kept
    assert out["rank_task_subagents.q_extra_stats_query"] == "SELECT 3"  # the CLASS: discovered
    assert len(out) == 3
