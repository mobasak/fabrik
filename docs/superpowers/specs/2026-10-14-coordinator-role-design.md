# The coordinator — one agent per repo that sorts, prioritises, merges and keeps the records, and never builds

Status: DRAFT
Size: large (a role across every repo; work-store fields; a main-checkout handover in the multi-window repos)
Owner: infra (author) · the coordinator role, once it exists, owns the operation · Intake: operator conversation 2026-10-14 (infra window) · W-33126da2, W-8733139e
Decided by: the operator, in conversation (brainstorming, architectural path): *"ok we we agree on this, please do not drift. approved"* — this approves the design below for writing; the written spec still owes its own review and the operator's approval before any plan.

## Personas

- **PRIMARY — the operator**, in their own words: *"i want an agent its task is to sort mails, assign priority and do merge ownership and coordination only. not building anything as like you do for each repo or anymore task you might suggest in this manner"*; *"also priority must be set into each work items as we have limited source. we dont have unlimited claude max subscriptions"*; *"research and brainstorm skill first, it will be used in all repos not only in fabrik."*; *"i think it should also maintain uptodate and correctness of work ledgers, strategic backlog and plans.md and plans files and spec files"*.
- **The coordinator** — the one agent in a repo's main checkout. Sorts, scores, assigns, merges, keeps the records. Never builds.
- **The builders** — every other agent window of the repo (in the hub: infra, fleet, intel, kaizen), each in its own worktree. Build, review, write specs and plans; take one assignment at a time from the coordinator.
- **A single-window repo's agent** — the only agent of a repo with one window. Builds AND coordinates (no split), under the same priority rules.
- **The Opus + Fable panel** — answers the priority calls the coordinator cannot make (D-558), and design questions.

## Goal

Spend the fleet's limited Claude Max quota on the highest-value work first, and stop the agents who build from being interrupted by sorting, merging and bookkeeping — in every repo, not only the hub.

## Why this exists

Measured 2026-10-14:
- **Priority carries no information.** The hub's work store holds 535 open items; 442 (83%) sit at `priority: 2`, which is `DEFAULT_PRIORITY` (`scripts/work.py:84`); 89 at 3, 4 at 1. 272 are owned by infra, 203 by nobody. "Next item" therefore means "oldest item".
- **Mail is mostly overhead.** The hub's mailbox took 2,192 of the fleet's 6,629 mails in 30 days (52 mailboxes); 70% are hub agents writing to each other, ~34% are merge requests and their results, 835 replies.
- **The merge owner is also a builder.** D-471 (operator, 2026-10-01): *"in each repo the agent which is not on worktree must be merge owner and coordinator."* In practice that agent (infra in the hub) also builds: every build delays merges and every merge interrupts a build.

Prior art (all sources in `docs/reference/research/2026-10-14-coordinator-role-ledger.md`): separate interrupt handling from project work (Google SRE, tr-1..tr-3); dedicated triage roles set priority and owner on everything (Kubernetes, Rust; tr-4, tr-5); route with a cheap model, plan with a strong one (ma-2, ma-5, ma-10); a supervisor that rewords messages loses accuracy — forward verbatim (ma-6); multi-agent setups cost ~15× chat tokens, so keep the coordinator small (ma-1); schedule a constrained resource by value ÷ size (WSJF/CD3, pr-5..pr-8); limit work in progress (wip-1..wip-5); a merge steward tests the merged result and hands failures back, never fixes them (mq-1..mq-6).

## What exists today (grounded)

- Mail: `scripts/mail.py` `claim` (`:3011`), `route` (`:3033`), `ack`; one mailbox per repo under `/opt/fabrik-mail/`.
- Merges: `scripts/merge_request.py` `request` / `merge` (`:2105`) / `resume` — the merge-request loop (D-462, D-463, D-468).
- Work store: `scripts/work.py` — one JSON item per file under `.fabrik/work/`, fields `id, kind, title, status, owner, priority, links, next, note, tags, blocked_by, evidence, created, creator`; `assign` (`:2937`), `triage`, `sync` (`:3786`); `.fabrik/work/config.json` names the `distributor` (hub: `infra`), `autonomy` and `feedback_owner`.
- The records' own state: a spec's `Status:` line, a plan's ticket board, `docs/STRATEGIC_BACKLOG.md`, `docs/DECISIONS.md` (D-394: specs and plans are the record of their own state, never copied).
- Fleet layout (measured): 42 repos carry a work store; 10 run several agent windows in worktrees — fabrik, fabrik-lib, web-ecommerce-factory, tryton-crm, trade-intelligence, site-provisioner, whatsapp-agent, iterative_image_editor, seo, brand-identiy-creator; the rest run one agent.

## The delta

### D1 — Where the role runs (operator-approved option B)

- **Multi-window repos (the 10 above, and any repo that adopts worktrees later):** the main-checkout agent IS the coordinator and does only the coordinator's jobs (D3). Every other window builds.
- **Single-window repos:** the one agent keeps both roles — no split, because there is no second agent to build. It follows the same priority rules (D4) and the same one-major-project limit.
- **Never one fleet-wide coordinator:** each repo coordinates itself; the hub coordinator coordinates the hub only.
- **The hub:** the coordinator takes the main checkout and merge ownership; infra becomes a builder in a worktree like fleet, intel and kaizen. This narrows D-471 — the main-checkout agent is merge owner and coordinator *and does nothing else* in a multi-window repo.

### D2 — Model

The coordinator runs on Sonnet (routing and scoring are classification work). It calls a stronger model only through the Opus + Fable panel, for a priority call it cannot make.

### D3 — The seven jobs

1. **Sort mail.** Claim each mail; read only as much of the cited code as it needs to name the owner; route it to that agent **verbatim** (never reworded) and turn it into a work item; answer routing-only mail; ack pure FYIs. Never answers technical content, never fixes.
2. **Set priority on every work item** — new items on arrival, the backlog once (D5). Score per D4, place it in a quadrant, drop time sinks with a written reason (reopenable), re-score when new evidence arrives (not on a calendar), keep the top band narrow (force-rank when everything reads high).
3. **Assign.** One item per builder at a time — highest score first, dependencies first; hold **one major project at a time per repo** (blocked work counts against it); batch fill-ins into one session or send them to the cloud credit while it lasts (D-860); respect the quota band (AMBER: start nothing heavy; RED: assign nothing new).
4. **Own merges.** Merge builder branches only when the branch merged onto current main passes its tests; hand a failing or conflicting branch back to its author with the reason — never fix it; keep main green and pushed; run the fleet sync after a merge that touches synced files.
5. **Be the operator's single point of contact.** The only agent that boards decisions; batches them; relays the operator's answers back; relays cross-repo mail for its repo's agents, verbatim.
6. **Keep the books.** Commit work-store items; clear stale claims of dead sessions; once a day compare each closed item's score with its real cost (wall-clock and tokens from the run's close) — a scorer who keeps underrating effort becomes visible.
7. **Keep the records correct and current (status, never content).**

   | Record | Keeps correct | Never touches |
   |---|---|---|
   | Work store | priority, owner, status, links; closes items whose work landed; drops duplicates | — |
   | `docs/STRATEGIC_BACKLOG.md` | each row's status matches its work item; new findings land as rows | what a row's problem is |
   | Plans | the ticket board shows what actually merged; a finished plan is marked and archived; a stalled plan is flagged and a dead session's lock released | steps, design, acceptance criteria |
   | Specs | `Status:` matches reality (DRAFT → under review → CONVERGED → approved → built); a DRAFT with no review past a threshold is flagged | requirements and design text |
   | `docs/DECISIONS.md` | every operator ruling recorded; a superseded row points at its replacement | a past row (rows are immutable) |
   | INDEX / CHANGELOG | an entry exists for what merged | — |

   A record whose CONTENT is wrong (a plan citing a deleted file, a spec contradicting the build) becomes a scored work item for its owner, with the evidence; the fix goes through that owner's review.

**Never:** write or edit code, docs, specs, plans or rules beyond the status fields of job 7; review, test or reproduce a bug (it routes "is this real?" to a builder); reword another agent's message; decide a design question (the panel or the operator does).

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
- **Effort is the quota it will spend**, not hours: low = about an hour with the scoped review; high = the full review, a spec, or a fleet-synced surface. (Using quota as the effort unit is our own inference — no published source covers it; research ledger pr-18.)
- **Priority is derived, never typed:**

  | Quadrant | impact | effort | priority | rule |
  |---|---|---|---|---|
  | Quick win | high | low | P1 | next |
  | Major project | high | high | P2 | one in flight per repo; the rest wait at P3 |
  | Fill-in | low | low | P3 | batched (one session, or the cloud credit) |
  | Time sink | low | high | dropped | closed with a reason; reopenable when the impact changes |

- Order within a band: dependencies first, then age.
- **Cobra (D-253):** the cheapest way to look prioritised is to label everything a quick win. Counters: the high band is kept narrow (force-rank); every score carries its reason; job 6 compares each estimate with the real cost at close.

### D5 — The first job: re-score the backlog

The hub's 535 open items (and each repo's own store) are scored once under D4 — the coordinator's first assignment, expected to close a large share as time sinks or duplicates. A dropped item keeps its reason and can be reopened.

### D6 — Mail noise

- A merge result becomes a status on the work item, not a mail.
- An ack-only reply becomes the `ack` itself, not a new mail.
- Hub-agent-to-hub-agent talk moves to live messaging or the work store; mail stays for cross-repo traffic.

## Contract deltas

- Work item: two new fields `impact`, `effort` (+ the reason); `priority` becomes derived from them.
- D-471 narrowed (a new D-row supersedes it in part): in a multi-window repo the main-checkout agent coordinates and does nothing else.
- The hub's `.fabrik/work/config.json` `distributor` moves from `infra` to the coordinator.
- The project-facing `templates/governance/CLAUDE.md` gains the role (fleet-wide); fabrik-lib's hand-kept CLAUDE.md by mail.

## Decisions taken

- Option B (multi-window repos split; single-window repos keep one agent) — operator, 2026-10-14.
- The seven jobs, including job 7 (status, never content) — operator, 2026-10-14.
- Sonnet for the coordinator, the panel for hard calls — from the research.
- Impact × effort with derived priority; effort measured in quota.

## Rejected alternatives

- **A — a coordinator window in every repo:** doubles sessions in the ~32 single-window repos; costs quota instead of saving it.
- **C — one fleet-wide coordinator:** one session would need to read 48 repos' code to route well; one queue for the fleet becomes the bottleneck (ma-1, ma-6).
- **The coordinator fixes stale content itself:** that makes it a builder, unreviewed (job 7's line).
- **RICE / ICE as the score:** a confidence factor tracks enthusiasm, not evidence (pr-11); the four-quadrant view with a derived priority is what the operator asked for.

## Open unknowns

- The re-score of 535 items — how long it takes on Sonnet, measured on the first 50.
- The threshold for flagging a stale DRAFT spec and a stalled plan.
- Whether the three mail-noise changes (D6) cut volume by about half — an estimate, measured in the first week.

## Intake Inventory

| # | Operator ask (verbatim) | Where it lands |
|---|---|---|
| 1 | "sort mails" | D3 job 1 |
| 2 | "assign priority" / "priority must be set into each work items as we have limited source" | D3 job 2, D4, D5 |
| 3 | "do merge ownership" | D3 job 4 |
| 4 | "coordination only. not building anything" | D3 jobs 3, 5 and **Never** |
| 5 | Impact vs Effort framework | D4 |
| 6 | "it will be used in all repos not only in fabrik" | D1 |
| 7 | "maintain uptodate and correctness of work ledgers, strategic backlog and plans.md and plans files and spec files" | D3 job 7 |
| 8 | "please do not drift" | this spec carries only what was agreed; nothing is added |
