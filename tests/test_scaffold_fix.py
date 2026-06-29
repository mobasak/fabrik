"""Tests for fix_project() AFCL preservation + reference-doc refresh behavior."""

import os
from pathlib import Path

import pytest

from fabrik.scaffold import fix_project

FABRIK_ROOT = Path("/opt/fabrik")
requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik (not available in CI)",
)


class TestScaffoldHubGuard:
    """scaffold/fix must refuse to target the Fabrik hub (/opt/fabrik) itself.

    Regression guard: writing the project synced-gitignore block to the hub
    would ignore the hub's own canonical sources (.windsurf/, CLAUDE.md, …).
    """

    def test_fix_project_refuses_hub(self):
        with pytest.raises(ValueError, match="hub"):
            fix_project(FABRIK_ROOT)

    def test_assert_not_hub_refuses_hub_and_dotpath(self):
        from fabrik.scaffold import _assert_not_hub

        with pytest.raises(ValueError, match="hub"):
            _assert_not_hub(FABRIK_ROOT)
        # Path normalization: /opt/fabrik/. resolves to the hub.
        with pytest.raises(ValueError, match="hub"):
            _assert_not_hub(FABRIK_ROOT / ".")

    def test_assert_not_hub_allows_non_hub(self):
        from fabrik.scaffold import _assert_not_hub

        # A normal project path must not trip the guard.
        _assert_not_hub(Path("/opt/some-other-project"))

    def test_assert_not_hub_allows_hub_subdir(self):
        """Under-block guard: a subdir of the hub is NOT the hub and must pass."""
        from fabrik.scaffold import _assert_not_hub

        _assert_not_hub(FABRIK_ROOT / "src")  # must not raise

    def test_assert_not_hub_blocks_symlink_to_hub(self, tmp_path):
        """Over-block guard: resolve() must follow a symlink and still block the hub."""
        from fabrik.scaffold import _assert_not_hub

        link = tmp_path / "hublink"
        link.symlink_to(FABRIK_ROOT)
        with pytest.raises(ValueError, match="hub"):
            _assert_not_hub(link)


@requires_fabrik_env
class TestFixProjectAFCLPreservation:
    """fix_project() must NOT overwrite project-local AFCL.md content."""

    def test_existing_afcl_with_custom_content_is_preserved(self, tmp_path):
        """AFCL.md with project-specific findings survives fabrik fix."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        custom_afcl = "# AFCL\n\n## Friction 1\n\nProject-local lore must survive.\n"
        afcl_path = project_dir / "AFCL.md"
        afcl_path.write_text(custom_afcl)

        added = fix_project(project_dir, dry_run=False)

        assert afcl_path.read_text() == custom_afcl, "AFCL.md was overwritten"
        assert not any("AFCL.md" in entry for entry in added), (
            "fix_project reported AFCL change despite preserving it"
        )

    def test_missing_afcl_is_created_from_template(self, tmp_path):
        """AFCL.md is created from template when missing."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        afcl_path = project_dir / "AFCL.md"
        assert not afcl_path.exists()

        added = fix_project(project_dir, dry_run=False)

        if (FABRIK_ROOT / "templates" / "scaffold" / "AFCL_TEMPLATE.md").exists():
            assert afcl_path.exists(), "AFCL.md was not created from template"
            assert "AFCL.md (created)" in added

    def test_dry_run_reports_afcl_only_when_missing(self, tmp_path):
        """Dry-run preview matches the live behavior: AFCL only-if-missing."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # Case 1: AFCL exists -> dry_run must NOT report it
        (project_dir / "AFCL.md").write_text("# Custom AFCL\n")
        added_with = fix_project(project_dir, dry_run=True)
        assert not any("AFCL.md" in entry for entry in added_with), (
            "dry_run reported AFCL.md change when file already exists"
        )

        # Case 2: AFCL missing -> dry_run must report (created)
        (project_dir / "AFCL.md").unlink()
        added_without = fix_project(project_dir, dry_run=True)
        if (FABRIK_ROOT / "templates" / "scaffold" / "AFCL_TEMPLATE.md").exists():
            assert "AFCL.md (created)" in added_without


@requires_fabrik_env
class TestFixProjectReferenceDocsRefresh:
    """fix_project() MUST overwrite reference docs from canonical Fabrik root."""

    def test_stack_decision_guide_is_overwritten_when_target_exists(self, tmp_path):
        """technology-stack-decision-guide.md is refreshed even if target exists."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ref_dir = project_dir / "docs" / "reference"
        ref_dir.mkdir(parents=True)
        target = ref_dir / "technology-stack-decision-guide.md"
        stale_marker = "# STALE LOCAL COPY — must be replaced\n"
        target.write_text(stale_marker)

        added = fix_project(project_dir, dry_run=False)

        canonical = (FABRIK_ROOT / "docs" / "reference" / "technology-stack-decision-guide.md").read_text()
        assert target.read_text() == canonical, "Reference doc was not refreshed from master"
        assert target.read_text() != stale_marker
        assert any(
            "technology-stack-decision-guide.md (refreshed from master)" in e for e in added
        )

    def test_prebuilt_containers_is_overwritten_when_target_exists(self, tmp_path):
        """prebuilt-app-containers.md is refreshed even if target exists."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ref_dir = project_dir / "docs" / "reference"
        ref_dir.mkdir(parents=True)
        target = ref_dir / "prebuilt-app-containers.md"
        target.write_text("# stale\n")

        added = fix_project(project_dir, dry_run=False)

        canonical = (FABRIK_ROOT / "docs" / "reference" / "prebuilt-app-containers.md").read_text()
        assert target.read_text() == canonical
        assert any("prebuilt-app-containers.md (refreshed from master)" in e for e in added)

    def test_kilo_naming_is_overwritten_when_target_exists(self, tmp_path):
        """KILO_AGENT_NAMING.md is refreshed even if target exists."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        kilo_dir = project_dir / "docs" / "reference" / "kilo"
        kilo_dir.mkdir(parents=True)
        target = kilo_dir / "KILO_AGENT_NAMING.md"
        target.write_text("# stale\n")

        added = fix_project(project_dir, dry_run=False)

        if (FABRIK_ROOT / "docs" / "reference" / "kilo" / "KILO_AGENT_NAMING.md").exists():
            canonical = (FABRIK_ROOT / "docs" / "reference" / "kilo" / "KILO_AGENT_NAMING.md").read_text()
            assert target.read_text() == canonical
            assert any("KILO_AGENT_NAMING.md (refreshed from master)" in e for e in added)

    def test_kilo_47_agents_json_is_overwritten_when_target_exists(self, tmp_path):
        """kilo_47_agents_final.json is refreshed even if target exists."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        scripts_dir = project_dir / "scripts"
        scripts_dir.mkdir()
        target = scripts_dir / "kilo_47_agents_final.json"
        target.write_text("{\"stale\": true}\n")

        added = fix_project(project_dir, dry_run=False)

        if (FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json").exists():
            canonical = (FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json").read_text()
            assert target.read_text() == canonical
            assert any("kilo_47_agents_final.json (refreshed from master)" in e for e in added)

    def test_dry_run_previews_reference_doc_refresh(self, tmp_path):
        """dry_run accurately reports the 4 reference docs as refreshed."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        added = fix_project(project_dir, dry_run=True)

        if (FABRIK_ROOT / "docs" / "reference" / "technology-stack-decision-guide.md").exists():
            assert any(
                "technology-stack-decision-guide.md (refreshed from master)" in e for e in added
            )
        if (FABRIK_ROOT / "docs" / "reference" / "prebuilt-app-containers.md").exists():
            assert any("prebuilt-app-containers.md (refreshed from master)" in e for e in added)
        if (FABRIK_ROOT / "docs" / "reference" / "kilo" / "KILO_AGENT_NAMING.md").exists():
            assert any("KILO_AGENT_NAMING.md (refreshed from master)" in e for e in added)
        if (FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json").exists():
            assert any("kilo_47_agents_final.json (refreshed from master)" in e for e in added)
