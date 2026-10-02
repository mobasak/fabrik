# Coordinator proactive assignment — no window idles while work exists

Status: DRAFT
Profile: delta — every item changes an engine that exists today: the work store (`scripts/work.py`), the Stop hook (`.claude/hooks/final_gate_stop.py`) and the multi-agent model docs.

Work item: W-83021827 · Decision: D-512 · Owner: infra (the hub's merge owner and coordinator, D-471)

## Personas

| Persona | Who | What they need from this | Duty this spec gives them |
|---|---|---|---|
| **Operator (PRIMARY)** | the person running the windows | *"merge owner and coordinator ais must always sort out waiting tasks, strategic_backlog, work, specs plans and proactively assign them to other windows so that no agent waits idle if there is work to be done."* (D-512) | none — the point is that they never dispatch by hand |
| Coordinator agent | the one agent in a repo's main checkout: merge owner and distributor (D-471); `infra` in the hub | a short, executable way to keep every worker supplied | **triage** the waiting work and **top up** each present worker's owned queue; refused at its own Stop while a present worker is under the floor and work on its beat is assignable; it is the `distributor` in `config.json` |
| Worker agents | agents 2..N in worktrees (`fleet`, `intel` in the hub; named agents in projects) | to always know their next item without asking | **claim an owned item** instead of ending a turn idle; refused at Stop while it owns ready items and claims none |
| One-window agent | a project repo with a single window: coordinator and worker are the same agent | the same rule without a second window | its own queue is the worker queue; the worker cause applies to it |
| The Stop hook (automated) | `.claude/hooks/final_gate_stop.py`, fleet-synced | facts it can compute from the store, without `ListAgents` | enforces both new causes, each with its own counter slot; warns through after 3 attempts like every cause |
| `work.py` (automated) | the store's CLI | — | gains `triage` (report + top-up plan) and `queue` (per-agent depth) |

**Step budget (the primary loop, counted):** the operator opens the windows (1) and answers only the decisions that are theirs (2, when any exist). Every other step — triage, assignment, claiming the next item — happens without them. **Operator steps for dispatch: 0.** A design that asks the operator to say "take the next item" has broken the budget.

## Goal

No agent window ends a turn idle while there is assignable work in its repo. The coordinator keeps a triaged, owned queue in front of every worker; a worker always claims an item it owns rather than ending idle; the Stop hook makes both duties binding, within the quota bands and the operator's own gates.

## Why this exists

The work-tracking design made the distributor an occasional role: *"Assigning is not the default way work moves: an idle worker claims from `ready` itself"* (`docs/reference/work-tracking.md:138-141`; `docs/reference/multi-agent-operating-model.md:218-220`, D-442). Measured 2026-10-02 over the hub store's 656 item files tracked at commit a3bd668a1 (`git ls-files '.fabrik/work/W-*.json'`; untracked new items excluded — later commits move these counts):

- **384 open items**: 340 backlog, 38 task, 6 mail (plus 7 awaiting-operator).
- **Owner skew:** infra owns 246, fleet 71, intel 9, operator 4, and 54 have no owner. So one worker can run dry while another owns a pile; a self-service puller has no reason to rebalance.
- **No triage signal:** 365 of 384 sit at the default priority 2, so `ready`'s `(priority, created, id)` sort (`scripts/work.py:724`) degenerates to oldest-first.
- **Stale:** 130 items not yet closed (open or awaiting-operator) are older than 14 days, 43 older than 30.
- **Waiting approvals duplicated:** 7 awaiting-operator items, 3 of them the same question (W-7eda7b6c, W-0aea1bba, W-2c7c08a6).
- **Unexecuted plans:** 9 of the 25 live plan documents that carry a Status line read CONVERGED, not EXECUTED (ticket files and `archived/` excluded); no item names an owner for them.

Nothing today tells the coordinator that a peer is idle (no script computes it — the grounding sweep found none), and nothing stops a worker from ending its turn with work available. The operator dispatches by hand. This design removes that.

## What exists today (grounded)

- `scripts/work.py:2669-2701` `cmd_assign` — sets `owner`, `priority`, `tags`; gated to `config.json`'s `distributor` (`:2684-2687`).
- `scripts/work.py:708-727` `_ready_from` — open, unblocked, unclaimed, non-`next` items sorted `(priority, created, id)`; with `mine=True` returns the caller's owned items, then unowned items (`:727-729`); items owned by another agent are excluded.
- `scripts/work.py:2769-2776` `cmd_next` — the first item of that `mine` ordering.
- `scripts/work.py:2891-2934` `claim` — a 2-hour lease (`DEFAULT_LEASE_S`, `:87`) with a fencing token, stored in the git common dir (`:272-286`, `:883-884`); claiming never reads `owner`.
- `scripts/work.py:3812-3861` `prompt_block` — the per-prompt `work:` banner (ready count, live claims per session).
- `.claude/hooks/final_gate_stop.py` — seven blocking causes, each capped at 3 attempts (`:46`); the seventh, a waiting merge request, fires only for the resolved merge owner via `whoami_agent.py --who` and `decisions.py --merge-owner` (`_merge_owner_duty`, `:1663-1753`), and only once a request waits — its early return (`:1712`) runs no resolver otherwise.
- `scripts/merge_request.py:418-420` — the coordinator is notified by mail plus a printed `SendMessage to=<name>:` doorbell; the same pattern carries an assignment notice.
- Charters: `docs/reference/agents/infra.md:12-18`, `fleet.md:11-18`, `intel.md:19-33` — each agent's beat, the routing key for triage.
- Claude Code messaging (external, below): no idle state in `ListAgents`; idle is observable only through `notify_when_idle`.

## The delta

**D0 — Terms (one definition, used by every item below).**
- **Main checkout** — the first entry of `git worktree list --porcelain` (the same resolution CLAUDE.md § EXIT uses for `MAIN`). Its store, `<main>/.fabrik/work/`, is the **store of record for assignment**: the coordinator writes `owner` there and commits it on the base branch (`base_branch` in `config.json`).
- **Coordinator** — the agent named by `config.json`'s `distributor`, the one identity `assign` and `triage` accept when it is set (`scripts/work.py:2684-2687`); D-471 makes it the merge owner too, and where the two disagree the distributor wins, because it is the identity that can carry out what D4 asks. When no distributor is named — 37 of the 42 stores on this box today (`config.json` read 2026-10-02) — the coordinator is the merge owner (`decisions.py --merge-owner`, the resolver cause seven already runs), and `assign`/`triage` stay open to any caller as `assign` is today. Today that fallback resolves nothing: all 37 of those repos also have no declared merge owner (`decisions.py --merge-owner` → UNDECLARED) and none has a worker yet. So adoption (Lifecycle) writes `distributor` into a repo's `config.json` before its first worker counts, and a multi-window repo whose coordinator still resolves to nobody gets one advisory line from D4 naming that key — never a silent pass and never a block.
- **Agent name** — a worker's agent name is its worktree `<name>` (the launch recipe, `docs/reference/multi-agent-operating-model.md:25`); top-up assigns to that name, and D3 looks up owned items by the session's own resolved name. A window bound under a different name is not that worker.
- **Worker** — a linked worktree registered in `<git common dir>/worktrees/*/gitdir` whose path is `<main>/.claude/worktrees/<name>` and whose `<name>` is not a harness id. Harness ids are `agent-` plus 16 or more hex digits (the hub's are 17, e.g. `.claude/worktrees/agent-a5dabb83737b0534f`); `agent-2` and other short names stay workers. Reading the registry files, not listing the folder, skips a symlink or a leftover directory under `.claude/worktrees/` that git does not know.
- **Multi-window repo** — one with at least one worker. A **one-window** repo has none; there the coordinator is also the only worker.
- **Present** — a worker is present while a process named `claude`, owned by the same user, has the worker's worktree (or a folder inside it) as its working directory (`/proc/<pid>/cwd`). An open window counts whether it is busy or idle, including one that moved into its worktree with `EnterWorktree`, which moves the process's working directory (`docs/workstation/session-recall.md:42-44`); a closed one stops counting at once; a worktree of another repo never counts. Where `/proc` cannot be read, presence is unknown and every presence-dependent step stands down (fail-open).

**D1 — `work.py queue`: per-agent queue depth (read-only).** Prints one row per worker and one for the coordinator, and with `--agent <name>` only that agent's row: whether it is present (the coordinator always is in its own checkout), the number of open, ready, unclaimed items it owns in the store of record, its live claim if any, and the floor `K`. `--json` prints ONE line (the Stop hook keeps a resolver's first stdout line only, `.claude/hooks/final_gate_stop.py:1636`). Pure read; no lock beyond the existing store read.

**D2 — `work.py triage`: the coordinator's sort (coordinator-only, like `assign`).** One pass over the store of record that:
1. **Dedups** awaiting-operator items that ask the same question with the same ground — the same block digest, or else the same normalised question (lower-cased, whitespace collapsed, `(also asked as …)` removed) AND the same `ground`. The hub's three copies of one question carry three different digests, so the normalised question is the path real data takes. Each copy is dropped with `drop --duplicate-of <keep>` (the oldest is kept), inside `_drop_duplicate`'s own permission rule (`scripts/work.py:2976-3043`). This is the only drop triage makes.
2. **Routes by beat** — an unowned item whose `tags`, links or title match exactly one charter's beat gets that owner; an ambiguous one is listed for the coordinator, never guessed.
3. **Surfaces derived work** — every live plan whose first Status line reads CONVERGED (plain `Status:` or bold `**Status:**`; 4 of the hub's 9 use the bold form) and not EXECUTED, and every CONVERGED spec with no plan, becomes a `task` item linking it — once: an open or closed item already linking that path stops a second one.
4. **Lists stale items** (older than 14 days, no claim in that time) for the coordinator to keep with a priority or drop with a reason; triage never drops them itself.
5. **Reclaims from absent workers** — an item carrying the `triaged` tag whose owner is not present and that has no LIVE claim (`_is_live`, `scripts/work.py:926`) and no closed-marker FILE of any age returns to unowned and loses the tag. Hand assignments are never reclaimed: `assign --owner` removes `triaged` unless the same call adds it.
6. **Prints the top-up plan** — for each present worker below `K`, the next unowned items routed to its beat, by priority, then age. Off-beat and ambiguous items are never assigned by the plan. `--apply` runs the assigns (tagging each `triaged`) and step 5; without `--apply`, triage only reports.
7. **Lists off-beat assignments** — every owned, unclaimed item whose beat route names a different agent than its owner, so a hand assignment made only to lift a count shows up in the coordinator's own report.
Triage never writes an item that has a live claim or a closed-marker file of any age: while a worker holds it, or once it is closed, the item is the worker's. The age matters: `_closed_ids` stops honouring a marker after 14 days (`MARKER_MAX_AGE_S`, `scripts/work.py:88`, `:1064-1079`), and a `done` waiting longer than that in an unmerged branch must not return to the pool. Claim records are never deleted — `release` and `done` only zero the lease (`_end_claim`, `:952-957`) — so the rule is on the LIVE claim, not on the record's existence; an item a worker wrote, released and left can conflict when that worker's branch merges, and `merge_request.py` already refuses that conflict with its own remedy. Priorities stay the coordinator's judgment: triage proposes, `assign --priority` records it.

**D3 — Worker Stop cause (eighth cause): "idle with owned work."** At a Stop, in a repo with a work store, the cause blocks when all of these hold:
- the session runs in a worker's worktree, or in the main checkout of a one-window repo;
- the session resolves to an agent name (`whoami_agent.py --who`, the session id passed in the resolver's environment as cause seven does) — a nameless session (a headless `claude -p`, an operator one-off) is never refused;
- it holds no live claim (a claim record whose `session` is this session);
- the agent OWNS at least one open, ready, unclaimed item in the store of record (read with `work.py --repo <main> queue --json --agent <name>`). Unowned items never trigger it: they reach a worker through the coordinator's beat-routed top-up, so the cause never orders a worker onto off-beat work or a serialising act the coordinator has not handed out (`docs/reference/multi-agent-operating-model.md:205-225`);
- no command run record is `running`, and the session's own quota band is GREEN — the band the `QUOTA:` line computes for this session (`_load_posture` then `_band_for_session(posture, transcript_path)`, `scripts/sysadmin/quota_posture_hook.py:179`, `:477`; on a Fable model that is the Fable band), imported by absolute path from `/opt/fabrik/scripts/sysadmin/` inside a guard so a failed import stands the cause down. A missing, stale or unreadable posture stands the cause down, the posture hook's own charter ("a session must never be trapped", `scripts/sysadmin/quota_posture_hook.py:25-29`); the hook already yields to the `fleet-exhausted` hold before any cause runs (`final_gate_stop.py:3301-3311`);
- the turn did not end on an accepted DECISION NEEDED block or a formatted `BLOCKED:` escalation — a `BLOCKED:` header with `searched:` and `missing:` before the footer (`_blocked_header`, `final_gate_stop.py:2380`), the same two exemptions the stall cause honours.
Block text: *"You own `<n>` ready item(s), first `<id> — <title>`: claim it with `python3 scripts/work.py --repo <main> claim <id>` and start it — or end on a formatted `BLOCKED:` escalation (header, `searched:`, `missing:`) naming why it cannot start."* Its own counter slot; capped at 3 attempts like every cause.

**D4 — Coordinator Stop cause (ninth cause): "a worker is under-supplied."** Only in the main checkout of a multi-window repo, checked cheapest first:
1. a present worker exists (the worktree registry and `/proc`, file reads only — no subprocess otherwise);
2. the session resolves to the coordinator (D0: `whoami_agent.py --who` equals `distributor`, or, with no distributor named, the `decisions.py --merge-owner` answer) — every other session, named or not, stops here;
3. `work.py queue --json` shows a present worker below `K` **and** `work.py triage --json`'s top-up plan has an item for it.
Then it blocks: *"<worker> has <n> of K items queued and <m> on its beat are assignable: run `python3 scripts/work.py triage --apply`, commit the store, then send the assignment line it prints."* It is a cause of its own: its own counter slot, block prefix and kaizen cause name, so it never shares cause seven's attempt count (`:472-476`: "Each cause owns its OWN slot"). The run-record, quota and DECISION/`BLOCKED:` exemptions of D3 apply.

**D5 — The assignment notice and how a worker takes the item.** `triage --apply` writes `owner` into the store of record; the coordinator commits it on the base branch, then sends the one `SendMessage to=<worker>: assigned <ids> — <titles>` line per worker that `--apply` printed (the doorbell pattern of `merge_request.py:418-420`). The worker claims through the store of record (`work.py --repo <main> claim <id>`): claims live in the shared git common dir (`scripts/work.py:283-286`), so the claim needs no copy of the item in the worker's own tree and is seen in every tree at once. Before its first WRITE to the item (a note, `done`), the worker catches its branch up with the base branch (`git merge <base>`); that merge is clean for the item because triage never writes an item after a claim record exists (D2), and the worker has not written it before. The notice is a speed-up: D3 reads the store of record directly, so a worker the notice never reached is still refused at its next Stop.

**D6 — `K`, the queue floor.** Default 3 owned-ready items per worker (`work.py` constant `QUEUE_FLOOR`, overridable per repo in `.fabrik/work/config.json` as `queue_floor`). Three keeps a worker supplied across a coordinator turn of normal length without front-loading the queue that a reprioritisation would have to unwind.

**D7 — Docs and the rule text.** `docs/reference/work-tracking.md` § Ownership and the distributor and `docs/reference/multi-agent-operating-model.md` § Claim or assign are rewritten: the coordinator assigns by default and keeps every present worker at `K`; a worker claims an item it owns rather than ending idle; self-service claiming of unowned work remains the fallback. The project contract gains the two duties in one sentence each beside D-471's merge-owner rule — the coordinator's sentence includes naming itself as `distributor` in `.fabrik/work/config.json`, the adoption step Lifecycle relies on — (`templates/governance/CLAUDE.md:48`, which ends "…and it alone runs `work.py assign`."); the hub `CLAUDE.md` carries no D-471 sentence, so its mirror goes beside its own merge-owner rule in § Behavior, the Shared repo bullet ("the MAIN CHECKOUT's writers are agent-1 (infra, the merge owner)").

## Contract deltas

No data-contract or UI change. Interface changes: two `work.py` verbs (`queue [--json]`, `triage [--apply] [--json]`), one config key (`queue_floor`), one item tag with a meaning (`triaged`), one change to `assign` (`--owner` removes `triaged` unless the same call adds it), and two Stop-hook causes (D3 eighth, D4 ninth) with two new counter slots. `ready`, `next` and `claim` are unchanged. **Mirror — the counter file grows from 7 to 9 fields.** `_read_counters` (`final_gate_stop.py:468-486`) already pads a short file with zeros, so a 7-field file from before the upgrade reads the new slots as 0 once `_COUNTER_SLOTS` is 9. What breaks is everything else that spells seven fields: the 8 positional writes (`:3377 :3438 :3496 :3548 :3584 :3590 :3750 :3762`), the 2 seven-name unpacks (`:3368 :3714`, an unpack of the wrong width crashed every Stop for ~12 h once, `:3702-3704`) and the delete guard at `:3581` (`if not any((g, c, p_att, r_att, v_att, m_att))`, which would delete a live D3/D4 count). All of them move to one reader/writer pair over a 9-slot record. Each new slot follows `m_att`'s rule: it rises on its own cause's block, resets when its own cause is false, and every other cause's write carries it through unchanged.

## Cost

Code ≈480 lines across `scripts/work.py` (D0–D2, D6 ≈290) and `.claude/hooks/final_gate_stop.py` (D3, D4 and the counter reader/writer ≈190), plus the template/docs (D7, prose); tests excluded. Runtime per Stop: D3 costs two subprocesses (`whoami_agent.py --who`, `work.py --repo <main> queue --json`), each under the hook's 5 s resolver timeout (`:1552`); D4 costs none unless a present worker exists, then one (`whoami_agent.py --who`) for every session, one more (`decisions.py --merge-owner`) only in a store with no distributor, and two more (queue, triage) only for the coordinator. V9 measures both. Tokens: one triage pass per coordinator turn that needs it — reports are bounded to the top-up plan and the stale list.

## Validation

- **V1** — a worker session with no claim and one item it OWNS in the store of record is refused at Stop with the item named, though its own worktree's copy of the store predates the assignment; with a claim, with nothing owned, or with only unowned items ready, it is not (D3, D5). Red-first.
- **V2** — the same worker at quota AMBER, RED or WALL, with a missing or stale posture, with a `running` run record, ending on an accepted DECISION block or a formatted `BLOCKED:` escalation, or with no resolvable agent name, is not refused; a one-line `BLOCKED:` without `searched:`/`missing:` is (D3 exemptions).
- **V3** — the coordinator is refused while a present worker is below `K` and triage has a beat-matching item for it; once `triage --apply` has run, it is not; a worker with no `claude` process in its worktree never refuses it, a `claude` process in a folder inside the worktree counts, a process in another repo's worktree does not, and an unreadable `/proc` stands D4 and the top-up down; a non-coordinator session in the main checkout never reaches the queue call; with no distributor named the merge owner is the coordinator, and with neither resolvable D4 prints one advisory line and never blocks; D4's attempts never move cause seven's counter, nor the reverse (D4).
- **V4** — `triage` dedups three awaiting items with the same question, same ground and three different digests to one, and keeps two with the same question and different grounds; assigns an unowned item whose tag names one beat and lists an ambiguous one; creates one task item per unexecuted CONVERGED plan (plain and bold Status forms) and per CONVERGED spec with no plan; lists an item older than 14 days with no claim; returns a `triaged` item of an absent worker with only an ENDED claim to unowned, leaves one with a live claim and a hand-assigned one alone; lists an off-beat owned item; never writes an item with a live claim or a closed-marker file of any age; is idempotent on a second run (D2).
- **V5** — a one-window repo gives its coordinator D3 on its own owned items and never D4; in a multi-window repo the coordinator gets D4 and never D3, and a worker gets D3 and never D4; a repo whose only linked worktrees are harness ones, or whose `.claude/worktrees/` holds only a symlink, is one-window (D0, D3, D4).
- **V6** — `queue` reports present/absent, owned-ready count, live claim and `K` per worker and for the coordinator, `--agent <name>` returns that row alone, and `queue --json` is one line; `queue_floor` in `config.json` overrides `QUEUE_FLOOR` (3) and a missing or invalid value falls back to 3 (D1, D6).
- **V7** — every 7-field counter file reads its two new slots as 0; a block by any earlier cause leaves the D3 and D4 counts intact; the delete guard never removes a file holding a live D3/D4 count (the mirror in Contract deltas).
- **V8** — a worker that claimed through `--repo <main>`, then caught up with `git merge <base>`, merges cleanly and can close the item in its own tree (D5).
- **V9** — measured after one week in the hub, from the kaizen events D3 and D4 write on every block and every exemption: the share of worker turns that ended with no claim while the worker owned ready items (target 0), the open items owned per present worker (target: none below `K` while beat-matching items are assignable), the off-beat assignments triage listed, and the Stop-time cost of both causes (target: under 1 s median).
- **V10** — the docs and both contracts state the two duties (D7): `tests/test_work_contract_rule.py` and `tests/test_governance_template_split.py` stay green, and the new sentences are pinned by a grader.

## Decisions taken

- **Push into owned queues, pull at the worker (B)** over idle-notice dispatch (A) and queues plus idle wake (C) — the judge panel ranked B first 3 of 3 (see Rejected alternatives).
- **Enforcement is a Stop refusal on both sides**, not advice — closes the coordinator-skips-assigning gaming path the panel named.
- **The worker cause reads OWNED items only** — unowned work reaches a worker through the coordinator's beat-routed top-up, so D3 never orders a worker onto off-beat work or an unassigned serialising act. A worker may still claim unowned work by itself (`next` is unchanged); it is only never refused for not doing so.
- **The main checkout's store is the store of record for assignment** (D0, D5) over a shared-folder owner overlay: an overlay would be a second source of truth for `owner` beside the committed item, and it still could not make an item created on the base branch claimable in a worktree whose branch predates it; claiming through the store of record and catching up before the first write do both with no new record.
- **Presence is a live `claude` process in the worktree** (D0) over a whoami binding or a claim in the last 24 h: windows launched with `CLAUDE_AGENT=<name>` write no binding, a binding is written once at bind time and kept 30 days, and the whoami store is box-wide, so either record calls a fresh window absent and a closed one present. Only present workers are topped up, and triage reclaims its own assignments from absent ones — an assignment to a closed window would hide work from every live worker (`ready --mine` excludes items owned by another agent, `scripts/work.py:727-729`).
- **The coordinator is the `distributor`** (D0), the identity `assign` and `triage` accept, so D4 never asks a session for an act it would be refused.
- **`K = 3`**, per-repo override; reversible.
- **Triage drops only duplicates and never reprioritises** — a duplicate is the same digest, or the same normalised question with the same ground (D2 step 1); every other drop and every priority is the coordinator's decision, recorded by `assign`/`drop`.
- **The quota bands, DECISION blocks and `BLOCKED:` escalations outrank D3/D4** — AMBER finishes, RED/WALL checkpoints (CLAUDE.md), an accepted DECISION means the turn waits on the operator, and a formatted `BLOCKED:` is the contract's one legitimate halt. A missing or stale posture stands both causes down, the posture hook's fail-open charter; V9 counts how often that happens.

## Rejected alternatives

- **A — Idle-notice dispatch** (`notify_when_idle` per peer, re-armed after each one-shot notice, assign on notice): same-machine only, so one-window repos and cross-machine peers get nothing; a coordinator that is offline or forgets to re-arm stops the whole mechanism for up to 12 hours; ranked last by all three judges.
- **C — Owned queues plus idle wake:** closes B's drain gap for same-machine peers but carries A's re-arm fragility and roughly doubles the mechanism; D3's owned-item read plus the coordinator's top-up closes the same gap with no messaging dependency.
- **An external dispatcher daemon (cron/systemd):** `SendMessage` is a tool inside a Claude session, so a daemon cannot deliver an assignment to a window; it could only write the store, which D2 already does inside the coordinator's turn.
- **Pure self-service (today):** measured above — owner skew and a flat priority field leave work unassigned while agents idle.
- **A shared-folder owner overlay** (`<git common dir>/fabrik-work/assigned/<id>.json`): rejected in Decisions taken — a second owner record, and no help for items the worker's branch lacks.
- **Presence from whoami bindings or recent claims:** rejected in Decisions taken — wrong in both directions for the windows the hub actually runs.
- **A worker cause over owned-then-unowned items:** every worker would be refused at every Stop while any unowned item exists (54 in the hub today), including off-beat items and serialising acts.
- **Assign everything up front (no floor):** front-loads queues that the next reprioritisation must unwind; the field calls this the prefetch starvation problem (Celery, below).

## Lifecycle

- **Adoption:** each repo's coordinator first writes `distributor` into its `.fabrik/work/config.json` (the hub already has `infra`; 37 of 42 stores have none today) — the template sentence (D7) names that step, so a repo leaves the D0 fallback when its coordinator adopts, and D4's advisory names the key until then. Then the hub first (its coordinator, infra, runs the first `triage --apply`: dedups the awaiting items, routes the 54 unowned, surfaces the 9 plans); the template sentence and the synced hook carry it to every project on the next sync. A project repo without a work store is untouched (both causes need a store).
- **Growth:** at more than one coordinator turn per hour of worker drain (V6 shows workers hitting the floor between coordinator turns), raise `K` for that repo; at more than ~1,000 open items, `queue --json` gets an index file instead of a full scan (measure first).
- **Degradation:** messaging off → D3 still binds at the worker's Stop (it reads the store of record directly); the quota posture missing or stale → both causes stand down (fail-open); `/proc` unreadable → presence is unknown and D4 and the top-up stand down; coordinator offline → workers finish their owned items and may claim unowned ones by themselves; a worker window closed → it is absent at once, stops counting for D4, and its unclaimed `triaged` items return to the pool at the next triage; the store unreadable or a resolver failing → both causes stay silent (fail-open, like every Stop cause).
- **Retirement:** superseded only by a scheduler that owns windows directly; until then this is the dispatch layer.

## External dependencies

| Dependency | Fact used | Source (fetched 2026-10-02) |
|---|---|---|
| Claude Code cross-session messaging | `ListAgents` rows carry names and working directories, no busy/idle field; `notify_when_idle` is one-shot, same-machine, dropped after 12 h; a message to an idle session "starts a new turn with the message", a busy one reads it "between tool calls" | https://code.claude.com/docs/en/cross-session-messaging (WebFetch; an exa copy of the page was an older revision without `notify_when_idle`) |

## Approach grounding (current practice)

| Claim | Source (fetched 2026-10-02, tool) |
|---|---|
| Prefetch/push without demand starves idle workers while busy ones hoard: "Prefetch caused busy workers to hold tasks in reserve while idle workers sat empty" | https://github.com/celery/celery/pull/9863 (exa search) |
| The demand-gated pull: "the worker fetches a new task only when an execution slot is free" — Celery's own fix had a regression report and is limited to the Redis broker today, so it is cited for the starvation mechanism, not as settled tooling | https://docs.celeryq.dev/en/stable/userguide/optimizing.html (exa search; re-fetched 2026-10-02) |
| The production hybrid — a server-held queue workers poll "only when it has spare capacity" | https://docs.temporal.io/task-queue (exa fetch) |
| Orchestrator–workers: "a central LLM dynamically breaks down tasks, delegates them to worker LLMs" | https://www.anthropic.com/engineering/building-effective-agents (exa search) |
| Its failure mode: "Without detailed task descriptions, agents duplicate work, leave gaps" | https://www.anthropic.com/engineering/multi-agent-research-system (exa search) |
| A lease TTL is sized to ≥3× a heartbeat — which is why presence here is NOT a lease: an idle open window sends no heartbeat at all, so D0 reads the live process instead, and only the existing 2 h claim lease stays a lease | https://hackernoon.com/building-distributed-leases-with-consensus-heartbeats-and-fencing-tokens (exa fetch; a practitioner post citing Kleppmann and the Kubernetes Lease API) |

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

**Cobra (D-253):** the cheapest way past D3 is to claim an item and never work it — the counter is the existing lease (2 h, renewed only by the session's own writes) and the banner showing who is "on it". The second cheapest is a hollow escalation, `searched: nothing — missing: nothing` — the same seam the stall cause already accepts (`_blocked_header`'s own Cobra note, `final_gate_stop.py:2387`), and V9 counts D3's exemptions by kind so a rise shows. The cheapest way past D4 is to hand-assign anything to a worker to lift its count — `assign` checks no beat, so the counter is triage's off-beat list (D2 step 7) in the coordinator's own report and V9's off-beat count. The cheapest way to keep `triaged` items from being reclaimed is to keep an idle window open — that window is present and owns ready items, so D3 refuses it until it claims. The cheapest way to look busy is to assign the same item twice — `claim`'s fencing token refuses a second live holder.

## Documentation landing sites

- `docs/reference/work-tracking.md` § Ownership and the distributor — the rule and the two verbs (D7).
- `docs/reference/multi-agent-operating-model.md` § Claim or assign — the duty split (D7).
- `docs/workstation/hooks-index.md` — the eighth and ninth causes and the 9-slot counter.
- `templates/governance/CLAUDE.md` and hub `CLAUDE.md` — one sentence per duty beside D-471.
- `CHANGELOG.md`, `docs/DECISIONS.md` (the build's D-row).

## Open unknowns

- **U1 — K's right value** is a planning figure, not a measurement; V6's week of data resolves it (resolution: re-measure, adjust `queue_floor`).
- **U2 — beat routing precision:** 16 of the 54 unowned items carry exactly one agent name as a tag (counted 2026-10-02 over the tracked items) and route trivially; how many of the other 38 route by charter vocabulary is unknown. Resolution: `triage` reports the ambiguous list on its first hub run and the plan sizes the matcher from that count.
- **U3 — the eighth cause on a conversational turn.** An agent that owns ready items and holds no claim is refused even when its turn only answered the operator (most often a one-window coordinator with hand-owned items). Accepted residual: bounded by the 3-attempt cap, and claiming the item or a formatted `BLOCKED:` clears it; resolution: V9 counts D3 blocks that end in warn-through, and above 1 in 10 the cause gains a turn-kind exemption.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "merge owner and coordinator ais must always sort out waiting tasks" | IN | D2 triage, D4 coordinator cause |
| I2 | "strategic_backlog" | IN | D2 (the backlog is rendered from the store's `backlog` items, D-413) |
| I3 | "work" | IN | D1, D2 over `.fabrik/work/` |
| I4 | "specs plans" | IN | D2 step 3 — unexecuted CONVERGED plans and plan-less CONVERGED specs become items |
| I5 | "proactively assign them to other windows" | IN | D2 `--apply`, D5 notice, D6 floor |
| I6 | "so that no agent waits idle if there is work to be done" | IN | D3 worker cause, D4 coordinator cause, D0 presence |
| I7 | "we encourage maximum subagent utilization where it adds value for all our commands/skills" | OUT-OF-SCOPE | delivered by D-511 (`scripts/sysadmin/dispatch_headroom.py`, commit fdfffb228), which sizes the fan-out of 31 of 38 commands |
| I8 | waiting mail ("waiting tasks"; 53 mails need an answer) | IN | D2 — `mail` items are store items (6 open today) and route by addressee |
| I9 | duplicated awaiting-operator items (3 copies of one question) | IN | D2 step 1 |
| I10 | every repo, not only the hub (D-471: "in each repo the agent which is not on worktree must be merge owner and coordinator") | IN | D0 roster; D7 template sentence; Lifecycle adoption; V5 one-window repos |
