# Fabrik Enforcement System

**Last Updated:** 2026-01-07

---

## Overview

The enforcement system validates code against Fabrik conventions at multiple points:
- **Windsurf hooks** (`.windsurf/hooks.json`) — runs before/after Cascade edits
- **Pre-commit** (git hooks) — blocks bad commits
- **Post-edit** (Kilo hooks) — runs after Kilo CLI edits
- **Manual** — run anytime via CLI

### Windsurf Cascade Hooks

Located in `.windsurf/hooks.json`:

```json
{
  "hooks": [
    {"event": "post_write_code", "command": "python3 -m scripts.enforcement.validate_conventions --strict --git-diff", "cwd": "/opt/fabrik"},
    {"event": "post_write_code", "command": "python3 /opt/fabrik/.factory/hooks/secret-scanner.py"}
  ]
}
```

**Note:** Validation runs at `post_write_code` (not `pre_write_code`) because files must exist on disk for git-based detection to work. The `--git-diff` flag checks:
- Staged changes (`git diff --staged`)
- Unstaged changes (`git diff`)
- **Untracked files** (`git ls-files --others --exclude-standard`)

### Modular Rules (`.windsurf/rules/`)

| File | Activation | Description |
|------|------------|-------------|
| `00-critical.md` | `always_on` | Security, env vars, mandatory workflow |
| `10-python.md` | `glob: **/*.py` | FastAPI patterns |
| `20-typescript.md` | `glob: **/*.ts, **/*.tsx` | Next.js patterns |
| `30-ops.md` | `glob: **/Dockerfile, **/compose.yaml` | Docker standards |
| `90-automation.md` | `manual` | Kilo CLI automation |

All rule files use YAML frontmatter for structured activation metadata.

### Legacy windsurfrules

The monolithic `.windsurfrules` file is deprecated. New projects should use `.windsurf/rules/` instead.

---

## Components

### 1. Check Scripts (`scripts/enforcement/`)

| Script | Purpose | Severity |
|--------|---------|----------|
| `validate_conventions.py` | Orchestrator - runs all checks | - |
| `check_env_vars.py` | Detects hardcoded `localhost`, `127.0.0.1` | ERROR |
| `check_secrets.py` | Detects hardcoded credentials (14 patterns) | ERROR |
| `check_health.py` | Verifies health endpoints test dependencies | ERROR |
| `check_docker.py` | Validates base images, HEALTHCHECK presence | WARN |
| `check_ports.py` | Checks port registration and range | WARN |
| `check_watchdog.py` | Verifies services have watchdog scripts | WARN |
| `check_rule_size.py` | Ensures rule files stay under 12KB | ERROR |
| `check_structure.py` | Enforces .md file locations | ERROR |
| `check_changelog.py` | Requires CHANGELOG.md updates | ERROR |
| `check_plans.py` | Validates plan file naming | WARN |
| `check_docs.py` | Warns on undocumented modules | WARN |

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

### Standard Hooks

| Hook | Purpose | Auto-fix? |
|------|---------|----------|
| `ruff` | Python linting and formatting | Yes (`--fix` flag) |
| `mypy` | Static type checking (src/fabrik/ only) | No |
| `trailing-whitespace` | Remove trailing spaces | Yes |
| `end-of-file-fixer` | Ensure files end with newline | Yes |
| `check-yaml` | Validate YAML syntax | No |
| `check-json` | Validate JSON syntax | No |
| `check-added-large-files` | Block files > 1MB | No |
| `check-merge-conflict` | Detect merge conflict markers | No |
| `detect-private-key` | Detect exposed private keys | No |

### Security Hooks

| Hook | Purpose | Auto-fix? |
|------|---------|----------|
| `bandit` | Python security linter (Medium+ severity) | No |
| `sqlfluff` | SQL injection detection (Postgres) | No |
| `semgrep` | Advanced security patterns (injection, SSRF, path traversal) | No |

### Code Quality

| Hook | Purpose | Auto-fix? |
|------|---------|----------|
| `vulture` | Dead code detection (95% confidence) | No |

### Fabrik-Specific Hooks

| Hook | Purpose | Auto-fix? |
|------|---------|----------|
| `fabrik-conventions` | Check for hardcoded localhost, secrets, health endpoints, Docker issues | No |
| `rule-file-size` | Ensure `.windsurf/rules/*.md` < 12KB | No |
| `changelog-check` | Require CHANGELOG.md updates for code changes | No |
| `structure-check` | Ensure `.md` files in correct locations | No |
| `sync-extensions` | Keep EXTENSIONS.md updated with installed extensions | No |
| `sync-cascade-backup` | Export AI memories and global rules daily | No |

### Pre-commit Workflow

In Kilo code review, pre-commit runs **before** AI agents with auto-fixing:

```python
MAX_PRECOMMIT_ITERATIONS = 5

def run_precommit(files: list[Path], max_iterations: int = 5) -> bool:
    # 1. Run pre-commit
    # 2. If "files were modified" - auto-fix happened, re-run
    # 3. If ruff issues - run ruff --fix directly
    # 4. Repeat until clean or max iterations
    # 5. If still failing after 5 iterations - abort, require manual fixes
```

**Purpose:** Catches ~80% of MINOR issues for FREE before expensive AI review runs.

---

## Windsurf Rules (`.windsurf/rules/`)

| File | Size | Activation | Content |
|------|------|------------|---------|
| `00-critical.md` | 2.2KB | Always On | Security, env vars, ports |
| `10-python.md` | 2.3KB | `**/*.py` | FastAPI patterns |
| `20-typescript.md` | 2.0KB | `**/*.ts` | Next.js patterns |
| `30-ops.md` | 3.1KB | Dockerfile, compose | Docker standards |
| `90-automation.md` | 2.6KB | Manual | Kilo CLI automation |

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

Automatic code review is available via **Kilo CLI** as part of the 8-step workflow (Step 3):

### Components

| Script | Purpose |
|--------|--------|
| `scripts/kilo_code_review.py` | Runs AI code review on staged changes |
| `scripts/kilo_docs_enforcer.py` | Auto-generates and enforces documentation |

### Flow

```
Code edit → git add → kilo_code_review.py staged → fix findings → commit
```

### Usage

```bash
# Review staged changes
python scripts/kilo_code_review.py staged --plan "task description" --output json

# Auto-generate docs
python scripts/kilo_docs_enforcer.py --auto-generate --verbose
```

### Integration

**Works with both Cascade and Kilo CLI.** The 8-step workflow in AGENTS.md defines when to run reviews.

---

## See Also

- [AGENTS.md](../../AGENTS.md) — Cross-agent briefing
- [Final Gate Workflow](../workflows/FINAL_GATE_WORKFLOW.md) — Pre-commit quality gate
