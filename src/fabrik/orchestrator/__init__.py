"""Fabrik Deployment Orchestrator.

Unified controller for end-to-end deployments.
"""

import logging
import os
from pathlib import Path
from typing import Any

import fabrik.state as state_module
from fabrik.drivers.cloudflare import CloudflareClient
from fabrik.drivers.dns import DNSClient
from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer_ssh import SSHDeployer
from fabrik.orchestrator.exceptions import (
    DeployError,
    DeploymentError,
    InvalidStateTransitionError,
    ProvisioningError,
    RollbackError,
    ValidationError,
    VerificationError,
)
from fabrik.orchestrator.infrastructure import _REGISTRAR_ORDER
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


def _assert_error_webhook_colocated(spec: dict[str, Any], target_vps: str) -> None:
    """Fail closed if a spec ingests ``error_webhook`` but deploys off the hub.

    Phase 2 (deploy-readiness): GlitchTip is pinned to vps1 and the ``fabrik``
    network is a per-host bridge, so a watchdog sidecar on vps2/vps3 can't receive
    GlitchTip's POST to ``<id>-watchdog:8889``. Rather than silently ship a dead
    alerting path, reject at apply time. Only ``error_webhook`` needs same-host
    ingest — the HTTP-based sources (``emitter``, ``health``) are unaffected.
    """
    sources = (spec.get("watchdog") or {}).get("trigger_sources") or []
    if "error_webhook" in sources and target_vps != "vps1":
        raise ValidationError(
            f"watchdog.trigger_sources includes 'error_webhook' but target_vps={target_vps!r}: "
            "GlitchTip (vps1) cannot reach a :8889 ingest on another host over the per-host "
            "fabrik bridge. Deploy on vps1, or drop 'error_webhook' from trigger_sources.",
            field="watchdog.trigger_sources",
        )


class DeploymentOrchestrator:
    """Unified orchestrator for end-to-end deployments.

    Handles: validation → secrets → provisioning → deploy → verify → rollback
    """

    def __init__(
        self,
        validator: SpecValidator | None = None,
        secrets_manager: SecretsManager | None = None,
        deployer: SSHDeployer | None = None,
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
        self.deployer = deployer or SSHDeployer()
        self.verifier = verifier or DeploymentVerifier()
        self.rollback_manager = rollback_manager or RollbackManager()
        self.infrastructure_provisioner = infrastructure_provisioner or InfrastructureProvisioner(
            deployer=self.deployer
        )

    def deploy(
        self,
        spec_path: Path,
        dry_run: bool = False,
        skip_health_check: bool = False,
        keep_on_failure: bool = False,
        target_vps: str | None = None,
    ) -> DeploymentContext:
        """Run full deployment pipeline.

        Args:
            spec_path: Path to spec YAML file
            dry_run: If True, simulate without making changes
            skip_health_check: If True, skip health check verification (useful for initial deployments)
            keep_on_failure: B27 — when True, do NOT roll back created resources
                on failure. The deployed app, DNS records, GlitchTip project,
                etc. all stay in place. Used by the proof-run harness so build
                logs and container state survive long enough to be inspected.
                Default ``False`` preserves the production fail-closed behavior.
            target_vps: Which host to deploy the application to (W-Multi M4).
                Overrides the spec's ``target_vps`` field if set. Falls back to
                spec value, then to "vps1" (hub). Hub-side registrars stay on
                vps1 regardless — only the application deploy is routed.

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

            # Resolve target_vps: CLI flag > spec field > default vps1.
            # The env-swap for FABRIK_VPS_SSH_HOST is NOT done here at the
            # pipeline level (W14 hoist was reverted 2026-06-02): hub-side
            # registrars (gatus on vps1, postgres-main on vps1, authelia on
            # vps1) would then SSH to the spoke and fail. Only the calls
            # that target the app's location (SSHDeployer.deploy, inject_env)
            # swap; they read ctx.target_vps themselves.
            ctx.target_vps = target_vps or spec.get("target_vps") or "vps1"
            # Phase 2: fail closed on cross-host error_webhook (unreachable :8889).
            _assert_error_webhook_colocated(spec, ctx.target_vps)
            for w in warnings:
                logger.warning("Validation warning: %s", w)

            # Step 2: Load secrets
            self._load_secrets(ctx, spec)

            # Step 2b: For init-at-boot images (deploy.db_before_boot), provision the
            # DB + seed DATABASE_URL into ctx.secrets BEFORE the first container boot,
            # so the initial .env carries it. Closes deploy-plan-review finding D1
            # (2026-08-28): start-from-init-style images crash on an empty DSN and the
            # deploy rolls back before the post-deploy registrar ever injects it.
            self._pre_provision_db_for_boot(ctx, spec)

            # Step 3: Provision (DNS)
            self._transition(ctx, DeploymentState.PROVISIONING)
            logger.info("Provisioning resources for %s", spec["name"])
            self._provision_dns(ctx, spec)

            # Step 4: Deploy
            self._transition(ctx, DeploymentState.DEPLOYING)
            self.deployer.deploy(ctx)

            # Step 4b: Provision infrastructure registrars (post-deploy).
            # Must run AFTER deployer.deploy so ctx.app_name is set
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
            self._persist_state(ctx, spec)
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

    def _warn_fabricated_secrets(self, keys: list) -> None:
        """Warn for each REQUIRED secret that is absent and will be auto-generated.

        Never raises and never blocks the deploy — a generated password is legitimate. It exists so
        an absent API key/token/DSN cannot be replaced by a random string in silence (found while
        making /opt/seo deploy-ready, 2026-08-07: KILO_API_KEY + DNS_MANAGER_TOKEN would each have
        been fabricated, producing a green deploy with two dead integrations).
        """
        try:
            missing = self.secrets_manager.get_missing([k for k in keys if isinstance(k, str)])
        except Exception:  # noqa: BLE001 — a warning path must never break a deploy
            return
        for key in missing:
            logger.warning(
                "SECRET %s is required but absent from the environment and .env — a RANDOM value "
                "will be generated. Correct for a self-defined password; WRONG for an API key, "
                "token, or DSN that must match an external system (the deploy will look green "
                "while that integration is dead). Add the real value to /opt/fabrik/.env.",
                key,
            )

    def _pre_provision_db_for_boot(self, ctx: DeploymentContext, spec: dict) -> None:
        """Create the DB + seed ``DATABASE_URL`` BEFORE the first container boot.

        Opt-in via ``deploy.db_before_boot: true``. Init-at-boot images (Zitadel
        ``start-from-init``) run migrations synchronously at startup and need the DB
        reachable then — but the postgres registrar injects ``DATABASE_URL`` only
        post-deploy (:meth:`deploy` step 4b), so the container's first boot has an
        empty DSN, crashes, and the deploy rolls back before the registrar runs
        (deploy-plan-review 2026-08-28 finding D1). Here we create the DB + role now
        and seed the DSN into ``ctx.secrets`` so :meth:`SSHDeployer._build_env_content`
        writes it into the INITIAL ``.env``. The post-deploy registrar's
        ``create_database`` is idempotent (DB exists → no password returned → the
        ``.env`` value is preserved by the merge), so this does not double-provision.
        A service WITHOUT the flag is completely unaffected — strict no-op.
        """
        deploy_cfg = spec.get("deploy") or {}
        if not (isinstance(deploy_cfg, dict) and deploy_cfg.get("db_before_boot")):
            return
        if not (spec.get("shape") or {}).get("needs_database"):
            return
        from fabrik.drivers.postgres import create_database
        from fabrik.orchestrator.infrastructure import _rewrite_shared_infra_host

        name = spec.get("id") or spec.get("name")
        # Mirror the postgres registrar's db-name derivation (infrastructure.py
        # _provision_postgres) so the pre-provisioned DB is the SAME one the
        # post-deploy registrar later sees as already existing.
        depends = spec.get("depends", {}) or {}
        db_name = depends.get("postgres") or str(name).replace("-", "_")
        spec_dir = ctx.spec_path.parent if ctx.spec_path else None
        result = create_database(
            db_name,
            db_user=db_name,
            dry_run=ctx.dry_run,
            spec_id=name,
            owner="fabrik",
            spec_dir=spec_dir,
            seed_relpath=depends.get("postgres_seed"),
        )
        password = result.get("password")
        if password and not ctx.dry_run:
            database_url = f"postgresql://{db_name}:{password}@postgres-main:5432/{db_name}"  # noqa: password is a runtime CSPRNG value from create_database, not a hardcoded secret
            database_url = _rewrite_shared_infra_host(
                database_url, getattr(ctx, "target_vps", None)
            )
            ctx.secrets["DATABASE_URL"] = database_url
            logger.info("db_before_boot: seeded DATABASE_URL for %s before first boot", db_name)

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
            self._warn_fabricated_secrets(secrets_config)
            ctx.secrets = self.secrets_manager.load_all(secrets_config)
            return

        if not isinstance(secrets_config, dict):
            return

        all_secrets: dict[str, str] = {}

        required = secrets_config.get("required", [])
        if required:
            # A REQUIRED secret that is absent gets a random value invented for it
            # (`SecretsManager.get(generate_if_missing=True)`). That is correct for a password the
            # service defines itself, and WRONG for anything that must match an external system —
            # an API key, a token, a DSN — where the deploy then goes green while the integration
            # is silently dead. Loud, itemised warning; still non-fatal (a generated password is a
            # legitimate use), so the operator sees it instead of debugging a 401 later.
            self._warn_fabricated_secrets(required)
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
          3. Resolve ``ctx.app_name`` from the live VPS state
             matched on spec name (with the conventional ``fabrik-`` prefix
             tried as a fallback).
          4. Call ``InfrastructureProvisioner.provision(ctx)``.

        Skipped vs :meth:`deploy`: DNS provisioning, ``SSHDeployer.deploy``,
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
            ProvisioningError: App not found on VPS, or any registrar
                raises (notably the GlitchTip DSN-injection verifier).
        """
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
                "Spec is missing both 'name' and 'id' — cannot resolve app.",
                resource_type="infrastructure",
            )

        # Try exact name first, then fabrik- prefix fallback
        existing = self.deployer.find_existing(spec_name)
        if not existing:
            existing = self.deployer.find_existing(f"fabrik-{spec_name}")
        if not existing:
            raise ProvisioningError(
                f"No compose app found at /opt/{spec_name}/ or /opt/fabrik-{spec_name}/",
                resource_type="infrastructure",
            )
        ctx.app_name = existing["name"]  # stores app name, not UUID
        ctx.deployed_url = f"https://{spec['domain']}" if spec.get("domain") else None
        logger.info("refresh_infrastructure: matched %s -> %s", spec_name, ctx.app_name)

        try:
            self.infrastructure_provisioner.provision(ctx)
        except Exception as e:
            raise ProvisioningError(
                f"Infrastructure refresh failed: {e}",
                resource_type="infrastructure",
            ) from e

        self._persist_state(ctx, spec)
        return ctx

    def _persist_state(self, ctx: DeploymentContext, spec: dict[str, Any]) -> None:
        # Write .fabrik/state/<id>.json with the 8-field G-F3 schema. Failure
        # is logged but never raised — state files are best-effort metadata,
        # not load-bearing for the orchestrator success path.
        try:
            spec_id = spec.get("id") or spec.get("name")
            if not spec_id:
                logger.warning("state.save: spec has no id/name; skipping")
                return
            registrars_applied = [
                {
                    "type": r.resource_type,
                    "id": r.resource_id,
                    "status": r.metadata.get("status", "applied"),
                }
                for r in ctx.created_resources
                if r.resource_type in _REGISTRAR_ORDER
            ]
            state_module.save(
                spec_id,
                spec_path=str(ctx.spec_path),
                spec_hash=ctx.spec_hash,
                coolify_uuid=ctx.app_name,
                coolify_app_name=spec.get("name") or spec.get("id") or "",
                registrars_applied=registrars_applied,
                domain=spec.get("domain") or "",
                target_vps=getattr(ctx, "target_vps", None) or "vps1",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("state.save failed (non-fatal): %s", e)

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

        # W-Multi M4 — route DNS to the right host IP based on ctx.target_vps.
        # Precedence: ctx.target_vps (set by spec or --target-vps) wins, since
        # a spoke deploy explicitly targets a different host than vps1.
        # VPS_IP env var is a final fallback for one-off overrides (tests).
        VPS_IPS = {  # noqa: N806 — constant-style lookup table, uppercase intentional
            "vps1": "172.93.160.197",
            "vps2": "96.9.214.128",
            "vps3": "104.128.190.151",
        }
        vps_ip = VPS_IPS.get(ctx.target_vps) or os.getenv("VPS_IP") or VPS_IPS["vps1"]

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
