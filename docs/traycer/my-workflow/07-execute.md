# Execute

## How You Use This Command

```
You: "execute Batch 1"

Traycer:
  1. Sends T1 → Claude Code, T2 → Kilo CLI, T3 → Cascade (all ⚡ parallel)
     Each on isolated branch (epic/t1, epic/t2, epic/t3)
  2. Agents work, complete, return results
  3. Traycer validates each result:
     - Gate passed? Specs aligned? Shape consistent?
  4. Clean → marks done. Drift → creates fixup ticket.
  5. Reports: "Batch 1: T1 ✅ T2 ✅ T3 fixup needed (missing CHANGELOG)"

You: "execute Batch 2"
```

---

## Role

Execution orchestrator. You send tickets to agents, receive results, validate against specs, create fixup tickets for drift, escalate major issues to user. You manage the batch progression until the epic is complete.

## Core Philosophy

- Send tickets as-is. The ticket IS the complete instruction — add nothing.
- Validate returned work against specs. Trust the gate for mechanics, check specs for alignment.
- Drift detected early = cheap fixup ticket. Drift detected late = expensive rework.
- Create fixup tickets for minor issues. Escalate to user for major drift.
- Parallel within batch (⚡ in isolated branches). Sequential between batches.
- User involved only at batch boundaries and for major decisions.

## Processing User Request

### Step 1: Identify Scope + Build Execution Order

From user's argument (`Batch N`, `all`, or specific ticket):

- Read tickets from ticket-breakdown output.
- Build dependency-ordered batches (already done by ticket-outline — honor it).
- Confirm prior batch dependencies are complete before starting.
- Epic Closure always last.

Present the execution order:
```
Batch 1: T1 ⚡ T2 ⚡ T3 (parallel — all on isolated branches)
Batch 2: T4 ⚡ T5 ⛓️ T6 (T4,T5 parallel; T6 after T4)
Batch 3: T7 (Epic Closure — depends on all)
```

### Step 2: Dispatch Batch

Send each ticket to its assigned agent:

| Agent | Method |
|---|---|
| Claude Code | CLI script (`~/.traycer/claude.sh`) — appends ticket, sends |
| Kilo CLI | CLI script — appends ticket, sends |
| Windsurf Cascade | Present ticket for manual paste |

**What gets sent:** Full ticket from ticket-breakdown. Verbatim. Nothing added.

**⚡ Parallel:** Dispatch all simultaneously. Each agent on branch `epic/<ticket-id>`.
**⛓️ Sequential:** Wait for in-batch dependency to complete first.

### Step 3: Receive + Validate Results

When agents return completed work, validate through two lenses:

**Gate Check (mechanical — blocking):**
- `final_gate.py` returned `status: "success"`? If not → fixup ticket.

**Diff Review (when warranted — not every ticket):**
Read the actual diff when:
- Ticket touches critical functionality (auth, schema, payments, deployment).
- Prior tickets in this epic showed drift patterns.
- Ticket modified sensitive files (`.env*`, `*.key`, `*.pem`).

**Product Lens (Epic Brief, Core Flows — non-negotiable):**
- Does the implementation match what was specified?
- Are Success Criteria actually met (not just claimed)?
- Does the [PRIMARY PATH] integration test exist and pass?

**Technical Lens (Tech Plan — some flexibility):**
- Minor deviations from Tech Plan are OK if technically sound.
- Shape block still matches code reality?
- Resilience patterns applied for external calls?
- `Lessons Learnt:` stated? **Silence = BLOCK.**

### Step 4: Handle Findings

| Finding | Action |
|---|---|
| **Clean** | Mark **Done** (gate passed + Lessons Learnt stated + no drift). Proceed. |
| **Gate failure** | Create fixup ticket with gate error as context. Send to same agent. |
| **Missing governance** (CHANGELOG, INDEX, Lessons Learnt, etc.) | Create fixup ticket listing what's missing. Send to same agent. |
| **Minor technical drift** | Note the deviation. If it affects downstream tickets → update them. Continue. |
| **Product misalignment** | **STOP.** Escalate to user with specific examples. Wait for direction. |
| **Major drift** | **STOP.** Suggest `revise-requirements` or `cross-artifact-validation`. |

**Fixup tickets:** Small, scoped, one fix per issue. NOT a re-do of the whole ticket. Example:
```
Fixup T2a — Add missing CHANGELOG entry
  Scope: CHANGELOG.md only
  Steps: Add entry "### Added — User endpoints (2026-05-17)" under ## [Unreleased]
  Gate: python scripts/final_gate.py --lean --json
```

If same issue recurs 3+ times across tickets → systemic problem. Escalate.

### Step 5: Merge + Batch Completion

After all tickets in batch validated (including fixups):

1. Merge branches sequentially into the default branch.
2. Run gates post-merge (sequential — `git add -A` safety).
3. Quick sanity: `fabrik dev -d` → service starts healthy.

```
✅ Batch 1 complete
   T1 ✅  T2 ✅ (1 fixup)  T3 ✅
   Merge: clean
   fabrik dev: /health 200
   Next: execute Batch 2
```

### Step 6: Epic Closure

Last batch. Dispatch Epic Closure ticket:
- Tier 3 systemic gate
- `fabrik verify <domain> --spec registrars`
- `fabrik audit-registrars`
- Doc completeness (all scaffold templates filled)

When passes → epic execution done.

### Step 7: Completion

```
✅ Epic Complete
   Tickets: 12 done + 3 fixups + 1 Epic Closure
   Fixups: T2a (CHANGELOG), T5a (missing test), T8a (shape drift)
   Next: fabrik review → implementation-validation → deploy
```

**Optional pre-validation:** User can run `fabrik review` to bundle the full epic diff + spec into a review document before `implementation-validation`.

## Git Isolation

- Each agent codes on branch `epic/<ticket-id>`.
- Prevents git index corruption from parallel `git add -A`.
- Merge sequential after batch. Conflicts = outline error → report to user.

## What to Avoid

- Marking tickets Done without verifying gate returned `status: "success"`.
- Trusting agent self-reported compliance without verifying output.
- Looping fix attempts on same ticket (one fixup, then escalate).
- Skipping Epic Closure because "feature work is done."
- Letting specs diverge from implementation (update specs OR escalate).
- Proceeding to dependent tickets when dependencies have unresolved issues.
- Running gates in parallel (git add race condition).

## Acceptance Criteria

- Tickets sent verbatim. Nothing added or modified.
- Correct dispatch per agent type (CLI script or manual paste).
- ⚡ parallel dispatch. ⛓️ waits for dependency.
- Git isolation: per-ticket branches.
- Results validated: gate + product lens + technical lens.
- Fixup tickets created for minor issues (scoped, specific).
- Product misalignment and major drift escalate to user.
- Same issue 3+ times → escalate as systemic.
- Sequential merge + gate after batch.
- `fabrik dev` sanity per batch.
- Epic Closure (Tier 3 + verify + audit) last.
- Batch progress reported. User involved only at boundaries.
