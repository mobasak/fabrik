---
activation: always_on
description: Traycer YOLO automation, Fabrik skills
trigger: always_on
---

# Automation Rules

**Activation:** Always On
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

## Kilo CLI Code Review (Fallback)

**When NOT using Traycer:** Use Kilo CLI directly for code review.

**Staged-first workflow with scoped sessions (2026-03-17):**

```bash
# Set stable review ID once per cycle
export REVIEW_ID="feat-$(date +%Y%m%d)-<feature-slug>"

# Stage intended files before initial review
git add <intended_files>

# Initial pass: staged commit candidate
python /opt/fabrik/scripts/kilo_code_review.py staged \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --plan "Brief task description" \
  --review-agent ask \
  --output json

# Intermediate passes: verify command (lighter)
python /opt/fabrik/scripts/kilo_code_review.py verify <changed_files> \
  --session continue \
  --tracked-review-id "$REVIEW_ID" \
  --fixes "What was fixed" \
  --review-agent ask \
  --output json
```

**Session Scoping:**
- Sessions scoped by: `project_root + git_branch + tracked_review_id`
- `--tracked-review-id` REQUIRED with `--session continue`
- Prevents cross-repo/branch session pollution
- Issue state persisted to `.droid/reviews/<tracked_review_id>_issues.json`
- Open issues reused across iterations

**Review Mode Selection:**
- **staged**: Initial pass, final risky-branch check
- **verify** (command): Intermediate fix loops (cheaper, focused - use after manual fixes)
- **review <files>**: Manual WIP review only
- **--mode full**: Full file review (default for review command)

**Recommendation:** Stage intended files semantically before calling reviewer.

**See:** `.windsurf/rules/50-code-review.md` for complete 6-step workflow

---

## Context-Aware Reviewer Selection (March 2026)

**Auto-select cheapest capable reviewer based on task complexity:**

```bash
# Auto-detect tier and select reviewer
python /opt/fabrik/scripts/reviewer_selector.py auto

# Get model name for piping
MODEL=$(python /opt/fabrik/scripts/reviewer_selector.py model)

# List all tiers and costs
python /opt/fabrik/scripts/reviewer_selector.py list
```

**Reviewer Tiers (based on Terminal-Bench 2.0, Chatbot Arena, SWE-Bench):**

| Tier | Cost/Review | Models | Use Case |
|------|-------------|--------|----------|
| **quick** | $0.02 | gemini-3.1-flash-lite, step-3.5-flash | Lint, format, simple fixes |
| **standard** | $0.05 | deepseek-v3.2, glm-4.7, minimax-m2.5 | Regular PRs, features |
| **complex** | $0.12 | glm-5, qwen3-max, kimi-k2.5 | Refactoring, logic changes |
| **security** | $0.30 | claude-sonnet-4.6, gemini-3.1-pro | Security-critical, API |
| **architecture** | $0.50 | claude-opus-4.6, gpt-5.4 | Design review, architecture |

**Selection Logic:**
- Security patterns (auth, token, key) → security tier
- Large diffs (>300 lines) or model/API changes → complex tier
- Medium diffs (>50 lines) → standard tier
- Small changes → quick tier
