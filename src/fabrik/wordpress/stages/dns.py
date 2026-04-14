"""DNS configuration stage — syncs A record and www CNAME via DNSClient (authenticated)."""

import logging
import os
from pathlib import Path

from fabrik.drivers.dns import DNSClient
from fabrik.wordpress.stages import StageResult, time_stage

logger = logging.getLogger(__name__)


@time_stage
def apply(
    spec: dict, wp: object | None, api: object | None, build_dir: Path
) -> StageResult:
    """Sync DNS A record and www CNAME via site-provisioner (DNSClient)."""
    result = StageResult(name="dns", success=True)

    try:
        deployment = spec.get("deployment", {})
        vps_ip = deployment.get("vps_ip") or os.getenv("VPS_IP", "")
        proxied = deployment.get("cloudflare_proxy", True)
        dry_run = spec.get("dry_run", False)
        domain = spec.get("site", {}).get("domain", "")

        if not domain:
            result.errors.append("site.domain not configured in spec")
            result.success = False
            return result

        if not vps_ip:
            result.errors.append(
                "VPS_IP not configured — set deployment.vps_ip in spec or VPS_IP env var"
            )
            result.success = False
            return result

        if dry_run:
            result.metadata["dry_run"] = {
                "domain": domain,
                "vps_ip": vps_ip,
                "proxied": proxied,
                "actions": ["add_subdomain (root A)", "add_subdomain (www CNAME)"],
            }
            return result

        client = DNSClient()
        try:
            existing_records = client.get_cloudflare_records(domain)
            result.metadata["existing_records"] = len(existing_records)

            root_a = [
                r for r in existing_records
                if r.get("type") == "A" and r.get("name") in (domain, f"{domain}.")
            ]
            if not root_a:
                client.add_record(domain, "A", domain, vps_ip, proxied=proxied)
                result.metadata["a_record_created"] = True
                logger.info("DNS A record created: %s → %s", domain, vps_ip)
            else:
                result.metadata["a_record_created"] = False
                logger.info("DNS A record already exists for %s", domain)

            www_records = [
                r for r in existing_records
                if r.get("name") in (f"www.{domain}", f"www.{domain}.")
            ]
            if not www_records:
                client.add_subdomain(domain, "www", vps_ip, proxied=proxied)
                result.metadata["www_record_created"] = True
                logger.info("DNS www record created for %s", domain)
            else:
                result.metadata["www_record_created"] = False
                logger.info("DNS www record already exists for %s", domain)

            ready = client.check_ready(domain)
            result.metadata["ready"] = ready
            if not ready.get("ready_for_deployment"):
                result.warnings.append(
                    f"Domain {domain} zone not yet active in Cloudflare. "
                    "Nameservers may not have propagated. Re-run dns stage later."
                )

        finally:
            client.close()

    except Exception as e:
        result.success = False
        result.errors.append(str(e))
        logger.exception("dns stage failed")

    return result
