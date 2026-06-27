#!/usr/bin/env python3
"""Multi-signal quality_tier deriver. Replaces the old single-source
arena+tbench-only logic in `migrate_selector_columns.py` with a
weight-of-evidence approach that uses:

  1. Chatbot Arena ELO (existing column)            — 30% coverage
  2. Terminal Bench accuracy (existing column)      — 12% coverage
  3. Weighted coding score (existing column)        —  8% coverage
  4. OpenRouter design_arena ELOs (NEW from API)    — 40% coverage
  5. OpenRouter Artificial Analysis index (NEW)     — 19% coverage
  6. Model family / id pattern (NEW)                — 100% coverage
  7. Input price (cost as quality proxy)            — 100% coverage
  8. Reasoning capability flag                      — 29% coverage
  9. Context window size                            — 100% coverage

A model passes a tier floor if ANY signal places it there. No single
signal is required, so a frontier model with no public benchmarks
still gets T3 from its family + price + reasoning combo.

This script is called from `daily_refresh.sh` after the verifier
and before the classifier. Idempotent — same DB + same OpenRouter
cache → byte-identical tier assignments.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
CACHE_PATH = SCRIPT_DIR / "cache" / "openrouter_live_catalog.json"

# Family patterns. Order matters — earlier matches win.
# Each entry: (compiled regex on id, tier, label) — tier is a FLOOR.
FAMILY_TIERS: list[tuple[re.Pattern, int, str]] = [
    # T3 frontier — flagship models from the top providers.
    (re.compile(r"^(anthropic|~anthropic|stealth)/claude-opus(?:-|$)"), 3, "claude-opus"),
    (re.compile(r"^anthropic/claude-fable"), 3, "claude-fable"),
    (re.compile(r"^openai/gpt-5(\.\d+)?(-pro)?$"), 3, "gpt-5/pro"),
    (re.compile(r"^openai/o[1-9](-pro|-deep-research)?$"), 3, "o-series"),
    (re.compile(r"^openai/gpt-5(\.\d+)?-pro$"), 3, "gpt-5-pro"),
    (re.compile(r"^google/gemini-[34]\.?\d*-pro"), 3, "gemini-pro"),
    (re.compile(r"^x-ai/grok-[345](\.\d+)?$"), 3, "grok-3+"),
    (re.compile(r"^deepseek/deepseek-(r1|v3\.2|v4-pro)"), 3, "deepseek-r1/v4-pro"),
    (re.compile(r"^qwen/qwen3\.\d+-max"), 3, "qwen-max"),
    (re.compile(r"^qwen/qwen3-235b"), 3, "qwen3-235b"),
    (re.compile(r"^moonshotai/kimi-k[23]"), 3, "kimi-k2/k3"),
    (re.compile(r"^z-ai/glm-[5-9]"), 3, "glm-5+"),
    # T2 strong — capable mid-tier.
    (re.compile(r"^(anthropic|~anthropic|stealth)/claude-sonnet"), 2, "claude-sonnet"),
    (re.compile(r"^anthropic/claude-3\.[5-9]"), 2, "claude-3.5+"),
    (re.compile(r"^openai/gpt-5(\.\d+)?-mini"), 2, "gpt-5-mini"),
    (re.compile(r"^openai/gpt-4(o|-turbo)?"), 2, "gpt-4-class"),
    (re.compile(r"^google/gemini-[234]\.?\d*-flash"), 2, "gemini-flash"),
    (re.compile(r"^meta-llama/llama-[34](\.\d+)?-(70|90|400|405)"), 2, "llama large"),
    (re.compile(r"^qwen/qwen3-coder(-plus|-flash)?$"), 2, "qwen3-coder"),
    (re.compile(r"^qwen/qwen3\.\d+-plus"), 2, "qwen3-plus"),
    (re.compile(r"^mistralai/mistral-(large|medium)"), 2, "mistral-large/med"),
    (re.compile(r"^minimax/minimax-m[23](\.\d+)?$"), 2, "minimax-m2/m3"),
    # T2 default for ~latest aliases (always redirect to most-recent in family).
    (re.compile(r"^~[a-z-]+/.*-latest$"), 2, "~latest alias"),
    # T1 explicit — small / experimental / free-tier dominant.
    (re.compile(r":free$"), 1, ":free"),
    (re.compile(r"^kilo-auto/(small|free)"), 1, "small auto-router"),
]

# Cost thresholds — input USD/M.  Active models above these floors get
# AT LEAST the named tier (top providers don't undersell their best).
COST_TIER_FLOORS = [
    (10.0, 3, "≥$10/M input"),  # p95+ of catalog
    (3.0, 2, "≥$3/M input"),  # p90+
]

# Benchmark thresholds (any one hits → that tier floor).
# `aa_scraped` is the Artificial Analysis intelligence_index column we
# populate via `scrape_artificial_analysis.py` (AA's own leaderboard).
# Live distribution: top frontier sits at 56-60 (opus, fable),
# strong-mid at 40-50, mid-tier at 25-40. Thresholds picked from the
# observed distribution.
BENCH_TIER3 = {
    "arena_elo": 1500,
    "tbench": 78.0,
    "weighted_coding": 88.0,
    "design_arena_avg_elo": 1450,
    "aa_index": 75.0,  # from OpenRouter's `benchmarks.artificial_analysis` block (sparser)
    "aa_scraped": 50.0,  # from AA's own leaderboard scrape
    # Coding-specific (scrape_coding_benchmarks.py)
    "swe_bench": 60.0,  # % resolved on SWE-bench Verified (mini-SWE-agent v2)
    "aider_polyglot": 65.0,  # % pass_rate_2 on Aider Polyglot (225 problems × 6 langs)
    "design_arena_coding": 1280,  # mean ELO across coding-only design_arena categories
}
BENCH_TIER2 = {
    "arena_elo": 1400,
    "tbench": 60.0,
    "weighted_coding": 70.0,
    "design_arena_avg_elo": 1300,
    "aa_index": 55.0,
    "aa_scraped": 30.0,
    "swe_bench": 35.0,
    "aider_polyglot": 40.0,
    "design_arena_coding": 1220,
}


def _design_arena_avg(benchmarks: dict | None) -> float | None:
    """Mean ELO across all design_arena entries for this model."""
    if not benchmarks:
        return None
    rows = benchmarks.get("design_arena") or []
    elos = [r.get("elo") for r in rows if isinstance(r.get("elo"), (int, float))]
    return sum(elos) / len(elos) if elos else None


def _aa_index(benchmarks: dict | None) -> float | None:
    """Pull Artificial Analysis quality index when present."""
    if not benchmarks:
        return None
    aa = benchmarks.get("artificial_analysis")
    if isinstance(aa, dict):
        for k in ("quality_index", "intelligence_index", "intelligence", "index"):
            v = aa.get(k)
            if isinstance(v, (int, float)):
                return float(v)
    elif isinstance(aa, list) and aa:
        v = aa[0].get("intelligence_index") or aa[0].get("quality_index")
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _family_tier(model_id: str) -> tuple[int, str] | None:
    for rx, tier, label in FAMILY_TIERS:
        if rx.match(model_id):
            return tier, label
    return None


def derive_v2(row: dict, or_record: dict | None = None) -> tuple[int, list[str]]:
    """Derive quality_tier from all available signals. Returns
    (tier, evidence_list)."""
    tier = 1
    evidence: list[str] = []

    def bump(new_tier: int, why: str) -> None:
        nonlocal tier
        if new_tier > tier:
            tier = new_tier
        evidence.append(why)

    # ---- benchmark hits ----
    arena = row.get("arena_elo") or 0
    tbench = row.get("tbench_accuracy") or 0
    wcode = row.get("weighted_coding") or 0
    aa_scraped = row.get("aa_intelligence_index") or 0
    swe = max(
        row.get("swe_bench_verified_pct") or 0,
        row.get("swe_bench_multilingual_pct") or 0,
    )
    aider = row.get("aider_polyglot_pct") or 0
    da_code = row.get("design_arena_coding_elo") or 0
    da_avg = _design_arena_avg(or_record.get("benchmarks") if or_record else None) or 0
    aa = _aa_index(or_record.get("benchmarks") if or_record else None) or 0

    for label, val, thr in [
        ("arena_elo", arena, BENCH_TIER3["arena_elo"]),
        ("tbench", tbench, BENCH_TIER3["tbench"]),
        ("weighted_coding", wcode, BENCH_TIER3["weighted_coding"]),
        ("design_arena_avg", da_avg, BENCH_TIER3["design_arena_avg_elo"]),
        ("aa_index", aa, BENCH_TIER3["aa_index"]),
        ("aa_scraped", aa_scraped, BENCH_TIER3["aa_scraped"]),
        ("swe_bench", swe, BENCH_TIER3["swe_bench"]),
        ("aider_polyglot", aider, BENCH_TIER3["aider_polyglot"]),
        ("design_arena_coding", da_code, BENCH_TIER3["design_arena_coding"]),
    ]:
        if val >= thr:
            bump(3, f"{label}≥{thr}({val:.1f})")
            break
    if tier < 3:
        for label, val, thr in [
            ("arena_elo", arena, BENCH_TIER2["arena_elo"]),
            ("tbench", tbench, BENCH_TIER2["tbench"]),
            ("weighted_coding", wcode, BENCH_TIER2["weighted_coding"]),
            ("design_arena_avg", da_avg, BENCH_TIER2["design_arena_avg_elo"]),
            ("aa_index", aa, BENCH_TIER2["aa_index"]),
            ("aa_scraped", aa_scraped, BENCH_TIER2["aa_scraped"]),
            ("swe_bench", swe, BENCH_TIER2["swe_bench"]),
            ("aider_polyglot", aider, BENCH_TIER2["aider_polyglot"]),
            ("design_arena_coding", da_code, BENCH_TIER2["design_arena_coding"]),
        ]:
            if val >= thr:
                bump(2, f"{label}≥{thr}({val:.1f})")
                break

    # ---- family pattern ----
    fam = _family_tier(row.get("id") or "")
    if fam:
        bump(fam[0], f"family:{fam[1]}")

    # ---- cost proxy ----
    cost = row.get("input_cost_per_m") or 0
    if cost > 0:
        for floor, t, why in COST_TIER_FLOORS:
            if cost >= floor:
                bump(t, why)
                break

    # ---- reasoning + context boosts (small) ----
    if or_record:
        reasoning = or_record.get("reasoning") or {}
        if reasoning.get("mandatory") and tier < 3:
            bump(2, "reasoning mandatory")
        ctx = or_record.get("context_length") or 0
        if ctx >= 1_000_000 and tier < 3:
            bump(2, "context≥1M")

    return tier, evidence


def run(db_path: Path = DB_PATH) -> dict:
    """Recompute quality_tier for every agents row."""
    or_by_id: dict[str, dict] = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text())
        or_by_id = {m["id"]: m for m in cache.get("data", [])}
        print(f"[derive_quality_v2] OpenRouter cache loaded: {len(or_by_id)} rows")
    else:
        print("[derive_quality_v2] WARN: OpenRouter cache missing; family + cost signals only")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM agents").fetchall()]
    tier_counts = {1: 0, 2: 0, 3: 0}
    diffs = []
    try:
        for r in rows:
            new_tier, evidence = derive_v2(r, or_by_id.get(r["id"]))
            old_tier = r.get("quality_tier")
            tier_counts[new_tier] += 1
            if old_tier != new_tier:
                diffs.append((r["id"], old_tier, new_tier, evidence[:3]))
            conn.execute(
                "UPDATE agents SET quality_tier = ? WHERE id = ?",
                (new_tier, r["id"]),
            )
        conn.commit()
    finally:
        conn.close()

    print(
        f"[derive_quality_v2] tier distribution: "
        f"T1={tier_counts[1]} T2={tier_counts[2]} T3={tier_counts[3]}"
    )
    print(f"[derive_quality_v2] {len(diffs)} rows changed tier")
    for mid, old, new, ev in diffs[:25]:
        arrow = "↑" if (new or 0) > (old or 0) else "↓"
        print(f"  {arrow} {mid:<45} T{old}→T{new}  via {', '.join(ev[:2])}")
    return {"tier_counts": tier_counts, "changed": len(diffs)}


if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} does not exist", file=sys.stderr)
        sys.exit(1)
    run()
