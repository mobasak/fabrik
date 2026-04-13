"""Tests for ContentPublisher orchestrator.

All tests mock SEOClient, TCOClient, ImageBrokerClient, and WordPressAPIClient
to avoid live service calls. Tests cover both publish_page() (legacy) and
publish() (T2 batch brief-drain) interfaces.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

import uuid

from fabrik.content.orchestrator import (
    ContentPublisher,
    PublishContext,
    PublishResult,
    PublishSummary,
)


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
            "h1": "Test H1",
            "meta_description": "Meta desc",
            "primary_keyword": "test keyword",
            "schema_primary_type": "WebPage",
            "schema_secondary_types": ["FAQPage"],
        },
        "rendered_sections": [
            {"type": "hero", "content": {"title": "Hero"}},
            {"type": "body", "content": {"text": "Body text"}},
        ],
        "json_ld": [{"@type": "WebPage"}],
    }


def _make_claimed_brief(brief_id="brief-1"):
    """Minimal claimed brief with all 10 TCO-required fields + lock."""
    return {
        "brief_version": "1.0",
        "brief_id": brief_id,
        "site_id": "site-1",
        "job_id": "job-1",
        "cluster_id": "cluster-1",
        "page_record": {
            "primary_keyword": "test keyword",
            "page_type": "service",
            "h1": "Test Title",
            "slug": "test-page",
        },
        "geo": {"country": "us"},
        "content_contract": {},
        "cannibalization_guard": {},
        "status": "claimed",
        "lock": {"expires_at": "2099-01-01T00:00:00Z"},
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
    """publish_page creates WordPress post when credentials are provided."""
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
    """_build_wp_post assembles content from rendered_sections using _render_html."""
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
    assert "Hero" in wp_post.content


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


# =============================================================================
# T4 spec tests — publish() batch brief-drain interface
# =============================================================================


def _make_publisher_t2(seo=None, tco=None, image=None, wp=None):
    """Create ContentPublisher with all T2 private attribute aliases set."""
    pub = ContentPublisher(
        seo_client=seo or MagicMock(),
        tco_client=tco or MagicMock(),
        image_client=image or MagicMock(),
        wp_client=wp or MagicMock(),
    )
    return pub


def test_publish_raises_on_unknown_domain_t2():
    """publish() raises ValueError when domain not found in SEO service."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = None
    pub = _make_publisher_t2(seo=seo)
    with pytest.raises(ValueError, match="not found in SEO service"):
        pub.publish("bad.com")


def test_publish_skips_all_on_dry_run():
    """publish() with dry_run=True returns PublishSummary with all skipped."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [
        {"brief_id": "b1"},
        {"brief_id": "b2"},
    ]
    seo.claim_brief.side_effect = lambda brief_id, worker_id: {"brief_id": brief_id}

    pub = _make_publisher_t2(seo=seo)
    summary = pub.publish("x.com", dry_run=True)

    assert isinstance(summary, PublishSummary)
    assert summary.published == 0
    assert all(r.status == "skipped" for r in summary.results)


def test_publish_releases_lock_on_tco_failure():
    """publish() calls release_brief and returns failed when TCO raises."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [{"brief_id": "b1"}]
    seo.claim_brief.return_value = _make_claimed_brief("b1")

    tco = MagicMock()
    tco.generate_from_brief.side_effect = RuntimeError("tco exploded")

    pub = _make_publisher_t2(seo=seo, tco=tco)
    summary = pub.publish("x.com")

    assert summary.results[0].status == "failed"
    seo.release_brief.assert_called_once_with("b1", "fabrik-content-publisher")


def test_publish_continues_without_image_t2():
    """publish() continues and calls create_page even when auto_download returns None."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [{"brief_id": "b1"}]
    seo.claim_brief.return_value = _make_claimed_brief("b1")
    seo.submit_brief.return_value = {}

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = None

    wp = MagicMock()
    wp.create_page.return_value = {"link": "https://x.com/test-page", "slug": "test-page"}

    pub = _make_publisher_t2(seo=seo, tco=tco, image=image, wp=wp)
    summary = pub.publish("x.com")

    assert summary.results[0].status == "published"
    wp.create_page.assert_called_once()


@patch("fabrik.orchestrator.content_publisher.httpx.get")
def test_publish_upload_media_receives_file_path_not_url(mock_httpx_get):
    """upload_media is called with a local file path, never a URL."""
    mock_response = MagicMock()
    mock_response.content = b"fake image bytes"
    mock_httpx_get.return_value = mock_response

    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [{"brief_id": "b1"}]
    seo.claim_brief.return_value = _make_claimed_brief("b1")
    seo.submit_brief.return_value = {}

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = {
        "success": True,
        "selected": [{"local_url": "http://localhost:18016/cache/img.jpg"}],
    }

    wp = MagicMock()
    wp.upload_media.return_value = {"id": 99}
    wp.create_page.return_value = {"link": "https://x.com/test-page", "slug": "test-page"}

    pub = _make_publisher_t2(seo=seo, tco=tco, image=image, wp=wp)
    pub.publish("x.com")

    wp.upload_media.assert_called_once()
    path_arg = wp.upload_media.call_args[0][0]
    assert not path_arg.startswith("http"), f"upload_media got URL, expected file path: {path_arg}"


@patch("fabrik.orchestrator.content_publisher.httpx.get")
def test_publish_continues_if_image_download_raises(mock_httpx_get):
    """publish() continues with featured_media=0 when httpx.get raises."""
    mock_httpx_get.side_effect = httpx.HTTPError("connection failed")

    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [{"brief_id": "b1"}]
    seo.claim_brief.return_value = _make_claimed_brief("b1")
    seo.submit_brief.return_value = {}

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = {
        "success": True,
        "selected": [{"local_url": "http://localhost:18016/cache/img.jpg"}],
    }

    wp = MagicMock()
    wp.create_page.return_value = {"link": "https://x.com/test-page", "slug": "test-page"}

    pub = _make_publisher_t2(seo=seo, tco=tco, image=image, wp=wp)
    summary = pub.publish("x.com")

    assert summary.results[0].status == "published"
    wp.create_page.assert_called_once()
    wp_post_arg = wp.create_page.call_args[0][0]
    assert wp_post_arg.featured_media == 0


def test_publish_routes_blog_post_to_create_post():
    """publish() calls create_post for page_type == 'blog_post'."""
    pkg = _make_page_package()
    pkg["page_payload"]["page_type"] = "blog_post"

    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [{"brief_id": "b1"}]
    seo.claim_brief.return_value = _make_claimed_brief("b1")
    seo.submit_brief.return_value = {}

    tco = MagicMock()
    tco.generate_from_brief.return_value = pkg

    image = MagicMock()
    image.auto_download.return_value = None

    wp = MagicMock()
    wp.create_post.return_value = {"link": "https://x.com/test-page", "slug": "test-page"}

    pub = _make_publisher_t2(seo=seo, tco=tco, image=image, wp=wp)
    pub.publish("x.com")

    wp.create_post.assert_called_once()
    wp.create_page.assert_not_called()


def test_publish_routes_service_to_create_page():
    """publish() calls create_page for page_type != 'blog_post'."""
    pkg = _make_page_package()
    pkg["page_payload"]["page_type"] = "service"

    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [{"brief_id": "b1"}]
    seo.claim_brief.return_value = _make_claimed_brief("b1")
    seo.submit_brief.return_value = {}

    tco = MagicMock()
    tco.generate_from_brief.return_value = pkg

    image = MagicMock()
    image.auto_download.return_value = None

    wp = MagicMock()
    wp.create_page.return_value = {"link": "https://x.com/test-page", "slug": "test-page"}

    pub = _make_publisher_t2(seo=seo, tco=tco, image=image, wp=wp)
    pub.publish("x.com")

    wp.create_page.assert_called_once()
    wp.create_post.assert_not_called()


def test_publish_submits_brief_after_success_t2():
    """publish() calls submit_brief with correct final_url from WP response."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [{"brief_id": "b1"}]
    seo.claim_brief.return_value = _make_claimed_brief("b1")
    seo.submit_brief.return_value = {}

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = None

    wp = MagicMock()
    wp.create_page.return_value = {"link": "https://x.com/test-page", "slug": "test-page"}

    pub = _make_publisher_t2(seo=seo, tco=tco, image=image, wp=wp)
    pub.publish("x.com")

    seo.submit_brief.assert_called_once()
    submission = seo.submit_brief.call_args[0][2]
    assert submission["final_url"] == "https://x.com/test-page"


def test_publish_submits_full_submission_payload():
    """submit_brief receives all required submission fields."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [{"brief_id": "b1"}]
    seo.claim_brief.return_value = _make_claimed_brief("b1")
    seo.submit_brief.return_value = {}

    tco = MagicMock()
    tco.generate_from_brief.return_value = _make_page_package()

    image = MagicMock()
    image.auto_download.return_value = None

    wp = MagicMock()
    wp.create_page.return_value = {"link": "https://x.com/test-page", "slug": "test-page"}

    pub = _make_publisher_t2(seo=seo, tco=tco, image=image, wp=wp)
    pub.publish("x.com")

    submission = seo.submit_brief.call_args[0][2]
    for key in ("final_title", "final_h1", "final_page_type", "schema_primary_used", "schema_secondary_used"):
        assert key in submission, f"Missing submission key: {key}"


def test_assemble_brief_excludes_lock_field():
    """_assemble_brief strips 'lock' and returns exactly 10 keys."""
    pub = ContentPublisher.__new__(ContentPublisher)
    result = pub._assemble_brief(_make_claimed_brief())
    assert "lock" not in result
    assert len(result) == 10


def test_assemble_brief_converts_uuids_to_str():
    """_assemble_brief coerces UUID objects to str."""
    pub = ContentPublisher.__new__(ContentPublisher)
    uid = uuid.uuid4()
    claimed = {
        "brief_version": "1.0",
        "brief_id": uid,
        "site_id": uid,
        "job_id": uid,
        "cluster_id": uid,
        "page_record": {},
        "geo": {},
        "content_contract": {},
        "cannibalization_guard": {},
        "status": "claimed",
    }
    result = pub._assemble_brief(claimed)
    for key in ("brief_id", "site_id", "job_id", "cluster_id"):
        assert isinstance(result[key], str)


def test_render_html_produces_section_tags():
    """_render_html maps section dicts to correct HTML tags."""
    pub = ContentPublisher.__new__(ContentPublisher)
    sections = [
        {"type": "hero", "content": {"title": "Hero Title", "subtitle": "Sub"}},
        {"type": "ai_summary", "content": {"text": "Summary text"}},
    ]
    html = pub._render_html(sections)
    assert '<section data-type="hero">' in html
    assert "<h2>Hero Title</h2>" in html
    assert "<h3>Sub</h3>" in html
    assert '<section data-type="ai_summary">' in html
    assert "<p>Summary text</p>" in html


def test_publish_respects_limit():
    """publish() processes at most `limit` briefs."""
    seo = MagicMock()
    seo.get_site_by_domain.return_value = {"site_id": "s1", "domain": "x.com"}
    seo.list_ready_briefs.return_value = [
        {"brief_id": f"b{i}"} for i in range(5)
    ]
    seo.claim_brief.side_effect = lambda brief_id, worker_id: {"brief_id": brief_id}

    pub = _make_publisher_t2(seo=seo)
    summary = pub.publish("x.com", dry_run=True, limit=2)

    assert summary.total_briefs == 2
    assert len(summary.results) == 2
