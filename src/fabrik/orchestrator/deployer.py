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

    def _resolve_project_server_uuids(
        self, ctx: DeploymentContext | None = None
    ) -> tuple[str, str]:
        """Resolve Coolify server and project UUIDs.

        Resolution order (highest precedence first):
        1. Env vars ``COOLIFY_SERVER_UUID`` / ``COOLIFY_PROJECT_UUID`` (operator override)
        2. ``spec.coolify.server`` / ``spec.coolify.project`` (declared in the spec)
        3. First server from ``list_servers()`` / project named ``"fabrik"`` (legacy fallback)

        ``spec.coolify`` values are resolved by name against ``list_servers()`` and
        ``list_projects()``. If the named project is missing, it is created. This
        means specs like ``coolify.project: fabrik-services`` are honored without
        needing to set ``COOLIFY_PROJECT_UUID`` in every environment.

        Args:
            ctx: Deployment context (optional for backward compatibility; without
                it, only env-var + legacy fallback resolution is used).

        Returns:
            (server_uuid, project_uuid)

        Raises:
            DeployError: If no servers found
        """
        spec_coolify: dict[str, Any] = {}
        if ctx is not None:
            spec_coolify = ctx.spec.get("coolify") or {}

        # Server
        server_uuid = os.environ.get("COOLIFY_SERVER_UUID")
        if not server_uuid:
            servers = self.client.list_servers()
            if not servers:
                raise DeployError("No Coolify servers found. Set COOLIFY_SERVER_UUID.")
            spec_server_name = spec_coolify.get("server")
            if spec_server_name:
                match = next(
                    (s for s in servers if s.get("name") == spec_server_name),
                    None,
                )
                server_uuid = match["uuid"] if match else servers[0]["uuid"]
                if not match:
                    logger.warning(
                        "spec.coolify.server=%r not found; falling back to first server (%s)",
                        spec_server_name,
                        servers[0].get("name"),
                    )
            else:
                server_uuid = servers[0]["uuid"]

        # Project
        project_uuid = os.environ.get("COOLIFY_PROJECT_UUID")
        if not project_uuid:
            spec_project_name = spec_coolify.get("project") or "fabrik"
            projects = self.client.list_projects()
            for proj in projects:
                if proj.get("name") == spec_project_name:
                    project_uuid = proj["uuid"]
                    break
            if not project_uuid:
                result = self.client.create_project(
                    spec_project_name, f"Fabrik project {spec_project_name}"
                )
                project_uuid = result["uuid"]

        return server_uuid, project_uuid

    def _resolve_environment_uuid(self, project_uuid: str) -> str:
        """Resolve the UUID of the 'production' environment for a project.

        The /applications endpoint requires an explicit ``environment_uuid``
        (unlike /applications/dockercompose which only needs ``environment_name").
        This helper fetches it from the Coolify project details.

        Args:
            project_uuid: Coolify project UUID

        Returns:
            Environment UUID

        Raises:
            DeployError: If no production environment found
        """
        env_uuid = os.environ.get("COOLIFY_ENVIRONMENT_UUID", "").strip()
        # Strip inline comments and whitespace — defensive against malformed
        # `.env` entries like ``COOLIFY_ENVIRONMENT_UUID=  # auto-detect``
        # which python-dotenv parses as the literal string ``# auto-detect``.
        if "#" in env_uuid:
            env_uuid = env_uuid.split("#", 1)[0].strip()
        # Coolify UUIDs are at least 8 chars (alphanumeric + dashes/underscores
        # in the general UUID grammar). Anything shorter or containing
        # whitespace is a malformed value and we should fall through to
        # the API lookup rather than send Coolify garbage.
        if env_uuid and len(env_uuid) >= 8 and all(c.isalnum() or c in "-_" for c in env_uuid):
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

    def _create_deployment(self, ctx: DeploymentContext) -> str:
        """Create a new Coolify deployment.

        Dispatches to the correct Coolify API endpoint based on source type:
        - ``source.type=git`` → ``/applications`` with ``build_pack=dockercompose``.
          The compose is pulled from the git repo, not rendered inline.
          Coolify v4.0.0+ auto-selects SSH keys based on the repo URL.
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

        server_uuid, project_uuid = self._resolve_project_server_uuids(ctx)

        if source.type == SourceType.GIT:
            uuid = self._create_git_deployment(ctx, source, server_uuid, project_uuid)
        else:
            uuid = self._create_inline_deployment(ctx, server_uuid, project_uuid)

        # Coolify's `instant_deploy: true` on POST /applications/dockercompose
        # (inline) does NOT reliably start the container (leaves service at
        # status=exited). Explicitly trigger /deploy in that case.
        # For GIT deploys, instant_deploy=True works correctly (verified
        # 2026-04-27) and a redundant force-deploy fired immediately after
        # create races with the in-progress build, which produces
        # ``exited:unhealthy`` even though the build itself was succeeding.
        # B17 fix: only force-deploy on the inline path.
        if source.type != SourceType.GIT:
            try:
                self.client.deploy(uuid, force=True)
                logger.info("Triggered deploy for %s", uuid)
            except Exception as e:  # noqa: BLE001
                logger.warning("Post-create deploy trigger failed (non-fatal): %s", e)

        # Give Coolify some time to actually spin up the container before
        # downstream steps (verification, Traefik router check) probe it.
        # Git-sourced apps take longer (git clone + docker build), and the
        # *first* build per repo on Coolify can hit cold caches: pulling
        # base images, installing deps from scratch, etc. 10 min covers
        # python-api / saas-skeleton first builds with margin.
        wait_time = 600 if source.type == SourceType.GIT else 90
        # B11: prefer Coolify app-status API over docker name pattern. The
        # docker container name is determined by the compose service name
        # (e.g. ``app-<uuid>-<ts>`` when the user's compose declares a
        # generic ``app:`` service), not by the Coolify app name. Polling
        # the API by uuid is name-agnostic.
        if not self._wait_for_app_status(uuid, max_wait=wait_time):
            self._wait_for_container(spec["name"], max_wait=30)
        return uuid

    def _create_git_deployment(
        self,
        ctx: DeploymentContext,
        source: Source,
        server_uuid: str,
        project_uuid: str,
    ) -> str:
        """Create a git-sourced Coolify application.

        Uses Coolify's ``/applications`` endpoint with git_repository and
        git_branch fields. Coolify v4.0.0+ auto-selects SSH keys based on the
        repo URL from configured SSH keys in Coolify settings — no manual
        private key UUID resolution needed. The compose is pulled from the
        git repo on deploy — no inline compose YAML is rendered.

        Args:
            ctx: Deployment context
            source: Parsed Source object with type=GIT
            server_uuid: Coolify server UUID
            project_uuid: Coolify project UUID

        Returns:
            New application UUID

        Raises:
            DeployError: If git_repository is missing
        """
        spec = ctx.spec
        git_repository = source.repository
        if not git_repository:
            raise DeployError("Git-sourced deployment requires 'source.repository' in spec")

        environment_uuid = self._resolve_environment_uuid(project_uuid)

        # Determine compose location from spec or default
        docker_compose_location = spec.get("coolify", {}).get(
            "docker_compose_location", "/compose.yaml"
        )

        # B13: pass ``domains`` so Coolify configures Traefik to route the
        # spec's FQDN. Without this, Coolify auto-generates an sslip.io URL
        # and the post-deploy verifier (which probes the spec domain) 404s.
        spec_domain = spec.get("domain")
        domains_field: str | None = None
        if spec_domain:
            # Coolify accepts ``https://<host>`` (with scheme) — using https
            # also flips ``is_force_https_enabled`` semantics correctly so
            # Traefik issues the redirect and Let's Encrypt cert.
            domains_field = f"https://{spec_domain}"

        result = self.client.create_git_application(
            project_uuid=project_uuid,
            server_uuid=server_uuid,
            environment_uuid=environment_uuid,
            git_repository=git_repository,
            git_branch=source.branch,
            build_pack="dockercompose",
            docker_compose_location=docker_compose_location,
            name=spec["name"],
            description=spec.get("description", ""),
            # B17: instant_deploy=True so Coolify performs a single,
            # uninterrupted build. A redundant force-deploy fired after the
            # create races with the in-progress build and produces
            # ``exited:unhealthy``. Verified clean run with True on
            # /applications/public, 2026-04-27.
            instant_deploy=True,
            domains=domains_field,
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

        # B7 preflight: Coolify's inline-compose endpoint receives only the
        # rendered compose YAML, not the source tree. A compose with a
        # ``build:`` directive therefore cannot resolve its build context —
        # the build silently never happens and no container is created.
        # Fail-fast with a clear error before the request hits Coolify.
        if "build:" in compose_content and spec_obj.source.type != SourceType.GIT:
            raise DeployError(
                f"Spec {spec.get('name')!r} renders a compose with `build:` but "
                f"`source.type` is {spec_obj.source.type.value!r} (not 'git'). "
                "Coolify's inline-compose endpoint has no source for `build:` to "
                "consume — the build will never run. Either:\n"
                "  1. Add a git remote and re-emit the spec:\n"
                f"       git -C /opt/{spec.get('name')} remote add origin <url>\n"
                f"       git -C /opt/{spec.get('name')} push -u origin main\n"
                "       # then re-run the scaffolder spec emitter to refresh the spec\n"
                "  2. Or rewrite the compose template to use `image:` from a registry."
            )

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

    def _wait_for_app_status(self, uuid: str, max_wait: int = 600) -> bool:
        """Poll Coolify's app-status API until ``status`` reaches ``running``.

        B11: Replaces the brittle ``docker ps | grep <name>-`` strategy
        which assumed the compose service name == Coolify app name. In
        practice, scaffolded composes often declare a generic ``app:``
        service so the container is ``app-<uuid>-<ts>``. Polling the
        Coolify API by uuid is name-agnostic and rollback-aware.

        B17: terminal-failure states (``exited:*``, ``degraded:exited``,
        ``killed``) are observed transiently during normal deploy cycles
        — Coolify briefly reports the *old* container's exited status
        before the new container's status overwrites it. Verified
        2026-04-27: the previous "bail on first terminal state" logic
        produced false-positive failures on healthy deploys (container
        was Up + healthy on the VPS but the orchestrator had already
        rolled back). Fix: require the terminal state to persist for
        ``terminal_grace_period`` seconds before treating it as a real
        failure.

        Returns ``True`` once the app reports ``running:*`` (running:healthy
        or running:unhealthy — both indicate the container exists).
        Returns ``False`` on timeout or **sustained** terminal failure.
        """
        import time

        start = time.time()
        last_status = ""
        terminal_failure_states = ("exited", "degraded:exited", "killed")
        # B46: 180s grace (was 30s). Docusaurus's git-source build takes
        # 60-90s for ``npm install`` + ``npm run build`` + image export,
        # during which Coolify reports the application status as
        # ``exited:unhealthy`` (old container removed, new image not yet
        # running). 30s gave up well before the new container even
        # started, marking healthy deploys as failed. 180s comfortably
        # covers all observed slow-build types (docusaurus, saas-skeleton
        # Next.js multi-stage, file-api with R2/Supabase deps) without
        # significantly slowing failure detection on genuinely broken
        # deploys (failures still terminate via the explicit Coolify
        # ``failed`` state, which is reported promptly by the deployment
        # job, not via this terminal-state grace path). Surfaced by
        # proof-run on 2026-04-28 \u2014 docusaurus container reached
        # ``running:healthy`` ~110s after this method gave up at 30s.
        terminal_grace_period = 180.0
        terminal_first_seen: float | None = None
        while time.time() - start < max_wait:
            try:
                app = self.client.get_application(uuid)
                status = (app or {}).get("status", "") or ""
            except Exception:  # noqa: BLE001
                status = ""
            if status != last_status:
                logger.info("Coolify app %s status: %s", uuid, status or "(unknown)")
                last_status = status
            if status.startswith("running"):
                return True
            is_terminal = any(status.startswith(s) for s in terminal_failure_states)
            if is_terminal:
                if terminal_first_seen is None:
                    terminal_first_seen = time.time()
                    logger.info(
                        "Coolify app %s reported terminal state %s; "
                        "waiting up to %.0fs to confirm (deploy-recreate transient possible)",
                        uuid, status, terminal_grace_period,
                    )
                elif time.time() - terminal_first_seen >= terminal_grace_period:
                    logger.warning(
                        "Coolify app %s sustained terminal-failure state %s for %.0fs",
                        uuid, status, terminal_grace_period,
                    )
                    return False
            else:
                terminal_first_seen = None
            time.sleep(5)
        logger.warning(
            "Coolify app %s did not reach running:* within %ds (last status: %s)",
            uuid,
            max_wait,
            last_status or "(none)",
        )
        return False

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
