"""Tests for `fabrik content` CLI command group.

Uses click.testing.CliRunner with mocked ContentPublisher.
"""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from fabrik.cli import cli
from fabrik.orchestrator.content_publisher import PublishContext


@patch("fabrik.cli.ContentPublisher", create=True)
def test_content_publish_help(mock_publisher_cls):
    """'fabrik content publish --help' exits 0 and shows DOMAIN in output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["content", "publish", "--help"])

    assert result.exit_code == 0
    assert "DOMAIN" in result.output


@patch("fabrik.orchestrator.content_publisher.SEOClient")
@patch("fabrik.orchestrator.content_publisher.TCOClient")
@patch("fabrik.orchestrator.content_publisher.ImageBrokerClient")
def test_content_publish_pipeline_error(mock_ib, mock_tco, mock_seo):
    """'fabrik content publish' with pipeline error exits 1 with error output."""
    # Make SEO client raise on get_site_by_domain to trigger pipeline failure
    mock_seo_instance = MagicMock()
    mock_seo.return_value = mock_seo_instance
    mock_seo_instance.get_site_by_domain.side_effect = Exception("Connection refused")

    mock_tco.return_value = MagicMock()
    mock_ib.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(cli, ["content", "publish", "bad.com", "test topic"])

    # Should fail with non-zero exit (either from error list or exception)
    assert result.exit_code != 0


@patch("fabrik.orchestrator.content_publisher.SEOClient")
@patch("fabrik.orchestrator.content_publisher.TCOClient")
@patch("fabrik.orchestrator.content_publisher.ImageBrokerClient")
def test_content_publish_dry_run_flag(mock_ib, mock_tco, mock_seo):
    """'fabrik content publish --dry-run' shows dry run warnings and exits 0."""
    mock_seo_instance = MagicMock()
    mock_seo.return_value = mock_seo_instance
    mock_seo_instance.get_site_by_domain.return_value = {
        "site_id": "s1",
        "domain": "example.com",
    }
    mock_seo_instance.create_job.return_value = {"id": "j1"}
    mock_seo_instance.list_ready_briefs.return_value = [
        {"brief_id": "b1", "job_id": "j1", "page_record": {}}
    ]
    mock_seo_instance.get_brief.return_value = {
        "brief_id": "b1",
        "job_id": "j1",
        "page_record": {},
    }

    mock_tco.return_value = MagicMock()
    mock_ib.return_value = MagicMock()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["content", "publish", "example.com", "test topic", "--dry-run"],
    )

    # Dry run should complete successfully
    assert result.exit_code == 0
    # Should mention dry run in warnings
    assert "dry run" in result.output.lower() or "Dry run" in result.output
