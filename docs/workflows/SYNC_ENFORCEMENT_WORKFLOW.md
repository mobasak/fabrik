# Sync Enforcement Workflow (Fabrik → Projects)

**Last Updated:** 2026-06-18
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
| `AGENTS.md` | Agent workflow rules |
| `AGENTS-compact.md` | Compact reference |
| `CLAUDE.md` | Per-project Claude agent configuration |
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
| `docs/reference/windsurf/cascade-models.md` | Windsurf AI model reference |
| `docs/reference/long-command-monitoring.md` | Long command monitoring system documentation |
| `docs/reference/technology-stack-decision-guide.md` | Stack selection guide |
| `docs/operations/fabrik-lifecycle.md` | Runtime behavior & data safety |
| `docs/BUSINESS_MODEL.md` | Project catalog (single source) |
| `docs/reference/mobile-responsive-testing-guide.md` | Mobile/responsive testing guide |
| `PORTS.md` | Port allocations (seed; project-owned thereafter — exempt from drift check) |

### Core Scripts

| Script | Purpose |
|--------|----------|
| `final_gate.py` | Pre/post Kilo gate checks |
| `kilo_code_review.py` | Kilo CLI review integration |
| `kilo_docs_enforcer.py` | Step 4 DOCUMENTATOR |
| `docs_updater.py` | Documentation maintenance |
| `update_agents_toc.py` | AGENTS.md table of contents |
| `health_checker.py` | HTTP + DB health probes |

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

All files in `scripts/enforcement/` are recursively synced:

- `check_docker.py` — Dockerfile amd64 compliance
- `check_secrets.py` — Hardcoded secrets detection
- `check_env_contract.py` — .env/.env.example sync
- `check_health.py` — Health endpoint validation
- ... (24+ checks total)

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

The script skips:

- `_*` prefixed directories (staging areas)
- `.` prefixed directories (hidden)
- `/opt/fabrik` itself (source)
- `/opt/.factory` (job queue)
- `/opt/web_scraper` (deprecated)

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
