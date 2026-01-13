# Project Compliance Status

**Generated:** 2026-01-13
**Purpose:** Guide for Cascade agents to make projects Fabrik-compliant

---

## Compliance Summary

### Infrastructure Files

| Project | .windsurfrules | AGENTS.md | trajectories/ | pre-commit | backup.sh |
|---------|----------------|-----------|---------------|------------|-----------|
| captcha | ✅ | ❌ | ❌ | ❌ | ❌ |
| dns-manager | ✅ | ❌ | ❌ | ❌ | ❌ |
| emailgateway | ✅ | ❌ | ❌ | ❌ | ❌ |
| file-api | ✅ | ❌ | ❌ | ❌ | ❌ |
| file-worker | ✅ | ❌ | ❌ | ❌ | ❌ |
| _final-verify | ❌ | ❌ | ❌ | ❌ | ❌ |
| image-broker | ✅ | ❌ | ❌ | ❌ | ❌ |
| _project_management | ❌ | ❌ | ❌ | ❌ | ❌ |
| proposal-creator | ✅ | ❌ | ❌ | ✅ | ❌ |
| proxy | ✅ | ✅ | ❌ | ❌ | ❌ |
| translator | ✅ | ❌ | ❌ | ❌ | ❌ |
| youtube | ✅ | ✅ | ❌ | ❌ | ❌ |

### Documentation Files (REQUIRED for AI Understanding)

| Project | README.md | CHANGELOG.md | docs/ | docs/INDEX.md |
|---------|-----------|--------------|-------|---------------|
| captcha | ✅ | ✅ | ✅ | ❌ |
| dns-manager | ✅ | ✅ | ✅ | ❌ |
| emailgateway | ✅ | ✅ | ✅ | ❌ |
| file-api | ✅ | ❌ | ❌ | ❌ |
| file-worker | ❌ | ❌ | ❌ | ❌ |
| _final-verify | ✅ | ❌ | ❌ | ❌ |
| image-broker | ✅ | ✅ | ✅ | ❌ |
| _project_management | ✅ | ❌ | ✅ | ❌ |
| proposal-creator | ✅ | ✅ | ✅ | ❌ |
| proxy | ✅ | ✅ | ✅ | ❌ |
| translator | ✅ | ✅ | ✅ | ❌ |
| youtube | ✅ | ✅ | ✅ | ❌ |

---

## Instructions for Cascade Agent

When you open a project from this list, execute these commands to make it Fabrik-compliant:

### Step 1: Check Current Status
```bash
# Run from project root
echo "=== Infrastructure Check ==="
echo ".windsurfrules: $([ -e .windsurfrules ] && echo 'EXISTS' || echo 'MISSING')"
echo "AGENTS.md: $([ -f AGENTS.md ] && echo 'EXISTS' || echo 'MISSING')"
echo "docs/trajectories/: $([ -d docs/trajectories ] && echo 'EXISTS' || echo 'MISSING')"
echo ".pre-commit-config.yaml: $([ -f .pre-commit-config.yaml ] && echo 'EXISTS' || echo 'MISSING')"
echo "scripts/sync_cascade_backup.sh: $([ -f scripts/sync_cascade_backup.sh ] && echo 'EXISTS' || echo 'MISSING')"

echo ""
echo "=== Documentation Check (REQUIRED for AI Understanding) ==="
echo "README.md: $([ -f README.md ] && echo 'EXISTS' || echo 'MISSING')"
echo "CHANGELOG.md: $([ -f CHANGELOG.md ] && echo 'EXISTS' || echo 'MISSING')"
echo "docs/: $([ -d docs ] && echo 'EXISTS' || echo 'MISSING')"
echo "docs/INDEX.md: $([ -f docs/INDEX.md ] && echo 'EXISTS' || echo 'MISSING')"
```

### Step 2: Add Missing Components

**If .windsurfrules is MISSING:**
```bash
ln -s /opt/fabrik/windsurfrules .windsurfrules
```

**If AGENTS.md is MISSING:**
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
```

**If docs/trajectories/ is MISSING:**
```bash
mkdir -p docs/trajectories
```

**If .pre-commit-config.yaml is MISSING:**
```bash
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
```

**If scripts/sync_cascade_backup.sh is MISSING:**
```bash
mkdir -p scripts
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
chmod +x scripts/sync_cascade_backup.sh
```

**If scripts/sync_extensions.sh is MISSING:**
```bash
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/sync_extensions.sh
```

### Step 2b: Add Missing Documentation (CRITICAL for AI Understanding)

**If README.md is MISSING or incomplete, CREATE/UPDATE it with this structure:**
```markdown
# Project Name

**Purpose:** One-line description of what this project does

## Quick Start
\`\`\`bash
# How to run locally
\`\`\`

## Architecture
- What components exist
- How they interact

## Configuration
- Environment variables required
- Config files

## Deployment
- How to deploy to production
```

**If CHANGELOG.md is MISSING:**
```bash
cat > CHANGELOG.md << 'EOF'
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Initial Fabrik compliance (YYYY-MM-DD)
EOF
```

**If docs/ folder is MISSING:**
```bash
mkdir -p docs
```

**If docs/INDEX.md is MISSING, CREATE it:**
```markdown
# Documentation Index

**Last Updated:** YYYY-MM-DD

## Structure

- `README.md` - Project overview and quick start
- `CHANGELOG.md` - Version history
- `AGENTS.md` - AI agent instructions

## docs/
- (list documentation files here as they are created)
```

### Step 2c: Update README.md to be AI-Readable

**Read the existing README.md and ensure it answers these questions:**

1. **What does this project do?** (Purpose in first paragraph)
2. **How do I run it locally?** (Quick start commands)
3. **What environment variables are needed?** (Configuration section)
4. **What are the main components?** (Architecture section)
5. **How is it deployed?** (Deployment section)

**If any of these are missing, ADD them to README.md.**

### Step 3: Check for Rule Violations

```bash
# Check for /tmp/ usage (forbidden)
grep -r "/tmp/" --include="*.py" --include="*.sh" . 2>/dev/null | grep -v ".git" | head -10

# Check for hardcoded localhost (should use os.getenv)
grep -r "localhost" --include="*.py" . 2>/dev/null | grep -v ".git" | grep -v "# " | head -10

# Check for tempfile module usage (should use project .tmp/)
grep -r "tempfile\." --include="*.py" . 2>/dev/null | grep -v ".git" | head -10
```

### Step 4: Fix Violations Found

**Replace /tmp/ with project .tmp/:**
```python
# WRONG
import tempfile
fd, path = tempfile.mkstemp()

# CORRECT
from pathlib import Path
project_tmp = Path(__file__).parent.parent / ".tmp"
project_tmp.mkdir(exist_ok=True)
path = project_tmp / f"file_{uuid.uuid4().hex}.txt"
```

**Replace hardcoded localhost:**
```python
# WRONG
DB_HOST = "localhost"

# CORRECT
DB_HOST = os.getenv("DB_HOST", "localhost")
```

### Step 5: Commit Changes
```bash
git add -A
git commit -m "Add Fabrik compliance: rules, AGENTS.md, backup hooks"
```

### Step 6: Before Closing Session
1. If this was a valuable session, download trajectory
2. Save to `docs/trajectories/YYYY-MM-DD-description.md`

---

## Per-Project Instructions

### captcha
**Infrastructure Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
**Docs Missing:** docs/INDEX.md
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### dns-manager
**Infrastructure Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
**Docs Missing:** docs/INDEX.md
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### emailgateway
**Infrastructure Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
**Docs Missing:** docs/INDEX.md
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### file-api
**Infrastructure Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
**Docs Missing:** CHANGELOG.md, docs/, docs/INDEX.md
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Create CHANGELOG.md. Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### file-worker
**Infrastructure Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
**Docs Missing:** README.md, CHANGELOG.md, docs/, docs/INDEX.md
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** CREATE README.md with Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create CHANGELOG.md. Create docs/INDEX.md.

### _final-verify
**Infrastructure Missing:** ALL components
**Docs Missing:** CHANGELOG.md, docs/, docs/INDEX.md
```bash
ln -s /opt/fabrik/windsurfrules .windsurfrules
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Create CHANGELOG.md. Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### image-broker
**Infrastructure Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
**Docs Missing:** docs/INDEX.md
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### _project_management
**Infrastructure Missing:** ALL components
**Docs Missing:** CHANGELOG.md, docs/INDEX.md
```bash
ln -s /opt/fabrik/windsurfrules .windsurfrules
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Create CHANGELOG.md. Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### proposal-creator
**Infrastructure Missing:** AGENTS.md, docs/trajectories/, scripts/sync_cascade_backup.sh
**Docs Missing:** docs/INDEX.md
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### proxy
**Infrastructure Missing:** docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
**Docs Missing:** docs/INDEX.md
```bash
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### translator
**Infrastructure Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
**Docs Missing:** docs/INDEX.md
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

### youtube
**Infrastructure Missing:** docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
**Docs Missing:** docs/INDEX.md
```bash
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```
**Then:** Read README.md and verify it has Purpose, Quick Start, Architecture, Configuration, Deployment sections. Create docs/INDEX.md.

---

## Verification After Compliance

Run this to verify full compliance:
```bash
echo "=== Infrastructure Check ==="
[ -e .windsurfrules ] && echo "✅ .windsurfrules" || echo "❌ .windsurfrules"
[ -f AGENTS.md ] && echo "✅ AGENTS.md" || echo "❌ AGENTS.md"
[ -d docs/trajectories ] && echo "✅ docs/trajectories/" || echo "❌ docs/trajectories/"
[ -f .pre-commit-config.yaml ] && echo "✅ .pre-commit-config.yaml" || echo "❌ .pre-commit-config.yaml"
[ -f scripts/sync_cascade_backup.sh ] && echo "✅ scripts/sync_cascade_backup.sh" || echo "❌ scripts/sync_cascade_backup.sh"

echo ""
echo "=== Documentation Check ==="
[ -f README.md ] && echo "✅ README.md" || echo "❌ README.md"
[ -f CHANGELOG.md ] && echo "✅ CHANGELOG.md" || echo "❌ CHANGELOG.md"
[ -d docs ] && echo "✅ docs/" || echo "❌ docs/"
[ -f docs/INDEX.md ] && echo "✅ docs/INDEX.md" || echo "❌ docs/INDEX.md"

echo ""
echo "=== README.md Content Check ==="
if [ -f README.md ]; then
  grep -q "Purpose\|purpose\|What.*does" README.md && echo "✅ Has Purpose" || echo "❌ Missing Purpose"
  grep -q "Quick Start\|Getting Started\|Installation" README.md && echo "✅ Has Quick Start" || echo "❌ Missing Quick Start"
  grep -q "Configuration\|Environment\|Config" README.md && echo "✅ Has Configuration" || echo "❌ Missing Configuration"
fi
```

---

## Reference Files in Fabrik

| File | Purpose |
|------|---------|
| `/opt/fabrik/windsurfrules` | Symlink target for .windsurfrules |
| `/opt/fabrik/templates/scaffold/AGENTS.md` | Template AGENTS.md for projects |
| `/opt/fabrik/templates/scaffold/pre-commit-config.yaml` | Template pre-commit config |
| `/opt/fabrik/scripts/sync_cascade_backup.sh` | Cascade backup freshness checker |
| `/opt/fabrik/scripts/sync_extensions.sh` | Extensions sync script |
