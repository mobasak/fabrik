#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/build_task_baselines.py scripts/kilo-benchmarks/rank_task_subagents.py scripts/kilo-benchmarks/rank_coding_subagents.py
"""Ground-truth code-REVIEW quality benchmark for the subagent pool — accuracy AND speed.

The flywheel scores `review` by our own 0-5 verdict on real runs — circular, and useless for
*ranking* a model's true catch-rate (a model can look good by flagging everything). This measures
review against GROUND TRUTH instead: a diff with a KNOWN planted defect, so we can check whether the
model actually found it — and, on clean controls, whether it stayed quiet.

Two numbers, both mandatory (precision is the whole game — a "flag everything" model has perfect
recall and zero worth):

    recall     = planted defects caught / total planted            (accuracy)
    precision  = 1 - (clean controls falsely flagged / controls)   (noise)
    score/5    = F1(recall, precision) * 5   -> model_task_baseline(task_type='review')

Composition (reuse, not reinvent — per the "use what we already have" call):
    corpus   <- deterministic AST mutation of self-contained victim functions, from the mutmut
                operator CLASSES actually implemented here: comparison flip (< <= > >= == !=),
                arithmetic swap (+ - *→//), and boolean and↔or. mutmut 3.x's own runner emits no
                standalone labeled diff, so we apply these operators directly — no test-runner
                coupling. (Negation-drop / is↔is-not are mutmut classes we do NOT yet mutate.)
    run      <- libs.subagents.run_agents + pick_models  (THE existing pool — single-shot read_only)
    persist  <- model_task_baseline (the build_task_baselines table) + the flywheel (record_agent_run)

Speed comes free from AgentResult.latency_s / out_tokens / cost_usd — reported per model.

Run:   python scripts/kilo-benchmarks/microbench_review.py --smoke        # 2 models x few items (~cents)
       python scripts/kilo-benchmarks/microbench_review.py --all          # whole pool, persist + flywheel
       python scripts/kilo-benchmarks/microbench_review.py --report       # print the stored baseline
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# --- reuse the existing pool + persistence layer -------------------------------------------------
REPO = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, REPO)
from build_task_baselines import DB_PATH, SCALE, ensure_table  # noqa: E402  (same table/DDL)
from libs.subagents import (  # noqa: E402
    AgentSpec,
    methodology,
    pick_models,
    record_agent_run,
    run_agents,
)

# =================================================================================================
# 1. CORPUS — self-contained victim functions (realistic, pure logic) + deterministic mutation.
#    Each victim is intentionally CORRECT; a mutant flips exactly one operator at a known line.
# =================================================================================================

VICTIMS: dict[str, str] = {
    "binary_search": """\
def binary_search(items, target):
    lo, hi = 0, len(items) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if items[mid] == target:
            return mid
        if items[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
""",
    "page_offset": """\
def page_offset(page, per_page):
    if page < 1:
        page = 1
    return (page - 1) * per_page
""",
    "retry_backoff": """\
def next_delay(attempt, base, cap):
    delay = base * (2 ** attempt)
    if delay > cap:
        delay = cap
    return delay
""",
    "running_avg": """\
def running_avg(total, count, value):
    count = count + 1
    total = total + value
    return total / count
""",
    "within_budget": """\
def within_budget(spent, incoming, limit):
    return spent + incoming <= limit
""",
    "is_expired": """\
def is_expired(now_ts, issued_ts, ttl):
    return now_ts - issued_ts >= ttl
""",
    "clamp": """\
def clamp(value, low, high):
    if value < low:
        return low
    if value > high:
        return high
    return value
""",
    "should_evict": """\
def should_evict(size, capacity, pinned):
    return size >= capacity and not pinned
""",
}

# operator-class flips (the mutmut operator families) -> (from, to, label)
_CMP_FLIP = {
    ast.Lt: (ast.LtE, "<->=<"),
    ast.LtE: (ast.Lt, "<=->,<"),
    ast.Gt: (ast.GtE, ">->=>"),
    ast.GtE: (ast.Gt, ">=->,>"),
    ast.Eq: (ast.NotEq, "==->!="),
    ast.NotEq: (ast.Eq, "!=->=="),
}
_BINOP_FLIP = {
    ast.Add: (ast.Sub, "+->-"),
    ast.Sub: (ast.Add, "-->+"),
    ast.Mult: (ast.FloorDiv, "*->//"),
}
_BOOL_FLIP = {ast.And: (ast.Or, "and->or"), ast.Or: (ast.And, "or->and")}


@dataclass
class Item:
    item_id: str
    victim: str
    numbered_code: str  # code with 1-based line numbers prefixed (the reviewer cites these)
    truth_line: int | None  # planted-defect line; None => clean control
    operator: str | None


def _number(code: str) -> str:
    return "\n".join(f"{i:>3}: {ln}" for i, ln in enumerate(code.splitlines(), 1))


def _mutants_for(name: str, src: str) -> list[Item]:
    """One mutant per flippable operator occurrence, each at its real (unparsed) line number."""
    tree = ast.parse(src)
    base_unparsed = ast.unparse(tree)  # the reviewer sees UNPARSED code — truth_line is keyed to it
    out: list[Item] = []
    seen: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        flip: tuple[type, str] | None = None
        target: ast.AST | None = None
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            flip = _CMP_FLIP.get(type(node.ops[0]))
            target = node.ops[0]
        elif isinstance(node, ast.BinOp):
            flip = _BINOP_FLIP.get(type(node.op))
            target = node.op
        elif isinstance(node, ast.BoolOp):
            flip = _BOOL_FLIP.get(type(node.op))
            target = node.op
        if not flip:
            continue
        line = getattr(node, "lineno", None)
        if line is None or (line, flip[1]) in seen:
            continue
        seen.add((line, flip[1]))
        new_tree = ast.parse(src)
        # re-walk the fresh tree to the same position and swap the operator in place
        _apply_flip(new_tree, line, type(target), flip[0])
        mutated = ast.unparse(new_tree)
        # truth_line MUST be the line the reviewer actually sees changed — i.e. the line in the
        # UNPARSED output, not the original-source lineno. They coincide for one-statement-per-line
        # victims, but any multi-line statement / continuation would drift and silently under-count
        # recall. Derive it by diffing unparsed-original vs mutant; skip the mutant if it isn't a
        # clean single-line change (ambiguous → don't ship a mislabeled item).
        base_lines = base_unparsed.splitlines()
        mut_lines = mutated.splitlines()
        diffs = [
            i + 1
            for i, (a, b) in enumerate(zip(base_lines, mut_lines, strict=False))
            if a.strip() != b.strip()
        ]
        if len(diffs) != 1 or len(base_lines) != len(mut_lines):
            continue
        out.append(
            Item(
                item_id=f"{name}:{diffs[0]}:{flip[1]}",
                victim=name,
                numbered_code=_number(mutated),
                truth_line=diffs[0],
                operator=flip[1],
            )
        )
    return out


def _apply_flip(tree: ast.AST, line: int, from_type: type, to_type: type) -> None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and getattr(node, "lineno", None) == line:
            for i, op in enumerate(node.ops):
                if isinstance(op, from_type):
                    node.ops[i] = to_type()
                    return
        if isinstance(node, ast.BinOp) and getattr(node, "lineno", None) == line:
            if isinstance(node.op, from_type):
                node.op = to_type()
                return
        if isinstance(node, ast.BoolOp) and getattr(node, "lineno", None) == line:
            if isinstance(node.op, from_type):
                node.op = to_type()
                return


def build_corpus() -> list[Item]:
    items: list[Item] = []
    for name, src in VICTIMS.items():
        items.extend(_mutants_for(name, src))
        # the un-mutated original is a CLEAN control (a finding here is a false positive).
        # Unparse it too, so it is byte-identical in FORMATTING to the mutants (only the operator
        # differs) — no reformatting "tell" that a model could use to guess mutant vs. control.
        items.append(
            Item(
                item_id=f"{name}:clean",
                victim=name,
                numbered_code=_number(ast.unparse(ast.parse(src))),
                truth_line=None,
                operator=None,
            )
        )
    return items


# =================================================================================================
# 2. DISPATCH via the existing pool + 3. GRADE
# =================================================================================================

_TASK = (
    "You are a code reviewer. The snippet below has line numbers prefixed as `N: `.\n"
    "It may contain AT MOST ONE bug (an operator that produces wrong output), or none.\n"
    'Return ONLY a JSON array of objects {{"line": <int>, "bug": "<short>"}} for lines you\n'
    "believe are buggy. If the code is correct, return exactly []. No prose, JSON only.\n\n"
    "```python\n{code}\n```"
)

_LINE_RE = re.compile(r'"line"\s*:\s*(\d+)')
_FALLBACK_RE = re.compile(r"\bline\s*#?\s*(\d+)\b", re.IGNORECASE)


def cited_lines(text: str) -> set[int]:
    """Lines the reviewer flagged — JSON first, regex fallback for models that ignore the format."""
    if not text:
        return set()
    for m in re.finditer(r"\[.*?\]", text, re.DOTALL):
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                got = {int(o["line"]) for o in arr if isinstance(o, dict) and "line" in o}
                if got or arr == []:
                    return got
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            continue
    return {int(x) for x in _LINE_RE.findall(text)} or {int(x) for x in _FALLBACK_RE.findall(text)}


def f1(recall: float, precision: float) -> float:
    return 0.0 if (recall + precision) == 0 else 2 * recall * precision / (recall + precision)


@dataclass
class ModelScore:
    model: str
    n_mut: int
    caught: int
    n_ctrl: int
    ctrl_flagged: int
    latencies: list[float]
    out_tokens: int
    cost: float
    n_err: int = (
        0  # calls that errored / returned empty — EXCLUDED from recall/precision, never a "miss"
    )
    out_price_mtok: float = (
        0.0  # the model's OpenRouter OUTPUT price, $/M tokens (static per model)
    )

    # A model is only measured if enough calls actually returned. A 404/timeout is not "missed every
    # bug" — scoring it 0 would poison the ranker into never picking a model we simply failed to reach.
    MIN_MEASURED_MUTANTS = 3
    # ...AND at least one CONTROL returned. precision is `1 - flagged/n_ctrl`, which defaults to a
    # vacuous 1.0 when n_ctrl==0 — so a model that emits empty content on every clean control (now
    # excluded) would clear the precision gate on ZERO evidence. Require ≥1 real control so precision
    # is never vacuous. (Kept at 1, not higher: `--smoke` runs only 2 victims = 2 controls, and a
    # model may legitimately error on some — a higher floor would render smoke-mode unmeasurable.)
    MIN_MEASURED_CONTROLS = 1

    @property
    def is_measured(self) -> bool:
        return self.n_mut >= self.MIN_MEASURED_MUTANTS and self.n_ctrl >= self.MIN_MEASURED_CONTROLS

    @property
    def recall(self) -> float:
        return self.caught / self.n_mut if self.n_mut else 0.0

    @property
    def precision(self) -> float:
        return 1 - (self.ctrl_flagged / self.n_ctrl) if self.n_ctrl else 1.0

    @property
    def score5(self) -> float:
        return round(f1(self.recall, self.precision) * SCALE, 3)

    @property
    def grade(self) -> str:
        """Letter grade for the correctness score (F1-based)."""
        s = self.score5
        for cut, g in (
            (4.5, "A+"),
            (4.0, "A"),
            (3.5, "B+"),
            (3.0, "B"),
            (2.5, "C+"),
            (2.0, "C"),
            (1.0, "D"),
        ):
            if s >= cut:
                return g
        return "F"

    @property
    def n_calls(self) -> int:
        return self.n_mut + self.n_ctrl

    @property
    def median_latency(self) -> float:
        s = sorted(x for x in self.latencies if x is not None)
        return s[len(s) // 2] if s else 0.0

    @property
    def tokens_per_s(self) -> float:
        """Aggregate output throughput — total tokens / total wall-clock across this model's calls."""
        total_t = sum(x for x in self.latencies if x is not None)
        return round(self.out_tokens / total_t, 1) if total_t else 0.0

    @property
    def cost_per_1k(self) -> float:
        """Cost normalized to $ per 1000 reviews — comparable across models of different verbosity."""
        return round(self.cost / self.n_calls * 1000, 4) if self.n_calls else 0.0


def run(models: list[str], corpus: list[Item], cost_cap: float, concurrency: int):
    specs, meta = [], []
    sys_prompt = methodology("review")
    for model in models:
        for it in corpus:
            specs.append(
                AgentSpec(
                    task=_TASK.format(code=it.numbered_code),
                    model=model,
                    system=sys_prompt,
                    task_type="review",
                    tools_enabled=False,
                    allow_ungrounded=True,
                    max_turns=1,
                    max_cost_usd=cost_cap,
                    wall_clock_s=120.0,
                )
            )
            meta.append((model, it))
    results = run_agents(specs, repo=REPO, max_concurrency=concurrency)
    return specs, meta, results


# --- Direct OpenRouter dispatch -----------------------------------------------------------------
# The pool (run_agents) adds a provider/parameter constraint that some models' endpoints reject with
# "No endpoints found that satisfy" (a 404) — even though the model answers a plain request fine. For
# a *benchmark* we must reach every model, so this path calls OpenRouter's chat/completions directly
# (the proven-reachable shape) with a generous token budget so reasoning-heavy models still emit a
# JSON answer after their reasoning. Same corpus, same grader => comparable grades.

_OR_URL = "https://openrouter.ai/api/v1/chat/completions"


class _DirectResult:
    """Duck-types the AgentResult fields grade()/record_flywheel read."""

    def __init__(
        self,
        model,
        text="",
        error=None,
        out_tokens=0,
        cost_usd=0.0,
        latency_s=None,
        out_price_mtok=0.0,
    ):
        import uuid

        self.agent_id = uuid.uuid4().hex
        self.model = model
        self.text = text
        self.error = error
        self.out_tokens = out_tokens
        self.cost_usd = cost_usd
        self.latency_s = latency_s
        self.out_price_mtok = out_price_mtok
        self.diff = ""
        self.provider = None
        self.turns = 1
        self.tool_calls: dict = {}


def _or_pricing() -> dict[str, tuple[float, float]]:
    """model_id -> ($/token prompt, $/token completion) from the live OR models list.

    Fail-soft: a network hiccup on the (once-per-run) models fetch returns {} rather than aborting
    the whole benchmark — cost then falls back to the per-call `usage.cost` (the primary source
    anyway) and `out_price_mtok` shows 0. One transient failure must not lose the entire run.
    """
    import urllib.error
    import urllib.request

    key = _require_key()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {key}"}
    )
    out: dict[str, tuple[float, float]] = {}
    try:
        data = json.load(urllib.request.urlopen(req, timeout=30))["data"]
    except (urllib.error.URLError, OSError, ValueError, KeyError) as exc:
        print(
            f"[review-bench] pricing fetch failed ({exc}); using usage.cost only", file=sys.stderr
        )
        return out
    for m in data:
        p = m.get("pricing") or {}
        try:
            out[m["id"]] = (float(p.get("prompt", 0)), float(p.get("completion", 0)))
        except (TypeError, ValueError):
            out[m["id"]] = (0.0, 0.0)
    return out


def _require_key() -> str:
    """Fetch the OpenRouter key with a clear message instead of a bare KeyError."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit(
            "OPENROUTER_API_KEY is not set — --direct mode needs it. Export it or add it to .env."
        )
    return key


def _direct_call(model: str, task: str, max_tokens: int, pricing: dict, timeout: float):
    import time
    import urllib.error
    import urllib.request

    key = _require_key()
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": task}],
            "max_tokens": max_tokens,
            "usage": {
                "include": True
            },  # ask OpenRouter to return the REAL billed cost (usage.cost)
        }
    ).encode()
    req = urllib.request.Request(
        _OR_URL,
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    try:
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        return _DirectResult(
            model,
            error=f"HTTP {e.code}: {e.read().decode()[:120]}",
            latency_s=time.monotonic() - t0,
        )
    except Exception as e:
        return _DirectResult(
            model, error=f"{type(e).__name__}: {str(e)[:120]}", latency_s=time.monotonic() - t0
        )
    lat = time.monotonic() - t0
    choices = r.get("choices") or []
    if not choices:
        return _DirectResult(model, error=f"no choices: {json.dumps(r)[:120]}", latency_s=lat)
    text = (choices[0].get("message") or {}).get("content") or ""
    usage = r.get("usage") or {}
    pt, ct = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    pp, cp = pricing.get(model, (0.0, 0.0))
    # REAL billed cost from OpenRouter (usage.cost) — authoritative $ actually charged, incl.
    # caching/BYOK/rounding/provider rate. Fall back to tokens×list-price only if a provider omits it.
    real_cost = usage.get("cost")
    cost = float(real_cost) if real_cost is not None else pt * pp + ct * cp
    return _DirectResult(
        model,
        text=text,
        out_tokens=ct,
        cost_usd=cost,
        latency_s=lat,
        out_price_mtok=round(cp * 1_000_000, 3),  # $/M list price, for reference vs. the real $/1k
    )


def run_direct(models, corpus, max_tokens: int, concurrency: int, timeout: float = 150.0):
    """Grade every model via a direct OR call — reaches models the pool 404s. Same (specs, meta, results)."""
    from concurrent.futures import ThreadPoolExecutor

    pricing = _or_pricing()
    sys_prompt = methodology("review")
    specs, meta, tasks = [], [], []
    for model in models:
        for it in corpus:
            task = f"{sys_prompt}\n\n{_TASK.format(code=it.numbered_code)}"
            specs.append(AgentSpec(task=task, model=model, task_type="review"))
            meta.append((model, it))
            tasks.append((model, task))
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        results = list(
            ex.map(lambda mt: _direct_call(mt[0], mt[1], max_tokens, pricing, timeout), tasks)
        )
    return specs, meta, results


def grade(specs, meta, results):
    """Aggregate per model; return (scores, per-run rows for the flywheel)."""
    by: dict[str, ModelScore] = {}
    rows = []
    for spec, (model, it), res in zip(specs, meta, results, strict=False):
        s = by.setdefault(model, ModelScore(model, 0, 0, 0, 0, [], 0, 0.0))
        # A failed dispatch is NOT a missed bug — exclude it from the denominators (counting it as
        # recall=0 is the poison the F-rows exposed). "Failed" = None, an API error, OR empty content:
        # the prompt demands a JSON answer (`[]` for clean), so EMPTY content is never a valid "no
        # bugs" — it means the model gave no usable answer (refused, or spent its whole budget on
        # reasoning tokens and emitted no content). Excluding on empty content regardless of token
        # count also covers the reasoning-only model that returns completion_tokens>0 but content="".
        errored = (
            res is None
            or bool(getattr(res, "error", None))
            or not (getattr(res, "text", None) or "").strip()
        )
        if errored:
            s.n_err += 1
            continue
        flagged = cited_lines(res.text or "")
        if res.latency_s is not None:
            s.latencies.append(res.latency_s)
        s.out_tokens += res.out_tokens or 0
        s.cost += res.cost_usd or 0.0
        if getattr(res, "out_price_mtok", 0.0):  # static per model — take from any successful call
            s.out_price_mtok = res.out_price_mtok
        if it.truth_line is None:  # clean control
            s.n_ctrl += 1
            s.ctrl_flagged += 1 if flagged else 0
        else:
            s.n_mut += 1
            s.caught += 1 if it.truth_line in flagged else 0
        rows.append((spec, res, it))  # only successful calls feed the flywheel
    return by, rows


def persist(scores: dict[str, ModelScore]) -> int:
    """Write each MEASURED model's review prior into model_task_baseline (same table as ops/code).

    Unmeasured models (mostly-errored dispatch) are skipped, never written as a 0 prior — an
    unreachable model must not be ranked as a terrible reviewer.
    """
    ensure_table(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    today = date.today().isoformat()
    written = 0
    try:
        for m, s in scores.items():
            if not s.is_measured:
                continue
            written += 1
            conn.execute(
                "INSERT OR REPLACE INTO model_task_baseline "
                "(model_id, task_type, baseline, pass_rate, n_tasks, n_trials, source, built_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    m,
                    "review",
                    s.score5,
                    round(s.recall, 4),
                    s.n_mut,
                    s.n_mut + s.n_ctrl,
                    "microbench_review:mutmut-ops+controls",
                    today,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    return written


def record_flywheel(rows) -> int:
    """One flywheel row per SUCCESSFUL run, scored by whether it got THIS item right (0 or 5).

    `grade()` already dropped errored calls from `rows`, so a 404/timeout never lands as a
    quality-0 flywheel row (which would teach the ranker the wrong thing).
    """
    n = 0
    for spec, res, it in rows:
        if res is None or getattr(res, "error", None):
            continue
        flagged = cited_lines(res.text or "")
        # `is not None`, not truthiness: a control is truth_line=None; a mutant's truth_line is a
        # real line number. (Line numbers are ≥1 today so truthiness happens to agree, but the
        # control predicate must match grade()'s `is None` to stay correct if that ever changes.)
        correct = (it.truth_line in flagged) if it.truth_line is not None else (not flagged)
        try:
            if record_agent_run(spec, res, quality_score=5.0 if correct else 0.0, project="review"):
                n += 1
        except Exception:  # flywheel is best-effort; a DB hiccup never fails the bench
            pass
    return n


def report(scores: dict[str, ModelScore]) -> None:
    """Three metric families side by side: CORRECTNESS | COST | SPEED — ranked by correctness.

    Only MEASURED models are ranked; models whose dispatch mostly errored are listed apart as
    UNMEASURED (never as an F — a 404 is not a review verdict).
    """
    measured = [s for s in scores.values() if s.is_measured]
    unmeasured = [s for s in scores.values() if not s.is_measured]
    print(f"\n{'':<32}{'|  CORRECTNESS':<26}{'|  COST':<26}{'|  SPEED':<16}")
    print(
        f"{'model':<32}{'grade':>6}{'/5':>6}{'rec':>6}{'prec':>6}  "
        f"{'out$/M':>8}{'$/1k':>8}  {'p50 s':>7}{'tok/s':>8}"
    )
    print("-" * 98)
    for s in sorted(measured, key=lambda x: (x.score5, -x.median_latency), reverse=True):
        err = f"  ({s.n_err} err)" if s.n_err else ""
        print(
            f"  {s.model[:29]:<30}{s.grade:>6}{s.score5:>6.2f}{s.recall * 100:>5.0f}%"
            f"{s.precision * 100:>5.0f}%  {s.out_price_mtok:>8.2f}{s.cost_per_1k:>8.3f}  "
            f"{s.median_latency:>7.1f}{s.tokens_per_s:>8.1f}{err}"
        )
    if unmeasured:
        print("\n  UNMEASURED (dispatch mostly errored — NOT scored; excluded from the ranker):")
        for s in unmeasured:
            print(f"    · {s.model:<40} {s.n_err} errored / {s.n_err + s.n_mut + s.n_ctrl} calls")
    print(
        "\n  CORRECTNESS grade = F1(recall, precision)·5  ·  COST out$/M = OpenRouter OUTPUT list "
        "price ($/M tokens), $/1k = REAL OpenRouter-billed cost (usage.cost) per 1000 reviews  ·  "
        "SPEED p50 = median call latency, tok/s = aggregate output throughput"
    )


def persist_metrics(scores: dict[str, ModelScore]) -> Path:
    """Durably store ALL three metric families (model_task_baseline holds only the correctness prior)."""
    ensure_table(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    today = date.today().isoformat()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS model_review_metrics (
                model_id TEXT NOT NULL, score5 REAL, grade TEXT, recall REAL, precision REAL,
                out_price_mtok REAL, cost_usd REAL, cost_per_1k REAL, p50_latency_s REAL,
                tokens_per_s REAL, n_mut INTEGER, n_ctrl INTEGER, built_at TEXT,
                PRIMARY KEY (model_id, built_at))
        """)
        for s in scores.values():
            if not s.is_measured:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO model_review_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    s.model,
                    s.score5,
                    s.grade,
                    round(s.recall, 4),
                    round(s.precision, 4),
                    s.out_price_mtok,
                    round(s.cost, 4),
                    s.cost_per_1k,
                    s.median_latency,
                    s.tokens_per_s,
                    s.n_mut,
                    s.n_ctrl,
                    today,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    art = Path(__file__).parent / f".microbench_cache/review_metrics_{today}.json"
    art.parent.mkdir(exist_ok=True)
    art.write_text(
        json.dumps(
            {
                s.model: {
                    "grade": s.grade,
                    "score5": s.score5,
                    "recall": round(s.recall, 4),
                    "precision": round(s.precision, 4),
                    "n_err": s.n_err,
                    "out_price_mtok": s.out_price_mtok,
                    "cost_usd": round(s.cost, 4),
                    "cost_per_1k": s.cost_per_1k,
                    "p50_latency_s": s.median_latency,
                    "tokens_per_s": s.tokens_per_s,
                }
                for s in scores.values()
                if s.is_measured
            },
            indent=2,
        )
    )
    return art


def report_stored() -> None:
    """Print the latest stored CORRECTNESS | COST | SPEED metrics (falls back to the prior table)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        has_metrics = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_review_metrics'"
        ).fetchone()
        if has_metrics:
            latest = conn.execute("SELECT MAX(built_at) FROM model_review_metrics").fetchone()[0]
            rows = conn.execute(
                "SELECT model_id, grade, score5, recall, precision, out_price_mtok, cost_per_1k, "
                "p50_latency_s, tokens_per_s FROM model_review_metrics WHERE built_at=? "
                "ORDER BY score5 DESC, p50_latency_s ASC",
                (latest,),
            ).fetchall()
            if rows:
                print(f"\n  stored review metrics ({latest}):")
                print(f"\n{'':<32}{'|  CORRECTNESS':<26}{'|  COST':<26}{'|  SPEED':<16}")
                print(
                    f"{'model':<32}{'grade':>6}{'/5':>6}{'rec':>6}{'prec':>6}  "
                    f"{'out$/M':>8}{'$/1k':>8}  {'p50 s':>7}{'tok/s':>8}"
                )
                print("-" * 98)
                for m, g, s5, rec, prec, opm, c1k, p50, tps in rows:
                    print(
                        f"  {m[:29]:<30}{g:>6}{s5:>6.2f}{rec * 100:>5.0f}%{prec * 100:>5.0f}%  "
                        f"{(opm or 0):>8.2f}{c1k:>8.3f}  {p50:>7.1f}{tps:>8.1f}"
                    )
                return
        rows = conn.execute(
            "SELECT model_id, baseline, pass_rate, n_trials, built_at FROM model_task_baseline "
            "WHERE task_type='review' ORDER BY baseline DESC"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        print("no stored review metrics — run with --all first")
        return
    print(f"\n{'model':<34}{'prior/5':>8}{'recall':>8}{'items':>7}{'built':>12}")
    print("-" * 70)
    for m, b, pr, n, built in rows:
        print(f"  {m[:31]:<34}{b:>7.2f}{pr * 100:>7.0f}%{n:>7}{built:>12}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="microbench_review")
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--smoke", action="store_true", help="2 models x 6 items — validate wiring (~cents)"
    )
    g.add_argument("--all", action="store_true", help="whole pool, persist prior + flywheel")
    g.add_argument("--report", action="store_true", help="print stored review baselines")
    p.add_argument("--models", nargs="*", help="explicit model ids (else pick_models)")
    p.add_argument("--n", type=int, default=24, help="pool size for --all (default 24)")
    p.add_argument(
        "--cost-cap", type=float, default=0.03, help="hard per-call $ cap (default 0.03)"
    )
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--persist", action="store_true", help="write model_task_baseline + flywheel")
    p.add_argument(
        "--direct",
        action="store_true",
        help="dispatch via a DIRECT OpenRouter call instead of the pool — reaches every model "
        "(the pool 404s some); required for a proper test of the full candidate list",
    )
    p.add_argument(
        "--max-tokens",
        type=int,
        default=2500,
        help="direct-mode output budget (reasoning headroom)",
    )
    args = p.parse_args(argv)

    if args.report:
        report_stored()
        return 0

    corpus = build_corpus()

    if args.smoke:
        models = args.models or pick_models("review", n=2)
        corpus = [i for i in corpus if i.victim in ("binary_search", "is_expired")]  # small slice
    else:
        models = args.models or pick_models("review", n=args.n)

    mode = "DIRECT-OR" if args.direct else "pool"
    print(
        f"[review-bench:{mode}] {len(models)} models x {len(corpus)} items "
        f"({sum(1 for i in corpus if i.truth_line is not None)} mutants + "
        f"{sum(1 for i in corpus if i.truth_line is None)} controls) "
        f"= {len(models) * len(corpus)} calls",
        file=sys.stderr,
    )

    if args.direct:
        specs, meta, results = run_direct(models, corpus, args.max_tokens, args.concurrency)
    else:
        specs, meta, results = run(models, corpus, args.cost_cap, args.concurrency)
    scores, rows = grade(specs, meta, results)
    report(scores)

    if args.persist or args.all:
        n = persist(scores)
        art = persist_metrics(scores)
        fw = record_flywheel(rows)
        print(
            f"\n[review-bench] persisted {n} correctness priors -> model_task_baseline(review); "
            f"cost+speed -> model_review_metrics + {art.name}; {fw} flywheel rows",
            file=sys.stderr,
        )
    else:
        print(
            "\n[review-bench] dry (no persist) — add --persist to write the prior + flywheel",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
