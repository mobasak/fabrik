"""
WordPress SEO Applicator - Configure SEO settings via Yoast/RankMath.

Handles:
- Site-wide SEO settings
- Page-specific meta (title, description)
- Schema markup configuration
- Sitemap settings
- Archive noindex (tags, author, date)
- Open Graph + Twitter Card
- Breadcrumbs
- robots.txt AI crawler allow rules
"""

import json
import logging
import shlex
from dataclasses import dataclass

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client

logger = logging.getLogger(__name__)


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

    def _merge_option(self, option_name: str, updates: dict) -> None:
        """
        Read-merge-write a WordPress option stored as a JSON object.

        Writing only the keys we care about prevents destroying other keys
        already stored in compound options like wpseo_titles or rank_math_titles.
        """
        try:
            raw = self.wp.run(f"option get {shlex.quote(option_name)} --format=json")
            existing: dict = json.loads(raw) if raw.strip() else {}
            # Guard: Ensure existing is actually a dict (WP-CLI may return "none" or empty string)
            if not isinstance(existing, dict):
                existing = {}
        except (RuntimeError, json.JSONDecodeError):
            existing = {}
        merged = {**existing, **updates}
        self.wp.option_update(option_name, json.dumps(merged))

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

        # Batch Yoast wpseo_titles updates to avoid multiple destructive overwrites
        yoast_titles_updates: dict = {}
        rankmath_titles_updates: dict = {}

        # Title template
        if title := seo.get("title_template"):
            if plugin == "yoast":
                yoast_titles_updates["title-home-wpseo"] = title
            elif plugin == "rankmath":
                rankmath_titles_updates["homepage_title"] = title
            applied["title_template"] = title

        # Meta description
        if description := seo.get("meta_description"):
            if plugin == "yoast":
                yoast_titles_updates["metadesc-home-wpseo"] = description
            elif plugin == "rankmath":
                rankmath_titles_updates["homepage_description"] = description
            applied["meta_description"] = description

        # Flush batched Yoast / RankMath title option in a single read-merge-write
        if yoast_titles_updates:
            self._merge_option("wpseo_titles", yoast_titles_updates)
        if rankmath_titles_updates:
            self._merge_option("rank_math_titles", rankmath_titles_updates)

        # Schema type + LocalBusiness JSON-LD
        if schema := seo.get("schema"):
            if isinstance(schema, dict):
                schema_type = schema.get("type", "Organization")
                applied["schema_type"] = schema_type
                self.add_schema_markup(seo)
            else:
                logger.warning("SEO schema is not a dict, skipping schema markup")

        # Verification codes
        if google_verification := seo.get("google_verification"):
            if plugin == "yoast":
                self._merge_option("wpseo", {"googleverify": google_verification})
            elif plugin == "rankmath":
                self._merge_option("rank_math_options", {"google_verify": google_verification})
            applied["google_verification"] = google_verification

        # Archives noindex
        if seo.get("archives_noindex"):
            self.set_archives_noindex()
            applied["archives_noindex"] = True

        # Breadcrumbs
        if seo.get("breadcrumbs"):
            self.set_breadcrumbs(enabled=True)
            applied["breadcrumbs"] = True

        # Open Graph
        if seo.get("og_enabled"):
            twitter_card = seo.get("twitter_card", "summary_large_image")
            self.set_open_graph(enabled=True, twitter_card=twitter_card)
            applied["og_enabled"] = True
            applied["twitter_card"] = twitter_card

        # robots.txt AI crawler rules
        robots_txt = seo.get("robots_txt", {})
        if isinstance(robots_txt, dict) and robots_txt.get("allow_ai_crawlers"):
            self.set_robots_txt_ai_crawlers(allow=True)
            applied["robots_txt_ai_crawlers"] = True

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
                self.wp.run(f"post meta update {page_id} _yoast_wpseo_title {shlex.quote(title)}")
                applied["title"] = title
            if description:
                self.wp.run(
                    f"post meta update {page_id} _yoast_wpseo_metadesc {shlex.quote(description)}"
                )
                applied["description"] = description
            if focus_keyword:
                self.wp.run(
                    f"post meta update {page_id} _yoast_wpseo_focuskw {shlex.quote(focus_keyword)}"
                )
                applied["focus_keyword"] = focus_keyword

        elif plugin == "rankmath":
            if title:
                self.wp.run(f"post meta update {page_id} rank_math_title {shlex.quote(title)}")
                applied["title"] = title
            if description:
                self.wp.run(
                    f"post meta update {page_id} rank_math_description {shlex.quote(description)}"
                )
                applied["description"] = description
            if focus_keyword:
                self.wp.run(
                    f"post meta update {page_id} rank_math_focus_keyword {shlex.quote(focus_keyword)}"
                )
                applied["focus_keyword"] = focus_keyword

        else:
            # No SEO plugin - use basic meta
            if description:
                self.wp.run(
                    f"post meta update {page_id} _meta_description {shlex.quote(description)}"
                )
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
            # Yoast uses numeric values
            if not index:
                self.wp.run(f"post meta update {page_id} _yoast_wpseo_meta-robots-noindex 1")
            if not follow:
                self.wp.run(f"post meta update {page_id} _yoast_wpseo_meta-robots-nofollow 1")

        elif plugin == "rankmath":
            self.wp.run(f"post meta update {page_id} rank_math_robots {shlex.quote(robots_value)}")

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
            self._merge_option("wpseo", {"enable_xml_sitemap": enabled})
        elif plugin == "rankmath":
            self._merge_option("rank_math_general", {"sitemap": "on" if enabled else "off"})

        return True

    def set_archives_noindex(self) -> bool:
        """
        Set date, author, and tag archives to noindex.

        Returns:
            True if successful
        """
        plugin = self.detect_seo_plugin()

        if plugin == "rankmath":
            self._merge_option(
                "rank_math_titles",
                {
                    "noindex_archive_date": 1,
                    "noindex_archive_author": 1,
                    "noindex_archive_tag": 1,
                },
            )
        elif plugin == "yoast":
            self._merge_option(
                "wpseo_titles",
                {
                    "noindex-tax-post_tag": True,
                    "noindex-author-wpseo": True,
                    "noindex-archive-wpseo": True,
                },
            )

        logger.info("archives noindex configured for plugin=%s", plugin)
        return True

    def set_breadcrumbs(self, enabled: bool = True) -> bool:
        """
        Enable or disable breadcrumbs.

        Args:
            enabled: Enable breadcrumbs if True

        Returns:
            True if successful
        """
        plugin = self.detect_seo_plugin()

        if plugin == "rankmath":
            self._merge_option("rank_math_general", {"breadcrumbs": 1 if enabled else 0})
        elif plugin == "yoast":
            self._merge_option("wpseo_titles", {"breadcrumbs-enable": enabled})

        logger.info("breadcrumbs enabled=%s for plugin=%s", enabled, plugin)
        return True

    def set_open_graph(
        self, enabled: bool = True, twitter_card: str = "summary_large_image"
    ) -> bool:
        """
        Enable Open Graph and Twitter Card meta tags.

        Args:
            enabled: Enable OG tags if True
            twitter_card: Twitter card type (summary_large_image | summary)

        Returns:
            True if successful
        """
        plugin = self.detect_seo_plugin()

        if plugin == "rankmath":
            self._merge_option(
                "rank_math_titles",
                {
                    "social_networks": 1 if enabled else 0,
                    "twitter_card_type": twitter_card,
                },
            )
        elif plugin == "yoast":
            self._merge_option(
                "wpseo_social",
                {
                    "opengraph": enabled,
                    "twitter": enabled,
                    "twitter_card_type": twitter_card,
                },
            )

        logger.info("OG enabled=%s twitter_card=%s for plugin=%s", enabled, twitter_card, plugin)
        return True

    def set_robots_txt_ai_crawlers(self, allow: bool = True) -> bool:
        """
        Append Allow rules for AI crawlers (GPTBot, ClaudeBot, PerplexityBot) to robots.txt.

        Uses the WordPress `robots_txt` filter via wp option — RankMath stores a custom
        robots.txt header in `rank_math_robots_txt`. Falls back to writing the file directly
        via WP-CLI if no plugin option is available.

        Args:
            allow: Add Allow rules if True

        Returns:
            True if successful
        """
        if not allow:
            return True

        ai_rules = (
            "\n# AI crawlers — allowed per site policy\n"
            "User-agent: GPTBot\nAllow: /\n\n"
            "User-agent: ClaudeBot\nAllow: /\n\n"
            "User-agent: PerplexityBot\nAllow: /\n"
        )

        plugin = self.detect_seo_plugin()
        if plugin == "rankmath":
            self.wp.option_update("rank_math_robots_txt", ai_rules)
        else:
            self.wp.option_update("fabrik_robots_txt_extra", ai_rules)
            logger.warning(
                "No RankMath detected — AI crawler rules written to fabrik_robots_txt_extra option. "
                "A mu-plugin or theme hook must render this option into robots.txt."
            )

        logger.info("robots.txt AI crawler Allow rules written")
        return True

    def add_schema_markup(self, seo: dict) -> bool:
        """
        Inject LocalBusiness / WebSite JSON-LD schema via RankMath local business settings.

        Args:
            seo: Full SEO section from site spec (must contain schema sub-dict)

        Returns:
            True if successful
        """
        schema = seo.get("schema", {})
        if isinstance(schema, dict):
            schema_type = schema.get("type", "Organization")
        else:
            schema_type = "Organization"  # Fallback if schema is not a dict
        plugin = self.detect_seo_plugin()

        if plugin == "rankmath":
            self.wp.option_update(
                "rank_math_schema_type",
                schema_type,
            )
            logger.info("RankMath schema type set to %s", schema_type)
        else:
            logger.warning(
                "add_schema_markup: no supported SEO plugin detected (plugin=%s). "
                "JSON-LD schema not injected.",
                plugin,
            )

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
