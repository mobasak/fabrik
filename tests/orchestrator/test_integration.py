"""Integration tests for the full orchestrator pipeline."""

from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator import DeploymentOrchestrator, DeploymentState
from fabrik.orchestrator.deployer_ssh import SSHDeployer
from fabrik.orchestrator.rollback import RollbackManager
from fabrik.orchestrator.validator import SpecValidator
from fabrik.orchestrator.verifier import DeploymentVerifier


class TestDeploymentOrchestrator:
    """Integration tests for DeploymentOrchestrator."""

    @pytest.fixture(autouse=True)
    def _bypass_dns_resolution(self):
        """Bypass DNS resolution and DNS API calls for test domains."""
        mock_dns = MagicMock()
        mock_dns.add_subdomain.return_value = {"success": True}
        with (
            patch("fabrik.orchestrator.validator.is_private_ip", return_value=False),
            patch("fabrik.orchestrator.DNSClient", return_value=mock_dns),
        ):
            yield

    @pytest.fixture
    def mock_deployer(self):
        """Create a mock deployer that succeeds."""
        deployer = MagicMock(spec=SSHDeployer)
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
        mock_deployer = MagicMock(spec=SSHDeployer)

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
        orchestrator.deploy(test_spec_path)

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

    def test_deploy_creates_dns_record(
        self, test_spec_path, tmp_path, mock_deployer, mock_verifier
    ):
        """When spec has a domain, a DNS resource is added to ctx.created_resources."""
        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        mock_dns_client = MagicMock()
        mock_dns_client.add_subdomain.return_value = {"success": True}

        # W-Multi M4: ctx.target_vps maps to a fleet IP (vps1 = 172.93.160.197
        # by default). The VPS_IP env var is now a fallback used only when
        # target_vps is not a known fleet alias — kept here for documentation
        # but no longer the primary signal.
        with (
            patch("fabrik.orchestrator.DNSClient", return_value=mock_dns_client),
            patch.dict("os.environ", {"VPS_IP": "1.2.3.4"}),
        ):
            orchestrator = DeploymentOrchestrator(
                validator=validator,
                deployer=mock_deployer,
                verifier=mock_verifier,
            )
            ctx = orchestrator.deploy(test_spec_path)

        assert ctx.state == DeploymentState.COMPLETE
        # Default target_vps="vps1" → 172.93.160.197 (from VPS_IPS map).
        mock_dns_client.add_subdomain.assert_called_once_with(
            "example.com", "test", "172.93.160.197"
        )
        dns_resources = ctx.get_resources_by_type("dns")
        assert len(dns_resources) == 1
        assert dns_resources[0].resource_id == "test.example.com"
        assert ctx.dns_record_id == "test.example.com"

    def test_deploy_skips_dns_when_no_domain(self, tmp_path, mock_deployer, mock_verifier):
        """When spec has no domain, no DNS calls are made."""
        spec_file = tmp_path / "no-domain.yaml"
        spec_file.write_text('name: no-domain-test\ntemplate: python-api\ndomain: ""\n')

        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        with patch("fabrik.orchestrator.DNSClient") as mock_dns_cls:
            orchestrator = DeploymentOrchestrator(
                validator=validator,
                deployer=mock_deployer,
                verifier=mock_verifier,
            )
            ctx = orchestrator.deploy(spec_file)

        mock_dns_cls.assert_not_called()
        assert ctx.get_resources_by_type("dns") == []

    def test_deploy_rollback_includes_dns(self, test_spec_path, tmp_path):
        """When deploy fails after DNS creation, DNS is in the rollback list."""
        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        mock_dns_client = MagicMock()
        mock_dns_client.add_subdomain.return_value = {"success": True}

        # Deployer that fails
        failing_deployer = MagicMock(spec=SSHDeployer)
        failing_deployer.deploy.side_effect = Exception("Deploy crashed")

        mock_rollback = MagicMock(spec=RollbackManager)
        mock_rollback.rollback.return_value = []

        with (
            patch("fabrik.orchestrator.DNSClient", return_value=mock_dns_client),
            patch.dict("os.environ", {"VPS_IP": "1.2.3.4"}),
        ):
            orchestrator = DeploymentOrchestrator(
                validator=validator,
                deployer=failing_deployer,
                rollback_manager=mock_rollback,
            )
            ctx = orchestrator.deploy(test_spec_path)

        # DNS resource should exist in created_resources (for rollback)
        dns_resources = ctx.get_resources_by_type("dns")
        assert len(dns_resources) == 1
        assert dns_resources[0].resource_id == "test.example.com"

        # Rollback should have been called
        mock_rollback.rollback.assert_called_once()
        assert ctx.state in (DeploymentState.ROLLED_BACK, DeploymentState.FAILED)

    def test_full_pipeline_dry_run_id_based_spec(self, tmp_path):
        """Dry run with id-based spec should use validator shim for name."""
        spec_file = tmp_path / "id-spec.yaml"
        spec_file.write_text("id: id-based-app\ntemplate: python-api\ndomain: test.example.com\n")

        validator = SpecValidator(templates_dir=tmp_path)
        (tmp_path / "python-api").mkdir()

        orchestrator = DeploymentOrchestrator(validator=validator)
        ctx = orchestrator.deploy(spec_file, dry_run=True)

        assert ctx.state == DeploymentState.COMPLETE
        assert ctx.spec["name"] == "id-based-app"
        assert ctx.dry_run is True
