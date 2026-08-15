# Terminal-Bench runner (`microbench_terminal.py`)

**Last Updated:** 2026-07-14

Home-run [Terminal-Bench](https://www.tbench.ai/) scores for OpenRouter models — the sysadmin/terminal-agent
capability signal — instead of only scraping the public leaderboard. Sibling of `microbench_coding.py`.
Writes the task-resolution pass-rate to `agents.tbench_accuracy`.

## Runs Terminal-Bench 2.x via **harbor** (migrated 2026-07-14)

Terminal-Bench 2.x lives in a **different package** from the retired 1.x `tb` CLI: **`harbor`**.
This runner was migrated to it, because a 1.x score cannot be compared to a single entry on today's public
leaderboard — we paid for a full 80-task run before discovering that.

```bash
harbor run -d terminal-bench/terminal-bench-2-1 -a terminus -m openrouter/<id> \
    -k <n_attempts> -n <n_concurrent> -o <jobs-dir> [-t terminal-bench/<task>]…
```

Everything below was **learned from a real `oracle` run** (harbor's reference agent — it calls no LLM, so the
layout was grounded for **$0** instead of guessed):

| | |
|---|---|
| job dir | `<jobs-dir>/<job-id>/` — harbor names it `YYYY-MM-DD__HH-MM-SS`; there is **no `--job-id` flag** |
| job started | `<job>/config.json` |
| job **completed** | `<job>/result.json` ← the run-complete marker |
| one trial | `<job>/<task>__<hash>/result.json` |
| task metadata | `task.toml` (`[metadata] category`) — TB 2.x is TOML; 1.x was `task.yaml` |
| resume | `harbor job resume <job-dir>` — the **directory is the job's identity** |
| task ids | must be **org-qualified** (`terminal-bench/fix-perms`); a bare name is rejected |

**One parser, two sources.** harbor's trial `result.json` is byte-compatible with the public leaderboard's, so
`parse_trial` reads both our runs *and* the scraped leaderboard — same reward shape, same errored-vs-failed
logic. A trial whose verifier never ran (sandbox died) is **excluded from the pass-rate denominator**, not
scored 0: counting infra flakes as model failures deflates every model unlucky enough to hit them.

**Terminal-Bench 3** exists upstream (76 tasks, active) but is **not in harbor's registry**, so it cannot be
benched and the public leaderboard is still on 2.x. `dataset_freshness.py` warns about it and will start
refusing 2-1 automatically the day 3 becomes runnable.

## What it measures

Terminal-Bench drops an agent into a real Linux container per task and scores pass/fail. TB 2.1 = **89 tasks,
16 categories** (30 hard / 55 medium / 4 easy). The sysadmin workload — `system-administration` (9) +
`security` (8) — is **17 tasks**.

## Prerequisites

- `harbor>=0.18.0` (in `pyproject.toml`) → the `harbor` CLI. Hard dep: **Docker**.
- `OPENROUTER_API_KEY` in `/opt/fabrik/.env` (models route as `openrouter/<id>`).
- **OpenRouter credit headroom** — a real run costs credit. `--dry-run` first.
- Tasks: `harbor download terminal-bench/terminal-bench-2-1 -o ~/.cache/harbor/tasks`.

## Usage

```bash
cd /opt/fabrik/scripts/kilo-benchmarks

# Preview — no model calls, no cost:
python microbench_terminal.py --dry-run

# The 17-task SYSADMIN subset (what you actually care about for a sysadmin agent):
python microbench_terminal.py --models z-ai/glm-5 --category sysadmin --cost-cap 5

# Default cohort = the sub-$2 candidates with a TB2 score but no per-task profile:
python microbench_terminal.py --category sysadmin --cost-cap 8

# Per-category capability matrix (no benching):
python microbench_terminal.py --report
```

Flags: `--models` (comma list, or `all`) · `--cost-cap` (cohort budget) · `--n-tasks` (`> 0`) / `--task-id` ·
`--category` (`sysadmin` = system-administration + security) · `--n-concurrent` · `--n-attempts` (harbor `-k`) ·
`--dataset` · `--force` · `--report [model]` · `--dry-run` · `--allow-stale`.

**Runtime, from glm-5's real leaderboard trials:** median **5.6 min/task**, but one task takes **44 min** — the
slowest task is the floor, so concurrency past ~4 buys nothing. Budget **~1 h** for the 17-task sysadmin subset
at k=1 (~$2 at glm-5 prices).

## Resumable

An interrupted run resumes automatically: the runner finds the unfinished job (a `config.json` with no
`result.json`) and calls `harbor job resume <job-dir>` — completed trials are not re-run, so **no credit is
re-spent on finished work**. `--force` discards it and starts fresh. Launch long runs detached
(`setsid nohup … &`) so a session teardown never kills them.

**A FINISHED job is READ, never re-run.** harbor writes the job-level `result.json` only on completion, so its
presence is the run-complete marker. Re-invoking on a completed job costs **$0** — the runner parses it and
(re)persists the score. This is the second line of defence behind the freshness skip, and it exists because the
first has a hole: `tbench_accuracy` is written *after* the run finishes, so a process killed in between leaves a
**complete run behind a NULL score**. That hole cost a real 3-hour re-run — `docs/LESSONS_LEARNT.md` Lesson 94.

The run dir is keyed on **(model, dataset, task-set, n_tasks, n_attempts, agent-timeout, agent)** — everything
that changes a *result* — so a changed flag never silently resumes a differently-configured run.
`--n-concurrent` is deliberately excluded: it changes speed, not results.

## Per-task detail + category profile (the aggregate lies)

The aggregate `tbench_accuracy` **hides the category profile** — minimax-m3 scored 34% overall but only
**15% at system-administration**, while `z-ai/glm-5` scores **72% sysadmin vs 54% overall** (it fails `configure-git-webserver`, `cron-broken-network`, `fix-permissions`,
`nginx-request-logging`, …). So a single number is misleading for role-specific selection.

Every run persists one row per (model, task) to the **`tbench_task_results`** table — `category`, `difficulty`,
`is_resolved`, `failure_mode` (`errored` when the sandbox died before the verifier ran), `duration_s` — joined
from each task's `task.toml`. This survives re-runs and is comparable across models.

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
  Real categories (TB 2.1, 89 tasks / 16 categories): software-engineering (26), system-administration (9),
  scientific-computing (8), security (8), data-science (8), debugging (5), file-operations (5),
  model-training (4), mathematics (4), data-processing (4), machine-learning (3), plus games,
  personal-assistant, optimization, data-querying, video-processing (1 each).
  The alias `sysadmin` = `system-administration,security` = **17 tasks**.
  A different `--category` is a different task-set, so it gets its own run dir automatically — no `--force`
  needed. `--n-tasks` **also bounds a `--category` run** (`--category sysadmin --n-tasks 5` runs 5 of the 25,
  not all 25): tb only honours `--n-tasks` when no `-t` list is passed, so the runner applies the bound to the
  task list itself.

## ⚠️ Home score ≠ public leaderboard score

Terminal-Bench scores an *agent* = model + harness. Our runs use `terminus` under our own harbor invocation, so
the numbers are a **relative comparison across our candidates under one identical harness** — not byte-identical
to the public leaderboard, whose entries use bespoke tuned scaffolds (vix, LemonHarness, NexAU-AHE). Use home
scores to rank *our* candidates against each other; use `scrape_tbench_task_results.py` for the public
per-category matrix.

## Not a daily job

On-demand only — a full core-set run is minutes + credit per model, far too heavy for `daily_refresh.sh`. The
daily leaderboard *scrape* (`scrape_benchmarks.py`) is unaffected and remains the bulk-coverage source.

## Related

- `/opt/ai-model-catalog/engine/microbench_terminal.py` — the runner.
- `/opt/ai-model-catalog/engine/scrape_benchmarks.py` — scrapes the public tbench.ai leaderboard into `tbench_accuracy`.
- `/opt/ai-model-catalog/engine/scrape_tbench_task_results.py` — the public per-task/per-category results matrix into `tbench_task_results`.
- `/opt/ai-model-catalog/engine/compute_assignments.py` / `category_selector.py` / `llm_selector.py` — consume
  `tbench_accuracy`; their sorts place unbenched (NULL) models below real 0-scorers (plan-1 Phase C).
