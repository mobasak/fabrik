# The coordinator — one agent per repo that sorts, prioritises, merges and keeps the records, and never builds

Status: CONVERGED — approved D-868
Size: large (a role across every repo; work-store fields; a main-checkout handover in the multi-window repos)
Owner: infra (author) · the coordinator role, once it exists, owns the operation · Intake: operator conversation 2026-10-14 (infra window) · W-33126da2, W-8733139e
Decided by: the operator, in conversation (brainstorming, architectural path): *"ok we we agree on this, please do not drift. approved"* — this approves the design below for writing; the written spec still owes its review and the design-approval gate before any plan.

## Personas

- **PRIMARY — the operator**, in their own words: *"i want an agent its task is to sort mails, assign priority and do merge ownership and coordination only. not building anything as like you do for each repo or anymore task you might suggest in this manner"*; *"also priority must be set into each work items as we have limited source. we dont have unlimited claude max subscriptions"*; *"research and brainstorm skill first, it will be used in all repos not only in fabrik."*; *"i think it should also maintain uptodate and correctness of work ledgers, strategic backlog and plans.md and plans files and spec files"*.
- **The coordinator** — the one agent in a repo's main checkout. Sorts, scores, assigns, merges, keeps the records. Never builds.
- **The builders** — every other agent window of the repo (in the hub: infra, fleet, intel, kaizen), each in its own worktree. Build, review, write specs and plans; take one assignment at a time from the coordinator.
- **A single-window repo's agent** — the only agent of a repo with one window. Builds AND coordinates (no split), under the same priority rules.
- **The Opus + Fable panel** — answers the priority calls the coordinator cannot make (D-558), and design questions.

## Goal

Spend the fleet's limited Claude Max quota on the highest-value work first, and stop the agents who build from being interrupted by sorting, merging and bookkeeping — in every repo, not only the hub.

## Why this exists

Measured by the author 2026-10-14 (the hub's store and the fleet mail store; D-863 records the same figures, except its "10 multi-window repos", corrected to 9 below):
- **Priority carries no information.** The hub's work store holds 535 open items; 442 (83%) sit at `priority: 2`, which is `DEFAULT_PRIORITY` (`scripts/work.py:84`); 89 at 3, 4 at 1. 272 are owned by infra, 203 by nobody. "Next item" therefore means "oldest item".
- **The hub carries a third of the fleet's mail.** 2,192 of the fleet's 6,629 mails in 30 days (52 mailboxes, by file mtime) landed in the hub's mailbox.
- **Mail is mostly overhead** — from the operator's own pasted analysis of the hub mailbox (not re-measured here): 70% hub agents writing to each other, ~34% merge requests and their results, 835 replies.
- **The merge owner is also a builder.** D-471 (operator, 2026-10-01): *"in each repo the agent which is not on worktree must be merge owner and coordinator."* In practice that agent (infra in the hub) also builds: every build delays merges and every merge interrupts a build.

Prior art (all sources in `docs/reference/research/2026-10-14-coordinator-role-ledger.md`): separate interrupt handling from project work (Google SRE, tr-1..tr-3); dedicated triage roles set priority and owner on everything (Kubernetes, Rust; tr-4, tr-5); route with a cheap model, plan with a strong one (ma-2, ma-5, ma-10); a supervisor that rewords messages loses accuracy — forward verbatim (ma-6); multi-agent setups cost ~15× chat tokens, so keep the coordinator small (ma-1); schedule a constrained resource by value ÷ size (WSJF/CD3, pr-5..pr-8); limit work in progress (wip-1, wip-2, wip-4, wip-5); a merge steward tests the merged result and hands failures back, never fixes them (mq-1..mq-6).

## What exists today (grounded)

- Mail: `scripts/mail.py` `claim` (`:3011`), `route` (`:3033`), `ack`; one mailbox per repo under `/opt/fabrik-mail/`.
- Merges: `scripts/merge_request.py` `request` / `merge` (`:2105`) / `resume` — the merge-request loop (D-462, D-463, D-468). The merge owner is resolved from the newest `MERGE OWNER:` row in `docs/DECISIONS.md` (`decisions.py --merge-owner`, called at `merge_request.py:297-311`; hub today: D-453, `infra`); a non-owner's `merge` is refused (`:1927-1931`). The request, its copy and its result travel as mail (D-462).
- Work store: `scripts/work.py` — one JSON item per file under `.fabrik/work/`, fields `id, kind, title, status, owner, priority, links, next, note, tags, blocked_by, evidence, created, creator`; `priority` an integer 0 (urgent) to 3 (someday), default 2 (`_priority_arg`, `:4474-4481`), typed by `add --priority` and `assign --priority`, read by every ordering (`_priority`, the ready list, the backlog render, the Stop hook's owned-item rung); `assign` (`:2937`), `triage`, `sync` (`:3786`), `drop --why` (owner or distributor; a dropped item refuses every later verb — there is no reopen); `.fabrik/work/config.json` names the `distributor` (hub: `infra`), `autonomy` and `feedback_owner`.
- The records' own state: a spec's `Status:` line (values in use include DRAFT, CONVERGED, EXECUTED, IMPLEMENTED, SUPERSEDED, BLOCKED; an approval is a D-row cited on the line, e.g. `CONVERGED — approved D-463`); a plan's ticket board and lock, the executing orchestrator's write surface (`scripts/enforcement/check_plan_tickets.py:27-28`) — freeing a dead run's lock is an operator action (`scripts/enforcement/check_plan_lock_release.py:130-131`); `docs/STRATEGIC_BACKLOG.md` and `PLANS.md`, both RENDERED (`work.py render`, `docs_updater.py --sync`); `docs/DECISIONS.md`; each agent writes its own CHANGELOG/DECISIONS/BACKLOG rows on its own branch (D-448). D-394: specs and plans are the record of their own state, never copied.
- Fleet layout (measured with `work.py::_workers`, which counts named worktrees under `.claude/worktrees/` and ignores subagent harness trees): 9 repos run several agent windows — fabrik, fabrik-lib, web-ecommerce-factory, tryton-crm, trade-intelligence, site-provisioner, whatsapp-agent, iterative_image_editor, brand-identiy-creator. 42 repos carry a work store; fabrik-lib does not (it is multi-window without one).

## The delta

### D1 — Where the role runs (operator-approved option B)

- **Multi-window repos** — a repo where `work.py::_workers` is non-empty (the 9 above today; any repo that registers a named worktree later): the main-checkout agent IS the coordinator and does only the coordinator's jobs (D3). Every other window builds.
- **Single-window repos:** the one agent keeps both roles — no split, because there is no second agent to build. It follows the same priority rules (D4) and the same one-major-project limit.
- **A multi-window repo with no work store** (fabrik-lib today): the store-based jobs (2, 3, 6 and job 7's store row) wait until the repo has a store; jobs 1, 4 and 5 run as today.
- **Never one fleet-wide coordinator:** each repo coordinates itself; the hub coordinator coordinates the hub only.
- **The hub:** the coordinator takes the main checkout and merge ownership; infra becomes a builder in a named worktree (`.claude/worktrees/infra`) like fleet, intel and kaizen. This narrows D-471 — in a multi-window repo the main-checkout agent is merge owner and coordinator *and does nothing else*.

### D2 — Model

The coordinator runs on Sonnet (routing and scoring are classification work). It calls a stronger model only through the Opus + Fable panel, for a priority call it cannot make.

### D3 — The seven jobs

1. **Sort mail.** Claim each mail; read only as much of the cited code as it needs to name the owner; route it to that agent **verbatim** (never reworded) and turn it into a work item; answer routing-only mail; ack pure FYIs. Never answers technical content, never fixes.
2. **Set priority on every work item** — new items on arrival, the backlog once (D5). Score per D4, place it in a quadrant, drop time sinks with a written reason, re-score when new evidence arrives (not on a calendar), keep the top band narrow (force-rank when everything reads high).
3. **Assign.** One item per builder at a time — the store's `queue_floor` is 1 in a multi-window repo, and a builder claims what the coordinator queued it rather than self-serving from `work.py ready` (Contract deltas); highest score first, dependencies first. Hold **one major project in flight per repo**: in flight = a major-project item (impact high, effort high) with an owner and status `open` or `blocked` (a blocked one still counts); every other major project keeps its P2 and carries `blocked_by: <the in-flight id>`, so `ready` never offers it; batch fill-ins into one session or send them to the cloud credit while it lasts (D-860); respect the quota band (AMBER: start nothing heavy; RED: assign nothing new).
4. **Own merges.** Merge builder branches only when the branch merged onto current main passes its tests; hand a failing or conflicting branch back to its author with the reason — never fix it; keep main green and pushed; run the fleet sync after a merge that touches synced files, and render the command corpus at merge (a main-checkout-only act). Shared-runtime acts (a migration, a reload, an app or worker restart — `templates/governance/CLAUDE.md` § Orient (d)) stay sequenced by the merge owner one at a time, as today: the coordinator grants each turn; the builder whose ticket owns the act runs it, so the coordinator still builds nothing.
5. **Be the operator's single point of contact.** The only agent that boards decisions; batches them; relays the operator's answers back; relays cross-repo mail for its repo's agents, verbatim.
6. **Keep the books.** Commit work-store items; clear stale claims of dead sessions; once a day compare each closed item's score with its real cost — the join from a closed item to its run's wall-clock and tokens does not exist today (§ Open unknowns), so this comparison starts when it does.
7. **Keep the records correct and current (status, never content).**

   | Record | Keeps correct | Never touches |
   |---|---|---|
   | Work store | priority, owner, status, links; closes items whose work landed; drops duplicates | — |
   | `docs/STRATEGIC_BACKLOG.md`, `PLANS.md` | re-renders them (`work.py render`, `docs_updater.py --sync`) so they match the store and the plans; new findings enter as `work.py add --kind backlog` | the rendered block by hand |
   | Plans | marks a FINISHED plan (no live run, every ticket merged) done and archives it — a status edit; flags a live run's ticket board or lock that contradicts what merged to the plan's `Owner:` (and to the operator when the owning run looks dead) | a live run's board or lock (the orchestrator's; freeing a dead lock is the operator's — § Decisions taken); steps, design, acceptance criteria |
   | Specs | keeps each `Status:` value current; a new transition uses the values in use — DRAFT, CONVERGED (approval cited as `— approved D-NNN`), EXECUTED, IMPLEMENTED, SUPERSEDED, BLOCKED; flags a DRAFT with no review past a threshold (§ Open unknowns) | requirements and design text |
   | `docs/DECISIONS.md` | records each operator ruling it receives as the operator's single contact (job 5); a changed decision is a new row citing `supersedes D-NNN` (`decisions.py --check` resolves it) | a past row (rows are immutable) |
   | INDEX / CHANGELOG | checks that the author's entry exists for what merged (the author's gate errors on a missing CHANGELOG entry for a code change and only warns on INDEX; neither check runs at merge); a merged change with no entry becomes a work item for its author | the author's entry itself (D-448) |

   A record whose CONTENT is wrong (a plan citing a deleted file, a spec contradicting the build) becomes a scored work item for its owner, with the evidence; the fix goes through that owner's review.

**Never:** write or edit code, docs, specs, plans or rules, except the status edits and the appends job 7 names — a spec's `Status:` line, a finished plan's status and archive move, the rendered backlog and plan views, the D-rows for rulings the coordinator receives, and work items; review, test or reproduce a bug (it routes "is this real?" to a builder); reword another agent's message; decide a design question (the panel or the operator does).

**Escalation:**

| Situation | Goes to |
|---|---|
| A score is a coin-flip on a high-effort item | the Opus + Fable panel |
| A merge conflict between two builders' work | back to both authors; the later one rebases |
| An item needs a design before it can be scored | a builder writes the spec; the coordinator then scores it |
| A gate — deploy, destructive, spend, credentials | the operator, through the board |

### D4 — Priority: impact × effort under the quota budget

- Two fields on every work item, set at triage: `impact` (`high` | `low`, with a one-line reason) and `effort` (`high` | `low`).
- **Impact is high** when the item unblocks a project, protects production or data, or stops a recurring fleet-wide defect; otherwise low.
- **Effort is the quota it will spend**, not hours: low = the work closes with one `/fabrik-review-scoped`; high = it owes a full `/fabrik-review`, a spec chain, or a fleet-synced surface (the sync fan-out). (Using quota as the effort unit is our own inference — no published source covers it; research ledger pr-18.)
- **Priority is derived from the two fields**, written by the coordinator into the existing integer `priority`, so every reader of it keeps working:

  | Quadrant | impact | effort | priority | rule |
  |---|---|---|---|---|
  | Quick win | high | low | 1 | next |
  | Major project | high | high | 2 | one in flight per repo (job 3); the rest keep 2 and wait |
  | Fill-in | low | low | 3 | batched (one session, or the cloud credit) |
  | Time sink | low | high | — | status `dropped` (`work.py drop --why`); revived only as a new item whose text names the dropped id |

- **An unscored item** (no `impact`/`effort`) still carries the default P2 and so ranks with the major projects until it is scored; the guard is job 2's scoring on arrival, made executable by `work.py triage` listing every open item that lacks the two fields — D5 ends with that list empty.
- Priority 0 (urgent) stays what it is today: an override for production or data incidents; it bypasses the quadrants.
- Order within a band: dependencies first, then age.
- **Cobra (D-253):** the cheapest way to look prioritised is to label everything a quick win; the cheapest way to shrink the backlog is to label everything a time sink. Counters: the high band is kept narrow (force-rank); every score and every drop carries its reason; job 6's estimate-versus-cost comparison once its join exists. **Job 6's own cobra:** clearing "stale" claims that are live — counter: only a claim whose session is not live (the existing test) is cleared.

### D5 — The first job: re-score the backlog

The hub's 535 open items (and each repo's own store) are scored once under D4 — the coordinator's first assignment, expected to close a large share as time sinks or duplicates, each drop with its reason.

## Contract deltas

- **Work item:** two new fields `impact`, `effort` (+ the reason); `priority` stays the stored integer, written by the coordinator from D4's table; `add --priority` / `assign --priority` stay as today (the 0-override, and single-window repos' self-scoring). `work.py triage` lists the open items that lack the two fields (D4).
- **Assignment (job 3):** `.fabrik/work/config.json` `queue_floor: 1` in every multi-window repo's store (`QUEUE_FLOOR`, `scripts/work.py:4499`, stays 3 for single-window repos); a new D-row supersedes D-442's self-service ("an idle agent runs `work.py ready`, claims what it will do") in part — in a multi-window repo a builder claims what the coordinator queued it; `docs/reference/multi-agent-operating-model.md` § Claim or assign rewritten with it.
- **D-471 narrowed:** a new D-row supersedes it in part — in a multi-window repo the main-checkout agent coordinates and does nothing else.
- **The hub beat lists** — `coordinator` is added, BEFORE the merge-owner row below lands (otherwise every hub merge request is refused: `merge_request.py:353` sends `--to-agent <owner>` and `mail.py` refuses a name outside `HUB_BEATS`): `scripts/mail.py::HUB_BEATS` (`:548`; refusal `:1429-1433`, `route --to-agent` on the hub mailbox, its help text), `.claude/hooks/mail_notify.py::_HUB_BEATS` (`:100`, pinned equal by `tests/test_mail_notify.py`), `scripts/command_run.py::_BEATS` (`:2086`), `scripts/sysadmin/quota_dashboard.py::_HUB_OWNERS` / `_HUB_AGENTS` (`:2245`, `:2248`), and `CLAUDE.md`'s trailer table ("hub sessions keep the four role names").
- **The hub's merge owner:** a new row `supersedes D-453: MERGE OWNER: coordinator` (the name `merge_request.py` resolves), and `.fabrik/work/config.json` `distributor: coordinator` changed with it.
- **The hub coordinator's identity:** agent name `coordinator` (`CLAUDE_AGENT=coordinator`), a charter at `docs/reference/agents/coordinator.md`, launched in the main checkout; infra relaunched in `.claude/worktrees/infra`.
- **Mirrors that name infra as agent-1 / the merge owner / the main-checkout writer**, each rewritten: `CLAUDE.md` § Shared repo and § EXIT (main-checkout writers, "infra (the merge owner)"), `CLAUDE.md` § Autonomy (the Stop hook's coordinator cause, "for the distributor the command-feedback queues"), `docs/reference/agents/infra.md` (merge owner and distributor), `docs/reference/multi-agent-operating-model.md` § Ownership surfaces and § Hub vs project, and `templates/governance/CLAUDE.md`'s D-471 sentence (fleet-wide, adds "and does nothing else in a multi-window repo"); fabrik-lib's hand-kept CLAUDE.md by mail.
- **The fleet carrier for D3 and D4:** every project reads the seven jobs and the priority table from `templates/governance/CLAUDE.md` (fleet-synced, `scripts/fabrik_synced_manifest.py`) — a short section beside the D-471 sentence, so the 8 other multi-window repos and every single-window repo apply the same rules; the hub charter `docs/reference/agents/coordinator.md` points to it, never restates it.

## Decisions taken

- Option B (multi-window repos split; single-window repos keep one agent) — operator, 2026-10-14.
- The seven jobs, including job 7 (status, never content) — operator, 2026-10-14.
- Sonnet for the coordinator, the panel for hard calls — the author's choice from the research (ma-2, ma-5); approved at the design-approval gate (D-868).
- Impact × effort with derived priority, effort measured in quota — the operator's framework (Impact vs Effort); the quota unit is the author's inference (pr-18), approved at the design-approval gate (D-868).
- The coordinator's name `coordinator` — the author's choice, approved at the design-approval gate (D-868).
- **Plans, narrowed from the approved wording** ("the ticket board shows what was actually merged; a finished plan is marked done and archived; a stalled plan is flagged and its lock released when its session is dead"): the finished-plan mark and archive stay the coordinator's; a LIVE run's board stays the executing orchestrator's write surface (`scripts/enforcement/check_plan_tickets.py:27-28`), and freeing a dead run's lock stays an operator act (`scripts/enforcement/check_plan_lock_release.py:130-131`), so the coordinator flags those two instead of writing them. Changing either rule is a separate decision, not this spec's.
- Shared-runtime acts keep today's rule (sequenced by the merge owner, run by the owning ticket) — job 4.

## Rejected alternatives

- **A — a coordinator window in every repo:** doubles sessions in the 34 single-window repos with a store (42 stores less the 8 multi-window repos that carry one); costs quota instead of saving it.
- **C — one fleet-wide coordinator:** one session would need to read 42 repos' code to route well; one queue for the fleet becomes the bottleneck (ma-1, ma-6).
- **The coordinator fixes stale content itself:** that makes it a builder, unreviewed (job 7's line).
- **RICE / ICE as the score:** a confidence factor tracks enthusiasm, not evidence (pr-11), and RICE's graded impact scale and effort-divides formula (pr-1, pr-2) are finer than the operator's two-by-two; the four-quadrant view with a derived priority is what the operator asked for.

## Open unknowns

- The re-score of 535 items — how long it takes on Sonnet, measured on the first 50.
- The threshold for flagging a stale DRAFT spec and a stalled plan.
- **D5's drops are irreversible** (a dropped item refuses every later verb; revival is a new item naming the dropped id): a wrong mass drop by a Sonnet coordinator would be costly to undo. Whether the first re-score's drop list needs a batch check (the panel, or the operator) before `drop --why` runs is decided at planning, measured on the first 50.
- The join from a closed work item to its run's wall-clock and tokens (job 6, D4's third counter): today a run's usage row carries no work-item id and `work.py done` records no cost.

### Recorded, not applied (scope requests from the review — backlog, not this spec)

- A work-item id on the `command_run.py` usage row (or a cost on `work.py done`), so job 6 can join cost to item.
- A `work.py reopen` verb, if reviving a dropped item as a new item that names the dropped id proves too clumsy.
- **Mail noise** — not in the approved design (the panel review found it added): a merged result becoming a work-item status instead of a mail (a `merge_request.py` change superseding D-462 in part), ack-only replies becoming the `ack` itself, and hub-agent-to-hub-agent talk moving to live messaging (already `CLAUDE.md`'s rule for intra-repo chatter). A candidate for its own decision once the coordinator runs.

## Intake Inventory

| # | Operator ask (verbatim) | Where it lands |
|---|---|---|
| 1 | "sort mails" | D3 job 1 |
| 2 | "assign priority" / "priority must be set into each work items as we have limited source" | D3 job 2, D4, D5 |
| 3 | "do merge ownership" | D3 job 4 |
| 4 | "coordination only. not building anything" | D3 jobs 3, 5 and **Never** |
| 5 | Impact vs Effort framework | D4 |
| 5b | "research and brainstorm skill first" | the prior-art research ledger `docs/reference/research/2026-10-14-coordinator-role-ledger.md` (45 rows) and the brainstorming session this spec records |
| 6 | "it will be used in all repos not only in fabrik" | D1 |
| 7 | "maintain uptodate and correctness of work ledgers, strategic backlog and plans.md and plans files and spec files" | D3 job 7 |
| 8 | "please do not drift" | this spec carries only what was agreed; review findings that asked for new scope are recorded, not applied |
