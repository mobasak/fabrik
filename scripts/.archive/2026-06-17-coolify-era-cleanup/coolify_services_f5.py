#!/usr/bin/env python3
"""F5 backfill for Coolify Services (one-click stacks).

String-based deploy.resources.limits injection that preserves original
formatting (no PyYAML round-trip noise). Touches only the byte range where
the new block is inserted.

  1. GETs each service via /api/v1/services/<uuid>
  2. Finds each named service block in docker_compose_raw
  3. Inserts a 4-line `deploy:` block at the end of that service block
     (before the next top-level key or next service definition)
  4. PATCHes the updated docker_compose_raw back
  5. Does NOT trigger redeploy — operator's call

Idempotent: if a service block already contains `deploy:` indented under it,
the helper skips that service.

Limits match what vps_apply_limits.sh enforces live today.

Usage:
  python3 /tmp/coolify_services_f5.py --dry-run
  python3 /tmp/coolify_services_f5.py --apply
  python3 /tmp/coolify_services_f5.py --apply --only apprise
"""

import argparse
import base64
import difflib
import json
import re
import sys
from urllib import error, request

# uuid -> (display name, {service_key_substring -> memory})
SERVICES = {
    "lcocgs4gs8ksg4g08w40ows8": {"name": "apprise", "limits": {"apprise": "768M"}},
    "kk4kcw4csksc48848go4o0wo": {"name": "netdata", "limits": {"netdata": "768M"}},
    "loc484owg8gsw04owo0go8kc": {"name": "grafana", "limits": {"grafana": "512M"}},
    "r48swckog008wosgwcs4g0g0": {"name": "loki", "limits": {"loki": "512M"}},
    "w0000ckgsgg048w0848okk08": {"name": "promtail", "limits": {"promtail": "128M"}},
    "doc8c8gkcgs88s8ckggw84o4": {"name": "node-exporter", "limits": {"node-exporter": "128M"}},
    "r08sog4gwws88og048ows448": {"name": "cadvisor", "limits": {"cadvisor": "512M"}},
    "zw4swgkwk0s4s8kg048gw80o": {"name": "alertmanager", "limits": {"alertmanager": "256M"}},
    "l0k4gk0kggc8okcwk0s4c8s8": {"name": "postgres-main", "limits": {"postgres": "2G"}},
    "s8gwccsws0ccssw0wwgwsoks": {"name": "n8n", "limits": {"n8n": "2G"}},
    "l48000k44wc4gk8os88s8k0c": {"name": "backrest", "limits": {"backrest": "512M"}},
    "hks48k8sg8o4co4co08co00o": {"name": "authelia", "limits": {"authelia": "512M"}},
}

CPUS_DEFAULT = "0.5"


def load_token() -> str:
    with open("/opt/fabrik/.env") as f:
        text = f.read()
    m = re.search(r'COOLIFY_API_TOKEN[=:]\s*"?([^"\n]+)', text)
    if not m:
        sys.exit("COOLIFY_API_TOKEN not found in /opt/fabrik/.env")
    return m.group(1)


def api(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"https://coolify.vps1.ocoron.com{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = request.Request(url, headers=headers, method=method, data=data)
    try:
        r = request.urlopen(req, timeout=15)
        return json.loads(r.read())
    except error.HTTPError as e:
        sys.exit(f"{method} {path} -> HTTP {e.code}: {e.read()[:400].decode(errors='replace')}")


def find_service_range(lines: list[str], svc_key_pattern: str) -> tuple[int, int] | None:
    """Find [start_idx, end_idx) of a service block whose key contains pattern.

    Service blocks are top-level keys under `services:`, indented 2 spaces.
    The block ends at the next 2-space-indented sibling, or at a 0-indented
    top-level key (volumes/networks/etc.).
    """
    # Find the services: key first
    services_line = None
    for i, line in enumerate(lines):
        if line.rstrip() == "services:":
            services_line = i
            break
    if services_line is None:
        return None

    start = None
    for i in range(services_line + 1, len(lines)):
        line = lines[i]
        if not line.strip():
            continue
        # Top-level key (no indent) — exit services section
        if line and not line[0].isspace():
            if start is not None:
                return (start, i)
            return None
        # 2-space-indented key (service definition)
        m = re.match(r"^  ([^\s:]+):\s*$", line)
        if m:
            if start is None and svc_key_pattern in m.group(1):
                start = i
            elif start is not None:
                # next sibling — end of our block
                return (start, i)
    if start is not None:
        return (start, len(lines))
    return None


def inject_deploy(raw: str, name_to_memory: dict[str, str]) -> tuple[str, list[str]]:
    """Inject deploy block per matching service. Preserves all original
    formatting; only inserts lines."""
    lines = raw.splitlines()
    notes: list[str] = []
    # Process services bottom-up so insertions don't shift earlier ranges
    insertions: list[tuple[int, list[str], str]] = []  # (idx, block_lines, note)
    for pattern, mem in name_to_memory.items():
        rng = find_service_range(lines, pattern)
        if rng is None:
            notes.append(f"  miss   pattern '{pattern}' not found")
            continue
        start, end = rng
        # Check if deploy: already exists within this range (indented 4 spaces under service)
        already = False
        for j in range(start, end):
            if re.match(r"^    deploy:\s*$", lines[j]):
                already = True
                break
        if already:
            notes.append(f"  noop   {pattern}: deploy: already present")
            continue

        # Insert position: before the last blank line preceding the range end,
        # i.e. at the end of the service's content.
        insert_at = end
        while insert_at > start + 1 and not lines[insert_at - 1].strip():
            insert_at -= 1

        block = [
            "    deploy:",
            "      resources:",
            "        limits:",
            f"          memory: {mem}",
            f"          cpus: '{CPUS_DEFAULT}'",
        ]
        insertions.append(
            (insert_at, block, f"  add    {pattern}: memory={mem} cpus={CPUS_DEFAULT}")
        )

    # Apply bottom-up
    for idx, block, note in sorted(insertions, key=lambda x: -x[0]):
        lines[idx:idx] = block
        notes.append(note)

    new_raw = "\n".join(lines)
    if raw.endswith("\n") and not new_raw.endswith("\n"):
        new_raw += "\n"
    return new_raw, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="filter by service display name (e.g. apprise)")
    args = ap.parse_args()
    if not args.apply and not args.dry_run:
        ap.error("specify --dry-run or --apply")

    token = load_token()
    summary: list[str] = []
    for uuid, cfg in SERVICES.items():
        if args.only and args.only != cfg["name"]:
            continue
        print(f"\n=== {cfg['name']} ({uuid}) ===")
        svc = api("GET", f"/api/v1/services/{uuid}", token)
        raw = svc.get("docker_compose_raw") or ""
        if not raw:
            print("  ERROR: empty docker_compose_raw")
            summary.append(f"{cfg['name']}: SKIP empty")
            continue

        new_raw, notes = inject_deploy(raw, cfg["limits"])
        for n in notes:
            print(n)

        if new_raw == raw:
            print("  unchanged")
            summary.append(f"{cfg['name']}: unchanged")
            continue

        diff = difflib.unified_diff(
            raw.splitlines(),
            new_raw.splitlines(),
            fromfile="before",
            tofile="after",
            lineterm="",
            n=2,
        )
        print("  ---- diff ----")
        for line in diff:
            print(f"  {line}")
        print("  ---- end diff ----")

        if args.apply:
            # Coolify v4 requires docker_compose_raw to be base64-encoded on PATCH.
            encoded = base64.b64encode(new_raw.encode()).decode()
            result = api(
                "PATCH", f"/api/v1/services/{uuid}", token, {"docker_compose_raw": encoded}
            )
            print(f"  PATCH OK: {json.dumps(result)[:200]}")
            summary.append(f"{cfg['name']}: PATCHED")
        else:
            summary.append(f"{cfg['name']}: would PATCH")

    print("\n=== summary ===")
    for s in summary:
        print(s)


if __name__ == "__main__":
    main()
