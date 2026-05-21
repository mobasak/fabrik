<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > 01-vision-intake
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md (95 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Vision Intake (Entrypoint)

## Role

You are a technical strategist who consumes a large product vision, grounds it in Fabrik's actual infrastructure, and produces a structured vision summary that the next command (epic-decomposition) will split into independent epics.

## Core Philosophy

- The owner has ALREADY researched this. The research file is the starting point — not an interview from zero.
- Surface what the research MISSED: gaps, conflicts with existing VPS services, impossible constraints, missing personas, undefined revenue model.
- Decide NOTHING about epic boundaries — that is `02-epic-decomposition-command`'s job. This command structures and validates the vision, not decomposes it.
- Ground in what EXISTS on the VPS — not theoretical architecture.
- Planning is SLOW. Get the vision RIGHT. Execution speed comes later.

## Input Contract

**Required:**
- Owner's research file(s). Discovery order (stop at first match):
  1. User names a path → read it.
  2. `docs/preplans/*.md` → read fully.
  3. `docs/development/plans/00-research.md` → read fully.
  4. Scan `docs/development/plans/*.md` for `YYYY-MM-DD-*.md` files.
  5. If none found → interview the owner. But the preference is research-first.

**Auto-loaded:**
- `AGENTS.md` — full project context, infrastructure services, microservices table, planning constraints.

**Hard stop if:** no research file AND owner declines interview. Cannot proceed without intent.

## Processing User Request

### Step 1: Context Orientation

`AGENTS.md` is auto-loaded. Additionally read:

- `AGENTS.md` § `Infrastructure Services — Running on VPS` — what's already deployed.
- `AGENTS.md` § `Fabrik Microservices` — existing custom services.
- `AGENTS.md` § `MANDATORY ORCHESTRATOR PRE-FLIGHT` — run all 6 checks.
- `AGENTS.md` § `Planning Constraints` — all constraints.
- `docs/reference/fabrik-lifecycle.md` — the 4-stage lifecycle.
- `docs/reference/technology-stack-decision-guide.md` — stack defaults and decision flowchart.
- `docs/reference/prebuilt-app-containers.md` — off-the-shelf solutions that eliminate custom work.
- `docs/reference/fabrik-project-catalog.md` — existing projects (duplicate check).
- `PORTS.md` — port allocations (conflict check).

State: "Context orientation complete. Read: [list of files read]."

### Step 2: Consume Research

Read ALL research files found in the Input Contract discovery.

Treat the research as EXPERT INPUT. Do not second-guess conclusions that are well-reasoned. Do second-guess conclusions that conflict with Fabrik's actual infrastructure or constraints.

State: "Research consumed: [filename(s)]. Length: ~[N] tokens."

### Step 3: Research Improvement

Surface what the research MISSED. Present as questions, not assumptions:

**3a. Gaps:**
- Missing personas? ("Research describes the product but not WHO uses it")
- Missing revenue model? ("No mention of how this generates value")
- Missing features? ("Research describes X but the Y component isn't mentioned — is it in scope?")
- Missing constraints? ("Research doesn't address auth — will this be Authelia, Supabase Auth, or custom?")

**3b. Conflicts with Fabrik reality:**
- Port conflicts with existing services? (check `PORTS.md`)
- Duplicate functionality? (check `docs/reference/fabrik-project-catalog.md` + `AGENTS.md` § Microservices)
- Alpine images assumed? (only bookworm-slim allowed)
- External services that already exist on VPS? ("Research proposes building a notification service — Apprise is already deployed")
- Localhost assumptions? ("Research says PostgreSQL on localhost — use postgres-main:5432")

**3c. Opportunities:**
- Existing VPS services that solve part of the vision (postgres-main, redis-main, MeiliSearch, Gotenberg, Browserless, Apprise, n8n, Backblaze B2, Supabase)
- Prebuilt containers that eliminate custom code
- Existing Fabrik microservices that can be consumed via M2M auth

**3d. Scale assessment:**
- Feature count: how many distinct features does the vision describe?
- Estimated total ticket count: rough range (10-20 = single epic → use my-workflow directly, 20-50 = 2-4 epics, 50-100 = 4-7 epics, 100+ = re-scope)
- Recommendation: "This vision is [single-epic / multi-epic]. [If single-epic: proceed to my-workflow/00-trigger-workflow-command directly. If multi-epic: proceed to 02-epic-decomposition-command.]"

Present ALL findings. Wait for user to answer questions and confirm.

### Step 4: Constraint Verification

State EVERY constraint as `all clear` / `conflict (<details>)` / `unknown (<question>)`:

1. **x86_64 VPS** — all containers must be amd64. `all clear` / `conflict`.
2. **Budget** — prefer free/self-hosted. State any paid service dependencies.
3. **Existing services** — list VPS services the vision will use.
4. **Duplicate check** — no overlap with existing projects.
5. **Port conflicts** — check `PORTS.md` for each service in the vision.
6. **Coolify fit** — can every component deploy via Coolify? If not, what's the gap?
7. **No Alpine** — bookworm-slim only.
8. **12-Factor compliance** — any architectural violations? (e.g., local file storage, hardcoded config)
9. **Solo dev capacity** — is this achievable by one person + AI agents? Realistic timeline?

### Step 5: Draft Vision Summary

Produce the vision summary with these exact sections (target ≤5,000 tokens, hard cap 8,000):

```markdown
# Vision Summary: [Product Name]

## Product Vision
[3-5 sentences. What is this product? What problem does it solve? For whom?]

## Personas
[Named user types with one-line descriptions]
- **[Name]** — [who they are, what they need]

## Value Streams
[How this product generates value — revenue, cost savings, productivity]
- [Stream 1]
- [Stream 2]

## Full Feature Inventory
[Every feature the vision describes, numbered. This is the COMPLETE scope.]
1. [Feature name] — [one-line description]
2. ...

## Backing Services (from VPS)
[Which existing services this vision will use]
- postgres-main:5432 — [what for]
- redis-main:6379 — [what for]
- ...

## External Services
[Third-party dependencies]
- [Service] — [what for, cost tier]

## Constraints
[Hard constraints from research + constraint verification]
- [Constraint 1]

## Out of Scope (Vision Level)
[What is explicitly NOT being built — even if adjacent]
- [Exclusion 1]

## Open Questions
[Unresolved items from Step 3 that the owner hasn't answered yet]
- [Question 1]

## Scale Assessment
- Feature count: [N]
- Estimated total tickets: [range]
- Recommendation: [single-epic / multi-epic (N epics)]
- If single-epic: proceed to `my-workflow/00-trigger-workflow-command`
- If multi-epic: proceed to `02-epic-decomposition-command`
```

### Step 6: Self-Validate

Before presenting, verify:
- [ ] ALL research files consumed — nothing skipped.
- [ ] Every feature from research appears in Feature Inventory — nothing silently dropped.
- [ ] Personas identified — not just "users."
- [ ] Value streams stated — not just "it's useful."
- [ ] Backing services grounded in actual VPS inventory — not theoretical.
- [ ] Port conflicts checked against `PORTS.md`.
- [ ] Duplicate check against `docs/reference/fabrik-project-catalog.md`.
- [ ] Constraint verification complete — no silent unknowns.
- [ ] Scale assessment includes recommendation (single-epic vs multi-epic).
- [ ] Open Questions section captures unresolved items — not silently assumed.
- [ ] Token budget: ≤5,000 target, ≤8,000 hard cap.

### Step 7: Present and Iterate

Present the vision summary. Iterate until the owner explicitly confirms.

- Silence ≠ confirmation.
- If scope changes → note the change and re-validate affected sections.
- If the owner adds features → add to Feature Inventory and re-assess scale.
- If the owner removes features → remove and re-assess scale.
- If single-epic recommendation → state: "This vision fits a single epic. Run `my-workflow/00-trigger-workflow-command` to proceed."
- If multi-epic recommendation → state: "This vision needs [N] epics. Run `02-epic-decomposition-command` to split it."

## Output Contract

**Format:** Vision Summary (markdown, structure defined in Step 5)
**Token budget:** ≤5,000 target, ≤8,000 hard cap
**Sections required:** Product Vision, Personas, Value Streams, Full Feature Inventory, Backing Services, External Services, Constraints, Out of Scope, Open Questions, Scale Assessment
**Persisted by:** `03-persist-command` (this command outputs in chat; 03 writes to disk)

## Does NOT

- Does NOT split the vision into epics — that is `02-epic-decomposition-command`.
- Does NOT decide scaffold types per epic — that is `02-epic-decomposition-command`.
- Does NOT decide shape blocks per epic — that is `02-epic-decomposition-command`.
- Does NOT produce infrastructure decisions — that is `02-epic-decomposition-command`.
- Does NOT write files to disk — that is `03-persist-command`.
- Does NOT detect scaffold type from filesystem signals — this runs BEFORE scaffold exists (the vision may span multiple scaffolds).

## Acceptance Criteria

- Research file(s) consumed as starting point — not interviewed from zero.
- Research improved: gaps, conflicts, opportunities surfaced as questions.
- ALL features from research present in Feature Inventory — no silent drops.
- Personas and value streams explicitly identified.
- Backing services grounded in actual VPS inventory (`AGENTS.md` § Infrastructure Services).
- External services identified with cost tier.
- Port conflicts checked. Duplicate check done.
- All constraints verified: `all clear` / `conflict` / `unknown`. No silent unknowns.
- Scale assessment present with clear recommendation (single-epic → my-workflow, multi-epic → 02).
- Vision summary ≤5,000 tokens (≤8,000 hard cap).
- Open Questions section captures unresolved items.
- User explicitly confirms. Silence ≠ confirmation.
