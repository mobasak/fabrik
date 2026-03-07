"""DNS configuration stage."""

import os
from pathlib import Path

from fabrik.drivers.wordpress import WordPressClient
from fabrik.drivers.wordpress_api import WordPressAPIClient
from fabrik.wordpress.domain_setup import DomainSetup
from fabrik.wordpress.stages import StageResult, time_stage


@time_stage
def apply(
    spec: dict, wp: WordPressClient | None, api: WordPressAPIClient | None, build_dir: Path
) -> StageResult:
    """Configure DNS for the domain."""
    result = StageResult(name="dns", success=True)

    try:
        # Get VPS IP from spec or environment
        deployment = spec.get("deployment", {})
        vps_ip = deployment.get("vps_ip") or os.getenv("VPS_IP", "")
        proxied = deployment.get("cloudflare_proxy", True)
        dry_run = spec.get("dry_run", False)
        domain = spec.get("site", {}).get("domain", "")

        if not vps_ip:
            result.errors.append("VPS_IP not configured")
            result.success = False
            return result

        if dry_run:
            # Dry-run: just log intent
            pass
        else:
            setup = DomainSetup(domain, vps_ip=vps_ip, proxied=proxied, dry_run=False)
            dns_result = setup.configure_dns()
            setup.close()

            if not dns_result.success:
                result.errors.extend(dns_result.errors)
                result.success = False

    except Exception as e:
        result.success = False
        result.errors.append(str(e))

    return result
