# AFTER-EDIT: docs/reference/kilo/TASK_SUBAGENT_SELECTION.md | scripts/kilo-benchmarks/build_task_baselines.py
"""Judged task-subagent benchmark — scores the pool models on docs / research / plan / spec.

Parallel to microbench_review.py (review) and microbench_coding_direct.py (code): a task-agnostic
spine (dispatch → grade → persist_metrics/persist_baseline → batched-resume main()) that a per-task
GRADER fills. Generation goes DIRECTLY through the vendored ai-consult transport
(`libs.subagents._transport.run`, real billed cost via `{"usage":{"include":true}}`) so it reaches
ALL ~57 pool models (the pool 404s some); grading is task-specific and runs LOCALLY ($0):

    research  normalized EM / token-F1 on fabrik-private Q&A (+ a claude-evaluator near-miss tiebreak)
    docs      bidirectional git-grounded recall/precision (reuses doc_reconcile plumbing, torch-free)
    plan/spec free structural filter + correlated cold-start prior (no paid generation)

Each MEASURED model gets BOTH a `model_task_baseline` prior (what pick_models shrinks against) AND
one `subagent_runs` flywheel row per dispatch (`quality_score=score5`) — the latter is load-bearing:
the ranker only surfaces a (model, task_type) with `HAVING COUNT(*) >= 3` real runs, so the baseline
alone never surfaces a cold model (verified rank_task_subagents.py:154-164).

    python microbench_judged.py --task research --all          # full run (persists) — operator step ($)
    python microbench_judged.py --task research --smoke         # $0 stub end-to-end (proves surfacing)
    python microbench_judged.py --task research --report        # print the latest stored table

⚠️ The paid --all 57-model run spends money + takes ~an hour; it is an OPERATOR step (see the runbook),
never run autonomously. The build ships a $0 --smoke that proves the persistence + surfacing path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from collections.abc import Callable
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Protocol

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
CACHE_DIR = SCRIPT_DIR / ".microbench_cache"

# libs.subagents is vendored in fabrik; its _transport IS the ai-consult transport (real cost_usd,
# body passthrough, max_cost_usd). Direct — no pool sandbox/owned_paths overhead for a batch bench.
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))
try:
    from libs.subagents._dotenv import load_env

    # A fresh cron/CLI env has no OPENROUTER_API_KEY — load it from .env so BOTH the transport AND
    # the balance guard can authenticate (without it the guard goes blind → "proceeding on cap alone").
    load_env(str(SCRIPT_DIR.parent.parent))
except Exception:  # pragma: no cover - .env optional (key may already be exported)
    pass
try:
    from libs.subagents._transport import run as _or_run  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - only when the vendored pool is absent
    _or_run = None  # type: ignore[assignment]  # generation unavailable; grading/report still work
try:
    from libs.subagents.agent import AgentResult, AgentSpec  # type: ignore[import-not-found]
    from libs.subagents.pg_ledger import record_agent_run  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - flywheel best-effort when the pool is absent
    AgentSpec = AgentResult = None  # type: ignore[assignment,misc]
    record_agent_run = None  # type: ignore[assignment]

SCALE = 5.0
MAX_TOKENS = 2048  # docs/research outputs are short; bound output length (unbounded = unbounded cost)
# A model is MEASURED only if enough items actually returned — a 404/timeout is not a wrong answer;
# scoring it 0 would poison the ranker into never picking a model we merely failed to reach.
MIN_MEASURED = 3

# ── Cost safety (real money — every knob here is fail-SAFE: bound spend, over-count when unsure) ──
_PER_CALL_COST_CAP = 0.25  # hard per-CALL ceiling passed to the transport (one call can't eat the batch)
_FALLBACK_COST_PER_MTOK = 5.0  # conservative estimate when a provider returns NO billed cost (over-count → stop early)
_BALANCE_SAFETY_FRAC = 0.90  # never let a run's cost-cap exceed 90% of the live OpenRouter balance
BATCH_SIZE = 8  # persist after EACH batch — an interrupted run loses ≤ one batch; a re-run RESUMES

_TASK_KINDS = ("research", "docs", "plan", "spec")


# ── grader + prompter seams (Phases B/C/D fill these) ─────────────────────────────────────────
@dataclass
class _Gen:
    """One (model, item) generation. `spec`/`result` are the synthetic flywheel pair for a SUCCESS;
    both None on an error/cap/unreachable slot (excluded from grading + the flywheel + the denominator)."""

    text: str | None  # None = errored/unreachable
    cost_usd: float
    latency_s: float | None
    out_tokens: int
    error: str | None
    spec: object | None = None  # AgentSpec — carries model + task_type into the flywheel row
    result: object | None = None  # AgentResult(status="done") — required or record_run nulls the score


@dataclass
class TaskScore:
    """One model's graded result for a task. `score5` (0–5) is set BY the grader (each family has a
    different underlying metric); the display axes (recall/precision/structural) are optional."""

    model: str
    score5: float
    n_graded: int
    n_err: int
    cost_usd: float = 0.0
    latencies: list[float] = field(default_factory=list)
    out_tokens: int = 0
    recall: float | None = None  # docs family
    precision: float | None = None  # docs family
    structural: str | None = None  # plan/spec family — e.g. "8/10 checks"

    @property
    def is_measured(self) -> bool:
        return self.n_graded >= MIN_MEASURED

    @property
    def clamped_score5(self) -> float:
        return round(max(0.0, min(SCALE, self.score5)), 3)

    @property
    def grade(self) -> str:
        """Same F1/score→letter cuts as microbench_review/coding (one scale across all tables)."""
        s = self.clamped_score5
        for cut, g in ((4.5, "A+"), (4.0, "A"), (3.5, "B+"), (3.0, "B"), (2.5, "C+"), (2.0, "C"), (1.0, "D")):
            if s >= cut:
                return g
        return "F"

    @property
    def median_latency(self) -> float:
        lat = sorted(x for x in self.latencies if x is not None)
        return round(lat[len(lat) // 2], 3) if lat else 0.0

    @property
    def tokens_per_s(self) -> float:
        total_t = sum(x for x in self.latencies if x is not None)
        return round(self.out_tokens / total_t, 1) if total_t else 0.0

    @property
    def cost_per_1k(self) -> float:
        """$ per 1000 items — comparable across models of different verbosity."""
        return round(self.cost_usd / self.n_graded * 1000, 4) if self.n_graded else 0.0


class Grader(Protocol):
    """A task grader: score each model's generations against the corpus. Deterministic + local ($0)."""

    def __call__(self, gens: dict[str, list[_Gen]], corpus: list[dict]) -> dict[str, TaskScore]: ...


# Phases B/C/D register their graders here (keyed by task_type); PROMPTERS builds a task's prompt.
GRADERS: dict[str, Grader] = {}
PROMPTERS: dict[str, Callable[[dict], str]] = {}


def register_grader(task_type: str, grader: Grader) -> None:
    GRADERS[task_type] = grader


def register_prompter(task_type: str, prompter: Callable[[dict], str]) -> None:
    PROMPTERS[task_type] = prompter


def default_prompt(item: dict) -> str:
    """Fallback prompt builder: a pre-built `prompt`, else question + inlined RAG context."""
    if item.get("prompt"):
        return str(item["prompt"])
    q = str(item.get("question") or item.get("goal") or "")
    ctx = item.get("context")
    return f"Context:\n{ctx}\n\nQuestion: {q}\nAnswer concisely." if ctx else q


def _stub_grader(gens: dict[str, list[_Gen]], corpus: list[dict]) -> dict[str, TaskScore]:
    """Passthrough grader so the spine runs end-to-end before B/C/D land (and for --smoke): a
    non-empty answer scores 5, an empty/errored slot is not graded. Deterministic."""
    scores: dict[str, TaskScore] = {}
    for model, glist in gens.items():
        graded = [g for g in glist if g.text]
        n_err = sum(1 for g in glist if g.text is None)
        scores[model] = TaskScore(
            model=model,
            score5=SCALE if graded else 0.0,
            n_graded=len(graded),
            n_err=n_err,
            cost_usd=round(sum(g.cost_usd for g in glist), 6),
            latencies=[g.latency_s for g in glist if g.latency_s is not None],
            out_tokens=sum(g.out_tokens for g in glist),
        )
    return scores


def _finalize_scores(scores: dict[str, TaskScore], gens: dict[str, list[_Gen]]) -> dict[str, TaskScore]:
    """Overlay the OBJECTIVE metrics (cost / latency / tokens / n_err) onto each TaskScore from the
    real generations — so cost-safety + the cost/latency columns NEVER depend on a Phase-B/C/D grader
    remembering to thread them (a grader owns only score5 / n_graded / recall / precision / structural).
    The harness always knows the true billed cost from `gens`; this makes it the source of truth."""
    for model, glist in gens.items():
        s = scores.get(model)
        if s is None:
            continue
        s.cost_usd = round(sum(g.cost_usd for g in glist), 6)
        s.latencies = [g.latency_s for g in glist if g.latency_s is not None]
        s.out_tokens = sum(g.out_tokens for g in glist)
        s.n_err = sum(1 for g in glist if g.text is None)
    return scores


# ── generation ────────────────────────────────────────────────────────────────────────────────
def _synth_pair(model: str, task_type: str, prompt: str, i: int, gen: _Gen, run_id: str,
                window: str = "v1") -> None:
    """Attach the synthetic (AgentSpec, AgentResult) flywheel pair to a SUCCESSFUL _Gen.

    Raw `_transport.run` yields no AgentSpec/AgentResult (unlike the pool's `run_agents`), yet
    `record_agent_run` needs both — the flywheel row's `model`+`task_type` live on the SPEC, and the
    score only persists when `status == "done"` (record_run nulls a non-done row's quality_score).

    `agent_id` carries a per-RUN nonce (`run_id`) + the window so two runs — a `--fresh` re-measure or
    two windows the same day — never collide on a stable id (the INSERT-only ledger would otherwise
    double-count them under one id). Each dispatch is a distinct run, so a distinct id is correct.
    """
    if AgentSpec is None or AgentResult is None:  # pool absent — flywheel is best-effort
        return
    gen.spec = AgentSpec(task=prompt, model=model, task_type=task_type)
    gen.result = AgentResult(
        agent_id=f"judged-{task_type}-{window}-{model}-{i}-{run_id}",
        text=gen.text or "",
        diff="",
        status="done",  # REQUIRED — record_run nulls the score on any non-"done" status
        provider=None,
        cost_usd=gen.cost_usd,
        turns=1,
        latency_s=gen.latency_s,
        out_tokens=gen.out_tokens,
        model=model,
    )


def generate(
    models: list[str],
    corpus: list[dict],
    task_type: str,
    *,
    cost_cap: float,
    max_tokens: int = MAX_TOKENS,
    max_concurrency: int = 8,
    window: str = "v1",
    prompt_fn: Callable[[dict], str] | None = None,
    run_fn: Callable[..., object] | None = None,
) -> dict[str, list[_Gen]]:
    """One completion per (model, item) via the vendored ai-consult transport, real billed cost.

    Cost-cap = a running-total DISPATCH GATE (the transport has only a per-CALL cap, not a shared
    batch budget): once accumulated billed cost exceeds `cost_cap`, no NEW calls dispatch (in-flight
    finish; overshoot bounded by ≤ max_concurrency). Errored / cap-stopped slots come back
    `text=None` → counted as n_err, never scored 0. `run_fn` is injectable (--smoke / tests).
    """
    run = run_fn or _or_run
    if run is None:
        raise RuntimeError("libs.subagents._transport unavailable — cannot generate (grading/report still work).")
    build_prompt = prompt_fn or PROMPTERS.get(task_type) or default_prompt
    body = {"usage": {"include": True}, "max_tokens": max_tokens}
    run_id = uuid.uuid4().hex[:8]  # per-run nonce → unique agent_ids across --fresh / windows

    def _bill(r: object, toks: int) -> float:
        c = getattr(r, "cost_usd", None)
        return float(c) if c is not None else toks * _FALLBACK_COST_PER_MTOK / 1e6

    # Seed every slot with a "not_run" placeholder so a cap-cancelled / never-dispatched slot is a
    # real _Gen(text=None) → counted as n_err (never a raw None that would crash grade()).
    out: dict[str, list[_Gen]] = {
        m: [_Gen(None, 0.0, None, 0, "not_run") for _ in corpus] for m in models
    }
    spent = 0.0
    stopped = False

    def _one(model: str, i: int, item: dict) -> tuple[str, int, _Gen]:
        prompt = build_prompt(item)
        t0 = time.time()
        try:
            r = run(model, [{"role": "user", "content": prompt}], body=body, max_cost_usd=_PER_CALL_COST_CAP)
            dt = time.time() - t0
            toks = int((getattr(r, "usage", None) or {}).get("completion_tokens") or 0)
            if getattr(r, "error", None) or not getattr(r, "text", None):
                return model, i, _Gen(None, _bill(r, toks), None, 0, getattr(r, "error", None) or "empty")
            gen = _Gen(r.text, _bill(r, toks), dt, toks, None)
            _synth_pair(model, task_type, prompt, i, gen, run_id, window)
            return model, i, gen
        except Exception as e:  # noqa: BLE001 — a single call's failure is that slot's error, never fatal
            return model, i, _Gen(None, 0.0, None, 0, str(e)[:120])

    tasks = [(m, i, it) for m in models for i, it in enumerate(corpus)]
    with ThreadPoolExecutor(max_workers=max_concurrency) as ex:
        futs = {ex.submit(_one, m, i, it): (m, i) for m, i, it in tasks}
        for fut in as_completed(futs):
            try:
                model, i, gen = fut.result()
            except CancelledError:
                continue  # cap-stopped before it ran — slot stays text=None → counted as n_err
            out[model][i] = gen
            spent += gen.cost_usd
            if spent >= cost_cap and not stopped:
                stopped = True
                for f in futs:
                    f.cancel()
    return out


# ── flywheel (the surface-a-cold-model fix) ────────────────────────────────────────────────────
def record_flywheel(gens: dict[str, list[_Gen]], scores: dict[str, TaskScore], *, project: str = "microbench") -> int:
    """One flywheel row per SUCCESSFUL dispatch, `quality_score=score5` (the model's graded score).

    Load-bearing: these rows clear rank_task_subagents' `HAVING COUNT(*) >= 3` gate so a cold model
    SURFACES (the baseline only re-weights an already-surfaced model). Errored/cap slots carry no
    (spec, result) pair → skipped, so a 404 never lands as a quality-0 row (which would mis-teach the
    ranker). Best-effort: a DB hiccup never fails the bench.
    """
    if record_agent_run is None:  # pool absent
        return 0
    n = 0
    for model, glist in gens.items():
        score = scores.get(model)
        if score is None or not score.is_measured:
            continue
        for g in glist:
            if g.text is None or g.spec is None or g.result is None:
                continue
            try:
                if record_agent_run(g.spec, g.result, quality_score=score.clamped_score5, project=project):
                    n += 1
            except Exception:  # noqa: BLE001 — flywheel is best-effort
                pass
    return n


# ── persistence ────────────────────────────────────────────────────────────────────────────────
def _ensure_metrics_table(conn: object) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS model_judged_metrics (
            model_id TEXT NOT NULL, task_type TEXT NOT NULL, score5 REAL, grade TEXT,
            recall REAL, precision REAL, structural TEXT,
            cost_usd REAL, cost_per_1k REAL, p50_latency_s REAL, tokens_per_s REAL,
            n_graded INTEGER, n_err INTEGER, window TEXT, built_at TEXT,
            PRIMARY KEY (model_id, task_type, window, built_at))
    """)


def persist_metrics(scores: dict[str, TaskScore], task_type: str, window: str, db_path: Path = DB_PATH) -> Path:
    """Store MEASURED models in model_judged_metrics (one table, task_type-discriminated) + a JSON artifact."""
    import sqlite3

    today = date.today().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        _ensure_metrics_table(conn)
        for s in scores.values():
            if not s.is_measured:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO model_judged_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (s.model, task_type, s.clamped_score5, s.grade, s.recall, s.precision, s.structural,
                 round(s.cost_usd, 6), s.cost_per_1k, s.median_latency, s.tokens_per_s,
                 s.n_graded, s.n_err, window, today),
            )
        conn.commit()
    finally:
        conn.close()
    CACHE_DIR.mkdir(exist_ok=True)
    # window in the filename (two windows same day don't clobber) + MERGE with any existing content so
    # the batched --all run accumulates ALL measured models, not just the last batch's (reviewer C1).
    art = CACHE_DIR / f"judged_metrics_{task_type}_{window}_{today}.json"
    merged: dict = {}
    if art.exists():
        try:
            loaded = json.loads(art.read_text())
            merged = loaded if isinstance(loaded, dict) else {}  # a non-object JSON → reset (no crash)
        except (OSError, json.JSONDecodeError):
            merged = {}
    merged.update(
        {s.model: {"grade": s.grade, "score5": s.clamped_score5, "recall": s.recall,
                   "precision": s.precision, "structural": s.structural, "cost_per_1k": s.cost_per_1k,
                   "p50_latency_s": s.median_latency, "n_graded": s.n_graded, "n_err": s.n_err}
         for s in scores.values() if s.is_measured})
    art.write_text(json.dumps(merged, indent=2))
    return art


def persist_baseline(scores: dict[str, TaskScore], task_type: str, window: str, db_path: Path = DB_PATH) -> int:
    """Write measured score5 as the task_type prior that pick_models(task_type) shrinks against.

    source='microbench_judged:<task>' tags provenance. (build_task_baselines only EMITS ops/code
    priors today — its `TASK_CATEGORIES` has no judged task — so nothing there clobbers these rows;
    were a judged task ever added there, its precedence guard would need to protect this source too.)
    """
    import sqlite3

    from build_task_baselines import ensure_table  # same dir, same DB

    ensure_table(db_path)
    today = date.today().isoformat()
    conn = sqlite3.connect(db_path)
    n = 0
    try:
        for s in scores.values():
            if not s.is_measured:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO model_task_baseline "
                "(model_id, task_type, baseline, pass_rate, n_tasks, n_trials, source, built_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (s.model, task_type, s.clamped_score5, round(s.clamped_score5 / SCALE, 4),
                 s.n_graded, s.n_graded, f"microbench_judged:{task_type}", today),
            )
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


def load_judged_metrics(task_type: str, db_path: Path = DB_PATH) -> dict[str, dict]:
    """Latest-per-model metrics for ONE task_type (the Phase-E leaderboard + `<task>_eligible()` source).

    ⚠️ Phase E readers MUST call THIS — the harness stores ALL judged tasks in the single
    `model_judged_metrics` table (task_type-discriminated), NOT per-task `model_<task>_metrics`
    tables. A naive mirror of `load_review_metrics`/`load_coding_metrics` that queried
    `model_research_metrics`/`model_docs_metrics` would read an empty (non-existent) table and silently
    drop every model. Fail-soft: empty dict when the table/task is absent (benchmark not yet run)."""
    import sqlite3

    out: dict[str, dict] = {}
    if not Path(db_path).exists():  # mode=ro refuses to CREATE a missing file → guard first (fail-soft)
        return {}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)  # concurrent-write safe (read-only)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_judged_metrics'"
        ).fetchone():
            return {}
        rows = conn.execute(
            "SELECT model_id, score5, grade, recall, precision, structural, cost_per_1k, "
            "p50_latency_s, tokens_per_s, n_graded, n_err, built_at "
            "FROM model_judged_metrics WHERE task_type=? ORDER BY built_at, window",
            (task_type,),  # (built_at, window) → deterministic latest-per-model on a same-day tie (C3)
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conn.close()
    for r in rows:  # ORDER BY built_at ASC → later dates overwrite → latest-per-model wins
        out[r[0]] = {"score5": r[1], "grade": r[2], "recall": r[3], "precision": r[4],
                     "structural": r[5], "cost_per_1k": r[6], "p50_latency_s": r[7],
                     "tokens_per_s": r[8], "n_graded": r[9], "n_err": r[10], "built_at": r[11]}
    return out


def _measured_models(task_type: str, window: str, db_path: Path = DB_PATH) -> set[str]:
    """Models already measured for THIS (task_type, window) today — for --all RESUME (skip re-paying)."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_judged_metrics'"
        ).fetchone():
            return set()
        today = date.today().isoformat()
        return {
            r[0] for r in conn.execute(
                "SELECT DISTINCT model_id FROM model_judged_metrics WHERE task_type=? AND window=? AND built_at=?",
                (task_type, window, today),
            ).fetchall()
        }
    finally:
        conn.close()


# ── model resolution + balance guard (mirror the coding bench) ─────────────────────────────────
def _resolve_models(explicit: list[str] | None, auto_tier: bool, task_type: str = "research",
                    db_path: Path = DB_PATH) -> list[str]:
    """Default = all ~57 models the sibling benches measured (review ∪ coding). --auto-tier restricts
    to THIS task's pick_models-selectable pool (out ≤ $1.5/Mtok). Explicit --models always wins."""
    if explicit:
        return explicit
    if auto_tier:
        try:
            from libs.subagents.select import pick_models  # type: ignore[import-not-found]

            return sorted(set(pick_models(task_type, n=64)))  # this task's selectable pool ids
        except Exception:
            return []
    import sqlite3

    conn = sqlite3.connect(db_path)
    ids: set[str] = set()
    try:
        for tbl in ("model_review_metrics", "model_coding_metrics"):
            if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,)).fetchone():
                ids.update(r[0] for r in conn.execute(f"SELECT DISTINCT model_id FROM {tbl}").fetchall())  # noqa: S608
    finally:
        conn.close()
    return sorted(ids)


def _openrouter_balance() -> float | None:
    """Live remaining OpenRouter credit in $, or None if unreachable. One read-only GET."""
    import urllib.request

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/credits", headers={"Authorization": f"Bearer {key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 — fixed https host, not user input
            d = json.loads(resp.read()).get("data", {})
        return float(d.get("total_credits", 0)) - float(d.get("total_usage", 0))
    except Exception:
        return None


# ── report ─────────────────────────────────────────────────────────────────────────────────────
def report(scores: dict[str, TaskScore], task_type: str) -> None:
    ranked = sorted(scores.values(), key=lambda s: (-s.clamped_score5, s.model))
    print(f"\n[{task_type}] {'#':>2}  {'model':<34} {'grade':<5} {'/5':>5} {'$/1k':>8} {'p50 s':>6} {'n':>4}")
    print("-" * 78)
    for i, s in enumerate((s for s in ranked if s.is_measured), 1):
        print(f"     {i:>2}  {s.model:<34} {s.grade:<5} {s.clamped_score5:>5.2f} "
              f"{s.cost_per_1k:>8.4f} {s.median_latency:>6.1f} {s.n_graded:>4}")
    unmeasured = [s.model for s in scores.values() if not s.is_measured]
    if unmeasured:
        print(f"\nunmeasured ({len(unmeasured)}, < {MIN_MEASURED} graded / unreachable): {', '.join(unmeasured)}")


def report_stored(task_type: str, db_path: Path = DB_PATH) -> None:
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_judged_metrics'"
        ).fetchone():
            print(f"no stored {task_type} metrics — run with --all first")
            return
        latest = conn.execute(
            "SELECT MAX(built_at) FROM model_judged_metrics WHERE task_type=?", (task_type,)
        ).fetchone()[0]
        if latest is None:  # table exists but no rows for THIS task → friendly message, not "built None"
            print(f"no stored {task_type} metrics — run with --all first")
            return
        # (built_at, window) order → dedupe to ONE deterministic row per model, so two windows sharing
        # the latest day don't print the same model twice (reviewer C3).
        raw = conn.execute(
            "SELECT model_id, grade, score5, cost_per_1k, p50_latency_s, n_graded "
            "FROM model_judged_metrics WHERE task_type=? AND built_at=? ORDER BY window",
            (task_type, latest),
        ).fetchall()
    finally:
        conn.close()
    dedup = {r[0]: r for r in raw}  # last (highest window) wins deterministically
    rows = sorted(dedup.values(), key=lambda r: -r[2])
    print(f"\n{task_type} metrics (built {latest})")
    print(f"{'#':>2}  {'model':<34} {'grade':<5} {'/5':>5} {'$/1k':>8} {'p50 s':>6} {'n':>4}")
    print("-" * 78)
    for i, r in enumerate(rows, 1):
        print(f"{i:>2}  {r[0]:<34} {r[1]:<5} {r[2]:>5.2f} {r[3]:>8.4f} {r[4]:>6.1f} {r[5]:>4}")


# ── smoke ($0, no network — proves the persist + surfacing path end-to-end) ────────────────────
def _smoke_corpus(n: int = 3) -> list[dict]:
    """A ≥3-item synthetic corpus (≥3 so the stub model clears the ranker's HAVING COUNT>=3 gate)."""
    return [{"question": f"smoke-q{i}", "context": f"ctx{i}", "gold": f"a{i}", "prompt": f"echo a{i}"}
            for i in range(max(3, n))]


def _echo_run(model: str, messages: list[dict], *, body: dict, max_cost_usd: float) -> object:
    """A $0 stand-in for _transport.run: echoes the prompt back so the stub grader scores it measured."""

    @dataclass
    class _R:
        text: str
        error: str | None = None
        cost_usd: float = 0.0
        usage: dict = field(default_factory=lambda: {"completion_tokens": 3})

    return _R(text=messages[0]["content"])


def run_smoke(task_type: str, db_path: Path = DB_PATH) -> dict[str, TaskScore]:
    """End-to-end $0 stub: dispatch (echo) → grade (registered grader or stub) → persist baseline +
    metrics + flywheel. Proves a seeded model gets ≥3 flywheel rows so rank_task_subagents surfaces it."""
    corpus = _smoke_corpus()
    models = ["smoke/echo-model"]
    gens = generate(models, corpus, task_type, cost_cap=1.0, window="smoke", run_fn=_echo_run)
    grader = GRADERS.get(task_type, _stub_grader)
    scores = _finalize_scores(grader(gens, corpus), gens)
    persist_metrics(scores, task_type, "smoke", db_path)
    persist_baseline(scores, task_type, "smoke", db_path)
    # attempted = flywheel rows this run WOULD write (measured successes); committed = rows the DB
    # accepted NOW. On a box with no DSN route to postgres, record_agent_run durably OUTBOXES each row
    # and returns False → committed<attempted, and a hub-side flush_outbox lands them later. Report
    # BOTH so the smoke never claims "0 rows" when 3 were durably captured (reviewer finding F-A).
    attempted = sum(1 for m, gl in gens.items() if (scores.get(m) and scores[m].is_measured)
                    for g in gl if g.spec is not None)
    committed = record_flywheel(gens, scores, project="microbench-smoke")
    measured = sum(s.is_measured for s in scores.values())
    if record_agent_run is None:
        print("[smoke] ⚠️  libs.subagents absent — the flywheel path was NOT exercised (surfacing unproven here)")
    # key the headline off MEASURED (not attempted) so a pool-absent box doesn't misreport "0 measured"
    # when the grader did measure the model (reviewer C2); report the flywheel counts honestly alongside.
    print(f"[smoke] {task_type}: {measured} measured; {attempted} flywheel rows attempted, "
          f"{committed} committed now ({attempted - committed} outboxed for hub flush)")
    return scores


# ── main ─────────────────────────────────────────────────────────────────────────────────────
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="microbench_judged", description=__doc__)
    p.add_argument("--task", choices=_TASK_KINDS, default="research", help="task type to benchmark")
    p.add_argument("--models", nargs="*", help="explicit model ids (default: all review∪coding models)")
    p.add_argument("--window", default="v1", help="corpus/window tag stored with the metrics (default v1)")
    p.add_argument("--cost-cap", type=float, default=15.0, help="running billed-$ dispatch gate (default 15)")
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS, help=f"output cap per call (default {MAX_TOKENS})")
    p.add_argument("--concurrency", type=int, default=16, help="parallel in-flight calls (default 16)")
    p.add_argument("--auto-tier", action="store_true", help="restrict to the pick_models-selectable pool (cost lever)")
    p.add_argument("--all", action="store_true", help="run + persist metrics + task_baseline (batched, resumable)")
    p.add_argument("--fresh", action="store_true", help="with --all: re-measure even models already done today")
    p.add_argument("--smoke", action="store_true", help="$0 stub end-to-end (proves surfacing) + exit")
    p.add_argument("--report", action="store_true", help="print the latest stored table + exit")
    args = p.parse_args(argv)

    if args.report:
        report_stored(args.task)
        return 0
    if args.smoke:
        run_smoke(args.task)
        return 0

    if args.task not in GRADERS:
        print(f"no grader registered for '{args.task}' — import its grader module first", file=sys.stderr)
        return 1
    models = _resolve_models(args.models, args.auto_tier, args.task)
    if not models:
        print("no models resolved (pass --models or run the review/coding bench first)", file=sys.stderr)
        return 1
    corpus_path = SCRIPT_DIR / "corpora" / f"{args.task}_qa.json"
    if not corpus_path.exists():
        print(f"corpus missing: {corpus_path} — author it first (Phase B/C)", file=sys.stderr)
        return 1
    corpus = json.loads(corpus_path.read_text())
    if not corpus:
        print(f"corpus empty: {corpus_path} — nothing to grade", file=sys.stderr)
        return 1
    print(f"[judged] task={args.task} models={len(models)} corpus={len(corpus)}", file=sys.stderr)

    # ── COST SAFETY: never let the run's cap exceed the LIVE OpenRouter balance ──
    eff_cap = args.cost_cap
    bal = _openrouter_balance()
    if bal is not None:
        safe = round(bal * _BALANCE_SAFETY_FRAC, 2)
        print(f"[judged] OpenRouter balance ${bal:.2f}; requested cost-cap ${args.cost_cap:.2f}", file=sys.stderr)
        if args.cost_cap > safe:
            eff_cap = safe
            print(f"[judged] ⚠️  cost-cap LOWERED to ${eff_cap:.2f} (90% of balance) to protect the account", file=sys.stderr)
        if eff_cap < 0.01:
            print("[judged] balance exhausted — refusing to run", file=sys.stderr)
            return 1
    else:
        print("[judged] ⚠️  could not read OpenRouter balance — proceeding on the cost-cap alone", file=sys.stderr)

    grader = GRADERS[args.task]
    if not args.all:
        gens = generate(models, corpus, args.task, cost_cap=eff_cap, max_tokens=args.max_tokens,
                        max_concurrency=args.concurrency, window=args.window)
        report(_finalize_scores(grader(gens, corpus), gens), args.task)
        return 0

    # ── --all: BATCHED, RESUMABLE, incremental-persist run ──
    if not args.fresh:
        done = _measured_models(args.task, args.window)
        if done:
            models = [m for m in models if m not in done]
            print(f"[judged] resume: {len(done)} already measured today — {len(models)} to go", file=sys.stderr)
    all_scores: dict[str, TaskScore] = {}
    spent = 0.0
    for bi in range(0, len(models), BATCH_SIZE):
        batch = models[bi:bi + BATCH_SIZE]
        rem = round(eff_cap - spent, 2)
        if rem < 0.05:
            print(f"[judged] cost-cap ${eff_cap:.2f} reached after {len(all_scores)} models — stopping", file=sys.stderr)
            break
        gens = generate(batch, corpus, args.task, cost_cap=rem, max_tokens=args.max_tokens,
                        max_concurrency=args.concurrency, window=args.window)
        scores = _finalize_scores(grader(gens, corpus), gens)  # harness owns cost/latency/tokens/n_err
        persist_metrics(scores, args.task, args.window)
        persist_baseline(scores, args.task, args.window)
        record_flywheel(gens, scores)
        # spend from the REAL generations, never a grader's (possibly-zeroed) TaskScore.cost_usd —
        # this is the cross-batch cost gate, so it must not depend on grader bookkeeping (finding #1).
        spent += sum(g.cost_usd for gl in gens.values() for g in gl)
        all_scores.update(scores)
        nm = sum(1 for s in scores.values() if s.is_measured)
        print(f"[judged] batch {bi // BATCH_SIZE + 1}: +{nm}/{len(batch)} measured & PERSISTED; "
              f"spent ${spent:.2f}/${eff_cap:.2f}", file=sys.stderr)
    report(all_scores, args.task)
    print(f"\n[judged] persisted {sum(s.is_measured for s in all_scores.values())} models; spent ${spent:.2f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
