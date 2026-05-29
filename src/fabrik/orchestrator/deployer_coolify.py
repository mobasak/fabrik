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

    def _resolve_private_key_uuid(self, spec: dict[str, Any]) -> str | None:
        """Resolve the Coolify SSH deploy-key UUID for a git-sourced app.

        Precedence:

        1. ``spec.coolify.private_key_uuid`` — per-service override.
        2. ``COOLIFY_PRIVATE_KEY_UUID`` environment variable — operator
           default, usually the ``github-deploy-key`` UUID.
        3. Auto-discovery via ``CoolifyClient.list_private_keys()`` —
           prefer keys with ``is_git_related=True``, then keys whose
           name contains ``deploy`` or ``github``.

        Only required for SSH-URL repos (``git@...``). Returns ``None``
        for HTTPS-cloneable repos so the caller routes to
        ``/applications/public``.

        Context (2026-05-04): the 2026-04-26 removal of this helper
        assumed Coolify v4.0.0+ auto-selects SSH keys. It does not.
        Apps created without ``private_key_uuid`` land with
        ``private_key_id=NULL`` and fail ``git ls-remote`` on the first
        deploy. See ``create_git_application`` docstring.
        """
        spec_key = spec.get("coolify", {}).get("private_key_uuid")
        if spec_key:
            return spec_key

        env_key = os.environ.get("COOLIFY_PRIVATE_KEY_UUID", "").strip()
        if "#" in env_key:
            env_key = env_key.split("#", 1)[0].strip()
        if env_key and len(env_key) >= 8 and all(c.isalnum() or c in "-_" for c in env_key):
            return env_key

        try:
            keys = self.client.list_private_keys()
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not list Coolify private keys: %s", e)
            return None

        # Prefer explicitly git-related keys.
        for k in keys:
            if k.get("is_git_related"):
                return k.get("uuid")
        # Then name-based heuristic.
        for k in keys:
            name = (k.get("name") or "").lower()
            if "deploy" in name or "github" in name:
                return k.get("uuid")

        logger.warning(
            "No git-related SSH key found in Coolify; "
            "set COOLIFY_PRIVATE_KEY_UUID for private SSH repos"
        )
        return None

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
        # For GIT deploys (revised 2026-05-04): we now create with
        # instant_deploy=False and push env vars before triggering the
        # build, so the FIRST /deploy call must come from here. This is
        # not a "redundant force-deploy" (the original B17 concern) — it
        # is the only deploy fired for the app.
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

        # Resolve SSH deploy key for SSH-URL repos. For git@ URLs a key
        # is required; for https:// URLs we pass None and Coolify routes
        # to /applications/public. See CoolifyClient.create_git_application
        # docstring for the 2026-05-04 reason this is not optional.
        private_key_uuid: str | None = None
        is_ssh_repo = git_repository.startswith("git@") or git_repository.startswith("ssh://")
        if is_ssh_repo:
            private_key_uuid = self._resolve_private_key_uuid(spec)
            if not private_key_uuid:
                raise DeployError(
                    f"SSH git repo '{git_repository}' requires a Coolify deploy key. "
                    "Set COOLIFY_PRIVATE_KEY_UUID or spec.coolify.private_key_uuid, "
                    "or register a git-related key in Coolify."
                )

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
            # B17 (revised 2026-05-04): instant_deploy=False so env vars
            # can be pushed BEFORE the build starts. With instant_deploy=True
            # the build kicks off immediately with no env vars set, so
            # services that need DB credentials / API keys at runtime fail
            # their healthcheck and exit unhealthy. A SINGLE /deploy call
            # AFTER env-var injection avoids the original B17 race (which
            # was specifically about firing a redundant force-deploy on top
            # of an in-progress instant_deploy=True build — different
            # scenario).
            instant_deploy=False,
            domains=domains_field,
            private_key_uuid=private_key_uuid,
        )

        uuid = result.get("uuid") or result.get("id")
        if not uuid:
            raise DeployError(
                "Coolify API response missing 'uuid' or 'id'",
                coolify_error=str(result),
            )

        # Fix 3 (Coolify .env race, 2026-05-16): Coolify's dockercompose
        # build-pack adds `env_file: .env` to the rewritten compose but
        # doesn't create the .env file until env vars are pushed. If the
        # file is missing, `docker compose config` fails before the build
        # even starts (silent failure — Coolify issue #9161). Pre-seed an
        # empty .env so compose validation passes regardless of push timing.
        try:
            from fabrik.drivers.ssh import ssh as _ssh

            _ssh(
                f"sudo mkdir -p /data/coolify/applications/{uuid} && "
                f"sudo touch /data/coolify/applications/{uuid}/.env"
            )
            logger.debug("Pre-seeded .env for Coolify app %s", uuid)
        except Exception as exc:  # noqa: BLE001 — non-fatal; env push below will create it
            logger.warning("Failed to pre-seed .env for %s (non-fatal): %s", uuid, exc)

        # Push env vars + secrets BEFORE triggering the deploy so the first
        # build has them in scope. Same construction as _update_existing.
        env_vars = dict(spec.get("env", {}))
        for key, value in ctx.secrets.items():
            env_vars[key] = value
        if env_vars:
            self.client.bulk_update_env_vars(uuid, env_vars)
            logger.info(
                "Pushed %d env vars to git-sourced app %s before initial deploy",
                len(env_vars),
                uuid,
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
        # B46 revised 2026-05-16: bumped from 180s to 300s. The 180s value
        # was set during docusaurus-only proof-runs (max build ~110s). Python-api
        # pip-install multi-stage builds take ~200s on this VPS, hitting the grace
        # limit and false-positiving as failed. 300s covers all observed types
        # with margin while still failing genuinely broken deploys promptly
        # (Coolify's explicit "failed" state fires within seconds on real errors).
        terminal_grace_period = 300.0
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
                        uuid,
                        status,
                        terminal_grace_period,
                    )
                elif time.time() - terminal_first_seen >= terminal_grace_period:
                    logger.warning(
                        "Coolify app %s sustained terminal-failure state %s for %.0fs; "
                        "attempting SSH fallback build+up (Coolify issue #9161 workaround)",
                        uuid,
                        status,
                        terminal_grace_period,
                    )
                    # Fix 2 (Coolify silent build-trigger, 2026-05-16):
                    # Coolify's dockercompose build-pack sometimes writes the
                    # compose + image tag but never actually executes `docker
                    # compose build && up`. If the grace period expires with
                    # the app in a terminal state, SSH into the VPS and kick
                    # the build manually from Coolify's own application dir.
                    return bool(self._ssh_fallback_build(uuid))
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

    def _ssh_fallback_build(self, uuid: str, timeout: int = 180) -> bool:
        """Fix 2 workaround: SSH into VPS and manually clone+build+up.

        Coolify v4.0.0-beta.459 has a confirmed silent-build-trigger bug
        (GitHub issue #9161) where the orchestration step never clones the
        git repo into the app directory, never builds the image, and never
        starts the container. The API reports ``exited:unhealthy`` indefinitely.

        Coolify's app dir (``/data/coolify/applications/<uuid>/``) contains
        only the rewritten ``docker-compose.yaml`` + ``.env`` — no source
        code. This fallback:

        1. Reads the git repo + branch from the Coolify API (or compose).
        2. Clones the repo into the app dir (alongside the compose).
        3. Runs ``docker compose build && docker compose up -d``.

        Returns ``True`` if the container reaches ``running:*`` within 90s.
        """
        import time

        from fabrik.drivers.ssh import ssh

        app_dir = f"/data/coolify/applications/{uuid}"
        logger.info("SSH fallback: cloning + building from %s", app_dir)

        # Get git repo + branch from Coolify API
        try:
            app_info = self.client.get_application(uuid)
            git_repo = (app_info or {}).get("git_repository", "")
            git_branch = (app_info or {}).get("git_branch", "main")
            # Coolify stores repo as "owner/repo.git" — prefix with https://github.com/
            if git_repo and not git_repo.startswith("http"):
                git_repo = f"https://github.com/{git_repo}"
        except Exception as exc:  # noqa: BLE001
            logger.warning("SSH fallback: can't read app info: %s", exc)
            return False

        if not git_repo:
            logger.warning("SSH fallback: no git_repository in app %s", uuid)
            return False

        try:
            # Clone the repo INTO the app dir (git clone into existing dir
            # with files requires `git init` + `fetch` + `checkout`).
            ssh(
                f"cd {app_dir} && "
                f"git init -q && "
                f"git remote add origin {git_repo} 2>/dev/null || git remote set-url origin {git_repo} && "
                f"git fetch --depth 1 origin {git_branch} && "
                f"git checkout FETCH_HEAD -- . ",
                timeout=60,
            )
            logger.info("SSH fallback: repo cloned into %s (branch=%s)", app_dir, git_branch)

            # Build the image using Coolify's rewritten docker-compose.yaml
            # (NOT the repo's compose.yaml — Coolify's version has the correct
            # UUID-based container_name that Coolify monitors for status).
            ssh(
                f"cd {app_dir} && sudo docker compose -f docker-compose.yaml build 2>&1 | tail -5",
                timeout=timeout,
            )
            logger.info("SSH fallback: image built")

            # Start the container
            ssh(
                f"cd {app_dir} && sudo docker compose -f docker-compose.yaml up -d 2>&1 | tail -5",
                timeout=30,
            )
            logger.info("SSH fallback: docker compose up -d executed")
        except Exception as exc:  # noqa: BLE001
            logger.warning("SSH fallback build failed: %s", exc)
            return False

        # Wait for the container to come up healthy (poll Coolify status)
        start = time.time()
        while time.time() - start < 90:
            try:
                app = self.client.get_application(uuid)
                status = (app or {}).get("status", "") or ""
            except Exception:  # noqa: BLE001
                status = ""
            if status.startswith("running"):
                logger.info("SSH fallback succeeded: app %s now %s", uuid, status)
                return True
            time.sleep(5)
        logger.warning("SSH fallback: container still not running after clone+build+up")
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
