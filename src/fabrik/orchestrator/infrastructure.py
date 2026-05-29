"""Infrastructure provisioning — post-deploy registrar dispatch.

Shape-driven: ``spec['shape']`` declares what the project IS; the
orchestrator decides which registrars are applicable. ``spec['infra']``
is **override-only** — the only valid entry is ``<registrar>: false`` to
disable a shape-applicable registrar. There is no ``infra.foo: true``
opt-in path.

Applicability matrix (locked 2026-04-18, Plan §Phase 7):

===========  =============================================================
 Registrar    Applies when
===========  =============================================================
 postgres     ``shape.needs_database``
 gatus        ``shape.is_public`` AND ``spec.domain`` set
 backrest     ``shape.has_persistent_data``
 glitchtip    ``shape.kind in {service, worker, wordpress}``
 grafana      always — deployment annotations are universal
 authelia     ``shape.is_admin_dashboard`` AND ``spec.domain`` set
              (+ ``^/api/`` bypass first if ``shape.has_bearer_api``,
               Critical Success Factor §10)
 meilisearch  ``shape.has_search_feature``
===========  =============================================================

Error philosophy (mostly non-fatal):

* Every ``_provision_*`` method catches and LOGS (at WARNING) the driver
  exception — a single registrar's failure cannot break a deploy. The
  underlying drivers already categorise their own errors (e.g.
  ``grafana.py`` is non-fatal by contract; ``authelia.py`` raises on
  structural failures; ``postgres.py`` raises on identifier
  validation).
* **The one exception is glitchtip's DSN-injection step** — if
  ``verify_dsn_injection`` returns False after .env injection + docker
  compose restart, the method ROLLS BACK the GlitchTip project (to avoid an
  orphan) and re-raises. A silent miss here would leave the deployed
  app running with a stale/missing ``SENTRY_DSN`` and no errors would
  ever arrive in GlitchTip — worse than failing loud.

Rollback integration:

Every successful provisioning step calls ``ctx.add_resource(<type>, <id>)``
so :class:`fabrik.orchestrator.rollback.DeploymentRollback` can find
them via :meth:`DeploymentContext.get_resources_by_type`. Resource types
registered here (additive to the DNS/compose types already in use):

* ``"postgres"`` — value is the DB name.
* ``"gatus"`` — value is the project name (matches
  :func:`fabrik.drivers.gatus.remove_endpoint` argument).
* ``"backrest"`` — value is the plan id (``<name>-data``).
* ``"glitchtip"`` — value is the GlitchTip project name.
* ``"grafana_annotation_id"`` — integer annotation id returned by
  :func:`fabrik.drivers.grafana.post_deployment_annotation`.
* ``"authelia"`` — domain for the ``two_factor`` rule.
* ``"authelia_bypass"`` — domain for the ``^/api/`` bypass rule
  (registered separately so a rollback can remove the pair as one
  transaction — both-rule removal is what
  :func:`fabrik.drivers.authelia.remove_access_rule` already does, but
  tracking them as two records preserves the audit trail).
* ``"meilisearch"`` — index uid.

Testing:

* ``tests/orchestrator/test_infrastructure.py`` covers the shape-gating
  dispatch + the ``_enabled()`` override semantics + every registrar's
  success/skip/error path with mocked drivers.
* ``tests/orchestrator/test_infrastructure_integration.py`` runs a
  dry-run end-to-end walk through a fully-populated spec to assert
  the ``ctx.created_resources`` ledger matches the applicability matrix.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fabrik.orchestrator.context import DeploymentContext

logger = logging.getLogger(__name__)

# Registrars whose applicability should print in the resolved-infra summary.
# Kept in the same order as Plan §Phase 7 for operator readability.
_REGISTRAR_ORDER = (
    "postgres",
    "redis",
    "gatus",
    "backrest",
    "glitchtip",
    "grafana",
    "authelia",
    "meilisearch",
    "prometheus",
)


# --------------------------------------------------------------------------- #
# Override-only gate                                                           #
# --------------------------------------------------------------------------- #


def _enabled(infra: dict[str, Any], key: str) -> bool:
    """Return True unless ``infra[key]`` is explicitly ``False``.

    ``infra:`` is override-ONLY: the spec's only valid entry is
    ``<registrar>: false`` to disable an otherwise-applicable registrar.
    Any truthy value (including the default-absent case) means "run".
    We reject only the explicit ``False`` so a typo like
    ``backrest: flase`` doesn't silently skip the registrar.

    Args:
        infra: The spec's ``infra:`` block (may be empty or missing).
        key: Registrar name.

    Returns:
        False iff ``infra.get(key) is False``; True otherwise.
    """
    return infra.get(key, True) is not False


# --------------------------------------------------------------------------- #
# Applicability resolver                                                       #
# --------------------------------------------------------------------------- #


def resolve_applicability(spec: dict[str, Any]) -> dict[str, tuple[bool, str]]:
    """Resolve which registrars should run for ``spec`` and why.

    Pure function — no side effects, no driver imports. Used by:

    * :meth:`InfrastructureProvisioner.provision` to drive dispatch.
    * The CLI's resolved-registrars print at ``fabrik apply`` time.
    * The test harness to assert the matrix is honored.

    Args:
        spec: Loaded project spec (already template-merged).

    Returns:
        OrderedDict in :data:`_REGISTRAR_ORDER` mapping registrar name
        to ``(should_run: bool, reason: str)``. The reason string is
        safe to print to the operator.
    """
    shape = spec.get("shape", {}) or {}
    infra = spec.get("infra", {}) or {}
    domain = spec.get("domain")
    kind = shape.get("kind", "service")

    out: dict[str, tuple[bool, str]] = {}

    # postgres
    if shape.get("needs_database", False):
        out["postgres"] = (
            _enabled(infra, "postgres"),
            "shape.needs_database=true"
            + ("" if _enabled(infra, "postgres") else " (infra.postgres=false override)"),
        )
    else:
        out["postgres"] = (False, "not applicable: shape.needs_database=false")

    # gatus
    if shape.get("is_public", False) and domain:
        out["gatus"] = (
            _enabled(infra, "gatus"),
            "shape.is_public=true + domain set"
            + ("" if _enabled(infra, "gatus") else " (infra.gatus=false override)"),
        )
    else:
        reason = (
            "not applicable: shape.is_public=false"
            if not shape.get("is_public", False)
            else "not applicable: no domain in spec"
        )
        out["gatus"] = (False, reason)

    # backrest
    if shape.get("has_persistent_data", False):
        out["backrest"] = (
            _enabled(infra, "backrest"),
            "shape.has_persistent_data=true"
            + ("" if _enabled(infra, "backrest") else " (infra.backrest=false override)"),
        )
    else:
        out["backrest"] = (False, "not applicable: shape.has_persistent_data=false")

    # glitchtip
    if kind in ("service", "worker", "wordpress"):
        out["glitchtip"] = (
            _enabled(infra, "glitchtip"),
            f"shape.kind={kind}"
            + ("" if _enabled(infra, "glitchtip") else " (infra.glitchtip=false override)"),
        )
    else:
        out["glitchtip"] = (False, f"not applicable: shape.kind={kind}")

    # grafana (universal)
    out["grafana"] = (
        _enabled(infra, "grafana"),
        "always" + ("" if _enabled(infra, "grafana") else " (infra.grafana=false override)"),
    )

    # authelia
    if shape.get("is_admin_dashboard", False) and domain:
        out["authelia"] = (
            _enabled(infra, "authelia"),
            "shape.is_admin_dashboard=true + domain set"
            + ("" if _enabled(infra, "authelia") else " (infra.authelia=false override)"),
        )
    else:
        reason = (
            "not applicable: shape.is_admin_dashboard=false"
            if not shape.get("is_admin_dashboard", False)
            else "not applicable: no domain in spec"
        )
        out["authelia"] = (False, reason)

    # meilisearch
    if shape.get("has_search_feature", False):
        out["meilisearch"] = (
            _enabled(infra, "meilisearch"),
            "shape.has_search_feature=true"
            + ("" if _enabled(infra, "meilisearch") else " (infra.meilisearch=false override)"),
        )
    else:
        out["meilisearch"] = (False, "not applicable: shape.has_search_feature=false")

    # redis (G4 — DEPLOYMENT.md §9.9)
    if shape.get("needs_cache", False):
        out["redis"] = (
            _enabled(infra, "redis"),
            "shape.needs_cache=true"
            + ("" if _enabled(infra, "redis") else " (infra.redis=false override)"),
        )
    else:
        out["redis"] = (False, "not applicable: shape.needs_cache=false")

    # prometheus (G5 — DEPLOYMENT.md §9.9)
    # Requires both the metrics flag AND a domain (we scrape over public HTTPS
    # because we scrape via public HTTPS for consistency — same
    # rationale as gatus; see drivers/prometheus.py for the long-form notes).
    if shape.get("exposes_metrics", False) and domain:
        out["prometheus"] = (
            _enabled(infra, "prometheus"),
            "shape.exposes_metrics=true + domain set"
            + ("" if _enabled(infra, "prometheus") else " (infra.prometheus=false override)"),
        )
    else:
        reason = (
            "not applicable: shape.exposes_metrics=false"
            if not shape.get("exposes_metrics", False)
            else "not applicable: no domain in spec"
        )
        out["prometheus"] = (False, reason)

    return out


def format_resolved_summary(resolved: dict[str, tuple[bool, str]]) -> str:
    """Pretty-print the resolve_applicability output for operator eyes.

    Reproduces the Plan §Phase 7 sample:

    .. code-block:: text

        Resolved registrars (shape-driven; infra: overrides in parens):
          postgres:    RUNS     (shape.needs_database=true)
          gatus:       RUNS     (shape.is_public=true + domain set)
          ...
          authelia:    skipped  (not applicable: shape.is_admin_dashboard=false)
        Proceeding with 5 registrars. Ctrl-C to abort.
    """
    lines = ["Resolved registrars (shape-driven; infra: overrides in parens):"]
    run_count = 0
    for name in _REGISTRAR_ORDER:
        should_run, reason = resolved[name]
        verb = "RUNS    " if should_run else "skipped "
        if should_run:
            run_count += 1
        lines.append(f"  {name:<12} {verb} ({reason})")
    lines.append(f"Proceeding with {run_count} registrars.")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Provisioner                                                                  #
# --------------------------------------------------------------------------- #


class InfrastructureProvisioner:
    """Shape-driven post-deploy registrar dispatch.

    Invoked by :class:`DeploymentOrchestrator` between the Deploy and
    Verify steps. Each registrar method is isolated in a try/except —
    a single driver's failure is logged at WARNING and does NOT break
    the deploy. The one exception is glitchtip's DSN-injection
    verification: if the DSN isn't propagated to the running container,
    the project is rolled back and the method raises.

    The provisioner is stateless; it takes a :class:`DeploymentContext`
    and calls ``ctx.add_resource(type, id)`` for every successful step.
    """

    def __init__(self, deployer: Any | None = None) -> None:
        self._deployer = deployer

    @property
    def deployer(self) -> Any:
        """Lazy-load SSHDeployer if not injected."""
        if self._deployer is None:
            from fabrik.orchestrator.deployer_ssh import SSHDeployer

            self._deployer = SSHDeployer()
        return self._deployer

    def provision(self, ctx: DeploymentContext) -> None:
        """Dispatch all applicable registrars for ``ctx.spec``."""
        spec = ctx.spec
        name = spec.get("name") or spec.get("id", "unknown")
        domain = spec.get("domain")
        dry_run = ctx.dry_run

        resolved = resolve_applicability(spec)
        logger.info("Infrastructure provisioning for %s", name)
        for line in format_resolved_summary(resolved).splitlines():
            logger.info("%s", line)

        should_run = {k: v[0] for k, v in resolved.items()}

        if should_run["postgres"]:
            self._provision_postgres(name, ctx, dry_run)

        if should_run["redis"]:
            self._provision_redis(name, ctx, dry_run)

        if should_run["gatus"]:
            self._provision_gatus(name, domain, spec, ctx, dry_run)

        if should_run["backrest"]:
            self._provision_backrest(name, ctx, dry_run)

        if should_run["glitchtip"]:
            self._provision_glitchtip(name, ctx, dry_run)

        if should_run["grafana"]:
            self._provision_grafana(name, domain, spec, ctx, dry_run)

        if should_run["authelia"]:
            self._provision_authelia(domain, spec.get("shape", {}) or {}, ctx, dry_run)

        if should_run["meilisearch"]:
            self._provision_meilisearch(name, ctx, dry_run)

        if should_run["prometheus"]:
            self._provision_prometheus(name, domain, spec, ctx, dry_run)

        logger.info("Infrastructure provisioning complete for %s", name)

    # ── individual registrars ────────────────────────────────────────────── #

    def _provision_postgres(self, name: str, ctx: DeploymentContext, dry_run: bool) -> None:
        try:
            from fabrik.drivers.postgres import create_database

            # PostgreSQL identifiers don't allow hyphens without quoting.
            # Normalize to snake_case — same pattern used throughout Fabrik.
            db_name = name.replace("-", "_")
            # T4-01 G-J4: pass spec_id so the allocation registry records
            # which spec owns this DB. ``owner='fabrik'`` because the
            # orchestrator is the creator. The driver writes
            # /opt/monitoring/configs/postgres/allocations.json atomically.
            result = create_database(db_name, dry_run=dry_run, spec_id=name, owner="fabrik")
            ctx.add_resource("postgres", db_name, status=result.get("status"))
            logger.info("postgres: %s → %s", db_name, result.get("status"))
        except Exception as e:  # noqa: BLE001 — bounded non-fatal
            logger.warning("postgres provisioning failed (non-fatal): %s", e)

    def _provision_gatus(
        self,
        name: str,
        domain: str | None,
        spec: dict[str, Any],
        ctx: DeploymentContext,
        dry_run: bool,
    ) -> None:
        try:
            from fabrik.drivers.gatus import add_endpoint

            if not domain:
                # resolve_applicability should have prevented this; belt-and-braces.
                logger.warning("gatus skipped: no domain (unreachable branch)")
                return
            health_path = (spec.get("health") or {}).get("path", "/health")
            result = add_endpoint(name, domain, health_path, dry_run=dry_run)
            ctx.add_resource("gatus", name, status=result.get("status"))
            logger.info("gatus: %s → %s", name, result.get("status"))
        except Exception as e:  # noqa: BLE001
            logger.warning("gatus provisioning failed (non-fatal): %s", e)

    def _provision_backrest(self, name: str, ctx: DeploymentContext, dry_run: bool) -> None:
        try:
            from fabrik.drivers.backrest import add_backup_plan

            plan_id = f"{name}-data"
            paths = [f"/opt/{name}/data"]
            result = add_backup_plan(plan_id, paths, dry_run=dry_run)
            ctx.add_resource("backrest", plan_id, status=result.get("status"))
            logger.info("backrest: %s → %s", plan_id, result.get("status"))
        except Exception as e:  # noqa: BLE001
            logger.warning("backrest provisioning failed (non-fatal): %s", e)

    def _provision_glitchtip(self, name: str, ctx: DeploymentContext, dry_run: bool) -> None:
        """Provision GlitchTip project + inject DSN into container + verify.

        This is the one registrar where a soft failure is unacceptable.
        If the DSN isn't actually in the running container after
        .env injection + docker compose restart, the project is rolled
        back and this method raises — the app was deployed, but its error
        reporting is broken and silently missing reports is worse than
        a visible deploy failure.
        """
        try:
            from fabrik.drivers.glitchtip import (
                create_project,
                delete_project,
                verify_dsn_injection,
            )

            result = create_project(name, dry_run=dry_run)
            dsn = result.get("dsn")

            # Register the project for rollback regardless of the DSN path
            # below — if the DSN injection raises, rollback still finds it.
            ctx.add_resource("glitchtip", name, status=result.get("status"))

            if dry_run:
                logger.info("glitchtip: %s → dry_run (DSN injection skipped)", name)
                return

            if not dsn:
                # create_project already logged the anomaly; treat as
                # degraded but not fatal — the project exists, just no DSN.
                logger.warning("glitchtip: %s has no DSN; skipping injection", name)
                return

            # Inject DSN into the deployed container via .env + restart,
            # then verify it actually arrived via docker inspect (Lesson 31).
            if not ctx.coolify_uuid:
                logger.warning(
                    "glitchtip: ctx.coolify_uuid unset; "
                    "cannot inject SENTRY_DSN. Degraded but non-fatal."
                )
                return

            self.deployer.inject_env(ctx, {"SENTRY_DSN": dsn, "GLITCHTIP_DSN": dsn})

            if not verify_dsn_injection(name, dsn, max_wait=240):
                # Ground-truth check failed: roll back the project so we
                # don't leave an orphan, then raise so the caller can
                # decide (typically: fail the deploy with full rollback).
                delete_project(name)
                raise RuntimeError(
                    f"SENTRY_DSN not injected into {name!r} container "
                    f"within 240s after .env injection + restart. Project "
                    f"rolled back."
                )

            logger.info("glitchtip: %s → DSN verified in container", name)
        except RuntimeError:
            # DSN verification failures are fatal per the contract above.
            raise
        except Exception as e:  # noqa: BLE001
            logger.warning("glitchtip provisioning failed (non-fatal): %s", e)

    def _provision_grafana(
        self,
        name: str,
        domain: str | None,
        spec: dict[str, Any],
        ctx: DeploymentContext,
        dry_run: bool,
    ) -> None:
        try:
            from fabrik.drivers.grafana import post_deployment_annotation

            # Grafana annotation also embeds the git SHA for operator
            # correlation against commit history. Prefer spec-level
            # ``git_sha`` if set (e.g. by the deployer after commit
            # resolution); fall back to the FABRIK_GIT_SHA env var the
            # CI injects; otherwise omit.
            git_sha = spec.get("git_sha") or os.getenv("FABRIK_GIT_SHA")
            result = post_deployment_annotation(
                name, domain=domain, git_sha=git_sha, dry_run=dry_run
            )
            aid = result.get("annotation_id")
            if aid is not None:
                ctx.add_resource("grafana_annotation_id", str(aid), status=result.get("status"))
            logger.info("grafana: %s → %s", name, result.get("status"))
        except Exception as e:  # noqa: BLE001
            logger.warning("grafana annotation failed (non-fatal): %s", e)

    def _provision_authelia(
        self,
        domain: str | None,
        shape: dict[str, Any],
        ctx: DeploymentContext,
        dry_run: bool,
    ) -> None:
        """Provision Authelia forward-auth — bypass FIRST, then two_factor.

        Critical Success Factor §10 ordering: when ``has_bearer_api``
        is true, the ``^/api/`` bypass rule MUST be inserted before
        the ``two_factor`` catch-all so Authelia matches the bypass
        first on Bearer-token API requests. The authelia driver's
        ``insert_before_twofactor=True`` handles that placement.
        """
        try:
            from fabrik.drivers.authelia import add_access_rule

            if not domain:
                logger.warning("authelia skipped: no domain (unreachable branch)")
                return

            if shape.get("has_bearer_api", False):
                add_access_rule(
                    domain,
                    policy="bypass",
                    resources=["^/api/"],
                    insert_before_twofactor=True,
                    dry_run=dry_run,
                )
                ctx.add_resource("authelia_bypass", domain)

            add_access_rule(domain, policy="two_factor", dry_run=dry_run)
            ctx.add_resource("authelia", domain)
            logger.info("authelia: %s → protected", domain)
        except Exception as e:  # noqa: BLE001
            logger.warning("authelia provisioning failed (non-fatal): %s", e)

    def _provision_redis(self, name: str, ctx: DeploymentContext, dry_run: bool) -> None:
        """Reserve a Redis logical-DB index and inject ``REDIS_URL`` (G4).

        The driver call is idempotent — a re-run picks up the existing
        assignment from the registry file. Always tracks the resource
        record (so a same-deploy rollback can release the slot) and
        always patches the env var when ``coolify_uuid`` is known (so
        a re-run after a compose redeploy repopulates a wiped env).
        """
        try:
            from fabrik.drivers.redis import acquire_db_index

            result = acquire_db_index(name, dry_run=dry_run)
            ctx.add_resource("redis", name, status=result.get("status"))
            redis_url = result.get("redis_url")
            db_index = result.get("db_index")
            logger.info("redis: %s -> DB %s (%s)", name, db_index, result.get("status"))

            if dry_run or not redis_url:
                return

            # Inject REDIS_URL via .env merge + docker compose up -d.
            if not ctx.coolify_uuid:
                logger.warning(
                    "redis: ctx.coolify_uuid unset; cannot inject REDIS_URL. "
                    "Degraded but non-fatal — value will be patched on next "
                    "deploy."
                )
                return
            self.deployer.inject_env(ctx, {"REDIS_URL": redis_url})
            logger.info("redis: REDIS_URL injected into .env and container restarted")
        except Exception as e:  # noqa: BLE001 — bounded non-fatal
            logger.warning("redis provisioning failed (non-fatal): %s", e)

    def _provision_prometheus(
        self,
        name: str,
        domain: str | None,
        spec: dict[str, Any],
        ctx: DeploymentContext,
        dry_run: bool,
    ) -> None:
        """Append a Prometheus scrape job for the service's ``/metrics`` (G5).

        Optional bearer token via ``spec['monitoring']['bearer_token']``
        for protected metrics endpoints — most Fabrik services leave
        ``/metrics`` open on the internal network and rely on
        ``X-Internal-Token`` at the Traefik layer for the public path,
        so this defaults to no auth.
        """
        try:
            from fabrik.drivers.prometheus import add_scrape_target

            if not domain:
                logger.warning("prometheus skipped: no domain (unreachable branch)")
                return
            monitoring = (
                (spec.get("monitoring") or {}) if isinstance(spec.get("monitoring"), dict) else {}
            )
            metrics_path = monitoring.get("metrics_path", "/metrics")
            bearer_token = monitoring.get("bearer_token")
            result = add_scrape_target(
                name,
                domain=domain,
                metrics_path=metrics_path,
                bearer_token=bearer_token,
                dry_run=dry_run,
            )
            ctx.add_resource("prometheus", name, status=result.get("status"))
            logger.info("prometheus: %s -> %s", name, result.get("status"))
        except Exception as e:  # noqa: BLE001
            logger.warning("prometheus provisioning failed (non-fatal): %s", e)

    def _provision_meilisearch(self, name: str, ctx: DeploymentContext, dry_run: bool) -> None:
        try:
            from fabrik.drivers.meilisearch import create_index

            # MeiliSearch UIDs allow `-` but Fabrik uses snake_case for
            # consistency with postgres (and for cleaner query strings).
            index_uid = name.replace("-", "_")
            result = create_index(index_uid, dry_run=dry_run)
            ctx.add_resource("meilisearch", index_uid, status=result.get("status"))
            logger.info("meilisearch: %s → %s", index_uid, result.get("status"))
        except Exception as e:  # noqa: BLE001
            logger.warning("meilisearch provisioning failed (non-fatal): %s", e)


__all__ = (
    "InfrastructureProvisioner",
    "resolve_applicability",
    "format_resolved_summary",
)
