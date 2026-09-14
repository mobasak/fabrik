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
        [
            "RESILIENCE.md",
            "data-contract.md",
            "ui-design.md",
            "STRATEGIC_BACKLOG.md",
            "LESSONS_LEARNT.md",
        ]
    )
    assert not flagged, f"registry docs wrongly WARNed: {sorted(flagged)}"


# --- (b) a recognized-standard legacy doc older projects carry is tolerated
def test_legacy_docs_tolerated():
    flagged = _docs_violations(
        ["HANDOVER.md", "lessons-learnt.md", "API_REFERENCE.md", "FINANCIALS.md"]
    )
    assert not flagged, f"legacy docs wrongly WARNed: {sorted(flagged)}"


# --- (c) a genuinely-misplaced doc still WARNs (the gate still does its job)
def test_misplaced_doc_still_warns():
    flagged = _docs_violations(["random.md", "my_notes.md"])
    assert "random.md" in flagged and "my_notes.md" in flagged


# --- the allowlist is DERIVED (permissive no-arg union + LEGACY_TOLERATED), not the fallback
def test_allowlist_is_registry_derived_permissive_union():
    import _doc_registry

    expected = _doc_registry.docs_allowlist() | _doc_registry.LEGACY_TOLERATED
    assert expected == cs.DOCS_ALLOWLIST
    # it must be the RICHER derived set, proving the import path worked (not the fallback)
    assert cs.DOCS_ALLOWLIST != cs._FALLBACK_DOCS_ALLOWLIST
    assert len(cs.DOCS_ALLOWLIST) > len(cs._FALLBACK_DOCS_ALLOWLIST)


# --- (d) grandfather: derived ⊇ old hard-coded set (no currently-clean project regresses)
def test_grandfather_derived_superset_of_old_set():
    assert cs._FALLBACK_DOCS_ALLOWLIST <= cs.DOCS_ALLOWLIST, (
        "a currently-clean doc would newly WARN"
    )
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
    spec = importlib.util.spec_from_file_location(
        "check_structure_fb", ENFORCE / "check_structure.py"
    )
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


# --- runtime-asset carve-out (2026-07-16): src/**/prompts/ + src/**/libs/ are code-adjacent
#     runtime assets, not stray docs — 30 prompt templates hard-failed Project Structure before.
def _src_errors(paths):
    viols = cs.check_structure(REPO_ROOT, files=list(paths))
    return {v["file"] for v in viols if v["severity"] == "error"}


def test_src_prompts_md_exempt_runtime_asset():
    paths = ["src/brand_identity/prompts/generate_name.md", "src/app/prompts/bible/tone.md"]
    assert not _src_errors(paths), (
        "runtime prompt templates under src/**/prompts/ must not be flagged"
    )


def test_prompts_md_exempt_at_any_depth():
    # Prompt templates are md-as-DATA wherever they live (the dir NAME is the
    # contract, like libs/): data/prompts/, scripts/**/prompts/, config/prompts/.
    paths = [
        "data/prompts/seo/title.md",
        "scripts/generators/prompts/outline.md",
        "config/prompts/system.md",
    ]
    assert not _src_errors(paths), "prompt templates under any */prompts/ must not be flagged"


def test_src_nested_libs_md_exempt_vendored():
    paths = [
        "src/brand_identity/libs/mt_router/UPSTREAM_FEEDBACK.md",
        "src/pkg/libs/foo/VENDORING.md",
    ]
    assert not _src_errors(paths), "vendored-module docs under src/**/libs/ must not be flagged"


def test_stray_src_md_outside_prompts_libs_still_flagged():
    # scoped carve-out: a genuinely stray .md under src/ (not prompts/ or libs/) STILL errors
    errs = _src_errors(["src/brand_identity/notes.md", "src/pkg/services/TODO.md"])
    assert "src/brand_identity/notes.md" in errs and "src/pkg/services/TODO.md" in errs


# --- upstream fixes (trade-intelligence proposals, applied 2026-08-06) ------------
def test_docs_site_docusaurus_md_exempt():
    # docusaurus is a first-class SCAFFOLD_TYPE; its markdown MUST live under
    # docs-site/ by Docusaurus's own contract — the scaffolder produces this layout.
    paths = [
        "docs-site/docs/intro.md",
        "docs-site/docs/guides/setup.md",
        "docs-site/blog/2026-08-01-launch.md",
    ]
    assert not _src_errors(paths), "Docusaurus markdown under docs-site/ must not be flagged"


def test_any_depth_libs_md_exempt_vendored():
    # vendor-don't-import: a dir literally named libs/ at ANY depth carries its
    # module's own docs (web/libs/, app/libs/ — not just root or src/**/libs/).
    paths = [
        "web/libs/ui-verify/examples/stack-up.md",
        "app/libs/rag/CUSTOMIZATION.md",
    ]
    assert not _src_errors(paths), "vendored-module docs under any */libs/ must not be flagged"


def test_gitignored_set_returns_unquoted_nonascii_paths(tmp_path):
    # quotePath regression: git escapes non-ASCII by default; the ignore-set must
    # carry REAL paths or en-dash-named artifacts get gated despite being ignored.
    import subprocess as sp

    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True, timeout=15)
    (tmp_path / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    (tmp_path / "artifacts").mkdir()
    name = "run – result.md"  # en dash in filename
    (tmp_path / "artifacts" / name).write_text("x", encoding="utf-8")
    got = cs._gitignored_files(tmp_path)
    assert f"artifacts/{name}" in got, got


# ── sites/<slug>/ nested roots (upstream proposal from web-ecommerce-factory, 2026-08-08) ──


def _paths_violations(paths):
    """Run check_structure over arbitrary repo-relative paths; return flagged paths."""
    return {v["file"] for v in cs.check_structure(REPO_ROOT, files=list(paths))}


def test_site_package_markdown_is_allowed():
    """A factory project produces sites into sites/<slug>/, each a self-contained deliverable
    whose docs must stay WITH it (brand isolation: one client's strategy must never land in the
    factory's shared docs/). Same nested-root reasoning as docs-site/ — without this branch the
    catch-all flags every per-site doc as "unexpected location" and instructs the project to
    violate the policy its own docs/README.md wrote down first."""
    flagged = _paths_violations(
        [
            "sites/bhdtrade/INDEX.md",
            "sites/bhdtrade/page-layouts.md",
            "sites/bhdtrade/BHD_global_market_strategy.md",
            "sites/acme/README.md",
        ]
    )
    assert flagged == set(), f"site-package docs must not be flagged: {sorted(flagged)}"


def test_markdown_outside_a_site_package_still_flagged():
    """The allowance is scoped — it must not become a blanket amnesty."""
    flagged = _paths_violations(["random_dir/STRAY.md"])
    assert any("STRAY.md" in f for f in flagged), f"stray doc must still be flagged: {flagged}"


# --------------------------------------------------------------------------------------
# T12.11 (01M1VHCH1) — the registry-drift guard, moved from a test nobody runs into the gate.
# --------------------------------------------------------------------------------------


def _hub_fixture(tmp_path: Path, extra_types: list[str] | None = None) -> Path:
    """A HUB-shaped tree whose `scaffold.py` declares the LIVE registry's types plus any extras.

    `_scaffold_registry_drift` reads the registry through the loaded `check_structure` module —
    i.e. the REAL `_doc_registry` — so the fixture varies only the half it can vary: the declared
    SCAFFOLD_TYPES. An `extra` is exactly the defect shape: a new scaffold type the registry has
    not learned about. (My first cut varied the scaffold half down to two types and the guard
    correctly reported the other eleven as unknown — the mechanism was right and the fixture was
    lying about what it isolated.)
    """
    cs = _load_check_structure()
    types = sorted(set(cs._doc_registry.ALL_TYPES) | set(extra_types or []))
    (tmp_path / "src" / "fabrik").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "src" / "fabrik" / "scaffold.py").write_text(
        "SCAFFOLD_TYPES = {" + ", ".join(repr(x) for x in types) + "}\n"
    )
    return tmp_path


def _drift(root: Path) -> list[str]:
    cs = _load_check_structure()
    return cs._scaffold_registry_drift(root)


def test_the_drift_guard_fires_on_a_type_missing_from_the_registry(tmp_path: Path) -> None:
    """The exact defect: `ALL_TYPES` carried 12 of the registry's 13 types, `office-extension` was
    absent, and the grader that would have caught it lived in `tests/test_doc_registry.py` — RED for
    as long as the drift, because the hub's pytest leg is OFF by design (a 5,913-test suite would
    brick every completion gate three sessions run). A guard nothing executes is not a guard, so
    the assertion now rides a gate-wired check."""
    root = _hub_fixture(tmp_path, extra_types=["quantum-api"])
    msgs = _drift(root)
    assert len(msgs) == 1, msgs
    assert "quantum-api" in msgs[0] and "missing from ALL_TYPES" in msgs[0]
    assert "no docs allowlist" in msgs[0], "the message must name the CONSEQUENCE, not just the set"


def test_the_drift_guard_is_silent_when_the_two_agree(tmp_path: Path) -> None:
    """The live pair, mirrored into a fixture: no extras, no findings."""
    assert _drift(_hub_fixture(tmp_path)) == []


def test_the_drift_guard_stands_down_in_a_project(tmp_path: Path) -> None:
    """`src/fabrik/scaffold.py` is hub-only and never synced. In a project the guard must return on
    the first `if` and import nothing — as permissive there as the check was before."""
    import shutil

    root = _hub_fixture(tmp_path, extra_types=["quantum-api"])
    assert _drift(root), "the premise — this tree drifts while scaffold.py is present"
    shutil.rmtree(root / "src")
    assert _drift(root) == [], "a project has no SCAFFOLD_TYPES, and that is not a defect"


def test_the_shipped_registry_and_scaffold_actually_agree() -> None:
    """The live assertion, not a fixture's: this repo's own two halves must match."""
    assert _drift(REPO_ROOT) == []


def test_a_missing_registry_name_is_not_reported_as_an_unreadable_one(tmp_path: Path) -> None:
    """Round 3 of the Phase E review: `if not declared:` could not tell `None` (no SCAFFOLD_TYPES
    assignment anywhere in the module) from `set()` (found it, no string literals in it), so a
    RENAMED or MOVED constant sent the operator hunting a comprehension that does not exist.
    Both are "parity was NOT checked" — they are not the same instruction to the reader."""
    absent = tmp_path / "absent"
    (absent / "src" / "fabrik").mkdir(parents=True)
    (absent / "docs").mkdir()
    (absent / "src" / "fabrik" / "scaffold.py").write_text("SOMETHING_ELSE = {'a'}\n")

    unreadable = tmp_path / "unreadable"
    (unreadable / "src" / "fabrik").mkdir(parents=True)
    (unreadable / "docs").mkdir()
    (unreadable / "src" / "fabrik" / "scaffold.py").write_text(
        "_T = ('a',)\nSCAFFOLD_TYPES = frozenset(_T)\n"
    )

    a, u = _drift(absent), _drift(unreadable)
    assert a and u, (a, u)
    assert "no SCAFFOLD_TYPES assignment found" in a[0], a[0]
    assert "carries no string literals" in u[0], u[0]
    assert a[0] != u[0], "two different facts reported with one message"
    for msg in (a[0], u[0]):
        assert "This is not a pass" in msg
