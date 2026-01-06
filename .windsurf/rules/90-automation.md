---
activation: manual
description: droid exec integration, Fabrik skills, workflows - invoke with @90-automation
---

# Automation Rules

**Activation:** Manual (use `@90-automation` to invoke)
**Purpose:** droid exec integration, Fabrik skills, workflows

---

## Fabrik Skills (Auto-Invoked)

| Skill | Triggers On |
|-------|-------------|
| `fabrik-saas-scaffold` | "SaaS", "web app", "dashboard" |
| `fabrik-scaffold` | "new project", "create service" |
| `fabrik-docker` | "dockerfile", "compose", "deploy" |
| `fabrik-health-endpoint` | "health", "healthcheck" |
| `fabrik-config` | "config", "environment" |
| `fabrik-preflight` | "preflight", "deploy ready" |
| `fabrik-api-endpoint` | "endpoint", "route", "API" |
| `fabrik-watchdog` | "watchdog", "monitor" |
| `fabrik-postgres` | "database", "postgres" |
| `fabrik-documentation` | "docs", "readme", "update docs" |

---

## droid exec Quick Reference

```bash
# Read-only (safe default)
droid exec "Analyze this codebase"

# File edits
droid exec --auto low "Add comments"

# Development
droid exec --auto medium "Install deps, run tests"

# Full autonomy (Cascade-driven)
droid exec --auto high "Fix, test, commit, push"

# Spec mode (plan first)
droid exec --use-spec "Add authentication"

# Model selection
droid exec -m gemini-3-flash-preview "Quick task"
droid exec -m gpt-5.1-codex-max -r high "Complex task"
```

---

## Auto-Run Levels

| Level | Runs Automatically |
|-------|-------------------|
| Default | Read-only only |
| `--auto low` | + File edits |
| `--auto medium` | + Installs, commits |
| `--auto high` | All non-blocked |

**Always blocked:** `rm -rf /`, `dd of=/dev/*`, `$(...)`.

---

## Dual-Model Code Review

**Always use BOTH models:**
```bash
python3 scripts/droid_models.py recommend code_review
droid exec -m gpt-5.1-codex-max "Review [files]..."
droid exec -m gemini-3-flash-preview "Review [files]..."
```

---

## Large Features (30+ files)

```bash
# 1. Plan with spec mode
droid exec --use-spec "Create plan for [feature]"

# 2. Implement phase by phase
droid exec --auto medium "Implement Phase 1"

# 3. Commit per phase
droid exec --auto medium "Commit Phase 1"
```

---

## Model Management

```bash
python3 scripts/droid_models.py stack-rank     # Rankings
python3 scripts/droid_models.py recommend ci_cd # Best model
./scripts/setup_model_updates.sh               # Auto-update
```

---

## Batch Scripts

| Script | Purpose |
|--------|---------|
| `scripts/droid/refactor-imports.sh` | Organize imports |
| `scripts/droid/improve-errors.sh` | Better errors |
| `scripts/droid/fix-lint.sh` | Fix lint issues |

Usage: `DRY_RUN=true ./scripts/droid/script.sh src`
