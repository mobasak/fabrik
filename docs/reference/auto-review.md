# Automatic Code Review & Documentation Update

**Last Updated:** 2026-01-05

Fabrik automatically reviews code after every edit and will run documentation updates for changes that the PostToolUse hook flags as needing docs coverage (API/CLI/config surface changes), whether edits come from Cascade, droid exec, or any Factory-enabled tool.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTO-REVIEW FLOW                              │
└─────────────────────────────────────────────────────────────────┘

  Code Change                   PostToolUse Hook
  (any source)                  (fabrik-post-edit.py)
       │                               │
       ▼                               ▼
  ┌──────────┐                 ┌───────────────┐
  │ Edit/    │────────────────▶│ Queue task    │
  │ Write    │                 │ for review    │
  └──────────┘                 └───────┬───────┘
                                       │
                                       ▼
                               ┌───────────────┐
                               │ Async review  │
                               │ processor     │
                               └───────┬───────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
           ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
           │ Model 1      │   │ Model 2      │   │ Docs update  │
           │ review       │   │ review       │   │ check        │
           └──────────────┘   └──────────────┘   └──────────────┘
                    │                  │                  │
                    └──────────────────┴──────────────────┘
                                       │
                                       ▼
                               ┌───────────────┐
                               │ Notification  │
                               │ if issues     │
                               └───────────────┘
```

---

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `fabrik-post-edit.py` | `~/.factory/hooks/` | PostToolUse hook - queues changed files |
| `review_processor.py` | `/opt/fabrik/scripts/` | Async processor - runs dual-model review |
| `config/models.yaml` | `/opt/fabrik/config/` | Defines which models to use (dynamic) |

---

## Configuration

### Model Selection

Review models are defined in `config/models.yaml`:

```yaml
scenarios:
  code_review:
    description: "Code review, bug finding, convention compliance"
    models:
      - gpt-5.1-codex-max
      - gemini-3-flash-preview
    notes: "ALWAYS use BOTH models in parallel"
```

Model names are refreshed automatically from Factory docs. No hardcoded names.

### Hook Settings

Configured in `~/.factory/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|Create",
        "hooks": [
          {
            "type": "command",
            "command": "/home/ozgur/.factory/hooks/fabrik-post-edit.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

### Notifications

The review processor sends alerts via a notification script. Override the script path with an environment variable if you use a custom notifier (Slack, email, etc.).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FABRIK_NOTIFY_SCRIPT` | No | `~/.factory/hooks/notify.sh` | Path to an executable that accepts a JSON payload on stdin: `{"message": "<text>"}` |

Ensure the script is executable and handles the JSON input. The default uses `notify.sh` from the Factory hook set for desktop notifications.

### Path Overrides

The processor resolves paths from environment variables so it can run from custom locations or alternate queues:

- `FABRIK_ROOT` — Base path for the Fabrik repo (default: `/opt/fabrik`).
- `FABRIK_REVIEW_QUEUE` — Queue directory for pending review tasks (default: `${FABRIK_ROOT}/.droid/review_queue`).
- `FABRIK_REVIEW_RESULTS` — Directory for completed review results (default: `${FABRIK_ROOT}/.droid/review_results`).
- `FABRIK_MODELS_CONFIG` — Path to the models configuration file (default: `${FABRIK_ROOT}/config/models.yaml`).

---

## What Gets Reviewed

### Included
- All source files (`src/`, `lib/`, `api/`)
- Configuration files
- Scripts

### Excluded
- `.git/`, `__pycache__/`, `.venv/`
- Log files, compiled files
- The review queue itself

---

## Review Focus

The dual-model review checks for:

1. **Security vulnerabilities**
2. **Error handling gaps**
3. **Fabrik convention violations**
   - No hardcoded localhost
   - Proper health checks
   - Environment variables for config
4. **Logic errors**

---

## Documentation Updates

The processor only runs the documentation update routine for queue items flagged with `needs_docs_update` (set by the PostToolUse hook when enqueueing files). It does **not** infer this from file paths on its own, so ensure the hook marks files that touch user-facing surfaces (API endpoints, CLI commands, or configuration).

When invoked, the docs pass updates:
- `docs/reference/` for API changes
- `docs/CONFIGURATION.md` for configuration changes
- `docs/INDEX.md` structure map when docs are added, moved, or removed

---

## Manual Operations

### Process Queue Manually

```bash
python3 /opt/fabrik/scripts/review_processor.py
```

### Run as Daemon

```bash
python3 /opt/fabrik/scripts/review_processor.py --daemon
```

### Check Queue Status

```bash
ls -la /opt/fabrik/.droid/review_queue/
```

### View Completed Reviews

```bash
ls -la /opt/fabrik/.droid/review_results/
```

---

## Troubleshooting

### Reviews Not Running

1. Check hook is enabled:
   ```bash
   grep fabrik-post-edit ~/.factory/settings.json
   ```

2. Check hook is executable:
   ```bash
   ls -la ~/.factory/hooks/fabrik-post-edit.py
   ```

3. Test hook manually:
   ```bash
   echo '{"tool_name": "Edit", "tool_input": {"file_path": "/opt/fabrik/src/test.py"}}' | \
     python3 ~/.factory/hooks/fabrik-post-edit.py
   ```

### Wrong Models Used

Models are loaded from `config/models.yaml`. Check with:

```bash
python3 scripts/droid_models.py recommend code_review
```

### Slow or Silent Runs

If a review appears stuck, the processor will emit periodic diagnostics when the optional `process_monitor` module is installed. These messages report CPU/IO/network activity to help identify hangs. Without the module, the processor still runs but only prints a simple inactivity warning.

---

## See Also

- [Verification Framework](verification-framework.md)
- [Droid Exec Usage](droid-exec-usage.md)
- [AGENTS.md](../../AGENTS.md)
