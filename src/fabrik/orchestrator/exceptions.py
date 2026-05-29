"""Typed exceptions for the orchestrator."""

from typing import Any


class DeploymentError(Exception):
    """Base exception for deployment failures."""

    def __init__(self, message: str, step: str | None = None):
        super().__init__(message)
        self.step = step


class ValidationError(DeploymentError):
    """Spec validation failed."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, step="validation")
        self.field = field


class ProvisioningError(DeploymentError):
    """Resource provisioning failed (DNS, etc.)."""

    def __init__(self, message: str, resource_type: str | None = None):
        super().__init__(message, step="provisioning")
        self.resource_type = resource_type


class DeployError(DeploymentError):
    """Deployment failed."""

    def __init__(self, message: str, detail: str | None = None, **kwargs: Any):
        super().__init__(message, step="deploying")
        self.detail = detail
        # Backward compat: accept coolify_error= kwarg from legacy callers
        if "coolify_error" in kwargs:
            self.detail = self.detail or kwargs["coolify_error"]


class VerificationError(DeploymentError):
    """Post-deployment verification failed."""

    def __init__(self, message: str, check_type: str | None = None):
        super().__init__(message, step="verifying")
        self.check_type = check_type


class RollbackError(DeploymentError):
    """Rollback failed."""

    def __init__(self, message: str, resource_type: str | None = None):
        super().__init__(message, step="rolling_back")
        self.resource_type = resource_type


class InvalidStateTransitionError(DeploymentError):
    """Invalid state machine transition attempted."""

    def __init__(self, from_state: str, to_state: str):
        message = f"Invalid state transition: {from_state} -> {to_state}"
        super().__init__(message, step="state_transition")
        self.from_state = from_state
        self.to_state = to_state
