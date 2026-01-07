"""Rollback manager for failed deployments."""

import logging
from typing import Any

from fabrik.orchestrator.context import DeploymentContext, ResourceRecord
from fabrik.orchestrator.exceptions import RollbackError

logger = logging.getLogger(__name__)


class RollbackManager:
    """Manage rollback of failed deployments.

    Only rolls back resources created in the current deployment run.
    Uses ownership tracking from DeploymentContext.
    """

    def __init__(
        self,
        coolify_client: Any | None = None,
        dns_client: Any | None = None,
    ):
        """Initialize rollback manager.

        Args:
            coolify_client: CoolifyClient instance
            dns_client: DNSClient instance
        """
        self._coolify_client = coolify_client
        self._dns_client = dns_client

    @property
    def coolify_client(self) -> Any:
        """Lazy-load Coolify client."""
        if self._coolify_client is None:
            from fabrik.drivers.coolify import CoolifyClient

            self._coolify_client = CoolifyClient()
        return self._coolify_client

    @property
    def dns_client(self) -> Any:
        """Lazy-load DNS client."""
        if self._dns_client is None:
            from fabrik.drivers.cloudflare import CloudflareClient

            self._dns_client = CloudflareClient()
        return self._dns_client

    def rollback(self, ctx: DeploymentContext) -> list[str]:
        """Roll back all resources created in this deployment.

        Args:
            ctx: Deployment context with created_resources

        Returns:
            List of errors encountered (empty if all successful)
        """
        if ctx.dry_run:
            logger.info("[DRY RUN] Would rollback %d resources", len(ctx.created_resources))
            return []

        if not ctx.created_resources:
            logger.info("No resources to rollback")
            return []

        errors: list[str] = []

        # Rollback in reverse order (LIFO)
        for resource in reversed(ctx.created_resources):
            try:
                self._rollback_resource(resource)
            except Exception as e:
                error_msg = (
                    f"Failed to rollback {resource.resource_type}/{resource.resource_id}: {e}"
                )
                logger.error(error_msg)
                errors.append(error_msg)

        if errors:
            logger.warning("Rollback completed with %d errors", len(errors))
        else:
            logger.info("Rollback completed successfully")

        return errors

    def _rollback_resource(self, resource: ResourceRecord) -> None:
        """Roll back a single resource.

        Args:
            resource: Resource record to rollback

        Raises:
            Exception: If rollback fails
        """
        logger.info(
            "Rolling back %s: %s",
            resource.resource_type,
            resource.resource_id,
        )

        if resource.resource_type == "coolify":
            self._rollback_coolify(resource)
        elif resource.resource_type == "dns":
            self._rollback_dns(resource)
        elif resource.resource_type == "monitor":
            self._rollback_monitor(resource)
        else:
            logger.warning("Unknown resource type: %s", resource.resource_type)

    def _rollback_coolify(self, resource: ResourceRecord) -> None:
        """Delete a Coolify application.

        Args:
            resource: Coolify resource record
        """
        uuid = resource.resource_id
        try:
            self.coolify_client.delete_application(uuid)
            logger.info("Deleted Coolify application: %s", uuid)
        except Exception as e:
            raise RollbackError(
                f"Failed to delete Coolify app {uuid}: {e}",
                resource_type="coolify",
            ) from e

    def _rollback_dns(self, resource: ResourceRecord) -> None:
        """Delete a DNS record.

        Args:
            resource: DNS resource record
        """
        record_id = resource.resource_id
        zone = resource.metadata.get("zone")

        if not zone:
            logger.warning("DNS record %s has no zone metadata, skipping", record_id)
            return

        try:
            self.dns_client.delete_record(zone, record_id)
            logger.info("Deleted DNS record: %s", record_id)
        except Exception as e:
            raise RollbackError(
                f"Failed to delete DNS record {record_id}: {e}",
                resource_type="dns",
            ) from e

    def _rollback_monitor(self, resource: ResourceRecord) -> None:
        """Delete an Uptime Kuma monitor.

        Args:
            resource: Monitor resource record
        """
        monitor_id = resource.resource_id
        logger.info("Would delete monitor: %s (not implemented)", monitor_id)
