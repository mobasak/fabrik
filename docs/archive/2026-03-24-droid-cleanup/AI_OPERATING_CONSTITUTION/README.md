# AI Spec Pipeline

A 3-stage system for going from idea → spec → plan → implementation without AI agents losing context.

**Integration:** This pipeline works alongside your existing `windsurfrules`. The pipeline defines *what* gets built; windsurfrules define *how* code is written.

---

## Stages vs Modes (How Work Is Controlled)

This system uses **two orthogonal control layers**:

* **Stages** define *what artifacts are produced and when*
* **Modes** define *how work is done, which agent is used, and who has authority*

### Stages (Lifecycle)

| Stage | Produces | Location |
|-------|----------|----------|
| 1 — Discovery | Complete spec | `/opt/<project>/spec_out/` |
| 2 — Planning | Implementation plan | `/opt/<project>/plan/` |
| 3 — Execution | Working code | `/opt/<project>/src/` |

Stages are about **outputs**, not behavior.

---

### Modes (Operating Control Layer)

Modes determine:

* which tool is allowed
* which model is allowed
* who decides vs who executes
* when escalation is required

| Mode | Name    | Purpose                       |
| ---- | ------- | ----------------------------- |
| 1    | Explore | Reduce uncertainty            |
| 2    | Design  | Decide structure and plan     |
| 3    | Build   | Implement working changes     |
| 4    | Verify  | Audit correctness and safety  |
| 5    | Ship    | Document and make recoverable |

**Important:**
Modes can change *within a stage*, especially during Stage 3 (Execution).

---

### Model & Tool Policy (Enforced)

| Mode        | Tool                      | Default Model            | Escalation        |
| ----------- | ------------------------- | ------------------------ | ----------------- |
| 1 — Explore | ChatGPT Web / Factory CLI | Gemini 3 Flash (0.2×)    | Sonnet 4.5        |
| 2 — Design  | Factory Droid CLI         | Claude Sonnet 4.5 (1.2×) | Claude Opus 4.5   |
| 3 — Build   | Windsurf Cascade          | SWE-1.5 (Free)           | GPT-5.1-Codex-Max |
| 4 — Verify  | Factory Droid CLI         | GPT-5.1-Codex-Max (0.5×) | Claude Opus 4.5   |
| 5 — Ship    | Factory CLI / Cascade     | Claude Haiku 4.5 (0.4×)  | Gemini 3 Flash    |

This policy is **mandatory**, not advisory.

---

### Spec Freeze Rule

Once Stage 3 (Execution) begins:

> **All spec documents are read-only.**
> Any requirement change requires returning to Stage 1 or Stage 2.

---

## The Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 1: Discovery (1-2 hours)                                      │
│ Tool: Claude.ai / ChatGPT                                           │
│ Input: Your idea + research from /opt/_research/<project>/          │
│ Output: Complete spec document                                      │
│ File: stage1_discovery_prompt.md                                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 2: Planning (30 min)                                          │
│ Tool: Traycer / Factory Droid                                       │
│ Input: Spec from Stage 1                                            │
│ Output: Phases → Tasks → Steps                                      │
│ File: stage2_traycer_prompt.md                                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STAGE 3: Execution (hours/days)                                     │
│ Tool: Windsurf Cascade (build) + Factory Droid (verify)             │
│ Input: One task at a time                                           │
│ Output: Working code                                                │
│ File: stage3_cascade_execution.md                                   │
└─────────────────────────────────────────────────────────────────────┘
```

## Why This Works

| Problem | Solution |
|---------|----------|
| AI forgets context | Fresh chat per task, full context in prompt |
| AI adds unwanted features | Strict task scope + constraints |
| AI makes inconsistent decisions | Single source of truth (spec docs) |
| AI doesn't know when to stop | Clear acceptance criteria |
| You lose track of progress | `tasks.md` tracks everything |

## Quick Start

### Pre-Project (BEFORE Stage 1)

Complete research phase per windsurfrules:
1. Create `/opt/_research/<project>/` folder
2. Use template: `/opt/_project_management/templates/docs/RESEARCH_TEMPLATE.md`
3. Evaluate tools, APIs, costs
4. Document selected approach

### Stage 1: Discovery
1. Open Claude.ai (or ChatGPT)
2. Paste contents of `stage1_discovery_prompt.md`
3. Have a 1-2 hour conversation about your product
4. AI produces the complete spec
5. Create project: `create-project.sh <n> "<description>"`
6. Save spec to `/opt/<project>/spec_out/SPEC.md`

### Stage 2: Planning
1. Open Traycer (or Factory Droid)
2. Paste contents of `stage2_traycer_prompt.md`
3. Add your spec from Stage 1
4. Tool generates implementation plan
5. Save to `/opt/<project>/plan/IMPLEMENTATION_PLAN.md`
6. Copy task structure to `/opt/<project>/tasks.md`

### Stage 3: Execution
1. Open Windsurf Cascade
2. For each task in `tasks.md`:
   - Open fresh chat
   - Paste task prompt (from plan)
   - Let Cascade complete it
   - Run Mode 4 verification with Factory Droid
   - Update `tasks.md`
   - Close chat, move to next task

## Folder Structure

```
/opt/<project>/
├── spec_out/                    # Stage 1 output (frozen after Stage 2)
│   ├── SPEC.md                  # Complete specification
│   ├── PRD.md                   # Product requirements (optional split)
│   ├── UI.md                    # UI specification
│   ├── DataModel.md             # Data model
│   └── Workflows.md             # Workflow definitions
├── plan/                        # Stage 2 output (frozen after Stage 3 starts)
│   ├── IMPLEMENTATION_PLAN.md   # Phased plan
│   └── task_prompts/            # Individual task prompts
│       ├── task_1.1.md
│       ├── task_1.2.md
│       └── ...
├── src/                         # Stage 3 output (or <package_name>/)
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── models/
│   ├── services/
│   ├── api/
│   └── utils/
├── tests/                       # Test files mirror src/
├── scripts/                     # Utility scripts + watchdogs
├── config/                      # Config files (yaml/json)
├── data/                        # Persistent data (gitignored)
├── .tmp/                        # Temp files (gitignored)
├── .cache/                      # Cache files (gitignored)
├── logs/                        # Log files (gitignored)
├── docs/                        # Documentation per windsurfrules
│   ├── README.md                # Doc index
│   ├── QUICKSTART.md
│   ├── CONFIGURATION.md
│   ├── TROUBLESHOOTING.md
│   ├── DEPLOYMENT.md
│   ├── BUSINESS_MODEL.md
│   ├── SERVICES.md              # If project has services
│   ├── guides/
│   └── reference/
│       ├── database.md
│       └── api.md
├── tasks.md                     # Progress tracker (root level)
├── README.md                    # Project overview
├── CHANGELOG.md                 # Version history
├── .env.example                 # Env template (committed)
├── .env                         # Actual env (gitignored)
├── Dockerfile                   # Container build
├── compose.yaml                 # Docker Compose
├── .dockerignore
├── Makefile                     # make dev, make docker-smoke, make test
├── pyproject.toml               # Python config
├── .python-version              # Python version
├── requirements.lock            # Locked deps
└── .pre-commit-config.yaml      # Pre-commit hooks
```

## Integration with Existing Rules

| This Pipeline | Existing windsurfrules |
|---------------|------------------------|
| Stage 1 Discovery | Uses research from `/opt/_research/` |
| Stage 2 Planning → `tasks.md` | tasks.md format per windsurfrules |
| Stage 3 task prompts | Include Before-Writing-Code Protocol |
| Mode 4 Verify | Uses self-review checklist + quality gate |
| Mode 5 Ship | Updates docs per keep-docs-in-sync rule |

## Files in This Package

| File | Purpose |
|------|---------|
| `stage1_discovery_prompt.md` | System prompt for discovery conversation |
| `stage2_traycer_prompt.md` | Prompt for Traycer/Droid to generate plan |
| `stage3_cascade_execution.md` | Instructions for Cascade execution + verification |
| `AI_OPERATING_CONSTITUTION.md` | Single-page quick reference |
| `README.md` | This file |

## Tips

1. **Pre-Project**: Complete research before Stage 1. Use `/opt/_research/<project>/`.
2. **Stage 1**: Don't rush. The spec quality determines everything downstream.
3. **Stage 2**: Review the plan. Adjust task sizes if too big/small.
4. **Stage 3**: One task per chat. No exceptions. Always verify with Droid.
5. **Recovery**: If Cascade goes off track, revert and restart fresh.

## Starting Your First Project

```bash
# 1. Complete research first
mkdir -p /opt/_research/myproject
cp /opt/_project_management/templates/docs/RESEARCH_TEMPLATE.md /opt/_research/myproject/

# 2. After research + Stage 1 discovery complete:
create-project.sh myproject "Brief description"

# 3. Create spec folders
mkdir -p /opt/myproject/{spec_out,plan/task_prompts}

# 4. Save your spec from Stage 1
# Save your plan from Stage 2
# Execute tasks per Stage 3
```

## Reference Docs

- Windsurf rules: `/opt/_project_management/windsurfrules`
- Droid usage: `/opt/_project_management/droid-exec-usage.md`
- Templates: `/opt/_project_management/templates/`
- Database strategy: `/opt/_project_management/docs/reference/DATABASE_STRATEGY.md`
- Port registry: `/opt/_project_management/PORTS.md`
- Master credentials: `/opt/fabrik/.env`
