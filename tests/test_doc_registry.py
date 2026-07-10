"""Behavior Contract for the canonical project-doc registry (SSOT).

Covers the Phase-A acceptance criteria: type-aware allowlist derivation, the None-union,
the grandfather / no-regression guarantee vs today's hard-coded allowlist, and registry
integrity (real buckets + on-disk templates).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_REG_PATH = REPO_ROOT / "scripts" / "enforcement" / "_doc_registry.py"


def _load_registry():
    """Import _doc_registry the same way check_structure will — same-dir, stdlib-only."""
    spec = importlib.util.spec_from_file_location("_doc_registry", _REG_PATH)
    assert spec and spec.loader, f"registry not importable at {_REG_PATH}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_doc_registry"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:
        sys.modules.pop("_doc_registry", None)  # don't leave a half-loaded module cached
        raise
    return mod


reg = _load_registry()


# --- (a) a headless python-api excludes product/data/gui docs, includes universal+deployed
def test_python_api_allowlist_excludes_product_and_gui_docs():
    allow = reg.docs_allowlist("python-api")
    for excluded in ("BUSINESS_MODEL.md", "data-contract.md", "ui-design.md", "design-system.md", "STRATEGIC_BACKLOG.md"):
        assert excluded not in allow, f"python-api should not allow {excluded}"
    for included in ("README.md", "QUICKSTART.md", "SERVICES.md", "OPERATIONS.md", "RESILIENCE.md"):
        assert included in allow, f"python-api should allow {included}"


# --- (b) a saas-skeleton includes the product + gui docs (data docs are db-driven, so
#         they live only in the permissive None-union, not any per-type allowlist).
def test_saas_allowlist_includes_business_model_and_gui():
    allow = reg.docs_allowlist("saas-skeleton")
    for included in ("BUSINESS_MODEL.md", "STRATEGIC_BACKLOG.md", "ui-design.md", "design-system.md"):
        assert included in allow, f"saas-skeleton should allow {included}"
    # data docs are NOT type-guaranteed (db-driven) — absent from the per-type allowlist
    assert "data-contract.md" not in allow


# --- a client-app type (mobile-app) gets gui but NOT deployed/saas docs
def test_mobile_app_allowlist_has_gui_not_deployed():
    allow = reg.docs_allowlist("mobile-app")
    assert "ui-design.md" in allow and "design-system.md" in allow
    for excluded in ("SERVICES.md", "OPERATIONS.md", "RESILIENCE.md", "BUSINESS_MODEL.md"):
        assert excluded not in allow, f"mobile-app should not allow {excluded}"


# --- (c) None == the union of ALL buckets = every registry doc that lives flat in docs/
def test_none_allowlist_is_union_of_all_buckets():
    all_flat = {
        r.name.split("/", 1)[1]
        for r in reg.PROJECT_DOCS
        if r.name.startswith("docs/") and r.name.count("/") == 1
    }
    assert reg.docs_allowlist(None) == frozenset(all_flat)
    # the None-union is permissive: spans deployed + gui + saas + data docs (check_structure use)
    for name in ("SERVICES.md", "ui-design.md", "BUSINESS_MODEL.md", "data-contract.md"):
        assert name in reg.docs_allowlist(None)
    # and it is a superset of every specific type's (stricter) allowlist
    for t in reg.ALL_TYPES:
        assert reg.docs_allowlist(t) <= reg.docs_allowlist(None)


# --- (d) grandfather / no-regression: allowlist ∪ LEGACY_TOLERATED ⊇ today's hard-coded set
def test_grandfather_covers_todays_hardcoded_allowlist():
    # The literal set check_structure.py carried BEFORE this change (Phase B replaces it).
    todays_hardcoded = {
        "README.md", "QUICKSTART.md", "CONFIGURATION.md", "TROUBLESHOOTING.md",
        "BUSINESS_MODEL.md", "SERVICES.md", "OPERATIONS.md", "DEPLOYMENT.md",
        "EXTERNAL_SYSTEMS.md", "FAQ.md", "FEATURES.md", "TESTING.md",
        "owner_ozgur_basak.md",
    }
    tolerated = reg.docs_allowlist(None) | reg.LEGACY_TOLERATED
    missing = todays_hardcoded - tolerated
    assert not missing, f"regression: these would newly WARN: {sorted(missing)}"


# --- (e) registry integrity: real buckets + on-disk templates
def test_every_row_names_a_real_bucket():
    valid_buckets = set(reg.TYPE_BUCKETS)
    for row in reg.PROJECT_DOCS:
        assert row.applies_to, f"{row.name} has empty applies_to"
        for b in row.applies_to:
            assert b in valid_buckets, f"{row.name} names unknown bucket {b!r}"


def test_bucket_type_sets_are_subsets_of_all_types():
    """A typo in a bucket's type set (e.g. 'python_api') would silently drop every doc in
    that bucket from the allowlist + seeding. Guard: each bucket's types ⊆ ALL_TYPES."""
    for name, types in reg.TYPE_BUCKETS.items():
        stray = types - reg.ALL_TYPES
        assert not stray, f"bucket {name!r} contains non-SCAFFOLD types: {sorted(stray)}"


def test_docs_allowlist_needs_database_is_symmetric_with_seed_rows():
    """A DB-backed project legitimately carries data-contract.md — the per-type allowlist
    must include it when needs_database, mirroring seed_rows (closes the SSOT split).
    Checked across several types, not just one, so a per-type asymmetry can't hide."""
    for t in ("python-api", "saas-skeleton", "node-api", "file-worker"):
        assert "data-contract.md" not in reg.docs_allowlist(t)  # no-DB default excludes it
        assert "data-contract.md" in reg.docs_allowlist(t, needs_database=True)
        seeded = {r.name for r in reg.seed_rows(t, needs_database=True)}
        assert "docs/data-contract.md" in seeded, f"{t}: seed/allowlist asymmetry"


def test_unknown_type_fails_loud_not_silent_empty():
    """A typo'd/unknown type must raise, never silently return an empty set (which would
    make check_structure false-WARN every doc or scaffold seed nothing)."""
    import pytest

    for bad in ("python_api", "not-a-type", "PYTHON-API", ""):
        with pytest.raises(ValueError):
            reg.docs_allowlist(bad)
        with pytest.raises(ValueError):
            reg.seed_rows(bad)
    # None is still valid (the permissive union) — must NOT raise
    assert reg.docs_allowlist(None)


def test_every_template_exists_on_disk():
    template_root = REPO_ROOT / "templates" / "scaffold"
    for row in reg.PROJECT_DOCS:
        if row.template is None:
            continue
        assert (template_root / row.template).is_file(), (
            f"{row.name}: template templates/scaffold/{row.template} not found on disk"
        )


def test_registry_is_stdlib_only():
    """The module is synced into bare projects — every import must be stdlib (or __future__).
    Guards the STDLIB-ONLY contract that a same-dir project-side import depends on."""
    import ast

    tree = ast.parse(_REG_PATH.read_text())
    stdlib = set(sys.stdlib_module_names) | {"__future__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in stdlib, f"non-stdlib import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert node.level == 0 and top in stdlib, f"non-stdlib import from: {node.module}"


def test_all_types_matches_scaffold_source_of_truth():
    """ALL_TYPES must mirror scaffold.py's SCAFFOLD_TYPES exactly — else a new scaffold
    type silently gets no docs. This is the drift the whole registry exists to prevent."""
    from fabrik.scaffold import SCAFFOLD_TYPES

    assert reg.ALL_TYPES == frozenset(SCAFFOLD_TYPES), (
        f"ALL_TYPES drifted from SCAFFOLD_TYPES: "
        f"only-in-registry={reg.ALL_TYPES - SCAFFOLD_TYPES}, "
        f"only-in-scaffold={SCAFFOLD_TYPES - reg.ALL_TYPES}"
    )


def test_seed_rows_type_aware_and_data_gated():
    # python-api WITHOUT a database seeds no data-contract; saas WITH a db does.
    py_names = {r.name for r in reg.seed_rows("python-api", needs_database=False)}
    assert "docs/data-contract.md" not in py_names
    assert "docs/BUSINESS_MODEL.md" not in py_names  # not a saas type
    assert "docs/SERVICES.md" in py_names  # deployed
    saas_names = {r.name for r in reg.seed_rows("saas-skeleton", needs_database=True)}
    assert "docs/data-contract.md" in saas_names
    assert "docs/BUSINESS_MODEL.md" in saas_names
    # saas WITHOUT a db must NOT seed the data-contract (the data gate is real)
    saas_no_db = {r.name for r in reg.seed_rows("saas-skeleton", needs_database=False)}
    assert "docs/data-contract.md" not in saas_no_db
    assert "docs/BUSINESS_MODEL.md" in saas_no_db  # saas doc is unconditional for saas type
    # None-template rows are never seeded
    assert all(r.template is not None for r in reg.seed_rows("saas-skeleton", needs_database=True))
