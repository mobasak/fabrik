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
    verified code score    : 0.45   max(SWE-bench, Aider-polyglot) — "best verified
                                    code-understanding evidence". Additive weighting
                                    of the two would give models with both benchmarks
                                    filled a "coverage completeness" bonus that isn't
                                    about capability (v3.2 outranking m2.5 despite
                                    m2.5's higher SWE was the tell).
    AA intelligence index  : 0.20   (normalized against ceiling 60)
    Arena ELO              : 0.15   (normalized (elo-1350)/200, capped at 1.0)
    speed (db tps)         : 0.10   (normalized log)
    cost-inverse           : 0.10   (cheaper = higher score)

Doc-vs-code review grade is derived from context size + verified scores +
Arena/AA — captures how well a model can compare docs against implementation
across a whole service.
"""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import sys
import tempfile
import zlib
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

# Provider-pin overrides — OR's `provider.only` list is order-sensitive
# (first-listed = most preferred). Do NOT re-sort at render time.
PROVIDER_PINS: dict[str, list[str]] = {
    "minimax/minimax-m3": [
        "Minimax",
        "Novita",
        "Parasail",
        "Together",
    ],  # exclude DeepInfra (broken stream)
}

# Extra body params callers should send. Dict form (not pre-formatted JSON
# strings) so json.dumps handles quoting + merging safely — earlier
# string-concat approach corrupted JSON when a hint + pin overlapped.
BODY_HINTS: dict[str, dict] = {
    "minimax/minimax-m2.5": {"reasoning": {"exclude": True}, "max_tokens": 30000},
    "deepseek/deepseek-v3.2": {"reasoning": {"exclude": True}},
    "z-ai/glm-5": {"max_tokens": 20000},
}


def _grade_doc_review(ctx_k: float, swe: float, aider: float, aa_idx: float, arena: float) -> str:
    """Return A+/A/B+/B/B-/C+/C for doc↔code review capability.

    Weight: context size (can hold docs+code together), verified code
    understanding (SWE or Aider — whichever is available), general
    intelligence (AA/Arena). Ladder is monotonic: a strictly-stronger
    signal must never grade WORSE than a weaker one at the same ctx bucket.
    """
    verified = max(swe or 0, aider or 0)
    huge_ctx = ctx_k >= 800
    mid_ctx = 200 <= ctx_k < 800
    small_ctx = ctx_k < 200
    top_intel = (aa_idx or 0) >= 45 or (arena or 0) >= 1480
    good_intel = (aa_idx or 0) >= 40 or (arena or 0) >= 1450
    mid_intel = (aa_idx or 0) >= 30 or (arena or 0) >= 1400
    if huge_ctx and top_intel:
        return "A+"
    if huge_ctx and good_intel:
        return "A"
    if huge_ctx and verified >= 70:
        return "A"  # huge ctx + verified code-understanding beats "mid intel"
    if huge_ctx and mid_intel:
        return "B+"
    if huge_ctx:
        return "B"  # huge ctx w/o intel — still useful for reads
    if mid_ctx and verified >= 70:
        return "B+"
    if mid_ctx and good_intel:
        return "B"
    if mid_ctx and mid_intel:
        return "B-"
    if mid_ctx:
        return "C+"
    if small_ctx and verified >= 70:
        return "B"
    if small_ctx and good_intel:
        return "B-"
    if small_ctx and mid_intel:
        return "C+"
    return "C"


def _compose_score(row: dict) -> float:
    """Composite ranking score. Higher = better coding-subagent fit.

    Every component is normalized to [0, 1] before its weight is applied —
    a component that could exceed 1.0 (e.g. Arena) would silently overweight
    that signal past its stated share.
    """
    swe = row.get("swe") or 0
    aider = row.get("aider") or 0
    verified = max(swe, aider)  # "best verified code-understanding evidence"
    aa = row.get("aa_idx") or 0
    arena = row.get("arena") or 0
    tps = row.get("db_tps") or 0
    # `.get(k) or D` collapses a legitimate 0.0 price to D (Python falsy). Use
    # an explicit-None check so a free-tier / discounted row doesn't get
    # misclassified as expensive.
    cost_in = row.get("in_M") if row.get("in_M") is not None else 999
    cost_out = row.get("out_M") if row.get("out_M") is not None else 999
    # Typical bench task ≈ 3k output + 500 input tokens
    task_cost = (cost_in * 0.5 + cost_out * 3) / 1000  # dollars
    return (
        min(verified / 100, 1.0) * 0.45
        + min(aa / 60, 1.0) * 0.20
        + min(max((arena - 1350) / 200, 0), 1.0) * 0.15
        + min(math.log1p(tps) / math.log(200), 1.0) * 0.10
        # `1 - task_cost/0.03` maxes at 1.0 when task_cost=0 and goes negative
        # otherwise — but a negative cost from a data-entry anomaly would push
        # the term > 1.0; wrap in min for defense-in-depth so composite ≤ 1.0.
        + min(max(1 - task_cost / 0.03, 0), 1.0) * 0.10
    )


_FMT_PRECISION_RE = re.compile(r"\.(\d+)f")


def _fmt_or_dash(v, fmt: str = "{}") -> str:
    if v is None or v == 0:
        return "—"
    # A price like 1.4e-07 rounds to "0.000" under "{:.3f}", visually
    # indistinguishable from the em-dash convention. Show "<X" for a
    # non-zero-but-below-precision value so :discounted / promo rows
    # aren't mistaken for actually-free ones. Parse the precision directly
    # from the format string (works for suffixed formats like `{:.0f}k` too,
    # where `float()`-based sniffing on the formatted string would crash).
    m = _FMT_PRECISION_RE.search(fmt)
    if m:
        precision = int(m.group(1))
        threshold = 10**-precision if precision else 1
        if 0 < abs(v) < threshold:
            suffix = fmt.rsplit("}", 1)[-1] if "}" in fmt else ""
            return f"<{threshold:.{precision}f}{suffix}"
    return fmt.format(v)


def _fmt_body_hint(mid: str) -> str:
    """Return the extra request-body params for `mid` as a JSON string.

    Builds a dict from the hand-maintained BODY_HINTS + PROVIDER_PINS entries
    and serializes via json.dumps — avoids the earlier string-concat approach
    that corrupted JSON when a hint didn't end in '}' or when a provider name
    contained a quote character (repr → .replace bypass).
    """
    body: dict = dict(BODY_HINTS.get(mid) or {})
    pin = PROVIDER_PINS.get(mid)
    if pin:
        # `provider.only` order matters to OR routing — keep the list as
        # declared, do NOT sort.
        body["provider"] = {"only": list(pin)}
    if not body:
        return "—"
    return json.dumps(body, separators=(",", ":"))


def _rows_from_db(db_path: Path | None = None) -> list[dict]:
    with sqlite3.connect(db_path if db_path is not None else DB_PATH) as conn:
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
            d.get("ctx_k") or 0,
            d.get("swe") or 0,
            d.get("aider") or 0,
            d.get("aa_idx") or 0,
            d.get("arena") or 0,
        )
        out.append(d)
    out.sort(key=lambda x: (-x["score"], x["id"]))
    return out


_MD_ID_SAFE = re.compile(r"^[A-Za-z0-9./_:\-]+$")


def _safe_md_id(mid: str) -> str:
    """Reject any model id that would break markdown table structure.

    OR model ids come from a restricted charset (`vendor/model-name` with
    letters/digits/dots/hyphens/underscores/colons). If a future upstream ever
    surfaces an id containing `|`, backticks, or a newline, the emitted
    markdown table would break — return a fenced-safe placeholder instead.
    """
    if _MD_ID_SAFE.match(mid) and "\n" not in mid:
        return mid
    # Use zlib.crc32 (deterministic across processes) rather than hash() which
    # is randomized by PYTHONHASHSEED — otherwise the same bad id would produce
    # a different placeholder every nightly run, creating spurious diff churn.
    return f"INVALID_ID_{zlib.crc32(mid.encode()) % 10_000}"


def _render(rows: list[dict]) -> str:
    today = datetime.now(UTC).date().isoformat()
    lines = [
        "# Coding subagent selection",
        "",
        f"**Generated:** {today} · **Source:** `scripts/kilo-benchmarks/kilo_agents.db` · **Generator:** `scripts/kilo-benchmarks/rank_coding_subagents.py`",
        "",
        "Ranked candidates for coding-subagent dispatch across the GLM (z-ai), Kimi (moonshotai), Minimax, and DeepSeek families. Regenerated daily by `scripts/kilo-benchmarks/daily_refresh.sh` after pricing and microbench data refreshes.",
        "",
        "> **Score composition**: 45% best-verified code score (max of SWE-bench-Verified and Aider-Polyglot — whichever is available) · 20% AA intelligence index · 15% Arena ELO · 10% output tok/s · 10% cost-inverse. Every component normalized to [0,1] before its weight is applied. Higher = better fit.",
        "",
        "> **Doc↔Code grade**: composite of context size (fits code + docs together), verified code-understanding score, and general intelligence — measures ability to spot drift between documentation and implementation.",
        "",
        "## Ranked table",
        "",
        # Level-3 header `### code` makes this file directly consumable by the
        # subagents module's `load_task_ranking()` reader (at select.py) — it
        # parses `### <task_type>` headers and reads the following table as
        # `(rank, model, ..., n)`. The reader looks at cells[0] (rank), cells[1]
        # (model), and cells[-1] (n; here it's Score, which isn't decimal → n=0,
        # harmless when min_n=0). This lets projects EITHER set
        #   SUBAGENT_SELECTION_DOC=docs/reference/kilo/CODING_SUBAGENT_SELECTION.md
        # directly (for benchmark-only rankings, no fleet data required), OR
        # let `fabrik apply` inject the default `TASK_SUBAGENT_SELECTION.md`
        # path — the hub-side aggregator (`rank_task_subagents.py`) reads
        # THIS file and BLENDS its `### code` section into the emitted TASK
        # doc when the fleet has no empirical code data. A prior wiring tried
        # comma-separated `TASK,CODING`; that broke because `select.py` reads
        # SUBAGENT_SELECTION_DOC as one literal filename. See workflow doc's
        # "Two ranking docs" section.
        "### code",
        "",
        "| # | Model | OR | OR_prov | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | Score |",
        "|---:|---|:-:|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---:|",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(
            "| {i} | `{mid}` | {or_ok} | {prov} | {tps} | {inp} | {out} | {swe} | {aider} | {aa} | {arena} | {ctx} | **{grade}** | {score} |".format(
                i=i,
                mid=_safe_md_id(r["id"]),
                or_ok="✅" if r.get("or_ok") else "—",
                # `_safe_md_id` on the em-dash fallback would trip the regex
                # and emit `INVALID_ID_<hash>`; check-then-sanitize instead.
                prov=_safe_md_id(r["or_prov"]) if r.get("or_prov") else "—",
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
    lines.extend(
        [
            "",
            "## API call recipes (OpenRouter)",
            "",
            "Base endpoint: `POST https://openrouter.ai/api/v1/chat/completions` with `Authorization: Bearer $OPENROUTER_API_KEY`.",
            "",
            "| Model | Extra body params |",
            "|---|---|",
        ]
    )
    for r in rows:
        hint = _fmt_body_hint(r["id"])
        if hint == "—":
            continue
        lines.append(f"| `{_safe_md_id(r['id'])}` | `{hint}` |")
    lines.extend(
        [
            "",
            "## Excluded from the pool",
            "",
            "| Model | Reason |",
            "|---|---|",
        ]
    )
    for mid in sorted(EXCLUDE_MODELS):
        lines.append(
            f"| `{_safe_md_id(mid)}` | Reasoning-mandatory model that returns 0 output tokens when reasoning is excluded — not a code-producing model. |"
        )
    lines.extend(
        [
            "",
            "## How this file stays fresh",
            "",
            "1. Nightly at 06:00 UTC, `daily_refresh.sh` runs the pricing + microbench pipeline that populates `kilo_agents.db`.",
            "2. Immediately after `derive_cheapest_gateway.py`, this script queries the DB and regenerates the table.",
            "3. `EXCLUDE_MODELS`, `PROVIDER_PINS`, and `BODY_HINTS` in the generator are hand-maintained — when a new provider bug or reasoning-only model is discovered, add it there and re-run.",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    """Write via temp file in the same dir + os.replace so a concurrent
    reader (or a crash mid-write) never sees a truncated/partial file.

    `tempfile.mkstemp` creates the temp file at mode 0600 regardless of
    umask, and `os.replace` preserves that mode onto the final path — which
    would silently strip group/world read from a previously-0644 doc. Restore
    umask-respecting behavior explicitly (matches plain `open(path,'w')`).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        current_umask = os.umask(0)
        os.umask(current_umask)
        os.chmod(tmp_name, 0o666 & ~current_umask)
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    rows = _rows_from_db()
    if not rows:
        print("[rank_coding_subagents] no candidates in DB", file=sys.stderr)
        return 1
    _atomic_write(OUT_PATH, _render(rows))
    print(f"[rank_coding_subagents] wrote {OUT_PATH} · {len(rows)} models ranked")
    return 0


# ---------------------------------------------------------------------------
# Public API — consumers (e.g. export_models_browser.py) call these to overlay
# coding-subagent ranking data onto other views. Never fork the constants below.
# ---------------------------------------------------------------------------


def rank_all(db_path: Path | None = None) -> list[dict]:
    """Public entrypoint: return the ranked candidates.

    Same shape as `_rows_from_db` (adds `score` + `doc_grade` per row), but
    accepts a caller-supplied db_path so `export_models_browser` can invoke
    it directly instead of shelling out to the CLI. Thread-safe: the db_path
    is passed straight through to `_rows_from_db` — no global state mutation.
    """
    return _rows_from_db(Path(db_path) if db_path is not None else None)


def grade_doc_review(ctx_k: float, swe: float, aider: float, aa_idx: float, arena: float) -> str:
    """Public alias — see `_grade_doc_review`."""
    return _grade_doc_review(ctx_k, swe, aider, aa_idx, arena)


def fmt_body_hint(mid: str) -> str:
    """Public alias — see `_fmt_body_hint`."""
    return _fmt_body_hint(mid)


CODING_EXCLUDE_MODELS = EXCLUDE_MODELS
CODING_PROVIDER_PINS = PROVIDER_PINS
CODING_BODY_HINTS = BODY_HINTS


if __name__ == "__main__":
    sys.exit(main())
