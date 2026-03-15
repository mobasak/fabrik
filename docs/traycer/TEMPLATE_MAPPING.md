# Traycer Template Mapping & Usage Guide

**Last Updated:** 2026-03-15

This document maps all Traycer prompt templates to their usage contexts and verifies correctness.

---

## Template Metadata System

Templates use YAML frontmatter to declare their purpose:

```yaml
---
displayName: Human-readable name shown in Traycer UI
applicableFor: plan | user query | verification | review | generic
---
```

**Official Traycer template types:**
- `plan` → Handlebars: `{{planMarkdown}}`
- `user query` → Handlebars: `{{userQuery}}`
- `verification` → Handlebars: `{{comments}}`
- `review` → Handlebars: `{{reviewComments}}`
- `generic` → Handlebars: `{{basePrompt}}`

**Note:** Traycer does NOT support `applicableFor: all`, partials, or includes.

---

## Template Inventory

### Location: `~/.traycer/prompt-templates/`

| Template File | `applicableFor` | Handlebars | Traycer Tab | When Used |
|---------------|-----------------|------------|-------------|-----------|
| `Execute.md` | `plan` | `{{planMarkdown}}` | Plan | Structured planning with full 9-step workflow |
| `Direct Execute.md` | `user query` | `{{userQuery}}` | Plan (skip-plan) | Direct task handoff without plan generation |
| `Execute Epic.md` | `plan` | `{{planMarkdown}}` | Plan | Epic mode direct agent handoff for specs/tickets |
| `Code Review.md` | `review` | `{{reviewComments}}` | Review | Fix issues from code review |
| `Fix.md` | `verification` | `{{comments}}` | Verification | Fix issues from Traycer verification |
| `Phased YOLO Execute.md` | `plan` | `{{planMarkdown}}` | Plan | Autonomous YOLO execution |
| `Phased YOLO Review.md` | `review` | `{{reviewComments}}` | Review | YOLO mode code review fixes |
| `Phased YOLO FixafterVerification.md` | `verification` | `{{comments}}` | Verification | YOLO mode verification fixes |

### Built-in Traycer Templates

| Template | Source | `applicableFor` | Notes |
|----------|--------|-----------------|-------|
| `Default` | Traycer built-in | `user query` | Generic prompt, no Fabrik conventions |

**We cannot modify built-in templates.** Use custom templates instead.

---

## Traycer Mode → Template Mapping

### 1. **Plan Mode** (Single-PR tasks)

**Templates available:**
- `Execute.md` ✅ **Use for structured planning**
- `Direct Execute.md` ✅ **Use with skip-plan checked**

**How it works:**
1. User describes task in Traycer Plan mode
2. Traycer generates plan OR skips to direct handoff
3. Agent receives task via `TRAYCER_PROMPT` env var
4. Agent executes workflow (Steps 2-5)
5. Agent outputs report with delimiters
6. Traycer handles verification/sync/commit (Steps 6-9)

---

### 2. **Phases Mode** (Multi-step projects)

**Templates available:**
- `Execute.md` ✅ **Use for each phase**
- `Phased YOLO Execute.md` ✅ **Use for YOLO automation**

**YOLO Mode Configuration (3 tabs):**
1. **Plan Tab**: Select execution agent + `Phased YOLO Execute.md`
2. **Review Tab**: Select review agent + `Phased YOLO Review.md`
3. **Verification Tab**: Select verification agent + `Phased YOLO FixafterVerification.md`

---

### 3. **Review Mode** (Code audit/verification)

**Templates available:**
- `Code Review.md` ✅ **Use for code review fixes**
- `Fix.md` ✅ **Use for verification fixes**
- `Phased YOLO Review.md` ✅ **Use for YOLO mode**

**How it works:**
1. Traycer runs verification on codebase
2. Finds issues (security, config, edge cases, docs)
3. User assigns fixes to agent with template
4. Agent fixes issues and reports
5. Traycer re-verifies
6. Loop until clean

---

### 4. **Epic Mode** (Large initiatives)

**Templates available:**
- `Execute Epic.md` ✅ **Use for direct agent handoff**
- `Execute.md` ✅ **Use for Phases/YOLO execution**

**Execution options:**
1. **Direct Agent Handoff**: Select specs/tickets → Assign agent + template → Agent implements
2. **Phases Execution**: Convert tickets to phases → Use Phases templates
3. **Smart YOLO** (`/execute`): Orchestrator manages dynamically

**How direct handoff works:**
1. User creates Epic with specs and tickets
2. User selects tickets to hand off
3. User assigns agent + `Execute Epic.md` template
4. Agent implements all assigned tickets
5. Agent outputs report with item status

---

## Template Correctness Verification

### ✅ All Templates Ready

| Template | `applicableFor` | Handlebars | Status |
|----------|-----------------|------------|--------|
| Execute | `plan` | `{{planMarkdown}}` | **READY** |
| Direct Execute | `user query` | `{{userQuery}}` | **READY** |
| Execute Epic | `plan` | `{{planMarkdown}}` | **READY** |
| Code Review | `review` | `{{reviewComments}}` | **READY** |
| Fix | `verification` | `{{comments}}` | **READY** |
| Phased YOLO Execute | `plan` | `{{planMarkdown}}` | **READY** |
| Phased YOLO Review | `review` | `{{reviewComments}}` | **READY** |
| Phased YOLO FixafterVerification | `verification` | `{{comments}}` | **READY** |

---

## Which Template Should You Use?

### For Plan Mode (with plan generation)
**Use:** `Execute.md`

### For Plan Mode (skip plan / direct task)
**Use:** `Direct Execute.md`

### For Phases Mode (Manual)
**Use:** `Execute.md` for each phase

### For Phases Mode (YOLO)
| Tab | Template |
|-----|----------|
| Plan | `Phased YOLO Execute.md` |
| Review | `Phased YOLO Review.md` |
| Verification | `Phased YOLO FixafterVerification.md` |

### For Epic Mode (Direct Handoff)
**Use:** `Execute Epic.md`

### For Review Mode
**Use:** `Code Review.md` or `Fix.md`

---

## References

- Workflow authority: `/opt/fabrik/AGENTS.md`
- CLI agent generation: `/opt/fabrik/scripts/generate_kilo_agents.py`
- Template location: `~/.traycer/prompt-templates/`
