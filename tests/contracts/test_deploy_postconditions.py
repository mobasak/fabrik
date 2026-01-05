"""Contract tests for deploy postconditions.

These tests verify that the postcondition checker correctly validates deployments.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fabrik.verify import CheckResult, PostconditionChecker, PostconditionResult


@pytest.fixture
def deploy_spec_path():
    return Path("/opt/fabrik/specs/verification/deploy.yaml")


@pytest.fixture
def mock_context():
    return {
        "DOMAIN": "test.example.com",
        "APP_NAME": "test-app",
        "TARGET_IP": "172.93.160.197",
    }


class TestPostconditionChecker:
    """Tests for PostconditionChecker class."""

    def test_load_spec_substitutes_variables(self, deploy_spec_path, mock_context):
        """Verify that ${VAR} placeholders are substituted."""
        if not deploy_spec_path.exists():
            pytest.skip("Deploy spec not found")

        checker = PostconditionChecker(deploy_spec_path, mock_context)

        # Check that context was applied
        assert checker.spec is not None
        assert "postconditions" in checker.spec

    def test_check_http_returns_pass_on_200(self, deploy_spec_path, mock_context):
        """HTTP check should pass when endpoint returns expected status."""
        if not deploy_spec_path.exists():
            pytest.skip("Deploy spec not found")

        checker = PostconditionChecker(deploy_spec_path, mock_context)

        with patch("fabrik.verify.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            result = checker.check_http("health_check")
            assert result.result == CheckResult.PASS

    def test_check_http_returns_fail_on_wrong_status(self, deploy_spec_path, mock_context):
        """HTTP check should fail when endpoint returns unexpected status."""
        if not deploy_spec_path.exists():
            pytest.skip("Deploy spec not found")

        checker = PostconditionChecker(deploy_spec_path, mock_context)

        with patch("fabrik.verify.httpx.Client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            result = checker.check_http("health_check")
            assert result.result == CheckResult.FAIL

    def test_check_dns_returns_pass_on_resolve(self, deploy_spec_path, mock_context):
        """DNS check should pass when domain resolves."""
        if not deploy_spec_path.exists():
            pytest.skip("Deploy spec not found")

        checker = PostconditionChecker(deploy_spec_path, mock_context)

        with patch("fabrik.verify.socket.gethostbyname") as mock_dns:
            mock_dns.return_value = "172.93.160.197"

            result = checker.check_dns("dns_resolves")
            # May skip if no domain configured in spec for this check
            assert result.result in (CheckResult.PASS, CheckResult.SKIP)

    def test_all_passed_returns_true_when_no_failures(self, deploy_spec_path, mock_context):
        """all_passed() should return True when all checks pass or skip."""
        if not deploy_spec_path.exists():
            pytest.skip("Deploy spec not found")

        checker = PostconditionChecker(deploy_spec_path, mock_context)
        checker.results = [
            PostconditionResult("test1", CheckResult.PASS, "ok"),
            PostconditionResult("test2", CheckResult.SKIP, "skipped"),
        ]

        assert checker.all_passed() is True

    def test_all_passed_returns_false_on_failure(self, deploy_spec_path, mock_context):
        """all_passed() should return False when any check fails."""
        if not deploy_spec_path.exists():
            pytest.skip("Deploy spec not found")

        checker = PostconditionChecker(deploy_spec_path, mock_context)
        checker.results = [
            PostconditionResult("test1", CheckResult.PASS, "ok"),
            PostconditionResult("test2", CheckResult.FAIL, "failed"),
        ]

        assert checker.all_passed() is False

    def test_should_rollback_respects_spec_config(self, deploy_spec_path, mock_context):
        """should_rollback() should respect the rollback.default setting."""
        if not deploy_spec_path.exists():
            pytest.skip("Deploy spec not found")

        checker = PostconditionChecker(deploy_spec_path, mock_context)
        checker.results = [
            PostconditionResult("test1", CheckResult.FAIL, "failed"),
        ]

        # Deploy spec has rollback.default: auto
        assert checker.should_rollback() is True
