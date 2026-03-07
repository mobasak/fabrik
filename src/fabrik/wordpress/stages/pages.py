"""Page creation stage."""

from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.page_generator import generate_pages
from fabrik.wordpress.pages import PageCreator
from fabrik.wordpress.stages import StageResult, time_stage


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

        if not page_specs:
            # Key fix: No early return. Fall through to mark stage complete.
            pass
        elif dry_run:
            # Dry-run: just log intent
            pass
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
            pages_by_parent = {}
            top_level_specs = []

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
            top_level_pages = []
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

            # Create all pages (idempotent, path-based keys)
            pages_created = creator.create_all(top_level_pages)

            # Set homepage if defined
            homepage = pages_created.get("")
            if homepage:
                creator.set_homepage(homepage.id)

            # Set blog page if defined
            blog_page = pages_created.get("insights") or pages_created.get("blog")
            if blog_page:
                creator.set_blog_page(blog_page.id)

            # Store pages_created in metadata for SiteDeployer
            result.metadata["pages_created"] = pages_created

        else:
            # API not available: log but don't fail
            pass

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
