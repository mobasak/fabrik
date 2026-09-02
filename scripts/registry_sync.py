#!/usr/bin/env python3
# AFTER-EDIT: scripts/registry_db.py db/services_registry_schema.sql
"""Load secrets/all-envs.env (the #svc-annotated consolidation) into the local Postgres registry.

Reads each #svc block + its KEY=value lines and upserts `services` + `api_keys`. Stores
value_sha256 (SHA-256 of the secret) — NEVER the raw secret (the secret lives only in
all-envs.env, chmod 600). Idempotent: ON CONFLICT upserts and only bumps last_seen on re-run.
internal-config vars are excluded (not services).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import gather_envs  # noqa: E402 - the one classifier of secret vs config, shared with the scan
import registry_db  # noqa: E402
from credit_fetchers import fetch_balance  # noqa: E402

ALL_ENVS = REPO / "secrets" / "all-envs.env"
SVC_RE = re.compile(
    r"#svc name=(?P<name>\S+) category=(?P<category>\S+) cost=(?P<cost>\S+) "
    r'capability="(?P<capability>[^"]*)" url=(?P<url>\S+) status=(?P<status>\S+)'
    r"(?: used_by=(?P<used_by>\S*))?"
)
# A key NAME that carries a credential (the value is a secret): the fetcher's input.
CREDENTIAL_KEY_RE = re.compile(
    r"(API_KEY|APIKEY|API_TOKEN|TOKEN|SECRET|PASSWORD|PASS|AUTH_KEY|KEY)S?$", re.I
)


# Public identifiers (OAuth client/tenant/account/project ids) are long, alphanumeric and NOT
# secrets — value entropy alone calls them credentials (AD1: M365_CLIENT_ID, GOOGLE_CLIENT_ID,
# R2_ACCOUNT_ID …, 26 live pairs). A credential is credential-shaped by NAME, or secret-shaped by
# value with a name that is not an identifier.
IDENTIFIER_KEY_RE = re.compile(
    r"(_ID|_IDS|_UUID|_NUMBER|_ARN|_REGION|_ZONE|_HOST|_PORT|_MODEL|_VERSION|_URL|_URLS|_ENDPOINT|_BASE|_DOMAIN)$",
    re.I,
)
# a DSN/URL that CARRIES a password (`scheme://user:pw@host`) is a credential whatever its name
USERINFO_RE = re.compile(r"://[^/@\s]+:[^/@\s]+@")


def is_credential(key: str, value: str) -> bool:
    """`kind` is decided by the NAME first — the value-entropy branch of `gather_envs.is_secret`
    calls any 24+-char alphanumeric value a secret (API URLs, tenant ids, model names — 48 live
    vendor rows, AF1). Order: credential-shaped name → yes; URL/identifier-shaped name → no unless
    the value embeds userinfo; otherwise the value decides."""
    if CREDENTIAL_KEY_RE.search(key) or gather_envs.SECRET_KEY_RE.search(key):
        return True
    if USERINFO_RE.search(value):
        return True
    if IDENTIFIER_KEY_RE.search(key):
        return False
    return gather_envs.is_secret(key, value)


def ensure_schema(cur) -> None:
    """Idempotent forward migration: `api_keys.kind` ('credential' | 'config' | 'code-host') — a code
    call-site row is a public URL's digest, not a secret, and the dashboard must not count it
    as a key (review 2026-09-02, O4). `db/services_registry_schema.sql` carries the column for
    fresh installs; this brings an existing registry level on its next sync."""
    # Probe first: even a no-op `ADD COLUMN IF NOT EXISTS` takes ACCESS EXCLUSIVE, which waits
    # behind ANY open reader transaction (an idle dashboard-server read stalled the daily sync
    # in review, closing pass — N3). The probe is ACCESS SHARE; the ALTER runs once, ever.
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema=current_schema() "
        "AND table_name='api_keys' AND column_name='kind'"
    )
    if cur.fetchone() is None:
        cur.execute(
            "ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'credential'"
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


def sync_registry(
    dsn: str | None = None,
    fetch_credits: bool = False,
    prune: bool = True,
    prune_keys: bool
    | None = None,  # default = prune; a PARTIAL file must not delete a provider's other keys (Z7)
) -> dict:
    if dsn:
        os.environ["SERVICES_REGISTRY_DSN"] = dsn
    provs = parse(ALL_ENVS)
    stats = {"services": 0, "api_keys": 0, "credit_snapshots": 0, "pruned": 0, "keys_pruned": 0}
    to_fetch: list[tuple[int, str, str]] = []
    conn = registry_db.connect()
    # Schema first, in its OWN short transaction: an ALTER inside the sync transaction holds an
    # ACCESS EXCLUSIVE lock on api_keys for the whole run (measured: the no-op ADD COLUMN IF NOT
    # EXISTS still takes it), blocking the live dashboard server's reads (closing review 2026-09-02).
    try:
        with conn, conn.cursor() as cur:
            ensure_schema(cur)
    except Exception:
        conn.close()
        raise
    try:
        with conn, conn.cursor() as cur:
            # Bounded-prune denominator: the PRE-EXISTING registry size, captured BEFORE the
            # upserts below insert this file's providers — else a corrupt file that ADDS many
            # bogus rows inflates the denominator and a mass real-provider delete slips under
            # the cap (the exact irreversible outcome the bound exists to prevent).
            cur.execute("SELECT count(*) FROM services")
            preexisting_total = cur.fetchone()[0]
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
                fallback_value = None
                digests: list[str] = []
                for _key, value, aliases, per_key_used in p["keys"]:
                    if not value:
                        continue
                    # The credit fetcher gets the first CREDENTIAL, chosen by the KEY's role, never
                    # by line order: `CODE_HOST_URL` sorts before `DEEPL_API_KEY` and
                    # `AZURE_ACCOUNT_NAME` before `AZURE_API_KEY` (review 2026-09-02, N1 + O5).
                    # `code-host` is the SYNTHETIC key only — never a value shape: a proxy URL with
                    # userinfo (`NAMECHEAP_PROXY_URL=http://u:pw@…`) is a credential (pass 2, G3)
                    if _key == "CODE_HOST_URL":
                        kind = "code-host"
                    elif is_credential(_key, value):
                        kind = "credential"
                    else:
                        kind = "config"  # a URL/host/port/model/ID knob under a vendor prefix — never a key (AC6/AD1)
                    if kind == "credential":
                        if CREDENTIAL_KEY_RE.search(_key):
                            first_value = first_value or value
                        elif not value.lower().startswith(("http://", "https://")):
                            fallback_value = fallback_value or value  # e.g. GROQ_API_KEY_2 (G4)
                    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
                    digests.append(digest)
                    # per-key attribution when present (a multi-key provider's keys differ),
                    # else the provider-wide union from the #svc used_by= field.
                    key_used = per_key_used or used_by
                    cur.execute(
                        """INSERT INTO api_keys (service_id, value_sha256, aliases, used_by_projects, kind)
                           VALUES (%s,%s,%s,%s,%s)
                           ON CONFLICT (service_id, value_sha256)
                           DO UPDATE SET last_seen=now(), aliases=EXCLUDED.aliases,
                             used_by_projects=EXCLUDED.used_by_projects, kind=EXCLUDED.kind""",
                        (sid, digest, aliases, key_used, kind),
                    )
                    stats["api_keys"] += 1
                # Keys that LEFT this provider (a code host no longer referenced, a var moved to
                # internal-config) are deleted — upsert-only rows lived forever, and the code-host
                # input makes churn daily (closing review 2026-09-02, N2). Per-service, never global.
                if digests and (
                    prune if prune_keys is None else prune_keys
                ):  # `<> ALL('{}')` is TRUE for every row
                    cur.execute(
                        "DELETE FROM api_keys WHERE service_id=%s AND value_sha256 <> ALL(%s)",
                        (sid, digests),
                    )
                    stats["keys_pruned"] += cur.rowcount
                cred = first_value or fallback_value
                if fetch_credits and cred:
                    to_fetch.append((sid, meta["name"], cred))  # fetch AFTER commit
            # Prune orphans: services no longer in all-envs.env (e.g. a provider recatalogued
            # under a new match prefix leaves its old `?` row behind). Children cascade-delete.
            # GUARD 1: never prune when the parse yielded nothing — an empty/corrupt file must not
            # wipe the whole registry. `prune=False` is for callers syncing a PARTIAL file (e.g.
            # tests with a one-provider fixture) that must not delete the rest of the registry.
            # GUARD 2 (bounded prune): a mass-delete means the FILE is wrong (corrupted #svc lines
            # dropping providers from `seen`), not the registry — cascade-deleting credit_snapshots
            # history is irreversible, so refuse loudly instead of pruning silently. Cap: roughly
            # >20% of the registry (integer //5, min 5) aborts the whole transaction (upserts
            # included — sync fails loud).
            seen = [p["meta"]["name"] for p in provs]
            if prune and seen:
                cur.execute("DELETE FROM services WHERE provider <> ALL(%s)", (seen,))
                allowed = max(5, preexisting_total // 5)
                # Explicit truthy values ONLY — a conventional "0"/"false"/"no" must NOT
                # silently disable a data-loss guard (any-non-empty truthiness would).
                force = os.getenv("REGISTRY_PRUNE_FORCE", "").strip().lower() in (
                    "1",
                    "true",
                    "yes",
                )
                if cur.rowcount > allowed and not force:
                    raise RuntimeError(
                        f"bounded prune: refusing to delete {cur.rowcount}/{preexisting_total} "
                        f"services (> {allowed} allowed) — all-envs.env is likely corrupt/"
                        "truncated; no changes applied (transaction rolled back). If this is a "
                        "LEGITIMATE mass recatalog, re-run once with REGISTRY_PRUNE_FORCE=1."
                    )
                stats["pruned"] = cur.rowcount
    finally:
        conn.close()
    # Hybrid credit: fetch balances OUTSIDE the upsert transaction — network I/O must never hold
    # the services/api_keys row locks. fetch_balance never raises (guarded); a dead vendor => no
    # snapshot. The REAL key stays host-side (sent only to the vendor's own API).
    if to_fetch:
        conn2 = registry_db.connect()
        try:
            for sid, name, value in to_fetch:
                snap = fetch_balance(name, value)
                if snap is not None:
                    with conn2, conn2.cursor() as cur:
                        cur.execute(
                            "INSERT INTO credit_snapshots (service_id, balance, unit) VALUES (%s,%s,%s)",
                            (sid, snap.balance, snap.unit),
                        )
                    stats["credit_snapshots"] += 1
        finally:
            conn2.close()
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--fetch-credits",
        action="store_true",
        help="also call each provider's credit fetcher and store a credit_snapshots row "
        "(network; the daily path passes it, a quick manual sync omits it)",
    )
    args = ap.parse_args()
    if not ALL_ENVS.exists():
        print(f"{ALL_ENVS} missing — run scripts/gather_envs.py --apply first", file=sys.stderr)
        return 1
    stats = sync_registry(fetch_credits=args.fetch_credits)
    print(
        f"synced {stats['services']} services, {stats['api_keys']} api_keys, "
        f"{stats['credit_snapshots']} credit snapshots into the registry "
        f"(pruned {stats['pruned']} services, {stats['keys_pruned']} stale keys)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
