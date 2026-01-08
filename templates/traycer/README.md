# Traycer Templates (Optional Integration)

**Last Updated:** 2026-01-08

Templates for using Traycer.ai with Fabrik's spec pipeline.

## What is Traycer?

Traycer is a spec-driven development orchestrator that:
- Reads your specification
- Generates phased implementation plans
- Hands tasks to AI coding agents (like Windsurf)
- Verifies task completion

## When to Use Traycer

| Scenario | Use Traycer? |
|----------|--------------|
| Small feature (< 5 files) | No - use `droid exec` directly |
| Medium feature (5-20 files) | Optional - helps with organization |
| Large feature (20+ files) | Yes - prevents context loss |
| Multi-phase project | Yes - manages phases and verification |

## Templates in This Directory

| Template | Type | Purpose |
|----------|------|---------|
| `plan_template.md` | Plan | Reads spec → generates phases/tasks |
| `task_execution_template.md` | User Query | Enforces spec during coding |
| `verification_template.md` | Verification | Checks implementation against spec |

## Setup (One-Time)

1. Open Traycer → Settings → Prompt Templates
2. Add each template from this directory
3. Configure Windsurf as an agent in Traycer

## Workflow with Fabrik

```
┌─────────────────────────────────────────────────────────────────┐
│ FABRIK (Discovery)                                              │
│                                                                 │
│ droid exec idea "..."  → specs/<project>/00-idea.md             │
│ droid exec scope "..." → specs/<project>/01-scope.md            │
│ droid exec spec "..."  → specs/<project>/02-spec.md             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ TRAYCER (Planning & Orchestration)                              │
│                                                                 │
│ 1. Open project in Traycer                                      │
│ 2. Use plan_template.md → generates phases/tasks                │
│ 3. For each task:                                               │
│    - Traycer hands to Windsurf                                  │
│    - Windsurf executes (uses task_execution_template.md)        │
│    - Traycer verifies (uses verification_template.md)           │
│    - Mark done, next task                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ FABRIK (Deployment)                                             │
│                                                                 │
│ droid exec preflight   → Pre-deployment checks                  │
│ fabrik apply           → Deploy to VPS                          │
└─────────────────────────────────────────────────────────────────┘
```

## Without Traycer

If not using Traycer, the workflow still works:

```bash
# Discovery (new stages)
droid exec idea "Your idea"
droid exec scope "project-name"
droid exec spec "project-name"

# Implementation (existing Fabrik)
droid exec plan "Implement per specs/project-name/02-spec.md"
droid exec code "Implement Phase 1"
droid exec review "Review Phase 1"
droid exec deploy "Deploy to VPS"
```

## Source

These templates were adapted from `/opt/spect-interviewer/traycer_templates/`.
