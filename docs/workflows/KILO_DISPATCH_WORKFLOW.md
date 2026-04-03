# Kilo Dispatch Workflow

**Last Updated:** 2026-04-03

> Dispatch tasks from Windsurf Cascade to Kilo CLI agents. This is the reference doc for `scripts/kilo_dispatch.py` and the `/kilo` Windsurf workflow.

---

## Table of Contents

1. [Overview](#overview)
2. [When to Use](#when-to-use)
3. [Available Agents](#available-agents)
4. [Commands Reference](#commands-reference)
5. [Dispatch Flow](#dispatch-flow)
6. [Template Selection](#template-selection)
7. [Environment Variables](#environment-variables)
8. [Report Format](#report-format)
9. [Troubleshooting](#troubleshooting)

---

## Overview

`kilo_dispatch.py` bridges **Windsurf Cascade** (interactive IDE agent) and **Kilo CLI** (autonomous coding agent). It:

1. Builds a prompt from project context (`AGENTS-compact.md` + selectively loaded rule packs based on project type) + task description
2. Writes the prompt to a temp file (simulating Traycer's `TRAYCER_PROMPT_TMP_FILE` pattern)
3. Runs the selected Kilo CLI agent script
4. Reads the structured report from `.droid/traycer-reports/latest.md`

**Windsurf workflow:** `.windsurf/workflows/kilo.md` (activated via `/kilo` slash command)

---

## When to Use

- **Large refactoring** across multiple files that benefits from autonomous execution
- **Compliance fixes** that follow a well-defined spec
- **Tasks that need reasoning** beyond mechanical find-and-replace
- **Budget-conscious execution** using cheaper models for simpler tasks

**Do NOT use for:** Quick edits, single-file changes, or tasks requiring user interaction.

---

## Available Agents

List agents with costs:
```bash
python /opt/fabrik/scripts/kilo_dispatch.py --list
```

Current agent inventory (`~/.traycer/cli-agents/`):

| Agent | Model | Variant | Best For |
|-------|-------|---------|----------|
| `code&fix-1-opus46` | Claude Opus 4.6 | max | Complex multi-file tasks |
| `coding-2-gpt54` | GPT-5.4 | max | General coding |
| `coding-3-gemini31pro` | Gemini 3.1 Pro | high | Budget coding |
| `code&fix-4-gpt53codex` | GPT-5.3 Codex | high | Code generation |
| `fixing-2-gemini31pro` | Gemini 3.1 Pro | max | Review fixes |
| `fixing-3-gpt54` | GPT-5.4 | high | Complex fixes |
| `coding-1-fabrik-coder-qwen32b` | Qwen 2.5 Coder 32B | local | Local free coding |
| `fixing-1-fabrik-fixer-ds16b` | DeepSeek Coder V2 16B | local | Local fast fixes |
| `documentation-1-fabrik-docs-llama8b` | Llama 3.1 8B | local | Local doc generation |
| `reviewing-1-fabrik-reviewer-llama70b` | Llama 3.1 70B | local | Local code review |

**Model names use `kilo/` prefix** (e.g., `kilo/anthropic/claude-opus-4.6`).

---

## Commands Reference

### Basic dispatch
```bash
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "<agent-name>" \
    --task "<task description>" \
    --project "<project-directory>" \
    --template <code|fix|plan|verify>
```

### File-based task (for large specs)
```bash
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "<agent-name>" \
    --task-file "<path-to-task-file.md>" \
    --project "<project-directory>"
```

### With explicit rule packs (required for Fabrik-root work)
```bash
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "<agent-name>" \
    --task "<task>" \
    --project /opt/fabrik \
    --packs PY_CORE,TESTING
```

### Dry-run (preview prompt)
```bash
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "<agent-name>" \
    --task "<task>" \
    --dry-run
```

---

## Dispatch Flow

```
Cascade → kilo_dispatch.py → writes unique temp file (task-<UUID>.md)
                            → sets TRAYCER_PROMPT_TMP_FILE env var
                            → sets CWD to project directory
                            → runs agent .sh script
                                → agent reads temp file
                                → agent saves to .droid/review-context/task-${TRAYCER_TASK_ID}.md
                                → agent calls `kilo run --model kilo/<provider>/<model> ...`
                                → Kilo executes autonomously
                                → agent extracts report → .droid/traycer-reports/latest.md
Cascade ← reads latest.md ← presents report to user

NOTE: Traycer sets CWD to project directory. Agent scripts use relative paths.
NOTE: Task files use unique names (never shared task.md) for multi-instance safety.
```

---

## Template Selection

| Template | Use When | Prompt Template Source |
|----------|----------|----------------------|
| `code` (default) | Single coding task | Coder-for-Plan-Mode |
| `plan` | Phased/epic multi-step task | Coder-for-Phased-Epic-Modes |
| `fix` | Fix review findings | Fix-After-Review |
| `verify` | Fix verification failures | Fix-After-Verification |

---

## Environment Variables

Set by `kilo_dispatch.py`, consumed by agent scripts:

| Variable | Purpose |
|----------|---------|
| `TRAYCER_PROMPT_TMP_FILE` | Path to temp file containing the full prompt |
| `TRAYCER_TASK_ID` | Unique task ID (`cascade-YYYYMMDD-HHMMSS`) |
| `TRAYCER_WORKFLOW` | Always `cascade-dispatch` |
| `TRAYCER_HANDOFF_TYPE` | Template name used |
| `KILO_TIMEOUT` | Max seconds before timeout (default 7200) |

Optional:
| Variable | Purpose |
|----------|---------|
| `KILO_DEBUG` | Set to `1` for verbose agent logging |
| `KILO_RICH_UI` | Set to `0` to disable TUI (default `1`) |

---

## Report Format

After Kilo completes, the agent extracts a structured report:

```
STATUS: COMPLETE | PARTIAL | FAILED
FILES: <comma-separated changed files>
FOLLOWED: <rule IDs followed>
DEVIATED: <deviations or "none">
ENV: <new env vars or "none">
DB: <schema changes or "none">
CHECKS: FG_PRE=PASS|FAIL, SELF_REVIEW=DONE|SKIP, KILO=PASS|SKIP, FG_POST=PASS|FAIL
VERIFY: <verification commands>
```

Report location: `<project>/.droid/traycer-reports/latest.md`

---

## Troubleshooting

### Model not found
Agent scripts must use the `kilo/` prefix for model names:
```bash
# WRONG
--model anthropic/claude-opus-4.6

# CORRECT
--model kilo/anthropic/claude-opus-4.6
```

### Prompt too large
Use `--task-file` instead of `--task` for large specs. The dispatch script writes to a temp file automatically, but very large prompts may still hit shell argument limits inside the agent script.

### Agent script fails silently
Check `~/.traycer/agent-debug.log` for error details.

### No report generated
The Kilo agent may have failed before producing output. Check the transcript in `<project>/.droid/transcripts/`.

### Fabrik-root requires --packs
Running against `/opt/fabrik` (the monorepo root) without `project.yaml` requires explicit `--packs`:
```bash
# ERROR: will fail fast
python scripts/kilo_dispatch.py --agent "coding-2-gpt54" --task "Fix X" --project /opt/fabrik

# CORRECT: specify packs explicitly
python scripts/kilo_dispatch.py --agent "coding-2-gpt54" --task "Fix X" --project /opt/fabrik --packs PY_CORE,TESTING
```
This prevents silent reduced-context runs. Pack IDs must be valid — unknown IDs (e.g. `--packs BOGUS`) also fail fast. The error message lists all available pack IDs.

### TUI not showing
Requires: TTY terminal, `KILO_RICH_UI=1`, and `/opt/fabrik/scripts/kilo_terminal_runner.py` accessible.
