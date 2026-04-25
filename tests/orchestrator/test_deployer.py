"""Tests for Coolify deployer."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer import ServiceDeployer
from fabrik.orchestrator.exceptions import DeployError


class TestServiceDeployer:
    """Test ServiceDeployer class."""

    def test_find_existing_found(self):
        """Find an existing deployment by name."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = [
            {"name": "other-app", "uuid": "uuid-1"},
            {"name": "my-app", "uuid": "uuid-2"},
        ]

        deployer = ServiceDeployer(coolify_client=mock_client)
        result = deployer.find_existing("my-app")

        assert result is not None
        assert result["uuid"] == "uuid-2"

    def test_find_existing_not_found(self):
        """Return None if deployment not found."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = [
            {"name": "other-app", "uuid": "uuid-1"},
        ]

        deployer = ServiceDeployer(coolify_client=mock_client)
        result = deployer.find_existing("my-app")

        assert result is None

    def test_find_existing_api_error_propagates(self):
        """API errors should propagate (fail fast), not be swallowed."""
        mock_client = MagicMock()
        mock_client.list_applications.side_effect = Exception("Coolify API error")

        deployer = ServiceDeployer(coolify_client=mock_client)

        with pytest.raises(Exception) as exc:
            deployer.find_existing("my-app")

        assert "Coolify API error" in str(exc.value)

    def test_deploy_dry_run(self):
        """Dry run should not call Coolify API."""
        mock_client = MagicMock()
        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test-app", "domain": "test.com"},
            dry_run=True,
        )

        result = deployer.deploy(ctx)

        assert result == "dry-run-uuid"
        mock_client.create_dockercompose_application.assert_not_called()

    def test_deploy_creates_new(self):
        """Create new deployment if none exists."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [{"name": "fabrik", "uuid": "project-uuid"}]
        mock_client.create_dockercompose_application.return_value = {"uuid": "new-uuid"}

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test-app", "domain": "test.com", "template": "python-api"},
            secrets={"API_KEY": "secret123"},
        )

        with (
            patch("fabrik.spec_loader.Spec"),
            patch("fabrik.template_renderer.TemplateRenderer") as mock_renderer_cls,
        ):
            mock_renderer_cls.return_value.render.return_value = {"compose.yaml": "version: '3'"}
            result = deployer.deploy(ctx)

        assert result == "new-uuid"
        assert ctx.coolify_uuid == "new-uuid"
        mock_client.create_dockercompose_application.assert_called_once()

    def test_deploy_updates_existing(self):
        """Update existing deployment if found."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = [
            {"name": "test-app", "uuid": "existing-uuid"},
        ]
        mock_client._resolve_resource_base.return_value = "applications"

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test-app", "domain": "test.com"},
        )

        result = deployer.deploy(ctx)

        assert result == "existing-uuid"
        mock_client.update_application.assert_called_once()
        mock_client.create_dockercompose_application.assert_not_called()

    def test_update_skips_fqdn_patch_for_dockercompose(self):
        """Regression: dockercompose apps reject fqdn PATCH (422 "not allowed").

        For dockercompose apps the domain is carried by the compose's Traefik
        labels, not by the fqdn field. Attempting to PATCH fqdn returns HTTP
        422 and fails the deployment. See `orchestrator/deployer.py` +
        CHANGELOG entry (2026-04-22, site-provisioner redeploy).
        """
        mock_client = MagicMock()
        mock_client.list_applications.return_value = [
            {"name": "test-app", "uuid": "existing-uuid", "build_pack": "dockercompose"},
        ]
        # Simulate CoolifyClient._resolve_resource_base returning "applications"
        # for a dockercompose app (which is the real-world case).
        mock_client._resolve_resource_base.return_value = "applications"

        deployer = ServiceDeployer(coolify_client=mock_client)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test-app", "domain": "test.com"},
        )
        deployer.deploy(ctx)

        # fqdn PATCH MUST NOT happen for dockercompose apps
        mock_client.update_application.assert_not_called()

    def test_update_does_not_track_for_rollback(self):
        """UPDATE should NOT add to created_resources (prevents deleting pre-existing apps)."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = [
            {"name": "test-app", "uuid": "existing-uuid"},
        ]

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test-app", "domain": "test.com"},
        )

        deployer.deploy(ctx)

        # CRITICAL: Update path should NOT track resource for rollback
        assert len(ctx.created_resources) == 0, "Update should not mark existing app for rollback"

    def test_deploy_tracks_resource(self):
        """Deployment should track created resource."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [{"name": "fabrik", "uuid": "project-uuid"}]
        mock_client.create_dockercompose_application.return_value = {"uuid": "new-uuid"}

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test-app", "domain": "test.com", "template": "python-api"},
        )

        with (
            patch("fabrik.spec_loader.Spec"),
            patch("fabrik.template_renderer.TemplateRenderer") as mock_renderer_cls,
        ):
            mock_renderer_cls.return_value.render.return_value = {"compose.yaml": "version: '3'"}
            deployer.deploy(ctx)

        assert len(ctx.created_resources) == 1
        assert ctx.created_resources[0].resource_type == "coolify"
        assert ctx.created_resources[0].resource_id == "new-uuid"

    def test_delete_dry_run(self):
        """Dry run delete should not call API."""
        mock_client = MagicMock()
        deployer = ServiceDeployer(coolify_client=mock_client)

        result = deployer.delete("some-uuid", dry_run=True)

        assert result is True
        mock_client.delete_application.assert_not_called()

    def test_delete_success(self):
        """Delete should call API and return True."""
        mock_client = MagicMock()
        deployer = ServiceDeployer(coolify_client=mock_client)

        result = deployer.delete("some-uuid")

        assert result is True
        mock_client.delete_application.assert_called_once_with("some-uuid")

    def test_delete_failure(self):
        """Delete should return False on error."""
        mock_client = MagicMock()
        mock_client.delete_application.side_effect = Exception("API error")

        deployer = ServiceDeployer(coolify_client=mock_client)
        result = deployer.delete("some-uuid")

        assert result is False

    def test_deploy_creates_git_sourced_private_repo(self):
        """Git-sourced spec with private repo uses create_git_application."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [
            {"name": "fabrik", "uuid": "project-uuid"}
        ]
        mock_client.get_project.return_value = {
            "environments": [{"name": "production", "uuid": "env-uuid"}]
        }
        mock_client.list_private_keys.return_value = [
            {"uuid": "key-1", "name": "localhost's key", "is_git_related": False},
            {"uuid": "deploy-key-uuid", "name": "github-deploy-key", "is_git_related": False},
        ]
        mock_client.create_git_application.return_value = {"uuid": "new-git-uuid"}
        mock_client.deploy.return_value = {"deployment_uuid": "deploy-1"}

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={
                "name": "my-git-app",
                "domain": "my-git.vps1.ocoron.com",
                "source": {
                    "type": "git",
                    "repository": "git@github.com:mobasak/my-app.git",
                    "branch": "main",
                },
            },
        )

        result = deployer.deploy(ctx)

        assert result == "new-git-uuid"
        assert ctx.coolify_uuid == "new-git-uuid"
        # Must call create_git_application, NOT create_dockercompose_application
        mock_client.create_git_application.assert_called_once()
        mock_client.create_dockercompose_application.assert_not_called()
        # Verify the call includes private_key_uuid for private repo
        call_kwargs = mock_client.create_git_application.call_args
        assert call_kwargs.kwargs["private_key_uuid"] == "deploy-key-uuid"
        assert call_kwargs.kwargs["git_repository"] == "git@github.com:mobasak/my-app.git"
        assert call_kwargs.kwargs["build_pack"] == "dockercompose"

    def test_deploy_creates_git_sourced_public_repo(self):
        """Git-sourced spec with public repo (https://) omits private_key_uuid."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [
            {"name": "fabrik", "uuid": "project-uuid"}
        ]
        mock_client.get_project.return_value = {
            "environments": [{"name": "production", "uuid": "env-uuid"}]
        }
        mock_client.create_git_application.return_value = {"uuid": "new-git-uuid"}
        mock_client.deploy.return_value = {"deployment_uuid": "deploy-1"}

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={
                "name": "my-public-app",
                "domain": "my-public.vps1.ocoron.com",
                "source": {
                    "type": "git",
                    "repository": "https://github.com/mobasak/public-app.git",
                    "branch": "main",
                },
            },
        )

        result = deployer.deploy(ctx)

        assert result == "new-git-uuid"
        mock_client.create_git_application.assert_called_once()
        call_kwargs = mock_client.create_git_application.call_args
        # Public repo: no private_key_uuid
        assert call_kwargs.kwargs["private_key_uuid"] is None

    def test_deploy_git_sourced_missing_repository_raises(self):
        """Git-sourced spec without repository raises DeployError."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [
            {"name": "fabrik", "uuid": "project-uuid"}
        ]

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={
                "name": "broken-app",
                "source": {
                    "type": "git",
                    "branch": "main",
                    # repository intentionally missing
                },
            },
        )

        with pytest.raises(DeployError, match="source.repository"):
            deployer.deploy(ctx)

    def test_deploy_git_sourced_no_deploy_key_raises(self):
        """Private git repo with no deploy key in Coolify raises DeployError."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [
            {"name": "fabrik", "uuid": "project-uuid"}
        ]
        mock_client.get_project.return_value = {
            "environments": [{"name": "production", "uuid": "env-uuid"}]
        }
        mock_client.list_private_keys.return_value = [
            {"uuid": "key-1", "name": "localhost's key", "is_git_related": False},
        ]

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={
                "name": "private-app",
                "source": {
                    "type": "git",
                    "repository": "git@github.com:mobasak/private.git",
                    "branch": "main",
                },
            },
        )

        with pytest.raises(DeployError, match="SSH deploy key"):
            deployer.deploy(ctx)

    def test_resolve_environment_uuid_from_env_var(self):
        """COOLIFY_ENVIRONMENT_UUID env var short-circuits API call."""
        mock_client = MagicMock()
        deployer = ServiceDeployer(coolify_client=mock_client)

        with patch.dict(os.environ, {"COOLIFY_ENVIRONMENT_UUID": "env-from-var"}):
            result = deployer._resolve_environment_uuid("project-uuid")

        assert result == "env-from-var"
        mock_client.get_project.assert_not_called()

    def test_resolve_private_key_uuid_prefers_git_related(self):
        """_resolve_private_key_uuid picks git-related key over others."""
        mock_client = MagicMock()
        mock_client.list_private_keys.return_value = [
            {"uuid": "localhost-key", "name": "localhost's key", "is_git_related": False},
            {"uuid": "git-key", "name": "deploy-key", "is_git_related": True},
        ]
        deployer = ServiceDeployer(coolify_client=mock_client)

        result = deployer._resolve_private_key_uuid()

        assert result == "git-key"
