"""Behavior Contract for Phase B — check_structure derives its docs/ allowlist from the
canonical registry (SSOT) instead of a hard-coded second copy.

Covers: registry docs no longer WARN (defect-1 killed), legacy docs tolerated, genuinely
misplaced docs still WARN, the derived set is permissive (no-arg union) + grandfathers the
old hard-coded set, and the fail-safe fallback is sound.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ENFORCE = REPO_ROOT / "scripts" / "enforcement"


def _load_check_structure():
    sys.path.insert(0, str(ENFORCE))
    spec = importlib.util.spec_from_file_location("check_structure", ENFORCE / "check_structure.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cs = _load_check_structure()


def _docs_violations(names):
    """Run check_structure over the given docs/ files; return the flagged basenames."""
    viols = cs.check_structure(REPO_ROOT, files=[f"docs/{n}" for n in names])
    return {Path(v["file"]).name for v in viols}


# --- (a) registry docs that USED to WARN are now allowed (defect-1 class gone)
def test_registry_docs_no_longer_warn():
    flagged = _docs_violations(
        ["RESILIENCE.md", "data-contract.md", "ui-design.md", "STRATEGIC_BACKLOG.md", "LESSONS_LEARNT.md"]
    )
    assert not flagged, f"registry docs wrongly WARNed: {sorted(flagged)}"


# --- (b) a recognized-standard legacy doc older projects carry is tolerated
def test_legacy_docs_tolerated():
    flagged = _docs_violations(["HANDOVER.md", "lessons-learnt.md", "API_REFERENCE.md", "FINANCIALS.md"])
    assert not flagged, f"legacy docs wrongly WARNed: {sorted(flagged)}"


# --- (c) a genuinely-misplaced doc still WARNs (the gate still does its job)
def test_misplaced_doc_still_warns():
    flagged = _docs_violations(["random.md", "my_notes.md"])
    assert "random.md" in flagged and "my_notes.md" in flagged


# --- the allowlist is DERIVED (permissive no-arg union + LEGACY_TOLERATED), not the fallback
def test_allowlist_is_registry_derived_permissive_union():
    import _doc_registry

    expected = _doc_registry.docs_allowlist() | _doc_registry.LEGACY_TOLERATED
    assert cs.DOCS_ALLOWLIST == expected
    # it must be the RICHER derived set, proving the import path worked (not the fallback)
    assert cs.DOCS_ALLOWLIST != cs._FALLBACK_DOCS_ALLOWLIST
    assert len(cs.DOCS_ALLOWLIST) > len(cs._FALLBACK_DOCS_ALLOWLIST)


# --- (d) grandfather: derived ⊇ old hard-coded set (no currently-clean project regresses)
def test_grandfather_derived_superset_of_old_set():
    assert cs._FALLBACK_DOCS_ALLOWLIST <= cs.DOCS_ALLOWLIST, "a currently-clean doc would newly WARN"
    # in the NORMAL (registry-imported) state the derived set is strictly richer than the old
    # literal — proving this is not the trivially-reflexive reverted state
    assert cs._FALLBACK_DOCS_ALLOWLIST < cs.DOCS_ALLOWLIST


# --- the fail-safe fallback is REAL: sabotage the registry import → gate degrades to the old
#     literal set (never crashes) and still flags a misplaced doc
def test_fallback_fires_when_registry_unimportable(monkeypatch):
    import importlib

    class _Boom:
        def __getattr__(self, name):  # any registry attribute access explodes
            raise RuntimeError("registry sabotaged")

    monkeypatch.setitem(sys.modules, "_doc_registry", _Boom())
    spec = importlib.util.spec_from_file_location("check_structure_fb", ENFORCE / "check_structure.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # module-level try/except runs against the sabotaged import
    # degraded to the fallback (the exact pre-change literal), no crash
    assert mod.DOCS_ALLOWLIST == mod._FALLBACK_DOCS_ALLOWLIST
    # and the gate is still operational under fallback: a misplaced doc still WARNs,
    # a fallback-allowed doc does not
    viols = mod.check_structure(REPO_ROOT, files=["docs/random.md", "docs/SERVICES.md"])
    flagged = {Path(v["file"]).name for v in viols}
    assert "random.md" in flagged
    assert "SERVICES.md" not in flagged  # SERVICES.md is in the fallback set
