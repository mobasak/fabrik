# AFTER-EDIT: docs/reference/kilo/CODING_SUBAGENT_SELECTION.md | scripts/kilo-benchmarks/build_task_baselines.py
"""Coding-performance benchmark — LiveCodeBench (contamination-free), DIRECT dispatch.

One uniform pass@1 per model over ONE fixed LiveCodeBench window, apples-to-apples with the
review table. Generation goes DIRECTLY through the vendored ai-consult transport
(`libs.subagents._transport.run`, real billed `cost_usd` via `{"usage":{"include":true}}`);
grading reuses LiveCodeBench's sandboxed test execution (`lcb_runner.evaluation.codegen_metrics`)
via the sibling `.lcb-venv` (grading-only install — no torch/vllm). pass@1 -> grade (same 0-5
letter scale as review) -> model_coding_metrics + model_task_baseline(code).

    metric   pass@1 = fraction of problems whose generated code passes ALL its tests (IS the accuracy;
             code passes or it doesn't -> no "precision" column, unlike review).
    columns  # . model . grade . pass@1 % . $/1k . p50 s

    python microbench_coding_direct.py --probe --models X Y       # 1-2 problems x models, real-token estimate
    python microbench_coding_direct.py --all --release-version release_v5 --limit 50   # full run (persists)
    python microbench_coding_direct.py --report                  # print the latest stored table

Isolation: NEVER touches the pool-coupled microbench_coding.py. The build writes NO real db
(tests use temp sqlite); the operator triggers the real ~$12-18 run.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
LCB_VENV_PY = SCRIPT_DIR / ".lcb-venv" / "bin" / "python"
CACHE_DIR = SCRIPT_DIR / ".microbench_cache"

# libs.subagents is vendored in fabrik; its _transport IS the ai-consult transport (real cost_usd,
# body passthrough, max_cost_usd). Direct — no pool sandbox/owned_paths overhead for a batch bench.
sys.path.insert(0, str(SCRIPT_DIR.parent.parent))
try:
    from libs.subagents._transport import run as _or_run  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - only when the vendored pool is absent
    _or_run = None  # type: ignore[assignment]  # generation unavailable; grading/report still work

SCALE = 5.0
MAX_TOKENS = 4096
# A model is MEASURED only if enough problems actually returned — a 404/timeout is not a wrong
# answer; scoring it 0 would poison the ranker into never picking a model we failed to reach.
MIN_MEASURED = 3

# ── Cost safety (real money — every knob here is fail-SAFE: bound spend, over-count when unsure) ──
_PER_CALL_COST_CAP = 0.50  # hard per-CALL ceiling passed to the transport (one call can never eat the batch)
# When a provider returns NO billed cost (cost_unknown), the running total would go blind and the
# cost-cap could never trigger. Fall back to a CONSERVATIVE token estimate (higher than most real
# rates) so an unknown-cost call still counts toward the cap — over-counting stops the run early,
# never drains the account silently.
_FALLBACK_COST_PER_MTOK = 5.0
_LCB_TIMEOUT_S = 900  # outer wall-clock on the .lcb-venv grader subprocess (a hung sandbox = wedged run)
_BALANCE_SAFETY_FRAC = 0.90  # never let a run's cost-cap exceed 90% of the live OpenRouter balance

_TASK_SUFFIX = (
    "\n\nWrite a complete, correct Python 3 solution. Read from stdin and write to stdout unless a "
    "function signature / starter code is given. Output ONLY the code, in a single ```python block."
)


# ── LiveCodeBench-side helpers (run in .lcb-venv — need lcb_runner + datasets) ────────────────
# Embedded as strings + executed via .lcb-venv/bin/python so the main tool stays in fabrik's .venv
# (which has neither lcb_runner nor datasets). Both read/write JSON on argv for a clean boundary.

_CORPUS_SRC = r'''
import json, sys
from lcb_runner.benchmarks.code_generation import load_code_generation_dataset
release, limit, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
probs = load_code_generation_dataset(release_version=release)
if limit > 0:
    probs = probs[:limit]
rows = [{"question_id": str(p.question_id), "prompt": p.question_content,
         "starter_code": p.starter_code or "", "sample": p.get_evaluation_sample()} for p in probs]
json.dump(rows, open(out, "w"))
print(f"loaded {len(rows)} problems from {release}", file=sys.stderr)
'''

_GRADE_SRC = r'''
import json, sys
from lcb_runner.evaluation import codegen_metrics
payload = json.load(open(sys.argv[1]))           # {"samples":[...], "per_model":{model:[code_or_None,...]}}
samples = payload["samples"]
out = {}
for model, codes in payload["per_model"].items():
    idx = [i for i, c in enumerate(codes) if c is not None]     # grade only problems that returned
    if len(idx) < 1:
        out[model] = {"pass_at_1": None, "n_graded": 0}; continue
    s = [samples[i] for i in idx]
    g = [[codes[i]] for i in idx]
    metrics, _, _ = codegen_metrics(s, g, k_list=[1], num_process_evaluate=8, timeout=6)
    out[model] = {"pass_at_1": metrics.get("pass@1"), "n_graded": len(idx)}
json.dump(out, open(sys.argv[2], "w"))
'''


def _run_lcb(src: str, args: list[str]) -> None:
    """Execute a .lcb-venv-side helper. Raises RuntimeError with a clear message if the venv is absent."""
    if not LCB_VENV_PY.exists():
        raise RuntimeError(
            f"{LCB_VENV_PY} missing — run the Phase-A provisioning "
            "(git clone LiveCodeBench + .lcb-venv grading-only install) first."
        )
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(src)
        helper = f.name
    try:
        # timeout: a model's generated code can hang the sandbox past codegen_metrics' per-problem
        # cap (deadlocked child, un-reaped process); without this the whole run wedges indefinitely.
        subprocess.run([str(LCB_VENV_PY), helper, *args], check=True, timeout=_LCB_TIMEOUT_S)
    finally:
        Path(helper).unlink(missing_ok=True)


@dataclass
class Problem:
    question_id: str
    prompt: str
    starter_code: str
    sample: dict  # get_evaluation_sample() -> {"input_output": ...}


def load_corpus(release_version: str, limit: int | None) -> list[Problem]:
    """Load the fixed LiveCodeBench window (via .lcb-venv). limit<=0 / None = whole release."""
    with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as f:
        out = f.name
    try:
        _run_lcb(_CORPUS_SRC, [release_version, str(limit or 0), out])
        rows = json.loads(Path(out).read_text())
    finally:
        Path(out).unlink(missing_ok=True)
    return [Problem(r["question_id"], r["prompt"], r["starter_code"], r["sample"]) for r in rows]


def extract_code(text: str) -> str:
    """Pull the solution out of a model's answer: prefer a fenced ```python block, else the whole text."""
    if not text:
        return ""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    return (m.group(1) if m else text).strip()


@dataclass
class _Gen:
    code: str | None  # None = errored/unreachable (excluded from grading + denominator)
    cost_usd: float
    latency_s: float | None
    out_tokens: int
    error: str | None


def generate(
    models: list[str],
    corpus: list[Problem],
    *,
    cost_cap: float,
    max_tokens: int = MAX_TOKENS,
    max_concurrency: int = 6,
) -> dict[str, list[_Gen]]:
    """One completion per (model, problem) via the vendored ai-consult transport, real billed cost.

    Cost-cap = a running-total DISPATCH GATE (the vendored `_transport.run` has only a per-CALL cap,
    not a shared batch budget): once the accumulated billed cost exceeds `cost_cap`, no NEW calls
    dispatch (in-flight ones finish). Overshoot bounded by <= max_concurrency in-flight. Errored /
    cap-stopped calls come back `code=None` -> counted as n_err, never scored 0.
    """
    if _or_run is None:
        raise RuntimeError("libs.subagents._transport unavailable — cannot generate (grading/report still work).")
    # max_tokens bounds output length (unbounded output = unbounded cost); usage.include -> real billed cost.
    body = {"usage": {"include": True}, "max_tokens": max_tokens}

    def _bill(r: object, toks: int) -> float:
        # real billed cost when the provider returned it; else a CONSERVATIVE token estimate so the
        # running cost-cap is never blind on an unknown-cost call (fail-safe: over-count, stop early).
        c = getattr(r, "cost_usd", None)
        return float(c) if c is not None else toks * _FALLBACK_COST_PER_MTOK / 1e6
    # Seed every slot with a "not_run" placeholder so a cap-cancelled / never-dispatched slot is a
    # real _Gen(code=None) -> counted as n_err (never a raw None that would crash grade()).
    out: dict[str, list[_Gen]] = {
        m: [_Gen(None, 0.0, None, 0, "not_run") for _ in corpus] for m in models
    }
    spent = 0.0
    stopped = False

    def _one(model: str, i: int, prob: Problem) -> tuple[str, int, _Gen]:
        prompt = prob.prompt + (f"\n\nStarter code:\n{prob.starter_code}" if prob.starter_code else "") + _TASK_SUFFIX
        t0 = time.time()
        try:
            # per-call cap = a small FIXED ceiling (never the whole batch budget); one call can't drain it.
            r = _or_run(model, [{"role": "user", "content": prompt}], body=body, max_cost_usd=_PER_CALL_COST_CAP)
            dt = time.time() - t0
            toks = int((r.usage or {}).get("completion_tokens") or 0)
            if r.error or not r.text:
                return model, i, _Gen(None, _bill(r, toks), None, 0, r.error or "empty")
            return model, i, _Gen(extract_code(r.text), _bill(r, toks), dt, toks, None)
        except Exception as e:  # noqa: BLE001 — a single call's failure is that slot's error, never fatal
            return model, i, _Gen(None, 0.0, None, 0, str(e)[:120])

    tasks = [(m, i, p) for m in models for i, p in enumerate(corpus)]
    with ThreadPoolExecutor(max_workers=max_concurrency) as ex:
        futs = {ex.submit(_one, m, i, p): (m, i) for m, i, p in tasks}
        for fut in as_completed(futs):
            try:
                model, i, gen = fut.result()
            except CancelledError:
                continue  # cap-stopped before it ran — slot stays code=None -> counted as n_err
            out[model][i] = gen
            spent += gen.cost_usd
            if spent >= cost_cap and not stopped:
                stopped = True
                # cancel not-yet-started dispatches (in-flight finish); their slots stay code=None -> n_err
                for f in futs:
                    f.cancel()
    return out


@dataclass
class CodingScore:
    model: str
    pass_at_1: float | None  # 0-1 fraction over graded problems; None if unmeasured
    n_problems: int  # problems attempted
    n_graded: int  # problems that returned + were graded
    n_err: int  # errored / cap-stopped / unreachable
    cost_usd: float
    latencies: list[float] = field(default_factory=list)
    out_tokens: int = 0

    @property
    def is_measured(self) -> bool:
        return self.n_graded >= MIN_MEASURED and self.pass_at_1 is not None

    @property
    def score5(self) -> float:
        return round((self.pass_at_1 or 0.0) * SCALE, 3)

    @property
    def grade(self) -> str:
        """Same F1/score->letter cuts as microbench_review (one scale across both tables)."""
        s = self.score5
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
        """$ per 1000 problems — comparable across models of different verbosity."""
        return round(self.cost_usd / self.n_graded * 1000, 4) if self.n_graded else 0.0


def grade(gens: dict[str, list[_Gen]], corpus: list[Problem]) -> dict[str, CodingScore]:
    """Grade each model's generations via LiveCodeBench's sandbox (.lcb-venv codegen_metrics)."""
    samples = [p.sample for p in corpus]
    per_model = {m: [g.code for g in glist] for m, glist in gens.items()}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"samples": samples, "per_model": per_model}, f)
        infile = f.name
    with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as f:
        outfile = f.name
    try:
        _run_lcb(_GRADE_SRC, [infile, outfile])
        graded = json.loads(Path(outfile).read_text())
    finally:
        Path(infile).unlink(missing_ok=True)
        Path(outfile).unlink(missing_ok=True)
    scores: dict[str, CodingScore] = {}
    for model, glist in gens.items():
        g = graded.get(model, {})
        n_err = sum(1 for x in glist if x.code is None)
        scores[model] = CodingScore(
            model=model,
            pass_at_1=g.get("pass_at_1"),
            n_problems=len(glist),
            n_graded=int(g.get("n_graded") or 0),
            n_err=n_err,
            cost_usd=round(sum(x.cost_usd for x in glist), 4),
            latencies=[x.latency_s for x in glist if x.latency_s is not None],
            out_tokens=sum(x.out_tokens for x in glist),
        )
    return scores


# ── persistence (Phase C wires it into selection) ────────────────────────────────────────────
def persist_metrics(scores: dict[str, CodingScore], window: str, db_path: Path = DB_PATH) -> Path:
    """Store MEASURED models in model_coding_metrics (parallel to model_review_metrics) + a dated JSON."""
    import sqlite3

    today = date.today().isoformat()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_coding_metrics (
                model_id TEXT NOT NULL, pass_at_1 REAL, score5 REAL, grade TEXT,
                cost_usd REAL, cost_per_1k REAL, p50_latency_s REAL, tokens_per_s REAL,
                n_problems INTEGER, n_graded INTEGER, n_err INTEGER, window TEXT, built_at TEXT,
                PRIMARY KEY (model_id, built_at))
        """)
        for s in scores.values():
            if not s.is_measured:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO model_coding_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (s.model, round(s.pass_at_1 or 0.0, 4), s.score5, s.grade, s.cost_usd, s.cost_per_1k,
                 s.median_latency, s.tokens_per_s, s.n_problems, s.n_graded, s.n_err, window, today),
            )
        conn.commit()
    finally:
        conn.close()
    CACHE_DIR.mkdir(exist_ok=True)
    art = CACHE_DIR / f"coding_metrics_{today}.json"
    art.write_text(json.dumps(
        {s.model: {"grade": s.grade, "pass_at_1": round(s.pass_at_1 or 0.0, 4), "score5": s.score5,
                   "cost_per_1k": s.cost_per_1k, "p50_latency_s": s.median_latency,
                   "tokens_per_s": s.tokens_per_s, "n_graded": s.n_graded, "n_err": s.n_err}
         for s in scores.values() if s.is_measured}, indent=2))
    return art


def persist_baseline(scores: dict[str, CodingScore], window: str, db_path: Path = DB_PATH) -> int:
    """Write measured pass@1 as the task_type='code' prior that pick_models('code') ranks on.

    source='livecodebench:<window>' so build_task_baselines' precedence guard keeps it over the
    terminal-bench scraped 'code' baseline.
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
                (s.model, "code", s.score5, round(s.pass_at_1 or 0.0, 4), s.n_graded, s.n_graded,
                 f"livecodebench:{window}", today),
            )
            n += 1
        conn.commit()
    finally:
        conn.close()
    return n


# ── report ────────────────────────────────────────────────────────────────────────────────────
def _openrouter_balance() -> float | None:
    """Live remaining OpenRouter credit in $, or None if unreachable. One read-only GET."""
    import os
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


def _resolve_models(explicit: list[str] | None, db_path: Path = DB_PATH) -> list[str]:
    """Default = the SAME models the review table measured (apples-to-apples, by construction)."""
    if explicit:
        return explicit
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_review_metrics'"
        ).fetchone():
            return []
        rows = [r[0] for r in conn.execute("SELECT DISTINCT model_id FROM model_review_metrics").fetchall()]
    finally:
        conn.close()
    return sorted(rows)


def report(scores: dict[str, CodingScore]) -> None:
    ranked = sorted(scores.values(), key=lambda s: (-(s.score5), s.model))
    print(f"\n{'#':>2}  {'model':<34} {'grade':<5} {'pass@1':>7} {'$/1k':>8} {'p50 s':>6} {'n':>4}")
    print("-" * 76)
    for i, s in enumerate(ranked, 1):
        if not s.is_measured:
            continue
        print(f"{i:>2}  {s.model:<34} {s.grade:<5} {(s.pass_at_1 or 0) * 100:>6.1f}% "
              f"{s.cost_per_1k:>8.4f} {s.median_latency:>6.1f} {s.n_graded:>4}")
    unmeasured = [s.model for s in scores.values() if not s.is_measured]
    if unmeasured:
        print(f"\nunmeasured ({len(unmeasured)}, < {MIN_MEASURED} graded / unreachable): {', '.join(unmeasured)}")


def report_stored(db_path: Path = DB_PATH) -> None:
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_coding_metrics'"
        ).fetchone():
            print("no stored coding metrics — run with --all first")
            return
        latest = conn.execute("SELECT MAX(built_at) FROM model_coding_metrics").fetchone()[0]
        rows = conn.execute(
            "SELECT model_id, grade, pass_at_1, cost_per_1k, p50_latency_s, n_graded, window "
            "FROM model_coding_metrics WHERE built_at=? ORDER BY score5 DESC", (latest,)
        ).fetchall()
    finally:
        conn.close()
    print(f"\ncoding metrics (built {latest}, window {rows[0][6] if rows else '?'})")
    print(f"{'#':>2}  {'model':<34} {'grade':<5} {'pass@1':>7} {'$/1k':>8} {'p50 s':>6} {'n':>4}")
    print("-" * 76)
    for i, r in enumerate(rows, 1):
        print(f"{i:>2}  {r[0]:<34} {r[1]:<5} {r[2] * 100:>6.1f}% {r[3]:>8.4f} {r[4]:>6.1f} {r[5]:>4}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="microbench_coding_direct", description=__doc__)
    p.add_argument("--models", nargs="*", help="explicit model ids (default: the models review measured)")
    p.add_argument("--release-version", default="release_v5", help="LiveCodeBench window (default release_v5)")
    p.add_argument("--limit", type=int, default=50, help="problems from the window (default 50; <=0 = all)")
    p.add_argument("--cost-cap", type=float, default=20.0, help="running billed-$ dispatch gate (default 20)")
    p.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    p.add_argument("--concurrency", type=int, default=6)
    p.add_argument("--probe", action="store_true", help="1-2 problems x models -> real-token cost estimate, no persist")
    p.add_argument("--all", action="store_true", help="run + persist metrics + task_baseline")
    p.add_argument("--report", action="store_true", help="print the latest stored table + exit")
    args = p.parse_args(argv)

    if args.report:
        report_stored()
        return 0

    models = _resolve_models(args.models)
    if not models:
        print("no models resolved (pass --models or run the review bench first)", file=sys.stderr)
        return 1
    review_n = len(_resolve_models(None)) if args.models else len(models)
    print(f"[coding-bench] resolved {len(models)} models"
          + (f" (review table has {review_n}; shortfall!)" if len(models) < review_n else ""), file=sys.stderr)

    limit = 2 if args.probe else args.limit
    window = args.release_version
    corpus = load_corpus(window, limit)
    print(f"[coding-bench] corpus: {len(corpus)} problems from {window}", file=sys.stderr)

    # ── COST SAFETY (real money): never let the run's cap exceed the LIVE OpenRouter balance ──
    eff_cap = args.cost_cap
    bal = _openrouter_balance()
    if bal is not None:
        safe = round(bal * _BALANCE_SAFETY_FRAC, 2)
        print(f"[coding-bench] OpenRouter balance ${bal:.2f}; requested cost-cap ${args.cost_cap:.2f}", file=sys.stderr)
        if args.cost_cap > safe:
            eff_cap = safe
            print(f"[coding-bench] ⚠️  cost-cap ${args.cost_cap:.2f} exceeds 90% of balance — LOWERED to "
                  f"${eff_cap:.2f} to protect the account", file=sys.stderr)
        if eff_cap < 0.01:
            print("[coding-bench] balance exhausted — refusing to run", file=sys.stderr)
            return 1
    else:
        print("[coding-bench] ⚠️  could not read OpenRouter balance — proceeding on the cost-cap alone", file=sys.stderr)

    gens = generate(models, corpus, cost_cap=eff_cap, max_tokens=args.max_tokens,
                    max_concurrency=args.concurrency)
    scores = grade(gens, corpus)

    if args.probe:
        total_cost = sum(s.cost_usd for s in scores.values())
        per_model = total_cost / max(len(models), 1)
        full = int(args.limit if args.limit > 0 else 50)
        print(f"\n[probe] {len(corpus)} problems x {len(models)} models = ${total_cost:.4f} real billed")
        print(f"[probe] est. full run ({full} problems): ~${per_model / max(len(corpus), 1) * full * len(models):.2f}")
        report(scores)
        return 0

    report(scores)
    if args.all:
        art = persist_metrics(scores, window)
        n = persist_baseline(scores, window)
        print(f"\n[coding-bench] persisted {n} measured priors -> model_task_baseline(code) + "
              f"model_coding_metrics + {art.name}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
