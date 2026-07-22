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
# 1b. HARD CORPUS — hand-planted single-line logic bugs in realistic functions (--hard mode).
#
# Why it exists: per-item probing (2026-07-23) proved the operator-flip corpus has almost no
# resolution at the frontier — of its 22 mutants, 15 are caught by EVERY strong model, 6 by NONE,
# and exactly 1 discriminates. Frontier tiers (claude-code/*, top OR models) therefore tie at the
# same score regardless of capability. These items target the band a stronger reviewer separates
# on: stateful traces, stdlib semantics (sort stability, OrderedDict, setdefault), contract-vs-code
# reading, and placement bugs — not "spot the flipped operator in five lines".
#
# Soundness rules (each one is a lesson bought this week — see LESSONS_LEARNT 82 + the equivalent-
# mutant incident):
#   * Every buggy/clean pair differs on EXACTLY ONE line (rstrip-compared, so an indent-placement
#     bug counts) — build_hard_corpus() derives truth_line from that diff and fails loud otherwise.
#   * Every bug is KILL-PROVEN: `probes` are concrete inputs on which buggy != clean, executed by
#     tests (test_microbench_review.py) — never certified by eye.
#   * Ground truth is OBJECTIVE: each function's docstring states its contract; the bug violates
#     the docstring, so "is this a bug?" never depends on the reviewer guessing intent.
#   * Each snippet has exactly ONE top-level function (probes call it; tests rely on it).
#
# --hard NEVER touches the standard corpus, model_review_metrics, model_task_baseline, or the
# flywheel — it persists to its own table (model_review_hard_metrics) so the established 61-model
# baseline stays untouched and comparable.
# =================================================================================================

HARD_CASES: list[dict] = [
    {
        "name": "batch_records",
        "clean": '''\
def batch_records(records, size):
    """Group records into consecutive batches of `size`, preserving order.
    The final PARTIAL batch (fewer than `size` records) is included too."""
    batches = []
    batch = []
    for r in records:
        batch.append(r)
        if len(batch) == size:
            batches.append(batch)
            batch = []
    if batch:
        batches.append(batch)
    return batches
''',
        "buggy": '''\
def batch_records(records, size):
    """Group records into consecutive batches of `size`, preserving order.
    The final PARTIAL batch (fewer than `size` records) is included too."""
    batches = []
    batch = []
    for r in records:
        batch.append(r)
        if len(batch) == size:
            batches.append(batch)
            batch = []
    if batches:
        batches.append(batch)
    return batches
''',
        "probes": [([1, 2], 5), ([1, 2, 3], 3), ([1, 2, 3, 4], 3)],
    },
    {
        "name": "max_window_sum",
        "clean": '''\
def max_window_sum(xs, k):
    """Maximum sum over any contiguous window of EXACTLY k elements.
    xs always has at least k elements; values may be negative."""
    cur = sum(xs[:k])
    best = cur
    for i in range(k, len(xs)):
        cur += xs[i] - xs[i - k]
        if cur > best:
            best = cur
    return best
''',
        "buggy": '''\
def max_window_sum(xs, k):
    """Maximum sum over any contiguous window of EXACTLY k elements.
    xs always has at least k elements; values may be negative."""
    cur = sum(xs[:k])
    best = 0
    for i in range(k, len(xs)):
        cur += xs[i] - xs[i - k]
        if cur > best:
            best = cur
    return best
''',
        "probes": [([-3, -1, -2], 2), ([9, 1, 1], 2), ([1, 2, 3], 2)],
    },
    {
        "name": "merge_intervals",
        "clean": '''\
def merge_intervals(intervals):
    """Merge overlapping (start, end) intervals, start <= end. Intervals that
    merely TOUCH (one's end == the next one's start) merge as well."""
    ordered = sorted(intervals)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return [tuple(pair) for pair in merged]
''',
        "buggy": '''\
def merge_intervals(intervals):
    """Merge overlapping (start, end) intervals, start <= end. Intervals that
    merely TOUCH (one's end == the next one's start) merge as well."""
    ordered = sorted(intervals)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start < merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return [tuple(pair) for pair in merged]
''',
        "probes": [([(1, 3), (3, 5)],), ([(1, 4), (2, 6)],), ([(1, 2), (5, 6)],)],
    },
    {
        "name": "try_consume",
        "clean": '''\
def try_consume(tokens, capacity, elapsed_s, rate_per_s, cost):
    """Refill a token bucket, then try to spend `cost` tokens. Refill adds
    elapsed_s * rate_per_s tokens, capped at `capacity`. If the refilled balance
    COVERS the cost (balance >= cost), consume it and return (True, remaining);
    otherwise consume nothing and return (False, refilled_balance)."""
    refilled = tokens + elapsed_s * rate_per_s
    if refilled > capacity:
        refilled = capacity
    if refilled >= cost:
        return (True, refilled - cost)
    return (False, refilled)
''',
        "buggy": '''\
def try_consume(tokens, capacity, elapsed_s, rate_per_s, cost):
    """Refill a token bucket, then try to spend `cost` tokens. Refill adds
    elapsed_s * rate_per_s tokens, capped at `capacity`. If the refilled balance
    COVERS the cost (balance >= cost), consume it and return (True, remaining);
    otherwise consume nothing and return (False, refilled_balance)."""
    refilled = tokens + elapsed_s * rate_per_s
    if refilled > capacity:
        refilled = capacity
    if refilled > cost:
        return (True, refilled - cost)
    return (False, refilled)
''',
        "probes": [(0, 10, 5, 1, 5), (0, 10, 20, 1, 3), (2, 10, 1, 1, 9)],
    },
    {
        "name": "top_n",
        "clean": '''\
def top_n(scored, n):
    """Return the n highest-scoring (score, name) pairs, highest score first.
    Pairs with EQUAL scores keep their original relative order from `scored`
    (i.e. the ranking is stable)."""
    ranked = sorted(scored, key=lambda pair: -pair[0])
    return ranked[:n]
''',
        "buggy": '''\
def top_n(scored, n):
    """Return the n highest-scoring (score, name) pairs, highest score first.
    Pairs with EQUAL scores keep their original relative order from `scored`
    (i.e. the ranking is stable)."""
    ranked = sorted(scored, key=lambda pair: (-pair[0], pair[1]))
    return ranked[:n]
''',
        "probes": [
            ([(5, "b"), (5, "a")], 2),
            ([(3, "x"), (7, "y")], 1),
            ([(2, "z"), (2, "y"), (9, "a")], 3),
        ],
    },
    {
        "name": "lru_trace",
        "clean": '''\
def lru_trace(capacity, ops):
    """Simulate an LRU cache of the given capacity over `ops`; return
    (get_results, final_keys_oldest_first). Each op is ("put", key, value) or
    ("get", key). A GET on a present key returns its value and marks that key
    the MOST recently used; a miss returns None. A put that exceeds capacity
    evicts the LEAST recently used key."""
    from collections import OrderedDict
    cache = OrderedDict()
    results = []
    for op in ops:
        if op[0] == "put":
            _, key, value = op
            if key in cache:
                cache.move_to_end(key)
            cache[key] = value
            if len(cache) > capacity:
                cache.popitem(last=False)
        else:
            _, key = op
            if key in cache:
                cache.move_to_end(key)
                results.append(cache[key])
            else:
                results.append(None)
    return (results, list(cache))
''',
        "buggy": '''\
def lru_trace(capacity, ops):
    """Simulate an LRU cache of the given capacity over `ops`; return
    (get_results, final_keys_oldest_first). Each op is ("put", key, value) or
    ("get", key). A GET on a present key returns its value and marks that key
    the MOST recently used; a miss returns None. A put that exceeds capacity
    evicts the LEAST recently used key."""
    from collections import OrderedDict
    cache = OrderedDict()
    results = []
    for op in ops:
        if op[0] == "put":
            _, key, value = op
            if key in cache:
                cache.move_to_end(key)
            cache[key] = value
            if len(cache) > capacity:
                cache.popitem(last=False)
        else:
            _, key = op
            if key in cache:
                cache.move_to_end(key, last=False)
                results.append(cache[key])
            else:
                results.append(None)
    return (results, list(cache))
''',
        "probes": [
            (
                2,
                [
                    ("put", "a", 1),
                    ("put", "b", 2),
                    ("get", "a"),
                    ("put", "c", 3),
                    ("get", "a"),
                    ("get", "b"),
                    ("get", "c"),
                ],
            ),
        ],
    },
    {
        "name": "p95",
        "clean": '''\
def p95(sorted_vals):
    """95th percentile of a non-empty ASCENDING-sorted list, by the nearest-rank
    method: the value at 1-based rank ceil(0.95 * n), never below rank 1."""
    import math
    n = len(sorted_vals)
    rank = math.ceil(0.95 * n)
    if rank < 1:
        rank = 1
    return sorted_vals[rank - 1]
''',
        "buggy": '''\
def p95(sorted_vals):
    """95th percentile of a non-empty ASCENDING-sorted list, by the nearest-rank
    method: the value at 1-based rank ceil(0.95 * n), never below rank 1."""
    import math
    n = len(sorted_vals)
    rank = int(0.95 * n)
    if rank < 1:
        rank = 1
    return sorted_vals[rank - 1]
''',
        "probes": [(list(range(1, 11)),), (list(range(1, 21)),), ([7],)],
    },
    {
        "name": "latest_by_key",
        "clean": '''\
def latest_by_key(pairs):
    """Collapse (key, value) pairs into a dict mapping each key to its LATEST
    value (the last occurrence in `pairs` wins). Keys keep the order of their
    first appearance."""
    latest = {}
    for key, value in pairs:
        latest[key] = value
    return latest
''',
        "buggy": '''\
def latest_by_key(pairs):
    """Collapse (key, value) pairs into a dict mapping each key to its LATEST
    value (the last occurrence in `pairs` wins). Keys keep the order of their
    first appearance."""
    latest = {}
    for key, value in pairs:
        latest.setdefault(key, value)
    return latest
''',
        "probes": [([("a", 1), ("b", 2), ("a", 3)],), ([("x", 9)],)],
    },
    {
        "name": "get_setting",
        "clean": '''\
def get_setting(config, key, default):
    """Return the stored value for `key` — INCLUDING falsy stored values such
    as 0, "" or False. Only a genuinely MISSING key falls back to `default`."""
    if key in config:
        return config[key]
    return default
''',
        "buggy": '''\
def get_setting(config, key, default):
    """Return the stored value for `key` — INCLUDING falsy stored values such
    as 0, "" or False. Only a genuinely MISSING key falls back to `default`."""
    if key in config:
        return config[key] or default
    return default
''',
        "probes": [({"a": 0}, "a", 42), ({"a": 7}, "a", 42), ({}, "a", 42)],
    },
    {
        "name": "throttle",
        "clean": '''\
def throttle(times, window):
    """Filter ascending event timestamps: an event is KEPT iff it is at least
    `window` seconds after the most recent KEPT event. The first event is
    always kept. Dropped events do NOT reset the window."""
    kept = [times[0]]
    last_kept = times[0]
    for t in times[1:]:
        if t - last_kept >= window:
            kept.append(t)
            last_kept = t
    return kept
''',
        "buggy": '''\
def throttle(times, window):
    """Filter ascending event timestamps: an event is KEPT iff it is at least
    `window` seconds after the most recent KEPT event. The first event is
    always kept. Dropped events do NOT reset the window."""
    kept = [times[0]]
    last_kept = times[0]
    for t in times[1:]:
        if t - last_kept >= window:
            kept.append(t)
        last_kept = t
    return kept
''',
        "probes": [([0, 5, 10], 8), ([0, 10, 20], 8), ([0, 1, 2, 3], 10)],
    },
]

HARD_TABLE = "model_review_hard_metrics"
# The ONLY tables persist_metrics/_measured_review_models may touch. Their SQL interpolates the table
# name (sqlite can't parametrize identifiers), so membership here is ENFORCED at the top of both
# functions — the "internal allowlist" is a real check, not a comment (review finding, 2026-07-23).
_METRICS_TABLES = frozenset({"model_review_metrics", HARD_TABLE})


def _hard_truth_line(clean: str, buggy: str) -> int:
    """The single line (1-based) where buggy differs from clean — rstrip-compared, so a placement
    (indent) bug counts as the changed line. Raises if the pair isn't an exactly-one-line diff:
    a mislabeled item must never ship (the ground truth IS this diff)."""
    c_lines, b_lines = clean.splitlines(), buggy.splitlines()
    if len(c_lines) != len(b_lines):
        raise ValueError("hard case clean/buggy line counts differ — cannot derive truth_line")
    diffs = [
        i + 1
        for i, (a, b) in enumerate(zip(c_lines, b_lines, strict=True))
        if a.rstrip() != b.rstrip()
    ]
    if len(diffs) != 1:
        raise ValueError(f"hard case must differ on exactly one line, got {diffs}")
    return diffs[0]


def _kill_proven(case: dict) -> bool:
    """True iff at least one probe input produces a DIFFERENT outcome from buggy vs clean.

    Runtime enforcement of the corpus's core soundness property — an unkillable item (the defect
    class that invalidated the operator-flip corpus) must never be DISPATCHED, not merely fail a
    test that may not have run. Cases are small pure functions; executing every probe costs ms."""
    import ast as _ast

    def _fn(src: str):
        tree = _ast.parse(src)
        fns = [n for n in tree.body if isinstance(n, _ast.FunctionDef)]
        if len(fns) != 1:  # fail loud with the module's own contract message, not a bare IndexError
            raise ValueError(
                f"hard case snippet must define exactly ONE top-level function, got {len(fns)}"
            )
        ns: dict = {}
        exec(compile(src, "<hard-case>", "exec"), ns)  # noqa: S102 — fixed in-repo corpus source
        return ns[fns[0].name]

    clean_fn, buggy_fn = _fn(case["clean"]), _fn(case["buggy"])
    for args in case["probes"]:
        try:
            c = ("OK", clean_fn(*args))
        except Exception as e:  # noqa: BLE001 — outcome comparison
            c = ("EXC", type(e).__name__)
        try:
            b = ("OK", buggy_fn(*args))
        except Exception as e:  # noqa: BLE001
            b = ("EXC", type(e).__name__)
        if c != b:
            return True
    return False


def build_hard_corpus() -> list[Item]:
    """10 hand-planted single-line bugs + 10 clean controls (the fixed versions, same formatting —
    no reformatting tell). truth_line is DERIVED from the clean/buggy diff, never hand-labeled,
    and every case's killability is EXECUTED at build (fail loud, never ship an unkillable item)."""
    items: list[Item] = []
    for case in HARD_CASES:
        if not _kill_proven(case):
            raise ValueError(
                f"hard case {case['name']!r} is not kill-proven: no probe distinguishes buggy "
                "from clean — an unkillable item must never be dispatched"
            )
        line = _hard_truth_line(case["clean"], case["buggy"])
        items.append(
            Item(
                item_id=f"hard:{case['name']}:{line}",
                victim=case["name"],
                numbered_code=_number(case["buggy"]),
                truth_line=line,
                operator="hand-planted",
            )
        )
        items.append(
            Item(
                item_id=f"hard:{case['name']}:clean",
                victim=case["name"],
                numbered_code=_number(case["clean"]),
                truth_line=None,
                operator=None,
            )
        )
    return items


# =================================================================================================
# 2. DISPATCH via the existing pool + 3. GRADE
# =================================================================================================

_TASK_HARD = (
    "You are a code reviewer. The snippet below has line numbers prefixed as `N: `.\n"
    "The function's docstring states its intended CONTRACT. The implementation may contain\n"
    "AT MOST ONE single-line logic bug that makes it violate that contract, or none.\n"
    'Return ONLY a JSON array of objects {{"line": <int>, "bug": "<short>"}} for lines you\n'
    "believe are buggy. If the code is correct, return exactly []. No prose, JSON only.\n\n"
    "```python\n{code}\n```"
)


def _task_for(it: Item) -> str:
    """Per-item prompt: hard items describe a docstring-contract logic bug, standard items an
    operator flip. Same JSON answer contract either way — grade() is corpus-agnostic."""
    # getattr: dispatch tests use minimal duck-typed Item stubs that may omit item_id.
    tmpl = _TASK_HARD if getattr(it, "item_id", "").startswith("hard:") else _TASK
    return tmpl.format(code=it.numbered_code)


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
    # Raw per-type tokens (claude-code/* only — the OR path never populates these). Needed to compute
    # ② (derive_cost.amortized_cost) — a real subscription-derived $, NOT a list-price valuation.
    in_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

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
                    task=_task_for(it),
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
        in_tokens=0,
        cache_read_tokens=0,
        cache_creation_tokens=0,
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
        # raw per-type tokens (claude-code/* only — the OR path never populates these) — the input
        # ② (real amortized $) needs, since it's a token-volume figure, not a list-price valuation.
        self.in_tokens = in_tokens
        self.cache_read_tokens = cache_read_tokens
        self.cache_creation_tokens = cache_creation_tokens
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


def _claude_p_direct(model: str, task: str, timeout: float):
    """Dispatch a claude-code/* review via the single-shot shim; build a _DirectResult (cost_usd = ① api_equiv).

    `task` (methodology + code) is passed as the shim's PROMPT with system="" — transport parity with the
    OpenRouter user-only call (`_direct_call` sends the same task as one user message, no system). A failed
    claude -p call becomes this model's error (like a failed OR call), never fatal.
    """
    import time

    import claude_p
    import derive_cost

    t0 = time.monotonic()
    try:
        text, usage = claude_p.claude_p_call(model, task, system="", timeout=timeout)
        cost = derive_cost.api_equiv(
            usage, model
        )  # ① — inside try: an unpriced model becomes an error
        out_price = derive_cost.out_price_mtok(
            model
        )  # result, NOT a KeyError that crashes the whole run
    except Exception as e:  # noqa: BLE001 — a failed claude -p call is that model's error, not fatal
        return _DirectResult(
            model, error=f"{type(e).__name__}: {str(e)[:120]}", latency_s=time.monotonic() - t0
        )
    lat = time.monotonic() - t0
    return _DirectResult(
        model,
        text=text,
        out_tokens=usage["output_tokens"],
        cost_usd=cost,  # ① the ranking axis
        latency_s=lat,
        out_price_mtok=out_price,
        in_tokens=usage["input_tokens"],
        cache_read_tokens=usage["cache_read_input_tokens"],
        cache_creation_tokens=usage["cache_creation_input_tokens"],
    )


def run_direct(models, corpus, max_tokens: int, concurrency: int, timeout: float = 150.0):
    """Grade every model via a direct OR call — reaches models the pool 404s. Same (specs, meta, results).

    A `claude-code/*` model routes to the single-shot `claude -p` shim instead of the OR call (same
    _DirectResult shape, same grader). When any claude-code/* tier is scored the run is capped to low
    concurrency (they share the rotation quota) and the ②/③ cost sidecar is written for the ranker preamble.
    """
    from concurrent.futures import ThreadPoolExecutor

    import derive_cost

    # Only the OR path needs pricing/creds; a pure claude-code/* run bills the subscription (no OR key).
    pricing = _or_pricing() if any(not m.startswith("claude-code/") for m in models) else {}
    sys_prompt = methodology("review")
    specs, meta, tasks = [], [], []
    for model in models:
        for it in corpus:
            task = f"{sys_prompt}\n\n{_task_for(it)}"
            specs.append(AgentSpec(task=task, model=model, task_type="review"))
            meta.append((model, it))
            tasks.append((model, task))

    has_claude = any(m.startswith("claude-code/") for m in models)
    if has_claude:
        # conc=1: 2+ concurrent `claude -p` subprocesses can race the shared account-rotation state
        # (a separate risk from quota consumption). conc=1 doesn't protect against an UNRELATED process
        # sharing the same rotated account concurrently — that's outside this harness's control — but it
        # does eliminate the self-inflicted 2-way race between this run's own dispatches.
        concurrency = min(concurrency, 1)
    q_before = derive_cost.quota_snapshot() if has_claude else None

    def _dispatch(mt):
        model, task = mt
        if model.startswith("claude-code/"):
            return _claude_p_direct(model, task, timeout)
        return _direct_call(model, task, max_tokens, pricing, timeout)

    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        results = list(ex.map(_dispatch, tasks))
    if has_claude:  # ②/③ sidecar for the ranker preamble
        derive_cost.write_cost_sidecar(q_before, derive_cost.quota_snapshot())
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
        s.in_tokens += getattr(res, "in_tokens", 0) or 0
        s.cache_read_tokens += getattr(res, "cache_read_tokens", 0) or 0
        s.cache_creation_tokens += getattr(res, "cache_creation_tokens", 0) or 0
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
        # claude-code/* are spawn-native, NOT pool workers — never record them to the shared postgres
        # subagent_runs table. It is the fleet routing source rank_task_subagents aggregates, so a claude
        # row there would surface in `### review` and make pick_models return an id the pool 404s on. Their
        # scores live in model_review_metrics (display-only) — the coding path records nothing here either.
        if spec.model.startswith("claude-code/"):
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
    # ② is a run TOTAL (not a per-1k/per-M RATE like its neighbors) — "②total$", never "②$/run", so it
    # can't visually read as another rate column beside $/1k and out$/M (the label collision a review
    # caught: two numbers differing by ~6 orders of magnitude under one loose "rate-shaped" header).
    print(f"\n{'':<32}{'|  CORRECTNESS':<26}{'|  COST (① rate / ② total)':<34}{'|  SPEED':<16}")
    print(
        f"{'model':<32}{'grade':>6}{'/5':>6}{'rec':>6}{'prec':>6}  "
        f"{'out$/M':>8}{'$/1k':>8}{'②total$':>10}  {'p50 s':>7}{'tok/s':>8}"
    )
    print("-" * 106)
    for s in sorted(measured, key=lambda x: (x.score5, -x.median_latency), reverse=True):
        err = f"  ({s.n_err} err)" if s.n_err else ""
        amort = f"${_amortized_cost_for(s):.6f}" if s.model.startswith("claude-code/") else "—"
        print(
            f"  {s.model[:29]:<30}{s.grade:>6}{s.score5:>6.2f}{s.recall * 100:>5.0f}%"
            f"{s.precision * 100:>5.0f}%  {s.out_price_mtok:>8.2f}{s.cost_per_1k:>8.3f}{amort:>10}  "
            f"{s.median_latency:>7.1f}{s.tokens_per_s:>8.1f}{err}"
        )
    if unmeasured:
        print("\n  UNMEASURED (dispatch mostly errored — NOT scored; excluded from the ranker):")
        for s in unmeasured:
            print(f"    · {s.model:<40} {s.n_err} errored / {s.n_err + s.n_mut + s.n_ctrl} calls")
    print(
        "\n  CORRECTNESS grade = F1(recall, precision)·5  ·  COST out$/M = OpenRouter OUTPUT list "
        "price ($/M tokens), $/1k = REAL OpenRouter-billed cost (usage.cost) per 1000 reviews (① "
        "API-equivalent for claude-code/*, a RATE) · ②total$ = REAL subscription-derived $ (claude-code/* "
        "only — amortized_rate × this run's OWN tokens, a lump-SUM for the whole measured run, NOT a "
        "rate — expect it many orders of magnitude below $/1k; '—' for OR rows, which already show real "
        "billed cost via $/1k)  ·  SPEED p50 = median call latency, tok/s = aggregate output throughput"
    )


def _measured_review_models(
    db_path: Path = DB_PATH, table: str = "model_review_metrics"
) -> set[str]:
    """Models already measured TODAY in the given metrics table — for RESUME (skip re-dispatching/
    paying for a model whose score already landed). Mirrors microbench_coding_direct._measured_models;
    review has no versioned corpus window (a fixed corpus per table), so "already measured" = built_at
    == today. `table` separates the standard corpus (model_review_metrics) from --hard (HARD_TABLE) —
    a hard run must never be resume-skipped because the STANDARD run already measured that model today.
    Fail-soft empty set if the table doesn't exist yet (first-ever run)."""
    if table not in _METRICS_TABLES:  # enforced allowlist — the f-string SQL below interpolates it
        raise ValueError(f"unknown metrics table {table!r}; allowed: {sorted(_METRICS_TABLES)}")
    conn = sqlite3.connect(db_path)
    try:
        if not conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone():
            return set()
        today = date.today().isoformat()
        return {
            r[0]
            for r in conn.execute(
                f"SELECT DISTINCT model_id FROM {table} WHERE built_at=?",
                (today,),  # noqa: S608 — table from a fixed internal allowlist, never user input
            ).fetchall()
        }
    finally:
        conn.close()


def _amortized_cost_for(s: ModelScore) -> float:
    """② real subscription-derived $ for this model's measured run (claude-code/* only)."""
    import derive_cost

    usage = {
        "input_tokens": s.in_tokens,
        "output_tokens": s.out_tokens,
        "cache_read_input_tokens": s.cache_read_tokens,
        "cache_creation_input_tokens": s.cache_creation_tokens,
    }
    return derive_cost.amortized_cost(usage)


def persist_metrics(scores: dict[str, ModelScore], table: str = "model_review_metrics") -> Path:
    """Durably store ALL three metric families (model_task_baseline holds only the correctness prior).

    `table` routes --hard runs to their own table (HARD_TABLE) so the standard 61-model baseline in
    model_review_metrics is never mixed with hard-corpus rows (different corpus => not comparable)."""
    if table not in _METRICS_TABLES:  # enforced allowlist — the f-string SQL below interpolates it
        raise ValueError(f"unknown metrics table {table!r}; allowed: {sorted(_METRICS_TABLES)}")
    ensure_table(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    today = date.today().isoformat()
    try:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                model_id TEXT NOT NULL, score5 REAL, grade TEXT, recall REAL, precision REAL,
                out_price_mtok REAL, cost_usd REAL, cost_per_1k REAL, p50_latency_s REAL,
                tokens_per_s REAL, n_mut INTEGER, n_ctrl INTEGER, built_at TEXT,
                PRIMARY KEY (model_id, built_at))
        """)
        # Migration: raw per-type tokens (claude-code/* only) — needed for ② (derive_cost.amortized_cost),
        # a REAL subscription-derived $, distinct from ① (the list-price valuation already in cost_usd).
        # ALTER, not a schema rewrite — the table may already hold rows from before this column existed.
        existing_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col in ("in_tokens", "out_tokens_total", "cache_read_tokens", "cache_creation_tokens"):
            if col not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} INTEGER")
                except sqlite3.OperationalError as e:
                    # PRAGMA-check-then-ALTER isn't atomic: two genuinely-simultaneous invocations
                    # could both see the column missing and both ALTER — the second hits "duplicate
                    # column name" (the column already exists by then, harmlessly). Any OTHER
                    # OperationalError is a real problem and must still raise.
                    if "duplicate column name" not in str(e):
                        raise
        for s in scores.values():
            if not s.is_measured:
                continue
            conn.execute(
                f"INSERT OR REPLACE INTO {table} "  # noqa: S608 — table from a fixed internal allowlist, never user input
                "(model_id, score5, grade, recall, precision, out_price_mtok, cost_usd, cost_per_1k, "
                "p50_latency_s, tokens_per_s, n_mut, n_ctrl, built_at, "
                "in_tokens, out_tokens_total, cache_read_tokens, cache_creation_tokens) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
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
                    s.in_tokens,
                    s.out_tokens,
                    s.cache_read_tokens,
                    s.cache_creation_tokens,
                ),
            )
        conn.commit()
    finally:
        conn.close()
    stem = "review_hard_metrics" if table == HARD_TABLE else "review_metrics"
    art = Path(__file__).parent / f".microbench_cache/{stem}_{today}.json"
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
                    # ② real subscription-derived $ (only meaningful for claude-code/*; 0 for OR rows
                    # since they never populate in_tokens/cache_*).
                    "amortized_cost_usd": (
                        round(_amortized_cost_for(s), 6)
                        if s.model.startswith("claude-code/")
                        else None
                    ),
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
    p.add_argument(
        "--fresh",
        action="store_true",
        help="re-measure every model even if already measured today (default: RESUME — skip a model "
        "whose score already landed, e.g. after a quota-hit mid-run; safe because this harness is "
        "operator-triggered only, never in daily_refresh.sh)",
    )
    p.add_argument(
        "--hard",
        action="store_true",
        help="use the HARD corpus (10 hand-planted subtle logic bugs + 10 clean controls, "
        "kill-proven by differential tests) instead of the operator-flip corpus. Persists to "
        f"{HARD_TABLE} ONLY — never touches model_review_metrics, model_task_baseline, or the "
        "flywheel, so the established standard-corpus baseline stays untouched and comparable. "
        "A diagnostic instrument for separating frontier models the standard corpus ties.",
    )
    args = p.parse_args(argv)

    if args.report:
        if args.hard:
            # fail loud: report_stored() reads ONLY the standard tables (model_review_metrics /
            # model_task_baseline) — silently printing standard-corpus numbers for a --hard ask
            # would misrepresent which corpus they came from. Hard results render in
            # rank_task_subagents' TASK_SUBAGENT_SELECTION.md hard table.
            p.error(
                "--report does not support --hard (it reads the standard tables only); "
                "hard results render in docs/reference/kilo/TASK_SUBAGENT_SELECTION.md"
            )
        report_stored()
        return 0

    # `--models` with ZERO values ([] is falsy) must NOT silently fall through to the full
    # pick_models pool — an explicit-but-empty list dispatches nothing, not 24 models.
    def _models_or_pool(n: int) -> list[str]:
        return args.models if args.models is not None else pick_models("review", n=n)

    if args.hard:
        if args.smoke:
            # fail loud, not expensive: silently ignoring --smoke here would dispatch the FULL
            # pool (n=24) x 20 items = 480 live calls when the operator asked for a cheap slice.
            p.error("--smoke does not apply to --hard (different corpus); use --models to narrow")
        corpus = build_hard_corpus()
        models = _models_or_pool(args.n)
    else:
        corpus = build_corpus()
        if args.smoke:
            models = _models_or_pool(2)
            corpus = [
                i for i in corpus if i.victim in ("binary_search", "is_expired")
            ]  # small slice
        else:
            models = _models_or_pool(args.n)
    if not models:
        print(
            "[review-bench] --models given with no values — nothing to dispatch.", file=sys.stderr
        )
        return 0

    metrics_table = HARD_TABLE if args.hard else "model_review_metrics"
    if not args.fresh:
        done = _measured_review_models(table=metrics_table)
        skip = [m for m in models if m in done]
        if skip:
            models = [m for m in models if m not in done]
            print(
                f"[review-bench] resume: {len(skip)} model(s) already measured today — skipping "
                f"({', '.join(skip)}); {len(models)} to go (--fresh to re-measure all)",
                file=sys.stderr,
            )
        if not models:
            print(
                "[review-bench] nothing to do — every requested model was already measured today.",
                file=sys.stderr,
            )
            return 0

    mode = ("HARD:" if args.hard else "") + ("DIRECT-OR" if args.direct else "pool")
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
        if args.hard:
            # HARD mode is a diagnostic: metrics table only. Never the routing prior
            # (model_task_baseline) and never the flywheel — different corpus, not comparable
            # with (and must not contaminate) anything the standard corpus feeds.
            art = persist_metrics(scores, table=HARD_TABLE)
            print(
                f"\n[review-bench] HARD corpus: persisted cost+speed+correctness -> {HARD_TABLE} + "
                f"{art.name}; baseline prior + flywheel SKIPPED by design (diagnostic, non-routing)",
                file=sys.stderr,
            )
        else:
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
