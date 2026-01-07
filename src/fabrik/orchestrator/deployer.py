"""Coolify deployment with idempotency."""

import logging
from typing import Any

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import DeployError

logger = logging.getLogger(__name__)


class ServiceDeployer:
    """Deploy services to Coolify with idempotency.

    Checks for existing deployments by name before creating new ones.
    Updates existing deployments if spec has changed.
    """

    def __init__(self, coolify_client: Any | None = None):
        """Initialize deployer.

        Args:
            coolify_client: CoolifyClient instance (lazy loaded if None)
        """
        self._client = coolify_client

    @property
    def client(self) -> Any:
        """Lazy-load Coolify client."""
        if self._client is None:
            from fabrik.drivers.coolify import CoolifyClient

            self._client = CoolifyClient()
        return self._client

    def find_existing(self, name: str) -> dict[str, Any] | None:
        """Find an existing deployment by name.

        Args:
            name: Application name

        Returns:
            Application info dict or None if not found
        """
        try:
            apps = self.client.list_applications()
            for app in apps:
                if app.get("name") == name:
                    logger.info("Found existing deployment: %s (uuid=%s)", name, app.get("uuid"))
                    return app
            return None
        except Exception as e:
            logger.warning("Could not check for existing deployment: %s", e)
            return None

    def deploy(self, ctx: DeploymentContext) -> str:
        """Deploy or update a service.

        Args:
            ctx: Deployment context with spec and secrets

        Returns:
            Coolify application UUID

        Raises:
            DeployError: If deployment fails
        """
        name = ctx.spec["name"]
        domain = ctx.spec["domain"]

        if ctx.dry_run:
            logger.info("[DRY RUN] Would deploy %s to %s", name, domain)
            return "dry-run-uuid"

        # Check for existing deployment
        existing = self.find_existing(name)

        try:
            if existing:
                uuid = existing["uuid"]
                logger.info("Updating existing deployment: %s", uuid)
                self._update_deployment(uuid, ctx)
            else:
                logger.info("Creating new deployment: %s", name)
                uuid = self._create_deployment(ctx)

            ctx.coolify_uuid = uuid
            ctx.add_resource("coolify", uuid, name=name)
            return uuid

        except Exception as e:
            raise DeployError(f"Deployment failed: {e}", coolify_error=str(e)) from e

    def _create_deployment(self, ctx: DeploymentContext) -> str:
        """Create a new Coolify deployment.

        Args:
            ctx: Deployment context

        Returns:
            New application UUID
        """
        spec = ctx.spec

        # Build environment from spec + secrets
        env_vars = dict(spec.get("env", {}))
        for key, value in ctx.secrets.items():
            env_vars[key] = value

        # Create via Coolify API
        result = self.client.create_application(
            name=spec["name"],
            fqdn=f"https://{spec['domain']}",
            env_vars=env_vars,
        )

        return result.get("uuid", result.get("id", "unknown"))

    def _update_deployment(self, uuid: str, ctx: DeploymentContext) -> None:
        """Update an existing Coolify deployment.

        Args:
            uuid: Existing application UUID
            ctx: Deployment context
        """
        spec = ctx.spec

        # Build environment from spec + secrets
        env_vars = dict(spec.get("env", {}))
        for key, value in ctx.secrets.items():
            env_vars[key] = value

        self.client.update_application(
            uuid=uuid,
            fqdn=f"https://{spec['domain']}",
            env_vars=env_vars,
        )

    def delete(self, uuid: str, dry_run: bool = False) -> bool:
        """Delete a Coolify deployment.

        Args:
            uuid: Application UUID to delete
            dry_run: If True, only log what would happen

        Returns:
            True if deleted, False if failed
        """
        if dry_run:
            logger.info("[DRY RUN] Would delete deployment: %s", uuid)
            return True

        try:
            self.client.delete_application(uuid)
            logger.info("Deleted deployment: %s", uuid)
            return True
        except Exception as e:
            logger.error("Failed to delete deployment %s: %s", uuid, e)
            return False
