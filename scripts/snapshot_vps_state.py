"""Pre/post-deploy VPS state snapshot for the dev→VPS workflow test.

Captures Coolify apps, Cloudflare DNS records on vps1.ocoron.com, GlitchTip
projects, and Gatus endpoints, then writes a JSON snapshot to
``.tmp/vps-snapshot-<label>.json``.

Read-only: no mutations. Safe to run repeatedly.

Usage:
    python scripts/snapshot_vps_state.py --label pre-deploy
    python scripts/snapshot_vps_state.py --label post-python-api
    python scripts/snapshot_vps_state.py --diff pre-deploy post-python-api
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv("/opt/fabrik/.env")

REPO_ROOT = Path("/opt/fabrik")
SNAPSHOT_DIR = REPO_ROOT / ".tmp"
SNAPSHOT_DIR.mkdir(exist_ok=True)


def snapshot_coolify() -> dict[str, Any]:
    from fabrik.drivers import coolify

    client = coolify.CoolifyClient()
    apps = client.list_applications()
    projects = client.list_projects()
    return {
        "applications": [
            {
                "uuid": a.get("uuid"),
                "name": a.get("name"),
                "fqdn": a.get("fqdn"),
                "status": a.get("status"),
                "project_uuid": a.get("project_uuid") or (a.get("project") or {}).get("uuid"),
            }
            for a in apps
        ],
        "projects": [{"uuid": p.get("uuid"), "name": p.get("name")} for p in projects],
    }


def snapshot_cloudflare() -> dict[str, Any]:
    zone_id = os.getenv("CLOUDFLARE_ZONE_ID_OCORON")
    token = os.getenv("CLOUDFLARE_API_TOKEN")
    if not zone_id or not token:
        return {"error": "CLOUDFLARE_ZONE_ID_OCORON or CLOUDFLARE_API_TOKEN missing"}

    headers = {"Authorization": f"Bearer {token}"}
    records: list[dict[str, Any]] = []
    page = 1
    with httpx.Client(timeout=30.0) as http:
        while True:
            r = http.get(
                f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records",
                params={"page": page, "per_page": 100},
                headers=headers,
            )
            r.raise_for_status()
            payload = r.json()
            for rec in payload.get("result", []):
                if "vps1.ocoron.com" in rec.get("name", ""):
                    records.append(
                        {
                            "id": rec["id"],
                            "type": rec["type"],
                            "name": rec["name"],
                            "content": rec["content"],
                            "proxied": rec.get("proxied"),
                        }
                    )
            info = payload.get("result_info", {})
            if page >= info.get("total_pages", 1):
                break
            page += 1
    return {"zone": "ocoron.com", "vps1_records": records}


def snapshot_glitchtip() -> dict[str, Any]:
    base = os.getenv("GLITCHTIP_BASE_URL", "https://errors.vps1.ocoron.com")
    token = os.getenv("GLITCHTIP_AUTH_TOKEN")
    org = os.getenv("GLITCHTIP_ORG_SLUG", "ocoron")
    if not token:
        return {"error": "GLITCHTIP_AUTH_TOKEN missing"}
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=30.0) as http:
        r = http.get(f"{base}/api/0/organizations/{org}/projects/", headers=headers)
        r.raise_for_status()
        return {
            "org": org,
            "projects": [
                {"id": p.get("id"), "slug": p.get("slug"), "name": p.get("name")} for p in r.json()
            ],
        }


def snapshot_gatus() -> dict[str, Any]:
    """List per-app Gatus config files on the VPS via SSH."""
    from fabrik.drivers.ssh import ssh

    out = ssh(
        "ls -1 /opt/monitoring/configs/gatus/apps/ 2>/dev/null | sort",
        timeout=30,
    )
    files = [line.strip() for line in out.splitlines() if line.strip()]
    return {
        "config_dir": "/opt/monitoring/configs/gatus/apps",
        "endpoint_count": len(files),
        "endpoints": [{"name": f.replace(".yaml", ""), "file": f} for f in files],
    }


def take_snapshot(label: str) -> Path:
    snap = {
        "label": label,
        "captured_at": datetime.now(UTC).isoformat(),
        "coolify": _safe(snapshot_coolify),
        "cloudflare": _safe(snapshot_cloudflare),
        "glitchtip": _safe(snapshot_glitchtip),
        "gatus": _safe(snapshot_gatus),
    }
    out = SNAPSHOT_DIR / f"vps-snapshot-{label}.json"
    out.write_text(json.dumps(snap, indent=2, sort_keys=True))
    return out


def _safe(fn) -> dict[str, Any]:
    try:
        return fn()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def diff(a_label: str, b_label: str) -> int:
    a = json.loads((SNAPSHOT_DIR / f"vps-snapshot-{a_label}.json").read_text())
    b = json.loads((SNAPSHOT_DIR / f"vps-snapshot-{b_label}.json").read_text())
    leaks: list[str] = []

    a_apps = {x["uuid"] for x in (a.get("coolify", {}).get("applications") or [])}
    b_apps = {x["uuid"] for x in (b.get("coolify", {}).get("applications") or [])}
    for new_uuid in b_apps - a_apps:
        leaks.append(f"coolify.application leaked: {new_uuid}")

    a_dns = {x["id"] for x in (a.get("cloudflare", {}).get("vps1_records") or [])}
    b_dns = {x["id"] for x in (b.get("cloudflare", {}).get("vps1_records") or [])}
    for new_id in b_dns - a_dns:
        leaks.append(f"cloudflare.dns_record leaked: {new_id}")

    a_gt = {x["slug"] for x in (a.get("glitchtip", {}).get("projects") or [])}
    b_gt = {x["slug"] for x in (b.get("glitchtip", {}).get("projects") or [])}
    for new_slug in b_gt - a_gt:
        leaks.append(f"glitchtip.project leaked: {new_slug}")

    a_g = {x["name"] for x in (a.get("gatus", {}).get("endpoints") or [])}
    b_g = {x["name"] for x in (b.get("gatus", {}).get("endpoints") or [])}
    for new_name in b_g - a_g:
        leaks.append(f"gatus.endpoint leaked: {new_name}")

    if leaks:
        print(f"LEAKS DETECTED ({a_label} -> {b_label}):")
        for line in leaks:
            print(f"  - {line}")
        return 1
    print(f"clean: {a_label} -> {b_label} (no leaks)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", help="Take a snapshot with this label")
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("A", "B"),
        help="Diff two snapshots: leaks = resources in B but not A",
    )
    args = parser.parse_args()

    if args.diff:
        return diff(*args.diff)
    if args.label:
        out = take_snapshot(args.label)
        print(f"snapshot written: {out}")
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
