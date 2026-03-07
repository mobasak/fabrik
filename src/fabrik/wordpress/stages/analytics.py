"""Analytics injection stage."""

from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.analytics import AnalyticsInjector
from fabrik.wordpress.stages import StageResult, time_stage


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

        ga4 = seo.get("ga4_id")
        gtm = seo.get("gtm_id")

        if not ga4 and not gtm:
            result.warnings.append("  No analytics IDs defined")
            result.skipped = True
            return result
        elif dry_run:
            # Dry-run: just log intent
            pass
        else:
            if not wp:
                raise RuntimeError("WordPressClient required for analytics stage")
            injector = AnalyticsInjector(site_name, wp)
            injector.apply_from_spec(seo)

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
