"""Watchdog sidecar driver — per-project image build + compose overlay + bring-up.

Called by ``InfrastructureProvisioner._provision_watchdog`` (T-P2 artifact 12)
after the spec's main compose stack is deployed. Three jobs:

1. **Render-and-build.** Vendor the sidecar source tree from
   ``/opt/fabrik-lib/watchdog/watchdog_sidecar/`` into a per-project build context,
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

3. **Generate the deploy key** (only when the project opts into git push —
   ``propose_fix_prs`` today, ``auto_code_fix`` in Tier-D). The push path needs
   a per-project git deploy key at ``/var/lib/watchdog/keys/git-deploy.key``
   (mode 600, owned by the in-container ``watchdog`` user); the image bakes
   ``GIT_SSH_COMMAND`` to use it (``Dockerfile:119-121``). Generated **once**,
   VPS-side, *after* bring-up so it lands in the exact state volume the
   container mounted (sidesteps compose's volume-name prefixing): ``ssh-keygen
   -t ed25519`` on the VPS → ``docker cp`` into the running container → chmod
   600 + chown ``watchdog``. **Idempotent — never regenerated** if already
   present (that would orphan the pubkey already registered on GitHub). The
   driver logs the PUBLIC key for the operator to register as a WRITE-enabled
   deploy key on the project's GitHub repo (CODEOWNERS-enforced ruleset).

4. **Pre-flight the app HEALTHCHECK.** ``verify_health`` (and thus Tier-D
   auto-rollback) is a no-op unless the watched app container declares a real
   ``HEALTHCHECK`` (``coordinator.py`` treats "no healthcheck" as PASS). The
   driver does **not** own the app's ``compose.yaml`` (``SSHDeployer`` does —
   see overlay note below), so it cannot inject one; instead it inspects the
   main container at provision time and logs a loud warning when none is
   present (auto-rollback-on-health will not fire → escalate-only). Tier-D
   enablement refuses projects lacking one.

5. **Tier-D autonomous code-fix** (``auto_code_fix: true`` only — off by
   default; default path renders a byte-identical image). The library ships
   ops-only: ``configure()`` is never called and ``code_fix_enabled`` needs all
   four planes present. So the driver renders a consumer ``bootstrap.py`` into
   the build context that constructs the four planes (``GitPushDeployAdapter``
   with ``repo_dir = /var/lib/watchdog/proposed/<id>`` — the same stable clone
   ``agent.propose_fix`` reuses — ``Remediator``, ``TelegramBot.from_env``,
   ``ApprovalManager``) and calls ``configure()`` before ``agent.main()``, and
   switches the Dockerfile CMD to it. Refuses to enable (degrades to
   escalate-only) when the app has no HEALTHCHECK; hard-fails when
   ``project_git_remote`` is unset. Gates are enforced by the library
   (tests/secret-scan/Telegram/silence-window/auto-rollback/STOP); the driver
   only wires them. **Prod-affecting: ships off by default; first enablement on
   one non-critical project, operator watching.**

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

import json
import logging
import os
import re
import shutil
import subprocess  # noqa: S404 — used for `gh` CLI invocation (Phase 8 deploy-key auto-push); fixed argv, no shell
import tarfile
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from fabrik.drivers.ssh import scp_to_vps, ssh

# Deterministic per-host sysadmin prompt substitutions. Replaces a hardcoded
# vps1/2/3 dict so a NEWLY PROVISIONED spoke (vpsN) renders real peers + its
# own mesh IP/role instead of "unknown" (PR3). The established fleet every host
# peers with is settled at 3; a new spoke peers with these and derives its own
# ip/role from its name. NOTE: the live trio's prompts are baked at bootstrap —
# adding a host to THEIR peer awareness still requires re-rendering them; this
# only fixes what a fresh provision renders for the new host.
_VPS_RE = re.compile(r"^vps(\d+)$")
FLEET_PEER_HOSTS = ("vps1", "vps2", "vps3")


def _mesh_ip(host: str) -> str | None:
    m = _VPS_RE.match(host)
    return f"10.99.0.{m.group(1)}" if m else None


def host_prompt_substitutions(host: str) -> dict[str, str]:
    """Deterministic {name, ip, role, peers} for the sysadmin system prompt.

    Byte-identical to the former hardcoded map for vps1/2/3; for any other
    ``vpsN`` it derives a real mesh IP/role and peers = the fleet minus self.
    A non-``vpsN`` name still falls back to ``unknown`` (true unknown host).
    """
    ip = _mesh_ip(host)
    if ip is None:
        return {"name": host, "ip": "unknown", "role": "unknown", "peers": "unknown"}
    n = int(ip.rsplit(".", 1)[1])
    role = "hub" if n == 1 else "spoke"
    peers = ", ".join(f"{p} ({_mesh_ip(p)})" for p in FLEET_PEER_HOSTS if p != host)
    return {"name": host, "ip": ip, "role": role, "peers": peers or "none"}


logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

SIDECAR_SOURCE = Path("/opt/fabrik-lib/watchdog/watchdog_sidecar")
IMAGE_REPO = "fabrik/watchdog"
# Where on the VPS the build context lands while docker reads it. Always
# under /tmp so a failed build doesn't leave a per-project residue under
# /opt; cleaned up by the driver in finally{}.
VPS_BUILD_ROOT = "/tmp/fabrik-watchdog-build"  # nosec B108 — path on the REMOTE VPS (docker build context), not a local temp; cleaned in finally
# REMOTE VPS host dir holding the per-project governance set (CLAUDE.md +
# AGENTS.md + .windsurf/rules), bind-mounted RO into the sidecar at /governance.
# Dedicated dir OUTSIDE /opt/<id> (Option B) so it never touches the app's git
# working tree — a hub copy of a git-tracked CLAUDE.md/AGENTS.md would otherwise
# collide with `git pull` on redeploy. See docs/superpowers/specs/2026-07-07-
# watchdog-governance-mount-design.md.
VPS_GOVERNANCE_ROOT = "/var/lib/watchdog-governance"
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

# Tier-D consumer bootstrap. Rendered into the build context (and the
# Dockerfile CMD switched to it) ONLY when ``auto_code_fix`` is on; the default
# path keeps ``python -m watchdog_sidecar.agent`` and never sees this file.
# Static (no per-project substitution — everything is read from env at runtime),
# so it's a constant the driver writes verbatim. The library only enters the
# code-fix path when all four planes are non-None (coordinator.code_fix_enabled),
# so a missing Telegram token here is a hard, loud failure, not a silent downgrade.
_BOOTSTRAP_PY = '''\
"""Tier-D consumer bootstrap — RENDERED by fabrik's watchdog driver.

Wires the four orchestration planes and calls configure() before the agent
loop. Only used when WATCHDOG_AUTO_CODE_FIX=true (the driver switches the
Dockerfile CMD to this file in that path); the default sidecar entrypoint is
`python -m watchdog_sidecar.agent` and never imports this.

repo_dir == PROPOSED_WORKSPACE_ROOT/<project_id>: the SAME stable clone
`agent.propose_fix` prepares each incident (idempotent clone-once, then
checkout -B watchdog/<incident> per incident). The deploy adapter merges that
per-incident branch into the deploy branch and pushes.
"""
from __future__ import annotations

import json
import os

from watchdog_sidecar import configure, state
from watchdog_sidecar.agent import PROPOSED_WORKSPACE_ROOT, STATE_DB_PATH, main
from watchdog_sidecar.control_plane import ApprovalManager, TelegramBot
from watchdog_sidecar.deploy_adapter import GitPushDeployAdapter
from watchdog_sidecar.remediation import Remediator


def _argv(env_key: str, default: list[str]) -> list[str]:
    """Parse a command from env as JSON list or shell-split string."""
    raw = os.environ.get(env_key, "").strip()
    if not raw:
        return default
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except (ValueError, TypeError):
        pass
    return raw.split()


def _redeploy_cmd(project_id: str) -> list[str]:
    target = os.environ.get("WATCHDOG_TARGET_VPS", "vps1")
    return _argv("WATCHDOG_REDEPLOY_CMD", ["ssh", target, "fabrik", "redeploy", project_id])


def build_deps() -> dict:
    project_id = os.environ["WATCHDOG_PROJECT_ID"]
    repo_dir = os.path.join(PROPOSED_WORKSPACE_ROOT, project_id)
    telegram = TelegramBot.from_env()
    if telegram is None:
        raise SystemExit(
            "Tier-D bootstrap: WATCHDOG_TELEGRAM_BOT_TOKEN + _CHAT_ID required "
            "but unset — refusing to start an unapprovable autonomous-fix loop"
        )
    window = int(os.environ.get("WATCHDOG_APPROVAL_WINDOW_SEC", "300"))
    critical = tuple(
        p.strip() for p in os.environ.get("WATCHDOG_CRITICAL_PATHS", "").split(",") if p.strip()
    )
    return {
        "deploy_adapter": GitPushDeployAdapter(
            repo_dir=repo_dir,
            deploy_branch=os.environ.get("WATCHDOG_DEPLOY_BRANCH", "main"),
            redeploy_cmd=_redeploy_cmd(project_id),
            push=True,
        ),
        "remediator": Remediator(test_cmd=_argv("WATCHDOG_TEST_CMD", ["pytest", "-q"])),
        "telegram_bot": telegram,
        "approval_manager": ApprovalManager(state.connect(STATE_DB_PATH), window_sec=window),
        "approval_window_sec": window,
        "critical_paths": critical,
    }


def run() -> None:
    configure(**build_deps())
    main()


if __name__ == "__main__":
    run()
'''


class WatchdogProvisionError(RuntimeError):
    """Driver failed in a way the orchestrator should treat as non-fatal warn."""


# Cap the per-project prompt so it can't bloat the sidecar's --system-prompt / env.
_MAX_PROMPT_BYTES = 32768
# Base for resolving project-relative prompt paths (overridable in tests).
_PROJECTS_ROOT = Path("/opt")


def _load_project_prompt(wcfg: dict, project_id: str) -> str:
    """Read watchdog.project_system_prompt_file (project-relative Markdown) and
    return its contents for injection as WATCHDOG_SYSTEM_PROMPT.

    Returns "" when unset. FAIL-SOFT on any problem with a set path (non-str /
    absolute / '..'-escape / unsafe id / missing / non-file / oversized / unreadable /
    non-UTF-8 / null byte / symlink loop): log a warning and return "" so the sidecar
    runs the CANONICAL prompt only. Traversal / symlink-escape / absolute / unsafe-id
    paths are refused WITHOUT reading; the read is bounded to _MAX_PROMPT_BYTES+1 bytes
    (no unbounded load). (A same-filesystem HARDLINK is indistinguishable from a regular
    in-project file and is not defended against — acceptable under the single-operator
    threat model: the operator already has read access, and there is no other actor.)
    Rationale: the watchdog registrar is non-fatal by design
    (``infrastructure.py`` swallows WatchdogProvisionError as a warning), so RAISING
    here would silently skip the WHOLE sidecar over an optional prompt-file typo —
    leaving the app unmonitored. A loud warning + canonical fallback keeps monitoring
    alive and never blocks the deploy.
    """
    rel = wcfg.get("project_system_prompt_file")
    if not rel:
        return ""
    if not isinstance(rel, str):
        logger.warning(
            "watchdog: project_system_prompt_file must be a string, got %s — "
            "ignoring, using canonical prompt",
            type(rel).__name__,
        )
        return ""
    try:
        if os.path.isabs(rel):
            logger.warning(
                "watchdog: project_system_prompt_file must be project-relative "
                "(got absolute %r) — ignoring, using canonical prompt",
                rel,
            )
            return ""
        # Guard the id STRING (real specs validate id to ^[a-z][a-z0-9-]*$, so this is
        # defense-in-depth for unvalidated dicts). Checking the string — not the resolved
        # path — also lets a legitimately symlinked /opt/<id> still work.
        if not project_id or "/" in project_id or ".." in project_id or project_id.startswith("."):
            logger.warning("watchdog: unsafe project id %r — ignoring project prompt", project_id)
            return ""
        project_dir = (_PROJECTS_ROOT / project_id).resolve()
        candidate = (project_dir / rel).resolve()
        if not candidate.is_relative_to(project_dir):
            logger.warning(
                "watchdog: project_system_prompt_file %r resolves outside the project "
                "dir (%s) — refused, using canonical prompt",
                rel,
                candidate,
            )
            return ""
        if not candidate.is_file():
            logger.warning(
                "watchdog: project_system_prompt_file not found: %s — using canonical prompt",
                candidate,
            )
            return ""
        # Bounded read — never load more than the cap into memory, even if the file
        # grows / is swapped after any stat (read at most MAX+1 bytes, then check).
        with candidate.open("rb") as fh:
            data = fh.read(_MAX_PROMPT_BYTES + 1)
        if len(data) > _MAX_PROMPT_BYTES:
            logger.warning(
                "watchdog: project_system_prompt_file too large (> %d bytes): %s — "
                "using canonical prompt",
                _MAX_PROMPT_BYTES,
                candidate,
            )
            return ""
        return data.decode("utf-8")  # decode error → outer except → canonical
    except Exception as e:  # noqa: BLE001 — fail-soft: ANY prompt-file problem → canonical
        logger.warning(
            "watchdog: could not read project_system_prompt_file %r: %s — using canonical prompt",
            rel,
            e,
        )
        return ""


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
    # Tier-D autonomous code-fix (opt-in). Default-false keeps the rendered
    # image byte-identical to the pre-Tier-D path.
    auto_code_fix: bool
    code_fix_window_sec: int
    critical_paths: list[str]
    # Opt-in event-driven bus sources (emitter|health|error_webhook). Empty →
    # WATCHDOG_TRIGGER_SOURCES left unset → library legacy poll path (no bus).
    trigger_sources: list[str]
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
    # Trio plan Phase 1.3 (2026-06-04): which host the sidecar will run on.
    # Used at build time to render {{ HOST_NAME }} / {{ HOST_IP }} / etc. in
    # the vendored sysadmin prompt. Sourced from ctx.target_vps in
    # _build_render_context; defaults to "vps1" so existing single-host
    # behavior is preserved if the orchestrator didn't set target_vps.
    target_vps: str = "vps1"
    # Governance mount (plan-2): set by _push_governance() to True iff the
    # project's CLAUDE.md/AGENTS.md/.windsurf/rules were shipped to the VPS
    # governance dir. Gates the /governance:ro mount (_push_overlay) +
    # WATCHDOG_GOVERNANCE_MOUNT env (_render_env). Fail-soft: False → neither is
    # emitted and the sidecar's materialize falls back to /project.
    governance_mount_ready: bool = False


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
            steps = [
                "pre-flight app HEALTHCHECK (warn-only)",
                f"build {rctx.image_tag}" + (" + Tier-D bootstrap" if rctx.auto_code_fix else ""),
                f"write {self._compose_dir(rctx)}/compose.watchdog.yaml",
                "docker compose up -d watchdog",
            ]
            if rctx.propose_fix_prs or rctx.auto_code_fix:
                steps.append("ensure git deploy key (generate-once if absent)")
            logger.info("[dry-run] watchdog: would %s", " + ".join(steps))
            return {"status": "dry-run", "image_tag": rctx.image_tag}

        try:
            # Pre-flight BEFORE build: this driver runs AFTER the app stack is
            # deployed, so the app container already exists to inspect. The
            # result decides whether Tier-D can be safely enabled — which in
            # turn decides the image's entrypoint — so it must precede the build.
            has_hc = self._check_app_healthcheck(rctx)
            self._gate_tier_d(rctx, has_hc)
            self._build_image(rctx)
            # Ship governance BEFORE the overlay — the overlay's volume list +
            # env read the returned flag. Fail-soft (False → no mount/env).
            rctx.governance_mount_ready = self._push_governance(rctx)
            self._push_overlay(rctx)
            self._bring_up(rctx)
            # Projects that push (PR proposals OR Tier-D) need a git deploy key.
            # Generated once, never rotated by the driver.
            if rctx.propose_fix_prs or rctx.auto_code_fix:
                self._ensure_deploy_key(rctx)
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

        # Git remote for the PR/Tier-D workspace clone. It is NOT a watchdog-block
        # field (WatchdogConfig has extra="forbid") — it's the project's own
        # source repo. Derive it from spec.source.repository; fall back to a raw
        # wcfg value only for unvalidated test dicts. Empty for docker/local
        # sources, which Tier-D's gate then rejects.
        source = spec.get("source") or {}
        source_repo = (
            source.get("repository")
            if isinstance(source, dict)
            else getattr(source, "repository", None)
        )
        project_git_remote = wcfg.get("project_git_remote") or source_repo or ""

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
            "postgresql://watchdog:${WATCHDOG_PG_PASSWORD}@postgres-main:5432/fabrik_analytics",  # noqa: env-var interpolation
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
            auto_code_fix=bool(wcfg.get("auto_code_fix", False)),
            code_fix_window_sec=int(wcfg.get("code_fix_window_sec", 1800)),
            critical_paths=list(wcfg.get("critical_paths", []) or []),
            trigger_sources=list(wcfg.get("trigger_sources", []) or []),
            external_docs_enabled=bool(wcfg.get("external_docs_enabled", True)),
            llm_provider_primary=wcfg.get("llm_provider_primary", "claude-code"),
            llm_provider_fallback=wcfg.get("llm_provider_fallback", "openrouter"),
            cheap_model=wcfg.get("cheap_model", "anthropic/claude-3.5-haiku"),
            expensive_model=wcfg.get("expensive_model", "anthropic/claude-opus-4"),
            project_system_prompt=_load_project_prompt(wcfg, project_id),
            project_git_remote=project_git_remote,
            check_interval_seconds=int(wcfg.get("check_interval_seconds", 60)),
            log_level=str(wcfg.get("log_level", "INFO")),
            promtail_update_url=str(wcfg.get("promtail_update_url", "")),
            image_tag=image_tag,
            target_vps=getattr(ctx, "target_vps", None) or spec.get("target_vps") or "vps1",
        )

    def _gate_tier_d(self, rctx: _RenderContext, has_healthcheck: bool) -> None:
        """Enforce Tier-D deploy-time prerequisites; degrade rather than ship blind.

        Mutates ``rctx.auto_code_fix`` to False when a prerequisite the spec
        validator can't see is unmet, so the build falls back to the default
        escalate-only entrypoint instead of an autonomous loop that can't be
        safely rolled back. Two checks:

        - **git remote** (hard): autonomous push needs a clone source. Missing
          it is an operator error → fail the apply loudly (not a silent degrade).
        - **app HEALTHCHECK** (degrade): without one, ``verify_health`` is a
          no-op so auto-rollback can't fire (R-B). Refuse Tier-D → escalate-only.
        """
        if not rctx.auto_code_fix:
            return
        if not rctx.project_git_remote:
            raise WatchdogProvisionError(
                f"watchdog: auto_code_fix=true for {rctx.project_id} but "
                f"project_git_remote is empty — Tier-D cannot clone/push without it"
            )
        if not has_healthcheck:
            logger.error(
                "watchdog: auto_code_fix requested for %s but the app container "
                "%r has NO HEALTHCHECK — auto-rollback-on-health would be blind. "
                "REFUSING Tier-D; degrading to escalate-only (default entrypoint). "
                "Add a HEALTHCHECK to the app and re-apply to enable Tier-D.",
                rctx.project_id,
                rctx.main_container,
            )
            rctx.auto_code_fix = False

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
        # 2b. Copy + render the canonical veteran-sysadmin prompt + peer protocol.
        # Trio plan Phase 1.3 (2026-06-04): the canonical prompt lives at
        # /opt/fabrik/scripts/sysadmin/system-prompt.txt on the dev WSL. The
        # driver renders host-substitution markers for the host the sidecar will
        # run on (vps1 today; per-spec target_vps in future). peer-protocol.md
        # is copied unchanged — it's reference doc the AI may Read at runtime.
        sysadmin_source = Path("/opt/fabrik/scripts/sysadmin")
        prompt_src = sysadmin_source / "system-prompt.txt"
        protocol_src = sysadmin_source / "peer-protocol.md"
        if not prompt_src.exists():
            raise WatchdogProvisionError(
                f"sysadmin prompt not found at {prompt_src} — trio plan Phase 1.1 "
                f"should have created it; run that first"
            )
        # Resolve host substitution values from rctx.target_vps (populated in
        # _build_render_context). For the watchdog-test deploy on vps1 these
        # are static; spoke deploys via target_vps would populate from the
        # deploy target's IP/role.
        target_host = rctx.target_vps
        host_substitutions = host_prompt_substitutions(target_host)
        prompt_text = prompt_src.read_text(encoding="utf-8")
        prompt_text = prompt_text.replace("{{ HOST_NAME }}", host_substitutions["name"])
        prompt_text = prompt_text.replace("{{ HOST_IP }}", host_substitutions["ip"])
        prompt_text = prompt_text.replace("{{ HOST_ROLE }}", host_substitutions["role"])
        prompt_text = prompt_text.replace("{{ PEER_HOSTS }}", host_substitutions["peers"])
        (local_ctx / "system-prompt.txt").write_text(prompt_text, encoding="utf-8")
        if protocol_src.exists():
            shutil.copy2(protocol_src, local_ctx / "peer-protocol.md")
        else:
            # Tolerate missing protocol doc — Phase 1.2 may not have shipped yet
            # on this branch; sidecar still works, just without the reference.
            (local_ctx / "peer-protocol.md").write_text(
                "# peer-protocol.md not yet vendored on this build\n",
                encoding="utf-8",
            )
        # 3. Patch the Dockerfile so COPY picks up the rendered file.
        dockerfile = local_ctx / "Dockerfile"
        df_content = dockerfile.read_text().replace(
            "claude-settings.json.template",
            "claude-settings.json",
        )
        # 3b. Tier-D ONLY: drop the consumer bootstrap into the build context and
        # switch the entrypoint to it. Default path is untouched → byte-identical
        # image. The bootstrap lands at WORKDIR (/home/watchdog/sidecar) next to
        # the package dir, so `import watchdog_sidecar` resolves.
        if rctx.auto_code_fix:
            (local_ctx / "bootstrap.py").write_text(_BOOTSTRAP_PY, encoding="utf-8")
            old_cmd = 'CMD ["python3", "-u", "-m", "watchdog_sidecar.agent"]'
            new_cmd = (
                "COPY --chown=watchdog:watchdog bootstrap.py ./\n"
                'CMD ["python3", "-u", "bootstrap.py"]'
            )
            if old_cmd not in df_content:
                raise WatchdogProvisionError(
                    "watchdog: Tier-D requested but the sidecar Dockerfile CMD line "
                    f"changed upstream (expected {old_cmd!r}); refusing to render an "
                    "ambiguous entrypoint. Update the driver's CMD patch."
                )
            df_content = df_content.replace(old_cmd, new_cmd)
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

    def _detect_docker_sock_gid(self) -> int:
        """Return the GID owning /var/run/docker.sock on the hub.

        The sidecar runs as UID/GID 1000 (Dockerfile-fixed so a bind-mounted
        ~/.claude/ owned by the operator works without chown). docker.sock is
        owned by root with group=docker; without group_add the sidecar can't
        call `docker inspect` / `docker logs` at all and detect_anomalies
        silently returns []. Caught on T-P5 dogfood 2026-06-03 — state.db had
        zero incidents after a kill because every docker probe was returning
        "permission denied".

        Using `stat` (not `getent group docker`) handles the edge case where
        the GID owning the socket differs from the `docker` group GID.
        """
        result = ssh("stat -c %g /var/run/docker.sock", timeout=10)
        return int(result.strip())

    def _push_governance(self, rctx: _RenderContext) -> bool:
        """Ship the project's governance set to a dedicated VPS dir for the mount.

        Tars ``CLAUDE.md`` + ``AGENTS.md`` + ``.windsurf/rules/`` from the hub's
        local project tree (``_PROJECTS_ROOT/<id>``) — arcname-flat at the root so
        the mount presents ``/governance/CLAUDE.md``, ``/governance/AGENTS.md``,
        ``/governance/.windsurf/rules/**`` — ``scp``s it, and extracts into
        ``VPS_GOVERNANCE_ROOT/<id>`` (wiped + recreated each apply, since governance
        drifts with every sync). fabrik-lib's ``_materialize_conventions`` reads it
        via ``WATCHDOG_GOVERNANCE_MOUNT`` (set by :meth:`_render_env` when this
        returns ``True``).

        Returns ``True`` iff the files shipped (caller then adds the mount + env).
        **Fail-soft:** returns ``False`` — never raises — on ANY error or when no
        governance member exists locally, so a governance problem never aborts
        ``provision()``; the sidecar's materialize then falls back to ``/project``
        (today's behavior). Governance files are NON-secret (rules/contracts):
        ``chmod a+rX`` (world-readable), NOT the ``chmod 600`` credential path.
        """
        # Guard project_id before it flows into paths + ssh commands — same
        # check as _load_project_prompt (rejects traversal / absolute / hidden).
        pid = rctx.project_id
        if not pid or "/" in pid or ".." in pid or pid.startswith("."):
            logger.warning("watchdog: unsafe project id %r — skipping /governance", pid)
            return False
        src_root = _PROJECTS_ROOT / pid
        members = [m for m in ("CLAUDE.md", "AGENTS.md", ".windsurf/rules") if (src_root / m).exists()]
        if not members:
            logger.warning(
                "watchdog: no governance files under %s (CLAUDE.md/AGENTS.md/.windsurf/rules) — "
                "skipping /governance mount; sidecar materialize falls back to /project",
                src_root,
            )
            return False
        remote_dir = f"{VPS_GOVERNANCE_ROOT}/{rctx.project_id}"
        remote_tar = f"{VPS_BUILD_ROOT}/{rctx.project_id}-governance.tar.gz"
        local_ctx = Path(tempfile.mkdtemp(prefix=f"watchdog-gov-{rctx.project_id}-"))
        try:
            local_tar = local_ctx / "governance.tar.gz"
            with tarfile.open(local_tar, "w:gz") as tar:
                for m in members:
                    tar.add(str(src_root / m), arcname=m)
            ssh(f"mkdir -p {VPS_BUILD_ROOT}", timeout=15)
            scp_to_vps(str(local_tar), remote_tar)
            # Wipe+recreate (fresh each apply), extract, make world-readable (RO mount).
            ssh(
                f"sudo rm -rf {remote_dir} && sudo mkdir -p {remote_dir} && "
                f"sudo tar -xzf {remote_tar} -C {remote_dir} && sudo rm -f {remote_tar} && "
                f"sudo chmod -R a+rX {remote_dir}",
                timeout=60,
            )
            logger.info(
                "watchdog: shipped governance (%s) → %s:/governance:ro",
                ", ".join(members),
                remote_dir,
            )
            return True
        except Exception as exc:  # noqa: BLE001 — fail-soft: governance never aborts provision
            logger.warning(
                "watchdog: governance ship failed for %s (%s) — skipping /governance mount; "
                "sidecar materialize falls back to /project",
                rctx.project_id,
                exc,
            )
            return False
        finally:
            shutil.rmtree(local_ctx, ignore_errors=True)

    def _push_overlay(self, rctx: _RenderContext) -> None:
        """Write ``compose.watchdog.yaml`` to ``/opt/<project_id>/``."""
        docker_gid = self._detect_docker_sock_gid()
        compose = {
            "services": {
                "watchdog": {
                    "image": rctx.image_tag,
                    "container_name": f"{rctx.project_id}-watchdog",
                    "restart": "unless-stopped",
                    "depends_on": [rctx.main_container],
                    # Add the hub's docker.sock GID as a supplementary group so
                    # the watchdog user (UID 1000) can call `docker inspect`
                    # and `docker logs` against the mounted socket. Without
                    # this, every detect_anomalies tick silently returns [].
                    "group_add": [str(docker_gid)],
                    "volumes": [
                        # OAuth — read-only from VPS user's ~/.claude. Path
                        # is operator-configurable via FABRIK_VPS_CLAUDE_HOME.
                        f"{VPS_CLAUDE_HOME}:/home/watchdog/.claude:ro",
                        # Claude CLI's per-user config file lives ALONGSIDE
                        # ~/.claude/, not inside it. Without this second mount
                        # `claude -p` exits with "Claude configuration file
                        # not found at: /home/watchdog/.claude.json" and the
                        # primary LLM path is dead — caught on T-P5 dogfood
                        # Step 6 2026-06-03. The file is gitignored on the
                        # host and contains OAuth session state; mounting RO
                        # avoids the sidecar mutating it.
                        f"{VPS_CLAUDE_HOME}.json:/home/watchdog/.claude.json:ro",
                        # State + PR workspace + deploy key — RW.
                        f"watchdog-state-{rctx.project_id}:/var/lib/watchdog",
                        # docker.sock — scoped via PreToolUse hook + claude-settings.
                        "/var/run/docker.sock:/var/run/docker.sock",
                        # Project tree RO — for Read/Grep/Glob.
                        f"/opt/{rctx.project_id}:/project:ro",
                        # Governance set RO (plan-2) — dedicated dir, added ONLY
                        # when _push_governance shipped it (Option B, never the
                        # git working tree). Sidecar materialize reads it via
                        # WATCHDOG_GOVERNANCE_MOUNT; unset → falls back to /project.
                        *(
                            [f"{VPS_GOVERNANCE_ROOT}/{rctx.project_id}:/governance:ro"]
                            if rctx.governance_mount_ready
                            else []
                        ),
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
                        "test": ["CMD", "curl", "-fsS", "http://localhost:8888/health"],  # noqa: container self-check; localhost is correct inside the container
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
            remote_tmp = f"/tmp/{rctx.project_id}-compose.watchdog.yaml"  # nosec B108 — REMOTE VPS scp target, not a local temp file
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
        # Event-driven bus sources (independent of Tier-D). Only set when the
        # spec opts in; leaving it UNSET keeps the library on its legacy poll
        # path (agent.py starts no TriggerBus). 'error_webhook' starts the
        # sidecar's :8889 ingest server; GlitchTip points its new-issue webhook
        # at http://<id>-watchdog:8889/ over the internal fabrik net.
        # WATCHDOG_INGEST_TOKEN (optional shared secret) flows via the project
        # .env (env_file), not rendered here.
        if rctx.trigger_sources:
            env["WATCHDOG_TRIGGER_SOURCES"] = ",".join(rctx.trigger_sources)
        # Critical paths drive error_webhook paging (Option A: a signal pages
        # only when its error_type / url-path substring-matches one of these)
        # AND the Tier-D remediator's high-blast-radius escalation. Render it
        # whenever set — INDEPENDENT of Tier-D — so an alerting-only target
        # (error_webhook on, auto_code_fix off, hence no bootstrap to carry
        # deps.critical_paths) still pages. For Tier-D the env is additive with
        # the bootstrap's configure(critical_paths=…). The library unions both.
        if rctx.critical_paths:
            env["WATCHDOG_CRITICAL_PATHS"] = ",".join(rctx.critical_paths)
        elif "error_webhook" in rctx.trigger_sources:
            logger.warning(
                "watchdog: %s enables error_webhook but sets no critical_paths — "
                "under Option A, error-tracker signals are CAPTURED but never PAGE "
                "(no error_type/url-path to match). Set watchdog.critical_paths "
                "(substrings of error_type e.g. 'PaymentError' or url-path e.g. "
                "'/checkout') to page.",
                rctx.project_id,
            )
        # Tier-D: only emit the autonomous-code-fix env when opted in. The
        # bootstrap (rendered into the image in the same opt-in path) reads
        # these; Telegram tokens + WATCHDOG_TEST_CMD are operator secrets that
        # arrive via the project .env (env_file), NOT rendered here.
        if rctx.auto_code_fix:
            env["WATCHDOG_AUTO_CODE_FIX"] = "true"
            env["WATCHDOG_PROPOSE_FIX_PRS"] = "true"  # workspace clone prereq
            env["WATCHDOG_APPROVAL_WINDOW_SEC"] = str(rctx.code_fix_window_sec)
            env["WATCHDOG_TARGET_VPS"] = rctx.target_vps  # default redeploy_cmd
        # Governance mount (plan-2): point the sidecar's materialize at the
        # dedicated RO mount when _push_governance succeeded. Unset → materialize
        # falls back to /project (today's behavior). Independent of Tier-D.
        if rctx.governance_mount_ready:
            env["WATCHDOG_GOVERNANCE_MOUNT"] = "/governance"
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

    # ── Prereqs: app healthcheck pre-flight + git deploy key ────────────────

    def _check_app_healthcheck(self, rctx: _RenderContext) -> bool:
        """Warn (don't fail) if the watched app container has no HEALTHCHECK.

        ``verify_health`` in the sidecar treats a container with no healthcheck
        as healthy, so Tier-D auto-rollback-on-health silently never fires for
        such an app (it degrades to escalate-only). The driver can't add a
        healthcheck — ``SSHDeployer`` owns ``compose.yaml`` — so it surfaces the
        gap loudly here. Returns True iff the main container declares one.
        """
        # `docker inspect` prints `<no value>` (Go template) when the field is
        # null/absent; any non-empty Test array means a real healthcheck.
        out = ssh(
            "sudo docker inspect --format "
            "'{{if .Config.Healthcheck}}{{.Config.Healthcheck.Test}}{{else}}NONE{{end}}' "
            f"{rctx.main_container} 2>/dev/null || echo MISSING",
            timeout=15,
        ).strip()
        has_hc = bool(out) and out not in ("NONE", "MISSING", "[]", "<no value>")
        if not has_hc:
            logger.warning(
                "watchdog: app container %r has NO HEALTHCHECK (%s) — Tier-D "
                "auto-rollback-on-health will be a no-op for %s; it will "
                "escalate instead. Add a HEALTHCHECK to the app's compose.yaml "
                "to enable health-gated rollback.",
                rctx.main_container,
                out or "inspect failed",
                rctx.project_id,
            )
        return has_hc

    def _ensure_deploy_key(self, rctx: _RenderContext) -> None:
        """Generate-once a git deploy key inside the sidecar's state volume.

        Idempotent: if ``/var/lib/watchdog/keys/git-deploy.key`` already exists
        in the running container we keep it (regenerating would orphan the
        pubkey already registered on GitHub). Done VPS-side via the running
        container so it targets the exact volume Compose mounted, regardless of
        Compose's volume-name prefixing.
        """
        container = f"{rctx.project_id}-watchdog"
        key_path = "/var/lib/watchdog/keys/git-deploy.key"
        present = ssh(
            f"sudo docker exec -u 0 {container} sh -c "
            f"'test -f {key_path} && echo PRESENT || echo ABSENT' 2>/dev/null || echo NOCONTAINER",
            timeout=15,
        ).strip()
        if present.endswith("PRESENT"):
            logger.info("watchdog: deploy key already present for %s — keeping it", rctx.project_id)
            return
        if present.endswith("NOCONTAINER"):
            raise WatchdogProvisionError(
                f"cannot place deploy key: container {container} not running"
            )
        # Generate on the VPS (host has ssh-keygen; the sidecar image may not),
        # copy into the container, lock down perms, then remove the host copy.
        remote_priv = f"/tmp/{rctx.project_id}-git-deploy.key"  # nosec B108 — REMOTE VPS tmp, removed below
        remote_pub = f"{remote_priv}.pub"
        comment = f"watchdog-{rctx.project_id}@fabrik"
        ssh(
            f"rm -f {remote_priv} {remote_pub} && "
            f"ssh-keygen -t ed25519 -N '' -C '{comment}' -f {remote_priv}",
            timeout=30,
        )
        try:
            ssh(
                # keys/ is volume-initialized from the image (owned watchdog);
                # ensure it exists, drop the key in, lock perms, restore owner.
                f"sudo docker exec -u 0 {container} mkdir -p /var/lib/watchdog/keys && "
                f"sudo docker cp {remote_priv} {container}:{key_path} && "
                f"sudo docker cp {remote_pub} {container}:{key_path}.pub && "
                f"sudo docker exec -u 0 {container} sh -c "
                f"'chmod 700 /var/lib/watchdog/keys && chmod 600 {key_path} && "
                f"chmod 644 {key_path}.pub && chown -R watchdog:watchdog /var/lib/watchdog/keys'",
                timeout=60,
            )
            pubkey = ssh(f"cat {remote_pub}", timeout=15).strip()
        finally:
            ssh(f"rm -f {remote_priv} {remote_pub}", timeout=15)
        # Phase 8 of deploy-readiness-gaps (2026-06-30): auto-push the pubkey
        # to GitHub as a write-enabled deploy key. Falls back to the print-
        # pubkey path on ANY failure (token scope missing, gh not installed,
        # non-GitHub URL, network error) — the deploy must never crash here.
        push_result = {"status": "skipped", "reason": "no_repo_url"}
        if rctx.project_git_remote:
            try:
                owner, repo = _parse_github_repo(rctx.project_git_remote)
                push_result = _push_deploy_key_to_github(
                    owner=owner,
                    repo=repo,
                    title=f"fabrik-watchdog-{rctx.project_id}",
                    pubkey=pubkey,
                )
            except ValueError as exc:
                push_result = {"status": "skipped", "reason": str(exc)}
                logger.info(
                    "watchdog: deploy-key auto-push skipped for %s (%s)",
                    rctx.project_id,
                    exc,
                )
            except Exception as exc:  # noqa: BLE001 — must not crash deploy
                push_result = {"status": "failed", "reason": str(exc)}
                logger.warning(
                    "watchdog: deploy-key auto-push raised unexpected error for %s (%s); "
                    "falling back to print-pubkey",
                    rctx.project_id,
                    exc,
                )

        if push_result["status"] in {"registered", "idempotent"}:
            logger.info(
                "watchdog: deploy key %s on GitHub for %s",
                push_result["status"],
                rctx.project_id,
            )
        else:
            # Fall-back: log the pubkey so the operator can paste it manually
            # into GitHub Settings → Deploy keys. Preserves the pre-Phase-8
            # behavior on any path the push didn't succeed.
            logger.warning(
                "watchdog: generated git deploy key for %s (auto-push: %s/%s). "
                "Register this PUBLIC key as a WRITE-enabled deploy key on the "
                "project's GitHub repo (Settings → Deploy keys → Allow write access):\n%s",
                rctx.project_id,
                push_result["status"],
                push_result.get("reason", "—"),
                pubkey,
            )


# ---------------------------------------------------------------------------
# Phase 8 of deploy-readiness-gaps plan (2026-06-30): deploy key auto-push.
#
# Helpers below are module-level (not WatchdogDriver methods) so the test
# suite can patch them at the module path without setting up a driver.
# ---------------------------------------------------------------------------

_GITHUB_REPO_RE = re.compile(
    r"^(?:https?://github\.com/|git@github\.com:)"
    r"(?P<owner>[A-Za-z0-9][A-Za-z0-9-]*)/"
    r"(?P<repo>[A-Za-z0-9_.-]+?)"
    r"(?:\.git)?/?$"
)


def _parse_github_repo(repo_url: str) -> tuple[str, str]:
    """Parse `https://github.com/<owner>/<repo>(.git)` or `git@github.com:<owner>/<repo>(.git)`.

    Returns (owner, repo). Raises ValueError for empty, malformed, or non-GitHub URLs.
    """
    if not repo_url:
        raise ValueError("repo_url is empty")
    m = _GITHUB_REPO_RE.match(repo_url.strip())
    if not m:
        raise ValueError(
            f"not a recognized GitHub URL: {repo_url!r} "
            "(supported: https://github.com/<o>/<r>(.git), git@github.com:<o>/<r>(.git))"
        )
    return m.group("owner"), m.group("repo")


def _has_repo_scope() -> bool:
    """True if `gh auth status` shows the `repo` scope is present.

    Defensive: returns False on FileNotFoundError (gh not installed),
    non-zero exit (auth failed), or absent scope. Never raises.
    """
    try:
        proc = subprocess.run(  # noqa: S603,S607 — fixed argv, no shell
            ["gh", "auth", "status", "--show-token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    # gh writes auth status to stderr by design. Look for `repo` as a
    # standalone scope token (avoid false-positive on `read:repo_hook`).
    combined = (proc.stderr or "") + (proc.stdout or "")
    return bool(re.search(r"Token scopes:.*\brepo\b", combined))


def _push_deploy_key_to_github(
    owner: str,
    repo: str,
    title: str,
    pubkey: str,
) -> dict:
    """Idempotently register `pubkey` as a write-enabled deploy key on the repo.

    Pipeline:
      1. _has_repo_scope() — if False, return early with status:skipped.
      2. GET /repos/<o>/<r>/keys — if a key with matching title exists:
         - same pubkey → status:idempotent
         - different pubkey → status:conflict (caller should fall back)
      3. POST /repos/<o>/<r>/keys with read_only=false. If 422
         "key is already in use" → status:idempotent (race-safe).
      4. Any other failure → status:failed (caller falls back).

    Returns: {"status": <enum>, ...metadata}. Never raises.
    """
    if not _has_repo_scope():
        logger.warning(
            "watchdog: `gh` token lacks `repo` scope — manual deploy-key registration required"
        )
        return {"status": "skipped", "reason": "no_repo_scope"}

    # ----- GET existing keys -----
    try:
        get_proc = subprocess.run(  # noqa: S603,S607
            ["gh", "api", f"repos/{owner}/{repo}/keys"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        logger.warning(
            "watchdog: gh GET keys failed (%s) — falling back to print-pubkey",
            exc,
        )
        return {"status": "failed", "reason": str(exc)}

    if get_proc.returncode != 0:
        logger.warning(
            "watchdog: gh GET keys returned %d — falling back to print-pubkey",
            get_proc.returncode,
        )
        return {"status": "failed", "reason": "get_failed"}

    try:
        existing = json.loads(get_proc.stdout or "[]")
    except json.JSONDecodeError:
        existing = []

    pubkey_normalized = _normalize_pubkey(pubkey)
    for entry in existing:
        if entry.get("title") == title:
            if _normalize_pubkey(entry.get("key", "")) == pubkey_normalized:
                return {"status": "idempotent", "reason": "matching_key_present"}
            logger.warning(
                "watchdog: deploy-key conflict on %s/%s — title %r already registered "
                "with a DIFFERENT key; falling back to print-pubkey",
                owner,
                repo,
                title,
            )
            return {"status": "conflict", "reason": "title_taken_by_different_key"}

    # ----- POST new key -----
    try:
        post_proc = subprocess.run(  # noqa: S603,S607
            [
                "gh",
                "api",
                "-X",
                "POST",
                f"repos/{owner}/{repo}/keys",
                "-f",
                f"title={title}",
                "-f",
                f"key={pubkey}",
                "-F",
                "read_only=false",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        logger.warning(
            "watchdog: gh POST key failed (%s) — falling back to print-pubkey",
            exc,
        )
        return {"status": "failed", "reason": str(exc)}

    if post_proc.returncode == 0:
        return {"status": "registered"}

    # Race-safe: 422 "key is already in use" is success-equivalent.
    if "key is already in use" in (post_proc.stderr or "") + (post_proc.stdout or ""):
        return {"status": "idempotent", "reason": "key_already_in_use"}

    logger.warning(
        "watchdog: gh POST key returned %d (%s) — falling back to print-pubkey",
        post_proc.returncode,
        (post_proc.stderr or "").strip()[:200],
    )
    return {"status": "failed", "reason": "post_failed"}


def _normalize_pubkey(raw: str) -> str:
    """Compare keys by the (type, base64-blob) pair only — strip the trailing
    comment + whitespace so a re-rendered comment doesn't cause a false conflict.
    """
    parts = (raw or "").strip().split()
    if len(parts) < 2:
        return raw.strip()
    return f"{parts[0]} {parts[1]}"


__all__ = ("WatchdogDriver", "WatchdogProvisionError")
