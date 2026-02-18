# Stage 3: Cascade Execution

Traycer manages the plan. Cascade executes one task at a time. This is how to keep Cascade from losing context.

**Integration:** This stage works with your existing windsurfrules. Cascade follows windsurfrules for code quality; this document adds the verification layer.

---

## The Problem with AI Coding Agents

They:
- Forget what they did 10 messages ago
- Lose track of the bigger picture
- Make inconsistent decisions across files
- Don't know when to stop

## The Solution: Single-Task Execution

Never give Cascade the whole project. Give it ONE task with:
1. Complete context (what exists)
2. Specific goal (what to build)
3. Exact steps (how to do it)
4. Clear done criteria (how to verify)

---

## Mandatory Verification Gate (Mode 4)

After **every task implementation**, verification is mandatory.

### Roles (Strict Separation)

**Verifier — Factory Droid (GPT-5.1-Codex-Max)**

* Finds bugs, risks, and inconsistencies
* Explains why they matter
* Proposes concrete fixes
* Decides whether the task is acceptable

**Implementer — Windsurf Cascade (SWE-1.5)**

* Applies fixes exactly as instructed
* Runs tests locally
* Makes no new design decisions

> **Verifier never fixes. Builder never self-verifies.**

---

### Per-Task Execution Loop

For every task X.Y:

1. **Mode 3 — Build**
   Cascade implements the task.
2. **Self-Review**
   Cascade runs windsurfrules self-review checklist.
3. **Quality Gate**
   Run: `ruff check .`, `mypy .`, `pytest`
4. **Mode 4 — Verify**
   Factory Droid audits the changes.
5. **Mode 3 — Fix**
   Cascade applies required fixes.
6. **Mode 4 — Re-verify**
   Droid confirms resolution.
7. **Mode 5 — Ship**
   Update `tasks.md` + docs.

A task is **NOT DONE** until Mode 4 passes.

---

### Required Mode Header (Add to Every Task Prompt)

Add this header at the top of every task:

```
Stage: 3 — Execution
Current Mode: Mode 3 — Build
Spec Status: Frozen
Scope: Task X.Y only
Next Required Step: Mode 4 — Verify with Factory Droid (Codex-Max)
```

This header must remain unchanged during execution.

---

## Cascade Task Prompt Template

Use this template for EVERY task:

```
Stage: 3 — Execution
Current Mode: Mode 3 — Build
Spec Status: Frozen
Scope: Task X.Y only
Next Required Step: Mode 4 — Verify with Factory Droid (Codex-Max)

---

## Task: [X.Y] [Task Name]

### Before-Writing-Code Protocol

```
GOAL: [one sentence outcome]
PLAN: [tools/libs chosen; why; key risks]
DEPLOY: [WSL | VPS Docker | Supabase] — Will config work in all targets?
ISSUES: "Known issues for [tool]? If yes, list now."
CONFIRM: "Proceed?" → Wait for explicit "yes"
```

### Context
**Project**: [name]
**Project Root**: `/opt/<project>/`
**Spec Location**: `/opt/<project>/spec_out/`
**Current State**:
- [what files/features exist from previous tasks]
- [what's working]

### Goal
[One sentence: what this task achieves]

### Reference Docs
Read these before starting:
- `spec_out/SPEC.md` - Section [X] for requirements
- `spec_out/DataModel.md` - Entity: [Z] for data model

### Steps
1. [Exact action with file paths]
2. [Exact action]
3. [Exact action]
...

### Acceptance Criteria
- [ ] [Specific testable criterion]
- [ ] [Specific testable criterion]
- [ ] [Specific testable criterion]

### Constraints (windsurfrules enforced)
- Do NOT modify files outside this task's scope
- Do NOT add features not in the spec
- Do NOT refactor existing code unless required for this task
- NEVER hardcode `localhost` — use `os.getenv('VAR', 'default')`
- NEVER use `/tmp/` — use project-local `.tmp/` or `.cache/`
- Health checks MUST test actual dependencies (not just return OK)
- App MUST bind to `0.0.0.0` (not 127.0.0.1)
- All config via env vars, not hardcoded
- Ask if anything is unclear before proceeding

### Self-Review Checklist (run before reporting done)
- [ ] Does it handle edge cases? (empty input, null, errors)
- [ ] Any hardcoded values that should be config?
- [ ] Security issues? (exposed secrets, injection, etc.)
- [ ] Will it break existing functionality?
- [ ] Is the code readable without comments?
- [ ] Type hints on all functions?
- [ ] `ruff check .` passes?
- [ ] `mypy .` passes?
- [ ] DOCS UPDATED? (schema→database.md, API→api.md, config→CONFIGURATION.md)

### When Done
Report:
1. Files created/modified (list with one-line description)
2. How to test (exact commands or steps)
3. Any deviations from spec (explain why)
4. Any blockers for next task

---

After completing this task, the next step is mandatory:
→ Run Mode 4 — Verify using Factory Droid (GPT-5.1-Codex-Max)
```

---

## Mode 4 Verification Prompt Template

Use this template when running verification in Factory Droid:

```bash
# Run verification with Factory Droid
droid exec --auto low "
Stage: 3 — Execution
Current Mode: Mode 4 — Verify
Spec Status: Frozen
Scope: Task X.Y only

---

## Verification Request: Task [X.Y] [Task Name]

### Task Summary
[Brief description of what was implemented]

### Files Changed
- \`/opt/<project>/path/to/file1.py\` - [purpose]
- \`/opt/<project>/path/to/file2.py\` - [purpose]

### Acceptance Criteria
- [ ] [criterion 1]
- [ ] [criterion 2]
- [ ] [criterion 3]

### Reference Specs
- \`/opt/<project>/spec_out/SPEC.md\` - Section [X]
- \`/opt/<project>/spec_out/DataModel.md\` - Entity [Z]

### Windsurfrules Compliance Check
Verify:
- [ ] No hardcoded \`localhost\` — uses env vars
- [ ] No \`/tmp/\` usage — uses project-local dirs
- [ ] Health endpoint tests actual dependencies
- [ ] App binds to 0.0.0.0
- [ ] All config via env vars
- [ ] Type hints present
- [ ] No bare except clauses
- [ ] No secrets in code

### Your Task (Verifier)
1. Audit all changed files against the spec
2. Check windsurfrules compliance
3. Identify bugs, risks, inconsistencies
4. For each issue found:
   - Describe the problem
   - Explain why it matters
   - Propose a concrete fix
5. Verdict: PASS or FAIL with required fixes

### Constraints
- You do NOT implement fixes (that's Cascade's job)
- You do NOT make design decisions
- You ONLY audit and recommend

### Output Format

## Verification Report: Task X.Y

### Windsurfrules Compliance
- [x] No hardcoded localhost
- [ ] FAIL: Health endpoint just returns OK (must test DB)

### Issues Found
1. **[Issue Title]**
   - Problem: [description]
   - Impact: [why it matters]
   - Fix: [exact instructions for Cascade]

2. **[Issue Title]**
   ...

### Verdict
[ ] PASS - No issues, proceed to next task
[ ] FAIL - Fix required issues and re-verify

### Notes for Next Task
[Any context the next task should know]
"
```

---

## Execution Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│ You (with tasks.md open)                                            │
│                                                                     │
│ 1. Copy Task X.Y prompt from plan/task_prompts/task_X.Y.md          │
│ 2. Paste into fresh Windsurf Cascade chat (Mode 3 — Build)          │
│ 3. Let Cascade complete the task                                    │
│ 4. Cascade runs self-review checklist                               │
│ 5. Run quality gate: ruff check . && mypy . && pytest               │
│ 6. Run Mode 4 verification with Factory Droid                       │
│ 7. If FAIL: paste fixes back to Cascade, repeat from step 3         │
│ 8. If PASS: update tasks.md, close chats, next task                 │
└─────────────────────────────────────────────────────────────────────┘
```

**Key: Fresh chat for each task.** This prevents context pollution.

---

## Cascade Session Rules

Paste this at the START of every Cascade session:

```
You are executing a single implementation task for a project at /opt/<project>/.

Rules (from windsurfrules):
1. Read all referenced spec docs BEFORE writing code
2. Follow the steps in order
3. Do not add unrequested features
4. Do not modify files outside task scope
5. NEVER hardcode localhost — use os.getenv('VAR', 'default')
6. NEVER use /tmp/ — use project-local .tmp/ or .cache/
7. Health checks MUST test actual dependencies
8. If something is unclear, ASK before assuming
9. Run self-review checklist before reporting done
10. You do NOT self-verify — verification is done by Factory Droid

Current task follows:
```

---

## Long Command Handling

Per windsurfrules, use `rund`/`rundsh` for commands >30s:

```bash
# Tier A (<30s) - run normally
git status
ruff check .

# Tier C (>2min or complex) - use rund
rund npm install
rund docker build -t myapp .
rund pytest -v

# Monitor long commands
runc /tmp/job_xxx     # Check status every 15s
runk /tmp/job_xxx     # Kill if stuck 90s
```

---

## Recovery: When Cascade Goes Off Track

Signs it's lost:
- Modifying files not in the task
- Adding features not requested
- Contradicting the spec
- Looping on the same error
- Using `/tmp/` instead of project dirs
- Hardcoding connection strings

Recovery:
1. Stop the chat
2. Manually review/revert changes: `git diff`, `git checkout -- .`
3. Start fresh chat with same task prompt
4. Add note: "Previous attempt failed because [X]. Avoid [Y]."

---

## Folder Structure for Execution

```
/opt/<project>/
├── spec_out/                    # Stage 1 (frozen - read only)
│   ├── SPEC.md
│   ├── PRD.md
│   ├── UI.md
│   ├── DataModel.md
│   └── Workflows.md
├── plan/                        # Stage 2 (frozen - your execution guide)
│   ├── IMPLEMENTATION_PLAN.md
│   └── task_prompts/
│       ├── task_1.1.md
│       ├── task_1.2.md
│       └── ...
├── src/                         # Stage 3 output (the actual code)
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models/
│   ├── services/
│   ├── api/
│   └── utils/
├── tests/                       # Test files mirror src/
├── scripts/                     # Watchdog scripts per windsurfrules
├── config/
├── docs/
│   ├── README.md
│   ├── CONFIGURATION.md         # Update when config changes
│   └── reference/
│       ├── database.md          # Update when schema changes
│       └── api.md               # Update when API changes
├── data/                        # Persistent data (gitignored)
├── .tmp/                        # Temp files (gitignored, safe to delete)
├── .cache/                      # Cache files (gitignored, safe to delete)
├── logs/                        # Log files (gitignored)
├── tasks.md                     # Progress tracker
├── README.md
├── CHANGELOG.md
├── .env.example
├── .env                         # Gitignored
├── Dockerfile
├── compose.yaml
├── Makefile
├── pyproject.toml
├── .python-version
└── .pre-commit-config.yaml
```

---

## Progress Tracking

Update `tasks.md` after each task (per windsurfrules format):

```markdown
# Project: myproject

## Phase 1: Foundation
- [x] Task 1.1: Project setup
  - [x] Create folder structure
  - [x] Setup .env.example
  - [x] Initialize git
  - [x] ✓ Verified with Droid
- [x] Task 1.2: Database schema
  - [x] Design tables
  - [x] Create migrations
  - [x] ✓ Verified with Droid
- [ ] Task 1.3: Auth setup — IN PROGRESS
  - [ ] Login endpoint
  - [ ] Token validation
- [ ] Task 1.4: Base API routes

## Phase 2: Core Features
- [ ] Task 2.1: ...
```

**Rules** (from windsurfrules):
- Update tasks.md after completing each task
- Never work on tasks out of order without approval
- Use for resuming work in new sessions

---

## Continue Project Protocol

When resuming work (per windsurfrules):
1. Read `tasks.md` + recent git log
2. Show: current phase, next task, blockers if any
3. Ask: "Proceed with [next task]?"
4. Wait for approval before any changes

---

## Quality Gate Commands

Run before Mode 4 verification:

```bash
# Python projects
ruff check .                    # Lint
ruff format --check .           # Format check
mypy .                          # Type check
pytest                          # Tests

# Or use pre-commit
pre-commit run --all-files

# Docker parity check
make docker-smoke               # Build + run + health check
```

---

## Credentials Checklist

When task adds new credentials (per windsurfrules):

```bash
# 1. Add to project .env
echo "NEW_API_KEY=xyz123" >> /opt/<project>/.env

# 2. ALSO add to Fabrik master .env
echo "NEW_API_KEY=xyz123" >> /opt/fabrik/.env

# 3. Add placeholder to .env.example
echo "NEW_API_KEY=" >> /opt/<project>/.env.example
```

---

## Summary: The 5-Mode Discipline

| Mode | Actor | Action | Output |
|------|-------|--------|--------|
| 3 — Build | Cascade (SWE-1.5) | Implement task | Code changes |
| (Self-Review) | Cascade | Run windsurfrules checklist | Verified code |
| (Quality Gate) | You | Run ruff/mypy/pytest | Clean code |
| 4 — Verify | Droid (Codex-Max) | Audit changes | PASS/FAIL + fixes |
| 3 — Fix | Cascade (SWE-1.5) | Apply fixes | Updated code |
| 4 — Re-verify | Droid (Codex-Max) | Confirm fixes | PASS |
| 5 — Ship | You | Update tasks.md + docs | DONE |

**No task is complete without passing Mode 4.**
