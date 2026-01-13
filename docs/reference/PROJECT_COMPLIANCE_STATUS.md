# Project Compliance Status

**Generated:** 2026-01-13
**Purpose:** Guide for Cascade agents to make projects Fabrik-compliant

---

## Compliance Summary

| Project | .windsurfrules | AGENTS.md | trajectories/ | pre-commit | backup.sh | .windsurf/rules/ |
|---------|----------------|-----------|---------------|------------|-----------|------------------|
| captcha | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| dns-manager | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| emailgateway | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| file-api | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| file-worker | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| _final-verify | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| image-broker | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| _project_management | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| proposal-creator | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| proxy | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| translator | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| youtube | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |

---

## Instructions for Cascade Agent

When you open a project from this list, execute these commands to make it Fabrik-compliant:

### Step 1: Check Current Status
```bash
# Run from project root
echo "=== Compliance Check ==="
echo ".windsurfrules: $([ -e .windsurfrules ] && echo 'EXISTS' || echo 'MISSING')"
echo "AGENTS.md: $([ -f AGENTS.md ] && echo 'EXISTS' || echo 'MISSING')"
echo "docs/trajectories/: $([ -d docs/trajectories ] && echo 'EXISTS' || echo 'MISSING')"
echo ".pre-commit-config.yaml: $([ -f .pre-commit-config.yaml ] && echo 'EXISTS' || echo 'MISSING')"
echo "scripts/sync_cascade_backup.sh: $([ -f scripts/sync_cascade_backup.sh ] && echo 'EXISTS' || echo 'MISSING')"
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
**Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### dns-manager
**Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### emailgateway
**Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### file-api
**Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### file-worker
**Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### _final-verify
**Missing:** ALL components
```bash
ln -s /opt/fabrik/windsurfrules .windsurfrules
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### image-broker
**Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### _project_management
**Missing:** ALL components
```bash
ln -s /opt/fabrik/windsurfrules .windsurfrules
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### proposal-creator
**Missing:** AGENTS.md, docs/trajectories/, scripts/sync_cascade_backup.sh
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### proxy
**Missing:** docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
```bash
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### translator
**Missing:** AGENTS.md, docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
```bash
cp /opt/fabrik/templates/scaffold/AGENTS.md .
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

### youtube
**Missing:** docs/trajectories/, .pre-commit-config.yaml, scripts/sync_cascade_backup.sh
```bash
mkdir -p docs/trajectories scripts
cp /opt/fabrik/templates/scaffold/pre-commit-config.yaml .pre-commit-config.yaml
cp /opt/fabrik/scripts/sync_cascade_backup.sh scripts/
cp /opt/fabrik/scripts/sync_extensions.sh scripts/
chmod +x scripts/*.sh
```

---

## Verification After Compliance

Run this to verify full compliance:
```bash
echo "=== Final Compliance Check ==="
[ -e .windsurfrules ] && echo "✅ .windsurfrules" || echo "❌ .windsurfrules"
[ -f AGENTS.md ] && echo "✅ AGENTS.md" || echo "❌ AGENTS.md"
[ -d docs/trajectories ] && echo "✅ docs/trajectories/" || echo "❌ docs/trajectories/"
[ -f .pre-commit-config.yaml ] && echo "✅ .pre-commit-config.yaml" || echo "❌ .pre-commit-config.yaml"
[ -f scripts/sync_cascade_backup.sh ] && echo "✅ scripts/sync_cascade_backup.sh" || echo "❌ scripts/sync_cascade_backup.sh"
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
