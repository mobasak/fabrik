"""Tests for ContentPublisher orchestrator.

All tests mock SEOClient, TCOClient, ImageBrokerClient, and WordPressAPIClient
to avoid live service calls. Tests verify the pipeline logic in
ContentPublisher.publish_page().
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from fabrik.orchestrator.content_publisher import ContentPublisher, PublishContext


def _make_publisher(
    seo=None,
    tco=None,
    image=None,
    wp=None,
):
    """Create a ContentPublisher with mocked clients."""
    return ContentPublisher(
        seo_client=seo or MagicMock(),
        tco_client=tco or MagicMock(),
        image_client=image or MagicMock(),
        wp_client=wp or MagicMock(),
    )


def _make_site_dict(domain="example.com", site_id="site-1"):
    return {"site_id": site_id, "domain": domain}


def _make_brief_dict(brief_id="brief-1", job_id="job-1"):
    return {
        "brief_id": brief_id,
        "job_id": job_id,
        "page_record": {
            "primary_keyword": "test keyword",
            "page_type": "service",
            "h1": "Test Title",
            "slug": "test-page",
            "meta_description": "Test description",
            "schema": {
                "primary_type": "WebPage",
                "secondary_types": ["FAQPage"],
            },
        },
        "geo": {"country": "us"},
        "content_contract": {},
        "cannibalization_guard": {},
    }


def _make_page_package():
    return {
        "page_payload": {
            "page_type": "service",
            "slug": "test-page",
            "seo_title": "Test SEO Title",
            "meta_description": "Meta desc",
        },
        "rendered_sections": [
            {"type": "hero", "content": "<h2>Hero</h2>"},
            {"type": "body", "content": "<p>Body text</p>"},
        ],
        "json_ld": [{"@type": "WebPage"}],
    }


def test_publish_raises_on_unknown_domain():
    """publish_page records error when SEOClient.get_site_by_domain returns None."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = None
    seo.ensure_site.side_effect = Exception("Site not found")

    publisher = _make_publisher(seo=seo)
    ctx = publisher.publish_page(
        domain="bad.com",
        site_name="Bad Site",
        seed_topic="test",
    )

    assert len(ctx.errors) > 0
    assert "failed" in ctx.errors[0].lower() or "not found" in ctx.errors[0].lower()


def test_publish_skips_on_dry_run():
    """publish_page in dry_run mode adds warnings about skipped steps."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = _make_site_dict()
    seo.create_job.return_value = {"id": "job-1"}
    seo.list_ready_briefs.return_value = [_make_brief_dict()]
    seo.get_brief.return_value = _make_brief_dict()

    publisher = _make_publisher(seo=seo)
    ctx = publisher.publish_page(
        domain="example.com",
        site_name="Example",
        seed_topic="test topic",
        dry_run=True,
    )

    # Dry run should not claim, generate, or publish
    seo.claim_brief.assert_not_called()
    assert any("dry run" in w.lower() for w in ctx.warnings)


def test_publish_pipeline_catches_tco_failure():
    """Pipeline catches TCO failure and records error in context."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = _make_site_dict()
    seo.create_job.return_value = {"id": "job-1"}
    seo.run_job.return_value = {}
    seo.wait_for_job.return_value = {"status": "completed"}
    seo.list_ready_briefs.return_value = [_make_brief_dict()]
    seo.claim_brief.return_value = _make_brief_dict()

    tco = MagicMock()
    tco.generate_from_brief.side_effect = RuntimeError("TCO exploded")

    publisher = _make_publisher(seo=seo, tco=tco)
    ctx = publisher.publish_page(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )

    # Pipeline catches exception, records error
    assert len(ctx.errors) > 0
    assert "failed" in ctx.errors[0].lower()


def test_publish_continues_without_image():
    """Pipeline completes even when ImageBrokerClient.auto_download returns None."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = _make_site_dict()
    seo.create_job.return_value = {"id": "job-1"}
    seo.run_job.return_value = {}
    seo.wait_for_job.return_value = {"status": "completed"}
    seo.list_ready_briefs.return_value = [_make_brief_dict()]
    seo.claim_brief.return_value = _make_brief_dict()

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = None  # No image available

    publisher = _make_publisher(seo=seo, tco=tco, image=image)
    ctx = publisher.publish_page(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )

    # Pipeline should continue — image failure is non-fatal
    assert ctx.page_package is not None
    # Warning about no image
    assert any("image" in w.lower() for w in ctx.warnings)


@patch("fabrik.orchestrator.content_publisher.WordPressAPIClient")
def test_publish_creates_wp_post_with_credentials(mock_wp_cls):
    """Pipeline creates WordPress post when credentials are provided."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = _make_site_dict()
    seo.create_job.return_value = {"id": "job-1"}
    seo.run_job.return_value = {}
    seo.wait_for_job.return_value = {"status": "completed"}
    seo.list_ready_briefs.return_value = [_make_brief_dict()]
    seo.claim_brief.return_value = _make_brief_dict()

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = None

    mock_wp_instance = MagicMock()
    mock_wp_instance.create_post.return_value = {"id": 42}
    mock_wp_cls.return_value = mock_wp_instance

    publisher = _make_publisher(seo=seo, tco=tco, image=image)
    ctx = publisher.publish_page(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
        wp_credentials={"url": "https://wp.test", "username": "u", "password": "p"},
    )

    assert ctx.wp_post_id == 42


def test_publish_submits_brief_after_success():
    """Pipeline calls submit_brief after successful WP creation."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = _make_site_dict()
    seo.create_job.return_value = {"id": "job-1"}
    seo.run_job.return_value = {}
    seo.wait_for_job.return_value = {"status": "completed"}
    seo.list_ready_briefs.return_value = [_make_brief_dict()]
    seo.claim_brief.return_value = _make_brief_dict()
    seo.submit_brief.return_value = {"status": "submitted"}

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = None

    publisher = _make_publisher(seo=seo, tco=tco, image=image)
    ctx = publisher.publish_page(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )

    # submit_brief should have been called
    seo.submit_brief.assert_called_once()


def test_publish_submission_contains_required_fields():
    """submit_brief submission dict contains final_title, final_h1, final_page_type,
    schema_primary_used, schema_secondary_used."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = _make_site_dict()
    seo.create_job.return_value = {"id": "job-1"}
    seo.run_job.return_value = {}
    seo.wait_for_job.return_value = {"status": "completed"}
    seo.list_ready_briefs.return_value = [_make_brief_dict()]
    seo.claim_brief.return_value = _make_brief_dict()
    seo.submit_brief.return_value = {"status": "submitted"}

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = None

    publisher = _make_publisher(seo=seo, tco=tco, image=image)
    ctx = publisher.publish_page(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )

    seo.submit_brief.assert_called_once()
    call_args = seo.submit_brief.call_args
    submission = call_args[1].get("submission") or call_args[0][2]

    required_fields = [
        "final_title",
        "final_h1",
        "final_page_type",
        "schema_primary_used",
        "schema_secondary_used",
    ]
    for field_name in required_fields:
        assert field_name in submission, f"Missing field: {field_name}"


def test_build_wp_post_produces_content():
    """_build_wp_post assembles content from rendered_sections."""
    seo = MagicMock()
    publisher = _make_publisher(seo=seo)

    ctx = PublishContext(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )
    ctx.brief = _make_brief_dict()
    ctx.page_package = _make_page_package()

    wp_post = publisher._build_wp_post(ctx)

    assert wp_post.title
    assert wp_post.content
    assert "<h2>Hero</h2>" in wp_post.content or "Hero" in wp_post.content


def test_build_submission_produces_required_keys():
    """_build_submission produces a dict with all required submission keys."""
    publisher = _make_publisher()

    ctx = PublishContext(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )
    ctx.brief = _make_brief_dict()
    ctx.page_package = _make_page_package()
    ctx.wp_post_id = 42

    submission = publisher._build_submission(ctx)

    assert "final_url" in submission
    assert "final_slug" in submission
    assert "final_title" in submission
    assert "final_h1" in submission
    assert "final_page_type" in submission
    assert "schema_primary_used" in submission
    assert "schema_secondary_used" in submission
    assert "status" in submission


def test_build_submission_status_published_with_wp_id():
    """_build_submission returns status='published' when wp_post_id is set."""
    publisher = _make_publisher()

    ctx = PublishContext(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )
    ctx.brief = _make_brief_dict()
    ctx.page_package = _make_page_package()
    ctx.wp_post_id = 42

    submission = publisher._build_submission(ctx)
    assert submission["status"] == "published"


def test_build_submission_status_draft_without_wp_id():
    """_build_submission returns status='draft' when wp_post_id is None."""
    publisher = _make_publisher()

    ctx = PublishContext(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )
    ctx.brief = _make_brief_dict()
    ctx.page_package = _make_page_package()
    ctx.wp_post_id = None

    submission = publisher._build_submission(ctx)
    assert submission["status"] == "draft"


def test_publish_pipeline_records_no_briefs_error():
    """Pipeline records error when no ready briefs are found."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = _make_site_dict()
    seo.create_job.return_value = {"id": "job-1"}
    seo.run_job.return_value = {}
    seo.wait_for_job.return_value = {"status": "completed"}
    seo.list_ready_briefs.return_value = []  # No briefs

    publisher = _make_publisher(seo=seo)
    ctx = publisher.publish_page(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )

    assert any("no ready briefs" in e.lower() for e in ctx.errors)


def test_publish_image_auto_download_called_with_keyword():
    """Pipeline calls auto_download with primary_keyword from brief."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = _make_site_dict()
    seo.create_job.return_value = {"id": "job-1"}
    seo.run_job.return_value = {}
    seo.wait_for_job.return_value = {"status": "completed"}
    brief = _make_brief_dict()
    brief["page_record"]["primary_keyword"] = "saas pricing"
    seo.list_ready_briefs.return_value = [brief]
    seo.claim_brief.return_value = brief

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = None

    publisher = _make_publisher(seo=seo, tco=tco, image=image)
    publisher.publish_page(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )

    image.auto_download.assert_called_once()
    call_kwargs = image.auto_download.call_args
    assert call_kwargs[1]["query"] == "saas pricing" or call_kwargs[0][0] == "saas pricing"


def test_publish_context_add_error_and_warning():
    """PublishContext.add_error and add_warning append to respective lists."""
    ctx = PublishContext(
        domain="example.com",
        site_name="Example",
        seed_topic="test",
    )

    ctx.add_error("something broke")
    ctx.add_warning("something suspicious")

    assert len(ctx.errors) == 1
    assert "something broke" in ctx.errors[0]
    assert len(ctx.warnings) == 1
    assert "something suspicious" in ctx.warnings[0]
