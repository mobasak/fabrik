# Sync Enforcement Workflow (Fabrik → Projects)

**Last Updated:** 2026-07-20
**Status:** PRODUCTION
**Script:** `scripts/sync_enforcement_to_projects.py`
**Source of truth (the synced list):** `scripts/fabrik_synced_manifest.py`
**Direction:** Fabrik → Projects

## Overview

Synchronizes Fabrik governance + enforcement files to all `/opt/*` projects, ensuring consistent tooling and agent contracts across the ecosystem. Uses hash comparison and timestamp checks to avoid unnecessary overwrites.

> **⚠️ These files are centrally managed — do not edit them inside a project.**
> A local edit is overwritten on the next sync. The list lives once in
> [`scripts/fabrik_synced_manifest.py`](../../scripts/fabrik_synced_manifest.py) and is consumed by this sync
> script, the `.gitignore` "Fabrik-synced" block emitted by `scaffold.py`, and the
> gate check `scripts/enforcement/check_synced_unmodified.py` (which **fails the
> gate** when a project's copy drifts from the `/opt/fabrik` source). To change a
> synced file: edit the canonical copy in `/opt/fabrik`, re-sync, and **only** if
> the change is correct for ALL projects. Otherwise propose it upstream — never
> fork it locally. (`PORTS.md` is seeded then project-owned, so it is exempt from
> the drift check.)
>
> **When you modify the synced set, edit `fabrik_synced_manifest.py` only** — the
> three consumers derive from it. The tables below mirror those lists.

| **Trigger** | Manual (`fabrik enforce` or direct), or automatic via `watch_enforcement_changes.sh` |
| **Automation** | ✅ Optional: WSL startup hook via `watch_enforcement_changes.sh` (monitors Fabrik governance files) |

---

## What Gets Synced

### Governance Files

| File/Dir | Purpose |
|----------|----------|
| `AGENTS.md` | Agent workflow rules (stub pointing to `agents-fabrik.md`) |
| `agents-fabrik.md` | Canonical infra + codebase map (the real content `AGENTS.md` stubs to) |
| `agents-fabrik-core.md` | High-frequency platform core, @import-ed by every project's synced `CLAUDE.md` |
| `AGENTS-compact.md` | Compact reference |
| `CLAUDE.md` | Per-project Claude agent configuration — sourced from `templates/governance/CLAUDE.md` (`GOVERNANCE_TEMPLATES`), NOT from the hub's own `/opt/fabrik/CLAUDE.md`, which is the hub agents' contract and never distributed |
| `opencode.json` | Kilo CLI configuration |
| `.windsurfrules` | Cascade compact agent contract |
| `.windsurf/rules/` | Cascade rule files (recursive, orphan-pruned) |
| `.windsurf/workflows/` | Cascade workflow files (recursive, orphan-pruned) |
| `docs/reference/kilo/` | Kilo agent-selection + model docs (recursive, orphan-pruned) |
| `docs/reference/MD/` | Shared markdown reference set (recursive, orphan-pruned) |

**Note:** `AFCL.md` is scaffolded as `AFCL_TEMPLATE.md` and customized per project, not synced. `.pre-commit-config.yaml` is tech-stack specific and not synced.

### Reference Documentation

| File | Purpose |
|------|----------|
| `docs/reference/long-command-monitoring.md` | Long command monitoring system documentation |
| `docs/reference/technology-stack-decision-guide.md` | Stack selection guide |
| `PORTS.md` | Port allocations (seed; project-owned thereafter — exempt from drift check) |
| `docs/operations/fabrik-lifecycle.md` | Runtime behavior & data safety |
| `docs/PROJECT_CATALOG.md` → `docs/reference/opt-project-catalog.md` | The `/opt` project inventory ("what exists, so a project can wire to a sibling instead of rebuilding"). Renamed from `BUSINESS_MODEL.md` 2026-07-11 — that path is each project's own *monetization* doc, and the old sync target was clobbering it; now synced to a reference path that never collides. |
| `docs/reference/mobile-responsive-testing-guide.md` | Mobile/responsive testing guide |
| `docs/reference/convergence-prompts.md` | The 3 direct-agent convergence prompts (PLAN/CODE REVIEW/DOCS) — referenced by the synced `CLAUDE.md` HARD-STOP row |

### Core Scripts

| Script | Purpose |
|--------|----------|
| `final_gate.py` | Pre/post Kilo gate checks |
| `kilo_code_review.py` | Kilo CLI review integration |
| `kilo_docs_enforcer.py` | Step 4 DOCUMENTATOR |
| `docs_updater.py` | Documentation maintenance |
| `doc_reconcile.py` | Tier-1 doc-reconcile loop (pool author → verify → converge); agents run it per phase |
| `update_agents_toc.py` | AGENTS.md table of contents |
| `health_checker.py` | HTTP + DB health probes |
| `select_rules.py` | Plan-time: lists applicable `.windsurf/rules` packs |
| `review_rubric.py` | Armed-review rubric extractor — `/fabrik-review` injects its output into finders |

### Run Scripts

Long Command Monitoring System v1.1.0 - see `docs/reference/long-command-monitoring.md`

| Script | Purpose |
|--------|----------|
| `rund` | Run command with timeout monitoring |
| `rundsh` | Run shell script with timeout monitoring |
| `runc` | Read result from last run |
| `runk` | Kill last run |
| `runls` | List active runs |
| `runlast` | Show last run ID |
| `runwait` | Wait for run completion |
| `runtail` | Tail run output |
| `runclean` | Clean up completed runs |
| `sync_cascade_backup.sh` | Check Cascade memory backup freshness (warn if >7d) |
| `sync_extensions.sh` | Sync Windsurf extensions documentation |

### Enforcement Directory

All files in `scripts/enforcement/` are recursively synced (`ENFORCEMENT_DIR`, `fabrik_synced_manifest.py`) — 49 files as of 2026-07-20 (`git ls-files scripts/enforcement/ | wc -l`), a representative sample:

- `check_docker.py` — Dockerfile amd64 compliance
- `check_secrets.py` — Hardcoded secrets detection
- `check_env_contract.py` — .env/.env.example sync
- `check_health.py` — Health endpoint validation
- ... (49 checks total; see [FINAL_GATE_WORKFLOW.md § Enforcement Scripts](FINAL_GATE_WORKFLOW.md) for the full gate-wired inventory)

### Vendored Modules

| Dir | Purpose |
|-----|----------|
| `libs/subagents` | The OpenRouter subagent-pool module (`VENDORED_DIRS`, `fabrik_synced_manifest.py`), vendored into every project. Dev-time tool the `/fabrik-*` commands import as `from libs.subagents import …`; a fix in the hub copy (`/opt/fabrik/libs/subagents`, kept byte-identical to canonical `/opt/fabrik-lib/subagents`) propagates fleet-wide on the next sync. |

### Agent Hook Files

| File | Purpose |
|------|----------|
| `.claude/settings.json` | Claude Code hook configuration |
| `.claude/hooks/final_gate_stop.py` | Claude Code stop-hook enforcing `final_gate` green as the definition of done |
| `.windsurf/hooks.json` | Cascade equivalent hook configuration |

Synced verbatim to project root (`AGENT_HOOK_FILES`, `fabrik_synced_manifest.py`) — path/cwd-agnostic: the Claude Code hook resolves its project via `${CLAUDE_PROJECT_DIR}` + stdin cwd, the Cascade hook commands self-locate via `git rev-parse`. This is what makes every project — existing and future — enforce `final_gate` green as the definition of done. Kilo/opencode has no config-level hook surface (strict schema), so Kilo stays instruction-only via `AGENTS-compact.md` (rides the Governance Files sync instead).

---

## CLI Usage

```bash
# Preview what would be synced (safe)
python scripts/sync_enforcement_to_projects.py --dry-run

# Sync with backups before overwriting
python scripts/sync_enforcement_to_projects.py --backup

# Force sync (skip hash comparison)
python scripts/sync_enforcement_to_projects.py --force

# Verbose output (show all file actions)
python scripts/sync_enforcement_to_projects.py -v
```

---

## Sync Logic

### Decision Flow

```text
For each file:
├── Destination doesn't exist? → COPY (new file)
├── --force flag? → COPY (forced overwrite)
├── Hash identical? → SKIP (no change needed)
├── Destination newer? → WARN (don't overwrite local changes)
└── Source newer? → COPY (update)
```

### Safety Features

1. **Hash Comparison** — MD5 hash avoids unnecessary writes
2. **Timestamp Check** — Won't overwrite if destination is newer
3. **Backup Option** — Creates `.backup.YYYYMMDD-HHMMSS` before overwriting
4. **Dry Run** — Preview changes without writing
5. **Permission Check** — Skips projects without write access
6. **Symlink Replacement** — Replaces file and directory symlinks with real copies (workspace isolation)

---

## Output Example

```text
Found 38 projects to sync

✓ api-gateway                            OK (5 copied, 20 skipped)
✓ auth-service                           OK (0 copied, 25 skipped)
✓ captcha                                OK (3 copied, 22 skipped)
  WARN (destination newer): final_gate.py
✓ dns-manager                            OK (0 copied, 25 skipped)
✗ legacy-app                             SKIP (no write permission)

Results: 37 projects synced, 1 failed | Files: 8 copied, 917 skipped, 1 warnings
```

---

## When to Run

| Trigger | Command |
|---------|----------|
| After updating scripts | `python sync_enforcement_to_projects.py` |
| Before major releases | `python sync_enforcement_to_projects.py --force` |
| Automatic (optional) | `scripts/watch_enforcement_changes.sh` (WSL startup hook) |

---

## Excluded Directories

The script skips `/opt/fabrik` itself (source) plus the `exclude_folders` set (`sync_enforcement_to_projects.py:748-762`, 11 entries, reconciled 2026-07-20):

- `.factory`, `.ssh` — non-project system dirs
- `web_scraper` (deprecated — use `web-scraper`)
- `containerd` — Docker runtime artifact dir
- `google` — Google Chrome install location
- `logs` — generic logs dir, not a Fabrik project
- `archived` — archived projects, no longer active
- `fabrik-lib`, `fabrik-libs` — reference implementation store (vendor, don't depend)
- `mt-router` — standalone copy, reference already in `fabrik-lib`

---

## Project INDEX.md Updates

Each project's `INDEX.md` contains an auto-generated **Documentation Structure Map** section that is kept in sync with the actual files.

### How to Update Project INDEX.md

```bash
# In any project directory:
cd /opt/<project-name>
python scripts/docs_updater.py

# Or check for issues:
python scripts/docs_updater.py --check

# Dry run to see what would change:
python scripts/docs_updater.py --dry-run
```

### What Gets Updated Automatically

- **Documentation Structure Map** (between `AUTO-GENERATED:STRUCTURE` tags)
- File tree structure of `docs/` directory
- Detects new, moved, or deleted documentation files

### What Remains Manual

- File purposes table (top section)
- "Last Updated" date
- File descriptions and update triggers

---

## Exit Codes

| Code | Meaning |
|------|----------|
| 0      | All projects synced successfully |
| 1      | One or more projects failed       |

---

## Related Workflows

- [Final Gate Workflow](FINAL_GATE_WORKFLOW.md) — The synced enforcement scripts
- [Fabrik Scaffold Workflow](FABRIK_SCAFFOLD_WORKFLOW.md) — Project creation
