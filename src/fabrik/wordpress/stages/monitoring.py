"""Uptime Kuma monitoring registration stage."""

import logging
import os
from pathlib import Path

from fabrik.drivers.uptime_kuma import UptimeKumaClient
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


@time_stage
def apply(
    spec: dict, wp: object | None, api: object | None, build_dir: Path
) -> StageResult:
    """Register site HTTP monitor in Uptime Kuma."""
    result = StageResult(name="monitoring", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        domain = spec.get("site", {}).get("domain", "")
        monitoring = spec.get("monitoring", {})
        uk_config = monitoring.get("uptime_kuma", {})

        if not uk_config.get("enabled", False):
            result.skipped = True
            result.metadata["reason"] = "monitoring.uptime_kuma.enabled is false or missing"
            return result

        if not domain:
            result.warnings.append("site.domain not set — skipping monitoring stage")
            result.skipped = True
            return result

        site_url = f"https://{domain}"
        interval = uk_config.get("interval", 60)
        monitor_name = f"{domain} — HTTP"

        if dry_run:
            result.metadata["dry_run"] = {
                "monitor_name": monitor_name,
                "url": site_url,
                "interval": interval,
            }
            return result

        uk_url = os.getenv("UPTIME_KUMA_URL", "https://status.vps1.ocoron.com")
        uk_user = os.getenv("UPTIME_KUMA_USERNAME")
        uk_pass = os.getenv("UPTIME_KUMA_PASSWORD")

        if not uk_user or not uk_pass:
            result.warnings.append(
                "UPTIME_KUMA_USERNAME or UPTIME_KUMA_PASSWORD not set — skipping monitor creation"
            )
            result.skipped = True
            return result

        client = UptimeKumaClient(url=uk_url, username=uk_user, password=uk_pass)
        try:
            monitor_result = client.add_http_monitor(
                name=monitor_name,
                url=site_url,
                interval=interval,
            )
            result.metadata["monitor"] = monitor_result
            logger.info("Uptime Kuma monitor: %s → %s", monitor_name, monitor_result.get("status"))

            wp_cron_ping = uk_config.get("wp_cron_ping_url")
            if wp_cron_ping:
                wp_cron_interval = uk_config.get("wp_cron_interval", 300)
                cron_result = client.add_http_monitor(
                    name=f"{domain} — WP Cron",
                    url=wp_cron_ping,
                    interval=wp_cron_interval,
                )
                result.metadata["wp_cron_monitor"] = cron_result
                logger.info(
                    "Uptime Kuma WP Cron monitor: %s → %s",
                    wp_cron_ping,
                    cron_result.get("status"),
                )
        finally:
            client.disconnect()

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        logger.exception("monitoring stage failed")

    return result
