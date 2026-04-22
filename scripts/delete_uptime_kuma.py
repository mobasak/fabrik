#!/usr/bin/env python3
"""
Delete Uptime Kuma application from Coolify via API.

Usage:
    python scripts/delete_uptime_kuma.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fabrik.config import Config
from fabrik.drivers.coolify import CoolifyClient


def main():
    """Find and delete Uptime Kuma from Coolify."""
    config = Config()
    # Use external URL instead of SSH tunnel
    coolify_url = "https://coolify.vps1.ocoron.com/api/v1"
    coolify = CoolifyClient(base_url=coolify_url, token=config.coolify_token)

    print("Fetching all applications from Coolify...")
    apps = coolify.list_applications()

    # Find Uptime Kuma in applications
    uptime_kuma = None
    resource_type = None
    for app in apps:
        if "uptime" in app.get("name", "").lower() or "kuma" in app.get("name", "").lower():
            uptime_kuma = app
            resource_type = "application"
            break

    # If not found in applications, check services
    if not uptime_kuma:
        print("Uptime Kuma not found in applications, checking services...")
        services = coolify.list_services()
        for service in services:
            if (
                "uptime" in service.get("name", "").lower()
                or "kuma" in service.get("name", "").lower()
            ):
                uptime_kuma = service
                resource_type = "service"
                break

    if not uptime_kuma:
        print("❌ Uptime Kuma not found in applications or services")
        print("\nAll applications:")
        for app in apps:
            print(f"  - {app.get('name')} ({app.get('uuid')})")
        print("\nAll services:")
        for service in services:
            print(f"  - {service.get('name')} ({service.get('uuid')})")
        sys.exit(1)

    print("✓ Found Uptime Kuma:")
    print(f"  Type: {resource_type}")
    print(f"  Name: {uptime_kuma.get('name')}")
    print(f"  UUID: {uptime_kuma.get('uuid')}")
    print(f"  Status: {uptime_kuma.get('status')}")

    # Confirm deletion
    response = input("\n⚠️  Delete Uptime Kuma? (yes/no): ")
    if response.lower() != "yes":
        print("❌ Deletion cancelled")
        sys.exit(0)

    # Delete based on resource type
    print(f"\nDeleting Uptime Kuma (UUID: {uptime_kuma.get('uuid')})...")
    if resource_type == "application":
        result = coolify.delete_application(uptime_kuma.get("uuid"), delete_volumes=False)
    else:
        result = coolify.delete_service(uptime_kuma.get("uuid"))
    print("✓ Uptime Kuma deleted successfully")
    print(f"  Result: {result}")


if __name__ == "__main__":
    main()
