"""Tests for T3 — wp plan and wp apply resolve spec from project folder.

Covers the three-priority spec resolution chain:
  1. --project <path> → <path>/site.yaml
  2. CWD auto-detection (site.yaml + project.yaml with type: wordpress)
  3. Legacy fallback (specs/sites/<site_id>.yaml)
And the FileNotFoundError when none match.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.testing import CliRunner

from fabrik.wordpress.spec_loader import (
    SpecLoader,
    load_spec_from_path,
    resolve_spec_path,
)


# ---------------------------------------------------------------------------
# resolve_spec_path — Priority 1: explicit --project path
# ---------------------------------------------------------------------------


class TestResolveSpecPathProject:
    """Priority 1: --project <path> → <path>/site.yaml."""

    def test_project_path_returns_site_yaml(self, tmp_path: Path) -> None:
        site_yaml = tmp_path / "site.yaml"
        site_yaml.write_text("preset: saas\nsite:\n  domain: test.com\n")

        resolved, is_legacy = resolve_spec_path("test-site", project_path=str(tmp_path))

        assert resolved == site_yaml
        assert is_legacy is False

    def test_project_path_missing_site_yaml_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="No site.yaml found at"):
            resolve_spec_path("test-site", project_path=str(tmp_path))


# ---------------------------------------------------------------------------
# resolve_spec_path — Priority 2: CWD auto-detection
# ---------------------------------------------------------------------------


class TestResolveSpecPathCWD:
    """Priority 2: CWD with site.yaml + project.yaml type: wordpress."""

    def test_cwd_with_wordpress_project_yaml(self, tmp_path: Path) -> None:
        site_yaml = tmp_path / "site.yaml"
        site_yaml.write_text("preset: saas\n")
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text(yaml.dump({"name": "my-wp", "type": "wordpress"}))

        with patch("fabrik.wordpress.spec_loader.Path") as mock_path_cls:
            # Make Path.cwd() return tmp_path, but let Path(x) work normally
            real_path = Path

            def side_effect(*args, **kwargs):
                if not args:
                    return real_path(*args, **kwargs)
                return real_path(*args, **kwargs)

            mock_path_cls.side_effect = side_effect
            mock_path_cls.cwd.return_value = tmp_path

            resolved, is_legacy = resolve_spec_path("my-wp", project_path=None)

        assert resolved == site_yaml
        assert is_legacy is False

    def test_cwd_without_project_yaml_falls_through(self, tmp_path: Path) -> None:
        """CWD has site.yaml but no project.yaml — should fall to legacy."""
        site_yaml = tmp_path / "site.yaml"
        site_yaml.write_text("preset: saas\n")

        with patch("fabrik.wordpress.spec_loader.Path") as mock_path_cls:
            real_path = Path

            def side_effect(*args, **kwargs):
                if not args:
                    return real_path(*args, **kwargs)
                return real_path(*args, **kwargs)

            mock_path_cls.side_effect = side_effect
            mock_path_cls.cwd.return_value = tmp_path

            # No legacy file either, should raise
            with pytest.raises(FileNotFoundError, match="No site.yaml found"):
                resolve_spec_path("nonexistent-site", project_path=None)

    def test_cwd_non_wordpress_type_falls_through(self, tmp_path: Path) -> None:
        """CWD has site.yaml + project.yaml but type != wordpress."""
        site_yaml = tmp_path / "site.yaml"
        site_yaml.write_text("preset: saas\n")
        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text(yaml.dump({"name": "my-api", "type": "python-api"}))

        with patch("fabrik.wordpress.spec_loader.Path") as mock_path_cls:
            real_path = Path

            def side_effect(*args, **kwargs):
                if not args:
                    return real_path(*args, **kwargs)
                return real_path(*args, **kwargs)

            mock_path_cls.side_effect = side_effect
            mock_path_cls.cwd.return_value = tmp_path

            # Falls through to legacy, which doesn't exist either
            with pytest.raises(FileNotFoundError, match="No site.yaml found"):
                resolve_spec_path("nonexistent-site", project_path=None)


# ---------------------------------------------------------------------------
# resolve_spec_path — Priority 3: Legacy fallback
# ---------------------------------------------------------------------------


class TestResolveSpecPathLegacy:
    """Priority 3: Legacy fallback to specs/sites/<site_id>.yaml."""

    def test_legacy_path_resolved(self, tmp_path: Path) -> None:
        """Legacy spec file in SPECS_DIR resolves with is_legacy=True."""
        specs_dir = tmp_path / "specs" / "sites"
        specs_dir.mkdir(parents=True)
        legacy_file = specs_dir / "example.com.yaml"
        legacy_file.write_text("preset: company\n")

        with patch.object(SpecLoader, "SPECS_DIR", specs_dir):
            # Ensure CWD doesn't interfere
            with patch("fabrik.wordpress.spec_loader.Path") as mock_path_cls:
                real_path = Path
                nonexistent = tmp_path / "empty_cwd"
                nonexistent.mkdir(exist_ok=True)

                def side_effect(*args, **kwargs):
                    if not args:
                        return real_path(*args, **kwargs)
                    return real_path(*args, **kwargs)

                mock_path_cls.side_effect = side_effect
                mock_path_cls.cwd.return_value = nonexistent

                resolved, is_legacy = resolve_spec_path("example.com", project_path=None)

        assert resolved == legacy_file
        assert is_legacy is True

    def test_legacy_v2_path_preferred(self, tmp_path: Path) -> None:
        """v2 spec file takes precedence over .yaml in legacy mode."""
        specs_dir = tmp_path / "specs" / "sites"
        specs_dir.mkdir(parents=True)
        (specs_dir / "example.com.yaml").write_text("preset: company\n")
        v2_file = specs_dir / "example.com.v2.yaml"
        v2_file.write_text("preset: saas\n")

        with patch.object(SpecLoader, "SPECS_DIR", specs_dir):
            with patch("fabrik.wordpress.spec_loader.Path") as mock_path_cls:
                real_path = Path
                nonexistent = tmp_path / "empty_cwd"
                nonexistent.mkdir(exist_ok=True)

                def side_effect(*args, **kwargs):
                    if not args:
                        return real_path(*args, **kwargs)
                    return real_path(*args, **kwargs)

                mock_path_cls.side_effect = side_effect
                mock_path_cls.cwd.return_value = nonexistent

                resolved, is_legacy = resolve_spec_path("example.com", project_path=None)

        assert resolved == v2_file
        assert is_legacy is True


# ---------------------------------------------------------------------------
# resolve_spec_path — No match → FileNotFoundError
# ---------------------------------------------------------------------------


class TestResolveSpecPathNotFound:
    """FileNotFoundError when no spec file resolves."""

    def test_no_match_raises_file_not_found(self, tmp_path: Path) -> None:
        with patch.object(SpecLoader, "SPECS_DIR", tmp_path / "empty"):
            with patch("fabrik.wordpress.spec_loader.Path") as mock_path_cls:
                real_path = Path
                nonexistent = tmp_path / "empty_cwd"
                nonexistent.mkdir(exist_ok=True)

                def side_effect(*args, **kwargs):
                    if not args:
                        return real_path(*args, **kwargs)
                    return real_path(*args, **kwargs)

                mock_path_cls.side_effect = side_effect
                mock_path_cls.cwd.return_value = nonexistent

                with pytest.raises(FileNotFoundError, match="No site.yaml found"):
                    resolve_spec_path("ghost.com", project_path=None)


# ---------------------------------------------------------------------------
# SpecLoader — site_path override
# ---------------------------------------------------------------------------


class TestSpecLoaderSitePath:
    """SpecLoader.__init__ accepts optional site_path override."""

    def test_site_path_override_used(self, tmp_path: Path) -> None:
        custom_path = tmp_path / "custom" / "site.yaml"
        custom_path.parent.mkdir(parents=True)
        custom_path.write_text("preset: saas\n")

        loader = SpecLoader("test.com", site_path=custom_path)
        assert loader.site_path == custom_path

    def test_default_site_path_without_override(self) -> None:
        loader = SpecLoader("test.com")
        assert loader.site_path == SpecLoader.SPECS_DIR / "test.com.yaml"


# ---------------------------------------------------------------------------
# load_spec_from_path — integration
# ---------------------------------------------------------------------------


class TestLoadSpecFromPath:
    """load_spec_from_path uses SpecLoader with site_path override."""

    def test_loads_spec_from_explicit_path(self, tmp_path: Path) -> None:
        site_yaml = tmp_path / "site.yaml"
        site_yaml.write_text("preset: saas\nsite:\n  domain: test.com\n")

        with patch.object(SpecLoader, "TEMPLATES_DIR", tmp_path / "templates"):
            # Create minimal defaults and preset so the merge doesn't fail
            templates_dir = tmp_path / "templates"
            templates_dir.mkdir(parents=True)
            (templates_dir / "defaults.yaml").write_text("site:\n  title: Default\n")
            presets_dir = templates_dir / "presets"
            presets_dir.mkdir()
            (presets_dir / "saas.yaml").write_text("site:\n  title: SaaS Default\n")

            result = load_spec_from_path("test.com", site_yaml)

        assert isinstance(result, dict)
        assert result.get("site", {}).get("domain") == "test.com"


# ---------------------------------------------------------------------------
# CLI helper — _resolve_wp_site_id
# ---------------------------------------------------------------------------


class TestResolveWpSiteId:
    """CLI helper resolves site_id from project.yaml when not provided."""

    def test_explicit_site_id_returned(self) -> None:
        from fabrik.cli import _resolve_wp_site_id

        assert _resolve_wp_site_id("ocoron.com", None) == "ocoron.com"

    def test_site_id_from_cwd_project_yaml(self, tmp_path: Path) -> None:
        from fabrik.cli import _resolve_wp_site_id

        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text(yaml.dump({"name": "my-wp-site", "type": "wordpress"}))

        with patch("fabrik.cli.Path") as mock_path_cls:
            real_path = Path

            def side_effect(*args, **kwargs):
                if not args:
                    return real_path(*args, **kwargs)
                return real_path(*args, **kwargs)

            mock_path_cls.side_effect = side_effect
            mock_path_cls.cwd.return_value = tmp_path

            result = _resolve_wp_site_id(None, None)

        assert result == "my-wp-site"

    def test_no_project_yaml_exits(self, tmp_path: Path) -> None:
        from fabrik.cli import _resolve_wp_site_id

        with patch("fabrik.cli.Path") as mock_path_cls:
            real_path = Path

            def side_effect(*args, **kwargs):
                if not args:
                    return real_path(*args, **kwargs)
                return real_path(*args, **kwargs)

            mock_path_cls.side_effect = side_effect
            mock_path_cls.cwd.return_value = tmp_path

            with pytest.raises(SystemExit):
                _resolve_wp_site_id(None, None)

    def test_project_path_option_reads_project_yaml(self, tmp_path: Path) -> None:
        from fabrik.cli import _resolve_wp_site_id

        project_yaml = tmp_path / "project.yaml"
        project_yaml.write_text(yaml.dump({"name": "from-project", "type": "wordpress"}))

        result = _resolve_wp_site_id(None, str(tmp_path))
        assert result == "from-project"


class TestWpCliSpecResolutionErrors:
    """CLI should preserve spec-loader FileNotFoundError messages."""

    def test_wp_apply_empty_directory_reports_missing_site_yaml(self, tmp_path: Path) -> None:
        from fabrik.cli import cli

        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=str(tmp_path)):
            result = runner.invoke(cli, ["wp", "apply", "--dry-run"], catch_exceptions=False)

        assert result.exit_code == 1
        assert "No site.yaml found" in result.output

    def test_wp_plan_empty_directory_reports_missing_site_yaml(self, tmp_path: Path) -> None:
        from fabrik.cli import cli

        runner = CliRunner()

        with runner.isolated_filesystem(temp_dir=str(tmp_path)):
            result = runner.invoke(cli, ["wp", "plan"], catch_exceptions=False)

        assert result.exit_code == 1
        assert "No site.yaml found" in result.output
