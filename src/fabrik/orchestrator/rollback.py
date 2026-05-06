"""Rollback manager for failed deployments."""

import logging
from typing import Any

from fabrik.orchestrator.context import DeploymentContext, ResourceRecord
from fabrik.orchestrator.exceptions import RollbackError

logger = logging.getLogger(__name__)


class RollbackManager:
    """Manage rollback of failed deployments.

    Only rolls back resources created in the current deployment run.
    Uses ownership tracking from DeploymentContext.
    """

    def __init__(
        self,
        coolify_client: Any | None = None,
        dns_client: Any | None = None,
    ):
        """Initialize rollback manager.

        Args:
            coolify_client: CoolifyClient instance
            dns_client: DNSClient instance
        """
        self._coolify_client = coolify_client
        self._dns_client = dns_client

    @property
    def coolify_client(self) -> Any:
        """Lazy-load Coolify client."""
        if self._coolify_client is None:
            from fabrik.drivers.coolify import CoolifyClient

            self._coolify_client = CoolifyClient()
        return self._coolify_client

    @property
    def dns_client(self) -> Any:
        """Lazy-load DNS client."""
        if self._dns_client is None:
            from fabrik.drivers.cloudflare import CloudflareClient

            self._dns_client = CloudflareClient()
        return self._dns_client

    def rollback(self, ctx: DeploymentContext) -> list[str]:
        """Roll back all resources created in this deployment.

        Args:
            ctx: Deployment context with created_resources

        Returns:
            List of errors encountered (empty if all successful)
        """
        if ctx.dry_run:
            logger.info("[DRY RUN] Would rollback %d resources", len(ctx.created_resources))
            return []

        if not ctx.created_resources:
            logger.info("No resources to rollback")
            return []

        errors: list[str] = []

        # Rollback in reverse order (LIFO)
        for resource in reversed(ctx.created_resources):
            try:
                self._rollback_resource(resource)
            except Exception as e:
                error_msg = (
                    f"Failed to rollback {resource.resource_type}/{resource.resource_id}: {e}"
                )
                logger.error(error_msg)
                errors.append(error_msg)

        if errors:
            logger.warning("Rollback completed with %d errors", len(errors))
        else:
            logger.info("Rollback completed successfully")

        return errors

    def _rollback_resource(self, resource: ResourceRecord) -> None:
        """Roll back a single resource.

        Dispatches on ``resource_type`` to the matching ``_rollback_*``
        handler. Resource types registered by
        :class:`fabrik.orchestrator.infrastructure.InfrastructureProvisioner`
        are handled here (Phase 4i):

        * ``coolify`` / ``dns`` / ``monitor`` — legacy pre-Phase-4 types.
        * ``postgres`` — **destructive-no-op by policy.** Logs WARNING
          directing the operator to drop the DB manually
          (Plan §Rollback Strategy, "Destructive-action policy"). DB
          data loss must be a conscious, human decision.
        * ``gatus`` — config mutation, auto-unwound via
          :func:`fabrik.drivers.gatus.remove_endpoint`.
        * ``backrest`` — config mutation, auto-unwound via
          :func:`fabrik.drivers.backrest.remove_backup_plan`.
        * ``glitchtip`` — ephemeral project, auto-unwound via
          :func:`fabrik.drivers.glitchtip.delete_project`.
        * ``grafana_annotation_id`` — ephemeral annotation, auto-unwound
          via :func:`fabrik.drivers.grafana.delete_annotation`.
        * ``authelia`` / ``authelia_bypass`` — access-control rule,
          auto-unwound via
          :func:`fabrik.drivers.authelia.remove_access_rule` which
          removes **all** rules for the domain (two_factor + any
          ^/api/ bypass) in a single call. The second record of the
          pair is therefore a **no-op** — tracked here by maintaining
          a per-context set of domains already rolled back so we don't
          double-restart Authelia. The set lives on the
          :class:`DeploymentContext` via a dynamic attribute (safer
          than passing it through every call).
        * ``meilisearch`` — **destructive-no-op by policy.** Index data
          may be populated; operator runs ``fabrik meili drop`` manually.

        Args:
            resource: Resource record to rollback

        Raises:
            Exception: If rollback fails (only for legacy ``coolify``/
            ``dns``/``monitor`` types; Phase-4 registrar handlers are
            best-effort and swallow exceptions internally so one
            broken handler never aborts the reverse-order walk).
        """
        logger.info(
            "Rolling back %s: %s",
            resource.resource_type,
            resource.resource_id,
        )

        rt = resource.resource_type
        if rt == "coolify":
            self._rollback_coolify(resource)
        elif rt == "dns":
            self._rollback_dns(resource)
        elif rt == "monitor":
            self._rollback_monitor(resource)
        elif rt == "postgres":
            self._rollback_postgres(resource)
        elif rt == "gatus":
            self._rollback_gatus(resource)
        elif rt == "backrest":
            self._rollback_backrest(resource)
        elif rt == "glitchtip":
            self._rollback_glitchtip(resource)
        elif rt == "grafana_annotation_id":
            self._rollback_grafana_annotation_id(resource)
        elif rt in ("authelia", "authelia_bypass"):
            self._rollback_authelia(resource)
        elif rt == "meilisearch":
            self._rollback_meilisearch(resource)
        elif rt == "redis":
            self._rollback_redis(resource)
        elif rt == "prometheus":
            self._rollback_prometheus(resource)
        else:
            logger.warning("Unknown resource type: %s", resource.resource_type)

    def _rollback_coolify(self, resource: ResourceRecord) -> None:
        """Delete a Coolify application.

        Args:
            resource: Coolify resource record
        """
        uuid = resource.resource_id
        try:
            self.coolify_client.delete_application(uuid)
            logger.info("Deleted Coolify application: %s", uuid)
        except Exception as e:
            raise RollbackError(
                f"Failed to delete Coolify app {uuid}: {e}",
                resource_type="coolify",
            ) from e

    def _rollback_dns(self, resource: ResourceRecord) -> None:
        """Delete a DNS record.

        ``resource.resource_id`` is the FQDN (e.g. ``app.example.com``) and
        ``resource.metadata['zone']`` is the root zone (``example.com``).
        Cloudflare's API requires zone-id/record-id UUIDs, so we resolve
        both from the names via :meth:`CloudflareClient.delete_record_by_name`.

        Args:
            resource: DNS resource record
        """
        fqdn = resource.resource_id
        zone = resource.metadata.get("zone")

        if not zone:
            logger.warning("DNS record %s has no zone metadata, skipping", fqdn)
            return

        # Derive subdomain label: "app.example.com" + zone "example.com" -> "app"
        subdomain = fqdn[: -len(zone) - 1] if fqdn.endswith(zone) and fqdn != zone else fqdn

        try:
            # delete_record_by_name(domain=zone, record_type, name=subdomain)
            self.dns_client.delete_record_by_name(zone, "A", subdomain)
            logger.info("Deleted DNS record: %s", fqdn)
        except Exception as e:
            # Record may already be gone (idempotent rollback) — warn, don't fail
            logger.warning("Failed to delete DNS record %s (non-fatal): %s", fqdn, e)

    def _rollback_monitor(self, resource: ResourceRecord) -> None:
        """Legacy monitor rollback stub.

        Superseded by :meth:`_rollback_gatus` for Phase-4 registrar
        tracking. Left in place for backwards-compatibility with any
        resource records already written under the old
        ``resource_type="monitor"`` convention.

        Args:
            resource: Monitor resource record
        """
        monitor_id = resource.resource_id
        logger.info("Would delete monitor: %s (legacy stub)", monitor_id)

    # =========================================================================
    # Phase 4i — Infrastructure registrar rollback handlers
    #
    # These unwind resources created by InfrastructureProvisioner (see
    # src/fabrik/orchestrator/infrastructure.py). All handlers are
    # best-effort: they log and swallow driver exceptions so that a
    # single broken handler cannot abort the reverse-order walk.
    # This is a deliberate contrast with _rollback_coolify/_rollback_dns
    # above, which raise RollbackError — those are hard-stops because
    # a lingering Coolify app or DNS record is a billable/visible
    # resource, whereas a lingering Gatus endpoint or Authelia rule is
    # a config-level artefact the operator can clean up later.
    # =========================================================================

    def _rollback_postgres(self, resource: ResourceRecord) -> None:
        """Destructive-no-op by design (Plan §Rollback Strategy).

        Database drops are destructive and must be an explicit human
        decision. On rollback, we log a prominent WARNING pointing the
        operator at the manual-drop command. Auto-dropping here would
        turn a partial deploy failure into data loss — fail-closed
        means data survives.

        Args:
            resource: Postgres resource record (``resource_id`` is the
                DB name).
        """
        db_name = resource.resource_id
        logger.warning(
            "Postgres database %r was created during this deploy but will "
            "NOT be auto-dropped (destructive-action policy). If you want "
            "it removed, run: fabrik db drop %s",
            db_name,
            db_name,
        )

    def _rollback_gatus(self, resource: ResourceRecord) -> None:
        """Remove the Gatus endpoint file for this project (best-effort)."""
        from fabrik.drivers.gatus import remove_endpoint

        name = resource.resource_id
        try:
            remove_endpoint(name)
            logger.info("Rolled back gatus endpoint: %s", name)
        except Exception as e:  # noqa: BLE001 — bounded best-effort
            logger.warning("gatus rollback failed for %s (non-fatal): %s", name, e)

    def _rollback_backrest(self, resource: ResourceRecord) -> None:
        """Remove the Backrest backup plan (best-effort)."""
        from fabrik.drivers.backrest import remove_backup_plan

        plan_id = resource.resource_id
        try:
            remove_backup_plan(plan_id)
            logger.info("Rolled back backrest plan: %s", plan_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("backrest rollback failed for %s (non-fatal): %s", plan_id, e)

    def _rollback_glitchtip(self, resource: ResourceRecord) -> None:
        """Delete the GlitchTip project (best-effort).

        The provisioner already calls ``delete_project`` on DSN-verify
        failure (inside
        :meth:`fabrik.orchestrator.infrastructure.InfrastructureProvisioner._provision_glitchtip`),
        so this handler often finds a 404. The driver's
        :func:`fabrik.drivers.glitchtip.delete_project` treats 404 as
        success, so the call is idempotent.
        """
        from fabrik.drivers.glitchtip import delete_project

        name = resource.resource_id
        try:
            delete_project(name)
            logger.info("Rolled back glitchtip project: %s", name)
        except Exception as e:  # noqa: BLE001
            logger.warning("glitchtip rollback failed for %s (non-fatal): %s", name, e)

    def _rollback_grafana_annotation_id(self, resource: ResourceRecord) -> None:
        """Delete the Grafana deployment annotation (best-effort).

        Grafana annotations are informational — a dangling one is a
        cosmetic issue on the dashboard, never a security or billing
        concern. The resource_id is the annotation id as a **string**
        (DeploymentContext.add_resource coerces to str); we parse it
        back to int for the driver call.
        """
        from fabrik.drivers.grafana import delete_annotation

        raw_id = resource.resource_id
        try:
            ann_id = int(raw_id)
        except (TypeError, ValueError):
            logger.warning(
                "grafana rollback skipped: non-integer annotation id %r",
                raw_id,
            )
            return
        try:
            delete_annotation(ann_id)
            logger.info("Rolled back grafana annotation: %d", ann_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("grafana rollback failed for %d (non-fatal): %s", ann_id, e)

    def _rollback_authelia(self, resource: ResourceRecord) -> None:
        """Remove ALL Authelia rules for this domain (best-effort, deduped).

        A single call to
        :func:`fabrik.drivers.authelia.remove_access_rule` removes
        both the ``two_factor`` rule and any ``^/api/`` bypass rule for
        the domain in one Authelia restart. If the provisioner
        registered the domain under BOTH ``authelia`` and
        ``authelia_bypass`` resource records (which it does when
        ``shape.has_bearer_api`` is true), the second rollback pass
        would otherwise trigger a redundant driver invocation — two
        Authelia container restarts in quick succession, which is both
        slow and can transiently 502 in-flight admin requests.

        Dedup strategy: we stash a set of already-rolled-back domains
        on the ``RollbackManager`` instance itself (``self``, not the
        context — the context is passed by value to each handler and a
        fresh attribute on it would be clobbered-by-surprise). The
        manager is single-use per deploy, so the set's lifetime
        matches the rollback run exactly.
        """
        from fabrik.drivers.authelia import remove_access_rule

        domain = resource.resource_id
        if not hasattr(self, "_authelia_rolled_back"):
            self._authelia_rolled_back: set[str] = set()
        if domain in self._authelia_rolled_back:
            logger.debug(
                "authelia rollback skipped for %s: already removed by sibling record",
                domain,
            )
            return
        try:
            remove_access_rule(domain)
            self._authelia_rolled_back.add(domain)
            logger.info("Rolled back authelia rules for %s", domain)
        except Exception as e:  # noqa: BLE001
            logger.warning("authelia rollback failed for %s (non-fatal): %s", domain, e)

    def _rollback_redis(self, resource: ResourceRecord) -> None:
        """Release the Redis logical-DB index for this service (best-effort).

        Same fail-closed data-preservation policy as
        :meth:`_rollback_postgres`: we only release the registry slot,
        we do NOT FLUSHDB. The slot becomes available for the next
        ``acquire_db_index`` call. Any Redis data left in the released
        DB is preserved for forensic / recovery use; the operator
        explicitly opts in to FLUSHDB via ``fabrik destroy --drop-data``.
        """
        from fabrik.drivers.redis import release_db_index

        name = resource.resource_id
        try:
            release_db_index(name, flushdb=False)
            logger.info("Rolled back redis assignment: %s", name)
        except Exception as e:  # noqa: BLE001
            logger.warning("redis rollback failed for %s (non-fatal): %s", name, e)

    def _rollback_prometheus(self, resource: ResourceRecord) -> None:
        """Remove the Prometheus scrape target for this service (best-effort)."""
        from fabrik.drivers.prometheus import remove_scrape_target

        name = resource.resource_id
        try:
            remove_scrape_target(name)
            logger.info("Rolled back prometheus scrape target: %s", name)
        except Exception as e:  # noqa: BLE001
            logger.warning("prometheus rollback failed for %s (non-fatal): %s", name, e)

    def _rollback_meilisearch(self, resource: ResourceRecord) -> None:
        """Destructive-no-op by design (Plan §Rollback Strategy).

        MeiliSearch indices are cheap to recreate, but the *data* in
        them may be the result of hours of ingestion. Same policy as
        postgres: log a WARNING with the manual-drop command; do NOT
        auto-delete. Distinguished from `_rollback_postgres` only by
        the recovery command.

        Args:
            resource: Meilisearch resource record (``resource_id`` is
                the index uid).
        """
        uid = resource.resource_id
        logger.warning(
            "MeiliSearch index %r was created during this deploy but will "
            "NOT be auto-dropped (destructive-action policy). If you want "
            "it removed, run: fabrik meili drop %s",
            uid,
            uid,
        )
