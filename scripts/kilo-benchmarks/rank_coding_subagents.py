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

FAMILIES = (
    "z-ai/glm-",
    "moonshotai/kimi-",
    "minimax/minimax-",
    "deepseek/",
    # 2026-07-09 — admits the qwen3-coder line (cheap OSS coders) per fabrik-lib
    # request. TIGHT prefix (trailing `-`) so it matches -next/-flash/
    # -30b-a3b-instruct/-plus but NOT `qwen/qwen3-coder` (base $1.80, above cap)
    # and NOT `qwen/qwen3.7-max`, `qwen/qwen3-vl-*`, etc. The Auto/On-request
    # price split at :86 then tiers automatically (-next $0.80, -flash $0.975,
    # -30b-a3b-instruct $0.27 → Auto; -plus $3.25 → On-request).
    "qwen/qwen3-coder-",
    # 2026-07-10 — admits ByteDance Seed coding models per plan-2-coding-microbench-runner.
    # TIGHT prefix (trailing `-`) so it matches -1.6-flash/-2.0-mini/-1.6/-2.0-lite
    # but NOT bytedance-seed/dola-* (image), bytedance-seed/seedream-* (image), or
    # bytedance/ui-tars-* (GUI-agent, deferred to a separate follow-up plan).
    # Price tiering (per rank_coding_subagents.py:98 AUTO_OUTPUT_PRICE_CEILING = 1.5):
    # -1.6-flash $0.30 / -2.0-mini $0.40 → Auto; -1.6 $2.00 / -2.0-lite $2.00 → On-request.
    "bytedance-seed/seed-",
)

# ─────────────────────────────────────────────────────────────────────────────
# Auto vs On-request tier split — defense-in-depth (see 62-using-subagents.md § Approved pool models)
# ─────────────────────────────────────────────────────────────────────────────
# This filter is BELT-AND-SUSPENDERS — as of the fabrik-lib re-vendor `fa33a14`
# (`_MAX_POOL_PRICE_PER_MTOK = 1.5` at `libs/subagents/subagents/select.py:67` +
# `allow_above_cap` kwarg), the canonical `pick_models` is now the **SOLE
# gatekeeper**: it ALWAYS enforces the ≤$1.5/Mtok cap on the Auto tier (a caller
# can only make it tighter via `max_cost_per_mtok`, never looser; unpriced
# models price to +inf and are dropped fail-closed). A pricier model can never
# reach the default pool even if this doc surfaces one.
# → Three enforcement points now agree, in ascending trust order:
#   (1) this filter at aggregation time — the earliest guard; also documents
#       operator intent + gives humans a readable tiered doc.
#   (2) the caller passing `max_cost_per_mtok` — optional per-call tightener.
#   (3) `pick_models`' unconditional `_MAX_POOL_PRICE_PER_MTOK` — the SOLE
#       gatekeeper, always on, fail-closed.
# Keeping this filter is cheap belt-and-suspenders: even if a future re-vendor
# regresses the module cap, or a caller uses `allow_above_cap=True`, only rows
# we already marked Auto surface under `### code`. Also, humans reading the doc
# directly need to see the tiered structure — that's this filter's other job.
#
# Rule shape (per 62-using-subagents.md § Approved pool models — BINDING):
#   - Auto (output ≤ $1.5/Mtok): `pick_models` selects freely, no operator approval.
#   - On-request (output > $1.5): fully benchmarked + priced, but NEVER
#     auto-selected — the operator names it explicitly (`allow_above_cap=True`)
#     per turn.
#   - Unknown / NULL output price is treated as On-request (fail-safe: never
#     auto-select an unpriced row — the operator might get charged $10/Mtok).
# The tier is a filter/flag, NOT a cut: a pricier model that benchmarks
# brilliantly stays in On-request; a new cheaper model that clears $1.5
# auto-joins Auto on next daily refresh.
AUTO_OUTPUT_PRICE_CEILING = 1.5


def _is_auto_tier(row: dict) -> bool:
    """A row is Auto-selectable iff its OR output price is known AND ≤ $1.5/Mtok.

    Unknown price → On-request (conservative: never auto-select an unpriced row).
    """
    out = row.get("out_M")
    if out is None:
        return False
    try:
        return float(out) <= AUTO_OUTPUT_PRICE_CEILING
    except (TypeError, ValueError):
        return False


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


def _grade_doc_review(
    ctx_k: float,
    swe: float,
    aider: float,
    aa_idx: float,
    arena: float,
    coding_score: float = 0,
) -> str:
    """Return A+/A/B+/B/B-/C+/C for doc↔code review capability.

    Weight: context size (can hold docs+code together), verified code
    understanding (SWE or Aider — whichever is available; falls back to
    our own coding_score when neither is populated), general intelligence
    (AA/Arena). Ladder is monotonic: a strictly-stronger signal must never
    grade WORSE than a weaker one at the same ctx bucket.

    coding_score fallback: HE+/MBPP+ pass_at_1 saturates ~10-15pp higher
    than SWE-bench for the same model class, so discount to ~SWE scale
    (× 0.7) — used ONLY when both swe and aider are 0/absent.
    """
    verified = max(swe or 0, aider or 0)
    if verified == 0 and coding_score:
        verified = coding_score * 0.7
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
    coding_s = row.get("coding_s") or 0
    verified = max(swe, aider)  # "best verified code-understanding evidence"
    # Fallback: our own live HumanEval+/MBPP+ pass_at_1 when neither
    # external benchmark is populated. Discount × 0.7 to align scales
    # (HE+/MBPP+ tops out ~10-15pp above SWE-bench for the same class).
    if verified == 0 and coding_s:
        verified = coding_s * 0.7
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
                   coding_score AS coding_s,
                   humaneval_score AS he_score,
                   aa_intelligence_index AS aa_idx,
                   arena_elo AS arena,
                   context_window_k AS ctx_k,
                   quality_tier AS tier,
                   has_reasoning AS reasoning,
                   via_openrouter AS or_ok,
                   cheapest_provider AS or_prov
            FROM agents
            WHERE status='active' AND service_type='llm'
              AND reachable_with_existing_keys=1
              AND ({placeholder})
              AND quality_tier IS NOT NULL AND quality_tier >= 1
            """,
            FAMILIES,
        ).fetchall()
    # Measured grades keyed by model id. DISPLAY ONLY (the sort stays `_compose_score` — D4): a
    # measured CODING grade (microbench_coding_direct -> model_coding_metrics) is the real coding
    # signal, so it wins for the Doc↔Code column; else the measured REVIEW grade (code-understanding
    # proxy); else the heuristic. `coding_pass_at_1` feeds the new pass@1 % column.
    try:
        from build_task_baselines import load_coding_metrics, load_review_metrics

        _db = db_path if db_path is not None else DB_PATH
        measured_review = load_review_metrics(_db)
        measured_coding = load_coding_metrics(_db)
    except Exception:  # never let a missing/locked benchmark table block the daily coding doc
        measured_review, measured_coding = {}, {}
    out = []
    for r in rows:
        d = dict(r)
        if d["id"] in EXCLUDE_MODELS:
            continue
        d["score"] = _compose_score(d)
        c = measured_coding.get(d["id"])
        m = measured_review.get(d["id"])
        d["coding_pass_at_1"] = c.get("pass_at_1") if c else None
        if c and c.get("grade"):
            # measured LiveCodeBench pass@1 -> the real coding grade (this IS a coding-selection doc)
            d["doc_grade"] = c["grade"]
            d["doc_grade_measured"] = True
        elif m and m.get("grade"):
            # fallback: measured review grade (ground-truth code-understanding, not inferred)
            d["doc_grade"] = m["grade"]
            d["doc_grade_measured"] = True
        else:
            d["doc_grade"] = _grade_doc_review(
                d.get("ctx_k") or 0,
                d.get("swe") or 0,
                d.get("aider") or 0,
                d.get("aa_idx") or 0,
                d.get("arena") or 0,
                d.get("coding_s") or 0,
            )
            d["doc_grade_measured"] = False
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
    # NOTE (2026-07-09 canonical alignment): the earlier `<!-- reachable-set: ... -->`
    # emit + `pick_models(require_reachable=True)` fork was reverted after
    # fabrik-lib's source-of-truth AI ruled the mechanism wrong-layer. The
    # canonical seam is `pick_models(task_type, exclude=unreachable_ids)`; callers
    # in this project build `unreachable_ids` from `agents.reachable_with_existing_keys=0`
    # at dispatch time. See `docs/reference/kilo/AI_VENDOR_ACCESS.md` for the source.
    # The DB filter below (`AND reachable_with_existing_keys=1` in the SELECT that
    # produced `rows`) still applies — this ranked doc lists only reachable models.
    lines = [
        "# Coding subagent selection",
        "",
        f"**Generated:** {today} · **Source:** `scripts/kilo-benchmarks/kilo_agents.db` · **Generator:** `scripts/kilo-benchmarks/rank_coding_subagents.py`",
        "",
        "Ranked candidates for coding-subagent dispatch across the GLM (z-ai), Kimi (moonshotai), Minimax, and DeepSeek families. Regenerated daily by `scripts/kilo-benchmarks/daily_refresh.sh` after pricing and microbench data refreshes.",
        "",
        "> **Score composition**: 45% best-verified code score (max of SWE-bench-Verified and Aider-Polyglot; falls back to our own live HumanEval+/MBPP+ `coding_score` × 0.7 when neither external benchmark is populated) · 20% AA intelligence index · 15% Arena ELO · 10% output tok/s · 10% cost-inverse. Every component normalized to [0,1] before its weight is applied. Higher = better fit.",
        "",
        "> **Doc↔Code grade + pass@1**: coding capability. `†` = MEASURED — the measured **coding** grade from `scripts/kilo-benchmarks/microbench_coding_direct.py` (LiveCodeBench pass@1, shown in the `pass@1` column) wins when present; else the measured **review** grade from `microbench_review.py` (ground-truth planted-bug corpus — code-understanding proxy); unmarked = the heuristic composite of context size + verified code-understanding score + general intelligence. `pass@1` = LiveCodeBench coding accuracy (contamination-free); `—` until the coding bench has run on that model. (The row **sort** is the composite `Score`, not the grade — the grade/pass@1 are the coding signal; `pick_models(\"code\")` ranks on the measured `model_task_baseline` prior.)",
        "",
        '> **Column key** — `Reason` = native reasoning / thinking capability (may need `reasoning={"exclude":true}` in the request body for pure code — see API recipes). `Bench` = ✅ if `scripts/kilo-benchmarks/microbench_coding.py` has run our own live HumanEval+/MBPP+ pass_at_1 on this model (`humaneval_score` populated); `—` = external benchmarks only, our own live signal is not yet available. Un-benched candidates worth prioritizing are listed under **Candidates not yet benched by us** below.',
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
        # BINDING tier split (see .windsurf/rules/core/62-using-subagents.md § Approved pool models):
        # rows with OR output price ≤ $1.5/Mtok land under `### code`;
        # everything else under `### code-onrequest`. The `pick_models` reader
        # in the fabrik-lib subagents module (select.py:load_task_ranking)
        # resets `current` to None on ANY `###` header whose name is NOT a
        # known TaskKind — since `code-onrequest` is not in TASK_KINDS
        # (`spec`, `plan`, `code`, `review`, `docs`, `research`), its rows are
        # scoped out and pick_models NEVER sees them. Only the Auto table is
        # readable by the module. NULL out_M → On-request (fail-safe: never
        # auto-select an unpriced row).
        "### code",
        "",
        f"Auto tier — OpenRouter output ≤ ${AUTO_OUTPUT_PRICE_CEILING:.1f}/Mtok. `pick_models` auto-selects freely from this table (no operator approval required).",
        "",
        "| # | Model | OR | OR_prov | Reason | Bench | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | pass@1 | Score |",
        "|---:|---|:-:|---|:-:|:-:|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---:|---:|",
    ]

    def _fmt_row(i: int, r: dict) -> str:
        return (
            "| {i} | `{mid}` | {or_ok} | {prov} | {reason} | {bench} | {tps} | {inp} | {out} | {swe} | {aider} | {aa} | {arena} | {ctx} | **{grade}** | {passk} | {score} |"
        ).format(
            i=i,
            mid=_safe_md_id(r["id"]),
            or_ok="✅" if r.get("or_ok") else "—",
            # `_safe_md_id` on the em-dash fallback would trip the regex
            # and emit `INVALID_ID_<hash>`; check-then-sanitize instead.
            prov=_safe_md_id(r["or_prov"]) if r.get("or_prov") else "—",
            # Reason = model has native reasoning / thinking mode. Callers may
            # need `reasoning={"exclude": true}` to suppress it for pure code
            # output (see BODY_HINTS).
            reason="✅" if r.get("reasoning") else "—",
            # Bench = our own live HumanEval+/MBPP+ pass_at_1 pass ran on this
            # model (populated humaneval_score / coding_score). Distinct from
            # SWE/Aider (external benchmarks). "—" = not benched by us yet.
            bench="✅" if r.get("he_score") is not None else "—",
            tps=_fmt_or_dash(r.get("db_tps"), "{:.0f}"),
            inp=_fmt_or_dash(r.get("in_M"), "{:.3f}"),
            out=_fmt_or_dash(r.get("out_M"), "{:.3f}"),
            swe=_fmt_or_dash(r.get("swe"), "{:.1f}"),
            aider=_fmt_or_dash(r.get("aider"), "{:.1f}"),
            aa=_fmt_or_dash(r.get("aa_idx"), "{:.0f}"),
            arena=_fmt_or_dash(r.get("arena"), "{:.0f}"),
            ctx=_fmt_or_dash(r.get("ctx_k"), "{:.0f}k"),
            # `†` marks a grade MEASURED by microbench_review (ground-truth planted-bug corpus);
            # unmarked = the heuristic composite below.
            grade=r["doc_grade"] + ("†" if r.get("doc_grade_measured") else ""),
            # pass@1 % — measured LiveCodeBench coding accuracy (microbench_coding_direct); "—" until run
            passk=(f"{r['coding_pass_at_1'] * 100:.0f}%" if r.get("coding_pass_at_1") is not None else "—"),
            score=f"{r['score']:.3f}",
        )

    auto_rows = [r for r in rows if _is_auto_tier(r)]
    onreq_rows = [r for r in rows if not _is_auto_tier(r)]

    # Auto table
    for i, r in enumerate(auto_rows, 1):
        lines.append(_fmt_row(i, r))
    if not auto_rows:
        lines.append(
            "| — | _no Auto-tier candidates today (all rows over $1.5/Mtok output or unpriced)_ | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |"
        )

    lines.extend(
        [
            "",
            # Level-3 header with a name that is NOT a TaskKind — this makes
            # pick_models RESET current to None, so the On-request table's
            # rows are scoped out of the reader entirely (that's the whole
            # point of the tier split — see the BINDING comment above the
            # `### code` header).
            "### code-onrequest",
            "",
            f"On-request tier — OpenRouter output > ${AUTO_OUTPUT_PRICE_CEILING:.1f}/Mtok. Operator opt-in only: `pick_models` NEVER auto-promotes these. Selectable when the operator names one this turn and says why the Auto tier didn't suffice for this specific hard task. A pricier model that benchmarks brilliantly stays here until its OR output price drops ≤ ${AUTO_OUTPUT_PRICE_CEILING:.1f}/Mtok, at which point it auto-joins Auto on the next daily refresh.",
            "",
            "| # | Model | OR | OR_prov | Reason | Bench | db_tps | In $/M | Out $/M | SWE | Aider | AA | Arena | Ctx | Doc↔Code | pass@1 | Score |",
            "|---:|---|:-:|---|:-:|:-:|---:|---:|---:|---:|---:|---:|---:|---:|:-:|---:|---:|",
        ]
    )
    for i, r in enumerate(onreq_rows, 1):
        lines.append(_fmt_row(i, r))
    if not onreq_rows:
        lines.append(
            "| — | _no On-request rows today_ | — | — | — | — | — | — | — | — | — | — | — | — | — | — | — |"
        )

    # ─── Un-benched candidates (visibility for future microbench runs) ─────
    #
    # Any row in the coding families that (a) is OR-reachable, (b) sits under
    # the Auto price ceiling, and (c) has NEITHER our own live pass_at_1 (from
    # microbench_coding.py) NOR external SWE-bench / Aider-Polyglot / AA-idx
    # data lands here — these are the models whose ranking score will lean
    # entirely on TPS + cost until someone runs a live pass_at_1 on them.
    # Explicit call-out so the operator can budget the next bench.
    unbenched = [
        r
        for r in rows
        if r.get("or_ok")
        and r.get("out_M") is not None
        and r["out_M"] < AUTO_OUTPUT_PRICE_CEILING
        and r.get("he_score") is None
        and not r.get("swe")
        and not r.get("aider")
        and not r.get("aa_idx")
    ]
    lines.extend(
        [
            "",
            "## Candidates not yet benched by us",
            "",
            f"Auto-tier coding candidates (OR-reachable, output ≤ ${AUTO_OUTPUT_PRICE_CEILING:.1f}/Mtok) with no live pass_at_1 from `scripts/kilo-benchmarks/microbench_coding.py` AND no external SWE-bench / Aider-Polyglot / AA-idx signal. Their composite score rests only on TPS + cost until benched, so their ranking is provisional — an explicit `microbench_coding.py --models <id> --datasets humaneval,mbpp` run would move them into (or out of) the top of the Auto tier.",
            "",
            "| Model | In $/M | Out $/M | db_tps | Ctx | Arena | Reason | Score (provisional) |",
            "|---|---:|---:|---:|---:|---:|:-:|---:|",
        ]
    )
    if unbenched:
        for r in unbenched:
            lines.append(
                "| `{mid}` | {inp} | {out} | {tps} | {ctx} | {arena} | {reason} | {score} |".format(
                    mid=_safe_md_id(r["id"]),
                    inp=_fmt_or_dash(r.get("in_M"), "{:.3f}"),
                    out=_fmt_or_dash(r.get("out_M"), "{:.3f}"),
                    tps=_fmt_or_dash(r.get("db_tps"), "{:.0f}"),
                    ctx=_fmt_or_dash(r.get("ctx_k"), "{:.0f}k"),
                    arena=_fmt_or_dash(r.get("arena"), "{:.0f}"),
                    reason="✅" if r.get("reasoning") else "—",
                    score=f"{r['score']:.3f}",
                )
            )
    else:
        lines.append(
            "| — | _every Auto-tier candidate has some quality signal today (either our own bench or an external benchmark)_ | — | — | — | — | — | — |"
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
