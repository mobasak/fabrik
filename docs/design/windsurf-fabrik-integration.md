# Windsurf + Fabrik Integration Strategy

**Status:** RFC (Request for Comments)
**Date:** 2026-01-05

---

## Executive Summary

Unified strategy for integrating Windsurf Cascade with Fabrik's droid exec infrastructure. Goal: consistent convention enforcement regardless of which AI tool is used.

---

## 1. Current State

| Component | Status | Issue |
|-----------|--------|-------|
| `.windsurfrules` | 50KB | **4x over 12KB limit** |
| `AGENTS.md` | 519 lines | Works well |
| `.windsurf/rules/` | Missing | Not configured |
| `.windsurf/workflows/` | Missing | Not configured |
| `.windsurf/hooks.json` | Missing | Not configured |
| `mcp_config.json` | Missing | Not configured |

---

## 2. Environment Overview

```
DEVELOPMENT (WSL)
├── Windows 11 Host
│   └── Windsurf IDE (connects to WSL)
└── WSL2 Ubuntu
    ├── /opt/fabrik/        (core infrastructure)
    ├── /opt/project-*/     (project folders)
    ├── PostgreSQL localhost
    └── droid exec CLI

PRODUCTION
├── VPS (ARM64 Hetzner)
│   ├── Coolify (Docker orchestration)
│   ├── Traefik (reverse proxy)
│   └── postgres-main container
└── Supabase (alternative target)
```

---

## 3. Problem Statement

1. **Size limit:** `.windsurfrules` at 50KB exceeds 12KB limit
2. **Fragmentation:** Rules split between two files with overlap
3. **No cross-tool enforcement:** Cascade rules don't apply to droid
4. **Missing features:** Workflows, hooks, MCP not configured

---

## 4. Proposed Architecture

### Source of Truth Hierarchy

```
Level 1: AGENTS.md (All AI agents read this)
    └── Core conventions, droid usage, patterns

Level 2: .windsurf/rules/ (Windsurf-specific)
    └── Split by activation mode (<12KB each)

Level 3: Shared enforcement scripts
    └── Called by BOTH Cascade and droid hooks

Level 4: Workflows
    └── Automated processes (/new-project, /deploy-vps)
```

### File Structure

```
/opt/fabrik/
├── AGENTS.md                    ← PRIMARY (all agents)
├── .windsurf/
│   ├── rules/
│   │   ├── 01-critical.md       ← Always On (security, env vars)
│   │   ├── 02-python.md         ← Glob: **/*.py
│   │   ├── 03-typescript.md     ← Glob: **/*.ts,**/*.tsx
│   │   ├── 04-docker.md         ← Glob: **/Dockerfile
│   │   └── 05-manual.md         ← Manual: @saas, @api
│   ├── workflows/
│   │   ├── new-project.md       ← /new-project
│   │   ├── deploy-vps.md        ← /deploy-vps
│   │   └── code-review.md       ← /code-review
│   └── hooks.json
├── .factory/hooks/              ← droid hooks (existing)
└── scripts/enforcement/         ← SHARED scripts
    ├── validate_conventions.py
    └── format_code.py
```

---

## 5. Rule Distribution

### 01-critical.md (Always On, ~8KB)

Content:
- No hardcoded localhost/127.0.0.1
- Runtime env var loading (not class-level)
- Health checks must test dependencies
- CSPRNG passwords (32 chars)
- No `/tmp/` usage
- ARM64 Docker images

### 02-python.md (Glob: *.py, ~6KB)

Content:
- FastAPI patterns
- Dependency injection
- Structured logging
- Type hints required
- Error handling patterns

### 03-typescript.md (Glob: *.ts/*.tsx, ~6KB)

Content:
- Next.js App Router structure
- Component patterns (named exports, typed props)
- API route patterns
- Environment variable handling

### 04-docker.md (Glob: Dockerfile/compose.yaml, ~4KB)

Content:
- Debian-based images (not Alpine)
- Health check configuration
- Multi-stage builds
- Coolify network setup

---

## 6. Workflows

### /new-project
1. Determine type (API/SaaS/Worker/Library)
2. Run scaffold command
3. Configure environment
4. Verify setup
5. Initialize git

### /deploy-vps
1. Pre-flight checks
2. Test locally with docker compose
3. Push to git
4. Deploy via Coolify
5. Verify deployment

### /code-review
1. Identify changed files
2. Run primary model review
3. Run secondary model review
4. Compile findings
5. Create summary

---

## 7. Hooks Configuration

```json
{
  "hooks": {
    "pre_write_code": [{
      "command": "python3 /opt/fabrik/scripts/enforcement/validate_conventions.py",
      "show_output": true
    }],
    "post_write_code": [{
      "command": "python3 /opt/fabrik/scripts/enforcement/format_code.py",
      "show_output": false
    }]
  }
}
```

**Key:** Same scripts called by both Cascade hooks and droid hooks = unified enforcement.

---

## 8. Enforcement Matrix

| Rule | Docs | Rules | Hooks | CI |
|------|------|-------|-------|-----|
| No hardcoded localhost | ✅ | ✅ | ✅ blocks | ✅ |
| Runtime env loading | ✅ | ✅ | ✅ warns | ✅ |
| CSPRNG passwords | ✅ | ✅ | ✅ warns | ✅ |
| Health checks | ✅ | ✅ | ❌ | ✅ |
| ARM64 images | ✅ | ✅ | ❌ | ✅ |
| Docs updated | ✅ | ✅ | ✅ reminds | ✅ |

---

## 9. Migration Plan

### Phase 1: Split Rules
- Create `.windsurf/rules/` directory
- Split `.windsurfrules` into <12KB files
- Keep old file as symlink for backward compat

### Phase 2: Add Workflows
- Create `.windsurf/workflows/`
- Implement /new-project, /deploy-vps, /code-review

### Phase 3: Add Hooks
- Create shared enforcement scripts
- Configure `.windsurf/hooks.json`
- Ensure compatibility with droid hooks

### Phase 4: Enable MCP
- Configure GitHub MCP server
- Test integration

---

## 10. Open Questions

1. **Rule priority:** If AGENTS.md and rules conflict, which wins?
2. **Hook strictness:** Block violations or just warn?
3. **Workflow scope:** Workspace-level or user-level?
4. **MCP servers:** Which ones are worth enabling?
5. **Backward compat:** Keep `.windsurfrules` symlink or remove?

---

## 11. Next Steps

1. Get feedback from ChatGPT, Sonnet, Gemini Pro
2. Refine strategy based on feedback
3. Implement Phase 1 (split rules)
4. Test with real projects
5. Document final approach

---

*See companion file: `windsurf-fabrik-integration-details.md` for full implementation details.*
