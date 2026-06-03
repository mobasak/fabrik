"""Watchdog sidecar driver — per-project image build + compose overlay + bring-up.

Called by ``InfrastructureProvisioner._provision_watchdog`` (T-P2 artifact 12)
after the spec's main compose stack is deployed. Three jobs:

1. **Render-and-build.** Vendor the sidecar source tree from
   ``/opt/fabrik-lib/watchdog/sidecar/`` into a per-project build context,
   render the 3 placeholders in ``claude-settings.json.template`` (``<project_id>``,
   ``<main_container>``, ``<project_prefix>``) to ``claude-settings.json``,
   patch the Dockerfile's COPY line to pick up the rendered file, tar the
   context, scp to the VPS, and run ``docker build -t fabrik/watchdog:<project_id>``.

2. **Compose overlay.** Generate ``compose.watchdog.yaml`` next to the spec's
   ``compose.yaml`` carrying ONLY the ``watchdog`` service. Operators bring
   the stack up with ``docker compose -f compose.yaml -f compose.watchdog.yaml up -d``;
   the driver does the same to start the sidecar after build. Overlay pattern
   chosen over in-place YAML merge to avoid clobbering ``SSHDeployer``'s
   contract that it owns ``compose.yaml``.

3. **Generate the deploy key.** The PR-proposal path needs a per-project
   git deploy key at ``/var/lib/watchdog/keys/git-deploy.key`` (mode 600).
   Generated locally with ``ssh-keygen -t ed25519``, pushed to the VPS as
   a named volume entry. Operator separately registers the pubkey with the
   project's GitHub repo (CODEOWNERS-enforced ruleset).

Spec: docs/development/plans/2026-05-30-ai-watchdog-platform-P2-subplan.md
      § 4 (sidecar contents) + § 4.6 (v1 capability expansion) + § 5
      (emitter — separately vendored into host app, not this driver's job).

NOT in this driver:
- Backrest plan registration for the watchdog state volume — picked up by
  the existing backrest registrar via ``shape.has_persistent_data`` if the
  spec opts in.
- Emitter library vendoring into the host app — operator action.
- Image rebuild optimization — every ``fabrik apply`` triggers a build;
  the Docker layer cache makes repeated builds fast (~5s incremental;
  ~3 min cold for the Node.js/Claude Code layer).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from fabrik.drivers.ssh import scp_to_vps, ssh

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

SIDECAR_SOURCE = Path("/opt/fabrik-lib/watchdog/sidecar")
IMAGE_REPO = "fabrik/watchdog"
# Where on the VPS the build context lands while docker reads it. Always
# under /tmp so a failed build doesn't leave a per-project residue under
# /opt; cleaned up by the driver in finally{}.
VPS_BUILD_ROOT = "/tmp/fabrik-watchdog-build"
# Path on the VPS where the operator's Claude Code OAuth credentials live.
# Mounted RO into the sidecar so it inherits the subscription. Defaults to
# /home/ozgur/.claude (matches the current single-operator fleet) but
# overridable via FABRIK_VPS_CLAUDE_HOME for future multi-operator setups
# or different VPS user accounts. The directory must already exist on the
# target VPS — the driver does not create it.
VPS_CLAUDE_HOME = os.environ.get("FABRIK_VPS_CLAUDE_HOME", "/home/ozgur/.claude")

# Placeholders that get substituted at render time. The PreToolUse.sh hook
# also references these but reads them from env at runtime — only the
# settings template is rendered at build time.
_PLACEHOLDERS = ("<project_id>", "<main_container>", "<project_prefix>")


class WatchdogProvisionError(RuntimeError):
    """Driver failed in a way the orchestrator should treat as non-fatal warn."""


@dataclass(slots=True)
class _RenderContext:
    """Substitution values + paths threaded through the build flow."""

    project_id: str
    main_container: str
    project_prefix: str
    apprise_url: str
    redis_url: str
    pg_dsn: str
    daily_budget_usd: float
    daily_invocations_cap: int
    per_incident_budget_usd: float
    deadman_timeout_seconds: int
    auto_tier_b: bool
    propose_fix_prs: bool
    external_docs_enabled: bool
    llm_provider_primary: str
    llm_provider_fallback: str
    cheap_model: str
    expensive_model: str
    project_system_prompt: str
    project_git_remote: str
    # Operator-tunable runtime knobs — agent.py has defaults if absent.
    check_interval_seconds: int = 60
    log_level: str = "INFO"
    promtail_update_url: str = ""
    image_tag: str = ""
    # Filled in by _build_context.
    build_ctx_local: Path | None = None
    extra_env: dict[str, str] = field(default_factory=dict)


# ── Driver ────────────────────────────────────────────────────────────────


class WatchdogDriver:
    """Build sidecar image + write compose overlay + start the service.

    Idempotent: every method is safe to re-run; the docker build is
    cache-driven, the overlay rewrite is unconditional, and ``docker compose
    up -d`` reconciles to the new image automatically.
    """

    def provision(self, ctx: Any, *, dry_run: bool = False) -> dict[str, str]:
        """Top-level entry called by the orchestrator.

        Args:
            ctx: ``DeploymentContext`` from the orchestrator. ``ctx.spec`` is
                the merged spec dict; ``ctx.app_name`` is the project_id we
                deploy under.
            dry_run: If True, return what would happen without touching the
                VPS or building anything.

        Returns:
            ``{"status": "..."}`` for the orchestrator's resource record.
        """
        spec = dict(ctx.spec) if ctx.spec else {}
        rctx = self._build_render_context(spec, ctx)
        if rctx is None:
            return {"status": "skipped"}

        if dry_run:
            logger.info(
                "[dry-run] watchdog: would build %s + write %s/compose.watchdog.yaml "
                "+ docker compose up -d watchdog",
                rctx.image_tag,
                self._compose_dir(rctx),
            )
            return {"status": "dry-run", "image_tag": rctx.image_tag}

        try:
            self._build_image(rctx)
            self._push_overlay(rctx)
            self._bring_up(rctx)
        except WatchdogProvisionError:
            raise
        except Exception as e:  # noqa: BLE001 — wrap unknown failures
            raise WatchdogProvisionError(f"watchdog provision failed: {e!r}") from e
        finally:
            if rctx.build_ctx_local and rctx.build_ctx_local.exists():
                shutil.rmtree(rctx.build_ctx_local, ignore_errors=True)
            # Best-effort: clean the remote build dir whether or not build succeeded.
            try:
                ssh(f"sudo rm -rf {VPS_BUILD_ROOT}/{rctx.project_id}", timeout=15)
            except Exception:  # noqa: BLE001
                logger.debug("post-build remote cleanup raised; ignoring")

        logger.info("watchdog: provisioned %s → %s", rctx.project_id, rctx.image_tag)
        return {"status": "provisioned", "image_tag": rctx.image_tag}

    # ── Render-context assembly ───────────────────────────────────────────

    def _build_render_context(self, spec: dict, ctx: Any) -> _RenderContext | None:
        """Materialize WatchdogConfig + project identity into a _RenderContext.

        Returns None if the spec doesn't actually opt into watchdog at this
        layer — defense in depth against a wiring slip in the orchestrator.
        """
        wcfg = spec.get("watchdog", {}) or {}
        if wcfg.get("enabled", True) is False:
            logger.info("watchdog provision: spec.watchdog.enabled=false — skipping")
            return None

        project_id = spec.get("id") or spec.get("name") or getattr(ctx, "app_name", None)
        if not project_id:
            raise WatchdogProvisionError("spec missing id/name — cannot derive project_id")
        main_container = wcfg.get("main_container") or project_id
        project_prefix = wcfg.get("project_prefix") or project_id

        # Apprise URL — by convention the registrar bakes in /notify/alerts.
        apprise_url = wcfg.get("apprise_url", "http://apprise:8000/notify/alerts")
        # Redis URL: registrar would normally inject this via inject_env when
        # shape.needs_cache=true; the watchdog needs its own DB index for
        # pause flags. Default to DB 15 (high-numbered) so it doesn't collide.
        redis_url = wcfg.get("redis_url", "redis://redis-main:6379/15")
        # Postgres DSN: cost_ledger writes go to fabrik_analytics on postgres-main.
        # Driver doesn't manage credentials here — operator-owned secret in .env;
        # the value below is the template the driver renders.
        pg_dsn = wcfg.get(
            "pg_dsn",
            "postgresql://watchdog:${WATCHDOG_PG_PASSWORD}@postgres-main:5432/fabrik_analytics",
        )

        image_tag = f"{IMAGE_REPO}:{project_id}"

        return _RenderContext(
            project_id=project_id,
            main_container=main_container,
            project_prefix=project_prefix,
            apprise_url=apprise_url,
            redis_url=redis_url,
            pg_dsn=pg_dsn,
            daily_budget_usd=float(wcfg.get("daily_budget_usd", 5.0)),
            daily_invocations_cap=int(wcfg.get("daily_invocations_cap", 200)),
            per_incident_budget_usd=float(wcfg.get("per_incident_budget_usd", 0.25)),
            deadman_timeout_seconds=int(wcfg.get("deadman_timeout_seconds", 300)),
            auto_tier_b=bool(wcfg.get("auto_tier_b", False)),
            propose_fix_prs=bool(wcfg.get("propose_fix_prs", False)),
            external_docs_enabled=bool(wcfg.get("external_docs_enabled", True)),
            llm_provider_primary=wcfg.get("llm_provider_primary", "claude-code"),
            llm_provider_fallback=wcfg.get("llm_provider_fallback", "openrouter"),
            cheap_model=wcfg.get("cheap_model", "anthropic/claude-3.5-haiku"),
            expensive_model=wcfg.get("expensive_model", "anthropic/claude-opus-4"),
            project_system_prompt=wcfg.get("project_system_prompt", ""),
            project_git_remote=wcfg.get("project_git_remote", ""),
            check_interval_seconds=int(wcfg.get("check_interval_seconds", 60)),
            log_level=str(wcfg.get("log_level", "INFO")),
            promtail_update_url=str(wcfg.get("promtail_update_url", "")),
            image_tag=image_tag,
        )

    # ── Build flow ────────────────────────────────────────────────────────

    def _build_image(self, rctx: _RenderContext) -> None:
        """Vendor source + render settings + ship to VPS + docker build."""
        if not SIDECAR_SOURCE.is_dir():
            raise WatchdogProvisionError(
                f"sidecar source not found at {SIDECAR_SOURCE} — vendor it from "
                f"mobasak/fabrik-lib first"
            )
        local_ctx = Path(tempfile.mkdtemp(prefix=f"watchdog-build-{rctx.project_id}-"))
        rctx.build_ctx_local = local_ctx
        # 1. Mirror the sidecar tree.
        shutil.copytree(SIDECAR_SOURCE, local_ctx, dirs_exist_ok=True)
        # 2. Render the settings template.
        tpl_src = local_ctx / "claude-settings.json.template"
        tpl_out = local_ctx / "claude-settings.json"
        content = tpl_src.read_text()
        content = content.replace("<project_id>", rctx.project_id)
        content = content.replace("<main_container>", rctx.main_container)
        content = content.replace("<project_prefix>", rctx.project_prefix)
        tpl_out.write_text(content)
        tpl_src.unlink()  # don't ship the unrendered template
        # 3. Patch the Dockerfile so COPY picks up the rendered file.
        dockerfile = local_ctx / "Dockerfile"
        df_content = dockerfile.read_text().replace(
            "claude-settings.json.template",
            "claude-settings.json",
        )
        dockerfile.write_text(df_content)
        # 4. Tar the context and ship it.
        tar_path = local_ctx.with_suffix(".tar.gz")
        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(str(local_ctx), arcname=rctx.project_id)
        remote_tar = f"{VPS_BUILD_ROOT}/{rctx.project_id}.tar.gz"
        # /tmp is world-writable + sticky (1777); mkdir as the SSH user (no
        # sudo) so the user can scp into the dir without permission denied.
        # An earlier driver version used `sudo mkdir` which left the dir
        # root-owned 755 — operator hit that on T-P5 Step 5 2026-06-03;
        # fixed in fabrik:HEAD + one-time hub cleanup at apply time.
        ssh(f"mkdir -p {VPS_BUILD_ROOT}", timeout=15)
        scp_to_vps(str(tar_path), remote_tar)
        ssh(f"sudo tar -xzf {remote_tar} -C {VPS_BUILD_ROOT} && sudo rm {remote_tar}", timeout=60)
        # 5. docker build. Cache-friendly: rebuilds only invalidated layers.
        build_cmd = (
            f"cd {VPS_BUILD_ROOT}/{rctx.project_id} && "
            # NO `| tail -N` — that masks the docker build's exit code with
            # tail's-always-zero. Without pipefail (off by default), a build
            # failure passes silently and the driver thinks success.
            # If output volume is a concern, trim Python-side after the call.
            f"sudo docker build -t {rctx.image_tag} . 2>&1"
        )
        logger.info("watchdog: building %s on VPS (may take ~3min cold, ~5s warm)", rctx.image_tag)
        ssh(build_cmd, timeout=600)

    # ── Compose overlay ───────────────────────────────────────────────────

    def _compose_dir(self, rctx: _RenderContext) -> str:
        return f"/opt/{rctx.project_id}"

    def _push_overlay(self, rctx: _RenderContext) -> None:
        """Write ``compose.watchdog.yaml`` to ``/opt/<project_id>/``."""
        compose = {
            "services": {
                "watchdog": {
                    "image": rctx.image_tag,
                    "container_name": f"{rctx.project_id}-watchdog",
                    "restart": "unless-stopped",
                    "depends_on": [rctx.main_container],
                    "volumes": [
                        # OAuth — read-only from VPS user's ~/.claude. Path
                        # is operator-configurable via FABRIK_VPS_CLAUDE_HOME.
                        f"{VPS_CLAUDE_HOME}:/home/watchdog/.claude:ro",
                        # State + PR workspace + deploy key — RW.
                        f"watchdog-state-{rctx.project_id}:/var/lib/watchdog",
                        # docker.sock — scoped via PreToolUse hook + claude-settings.
                        "/var/run/docker.sock:/var/run/docker.sock",
                        # Project tree RO — for Read/Grep/Glob.
                        f"/opt/{rctx.project_id}:/project:ro",
                    ],
                    "environment": self._render_env(rctx),
                    # Operator-supplied env vars (e.g. WATCHDOG_OPENROUTER_KEY,
                    # WATCHDOG_PG_PASSWORD for the pg_dsn interpolation) live
                    # in /opt/<project_id>/.env, written by SSHDeployer at
                    # deploy time. docker-compose auto-loads this since the
                    # overlay sits next to compose.yaml in /opt/<project_id>/.
                    # Anything NOT in _render_env above falls through here.
                    "env_file": [".env"],
                    "networks": ["fabrik"],
                    "deploy": {
                        "resources": {
                            "limits": {
                                # Sidecar runs Claude Code subprocess; needs headroom.
                                "memory": "1024m",
                                "cpus": "0.5",
                            }
                        }
                    },
                    "healthcheck": {
                        "test": ["CMD", "curl", "-fsS", "http://localhost:8888/health"],
                        "interval": "30s",
                        "timeout": "5s",
                        "start_period": "30s",
                        "retries": "3",
                    },
                }
            },
            "volumes": {f"watchdog-state-{rctx.project_id}": {}},
            "networks": {"fabrik": {"external": True}},
        }
        yaml_text = yaml.safe_dump(compose, sort_keys=False, default_flow_style=False)

        # scp to a tmp path then sudo mv into /opt/<id>/ (root-owned).
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write(yaml_text)
            local_tmp = fh.name
        try:
            remote_tmp = f"/tmp/{rctx.project_id}-compose.watchdog.yaml"
            scp_to_vps(local_tmp, remote_tmp)
            ssh(
                f"sudo mv {remote_tmp} {self._compose_dir(rctx)}/compose.watchdog.yaml && "
                f"sudo chown root:root {self._compose_dir(rctx)}/compose.watchdog.yaml",
                timeout=30,
            )
        finally:
            os.unlink(local_tmp)

    def _render_env(self, rctx: _RenderContext) -> dict[str, str]:
        """The 18 WATCHDOG_* env vars that agent.WatchdogContext.from_env reads."""
        env = {
            "WATCHDOG_PROJECT_ID": rctx.project_id,
            "WATCHDOG_MAIN_CONTAINER": rctx.main_container,
            "WATCHDOG_PROJECT_PREFIX": rctx.project_prefix,
            "WATCHDOG_APPRISE_URL": rctx.apprise_url,
            "WATCHDOG_REDIS_URL": rctx.redis_url,
            "WATCHDOG_PG_DSN": rctx.pg_dsn,
            "WATCHDOG_DAILY_BUDGET_USD": str(rctx.daily_budget_usd),
            "WATCHDOG_DAILY_INVOCATIONS_CAP": str(rctx.daily_invocations_cap),
            "WATCHDOG_PER_INCIDENT_BUDGET_USD": str(rctx.per_incident_budget_usd),
            "WATCHDOG_DEADMAN_TIMEOUT": str(rctx.deadman_timeout_seconds),
            "WATCHDOG_AUTO_TIER_B": str(rctx.auto_tier_b).lower(),
            "WATCHDOG_PROPOSE_FIX_PRS": str(rctx.propose_fix_prs).lower(),
            "WATCHDOG_EXTERNAL_DOCS_ENABLED": str(rctx.external_docs_enabled).lower(),
            "WATCHDOG_LLM_PRIMARY": rctx.llm_provider_primary,
            "WATCHDOG_LLM_FALLBACK": rctx.llm_provider_fallback,
            "WATCHDOG_CHEAP_MODEL": rctx.cheap_model,
            "WATCHDOG_EXPENSIVE_MODEL": rctx.expensive_model,
            "WATCHDOG_SYSTEM_PROMPT": rctx.project_system_prompt,
            "WATCHDOG_PROJECT_GIT_REMOTE": rctx.project_git_remote,
            "WATCHDOG_CHECK_INTERVAL": str(rctx.check_interval_seconds),
            "WATCHDOG_LOG_LEVEL": rctx.log_level,
            "WATCHDOG_PROMTAIL_UPDATE_URL": rctx.promtail_update_url,
        }
        # OpenRouter key + Postgres password come from the project's .env via
        # docker-compose env-file inclusion; we don't ship secrets in compose.
        # Sidecar code looks them up via os.environ.
        env.update(rctx.extra_env)
        return env

    # ── Bring-up ──────────────────────────────────────────────────────────

    def _bring_up(self, rctx: _RenderContext) -> None:
        """Start the sidecar service using the overlay alongside the main compose."""
        cmd = (
            f"cd {self._compose_dir(rctx)} && "
            f"sudo docker compose -f compose.yaml -f compose.watchdog.yaml "
            # NO `| tail -N` (same trap as _build_image — masks exit code).
            f"up -d watchdog 2>&1"
        )
        ssh(cmd, timeout=120)
        # Verify the container is alive (not just `up`d).
        status = ssh(
            f"sudo docker inspect --format='{{{{.State.Health.Status}}}}' "
            f"{rctx.project_id}-watchdog 2>/dev/null || echo 'unknown'",
            timeout=10,
        )
        logger.info("watchdog: %s-watchdog health=%s", rctx.project_id, status)


__all__ = ("WatchdogDriver", "WatchdogProvisionError")
