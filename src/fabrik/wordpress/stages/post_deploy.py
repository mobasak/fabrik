"""Post-deploy integrations stage: sitemap resubmission + GA4 ID retrieval via site-provisioner."""

import logging
from pathlib import Path

from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)

GA4_ARTIFACT_FILENAME = "ga4_measurement_id.txt"


@time_stage
def apply(
    spec: dict, wp: object | None, api: object | None, build_dir: Path
) -> StageResult:
    """Resubmit sitemap and retrieve GA4 measurement ID from site-provisioner integrations."""
    result = StageResult(name="post_deploy", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        domain = spec.get("site", {}).get("domain", "")
        post_deploy = spec.get("post_deploy", {})

        if not domain:
            result.warnings.append("site.domain not set — skipping post_deploy stage")
            result.skipped = True
            return result

        sitemap_url = post_deploy.get("sitemap_url", f"https://{domain}/sitemap.xml")

        if dry_run:
            result.metadata["dry_run"] = {
                "domain": domain,
                "sitemap_url": sitemap_url,
                "actions": ["update_sitemap", "get_integrations (GA4 ID)"],
            }
            return result

        from fabrik.drivers.dns import DNSClient

        dns_client = DNSClient()
        try:
            sitemap_result = dns_client.update_sitemap(domain, sitemap_url)
            result.metadata["sitemap"] = sitemap_result
            logger.info("sitemap resubmitted for %s → %s", domain, sitemap_url)

            integrations = dns_client.get_integrations(domain)
            result.metadata["integrations"] = integrations

            ga4_measurement_id = integrations.get("google_analytics", {}).get("measurement_id")
            if ga4_measurement_id:
                artifact_path = build_dir / GA4_ARTIFACT_FILENAME
                artifact_path.write_text(ga4_measurement_id, encoding="utf-8")
                result.artifacts_written.append(str(artifact_path))
                result.metadata["ga4_measurement_id"] = ga4_measurement_id
                logger.info("GA4 measurement_id written: %s → %s", ga4_measurement_id, artifact_path)
            else:
                result.warnings.append(
                    f"GA4 measurement_id not found in site-provisioner integrations for {domain}. "
                    "Run 'fabrik domain integrations <domain>' to verify GA4 was set up during provisioning."
                )
        finally:
            dns_client.close()

        logger.info("post_deploy complete for %s", domain)

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
