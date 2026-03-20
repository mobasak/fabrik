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

**If multiple skills match, invoke the most specific one. If uncertain, invoke and report.**

---

## Traycer YOLO Automation

**Traycer YOLO** enables autonomous development following the simplified 6-step workflow:

### Smart YOLO Mode
- **Use when:** Single-phase tasks with clear scope
- **How it works:** Traycer plans, codes, runs gates, optional review, commits
- **6-step enforcement:** Automatic (Final Gate → Cheap Review → Verify → Commit)

### Phased YOLO Mode
- **Use when:** Multi-phase features (complex refactoring, new modules)
- **How it works:** Traycer breaks into phases, runs YOLO per phase
- **Context preservation:** Carries forward decisions across phases
- **6-step enforcement:** Per phase (prevents drift)

**Activation:**
```bash
# In Traycer IDE Extension
/yolo smart "Add health endpoint with DB check"
/yolo phased "Refactor auth system to use JWT"
```

**See:** `docs/traycer/traycer-yolo-workflow.md` for complete workflow

---

## Kilo CLI Code Review (March 2026)

**Single command, automatic model selection, report-only by default:**

```bash
# Stage files and run review (all routing is automatic)
git add <intended_files>
python /opt/fabrik/scripts/kilo_code_review.py staged --plan "task description" --output json
```

**Automatic Features:**
- **Risk Detection**: Scans file paths + diff size → determines risk level
- **Model Selection**: Risk level → cheapest capable model
- **Variant Selection**: Risk level → appropriate thinking depth
- **Session Isolation**: Auto-generates `tracked_review_id` from project+branch+date

**Review Commands:**
- **staged**: Review git staged files (most common)
- **changed**: Review all changed files
- **review <files>**: Review specific files
- **verify <files> --fixes "..."**: Verify manual fixes (cheaper)

**Flags:**
- `--plan "..."`: Task description for SPEC compliance checking
- `--output json`: Machine-readable output
- `--fix`: Enable Kilo auto-fix (default: report-only)
- `--model <id>`: Override auto-selected model
- `--variant <level>`: Override auto-selected variant (low/high/max)

**See:** `.windsurf/rules/50-code-review.md` for complete workflow

---

## Tiered Model Routing (Built into kilo_code_review.py)

**Model selection is automatic based on risk level:**

| Risk Level | Trigger | Strategy | Starting Tier | Models |
|------------|---------|----------|---------------|--------|
| **low** | Docs only | free | Free | minimax, glm-4.7-free |
| **medium** | Normal code | economy | Economy | gemini-flash-lite |
| **high** | src/, scripts/, >400 lines | standard | Balanced | glm-4.7, gpt-5.2-codex |
| **critical** | auth/, security/, secrets | premium | Strong | glm-5, claude-sonnet-4.6 |

**Variant Selection (Thinking Depth):**

| Risk Level | Variant | Time | Cost |
|------------|---------|------|------|
| low | `low` | ~10s | Cheapest |
| medium | `high` | ~20s | Best value |
| high | `high` | ~20s | Best value |
| critical | `max` | ~40s | Deepest |

**Escalation on Failure:**
- Model timeout/error → try next model in tier
- Tier exhausted → escalate to next tier
- Max 1 fallback escalation per review
