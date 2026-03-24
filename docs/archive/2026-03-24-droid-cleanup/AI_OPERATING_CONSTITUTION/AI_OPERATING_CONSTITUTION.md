# AI Operating Constitution

**Single-page reference for the 5-Mode control system.**

---

## Stages (What Gets Built)

| Stage | Produces | Location | Tool |
|-------|----------|----------|------|
| 1 — Discovery | `spec_out/*` | `/opt/<project>/spec_out/` | Claude.ai / ChatGPT |
| 2 — Planning | `plan/*` + `tasks.md` | `/opt/<project>/plan/` | Traycer / Factory Droid |
| 3 — Execution | `src/*` | `/opt/<project>/src/` | Cascade + Droid |

**Pre-Project:** Complete research in `/opt/_research/<project>/` before Stage 1.

---

## Modes (How Work Is Controlled)

| Mode | Name | Who Executes | Who Decides | Escalation |
|------|------|--------------|-------------|------------|
| 1 | Explore | Gemini 3 Flash | You | Sonnet 4.5 |
| 2 | Design | Claude Sonnet 4.5 | You | Opus 4.5 |
| 3 | Build | Cascade (SWE-1.5) | You | Codex-Max |
| 4 | Verify | Droid (Codex-Max) | Droid | Opus 4.5 |
| 5 | Ship | Haiku 4.5 | You | Gemini 3 Flash |

---

## Core Rules

### Spec Freeze
> Once Stage 3 begins, all specs are **read-only**.
> Changes require returning to Stage 1 or 2.

### Verification Gate
> No task is complete until Mode 4 passes.
> Verifier never fixes. Builder never self-verifies.

### Role Separation
| Role | Tool | Can Do | Cannot Do |
|------|------|--------|-----------|
| Builder | Cascade | Implement, fix | Verify, design |
| Verifier | Droid | Audit, recommend | Implement, fix |

---

## Per-Task Loop

```
1. Mode 3 — Build       → Cascade implements
2. Self-Review          → Cascade runs windsurfrules checklist
3. Quality Gate         → ruff check . && mypy . && pytest
4. Mode 4 — Verify      → Factory Droid audits
5. Mode 3 — Fix         → Cascade applies fixes (if needed)
6. Mode 4 — Re-verify   → Droid confirms
7. Mode 5 — Ship        → Update tasks.md + docs
```

---

## Required Header (Every Task)

```
Stage: 3 — Execution
Current Mode: Mode 3 — Build
Spec Status: Frozen
Scope: Task X.Y only
Next Required Step: Mode 4 — Verify with Factory Droid (Codex-Max)
```

---

## Before-Writing-Code Protocol (Every Task)

```
GOAL: [one sentence outcome]
PLAN: [tools/libs chosen; why; key risks]
DEPLOY: [WSL | VPS Docker | Supabase] — Will config work in all targets?
ISSUES: "Known issues for [tool]? If yes, list now."
CONFIRM: "Proceed?" → Wait for explicit "yes"
```

---

## Windsurfrules Integration

| Pipeline Step | Windsurfrules Requirement |
|---------------|---------------------------|
| Pre-Project | Research in `/opt/_research/` |
| Stage 2 | tasks.md format: Phase > Task > Subtask |
| Stage 3 Build | Before-Writing-Code Protocol |
| Stage 3 Self-Review | Self-review checklist |
| Stage 3 Quality | `ruff check .`, `mypy .`, `pytest` |
| Mode 5 Ship | Keep docs in sync (schema→database.md, API→api.md) |

---

## Hardcoded Rules (Never Violate)

```python
# WRONG
DB_HOST = 'localhost'
temp_file = '/tmp/data.json'
return {"status": "ok"}  # Health check

# RIGHT
DB_HOST = os.getenv('DB_HOST', 'localhost')
temp_file = PROJECT_ROOT / '.tmp' / 'data.json'
# Health check that tests DB:
async with db.acquire() as conn:
    await conn.execute("SELECT 1")
return {"status": "ok", "database": "connected"}
```

---

## Quick Reference: Tool Selection

| Situation | Tool | Model |
|-----------|------|-------|
| Exploring ideas | ChatGPT Web | Gemini 3 Flash |
| Defining spec | Claude.ai | Sonnet 4.5 |
| Planning tasks | Traycer / Droid | Sonnet 4.5 |
| Writing code | Windsurf Cascade | SWE-1.5 |
| Auditing code | Factory Droid | Codex-Max |
| Documentation | Factory CLI | Haiku 4.5 |

---

## Recovery Protocol

1. Stop the current chat
2. Revert uncommitted changes: `git checkout -- .`
3. Open fresh chat
4. Add context: "Previous attempt failed because [X]"
5. Resume from last verified checkpoint

---

## Credentials Protocol

When adding credentials:
```bash
# 1. Project .env
echo "API_KEY=xyz" >> /opt/<project>/.env

# 2. Master .env
echo "API_KEY=xyz" >> /opt/fabrik/.env

# 3. Template
echo "API_KEY=" >> /opt/<project>/.env.example
```

---

## File Hierarchy

```
/opt/<project>/
├── spec_out/     # Stage 1 (frozen after Stage 2)
├── plan/         # Stage 2 (frozen after Stage 3 starts)
│   └── task_prompts/
├── src/          # Stage 3 (mutable during execution)
├── tests/
├── scripts/      # Watchdogs
├── docs/         # Keep in sync with code
├── tasks.md      # Progress tracker
├── .env          # Credentials (gitignored)
├── .env.example  # Template (committed)
├── Dockerfile
├── compose.yaml
└── Makefile      # make dev, make docker-smoke, make test
```

---

## Reference Locations

| Resource | Path |
|----------|------|
| Windsurf rules | `/opt/_project_management/windsurfrules` |
| Droid usage | `/opt/_project_management/droid-exec-usage.md` |
| Templates | `/opt/_project_management/templates/` |
| Research | `/opt/_research/<project>/` |
| Port registry | `/opt/_project_management/PORTS.md` |
| Master credentials | `/opt/fabrik/.env` |
| DB strategy | `/opt/_project_management/docs/reference/DATABASE_STRATEGY.md` |

---

## Quick Commands

```bash
# Quality gate
ruff check . && mypy . && pytest

# Docker parity
make docker-smoke

# Long commands (>2min)
rund npm install
runc /tmp/job_xxx    # Check status
runk /tmp/job_xxx    # Kill if stuck

# Verification
droid exec --auto low "..."

# Pre-commit
pre-commit run --all-files
```
