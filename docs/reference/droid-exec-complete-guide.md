# Droid Exec Complete Guide - Fabrik Edition

> **The definitive guide to using Factory's droid exec with Fabrik workflows.**

Last updated: 2025-01-03

---

## Quick Reference

```bash
# Cascade-driven (most common)
droid exec --auto high "Create Dockerfile for Python app"

# Interactive (you at terminal)
droid exec --auto medium "Set up postgres container"

# Specification mode (plan first)
droid exec --use-spec "Design authentication system"
```

---

## 1. Architecture Overview

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Factory CLI** | `droid` command | AI coding agent |
| **Settings** | `~/.factory/settings.json` | Global configuration |
| **Hooks** | `~/.factory/hooks/` or `.factory/hooks/` | Pre/post execution scripts |
| **Skills** | `~/.factory/skills/` | Auto-invoked capabilities |
| **MCP Servers** | `.factory/mcp.json` | External tool integrations |
| **AGENTS.md** | Project root | Project-specific agent briefing |

### Data Flow

```
User Request
    ↓
Windsurf Cascade (IDE)
    ↓
droid exec --auto high "task"
    ↓
Factory CLI reads:
  - ~/.factory/settings.json (autonomy, model, allowlist)
  - .factory/hooks.json (pre/post hooks)
  - AGENTS.md (project context)
    ↓
LLM processes task
    ↓
Commands executed (filtered by allowlist/denylist)
    ↓
Results returned
```

---

## 2. Configuration

### Settings File: `~/.factory/settings.json`

**Key settings for full automation:**

```json
{
  "model": "claude-sonnet-4-5-20250929",
  "reasoningEffort": "high",
  "autonomyLevel": "auto-high",
  "cloudSessionSync": true,
  "enableHooks": true,
  "enableSkills": true,
  "specSaveEnabled": true,
  "specModeReasoningEffort": "high",
  "commandAllowlist": ["..."],
  "commandDenylist": ["..."]
}
```

### Autonomy Levels

| Level | Behavior | Use Case |
|-------|----------|----------|
| `normal` | Asks for every command | Maximum safety |
| `auto-low` | Auto-runs read-only + file edits | Documentation work |
| `auto-medium` | + reversible changes (installs, commits) | Interactive dev |
| `auto-high` | All except denylist | **Cascade-driven automation** |

### Command Allowlist (Fabrik Defaults)

```
File ops:      cat, head, tail, grep, find, mkdir, cp, mv, touch
Git:           All git commands
Package mgmt:  pip, npm, yarn, apt
Docker:        build, run, compose, ps, logs, exec, stop, start
Dev tools:     python, node, pytest, ruff, mypy, uvicorn
Remote:        ssh vps, rsync, scp
Safe cleanup:  rm -rf .venv, node_modules, __pycache__, .tmp
```

### Command Denylist (Always Blocked)

```
System destruction:  rm -rf /, rm -rf ~, rm -rf /etc, /usr, /home
Disk operations:     mkfs, dd of=/dev
System control:      shutdown, reboot, halt, poweroff
Permission hazards:  chmod -R 777 /, chown -R
Fork bombs:          :(){ :|: & };:
```

---

## 3. Execution Modes

### Mode Overview

| Mode | Command | Model | Reasoning | Autonomy |
|------|---------|-------|-----------|----------|
| **Explore** | `analyze` | gemini-3-flash-preview | off | low |
| **Design** | `spec` | claude-sonnet-4-5-20250929 | **high** | low |
| **Build** | `code` | gpt-5.1-codex-max | medium | **high** |
| **Verify** | `test` | gpt-5.1-codex-max | low | **high** |
| **Ship** | `deploy` | gemini-3-flash-preview | off | **high** |

### Using Fabrik Task Runner

```bash
cd /opt/fabrik && source .venv/bin/activate

# Exploration
python scripts/droid_tasks.py analyze "Find auth patterns in codebase"

# Specification (planning)
python scripts/droid_tasks.py spec "Design user authentication"

# Implementation
python scripts/droid_tasks.py code "Implement login endpoint"

# Testing
python scripts/droid_tasks.py test "Run all tests and fix failures"

# Deployment
python scripts/droid_tasks.py deploy "Update compose.yaml for production"
```

---

## 4. Cascade + Droid Exec Workflow

**This is the primary workflow: Windsurf Cascade drives droid exec.**

### Why `--auto high` is Required

- Cascade cannot respond to interactive prompts
- Commands would hang waiting for confirmation
- Solution: Use `--auto high` with small, safe tasks

### The Pattern

```bash
# BAD: Big task that can fail in many ways
droid exec --auto high "Set up entire infrastructure with postgres, redis, nginx"

# GOOD: Small steps, each verifiable
droid exec --auto high "Create Dockerfile"
droid exec --auto high "Create compose.yaml"
droid exec --auto high "Run docker compose up"
```

### Terminal-Bench Reality Check

> **Even the best AI models score only ~65% on complex terminal tasks.**

This means:
- Break complex tasks into smaller steps
- Verify each step before proceeding
- Have rollback plans ready
- Don't trust multi-step commands blindly

---

## 5. Hooks System

### Hook Types

| Hook | When | Use Case |
|------|------|----------|
| `PreToolUse` | Before tool execution | Block dangerous patterns |
| `PostToolUse` | After tool execution | Validate results, scan secrets |
| `SessionStart` | Session begins | Load context |
| `Notification` | Status updates | Alerts |

### Fabrik Hooks (`.factory/hooks/`)

| Hook | Purpose |
|------|---------|
| `secret-scanner.py` | Scans for hardcoded credentials |
| `fabrik-conventions.py` | Enforces Fabrik patterns |
| `protect-files.sh` | Prevents editing protected files |
| `format-python.sh` | Auto-formats Python code |
| `log-commands.sh` | Logs all bash commands |
| `session-context.py` | Loads project context |
| `notify.sh` | Desktop notifications |

### Secret Scanner Detects

- AWS keys (`AKIA...`)
- OpenAI keys (`sk-...`)
- Anthropic keys (`sk-ant-...`)
- GitHub tokens (`ghp_...`, `gho_...`)
- Stripe keys (`sk_live_...`)
- Database URLs with passwords
- Generic hardcoded credentials

---

## 6. Skills System

Skills are auto-invoked based on task keywords.

| Skill | Triggers On | What It Does |
|-------|-------------|--------------|
| `fabrik-saas-scaffold` | "SaaS", "web app", "dashboard" | Full Next.js SaaS template |
| `fabrik-scaffold` | "new project", "create service" | Python service scaffold |
| `fabrik-docker` | "dockerfile", "compose" | Docker/Compose setup |
| `fabrik-health-endpoint` | "health", "healthcheck" | Proper health endpoints |
| `fabrik-config` | "config", "environment" | os.getenv() patterns |
| `fabrik-preflight` | "preflight", "deploy ready" | Pre-deploy validation |
| `fabrik-api-endpoint` | "endpoint", "route", "API" | FastAPI patterns |
| `fabrik-watchdog` | "watchdog", "monitor" | Service monitoring |
| `fabrik-postgres` | "database", "postgres" | PostgreSQL + pgvector |

---

## 7. Model Selection

### Stack Rankings (from Factory docs)

| Rank | Model | Best For |
|------|-------|----------|
| 1 | claude-opus-4-5-20251101 | Highest quality, current default |
| 2 | gpt-5.1-codex-max | Heavy implementation, debugging |
| 3 | claude-sonnet-4-5-20250929 | Daily driver, balanced |
| 4 | gpt-5.1-codex | Quick iteration |
| 5 | gpt-5.1 | General purpose |
| 6 | claude-haiku-4-5-20251001 | Fast, cost-efficient |
| 7 | gemini-3-pro-preview | Research flows |
| 8 | gemini-3-flash-preview | High-volume, cheap |
| 9 | glm-4.6 | Open-source, bulk automation |

### Model Management

```bash
cd /opt/fabrik && source .venv/bin/activate

# View current rankings
python scripts/droid_models.py stack-rank

# Get recommendation for scenario
python scripts/droid_models.py recommend ci_cd

# Force update from Factory docs
python scripts/droid_model_updater.py

# Enable daily auto-updates
./scripts/setup_model_updates.sh
```

---

## 8. Implementing Large Features

For projects touching 30+ files:

### Phased Workflow

```bash
# 1. Create master plan with spec mode
droid exec --use-spec "Create implementation plan for [feature].
Break into phases completable in 1-2 days with testing points."
# Save output as IMPLEMENTATION_PLAN.md

# 2. Implement phase by phase (fresh session per phase)
droid exec --auto high "Implement Phase 1 per IMPLEMENTATION_PLAN.md.
Update doc to mark complete when done."

# 3. Commit per phase
droid exec --auto high "Commit Phase 1 with detailed message."

# 4. Test before moving on
droid exec --auto high "Run tests for Phase 1. Verify functionality."
```

### Best Practices

- **Fresh session per phase** — Prevents context pollution
- **Test after each phase** — Catch issues early
- **Plan rollback** — Know how to undo each phase
- **Maintain backward compatibility** — Use feature flags if needed

---

## 9. Output Formats

| Format | Flag | Use Case |
|--------|------|----------|
| Text | (default) | Human reading |
| JSON | `-o json` | Script parsing |
| Stream JSON | `-o stream-json` | Real-time JSONL events |
| Debug | `--debug` | Web UI, troubleshooting |

```bash
# Structured output for scripts
droid exec -o json "Analyze code" | jq '.result'

# Real-time streaming
droid exec -o stream-json "Complex task"
```

---

## 10. Session Management

```bash
# Start a session
droid exec "Start working on feature X"
# Returns session ID: abc123

# Continue session
droid exec -s abc123 "Now add tests"

# Sessions sync to cloud if cloudSessionSync: true
```

---

## 11. Cost Optimization

| Strategy | Implementation |
|----------|----------------|
| Use cheaper models for simple tasks | `gemini-3-flash-preview` (0.2x cost) |
| Batch similar operations | One prompt, multiple files |
| Cache expensive analyses | Store in project docs |
| Use spec mode for planning | Avoids expensive re-runs |

---

## 12. Troubleshooting

### Command hangs

**Cause:** Waiting for confirmation in non-interactive mode
**Fix:** Use `--auto high` or add command to allowlist

### "Command blocked"

**Cause:** Command matches denylist pattern
**Fix:** Verify command is safe, update denylist if needed

### Poor results on complex tasks

**Cause:** Models score ~65% on terminal tasks
**Fix:** Break into smaller steps

### Hooks not running

**Cause:** `enableHooks: false` in settings
**Fix:** Set `"enableHooks": true`

---

## 13. File Locations Summary

### Global (User)

| File | Purpose |
|------|---------|
| `~/.factory/settings.json` | CLI configuration |
| `~/.factory/hooks/` | User-level hooks |
| `~/.factory/skills/` | User-level skills |
| `~/.factory/commands/` | Custom slash commands |

### Project-Level

| File | Purpose |
|------|---------|
| `.factory/hooks.json` | Project hook configuration |
| `.factory/mcp.json` | MCP server configuration |
| `.factory/settings.json` | Project settings override |
| `AGENTS.md` | Agent briefing (auto-loaded) |

### Fabrik-Specific

| File | Purpose |
|------|---------|
| `/opt/fabrik/config/models.yaml` | Model rankings & scenarios |
| `/opt/fabrik/scripts/droid_tasks.py` | Task runner |
| `/opt/fabrik/scripts/droid_models.py` | Model registry |
| `/opt/fabrik/scripts/droid_model_updater.py` | Auto-update from Factory docs |
| `/opt/fabrik/.factory/hooks/` | Fabrik hooks |

### User Skills (`~/.factory/skills/`)

| Skill | Purpose |
|-------|---------|
| `fabrik-scaffold/SKILL.md` | Full project structure with all conventions |
| `fabrik-docker/SKILL.md` | Docker/Compose for ARM64 Coolify VPS |
| `fabrik-health-endpoint/SKILL.md` | Health endpoints that test dependencies |
| `fabrik-config/SKILL.md` | os.getenv() patterns, .env.example |
| `fabrik-preflight/SKILL.md` | Pre-deployment validation checklist |
| `fabrik-api-endpoint/SKILL.md` | FastAPI patterns with Pydantic |
| `fabrik-watchdog/SKILL.md` | Service monitoring scripts |
| `fabrik-postgres/SKILL.md` | PostgreSQL + pgvector setup |
| `documentation-generator/SKILL.md` | Auto-generate project documentation |

---

## 14. Quick Command Reference

```bash
# Basic execution
droid exec "prompt"

# With autonomy
droid exec --auto high "prompt"

# With model selection
droid exec -m claude-sonnet-4-5-20250929 "prompt"

# With reasoning
droid exec -r high "complex prompt"

# Specification mode
droid exec --use-spec "plan something"

# Continue session
droid exec -s SESSION_ID "continue"

# From file
droid exec -f prompt.md

# JSON output
droid exec -o json "prompt"

# Working directory
droid exec --cwd /path/to/project "prompt"
```

---

*See also:*
- `/opt/fabrik/docs/reference/droid-exec-usage.md` — Original detailed docs
- `/opt/fabrik/docs/reference/factory-enterprise.md` — Enterprise features
- `/opt/fabrik/docs/reference/factory-hooks.md` — Hook system details
- `/opt/fabrik/docs/reference/factory-skills.md` — Skills system details
