#!/usr/bin/env python3
# AFTER-EDIT: none
"""
update_vps_docs.py — regenerate dynamic sections of VPS documentation.

Reads live state from VPS (SSH + Coolify API + Cloudflare API) and rewrites
the marked dynamic sections in:
  docs/infrastructure/vps-status.md
  docs/infrastructure/vps-urls.md
  docs/infrastructure/vps-complete-inventory.md

Static sections (architecture notes, how-to guides, maintenance procedures,
resource limit explanations) are preserved unchanged.

Usage:
  python3 scripts/update_vps_docs.py           # update all three files
  python3 scripts/update_vps_docs.py --dry-run # print diff only, no writes

Called automatically by:
  fabrik apply    (post-deploy hook)
  fabrik redeploy (post-deploy hook)
  vps_apply_limits.sh (after limits applied)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv("/opt/fabrik/.env")

REPO = Path("/opt/fabrik")
DOCS_INFRA = REPO / "docs/infrastructure"

# ── Sentinel comments that wrap dynamic sections ─────────────────────────────
# Each dynamic block is bounded by:  <!-- AUTO:section_name -->  ... <!-- /AUTO -->

BEGIN = "<!-- AUTO:{} -->"
END = "<!-- /AUTO -->"


# The ONLY paths this script may ever stage or commit. Single-sourced so the `add` and the
# `commit` pathspec cannot drift apart — the drift between them WAS the defect.
VPS_DOC_PATHS = [
    "docs/infrastructure/vps-status.md",
    "docs/infrastructure/vps-urls.md",
    "docs/infrastructure/vps-complete-inventory.md",
]


def now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")


# ── Live data collectors ──────────────────────────────────────────────────────


def _ssh(cmd: str, timeout: int = 20) -> str:
    """Run cmd on VPS via ssh alias."""
    r = subprocess.run(["ssh", "vps", cmd], capture_output=True, text=True, timeout=timeout)
    return r.stdout


def collect_containers() -> list[dict]:
    raw = _ssh("sudo docker ps --format '{{.Names}}\\t{{.Status}}\\t{{.Ports}}'", timeout=30)
    rows = []
    for line in raw.strip().splitlines():
        parts = line.split("\t")
        name = parts[0] if len(parts) > 0 else ""
        status = parts[1] if len(parts) > 1 else ""
        ports = parts[2] if len(parts) > 2 else ""
        rows.append({"name": name, "status": status, "ports": ports})
    return sorted(rows, key=lambda r: r["name"])


def collect_limits() -> dict[str, int]:
    """Returns {container_name: memory_bytes}"""
    raw = _ssh(
        "sudo docker inspect $(sudo docker ps -q)"
        " --format '{{.Name}} {{.HostConfig.Memory}}' 2>/dev/null",
        timeout=30,
    )
    result = {}
    for line in raw.strip().splitlines():
        line = line.strip().lstrip("/")
        parts = line.rsplit(" ", 1)
        if len(parts) == 2:
            result[parts[0]] = int(parts[1])
    return result


def collect_disk() -> dict:
    df = _ssh("df -h / | tail -1")
    parts = df.split()
    return {
        "total": parts[1] if len(parts) > 1 else "?",
        "used": parts[2] if len(parts) > 2 else "?",
        "free": parts[3] if len(parts) > 3 else "?",
        "pct": parts[4] if len(parts) > 4 else "?",
    }


def collect_memory() -> dict:
    raw = _ssh("free -h | grep Mem")
    parts = raw.split()
    return {
        "total": parts[1] if len(parts) > 1 else "?",
        "used": parts[2] if len(parts) > 2 else "?",
        "free": parts[3] if len(parts) > 3 else "?",
    }


def collect_coolify_apps() -> list[dict]:
    try:
        sys.path.insert(0, str(REPO / "src"))
        from fabrik.drivers.coolify import CoolifyClient

        client = CoolifyClient()
        return client.list_applications()
    except Exception as e:
        return [{"error": str(e)}]


def collect_ufw() -> list[dict]:
    raw = _ssh("sudo ufw status numbered")
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("["):
            # e.g. "[ 1] 22/tcp  ALLOW IN  Anywhere  # SSH"
            parts = line.split("]", 1)
            if len(parts) == 2:
                rule = parts[1].strip()
                rows.append({"rule": rule})
    return rows


def collect_traefik_middlewares() -> list[dict]:
    raw = _ssh(
        "sudo docker exec traefik wget -qO- http://localhost:8080/api/http/middlewares 2>/dev/null",  # noqa: E501 — localhost IS the traefik container (docker exec)
        timeout=20,
    )
    import json

    try:
        items = json.loads(raw)
        return [{"name": m.get("name", ""), "type": m.get("type", "")} for m in items]
    except Exception:
        return []


def collect_uptime() -> str:
    return _ssh("uptime -p").strip()


# ── Section renderers ─────────────────────────────────────────────────────────


def render_system_overview(disk: dict, mem: dict, uptime: str, containers: list) -> str:
    count = len(containers)
    lines = [
        f"| **Containers running** | {count} |",
        f"| **Disk** | {disk['total']} total, {disk['used']} used, {disk['free']} free ({disk['pct']}) |",
        f"| **Memory** | {mem['total']} total, {mem['used']} used, {mem['free']} free |",
        f"| **Uptime** | {uptime} |",
        f"| **Last snapshot** | {now_ts()} |",
    ]
    return "\n".join(lines)


def render_container_status(containers: list, limits: dict) -> str:
    def fmt_status(s: str) -> str:
        if "healthy" in s:
            return "✅ " + s
        if "Restarting" in s:
            return "⚠️ " + s
        if "Up" in s:
            return "✅ " + s
        return "❓ " + s

    def fmt_mem(name: str) -> str:
        for k, v in limits.items():
            if name in k:
                if v == 0:
                    return "—"
                mb = v // (1024 * 1024)
                return f"{mb}m" if mb < 1024 else f"{mb // 1024}g"
        return "—"

    rows = [
        "| Container | Status | Memory limit |",
        "|---|---|---|",
    ]
    for c in containers:
        name = c["name"]
        status = fmt_status(c["status"])
        mem = fmt_mem(name)
        rows.append(f"| `{name}` | {status} | {mem} |")
    return "\n".join(rows)


def render_ufw(ufw: list) -> str:
    rows = ["| Rule | Notes |", "|---|---|"]
    for r in ufw:
        rows.append(f"| `{r['rule']}` | |")
    return "\n".join(rows)


def render_middlewares(mws: list) -> str:
    rows = ["| Name | Type |", "|---|---|"]
    for m in mws:
        rows.append(f"| `{m['name']}` | {m['type']} |")
    return "\n".join(rows)


def render_coolify_apps(apps: list) -> str:
    rows = [
        "| Name | FQDN | Status |",
        "|---|---|---|",
    ]
    for a in sorted(apps, key=lambda x: x.get("name", "")):
        if "error" in a:
            rows.append(f"| ERROR | {a['error']} | — |")
            continue
        name = a.get("name", "?")
        fqdn = a.get("fqdn", "") or "internal"
        status = a.get("status", "?")
        icon = "✅" if status in ("running", "healthy") else "⚠️"
        rows.append(f"| `{name}` | {fqdn} | {icon} {status} |")
    return "\n".join(rows)


def render_limits_summary(limits: dict) -> str:
    rows = ["| Container | Memory |", "|---|---|"]
    for name, mem in sorted(limits.items()):
        if mem == 0:
            continue
        mb = mem // (1024 * 1024)
        human = f"{mb}m" if mb < 1024 else f"{mb // 1024}g"
        rows.append(f"| `{name}` | {human} |")
    return "\n".join(rows)


# ── Document update engine ────────────────────────────────────────────────────


def update_section(content: str, section: str, new_body: str) -> str:
    """Replace content between AUTO:section_name and /AUTO sentinels."""
    begin_tag = BEGIN.format(section)
    end_tag = END
    start = content.find(begin_tag)
    if start == -1:
        return content  # sentinel not present — skip silently
    end = content.find(end_tag, start)
    if end == -1:
        return content
    new_block = f"{begin_tag}\n{new_body}\n{end_tag}"
    return content[:start] + new_block + content[end + len(end_tag) :]


def update_timestamp(content: str) -> str:
    import re

    ts = now_ts()
    content = re.sub(r"\*\*Last Updated:\*\*.*", f"**Last Updated:** {ts}", content)
    return content


def write_if_changed(path: Path, new_content: str, dry_run: bool) -> bool:
    old = path.read_text()
    if old == new_content:
        return False
    if dry_run:
        import difflib

        diff = list(
            difflib.unified_diff(
                old.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(path),
                tofile=str(path) + " (new)",
            )
        )
        print(f"\n{'=' * 60}\nDIFF: {path}\n{'=' * 60}")
        print("".join(diff[:60]))
    else:
        path.write_text(new_content)
        print(f"  ✅ updated: {path.relative_to(REPO)}")
    return True


# ── Main ──────────────────────────────────────────────────────────────────────


def _push_with_ladder() -> bool:
    """Push REPO to origin. An unpushed cron commit sits off-box-unprotected (CLAUDE.md § EXIT:
    push is a task-end law) and trips every interactive session's Stop hook with an "UNPUSHED WORK"
    nag for a commit that is not theirs. The pipeline is the only writer in this window, so a plain
    push normally lands; on a concurrent rejection, rebase our commit on top and retry ONCE. NEVER
    --force. Returns True if pushed; False leaves it committed-local (a session will push it — the
    pre-fix status quo, now only the exceptional case).
    """
    push = subprocess.run(["git", "-C", str(REPO), "push"], capture_output=True, text=True)
    if push.returncode != 0:
        subprocess.run(["git", "-C", str(REPO), "pull", "--rebase=merges"], check=False)
        push = subprocess.run(["git", "-C", str(REPO), "push"], capture_output=True, text=True)
    return push.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Update VPS documentation from live state")
    parser.add_argument("--dry-run", action="store_true", help="Print diff only, no writes")
    args = parser.parse_args()

    print(f"📡 Collecting live VPS state ({now_ts()})...")

    containers = collect_containers()
    limits = collect_limits()
    disk = collect_disk()
    mem = collect_memory()
    uptime_str = collect_uptime()
    apps = collect_coolify_apps()
    ufw = collect_ufw()
    middlewares = collect_traefik_middlewares()

    print(f"   {len(containers)} containers, {len(apps)} Coolify apps, {len(ufw)} UFW rules")

    changed = 0

    # ── vps-status.md ────────────────────────────────────────────────────────
    path = DOCS_INFRA / "vps-status.md"
    content = path.read_text()
    content = update_section(
        content, "system_overview", render_system_overview(disk, mem, uptime_str, containers)
    )
    content = update_section(
        content, "container_status", render_container_status(containers, limits)
    )
    content = update_section(content, "ufw_rules", render_ufw(ufw))
    content = update_section(content, "traefik_middlewares", render_middlewares(middlewares))
    content = update_section(content, "limits_summary", render_limits_summary(limits))
    content = update_timestamp(content)
    if write_if_changed(path, content, args.dry_run):
        changed += 1

    # ── vps-urls.md ──────────────────────────────────────────────────────────
    path = DOCS_INFRA / "vps-urls.md"
    content = path.read_text()
    content = update_section(content, "coolify_apps", render_coolify_apps(apps))
    content = update_timestamp(content)
    if write_if_changed(path, content, args.dry_run):
        changed += 1

    # ── vps-complete-inventory.md ────────────────────────────────────────────
    path = DOCS_INFRA / "vps-complete-inventory.md"
    content = path.read_text()
    content = update_section(
        content, "container_inventory", render_container_status(containers, limits)
    )
    content = update_section(content, "coolify_apps", render_coolify_apps(apps))
    content = update_section(content, "ufw_rules", render_ufw(ufw))
    content = update_section(content, "limits_summary", render_limits_summary(limits))
    content = update_timestamp(content)
    if write_if_changed(path, content, args.dry_run):
        changed += 1

    if changed == 0:
        print("✅ All docs already up to date.")
    elif not args.dry_run:
        print(f"\n📝 {changed} file(s) updated. Committing...")
        subprocess.run(
            ["git", "-C", str(REPO), "add", *VPS_DOC_PATHS],
            check=True,
        )
        # ⚠️ PATHSPEC IS MANDATORY. A bare `git commit` commits the whole INDEX, and this repo is
        # a shared tree with up to three concurrent Claude sessions plus the daily pipeline. The
        # `git add` above is correctly scoped to three files; the commit below was not, so every
        # file ANY other session had staged rode along under this automated message and author.
        # Measured 2026-09-05: commit 5b9c420d ("docs(auto): update VPS docs from live state")
        # carried INDEX.md, a design spec, scripts/vps_apply_limits.sh and a 280-line new test
        # file belonging to another session's in-flight work — and then PUSHED them. Staging is
        # the normal way an agent protects work from pre-commit's stash, so this defect
        # specifically ate the files that were being handled most carefully.
        # `commit -- <paths>` reads the WORKING TREE for those paths, which is exactly what this
        # script wants: it just wrote them.
        subprocess.run(
            [
                "git",
                "-C",
                str(REPO),
                "commit",
                "-m",
                f"docs(auto): update VPS docs from live state [{now_ts()}]",
                "--",
                *VPS_DOC_PATHS,
            ],
            check=True,
        )
        print("✅ Committed.")
        print("✅ Pushed." if _push_with_ladder() else "⚠️  Push failed — commit left local.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
