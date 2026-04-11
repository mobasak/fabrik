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

    def test_wordpress_calls_wp_pipeline(self, tmp_path: Path) -> None:
        data = {"name": "my-wp", "type": "wordpress"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        mock_planner = MagicMock()
        mock_planner_instance = MagicMock()
        mock_planner.return_value = mock_planner_instance

        mock_deployer = MagicMock()
        mock_deployer_instance = MagicMock()
        mock_deployer_instance.deploy.return_value = MagicMock(success=True)
        mock_deployer.return_value = mock_deployer_instance

        with (
            patch("fabrik.deploy_router.get_project_metadata", return_value=data),
            patch("fabrik.wordpress.planner.Planner", mock_planner),
            patch("fabrik.wordpress.deployer.SiteDeployer", mock_deployer),
        ):
            exit_code = route_deploy(tmp_path, "wordpress", dry_run=True)

        assert exit_code == 0
        mock_planner.assert_called_once_with("my-wp", project_path=str(tmp_path))
        mock_planner_instance.plan.assert_called_once()
        mock_deployer.assert_called_once_with("my-wp", dry_run=True, project_path=str(tmp_path))
        mock_deployer_instance.deploy.assert_called_once()

    def test_wordpress_failure_returns_1(self, tmp_path: Path) -> None:
        data = {"name": "fail-wp", "type": "wordpress"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        mock_deployer_instance = MagicMock()
        mock_deployer_instance.deploy.return_value = MagicMock(success=False)

        with (
            patch("fabrik.deploy_router.get_project_metadata", return_value=data),
            patch("fabrik.wordpress.planner.Planner"),
            patch(
                "fabrik.wordpress.deployer.SiteDeployer",
                return_value=mock_deployer_instance,
            ),
        ):
            exit_code = route_deploy(tmp_path, "wordpress")

        assert exit_code == 1

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


class TestDeployCLI:
    """CLI integration via CliRunner."""

    def test_missing_project_yaml(self, tmp_path: Path) -> None:
        from fabrik.cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["deploy", "--project", str(tmp_path)])

        assert result.exit_code != 0
        assert "No project.yaml found" in result.output

    def test_unknown_type(self, tmp_path: Path) -> None:
        from fabrik.cli import cli

        data = {"name": "bad", "type": "unknown-type"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        runner = CliRunner()
        result = runner.invoke(cli, ["deploy", "--project", str(tmp_path)])

        assert result.exit_code != 0
        assert "Unknown project type" in result.output

    def test_deploy_echoes_type(self, tmp_path: Path) -> None:
        from fabrik.cli import cli

        data = {"name": "my-api", "type": "python-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        # Patch route_deploy to return 0 without actual deployment
        runner = CliRunner()
        with patch("fabrik.deploy_router.route_deploy", return_value=0) as mock_route:
            result = runner.invoke(cli, ["deploy", "--project", str(tmp_path), "--dry-run"])

        assert "type=python-api" in result.output
        assert "dry-run" in result.output
        mock_route.assert_called_once()

    def test_deploy_dry_run_flag(self, tmp_path: Path) -> None:
        from fabrik.cli import cli

        data = {"name": "my-api", "type": "python-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        runner = CliRunner()
        with patch("fabrik.deploy_router.route_deploy", return_value=0) as mock_route:
            runner.invoke(cli, ["deploy", "--project", str(tmp_path), "--dry-run"])

        # Verify dry_run was passed through
        call_kwargs = mock_route.call_args
        assert call_kwargs[1]["dry_run"] is True

    def test_deploy_missing_spec_error(self, tmp_path: Path) -> None:
        from fabrik.cli import cli

        data = {"name": "orphan", "type": "python-api"}
        (tmp_path / "project.yaml").write_text(yaml.dump(data))

        runner = CliRunner()
        with patch(
            "fabrik.deploy_router.route_deploy",
            side_effect=RuntimeError("No service spec found for project 'orphan'"),
        ):
            result = runner.invoke(cli, ["deploy", "--project", str(tmp_path)])

        assert result.exit_code != 0
        assert "No service spec found" in result.output
