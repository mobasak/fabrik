"""Tests for deployment state machine."""

from fabrik.orchestrator.states import VALID_TRANSITIONS, DeploymentState, can_transition


class TestDeploymentState:
    """Test DeploymentState enum."""

    def test_all_states_exist(self):
        """Verify all expected states exist."""
        expected = [
            "PENDING",
            "VALIDATING",
            "PROVISIONING",
            "DEPLOYING",
            "VERIFYING",
            "COMPLETE",
            "FAILED",
            "ROLLING_BACK",
            "ROLLED_BACK",
        ]
        actual = [s.name for s in DeploymentState]
        assert set(actual) == set(expected)

    def test_initial_state_is_pending(self):
        """Deployment should start in PENDING state."""
        assert DeploymentState.PENDING.value == 1


class TestStateTransitions:
    """Test state transition validation."""

    def test_pending_to_validating(self):
        """Can transition from PENDING to VALIDATING."""
        assert can_transition(DeploymentState.PENDING, DeploymentState.VALIDATING)

    def test_pending_cannot_skip_to_deploying(self):
        """Cannot skip from PENDING directly to DEPLOYING."""
        assert not can_transition(DeploymentState.PENDING, DeploymentState.DEPLOYING)

    def test_validating_to_failed(self):
        """Can transition from VALIDATING to FAILED."""
        assert can_transition(DeploymentState.VALIDATING, DeploymentState.FAILED)

    def test_deploying_to_rolling_back(self):
        """Can transition from DEPLOYING to ROLLING_BACK."""
        assert can_transition(DeploymentState.DEPLOYING, DeploymentState.ROLLING_BACK)

    def test_complete_is_terminal(self):
        """COMPLETE is a terminal state with no transitions."""
        assert VALID_TRANSITIONS[DeploymentState.COMPLETE] == []

    def test_failed_is_terminal(self):
        """FAILED is a terminal state with no transitions."""
        assert VALID_TRANSITIONS[DeploymentState.FAILED] == []

    def test_rolled_back_is_terminal(self):
        """ROLLED_BACK is a terminal state with no transitions."""
        assert VALID_TRANSITIONS[DeploymentState.ROLLED_BACK] == []

    def test_rolling_back_to_rolled_back(self):
        """Can transition from ROLLING_BACK to ROLLED_BACK."""
        assert can_transition(DeploymentState.ROLLING_BACK, DeploymentState.ROLLED_BACK)

    def test_verifying_to_complete(self):
        """Can transition from VERIFYING to COMPLETE."""
        assert can_transition(DeploymentState.VERIFYING, DeploymentState.COMPLETE)
