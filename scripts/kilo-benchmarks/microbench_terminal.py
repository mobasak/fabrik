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
(``GET /api/v1/credits``), NOT token counts. ``--cost-cap`` is a **run (cohort)
budget**, checked BEFORE each model — it stops the run once cumulative spend
reaches the cap, but cannot interrupt a single ``tb run`` mid-flight, so the
real **per-model** spend bound is ``--n-tasks``. On a shared OpenRouter key the
balance-delta is best-effort (concurrent sibling spend perturbs it) — treat it
as approximate and rely on ``--n-tasks`` for a hard per-model bound.
``--agent-timeout`` caps a stuck agent loop. ``--dry-run`` calls no model.

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
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, datetime

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

# The task categories that matter for a fleet-sysadmin agent — used by
# --category sysadmin as a convenience alias for the on-workload subset.
SYSADMIN_CATEGORIES = ("system-administration", "security")


def _dataset_dir(dataset: str) -> pathlib.Path:
    """Local task dir for a tb dataset: 'terminal-bench-core==0.1.1' →
    ~/.cache/terminal-bench/terminal-bench-core/0.1.1 (tb downloads it there)."""
    name, _, ver = dataset.partition("==")
    return pathlib.Path.home() / ".cache" / "terminal-bench" / name / (ver or "head")


_TASK_META_CACHE: dict[str, dict[str, dict]] = {}


def load_task_meta(dataset: str) -> dict[str, dict]:
    """Map task_id → {'category', 'difficulty'} from each task's task.yaml.

    Returns {} if the dataset isn't downloaded yet (tb fetches it on first run).

    Memoized per dataset so an N-model cohort parses the ~80 task.yaml files once
    instead of once per model. ⚠️ Only a NON-EMPTY result is cached: `{}` means the
    dataset is not on disk YET (tb downloads it DURING the first run), so caching that
    would pin every later persist to all-NULL categories — the exact bug the
    load-meta-after-the-run change fixed. An empty read stays retryable.
    """
    cached = _TASK_META_CACHE.get(dataset)
    if cached:
        return cached

    import yaml

    meta: dict[str, dict] = {}
    ddir = _dataset_dir(dataset)
    if not ddir.exists():
        return meta
    for ty in ddir.glob("*/task.yaml"):
        try:
            y = yaml.safe_load(ty.read_text()) or {}
            meta[ty.parent.name] = {
                "category": y.get("category"),
                "difficulty": y.get("difficulty"),
            }
        except (OSError, yaml.YAMLError):
            meta[ty.parent.name] = {"category": None, "difficulty": None}
    if meta:
        _TASK_META_CACHE[dataset] = meta
    return meta


def tasks_in_categories(dataset: str, categories: list[str]) -> list[str]:
    """Task ids whose task.yaml category is in `categories` (for --category)."""
    meta = load_task_meta(dataset)
    return sorted(t for t, m in meta.items() if m.get("category") in set(categories))


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
    except (httpx.HTTPError, KeyError, ValueError, TypeError, RuntimeError) as e:
        # TypeError covers a schema drift like {"data": null} → d["total_credits"] on
        # None; this wrapper must NEVER crash the cohort (it runs in main's finally).
        print(
            f"[terminal-bench] balance check failed ({e}); cost not counted for this model",
            file=sys.stderr,
        )
        return None


# --- DB cohort + writeback ---------------------------------------------------
def select_cohort(conn, models: list[str] | None) -> list[str]:
    """Return the model ids to bench (unvalidated — main validates the whole cohort
    up front, so BOTH the explicit --models path and the DB path get one uniform
    clean exit-2 on a malformed id, instead of this path raising an uncaught error).

    Default cohort = OpenRouter-routed, active, tool-capable (a sysadmin agent
    must call tools). An explicit --models list overrides.
    """
    if models:
        return list(models)
    rows = conn.execute(
        "SELECT id FROM agents "
        "WHERE via_openrouter = 1 AND status = 'active' AND has_tools = 1 "
        "ORDER BY id"
    ).fetchall()
    return [r[0] for r in rows]


def _model_exists(conn, model_id: str) -> bool:
    """True iff the id is a row in agents. write_tbench_score's UPDATE is a silent
    no-op for an absent id, so main pre-checks existence to fail (before spending
    credit) rather than bench + report success + persist nothing."""
    return (
        conn.execute("SELECT 1 FROM agents WHERE id = ? LIMIT 1", (model_id,)).fetchone()
        is not None
    )


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
def _scope_tag(
    dataset: str,
    task_ids: list[str] | None,
    n_tasks: int | None = None,
    n_attempts: int = 1,
    agent_timeout_sec: float = 600.0,
    agent: str = TB_AGENT,
) -> str:
    """A short deterministic tag for every knob a resume would SILENTLY IGNORE.

    ``tb runs resume`` takes only ``--run-id``/``--runs-dir`` and rebuilds the harness
    from the original ``tb.lock`` — *"The resume command uses the original configuration
    from the run's tb.lock file"* (terminal_bench/cli/tb/runs.py:793-804). So EVERY config
    flag on the resuming invocation is discarded. A run may therefore only resume into a
    run with the SAME config, or it silently benches something other than what was asked
    for. In the key:

    - **task set** — a subset (--category/--task-id) resuming a full run's dir would
      re-run the WHOLE set.
    - **dataset** — re-running a model on a new ``--dataset`` resumed the OLD dataset's
      run while ``persist_task_results`` labelled every row with the NEW dataset name:
      rows attributed to a dataset that was never benched.
    - **n_tasks** — the one that bites hardest, because it costs money. After a full run,
      ``--n-tasks 5`` has ``task_ids is None``, so it hashed to the FULL run's dir, found
      its lock, and resumed it — re-running the ENTIRE task set. The operator asked for a
      bounded 5-task sanity check and paid for a full run.
    - **n_attempts** — same class: ``--n-attempts 3`` over a locked ``n_attempts=1`` run
      silently benches ONE attempt (tb validates trial dirs against the lock's count,
      run_lock.py:296-303 — the lock wins, not your flag).
    - **agent + agent_timeout** — both change RESULTS. Raising ``--agent-timeout`` to give
      a model more room does nothing on a resume: the timed-out tasks already wrote a
      ``results.json`` (``failure_mode: agent_timeout``), so resume counts them DONE and
      skips them. A different timeout is a different run.

    ``n_concurrent`` is deliberately NOT in the key — it changes only how FAST the run
    goes, never the result, so changing it must still be able to resume.

    The key holds what BINDS, not what was merely typed. ``n_tasks`` only reaches tb when
    there is no ``-t`` list (``run_one``: ``if not task_ids and n_tasks is not None``), and
    on a subset run ``main`` has ALREADY folded the bound into ``task_ids`` by truncating
    it. So with a task set, ``task_ids`` alone fully describes the run and ``n_tasks`` is
    inert — keying on it anyway would split two byte-identical ``tb`` invocations
    (``--category security --n-tasks 50`` vs ``100``, against a 3-task category) into
    different dirs and make them REFUSE to resume each other: a legitimate resume denied,
    credit re-spent. That is the same bug as an illegitimate resume permitted, just
    pointing the other way.

    Same scope → same dir → resumable; different scope → its own dir, fresh run.
    """
    import hashlib

    # json, not a "|".join of raw strings: the fields are operator-supplied (a --dataset
    # or task id containing the delimiter could shift field boundaries and alias two
    # different configs onto one key). JSON quotes/escapes, so the encoding is unambiguous.
    key = json.dumps(
        [
            dataset,
            sorted(task_ids) if task_ids else None,
            n_tasks if not task_ids else None,  # inert once a task set pins the run
            n_attempts,
            agent_timeout_sec,
            agent,
        ]
    )
    digest = hashlib.sha1(key.encode()).hexdigest()[:8]  # noqa: S324 — dir tag, not security
    return f"__{digest}"


def out_dir_for(
    model_id: str,
    dataset: str,
    task_ids: list[str] | None,
    n_tasks: int | None = None,
    n_attempts: int = 1,
    agent_timeout_sec: float = 600.0,
) -> pathlib.Path:
    """Per-(model, run-config) dir — the exact key a resume is safe across. Anything
    outside this key must never resume into it (see ``_scope_tag``)."""
    safe = re.sub(
        r"[^A-Za-z0-9]+", "_", model_id
    )  # non-empty: _validate_model_id forces [A-Za-z0-9] first
    tag = _scope_tag(dataset, task_ids, n_tasks, n_attempts, agent_timeout_sec)
    return CACHE_DIR / f"tb_run_{safe}{tag}"


def _find_resumable_run(out_dir: pathlib.Path) -> str | None:
    """The newest run-id under out_dir that has a tb.lock (i.e. is resumable).

    out_dir is per-(model, scope), so any run in it shares this model+task-set —
    resume is safe. Returns the run-id (dir name) or None if nothing to resume.
    """
    if not out_dir.exists():
        return None
    runs = sorted(p.name for p in out_dir.iterdir() if p.is_dir() and (p / "tb.lock").exists())
    return runs[-1] if runs else None


def run_one(
    model_id: str,
    out_dir: pathlib.Path,
    *,
    dataset: str = TB_DATASET,
    n_tasks: int | None = None,
    task_ids: list[str] | None = None,
    n_concurrent: int = 4,
    n_attempts: int = 1,
    agent_timeout_sec: float = 600.0,
    run_timeout_sec: float | None = None,
    resume: bool = True,
) -> str | None:
    """Shell out to ``tb`` for one model. Returns the RUN-ID it operated on (so the
    caller scopes parse/persist to exactly this run, not the newest across all runs).

    argv list, never shell=True. model_id is validated before interpolation.
    ``agent_timeout_sec`` → ``--global-agent-timeout-sec`` kills a stuck AGENT loop;
    ``run_timeout_sec`` (optional) is a HARD wall-clock cap on the whole ``tb``
    PROCESS (a hang outside the agent loop). Left ``None`` by default (a full task
    set runs for hours); the caller treats a ``TimeoutExpired`` as a model failure.

    ``resume=True`` (default): if a partial prior run exists in out_dir, resume it
    via ``tb runs resume`` — completed tasks are skipped, incomplete ones re-run,
    NO credit is re-spent on finished work (returns the resumed run-id). ``resume=
    False`` (the caller's --force path, which wiped out_dir first) always starts
    fresh (returns the newly-created run-id).

    A fresh run is given an EXPLICIT ``--run-id`` we generate, rather than letting tb
    default it and then guessing which dir appeared. Guessing (diff the dir listing
    before/after, else newest-by-mtime) misattributes the run whenever tb writes any
    other top-level dir, or when two runs share an out_dir — and it is untestable
    without faking directory side-effects. Handing tb the id makes the run-id an
    INPUT, so parse/persist scope to exactly this run by construction.
    ``tb run --run-id`` is a real flag (terminal_bench/cli/tb/runs.py:164, default
    ``YYYY-MM-DD__HH-MM-SS``); the microsecond suffix keeps ids unique + lexicographically
    ordered, which ``_find_resumable_run``'s sort relies on.
    """
    _validate_model_id(model_id)
    prior = _find_resumable_run(out_dir) if resume else None
    env = {**os.environ}
    if prior:
        # Resume reuses the original run's tb.lock config (agent/model/dataset/tasks).
        argv = [TB_CLI, "runs", "resume", "--run-id", prior, "--runs-dir", str(out_dir)]
        subprocess.run(argv, check=True, env=env, timeout=run_timeout_sec)  # noqa: S603
        return prior
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y-%m-%d__%H-%M-%S-%f")
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
        "--global-agent-timeout-sec",
        str(agent_timeout_sec),
        "--output-path",
        str(out_dir),
        "--run-id",
        run_id,
        "--no-upload-results",
        "--cleanup",
    ]
    for t in task_ids or []:
        argv += ["-t", t]
    if not task_ids and n_tasks is not None:
        argv += ["--n-tasks", str(n_tasks)]
    subprocess.run(argv, check=True, env=env, timeout=run_timeout_sec)  # noqa: S603
    # tb writes its run under <out_dir>/<run_id> (harness.py:182). A tb that exits 0
    # without creating it produced nothing → None, which the caller turns into a
    # per-model failure rather than reading some other run's results.
    return run_id if (out_dir / run_id).is_dir() else None


def parse_tbench_output(out_dir: pathlib.Path, run_id: str | None = None) -> float:
    """Read a run's top-level results.json → accuracy * 100 (0-100).

    When ``run_id`` is given, reads exactly ``<out_dir>/<run_id>/results.json`` — so
    a re-run in a dir that also holds OLD run-id dirs can't read a stale prior
    accuracy (the pre-run-id-scoping bug). When ``run_id`` is None, falls back to
    the newest by mtime. Raises FileNotFoundError if the run produced no
    results.json, or ValueError if it is present but malformed — the caller treats
    both as a model failure (never crashes the cohort on a bad results.json).
    """
    if run_id is not None:
        rj = out_dir / run_id / "results.json"
        if not rj.exists():
            raise FileNotFoundError(f"no results.json for run {run_id} under {out_dir}")
        candidates = [rj]
    else:
        candidates = sorted(
            out_dir.glob("*/results.json"), key=lambda p: p.stat().st_mtime, reverse=True
        )
        if not candidates:
            raise FileNotFoundError(f"no run results.json under {out_dir}")
    try:
        data = json.loads(candidates[0].read_text())
        return float(data["accuracy"]) * 100.0
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        raise ValueError(f"malformed results.json in {out_dir}: {e}") from e


# The exception classes that mean "this model failed — skip it, don't crash the
# cohort" (a tb non-zero exit / hang / hard-timeout, no results, or malformed output).
MODEL_FAILURE = (
    subprocess.CalledProcessError,
    subprocess.TimeoutExpired,
    FileNotFoundError,
    ValueError,
)


# --- Per-task persistence ----------------------------------------------------
def _trial_duration_s(d: dict) -> float | None:
    from datetime import datetime

    s, e = d.get("trial_started_at"), d.get("trial_ended_at")
    if not s or not e:
        return None
    try:
        return (datetime.fromisoformat(e) - datetime.fromisoformat(s)).total_seconds()
    except (ValueError, TypeError):
        return None


def persist_task_results(
    conn,
    model_id: str,
    out_dir: pathlib.Path,
    dataset: str,
    run_id: str,
    meta: dict | None = None,
) -> int:
    """Write one row per task into tbench_task_results for THIS run only.

    Scoped to ``out_dir/run_id`` (NOT ``out_dir/*``) so accumulated OLD run-id dirs
    can't leak stale rows or mislabel run_id (pool #2 / native #3). ``meta`` is
    loaded here by default (``load_task_meta``) rather than passed from before the
    run — on a first run tb downloads the dataset DURING the run, so meta captured
    up front would be empty → all-NULL categories (native #2). INSERT OR REPLACE
    keyed on (model_id, task_id, dataset). With ``--n-attempts > 1`` a task has
    several trial results.json; the last one globbed wins (one row per task — the
    per-attempt spread lives in the aggregate accuracy, not this table).
    """
    if meta is None:
        meta = load_task_meta(dataset)
    today = date.today().isoformat()
    rows = 0
    for tr in (out_dir / run_id).glob("*/*/results.json"):  # <task>/<trial>/results.json
        try:
            d = json.loads(tr.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        tid = d.get("task_id")
        if not tid:
            continue
        m = meta.get(tid, {})
        conn.execute(
            "INSERT OR REPLACE INTO tbench_task_results "
            "(model_id, task_id, dataset, category, difficulty, is_resolved, "
            " failure_mode, duration_s, run_id, benched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                model_id,
                tid,
                dataset,
                m.get("category"),
                m.get("difficulty"),
                1 if d.get("is_resolved") else 0,
                d.get("failure_mode"),
                _trial_duration_s(d),
                run_id,
                today,
            ),
        )
        rows += 1
    conn.commit()
    return rows


# --- Orchestration -----------------------------------------------------------
def bench_model(
    conn,
    model_id: str,
    *,
    dataset: str,
    n_tasks: int | None,
    task_ids: list[str] | None,
    n_concurrent: int,
    n_attempts: int,
    agent_timeout_sec: float = 600.0,
    run_timeout_sec: float | None = None,
    force: bool = False,
    task_meta: dict | None = None,
) -> float:
    """Run (or RESUME) → parse → persist per-task → write aggregate → return score.

    Cost is NOT measured here — the CALLER (``main``) brackets each call with
    balance reads, so a model that fails *after* spending credit still counts.

    Resumability: by default a partial prior run in out_dir is **resumed** (only
    the incomplete tasks re-run, no credit re-spent). ``force`` wipes out_dir and
    starts fresh. out_dir is per-(model, dataset, task-scope) so a subset (--category)
    run never resumes or clobbers the full run's dir. run_one returns the RUN-ID it
    operated on; parse + persist are scoped to exactly that run (no stale-prior read).

    The aggregate ``agents.tbench_accuracy`` is written ONLY on a full-set run
    (``task_ids is None and n_tasks is None``) — a subset run's pass-rate is NOT the
    overall score, so it must not overwrite the aggregate column (native #1). Subset
    runs still persist their per-task detail to tbench_task_results.

    Failure classes, handled differently — the dividing line is *did we already pay for
    a result*:
    - **Per-model** (``MODEL_FAILURE``) → raised, caller logs + SKIPS, cohort continues.
    - **Systemic infra, BEFORE the score exists** (``OSError`` from the ``--force`` wipe,
      ``sqlite3.Error`` from the aggregate ``write_tbench_score``) → NOT caught: it
      affects every model, so it halts LOUDLY rather than masking as N skips.
    - **ANY failure of the per-task detail write, AFTER the score exists** → caught and
      logged, never fatal. This is a deliberate asymmetry, not an oversight: by then the
      score has cost real OpenRouter credit and is already persisted, and the per-task
      table is *supplementary*. Letting an optional write destroy a paid-for result — or
      abort every remaining model in the cohort — would be strictly worse than running on
      without the category breakdown. The trade-off is that a genuine bug in
      ``persist_task_results`` degrades to a loud stderr line per model instead of a
      traceback; the tests, not the runtime, are what catch that.
    """
    # Normalize an empty list to None UP FRONT: `[]` is falsy (so it built a FULL-set
    # argv and hashed to the full-run dir) yet `[] is None` is False (so the aggregate
    # write was skipped) — a run that behaves full but scores as a subset. One
    # canonical "no task filter" value keeps every downstream branch agreeing.
    task_ids = task_ids or None
    out_dir = out_dir_for(model_id, dataset, task_ids, n_tasks, n_attempts, agent_timeout_sec)
    if force and out_dir.exists():
        shutil.rmtree(out_dir)
    run_id = run_one(
        model_id,
        out_dir,
        dataset=dataset,
        n_tasks=n_tasks,
        task_ids=task_ids,
        n_concurrent=n_concurrent,
        n_attempts=n_attempts,
        agent_timeout_sec=agent_timeout_sec,
        run_timeout_sec=run_timeout_sec,
        resume=not force,
    )
    if run_id is None:
        raise FileNotFoundError(f"tb produced no run dir under {out_dir}")
    score = parse_tbench_output(out_dir, run_id)
    # Aggregate column reflects the OVERALL score only — never a subset pass-rate.
    if task_ids is None and n_tasks is None:
        write_tbench_score(conn, model_id, score)
    # Per-task detail (category profile), scoped to this run. Best-effort, and that has
    # to mean ANY failure: the score above cost real credit and is already earned, so
    # nothing in the *optional* detail write may discard it or kill the cohort. Catching
    # only sqlite3.Error did not deliver that — persist also reads the dataset from disk
    # (load_task_meta), so an OSError from the glob, or a bad yaml import, escaped the
    # guard, escaped MODEL_FAILURE, and aborted every remaining model. Broad by intent;
    # loud, never silent.
    try:
        persist_task_results(conn, model_id, out_dir, dataset, run_id, task_meta)
    except Exception as e:  # noqa: BLE001 — best-effort by contract; the score must survive
        print(
            f"[terminal-bench] per-task persist failed for {model_id} "
            f"({type(e).__name__}: {e}) — score kept, per-task detail skipped",
            file=sys.stderr,
        )
    return score


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="microbench_terminal",
        description="Home-run Terminal-Bench scoring for OpenRouter models.",
    )
    p.add_argument(
        "--models",
        default="",
        help="Comma-separated model ids. Default: the unbenched sysadmin cohort "
        f"({','.join(DEFAULT_MODELS)}); include 'all' (any case, anywhere) for every "
        "tool-capable OR model.",
    )
    p.add_argument(
        "--cost-cap",
        type=float,
        default=5.0,
        help="Total USD budget for the RUN (cohort). Before each model, if cumulative "
        "spend has reached the cap the run stops. NOTE: this cannot interrupt a single "
        "model's tb-run mid-flight — bound per-model spend with --n-tasks. (default 5.0)",
    )
    p.add_argument("--dataset", default=TB_DATASET, help=f"tb dataset (default {TB_DATASET}).")
    p.add_argument(
        "--n-tasks",
        type=int,
        default=None,
        help="Tasks per model — the real per-model spend bound (default: full set; "
        "with a cost-cap set, leaving this unbounded lets the first model run the whole "
        "set before the cohort budget can act — a warning is printed).",
    )
    p.add_argument(
        "--task-id", default=None, help="Task id/glob to run (overrides --category/--n-tasks)."
    )
    p.add_argument(
        "--category",
        default=None,
        help="Run only tasks in these task.yaml categories (comma list), e.g. "
        "'system-administration,security'. Alias 'sysadmin' = those two (the "
        f"{len(SYSADMIN_CATEGORIES)}-category on-workload subset). Real categories: "
        "system-administration, security, software-engineering, debugging, "
        "file-operations, data-science, model-training, games, scientific-computing.",
    )
    p.add_argument("--n-concurrent", type=int, default=4, help="Concurrent trials (default 4).")
    p.add_argument(
        "--n-attempts", type=int, default=1, help="Attempts (trials) per task (default 1)."
    )
    p.add_argument(
        "--agent-timeout",
        type=float,
        default=600.0,
        help="Per-agent-run wall-clock cap in seconds (tb --global-agent-timeout-sec) so a "
        "stuck agent loop can't hang the cohort (default 600).",
    )
    p.add_argument(
        "--run-timeout",
        type=float,
        default=None,
        help="Optional HARD wall-clock cap (seconds) on a single model's whole tb process — "
        "catches a hang outside the agent loop (e.g. stalled Docker pull). Default: none "
        "(a full task set runs for hours); a timeout is treated as a model failure + skipped. "
        "CAVEAT: a killed tb bypasses its own --cleanup, so a leaked task container may remain — "
        "the next tb run or a manual `docker container prune` clears it.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Wipe the model's prior run and start FRESH (default: resume a partial "
        "prior run — completed tasks skipped, no credit re-spent). Also bypasses the "
        "already-benched freshness skip.",
    )
    p.add_argument(
        "--report",
        default=None,
        const="__ALL__",
        nargs="?",
        help="Print the per-category capability matrix from tbench_task_results and exit "
        "(no benching). Optionally pass a model id to report just that model.",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Print the dispatch plan + estimate; call no model."
    )
    return p


def report_matrix(conn, model_id: str | None = None) -> None:
    """Print the per-(model, category) pass-rate matrix from tbench_task_results."""
    where, params = "", []
    if model_id and model_id != "__ALL__":
        where, params = "WHERE model_id = ?", [model_id]
    rows = conn.execute(
        f"SELECT model_id, COALESCE(category,'(none)') AS category, "  # noqa: S608 — where is a fixed literal
        f"SUM(is_resolved) AS passed, COUNT(*) AS total "
        f"FROM tbench_task_results {where} "
        f"GROUP BY model_id, category ORDER BY model_id, category",
        params,
    ).fetchall()
    if not rows:
        print("[report] no per-task results yet — run a bench first.")
        return
    cur = None
    for mid, cat, passed, total in rows:
        if mid != cur:
            print(f"\n=== {mid} ===")
            print(f"  {'category':<24} {'passed':>7} {'total':>6} {'rate':>6}")
            cur = mid
        rate = (passed / total * 100) if total else 0.0
        print(f"  {cat:<24} {passed:>7} {total:>6} {rate:>5.0f}%")
    # overall line per model
    for (mid,) in {(r[0],) for r in rows}:
        tot = conn.execute(
            "SELECT SUM(is_resolved), COUNT(*) FROM tbench_task_results WHERE model_id=?", (mid,)
        ).fetchone()
        if tot and tot[1]:
            print(f"  → {mid} OVERALL: {tot[0]}/{tot[1]} = {tot[0] / tot[1] * 100:.0f}%")


def main(argv: list[str] | None = None) -> int:
    load_dotenv(SCRIPT_DIR.parent.parent / ".env")
    args = _build_argparser().parse_args(argv)
    if args.cost_cap <= 0:
        print(f"error: --cost-cap must be > 0 (got {args.cost_cap})", file=sys.stderr)
        return 2
    if args.agent_timeout <= 0:
        print(f"error: --agent-timeout must be > 0 (got {args.agent_timeout})", file=sys.stderr)
        return 2
    if args.run_timeout is not None and args.run_timeout <= 0:
        print(
            f"error: --run-timeout must be > 0 when set (got {args.run_timeout})", file=sys.stderr
        )
        return 2
    # --n-tasks was the one bound left unvalidated, and both bad values fail SILENTLY
    # rather than loudly: `--n-tasks 0` truncates a --category set to [], which
    # bench_model then reads as "no task filter" and runs the FULL dataset; a negative
    # value hits Python's slice semantics (`[:-1]` keeps len-1 items), quietly turning a
    # bad bound into a near-full run. A bound you got wrong must never widen the run.
    if args.n_tasks is not None and args.n_tasks <= 0:
        print(f"error: --n-tasks must be > 0 when set (got {args.n_tasks})", file=sys.stderr)
        return 2
    # Pre-flight: a missing tb binary must surface as an infra error, not be masked
    # as N benign per-model "skips" with a success exit code (finding pass-3).
    if not args.dry_run and shutil.which(TB_CLI) is None:
        print(
            f"error: '{TB_CLI}' not on PATH — is terminal-bench installed? "
            f"(pip install terminal-bench)",
            file=sys.stderr,
        )
        return 2

    from add_tbench_task_results_table import ensure_tbench_task_results_table

    ensure_tbench_task_results_table(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    try:
        # --report: print the per-category matrix from tbench_task_results and exit.
        if args.report is not None:
            report_matrix(conn, None if args.report == "__ALL__" else args.report)
            return 0

        # Resolve --category → explicit task ids (needs the dataset downloaded).
        task_ids: list[str] | None = None
        if args.task_id:
            task_ids = [args.task_id]
        elif args.category:
            cats = (
                list(SYSADMIN_CATEGORIES)
                if args.category.lower() == "sysadmin"
                else [c.strip() for c in args.category.split(",") if c.strip()]
            )
            task_ids = tasks_in_categories(args.dataset, cats)
            if not task_ids:
                print(
                    f"error: no tasks match category {cats} in {args.dataset} "
                    f"(is the dataset downloaded? run one bench first, or check the name)",
                    file=sys.stderr,
                )
                return 2
            print(f"[terminal-bench] --category {cats} → {len(task_ids)} tasks", file=sys.stderr)

        # --n-tasks is documented as "the real per-model spend bound", but tb only
        # honours it when NO -t list is passed — so `--category sysadmin --n-tasks 5`
        # silently ran the WHOLE category: an unbounded spend the operator believed was
        # capped. Bound the subset here instead (deterministically), so --n-tasks means
        # the same thing on every path. run_one then passes only -t (no --n-tasks), so
        # the bound is applied exactly once.
        if task_ids and args.n_tasks is not None and args.n_tasks < len(task_ids):
            task_ids = sorted(task_ids)[: args.n_tasks]
            print(
                f"[terminal-bench] --n-tasks {args.n_tasks} → bounding the subset to "
                f"{len(task_ids)} task(s)",
                file=sys.stderr,
            )
        # NB: task metadata (category/difficulty) is loaded by persist_task_results
        # AFTER each run — on a first run tb downloads the dataset DURING the run, so
        # capturing meta here (before it exists) would persist all-NULL categories.

        raw = [m.strip() for m in args.models.split(",") if m.strip()]
        # 'all' (any case, anywhere in the list) → the full tool-capable OR cohort.
        if any(m.lower() == "all" for m in raw):
            cohort = select_cohort(conn, None)
        else:
            cohort = select_cohort(conn, raw or DEFAULT_MODELS)

        # De-dup (preserve order) so `--models m,m` never double-runs + double-charges.
        cohort = list(dict.fromkeys(cohort))

        # Validate every id UP FRONT — before freshness/dry-run — so a malformed id
        # (from --models OR the DB) surfaces as ONE uniform loud config error (exit 2),
        # never an uncaught traceback or a masked per-model "FAILED" skip. This runs
        # before --dry-run too, so a dry-run preview also refuses a bad id.
        try:
            cohort = [_validate_model_id(m) for m in cohort]
        except ValueError as e:
            print(f"error: malformed model id in cohort — {e}", file=sys.stderr)
            return 2

        # Existence pre-check: write_tbench_score's UPDATE silently no-ops for an id
        # not in agents, so a --models id not in the catalog would bench (spend credit),
        # report success, and persist nothing — non-idempotent. Fail up front instead.
        absent = [m for m in cohort if not _model_exists(conn, m)]
        if absent:
            print(
                f"error: not in the agents catalog (import first): {', '.join(absent)}",
                file=sys.stderr,
            )
            return 2

        # Freshness skip only on a FULL default run — a targeted --category/--task-id
        # run always dispatches (resume then skips its already-completed tasks).
        if not args.force and task_ids is None:
            cohort = [m for m in cohort if not is_fresh(conn, m)]

        if args.dry_run:
            scope = (
                f"{len(task_ids)} tasks (subset)"
                if task_ids
                else (f"n_tasks={args.n_tasks}" if args.n_tasks is not None else "ALL tasks")
            )
            mode = "FRESH (--force)" if args.force else "resume-if-partial"
            print(
                f"[dry-run] would bench {len(cohort)} model(s) on {args.dataset} · {scope} · {mode}"
            )
            for m in cohort:
                print(f"[dry-run]   {m}")
            print("[dry-run] no OpenRouter calls made.")
            return 0

        if not cohort:
            print("[terminal-bench] nothing to bench (all fresh; use --force).")
            return 0

        if args.n_tasks is None and task_ids is None:
            print(
                f"[terminal-bench] ⚠ per-model task count is UNBOUNDED (full set) — a single "
                f"model may spend well before the ${args.cost_cap:.2f} run budget can stop the "
                f"cohort. Pass --n-tasks to bound per-model spend, or --dry-run first.",
                file=sys.stderr,
            )

        # Budget is tracked by ACCUMULATING each model's measured spend. `main` brackets
        # every bench_model call with balance reads (the `finally` below) so spend counts
        # even when a model FAILS after spending credit — the pass-2 fix tracked budget by
        # re-reading the global balance at the loop top, which both failed open on a blip
        # AND lost a failed model's spend. `spent is None` (balance unreadable) doesn't add:
        # known spends still bound the run, the unmeasurable part is bounded by --n-tasks.
        cohort_spent = 0.0
        benched_ok = 0
        for m in cohort:
            if cohort_spent >= args.cost_cap:
                # Budget exhausted — stop dispatching, but DON'T force exit 1: models already
                # scored are real successes. Break and let the benched_ok check set the code
                # (0 if any scored, 1 only if the run produced nothing).
                print(
                    f"[terminal-bench] STOP — run budget reached: spent "
                    f"${cohort_spent:.4f} >= cap ${args.cost_cap:.2f} before {m}",
                    file=sys.stderr,
                )
                break
            print(f"[terminal-bench] benching {m} … (run spend so far ${cohort_spent:.4f})")
            before = _balance_or_none()
            score: float | None = None
            try:
                score = bench_model(
                    conn,
                    m,
                    dataset=args.dataset,
                    n_tasks=args.n_tasks,
                    task_ids=task_ids,
                    n_concurrent=args.n_concurrent,
                    n_attempts=args.n_attempts,
                    agent_timeout_sec=args.agent_timeout,
                    run_timeout_sec=args.run_timeout,
                    force=args.force,
                )
            except MODEL_FAILURE as e:
                # tb error / hang / no-results / malformed output → skip, don't crash cohort.
                print(
                    f"[terminal-bench] {m} FAILED ({type(e).__name__}) — skipping", file=sys.stderr
                )
            finally:
                # Count spend whether the model succeeded OR failed-after-spending.
                after = _balance_or_none()
                if before is not None and after is not None:
                    model_spent = max(0.0, before - after)  # max() ignores a mid-run top-up
                    cohort_spent += model_spent
                    spent_str = f"${model_spent:.4f}"
                else:
                    spent_str = "unknown (balance unavailable)"
            if score is not None:
                benched_ok += 1
                print(f"[terminal-bench] {m}: tbench={score:.1f} spent={spent_str}")
        if cohort and benched_ok == 0:
            print(
                f"[terminal-bench] FAILED — 0 of {len(cohort)} models produced a score.",
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
