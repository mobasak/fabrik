"""Coolify deployment with idempotency."""

import logging
import os
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

        Raises:
            DeployError: If Coolify API call fails (fail fast, don't hide errors)
        """
        # Fail fast on API errors - don't swallow and risk duplicate deployments
        apps = self.client.list_applications()
        for app in apps:
            if app.get("name") == name:
                logger.info("Found existing deployment: %s (uuid=%s)", name, app.get("uuid"))
                return app
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
        domain = ctx.spec.get("domain", "")

        if ctx.dry_run:
            logger.info("[DRY RUN] Would deploy %s to %s", name, domain or "(no domain)")
            return "dry-run-uuid"

        # Check for existing deployment
        existing = self.find_existing(name)

        try:
            if existing:
                uuid = existing["uuid"]
                logger.info("Updating existing deployment: %s", uuid)
                self._update_deployment(uuid, ctx)
                # NOTE: Do NOT add to created_resources on UPDATE
                # Only rollback resources we CREATE, not pre-existing ones
            else:
                logger.info("Creating new deployment: %s", name)
                uuid = self._create_deployment(ctx)
                # Only track newly created resources for rollback
                ctx.add_resource("coolify", uuid, name=name)

            ctx.coolify_uuid = uuid
            return uuid

        except Exception as e:
            raise DeployError(f"Deployment failed: {e}", coolify_error=str(e)) from e

    def _resolve_project_server_uuids(self) -> tuple[str, str]:
        """Resolve Coolify server and project UUIDs.

        Mirrors the UUID-resolution logic in deploy.py:
        - Server: env var or first from list_servers()
        - Project: env var or find/create 'fabrik' project

        Returns:
            (server_uuid, project_uuid)

        Raises:
            DeployError: If no servers found
        """
        server_uuid = os.environ.get("COOLIFY_SERVER_UUID")
        if not server_uuid:
            servers = self.client.list_servers()
            if not servers:
                raise DeployError("No Coolify servers found. Set COOLIFY_SERVER_UUID.")
            server_uuid = servers[0]["uuid"]

        project_uuid = os.environ.get("COOLIFY_PROJECT_UUID")
        if not project_uuid:
            projects = self.client.list_projects()
            for proj in projects:
                if proj.get("name") == "fabrik":
                    project_uuid = proj["uuid"]
                    break
            if not project_uuid:
                result = self.client.create_project("fabrik", "Fabrik apps")
                project_uuid = result["uuid"]

        return server_uuid, project_uuid

    def _create_deployment(self, ctx: DeploymentContext) -> str:
        """Create a new Coolify deployment.

        Args:
            ctx: Deployment context

        Returns:
            New application UUID
        """
        from fabrik.spec_loader import Spec
        from fabrik.template_renderer import TemplateRenderer

        spec = ctx.spec

        server_uuid, project_uuid = self._resolve_project_server_uuids()

        # Build spec_dict preserving all user fields (resources, volumes, depends, etc.)
        spec_dict = dict(spec)
        spec_dict["id"] = spec.get("id", spec["name"])
        spec_dict.pop("name", None)  # Remove orchestrator-only key

        # Ensure env is a dict (validator allows it to be absent)
        if not isinstance(spec_dict.get("env"), dict):
            spec_dict["env"] = {}

        spec_obj = Spec(**spec_dict)

        rendered = TemplateRenderer().render(spec_obj, secrets=ctx.secrets, dry_run=True)
        compose_content = rendered["compose.yaml"]

        result = self.client.create_dockercompose_application(
            project_uuid=project_uuid,
            server_uuid=server_uuid,
            docker_compose_raw=compose_content,
            name=spec["name"],
            instant_deploy=True,
        )

        uuid = result.get("uuid") or result.get("id")
        if not uuid:
            raise DeployError(
                "Coolify API response missing 'uuid' or 'id'",
                coolify_error=str(result),
            )
        return uuid

    def _update_deployment(self, uuid: str, ctx: DeploymentContext) -> None:
        """Update an existing Coolify deployment.

        Args:
            uuid: Existing application UUID
            ctx: Deployment context
        """
        spec = ctx.spec
        domain = spec.get("domain")

        # Update application metadata (fqdn only if domain is set)
        if domain:
            self.client.update_application(
                uuid=uuid,
                fqdn=f"https://{domain}",
            )

        # Build environment from spec + secrets
        # NOTE: Secrets are passed to Coolify API. Ensure HTTP client debug
        # logging is disabled in production to avoid exposing secret values.
        env_vars = dict(spec.get("env", {}))
        for key, value in ctx.secrets.items():
            env_vars[key] = value

        # Use dedicated bulk_update_env_vars - update_application ignores env_vars
        if env_vars:
            self.client.bulk_update_env_vars(uuid, env_vars)

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
