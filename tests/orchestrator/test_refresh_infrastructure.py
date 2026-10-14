"""G2 regression: DeploymentOrchestrator.refresh_infrastructure().

Closes DEPLOYMENT.md §9.9 G2 — re-run only the InfrastructureProvisioner
against an existing compose app, without DNS provisioning, code rebuild,
or post-deploy verification.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator import DeploymentOrchestrator, ProvisioningError


@pytest.fixture
def spec_path(tmp_path):
    p = tmp_path / "svc.yaml"
    p.write_text(
        "name: refresh-test\n"
        "template: python-api\n"
        "domain: refresh-test.example.com\n"
        "shape:\n"
        "  needs_database: false\n"
    )
    return p


@pytest.fixture
def orchestrator():
    """Orchestrator with stubbed validator + provisioner + deployer."""
    orch = DeploymentOrchestrator()

    # Stub validator so we don't have to satisfy full spec schema.
    orch.validator = MagicMock()
    orch.validator.load_and_validate.return_value = (
        {"name": "refresh-test", "id": "refresh-test", "domain": "refresh-test.example.com"},
        "spec-hash-abc",
        [],  # warnings
    )
    # Stub provisioner so we can assert it's called.
    orch.infrastructure_provisioner = MagicMock()
    # Stub deployer so probe_app doesn't do real SSH.
    orch.deployer = MagicMock()
    return orch


def _probes(by_path):
    """A ``probe_app`` stub keyed by PATH; an unlisted path is absent."""
    absent = {"exists": False, "ps": "", "error": None}
    return lambda path: by_path.get(path, absent)


PRESENT = {"exists": True, "ps": "", "error": None}


class TestRefreshInfrastructure:
    """Validate the refresh-only flow."""

    def test_resolves_uuid_and_calls_provisioner(self, orchestrator, spec_path):
        orchestrator.deployer.probe_app.side_effect = _probes({"/opt/refresh-test": PRESENT})

        ctx = orchestrator.refresh_infrastructure(spec_path=spec_path)

        assert ctx.coolify_uuid == "refresh-test"
        assert ctx.spec_hash == "spec-hash-abc"
        assert ctx.deployed_url == "https://refresh-test.example.com"
        orchestrator.infrastructure_provisioner.provision.assert_called_once_with(ctx)

    def test_falls_back_to_fabrik_prefix(self, orchestrator, spec_path):
        """Apps may live under /opt/fabrik-<name>/ on the VPS."""
        orchestrator.deployer.probe_app.side_effect = _probes({"/opt/fabrik-refresh-test": PRESENT})

        ctx = orchestrator.refresh_infrastructure(spec_path=spec_path)

        assert ctx.coolify_uuid == "fabrik-refresh-test"

    def test_raises_when_app_not_found(self, orchestrator, spec_path):
        orchestrator.deployer.probe_app.side_effect = _probes({})

        with pytest.raises(
            ProvisioningError,
            match=(
                "No compose app found on vps1: no compose.yaml in "
                "/opt/refresh-test/ or /opt/fabrik-refresh-test/"
            ),
        ):
            orchestrator.refresh_infrastructure(spec_path=spec_path)

        orchestrator.infrastructure_provisioner.provision.assert_not_called()

    def test_skips_dns_and_deploy(self, orchestrator, spec_path):
        """Refresh must not touch DNS, the deployer.deploy, or the verifier."""
        orchestrator.deployer.probe_app.side_effect = _probes({"/opt/refresh-test": PRESENT})
        orchestrator.verifier = MagicMock()

        with patch.object(orchestrator, "_provision_dns") as mock_dns:
            orchestrator.refresh_infrastructure(spec_path=spec_path)

        mock_dns.assert_not_called()
        orchestrator.deployer.deploy.assert_not_called()
        orchestrator.verifier.verify.assert_not_called()

    def test_provisioner_failure_wrapped_as_provisioning_error(self, orchestrator, spec_path):
        orchestrator.deployer.probe_app.side_effect = _probes({"/opt/refresh-test": PRESENT})
        orchestrator.infrastructure_provisioner.provision.side_effect = RuntimeError("boom")

        with pytest.raises(ProvisioningError, match="Infrastructure refresh failed"):
            orchestrator.refresh_infrastructure(spec_path=spec_path)
