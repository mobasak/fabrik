"""/fabrik-data-contract: the doc-links gate honours the lowercase `does not exist` marker.

The corpus-text presence pins of this file retired into commands/_rules/fabrik-data-contract.yaml (the lean
rule ledger); the behavioural test below stays because it executes the checker.
"""

from __future__ import annotations

from pathlib import Path


def test_a_delta_citing_an_unbuilt_file_carries_the_doc_links_marker() -> None:
    """Row 1791942388 (web-ecommerce-factory): two pushes went red on Doc Link Integrity because a re-frozen contract
    cited, by repo-relative path, files its spec had not built yet. Phase 3 item 6 names the marker the link checker
    honours, its exact phrase and its whole-line reach; the checker still honours it, lowercase only."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_doc_links", Path(__file__).resolve().parents[1] / "scripts" / "enforcement" / "check_doc_links.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    marked = "- `src/pending/reader.py` — does not exist yet (built by the spec)."
    unmarked = "- `src/pending/reader.py` — built by the spec."
    capital = "- `src/pending/reader.py` — Does not exist yet."
    assert list(mod._iter_refs(marked)) == []
    assert list(mod._iter_refs(unmarked)) != []
    assert list(mod._iter_refs(capital)) != []
