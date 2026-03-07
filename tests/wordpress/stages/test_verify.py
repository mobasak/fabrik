"""Tests for verify stage."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.wordpress.stages import verify


def test_verify_all_pass(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test verify stage when all checks pass."""
    # Create checks.json manifest
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    checks = {
        "urls": [
            {"url": "/", "expected_status": 200},
            {"url": "/about", "expected_status": 200},
        ]
    }
    checks_path = manifests_dir / "checks.json"
    with open(checks_path, "w") as f:
        json.dump(checks, f)

    # Mock HTTP responses
    with patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert result.name == "verify"
    assert len(result.errors) == 0

    # Verify report written
    verify_report_path = tmp_path / "reports" / "verify-report.json"
    assert verify_report_path.exists()

    with open(verify_report_path, "r") as f:
        report = json.load(f)

    assert report["overall"] == "pass"
    assert len(report["checks"]) == 2
    assert all(c["passed"] for c in report["checks"])
    assert str(verify_report_path) in result.artifacts_written


def test_verify_one_fail(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test verify stage when one check fails."""
    # Create checks.json manifest
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    checks = {
        "urls": [
            {"url": "/", "expected_status": 200},
            {"url": "/missing", "expected_status": 200},
        ]
    }
    checks_path = manifests_dir / "checks.json"
    with open(checks_path, "w") as f:
        json.dump(checks, f)

    # Mock HTTP responses - first passes, second fails
    with patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value

        def get_side_effect(url):
            mock_response = MagicMock()
            if "/missing" in url:
                mock_response.status_code = 404
            else:
                mock_response.status_code = 200
            return mock_response

        mock_client.get.side_effect = get_side_effect

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert result.name == "verify"
    assert len(result.errors) == 1
    assert "expected 200, got 404" in result.errors[0]
    assert "missing" in result.errors[0]

    # Verify report written with failure
    verify_report_path = tmp_path / "reports" / "verify-report.json"
    assert verify_report_path.exists()

    with open(verify_report_path, "r") as f:
        report = json.load(f)

    assert report["overall"] == "fail"
    assert len(report["checks"]) == 2
    assert report["checks"][0]["passed"]
    assert not report["checks"][1]["passed"]


def test_verify_missing_checks_json(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test verify stage fails when checks.json not found."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False
    result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert "checks.json not found" in result.errors


def test_verify_dry_run_skips_http(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test verify stage skips HTTP calls in dry-run mode."""
    # Create checks.json manifest
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    checks = {
        "urls": [
            {"url": "/", "expected_status": 200},
        ]
    }
    checks_path = manifests_dir / "checks.json"
    with open(checks_path, "w") as f:
        json.dump(checks, f)

    # Patch httpx.Client to detect if called
    with patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls:
        spec = minimal_spec.copy()
        spec["dry_run"] = True
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

        # Verify httpx.Client was never instantiated
        mock_client_cls.assert_not_called()

    assert result.success
    assert len(result.errors) == 0

    # Verify report still written
    verify_report_path = tmp_path / "reports" / "verify-report.json"
    assert verify_report_path.exists()


def test_verify_network_error(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test verify stage handles network errors gracefully."""
    # Create checks.json manifest
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    checks = {
        "urls": [
            {"url": "/", "expected_status": 200},
        ]
    }
    checks_path = manifests_dir / "checks.json"
    with open(checks_path, "w") as f:
        json.dump(checks, f)

    # Mock httpx.Client to raise RequestError
    with patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = httpx.RequestError("Connection refused")

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert len(result.errors) == 1
    assert "Connection refused" in result.errors[0]

    # Verify report written with error
    verify_report_path = tmp_path / "reports" / "verify-report.json"
    assert verify_report_path.exists()

    with open(verify_report_path, "r") as f:
        report = json.load(f)

    assert report["overall"] == "fail"
    assert not report["checks"][0]["passed"]
    assert "error" in report["checks"][0]


def test_verify_report_written_correctly(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test verify report has correct JSON schema."""
    # Create checks.json manifest
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    checks = {
        "urls": [
            {"url": "/", "expected_status": 200},
        ]
    }
    checks_path = manifests_dir / "checks.json"
    with open(checks_path, "w") as f:
        json.dump(checks, f)

    # Mock HTTP responses
    with patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    # Validate JSON schema
    verify_report_path = tmp_path / "reports" / "verify-report.json"
    assert verify_report_path.exists()

    with open(verify_report_path, "r") as f:
        report = json.load(f)

    # Required keys
    assert "site_id" in report
    assert "verified_at" in report
    assert "checks" in report
    assert "overall" in report

    # Validate types
    assert isinstance(report["site_id"], str)
    assert isinstance(report["verified_at"], str)
    assert isinstance(report["checks"], list)
    assert report["overall"] in ["pass", "fail"]

    # Validate check structure
    for check in report["checks"]:
        assert "url" in check
        assert "status" in check
        assert "passed" in check
        assert isinstance(check["passed"], bool)


def test_verify_relative_url_prepends_domain(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test verify stage prepends domain to relative URLs."""
    # Create checks.json manifest with relative URL
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir()
    checks = {
        "urls": [
            {"url": "/", "expected_status": 200},
        ]
    }
    checks_path = manifests_dir / "checks.json"
    with open(checks_path, "w") as f:
        json.dump(checks, f)

    # Mock HTTP responses and capture called URL
    called_urls = []

    with patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value

        def capture_url(url):
            called_urls.append(url)
            mock_response = MagicMock()
            mock_response.status_code = 200
            return mock_response

        mock_client.get.side_effect = capture_url

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    # Verify domain was prepended
    assert len(called_urls) == 1
    assert called_urls[0] == "https://test.example.com/"
    assert result.success
