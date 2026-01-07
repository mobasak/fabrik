"""Tests for deployment verification."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.orchestrator.context import DeploymentContext
from fabrik.orchestrator.exceptions import VerificationError
from fabrik.orchestrator.verifier import DeploymentVerifier


class TestDeploymentVerifier:
    """Test DeploymentVerifier class."""

    def test_verify_dry_run(self):
        """Dry run should skip actual verification."""
        verifier = DeploymentVerifier()
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test", "domain": "test.com"},
            dry_run=True,
        )

        result = verifier.verify(ctx)
        assert result is True

    def test_verify_uses_healthcheck_path(self):
        """Should use custom healthcheck path from spec."""
        verifier = DeploymentVerifier(max_retries=1)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={
                "name": "test",
                "domain": "test.com",
                "healthcheck": {"path": "/api/health"},
            },
        )

        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            result = verifier.verify(ctx)

            assert result is True
            mock_urlopen.assert_called_once()
            call_url = mock_urlopen.call_args[0][0]
            assert "/api/health" in call_url

    def test_verify_sets_deployed_url(self):
        """Should set deployed_url on context."""
        verifier = DeploymentVerifier(max_retries=1)
        ctx = DeploymentContext(
            spec_path=Path("test.yaml"),
            spec={"name": "test", "domain": "example.com"},
        )

        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_urlopen.return_value = mock_response

            verifier.verify(ctx)

            assert ctx.deployed_url == "https://example.com"

    def test_health_check_retries(self):
        """Should retry on failure."""
        verifier = DeploymentVerifier(max_retries=3, retry_interval=0)

        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200

            # Fail twice, succeed on third
            mock_urlopen.side_effect = [
                Exception("Connection refused"),
                Exception("Timeout"),
                mock_response,
            ]

            result = verifier._check_health("https://test.com/health")
            assert result is True
            assert mock_urlopen.call_count == 3

    def test_health_check_fails_after_max_retries(self):
        """Should raise VerificationError after max retries."""
        verifier = DeploymentVerifier(max_retries=2, retry_interval=0)

        with patch("fabrik.orchestrator.verifier.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = Exception("Connection refused")

            with pytest.raises(VerificationError) as exc:
                verifier._check_health("https://test.com/health")

            assert "2 attempts" in str(exc.value)
            assert exc.value.check_type == "health"
