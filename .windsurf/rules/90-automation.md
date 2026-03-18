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

**See:** `.windsurf/rules/50-code-review.md` for complete 9-step workflow
