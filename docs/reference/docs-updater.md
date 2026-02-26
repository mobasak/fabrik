# Automatic Documentation Updater

**Last Updated:** 2026-01-14

Automatically updates documentation when code changes are detected. Uses low-cost AI models to analyze changes and write updates directly to doc files.

Also provides **structure enforcement** via `--check` and `--sync` modes for CI integration.

---

## Overview

The documentation updater is a **separate workflow** from code review:

| Workflow | Purpose | Trigger | Model Cost |
|----------|---------|---------|------------|
| **Code Review** | Find bugs, security issues | Post-edit hook | 0.5x (dual model) |
| **Docs Update** | Keep docs in sync | Post-edit hook | 0.2x (single model) |

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│  1. You edit code (via Cascade or droid exec)                   │
│     ↓                                                           │
│  2. Post-edit hook detects change in src/, scripts/, etc.       │
│     ↓                                                           │
│  3. Queues documentation update task                            │
│     ↓                                                           │
│  4. docs_updater.py runs async (~30 seconds)                    │
│     - Uses gemini-3-flash-preview (0.2x credits)                │
│     - Analyzes what changed (API, CLI, config, etc.)            │
│     - Handles task recovery and retries                         │
│     ↓                                                           │
│  5. Writes updates DIRECTLY to doc files                        │
│     ↓                                                           │
│  6. You see changes in Windsurf diff view                       │
│     - Green lines = additions                                    │
│     - Accept/Reject buttons available                           │
│     ↓                                                           │
│  7. Accept → changes stay | Reject → git restore <file>         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Task Management

The updater includes robust task management to ensure documentation stays in sync even during failures:

- **Stale Task Recovery:** Tasks stuck in "processing" for more than 15 minutes are automatically reset to "pending".
- **Retry Logic:** Failed tasks are automatically retried up to 3 times before being marked as permanently failed.
- **Security:** The updater rejects symlink task files to prevent arbitrary file access or manipulation.
- **Batching:** Tasks are processed in batches (max 10) with a delay to allow changes to accumulate.

---

## User Experience

After the docs updater runs, you see changes in Windsurf exactly like Cascade edits:

```
┌─────────────────────────────────────────────────────────────────┐
│  docs/reference/droid-exec-usage.md                         ✎   │
│                                                                  │
│  502 │ ### Health Endpoints                                      │
│  503 │                                                           │
│  504+│ ### Metrics Endpoint                          [green]     │
│  505+│                                               [green]     │
│  506+│ The `/metrics` endpoint provides...           [green]     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  ✓ Accept  │  ✗ Reject  │  ↺ Revert                       │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Accept** → Changes are kept (commit with your code)
**Reject** → Run `git restore <file>` to revert

---

## Components

### 1. Hook: `fabrik-post-edit-docs.py`

Location: `~/.factory/hooks/fabrik-post-edit-docs.py`

Triggers on file edits in:
- `src/`
- `scripts/`
- `lib/`
- `api/`
- `fabrik/`

Skips:
- `docs/` (no recursive triggers)
- `test_*.py` (test files)
- `__pycache__`, `node_modules`

### 2. Processor: `docs_updater.py`

Location: `/opt/fabrik/scripts/docs_updater.py`

```bash
# Process queue once (AI-driven updates)
python scripts/docs_updater.py

# Run as daemon (continuous)
python scripts/docs_updater.py --daemon

# Update docs for specific file
python scripts/docs_updater.py --file scripts/droid_runner.py

# Integrated with droid-review.sh
./scripts/droid-review.sh --update-docs src/file.py

# Structure enforcement (CI modes)
python scripts/docs_updater.py --check      # Validate, fail on drift (exit code 1)
python scripts/docs_updater.py --sync       # Create missing stubs + sync indexes
python scripts/docs_updater.py --dry-run    # Preview changes without writing
```

### Structure Enforcement (New)

The `--check` and `--sync` modes provide **deterministic structure enforcement**:

| Mode | Purpose | Writes Files? |
|------|---------|---------------|
| `--check` | CI validation — fails if docs out of sync | No |
| `--sync` | Creates missing stubs, updates auto-blocks | Yes |
| `--dry-run` | Preview what `--sync` would do | No |

**What `--check` validates:**
- All plan files indexed in `docs/development/PLANS.md`
- All public modules have `docs/reference/<module>.md`
- Auto-block markers exist where required
- **Stub completeness** - Reference docs aren't empty placeholders
- **Link integrity** - Internal markdown links point to existing files
- **Staleness** - Manual docs have `**Last Updated:**` date
- **Plan consistency** - Plans marked COMPLETE have all checkboxes checked
- **Archive reminder** - Warns if COMPLETE plans are >14 days old

**What `--sync` does:**
- Updates `docs/development/PLANS.md` auto-indexed table with real status/progress
- Creates reference doc stubs for new public modules
- Idempotent: running twice = no diff

**PLANS.md table format:**
```markdown
| Plan | Date | Status | Progress |
|------|------|--------|----------|
| 2026-01-07-docs-automation.md | 2026-01-07 | COMPLETE | 8/8 |
```

Status is extracted from `**Status:**` line in plan file. Progress shows checked/total checkboxes.

### 3. Queue Directory

Location: `/opt/fabrik/.droid/docs_queue/`

Pending tasks are stored as JSON files:
```json
{
  "task_id": "20260105_120000_12345",
  "file_path": "scripts/droid_runner.py",
  "tool_name": "Edit",
  "session_id": "abc123",
  "queued_at": "2026-01-05T12:00:00",
  "status": "pending"
}
```

### 4. Log Directory

Location: `/opt/fabrik/.droid/docs_log/`

Completed tasks and update logs are stored here for audit.

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FABRIK_ROOT` | `/opt/fabrik` | Root directory |
| `FABRIK_DOCS_QUEUE` | `$FABRIK_ROOT/.droid/docs_queue` | Queue directory |
| `FABRIK_DOCS_LOG` | `$FABRIK_ROOT/.droid/docs_log` | Log directory |
| `FABRIK_MODELS_CONFIG` | `$FABRIK_ROOT/config/models.yaml` | Model config |
| `FABRIK_NOTIFY_SCRIPT` | `~/.factory/hooks/notify.sh` | Notification script |

### Model Configuration

In `config/models.yaml`:

```yaml
scenarios:
  documentation:
    description: "Documentation updates, README maintenance, API docs"
    primary: gemini-3-flash-preview
    alternatives:
      - glm-4.7
      - claude-haiku-4-5-20251001
    notes: "Low-cost model for docs (0.2x). Escalate to haiku for complex API docs."
```

---

## Fabrik Documentation Conventions

The updater follows these conventions (from AGENTS.md):

1. **Update docs/INDEX.md structure map** if files added/moved/deleted
2. **Update relevant docs in docs/reference/** based on change type
3. **Add "Last Updated: YYYY-MM-DD"** to modified docs
4. **Use clear titles, purpose statements, runnable examples**
5. **Cross-reference related docs** with relative paths

### Change Type Detection

The updater detects what type of change was made to guide the documentation process:

| Pattern Detected | Change Type | Documentation Updated |
|------------------|-------------|----------------------|
| `@app.get`, `@router.`, `FastAPI`, `APIRouter` | `api_endpoint` | API documentation |
| `argparse`, `ArgumentParser`, `typer` | `cli_command` | CLI reference |
| `os.getenv`, `environ.get`, `Settings` | `configuration` | ENVIRONMENT_VARIABLES.md |
| `/health`, `healthcheck`, `liveness` | `health_endpoint` | Deployment/health docs |
| `SQLAlchemy`, `Prisma`, `Model` | `database_model` | Data model docs |

---

## Notifications

When docs are updated, you receive a notification:

**Windows (WSL):** Toast notification in bottom-right corner
**Linux:** `notify-send` desktop notification
**Fallback:** Terminal message

Message: `📄 Documentation updated for X files - check Windsurf diff view`

---

## Troubleshooting

### Docs not updating?

1. Check if hook is registered:
   ```bash
   grep "fabrik-post-edit-docs" ~/.factory/settings.json
   ```

2. Check queue for pending tasks:
   ```bash
   ls /opt/fabrik/.droid/docs_queue/
   ```

3. Run processor manually:
   ```bash
   python /opt/fabrik/scripts/docs_updater.py
   ```

4. Check logs:
   ```bash
   ls /opt/fabrik/.droid/docs_log/
   cat /opt/fabrik/.droid/docs_log/update_*.json | jq .
   ```

### Want to disable?

Remove the hook from `~/.factory/settings.json`:
```json
// Remove this block:
{
  "type": "command",
  "command": "/home/ozgur/.factory/hooks/fabrik-post-edit-docs.py",
  "timeout": 5
}
```

---

## See Also

- [Auto Review System](auto-review.md) - Code review workflow
- .env.example (authoritative variable reference) - All env vars
- [AGENTS.md](../../AGENTS.md) - Documentation conventions
