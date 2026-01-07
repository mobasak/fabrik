"""
WordPress Settings Applicator - Apply WordPress settings from site spec.

Handles:
- Core WordPress settings (title, tagline, permalinks, timezone)
- Default content cleanup (sample post, page, comments)
- User account creation (editor accounts)
- Reading settings (homepage, blog page)
"""

import secrets
from dataclasses import dataclass

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client


@dataclass
class EditorCredentials:
    """Created editor account credentials."""

    username: str
    email: str
    password: str
    role: str = "editor"


class SettingsApplicator:
    """
    Apply WordPress settings from site specification.

    Usage:
        applicator = SettingsApplicator("wp-test")
        applicator.cleanup_defaults()
        applicator.apply_settings(spec)
        editor = applicator.create_editor("editor@example.com")
    """

    def __init__(self, site_name: str, wp_client: WordPressClient | None = None):
        """
        Initialize settings applicator.

        Args:
            site_name: WordPress site name (container prefix)
            wp_client: Optional WP-CLI client (created if not provided)
        """
        self.site_name = site_name
        self.wp = wp_client or get_wordpress_client(site_name)

    def cleanup_defaults(self) -> dict:
        """
        Remove WordPress default content.

        Removes:
        - "Hello World" post (ID 1)
        - "Sample Page" page (ID 2)
        - Default comment (ID 1)
        - Hello Dolly plugin
        - Akismet plugin (if not needed)

        Returns:
            Dict with cleanup results
        """
        plugins_deleted: list[str] = []
        results: dict[str, bool | list[str]] = {
            "post_deleted": False,
            "page_deleted": False,
            "comment_deleted": False,
            "plugins_deleted": plugins_deleted,
        }

        # Delete default post
        try:
            self.wp.run("post delete 1 --force")
            results["post_deleted"] = True
        except RuntimeError:
            pass  # Already deleted or doesn't exist

        # Delete sample page
        try:
            self.wp.run("post delete 2 --force")
            results["page_deleted"] = True
        except RuntimeError:
            pass

        # Delete default comment
        try:
            self.wp.run("comment delete 1 --force")
            results["comment_deleted"] = True
        except RuntimeError:
            pass

        # Delete default plugins
        for plugin in ["hello", "akismet"]:
            try:
                self.wp.plugin_delete(plugin)
                plugins_deleted.append(plugin)
            except RuntimeError:
                pass

        return results

    def apply_settings(self, spec: dict) -> dict:
        """
        Apply WordPress settings from site spec.

        Args:
            spec: Site specification dict with 'brand', 'settings', 'timezone', etc.

        Returns:
            Dict with applied settings
        """
        applied: dict[str, str | bool | int] = {}

        brand = spec.get("brand", {})
        settings = spec.get("settings", {})

        # Site identity
        if brand.get("name"):
            self.wp.option_update("blogname", brand["name"])
            applied["blogname"] = brand["name"]

        if brand.get("tagline"):
            self.wp.option_update("blogdescription", brand["tagline"])
            applied["blogdescription"] = brand["tagline"]

        # Permalinks
        permalink = settings.get("permalink_structure", "/%postname%/")
        self.wp.option_update("permalink_structure", permalink)
        self.wp.rewrite_flush()
        applied["permalink_structure"] = permalink

        # Timezone
        timezone = spec.get("timezone", settings.get("timezone_string", "UTC"))
        self.wp.option_update("timezone_string", timezone)
        applied["timezone_string"] = timezone

        # Date format
        date_format = spec.get("date_format", settings.get("date_format", "Y-m-d"))
        self.wp.option_update("date_format", date_format)
        applied["date_format"] = date_format

        # Enable search engine indexing
        self.wp.option_update("blog_public", "1")
        applied["blog_public"] = "1"

        return applied

    def set_homepage(self, homepage_id: int, blog_page_id: int | None = None) -> dict:
        """
        Set static homepage and optional blog page.

        Args:
            homepage_id: Page ID to use as homepage
            blog_page_id: Optional page ID for blog posts

        Returns:
            Dict with applied settings
        """
        applied: dict[str, str | int] = {}

        # Set to static page mode
        self.wp.option_update("show_on_front", "page")
        applied["show_on_front"] = "page"

        # Set homepage
        self.wp.option_update("page_on_front", str(homepage_id))
        applied["page_on_front"] = homepage_id

        # Set blog page if provided
        if blog_page_id:
            self.wp.option_update("page_for_posts", str(blog_page_id))
            applied["page_for_posts"] = blog_page_id

        return applied

    def create_editor(self, email: str, username: str | None = None) -> EditorCredentials:
        """
        Create an editor account for daily content management.

        Args:
            email: Email address for the editor
            username: Optional username (derived from email if not provided)

        Returns:
            EditorCredentials with login details
        """
        if not username:
            username = email.split("@")[0].replace(".", "_").replace("+", "_")

        password = secrets.token_urlsafe(16)

        self.wp.user_create(username=username, email=email, role="editor", password=password)

        return EditorCredentials(username=username, email=email, password=password, role="editor")

    def get_page_id_by_slug(self, slug: str) -> int | None:
        """
        Get page ID by slug.

        Args:
            slug: Page slug (empty string for homepage)

        Returns:
            Page ID or None if not found
        """
        try:
            # Use WP-CLI to find page by slug
            if slug == "":
                # Homepage - find by title or get front page
                output = self.wp.run("option get page_on_front")
                if output and output.strip() != "0":
                    return int(output.strip())

            output = self.wp.run(f"post list --post_type=page --name='{slug}' --format=ids")
            if output.strip():
                return int(output.strip().split()[0])
        except (RuntimeError, ValueError):
            pass

        return None

    def get_page_id_by_title(self, title: str) -> int | None:
        """
        Get page ID by title.

        Args:
            title: Page title

        Returns:
            Page ID or None if not found
        """
        try:
            output = self.wp.run(f"post list --post_type=page --title='{title}' --format=ids")
            if output.strip():
                return int(output.strip().split()[0])
        except (RuntimeError, ValueError):
            pass

        return None


def apply_settings(site_name: str, spec: dict, cleanup: bool = True) -> dict:
    """
    Convenience function to apply settings to a WordPress site.

    Args:
        site_name: WordPress site name
        spec: Site specification dict
        cleanup: Whether to cleanup default content first

    Returns:
        Dict with all applied settings and actions
    """
    applicator = SettingsApplicator(site_name)
    results = {}

    if cleanup:
        results["cleanup"] = applicator.cleanup_defaults()

    results["settings"] = applicator.apply_settings(spec)

    return results
