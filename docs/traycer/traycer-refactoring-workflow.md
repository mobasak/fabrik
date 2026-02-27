# Traycer Refactoring Workflow (Detailed Reference)

**Last Updated:** 2026-02-24

Complete breakdown of the Traycer Refactoring Workflow commands, including roles, philosophy, artifact structures, and acceptance criteria.

---

## Workflow Overview

The Traycer Refactoring Workflow is a collaborative process for safe, intentional code refactoring. It ensures refactoring is well-understood and safely executed through 4 structured commands:

1. **trigger-workflow** (Entrypoint) - Understanding before changing
2. **plan-refactor** - Thorough analysis + collaborative approach
3. **ticket-breakdown** - Translate approach into work units
4. **verification** - Quality gate with feedback loop

---

## Core Philosophy

**Refactoring is restructuring code without changing its external behavior.** This workflow ensures refactoring is intentional, well-understood, and safely executed.

**Value system:**
- Understanding before changing - know what you're working with
- Validate assumptions early - the problem might be different than it appears
- Clear boundaries prevent scope creep
- Small, validated steps beat big-bang rewrites
- Blast radius first - know what you're affecting before deciding how to change it
- Surface risks early - surprises during implementation are expensive
- Decisions need buy-in - technical approach requires genuine alignment
- Thoroughness is a feature - multiple rounds of collaboration lead to higher quality
- Planning can't anticipate everything - implementation reveals realities

---

## Command 1: trigger-workflow (Entrypoint)

**Role:** Technical Architect who builds shared understanding before planning begins

**Focus:**
- Understanding the code area the user wants to refactor
- Validating that the stated problem matches reality
- Establishing clear scope boundaries
- Creating alignment before proceeding to planning

### Processing Flow

1. **Understand what the user wants to change and why:**
   - What code area do they want to refactor?
   - What's the motivation? (performance, readability, maintainability, tech debt, preparing for a feature)
   - What outcome are they hoping for?

2. **Build a mental model of what exists:**
   - What does this code do? What's its responsibility?
   - How is it structured? What are the key components/functions?
   - How does it fit into the larger system?
   - Who calls this code? What does it depend on?

3. **Verify that the stated problem matches reality:**
   - If user says "it's slow" - is the code actually the bottleneck?
   - If user says "it's hard to test" - what specifically makes it untestable?
   - If user says "it's messy" - what kind of mess? (tangled logic, poor naming, mixed concerns?)
   - If user says "needs refactoring for feature X" - is this code actually in the way?

4. **If exploration reveals a mismatch, ask clarifying questions:**
   - "You mentioned testability - I see the class already uses dependency injection. Is the actual pain point the business logic mixed with I/O in methods X and Y?"
   - "You said performance, but this code path isn't called frequently. Is there a specific scenario where you're seeing slowness?"

5. **Establish clear boundaries for the refactoring:**
   - What's IN scope? (specific files, functions, modules)
   - What's explicitly OUT of scope?
   - What's the risk level? (isolated code vs widely-used core component)

6. **Once shared understanding reached, provide crisp 50-word summary:**
   - Code area: What we're refactoring
   - Validated problem: The motivation (confirmed against code reality)
   - Scope boundaries: What's in, what's out
   - Risk level: Isolated vs core

### Acceptance Criteria

- [ ] Code area is understood (structure, responsibility, connections)
- [ ] User's stated problem is validated against code reality (asked if mismatch found)
- [ ] Scope boundaries are confirmed via questions (what's in, what's out, risk level)
- [ ] User confirms shared understanding before proceeding

**Next Steps:** `plan-refactor`

---

## Command 2: plan-refactor

**Role:** Technical architect who thoroughly analyzes and plans before executing

**Focus:**
- Mapping the full impact of changes before committing to an approach
- Identifying risk hotspots that need careful handling
- Making technical decisions collaboratively with genuine alignment
- Producing documents that guide implementation without ambiguity

### Core Philosophy

Good refactoring plans are grounded in reality. Analysis reveals what's actually there - dependencies, risks, test coverage gaps. Only then can you make sound technical decisions.

**Planning is where the thinking happens.** Investing time in thorough planning produces better, more controlled results.

**Collaboration philosophy:**
- Multiple rounds of questioning is expected and appreciated - don't rush to draft
- Surface and clarify assumptions diligently - wrong assumptions lead to wrong implementations
- Represent technical decisions clearly - the user should understand what they're agreeing to
- The goal is genuine alignment that constrains implementation, not quick approval

### Processing Flow

#### Part 1: Analysis

1. **Internalize** the refactoring from the trigger workflow's shared understanding

2. **Map the impact** of the proposed refactoring comprehensively:

   **Map Dependencies and Coupling:**
   - Who calls this code? (direct callers, indirect dependents)
   - What does this code call? (dependencies it relies on)
   - Shared state or side effects? (globals, events, database writes)
   - API boundaries? (public interfaces that external code depends on)

   **Identify Risk Hotspots:**
   - Core flows - critical paths that must not break
   - Concurrency - threading, async, race conditions
   - Persistence - database operations, data migrations
   - External integrations - APIs, services, third-party code
   - Complex logic - tricky algorithms, edge case handling

   **Assess Test Coverage:**
   - What test coverage exists for this code?
   - Which critical paths are tested vs untested?
   - Are the tests reliable (not flaky)?
   - What's the gap between current coverage and what we'd need for safe refactoring?

3. **Capture findings** in lean, focused `refactoring-analysis.md`:
   - Dependency Map - key callers and dependencies
   - Risk Hotspots - areas requiring careful handling, with brief explanation of why
   - Test Coverage - current state and critical gaps
   - Change Surface Area - summary of what's affected by this refactoring

   **IMPORTANT:** This document stays focused on current state - no implementation proposals or solutions

4. **Ask user to review** the Analysis document with targeted questions:
   - "Test coverage is thin in [area]. Should we add tests before refactoring, or is this acceptable risk?"
   - "I found these key dependencies: [list]. Are there any implicit dependencies or second order repercussions I might have missed?"

5. **Incorporate answers** into Analysis document before proceeding

#### Part 2: Approach

1. **Analyze existing codebase** thoroughly (architecture patterns, constraints, integration points)

2. **Identify key decisions** - think thoroughly through the new architecture:
   - Trace through a request in the new design end-to-end
   - Identify key technical decisions
   - Trace through implications of each decision
   - Surface things with non-obvious consequences or trade-offs

3. **Clarify via structured interview questions:**
   - Present options, not open-ended asks: "Should we decompose by layer or by domain?" not "How should we decompose?"
   - Ground in specifics from Analysis: "The Analysis showed X is a risk hotspot. Should we [approach A] or [approach B]?"
   - Surface trade-offs: "Option A is simpler but Option B is more flexible. Which matters more here?"
   - For implementation details: "The interface would look like [code]. Does this match your expectations?"

4. **Draft `refactoring-approach.md`** only after complete clarification and alignment

### Refactoring Approach Document Structure

**1. Key Decisions**

Document major technical decisions organized by relevant categories:

**Categories to consider:**

- **Structure** - How do we organize the change?
  - Decomposition principle (by layer, by domain, by concern?)
  - Granularity (coarse chunks vs fine-grained?)
  - Placement (where does new/shared code live?)
  - Layer responsibilities (what belongs where?)

- **Transition** - How do we get from current to target safely?
  - Strategy (incremental, big-bang, strangler pattern?)
  - Intermediate states (facades, adapters, wrappers?)
  - Order (what changes first? top-down or bottom-up?)
  - Coexistence (do old and new need to run together?)
  - Rollback (how do we undo if something goes wrong?)

- **Mapping & Gaps** - What doesn't translate cleanly?
  - API/behavior mapping (how does old map to new?)
  - Translation gaps (what doesn't have a clean equivalent?)
  - Divergence handling (when consolidating, how to reconcile differences?)
  - Canonical version (when consolidating duplicates, which becomes the base?)
  - Semantic changes (what behavior intentionally changes vs must stay the same?)

- **Design** - What do new interfaces/structures look like?
  - Interface shape (method signatures, contracts)
  - Abstraction level (direct use vs wrapper, configurable vs specific)
  - Dependency direction (what can know about what?)

- **New Concerns** - What problems might this refactoring introduce?
  - Concurrency issues (race conditions, thread safety)
  - New failure modes (what breaks differently now?)
  - Performance implications (better or worse?)
  - Complexity introduced (is the cure worse than the disease?)

- **Risk mitigation decisions:**
  - How to handle identified risk hotspots
  - How to address new concerns introduced by the refactoring

For each decision, capture:
- The decision made
- Rationale (why this choice over alternatives)
- Trade-offs (what we gain, what we give up)
- Implementation impact (what this means for the work)

**2. Target State**

Define what "done" looks like for this refactoring:
- How the code will be structured after refactoring
- What properties it will have (more modular, more testable, clearer separation, etc.)
- The minimum change that achieves the goal

Keep it concrete:
- Describe the end state, not the journey
- Be specific enough that someone could verify "yes, we achieved this"

**3. Component Architecture** (when applicable)

For refactorings that introduce new structures, define the core implementation parts. This describes 20% of the architecture that governs 80% of the implementation.

**DO NOT INCLUDE CODE FOR BUSINESS LOGIC OR IMPLEMENTATION DETAILS.**

Include:
- **Key components/classes:** New abstractions being introduced, their responsibilities, how they relate to existing components
- **Core interfaces:** Method signatures for critical contracts, type definitions that constrain implementation choices
- **Data structures:** Schema changes, new types, state shape
- **Interaction patterns:** How components communicate, diagrams for complex multi-component flows, integration points

**When to include this section:**
- Introducing new abstractions (services, managers, utilities)
- Changing data models or schemas
- Restructuring component boundaries
- Technology migrations with new APIs

**4. Invariants**

Explicitly state what must NOT change during this refactoring.

**Categories to consider:**

- **Behavioral invariants:**
  - External behavior that must be preserved
  - Edge cases that must continue working
  - Error handling that must remain consistent

- **Contract invariants:**
  - Public API signatures that cannot change
  - Data formats that external systems depend on
  - Event/message contracts

- **Performance invariants:**
  - Response time characteristics (unless performance is the goal)
  - Resource usage bounds
  - Throughput requirements

- **Data invariants:**
  - Data integrity constraints
  - Migration compatibility (existing data must still work)
  - Schema compatibility

**5. Test Strategy**

Define how correctness will be verified during and after the refactoring.

**If tests exist and are adequate:**
- Which test suites provide the safety net
- What coverage they provide
- How to run them during refactoring

**If tests are lacking but code is testable:**
- What characterization tests to add before refactoring
- Which critical paths need coverage
- First ticket should be adding these tests

**If code is untestable:**
- Acknowledge the higher risk explicitly
- What integration tests or manual verification to rely on
- Why smaller incremental steps are needed
- How ticket guardrails compensate for lack of tests

### Acceptance Criteria

- [ ] Refactoring Analysis document captures dependencies, risks, and test coverage
- [ ] Analysis document stays focused on current state (no implementation proposals)
- [ ] User has reviewed Analysis and added any missing context
- [ ] Refactoring Approach document captures decisions, target state, component architecture (when applicable), and invariants
- [ ] Component architecture defines concrete interfaces that tickets can reference
- [ ] User has genuine alignment on the technical approach through multiple rounds of collaboration

**Next Steps:** `ticket-breakdown`

---

## Command 3: ticket-breakdown

**Role:** Implementation planner who translates architectural decisions into executable work units

**Focus:**
- Breaking the approach into logical, executable tickets
- Sequencing work to minimize risk and maintain working code
- Creating tickets concrete enough to execute without ambiguity
- Ensuring each ticket has clear boundaries, guardrails, and verification steps

### Processing Flow

1. **Review** `refactoring-analysis.md` and `refactoring-approach.md` to understand:
   - Scope and risk hotspots (from Analysis)
   - Key decisions and component architecture (from Approach)
   - Invariants that must be preserved
   - Test strategy

2. **Identify logical work units** based on the Approach:
   - What are the natural boundaries? (by component, by layer, by concern)
   - What depends on what? (ordering constraints)
   - What can be done in parallel vs must be sequential?

3. **Sequence tickets to minimize risk:**
   - If tests need to be added first, that's ticket #1
   - Foundation/infrastructure changes before dependent changes
   - Lower-risk changes before higher-risk ones
   - Each ticket should leave code compilable and tests passing

4. **Prefer coarse groupings:**
   - Group by component or layer, not by individual function
   - Group by flow, not by step
   - Each ticket should be story-sized (meaningful work, not a single function)

5. **Draft each ticket** with clear structure (see Ticket Structure below)

6. **Present tickets to user** with mermaid diagram visualizing dependencies

7. **Ask for review:**
   - "Do the scope boundaries for each ticket look right?"
   - "Should any tickets be reordered or split differently?"
   - "Are the verification steps sufficient?"

### Ticket Structure

Each ticket should include:

**Scope & Objective**
- What this ticket accomplishes (one clear sentence)
- Explicit boundaries: what's in scope, what's out

**References**
- Link to relevant Analysis sections (risk hotspots to be careful about)
- Link to relevant Approach sections (decisions to follow, interfaces to implement)

**Guardrails**
- Invariants that must be preserved (from Approach §4)
- Specific risks to watch for (from Analysis risk hotspots)

**Acceptance Criteria**
- Concrete conditions that define "done"
- Behaviors that must work after this ticket

**Verification Steps**
- Specific tests to run
- Manual checks if applicable
- Expected outcomes

### Sequencing Principles

- Test coverage tickets come first (if needed)
- Infrastructure/foundation before features that depend on it
- Isolated changes before changes with many touchpoints
- Each ticket leaves the codebase in a working state

### Granularity Guidance

- Group by component or concern, not by individual function
- Each ticket should be meaningful work (not just a rename)
- But not so large that it's hard to verify or rollback
- A ticket that takes more than a day of implementation is probably too big

**Anti-pattern:** Do NOT over-breakdown. The minimal least set of tickets is better than multiple small ones.

### Acceptance Criteria

- [ ] Tickets cover the full scope of the refactoring approach
- [ ] Each ticket has clear boundaries and doesn't overlap with others
- [ ] Sequencing respects dependencies and minimizes risk
- [ ] Each ticket has concrete references to Analysis and Approach
- [ ] Guardrails and verification steps are specific, not generic
- [ ] User approves the ticket breakdown

**Next Steps:** Implementation via Phases, Plan, or Agent handoff

---

## Command 4: verification

**Role:** Quality gate who verifies implementation matches intent and catches what slipped through

**Focus:**
- Checking implementation against the agreed Refactoring Analysis and Approach
- Identifying drift, missed areas, or unintended changes
- Surfacing issues discovered during implementation that require rethinking
- Closing the feedback loop between planning and execution

### Core Philosophy

**Planning can't anticipate everything.** Implementation reveals realities that weren't visible during analysis. This verification step catches misalignments and incorporates new learnings.

**Value system:**
- Trust but verify - check the outcome against what was planned
- New information is valuable - if implementation revealed something important, incorporate it
- The goal is correctness, not blame - issues are opportunities to improve

### Processing Flow

1. **Read and understand** `refactoring-analysis.md` and `refactoring-approach.md`

2. **Review implementation against Refactoring Approach:**

   **Target State**
   - Does the refactored code match the defined target state?
   - Is the structure what we intended?
   - Were the restructuring goals achieved?

   **Invariants**
   - Were the specified invariants preserved?
   - Any unintended behavior changes?
   - Are public APIs intact (if they should be)?

   **Technical Decisions**
   - Were the agreed decisions followed?
   - Any deviations from the approach? If so, why?

   **Component Architecture** (if applicable)
   - Were the defined interfaces implemented correctly?
   - Do data structures match the spec?
   - Are interaction patterns as designed?

3. **Review implementation against Refactoring Analysis:**

   **Risk Hotspots**
   - Were the identified risk areas handled carefully?
   - Any issues in core flows, concurrency, persistence, or integrations?

   **Dependencies**
   - Are callers still working correctly?
   - Any broken dependencies?

4. **Assess overall quality beyond matching the spec:**
   - Is the code clean and maintainable?
   - Any code smells introduced?

5. **Note new information** that implementation revealed:
   - Constraints that weren't visible until code was written
   - Edge cases that emerged
   - Better approaches that became apparent
   - Risks that materialized or didn't

6. **Present findings to user** and ask questions to determine next steps:
   - "I found these deviations from the plan: [list]. Were these intentional changes, or should we correct them?"
   - "These areas weren't fully addressed: [list]. Should we create fix tickets, or is this acceptable?"
   - "During implementation, [discovery] was revealed. Does this change how we should think about the remaining work?"
   - "Given the findings, should we: (A) approve and close, (B) create fix tickets for [issues], or (C) revisit the approach?"

### Three Paths Based on Findings

**Path A: Approve**
- The implementation matches the plan
- Confirm refactoring is complete
- Note any observations for future reference
- Close the workflow

**Path B: Create Fix Tickets**
- Issues found but addressable without rethinking the approach
- Typical issues: implementation drift, missed areas, minor bugs, tests needed
- Create targeted fix tickets that reference:
  - What's wrong (specific files, functions, behaviors)
  - What the correct state should be
  - How to verify the fix
- After fixes are implemented, run verification again

**Path C: Escalate to Re-plan**
- Significant issues that require rethinking the approach
- Typical issues: fundamental blocker, constraint that invalidates the approach, new information that changes the picture
- Explain to user what was discovered and why it matters
- If re-planning is needed, return to `plan-refactor` with the new information
- Update the documents accordingly
- **This isn't failure** - it's the feedback loop working. Better to catch and correct than to push forward with a flawed approach.

### Acceptance Criteria

- [ ] Implementation has been reviewed against Analysis and Approach documents
- [ ] User has been asked about all findings and answered
- [ ] A clear decision has been made (approve, fix tickets, or escalate)
- [ ] If fix tickets: they're concrete and actionable
- [ ] If escalate: new information is clearly documented for re-planning
- [ ] User confirms the verification outcome

---

## Refactoring Workflow Philosophy Summary

**Understanding First:**
- Build shared understanding before planning
- Validate assumptions early (problem might be different than it appears)
- Know what you're working with before changing it

**Thorough Planning:**
- Analysis reveals reality (dependencies, risks, test coverage)
- Decisions need genuine alignment, not rubber-stamping
- Multiple rounds of clarification is expected and appreciated
- Thoroughness is a feature, not overhead

**Safe Execution:**
- Clear boundaries prevent scope creep
- Small, validated steps beat big-bang rewrites
- Each ticket leaves code in working state
- Guardrails and verification steps are explicit

**Feedback Loop:**
- Planning can't anticipate everything
- Implementation reveals new realities
- Verification closes the loop (approve, fix, or re-plan)
- New information improves the plan

---

## See Also

- [Traycer Integration Guide](README.md)
- [Traycer Agile Workflow](traycer-agile-workflow.md)
- [Traycer YOLO Workflow](traycer-yolo-workflow.md)
- [Development Workflow](../guides/DEVELOPMENT_WORKFLOW.md)
- [AGENTS.md](../../AGENTS.md)
