#!/usr/bin/env python3
"""Refresh VPS documentation from live state.

Queries VPS via SSH (docker ps) and Coolify API, then rewrites the
container tables in vps-status.md and updates timestamps in all three
VPS docs. Run manually or via ``fabrik vps-sync``.

Usage:
    python scripts/vps_sync.py
    python scripts/vps_sync.py --dry-run   # Print what would change
    python scripts/vps_sync.py --verify    # Drift detector — exits non-zero
                                           # on stale Gatus URLs etc.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/opt/fabrik/.env")

FABRIK_ROOT = Path("/opt/fabrik")
TZ = timezone(timedelta(hours=3))  # UTC+3

VPS_STATUS = FABRIK_ROOT / "docs" / "operations" / "vps-status.md"
VPS_URLS = FABRIK_ROOT / "docs" / "operations" / "vps-urls.md"
VPS_INVENTORY = FABRIK_ROOT / "docs" / "infrastructure" / "vps-complete-inventory.md"

DATE_PATTERN = re.compile(r"(\*\*(?:Last Updated|Date):\*\*\s*)\d{4}-\d{2}-\d{2}[^\n]*")

CONTAINER_COUNT_PATTERN = re.compile(r"(\| Running containers \| )\d+[^|]*(\|)")

TOTAL_CONTAINERS_PATTERN = re.compile(r"(\*\*Total Containers:\*\*\s*)\d+[^\n]*")


def _now_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M UTC+3")


def _today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def get_docker_containers() -> list[dict[str, str]]:
    """Get running container info via SSH."""
    from fabrik.drivers.ssh import ssh

    raw = ssh(
        'sudo docker ps --format "{{.Names}}|{{.Image}}|{{.Status}}" --no-trunc',
        timeout=30,
    )
    containers = []
    for line in raw.strip().splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            containers.append(
                {"name": parts[0].strip(), "image": parts[1].strip(), "status": parts[2].strip()}
            )
    return sorted(containers, key=lambda c: c["name"])


def get_disk_info() -> dict[str, str]:
    """Get disk usage from VPS."""
    from fabrik.drivers.ssh import ssh

    raw = ssh("df -h / | tail -1", timeout=10)
    parts = raw.split()
    if len(parts) >= 5:
        return {"total": parts[1], "used": parts[2], "available": parts[3], "pct": parts[4]}
    return {}


def get_memory_info() -> dict[str, str]:
    """Get memory info from VPS."""
    from fabrik.drivers.ssh import ssh

    raw = ssh("free -h | grep Mem:", timeout=10)
    parts = raw.split()
    if len(parts) >= 4:
        return {"total": parts[1], "available": parts[6] if len(parts) >= 7 else parts[3]}
    return {}


def get_kernel() -> str:
    """Get kernel version."""
    from fabrik.drivers.ssh import ssh

    return ssh("uname -r", timeout=10).strip()


def categorize_containers(
    containers: list[dict[str, str]],
) -> dict[str, list[dict[str, str]]]:
    """Group containers into categories."""
    coolify = []
    datastores = []
    monitoring = []
    infra = []
    microservices = []
    websites = []
    other = []

    coolify_names = {
        "coolify",
        "coolify-db",
        "coolify-redis",
        "coolify-realtime",
        "coolify-sentinel",
    }
    datastore_patterns = {"postgres-main", "redis-main"}
    monitoring_patterns = {
        "grafana",
        "alertmanager",
        "loki",
        "promtail",
        "cadvisor",
        "node-exporter",
        "netdata",
        "gatus",
        "glitchtip",
        "prometheus",
    }
    infra_patterns = {"authelia", "n8n", "apprise", "backrest", "traefik"}
    website_patterns = {"ocoron-com", "wordpress"}

    for c in containers:
        name = c["name"].lower()
        if any(name == cn or name.startswith(cn + "-") for cn in coolify_names):
            if ("proxy" in name and "traefik" in c["image"].lower()) or name in coolify_names:
                coolify.append(c)
            else:
                other.append(c)
        elif any(p in name for p in datastore_patterns):
            datastores.append(c)
        elif any(p in name for p in monitoring_patterns):
            monitoring.append(c)
        elif any(p in name for p in infra_patterns):
            infra.append(c)
        elif any(p in name for p in website_patterns):
            websites.append(c)
        else:
            microservices.append(c)

    return {
        "Coolify Platform": coolify,
        "Data Stores": datastores,
        "Monitoring Stack": monitoring,
        "Infrastructure Services": infra,
        "Fabrik Microservices": microservices,
        "Websites": websites,
    }


_COOLIFY_SUFFIX = re.compile(r"-[a-z0-9]{24,}(-\d+)?$")


def _display_name(raw_name: str) -> str:
    """Strip Coolify UUID suffixes for cleaner table display."""
    # e.g. 'postgres-main-l0k4gk0kggc8okcwk0s4c8s8' → 'postgres-main'
    # e.g. 'captcha-j8gg4ggskkossc4gkwowk4os-195201011254' → 'captcha'
    cleaned = _COOLIFY_SUFFIX.sub("", raw_name)
    return cleaned or raw_name


def _health_icon(status: str) -> str:
    s = status.lower()
    if "healthy" in s:
        return "✅ healthy"
    if "restart" in s:
        return "⚠️ restarting"
    if "unhealthy" in s:
        return "⚠️ unhealthy"
    return "✅ running"


def build_container_tables(categories: dict[str, list[dict[str, str]]]) -> str:
    """Build markdown tables for containers by category."""
    lines = []
    for category, containers in categories.items():
        if not containers:
            continue
        lines.append(f"#### {category}")
        lines.append("")
        lines.append("| Container | Status |")
        lines.append("|-----------|--------|")
        for c in containers:
            lines.append(f"| {_display_name(c['name'])} | {_health_icon(c['status'])} |")
        lines.append("")
    return "\n".join(lines)


def update_vps_status(containers: list[dict[str, str]], dry_run: bool = False) -> bool:
    """Update vps-status.md with current container info."""
    if not VPS_STATUS.exists():
        print(f"  ⚠️  {VPS_STATUS.name} not found, skipping")
        return False

    content = VPS_STATUS.read_text()
    now = _now_str()
    today = _today_str()
    count = len(containers)

    # Update date
    content = DATE_PATTERN.sub(rf"\g<1>{now}", content, count=1)

    # Update container count
    content = CONTAINER_COUNT_PATTERN.sub(
        rf"\g<1>{count} (Coolify stack + infra + microservices)\2", content
    )

    # Replace container tables section
    categories = categorize_containers(containers)
    new_tables = build_container_tables(categories)

    # Find the running containers section and replace it
    marker_start = re.search(r"### Running Containers \([^)]+\)\n", content)
    if marker_start:
        # Find the next --- or ## heading after the tables
        rest = content[marker_start.end() :]
        next_section = re.search(r"\n---\n|\n## ", rest)
        end_pos = marker_start.end() + next_section.start() if next_section else len(content)

        new_header = f"### Running Containers ({today})\n\n"
        content = content[: marker_start.start()] + new_header + new_tables + content[end_pos:]

    if dry_run:
        print(f"  [dry-run] Would update {VPS_STATUS.name} ({count} containers)")
        return True

    VPS_STATUS.write_text(content)
    print(f"  ✅ {VPS_STATUS.name} updated ({count} containers)")
    return True


def update_timestamp(path: Path, dry_run: bool = False) -> bool:
    """Update the Last Updated / Date timestamp in a file."""
    if not path.exists():
        print(f"  ⚠️  {path.name} not found, skipping")
        return False

    content = path.read_text()
    today = _today_str()

    if not DATE_PATTERN.search(content):
        print(f"  ℹ️  {path.name} — no date pattern found")
        return False

    new_content = DATE_PATTERN.sub(rf"\g<1>{today}", content)
    if new_content == content:
        print(f"  ℹ️  {path.name} — already current ({today})")
        return True

    if dry_run:
        print(f"  [dry-run] Would update timestamp in {path.name}")
        return True

    path.write_text(new_content)
    print(f"  ✅ {path.name} timestamp updated to {today}")
    return True


def update_inventory_count(count: int, dry_run: bool = False) -> bool:
    """Update the total container count in vps-complete-inventory.md."""
    if not VPS_INVENTORY.exists():
        return False
    content = VPS_INVENTORY.read_text()
    new_content = TOTAL_CONTAINERS_PATTERN.sub(rf"\g<1>{count} running", content)
    if new_content == content:
        return False
    if dry_run:
        print(f"  [dry-run] Would update container count in {VPS_INVENTORY.name}")
        return True
    VPS_INVENTORY.write_text(new_content)
    print(f"  ✅ {VPS_INVENTORY.name} container count → {count}")
    return True


# --- Drift detectors -------------------------------------------------------

# Coolify auto-generated container DNS aliases follow the pattern
# ``<service>-<24-char-base36-uuid>-<10-13-digit-timestamp>``. The UUID+timestamp
# segment changes on every redeploy, silently breaking any config that pinned
# to it (Gatus, Prometheus targets, custom proxies). This regex flags such
# pinned hostnames so the drift detector can refuse to ship them.
STALE_COOLIFY_ALIAS_RE = re.compile(r"://[a-z][a-z0-9_-]*-[a-z0-9]{24}-[0-9]{10,13}\b")

GATUS_APPS_DIR = "/opt/monitoring/configs/gatus/apps"


def verify_gatus_aliases() -> list[str]:
    """Scan VPS Gatus configs for stale Coolify container aliases.

    Returns a list of human-readable findings. Empty list = no drift.
    """
    from fabrik.drivers.ssh import ssh

    try:
        listing = ssh(
            f"sudo ls {GATUS_APPS_DIR}/*.yaml 2>/dev/null || true",
            timeout=15,
        )
    except Exception as e:  # pragma: no cover — best-effort
        return [f"verify: SSH listing failed: {e}"]

    findings: list[str] = []
    for path in listing.strip().splitlines():
        path = path.strip()
        if not path:
            continue
        try:
            body = ssh(f"sudo cat {path}", timeout=15)
        except Exception as e:  # pragma: no cover
            findings.append(f"{path}: read failed: {e}")
            continue
        for lineno, line in enumerate(body.splitlines(), 1):
            m = STALE_COOLIFY_ALIAS_RE.search(line)
            if m:
                findings.append(
                    f"{path}:{lineno}  stale Coolify alias '{m.group(0)[3:]}' "
                    f"— use bare service name (e.g. http://captcha:8000/health)"
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync VPS docs from live state")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Drift detection only. Exit 0 = clean, 1 = drift found, 2 = scan failed.",
    )
    args = parser.parse_args()

    if args.verify:
        print("🔍 Verifying VPS config for known drift patterns...")
        findings = verify_gatus_aliases()
        if not findings:
            print("✅ No stale Coolify container aliases in Gatus configs.")
            return 0
        print(f"❌ Drift detected — {len(findings)} finding(s):")
        for f in findings:
            print(f"   • {f}")
        print(
            "\nRemediation: replace the stale '<service>-<uuid>-<ts>' hostname "
            "with the bare service alias (e.g. 'http://captcha:8000/health'). "
            "Coolify exposes both forms; only the bare alias survives redeploy."
        )
        return 1

    print("🔄 Fetching VPS state via SSH...")
    try:
        containers = get_docker_containers()
    except Exception as e:
        print(f"❌ Failed to fetch containers: {e}")
        return 1

    print(f"   Found {len(containers)} running containers")

    print()
    print("📝 Updating documentation...")

    update_vps_status(containers, dry_run=args.dry_run)
    update_timestamp(VPS_URLS, dry_run=args.dry_run)
    update_timestamp(VPS_INVENTORY, dry_run=args.dry_run)
    update_inventory_count(len(containers), dry_run=args.dry_run)

    # Also run sync_projects.py
    print()
    print("📊 Syncing project registry...")
    if not args.dry_run:
        import subprocess

        sync_script = FABRIK_ROOT / "scripts" / "sync_projects.py"
        if sync_script.exists():
            result = subprocess.run(
                ["python3", str(sync_script)],
                cwd=str(FABRIK_ROOT),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                print("  ✅ projects.yaml updated")
            else:
                print(f"  ⚠️  sync_projects failed: {result.stderr[:200]}")
    else:
        print("  [dry-run] Would run sync_projects.py")

    print()
    print("✅ VPS docs sync complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
