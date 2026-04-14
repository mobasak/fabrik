"""Analytics injection stage."""

import logging
import os
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.analytics import AnalyticsInjector
from fabrik.wordpress.stages import StageResult, time_stage
from fabrik.wordpress.stages.post_deploy import read_ga4_measurement_id

logger = logging.getLogger(__name__)


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Inject analytics codes."""
    result = StageResult(name="analytics", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        site_name = (
            spec.get("site_name")
            or spec.get("site", {}).get("name")
            or spec.get("site", {}).get("domain", "").replace(".", "-")
        )
        seo = spec.get("seo", {})

        ga4 = seo.get("ga4_id") or os.getenv("GA4_ID")

        if not ga4:
            ga4 = read_ga4_measurement_id(build_dir)
            if ga4:
                seo = dict(seo)
                seo["ga4_id"] = ga4
                result.metadata["ga4_source"] = "post_deploy_artifact"
                logger.info("GA4 ID sourced from post_deploy artifact: %s", ga4)

        gtm = seo.get("gtm_id")

        if not ga4 and not gtm:
            result.warnings.append("No analytics IDs defined")
            result.skipped = True
            return result
        elif dry_run:
            result.metadata["dry_run"] = {
                "ga4": ga4 or None,
                "gtm": gtm or None,
            }
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for analytics stage")
            injector = AnalyticsInjector(site_name, wp)
            applied = {}
            if ga4:
                applied["ga4"] = injector.inject_ga4(ga4)
            if gtm:
                applied["gtm"] = injector.inject_gtm(gtm)
            result.metadata["applied"] = applied

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
