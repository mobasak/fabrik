---
description: Delegate a task to a Kilo CLI agent (any Cascade can use this)
---

# Kilo Dispatch — Run a Kilo CLI Agent from Cascade

## When to Use

When the user says something like:
- "run kilo agent X on task Y"
- "use coding-2-gpt54 to implement Z"
- "dispatch this to code&fix-1-opus46"

## Available Agents

Run this to see all agents with costs and performance:
// turbo
```bash
python /opt/fabrik/scripts/kilo_dispatch.py --list
```

## How to Dispatch

### Step 1: Identify agent and task

The user provides:
- **Agent name** — exact script name or prefix (e.g., `coding-2-gpt54`, `code&fix-1-opus46`)
- **Task description** — what Kilo should do

### Step 2: Run the dispatch

```bash
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "<agent-name>" \
    --task "<task description>" \
    --project "<project-directory>" \
    --template <code|fix|plan|verify>
```

**Template selection:**
- `code` (default) — coding task, uses Coder-for-Plan-Mode template
- `plan` — phased/epic task, uses Coder-for-Phased-Epic-Modes template
- `fix` — fix review findings, uses Fix-After-Review template
- `verify` — fix verification issues, uses Fix-After-Verification template

**For large tasks**, write the task to a file first, then use `--task-file`:
```bash
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "<agent-name>" \
    --task-file "<path-to-task.md>" \
    --project "<project-directory>"
```

**IMPORTANT:** Run this as a **non-blocking** command so the user can see the Kilo TUI in the terminal. Set a reasonable wait (e.g., 5000ms) to catch early failures.

### Step 3: Monitor

The Kilo agent runs in a TUI — both you and the user can watch it. Wait for the command to complete using `command_status`.

### Step 4: Read the report

After Kilo finishes, read the report:
// turbo
```bash
cat <project-directory>/.droid/traycer-reports/latest.md
```

### Step 5: Report to user

Present the Kilo report summary:
- **STATUS** — COMPLETE / PARTIAL / FAILED
- **FILES** — what was changed
- **CHECKS** — gate results (SELF_REVIEW, KILO, FG)
- **VERIFY** — verification commands to run

If STATUS is not COMPLETE, explain what went wrong and suggest next steps.

### Optional: Verify independently

After reading the report, you can independently verify by running:
// turbo
```bash
cd <project-directory> && python scripts/final_gate.py
```

## Dry-Run (Preview Prompt)

To see what prompt would be sent without running Kilo:
// turbo
```bash
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "<agent-name>" \
    --task "<task>" \
    --dry-run
```

## Examples

```bash
# Coding task with best agent
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "code&fix-1-opus46" \
    --task "Add Stripe subscription integration to the SaaS skeleton" \
    --project /opt/my-saas

# Fix task with cheaper agent
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "fixing-2-gemini31pro" \
    --task "Fix the 3 TypeScript errors in app/api/health/route.ts" \
    --template fix \
    --project /opt/my-saas

# Plan-based task from a spec file
python /opt/fabrik/scripts/kilo_dispatch.py \
    --agent "coding-3-gemini31pro" \
    --task-file specs/my-saas/02-spec.md \
    --template plan \
    --project /opt/my-saas
```
