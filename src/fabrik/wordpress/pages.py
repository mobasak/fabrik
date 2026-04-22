"""
WordPress Page Creator - Create pages from site specification.

Handles:
- Page creation via REST API
- Hierarchical pages (parent/child)
- Page templates
- Slug management
"""

from __future__ import annotations

import json
import logging
import shlex
from dataclasses import dataclass

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client
from fabrik.drivers.wordpress_api import WordPressAPIClient, WPCredentials


@dataclass
class CreatedPage:
    """Created page details."""

    id: int
    title: str
    slug: str
    url: str
    parent_id: int | None = None


logger = logging.getLogger(__name__)


class PageCreator:
    """
    Create WordPress pages from site specification.

    Usage:
        creator = PageCreator("wp-test", api_url, api_user, api_pass)
        pages = creator.create_all(spec["pages"])
        creator.set_homepage(pages[""])  # Empty slug = homepage
    """

    def __init__(
        self,
        site_name: str,
        api_url: str | None = None,
        api_user: str | None = None,
        api_password: str | None = None,
        wp_client: WordPressClient | None = None,
        api_client: WordPressAPIClient | None = None,
    ):
        """
        Initialize page creator.

        Args:
            site_name: WordPress site name
            api_url: WordPress site URL for REST API
            api_user: Admin username
            api_password: Application password
            wp_client: Optional WP-CLI client
            api_client: Optional REST API client
        """
        self.site_name = site_name
        self.wp = wp_client or get_wordpress_client(site_name)

        if api_client:
            self.api = api_client
        elif api_url and api_user and api_password:
            creds = WPCredentials(url=api_url, username=api_user, password=api_password)
            self.api = WordPressAPIClient(creds)
        else:
            self.api = None

    def find_page(self, slug: str, parent_id: int | None = None) -> CreatedPage | None:
        """
        Find existing page by slug and parent_id.

        Args:
            slug: Page slug
            parent_id: Parent page ID (None for top-level)

        Returns:
            CreatedPage if found, None otherwise
        """
        # Guard: empty slug queries return ALL pages from WordPress REST API
        # (the ?slug= parameter matches everything when empty).  For homepage
        # pages the spec uses slug="" but WordPress auto-generates "home", so
        # search for "home" instead.
        if not slug:
            # Try to find the actual page set as front page first
            try:
                front_page_id = self.wp.option_get("page_on_front")
                if front_page_id and int(front_page_id) > 0:
                    # Fetch this specific page details
                    page_id = int(front_page_id)
                    try:
                        if self.api:
                            page = self.api.get_page(page_id)
                            return CreatedPage(
                                id=page["id"],
                                title=page.get("title", {}).get("rendered", ""),
                                slug=page.get("slug", ""),
                                url=page.get("link", ""),
                                parent_id=page.get("parent"),
                            )
                    except Exception:
                        pass

                    # Fallback to WP-CLI to get details of this ID
                    try:
                        output = self.wp.run(
                            f"post get {page_id} --format=json --fields=ID,post_title,post_name,guid,post_parent"
                        )
                        page = json.loads(output)
                        return CreatedPage(
                            id=int(page.get("ID", page_id)),
                            title=page.get("post_title", ""),
                            slug=page.get("post_name", ""),
                            url=page.get("guid", ""),
                            parent_id=int(page.get("post_parent", 0)) or None,
                        )
                    except Exception:
                        pass
            except Exception:
                pass

            # Fallback to searching for "home" slug
            return self.find_page("home", parent_id)

        # Try REST API first
        try:
            if not self.api:
                return self.find_page_cli(slug, parent_id)

            # Query pages by slug (WordPress REST API returns 400 with comma-separated status)
            # Query without status filter and check results locally
            params: dict[str, str | int] = {"slug": slug}
            if parent_id is not None:
                params["parent"] = parent_id

            result = self.api._request("GET", "/pages", params=params)

            if result and len(result) > 0:
                page = result[0]
                return CreatedPage(
                    id=page["id"],
                    title=page.get("title", {}).get("rendered", ""),
                    slug=page.get("slug", slug),
                    url=page.get("link", ""),
                    parent_id=parent_id,
                )

            return None
        except Exception as exc:
            logger.warning(
                "find_page(%s, parent=%s) REST API error: %s, falling back to WP-CLI",
                slug,
                parent_id,
                exc,
            )
            return self.find_page_cli(slug, parent_id)

    def find_page_cli(self, slug: str, parent_id: int | None = None) -> CreatedPage | None:
        """
        Find existing page by slug using WP-CLI (fallback for REST API auth issues).

        Args:
            slug: Page slug
            parent_id: Parent page ID (None for top-level)

        Returns:
            CreatedPage if found, None otherwise
        """
        try:
            # Build WP-CLI command
            cmd = [
                "post",
                "list",
                "--post_type=page",
                f"--name={slug}",
                "--format=json",
                "--fields=ID,post_title,post_name,guid",
            ]

            if parent_id is not None:
                cmd.append(f"--post_parent={parent_id}")

            result = self.wp.run(" ".join(shlex.quote(arg) for arg in cmd))

            if result:
                pages = json.loads(result)
                if pages and len(pages) > 0:
                    page = pages[0]
                    return CreatedPage(
                        id=int(page.get("ID", 0)),
                        title=page.get("post_title", ""),
                        slug=page.get("post_name", slug),
                        url=page.get("guid", ""),
                        parent_id=parent_id,
                    )

            return None
        except Exception as exc:
            logger.warning("find_page_cli(%s, parent=%s) error: %s", slug, parent_id, exc)
            return None

    def create_or_get_page(
        self,
        title: str,
        slug: str = "",
        content: str = "",
        status: str = "publish",
        template: str = "",
        parent_id: int | None = None,
    ) -> CreatedPage:
        """
        Create page or return existing (idempotent).

        Args:
            title: Page title
            slug: Page slug (empty for homepage)
            content: Page content (HTML)
            status: publish, draft, private
            template: Page template filename
            parent_id: Parent page ID for hierarchical pages

        Returns:
            CreatedPage (existing or newly created)
        """
        # Try to find existing page
        existing = self.find_page(slug, parent_id)
        if existing:
            return existing

        # Create new page
        return self.create_page(
            title=title,
            slug=slug,
            content=content,
            status=status,
            template=template,
            parent_id=parent_id,
        )

    def create_page(
        self,
        title: str,
        slug: str = "",
        content: str = "",
        status: str = "publish",
        template: str = "",
        parent_id: int | None = None,
    ) -> CreatedPage:
        """
        Create a single page.

        Args:
            title: Page title
            slug: URL slug (empty for auto-generated)
            content: Page content (HTML)
            status: publish, draft, private
            template: Page template filename
            parent_id: Parent page ID for hierarchical pages

        Returns:
            CreatedPage with details
        """
        # Try REST API first
        try:
            if not self.api:
                raise ValueError("REST API client required for page creation")

            # Create page
            data: dict[str, str | int] = {
                "title": title,
                "content": content,
                "status": status,
            }

            if slug:
                data["slug"] = slug

            if template:
                data["template"] = template

            if parent_id is not None:
                data["parent"] = parent_id

            result = self.api._request("POST", "/pages", json=data)

            return CreatedPage(
                id=result["id"],
                title=result.get("title", {}).get("rendered", title),
                slug=result.get("slug", slug),
                url=result.get("link", ""),
                parent_id=parent_id,
            )
        except Exception as exc:
            logger.error(
                "create_page(%s) REST API error: %s, falling back to WP-CLI. "
                "Title: %s, Slug: %s, Template: %s, Parent: %s",
                title,
                exc,
                title,
                slug,
                template,
                parent_id,
                exc_info=True,
            )
            return self.create_page_cli(title, slug, content, status, template, parent_id)

    def create_page_cli(
        self,
        title: str,
        slug: str = "",
        content: str = "",
        status: str = "publish",
        template: str = "",
        parent_id: int | None = None,
    ) -> CreatedPage:
        """
        Create a single page using WP-CLI (fallback for REST API auth issues).

        Args:
            title: Page title
            slug: URL slug (empty for auto-generated)
            content: Page content (HTML)
            status: publish, draft, private
            template: Page template filename
            parent_id: Parent page ID for hierarchical pages

        Returns:
            CreatedPage with details
        """
        try:
            # Build WP-CLI command - create page without content first
            # to avoid shell argument length limits with large HTML
            cmd = [
                "post",
                "create",
                "--post_type=page",
                f"--post_title={shlex.quote(title)}",
                f"--post_status={status}",
                "--porcelain",
            ]

            if slug:
                cmd.append(f"--post_name={shlex.quote(slug)}")

            if template:
                cmd.append(f"--page_template={shlex.quote(template)}")

            if parent_id is not None:
                cmd.append(f"--post_parent={parent_id}")

            result = self.wp.run(" ".join(cmd))

            if result:
                post_id = int(result.strip())

                # Set content separately using post update to avoid shell limits
                if content:
                    # Write content to temporary file
                    import os
                    import subprocess
                    import tempfile

                    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                        f.write(content)
                        content_file = f.name

                    try:
                        # Copy temp file to VPS for remote execution
                        vps_file = f"/tmp/wp_page_{post_id}.txt"
                        subprocess.run(
                            ["scp", content_file, f"vps:{vps_file}"],
                            check=True,
                            capture_output=True,
                        )

                        # Use post update with content from VPS file
                        update_cmd = (
                            f"post update {post_id} --post_content=< {shlex.quote(vps_file)}"
                        )
                        self.wp.run(update_cmd)
                    finally:
                        os.unlink(content_file)

                # Get the created page details
                list_cmd = [
                    "post",
                    "get",
                    str(post_id),
                    "--format=json",
                    "--fields=ID,post_title,post_name,guid",
                ]
                page_data = self.wp.run(" ".join(shlex.quote(arg) for arg in list_cmd))
                page = json.loads(page_data)

                return CreatedPage(
                    id=int(page.get("ID", post_id)),
                    title=page.get("post_title", title),
                    slug=page.get("post_name", slug),
                    url=page.get("guid", ""),
                    parent_id=parent_id,
                )

            raise RuntimeError("WP-CLI page creation returned no result")
        except Exception as exc:
            # If template is invalid, retry without template
            if template and "Invalid page template" in str(exc):
                logger.warning(
                    "create_page_cli(%s) invalid template '%s', retrying without template",
                    title,
                    template,
                )
                return self.create_page_cli(title, slug, content, status, "", parent_id)
            logger.warning("create_page_cli(%s) error: %s", title, exc)
            raise

    def create_all(
        self,
        pages: list,
        parent_id: int | None = None,
        parent_path: str = "",
    ) -> dict[str, CreatedPage]:
        """
        Create all pages from spec, including children.

        Uses path-based keys to prevent slug collisions.

        Args:
            pages: List of page specs from site YAML
            parent_id: Parent page ID (for recursive calls)
            parent_path: Parent path for building full paths

        Returns:
            Dict mapping full path to CreatedPage

        Example:
            {
                "": CreatedPage(...),              # Homepage
                "about": CreatedPage(...),         # /about
                "about/team": CreatedPage(...),    # /about/team
                "services/consulting": CreatedPage(...)  # /services/consulting
            }
        """
        created = {}

        for page_spec in pages:
            title = page_spec.get("title", "Untitled")
            slug = page_spec.get("slug", "")
            content = page_spec.get("content", "")
            status = page_spec.get("status", "publish")
            template = self._get_template(page_spec.get("template", ""))

            # Build full path (collision-safe key)
            path = f"{parent_path}/{slug}".strip("/") if slug else ""

            # Create the page (idempotent via create_or_get_page)
            page = self.create_or_get_page(
                title=title,
                slug=slug,
                content=content,
                status=status,
                template=template,
                parent_id=parent_id,
            )

            # Store by full path.  WordPress auto-generates slug "home" for
            # pages created with an empty slug, so also store under "home"
            # to let the homepage lookup in stages/pages.py find it via
            # either key.
            created[path] = page
            if not path and page.slug and page.slug != path:
                created[page.slug] = page

            # Handle child pages
            children = page_spec.get("children", [])
            if children:
                child_pages = self.create_all(
                    children,
                    parent_id=page.id,
                    parent_path=path,
                )
                created.update(child_pages)

        return created

    def _get_template(self, template: str) -> str:
        """
        Convert template name to WordPress template filename.

        Args:
            template: Template name from spec

        Returns:
            WordPress template filename
        """
        template_map = {
            "full-width": "full-width.php",
            "landing": "landing.php",
            "blank": "blank.php",
            "default": "",
            "": "",
        }
        return template_map.get(template, template)

    def update_page(self, page_id: int, **fields) -> dict:
        """
        Update an existing page.

        Args:
            page_id: Page ID to update
            **fields: Fields to update (title, content, status, etc.)

        Returns:
            Updated page data
        """
        if not self.api:
            raise ValueError("REST API client required")
        return self.api.update_page(page_id, **fields)

    def delete_page(self, page_id: int, force: bool = True) -> bool:
        """
        Delete a page.

        Args:
            page_id: Page ID to delete
            force: Bypass trash

        Returns:
            True if deleted
        """
        if not self.api:
            raise ValueError("REST API client required")
        self.api.delete_page(page_id, force=force)
        return True

    def list_pages(self, status: str = "any") -> list[dict]:
        """List all pages."""
        if not self.api:
            raise ValueError("REST API client required")
        return self.api.list_pages(per_page=100, status=status)

    def get_page_by_slug(self, slug: str) -> dict | None:
        """Get page by slug."""
        if not self.api:
            # Use WP-CLI
            try:
                output = self.wp.run(
                    f"post list --post_type=page --name={shlex.quote(slug)} --format=json"
                )
                pages = json.loads(output)
                return pages[0] if pages else None
            except Exception as exc:
                logger.warning("get_page_by_slug(%s) WP-CLI lookup failed: %s", slug, exc)
                return None

        pages = self.api._request("GET", "/pages", params={"slug": slug})
        return pages[0] if pages else None

    def set_homepage(self, page_id: int) -> bool:
        """
        Set a page as the static homepage.

        Args:
            page_id: Page ID to use as homepage

        Returns:
            True if successful
        """
        self.wp.option_update("show_on_front", "page")
        self.wp.option_update("page_on_front", str(page_id))
        return True

    def set_blog_page(self, page_id: int) -> bool:
        """
        Set a page as the blog posts page.

        Args:
            page_id: Page ID for blog

        Returns:
            True if successful
        """
        self.wp.option_update("page_for_posts", str(page_id))
        return True


def create_pages(
    site_name: str,
    pages: list,
    api_url: str,
    api_user: str,
    api_password: str,
) -> dict[str, CreatedPage]:
    """
    Convenience function to create pages from spec.

    Args:
        site_name: WordPress site name
        pages: List of page specs
        api_url: WordPress site URL
        api_user: Admin username
        api_password: Application password

    Returns:
        Dict mapping slug to CreatedPage
    """
    creator = PageCreator(
        site_name=site_name,
        api_url=api_url,
        api_user=api_user,
        api_password=api_password,
    )
    return creator.create_all(pages)
