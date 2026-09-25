# Plan — the work store as the one place every open obligation shows up

Status: IN-PROGRESS (2026-09-25, /fabrik-execute-plan — converged 2026-09-25 by /fabrik-plan-review, 3 passes, confirmed 24 → 4 → 0; see § Pass Ledger)
**Owner:** infra (the unnamed hub window)
Spec: docs/superpowers/specs/2026-09-25-work-store-single-tracker-design.md
Date: 2026-09-25

Built from the CONVERGED spec (D-417), whose design the operator approved: *"if you are 100% sure
proceed"* (D-418, 492a141a6). A spec-fed delta plan on the EXECUTED parent plan
`docs/development/plans/archived/2026-09-24-plan-2-work-tracking` (D-394): each ticket cites the spec
section it implements and restates nothing that section already settles.

## What we already agreed

- The goal and the personas' step budgets — spec § Goal; spec § Personas.
- One view, read live and never copied: mail and feedback-queue lines — spec § The delta D1.
- Taking an obligation creates its item; `close_linked`; no hand-made `mail`/`feedback` items; drift
  class 6 exempts them — spec § The delta D2.
- The four NEXT rules, the session's one `next` item, the 7-day close — spec § The delta D3.
- Every claim in the prompt, a crisp `ready` and `ready --all`, three `status` lines — spec § The delta D4.
- `drop --duplicate-of` and `alt_block_digests` — spec § The delta D5.
- The unnamed-window line — spec § The delta D6.
- The contract sentence in the three copies — spec § The delta D7.
- The measurement script `next_census.py` (spec § Review — Pass Ledger, RECORDED) and V1–V6 — spec §
  Validation.
- Rejected: copy every obligation, a NEXT gate, retiring or mirroring the register, moving mail into the
  store, one feedback item per row, any agent retiring a duplicate — spec § Rejected alternatives.
- Standing rulings carried: D-392 (no NEXT gate; the register stays), D-330 (no operator gate between
  review and execution once the design is approved).
- Decided HERE, at plan time, from the grounding (one row, D-419, minted with the plan's commit):
  - `on_harvest` learns whether the register accepted the NEXT through one keyword, `next_anchored`,
    which `thread_anchor.py` passes only when the loaded `work.py` has it (T05a, T05b): `work.py` cannot
    import `thread_anchor.py` (the dependency runs the other way, `scripts/thread_anchor.py:245-270`),
    and a synced `thread_anchor.py` can sit beside an older `work.py` for one sync cycle.
  - `kind: next` items belong to their session: they never appear in `ready`, `next` or the prompt's
    ready count (T02a) — otherwise another session would pick up this session's current thread.
  - The mail item is created and closed in `mail.py`'s CLI dispatch only, and only when the mailbox acted
    on is the cwd's own (T03): no in-repo code calls the library functions directly, and a cross-repo
    `--repo` claim belongs to the other repo's agents.
  - The feedback item is taken by `command_feedback_report.py --take <command>` and closed by
    `--mark-answered`; the depth comes from `queue_depths()`, one ledger read (T04).
  - The prompt keeps this session's `your claim` lines and adds one `on it:` line per OTHER session, so
    every live claim appears exactly once (T02b).
  - One classifier, `work.classify_next`, sorts every NEXT line for both the harvest and the census
    (T05a, T06): an operator decision anywhere in the line holds, whatever it names (spec § The delta D3
    rule 1), so the store and the measurement never disagree about a line.

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01 | Store: mail and feedback kinds, linked items, duplicate drop | — | ⛓️ | ✅ | 1a754bc96 |
| T04 | Feedback queues: depth and the taken item | T01 | ⚡ | ✅ | 659ea6a32 |
| T02a | The view: obligations, crisp ready, status lines | T01, T04 | ⛓️ | ⬜ | |
| T02b | The prompt block: obligations, others' claims, unnamed line | T02a | ⛓️ | ⬜ | |
| T03 | mail.py claim/ack/requeue create and close the mail item | T01 | ⚡ | ✅ | bc90eca8a |
| T05a | The harvest's NEXT rules in on_harvest | T02b | ⛓️ | ⬜ | |
| T05b | The harvest passes next_anchored; the V1 seam test | T05a | ⛓️ | ⬜ | |
| T06 | next_census.py: the NEXT measurement | T05a | ⚡ | ⬜ | |
| T07a | The contract sentence in all three copies | T05b | ⚡ | ⬜ | |
| T07b | The landing docs | T02b, T03, T04, T05b, T06 | ⚡ | ⬜ | |
| T08 | Integration: validation, hub adoption, announcement, receipt | T07a, T07b | ⛓️ | ⬜ | |

## Merge Order

1. T01
2. T04
3. T03
4. T02a
5. T02b
6. T05a
7. T05b
8. T06
9. T07a
10. T07b
11. T08

Merge Order is adoption order (spec § Cost): the store and its API first (T01), then its producers
(T04 feedback, T03 mail), then the view that reads them (T02a, T02b), then the harvest (T05a, T05b) and
the census that shares its classifier (T06), then the contracts and docs that describe the merged code
(T07a, T07b). `scripts/work.py` is one file, so T01 → T02a → T02b → T05a run in sequence;
`tests/test_work.py` (T02a), `tests/test_work_claims.py` (T02a, T02b, T05a) and `tests/test_thread_anchor.py`
(T02b, T05b) are each shared only along that Depends chain. No two Depends-unconnected tickets share a
path, so no `Serialized:` row is needed.

Breadth advisory (`check_ticket_breadth.py`, 7 of 11 tickets flagged at score 5–8): **kept, not split** (T02 was split into T02a and T02b for its READ budget, not for breadth).
- Its main suggestion is at most two behaviours per ticket. T01, T02a, T02b and T05a all edit
  `scripts/work.py` and already run in strict sequence; cutting them into about ten same-file tickets would pay a full
  review each and change no risk class.
- Its T04 suggestion peels `commands/_sources/fabrik-command-improve.md` off `scripts/command_feedback_report.py`.
  The source's two added lines name the `--take` flag the same ticket adds; split, the command would
  point at a flag that does not exist yet.
- Every ticket already owns one file's behaviour or one seam.

## Interfaces

- **T01 → T03, T04 — the linked-item API** in `scripts/work.py`:
  `open_linked(repo, *, kind, link: tuple[str, str], title: str, session: str, lock_timeout: float = HOOK_LOCK_TIMEOUT_S) -> str | None`
  and `close_linked(repo, *, kind, link: tuple[str, str], status: str, note: str, lock_timeout: float = HOOK_LOCK_TIMEOUT_S) -> str | None`;
  `kind` ∈ {`mail`, `feedback`}, `status` ∈ {`done`, `dropped`}; both return None on a store-less repo
  before touching anything and fail open. Seam tests: `tests/test_mail_items.py` (T03) and
  `tests/test_command_feedback_report.py` (T04), each driving the real `work.py` in a temp repo.
- **T04 → T02a — `queue_depths(ledger: Path | None = None) -> dict[str, int]`** in
  `scripts/command_feedback_report.py`, equal per command to `--queue`'s `N unanswered`, `{}` on any read
  failure. Seam test: `tests/test_work_view.py` (T02a) loads the real script by path against a temp ledger.
- **mail.py's `_parse` and `_ts_epoch` → T02a** (existing, `scripts/mail.py:1208-1226`, `:499`), loaded by
  path by the mail obligation reader. Seam test: `tests/test_work_view.py`.
- **T02a → T02b — `obligations(repo: Path) -> list[str]`** and `_ready_from`'s `kind: next` exclusion.
  Seam test: `tests/test_work_prompt.py` (T02b).
- **T05a → T05b — `on_harvest(..., next_anchored: bool = False)`**. Seam test: `tests/test_work_hook_seam.py`
  (T05b), the real Stop hook end to end (V1).
- **T05a → T06 — `classify_next(v: str) -> str`** (`"hold"` · `"names-item"` · `"free-text"`), loaded by
  path by the census. Seam test: `tests/test_next_census.py` (T06).
- **T06 → T08** — `next_census.py --since 7 --repo <path>` prints the V5 verdict line T08 embeds.

## Constraints Digest

The MUST-READ set, computed 2026-09-25 by `python3 scripts/review_rubric.py --changed` over this plan's
surface (FLOOR `core/10-python.md`; MATCHED `core/40-documentation.md`), plus the testing and subagent
packs every ticket's Behavior Contract and every fan-out obey. Each row is a verbatim rule and its bearing.

| Rule (verbatim) | file:line | Pack |
|---|---|---|
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:160` | core/10-python — every new `work.py`, `mail.py`, `command_feedback_report.py` and `next_census.py` function |
| **BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write | `.windsurf/rules/core/10-python.md:292` | core/10-python — the census and every hook path print to stdout/stderr only |
| **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** | `.windsurf/rules/core/45-testing-strategy.md:20` | core/45-testing-strategy — one test per G/W/T row, every ticket |
| **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` | core/45-testing-strategy — the claim rule (D3 rule 2), the duplicate match (D5), the mail close, the 7-day close |
| **Fenced code blocks only** — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:243` | core/40-documentation — `docs/reference/work-tracking.md` and the other landing docs (T07) |
| Every fan-out a command names runs native | `.windsurf/rules/core/62-using-subagents.md:38` | core/62-using-subagents — § Execution Discipline's dispatch policy |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — "every ticket, on the coder's return, runs `/fabrik-review` on its changed
  surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green."
  `scripts/work.py`, `scripts/mail.py`, `scripts/thread_anchor.py` and `templates/governance/CLAUDE.md`
  are governance-sync paths (`.pre-commit-config.yaml:164`), so T01, T02a, T02b, T03, T05a, T05b and T07a take
  the full `/fabrik-review`, closed BEFORE their merge (each distributes to ~46 repos AT MERGE); a
  plumbing commit is followed by a hand-run `bash scripts/governance_sync_postcommit.sh`. T04 and T06
  (hub-only scripts) and T07b (docs) take the full `/fabrik-review` too — T04 is a new mechanism (a
  flag) and the operator named this work.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182):
  `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py` then `python3 scripts/command_run.py dispatch --seats N`
  before each fan-out. Coders: Opus for T01, T02a, T02b, T05a, T05b (the lock-held harvest, the view's budget, the
  linked-item API — concurrency and hook seams) and T07a (a never-route governance path); Sonnet for T03,
  T04, T06, T07b. Haiku never codes. The Opus seat is the authoritative pass in every review; the
  orchestrator decides and merges.
- **Parallelism + merge** — T01 starts first. Once T01 is merged, T04 and T03 run in their own
  worktrees alongside each other (disjoint Touches). T02a starts once T01 and T04 are merged; T02b after
  T02a; T05a after T02b; T05b and T06 after T05a, together (disjoint Touches). T07a starts after T05b; T07b
  after T02b, T03, T04, T05b and T06 — the two run together. Every merge happens in the main checkout in
  `## Merge Order`; a finished ticket whose predecessor in that order is not yet merged waits. The dedupe
  point is the orchestrator's merge step: each coder's return is reviewed, then merged, one at a time.

## Behavior Contract

- **Given** an initialised temp store, **When** `work.py add --kind mail`, `--kind feedback` or `--kind next` runs, **Then** it exits 1 naming the kind and writes nothing, and an item added with `--link spec=…` still stores exactly the three standing link keys (spec § The delta D2)
- **Given** a temp store and a session id, **When** `open_linked` runs twice for the same mail link, **Then** one open `mail` item exists and that session holds its live claim; another session's call leaves the claim with its holder (spec § The delta D2)
- **Given** that item, **When** `close_linked(status="done")` runs, **Then** it is `done` with the note, its claim is ended, and `work.py sync --check` reports no class-6 drift for it (spec § The delta D2)
- **Given** no open item for a link, **When** `close_linked` runs, **Then** it returns None and writes nothing; and `done <id>` on a `mail` item is refused by hand (spec § The delta D2)
- **Given** two open awaiting items A and B created by the calling agent, **When** `drop A --duplicate-of B` runs, **Then** A is `dropped` with note `duplicate of B`, B carries A's block digest, and B's prompt line reads `(also asked as A)` (spec § The delta D5)
- **Given** that drop, **When** a later message whose DECISION block is A's wording is harvested, **Then** B gains the message digest and no new item is created (spec § Validation V6)
- **Given** an agent that is neither the distributor nor the creator of both items, or a caller with no agent name and no session, **When** it runs `drop A --duplicate-of B`, **Then** it is refused and nothing changes; `drop A --duplicate-of A` and a plain `drop` of an awaiting item stay refused (spec § Validation V6)
- **Given** a temp ledger holding verdict rows, none-verdict rows and answered rows for two commands, **When** `queue_depths` runs, **Then** each command's depth equals the `N unanswered` that `--queue <command>` prints for the same ledger, and a command with none left is absent (spec § The delta D1)
- **Given** an unreadable ledger path, **When** `queue_depths` runs, **Then** it returns an empty mapping and raises nothing (spec § The delta D1)
- **Given** a temp store and a session id, **When** `--take fabrik-review` runs twice, **Then** exactly one open `kind: feedback` item links `command=fabrik-review` and the session holds its live claim (spec § The delta D2)
- **Given** that item, **When** `--mark-answered fabrik-review` succeeds on a corpus commit, **Then** the item is `done` with the note naming the commit, and a `--mark-answered` that is refused leaves it open (spec § The delta D2)
- **Given** a repo with no store, **When** `--take` runs, **Then** it prints the no-store line, exits 0 and creates nothing (spec § Lifecycle — Degradation)
- **Given** an initialised temp store in the repo named by the mailbox and a session id, **When** `mail.py claim <id>` runs, **Then** one open `mail` item links that id, its title is the body's first line, and the session holds its claim (spec § Validation V2)
- **Given** that item, **When** `mail.py ack <id> --disposition done` runs, **Then** the item is `done` with note `mail ack: done`; and after a fresh claim, `mail.py requeue <id>` closes it `dropped` with note `requeued` (spec § Validation V2)
- **Given** a message never claimed, **When** `mail.py ack <id>` runs, **Then** no item is created and the ack behaves as before (spec § Validation V2)
- **Given** a claim with `--repo` naming another repo's mailbox, **When** it runs, **Then** no item is created in either store (spec § The delta D2)
- **Given** a repo with no store, or a `work.py` that fails to import, **When** claim, ack and requeue run, **Then** each prints and exits exactly as today and nothing is created (spec § Validation V2)
- **Given** a temp mail root whose mailbox (named by the main checkout) holds two `ack: required` messages, one `ack: no` and one malformed file, **When** `obligations` runs, **Then** it prints `mail: 2 need an answer` with the older one's age, and the malformed file is still in the inbox afterwards (spec § The delta D1)
- **Given** a repo with `commands/_sources/` and a temp ledger with three commands' unanswered rows, **When** `obligations` runs, **Then** the feedback line lists the three deepest with their `queue_depths` counts; a repo without `commands/_sources/` prints no feedback line (spec § The delta D1)
- **Given** a store with this session's claim, an owned item, an awaiting item and 14 other ready items, **When** `ready` runs, **Then** it prints them in that order with exactly 10 others and the `… and 4 more` line, and `ready --all` prints every ready item as before (spec § Validation V3)
- **Given** an open `kind: next` item, **When** `ready`, `ready --all` and `next` run, **Then** none lists it, and `status` does (spec § The delta D3)
- **Given** live claims held by two sessions, one of them holding six, and 51 open mail items created 15 days ago, **When** `status` runs, **Then** it prints one `CLAIMS` line per session with the six-claim session flagged `over 5`, and `AGED MAIL` with `over 50` (spec § The delta D4; spec § Lifecycle — Growth)
- **Given** a store with an `ack: required` mail, live claims held by this session and by two other sessions, and an open `kind: next` item, **When** `prompt_block` runs, **Then** it shows the mail line, this session's `your claim` lines, one `on it:` line per other session, and a ready count that leaves the `next` item out (spec § Validation V3)
- **Given** an unnamed window (no `CLAUDE_AGENT`, no binding), **When** `prompt_block` runs on an empty store, **Then** it returns exactly the no-agent-name line; with a name set, that line is absent and the empty store's block is `""` (spec § The delta D6)
- **Given** the hub-sized inbox and a 500-row ledger, **When** `prompt_block` is timed, **Then** it returns in under 0.5 s (spec § Validation V4)
- **Given** a session and three Stops with different free-text NEXT lines the register accepts, **When** each `on_harvest` runs with `next_anchored=True`, **Then** exactly one open `next` item exists for the session holding the last text and its time, and a repeated identical harvest writes nothing (spec § Validation V1)
- **Given** that `next` item and an open item X, **When** a harvest carries `NEXT: X — continue`, **Then** X's `next` is the line, the session holds X's live claim, and the `next` item is `dropped` with note `superseded` (spec § Validation V1)
- **Given** a NEXT whose first id is an awaiting item and whose second is an open item Y, **When** it is harvested, **Then** only Y is updated and claimed (spec § Validation V1)
- **Given** a NEXT naming only items another live session holds, or closed or awaiting ones, **When** it is harvested, **Then** no item is updated or claimed and the session's `next` item closes `superseded`; and `NEXT: awaiting operator decision — start X now` naming an open item X claims nothing (spec § Validation V1; spec § The delta D3 rule 1)
- **Given** `NEXT: operator decision: start X now` naming an open item X, **When** it is harvested, **Then** X is not updated or claimed (spec § Why this exists — the W-992909ca incident)
- **Given** another session's `next` item whose `next_at` is 8 days old and a second `next` item whose `next_at` is empty and `created` 8 days old, **When** any session's harvest runs, **Then** both are `dropped` with note `idle 7 days` (spec § Validation V1)
- **Given** the session id `nosession`, **When** a harvest carries a NEXT naming an open item, **Then** nothing is claimed and no `next` item is created (spec § The delta D3)
- **Given** a session whose last NEXT is accepted free text, **When** the harvest runs with `--repo`, **Then** `on_harvest` receives `next_anchored=True`, and a free text the register rejects receives `False` (spec § The delta D3)
- **Given** a `work.py` whose `on_harvest` has no `next_anchored` parameter, **When** the harvest runs on a message carrying a DECISION block, **Then** the decision item is still written and nothing raises (spec § Lifecycle — Degradation)
- **Given** the real Stop hook and an initialised temp repo, **When** one session stops three times on accepted free text, then on `NEXT: <open item id>`, then on `NEXT: operator decision: … <id>`, then on `NEXT: <awaiting id> <open id>`, then on a NEXT naming only an item another live session holds, and a second session stops once after an 8-day-old `next` item is planted, **Then** the store holds one superseded `next` item, the first named item and only the second id of the mixed line claimed by the first session, no item FILE changed by the operator-decision or other-held Stops, and the 8-day-old item closed by the second session's Stop (spec § Validation V1)
- **Given** the register's anchor state before this ticket, **When** the same harvests run, **Then** the session's anchors are identical to what the pre-ticket code writes (spec § Rejected alternatives — the register stays, D-392)
- **Given** a temp root holding two sessions' transcripts with NEXT lines of all five classes, one of them `operator decision: start W-00000000 now`, **When** `next_census.py --root <tmp> --since 7` runs, **Then** the classes line prints each count, the total and `over 2 sessions` exactly, with that line counted as `operator-decision` (spec § Why this exists)
- **Given** one session whose last NEXT of a turn is `phase B of the plan — docs/development/plans/x` and another whose free-text NEXT is `tidy the notes`, **When** the census runs, **Then** only the first is counted in the sessions line, under its repo (spec § The delta D3 measured volume)
- **Given** a transcript older than `--since` days and one unreadable line, **When** the census runs, **Then** the old file is not counted and the bad line is skipped without stopping the run (spec § Validation V5)
- **Given** a temp store with two open `next` items within 7 days, one live claim and two qualifying sessions for that repo, **When** the census runs with `--repo`, **Then** it prints `V5: PASS`; with no live claim it prints `V5: FAIL` naming the claims bound (spec § Validation V5)
- **Given** the hub contract and the template after this ticket, **When** `tests/test_work_contract_rule.py` runs, **Then** all three copies carry the new sentence at the same place and equal the pinned canonical text after the two sanctioned substitutions (spec § The delta D7)
- **Given** the pinned canonical text reverted to the old wording, **When** the same test runs, **Then** it fails on all three copies (spec § The delta D7)
- **Given** the merged CLI, **When** `tests/test_work_doc_verbs.py` runs, **Then** the reference doc's verb table equals the parser's verbs, `--duplicate-of` and `--all` included (spec § Documentation landing sites)
- **Given** the five edited docs, **When** `python3 scripts/enforcement/check_citations_resolve.py --changed` runs, **Then** it reports every `path:line` citation in the changed `docs/reference/` files as landing, with the examined count stated (spec § Documentation landing sites)
- **Given** every work ticket merged, **When** the whole-plan gate and `check_convergence.py` run, **Then** both are green and the receipt embeds the verbatim `"status": "success"` block
- **Given** the hub after adoption, **When** a real message is claimed and acked with `mail.py`, **Then** the receipt shows the mail item created and then closed `done`
- **Given** the hub after adoption, **When** `next_census.py --since 7 --repo /opt/fabrik` runs, **Then** the receipt embeds its output as the first V5 reading

## Global Constraints

- Python 3 stdlib only in every script this plan touches (`scripts/work.py`, `scripts/mail.py` and
  `scripts/thread_anchor.py` are fleet-synced; spec § Constraints); no new dependency and no
  dependency-file edit (CLAUDE.md § HARD STOPS).
- Every hook-side and `mail.py`-side store call fails OPEN (one stderr line, the caller's own result
  unchanged); every `work.py` CLI verb fails LOUD (spec § Lifecycle — Degradation).
- Hook budgets hold: the Stop harvest is killed at 5 s, a hook waits at most 2 s for the store lock
  (`HOOK_LOCK_TIMEOUT_S`, `scripts/work.py:83`), the prompt path's store work runs inside 3 s, and the
  prompt path takes the store lock only for the DECISION second chance (the parent plan's T04 rule
  A-O3). D1 and D4 only READ; every D3 write happens inside `on_harvest`, which already holds the lock.
- The thread-anchor register is never changed in behaviour (D-392): no anchor is added, re-keyed,
  capped or closed by this plan.
- No store is ever created implicitly: `init` stays the only writer of `.fabrik/work/config.json`, and
  a repo without a store behaves exactly as today for every new path.
- Every write goes through `_write_item`/`_write_claim` (a unique temp file plus `os.replace`); a file
  is read into a variable before it is opened for writing.
- Tests are hermetic: temp git repos, an explicit `env=` (the pattern at `tests/test_thread_anchor.py:215`),
  `FABRIK_MAIL_ROOT` and the feedback ledger pointed at temp paths — never the hub's own
  `.fabrik/work/`, `.git/fabrik-work/`, `/opt/fabrik-mail` or `~/.claude/state/`.
- Shared tree: three sessions and the daily pipeline share `/opt/fabrik`; stage explicit paths only,
  never stash, revert or `noqa` a sibling's WIP; shared-append ledgers (CHANGELOG, DECISIONS, INDEX,
  STRATEGIC_BACKLOG, LESSONS_LEARNT) go through the private-index recipe in ONE shell.
- 12-Factor: this is repo tooling, not a deployed service (spec § Shape / infra). XI — logs go to
  stdout/stderr only, no logfile; VIII — no daemon and no PID file (the 7-day `next` close runs at
  read-and-write time inside a harvest, no reaper); X — no backing service is introduced; III — config
  is the committed `config.json` plus env (`CLAUDE_AGENT`, `CLAUDE_CODE_SESSION_ID`,
  `FABRIK_MAIL_ROOT`), no secret anywhere; II, V, VI, VII, IX, XII — not applicable (no container, no
  port, no job queue, no migration).
- Never-Route: templates/governance/

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR) | typed stdlib code, no file logging | `.windsurf/rules/core/10-python.md:160`, `:292` |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | one test per behaviour, watched red first | `.windsurf/rules/core/45-testing-strategy.md:20`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED) | fenced code only; the doc landing sites | `.windsurf/rules/core/40-documentation.md:243` |
| `.windsurf/rules/core/62-using-subagents.md` | native seats, the dispatch step | `.windsurf/rules/core/62-using-subagents.md:38` |
| `fabrik-lib` | none fits — BUILD inside the hub scripts (spec § fabrik-lib verdict); not a candidate: fleet governance tooling | spec § fabrik-lib verdict |
| `agents-fabrik.md` infra invariants | none touched: no service, port, database or compose (spec § Shape / infra) | spec § Shape / infra |
| `specs/services/<id>.yaml` `shape.*` | none: not a deployed service | spec § Shape / infra |
| Frozen contracts (`docs/data-contract.md`, `docs/ui-design.md`) | none in the hub | — |
| Fleet-synced surfaces | `work.py`, `mail.py`, `thread_anchor.py` in `CORE_SCRIPTS`; the template and those three scripts are sync triggers; `command_feedback_report.py` is hub-only | `scripts/fabrik_synced_manifest.py:51`, `:62-63`; `.pre-commit-config.yaml:164` |

## File Scope (owned paths)

- scripts/work.py
- tests/test_work.py
- tests/test_work_claims.py
- tests/test_work_linked.py
- tests/test_work_view.py
- tests/test_work_prompt.py
- tests/test_work_harvest_rules.py
- scripts/mail.py
- tests/test_mail_items.py
- scripts/command_feedback_report.py
- tests/test_command_feedback_report.py
- commands/_sources/fabrik-command-improve.md
- scripts/thread_anchor.py
- tests/test_thread_anchor.py
- tests/test_work_hook_seam.py
- scripts/sysadmin/next_census.py
- tests/test_next_census.py
- templates/governance/CLAUDE.md
- CLAUDE.md
- tests/test_work_contract_rule.py
- docs/reference/work-tracking.md
- docs/reference/thread-anchors.md
- docs/reference/fabrik-mail.md
- docs/workstation/hooks-index.md
- docs/reference/command-run-protocol.md
- docs/development/reviews/2026-09-25-plan-1-work-store-single-tracker-review.md

## Evidence

Every ticket's primary path, grounded at HEAD 492a141a6 by five read-only seats (one Opus on the
harvest seam, four Sonnet — mail, feedback, contracts and docs, the view and the duplicate drop), each
claim re-read by the lead before it was cited:

- T01 `scripts/work.py:76` (`KINDS`), `:79` (`LINK_KEYS`), `:617-649` (`_new_item`, `_create_item`),
  `:1581` (drift class 6's `done` test), `:2454-2460` (`cmd_add` refusing `decision`), `:2524-2531`
  (`_refuse_closed`'s awaiting refusal), `:2561` (`_close`), `:2690-2713` (`cmd_drop`), `:2841-2859`
  (`_decision_index`, `by_block` keyed by `block_digest` alone), `:2906-2909` (a harvested creator is the
  agent name, or the session when unnamed or rescued).
- T02a `scripts/work.py:293` (`_worktrees`, main checkout first), `:672-688` (`_ready_from`, never reads
  `kind`), `:2503` (`cmd_ready`), `:2749-2776` (`cmd_status`); `scripts/mail.py:1208-1226` (`_parse`),
  `:499` (`_ts_epoch`), `:1509-1511` (`list_msgs` quarantines); `scripts/command_feedback_report.py:34-42`
  (the default ledger).
- T02b `scripts/work.py:3067-3103` (`prompt_block`); `scripts/thread_anchor.py:199`
  (`_PROMPT_STORE_BUDGET_S = 3.0`); `tests/test_work_claims.py:653`, `tests/test_thread_anchor.py:1212-1214`, `:1407`.
- T03 `scripts/mail.py:303-318` (`_current_repo`), `:1006` (`claim`), `:1088` (`ack`), `:1168`
  (`requeue`), `:1819-1826` (the CLI dispatch), `:440-466` (frontmatter keys — no subject);
  `docs/DECISIONS.md:417` (D-271).
- T04 `scripts/command_feedback_report.py:45` (`_rows`), `:1248-1300` (`queue`), `:327-404`
  (`mark_answered`), `:1524-1529` (no window with `--queue` alone); `commands/_sources/fabrik-command-improve.md:85`, `:229-248`.
- T05a `scripts/work.py:2990-3002` (`_set_next`, first id only), `:3005-3049` (`on_harvest`), `:945`
  (`_after_write` renews and prunes); `.claude/hooks/final_gate_stop.py:2663-2676` and `:2851` (two
  harvests per allowed Stop), `:2789-2797` (`nosession`).
- T05b `scripts/thread_anchor.py:465` (`_is_anchor`), `:535-600` (`cmd_harvest`), `:599`/`:612`
  (`matches[-1]` passed raw), `:245-270` (`_work()`).
- T06 new (`ls scripts/sysadmin/next_census.py` → no such file); the method is the session's measurement
  scripts, restated in T06 § Scope.
- T07a `CLAUDE.md:661`, `templates/governance/CLAUDE.md:650`, `:739`, `tests/test_work_contract_rule.py:61-70`.
- T07b `docs/reference/work-tracking.md:33`, `:86`, `:135`, `docs/reference/thread-anchors.md:87-97`,
  `docs/reference/fabrik-mail.md:61-84`, `docs/workstation/hooks-index.md:23`,
  `docs/reference/command-run-protocol.md:314-330`.

Today's prompt block over the hub store, timed (V4's baseline):

```
$ time python3 -c "import sys;sys.path.insert(0,'scripts');import work;print(len(work.prompt_block('.', 'x').splitlines()))"
5

real	0m0.056s
```

No active plan lock owns a path in File Scope (every lock under `.fabrik/plan-locks/` read; the one
`active` lock, `2026-09-05-plan-1-windowed-cost-sidecar`, owns none of these paths):

```
.fabrik/plan-locks/2026-09-05-plan-1-windowed-cost-sidecar.json active []
.fabrik/plan-locks/2026-09-24-plan-2-work-tracking.json released ['scripts/work.py', …]
```

The emit gate, run from the repo root, measures every ticket's READ set against its 262,144-byte budget:

```
$ python -m scripts.enforcement.check_plan_tickets --plan-dir docs/development/plans/2026-09-25-plan-1-work-store-single-tracker
✓ [plan_tickets] …/2026-09-25-plan-1-work-store-single-tracker: graded 10 ticket(s), 28 Touches path(s), 38 Context-Files entry(ies); READ budget measured against /opt/fabrik; 0 finding(s)
```

## Self-audit

**Grounding passes.** One fan-out, five seats, stamped first (`command_run.py dispatch --seats 5`).
What each found:
- **The harvest seam** (Opus): `on_harvest` receives the raw last NEXT and cannot tell whether the
  register accepted it; one Stop can harvest twice, on different texts (the plain harvest's `_text`, the decision harvest's `_turn_text` — the review corrected the seat's "same text"); an open `kind: next` item
  would appear in every session's `ready`; `_set_next` stops at the first id; the Stop hook's session may
  be `nosession`; six tests pin today's `_set_next` and prompt behaviour (named in T05a, T05b, T02b).
- **The mail seam**: nothing but `main()` claims, acks or requeues; a cross-repo `--repo` is legal and
  common; there is no subject header; `mail.py` imports nothing by path today.
- **The feedback seam**: `--queue` alone applies no window; `queue()`'s three exclusions; the
  success point of `mark_answered`; the report is hub-only.
- **Contracts and docs**: one hub copy, two template copies, pinned byte for byte by
  `tests/test_work_contract_rule.py`; the corpus-weight ratchet is advisory; the landing lines.
- **The view and the drop**: `_refuse_closed`'s refusal to branch around; `by_block` needs the alternate
  digests; a creator is either an agent name or a session id; `_agent_name()` costs one small file read.

**(a) Coverage** — every "What we already agreed" line maps to a ticket: D1 → T02a, T02b (+ T04's
`queue_depths`); D2 → T01 (store), T03 (mail), T04 (feedback); D3 → T05a, T05b; D4 → T02a, T02b; D5 → T01;
D6 → T02b; D7 → T07a; the census and V5 → T06, T08; V1 → T05a, T05b; V2 → T03; V3 → T02a, T02b; V4 → T02b; V6 → T01;
the docs → T07b; the adoption and I16's announcement → T08; the plan-time decisions → T02a, T02b, T03, T04,
T05a, T05b, T06. No gap.

**(b) Cross-ticket signatures** — `open_linked`/`close_linked` read identically in T01 (producer), T03
and T04 (consumers) and § Interfaces; `queue_depths` in T04 and T02a; `obligations` in T02a and T02b; `classify_next` in T05a and T06; `next_anchored` in T05a and T05b.

**Fixed point.** Reached by `/fabrik-plan-review` on 2026-09-25 — three passes, confirmed 24 → 4 → 0, the closing pass's md5 unchanged (§ Pass Ledger).

## Coverage Checklist

Rubric over the plan's File Scope (`python scripts/review_rubric.py --changed scripts/work.py tests/test_work.py tests/test_work_claims.py tests/test_work_linked.py tests/test_work_view.py tests/test_work_harvest_rules.py scripts/mail.py tests/test_mail_items.py scripts/command_feedback_report.py tests/test_command_feedback_report.py commands/_sources/fabrik-command-improve.md scripts/thread_anchor.py tests/test_thread_anchor.py tests/test_work_hook_seam.py scripts/sysadmin/next_census.py tests/test_next_census.py templates/governance/CLAUDE.md CLAUDE.md tests/test_work_contract_rule.py docs/reference/work-tracking.md docs/reference/thread-anchors.md docs/reference/fabrik-mail.md docs/workstation/hooks-index.md docs/reference/command-run-protocol.md docs/development/reviews/2026-09-25-plan-1-work-store-single-tracker-review.md`), verbatim:

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; TOOLING surface)

### core/10-python.md
**`uv`** is the mandated Python package manager. Never use raw `pip`, `pip install`, `poetry`, or `pipenv`.
- Dependencies live in `pyproject.toml` + `uv.lock`. Do not modify these files unless the ticket authorises it.
- its own reviewed commit, never as a side effect of unrelated work.
- The one RULE: use SQLAlchemy async consistently — never mix `async def` with sync `.query().all()` (the Banned table row; the full session pattern is `25-data-postgres.md`'s).
- The canonical `engine`, `async_session`, and `get_db` are defined in `src/database.py` — owned by `25-data-postgres.md`. Import from there, never redefine:
**Config convention:** apps read a complete `DATABASE_URL` (`postgresql+asyncpg://user:pass@host:port/db`) and `REDIS_URL` from env. Discrete `DB_HOST`/`DB_PORT`/`DB_NAME`/`DB_USER`/`DB_PASSWORD` for the app to assemble are **banned**. The env supplies the complete URL — `localhost` in WSL, `postgres-main` on VPS — so the host concern is an env-layer responsibility, never code logic. See `30-ops.md` compose template for how discrete vars are interpolated into `DATABASE_URL` at the compose level.
- volume** (`30-ops.md` § Volumes), never in `.tmp` and never in `/tmp`.
**GlitchTip discipline:** unhandled exceptions (FastAPI 500s) are auto-captured by GlitchTip with full stacktraces. In the `except Exception` branch, log a **short event name + correlation_id** — never `logger.exception()` (that duplicates the traceback in Loki AND GlitchTip). See `55-observability.md` § Error Reporting for the full rule.
**Note:** Use the scaffolded logger: `from {package}.logger import get_logger` (see `55-observability.md` § Pre-Scaffolded Logging). Do not use `structlog.get_logger()` directly or `logging.getLogger(__name__)`.
- **Never a bare `asyncio.create_task()`** — an unreferenced task is silently garbage-collected and its exceptions vanish. Hold the reference and await it, or use `asyncio.TaskGroup`.
- **`datetime.now(UTC)`, never `datetime.utcnow()`** — deprecated and naive; naive datetimes are a real cross-service defect class.
- Ruff's selected rule-sets MUST include `ASYNC` (blocking IO in async code — machine-enforces this pack's hardest-to-review rule), `B` (bugbear) and `S` (bandit) alongside the defaults; configured in `pyproject.toml`, emitted by the scaffolder.
- Production services run via `uvicorn` CLI in the Dockerfile, not `uvicorn.run()` in code. Base image is always the pinned Debian `-slim` variant on `linux/amd64` (the variant is pinned fleet-wide in `30-ops.md` § Container Base Images — change it THERE, never per-repo). Never use Alpine — musllinux wheels exist now (PEP 656) but coverage is still partial, source builds are dramatically slower, and musl's allocator/stack defaults degrade CPython; the trade never pays on this fleet.
- `uvicorn.run()` is for local development only. Never ship it in production code.
- a fleet scaling decision (more containers), never a per-app flag.
**BANNED: grouped/named env config sets.** 12F is explicit — *"env vars are granular controls, each fully orthogonal to other env vars"* — so a `config/production.yml`, a `settings.production` group, or a `config/{dev,staging,prod}.yaml` tree is a violation. Env vars are granular and set **per deploy**, never batched into a named "environment".
**BANNED:** `logging.FileHandler`, `logging.handlers.RotatingFileHandler`, `TimedRotatingFileHandler`, `loguru` file sinks, any `*.log` file write, any in-app log rotation/retention/cleanup. The app never decides where logs are stored or routed — Docker → Promtail → Loki does. Full rule: `55-observability.md` § Logs.
**Factor XII — Admin processes. NEVER migrate from app startup.**
**BANNED: `alembic upgrade head` in FastAPI's `lifespan`, in an `@app.on_event("startup")`, or as an import side-effect.** With more than one replica (or a restart storm) two containers run `upgrade head` **concurrently** → they race the Alembic version table → duplicate DDL → **wedged deploy**. Migrations are a **one-off admin process against the deployed release**: `docker compose run --rm <svc> alembic upgrade head` (see `30-ops.md` § Release & Admin Processes).

### 12-FACTOR (all twelve axes)
- I codebase: shared code → fabrik-lib, never two apps in one repo
- II deps: every shelled-out binary installed + pinned in the Dockerfile
- III config: granular env vars; no secrets in code; no grouped env sets
- IV backing services: swappable by DSN/config change only
- V build/release/run: releases immutable; never hot-patch a container
- VI processes: stateless; session state → redis-main; no sticky sessions
- VII port binding: bind in-container; Traefik routes; no host ports:
- VIII concurrency: scale out; never daemonize or write PID files
- IX disposability: SIGTERM returns in-flight jobs to the queue; jobs idempotent
- X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres
- XI logs: unbuffered stdout only; the app never writes/rotates a logfile
- XII admin: migrations/one-offs run against the deployed release, never startup

## MATCHED — packs whose globs hit the changed paths

### core/40-documentation.md  (hit: CLAUDE.md, commands/_sources/fabrik-command-improve.md, docs/development/reviews/2026-09-25-plan-1-work-store-single-tracker-review.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_command_feedback_report.py, tests/test_mail_items.py, tests/test_next_census.py)
- **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** — one high-value integration/E2E test per behavior, risk-ordered, TDD for the risky ones. Skip trivia (getters / framework glue / config): **lean-but-complete, NOT 100%-line-coverage dogma**. Do not chase line coverage — ensure every behavior has a test that would fail if that behavior regressed. (Cheap pool subagents can author the per-behavior tests — the suggest→curate→author→fix workflow in `62-using-subagents.md` § Dispatch policy + `~/.claude/commands/fabrik-review.md`.)
- **No cosmetic assertions**: never assert against CSS classes, Tailwind utility strings, pixel measurements, or snapshot hashes. Assert application state and user-visible outcomes only.
- **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED — either write it first and watch it fail, or (after the fact) neuter the fix/feature, prove the test goes red, then RESTORE and re-run to green. The neutered state is never staged, committed, or left in the tree. A green test never seen red is unverified — a suite can pass with its guard deleted.
- **Run tests**: `uv run pytest tests/` (never bare `pytest` — Fabrik uses `uv`) — **when the project has a `pyproject.toml`/`uv.lock`**. A `requirements.txt`-only project (no manifest) runs `.venv/bin/python -m pytest tests/` — the manifest clause chooses the RUNNER, it never disarms the mandate to run the suite (web-ecommerce-factory 01M1QEY5, 2026-09-05: the clause read as "does not apply here"). ⚠️ **Gate this on the manifest, because this line is FLOOR-injected into finder prompts and a vendored fabrik-lib MODULE has neither by design**: the module recipe ships `requirements.txt` (`fabrik-lib/README.md` § Creating a Reference Implementation), so `uv run` cannot resolve it and `python3 -m pytest` is the only thing that works. Telling a finder the sole working … (wrapped further — read the pack)
- **Zero-mock database policy**: never mock SQLAlchemy, SQLModel, or database sessions. All backend tests execute against a real PostgreSQL instance.
- **`ASGITransport` never runs lifespan** — anything the app initializes at startup (scaffolded apps are lifespan-based) silently does not exist in tests; wrap with `asgi-lifespan`'s `LifespanManager` when a test needs startup state.
- Use `structlog` in test helpers if logging is needed — never `print()`. See `55-observability.md`.
- **Never stub a server action from Playwright** — the server is the E2E boundary; stubbing belongs in the unit lane where the action is a plain function.
- Run Playwright against the PRODUCTION build (`next build && next start`), never the dev server.
- All locators must be **semantic**: `page.getByRole('button', { name: /submit/i })`. Never use CSS selectors or XPath.
- Launch Playwright's **bundled Chromium** (`channel: 'chromium'`) — stable Chrome/Edge removed the `--load-extension` / `--disable-extensions-except` side-load flags (Chrome 137/139), so those args only work under bundled Chromium, never installed stable Chrome.
- Run `@axe-core/playwright` with **`bypassCSP: true`** (the non-relaxable extension CSP otherwise makes axe throw on `chrome-extension://` pages); keep `@axe-core/playwright` a **dev-dependency only** (MPL-2.0 — never bundled into the shipped artifact). Gate bundle size with `size-limit` **per surface** (popup / side-panel / content-script). Full loop: `chrome-ext/70-chrome-ext.md` § Testing & UI Verification.
- Keep the generated types committed and re-generate on schema changes (`uv run python -c "import json; from <package>.main import app; print(json.dumps(app.openapi()))" > openapi.json` — the scaffold emits `src/<package>/main.py`, never a flat `src/main.py`, so `src.main` imports nothing).
**BANNED in tests:**
| A GUARD proven only by the ONE spelling of the defect you already fixed | Write the guard's subject five LEGITIMATE ways — five a DIFFERENT author would plausibly write, not five typos of yours — and count how many it still catches; one of five means it is keyed on your fix, not on the class — and one of five is the FLOOR of the failure, never its definition: four of five is a partial class and is reported as four of five. This is IN ADDITION to red-on-revert below, not a rival bar: that one proves the guard fires at all, this one proves it fires on the class. ⚠️ Cheapest ways to satisfy it WITHOUT the outcome (`CLAUDE.md` § UNIVERSAL governance markers, the entry whose anchor is **you get the behavior you measure** — search the ANCHOR, not the rule name: the project-facing contract lists that section by anchor alone and carries the name `cobra-effect` nowhere): (i) write five near-identical spellings and count 5/5; (ii) ship at 2/5 and REPORT it, needing no fabrication at all, in the hope that a reported count reads as a passed one — it does not: under 5/5 is a finding; (iii) claim the exercise and record nothing, since the five are never committed. So the bar is TWO things and needs both: **the five go IN the test file as executable CASES**, never a comment — a comment cannot go RED, so nothing can falsify it, and that is the objection, not that it records nothing — **and anything under 5/5 is a finding, not a pass**. ⚠️ Two paths this row does NOT close, stated rather than pretended away: you can shrink the SUBJECT until five legitimate spellings all land inside what the guard already catches (nothing is fabricated; the claim narrowed, not the guard), and an honest 4/5 — real information, 80% of the class — costs the author something to report, so the cheapest response to it is silence. Report the count you got either way — a 4/5 with the miss NAMED is a finding someone can act on, and a 5/5 nobody can execute is not a pass at all. Measured 4× in one day across 2 repos (01M1S4D78KRM0ZSYDNGTHS9HYQ), and once more the day this row landed: a contract-parity grader that read the LIVE file instead of the tree under test stayed green under the exact drift it existed to catch |
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | Watch it fail first, or neuter the change → prove red → restore → re-run green |
- [ ] Destructive DB tests call `require_throwaway(TEST_DATABASE_URL)` before connecting — never point them at a dev/shared DB.

# promote-to-check_*: 34 injected mandate(s) look deterministically greppable — their backtick literals, one line each (the full mandates are ABOVE, not repeated: re-emitting ~20 FLOOR lines verbatim doubled the rubric and got it skimmed — web-ecommerce-factory 01M1QEY5, 2026-09-05)
- `uv` `pip` `pip install` `poetry` `pipenv`
- `pyproject.toml` `uv.lock`
- `async def` `.query().all()` `25-data-postgres.md`
- `engine` `async_session` `get_db` `src/database.py` `25-data-postgres.md`
- `DATABASE_URL` `postgresql+asyncpg://user:pass@host:port/db` `REDIS_URL` `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` `DB_PASSWORD` `localhost` `postgres-main`
- `30-ops.md` `.tmp` `/tmp`
- `except Exception` `logger.exception()` `55-observability.md`
- `from {package}.logger import get_logger` `55-observability.md` `structlog.get_logger()` `logging.getLogger(__name__)`
- `asyncio.create_task()` `asyncio.TaskGroup`
- `datetime.now(UTC)` `datetime.utcnow()`
- `ASYNC` `B` `S` `pyproject.toml`
- `uvicorn` `uvicorn.run()` `-slim` `linux/amd64` `30-ops.md`
- `uvicorn.run()`
- `config/production.yml` `settings.production` `config/{dev,staging,prod}.yaml`
- `logging.FileHandler` `logging.handlers.RotatingFileHandler` `TimedRotatingFileHandler` `loguru` `*.log` `55-observability.md`
- `alembic upgrade head` `lifespan` `@app.on_event("startup")` `upgrade head` `docker compose run --rm <svc> alembic upgrade head` `30-ops.md`
- `docs/OPERATIONS.md` `docs/DEPLOYMENT.md`
- `scripts/doc_reconcile.py` `docs/QUICKSTART.md` `docs/CONFIGURATION.md` `docs/data-contract.md` `docs/SERVICES.md` `docs/OPERATIONS.md`
- `scripts/enforcement/_doc_registry.py::PROJECT_DOCS` `/fabrik-plan-after-chat` `Docs:`
- `Agent-Role: primary` `Co-Authored-By` `Co-Authored-By:` `Agent-Role:`
```

| # | Class | Verdict | Evidence (paths hunted) |
|---|---|---|---|
| 1 | FLOOR core/10-python — typed stdlib code, no file logging | CLEAN | every new function is typed in its ticket (`open_linked`, `close_linked`, `obligations`, `classify_next`, `queue_depths`); the census prints to stdout only; hunted T01–T06 |
| 2 | FLOOR 12-FACTOR (all twelve axes) — § Global Constraints | CLEAN | § Global Constraints states the axes for repo tooling; no daemon, logfile or backing service in any ticket |
| 3 | MATCHED core/40-documentation — the landing docs, fenced code only | FIXED | pass 1: T07b row 2 made provable by `check_citations_resolve.py --changed` (C-S1); T07a's substitution cite corrected to the two literal replacements (C-S3); T08's announcement quotes the merged sentence (C-S2) |
| 4 | MATCHED core/45-testing-strategy — a test per behaviour, seen red | FIXED | pass 1: the un-reddable class-6 row removed (A-O10); the pinned tests each change moves are named — `tests/test_work.py:258` kept by the extra-link-key rule (A-O1), five prompt assertions in T02b (A-O2, A-O19), `ready --mine` kept (A-O3); pass 2: the seam walk covers every V1 clause through the real hook (A-O15, A-O20) |
| 5 | fail-open vs fail-closed on every gate/guard — hooks and mail open, CLI loud | FIXED | pass 1: `open_linked`/`close_linked` inside `_hook_git_budget` and skipping closed ids (A-O14); the 7-day close judged per item (A-O12); the duplicate drop refuses an empty identity and `id == keep` (A-O13, A-O17) |
| 6 | cost / quota / limit edges — the 2 s lock inside the 5 s harvest, the 3 s prompt budget, the READ budgets, the 7-day and 6-day windows, the top-10 cut | FIXED | pass 1: T02 split into T02a/T02b for its READ budget (282,980 > 262,144 bytes); the prompt budget cited at `scripts/thread_anchor.py:199` (A-O11); the emit gate re-run after every batch, 0 findings |
| 7 | boundary / sentinel / prefix — `W-` ids, `nosession`, the rule-1 prefixes, the mailbox name, `ack: required` | FIXED | pass 1: one classifier `classify_next` for the harvest and the census, an operator decision anywhere holds (A-O9, B-S2); `[:300]` matches the register's judged string (A-O8); `mail._ts_epoch` for the oldest mail (A-O16) |
| 8 | behaviour without a test — every G/W/T row names its grader | FIXED | the 47-row roll-up regenerated from the tickets after every batch and graded by the emit gate (set-equality); pass 1 moved the V4 and prompt rows into T02b with their tests |

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | set md5 (start → end) |
|---:|---|---|---|---|
| Pass 1 | opus×1 (A: the spine's rule/grammar sections + T01, T02, T05a, T05b) + sonnet×1 (B: T03, T04, T06 + Board, Merge Order, Context Ledger) + sonnet×1 (C: T07a, T07b, T08 + File Scope, Evidence, Self-audit, Checklist, Residuals, spec coverage) + 3 refuters · all classes | found: 24, new: 24, confirmed: 24, fixed: 24, unexecuted: 0, edits: 24 | method: citation — the full partitioned pass (workflow wf_03a21eb6-f0f); 23 seat candidates each executed by its slice refuter and re-run by the orchestrator at the pin (`git show 5546aa330:…` for `tests/test_work.py:258`, `tests/test_thread_anchor.py:1212-1214`, `:1407`, `.claude/hooks/final_gate_stop.py:2828-2853`, `scripts/thread_anchor.py:199`, `scripts/command_feedback_report.py:1524-1529`, `tests/test_work_contract_rule.py:73-78`), plus 1 of the orchestrator's own (the spec's third growth trigger); T02 split into T02a/T02b on the READ budget; emit gate 11 tickets, 32 Touches, 42 Context Files, 0 findings | 5b1cee15 → b2532ca0 |
| Pass 2 | opus×1 (A) + sonnet×1 (B) + sonnet×1 (C), the round-1 slice owners, + refuter on A · their ledgers over the fix diff plus one hop | found: 4, new: 3, confirmed: 4, fixed: 4, unexecuted: 0, edits: 5 | method: re-derivation — 21 of 22 ledger claims re-executed NOW_FALSE, A-O15 STILL_TRUE; 3 new, all inside pass 1's own fix hunks (own-fix 3 of 4): a fifth moved assertion `tests/test_work_claims.py:663-664` (A-O19), the 8-day item's planting moment (A-O20), `_close`'s write order stated backwards (A-O21, re-read at `scripts/work.py:2561-2575`); slices B and C closed | b2532ca0 → 1741b49b |
| Pass 3 | opus×1 (A), the round-1 owner, + refuter · the four open claims of slice A over the pass-2 fix hunks plus one hop | found: 1, new: 1, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — 4 of 4 ledger claims re-executed NOW_FALSE; A-O22 (the unnamed line before a store-less return) REFUTED by the executed read of `scripts/work.py:3070-3074` (the early `return ""` precedes any new line); standing clean since pass 1–2: every class of the ledger | 1741b49b → 1741b49b ✓ → **CONVERGED** |

RECORDED, not counted (outside the fix hunks), each with its destination:
- T05b step 3 leaves the executor to choose which session holds the other-held claim and what the second session's Stop ends on — self-service for the T05b coder, graded by T05b's `/fabrik-review`.
- T02b step 2 introduces its five moved assertions as changes of "the unnamed-window line", while `tests/test_work_claims.py:663-664` moves because of the `on it:` line — wording only; the T02b coder's review.

## Residual unknowns

**Resolved:**
- Whether `on_harvest` can tell an accepted NEXT: it cannot today; the `next_anchored` keyword carries it (T05a, T05b).
- Which store a mail item lands in: the cwd's, only when its mailbox is the one acted on (T03).
- Whether the feedback depth can be read without a subprocess per command: `queue_depths()`, one ledger read (T04).
- Whether the contract sentence breaks a pinned test: `tests/test_work_contract_rule.py:61-70` is updated in the same ticket (T07a).

**Open, each with its resolution step:**
- **Whether `_is_anchor` is the right filter for the session's `next` item** (spec § Open unknowns). Resolution: the V5 reading two weeks after hub adoption, `next_census.py --since 7 --repo /opt/fabrik`, a work item T08 creates for intel, due 2026-10-09.
- **The hub windows are unnamed**, so owners and `ready`'s "owned by this agent" section resolve to nothing until each is named (`CLAUDE_AGENT` at launch, or `python3 scripts/whoami_agent.py --as <name>`). The unnamed-window line (T02b) makes it visible; naming is the operator's action, named again in T08's announcement.
