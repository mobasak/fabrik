#!/usr/bin/env python3
"""Scrape OpenRouter's per-model /endpoints API.

For each active `via_openrouter=1` chat model we fetch:
    GET https://openrouter.ai/api/v1/models/<slug>/endpoints

which returns the full inference-provider list — DeepInfra, Fireworks,
Together, Groq, Cerebras, Novita, etc. — each with its own pricing,
quantization, context length, and status. OR's headline
`input_cost_per_m` is usually the DEFAULT-provider price (often a
premium endpoint like Together fp8 for llama-3.3-70b), which can be
6-8× more than the cheapest provider on the same model
(DeepInfra fp8 @ $0.10/M vs Together fp8 @ $1.04/M for that model).

Writes per-row:
  endpoints_json           TEXT  — full endpoint list, JSON
  endpoints_last_scraped   DATE  — YYYY-MM-DD of last successful fetch
  cheapest_provider        TEXT  — name of the min-price provider ('DeepInfra')
  cheapest_provider_price  REAL  — that provider's $/M prompt price
  cheapest_provider_quant  TEXT  — quantization at that provider ('fp8', 'bf16', 'fp16')

Only in-service endpoints (status >= 0) are considered candidates —
OR uses negative status codes to signal disabled/degraded endpoints.

Rate limit: 0.25s between calls (4 req/s) — friendly to OR's API.
340 active OR rows → ~90s wall time.

Idempotent: re-run any day. Rows fetched successfully today are skipped
by default; pass --force to refetch anyway.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

API_BASE = "https://openrouter.ai/api/v1/models"
RATE_LIMIT_S = 0.25
TIMEOUT_S = 20


def _log(msg: str) -> None:
    print(f"[scrape_openrouter_endpoints] {msg}", flush=True)


def _fetch_endpoints(slug: str) -> dict | None:
    url = f"{API_BASE}/{slug}/endpoints"
    req = Request(url, headers={"User-Agent": "fabrik-kilo-benchmarks/1.0"})
    try:
        with urlopen(req, timeout=TIMEOUT_S) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            return {"data": {"id": slug, "endpoints": []}}
        _log(f"HTTP {e.code} for {slug}")
        return None
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        _log(f"error for {slug}: {type(e).__name__} {e}")
        return None


def _extract_cheapest(payload: dict) -> tuple[str | None, float | None, str | None]:
    """Return (provider_name, price_per_m, quant) for the min-price
    in-service endpoint. In-service = status >= 0 (OR uses negative
    codes for disabled/degraded routes)."""
    data = payload.get("data") or {}
    eps = data.get("endpoints") or []
    candidates: list[tuple[float, str, str | None]] = []
    for e in eps:
        status = e.get("status", 0)
        try:
            if int(status) < 0:
                continue
        except (TypeError, ValueError):
            continue
        pr = e.get("pricing") or {}
        prompt = pr.get("prompt")
        if prompt is None:
            continue
        try:
            price_per_token = float(prompt)
        except (TypeError, ValueError):
            continue
        if price_per_token <= 0:
            continue
        price_per_m = price_per_token * 1_000_000
        provider = e.get("provider_name") or e.get("name") or ""
        quant = pr.get("quantization") or e.get("quantization")
        candidates.append((price_per_m, provider, quant))
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda x: x[0])
    price, provider, quant = candidates[0]
    return provider, price, quant


def _ensure_columns(conn: sqlite3.Connection) -> None:
    existing = {r[1] for r in conn.execute("PRAGMA table_info(agents)").fetchall()}
    to_add = [
        ("endpoints_json", "TEXT"),
        ("endpoints_last_scraped", "TEXT"),
        ("cheapest_provider", "TEXT"),
        ("cheapest_provider_price", "REAL"),
        ("cheapest_provider_quant", "TEXT"),
    ]
    for col, typ in to_add:
        if col not in existing:
            conn.execute(f"ALTER TABLE agents ADD COLUMN {col} {typ}")
            _log(f"added column agents.{col}")
    conn.commit()


def run(db_path: Path, force: bool = False, limit: int | None = None) -> dict:
    counts = {"scanned": 0, "fetched": 0, "skipped_recent": 0, "no_endpoints": 0, "errors": 0}
    today = datetime.now(UTC).date().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        _ensure_columns(conn)
        rows = conn.execute(
            "SELECT id, endpoints_last_scraped FROM agents "
            "WHERE via_openrouter=1 AND status='active' "
            "ORDER BY id"
        ).fetchall()
        if limit:
            rows = rows[:limit]
        counts["scanned"] = len(rows)
        for i, (mid, last_scraped) in enumerate(rows, 1):
            if not force and last_scraped == today:
                counts["skipped_recent"] += 1
                continue
            payload = _fetch_endpoints(mid)
            if payload is None:
                counts["errors"] += 1
                time.sleep(RATE_LIMIT_S)
                continue
            provider, price, quant = _extract_cheapest(payload)
            eps = payload.get("data", {}).get("endpoints", [])
            if not eps:
                counts["no_endpoints"] += 1
            conn.execute(
                "UPDATE agents SET "
                "endpoints_json = ?, "
                "endpoints_last_scraped = ?, "
                "cheapest_provider = ?, "
                "cheapest_provider_price = ?, "
                "cheapest_provider_quant = ? "
                "WHERE id = ?",
                (json.dumps(eps), today, provider, price, quant, mid),
            )
            counts["fetched"] += 1
            if counts["fetched"] % 25 == 0:
                conn.commit()
                _log(f"progress {i}/{len(rows)} — fetched={counts['fetched']}")
            time.sleep(RATE_LIMIT_S)
        conn.commit()
    finally:
        conn.close()
    return counts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--force", action="store_true", help="refetch rows already fetched today")
    p.add_argument("--limit", type=int, help="cap number of rows (for smoke tests)")
    args = p.parse_args()
    counts = run(args.db, force=args.force, limit=args.limit)
    _log(f"summary: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
