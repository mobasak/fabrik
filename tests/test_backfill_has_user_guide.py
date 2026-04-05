"""Tests for has_user_guide backfill in fix_project().

Covers:
- Missing key is backfilled with correct derived value
- Existing explicit key is preserved (not overwritten)
- Guide-enabled types derive True
- Non-guide types derive False
- Dry-run reports pending changes without writing
"""

from pathlib import Path

import yaml

from fabrik.scaffold import GUIDE_ENABLED_TYPES, fix_project


def _make_project_yaml(project_dir: Path, data: dict) -> Path:
    """Write a minimal project.yaml and create .git marker."""
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".git").mkdir(exist_ok=True)
    yaml_path = project_dir / "project.yaml"
    yaml_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
    return yaml_path


class TestBackfillMissingKey:
    """fix_project() adds has_user_guide when the key is absent."""

    def test_guide_enabled_type_gets_true(self, tmp_path):
        project_dir = tmp_path / "my-saas"
        _make_project_yaml(project_dir, {"name": "my-saas", "type": "saas-skeleton"})

        added = fix_project(project_dir, dry_run=False)

        data = yaml.safe_load((project_dir / "project.yaml").read_text())
        assert data["has_user_guide"] is True
        assert any("backfilled has_user_guide: true" in item for item in added)

    def test_non_guide_type_gets_false(self, tmp_path):
        project_dir = tmp_path / "my-api"
        _make_project_yaml(project_dir, {"name": "my-api", "type": "python-api"})

        added = fix_project(project_dir, dry_run=False)

        data = yaml.safe_load((project_dir / "project.yaml").read_text())
        assert data["has_user_guide"] is False
        assert any("backfilled has_user_guide: false" in item for item in added)

    def test_missing_type_defaults_to_python_api(self, tmp_path):
        """Projects without a type field default to python-api (non-guide)."""
        project_dir = tmp_path / "no-type"
        _make_project_yaml(project_dir, {"name": "no-type"})

        fix_project(project_dir, dry_run=False)

        data = yaml.safe_load((project_dir / "project.yaml").read_text())
        assert data["has_user_guide"] is False


class TestPreserveExistingKey:
    """fix_project() does NOT overwrite an explicit has_user_guide value."""

    def test_explicit_true_preserved(self, tmp_path):
        project_dir = tmp_path / "explicit-true"
        _make_project_yaml(
            project_dir,
            {"name": "explicit-true", "type": "python-api", "has_user_guide": True},
        )

        added = fix_project(project_dir, dry_run=False)

        data = yaml.safe_load((project_dir / "project.yaml").read_text())
        assert data["has_user_guide"] is True
        assert not any("backfill" in item for item in added)

    def test_explicit_false_preserved(self, tmp_path):
        project_dir = tmp_path / "explicit-false"
        _make_project_yaml(
            project_dir,
            {"name": "explicit-false", "type": "saas-skeleton", "has_user_guide": False},
        )

        added = fix_project(project_dir, dry_run=False)

        data = yaml.safe_load((project_dir / "project.yaml").read_text())
        assert data["has_user_guide"] is False
        assert not any("backfill" in item for item in added)


class TestDryRun:
    """Dry-run reports backfill without writing."""

    def test_dry_run_reports_backfill(self, tmp_path):
        project_dir = tmp_path / "dry-run-test"
        yaml_path = _make_project_yaml(
            project_dir, {"name": "dry-run-test", "type": "mobile-app"}
        )
        original = yaml_path.read_text()

        added = fix_project(project_dir, dry_run=True)

        # File content must be unchanged
        assert yaml_path.read_text() == original
        assert any("backfill has_user_guide: true" in item for item in added)

    def test_dry_run_no_report_when_key_exists(self, tmp_path):
        project_dir = tmp_path / "dry-existing"
        _make_project_yaml(
            project_dir,
            {"name": "dry-existing", "type": "python-api", "has_user_guide": False},
        )

        added = fix_project(project_dir, dry_run=True)

        assert not any("backfill" in item for item in added)


class TestAllGuideEnabledTypes:
    """Every GUIDE_ENABLED_TYPES member derives True; others derive False."""

    def test_all_guide_types_derive_true(self, tmp_path):
        for ptype in sorted(GUIDE_ENABLED_TYPES):
            project_dir = tmp_path / f"proj-{ptype}"
            _make_project_yaml(project_dir, {"name": f"proj-{ptype}", "type": ptype})

            fix_project(project_dir, dry_run=False)

            data = yaml.safe_load((project_dir / "project.yaml").read_text())
            assert data["has_user_guide"] is True, f"{ptype} should derive True"

    def test_non_guide_types_derive_false(self, tmp_path):
        non_guide = {"python-api", "node-api", "file-api", "file-worker", "wordpress", "docusaurus"}
        for ptype in sorted(non_guide):
            project_dir = tmp_path / f"proj-{ptype}"
            _make_project_yaml(project_dir, {"name": f"proj-{ptype}", "type": ptype})

            fix_project(project_dir, dry_run=False)

            data = yaml.safe_load((project_dir / "project.yaml").read_text())
            assert data["has_user_guide"] is False, f"{ptype} should derive False"
