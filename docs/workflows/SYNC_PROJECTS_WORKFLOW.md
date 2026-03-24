# Sync Projects Workflow

**Last Updated:** 2026-03-24
**Status:** PRODUCTION
**Script:** `scripts/sync_projects.py`
**Output:** `docs/BUSINESS_MODEL.md` (AUTO-GENERATED:PROJECTS block)

## Overview

Scans all `/opt/*` projects and generates a live project catalog in `docs/BUSINESS_MODEL.md`. Extracts metadata from README files, detects tech stacks, and checks scaffold compliance.

---

## What Gets Extracted

### Per-Project Metadata

| Field | Source | Example |
|-------|--------|---------|
| **Name** | Directory name | `captcha` |
| **Purpose** | README.md `## Overview` | "Anti-captcha solving service" |
| **Stack** | `compose.yaml`, `pyproject.toml`, `package.json` | "FastAPI + PostgreSQL" |
| **Status** | Known production URLs | "✅ Production" or "🔨 Development" |
| **URL** | Hardcoded mapping | `https://captcha.vps1.ocoron.com` |
| **Scaffold Status** | `.windsurfrules` local copy check | "✅ Current" or "❌ No scaffold" |

### Stack Detection

```
compose.yaml services → PostgreSQL, Redis
pyproject.toml deps → FastAPI, Flask, Python
package.json deps → Express, Fastify, Node.js
wp-config.php → WordPress
```

### Project Categories

| Category | Criteria |
|----------|----------|
| **Production** | Has known production URL |
| **Active** | Has compose.yaml + src/app directory |
| **Planning** | Has README or docs/ |
| **Shell** | Empty scaffold only |

---

## CLI Usage

```bash
# Scan and update BUSINESS_MODEL.md
python scripts/sync_projects.py
```

---

## Output Format

The script updates the `<!-- AUTO-GENERATED:PROJECTS:START -->` block in `docs/BUSINESS_MODEL.md`:

```markdown
<!-- Last synced: 2026-03-24 17:30:00 -->
<!-- Total projects: 39 -->

### Production Services (5 projects)

| Project | Purpose | Stack | Status | URL | Scaffold Status |
|---------|---------|-------|--------|-----|------------------|
| **captcha** | Anti-captcha solving | FastAPI + Redis | ✅ Production | https://captcha.vps1.ocoron.com | ✅ Current |
| **translator** | DeepL + Azure translation | FastAPI | ✅ Production | https://translator.vps1.ocoron.com | ✅ Current |

### Active Development (15 projects)

| Project | Purpose | Stack | Status | URL | Scaffold Status |
|---------|---------|-------|--------|-----|------------------|
| **fabrik** | Development toolkit | Python | 🔨 Development | - | ✅ Current |
...
```

---

## When to Run

| Trigger | How |
|---------|-----|
| After `fabrik scaffold` | Automatically via post-scaffold hook |
| After project changes | `python scripts/sync_projects.py` |
| Weekly cleanup | Manual run to update statuses |

---

## Scaffold Compliance Check

Checks `.windsurfrules` in each project:

| Status | Meaning |
|--------|---------|
| ✅ Current | `.windsurfrules` is local copy (not symlink) |
| ⚠️ Needs update | `.windsurfrules` content differs from Fabrik source |
| ❌ No scaffold | `.windsurfrules` missing |

---

## Excluded Directories

- `_*` prefixed (staging areas)
- `/opt/fabrik` (source, not a "project")

---

## Known Production URLs

Hardcoded in script (update when deploying new services):

```python
production_urls = {
    "captcha": "https://captcha.vps1.ocoron.com",
    "dns-manager": "https://dns.vps1.ocoron.com",
    "file-api": "https://files-api.vps1.ocoron.com",
    "translator": "https://translator.vps1.ocoron.com",
}
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Catalog updated successfully |
| 1 | Failed to update BUSINESS_MODEL.md |

---

## Related Workflows

- [Fabrik Scaffold Workflow](FABRIK_SCAFFOLD_WORKFLOW.md) — Creates new projects
- [Sync Enforcement Workflow](SYNC_ENFORCEMENT_WORKFLOW.md) — Syncs scripts to projects
