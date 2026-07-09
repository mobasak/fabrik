#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/kilo/AI_VENDOR_ACCESS.md scripts/kilo-benchmarks/models_browser.html
"""Scrape SiliconFlow's model catalog + flip `agents.via_siliconflow=1` per exact match.

Live source: https://api.siliconflow.com/v1/models — INTERNATIONAL endpoint.
The `.cn` endpoint uses a different key domain and returns 401 on international keys.

Auth: `SILICONFLOW_API_KEY` in env (see `.env` on WSL dev, hub-injected on VPS).

Mirror of `verify_openrouter_catalog.py`'s per-model logic but stripped to just
the flag-flip: SF pricing is NOT exposed on the /models endpoint (would need
`/v1/{model}/pricing` per-model, out of scope here), so we only populate the
availability flag. Per-model pricing goes in a follow-up scraper.

Idempotent: safe to run daily from `daily_refresh.sh`. Prints match counts to
stderr for observability. Non-fatal on network failure (exits 0 with a WARN).
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"
SF_URL = "https://api.siliconflow.com/v1/models"

# HF-style org → agents.provider normalization.
# SF publishes models as `Org/ModelName` (HuggingFace convention); our DB uses
# lowercase kebab-case for provider. Known mismatches:
_ORG_MAP = {
    "deepseek-ai": "deepseek",
    "zai-org": "z-ai",
    "minimaxai": "minimax",
    "stepfun-ai": "stepfun",
    "wan-ai": "wan-ai",
    "indexteam": "indexteam",
    "tongyi-mai": "tongyi-mai",
    "inclusionai": "inclusionai",
    "funaudiollm": "funaudiollm",
    "fishaudio": "fishaudio",
    "black-forest-labs": "black-forest-labs",  # DB uses same
    "moonshotai": "moonshotai",
    "tencent": "tencent",
    "qwen": "qwen",
    "google": "google",
    "openai": "openai",
    "meituan-longcat": "meituan-longcat",
    "nex-agi": "nex-agi",
    "bytedance-seed": "bytedance-seed",
    "microsoft": "microsoft",
}


def _norm(s: str) -> str:
    """Lowercase + strip + collapse `.` to `-` (mirrors `_canonicalize_id`
    convention from verify_openrouter_catalog.py)."""
    return re.sub(r"[^a-z0-9\-]", "-", (s or "").lower())


def _sf_to_agent_id_candidates(sf_id: str) -> list[str]:
    """Map an SF id like `deepseek-ai/DeepSeek-V4-Flash` to candidate agents.id
    strings the DB might use. Returns a list because DB naming isn't consistent
    (e.g. glm-5.2 vs glm-5-2).
    """
    if "/" not in sf_id:
        return []
    org, model = sf_id.split("/", 1)
    prov = _ORG_MAP.get(org.lower(), org.lower())
    # Basic form: <prov>/<model-lowercase-with-.-preserved-and-_-to->
    model_kebab = model.lower().replace("_", "-")
    model_dot_kebab = model.lower().replace("_", "-").replace(".", "-")
    return [
        f"{prov}/{model_kebab}",
        f"{prov}/{model_dot_kebab}",
    ]


def fetch_sf_models() -> list[dict]:
    """Return SF /v1/models as a list of {id: str, ...} dicts. Never raises;
    empty list on any failure (fail-open — same discipline as pg_ledger)."""
    try:
        import httpx  # local import; script also runs on hosts without httpx

        key = os.getenv("SILICONFLOW_API_KEY")
        if not key:
            print(
                "[sf-scraper] WARN: SILICONFLOW_API_KEY unset — nothing to fetch",
                file=sys.stderr,
            )
            return []
        r = httpx.get(SF_URL, headers={"Authorization": f"Bearer {key}"}, timeout=15.0)
        r.raise_for_status()
        return r.json().get("data", []) if isinstance(r.json(), dict) else []
    except Exception as exc:  # noqa: BLE001 — fail-open contract
        print(f"[sf-scraper] WARN: fetch failed: {exc}", file=sys.stderr)
        return []


def apply_flags(conn: sqlite3.Connection, sf_models: list[dict]) -> tuple[int, int, list[str]]:
    """Flip `via_siliconflow=1` on every agents row that matches an SF id.

    Returns (matched, updated, unmatched_sf_ids). `matched` is how many SF
    entries mapped to a DB row (a single row may match >1 SF entry —
    idempotent flip either way). `updated` is rowcount from the UPDATE.
    """
    matched = 0
    unmatched: list[str] = []
    ids_to_flip: set[str] = set()
    for m in sf_models:
        sf_id = m.get("id") if isinstance(m, dict) else None
        if not sf_id:
            continue
        candidates = _sf_to_agent_id_candidates(sf_id)
        hit = None
        for cand in candidates:
            r = conn.execute("SELECT id FROM agents WHERE id = ?", (cand,)).fetchone()
            if r:
                hit = r[0]
                break
        if hit:
            matched += 1
            ids_to_flip.add(hit)
        else:
            unmatched.append(sf_id)
    if not ids_to_flip:
        return matched, 0, unmatched
    placeholders = ",".join("?" for _ in ids_to_flip)
    cur = conn.execute(
        f"UPDATE agents SET via_siliconflow = 1 WHERE id IN ({placeholders})",  # noqa: S608 — placeholders is a fixed count
        tuple(sorted(ids_to_flip)),
    )
    updated = cur.rowcount
    conn.commit()
    return matched, updated, unmatched


def main() -> int:
    sf = fetch_sf_models()
    if not sf:
        print("[sf-scraper] 0 SF models fetched — nothing to do", file=sys.stderr)
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        matched, updated, unmatched = apply_flags(conn, sf)
    finally:
        conn.close()
    print(
        f"[sf-scraper] fetched {len(sf)} SF models; matched {matched} to agents.id; "
        f"flipped via_siliconflow=1 on {updated} rows"
    )
    if unmatched:
        print(
            f"[sf-scraper] {len(unmatched)} unmatched SF ids (no agents row):",
            file=sys.stderr,
        )
        for sfid in unmatched[:20]:
            print(f"  {sfid}", file=sys.stderr)
        if len(unmatched) > 20:
            print(f"  ... and {len(unmatched) - 20} more", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
