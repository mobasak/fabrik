# Windsurfrules Patch - AI Spec Pipeline Integration

**Add these sections to your existing `/opt/_project_management/windsurfrules` file.**

This patch integrates the 5-Mode control system and spec pipeline without duplicating existing rules.

---

## Section to Add: After "## Environment Context"

```markdown
---

## AI Spec Pipeline Integration

This project uses the **AI Spec Pipeline** for structured development:
- Stage 1 (Discovery) → Stage 2 (Planning) → Stage 3 (Execution)
- See: `/opt/_project_management/ai-spec-pipeline/README.md`

### Modes (Operating Control Layer)

| Mode | Name    | Tool                 | Purpose                       |
| ---- | ------- | -------------------- | ----------------------------- |
| 1    | Explore | ChatGPT / Factory    | Reduce uncertainty            |
| 2    | Design  | Factory Droid        | Decide structure and plan     |
| 3    | Build   | Windsurf Cascade     | Implement working changes     |
| 4    | Verify  | Factory Droid        | Audit correctness and safety  |
| 5    | Ship    | Factory / Cascade    | Document and make recoverable |

### Spec Freeze Rule

Once Stage 3 (Execution) begins:
> **All spec documents in `spec_out/` are read-only.**
> Any requirement change requires returning to Stage 1 or Stage 2.

### Mandatory Verification Gate

After every task implementation:
1. Builder (Cascade) implements and runs self-review
2. Verifier (Droid) audits changes
3. Task is NOT DONE until Mode 4 passes

**Verifier never fixes. Builder never self-verifies.**

---
```

---

## Section to Add: Under "## Project Setup Requirements"

```markdown
### Spec Pipeline Folders (if using AI Spec Pipeline)

```
/opt/<project>/
├── spec_out/                    # Stage 1 output (frozen)
│   └── SPEC.md
├── plan/                        # Stage 2 output (frozen)
│   ├── IMPLEMENTATION_PLAN.md
│   └── task_prompts/
│       ├── task_1.1.md
│       └── ...
└── [standard project structure]
```

Reference: `/opt/_project_management/ai-spec-pipeline/`
```

---

## Section to Add: Under "## Before-Writing-Code Protocol"

```markdown
### Mode Header (if using AI Spec Pipeline)

When executing Stage 3 tasks, every task prompt MUST include:

```
Stage: 3 — Execution
Current Mode: Mode 3 — Build
Spec Status: Frozen
Scope: Task X.Y only
Next Required Step: Mode 4 — Verify with Factory Droid (Codex-Max)
```

After completing the task and self-review, run Mode 4 verification:

```bash
droid exec --auto low "[verification prompt from plan/task_prompts/]"
```
```

---

## Section to Add: Under "## Self-Review Before Done (MUST)"

```markdown
### Mode 4 Verification (if using AI Spec Pipeline)

After self-review passes, Mode 4 verification is mandatory:

1. Run `droid exec --auto low` with verification prompt
2. Droid checks:
   - Spec compliance
   - Windsurfrules compliance (no hardcoded localhost, etc.)
   - Code quality
3. If FAIL: apply fixes in Cascade, re-verify
4. If PASS: update tasks.md, proceed to next task

**A task is complete only when both self-review AND Mode 4 pass.**
```

---

## Section to Add: Under "## Continue Project Protocol"

```markdown
### Resume with AI Spec Pipeline

When resuming a project using the spec pipeline:

1. Read `tasks.md` for current phase and next task
2. Read `spec_out/SPEC.md` for context (but don't modify - frozen)
3. Load task prompt from `plan/task_prompts/task_X.Y.md`
4. Open fresh Cascade chat
5. Execute task per Mode 3 → Mode 4 → Mode 5 flow
```

---

## Files to Create

Create folder: `/opt/_project_management/ai-spec-pipeline/`

Copy these files into it:
- `README.md` - Pipeline overview
- `stage1_discovery_prompt.md` - Discovery session prompt
- `stage2_traycer_prompt.md` - Planning prompt
- `stage3_cascade_execution.md` - Execution instructions
- `AI_OPERATING_CONSTITUTION.md` - Quick reference

---

## Symlink for Project Access

To make pipeline docs available in any project:

```bash
# Create symlink in project
ln -s /opt/_project_management/ai-spec-pipeline /opt/<project>/ai-spec-pipeline

# Or copy templates when starting new project
cp /opt/_project_management/ai-spec-pipeline/stage*.md /opt/<project>/plan/
```
