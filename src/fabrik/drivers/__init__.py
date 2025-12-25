"""
Fabrik drivers for external services.

- dns: DNS management (Namecheap API wrapper)
- coolify: Coolify deployment API
- uptime_kuma: Status monitoring (Uptime Kuma API)
"""

from fabrik.drivers.dns import DNSClient
from fabrik.drivers.coolify import CoolifyClient
from fabrik.drivers.uptime_kuma import UptimeKumaClient, add_fabrik_service_to_monitoring
from fabrik.drivers.supabase import SupabaseClient
from fabrik.drivers.r2 import R2Client

__all__ = [
    "DNSClient",
    "CoolifyClient",
    "UptimeKumaClient",
    "SupabaseClient",
    "R2Client",
    "add_fabrik_service_to_monitoring"
]
