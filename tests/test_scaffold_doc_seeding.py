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
    # BUSINESS_MODEL is product-facing and a headless API has no product story to tell.
    assert not scaffold._type_seeds_doc(reg, "python-api", "docs/BUSINESS_MODEL.md"), (
        "python-api should skip docs/BUSINESS_MODEL.md"
    )
    # ⚠️ STRATEGIC_BACKLOG moved from product-only to UNIVERSAL in 245cb5e7 (2026-08-27,
    # operator rule: every type seeds it, because every project accrues deferred work). This
    # assertion still demanded the old contract and had been RED for two days — unnoticed
    # because the hub's `final_gate` does not run pytest (`_ci_runs_pytest` is false here, and
    # as of 7051a25a there are no workflow files at all), so nothing on this repo executes its
    # own suite unless a human does. Found by a background run started for an unrelated reason.
    assert scaffold._type_seeds_doc(reg, "python-api", "docs/STRATEGIC_BACKLOG.md"), (
        "STRATEGIC_BACKLOG is universal since 245cb5e7 — every type seeds it"
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
    # STRATEGIC_BACKLOG is UNIVERSAL since 245cb5e7 — the integration-layer twin of the same
    # stale assertion fixed above. Both sites demanded the pre-2026-08-27 contract; the registry
    # change updated neither, and nothing ran them.
    assert (p / "docs" / "STRATEGIC_BACKLOG.md").exists()


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


def test_docusaurus_config_excludes_internal_governance_docs(tmp_path):
    # fleet+infra finding 01M19JJNWK: Docusaurus publishes the whole docs/ tree, so internal Fabrik
    # docs in docs/ (seeded governance: DECISIONS/LESSONS_LEARNT/STRATEGIC_BACKLOG; pipeline
    # contracts: flows/ui-design/design-system) would land on a world-readable site. They must stay
    # PRESENT (governance requires docs/DECISIONS.md in every repo) but be content-docs EXCLUDED.
    proj = tmp_path / "proj-docs"
    proj.mkdir()
    scaffold._scaffold_docusaurus(proj, "mysite", "A docs site")
    cfg = (proj / "docusaurus.config.js").read_text()
    # the entries must live INSIDE the docs-preset exclude ARRAY, not merely somewhere in the file
    start = cfg.index("exclude: [")
    block = cfg[start : cfg.index("]", start)]
    for d in scaffold._DOCUSAURUS_UNPUBLISHED_DOCS:
        assert f"'**/{d}'" in block, f"{d} must be in the docusaurus content-docs exclude array"
    # setting `exclude` replaces the plugin default, so the defaults must be re-listed in the array
    assert "'**/_*.{js,jsx,ts,tsx,md,mdx}'" in block, (
        "docusaurus default excludes must be preserved"
    )
    # PRESENT half of present-but-unpublished: the seeded governance docs still SEED to docusaurus
    for dest in ("docs/DECISIONS.md", "docs/LESSONS_LEARNT.md", "docs/STRATEGIC_BACKLOG.md"):
        assert scaffold._type_seeds_doc(reg, "docusaurus", dest), (
            f"{dest} must still SEED to docusaurus"
        )


def test_decisions_doc_is_in_the_template_map_and_universal():
    # Same class as the 2026-08-07 DEPLOYMENT regression (decision-ledger plan-1 B6):
    # the registry declares docs/DECISIONS.md (universal governance surface) but the
    # template landed inert until SHARED_TEMPLATE_MAP carried it — seeding iterates the
    # MAP, so an unmapped registry doc is silently never seeded for any type.
    assert scaffold.SHARED_TEMPLATE_MAP.get("docs/DECISIONS_TEMPLATE.md") == "docs/DECISIONS.md"
    # universal: EVERY scaffold type seeds it — a headless api, a saas, and a client app alike
    for t in ("python-api", "saas-skeleton", "chrome-extension", "docusaurus"):
        assert scaffold._type_seeds_doc(reg, t, "docs/DECISIONS.md"), (
            f"{t} should seed docs/DECISIONS.md"
        )


# ---------------------------------------------------------------------------------------
# T06 — a new repo is born with the PLANS ownership markers (the T02a→T06 seam):
# docs_updater.py --adopt seeds `## Ownership (auto-generated)` + the marker pair into an
# EXISTING PLANS.md that lacks them; the scaffolder now ships that same block already in
# place, below the hand table, so a fresh repo needs no --adopt run to gain the surface.
# ---------------------------------------------------------------------------------------

# The exact seed `docs_updater.run_adopt()` writes when PLANS.md exists but has no markers
# (scripts/docs_updater.py, grep "Ownership (auto-generated)") — reproduced byte-for-byte.
_OWNERSHIP_SEED_BLOCK = (
    "\n## Ownership (auto-generated)\n\n"
    "<!-- AUTO-GENERATED:PLANS:START -->\n<!-- AUTO-GENERATED:PLANS:END -->\n"
)


def test_fresh_scaffold_plans_md_already_carries_the_ownership_markers(mock_root: Path):
    """RED before src/fabrik/scaffold.py's PLANS.md literal grows the block: a fresh
    `_scaffold_shared` must already produce docs/development/PLANS.md with the markers
    below the hand table, byte-equal to the docs_updater --adopt seed constant — so a new
    repo never needs a --adopt run just to gain the surface."""
    p = _seed(mock_root, "python-api")
    plans_md = p / "docs" / "development" / "PLANS.md"
    assert plans_md.exists()
    content = plans_md.read_text(encoding="utf-8")
    assert content.endswith(_OWNERSHIP_SEED_BLOCK), (
        f"docs/development/PLANS.md must end with the byte-for-byte ownership seed block; "
        f"got tail: {content[-200:]!r}"
    )
    # the hand table survives above the markers (never replaced, per the ticket's DO-NOT)
    assert "| (none) | - | - |" in content
    assert content.index("| (none) | - | - |") < content.index(
        "<!-- AUTO-GENERATED:PLANS:START -->"
    )


def test_fresh_scaffold_plans_md_is_regenerable_by_docs_updater_sync(mock_root: Path, monkeypatch):
    """RED before the scaffold literal gains the markers: `docs_updater.sync_plans_index()`
    must regenerate the block IN PLACE against a fresh scaffold's PLANS.md, and — since the
    scratch repo carries no docs/DECISIONS.md yet — the block's second header line must be
    the undeclared-merge-owner line (proves the block is real, not just matching text)."""
    p = _seed(mock_root, "python-api")

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import docs_updater as du

    monkeypatch.setattr(du, "PROJECT_ROOT", p)
    monkeypatch.setattr(du, "PLANS_DIR", p / "docs" / "development" / "plans")
    monkeypatch.setattr(du, "PLANS_INDEX", p / "docs" / "development" / "PLANS.md")

    changed, _msg = du.sync_plans_index()
    assert changed, (
        "a fresh scaffold's PLANS.md has no rows yet — --sync must still write the table"
    )

    content = (p / "docs" / "development" / "PLANS.md").read_text(encoding="utf-8")
    body = du.extract_block_body(content, du.PLANS_BLOCK_RE)
    assert body is not None, "sync_plans_index must find the markers it just regenerated"
    lines = body.splitlines()
    assert lines[1].startswith("<!-- Merge owner: UNDECLARED"), (
        f"second header line must be the undeclared-merge-owner line; got: {lines[1]!r}"
    )


# ---------------------------------------------------------------------------------------
# T06 — docs the ticket owes: the operating-model doc and the project-facing governance
# template name `--adopt`, not the retired "tail sweep" prose (D-154/D-155).
# ---------------------------------------------------------------------------------------
_OPERATING_MODEL_DOC = REPO_ROOT / "docs" / "reference" / "multi-agent-operating-model.md"
_GOVERNANCE_TEMPLATE = REPO_ROOT / "templates" / "governance" / "CLAUDE.md"


def test_operating_model_doc_names_adopt_not_tail_sweep():
    text = _OPERATING_MODEL_DOC.read_text(encoding="utf-8")
    assert "tail sweep" not in text, (
        "the retired 'agent-1's tail sweep' prose must be replaced by the --adopt step (D-154/D-155)"
    )
    assert "docs_updater.py --adopt" in text


def test_governance_template_names_adopt():
    text = _GOVERNANCE_TEMPLATE.read_text(encoding="utf-8")
    assert "tail sweep" not in text
    assert "docs_updater.py --adopt" in text
