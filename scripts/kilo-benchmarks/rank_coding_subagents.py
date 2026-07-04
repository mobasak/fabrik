#!/usr/bin/env python3
# AFTER-EDIT: docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
"""Rank coding-subagent candidates from `kilo_agents.db` and emit a markdown table.

Consumers: [docs/reference/kilo/CODING_SUBAGENT_SELECTION.md](../../docs/reference/kilo/CODING_SUBAGENT_SELECTION.md)
Cron: run daily from `daily_refresh.sh` after `derive_cheapest_gateway.py` so the
      rankings reflect fresh pricing + microbench speeds.

Scope (families in the pool):
    z-ai/glm-*, moonshotai/kimi-*, minimax/minimax-*, deepseek/*

Filters:
    - status='active' AND service_type='llm'
    - quality_tier >= 1
    - Not in EXCLUDE_MODELS (models that returned 0 output on our probes,
      e.g. reasoning-only models where `reasoning.exclude:true` empties the
      response body)

Signals used, weighted:
    verified SWE-bench     : 0.30
    verified Aider         : 0.15
    AA intelligence index  : 0.20   (normalized 0-100 vs 60 ceiling)
    Arena ELO              : 0.15   (normalized (elo-1350)/200)
    speed (db tps)         : 0.10   (normalized log)
    cost-inverse           : 0.10   (cheaper = higher score)

Doc-vs-code review grade is derived from context size + verified scores +
Arena/AA — captures how well a model can compare docs against implementation
across a whole service.
"""

from __future__ import annotations

import math
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
OUT_PATH = SCRIPT_DIR.parent.parent / "docs" / "reference" / "kilo" / "CODING_SUBAGENT_SELECTION.md"

FAMILIES = ("z-ai/glm-", "moonshotai/kimi-", "minimax/minimax-", "deepseek/")

# Models filtered out of the ranked table.
# Add here only when a model is verifiably unusable in a code-subagent role
# (e.g. reasoning-mandatory + returns 0 output when reasoning is excluded).
EXCLUDE_MODELS = frozenset(
    {
        "moonshotai/kimi-k2-thinking",  # returns 0 output tokens when reasoning.exclude:true
    }
)

# Provider-pin overrides — for cases where OR's default sub-provider has a
# known broken streaming route.
PROVIDER_PINS = {
    "minimax/minimax-m3": ["Minimax", "Novita", "Parasail", "Together"],  # exclude DeepInfra (broken stream)
}

# Extra body params callers should send.
BODY_HINTS = {
    "minimax/minimax-m2.5": '{"reasoning":{"exclude":true},"max_tokens":30000}',  # mandatory reasoning
    "deepseek/deepseek-v3.2": '{"reasoning":{"exclude":true}}',
    "z-ai/glm-5": '{"max_tokens":20000}',
}


def _grade_doc_review(ctx_k: float, swe: float, aider: float, aa_idx: float, arena: float) -> str:
    """Return A+/A/B+/B/B-/C+/C for doc↔code review capability.

    Weight: context size (can hold docs+code together), verified code
    understanding (SWE/Aider), general intelligence (AA/Arena).
    """
    verified = max(swe or 0, aider or 0)
    huge_ctx = ctx_k >= 800
    mid_ctx = 200 <= ctx_k < 800
    small_ctx = ctx_k < 200
    top_intel = (aa_idx or 0) >= 45 or (arena or 0) >= 1480
    good_intel = (aa_idx or 0) >= 40 or (arena or 0) >= 1450
    if huge_ctx and top_intel:
        return "A+"
    if huge_ctx and good_intel:
        return "A"
    if mid_ctx and verified >= 70:
        return "B+"
    if mid_ctx and good_intel:
        return "B"
    if mid_ctx:
        return "B-"
    if small_ctx and verified >= 70:
        return "B"
    if small_ctx and good_intel:
        return "B-"
    if small_ctx and (arena or 0) >= 1400:
        return "C+"
    return "C"


def _compose_score(row: dict) -> float:
    """Composite ranking score. Higher = better coding-subagent fit."""
    swe = row.get("swe") or 0
    aider = row.get("aider") or 0
    aa = row.get("aa_idx") or 0
    arena = row.get("arena") or 0
    tps = row.get("db_tps") or 0
    cost_in = row.get("in_M") or 999
    cost_out = row.get("out_M") or 999
    # Typical bench task ≈ 3k output + 500 input tokens
    task_cost = (cost_in * 0.5 + cost_out * 3) / 1000  # dollars
    return (
        (swe / 100) * 0.30
        + (aider / 100) * 0.15
        + min(aa / 60, 1.0) * 0.20
        + max((arena - 1350) / 200, 0) * 0.15
        + min(math.log1p(tps) / math.log(200), 1.0) * 0.10
        + max(1 - task_cost / 0.03, 0) * 0.10  # $0.03 = expensive cutoff
    )


def _fmt_or_dash(v, fmt: str = "{}") -> str:
    if v is None or v == 0:
        return "—"
    return fmt.format(v)


def _fmt_body_hint(mid: str) -> str:
    hint = BODY_HINTS.get(mid, "")
    pin = PROVIDER_PINS.get(mid)
    if pin:
        pin_str = f'{{"provider":{{"only":{sorted(pin)!r}}}}}'.replace("'", '"')
        return (pin_str if not hint else hint[:-1] + "," + pin_str[1:])
    return hint or "—"


def _rows_from_db() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        placeholder = " OR ".join(["id LIKE ? || '%'"] * len(FAMILIES))
        rows = conn.execute(
            f"""
            SELECT id,
                   input_cost_per_m AS in_M,
                   output_cost_per_m AS out_M,
                   output_tokens_per_sec AS db_tps,
                   swe_bench_verified_pct AS swe,
                   aider_polyglot_pct AS aider,
                   aa_intelligence_index AS aa_idx,
                   arena_elo AS arena,
                   context_window_k AS ctx_k,
                   quality_tier AS tier,
                   has_reasoning AS reasoning,
                   via_openrouter AS or_ok,
                   cheapest_provider AS or_prov
            FROM agents
            WHERE status='active' AND service_type='llm'
              AND ({placeholder})
              AND quality_tier IS NOT NULL AND quality_tier >= 1
            """,
            FAMILIES,
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d["id"] in EXCLUDE_MODELS:
            continue
        d["score"] = _compose_score(d)
        d["doc_grade"] = _grade_doc_review(
            d.get("ctx_k") or 0, d.get("swe") or 0, d.get("aider") or 0,
            d.get("aa_idx") or 0, d.get("arena") or 0,
        )
        out.append(d)
    out.sort(key=lambda x: (-x["score"], x["id"]))
    return out


def _render(rows: list[dict]) -> str:
    today = datetime.now(UTC).date().isoformat()
    lines = [
        "# Coding subagent selection",
        "",
        f"**Generated:** {today} · **Source:** `scripts/kilo-benchmarks/kilo_agents.db` · **Generator:** `scripts/kilo-benchmarks/rank_coding_subagents.py`",
        "",
        "Ranked candidates for coding-subagent dispatch across the GLM (z-ai), Kimi (moonshotai), Minimax, and DeepSeek families. Regenerated daily by `scripts/kilo-benchmarks/daily_refresh.sh` after pricing and microbench data refreshes.",
        "",
        "> **Score composition**: 30% verified SWE-bench · 15% verified Aider · 20% AA intelligence index · 15% Arena ELO · 10% output tok/s · 10% cost-inverse. Higher = better fit.",
        "",
        "> **Doc↔Code grade**: composite of context size (fits code + docs together), verified code-understanding score, and general intelligence — measures ability to spot drift between documentation and implementation.",
        "",
        "## Ranked table",
        "",
        "| # | Model | OR | OR_prov | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | Score |",
        "|---:|---|:-:|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---:|",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(
            "| {i} | `{mid}` | {or_ok} | {prov} | {tps} | {inp} | {out} | {swe} | {aider} | {aa} | {arena} | {ctx} | **{grade}** | {score} |".format(
                i=i, mid=r["id"],
                or_ok="✅" if r.get("or_ok") else "—",
                prov=r.get("or_prov") or "—",
                tps=_fmt_or_dash(r.get("db_tps"), "{:.0f}"),
                inp=_fmt_or_dash(r.get("in_M"), "{:.3f}"),
                out=_fmt_or_dash(r.get("out_M"), "{:.3f}"),
                swe=_fmt_or_dash(r.get("swe"), "{:.1f}"),
                aider=_fmt_or_dash(r.get("aider"), "{:.1f}"),
                aa=_fmt_or_dash(r.get("aa_idx"), "{:.0f}"),
                arena=_fmt_or_dash(r.get("arena"), "{:.0f}"),
                ctx=_fmt_or_dash(r.get("ctx_k"), "{:.0f}k"),
                grade=r["doc_grade"],
                score=f"{r['score']:.3f}",
            )
        )
    lines.extend([
        "",
        "## API call recipes (OpenRouter)",
        "",
        "Base endpoint: `POST https://openrouter.ai/api/v1/chat/completions` with `Authorization: Bearer $OPENROUTER_API_KEY`.",
        "",
        "| Model | Extra body params |",
        "|---|---|",
    ])
    for r in rows:
        hint = _fmt_body_hint(r["id"])
        if hint == "—":
            continue
        lines.append(f"| `{r['id']}` | `{hint}` |")
    lines.extend([
        "",
        "## Excluded from the pool",
        "",
        "| Model | Reason |",
        "|---|---|",
    ])
    for mid in sorted(EXCLUDE_MODELS):
        lines.append(f"| `{mid}` | Reasoning-mandatory model that returns 0 output tokens when reasoning is excluded — not a code-producing model. |")
    lines.extend([
        "",
        "## How this file stays fresh",
        "",
        "1. Nightly at 06:00 UTC, `daily_refresh.sh` runs the pricing + microbench pipeline that populates `kilo_agents.db`.",
        "2. Immediately after `derive_cheapest_gateway.py`, this script queries the DB and regenerates the table.",
        "3. `EXCLUDE_MODELS`, `PROVIDER_PINS`, and `BODY_HINTS` in the generator are hand-maintained — when a new provider bug or reasoning-only model is discovered, add it there and re-run.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    rows = _rows_from_db()
    if not rows:
        print("[rank_coding_subagents] no candidates in DB", file=sys.stderr)
        return 1
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(_render(rows))
    print(f"[rank_coding_subagents] wrote {OUT_PATH} · {len(rows)} models ranked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
