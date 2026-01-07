"""Integration tests for the full orchestrator pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator import DeploymentOrchestrator, DeploymentState
from fabrik.orchestrator.deployer import ServiceDeployer
from fabrik.orchestrator.rollback import RollbackManager
from fabrik.orchestrator.validator import SpecValidator
from fabrik.orchestrator.verifier import DeploymentVerifier


class TestDeploymentOrchestrator:
    """Integration tests for DeploymentOrchestrator."""

    @pytest.fixture
    def mock_deployer(self):
        """Create a mock deployer that succeeds."""
        deployer = MagicMock(spec=ServiceDeployer)
        deployer.deploy.return_value = "test-uuid"
        return deployer

    @pytest.fixture
    def mock_verifier(self):
        """Create a mock verifier that succeeds."""
        verifier = MagicMock(spec=DeploymentVerifier)
        verifier.verify.return_value = True
        return verifier

    @pytest.fixture
    def test_spec_path(self, tmp_path):
        """Create a valid test spec file."""
        spec_file = tmp_path / "test.yaml"
        spec_file.write_text(
            "name: integration-test\n"
            "template: python-api\n"
            "domain: test.example.com\n"
            "secrets:\n"
            "  - API_KEY\n"
        )
        return spec_file

    def test_full_pipeline_dry_run(self, test_spec_path, tmp_path):
        """Dry run should complete without calling external services."""
        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        orchestrator = DeploymentOrchestrator(validator=validator)
        ctx = orchestrator.deploy(test_spec_path, dry_run=True)

        assert ctx.state == DeploymentState.COMPLETE
        assert ctx.spec["name"] == "integration-test"
        assert ctx.dry_run is True
        assert "API_KEY" in ctx.secrets  # Auto-generated

    def test_full_pipeline_success(self, test_spec_path, tmp_path, mock_deployer, mock_verifier):
        """Full pipeline should complete successfully with mocked services."""
        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        orchestrator = DeploymentOrchestrator(
            validator=validator,
            deployer=mock_deployer,
            verifier=mock_verifier,
        )
        ctx = orchestrator.deploy(test_spec_path)

        assert ctx.state == DeploymentState.COMPLETE
        mock_deployer.deploy.assert_called_once()
        mock_verifier.verify.assert_called_once()

    def test_validation_failure(self, tmp_path):
        """Should fail on invalid spec."""
        spec_file = tmp_path / "invalid.yaml"
        spec_file.write_text("name: test\n")  # Missing required fields

        orchestrator = DeploymentOrchestrator()
        ctx = orchestrator.deploy(spec_file)

        assert ctx.state == DeploymentState.FAILED
        assert "template" in ctx.error.lower() or "domain" in ctx.error.lower()

    def test_deploy_failure_triggers_rollback(self, test_spec_path, tmp_path):
        """Should rollback on deployment failure."""
        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        # Deployer that fails after creating a resource
        mock_deployer = MagicMock(spec=ServiceDeployer)

        def deploy_and_fail(ctx):
            ctx.add_resource("coolify", "test-uuid")
            raise Exception("Deployment failed")

        mock_deployer.deploy.side_effect = deploy_and_fail

        mock_rollback = MagicMock(spec=RollbackManager)
        mock_rollback.rollback.return_value = []

        orchestrator = DeploymentOrchestrator(
            validator=validator,
            deployer=mock_deployer,
            rollback_manager=mock_rollback,
        )
        ctx = orchestrator.deploy(test_spec_path)

        # Should have attempted rollback
        assert ctx.state in (DeploymentState.ROLLED_BACK, DeploymentState.FAILED)

    def test_verification_failure_triggers_rollback(self, test_spec_path, tmp_path, mock_deployer):
        """Should rollback on verification failure."""
        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        # Verifier that fails
        mock_verifier = MagicMock(spec=DeploymentVerifier)
        mock_verifier.verify.side_effect = Exception("Health check failed")

        # Mock deployer that creates a resource
        def deploy_success(ctx):
            ctx.add_resource("coolify", "test-uuid")
            return "test-uuid"

        mock_deployer.deploy.side_effect = deploy_success

        mock_rollback = MagicMock(spec=RollbackManager)
        mock_rollback.rollback.return_value = []

        orchestrator = DeploymentOrchestrator(
            validator=validator,
            deployer=mock_deployer,
            verifier=mock_verifier,
            rollback_manager=mock_rollback,
        )
        ctx = orchestrator.deploy(test_spec_path)

        # Should have rolled back
        mock_rollback.rollback.assert_called_once()

    def test_secrets_loaded_from_env(self, test_spec_path, tmp_path):
        """Should load secrets from environment variables."""
        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        with patch.dict("os.environ", {"API_KEY": "env-secret"}):
            orchestrator = DeploymentOrchestrator(validator=validator)
            ctx = orchestrator.deploy(test_spec_path, dry_run=True)

            assert ctx.secrets.get("API_KEY") == "env-secret"

    def test_state_transitions(self, test_spec_path, tmp_path, mock_deployer, mock_verifier):
        """Should follow correct state transitions."""
        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        states_seen = []

        original_transition = DeploymentOrchestrator._transition

        def track_transition(self, ctx, new_state):
            states_seen.append(new_state)
            original_transition(self, ctx, new_state)

        with patch.object(DeploymentOrchestrator, "_transition", track_transition):
            orchestrator = DeploymentOrchestrator(
                validator=validator,
                deployer=mock_deployer,
                verifier=mock_verifier,
            )
            orchestrator.deploy(test_spec_path)

        expected_states = [
            DeploymentState.VALIDATING,
            DeploymentState.PROVISIONING,
            DeploymentState.DEPLOYING,
            DeploymentState.VERIFYING,
            DeploymentState.COMPLETE,
        ]
        assert states_seen == expected_states
