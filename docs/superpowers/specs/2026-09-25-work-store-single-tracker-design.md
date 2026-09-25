# Design — the work store as the one place every open obligation shows up

Status: DRAFT
Profile: delta — every Intake item maps to code that exists today (`scripts/work.py`, `scripts/thread_anchor.py`, `scripts/mail.py`, `scripts/command_feedback_report.py`); this spec changes how they meet, and adds no new component.
Owner: infra
Parent: `docs/superpowers/specs/2026-09-24-work-tracking-design.md` (CONVERGED, D-394; built by plan `archived/2026-09-24-plan-2-work-tracking`, EXECUTED 02744deea)
Surface: `scripts/work.py`, `scripts/thread_anchor.py`, `scripts/mail.py`, `scripts/command_feedback_report.py`, both CLAUDE.md contracts, `docs/reference/work-tracking.md` — all fleet-synced or governance paths (rule 1: the full chain)

## Personas

- **The operator (primary).** In their words: *"we have specs, plans, we have stragetic_backlog. while agents are working all must be synced and maintained and updated properly, in each repo 3 different agent is working. one agent is managing the distribution of tasks and responsibilities. next is good feature. so we need our own tracking system."* And on 2026-09-25, after two agents' NEXT lines pointed at two different places: *"are you sure you have implemented a good tracking system ?"* They want ONE place that shows every open obligation and who is on it, without asking any agent.
- **The distributor agent** (intel on the hub, D-395): assigns owners; sees unowned and stale work.
- **The worker agents** (up to three sessions per repo): take work, do it, close it.
- **Automated consumers** — each duty's holder named:
  - the Stop hook's harvest (`thread_anchor.py harvest`, called from `.claude/hooks/final_gate_stop.py`) — turns a NEXT line into a claim or a thread item (§ The delta, D3);
  - the prompt hook (`thread_anchor.py line --hook`) — shows the session its view (D1, D4, D6);
  - `mail.py claim` / `mail.py ack` — create and close a mail item (D2);
  - `command_feedback_report.py --mark-answered`, run by `/fabrik-command-improve` — closes a feedback item (D2);
  - the completion gate's `Work items (sync)` row — unchanged;
  - fleet repos' agents — receive all of it through the governance sync.

**Step budgets (frozen).**
- Operator: open any session → the prompt shows every awaiting question, the counts of mail and feedback queues needing an answer, and who is on what (1).
- Worker, on store work: the prompt shows its claimed and owned items (1) → work, ending the turn with `NEXT: <item id>` — which claims it (2) → `done --evidence <sha>` (3).
- Worker, on mail: `mail.py claim <id>` — the mail item is created and claimed (1) → work → `mail.py ack <id>` — the item closes (2).
- Distributor: `work.py status` shows unowned, stale and unclaimed work (1) → `assign` (2).

Every item of § The delta traces to one of these; none is untraceable.

## Goal

After adoption, a reader who opens any session in a repo sees, in one block, every open obligation of that repo — store items, awaiting operator questions, mail that needs an answer, and command feedback queues — and which session is working on what. No obligation lives only in a place that block does not show.

## Why this exists

The parent spec built the store and fed it the backlog and DECISION blocks. Measured on 2026-09-25, one day after adoption:
- **Open work still lives in five places.** The store (319 open items); fabrik-mail (3,135 unread across 50 mailboxes, of which **158** are `ack: required` obligations and the rest information); per-command feedback queues (455 ledger rows; `/fabrik-execute-plan` alone holds 36 unanswered); per-session thread anchors; run records and plan boards.
- **Nobody records what they are on.** 0 live claims across 319 open items.
- **NEXT points anywhere.** Across the fleet's last 7 days (47 sessions): 14,724 `NEXT:` lines — 12,395 free text, 1,786 operator decision, 530 `none`, **4** naming an item. Fleet's NEXT on 2026-09-25 read *"… (it's queued in that command's feedback queue, not in the work store)"*.
- **`ready` is a swamp.** It lists 317 items, most of them old backlog.
- **Owners do not resolve.** No hub window is named (`CLAUDE_AGENT` unset), so `--mine` finds nothing.

How this design removes each: one view reads the other sources live (D1); taking an obligation creates its item and claim (D2); a NEXT line either claims the item it names or updates one thread item (D3); `ready` defaults to what is yours (D4); a duplicate question can be retired (D5); an unnamed window is told so on every prompt (D6).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"we need our own tracking system"* (2026-09-24, the parent's I1) | IN — this spec completes it | § Goal |
| I2 | *"this is the type of mess and work tracking i am trying to resolve now make this tidy asap"* | IN | § Why this exists; the tidy itself was done in chat (5 stale anchors closed, W-e0e161b4 closed as a duplicate, commit 12f658d32) |
| I3 | *"are you sure you have implemented a good tracking system ?"* with intel's and fleet's NEXT lines | IN | § Why this exists (the five places); D1, D3 |
| I4 | *"yes it must of course"* — approving option A, the single tracker via the full chain (item W-f8a26582) | IN | the whole spec; its D-row is minted with this spec's commit |
| I5 | Gap 1: work lives in ≥ 5 places | IN | D1, D2 |
| I6 | Gap 2: 0 live claims | IN | D2, D3 |
| I7 | Gap 3: NEXT is free text | IN | D3 |
| I8 | Gap 4: windows unnamed | IN (visibility); naming itself stays the operator's action | D6 |
| I9 | No verb retires a duplicate awaiting question (W-4025bfea) | IN | D5 |
| I10 | Thread anchors duplicate what items hold | IN | D3 |
| I11 | *"send mails to fleet and intel so they can work their items. we have a lot to cover."* | OUT-OF-SCOPE — done in chat, not a design item | mails 01M3C572CA1N6XJV0PV6CH7J1J (fleet) and 01M3C572JPBTV22MBS439Y61VG (intel), 2026-09-25 |
| I12 | The loop program's next measurement | OUT-OF-SCOPE — separate work | item W-992909ca |
| I13 | The git-decoder spec's design approval | OUT-OF-SCOPE — a separate question for the operator | item W-f9e2e6ec |
| I14 | The 45 synced repos have not adopted the store yet | OUT-OF-SCOPE — tracked | item W-59c5ab33 |
| I15 | fabrik-lib is sync-excluded and has no `work.py` | OUT-OF-SCOPE — its adoption is the operator's call with fabrik-lib | told to the three live fabrik-lib sessions, 2026-09-25 |

Intake: 15 items — 10 IN, 5 OUT-OF-SCOPE (each named above), 0 ASK.

## What exists today (grounded)

- The store and its verbs: `scripts/work.py` — `KINDS = ("backlog", "decision", "next", "task")` at `:76` (a `next` kind already exists and nothing creates it), `cmd_ready` at `:2503`, `cmd_claim` at `:2623`, `cmd_drop` at `:2690` (refuses awaiting items), `cmd_status` at `:2749`, `_set_next` at `:2990` (a NEXT naming an item updates its `next` field, capped at 300 characters), `on_harvest` at `:3005`, `prompt_block` at `:3067`.
- Thread anchors: `scripts/thread_anchor.py` — `_anchor_key` at `:430`, `_same_thread` at `:456`, `_is_anchor` at `:465`, `cmd_harvest` at `:535`, `cmd_line` at `:762` (prints OPEN THREADS from the per-session state file).
- Mail: `scripts/mail.py` — `claim` at `:1006` (the atomic inbox→archive rename), `ack` at `:1088`, `list_msgs` at `:1484`. A message header carries `kind:`, `ack:` and an optional addressee role.
- Feedback queues: `scripts/command_feedback_report.py --queue <command>` prints one command's unanswered verdict rows; `mark_answered` at `:327` records an applied edit against them.
- Measured cost of the new read: all 95 inbox headers of the largest mailbox read in 2.3 ms; the hub's 58 in 0.7 ms (2026-09-25).

## The delta

### D1. One view — read live, never copied

`work.py` gains one reader, `obligations(repo, agent)`, returning at most one line per source:
- **Mail:** the count of unread `ack: required` messages in this repo's inbox (`$FABRIK_MAIL_ROOT` or `/opt/fabrik-mail`, `<repo name>/inbox/`) addressed to this agent or to nobody, with the oldest one's age — `mail: 3 need an answer (oldest 4 d) — python3 scripts/mail.py list`. `ack: no` mail is information and is not counted.
- **Feedback queues:** only where the repo holds the command corpus (the hub), and only for the corpus owner's beat (infra): the unanswered depth per command, largest first, top three — `feedback queues: fabrik-execute-plan 36 · fabrik-review 12 · … — /fabrik-command-improve <command>`.
- **Awaiting questions and claims** are already in the prompt block (parent § NEXT, DECISION blocks and the register).

The reader only reads files, fails open (any error → no line), and is bounded by the file counts measured above. It is shown in three places: the head of `ready`, `status`, and the prompt block. Nothing is copied into the store at this stage — the sources stay the truth (the parent's principle, § Spec and plan state is derived, never copied).

### D2. Taking an obligation creates its item

- `mail.py claim <id>` (the handler's first act under the mailbox contract) creates a `kind: mail` item — title the subject, `links.mail` the message id — owned by the claimer's agent and claimed by that session, in the claimer's repo store. `mail.py ack <id>` closes it with the disposition as its note. A repo without a store: nothing is created, and mail works as today.
- `/fabrik-command-improve <command>` creates one `kind: feedback` item per command it takes (never one per row), and `command_feedback_report.py --mark-answered` closes it with the edit's commit as evidence.
- `KINDS` gains `mail` and `feedback`. Everything else about an item is the parent's.

### D3. A NEXT line is either a claim or a thread item

At the Stop harvest (`on_harvest`, already called with the turn's last NEXT):
- **A NEXT naming an item id** updates that item's `next` (as today) **and claims it for the session** (a new claim, or a renewal of its own). A claim held by another live session is not stolen; the NEXT still updates `next`.
- **A free-text NEXT that `_is_anchor` accepts** updates the session's open `kind: next` item on the same thread (`_same_thread`), or creates one, owned by the session's agent — the session id when the window is unnamed. One item per thread, never one per line.
- **`NEXT: none — terminal`, an operator decision, `BLOCKED:`, or a free-text NEXT `_is_anchor` refuses** create nothing (D-392: no gate, nothing forced).
- **Thread anchors retire into items.** In a repo with a store, OPEN THREADS is printed from the session's open `next` items; the per-session anchor file is kept only for store-less repos. `thread_anchor.py done --match` closes the matching `next` item.

Measured volume (fleet, last 7 days): 653 anchor-worthy NEXT lines grouping into **183 threads** — about 26 new `next` items a day fleet-wide, at most 80 in the busiest session. The literal alternative, an item per distinct free-text NEXT, would create **6,841** a week (§ Rejected alternatives).

### D4. `ready` shows what is yours

`work.py ready` defaults to: the D1 obligation lines; this session's claims; items owned by this agent; awaiting-operator items; then the top 10 others by priority. `ready --all` prints everything, as today. `next` is unchanged (the first of `ready --mine`). The field's lesson, quoted: *"The goal is keeping bd ready crisp and actionable."* (Ian Bull on Beads, fetched 2026-09-25).

### D5. A duplicate question can be retired

`work.py drop <id> --duplicate-of <keep>` is allowed on an `awaiting-operator` item when `<keep>` is an open awaiting item: `<id>`'s `msg_digests` merge into `<keep>`, so the Stop harvest's echo guard still recognises the old message, and `<id>` closes as `dropped` with the note `duplicate of <keep>`. Any agent may run it; the dropped item's git history shows who did.

### D6. An unnamed window is told so

When `_agent_name()` resolves nothing, the prompt block's first line reads: `work: this window has no agent name — owned items cannot reach it; run python3 scripts/whoami_agent.py --as <name>`. Naming stays the operator's action; its absence is now visible on every prompt.

### D7. The contract line

Both CLAUDE.md contracts' work-items paragraph gains one sentence: end a turn on work with `NEXT: <item id>`, which claims it; claiming a mail creates its item. No new gate (D-392).

## Contract deltas

None to `docs/data-contract.md` or `docs/ui-design.md` (the hub has neither). The item schema gains two `kind` values (D2); the CLI gains `drop --duplicate-of` (D5) and `ready --all` becomes the old default (D4).

## Rejected alternatives

- **Copy every obligation into the store** (a sync pass mirroring each `ack: required` mail and each feedback row as an item, and every distinct free-text NEXT as an item). Rejected 3–0 by the judge panel: two sources of truth that drift, against the parent's derived-never-copied rule, and **6,841** NEXT items a week plus 158 mails would bury `ready`.
- **Gate the Stop on a NEXT that names no item.** Rejected 3–0: it is the gate the operator refused (D-392 — *"agent will start making up unnecessary tasks in next field"*), and it leaves mail and queues where they are.
- **Move mail into the store.** Rejected: fabrik-mail is the cross-repo transport (`/opt/fabrik-mail`, repo-to-repo, with its own claim/ack lock); the store is per repo.
- **One feedback item per queue row.** Rejected: 455 rows; the unit of work is a command's queue, which `/fabrik-command-improve` takes whole.
- **Keep thread anchors beside `next` items.** Rejected: two records of the same thread, the drift class that left five 3–4-week-old anchors open until they were closed by hand on 2026-09-25.

## Lifecycle

- **Adoption.** Ships through the governance sync with the next `work.py` and `thread_anchor.py`; repos that have adopted the store start creating `next` and `mail` items at their next Stop and mail claim. Hub first, then the fleet on the existing rollout item (W-59c5ab33).
- **Growth.** Triggers, each measured from the store: more than 200 open `next` items in one repo (the dedup is too loose — tighten `_is_anchor`); the prompt block over 1 s (read the obligation sources less often); more than 50 open `mail` items older than 14 days in one repo (claims are being taken and not acked — the distributor's queue).
- **Degradation.** Every new reader fails open to "no line"; every new write happens where a write happens today (the Stop harvest, `mail.py claim/ack`, `--mark-answered`) and follows the parent's lock and budget rules. A repo without a store behaves exactly as today.
- **Retirement.** Items are files; removing the reader and the D2/D3 writes leaves them readable. The per-session anchor file is already the store-less fallback.

## External dependencies and practice (fetched 2026-09-25)

- **Beads** (Steve Yegge) — README, raw: https://raw.githubusercontent.com/gastownhall/beads/main/README.md (curl, 200, 2026-09-25); found through an exa search and a brave search the same day. Its agent contract: *"Use `bd ready`, `bd show <id>`, `bd update <id> --claim`, and `bd close <id>`."* — one queue, an explicit claim, a close. Its discovered-work link type is `discovered-from`.
- **Ian Bull, "Beads - Memory for your Agent"** — https://ianbull.com/posts/beads/ (curl, 200, 2026-09-25): *"Claude doesn’t proactively use it. You need to say “track this in beads” or “check bd ready.”"* and *"CLAUDE.md instructions fade."* — the reason D2 and D3 hang on existing hooks and verbs rather than on an instruction; and *"The goal is keeping bd ready crisp and actionable."* — the reason for D4.
- No external API is called; no vendor limit applies.

## fabrik-lib verdict

BUILD, inside existing hub scripts — no fabrik-lib module tracks work; the parent's verdict stands (not a fabrik-lib candidate: it is fleet governance tooling, not a product module).

## Shape / infra

None — no service, no `shape:` flag, no port. Box-local files only (`/opt/fabrik-mail` is read, never written, by `work.py`).

## Constraints

Digest (MUST-READ set computed 2026-09-25 by `review_rubric.py --changed` over the surface: FLOOR `core/10-python.md` + 12-FACTOR, MATCHED `core/40-documentation.md`) — carried from the parent's § Constraints unchanged: stdlib only for fleet-synced scripts; hooks fail open inside their budgets (Stop harvest 5 s kill, store lock ≤ 2 s from hooks, prompt store budget 3 s, and the prompt path takes the store lock only for the DECISION second chance — T04's A-O3); CLI verbs fail loud; no temporary workaround ships (FIX DIRECTIVE 3). D3's claim is written by the Stop harvest, which already holds the store lock for `on_harvest`, so A-O3 is untouched.

## Documentation landing sites

- `docs/reference/work-tracking.md` — the one reference doc: § The view (D1, D4, D6), § Items from mail and feedback queues (D2), § NEXT lines (D3, replacing its thread-anchor paragraph), the `drop --duplicate-of` verb row (D5).
- `docs/reference/thread-anchors.md` — its OPEN THREADS section points at `next` items where a store exists.
- `docs/reference/fabrik-mail.md` — `claim` and `ack` name the item they create and close.
- Both CLAUDE.md contracts — the D7 sentence.
- `CHANGELOG.md`, the D-rows below, `docs/workstation/hooks-index.md` (the harvest and prompt rows).

## Validation

- **V1 — one thread, one item.** Three Stops whose NEXT lines are the same thread in different words create one `next` item whose `next` holds the last text; a NEXT naming that item's id afterwards claims it. (Seam test through the real hook.)
- **V2 — mail round trip.** `mail.py claim` creates a claimed `mail` item in the claimer's store; `ack` closes it; in a store-less repo both behave exactly as today.
- **V3 — `ready` is crisp.** On the hub after adoption, default `ready` prints the obligation lines, this session's claims and owned items, awaiting items and at most 10 others; `ready --all` prints every open item.
- **V4 — budgets hold.** The prompt block, with the hub's inbox and queues, stays under 0.5 s (measured: the mail read is 0.7 ms today).
- **V5 — volume matches the measurement.** Two weeks after hub adoption, the count of `next` items created fleet-wide per week is within 2× of the measured 183, and the count of live claims is above 0.
- **V6 — duplicates.** `drop --duplicate-of` on an awaiting item merges digests; the old message harvested again creates nothing.

## Cobra (D-253)

- **"Who is working on what" satisfied by claiming everything.** Claims expire when read unless renewed at a Stop (the parent's lease), and `status` lists any session holding more than 5 claims.
- **A crisp `ready` satisfied by never assigning owners.** `status` shows the unassigned count to the distributor, and D4 always prints the top 10 others.
- **Thread items as busywork.** Nothing counts, scores or rewards items (the parent's rule); `next` items come only from what an agent already writes.
- **A mail claimed to look busy and never acked.** The growth trigger above (open `mail` items older than 14 days) lists them to the distributor.

## Open / blocking unknowns

- **Open, resolution step named.** Whether `_is_anchor` is the right filter for which free-text NEXT lines become thread items (it was built for thread anchors). Resolution: V5's reading two weeks after adoption; the growth trigger tightens it.
- **Open, resolution step named.** How `mail.py claim` finds the claimer's repo store when the claim runs from a different working directory. Resolution: the plan grounds it against `mail.py`'s repo argument (`claim(msg_id, repo)` at `scripts/mail.py:1006`) and the store's `repo_root`.
- **Resolved.** The mail read's cost (2.3 ms for the largest inbox, measured 2026-09-25).

## Cost

- `scripts/work.py` — the obligations reader, `ready` default, `drop --duplicate-of`, the D3 claim in `on_harvest`, the two kinds; tests.
- `scripts/thread_anchor.py` — thread items in the harvest, OPEN THREADS from items; tests.
- `scripts/mail.py` — claim/ack create and close the item (a fail-open call into the store API); tests.
- `commands/_sources/fabrik-command-improve.md` and `scripts/command_feedback_report.py` — take and close the feedback item.
- Both contracts and the docs above.
Every script is on a governance-sync path, so each ticket gets the full `/fabrik-review`, and merge order is adoption order: `work.py` first, then its callers.

## Decisions taken

- **Chosen: derive the view, create items only when an obligation is taken, and fold NEXT lines into claims or one thread item.** The judge panel ranked it first 3–0; no split verdict.
- **Operator ruling (2026-09-25, W-f8a26582):** the work store becomes the single tracker, built through the full chain — D-row minted with this spec's commit.
- `ack: no` mail is information, not an obligation, and is never counted or itemised.
- Thread anchors give way to `next` items wherever a store exists.
