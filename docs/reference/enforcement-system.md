# Fabrik Enforcement System

**Last Updated:** 2026-01-06 (16:55 UTC+3)

---

## Overview

The enforcement system validates code against Fabrik conventions at multiple points:
- **Windsurf hooks** (`.windsurf/hooks.json`) — runs before/after Cascade edits
- **Pre-commit** (git hooks) — blocks bad commits
- **Post-edit** (droid hooks) — runs after droid exec edits
- **Manual** — run anytime via CLI

### Windsurf Cascade Hooks

Located in `.windsurf/hooks.json`:

```json
{
  "hooks": [
    {"event": "pre_write_code", "command": "python3 -m scripts.enforcement.validate_conventions --strict ${WINDSURF_FILES:-}", "cwd": "/opt/fabrik"},
    {"event": "post_write_code", "command": "python3 /opt/fabrik/.factory/hooks/secret-scanner.py"}
  ]
}
```

### Modular Rules (`.windsurf/rules/`)

| File | Activation | Description |
|------|------------|-------------|
| `00-critical.md` | `always_on` | Security, env vars, mandatory workflow |
| `10-python.md` | `glob: **/*.py` | FastAPI patterns |
| `20-typescript.md` | `glob: **/*.ts, **/*.tsx` | Next.js patterns |
| `30-ops.md` | `glob: **/Dockerfile, **/compose.yaml` | Docker standards |
| `90-automation.md` | `manual` | droid exec reference |

All rule files use YAML frontmatter for structured activation metadata.

### Legacy windsurfrules

The monolithic `windsurfrules` file (50KB) is deprecated but maintained for backward compatibility with existing project symlinks. New projects should use `.windsurf/rules/` instead.

---

## Components

### 1. Check Scripts (`scripts/enforcement/`)

| Script | Purpose | Severity |
|--------|---------|----------|
| `validate_conventions.py` | Orchestrator - runs all checks | - |
| `check_env_vars.py` | Detects hardcoded `localhost`, `127.0.0.1` | ERROR |
| `check_secrets.py` | Detects hardcoded credentials (14 patterns) | ERROR |
| `check_health.py` | Verifies health endpoints test dependencies | WARN |
| `check_docker.py` | Validates base images, HEALTHCHECK presence | WARN |
| `check_ports.py` | Checks port registration and range | WARN |
| `check_watchdog.py` | Verifies services have watchdog scripts | WARN |
| `check_rule_size.py` | Ensures rule files stay under 12KB | ERROR |

### 2. Secret Patterns Detected

```
- AWS Access Key ID (AKIA...)
- AWS Secret Access Key
- Google API Key (AIza...)
- OpenAI API Key (sk-...)
- Anthropic API Key (sk-ant-...)
- GitHub PAT (ghp_...)
- GitHub OAuth Token (gho_...)
- Stripe Live/Restricted Keys
- PostgreSQL/MongoDB URLs with passwords
- Private Keys (RSA, DSA, EC, OPENSSH)
- Bearer Tokens
- Generic password/secret/api_key/token assignments
```

### 3. Port Ranges

| Technology | Range | Enforced By |
|------------|-------|-------------|
| Python services | 8000-8099 | `check_ports.py` |
| Frontend apps | 3000-3099 | `check_ports.py` |

---

## Usage

### Manual Check

```bash
# Check specific files
python3 -m scripts.enforcement.validate_conventions src/config.py Dockerfile

# JSON output
python3 -m scripts.enforcement.validate_conventions --json src/*.py

# Strict mode (warnings become errors)
python3 -m scripts.enforcement.validate_conventions --strict src/
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Pass |
| 1 | Warnings only |
| 2 | Errors (blocks commit) |

---

## Pre-commit Integration

Added to `.pre-commit-config.yaml`:

```yaml
- id: fabrik-conventions
  name: Fabrik Convention Validator
  entry: python3 -c "from scripts.enforcement.validate_conventions import main; ..."
  types_or: [python, yaml, dockerfile, ts, tsx, javascript]

- id: rule-file-size
  name: Rule File Size Guard
  entry: python3 scripts/enforcement/check_rule_size.py
```

---

## Windsurf Rules (`.windsurf/rules/`)

| File | Size | Activation | Content |
|------|------|------------|---------|
| `00-critical.md` | 2.2KB | Always On | Security, env vars, ports |
| `10-python.md` | 2.3KB | `**/*.py` | FastAPI patterns |
| `20-typescript.md` | 2.0KB | `**/*.ts` | Next.js patterns |
| `30-ops.md` | 3.1KB | Dockerfile, compose | Docker standards |
| `90-automation.md` | 2.6KB | Manual | droid exec reference |

**Size limit:** Each file must be <12KB (enforced by `check_rule_size.py`)

---

## Tests

Location: `tests/test_enforcement.py`

```bash
pytest tests/test_enforcement.py -v
```

**Coverage:** 13 tests covering env vars, secrets, Docker, orchestrator.

---

---

## Code Review Feedback Loop

For **droid exec only** (not Cascade), automatic code review is available:

### Components

| Script | Purpose |
|--------|---------|
| `~/.factory/hooks/fabrik-code-review.py` | PostToolUse hook - queues reviews |
| `scripts/review_worker.py` | Processes queue, calls reviewer model |
| `scripts/acknowledge_reviews.py` | CLI to manage pending reviews |
| `~/.factory/hooks/fabrik-session-reviews.py` | SessionStart hook - shows pending |

### Flow

```
droid exec edit → queue review → worker processes → next session sees issues
```

### Usage

```bash
# Start review worker (background)
python3 scripts/review_worker.py --watch &

# List pending reviews
python3 scripts/acknowledge_reviews.py --list

# Acknowledge all
python3 scripts/acknowledge_reviews.py --all
```

### Limitation

**This only works for droid exec.** Cascade (Windsurf) does not trigger `.factory/hooks.json`.

---

## See Also

- [AGENTS.md](/opt/fabrik/AGENTS.md) — Cross-agent briefing
- [droid-exec-usage.md](droid-exec-usage.md) — droid exec reference
- [hooks-and-skills-guide.md](hooks-and-skills-guide.md) — Hook configuration
