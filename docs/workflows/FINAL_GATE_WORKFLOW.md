# Final Gate Workflow

**Last Updated:** 2026-04-03
**Script:** `scripts/final_gate.py`

> Complete reference for `scripts/final_gate.py` — deterministic quality checks that validate code and documentation before Traycer commit.

---

## Table of Contents

1. [Overview](#overview)
2. [When to Use](#when-to-use)
3. [Commands Reference](#commands-reference)
4. [Execution Phases](#execution-phases)
5. [All Checks Reference](#all-checks-reference)
6. [Configuration](#configuration)
7. [Exit Codes](#exit-codes)
8. [Integration Examples](#integration-examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview

`final_gate.py` provides **deterministic quality checks** that catch formatting, syntax, and convention errors before expensive LLM review. It validates both code quality and documentation completeness.

### Key Features

1. **Auto-fix formatting** — Repairs whitespace, EOF newlines, Python formatting
2. **Static analysis** — Runs ruff, mypy, bandit, semgrep, yaml/json validation
3. **Repo consistency** — Validates Fabrik conventions, structure, and documentation
4. **Iterative convergence** — Re-runs up to 3 times when files change
5. **Best-effort tools** — Skips optional tools if not installed

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Final Gate System                           │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 1: AUTO-FIX     │  PHASE 2: STATIC      │  PHASE 3: REPO │
│  ├── whitespace        │  ├── ruff             │  ├── structure │
│  ├── EOF newlines      │  ├── mypy             │  ├── conventions│
│  ├── ruff format       │  ├── bandit           │  ├── changelog │
│  └── ruff --fix        │  ├── semgrep          │  └── symlinks  │
│                        │  ├── yaml/json        │                │
│                        │  ├── sqlfluff         │                │
│                        │  └── vulture          │                │
└─────────────────────────────────────────────────────────────────┘
```

---

## When to Use

| Context | Command | Purpose |
|---------|---------|---------|
| **Agent self-review (Tier 1)** | `python scripts/final_gate.py --lean` | Fast showstoppers only (syntax, secrets, schema sync) |
| **Phase handover (Tier 2)** | `python scripts/final_gate.py` | Full quality gate before Traycer commit |
| **Systemic maintenance (Tier 3)** | `python scripts/final_gate.py --systemic` | Repo health only (docker, ports, deps, docs sprawl, env contract, watchdog, health) |
| **CI read-only** | `python scripts/final_gate.py --check` | Read-only verification (no fixes, tier selected by flags) |

**Note:** Default mode auto-stages changes if all checks pass. Use `--no-stage` to disable.

---

## Commands Reference

### Basic Commands

```bash
# Tier 1 (LEAN): Showstoppers only (syntax, secrets, schema sync)
python scripts/final_gate.py --lean

# Tier 2 (FULL - default): Full quality gate
python scripts/final_gate.py

# Tier 3 (SYSTEMIC): Repo health only (no showstoppers)
python scripts/final_gate.py --systemic

# Check-only mode (CI - no fixes, respects tier flags)
python scripts/final_gate.py --check

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

## Execution Phases

### Phase 1: Auto-Fix Formatting

**Runs in:** Fix mode for Tier 1 and Tier 2 (skipped for Tier 3 and in `--check` mode)
**Skipped in:** `--check` mode

| Check | Action | Files Affected |
|-------|--------|----------------|
| **Trailing whitespace** | Strip trailing spaces | `*.py`, `*.md`, `*.yaml`, `*.yml`, `*.json`, `*.sh` |
| **EOF newlines** | Ensure files end with newline | Same as above |
| **ruff format** | Auto-format Python code | `src/`, `scripts/` |
| **ruff --fix** | Auto-fix lint issues | `src/`, `scripts/` |

### Phase 2: Static Analysis

**Runs in:** All modes for Tier 1 and Tier 2 (skipped for Tier 3)

| Check | Tool | Timeout | Required |
|-------|------|---------|----------|
| **ruff** | Lint check (no fix) | 120s | ✅ Yes |
| **mypy** | Type checking | 300s | ✅ Yes |
| **bandit** | Security scanner | 180s | ⚠️ Best-effort |
| **semgrep** | SAST rules | 30s | ⚠️ Best-effort |
| **yaml** | YAML syntax | — | ✅ Yes |
| **json** | JSON syntax | — | ✅ Yes |
| **sqlfluff** | SQL lint (PostgreSQL dialect) | 180s | ⚠️ If SQL files exist |
| **vulture** | Dead code | — | ⚠️ Best-effort |

**Best-effort checks:** Skip if tool not installed, don't fail build.

### Phase 3: Repo Consistency

**Runs in:** All tiers (1, 2, 3) and modes (except `--sync`), with tier-specific check sets:

- **Tier 1 (`--lean`)**: Showstoppers only (secrets, env vars, schema sync).
- **Tier 2 (default)**: Full consistency suite (structure, docs, changelog, schema, ports, docker, etc.).
- **Tier 3 (`--systemic`)**: Systemic repo health only (docker, ports, env contract, deps, docs completeness/drift, doc sprawl, watchdog, health, duplicates).

### Tier Matrix

| Tier | Flag | Primary Use |
|------|------|-------------|
| 1 | `--lean` | Agent self-review loop (fast showstoppers) |
| 2 | *(default)* | Phase handover / pre-commit quality gate |
| 3 | `--systemic` | On-demand repo/system hygiene |

### Tier 1 (LEAN) - `--lean` - Agent Self-Review

**Purpose:** Fast showstoppers only (syntax, secrets, schema sync, changelog)

**Phase 3: Repo Consistency (5 checks)**
- **Secrets (Zero Hardcoding)** - `check_secrets.py`
  - Scans for hardcoded secrets (API keys, passwords, tokens)
  - Enforces use of environment variables
- **.env Updates (Secrets)** - `check_env_vars.py`
  - Validates .env files don't contain actual secrets
  - Ensures .env.example is properly maintained
- **Schema Sync (DB Models)** - `check_schema_sync.py`
  - Only runs if .py or .sql files changed
  - Ensures database schema changes are documented in `db/schema.sql`
- **CHANGELOG.md Updated** - `check_changelog.py`
  - Enforces changelog entry for every task (prevents forgetting across tasks 1-9)
  - Reduces token spike at milestone by enforcing incrementally
  - Context stays small, fixes are instantaneous
- **Print/Console Ban** - `check_print_ban.py`
  - Bans `print()` in `.py` and `console.log()` in `.ts`/`.tsx`/`.js`/`.jsx` production code
  - Skips test files (all extensions) and `scripts/` directory

### Tier 2 (FULL) - Default - Phase Handover

**Purpose:** Full quality gate before Traycer commit

**Phase 3: Repo Consistency (17 checks)**
- **Project Structure** - `check_structure.py`
  - Validates directory layout matches Fabrik conventions
- **Rule File Size** - `check_rule_size.py`
  - Ensures `.windsurf/rules/` files are < 50KB each
- **opencode.json** - `check_opencode_json.py`
  - Validates Kilo-safe rules configuration
- **INDEX.md** - `check_index_md.py`
  - Ensures master file index is current
- **One-Test Rule** - `check_test_proposal.py`
  - Verifies test justification is documented
- **README.md** - `check_readme_md.py`
  - Validates primary entry point documentation
- **CONFIGURATION.md** - `check_configuration_md.py`
  - Ensures environment variables are documented
- **.env Updates (Secrets)** - `check_env_updates.py`
  - Validates secrets not committed to git
- **OpenAPI Sync** - `check_openapi_sync.py`
  - Validates API documentation matches routes
- **Test Coverage** - `check_test_coverage.py`
  - Ensures new code has test coverage
- **.env.example** - `check_env_example.py`
  - Validates all environment variables are documented
- **Compose Services** - `check_compose_services.py`
  - Ensures Docker Compose services are documented
- **Schema Sync (DB Models)** - `check_schema_sync.py`
  - Ensures DB models match schema documentation
- **Secrets (Zero Hardcoding)** - `check_secrets.py`
  - Scans for hardcoded secrets
- **Kilo CLI Health Check** - `check_kilo_health.sh`
  - Validates Kilo CLI installation and configuration
- **User Guide Presence** - `check_user_guide.py`
  - Verifies `docs/user-guide/` exists with `.md` files when `project.yaml` has `has_user_guide: true`
  - Skips silently when `has_user_guide` is false or absent
- **Reusable Module Tagging** - `check_reusable_modules.py` *(advisory — warning only)*
  - Checks `src/utils/` and `src/lib/` modules are tagged `[reusable]` in `INDEX.md`
  - Surfaces warnings in yellow but does not fail the gate

### Tier 3 (SYSTEMIC) - `--systemic` - Repo Health

**Purpose:** On-demand repo/system hygiene (no showstoppers)

**Phase 3: Repo Consistency (13 checks)**
- **Docker** - `check_docker.py`
  - Validates amd64 compatibility, No-Alpine base images, HEALTHCHECK presence
- **Port Registration** - `check_ports.py`
  - Ensures PORTS.md is updated with port allocations
- **.env Contract Sync** - `check_env_contract.py`
  - Validates environment variable contracts are consistent
- **Dependencies Sync** - `check_deps_sync.py`
  - Ensures dependencies are properly documented
- **Documentation** - `check_docs.py`
  - Validates required documentation files are present
- **Documentation Sprawl** - `check_doc_sprawl.py`
  - Detects documentation sprawl and duplication
- **Watchdog Scripts** - `check_watchdog.py`
  - Ensures watchdog monitoring scripts are present
- **Health Endpoint** - `check_health.py`
  - Validates /health endpoint tests actual dependencies
- **Duplicate Detection** - `check_duplicates.py`
  - Detects duplicate files and configurations
- **Documentation Drift** - `docs_updater.py --check`
  - Ensures documentation matches code implementation
- **Fabrik Conventions** - `validate_conventions.py --strict`
  - Validates naming conventions and structure
- **Kilo CLI Health Check** - `check_kilo_health.sh`
  - Validates Kilo CLI installation and configuration

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

#### sqlfluff

```bash
# What it checks
python -m sqlfluff lint --dialect postgres *.sql
```

**Dialect:** PostgreSQL (required for Fabrik projects)

**Common issues:**
- SQL syntax errors
- Missing semicolons
- Incorrect keywords
- Inconsistent capitalization

**Note:** Only runs if `.sql` files exist in the repository.

### Enforcement Scripts

All repo consistency checks are implemented by scripts in `scripts/enforcement/`. Each script validates specific Fabrik conventions:

- `check_structure.py` — Validates required directories exist
- `check_rule_size.py` — Ensures rule files < 50KB
- `check_opencode.json.py` — Validates Kilo-safe instruction list
- `check_index_md.py` — Verifies INDEX.md reflects current structure
- `check_test_proposal.py` — Enforces One-Test Rule documentation
- `check_readme_md.py` — Validates README.md structure
- `check_configuration_md.py` — Ensures env vars documented
- `check_env_updates.py` — Prevents secret commits
- `check_changelog.py` — Validates CHANGELOG.md updated
- `check_schema_sync.py` — Checks DB models match schema.sql
- `check_openapi_sync.py` — Validates API docs match routes
- `check_test_coverage.py` — Ensures new code has tests
- `check_env_example.py` — Validates .env.example completeness
- `check_compose_services.py` — Documents Docker services
- `check_docker.py` — Enforces amd64, no-Alpine, HEALTHCHECK
- `check_secrets.py` — Scans for hardcoded secrets
- `check_env_contract.py` — Validates env var contracts
- `check_ports.py` — Checks PORTS.md registration
- `check_health.py` — Validates /health endpoint
- `check_deps_sync.py` — Validates dependencies documented
- `check_docs.py` — Ensures required docs present
- `validate_conventions.py` — Enforces naming/structure conventions

---

#### check_structure.py

**Purpose:** Validate project follows Fabrik directory structure.

**Required directories:**
- `src/` — Source code
- `docs/` — Documentation
- `scripts/` — Utility scripts
- `tests/` — Test suite
- `.droid/` — Kilo working directory

**Why this matters:**
- Consistent structure across projects
- Enables automation and tooling

#### check_rule_size.py

**Purpose:** Ensures rule files are under 50KB each.

**Validates:**
- `.windsurf/rules/*.md` files < 50KB
- Rules are concise and focused
- No unnecessary verbosity

**Why this matters:**
- Keeps rules manageable
- Prevents AI context overflow

#### check_opencode_json.py

**Purpose:** Ensures project's opencode.json contains only Kilo-safe instructions.

**Validates:**
- File exists and is valid JSON
- Contains `instructions` field that is a list
- Instructions exactly match Kilo-safe allowlist: `["AGENTS-compact.md"]`
- No forbidden patterns (e.g., `.windsurf/rules/*.md`)
- Instructions are in correct order

**Why this matters:**
- Prevents Cascade-only rules from being passed to Kilo CLI agents
- Ensures consistent behavior across all projects
- Enforces separation: Traycer uses AGENTS.md, Kilo uses AGENTS-compact.md

**Example valid configuration:**
```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "AGENTS-compact.md"
  ]
}
```

#### check_index_md.py

**Purpose:** Ensures INDEX.md reflects current file structure.

**Validates:**
- All important files are listed
- No stale entries for deleted files
- File descriptions are accurate
- Hierarchy is properly organized

**Why this matters:**
- Provides project navigation
- Helps new team members find files

#### check_test_proposal.py

**Purpose:** Enforce One-Test Rule from Solo-Dev Creed (Step 2.5 Decision-Grade Audit).

**When triggered:**
- After Step 2.5 Internal Audit
- During Step 5 Final Gate (this script)
- Validates that agents documented test justification BEFORE implementation

**Validates presence of:**
- `One-Test Rule` heading or section
- `Given` — Initial state
- `When` — Action taken
- `Then` — Expected result

**Location checked:** `docs/development/plans/` (latest plan file)

**Skipped when:** No plans directory or no plan files exist

**Why this matters:**
- **Forces High-Leverage Thinking:** Solo developers avoid low-value "coverage" tests
- **Prevents Forgotten Context:** Documents how to verify core logic for future maintenance
- **Ensures AI Discipline:** Stops agents from prioritizing "clean code" over correctness
- **Zero-Speculation:** Eliminates need to "guess" how to test during implementation

**Example format:**
```markdown
## One-Test Rule

**Why:** Database connection pooling is the highest risk area — if pool exhausts,
entire API becomes unresponsive. This test verifies graceful degradation.

**Contract:**
- **Given:** Connection pool at max capacity (10/10 connections)
- **When:** New API request arrives
- **Then:** Request waits up to 5s, then returns 503 with retry-after header
- **Mocked:** Database responses (simulate slow queries)
- **Real:** Connection pool manager, timeout logic
```

**Exit codes:**
- `0` — Proposal found or no plan exists
- `1` — Plan exists but missing required keywords

#### check_readme_md.py

**Purpose:** Ensures README.md is a valid primary entry point.

**Validates:**
- Required sections exist (Overview, Quick Start, etc.)
- Installation instructions work
- Links are valid
- Project description is clear

**Why this matters:**
- README is often the first thing people see
- Must provide accurate project introduction

#### check_configuration_md.py

**Purpose:** Ensures CONFIGURATION.md documents all env vars.

**Validates:**
- Every environment variable is documented
- Usage examples are provided
- Security implications are noted
- Default values are specified

**Why this matters:**
- Complete configuration reference
- Prevents configuration errors

#### check_env_updates.py

**Purpose:** Ensures no secrets are committed to git.

**Validates:**
- No API keys in code
- No passwords or tokens
- No private keys or certificates
- Proper use of os.getenv() for secrets

**Why this matters:**
- Prevents credential leakage in version control
- Enforces security best practices

**Skips:**
- Test files only
- Documentation only
- Config files only

#### check_changelog.py

**Purpose:** Ensures CHANGELOG.md is updated for significant code changes.

**Triggers when:**
- Changes in `src/`, `scripts/`, `templates/`
- More than 10 lines changed
- New files added

**Skips:**
- Test files only
- Documentation only
- Config files only

**Validates:**
- Entry exists for current changes
- Follows changelog format
- Includes version/date

**Why this matters:**
- Maintains project history
- Helps with release tracking

#### check_schema_sync.py

**Purpose:** Ensures database models match schema.sql.

**Validates:**
- All models have corresponding schema
- Schema includes all columns and indexes
- Migration history is consistent
- Data types match

**Why this matters:**
- Prevents database mismatches
- Ensures reproducible deployments

#### check_openapi_sync.py

**Purpose:** Ensures API documentation matches actual routes.

**Validates:**
- All endpoints are documented
- Request/response schemas match
- Authentication requirements are documented
- Example values are accurate

**Why this matters:**
- API docs must be trustworthy
- Prevents integration issues

#### check_test_coverage.py

**Purpose:** Ensures new code has appropriate test coverage.

**Validates:**
- New functions have tests
- Critical paths are covered
- Edge cases are considered
- Tests are meaningful (not just coverage)

**Why this matters:**
- Maintains code quality
- Catches regressions early

#### check_env_example.py

**Purpose:** Ensures all environment variables are documented.

**Validates:**
- Every env var in code has entry in .env.example
- Descriptions are clear and accurate
- Default values are provided where appropriate

**Why this matters:**
- Enables easy setup for new developers
- Documents all configuration options

#### check_compose_services.py

**Purpose:** Ensures Docker Compose services are documented.

**Validates:**
- All services have descriptions
- Port mappings are documented
- Environment variables are listed
- Volume mounts are explained

**Why this matters:**
- Provides clear deployment documentation
- Helps with service understanding

#### check_docker.py

**Purpose:** Enforces Docker conventions for amd64 compatibility and security.

**Validates:**
- **No Alpine images**: Blocks `FROM alpine` and variants (use `-slim-bookworm` instead)
- **amd64 platform**: Custom builds must specify `platform: linux/amd64`
- **HEALTHCHECK**: All Dockerfiles must include health check
- **Approved base images**: Python 3.12/3.13-slim-bookworm, Node 22-bookworm-slim, debian:bookworm-slim, ubuntu:24.04
- **Port consistency**: EXPOSE ports match compose.yaml mappings

**Why this matters:**
- amd64 is required for VPS deployment (x86_64)
- Alpine images have glibc compatibility issues
- Health checks enable proper container monitoring

#### check_secrets.py

**Purpose:** No secrets committed to git.

**Scans for:**
- API keys
- Passwords
- Private keys
- AWS credentials

**Example detection:**
```python
# BAD
DB_HOST = 'localhost'
API_KEY = 'sk-abc123'

# GOOD
DB_HOST = os.getenv('DB_HOST', 'localhost')
API_KEY = os.getenv('API_KEY')
```

#### check_env_contract.py

**Purpose:** Ensures environment variable contracts are consistent.

**Validates:**
- `.env.example` matches actual `.env` variables
- All required variables are documented
- No undocumented variables in use
- Variable descriptions are accurate

**Why this matters:**
- Prevents deployment failures due to missing env vars
- Ensures clear documentation for setup

#### check_ports.py

**Purpose:** Ensures PORTS.md is updated with port allocations.

**Validates:**
- All used ports are registered
- No port conflicts documented
- Port purposes are explained
- Auto-generated section is current

**Why this matters:**
- Prevents port conflicts across projects
- Documents service endpoints

#### check_deps_sync.py

**Purpose:** Ensures dependencies are properly documented and synchronized.

**Validates:**
- `requirements.txt` contains production dependencies only
- `requirements-dev.txt` contains development dependencies
- Package versions are pinned
- No dependency conflicts
- Development dependencies properly separated

**Why this matters:**
- Prevents import errors in deployment
- Ensures reproducible builds

#### check_docs.py

**Purpose:** Ensures all required documentation files are present.

**Validates:**
- README.md exists and has required sections
- CONFIGURATION.md documents all env vars
- CHANGELOG.md exists for version tracking
- Required API docs are generated

**Why this matters:**
- Ensures project is self-documenting
- Prevents missing critical documentation

#### check_health.py

**Purpose:** Ensures health endpoints test actual dependencies.

**Validates:**
- /health endpoint exists
- Returns proper JSON structure
- Tests database connection
- Checks external service dependencies

**Why this matters:**
- Health checks must reflect real system state
- Prevents false-positive monitoring

#### docs_updater.py

**Purpose:** Ensures documentation matches code (drift check).

**Validates:**
- API docs match actual implementation
- Class/function docs are current
- Parameter types are accurate
- Return values are documented

**Why this matters:**
- Prevents documentation drift
- Maintains trust in docs

#### update_agents_toc.py

**Purpose:** Ensures AGENTS.md table of contents is current.

**Validates:**
- All sections are listed in TOC
- Page numbers/links are accurate
- No stale TOC entries
- Formatting is consistent

**Why this matters:**
- Navigation aid for large document
- Helps find specific sections quickly

#### validate_conventions.py

**Purpose:** Fabrik naming and structure conventions.

**Validates:**
- Package names (lowercase, underscores)
- File naming patterns
- Import structure
- Docstring presence

**Why this matters:**
- Maintains consistency across projects
- Enables automated tooling

### Symlink Integrity Check

**Purpose:** Governance files must be local copies, not symlinks.

**Validates:**
- `AGENTS.md` — Local copy
- `AGENTS-compact.md` — Local copy
- `opencode.json` — Local copy
- `.windsurfrules` — Local copy
- `.windsurf/rules/` — Local directory (not symlinked), recursive descendant check
- `.windsurf/workflows/` — Local directory (not symlinked), recursive descendant check

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

## Integration Examples

### Example 1: Coder Agent Plan

```
5. Fix Issues
   - Run final_gate.py to validate implementation
   - If failures:
     * Fix formatting issues (auto-fixed by gate)
     * Fix semantic errors (mypy, bandit findings)
     * Fix convention violations
   - Re-run final_gate.py until PASS
   - Changes auto-staged
```

### Example 2: Fixer Agent Plan

```
3. Validate Fixes
   - Run final_gate.py to ensure no regressions
   - Address any new issues found
   - Re-run until all checks pass
```

### Example 3: CI/CD Pipeline

```yaml
- name: Final Gate Check
  run: python scripts/final_gate.py --check
```

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

### "opencode.json contains incorrect Kilo-safe list"

**Cause:** Project's opencode.json has wrong instructions.

**Common issues:**
- Contains `.windsurf/rules/*.md` (Cascade-only)
- Contains `AGENTS.md` (Traycer-only)
- Missing `AGENTS-compact.md`
- Wrong order of instructions

**Fix:** Update project's opencode.json:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [
    "AGENTS-compact.md"
  ]
}
```

**Note:** This check validates the PROJECT's opencode.json, not the global one at `~/.config/kilo/opencode.json`.

### "Symlink integrity failed"

**Cause:** Old project has symlinks to `/opt/fabrik` (pre-March 2026 scaffold).

**Fix:** Run `fabrik fix` to migrate symlinks to copies:
```bash
fabrik fix /opt/your-project
```

Or manually copy:
```bash
rm -f AGENTS.md AGENTS-compact.md opencode.json .windsurfrules  # Remove old symlinks
rm -rf .windsurf/rules .windsurf/workflows                      # Remove old symlinked dirs
mkdir -p .windsurf
cp /opt/fabrik/AGENTS.md ./AGENTS.md
cp /opt/fabrik/AGENTS-compact.md ./AGENTS-compact.md
cp /opt/fabrik/opencode.json ./opencode.json
cp /opt/fabrik/.windsurfrules ./.windsurfrules
cp -r /opt/fabrik/.windsurf/rules/ ./.windsurf/rules/
cp -r /opt/fabrik/.windsurf/workflows/ ./.windsurf/workflows/
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
/opt/<project>/.venv/bin/pip install bandit semgrep sqlfluff vulture
```

**Note:** These are best-effort; missing tools are skipped.

---

## Sources of Truth

- `.windsurfrules` — Cascade agent contract: behavior rules, invariants, and audit directives.
- `.windsurf/rules/50-code-review.md` — Tiered gate commands and usage for Cascade.
- `.windsurf/rules/90-automation.md` — Traycer YOLO automation and gate triggering.
- `scripts/final_gate.py` — Executable tiered implementation (runtime truth).

## See Also

- [AGENTS.md](../../AGENTS.md) — Traycer orchestrator contract
- [KILO_REVIEW_WORKFLOW.md](KILO_REVIEW_WORKFLOW.md) — AI code review workflow
- [KILO_AGENT_MANAGEMENT.md](KILO_AGENT_MANAGEMENT.md) — Agent discovery, benchmarking, role assignment
- [DOCUMENTATOR_WORKFLOW.md](DOCUMENTATOR_WORKFLOW.md) — Documentation generation
- [FABRIK_SCAFFOLD_WORKFLOW.md](FABRIK_SCAFFOLD_WORKFLOW.md) — Project scaffold reference
