#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_suggest_model.py
"""Phase B of best-model-suggester — Pareto-ranked model suggester.

Reads `agents` filtered by service_type + reachable_with_existing_keys=1, computes
per-workload cost given a --volume flag, and ranks by (cost ↑, quality_elo ↓)
Pareto frontier. Exit codes:
  0 = ≥1 candidate printed
  1 = empty pool (message: NO DATA for task=<t> under accessible vendors)
  2 = missing --volume flag (message: --volume-<unit> required for --task <t>)
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

_DEFAULT_DB = Path(__file__).parent / "kilo_agents.db"
CATALOG_PATH = (
    Path(__file__).parent.parent.parent
    / "docs" / "reference" / "kilo" / "AI_VENDOR_ACCESS.md"
)

# Grounded 2026-07-05 — per-family avg tokens per image (for M-tokens image_gen rows).
AVG_TOKENS_PER_IMAGE = {
    "google": 1290,
    "openai": 1024,
    "microsoft": 1024,
    "bytedance-seed": 1024,
    "x-ai": 1024,
    "sourceful": 1024,
}
DEFAULT_TOKENS_PER_IMAGE = 2048  # conservative over-estimate

VOLUME_FLAG_BY_TASK = {
    "tts": "--volume-chars",
    "stt": "--volume-minutes",
    "translation": "--volume-chars",
    "image_gen": "--volume-images",
    "music_gen": "--volume-images",
    "video_gen": "--volume-images",  # future task class; empty pool exits 1 today
    "llm": None,
    "coding_llm": None,
}


def _db_path() -> Path:
    p = os.getenv("KILO_DB")
    return Path(p) if p else _DEFAULT_DB


def _normalize_cost(row: dict, volume: dict) -> float:
    """Per-workload cost given the row + volume kwargs. Handles mixed pricing_unit."""
    unit = row.get("pricing_unit") or "M-tokens"
    cpm = row.get("input_cost_per_m") or 0.0
    if unit == "image":
        return (cpm / 1_000_000) * volume.get("images", 0)
    if unit == "M-chars":
        return (cpm / 1_000_000) * volume.get("chars", 0)
    if unit == "audio-min":
        return (cpm / 1_000_000) * volume.get("minutes", 0)
    if unit == "M-tokens":
        provider = (row.get("provider") or "").split("/")[0]
        toks = AVG_TOKENS_PER_IMAGE.get(provider)
        if toks is None:
            print(
                f"warn: no avg_tokens_per_image for {row['id']}, using {DEFAULT_TOKENS_PER_IMAGE}",
                file=sys.stderr,
            )
            toks = DEFAULT_TOKENS_PER_IMAGE
        return (cpm / 1_000_000) * toks * volume.get("images", 0)
    return 0.0


def _rank_service_type(conn: sqlite3.Connection, service_type: str, **volume) -> list[dict]:
    """Query accessible rows for the service_type, compute per-workload cost, Pareto-rank."""
    rows = conn.execute(
        "SELECT id, provider, service_type, pricing_unit, input_cost_per_m, "
        "quality_elo, output_tokens_per_sec, perf_seconds, reachable_with_existing_keys "
        "FROM agents "
        "WHERE service_type = ? AND status = 'active' "
        "AND reachable_with_existing_keys = 1",
        (service_type,),
    ).fetchall()
    fields = [
        "id", "provider", "service_type", "pricing_unit", "input_cost_per_m",
        "quality_elo", "output_tokens_per_sec", "perf_seconds",
        "reachable_with_existing_keys",
    ]
    result = []
    for r in rows:
        d = dict(zip(fields, r))
        d["cost_usd"] = _normalize_cost(d, volume)
        result.append(d)
    # Pareto: drop rows dominated on (lower cost, higher quality_elo).
    frontier = []
    for a in result:
        dominated = False
        for b in result:
            if a is b:
                continue
            q_a = a.get("quality_elo") or 0
            q_b = b.get("quality_elo") or 0
            if (b["cost_usd"] <= a["cost_usd"] and q_b >= q_a
                    and (b["cost_usd"] < a["cost_usd"] or q_b > q_a)):
                dominated = True
                break
        if not dominated:
            frontier.append(a)
    frontier.sort(key=lambda r: (r["cost_usd"], -(r.get("quality_elo") or 0)))
    return frontier


def _print_markdown_table(rows: list[dict]) -> None:
    print("| Model | Provider | Cost (USD) | quality_elo | Notes |")
    print("|---|---|---:|---:|---|")
    for r in rows:
        q = f"{r['quality_elo']:.0f}" if r.get("quality_elo") else "—"
        note = ""
        print(f"| `{r['id']}` | {r['provider']} | ${r['cost_usd']:.4f} | {q} | {note} |")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task", required=True, choices=list(VOLUME_FLAG_BY_TASK))
    p.add_argument("--volume-chars", type=int)
    p.add_argument("--volume-minutes", type=float)
    p.add_argument("--volume-images", type=int)
    p.add_argument("--quality-tier", choices=["cheap", "balanced", "expressive", "premium"], default="balanced")
    p.add_argument("--language", default=None)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    required_flag = VOLUME_FLAG_BY_TASK[args.task]
    if required_flag:
        attr = required_flag.lstrip("-").replace("-", "_")
        flag_val = getattr(args, attr)
        if flag_val is None:
            print(f"error: {required_flag} required for --task {args.task}", file=sys.stderr)
            return 2

    conn = sqlite3.connect(_db_path())
    try:
        frontier = _rank_service_type(
            conn, args.task,
            chars=args.volume_chars or 0,
            minutes=args.volume_minutes or 0.0,
            images=args.volume_images or 0,
        )
    finally:
        conn.close()

    if not frontier:
        print(
            f"NO DATA for task={args.task} under accessible vendors — "
            "populate specialty catalog for this task class before suggesting.",
            file=sys.stderr,
        )
        return 1

    top = frontier[: args.top]
    if args.json:
        print(json.dumps(top, indent=2, default=str))
    else:
        _print_markdown_table(top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
