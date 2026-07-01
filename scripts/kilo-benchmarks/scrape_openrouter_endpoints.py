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
    except (URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as e:
        # UnicodeDecodeError: OR normally returns UTF-8; a mangling proxy
        # or edge case can send non-UTF-8 bytes. Without this catch the
        # whole 340-row loop would crash mid-run, wasting rate-limit
        # budget and leaving partial state. Log + skip is the right call.
        _log(f"error for {slug}: {type(e).__name__} {e}")
        return None


def _prefers_namespace(provider: str, model_id: str | None) -> bool:
    """True if `provider` matches the model-id namespace prefix.

    Anthropic-family models (anthropic/claude-*) are served on OR by
    Anthropic, Google Vertex, and Amazon Bedrock at IDENTICAL prices
    — Anthropic's wholesale deal. Which endpoint "wins" is meaningless
    for the operator's cost question, but showing "Google" as the
    cheapest is misleading (implies Vertex is a discount). When there's
    a tie at min price, prefer the provider whose name matches the model
    namespace (Anthropic for anthropic/*, xAI for x-ai/*, Alibaba for
    alibaba/*, etc.) — that's the natural first-party.
    """
    if not model_id or not provider:
        return False
    ns = model_id.split("/", 1)[0].lower().replace("-", "").replace("_", "")
    pn = provider.lower().replace(" ", "").replace("-", "").replace("_", "")
    if not ns or not pn:
        return False
    return pn.startswith(ns) or ns.startswith(pn) or ns in pn


def _extract_cheapest(
    payload: dict, model_id: str | None = None
) -> tuple[str | None, float | None, str | None]:
    """Return (provider_name, price_per_m, quant) for the min-price
    in-service endpoint. In-service = status >= 0 (OR uses negative
    codes for disabled/degraded routes).

    When multiple providers tie at min price (common for first-party
    models where all endpoints re-sell the same wholesale rate),
    prefer the provider matching `model_id`'s namespace so the UI
    shows "Anthropic" for anthropic/* instead of an arbitrary
    Google/Bedrock re-seller."""
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
        # OR's endpoint schema uses `provider_name` for the clean
        # display name ("DeepInfra"). The bare `name` field is the full
        # endpoint identifier ("DeepInfra | meta-llama/llama-3.3-70b-
        # instruct") — useless as a provider label and misleading in the
        # UI. If provider_name is missing (never observed in practice
        # but defensive), skip the endpoint rather than fall back to a
        # garbage label that then hits the DB and the browser.
        provider = e.get("provider_name")
        if not provider:
            continue
        quant = pr.get("quantization") or e.get("quantization")
        candidates.append((price_per_m, provider, quant))
    if not candidates:
        return None, None, None
    candidates.sort(key=lambda x: x[0])
    min_price = candidates[0][0]
    # Namespace preference on price ties (within $0.005/M of the min).
    # Prefers the first-party for models like anthropic/claude-opus-4.8
    # where 6 endpoints all list identical $5/M and the first-in-list is
    # arbitrary (Google Vertex misleadingly labeled as "cheapest").
    ties = [c for c in candidates if c[0] - min_price <= 0.005]
    if len(ties) > 1:
        for cand_price, cand_provider, cand_quant in ties:
            if _prefers_namespace(cand_provider, model_id):
                return cand_provider, cand_price, cand_quant
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
            provider, price, quant = _extract_cheapest(payload, model_id=mid)
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
