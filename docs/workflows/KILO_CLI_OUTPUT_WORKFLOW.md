# Kilo CLI Output & Completion Workflow

**Last Updated:** 2026-03-26

> How Kilo CLI agent output is captured, saved, and how Traycer detects task completion.

---

## Table of Contents

1. [Output Storage](#output-storage)
2. [Traycer Completion Detection](#traycer-completion-detection)
3. [Script Compatibility](#script-compatibility)
4. [Troubleshooting](#troubleshooting)

---

## Output Storage

Every Kilo CLI agent run saves output to **two locations**:

### 1. Project Transcripts (Always Saved)

**Location:** `<project>/.droid/transcripts/`

**Format:** `<YYYYMMDD-HHMMSS>-<role>-<priority>-<model>-exit<code>-raw.txt`

**Example:** `.droid/transcripts/20260326-001608-coding-3-gemini31pro-exit0-raw.txt`

**Contains:**
- Full raw terminal output from kilo
- Reasoning steps (if `--thinking` flag used, though often `[REDACTED]` by OpenRouter)
- Tool calls and file edits
- The `BEGIN_TRAYCER_REPORT_MD...END_TRAYCER_REPORT_MD` block

**Retention:** Unlimited (manual cleanup)

### 2. Kilo Internal Sessions (Kilo CLI Storage)

**Access:**
```bash
kilo session list                    # List all sessions
kilo export <sessionID> > file.json  # Export full session as JSON
```

**Contains:**
- Structured message history
- Token counts and costs
- Tool invocations with parameters
- Model metadata

**Retention:** Managed by Kilo CLI

---

## Traycer Completion Detection

### Two Detection Mechanisms

Traycer uses **different mechanisms** depending on mode:

#### 1. Artifact File Watcher (YOLO Mode)

In YOLO mode, Traycer watches `~/.traycer/yolo_artifacts/<artifact_id>.json`:
- When file is created → Traycer immediately considers task complete
- **CRITICAL:** This is FASTER than shell integration
- If agent creates artifact mid-task → premature completion detection

**Problem discovered (2026-03-26):**
Traycer's prompt includes `<task_completion_requirement>` telling agent to create artifact file.
Agent creates it BEFORE finishing → Traycer moves to next phase while agent still runs.

**Solution:** Shell script intercepts and handles artifact creation:
```bash
# Extract artifact ID, strip from prompt
ARTIFACT_ID=$(echo "$PROMPT" | grep -oP 'yolo_artifacts/\K[a-f0-9-]+(?=\.json)')
PROMPT=$(echo "$PROMPT" | sed '/<task_completion_requirement>/,/<\/task_completion_requirement>/d')

# ... kilo runs ...

# Create artifact AFTER kilo exits
if [ -n "$ARTIFACT_ID" ] && [ $EXIT_CODE -eq 0 ]; then
    echo '{}' > "$HOME/.traycer/yolo_artifacts/$ARTIFACT_ID.json"
fi
```

#### 2. Shell Integration (Plan/Review Modes)

Uses **VS Code's `onDidEndTerminalShellExecution` API**:
- Tracks command boundaries via OSC escape sequences
- Detects when shell script process exits
- Reports exit code

### What Traycer Sees

| Exit Code | Meaning | Traycer Action |
|-----------|---------|----------------|
| 0 | Success | Proceed to verification or next phase |
| 1 | Agent failed | Report failure, may retry |
| 124 | Timeout | Report timeout, task failed |
| >128 | Signal (interrupted) | Report interruption |

### Critical Constraints

**These patterns BREAK shell integration:**

1. **`| tee` pipelines** — Pipeline makes shell track `tee`, not `kilo`
2. **Rich TUI (Textual)** — Alternate screen buffer corrupts OSC sequences
3. **`--format json`** — Produces no output with Kilo 7.0.33+ (silent failure)

**Working pattern (used in Traycer mode):**
```bash
# Background kilo + wait = clean exit detection
timeout "$TIMEOUT" kilo run ... > "$OUTPUT_FILE" 2>&1 &
KILO_PID=$!
tail -f "$OUTPUT_FILE" &
TAIL_PID=$!
wait "$KILO_PID"
EXIT_CODE=$?
kill "$TAIL_PID" 2>/dev/null
exit $EXIT_CODE
```

---

## Script Compatibility

### generate_kilo_agents.py Modes

| Mode | Detected By | Pattern | Shell Integration |
|------|-------------|---------|-------------------|
| **Traycer** | `TRAYCER_TASK_ID` set | Background + wait | ✅ Works |
| **Interactive (TUI)** | `KILO_RICH_UI=1` + TTY | kilo_terminal_runner.py | ❌ N/A (no Traycer) |
| **Interactive (Plain)** | No TUI | `tee` pipeline | ❌ N/A (no Traycer) |

### Verification

To verify scripts are Traycer-compatible:
```bash
grep -A10 "TRAYCER_TASK_ID" ~/.traycer/cli-agents/*.sh | head -20
```

Expected: Background kilo with `wait`, NOT `| tee` pipeline.

---

## Troubleshooting

### Traycer doesn't detect completion

**Symptoms:** Agent finished but Traycer stuck on "Executing..."

**Causes:**
1. Script uses `| tee` pipeline (breaks shell integration)
2. Script uses Rich TUI (alternate screen buffer)
3. Script exits before shell integration can track it

**Fix:** Regenerate scripts with `python scripts/generate_kilo_agents.py`

### Transcript missing or empty

**Check:**
```bash
ls -la <project>/.droid/transcripts/
```

**If empty:** Agent may have failed before producing output. Check:
```bash
tail ~/.traycer/agent-debug.log
```

### Traycer detects completion prematurely

**Cause:** Shell integration tracking wrong process (e.g., `tee` instead of `kilo`)

**Fix:** Ensure Traycer mode uses background + wait pattern (see above)

### No output from agent

**Cause:** `--format json` produces no output with Kilo 7.0.33+

**Fix:** Use `--format default` (already fixed in generate_kilo_agents.py as of 2026-03-25)

---

## Related Documentation

- `docs/traycer/traycer-yolo-workflow.md` — Full YOLO workflow with completion contract
- `docs/workflows/KILO_DISPATCH_WORKFLOW.md` — Dispatching from Cascade to Kilo
- `docs/traycer/TRAYCER-KILO-AGENTS-GUIDE.md` — Exit codes and troubleshooting
