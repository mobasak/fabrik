"""
Domain Provisioning - Full Automation for WordPress Sites.

Fully automated workflow via VPS DNS Manager:
- Step A: Create Cloudflare zone (POST /api/cloudflare/zones)
- Step B: Set Cloudflare nameservers at Namecheap (PUT /api/dns/{domain}/nameservers)
- Step C: Track Cloudflare zone status (GET /api/cloudflare/zones/{domain}/status)
- Step D: Apply DNS records when zone is active (POST /api/cloudflare/dns/{domain})

ALL operations go through VPS DNS Manager. No direct API calls.
No manual steps. No propagation waiting. Cloudflare status is the only gate.

Usage:
    from fabrik.wordpress.domain_setup import provision_domain, sync_dns

    # Full provisioning (new domain)
    result = provision_domain('tojlo.com')
    print(result.zone_id, result.nameservers, result.cloudflare_status)

    # Sync DNS records (when zone is active)
    dns_result = sync_dns('tojlo.com', vps_ip='172.93.160.197')
    print(dns_result.applied, dns_result.blocked_by_status)
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

import httpx


class ProvisionState(str, Enum):
    """Domain provisioning state machine."""

    INIT = "init"
    CF_ZONE_CREATED = "cf_zone_created"
    NC_NAMESERVERS_SET = "nc_nameservers_set"
    CF_STATUS_PENDING = "cf_status_pending"
    CF_STATUS_ACTIVE = "cf_status_active"
    DNS_SYNCED = "dns_synced"
    ERROR = "error"


@dataclass
class ProvisionResult:
    """Result of domain provisioning (Steps A-C)."""

    success: bool = False
    domain: str = ""
    state: ProvisionState = ProvisionState.INIT

    # Step A: Cloudflare zone
    zone_id: str | None = None
    zone_created: bool = False
    nameservers: list[str] = field(default_factory=list)

    # Step B: Namecheap nameservers
    registrar_ns_set: bool = False

    # Step C: Zone status
    cloudflare_status: Literal["pending", "active"] | None = None

    # Errors
    errors: list[str] = field(default_factory=list)


@dataclass
class DNSSyncResult:
    """Result of DNS sync (Step D)."""

    success: bool = False
    domain: str = ""
    applied: bool = False
    blocked_by_status: Literal["pending"] | None = None

    # Records
    a_record_created: bool = False
    www_record_created: bool = False
    records_preserved: int = 0

    # Errors
    errors: list[str] = field(default_factory=list)


class DomainProvisioner:
    """
    Full domain provisioning automation via VPS DNS Manager.

    ALL operations go through VPS DNS Manager - no direct API calls.

    State machine:
    INIT → CF_ZONE_CREATED → NC_NAMESERVERS_SET → CF_STATUS_PENDING/ACTIVE → DNS_SYNCED
    """

    def __init__(self, dns_manager_url: str | None = None):
        self.dns_manager_url = dns_manager_url or os.getenv(
            "DNS_MANAGER_URL", "https://dns.vps1.ocoron.com"
        )

        self._http = httpx.Client(timeout=30)

    def provision(self, domain: str) -> ProvisionResult:
        """
        Provision a domain: create zone, set nameservers, track status.

        Steps:
        A. Create Cloudflare zone (idempotent)
        B. Set Cloudflare nameservers at Namecheap
        C. Check zone status

        Args:
            domain: Root domain (e.g., "tojlo.com")

        Returns:
            ProvisionResult with zone_id, nameservers, status
        """
        result = ProvisionResult(domain=domain)

        try:
            # Step A: Create/ensure Cloudflare zone
            zone_result = self._step_a_create_zone(domain)
            result.zone_id = zone_result["zone_id"]
            result.zone_created = zone_result["created"]
            result.nameservers = zone_result["name_servers"]
            result.state = ProvisionState.CF_ZONE_CREATED

            # Step B: Set nameservers at Namecheap
            ns_result = self._step_b_set_nameservers(domain, result.nameservers)
            result.registrar_ns_set = ns_result
            result.state = ProvisionState.NC_NAMESERVERS_SET

            # Step C: Check zone status (use domain, not zone_id)
            status = self._step_c_check_status(domain)
            result.cloudflare_status = status

            if status == "active":
                result.state = ProvisionState.CF_STATUS_ACTIVE
            else:
                result.state = ProvisionState.CF_STATUS_PENDING

            result.success = True

        except Exception as e:
            result.state = ProvisionState.ERROR
            result.errors.append(str(e))

        return result

    def sync_dns(
        self, domain: str, vps_ip: str = "172.93.160.197", proxied: bool = True, force: bool = False
    ) -> DNSSyncResult:
        """
        Sync DNS records for a domain (Step D).

        Precondition: zone_status == 'active' (unless force=True)

        Args:
            domain: Root domain
            vps_ip: VPS IP address
            proxied: Enable Cloudflare proxy
            force: Apply even if zone is pending

        Returns:
            DNSSyncResult
        """
        result = DNSSyncResult(domain=domain)

        try:
            # Check zone status first via DNS Manager
            status = self._step_c_check_status(domain)

            if status != "active" and not force:
                result.blocked_by_status = "pending"
                result.applied = False
                return result

            # Get existing records
            existing = self._get_cloudflare_records(domain)
            result.records_preserved = len(existing)

            # Check/create A record
            root_a = [r for r in existing if r.get("type") == "A" and r.get("name") == domain]
            if not root_a:
                self._create_dns_record(domain, "A", domain, vps_ip, proxied)
                result.a_record_created = True
            elif root_a[0].get("content") != vps_ip:
                # Update existing
                self._delete_dns_record(domain, "A", domain)
                self._create_dns_record(domain, "A", domain, vps_ip, proxied)
                result.a_record_created = True

            # Check/create www CNAME
            www_records = [r for r in existing if r.get("name") == f"www.{domain}"]
            if not www_records:
                self._create_dns_record(domain, "CNAME", f"www.{domain}", domain, proxied)
                result.www_record_created = True

            result.applied = True
            result.success = True

        except Exception as e:
            result.errors.append(str(e))

        return result

    def _step_a_create_zone(self, domain: str) -> dict:
        """Step A: Create Cloudflare zone via DNS Manager."""
        url = f"{self.dns_manager_url}/api/cloudflare/zones"
        payload = {"domain": domain}

        response = self._http.post(url, json=payload)
        response.raise_for_status()

        data = response.json()
        return {
            "zone_id": data.get("zone_id"),
            "name_servers": data.get("name_servers", []),
            "status": data.get("status"),
            "created": data.get("created", False),
        }

    def _step_b_set_nameservers(self, domain: str, nameservers: list[str]) -> bool:
        """Step B: Set nameservers at Namecheap via DNS Manager."""
        url = f"{self.dns_manager_url}/api/dns/{domain}/nameservers"
        payload = {"nameservers": nameservers}

        response = self._http.put(url, json=payload)
        response.raise_for_status()

        data = response.json()
        return data.get("success", False)

    def _step_c_check_status(self, domain: str) -> str:
        """Step C: Check Cloudflare zone status via DNS Manager."""
        url = f"{self.dns_manager_url}/api/cloudflare/zones/{domain}/status"

        response = self._http.get(url)
        response.raise_for_status()

        data = response.json()
        return data.get("status", "pending")

    def _get_cloudflare_records(self, domain: str) -> list[dict]:
        """Get DNS records via VPS DNS Manager."""
        url = f"{self.dns_manager_url}/api/cloudflare/dns/{domain}"
        response = self._http.get(url)

        if response.status_code == 200:
            return response.json().get("records", [])
        return []

    def _create_dns_record(
        self, domain: str, record_type: str, name: str, content: str, proxied: bool = True
    ) -> dict:
        """Create DNS record via VPS DNS Manager."""
        url = f"{self.dns_manager_url}/api/cloudflare/dns/{domain}"
        payload = {
            "record_type": record_type,
            "name": name,
            "content": content,
            "ttl": 1,
            "proxied": proxied,
        }

        response = self._http.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def _delete_dns_record(self, domain: str, record_type: str, name: str) -> None:
        """Delete DNS record via VPS DNS Manager."""
        url = f"{self.dns_manager_url}/api/cloudflare/dns/{domain}"
        self._http.delete(url, params={"record_type": record_type, "name": name})

    def get_status(self, domain: str) -> dict:
        """Get current provisioning status for a domain via DNS Manager."""
        try:
            url = f"{self.dns_manager_url}/api/cloudflare/zones/{domain}/status"
            response = self._http.get(url)
            response.raise_for_status()

            data = response.json()
            records = self._get_cloudflare_records(domain)

            return {
                "domain": domain,
                "zone_id": data.get("zone_id"),
                "cloudflare_status": data.get("status"),
                "nameservers": data.get("name_servers", []),
                "record_count": len(records),
                "has_a_record": any(
                    r.get("type") == "A" and r.get("name") == domain for r in records
                ),
            }
        except Exception:
            return {
                "domain": domain,
                "zone_id": None,
                "cloudflare_status": None,
                "error": "Zone not found",
            }

    def close(self):
        """Close HTTP client."""
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# === Convenience functions ===


def provision_domain(domain: str) -> ProvisionResult:
    """
    Provision a domain: create zone, set nameservers, track status.

    Example:
        result = provision_domain('tojlo.com')
        print(f"Zone: {result.zone_id}")
        print(f"Nameservers: {result.nameservers}")
        print(f"Status: {result.cloudflare_status}")
    """
    with DomainProvisioner() as provisioner:
        return provisioner.provision(domain)


def sync_dns(
    domain: str, vps_ip: str = "172.93.160.197", proxied: bool = True, force: bool = False
) -> DNSSyncResult:
    """
    Sync DNS records for a domain.

    Example:
        result = sync_dns('tojlo.com')
        if result.applied:
            print("DNS records synced")
        elif result.blocked_by_status:
            print("Zone still pending")
    """
    with DomainProvisioner() as provisioner:
        return provisioner.sync_dns(domain, vps_ip, proxied, force)


def get_domain_status(domain: str) -> dict:
    """Get current status for a domain."""
    with DomainProvisioner() as provisioner:
        return provisioner.get_status(domain)


# === Legacy compatibility ===


@dataclass
class DomainSetupResult:
    """Legacy result class for backward compatibility."""

    success: bool = False
    domain: str = ""
    a_record_created: bool = False
    a_record_id: str | None = None
    existing_records_preserved: int = 0
    dns_resolving: bool = False
    resolved_ips: list[str] = field(default_factory=list)
    https_working: bool = False
    https_status_code: int | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DomainSetup:
    """Legacy class - wraps new DomainProvisioner."""

    def __init__(
        self,
        domain: str,
        vps_ip: str = "172.93.160.197",
        dns_manager_url: str | None = None,
        proxied: bool = True,
        dry_run: bool = False,
    ):
        self.domain = domain
        self.vps_ip = vps_ip
        self.proxied = proxied
        self.dry_run = dry_run
        self._provisioner = DomainProvisioner(dns_manager_url=dns_manager_url)
        self.result = DomainSetupResult(domain=domain)

    def configure_dns(self) -> DomainSetupResult:
        """Configure DNS using new provisioning system."""
        if self.dry_run:
            self.result.warnings.append("DRY RUN - no changes made")
            self.result.success = True
            return self.result

        try:
            # Check if zone exists, if not provision it
            status = self._provisioner.get_status(self.domain)

            if status.get("zone_id") is None:
                # Need to provision
                prov_result = self._provisioner.provision(self.domain)
                if not prov_result.success:
                    self.result.errors.extend(prov_result.errors)
                    return self.result

                self.result.warnings.append(f"Zone created: {prov_result.zone_id}")
                self.result.warnings.append(f"Nameservers: {prov_result.nameservers}")

                if prov_result.cloudflare_status == "pending":
                    self.result.warnings.append("Zone status: pending (DNS records queued)")

            # Sync DNS records
            dns_result = self._provisioner.sync_dns(
                self.domain,
                self.vps_ip,
                self.proxied,
                force=True,  # Apply even if pending for backward compat
            )

            self.result.a_record_created = dns_result.a_record_created
            self.result.existing_records_preserved = dns_result.records_preserved

            if dns_result.blocked_by_status:
                self.result.warnings.append("Zone pending - records may not resolve yet")

            # Quick verification
            import socket

            try:
                ips = socket.gethostbyname_ex(self.domain)[2]
                self.result.resolved_ips = ips
                self.result.dns_resolving = len(ips) > 0
            except socket.gaierror:
                self.result.dns_resolving = False

            # HTTPS check
            try:
                resp = self._provisioner._http.head(
                    f"https://{self.domain}", follow_redirects=True, timeout=10
                )
                self.result.https_working = True
                self.result.https_status_code = resp.status_code
            except Exception:
                self.result.https_working = False

            self.result.success = True

        except Exception as e:
            self.result.errors.append(str(e))

        return self.result

    def close(self):
        self._provisioner.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def setup_domain(
    domain: str, vps_ip: str = "172.93.160.197", proxied: bool = True, dry_run: bool = False
) -> DomainSetupResult:
    """Legacy function - uses new provisioning system."""
    with DomainSetup(domain, vps_ip, proxied=proxied, dry_run=dry_run) as setup:
        return setup.configure_dns()
