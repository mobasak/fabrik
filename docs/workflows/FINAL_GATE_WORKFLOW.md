# Final Gate Workflow

**Last Updated:** 2026-03-23

> Complete workflow documentation for `scripts/final_gate.py` — deterministic quality checks after DOCUMENTATOR and before Traycer verification and commit.

---

## Table of Contents

1. [Overview](#overview)
2. [When to Use](#when-to-use)
3. [Commands Reference](#commands-reference)
4. [Workflow Phases](#workflow-phases)
5. [All Checks Reference](#all-checks-reference)
6. [Enforcement Scripts](#enforcement-scripts)
7. [Configuration](#configuration)
8. [Exit Codes](#exit-codes)
9. [Integration with AGENTS.md Workflow](#integration-with-agentsmd-workflow)
10. [Troubleshooting](#troubleshooting)

---

## Overview

`final_gate.py` provides **deterministic quality checks** that run at Step 5, after KILO_REVIEW (Step 3) and DOCUMENTATOR (Step 4). It validates both code quality and documentation completeness in a single pass:

1. **Single-pass validation** — Check code AND docs together after DOCUMENTATOR generates them
2. **Fail fast** — Catch lint, syntax, and convention errors before Traycer verification
3. **Auto-fix** — Automatically repair formatting issues
4. **Enforce standards** — Validate Fabrik conventions

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       Final Gate System                          │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 1: AUTO-FIX     │  PHASE 2: STATIC      │  PHASE 3: REPO │
│  ├── whitespace        │  ├── ruff             │  ├── structure │
│  ├── EOF newlines      │  ├── mypy             │  ├── conventions│
│  ├── ruff format       │  ├── bandit           │  ├── changelog │
│  └── ruff --fix        │  ├── semgrep          │  ├── symlinks  │
│                        │  ├── yaml/json        │  └── docs sync │
│                        │  ├── sqlfluff         │                │
│                        │  └── vulture          │                │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 4: SYNC (--sync only)                                    │
│  ├── Windsurf extensions → docs/reference/EXTENSIONS.md         │
│  └── Cascade backup freshness check                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## When to Use

| Context | Command | Purpose |
|---------|---------|---------|
| **Step 5** (After DOCUMENTATOR) | `python scripts/final_gate.py` | Fix mode — validate code + docs |
| **CI Pipeline** | `python scripts/final_gate.py --check` | Read-only verification |
| **Sync Mode** (manual) | `python scripts/final_gate.py --sync` | Sync extensions/backup only |

**Note:** Final gate runs **once** at Step 5, after DOCUMENTATOR (Step 4). It validates both code quality AND documentation in a single pass.

---

## Commands Reference

### Basic Commands

```bash
# Default: Fix mode (Step 5 - after DOCUMENTATOR)
# Auto-fixes formatting, runs all checks, stages if all pass
python scripts/final_gate.py

# Check-only mode (CI - no fixes, no sync)
python scripts/final_gate.py --check

# Sync-only mode (manual utility - no quality checks)
python scripts/final_gate.py --sync

# Don't auto-stage modified files
python scripts/final_gate.py --no-stage

# Log issues for post-Kilo analysis
python scripts/final_gate.py --post-kilo
```

### AI Fix Agent (Experimental)

```bash
# Enable AI-assisted fixes for mypy/ruff errors
FINAL_GATE_AI_FIX=1 python scripts/final_gate.py
```

---

## Workflow Phases

### Phase 1: Auto-Fix Formatting

**Runs in:** Fix mode (default)
**Skipped in:** `--check` mode

| Check | Action | Files Affected |
|-------|--------|----------------|
| **Trailing whitespace** | Strip trailing spaces | `*.py`, `*.md`, `*.yaml`, `*.yml`, `*.json`, `*.sh` |
| **EOF newlines** | Ensure files end with newline | Same as above |
| **ruff format** | Auto-format Python code | `src/`, `scripts/` |
| **ruff --fix** | Auto-fix lint issues | `src/`, `scripts/` |

### Phase 2: Static Analysis

**Runs in:** All modes

| Check | Tool | Timeout | Required |
|-------|------|---------|----------|
| **ruff** | Lint check (no fix) | 120s | ✅ Yes |
| **mypy** | Type checking | 300s | ✅ Yes |
| **bandit** | Security scanner | 180s | ⚠️ Best-effort |
| **semgrep** | SAST rules | 30s | ⚠️ Best-effort |
| **yaml** | YAML syntax | — | ✅ Yes |
| **json** | JSON syntax | — | ✅ Yes |
| **sqlfluff** | SQL lint | 180s | ⚠️ If SQL files exist |
| **vulture** | Dead code | — | ⚠️ Best-effort |

**Best-effort checks:** Skip if tool not installed, don't fail build.

### Phase 3: Repo Consistency

**Runs in:** All modes (except `--sync`)

| Check | Script | Purpose |
|-------|--------|---------|
| **Project Structure** | `check_structure.py` | Validate directory layout |
| **Rule File Size** | `check_rule_size.py` | `.windsurf/rules/` < 50KB each |
| **opencode.json** | `check_opencode_json.py` | Kilo-safe rules validation |
| **INDEX.md** | `check_index_md.py` | Master file index current |
| **README.md** | `check_readme_md.py` | Primary entry point valid |
| **CONFIGURATION.md** | `check_configuration_md.py` | Env vars documented |
| **.env Updates** | `check_env_updates.py` | Secrets not in git |
| **CHANGELOG.md** | `check_changelog.py` | Updated for code changes |
| **Schema Sync** | `check_schema_sync.py` | DB models match schema |
| **OpenAPI Sync** | `check_openapi_sync.py` | API docs match routes |
| **Test Coverage** | `check_test_coverage.py` | New code has tests |
| **.env.example** | `check_env_example.py` | All vars documented |
| **Compose Services** | `check_compose_services.py` | Services documented |
| **Documentation Drift** | `docs_updater.py --check` | Docs match code |
| **AGENTS.md TOC** | `update_agents_toc.py --check` | TOC current |
| **Fabrik Conventions** | `validate_conventions.py --strict` | Naming, structure |
| **Kilo CLI Health** | `check_kilo_health.sh` | Kilo available |
| **Symlink Integrity** | (inline) | Governance files local |

### Phase 4: Sync Steps

**Runs in:** `--sync` mode only

| Step | Script | Purpose |
|------|--------|---------|
| **Windsurf Extensions** | `sync_extensions.sh` | Sync to EXTENSIONS.md |
| **Cascade Backup** | `sync_cascade_backup.sh` | Check backup freshness |

---

## All Checks Reference

### Static Analysis Checks (Phase 2)

#### ruff

```bash
# What it checks
python -m ruff check src/ scripts/

# Auto-fix (Phase 1)
python -m ruff check --fix src/ scripts/
python -m ruff format src/ scripts/
```

**Common issues:**
- Unused imports (F401)
- Undefined names (F821)
- Line too long (E501)
- Import sorting (I001)

#### mypy

```bash
# What it checks
python -m mypy --config-file=pyproject.toml src/package_name
```

**Recovery:** If mypy hangs (cache corruption), final_gate clears cache and retries with `--no-incremental`.

**Common issues:**
- Missing type annotations
- Type mismatches
- Incompatible return types

#### bandit

```bash
# What it checks
python -m bandit -ll -x tests/ -r src/
```

**Common issues:**
- Hardcoded passwords (B105)
- SQL injection (B608)
- Insecure pickle (B301)

#### semgrep

```bash
# What it checks
semgrep --config auto src/
```

**Note:** Requires `semgrep login` for authentication. Skipped if not authenticated.

### Enforcement Checks (Phase 3)

#### check_changelog.py

**Purpose:** Ensure CHANGELOG.md updated for significant code changes.

**Triggers when:**
- Changes in `src/`, `scripts/`, `templates/`
- More than 10 lines changed
- New files added

**Skips:**
- Test files only
- Documentation only
- Config files only

#### check_structure.py

**Purpose:** Validate project follows Fabrik directory structure.

**Required directories:**
- `src/` — Source code
- `docs/` — Documentation
- `scripts/` — Utility scripts
- `tests/` — Test suite
- `.droid/` — Kilo working directory

#### check_env_vars.py

**Purpose:** No hardcoded localhost or secrets.

**Checks for:**
```python
# BAD
DB_HOST = 'localhost'
API_KEY = 'sk-abc123'

# GOOD
DB_HOST = os.getenv('DB_HOST', 'localhost')
API_KEY = os.getenv('API_KEY')
```

#### check_health.py

**Purpose:** Health endpoints test actual dependencies.

**Validates:**
- `/health` endpoint exists
- Returns proper JSON structure
- Tests database connection (if configured)

#### check_secrets.py

**Purpose:** No secrets committed to git.

**Scans for:**
- API keys
- Passwords
- Private keys
- AWS credentials

#### validate_conventions.py

**Purpose:** Fabrik naming and structure conventions.

**Validates:**
- Package names (lowercase, underscores)
- File naming patterns
- Import structure
- Docstring presence

### Symlink Integrity Check

**Purpose:** Governance files must be local copies, not symlinks.

**Validates:**
- `AGENTS.md` — Local copy
- `AGENTS-compact.md` — Local copy
- `opencode.json` — Local copy
- `.windsurfrules` — Local copy
- `.windsurf/rules/` — Local directory (not symlinked)

**Self-exemption:** Skipped when running inside `/opt/fabrik` (source repo).

---

## Configuration

### Timeouts

| Tool | Timeout (seconds) |
|------|-------------------|
| default | 120 |
| mypy | 300 |
| bandit | 180 |
| sqlfluff | 180 |
| ruff | 120 |
| semgrep | 300 |

### Max Iterations

Final gate runs up to **3 iterations** to achieve convergence (auto-fix → re-validate).

### Colors (Terminal Output)

- 🟢 **PASS** — Check succeeded
- 🔴 **FAIL** — Check failed
- 🟡 **SKIP** — Check skipped (tool not installed)

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | One or more checks failed |

---

## Integration with AGENTS.md Workflow

### Position in 8-Step Workflow

```
PLAN → IMPLEMENT → SELF_REVIEW → KILO_REVIEW → DOCUMENTATOR → FINAL_GATE → VERIFY → COMMIT
                                                                ^^^^^^^^^^^
                                                                Step 5: This script
```

### Step 5: After DOCUMENTATOR

```bash
# After DOCUMENTATOR generates and stages docs (Step 4)
python scripts/final_gate.py

# If PASS → proceed to Step 6 (Traycer Verify)
# If FAIL → fix issues, re-run final_gate.py
```

Final gate runs **once** at Step 5. It validates both code quality AND documentation completeness in a single pass. There is no separate pre-Kilo or post-fix invocation.

### Sync Mode (Manual Utility)

```bash
# Sync Windsurf extensions to docs - NOT part of main workflow
python scripts/final_gate.py --sync
```

**Note:** FIXER is a conditional loop triggered only when Traycer verification (Step 6) fails — not part of the main workflow sequence.

---

## Troubleshooting

### "mypy hung (>30s) - clearing cache"

**Cause:** Incremental cache corrupted (common with large files).

**Auto-fix:** Script clears `.mypy_cache/` and retries with `--no-incremental`.

**Manual fix:**
```bash
rm -rf .mypy_cache/
python scripts/final_gate.py
```

### "semgrep not authenticated"

**Cause:** Semgrep requires login for rule updates.

**Fix:**
```bash
semgrep login
```

**Note:** Check is best-effort; build won't fail.

### "CHANGELOG.md not updated"

**Cause:** Significant code changes without changelog entry.

**Fix:** Add entry to `CHANGELOG.md`:
```markdown
## [Unreleased]

### Added
- New feature X

### Fixed
- Bug in Y
```

### "Symlink integrity failed"

**Cause:** Old project has symlinks to `/opt/fabrik` (pre-March 2026 scaffold).

**Fix:** Run `fabrik fix` to migrate symlinks to copies:
```bash
fabrik fix /opt/your-project
```

Or manually copy:
```bash
rm AGENTS.md .windsurfrules  # Remove symlinks
cp /opt/fabrik/AGENTS.md ./AGENTS.md
cp /opt/fabrik/opencode.json ./opencode.json
cp -r /opt/fabrik/.windsurf/rules/ ./.windsurf/rules/
```

**Note:** New scaffolds (March 2026+) copy files directly, no symlinks.

### "Command timed out after Xs"

**Cause:** Tool took too long (network issue, large codebase).

**Fix:** Check tool directly:
```bash
# Test specific tool
python -m mypy src/ --config-file=pyproject.toml
python -m bandit -r src/
```

### "No module named X"

**Cause:** Optional tool not installed.

**Fix:** Install missing tool:
```bash
pip install bandit semgrep sqlfluff vulture
```

**Note:** These are best-effort; missing tools are skipped.

---

## See Also

- [AGENTS.md](../../AGENTS.md) — Full workflow specification
- [KILO_REVIEW_WORKFLOW.md](KILO_REVIEW_WORKFLOW.md) — AI code review workflow
- [KILO_AGENT_MANAGEMENT.md](KILO_AGENT_MANAGEMENT.md) — Agent discovery, benchmarking, role assignment
- [DOCUMENTATOR_WORKFLOW.md](DOCUMENTATOR_WORKFLOW.md) — Documentation generation
- [fabrik-scaffold-specs.md](../reference/fabrik-scaffold-specs.md) — Project scaffold reference
