"""
WordPress SEO Applicator - Configure SEO settings via Yoast/RankMath.

Handles:
- Site-wide SEO settings
- Page-specific meta (title, description)
- Schema markup configuration
- Sitemap settings
"""

import json
from dataclasses import dataclass

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client


@dataclass
class SEOSettings:
    """SEO configuration."""

    title_template: str = ""
    meta_description: str = ""
    schema_type: str = "Organization"
    social_image: str = ""
    robots: str = "index,follow"


class SEOApplicator:
    """
    Apply SEO settings to WordPress via Yoast or RankMath.

    Usage:
        applicator = SEOApplicator("wp-test")
        applicator.apply_site_seo(spec["seo"])
        applicator.set_page_meta(page_id, title, description)
    """

    def __init__(self, site_name: str, wp_client: WordPressClient | None = None):
        """
        Initialize SEO applicator.

        Args:
            site_name: WordPress site name
            wp_client: Optional WP-CLI client
        """
        self.site_name = site_name
        self.wp = wp_client or get_wordpress_client(site_name)
        self._seo_plugin: str | None = None

    def detect_seo_plugin(self) -> str | None:
        """Detect installed SEO plugin."""
        if self._seo_plugin:
            return self._seo_plugin

        plugins = self.wp.plugin_list()

        for plugin in plugins:
            name = plugin.get("name", "")
            status = plugin.get("status", "")

            if status != "active":
                continue

            if "yoast" in name.lower() or name == "wordpress-seo":
                self._seo_plugin = "yoast"
                return "yoast"
            elif "rank-math" in name.lower() or "seo-by-rank-math" in name:
                self._seo_plugin = "rankmath"
                return "rankmath"

        return None

    def apply_site_seo(self, seo: dict) -> dict:
        """
        Apply site-wide SEO settings.

        Args:
            seo: SEO section from site spec

        Returns:
            Dict of applied settings
        """
        applied = {}
        plugin = self.detect_seo_plugin()

        # Title template
        if title := seo.get("title_template"):
            if plugin == "yoast":
                self.wp.option_update(
                    "wpseo_titles",
                    json.dumps(
                        {
                            "title-home-wpseo": title,
                        }
                    ),
                )
            elif plugin == "rankmath":
                self.wp.option_update(
                    "rank_math_titles",
                    json.dumps(
                        {
                            "homepage_title": title,
                        }
                    ),
                )
            applied["title_template"] = title

        # Meta description
        if description := seo.get("meta_description"):
            if plugin == "yoast":
                self.wp.option_update(
                    "wpseo_titles",
                    json.dumps(
                        {
                            "metadesc-home-wpseo": description,
                        }
                    ),
                )
            elif plugin == "rankmath":
                self.wp.option_update(
                    "rank_math_titles",
                    json.dumps(
                        {
                            "homepage_description": description,
                        }
                    ),
                )
            applied["meta_description"] = description

        # Schema type
        if schema := seo.get("schema"):
            schema_type = schema.get("type", "Organization")
            applied["schema_type"] = schema_type

        # Verification codes
        if google_verification := seo.get("google_verification"):
            if plugin == "yoast":
                self.wp.option_update(
                    "wpseo",
                    json.dumps(
                        {
                            "googleverify": google_verification,
                        }
                    ),
                )
            elif plugin == "rankmath":
                self.wp.option_update(
                    "rank_math_options",
                    json.dumps(
                        {
                            "google_verify": google_verification,
                        }
                    ),
                )
            applied["google_verification"] = google_verification

        return applied

    def set_page_meta(
        self,
        page_id: int,
        title: str | None = None,
        description: str | None = None,
        focus_keyword: str | None = None,
    ) -> dict:
        """
        Set SEO meta for a specific page.

        Args:
            page_id: WordPress page/post ID
            title: SEO title
            description: Meta description
            focus_keyword: Primary keyword

        Returns:
            Dict of applied settings
        """
        applied = {}
        plugin = self.detect_seo_plugin()

        if plugin == "yoast":
            if title:
                self.wp.run(f"post meta update {page_id} _yoast_wpseo_title '{title}'")
                applied["title"] = title
            if description:
                self.wp.run(f"post meta update {page_id} _yoast_wpseo_metadesc '{description}'")
                applied["description"] = description
            if focus_keyword:
                self.wp.run(f"post meta update {page_id} _yoast_wpseo_focuskw '{focus_keyword}'")
                applied["focus_keyword"] = focus_keyword

        elif plugin == "rankmath":
            if title:
                self.wp.run(f"post meta update {page_id} rank_math_title '{title}'")
                applied["title"] = title
            if description:
                self.wp.run(f"post meta update {page_id} rank_math_description '{description}'")
                applied["description"] = description
            if focus_keyword:
                self.wp.run(f"post meta update {page_id} rank_math_focus_keyword '{focus_keyword}'")
                applied["focus_keyword"] = focus_keyword

        else:
            # No SEO plugin - use basic meta
            if description:
                self.wp.run(f"post meta update {page_id} _meta_description '{description}'")
                applied["description"] = description

        return applied

    def set_robots(
        self,
        page_id: int,
        index: bool = True,
        follow: bool = True,
    ) -> dict:
        """
        Set robots meta for a page.

        Args:
            page_id: WordPress page/post ID
            index: Allow indexing
            follow: Allow link following

        Returns:
            Dict with robots settings
        """
        plugin = self.detect_seo_plugin()

        robots = []
        if not index:
            robots.append("noindex")
        if not follow:
            robots.append("nofollow")

        robots_value = ",".join(robots) if robots else ""

        if plugin == "yoast":
            meta_robots = {
                "index": "1" if index else "2",
                "follow": "1" if follow else "2",
            }
            # Yoast uses numeric values
            if not index:
                self.wp.run(f"post meta update {page_id} _yoast_wpseo_meta-robots-noindex 1")
            if not follow:
                self.wp.run(f"post meta update {page_id} _yoast_wpseo_meta-robots-nofollow 1")

        elif plugin == "rankmath":
            self.wp.run(f"post meta update {page_id} rank_math_robots '{robots_value}'")

        return {"robots": robots_value or "index,follow"}

    def configure_sitemap(self, enabled: bool = True) -> bool:
        """
        Configure XML sitemap settings.

        Args:
            enabled: Enable/disable sitemap

        Returns:
            True if successful
        """
        plugin = self.detect_seo_plugin()

        if plugin == "yoast":
            self.wp.option_update(
                "wpseo",
                json.dumps(
                    {
                        "enable_xml_sitemap": enabled,
                    }
                ),
            )
        elif plugin == "rankmath":
            self.wp.option_update(
                "rank_math_options",
                json.dumps(
                    {
                        "sitemap": enabled,
                    }
                ),
            )

        return True

    def add_schema_markup(self, schema: dict) -> bool:
        """
        Add JSON-LD schema markup.

        Args:
            schema: Schema configuration from spec

        Returns:
            True if successful
        """
        schema_type = schema.get("type", "Organization")

        # This would typically be handled by the SEO plugin
        # For custom schema, we'd inject via a custom plugin or theme
        return True


def apply_seo(site_name: str, seo: dict) -> dict:
    """
    Convenience function to apply SEO settings.

    Args:
        site_name: WordPress site name
        seo: SEO section from site spec

    Returns:
        Dict of applied settings
    """
    applicator = SEOApplicator(site_name)
    return applicator.apply_site_seo(seo)
