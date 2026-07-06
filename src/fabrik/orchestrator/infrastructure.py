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
 prometheus   ``shape.exposes_metrics`` AND ``spec.domain`` set
 redis        ``shape.needs_cache``
 watchdog     ``spec.watchdog.enabled`` (default True; operator opts out
              with ``watchdog: { enabled: false }``; rule pack
              ``.windsurf/rules/core/60-watchdog.md`` documents the
              shape-kind-driven recommendation operators implement)
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
    "watchdog",
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

    # watchdog (T-P2). WatchdogConfig.enabled defaults to True so the
    # registrar runs by default; operator opts a spec out with
    # `watchdog: { enabled: false }`. The shape-kind-driven matrix in
    # `.windsurf/rules/core/60-watchdog.md` is operator discipline (e.g.
    # disable for static-site / docusaurus), not encoded here — keeping the
    # gate one-line keeps applicability honest to what the spec actually says.
    watchdog_cfg = spec.get("watchdog", {}) or {}
    if watchdog_cfg.get("enabled", True):
        out["watchdog"] = (
            _enabled(infra, "watchdog"),
            "spec.watchdog.enabled=true"
            + ("" if _enabled(infra, "watchdog") else " (infra.watchdog=false override)"),
        )
    else:
        out["watchdog"] = (False, "not applicable: spec.watchdog.enabled=false")

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

        # P1 (watchdog platform): ensure the shared fabrik_analytics DB +
        # cost_ledger table exist BEFORE any per-spec registrar runs.
        # Unconditional (NOT gated by shape.needs_database) so a worker
        # spec without its own DB but with the watchdog enabled can still
        # write to cost_ledger. Idempotent at the DB level — every call
        # after the first is a no-op.
        self._provision_shared_analytics(dry_run)

        should_run = {k: v[0] for k, v in resolved.items()}

        if should_run["postgres"]:
            self._provision_postgres(
                name, spec, ctx, dry_run, provision_watchdog_roles=should_run["watchdog"]
            )

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

        if should_run["watchdog"]:
            self._provision_watchdog(name, ctx, dry_run)

        logger.info("Infrastructure provisioning complete for %s", name)

    # ── individual registrars ────────────────────────────────────────────── #

    def _provision_shared_analytics(self, dry_run: bool) -> None:
        """Ensure the shared ``fabrik_analytics`` DB + ``cost_ledger`` exist.

        Called unconditionally from :meth:`provision` — does NOT depend on
        ``shape.needs_database``. A watchdog-enabled worker spec that has
        no Postgres need of its own still requires ``cost_ledger`` to be
        available for cost-budget writes.

        Idempotent: every call after the first per cluster is a no-op at
        the DB level (CREATE DATABASE existence check + CREATE TABLE
        IF NOT EXISTS).

        Non-fatal: a failure here logs WARNING and does NOT abort the
        deploy. The per-spec postgres registrar (if applicable) still
        runs afterwards.
        """
        try:
            from fabrik.drivers.postgres import ensure_shared_analytics_db

            # No grant_to_role yet — current projects use the postgres
            # superuser, which already has all privileges. Per-project
            # roles + their GRANT will be wired when create_database
            # starts provisioning dedicated roles.
            analytics_result = ensure_shared_analytics_db(dry_run=dry_run)
            logger.info(
                "shared analytics DB %s → %s (schema_applied=%s)",
                analytics_result.get("database"),
                analytics_result.get("status"),
                analytics_result.get("schema_applied"),
            )
        except Exception as e:  # noqa: BLE001 — bounded non-fatal
            logger.warning("shared analytics provisioning failed (non-fatal): %s", e)

    def _provision_postgres(
        self,
        name: str,
        spec: dict[str, Any],
        ctx: DeploymentContext,
        dry_run: bool,
        provision_watchdog_roles: bool = False,
    ) -> None:
        try:
            from fabrik.drivers.postgres import create_database, database_exists

            # PostgreSQL identifiers don't allow hyphens without quoting.
            # Normalize to snake_case — same pattern used throughout Fabrik.
            derived = name.replace("-", "_")
            # Phase 1a (deploy-readiness-gaps): respect spec.depends.postgres when
            # set — it is now load-bearing, the derived spec-id name is only the
            # fallback. `spec` is a raw dict here; `depends` may be absent or null.
            configured = (spec.get("depends", {}) or {}).get("postgres")
            db_name = configured or derived
            # RENAME GUARD: if the spec pins a name that differs from the historical
            # derived name, and a DB under the derived name already exists while the
            # pinned one does not, applying would point the app at a NEW empty DB and
            # orphan the derived DB's data (app /health passes on SELECT 1 but real
            # endpoints 500). Refuse loudly + skip rather than silently mis-provision,
            # unless the operator explicitly opts in.
            if (
                configured
                and db_name != derived
                and not dry_run
                and database_exists(derived)
                and not database_exists(db_name)
                and os.getenv("FABRIK_ALLOW_DB_RENAME") != "1"
            ):
                logger.error(
                    "postgres: RENAME GUARD blocked '%s' — spec pins depends.postgres='%s' "
                    "but DB '%s' (historical derived name) exists and '%s' does not. NOT "
                    "creating '%s' (would orphan '%s' data + point the app at an empty DB). "
                    "Migrate (pg_dump '%s' | psql '%s'), then re-apply; or set "
                    "FABRIK_ALLOW_DB_RENAME=1 to create the new DB intentionally.",
                    name,
                    db_name,
                    derived,
                    db_name,
                    db_name,
                    derived,
                    derived,
                    db_name,
                )
                ctx.add_resource("postgres", derived, status="rename_guard_blocked")
                return
            # Mint a DEDICATED non-superuser role that OWNS the DB (db_user==db_name)
            # so the app can connect as a non-superuser — the only way Postgres RLS
            # (multi-tenant isolation) actually applies; the postgres superuser would
            # bypass it. T4-01 G-J4: spec_id records which spec owns this DB.
            db_user = db_name
            # Phase 5 of deploy-readiness-gaps (2026-06-30): pass through the
            # spec_dir + postgres_seed so create_database can auto-restore
            # a checked-in dump if the new DB is empty (idempotent).
            depends = spec.get("depends", {}) or {}
            seed_relpath = depends.get("postgres_seed")
            spec_dir = ctx.spec_path.parent if ctx.spec_path else None
            result = create_database(
                db_name,
                db_user=db_user,
                dry_run=dry_run,
                spec_id=name,
                owner="fabrik",
                spec_dir=spec_dir,
                seed_relpath=seed_relpath,
            )
            ctx.add_resource("postgres", db_name, status=result.get("status"))
            # Inject DATABASE_URL for the dedicated role so the container connects
            # with a working credential (the registrar is the ONLY place that knows
            # the generated password). On a re-deploy the DB already 'exists' and no
            # password is returned — the prior .env value is preserved by the merge.
            password = result.get("password")
            if password and not dry_run:
                database_url = f"postgresql://{db_user}:{password}@postgres-main:5432/{db_name}"  # noqa: password is a runtime CSPRNG value from create_database, not a hardcoded secret
                self.deployer.inject_env(ctx, {"DATABASE_URL": database_url})
                logger.info("postgres: DATABASE_URL injected for role %s", db_user)
            # Watchdog per-project DB roles (fabrik-lib product-aware contract):
            # when the watchdog sidecar is applicable for this spec, mint a
            # SELECT-only RO role (sidecar default; the diagnosis lane used across
            # all tiers) + a DML-only RW role (Tier-C approved-write lane) on the
            # app DB and inject their DSNs. Gated on the SAME predicate as the
            # watchdog registrar (should_run["watchdog"]) so the roles never drift
            # from the sidecar. Own try/except: a role failure must NOT abort the
            # app DB provisioning that already succeeded above.
            if provision_watchdog_roles:
                try:
                    from fabrik.drivers.postgres import create_watchdog_roles

                    wd = create_watchdog_roles(db_name, dry_run=dry_run)
                    wd_env: dict[str, str] = {}
                    if wd["ro"].get("password"):
                        wd_env["WATCHDOG_DB_URL_RO"] = (
                            f"postgresql://{wd['ro']['user']}:{wd['ro']['password']}"
                            f"@postgres-main:5432/{db_name}"  # noqa: runtime CSPRNG password, not a hardcoded secret
                        )
                    if wd["rw"].get("password"):
                        wd_env["WATCHDOG_DB_URL_RW"] = (
                            f"postgresql://{wd['rw']['user']}:{wd['rw']['password']}"
                            f"@postgres-main:5432/{db_name}"  # noqa: runtime CSPRNG password, not a hardcoded secret
                        )
                    if wd_env and not dry_run:
                        self.deployer.inject_env(ctx, wd_env)
                        logger.info(
                            "postgres: watchdog DSNs injected for %s (%s)",
                            db_name,
                            ", ".join(sorted(wd_env)),
                        )
                    # Record in the deploy resource summary so a provisioning
                    # problem is visible to the operator, not buried in a warning.
                    ctx.add_resource(
                        "watchdog-db-roles",
                        db_name,
                        status="dry_run" if dry_run else "provisioned",
                    )
                except Exception as e:  # noqa: BLE001 — bounded non-fatal
                    logger.warning(
                        "postgres: watchdog role provisioning failed for %s (non-fatal): %s",
                        db_name,
                        e,
                    )
                    ctx.add_resource("watchdog-db-roles", db_name, status="failed")

            # Subagent-runs telemetry: per-project INSERT-only role on the shared
            # fabrik_analytics.subagent_runs table + fleet-wide env injection so
            # projects vendoring fabrik-lib/subagents just work after `fabrik apply`,
            # no manual .env.local edits. Gated on the SAME analytics-DB availability:
            # ensure_shared_analytics_db() (which applied SUBAGENT_RUNS_DDL) already
            # ran during this apply, so the table exists. Own try/except: a role
            # failure must NOT abort the app DB provisioning above.
            #
            # Unconditional (not shape-flag-gated): unset SUBAGENT_RUNS_DSN is a
            # harmless no-op per the module (JSONL-only fail-open). Fleet-wide inject
            # mirrors DATABASE_URL — every project gets it; only those that vendor
            # `subagents` and set OPENROUTER_API_KEY actually use it.
            try:
                from fabrik.drivers.postgres import create_subagent_ins_role

                # Sanitize hyphens → underscores for the pg role name (Finder A#1: the
                # `_validate_identifier` regex `^[a-zA-Z_][a-zA-Z0-9_]{0,62}$` rejects
                # hyphens; nearly every fleet spec has one). SUBAGENT_PROJECT keeps the
                # ORIGINAL name so row tagging stays human-friendly for querying — the
                # sanitized form is only the role/DSN handle. Same discipline as db_user
                # derivation for DATABASE_URL: `derived = name.replace('-', '_')` (:441).
                sa_project_id = name.replace("-", "_")
                sa = create_subagent_ins_role(sa_project_id, dry_run=dry_run)
                sa_env: dict[str, str] = {"SUBAGENT_PROJECT": name}
                if sa["ins"].get("password"):
                    sa_env["SUBAGENT_RUNS_DSN"] = (
                        f"postgresql://{sa['ins']['user']}:{sa['ins']['password']}"
                        f"@postgres-main:5432/fabrik_analytics"  # noqa: runtime CSPRNG password, not a hardcoded secret
                    )
                # SUBAGENT_SELECTION_DOC = the governance-synced ranking doc. SINGLE
                # path — the vendored subagents module's reader (`_synced_ranking()`
                # in select.py) accepts one file, not a list. To combine the fleet's
                # real-run data (TASK) with the public benchmarks (CODING), the
                # HUB-SIDE aggregator (`rank_task_subagents.py`) BLENDS both signals
                # into this one file: fleet data wins where present, CODING seeds
                # the `### code` section when the fleet has no coding runs yet.
                # A prior draft of this code injected `TASK,CODING` comma-separated,
                # but the reader treats the whole string as ONE literal filename
                # → OSError → silent `{}` → pick_models permanently on `_TABLE`.
                # Reverted to single-path 2026-07-06 after the convergence review
                # caught the regression; the CODING blend now happens at doc-emit
                # time (rank_task_subagents.py) instead of at read time.
                sa_env["SUBAGENT_SELECTION_DOC"] = "docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
                if not dry_run:
                    self.deployer.inject_env(ctx, sa_env)
                    injected = ", ".join(sorted(sa_env))
                    logger.info("postgres: subagent-runs env injected for %s (%s)", name, injected)
                ctx.add_resource(
                    "subagent-ins-role",
                    name,
                    status="dry_run" if dry_run else "provisioned",
                )
            except Exception as e:  # noqa: BLE001 — bounded non-fatal
                logger.warning(
                    "postgres: subagent-ins role provisioning failed for %s (non-fatal): %s",
                    name,
                    e,
                )
                ctx.add_resource("subagent-ins-role", name, status="failed")

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
            if not ctx.app_name:
                logger.warning(
                    "glitchtip: ctx.app_name unset; "
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
                # Bypass ONLY the authenticated API prefix. Default ^/api/, but a
                # service whose bearer auth covers a SUB-prefix (e.g. /api/v1) while
                # OTHER /api/* routes are unauthenticated MUST narrow this via
                # shape.bearer_bypass_prefix — otherwise the broad ^/api/ bypass
                # exposes those routes publicly (un-2FA'd). See core/35-security-auth.
                bypass_prefix = shape.get("bearer_bypass_prefix") or "^/api/"
                add_access_rule(
                    domain,
                    policy="bypass",
                    resources=[bypass_prefix],
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
        always patches the env var when ``app_name`` is known (so
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
            if not ctx.app_name:
                logger.warning(
                    "redis: ctx.app_name unset; cannot inject REDIS_URL. "
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
            # Multi-service composes (saas-skeleton) serve /metrics on an
            # INTERNAL container, not the public Traefik edge — the default
            # ``<domain>:443`` target would scrape the Next.js frontend, which
            # has no /metrics. Scrape the ``<name>-api`` container directly over
            # the fabrik network instead. An explicit ``monitoring.target`` in
            # the spec always wins.
            target = monitoring.get("target")
            scheme = monitoring.get("scheme", "https")
            if target is None and spec.get("template") == "saas-skeleton":
                target = f"{name}-api:8000"
                scheme = "http"
            result = add_scrape_target(
                name,
                domain=domain,
                target=target,
                scheme=scheme,
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

    def _provision_watchdog(self, name: str, ctx: DeploymentContext, dry_run: bool) -> None:
        """Build/refresh the per-project watchdog sidecar image + inject sidecar service.

        Real work happens in the watchdog driver (T-P2 artifact 13). Until that
        driver ships, this method is a wire-up stub: it logs the intended action
        in dry-run mode and lazily-imports the driver in real mode, falling back
        to a WARNING (non-fatal — every registrar's failure is bounded) if the
        driver module isn't present yet. That keeps `fabrik apply` working on
        existing specs that don't depend on the watchdog while T-P2 finishes.
        """
        if dry_run:
            logger.info(
                "[dry-run] watchdog: would build fabrik/watchdog:%s + inject sidecar service "
                "alongside main container",
                name,
            )
            ctx.add_resource("watchdog", name, status="dry-run")
            return
        try:
            from fabrik.drivers.watchdog import WatchdogDriver  # T-P2 artifact 13
        except ImportError:
            logger.warning(
                "watchdog registrar reached but fabrik.drivers.watchdog is not installed yet "
                "(T-P2 artifact 13 pending — see "
                "docs/development/plans/2026-05-30-ai-watchdog-platform-P2-subplan.md). "
                "Skipping for spec '%s'.",
                name,
            )
            return
        try:
            driver = WatchdogDriver()
            result = driver.provision(ctx, dry_run=dry_run)
            ctx.add_resource("watchdog", name, status=result.get("status") if result else "ok")
            logger.info("watchdog: %s → %s", name, result.get("status") if result else "ok")
        except Exception as e:  # noqa: BLE001
            logger.warning("watchdog provisioning failed (non-fatal): %s", e)


__all__ = (
    "InfrastructureProvisioner",
    "resolve_applicability",
    "format_resolved_summary",
)
