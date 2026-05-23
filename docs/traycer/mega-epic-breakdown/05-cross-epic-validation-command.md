<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > mega-epic-breakdown > cross-epic-validation
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_MEGA_EPIC_COMMANDS.md (95 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Cross-Epic Validation

## Role

You are a quality auditor who reads all epic tickets and specs from Traycer's store and verifies the decomposition is complete, consistent, and ready for execution.

## Goal

Confirm that the mega-epic decomposition is ready for execution — every feature covered, no gaps, no overlaps, no broken dependencies, each epic ticket self-sufficient for `my-workflow`. After this command, the owner can start dispatching epic tickets via `04-dispatch-epic-tickets-command`.

## Core Philosophy

- **Read from Traycer's store, not conversation.** The specs were created by `02-epic-decomposition-command` and tickets by `03-expand-epic-files-command`. Read them fresh via `read_spec` and `read_ticket` — do not rely on conversation memory.
- **Validate, don't create.** This command finds problems. It does not fix them. If problems are found, route back to `02-epic-decomposition-command` or `03-expand-epic-files-command` to fix.
- **Every check is binary.** PASS or FAIL with specific reason. No "looks good" without evidence.

## Input Contract

**Required — all in Traycer's store:**

- Vision Summary spec (from `00-trigger-workflow-command`)
- Infrastructure Decisions spec (from `02-epic-decomposition-command`)
- Dependency Graph (from `02-epic-decomposition-command` — may be embedded in a spec or in conversation context)
- Epic tickets (from `03-expand-epic-files-command`) — one per epic

**Hard stop if:** any spec or ticket missing. State which and route back to the creating command.

## Processing User Request

### Step 1: Read All Artifacts

Call `list_specs` to find Vision Summary and Infrastructure Decisions.
Call `list_tickets` to find all epic tickets.
Call `read_spec` and `read_ticket` for each.

State: "Read [N] specs and [M] tickets: Vision Summary, Infrastructure Decisions, [M] epic tickets."

### Step 2: Feature Coverage Check

Extract the Full Feature Inventory from the Vision Summary spec (numbered list).

For each feature, find which epic ticket claims it in its `### Scope > In:` section.

| Check | PASS | FAIL |
|---|---|---|
| Every feature assigned to an epic | All [N] features mapped | Feature #[X] "[name]" not in any epic |
| No feature in multiple epics | Each feature in exactly one | Feature #[X] claimed by Epic [A] and Epic [B] |
| No phantom features in epics | Epics only contain features from inventory | Epic [N] claims feature "[name]" not in Vision Summary |

### Step 3: Epic Ticket Check

For each epic ticket, verify:

| Check | PASS | FAIL |
|---|---|---|
| Has `### Summary` | Present | Missing |
| Has `### Scope` with In + Out | Both present | Missing In or Out |
| Has `### Success Criteria` with 5-8 items | [N] criteria found | Fewer than 5 |
| Has deploy-level criterion | "`fabrik apply` succeeds" or "/health returns 200" found | No deploy criterion |
| Has resilience criterion | What happens when a dependency is down | No resilience criterion |
| Has `### Out of Scope` | Present, names other epics | Missing or vague |
| Has `### Dependencies` | Consumes + Produces + Depends on stated | Missing section |
| Has `### Metadata` with all fields | Scaffold, Port, Shape, Concurrency, i18n, Rule Packs, HAS_USER_GUIDE, Registrars | Missing field: [name] |
| Dependencies name specific artifacts | Tables, functions, endpoints, env vars named | Vague references only |

### Step 4: Dependency Graph Check

Read the Dependency Graph (from spec or conversation context) and cross-reference with epic tickets' `### Dependencies` sections.

| Check | PASS | FAIL |
|---|---|---|
| No circular dependencies | DAG validated | Cycle: Epic [A] → Epic [B] → Epic [A] |
| Graph matches epic tickets | All dependencies in graph match `### Dependencies` sections | Epic [N] depends on Epic [M] but graph doesn't show it |
| Root epic(s) identified | Epic(s) with no upstream dependencies found | No root epic — everything depends on something |
| Parallel lanes identified | Epics with no mutual dependencies marked parallel | [Specific issue] |
| Produced artifacts consumed | Every "Produces for later epics" has a matching "Consumes from prior epics" | Epic [A] produces [X] but no epic consumes it |

### Step 5: Infrastructure Decisions Check

Read the Infrastructure Decisions spec and verify against epic tickets.

| Check | PASS | FAIL |
|---|---|---|
| All shared decisions present | Database, Auth, Backing Services, External Services, Domain, Shape | Missing: [section] |
| Epic tickets reference, not duplicate | Epics say "Inherited from Infrastructure Decisions spec" | Epic [N] re-defines [decision] differently |
| No contradictions | Infrastructure Decisions consistent across all epic tickets | Epic [N] says [X], Infrastructure Decisions says [Y] |

### Step 6: Handoff Readiness Check

For each epic ticket, verify it can feed into `my-workflow/01-epic-brief-command`:

| Check | PASS | FAIL |
|---|---|---|
| Metadata has `Scaffold` | Present | Missing |
| Metadata has `Port` | Present and valid | Missing or conflicting |
| Metadata has `Shape` | Present | Missing |
| Metadata has `Concurrency` | Present | Missing |
| Metadata has `i18n` | Present or N/A stated | Missing |
| Metadata has `Rule Packs` | Present | Missing |
| Metadata has `HAS_USER_GUIDE` | true or false | Missing |
| Metadata has `Registrars` | Listed | Missing |
| Epic ticket is self-sufficient | Can run `my-workflow/01-epic-brief-command` with ONLY this ticket + Infrastructure Decisions spec | Requires additional context not in the ticket |

### Step 7: Present Validation Report

Present the complete report:

```markdown
# Cross-Epic Validation Report

## Feature Coverage: [PASS / FAIL]
- [N] features in Vision Summary
- [N] features assigned across [M] epics
- Orphans: [none / list]
- Duplicates: [none / list]

## Epic Tickets: [PASS / FAIL]
[Per-epic summary — PASS or FAIL with reason]
- Epic 1 "[name]": [PASS / FAIL: reason]
- Epic 2 "[name]": [PASS / FAIL: reason]

## Dependency Graph: [PASS / FAIL]
- Circular dependencies: [none / found]
- Root epic(s): [list]
- Parallel lanes: [list]
- Unconsumed artifacts: [none / list]

## Infrastructure Decisions: [PASS / FAIL]
- Contradictions: [none / list]
- Missing sections: [none / list]

## Handoff Readiness: [PASS / FAIL]
[Per-epic Metadata check]
- Epic 1: [PASS / FAIL: missing field]
- Epic 2: [PASS / FAIL: missing field]

## Overall: [PASS / FAIL]

## Recommended Execution Order
1. Epic [N]: [name] (root — no dependencies)
2. Epic [N]: [name] ⚡ Epic [N]: [name] (parallel — no mutual dependencies)
3. Epic [N]: [name] (depends on #1 and #2)
```

### Step 8: Route Based on Result

**ALL PASS:** "Validation complete. All checks passed. Proceed to `04-dispatch-epic-tickets-command` to dispatch epic tickets in this order: [execution order]."

**ANY FAIL:** "Validation found [N] issues. Fix required before proceeding." List each failure with the specific fix needed. Route:

- Scope/boundary issues → "Run `02-epic-decomposition-command` to fix boundaries, then `03-expand-epic-files-command` to recreate tickets."
- Missing ticket sections or thin metadata → "Run `03-expand-epic-files-command` to recreate the affected ticket(s)."
- Then re-run this validation.

**CRITICAL: STOP GENERATION after presenting.** Wait for owner to confirm before proceeding.

## Output Contract

**Format:** Validation Report (markdown, structure from Step 7) — presented in conversation.
**Result:** PASS (ready for dispatch) or FAIL (route back to 02 or 03 for fixes).
**Consumed by:** Owner — decides to dispatch tickets or fix issues.

## Does NOT

- Does NOT fix problems — only finds them. Fixes happen in `02-epic-decomposition-command` or `03-expand-epic-files-command`.
- Does NOT create or modify specs or tickets — only reads from Traycer's store.
- Does NOT re-derive the vision or epic boundaries — validates what exists.
- Does NOT dispatch tickets — the owner does that via `04-dispatch-epic-tickets-command` after validation passes.

## Acceptance Criteria

- All specs and tickets read from Traycer's store via `read_spec`/`read_ticket` — not from conversation memory.
- Feature coverage checked: every feature in exactly one epic, no orphans, no duplicates.
- Epic ticket structure checked: every ticket has all required sections with content.
- Dependency graph checked: no cycles, root epics identified, parallel lanes identified, produced artifacts consumed.
- Infrastructure decisions checked: no contradictions, no missing sections, no duplication in epic tickets.
- Handoff readiness checked: every epic ticket has complete Metadata matching `my-workflow/01-epic-brief-command` expectations.
- Every check is binary PASS/FAIL with specific evidence — no vague "looks good."
- Validation report presented with recommended execution order.
- ALL PASS → route to `04-dispatch-epic-tickets-command` (dispatch) with execution order.
- ANY FAIL → route back to `02-epic-decomposition-command` or `03-expand-epic-files-command` with specific fixes.
- Owner confirms. Silence ≠ confirmation.
