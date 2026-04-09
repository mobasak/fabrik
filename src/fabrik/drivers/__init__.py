"""
Fabrik drivers for external services.

- dns: DNS management (Namecheap API wrapper)
- coolify: Coolify deployment API
- uptime_kuma: Status monitoring (Uptime Kuma API)
- seo: SEO keyword research and content brief service
- tco: Triggered Content Orchestration (AI content generation)
- image_broker: Stock image selection and download
"""

from fabrik.drivers.coolify import CoolifyClient
from fabrik.drivers.dns import DNSClient
from fabrik.drivers.image_broker import ImageBrokerClient
from fabrik.drivers.r2 import R2Client
from fabrik.drivers.seo import SEOClient
from fabrik.drivers.supabase import SupabaseClient
from fabrik.drivers.tco import TCOClient
from fabrik.drivers.uptime_kuma import UptimeKumaClient, add_fabrik_service_to_monitoring

__all__ = [
    "DNSClient",
    "CoolifyClient",
    "UptimeKumaClient",
    "SupabaseClient",
    "R2Client",
    "SEOClient",
    "TCOClient",
    "ImageBrokerClient",
    "add_fabrik_service_to_monitoring",
]
