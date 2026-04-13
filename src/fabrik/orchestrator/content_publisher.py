"""Content Publisher Orchestrator.

Chains SEO → TCO → Image Broker → WordPress for automated content publishing.

v1 single-site constraint: WordPress credentials (WP_SITE_URL, WP_USERNAME,
WP_PASSWORD) apply to one WordPress site at a time. Switch env vars per domain
before running `fabrik content publish`.

Two interfaces are provided:

- ``publish()`` — batch brief-drain loop (T2 spec): consumes ready briefs that
  already exist in the SEO service and publishes each one. Returns PublishSummary.

- ``publish_page()`` — legacy job-creation pipeline (used by `fabrik content
  publish` CLI): creates a new SEO job, runs it, then publishes the resulting
  brief. Returns PublishContext.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx

from fabrik.drivers.image_broker import ImageBrokerClient
from fabrik.drivers.seo import SEOClient
from fabrik.drivers.tco import TCOClient
from fabrik.drivers.wordpress_api import WordPressAPIClient, WPCredentials, WPPost
from fabrik.notifications import notify_content

logger = logging.getLogger(__name__)


# =============================================================================
# T2 Data Models
# =============================================================================


@dataclass
class PublishResult:
    """Result of publishing a single brief."""

    brief_id: str
    status: Literal["published", "failed", "skipped"]
    wp_url: str | None
    error: str | None


@dataclass
class PublishSummary:
    """Aggregate result of a publish() run for one domain."""

    domain: str
    total_briefs: int
    published: int
    failed: int
    results: list[PublishResult]


# =============================================================================
# Legacy Data Model (used by publish_page / CLI)
# =============================================================================


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


# =============================================================================
# ContentPublisher
# =============================================================================


class ContentPublisher:
    """Orchestrates the SEO → TCO → Image Broker → WordPress pipeline.

    v1 single-site constraint: WP_SITE_URL / WP_USERNAME / WP_PASSWORD apply
    to one WordPress site at a time. Switch env vars per domain before running.
    """

    def __init__(
        self,
        seo_client: SEOClient | None = None,
        tco_client: TCOClient | None = None,
        image_client: ImageBrokerClient | None = None,
        wp_client: WordPressAPIClient | None = None,
    ):
        """Initialize ContentPublisher with optional client overrides.

        WordPress credentials are read from env vars (WP_SITE_URL, WP_USERNAME,
        WP_PASSWORD) and stored as instance attributes. A WP client is
        constructed on demand per-domain via _get_wp_client().
        """
        self._seo = seo_client or SEOClient()
        self._tco = tco_client or TCOClient()
        self._ib = image_client or ImageBrokerClient()
        self._wp_client_override = wp_client  # optional injection for tests

        # WordPress credentials (v1 single-site)
        self._wp_site_url = os.getenv("WP_SITE_URL")
        self._wp_username = os.getenv("WP_USERNAME", "")
        self._wp_password = os.getenv("WP_PASSWORD", "")

        # Keep legacy attribute aliases so existing callers (cli.py) still work
        self.seo = self._seo
        self.tco = self._tco
        self.image = self._ib

    # =========================================================================
    # T2: Batch brief-drain interface
    # =========================================================================

    def publish(
        self,
        domain: str,
        dry_run: bool = False,
        limit: int = 10,
    ) -> PublishSummary:
        """Consume ready briefs from SEO service and publish each to WordPress.

        Args:
            domain: Target domain (must already be registered in SEO service).
            dry_run: If True, skip image download, WP publish, and SEO submit.
            limit: Maximum number of briefs to process in this run.

        Returns:
            PublishSummary with per-brief PublishResult list.

        Raises:
            ValueError: If domain is not found in SEO service.
        """
        site = self._seo.get_site_by_domain(domain)
        if site is None:
            raise ValueError(f"Domain '{domain}' not found in SEO service")

        site_id = str(site["site_id"])
        briefs = self._seo.list_ready_briefs(site_id)[:limit]
        logger.info("Publishing %d brief(s) for domain=%s dry_run=%s", len(briefs), domain, dry_run)

        results: list[PublishResult] = []
        for brief in briefs:
            result = self._publish_one(brief, domain, dry_run)
            results.append(result)

        published = sum(1 for r in results if r.status == "published")
        failed = sum(1 for r in results if r.status == "failed")
        notify_content(domain=domain, published=published, failed=failed, dry_run=dry_run)
        return PublishSummary(
            domain=domain,
            total_briefs=len(briefs),
            published=published,
            failed=failed,
            results=results,
        )

    def _get_wp_client(self, domain: str) -> WordPressAPIClient:
        """Construct a WordPressAPIClient. WP_SITE_URL takes precedence over domain."""
        if self._wp_client_override is not None:
            return self._wp_client_override
        url = self._wp_site_url or f"https://{domain}"
        credentials = WPCredentials(
            url=url,
            username=self._wp_username,
            password=self._wp_password,
        )
        return WordPressAPIClient(credentials)

    def _assemble_brief(self, claimed_brief: dict[str, Any]) -> dict[str, Any]:
        """Strip the extra ``lock`` field from a ClaimBriefResponse.

        TCO's ContentBrief schema uses ``extra="forbid"`` — it rejects any key
        not in its whitelist. The SEO service's ClaimBriefResponse adds a
        ``lock`` field that TCO does not know about. This method returns a new
        dict containing exactly the 10 fields TCO expects.

        UUID fields are coerced to ``str`` because TCO expects strings.
        """
        return {
            "brief_version": claimed_brief["brief_version"],
            "brief_id": str(claimed_brief["brief_id"]),
            "site_id": str(claimed_brief["site_id"]),
            "job_id": str(claimed_brief["job_id"]),
            "cluster_id": str(claimed_brief["cluster_id"]),
            "page_record": claimed_brief["page_record"],
            "geo": claimed_brief["geo"],
            "content_contract": claimed_brief["content_contract"],
            "cannibalization_guard": claimed_brief["cannibalization_guard"],
            "status": claimed_brief["status"],
        }

    def _render_html(self, rendered_sections: list[dict[str, Any]]) -> str:
        """Convert TCO rendered_sections into an HTML string for WordPress.

        Each section is ``{"type": str, "content": dict[str, Any]}``.
        ``content`` keys are rendered as HTML elements:
          - ``title``              → <h2>
          - ``subtitle``          → <h3>
          - ``text`` / ``body`` / ``content`` → <p>
          - ``items`` (list)      → <ul><li>…</li></ul>
          - any other str value   → <p>
        Each section is wrapped in ``<section data-type="…">``.
        """
        blocks: list[str] = []
        for section in rendered_sections:
            section_type = section.get("type", "unknown")
            content = section.get("content", {})
            inner_parts: list[str] = []
            for key, value in content.items():
                if key == "title":
                    inner_parts.append(f"<h2>{value}</h2>")
                elif key == "subtitle":
                    inner_parts.append(f"<h3>{value}</h3>")
                elif key in ("text", "body", "content"):
                    inner_parts.append(f"<p>{value}</p>")
                elif key == "items" and isinstance(value, list):
                    items_html = "".join(f"<li>{item}</li>" for item in value)
                    inner_parts.append(f"<ul>{items_html}</ul>")
                elif isinstance(value, str):
                    inner_parts.append(f"<p>{value}</p>")
            inner = "\n".join(inner_parts)
            blocks.append(f'<section data-type="{section_type}">\n{inner}\n</section>')
        return "\n".join(blocks)

    def _publish_one(
        self,
        brief: dict[str, Any],
        domain: str,
        dry_run: bool,
    ) -> PublishResult:
        """Run the full pipeline for a single ready brief.

        Order: claim → TCO generate → image download → WP publish → SEO submit.
        Any exception releases the brief lock and returns status="failed".
        Image failures are non-fatal (featured_media=0).
        dry_run skips image download, WP publish, and SEO submit.
        """
        worker_id = os.getenv("CONTENT_WORKER_ID", "fabrik-content-publisher")
        brief_id = str(brief["brief_id"])

        try:
            logger.info("Processing brief_id=%s domain=%s dry_run=%s", brief_id, domain, dry_run)

            # --- Claim ---
            claimed_brief = self._seo.claim_brief(brief_id, worker_id)

            # --- dry_run early exit ---
            if dry_run:
                logger.info("dry_run=True — skipping TCO/WP/submit for brief_id=%s", brief_id)
                return PublishResult(brief_id=brief_id, status="skipped", wp_url=None, error=None)

            # --- TCO generate ---
            try:
                page_package = self._tco.generate_from_brief(self._assemble_brief(claimed_brief))
            except Exception as exc:
                logger.error("TCO failed for brief_id=%s: %s", brief_id, exc)
                self._seo.release_brief(brief_id, worker_id)
                return PublishResult(
                    brief_id=brief_id, status="failed", wp_url=None, error=str(exc)
                )

            page_payload = page_package["page_payload"]

            # --- Image (non-fatal) ---
            media_id = 0
            wp_client = self._get_wp_client(domain)
            try:
                image_result = self._ib.auto_download(
                    query=page_payload["primary_keyword"],
                    intent="hero",
                    count=1,
                    image_type="photo",
                    orientation="landscape",
                )
                if image_result and image_result.get("selected"):
                    local_url = image_result["selected"][0]["local_url"]
                    ext = local_url.rsplit(".", 1)[-1].lower() if "." in local_url else "jpg"
                    tmp_path: str | None = None
                    try:
                        with tempfile.NamedTemporaryFile(
                            suffix=f".{ext}", delete=False
                        ) as tmp_file:
                            tmp_path = tmp_file.name
                        img_bytes = httpx.get(local_url, timeout=60).content
                        with open(tmp_path, "wb") as f:
                            f.write(img_bytes)
                        wp_media_result = wp_client.upload_media(tmp_path)
                        media_id = wp_media_result["id"]
                        logger.info("Uploaded media id=%d for brief_id=%s", media_id, brief_id)
                    except Exception as img_exc:
                        logger.warning(
                            "Image upload failed for brief_id=%s (non-fatal): %s",
                            brief_id,
                            img_exc,
                        )
                        media_id = 0
                    finally:
                        if tmp_path:
                            try:
                                os.unlink(tmp_path)
                            except OSError:
                                pass
                else:
                    logger.warning("No image selected for brief_id=%s", brief_id)
            except Exception as img_exc:
                logger.warning(
                    "Image broker failed for brief_id=%s (non-fatal): %s", brief_id, img_exc
                )
                media_id = 0

            # --- WP publish ---
            wp_post = WPPost(
                title=page_payload["seo_title"],
                content=self._render_html(page_package["rendered_sections"]),
                slug=page_payload["slug"],
                status="publish",
                featured_media=media_id,
            )

            if page_payload.get("page_type") == "blog_post":
                wp_result = wp_client.create_post(wp_post)
            else:
                wp_result = wp_client.create_page(wp_post)

            logger.info("Published brief_id=%s to WP url=%s", brief_id, wp_result.get("link"))

            # --- SEO submit ---
            submission = {
                "final_url": wp_result["link"],
                "final_slug": wp_result["slug"],
                "final_title": page_payload["seo_title"],
                "final_h1": page_payload["h1"],
                "final_page_type": page_payload["page_type"],
                "schema_primary_used": page_payload["schema_primary_type"],
                "schema_secondary_used": page_payload["schema_secondary_types"],
                "status": "published",
            }
            self._seo.submit_brief(brief_id, worker_id, submission)
            logger.info("Submitted brief_id=%s", brief_id)

            return PublishResult(
                brief_id=brief_id,
                status="published",
                wp_url=wp_result["link"],
                error=None,
            )

        except Exception as exc:
            logger.error("Unhandled error for brief_id=%s: %s", brief_id, exc)
            try:
                self._seo.release_brief(brief_id, worker_id)
            except Exception as rel_exc:
                logger.warning("release_brief failed for brief_id=%s: %s", brief_id, rel_exc)
            return PublishResult(brief_id=brief_id, status="failed", wp_url=None, error=str(exc))

    # =========================================================================
    # Legacy: job-creation pipeline (used by `fabrik content publish` CLI)
    # =========================================================================

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
        """Run the full content publishing pipeline (legacy job-creation flow).

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
            job = self._seo.create_job(
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
                self._seo.run_job(ctx.job_id)
                self._seo.wait_for_job(ctx.job_id, timeout=300)
                logger.info("Job completed")
            else:
                ctx.add_warning("Dry run: skipping job execution")

            # Step 4: Fetch briefs
            logger.info("Step 4: Fetching ready briefs")
            briefs = self._seo.list_ready_briefs(ctx.site_id)
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
                brief = self._seo.claim_brief(ctx.brief_id, worker_id)
                ctx.brief = brief
                logger.info("Brief claimed")
            else:
                ctx.brief = self._seo.get_brief(ctx.brief_id)
                ctx.add_warning("Dry run: skipping brief claim")

            # Step 6: Generate content via TCO
            logger.info("Step 6: Generating content via TCO")
            if not dry_run:
                page_package = self._tco.generate_from_brief(ctx.brief)
                ctx.page_package = page_package
                logger.info("Content generated")
            else:
                ctx.add_warning("Dry run: skipping TCO generation")

            # Step 7: Fetch image via Image Broker
            if ctx.brief and not dry_run:
                logger.info("Step 7: Fetching image via Image Broker")
                page_record = ctx.brief.get("page_record", {})
                primary_keyword = page_record.get("primary_keyword", seed_topic)

                image_result = self._ib.auto_download(
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
                wp_client = WordPressAPIClient(
                    WPCredentials(
                        url=wp_credentials["url"],
                        username=wp_credentials["username"],
                        password=wp_credentials["password"],
                    )
                )
                wp_post = self._build_wp_post(ctx)
                result = wp_client.create_post(wp_post)
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
                self._seo.submit_brief(ctx.brief_id, worker_id, submission)
                logger.info("Brief submitted")
            elif dry_run:
                ctx.add_warning("Dry run: skipping brief submission")

        except Exception as exc:
            ctx.add_error(f"Pipeline failed: {exc}")
            logger.exception("Content publishing pipeline failed")

        return ctx

    def _ensure_site(self, ctx: PublishContext) -> str:
        """Register or find site in SEO service."""
        existing = self._seo.get_site_by_domain(ctx.domain)
        if existing:
            logger.info("Site already exists: %s", ctx.domain)
            return str(existing["site_id"])

        return self._seo.ensure_site(
            domain=ctx.domain,
            name=ctx.site_name,
            country_code=ctx.country_code,
            language_code=ctx.language_code,
            category=ctx.category,
        )

    def _download_image(self, image_url: str) -> str:
        """Download image from URL to temp file (legacy pipeline helper)."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            path = tmp.name
        self._ib.download_image(image_url, path)
        return path

    def _build_wp_post(self, ctx: PublishContext) -> WPPost:
        """Build WPPost from page package and brief (legacy pipeline helper)."""
        if not ctx.page_package:
            return WPPost(title=ctx.seed_topic, content="")

        page_payload = ctx.page_package.get("page_payload", {})
        brief_record = ctx.brief.get("page_record", {}) if ctx.brief else {}

        content = self._render_html(ctx.page_package.get("rendered_sections", []))

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
        """Build submission payload for SEO brief (legacy pipeline helper)."""
        brief_record = ctx.brief.get("page_record", {}) if ctx.brief else {}
        page_payload = ctx.page_package.get("page_payload", {}) if ctx.page_package else {}

        return {
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
