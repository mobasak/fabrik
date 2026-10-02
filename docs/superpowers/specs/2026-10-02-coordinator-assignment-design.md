# Coordinator proactive assignment — no window idles while work exists

Status: DRAFT
Size: small (≈350 lines, 3 files)
Profile: delta — every item changes an engine that exists today: the work store (`scripts/work.py`), the Stop hook (`.claude/hooks/final_gate_stop.py`) and the multi-agent model docs.

Work item: W-83021827 · Decision: D-512 · Owner: infra (the hub's merge owner and coordinator, D-471)

## Personas

| Persona | Who | What they need from this | Duty this spec gives them |
|---|---|---|---|
| **Operator (PRIMARY)** | the person running the windows | *"merge owner and coordinator ais must always sort out waiting tasks, strategic_backlog, work, specs plans and proactively assign them to other windows so that no agent waits idle if there is work to be done."* (D-512) | none — the point is that they never dispatch by hand |
| Coordinator agent | the one agent in a repo's main checkout: merge owner and distributor (D-471); `infra` in the hub | a short, executable way to keep every worker supplied | **triage** the waiting work and **top up** each worker's owned queue; refused at its own Stop while a worker is under the floor and assignable work exists |
| Worker agents | agents 2..N in worktrees (`fleet`, `intel` in the hub; named agents in projects) | to always know their next item without asking | **claim the next item** instead of ending a turn idle; refused at Stop while `ready --mine` is non-empty and nothing is claimed |
| One-window agent | a project repo with a single window: coordinator and worker are the same agent | the same rule without a second window | its own queue is the worker queue; the worker cause applies to it |
| The Stop hook (automated) | `.claude/hooks/final_gate_stop.py`, fleet-synced | facts it can compute from the store, without `ListAgents` | enforces both new causes; warns through after 3 attempts like every cause |
| `work.py` (automated) | the store's CLI | — | gains `triage` (report + top-up plan) and `queue` (per-agent depth) |

**Step budget (the primary loop, counted):** the operator opens the windows (1) and answers only the decisions that are theirs (2, when any exist). Every other step — triage, assignment, claiming the next item — happens without them. **Operator steps for dispatch: 0.** A design that asks the operator to say "take the next item" has broken the budget.

## Goal

No agent window ends a turn idle while there is assignable work in its repo. The coordinator keeps a triaged, owned queue in front of every worker; a worker always claims its next item; the Stop hook makes both duties binding, within the quota bands and the operator's own gates.

## Why this exists

The work-tracking design made the distributor an occasional role: *"Assigning is not the default way work moves: an idle worker claims from `ready` itself"* (`docs/reference/work-tracking.md:138-141`; `docs/reference/multi-agent-operating-model.md:218-220`, D-442). Measured 2026-10-02 in the hub store (`.fabrik/work/`, 663 items):

- **386 open items**: 342 backlog, 36 task, 8 mail.
- **Owner skew:** infra owns 248, fleet 71, intel 9, and 54 have no owner. So one worker can run dry while another owns a pile; a self-service puller has no reason to rebalance.
- **No triage signal:** 366 of 386 sit at the default priority 2, so `ready`'s `(priority, created, id)` sort (`scripts/work.py:724`) degenerates to oldest-first.
- **Stale:** 130 open items are older than 14 days, 43 older than 30.
- **Waiting approvals duplicated:** 7 awaiting-operator items, 3 of them the same question (W-7eda7b6c, W-0aea1bba, W-2c7c08a6).
- **Unexecuted plans:** 9 of the 25 live plan documents that carry a Status line read CONVERGED, not EXECUTED (ticket files and `archived/` excluded); no item names an owner for them.

Nothing today tells the coordinator that a peer is idle (no script computes it — the grounding sweep found none), and nothing stops a worker from ending its turn with work available. The operator dispatches by hand. This design removes that.

## What exists today (grounded)

- `scripts/work.py:2669-2701` `cmd_assign` — sets `owner`, `priority`, `tags`; gated to `config.json`'s `distributor` (`:2684-2687`).
- `scripts/work.py:708-727` `_ready_from` — open, unblocked, unclaimed, non-`next` items sorted `(priority, created, id)`; with `mine=True` returns the caller's owned items, then unowned items (`:725-727`); items owned by another agent are excluded.
- `scripts/work.py:2769-2776` `cmd_next` — the first item of that `mine` ordering.
- `scripts/work.py:2891-2934` `claim` — a 2-hour lease (`DEFAULT_LEASE_S`, `:87`) with a fencing token, stored in the git common dir (`:272-286`, `:883-884`); claiming never reads `owner`.
- `scripts/work.py:3812-3861` `prompt_block` — the per-prompt `work:` banner (ready count, live claims per session).
- `.claude/hooks/final_gate_stop.py` — seven blocking causes, each capped at 3 attempts (`:46`); the seventh, a waiting merge request, fires only for the resolved merge owner via `whoami_agent.py --who` and `decisions.py --merge-owner` (`:1529-1735`).
- `scripts/merge_request.py:414-425` — the coordinator is notified by mail plus a printed `SendMessage to=<name>:` doorbell; the same pattern carries an assignment notice.
- Charters: `docs/reference/agents/infra.md:12-18`, `fleet.md:11-18`, `intel.md:19-33` — each agent's beat, the routing key for triage.
- Claude Code messaging (external, below): no idle state in `ListAgents`; idle is observable only through `notify_when_idle`.

## The delta

**D1 — `work.py queue`: per-agent queue depth (read-only).** Prints, per agent in the repo's roster (the charters plus any `owner` value in the store), the number of open, ready, unclaimed items it owns, its live claim if any, and the floor `K`. `--json` for the hooks. Pure read; no lock beyond the existing store read.

**D2 — `work.py triage`: the coordinator's sort (distributor-only, like `assign`).** One pass over the store that:
1. **Dedups** awaiting-operator items asking the same question (normalised title + block digest) — `drop --duplicate-of <keep>` on the copies, printing each.
2. **Routes by beat** — an unowned item whose `tags`, links or title match exactly one charter's beat gets that owner; an ambiguous one is listed for the coordinator, never guessed.
3. **Surfaces derived work** — every live plan whose Status is CONVERGED and not EXECUTED, and every CONVERGED spec with no plan, becomes (once, idempotently, keyed by path) a `task` item linking it.
4. **Lists stale items** (older than 14 days, no claim in that time) as a review list for the coordinator: keep with a priority, or drop with a reason. Triage never drops on its own.
5. **Prints the top-up plan** — for each worker below `K`, the next items to assign, by priority, then age. `--apply` runs the assigns; without it, triage only reports.
Priorities stay the coordinator's judgment: triage proposes, `assign --priority` records it.

**D3 — Worker Stop cause (eighth cause): "idle with work available."** At a worker's Stop, in a repo with a work store, when: the session holds **no live claim**, `ready --mine` (owned, then unowned) is **non-empty**, the session is **not** the merge owner of a repo that has linked worktrees (`git worktree list` shows more than the main checkout — there the merge owner gets D4 instead; in a one-window repo the merge owner IS the worker and gets D3), no command run record is `running`, the quota band is **GREEN** (AMBER means finish what you started and start nothing heavy, RED and the wall mean checkpoint — CLAUDE.md § the quota bands), and the turn did not end on an accepted DECISION NEEDED block → **block**: *"Work is waiting: claim `<next id> — <title>` (`python3 scripts/work.py claim <id>`) and start it, or say why it cannot start."* Capped at 3 attempts like every cause.

**D4 — Coordinator Stop cause (extends the merge-owner duty, cause seven): "a worker is under-supplied."** At the merge owner's Stop, when `work.py queue --json` shows any worker below `K` owned-ready items **and** triage's top-up plan has assignable items for that worker's beat → **block**: *"<worker> has <n> of K items queued and <m> assignable items wait: run `python3 scripts/work.py triage --apply`, then send the assignment line it prints."* Refusal, never advice (the judge panel's top risk: an advisory coordinator can run triage and skip the assigning). Fires only in a repo with linked worktrees; same quota and DECISION exemptions as D3.

**D5 — The assignment notice.** `triage --apply` prints, per worker that received items, one `SendMessage to=<worker>: assigned <ids> — <titles>` line (the `merge_request.py:416` doorbell pattern). The coordinator sends it; a busy worker reads it between tool calls, an idle one starts a new turn with it (Claude Code docs, below). Where messaging is off or the peer is on another machine, D3 still makes the worker claim at its next Stop — the notice is a speed-up, never the mechanism.

**D6 — `K`, the queue floor.** Default 3 owned-ready items per worker (`work.py` constant `QUEUE_FLOOR`, overridable per repo in `.fabrik/work/config.json` as `queue_floor`). Three keeps a worker supplied across a coordinator turn of normal length without front-loading the queue that a reprioritisation would have to unwind.

**D7 — Docs and the rule text.** `docs/reference/work-tracking.md` § Ownership and the distributor and `docs/reference/multi-agent-operating-model.md` § Claim or assign are rewritten: the coordinator assigns by default and keeps every worker at `K`; a worker claims its next item rather than ending idle; self-service claiming of unowned work remains the fallback. The project contract (`templates/governance/CLAUDE.md`) gains the two duties in one sentence each beside D-471's merge-owner rule; the hub `CLAUDE.md` mirrors them.

## Contract deltas

No data-contract or UI change. Interface changes: two `work.py` verbs (`queue`, `triage [--apply] [--json]`), one config key (`queue_floor`), one Stop-hook cause (D3) and one extension of cause seven (D4). `ready`, `next`, `claim`, `assign` are unchanged.

## Cost

Code ≈350 lines across `scripts/work.py` (D1, D2, D6 ≈220), `.claude/hooks/final_gate_stop.py` (D3, D4 ≈110) and the template/docs (D7, prose); tests excluded. Runtime: `queue --json` reads the store once (663 files today, well under a second on this box); the Stop hook already reads the store for the banner. Tokens: one triage pass per coordinator turn that needs it — reports are bounded to the top-up plan and the stale list.

## Validation

- **V1** — a worker session with no claim and one owned ready item is refused at Stop with the item named; with a claim, or with `ready --mine` empty, it is not (D3). Red-first.
- **V2** — the same worker at quota AMBER or RED, with a `running` run record, or ending on an accepted DECISION block is not refused (D3 exemptions).
- **V3** — the merge owner is refused while `queue --json` shows a worker below `K` and triage has assignable items for it; once `triage --apply` has run, it is not (D4).
- **V4** — `triage` dedups the three identical awaiting items to one, assigns an unowned item whose tag names one beat, lists an ambiguous one, creates one task item per unexecuted CONVERGED plan and is idempotent on a second run (D2).
- **V5** — a one-window repo (`git worktree list` shows only the main checkout) gives its merge owner D3 on its own queue and never D4; a repo with worktrees gives its merge owner D4 and never D3 (D3, D4).
- **V6** — measured after one week in the hub: the share of worker turns that ended with no claim while `ready --mine` was non-empty (target 0, from the Stop-hook log), and the open items owned per agent (target: no worker below `K` while assignable items exist).

## Decisions taken

- **Push into owned queues, pull at the worker (B)** over idle-notice dispatch (A) and queues plus idle wake (C) — the judge panel ranked B first 3 of 3 (see Rejected alternatives).
- **Enforcement is a Stop refusal on both sides**, not advice — closes the coordinator-skips-assigning gaming path the panel named.
- **The worker reads owned-then-unowned (`ready --mine`)** — closes B's drain gap without waiting for the coordinator.
- **`K = 3`**, per-repo override; reversible.
- **Triage never drops or reprioritises on its own** — it proposes; the coordinator decides and the decision is recorded by `assign`/`drop`.
- **The quota bands and DECISION blocks outrank D3/D4** — only GREEN starts new work (AMBER finishes, RED/WALL checkpoints — CLAUDE.md), and an accepted DECISION means the turn is legitimately waiting on the operator.

## Rejected alternatives

- **A — Idle-notice dispatch** (`notify_when_idle` per peer, re-armed after each one-shot notice, assign on notice): same-machine only, so one-window repos and cross-machine peers get nothing; a coordinator that is offline or forgets to re-arm stops the whole mechanism for up to 12 hours; ranked last by all three judges.
- **C — Owned queues plus idle wake:** closes B's drain gap for same-machine peers but carries A's re-arm fragility and roughly doubles the mechanism; D3's owned-then-unowned read closes the same gap with no messaging dependency.
- **An external dispatcher daemon (cron/systemd):** `SendMessage` is a tool inside a Claude session, so a daemon cannot deliver an assignment to a window; it could only write the store, which D2 already does inside the coordinator's turn.
- **Pure self-service (today):** measured above — owner skew and a flat priority field leave work unassigned while agents idle.
- **Assign everything up front (no floor):** front-loads queues that the next reprioritisation must unwind; the field calls this the prefetch starvation problem (Celery, below).

## Lifecycle

- **Adoption:** the hub first (its coordinator, infra, runs the first `triage --apply`: dedups the awaiting items, routes the 54 unowned, surfaces the 9 plans); the template sentence and the synced hook carry it to every project on the next sync. A project repo without a work store is untouched (both causes need a store).
- **Growth:** at more than one coordinator turn per hour of worker drain (V6 shows workers hitting the floor between coordinator turns), raise `K` for that repo; at more than ~1,000 open items, `queue --json` gets an index file instead of a full scan (measure first).
- **Degradation:** messaging off or cross-machine → D3 still binds at the worker's Stop; coordinator offline → workers keep claiming owned and then unowned items until the queue is empty; the store unreadable → both causes stay silent (fail-open, like every Stop cause).
- **Retirement:** superseded only by a scheduler that owns windows directly; until then this is the dispatch layer.

## External dependencies

| Dependency | Fact used | Source (fetched 2026-10-02) |
|---|---|---|
| Claude Code cross-session messaging | `ListAgents` rows carry names and working directories, no busy/idle field; `notify_when_idle` is one-shot, same-machine, dropped after 12 h; a message to an idle session "starts a new turn with the message", a busy one reads it "between tool calls" | https://code.claude.com/docs/en/cross-session-messaging (WebFetch; an exa copy of the page was an older revision without `notify_when_idle`) |

## Approach grounding (current practice)

| Claim | Source (fetched 2026-10-02, tool) |
|---|---|
| Prefetch/push without demand starves idle workers while busy ones hoard: "Prefetch caused busy workers to hold tasks in reserve while idle workers sat empty" | https://github.com/celery/celery/pull/9863 (exa search) |
| The demand-gated pull: "the worker fetches a new task only when an execution slot is free" | https://docs.celeryq.dev/en/stable/userguide/optimizing.html (exa search) |
| The production hybrid — a server-held queue workers poll "only when it has spare capacity" | https://docs.temporal.io/task-queue (exa fetch) |
| Orchestrator–workers: "a central LLM dynamically breaks down tasks, delegates them to worker LLMs" | https://www.anthropic.com/engineering/building-effective-agents (exa search) |
| Its failure mode: "Without detailed task descriptions, agents duplicate work, leave gaps" | https://www.anthropic.com/engineering/multi-agent-research-system (exa search) |
| Lease TTL ≥3× the heartbeat as the dead-worker signal | https://hackernoon.com/building-distributed-leases-with-consensus-heartbeats-and-fencing-tokens (exa fetch) |

## fabrik-lib verdict

BUILD, hub tooling — no fabrik-lib module covers agent work distribution; the change extends the hub's own `work.py` and Stop hook. Not a fabrik-lib candidate (governance machinery, not an app capability).

## Shape/infra implications

None: no service, no port, no `shape:` flag. Hub scripts and a fleet-synced hook.

## Constraints

| Rule | Verbatim | Applies to |
|---|---|---|
| `.windsurf/rules/core/10-python.md:220` | "**`datetime.now(UTC)`, never `datetime.utcnow()`**" | the stale-age computation in D2 |
| `.windsurf/rules/core/40-documentation.md:241` | "**No skipped heading levels**" | D7's doc rewrites |
| `.windsurf/rules/core/40-documentation.md:243` | "**Fenced code blocks only**" | D7's doc rewrites |
| CLAUDE.md § THE FIX DIRECTIVE 5 | "the cheapest way to satisfy it without producing the outcome is written down IN THE SAME CHANGE" | D3, D4 — see Cobra below |

**Cobra (D-253):** the cheapest way past D3 is to claim an item and never work it — the counter is the existing lease (2 h, renewed only by the session's own writes) and the banner showing who is "on it"; the cheapest way past D4 is to assign anything to anyone — the counter is beat routing (triage proposes by charter) and the priority the coordinator must record; the cheapest way to look busy is to assign the same item twice — `claim`'s fencing token refuses a second live holder.

## Documentation landing sites

- `docs/reference/work-tracking.md` § Ownership and the distributor — the rule and the two verbs (D7).
- `docs/reference/multi-agent-operating-model.md` § Claim or assign — the duty split (D7).
- `docs/workstation/hooks-index.md` — the eighth cause and the extended seventh.
- `templates/governance/CLAUDE.md` and hub `CLAUDE.md` — one sentence per duty beside D-471.
- `CHANGELOG.md`, `docs/DECISIONS.md` (the build's D-row).

## Open unknowns

- **U1 — K's right value** is a planning figure, not a measurement; V6's week of data resolves it (resolution: re-measure, adjust `queue_floor`).
- **U2 — beat routing precision:** how many of the 54 unowned items route unambiguously by tag/title; resolution: `triage` reports the ambiguous list on its first hub run and the plan sizes the matcher from that count.
- **U3 — the eighth cause's interaction with a long human pause** (the operator away, workers keep claiming): bounded by the quota bands and the 3-attempt cap; resolution: V6 reads the Stop-hook log for turns refused more than once in a row.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "merge owner and coordinator ais must always sort out waiting tasks" | IN | D2 triage, D4 coordinator cause |
| I2 | "strategic_backlog" | IN | D2 (the backlog is rendered from the store's `backlog` items, D-413) |
| I3 | "work" | IN | D1, D2 over `.fabrik/work/` |
| I4 | "specs plans" | IN | D2 step 3 — unexecuted CONVERGED plans and plan-less CONVERGED specs become items |
| I5 | "proactively assign them to other windows" | IN | D2 `--apply`, D5 notice, D6 floor |
| I6 | "so that no agent waits idle if there is work to be done" | IN | D3 worker cause, D4 coordinator cause |
| I7 | "we encourage maximum subagent utilization where it adds value for all our commands/skills" | OUT-OF-SCOPE | delivered by D-511 (`scripts/sysadmin/dispatch_headroom.py`, commit fdfffb228), which sizes the fan-out of 31 of 38 commands |
| I8 | waiting mail ("waiting tasks"; 53 mails need an answer) | IN | D2 — `mail` items are store items (8 open today) and route by addressee |
| I9 | duplicated awaiting-operator items (3 copies of one question) | IN | D2 step 1 |
| I10 | every repo, not only the hub (D-471: "in each repo the agent which is not on worktree must be merge owner and coordinator") | IN | D7 template sentence; Lifecycle adoption; V5 one-window repos |
