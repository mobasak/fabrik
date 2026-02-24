# Traycer Templates (Integration Guide)

**Last Updated:** 2026-02-24

Templates and instructions for using Traycer.ai with Fabrik's spec pipeline. Traycer runs as a **Windsurf extension** (Windows 11 Pro) connecting to the WSL environment.

## What is Traycer?

Traycer is a spec-driven development orchestrator that:
- Runs as an IDE Extension (Windsurf).
- Interacts with WSL via CLI agents located in `~/.traycer/cli-agents/`.
- Reads your specification and generates phased implementation plans.
- Hands tasks to AI coding agents (like Cascade or droid exec).
- Verifies task completion.

## When to Use Traycer

Traycer prevents agent drift and preserves human intent using **Spec-Driven Development**. Instead of monolithic documents, it uses **Epic Mode** and **focused mini-specs** to guide agents.

| Scenario | Official Workflow | Description |
|----------|-------------------|-------------|
| Single-PR / Focused task | **Plan** | Creates a detailed, actionable implementation plan. |
| Complex / Multi-step project | **Phases** (Epic Mode) | Manages specs and tickets across a project lifecycle to prevent context loss. |
| Code Audit / Verification | **Review** | Structured workflow for code review tasks. |
| Trivial change (< 5 files) | *Skip Traycer* | Use `droid exec` directly. |

## WSL Environment Architecture

Traycer manages its configuration and data inside your WSL home directory at **`~/.traycer/`**:

- **`~/.traycer/cli-agents/`**: Shell scripts that Traycer executes (e.g., `Factory AI.sh`). Must be configured to point to `/opt/fabrik` instead of `/opt/proxy`.
- **`~/.traycer/prompt-templates/`**: The active templates Traycer uses for generating specs and verifying tasks.
- **`~/.traycer/app-assets/`**: **Main history database** (`app-assets.db`) - SQLite database storing all task history, phase progression, plan evolution, context preservation, and development decisions.
- **`~/.traycer/cache/`**: Cache database (`cache.db`) - SQLite database for caching.
- **`~/.traycer/epic-chat-transcripts/`**: Epic Mode chat conversation history.
- **`~/.traycer/yolo_artifacts/`**: YOLO Mode execution artifacts.

**Data Storage Location:** All Traycer data is stored locally on your machine at `~/.traycer/`, ensuring your development history and sensitive project information remain private and under your control.

## Phase Management & Automation

Traycer provides flexible phase management for evolving projects:
- **Phase Selection:** Select, refer to, or merge multiple phases at once.
- **Adding Phases:** Insert new requirements, testing, or refinement phases anywhere in the sequence.
- **Rearranging:** Drag-and-drop phases to adjust priorities based on new insights.

### ⚡ YOLO Mode for Phases (Full Automation)

YOLO Mode automates the entire phase workflow end-to-end. The entire cycle (Planning → Coding → Verification → Next phase) runs without manual intervention using your predefined configuration.

**Two automation levels:**

**Regular YOLO** (Phases Mode):
- Fixed configuration set upfront
- Applies same settings consistently across all selected phases
- You define: agents, templates, verification levels, timeouts, auto-commit behavior
- Settings remain unchanged throughout execution

**Smart YOLO** (Epic Mode):
- Uses same underlying configuration options as Regular YOLO
- **But the orchestrator goes beyond configuration** — it evolves your Epic based on implementation learnings:
  - **Epic Evolution:** Updates specs and tickets based on implementation discoveries, refines acceptance criteria and requirements, steers plans by splitting/merging/reordering work items, propagates learnings from one execution to inform subsequent ones
  - **Dynamic Configuration:** The orchestrator analyzes each task, learns from implementation progress, and optimizes both Epic content AND execution settings (skip/generate plans, select agents, choose templates, adjust timeouts, configure verification severity, select review categories, enable/disable verification, enable/disable auto-commits, configure custom commit scripts)
- The orchestrator makes these decisions based on the specific context of each task

#### How It Works

YOLO Mode works with two types of workflows:

**Plan Workflow** (for implementation tasks):
1. **Planning** — Traycer generates detailed plans or skips directly to coding (based on your config)
2. **Coding** — Automatically hands off to your selected coding agent with optional custom templates
3. **Verification** — Validates implementation and optionally hands off selected comment categories back to your agent
4. **Next phase** — Continues to the next phase automatically until all phases are complete

**Review Workflow** (for code review tasks):
1. **Review** — Traycer analyzes code and generates review comments
2. **Coding** — Automatically hands off review comments to your selected coding agent for fixes
3. **Next phase** — Continues to the next phase automatically until all phases are complete

#### Activating YOLO Mode

1. **Create a Phases task** — Start with Phases Mode
2. **Click YOLO Mode button** — Once phases are displayed in Kanban board view
3. **Select phase range** — Use side slider to choose which phases to automate (current phase to any future phase)
4. **Configure automation settings** — Set preferences (see Configuration Options below)
5. **Start automation** — Confirm and let Traycer run the entire workflow

#### Configuration Options

**Both Regular YOLO and Smart YOLO use the same underlying configuration options.** The difference:
- **Regular YOLO:** You set these configurations upfront and they remain fixed throughout execution
- **Smart YOLO:** The orchestrator dynamically adjusts these settings based on task analysis and implementation learnings

**1. User Query Handoff**

Skip detailed planning and send the phase query directly to your coding agent.

**When to use:**
- Simple, straightforward implementation tasks
- Phase query is already detailed enough for direct coding
- Speed priority over structured guidance

**Configuration:**
- **Skip plan generation:** Check this to bypass detailed plan generation for this phase
- **Execution Agent:** Choose from YOLO-compatible agents (⚡)
- **Template:** Optionally apply a custom user query template to wrap the query with additional instructions (testing requirements, coding standards, etc.)

**2. Plan Handoff** (default mode)

Generate a detailed plan and automatically hand it off to your coding agent.

**When to use:**
- Complex implementations requiring structured guidance
- You want agents to follow specific architecture patterns
- Tasks where detailed file-level plans improve code quality

**Configuration:**
- **Execution Agent:** Choose from YOLO-compatible agents (⚡)
- **Template:** Optionally apply a custom plan template to include project-specific instructions, testing requirements, or coding standards
- **Execution Timeout:** Configure how long the agent has to complete the task
- **Auto-commit:** Enable/disable automatic commits after successful execution
- **Custom Commit Script:** Configure custom commit scripts for specialized workflows

**3. Verification Handoff**

After Traycer verifies the agent's implementation, automatically send selected comment categories back to the agent for fixes.

**When to use:**
- Automatically iterate on critical and major issues
- Maintain quality standards across all phases
- Polish implementations before moving to next phase

**Configuration:**
- **Skip verification:** Check this to bypass verification for this phase
- **Execution Agent:** Choose from YOLO-compatible agents (⚡)
- **Template:** Optionally apply a custom verification template to provide fix instructions
- **Severity levels to verify** (multiple selections allowed):
  - **Critical:** Blocks core functionality or plan requirements
  - **Major:** Significant issues affecting behavior or UX
  - **Minor:** Small polish items that don't block functionality
- **Execution Timeout:** Configure how long the agent has to complete fixes
- **Auto-commit:** Enable/disable automatic commits after successful fixes

**Tip:** Select multiple severity levels to balance quality and speed. For example, selecting only Critical and Major ensures agents address serious issues while skipping minor polish items.

**4. Review Handoff** (Review workflow only)

For Review workflow tasks, automatically hand off review comments to your coding agent for fixes.

**When to use:**
- Working with Review workflow tasks in YOLO Mode
- Automatically address code review feedback
- Maintain code quality standards through automated review cycles

**Configuration:**
- **Execution Agent:** Choose from YOLO-compatible agents (⚡)
- **Template:** Optionally apply a custom review template to provide fix instructions
- **Review categories:** Choose which review categories to hand off (multiple selections allowed)
- **Execution Timeout:** Configure how long the agent has to complete fixes
- **Auto-commit:** Enable/disable automatic commits after successful fixes

**Note:** Review handoff is only available for tasks created with the Review workflow.

#### Managing Agents and Templates

**Agents:**

YOLO Mode only works with **YOLO-compatible agents** (marked with ⚡) that support automated execution. These agents must be configured in your workspace settings.

- **Available agents:** Must be configured in Settings → Additional agents
- **Built-in support:** Custom CLI Agents, Claude Code CLI, Codex CLI, Gemini CLI
- **Custom CLI Agents:** For more control over CLI-based agents, create Custom CLI Agents with custom arguments, permissions, and special flags (e.g., `--dangerous`, custom paths)
- See the Supported Coding Agents section for complete list and configuration instructions

**Templates:**

Templates **wrap Traycer's generated content with your custom instructions**. This allows you to maintain consistent project standards across automated executions.

**How templates work:**
- Traycer generates the core content (plan, verification comments, review feedback)
- Your template wraps this content with additional instructions
- The combined prompt is sent to the coding agent

**Template types:**
- **User query template:** Wraps the phase query with project context, testing requirements, coding standards
- **Plan template:** Wraps generated plans with architecture guidelines, file organization rules, quality requirements
- **Verification template:** Wraps fix instructions with debugging approaches, testing requirements, commit message standards
- **Review template:** Wraps review feedback with fix priorities, refactoring guidelines, documentation requirements

**Creating templates:** See Templates documentation for detailed instructions on creating and managing custom templates.

#### Preventing Interruptions

**Artifact Slots and Rate Limits:**
- YOLO Mode consumes artifact slots as it progresses
- If you run out of slots, YOLO Mode pauses until slots are available
- **Recommendation:** Enable automatic instant refills in VS Code settings ($0.50/slot)
- You'll need to manually resume after slots are refilled

**Keep Screen Active:**
- YOLO Mode requires active IDE connection
- Automation stops if computer sleeps or screen times out
- **Recommendations:** Disable sleep/timeout during execution, keep IDE window visible

#### FAQ

**Q: What happens if YOLO Mode hits a rate limit?**

A: YOLO Mode will pause when you run out of artifact slots. You can either:
- Wait for slots to recharge based on your plan's recharge rate
- Use instant refills ($0.50 per slot)
- Enable automatic instant refills in VS Code settings (recommended to avoid interruptions)

Once slots are available, you'll need to manually resume YOLO Mode from where it stopped.

**Q: Can I change configuration while YOLO Mode is running?**

A: Yes, but only for phases that haven't started yet. You can modify configuration for upcoming phases while YOLO Mode is running. However, you cannot change settings for:
- The currently executing phase
- Phases that have already completed

To adjust settings for future phases, update your configuration and the changes will apply when those phases begin.

**Q: Can I use different agents for different phases?**

A: Yes! Each phase can be configured with its own coding agent selection. This allows you to use specialized agents for specific types of work. For example:
- Use one agent for frontend phases
- Use another agent for backend phases
- Use a different agent for database migration phases

**Q: What if my computer goes to sleep during execution?**

A: YOLO Mode will stop if your computer sleeps or the screen times out. Make sure to disable sleep/timeout settings before starting long automation runs. You can resume from the last completed step once your computer wakes up.

**Q: Does YOLO Mode work with all coding agents?**

A: No. YOLO Mode only works with YOLO-compatible agents (marked with ⚡) that support automated execution. Other agents require manual interaction and are not compatible with YOLO Mode's automated workflow. See the Supported Coding Agents section for the complete list.

**Q: How do templates work with YOLO Mode?**

A: Templates wrap Traycer's generated content with your custom instructions. You can select different templates for:
- User query handoff
- Plan handoff
- Verification handoff
- Review handoff

This allows you to maintain consistent project standards (testing requirements, coding conventions, commit message formats) across automated executions. Learn more in the Templates documentation.

**Q: What's the difference between user query handoff and plan handoff?**

A: **User query handoff:**
- Skips detailed planning
- Sends the phase query directly to the agent
- Faster execution
- Provides less structured guidance
- Best for simple, straightforward tasks

**Plan handoff:**
- Generates a detailed implementation plan first
- Then hands the plan to the agent
- Takes more time
- Provides better structure and file-level guidance
- Reduces agent drift and improves code quality
- Best for complex implementations

Choose based on task complexity and how much guidance your agent needs.

**Q: Can I use Custom CLI Agents with YOLO Mode?**

A: Yes! Custom CLI Agents that use YOLO-compatible CLI tools (like Claude Code CLI, Codex CLI, or Gemini CLI) work seamlessly with YOLO Mode. You can create custom templates with special flags like `--dangerous` or custom paths, and they'll appear in the agent selection dropdown. Learn more in the Custom CLI Agents documentation.

## Epic Mode (Specs, Tickets, Artifacts)

Epic Mode is designed to preserve human intent from initial idea to implementation. Instead of one giant document, it uses focused mini-specs that each address a specific aspect of your project.

Epic Mode manages **artifacts**: structured documents that form a system of interconnected specs and tickets; in the Epic UI you may also see **Executions** listed under Artifacts as the audit trail of handoffs and outcomes.

### Specifications (Specs)

Specs are focused, high-level documents that capture requirements, design decisions, and technical planning. They provide the “why” and “what” of your project.

Common spec types:
- PRD (Product Requirements Document)
- Tech Doc
- Design Spec
- API Spec

Specs are living documents: when requirements change, update the relevant mini-spec instead of rewriting everything.

### Tickets

Tickets are actionable work items that break down specs into concrete implementation tasks. Each ticket represents a focused unit of work that can be independently implemented.

Ticket characteristics:
- Contains clear acceptance criteria
- Tracks status: Todo → In Progress → Done
- Can be handed off to coding agents for implementation

### How Epic Mode Works

1. Choose a Workflow.
2. Start with requirements: provide your requirements, problem statement, or goals to the workflow’s entrypoint command.
3. Follow the workflow’s commands. Epic Mode emphasizes dialogue and elicitation: the AI doesn’t just generate documents — it actively asks pointed questions to surface constraints, edge cases, and the “invisible rules” behind your requirements.

During this process, the AI will:
- Ask clarifying questions to understand your intent deeply
- Help you make explicit decisions instead of leaving ambiguity
- Propose and create specification documents (mini-specs)
- Generate actionable tickets for implementation
- Guide you through additional workflow-specific steps

4. Once you have the specs and tickets you need, select them and hand off for implementation. Verification is built into Traycer’s implementation modes to continuously validate that execution matches your captured intent.

### Executions (Audit Trail)

Executions provide complete visibility into every agent handoff within your Epic. Each execution represents a discrete unit of work sent to a coding agent, capturing the full lifecycle from handoff to completion.

What gets tracked:
- Plans generated during execution (if any)
- Verification comments and post-execution review results
- Commit created after successful execution
- Status (running, completed, verification pending, etc.)

Viewing executions:
- Execution history: every handoff (manual and automated)
- Execution details: full context, what was handed off, and verification results
- Real-time updates: progress as agents work

### Concept Map (How the Pieces Relate)

- **Workflow**: A prescribed sequence of commands/steps in Traycer (e.g., Plan/Phases/Review/Epic) that guides you from requirements to verified implementation.
- **Artifacts**: The structured items Epic Mode manages. The core artifact types are **Specs** and **Tickets**, and the Epic UI may also show **Executions** under Artifacts as the audit trail of handoffs and outcomes.
- **Spec**: A focused mini-spec capturing the “why” and “what” (PRD/Tech Doc/Design Spec/API Spec). Specs evolve over time.
- **Ticket**: A concrete unit of work derived from one or more specs, with acceptance criteria and a status (Todo → In Progress → Done).
- **Phase**: An ordered milestone grouping in Traycer for a project lifecycle (you can add/reorder phases; phases typically contain multiple tickets).
- **Plan**: A detailed, file-level implementation approach (often produced from a ticket/spec during planning) that drives execution.
- **Task**: A single execution-unit handed to a coding agent (often equivalent to “implement this ticket” or a slice of a ticket).
- **Execution**: The recorded handoff/run of a task to an agent, including plan (if generated), verification comments, commit, and status.

### Smart YOLO for Epic Mode (Intelligent Orchestration)

Smart YOLO brings intelligent orchestration to Epic Mode, automatically executing entire Epics end-to-end while adapting specs, tickets, and plans based on implementation discoveries. **It can run multiple executions in parallel when safe to do so, dramatically reducing overall execution time.** Unlike fixed automation, Smart YOLO learns from each execution and steers the Epic dynamically with minimal human intervention.

**Agent Selection:** Smart YOLO can only select from YOLO-compatible agents (marked with ⚡) that are configured in your workspace settings. The orchestrator dynamically chooses the most appropriate agent for each phase based on the task context.

#### What Smart YOLO Does

1. **Evolves your Epic dynamically** — Updates specs and tickets at runtime based on implementation discoveries, refining requirements and acceptance criteria as the codebase reveals constraints or opportunities

2. **Steers execution strategy** — Analyzes implementation progress and adaptively adjusts plans, breaking down complex tickets or merging related work items as needed

3. **Runs executions in parallel** — Intelligently determines which specs and tickets can be executed concurrently without conflicts, significantly reducing overall execution time for independent work items

4. **Creates Executions** — Each handoff to a coding agent is tracked as an Execution in your Epic, providing full visibility into plans, verification results, commits, and status

5. **Makes smart handoffs** — Determines optimal execution strategy for each task based on dependencies and implementation context

6. **Adapts all execution settings** — Adjusts plans, agents, templates, verification, timeouts, and commits based on requirements and implementation context

7. **Runs verification loops** — Validates changes match intent after each execution

8. **Coordinates iterative refinement** — If verification finds issues or implementation reveals scope changes, orchestrates fixes, plan adjustments, and re-verification

9. **Maintains context** — Preserves Epic context throughout the entire execution chain, using learnings from one execution to inform subsequent ones

10. **Propagates learnings** — Uses discoveries from one execution to update specs, refine tickets, and optimize subsequent executions

#### Triggering Smart YOLO

To start automated execution in Epic Mode:
- Use the **`/execute` command** in the Epic chat, or
- Simply **tell Traycer to execute** your tickets or specs (e.g., "Execute these tickets")

Smart YOLO will take over from there, coordinating the entire execution process.

#### When to Use Smart YOLO

Smart YOLO is ideal when:
- You have specs and tickets ready for implementation (even if they need refinement during execution)
- You want to execute multiple tickets with minimal manual coordination
- You expect implementation to reveal scope changes or technical constraints
- You want an orchestrator that **adapts to discoveries** rather than blindly following a fixed plan
- You trust your coding agents to handle implementation details while Smart YOLO steers overall strategy
- You want automatic verification after each execution
- You want full execution tracking with plans, verification results, and commits

**You describe the Epic and its requirements. Smart YOLO coordinates the rest** — adapting specs, steering plans, and managing execution through verification. All handoffs are tracked as Executions in your Epic view for complete visibility.

#### Auto-Commit Configuration

You can configure Smart YOLO to automatically commit changes after successful execution, creating a clean commit history as your Epic progresses.

#### Smart YOLO FAQ

**Q: Can Smart YOLO execute multiple specs/tickets in parallel?**

A: Yes! Smart YOLO intelligently parallelizes execution to maximize speed while ensuring correctness. It analyzes your Epic to determine:
- Which specs or tickets are independent and can run concurrently
- Which work items have dependencies that require sequential execution
- How to batch related changes to avoid conflicts

This parallel execution capability can dramatically reduce overall execution time for Epics with multiple independent work streams.

**Q: Can I override Smart YOLO's configuration decisions?**

A: Smart YOLO operates autonomously with the `/execute` command. If you need more control over specific configurations, you can use **manual handoff options** from the Epic view where you can specify exact settings for each execution.

**Q: What happens if an execution fails?**

A: Smart YOLO monitors execution results and coordinates fixes:
- If verification finds issues, it can automatically hand off fixes to agents
- If an execution fails, Smart YOLO pauses to allow you to address the issue
- You can resume Smart YOLO after resolving failures
- All execution results are tracked in the Executions view within your Epic

**Q: Does Smart YOLO work with all agents?**

A: No. Smart YOLO only works with YOLO-compatible agents (marked with ⚡) that are configured in your workspace settings. The orchestrator dynamically selects from these configured agents based on the task requirements.

**Q: Can Smart YOLO modify my specs and tickets during execution?**

A: Yes! **This is a key differentiator of Smart YOLO.** Unlike fixed automation, Smart YOLO can:
- Update specs and tickets based on implementation discoveries
- Refine acceptance criteria when the codebase reveals constraints
- Add or modify requirements as execution uncovers scope changes
- Split complex tickets or merge related ones based on actual implementation needs

All updates are tracked in your Epic, so you have full visibility into how specs and tickets evolved during execution. This adaptive approach produces better results than rigidly following initial specs that may not account for implementation realities.

### Verification (Managing Review Comments)

Traycer's verification process ensures that agent's implementation meets your requirements and follows your original plan. When issues are found, it generates actionable review comments that can be handed back to agents for fixes and iterative improvements.

#### How Verification Works

Traycer analyzes agent's implementation against your original plan and creates categorized review comments for any issues found. These comments can be handed off to your preferred agent for iterative fixes and improvements.

#### Verification Comment Categories

Traycer organizes verification comments by priority level to help you focus on the most important issues first:

- **Critical** — Blocks core functionality or plan requirements and must be fixed first
- **Major** — Significant issues that affect behavior or UX but may have workarounds
- **Minor** — Small polish items that don't block functionality
- **Outdated** — Comments that are no longer relevant due to changes in the implementation

#### Fixing Verification Comments

You have three options for addressing verification comments:

**1. Fix individual comments**

Use the coding agent icon button next to each comment to address specific issues one at a time.

**2. Fix selected comments**

Enable selection mode to choose multiple comments, then send the selected comments to your agent for fixing.

**3. Fix all comments**

Use the **Fix all in** button to have your agent address all verification comments at once.

#### Verification Options

Choose between focused re-verification or complete fresh verification based on your needs:

**Re-verify:**
- Focused pass that checks whether previously identified issues are resolved
- Faster and ideal for iterative cycles
- Checks if specific comments have been addressed

**Fresh Verification:**
- Full re-analysis that ignores old comments and reassesses the whole implementation
- Comprehensive evaluation of current state
- Generates new verification comments based on current implementation vs original plan

### Managing Specs and Tickets (Documents Panel)

Epic Mode provides artifact management via the Documents panel:

**Specs**
- Create: Generate via AI-assisted conversation or use the `+ Add Spec` button
- View & Edit: Select a spec to view and edit contents
- Organize: Specs are grouped in the **SPECS** section

**Tickets**
- Create: Break work into actionable tickets or use the `+ Add Ticket` button
- View & Edit: Select a ticket to view and edit contents
- Status tracking: Todo → In Progress → Done
- Organize: Tickets are grouped in the **TICKETS** section
- Collaboration: Team collaboration for distributing work is coming soon

### Selection and Handoff

Use the **Select** button to enter selection mode and choose specific specs and tickets. Once selected, you can:
- Refer in chat: reference selected artifacts in conversation
- Execute in phases: hand off to Phases mode for implementation
- Handoff to: send to your preferred coding agent

### Mermaid Diagrams (Interactive Workflow Visualizations)

Traycer automatically generates **interactive Mermaid diagrams** with implementation plans, providing visual representations of workflows, dependencies, and system architecture.

**What Mermaid diagrams help visualize:**
- **Multi-step processes:** Sequential workflows and dependencies
- **System interactions:** How different components connect and communicate
- **Decision flows:** Conditional logic and branching paths
- **Data flows:** Input/output transformations and state changes

**Interaction Options:**

**1. Copy Diagram Text**

Click the **"Copy Diagram" button** to copy the raw Mermaid diagram code to your clipboard. Useful for:
- Pasting into documentation
- Sharing with team members
- Using in other Mermaid-compatible tools

**2. Full-Screen View**

Click the **"Open Diagram" button** to open it in a full-screen PNG view for better visibility and interaction:
- **Better readability:** View complex diagrams without scrolling
- **Copy as image:** Right-click on the full-screen diagram and select "Copy" to copy it as a PNG image
- **Perfect for presentations:** Easily include visual workflows in slides or documents

## Workflows (Epic Mode Command Sequences)

Workflows are the backbone of Epic Mode. They are structured command sequences that guide you through development tasks, from requirements gathering to implementation.

### What is a Workflow?

A workflow is a collection of **command files** that guide you through a development process. Each workflow consists of:
- **Name & Description**: Identify the workflow and its purpose
- **Entrypoint Command**: The starting point (default: `trigger_workflow`, customizable)
- **Command Files**: Additional steps in your process

Workflows are used within Epic Mode to structure your development process.

### Command Structure

Each command in a workflow has:
1. **Description**: Brief explanation shown when users type `/` to select commands
2. **Argument Hints**: Optional hints for what information should be passed (e.g., "Feature name", "Technology")
3. **Next Steps**: Define which commands can follow (enables multi-path workflows)
4. **Agent Mode**: Planner (strategic thinking) or Reviewer (evaluation/quality)

### Using Workflows

**Triggering a workflow:**
1. Select a workflow from the dropdown when creating or working in an Epic:
   - Your custom workflows
   - Traycer Agile Workflow (default)
   - No Workflow (run without structure)
2. Type `/` in chat to see all available commands from your selected workflow
3. Select a command (e.g., `/trigger_workflow`, `/epic-brief`)
4. Provide context after the command — the slash becomes regular text, allowing you to add requirements

**Note:** Only one command per query.

**Using arguments:**
Commands can accept arguments using `$1`, `$2`, etc. Example:
```
/create-feature User authentication OAuth2 and JWT
```
Maps to:
- `$1` = "User authentication"
- `$2` = "OAuth2 and JWT"

### Traycer Agile Workflow (Default)

The default workflow that guides you through feature development with a collaborative, spec-driven approach organized in **3 gated phases**:

**Requirements Phase:**
1. **`/trigger_workflow`** (Entrypoint) — Requirements gathering through structured interviewing (readonly, no artifacts)
2. **`/epic-brief`** — Define problem and context (creates Epic Brief: Summary + Context & Problem, <50 lines)
3. **`/core-flows`** — Map user flows and interactions (creates Core Flows: each flow <30 lines)
4. **`/prd-validation`** — Requirements validation gate (validates + updates Epic Brief and Core Flows)

**Architecture Phase:**
5. **`/tech-plan`** — Create technical implementation plan (creates Tech Plan: 3 sections, <100 lines each)
6. **`/architecture-validation`** — Architecture validation gate (stress-tests critical decisions, updates Tech Plan)

**Execution Phase:**
7. **`/ticket-breakdown`** — Break down work into actionable tickets (creates Tickets with dependencies)
8. **`/implementation-validation`** — Implementation validation gate (validates code vs specs, creates bug tickets)

**Workflow Philosophy:**
- **Collaboration First**: Discuss and align before drafting artifacts
- **Questions as Investments**: Clarification prevents costly mistakes
- **Shared Understanding**: Multiple rounds of questions is normal
- **Readable Artifacts**: Optimize for human parsability

**Workflow Commands:**

1. **`/trigger_workflow`** — Initial requirements gathering
   - Discuss user's request and goals
   - Ask clarifying questions
   - Build shared understanding
   - No assumptions — alignment first
   - **Next Steps:** `epic-brief` or `core-flows`

2. **`/epic-brief`** — Define problem and context
   - Capture who's affected and current pain points
   - Document the problem at a product level
   - Create concise Epic Brief spec (under 50 lines)
   - No UI specifics or technical design yet
   - **Next Steps:** `core-flows`

3. **`/core-flows`** — Map user flows and interactions
   - Explore current product flows
   - Design UX decisions (information hierarchy, user journeys)
   - Document step-by-step user actions
   - Include wireframes or ASCII sketches
   - **Next Steps:** `tech-plan` or `ticket-breakdown`

4. **`/tech-plan`** — Create technical implementation plan
   - Define architecture and technical approach
   - Identify files and components to modify
   - Document technical decisions and rationale
   - Reference existing code patterns
   - **Next Steps:** `ticket-breakdown`

5. **`/ticket-breakdown`** — Break down work into actionable tickets
   - Create independently implementable tickets
   - Link tickets to relevant specs
   - Define acceptance criteria
   - Prioritize and sequence work
   - **Next Steps:** Implementation via Phases, Plan, or Agent handoff

**Validation Gates:** Three additional validation commands ensure quality at each phase:
- **`/prd-validation`** — Validates and updates Epic Brief + Core Flows (requirements gate)
- **`/architecture-validation`** — Validates and updates Tech Plan (architecture gate)
- **`/implementation-validation`** — Validates code vs specs, creates bug tickets (implementation gate)

**For complete command details** (roles, acceptance criteria, artifact structures, processing flows, validation gate mechanics), see:
- [Traycer Agile Workflow (Detailed Reference)](../../docs/reference/traycer-agile-workflow.md)

### Traycer Refactoring Workflow

A collaborative workflow for safe, intentional code refactoring organized in **4 commands**:

1. **`/trigger-workflow`** (Entrypoint) — Understanding before changing
   - Build shared understanding of code area to refactor
   - Validate stated problem matches code reality (ask clarifying questions if mismatch found)
   - Establish clear scope boundaries (what's in, what's out, risk level)
   - **Output:** 50-word summary (code area, validated problem, scope, risk level)
   - **Next Steps:** `plan-refactor`

2. **`/plan-refactor`** — Thorough analysis + collaborative approach
   - **Part 1: Analysis** → Creates `refactoring-analysis.md` (dependency map, risk hotspots, test coverage, change surface)
   - **Part 2: Approach** → Creates `refactoring-approach.md` after clarification (key decisions, target state, component architecture, invariants, test strategy)
   - Philosophy: "Blast radius first, surface risks early, decisions need buy-in, thoroughness is a feature"
   - **Next Steps:** `ticket-breakdown`

3. **`/ticket-breakdown`** — Translate approach into executable work units
   - Sequence tickets to minimize risk (tests first if needed, foundation before dependents)
   - Each ticket: Scope, References (to Analysis/Approach), Guardrails (invariants), Acceptance Criteria, Verification Steps
   - Anti-pattern: Don't over-breakdown (minimal least set is better)
   - **Next Steps:** Implementation via Phases, Plan, or Agent handoff

4. **`/verification`** — Quality gate with feedback loop
   - Check implementation against Analysis and Approach documents
   - Identify drift, missed areas, or unintended changes
   - Three paths: (A) Approve and close, (B) Create fix tickets, (C) Escalate to re-plan
   - Philosophy: "Planning can't anticipate everything; implementation reveals realities"

**Refactoring Philosophy:**
- **Understanding before changing**: Know what you're working with
- **Validate assumptions early**: Problem might be different than it appears
- **Clear boundaries prevent scope creep**: Small validated steps beat big-bang rewrites
- **Feedback loop**: New information from implementation improves the plan

**Artifacts created:**
- `refactoring-analysis.md` — Current state analysis (dependencies, risks, test coverage)
- `refactoring-approach.md` — Technical decisions and target architecture
- Tickets — Sequenced work units with guardrails and verification

### Custom Workflows

You can create custom workflows tailored to your team's methodology:

**Creating a workflow:**
1. Click `+ Add Workflow` in the Workflows panel
2. Enter a Name and Description
3. An entrypoint command is automatically created (default: `trigger_workflow`)

**Adding commands:**
1. Click `+ Add Command` in the Workflow Commands panel
2. Give it a descriptive name (becomes the file name)
3. Configure description, argument hints, next steps, and agent mode
4. Write command instructions in markdown (can reference `$1`, `$2`, etc.)

**Managing workflows:**
- **View**: Access via Workflows panel or Epic workflow selector
- **Clone**: Default workflows are read-only but can be cloned for customization
- **Edit**: Custom workflows are fully editable (changes save automatically)
- **Delete**: Custom workflows can be deleted; default workflows cannot

**Agent Modes:**
- **Planner Mode**: Strategic thinking, extended reasoning, ideal for creating specs/designs
- **Reviewer Mode**: Evaluation/quality assessment, ideal for validation/critique

### Multi-Path Workflows

Use **Next Steps** to create workflows with alternative paths. The AI will suggest or let the user choose from configured next commands based on context.

Example: A command might have multiple next steps:
- `design-review` — for UI-heavy features
- `tech-plan` — for backend features
- `spike-investigation` — for uncertain requirements

## History (Task & Phase Tracking)

Traycer automatically preserves the complete history of all your tasks and phases, allowing you to review, revert, or continue from any previous state.

### What is Preserved

Traycer maintains a comprehensive record of your development workflow:

- **Task history:** Complete timeline of all generated tasks and their iterations
- **Phase progression:** Step-by-step history of multi-phase projects
- **Plan evolution:** How your implementation plans changed over time
- **Context preservation:** All decisions, file mappings, and rationale from previous sessions

### Finding Your Tasks

The Task History interface provides powerful tools to locate and manage your development history:

**Fuzzy search:**
- Quickly find tasks using partial matches across task titles and queries

**Workspace filtering:**
- **Current Workspace:** Show only tasks from your active workspace
- **All Workspaces:** Display tasks from all your workspaces for a complete overview

### History Data Storage

**Where is my data stored?**

All history is stored locally on your machine at **`~/.traycer/app-assets/app-assets.db`** (SQLite database), ensuring your data stays private.

**Is my data secure?**

Yes. Since all data remains on your local machine at `~/.traycer/`, you maintain complete control over your development history and sensitive project information.

**What happens if I reinstall Traycer?**

Your history persists across Traycer installations as long as your local data directory (`~/.traycer/`) remains intact.

## Supported Coding Agents

Traycer hands off clean, actionable prompts to your preferred AI coding agents.

### Built-in YOLO Mode Support ⚡

These agents have **native YOLO Mode automation**:
- **Custom CLI Agents** — Fabrik uses this for async job submission via `~/.traycer/cli-agents/Factory*.sh`
- **Claude Code CLI**
- **Codex CLI**
- **Gemini CLI**

### Configurable as Custom CLI Agents

**Any CLI-based coding agent** can be configured as a Custom CLI Agent to enable YOLO Mode automation. Examples include:
- Cursor (if using CLI)
- Cline (if using CLI)
- KiloCode (if using CLI)
- RooCode (if using CLI)
- Amp (if using CLI)
- ZenCoder (if using CLI)

Configure via Settings → Additional agents → Add item → Custom CLI Agent

### IDE Extension-Only Agents

These agents currently have **extension-only interfaces** and require manual handoff:
- Claude Code Extension
- Codex Extension
- Windsurf Extension
- Antigravity Extension
- Augment Extension

**Note:** The distinction is CLI availability, not agent capability. If an agent offers a CLI interface, it can be configured as a Custom CLI Agent for YOLO Mode automation.

### Export Options

**Copy** (always available)
- Copy prompts directly to clipboard for immediate use
- Available in Execute dropdown

**Export as markdown** (configurable)
- Generate clean markdown file with complete prompts
- Can be shared or used as documentation
- Configure via Settings → Additional agents → Add item

### Fabrik Integration

Fabrik uses **Custom CLI Agents** for async job submission:
- `Factory Submit (async).sh` — Submits jobs to `/opt/fabrik/factory_submit.py`
- `Factory Wait (async).sh` — Monitors jobs via `/opt/fabrik/factory_wait.py`
- `Factory AI.sh` — Direct execution wrapper

These agents are configured in `~/.traycer/cli-agents/` and enable YOLO Mode automation with Fabrik's 9-step workflow.

## AGENTS.md Integration (Project-Specific Context)

Traycer automatically detects and uses `AGENTS.md` files to enhance AI task execution with project-specific context—no configuration required.

### What is AGENTS.md?

`AGENTS.md` is an open standard that provides AI coding agents with machine-readable, project-specific instructions. Unlike `README.md` files designed for human developers, `AGENTS.md` focuses on giving AI agents clear guidance about:
- Build processes and testing procedures
- Coding conventions and style guidelines
- Architectural patterns and design decisions
- Project structure and component organization

### How Traycer Uses AGENTS.md

When you create a Task, Traycer automatically searches for `AGENTS.md` files to gather project context:

1. **Finds the nearest AGENTS.md** — Starts from the location of attached file references or the current working directory during exploration
2. **Traverses to workspace root** — Continues up the directory tree if no `AGENTS.md` is found nearby
3. **Incorporates into Task context** — Uses the instructions to inform plan generation and execution

**This means:**
- Place `AGENTS.md` at your repository root for project-wide instructions
- Add nested `AGENTS.md` files in subdirectories for component-specific guidance (ideal for monorepos)
- No manual configuration needed—detection happens automatically

### What This Means for Your Tasks

When Traycer finds an `AGENTS.md` file, it uses the project-specific instructions to:
- **Generate more accurate plans** — Understands your project's structure, conventions, and patterns
- **Follow your standards** — Respects your team's coding style, testing requirements, and workflows
- **Reduce iterations** — Creates plans aligned with your project from the start
- **Support monorepos** — Uses the most relevant `AGENTS.md` based on your working directory

The result is faster, more accurate Task execution that respects your project's unique requirements.

### Industry Standard

`AGENTS.md` is supported by AI coding tools including Cursor, GitHub Copilot, Factory, Codex, Jules, and others. By adding an `AGENTS.md` file to your repository, you provide consistent instructions across all these tools.

**Learn more:** [agents.md](https://agents.md) (official standard documentation)

### Disabling AGENTS.md Detection

You can disable `AGENTS.md` detection at any time in your Traycer settings if you prefer not to use this feature.

## Custom CLI Agents (Advanced Integration)

Create custom CLI agents with custom arguments and permissions for any CLI-based coding agent. This powerful feature enables you to pass special flags and create platform-specific configurations tailored to your workflow.

### What are Custom CLI Agents?

Custom CLI agents allow you to:
- **Execute any CLI-based coding agent** with custom arguments
- **Pass special flags** like `--dangerous` or `--force` for elevated permissions
- **Create platform-specific CLI agents** for different environments (WSL, macOS, Windows)
- **Maintain session state** across plan generation, execution, and verification using Traycer identifiers

### Available Environment Variables

Traycer sets the following environment variables at runtime that you can use in your custom CLI agent scripts:

| Variable | Bash / Git Bash | PowerShell | Description |
|----------|-----------------|------------|-------------|
| `TRAYCER_PROMPT` | `"$TRAYCER_PROMPT"` | `"$env:TRAYCER_PROMPT"` | **Required.** The prompt content. At least one of `TRAYCER_PROMPT` or `TRAYCER_PROMPT_TMP_FILE` must be referenced. |
| `TRAYCER_PROMPT_TMP_FILE` | `"$TRAYCER_PROMPT_TMP_FILE"` | `"$env:TRAYCER_PROMPT_TMP_FILE"` | Temporary file path containing prompt content. Use for large prompts exceeding environment variable size limits. |
| `TRAYCER_PHASE_ID` | `"$TRAYCER_PHASE_ID"` | `"$env:TRAYCER_PHASE_ID"` | Per-phase identifier for maintaining session across plan and verification. |
| `TRAYCER_PHASE_BREAKDOWN_ID` | `"$TRAYCER_PHASE_BREAKDOWN_ID"` | `"$env:TRAYCER_PHASE_BREAKDOWN_ID"` | Phase breakdown identifier for maintaining session across current phase list. |
| `TRAYCER_TASK_ID` | `"$TRAYCER_TASK_ID"` | `"$env:TRAYCER_TASK_ID"` | Task identifier for maintaining session across all phase iterations, plans, and verification. |
| `TRAYCER_SYSTEM_PROMPT` | `"$TRAYCER_SYSTEM_PROMPT"` | `"$env:TRAYCER_SYSTEM_PROMPT"` | System prompt to append to CLI agent. Use with `--append-system-prompt` flag. |

**Important:** The temporary file from `TRAYCER_PROMPT_TMP_FILE` is automatically cleaned up by Traycer after 30 seconds.

### Template Scopes

Custom CLI agents can be created in two different scopes:

**User Scope:**
- Location: `~/.traycer/cli-agents/`
- Personal CLI agents available across all your projects
- Travel with you to any workspace
- Ideal for personal tool configurations

**Workspace Scope:**
- Location: `<workspace-root>/.traycer/cli-agents/`
- Project-specific CLI agents stored in workspace settings
- Can be committed to repository for team sharing
- Ideal for team-shared configurations or project-specific agent setups

### Creating Custom CLI Agents

**5-Step Process:**

1. **Open Manage CLI Agents** — Click the three dots on the top of the sidebar → "Manage CLI Agents"
2. **Click Add CLI Agent** — Click "Add CLI Agent" button
3. **Choose scope** — Select **User** (personal) or **Workspace** (project-specific)
4. **CLI Agent Name** — Provide a descriptive name (e.g., "Claude Dangerous", "Factory Submit")
5. **Add CLI Agent Command** — Add your custom command to the created file and save

### Popular CLI Agents

Here are popular CLI-based coding agents you can configure:

**Claude Code CLI:**
```bash
#!/bin/sh
# Basic
claude "$TRAYCER_PROMPT"

# Verbose
claude --verbose "$TRAYCER_PROMPT"

# Dangerous Mode (elevated permissions)
claude --dangerously-skip-permissions "$TRAYCER_PROMPT"
```

**Codex CLI:**
```bash
#!/bin/sh
codex "$TRAYCER_PROMPT"
```

**Gemini CLI:**
```bash
#!/bin/sh
gemini "$TRAYCER_PROMPT"
```

**Factory Droid CLI (Fabrik Integration):**
```bash
#!/bin/sh
# Basic execution
droid exec "$TRAYCER_PROMPT"

# With auto-run level
droid exec --auto medium "$TRAYCER_PROMPT"
```

**Cline CLI:**
```bash
#!/bin/sh
cline "$TRAYCER_PROMPT"
```

**Cursor CLI:**
```bash
#!/bin/sh
cursor "$TRAYCER_PROMPT"
```

**Aider:**
```bash
#!/bin/sh
aider "$TRAYCER_PROMPT"
```

### Using Custom Paths

If your CLI agent is installed at a custom location, specify the full path:

```bash
#!/bin/sh
/usr/local/bin/claude --verbose "$TRAYCER_PROMPT"
```

**Security Warning:** Flags like `--dangerous` grant elevated permissions to the agent. Always review what permissions you're granting to CLI agents.

### Reading Large Prompts from File

For very large prompts that exceed environment variable size limits, use `TRAYCER_PROMPT_TMP_FILE`:

**Bash/Git Bash:**
```bash
#!/bin/sh
claude "$(cat "$TRAYCER_PROMPT_TMP_FILE")"
```

**PowerShell:**
```powershell
claude "$(Get-Content -Raw "$env:TRAYCER_PROMPT_TMP_FILE")"
```

### Use Cases

Custom CLI agents are particularly useful for:
- **Passing dangerous/elevated permissions flags** for trusted automation
- **Using custom model configurations** (specific models, temperature settings)
- **Setting specific output formats** (JSON, structured output)
- **Creating environment-specific agent configurations** (dev vs prod)
- **Team-shared agent configurations** (via Workspace scope)
- **Maintaining session continuity** using `TRAYCER_PHASE_ID` and `TRAYCER_TASK_ID`

### Fabrik Custom CLI Agents

Fabrik uses three Custom CLI Agents for async job submission with Traycer:

**Factory Submit (async).sh:**
```bash
#!/bin/sh
# Submits jobs to /opt/fabrik/factory_submit.py
cd /opt/fabrik && python factory_submit.py "$TRAYCER_PROMPT"
```

**Factory Wait (async).sh:**
```bash
#!/bin/sh
# Monitors jobs via /opt/fabrik/factory_wait.py
cd /opt/fabrik && python factory_wait.py "$TRAYCER_TASK_ID"
```

**Factory AI.sh:**
```bash
#!/bin/sh
# Direct execution wrapper
cd /opt/fabrik && droid exec --auto medium "$TRAYCER_PROMPT"
```

These agents are configured in `~/.traycer/cli-agents/` and enable YOLO Mode automation with Fabrik's 9-step workflow.

### Custom CLI Agents FAQ

**Q: Can I pass dangerous or elevated permission flags?**

A: Yes, you can pass any flags supported by your CLI agent, including `--dangerous`, `--force`, or other elevated permission flags. However, be cautious as these flags grant the agent more control over your system. Always understand what permissions you're granting before using such flags.

**Q: How do I share custom CLI agents with my team?**

A: Create them in **Workspace scope**. Workspace-scoped CLI agents are stored in your project's workspace root under `.traycer/cli-agents/`, which can be committed to your repository. When team members pull the latest changes, they'll automatically have access to the shared custom CLI agents.

**Q: What's the difference between User and Workspace scope?**

A: **User scope** CLI agents are stored in your personal settings (`~/.traycer/cli-agents/`) and available across all projects. **Workspace scope** CLI agents are project-specific (`.traycer/cli-agents/` in repo) and stored in the workspace settings, making them ideal for team collaboration.

**Q: Can I edit an existing CLI agent?**

A: Yes, you can modify any custom CLI agent by clicking on it within the Custom CLI Agents section of Traycer settings. This will open the file for editing.

**Q: What's the difference between Bash and PowerShell syntax for environment variables?**

A: Bash (Linux/macOS/Git Bash) uses `$VARIABLE_NAME` directly (e.g., `$TRAYCER_PROMPT`). PowerShell (Windows) uses `$env:` prefix (e.g., `$env:TRAYCER_PROMPT`). Double quotes are recommended in both shells to handle prompts containing spaces or special characters. Git Bash on Windows uses Bash syntax, not PowerShell syntax.

**Q: What happens if I don't include the `$TRAYCER_PROMPT` or `$TRAYCER_PROMPT_TMP_FILE` environment variable?**

A: The CLI agent validation will fail because at least one of `$TRAYCER_PROMPT` or `$TRAYCER_PROMPT_TMP_FILE` must be referenced in your CLI agent template to pass the task instructions to the agent.

**Q: When should I use `TRAYCER_PROMPT_TMP_FILE` instead of `TRAYCER_PROMPT`?**

A: `TRAYCER_PROMPT` is the recommended default for most use cases. Use `TRAYCER_PROMPT_TMP_FILE` when:
- Dealing with very large prompts (multiple files, extensive context)
- Encountering environment variable size limits (Windows: ~32KB, Linux/macOS: varies)
- Experiencing prompt truncation issues

Both variables are always available.

**Q: How does `TRAYCER_PROMPT_TMP_FILE` work internally?**

A: Traycer creates a temporary file containing the prompt content and sets `TRAYCER_PROMPT_TMP_FILE` to the file path. When you reference `$TRAYCER_PROMPT_TMP_FILE` in your template, you need to read the file content using commands like `cat "$TRAYCER_PROMPT_TMP_FILE"` (bash/sh) or `Get-Content -Raw "$env:TRAYCER_PROMPT_TMP_FILE"` (PowerShell). This approach bypasses environment variable size limits. The temporary file is automatically cleaned up by Traycer after 30 seconds.

**Q: Can I use custom CLI agents with YOLO Mode?**

A: Yes, custom CLI agents work with YOLO Mode for automated execution. This is exactly how Fabrik's async job submission works.

**Q: Can I have multiple versions of the same agent?**

A: Yes, you can create multiple custom CLI agents with different names that use the same underlying CLI tool. For example, you could have "Claude Verbose", "Claude Dangerous", and "Claude Standard" - each with different flags but all calling the same `claude` CLI agent.

**Q: What if the CLI tool isn't installed on my system?**

A: Traycer does not install CLI agents for you. You must install the CLI tool separately before creating a custom CLI agent. We recommend testing the CLI command in your terminal first to ensure it works correctly before adding it to an agent.

**Q: Can I use session identifiers to maintain state?**

A: Yes! Use `TRAYCER_PHASE_ID`, `TRAYCER_TASK_ID`, or `TRAYCER_PHASE_BREAKDOWN_ID` in your scripts to maintain session continuity across plan generation, execution, and verification. This is useful for tools that support session resumption.

**Q: How do I debug a custom CLI agent that isn't working?**

A: Test the command manually in your terminal first:
```bash
# Set test variables
export TRAYCER_PROMPT="Test prompt"
export TRAYCER_TASK_ID="test-123"

# Run your script
~/.traycer/cli-agents/YourAgent.sh
```
Check for errors and verify the CLI tool is installed and in your PATH.

## Setup (One-Time)

1. Open Traycer Extension in Windsurf.
2. Ensure you are logged into your Pro+ account.
3. Update the `~/.traycer/cli-agents/*.sh` scripts in WSL to explicitly execute in `/opt/fabrik` instead of `/opt/proxy` or other legacy paths.
4. Sync your preferred templates into `~/.traycer/prompt-templates/`.

## Workflow with Fabrik

```text
┌─────────────────────────────────────────────────────────────────┐
│ TRAYCER (Planning & Orchestration via Windsurf Extension)       │
│                                                                 │
│ 1. Open project in Traycer within Windsurf                      │
│ 2. Use plan templates to generate phases/tasks                  │
│ 3. For each task:                                               │
│    - Traycer hands to execution agent (via cli-agents scripts)  │
│    - Agent executes inside /opt/fabrik                          │
│    - Agent undergoes FINAL_GATE and KILO Review                 │
│    - Traycer verifies completion                                │
│    - Mark done, next task                                       │
└─────────────────────────────────────────────────────────────────┘
```
