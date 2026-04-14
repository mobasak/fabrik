"""Post-deploy integrations stage: GSC, Bing, IndexNow, GA4 via site-provisioner."""

import logging
import os
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)

GA4_ARTIFACT_FILENAME = "ga4_measurement_id.txt"


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Register site with GSC, Bing, IndexNow, and GA4 via site-provisioner."""
    result = StageResult(name="post_deploy", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        domain = spec.get("site", {}).get("domain", "")
        post_deploy = spec.get("post_deploy", {})

        if not post_deploy:
            result.skipped = True
            result.metadata["reason"] = "post_deploy section not present in spec"
            return result

        if not domain:
            result.warnings.append("site.domain not set — skipping post_deploy stage")
            result.skipped = True
            return result

        setup_google = post_deploy.get("setup_google", True)
        setup_bing = post_deploy.get("setup_bing", True)
        setup_indexnow = post_deploy.get("setup_indexnow", True)
        setup_ga4 = post_deploy.get("setup_ga4", False)
        ga4_account_id = post_deploy.get("ga4_account_id") or os.getenv("GA4_ACCOUNT_ID")
        sitemap_url = post_deploy.get("sitemap_url", f"https://{domain}/sitemap.xml")

        if dry_run:
            result.metadata["dry_run"] = {
                "domain": domain,
                "setup_google": setup_google,
                "setup_bing": setup_bing,
                "setup_indexnow": setup_indexnow,
                "setup_ga4": setup_ga4,
                "ga4_account_id": ga4_account_id,
                "sitemap_url": sitemap_url,
            }
            return result

        from fabrik.drivers.dns import DNSClient

        target_ip = os.getenv("VPS_IP", "172.93.160.197")
        dns_client = DNSClient()

        provision_result = dns_client.provision(
            domain=domain,
            target_ip=target_ip,
            subdomains=["www"],
            setup_google=setup_google,
            setup_bing=setup_bing,
            setup_indexnow=setup_indexnow,
            setup_ga4=setup_ga4,
            ga4_account_id=ga4_account_id,
            sitemap_url=sitemap_url,
        )
        result.metadata["provision"] = provision_result

        ga4_measurement_id = (
            provision_result.get("ga4", {}).get("measurement_id")
            or provision_result.get("ga4_measurement_id")
        )
        if ga4_measurement_id:
            artifact_path = build_dir / GA4_ARTIFACT_FILENAME
            artifact_path.write_text(ga4_measurement_id)
            result.artifacts_written.append(str(artifact_path))
            result.metadata["ga4_measurement_id"] = ga4_measurement_id
            logger.info("GA4 measurement_id written: %s → %s", ga4_measurement_id, artifact_path)

        logger.info(
            "post_deploy complete for %s: google=%s bing=%s indexnow=%s ga4=%s",
            domain,
            setup_google,
            setup_bing,
            setup_indexnow,
            setup_ga4,
        )

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        logger.exception("post_deploy stage failed")

    return result


def read_ga4_measurement_id(build_dir: Path) -> str | None:
    """
    Read the GA4 measurement ID written by the post_deploy stage.

    Args:
        build_dir: Site build directory (e.g. build/sites/ocoron.com/)

    Returns:
        Measurement ID string (e.g. "G-XXXXXXXXXX") or None if not found
    """
    artifact_path = build_dir / GA4_ARTIFACT_FILENAME
    if artifact_path.exists():
        return artifact_path.read_text().strip() or None
    return None
