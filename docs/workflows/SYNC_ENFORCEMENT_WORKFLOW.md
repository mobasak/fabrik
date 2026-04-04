# Sync Enforcement Workflow

**Last Updated:** 2026-04-04
**Status:** PRODUCTION
**Script:** `scripts/sync_enforcement_to_projects.py`

## Overview

Synchronizes Fabrik enforcement scripts to all `/opt/*` projects, ensuring consistent code quality tooling across the ecosystem. Uses hash comparison and timestamp checks to avoid unnecessary overwrites.

---

## What Gets Synced

### Governance Files

| File/Dir | Purpose |
|----------|----------|
| `AGENTS.md` | Agent workflow rules |
| `AGENTS-compact.md` | Compact reference |
| `opencode.json` | Kilo-safe rules |
| `.windsurfrules` | Cascade compact agent contract |
| `.windsurf/rules/` | Cascade rule files (recursive) |
| `.windsurf/workflows/` | Cascade slash-command workflows |

### Reference Documentation

| File | Purpose |
|------|----------|
| `cascade-models.md` | Windsurf AI model reference |
| `technology-stack-decision-guide.md` | Technology selection guidance |
| `prebuilt-app-containers.md` | Prebuilt Docker container catalog |

**Auto-sync trigger:** Pre-commit hook in `/opt/fabrik/.pre-commit-config.yaml` runs sync when any governance or reference file is committed. No cron needed.

### Core Scripts

| Script | Purpose |
|--------|----------|
| `final_gate.py` | Pre/post Kilo gate checks |
| `kilo_code_review.py` | Kilo CLI review integration |
| `kilo_docs_enforcer.py` | Step 4 DOCUMENTATOR |
| `docs_updater.py` | Documentation maintenance |
| `update_agents_toc.py` | AGENTS.md table of contents |
| `health_checker.py` | HTTP + DB health probes |

### Enforcement Directory

All files in `scripts/enforcement/` are recursively synced:

- `check_docker.py` — Dockerfile ARM64 compliance
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
| On governance file commit | **Automatic** via pre-commit hook in fabrik |

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
