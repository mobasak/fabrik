"""
WordPress Analytics Injector - Add tracking codes to WordPress.

Handles:
- Google Analytics 4 (GA4)
- Google Tag Manager
- Custom tracking scripts
"""

from dataclasses import dataclass

from fabrik.drivers.wordpress import WordPressClient, get_wordpress_client


@dataclass
class AnalyticsConfig:
    """Analytics configuration."""

    ga4_id: str = ""
    gtm_id: str = ""
    custom_head: str = ""
    custom_body: str = ""


class AnalyticsInjector:
    """
    Inject analytics and tracking codes into WordPress.

    Uses theme/plugin hooks or custom code injection methods.

    Usage:
        injector = AnalyticsInjector("wp-test")
        injector.inject_ga4("G-XXXXXXXXXX")
        injector.inject_gtm("GTM-XXXXXXX")
    """

    GA4_TEMPLATE = """<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id={ga4_id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga4_id}');
</script>"""

    GTM_HEAD_TEMPLATE = """<!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){{w[l]=w[l]||[];w[l].push({{'gtm.start':
new Date().getTime(),event:'gtm.js'}});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
}})(window,document,'script','dataLayer','{gtm_id}');</script>
<!-- End Google Tag Manager -->"""

    GTM_BODY_TEMPLATE = """<!-- Google Tag Manager (noscript) -->
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id={gtm_id}"
height="0" width="0" style="display:none;visibility:hidden"></iframe></noscript>
<!-- End Google Tag Manager (noscript) -->"""

    def __init__(self, site_name: str, wp_client: WordPressClient | None = None):
        """
        Initialize analytics injector.

        Args:
            site_name: WordPress site name
            wp_client: Optional WP-CLI client
        """
        self.site_name = site_name
        self.wp = wp_client or get_wordpress_client(site_name)

    def inject_ga4(self, ga4_id: str) -> bool:
        """
        Inject Google Analytics 4 tracking code.

        Args:
            ga4_id: GA4 Measurement ID (G-XXXXXXXXXX)

        Returns:
            True if successful
        """
        if not ga4_id:
            return False

        # Try SEO plugin first (cleanest method)
        if self._inject_via_seo_plugin("ga4", ga4_id):
            return True

        # Fall back to wp_head option
        script = self.GA4_TEMPLATE.format(ga4_id=ga4_id)
        return self._inject_head_code(script, "ga4")

    def inject_gtm(self, gtm_id: str) -> bool:
        """
        Inject Google Tag Manager code.

        Args:
            gtm_id: GTM Container ID (GTM-XXXXXXX)

        Returns:
            True if successful
        """
        if not gtm_id:
            return False

        # Try SEO plugin first
        if self._inject_via_seo_plugin("gtm", gtm_id):
            return True

        # Fall back to options
        head_code = self.GTM_HEAD_TEMPLATE.format(gtm_id=gtm_id)
        body_code = self.GTM_BODY_TEMPLATE.format(gtm_id=gtm_id)

        self._inject_head_code(head_code, "gtm_head")
        self._inject_body_code(body_code, "gtm_body")

        return True

    def _inject_via_seo_plugin(self, tracking_type: str, tracking_id: str) -> bool:
        """Try to inject via SEO plugin settings."""
        plugins = self.wp.plugin_list()

        for plugin in plugins:
            name = plugin.get("name", "")
            status = plugin.get("status", "")

            if status != "active":
                continue

            # RankMath has built-in analytics settings
            if "rank-math" in name.lower():
                if tracking_type == "ga4":
                    self.wp.option_update("rank_math_google_analytics", tracking_id)
                    return True

            # Yoast doesn't have built-in GA, needs separate plugin

        return False

    def _inject_head_code(self, code: str, key: str) -> bool:
        """
        Inject code into wp_head via option.

        Uses a custom option that can be hooked by theme/plugin.
        """
        escaped_code = code.replace("'", "'\\''")
        option_name = f"fabrik_head_code_{key}"

        try:
            self.wp.option_update(option_name, escaped_code)
            return True
        except RuntimeError:
            return False

    def _inject_body_code(self, code: str, key: str) -> bool:
        """Inject code into wp_body_open via option."""
        escaped_code = code.replace("'", "'\\''")
        option_name = f"fabrik_body_code_{key}"

        try:
            self.wp.option_update(option_name, escaped_code)
            return True
        except RuntimeError:
            return False

    def inject_custom_code(
        self,
        head_code: str = "",
        body_code: str = "",
        footer_code: str = "",
    ) -> dict:
        """
        Inject custom tracking/script code.

        Args:
            head_code: Code to inject in <head>
            body_code: Code to inject after <body>
            footer_code: Code to inject before </body>

        Returns:
            Dict of injection results
        """
        results = {}

        if head_code:
            results["head"] = self._inject_head_code(head_code, "custom_head")

        if body_code:
            results["body"] = self._inject_body_code(body_code, "custom_body")

        if footer_code:
            escaped = footer_code.replace("'", "'\\''")
            try:
                self.wp.option_update("fabrik_footer_code", escaped)
                results["footer"] = True
            except RuntimeError:
                results["footer"] = False

        return results

    def apply_from_spec(self, seo: dict) -> dict:
        """
        Apply analytics from SEO section of site spec.

        Args:
            seo: SEO section containing analytics config

        Returns:
            Dict of applied analytics
        """
        results = {}
        analytics = seo.get("analytics", {})

        # GA4
        if ga4_id := analytics.get("ga4") or analytics.get("google_analytics") or seo.get("ga4_id"):
            results["ga4"] = self.inject_ga4(ga4_id)

        # GTM
        if (
            gtm_id := analytics.get("gtm")
            or analytics.get("google_tag_manager")
            or seo.get("gtm_id")
        ):
            results["gtm"] = self.inject_gtm(gtm_id)

        return results


def inject_analytics(site_name: str, seo: dict) -> dict:
    """
    Convenience function to inject analytics from spec.

    Args:
        site_name: WordPress site name
        seo: SEO section from site spec

    Returns:
        Dict of injection results
    """
    injector = AnalyticsInjector(site_name)
    return injector.apply_from_spec(seo)
