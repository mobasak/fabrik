# Traycer Template Mapping & Usage Guide

**Last Updated:** 2026-03-08

This document maps all Traycer prompt templates to their usage contexts and verifies correctness.

---

## Template Metadata System

Templates use YAML frontmatter to declare their purpose:

```yaml
---
displayName: Human-readable name shown in Traycer UI
applicableFor: plan | userQuery | verification | review | epic
---
```

**Traycer uses `applicableFor` to filter templates** in the dropdown based on current mode.

---

## Template Inventory

### Location: `~/.traycer/prompt-templates/`

| Template File | `applicableFor` | Traycer Mode | When Used |
|---------------|-----------------|--------------|-----------|
| `Kilo Plan – 9-Step Workflow.md` | `plan` | **Plan** / **Phases** | Structured planning with full 9-step workflow |
| `Kilo Plan – YOLO Optimized.md` | `plan` | **Plan** / **Phases** | Fast iteration planning (same workflow, lighter tone) |
| `Kilo User Query – Direct.md` | `userQuery` | **All modes** | Direct task handoff to Kilo CLI agents |
| `Kilo Verification – Fix Loop.md` | `verification` | **Review** | Fix issues found by Traycer verification |
| `Kilo Verification – YOLO Optimized.md` | `verification` | **Review** | Fix verification issues (fast iteration) |
| `Kilo Review – Code Review.md` | `review` | **Review** | Fix issues from external code review |
| `_SHARED_REPORTING_REQUIREMENTS.md` | N/A | (Include file) | Shared delimiter/reporting rules |

### Built-in Traycer Templates

| Template | Source | `applicableFor` | Notes |
|----------|--------|-----------------|-------|
| `Default` | Traycer built-in | `userQuery` | Generic prompt, no Fabrik conventions |

**We cannot modify built-in templates.** Use custom templates instead.

---

## Traycer Mode → Template Mapping

### 1. **Plan Mode** (Single-PR tasks)

**What Traycer shows:**
- Default (built-in)
- Kilo User Query – Fabrik Direct ✅ **Use this**

**How it works:**
1. User describes task in Traycer Plan mode
2. Traycer lets you select template + Kilo CLI agent
3. Agent receives task via `TRAYCER_PROMPT` env var
4. Agent executes workflow (Steps 2-5)
5. Agent outputs report with delimiters
6. Traycer handles verification/sync/commit (Steps 6-9)

**Template content:**
- Step 2: Implementation
- Step 2.5: Self-Review ✅
- Step 3: Pre-Kilo Gate
- Step 4: Kilo Review
- Step 5: Post-Kilo Gate
- Report delimiters ✅
- Workflow boundary note ✅

---

### 2. **Phases Mode** (Multi-step projects)

**What Traycer shows:**
- Default (built-in)
- Kilo User Query – Fabrik Direct ✅ **Use this**

**How it works:**
1. User describes feature in Traycer Phases mode
2. Traycer breaks into phases (Phase 1, Phase 2, etc.)
3. For each phase, user selects template + agent
4. Agent executes that phase (Steps 2-5)
5. Traycer verification after each phase
6. Move to next phase after verification passes

**Template content:**
- Same as Plan mode (Kilo User Query – Fabrik Direct)
- Works for individual phase execution
- Each phase gets own report

---

### 3. **Review Mode** (Code audit/verification)

**What Traycer shows:**
- Kilo Verification – Fabrik Fix Loop ✅ **Use for iterative fixes**
- Kilo Verification – YOLO Optimized ✅ **Use for fast fixes**
- Kilo Review – Fabrik Code Review ✅ **Use for external review feedback**

**How it works:**
1. Traycer runs verification on codebase
2. Finds issues (security, config, edge cases, docs)
3. User assigns fixes to Kilo CLI agent with verification template
4. Agent fixes issues and reports
5. Traycer re-verifies
6. Loop until clean

**Template content:**
- Focus on fixing existing issues
- No Step 2.5 (not implementing new features)
- Report delimiters ✅
- Minimal changes philosophy

---

### 4. **Epic Mode** (Large initiatives)

**What Traycer shows:**
- (Unknown - need to test Epic mode)
- Likely uses `applicableFor: epic` templates

**Status:** ⚠️ No epic-specific templates yet

**Expected workflow:**
1. Traycer breaks epic into specs + tickets
2. Specs define requirements
3. Tickets are implementation units
4. Each ticket assigned to agent

**Action needed:** Test Epic mode to see template requirements

---

## Template Correctness Verification

### ✅ Complete Templates (Ready to Use)

| Template | Step 2.5 | Delimiters | Workflow | Status |
|----------|----------|------------|----------|--------|
| Kilo User Query – Fabrik Direct | ✅ Yes | ✅ Yes | ✅ Steps 2-5 only | **READY** |
| Kilo Verification – Fabrik Fix Loop | N/A (fix mode) | ✅ Yes | ✅ Fix loop | **READY** |
| Kilo Verification – YOLO Optimized | N/A (fix mode) | ✅ Yes | ✅ Fix loop | **READY** |
| Kilo Review – Fabrik Code Review | N/A (fix mode) | ✅ Yes | ✅ Fix loop | **READY** |

### ⚠️ Needs Minor Improvement

| Template | Issue | Impact |
|----------|-------|--------|
| Kilo Plan – Fabrik 9-Step | Missing workflow boundary note | Low - works but less explicit |
| Kilo Plan – YOLO Optimized | Missing workflow boundary note | Low - works but less explicit |

**Note:** Plan templates work correctly but don't explicitly state "Traycer handles Steps 6-9". Not critical since they're only used when Traycer manages the workflow anyway.

---

## Which Template Should You Use?

### For Traycer Plan/Phases Mode
**Use:** `Kilo User Query – Fabrik Direct`
- Full 9-step workflow
- Step 2.5 Self-Review
- Clear boundary (AI stops at Step 5)
- Report delimiters for Windsurf panel

**Don't use:** `Default` (no Fabrik conventions, no workflow)

---

### For Traycer Review Mode (Verification Issues)
**Use:** `Kilo Verification – Fabrik Fix Loop` (iterative) or `Kilo Verification – YOLO Optimized` (fast)
- Focused on fixing verification findings
- Minimal changes philosophy
- Report delimiters

---

### For External Code Review Feedback
**Use:** `Kilo Review – Fabrik Code Review`
- Addresses BLOCKER/MAJOR/MINOR issues
- Security/config/edge/docs categories
- Report delimiters

---

## Testing Plan

1. **Plan Mode:** Test with simple task (utility function)
2. **Phases Mode:** Test with multi-step feature (health monitoring)
3. **Review Mode:** Trigger verification, assign fixes
4. **Epic Mode:** Test epic breakdown (if applicable)

**Verify after each test:**
```bash
# Check report was written
ls -lht .droid/traycer-reports/ | head -3
cat .droid/traycer-reports/latest.md

# Check Report Panel updated
# (Should auto-open in Windsurf when report written)
```

---

## Next Steps

1. ✅ Document complete (this file)
2. 🔄 User testing templates with Traycer Phases mode
3. ⏳ Observe Kilo CLI agent responses
4. ⏳ Update templates if issues found
5. ⏳ Test Epic mode (determine template needs)

---

## References

- Workflow authority: `/opt/fabrik/AGENTS.md`
- CLI agent generation: `/opt/fabrik/scripts/generate_kilo_agents.py`
- Report writer: `/opt/fabrik/scripts/traycer_write_report.py`
- Template location: `~/.traycer/prompt-templates/`
