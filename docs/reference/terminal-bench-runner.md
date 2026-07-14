# Terminal-Bench runner (`microbench_terminal.py`)

**Last Updated:** 2026-07-13

Home-run [Terminal-Bench](https://www.tbench.ai/) scores for OpenRouter models — the sysadmin/terminal-agent
capability signal — instead of only scraping the public leaderboard. Sibling of `microbench_coding.py`.
Writes the task-resolution pass-rate to `agents.tbench_accuracy`.

## What it measures

Terminal-Bench drops an agent into a real Linux container per task and scores whether it completes the task
(pass/fail → resolution rate). Categories include system administration, security, software engineering, ML,
data science. `accuracy` (0.0–1.0) in the harness `results.json` × 100 = our `tbench_accuracy`.

## Prerequisites

- `terminal-bench>=0.2.18` (in `pyproject.toml`) → the `tb` CLI. Hard deps: **Docker** + **uv** (both must be
  on the host running the bench).
- `OPENROUTER_API_KEY` in `/opt/fabrik/.env` (the harness routes models via LiteLLM `openrouter/<id>`).
- **OpenRouter credit headroom** — a real run costs credit (agentic loops). Check `--dry-run` first; top up if low.

## Usage

```bash
cd /opt/fabrik/scripts/kilo-benchmarks
export PATH="/opt/fabrik/.venv/bin:$PATH"; set -a; source /opt/fabrik/.env; set +a

# Preview (no model calls, no cost):
python microbench_terminal.py --dry-run

# Bench the default unbenched sysadmin cohort (minimax-m3, glm-5.2, deepseek-v4-pro), full task set:
python microbench_terminal.py --cost-cap 5

# Bench specific models on a bounded task count (cheaper):
python microbench_terminal.py --models deepseek/deepseek-v4-pro,z-ai/glm-5.2 --n-tasks 20 --cost-cap 3

# Every tool-capable OpenRouter model (expensive — use with care):
python microbench_terminal.py --models all --cost-cap 5
```

Flags: `--models` (comma list, or `all`; default = the 3 unbenched sysadmin candidates) · `--cost-cap`
(total run/cohort budget) · `--n-tasks` / `--task-id` (bound the work per model) · `--category`
(run only these task categories) · `--n-concurrent` (default 4) · `--n-attempts` (trials per task) ·
`--dataset` (default `terminal-bench-core==0.1.1`) · `--force` (wipe + fresh; default RESUMES a partial run) ·
`--report [model]` (print the per-category matrix, no benching) · `--dry-run`.

## Resumable

A killed or interrupted run (session restart, `Ctrl-C`, a crash) is **resumed automatically** on the next
invocation — `microbench_terminal.py --models <same model>` detects the partial run and calls
`tb runs resume`, which **skips completed tasks and re-runs only the incomplete ones — no OpenRouter credit is
re-spent on finished work.** Use `--force` to discard the prior run and start fresh (this also re-enables the
stale-score guard, since a fresh run can't read a prior results.json). Long runs should still be launched
detached (`setsid nohup … &`) so a session teardown never kills them.

## Per-task detail + category profile (the aggregate lies)

The aggregate `tbench_accuracy` **hides the category profile** — minimax-m3 scored ~36% overall but only
**10% at system-administration** (it fails `configure-git-webserver`, `cron-broken-network`, `fix-permissions`,
`nginx-request-logging`, …). So a single number is misleading for role-specific selection.

Every run persists one row per (model, task) to the **`tbench_task_results`** table — `category`, `difficulty`,
`is_resolved`, `failure_mode` (`agent_timeout`/`parse_error`/`test_timeout`/…), `duration_s` — joined from each
task's `task.yaml`. This survives re-runs and is comparable across models.

- **`--report`** prints the per-category pass-rate matrix from the table:
  ```bash
  python microbench_terminal.py --report                    # all benched models
  python microbench_terminal.py --report minimax/minimax-m3 # one model
  ```
- **`--category`** runs only the relevant subset (cheaper + on-workload):
  ```bash
  # sysadmin agent selection — 25 tasks (system-administration + security), not the full 80:
  python microbench_terminal.py --models glm-5.2 --category sysadmin --cost-cap 5
  ```
  Real categories (task counts in terminal-bench-core 0.1.1): system-administration (13), security (12),
  software-engineering (17), debugging (10), file-operations (8), data-science (8), model-training (7),
  games (3), scientific-computing (2). The alias `sysadmin` = `system-administration,security`. Changing
  `--category` on an already-run model needs `--force` (the per-model run dir resumes its original task set).

## How it works (grounded invocation)

Per model: `tb run -a terminus-2 -m openrouter/<id> -d terminal-bench-core==0.1.1 --n-concurrent N
--output-path <dir> --no-upload-results --cleanup`. Reads `<dir>/<run-id>/results.json → accuracy × 100`,
writes it to `agents.tbench_accuracy` + `last_verified`.

- **Cost** is measured via the OpenRouter **balance-delta** (`GET /api/v1/credits` before/after) — the
  harness's own `total_*_tokens` are `0`, so token counts are unusable. Graceful: a credits-API blip never
  loses a completed run's score.
- **Freshness** is keyed on `tbench_accuracy` *presence* (a model with a score is skipped unless `--force`) —
  **not** `last_verified`, which the daily price scrapers overload on every active model.
- **Shell-out safety**: the model_id is validated (`^[A-Za-z0-9][A-Za-z0-9./_:-]*$`) before it is interpolated
  into the argv; the subprocess is never `shell=True`.

## ⚠️ Home score ≠ public leaderboard score

Terminal-Bench scores an *agent* = model + harness. Our runs use `terminus-2` + `terminal-bench-core==0.1.1`
under our own harness invocation, so the numbers are a **relative comparison across our candidates under one
identical harness**, not byte-identical to `tbench.ai`'s leaderboard (which uses its own harness version/runs).
Use home scores to rank *our* OpenRouter candidates against each other; use the scraped leaderboard
(`scrape_benchmarks.py`) for the public frontier comparison.

## Not a daily job

On-demand only — a full core-set run is minutes + credit per model, far too heavy for `daily_refresh.sh`. The
daily leaderboard *scrape* (`scrape_benchmarks.py`) is unaffected and remains the bulk-coverage source.

## Related

- `scripts/kilo-benchmarks/microbench_terminal.py` — the runner.
- `scripts/kilo-benchmarks/scrape_benchmarks.py` — scrapes the public tbench.ai leaderboard into `tbench_accuracy`.
- `scripts/kilo-benchmarks/compute_assignments.py` / `category_selector.py` / `llm_selector.py` — consume
  `tbench_accuracy`; their sorts place unbenched (NULL) models below real 0-scorers (plan-1 Phase C).
