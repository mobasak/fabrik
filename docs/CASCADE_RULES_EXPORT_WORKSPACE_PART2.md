# Cascade Rules Export - WORKSPACE RULES (Part 2 of 4)

**Exported:** 2026-01-13
**Type:** WORKSPACE RULES (apply to /opt/fabrik workspace only)
**Location:** `.windsurf/rules/`

---

# FILE: .windsurf/rules/30-ops.md

```markdown
---
activation: glob
globs: ["**/Dockerfile", "**/compose.yaml", "**/compose.yml", "**/docker-compose.yaml", "**/docker-compose.yml"]
description: Docker standards, deployment, infrastructure
trigger: always_on
---

# Operations & Deployment Rules

**Activation:** Glob `**/Dockerfile`, `**/compose.yaml`, `**/compose.yml`
**Purpose:** Docker standards, deployment, infrastructure

---

## Container Base Images (CRITICAL)

**Use Debian/Ubuntu, NOT Alpine:**

| Use Case | Base Image |
|----------|------------|
| Python apps | `python:3.12-slim-bookworm` |
| Node.js apps | `node:22-bookworm-slim` |
| General | `debian:bookworm-slim` |

**Why not Alpine:** glibc compatibility, ARM64 support, pre-built wheels.

---

## Dockerfile Template

```dockerfile
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .

# HEALTHCHECK is REQUIRED
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

ENV PORT=8000
EXPOSE ${PORT}
CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT}"]
```

---

## compose.yaml Template

```yaml
services:
  api:
    build: .
    ports:
      - "${PORT:-8000}:${PORT:-8000}"
    environment:
      - DB_HOST=postgres-main
      - DB_PORT=5432
      - DB_NAME=${DB_NAME}
      - DB_USER=${DB_USER}
      - DB_PASSWORD=${DB_PASSWORD}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${PORT:-8000}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    networks:
      - coolify

networks:
  coolify:
    external: true
```

---

## Deployment Checklist

Before deploying to Coolify:

- [ ] Dockerfile uses bookworm-slim (not Alpine)
- [ ] HEALTHCHECK instruction present
- [ ] Health endpoint tests actual dependencies
- [ ] All env vars documented in .env.example
- [ ] Credentials in project .env AND /opt/fabrik/.env
- [ ] Port registered in PORTS.md
- [ ] compose.yaml uses coolify network
- [ ] Service added to /opt/fabrik/docs/SERVICES.md
- [ ] Watchdog script created

---

## Watchdog Requirement

Every service MUST have a watchdog script:

```bash
#!/bin/bash
# scripts/watchdog.sh
SERVICE_NAME="myservice"
HEALTH_URL="http://localhost:8000/health"
MAX_FAILURES=3

failures=0
while true; do
    if ! curl -sf "$HEALTH_URL" > /dev/null; then
        ((failures++))
        if [ $failures -ge $MAX_FAILURES ]; then
            systemctl restart "$SERVICE_NAME"
            failures=0
        fi
    else
        failures=0
    fi
    sleep 30
done
```

---

## Microservice URLs

| Environment | Pattern |
|-------------|---------|
| WSL | `http://localhost:PORT` |
| VPS Internal | `http://service-name:PORT` |
| VPS External | `https://service.vps1.ocoron.com` |

---

## ARM64 Requirement

VPS1 uses ARM64 (aarch64). Verify image support:
```bash
python scripts/container_images.py check-arch <image:tag>
```
```

---

# FILE: .windsurf/rules/40-documentation.md

```markdown
---
trigger: always_on
---
# Documentation Rules

activation: glob
globs: ["*.md", "docs/**/*", "specs/**/*"]

---

## CHANGELOG.md (MANDATORY)

**Every code change MUST update CHANGELOG.md:**

```markdown
## [Unreleased]

### Added/Changed/Fixed - <Brief Title> (YYYY-MM-DD)

**What:** One-line description

**Files:**
- `path/to/file.py` - what changed
```

**No exceptions.** This is enforced by `docs_updater.py`.

---

## Plan Document Types

### 1. Exploration Plans (Phase A)
Use `templates/docs/PLAN_TEMPLATE.md` for **research and design** phase:
- The Problem
- The Solution
- What We're Building
- How It Works
- What This Fixes
- Timeline

### 2. Execution Plans (Phase B)
Use `templates/docs/EXECUTION_PLAN_TEMPLATE.md` for **locked implementation**:
- Task Metadata (goal, done-when, out-of-scope)
- Constraints
- Canonical Gate
- 5-7 Execution Steps (DO → GATE → EVIDENCE)
- Stop Conditions

## When to Use Which

| Situation | Template |
|-----------|----------|
| New feature exploration | PLAN_TEMPLATE.md |
| Locked implementation | EXECUTION_PLAN_TEMPLATE.md |
| Bug fix | EXECUTION_PLAN_TEMPLATE.md |
| Refactoring | EXECUTION_PLAN_TEMPLATE.md |

## Execution Plan Rules (STRICT)

```text
- Follow steps exactly in order
- Do NOT redesign or change scope
- One step at a time
- After each step: show Evidence + Gate result
- If a Gate fails → STOP and report
```

## Writing Style

- **Plain language** — No jargon
- **Show don't tell** — Use examples
- **Before/After tables** — Make improvements obvious
- **5-7 steps max** — Human-manageable
```

---

# FILE: .windsurf/rules/50-code-review.md

```markdown
---
activation: always_on
description: Mandatory execution protocol with code review enforcement
trigger: always_on
---

# Execution Protocol (MANDATORY)

## The Flow: PLAN → APPROVE → IMPLEMENT → REVIEW → FIX → VALIDATE → NEXT

**This applies to ALL tasks in /opt/* projects.**

| Phase | Action | Gate |
|-------|--------|------|
| **1. PLAN** | Create/show execution plan | Plan exists |
| **2. APPROVE** | Wait for explicit "go" from human | Human says "go" |
| **3. IMPLEMENT** | Execute ONE step | Code written |
| **4. REVIEW** | Run code review (see below) | Review output shown |
| **5. FIX** | Address ALL issues found | Zero errors |
| **6. VALIDATE** | Run gate command | Gate passes |
| **7. NEXT** | Only proceed after gate passes | Ready for next step |

---

## Code Review (After EVERY Code Change)

**Immediately after writing/editing code, I MUST:**

```bash
# 1. Check no droid instances running (prevents resource contention)
pgrep -f "droid exec" || echo "Ready"

# 2. Get recommended model for code review
python3 scripts/droid_models.py recommend code_review 2>/dev/null || echo "gemini-3-flash-preview"

# 3. Run review (read-only, NO changes)
droid exec -m <model_from_step_2> "Review these files for Fabrik conventions and bugs. DO NOT make changes, only report issues as JSON: {issues: [{file, line, severity, message}], summary: string}

Files: <changed_files>"
```

**Then I MUST:**
1. Show the review output to user
2. Fix ALL errors (severity: error)
3. Fix warnings if reasonable
4. Re-run review until: `"issues": []` or only minor warnings remain

**Output format after each step:**
```
STEP <N> STATUS: PASS / FAIL
Changed files:
- <path>
Review output:
<issues or "No issues">
Gate output:
<command result>
Next: Proceed to Step <N+1> / STOP (issues remain)
```

---

## Plan Template (For Every Non-Trivial Task)

Every plan MUST include review checkpoints:

```markdown
## Step N: <description>

**DO:** <what to implement>

**REVIEW:**
- Run: `droid exec -m <model> "Review <files>..."`
- Fix all issues
- Re-review until clean

**GATE:** <validation command>

**EVIDENCE:** <expected output>
```

---

## Violations

**I am FORBIDDEN from:**
- Skipping REVIEW phase
- Proceeding to next step with unfixed errors
- Marking task complete without final review
- Assuming approval — must wait for explicit "go"

**If user catches me skipping review:**
- I must acknowledge the violation
- Run the skipped review immediately
- Fix issues before continuing

---

## Scope

This protocol applies to:
- All projects under `/opt/`
- All Cascade agents working in this workspace
- All file modifications (edit, multi_edit, write_to_file, Create)

Symlinked via `.windsurfrules` to all project roots.
```
