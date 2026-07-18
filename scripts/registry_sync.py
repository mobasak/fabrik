#!/usr/bin/env python3
# AFTER-EDIT: scripts/registry_db.py db/services_registry_schema.sql
"""Load secrets/all-envs.env (the #svc-annotated consolidation) into the local Postgres registry.

Reads each #svc block + its KEY=value lines and upserts `services` + `api_keys`. Stores
value_sha256 (SHA-256 of the secret) — NEVER the raw secret (the secret lives only in
all-envs.env, chmod 600). Idempotent: ON CONFLICT upserts and only bumps last_seen on re-run.
internal-config vars are excluded (not services).
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import registry_db  # noqa: E402
from credit_fetchers import fetch_balance  # noqa: E402

ALL_ENVS = REPO / "secrets" / "all-envs.env"
SVC_RE = re.compile(
    r'#svc name=(?P<name>\S+) category=(?P<category>\S+) cost=(?P<cost>\S+) '
    r'capability="(?P<capability>[^"]*)" url=(?P<url>\S+) status=(?P<status>\S+)'
    r"(?: used_by=(?P<used_by>\S*))?"
)
KV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def parse(path: Path) -> list[dict]:
    """Return [{meta:{name,category,...,used_by}, keys:[(key, value, aliases)]}] per provider."""
    provs: list[dict] = []
    cur: dict | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# ═"):  # section header
            cur = None  # a header ends the current provider block (incl. internal-config)
            continue
        m = SVC_RE.match(line)
        if m:
            cur = {"meta": m.groupdict(), "keys": []}
            provs.append(cur)
            continue
        kv = KV_RE.match(line)
        if cur is not None and kv:
            key, rest = kv.group(1), kv.group(2)
            # "   # " (3-space-hash-SPACE) is gather_envs' exact note delimiter; splitting on it
            # (not "   #") avoids truncating a value that merely contains "   #".
            value = rest.split("   # ", 1)[0].strip()
            aliases: list[str] = []
            per_key_used: list[str] = []
            if "   # " in rest:
                note = rest.split("   # ", 1)[1]
                if "aliases:" in note:
                    seg = note.split("aliases:", 1)[1].split("·")[0]
                    aliases = [a.strip() for a in seg.split(",") if a.strip()]
                if "used by:" in note:
                    seg = note.split("used by:", 1)[1]
                    per_key_used = [p.strip() for p in seg.split(",") if p.strip()]
            cur["keys"].append((key, value, aliases, per_key_used))
    return provs


def sync_registry(dsn: str | None = None, fetch_credits: bool = False) -> dict:
    if dsn:
        os.environ["SERVICES_REGISTRY_DSN"] = dsn
    provs = parse(ALL_ENVS)
    stats = {"services": 0, "api_keys": 0, "credit_snapshots": 0}
    conn = registry_db.connect()
    try:
        with conn, conn.cursor() as cur:
            for p in provs:
                meta = p["meta"]
                ub = meta.get("used_by") or ""
                used_by = [x for x in ub.split(",") if x and x != "-"]
                cur.execute(
                    """INSERT INTO services (provider, category, cost_tier, url, status)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (provider) DO UPDATE SET category=EXCLUDED.category,
                         cost_tier=EXCLUDED.cost_tier, url=EXCLUDED.url, status=EXCLUDED.status
                       RETURNING id""",
                    (meta["name"], meta["category"], meta["cost"], meta["url"], meta["status"]),
                )
                sid = cur.fetchone()[0]
                stats["services"] += 1
                first_value = None
                for _key, value, aliases, per_key_used in p["keys"]:
                    if not value:
                        continue
                    first_value = first_value or value
                    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
                    # per-key attribution when present (a multi-key provider's keys differ),
                    # else the provider-wide union from the #svc used_by= field.
                    key_used = per_key_used or used_by
                    cur.execute(
                        """INSERT INTO api_keys (service_id, value_sha256, aliases, used_by_projects)
                           VALUES (%s,%s,%s,%s)
                           ON CONFLICT (service_id, value_sha256)
                           DO UPDATE SET last_seen=now(), aliases=EXCLUDED.aliases,
                             used_by_projects=EXCLUDED.used_by_projects""",
                        (sid, digest, aliases, key_used),
                    )
                    stats["api_keys"] += 1
                # Hybrid credit: fetch the account balance where a provider API exposes it.
                # Resilient — fetch_balance returns None on any failure, so a dead vendor never
                # sinks the sync. The REAL key stays host-side (sent only to the vendor's API).
                if fetch_credits and first_value:
                    snap = fetch_balance(meta["name"], first_value)
                    if snap is not None:
                        cur.execute(
                            "INSERT INTO credit_snapshots (service_id, balance, unit) VALUES (%s,%s,%s)",
                            (sid, snap.balance, snap.unit),
                        )
                        stats["credit_snapshots"] += 1
    finally:
        conn.close()
    return stats


def main() -> int:
    if not ALL_ENVS.exists():
        print(f"{ALL_ENVS} missing — run scripts/gather_envs.py --apply first", file=sys.stderr)
        return 1
    stats = sync_registry()
    print(f"synced {stats['services']} services, {stats['api_keys']} api_keys into the registry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
