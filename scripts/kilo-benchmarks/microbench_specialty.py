#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_microbench_specialty.py
"""Specialty-service bench dispatcher.

Plan 2026-07-03-plan-1-full-speed-coverage-close.md Phase B.4.

Cohort: agents.status='active' AND service_type IN ('image_gen','tts','music_gen','stt','translation')
        AND (perf_seconds IS NULL OR speed_updated_at < cutoff).

Dispatches by row's `id` prefix to the right specialty_clients/*.bench_one().
Reuses microbench_or_models.py's per-write short-lived sqlite connections
+ non-fatal write failure pattern.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import statistics
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from add_perf_seconds_column import ensure_perf_seconds_column  # noqa: E402
from specialty_clients import (  # noqa: E402
    bfl_via_fal,
    dashscope_translation,
    elevenlabs_sfx,
    elevenlabs_tts,
    openai_whisper,
    recraft,
    replicate,
)
from specialty_pricing import PRICING, estimate_cost  # noqa: E402

DB_PATH = SCRIPT_DIR / "kilo_agents.db"
COST_CAP_USD = 10.0
COST_SOFT_CAP_USD = 2.50
RECENCY_WINDOW_DAYS = 30
BENCH_N_RUNS = 3
RATE_LIMIT_SLEEP_S = 1.0


def log(msg: str) -> None:
    print(f"[microbench_specialty] {msg}", flush=True)


def _dispatch(model_id: str, service_type: str, keys: dict) -> tuple:
    """Return (bench_fn, api_key, provider_tag)."""
    via = (PRICING.get(model_id) or {}).get("via", "")
    if via == "fal_ai" or model_id.startswith("bfl/") or model_id.startswith("black-forest-labs/"):
        return bfl_via_fal.bench_one, keys.get("FAL_KEY"), "fal_bfl"
    if via == "recraft_direct" or model_id.startswith("recraft/"):
        return recraft.bench_one, keys.get("RECRAFT_API_KEY"), "recraft_direct"
    if via == "replicate":
        return replicate.bench_one, keys.get("REPLICATE_API_TOKEN"), "replicate_direct"
    if model_id.startswith("elevenlabs/") and service_type == "tts":
        return elevenlabs_tts.bench_one, keys.get("ELEVENLABS_API_KEY"), "elevenlabs_direct"
    if model_id.startswith("elevenlabs/") and service_type == "music_gen":
        return elevenlabs_sfx.bench_one, keys.get("ELEVENLABS_API_KEY"), "elevenlabs_direct"
    if service_type == "stt" and "whisper" in model_id:
        return openai_whisper.bench_one, keys.get("OPENAI_API_KEY"), "openai_direct"
    if service_type == "translation" and "qwen-mt" in model_id:
        return dashscope_translation.bench_one, keys.get("DASHSCOPE_API_KEY"), "dashscope_direct"
    return None, None, None


def bench_median(model_id: str, service_type: str, keys: dict) -> dict:
    fn, key, tag = _dispatch(model_id, service_type, keys)
    if fn is None:
        return {"perf_seconds": None, "cost_usd": 0.0, "error": f"no client for {model_id}", "tag": None}
    if not key:
        return {"perf_seconds": None, "cost_usd": 0.0, "error": "provider key not set", "tag": tag}
    results = []
    total_cost = 0.0
    for i in range(BENCH_N_RUNS):
        r = fn(model_id, key)
        total_cost += r.get("cost_usd", 0.0)
        if r["error"] is None:
            results.append(r["perf_seconds"])
        elif "[FAL-BALANCE-EXHAUSTED]" in (r["error"] or ""):
            return {"perf_seconds": None, "cost_usd": total_cost, "error": r["error"], "tag": tag}
        if i < BENCH_N_RUNS - 1:
            time.sleep(RATE_LIMIT_SLEEP_S)
    if len(results) < 2:
        return {"perf_seconds": None, "cost_usd": total_cost,
                "error": f"{BENCH_N_RUNS - len(results)}/{BENCH_N_RUNS} calls failed",
                "tag": tag}
    return {"perf_seconds": round(statistics.median(results), 2),
            "cost_usd": round(total_cost, 6), "error": None, "tag": tag}


def _select_cohort(conn: sqlite3.Connection) -> list[dict]:
    cutoff = (datetime.now(UTC).date() - timedelta(days=RECENCY_WINDOW_DAYS)).isoformat()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, service_type
        FROM agents
        WHERE status='active'
          AND service_type IN ('image_gen','tts','music_gen','stt','translation')
          AND (perf_seconds IS NULL OR speed_updated_at < ?)
        ORDER BY service_type, id
        """,
        (cutoff,),
    ).fetchall()
    return [dict(r) for r in rows]


def _write_result(db_path: Path, agent_id: str, result: dict) -> bool:
    today = datetime.now(UTC).date().isoformat()
    tag = f"{result['tag']} {today}" if result.get("tag") else f"unknown_direct {today}"
    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            conn.execute(
                "UPDATE agents SET perf_seconds=?, speed_source=?, speed_updated_at=? "
                "WHERE id=?",
                (result["perf_seconds"], tag, today, agent_id),
            )
        return True
    except sqlite3.OperationalError as e:
        log(f"  → WRITE-FAIL: {e}")
        return False


def run_specialty(dry_run: bool = False, limit: int | None = None) -> int:
    load_dotenv()
    ensure_perf_seconds_column(DB_PATH)
    keys = {
        "FAL_KEY": os.getenv("FAL_KEY"),
        "RECRAFT_API_KEY": os.getenv("RECRAFT_API_KEY"),
        "REPLICATE_API_TOKEN": os.getenv("REPLICATE_API_TOKEN"),
        "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY"),
    }
    conn = sqlite3.connect(DB_PATH)
    cohort = _select_cohort(conn)
    conn.close()
    if limit:
        cohort = cohort[:limit]
    log(f"cohort: {len(cohort)} rows")
    if dry_run:
        est = sum(estimate_cost(r["id"]) * BENCH_N_RUNS for r in cohort)
        log(f"dry-run est cost: ${est:.2f}")
        return 0
    running_cost = 0.0
    updated = failed = 0
    for i, row in enumerate(cohort, 1):
        if running_cost >= COST_CAP_USD:
            log(f"cost_stop: ${running_cost:.4f} >= cap ${COST_CAP_USD}")
            break
        log(f"[{i}/{len(cohort)}] bench {row['id']} ({row['service_type']}) (spent ${running_cost:.4f})")
        result = bench_median(row["id"], row["service_type"], keys)
        running_cost += result.get("cost_usd", 0.0)
        if result["error"]:
            failed += 1
            log(f"  → FAIL: {result['error']}")
            continue
        if _write_result(DB_PATH, row["id"], result):
            updated += 1
            log(f"  → perf_seconds={result['perf_seconds']} cost=${result['cost_usd']}")
        else:
            failed += 1
    log(f"summary: cohort={len(cohort)} updated={updated} failed={failed} cost=${running_cost:.4f}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    return run_specialty(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    sys.exit(main())
