"""SSH + Docker Compose deployer — replaces Coolify API deployer.

Deploys services by rendering compose files locally, copying them to the VPS
via SCP, and running ``docker compose up -d`` over SSH.  Supports all four
source types: TEMPLATE, GIT, DOCKER, LOCAL.

Design doc: ``docs/development/plans/archived/2026-05-28-ssh-deployer.md``
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import subprocess
import tempfile
import time
from collections.abc import Callable
from typing import Any

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import DeployError
from fabrik.spec_loader import Source, SourceType

logger = logging.getLogger(__name__)

# Shell-safe name pattern — prevents injection in SSH commands.
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

# health.disabled readiness poll (see _compose_up): `docker compose up --wait` needs a
# healthcheck a FROM-scratch image can't have, so we `up -d` then poll `docker inspect` for a
# STABLE running state. Requires _HEALTH_STABLE_REQUIRED consecutive polls at running + an
# unchanged RestartCount; a crash-loop (exited/restarting/RestartCount climbing) exhausts the
# polls and fails the deploy — a broken container must never slip through as a false success.
_HEALTH_POLLS = 6
_HEALTH_STABLE_REQUIRED = 2
_HEALTH_POLL_INTERVAL = 4

# `docker compose build` wall-clock cap. 300s starves a heavy FIRST build (review finding
# 2026-08-10: tryton-crm's image bakes tesseract + language packs + poppler + pinned pip
# layers — a cold build plausibly exceeds 5 min and the apply died mid-build). Env-tunable
# per run: FABRIK_BUILD_TIMEOUT=1200 fabrik apply … ; default unchanged for light images.
_BUILD_TIMEOUT = int(os.getenv("FABRIK_BUILD_TIMEOUT", "300"))


def _health_disabled(spec: Any) -> bool:
    """True when the spec sets ``health.disabled: true`` (no compose HEALTHCHECK is emitted)."""
    h = spec.get("health") if isinstance(spec, dict) else None
    return bool(isinstance(h, dict) and h.get("disabled"))


def _compose_up(name: str, health_disabled: bool, ssh_fn: Callable[..., str]) -> None:
    """Bring the compose stack up, waiting for readiness the RIGHT way for the service.

    Healthchecked services use ``up -d --wait`` (unchanged). But ``--wait`` REQUIRES a
    healthcheck — a ``health.disabled`` container (a FROM-scratch image can't run an in-container
    probe) makes ``--wait`` exit rc=1 ("no healthcheck configured"), false-failing the deploy even
    when the container is fine (live S3 halt, Zitadel 2026-08-28). For those, ``up -d`` (no --wait)
    then an external readiness poll: the container must reach AND HOLD a running state; a crash-loop
    (exited / restarting / RestartCount climbing) exhausts the polls and raises — a broken container
    is never mistaken for a success.
    """
    if not health_disabled:
        ssh_fn(f"cd /opt/{name} && sudo docker compose up -d --wait", timeout=120)
        return
    ssh_fn(f"cd /opt/{name} && sudo docker compose up -d", timeout=120)
    prev_restarts: str | None = None
    stable = 0
    status = restarts = ""
    for _ in range(_HEALTH_POLLS):
        time.sleep(_HEALTH_POLL_INTERVAL)
        out = ssh_fn(
            f"sudo docker inspect -f '{{{{.State.Status}}}} {{{{.RestartCount}}}}' {name}",
            timeout=15,
        ).strip()
        status, _, restarts = out.partition(" ")
        if status == "running" and restarts == prev_restarts:
            stable += 1
            if stable >= _HEALTH_STABLE_REQUIRED:
                return
        else:
            stable = 0
        prev_restarts = restarts if status == "running" else None
    raise DeployError(
        f"{name}: container did not reach a STABLE running state after 'up -d' "
        f"(health.disabled — no healthcheck to --wait on); last inspect: '{status} {restarts}'. "
        "Likely a crash-loop — check `sudo docker logs " + name + "`."
    )


def _extract_git_host(repository: str) -> str | None:
    """Extract hostname from a git URL — `git@host:path` or `https://host/path`."""
    import re

    if not repository:
        return None
    m = re.match(r"^[^@]+@([^:]+):", repository)
    if m:
        return m.group(1)
    m = re.match(r"^https?://([^/]+)/", repository)
    if m:
        return m.group(1)
    return None


def _validate_name(name: str) -> None:
    """Raise ``DeployError`` if *name* is not a valid compose app name."""
    if not _NAME_RE.match(name):
        raise DeployError(f"Invalid app name: {name!r} — must match ^[a-z0-9][a-z0-9-]{{0,62}}$")


@contextlib.contextmanager
def _target_vps_env(ctx: DeploymentContext):
    """Swap ``FABRIK_VPS_SSH_HOST`` to ``ctx.target_vps`` for the block.

    The SSH driver reads ``FABRIK_VPS_SSH_HOST`` per call, so wrapping just
    the calls that target the app's location (``SSHDeployer.deploy`` and
    ``inject_env``) is enough to route them to the spoke. Hub-side
    registrars (gatus on vps1, postgres-main on vps1, authelia on vps1)
    outside this scope continue to talk to vps1 as intended.

    ``vps1`` is treated as a no-op so the env stays unchanged for
    hub-targeted deploys.
    """
    target = getattr(ctx, "target_vps", None) or "vps1"
    if target == "vps1":
        yield
        return
    prev = os.environ.get("FABRIK_VPS_SSH_HOST")
    os.environ["FABRIK_VPS_SSH_HOST"] = target
    logger.info("Routing SSH to %s for app-targeted op", target)
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("FABRIK_VPS_SSH_HOST", None)
        else:
            os.environ["FABRIK_VPS_SSH_HOST"] = prev


class SSHDeployer:
    """Deploy services via SSH + Docker Compose.

    Replaces ``ServiceDeployer`` (Coolify API).  Same interface contract:
    ``deploy()`` returns an app identifier, ``find_existing()`` checks VPS
    state.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def deploy(self, ctx: DeploymentContext) -> str:
        """Deploy or update a service on the VPS.

        Dispatches by ``source.type`` from the spec. Returns the app name
        (stored in ``ctx.app_name`` for backward compat).

        Env-swap (W-Multi M4): when ``ctx.target_vps != "vps1"``, swap
        ``FABRIK_VPS_SSH_HOST`` so the SSH driver routes app writes
        (compose.yaml, .env, ``docker compose up``) to the spoke. Restored
        in ``finally`` so the surrounding pipeline's hub-side registrars
        (gatus, postgres, authelia on vps1) keep talking to vps1.
        """
        with _target_vps_env(ctx):
            return self._deploy_inner(ctx)

    def _deploy_inner(self, ctx: DeploymentContext) -> str:
        """Actual deploy logic (env-swap wrapped by :meth:`deploy`)."""
        name = ctx.spec["name"]
        _validate_name(name)

        if ctx.dry_run:
            logger.info("[DRY RUN] Would deploy %s on %s", name, getattr(ctx, "target_vps", "vps1"))
            return "dry-run-uuid"

        source = ctx.spec.get("source", {})
        if isinstance(source, dict):
            source_type_str = source.get("type", "template")
        else:
            source_type_str = getattr(source, "type", "template")
            if isinstance(source_type_str, SourceType):
                source_type_str = source_type_str.value

        type_map = {
            "template": SourceType.TEMPLATE,
            "git": SourceType.GIT,
            "docker": SourceType.DOCKER,
            "local": SourceType.LOCAL,
        }
        source_type = type_map.get(source_type_str)
        if source_type is None:
            raise DeployError(
                f"Unknown source type: {source_type_str!r} — "
                "expected one of: template, git, docker, local"
            )

        # Check for existing deployment
        existing = self.find_existing(name)

        if source_type == SourceType.TEMPLATE:
            self._deploy_template(ctx, name, existing)
        elif source_type == SourceType.GIT:
            self._deploy_git(ctx, name, source, existing)
        elif source_type == SourceType.DOCKER:
            self._deploy_docker(ctx, name, source, existing)
        elif source_type == SourceType.LOCAL:
            self._deploy_local(ctx, name, source, existing)

        # Track newly created resource (not updates)
        if not existing:
            ctx.add_resource(
                "compose",
                name,
                name=name,
                target_vps=getattr(ctx, "target_vps", None) or "vps1",
            )

        ctx.app_name = name
        return name

    def find_existing(self, name: str) -> dict[str, Any] | None:
        """Check whether an app directory with a compose file exists on the VPS."""
        from fabrik.drivers.ssh import ssh as _ssh

        _validate_name(name)
        try:
            result = _ssh(f"test -f /opt/{name}/compose.yaml && echo exists", timeout=10)
        except RuntimeError:
            return None
        if "exists" in result:
            try:
                status = _ssh(
                    f"cd /opt/{name} && sudo docker compose ps --format json",
                    timeout=15,
                )
            except RuntimeError:
                status = ""
            return {"name": name, "status": status, "path": f"/opt/{name}"}
        return None

    def delete(self, name: str, dry_run: bool = False) -> bool:
        """Stop containers, remove volumes, and delete the app directory."""
        from fabrik.drivers.ssh import ssh as _ssh

        _validate_name(name)
        if dry_run:
            logger.info("[DRY RUN] Would delete %s", name)
            return True

        _ssh(f"cd /opt/{name} && sudo docker compose down -v", timeout=60)
        _ssh(f"sudo rm -rf /opt/{name}", timeout=30)
        _ssh("sudo docker image prune -f", timeout=30)
        logger.info("Deleted compose app %s", name)
        return True

    def inject_env(self, ctx: DeploymentContext, env_vars: dict[str, str]) -> None:
        """Merge *env_vars* into the app's ``.env`` and restart.

        Used by registrars (GlitchTip, Redis) to inject DSNs / URLs after
        the initial deploy.

        W14 (2026-06-02): env-swap to ``ctx.target_vps`` for the duration of
        this call, matching ``deploy()``'s scope. Without it, spoke apps
        get their DSN/URL injection misdirected to vps1 where /opt/<app>/
        doesn't exist — the deploy succeeds but the orchestrator marks the
        whole pipeline rolled-back.
        """
        from fabrik.drivers.ssh import ssh as _ssh

        name = ctx.app_name
        if not name:
            raise DeployError("inject_env called but ctx.app_name is not set")
        _validate_name(name)

        if ctx.dry_run:
            logger.info("[DRY RUN] Would inject %d env vars into %s", len(env_vars), name)
            return

        with _target_vps_env(ctx):
            # Read existing .env (may not exist yet)
            try:
                existing_content = _ssh(
                    f"sudo cat /opt/{name}/.env 2>/dev/null || echo ''", timeout=10
                )
            except RuntimeError:
                existing_content = ""

            merged = _parse_env(existing_content)
            merged.update(env_vars)
            env_content = _format_env(merged)

            _write_file_to_vps(name, ".env", env_content)
            _compose_up(name, _health_disabled(ctx.spec), _ssh)
            logger.info("Injected %d env vars into %s and restarted", len(env_vars), name)

    def restart(self, name: str, dry_run: bool = False) -> None:
        """Restart the compose stack (recreates changed containers)."""
        from fabrik.drivers.ssh import ssh as _ssh

        _validate_name(name)
        if dry_run:
            logger.info("[DRY RUN] Would restart %s", name)
            return
        _ssh(f"cd /opt/{name} && sudo docker compose up -d --wait", timeout=120)

    def redeploy(
        self,
        name: str,
        source_type: str = "template",
        force: bool = False,
        dry_run: bool = False,
    ) -> None:
        """Redeploy an existing app (pull/rebuild/restart)."""
        from fabrik.drivers.ssh import ssh as _ssh

        _validate_name(name)
        if dry_run:
            logger.info(
                "[DRY RUN] Would redeploy %s (source=%s, force=%s)", name, source_type, force
            )
            return

        if source_type == "git":
            # Capture the current commit as a rollback point BEFORE mutating,
            # so a failed health check (up -d --wait exits non-zero) can be
            # reverted to the last-known-good code instead of leaving an
            # unhealthy container live. Mirrors apply()'s fail-loud + rollback
            # contract, which redeploy previously lacked.
            old_sha = _ssh(f"cd /opt/{name} && sudo git rev-parse HEAD", timeout=30).strip()
            _ssh(f"cd /opt/{name} && sudo git pull", timeout=60)
            build_flags = " --no-cache" if force else ""
            _ssh(
                f"cd /opt/{name} && sudo docker compose build{build_flags}", timeout=_BUILD_TIMEOUT
            )
            try:
                _ssh(f"cd /opt/{name} && sudo docker compose up -d --wait", timeout=120)
            except (RuntimeError, subprocess.TimeoutExpired) as err:
                logger.error(
                    "Redeploy of %s failed health check; rolling back to %s",
                    name,
                    old_sha[:12] or "<unknown>",
                )
                if old_sha:
                    try:
                        _ssh(
                            f"cd /opt/{name} && sudo git reset --hard {old_sha}",
                            timeout=60,
                        )
                        _ssh(
                            f"cd /opt/{name} && sudo docker compose build{build_flags}",
                            timeout=_BUILD_TIMEOUT,
                        )
                        _ssh(
                            f"cd /opt/{name} && sudo docker compose up -d --wait",
                            timeout=120,
                        )
                        logger.info("Rollback of %s to %s succeeded", name, old_sha[:12])
                    except (RuntimeError, subprocess.TimeoutExpired) as rb_err:
                        raise DeployError(
                            f"Redeploy of {name!r} failed AND rollback to "
                            f"{old_sha[:12]} also failed — service may be down. "
                            f"Manual intervention required. "
                            f"Deploy error: {err}; Rollback error: {rb_err}"
                        ) from err
                raise DeployError(
                    f"Redeploy of {name!r} failed health check; rolled back to "
                    f"previous commit {old_sha[:12]}. New code is NOT live. "
                    f"Original error: {err}"
                ) from err
        else:
            # Non-git (template/local): no previous image tag to revert to,
            # so there is no recoverable rollback point. Fail loudly rather
            # than fabricate one — the operator must re-run apply/redeploy or
            # restore from a known-good spec.
            recreate_flags = " --force-recreate" if force else ""
            try:
                _ssh(
                    f"cd /opt/{name} && sudo docker compose up -d --wait{recreate_flags}",
                    timeout=120,
                )
            except (RuntimeError, subprocess.TimeoutExpired) as err:
                raise DeployError(
                    f"Redeploy of {name!r} failed health check. No automatic "
                    f"rollback is possible for non-git sources (no prior image "
                    f"tag). The container may be unhealthy — check "
                    f"`docker compose ps` on the VPS. Original error: {err}"
                ) from err

        logger.info("Redeployed %s (source=%s, force=%s)", name, source_type, force)

    # ------------------------------------------------------------------
    # Source-type dispatch (private)
    # ------------------------------------------------------------------

    def _deploy_template(
        self,
        ctx: DeploymentContext,
        name: str,
        existing: dict[str, Any] | None,
    ) -> None:
        """Deploy from a Fabrik template — render compose, SCP to VPS, up."""
        from fabrik.drivers.ssh import ssh as _ssh
        from fabrik.spec_loader import Spec
        from fabrik.template_renderer import TemplateRenderer

        spec = ctx.spec

        # Build Spec object from dict (same pattern as old deployer lines 492-514)
        spec_dict = dict(spec)
        spec_dict["id"] = spec.get("id", spec["name"])
        spec_dict.pop("name", None)

        if not isinstance(spec_dict.get("env"), dict):
            spec_dict["env"] = {}

        if "source" in spec_dict and isinstance(spec_dict["source"], dict):
            source_dict = spec_dict["source"]
            if "type" in source_dict and isinstance(source_dict["type"], str):
                _type_map = {
                    "docker": SourceType.DOCKER,
                    "git": SourceType.GIT,
                    "template": SourceType.TEMPLATE,
                    "local": SourceType.LOCAL,
                }
                source_dict["type"] = _type_map.get(source_dict["type"], SourceType.TEMPLATE)
            spec_dict["source"] = Source(**source_dict)

        spec_obj = Spec(**spec_dict)

        # Always dry_run=True for render — we need content strings, not file paths
        rendered = TemplateRenderer().render(spec_obj, secrets=ctx.secrets, dry_run=True)
        compose_content = rendered["compose.yaml"]

        # Validate compose against rule-pack constraints
        errors = _validate_compose(compose_content)
        if errors:
            raise DeployError(
                f"Compose validation failed for {name}:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        _assert_claude_cli_mounts(compose_content, ctx.spec)

        # Build .env from spec env + secrets (read-merge to preserve registrar-injected vars)
        env_content = self._build_env_content(ctx, name, existing)

        # Write files to VPS
        _ssh(f"sudo mkdir -p /opt/{name}", timeout=10)
        _write_file_to_vps(name, "compose.yaml", compose_content)
        _write_file_to_vps(name, ".env", env_content)

        # Write additional rendered files (Dockerfile, etc.)
        for filename, content in rendered.items():
            if filename in ("compose.yaml", ".env.example"):
                continue
            _write_file_to_vps(name, filename, content)

        _ssh(f"cd /opt/{name} && sudo docker compose up -d --wait", timeout=120)

        # Verify container started
        try:
            ps_output = _ssh(f"cd /opt/{name} && sudo docker compose ps --format json", timeout=15)
            logger.info(
                "Container status for %s: %s", name, ps_output[:200] if ps_output else "(empty)"
            )
        except RuntimeError as e:
            logger.warning("Could not verify container status for %s: %s", name, e)

    def _deploy_git(
        self,
        ctx: DeploymentContext,
        name: str,
        source: dict[str, Any] | Source,
        existing: dict[str, Any] | None,
    ) -> None:
        """Deploy from a git repository — clone/pull, build, up."""
        from fabrik.drivers.ssh import ssh as _ssh

        if isinstance(source, dict):
            repository = source.get("repository")
            branch = source.get("branch", "main")
        else:
            repository = source.repository
            branch = source.branch

        if not repository:
            raise DeployError("Git-sourced deployment requires 'source.repository' in spec")

        # Check if already cloned
        try:
            _ssh(f"test -d /opt/{name}/.git && echo exists", timeout=10)
            is_cloned = True
        except RuntimeError:
            is_cloned = False

        # Ensure the git host is trusted by root's SSH (git clone/pull runs as root).
        # Extracts the host from either SSH form (git@host:path) or HTTPS (https://host/...).
        git_host = _extract_git_host(repository)
        if git_host:
            _ssh(
                f"sudo bash -c 'mkdir -p /root/.ssh && chmod 700 /root/.ssh && "
                f"touch /root/.ssh/known_hosts && chmod 644 /root/.ssh/known_hosts && "
                f'grep -q "^{git_host} " /root/.ssh/known_hosts || '
                f"ssh-keyscan -t ed25519,rsa {git_host} 2>/dev/null >> /root/.ssh/known_hosts'",
                timeout=30,
            )

        if is_cloned:
            _ssh(f"cd /opt/{name} && sudo git pull", timeout=60)
        else:
            _ssh(f"sudo git clone -b {branch} {repository} /opt/{name}", timeout=120)

        # D1: validate the git-sourced compose against the Fabrik invariants BEFORE build/up.
        # Git-sourced is the STANDARD project deploy path, so the memory-limit / no-host-ports /
        # network invariants must be enforced here too — not only on the template/docker paths
        # (whose call sites are :373 / :481). The compose lives in the cloned repo on the VPS, so
        # read it back and validate; abort on any violation (matches _deploy_template's behaviour).
        compose_content = _read_compose_from_vps(name)
        errors = _validate_compose(compose_content)
        if errors:
            raise DeployError(
                f"Compose validation failed for {name}:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        _assert_claude_cli_mounts(compose_content, ctx.spec)

        # Write .env (read-merge to preserve registrar-injected vars)
        env_content = self._build_env_content(ctx, name, existing)
        _write_file_to_vps(name, ".env", env_content)

        _ssh(f"cd /opt/{name} && sudo docker compose build", timeout=_BUILD_TIMEOUT)
        _ssh(f"cd /opt/{name} && sudo docker compose up -d --wait", timeout=120)

    def _deploy_docker(
        self,
        ctx: DeploymentContext,
        name: str,
        source: dict[str, Any] | Source,
        existing: dict[str, Any] | None,
    ) -> None:
        """Deploy from a Docker image — generate minimal compose, up."""
        from fabrik.drivers.ssh import ssh as _ssh

        if isinstance(source, dict):
            image = source.get("image")
            image_port = source.get("image_port", 8080)
        else:
            image = source.image
            image_port = source.image_port or 8080

        if not image:
            raise DeployError("Docker-sourced deployment requires 'source.image' in spec")

        spec = ctx.spec
        domain = spec.get("domain", "")

        # Generate minimal compose.yaml
        compose_content = _generate_docker_compose(name, image, image_port, domain, spec)

        errors = _validate_compose(compose_content)
        if errors:
            raise DeployError(
                f"Compose validation failed for {name}:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        _assert_claude_cli_mounts(compose_content, ctx.spec)

        env_content = self._build_env_content(ctx, name, existing)

        _ssh(f"sudo mkdir -p /opt/{name}", timeout=10)
        _write_file_to_vps(name, "compose.yaml", compose_content)
        _write_file_to_vps(name, ".env", env_content)
        _compose_up(name, _health_disabled(spec), _ssh)

    def _deploy_local(
        self,
        ctx: DeploymentContext,
        name: str,
        source: dict[str, Any] | Source,
        existing: dict[str, Any] | None,
    ) -> None:
        """Deploy a local compose directory — just write .env and up."""
        from fabrik.drivers.ssh import ssh as _ssh

        if isinstance(source, dict):
            path = source.get("path") or f"/opt/{name}"
        else:
            path = source.path or f"/opt/{name}"

        # Verify compose exists at the path
        try:
            _ssh(f"test -f {path}/compose.yaml && echo exists", timeout=10)
        except RuntimeError:
            raise DeployError(
                f"Local source for {name}: no compose.yaml found at {path}/compose.yaml"
            )

        # shape.uses_claude_cli → the project compose must mount the host's rotated ~/.claude
        # (guard the extra read behind the flag — the common case does no extra SSH round-trip)
        if (ctx.spec.get("shape") or {}).get("uses_claude_cli"):
            _assert_claude_cli_mounts(_ssh(f"sudo cat {path}/compose.yaml", timeout=10), ctx.spec)

        # Write/merge .env
        env_content = self._build_env_content(ctx, name, existing, app_path=path)
        _write_file_to_vps_path(path, ".env", env_content)
        _ssh(f"cd {path} && sudo docker compose up -d --wait", timeout=120)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_env_content(
        self,
        ctx: DeploymentContext,
        name: str,
        existing: dict[str, Any] | None,
        app_path: str | None = None,
    ) -> str:
        """Build .env content by merging spec env + secrets over existing vars.

        Read-merge strategy: reads existing .env on VPS first (if any) to
        preserve registrar-injected vars (SENTRY_DSN, REDIS_URL, etc.) that
        were added after the initial deploy.
        """
        from fabrik.drivers.ssh import ssh as _ssh

        path = app_path or f"/opt/{name}"
        merged: dict[str, str] = {}

        # Read existing .env if this is an update
        if existing:
            try:
                existing_content = _ssh(f"sudo cat {path}/.env 2>/dev/null || echo ''", timeout=10)
                merged = _parse_env(existing_content)
            except RuntimeError:
                pass

        # Layer spec env vars — but NEVER clobber a real, already-present value
        # with a spec PLACEHOLDER. Registrar-managed vars (DATABASE_URL,
        # REDIS_URL, …) live in the spec as literal `…placeholder…` strings and
        # are filled in post-deploy by the infra registrars via inject_env().
        # On a re-apply, `merged` already holds the injected real value; letting
        # the spec placeholder overwrite it breaks `docker compose up --wait`
        # (the app can't reach its DB on the placeholder DSN) BEFORE the
        # registrar re-injects — a self-inflicted outage (site-provisioner,
        # 2026-08-02). First deploys are unaffected: there is no real value to
        # preserve, so the placeholder applies and the registrar fills it later.
        for key, value in ctx.spec.get("env", {}).items():
            value = str(value)
            existing_val = merged.get(key)
            if _is_placeholder(value) and existing_val and not _is_placeholder(existing_val):
                continue  # keep the registrar-injected real value
            merged[key] = value

        # Layer secrets (highest precedence)
        for key, value in ctx.secrets.items():
            merged[key] = str(value)

        return _format_env(merged)


# ======================================================================
# Module-level helpers
# ======================================================================


VPS_CLAUDE_HOME = os.environ.get("FABRIK_VPS_CLAUDE_HOME", "/home/ozgur/.claude")


def claude_cli_mount_lines(container_home: str) -> list[str]:
    """The two read-only bind mounts that give a container `claude -p` on the host's
    ROTATED OAuth. The fleet rotation swaps ``~/.claude/.credentials.json`` in place
    (``scripts/sysadmin/claude_rotate.py``), so a read-only mount follows the active
    account automatically — never a static ``CLAUDE_CODE_OAUTH_TOKEN``. Mirrors the
    watchdog sidecar (``drivers/watchdog.py``). ``container_home`` = the in-container
    ``$HOME`` whose ``~/.claude`` the CLI resolves (spec ``shape.claude_cli_home``)."""
    home = container_home.rstrip("/") or "/root"
    return [
        f"{VPS_CLAUDE_HOME}:{home}/.claude:ro",
        f"{VPS_CLAUDE_HOME}.json:{home}/.claude.json:ro",
    ]


def _assert_claude_cli_mounts(compose_content: str, spec: dict) -> None:
    """When ``shape.uses_claude_cli`` is set, the deployed compose MUST mount the host's
    rotated ``~/.claude`` (read-only) into the service, or ``claude -p`` has no auth in
    the container. We VALIDATE (not inject): a git/local project owns its compose, so
    injecting would re-drift it on the next pull (the coolify-network incident). No-op
    when the flag is off; raises ``DeployError`` with the exact snippet when missing."""
    shape = spec.get("shape") or {}
    if not shape.get("uses_claude_cli"):
        return
    home = (shape.get("claude_cli_home") or "/root").rstrip("/") or "/root"
    # BOTH mounts are required: `claude -p` reads creds from ~/.claude/ AND its session config
    # from ~/.claude.json — the watchdog learned (drivers/watchdog.py:818) that a missing
    # .claude.json makes `claude -p` exit "Claude configuration file not found". Checking only
    # the first mount would pass a compose that dies at runtime — the failure we exist to prevent.
    targets = (f"{home}/.claude:ro", f"{home}/.claude.json:ro")
    if all(t in compose_content for t in targets):
        return
    snippet = "\n".join(f"      - {m}" for m in claude_cli_mount_lines(home))
    raise DeployError(
        "shape.uses_claude_cli is set but the compose does not mount BOTH of the host's rotated "
        "~/.claude and ~/.claude.json (read-only) into the container (claude -p would have no auth "
        f"/ no config). Add to the service's volumes:\n{snippet}\nDo NOT use a static "
        "CLAUDE_CODE_OAUTH_TOKEN — it pins one account and ignores the fleet rotation."
    )


def _is_placeholder(value: str) -> bool:
    """True if *value* is a spec stand-in for a registrar-injected real value.

    Fabrik specs carry registrar-managed vars (DATABASE_URL, REDIS_URL, …) as
    literal ``…placeholder…`` strings; the infra registrars overwrite them
    post-deploy via ``inject_env()``. ``_build_env_content`` uses this to avoid
    letting such a placeholder clobber an already-injected real value on a
    re-apply (which would break ``docker compose up --wait``).
    """
    return "placeholder" in value.lower()


def _parse_env(content: str) -> dict[str, str]:
    """Parse a .env file into a dict, ignoring comments and blank lines."""
    result: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        # Strip surrounding quotes — and UNESCAPE a double-quoted value, mirroring
        # `_format_env`'s escaping. Without the unescape the round-trip corrupts:
        # write escapes `\"` -> read strips the wrapper but leaves the backslashes ->
        # the next write escapes them AGAIN, so a value grows a backslash per apply.
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            quote = value[0]
            value = value[1:-1]
            if quote == '"':
                value = value.replace('\\"', '"').replace("\\\\", "\\")
        result[key] = value
    return result


def _format_env(env: dict[str, str]) -> str:
    """Format a dict as .env file content."""
    lines = []
    for key, value in sorted(env.items()):
        # Quote values with spaces or special chars — and ESCAPE when we do.
        #
        # The escape is the fix (2026-08-31). The old code wrapped without it:
        # `value = f'"{value}"'`. A JSON secret contains `"`, so it shipped as
        # `K="{"a":"b"}"` and Compose read the first inner quote as a NEW VARIABLE
        # NAME — `failed to read .env: unexpected character '"' in variable name` —
        # breaking `docker compose build` for EVERY value carrying a quote on the
        # fleet. Measured live on tryton-crm's CONSUMER_TOKENS: two byte-identical
        # apply failures.
        #
        # The QUOTE TRIGGER is deliberately unchanged. Dropping it for spaces (a
        # compose env_file reads to end-of-line, so `K=a b` parses) broke
        # `TestFormatEnv::test_quotes_spaces`, which encodes a real contract: the
        # file must stay safe for a shell `source`, where a bare `K=a b` word-splits.
        # Verified live that Compose unescapes correctly: `K="{\"a\":\"b\"}"`
        # resolves to `{"a":"b"}`. `_parse_env` carries the matching unescape.
        if any(c in value for c in (" ", "#", "'", '"', "\n")):
            value = '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n" if lines else ""


def _write_file_to_vps(name: str, filename: str, content: str) -> None:
    """Write a file to ``/opt/{name}/{filename}`` via scp-to-tmp-then-sudo-mv."""
    _write_file_to_vps_path(f"/opt/{name}", filename, content)


def _write_file_to_vps_path(path: str, filename: str, content: str) -> None:
    """Write a file to ``{path}/{filename}`` via scp-to-tmp-then-sudo-mv."""
    from fabrik.drivers.ssh import scp_to_vps
    from fabrik.drivers.ssh import ssh as _ssh

    safe_name = filename.replace("/", "-")
    tmp_remote = f"/tmp/fabrik-{os.getpid()}-{safe_name}"  # nosec B108

    fd, tmp_local = tempfile.mkstemp(prefix=f"fabrik-{safe_name}-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        scp_to_vps(tmp_local, tmp_remote, timeout=30)
    finally:
        try:
            os.unlink(tmp_local)
        except OSError:
            pass

    try:
        _ssh(
            f"sudo mv {tmp_remote} {path}/{filename} && sudo chown root:root {path}/{filename}",
            timeout=10,
        )
    except Exception:
        # Clean up remote temp file so nothing lingers on VPS
        try:
            _ssh(f"rm -f {tmp_remote}", timeout=5)
        except Exception:  # noqa: BLE001, S110
            pass
        raise


def _validate_compose(content: str) -> list[str]:
    """Validate rendered compose YAML against rule-pack constraints.

    Returns a list of error messages (empty = valid).
    Per Lesson 32: explicit key presence checks, not ``.get(key, default)``.
    """
    import yaml as _yaml

    try:
        data = _yaml.safe_load(content)
    except _yaml.YAMLError as e:
        return [f"Invalid YAML: {e}"]

    if not isinstance(data, dict):
        return ["Compose file is not a YAML mapping"]

    errors: list[str] = []
    services = data.get("services", {})
    if not services:
        errors.append("No services defined")
        return errors

    for svc_name, svc_config in services.items():
        if not isinstance(svc_config, dict):
            errors.append(f"Service '{svc_name}': not a mapping")
            continue

        # platform: linux/amd64
        if "platform" not in svc_config:
            errors.append(f"Service '{svc_name}': missing 'platform: linux/amd64'")
        elif svc_config["platform"] != "linux/amd64":
            errors.append(
                f"Service '{svc_name}': platform must be 'linux/amd64', "
                f"got '{svc_config['platform']}'"
            )

        # deploy.resources.limits.memory
        deploy = svc_config.get("deploy", {})
        resources = deploy.get("resources", {}) if isinstance(deploy, dict) else {}
        limits = resources.get("limits", {}) if isinstance(resources, dict) else {}
        if "memory" not in limits:
            errors.append(f"Service '{svc_name}': missing 'deploy.resources.limits.memory'")

        # No ports: section
        if "ports" in svc_config:
            errors.append(f"Service '{svc_name}': 'ports' section forbidden — use Traefik routing")

        # restart: unless-stopped
        if "restart" not in svc_config:
            errors.append(f"Service '{svc_name}': missing 'restart: unless-stopped'")

        # container_name required (Lesson 22)
        if "container_name" not in svc_config:
            errors.append(
                f"Service '{svc_name}': missing 'container_name' (required for stable naming)"
            )

        # Traefik label checks
        labels = svc_config.get("labels", {})
        if isinstance(labels, list):
            label_str = " ".join(labels)
        elif isinstance(labels, dict):
            label_str = " ".join(f"{k}={v}" for k, v in labels.items())
        else:
            label_str = ""

        if "traefik.enable=true" in label_str or "traefik.enable: true" in label_str:
            if "websecure" not in label_str:
                errors.append(
                    f"Service '{svc_name}': Traefik entrypoint must be 'websecure' (not http/https)"
                )
            if "loadbalancer.server.port" not in label_str:
                errors.append(f"Service '{svc_name}': missing 'loadbalancer.server.port' label")

        # No depends_on referencing shared infra
        depends_on = svc_config.get("depends_on", {})
        if isinstance(depends_on, dict):
            dep_names = list(depends_on.keys())
        elif isinstance(depends_on, list):
            dep_names = depends_on
        else:
            dep_names = []
        for dep in dep_names:
            if dep in ("postgres-main", "redis-main"):
                errors.append(
                    f"Service '{svc_name}': depends_on '{dep}' forbidden — "
                    "use Docker DNS on the fabrik network instead"
                )

        # No localhost in DATABASE_URL / REDIS_URL
        env = svc_config.get("environment", {})
        if isinstance(env, dict):
            for env_key in ("DATABASE_URL", "REDIS_URL"):
                val = env.get(env_key, "")
                if isinstance(val, str) and "localhost" in val:
                    errors.append(
                        f"Service '{svc_name}': {env_key} contains 'localhost' — "
                        "use Docker DNS (postgres-main:5432 / redis-main:6379)"
                    )

    # Network: fabrik external (renamed from `coolify` 2026-05-31; W12 of fleet-hardening plan).
    networks = data.get("networks", {})
    # D1 (deliberate decision — fail-closed): a compose with NO top-level `networks:` block is
    # rejected. Every deployed service must join the external `fabrik` network — a container off it
    # can't be routed by Traefik and can't reach shared infra (postgres-main / redis-main). Previously
    # a missing block passed silently ("some inherit"), which is not true for an external network.
    if not networks:
        errors.append(
            "Missing top-level 'networks:' block — declare `networks: { fabrik: { external: true } }` "
            "and attach each service to it. A service off the fabrik network is unroutable by Traefik "
            "and cannot reach shared infra."
        )
    if "fabrik" in networks:
        fabrik_net = networks["fabrik"]
        if isinstance(fabrik_net, dict) and not fabrik_net.get("external"):
            errors.append("Network 'fabrik' must be declared as external: true")
    # Legacy `coolify` network = unmigrated spec; reject loudly so the operator
    # knows to rename before retrying (otherwise docker compose up fails with
    # "network coolify declared as external, but could not be found").
    if "coolify" in networks:
        errors.append(
            "Network 'coolify' is deprecated — rename to 'fabrik' in your compose.yaml "
            "(both the service's `networks:` list and the top-level `networks:` block). "
            "The fabrik external network was renamed on 2026-05-31."
        )

    return errors


def _read_compose_from_vps(name: str) -> str:
    """Read the deployed compose file back from ``/opt/<name>`` on the VPS (D1).

    Git-sourced deploys clone the compose onto the VPS rather than rendering it locally, so
    validation must fetch it. Tries the four Compose-recognised filenames; raises if none exist.
    """
    from fabrik.drivers.ssh import ssh as _ssh

    for filename in ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"):
        try:
            out = _ssh(f"cat /opt/{name}/{filename} 2>/dev/null", timeout=15)
        except RuntimeError:
            continue
        if out and out.strip():
            return out
    raise DeployError(
        f"No compose file found in /opt/{name} "
        "(looked for compose.yaml, compose.yml, docker-compose.yml, docker-compose.yaml)"
    )


def _generate_docker_compose(
    name: str,
    image: str,
    port: int,
    domain: str,
    spec: dict[str, Any],
) -> str:
    """Generate a minimal compose.yaml for a Docker image source."""
    resources = spec.get("resources", {})
    memory = resources.get("memory", "256M") if isinstance(resources, dict) else "256M"

    # Health: read from spec (W12.b 2026-06-02 — was hardcoded /health + curl).
    # `curl` is not in nginx:alpine or many other small images; use a wget/Python
    # 2-step that handles whichever exists. `wget -q --spider` returns 0 on 2xx,
    # nonzero otherwise — works in alpine, debian, ubuntu, distroless-busybox.
    health = spec.get("health", {}) if isinstance(spec.get("health"), dict) else {}
    health_path = health.get("path", "/health")
    health_interval = health.get("interval", "30s")
    source = spec.get("source", {}) if isinstance(spec.get("source"), dict) else {}
    image_command = source.get("image_command")

    lines = [
        "services:",
        f"  {name}:",
        f"    image: {image}",
        f"    container_name: {name}",
        "    platform: linux/amd64",
        "    restart: unless-stopped",
        "    env_file: .env",
    ]
    # Custom container command override (e.g. Zitadel's `start-from-init … --tlsMode external`). Without this
    # the container runs the image's DEFAULT CMD and the whole directive is silently lost. Docker Compose
    # interpolates ${VAR} in `command:` from env_file at `up` time (verified on compose 2.40.3), so a
    # secrets-minted ${ZITADEL_MASTERKEY} expands here exactly as it does in the env.
    if image_command:
        # Single-quoted YAML scalar (escape embedded single-quotes by doubling) — keeps a colon, `#`, or
        # other YAML-special char in the command from breaking the compose, and matches Zitadel's own official
        # docker-compose form. Compose still interpolates ${VAR} from env_file (interpolation runs on the
        # parsed string value, after YAML parsing).
        _q = image_command.replace("'", "''")
        lines.append(f"    command: '{_q}'")
    lines += [
        "    deploy:",
        "      resources:",
        "        limits:",
        f"          memory: {memory}",
    ]
    # `health: { disabled: true }` → OMIT the healthcheck. The default `wget --spider` probe needs a shell +
    # wget, absent from FROM-scratch/distroless images (e.g. Zitadel) — a forced healthcheck there errors,
    # marks the container unhealthy, and `docker compose up -d --wait` times out. With no healthcheck the
    # service reports `running` (not `healthy`), `--wait` proceeds, and external Gatus does the readiness probe.
    if not health.get("disabled"):
        lines += [
            "    healthcheck:",
            f'      test: ["CMD-SHELL", "wget -q --spider http://localhost:{port}{health_path} || exit 1"]',  # noqa: localhost is correct — a container health-check probes its OWN port
            f"      interval: {health_interval}",
            "      timeout: 10s",
            "      retries: 3",
            "      start_period: 20s",
        ]
    lines += [
        "    networks:",
        "      - fabrik",
    ]

    if domain:
        lines.extend(
            [
                "    labels:",
                "      - traefik.enable=true",
                f"      - traefik.http.routers.{name}.rule=Host(`{domain}`)",
                f"      - traefik.http.routers.{name}.entrypoints=websecure",
                f"      - traefik.http.routers.{name}.tls=true",
                f"      - traefik.http.routers.{name}.tls.certresolver=letsencrypt",
                f"      - traefik.http.services.{name}.loadbalancer.server.port={port}",
                f"      - traefik.http.routers.{name}.middlewares=gzip@docker",
            ]
        )

    lines.extend(
        [
            "",
            "networks:",
            "  fabrik:",
            "    external: true",
        ]
    )

    return "\n".join(lines) + "\n"
