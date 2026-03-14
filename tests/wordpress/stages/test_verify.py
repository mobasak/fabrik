"""Tests for verify stage."""

import json
import ssl
from pathlib import Path
from unittest.mock import MagicMock, call, patch

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

    # Mock HTTP responses; patch baseline so it doesn't make real network calls
    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
    ):
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
    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
    ):
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

    # Mock httpx.Client to raise RequestError; patch baseline to avoid real network calls
    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
    ):
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

    # Mock HTTP responses; patch baseline to avoid real network calls
    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
    ):
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

    # Mock HTTP responses and capture called URL; patch baseline to avoid real network calls
    called_urls = []

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify._run_baseline_checks", return_value=[]),
    ):
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


# ---------------------------------------------------------------------------
# Helper: create a minimal checks.json in tmp_path/manifests/
# ---------------------------------------------------------------------------


def _make_checks_json(tmp_path: Path, extra: dict | None = None) -> None:
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir(exist_ok=True)
    checks: dict = {"urls": [{"url": "/", "expected_status": 200}]}
    if extra:
        checks.update(extra)
    with open(manifests_dir / "checks.json", "w") as f:
        json.dump(checks, f)


# ---------------------------------------------------------------------------
# Baseline check tests
# ---------------------------------------------------------------------------


def test_baseline_ssl_passes(minimal_spec, mock_wp, mock_api, tmp_path):
    """SSL check passes when connection succeeds; result.success remains True."""
    _make_checks_json(tmp_path)

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped

        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    assert report_path.exists()
    with open(report_path) as f:
        report = json.load(f)

    ssl_check = next(c for c in report["baseline_checks"] if c["name"] == "ssl_cert")
    assert ssl_check["passed"] is True
    assert result.success is True


def test_baseline_ssl_retries(minimal_spec, mock_wp, mock_api, tmp_path):
    """SSL check retries: first 2 attempts raise SSLError, 3rd succeeds."""
    _make_checks_json(tmp_path)

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch(
            "fabrik.wordpress.stages.verify.socket.create_connection",
            return_value=mock_sock,
        ),
        patch("fabrik.wordpress.stages.verify.time.sleep") as mock_sleep,
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        # First 2 calls to wrap_socket raise SSLError; 3rd succeeds
        mock_ctx.wrap_socket.side_effect = [
            ssl.SSLError("handshake error"),
            ssl.SSLError("handshake error"),
            mock_wrapped,
        ]

        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    ssl_check = next(c for c in report["baseline_checks"] if c["name"] == "ssl_cert")
    assert ssl_check["passed"] is True
    assert mock_sleep.call_count == 2


def test_baseline_ssl_fails_after_max_retries(minimal_spec, mock_wp, mock_api, tmp_path):
    """All 5 SSL attempts fail → check passed=False, fatal=True, result.success=False."""
    _make_checks_json(tmp_path, extra={"require_ssl": True})

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch(
            "fabrik.wordpress.stages.verify.socket.create_connection",
            return_value=mock_sock,
        ),
        patch("fabrik.wordpress.stages.verify.time.sleep") as mock_sleep,
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.side_effect = ssl.SSLError("cert verify failed")

        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    ssl_check = next(c for c in report["baseline_checks"] if c["name"] == "ssl_cert")
    assert ssl_check["passed"] is False
    assert ssl_check.get("fatal") is True
    assert result.success is False
    # sleep called 4 times (between attempts 1-2, 2-3, 3-4, 4-5)
    assert mock_sleep.call_count == 4


def test_baseline_sitemap_first_url(minimal_spec, mock_wp, mock_api, tmp_path):
    """/wp-sitemap.xml returns 200 → sitemap check passed=True."""
    _make_checks_json(tmp_path)

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    def sitemap_side_effect(url):
        resp = MagicMock()
        resp.text = "User-agent: *"
        resp.headers = {"location": ""}
        if "/wp-sitemap.xml" in url:
            resp.status_code = 200
        elif "/sitemap_index.xml" in url:
            resp.status_code = 404
        elif "/sitemap.xml" in url:
            resp.status_code = 404
        else:
            resp.status_code = 200
        return resp

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped

        mock_client_cls.return_value.__enter__.return_value.get.side_effect = sitemap_side_effect

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    sitemap_check = next(c for c in report["baseline_checks"] if c["name"] == "sitemap")
    assert sitemap_check["passed"] is True
    assert "/wp-sitemap.xml" in sitemap_check["detail"]


def test_baseline_sitemap_fallback(minimal_spec, mock_wp, mock_api, tmp_path):
    """/wp-sitemap.xml returns 404, /sitemap_index.xml returns 200 → sitemap check passed=True."""
    _make_checks_json(tmp_path)

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    def sitemap_side_effect(url):
        resp = MagicMock()
        resp.text = "User-agent: *"
        resp.headers = {"location": ""}
        if "/wp-sitemap.xml" in url:
            resp.status_code = 404
        elif "/sitemap_index.xml" in url:
            resp.status_code = 200
        elif "/sitemap.xml" in url:
            resp.status_code = 404
        else:
            resp.status_code = 200
        return resp

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped

        mock_client_cls.return_value.__enter__.return_value.get.side_effect = sitemap_side_effect

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    sitemap_check = next(c for c in report["baseline_checks"] if c["name"] == "sitemap")
    assert sitemap_check["passed"] is True
    assert "/sitemap_index.xml" in sitemap_check["detail"]


def test_baseline_sitemap_all_fail(minimal_spec, mock_wp, mock_api, tmp_path):
    """All three sitemap URLs return 404 → sitemap check passed=False, fatal=True, result.success=False."""
    _make_checks_json(tmp_path, extra={"require_sitemap": True})

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    def sitemap_side_effect(url):
        resp = MagicMock()
        resp.text = "User-agent: *"
        resp.headers = {"location": ""}
        if any(p in url for p in ["/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml"]):
            resp.status_code = 404
        else:
            resp.status_code = 200
        return resp

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped

        mock_client_cls.return_value.__enter__.return_value.get.side_effect = sitemap_side_effect

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    sitemap_check = next(c for c in report["baseline_checks"] if c["name"] == "sitemap")
    assert sitemap_check["passed"] is False
    assert sitemap_check.get("fatal") is True
    assert result.success is False


def test_baseline_checks_in_report(minimal_spec, mock_wp, mock_api, tmp_path):
    """verify-report.json contains both 'checks' (URL checks) and 'baseline_checks' keys, both non-empty."""
    _make_checks_json(tmp_path)

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped

        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    assert report_path.exists()
    with open(report_path) as f:
        report = json.load(f)

    assert "checks" in report
    assert "baseline_checks" in report
    assert isinstance(report["checks"], list)
    assert isinstance(report["baseline_checks"], list)
    assert len(report["checks"]) > 0
    assert len(report["baseline_checks"]) > 0


def test_existing_url_checks_unaffected(minimal_spec, mock_wp, mock_api, tmp_path):
    """Passing URL checks and passing baseline: report['checks'] preserves URL entries, overall='pass'."""
    manifests_dir = tmp_path / "manifests"
    manifests_dir.mkdir(exist_ok=True)
    checks_data = {
        "urls": [
            {"url": "/", "expected_status": 200},
            {"url": "/about", "expected_status": 200},
        ],
    }
    with open(manifests_dir / "checks.json", "w") as f:
        json.dump(checks_data, f)

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped

        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    # Original URL checks are preserved
    assert len(report["checks"]) == 2
    for check in report["checks"]:
        assert "url" in check
        assert check["passed"] is True

    assert report["overall"] == "pass"
    assert result.success is True


# ---------------------------------------------------------------------------
# Comment 2: require_ssl / require_sitemap fatality tests
# ---------------------------------------------------------------------------


def test_require_ssl_false_ssl_fail_non_fatal(minimal_spec, mock_wp, mock_api, tmp_path):
    """SSL fails but require_ssl=False → result.success stays True (non-fatal)."""
    _make_checks_json(tmp_path, extra={"require_ssl": False, "require_sitemap": False})

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch(
            "fabrik.wordpress.stages.verify.socket.create_connection",
            return_value=mock_sock,
        ),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        # All SSL attempts fail
        mock_ctx.wrap_socket.side_effect = ssl.SSLError("cert verify failed")

        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    ssl_check = next(c for c in report["baseline_checks"] if c["name"] == "ssl_cert")
    assert ssl_check["passed"] is False
    assert ssl_check.get("fatal") is False
    # Non-fatal failure: result.success should remain True (URL checks all pass)
    assert result.success is True


def test_require_ssl_true_ssl_fail_fatal(minimal_spec, mock_wp, mock_api, tmp_path):
    """SSL fails and require_ssl=True → result.success=False (fatal)."""
    _make_checks_json(tmp_path, extra={"require_ssl": True, "require_sitemap": False})

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch(
            "fabrik.wordpress.stages.verify.socket.create_connection",
            return_value=mock_sock,
        ),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.side_effect = ssl.SSLError("cert verify failed")

        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    ssl_check = next(c for c in report["baseline_checks"] if c["name"] == "ssl_cert")
    assert ssl_check["passed"] is False
    assert ssl_check.get("fatal") is True
    assert result.success is False


def test_require_sitemap_false_sitemap_fail_non_fatal(minimal_spec, mock_wp, mock_api, tmp_path):
    """Sitemap fails but require_sitemap=False → result.success stays True (non-fatal)."""
    _make_checks_json(tmp_path, extra={"require_ssl": False, "require_sitemap": False})

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    def all_fail_side_effect(url):
        resp = MagicMock()
        resp.text = "User-agent: *"
        resp.headers = {"location": ""}
        if any(p in url for p in ["/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml"]):
            resp.status_code = 404
        else:
            resp.status_code = 200
        return resp

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped

        mock_client_cls.return_value.__enter__.return_value.get.side_effect = all_fail_side_effect

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    sitemap_check = next(c for c in report["baseline_checks"] if c["name"] == "sitemap")
    assert sitemap_check["passed"] is False
    assert sitemap_check.get("fatal") is False
    # Non-fatal: URL checks all pass so result.success is True
    assert result.success is True


def test_require_sitemap_true_sitemap_fail_fatal(minimal_spec, mock_wp, mock_api, tmp_path):
    """Sitemap fails and require_sitemap=True → result.success=False (fatal)."""
    _make_checks_json(tmp_path, extra={"require_ssl": False, "require_sitemap": True})

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    def all_fail_side_effect(url):
        resp = MagicMock()
        resp.text = "User-agent: *"
        resp.headers = {"location": ""}
        if any(p in url for p in ["/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml"]):
            resp.status_code = 404
        else:
            resp.status_code = 200
        return resp

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped

        mock_client_cls.return_value.__enter__.return_value.get.side_effect = all_fail_side_effect

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    sitemap_check = next(c for c in report["baseline_checks"] if c["name"] == "sitemap")
    assert sitemap_check["passed"] is False
    assert sitemap_check.get("fatal") is True
    assert result.success is False


# ---------------------------------------------------------------------------
# Comment 3: required_plugins_active validation tests
# ---------------------------------------------------------------------------


def test_required_plugins_all_active(minimal_spec, mock_wp, mock_api, tmp_path):
    """All required plugins present and active → passed=True."""
    _make_checks_json(tmp_path)

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    mock_wp.plugin_list.return_value = [
        {"name": "akismet/akismet", "status": "active"},
        {"name": "hello-dolly/hello", "status": "active"},
    ]

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    plugins_check = next(
        c for c in report["baseline_checks"] if c["name"] == "required_plugins_active"
    )
    assert plugins_check["passed"] is True
    assert plugins_check["detail"] == "All required active"


def test_required_plugins_missing(minimal_spec, mock_wp, mock_api, tmp_path):
    """Required plugin missing from plugin_list → passed=False (non-fatal)."""
    _make_checks_json(tmp_path)

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    # Only akismet returned; hello-dolly missing
    mock_wp.plugin_list.return_value = [
        {"name": "akismet/akismet", "status": "active"},
    ]

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    plugins_check = next(
        c for c in report["baseline_checks"] if c["name"] == "required_plugins_active"
    )
    assert plugins_check["passed"] is False
    assert "hello-dolly/hello" in plugins_check["detail"]
    # Non-fatal: no fatal key or fatal=False
    assert not plugins_check.get("fatal", False)


def test_required_plugins_inactive(minimal_spec, mock_wp, mock_api, tmp_path):
    """Required plugin present but inactive → passed=False (non-fatal)."""
    _make_checks_json(tmp_path)

    ok_response = MagicMock()
    ok_response.status_code = 200
    ok_response.text = "User-agent: *"
    ok_response.headers = {"location": ""}

    mock_sock = MagicMock()
    mock_wrapped = MagicMock()
    mock_wrapped.__enter__ = MagicMock(return_value=mock_wrapped)
    mock_wrapped.__exit__ = MagicMock(return_value=False)

    # Both plugins present but hello-dolly is inactive
    mock_wp.plugin_list.return_value = [
        {"name": "akismet/akismet", "status": "active"},
        {"name": "hello-dolly/hello", "status": "inactive"},
    ]

    with (
        patch("fabrik.wordpress.stages.verify.httpx.Client") as mock_client_cls,
        patch("fabrik.wordpress.stages.verify.socket.getaddrinfo"),
        patch("fabrik.wordpress.stages.verify.ssl.create_default_context") as mock_ctx_cls,
        patch("fabrik.wordpress.stages.verify.socket.create_connection", return_value=mock_sock),
        patch("fabrik.wordpress.stages.verify.time.sleep"),
    ):
        mock_ctx = MagicMock()
        mock_ctx_cls.return_value = mock_ctx
        mock_ctx.wrap_socket.return_value = mock_wrapped
        mock_client_cls.return_value.__enter__.return_value.get.return_value = ok_response

        spec = minimal_spec.copy()
        spec["dry_run"] = False
        result = verify.apply(spec, mock_wp, mock_api, tmp_path)

    report_path = tmp_path / "reports" / "verify-report.json"
    with open(report_path) as f:
        report = json.load(f)

    plugins_check = next(
        c for c in report["baseline_checks"] if c["name"] == "required_plugins_active"
    )
    assert plugins_check["passed"] is False
    assert "hello-dolly/hello" in plugins_check["detail"]
    assert not plugins_check.get("fatal", False)
