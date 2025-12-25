"""
DNS Client - Wrapper for DNS Manager service.

This client calls the dns-manager service at VPS (dns.vps1.ocoron.com),
which provides unified access to both Namecheap and Cloudflare DNS.
"""

import os
import httpx
from dataclasses import dataclass
from typing import Any


@dataclass
class DNSRecord:
    """DNS record representation."""
    type: str
    name: str
    value: str
    ttl: int = 1800


class DNSClient:
    """
    DNS management client that wraps the namecheap API service.
    
    The namecheap service is deployed at VPS and handles:
    - Namecheap API authentication
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
    
    def __init__(self, base_url: str | None = None, timeout: float = 30.0):
        """
        Initialize DNS client.
        
        Args:
            base_url: DNS Manager service URL. Defaults to DNS_MANAGER_URL env var
                     or https://dns.vps1.ocoron.com
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv(
            "DNS_MANAGER_URL",
            os.getenv("NAMECHEAP_API_URL", "https://dns.vps1.ocoron.com")
        )
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict[str, Any]:
        """Make HTTP request to namecheap service."""
        url = f"{self.base_url}{endpoint}"
        response = self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    
    # =========================================================================
    # Health & Status
    # =========================================================================
    
    def health(self) -> dict[str, Any]:
        """Check namecheap service health."""
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
        Uses the namecheap service's safe merge logic.
        
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
            "POST",
            f"/api/dns/{domain}/subdomain",
            json={"subdomain": subdomain, "ip": ip}
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
            "PUT",
            f"/api/dns/{domain}/nameservers",
            json={"nameservers": nameservers}
        )
    
    # =========================================================================
    # Account
    # =========================================================================
    
    def get_balance(self) -> dict[str, Any]:
        """Get account balance."""
        return self._request("GET", "/api/account/balance")
    
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
