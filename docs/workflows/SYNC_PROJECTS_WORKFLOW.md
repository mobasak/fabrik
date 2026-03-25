# Sync Projects Workflow

**Last Updated:** 2026-03-25
**Status:** PRODUCTION
**Script:** `scripts/sync_projects.py`
**Source Code:** `src/fabrik/cli.py` → `fabrik scan` command
**Outputs:**
- `data/projects.yaml` (aggregated registry, machine-readable)
- `docs/BUSINESS_MODEL.md` (AUTO-GENERATED:PROJECTS block, human-readable)

> **Coders:** When modifying `scripts/sync_projects.py`, update this workflow doc to match.

---

## Overview

Scans all `/opt/*` projects and builds a unified project catalog. The **primary source of truth** is each project's `project.yaml` file (created by `fabrik scaffold`). For projects without `project.yaml`, metadata is auto-detected from the filesystem.

### Data Flow

```
/opt/<project>/project.yaml   ──┐
                                 ├──→ scripts/sync_projects.py ──→ data/projects.yaml (registry)
Auto-detection (README, stack)  ──┘                             └──→ docs/BUSINESS_MODEL.md (catalog)
```

---

## Source of Truth: `project.yaml`

Each project under `/opt/` has a `project.yaml` file:

```yaml
# Project metadata — source of truth
name: captcha
type: python-api
description: Anti-captcha solving service
created: '2026-03-25'
status: production
category: production
url: https://captcha.vps1.ocoron.com
domain: captcha.vps1.ocoron.com
ports: [18011]
external_systems: [anti-captcha-api]
monthly_cost: 5
dependencies: [proxy]
tags: [scraping, automation]
```

### Schema Fields

| Field | Type | Values | Source |
|-------|------|--------|--------|
| **name** | string | — | Directory name |
| **type** | string | `python-api`, `node-api`, `saas-skeleton`, `wordpress`, etc. | Scaffold type |
| **description** | string | — | README or user-provided |
| **created** | date | `YYYY-MM-DD` | Scaffold date |
| **status** | string | `development`, `ready`, `production`, `archived` | Owner sets |
| **category** | string | `production`, `active`, `planning`, `shell` | Auto or owner |
| **url** | string | — | Deployment URL |
| **domain** | string | — | Domain name |
| **ports** | list[int] | Host ports this project binds (must be unique across `/opt`) | Auto-allocated by scaffold |
| **external_systems** | list | e.g. `supabase`, `stripe`, `cloudflare-r2` | Owner sets |
| **monthly_cost** | float | USD/month | Owner sets |
| **dependencies** | list | Other `/opt` project names | Owner sets |
| **tags** | list | Free-form labels | Owner sets |

---

## What Gets Extracted

### Per-Project Metadata

| Field | Primary Source | Fallback (auto-detect) |
|-------|---------------|----------------------|
| **Name** | Directory name | — |
| **Description** | `project.yaml → description` | README.md `## Overview` |
| **Stack** | Auto-detected always | `compose.yaml`, `pyproject.toml`, `package.json` |
| **Status** | `project.yaml → status` | "🔨 Development" |
| **URL** | `project.yaml → url` | None |
| **Category** | `project.yaml → category` | Heuristic (see below) |
| **Scaffold** | `.windsurfrules` + `project.yaml` check | — |

### Stack Detection

```
compose.yaml services → PostgreSQL, Redis
pyproject.toml deps   → FastAPI, Flask, Python
package.json deps     → Express, Fastify, Node.js
wp-config.php         → WordPress
```

### Auto-Categorization (when no project.yaml)

| Category | Criteria |
|----------|----------|
| **Production** | status = `production` |
| **Active** | Has `compose.yaml` + `src/` or `app/` directory |
| **Planning** | Has `README.md` or `docs/` |
| **Shell** | Empty scaffold only |

---

## Deletion Detection

On each scan, the script compares current `/opt/*` projects against the previous `data/projects.yaml`. Deleted projects appear in a **"Recently Removed"** section in BUSINESS_MODEL.md. This is non-destructive — the old registry entry is simply no longer present.

---

## CLI Usage

```bash
# Via Fabrik CLI (recommended)
fabrik scan

# Direct script execution
python scripts/sync_projects.py
```

---

## Output Format

### Registry (`data/projects.yaml`)

```yaml
version: 2
last_scan: '2026-03-25T12:06:40.175192'
total_projects: 39
projects:
  captcha:
    path: /opt/captcha
    type: python-api
    description: Anti-captcha solving service
    status: ✅ Production
    category: production
    stack: FastAPI + Redis
    scaffold_status: ✅ Current
    created: '2026-03-25'
    url: https://captcha.vps1.ocoron.com
    ports:
    - 18011
```

### Catalog (`docs/BUSINESS_MODEL.md`)

Updates the `<!-- AUTO-GENERATED:PROJECTS:START -->` block:

```markdown
### Production Services (5 projects)

| Project | Purpose | Stack | Status | URL | Scaffold |
|---------|---------|-------|--------|-----|----------|
| **captcha** | Anti-captcha solving | FastAPI + Redis | ✅ Production | https://... | ✅ Current |

### Recently Removed (1 projects)

| Project | Note |
|---------|------|
| ~~old-project~~ | Folder deleted since last scan |
```

---

## When to Run

| Trigger | How |
|---------|-----|
| After `fabrik scaffold` | **Automatically** via `_post_scaffold_sync()` hook in `scaffold.py` |
| Manual refresh | `fabrik scan` or `python scripts/sync_projects.py` |
| After deleting a project | `fabrik scan` to detect removal |

---

## Scaffold Compliance Check

| Status | Meaning |
|--------|---------|
| ✅ Current | `.windsurfrules` exists (copy) AND `project.yaml` exists |
| ⚠️ No project.yaml | `.windsurfrules` exists but no `project.yaml` |
| ⚠️ Needs update (symlink) | `.windsurfrules` is a symlink (should be copy) |
| ❌ No scaffold | `.windsurfrules` missing entirely |

---

## Excluded Directories

Pattern matching via `fnmatch`:
- `_*` — staging areas
- `.*` — hidden directories
- `fabrik` — Fabrik itself (the tool, not a project)
- `__pycache__`, `venv`, `google` — system/tool dirs

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Registry + catalog updated successfully |
| 1 | Failed to update BUSINESS_MODEL.md |

---

## Related Workflows

- [Fabrik Scaffold Workflow](FABRIK_SCAFFOLD_WORKFLOW.md) — Creates new projects with `project.yaml`
- [Sync Enforcement Workflow](SYNC_ENFORCEMENT_WORKFLOW.md) — Syncs scripts/rules to projects
