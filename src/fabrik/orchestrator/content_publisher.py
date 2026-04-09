"""Content Publisher Orchestrator.

Chains SEO → TCO → Image Broker → WordPress for automated content publishing.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any

from fabrik.drivers.image_broker import ImageBrokerClient
from fabrik.drivers.seo import SEOClient
from fabrik.drivers.tco import TCOClient
from fabrik.drivers.wordpress_api import WordPressAPIClient, WPPost

logger = logging.getLogger(__name__)


@dataclass
class PublishContext:
    """Context for content publishing pipeline."""

    domain: str
    site_name: str
    seed_topic: str
    page_type: str | None = None
    country_code: str = "us"
    language_code: str = "en"
    category: str | None = None
    worker_id: str | None = None

    # Pipeline state
    site_id: str | None = None
    job_id: str | None = None
    brief_id: str | None = None
    brief: dict[str, Any] | None = None
    page_package: dict[str, Any] | None = None
    wp_post_id: int | None = None
    image_local_path: str | None = None

    # Results
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, msg: str):
        """Add an error to the context."""
        self.errors.append(msg)
        logger.error(msg)

    def add_warning(self, msg: str):
        """Add a warning to the context."""
        self.warnings.append(msg)
        logger.warning(msg)


class ContentPublisher:
    """Orchestrates the SEO → TCO → Image Broker → WordPress pipeline.

    Workflow:
    1. Register site in SEO service (or find existing)
    2. Create and run SEO job for seed topic
    3. Wait for job completion
    4. Fetch briefs and claim one
    5. Generate content via TCO
    6. Fetch image via Image Broker
    7. Upload image to WordPress
    8. Create/update WordPress post/page
    9. Submit/accept brief in SEO service
    """

    def __init__(
        self,
        seo_client: SEOClient | None = None,
        tco_client: TCOClient | None = None,
        image_client: ImageBrokerClient | None = None,
        wp_client: WordPressAPIClient | None = None,
    ):
        """Initialize ContentPublisher with optional client overrides."""
        self.seo = seo_client or SEOClient()
        self.tco = tco_client or TCOClient()
        self.image = image_client or ImageBrokerClient()
        self.wp = wp_client or None  # WordPress client requires credentials

    def publish_page(
        self,
        domain: str,
        site_name: str,
        seed_topic: str,
        page_type: str | None = None,
        country_code: str = "us",
        language_code: str = "en",
        category: str | None = None,
        wp_credentials: dict[str, str] | None = None,
        dry_run: bool = False,
    ) -> PublishContext:
        """Run the full content publishing pipeline.

        Args:
            domain: Site domain (e.g. "example.com")
            site_name: Display name for the site
            seed_topic: Topic for SEO keyword research
            page_type: Optional page type override (e.g. "service", "blog_post")
            country_code: ISO-2 country code
            language_code: Language code
            category: Site category (e.g. "saas", "company")
            wp_credentials: Optional WordPress credentials dict with keys:
                url, username, password. If None, skips WordPress step.
            dry_run: If True, simulate without making changes

        Returns:
            PublishContext with results and any errors
        """
        worker_id = os.getenv("CONTENT_WORKER_ID", "fabrik-content-publisher")
        ctx = PublishContext(
            domain=domain,
            site_name=site_name,
            seed_topic=seed_topic,
            page_type=page_type,
            country_code=country_code,
            language_code=language_code,
            category=category,
            worker_id=worker_id,
        )

        try:
            # Step 1: Register site in SEO service
            logger.info("Step 1: Registering site in SEO service")
            ctx.site_id = self._ensure_site(ctx)
            logger.info("Site ID: %s", ctx.site_id)

            # Step 2: Create SEO job
            logger.info("Step 2: Creating SEO job for topic: %s", seed_topic)
            job = self.seo.create_job(
                site_id=ctx.site_id,
                seed_topics=[seed_topic],
                country_code=country_code,
                language_code=language_code,
                page_type_override=page_type,
            )
            ctx.job_id = job["id"]
            logger.info("Job ID: %s", ctx.job_id)

            if not dry_run:
                # Step 3: Run job and wait for completion
                logger.info("Step 3: Running SEO job and waiting for completion")
                self.seo.run_job(ctx.job_id)
                self.seo.wait_for_job(ctx.job_id, timeout=300)
                logger.info("Job completed")
            else:
                ctx.add_warning("Dry run: skipping job execution")

            # Step 4: Fetch briefs
            logger.info("Step 4: Fetching ready briefs")
            briefs = self.seo.list_ready_briefs(ctx.site_id)
            if not briefs:
                ctx.add_error("No ready briefs found")
                return ctx

            # Get brief from this job
            job_briefs = [b for b in briefs if b["job_id"] == ctx.job_id]
            if not job_briefs:
                ctx.add_error(f"No briefs found for job {ctx.job_id}")
                return ctx

            ctx.brief_id = job_briefs[0]["brief_id"]
            logger.info("Brief ID: %s", ctx.brief_id)

            # Step 5: Claim brief
            if not dry_run:
                logger.info("Step 5: Claiming brief")
                brief = self.seo.claim_brief(ctx.brief_id, worker_id)
                ctx.brief = brief
                logger.info("Brief claimed")
            else:
                ctx.brief = self.seo.get_brief(ctx.brief_id)
                ctx.add_warning("Dry run: skipping brief claim")

            # Step 6: Generate content via TCO
            logger.info("Step 6: Generating content via TCO")
            if not dry_run:
                page_package = self.tco.generate_from_brief(ctx.brief)
                ctx.page_package = page_package
                logger.info("Content generated")
            else:
                ctx.add_warning("Dry run: skipping TCO generation")

            # Step 7: Fetch image via Image Broker
            if ctx.brief and not dry_run:
                logger.info("Step 7: Fetching image via Image Broker")
                page_record = ctx.brief.get("page_record", {})
                primary_keyword = page_record.get("primary_keyword", seed_topic)

                image_result = self.image.auto_download(
                    query=primary_keyword,
                    intent="hero",
                    count=1,
                )

                if image_result and image_result.get("selected"):
                    image_url = image_result["selected"][0].get("local_url")
                    if image_url:
                        ctx.image_local_path = self._download_image(image_url)
                        logger.info("Image downloaded to: %s", ctx.image_local_path)
                    else:
                        ctx.add_warning("No local URL in image result")
                else:
                    ctx.add_warning("No image selected")
            elif dry_run:
                ctx.add_warning("Dry run: skipping image download")

            # Step 8: Create/update WordPress post
            if wp_credentials and not dry_run:
                logger.info("Step 8: Creating WordPress post")
                self.wp = WordPressAPIClient(
                    url=wp_credentials["url"],
                    username=wp_credentials["username"],
                    password=wp_credentials["password"],
                )

                wp_post = self._build_wp_post(ctx)
                result = self.wp.create_post(wp_post)
                ctx.wp_post_id = result.get("id")
                logger.info("WordPress post created: ID %s", ctx.wp_post_id)
            elif not wp_credentials:
                ctx.add_warning("No WordPress credentials provided, skipping WordPress step")
            elif dry_run:
                ctx.add_warning("Dry run: skipping WordPress post creation")

            # Step 9: Submit brief
            if not dry_run and ctx.brief_id:
                logger.info("Step 9: Submitting brief")
                submission = self._build_submission(ctx)
                self.seo.submit_brief(ctx.brief_id, worker_id, submission)
                logger.info("Brief submitted")

                # Optionally accept brief
                # self.seo.accept_brief(ctx.brief_id, worker_id)
            elif dry_run:
                ctx.add_warning("Dry run: skipping brief submission")

        except Exception as exc:
            ctx.add_error(f"Pipeline failed: {exc}")
            logger.exception("Content publishing pipeline failed")

        return ctx

    def _ensure_site(self, ctx: PublishContext) -> str:
        """Register or find site in SEO service."""
        existing = self.seo.get_site_by_domain(ctx.domain)
        if existing:
            logger.info("Site already exists: %s", ctx.domain)
            return str(existing["site_id"])

        return self.seo.ensure_site(
            domain=ctx.domain,
            name=ctx.site_name,
            country_code=ctx.country_code,
            language_code=ctx.language_code,
            category=ctx.category,
        )

    def _download_image(self, image_url: str) -> str:
        """Download image from URL to temp file."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            path = tmp.name
        self.image.download_image(image_url, path)
        return path

    def _build_wp_post(self, ctx: PublishContext) -> WPPost:
        """Build WPPost from page package and brief."""
        if not ctx.page_package:
            return WPPost(title=ctx.seed_topic, content="")

        page_payload = ctx.page_package.get("page_payload", {})
        brief_record = ctx.brief.get("page_record", {}) if ctx.brief else {}

        # Extract content from rendered sections
        content = ""
        for section in ctx.page_package.get("rendered_sections", []):
            content += section.get("content", "") + "\n\n"

        return WPPost(
            title=page_payload.get("seo_title") or brief_record.get("h1") or ctx.seed_topic,
            content=content,
            slug=page_payload.get("slug") or brief_record.get("slug", ""),
            excerpt=page_payload.get("meta_description")
            or brief_record.get("meta_description", ""),
            status="draft",
            type="post",
        )

    def _build_submission(self, ctx: PublishContext) -> dict[str, Any]:
        """Build submission payload for SEO brief."""
        brief_record = ctx.brief.get("page_record", {}) if ctx.brief else {}
        page_payload = ctx.page_package.get("page_payload", {}) if ctx.page_package else {}

        return {
            "draft_reference": f"wp_post_{ctx.wp_post_id}" if ctx.wp_post_id else None,
            "final_url": f"https://{ctx.domain}/{brief_record.get('slug', '')}"
            if brief_record.get("slug")
            else None,
            "final_slug": brief_record.get("slug"),
            "final_title": page_payload.get("seo_title") or brief_record.get("h1"),
            "final_h1": brief_record.get("h1"),
            "final_page_type": brief_record.get("page_type"),
            "schema_primary_used": brief_record.get("schema", {}).get("primary_type"),
            "schema_secondary_used": brief_record.get("schema", {}).get("secondary_types", []),
            "status": "published" if ctx.wp_post_id else "draft",
        }
