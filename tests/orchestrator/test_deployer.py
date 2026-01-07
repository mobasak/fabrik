"""Tests for Coolify deployer."""

from pathlib import Path
from unittest.mock import MagicMock

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer import ServiceDeployer


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
        mock_client.create_application.assert_not_called()

    def test_deploy_creates_new(self):
        """Create new deployment if none exists."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.create_application.return_value = {"uuid": "new-uuid"}

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test-app", "domain": "test.com", "template": "python-api"},
            secrets={"API_KEY": "secret123"},
        )

        result = deployer.deploy(ctx)

        assert result == "new-uuid"
        assert ctx.coolify_uuid == "new-uuid"
        mock_client.create_application.assert_called_once()

    def test_deploy_updates_existing(self):
        """Update existing deployment if found."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = [
            {"name": "test-app", "uuid": "existing-uuid"},
        ]

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test-app", "domain": "test.com"},
        )

        result = deployer.deploy(ctx)

        assert result == "existing-uuid"
        mock_client.update_application.assert_called_once()
        mock_client.create_application.assert_not_called()

    def test_deploy_tracks_resource(self):
        """Deployment should track created resource."""
        mock_client = MagicMock()
        mock_client.list_applications.return_value = []
        mock_client.create_application.return_value = {"uuid": "new-uuid"}

        deployer = ServiceDeployer(coolify_client=mock_client)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test-app", "domain": "test.com"},
        )

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
