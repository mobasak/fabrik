"""Tests for Coolify deployer."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer_coolify import ServiceDeployer
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

    def test_deploy_creates_git_sourced(self):
        """Git-sourced spec uses create_git_application with SSH deploy key."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [{"name": "fabrik", "uuid": "project-uuid"}]
        mock_client.get_project.return_value = {
            "environments": [{"name": "production", "uuid": "env-uuid"}]
        }
        mock_client.list_private_keys.return_value = [
            {"uuid": "key-github", "name": "github-deploy-key", "is_git_related": False},
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

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COOLIFY_PRIVATE_KEY_UUID", None)
            result = deployer.deploy(ctx)

        assert result == "new-git-uuid"
        assert ctx.coolify_uuid == "new-git-uuid"
        # Must call create_git_application, NOT create_dockercompose_application
        mock_client.create_git_application.assert_called_once()
        mock_client.create_dockercompose_application.assert_not_called()
        # Verify the call includes git_repository and build_pack + SSH key
        call_kwargs = mock_client.create_git_application.call_args
        assert call_kwargs.kwargs["git_repository"] == "git@github.com:mobasak/my-app.git"
        assert call_kwargs.kwargs["build_pack"] == "dockercompose"
        # Regression 2026-05-04: SSH repos MUST carry a private_key_uuid,
        # otherwise Coolify creates the app with private_key_id=NULL and
        # git ls-remote fails with Permission denied (publickey).
        assert call_kwargs.kwargs["private_key_uuid"] == "key-github"

    def test_deploy_git_sourced_ssh_without_deploy_key_raises(self):
        """SSH git repo with no resolvable deploy key fails fast.

        Regression for the 2026-05-04 /opt/fabrik-proxy redeploy: prior to
        the fix, an SSH URL with no key silently routed to
        /applications/public, the app was created with private_key_id=NULL,
        and the first deploy died with Permission denied (publickey). That
        failure mode is now caught pre-create.
        """
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [{"name": "fabrik", "uuid": "project-uuid"}]
        mock_client.get_project.return_value = {
            "environments": [{"name": "production", "uuid": "env-uuid"}]
        }
        # No git-related keys AND no name-heuristic matches.
        mock_client.list_private_keys.return_value = [
            {"uuid": "key-localhost", "name": "localhost's key", "is_git_related": False},
        ]

        deployer = ServiceDeployer(coolify_client=mock_client)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={
                "name": "keyless-app",
                "source": {
                    "type": "git",
                    "repository": "git@github.com:mobasak/keyless.git",
                    "branch": "main",
                },
            },
        )

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COOLIFY_PRIVATE_KEY_UUID", None)
            with pytest.raises(DeployError, match="requires a Coolify deploy key"):
                deployer.deploy(ctx)

        mock_client.create_git_application.assert_not_called()

    def test_deploy_git_sourced_https_skips_deploy_key(self):
        """HTTPS-cloneable repo doesn't need a private key."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [{"name": "fabrik", "uuid": "project-uuid"}]
        mock_client.get_project.return_value = {
            "environments": [{"name": "production", "uuid": "env-uuid"}]
        }
        mock_client.create_git_application.return_value = {"uuid": "https-uuid"}
        mock_client.deploy.return_value = {"deployment_uuid": "deploy-1"}

        deployer = ServiceDeployer(coolify_client=mock_client)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={
                "name": "public-app",
                "source": {
                    "type": "git",
                    "repository": "https://github.com/public/repo.git",
                    "branch": "main",
                },
            },
        )
        deployer.deploy(ctx)

        mock_client.list_private_keys.assert_not_called()
        call_kwargs = mock_client.create_git_application.call_args
        assert call_kwargs.kwargs["private_key_uuid"] is None

    def test_resolve_private_key_uuid_precedence(self):
        """spec override > env var > auto-discovery."""
        mock_client = MagicMock()
        mock_client.list_private_keys.return_value = [
            {"uuid": "key-auto", "name": "github-deploy-key", "is_git_related": False},
        ]
        deployer = ServiceDeployer(coolify_client=mock_client)

        # 1. spec override wins
        with patch.dict(os.environ, {"COOLIFY_PRIVATE_KEY_UUID": "env-value-xxxxxxxx"}):
            assert (
                deployer._resolve_private_key_uuid(
                    {"coolify": {"private_key_uuid": "spec-override-xxx"}}
                )
                == "spec-override-xxx"
            )

        # 2. env var wins over auto-discovery
        with patch.dict(os.environ, {"COOLIFY_PRIVATE_KEY_UUID": "env-value-xxxxxxxx"}):
            assert deployer._resolve_private_key_uuid({}) == "env-value-xxxxxxxx"

        # 3. auto-discovery via name heuristic (is_git_related=False on all keys
        #    — real-world Coolify state observed 2026-05-04).
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("COOLIFY_PRIVATE_KEY_UUID", None)
            assert deployer._resolve_private_key_uuid({}) == "key-auto"

        # 4. malformed env var (with inline comment) falls through to
        #    auto-discovery — guards against python-dotenv parsing
        #    ``KEY=  # comment`` as the literal ``# comment``.
        with patch.dict(os.environ, {"COOLIFY_PRIVATE_KEY_UUID": "  # auto-detect"}):
            assert deployer._resolve_private_key_uuid({}) == "key-auto"

    def test_deploy_git_sourced_missing_repository_raises(self):
        """Git-sourced spec without repository raises DeployError."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.list_servers.return_value = [{"uuid": "server-uuid"}]
        mock_client.list_projects.return_value = [{"name": "fabrik", "uuid": "project-uuid"}]

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

    def test_resolve_environment_uuid_from_env_var(self):
        """COOLIFY_ENVIRONMENT_UUID env var short-circuits API call."""
        mock_client = MagicMock()
        deployer = ServiceDeployer(coolify_client=mock_client)

        with patch.dict(os.environ, {"COOLIFY_ENVIRONMENT_UUID": "env-from-var"}):
            result = deployer._resolve_environment_uuid("project-uuid")

        assert result == "env-from-var"
        mock_client.get_project.assert_not_called()

    def test_resolve_project_server_uuids_honors_spec_coolify(self):
        """spec.coolify.project / .server names are looked up in Coolify.

        Why (One-Test Rule): the previous code path hard-coded the project name
        ``"fabrik"`` and ignored ``spec.coolify.project`` entirely, silently
        creating a wrong/orphan project when ``COOLIFY_PROJECT_UUID`` was unset.
        This test pins the new behavior: when the env override is absent, the
        deployer must look up the project by the spec-declared name.

        Given: spec declares ``coolify: {project: fabrik-services, server: vps1}``
               and no ``COOLIFY_*_UUID`` env vars are set.
        When: ``_resolve_project_server_uuids(ctx)`` runs.
        Then: it returns the UUIDs of the spec-named server and project (no
              fallback to "fabrik" or first server, no project creation).
        Mocks: CoolifyClient (the API surface; we don't hit live Coolify).
        """
        mock_client = MagicMock()
        mock_client.list_servers.return_value = [
            {"name": "other", "uuid": "other-server-uuid"},
            {"name": "vps1", "uuid": "vps1-uuid"},
        ]
        mock_client.list_projects.return_value = [
            {"name": "fabrik", "uuid": "wrong-uuid"},
            {"name": "fabrik-services", "uuid": "right-uuid"},
        ]

        deployer = ServiceDeployer(coolify_client=mock_client)
        ctx = DeploymentContext(
            spec_path=Path("proxy.yaml"),
            spec={
                "name": "fabrik-proxy",
                "coolify": {"project": "fabrik-services", "server": "vps1"},
            },
        )

        with patch.dict(os.environ, {}, clear=False) as env:
            env.pop("COOLIFY_SERVER_UUID", None)
            env.pop("COOLIFY_PROJECT_UUID", None)
            server_uuid, project_uuid = deployer._resolve_project_server_uuids(ctx)

        assert server_uuid == "vps1-uuid"
        assert project_uuid == "right-uuid"
        # Must not auto-create when the named project already exists
        mock_client.create_project.assert_not_called()
