# CRITICAL OPERATIONAL RULES

**READ THIS FILE FIRST before any file operations or project work.**

## 1. FILE OPERATIONS (ROLLBACK PREVENTION)

**⚠️ MANDATORY: MAX 50 LINES per heredoc. Operations >10s cause rollbacks.**

### Correct Pattern (ALWAYS USE):
```bash
# First chunk: CREATE (use >)
wsl-commander: bash -c "cat > /opt/project/file.py << 'EOF'
[max 50 lines]
EOF"

# Next chunks: APPEND (use >>)
wsl-commander: bash -c "cat >> /opt/project/file.py << 'EOF'
[max 50 lines]
EOF"

# Verify
wsl-commander: wc -l /opt/project/file.py
```

### Checklist:
1. Estimate total lines → divide by 50
2. First chunk: > (create)
3. Next chunks: >> (append)
4. Verify with wc -l

### NEVER USE:
- ❌ Large heredocs (100+ lines)
- ❌ wsl-commander:write_file
- ❌ bash_tool (isolated container)
- ❌ Filesystem MCP for WSL files

---

## 2. "CONTINUE [PROJECT]" PROTOCOL

**MANDATORY - NO EXCEPTIONS**

### STEP 1: Load State (DO THIS FIRST)
Read these files in order:
1. `/opt/[project]/project.yaml`
2. `/opt/[project]/.implementation-progress` (if exists)
3. Most recent `/opt/[project]/PHASE*_COMPLETE.md`
4. `/opt/[project]/README.md` (last 100 lines)
5. List `/opt/[project]/` directory

### STEP 2: State Report (REQUIRED FORMAT)
```
📊 PROJECT STATE LOADED: [name]

Version: [X.X.X]
Phase: [X] - [status]
Completion: [XX%]

✅ Features Built:
[list from completion docs]

📁 Structure:
[key dirs/files]

🎯 Last Work:
[what was completed]

⏭️ Next Step:
[logical next action]

❓ VERIFY: Proceed with [next step]?
```

### STEP 3: Wait for Approval
STOP. Do not proceed without "yes" from user.

### STEP 4: Execute (after approval only)

---

## 3. PROJECT LIFECYCLE

**Start new project:**
1. Create /opt/[name]/ + Git repo
2. Create project.yaml + checkpoint tools
3. Enable auto-checkpoint service
4. Verify first commit <15s

**Deploy to VPS:**
1. SSH: git clone to /opt/[project]
2. Setup production services
3. Enable production checkpoint

---

## 4. ENVIRONMENT RULES

**Three Environments:**
1. Windows: C:\Users\user\... → Filesystem MCP
2. WSL (Dev): /opt/[projects]/ → wsl-commander MCP
3. VPS (Prod): /opt/[production]/ → ssh MCP (ozgur@172.93.160.197)

**Quick Commands:**
```bash
wsl-commander: cat /opt/project/file     # Read
wsl-commander: ls -la /opt/              # List
wsl-commander: wc -l /opt/project/file   # Verify
```

---

## 5. COMMUNICATION STYLE

- Direct actionable steps (not options)
- 2 paths: Balanced vs Aggressive
- Recommend ONE (biased to action)
- Flag risks/trade-offs explicitly
- Step-by-step implementation
- Tie wins to: carnivore, fitness, girlfriend, financial security, travel

**Time Estimates:**
AI execution time in minutes only. Example: "3-5 minutes (90% confidence)"
NOT "1.5 hours for a human developer"

---

## ENFORCEMENT

**If Claude violates any rule above:**
User says: "STOP - Re-read CRITICAL_RULES.md"

Claude must:
1. Apologize
2. Re-read this file
3. Restart with correct approach

---

## 6. TOKEN CONSUMPTION MONITORING

**CRITICAL: Monitor token usage to prevent rollbacks.**

**Token Limits:**
- Maximum context: ~200K tokens
- Warning threshold: 140K tokens used
- Action threshold: 150K tokens used

**Required Actions:**

**At 140K tokens:**
```
⚠️ TOKEN WARNING: 140K/200K used.
Recommend starting fresh chat at 150K to prevent rollbacks.
```

**At 150K tokens:**
```
🚨 TOKEN LIMIT APPROACHING: 150K/200K used.
STRONG RECOMMENDATION: Start new chat now.
Copy project.yaml context only (not full history).
```

**Why This Matters:**
- Rollback frequency increases near token limits
- Operations slow down significantly
- Risk of losing work increases

**Starting Fresh Chat:**
1. User creates new chat
2. User says: "Continue [project]"
3. Claude reads CRITICAL_RULES.md + project state
4. Work resumes with clean token window

**Note:** Token count shown in system warnings (e.g., "Token usage: 77K/190K")
Monitor this and warn user proactively.

---

## 7. SESSION GATE (MANDATORY IN EVERY NEW CHAT)

Before ANY work, Claude must:
1) Read: /opt/context-management/CRITICAL_RULES.md
2) Output a 3-line summary:
   - What rules control file writes?
   - What counts as "Done" + time estimates rule?
   - When must it stop for approval?
3) Wait for: "Approved" before proceeding.

If violated, user says: "STOP - Re-read CRITICAL_RULES.md" → Claude apologizes, restarts gate.

---

## 8. BEFORE-WRITING-CODE PROTOCOL

NEW PROJECTS:
- User says: "I want to build X"
- Claude says: "Run planning-session first (see §22)"
- Wait for planning completion
- Then proceed with checklist below

EXISTING PROJECTS:

No code until this 4-item checklist is answered in one short block:

GOAL: [one sentence outcome]

PLAN: [tools/libs/APIs; why chosen; key risks/trade-offs]
**AI projects only** → Read /opt/context-management/AI_TAXONOMY.md first:
- Identify: ai_category + ai_subcategory
- Shortlist tools from taxonomy
- Justify chosen tool vs. top alternative
- Fill §17 grid before coding

ISSUES: "Known issues for [tool]? If yes, paste now."

CONFIRM: "Proceed?"  → Wait for explicit "yes".

Time estimate format: "X–Y minutes (Z% confidence)". No human-hour estimates.

---

## 9. ENVIRONMENT & TOOL VERIFICATION (VPS DEFAULT)

Assume Ubuntu VPS unless stated. Always verify tooling first:
- python3 --version
- psql --version
- which ffmpeg | which chromium | which chromedriver
- pip3 list | grep -E 'pandas|flask|fastapi|sqlalchemy|django'
- docker --version

If missing libs are required, list exact install commands before code. Prefer standard libraries. No new frameworks for simple tasks.

---

## 10. DATABASE POLICY (DEFAULT = PostgreSQL)

- One PostgreSQL 16 instance → one DB per project.
- Create DB:
  sudo -u postgres psql -c "CREATE DATABASE <project>;"
- Code pattern: psycopg2-binary, parameterized queries, connection pooling when needed.
- Backups: daily `pg_dump <db> > /opt/backups/<db>_$(date +%F).sql`
- Vector DB is optional. Only add if project demands semantic search.

---

## 11. RESILIENCE, LOGGING, STRUCTURE (TEMPLATE)

Every script must include:
- Header docstring: name, purpose, version, last updated.
- Config block: paths, flags (ENABLE_RETRIES, DRY_RUN), log file path.
- Logging: level+timestamp, rotate >10MB.
- Error policy:
  - Network = retry 5s, 15s, 30s then continue.
  - Permanent = skip, log ERROR.
  - Critical = log CRITICAL, stop.
- Atomic writes for important files.
- Minimal module split with clear tree.

Response format when code is requested:
1) Restate goal (1 sentence)
2) Approach (pros/cons, AI minutes)
3) Wait for approval
4) Provide code
5) Deployment steps (Ubuntu VPS, pip installs, SSH commands, paths)
6) Common errors & fixes

---

## 12. TIME-BOX & CIRCUIT BREAKERS

- 2-Hour Rule (wall-clock, including your testing):
  If not working → STOP, propose simpler path that ships this week.
- Rabbit-hole flags:
  - Adding frameworks for simple tasks
  - Multiple approaches without one recommendation
  - Code without setup instructions
  - Docker/K8s assumed without request
- If any flag triggers:
  User says: "STOP - Simplify. Minimal solution?" → Claude must pivot.

---

## 13. ENVIRONMENT HIERARCHY (DESKTOP FIRST)

Default = Claude Desktop (Commander MCP). CLI is execution-only.

Desktop (≈80%):
- Plan architecture, make decisions, multi-file review, write complex logic.
- Use MCP: view / str_replace / bash_tool.

VPS CLI (≈15%):
- Quick edits during SSH, long-running scripts, sysadmin tasks already in-shell.

WSL CLI (≈5%):
- Local testing when VPS is down or Windows-specific needs.

Anti-patterns:
- ❌ Architecture or multi-file reviews in CLI
- ❌ "Ping-pong" CLI back-and-forth for file reads/edits
- ✅ Desktop MCP for reading/editing/executing with fewer tokens

---

## 14. SHARED QUOTA RULE

All surfaces (Desktop, Web, CLI on VPS, CLI on WSL, Mobile) share ONE pool.
- Before heavy work: `claude /status` (or Desktop Usage panel).
- If weekly usage >70%: Desktop only; batch tasks; no exploratory work.
- No parallel CLI sessions. One surface at a time.

---

## 15. MODEL SELECTION POLICY

Default model: Sonnet 4.5 for coding and refactors.

Switch to Opus only when BOTH are true:
- Architectural reasoning across many modules/files
- You explicitly approve the switch in the thread

If auto-switch occurs, revert to Sonnet after the decision.

---

## 16. ORCHESTRATION PROTOCOL (DESKTOP → CLI → DESKTOP)

Desktop drives, CLI executes.

Desktop:
1) "Continue [project]" → load project.yaml + git log
2) Plan: list exact commands or edits
3) Use MCP tools whenever possible

CLI (only if needed):
1) Execute the prepared commands
2) Exit back to Desktop for analysis and next steps

---

## 17. TOKEN EFFICIENCY RULES

Prefer Desktop MCP over CLI for the same action:
- ✅ Desktop:
  view /opt/project/auth.py
  "Refactor authenticate(): [requirements]. Show diff only."
  bash_tool "cd /opt/project && git commit -m 'Refactor auth'"
- ❌ CLI sequence:
  "show file" → "explain" → "refactor" → "explain changes"

Never paste large files into chat. Use view.

---

## 18. CONTEXT WINDOW HYGIENE

Claude prunes around high usage; prevent rot/poisoning/anxiety:
- New chat every ~2–3 hours of heavy work.
- Between unrelated tasks: CLI `/clear` before continuing.
- Keep high-signal context only. Don't restate history; rely on project.yaml + git log.
- Checkpoint system: auto-commits every 15s; commit messages = breadcrumbs.

---

## 19. ANTI-PATTERNS (BLOCKERS)

Stop and pivot if any of these appear:
- Suggesting frameworks for simple scripts
- Multiple approaches without one recommendation
- Code without setup instructions
- Docker/K8s assumed without explicit request
- Rebuilding context in conversation instead of using project.yaml/git log
- Parallel CLI sessions

User trigger: "STOP – Simplify. Minimal solution?" → Claude pivots.

---

## 20. SESSION CHECKLISTS

Before each session:
- [ ] Quota OK? `/status`)
- [ ] Session Gate done?
- [ ] project.yaml current? checkpoint running?

During:
- [ ] Desktop for intelligence, CLI only for execution
- [ ] Batch related requests
- [ ] MCP tools for file ops and commands

After:
- [ ] Decisions saved to project.yaml
- [ ] Recent changes committed
- [ ] Next steps queued (for a fresh chat if needed)

---

## 21. PYTHON PRODUCTION STANDARD (REFERENCE)

For Python work, follow the production standard:
Read: /opt/context-management/PYTHON_PRODUCTION_STANDARDS.md

Minimum bar before code runs in production:
- Header docstring, config flags, logging with rotation (>10MB), atomic writes
- Error policy: Network=retry [5s,15s,30s]; Permanent=skip; Critical=stop
- Recovery on startup; daily DB backups; integrity check
- Session Gate + Before-Writing-Code protocol apply here as well
- Time estimates: AI minutes only with confidence

If a section conflicts with CRITICAL_RULES.md, CRITICAL_RULES.md wins.

---


## 22. PROJECT CREATION PROTOCOL (MANDATORY)

**NEW PROJECT WORKFLOW:**

STEP 1: Planning Session
- Run: planning-session
- Define: Problem, constraints, success criteria
- AI consultation: Explore 3-5 approaches
- Decision: Score and select best approach

STEP 2: Complexity Assessment
- Simple: Single file, <200 lines, no dependencies
- Medium: 2-5 files, <1000 lines, 1-2 dependencies
- Complex: Multi-module, >1000 lines, database/API

STEP 3: Template-Based Creation
- Run: project-create-from-plan [planning-session-dir]
- Applies: Correct template (simple/medium/complex)
- Creates: Structured project + documentation
- Enables: Auto-checkpoint service

QUICK SCRIPT PATH (No Planning):
- For trivial scripts only: project-create-quick name "desc"
- Bypasses planning, creates minimal structure

RULES:
- NEVER: Run project-create directly (deprecated)
- ALWAYS: planning-session → project-create-from-plan
- EXCEPTION: project-create-quick for 1-file scripts

This protocol ensures proper project structure and planning discipline.

---

**TECHNICAL NOTE:**
Planning tools in /opt/tools/ are wrapper scripts (not symlinks) to preserve path context for schema resolution.
