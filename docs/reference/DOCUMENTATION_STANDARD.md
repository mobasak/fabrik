# Documentation Standard

Global documentation standard for all projects under `/opt/`.

**Version:** 1.0.0
**Last Updated:** 2025-12-03
**Enforced By:** Windsurf Cascade Global Rules

---

## Overview

This standard defines the required documentation structure, naming conventions, and organization for all projects. Windsurf Cascade will automatically enforce these rules.

---

## Required Project Structure

Every project under `/opt/` MUST have:

```
/opt/<project>/
├── README.md                    # REQUIRED: Project overview
├── CHANGELOG.md                 # REQUIRED: Version history
│
├── docs/                        # REQUIRED: Documentation folder
│   ├── README.md                # REQUIRED: Docs index
│   ├── QUICKSTART.md            # REQUIRED: Getting started
│   ├── CONFIGURATION.md         # REQUIRED: Settings reference
│   ├── TROUBLESHOOTING.md       # REQUIRED: Common issues
│   │
│   ├── guides/                  # How-to guides
│   ├── reference/               # Technical reference
│   ├── operations/              # Operational docs
│   ├── development/             # Contributor docs
│   └── archive/                 # Obsolete docs (dated)
│
├── .factory/                    # AI agent context (optional)
│   └── context.md
│
└── .ops/                        # Operational runbooks (optional)
    └── runbooks/
```

---

## File Naming Conventions

### Root-Level Files (UPPERCASE)

| File | Purpose | Required |
|------|---------|----------|
| `README.md` | Project overview | ✅ Yes |
| `CHANGELOG.md` | Version history | ✅ Yes |
| `AGENTS.md` | AI agent context | Optional |
| `LICENSE.md` | License info | Optional |
| `CONTRIBUTING.md` | Contribution guide | Optional |

### docs/ Files (UPPERCASE for required, lowercase for others)

| File | Purpose | Required |
|------|---------|----------|
| `README.md` | Documentation index | ✅ Yes |
| `QUICKSTART.md` | 5-minute setup | ✅ Yes |
| `CONFIGURATION.md` | All settings | ✅ Yes |
| `TROUBLESHOOTING.md` | Common issues | ✅ Yes |

### Guide/Reference Files (lowercase-kebab-case)

```
docs/guides/installation.md
docs/guides/deployment.md
docs/reference/api-reference.md
docs/reference/cli-commands.md
```

### Archive Files (dated)

```
docs/archive/2025-12-03-migration-plan/
docs/archive/2025-11-15-old-feature/
```

---

## Documentation Categories

### guides/ - How-To Guides

Task-oriented documentation. "How do I...?"

- `installation.md` - Full installation
- `deployment.md` - Production deployment
- `usage.md` - Daily usage patterns

### reference/ - Technical Reference

Information-oriented documentation. "What is...?"

- `api.md` - API documentation
- `cli.md` - CLI commands
- `database.md` - Schema reference
- `architecture.md` - System design

### operations/ - Operational Docs

Procedure-oriented documentation. "How to maintain...?"

- `monitoring.md` - Health checks
- `backup-recovery.md` - Data protection
- `maintenance.md` - Regular tasks

### development/ - Developer Docs

Contribution-oriented documentation. "How to contribute...?"

- `contributing.md` - Contribution guide
- `testing.md` - Test procedures
- `code-style.md` - Coding standards

### archive/ - Obsolete Docs

Historical documentation preserved for reference.

**When to archive:**
- Document unchanged >90 days
- Feature deprecated
- Implementation complete
- Superseded by newer doc

**Archive format:**
```
archive/YYYY-MM-DD-topic-name/
├── README.md
└── [related files]
```

---

## Content Standards

### README.md Requirements

1. **Title** - Project name as H1
2. **Badges** - Status, version, etc.
3. **Overview** - 2-3 sentence description
4. **Features** - Bullet list of key features
5. **Quick Start** - Minimal getting started
6. **Documentation Links** - Table of docs
7. **Project Structure** - Directory tree
8. **Configuration** - Key settings
9. **Requirements** - Prerequisites
10. **License** - License info

### CHANGELOG.md Format

Use [Keep a Changelog](https://keepachangelog.com/) format:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing features

### Fixed
- Bug fixes

### Removed
- Removed features
```

### Code Blocks

Always specify language:

```python
# Good
def example():
    pass
```

Not:
```
# Bad - no language specified
def example():
    pass
```

---

## Forbidden Patterns

### ❌ Do NOT:

1. **Scatter MD files in root** - Max 5-7 root MD files
2. **Use misc/ for docs** - Use proper docs/ structure
3. **Mix naming conventions** - Pick one, stick to it
4. **Create deep nesting** - Max 3 levels in docs/
5. **Leave orphan docs** - All docs must be linked
6. **Duplicate READMEs** - One README per folder

### ❌ Avoid These Names:

- `todo.md` → Use issue tracker
- `notes.md` → Use proper category
- `temp.md` → Delete or archive
- `test.md` → Put in tests/
- `old_*.md` → Move to archive/

---

## Templates

Templates are available at:

```
/opt/fabrik/templates/docs/
├── PROJECT_README_TEMPLATE.md
├── DOCS_INDEX_TEMPLATE.md
├── CHANGELOG_TEMPLATE.md
├── QUICKSTART_TEMPLATE.md
└── TROUBLESHOOTING_TEMPLATE.md
```

Use templates when creating new documentation.

---

## Enforcement

This standard is enforced by Windsurf Cascade via:

1. **Global Rules** - `~/.windsurfrules`
2. **Project Rules** - `/opt/<project>/.windsurfrules`

Cascade will:
- Remind you of the standard when creating docs
- Suggest proper file locations
- Warn about naming violations
- Recommend archiving old docs

---

## Migrating Existing Projects

### Step-by-Step Workflow

When migrating an existing project to this standard:

**Step 1: Load Rules (if session already open)**

If Cascade is already running in the project, paste:

```
Read and follow the rules in .windsurfrules for all future responses in this session.
```

**Step 2: Request Analysis (Don't change yet)**

Ask Cascade:

```
Analyze the current documentation structure and create a migration plan
to match the documentation standard. Don't make changes yet, just show me the plan.
```

**Step 3: Review the Plan**

Cascade will show:
- What files exist vs what's required
- What needs to be created
- What should be moved/reorganized
- What should be archived

**Step 4: Execute in Phases**

| Phase | Action | Risk |
|-------|--------|------|
| 1 | Create missing required files | Safe - adds new files |
| 2 | Create docs/ subfolders | Safe - adds structure |
| 3 | Update docs/INDEX.md index | Safe - new content |
| 4 | Move files to proper locations | Medium - confirm each |
| 5 | Archive obsolete docs | Medium - review list first |
| 6 | Remove duplicates | High - explicit approval only |

**Step 5: Verify**

```
Verify the documentation structure matches the standard. List any gaps.
```

---

## Migration Checklist

For existing projects:

- [ ] Create `docs/` folder if missing
- [ ] Add `docs/INDEX.md` index
- [ ] Add `docs/QUICKSTART.md`
- [ ] Add `docs/CONFIGURATION.md`
- [ ] Add `docs/TROUBLESHOOTING.md`
- [ ] Add root `CHANGELOG.md`
- [ ] Move scattered MD files to proper locations
- [ ] Archive obsolete docs with dates
- [ ] Update all internal links
- [ ] Remove duplicate README variations
