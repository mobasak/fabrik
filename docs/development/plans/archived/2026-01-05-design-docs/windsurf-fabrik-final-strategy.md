# Windsurf + Fabrik Integration: Final Strategy

**Status:** Approved (Dual-Model Reviewed)
**Date:** 2026-01-05
**Reviewed By:** gpt-5.1-codex-max, gemini-3-flash-preview

---

## Executive Summary

Split the monolithic 50KB `.windsurfrules` into a modular, enforceable system with shared validation logic. Key insight from review: move from **instruction-based** (fragile) to **validation-based** (robust).

---

## Approved Architecture

### Source of Truth Hierarchy

```
Level 1: AGENTS.md ("Project Constitution")
         └── High-level policy, "What" and "Why"
         └── Read by ALL AI tools (Windsurf, droid, Cursor, Aider)

Level 2: .windsurf/rules/ ("Tool Instructions")
         └── Specific "How" for Cascade
         └── Modular files <12KB each with activation modes
         └── Root stub links back to AGENTS.md

Level 3: scripts/enforcement/ ("Hard Enforcement")
         └── Shared validation scripts
         └── Called by BOTH Cascade hooks AND droid hooks
         └── Single policy engine

Level 4: .windsurf/workflows/ ("Playbooks")
         └── Multi-step automation recipes
         └── Task tracking via tasks.md pattern
```

### Precedence Rule

**More restrictive rule wins.** Order: `AGENTS.md > .windsurf/rules/* > workflow defaults`

---

## File Structure (Final)

```
/opt/fabrik/
├── AGENTS.md                        ← Level 1: Project Constitution
│
├── .windsurfrules                   ← Stub (<1KB) with:
│                                       - Precedence declaration
│                                       - Links to .windsurf/rules/
│                                       - Discovery rule
│                                       - Version stamp
│
├── .windsurf/
│   ├── rules/
│   │   ├── index.md                 ← Links to all shards
│   │   ├── 01-core.md               ← Always On: Security, env vars
│   │   ├── 02-python.md             ← Glob: **/*.py
│   │   ├── 03-typescript.md         ← Glob: **/*.ts,**/*.tsx
│   │   ├── 04-docker.md             ← Glob: **/Dockerfile,compose.yaml
│   │   └── 05-automation.md         ← Manual: @saas, @api, @deploy
│   │
│   ├── workflows/
│   │   ├── new-project.md           ← /new-project
│   │   ├── deploy-vps.md            ← /deploy-vps
│   │   ├── code-review.md           ← /code-review
│   │   └── scaffold-service.md      ← /scaffold-service
│   │
│   └── hooks.json                   ← Cascade hook config
│
├── .factory/
│   └── hooks/                       ← droid hooks (existing)
│
└── scripts/
    └── enforcement/                 ← SHARED (Level 3)
        ├── enforce.py               ← Main validator (JSON output)
        ├── check_secrets.py         ← Secret detection
        ├── check_conventions.py     ← Fabrik conventions
        └── verify.sh                ← Final gate script
```

---

## Block vs Warn Policy

### BLOCK (exit code 2) - Hard Failures

| Check | Reason |
|-------|--------|
| Secrets/keys in code | Security |
| Hardcoded localhost/127.0.0.1 | Breaks Docker/VPS |
| Alpine base images | Breaks ARM64 VPS |
| Missing env var guards | Breaks portability |
| Missing health-check dependency probes | Hides failures |
| compose/Dockerfile drift from standards | Deployment failures |
| Missing validators (ruff/mypy/pytest) on Python changes | Quality gate |

### WARN (exit code 0 with message) - Soft Failures

| Check | Reason |
|-------|--------|
| Style suggestions | Non-breaking |
| Missing documentation | Warn → block on PR |
| Class-level getenv | Bad practice but may not crash |
| Small commit suggestions | Productivity tip |

### Escape Hatch

`--no-block` flag for emergency hotfixes (logs incident for review).

---

## Implementation Plan

### Phase 1: Create Stub + Split Rules

1. Create `.windsurfrules` stub (~500 bytes):
   ```markdown
   # Fabrik Rules v2026-01-05

   ## Precedence
   AGENTS.md > .windsurf/rules/* > workflow defaults

   ## Discovery
   Always check .windsurf/rules/ for tech-specific guidelines before editing.

   ## Index
   - [Core Rules](/.windsurf/rules/01-core.md)
   - [Python](/.windsurf/rules/02-python.md)
   - [TypeScript](/.windsurf/rules/03-typescript.md)
   - [Docker](/.windsurf/rules/04-docker.md)
   - [Automation](/.windsurf/rules/05-automation.md)
   ```

2. Shard current 50KB into 4-5 files <12KB each
3. Create `.windsurf/rules/index.md` linking all shards

### Phase 2: Build Shared Enforcement

1. Create `scripts/enforcement/enforce.py`:
   - Checks all blockers
   - JSON output for both tools
   - Exit code 0 (pass), 1 (warn), 2 (block)

2. Wire into Cascade hooks (`.windsurf/hooks.json`)
3. Wire into droid hooks (`.factory/hooks/`)

### Phase 3: Add Workflows

1. Create `.windsurf/workflows/` directory
2. Implement core workflows:
   - `/new-project` - Scaffold with all conventions
   - `/deploy-vps` - Coolify deployment
   - `/code-review` - Dual-model review

### Phase 4: Refine AGENTS.md

1. Keep AGENTS.md as "Project Constitution"
2. Move CLI flags and quick reference to Level 2
3. Add version stamp for sync tracking

---

## Cross-Tool Handshake

When Cascade finishes a task and hands off to droid:

1. Cascade creates `.droid/handoff.json` with:
   - Files changed
   - Task summary
   - Suggested next action

2. droid exec reads handoff and runs Level 3 verification

3. On success, clears handoff file

---

## Version Tracking

Both AGENTS.md and `.windsurfrules` stub include:

```markdown
Rules-Version: 2026-01-05
```

Enforcement script warns if versions mismatch.

---

## Success Criteria

- [ ] All rule files <12KB
- [ ] No content lost from original .windsurfrules
- [ ] Single enforcement script for both tools
- [ ] Blockers actually block (tested)
- [ ] Warnings show but don't block
- [ ] Workflows work with /slash-commands
- [ ] New projects get rules via symlink

---

## Next Steps

**Ready to implement when you give the go-ahead.**

1. Phase 1: Split rules (30 min)
2. Phase 2: Build enforcement (1 hr)
3. Phase 3: Add workflows (30 min)
4. Phase 4: Refine AGENTS.md (30 min)

Total: ~2.5 hours of implementation.
