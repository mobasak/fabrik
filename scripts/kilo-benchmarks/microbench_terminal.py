#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_microbench_terminal.py docs/reference/terminal-bench-runner.md
"""Home-run Terminal-Bench (Linux-sysadmin capability) scoring for OpenRouter models.

Sibling of ``microbench_coding.py`` — where that runs EvalPlus and writes
``humaneval_score``, this shells out to the official ``terminal-bench`` harness
(``tb run``, Apache-2.0) against OpenRouter-routed models and writes the task
resolution pass-rate to ``agents.tbench_accuracy``. Generates scores for models
the public tbench.ai leaderboard has not covered (e.g. minimax-m3, glm-5.2,
deepseek-v4-pro).

Grounded invocation (Phase A of 2026-07-13-plan-1-terminal-bench-runner):
    tb run -a terminus-2 -m openrouter/<id> -d terminal-bench-core==0.1.1 \
       --n-concurrent N [--n-tasks N | -t <glob>] --output-path <dir> \
       --no-upload-results --cleanup

Scoring: top-level ``<out>/<run-id>/results.json`` → ``accuracy`` (0.0-1.0) is
the resolution pass-rate → ``tbench_accuracy = accuracy * 100``.

Cost: the harness's per-trial ``total_*_tokens`` are 0 (terminus-2 does not
populate them), so cost is measured via the OpenRouter balance-delta
(``GET /api/v1/credits``), NOT token counts. Each model run is bounded by
``--cost-cap`` (per-model USD ceiling; breach stops the cohort) and by
``--n-tasks`` / ``--task-id``. ``--dry-run`` calls no model.

⚠️ Home scores use OUR harness run — they are a relative comparison across our
candidates under one identical harness, NOT byte-identical to the public
leaderboard (different harness version + runs). See docs/reference/terminal-bench-runner.md.

Not wired into daily_refresh.sh — on-demand only (agentic loops cost minutes +
credit per model).
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
from datetime import date

import httpx
from dotenv import load_dotenv

SCRIPT_DIR = pathlib.Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
CACHE_DIR = SCRIPT_DIR / "cache"

# --- Grounded constants (Phase A) -------------------------------------------
TB_CLI = "tb"
TB_AGENT = "terminus-2"
TB_DATASET = "terminal-bench-core==0.1.1"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"

# The unbenched sysadmin candidates this runner exists to score first.
DEFAULT_MODELS = [
    "minimax/minimax-m3",
    "z-ai/glm-5.2",
    "deepseek/deepseek-v4-pro",
]

# Shell-injection guard: model_id is interpolated into a subprocess argv, so it
# must be a safe vendor/name-tag. Mirror microbench_coding.py:_validate_model_id.
_SAFE_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9./_:-]*$")


def _validate_model_id(model_id: str) -> str:
    if not _SAFE_MODEL_ID_RE.match(model_id):
        raise ValueError(
            f"unsafe model id {model_id!r}: must match {_SAFE_MODEL_ID_RE.pattern} "
            f"(shell-injection guard). Reject at CLI boundary."
        )
    return model_id


# --- OpenRouter balance (cost measure) --------------------------------------
def openrouter_balance() -> float:
    """Remaining OpenRouter credit in USD (total_credits - total_usage)."""
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set (load .env)")
    resp = httpx.get(
        OPENROUTER_CREDITS_URL,
        headers={"Authorization": f"Bearer {key}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    d = resp.json()["data"]
    return float(d["total_credits"]) - float(d["total_usage"])


def _balance_or_none() -> float | None:
    """openrouter_balance() but graceful (core/58-resilience) — a transient
    credits-API blip must not lose a completed, paid-for bench. None = unknown."""
    try:
        return openrouter_balance()
    except (httpx.HTTPError, KeyError, ValueError, RuntimeError) as e:
        print(
            f"[terminal-bench] balance check failed ({e}); cost-cap skipped this model",
            file=sys.stderr,
        )
        return None


# --- DB cohort + writeback ---------------------------------------------------
def select_cohort(conn, models: list[str] | None) -> list[str]:
    """Return the model ids to bench.

    Default cohort = OpenRouter-routed, active, tool-capable (a sysadmin agent
    must call tools). An explicit --models list overrides (each validated).
    """
    if models:
        return [_validate_model_id(m) for m in models]
    rows = conn.execute(
        "SELECT id FROM agents "
        "WHERE via_openrouter = 1 AND status = 'active' AND has_tools = 1 "
        "ORDER BY id"
    ).fetchall()
    return [r[0] for r in rows]


def is_fresh(conn, model_id: str) -> bool:
    """A model is 'fresh' (skip re-benching) iff it already has a tbench score.

    Unlike microbench_coding's last_verified gate, we CANNOT use last_verified:
    it is overloaded — the daily price scrapers stamp it on every active model,
    so 305 never-tbench'd OR models carry a recent last_verified. Presence of a
    non-NULL tbench_accuracy is the honest "already benched" signal; a NULL means
    never benched → always bench it. Re-benching a scored model needs --force.
    """
    row = conn.execute(
        "SELECT 1 FROM agents WHERE id = ? AND tbench_accuracy IS NOT NULL",
        (model_id,),
    ).fetchone()
    return row is not None


def write_tbench_score(conn, model_id: str, score: float) -> None:
    """Write tbench_accuracy (0-100) + last_verified for one model.

    Explicit column list — only tbench_accuracy + last_verified are touched.
    """
    conn.execute(
        "UPDATE agents SET tbench_accuracy = ?, last_verified = ? WHERE id = ?",
        (round(score, 2), date.today().isoformat(), model_id),
    )
    conn.commit()


# --- Harness dispatch + parse ------------------------------------------------
def run_one(
    model_id: str,
    out_dir: pathlib.Path,
    *,
    dataset: str = TB_DATASET,
    n_tasks: int | None = None,
    task_id: str | None = None,
    n_concurrent: int = 4,
    n_attempts: int = 1,
) -> pathlib.Path:
    """Shell out to ``tb run`` for one model. Returns the run's output dir.

    argv list, never shell=True. model_id is validated before interpolation.
    """
    _validate_model_id(model_id)
    argv = [
        TB_CLI,
        "run",
        "-a",
        TB_AGENT,
        "-m",
        f"openrouter/{model_id}",
        "-d",
        dataset,
        "--n-concurrent",
        str(n_concurrent),
        "--n-attempts",
        str(n_attempts),
        "--output-path",
        str(out_dir),
        "--no-upload-results",
        "--cleanup",
    ]
    if task_id:
        argv += ["-t", task_id]
    elif n_tasks is not None:
        argv += ["--n-tasks", str(n_tasks)]
    env = {**os.environ}
    subprocess.run(argv, check=True, env=env)  # noqa: S603 — argv list, validated model_id
    return out_dir


def parse_tbench_output(out_dir: pathlib.Path) -> float:
    """Read the newest top-level results.json under out_dir → accuracy * 100.

    tb writes <out_dir>/<run-id>/results.json with an ``accuracy`` field
    (0.0-1.0) = resolution pass-rate. Returns 0-100.
    """
    candidates = sorted(
        out_dir.glob("*/results.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"no run results.json under {out_dir}")
    data = json.loads(candidates[0].read_text())
    return float(data["accuracy"]) * 100.0


# --- Orchestration -----------------------------------------------------------
def bench_model(
    conn,
    model_id: str,
    *,
    cost_cap: float,
    dataset: str,
    n_tasks: int | None,
    task_id: str | None,
    n_concurrent: int,
    n_attempts: int,
) -> tuple[float, float]:
    """Bench one model: balance-before → run → balance-after → parse → write.

    Returns (score_0_100, spent_usd). Raises RuntimeError if the model's
    spend-delta exceeds cost_cap (caller stops the cohort).
    """
    safe = re.sub(r"[^A-Za-z0-9]+", "_", model_id)
    out_dir = CACHE_DIR / f"tb_run_{safe}"
    out_dir.mkdir(parents=True, exist_ok=True)
    before = _balance_or_none()
    run_one(
        model_id,
        out_dir,
        dataset=dataset,
        n_tasks=n_tasks,
        task_id=task_id,
        n_concurrent=n_concurrent,
        n_attempts=n_attempts,
    )
    after = _balance_or_none()
    # Parse + WRITE the score first — a completed run's result is never lost to a
    # cost-check failure (core/58-resilience: graceful fallback on the external call).
    score = parse_tbench_output(out_dir)
    write_tbench_score(conn, model_id, score)
    # Enforce the cap only when both balances are known.
    spent = (before - after) if (before is not None and after is not None) else -1.0
    if spent > cost_cap:
        raise RuntimeError(
            f"cost cap breached: {model_id} spent ${spent:.4f} > cap ${cost_cap:.2f} "
            f"— stopping cohort (score {score:.1f} was still written)"
        )
    return score, spent


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="microbench_terminal",
        description="Home-run Terminal-Bench scoring for OpenRouter models.",
    )
    p.add_argument(
        "--models",
        default="",
        help="Comma-separated model ids. Default: the unbenched sysadmin cohort "
        f"({','.join(DEFAULT_MODELS)}); pass 'all' for every tool-capable OR model.",
    )
    p.add_argument(
        "--cost-cap", type=float, default=5.0, help="Per-model USD ceiling (default 5.0)."
    )
    p.add_argument("--dataset", default=TB_DATASET, help=f"tb dataset (default {TB_DATASET}).")
    p.add_argument(
        "--n-tasks", type=int, default=None, help="Limit tasks per model (default: full set)."
    )
    p.add_argument("--task-id", default=None, help="Task id/glob to run (overrides --n-tasks).")
    p.add_argument("--n-concurrent", type=int, default=4, help="Concurrent trials (default 4).")
    p.add_argument(
        "--n-attempts", type=int, default=1, help="Attempts (trials) per task (default 1)."
    )
    p.add_argument("--force", action="store_true", help="Re-bench even if fresh.")
    p.add_argument(
        "--dry-run", action="store_true", help="Print the dispatch plan + estimate; call no model."
    )
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv(SCRIPT_DIR.parent.parent / ".env")
    args = _build_argparser().parse_args(argv)
    if args.cost_cap <= 0:
        print(f"error: --cost-cap must be > 0 (got {args.cost_cap})", file=sys.stderr)
        return 2

    conn = sqlite3.connect(DB_PATH)
    try:
        raw = [m.strip() for m in args.models.split(",") if m.strip()]
        if raw == ["all"]:
            cohort = select_cohort(conn, None)
        else:
            cohort = select_cohort(conn, raw or DEFAULT_MODELS)
        if not args.force:
            cohort = [m for m in cohort if not is_fresh(conn, m)]

        if args.dry_run:
            print(f"[dry-run] would bench {len(cohort)} model(s) on {args.dataset}")
            print(
                f"[dry-run] agent={TB_AGENT} n_concurrent={args.n_concurrent} "
                f"n_attempts={args.n_attempts} cost_cap=${args.cost_cap:.2f}/model"
            )
            for m in cohort:
                print(f"[dry-run]   {TB_CLI} run -a {TB_AGENT} -m openrouter/{m} -d {args.dataset}")
            print("[dry-run] no OpenRouter calls made.")
            return 0

        if not cohort:
            print("[terminal-bench] nothing to bench (all fresh; use --force).")
            return 0

        for m in cohort:
            print(f"[terminal-bench] benching {m} …")
            try:
                score, spent = bench_model(
                    conn,
                    m,
                    cost_cap=args.cost_cap,
                    dataset=args.dataset,
                    n_tasks=args.n_tasks,
                    task_id=args.task_id,
                    n_concurrent=args.n_concurrent,
                    n_attempts=args.n_attempts,
                )
                print(f"[terminal-bench] {m}: tbench={score:.1f} spent=${spent:.4f}")
            except RuntimeError as e:
                print(f"[terminal-bench] STOP — {e}", file=sys.stderr)
                return 1
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
