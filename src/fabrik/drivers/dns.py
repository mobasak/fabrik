"""
DNS Client - Wrapper for DNS Manager service.

This client calls the dns-manager service at VPS (dns.vps1.ocoron.com),
which provides unified access to both Namecheap and Cloudflare DNS.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class DNSRecord:
    """DNS record representation."""

    type: str
    name: str
    value: str
    ttl: int = 1800


class DNSClient:
    """
    DNS management client that wraps the DNS Manager service API.

    The DNS Manager service is deployed at VPS and handles:
    - Multi-provider DNS authentication (Namecheap, Cloudflare)
    - Rate limiting
    - Safe record merging (doesn't overwrite existing records)

    Usage:
        dns = DNSClient()

        # Add subdomain
        dns.add_subdomain("ocoron.com", "api", "172.93.160.197")

        # Get all records
        records = dns.get_records("ocoron.com")

        # List domains
        domains = dns.list_domains()
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize DNS client.

        Args:
            base_url: DNS Manager service URL. Defaults to DNS_MANAGER_URL env var
                     or https://dns.vps1.ocoron.com
            token: API token for authentication. Defaults to DNS_MANAGER_TOKEN env var.
                   If not set, requests are made without authentication (for local/dev use).
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv(
            "DNS_MANAGER_URL", os.getenv("NAMECHEAP_API_URL", "https://dns.vps1.ocoron.com")
        )
        self.token = token or os.getenv("DNS_MANAGER_TOKEN")
        self.timeout = timeout

        # Build headers - include auth if token is available
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        else:
            logger.warning(
                "DNS_MANAGER_TOKEN not set — DNS requests will be unauthenticated. "
                "Set DNS_MANAGER_TOKEN in .env for production use."
            )

        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request to DNS Manager service."""
        url = f"{self.base_url}{endpoint}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Health & Status
    # =========================================================================

    def health(self) -> dict[str, Any]:
        """Check DNS Manager service health."""
        return self._request("GET", "/health")

    def get_rate_limit(self) -> dict[str, Any]:
        """Get current rate limit status."""
        return self._request("GET", "/ratelimit")

    # =========================================================================
    # Domain Management
    # =========================================================================

    def list_domains(self) -> list[dict[str, Any]]:
        """
        List all domains in account.

        Returns:
            List of domain info dicts with keys:
            - domain: domain name
            - expires: expiration date
            - autorenew: bool
            - locked: bool
        """
        result = self._request("GET", "/api/domains")
        return result.get("domains", [])

    def get_domain(self, domain: str) -> dict[str, Any]:
        """Get details for specific domain."""
        return self._request("GET", f"/api/domains/{domain}")

    def check_availability(self, domains: list[str]) -> dict[str, bool]:
        """
        Check domain availability for registration.

        Args:
            domains: List of domain names to check

        Returns:
            Dict mapping domain -> available (bool)
        """
        result = self._request("POST", "/api/domains/check", json={"domains": domains})
        return result.get("availability", {})

    # =========================================================================
    # DNS Records
    # =========================================================================

    def get_records(self, domain: str) -> list[dict[str, Any]]:
        """
        Get all DNS records for domain.

        Args:
            domain: Domain name (e.g., "ocoron.com")

        Returns:
            List of record dicts with keys: type, name, value, ttl
        """
        result = self._request("GET", f"/api/dns/{domain}")
        return result.get("records", [])

    def add_subdomain(self, domain: str, subdomain: str, ip: str) -> dict[str, Any]:
        """
        Add A record for subdomain.

        This is the most common operation - point subdomain.domain.com to an IP.
        Uses the DNS Manager service's safe merge logic.

        Args:
            domain: Base domain (e.g., "ocoron.com")
            subdomain: Subdomain name (e.g., "api" for api.ocoron.com)
            ip: IP address to point to

        Returns:
            Result dict with success status and message

        Example:
            dns.add_subdomain("ocoron.com", "api.vps1", "172.93.160.197")
            # Creates: api.vps1.ocoron.com -> 172.93.160.197
        """
        return self._request(
            "POST", f"/api/dns/{domain}/subdomain", json={"subdomain": subdomain, "ip": ip}
        )

    def set_records(self, domain: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Set DNS records for domain (replaces all records).

        WARNING: This replaces ALL records. Use add_subdomain for safe additions.

        Args:
            domain: Domain name
            records: List of record dicts with: type, name, value, ttl

        Returns:
            Result dict with success status
        """
        return self._request("PUT", f"/api/dns/{domain}", json={"records": records})

    def delete_records(self, domain: str) -> dict[str, Any]:
        """Delete all DNS records for domain. USE WITH CAUTION."""
        return self._request("DELETE", f"/api/dns/{domain}")

    # =========================================================================
    # Nameservers
    # =========================================================================

    def get_nameservers(self, domain: str) -> list[str]:
        """Get nameservers for domain."""
        result = self._request("GET", f"/api/dns/{domain}/nameservers")
        return result.get("nameservers", [])

    def set_nameservers(self, domain: str, nameservers: list[str]) -> dict[str, Any]:
        """
        Set custom nameservers for domain.

        Use this when migrating to Cloudflare or other DNS provider.

        Args:
            domain: Domain name
            nameservers: List of nameserver hostnames
        """
        return self._request(
            "PUT", f"/api/dns/{domain}/nameservers", json={"nameservers": nameservers}
        )

    # =========================================================================
    # Account
    # =========================================================================

    def get_balance(self) -> dict[str, Any]:
        """Get account balance."""
        return self._request("GET", "/api/account/balance")

    # =========================================================================
    # Cloudflare — Zone Management
    # =========================================================================

    def cloudflare_health(self) -> dict[str, Any]:
        """Check Cloudflare API health via dns-manager."""
        return self._request("GET", "/api/cloudflare/health")

    def list_zones(self) -> list[dict[str, Any]]:
        """List all Cloudflare zones."""
        result = self._request("GET", "/api/cloudflare/zones")
        return result.get("zones", [])

    def get_zone_status(self, domain: str) -> dict[str, Any]:
        """Get Cloudflare zone status and nameservers."""
        return self._request("GET", f"/api/cloudflare/zones/{domain}/status")

    def get_cloudflare_records(self, domain: str) -> list[dict[str, Any]]:
        """Get all Cloudflare DNS records for domain."""
        result = self._request("GET", f"/api/cloudflare/dns/{domain}")
        return result.get("records", [])

    # =========================================================================
    # Cloudflare — Provisioning (Fabrik deployment workflow)
    # =========================================================================

    def provision(
        self,
        domain: str,
        target_ip: str,
        subdomains: list[str] | None = None,
        enable_dnssec: bool = True,
        enable_tiered_cache: bool = True,
        enable_page_shield: bool = True,
        create_threat_rule: bool = True,
        threat_threshold: int = 50,
    ) -> dict[str, Any]:
        """
        Provision a website with Cloudflare enterprise features.

        Single call that sets up everything needed before Coolify deployment:
        - Creates/ensures Cloudflare zone
        - Creates A records for root and subdomains (proxied)
        - Enables DNSSEC, Smart Tiered Cache, Page Shield
        - Creates WAF threat score rule

        Args:
            domain: Root domain (e.g., "newsite.com")
            target_ip: VPS IP address to point DNS to
            subdomains: Optional list of subdomains (e.g., ["www", "api"])
            enable_dnssec: Enable DNSSEC
            enable_tiered_cache: Enable Smart Tiered Cache (CDN)
            enable_page_shield: Enable Page Shield (script monitoring)
            create_threat_rule: Create WAF rule blocking high threat scores
            threat_threshold: Threat score threshold (0-100, default 50)

        Returns:
            Dict with success, dns_records, features_enabled, ready_for_coolify

        Example:
            dns.provision("newsite.com", "172.93.160.197", ["www", "api"])
        """
        payload = {
            "target_ip": target_ip,
            "subdomains": subdomains or [],
            "enable_dnssec": enable_dnssec,
            "enable_tiered_cache": enable_tiered_cache,
            "enable_page_shield": enable_page_shield,
            "create_threat_rule": create_threat_rule,
            "threat_threshold": threat_threshold,
        }
        return self._request("POST", f"/api/cloudflare/zones/{domain}/provision", json=payload)

    def check_ready(self, domain: str) -> dict[str, Any]:
        """
        Check if domain is ready for Coolify deployment.

        Verifies zone is active, A records exist, and security features enabled.

        Args:
            domain: Root domain (e.g., "newsite.com")

        Returns:
            Dict with ready_for_deployment (bool), zone_status, dns_records, features

        Example:
            result = dns.check_ready("newsite.com")
            if result["ready_for_deployment"]:
                # proceed with Coolify deploy
        """
        return self._request("GET", f"/api/cloudflare/zones/{domain}/ready")

    # =========================================================================
    # Domain Registration
    # =========================================================================

    def get_pricing(self, tld: str) -> dict[str, Any]:
        """
        Get registration pricing for a TLD.

        Args:
            tld: Top-level domain (e.g., "com", "net", "io")

        Returns:
            Dict with tld and pricing info
        """
        return self._request("GET", f"/api/domains/pricing/{tld}")

    def register_domain(
        self,
        domain: str,
        years: int = 1,
        nameservers: list[str] | None = None,
        add_whoisguard: bool = True,
        contact: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Register a new domain via dns-manager.

        dns-manager selects the registrar internally. Fabrik does not
        need to know which registrar is used.

        Args:
            domain: Domain to register (e.g., "newsite.com")
            years: Registration period in years
            nameservers: Custom nameservers (dns-manager picks defaults if omitted)
            add_whoisguard: Enable WHOIS privacy
            contact: Registrant contact info dict with keys:
                     FirstName, LastName, Address1, City, StateProvince,
                     PostalCode, Country, Phone, EmailAddress

        Returns:
            Dict with success, domain, registered, domain_id, order_id, charged_amount

        Example:
            dns.register_domain("newsite.com")
        """
        payload: dict[str, Any] = {
            "domain": domain,
            "years": years,
            "add_whoisguard": add_whoisguard,
        }
        if nameservers:
            payload["nameservers"] = nameservers
        if contact:
            payload["contact"] = contact

        return self._request("POST", "/api/domains/register", json=payload)

    # =========================================================================
    # Context Manager
    # =========================================================================

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._client.close()

    def close(self):
        """Close HTTP client."""
        self._client.close()


# Convenience function for quick operations
def add_dns_record(domain: str, subdomain: str, ip: str) -> dict[str, Any]:
    """
    Quick helper to add a subdomain record.

    Example:
        from fabrik.drivers.dns import add_dns_record
        add_dns_record("ocoron.com", "api.vps1", "172.93.160.197")
    """
    with DNSClient() as dns:
        return dns.add_subdomain(domain, subdomain, ip)
