"""Gatus monitoring registration stage."""

import logging
import os
from pathlib import Path

from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


@time_stage
def apply(spec: dict, wp: object | None, api: object | None, build_dir: Path) -> StageResult:
    """Register site HTTP monitor in Gatus."""
    result = StageResult(name="monitoring", success=True)

    try:
        dry_run = spec.get("dry_run", False)
        domain = spec.get("site", {}).get("domain", "")
        monitoring = spec.get("monitoring", {})
        gatus_config = monitoring.get("gatus", {})

        if not gatus_config.get("enabled", False):
            result.skipped = True
            result.metadata["reason"] = "monitoring.gatus.enabled is false or missing"
            return result

        if not domain:
            result.warnings.append("site.domain not set — skipping monitoring stage")
            result.skipped = True
            return result

        site_url = f"https://{domain}"
        interval = gatus_config.get("interval", 60)
        monitor_name = f"{domain} — HTTP"

        if dry_run:
            result.metadata["dry_run"] = {
                "monitor_name": monitor_name,
                "url": site_url,
                "interval": interval,
            }
            return result

        gatus_url = os.getenv("GATUS_URL", "https://status.vps1.ocoron.com")
        gatus_user = os.getenv("GATUS_USERNAME")
        gatus_pass = os.getenv("GATUS_PASSWORD")

        if not gatus_user or not gatus_pass:
            result.warnings.append(
                "GATUS_USERNAME or GATUS_PASSWORD not set — skipping monitor creation"
            )
            result.skipped = True
            return result

        try:
            from fabrik.drivers.gatus import GatusClient  # noqa: PLC0415 — optional driver
        except ImportError as exc:
            result.warnings.append(f"Gatus driver not available ({exc}); skipping monitor creation")
            result.skipped = True
            return result

        client = GatusClient(url=gatus_url, username=gatus_user, password=gatus_pass)
        try:
            monitor_result = client.add_http_monitor(
                name=monitor_name,
                url=site_url,
                interval=interval,
            )
            result.metadata["monitor"] = monitor_result
            logger.info("Gatus monitor: %s → %s", monitor_name, monitor_result.get("status"))

            wp_cron_ping = gatus_config.get("wp_cron_ping_url")
            if wp_cron_ping:
                wp_cron_interval = gatus_config.get("wp_cron_interval", 300)
                cron_result = client.add_http_monitor(
                    name=f"{domain} — WP Cron",
                    url=wp_cron_ping,
                    interval=wp_cron_interval,
                )
                result.metadata["wp_cron_monitor"] = cron_result
                logger.info(
                    "Gatus WP Cron monitor: %s → %s",
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
