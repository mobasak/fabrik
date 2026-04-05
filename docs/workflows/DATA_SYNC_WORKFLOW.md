# Data Sync Workflow

**Last Updated:** 2026-04-05
**Status:** PRODUCTION

> Complete reference for all data synchronization between `/opt/*` project folders and `/opt/fabrik`.

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

### 1.2 Environment Variable Consolidation

| Field | Value |
|-------|-------|
| **Script** | `scripts/consolidate_envs.py` |
| **Watcher** | `scripts/watch_env_changes.sh` (inotifywait) |
| **Reads** | `.env` from all `/opt/*/` projects |
| **Writes** | `/opt/fabrik/.env` (master credentials file) |
| **Trigger** | Continuous (via inotifywait watcher on WSL boot) |
| **Automation** | ✅ WSL startup hook (persistent background process) |
| **Log** | `.tmp/env_watcher.log` |

What it aggregates:
- All env vars from project `.env` files, merged into project-scoped sections
- Preserves existing Fabrik core vars
- Masks sensitive values in dry-run output
- Backup before overwrite

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
- compose.yaml: arm64, coolify network, localhost refs
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

Scripts that **write files into project folders** from Fabrik templates/governance.

### 2.1 Enforcement Sync

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_enforcement_to_projects.py` |
| **Reads** | Fabrik governance files, scripts, enforcement checks |
| **Writes** | Every `/opt/*/` project |
| **Trigger** | Manual (`fabrik enforce` or direct) |
| **Automation** | ❌ Not automated — intentionally manual (overwrites governance files) |
| **Workflow Doc** | `docs/workflows/SYNC_ENFORCEMENT_WORKFLOW.md` |

What it syncs:
- **Governance files:** AGENTS.md, AGENTS-compact.md, opencode.json, .windsurfrules, .windsurf/rules/*, .windsurf/workflows/*
- **Core scripts (6):** final_gate.py, kilo_code_review.py, kilo_dispatch.py, kilo_docs_enforcer.py, kilo_terminal_runner.py, kilo_cost_tracker.py
- **Cascade wrappers (5):** Local_Coder, Local_Review, Local_Fixer, Local_Documentator, Kilo_Review
- **Enforcement checks (30+):** scripts/enforcement/*.py

### 2.2 Doc Policy Deployment

| Field | Value |
|-------|-------|
| **Script** | `scripts/deploy_doc_policy.py` |
| **Reads** | `templates/docs/.doc-policy.md` |
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
| `kilo_agents_db.py all` | Refresh agent list + benchmarks + snapshots + export |
| `generate_kilo_agents.py` | Generate Traycer CLI agent scripts |
| `kilo_model_sync.py --sync` | Sync model metadata |
| **Workflow Doc** | `docs/workflows/KILO_AGENT_MANAGEMENT.md` |

### 3.2 Windsurf Extensions Sync (Daily)

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_extensions.sh` |
| **Reads** | `windsurf --list-extensions` output |
| **Writes** | `docs/reference/windsurf/actively-used-windsurf-extensions.md` |
| **Trigger** | WSL startup hook (daily), pre-commit hook |

### 3.3 Cascade Backup Freshness Check

| Field | Value |
|-------|-------|
| **Script** | `scripts/sync_cascade_backup.sh` |
| **Reads** | `docs/reference/CASCADE_MEMORIES_GLOBAL_RULES_BACKUP.md` age |
| **Writes** | Console warning if stale (>7 days) |
| **Trigger** | WSL startup hook (daily) |

---

## 4. WSL Startup Hook Summary

**File:** `scripts/wsl_startup_hook.sh`
**Activation:** `source /opt/fabrik/scripts/wsl_startup_hook.sh` in `~/.bashrc`

### Persistent Processes (every WSL boot, run continuously)

| Process | Script | Purpose |
|---------|--------|---------|
| Env watcher | `watch_env_changes.sh` | inotifywait on `/opt/*/.env` → `consolidate_envs.py --apply` |

### Daily Pipeline (once per boot day, non-blocking)

| Step | Script | Purpose |
|------|--------|---------|
| 1 | `sync_projects.py` | Refresh project registry + BUSINESS_MODEL.md + PORTS.md |
| 2 | `sync_cascade_backup.sh` | Check Cascade memory backup freshness (warn if >7d) |
| 3 | `health_summary.py` | Scaffold health overview across all projects |
| 4 | `kilo_agents_db.py all` | Agent sync + benchmarks + snapshots + export |
| 5 | `update_kilo_benchmarks.py --force` | Scrape latest benchmark scores |
| 6 | `role_mapper.py` | AI role assignment (~$0.19/run via Gemini 3.1 Pro) |
| 7 | `generate_kilo_agents.py` | Generate Traycer CLI agent scripts |
| 8 | `sync_extensions.sh` | Windsurf extensions docs (retries 3x if IDE not ready) |

### Separate Startup Script

| Script | Purpose |
|--------|---------|
| `kilo_model_sync_startup.sh` | Model metadata sync (own lock file, own daily guard) |

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

