"""Tests for DNS stage."""

from unittest.mock import MagicMock, patch

from fabrik.wordpress.stages import dns


def test_dns_dry_run(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test DNS stage in dry-run mode."""
    result = dns.apply(minimal_spec, mock_wp, mock_api, tmp_path)

    assert result.success
    assert len(result.errors) == 0
    assert result.name == "dns"
    assert result.duration_ms >= 0


def test_dns_missing_vps_ip_fails(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test DNS stage fails even in dry-run when VPS_IP missing."""
    spec = minimal_spec.copy()
    spec["deployment"] = {}
    spec["dry_run"] = True

    result = dns.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert "VPS_IP not configured" in result.errors
    assert len(result.errors) == 1


def test_dns_missing_vps_ip_not_dry_run(minimal_spec, mock_wp, mock_api, tmp_path):
    """Test DNS stage fails when VPS_IP missing and not dry-run."""
    spec = minimal_spec.copy()
    spec["deployment"] = {}
    spec["dry_run"] = False

    result = dns.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert "VPS_IP not configured" in result.errors


@patch("fabrik.wordpress.stages.dns.DomainSetup")
def test_dns_exception(mock_setup_class, minimal_spec, mock_wp, mock_api, tmp_path):
    """Test DNS stage handles exceptions."""
    spec = minimal_spec.copy()
    spec["dry_run"] = False

    mock_setup = MagicMock()
    mock_setup.configure_dns.side_effect = RuntimeError("DNS error")
    mock_setup_class.return_value = mock_setup

    result = dns.apply(spec, mock_wp, mock_api, tmp_path)

    assert not result.success
    assert len(result.errors) > 0
