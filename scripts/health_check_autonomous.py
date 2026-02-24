import os
import sys
from pathlib import Path

FABRIK_ROOT = Path(os.getenv("FABRIK_ROOT", "/opt/fabrik"))

from dotenv import load_dotenv  # noqa: E402

# Add src to path
sys.path.append(str(FABRIK_ROOT / "src"))

from urllib.parse import urlparse  # noqa: E402

import httpx  # noqa: E402

from fabrik.drivers.coolify import CoolifyClient  # noqa: E402
from fabrik.orchestrator.validator import is_private_ip  # noqa: E402


def check_health():
    load_dotenv(FABRIK_ROOT / ".env")

    try:
        coolify = CoolifyClient()
        print(f"Coolify URL: {coolify.base_url}")

        # 1. Coolify Health
        print("\n--- Coolify Health ---")
        try:
            health = coolify.health()
            print(f"Health: {health}")
            version = coolify.version()
            print(f"Version: {version}")
        except Exception as e:
            print(f"Error checking Coolify health: {e}")

        # 2. Applications Status
        print("\n--- Applications Status ---")
        try:
            apps = coolify.list_applications()
            print(f"Found {len(apps)} applications")
            for app in apps:
                name = app.get("name")
                status = app.get("status")
                fqdn = app.get("fqdn")
                print(f"[{status}] {name} - {fqdn}")

                # Try to hit health endpoint if it's running
                if status == "running" and fqdn:
                    health_url = f"{fqdn}/health"
                    if not health_url.startswith("http"):
                        health_url = f"http://{health_url}"

                    # SSRF protection: validate hostname before request
                    try:
                        parsed = urlparse(health_url)
                        hostname = parsed.hostname or ""
                        if is_private_ip(hostname):
                            print("  Health Check: SKIPPED (internal address)")
                            continue
                    except Exception:
                        print("  Health Check: SKIPPED (invalid URL)")
                        continue

                    try:
                        resp = httpx.get(health_url, timeout=5.0)
                        print(
                            f"  Health Check ({health_url}): {resp.status_code} - {resp.text[:100]}"
                        )
                    except Exception as e:
                        print(f"  Health Check ({health_url}): FAILED - {e}")
        except Exception as e:
            print(f"Error listing applications: {e}")

        # 3. Databases Status
        print("\n--- Databases Status ---")
        try:
            dbs = coolify.list_databases()
            print(f"Found {len(dbs)} databases")
            for db in dbs:
                name = db.get("name")
                status = db.get("status")
                db_type = db.get("type")
                print(f"[{status}] {name} ({db_type})")
        except Exception as e:
            print(f"Error listing databases: {e}")

        # 4. Services Status
        print("\n--- Services Status ---")
        try:
            services = coolify.list_services()
            print(f"Found {len(services)} services")
            for svc in services:
                name = svc.get("name")
                status = svc.get("status")
                print(f"[{status}] {name}")
        except Exception as e:
            print(f"Error listing services: {e}")

    except Exception as e:
        print(f"Initialization error: {e}")


if __name__ == "__main__":
    check_health()
