#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/add_tbench_leaderboard_table.py docs/reference/terminal-bench-runner.md
"""Scrape the PER-TASK Terminal-Bench 2.x leaderboard results — the category profile, free.

The aggregate leaderboard score is the wrong number for hiring a model into a ROLE. Our own
run proved it: minimax-m3 scored 34% overall but **15% at system-administration** — it fails
the actual sysadmin job while looking merely mediocre. A single number cannot tell you that.

The public leaderboard publishes the per-task detail (every submission must upload k>=5
trials per task), and each task's `task.toml` carries its `category`. Joining the two gives
a full per-(model, category) capability matrix for every leaderboard entry — for **$0**,
instead of paying OpenRouter to re-measure what is already published. Our 11 other scrapers
all store a single aggregate; this is the first that keeps the detail.

Source (grounded live 2026-07-14):
    HF dataset `harborframework/terminal-bench-2-leaderboard`
    submissions/terminal-bench/2.0/<agent>__<model>/
        metadata.yaml                     -> model_name, model_provider, display names
        <job>/<task>__<hash>/result.json  -> one TRIAL

    result.json (the fields we need):
        task_name              "terminal-bench/configure-git-webserver"
        source                 "terminal-bench/terminal-bench-2-1"   (which dataset ran)
        verifier_result        {"rewards": {"reward": 1.0}}   1.0 = pass, 0.0 = fail
                               **null when the trial ERRORED** (docker/infra died before
                               the verifier ran) — an error is NOT a failure, and counting
                               it as one silently deflates every model's score.
        agent_result.cost_usd  measured $ for that trial (beats a per-token estimate)

Only `result.json` + `metadata.yaml` are fetched, via a partial+sparse git clone (472 MB
instead of 16 GB) — see `fetch_submissions` for why the HF library/API paths do not work
on a repo with ~33k trial directories.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from collections import defaultdict
from datetime import date

import yaml
from add_tbench_leaderboard_table import ensure_tbench_leaderboard_table

SCRIPT_DIR = pathlib.Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"

HF_REPO = "harborframework/terminal-bench-2-leaderboard"
# The task definitions (for category/difficulty). `harbor download` puts them here.
TASKS_DIR = pathlib.Path.home() / ".cache" / "harbor" / "tasks" / "terminal-bench-2-1"

SYSADMIN_CATEGORIES = ("system-administration", "security")


# --- Task metadata (the join key that turns tasks into CAPABILITIES) -----------
def load_task_meta(tasks_dir: pathlib.Path = TASKS_DIR) -> dict[str, dict]:
    """task_id -> {'category', 'difficulty'} from each task's task.toml (TB 2.x is TOML;
    the legacy 1.x set used task.yaml)."""
    meta: dict[str, dict] = {}
    if not tasks_dir.exists():
        return meta
    for tt in sorted(tasks_dir.glob("*/task.toml")):
        try:
            d = tomllib.loads(tt.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            continue
        m = d.get("metadata", {})
        meta[tt.parent.name] = {
            "category": m.get("category"),
            "difficulty": m.get("difficulty"),
        }
    return meta


# --- Parsing one trial --------------------------------------------------------
def parse_trial(d: dict) -> dict | None:
    """One result.json -> {task_id, passed, errored, cost_usd}, or None if unusable.

    ``errored`` is tracked SEPARATELY from ``passed``: a trial whose verifier never ran
    (docker failed, the sandbox died) tells us nothing about the model, and folding it in
    as a failure would understate every model that happened to hit flaky infra.
    """
    task_name = d.get("task_name") or ""
    task_id = task_name.split("/")[-1]  # "terminal-bench/foo" -> "foo"
    if not task_id:
        return None

    vr = d.get("verifier_result")
    if vr is None:
        return {"task_id": task_id, "passed": False, "errored": True, "cost_usd": None}

    reward = (vr.get("rewards") or {}).get("reward")
    ar = d.get("agent_result") or {}
    return {
        "task_id": task_id,
        "passed": reward == 1.0,
        "errored": False,
        "cost_usd": ar.get("cost_usd"),
    }


def parse_metadata(text: str) -> dict:
    """metadata.yaml -> {agent, models:[{model_raw, provider}]}."""
    y = yaml.safe_load(text) or {}
    models = []
    for m in y.get("models") or []:
        raw = m.get("model_name")
        if raw:
            models.append({"model_raw": raw, "provider": m.get("model_provider")})
    return {"agent": y.get("agent_display_name"), "models": models}


# --- Mapping a leaderboard model string onto agents.id ------------------------
def _normalize(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def map_model_id(model_raw: str, catalog: list[str]) -> str | None:
    """Map a submission's model string onto our agents.id, or None if we don't carry it.

    Leaderboard strings are messy and inconsistent across submitters ('gpt-5.5',
    'anthropic/claude-opus-4-7', 'zai-org/GLM-5.1'). An exact match is tried first, then a
    normalized compare on the tail. Returning None is FINE and expected — a model we don't
    route (a closed frontier model) simply has no agents row; we still store model_raw, so
    nothing is lost and nothing is silently mis-attributed to the wrong model.
    """
    if model_raw in catalog:
        return model_raw
    tail = _normalize(model_raw.split("/")[-1])
    if not tail:
        return None
    for cid in catalog:
        if _normalize(cid.split("/")[-1]) == tail:
            return cid
    return None


# --- Fetch --------------------------------------------------------------------
HF_GIT_URL = f"https://huggingface.co/datasets/{HF_REPO}"
DEFAULT_CLONE = pathlib.Path.home() / ".cache" / "fabrik" / "tbench-2-leaderboard"


def fetch_submissions(
    dest: pathlib.Path = DEFAULT_CLONE,
    git_url: str = HF_GIT_URL,
    *,
    refresh: bool = False,
) -> pathlib.Path:
    """Fetch ONLY the result.json + metadata.yaml blobs, via a partial+sparse git clone.

    NOT ``huggingface_hub.snapshot_download``: it resolves the file list first, and this
    repo has ~33k trial dirs — the listing call hangs for 15+ minutes and never gets to a
    download. (Ditto the HTTP tree API: ``recursive=true`` pages 1,000 entries at a time
    and emits every DIRECTORY before any file, so you page through >11k dirs before seeing
    a single result.json.) Verified against the live repo 2026-07-14.

    Instead: `--filter=blob:none` (fetch no file contents up front) + a sparse-checkout
    limited to the two filenames we read, so git materializes only those blobs.
    **472 MB instead of 16 GB** for the identical 33,047 result.json + 74 metadata.yaml.
    `GIT_LFS_SKIP_SMUDGE=1` leaves the LFS trajectory blobs as pointers — they are the
    bulk of the repo and we never read them.

    Re-running is cheap: an existing clone is `git pull`ed rather than re-cloned.
    """
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"}

    def _git(*args: str, cwd: pathlib.Path | None = None) -> None:
        subprocess.run(["git", *args], cwd=cwd, env=env, check=True)  # noqa: S603,S607

    if dest.exists() and (dest / ".git").is_dir():
        if refresh:
            print(f"[scrape] refreshing existing clone at {dest}", file=sys.stderr)
            _git("pull", "--ff-only", "--depth", "1", cwd=dest)
        else:
            print(f"[scrape] reusing clone at {dest} (--refresh to update)", file=sys.stderr)
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)  # a partial/failed clone would poison every later run
    print(f"[scrape] partial+sparse clone → {dest} (~472MB, not the full ~16GB)", file=sys.stderr)
    _git(
        "clone",
        "--depth",
        "1",
        "--filter=blob:none",
        "--no-checkout",
        "--quiet",
        git_url,
        str(dest),
    )
    _git("sparse-checkout", "set", "--no-cone", "**/result.json", "**/metadata.yaml", cwd=dest)
    _git("checkout", "--quiet", cwd=dest)
    return dest


def collect(root: pathlib.Path, task_meta: dict[str, dict]) -> list[dict]:
    """Walk the downloaded tree -> one row per (submission, task), aggregated over trials."""
    rows: list[dict] = []
    subs_root = root / "submissions" / "terminal-bench"
    if not subs_root.exists():
        return rows

    for meta_file in sorted(subs_root.glob("*/*/metadata.yaml")):
        sub_dir = meta_file.parent
        submission = sub_dir.name
        try:
            md = parse_metadata(meta_file.read_text())
        except (OSError, yaml.YAMLError):
            continue

        # trials: <job>/<task>__<hash>/result.json
        per_task: dict[str, list[dict]] = defaultdict(list)
        dataset = None
        for rj in sub_dir.glob("*/*/result.json"):
            try:
                d = json.loads(rj.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            t = parse_trial(d)
            if not t:
                continue
            dataset = dataset or d.get("source")
            per_task[t["task_id"]].append(t)

        if not per_task:
            continue

        # A submission may declare several models; we cannot attribute a trial to one of
        # them, so a multi-model submission is recorded under its raw label rather than
        # guessing (guessing here would poison the per-model matrix).
        models = md["models"]
        model_raw = models[0]["model_raw"] if len(models) == 1 else "Multiple"

        for task_id, trials in per_task.items():
            n = len(trials)
            n_err = sum(1 for t in trials if t["errored"])
            n_pass = sum(1 for t in trials if t["passed"])
            scored = n - n_err
            costs = [t["cost_usd"] for t in trials if t["cost_usd"] is not None]
            tm = task_meta.get(task_id, {})
            rows.append(
                {
                    "submission": submission,
                    "agent": md["agent"],
                    "model_raw": model_raw,
                    "task_id": task_id,
                    "dataset": dataset or "terminal-bench/terminal-bench-2-1",
                    "category": tm.get("category"),
                    "difficulty": tm.get("difficulty"),
                    "n_trials": n,
                    "n_passed": n_pass,
                    "n_errored": n_err,
                    # errored trials measured nothing — exclude them from the denominator
                    "pass_rate": (n_pass / scored) if scored else None,
                    "avg_cost_usd": (sum(costs) / len(costs)) if costs else None,
                }
            )
    return rows


def persist(conn, rows: list[dict], catalog: list[str]) -> int:
    today = date.today().isoformat()
    n = 0
    for r in rows:
        model_id = map_model_id(r["model_raw"], catalog) if r["model_raw"] != "Multiple" else None
        conn.execute(
            "INSERT OR REPLACE INTO tbench_leaderboard_results "
            "(submission, agent, model_id, model_raw, task_id, dataset, category, difficulty,"
            " n_trials, n_passed, n_errored, pass_rate, avg_cost_usd, scraped_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                r["submission"],
                r["agent"],
                model_id,
                r["model_raw"],
                r["task_id"],
                r["dataset"],
                r["category"],
                r["difficulty"],
                r["n_trials"],
                r["n_passed"],
                r["n_errored"],
                r["pass_rate"],
                r["avg_cost_usd"],
                today,
            ),
        )
        n += 1
    conn.commit()
    return n


# --- Report -------------------------------------------------------------------
def report_sysadmin(conn, limit: int = 25) -> None:
    """Rank submissions by the SYSADMIN workload (system-administration + security) — the
    slice that actually predicts the job, next to the overall score that hides it."""
    rows = conn.execute(
        """
        SELECT submission,
               COALESCE(model_id, model_raw) AS model,
               AVG(CASE WHEN category IN ('system-administration','security')
                        THEN pass_rate END) AS sysadmin,
               AVG(pass_rate)                AS overall,
               SUM(CASE WHEN category IN ('system-administration','security')
                        THEN n_trials ELSE 0 END) AS sys_trials
        FROM tbench_leaderboard_results
        WHERE pass_rate IS NOT NULL
        GROUP BY submission
        HAVING sysadmin IS NOT NULL
        ORDER BY sysadmin DESC, overall DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    if not rows:
        print("[report] no leaderboard rows yet — run the scrape first.")
        return
    print(f"\n{'submission':<40} {'model':<30} {'SYSADMIN':>9} {'overall':>8}")
    print("-" * 92)
    for sub, model, sysadmin, overall, _ in rows:
        print(
            f"{sub[:39]:<40} {str(model)[:29]:<30} {sysadmin * 100:>8.0f}% {overall * 100:>7.0f}%"
        )


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scrape_tbench_task_results",
        description="Scrape PER-TASK Terminal-Bench leaderboard results → per-category matrix.",
    )
    p.add_argument(
        "--report", action="store_true", help="Print the sysadmin ranking; do not scrape."
    )
    p.add_argument("--limit", type=int, default=25, help="Rows in the report (default 25).")
    p.add_argument(
        "--refresh", action="store_true", help="git pull an existing clone before scraping."
    )
    p.add_argument(
        "--from-clone", default=None, help="Parse an existing local clone instead of fetching."
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)
    ensure_tbench_leaderboard_table(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        if args.report:
            report_sysadmin(conn, args.limit)
            return 0

        task_meta = load_task_meta()
        if not task_meta:
            print(
                f"error: no task metadata at {TASKS_DIR} — the category join is the whole "
                f"point of this scraper, and without it every row lands with a NULL "
                f"category. Run: harbor download terminal-bench/terminal-bench-2-1 "
                f"-o ~/.cache/harbor/tasks",
                file=sys.stderr,
            )
            return 2
        print(f"[scrape] task metadata: {len(task_meta)} tasks", file=sys.stderr)

        print(
            "[scrape] fetching result.json + metadata.yaml (skipping the ~40GB of trajectories)…",
            file=sys.stderr,
        )
        root = (
            pathlib.Path(args.from_clone)
            if args.from_clone
            else fetch_submissions(refresh=args.refresh)
        )

        rows = collect(root, task_meta)
        if not rows:
            print(
                "error: fetched the repo but parsed 0 rows — the layout may have "
                "changed; re-ground before trusting this.",
                file=sys.stderr,
            )
            return 1

        catalog = [r[0] for r in conn.execute("SELECT id FROM agents").fetchall()]
        n = persist(conn, rows, catalog)
        subs = len({r["submission"] for r in rows})
        mapped = conn.execute(
            "SELECT COUNT(DISTINCT model_id) FROM tbench_leaderboard_results "
            "WHERE model_id IS NOT NULL"
        ).fetchone()[0]
        print(
            f"[scrape] {n} (submission, task) rows from {subs} submissions; "
            f"{mapped} models mapped onto agents.id",
            file=sys.stderr,
        )
        report_sysadmin(conn, args.limit)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
