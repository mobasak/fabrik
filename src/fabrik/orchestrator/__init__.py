"""Fabrik Deployment Orchestrator.

Unified controller for end-to-end deployments.
"""

import logging
from pathlib import Path

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.deployer import ServiceDeployer
from fabrik.orchestrator.exceptions import (
    DeployError,
    DeploymentError,
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
    ):
        """Initialize orchestrator with optional component overrides."""
        self.validator = validator or SpecValidator()
        self.secrets_manager = secrets_manager or SecretsManager()
        self.deployer = deployer or ServiceDeployer()
        self.verifier = verifier or DeploymentVerifier()
        self.rollback_manager = rollback_manager or RollbackManager()

    def deploy(self, spec_path: Path, dry_run: bool = False) -> DeploymentContext:
        """Run full deployment pipeline.

        Args:
            spec_path: Path to spec YAML file
            dry_run: If True, simulate without making changes

        Returns:
            DeploymentContext with results
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
            secret_keys = spec.get("secrets", [])
            if secret_keys:
                ctx.secrets = self.secrets_manager.load_all(secret_keys)

            # Step 3: Provision (DNS) - TODO: implement provisioner
            self._transition(ctx, DeploymentState.PROVISIONING)
            logger.info("Provisioning resources for %s", spec["name"])
            # DNS provisioning would go here

            # Step 4: Deploy
            self._transition(ctx, DeploymentState.DEPLOYING)
            self.deployer.deploy(ctx)

            # Step 5: Verify
            self._transition(ctx, DeploymentState.VERIFYING)
            self.verifier.verify(ctx)

            # Success
            self._transition(ctx, DeploymentState.COMPLETE)
            logger.info("Deployment complete: %s", ctx.deployed_url or spec["domain"])

        except (ValidationError, DeployError, VerificationError) as e:
            ctx.error = str(e)
            ctx.error_step = e.step if hasattr(e, "step") else None
            logger.error("Deployment failed at %s: %s", ctx.error_step, e)

            # Attempt rollback
            if ctx.created_resources:
                self._transition(ctx, DeploymentState.ROLLING_BACK)
                errors = self.rollback_manager.rollback(ctx)
                if errors:
                    self._transition(ctx, DeploymentState.FAILED)
                else:
                    self._transition(ctx, DeploymentState.ROLLED_BACK)
            else:
                self._transition(ctx, DeploymentState.FAILED)

        except Exception as e:
            ctx.error = str(e)
            logger.exception("Unexpected error during deployment")

            # Attempt rollback for unexpected errors too
            if ctx.created_resources:
                self._transition(ctx, DeploymentState.ROLLING_BACK)
                errors = self.rollback_manager.rollback(ctx)
                if errors:
                    self._transition(ctx, DeploymentState.FAILED)
                else:
                    self._transition(ctx, DeploymentState.ROLLED_BACK)
            else:
                self._transition(ctx, DeploymentState.FAILED)

        return ctx

    def _transition(self, ctx: DeploymentContext, new_state: DeploymentState) -> None:
        """Transition to a new state with validation."""
        if ctx.state != new_state:
            if not can_transition(ctx.state, new_state):
                logger.warning(
                    "Invalid state transition: %s -> %s",
                    ctx.state.name,
                    new_state.name,
                )
            ctx.state = new_state
            logger.debug("State: %s", new_state.name)
