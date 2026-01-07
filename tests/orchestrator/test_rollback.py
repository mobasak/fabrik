"""Tests for rollback manager."""

from pathlib import Path
from unittest.mock import MagicMock

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.rollback import RollbackManager


class TestRollbackManager:
    """Test RollbackManager class."""

    def test_rollback_dry_run(self):
        """Dry run should not delete anything."""
        mock_coolify = MagicMock()
        manager = RollbackManager(coolify_client=mock_coolify)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
            dry_run=True,
        )
        ctx.add_resource("coolify", "uuid-123")

        errors = manager.rollback(ctx)

        assert errors == []
        mock_coolify.delete_application.assert_not_called()

    def test_rollback_no_resources(self):
        """Should handle empty resources gracefully."""
        manager = RollbackManager()

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )

        errors = manager.rollback(ctx)
        assert errors == []

    def test_rollback_coolify_resource(self):
        """Should delete Coolify application."""
        mock_coolify = MagicMock()
        manager = RollbackManager(coolify_client=mock_coolify)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("coolify", "uuid-123", name="test-app")

        errors = manager.rollback(ctx)

        assert errors == []
        mock_coolify.delete_application.assert_called_once_with("uuid-123")

    def test_rollback_multiple_resources_lifo(self):
        """Should rollback in reverse order (LIFO)."""
        mock_coolify = MagicMock()
        manager = RollbackManager(coolify_client=mock_coolify)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("coolify", "uuid-1")
        ctx.add_resource("coolify", "uuid-2")
        ctx.add_resource("coolify", "uuid-3")

        manager.rollback(ctx)

        # Should be called in reverse order
        calls = mock_coolify.delete_application.call_args_list
        assert len(calls) == 3
        assert calls[0][0][0] == "uuid-3"
        assert calls[1][0][0] == "uuid-2"
        assert calls[2][0][0] == "uuid-1"

    def test_rollback_continues_on_error(self):
        """Should continue rollback even if one resource fails."""
        mock_coolify = MagicMock()
        mock_coolify.delete_application.side_effect = [
            None,  # First succeeds
            Exception("API error"),  # Second fails
            None,  # Third succeeds
        ]
        manager = RollbackManager(coolify_client=mock_coolify)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("coolify", "uuid-1")
        ctx.add_resource("coolify", "uuid-2")
        ctx.add_resource("coolify", "uuid-3")

        errors = manager.rollback(ctx)

        # Should have one error but all three attempted
        assert len(errors) == 1
        assert "uuid-2" in errors[0]
        assert mock_coolify.delete_application.call_count == 3

    def test_rollback_dns_resource(self):
        """Should delete DNS record with zone metadata."""
        mock_dns = MagicMock()
        manager = RollbackManager(dns_client=mock_dns)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("dns", "record-123", zone="example.com")

        errors = manager.rollback(ctx)

        assert errors == []
        mock_dns.delete_record.assert_called_once_with("example.com", "record-123")

    def test_rollback_dns_without_zone_skipped(self):
        """Should skip DNS record without zone metadata."""
        mock_dns = MagicMock()
        manager = RollbackManager(dns_client=mock_dns)

        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test"},
        )
        ctx.add_resource("dns", "record-123")  # No zone

        errors = manager.rollback(ctx)

        assert errors == []
        mock_dns.delete_record.assert_not_called()
