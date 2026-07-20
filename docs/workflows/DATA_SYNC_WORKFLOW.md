# Data Sync Workflow

**Last Updated:** 2026-07-20
**Status:** PRODUCTION (env-consolidation in Section 1.2 is DEPRECATED — see banner there)
**Scripts:** Multiple (see sections below)

> Complete reference for all data synchronization between `/opt/*` project folders and `/opt/fabrik`.
>
> **Directions:**
> - **Projects → Fabrik:** Data flows IN to Fabrik (Section 1)
> - **Fabrik → Projects:** Data flows OUT to projects (Section 2)

---

## Overview

Fabrik maintains a bidirectional data flow between the central `/opt/fabrik` repo and all `/opt/*` project folders. This document is the single source of truth for what syncs, how, and when.

---

## 1. Projects → Fabrik (Data Flows IN)

Scripts that **read from project folders** and aggregate into Fabrik.

### 1.1 Project Registry Sync

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_projects.py` |
| **Reads** | `project.yaml` from all `/opt/*/` projects |
| **Writes** | `data/projects.yaml`, `docs/BUSINESS_MODEL.md`, `PORTS.md` |
| **Trigger** | `fabrik scan`, `fabrik scaffold` (post-hook), manual |
| **Automation** | Post-scaffold hook (automatic), otherwise manual |
| **Workflow Doc** | `docs/workflows/SYNC_PROJECTS_WORKFLOW.md` |

What it aggregates:
- Project name, type, status, category, description
- Port allocations (with conflict detection)
- Stack detection (from files or `project.yaml` type fallback)
- Auto-categorization (Production / Active Development / Planning / Test)

### 1.2 Environment Variable Consolidation — DEPRECATED

> **⚠️ DEPRECATED (2026-06-16).** The consolidation model below is gone.
> `scripts/consolidate_envs.py` no longer exists as a live tool — it is retired
> to `scripts/consolidate_envs.py.deprecated` (and its test to
> `scripts/test_env_consolidation.py.deprecated`). Fabrik **no longer consolidates
> `/opt/fabrik/.env` FROM project `/opt/*/.env` files.**
>
> **Current env model:**
>
> - `/opt/fabrik/.env` is the **canonical source**, maintained directly (not generated).
> - It is mirrored off-site by the **W9 DR pipeline** — `scripts/dr_env_backup.sh`
>   driven by `fabrik-dr-watcher.service` (systemd inotify watcher), with a weekly
>   self-test via `scripts/dr_env_recovery_test.sh`. See
>   [`docs/operations/credential-recovery.md`](../operations/credential-recovery.md).
> - The still-running `scripts/watch_env_changes.sh` watcher (Section 4) was rewired
>   to invoke the **read-only** `scripts/audit_envs.py` — it audits project `.env`
>   files for violations and **never writes** `/opt/fabrik/.env`.

### 1.3 Scaffold Compliance Audit

| Field | Value |
|-------|-------|
| **Script** | `scripts/audit_all_projects.py` |
| **Reads** | Dockerfile, compose.yaml, code dirs, .env.example, project.yaml, tests/, scripts/ |
| **Writes** | `docs/development/plans/00-research.md` per project |
| **Trigger** | Manual only |
| **Automation** | ❌ Not automated |

What it checks:
- Dockerfile base image compliance, HEALTHCHECK, multi-stage parsing
- compose.yaml: amd64, fabrik network, localhost refs
- Health endpoints (with dependency testing detection)
- print() usage, logging imports, hardcoded localhost
- Scaffold file presence (Makefile, pyproject.toml, .env.example, db/schema.sql, watchdog, tests)
- Code layout classification, empty scaffold detection
- Cross-project port conflict detection

### 1.4 Health Summary

| Field | Value |
|-------|-------|
| **Script** | `scripts/health_summary.py` |
| **Reads** | Scaffold file presence per project |
| **Writes** | Console output only |
| **Trigger** | `fabrik scan --health`, manual |
| **Automation** | ❌ Not automated |
| **Workflow Doc** | `docs/workflows/HEALTH_SUMMARY_WORKFLOW.md` |

### 1.5 Port Migration (One-Time)

| Field | Value |
|-------|-------|
| **Script** | `scripts/seed_real_ports.py` |
| **Reads** | compose.yaml, .env port mappings per project |
| **Writes** | `project.yaml` ports field |
| **Trigger** | One-time migration (completed) |
| **Automation** | N/A — already done |

---

## 2. Fabrik → Projects (Data Flows OUT)

Scripts that **read from Fabrik** and push to all `/opt/*/` project folders.

Scripts that **write files into project folders** from Fabrik templates/governance.

### 2.1 Enforcement Sync

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_enforcement_to_projects.py` |
| **Watcher** | `scripts/watch_enforcement_changes.sh` (inotifywait) |
| **Reads** | Fabrik governance files, scripts, enforcement checks |
| **Writes** | Every `/opt/*/` project |
| **Trigger** | Manual (`fabrik enforce` or direct), or automatic via watcher |
| **Automation** | ✅ Optional: WSL startup hook via watcher (monitors Fabrik governance files) |
| **Workflow Doc** | `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md` |

What it syncs:
- **Governance files (5):** AGENTS.md, AGENTS-compact.md, CLAUDE.md, opencode.json, .windsurfrules
  - **Note:** AFCL.md is scaffolded as AFCL_TEMPLATE.md and customized per project, not synced
- **Governance directories:** .windsurf/rules/*
- **Core scripts (6):** final_gate.py, kilo_code_review.py, kilo_docs_enforcer.py, docs_updater.py, update_agents_toc.py, health_checker.py
- **Run scripts (11):** rund, rundsh, runc, runk, runls, runlast, runwait, runtail, runclean, sync_cascade_backup.sh, sync_extensions.sh
- **Reference docs:** docs/reference/long-command-monitoring.md (+ the rest of REFERENCE_DOCS in fabrik_synced_manifest.py)
- **Enforcement checks (30+):** scripts/enforcement/*.py

### 2.2 Doc Policy Deployment

| Field | Value |
|-------|-------|
| **Script** | `scripts/deploy_doc_policy.py` |
| **Reads** | `templates/docs/.doc-policy.md` — ⚠ template absent at this path (2026-07-20): the script currently no-ops; retarget or retire the script |
| **Writes** | `.doc-policy.md` in every `/opt/*/` project |
| **Trigger** | Manual |
| **Automation** | ❌ Not automated |

### 2.3 Schema Template Sync

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_schema_to_projects.py` |
| **Reads** | Schema template |
| **Writes** | `db/schema.sql` in projects missing it |
| **Trigger** | Manual |
| **Automation** | ❌ Not automated |

### 2.4 Audit Auto-Fixes

| Field | Value |
|-------|-------|
| **Script** | `scripts/audit_all_projects.py --fix` |
| **Writes** | `has_user_guide` in project.yaml, PORTS.md TBD→real port, CHANGELOG [Unreleased] section |
| **Trigger** | Manual (with `--fix` flag) |
| **Automation** | ❌ Not automated |

---

## 3. Fabrik-Internal Syncs (No Cross-Project IO)

Scripts that run within Fabrik only, referenced by the WSL startup hook.

### 3.1 Kilo Agent Pipeline (Daily)

| Script | Purpose |
|--------|---------|
| `kilo_agents_db.py all` | Refresh agent list + benchmarks + snapshots from Kilo CLI + Ollama |
| `update_kilo_benchmarks.py --force` | Scrape Arena ELO + Terminal-Bench scores |
| `scrape_artificial_analysis.py` | Scrape throughput (tokens/sec) + TTFT from artificialanalysis.ai |
| `role_mapper.py` | Deterministic role assignment (pre_filter → selector → post_filter → DB, ~50ms, $0 cost) |
| `export_traycer_registry.py` | Refresh `scripts/kilo_47_agents_final.json` from DB |
| `generate_kilo_agents.py` | Generate Traycer CLI agent scripts |
| **Workflow Doc** | `docs/workflows/KILO_AGENT_MANAGEMENT.md` |

**Note:** Re-enabled 2026-05-13 after switching from LLM-based to deterministic Pareto algorithm. Opt-out via `FABRIK_DISABLE_KILO_WORKFLOW=1`. Chained inside the same `FABRIK_DISABLE_KILO_WORKFLOW` guard as § 3.1b below (`scripts/wsl_startup_hook.sh:99-113`).

### 3.1b Embedding Selection Pipeline (Daily)

Mirrors the chat-model pipeline shape (catalog scrape → shortlists → role winners) for embedding models specifically. Runs immediately after § 3.1's `generate_kilo_agents.py`, inside the same `FABRIK_DISABLE_KILO_WORKFLOW` guard — an independent `&&` chain, so a broken embeddings catalog does not kill the chat-model workflow above it.

| Script | Purpose |
|--------|---------|
| `embedding_models_db.py all` | Refresh embedding-model catalog from Kilo CLI + Ollama |
| `embedding_pre_filter.py` | Pre-filter candidates before role mapping |
| `embedding_role_mapper.py` | Deterministic role assignment for embedding models |
| `embedding_export_markdown.py` | Export role winners to markdown |
| **Workflow Doc** | `docs/workflows/KILO_BENCHMARK_WORKFLOW.md` |

### 3.1c OpenRouter Category Routing (Daily)

Reads `agents` + `agent_categories`, writes `openrouter:{category}` pins to `agent_roles`, then injects `OPENROUTER_ROUTES` markers into the 7 `ai/NN-*.md` rule packs. Runs in its own subshell (`scripts/wsl_startup_hook.sh:126-157`), independent of the Kilo/embedding guard above — each step fails loud + non-fatal (`|| echo ... non-fatal`) so one broken script cannot short-circuit the rest. Kill-switch: `touch /tmp/.openrouter_routing_disabled` (disables the *next* scheduled run, not one already in flight).

| Order | Script | Purpose |
|-------|--------|---------|
| 1 | `verify_openrouter_catalog.py --apply --ingest-new` | Verify pricing/capabilities against the live OpenRouter API, auto-fix discrepancies, mark delisted rows deprecated, ingest new ones — runs BEFORE the classifier so it sees the corrected catalog |
| 2 | `classify_ai_category.py` | Classify models into the 7 categories |
| 3 | `category_route_mapper.py` | Rank per-category, write `openrouter:{category}` pins |
| 4 | `category_export_markdown.py` | Inject `OPENROUTER_ROUTES` markers + refresh verification stamps in the 7 packs |
| 5 | `update_gateway_counts.py` | Inject gateway counts |
| 6 | `fetch_replicate_prices.py` | Fetch Replicate pricing |
| 7 | `fetch_fal_prices.py` | Fetch fal.ai pricing — **conditional on `$FAL_KEY`** being set |
| 8 | `derive_cheapest_gateway.py` | Derive cheapest gateway per model |
| 9 | `export_models_browser.py` | Export the models browser data file |
| — | **Workflow Doc** | `docs/workflows/KILO_BENCHMARK_WORKFLOW.md` (§ OpenRouter category routing) |

### 3.2 Windsurf Extensions Sync (Daily)

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_extensions.sh` |
| **Reads** | `windsurf --list-extensions` output |
| **Writes** | `docs/reference/windsurf/actively-used-windsurf-extensions.md` |
| **Trigger** | WSL startup hook (daily) |

### 3.3 Cascade Backup Freshness Check

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_cascade_backup.sh` |
| **Reads** | `docs/reference/CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md` age — ⚠ file absent + Cascade retired 2026-07-19: script is a retirement-cleanup candidate |
| **Writes** | Console warning if stale (>7 days) |
| **Trigger** | WSL startup hook (daily) |

---

## 4. WSL Startup Hook Summary

**File:** `scripts/wsl_startup_hook.sh`
**Activation:** `source /opt/fabrik/scripts/wsl_startup_hook.sh` in `~/.bashrc`

### Persistent Processes (every WSL boot, run continuously)

| Process | Script | Purpose |
|---------|--------|---------|
| Env watcher | `watch_env_changes.sh` | inotifywait on `/opt/*/.env` → `audit_envs.py` (read-only violation audit; does NOT write `/opt/fabrik/.env`). The old `consolidate_envs.py --apply` consolidation is deprecated — see Section 1.2. |

### Daily Pipeline (once per boot day, non-blocking)

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `sync_projects.py` | Refresh project registry + `docs/PROJECT_CATALOG.md` (renamed from `BUSINESS_MODEL.md` 2026-07-11) + PORTS.md |
| 2 | `sync_cascade_backup.sh` | Check Cascade memory backup freshness (warn if >7d) |
| 3 | `health_summary.py` | Scaffold health overview across all projects |
| *(4a-4f gated together on `FABRIK_DISABLE_KILO_WORKFLOW`, chained `&&` — a failure anywhere in 4a-4f stops the rest of 4a-4f, but not steps 5+)* | | |
| 4a | `kilo_agents_db.py all` | Agent sync + benchmarks + snapshots from Kilo CLI + Ollama |
| 4b | `update_kilo_benchmarks.py --force` | Scrape Arena ELO + Terminal-Bench scores |
| 4c | `scrape_artificial_analysis.py` | Scrape throughput (tokens/sec) + TTFT |
| 4d | `role_mapper.py` | Deterministic role assignment (pre_filter → selector → post_filter → DB, ~50ms, $0 cost) |
| 4e | `export_traycer_registry.py` | Refresh `scripts/kilo_47_agents_final.json` from DB |
| 4f | `generate_kilo_agents.py` | Generate Traycer CLI agent scripts |
| 4g | `embedding_models_db.py all` | Refresh embedding-model catalog (§ 3.1b) |
| 4h | `embedding_pre_filter.py` | Pre-filter embedding-model candidates |
| 4i | `embedding_role_mapper.py` | Deterministic role assignment for embedding models |
| 4j | `embedding_export_markdown.py` | Export embedding role winners to markdown |
| *(5a-5i gated together on `/tmp/.openrouter_routing_disabled`, own subshell — independent of step 4's guard; each sub-step fails loud + non-fatal, § 3.1c)* | | |
| 5a | `verify_openrouter_catalog.py --apply --ingest-new` | Verify pricing/capabilities vs live OpenRouter API, auto-fix, ingest new |
| 5b | `classify_ai_category.py` | Classify models into the 7 categories |
| 5c | `category_route_mapper.py` | Rank per-category, write `openrouter:{category}` pins |
| 5d | `category_export_markdown.py` | Inject `OPENROUTER_ROUTES` markers + refresh verification stamps |
| 5e | `update_gateway_counts.py` | Inject gateway counts |
| 5f | `fetch_replicate_prices.py` | Fetch Replicate pricing |
| 5g | `fetch_fal_prices.py` | Fetch fal.ai pricing — conditional on `$FAL_KEY` |
| 5h | `derive_cheapest_gateway.py` | Derive cheapest gateway per model |
| 5i | `export_models_browser.py` | Export the models browser data file |
| 6 | `check_ai_pack_freshness.py` | Warn-only: flag `.windsurf/rules/ai/*.md` packs >90d unverified (`AI_PACK_STALE_DAYS` override) |
| 7 | `sync_extensions.sh` | Windsurf extensions docs (retries 3x if IDE not ready) |

**Note:** Steps 4a-4j are the Kilo agent + embedding-selection workflow (§ 3.1, § 3.1b). Deterministic algorithm (no LLM) re-enabled 2026-05-13. Opt-out via `FABRIK_DISABLE_KILO_WORKFLOW=1`. Steps 5a-5i are OpenRouter category routing (§ 3.1c); kill-switch: `touch /tmp/.openrouter_routing_disabled`. Full source: `scripts/wsl_startup_hook.sh`.

### Hibernate / Wake Behavior

The daily pipeline is guarded by a lock file (`/tmp/.fabrik_daily_YYYYMMDD`) and triggered via `.bashrc`. This means:

| Action | Pipeline triggers? | Why |
|--------|-------------------|-----|
| `wsl --shutdown` + reopen terminal | ✅ Yes | Fresh WSL start, `.bashrc` runs, no lock file |
| Windows reboot/restart | ✅ Yes | Same as above |
| **Windows hibernate + resume** | **❌ No** | WSL frozen in memory, no new shell, `.bashrc` doesn't run |
| Windows sleep + wake | ❌ No | Same as hibernate |
| Open new terminal tab (next day) | ✅ Yes | `.bashrc` runs, yesterday's lock file gone (`/tmp/` cleared on WSL restart) |
| Open new terminal tab (same day) | ⚠️ Skipped | Lock file still exists |

**Gap:** If you hibernate Monday night and resume Tuesday without opening a new terminal, Tuesday's pipeline never runs. Opening any new terminal tab will trigger it.

### Log Rotation

Logs auto-rotate at 500KB (1 backup kept):
- Daily pipeline: `scripts/kilo-benchmarks/cache/update.log`
- Env watcher: `.tmp/env_watcher.log`

Each daily run is delimited by `=== Fabrik Daily Pipeline — YYYY-MM-DD HH:MM:SS ===` markers.

---

## 5. NOT Automated (Manual Only)

| Script | Why Manual | Risk if Automated |
|--------|-----------|-------------------|
| `sync_enforcement_to_projects.py` | Overwrites governance files in all projects | Could overwrite project-specific customizations |
| `audit_all_projects.py` | Heavy scan, generates 42 reports | Low risk, but slow (~30s) |
| `deploy_doc_policy.py` | Infrequent template deployment | Low risk |
| `sync_schema_to_projects.py` | Creates db/schema.sql where missing | Low risk |
| `sync_cascade_backup.sh` | Freshness check only | No risk — read-only |
| `health_summary.py` | Console report only | No risk — read-only |

---

## 6. Automation Recommendations

### ✅ Add to WSL Startup Hook (Safe)

| Script | Reason | Type |
|--------|--------|------|
| `sync_cascade_backup.sh` | Read-only freshness check, warns if backup stale | Persistent (check once) |
| `sync_projects.py` | Keeps registry + BUSINESS_MODEL.md + PORTS.md current | Daily |
| `health_summary.py` | Quick scaffold health overview on boot | Daily |

### ⚠️ Consider Automating (Low Risk)

| Script | Reason | Guard Needed |
|--------|--------|-------------|
| `audit_all_projects.py` | Regenerate 00-research.md weekly | Weekly lock file, not daily |
| `deploy_doc_policy.py` | Template rarely changes, hash-compare prevents unnecessary writes | Hash guard (already safe) |
| `sync_schema_to_projects.py` | Only writes to projects *missing* schema | Only-if-missing guard (already safe) |

### ❌ Keep Manual (Intentional)

| Script | Reason |
|--------|--------|
| `sync_enforcement_to_projects.py` | Overwrites 30+ files per project — must be intentional |

