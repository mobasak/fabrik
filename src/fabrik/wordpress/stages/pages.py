"""Page creation stage."""

import logging
from pathlib import Path
from typing import Any

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.page_generator import generate_pages
from fabrik.wordpress.pages import PageCreator
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Create site pages from generated page specs."""
    result = StageResult(name="pages", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        site_name = (
            spec.get("site_name")
            or spec.get("site", {}).get("name")
            or spec.get("site", {}).get("domain", "").replace(".", "-")
        )

        # Generate pages from spec (templates + entities)
        primary_locale = spec.get("languages", {}).get("primary", "en_US")
        page_specs = generate_pages(spec, locale=primary_locale)
        pages_created: dict = {}

        if not page_specs:
            result.skipped = True
            result.metadata["skipped_reason"] = "no pages generated from spec"
        elif dry_run:
            result.metadata["dry_run"] = {
                "page_count": len(page_specs),
                "slugs": [p.get("slug", "") for p in page_specs],
            }
        elif api:
            if not wp:
                raise RuntimeError("WordPressClient required for pages stage")

            creator = PageCreator(
                site_name,
                wp_client=wp,
                api_client=api,
            )

            # Build hierarchical page structure for PageCreator
            # First pass: group children by parent_slug (entity pages)
            pages_by_parent: dict[str, list[dict[str, str]]] = {}
            top_level_specs: list[dict[str, Any]] = []

            for page_spec in page_specs:
                parent_slug = page_spec.get("parent_slug")

                if parent_slug:
                    # Entity child page - group by parent
                    if parent_slug not in pages_by_parent:
                        pages_by_parent[parent_slug] = []

                    pages_by_parent[parent_slug].append(
                        {
                            "slug": page_spec.get("slug", ""),
                            "title": page_spec.get("title", ""),
                            "content": page_spec.get("content", ""),
                            "status": page_spec.get("status", "publish"),
                            "template": page_spec.get("template", ""),
                        }
                    )
                else:
                    # Top-level page
                    top_level_specs.append(page_spec)

            # Second pass: build top-level pages with children
            top_level_pages: list[dict[str, Any]] = []
            for page_spec in top_level_specs:
                slug = page_spec.get("slug", "")
                page_dict = {
                    "slug": slug,
                    "title": page_spec.get("title", ""),
                    "content": page_spec.get("content", ""),
                    "status": page_spec.get("status", "publish"),
                    "template": page_spec.get("template", ""),
                }

                # Attach children if any
                if slug in pages_by_parent:
                    page_dict["children"] = pages_by_parent[slug]

                top_level_pages.append(page_dict)

            # Warn about orphaned entity children (parent_slug with no matching top-level page)
            top_level_slugs = {p.get("slug", "") for p in top_level_specs}
            for orphan_parent in sorted(set(pages_by_parent) - top_level_slugs):
                msg = (
                    f"Entity children reference parent_slug='{orphan_parent}' "
                    "but no top-level page with that slug exists — children will not be created"
                )
                result.warnings.append(msg)
                logger.warning(msg)

            # Create all pages (idempotent, path-based keys)
            pages_created = creator.create_all(top_level_pages)

            # Set homepage if defined (WordPress auto-generates "home" slug for empty slug).
            # PageCreator.create_all stores the homepage under both "" and the actual
            # WordPress slug (typically "home"), so check all possible keys.
            homepage = pages_created.get("") or pages_created.get("home")
            if homepage:
                creator.set_homepage(homepage.id)
                # Flush rewrite rules and object cache to ensure WordPress
                # resolves the front page correctly on the next request.
                wp.rewrite_flush()
                wp.cache_flush()
                logger.info("Homepage set and caches flushed: page ID %d", homepage.id)

            # Set blog page if defined
            blog_page = pages_created.get("insights") or pages_created.get("blog")
            if blog_page:
                creator.set_blog_page(blog_page.id)

            # Store pages_created in metadata for SiteDeployer
            # Convert CreatedPage dataclasses to plain dicts for JSON serialisation
            result.metadata["pages_created"] = {
                path: {"id": p.id, "title": p.title, "slug": p.slug, "url": p.url}
                for path, p in pages_created.items()
            }

            # Resubmit sitemap after pages are created so search engines
            # index new content. Skipped gracefully if not configured.
            if not dry_run and pages_created:
                domain = spec.get("site", {}).get("domain", "")
                sitemap_url = spec.get("post_deploy", {}).get("sitemap_url") or (
                    f"https://{domain}/sitemap.xml" if domain else None
                )
                if domain and sitemap_url:
                    import threading

                    def resubmit_sitemap_bg(domain: str, sitemap_url: str) -> None:
                        """Background thread for sitemap resubmit to prevent blocking."""
                        try:
                            from fabrik.drivers.dns import DNSClient

                            dns_client = DNSClient()
                            try:
                                _ = dns_client.update_sitemap(domain, sitemap_url)
                                logger.info(
                                    "Sitemap resubmitted after page creation: %s → %s",
                                    domain,
                                    sitemap_url,
                                )
                            finally:
                                dns_client.close()
                        except Exception as e:
                            logger.warning("Background sitemap resubmit failed: %s", e)

                    threading.Thread(
                        target=resubmit_sitemap_bg,
                        args=(domain, sitemap_url),
                        daemon=True,
                    ).start()
                    logger.info("Sitemap resubmit triggered in background.")

        else:
            # REST API not available — pages cannot be created
            result.warnings.append(
                "REST API client not available — pages stage skipped. "
                "Set WP_ADMIN_PASSWORD env var to enable page creation."
            )
            result.skipped = True
            logger.warning("pages stage skipped: REST API client not available")

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
