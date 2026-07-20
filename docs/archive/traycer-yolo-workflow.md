# Traycer Phased YOLO Workflow with Kilo Agents

**Last Updated:** 2026-02-25

This document describes the complete Phased YOLO workflow for Fabrik using custom Kilo CLI agents.

## Overview

**Phased YOLO Mode** automates the entire development cycle: Plan Generation → Implementation → Self-Review (MANDATORY) → Pre-Kilo Gate → Kilo Review → Post-Kilo Gate → External Verification → Sync → Commit → Next Phase.

**Key Components:**
- **Traycer:** Orchestrator (plan generation, verification analysis, commit management)
- **Kilo Agents:** Custom CLI agents (implementation, fixing)
- **Templates:** Custom prompt wrappers (Fabrik conventions + workflow instructions)

---

## The 9-Step Workflow

| Step | Who | Action | Configuration |
|------|-----|--------|---------------|
| **1** | Traycer | Create Phase | - |
| **2** | Kilo Code Agent | Implement | Plan Tab: Execution Agent |
| **2.5** | Kilo Code Agent | Self-Review (MANDATORY) | Template instructs this |
| **3** | Kilo Code Agent | Run Pre-Kilo Gate | Template instructs this |
| **4** | Kilo Code Agent | Run Kilo Review (self-review) | Template instructs this |
| **5** | Kilo Code Agent | Run Post-Kilo Gate | Template instructs this |
| **6** | Traycer + Kilo Code Agent | Verify → Fix → Re-verify | Verification Tab |
| **7** | Kilo Code Agent | Run Sync | Template instructs this |
| **8** | Traycer | Run commit.sh | Commit Tab |
| **9** | Traycer | Next Phase | - |

---

## Configuration (YOLO Settings Screen)

### **Plan Tab**

**Option 1: Generate Plan (Recommended)**
- ☐ Skip plan generation: **UNCHECKED**
- Execution Agent: **Kilo Code Gemini-3-Flash-Preview High**
- Template for plan generation: **Kilo Plan – YOLO Optimized**
- Execution timeout: **10 min**

**Option 2: User Query (Simple Tasks)**
- ☑ Skip plan generation: **CHECKED**
- Execution Agent for user query handoff: **Kilo Code Gemini-3-Flash-Preview High**
- Template for user query: **Kilo User Query – YOLO Mode** (if created)
- Execution timeout: **10 min**

### **Verification Tab**

- ☐ Skip verification: **UNCHECKED**
- Execution Agent: **Kilo Code Gemini-3-Flash-Preview High** ← **SAME agent as Plan**
- Template for verification: **Kilo Verification – YOLO Optimized**
- Severity levels to verify: **Critical, Major** (skip Minor for speed)
- Maximum number of Re-verification attempts: **3**
- Execution timeout: **10 min**

### **Commit Tab**

- ☑ Skip commit: **CHECKED** (for testing) or **UNCHECKED** (for production)
- Commit Script: `commit.sh` (automatic, cannot be changed)

---

## Session Continuity Mechanism

**How agents maintain context across handoffs:**

Traycer provides two key environment variables:
- `TRAYCER_TASK_ID` - Stable across entire task lifecycle
- `TRAYCER_PHASE_ID` - Changes per phase breakdown

```bash
# Agent script determines session title (from generate_kilo_agents.py)
SESSION_TITLE="${TRAYCER_PHASE_ID:-${TRAYCER_TASK_ID:-kilo-session}}"

# Implementation handoff - Phase A
export TRAYCER_TASK_ID="a1c68353-f282-45d7-8ef5-e1f9262d6c31"
export TRAYCER_PHASE_ID="17112c9f-a4d8-4899-a638-3d321650e77e"
kilo run --session-title "$SESSION_TITLE" ...  # Uses PHASE_ID

# Verification fix handoff - SAME Phase A
export TRAYCER_TASK_ID="a1c68353-f282-45d7-8ef5-e1f9262d6c31"  # SAME
export TRAYCER_PHASE_ID="17112c9f-a4d8-4899-a638-3d321650e77e"  # SAME
kilo run --session-title "$SESSION_TITLE" ...  # SAME session

# Next phase handoff - Phase B (NEW session)
export TRAYCER_TASK_ID="a1c68353-f282-45d7-8ef5-e1f9262d6c31"  # SAME
export TRAYCER_PHASE_ID="d6722e85-1bf6-42cd-b71b-274a35023787"  # NEW
kilo run --session-title "$SESSION_TITLE" ...  # NEW session
```

**Session Scoping:**
| Scope | Session ID Source | When Same |
|-------|-------------------|------------|
| Within phase | `TRAYCER_PHASE_ID` | Implementation + Verification fix |
| Across phases | `TRAYCER_TASK_ID` | Only if PHASE_ID missing |

**Result within a phase:** Agent remembers:
- Original plan
- Implementation decisions
- Files modified
- Verification comments being fixed

**Across phases:** Sessions are isolated (new PHASE_ID = new session).

**Critical:** Use the **SAME agent** in both Plan and Verification tabs to maintain session continuity within a phase.

---

## Detailed Execution Flow

### **Phase 1: Plan Handoff**

```
1. Traycer generates implementation plan
2. Traycer wraps plan with "Kilo Plan – YOLO Optimized" template
3. Traycer invokes "Kilo Code Gemini-3-Flash-Preview High.sh"
   └─ exports TRAYCER_TASK_ID, TRAYCER_PROMPT
4. Agent executes Steps 2-7:

   Step 2: Implement code
   - Read wrapped plan
   - Follow Fabrik conventions (env vars, multi-environment, CHANGELOG)
   - Apply Cascade behavior (check before create, minimal changes)

   Step 3: Pre-Kilo Gate
   - Run: python scripts/final_gate.py
   - Fix: formatting, lint, types, semgrep, etc.
   - Re-run until all checks PASS

   Step 4: Kilo Review (Self-Review)
   - Run: python scripts/kilo_code_review.py review <files> --plan .droid/review-context/task-${TRAYCER_TASK_ID}.md --review-agent ask --output json
   - Read JSON verdict and issues
   - Fix ALL issues (BLOCKER, MAJOR, MINOR)
   - Re-review with --session continue until verdict=PASS
   - Max 5 iterations

   Step 5: Post-Kilo Gate
   - Run: python scripts/final_gate.py --lean --json (Tier 1 — changelog check included)
   - Fix any failures including missing changelog entry
   - Re-run until status: "success"

   Step 7: Sync
   - Run: python scripts/final_gate.py --sync
   - Sync Windsurf Extensions + Cascade Backup
   - No quality checks (already passed)

5. Agent script exits with code 0
6. Traycer detects completion (inferred: waits for process exit)
```

### **Phase 2: Traycer Verification (Step 6)**

```
1. Traycer analyzes implementation
   - Checks against plan requirements
   - Validates Fabrik conventions
   - Generates verification comments with severity (Critical/Major/Minor)

2. IF issues found with selected severity levels:

   a. Traycer wraps comments with "Kilo Verification – YOLO Optimized" template

   b. Traycer invokes "Kilo Code Gemini-3-Flash-Preview High.sh" (SAME agent)
      └─ exports TRAYCER_TASK_ID (SAME ID), TRAYCER_PROMPT (verification comments)

   c. Agent fixes issues:
      - Reads verification comments
      - Applies fix strategy (minimal changes, check before create)
      - Fixes all reported issues
      - Updates CHANGELOG if code changed

   d. Agent script exits with code 0

   e. Traycer re-verifies
      - If still has issues → repeat (max 3 attempts)
      - If clean → proceed to commit

3. IF no issues or all fixed → proceed to Phase 3
```

### **Phase 3: Commit (Step 8)**

```
1. Traycer invokes commit.sh script
   └─ Pre-commit runs ONLY 4 blockers:
      - check-added-large-files
      - check-merge-conflict
      - detect-private-key
      - forbid-secrets

2. commit.sh exits with code 0

3. Traycer moves to next phase (Step 9)
```

---

## Template Architecture

### **Kilo Plan – YOLO Optimized** (100 lines)

**Purpose:** Wrap Traycer-generated plan with Fabrik conventions and workflow instructions

**Contains:**
- Project conventions (AGENTS.md, .windsurf/rules/)
- Critical rules (hardcoding, multi-environment, CHANGELOG)
- Behavioral rules (check/minimal/present)
- Key patterns (env vars, health checks, temp dir)
- Workflow steps (Steps 3-7 with commands)

**Handlebars:** `{{planMarkdown}}`

### **Kilo Verification – YOLO Optimized** (50 lines)

**Purpose:** Wrap Traycer verification comments with fix guidance

**Contains:**
- Behavioral rules (check/minimal/present)
- Critical patterns (env vars, multi-environment, CHANGELOG)
- Fix priorities (BLOCKER/MAJOR/MINOR)
- Structured report format

**Handlebars:** `{{comments}}`

### **Original Templates (Available)**

- **Execute** (180 lines) - More comprehensive, includes code examples
- **Fix** (90 lines) - More detailed, includes checklists

**Use case:** Manual workflows or when more guidance needed

---

## Agent Scripts

**Location:** `~/.traycer/cli-agents/`

**Available Agents:**

| Agent | Model | Variant | Cost per 10M | Use Case |
|-------|-------|---------|--------------|----------|
| Kilo Code Gemini-3-Flash-Preview High | Gemini 3 Flash | high | $0.75/$3 | Standard (recommended) |
| Kilo Code Gemini-3.1-Pro-Thinking High | Gemini 3.1 Pro | high | $12.50/$50 | Complex logic |
| Kilo Code Sonnet-4.6 High | Claude Sonnet 4.6 | high | $30/$150 | Critical features |
| Kilo Code GPT-5.2-Codex High | GPT-5.2 | high | $17.50/$140 | OpenAI preference |
| Kilo Code GPT-5.3-Codex High | GPT-5.3 | high | TBD | Bleeding edge |

**All agents:**
- Work in current directory (Traycer sets working directory)
- Accept `TRAYCER_TASK_ID` for session continuity
- Accept `TRAYCER_PROMPT` for template-wrapped content
- Call Kilo via absolute path: `/opt/fabrik/scripts/kilo_code_review.py`
- Output JSON for Traycer parsing

---

## Traycer Integration Contract

**These invariants MUST be maintained in all agent scripts and documentation:**

### 1. Working Directory
- **Traycer sets CWD to the project directory** before invoking agent scripts
- Agent scripts MUST use relative paths for `.droid/`, `scripts/`, etc.
- NEVER override CWD or add project-root detection — it's already correct
- This enables multi-instance: each Traycer instance runs in its own project

### 2. Unique Task Files (CRITICAL)
- Task context MUST use unique filenames: `task-${TRAYCER_TASK_ID}.md`
- **NEVER use a shared `task.md`** — concurrent agents WILL overwrite each other
- Format: `.droid/review-context/task-${TRAYCER_TASK_ID:-${TRAYCER_PHASE_ID:-$(date +%s)}}.md`

### 3. Multi-Instance Safety
- Multiple Traycer/Kilo/Windsurf instances can run simultaneously on different projects
- Per-run isolation: `$OUTPUT_FILE=$(mktemp)` — unique temp file per run
- Per-project isolation: `.droid/` is relative to CWD (project directory)
- Per-task isolation: `TRAYCER_TASK_ID` (UUID) and `TRAYCER_PHASE_ID` (UUID)
- Report files: timestamped + UUID slug, `latest.md` written atomically via `rename()`
- Shared log: `~/.traycer/agent-debug.log` is append-only (interleaved but harmless)

### 4. Completion Detection

**YOLO Mode uses TWO detection mechanisms:**

1. **Artifact File Watcher (YOLO-specific):**
   - Traycer watches `~/.traycer/yolo_artifacts/<artifact_id>.json`
   - When this file is created, Traycer immediately considers the task complete
   - **CRITICAL:** If agent creates this file mid-task, Traycer detects premature completion
   - **FIX (2026-03-26):** Shell script strips `<task_completion_requirement>` from prompt and creates artifact AFTER kilo exits

2. **Shell Integration (Plan/Review modes):**
   - VS Code's `onDidEndTerminalShellExecution` API
   - Detects when shell script process exits
   - Exit code 0 = success, non-zero = failure

**Why this matters:**
- Artifact watcher is FASTER than shell integration
- If agent creates artifact before exiting, Traycer moves to next phase while agent still runs
- This caused Phase 1 to "complete" while kilo was still executing

**Current solution (generate_kilo_agents.py):**
```bash
# Extract artifact ID, strip from prompt so agent doesn't create it
ARTIFACT_ID=$(echo "$PROMPT" | grep -oP 'yolo_artifacts/\K[a-f0-9-]+(?=\.json)')
PROMPT=$(echo "$PROMPT" | sed '/<task_completion_requirement>/,/<\/task_completion_requirement>/d')

# ... kilo runs ...

# Create artifact AFTER kilo exits successfully
if [ -n "$ARTIFACT_ID" ] && [ $EXIT_CODE -eq 0 ]; then
    echo '{}' > "$HOME/.traycer/yolo_artifacts/$ARTIFACT_ID.json"
fi
```

- Traycer does its OWN code analysis for verification (not dependent on report files)
- `.droid/traycer-reports/latest.md` is for the Windsurf Report Panel display only

### 5. Error Visibility
- Agent scripts MUST log errors to `~/.traycer/agent-debug.log`
- NEVER use `|| true` to swallow errors from critical operations (report writer, gate scripts)
- Capture exit codes and stderr; log failures explicitly

---

## What's Factual vs Inferred

### **Factual (Confirmed):**
- ✅ Traycer generates plans
- ✅ Traycer wraps content with templates
- ✅ Traycer hands off to CLI agents
- ✅ Traycer verifies implementation (its own AI analysis)
- ✅ Verification handoff sends issues back to agents
- ✅ Session ID maintained via `TRAYCER_TASK_ID` / `TRAYCER_PHASE_ID`
- ✅ Agents are shell scripts in `~/.traycer/cli-agents/`
- ✅ Traycer sets CWD to project directory
- ✅ Traycer detects completion via process exit code
- ✅ Task files use unique names per TRAYCER_TASK_ID

### **Inferred:**
- ❓ Whether execution is synchronous or asynchronous (assumed: blocking)
- ❓ How timeout is enforced by Traycer IDE (agent scripts have their own timeout)

---

## Testing Checklist

Before running YOLO mode:

- [ ] Phase created in Traycer
- [ ] YOLO button clicked
- [ ] Plan Tab configured (agent + template selected)
- [ ] Verification Tab configured (SAME agent + template selected)
- [ ] Commit Tab configured (skip checked for testing)
- [ ] All CLI agent scripts executable (`chmod +x`)
- [ ] Kilo script accessible at `/opt/fabrik/scripts/kilo_code_review.py`
- [ ] Templates exist in `~/.traycer/prompt-templates/`

---

## Monitoring During Execution

**What to watch:**

1. **Plan Handoff:**
   - Does agent receive wrapped plan?
   - Does agent run Steps 3-7?
   - Does agent maintain session in `.droid/.droid_sessions.json`?
   - Does Traycer proceed to verification after agent completes?

2. **Verification:**
   - Does Traycer analyze implementation?
   - Does Traycer generate verification comments?
   - Are comments wrapped with verification template?
   - Does SAME agent receive them with SAME session ID?
   - Does agent fix issues?
   - Does Traycer re-verify?

3. **Commit:**
   - Does commit.sh run after verification passes?
   - Does pre-commit run only 4 blockers?

4. **Session Continuity:**
   - Check `.droid/.droid_sessions.json` - should have entry for `TRAYCER_TASK_ID`
   - Check `.droid/review-context/task-${TRAYCER_TASK_ID}.md` - should have original plan

---

## Troubleshooting

**Agent doesn't complete:**
- Check agent script has execute permission
- Check agent script can find `/opt/fabrik/scripts/kilo_code_review.py`
- Check agent receives `TRAYCER_TASK_ID` and `TRAYCER_PROMPT`

**Session not maintained:**
- Verify SAME agent selected in Plan and Verification tabs
- Check `.droid/.droid_sessions.json` exists and has correct ID

**Traycer doesn't proceed:**
- Agent may have exited with non-zero code
- Check timeout settings
- Look for error messages in Traycer UI

---

## Success Criteria

✅ **Phase completes successfully when:**
1. Kilo Code Agent implements code (Steps 2-7)
2. Traycer verification finds no issues OR agent fixes all issues
3. commit.sh runs successfully (if not skipped)
4. Traycer moves to next phase

✅ **Session continuity working when:**
- Agent in verification handoff references original plan
- Agent fixes issues based on its own implementation
- `.droid/.droid_sessions.json` shows single session entry for the phase

---

## Next Steps After Validation

If test execution confirms expected behavior:
1. Document any discovered gaps between inferred vs actual behavior
2. Create production YOLO configurations for common workflows
3. Add monitoring/logging for debugging failed phases
4. Optimize timeout values based on actual execution times
