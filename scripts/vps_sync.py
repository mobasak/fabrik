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



# ---------------------------------------------------------------------------
# Residue audit — 12-point cleanup contract
# ---------------------------------------------------------------------------

TEST_PREFIX_RE = __import__('re').compile(r'(?:^|[-_])test(?:[-_]|$)', __import__('re').IGNORECASE)
"""Pattern that flags a name as test-scoped (prefix, suffix, or infix)."""

_BACKREST_REPO_DIR = "/opt/backrest/repos"
_OPT_PROJECTS_DIR = "/opt"
_TMP_LOCK_DIR = "/tmp"
_GATUS_APPS_DIR = GATUS_APPS_DIR  # already defined above


def _ssh_lines(cmd: str, timeout: int = 20) -> list[str]:
    """Run cmd via SSH and return non-empty stripped lines. Never raises."""
    from fabrik.drivers.ssh import ssh
    try:
        raw = ssh(cmd, timeout=timeout)
        return [l.strip() for l in raw.splitlines() if l.strip()]
    except Exception as e:
        return [f"[SSH ERROR: {e}]"]


def _is_test_name(name: str) -> bool:
    return bool(TEST_PREFIX_RE.search(name))


def verify_residue() -> list[str]:
    """Full 12-point residue audit.

    Checks Coolify apps, GlitchTip projects, Gatus .bak files, Authelia
    orphan rules, Postgres DBs, Meilisearch indexes, Cloudflare DNS records,
    Docker dangling volumes/images, /tmp locks, /opt stale dirs, and Backrest
    repos — all for test-scoped names or dangling state.

    Returns list of human-readable findings. Empty = clean.
    """
    import json as _json
    import os as _os

    findings: list[str] = []
    section = lambda s: findings.append(f"\n── {s} ──")

    # ── 1. Coolify: test-named apps/services ────────────────────────────────
    section("Coolify apps")
    try:
        from fabrik.drivers.coolify import CoolifyClient
        coolify = CoolifyClient()
        for item in coolify.list_applications():
            name = item.get("name", "")
            if _is_test_name(name):
                findings.append(
                    f"  Coolify: test app/service '{name}' (uuid={item.get('uuid','?')}) — run: fabrik destroy {name}"
                )
    except Exception as e:
        findings.append(f"  Coolify check failed: {e}")

    # ── 2. GlitchTip: test-named projects ───────────────────────────────────
    section("GlitchTip projects")
    try:
        import requests as _req
        gt_token = _os.getenv("GLITCHTIP_AUTH_TOKEN", "")
        gt_org = _os.getenv("GLITCHTIP_ORG_SLUG", "")
        gt_url = f"https://errors.vps1.ocoron.com/api/0/projects/{gt_org}/"
        resp = _req.get(gt_url, headers={"Authorization": f"Bearer {gt_token}"}, timeout=15)
        if resp.status_code == 200:
            for proj in resp.json():
                slug = proj.get("slug", "")
                if _is_test_name(slug):
                    findings.append(
                        f"  GlitchTip: test project '{slug}' — DELETE /api/0/projects/{gt_org}/{slug}/"
                    )
        else:
            findings.append(f"  GlitchTip list failed: HTTP {resp.status_code}")
    except Exception as e:
        findings.append(f"  GlitchTip check failed: {e}")

    # ── 3. Gatus: .bak files ─────────────────────────────────────────────────
    section("Gatus .bak files")
    baks = _ssh_lines(f"sudo find {_GATUS_APPS_DIR} -name '*.bak' 2>/dev/null")
    for b in baks:
        if b.startswith("[SSH ERROR"):
            findings.append(f"  {b}")
        else:
            findings.append(f"  Gatus leftover: {b} — rm {b}")

    # ── 4. Authelia: rules for domains not in active Coolify apps ───────────
    section("Authelia orphan rules")
    try:
        authelia_domains = _ssh_lines(
            "sudo docker exec $(sudo docker ps --filter label=coolify.serviceName=authelia "
            "--format '{{.Names}}' | head -1) "
            "grep -oP '(?<=domain: )\\S+' /config/configuration.yml 2>/dev/null || true"
        )
        from fabrik.drivers.coolify import CoolifyClient
        try:
            coolify = CoolifyClient()
            active_fqdns = set()
            for item in coolify.list_applications():
                fqdn = item.get("fqdn") or ""
                for f in fqdn.split(","):
                    f = f.strip().lstrip("https://").lstrip("http://").split("/")[0]
                    if f:
                        active_fqdns.add(f)
        except Exception:
            active_fqdns = set()

        for domain in authelia_domains:
            if domain.startswith("[SSH ERROR"):
                findings.append(f"  {domain}")
                break
            if active_fqdns and domain not in active_fqdns:
                findings.append(
                    f"  Authelia: rule for '{domain}' has no active Coolify app — verify manually"
                )
    except Exception as e:
        findings.append(f"  Authelia check failed: {e}")

    # ── 5. Postgres: test-named databases ────────────────────────────────────
    section("Postgres test databases")
    try:
        import base64 as _b64
        from fabrik.drivers.postgres import POSTGRES_CONTAINER
        from fabrik.drivers.ssh import ssh
        sql = "SELECT datname FROM pg_database WHERE datname NOT IN ('postgres','template0','template1');"
        payload = _b64.b64encode(sql.encode()).decode()
        cmd = f"echo {payload} | base64 -d | sudo docker exec -i {POSTGRES_CONTAINER} psql -U postgres -tA"
        raw = ssh(cmd, timeout=20)
        for db in raw.strip().splitlines():
            db = db.strip()
            if db and _is_test_name(db):
                findings.append(
                    f"  Postgres: test database '{db}' — fabrik postgres drop {db}"
                )
    except Exception as e:
        findings.append(f"  Postgres check failed: {e}")

    # ── 6. Meilisearch: test-named indexes ──────────────────────────────────
    section("Meilisearch test indexes")
    try:
        meili_out = _ssh_lines(
            "CONT=$(sudo docker ps --filter label=coolify.serviceName=meilisearch "
            "--format '{{.Names}}' | head -1) && "
            "sudo docker exec $CONT sh -c "
            "\'curl -s http://localhost:7700/indexes -H \"Authorization: Bearer $MEILI_MASTER_KEY\"\' 2>/dev/null"
        )
        raw_json = " ".join(meili_out)
        if raw_json and not raw_json.startswith("[SSH ERROR"):
            try:
                import json as _json2
                data = _json2.loads(raw_json)
                results = data.get("results", data) if isinstance(data, dict) else data
                for idx in (results if isinstance(results, list) else []):
                    uid = idx.get("uid", "")
                    if _is_test_name(uid):
                        findings.append(
                            f"  Meilisearch: test index '{uid}' — DELETE /indexes/{uid}"
                        )
            except Exception:
                findings.append(f"  Meilisearch: could not parse response: {raw_json[:120]}")
    except Exception as e:
        findings.append(f"  Meilisearch check failed: {e}")

    # ── 7. Cloudflare DNS: test subdomains ──────────────────────────────────
    section("Cloudflare DNS test records")
    try:
        import os as _os2, requests as _req2
        cf_token = _os2.getenv("CLOUDFLARE_API_TOKEN", "")
        cf_headers = {"Authorization": f"Bearer {cf_token}", "Content-Type": "application/json"}
        zone_vars = {k: v for k, v in _os2.environ.items() if k.startswith("CLOUDFLARE_ZONE_ID_")}
        for zone_var, zone_id in zone_vars.items():
            domain_label = zone_var.replace("CLOUDFLARE_ZONE_ID_", "").lower()
            r = _req2.get(
                f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?per_page=200",
                headers=cf_headers, timeout=15
            )
            if r.status_code == 200:
                for rec in r.json().get("result", []):
                    name = rec.get("name", "")
                    sub = name.split(".")[0] if "." in name else name
                    if _is_test_name(sub):
                        findings.append(
                            f"  DNS [{domain_label}]: test record '{name}' ({rec.get('type')}) id={rec.get('id')}"
                        )
            else:
                findings.append(f"  DNS [{domain_label}] list failed: HTTP {r.status_code}")
    except Exception as e:
        findings.append(f"  DNS check failed: {e}")

    # ── 8. Docker dangling volumes ───────────────────────────────────────────
    section("Docker dangling volumes")
    vols = _ssh_lines("sudo docker volume ls -q -f dangling=true 2>/dev/null")
    for v in vols:
        if v.startswith("[SSH ERROR"):
            findings.append(f"  {v}")
        else:
            findings.append(f"  Docker: dangling volume '{v}' — docker volume rm {v}")

    # ── 9. Docker dangling images ────────────────────────────────────────────
    section("Docker dangling images")
    imgs = _ssh_lines("sudo docker images -q -f dangling=true 2>/dev/null")
    if imgs and not imgs[0].startswith("[SSH ERROR"):
        count = len(imgs)
        if count > 0:
            findings.append(f"  Docker: {count} dangling image(s) — run: docker image prune -f")

    # ── 10. /tmp lock files ──────────────────────────────────────────────────
    section("/tmp lock files")
    locks = _ssh_lines(f"sudo find {_TMP_LOCK_DIR} -maxdepth 1 -name 'fabrik-*.lock' 2>/dev/null")
    for lk in locks:
        if lk.startswith("[SSH ERROR"):
            findings.append(f"  {lk}")
        else:
            findings.append(f"  /tmp lock: {lk} — verify no process holds it; rm {lk}")

    # ── 11. /opt stale test project dirs ────────────────────────────────────
    section("/opt stale directories")
    dirs = _ssh_lines(
        f"sudo find {_OPT_PROJECTS_DIR} -maxdepth 1 -type d 2>/dev/null | grep -E '/(test[-_]|[-_]test)' || true"
    )
    for d in dirs:
        if d.startswith("[SSH ERROR"):
            findings.append(f"  {d}")
        elif d and _is_test_name(d.split("/")[-1]):
            findings.append(f"  /opt: stale test dir '{d}' — rm -rf {d}")

    # ── 12. Backrest: test-named repos ──────────────────────────────────────
    section("Backrest repos")
    repos = _ssh_lines(f"sudo ls {_BACKREST_REPO_DIR} 2>/dev/null || true")
    for repo in repos:
        if repo.startswith("[SSH ERROR"):
            findings.append(f"  {repo}")
        elif _is_test_name(repo):
            findings.append(
                f"  Backrest: test repo '{repo}' at {_BACKREST_REPO_DIR}/{repo} — verify then rm"
            )

    # Strip section headers that produced no findings
    clean: list[str] = []
    i = 0
    while i < len(findings):
        line = findings[i]
        if line.startswith("\n──"):
            # Include section only if next line(s) are real findings (not another section)
            if i + 1 < len(findings) and not findings[i + 1].startswith("\n──"):
                clean.append(line)
        else:
            clean.append(line)
        i += 1

    return clean


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
        print("🔍 Verifying VPS config — gatus aliases + full 12-point residue audit...")
        all_findings: list[str] = []

        # Part A: stale Coolify container aliases in Gatus
        gatus_findings = verify_gatus_aliases()
        if gatus_findings:
            all_findings.append("\n── Gatus stale Coolify aliases ──")
            all_findings.extend(gatus_findings)

        # Part B: full residue audit
        print("   Running residue audit (Coolify/GlitchTip/Postgres/Meili/DNS/Docker/etc.)...")
        residue_findings = verify_residue()
        all_findings.extend(residue_findings)

        if not all_findings:
            print("✅ Clean — no stale aliases, no test residue found.")
            return 0

        # Count real findings (skip section headers)
        real = [f for f in all_findings if not f.startswith("\n──")]
        print(f"❌ {len(real)} finding(s) across audit:")
        for f in all_findings:
            if f.startswith("\n──"):
                print(f)
            else:
                print(f"   • {f.strip()}")
        print(
            "\nRemediation commands are shown inline above. "
            "Run each manually or use \'fabrik destroy <name>\' for Coolify resources."
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
