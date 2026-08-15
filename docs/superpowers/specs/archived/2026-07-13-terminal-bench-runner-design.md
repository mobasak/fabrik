# Terminal-Bench runner — home-bench Linux-sysadmin capability into the kilo-benchmarks pipeline — design spec

**Status:** CONVERGED
**Date:** 2026-07-13
**Converged:** 2026-07-13 (/fabrik-spec-review — 3 passes to an edit-free md5-verified no-op; live re-verified every cited URL, corrected the load-bearing OpenRouter fact's attribution from the terminal-bench README to the Harbor/LiteLLM docs, swapped the bot-403 openreview /pdf link for the 200 forum page, and adjudicated the two near-neighbour fabrik-lib modules (subagents, claude-evaluator) the DRAFT was silent on. md5 `2a72432681ac57ea00a58357ac38fac6`)
**Author:** primary (this session)

## Goal

Give the kilo-benchmarks pipeline the ability to **generate** Terminal-Bench scores itself, instead of only *scraping* the public `tbench.ai` leaderboard. Today `scrape_benchmarks.py` copies leaderboard rows into `agents.tbench_accuracy`, which leaves the newest models (e.g. `minimax/minimax-m3`, `z-ai/glm-5.2`, `deepseek/deepseek-v4-pro`) with **no sysadmin capability signal** — nobody has submitted them to the public leaderboard yet. This blocks the operator's real decision: *"which cheap OpenRouter model is actually a competent Linux sysadmin?"* The deliverable is `microbench_terminal.py` — a thin adapter that runs the official Terminal-Bench harness against OpenRouter-routed models and writes the resulting pass-rate to `agents.tbench_accuracy`, mirroring how `microbench_coding.py` runs EvalPlus and writes `humaneval_score`.

**Concretely it must:** run the Terminal-Bench task set against a configurable cohort of `via_openrouter=1` models, capture each model's task-resolution pass-rate, and write it to `agents.tbench_accuracy` — with cost caps, a dry-run cost estimate, and a `--models` cohort selector, so the operator can bench the three unbenched sysadmin candidates and compare them on evidence.

## Chosen approach — VENDOR the official `terminal-bench` CLI + BUILD a thin adapter (mirror microbench_coding.py)

**Composition (one new script + one deps addition + one ranking-bug fix):**

1. **`engine/microbench_terminal.py`** (new, ~250 LOC) — mirrors `microbench_coding.py`'s structure:
   - Cohort query: `SELECT id FROM agents WHERE via_openrouter=1 AND status='active' AND has_tools=1` (a sysadmin agent must call tools) filtered by `--models` if given.
   - For each target model, shell out to the Laude harness CLI with `terminus-2` (the default agent used in TerminalBench 2.0) and the OpenRouter-routed model: `subprocess.run([<cli>, "run", "--agent", "terminus-2", "--model", f"openrouter/{model_id}", "--dataset-name", "terminal-bench-core", "--dataset-version", "<pinned>", "--n-concurrent", str(N), "--output-path", <run_dir>])` with `OPENROUTER_API_KEY` in the subprocess env (read from `.env` via `load_dotenv()`). `<cli>` is `tb` or `harbor` — **pin at plan Phase A** (the documented `--model openrouter/...` example is `harbor run`; Terminal-Bench 2.0's harness IS Harbor/terminus-2, and both use LiteLLM so both accept `openrouter/` strings — Phase A confirms which CLI the installed package exposes via `--help`).
   - Parse the harness's run-output JSON → resolved/total → `pass_rate * 100`.
   - `UPDATE agents SET tbench_accuracy = ?, last_verified = ? WHERE id = ?` (column already exists — **no migration**).
   - Flags: `--models` (comma list, default = the unbenched-tool-capable cohort), `--cost-cap` (per-model USD ceiling, abort model if exceeded), `--trials` (default 1; >1 reports mean pass-rate for reliability), `--task-filter` (optional category/id subset — default full core set), `--dry-run` (print dispatch plan + estimated cost/time, do NOT call OR).
   - Idempotent per row (re-benching overwrites the score + `last_verified`).

2. **`requirements.txt` / `pyproject.toml`** (modify — **needs plan authorization per CLAUDE.md deps rule**) — add `terminal-bench` (Apache-2.0 pip package; pulls its own LiteLLM). `uv` + Docker are already present system-wide (verified: Docker 29.1.3, uv 0.11.16) — no manifest entry, they're system toolchain.

3. **`engine/derive_quality_v2.py` (or the ranking queries)** (modify, ~2 LOC delta) — fix the NULL-ranking footgun this work exposed: `COALESCE(tbench_accuracy, 0) DESC` sorts *unbenched* models to worst, structurally burying the newest models. Change ranking gates to treat NULL as "unranked" (exclude from the tbench-ordered sort, don't score them 0). Grep-audit `category_selector.py:119`, `compute_assignments.py`, and any other `COALESCE(...tbench...,0)` site.

**Invocation model:** operator-triggered / on-demand only. **NOT wired into `daily_refresh.sh`** — a full core-set run is minutes of wall-time and dollars of OR spend per model (agentic loops), far too heavy for a daily cron. The daily leaderboard *scrape* (`scrape_benchmarks.py`) stays; this tool fills gaps the scrape can't cover.

**Runtime environment:** runs hub-side / WSL dev where Docker + uv live. Terminal-Bench spins one Docker container per task; `--n-concurrent` bounds parallelism. `terminus-2` (the Harbor-generation harness) is the default agent scaffold; `--model openrouter/<id>` forces **all** model traffic through OpenRouter (constraint-compliant).

## Rejected alternatives

1. **Reimplement the Terminal-Bench harness ourselves** (our own Docker task runner + task set + scorers) — Rejected. Terminal-Bench IS the standard (ICLR 2026), it's actively maintained (Terminal-Bench 3.0 in development) and Apache-2.0. Reimplementing guarantees **non-comparable scores** and a large permanent maintenance burden for zero benefit. Violates "build where consume exists."

2. **Extend `microbench_coding.py` to add a "terminal" dataset** — Rejected. `microbench_coding.py` runs EvalPlus in a **bwrap** sandbox; Terminal-Bench needs **Docker** orchestration + its own agentic harness. The two eval models are structurally different; force-fitting them into one script muddies both. A separate sibling script matches the existing precedent (`microbench_or_models.py` / `microbench_specialty.py` / `microbench_coding.py` are already separate by eval type).

3. **Use LiteLLM/OpenRouter but write a custom minimal agent instead of `terminus-2`** — Rejected. Terminal-Bench's value is the *standard harness + task set + programmatic scorers*; swapping in a home-grown agent scaffold would make our scores incomparable to anything and re-introduce the reimplementation cost. Use the harness's own agent; vary only the `--model`.

## External dependencies (all live-grounded this session, 2026-07-13)

| Dependency | Fact | Source (fetched 2026-07-13) |
|---|---|---|
| terminal-bench package | `pip install terminal-bench` → provides the `tb` CLI harness. Apache-2.0. Hard deps: **Docker + uv**. | `https://github.com/laude-institute/terminal-bench` README + `https://github.com/laude-institute/terminal-bench/blob/main/LICENSE` (Apache 2.0 confirmed verbatim) |
| tb run command | `tb run --agent terminus --model <litellm-string> --dataset-name terminal-bench-core --dataset-version 0.1.1 --n-concurrent 8` | GitHub README (quoted verbatim) |
| Model routing (OpenRouter) | **Harbor** (the framework released alongside Terminal-Bench 2.0, same Laude Institute; it rewrote the original TB harness) uses **LiteLLM** for model calls → native `openrouter/<provider>/<model>` strings + `OPENROUTER_API_KEY` env. Documented example: `export OPENROUTER_API_KEY=...` then `harbor run --agent "terminus-2" --model "openrouter/google/gemini-3-pro-preview"`. **NOTE: the `terminal-bench` README itself does NOT mention OpenRouter/LiteLLM — this fact is sourced from the Harbor docs**, and since both TB and Harbor route through LiteLLM, `openrouter/` strings work on either CLI. **LiteLLM is a router, not a direct vendor SDK → satisfies the OpenRouter-only constraint.** | Harbor: `https://github.com/laude-institute/harbor` + LiteLLM's Harbor page `https://docs.litellm.ai/docs/projects/Harbor` + LiteLLM OpenRouter provider `https://docs.litellm.ai/docs/providers/openrouter` (all live 2026-07-13; the `harbor run … --model "openrouter/…"` example quoted verbatim) |
| Dataset | `terminal-bench-core` v0.1.1 ≈ 100 tasks (beta). The public leaderboard we scrape is **v2.0 = 89 tasks**. Dataset is fetched by the harness (`--dataset-name` + `--dataset-version`). | GitHub README + `tbench.ai/leaderboard/terminal-bench/2.0` (scraped by our `scrape_benchmarks.py:91`) |
| Scoring | Pass/fail per task via a programmatic success function checking the container's final state; score = task-resolution success-rate. | `tbench.ai` (fetched this session) + ICLR 2026 paper forum `https://openreview.net/forum?id=a7Qa4CcHak` (the `/pdf` direct link 403s to bots; the forum abstract page resolves 200 and states the pass/fail methodology) |
| Agents (scaffolds) | `terminus` (v1) and `terminus-2` (**the default agent used in TerminalBench 2.0**; Harbor generation — "rewrites the harness for reliability/observability/scalability"). Harbor also supports headless Claude Code / Codex / Cursor CLI agents, but those call vendors directly — **we pin `terminus-2` + `--model openrouter/<id>` so all model traffic routes through OpenRouter.** | GitHub README + Harbor docs (`https://github.com/laude-institute/harbor`) |
| Dev-env readiness | Docker **29.1.3** daemon reachable · uv **0.11.16** · `OPENROUTER_API_KEY` present in `/opt/fabrik/.env`. All three tb hard-deps satisfied. | live probe this session (`docker --version`/`docker ps`/`uv --version`/grep .env) |

**Cost/time envelope (design constraint, not a blocker):** each task is a full agentic loop (terminus-2 drives a shell over many turns), so one model × full core set (~89–100 tasks) is on the order of minutes–tens-of-minutes wall time and single-digit-to-low-tens USD of OR spend, depending on the model's price and how many turns it takes. This is why the tool is **on-demand + cost-capped + dry-run-estimated**, not a daily job. Exact per-run cost is model-dependent and will be measured by the first `--dry-run` + a single real run; recorded as a still-open (self-service) item.

## fabrik-lib verdict table

| Capability | Ladder verdict | Module (or why build) |
|---|---|---|
| Terminal-Bench task runner (Docker orchestration + task set + programmatic scorers) | **VENDOR (external pip)** | The official `terminal-bench` package IS this capability. No fabrik-lib module does terminal-agent evals; reimplementing is Rejected Alternative #1. Adopt the Apache-2.0 package as a dependency. |
| OpenRouter model routing for the harness | **VENDOR (comes with terminal-bench)** | LiteLLM ships inside terminal-bench; we pin `--model openrouter/<id>`. No separate HTTP/gateway code — and no direct vendor SDK, so the OpenRouter-only constraint holds. |
| Cohort selection + DB writeback (`tbench_accuracy`) | **VENDOR + ENHANCE (from precedent)** | Mirror `microbench_coding.py`: cohort query, subprocess dispatch, `--models`/`--cost-cap`/`--dry-run`, `UPDATE agents SET <score> WHERE id`. Project-local pattern; no fabrik-lib module covers "AI-model microbench dispatch." |
| Cost capping on an unattended paid-LLM loop | **VENDOR (rule + precedent)** | `core/cost-budget.md` mandate + `microbench_coding.py`'s `--cost-cap` / `max_cost_usd` pattern. Per-model USD ceiling, abort on breach. |
| Schema migration for the score column | **NONE NEEDED** | `agents.tbench_accuracy REAL` already exists (verified). The runner only writes it. |
| Parallel dispatch across models | **BUILD (thin) / none** | Explicitly adjudicated against the two near-neighbour modules. **`fabrik-lib/subagents`** is the OpenRouter parallel-subagent runtime (`run_agents([AgentSpec])`) that `microbench_coding.py` uses for dispatch — but Terminal-Bench's own `--n-concurrent` already parallelizes tasks *inside* one run, and the **outer per-model loop is intentionally serial** to bound local-Docker-daemon load (N models × M concurrent containers would thrash the WSL/hub daemon), so `subagents` is not needed for the outer loop; a plain serial `for model in cohort` is leaner and safer. **`fabrik-lib/claude-evaluator`** is LLM-as-judge structured scoring via the Claude Code CLI (batch items → scored JSON on subscription) — it does NOT run agentic Docker terminal tasks and routes via Claude Code, not the OpenRouter-model-under-test; wrong tool. Neither replaces the Terminal-Bench harness. |

**No new fabrik-lib module candidate.** The adapter is project-local to `scripts/kilo-benchmarks/` (matches the `microbench_*` precedents); nothing here is generic across ≥2 project types. Both near-neighbour modules (`subagents`, `claude-evaluator`) were checked and correctly not adopted (row above).

## Shape / infra implications

- **Scaffold type**: N/A — a change to `/opt/fabrik` kilo-benchmarks scripts, not a new project.
- **`shape:` flags**: unchanged. No DB flip (the column exists), no cache/metrics/search/auth/admin flip. It's a dev/hub CLI tool, not a deployed service.
- **Docker service**: none. Runs on-demand; Terminal-Bench manages its own per-task containers via the local Docker daemon.
- **Ports**: none.
- **Env vars**: none new — reuses `OPENROUTER_API_KEY` already in `.env`.
- **New tables/columns on `agents`**: none. Writes the existing `tbench_accuracy`.
- **Dependency change**: adds `terminal-bench` to the deps manifest — **requires plan authorization** (CLAUDE.md deps-file rule).
- **12-Factor**: it's a one-off CLI batch tool (Factor XII admin-process shape), not a long-running service — most factors N/A. Relevant: III (config via env — `OPENROUTER_API_KEY` from `.env`, no secrets in code) and X (dev/prod parity — the tool runs the same wherever Docker+uv exist; hub/dev only).

## Constraints

- **OpenRouter-only gateway**: satisfied — all model traffic routes via LiteLLM `openrouter/<id>` strings; the harness never calls a vendor SDK directly.
- **Cost-budget mandate** (`core/cost-budget.md`): an unattended paid-LLM loop MUST have a cost ceiling. Enforced per-model via `--cost-cap` + a mandatory `--dry-run` cost estimate before a real run.
- **Deps-file edit needs authorization**: adding `terminal-bench` to `requirements.txt`/`pyproject.toml` is gated — the plan must carry the authorization step.
- **Not in daily_refresh.sh**: too expensive/slow for a daily cron; on-demand only. The daily leaderboard *scrape* is unaffected and remains the bulk-coverage source.
- **Score comparability caveat**: home-run scores use *our* harness version (`terminus-2`) + *our* dataset-version + our own runs, so they will **not** be byte-identical to the public leaderboard's numbers (which use their harness/version). The value is **relative comparison between our candidates under one identical harness** (e.g. m3 vs glm-5.2 vs gemini-3-flash), plus a rough absolute anchor. This is documented in the script docstring so a future reader doesn't mistake a home score for a leaderboard score.
- **Docker-in-WSL**: verified working (daemon reachable). Terminal-Bench's per-task containers run on the local daemon.

## Open / blocking unknowns

### Resolved during this drafting

1. **Does the harness support OpenRouter?** — RESOLVED (live): yes, via LiteLLM `openrouter/<id>` + `OPENROUTER_API_KEY`. Constraint-compliant.
2. **Do we have Docker/uv in the dev env?** — RESOLVED (live probe): Docker 29.1.3 + uv 0.11.16 both present; daemon reachable.
3. **Migration needed for the score column?** — RESOLVED: no; `agents.tbench_accuracy` already exists.
4. **Reuse `microbench_coding.py` or new script?** — RESOLVED: new sibling script (different sandbox model: Docker vs bwrap). Matches the microbench_* separation precedent.
5. **License OK for our use?** — RESOLVED (live): Apache-2.0, commercial use permitted.

### Still-open (each with a self-service resolution step for the plan phase)

1. **[SELF-SERVICE — plan Phase A]** (a) Which CLI the installed package exposes — `tb` (Terminal-Bench) vs `harbor` — and that it accepts `--model openrouter/<id>`. Resolution: after install, run `tb --help` / `harbor --help` and one smoke task; pin the CLI whose `run` accepts the OpenRouter model string (both route via LiteLLM, so this is a which-binary detail, not a feasibility risk). (b) Exact `--dataset-version` to pin. The pip default shows `0.1.1`; the leaderboard we scrape is `2.0`. Resolution: run `tb datasets list` (or read the harness's dataset registry) to enumerate available versions; pin the newest stable `terminal-bench-core` and record it as a constant. Pin choice affects comparability only, not feasibility.
2. **[SELF-SERVICE — plan Phase A]** Exact JSON path/shape of `tb run`'s output for parsing the pass-rate. Resolution: run `tb run --agent terminus-2 --model openrouter/<cheap-model> --task-filter <one-task> --output-path <dir>` once, inspect the emitted results file, and write the parser against its real schema (mirror how `microbench_coding.py:166` reads EvalPlus's `eval_results.json`).
3. **[SELF-SERVICE — measured on first run]** Real per-model cost/time for the full core set. Resolution: the mandatory `--dry-run` estimate + one real capped run establishes the envelope; tune `--cost-cap` and default `--n-concurrent` from that measurement.
4. **[SELF-SERVICE — plan Phase B]** Default agent scaffold: `terminus` vs `terminus-2`. Resolution: default to `terminus-2` (the current Harbor generation per the docs); expose `--agent` to override. Not blocking — a one-flag default.

## Handoff

**Next command**: `/fabrik-spec-review docs/superpowers/specs/2026-07-13-terminal-bench-runner-design.md` — adversarial re-verification of every cited URL (the terminal-bench README, the LiteLLM/OpenRouter support claim, the Apache-2.0 license, the `tb run` syntax) + audit of the fabrik-lib vendor verdicts, flipping `Status: DRAFT → CONVERGED`.

**Then**: this design touches persistence (`agents.tbench_accuracy`) but adds **no user-facing form fields and no new entity** (the column exists), and it's not a GUI project (a hub-side CLI tool). So `/fabrik-data-contract` and `/fabrik-ui-design` are **not** needed. After approval, skip straight to `/fabrik-plan-after-chat`.

**After approval**: `/fabrik-plan-after-chat docs/superpowers/specs/2026-07-13-terminal-bench-runner-design.md` inherits the vendor verdicts + cited facts and emits the phased plan (likely: A = deps add + harness smoke-test + output-schema grounding + dataset-version pin; B = `microbench_terminal.py` cohort/dispatch/parse/writeback + cost-cap + dry-run; C = NULL-ranking-bug fix across the selection queries + docs).

**💡 fabrik-lib candidates**: none. Project-local to kilo-benchmarks, matches the `microbench_*` precedents.
