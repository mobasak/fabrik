#!/usr/bin/env python3
# AFTER-EDIT: scripts/kilo-benchmarks/tests/test_microbench_terminal.py docs/reference/terminal-bench-runner.md
"""Home-run Terminal-Bench (Linux-sysadmin capability) scoring for OpenRouter models.

Runs the **current** benchmark: Terminal-Bench 2.x via **harbor** — a DIFFERENT PACKAGE from
the retired 1.x `tb` CLI this runner was originally built on. That migration is the whole
point: a 1.x score cannot be compared to a single entry on today's public leaderboard, and
we paid for a full 80-task run before discovering it.

Grounded invocation (verified live with a FREE `oracle` run — no LLM, no spend):
    harbor run -d terminal-bench/terminal-bench-2-1 -a terminus -m openrouter/<id> \
        -k <n_attempts> -n <n_concurrent> -o <jobs-dir> [-t terminal-bench/<task>]…

Layout it produces (learned, not assumed):
    <jobs-dir>/<job-id>/                     job-id = 'YYYY-MM-DD__HH-MM-SS' (harbor names it)
        config.json                          job STARTED
        result.json                          job COMPLETED  <- the run-complete marker
        <task>__<hash>/result.json           one TRIAL

The TRIAL file is byte-compatible with the public leaderboard's, so ONE parser
(`parse_trial`) reads both our runs and the scraped leaderboard — the same
errored-vs-failed logic, the same reward shape.

Scoring: pass-rate over the trials that actually RAN. An **errored** trial (the sandbox died
before the verifier ran) is excluded from the denominator rather than scored 0 — counting
infra flakes as model failures deflates every model unlucky enough to hit them.

Cost: measured via the OpenRouter balance-delta (`GET /api/v1/credits`). `--cost-cap` is a
**cohort** budget checked BEFORE each model; it cannot interrupt a model mid-flight, so the
real per-model bound is `--n-tasks` / `--category`.

Resume: `harbor job resume <job-dir>` — the job DIRECTORY is the job's identity (harbor has
no --job-id flag). A FINISHED job is READ, never re-run.

Dataset freshness is enforced before any model is dispatched (`dataset_freshness.py`): a
superseded dataset is refused, because a score is only meaningful relative to the task set
it was measured on.

On-demand only — NOT in daily_refresh.sh (agentic loops cost minutes + credit per model).
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
from datetime import date, datetime

import httpx
from dataset_freshness import StaleDatasetError, check_dataset_fresh
from dotenv import load_dotenv

SCRIPT_DIR = pathlib.Path(__file__).parent
DB_PATH = SCRIPT_DIR / "kilo_agents.db"
CACHE_DIR = SCRIPT_DIR / "cache"

# --- Grounded constants (harbor; verified live 2026-07-14 with a FREE oracle run) ------
# Terminal-Bench 2.x is a DIFFERENT PACKAGE from the retired 1.x `tb` CLI: `harbor`.
#   harbor run -d terminal-bench/terminal-bench-2-1 -a terminus -m openrouter/<id>
#              -k <n_attempts> -n <n_concurrent> -o <jobs-dir> [-t terminal-bench/<task>]…
# Layout it produces (learned from a real oracle run, not assumed):
#   <jobs-dir>/<job-id>/                     job-id = 'YYYY-MM-DD__HH-MM-SS'
#       result.json                          JOB-level: written only when the job COMPLETES
#       <task>__<hash>/result.json           TRIAL-level
# The TRIAL result.json is byte-compatible with the public leaderboard's, so
# scrape_tbench_task_results.parse_trial() reads both — one parser, two sources.
TB_CLI = "harbor"
TB_AGENT = "terminus"
TB_DATASET = "terminal-bench/terminal-bench-2-1"
OPENROUTER_CREDITS_URL = "https://openrouter.ai/api/v1/credits"

# harbor writes result.json (SINGULAR) at both levels. The JOB-level one appears only when
# the job COMPLETES, so it is the run-complete marker (the role tb's results.json played).
JOB_RESULT = "result.json"

# Where `harbor download` puts task definitions (they carry the category we slice on).
HARBOR_TASKS_DIR = pathlib.Path.home() / ".cache" / "harbor" / "tasks"

# The sub-$2 sysadmin candidates with a TB2 score but NO per-task profile — the ones a
# bench actually teaches us something about (glm-5 is already measured at 72%).
DEFAULT_MODELS = [
    "xiaomi/mimo-v2.5-pro",
    "deepseek/deepseek-v4-pro",
    "xiaomi/mimo-v2.5",
]

# The task categories that matter for a fleet-sysadmin agent — used by
# --category sysadmin as a convenience alias for the on-workload subset.
SYSADMIN_CATEGORIES = ("system-administration", "security")


def _dataset_dir(dataset: str) -> pathlib.Path:
    """Local task dir for a harbor dataset: 'terminal-bench/terminal-bench-2-1' →
    ~/.cache/harbor/tasks/terminal-bench-2-1 (where `harbor download -o` puts it)."""
    return HARBOR_TASKS_DIR / dataset.split("/")[-1]


def _legacy_dataset_dir(dataset: str) -> pathlib.Path:
    """The retired `tb` 1.x layout — kept only for --allow-stale reproductions."""
    name, _, ver = dataset.partition("==")
    return pathlib.Path.home() / ".cache" / "terminal-bench" / name / (ver or "head")


_TASK_META_CACHE: dict[str, dict[str, dict]] = {}


def load_task_meta(dataset: str) -> dict[str, dict]:
    """Map task_id → {'category', 'difficulty'} from each task's manifest.

    Terminal-Bench 2.x ships **task.toml** (`[metadata] category`); the retired 1.x set
    used task.yaml. Both are read, so an --allow-stale 1.x reproduction still slices by
    category.

    Returns {} if the dataset isn't on disk yet (harbor fetches it on the first run).

    Memoized per dataset so an N-model cohort parses the ~89 manifests once, not once per
    model. ⚠️ Only a NON-EMPTY result is cached: `{}` means the dataset is not on disk YET
    (it is downloaded DURING the first run), so caching that would pin every later persist
    to all-NULL categories. An empty read stays retryable.
    """
    cached = _TASK_META_CACHE.get(dataset)
    if cached:
        return cached

    meta: dict[str, dict] = {}
    for ddir, pattern in (
        (_dataset_dir(dataset), "*/task.toml"),
        (_legacy_dataset_dir(dataset), "*/task.yaml"),
    ):
        if not ddir.exists():
            continue
        for tf in sorted(ddir.glob(pattern)):
            try:
                if tf.suffix == ".toml":
                    m = tomllib.loads(tf.read_text()).get("metadata", {})
                else:
                    import yaml

                    m = yaml.safe_load(tf.read_text()) or {}
                meta[tf.parent.name] = {
                    "category": m.get("category"),
                    "difficulty": m.get("difficulty"),
                }
            except (OSError, ValueError, tomllib.TOMLDecodeError):
                meta[tf.parent.name] = {"category": None, "difficulty": None}
        if meta:
            break

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


def _find_complete_run(out_dir: pathlib.Path) -> str | None:
    """The newest run-id under out_dir that is FINISHED — it has a top-level results.json.

    tb writes ``<run>/results.json`` only when the whole run completes, so its presence is
    the run-complete marker. A finished run has NOTHING left to resume, and resuming it
    anyway re-dispatches its tasks and re-spends OpenRouter credit for zero new results.

    This cost real money (2026-07-14): a run finished at 04:57 but its runner process was
    killed before it could write the score, leaving ``tbench_accuracy`` NULL — so the
    freshness guard didn't skip the model, ``_find_resumable_run`` matched the completed
    run's still-present ``tb.lock``, and the relaunch re-ran finished tasks for ~3h and
    produced not one new results.json. A completed run must be READ, never re-run.
    """
    if not out_dir.exists():
        return None
    done = sorted(p.name for p in out_dir.iterdir() if p.is_dir() and (p / JOB_RESULT).exists())
    return done[-1] if done else None


def _find_resumable_run(out_dir: pathlib.Path) -> str | None:
    """The newest run-id under out_dir that is resumable: it has a tb.lock AND is NOT
    finished (no top-level results.json).

    The tb.lock alone is NOT sufficient — it is a persistent manifest that outlives the
    run, so a COMPLETED run still carries one. Keying resumability on the lock alone is
    what re-ran a finished run (see ``_find_complete_run``). Resumable == has work left.

    out_dir is per-(model, scope), so any run in it shares this model+task-set —
    resume is safe. Returns the run-id (dir name) or None if nothing to resume.
    """
    if not out_dir.exists():
        return None
    # harbor writes no lock file; a job dir with a config.json but NO job-level result.json
    # is one that started and did not finish — i.e. it has work left.
    runs = sorted(
        p.name
        for p in out_dir.iterdir()
        if p.is_dir() and (p / "config.json").exists() and not (p / JOB_RESULT).exists()
    )
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
    env = {**os.environ}

    # RESUME. `harbor job resume` takes the JOB DIRECTORY, so the directory IS the job's
    # identity — there is no --job-id to hand it, and none to hand `harbor run` either.
    # (The 1.x runner generated its own --run-id precisely so the id was an INPUT, never a
    # guess; harbor removes that option, so instead we diff the dir listing — but ONLY
    # around a fresh run we just started, and we return the dir that appeared.)
    prior = _find_resumable_run(out_dir) if resume else None
    if prior:
        argv = [TB_CLI, "job", "resume", str(out_dir / prior)]
        subprocess.run(argv, check=True, env=env, timeout=run_timeout_sec)  # noqa: S603
        return prior

    out_dir.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in out_dir.iterdir() if p.is_dir()}
    argv = [
        TB_CLI,
        "run",
        "-d",
        dataset,
        "-a",
        TB_AGENT,
        "-m",
        f"openrouter/{model_id}",
        "-k",
        str(n_attempts),
        "-n",
        str(n_concurrent),
        "-o",
        str(out_dir),
    ]
    # harbor requires ORG-QUALIFIED task ids ('terminal-bench/fix-perms'), and rejects a
    # bare name with a pydantic error — grounded by a real (failing) run, not assumed.
    org = dataset.split("/")[0]
    for t in task_ids or []:
        argv += ["-t", t if "/" in t else f"{org}/{t}"]
    if not task_ids and n_tasks is not None:
        argv += ["--n-tasks", str(n_tasks)]
    subprocess.run(argv, check=True, env=env, timeout=run_timeout_sec)  # noqa: S603

    # harbor names the job dir 'YYYY-MM-DD__HH-MM-SS' itself. Take the one that APPEARED —
    # scoped to this call, so a stale sibling job in the same out_dir can never be
    # mistaken for ours (that misattribution is what cost a 3-hour re-run on the 1.x path).
    after = [p for p in out_dir.iterdir() if p.is_dir() and p.name not in before]
    if not after:
        return None  # harbor exited 0 but produced no job → a per-model failure
    return max(after, key=lambda p: p.stat().st_mtime).name


def parse_trial(d: dict) -> dict | None:
    """One harbor/leaderboard trial result.json -> {task_id, passed, errored, cost_usd}.

    harbor's trial file is byte-compatible with the public leaderboard's, so this is the
    SAME parse the scraper uses — one code path, two sources.

    An UNMEASURED trial is not a failed one: `verifier_result: null` (or any unusable
    reward) means the sandbox died before the verifier ran, so we learned nothing about the
    model. Those are marked errored and dropped from the pass-rate denominator; scoring them
    0 would deflate every model that hit flaky infra.
    """
    task_id = (d.get("task_name") or "").split("/")[-1]
    if not task_id:
        return None
    cost = (d.get("agent_result") or {}).get("cost_usd")
    rewards = (d.get("verifier_result") or {}).get("rewards")
    reward = rewards.get("reward") if isinstance(rewards, dict) else None
    if not isinstance(reward, (int, float)) or isinstance(reward, bool):
        return {"task_id": task_id, "passed": False, "errored": True, "cost_usd": cost}
    return {
        "task_id": task_id,
        "passed": reward == 1.0,  # partial credit is not a pass on this benchmark
        "errored": False,
        "cost_usd": cost,
    }


def parse_tbench_output(out_dir: pathlib.Path, run_id: str | None = None) -> float:
    """Read a completed job -> pass-rate as 0-100.

    Computed from the TRIALS rather than harbor's own summary block: the trial files are the
    primary record and they carry the errored-vs-failed distinction, which the summary's
    mean does not.

    Requires the JOB-level result.json (harbor writes it only on completion). Raises
    FileNotFoundError if the job never finished or produced no scored trials, ValueError if
    a trial is unreadable — the caller treats both as a per-model failure, not a cohort crash.
    """
    if run_id is not None:
        job = out_dir / run_id
        if not (job / JOB_RESULT).exists():
            raise FileNotFoundError(f"job {run_id} has no {JOB_RESULT} (it did not finish)")
    else:
        jobs = sorted(out_dir.glob(f"*/{JOB_RESULT}"), key=lambda q: q.stat().st_mtime)
        if not jobs:
            raise FileNotFoundError(f"no completed job under {out_dir}")
        job = jobs[-1].parent

    passed = scored = 0
    for tr in sorted(job.glob(f"*/{JOB_RESULT}")):  # <task>__<hash>/result.json
        try:
            t = parse_trial(json.loads(tr.read_text()))
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"unreadable trial {tr}: {e}") from e
        if not t or t["errored"]:
            continue  # unmeasured — excluded from the denominator, not scored 0
        scored += 1
        passed += bool(t["passed"])
    if not scored:
        raise FileNotFoundError(f"job {job.name} produced no scored trials")
    return passed / scored * 100.0


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
    s, e = d.get("started_at"), d.get("finished_at")  # harbor's field names
    if not s or not e:
        return None
    try:
        return (
            datetime.fromisoformat(e.replace("Z", "+00:00"))
            - datetime.fromisoformat(s.replace("Z", "+00:00"))
        ).total_seconds()
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
    for tr in sorted((out_dir / run_id).glob(f"*/{JOB_RESULT}")):  # <task>__<hash>/result.json
        try:
            d = json.loads(tr.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        t = parse_trial(d)
        if not t:
            continue
        tid = t["task_id"]
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
                # From parse_trial, NOT d["is_resolved"]: that was tb's field and harbor has
                # no such key, so reading it made every row silently resolved=0 — a persisted
                # 0% while the parsed pass-rate said 100%.
                1 if t["passed"] else 0,
                # harbor has no failure_mode. An UNMEASURED trial is recorded as 'errored' so
                # it can never be read back as a genuine failure.
                "errored" if t["errored"] else None,
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

    # A FINISHED run is READ, never re-run. tb's own resume would re-dispatch its tasks
    # and re-spend credit for zero new results. This is not hypothetical: it happened,
    # for ~3h, because the aggregate write is what marks a model "fresh" — and a run
    # whose process was killed AFTER tb finished but BEFORE the score was persisted
    # leaves a complete run behind a NULL tbench_accuracy. The freshness guard can't see
    # it; only the run dir can. Reading it here also makes the whole call idempotent:
    # re-invoking on a finished run now costs $0 and simply (re)persists the score.
    if not force:
        done = _find_complete_run(out_dir)
        if done:
            score = parse_tbench_output(out_dir, done)
            print(
                f"[terminal-bench] {model_id}: run {done} already COMPLETE "
                f"({score:.1f}) — reusing it, no credit spent (--force to re-bench).",
                file=sys.stderr,
            )
            if task_ids is None and n_tasks is None:
                write_tbench_score(conn, model_id, score)
            try:
                persist_task_results(conn, model_id, out_dir, dataset, done, task_meta)
            except Exception as e:  # noqa: BLE001 — best-effort; the score must survive
                print(
                    f"[terminal-bench] per-task persist failed for {model_id} "
                    f"({type(e).__name__}: {e}) — score kept",
                    file=sys.stderr,
                )
            return score

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
    p.add_argument(
        "--allow-stale",
        action="store_true",
        help="Bench even though the dataset has been SUPERSEDED. Only for deliberately "
        "reproducing an old score — the result will not be comparable to the current "
        "leaderboard. Without this, a stale dataset is refused before any credit is spent.",
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

    # ⚠️ ALWAYS check the dataset is the CURRENT one before benching anything.
    # A score is only meaningful relative to its dataset, so a run against a superseded
    # one produces a number that looks authoritative and compares to nothing. We shipped
    # exactly that: pinned to terminal-bench-core==0.1.1 (the launch-era 1.x set) long
    # after the benchmark moved to 2.x in a different package — and paid for a full
    # 80-task run whose score matched no leaderboard on earth. A pin never tells you it
    # has been superseded; you have to ASK, live, every time. This is that ask, and it
    # runs BEFORE a single model is dispatched (i.e. before any credit is spent).
    try:
        check_dataset_fresh("terminal-bench", args.dataset, allow_stale=args.allow_stale)
    except StaleDatasetError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

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
