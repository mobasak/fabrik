#!/usr/bin/env python3
# AFTER-EDIT: docs/DEPLOYMENT_ARCHITECTURE.md
"""
Generate the VPS container inventory table for vps-complete-inventory.md.

Reads live container state via SSH and outputs a markdown table between
<!-- AUTO:container_inventory --> markers.

Usage:
    python scripts/generate_vps_inventory.py                # print to stdout
    python scripts/generate_vps_inventory.py --update       # update the doc in-place

Friendly names are resolved from Coolify labels (resourceName, serviceName)
with a hardcoded fallback map for non-Coolify containers.
"""

import logging
import subprocess
import sys
from datetime import UTC
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DOC_PATH = Path(__file__).parent.parent / "docs" / "infrastructure" / "vps-complete-inventory.md"

# Hardcoded friendly names for containers without Coolify labels
KNOWN_NAMES = {
    "coolify": ("coolify", "Coolify control plane"),
    "coolify-db": ("coolify-db", "Coolify internal Postgres"),
    "coolify-realtime": ("coolify-realtime", "Coolify WebSocket (live logs)"),
    "coolify-redis": ("coolify-redis", "Coolify internal Redis"),
    "coolify-sentinel": ("coolify-sentinel", "Coolify Redis Sentinel (HA)"),
    "ocoron-com-backup-1": ("ocoron-backup", "WordPress backup cron (ocoron.com)"),
    "ocoron-com-db-1": ("ocoron-db", "MariaDB for ocoron.com"),
    "ocoron-com-nginx-1": ("ocoron-nginx", "Nginx reverse proxy for ocoron.com"),
    "ocoron-com-redis-1": ("ocoron-redis", "Redis object cache for ocoron.com"),
    "ocoron-com-wordpress-1": ("ocoron-wordpress", "WordPress PHP-FPM for ocoron.com"),
    "postgres-exporter": ("postgres-exporter", "Prometheus exporter for postgres-main"),
    "prometheus": ("prometheus", "Metrics collection + alerting rules"),
    "pushgateway": ("pushgateway", "Prometheus push target (drift alerts)"),
    "redis-exporter": ("redis-exporter", "Prometheus exporter for redis-main"),
    "redis-main": ("redis-main", "Shared Redis (auth sessions, cache)"),
    "traefik": ("traefik", "Reverse proxy + HTTPS termination"),
}

# Purpose descriptions for Coolify-labeled containers
PURPOSE_MAP = {
    "alertmanager": "Alert routing → Telegram",
    "apprise": "Notification gateway (multi-channel)",
    "authelia": "2FA forward-auth for admin dashboards",
    "backrest": "Restic backup manager → Backblaze B2",
    "browserless": "Headless Chrome for scraping/PDF",
    "cadvisor": "Container metrics for Prometheus",
    "fabrik-captcha": "Captcha solving service",
    "fabrik-emailgateway": "Provider-agnostic email gateway",
    "fabrik-file-api": "Presigned URL service for R2",
    "fabrik-file-worker": "Background file processing",
    "fabrik-proxy": "Proxy management API",
    "fabrik-translator": "DeepL + Azure translation service",
    "gatus": "Uptime monitoring → status.vps1.ocoron.com",
    "glitchtip-web": "Error tracking UI + API",
    "glitchtip-worker-v10": "GlitchTip async event processor",
    "gotenberg": "PDF generation API",
    "grafana": "Dashboards → monitor.vps1.ocoron.com",
    "loki": "Log aggregation (receives from Promtail)",
    "meilisearch": "Full-text search engine",
    "n8n": "Workflow automation",
    "netdata": "Real-time system monitoring",
    "node-exporter": "Host metrics for Prometheus",
    "postgres-main": "Shared PostgreSQL 16 (all app DBs)",
    "promtail": "Log shipper → Loki",
    "site-provisioner": "DNS + Cloudflare + domain provisioning",
}


def ssh_cmd(cmd: str) -> str:
    result = subprocess.run(
        ["ssh", "vps", cmd],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def get_containers() -> list[dict]:
    """Get all running containers with metadata via SSH."""
    raw = ssh_cmd(
        "for name in $(sudo docker ps --format '{{.Names}}' | sort); do "
        "  resourceName=$(sudo docker inspect $name --format '{{index .Config.Labels \"coolify.resourceName\"}}' 2>/dev/null); "
        "  coolifyType=$(sudo docker inspect $name --format '{{index .Config.Labels \"coolify.type\"}}' 2>/dev/null); "
        "  image=$(sudo docker inspect $name --format '{{.Config.Image}}' 2>/dev/null); "
        "  mem=$(sudo docker inspect $name --format '{{.HostConfig.Memory}}' 2>/dev/null); "
        "  health=$(sudo docker inspect $name --format '{{.State.Health.Status}}' 2>/dev/null); "
        '  echo "${name}|${resourceName}|${coolifyType}|${image}|${mem}|${health}"; '
        "done"
    )
    containers = []
    for line in raw.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 6:
            continue
        name, resource_name, coolify_type, image, mem_bytes, health = parts

        # Resolve friendly name
        if name in KNOWN_NAMES:
            friendly, purpose = KNOWN_NAMES[name]
        elif resource_name:
            friendly = resource_name
            purpose = PURPOSE_MAP.get(resource_name, "")
        else:
            friendly = name
            purpose = ""

        # Memory
        try:
            mem_int = int(mem_bytes)
        except (ValueError, TypeError):
            mem_int = 0
        if mem_int == 0:
            mem_str = "—"
        elif mem_int >= 1073741824:
            mem_str = f"{mem_int // 1073741824}g"
        else:
            mem_str = f"{mem_int // 1048576}m"

        # Managed by
        if coolify_type == "service":
            managed = "Coolify Service"
        elif coolify_type == "application":
            managed = "Coolify App"
        elif name.startswith("coolify"):
            managed = "Coolify Core"
        elif name.startswith("ocoron-com"):
            managed = "/opt/ocoron-com"
        elif name in ("prometheus", "pushgateway", "postgres-exporter", "redis-exporter"):
            managed = "/opt/monitoring"
        elif name in ("redis-main",):
            managed = "/opt/redis"
        elif name in ("traefik",):
            managed = "/opt/traefik"
        else:
            managed = "unknown"

        # Image short
        img_parts = image.split("/")
        img_short = img_parts[-1] if img_parts else image

        containers.append(
            {
                "name": name,
                "friendly": friendly,
                "purpose": purpose,
                "managed": managed,
                "image": img_short,
                "memory": mem_str,
                "health": health if health and health != "<no value>" else "—",
            }
        )
    return containers


def render_table(containers: list[dict]) -> str:
    lines = [
        "| Service | Container | Managed by | Image | Memory | Health | Purpose |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in containers:
        lines.append(
            f"| **{c['friendly']}** | `{c['name']}` | {c['managed']} | `{c['image']}` | {c['memory']} | {c['health']} | {c['purpose']} |"
        )
    return "\n".join(lines)


def update_doc(table: str) -> None:
    content = DOC_PATH.read_text(encoding="utf-8")
    start = "<!-- AUTO:container_inventory -->"
    end = "<!-- /AUTO -->"
    # Find the LAST occurrence of the start marker — the first may appear
    # in documentation text describing how to use the script.
    idx_start = content.rindex(start) + len(start)
    idx_end = content.index(end, idx_start)
    # Also update total count in header
    import re

    count = table.count("\n") - 1  # minus header row
    content = re.sub(
        r"\*\*Total containers:\*\* \d+ running",
        f"**Total containers:** {count} running",
        content,
    )
    # Update date
    from datetime import datetime

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    content = re.sub(
        r"\*\*Last Updated:\*\* .*",
        f"**Last Updated:** {now}",
        content,
    )
    new_content = content[:idx_start] + "\n" + table + "\n" + content[idx_end:]
    DOC_PATH.write_text(new_content, encoding="utf-8")
    logger.info("Updated %s (%d containers)", DOC_PATH.name, count)


def main() -> None:
    containers = get_containers()
    table = render_table(containers)

    if "--update" in sys.argv:
        update_doc(table)
    else:
        logger.info(table)
        logger.info(
            "\n%d containers. Run with --update to write to %s", len(containers), DOC_PATH.name
        )


if __name__ == "__main__":
    main()
