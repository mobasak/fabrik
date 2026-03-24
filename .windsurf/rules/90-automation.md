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

## Fabrik Behavior Patterns

When triggered, apply the corresponding rules from `.windsurf/rules/` and enforcement scripts:

| Trigger Keywords | Rules File | Enforcement | Action |
|-----------------|-----------|-------------|--------|
| "new project", "create service" | — | — | Run `fabrik scaffold <name> --type <type>` |
| "SaaS", "web app", "dashboard" | `20-typescript.md` | — | Run `fabrik scaffold <name> --type saas-skeleton` |
| "dockerfile", "compose", "deploy" | `30-ops.md` | `check_docker.py` | Follow ARM64 + bookworm-slim + HEALTHCHECK patterns |
| "health", "healthcheck" | `00-critical.md`, `10-python.md` | `check_health.py` | Health endpoints MUST test actual dependencies |
| "config", "environment" | `00-critical.md`, `10-python.md` | `check_env_contract.py` | No hardcoded values, function-level loading |
| "endpoint", "route", "API" | `10-python.md` | `validate_conventions.py` | Type hints, Pydantic models, proper HTTP status codes |
| "database", "postgres" | `00-critical.md` | `check_schema_sync.py` | Schema changes → `db/schema.sql` or migration |
| "watchdog", "monitor" | `30-ops.md` | `check_watchdog.py` | Services MUST have `scripts/watchdog*.sh` |
| "docs", "readme", "update docs" | `40-documentation.md` | `check_changelog.py`, `check_docs.py` | Run `kilo_docs_enforcer.py --auto-generate` |
| "preflight", "deploy ready" | — | All 27 scripts | Run `python scripts/final_gate.py` |

**Priority (when multiple match):**
1. Most specific to task
2. Infrastructure patterns before code patterns
3. If uncertain, present options to user first — do not auto-invoke.

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
