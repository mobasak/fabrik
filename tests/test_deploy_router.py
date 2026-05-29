"""Tests for T4 — fabrik deploy unified entry point.

Covers:
  - resolve_project_dir() — explicit path, CWD fallback, missing dir
  - get_project_metadata() — happy path, missing file, bad YAML
  - get_project_type() — known type, unknown type, missing field
  - resolve_service_spec_path() — spec exists, spec missing
  - route_deploy() — WordPress and generic dispatch
  - CLI integration — deploy command via CliRunner
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from fabrik.deploy_router import (
    get_project_metadata,
    get_project_type,
    resolve_project_dir,
    resolve_service_spec_path,
    route_deploy,
)

# ---------------------------------------------------------------------------
# resolve_project_dir
# ---------------------------------------------------------------------------


class TestResolveProjectDir:
    """resolve_project_dir — explicit path and CWD fallback."""

    def test_explicit_path(self, tmp_path: Path) -> None:
        result = resolve_project_dir(str(tmp_path))
        assert result == tmp_path.resolve()

    def test_none_uses_cwd(self) -> None:
        result = resolve_project_dir(None)
        assert result == Path.cwd()

    def test_missing_dir_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist"
        with pytest.raises(RuntimeError, match="does not exist"):
            resolve_project_dir(str(missing))


# ---------------------------------------------------------------------------
# get_project_metadata
# ---------------------------------------------------------------------------


class TestGetProjectMetadata:
    """get_project_metadata — loads project.yaml."""

    def test_happy_path(self, tmp_path: Path) -> None:
        data = {"name": "my-api", "type": "python-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        result = get_project_metadata(tmp_path)

        assert result["name"] == "my-api"
        assert result["type"] == "python-api"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="No project.yaml found"):
            get_project_metadata(tmp_path)

    def test_bad_yaml_raises(self, tmp_path: Path) -> None:
        (tmp_path / "project.yaml").write_text(": invalid: yaml: [")
        with pytest.raises(RuntimeError, match="Failed to parse"):
            get_project_metadata(tmp_path)

    def test_non_mapping_raises(self, tmp_path: Path) -> None:
        (tmp_path / "project.yaml").write_text("- just\n- a\n- list\n")
        with pytest.raises(RuntimeError, match="must be a YAML mapping"):
            get_project_metadata(tmp_path)


# ---------------------------------------------------------------------------
# get_project_type
# ---------------------------------------------------------------------------


class TestGetProjectType:
    """get_project_type — validates type field."""

    def test_known_type(self, tmp_path: Path) -> None:
        data = {"name": "my-site", "type": "wordpress"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        assert get_project_type(tmp_path) == "wordpress"

    def test_unknown_type_raises(self, tmp_path: Path) -> None:
        data = {"name": "my-thing", "type": "not-a-real-type"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        with pytest.raises(RuntimeError, match="Unknown project type"):
            get_project_type(tmp_path)

    def test_missing_type_raises(self, tmp_path: Path) -> None:
        data = {"name": "my-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        with pytest.raises(RuntimeError, match="missing a 'type' field"):
            get_project_type(tmp_path)


# ---------------------------------------------------------------------------
# resolve_service_spec_path
# ---------------------------------------------------------------------------


class TestResolveServiceSpecPath:
    """resolve_service_spec_path — centralised spec lookup."""

    def test_spec_exists(self, tmp_path: Path) -> None:
        data = {"name": "my-api", "type": "python-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        spec_dir = tmp_path / "specs" / "services"
        spec_dir.mkdir(parents=True)
        spec_file = spec_dir / "my-api.yaml"
        spec_file.write_text("name: my-api\ntemplate: python-api\n")

        with patch("fabrik.deploy_router.FABRIK_ROOT", tmp_path):
            result = resolve_service_spec_path(tmp_path)

        assert result == spec_file

    def test_spec_missing_raises(self, tmp_path: Path) -> None:
        data = {"name": "orphan-api", "type": "python-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        with patch("fabrik.deploy_router.FABRIK_ROOT", tmp_path):
            with pytest.raises(RuntimeError, match="No service spec found"):
                resolve_service_spec_path(tmp_path)

    def test_missing_name_raises(self, tmp_path: Path) -> None:
        data = {"type": "python-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        with pytest.raises(RuntimeError, match="missing a 'name' field"):
            resolve_service_spec_path(tmp_path)


# ---------------------------------------------------------------------------
# route_deploy — dispatch
# ---------------------------------------------------------------------------


class TestRouteDeploy:
    """route_deploy — dispatches to correct pipeline."""

    def test_wordpress_redirects_to_wpf(self, tmp_path: Path) -> None:
        """WordPress moved to /opt/wpf/; the router raises
        NotImplementedError pointing at the wpf CLI rather than running a
        pipeline here."""
        data = {"name": "my-wp", "type": "wordpress"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        with patch("fabrik.deploy_router.get_project_metadata", return_value=data):
            with pytest.raises(NotImplementedError, match="wpf"):
                route_deploy(tmp_path, "wordpress", dry_run=True)

    def test_generic_calls_orchestrator(self, tmp_path: Path) -> None:
        data = {"name": "my-api", "type": "python-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Create spec file
        spec_dir = tmp_path / "specs" / "services"
        spec_dir.mkdir(parents=True)
        (spec_dir / "my-api.yaml").write_text("name: my-api\n")

        mock_ctx = MagicMock()
        mock_ctx.state = MagicMock()
        mock_ctx.state.__eq__ = lambda self, other: True  # Always equals COMPLETE

        mock_orch = MagicMock()
        mock_orch.deploy.return_value = mock_ctx

        with (
            patch("fabrik.deploy_router.FABRIK_ROOT", tmp_path),
            patch("fabrik.deploy_router.DeploymentOrchestrator", return_value=mock_orch),
            patch("fabrik.deploy_router.DeploymentState") as mock_state_enum,
        ):
            mock_state_enum.COMPLETE = mock_ctx.state
            exit_code = route_deploy(tmp_path, "python-api")

        assert exit_code == 0
        mock_orch.deploy.assert_called_once()


# ---------------------------------------------------------------------------
# CLI integration — fabrik deploy
# ---------------------------------------------------------------------------


class TestApplyNoSpecPath:
    """`fabrik apply` with no SPEC_PATH resolves it from the current
    project's project.yaml (the behavior the removed `deploy` command
    used to provide). `apply` is now the single deploy entry point."""

    def test_missing_project_yaml(self, tmp_path: Path, monkeypatch) -> None:
        from fabrik.cli import cli

        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["apply", "--dry-run"])

        assert result.exit_code != 0
        assert "project.yaml" in result.output

    def test_unknown_type(self, tmp_path: Path, monkeypatch) -> None:
        from fabrik.cli import cli

        data = {"name": "bad", "type": "unknown-type"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["apply", "--dry-run"])

        assert result.exit_code != 0
        assert "Unknown project type" in result.output

    def test_wordpress_redirects_to_wpf(self, tmp_path: Path, monkeypatch) -> None:
        from fabrik.cli import cli

        data = {"name": "my-wp", "type": "wordpress"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["apply", "--dry-run"])

        assert result.exit_code != 0
        assert "wpf" in result.output

    def test_resolves_spec_from_project_yaml(self, tmp_path: Path, monkeypatch) -> None:
        from fabrik.cli import cli

        data = {"name": "my-api", "type": "python-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))
        monkeypatch.chdir(tmp_path)

        runner = CliRunner()
        # Patch the spec resolver to return a known path, and the orchestrator
        # so no real deployment runs.
        with patch(
            "fabrik.deploy_router.resolve_service_spec_path",
            return_value=Path("specs/services/my-api.yaml"),
        ):
            result = runner.invoke(cli, ["apply", "--dry-run"])

        assert "Resolved spec from project.yaml" in result.output
