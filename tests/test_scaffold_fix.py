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

    def test_assert_not_hub_blocks_hub_subdir(self):
        """Residual-risk R4 closed: a path INSIDE the hub is also refused."""
        from fabrik.scaffold import _assert_not_hub

        with pytest.raises(ValueError, match="hub"):
            _assert_not_hub(FABRIK_ROOT / "templates" / "x")

    def test_assert_not_hub_blocks_symlink_to_hub(self, tmp_path):
        """Over-block guard: resolve() must follow a symlink and still block the hub."""
        from fabrik.scaffold import _assert_not_hub

        link = tmp_path / "hublink"
        link.symlink_to(FABRIK_ROOT)
        with pytest.raises(ValueError, match="hub"):
            _assert_not_hub(link)

    @requires_fabrik_env
    def test_hub_is_refused_when_fabrik_root_points_elsewhere(self, tmp_path, monkeypatch):
        """W-508064a8: with FABRIK_ROOT pointed at a worktree, the real hub was 'not the hub'.

        That override is what the scaffold tests need (templates resolve through it), and on
        2026-09-24 it let test_fix_project_refuses_hub rewrite the shared checkout.
        """
        import fabrik.scaffold as scaffold

        monkeypatch.setattr(scaffold, "FABRIK_ROOT", tmp_path / "some-worktree")
        with pytest.raises(ValueError, match="hub"):
            scaffold._assert_not_hub(FABRIK_ROOT)
        with pytest.raises(ValueError, match="hub"):
            scaffold._assert_not_hub(FABRIK_ROOT / "templates" / "x")

    def test_any_hub_checkout_is_refused_by_its_markers(self, tmp_path, monkeypatch):
        """A hub checkout (a worktree or clone) is recognised by its own files, not its path."""
        import fabrik.scaffold as scaffold

        monkeypatch.setattr(scaffold, "FABRIK_ROOT", tmp_path / "elsewhere")
        # An old-revision clone (no synced manifest yet) is still a hub: the scaffolder is the marker.
        hub = tmp_path / "hub-clone"
        (hub / "src" / "fabrik").mkdir(parents=True)
        (hub / "src" / "fabrik" / "scaffold.py").write_text("")
        # A partial checkout where the marker path is a directory, or a dangling link, still counts.
        odd_dir = tmp_path / "partial-checkout"
        (odd_dir / "src" / "fabrik" / "scaffold.py").mkdir(parents=True)
        dangling = tmp_path / "dangling-checkout"
        (dangling / "src" / "fabrik").mkdir(parents=True)
        (dangling / "src" / "fabrik" / "scaffold.py").symlink_to(tmp_path / "gone")
        for target in (hub, hub / "docs" / "deep", odd_dir, dangling / "new-project"):
            with pytest.raises(ValueError, match="hub"):
                scaffold._assert_not_hub(target)

    def test_synced_project_files_do_not_make_a_hub(self, tmp_path, monkeypatch):
        """Over-block guard: a project carrying the hub's synced files is still scaffoldable."""
        import fabrik.scaffold as scaffold

        monkeypatch.setattr(scaffold, "FABRIK_ROOT", tmp_path / "elsewhere")
        project = tmp_path / "project"
        (project / "scripts" / "enforcement").mkdir(parents=True)
        (project / "scripts" / "fabrik_synced_manifest.py").write_text("")
        (project / "src" / "project").mkdir(parents=True)
        (project / "src" / "project" / "scaffold.py").write_text("")
        scaffold._assert_not_hub(project)
        scaffold._assert_not_hub(project / "not-yet-created")


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

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

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

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

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
        added_with = fix_project(project_dir, project_type="python-api", dry_run=True)
        assert not any("AFCL.md" in entry for entry in added_with), (
            "dry_run reported AFCL.md change when file already exists"
        )

        # Case 2: AFCL missing -> dry_run must report (created)
        (project_dir / "AFCL.md").unlink()
        added_without = fix_project(project_dir, project_type="python-api", dry_run=True)
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

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        canonical = (
            FABRIK_ROOT / "docs" / "reference" / "technology-stack-decision-guide.md"
        ).read_text()
        assert target.read_text() == canonical, "Reference doc was not refreshed from master"
        assert target.read_text() != stale_marker
        assert any("technology-stack-decision-guide.md (refreshed from master)" in e for e in added)

    def test_prebuilt_containers_is_overwritten_when_target_exists(self, tmp_path):
        """prebuilt-app-containers.md is refreshed even if target exists."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ref_dir = project_dir / "docs" / "reference"
        ref_dir.mkdir(parents=True)
        target = ref_dir / "prebuilt-app-containers.md"
        target.write_text("# stale\n")

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        canonical = (FABRIK_ROOT / "docs" / "reference" / "prebuilt-app-containers.md").read_text()
        assert target.read_text() == canonical
        assert any("prebuilt-app-containers.md (refreshed from master)" in e for e in added)

    def test_kilo_47_agents_json_is_overwritten_when_target_exists(self, tmp_path):
        """kilo_47_agents_final.json is refreshed even if target exists."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        scripts_dir = project_dir / "scripts"
        scripts_dir.mkdir()
        target = scripts_dir / "kilo_47_agents_final.json"
        target.write_text('{"stale": true}\n')

        added = fix_project(project_dir, project_type="python-api", dry_run=False)

        if (FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json").exists():
            canonical = (FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json").read_text()
            assert target.read_text() == canonical
            assert any("kilo_47_agents_final.json (refreshed from master)" in e for e in added)

    def test_dry_run_previews_reference_doc_refresh(self, tmp_path):
        """dry_run accurately reports the reference docs as refreshed."""
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        added = fix_project(project_dir, project_type="python-api", dry_run=True)

        if (FABRIK_ROOT / "docs" / "reference" / "technology-stack-decision-guide.md").exists():
            assert any(
                "technology-stack-decision-guide.md (refreshed from master)" in e for e in added
            )
        if (FABRIK_ROOT / "docs" / "reference" / "prebuilt-app-containers.md").exists():
            assert any("prebuilt-app-containers.md (refreshed from master)" in e for e in added)
        if (FABRIK_ROOT / "scripts" / "kilo_47_agents_final.json").exists():
            assert any("kilo_47_agents_final.json (refreshed from master)" in e for e in added)


@requires_fabrik_env
class TestFixProjectReadsTheDeclaredType:
    """W-526528b6: `fabrik fix` repaired every project from the python-api map unless --type was passed."""

    def _saas_project(self, tmp_path: Path) -> Path:
        project_dir = tmp_path / "saas-project"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: saas-project\ntype: saas-skeleton\n")
        return project_dir

    def test_declared_type_drives_the_repair(self, tmp_path):
        project_dir = self._saas_project(tmp_path)

        added = fix_project(project_dir, dry_run=False)

        assert "[unsupported-fix] server/Dockerfile" in added
        assert not (project_dir / "server").exists(), "a placeholder or stray dir was written"
        assert not (project_dir / "src").exists(), (
            "python-api files were seeded into a saas project"
        )

    def test_dry_run_reports_what_the_live_run_would(self, tmp_path):
        project_dir = self._saas_project(tmp_path)

        preview = fix_project(project_dir, dry_run=True)

        assert "[unsupported-fix] server/Dockerfile" in preview
        assert "server/Dockerfile" not in preview

    def test_explicit_type_overrides_the_declared_one(self, tmp_path):
        project_dir = self._saas_project(tmp_path)

        added = fix_project(project_dir, dry_run=True, project_type="python-api")

        assert not any("server/" in entry for entry in added)

    def test_no_declared_type_and_none_passed_is_refused(self, tmp_path):
        project_dir = tmp_path / "bare"
        (project_dir / ".git").mkdir(parents=True)

        with pytest.raises(ValueError, match="--type"):
            fix_project(project_dir, dry_run=True)
        assert list(project_dir.iterdir()) == [project_dir / ".git"]

    def test_cli_prints_the_refusal_and_exits_nonzero(self, tmp_path):
        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = tmp_path / "bare"
        (project_dir / ".git").mkdir(parents=True)

        result = CliRunner().invoke(cli, ["fix", str(project_dir), "--dry-run"])

        assert result.exit_code == 1
        assert "--type" in result.stderr
        assert "--type" not in result.stdout

    def test_cli_lists_unrepairable_files_apart_from_added_ones(self, tmp_path):
        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = self._saas_project(tmp_path)

        result = CliRunner().invoke(cli, ["fix", str(project_dir), "--dry-run"])

        assert result.exit_code == 1, "a project left incomplete must not exit 0"
        assert "not repairable by fix (re-run the scaffolder): server/Dockerfile" in result.stdout
        assert "📄 [unsupported-fix]" not in result.output
        assert "stay missing" in result.stderr

    def test_python_api_gpu_is_repaired_from_the_python_api_templates(self, tmp_path):
        """python-api-gpu shares the python-api layout, so its Dockerfile has a real template."""
        project_dir = tmp_path / "gpu-project"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: gpu-project\ntype: python-api-gpu\n")

        added = fix_project(project_dir, dry_run=False)

        assert "Dockerfile" in added
        assert not any(entry.startswith("[unsupported-fix]") for entry in added)
        assert "FROM" in (project_dir / "Dockerfile").read_text()

    def test_a_non_string_type_is_refused_not_crashed(self, tmp_path):
        project_dir = tmp_path / "odd"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: odd\ntype: [python-api]\n")

        with pytest.raises(ValueError, match="--type"):
            fix_project(project_dir, dry_run=True)

    def test_a_non_mapping_project_yaml_with_explicit_type_does_not_crash(self, tmp_path):
        project_dir = tmp_path / "listy"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("- a\n- b\n")

        fix_project(project_dir, dry_run=True, project_type="python-api")

    def test_cli_validate_checks_the_declared_type(self, tmp_path):
        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = self._saas_project(tmp_path)

        result = CliRunner().invoke(cli, ["validate", str(project_dir)])

        assert result.exit_code == 1
        assert "server/Dockerfile" in result.stdout
        assert f"Run: fabrik fix {project_dir}\n" in result.stdout, "the hint must not pin a type"

    def test_cli_validate_without_a_type_is_refused(self, tmp_path):
        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = tmp_path / "bare"
        (project_dir / ".git").mkdir(parents=True)

        result = CliRunner().invoke(cli, ["validate", str(project_dir)])

        assert result.exit_code == 1
        assert "--type" in result.stderr

    def test_a_type_without_its_own_list_is_held_to_the_shared_files(self, tmp_path):
        """wordpress has no TYPE_REQUIRED_FILES entry; it must not inherit python-api's Dockerfile."""
        from fabrik.scaffold import validate_project

        project_dir = tmp_path / "wp"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: wp\ntype: wordpress\n")

        _, missing = validate_project(project_dir, "wordpress")

        assert "Dockerfile" not in missing
        assert not any(
            e.startswith("[unsupported-fix]") for e in fix_project(project_dir, dry_run=True)
        )

    def test_refusal_hint_names_the_project_path(self, tmp_path):
        project_dir = tmp_path / "typeless"
        (project_dir / ".git").mkdir(parents=True)
        (project_dir / "project.yaml").write_text("name: typeless\n")

        with pytest.raises(ValueError, match=f"fabrik fix {project_dir} --type"):
            fix_project(project_dir, dry_run=True)

    def test_cli_prints_no_added_summary_when_nothing_was_added(self, tmp_path):
        from unittest import mock

        from click.testing import CliRunner

        from fabrik.cli import cli

        project_dir = self._saas_project(tmp_path)
        only_unsupported = ["[unsupported-fix] server/Dockerfile"]
        with mock.patch("fabrik.scaffold.fix_project", return_value=only_unsupported):
            result = CliRunner().invoke(cli, ["fix", str(project_dir)])

        assert result.exit_code == 1
        assert "Added 0 files" not in result.output
