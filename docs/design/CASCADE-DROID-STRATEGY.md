# Windsurf + Fabrik Integration: Consensus Strategy

**Status:** APPROVED (Triple-Model Consensus)
**Date:** 2026-01-05
**Reviewed By:**
- gpt-5.1-codex-max (high reasoning)
- gemini-3-pro-preview (high reasoning)
- claude-sonnet-4-5-20250929 (thinking mode)

---

## Executive Summary

**All three models agree:** Split the 50KB `.windsurfrules` into 5 modular files (<12KB each), establish `AGENTS.md` as the canonical cross-agent source of truth, and create a shared enforcement layer that both Windsurf and droid exec call.

---

## 1. Consensus Architecture

### The Four Levels (Unanimous Agreement)

```
┌─────────────────────────────────────────────────────────────┐
│ Level 1: AGENTS.md (Canonical - ~17KB)                      │
│ • WHAT and WHY: Architecture, standards, documentation      │
│ • Symlinked to ALL projects                                 │
│ • Read by ALL AI agents (Windsurf, droid, Cursor, Aider)   │
└─────────────────────────────────────────────────────────────┘
                            ↓ References
┌─────────────────────────────────────────────────────────────┐
│ Level 2: .windsurf/rules/ (5 files, each <12KB)            │
│ • HOW: IDE-specific behavior, commands, enforcement         │
│ ├── 00-critical.md (Always On, 8KB)                        │
│ ├── 10-python.md (Glob: **/*.py, 8KB)                      │
│ ├── 20-typescript.md (Glob: **/*.ts, 6KB)                  │
│ ├── 30-ops.md (Glob: Dockerfile, 10KB)                     │
│ └── 90-automation.md (Manual @mention, 5KB)                │
│ • Symlinked to projects                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓ Calls
┌─────────────────────────────────────────────────────────────┐
│ Level 3: scripts/enforcement/ (Shared Validation)           │
│ • validate_conventions.py (Orchestrator)                    │
│ • check_env_vars.py, check_secrets.py, check_health.py     │
│ • Called by: Windsurf hooks + droid hooks + CI             │
│ • Exit codes: 0=pass, 2=block                              │
└─────────────────────────────────────────────────────────────┘
                            ↓ References
┌─────────────────────────────────────────────────────────────┐
│ Level 4: templates/ + docs/reference/ (Not Rules)           │
│ • Dockerfile templates → templates/dockerfile/              │
│ • Watchdog script → templates/scripts/watchdog.sh          │
│ • droid-exec-usage.md stays as reference doc               │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Content Distribution (All Models Agree)

### AGENTS.md (~17KB) - Cross-Platform Standards

**Include:**
- Agent readiness checklist (4 levels)
- Execution modes table (Explore/Design/Build/Verify/Ship)
- Environment variable patterns (canonical examples)
- Health check requirements (canonical examples)
- Documentation rules & enforcement
- Security baseline (CSPRNG, credentials in 2 places)
- Project layout standard
- Symlink instructions
- Core Fabrik conventions

**Exclude:**
- Windsurf-specific workflows (command tiers, protocols)
- Full templates (Dockerfile, watchdog, compose)
- Port mapping details

### 00-critical.md (~8KB) - Always On

**Include:**
- **First line:** "Read AGENTS.md before proceeding"
- Command execution tiers (A/B/C with rund/rundsh/runc)
- Before-writing-code protocol
- When-stuck protocol (15 min threshold)
- Port management conventions (ranges + check process)
- Security gates (credentials reminder)
- Cross-references to other rule files

### 10-python.md (~8KB) - Glob: **/*.py

**Include:**
- FastAPI patterns (routers, dependency injection)
- Environment variable loading (function-level, NOT class-level)
- Health check implementation example
- uvicorn port range (8000-8099)
- pytest/ruff/mypy defaults
- `.tmp/` rule (never /tmp/)
- PostgreSQL/pgvector patterns

### 20-typescript.md (~6KB) - Glob: **/*.ts, **/*.tsx

**Include:**
- SaaS skeleton mandate
- Next.js App Router structure
- Tailwind CSS patterns
- Port range (3000-3099)
- Environment handling with `process.env`
- API base URL conventions

### 30-ops.md (~10KB) - Glob: Dockerfile, compose.yaml

**Include:**
- Base image standards (Debian/Ubuntu, NO Alpine)
- Dockerfile template reference (point to templates/)
- compose.yaml template reference
- Healthcheck configuration
- Coolify deployment notes
- Microservice URL conventions
- Watchdog requirement (point to template)
- Compliance checklist (14 items)

### 90-automation.md (~5KB) - Manual @mention

**Include:**
- Fabrik Skills table (10 skills)
- Auto-run mode levels
- droid exec quick reference
- Model management commands
- Dual-model code review pattern
- Large feature workflow summary

---

## 3. Deduplication Strategy (Consensus)

### Principle: One-Way References

```
AGENTS.md (Source of Truth)
    ↓
.windsurf/rules/* (References AGENTS.md, adds enforcement)
    ↓
scripts/enforcement/* (Implements checks programmatically)
```

### Topic Ownership

| Topic | Primary Location | Secondary (Reference) |
|-------|-----------------|----------------------|
| Env var patterns | AGENTS.md | 10-python.md (enforcement) |
| Health check standards | AGENTS.md | 30-ops.md (enforcement) |
| Command tiers A/B/C | 00-critical.md | Brief mention in AGENTS.md |
| Deployment checklist | 30-ops.md | Overview in AGENTS.md |
| Fabrik Skills | AGENTS.md | 90-automation.md |
| Watchdog template | templates/scripts/ | 30-ops.md (reference) |
| Dockerfile templates | templates/dockerfile/ | 30-ops.md (reference) |

---

## 4. Shared Enforcement Script (Consensus)

### API Design

```python
# scripts/enforcement/validate_conventions.py

class ConventionChecker:
    def check(self, context: dict) -> CheckResult:
        """
        Returns CheckResult:
        - severity: pass | warn | error
        - message: Human-readable description
        - fix_hint: Optional auto-fix suggestion
        """

    def fix(self, context: dict) -> bool:
        """Auto-fix if possible, return success status"""

# Exit codes
# 0 = pass (all checks passed)
# 1 = warn (issues found but non-blocking)
# 2 = block (critical violation, stop action)
```

### Checks to Implement

| Check | Severity | What It Does |
|-------|----------|--------------|
| `check_env_vars.py` | error | Detects hardcoded localhost/127.0.0.1 |
| `check_secrets.py` | error | Finds hardcoded passwords/keys |
| `check_health.py` | error | Verifies health endpoint tests deps |
| `check_docker.py` | error | Validates base image, healthcheck |
| `check_ports.py` | warn | Checks port against PORTS.md |

### Integration Points

```yaml
# Windsurf hooks.json
{
  "hooks": {
    "pre_write_code": [{
      "command": "python /opt/fabrik/scripts/enforcement/validate_conventions.py",
      "show_output": true
    }]
  }
}

# droid hooks (in ~/.factory/settings.json)
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{
        "type": "command",
        "command": "/opt/fabrik/scripts/enforcement/validate_conventions.py"
      }]
    }]
  }
}
```

---

## 5. Size Budgets (Enforced)

| File | Target | Max | Violation Action |
|------|--------|-----|-----------------|
| AGENTS.md | 17KB | 20KB | CI fails |
| 00-critical.md | 7KB | 8KB | CI fails |
| 10-python.md | 7KB | 8KB | CI fails |
| 20-typescript.md | 5KB | 6KB | CI fails |
| 30-ops.md | 9KB | 10KB | CI fails |
| 90-automation.md | 4KB | 5KB | CI fails |

### CI Size Check

```bash
# .github/workflows/check-rules-size.yml
- name: Check rule file sizes
  run: |
    for file in .windsurf/rules/*.md AGENTS.md; do
      size=$(wc -c < "$file")
      if [ "$size" -gt 12000 ]; then
        echo "ERROR: $file is $size bytes (max 12000)"
        exit 1
      fi
    done
```

---

## 6. Migration Plan (Phased)

### Week 1: Foundation

```bash
# Create directory structure
mkdir -p /opt/fabrik/.windsurf/rules
mkdir -p /opt/fabrik/scripts/enforcement
mkdir -p /opt/fabrik/templates/{dockerfile,compose,scripts}

# Create enforcement skeleton
touch scripts/enforcement/validate_conventions.py
touch scripts/enforcement/check_env_vars.py
touch scripts/enforcement/check_secrets.py
touch scripts/enforcement/check_health.py
touch scripts/enforcement/check_docker.py
touch scripts/enforcement/check_ports.py

# Extract templates from .windsurfrules
# → Move Dockerfile templates to templates/dockerfile/
# → Move compose.yaml template to templates/compose/
# → Move watchdog script to templates/scripts/
```

### Week 2: Content Split

1. Create `00-critical.md` with command tiers, protocols, ports
2. Create `10-python.md` with FastAPI patterns
3. Create `20-typescript.md` with Next.js patterns
4. Create `30-ops.md` with deployment content
5. Create `90-automation.md` with droid integration
6. Update AGENTS.md - remove Windsurf-specific content

### Week 3: Validation

1. Test in sandbox project
2. Verify Windsurf glob matching works
3. Implement enforcement script logic
4. Run parallel (new + old) for testing

### Week 4: Rollout

1. Update symlinks in pilot projects (3)
2. Document learnings
3. Remove legacy `.windsurfrules`
4. Update remaining projects

---

## 7. Risk Mitigation (From All Models)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Windsurf glob support missing | Medium | High | Fallback: concatenation script |
| Context fragmentation | Low | Medium | 00-critical.md links to others |
| Size creep over time | High | High | CI size checks, quarterly audits |
| Enforcement script drift | Medium | High | Shared test suite |
| Symlink issues in WSL | Low | Low | Use absolute paths |

---

## 8. Scalability (20+ Projects)

1. **Symlinks propagate updates:**
   - `/opt/fabrik/AGENTS.md` → Project `AGENTS.md`
   - `/opt/fabrik/.windsurf/` → Project `.windsurf/`

2. **Centralized enforcement:**
   - Single script in /opt/fabrik/scripts/enforcement/
   - Updates apply to all projects immediately

3. **CI guardrails:**
   - Size checks prevent bloat
   - Quarterly audits catch drift

---

## 9. Critical Content Preservation Checklist

✅ Command execution tiers (A/B/C) → 00-critical.md
✅ Port management conventions → 00-critical.md
✅ TWO-PLACE credential storage → AGENTS.md (canonical) + 00-critical.md
✅ Service watchdog template → templates/scripts/watchdog.sh
✅ Compliance checklist (14 items) → 30-ops.md
✅ Dockerfile/compose templates → templates/
✅ When-stuck protocol → 00-critical.md
✅ Before-writing-code protocol → 00-critical.md
✅ Container base image standards → 30-ops.md
✅ Microservice URL conventions → 30-ops.md
✅ Agent readiness checklist → AGENTS.md
✅ Execution modes table → AGENTS.md
✅ Documentation rules → AGENTS.md
✅ Fabrik Skills → AGENTS.md + 90-automation.md
✅ Dual-model code review → 90-automation.md
✅ CSPRNG password policy → AGENTS.md

---

## 10. Next Steps

**Ready to implement when you approve.**

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Foundation | 2 hours | Directory structure + skeleton scripts |
| Content Split | 4 hours | 5 rule files + updated AGENTS.md |
| Enforcement | 3 hours | validate_conventions.py + checks |
| Testing | 2 hours | Pilot project validation |
| Rollout | 1 hour | Symlink updates + legacy removal |

**Total: ~12 hours of implementation work**

---

## Approval

This strategy has been reviewed and approved by three independent AI models with high reasoning. All models agree on:

1. ✅ Four-level architecture
2. ✅ 5 rule files with glob triggers
3. ✅ AGENTS.md as canonical source
4. ✅ Shared enforcement scripts
5. ✅ Size budgets with CI enforcement
6. ✅ Phased migration approach

**Proceed with confidence.**
