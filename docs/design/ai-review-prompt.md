# AI Review Request: Windsurf + Fabrik Integration Strategy

**Please review this proposed architecture and provide feedback.**

---

## Context

I'm building a personal development infrastructure called **Fabrik** that standardizes how projects are created, developed, and deployed. I use two AI coding tools simultaneously:

1. **Windsurf Cascade** - IDE-integrated AI (like Cursor) for interactive coding
2. **droid exec** - CLI-based AI (Factory AI) for automation, CI/CD, batch operations

Both tools can work on the same codebase. I need a unified system where coding conventions are enforced regardless of which tool is active.

---

## Environment

```
DEVELOPMENT (WSL on Windows 11)
├── Windsurf IDE (Windows) → Connected to WSL via Remote
├── droid exec CLI → Runs in WSL terminal
├── PostgreSQL, Redis (localhost)
└── Projects at /opt/<project-name>/

PRODUCTION
├── VPS (ARM64 Hetzner) with Coolify + Docker Compose
└── Supabase (alternative for some projects)
```

---

## Current Problem

### 1. Rule Fragmentation
- `.windsurfrules` (50KB) - Windsurf-specific rules, **4x over 12KB limit**
- `AGENTS.md` (519 lines) - Cross-agent instructions
- Significant content overlap between them

### 2. No Cross-Tool Enforcement
- Rules in Windsurf don't apply to droid exec
- Rules in droid don't apply to Windsurf
- Risk of inconsistent behavior

### 3. Missing Features
- Windsurf workflows not configured
- Windsurf hooks not configured
- MCP servers not configured

---

## Proposed Architecture

### Source of Truth Hierarchy

```
Level 1: AGENTS.md (All AI agents read this)
         └── Core conventions, patterns, droid usage guide
         └── Works with: Windsurf, droid, Cursor, Aider, etc.

Level 2: .windsurf/rules/ (Windsurf-specific)
         └── Split into <12KB files with activation modes
         └── Only read by Windsurf Cascade

Level 3: Shared Enforcement Scripts
         └── Python scripts called by BOTH Cascade hooks AND droid hooks
         └── Single validation logic, two entry points

Level 4: Workflows
         └── Windsurf: .windsurf/workflows/*.md → /slash-commands
         └── droid: Skills + custom commands
```

### Proposed File Structure

```
/opt/fabrik/
├── AGENTS.md                    ← PRIMARY (all agents read)
│
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
│
├── .factory/hooks/              ← droid hooks (existing)
│
└── scripts/enforcement/         ← SHARED validation scripts
    ├── validate_conventions.py
    └── format_code.py
```

### Rule Activation Modes

| File | Mode | When Active |
|------|------|-------------|
| 01-critical.md | Always On | Every conversation |
| 02-python.md | Glob: **/*.py | When editing Python files |
| 03-typescript.md | Glob: **/*.ts | When editing TypeScript |
| 04-docker.md | Glob: Dockerfile | When editing Docker files |
| 05-manual.md | Manual | When @mentioned |

### Shared Hook Enforcement

Both Cascade and droid call the same validation scripts:

```python
# /opt/fabrik/scripts/enforcement/validate_conventions.py
# Called by BOTH tools

VIOLATIONS = [
    ("Hardcoded localhost", r"['\"](localhost|127\.0\.0\.1)['\"]"),
    ("Class-level env var", r"class \w+:.*os\.getenv"),
    ("Weak password", r"password\s*=\s*['\"][^'\"]{1,16}['\"]"),
]

# Exit code 2 blocks the action (pre-hooks only)
```

---

## Key Conventions to Enforce

1. **No hardcoded localhost** - Use `os.getenv('DB_HOST', 'localhost')`
2. **Runtime config loading** - Not at class definition time
3. **Health checks test dependencies** - Not just `return {"status": "ok"}`
4. **CSPRNG passwords** - 32 alphanumeric characters
5. **ARM64 Docker images** - VPS uses ARM64 architecture
6. **Documentation updates with code** - Every change needs docs update

---

## Questions for Review

1. **Is the hierarchy correct?** AGENTS.md → Rules → Hooks makes sense?

2. **Hook strictness:** Should violations block edits (exit code 2) or just warn?

3. **Rule activation modes:** Are Always/Glob/Manual the right choices for each file?

4. **Content distribution:** What belongs in AGENTS.md vs Rules?

5. **Simpler alternative?** Is there a simpler architecture that achieves the same goals?

6. **Conflict resolution:** If AGENTS.md says X and a Rule says Y, which wins?

7. **Workflow design:** Should workflows call droid exec for heavy tasks, or stay pure Windsurf?

8. **What's missing?** Any gaps in this design?

---

## Constraints

- Windsurf rule files limited to 12,000 characters each
- Both tools must enforce same conventions
- Cannot lose any enforcement from current 50KB .windsurfrules
- System must scale to many projects (each project symlinks to /opt/fabrik/)
- droid exec has its own hooks/skills system that must remain functional

---

## Success Criteria

1. Single source of truth for core conventions
2. Rules enforced whether using Cascade or droid
3. No rule content lost from current files
4. Workflows automate common tasks
5. Hooks catch violations before they're committed
6. System scales to new projects easily

---

**Please provide specific, actionable feedback on this architecture.**
