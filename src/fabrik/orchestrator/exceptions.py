"""Typed exceptions for the orchestrator."""


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
    """Coolify deployment failed."""

    def __init__(self, message: str, coolify_error: str | None = None):
        super().__init__(message, step="deploying")
        self.coolify_error = coolify_error


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
