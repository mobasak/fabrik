"""Coolify deployment with idempotency."""

import logging
import os
from typing import Any

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import DeployError
from fabrik.spec_loader import Source, SourceType

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

    def _resolve_environment_uuid(self, project_uuid: str) -> str:
        """Resolve the UUID of the 'production' environment for a project.

        The /applications/private-deploy-key endpoint requires an explicit
        ``environment_uuid`` (unlike /applications/dockercompose which only
        needs ``environment_name"). This helper fetches it from the
        Coolify project details.

        Args:
            project_uuid: Coolify project UUID

        Returns:
            Environment UUID

        Raises:
            DeployError: If no production environment found
        """
        env_uuid = os.environ.get("COOLIFY_ENVIRONMENT_UUID")
        if env_uuid:
            return env_uuid

        project = self.client.get_project(project_uuid)
        envs = project.get("environments", [])
        for env in envs:
            if env.get("name") == "production":
                return env["uuid"]
        # Fallback: first environment
        if envs:
            return envs[0]["uuid"]

        raise DeployError(
            f"No environments found in Coolify project {project_uuid}. "
            "Set COOLIFY_ENVIRONMENT_UUID or create an environment in Coolify."
        )

    def _resolve_private_key_uuid(self) -> str | None:
        """Resolve the UUID of a git-related SSH deploy key in Coolify.

        Looks up Coolify's security keys and returns the first key
        marked as ``is_git_related`` or whose name suggests it's a deploy
        key. Returns None if no suitable key is found (public repos
        don't need one).

        Returns:
            Private key UUID or None
        """
        key_uuid = os.environ.get("COOLIFY_PRIVATE_KEY_UUID")
        if key_uuid:
            return key_uuid

        try:
            keys = self.client.list_private_keys()
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not list Coolify private keys: %s", e)
            return None

        # Prefer git-related keys, then fall back to any non-localhost key
        for key in keys:
            if key.get("is_git_related"):
                return key["uuid"]
        for key in keys:
            name = (key.get("name") or "").lower()
            if "deploy" in name or "github" in name:
                return key["uuid"]

        logger.warning(
            "No git-related SSH key found in Coolify; "
            "set COOLIFY_PRIVATE_KEY_UUID for private repos"
        )
        return None

    def _create_deployment(self, ctx: DeploymentContext) -> str:
        """Create a new Coolify deployment.

        Dispatches to the correct Coolify API endpoint based on source type:
        - ``source.type=git`` → ``/applications/private-deploy-key`` (or
          ``/applications`` for public repos) with ``build_pack=dockercompose``.
          The compose is pulled from the git repo, not rendered inline.
        - ``source.type=template`` or ``docker`` → ``/applications/dockercompose``
          with inline rendered compose YAML.

        Args:
            ctx: Deployment context

        Returns:
            New application UUID
        """
        spec = ctx.spec
        source = spec.get("source", {})

        # Normalize source to a Source object if it's a raw dict
        if isinstance(source, dict):
            source_type_str = source.get("type", "template")
            type_map = {
                "docker": SourceType.DOCKER,
                "git": SourceType.GIT,
                "template": SourceType.TEMPLATE,
            }
            source = Source(
                **{**source, "type": type_map.get(source_type_str, SourceType.TEMPLATE)}
            )

        server_uuid, project_uuid = self._resolve_project_server_uuids()

        if source.type == SourceType.GIT:
            uuid = self._create_git_deployment(ctx, source, server_uuid, project_uuid)
        else:
            uuid = self._create_inline_deployment(ctx, server_uuid, project_uuid)

        # Coolify's `instant_deploy: true` on POST /applications/dockercompose
        # does NOT reliably start the container (leaves service at status=exited).
        # Explicitly trigger /deploy to ensure the container is created and started.
        try:
            self.client.deploy(uuid, force=True)
            logger.info("Triggered deploy for %s", uuid)
        except Exception as e:  # noqa: BLE001
            logger.warning("Post-create deploy trigger failed (non-fatal): %s", e)

        # Give Coolify some time to actually spin up the container before
        # downstream steps (verification, Traefik router check) probe it.
        self._wait_for_container(spec["name"], max_wait=90)
        return uuid

    def _create_git_deployment(
        self,
        ctx: DeploymentContext,
        source: Source,
        server_uuid: str,
        project_uuid: str,
    ) -> str:
        """Create a git-sourced Coolify application.

        Uses Coolify's ``/applications/private-deploy-key`` endpoint for
        private repos (with SSH deploy key) or ``/applications`` for public
        repos. The compose is pulled from the git repo on deploy — no
        inline compose YAML is rendered.

        Args:
            ctx: Deployment context
            source: Parsed Source object with type=GIT
            server_uuid: Coolify server UUID
            project_uuid: Coolify project UUID

        Returns:
            New application UUID

        Raises:
            DeployError: If git_repository is missing or private key not found
        """
        spec = ctx.spec
        git_repository = source.repository
        if not git_repository:
            raise DeployError("Git-sourced deployment requires 'source.repository' in spec")

        environment_uuid = self._resolve_environment_uuid(project_uuid)

        # Resolve SSH deploy key for private repos
        private_key_uuid = None
        repo_url = git_repository.lower()
        is_private = repo_url.startswith("git@") or "git@github.com" in repo_url
        if is_private:
            private_key_uuid = self._resolve_private_key_uuid()
            if not private_key_uuid:
                raise DeployError(
                    f"Private git repo '{git_repository}' requires an SSH deploy key. "
                    "Set COOLIFY_PRIVATE_KEY_UUID or register a git-related key in Coolify."
                )

        # Determine compose location from spec or default
        docker_compose_location = spec.get("coolify", {}).get(
            "docker_compose_location", "/compose.yaml"
        )

        result = self.client.create_git_application(
            project_uuid=project_uuid,
            server_uuid=server_uuid,
            environment_uuid=environment_uuid,
            git_repository=git_repository,
            git_branch=source.branch,
            private_key_uuid=private_key_uuid,
            build_pack="dockercompose",
            docker_compose_location=docker_compose_location,
            name=spec["name"],
            description=spec.get("description", ""),
            instant_deploy=False,  # Git apps: first deploy = git pull + build
        )

        uuid = result.get("uuid") or result.get("id")
        if not uuid:
            raise DeployError(
                "Coolify API response missing 'uuid' or 'id'",
                coolify_error=str(result),
            )
        logger.info(
            "Created git-sourced app %s (uuid=%s, repo=%s, branch=%s)",
            spec["name"],
            uuid,
            git_repository,
            source.branch,
        )
        return uuid

    def _create_inline_deployment(
        self,
        ctx: DeploymentContext,
        server_uuid: str,
        project_uuid: str,
    ) -> str:
        """Create an inline-compose Coolify application.

        Renders compose.yaml from the spec template and posts it to
        Coolify's ``/applications/dockercompose`` endpoint. This is the
        original path for template/docker-sourced apps.

        Args:
            ctx: Deployment context
            server_uuid: Coolify server UUID
            project_uuid: Coolify project UUID

        Returns:
            New application UUID
        """
        from fabrik.spec_loader import Spec
        from fabrik.template_renderer import TemplateRenderer

        spec = ctx.spec

        # Build spec_dict preserving all user fields (resources, volumes, depends, etc.)
        spec_dict = dict(spec)
        spec_dict["id"] = spec.get("id", spec["name"])
        spec_dict.pop("name", None)  # Remove orchestrator-only key

        # Ensure env is a dict (validator allows it to be absent)
        if not isinstance(spec_dict.get("env"), dict):
            spec_dict["env"] = {}

        # Convert nested dict fields to their proper types to avoid default_factory overrides
        if "source" in spec_dict and isinstance(spec_dict["source"], dict):
            source_dict = spec_dict["source"]
            # Convert type string to enum
            if "type" in source_dict and isinstance(source_dict["type"], str):
                type_map = {
                    "docker": SourceType.DOCKER,
                    "git": SourceType.GIT,
                    "template": SourceType.TEMPLATE,
                }
                source_dict["type"] = type_map.get(source_dict["type"], SourceType.TEMPLATE)
            spec_dict["source"] = Source(**source_dict)

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
        logger.info("Created inline-compose app %s (uuid=%s)", spec["name"], uuid)
        return uuid

    def _wait_for_container(self, name: str, max_wait: int = 90) -> bool:
        """Poll via SSH until a container named `<name>-*` is Up, or timeout."""
        import time

        from fabrik.drivers.ssh import ssh

        start = time.time()
        while time.time() - start < max_wait:
            try:
                out = ssh(
                    f"sudo docker ps --format '{{{{.Names}}}}\\t{{{{.Status}}}}' | grep '^{name}-' | head -1"
                ).strip()
            except Exception:  # noqa: BLE001
                out = ""
            if out and "Up" in out:
                logger.info("Container ready: %s", out.split()[0])
                return True
            time.sleep(5)
        logger.warning("Container %s-* did not come up within %ds", name, max_wait)
        return False

    def _update_deployment(self, uuid: str, ctx: DeploymentContext) -> None:
        """Update an existing Coolify deployment.

        Args:
            uuid: Existing application UUID
            ctx: Deployment context
        """
        spec = ctx.spec
        domain = spec.get("domain")

        # fqdn PATCH is only valid for dockerfile / buildpack applications on
        # `/applications/{uuid}`. It is rejected (HTTP 422 "fqdn: not allowed")
        # for dockercompose applications and for `/services/{uuid}`. In both
        # of those cases the domain is carried by the compose's Traefik labels
        # (rendered by TemplateRenderer for template-sourced apps, or by the
        # upstream repo's compose.yaml for git-sourced apps). Auto-route by
        # UUID AND skip when the application's build_pack is dockercompose.
        if domain:
            resource_base = self.client._resolve_resource_base(uuid)
            if resource_base == "applications":
                # Look up build_pack — dockercompose apps reject fqdn PATCH.
                build_pack = None
                try:
                    apps = self.client.list_applications()
                    match = next((a for a in apps if a.get("uuid") == uuid), None)
                    if match:
                        build_pack = match.get("build_pack")
                except Exception as e:  # noqa: BLE001
                    logger.warning("Could not resolve build_pack for %s: %s", uuid, e)

                if build_pack == "dockercompose":
                    logger.info(
                        "Skipping fqdn PATCH for dockercompose app %s "
                        "(domain carried by compose Traefik labels)",
                        uuid,
                    )
                else:
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
