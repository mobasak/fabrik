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

| Trigger Keywords                  | Rules File          | Enforcement           | Action                                                |
|----------------------------------|---------------------|-----------------------|-------------------------------------------------------|
| "new project", "create service" | —                   | —                     | Run `fabrik scaffold <name> --type <type>`           |
| "SaaS", "web app", "dashboard"  | `20-typescript.md`  | —                     | Run `fabrik scaffold <name> --type saas-skeleton`    |
| "dockerfile", "compose", "deploy" | `30-ops.md`       | `check_docker.py`     | Follow amd64 + bookworm-slim + HEALTHCHECK patterns  |
| "health", "healthcheck"        | `.windsurfrules`, `10-python.md` | `check_health.py` | Health endpoints MUST test actual dependencies       |
| "config", "environment"        | `.windsurfrules`, `10-python.md` | `check_env_contract.py` | No hardcoded values, function-level loading   |
| "endpoint", "route", "API"     | `15-api-contracts.md` + language pack | `validate_conventions.py` | API contracts + `10-python.md` or `20-typescript.md` per project type |
| "database", "postgres"         | `.windsurfrules`    | `check_schema_sync.py` | Schema changes → `db/schema.sql` or migration        |
| "watchdog", "monitor"          | `30-ops.md`         | `check_watchdog.py`   | Services MUST have `scripts/watchdog*.sh`            |
| "docs", "readme", "update docs" | `40-documentation.md` | `check_changelog.py`, `check_docs.py` | Run `kilo_docs_enforcer.py --auto-generate` |
| "preflight", "deploy ready"    | —                   | Tiered gate           | Run `python scripts/final_gate.py` (Tier 2) or `--systemic` (Tier 3) |

**Priority (when multiple match):**
1. Most specific to task
2. Infrastructure patterns before code patterns
3. If uncertain, present options to user first — do not auto-invoke.

---

## Traycer YOLO Automation

**Traycer YOLO** enables autonomous development. Traycer orchestrates the workflow; Cascade/Kilo agents execute.

### Smart YOLO Mode

- **Use when:** Single-phase tasks with clear scope
- **How it works:** Traycer plans, delegates to agents, runs gates, commits
- **Quality gates:** Agents run lean gate (`--lean`) during coding. Traycer runs full gate at phase end.

### Phased YOLO Mode

- **Use when:** Multi-phase features (complex refactoring, new modules)
- **How it works:** Traycer breaks into phases, runs YOLO per phase
- **Context preservation:** Carries forward decisions across phases via Traycer's phase state
- **Quality gates:** Per phase — lean gate during coding, full gate at each phase boundary

**See:** `docs/traycer/traycer-yolo-workflow.md` for context preservation mechanism.

**Activation:**
```bash
# In Traycer IDE Extension
/yolo smart "Add health endpoint with DB check"
/yolo phased "Refactor auth system to use JWT"
```

---

## Kilo CLI Code Review

Quick reference for Cascade:

```bash
git add -A
python scripts/kilo_code_review.py staged --plan "task description" --output json
```

For full gate commands and tier details, see `.windsurf/rules/50-code-review.md`.

