# Fabrik Workflow (Detailed Reference)

**Last Updated:** 2026-03-31

Custom workflow for Traycer Epic Mode optimized for solo developer execution with Fabrik infrastructure.

---

## Workflow Overview

**Requirements Phase:**
1. `trigger_workflow` - Pre-research + constraints + routing
2. `epic-brief` - Problem definition
3. `core-flows` - User flows (skip for APIs)
4. `prd-validation` - Requirements gate

**Architecture Phase:**
5. `tech-plan` - Technical architecture
6. `architecture-validation` - Architecture gate

**Execution Phase:**
7. `ticket-breakdown` - Actionable tickets
8. `execute` - Delegated implementation
9. `implementation-validation` - Code validation

**Utility:**
- `revise-requirements` - Update existing specs
- `cross-artifact-validation` - Cross-spec consistency

---

## Philosophy

> Goal: alignment, not artifacts. Specs = decisions made together.

- Questions = investments in correctness
- Surface assumptions early (cheap) vs fix wrong work (expensive)
- Multiple clarification rounds = normal

---

## trigger_workflow (Entrypoint)

**Steps:**
1. Orient on `AGENTS.md` (owner context, stack, constraints)
2. Detect scaffold type (`project.yaml`, `package.json`, etc)
3. Find pre-research MD in `docs/development/plans/`
4. Improve research (gaps, Fabrik services, ARM64, ports)
5. Verify 10 constraints (solo dev, ARM64, budget, ports, Alpine ban, etc)
6. Classify project type → recommend route
7. Present summary with **INFRA-CHECK** prefix

**Route Table:**

| Type | Route | Skip |
|------|-------|------|
| saas-skeleton | Full path | — |
| python-api | Skip UI | core-flows |
| wordpress | Minimal | core-flows, tech-plan |

---

## epic-brief

**Produces:** Summary (3-8 lines) + Context & Problem (<50 lines total)

**Process:**
1. Re-read pre-research
2. Ground in Fabrik services (check microservices table)
3. Draft, iterate until aligned

---

## core-flows

**Skippable for APIs/workers**

**Process:**
1. Map personas → journeys (entry/action/feedback/exit)
2. Align on UX: hierarchy, placement, feedback, integration
3. Document flows (mermaid, <30 lines each)
4. Validation gate before handoff

---

## tech-plan

**Stack Auto-Injection Table:**

| Component | Default | Override When |
|-----------|---------|---------------|
| Frontend | Next.js 14 + TS + Tailwind | — |
| Backend | FastAPI + Uvicorn | Node for web workers |
| DB | PostgreSQL 16 | Supabase for auth/realtime |
| Base | slim-bookworm | Never Alpine |
| Platform | linux/arm64 | Never x86 |

**Sections:** Architectural Approach + Data Model + Component Architecture

**Stress Test:** Simplicity, Flexibility, Robustness, Scaling, Codebase fit, Coverage

---

## ticket-breakdown

**Execution Metadata (every ticket):**
- **Plan Required**: Yes/No (default No)
- **Gate Tier**: 1 (lean) or 2 (full milestone)
- **Kilo CLI — First/Budget**: Agent recommendations
- **Cascade — First/Budget**: Model recommendations

**Agent Selection:**

| Classification | Kilo First | Cascade First |
|----------------|------------|---------------|
| Simple (single file, low risk) | Local free | Free promo (0 credits) |
| Complex (multi-file, medium risk) | Cloud mid-tier | Mid-tier (1-2 credits) |
| Critical (cross-component, high risk) | Premium | Premium (4-6+ credits) |

---

## execute

**Key Process:**

**Step 3: Plan Required Routing & Gate Tier Injection**

Check ticket metadata:
- **Plan Required = Yes** → High-level query, agent plans deeply first
- **Plan Required = No** → Full ticket details, agent implements directly

- **Gate Tier 2** → Prepend: `**MILESTONE / BATCH CLOSER** — Run full gate after implementation.`
- **Gate Tier 1** → No prepend (standard lean gate)

**Step 4: Template Selection**

Owner selects from `~/.traycer/prompt-templates/`:
- Coding: `Coder-for-Phased-Epic-Modes.md`
- Fix after review: `Fix-After-Review.md`
- Fix after verification: `Fix-After-Verification.md`

**Agent Contract (default):**
1. Implement
2. Self-review
3. Run `python scripts/final_gate.py --lean --json`
4. Fix failures (including changelog)
5. If MILESTONE: run `python scripts/final_gate.py --json` (full)

**Quality Gates:**

| Tier | Flag | When | Who |
|------|------|------|-----|
| 1 (lean) | `--lean --json` | Every task | Agent |
| 2 (full) | `--json` | Milestone close | Agent |
| 3 (systemic) | `--systemic` | On-demand | Manual |

---

## implementation-validation

**Two Lenses:**
- **Product** (Epic/Flows): Non-negotiable alignment
- **Technical** (Tech Plan): Flexible if sound

**Classification:** Blockers → Bugs → Edge Cases → Observations → Validated

**Process:** Present findings → Update passing tickets → Ask direction → Execute

---

## revise-requirements

**Process:**
1. Internalize current state (all specs + tickets)
2. Understand change via interview
3. Impact analysis (trace cascading effects)
4. Present impact map
5. Update specs one-by-one (Epic → Flows → Tech)
6. Reconcile tickets against updated specs

---

## cross-artifact-validation

**Validates:** Cross-spec consistency

**Dimensions:**
- Conceptual consistency (terminology, characterization)
- Coverage traceability (bidirectional)
- Interface alignment (contracts match)
- Specificity (no hand-waving)
- Assumption coherence (no contradictions)

**Process:** Read all → Analyze → Present findings → Update → Reconcile tickets

---

## References

- Traycer workflows stored in Traycer IDE extension workspace
- Managed via Workflows panel UI
- Command files are markdown with frontmatter

See `docs/traycer/traycer-agile-workflow.md` for Traycer's default workflow comparison.
