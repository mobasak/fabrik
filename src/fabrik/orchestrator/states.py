"""Deployment state machine."""

from enum import Enum, auto


class DeploymentState(Enum):
    """States in the deployment lifecycle."""

    PENDING = auto()
    VALIDATING = auto()
    PROVISIONING = auto()
    DEPLOYING = auto()
    VERIFYING = auto()
    COMPLETE = auto()
    FAILED = auto()
    ROLLING_BACK = auto()
    ROLLED_BACK = auto()


# Valid state transitions
VALID_TRANSITIONS: dict[DeploymentState, list[DeploymentState]] = {
    DeploymentState.PENDING: [DeploymentState.VALIDATING],
    DeploymentState.VALIDATING: [
        DeploymentState.PROVISIONING,
        DeploymentState.FAILED,
    ],
    DeploymentState.PROVISIONING: [
        DeploymentState.DEPLOYING,
        DeploymentState.FAILED,
        DeploymentState.ROLLING_BACK,
    ],
    DeploymentState.DEPLOYING: [
        DeploymentState.VERIFYING,
        DeploymentState.FAILED,
        DeploymentState.ROLLING_BACK,
    ],
    DeploymentState.VERIFYING: [
        DeploymentState.COMPLETE,
        DeploymentState.FAILED,
        DeploymentState.ROLLING_BACK,
    ],
    DeploymentState.COMPLETE: [],
    DeploymentState.FAILED: [],
    DeploymentState.ROLLING_BACK: [
        DeploymentState.ROLLED_BACK,
        DeploymentState.FAILED,
    ],
    DeploymentState.ROLLED_BACK: [],
}


def can_transition(from_state: DeploymentState, to_state: DeploymentState) -> bool:
    """Check if a state transition is valid."""
    return to_state in VALID_TRANSITIONS.get(from_state, [])
