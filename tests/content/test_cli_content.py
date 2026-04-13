"""Tests for `fabrik content` CLI command group.

Uses click.testing.CliRunner with mocked ContentPublisher to avoid
live service calls.
"""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from fabrik.cli import cli
from fabrik.content.orchestrator import PublishResult, PublishSummary


def test_content_publish_help():
    """'fabrik content publish --help' exits 0 and shows DOMAIN in output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["content", "publish", "--help"])

    assert result.exit_code == 0
    assert "DOMAIN" in result.output


@patch("fabrik.orchestrator.content_publisher.SEOClient")
@patch("fabrik.orchestrator.content_publisher.TCOClient")
@patch("fabrik.orchestrator.content_publisher.ImageBrokerClient")
def test_content_publish_pipeline_error(mock_ib, mock_tco, mock_seo):
    """'fabrik content publish' with connection error exits 1."""
    mock_seo_instance = MagicMock()
    mock_seo.return_value = mock_seo_instance
    mock_seo_instance.get_site_by_domain.side_effect = Exception("Connection refused")
    mock_tco.return_value = MagicMock()
    mock_ib.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(cli, ["content", "publish", "bad.com"])

    assert result.exit_code != 0


@patch("fabrik.orchestrator.content_publisher.SEOClient")
@patch("fabrik.orchestrator.content_publisher.TCOClient")
@patch("fabrik.orchestrator.content_publisher.ImageBrokerClient")
def test_content_publish_unknown_domain(mock_ib, mock_tco, mock_seo):
    """'fabrik content publish x.com' exits 1 and prints 'not found' on ValueError."""
    mock_seo_instance = MagicMock()
    mock_seo.return_value = mock_seo_instance
    mock_seo_instance.get_site_by_domain.return_value = None
    mock_tco.return_value = MagicMock()
    mock_ib.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(cli, ["content", "publish", "x.com"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


@patch("fabrik.orchestrator.content_publisher.SEOClient")
@patch("fabrik.orchestrator.content_publisher.TCOClient")
@patch("fabrik.orchestrator.content_publisher.ImageBrokerClient")
def test_content_publish_dry_run_flag(mock_ib, mock_tco, mock_seo):
    """'fabrik content publish --dry-run' shows dry run message and exits 0."""
    mock_seo_instance = MagicMock()
    mock_seo.return_value = mock_seo_instance
    mock_seo_instance.get_site_by_domain.return_value = {"site_id": "s1", "domain": "example.com"}
    mock_seo_instance.list_ready_briefs.return_value = [
        {"brief_id": "b1"},
        {"brief_id": "b2"},
    ]
    mock_seo_instance.claim_brief.side_effect = lambda brief_id, worker_id: {"brief_id": brief_id}
    mock_tco.return_value = MagicMock()
    mock_ib.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(cli, ["content", "publish", "example.com", "--dry-run"])

    assert result.exit_code == 0
    assert "dry run" in result.output.lower() or "Dry run" in result.output
