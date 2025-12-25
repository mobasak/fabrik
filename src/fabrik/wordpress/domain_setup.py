"""
Domain Setup Module for WordPress Sites.

Handles Step 1 automation:
- Add DNS records via VPS DNS Manager (Cloudflare API)
- Preserve existing records (M365, etc.)
- Verify DNS propagation
- Verify HTTPS certificate

Usage:
    from fabrik.wordpress.domain_setup import DomainSetup
    
    setup = DomainSetup('ocoron.com', vps_ip='172.93.160.197')
    result = setup.configure_dns()
    
    # Or via deployer integration
    deployer = SiteDeployer('ocoron.com')
    deployer.deploy()  # Includes DNS setup as step 1
"""

import os
import time
import socket
import httpx
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DNSRecord:
    """DNS record representation."""
    record_type: str
    name: str
    content: str
    ttl: int = 1
    proxied: bool = False
    priority: Optional[int] = None


@dataclass
class DomainSetupResult:
    """Result of domain setup operation."""
    success: bool = False
    domain: str = ""
    
    # DNS
    a_record_created: bool = False
    a_record_id: Optional[str] = None
    existing_records_preserved: int = 0
    
    # Verification
    dns_resolving: bool = False
    resolved_ips: list[str] = field(default_factory=list)
    https_working: bool = False
    https_status_code: Optional[int] = None
    
    # Errors
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DomainSetup:
    """
    Domain setup automation for WordPress sites.
    
    Uses VPS DNS Manager to configure Cloudflare DNS records.
    Preserves existing records (M365, etc.) by using per-record CRUD.
    """
    
    def __init__(
        self,
        domain: str,
        vps_ip: str = "172.93.160.197",
        dns_manager_url: Optional[str] = None,
        proxied: bool = True,
        dry_run: bool = False,
    ):
        """
        Initialize domain setup.
        
        Args:
            domain: Domain name (e.g., "ocoron.com")
            vps_ip: VPS IP address to point domain to
            dns_manager_url: VPS DNS Manager URL (defaults to env var or standard URL)
            proxied: Enable Cloudflare proxy (CDN/WAF)
            dry_run: If True, only simulate actions
        """
        self.domain = domain
        self.vps_ip = vps_ip
        self.proxied = proxied
        self.dry_run = dry_run
        
        self.dns_manager_url = dns_manager_url or os.getenv(
            "DNS_MANAGER_URL",
            "https://dns.vps1.ocoron.com"
        )
        
        self._client = httpx.Client(timeout=30)
        self.result = DomainSetupResult(domain=domain)
    
    def configure_dns(self) -> DomainSetupResult:
        """
        Configure DNS for the domain.
        
        Steps:
        1. Check existing records
        2. Add A record for root domain (if missing)
        3. Add A record for www (if missing and no CNAME)
        4. Verify DNS propagation
        5. Verify HTTPS
        
        Returns:
            DomainSetupResult with status and details
        """
        try:
            # Step 1: Check existing records
            existing = self._get_existing_records()
            self.result.existing_records_preserved = len(existing)
            
            # Check if A record already exists
            root_a_records = [
                r for r in existing 
                if r.get('type') == 'A' and r.get('name') == self.domain
            ]
            
            if root_a_records:
                current_ip = root_a_records[0].get('content')
                if current_ip == self.vps_ip:
                    self.result.warnings.append(
                        f"A record already exists: {self.domain} → {current_ip}"
                    )
                    self.result.a_record_created = False
                else:
                    self.result.warnings.append(
                        f"A record exists with different IP: {current_ip} (expected {self.vps_ip})"
                    )
                    # Update existing record
                    if not self.dry_run:
                        self._update_a_record(root_a_records[0]['id'])
                    self.result.a_record_created = True
            else:
                # Create new A record
                if not self.dry_run:
                    record_id = self._create_a_record()
                    self.result.a_record_id = record_id
                self.result.a_record_created = True
            
            # Step 2: Check www record
            www_records = [
                r for r in existing
                if r.get('name') == f"www.{self.domain}"
            ]
            
            if not www_records:
                # Add CNAME for www → root
                if not self.dry_run:
                    self._create_www_cname()
                self.result.warnings.append("Created www CNAME record")
            
            # Step 3: Verify DNS (skip in dry run)
            if not self.dry_run:
                time.sleep(2)  # Brief wait for DNS propagation
                self._verify_dns()
                self._verify_https()
            
            self.result.success = True
            
        except Exception as e:
            self.result.success = False
            self.result.errors.append(str(e))
        
        return self.result
    
    def _get_existing_records(self) -> list[dict]:
        """Get existing DNS records from Cloudflare via DNS Manager."""
        url = f"{self.dns_manager_url}/api/cloudflare/dns/{self.domain}"
        response = self._client.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get('records', [])
    
    def _create_a_record(self) -> str:
        """Create A record for root domain."""
        url = f"{self.dns_manager_url}/api/cloudflare/dns/{self.domain}"
        payload = {
            "record_type": "A",
            "name": self.domain,
            "content": self.vps_ip,
            "ttl": 1,
            "proxied": self.proxied
        }
        
        response = self._client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        return data.get('record', {}).get('id', '')
    
    def _update_a_record(self, record_id: str) -> None:
        """Update existing A record."""
        # Delete and recreate (DNS Manager may not have update endpoint)
        url = f"{self.dns_manager_url}/api/cloudflare/dns/{self.domain}"
        
        # Delete old record
        self._client.delete(
            url,
            params={"record_type": "A", "name": self.domain}
        )
        
        # Create new record
        self._create_a_record()
    
    def _create_www_cname(self) -> None:
        """Create CNAME record for www subdomain."""
        url = f"{self.dns_manager_url}/api/cloudflare/dns/{self.domain}"
        payload = {
            "record_type": "CNAME",
            "name": f"www.{self.domain}",
            "content": self.domain,
            "ttl": 1,
            "proxied": self.proxied
        }
        
        response = self._client.post(url, json=payload)
        # Don't raise on error - www is optional
        if response.status_code != 200:
            self.result.warnings.append(f"Failed to create www CNAME: {response.text}")
    
    def _verify_dns(self) -> None:
        """Verify DNS is resolving."""
        try:
            # Try to resolve domain
            ips = socket.gethostbyname_ex(self.domain)[2]
            self.result.resolved_ips = ips
            self.result.dns_resolving = len(ips) > 0
        except socket.gaierror as e:
            self.result.dns_resolving = False
            self.result.warnings.append(f"DNS not resolving yet: {e}")
    
    def _verify_https(self) -> None:
        """Verify HTTPS is working."""
        try:
            response = self._client.head(
                f"https://{self.domain}",
                follow_redirects=True,
                timeout=10
            )
            self.result.https_working = True
            self.result.https_status_code = response.status_code
        except Exception as e:
            self.result.https_working = False
            self.result.warnings.append(f"HTTPS not ready: {e}")
    
    def close(self):
        """Close HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


def setup_domain(
    domain: str,
    vps_ip: str = "172.93.160.197",
    proxied: bool = True,
    dry_run: bool = False
) -> DomainSetupResult:
    """
    Convenience function to set up domain DNS.
    
    Args:
        domain: Domain name
        vps_ip: VPS IP address
        proxied: Enable Cloudflare proxy
        dry_run: Simulate only
        
    Returns:
        DomainSetupResult
        
    Example:
        from fabrik.wordpress.domain_setup import setup_domain
        
        result = setup_domain('ocoron.com')
        if result.success:
            print(f"DNS configured, HTTPS: {result.https_working}")
    """
    with DomainSetup(domain, vps_ip, proxied=proxied, dry_run=dry_run) as setup:
        return setup.configure_dns()
