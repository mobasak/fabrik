#!/usr/bin/env python3
"""
Setup Uptime Kuma monitors for all VPS services.
Uses the uptime-kuma-api library for WebSocket communication.

Usage:
    pip install uptime-kuma-api
    python setup_uptime_kuma.py
"""

import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from uptime_kuma_api import MonitorType, UptimeKumaApi
except ImportError:
    print("Installing uptime-kuma-api...")
    os.system("pip install uptime-kuma-api")
    from uptime_kuma_api import MonitorType, UptimeKumaApi

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

UPTIME_KUMA_URL = os.getenv("UPTIME_KUMA_URL", "https://status.vps1.ocoron.com")
UPTIME_KUMA_USERNAME = os.getenv("UPTIME_KUMA_USERNAME")
UPTIME_KUMA_PASSWORD = os.getenv("UPTIME_KUMA_PASSWORD")

# Services to monitor - Add new services here
MONITORS = [
    # Infrastructure
    {
        "name": "Coolify Dashboard",
        "type": MonitorType.HTTP,
        "url": "https://vps1.ocoron.com:8000",
        "interval": 60,
    },
    {
        "name": "Netdata",
        "type": MonitorType.HTTP,
        "url": "https://netdata.vps1.ocoron.com",
        "interval": 60,
    },
    {
        "name": "Duplicati Backup",
        "type": MonitorType.HTTP,
        "url": "https://backup.vps1.ocoron.com",
        "interval": 300,
    },
    {
        "name": "Uptime Kuma",
        "type": MonitorType.HTTP,
        "url": "https://status.vps1.ocoron.com",
        "interval": 60,
    },
    # Fabrik API Services
    {
        "name": "Captcha API",
        "type": MonitorType.HTTP,
        "url": "https://captcha.vps1.ocoron.com/healthz",
        "interval": 60,
    },
    {
        "name": "Translator API",
        "type": MonitorType.HTTP,
        "url": "https://translator.vps1.ocoron.com/health",
        "interval": 60,
    },
    {
        "name": "DNS Manager",
        "type": MonitorType.HTTP,
        "url": "https://dns.vps1.ocoron.com/health",
        "interval": 60,
    },
    {
        "name": "Image Broker",
        "type": MonitorType.HTTP,
        "url": "https://images.vps1.ocoron.com/api/v1/health",
        "interval": 60,
    },
    {
        "name": "File API",
        "type": MonitorType.HTTP,
        "url": "https://files-api.vps1.ocoron.com/health",
        "interval": 60,
    },
    {
        "name": "Email Gateway",
        "type": MonitorType.HTTP,
        "url": "https://emailgateway.vps1.ocoron.com/health",
        "interval": 60,
    },
    {
        "name": "Proxy API",
        "type": MonitorType.HTTP,
        "url": "https://proxy.vps1.ocoron.com/health",
        "interval": 60,
    },
]


def main():
    if not UPTIME_KUMA_USERNAME or not UPTIME_KUMA_PASSWORD:
        print("Error: UPTIME_KUMA_USERNAME and UPTIME_KUMA_PASSWORD must be set in .env")
        sys.exit(1)

    print(f"Connecting to {UPTIME_KUMA_URL}...")

    api = UptimeKumaApi(UPTIME_KUMA_URL)
    api.login(UPTIME_KUMA_USERNAME, UPTIME_KUMA_PASSWORD)

    print("Logged in successfully!")

    # Get existing monitors
    existing = api.get_monitors()
    existing_names = {m["name"] for m in existing}
    print(f"Found {len(existing)} existing monitors")

    # Add new monitors
    added = 0
    for monitor in MONITORS:
        if monitor["name"] in existing_names:
            print(f"  ⏭️  {monitor['name']} already exists")
            continue

        try:
            api.add_monitor(
                type=monitor["type"],
                name=monitor["name"],
                url=monitor.get("url"),
                hostname=monitor.get("hostname"),
                port=monitor.get("port"),
                interval=monitor.get("interval", 60),
                retryInterval=20,
                maxretries=3,
            )
            print(f"  ✅ Added: {monitor['name']}")
            added += 1
        except Exception as e:
            print(f"  ❌ Failed to add {monitor['name']}: {e}")

    api.disconnect()
    print(f"\nDone! Added {added} new monitors.")


if __name__ == "__main__":
    main()
