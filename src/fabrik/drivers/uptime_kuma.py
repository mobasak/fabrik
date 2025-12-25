"""
Uptime Kuma driver for Fabrik.

Provides automatic service monitoring integration.
When a service is deployed via Fabrik, it can automatically be added to Uptime Kuma.
"""

import os
from typing import Optional

try:
    from uptime_kuma_api import UptimeKumaApi, MonitorType
    HAS_UPTIME_KUMA = True
except ImportError:
    HAS_UPTIME_KUMA = False
    UptimeKumaApi = None
    MonitorType = None


class UptimeKumaClient:
    """Client for Uptime Kuma status monitoring."""

    def __init__(
        self,
        url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.url = url or os.getenv("UPTIME_KUMA_URL", "https://status.vps1.ocoron.com")
        self.username = username or os.getenv("UPTIME_KUMA_USERNAME")
        self.password = password or os.getenv("UPTIME_KUMA_PASSWORD")
        self._api: Optional[UptimeKumaApi] = None

    def _ensure_connected(self) -> None:
        """Ensure we have an active connection."""
        if not HAS_UPTIME_KUMA:
            raise ImportError(
                "uptime-kuma-api not installed. Run: pip install uptime-kuma-api"
            )
        if self._api is None:
            self._api = UptimeKumaApi(self.url)
            self._api.login(self.username, self.password)

    def disconnect(self) -> None:
        """Disconnect from Uptime Kuma."""
        if self._api:
            self._api.disconnect()
            self._api = None

    def get_monitors(self) -> list[dict]:
        """Get all existing monitors."""
        self._ensure_connected()
        return self._api.get_monitors()

    def add_http_monitor(
        self,
        name: str,
        url: str,
        interval: int = 60,
        retries: int = 3,
    ) -> dict:
        """
        Add an HTTP(s) monitor.

        Args:
            name: Display name for the monitor
            url: URL to monitor (should include /health endpoint if available)
            interval: Check interval in seconds (default 60)
            retries: Number of retries before marking down (default 3)

        Returns:
            Monitor info dict
        """
        self._ensure_connected()

        # Check if already exists
        existing = self._api.get_monitors()
        for m in existing:
            if m["name"] == name:
                return {"status": "exists", "monitor": m}

        result = self._api.add_monitor(
            type=MonitorType.HTTP,
            name=name,
            url=url,
            interval=interval,
            retryInterval=20,
            maxretries=retries,
        )
        return {"status": "created", "monitor": result}

    def add_tcp_monitor(
        self,
        name: str,
        hostname: str,
        port: int,
        interval: int = 60,
    ) -> dict:
        """
        Add a TCP port monitor (for databases, redis, etc.).

        Args:
            name: Display name for the monitor
            hostname: Host to check (can be Docker container name)
            port: Port number to check
            interval: Check interval in seconds (default 60)

        Returns:
            Monitor info dict
        """
        self._ensure_connected()

        # Check if already exists
        existing = self._api.get_monitors()
        for m in existing:
            if m["name"] == name:
                return {"status": "exists", "monitor": m}

        result = self._api.add_monitor(
            type=MonitorType.PORT,
            name=name,
            hostname=hostname,
            port=port,
            interval=interval,
            retryInterval=20,
            maxretries=3,
        )
        return {"status": "created", "monitor": result}

    def delete_monitor(self, name: str) -> bool:
        """Delete a monitor by name."""
        self._ensure_connected()

        existing = self._api.get_monitors()
        for m in existing:
            if m["name"] == name:
                self._api.delete_monitor(m["id"])
                return True
        return False

    def add_service_monitor(
        self,
        service_name: str,
        domain: str,
        health_endpoint: str = "/health",
    ) -> dict:
        """
        Convenience method to add a standard Fabrik service monitor.

        Args:
            service_name: Name of the service (e.g., "translator")
            domain: Domain where service is deployed (e.g., "vps1.ocoron.com")
            health_endpoint: Health check endpoint (default "/health")

        Returns:
            Monitor info dict
        """
        url = f"https://{service_name}.{domain}{health_endpoint}"
        display_name = f"{service_name.title()} API"
        return self.add_http_monitor(name=display_name, url=url)


def add_fabrik_service_to_monitoring(
    service_name: str,
    domain: str = "vps1.ocoron.com",
    health_endpoint: str = "/health",
) -> dict:
    """
    Helper function to add a newly deployed Fabrik service to Uptime Kuma.

    This should be called as a post-deployment hook.

    Args:
        service_name: Name of the deployed service
        domain: Domain where deployed
        health_endpoint: Health check path

    Returns:
        Result dict with status
    """
    client = UptimeKumaClient()
    try:
        result = client.add_service_monitor(service_name, domain, health_endpoint)
        return result
    finally:
        client.disconnect()
