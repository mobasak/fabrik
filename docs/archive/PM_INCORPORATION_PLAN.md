> ⚠️ **ARCHIVED DOCUMENT** — This migration plan has been completed. Kept for historical reference.

# PM → Fabrik Incorporation Plan

**Created:** 2025-12-27

---

## Summary

Merge `/opt/_project_management` into Fabrik. After merge, `_project_management` becomes obsolete.

---

## What Moves to Fabrik

| From PM | To Fabrik | Action |
|---------|-----------|--------|
| `windsurfrules` | `fabrik/windsurfrules` | Move, update symlinks |
| `PORTS.md` | `fabrik/data/ports.yaml` | Convert to YAML |
| `scripts/create-project.sh` | `fabrik new --scaffold` | Rewrite as CLI |
| `scripts/validate-project.sh` | `fabrik validate` | Rewrite as CLI |
| `templates/docs/*` | `fabrik/templates/scaffold/docs/` | Move |
| `templates/docker/*` | `fabrik/templates/scaffold/docker/` | Move |
| `droid-exec-usage.md` | `fabrik/docs/reference/` | Already there |
| `docs/DOCUMENTATION_STANDARD.md` | `fabrik/docs/reference/` | Move |

---

## New CLI Commands

```bash
# Replace create-project.sh
fabrik new my-project --scaffold  # Full project structure
fabrik new my-project --template python-api  # Service template (existing)

# Replace validate-project.sh
fabrik validate /opt/my-project

# Replace migrate-project.sh
fabrik migrate /opt/my-project
```

---

## Phase Plan

### Phase 1: Move Assets (Safe)
1. Copy `windsurfrules` to `/opt/fabrik/windsurfrules`
2. Copy `templates/docs/*` to `/opt/fabrik/templates/scaffold/docs/`
3. Copy `templates/docker/*` to `/opt/fabrik/templates/scaffold/docker/`
4. Move `PORTS.md` → convert to `data/ports.yaml`
5. Copy key docs to `fabrik/docs/reference/`

### Phase 2: Implement CLI Commands
1. Add `fabrik new --scaffold` (replaces create-project.sh)
2. Add `fabrik validate` (replaces validate-project.sh)
3. Add `fabrik migrate` (replaces migrate-project.sh)

### Phase 3: Update Symlinks
1. Update all project `.windsurfrules` symlinks to point to fabrik
2. Test that Cascade still reads rules correctly

### Phase 4: Deprecate _project_management
1. Add deprecation notice to PM's README
2. After 2 weeks, archive to `_project_management_archive`

---

## Files to Keep in PM (Legacy)

- `legacy/` - Historical checkpoint system
- `scripts/rund`, `rundsh`, `runc`, `runk` - Keep symlinked to ~/.local/bin

---

## Detailed Asset Mapping

### windsurfrules Content Sections

| Section | Keep | Modify |
|---------|------|--------|
| Environment Context | ✅ | Update paths to fabrik |
| Target Deployment Environments | ✅ | No change |
| Droid exec rules | ✅ | Update doc path |
| Project Setup Requirements | ✅ | No change |
| Credentials Management | ✅ | No change (already refs fabrik) |
| Forbidden /tmp rules | ✅ | No change |

### Port Registry → YAML

**From `PORTS.md`:**
```markdown
| Port | Project | Service |
| 8002 | proposal-creator | FastAPI |
```

**To `data/ports.yaml`:**
```yaml
ports:
  development:
    5432: { project: shared, service: PostgreSQL }
    8002: { project: proposal-creator, service: FastAPI }
  production:
    80: { project: coolify, service: HTTP proxy }
```

### Template Directory Structure

```
/opt/fabrik/templates/
├── scaffold/              # NEW: Project scaffolding
│   ├── docs/              # From PM templates/docs/
│   │   ├── PROJECT_README.md
│   │   ├── CHANGELOG.md
│   │   ├── QUICKSTART.md
│   │   └── ...
│   ├── docker/            # From PM templates/docker/
│   │   ├── Dockerfile.python
│   │   ├── compose.yaml
│   │   └── ...
│   └── python/            # From PM templates/python/
│       └── pyproject.toml
├── python-api/            # Existing service templates
├── wordpress/
└── ...
```

---

## Implementation Estimate

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Move Assets | 1 hour | Low |
| Phase 2: CLI Commands | 2-3 hours | Medium |
| Phase 3: Update Symlinks | 30 min | Low |
| Phase 4: Deprecate | 5 min | None |

**Total: ~4 hours**

---

## Benefits After Merge

1. **Single source of truth** - All dev tooling in one place
2. **Unified CLI** - `fabrik` handles everything
3. **Better discovery** - `fabrik --help` shows all capabilities
4. **Simpler maintenance** - One project to update
5. **Integrated registry** - `fabrik projects` shows all, `fabrik new` creates new
