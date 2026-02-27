---
activation: always_on
description: Traycer YOLO automation, Fabrik skills
trigger: always_on
---

# Automation Rules

**Activation:** Manual (use `@90-automation` to invoke)
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

---

## Traycer YOLO Automation

**Traycer YOLO** enables autonomous development following the 9-step workflow:

### Smart YOLO Mode
- **Use when:** Single-phase tasks with clear scope
- **How it works:** Traycer plans, codes, runs gates, reviews, commits
- **9-step enforcement:** Automatic (Final Gate → Kilo → Final Gate → Verify → Sync → Commit)

### Phased YOLO Mode
- **Use when:** Multi-phase features (complex refactoring, new modules)
- **How it works:** Traycer breaks into phases, runs YOLO per phase
- **Context preservation:** Carries forward decisions across phases
- **9-step enforcement:** Per phase (prevents drift)

**Activation:**
```bash
# In Traycer IDE Extension
/yolo smart "Add health endpoint with DB check"
/yolo phased "Refactor auth system to use JWT"
```

**See:** `docs/traycer/traycer-yolo-workflow.md` for complete workflow

---

## Kilo CLI Code Review (Fallback)

**When NOT using Traycer:** Use Kilo CLI directly for code review.

```bash
# Review changed files
python /opt/fabrik/scripts/kilo_code_review.py review <files> --output json

# Continue session (maintains context)
python /opt/fabrik/scripts/kilo_code_review.py review <files> --session continue
```

**See:** `.windsurf/rules/50-code-review.md` for complete 9-step workflow
