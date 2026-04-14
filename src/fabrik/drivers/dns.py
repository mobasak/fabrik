"""
DNS Client - Wrapper for Site Provisioner service.

This client calls the site-provisioner service at VPS (dns.vps1.ocoron.com),
which provides unified access to both Namecheap and Cloudflare DNS.
"""

import json
import logging
import os
import subprocess
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
    DNS management client that wraps the Site Provisioner service API.

    The Site Provisioner service is deployed at VPS and handles:
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
        api_key: str | None = None,
        timeout: float = 30.0,
        ssh_host: str = "vps",
    ):
        """
        Initialize DNS client.

        Args:
            base_url: Site Provisioner URL. Defaults to SITE_PROVISIONER_URL env var
                     or https://dns.vps1.ocoron.com
            api_key: API key sent as X-API-Key header. Defaults to SITE_PROVISIONER_API_KEY
                     env var. If not set, requests are unauthenticated (local/dev only).
            timeout: Request timeout in seconds
            ssh_host: SSH host alias for VPS (used when SITE_PROVISIONER_INTERNAL_URL is set)
        """
        resolved_url: str = (
            base_url
            or os.getenv("SITE_PROVISIONER_URL", "https://dns.vps1.ocoron.com")
            or "https://dns.vps1.ocoron.com"
        )
        self.base_url = resolved_url.rstrip("/")
        self.api_key = api_key or os.getenv("SITE_PROVISIONER_API_KEY")
        self.timeout = timeout
        self.ssh_host = ssh_host

        # SITE_PROVISIONER_INTERNAL_URL bypasses Traefik IP allowlist by calling
        # directly through SSH to the container port (e.g. http://localhost:8001).
        # Set this when running from WSL where the public URL is blocked by iptables.
        self._internal_url: str | None = os.getenv("SITE_PROVISIONER_INTERNAL_URL")
        if self._internal_url:
            self._internal_url = self._internal_url.rstrip("/")
            logger.debug("DNS client: using SSH proxy via %s → %s", ssh_host, self._internal_url)

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        else:
            logger.warning(
                "SITE_PROVISIONER_API_KEY not set — requests will be unauthenticated. "
                "Set SITE_PROVISIONER_API_KEY in .env for production use."
            )

        self._headers = headers
        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _request_via_ssh(self, method: str, url: str, body: dict | None = None) -> dict[str, Any]:
        """Proxy an HTTP request through SSH to bypass Traefik IP allowlist."""
        header_args = " ".join(f'-H "{k}: {v}"' for k, v in self._headers.items())
        data_arg = ""
        if body is not None:
            escaped = json.dumps(body).replace("'", "'\\''")
            data_arg = f"-d '{escaped}'"
        cmd = f"curl -s -X {method} {header_args} {data_arg} '{url}'"
        result = subprocess.run(
            ["ssh", self.ssh_host, cmd],
            capture_output=True,
            text=True,
            timeout=int(self.timeout),
            check=False,
        )
        if result.returncode != 0:
            msg = f"SSH proxy request failed: {result.stderr.strip()}"
            raise RuntimeError(msg)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            msg = f"SSH proxy returned non-JSON: {result.stdout[:200]}"
            raise RuntimeError(msg) from exc

    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request to Site Provisioner service.

        When SITE_PROVISIONER_INTERNAL_URL is set, proxies the call through SSH
        to bypass Traefik IP allowlist restrictions (WSL → VPS pipeline use case).
        """
        if self._internal_url:
            url = f"{self._internal_url}{endpoint}"
            body = kwargs.get("json")
            return self._request_via_ssh(method, url, body)

        url = f"{self.base_url}{endpoint}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    # =========================================================================
    # Health & Status
    # =========================================================================

    def health(self) -> dict[str, Any]:
        """Check Site Provisioner service health."""
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

    def check_availability(self, domain: str) -> dict[str, Any]:
        """
        Check domain availability for registration across all registrars.

        Args:
            domain: Domain name to check (e.g., "newsite.com")

        Returns:
            Dict with available (bool), prices per registrar, cheapest registrar
        """
        return self._request("POST", "/api/domains/check", json={"domain": domain})

    # =========================================================================
    # DNS Records
    # =========================================================================

    def get_records(self, domain: str) -> list[dict[str, Any]]:
        """
        Get all Cloudflare DNS records for domain.

        Args:
            domain: Domain name (e.g., "ocoron.com")

        Returns:
            List of record dicts with keys: type, name, content, proxied, ttl
        """
        result = self._request("GET", f"/api/cloudflare/dns/{domain}")
        return result.get("records", [])

    def add_subdomain(
        self, domain: str, subdomain: str, ip: str, proxied: bool = False
    ) -> dict[str, Any]:
        """
        Add A record for subdomain via Cloudflare.

        Args:
            domain: Base domain (e.g., "ocoron.com")
            subdomain: Subdomain name (e.g., "api" for api.ocoron.com)
            ip: IP address to point to
            proxied: Whether to proxy through Cloudflare (default False)

        Returns:
            Result dict with success status

        Example:
            dns.add_subdomain("ocoron.com", "api", "172.93.160.197")
        """
        return self._request(
            "POST",
            f"/api/cloudflare/dns/{domain}/subdomain",
            json={"subdomain": subdomain, "ip": ip, "proxied": proxied},
        )

    def add_record(
        self,
        domain: str,
        record_type: str,
        name: str,
        content: str,
        proxied: bool = False,
        ttl: int = 1,
    ) -> dict[str, Any]:
        """
        Add or update a Cloudflare DNS record (idempotent).

        Args:
            domain: Root domain (e.g., "example.com")
            record_type: Record type — A, AAAA, CNAME, MX, TXT, NS, CAA
            name: Record name; use "@" for the root domain
            content: Record value (IP, hostname, text, etc.)
            proxied: Proxy through Cloudflare CDN
            ttl: TTL in seconds; 1 = automatic

        Returns:
            Result dict from site-provisioner
        """
        return self._request(
            "POST",
            f"/api/cloudflare/dns/{domain}",
            json={
                "record_type": record_type,
                "name": name,
                "content": content,
                "proxied": proxied,
                "ttl": ttl,
            },
        )

    def delete_record(self, domain: str, record_type: str, name: str) -> dict[str, Any]:
        """
        Delete a Cloudflare DNS record by type and name.

        Args:
            domain: Root domain
            record_type: A, AAAA, CNAME, MX, TXT, NS, CAA
            name: Record name (use "@" for root)

        Returns:
            Result dict from site-provisioner
        """
        return self._request(
            "DELETE",
            f"/api/cloudflare/dns/{domain}",
            params={"record_type": record_type, "name": name},
        )

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
        """Check Cloudflare API health via site-provisioner."""
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
        enable_dnssec: bool = False,
        enable_tiered_cache: bool = True,
        enable_page_shield: bool = True,
        create_threat_rule: bool = True,
        threat_threshold: int = 50,
        setup_google: bool = False,
        setup_bing: bool = True,
        setup_indexnow: bool = True,
        setup_ga4: bool = False,
        ga4_account_id: str | None = None,
        ga4_timezone: str = "America/Los_Angeles",
        ga4_currency: str = "USD",
        sitemap_url: str | None = None,
    ) -> dict[str, Any]:
        """
        Provision a website — single call for DNS, CDN, WAF, and search engine setup.

        Sequence before every Coolify deploy:
          1. provision() — creates zone, DNS records, security, search engines
          2. check_ready() — poll until ready=true
          3. Deploy to Coolify

        Args:
            domain: Root domain (e.g., "newsite.com")
            target_ip: VPS IP address
            subdomains: Extra subdomains (e.g., ["www", "api"])
            enable_dnssec: Enable DNSSEC
            enable_tiered_cache: Enable Smart Tiered Cache CDN
            enable_page_shield: Enable Page Shield script monitoring
            create_threat_rule: Create WAF rule blocking high threat scores
            threat_threshold: Threat score 0-100 to block at (default 50)
            setup_google: Register with Google Search Console (requires per-domain owner grant)
            setup_bing: Register with Bing Webmaster Tools
            setup_indexnow: Notify IndexNow (Bing/Yandex/Seznam/Naver)
            setup_ga4: Create GA4 property (requires ga4_account_id)
            ga4_account_id: GA4 account ID (required if setup_ga4=True)
            ga4_timezone: GA4 property timezone
            ga4_currency: GA4 property currency
            sitemap_url: Submit to all search engines during provisioning

        Returns:
            Dict with success, zone_id, dns_records, features_enabled,
            google_search_console, bing_webmaster, indexnow, google_analytics.
            GA4 measurement ID: response["google_analytics"]["measurement_id"]
        """
        payload: dict[str, Any] = {
            "target_ip": target_ip,
            "subdomains": subdomains or [],
            "enable_dnssec": enable_dnssec,
            "enable_tiered_cache": enable_tiered_cache,
            "enable_page_shield": enable_page_shield,
            "create_threat_rule": create_threat_rule,
            "threat_threshold": threat_threshold,
            "setup_google": setup_google,
            "setup_bing": setup_bing,
            "setup_indexnow": setup_indexnow,
            "setup_ga4": setup_ga4,
            "ga4_timezone": ga4_timezone,
            "ga4_currency": ga4_currency,
        }
        if ga4_account_id:
            payload["ga4_account_id"] = ga4_account_id
        if sitemap_url:
            payload["sitemap_url"] = sitemap_url
        return self._request("POST", f"/api/cloudflare/zones/{domain}/provision", json=payload)

    def check_ready(self, domain: str) -> dict[str, Any]:
        """
        Check if domain is ready for Coolify deployment.

        Poll this after provision() until ready_for_deployment=true, then deploy to Coolify.

        Args:
            domain: Root domain (e.g., "newsite.com")

        Returns:
            Dict with ready_for_deployment (bool), zone_exists, zone_status, dns_records, features

        Example:
            result = dns.check_ready("newsite.com")
            if result["ready_for_deployment"]:
                # proceed with Coolify deploy
        """
        return self._request("GET", f"/api/cloudflare/zones/{domain}/ready")

    # =========================================================================
    # Website Integrations (GA4, GSC, Bing — persisted by site-provisioner)
    # =========================================================================

    def get_integrations(self, domain: str) -> dict[str, Any]:
        """
        Retrieve stored integration metadata for a domain.

        Returns GA4 measurement ID, GSC verification status, Bing registration,
        IndexNow ping history — all saved automatically during provision().

        Args:
            domain: Root domain (e.g., "example.com")

        Returns:
            Dict with cloudflare_zone_id, google_analytics, google_search_console,
            bing_webmaster, indexnow fields

        Example:
            info = dns.get_integrations("example.com")
            ga4_id = info["google_analytics"]["measurement_id"]  # e.g. "G-XXXXXXXXXX"
        """
        return self._request("GET", f"/api/websites/{domain}/integrations")

    def list_websites(self, has_ga4: bool | None = None) -> list[dict[str, Any]]:
        """
        List all provisioned websites with optional GA4 filter.

        Args:
            has_ga4: If True, return only sites with GA4 setup

        Returns:
            List of website integration dicts
        """
        params: dict[str, Any] = {}
        if has_ga4 is not None:
            params["has_ga4"] = str(has_ga4).lower()
        result = self._request("GET", "/api/websites", params=params)
        return result if isinstance(result, list) else result.get("websites", [])

    def update_sitemap(self, domain: str, sitemap_url: str) -> dict[str, Any]:
        """
        Update sitemap URL and resubmit to Google, Bing, and IndexNow.

        Args:
            domain: Root domain
            sitemap_url: New sitemap URL

        Returns:
            Dict with success and per-engine submission results
        """
        return self._request(
            "PATCH",
            f"/api/websites/{domain}/sitemap",
            params={"sitemap_url": sitemap_url},
        )

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
        Register a new domain via site-provisioner.

        site-provisioner selects the registrar internally. Fabrik does not
        need to know which registrar is used.

        Args:
            domain: Domain to register (e.g., "newsite.com")
            years: Registration period in years
            nameservers: Custom nameservers (site-provisioner picks defaults if omitted)
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
