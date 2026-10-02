# Merge-request loop — finished work reaches base, safely and at once, in every repo

Status: CONVERGED (2026-09-30, /fabrik-spec-review — 4 passes, confirmed 29 → 10 → 4 → 0, scope-growth stop at pass 3; see § Review — Pass Ledger; D-462)
Profile: delta — every item maps to code that exists today (fabrik-mail, the self-watch, the merge-owner row,
the work-store distributor, the Stop hook's worktree push rule); the delta adds one mail kind, one lookup verb,
one merge script and one Stop-hook duty. Delta on `docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md`
(CONVERGED, D-447, approved D-448) and `docs/reference/multi-agent-operating-model.md`.

## Personas

- **PRIMARY — the operator**, in their own words: *"in each repo, including fabrik and fabrik-lib, when agent
  finishes their work, they should send a mail to merge authority and coordinator agent to commit and push the work
  without causing data loss and the merge and coordinator agent must be self watched to read and act immediately."*
  They never relay a merge by hand and never lose a sibling's work.
- **The finishing agent** (any agent 2..N, in its linked worktree `.claude/worktrees/<name>/`, branch
  `worktree-<name>`) — SENDS the merge request when its work is finished. Holds duty D-A: run
  `merge_request.py request` and send the doorbell it prints (delta 3, 4).
- **The merge owner** (agent 1 — the repo's `MERGE OWNER:` row, `scripts/decisions.py:582-599`; `infra` in the hub,
  D-453) — the only writer of the base branch. RECEIVES, merges, pushes, replies. Holds duties D-B, D-C.
- **The coordinator** (the work-store distributor — `scripts/work.py:2590-2593`; `intel` in the hub, D-395; defaults
  to the merge owner in a project) — RECEIVES a copy, sees every request, closes or re-assigns the linked work item
  on the owner's reply (it never merges and never re-routes). Holds D-D.
- **Automated consumers:** `mail.py` (writes the durable record), `mail_notify.py` (surfaces it at SessionStart /
  UserPromptSubmit), the Stop hook `final_gate_stop.py` (enforces D-B in the main checkout), `mail_escalate.py`
  (cron — Telegrams the OPERATOR about an `ack: required` request still unacked after 3 days; a notice of stuck
  work, never a question), the governance post-merge sync (distributes a merged trigger path).
- **Peers in other worktrees** — told "merged — rebase" by the owner's reply (existing multi-agent-operating-model.md
  step 3, `:153`).

**The primary loop, counted (STEP BUDGET = 5):** (1) the finishing agent commits and pushes its branch (existing §
EXIT law); (2) it runs `merge_request.py request` (the durable mail to the owner and the coordinator) and sends the
`SendMessage` doorbell lines it prints; (3) an idle owner session starts a turn on the doorbell (native, documented); (4) the owner runs ONE
command, `merge_request.py merge`, which merges data-safely and pushes; (5) the script replies to the requester and
the coordinator and acks the mail. The operator touches none of the five.

Every feature below traces to a persona: the kind → the finishing agent; the doorbell → owner and coordinator
("act immediately"); the merge script → the owner ("without causing data loss"); the coordinator copy and item close
→ the coordinator; the owner's Stop-hook duty → the operator (the loop runs without them asking).

## Goal

In every repo on the box — the hub, fabrik-lib, and all 41 projects — finished work in a linked worktree reaches the
base branch through one request, one wake and one data-safe merge, with no operator relay and no hand-rolled merge.

## Why this exists

Measured 2026-09-30 in the hub alone: six merge requests from fleet and intel arrived as live cross-session messages
(ephemeral — lost when either session is closed), and each merge was hand-rolled by infra — a detached worktree, a
compare-and-swap `update-ref`, a hand-carry into a main tree dirty with sibling WIP. One of the six went wrong
mid-flight (a resolution script failed but the commit after it still ran, committing conflict markers into the scratch
worktree; caught before master). Nothing tells a worktree agent it OWES a report: the report is prose only
(`multi-agent-operating-model.md:149-158`, `final_gate_stop.py:3059-3067`), template § EXIT is silent on it, and mail
never wakes an idle session (`mail_notify.py` fires only on SessionStart/UserPromptSubmit). With 39 repos being
moved onto the three-agent model today (W-d89b1c62), every one of them would re-invent this by hand.

## What exists today (grounded)

- **Roles.** `MERGE OWNER:` row → `decisions.py --merge-owner` (`scripts/decisions.py:40`, `:582-599`; UNDECLARED
  exits 3). Distributor → `.fabrik/work/config.json`, defaulting to the merge owner at `work.py init`
  (`scripts/work.py:2590-2593`), gating `assign` (`:2685-2688`). Hub: infra owns merges, intel distributes
  (`multi-agent-operating-model.md:239-248`). fabrik-lib: `fabrik-lib-sentinel` (its own ledger, D-336 there).
- **The handoff today.** `multi-agent-operating-model.md:149-153`: the agent rebases and pushes; agent-1 merges `--no-ff`
  and verifies; agent-1 messages the others. The Stop hook asks a no-upstream worktree branch to push and "report the
  branch to the merge owner" (`final_gate_stop.py:3059-3067`) — no mechanism names how.
- **fabrik-mail.** Durable `<root>/<repo>/inbox/<ULID>.md` (`scripts/mail.py:425-432`); kinds `request|finding|relay|
  reply|upstream-feedback` (`:54`); header `id from to ts re kind ack hops [agent]` (`:460-487`); `claim` is the lock
  (`:1225`), `ack` closes (`:1307`), `route` re-addresses (`:1252`). Surfaced only at SessionStart/UserPromptSubmit
  (`.claude/hooks/mail_notify.py`). Handle-now is the rule (`docs/reference/fabrik-mail.md:92-98`).
- **The rejected dispatcher.** *"No daemons, watchers, LLM, ledgers, systemd units"*
  (`docs/development/plans/archived/2026-08-25-plan-1-mail-dispatcher.md:25-26`, operator 2026-08-26).
- **The self-watch.** One background Bash task per session whose exit re-invokes the idle session
  (`scripts/sysadmin/selfwatch_arm.sh:7-9`, D-356); today woken only by the quota hold's lift (D-177/D-178); D-359: a
  standing arm once read as a lost waker and falsely woke every idle session every ~62 min.
- **Native cross-session messaging** (Claude Code ≥ 2.1.224; the box runs 2.1.280): an idle receiver starts a new turn
  on a message; auto/default-mode receivers deliver peer messages (see § External dependencies).
- **Live session registry.** `~/.claude/sessions/<pid>.json` carries `sessionId`, `cwd`, `name`,
  `messagingSocketPath` (read by the orchestrator 2026-09-30; not seat-verifiable, since seats never read
  `$HOME/.claude*` — an undocumented Claude Code internal); `scripts/whoami_agent.py` binds a session id to an agent
  name, and a session launched as `CLAUDE_AGENT=<name> claude` carries the name in its process environment.
- **No merge helper exists** (search of scripts/, .claude/hooks/, commands/*.py for update-ref / worktree add /
  merge-file: only `wip_backup.sh` backup refs).

## The delta

1. **A `merge-request` mail kind** (`scripts/mail.py` `KINDS`, `:54`), `ack: required`. Its body is WRITTEN BY THE
   SCRIPT, never by hand: `branch`, `head` (full SHA), `base`, `item` (the work item the branch finishes, or `none`),
   `review` (the closing run record or receipt path, verified to exist), `doorbell` (the session names `who` returned,
   or `none`), `sent` (ISO time). `files` and `synced` are NOT sender fields — the merge script re-derives both from
   `git diff --name-only base...head` and the governance-sync filter, so a sender cannot make the sync skip or narrow
   the file list (answers S-rules-O9).
2. **One command sends it — `scripts/merge_request.py request [--item <id>]`**, run by the finishing agent inside its
   worktree. It refuses unless the branch is pushed and `head` equals the remote tip (`git ls-remote`; unreachable
   remote → exit with the reason, never a partial send). It writes one message to the merge owner (`agent:` = owner)
   and, when the coordinator is a DIFFERENT agent, a second message to the coordinator (`agent:` = distributor,
   `ack: no`) — two `mail.py send` calls, because a message carries one `agent:` (`mail.py:460-487`, `:827-836`;
   answers S-ground-S1). The coordinator resolves from `.fabrik/work/config.json`; a repo with no work store has
   no coordinator and gets the one message (answers S-rules-O13). With `--item` it releases the sender's live claim
   on that item so the coordinator can later close it (answers S-rules-O14); another session claiming the released
   item meanwhile makes the coordinator's close fail loudly, and it retries on its next turn (a known, visible race).
3. **The finish signal is the request itself.** "Finished" means the agent ran `merge_request.py request` — never
   "a push happened". The existing Stop rule keeps forcing WIP pushes; a pushed branch without a request is simply
   unfinished work (answers S-rules-O1). The template § EXIT gains the duty: *when the branch's work is finished, run
   `merge_request.py request` and send the doorbell it prints.*
4. **The doorbell — `mail.py who <agent>` and the agent's `SendMessage`.** `who` prints the live session name(s) of an
   agent in THIS repo: a session in `~/.claude/sessions/<pid>.json` counts when its `CLAUDE_AGENT` (read from
   `/proc/<pid>/environ`, same user) equals the agent OR a `whoami_agent.py` binding names it (answers S-rules-O10),
   and its `cwd` resolves to the same git common dir as the caller (`git -C <cwd> rev-parse --path-format=absolute
   --git-common-dir`, realpath-compared, never a path prefix — answers S-rules-O11, S-rules-O26). `merge_request.py request` runs `who` for both recipients, records the result
   in the body's `doorbell` field, and prints one `SendMessage` line per name; the agent sends them. An idle receiver
   in auto/default mode starts a turn on it; a receiver in bypass mode HOLDS it for approval and may drop it after the
   dialog expiry (External dependencies — answers S-external-S1). Best effort by design: the durable mail is the
   guarantee, the doorbell the speed (S-rules-O16 recorded as the cobra path in § Lifecycle).
5. **One merge command — `scripts/merge_request.py merge [<id>]`**, the merge owner's only merge path. Every run holds
   an exclusive `flock` on `<git common dir>/fabrik-merge.lock` for its whole life, so two owner sessions never merge
   at once, and it records each request it claims in `<git common dir>/fabrik-merge/<id>.json` (claimer session, pid,
   phase reached, merge SHA). A request is STRANDED only when that record exists, its phase is short of `replied`,
   and the process it names (pid + start time) is no longer alive — the lock already keeps any OTHER live run out, so a
   run holding the lock can decide this for its predecessors (answers S-rules-O21, S-rules-O24, S-rules-O33). The run FIRST resumes a
   stranded request from its recorded phase, then takes the oldest UNCLAIMED `merge-request` whose `agent:` is the
   owner and `ack: required` (the coordinator's copy is never picked — answers S-rules-O2). FIFO is the default; the
   owner may name `<id>` to keep a plan's `epic_order` (multi-agent-operating-model.md § Merge protocol stands;
   answers S-rules-O18). The steps:
   - **(a) Preflight — nothing outside the throwaway worktree changes.** `git fetch`; refuse if origin's base is ahead
     of local base (the owner pulls first — this is a START condition only). Build the merge in a throwaway detached
     worktree off the current local base, with a message naming the request id and the `item`
     (`merge(<agent>): <branch> — request <id>, item <item>`, so `work.py`'s evidence rule accepts it — answers
     S-rules-O28). Record a SNAPSHOT (blob hash, or absent) of every merged path in the main checkout (answers
     S-rules-O4) and refuse, base untouched, when any merged path is: untracked in the main checkout (answers
     S-rules-O3); dirty and NOT one of the five ledgers (answers S-rules-O6); deleted or renamed by the merge while
     dirty (S-rules-O6); or staged differently from HEAD (answers S-rules-O19). For each dirty ledger, compute the
     3-way carry into a TEMP file (`git merge-file -p`) and refuse if it conflicts.
   - **(b) Ledger conflicts in the build.** Only the five shared-append ledgers (`CHANGELOG.md`, `docs/DECISIONS.md`,
     `INDEX.md`, `docs/STRATEGIC_BACKLOG.md`, `docs/LESSONS_LEARNT.md`) are auto-resolved, and only when BOTH sides are
     pure insertions at the conflict (neither side edits an existing line) — keep both, newest first for DECISIONS,
     then a line-anchored marker check. A conflict where either side modifies an existing ledger line, or any other
     conflict, refuses with "rebase on <base> and resend" (answers S-rules-O7).
   - **(c) Tests on the merged tree.** The OWNER's test command runs, never a requester string: the command in
     `.fabrik/merge-tests` read from the CURRENT BASE (`git show <base>:.fabrik/merge-tests`), so a branch cannot add or
     edit it (answers S-rules-O9, S-rules-O25), else pytest over the merged `tests/` files the diff touched; the
     worktree's own `src` first on the path (W-83ff5917) and a `fabrik-lib` sibling link when the repo vendors it. A
     red test refuses.
   - **(d) Move the local base.** Immediately before it, RE-HASH every merged path against the (a) snapshot; any
     change sends the run back to (a) (a fresh snapshot, within the rebuild budget below) — so the snapshot the carry
     relies on is current to the moment of the CAS (answers S-rules-O27, S-rules-O32). Compare-and-swap (`git update-ref <base> <new> <old>`). A failure means the local
     base moved during the build (the daily pipeline or a hook commit): REBUILD on the new local base and re-run (a),
     (b) and (c) in full — snapshot, refusals and tests all fresh — up to 3 times, then refuse (answers S-rules-O22,
     S-rules-O30). Once (d) succeeds the merge is committed; every later step is resumable, never undone.
   - **(e) Carry.** Immediately before writing, RE-HASH each merged path in the main checkout against the (a)
     snapshot; a path that changed in the milliseconds since (d) is not overwritten: its index entry is still reset to
     the merge (so no staged reverse of the merge is left behind), its working copy keeps the owner's edit, and it is
     listed in the reply (answers S-rules-O27, S-rules-O32).
     Unchanged clean paths are checked out from the new base, clean deleted paths removed, new paths created, dirty
     ledgers written from the 3-way result recomputed now; then `git reset -q <new> -- <carried paths>` realigns ONLY
     those index entries.
   - **(f) Push.** Fast-forward push of the new base (never `--force`). Rejected — origin moved from another machine
     during the run — `resume <id>` catches up WITHOUT a rebase or a stash: it merges origin's base into the local base
     through this same procedure ((a)-(e): throwaway worktree, snapshot, refusals, CAS, carry), then pushes. The
     request's merge commit stays in history unchanged, so its SHA in the reply and in `work.py` evidence stays valid
     (answers S-rules-O5, S-rules-O23, S-rules-O31).
   - **(g) Sync.** In the hub, when the re-derived file list matches the governance-sync filter, run the sync.
   - **(h) Reply and ack.** Reply to the requester and the coordinator with the merge SHA and each step's evidence;
     ack the request `done`. A refusal acks `blocked` with the reason. The worktree is removed either way.
   - **`resume <id>`** continues from the recorded phase. A request whose `head` is already an ancestor of base finds
     its merge commit by the request id in the message and skips straight to (e)-(h) — never a second merge (answers
     S-rules-O29).
6. **The owner's duties — D-B (act) and D-C (answer).** D-B: a merge owner whose repo inbox holds an unclaimed
   `merge-request` addressed to it runs `merge_request.py merge` until none remain before starting other work. D-C:
   every request ends in a reply (merged or refused). Enforced by a Stop-hook cause IN THE MAIN CHECKOUT only: a turn
   ends blocked while such a request waits in the inbox OR a request record is stranded short of `replied`, with the command in the message, capped at 3 attempts like every other
   cause (answers S-rules-O15).
7. **The coordinator's duty (D-D).** The copy keeps the coordinator current: when the owner's reply lands and the
   body named an `item`, the coordinator closes it (`work.py done <item> --evidence <merge sha>` — the merge commit's
   message names the item) or re-assigns it on a refusal. It never merges unless it IS the owner, and it re-routes
   nothing: an owner with no live session means the request waits durably (answers S-ground-S2, S-rules-O15).
8. **Where no owner is declared.** In a repo still `UNDECLARED` (`decisions.py --merge-owner` exits 3),
   `merge_request.py request` refuses with the adopt command, and the D-B Stop cause never fires; § EXIT's duty
   reads as advice there until the repo adopts (answers S-rules-O12).
9. **fabrik-lib.** Sync-excluded: the change reaches it as a mail request to `fabrik-lib-sentinel` carrying the
   template text and the script to vendor; the hub never edits it.

**Data-safety invariants (the operator's "without causing data loss"):** (1) every refusal happens in (a)-(c),
before the local base moves, so a refused request leaves origin, the local base and the main checkout byte-identical;
(2) the local base moves only by CAS after the tests pass, origin only by fast-forward push after that; (3) the main
checkout's untracked, dirty, staged and deleted-while-dirty files are never overwritten — any such collision refuses in
(a), and a path that changes after (a) is never written in (e) — the owner's working copy is kept, its index entry
realigned to the merge, and the path listed in the reply with the warning that a later `git commit -a` would revert the
merge there; (4) only pure-insertion ledger conflicts are
auto-resolved; (5) no stash, no `--force`, no `git add -A`, no whole-index reset; (6) one merge run per repo at a time
(the merge lock), every claimed request recorded with its phase, and a stranded one resumed from that phase, so no
request is merged twice or lost.

## Contract deltas

- `mail.py` kind vocabulary +1 (`merge-request`), a new read-only verb `who`, and two checks in `mail.py` itself, so no
  path around them exists: `claim` and `ack` of a `merge-request` refuse unless the caller resolves to the message's
  `agent:`, and `ack --disposition done` of one requires `--merge-sha <sha>` naming a commit that is an ancestor of
  base and carries the request id in its message (answers S-rules-O8); `docs/reference/fabrik-mail.md`
  § kinds and § ack defaults gain the rows.
- Template `templates/governance/CLAUDE.md` § EXIT +1 duty (governance-sync path — distributes to ~46 repos).
- `scripts/merge_request.py` — NEW: `request`, `merge [<id>]`, `resume <id>` (box script, vendored with the template).
- `.claude/hooks/final_gate_stop.py` +1 cause, D-B, main checkout only, CAP 3 (governance-sync path).
- No data-contract, ui-design or schema change.

## Chosen approach

**"Bell"** — the durable mail is the record, the native cross-session message is the wake, and the self-watch is left
as it is. Ranked first by 2 of 3 judges (§ Decisions taken). It consumes a documented Claude Code capability
("When the receiving session is idle, Claude Code starts a new turn with the message") instead of building a waker,
stays inside the operator's 2026-08-26 no-daemons/no-watchers ruling, and does not touch the self-watch/Stop-decider
surface D-359 shows is fragile. Its gap — an owner with no live session — degrades to today's behaviour (the mail
waits; SessionStart surfaces it), and § Lifecycle measures that gap before anything more is built.

**"Self watched"** is met by the session's own native inbox: every live session already listens on its socket and
wakes on a message — the watch the operator asked for, without a second standing watcher per session.

## Rejected alternatives

- **"Watch" — extend the self-watch to poll the repo inbox and wake on a merge request.** Ranked first by 1 of 3
  judges (it covers a closed-owner case Bell cannot). Rejected: a polling watcher is the shape the operator rejected on
  2026-08-26; it re-opens the self-watch wake taxonomy D-359 had to special-case; "immediate" becomes "within the poll
  interval". Kept as the measured upgrade path (§ Lifecycle).
- **"Both" — Bell plus the Watch backstop.** Rejected for now: two wake paths for one event, the largest surface, and
  the backstop covers a case not yet measured. Upgrade path, not first build.
- **`mail.py` posts the doorbell to the peer socket itself.** Rejected: the wire format for posting to ANOTHER
  session's socket is not documented (only a session's own children are described); coupling to an undocumented
  protocol is the fragility the design avoids. The agent's own `SendMessage` is the documented path.
- **A mail dispatcher / systemd path unit that launches a headless merge.** Rejected by the operator 2026-08-26, and a
  merge with no session to adjudicate a refusal is exactly where data loss happens.
- **Live messages only (today's practice).** Rejected: ephemeral, lost when either session is closed, no record, no
  enforcement.
- **The finishing agent merges its own branch.** Rejected: contradicts the one-writer rule (D-444/D-453) and the
  template's "never edit the main checkout" (`templates/governance/CLAUDE.md:48`).
- **A per-repo merge-queue service (GitHub merge queue).** Rejected: requires PR-based flow and GitHub Actions on every
  repo; the box merges locally by design. Its FIFO + test-against-latest-base discipline is adopted inside the script.

## Lifecycle

- **Adoption:** the hub first (infra runs `merge_request.py` for fleet and intel requests); then every repo on its
  next governance sync (the template duty, the script and the owner's Stop cause arrive together); fabrik-lib by mail
  request. In a repo still UNDECLARED, `merge_request.py request` refuses with the adopt command and the owner's Stop
  cause never fires (delta 8); the adopt order stands (W-d89b1c62).
- **Growth:** requests per repo per day are counted from the mail archive (`kind: merge-request`). Both inputs of the
  trigger are recorded: the body's `doorbell` field (what `who` returned at send) and `sent` time, and the ack line's
  timestamp in `archive/`. TRIGGER for the "Both" backstop: over any 14-day window, more than 10% of requests carry
  `doorbell: none` AND were acked more than 60 min after `sent`. Below that, no watcher is built.
- **Degradation:** no live owner → the mail waits, SessionStart surfaces it, and after 3 days `mail_escalate.py`
  Telegrams the operator that the request is stuck (a notice, never a question). A refused merge → the requester is told why and
  resends after a rebase. A doorbell to a session that has since exited is dropped by Claude Code — the mail remains.
- **The cobra path (D-253):** the cheapest way to satisfy D-A without the outcome is to run `request` and skip the
  doorbell — the loop then falls back to SessionStart latency. The SendMessage itself is unverifiable by any script, so
  it is measured by its effect: a request whose `doorbell` names live sessions yet was acked more than 60 min after
  `sent` is a SUSPECTED skip, counted separately from the backstop trigger above (which counts `doorbell: none`) and
  reported to the coordinator; the owner's D-B Stop cause also catches the request at the owner's next turn end.
  For the owner, the cheapest way past D-B is to ack a request without merging; `mail.py ack done` itself refuses
  without a merge SHA that is an ancestor of base and names the request (Contract deltas).
- **Supersession / retirement:** if Claude Code ships a documented way for a script to message another session, the
  doorbell moves into `mail.py send` and the agent's `SendMessage` step is deleted. If the fleet moves to PR-based
  review, `merge_request.py` is retired in favour of the forge's queue.

## External dependencies

- **Claude Code cross-session messaging** — https://code.claude.com/docs/en/cross-session-messaging (fetched
  2026-09-30 via WebFetch): *"When the receiving session is idle, Claude Code starts a new turn with the message."*;
  requires v2.1.224+ on Linux incl. WSL 2 (box: 2.1.280); auto/acceptEdits/dontAsk receivers deliver peer messages,
  bypass-mode receivers hold them; ≤ 50 queued per receiver; plain text; same-machine over a per-session socket; a
  closed session cannot receive. A receiver in bypass mode holds a peer message behind an approval dialog, which
  drops it after `dialogExpiry` (5 min default); the box's accounts run `auto`, which delivers.
- **git update-ref** — https://git-scm.com/docs/git-update-ref (fetched 2026-09-30): the three-argument form updates
  the ref only when its current value equals the given old value (the placeholder tokens render inconsistently across
  fetchers, so the sentence is paraphrased); verbatim: *"Otherwise, no modifications are performed."*
- **Merge-queue discipline** — https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
  (fetched 2026-09-30): merges *"in a first-in-first-out order"*, each validated with *"the latest version of the
  base_branch as well as changes from pull requests ahead of it"*; a failing change *"will be removed from the queue"*.
- **Claude Code session registry** (`~/.claude/sessions/<pid>.json`) — undocumented box internal; read by `mail.py
  who` only, and a format change makes `who` print nothing (the durable mail still carries the request).

## fabrik-lib verdict

| Capability | Verdict | Why |
|---|---|---|
| Mail transport, claim/ack locking | reuse (hub `scripts/mail.py`) | already the fleet's durable channel |
| Session wake | consume (Claude Code native messaging) | documented, free, first-party |
| Safe merge over a dirty tree | build (`scripts/merge_request.py`) | no module or script exists (searched: scripts/, fabrik-lib module table) |

## Shape / infra implications

None — no service, port, database or deploy. Box-local scripts and one synced hook cause.

## Documentation landing sites

`docs/reference/multi-agent-operating-model.md` § Merge protocol (the handoff, rewritten to name the request and the
script); `docs/reference/fabrik-mail.md` (the kind, its body fields, `who`); `docs/workstation/hooks-index.md` (the
Stop cause); `templates/governance/CLAUDE.md` § EXIT; `INDEX.md` rows for `scripts/merge_request.py` and its tests;
CHANGELOG; the D-row.

## Constraints

| Rule | Source (verbatim) |
|---|---|
| Durable state never in /tmp | `core/10-python.md:153-154` — "Anything that must SURVIVE a restart is not temp … never in `.tmp` and never in `/tmp`." (the queue IS the mail store; scratch worktrees are disposable) |
| Deps untouched | `core/10-python.md:30` — "Do not modify these files unless the ticket authorises it." |
| Synced docs are hub-owned | `core/40-documentation.md:43` — "Fabrik-hub-owned — do NOT edit locally (centrally synced, overwritten every sync)" |
| One CHANGELOG entry per change | `core/40-documentation.md:134` — "Every code-shipping ticket must produce exactly one entry." |
| No daemons or watchers | archived `2026-08-25-plan-1-mail-dispatcher.md:26` — "No daemons, watchers, LLM, ledgers, systemd units." |
| One writer of base | D-453 — "MERGE OWNER: infra — the only writer of the hub's main checkout" |

## Open / blocking unknowns

- **U1 (resolved in design):** the peer-socket wire format is undocumented → the doorbell uses `SendMessage`.
- **U2 (open, resolution step in the plan's first ticket):** does a `SendMessage` to an idle session in the VS Code
  extension start a turn exactly as the terminal does? Resolution: send one to a known-idle hub window and observe the
  turn start (the doc states it for "the receiving session" without surface qualifiers).
- **U4 (routed):** six residuals the scope-growth stop recorded (O34 the ack-done guard must also require the
  request head be an ancestor of the merge SHA; O35 the catch-up merge exempt from (a)'s origin-ahead start refusal; O36
  the record's pid is the run's own, with its start time; invariant (3)'s stale 'skipped' word; a raced path reverted by
  a later `git commit -a`; `ack --disposition blocked` needing a reason) — W-8a6a5644; the plan turns each into a
  ticket acceptance line.
- **U3 (open):** whether `mail_escalate.py`'s 3-day age is too slow for a merge request; the growth measurement in §
  Lifecycle (send-to-ack latency per request) decides it with data.

## Validation

- V1: `merge_request.py request` refuses an unpushed or not-at-tip `head`, and an UNDECLARED repo (tests).
- V2: `request` writes two messages when the coordinator differs, one when it is the owner or absent (test).
- V3: `mail.py who` finds a session by `CLAUDE_AGENT` in `/proc/<pid>/environ` AND by a whoami binding, and filters by
  git common dir — a `/opt/fabrik-lib` session never matches `/opt/fabrik` (fixture registry; red when either source or
  the common-dir filter is removed).
- V4: `merge` over a fixture repo whose main checkout has dirty CHANGELOG/DECISIONS WIP: base advances by one merge
  commit, sibling hunks survive byte-for-byte, the requester and coordinator get replies (mutation-proved on the carry
  and the CAS old value).
- V5: the preflight refuses, with origin, base and the main checkout byte-identical, for each of: an untracked
  collision, a dirty non-ledger merged path, a dirty path the merge deletes, a staged-only difference, a non-pure-
  insertion ledger conflict, a red test (one test per case).
- V6: origin ahead at start refuses; a local-ref move during the build rebuilds with a fresh snapshot and tests, and
  refuses after 3; a rejected push leaves the merge committed locally and `resume` finishes it (tests).
- V7: `merge` never picks the coordinator's copy; resumes a stranded claim first; never resumes one a live run holds
  (merge lock held); resuming a request already in base skips to the carry with the existing merge SHA (tests).
- V7b: `mail.py claim|ack` of a merge-request by a non-addressee is refused, and `ack done` without a valid merge SHA
  is refused (tests).
- V7d: a rejected push is finished by `resume` via a catch-up merge — no rebase, no stash, the request's merge SHA
  still an ancestor of base (test); a path edited between snapshot and CAS sends the run back to (a) (test).
- V7c: the carry skips a path edited after the snapshot, and `.fabrik/merge-tests` is read from the base, never the
  branch (tests).
- V8: the owner's Stop cause blocks the main checkout while an unclaimed request addressed to it waits, and warns
  through at CAP 3 (test).
- V9: live: the next fleet or intel request in the hub goes end to end with no hand-rolled step.

## Cost

Build: `merge_request.py` (~450 lines: request, merge, carry) with tests, `mail.py` kind + `who` (~100 lines), one Stop
cause (~60 lines), four doc edits. No runtime cost beyond each merge's own test run.

## Decisions taken

- Approach "Bell" — judge panel 2026-09-30: judges 2 and 3 ranked Bell first, judge 1 ranked Watch first (its reason:
  Watch covers the closed-owner case). The split is carried to the operator's approval as an open question.
- The coordinator is the work-store distributor (D-395 in the hub; the merge owner by default elsewhere).
- The finishing agent sends the doorbell with `SendMessage`; no script writes to another session's socket.
- Only the five shared-append ledgers are auto-resolved, keep-both, and only for pure-insertion conflicts.
- Finished = `merge_request.py request` was run; a push alone is not a finish signal.
- The merge owner's test command, never a requester-supplied one; `files`/`synced` re-derived, never trusted.
- Origin is fast-forwarded before the local base moves; every refusal precedes both.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "in each repo, including fabrik and fabrik-lib" | IN | § Goal, § Lifecycle adoption, delta 7 (fabrik-lib by mail) |
| I2 | "when agent finishes their work, they should send a mail" | IN | delta 1-3 (the kind; `request`; finished = the request) |
| I3 | "to merge authority and coordinator agent" | IN | delta 2 (owner + distributor copy, two messages) |
| I4 | "to commit and push the work" | IN | delta 5 (merge, fast-forward push, CAS), delta 6 (owner acts) |
| I5 | "without causing data loss" | IN | delta 5 (a) preflight + § Data-safety invariants |
| I6 | "the merge and coordinator agent must be self watched" | IN (CHANGED) | § Chosen approach — met by the session's native inbox, not a new watcher; the dissent is an open question |
| I7 | "read and act immediately" | IN | delta 4 (doorbell wakes an idle session); delta 6 (owner's Stop duty); delta 7 (coordinator) |
| I8 | earlier today: "i dont want them to interrupt work for asking" | IN | the loop never asks the operator (§ Personas step budget) |
| I9 | fleet's W-83ff5917 (worktree tests import main src) | IN | delta 5(c) — merged-tree tests pin the worktree's own src |
| I10 | the 08-26 ruling "No daemons, watchers" | IN (constraint) | § Constraints, § Rejected alternatives |

## Review — Pass Ledger

| Pass | seats · axes re-checked | counters | method | spec md5 (start → end) |
|---|---|---|---|---|
| Pass 1 | opus×1 (S-rules: the delta, invariants, approach) + sonnet×1 (S-ground: grounded facts) + sonnet×1 researcher (S-external: external quotes) · all axes | found: 29, new: 29, confirmed: 29, fixed: 29, unexecuted: 0, edits: 29 | method: citation + scratch-repo probes — full pass | d322a894 → 8a7bbcf3
| Pass 2 | opus×1 + sonnet×1 + researcher (the round-1 slice owners) · their ledgers over the delta rewrite + one hop | found: 12, new: 10, confirmed: 10, fixed: 10, unexecuted: 0, edits: 10 | method: re-derivation — 27 of 29 NOW_FALSE; 8 new inside the rewrite (push-before-CAS, stranded claims, relative common dir, stale snapshot, merge-tests source, evidence message, resume of a merged request, rebuild scope) | 8a7bbcf3 → 01f02dc0
| Pass 3 | opus×1 (S-rules) · the ten pass-2 claims + one hop | found: 4, new: 3, confirmed: 4, fixed: 4, unexecuted: 0, edits: 4 | method: re-derivation — 9 of 10 NOW_FALSE; O8 half-open; 3 new inside fix 2 (rejected-push resume, skipped-path index, stranded decidability); SCOPE GROWTH printed | 01f02dc0 → aefc7712
| Pass 4 | opus×1 (S-rules) · the four pass-3 fixes only (scope-growth remainder) | found: 3, new: 3, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation + scratch-repo probes — 4 of 4 NOW_FALSE; 3 new own-fix defects RECORDED to W-8a6a5644 (U4), never re-arming the stop | aefc7712 → aefc7712

Residuals carried: U2 (VS Code idle-session wake on `SendMessage`, probed in the plan's first ticket), U3 (the 3-day
escalation age, measured), U4 (W-8a6a5644, six routed residuals); the judge-panel split (2 Bell, 1 Watch) goes to the
operator's approval.
