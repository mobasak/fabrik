<!-- ⚠️ FABRIK FACTORY WORKFLOW — EXECUTE (our own, tool-capable twin of 07-execute-command)
     Run DIRECTLY by our orchestrator agent (Opus 4.8, via the driver) — never pasted into a planner GUI.
     THIS IS THE AUTONOMOUS EXECUTION LOOP. Opus orchestrates; it dispatches coder + reviewer agents,
     validates, fixes up, and DOES NOT STOP until the epic's tickets are done — halting only on the 3 BLOCKED
     cases. Between the plan-in gate (already passed) and the deploy-out gate (`11-deploy`) there is NO human
     step (north-star R14 two-gates); the operator watches a Telegram digest, not each batch.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · the ticket-breakdown batch (`06-ticket-breakdown-fabrik` output) — the tickets to dispatch, VERBATIM
       · the ticket-outline (`05-ticket-outline-fabrik`) — the batch order + dependency graph
       · the validation specs — Decisions Lock (`01-decisions-lock-fabrik`) · Core Flows (`02-core-flows-fabrik`) ·
         Tech Plan (`03-tech-plan-fabrik`) · Deploy Plan (`04-deploy-plan-fabrik`) — for the product/technical review lens
       · each returned agent's diff (the branch/worktree it produced) + its `final_gate.py --json` output
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Execute

## Role

The **autonomous execution orchestrator** — Opus 4.8, running the driver's loop `[canonical: docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md]`. It dispatches each batch's tickets to coder agents, reviews the returned work (gate + code-vs-spec), creates fixup tickets for drift, and **loops batch after batch until the epic's tickets are complete — it does not stop and ask** except on the three BLOCKED cases below. It writes no code itself; the agents do.

## Core Philosophy

- **Autonomous between the two human gates.** The plan was approved (plan-in gate); the deploy is a separate human gate (`11-deploy-command`). Everything in between runs without a human step — no per-batch confirmation, no stop-on-drift. Drift → a fixup ticket, re-dispatched. `[canonical: north star § Human gates — R14]`
- **The only halt conditions are the 3 BLOCKED cases** `[canonical: CLAUDE.md § Behavior — the three BLOCKED cases]`: **(1)** 3 consecutive same-test failures on one ticket; **(2)** missing infra; **(3)** an unresolvable spec contradiction. On any of these → post an Apprise→Telegram alert with `BLOCKED: <what> — searched: <sources> — missing: <need>` and pause THAT ticket (continue the rest of the batch). Anything short of these → keep going.
- Send tickets VERBATIM — the ticket IS the complete instruction; add nothing.
- Validate the returned work against the specs; trust the gate for mechanics, dispatch a review for alignment.
- Parallel within a batch (⚡ tickets, each in an isolated git worktree); sequential between batches.

## Processing User Request

### Step 1: Identify Scope + Build Execution Order

From the argument (`Batch N`, `all`, or a ticket): read the tickets from `06-ticket-breakdown-fabrik`'s output; honor the dependency-ordered batches the outline already built; confirm prior-batch dependencies are complete before starting. Epic Closure is last (delta-feature; optional for Retrofit — Step 6). Present the execution order (`Batch 1: T1 ⚡ T2 ⚡ T3`; `Batch 2: T4 ⚡ T5 ⛓️ T6`; …).

### Step 2: Dispatch Batch — coder agents

Send each ticket VERBATIM to the **exact** agent `06-ticket-breakdown-fabrik` Step 9 assigned for its `Complexity` — **do not change the tier** (`06` maps `simple` → cheapest pool coder, `complex` → a mid pool coder OR `claude -p sonnet`, `critical` → `claude -p opus`):

| Coder mechanism | Serves (the tier `06` chose) |
|---|---|
| **OpenRouter pool** — `pick_models("code")` via `fanout` `[canonical: libs/subagents/select.py]` | `simple`, and `complex` where `06` chose the pool — the ≤$1.5/Mtok auto-tier coder models; **records the flywheel** |
| **Native `claude -p`** in an **isolated git worktree** `[canonical: driver spec — producer process_fn]` | `complex` where `06` chose `claude -p sonnet`; `critical` → `claude -p opus` (auth/schema/migrations/concurrency/secrets) — the authoritative producer (the driver's always-on default is Opus 4.8) |

**⚡ Parallel:** dispatch all simultaneously — each agent in its own git **worktree** (not a shared branch), so parallel `git add` can't corrupt one index. **⛓️ Sequential:** wait for the in-batch dependency to finish first. The pool `fanout` and the `claude -p` worktrees are separate OS processes — no nesting.

### Step 3: Receive + Review Each Ticket TO A NO-OP (the driver's in-loop converge)

For each returned ticket, converge its diff to a **no-op** before it merges — no broken or drifting ticket proceeds. This runs the `/fabrik-review` convergence loop per ticket, orchestrated through the **`libs/subagents` module**. (This is execution's own per-ticket converge; the **authoritative epic-level code-vs-spec review is 07's paired command `08-implementation-validation-command`** `[canonical: north star § Command-chain build plan — CC5, "08 is 07-execute's review"]`, run after the epic converges — it catches cross-ticket regressions a per-ticket pass can't; the cross-artifact pass is `10-cross-artifact-validation-command`.)

- **Gate (mechanical, blocking):** the coder's `final_gate.py --json` returned `status:"success"`? A self-report without gate output is rejected. If not → fixup (Step 4).
- **Review to a no-op (`/fabrik-review`-style, via the `libs/subagents` module):** dispatch the review convergence on the ticket's diff — **BOTH** `[canonical: core/62-using-subagents.md § Dispatch policy]`: the **pool breadth** via `fanout("review", …)` (`pick_models("review")`, ≤$1.5/Mtok, **auto-records each run to the flywheel** — back-fill your verdict with `set_quality`) **AND ≥1 native `fabrik-reviewer` on Opus** (the authoritative pass — the pool never runs `anthropic/*`). Cover the **product lens** (Decisions Lock + Core Flows — Success Criteria met, `[PRIMARY PATH]` integration test exists + passes) and **technical lens** (Tech Plan — shape matches code, resilience applied, `Lessons Learnt` stated — *silence = block*). **You (Opus) refute/merge, then LOOP: every surviving finding → a scoped fixup ticket re-dispatched to the coder (Step 4) → re-review — until a fresh review round finds nothing AND changes nothing (`found:0, fixed:0`).** Only that no-op marks the ticket Done — one review pass is never enough (the pass that produced a fixup is never the last). The loop is capped by BLOCKED case 1 (3 consecutive same-test failures → Telegram, pause the ticket).

### Step 4: Handle Findings — fixup, don't stop

Everything short of a BLOCKED case is handled autonomously:

| Finding | Action (autonomous) |
|---|---|
| **Clean** (gate success + review clean + Lessons stated) | mark **Done**, proceed |
| **Gate failure / missing governance** (CHANGELOG, INDEX, Lessons, doc) | create a **scoped fixup ticket** (one fix per issue, NOT a re-do) with the gate/review output as context; re-dispatch to a coder agent; re-review |
| **Drift / misalignment** (code ≠ spec, shape drift, resilience gap) | create a fixup ticket that re-states the correct spec; re-dispatch; re-review. Downstream tickets affected → update them and continue |
| **3 consecutive same-test failures on one ticket** | **BLOCKED (case 1)** → Telegram alert, pause THIS ticket, continue the batch |
| **Missing infra** (a registrar/service the ticket needs isn't there) | **BLOCKED (case 2)** → Telegram alert |
| **Unresolvable spec contradiction** | **BLOCKED (case 3)** → Telegram alert; route the contradiction back to `09-revise-requirements-command` |

Fixup example: `Fixup T2a — Add missing CHANGELOG entry · Scope: CHANGELOG.md only · Final Gate: python scripts/final_gate.py --json`. **Loop Steps 2–4 until every ticket in the batch is Done or BLOCKED** — never stop with a fixable finding outstanding.

### Step 5: Merge + Batch Completion

After every ticket in the batch is Done (fixups included): merge the worktrees sequentially into the default branch (sequential — no parallel `git add` race); run the gate post-merge; `fabrik dev -d` sanity (service starts, `/health` 200). Then **immediately proceed to the next batch** — no human confirmation. Post a Telegram progress line (`Batch 1 ✅ (1 fixup) → Batch 2`).

### Step 6: Epic Closure

Dispatch behaviour depends on whether `06-ticket-breakdown-fabrik` emitted an Epic Closure ticket. **Delta-feature (default — ticket present):** dispatch it — at execution time the closure ticket's **pre-deploy** systemic check is the Tier-3 gate (`final_gate.py --systemic --json`) + doc completeness (all templates filled). ⚠️ Its `fabrik verify <domain> --spec registrars` + `fabrik audit-registrars` steps check **live VPS state** `[canonical: cli.py — verify/audit run against a deployed service]`, which doesn't exist — or lacks this epic's newly-added registrars — until `fabrik apply`; so those steps belong to the **deploy-out gate** (`11-deploy-command`, post-`fabrik apply`), NOT execution-time closure. Mark them deferred-to-deploy at closure. **Retrofit where `06` skipped it** `[canonical: 06-ticket-breakdown-fabrik § Step 10]`: no ticket to dispatch — state `Epic Closure: skipped per ticket-breakdown Step 10 (Retrofit — [reason])`, proceed to Step 7. **Mismatch → escalate:** no `Retrofit:` Title prefix but no Epic Closure ticket → ticket-breakdown bug, route back to `06`; `Retrofit:` prefix but Epic Closure emitted without justification → over-scoped, route back to `06`.

### Step 7: Completion

Epic execution done → post the Telegram digest (`Epic complete: 12 done + 3 fixups + closure`). The next step is the **deploy-out human gate**: the operator reviews the branch diff in VS Code Source Control, merges, and runs `11-deploy-command` (manual `fabrik apply`) — `07` stops at "epic execution done"; deploy is a separate, human-gated run.

## Does NOT

- Write or modify ticket content — that is `06-ticket-breakdown-fabrik` (tickets dispatched VERBATIM). A wrong boundary routes back to `05`/`06`.
- Fix code itself — agents fix code in response to fixup tickets; Step 4 creates the fixup, the agent implements.
- Stop and wait for a human on drift — drift is handled by fixup + re-dispatch; only the 3 BLOCKED cases pause a ticket (via Telegram).
- Loop fixups indefinitely on one ticket — **3 consecutive same-test failures is BLOCKED case 1** → Telegram, pause that ticket.
- Bypass `scripts/final_gate.py` — a `status:"success"` is required; agent self-reports without gate output are rejected.
- Change the coder tier from the ticket's `Complexity` — `06-ticket-breakdown-fabrik` Step 9 decided pool-vs-`claude -p`; this dispatches accordingly.
- Run `git commit`/`push` — `final_gate.py` auto-stages on success (CLAUDE.md HARD STOPS); merge is the worktree→default-branch step (Step 5).
- Execute `fabrik apply` / deploy — that is `11-deploy-command` (the deploy-out gate).
- Do the epic-wide validation itself — Step 3 is only the per-ticket in-loop check; the authoritative epic-level code-vs-spec review is 07's paired `08-implementation-validation-command` (CC5), and the cross-artifact pass is `10-cross-artifact-validation-command`; a scope change routes to `09-revise-requirements-command` and re-enters the chain.

## Acceptance Criteria

- Tickets sent VERBATIM; coder chosen by the ticket `Complexity` (pool `pick_models("code")` or `claude -p`), tier unchanged from `06`.
- ⚡ parallel dispatch, each in an isolated git **worktree**; ⛓️ waits for the dependency.
- Each ticket converged to a **no-op** before merge: **gate** (`status:"success"`, no self-reports) **+ a `/fabrik-review`-style review convergence via the `libs/subagents` module** (pool `fanout`/`pick_models("review")` recording the flywheel **AND** ≥1 native `fabrik-reviewer` on Opus), **looping review→fixup→re-review across the product + technical lenses until `found:0, fixed:0`**; `Lessons Learnt` silence = block.
- Findings handled **autonomously** — scoped fixup tickets, re-dispatched, re-reviewed, **looping until Done** — with **no human step** except the 3 BLOCKED cases (3 consecutive same-test failures · missing infra · unresolvable spec contradiction), each escalated via Apprise→Telegram.
- Sequential worktree merge + post-merge gate + `fabrik dev` sanity per batch; **immediately proceed** to the next batch (no per-batch human gate).
- Epic Closure last for delta-feature — the Tier-3 gate + doc completeness at execution time (the live `fabrik verify` + `audit-registrars` are deferred to the deploy-out gate, `11`); optional for Retrofit per `06` Step 10; mismatches escalate.
- Completion posts the Telegram digest and hands off to the deploy-out human gate (`11-deploy-command`) — never runs `fabrik apply` itself.

---

**Next (CC1 pairing, north star § Command-chain build plan):** `07`'s paired review is **`08-implementation-validation-command`** `[canonical: north star § Command-chain build plan — CC5, "08 is 07-execute's review"]` — the epic-level code-vs-spec pass that forces the implemented epic to a no-op (the Step-3 per-ticket review is execution's own converge; `08` is the authoritative cross-ticket pass that catches regressions). Then `10-cross-artifact-validation-command` (the integration review), and the **deploy-out human gate** → `11-deploy-command`. *(Downstream ettw twins are built incrementally; refs point to the live Traycer `-command` source and flip to `-fabrik` as each twin lands.)*
