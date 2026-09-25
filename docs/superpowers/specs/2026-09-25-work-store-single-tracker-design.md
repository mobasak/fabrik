# Design — the work store as the one place every open obligation shows up

Status: DRAFT
Profile: delta — every Intake item maps to code that exists today (`scripts/work.py`, `scripts/thread_anchor.py`, `scripts/mail.py`, `scripts/command_feedback_report.py`, `.claude/hooks/final_gate_stop.py`); this spec changes how they meet, and adds one measurement script.
Owner: infra
Parent: `docs/superpowers/specs/2026-09-24-work-tracking-design.md` (CONVERGED, D-394; built by plan `archived/2026-09-24-plan-2-work-tracking`, EXECUTED 02744deea)
Surface: `scripts/work.py`, `scripts/thread_anchor.py`, `scripts/mail.py`, `scripts/command_feedback_report.py`, `commands/_sources/fabrik-command-improve.md`, the new `scripts/sysadmin/next_census.py`, `CLAUDE.md` and `templates/governance/CLAUDE.md`, and the docs in § Documentation landing sites — the scripts and the template are fleet-synced or governance paths (rule 1: the full chain)

## Personas

- **The operator (primary).** In their words: *"we have specs, plans, we have stragetic_backlog. while agents are working all must be synced and maintained and updated properly, in each repo 3 different agent is working. one agent is managing the distribution of tasks and responsibilities. next is good feature. so we need our own tracking system."* And on 2026-09-25, after two agents' NEXT lines pointed at two different places: *"are you sure you have implemented a good tracking system ?"* They want ONE place that shows every open obligation and who is on it, without asking any agent.
- **The distributor agent** (intel on the hub, D-395): assigns owners; sees unowned, stale and over-claimed work in `status`.
- **The worker agents** (up to three sessions per repo): take work, do it, close it.
- **Automated consumers** — each duty's holder named:
  - the Stop hook (`.claude/hooks/final_gate_stop.py`) — runs `thread_anchor.py harvest`, which calls `work.on_harvest` with the turn's last NEXT (D3); the register itself is unchanged;
  - the prompt hook (`thread_anchor.py line --hook`) — prints `work.prompt_block` (D1, D4, D6);
  - `mail.py claim`, `ack`, `requeue` — create and close a mail item (D2);
  - `/fabrik-command-improve` — creates a feedback item when it takes a command's queue; `command_feedback_report.py --mark-answered` closes it (D2);
  - the completion gate's `Work items (sync)` row — reads drift class 6, which now also exempts `mail` and `feedback` items (D2);
  - fleet repos' agents — receive all of it through the governance sync.

**Step budgets (frozen).**
- Operator: open any session → the prompt shows every awaiting question, the mail and feedback-queue lines, and every live claim in the repo with its session and agent (1).
- Worker, on store work: the prompt shows its own claims (1) → work, ending the turn with `NEXT: <item id>`, which claims it (2) → `done --evidence <sha>` (3).
- Worker, on mail: `mail.py claim <id>` — the mail item is created and claimed (1) → work → `mail.py ack <id>` — the item closes (2).
- Distributor: `work.py status` shows unowned items, live claims per session, and `next` items about to be closed as idle (1) → `assign` (2).

Every item of § The delta traces to one of these; none is untraceable.

## Goal

After adoption, a reader who opens any session in a repo sees, in one block, every open obligation of that repo — store items, awaiting operator questions, mail that needs an answer, command feedback queues — and every live claim, so who is working on what. No obligation lives only in a place that block does not show.

## Why this exists

The parent spec built the store and fed it the backlog and DECISION blocks. Measured on 2026-09-25, one day after adoption:
- **Open work still lives in five places.** The store (at 51bdf4f24: 317 open items plus 1 awaiting); fabrik-mail (3,135 unread across 50 mailboxes, of which **158** carry `ack: required` and the rest are information); per-command feedback queues (455 ledger rows; `/fabrik-execute-plan` alone holds 36 unanswered); the per-session thread-anchor register; run records and plan boards.
- **Nobody records what they are on.** 0 live claims across the open items.
- **NEXT points anywhere.** The fleet's last 7 days, 47 sessions, re-measured 2026-09-25 with `next_census.py` (§ Validation): 14,736 `NEXT:` lines — 12,398 free text, 1,788 operator decision, 530 `none`, 11 naming an item, 9 `BLOCKED`. Fleet's NEXT on 2026-09-25 read *"… (it's queued in that command's feedback queue, not in the work store)"*. And a NEXT that only defers to the operator still rewrites the item it names: on 2026-09-25 the line `NEXT: operator decision: start W-992909ca now` replaced item W-992909ca's `next` text, because `_set_next` updates any named item (D3 rule 1 stops it).
- **`ready` is a swamp.** It lists every open item, most of them old backlog.
- **Owners do not resolve.** No hub window is named (`CLAUDE_AGENT` unset), so `--mine` finds nothing.

How this design removes each: one view reads the other sources live (D1); taking an obligation creates its item and claim (D2); every session's current free-text NEXT is one store item, and a NEXT naming an item claims it (D3); the prompt shows every live claim and `ready` defaults to what is yours (D4); a duplicate question can be retired (D5); an unnamed window is told so (D6).

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | *"we need our own tracking system"* (2026-09-24, the parent's I1) | IN — this spec completes it | § Goal |
| I2 | *"this is the type of mess and work tracking i am trying to resolve now make this tidy asap"* | IN | § Why this exists; the tidy itself was done in chat (5 stale anchors closed, W-e0e161b4 closed as a duplicate, commit 12f658d32) |
| I3 | *"are you sure you have implemented a good tracking system ?"* with intel's and fleet's NEXT lines | IN | § Why this exists; D1, D3 |
| I4 | *"yes it must of course"* — approving option A, the single tracker via the full chain (item W-f8a26582) | IN | the whole spec; D-416 |
| I5 | Gap 1: work lives in ≥ 5 places | IN | D1, D2 |
| I6 | Gap 2: 0 live claims | IN | D2, D3, D4 |
| I7 | Gap 3: NEXT is free text | IN | D3 |
| I8 | Gap 4: windows unnamed | IN (visibility); naming stays the operator's action | D6 |
| I9 | No verb retires a duplicate awaiting question (W-4025bfea) | IN | D5 |
| I10 | The register and the store hold the same threads apart | IN — the register stays as it is (D-392); the store holds one `next` item per session instead of mirroring the register | D3 |
| I11 | *"send mails to fleet and intel so they can work their items. we have a lot to cover."* | OUT-OF-SCOPE — done in chat, not a design item | mails 01M3C572CA1N6XJV0PV6CH7J1J (fleet) and 01M3C572JPBTV22MBS439Y61VG (intel), 2026-09-25 |
| I12 | The loop program's next measurement | OUT-OF-SCOPE — separate work | item W-992909ca |
| I13 | The git-decoder spec's design approval | OUT-OF-SCOPE — a separate question for the operator | item W-f9e2e6ec |
| I14 | The 45 synced repos have not adopted the store yet | OUT-OF-SCOPE — tracked | item W-59c5ab33 |
| I15 | fabrik-lib is sync-excluded and has no `work.py` | OUT-OF-SCOPE — its adoption is the operator's call with fabrik-lib | told to the three live fabrik-lib sessions, 2026-09-25 |
| I16 | *"inform all repo's agents about new way of working asap. they should run what is required"* | IN — this delta changes that way of working again, so its adoption carries a fleet announcement | § Lifecycle (Adoption) |

Intake: 16 items — 11 IN, 5 OUT-OF-SCOPE (each named above), 0 ASK.

## What exists today (grounded)

- The store: `scripts/work.py` — `KINDS = ("backlog", "decision", "next", "task")` at `:76` (a `next` kind exists and nothing creates it), `cmd_ready` at `:2503`, `cmd_claim` at `:2623`, `cmd_drop` at `:2690` (refuses awaiting items; owner, distributor, or anyone for an unassigned item), `cmd_status` at `:2749`, `_set_next` at `:2990` (updates the named item's `next`, **unless another session holds a live claim on it**), `on_harvest` at `:3005`, `prompt_block` at `:3067` (awaiting items, this session's claims, the ready count). `add --kind` takes its choices from `KINDS`. Owners must match the agent-name rule `[a-z0-9-]{1,32}` (`cmd_assign`, `:2483`).
- The register: `scripts/thread_anchor.py` — `_anchor_key` at `:430`, `_same_thread` at `:456`, `_is_anchor` at `:465`, `cmd_harvest` at `:535`, `cmd_line` at `:762` (OPEN THREADS), with caps `_MAX_ANCHORS`, `_MAX_FOLDED`, `_MAX_SHOWN` (`:128-140`). D-392 keeps it: *"the `thread_anchor.py` register stays"*.
- Mail: `scripts/mail.py` — `_current_repo` at `:303` (the repo's mailbox name is the MAIN-checkout basename, because worktrees lie), `claim` at `:1006` (inbox → archive, no disposition), `ack` at `:1088` (the same rename plus the disposition; works without a prior claim), `requeue` at `:1168` (archive → inbox), `list_msgs` at `:1484` (quarantines a malformed file — it moves it). D-271: teaching `mail.py` the whoami resolver once emptied a bound window's mailbox.
- Feedback queues: `scripts/command_feedback_report.py` reads the append-only ledger `~/.claude/state/command-feedback.jsonl` (455 rows on 2026-09-25); `--queue <command>` prints one command's unanswered rows (54 ms as a subprocess); `mark_answered` at `:327` records an applied edit against named rows, with a commit that touches the command corpus.
- Measured cost of the new mail read: all 95 inbox headers of the largest mailbox in 2.3 ms; the hub's 58 in 0.7 ms (2026-09-25).

## The delta

### D1. One view — read live, never copied

`work.py` gains one reader, `obligations(repo)`, returning at most two lines:
- **Mail:** the count of unread `ack: required` messages in this repo's inbox, with the oldest one's age — `mail: 3 need an answer (oldest 4 d) — python3 scripts/mail.py list`. The mailbox is `$FABRIK_MAIL_ROOT` (default `/opt/fabrik-mail`) + the main-checkout basename, the same rule as `mail.py`'s `_current_repo`. The reader opens each inbox file read-only and reads its header; it never calls `list_msgs`, so it never moves a file. `ack: no` mail is information and is not counted.
- **Feedback queues:** only in the repo that holds the command corpus (`commands/_sources/` present — the hub), shown to every session there: the unanswered depth of the three deepest commands — `feedback queues: fabrik-execute-plan 36 · … — /fabrik-command-improve <command>`. The reader parses the ledger once, in process, per call (never one subprocess per command).
- **Awaiting questions and claims** come from D4.

The reader fails open (any error → no line) and is shown at the head of `ready`, in `status`, and in the prompt block. Nothing from these sources is copied into the store by D1 — the sources stay the truth (the parent's § Spec and plan state is derived, never copied).

### D2. Taking an obligation creates its item

- **Mail.** `mail.py claim <id>` creates a `kind: mail` item — title the subject, `links.mail` the message id — claimed by the claiming session, in the store of the claiming repo (the repo whose mailbox holds the message; nothing when that repo has no store). The owner is the agent name `work.py` resolves, and the resolver is used ONLY for this store call — never to pick a mailbox (D-271). `mail.py ack <id>` closes the linked item as `done` with the note `mail ack: <disposition>`; `mail.py requeue <id>` closes it as `dropped` with the note `requeued` (the mail is back in the D1 count). An `ack` with no prior claim creates nothing (there was no taking to record).
- **Feedback queues.** When `/fabrik-command-improve <command>` takes a command's queue it creates one `kind: feedback` item for that command (never one per row), `links.command` the command name; `--mark-answered` closes it as `done` with the edit's commit.
- **The close.** Both closes go through one API function, `close_linked(repo, kind, link, status, note)`, under the store lock. `mail` and `feedback` items are exempt from the commit-names-the-id evidence rule: `done` refuses to close them by hand, their evidence is the mail disposition or the corpus commit, and drift class 6 (`work.py:1581`, today exempting only `legacy`) exempts both kinds too.
- **No hand-made ones.** `KINDS` gains `mail` and `feedback`, and `work.py add` refuses both — they come only from the paths above, as awaiting items come only from accepted DECISION blocks.

### D3. A NEXT claims the item it names, or becomes the session's one `next` item

At the Stop harvest (`thread_anchor.py harvest`, then `work.on_harvest` under the store lock), the turn's last `NEXT:` line is read in this order, and the first rule that matches decides:
1. **`none — terminal`, an operator decision, or `BLOCKED:`** → no claim and no thread item, whatever the line names (D-392: nothing forced).
2. **It names an item id** → the first id in the line that names an open, unblocked item no other live session holds is the target: its `next` is updated and the session claims it (a new claim, or a renewal of its own). No other named item is updated or claimed — this replaces today's `_set_next`, which updates the first id named whatever its state. If no id qualifies, no item is updated or claimed. In every case the session's own `next` item closes as superseded (below). A claim that fails for any reason fails open, like the rest of `on_harvest`.
3. **Free text the register accepts** (`_is_anchor`) → the session's `next` item carries it (below).
4. **Anything else** → nothing.

**The session's `next` item, as one rule.** While a session's last NEXT is free text the register accepts, the session has exactly one open `kind: next` item (`links.session` the session id) whose `next` and `next_at` are that text and the time it was set. When the session's NEXT falls under rules 1 or 2, the item closes as `dropped` with the note `superseded`; a later rule-3 NEXT opens a new one. Any Stop harvest in the repo closes as `dropped`, with the note `idle 7 days`, every `next` item whose `next_at` is more than 7 days old. Its `creator` is the session; its owner is the session's agent name, or empty (unassigned) when the window is unnamed — owners are always agent names. `dropped` is never read by drift class 6, which checks only `done` items. The register is not touched by any of this (D-392).

Measured volume (`next_census.py`, 2026-09-25, last 7 days): **17 sessions fleet-wide, 3 on the hub,** ended at least one turn on a free-text NEXT the register accepts — so at most that many open `next` items a week, before the 7-day close.

### D4. The view shows every claim; `ready` shows what is yours

- The prompt block adds every live claim in the repo, one line per claiming session: `on it: <session short id> (<agent or "unnamed">) — W-xxxx, W-yyyy`.
- `work.py ready` defaults to: the D1 lines; this session's claims; items owned by this agent; awaiting items; then the top 10 others by priority. `ready --all` prints every open item, as today. `next` is unchanged. The field's lesson, quoted: *"The goal is keeping bd ready crisp and actionable."* (Ian Bull on Beads, fetched 2026-09-25).
- `work.py status` adds three lines for the distributor: unowned open items (count); live claims per session, flagging any session holding more than 5; `next` items whose `next_at` is more than 6 days old (the ones the next Stop harvest will close within a day).

### D5. A duplicate question can be retired

`work.py drop <id> --duplicate-of <keep>` is allowed on an `awaiting-operator` `<id>` when `<keep>` is an open awaiting item, and only to the distributor or to a caller whose agent name or session id equals the `creator` field of each item (a rescued item's creator is its session id, so a named asker matches it from the asking session). `<keep>` records `<id>`'s `block_digest` in a new list `alt_block_digests`, and the harvest's open-item match reads that list too — so a later message that re-asks either wording refreshes `<keep>` instead of creating a third item. `<id>` closes as `dropped` with the note `duplicate of <keep>`, and `<keep>`'s question line in the prompt adds `(also asked as <id>)`.

### D6. An unnamed window is told so

When `_agent_name()` resolves nothing, the prompt block's first line reads: `work: this window has no agent name — owned items cannot reach it; run python3 scripts/whoami_agent.py --as <name>`. Naming stays the operator's action.

### D7. The contract line, and who commits

Every copy of the work-items paragraph — one in `CLAUDE.md`, two in `templates/governance/CLAUDE.md` — gains one sentence: end a turn on work with `NEXT: <item id>`, which claims it; claiming a mail creates its item. The files the hooks and `mail.py` write ride the session's next commit, as the paragraph already says of items a `NEXT:` line changes; `status` already lists uncommitted item files. No new gate (D-392).

## Contract deltas

None to `docs/data-contract.md` or `docs/ui-design.md` (the hub has neither). Item schema: two new `kind` values (`mail`, `feedback`), three new link keys (`links.mail`, `links.command`, `links.session`), a `next_at` time on `next` items, and `alt_block_digests` on awaiting items. Rule 2 changes what a NEXT naming an item updates (the qualifying item only). Drift class 6 exempts the two new kinds. CLI: `drop --duplicate-of`, `ready --all` (the old default).

## Rejected alternatives

- **Copy every obligation into the store** (a sync pass mirroring each `ack: required` mail and each feedback row as an item, and every distinct free-text NEXT as an item). Rejected 3–0 by the judge panel: two sources of truth that drift, against the parent's derived-never-copied rule, and **6,843** distinct NEXT texts a week plus 158 mails would bury `ready`.
- **Gate the Stop on a NEXT that names no item.** Rejected 3–0: the gate the operator refused (D-392 — *"agent will start making up unnecessary tasks in next field"*), and it leaves mail and queues where they are.
- **Retire the register into the store.** Rejected: D-392 keeps the register (*"3 no i will not do that"*).
- **One `next` item per register thread** (the first draft of this spec). Rejected in review: the register re-roots a thread's key on every rewording, keeps its per-session files with no expiry, and closes anchors from a CLI verb outside the Stop lock, so a 1:1 mirror could not hold; one item per session needs none of that.
- **Move mail into the store.** Rejected: fabrik-mail is the cross-repo transport with its own claim lock; the store is per repo.
- **One feedback item per queue row.** Rejected: 455 rows; the unit of work is a command's queue, which `/fabrik-command-improve` takes whole.
- **Let any agent retire a duplicate.** Rejected: it reopens the parent's cobra of an inconvenient awaiting question dropped to clear it (D5 limits it to the distributor or the creator of both).

## Lifecycle

- **Adoption.** Ships through the governance sync with the next `work.py`, `thread_anchor.py` and `mail.py`. Hub first; then the fleet on the existing rollout item (W-59c5ab33). The adoption ends with one fleet mail and a message to every live session stating the new rules — NEXT names the item you are on, claiming a mail creates its item — because the operator asked for every repo's agents to be told of each change to the way of working (I16).
- **Growth.** Triggers, each read from the store or `next_census.py`: more open `next` items with `next_at` within 7 days in one repo than sessions that ended a turn there in 7 days (the one-per-session rule is broken); the prompt block over 1 s; more than 50 open `mail` items older than 14 days in one repo (claims taken and not acked — the distributor's queue).
- **Degradation.** Every new reader fails open to "no line"; every new write happens where a write happens today (the Stop harvest, `mail.py claim/ack/requeue`, `--mark-answered`) under the parent's lock and budget rules. A repo without a store behaves exactly as today.
- **Retirement.** Items are files; removing the reader and the D2/D3 writes leaves them readable; the register was never changed.

## External dependencies and practice (fetched 2026-09-25)

- **Beads** (Steve Yegge) — README, raw: https://raw.githubusercontent.com/gastownhall/beads/main/README.md (curl, 200, 2026-09-25); found through an exa search and a brave search the same day. Its agent contract: *"Use `bd ready`, `bd show <id>`, `bd update <id> --claim`, and `bd close <id>`."* — one queue, an explicit claim, a close.
- **Ian Bull, "Beads - Memory for your Agent"** — https://ianbull.com/posts/beads/ (curl, 200, 2026-09-25): *"Claude doesn’t proactively use it. You need to say “track this in beads” or “check bd ready.”"* and *"CLAUDE.md instructions fade."* — the reason D2 and D3 hang on existing hooks and verbs rather than on an instruction; *"The goal is keeping bd ready crisp and actionable."* — the reason for D4; and *"The discovered-from type is particularly powerful."* — Beads' link for work found mid-task, which D3's per-session `next` item plays here.
- No external API is called; no vendor limit applies.

## fabrik-lib verdict

BUILD, inside existing hub scripts — no fabrik-lib module tracks work; the parent's verdict stands (fleet governance tooling, not a product module).

## Shape / infra

None — no service, no `shape:` flag, no port. Box-local files only: `/opt/fabrik-mail` is read by `work.py` and written only by `mail.py`, as today.

## Constraints

Digest (MUST-READ set computed 2026-09-25 by `review_rubric.py --changed` over the surface: FLOOR `core/10-python.md` + 12-FACTOR, MATCHED `core/40-documentation.md`) — carried from the parent's § Constraints unchanged: stdlib only for fleet-synced scripts; hooks fail open inside their budgets (Stop harvest 5 s kill, store lock ≤ 2 s from hooks, prompt store budget 3 s, and the prompt path takes the store lock only for the DECISION second chance — T04's A-O3); CLI verbs fail loud; no temporary workaround ships. Every D3 write happens in `on_harvest`, which already holds the store lock at the Stop; D1 and D4 only read; so A-O3 is untouched.

## Documentation landing sites

- `docs/reference/work-tracking.md` — the one reference doc: § The view (D1, D4, D6), § Items from mail and feedback queues (D2), § NEXT lines (D3), the `drop --duplicate-of` and `ready --all` rows (D5, D4), the new kinds and links.
- `docs/reference/thread-anchors.md` — one sentence: in a repo with a store, a free-text NEXT also becomes the session's `next` item (D3); the register is unchanged.
- `docs/reference/fabrik-mail.md` — `claim`, `ack` and `requeue` name the item they create and close.
- The three contract copies — the D7 sentence.
- `CHANGELOG.md`, D-rows, `docs/workstation/hooks-index.md` (the harvest and prompt rows), `INDEX.md` (the new script).

## Validation

- **V1 — one open `next` item per session; a NEXT claims.** Three Stops of one session with different free-text NEXT lines leave one open `next` item holding the last text and time; a following `NEXT: <open item id>` updates and claims that item and closes the `next` item as `dropped` `superseded`; a NEXT whose first id is awaiting and whose second is open updates and claims only the second; a NEXT naming only items another live session holds, or awaiting or closed ones, updates and claims no item; an operator-decision NEXT naming an id updates and claims no item; each of these closes the session's open `next` item as `superseded`; a `next` item whose `next_at` is 8 days old is closed by another session's Stop; drift class 6 lists none of these. (Seam test through the real hook.)
- **V2 — mail round trip.** `mail.py claim` creates a claimed `mail` item in the claiming repo's store; `ack` closes it `done`, `requeue` closes it `dropped`; an `ack` without a claim creates nothing; in a store-less repo all three behave exactly as today; `work.py add --kind mail` is refused.
- **V3 — the view.** On the hub, the prompt block lists every live claim with its session; default `ready` prints the D1 lines, this session's claims, owned items, awaiting items and at most 10 others; `ready --all` prints every open item.
- **V4 — budgets hold.** With the hub's inbox and the full feedback ledger, `work.py prompt_block` returns in under 0.5 s (timed in the test); the mail read measured 0.7 ms today.
- **V5 — volume matches the measurement.** `python3 scripts/sysadmin/next_census.py --since 7` — the three measurements of § Why this exists as one script — run two weeks after hub adoption: at every reading, the hub's open `next` items whose `next_at` is within 7 days number no more than the hub sessions that ended a turn in the last 7 days (measured 3 with a qualifying NEXT), and the hub shows more than 0 live claims.
- **V6 — duplicates.** After `drop A --duplicate-of B`, a new message re-asking A's wording refreshes B and creates no item; `drop` by an agent that is neither the distributor nor the creator of both is refused.

## Cobra (D-253)

- **"Who is working on what" satisfied by claiming everything.** Claims expire when read unless renewed at a Stop (the parent's lease), and `status` flags any session holding more than 5 claims (D4).
- **A crisp `ready` satisfied by never assigning owners.** `status` shows the unowned count to the distributor, and D4 always prints the top 10 others.
- **`next` items as busywork.** Nothing counts, scores or rewards items (the parent's rule); a `next` item comes only from a NEXT line the agent already writes, one per session.
- **A mail claimed to look busy and never acked.** The growth trigger (open `mail` items older than 14 days) lists them to the distributor.
- **An inconvenient question retired as a "duplicate".** Only the distributor or the creator of both may do it, and the kept question names the one it absorbed (D5).

## Open / blocking unknowns

- **Open, resolution step named.** Whether `_is_anchor` is the right filter for which free-text NEXT becomes the session's `next` item (it was built for the register). Resolution: V5's reading two weeks after adoption.
- **Resolved.** The mail read's cost (2.3 ms for the largest inbox) and the feedback queue's (one in-process parse replaces a 54 ms subprocess per command), measured 2026-09-25.
- **Resolved.** Which repo a mail item lands in: the repo whose mailbox holds the message, named by the main-checkout basename (`mail.py:303`).

## Cost

- `scripts/work.py` — `obligations`, the D4 prompt lines, `ready` default and `--all`, the `status` lines, `drop --duplicate-of`, `alt_block_digests`, the D3 rules in `on_harvest` (claim, the per-session `next` item, the 7-day close), `close_linked`, the two kinds and their drift class 6 exemption; tests.
- `scripts/thread_anchor.py` — no logic change: it already passes the turn's last NEXT to `on_harvest`; its seam tests grow.
- `scripts/mail.py` — `claim`, `ack`, `requeue` call the store (fail open); tests.
- `commands/_sources/fabrik-command-improve.md` and `scripts/command_feedback_report.py` — take and close the feedback item.
- `scripts/sysadmin/next_census.py` — the measurement script (new).
- The three contract copies and the docs above.
Every script but the census is on a governance-sync path, so each ticket gets the full `/fabrik-review`, and merge order is adoption order: `work.py` first, then its callers.

## Decisions taken

- **Chosen: derive the view, create items only when an obligation is taken, keep one `next` item per session, and let a NEXT claim the item it names.** The judge panel ranked Derive first 3–0; no split verdict.
- **Operator ruling (2026-09-25, W-f8a26582):** the work store becomes the single tracker, built through the full chain — D-416.
- The register stays as it is (D-392); the store never mirrors it.
- `ack: no` mail is information, never counted or itemised.
- `mail` and `feedback` items come only from taking an obligation, never from `add`.
