<!-- ⛔ RETIRED 2026-09-06 — the Traycer Agile Workflow is no longer a workflow here.
     Its twin is the `/fabrik-*` pipeline (CLAUDE.md § Pipeline — spec § Chain consolidation (b): "Retire the Traycer layer. The cockpit and driver the chain hands off to were never built (R8); `traycer_mirror.py` is a no-op without `TRAYCER_EPIC_ID`; the wrappers are doorbells."). Kept for history only. Do NOT wire it back. -->
# Traycer Agile Workflow (Detailed Reference)

**Last Updated:** 2026-07-20

Complete breakdown of the default Traycer Agile Workflow commands, including roles, philosophy, artifact structures, and acceptance criteria.

---

## Workflow Overview

The Traycer Agile Workflow is a collaborative, spec-driven development process that guides you from requirements to implementation through 8 structured commands organized in 3 phases:

**Requirements Phase:**
1. `trigger_workflow` (Entrypoint) - Requirements gathering
2. `epic-brief` - Problem definition
3. `core-flows` - User flow mapping
4. `prd-validation` - Requirements validation (gate)

**Architecture Phase:**
5. `tech-plan` - Technical architecture
6. `architecture-validation` - Architecture validation (gate)

**Execution Phase:**
7. `ticket-breakdown` - Actionable tickets
8. `implementation-validation` - Implementation validation (gate)

---

## Core Philosophy

**Consistent across all commands:**

> The goal is alignment, not artifacts. Specs are records of decisions made together, not deliverables to rush toward.

**Value system:**
- Questions are investments in correctness, not overhead
- Surfacing assumptions early is cheap; fixing wrong work is expensive
- Getting it right the first time is faster than iterating on wrong work
- Multiple rounds of clarification is normal and encouraged

**Before proceeding to next step:**
- Surface key assumptions with genuine honesty
- Continue asking questions until genuinely confident
- Only proceed when you and the user have shared understanding

---

## Command 1: trigger_workflow (Entrypoint)

**Role:** Requirements gatherer

**Purpose:** Requirements gathering through structured interviewing (readonly - no artifacts created)

### Processing Flow

1. Understand the user's request
2. Ask clarifying questions to resolve ambiguities
3. Multiple rounds of clarification expected
4. Present concise summary of agreed requirements
5. Suggest proceeding with next commands

### Key Principles

- **User intent first**: Workflow guides but user directs
- **Multi-round clarification**: Normal and encouraged
- **Goal is shared understanding**, not speed
- **No artifacts created** - this is a readonly step

### Acceptance Criteria

- [ ] User's request turned into precise requirements via structured interviewing (no assumptions)
- [ ] User is satisfied with the requirements

**Next Steps:** `epic-brief` or `core-flows`

---

## Command 2: epic-brief

**Role:** Product manager who digs into the "why" behind requests

**Focus:**
- Understanding root causes and motivations
- Keeping user value at the center
- Precision and clarity in communication
- Collaborative and iterative approach

### Processing Flow

1. Internalize user's request at product level
2. Ask clarifying questions for any ambiguities
3. Build shared understanding through responses
4. Ask: "Am I completely confident and clear?" If no → more questions
5. Draft Epic Brief once aligned

### Artifact Structure

**Epic Brief** (under 50 lines):
- **Summary**: 3-8 sentences describing what this Epic is about
- **Context & Problem**: Who's affected, where in the product, the current pain

**Constraints:**
- No UI flows, UI specifics, or technical design

### Acceptance Criteria

- [ ] Problem and context aligned with user, all assumptions clarified
- [ ] User confirms brief captures core problem and who's affected

**Next Steps:** `core-flows`

---

## Command 3: core-flows

**Role:** Product manager who designs user experiences through structured dialogue

**Focus:**
- Understanding user journey end-to-end (entry, actions, exit)
- Information hierarchy (critical vs. secondary)
- Placement and discoverability of actions
- Feedback and state communication
- Product-level documentation (not technical implementation)

### Design Dimensions

**Information Hierarchy:**
- What information is most critical and should be prioritized
- What's secondary and can be progressively disclosed
- Grouping and organization of information

**User Journey Integration:**
- Entry point to this flow
- Where user goes after completing
- How flow connects to adjacent workflows

**Placement & Affordances:**
- Integration with existing UI layout
- Where actions live and how they behave
- Discoverability of the feature

**Feedback & State Communication:**
- How users know action is in progress
- How success, errors, edge cases are communicated

### Processing Flow

1. Read and internalize Epic Brief
2. Explore codebase to understand current flows
3. Think through UX design decisions
4. Seek clarity through targeted questions
5. Work through all flows in conversation first
6. Mentally trace complete journey for each flow
7. Surface decision points and uncertainties
8. Iterate until shared understanding
9. Document all flows together once aligned

### Artifact Structure

**Each flow** (under 30 lines):
- Name and short description
- Trigger / entry point
- Step-by-step description
- User actions and interactions
- UI feedback and navigation
- Wireframes or ASCII sketches where helpful

**Constraints:**
- No file paths or component names
- No code or technical details
- Product-level spec only

### Acceptance Criteria

- [ ] All user flows aligned with user, all assumptions clarified
- [ ] User confirms flows capture intended experience

**Next Steps:** `tech-plan` or `ticket-breakdown`

---

## Command 4: prd-validation (Gate)

**Role:** Product quality advocate who ensures requirements are clear, complete, and actionable

**Focus:**
- Evidence-based validation (cite specific sections)
- Every requirement ties back to user value
- Scope is truly minimal while viable
- Clarity over completeness
- Finding gaps together through collaboration

### Validation Focus Areas

**1. Problem Definition & Context**
- Problem clearly articulated?
- Who experiences it and why it matters?
- Scope appropriate?
- Success criteria defined?

**2. User Experience Requirements**
- Primary user flows documented with entry/exit points?
- Decision points and branches identified?
- Critical edge cases considered?
- Error scenarios and recovery outlined?
- User journey coherent end-to-end?

**3. Functional Requirements Quality**
- Requirements specific and unambiguous?
- Focus on WHAT (behavior) not HOW (implementation)?
- Terminology consistent?
- Complex requirements broken into understandable parts?
- Each requirement testable/verifiable?

### Processing Flow

1. **Gather Context**: Read Epic Brief + Core Flows
2. **Evaluate Requirements**: Assess each focus area qualitatively
3. **Identify Gaps**: Prioritize by importance
4. **Interview for Resolution**: Present findings as questions, resolve collaboratively
5. **Update Specs**: Update Epic Brief and Core Flows with agreed changes
6. **Confirm Readiness**: Review updates, iterate if needed

### Acceptance Criteria

- [ ] All focus areas evaluated against existing specs
- [ ] Gaps and ambiguities identified and resolved
- [ ] Original documents (Epic Brief, Core Flows) updated with agreed changes
- [ ] User confirms updated specs are complete and accurate
- [ ] Requirements ready for technical architecture phase

**Next Steps:** `tech-plan`

---

## Command 5: tech-plan

**Role:** Technical architect who considers the complete system picture

**Focus:**
- Seeing each component in context of whole system
- Grounding recommendations in actual codebase
- Starting simple with clear path to scale
- Letting user journeys inform technical choices
- Designing for change and adaptation
- Considering failure modes

**Interactive Process Required:** Step-by-step collaboration, do not skip clarification

### Processing Flow

1. **Internalize** Epic Brief and Core Flows
2. **Analyze** existing codebase thoroughly (architecture patterns, constraints, integration points)
3. **Think through** high-level design:
   - Trace request end-to-end through proposed architecture
   - Change a requirement - what ripples through design?
   - Inject failures - what breaks, what recovers?
4. **Surface assumptions** and interview user about approach
5. **For each section** (one at a time):
   - Think through details and implications
   - Clarify with user (surface decisions, uncertainties)
   - Document only after alignment

### Artifact Structure

**Tech Plan** (3 sections only):

**1. Architectural Approach** (under 100 lines)
- Major architectural choices (patterns, paradigms, technologies)
- Trade-offs and rationale for each decision
- Constraints (technical, business, regulatory)

**2. Data Model** (under 100 lines)
- New entities required
- Relationships with existing data models
- Database schema changes

**3. Component Architecture** (under 100 lines)
- New components required
- Interfaces with existing components
- Clear boundaries and responsibilities
- Integration points and data flow

**Constraints:**
- No code repository structure
- No business logic implementation details
- Code snippets only for schemas and interfaces

### Acceptance Criteria

- [ ] Architectural approach aligned with user, all assumptions clarified
- [ ] Key decisions and trade-offs captured with user alignment
- [ ] User confirms technical direction

**Next Steps:** `ticket-breakdown`

---

## Command 6: architecture-validation (Gate)

**Role:** Architect who pressure-tests designs before they become locked in

**Focus:**
- The critical 30% (decisions that shape 80-90% of implementation)
- Stress-testing over checkbox ("what breaks?" not "is this documented?")
- Codebase grounding
- Simplicity bias (complexity needs justification)

### Validation Focus Areas

**Six dimensions:**

1. **Simplicity**: As simple as it can be? Unjustified complexity? Could simpler approach work?
2. **Flexibility**: What if requirements change? Hard-coded assumptions? Components modifiable independently?
3. **Robustness & Reliability**: What happens when components fail? Failure modes handled? Edge cases considered?
4. **Scaling Considerations**: Potential bottlenecks? What breaks under load? Single points of failure?
5. **Codebase Fit**: Works with existing patterns? Integration realistic? Patterns consistent?
6. **Consistency with Requirements**: Addresses Epic Brief + Core Flows? Critical requirements covered? Gaps?

### Processing Flow

1. **Gather Context**: Read Epic Brief, Core Flows, Tech Plan, existing codebase patterns
2. **Baseline Coverage Check**: Verify Tech Plan addresses foundational areas
3. **Identify Critical Decisions**: Extract 3-7 defining architectural choices
4. **Stress-Test Each Decision**: Evaluate against six focus areas
5. **Issue Classification**: Categorize by importance (Most Important → Significant → Moderate → Minor)
6. **Interview for Resolution**: Present findings as questions, start with most important
7. **Update Tech Plan**: Make clarifications/changes based on resolution
8. **Confirm Readiness**: Review updates, iterate if needed

### Issue Classification

- **Most Important** (address first): Major rework risk, violates requirements, fundamental robustness gaps, security vulnerabilities
- **Significant**: Notable complexity, fights codebase patterns, resilience gaps, missing error handling
- **Moderate**: Minor consistency issues, simplification opportunities, edge cases, terminology
- **Minor**: Observations, suggestions, polish, refinements

### Acceptance Criteria

- [ ] Baseline coverage check completed with no unaddressed gaps
- [ ] Critical architectural decisions identified and stress-tested
- [ ] Gaps and concerns clarified and resolved
- [ ] Agreed changes made to Tech Plan
- [ ] Architecture confirmed ready for ticket breakdown

**Next Steps:** `ticket-breakdown`

---

## Command 7: ticket-breakdown

**Role:** Work planner

**Focus:**
- Natural work units (by component, flow, or layer)
- Dependencies between pieces
- Implementation order
- Coarse groupings (story-sized, not function-sized)

### Processing Flow

1. Review specs (Epic Brief, Core Flows, Tech Plan)
2. Identify natural work units
3. Apply best judgment for grouping and dependencies
4. Draft tickets (Title, Scope, Spec references, Dependencies)
5. Present proposed breakdown with mermaid diagram
6. Offer refinement options
7. Iterate based on feedback

### Ticket Structure

Each ticket:
- **Title**: Action-oriented
- **Scope**: What's included, what's explicitly out
- **Spec references**: Link to relevant Epic Brief, Core Flows, Tech Plan sections
- **Dependencies**: What must be completed first (if any)

**Anti-pattern:** Do NOT over-breakdown. Minimal least set of tickets is better than multiple small ones.

### Acceptance Criteria

- [ ] Ticket breakdown aligned with user
- [ ] Dependencies clear
- [ ] Grouping makes sense for implementation

**Next Steps:** Implementation via Phases, Plan, or Agent handoff

---

## Command 8: implementation-validation (Gate)

**Role:** Careful reviewer who checks if what was built matches what was planned and works correctly

**Focus:**
- Evidence over assumption (cite code and spec references)
- Advisory not authoritative (present findings, user decides)
- Severity matters (distinguish blockers from observations)
- Practical focus (real issues, not pedantic nitpicks)

### Two Core Questions

1. **Alignment**: Does code match what was planned in specs?
2. **Correctness**: Does code actually work? Bugs or gaps?

### Processing Flow

1. **Identify Scope**: Specific ticket(s) or entire implementation
2. **Gather Context**: Read Epic Brief, Tech Plan, Tickets, implementation code (via git diff)
3. **Alignment Analysis**: Compare implementation against specs
4. **Correctness Analysis**: Review for bugs, edge cases, error handling, logic soundness
5. **Present Findings**: Organize by importance (blockers → bugs → edge cases → observations), ask for direction
6. **Execute Based on Direction**: Create bug tickets, add notes, document deviations
7. **Confirm Completion**: Summarize validation and actions taken

### Issue Classification

- **Blockers**: Broken functionality, major spec deviations, security concerns, data corruption risks
- **Bugs**: Logic errors, incorrect behavior, broken flows
- **Edge Cases**: Unhandled scenarios, missing validations, error conditions
- **Observations**: Minor concerns, code quality suggestions, potential improvements
- **Validated**: What's working correctly and aligned

### Actions

- Update passing tickets (no user confirmation needed)
- Create bug tickets for issues needing separate tracking
- Add notes to existing tickets for observations
- Document accepted deviations or trade-offs

### What Good Validation Looks Like

- Findings specific and actionable (not vague)
- Code locations referenced
- Importance calibrated (not everything is a blocker)
- Spec references show why something is a deviation
- User sees full picture and guides how to handle issues

### Acceptance Criteria

- [ ] Implementation validated against specs
- [ ] Issues categorized and presented
- [ ] User has guided how to handle findings
- [ ] Bug tickets created or notes added as directed
- [ ] Ticket statuses updated appropriately

---

## Workflow Philosophy Summary

**Collaboration First:**
- Discuss and align before drafting artifacts
- Questions as investments (clarification prevents costly mistakes)
- Shared understanding (multiple rounds is normal)
- Readable artifacts (optimize for human parsability)

**Gated Quality:**
- prd-validation gates requirements → architecture
- architecture-validation gates architecture → execution
- implementation-validation gates code → completion

**Spec-Driven Development:**
- Specs are records of decisions made together
- Alignment before artifacts
- Multi-round clarification is the norm
- Questions are investments, not overhead

---

## See Also

- [Traycer Integration Guide](README.md)
- [Traycer YOLO Workflow](../../../archive/traycer-yolo-workflow.md) (archived — Kilo-era fast path)
- [Traycer Refactoring Workflow](traycer-refactoring-workflow.RETIRED.md)
- [Mandatory Workflow](../../../../agents-fabrik.md#workflow-mandatory--three-tiers-by-scale) — See "Workflow (mandatory) — three tiers by scale" section
- [AGENTS.md](../../../../AGENTS.md)
