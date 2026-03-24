---
activation: always_on
description: Traycer YOLO automation and Fabrik skills (Windsurf Cascade only)
trigger: always_on
---

# Automation Rules

**Activation:** Always On
**Scope:** These rules apply to **Windsurf Cascade** agents working on any project under `/opt/`.
**Purpose:** Traycer YOLO automation, Fabrik skills

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

**Skill priority (when multiple match):**
1. Most specific to task (e.g., `fabrik-health-endpoint` over `fabrik-api-endpoint`)
2. Infrastructure skills before code skills
3. If still uncertain, present options to user first — do not auto-invoke.

### Fabrik Preflight Skill
**Trigger:** User asks "ready to deploy", "preflight", or during Step 5 (Final Gate).
**Action:** Execute enforcement suite:
```bash
python scripts/enforcement/check_docker.py
python scripts/enforcement/check_secrets.py
python scripts/enforcement/check_env_contract.py
```
**Failure in any script = STOP.** Fix all errors before proceeding.

---

## Traycer YOLO Automation

**Traycer YOLO** enables autonomous development following the 8-step workflow defined in `AGENTS.md`.

### Smart YOLO Mode
- **Use when:** Single-phase tasks with clear scope
- **How it works:** Traycer plans, codes, runs gates, DOCUMENTATOR auto-generates docs, commits
- **8-step enforcement:** Automatic (per `AGENTS.md` workflow)

### Phased YOLO Mode
- **Use when:** Multi-phase features (complex refactoring, new modules)
- **How it works:** Traycer breaks into phases, runs YOLO per phase
- **Context preservation:** Carries forward decisions across phases via Traycer's phase state
- **8-step enforcement:** Per phase (prevents drift)

**See:** `docs/traycer/traycer-yolo-workflow.md` for context preservation mechanism.

**Activation:**
```bash
# In Traycer IDE Extension
/yolo smart "Add health endpoint with DB check"
/yolo phased "Refactor auth system to use JWT"
```

**See:** `docs/traycer/traycer-yolo-workflow.md` for complete workflow

---

## Kilo CLI Code Review

**Workflow and review commands are defined in `AGENTS.md` section `[ALL AGENTS]`.**

**Quick reference for Cascade:**
```bash
git add <intended_files>
python scripts/kilo_code_review.py staged --plan "task description" --output json
```

**See `AGENTS.md`** for complete workflow, model routing, and session management.
