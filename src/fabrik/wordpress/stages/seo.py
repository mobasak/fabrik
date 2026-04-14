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
            result.skipped = True
            result.metadata["skipped_reason"] = "no seo section in spec"
        elif dry_run:
            result.metadata["dry_run"] = {"seo_keys": list(seo.keys())}
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for seo stage")
            applicator = SEOApplicator(site_name, wp)

            # Resolve localized default_meta → flat keys that apply_site_seo() reads.
            # Spec may use seo.default_meta.en_US.{title,description} (rich form)
            # or seo.{title_template,meta_description} (flat form). Support both.
            seo_resolved = dict(seo)
            if default_meta := seo.get("default_meta"):
                primary_locale = spec.get("languages", {}).get("primary", "en_US")
                locale_meta = default_meta.get(primary_locale) or next(
                    iter(default_meta.values()), {}
                )
                if isinstance(locale_meta, dict):
                    if "title_template" not in seo_resolved and locale_meta.get("title"):
                        seo_resolved["title_template"] = locale_meta["title"]
                    if "meta_description" not in seo_resolved and locale_meta.get("description"):
                        seo_resolved["meta_description"] = locale_meta["description"]

            # Check if SEO plugin available
            plugin = applicator.detect_seo_plugin()
            result.metadata["seo_plugin"] = plugin
            if plugin:
                sitemap_result = applicator.configure_sitemap(enabled=True)
                result.metadata["sitemap_configured"] = sitemap_result
                applied = applicator.apply_site_seo(seo_resolved)
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
