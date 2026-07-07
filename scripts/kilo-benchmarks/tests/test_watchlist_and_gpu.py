"""Tests for seed_watchlist_and_gpu.py — Phase E of best-model-suggester.

Highest-risk paths:
- gpu_providers schema migration is idempotent (repeated calls don't raise).
- Watch-list inference rows all land with reachable_with_existing_keys=0.
- GPU reachable=1 set matches fabrik-lib/gpu-rent's driver set exactly
  ({vast, runpod, modal}) — coherence anchor for SC #13.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _bare_conn(tmp_path):
    db = tmp_path / "gpu_test.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY, api_id TEXT, name TEXT, provider TEXT,
            service_type TEXT, pricing_unit TEXT, input_cost_per_m REAL,
            output_cost_per_m REAL, quality_elo REAL, output_tokens_per_sec REAL,
            perf_seconds REAL, status TEXT,
            reachable_with_existing_keys INTEGER NOT NULL DEFAULT 0,
            cheapest_gateway_price REAL, last_verified TEXT
        );
        """
    )
    return conn


def test_gpu_providers_migration_idempotent(tmp_path):
    from seed_watchlist_and_gpu import _migrate_gpu_providers

    conn = _bare_conn(tmp_path)
    _migrate_gpu_providers(conn)
    _migrate_gpu_providers(conn)  # second call must not raise
    cols = {r[1] for r in conn.execute("PRAGMA table_info(gpu_providers)")}
    required = {
        "id", "provider", "gpu_sku", "tier", "usd_per_hour", "usd_per_second",
        "reachable_with_existing_keys", "signup_trigger",
    }
    assert required <= cols, f"missing cols: {required - cols}"
    agent_cols = {r[1] for r in conn.execute("PRAGMA table_info(agents)")}
    assert "signup_trigger" in agent_cols
    conn.close()


def test_watchlist_seeded_rows_all_have_reachable_zero(tmp_path):
    from seed_watchlist_and_gpu import seed_watchlist_and_gpu

    conn = _bare_conn(tmp_path)
    seed_watchlist_and_gpu(conn)
    rows = conn.execute(
        "SELECT provider FROM agents "
        "WHERE provider IN ('together','hyperbolic','cerebras','novita') "
        "AND reachable_with_existing_keys=1"
    ).fetchall()
    assert rows == [], f"watch-list vendors must be reachable=0, got: {rows}"
    conn.close()


def test_gpu_reachable_set_matches_gpu_rent_drivers(tmp_path):
    """SC #13 coherence: reachable=1 GPU providers exactly = fabrik-lib/gpu-rent driver set."""
    from seed_watchlist_and_gpu import seed_watchlist_and_gpu

    conn = _bare_conn(tmp_path)
    seed_watchlist_and_gpu(conn)
    reachable = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT provider FROM gpu_providers WHERE reachable_with_existing_keys=1"
        )
    }
    assert reachable == {"vast", "runpod", "modal"}, f"drift: {reachable}"
    conn.close()
