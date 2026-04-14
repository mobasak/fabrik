"""SEO settings application stage."""

import logging
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.seo import SEOApplicator
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Apply SEO settings."""
    result = StageResult(name="seo", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        site_name = (
            spec.get("site_name")
            or spec.get("site", {}).get("name")
            or spec.get("site", {}).get("domain", "").replace(".", "-")
        )
        seo = spec.get("seo", {})

        if not seo:
            # No SEO settings: not an error
            pass
        elif dry_run:
            # Dry-run: just log intent
            pass
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for seo stage")
            applicator = SEOApplicator(site_name, wp)

            # Check if SEO plugin available
            plugin = applicator.detect_seo_plugin()
            result.metadata["seo_plugin"] = plugin
            if plugin:
                sitemap_result = applicator.configure_sitemap(enabled=True)
                result.metadata["sitemap_configured"] = sitemap_result
                applied = applicator.apply_site_seo(seo)
                result.metadata["applied"] = applied
                logger.info("SEO applied via %s: %s", plugin, list(applied.keys()))
            else:
                result.warnings.append("No active SEO plugin detected — skipping SEO settings")
                logger.warning("No active SEO plugin detected (yoast/rankmath)")
                result.skipped = True

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
