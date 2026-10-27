"""SSH + Docker Compose deployer — replaces Coolify API deployer.

Deploys services by rendering compose files locally, copying them to the VPS
via SCP, and running ``docker compose up -d`` over SSH.  Supports all four
source types: TEMPLATE, GIT, DOCKER, LOCAL.

Design doc: ``docs/development/plans/archived/2026-05-28-ssh-deployer.md``
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import posixpath
import re
import shlex
import subprocess
import tempfile
import time
from collections.abc import Callable
from typing import Any

from fabrik.env_file import EnvTemplate
from fabrik.env_file import format_env as _format_env
from fabrik.env_file import parse_env as _parse_env
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import DeployError, ProvisioningError
from fabrik.spec_loader import OWNER_ENV_FILE, OWNER_ENV_KEYS, Source, SourceType, Spec

logger = logging.getLogger(__name__)

# Shell-safe name pattern — prevents injection in SSH commands.
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

# A full SHA-1 commit id as `git rev-parse HEAD` prints it — the only GIT_SHA the deployer writes.
_GIT_SHA_RE = re.compile(r"[0-9a-f]{40}")

# Exactly one compose interpolation of a bare name, optionally with a `-`/`:-` default.
_INTERPOLATION_RE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*(:?-[^}]*)?\}")

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

    Healthchecked services use ``up -d --wait`` (unchanged). ``--wait`` refuses a service whose
    healthcheck is DISABLED (``healthcheck: disable: true`` → rc=1, "no healthcheck configured";
    a service with no healthcheck block at all passes — compose 2.40.3, 2026-10-06). The
    ``health.disabled`` path (a FROM-scratch image can't run an in-container probe) false-failed
    ``--wait`` live (S3 halt, Zitadel 2026-08-28), so it is not trusted to ``--wait``: ``up -d`` (no --wait)
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
    if not _NAME_RE.fullmatch(name):  # fullmatch: `$` alone admits a trailing "\n"
        raise DeployError(f"Invalid app name: {name!r} — must match ^[a-z0-9][a-z0-9-]{{0,62}}$")


@contextlib.contextmanager
def _host_env(host: str | None):
    """Swap ``FABRIK_VPS_SSH_HOST`` to *host* for the block, restoring it after.

    The SSH driver reads ``FABRIK_VPS_SSH_HOST`` per call, so wrapping just the calls that
    target an app's location routes them to that host. ``"vps1"``, ``None`` and ``""`` are a
    NO-OP: the driver's default host is the hub's ssh alias (``DEFAULT_SSH_HOST`` in
    ``drivers/ssh.py``), which the name ``vps1`` does not resolve to.
    """
    target = host or "vps1"
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


@contextlib.contextmanager
def _target_vps_env(ctx: DeploymentContext):
    """Swap ``FABRIK_VPS_SSH_HOST`` to ``ctx.target_vps`` for the block (see :func:`_host_env`).

    Wraps only the calls that target the app's location (``SSHDeployer.deploy`` and
    ``inject_env``); hub-side registrars (gatus, postgres-main, authelia on vps1) outside
    this scope keep talking to vps1. ``vps1`` is a no-op.
    """
    with _host_env(getattr(ctx, "target_vps", None)):
        yield


def app_dir(spec: dict[str, Any] | Spec) -> list[str]:
    """Return the CANDIDATE app directories for *spec*, in probe order (RAW, unquoted).

    A local source yields its single ``source.path`` normalised (no trailing slash), or
    ``/opt/<name>`` when the path is unset (as ``_deploy_local`` resolves it); a local path
    whose parent is not ``/opt`` raises :class:`ProvisioningError` before any probe. Any
    other source yields ``/opt/<n>`` then ``/opt/fabrik-<n>`` -- the second only when ``<n>``
    does not already start with ``fabrik-``. ``<n>`` is ``name or id``, and it must match the
    app-name pattern :func:`_validate_name` enforces on deploy (so ``../etc`` can never become
    ``/opt/../etc``; ``Spec.id`` is pattern-validated, ``Spec.name`` is not -- 0 of 69 specs
    set one today). Accepts the validator's dict (``source`` may be absent) and the ``Spec``
    model alike.
    """
    if isinstance(spec, dict):
        name = spec.get("name") or spec.get("id")
        source = spec.get("source") or {}
        if isinstance(source, dict):
            stype, path = source.get("type"), source.get("path")
        else:
            stype, path = source.type, source.path
    else:
        name = spec.name or spec.id
        stype, path = spec.source.type, spec.source.path
    if not name:
        raise ProvisioningError("spec has neither name nor id", resource_type="app_dir")
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ProvisioningError(f"invalid app name: {name!r}", resource_type="app_dir")
    if getattr(stype, "value", stype) == SourceType.LOCAL.value:
        resolved = posixpath.normpath(path) if path else f"/opt/{name}"
        if not resolved.startswith("/") or posixpath.dirname(resolved) != "/opt":
            raise ProvisioningError(
                f"local source path {path!r} is not a direct child of /opt",
                resource_type="app_dir",
            )
        return [resolved]
    candidates = [f"/opt/{name}"]
    if not name.startswith("fabrik-"):
        candidates.append(f"/opt/fabrik-{name}")
    return candidates


_PS_KEYS = ("Service", "State", "Health", "ExitCode")
# Everything the ssh driver's subprocess.run can raise (drivers/ssh.py:99): a failed command
# (RuntimeError), a missing ssh binary or fork failure (OSError), undecodable stdout
# (UnicodeDecodeError is a ValueError) and the timeout. probe_app RETURNS these, never raises.
_SSH_FAILURES = (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired)

# Printed by the remote shell when a compose filename does not exist (_read_compose_from_vps), so
# "absent, try the next name" is told apart from "exists but the read failed, refuse".
_NO_COMPOSE_FILE = "__FABRIK_NO_COMPOSE_FILE__"


def _parse_compose_ps(text: str) -> list[dict[str, str]]:
    """Parse ``docker compose ps --format json`` into rows of Service/State/Health/ExitCode.

    Reads JSON Lines (one object per line, Compose >= 2.21) or a leading-``[`` array (older
    Compose); every other key is ignored and every value is a string (missing -> ``""``). An
    empty body is zero rows; a body that is not JSON, or an object without a non-empty
    ``Service`` (``{}`` and ``{"Service": null}`` are not rows), raises :class:`ValueError` --
    the same rule :meth:`SSHDeployer.list_compose_projects` applies to a non-array body.
    """
    body = text.strip()
    if not body:
        return []
    if body.startswith("["):
        items = json.loads(body)
    else:
        items = [json.loads(line) for line in body.splitlines() if line.strip()]
    rows: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f"compose ps row is not an object: {item!r}")
        if not item.get("Service"):
            raise ValueError(f"compose ps row lacks a Service: {item!r}")
        rows.append({k: "" if item.get(k) is None else str(item.get(k)) for k in _PS_KEYS})
    return rows


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

        # Mint-once (W-023bdd59) — BEFORE any source path renders compose.yaml or builds .env.
        self._preserve_minted_secrets(ctx, name, source, source_type)

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

    def _preserve_minted_secrets(
        self, ctx: DeploymentContext, name: str, source: Any, source_type: SourceType
    ) -> None:
        """Swap every secret THIS run minted for the value the remote ``.env`` already holds.

        The hub never keeps a value it minted (the first apply wrote it only into the remote
        ``.env``), so without this every re-apply would render and write a NEW value — for a
        stable-forever key such as an encryption master key, the stored data becomes unreadable
        (W-023bdd59). It runs before any source path renders, because the template path bakes
        ``ctx.secrets`` into ``compose.yaml`` (``environment:`` literals beat ``.env``).

        The remote ``.env`` is read whenever anything was minted — never gated on
        :meth:`find_existing`, which answers ``None`` on an ssh failure and only looks at
        ``/opt/<name>``. ``_read_env_file`` fails closed: ``{}`` only for an absent file, any
        other failure raises :class:`DeployError` before anything is written. A key whose value
        no longer equals its minted one was set by something else this run and is left alone;
        an empty remote value counts as absent. Rotating such a secret means setting it on the hub
        (it is then not minted). Values are never logged.
        """
        minted = getattr(ctx, "minted_secrets", None) or {}
        if not minted:
            return
        from fabrik.drivers.ssh import ssh as _ssh

        if source_type == SourceType.LOCAL:
            path = (
                source.get("path") if isinstance(source, dict) else getattr(source, "path", None)
            ) or f"/opt/{name}"
        else:
            path = f"/opt/{name}"
        deployed = _read_env_file(path, _ssh)
        for key, minted_value in minted.items():
            current = ctx.secrets.get(key)
            remote = deployed.get(key)
            if current == minted_value and remote:
                ctx.secrets[key] = remote
                logger.info("Kept the deployed value of generated secret %s (mint-once)", key)

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

    def probe_app(self, path: str) -> dict[str, Any]:
        """Probe the app directory *path* read-only: ``{"exists", "ps", "error"}``.

        First the whole file test inside one ``sudo sh -c`` (rc 0 either way; a refused sudo
        prints nothing), then -- on ``exists`` -- ``docker compose ps -a`` in that directory.
        ``shlex.quote`` is applied once per shell layer. Every failure is RETURNED in
        ``error``, never raised (:data:`_SSH_FAILURES` -- a transport ``RuntimeError``, an
        ``OSError`` such as a missing ssh binary, undecodable output, the timeout): an
        exception from the first call or a stdout that is neither
        ``exists`` nor ``absent`` is a HOST failure (``exists`` False, the ``ps`` call never
        sent); an exception or a non-JSON body from the second keeps ``exists`` True.
        """
        from fabrik.drivers.ssh import ssh as _ssh

        test = "[ -f " + shlex.quote(path + "/compose.yaml") + " ] && echo exists || echo absent"
        try:
            out = _ssh("sudo sh -c " + shlex.quote(test), timeout=10)
        except _SSH_FAILURES as exc:
            return {"exists": False, "ps": "", "error": f"{type(exc).__name__}: {exc}"}
        verdict = out.strip()
        if verdict == "absent":
            return {"exists": False, "ps": "", "error": None}
        if verdict != "exists":
            return {"exists": False, "ps": "", "error": f"unexpected probe output: {out!r}"}
        try:
            ps = _ssh(
                f"cd {shlex.quote(path)} && sudo docker compose ps -a --format json", timeout=15
            )
        except _SSH_FAILURES as exc:
            return {"exists": True, "ps": "", "error": f"{type(exc).__name__}: {exc}"}
        try:
            _parse_compose_ps(ps)
        except (ValueError, RecursionError) as exc:  # a pathologically nested body is an error too
            return {"exists": True, "ps": ps, "error": f"compose ps output is not JSON: {exc}"}
        return {"exists": True, "ps": ps, "error": None}

    def list_compose_projects(self, host: str) -> list[dict[str, Any]]:
        """Return ``docker compose ls -a`` on *host* as the parsed array of projects.

        Runs under :func:`_host_env` so a spoke is reached and the env restored after. A
        transport failure propagates (``RuntimeError`` / ``TimeoutExpired``); a body that is
        not a JSON array of objects raises ``RuntimeError`` naming *host* (D3 reads ``Name``
        and ``ConfigFiles`` from every entry, so a non-object entry is a host failure, not a
        project).
        """
        from fabrik.drivers.ssh import ssh as _ssh

        with _host_env(host):
            out = _ssh("sudo docker compose ls -a --format json", timeout=60)
        try:
            projects = json.loads(out)
        except ValueError as exc:
            raise RuntimeError(f"compose ls on {host} returned non-JSON: {out[:200]!r}") from exc
        if not isinstance(projects, list):
            kind = type(projects).__name__
            raise RuntimeError(f"compose ls on {host} returned {kind}, not a JSON array")
        if not all(isinstance(p, dict) for p in projects):
            raise RuntimeError(f"compose ls on {host} returned an array with a non-object entry")
        return projects

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

    def read_env(self, ctx: DeploymentContext) -> dict[str, str]:
        """Return the app's parsed ``.env`` — it never swallows a read failure.

        Runs inside :func:`_target_vps_env` (as :meth:`inject_env` does), so a
        spoke's ``.env`` is read on the spoke. Returns ``{}`` ONLY when
        ``test -f`` reports the file absent; any ssh/read failure or an
        unrecognised probe answer raises :class:`DeployError`. Both the app-role
        cutover (reading ``DATABASE_URL``'s user) and :meth:`inject_env`'s merge
        read through here — a swallowed read in a merge writes a truncated .env.
        """
        from fabrik.drivers.ssh import ssh as _ssh

        name = ctx.app_name
        if not name:
            raise DeployError("read_env called but ctx.app_name is not set")
        _validate_name(name)

        with _target_vps_env(ctx):
            return _read_env_file(f"/opt/{name}", _ssh)

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

        # D7-registrar-O7: read through read_env, which fails CLOSED — ``{}`` only for
        # a truly absent file. The old swallowing read turned a failed ``sudo cat``
        # into an empty base and then wrote a .env holding ONLY the injected keys,
        # dropping every other secret. A read failure now raises DeployError before
        # anything is written (every caller is inside a registrar's non-fatal block).
        merged = self.read_env(ctx)
        merged.update(env_vars)

        with _target_vps_env(ctx):
            # The owner key lands in `.env.owner` FIRST, then `.env` without it, then ONE restart —
            # the registrar's one-call injection at creation keeps its invariant: the owner password
            # is on disk before anything below it can fail (plan 2026-10-12-plan-1-owner-dsn-split).
            _write_env_files(f"/opt/{name}", merged, _env_writer_for(name))
            _compose_up(name, _health_disabled(ctx.spec), _ssh)
            logger.info("Injected %d env vars into %s and restarted", len(env_vars), name)

    def restart(self, name: str, dry_run: bool = False) -> None:
        """Restart the compose stack (recreates changed containers)."""
        from fabrik.drivers.ssh import ssh as _ssh

        _validate_name(name)
        if dry_run:
            logger.info("[DRY RUN] Would restart %s", name)
            return
        _assert_deployed_compose_valid(name)
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
            # W-51d6c153: the pulled compose is checked BEFORE the GIT_SHA write, the build and
            # the up; a violation or a failed read resets the checkout to old_sha, so the running
            # containers and the code on disk stay on the last commit that passed (left on the
            # pulled commit, the next redeploy would capture it as its rollback point). When there
            # is no valid old_sha, or the reset itself fails, the pulled commit DOES stay on disk —
            # the raised error says so; the containers are untouched either way.
            try:
                _assert_deployed_compose_valid(name)
            except (DeployError, *_SSH_FAILURES) as err:
                if not _GIT_SHA_RE.fullmatch(old_sha):
                    raise DeployError(
                        f"Redeploy of {name!r} refused; no valid previous commit to reset to "
                        f"({old_sha[:40]!r}), pulled code left on disk, containers untouched: {err}"
                    ) from err
                try:
                    _ssh(f"cd /opt/{name} && sudo git reset --hard {old_sha}", timeout=60)
                except _SSH_FAILURES as rb_err:
                    raise DeployError(
                        f"Redeploy of {name!r} refused, AND the reset to {old_sha[:12]} failed — "
                        f"pulled code is on disk, containers untouched. Reason: {err}; "
                        f"reset error: {rb_err}"
                    ) from err
                logger.warning("Redeploy of %s refused; checkout reset to %s", name, old_sha[:12])
                raise DeployError(
                    f"Redeploy of {name!r} refused; checkout reset to {old_sha[:12]}, "
                    f"containers untouched. {err}"
                ) from err
            new_sha = _read_head_sha(name, _ssh)
            if new_sha:
                _persist_git_sha(name, new_sha, _ssh)
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
                        # The rebuilt container runs old_sha's code; label its events so.
                        if _GIT_SHA_RE.fullmatch(old_sha):
                            _persist_git_sha(name, old_sha, _ssh)
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
            _assert_deployed_compose_valid(name)
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

        # Always dry_run=True for render — we need content strings, not file paths. An owner
        # key among the secrets never reaches compose.yaml (the renderer puts every secret into
        # every service's `environment:`, which would hand the app the owner DSN, D-754): it
        # rides to `.env.owner` through `_build_env` and the writer instead (the Finish review, O1).
        rendered = TemplateRenderer().render(
            spec_obj,
            secrets={k: v for k, v in ctx.secrets.items() if k not in OWNER_ENV_KEYS},
            dry_run=True,
        )
        compose_content = rendered["compose.yaml"]

        # Validate compose against rule-pack constraints
        errors = _validate_compose(compose_content)
        if errors:
            raise DeployError(
                f"Compose validation failed for {name}:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        _assert_claude_cli_mounts(compose_content, ctx.spec)

        # Build .env from spec env + secrets (read-merge to preserve registrar-injected vars)
        env = self._build_env(ctx, name, existing)

        # Write files to VPS
        _ssh(f"sudo mkdir -p /opt/{name}", timeout=10)
        _write_file_to_vps(name, "compose.yaml", compose_content)
        _write_env_files(f"/opt/{name}", env, _env_writer_for(name))

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
        # The commit just checked out → GIT_SHA in .env, so a scaffolded service's GlitchTip
        # release names the code it runs.
        sha = _read_head_sha(name, _ssh)

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

        # Write .env (read-merge to preserve registrar-injected vars).
        env = self._build_env(ctx, name, existing, overrides={"GIT_SHA": sha} if sha else None)
        _write_env_files(f"/opt/{name}", env, _env_writer_for(name))

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

        env = self._build_env(ctx, name, existing)

        _ssh(f"sudo mkdir -p /opt/{name}", timeout=10)
        _write_file_to_vps(name, "compose.yaml", compose_content)
        _write_env_files(f"/opt/{name}", env, _env_writer_for(name))
        _compose_up(name, _health_disabled(spec), _ssh)

    def _deploy_local(
        self,
        ctx: DeploymentContext,
        name: str,
        source: dict[str, Any] | Source,
        existing: dict[str, Any] | None,
    ) -> None:
        """Deploy a local compose directory — validate its compose, write .env, up."""
        from fabrik.drivers.ssh import ssh as _ssh

        if isinstance(source, dict):
            path = source.get("path") or f"/opt/{name}"
        else:
            path = source.path or f"/opt/{name}"

        # source.path is spec-supplied and reaches a root shell on the VPS: every command below
        # quotes it (_shell_path), keeping a leading ~/ for the shell to expand, as the .env
        # writer does (_write_file_to_vps_path leaves a tilde app dir unquoted).
        compose_file = _shell_path(f"{path}/compose.yaml")

        # Verify compose exists at the path
        try:
            _ssh(f"test -f {compose_file} && echo exists", timeout=10)
        except RuntimeError:
            raise DeployError(
                f"Local source for {name}: no compose.yaml found at {path}/compose.yaml"
            )

        # W-807287f1: validate the compose against the Fabrik invariants BEFORE any write or up,
        # as the template, git and docker paths do — the local path was the one door around
        # them. One read serves both checks; a read that fails refuses (nothing written).
        try:
            compose_content = _ssh(f"sudo cat {compose_file}", timeout=10)
        except _SSH_FAILURES as err:
            raise DeployError(f"Local source for {name}: cannot read {path}/compose.yaml: {err}")
        errors = _validate_compose(compose_content)
        if errors:
            raise DeployError(
                f"Compose validation failed for {name}:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        # shape.uses_claude_cli → the project compose must mount the host's rotated ~/.claude
        _assert_claude_cli_mounts(compose_content, ctx.spec)

        # Write/merge .env. ``find_existing`` probes /opt/<name> only, so a source living
        # elsewhere arrives with existing=None; the compose verified above proves the app is at
        # ``path``, so its .env is always read (absent → {}) — else the merge dropped every
        # registrar-injected key, DATABASE_URL_OWNER included (W-7ec31807).
        existing = existing or {"name": name, "path": path}
        env = self._build_env(ctx, name, existing, app_path=path)
        _write_env_files(path, env, _write_file_to_vps_path)
        _ssh(f"cd {_shell_path(path)} && sudo docker compose up -d --wait", timeout=120)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_env_content(
        self,
        ctx: DeploymentContext,
        name: str,
        existing: dict[str, Any] | None,
        app_path: str | None = None,
        *,
        overrides: dict[str, str] | None = None,
    ) -> str:
        """The formatted view of :meth:`_build_env` — kept for its readers and tests; the deploy
        paths hand the DICT to :func:`_write_env_files`, never a string parsed back (the
        format→parse round trip loses a value holding a newline — Phase A's review, O2)."""
        return _format_env(self._build_env(ctx, name, existing, app_path, overrides=overrides))

    def _build_env(
        self,
        ctx: DeploymentContext,
        name: str,
        existing: dict[str, Any] | None,
        app_path: str | None = None,
        *,
        overrides: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build the merged .env mapping — spec env + secrets over existing vars.

        Read-merge strategy: reads existing .env on VPS first (if any) to
        preserve registrar-injected vars (SENTRY_DSN, REDIS_URL, etc.) that
        were added after the initial deploy.

        *overrides* are deploy-time facts (the git deploy's ``GIT_SHA``): layered AFTER the
        spec env, so a spec ``GIT_SHA: ""`` cannot blank them, and BEFORE secrets.
        """
        from fabrik.drivers.ssh import ssh as _ssh

        path = app_path or f"/opt/{name}"
        merged: dict[str, str] = {}

        # Read existing .env if this is an update. Fail CLOSED (D7 r1b, O7's class): a
        # failed read of an EXISTING .env raises DeployError and the deploy aborts before
        # anything is written — degrading to spec env + secrets rewrote .env without the
        # registrar-injected keys, DATABASE_URL_OWNER (the only owner-password copy after
        # an app-role cutover) included. An absent .env still builds from spec + secrets.
        # An existing app is never a tracked resource, so the abort's rollback leaves it.
        if existing:
            merged = _read_env_file(path, _ssh)

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
            # A spec value's `$` is a compose interpolation (`${LOG_LEVEL:-INFO}`), written bare;
            # every other value's `$` is literal and is escaped (fabrik.env_file).
            merged[key] = EnvTemplate(value) if "$" in value else value

        merged.update(overrides or {})

        # Layer secrets (highest precedence). A secret this run minted was already swapped for
        # the deployed value by _preserve_minted_secrets, before anything rendered.
        for key, value in ctx.secrets.items():
            merged[key] = str(value)

        return merged


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


def _shell_path(path: str) -> str:
    """``path`` as ONE shell word for a remote command, a leading ``~/`` (or a bare ``~``) left
    outside the quotes so the remote shell still expands it to the ssh user's home; anything else
    — ``;``, spaces, ``$`` — stays inside ``shlex.quote``. ``~user/…`` is quoted whole (literal)."""
    if path == "~":
        return "~"
    if path.startswith("~/"):
        return "~/" + shlex.quote(path[2:])
    return shlex.quote(path)


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
    post-deploy via ``inject_env()``. ``_build_env`` uses this to avoid
    letting such a placeholder clobber an already-injected real value on a
    re-apply (which would break ``docker compose up --wait``).

    A value that is exactly ONE compose interpolation of a bare name (``${SENTRY_DSN:-}``,
    ``${LOG_LEVEL:-INFO}``, ``${GIT_SHA}``) is a stand-in too: the spec generator copies such
    entries verbatim from a scaffold's compose ``environment:``, and on a re-apply writing the
    literal over the registrar's real value would blank it until the registrar re-injects.
    Cost (the MIRROR): a spec that DELIBERATELY sets such a literal no longer replaces a real
    value already in ``.env``; edit or remove the ``.env`` key to force it.
    """
    return "placeholder" in value.lower() or bool(_INTERPOLATION_RE.fullmatch(value))


# The line `_read_env_file` echoes between `.env` and `.env.owner`: no `=`, so a .env parser skips
# it, and no shell metacharacter (a leading `#` would make it a shell comment), so it needs no quoting.
_OWNER_SEPARATOR = "__fabrik_env_owner_follows__"


def _read_env_file(path: str, _ssh: Any) -> dict[str, str]:
    """Parse ``{path}/.env`` overlaid by ``{path}/.env.owner`` on the current SSH target — the
    MERGED view — ``{}`` ONLY when ``.env`` is absent; any ssh/read failure or unrecognised probe
    answer raises :class:`DeployError`.

    The one absent-vs-failed distinction shared by :meth:`SSHDeployer.read_env` (the
    app-role decision and :meth:`~SSHDeployer.inject_env`'s merge) and
    :meth:`SSHDeployer._build_env` (the deploy/redeploy merge). ONE probe and ONE
    read, as before the owner split: the probe answers ``present``/``absent`` for ``.env`` on
    its first line and ``owner`` on a second line when ``.env.owner`` exists; the read is then
    today's ``sudo cat <env>`` alone, or ``sudo sh -c 'cat <env> && echo && echo <separator> && cat
    <owner>'`` —
    chained with ``&&`` so a failed read of EITHER file is a non-zero exit the ssh driver raises
    on (a ``;`` chain exits with the LAST cat's status and would hand back the owner keys alone
    as the merged view — executed in Phase A's review), and the ``echo`` is a SEPARATOR,
    because a plain two-file ``cat`` joins the last line of a ``.env``
    that lacks a trailing newline onto the owner file's first line (executed at the design's
    approval panel: the owner key vanished from the parse and the owner DSN rode into
    ``REDIS_URL``'s value, which the next write would have put back into ``.env``). The owner
    file's keys parse LAST, so they win a shared key (a stale copy left in ``.env``).

    The two files are PARSED APART: ``echo <_OWNER_SEPARATOR>`` follows the separator ``echo``
    and the content is split on that line, because a quoted value may span lines and an unterminated
    quote in ``.env`` would otherwise read the owner file into an app key — which the next write
    puts into ``.env`` (W-2ae286e2 critique). An unterminated quote raises (compose refuses the same
    file), so the read fails closed.
    """
    env_path = f"{path}/.env"
    owner_path = f"{path}/{OWNER_ENV_FILE}"
    try:
        # The whole test runs INSIDE sudo: a refused sudo prints nothing (an
        # unrecognised answer → raise) instead of the `|| echo absent` fallback
        # that `sudo test -f X && … || echo absent` would print.
        inner = (
            f"[ -f {shlex.quote(env_path)} ] && echo present || echo absent; "
            f"[ -f {shlex.quote(owner_path)} ] && echo owner || true"
        )
        probe = _ssh(f"sudo sh -c {shlex.quote(inner)}", timeout=10).strip()
        lines = [ln.strip() for ln in probe.splitlines()]
        first = lines[0] if lines else ""
        if first == "absent":
            # The deployer always writes `.env` whenever it writes the owner file, so an orphan
            # `.env.owner` is not read while `.env` is absent; the moment any write recreates
            # `.env`, the next read merges the orphan again — by design, with no freshness check
            # (D-754's reversal deletes the file explicitly for that reason).
            return {}
        if first != "present" or len(lines) > 2 or (len(lines) == 2 and lines[1] != "owner"):
            raise DeployError(f"cannot read {env_path}: unexpected probe answer {probe[:40]!r}")
        if len(lines) == 2:
            cat = (
                f"cat {shlex.quote(env_path)} && echo && echo {_OWNER_SEPARATOR} && "
                f"cat {shlex.quote(owner_path)}"
            )
            content = _ssh(f"sudo sh -c {shlex.quote(cat)}", timeout=10)
            # The separator is matched as a whole LINE, never as `\n<sep>\n`: the ssh driver
            # strips the output, so an empty `.env` puts it on the first line and an empty
            # `.env.owner` on the last. The LAST such line wins — the owner file is ours, `.env`
            # may carry hand-written text.
            lines = content.split("\n")
            at = [i for i, ln in enumerate(lines) if ln.rstrip("\r") == _OWNER_SEPARATOR]
            if not at:
                raise DeployError(f"cannot read {env_path}: the owner separator is missing")
            app_text = "\n".join(lines[: at[-1]])
            owner_text = "\n".join(lines[at[-1] + 1 :])
        else:
            app_text = _ssh(f"sudo cat {shlex.quote(env_path)}", timeout=10)
            owner_text = ""
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        raise DeployError(f"cannot read {env_path}: {e}") from e
    merged: dict[str, str] = {}
    for file_path, text in ((env_path, app_text), (owner_path, owner_text)):
        try:
            merged.update(_parse_env(text))
        except ValueError as e:  # the message names the key and line, never the value
            raise DeployError(f"cannot read {file_path}: {e}") from None
    return merged


def _split_env(env: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """``(app, owner)`` — the keys of *env* partitioned by membership in ``OWNER_ENV_KEYS``."""
    owner = {k: v for k, v in env.items() if k in OWNER_ENV_KEYS}
    app = {k: v for k, v in env.items() if k not in OWNER_ENV_KEYS}
    return app, owner


def _write_env_files(
    path: str, merged: dict[str, str], write: Callable[[str, str, str], None]
) -> None:
    """The ONE writer of ``.env`` and ``.env.owner`` under *path*: the owner half FIRST (only when
    non-empty — no empty owner file is ever written), then ``.env`` WITHOUT any owner key, one log
    line. Every path that used to write ``.env`` — ``inject_env``, the four deploy paths and
    ``_persist_git_sha`` — writes through here, so no path can resurrect the key into ``.env``
    from a merged read, and a project whose ``.env`` still carries the key gets it moved on its
    next apply or redeploy with no flag and no runbook step (spec § The delta 3). *write* is the
    ``(path, filename, content)`` writer: :func:`_write_file_to_vps_path` for a local-source app,
    :func:`_env_writer_for` for the ``/opt/<name>`` apps.
    """
    app, owner = _split_env(merged)
    if owner:
        write(path, OWNER_ENV_FILE, _format_env(owner))
        logger.info("env: %d owner key(s) kept in %s for %s", len(owner), OWNER_ENV_FILE, path)
    write(path, ".env", _format_env(app))


def _env_writer_for(name: str) -> Callable[[str, str, str], None]:
    """A ``(path, filename, content)`` writer over :func:`_write_file_to_vps` for ``/opt/<name>``,
    so the name-based callers (and their tests, which patch ``_write_file_to_vps``) keep the
    ``(name, filename, content)`` shape they have today."""

    def write(path: str, filename: str, content: str) -> None:
        _write_file_to_vps(name, filename, content)

    return write


def _read_head_sha(name: str, _ssh: Any) -> str | None:
    """The commit checked out at ``/opt/{name}``, or None — never a guess.

    A failed read or an answer that is not 40 lowercase hex logs a warning and returns None: the
    caller then leaves ``.env``'s ``GIT_SHA`` as it was, because a missing GlitchTip release is not
    worth a failed deploy. It never raises on a malformed answer (None, a non-str).
    """
    try:
        # str(... or "") — a malformed seam answer (None, a non-str) reads as "not a SHA" below,
        # so this never raises on it.
        out = str(_ssh(f"sudo git -C /opt/{name} rev-parse HEAD", timeout=30) or "").strip()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        logger.warning("GIT_SHA not updated for %s: rev-parse failed: %s", name, e)
        return None
    if not _GIT_SHA_RE.fullmatch(out):
        logger.warning("GIT_SHA not updated for %s: rev-parse answered %r", name, out[:60])
        return None
    return out


def _persist_git_sha(name: str, sha: str, _ssh: Any) -> None:
    """Read-merge-write ``GIT_SHA`` into ``/opt/{name}/.env`` (the shape ``inject_env`` uses).

    Fails OPEN for the deploy and CLOSED for the file: a failed read or write logs a warning and
    writes nothing — a truncated ``.env`` is never written, and the redeploy proceeds.
    """
    try:
        merged = _read_env_file(f"/opt/{name}", _ssh)
        merged["GIT_SHA"] = sha
        _write_env_files(f"/opt/{name}", merged, _env_writer_for(name))
    except (DeployError, RuntimeError, OSError, subprocess.TimeoutExpired) as e:
        logger.warning("GIT_SHA not updated for %s: .env read-merge-write failed: %s", name, e)


def _write_file_to_vps(name: str, filename: str, content: str) -> None:
    """Write a file to ``/opt/{name}/{filename}`` via scp-to-tmp-then-sudo-mv."""
    _write_file_to_vps_path(f"/opt/{name}", filename, content)


def _write_file_to_vps_path(path: str, filename: str, content: str) -> None:
    """Write a file to ``{path}/{filename}`` via a remote ``mktemp`` file, scp into it, then ``sudo mv``."""
    from fabrik.drivers.ssh import remote_mktemp, scp_to_vps
    from fabrik.drivers.ssh import ssh as _ssh

    # A rendered key is a path RELATIVE to the app dir; an absolute one or a `..` part would write
    # outside it as root, and an empty or `.` part names the app dir itself (`mv` then drops the
    # file inside it under its tmp name and `chown` hits the directory). Refused before anything
    # reaches the VPS — a leading `/` is an empty first part.
    if any(part in ("", ".", "..") for part in filename.split("/")):
        raise ValueError(f"refusing to write a filename outside {path}: {filename!r}")

    safe_name = filename.replace("/", "-")
    fd, tmp_local = tempfile.mkstemp(prefix=f"fabrik-{safe_name}-")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        # The remote temp file is made by `mktemp` (a random name, O_EXCL, mode 0600) BEFORE scp
        # writes into it. A pid-derived name was predictable: a local VPS user could pre-create it
        # 0666 and read a DSN through the open fd in the window before the chmod (W-8dd25072). scp
        # into the existing file keeps its owner and 0600 mode. `remote_mktemp` fails closed on any
        # answer that is not a mktemp path.
        tmp_remote = remote_mktemp(_ssh)
        try:
            scp_to_vps(tmp_local, tmp_remote, timeout=30)
        except BaseException:
            # The remote temp file exists from the mktemp on: never leave it behind, not even on
            # an interrupt.
            try:
                _ssh(f"rm -f {shlex.quote(tmp_remote)}", timeout=5)
            except Exception:  # noqa: BLE001, S110
                pass
            raise
    finally:
        try:
            os.unlink(tmp_local)
        except OSError:
            pass

    # A rendered key may be nested (`src/theme/SearchBar/index.js`, D-476): `mv` does not create the
    # destination directory, so make the parent first. Only the FILENAME part is shell-quoted: `path`
    # is a hub value the callers also use unquoted (`cd {path}`), and quoting it would stop a `~`
    # from expanding. A safe name quotes to itself, so a flat filename's command is unchanged.
    parent = posixpath.dirname(filename)
    dest = f"{path}/{shlex.quote(filename)}"
    mkdir = f"sudo mkdir -p {path}/{shlex.quote(parent)} && " if parent else ""
    # `.env` and `.env.owner` are root:root 0600 BY NAME, the mode set on the remote temp file
    # BEFORE the `mv` (which keeps it; `chown` does not touch it) so the file never sits at its
    # final path wider than 0600. The remote mktemp file is already 0600, so the chmod by name is a
    # second guard for the two secret files.
    chmod = (
        f"sudo chmod 0600 {shlex.quote(tmp_remote)} && "
        if filename in (".env", OWNER_ENV_FILE)
        else ""
    )
    try:
        _ssh(
            f"{chmod}{mkdir}sudo mv {shlex.quote(tmp_remote)} {dest} && sudo chown root:root {dest}",
            timeout=10,
        )
    except Exception:
        # Clean up remote temp file so nothing lingers on VPS
        try:
            _ssh(f"rm -f {shlex.quote(tmp_remote)}", timeout=5)
        except Exception:  # noqa: BLE001, S110
            pass
        raise


def _validate_compose(content: str) -> list[str]:
    """Validate rendered compose YAML against rule-pack constraints.

    Returns a list of error messages (empty = valid).
    Per Lesson 32: explicit key presence checks, not ``.get(key, default)``.
    """
    import yaml as _yaml

    # Text only, checked FIRST: yaml.safe_load on a file-like object (a MagicMock from a test's
    # unconfigured ssh patch has a `.read` that never returns empty) reads forever — that took
    # WSL down twice on 2026-10-17 (W-51d6c153's draft). Refuse in microseconds instead.
    if not isinstance(content, str):
        return [f"Compose content is not text (got {type(content).__name__})"]
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

        # No localhost in DATABASE_URL / REDIS_URL. `environment:` is a mapping OR the fleet's
        # documented list form (`- KEY=value`); a list was never checked, so the guard read the
        # most common shape as clean (brand-identiy-creator 01M482YX).
        env = svc_config.get("environment", {})
        if isinstance(env, list):
            env = dict(str(item).partition("=")[::2] for item in env)
        if isinstance(env, dict):
            for env_key in ("DATABASE_URL", "REDIS_URL"):
                val = env.get(env_key, "")
                if isinstance(val, str) and "localhost" in val:
                    errors.append(
                        f"Service '{svc_name}': {env_key} contains 'localhost' — "
                        "use Docker DNS (postgres-main:5432 / redis-main:6379)"
                    )

        # `healthcheck: {disable: true}` fails `docker compose up -d --wait` ("has no healthcheck
        # configured", rc 1 — compose 2.40.3), which every git and redeploy path runs; a service with
        # NO healthcheck block passes. Refused here, before `up`, with the two shapes that work.
        # A healthcheck is disabled when `disable` is true (bool or the string "true") or when its
        # `test` names no command — `["NONE"]`, the bare "NONE", or an EMPTY list. Every one of these
        # fails `--wait` identically (all measured on compose 2.40.3). NOT the empty STRING: compose runs
        # `test: ""` as `CMD-SHELL ""`, which exits 0 — a valid, always-passing check. A block with no
        # `test` inherits the image HEALTHCHECK, which this static check cannot see, so it is not judged.
        healthcheck = svc_config.get("healthcheck")
        if isinstance(healthcheck, dict):
            test = healthcheck.get("test", "absent")
            disabled = str(healthcheck.get("disable")).strip().lower() == "true" or (
                test in ("NONE", []) or (isinstance(test, list) and test[:1] == ["NONE"])
            )
            if disabled:
                errors.append(
                    f"Service '{svc_name}': a disabled healthcheck (`disable: true` or "
                    '`test: ["NONE"]`) fails `compose up --wait` — give it a liveness probe '
                    '(e.g. test: ["CMD-SHELL", "kill -0 1"]) or omit the block when the image '
                    "declares no HEALTHCHECK"
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
    validation must fetch it. Tries the four Compose-recognised filenames in compose's own
    precedence (docker compose 2.40.3 picks docker-compose.yml over .yaml); raises if none exist.

    The FIRST file that exists is the one ``docker compose up`` runs, so it is returned as read —
    empty or not — and a file that exists but cannot be read REFUSES: falling through to the next
    name would validate a stale legacy file while ``up`` ran the unchecked one (W-51d6c153
    review). Absence is told from a failed read by a sentinel the remote shell prints. Read with
    sudo: the template path writes the rendered compose root:root 0600.
    """
    from fabrik.drivers.ssh import ssh as _ssh

    for filename in ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml"):
        path = shlex.quote(f"/opt/{name}/{filename}")
        probe = f"if [ -e {path} ]; then cat {path}; else printf {_NO_COMPOSE_FILE}; fi"
        try:
            out = _ssh(f"sudo sh -c {shlex.quote(probe)}", timeout=15)
        except _SSH_FAILURES as err:
            raise DeployError(f"Cannot read /opt/{name}/{filename}: {err}") from err
        # The ssh driver returns str; anything else (a test's unconfigured mock) is refused here,
        # before a YAML parser can stream from it without end (see _validate_compose).
        if not isinstance(out, str):
            raise DeployError(
                f"Reading /opt/{name}/{filename} returned {type(out).__name__}, not text"
            )
        if out == _NO_COMPOSE_FILE:
            continue
        return out
    raise DeployError(
        f"No compose file found in /opt/{name} "
        "(looked for compose.yaml, compose.yml, docker-compose.yml, docker-compose.yaml)"
    )


def _assert_deployed_compose_valid(name: str) -> None:
    """Refuse a deployed compose at ``/opt/<name>`` that breaks the Fabrik invariants — the same
    check and message the apply paths use (W-51d6c153: redeploy and restart were the doors
    around it) — and refuse a missing ``.env`` beside it. A read failure raises from
    ``_read_compose_from_vps``."""
    errors = _validate_compose(_read_compose_from_vps(name))
    if errors:
        raise DeployError(
            f"Compose validation failed for {name}:\n" + "\n".join(f"  - {e}" for e in errors)
        )
    _assert_deployed_env_present(name)


def _assert_deployed_env_present(name: str) -> None:
    """Refuse when ``/opt/<name>/.env`` is not a regular file.

    The scaffold composes load ``.env`` with ``required: false`` so a fresh checkout parses
    (W-6f690b90), which means compose no longer refuses when the file is gone. Every deploy path
    writes it before ``up`` (``_write_env_files``); restart and redeploy do not write it before
    this check (a git redeploy's ``_persist_git_sha`` runs after it), so without the check they
    would start a stack with no DATABASE_URL or secrets that can still report healthy. An empty ``.env`` (a deploy with no keys) is present. Anything but the exact
    ``present`` answer refuses.
    """
    from fabrik.drivers.ssh import ssh as _ssh

    path = shlex.quote(f"/opt/{name}/.env")
    probe = f"if [ -f {path} ]; then printf present; else printf absent; fi"
    try:
        out = _ssh(f"sudo sh -c {shlex.quote(probe)}", timeout=15)
    except _SSH_FAILURES as err:
        raise DeployError(f"Cannot check /opt/{name}/.env: {err}") from err
    if out != "present":
        state = "absent" if out == "absent" else f"unconfirmed (probe answered {out!r:.60})"
        raise DeployError(
            f"/opt/{name}/.env is {state}; every deploy writes it before up, and restart and "
            f"redeploy would start {name} without it. Run `fabrik apply` for {name} to rewrite it."
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
    # interpolates ${VAR} in `command:` from the shell and the PROJECT `.env` beside compose.yaml at `up`
    # time — never from a service's `env_file` entries (compose-spec interpolation; research ledger
    # 2026-10-12-owner-dsn-split ods-60/61). For an image-sourced app the two files coincide, which is why
    # the 2.40.3 check could not tell them apart; a secrets-minted ${ZITADEL_MASTERKEY} expands here because
    # it lives in that project `.env` — an owner key never would (it lives in `.env.owner`).
    if image_command:
        # Single-quoted YAML scalar (escape embedded single-quotes by doubling) — keeps a colon, `#`, or
        # other YAML-special char in the command from breaking the compose, and matches Zitadel's own official
        # docker-compose form. Compose still interpolates ${VAR} from the project `.env` (interpolation runs
        # on the parsed string value, after YAML parsing).
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
