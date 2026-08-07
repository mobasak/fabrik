"""Behavior Contract for Phase C — type-aware scaffold doc seeding (driven by the registry SSOT).

Two layers:
  1. Unit tests of `_type_seeds_doc` — the pure gating decision per (type, doc).
  2. Integration tests through `_scaffold_shared` — the seeding loop actually skips/keeps the
     right docs on disk.

Grounded deviation from the plan's criterion #2 (documented): `data-contract.md` keeps its
deliberate all-but-docusaurus behavior rather than a `needs_database` gate — `use_database`
defaults False even for saas-skeleton/static-site (which legitimately carry the contract), so
gating on it would wrongly strip it from them and break `test_static_site_seeds_contract`.
Type-awareness IS applied to the deployed + saas buckets (the primary defect-4 win).
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from fabrik import scaffold

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_registry():
    spec = importlib.util.spec_from_file_location(
        "_doc_registry", REPO_ROOT / "scripts" / "enforcement" / "_doc_registry.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_doc_registry"] = mod
    spec.loader.exec_module(mod)
    return mod


reg = _load_registry()


# ---------------------------------------------------------------------------------------
# Layer 1 — unit tests of the pure gating decision
# ---------------------------------------------------------------------------------------
def test_headless_python_api_skips_product_docs_keeps_deployed_and_universal():
    for dest in ("docs/BUSINESS_MODEL.md", "docs/STRATEGIC_BACKLOG.md"):
        assert not scaffold._type_seeds_doc(reg, "python-api", dest), (
            f"python-api should skip {dest}"
        )
    for dest in (
        "docs/SERVICES.md",
        "docs/OPERATIONS.md",
        "docs/RESILIENCE.md",
        "README.md",
        "docs/QUICKSTART.md",
    ):
        assert scaffold._type_seeds_doc(reg, "python-api", dest), f"python-api should seed {dest}"


def test_saas_seeds_product_docs():
    for dest in ("docs/BUSINESS_MODEL.md", "docs/STRATEGIC_BACKLOG.md", "docs/SERVICES.md"):
        assert scaffold._type_seeds_doc(reg, "saas-skeleton", dest)


def test_client_app_skips_deployed_docs():
    # chrome-extension / mobile-app / desktop-app ship no backend service
    for t in ("chrome-extension", "mobile-app", "desktop-app"):
        for dest in (
            "docs/SERVICES.md",
            "docs/OPERATIONS.md",
            "docs/RESILIENCE.md",
            "docs/BUSINESS_MODEL.md",
        ):
            assert not scaffold._type_seeds_doc(reg, t, dest), f"{t} should skip {dest}"
        # but universal docs still seed
        assert scaffold._type_seeds_doc(reg, t, "README.md")


def test_data_contract_kept_for_all_types_leak_guard_is_separate():
    # _type_seeds_doc returns True for data on every type (the docusaurus leak guard is applied
    # separately by the caller via _NO_DATA_CONTRACT_TYPES)
    for t in ("python-api", "saas-skeleton", "chrome-extension", "docusaurus"):
        assert scaffold._type_seeds_doc(reg, t, "docs/data-contract.md")


# ---------------------------------------------------------------------------------------
# Layer 2 — integration through _scaffold_shared
# ---------------------------------------------------------------------------------------
_DOC_TEMPLATES = [
    "PROJECT_INDEX_TEMPLATE.md",
    "PROJECT_README_TEMPLATE.md",
    "CHANGELOG_TEMPLATE.md",
    "DOCS_INDEX_TEMPLATE.md",
    "QUICKSTART_TEMPLATE.md",
    "CONFIGURATION_TEMPLATE.md",
    "TROUBLESHOOTING_TEMPLATE.md",
    "BUSINESS_MODEL_TEMPLATE.md",
    "STRATEGIC_BACKLOG_TEMPLATE.md",
    "SERVICES_TEMPLATE.md",
    "RESILIENCE_TEMPLATE.md",
    "OPERATIONS_TEMPLATE.md",
    "FEATURES_TEMPLATE.md",
    "data-contract-template.md",
]


@pytest.fixture()
def mock_root():
    """Minimal fabrik root sufficient for _scaffold_shared to run past its required-asset
    checks (mirrors the proven harness in test_scaffold_logging.py)."""
    d = Path(tempfile.mkdtemp())
    scaffold_tpl = d / "templates" / "scaffold" / "docs"
    scaffold_tpl.mkdir(parents=True)
    for tpl in _DOC_TEMPLATES:
        (scaffold_tpl / tpl).write_text("# [Project Name]\n\nYYYY-MM-DD\n[Brief description]\n")
    # required fabrik assets _scaffold_shared copies (else it raises FileNotFoundError)
    (d / ".windsurfrules").write_text("# rules\n")
    (d / ".windsurf" / "rules").mkdir(parents=True)
    (d / ".windsurf" / "rules" / "10-python.md").write_text("# rules\n")
    (d / ".windsurf" / "workflows").mkdir(parents=True)
    (d / ".windsurf" / "workflows" / "test.md").write_text("# wf\n")
    (d / "AGENTS.md").write_text("# AGENTS\n")
    (d / "AGENTS-compact.md").write_text("# AGENTS-compact\n")
    (d / "opencode.json").write_text("{}\n")
    (d / ".pre-commit-config.yaml").write_text("repos: []\n")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _seed(mock_root: Path, project_type: str) -> Path:
    project_dir = mock_root / f"proj-{project_type}"
    project_dir.mkdir()
    with (
        patch.object(scaffold, "FABRIK_ROOT", mock_root),
        patch.object(scaffold, "TEMPLATE_DIR", mock_root / "templates" / "scaffold"),
        patch.object(scaffold, "FABRIK_AGENTS_MD", mock_root / "AGENTS.md"),
        patch("subprocess.run"),
    ):
        scaffold._scaffold_shared(project_dir, "svc", "Test", "2026-07-11", 8099, project_type)
    return project_dir


def test_python_api_seeding_is_type_aware(mock_root: Path):
    p = _seed(mock_root, "python-api")
    # universal + deployed docs present
    assert (p / "README.md").exists()
    assert (p / "docs" / "SERVICES.md").exists()
    assert (p / "docs" / "data-contract.md").exists()  # preserved (grounded deviation)
    # product (saas) docs NOT seeded for a headless api
    assert not (p / "docs" / "BUSINESS_MODEL.md").exists()
    assert not (p / "docs" / "STRATEGIC_BACKLOG.md").exists()


def test_saas_seeding_gets_product_docs(mock_root: Path):
    p = _seed(mock_root, "saas-skeleton")
    assert (p / "docs" / "BUSINESS_MODEL.md").exists()
    assert (p / "docs" / "STRATEGIC_BACKLOG.md").exists()
    assert (p / "docs" / "SERVICES.md").exists()
    assert (p / "docs" / "data-contract.md").exists()


def test_docusaurus_skips_data_contract_and_deployed_docs(mock_root: Path):
    p = _seed(mock_root, "docusaurus")
    assert not (p / "docs" / "data-contract.md").exists()  # leak guard honored
    assert not (p / "docs" / "SERVICES.md").exists()  # not a deployed backend
    assert (p / "README.md").exists()  # universal still seeded


# --- crash-safety: a registry that raises on use degrades to full seeding, never breaks
def test_should_seed_doc_never_raises_on_malformed_registry():
    class _Bad:
        @property
        def PROJECT_DOCS(self):  # noqa: N802
            raise RuntimeError("schema drift")

    # any registry-use error → seed (True), never propagate
    assert scaffold._should_seed_doc(_Bad(), "python-api", "docs/BUSINESS_MODEL.md") is True
    # None registry → seed everything (prior full-seed behavior)
    assert scaffold._should_seed_doc(None, "chrome-extension", "docs/SERVICES.md") is True


# --- (d) registry-unavailable fallback: seeding degrades to the full untyped set (no gating)
def test_registry_unavailable_falls_back_to_full_seeding(mock_root: Path):
    with patch.object(scaffold, "_load_doc_registry", return_value=None):
        p = _seed(mock_root, "python-api")
    # with the registry off, the pre-change behavior returns: product docs ARE seeded again
    assert (p / "docs" / "BUSINESS_MODEL.md").exists()
    assert (p / "README.md").exists()


# --- the generalized leak guard covers ANY data-bucket doc for docusaurus, not just by-name.
#     Proven with a SYNTHETIC second data doc (not data-contract.md) so the by-name guard can't
#     be what catches it — only the bucket-based path can.
def test_data_leak_guard_generalizes_to_bucket():
    from types import SimpleNamespace

    reg = _load_registry()
    fake_row = SimpleNamespace(
        name="docs/metrics-contract.md",
        applies_to=frozenset({"data"}),
        template="x",
        trigger="",
        fills="agent",
    )
    fake_reg = SimpleNamespace(PROJECT_DOCS=(fake_row,), TYPE_BUCKETS=reg.TYPE_BUCKETS)
    assert scaffold._is_data_doc(fake_reg, "docs/metrics-contract.md")
    # docusaurus skips a NON-data-contract data doc purely via the bucket guard
    assert scaffold._should_seed_doc(fake_reg, "docusaurus", "docs/metrics-contract.md") is False
    # a deployed type keeps it
    assert scaffold._should_seed_doc(fake_reg, "python-api", "docs/metrics-contract.md") is True
    # and the real registry's data-contract is guarded for docusaurus too
    assert scaffold._should_seed_doc(reg, "docusaurus", "docs/data-contract.md") is False


def test_deployment_doc_is_in_the_template_map_and_gated_to_deployed():
    # Template-wave regression (2026-08-07): the registry declared docs/DEPLOYMENT.md
    # (deployed bucket) but SHARED_TEMPLATE_MAP never carried the template — seeding
    # iterates the MAP, so the doc was silently never seeded for any type.
    assert scaffold.SHARED_TEMPLATE_MAP.get("docs/DEPLOYMENT_TEMPLATE.md") == "docs/DEPLOYMENT.md"
    assert scaffold._type_seeds_doc(reg, "python-api", "docs/DEPLOYMENT.md")
    assert not scaffold._type_seeds_doc(reg, "chrome-extension", "docs/DEPLOYMENT.md")
