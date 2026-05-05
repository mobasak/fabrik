"""Fabrik Deployment Orchestrator.

Unified controller for end-to-end deployments.
"""

import logging
import os
from pathlib import Path
from typing import Any

from fabrik.drivers.cloudflare import CloudflareClient
from fabrik.drivers.dns import DNSClient
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer import ServiceDeployer
from fabrik.orchestrator.exceptions import (
    DeployError,
    DeploymentError,
    InvalidStateTransitionError,
    ProvisioningError,
    RollbackError,
    ValidationError,
    VerificationError,
)
from fabrik.orchestrator.rollback import RollbackManager
from fabrik.orchestrator.secrets import SecretsManager
from fabrik.orchestrator.states import DeploymentState, can_transition
from fabrik.orchestrator.validator import SpecValidator
from fabrik.orchestrator.verifier import DeploymentVerifier

logger = logging.getLogger(__name__)

__all__ = [
    "DeploymentState",
    "DeploymentContext",
    "DeploymentOrchestrator",
    "DeploymentError",
    "ValidationError",
    "ProvisioningError",
    "RollbackError",
]


class DeploymentOrchestrator:
    """Unified orchestrator for end-to-end deployments.

    Handles: validation → secrets → provisioning → deploy → verify → rollback
    """

    def __init__(
        self,
        validator: SpecValidator | None = None,
        secrets_manager: SecretsManager | None = None,
        deployer: ServiceDeployer | None = None,
        verifier: DeploymentVerifier | None = None,
        rollback_manager: RollbackManager | None = None,
        infrastructure_provisioner: Any | None = None,
    ):
        """Initialize orchestrator with optional component overrides.

        Args:
            infrastructure_provisioner: Post-deploy registrar dispatcher.
                Defaults to :class:`fabrik.orchestrator.infrastructure.InfrastructureProvisioner`.
                Override in tests to inject a stub and avoid driver-side
                network calls. See Plan §Phase 7.
        """
        from fabrik.orchestrator.infrastructure import InfrastructureProvisioner

        self.validator = validator or SpecValidator()
        self.secrets_manager = secrets_manager or SecretsManager()
        self.deployer = deployer or ServiceDeployer()
        self.verifier = verifier or DeploymentVerifier()
        self.rollback_manager = rollback_manager or RollbackManager()
        self.infrastructure_provisioner = infrastructure_provisioner or InfrastructureProvisioner()

    def deploy(
        self,
        spec_path: Path,
        dry_run: bool = False,
        skip_health_check: bool = False,
        keep_on_failure: bool = False,
    ) -> DeploymentContext:
        """Run full deployment pipeline.

        Args:
            spec_path: Path to spec YAML file
            dry_run: If True, simulate without making changes
            skip_health_check: If True, skip health check verification (useful for initial deployments)
            keep_on_failure: B27 — when True, do NOT roll back created resources
                on failure. The Coolify app, DNS records, GlitchTip project,
                etc. all stay in place. Used by the proof-run harness so build
                logs and container state survive long enough to be inspected.
                Default ``False`` preserves the production fail-closed behavior.

        Returns:
            DeploymentContext with deployment details

        Raises:
            ValidationError: Spec validation fails
            ProvisioningError: Infrastructure provisioning fails
            DeployError: Deployment fails
            VerificationError: Post-deployment verification fails
        """
        ctx = DeploymentContext(spec_path=spec_path, dry_run=dry_run)

        try:
            # Step 1: Validate
            self._transition(ctx, DeploymentState.VALIDATING)
            spec, spec_hash, warnings = self.validator.load_and_validate(spec_path)
            ctx.spec = spec
            ctx.spec_hash = spec_hash
            for w in warnings:
                logger.warning("Validation warning: %s", w)

            # Step 2: Load secrets
            self._load_secrets(ctx, spec)

            # Step 3: Provision (DNS)
            self._transition(ctx, DeploymentState.PROVISIONING)
            logger.info("Provisioning resources for %s", spec["name"])
            self._provision_dns(ctx, spec)

            # Step 4: Deploy
            self._transition(ctx, DeploymentState.DEPLOYING)
            self.deployer.deploy(ctx)

            # Step 4b: Provision infrastructure registrars (post-deploy).
            # Must run AFTER deployer.deploy so ctx.coolify_uuid is set
            # (glitchtip needs it for SENTRY_DSN injection) and the
            # deployed FQDN has Traefik routers up (authelia + gatus
            # attach to live routes). Non-fatal by contract, except for
            # glitchtip's DSN-injection verification which rolls back on
            # failure. See fabrik.orchestrator.infrastructure.
            try:
                self.infrastructure_provisioner.provision(ctx)
            except Exception as infra_err:
                # Only glitchtip's DSN-verify path re-raises from
                # InfrastructureProvisioner. Bubble it up as a
                # ProvisioningError so the main handler attempts
                # rollback with the resources tracked so far.
                raise ProvisioningError(
                    f"Infrastructure provisioning failed: {infra_err}",
                    resource_type="infrastructure",
                ) from infra_err

            # Step 5: Verify
            self._transition(ctx, DeploymentState.VERIFYING)
            self.verifier.verify(ctx, skip_health_check=skip_health_check)

            # Success
            self._transition(ctx, DeploymentState.COMPLETE)
            # B35: workers have no domain (validator/verifier already
            # short-circuit for them). Fall back to the spec id so this
            # log line doesn't raise ``KeyError: 'domain'`` and trigger the
            # broad ``except Exception`` block below \u2014 which would then
            # attempt an illegal COMPLETE -> FAILED transition.
            logger.info(
                "Deployment complete: %s",
                ctx.deployed_url or spec.get("domain") or spec.get("id") or spec.get("name"),
            )

        except (ValidationError, ProvisioningError, DeployError, VerificationError) as e:
            ctx.error = str(e)
            ctx.error_step = e.step if hasattr(e, "step") else None
            logger.error("Deployment failed at %s: %s", ctx.error_step, e)

            # Attempt rollback (skipped under keep_on_failure)
            if ctx.created_resources and not keep_on_failure:
                self._transition(ctx, DeploymentState.ROLLING_BACK)
                errors = self.rollback_manager.rollback(ctx)
                if errors:
                    self._transition(ctx, DeploymentState.FAILED)
                else:
                    self._transition(ctx, DeploymentState.ROLLED_BACK)
            else:
                if keep_on_failure and ctx.created_resources:
                    logger.warning(
                        "keep_on_failure=True; skipping rollback of %d resource(s) "
                        "so they can be inspected. Manual cleanup required.",
                        len(ctx.created_resources),
                    )
                self._transition(ctx, DeploymentState.FAILED)

        except Exception as e:
            ctx.error = str(e)
            logger.exception("Unexpected error during deployment")

            # Attempt rollback for unexpected errors too (skipped under keep_on_failure)
            if ctx.created_resources and not keep_on_failure:
                self._transition(ctx, DeploymentState.ROLLING_BACK)
                errors = self.rollback_manager.rollback(ctx)
                if errors:
                    self._transition(ctx, DeploymentState.FAILED)
                else:
                    self._transition(ctx, DeploymentState.ROLLED_BACK)
            else:
                if keep_on_failure and ctx.created_resources:
                    logger.warning(
                        "keep_on_failure=True; skipping rollback of %d resource(s) "
                        "so they can be inspected. Manual cleanup required.",
                        len(ctx.created_resources),
                    )
                self._transition(ctx, DeploymentState.FAILED)

        return ctx

    def _load_secrets(self, ctx: DeploymentContext, spec: dict) -> None:
        """Populate ``ctx.secrets`` from the spec's ``secrets`` block.

        Supports both the legacy list form (required-only) and the
        SecretsPolicy dict form with ``required`` / ``generate`` /
        ``from_env`` / ``from_file`` sub-blocks. Extracted from
        :meth:`deploy` so :meth:`refresh_infrastructure` can reuse the
        exact same loading semantics.
        """
        secrets_config = spec.get("secrets", {})
        if not secrets_config:
            return

        if isinstance(secrets_config, list):
            ctx.secrets = self.secrets_manager.load_all(secrets_config)
            return

        if not isinstance(secrets_config, dict):
            return

        all_secrets: dict[str, str] = {}

        required = secrets_config.get("required", [])
        if required:
            all_secrets.update(self.secrets_manager.load_all(required))

        generate = secrets_config.get("generate", [])
        if generate:
            all_secrets.update(self.secrets_manager.load_all(generate))

        from_env = secrets_config.get("from_env", [])
        project_path = Path(f"/opt/{spec.get('id', spec.get('name'))}")
        env_file = project_path / ".env"
        if env_file.exists():
            try:
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip()
                        if key in from_env and key not in all_secrets:
                            all_secrets[key] = value
            except Exception as e:
                logger.warning("Failed to read .env file: %s", e)

        for key in from_env:
            if key not in all_secrets:
                env_value = os.getenv(key)
                if env_value:
                    all_secrets[key] = env_value
                else:
                    logger.warning("Secret %s not found in environment", key)

        from_file = secrets_config.get("from_file", {})
        for env_var, file_path in from_file.items():
            if env_var not in all_secrets:
                try:
                    all_secrets[env_var] = Path(file_path).read_text()
                except FileNotFoundError:
                    logger.warning("File not found for secret %s: %s", env_var, file_path)
                except Exception as e:
                    logger.warning("Failed to read file for secret %s: %s", env_var, e)

        ctx.secrets = all_secrets

    def refresh_infrastructure(
        self,
        spec_path: Path,
        dry_run: bool = False,
    ) -> DeploymentContext:
        """Re-run only the InfrastructureProvisioner against an existing app.

        Closes DEPLOYMENT.md §9.9 G2. Use this when the spec's ``shape``
        flags or ``infra`` overrides change but the application code itself
        does not need a rebuild — for example after adding
        ``shape.needs_database: true`` or flipping ``infra.gatus: false``.

        Pipeline:
          1. Validate spec.
          2. Load secrets (same path as :meth:`deploy`).
          3. Resolve ``ctx.coolify_uuid`` from the live Coolify app list
             matched on spec name (with the conventional ``fabrik-`` prefix
             tried as a fallback).
          4. Call ``InfrastructureProvisioner.provision(ctx)``.

        Skipped vs :meth:`deploy`: DNS provisioning, ``ServiceDeployer.deploy``,
        post-deploy verification, rollback. The infrastructure provisioner is
        already idempotent per-registrar, so re-running is safe.

        Args:
            spec_path: Path to the spec YAML.
            dry_run: If True, the provisioner runs in dry-run mode
                (each registrar checks ``ctx.dry_run``).

        Returns:
            DeploymentContext with ``coolify_uuid`` and any
            ``created_resources`` recorded by the registrars.

        Raises:
            ValidationError: Spec validation fails.
            ProvisioningError: Coolify app not found, or any registrar
                raises (notably the GlitchTip DSN-injection verifier).
        """
        from fabrik.drivers.coolify import CoolifyClient

        ctx = DeploymentContext(spec_path=spec_path, dry_run=dry_run)

        spec, spec_hash, warnings = self.validator.load_and_validate(spec_path)
        ctx.spec = spec
        ctx.spec_hash = spec_hash
        for w in warnings:
            logger.warning("Validation warning: %s", w)

        self._load_secrets(ctx, spec)

        spec_name = spec.get("name") or spec.get("id")
        if not spec_name:
            raise ProvisioningError(
                "Spec is missing both 'name' and 'id' — cannot resolve Coolify app.",
                resource_type="infrastructure",
            )

        coolify = CoolifyClient()
        apps = coolify.list_applications()
        candidate_names = {spec_name, f"fabrik-{spec_name}"}
        match = next((a for a in apps if a.get("name") in candidate_names), None)
        if not match:
            available = ", ".join(sorted(a.get("name", "<unnamed>") for a in apps))
            raise ProvisioningError(
                f"No Coolify app found matching spec name {spec_name!r} "
                f"(also tried 'fabrik-{spec_name}'). Available: {available}",
                resource_type="infrastructure",
            )
        ctx.coolify_uuid = match.get("uuid")
        ctx.deployed_url = (
            f"https://{spec['domain']}" if spec.get("domain") else None
        )
        logger.info(
            "refresh_infrastructure: matched %s -> %s", spec_name, ctx.coolify_uuid
        )

        try:
            self.infrastructure_provisioner.provision(ctx)
        except Exception as e:
            raise ProvisioningError(
                f"Infrastructure refresh failed: {e}",
                resource_type="infrastructure",
            ) from e

        return ctx

    def _provision_dns(self, ctx: DeploymentContext, spec: dict) -> None:
        """Create DNS record for the deployment domain.

        Args:
            ctx: Deployment context
            spec: Parsed spec dict with optional 'domain' key
        """
        domain = spec.get("domain")
        if not domain:
            logger.info("No domain in spec — skipping DNS provisioning")
            return

        # Parse domain into subdomain + base domain
        parts = domain.split(".")
        if len(parts) < 3:
            logger.info("Domain %s has no subdomain — skipping DNS provisioning", domain)
            return

        base_parts = 2
        if (
            len(parts) >= 4
            and len(parts[-1]) == 2
            and parts[-2] in {"co", "com", "net", "org", "gov", "ac"}
        ):
            base_parts = 3

        subdomain = ".".join(parts[:-base_parts])
        base_domain = ".".join(parts[-base_parts:])

        if not subdomain:
            logger.info("Domain %s has no subdomain — skipping DNS provisioning", domain)
            return

        vps_ip = os.getenv("VPS_IP", "172.93.160.197")

        if ctx.dry_run:
            logger.info(
                "[DRY RUN] Would create DNS A record: %s.%s -> %s",
                subdomain,
                base_domain,
                vps_ip,
            )
            return

        # Try DNS Manager (Namecheap) first, fall back to Cloudflare
        try:
            dns = DNSClient()
            result = dns.add_subdomain(base_domain, subdomain, vps_ip)
            if result.get("success") is False:
                raise ProvisioningError(
                    f"DNS Manager error for {domain}: {result.get('message', 'unknown')}",
                    resource_type="dns",
                )
            ctx.add_resource("dns", domain, zone=base_domain)
            ctx.dns_record_id = domain
            logger.info("DNS record created: %s -> %s (via DNS Manager)", domain, vps_ip)
        except ProvisioningError:
            raise
        except Exception as dns_err:
            logger.warning("DNS Manager failed (%s), trying Cloudflare...", dns_err)
            try:
                cf = CloudflareClient()
                cf.add_subdomain(base_domain, subdomain, vps_ip)
                ctx.add_resource("dns", domain, zone=base_domain)
                ctx.dns_record_id = domain
                logger.info("DNS record created: %s -> %s (via Cloudflare)", domain, vps_ip)
            except Exception as cf_err:
                raise ProvisioningError(
                    f"DNS provisioning failed for {domain}: DNS Manager={dns_err}, Cloudflare={cf_err}",
                    resource_type="dns",
                ) from cf_err

    def _transition(self, ctx: DeploymentContext, new_state: DeploymentState) -> None:
        """Transition to a new state with validation.

        Raises:
            InvalidStateTransitionError: If transition is not allowed
        """
        if ctx.state != new_state:
            if not can_transition(ctx.state, new_state):
                raise InvalidStateTransitionError(ctx.state.name, new_state.name)
            ctx.state = new_state
            logger.debug("State: %s", new_state.name)
