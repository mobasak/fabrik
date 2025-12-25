"""
Cloudflare DNS Driver for Fabrik.

Provides per-record CRUD operations for DNS management.
Much safer than Namecheap's destructive setHosts API.

Usage:
    from fabrik.drivers.cloudflare import CloudflareClient
    
    cf = CloudflareClient()
    
    # List zones
    zones = cf.list_zones()
    
    # Get zone ID by domain
    zone_id = cf.get_zone_id("ocoron.com")
    
    # List DNS records
    records = cf.list_records(zone_id)
    
    # Create record
    cf.create_record(zone_id, "A", "myapp", "172.93.160.197", proxied=True)
    
    # Update record
    cf.update_record(zone_id, record_id, "A", "myapp", "172.93.160.198")
    
    # Delete record
    cf.delete_record(zone_id, record_id)
"""

import os
from typing import Optional, List, Dict, Any

import httpx


class CloudflareClient:
    """Cloudflare API client for DNS management."""
    
    def __init__(
        self,
        api_token: Optional[str] = None,
        account_id: Optional[str] = None,
        timeout: int = 30
    ):
        self.api_token = api_token or os.environ.get("CLOUDFLARE_API_TOKEN")
        self.account_id = account_id or os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.timeout = timeout
        
        if not self.api_token:
            raise ValueError("CLOUDFLARE_API_TOKEN is required")
        
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            },
            timeout=timeout
        )
    
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make API request and return result."""
        response = self._client.request(method, path, **kwargs)
        data = response.json()
        
        if not data.get("success", False):
            errors = data.get("errors", [])
            error_msg = "; ".join(e.get("message", str(e)) for e in errors)
            raise Exception(f"Cloudflare API error: {error_msg}")
        
        return data.get("result", data)
    
    def close(self):
        """Close the HTTP client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
    
    # === Account & Token ===
    
    def verify_token(self) -> Dict[str, Any]:
        """Verify the API token is valid."""
        # Use account-level verification if account_id available
        if self.account_id:
            return self._request("GET", f"/accounts/{self.account_id}/tokens/verify")
        return self._request("GET", "/user/tokens/verify")
    
    def health(self) -> Dict[str, Any]:
        """Health check - verify token and return status."""
        try:
            result = self.verify_token()
            return {
                "status": "healthy",
                "token_status": result.get("status"),
                "token_id": result.get("id")
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    # === Zones ===
    
    def list_zones(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all zones, optionally filtered by name."""
        params = {}
        if name:
            params["name"] = name
        return self._request("GET", "/zones", params=params)
    
    def get_zone_id(self, domain: str) -> str:
        """Get zone ID for a domain name."""
        # Handle subdomains - find root domain
        parts = domain.split(".")
        for i in range(len(parts) - 1):
            check_domain = ".".join(parts[i:])
            zones = self.list_zones(name=check_domain)
            if zones:
                return zones[0]["id"]
        
        raise ValueError(f"Zone not found for domain: {domain}")
    
    def get_zone(self, zone_id: str) -> Dict[str, Any]:
        """Get zone details by ID."""
        return self._request("GET", f"/zones/{zone_id}")
    
    # === DNS Records ===
    
    def list_records(
        self,
        zone_id: str,
        record_type: Optional[str] = None,
        name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List DNS records for a zone."""
        params = {}
        if record_type:
            params["type"] = record_type
        if name:
            params["name"] = name
        return self._request("GET", f"/zones/{zone_id}/dns_records", params=params)
    
    def get_record(self, zone_id: str, record_id: str) -> Dict[str, Any]:
        """Get a specific DNS record."""
        return self._request("GET", f"/zones/{zone_id}/dns_records/{record_id}")
    
    def create_record(
        self,
        zone_id: str,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,  # 1 = auto
        proxied: bool = False,
        priority: Optional[int] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new DNS record."""
        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied
        }
        if priority is not None:
            data["priority"] = priority
        if comment:
            data["comment"] = comment
        
        return self._request("POST", f"/zones/{zone_id}/dns_records", json=data)
    
    def update_record(
        self,
        zone_id: str,
        record_id: str,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool = False,
        priority: Optional[int] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing DNS record."""
        data = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied
        }
        if priority is not None:
            data["priority"] = priority
        if comment:
            data["comment"] = comment
        
        return self._request("PUT", f"/zones/{zone_id}/dns_records/{record_id}", json=data)
    
    def delete_record(self, zone_id: str, record_id: str) -> Dict[str, Any]:
        """Delete a DNS record."""
        return self._request("DELETE", f"/zones/{zone_id}/dns_records/{record_id}")
    
    # === High-level helpers ===
    
    def ensure_record(
        self,
        domain: str,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool = False,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ensure a DNS record exists with the given values.
        Creates if missing, updates if different, skips if identical.
        
        Args:
            domain: The root domain (e.g., "ocoron.com")
            record_type: A, AAAA, CNAME, TXT, MX, etc.
            name: Record name (e.g., "myapp" or "myapp.vps1")
            content: Record value (IP address, hostname, etc.)
            ttl: Time to live (1 = auto)
            proxied: Enable Cloudflare proxy (CDN/WAF)
            comment: Optional comment for the record
        
        Returns:
            Dict with action taken and record details
        """
        zone_id = self.get_zone_id(domain)
        
        # Build full record name
        if not name.endswith(domain):
            full_name = f"{name}.{domain}" if name else domain
        else:
            full_name = name
        
        # Check if record exists
        existing = self.list_records(zone_id, record_type=record_type, name=full_name)
        
        if existing:
            record = existing[0]
            # Check if update needed
            if (record["content"] == content and 
                record["proxied"] == proxied and
                (ttl == 1 or record["ttl"] == ttl)):
                return {"action": "unchanged", "record": record}
            
            # Update existing record
            updated = self.update_record(
                zone_id, record["id"], record_type, full_name, content,
                ttl=ttl, proxied=proxied, comment=comment
            )
            return {"action": "updated", "record": updated}
        
        # Create new record
        created = self.create_record(
            zone_id, record_type, full_name, content,
            ttl=ttl, proxied=proxied, comment=comment
        )
        return {"action": "created", "record": created}
    
    def delete_record_by_name(
        self,
        domain: str,
        record_type: str,
        name: str
    ) -> Dict[str, Any]:
        """Delete a DNS record by name."""
        zone_id = self.get_zone_id(domain)
        
        # Build full record name
        if not name.endswith(domain):
            full_name = f"{name}.{domain}" if name else domain
        else:
            full_name = name
        
        existing = self.list_records(zone_id, record_type=record_type, name=full_name)
        
        if not existing:
            return {"action": "not_found", "name": full_name}
        
        record = existing[0]
        self.delete_record(zone_id, record["id"])
        return {"action": "deleted", "record_id": record["id"], "name": full_name}
    
    def add_subdomain(
        self,
        domain: str,
        subdomain: str,
        ip: str,
        proxied: bool = False
    ) -> Dict[str, Any]:
        """
        Add a subdomain A record (Fabrik-compatible interface).
        
        Args:
            domain: Root domain (e.g., "ocoron.com")
            subdomain: Subdomain to create (e.g., "myapp.vps1")
            ip: IP address to point to
            proxied: Enable Cloudflare proxy
        
        Returns:
            Result dict with action and record
        """
        return self.ensure_record(
            domain=domain,
            record_type="A",
            name=subdomain,
            content=ip,
            proxied=proxied,
            comment="Created by Fabrik"
        )
