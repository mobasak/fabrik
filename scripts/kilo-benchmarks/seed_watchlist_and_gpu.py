#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_watchlist_and_gpu.py
"""Phase E of best-model-suggester — watch-list inference vendors + GPU providers.

Migrates:
- New table `gpu_providers` (id, provider, gpu_sku, tier, usd_per_hour,
  usd_per_second, cold_start_s, reachable_with_existing_keys, signup_trigger,
  last_verified, notes).
- Adds `agents.signup_trigger TEXT` column.

Seeds:
- Watch-list LLM inference vendors (Together, Hyperbolic, Cerebras, Novita)
  into `agents` with reachable_with_existing_keys=0 — they are candidate
  signups, not currently reachable. Novita LLM price is a $0.40 estimate
  awaiting live probe (see plan Open Unknown #4).
- GPU providers: {vast, runpod, modal} reachable=1 (matches gpu-rent driver set,
  SC #13 coherence); {hyperbolic, novita} reachable=0 watch-list.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "kilo_agents.db"


_GPU_PROVIDERS_DDL = """
CREATE TABLE IF NOT EXISTS gpu_providers (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    gpu_sku TEXT NOT NULL,
    tier TEXT NOT NULL,
    usd_per_hour REAL,
    usd_per_second REAL,
    cold_start_s REAL,
    reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0,
    signup_trigger TEXT,
    last_verified TEXT,
    notes TEXT
);
"""

# Watch-list LLM inference rows (agents table, reachable=0).
_WATCHLIST_AGENTS = [
    # (id, provider, cheapest_gateway_price_usd_per_M_in, signup_trigger, notes)
    ("together/llama-3.3-70b", "together", 0.88,
     "signup for direct-vendor inference with better throughput", "watch-list"),
    ("hyperbolic/llama-3.3-70b", "hyperbolic", 0.40,
     "signup — beats OR by ~30% for Llama 3.3 70B", "watch-list"),
    ("cerebras/llama-3.3-70b", "cerebras", 0.60,
     "signup — cerebras LPU is fastest for Llama 3.3", "watch-list"),
    ("novita/llama-3.3-70b", "novita", 0.40,
     "signup — cheapest observed for Llama 3.3", "estimate — awaiting live probe"),
]

# GPU providers: reachable=1 {vast, runpod, modal} matches gpu-rent driver set.
# Prices below are conservative placeholders for the seed pass; scrape_gpu_prices.py
# refreshes them from live vendor pages.
_GPU_ROWS = [
    # (id, provider, sku, tier, $/hr, $/sec, cold_start_s, reach, signup_trigger, notes)
    ("vast:h100-spot", "vast", "H100", "spot", 1.55, None, None, 1, None, "seed"),
    ("vast:h100-on-demand", "vast", "H100", "on-demand", 1.87, None, None, 1, None, "seed"),
    ("runpod:h100-community", "runpod", "H100", "community", 1.99, None, None, 1, None, "seed"),
    ("runpod:h100-secure", "runpod", "H100", "secure", 3.29, None, None, 1, None, "seed"),
    ("modal:h100-serverless", "modal", "H100", "serverless",
     3.95, 0.001097, 30.0, 1, None, "seed — modal charges per-second"),
    ("hyperbolic:h100", "hyperbolic", "H100", "on-demand", 1.49, None, None, 0,
     "signup — cheaper H100 than vast/runpod on-demand", "watch-list"),
    ("novita:h100", "novita", "H100", "on-demand", 1.79, None, None, 0,
     "signup — mid-market H100", "watch-list"),
]


def _migrate_gpu_providers(conn: sqlite3.Connection) -> None:
    """Create gpu_providers table + add agents.signup_trigger column. Idempotent."""
    conn.execute(_GPU_PROVIDERS_DDL)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(agents)")}
    if "signup_trigger" not in existing:
        conn.execute("ALTER TABLE agents ADD COLUMN signup_trigger TEXT")


def seed_watchlist_and_gpu(conn: sqlite3.Connection) -> tuple[int, int]:
    """Upsert watch-list agents + GPU rows. Returns (agents_upserted, gpu_upserted)."""
    _migrate_gpu_providers(conn)
    a = 0
    for mid, provider, price, trigger, _notes in _WATCHLIST_AGENTS:
        conn.execute(
            "INSERT OR IGNORE INTO agents (id, api_id, name, provider, service_type, "
            "pricing_unit, input_cost_per_m, output_cost_per_m, status, "
            "reachable_with_existing_keys, cheapest_gateway_price, signup_trigger, "
            "last_verified) "
            "VALUES (?, ?, ?, ?, 'llm', 'M-tokens', ?, 0, 'active', 0, ?, ?, DATE('now'))",
            (mid, mid, mid, provider, price, price, trigger),
        )
        conn.execute(
            "UPDATE agents SET reachable_with_existing_keys=0, signup_trigger=?, "
            "cheapest_gateway_price=? WHERE id=?",
            (trigger, price, mid),
        )
        a += 1
    g = 0
    for (mid, provider, sku, tier, hr, sec, cs, reach, trigger, notes) in _GPU_ROWS:
        conn.execute(
            "INSERT OR IGNORE INTO gpu_providers "
            "(id, provider, gpu_sku, tier, usd_per_hour, usd_per_second, "
            " cold_start_s, reachable_with_existing_keys, signup_trigger, "
            " last_verified, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, DATE('now'), ?)",
            (mid, provider, sku, tier, hr, sec, cs, reach, trigger, notes),
        )
        conn.execute(
            "UPDATE gpu_providers SET reachable_with_existing_keys=?, "
            "signup_trigger=?, notes=? WHERE id=?",
            (reach, trigger, notes, mid),
        )
        g += 1
    conn.commit()
    return a, g


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        a, g = seed_watchlist_and_gpu(conn)
    finally:
        conn.close()
    print(f"seed_watchlist_and_gpu: agents upserted={a}, gpu upserted={g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
