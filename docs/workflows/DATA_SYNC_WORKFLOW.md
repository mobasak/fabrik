# Data Sync Workflow

**Last Updated:** 2026-09-22 — every row below is re-read from the script, hook line, cron line or manifest list it names (`/fabrik-doc-converge`)
**Status:** PRODUCTION
**Scripts:** multiple (each section names its own)

> Reference for every data flow between the `/opt/*` project folders and `/opt/fabrik`, and for the two hub-internal daily pipelines that feed them.
>
> - **Projects → Fabrik** (Section 1): scripts that READ project folders and aggregate into the hub
> - **Fabrik → Projects** (Section 2): scripts that WRITE into project folders
> - **Hub-internal pipelines** (Section 3): the boot hook, the 06:00 cron and the model-catalog engine that produce what Section 2 distributes
> - Sibling docs own the detail: `SYNC_PROJECTS_WORKFLOW.md`, `SYNC_ENFORCEMENT_WORKFLOW.md`, `HEALTH_SUMMARY_WORKFLOW.md`, `KILO_AGENT_MANAGEMENT.md`, `KILO_BENCHMARK_WORKFLOW.md`, `SCAFFOLD_STRUCTURE.md` (what a scaffold copies at creation time — not repeated here).

---

## 1. Projects → Fabrik (data flows IN)

### 1.1 Project registry

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_projects.py` |
| **Reads** | `project.yaml` from every `/opt/*/` project |
| **Writes** | `data/projects.yaml` (machine-readable registry); the `AUTO-GENERATED:PROJECTS` block of `docs/PROJECT_CATALOG.md` (this path replaced `docs/BUSINESS_MODEL.md` on 2026-07-11); the `AUTO-GENERATED:PORTS` block of the hub's `PORTS.md` |
| **Triggers** | `fabrik scan` (`cli.py::scan` runs it as a subprocess) · `create_project` (`scaffold.py::_post_scaffold_sync`) · boot pipeline step (§ 3.2) · manual |
| **Workflow doc** | `docs/workflows/SYNC_PROJECTS_WORKFLOW.md` |

What it aggregates: name, type, status, category, description; port allocations with conflict detection; stack detection (files, then the `project.yaml` type as fallback); auto-categorisation (Production / Active Development / Planning / Test).

### 1.2 Project `.env` audit (read-only) and the hub `.env`

| Field | Value |
|-------|-------|
| **Script** | `scripts/audit_envs.py` |
| **Reads** | every `/opt/*/.env` |
| **Writes** | console report; `data/env_audit.yaml` (variable NAMES and metadata, never values) only with `--yaml` or `--fix` |
| **Trigger** | `scripts/watch_env_changes.sh` — `inotifywait -m -e modify,create,close_write` over every `/opt/<project>/.env` except the hub's own (21 files today), started by the boot hook under `nohup` when `pgrep -f watch_env_changes.sh` finds none; log `.tmp/env_watcher.log` |

The old consolidation model is retired: `scripts/consolidate_envs.py.deprecated` and `scripts/test_env_consolidation.py.deprecated` are the parked files, and nothing writes `/opt/fabrik/.env` from project files. `/opt/fabrik/.env` is the canonical, hand-maintained source, mirrored off-site by the DR pipeline: `fabrik-dr-watcher.service` (systemd, enabled; `ExecStart=scripts/dr_env_watcher_loop.sh`, an inotify watch on `/opt/fabrik/` filtered to `.env` so tempfile-rename saves are caught) drives `scripts/dr_env_backup.sh`; cron also runs the backup daily at 03:30 and at `@reboot`, and `scripts/dr_env_recovery_test.sh` weekly (Sunday 04:00). Runbook: `docs/operations/credential-recovery.md`.

### 1.3 External-services registry (the consolidation that DOES exist)

| Field | Value |
|-------|-------|
| **Script** | `scripts/external_services_chain.sh` — ONE definition, run from BOTH daily entry points (§ 3.1) |
| **Steps** | `scripts/gather_envs.py --apply` (reads every `/opt/*/.env` except the hub's; writes `secrets/all-envs.env`, chmod 600, gitignored, `#svc`-annotated per provider) → `scripts/classify_services.py --apply --tombstone-unresolved --max-per-run 10` (web-grounds the uncatalogued providers, bounded) → `gather_envs.py --apply` again → `scripts/registry_sync.py --fetch-credits` (upserts `services` + `api_keys` into the local Postgres registry, SHA-256 of each secret, never the value) → `scripts/gen_dashboard.py` → `external-services-dashboard.html`. Every step after the first `gather_envs` runs only if it succeeded (`core_failed -eq 0`): a failed scan skips classify, the reconsolidate pass, `registry_sync` and the dashboard in one shot |
| **Heartbeat** | the `external-services-chain` stamp in `.fabrik/liveness-registry.json`, written only after every data step succeeded (30 h budget) |
| **Reference doc** | `docs/reference/external-services-registry.md` |

### 1.4 Scaffold compliance audit

| Field | Value |
|-------|-------|
| **Script** | `scripts/audit_all_projects.py` |
| **Reads** | Dockerfile, compose.yaml, code dirs, `.env.example`, `project.yaml`, `tests/`, `scripts/` per project |
| **Writes** | `<project>/docs/development/plans/00-research.md` (every run); with `--fix`: `has_user_guide` into `project.yaml` when absent, `PORTS.md` TBD → real port, a CHANGELOG `[Unreleased]` section (`apply_fixes`) |
| **Trigger** | manual only |

Checks: Dockerfile base image, `HEALTHCHECK`, multi-stage; compose amd64 / `fabrik` network / localhost refs; health endpoints with dependency testing; `print()` and logging; scaffold file presence; code-layout classification; cross-project port conflicts.

### 1.5 Health summary

| Field | Value |
|-------|-------|
| **Script** | `scripts/health_summary.py` |
| **Reads** | scaffold file presence per project |
| **Writes** | stdout table, or a JSON array with `--json` |
| **Triggers** | manual · `fabrik scan --health` · boot pipeline step (§ 3.2) |
| **Workflow doc** | `docs/workflows/HEALTH_SUMMARY_WORKFLOW.md` |

### 1.6 Port migration (one-time, done)

`scripts/seed_real_ports.py` extracted real host ports from each project's compose.yaml / `.env` into `project.yaml::ports` (dry-run by default). Completed; kept for reference.

---

## 2. Fabrik → Projects (data flows OUT)

### 2.1 Governance and enforcement sync

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_enforcement_to_projects.py` (`--dry-run`, `--force`) |
| **What** | the lists in `scripts/fabrik_synced_manifest.py` are canonical — GOVERNANCE_FILES 6 (`AGENTS.md`, `agents-fabrik.md`, `agents-fabrik-core.md`, `AGENTS-compact.md`, `opencode.json`, `.windsurfrules`) · GOVERNANCE_TEMPLATES 3 (`templates/governance/CLAUDE.md` → `CLAUDE.md`, `templates/governance/DECISIONS.md` → `docs/DECISIONS.md` seeded once (SEED_IF_MISSING), `templates/governance/.worktreeinclude` → `.worktreeinclude`) · GOVERNANCE_DIRS 4 (`.windsurf/rules`, `.windsurf/workflows`, `docs/reference/kilo`, `docs/reference/MD`) · CORE_SCRIPTS 14 · RUN_SCRIPTS 11 (the nine `run*` helpers, `sync_cascade_backup.sh`, `sync_extensions.sh`) · REFERENCE_DOCS 7 · AGENT_HOOK_FILES 9 · VENDORED_DIRS 1 (`libs/health_probe`, a recursive flat copy into every project; `libs/subagents` left this list for RETIRED_VENDORED_DIRS, which only keeps its gitignore coverage) · the 78 files under `scripts/enforcement/` (74 checks plus `__init__.py` and three `_`-prefixed helpers) · RETIRED_CORE_SCRIPTS 3 (`kilo_code_review.py`, `kilo_docs_enforcer.py`, `update_agents_toc.py` — deleted from projects; the hub copies live under `scripts/archived/`). `AFCL.md` is scaffolded from `templates/scaffold/AFCL_TEMPLATE.md` and never synced |
| **Triggers** | (a) the hub's post-commit hook `scripts/governance_sync_postcommit.sh`, which runs the sync with `--force` when HEAD touches the `governance-sync` files-filter of `.pre-commit-config.yaml` · (b) `scripts/watch_enforcement_changes.sh` — inotify over a hand-kept file list, 5 s debounce, no flags; two instances are live on this box · (c) the 06:00 cron pipeline step (§ 3.3), no flags, under `flock -w 0 /tmp/fabrik-sync-enforcement.lock` · (d) manual. There is no `fabrik enforce` CLI verb |
| **Workflow doc** | `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md` |

A non-forced run WARN-skips any destination newer than its source ("destination newer"); the post-commit `--force` run does not. The watcher's file list still names the three retired core scripts and the hub's own `CLAUDE.md` (which is not a synced file — the template is).

### 2.2 Doc policy deployment — inert

`scripts/deploy_doc_policy.py` reads `templates/docs/.doc-policy.md`; `templates/docs/` does not exist, so the script no-ops. Manual; retire or retarget.

### 2.3 Schema template

`scripts/sync_schema_to_projects.py` writes `db/schema.sql` into projects that lack one, from an inline SQL header (no template file). Manual.

### 2.4 Delivered model-selection docs

`docs/reference/kilo/` is a GOVERNANCE_DIR, so the selection docs the engine delivers there (§ 3.4) reach every project on the next sync — the 06:00 step runs right after delivery for that reason.

### 2.5 Scaffold-time copies

What `create_project` copies into a NEW project (governance, templates, kilo docs, `PORTS.md`, `templates/saas-skeleton/`, …) is inventoried in `docs/workflows/SCAFFOLD_STRUCTURE.md` § "Copied from Fabrik at scaffold time".

---

## 3. Hub-internal pipelines

### 3.1 Two entry points, one lock

| | Boot hook | 06:00 cron |
|---|---|---|
| **File** | `scripts/wsl_startup_hook.sh` | `scripts/kilo-benchmarks/daily_refresh.sh` |
| **Activation** | `~/.bashrc:194` — `[ -t 1 ] && source /opt/fabrik/scripts/wsl_startup_hook.sh` (every interactive shell) | `crontab`: `0 6 * * * /opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh` |
| **Lock** | `/tmp/.fabrik_daily_YYYYMMDD` — shared; whichever runs first owns the day, the other skips | same file; `daily_refresh.sh` deletes older lockfiles at its end |
| **Log** | `scripts/kilo-benchmarks/cache/update.log` (the hook rotates it AND `.tmp/env_watcher.log` at 500 KB, two generations `.1`/`.2` — the hook's own comment still says "1 backup"); an unwritable log falls back to `/tmp/fabrik_daily_pipeline_YYYYMMDD.log`, then `/dev/stderr`, then `/dev/null`, alerts via `pipeline_alert.sh`, and withholds the heartbeat when it bottoms out at `/dev/null` | same log; fallback `/tmp/fabrik_daily_refresh_YYYYMMDD.log` |
| **Heartbeat** | `scripts/kilo-benchmarks/cache/daily_refresh_last_success.txt`, read by `check_daily_refresh_freshness.py` (alert when >36 h stale) | same |

Each run is delimited in the log by `=== Fabrik Daily Pipeline — … ===` (hook) or the refresh's own header.

### 3.2 Boot hook — what runs, in order

Outside the lock, on every sourced shell: log rotation; the env watcher (§ 1.2) if not running; `scripts/check_commit_trailers.py --install` and `pre-commit install -t pre-push` from a `cd /opt/fabrik` subshell (idempotent hook re-installs).

Under the lock, detached with `nohup`:

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `scripts/wait_for_network.sh` | wait for the network |
| 2 | `scripts/sync_projects.py` | § 1.1 |
| 3 | `scripts/health_summary.py` | § 1.5 |
| 4 | *(OpenRouter routing subshell)* | now EMPTY — only the `/tmp/.openrouter_routing_disabled` kill-switch test and a `cd` remain; the routing scripts moved to the engine (§ 3.4) |
| 5 | `scripts/check_ai_pack_freshness.py` | warn-only: `.windsurf/rules/ai/*.md` packs whose `Last content verification:` is >90 d old (`AI_PACK_STALE_DAYS`) |
| 6 | `scripts/sync_extensions.sh` | exits at once with "Skipped: windsurf CLI is not installed" (Windsurf/Cascade retired) |
| 7 | `ssh -N -L 15432:10.99.0.1:5432 …` | the Postgres MCP tunnel to the hub's `postgres-main`, `pgrep`-guarded |
| 8 | `commands/assemble_commands.py --check` | warn if `~/.claude/commands` drifted from `commands/_sources/` |
| 9 | `/opt/session-recall … -m ingest.reindex` | session-recall incremental index (`timeout 600`; Postgres down = one log line) |
| 10 | `scripts/kilo-benchmarks/flush_subagent_outboxes.py` | replay stranded subagent rows into the flywheel |
| 11 | `scripts/claude_p_cost.py --refresh` | rebuild `scripts/kilo-benchmarks/claude_p_cost.json` |
| 12 | `scripts/kilo-benchmarks/rank_task_subagents.py` | regenerate `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` |
| 13 | `scripts/kilo-benchmarks/tests/capture_golden.py --verify` | contract oracle (drift alerts) |
| 14 | `scripts/kilo-benchmarks/check_daily_refresh_freshness.py` | heartbeat check |
| 15 | `scripts/external_services_chain.sh` | § 1.3 |
| 16 | `scripts/kilo-benchmarks/autocommit_pipeline_outputs.sh` | commit the pipeline's own regenerated tracked files (explicit `PATHS` list: the `docs/reference/kilo/*` selection docs, `docs/CAPABILITIES.md`, `capabilities.json`, `docs/traycer/kilo_selected_agents.md`, `scripts/kilo-benchmarks/claude_p_cost.json`, …), guarded fast-forward push, never force |
| 17 | heartbeat write | `daily_refresh_last_success.txt` |

`generate_kilo_agents.py` and `sync_cascade_backup.sh` are NOT invoked on the boot path: the hook's comment says so for `sync_cascade_backup.sh`, and `AGENT_SCRIPT` (the hook's variable for `generate_kilo_agents.py`) is defined and never used. `generate_kilo_agents.py` runs from the cron (§ 3.3).

### 3.3 06:00 cron — `daily_refresh.sh` steps, in order

| Step | Purpose |
|------|---------|
| `check_daily_refresh_freshness` | heartbeat |
| `flush_subagent_outboxes` · `claude_p_cost_refresh` | as in § 3.2; the flush is skipped while pool evaluation is paused |
| `external_services_chain` | § 1.3 |
| `deliver_to_fabrik` | pull the engine's produced bundle into the hub (§ 3.4); non-fatal (yesterday's docs stay) |
| `rank_task_subagents` | must run AFTER delivery — delivery overwrites `TASK_SUBAGENT_SELECTION.md` with the unrestricted doc and the ranker re-applies the operator roster |
| *(pause gate)* | the flush, the delivery and the ranker are all gated on `_pool_eval_paused`, which reads `check_subagent_flywheel._POOL_POLICY_ON` — OFF since D-181/D-182 — so today all three are SKIPPED on every run (the log says `POOL EVAL PAUSED — skipping …` three times) and the delivered docs and routing doc stay frozen as last written |
| `generate_capability_index` | `scripts/generate_capability_index.py` → `capabilities.json` + `docs/CAPABILITIES.md` (hub-generated, never delivered) |
| `generate_kilo_agents` | `scripts/generate_kilo_agents.py` reads `scripts/kilo-benchmarks/kilo_agents.db` (a delivered — and frozen, § 3.4 c — snapshot) and rewrites `~/.traycer/cli-agents/`; skipped when `FABRIK_DISABLE_KILO_WORKFLOW=1`. Its own header says `RETIRED 2026-07-19 … zero runtime callers`, yet this step ran today (`exit=0`, the output dir touched 06:01) — routed |
| `capture_golden --verify` | contract oracle |
| `sync_enforcement_to_projects` | § 2.1 (c) |
| heartbeat + disk hygiene | `.microbench_cache` and `translation_bench/cache` files >30 d, all but the 5 newest `direct_vendor_audit_*`, rotated `update.log.*` / `env_watcher.log.*` beyond 3 generations, week-old `.notalog.*` squatters, `.pytest_cache`/`__pycache__` under `scripts/kilo-benchmarks/`, and stale `/tmp/.fabrik_daily_*` lockfiles are deleted |
| `autocommit_pipeline_outputs` | last, after the hygiene step — the same shared stage list as § 3.2 step 16 |

The model-catalog steps this file used to run (`kilo_agents_db.py`, `update_kilo_benchmarks.py`, `scrape_artificial_analysis.py`, `role_mapper.py`, `export_traycer_registry.py`, the `embedding_*` pipeline, `verify_openrouter_catalog.py`, `classify_ai_category.py`, `category_route_mapper.py`, `category_export_markdown.py`, the pricing fetchers, `derive_cheapest_gateway.py`, `export_models_browser.py`) no longer exist under `scripts/` and no longer run here; `update_gateway_counts.py` is the one that still exists (`scripts/kilo-benchmarks/`, referenced only in the file's header comment). Their comment blocks remain in `daily_refresh.sh` with no code beneath them.

### 3.4 The model-catalog engine (external repo)

| Field | Value |
|-------|-------|
| **Where** | `/opt/ai-model-catalog/engine/` — own venv, own `daily_refresh.sh`, cron `0 5 * * *` |
| **Runs** | the whole catalog pipeline: `kilo_agents_db.py`, benchmark scrapes, `role_mapper.py`, `export_traycer_registry.py`, the `embedding_*` pipeline, `classify_ai_category.py` → `category_route_mapper.py` → `category_export_markdown.py`, the pricing fetchers, `derive_cheapest_gateway.py`, the `rank_*` steps, `update_gateway_counts.py`, `export_models_browser.py`, … — it PRODUCES into `engine/out/` and never writes the hub itself |
| **Delivery** | `engine/deliver_to_fabrik.py --apply --target-root /opt/fabrik` (the hub's 06:00 step): (a) whole files `out/<rel>` → `<rel>` — the eight `docs/reference/kilo/*_SELECTION.md` / `KILO_MODEL_CAPABILITIES.md` / `CANDIDATE_SIGNUPS.md` docs and `scripts/kilo_47_agents_final.json`, `kilo_embeddings_final.json`, `kilo_openrouter_routes_final.json`; `models_browser.html` is remapped to `scripts/kilo-benchmarks/`; (b) marker blocks (`OPENROUTER_ROUTES`, `GATEWAY_COUNTS`, `EMBEDDING_WINNERS`, `ROSTER`, `EMBEDDING_ROSTER`, `EMBEDDING_CATALOG`) injected into 8 of the 11 `.windsurf/rules/ai/*.md` packs, `.windsurf/rules/core/65-rag-search.md` (EMBEDDING_WINNERS, a fleet-synced CORE pack) and two kilo docs — 18 blocks over 11 hosts per `out/blocks/manifest.json`; (c) `out/kilo_agents.db` → `scripts/kilo-benchmarks/kilo_agents.db` — in practice `out/` has never held a `.db` (nothing in the engine exports Postgres to it), so delivery always ships the engine's frozen pre-Postgres SQLite `engine/kilo_agents.db` and the hub's catalog snapshot is stale. Never delivered: `docs/CAPABILITIES.md`, `capabilities.json`, `llms.txt` |
| **Onward** | the delivered kilo docs and rule packs ride § 2.1 to every project |
| **Workflow docs** | `docs/workflows/KILO_AGENT_MANAGEMENT.md`, `docs/workflows/KILO_BENCHMARK_WORKFLOW.md` |

### 3.5 Other cron lines that touch these flows

| Cron | Script | State |
|------|--------|-------|
| `59 11 * * *` | `scripts/kilo_model_sync.py --sync` (→ `.droid/kilo_model_sync.log`) | fails on every run — `ERROR: Kilo CLI not found` now, `kilo models failed: Configuration is invalid` before that (Kilo CLI retired); log at 257 KB and growing — dead cron, routed. `scripts/kilo_model_sync_startup.sh` (`~/.bashrc:190`) is its boot-time sibling, same log, same failure |
| `30 3 * * *`, `@reboot`, `0 4 * * 0` | `dr_env_backup.sh`, `dr_env_recovery_test.sh` | § 1.2 |
| `0 5 * * *` | `/opt/ai-model-catalog/engine/daily_refresh.sh` | § 3.4 |

### 3.6 Retired but still shipped

`scripts/sync_extensions.sh` (exits at once) and `scripts/sync_cascade_backup.sh` (reads `docs/reference/CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md`, which no longer exists; nothing invokes it) are both still in RUN_SCRIPTS, so every project receives them, and the enforcement watcher still lists `sync_cascade_backup.sh`. Retirement candidates, routed to infra.

---

## 4. Hibernate / wake behaviour

The lockfile name carries the UTC date, so yesterday's lock never blocks today (and `daily_refresh.sh` deletes stale ones); what decides whether a day's pipeline runs is which entry point gets a chance:

| Action | Boot hook | 06:00 cron |
|--------|-----------|------------|
| `wsl --shutdown` + new terminal, or Windows reboot | runs (`.bashrc` sources the hook) | runs if WSL is up at 06:00 |
| Windows hibernate/sleep + resume, no new terminal | does not run (no new shell) | runs only if WSL is running at 06:00; a missed 06:00 is not replayed |
| new terminal tab, later the same day | skipped (lock exists) | — |
| new terminal tab, next day | runs | — |

---

## 5. Automation status per script

| Script | Automated by | Manual use |
|--------|--------------|------------|
| `sync_projects.py` | boot hook · `fabrik scan` · post-scaffold | `python3 scripts/sync_projects.py` |
| `audit_envs.py` | env watcher (on every project `.env` change) | `--yaml` to write `data/env_audit.yaml` |
| `external_services_chain.sh` | boot hook + 06:00 cron | `bash scripts/external_services_chain.sh` |
| `health_summary.py` | boot hook · `fabrik scan --health` | `--json` |
| `sync_enforcement_to_projects.py` | post-commit `--force` · watcher · 06:00 cron | `--dry-run` first; `--force` overwrites ~46 repos |
| `deliver_to_fabrik.py`, `rank_task_subagents.py`, `generate_capability_index.py`, `generate_kilo_agents.py` | 06:00 cron (the ranker also at boot) | run from `/opt/fabrik` with the venv named in the cron file |
| `audit_all_projects.py` | — | heavy scan, ~46 reports; `--fix` for the safe fixes |
| `deploy_doc_policy.py` | — | inert (§ 2.2) |
| `sync_schema_to_projects.py` | — | only writes where `db/schema.sql` is missing |
| `seed_real_ports.py` | — | one-time, done |

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/audit_all_projects.py`
- `scripts/audit_envs.py`
- `scripts/deploy_doc_policy.py`
- `scripts/sync_schema_to_projects.py`
<!-- END related-scripts -->
