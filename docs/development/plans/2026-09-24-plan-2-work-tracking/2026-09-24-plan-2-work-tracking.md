# Plan — work tracking: one open-work record per repo, shared by its three agents

Status: IN-PROGRESS
**Owner:** infra (the unnamed hub window)
Spec: docs/superpowers/specs/2026-09-24-work-tracking-design.md
Date: 2026-09-24

Built from the CONVERGED spec (D-394), whose design the operator approved with intel as the hub's
distributor: *"approved."* (D-395, 105e2d630). A spec-fed plan: each ticket cites the spec section
it implements and restates nothing that section already settles.

## What we already agreed

- The goal and the two kinds of state — spec § Goal; spec § Two kinds of state, two homes.
- The durable item, its fields and its never-delete rule — spec § The durable item.
- Identity, the one store lock, the lease with its fencing token — spec § Identity, the lock, the lease.
- The CLI verbs — spec § The CLI — `scripts/work.py` (stdlib only, fleet-synced).
- The distributor — spec § Ownership and the distributor; **intel distributes in the hub** (D-395).
- DECISION blocks become awaiting items, the second chance, the unfolded prompt block — spec § NEXT,
  DECISION blocks and the register, with the RECORDED residue from spec § Review — Pass Ledger (the second
  chance matches by the MESSAGE digest; T04 step 4).
- Spec and plan state is derived, drift classes 1–8, the blocking rule — spec § Spec and plan state is
  derived, never copied.
- The backlog becomes a rendered view — spec § The backlog becomes a view.
- The native Task list is an in-session checklist, never the record — spec § The native Task list; D-392.
- Rejected: B, A-full, C, fabrik-lib `job-queue/`, the Task list as the record, stored claims, one
  append-only file, a `~/.claude/state/` store, a reaper cron, an `await` verb, any NEXT gate — spec §
  Rejected alternatives.
- The operator's standing rulings: *"1 yes we can enable task tools. 2 if you refuse next:none if there
  is nothing to be done, agent will start making up unnecessary tasks in next field, this is not what we
  want. we want to keep track of next items properly. 3 no i will not do that"* (D-392).
- Decided HERE, at plan time (rows minted with the plan's commit):
  - V2 is re-derived at run time by an independent reader, not checked against the spec's frozen
    "253 open, 36 resolved": two grounding seats could not reproduce that snapshot (287–293 candidate
    rows), and the backlog grows daily (T03).
  - The Task-tools env rides in the fleet-synced `.claude/settings.json`, inside the tree, not a
    box-level write: a headless probe at plan time proved a project-level `env` block overrides a
    parent `CLAUDE_CODE_ENABLE_TASKS=0` (T07, § Evidence).
  - With a store present, WHERE YOU ARE lists the awaiting decision from the store, and the session
    slot's OPEN DECISION line prints only when the store does not hold that message's item — a repo
    with no store, or a Stop-side write that failed before a compaction (T04 step 5; refined in this
    review from D-398's "only in a repo with no store", which would hide a decision whose item write
    failed — the superseding row is minted with the CONVERGED flip).
  - `tasks/` joins `_SHARED_DIR_LINKS` and `_SHARED_DIR_MKDIR` in `claude_rotate.py`; linking the
    existing account dirs is an operator action (T10).

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | Store core: init, items, lock, add/assign/ready/next | — | ⛓️ | ✅ | 8912d0a21 |
| T01b | Claims, leases, closing verbs, hook-facing API | T01a | ⛓️ | 🔵 | |
| T02 | status, sync --check, readings, drift classes | T01b | ⛓️ | ⬜ | |
| T03 | migrate-backlog and render | T02 | ⛓️ | ⬜ | |
| T04 | thread_anchor.py: decision items, unfolded block, renewal | T01b | ⚡ | ⬜ | |
| T05 | Stop hook passes --repo; the V1 seam test | T04 | ⛓️ | ⬜ | |
| T06 | Completion gate's advisory sync row | T02 | ⚡ | ⬜ | |
| T07 | Distribution: manifest, sync filter, Task-tools env | T03 | ⛓️ | ⬜ | |
| T08 | Both contracts carry the work-items rule | T04, T05, T06 | ⚡ | ⬜ | |
| T09 | Reference doc and the four stale docs | T03, T04, T05, T06 | ⚡ | ⬜ | |
| T10 | Integration: tasks link, hub adoption, receipt | T07, T08, T09 | ⛓️ | ⬜ | |

## Merge Order

1. T01a
2. T01b
3. T02
4. T03
5. T07
6. T04
7. T05
8. T06
9. T08
10. T09
11. T10

Merge Order is adoption order (spec § Cost): the complete store and CLI reach the fleet (T07) before the
hooks call them (T04, T05), and the contracts and docs follow the code they describe. T04 may be
dispatched as soon as T01b is merged and runs alongside T02/T03, but it MERGES only after T07. No two
Depends-unconnected tickets share a path, so no `Serialized:` row is needed.

Breadth advisory (`check_ticket_breadth.py`, 10 of 11 tickets flagged at score 5–8): **kept, not split.**
- Its main suggestion is at most two behaviours per ticket. That would cut the four `scripts/work.py` tickets into about a dozen, each editing the same file in strict sequence and each paying a full review.
- Its T07 suggestion is to peel `.claude/settings.json` and `.pre-commit-config.yaml` off `fabrik_synced_manifest.py`. That would separate three small edits that ship one distribution invariant together.
- Every ticket already owns one file or one invariant.

## Interfaces

- **T01b → T04, T05 — the hook-facing API** in `scripts/work.py`: `repo_root(path) -> Path | None`,
  `has_store(repo) -> bool`,
  `on_harvest(repo, *, session, block=None, msg_digest=None, next_text=None, lock_timeout=2.0) -> str | None`
  (the Stop harvest's one call: decision item first, then an item's `next`, then claim renewal, under
  one lock), `ensure_decision_item(repo, *, block, msg_digest, session, lock_timeout=2.0) -> str | None`
  (one item), `ensure_decision_items(repo, entries, lock_timeout=2.0) -> list[str] | None` (the second
  chance, every missing slot under one lock), `has_msg_digest(repo, msg_digest) -> bool`,
  `prompt_block(repo, session) -> str`;
  every one returns its empty value on a repo with no store before touching anything, and fails open.
  Seam tests:
  `tests/test_thread_anchor.py` (T04, in-process via the real script) and `tests/test_work_hook_seam.py`
  (T05, the real Stop hook end to end).
- **T04 → T05 — `thread_anchor.py harvest --repo <root>`**, the slot's `repo` field, and `line --hook`
  printing `prompt_block` first. Seam test: `tests/test_work_hook_seam.py` (T05).
- **T02 → T06 — `work.py sync --check`'s exit contract:** 0 when there is no store or the repo is not
  yet blocking; non-zero only when blocking and classes 2–6 drift. Seam test:
  `tests/test_final_gate_work_row.py` (T06).
- **T03 → T10 — `migrate-backlog` + `render`** on the hub backlog; checked by T10's V2 reading in the receipt.
- **T07 → T10 — `CORE_SCRIPTS` lists `work.py`**; the fleet broadcast in T10 relies on it having synced.

## Constraints Digest

Every MATCHED pack from the rubric run below, each with a verbatim rule and its bearing.

| Rule (verbatim) | file:line | Pack |
|---|---|---|
| Use type hints for all function signatures | `.windsurf/rules/core/10-python.md:160` | core/10-python — every `work.py` function and the T01b API |
| **Behavior Contract**: every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one** | `.windsurf/rules/core/45-testing-strategy.md:20` | core/45-testing-strategy — one test per G/W/T row, every ticket |
| **Watched-fail-first** (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract): a non-trivial behavior's test proves something only if it has been SEEN RED | `.windsurf/rules/core/45-testing-strategy.md:22` | core/45-testing-strategy — claim atomicity, lease expiry, fencing, evidence refusal, the second chance |
| the computable parts regenerate mechanically | `.windsurf/rules/core/40-documentation.md:55` | core/40-documentation — the BACKLOG block is `render`'s alone (T03) |
| **Fenced code blocks only** — never indented code (AI treats it inconsistently) | `.windsurf/rules/core/40-documentation.md:243` | core/40-documentation — `docs/reference/work-tracking.md` (T09) |
| Every fan-out a command names runs native | `.windsurf/rules/core/62-using-subagents.md:38` | core/62-using-subagents — § Execution Discipline's dispatch policy; intel's charter (T09) |
| Pinning an old Claude model ID (or copying one from an old doc) instead of selecting by alias. | `.windsurf/rules/ai/00-ai-model-selection.md:166` | ai/00-ai-model-selection — matched through `docs/reference/agents/intel.md` (T09): the charter edit names no model ID |

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — "every ticket, on the coder's return, runs `/fabrik-review` on its changed
  surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green."
  Every ticket here is heavy by the lane table (a governance-sync path, a hook, the gate, or a new
  mechanism with concurrency), so the review is the full `/fabrik-review`, never the scoped one. A
  governance-sync merge (T04, T05, T06, T07, T08) distributes to ~46 repos AT MERGE, so its review
  closes before the merge, and a plumbing commit is followed by a hand-run
  `bash scripts/governance_sync_postcommit.sh`.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182):
  `scripts/sysadmin/dispatch_headroom.py` then `scripts/command_run.py dispatch --seats N` before each fan-out. Coders: Opus for
  the `native` and `never-route` tickets that carry concurrency or hook design (T01a, T01b, T04, T05, T06,
  T08, T10); Sonnet for T02, T03, T07, T09. Haiku never codes. The Opus seat is the authoritative pass in
  every review; the orchestrator decides and merges.
- **Parallelism + merge** — `scripts/work.py` is one file, so T01a → T01b → T02 → T03 run in sequence.
  Once T01b is merged, T04 runs alongside T02 and T03 in its own worktree, and T06 alongside T03 once T02
  is merged. T08 and T09 fan out together once T04, T05 and T06 are merged. Every merge happens in the
  main checkout in `## Merge Order`; a finished ticket whose predecessor in that order is not yet merged
  waits. The dedupe point is the orchestrator's merge step: each coder's return is reviewed, then merged,
  one at a time.

## Behavior Contract

- **Given** a git repo with no `.fabrik/work/`, **When** any verb other than `init` runs, **Then** it exits non-zero naming `init` and creates nothing, in the tree or in the git common directory (spec § The CLI)
- **Given** a repo after `init --distributor intel`, **When** `add --kind backlog --title T` runs twice with the same title, **Then** two distinct `W-` + 8-hex item files exist, each pretty-printed with sorted keys, status `open`, priority 2 (spec § The durable item)
- **Given** an initialised repo, **When** `add --kind decision` runs, **Then** it is refused with a message naming DECISION blocks and no file is written (spec § The CLI)
- **Given** another process holds the store lock, **When** a CLI verb needs it, **Then** the verb waits 10 s, exits non-zero with a named message, writes nothing, and one reading with the wait's duration lands in `readings.jsonl` (spec § Identity, the lock, the lease)
- **Given** items of priority 0 to 3 of different ages, some blocked by an open item, **When** `ready` runs, **Then** it lists only open unblocked items, ordered by priority then age (spec § The CLI)
- **Given** an item owned by `infra` and an unassigned one, **When** `ready --mine` runs with `CLAUDE_AGENT=infra`, **Then** the owned item is listed first, then the unassigned one, and `next` prints the first of them (spec § The CLI)
- **Given** a config naming distributor `intel`, **When** `assign <id> --owner fleet` runs with `CLAUDE_AGENT` unset or not `intel`, **Then** it is refused; with `CLAUDE_AGENT=intel` it sets the owner; with an empty `distributor` any agent may assign (spec § Ownership and the distributor)
- **Given** an initialised repo with no item `W-00000000`, **When** `assign W-00000000 --owner fleet` runs, **Then** it exits non-zero naming the id and the tree it looked in, and no file changes in the tree or the git common directory (spec § The CLI)
- **Given** one ready item, **When** three processes run `claim <id>` at the same instant, **Then** exactly one exits 0 and holds the claim, and the other two exit non-zero naming the holder (spec § Validation V3)
- **Given** a claim whose lease has passed, **When** `ready` runs, **Then** the item is listed as ready, and a new `claim` succeeds with a higher token; a `claim` by the live holder, or an `on_harvest` for its session, pushes the lease's end later (spec § Validation V3)
- **Given** session A's claim expired and session B took it over, **When** session A runs `done <id> --evidence <sha>`, **Then** it is refused for a token mismatch and the item is unchanged (spec § Validation V3)
- **Given** a linked worktree of the repo, **When** a claim is made from the worktree, **Then** `ready` in the main checkout stops listing that item at once (spec § Validation V3)
- **Given** an item claimed from a linked worktree, **When** `done` runs there with no evidence, with a SHA that does not resolve, or with a commit whose message does not name the id, **Then** each is refused; with a commit naming the id it succeeds and writes a closed marker, and `ready` in the MAIN checkout — whose own copy of the item is still `open` — no longer lists it (spec § Validation V4)
- **Given** an `awaiting-operator` item, **When** `drop`, `done` or `claim` runs on it, **Then** each is refused; **When** `answer <id> --note "<words>" --decision D-001` runs, **Then** the item is `done` with the note and the decision link, `docs/DECISIONS.md` is untouched, and its closed marker stops a stale copy of the item in a linked worktree from printing there (spec § Cobra)
- **Given** an item assigned to `fleet` and a distributor `intel`, **When** `drop <id> --why x` runs as `infra`, **Then** it is refused; as `fleet` or `intel` it succeeds and the reason is kept in `note` (spec § The CLI)
- **Given** a store and a DECISION block, **When** `ensure_decision_item` runs with a new message digest, then the same digest, then a new digest while the item is open, then a new digest after the item was answered, **Then** it creates one item, does nothing, adds the second digest to the same item, and creates a second item; `ensure_decision_items` with two missing entries creates both under one lock; on a repo with no store, `on_harvest`, `ensure_decision_item`, `ensure_decision_items` and `prompt_block` return their empty values and nothing is created in the tree or the git common directory (spec § NEXT, DECISION blocks and the register)
- **Given** a fixture repo with one spec and one plan per drift class 1–8 plus one clean spec and plan, **When** `status` runs, **Then** each class lists exactly its fixture paths and the clean ones appear in none (spec § Spec and plan state is derived, never copied)
- **Given** plan spines with `Status: IN_PROGRESS`, `COMPLETE`, `PLANNED` and `WEIRD`, **When** `status` runs, **Then** the first three are read as `IN-PROGRESS`, `EXECUTED` and `DRAFT`, and only `WEIRD` is listed under class 8 (spec § Spec and plan state is derived, never copied)
- **Given** a `done` item from the last 14 days whose evidence SHA does not name it, a `legacy` one, and a closed marker older than 14 days whose item is still open, **When** `status` runs, **Then** the first and the marker are class 6 and the legacy item is not (spec § Spec and plan state is derived, never copied)
- **Given** an initialised repo with class-3 drift and no `migrated_at`, **When** `sync --check` runs, **Then** it exits 0, prints the drift, and appends one reading line holding the per-class counts (spec § Spec and plan state is derived, never copied)
- **Given** `migrated_at` and readings clean for classes 2–6 on 7 consecutive days after it, **When** `sync --check` runs on class-3 drift, **Then** it exits non-zero; with only 6 such days it exits 0 (spec § Lifecycle)
- **Given** a repo with no `.fabrik/work/`, **When** `sync --check` runs, **Then** it prints one line, exits 0 and creates nothing (spec § The CLI)
- **Given** one committed item and one untracked item file, **When** `status` runs, **Then** only the untracked one is listed as uncommitted (spec § Constraints — shared tree)
- **Given** a fixture backlog with one row of every shape above, open and resolved, **When** `migrate-backlog` runs, **Then** every row becomes exactly one item, resolved rows are `done` with `legacy: true`, the others `open` with the owner from the tag, and each row's full text is kept (spec § The backlog becomes a view)
- **Given** a row no shape matches, **When** `migrate-backlog` runs, **Then** it becomes an item with an empty owner and the raw text kept, and the run's output lists it for the distributor (spec § The backlog becomes a view)
- **Given** a migrated store, **When** `migrate-backlog` runs again, **Then** it creates no item (spec § The backlog becomes a view)
- **Given** a copy of the hub's `docs/STRATEGIC_BACKLOG.md`, **When** `migrate-backlog` then `render` run, **Then** the item count and the open/done split equal what the test's own independent reader counts in that copy, and every source row's text appears in its item (spec § Validation V2)
- **Given** a rendered backlog, **When** `render` runs again, **Then** the file is byte-identical, and hand-written text above and below the block is untouched (spec § The backlog becomes a view)
- **Given** an initialised temp repo, **When** `harvest --decision-ok --repo <repo>` runs on a message with a DECISION block, **Then** one `awaiting-operator` item exists holding the message digest and the slot stores `repo` (spec § NEXT, DECISION blocks and the register)
- **Given** that item, **When** a second message carrying a different DECISION block is harvested the same way, **Then** a second item exists and the first is unchanged (spec § Validation V1)
- **Given** a slot stored with `repo` whose Stop-side item write failed, **When** the next UserPromptSubmit `line --hook` runs — in that session, or in another session after the first one ended — **Then** the item is created from the slot; if that write fails too, the prompt output carries one warning line, and a repo with no store prints none (spec § NEXT, DECISION blocks and the register)
- **Given** a block answered and then re-asked word for word in a new message whose Stop-side write failed, **When** the next UserPromptSubmit runs, **Then** a new awaiting item is created, matched by the message digest (spec § Review — Pass Ledger, RECORDED)
- **Given** two awaiting items created by two different sessions, **When** a third session's `line --hook` runs on UserPromptSubmit and on SessionStart `source=compact`, **Then** both questions print at the top of its output, unfolded (spec § Validation V1)
- **Given** a claim held by the session, **When** a Stop harvest runs with `--repo` and the message has no `NEXT:` line, **Then** the claim's lease is renewed (spec § Identity, the lock, the lease)
- **Given** no `--repo` and no payload `cwd`, **When** any `thread_anchor.py` command runs from inside an initialised repo, **Then** no store is read or written (grounding risk 2)
- **Given** an open item `W-…`, **When** a Stop harvest with `--repo` runs on a message whose last `NEXT:` names that id, **Then** the item's `next` field holds that line (spec § NEXT, DECISION blocks and the register, item 3)
- **Given** an initialised temp repo, **When** the real Stop hook runs on a final message ending in a valid DECISION block, **Then** the repo's store holds one `awaiting-operator` item for it (spec § Validation V1)
- **Given** that item, **When** a second Stop from another session ends on a different valid DECISION block, **Then** the store holds two awaiting items (spec § Validation V1)
- **Given** the two items, **When** a third session's `thread_anchor.py line --hook` runs on UserPromptSubmit and then on SessionStart `source=compact`, **Then** both questions print, unfolded, in both outputs, and they still print after that session's own state file is deleted (spec § Validation V1)
- **Given** a claim held by a session, **When** the Stop hook runs for that session on a message with no DECISION block, **Then** the claim's lease is renewed (spec § Identity, the lock, the lease)
- **Given** a repo whose `scripts/thread_anchor.py` does not know `--repo`, or a Stop payload with no `cwd`, **When** the Stop hook runs, **Then** the harvest argv carries no `--repo` and the Stop is allowed as before (spec § Lifecycle — Degradation)
- **Given** a repo with an initialised store and class-3 drift, not yet blocking, **When** the Tier-2 gate runs, **Then** the `Work items (sync)` row passes and its output names the drift (spec § Spec and plan state is derived, never copied)
- **Given** a blocking repo with class-3 drift, **When** the Tier-2 gate runs, **Then** the row fails and the gate status is not success (spec § Lifecycle)
- **Given** a repo with no `.fabrik/work/`, **When** the Tier-2 gate runs, **Then** the row passes with the one-line no-store message (spec § The CLI)
- **Given** the merged gate, **When** `tests/test_final_gate_tier_counts.py` runs, **Then** the instrumented Tier-2 count equals the declared `tier2` (docs/workflows/FINAL_GATE_WORKFLOW.md:144)
- **Given** the merged manifest, **When** `CORE_SCRIPTS` and the generated gitignore block are read, **Then** both name `work.py` and `thread_anchor.py` together (spec § The CLI)
- **Given** the merged `.pre-commit-config.yaml`, **When** its `governance-sync` files regex is applied, **Then** it matches `scripts/work.py` and still matches `scripts/thread_anchor.py`, and it matches no other path it did not match before, over every path `git ls-files` lists (spec § Shape / infra)
- **Given** the merged `.claude/settings.json`, **When** it is parsed, **Then** its `env` sets `CLAUDE_CODE_ENABLE_TASKS` and `CLAUDE_CODE_ENABLE_TODO_TOOLS` to `"1"` and every existing key is unchanged (spec § The native Task list)
- **Given** the merged contracts, **When** each `## ⚠️ FINAL OUTPUT` section is isolated (one in the hub, two in the template), **Then** each holds the work-items paragraph exactly once, after the `DONE:`/`NEXT:` discipline paragraph (spec § Documentation landing sites)
- **Given** the paragraph, **When** its text is compared across the three copies, **Then** they are identical except the template's `hub D-392` for the hub's `D-392` (spec § Documentation landing sites)
- **Given** the merged contracts, **When** the governance parity suite runs, **Then** it stays green (tests/test_governance_template_split.py:1122)
- **Given** the merged code, **When** `python3 scripts/render_doc_script_links.py --check` runs, **Then** it exits 0 and `docs/reference/work-tracking.md`'s `## Related scripts` block names `scripts/work.py` (spec § Documentation landing sites)
- **Given** the merged docs, **When** every verb named in `docs/reference/work-tracking.md` is run with `--help` against `scripts/work.py`, **Then** each exists, and the doc names every verb `work.py --help` lists (spec § The CLI)
- **Given** a scaffolded fleet dir, **When** `_scaffold_dir` runs, **Then** `tasks` is a symlink to the canonical `tasks/` like `sessions`, and a real `tasks/` directory in its place is reported, never touched (spec § The native Task list)
- **Given** the hub after adoption, **When** `work.py status` runs, **Then** each drift class lists exactly the paths an independent reader of the hub tree selects (spec § Validation V5)
- **Given** the hub after adoption, **When** the migrated items are counted, **Then** they equal the independent reader's open and resolved row counts for the pre-migration backlog (spec § Validation V2)

## Global Constraints

- Python 3 stdlib only in `scripts/work.py` (spec § External dependencies and practice); no new
  dependency, and no dependency-file edit (CLAUDE.md § HARD STOPS).
- Every hook-side call fails OPEN and never blocks a Stop; every CLI verb fails LOUD (spec § Lifecycle —
  Degradation).
- Never hold the per-session anchor lock while taking the store lock (T04 step 3).
- No store is ever created implicitly: `init` is the only writer of `.fabrik/work/config.json`.
- Every write goes through a unique temp file plus `os.replace`; a file is read into a variable before
  it is opened for writing.
- Tests are hermetic: temp git repos, an explicit `env=` (`tests/test_thread_anchor.py:215`), never
  the hub's own `.fabrik/work/` or `.git/fabrik-work/`.
- Shared tree: three sessions and the daily pipeline share `/opt/fabrik`; stage explicit paths only,
  never stash, revert or `noqa` a sibling's WIP; shared-append ledgers (CHANGELOG, DECISIONS, INDEX,
  STRATEGIC_BACKLOG, LESSONS_LEARNT) go through the private-index recipe in ONE shell.
- 12-Factor: this is repo tooling, not a deployed service (spec § Shape / infra). XI — logs go to
  stdout/stderr only, no logfile; VIII — no daemon and no PID file (the lease expires at read time, no
  reaper); X — no backing service is introduced; III — config is the committed `config.json` plus env
  (`CLAUDE_AGENT`, `CLAUDE_CODE_SESSION_ID`), no secret anywhere; II, V, VI, VII, IX, XII — not
  applicable (no container, no port, no job queue, no migration).
- Never-Route: .claude/hooks/
- Never-Route: templates/governance/

## Context Ledger

| Source | What binds | Grounded ref |
|---|---|---|
| `.windsurf/rules/core/10-python.md` (FLOOR) | typed stdlib code, no file logging | `.windsurf/rules/core/10-python.md` — "BANNED: `logging.FileHandler` …" |
| `.windsurf/rules/core/45-testing-strategy.md` (MATCHED) | one test per behaviour, watched red first | `.windsurf/rules/core/45-testing-strategy.md:20`, `:22` |
| `.windsurf/rules/core/40-documentation.md` (MATCHED) | regenerated blocks; the CHANGELOG entry format | `.windsurf/rules/core/40-documentation.md:55`, `:132` |
| `fabrik-lib` | none fits — BUILD (spec § fabrik-lib verdict); not a candidate: hub machinery, not an app library | `/opt/fabrik-lib/README.md:52` (`job-queue/`, rejected) |
| `agents-fabrik.md` infra invariants | none touched: no service, port, database or compose (spec § Shape / infra) | spec § Shape / infra |
| `specs/services/<id>.yaml` `shape.*` | none: not a deployed service | spec § Shape / infra |
| Frozen contracts (`docs/data-contract.md`, `docs/ui-design.md`) | none in the hub | — |
| Fleet-synced surfaces | `scripts/work.py` joins `CORE_SCRIPTS`; the hooks, gate, settings and template are sync triggers | `scripts/fabrik_synced_manifest.py:37-62`, `:261`; `.pre-commit-config.yaml:164` |

## File Scope (owned paths)

- scripts/work.py
- tests/test_work.py
- tests/test_work_claims.py
- tests/test_work_sync.py
- tests/test_work_migrate.py
- scripts/thread_anchor.py
- tests/test_thread_anchor.py
- .claude/hooks/final_gate_stop.py
- tests/test_work_hook_seam.py
- scripts/final_gate.py
- docs/workflows/FINAL_GATE_WORKFLOW.md
- tests/test_final_gate_work_row.py
- scripts/fabrik_synced_manifest.py
- .pre-commit-config.yaml
- .claude/settings.json
- tests/test_synced_manifest.py
- tests/test_work_distribution.py
- templates/governance/CLAUDE.md
- CLAUDE.md
- tests/test_work_contract_rule.py
- docs/reference/work-tracking.md
- docs/workstation/hooks-index.md
- docs/reference/thread-anchors.md
- docs/reference/multi-agent-operating-model.md
- docs/reference/agents/intel.md
- tests/test_work_doc_verbs.py
- scripts/sysadmin/claude_rotate.py
- tests/test_claude_fleet.py
- .fabrik/work/
- docs/development/reviews/2026-09-24-plan-2-work-tracking-review.md

## Evidence

Every ticket's primary path, grounded at HEAD 105e2d630 by three read-only units (seven native seats:
Opus on the hook seam, Sonnet breadth and Haiku inventory per unit), each claim re-read by the lead
before it was cited:

- T01a/T01b/T02/T03 `scripts/work.py` — new (`ls` → "No such file or directory"). Lock pattern to copy:
  `scripts/thread_anchor.py:319` (`_locked`), `:180` (`_LOCK_TIMEOUT_S = 1.0`). Readers reused:
  `scripts/enforcement/check_convergence.py:792`, `scripts/enforcement/check_plan_tickets.py:208`, `:991`,
  `scripts/enforcement/check_stage_artifacts.py:157`, `scripts/docs_updater.py:722` (`replace_block`),
  `:1041` (`classify_backlog_row`), `scripts/decisions.py:556` (`_merge_owner`).
- T04 `scripts/thread_anchor.py:469` (`cmd_harvest`), `:495-496` (the slot — it ALREADY stores the
  message digest as `msg`, so the RECORDED residue needs only `repo` added and a match by `msg`),
  `:516-538` (`cmd_clear_decision`), `:575` (`cmd_line`), `:686` (`cmd_where`), `:798` (`parse_known_args`).
- T05 `.claude/hooks/final_gate_stop.py:2809` (plain harvest argv), `:2644` (decision harvest argv),
  `:2641` (the knows-the-flag guard), `:2758` (root from the payload cwd).
- T06 `scripts/final_gate.py:1948` (`if tier == 2:` inside `run_consistency_checks`, `:1433`),
  `:436-440` (the `warn_only` contract), `:451-458` (absent script → ⚠ skip).
- T07 `scripts/fabrik_synced_manifest.py:37-62` (`CORE_SCRIPTS`), `.pre-commit-config.yaml:164`.
- T08 `CLAUDE.md:631`, `templates/governance/CLAUDE.md:629`, `:701`, `tests/test_governance_template_split.py:1122`.
- T09 `docs/workstation/hooks-index.md:171`, `docs/reference/thread-anchors.md:59-74`,
  `docs/reference/agents/intel.md:77-78`.
- T10 `scripts/sysadmin/claude_rotate.py:1431`, `:1436`, `:1912`, `:1929`, `tests/test_claude_fleet.py:828`.

The Task-tools probe (T07), a temp git repo, run with `CLAUDE_CODE_ENABLE_TASKS=0` exported, the
`system/init` event's tool list:

```
with-env tools= 106 ['Task', 'TaskCreate', 'TaskGet', 'TaskList', 'TaskStop', 'TaskUpdate']
no-env tools= 102 ['Task', 'TaskStop']
```

The governance-sync filter (`.pre-commit-config.yaml:164`), applied with Python `re`:

```
scripts/thread_anchor.py True
scripts/work.py False
.claude/settings.json True
.claude/hooks/final_gate_stop.py True
scripts/final_gate.py True
templates/governance/CLAUDE.md True
scripts/sysadmin/claude_rotate.py False
CLAUDE.md False
```

The gate's declared tier counts (T06 moves `tier2` to 56):

```
144:<!-- GATE-COUNTS: tier1=36 tier2=55 tier3=22 every-tier=14 -->
```

## Self-audit

**Grounding passes.** One fan-out, three units, seven seats (dispatch stamped first). What each found:
- **U1, the hook seam** (Opus authoritative).
  - The slot already carries `msg`.
  - The lock-nesting risk: the session lock must never be held while taking the store lock (T04 step 3).
  - Tests leak the hub's live store through `os.getcwd()` (T04 step 1).
  - Renewal must sit before the early return at `:489` (T04 step 2).
  - A warning must reach stdout, not stderr (T04 step 4).
- **U2, the gate and sync.**
  - Use `advisory=True`, not `warn_only`.
  - The GATE-COUNTS line must move.
  - `work.py` is absent from the sync filter's enumeration.
  - The shared-link tuple is in `claude_rotate.py`.
- **U3, the backlog and readers.**
  - The spec's 253/36 does not reproduce.
  - The existing backlog-row classifier can be reused.
  - The template's two § FINAL OUTPUT copies.

The lead re-read every anchor cited above and executed the probe and the filter test itself.

**(a) Coverage** — every "What we already agreed" line maps to a ticket:
- store and lock: T01a;
- lease, fencing and the closing verbs: T01b;
- distributor: T01a (`assign`) and T10 (`init --distributor intel`);
- DECISION items, the second chance with the RECORDED fix, the unfolded block, renewal: T04 and T05;
- drift and blocking: T02, with the gate row in T06;
- backlog view: T03, with the hub render in T10;
- Task list env: T07, with the link in T10;
- docs: T09;
- contracts: T08;
- adoption, V2, V5, V6 and the fleet request: T10;
- V1: T05;
- V3 and V4: T01b;
- I11, the decoder approval: the orchestrator's closing DECISION block (T10).

No gap.

**(b) Cross-ticket signatures** — each consumer is checked against its producer:
- `repo_root`, `has_store`, `on_harvest`, `ensure_decision_item`, `ensure_decision_items`, `has_msg_digest`, `prompt_block` are named identically in T01b (producer), T04 (consumer) and § Interfaces.
- `--repo` is named identically in T04 and T05.
- The `sync --check` exit contract reads the same in T02 and T06.

**Fixed point.** Not claimed here. Convergence is `/fabrik-plan-review`'s.

## Coverage Checklist

Rubric over the plan's File Scope (`python scripts/review_rubric.py --changed scripts/work.py tests/test_work.py tests/test_work_claims.py tests/test_work_sync.py tests/test_work_migrate.py scripts/thread_anchor.py tests/test_thread_anchor.py .claude/hooks/final_gate_stop.py tests/test_work_hook_seam.py scripts/final_gate.py docs/workflows/FINAL_GATE_WORKFLOW.md tests/test_final_gate_work_row.py scripts/fabrik_synced_manifest.py .pre-commit-config.yaml .claude/settings.json tests/test_synced_manifest.py templates/governance/CLAUDE.md CLAUDE.md tests/test_work_contract_rule.py docs/reference/work-tracking.md docs/workstation/hooks-index.md docs/reference/thread-anchors.md docs/reference/multi-agent-operating-model.md docs/reference/agents/intel.md scripts/sysadmin/claude_rotate.py tests/test_claude_fleet.py .fabrik/work/ docs/development/reviews/2026-09-24-plan-2-work-tracking-review.md`), verbatim; only the `# promote-to-check_*` tail is elided, as declared on its line:

```text
# REVIEW RUBRIC — inject into EVERY finder prompt (generated by review_rubric.py)
# Honesty (L1): this arms the review — it raises compliance probability, it does not guarantee it.

## FLOOR — always injected, regardless of glob (spec L3; SERVICE surface)

### core/35-security-auth.md
**The default for ALL new projects, including user-facing SaaS + mobile.** Vendor `fabrik-lib/fastapi-user-auth`: the app issues its own JWTs — **Argon2id** (the vendored argon2-cffi defaults meet OWASP minimums; never Argon2i) + timing-equalized login, atomic refresh-token rotation (`DELETE … RETURNING`), JWT `jti` denylist revocation, and dual-mode tenant-isolation RLS. Supabase is retired as a default (see `agents-fabrik.md § Supabase`); reach for Pattern B only for a project that *already* runs on Supabase Auth.
- Do not use NextAuth.js, Clerk, Auth0, or Firebase Auth.
- ADDITIONAL affordance a project justifies, never the default door.
- project files the fabrik-lib request FIRST, never hand-rolls WebAuthn.
| `chrome-extension` | ✅ **use this** | ⚠️ only via `chrome.identity.launchWebAuthFlow` + the `https://<ext-id>.chromiumapp.org/` redirect the pack already mandates; a bare mailed link lands in a TAB that cannot reach `chrome.storage.session` |
| `desktop-app` | ✅ **use this** | ⚠️ needs a registered custom protocol handler; the token then goes to `safeStorage` (`desktop-app/72-desktop.md`) |
- service MUST be able to say which:
| **Another Fabrik service** (Docker-to-Docker on the `fabrik` network) | `X-Internal-Token` + `internal_auth.py`, `hmac.compare_digest`, 403 on reject | § Internal Service Auth (M2M) below — **never** an inline `APIKeyHeader`, never a per-service key name |
- An approval link opened somewhere the user did not start must never mint a session silently.
- > **Fail-closed invariant (hard, every mode).** `auth.uid()` and `current_tenant_id()` MUST return `NULL` (→ the policy denies) on unset, empty, or malformed claims — wrap the body in `EXCEPTION WHEN OTHERS THEN RETURN NULL`. **Never** raise and never default to a value: an error-open helper turns one bad/empty JWT into a full cross-tenant read. This is the single most security-critical line in the build — verify it explicitly with a no-context probe (`SELECT auth.uid()` → `NULL`).
- The JWT signing secret must be at least 256 bits, generated via `openssl rand -hex 32`, and injected via Pydantic Settings. Never hardcode it.
- **Pin the algorithm in the VERIFIER** — pass an explicit allow-list (`algorithms=["HS256"]`), never let the library dispatch on the token header's `alg`. Header-driven dispatch is the classic confusion attack (an RS256 public key replayed as an HS256 HMAC secret); `alg: none` is rejected unconditionally.
- "Sticky sessions are a violation of twelve-factor and should never be used or relied upon."
- => Mandate: processes are stateless/share-nothing. **STICKY SESSIONS ARE BANNED** (not just file-based sessions). Session state goes to `redis-main` (Redis) with a TTL. Never in-process memory, never on local disk. Any design that assumes "the same user hits the same process" is a violation.
- **Pattern B (legacy / migration-only):** The Supabase client SDK handles token storage. On mobile, wrap with `expo-secure-store` (never AsyncStorage or MMKV for tokens). See `80-mobile.md` § Backend Integration.
- **Both patterns:** Never store JWTs in `localStorage` or `sessionStorage` on web. Never store JWTs in AsyncStorage or MMKV on mobile.
- **Chrome Extension (MV3) specifics:** `chrome.storage.session` defaults to `TRUSTED_CONTEXTS`, so **content scripts cannot read the token** — keep it in the SW / extension-page context and have content scripts fetch it via SW-mediated messaging (`chrome.runtime.sendMessage`), not a direct read. For social login use `chrome.identity.launchWebAuthFlow` with **PKCE** (`code_verifier` via `crypto.subtle`, held in `storage.session`, redirect `https://<ext-id>.chromiumapp.org/`); the **backend** does the code-for-token exchange. **Never a heavy browser auth SDK** (Auth0-SPA-JS, `oidc-client-ts`) — they assume DOM/`localStorage`/iframes and break in the service worker. Pin a manifest `key` so the extension ID (and thus the `chrome-extension://<id>` CORS origin) is stable across machines. Full detail: `chrome-ext/70-chrome-ext.md`.
- **Never rely solely on the framework's request-shaping layer for access control.** CVE-2025-29927 (the `x-middleware-subrequest` bypass) proved COMPLETE middleware bypass via one crafted header; it is long patched upstream, but the rule outlives the patch — current Next.js even RENAMED the file to say so: `middleware.ts` became **`proxy.ts`**, explicitly repositioned as request-shaping, not a security boundary. ⚠️ **On current majors a leftover `middleware.ts` is SILENTLY IGNORED at build** — nonce injection and redirects stop executing with no error; rename it when upgrading.
- `CORSMiddleware` in FastAPI must populate `allow_origins` from environment variables (Pydantic Settings). Never hardcode origins.
- `X-Frame-Options: DENY` — kept as the legacy fallback only; formally obsoleted by `frame-ancestors`, never ship it ALONE
**Never** write inline `APIKeyHeader` / `require_api_key`. **Never** use per-service key names (`SERVICE_API_KEY`, `PROXY_API_KEY`). Scaffold `python-api` auto-emits `internal_auth.py`, `metrics.py` (REQUEST_COUNT / ERROR_COUNT / ACTIVE_JOBS / PROCESSING_COUNT), `/metrics` endpoint (Authelia-bypassed), and `SERVICE_INTERNAL_SECRET_KEY` in `.env.example`.
- => Mandate: config via env vars only (`os.getenv("KEY", "default")`); **ZERO secrets/constants in code**. Apply the open-source litmus test to every change. **BANNED**: grouped/named env config sets (e.g. a `config/production.yml` or a `settings.production` group) — env vars are granular and orthogonal, set per deploy. (The pack already covers secret handling — cross-reference existing secret patterns and extend with config orthogonality.)
- [ ] Mobile tokens stored in `expo-secure-store` — never AsyncStorage or MMKV.
- > **⚠️ Bearer bypass scope — security-critical.** The bypass defaults to `^/api/`, which makes the **entire** `/api/*` surface public (un-2FA'd). If the application authenticates only a **sub-prefix** (e.g. `/api/v1` carries the bearer/internal-token check) while OTHER `/api/*` routes are unauthenticated (legacy / admin / destructive), you **MUST** narrow the bypass with `shape.bearer_bypass_prefix: "^/api/v1"` — otherwise `fabrik apply` exposes those routes to the public internet. **Bypass ONLY the path the app itself authenticates.** Value must start with `^/`; the verifier (`orchestrator/verifier.check_api_bypass`) probes the configured prefix on deploy. When unsure whether a service has un-auth'd `/api/*` routes, ask the app owner before relying on the `^/api/` default.

### core/25-data-postgres.md
| Vector search | pgvector on `postgres-main` + `fabrik-lib/rag` — ⚠️ the extension is NOT currently installed there (probed 2026-09-01: `postgres:16-alpine`, `plpgsql` only); a project needing vectors REQUESTS the fleet infra change first, never assumes it | same `postgres-main` DSN |
**"Own database" means a DATABASE on `postgres-main`, never a database SERVER.** Per-project and per-tenant isolation is a separate database (its own name, its own role) on the shared container — isolation, quota and backup are all satisfied at that grain. A dedicated Postgres instance is a decision, not a default: it needs its own `docs/DECISIONS.md` row naming what the shared server cannot serve (web-ecommerce-factory 01M1Q8X9, 2026-09-05: "one DB per store" read naively as one server per customer).
- Use Pydantic `BaseSettings` (per `10-python.md` § Config Loading) — never raw `os.getenv` **for an APPLICATION's settings surface**:
- ⚠️ **Scope, stated here because this LINE is what `review_rubric.py` injects — without its section.** The rubric FLOOR-injects this mandate *and* `35-security-auth`'s "config via env vars only (`os.getenv("KEY", "default")`)" into every finder prompt on every review, so a finder reading both literally has two rules it cannot both satisfy, and files a false positive on whichever it applies. The carve-out: `BaseSettings` governs a SERVICE's config surface (a `Settings` object, DB/Redis DSNs, secrets). A **vendored fabrik-lib module** has no settings object by design — it reads its own knobs with bare `os.getenv("KEY", "default")`, which is `35-security-auth`'s mandate being satisfied, not this … (wrapped further — read the pack)
- Never blindly trust `--autogenerate`. Always review `upgrade()` and `downgrade()` for unintended column drops, rename misinterpretations, and ENUM alterations before committing.
- > **Older pythons only** (services pinned below stdlib-uuid7 — which today includes SCAFFOLDED services: the scaffold still emits an older interpreter and ships `uuid-utils`; alignment tracked in the backlog): import `uuid7` from `uuid_utils.compat`, never `uuid_utils.uuid7()` directly — the latter returns `uuid_utils.UUID`, which asyncpg rejects (not a stdlib `uuid.UUID`). **DB-side:** newer PostgreSQL majors ship native `uuidv7()` (probe: `SELECT uuidv7()`); prefer `DEFAULT uuidv7()` at schema level where it exists. `postgres-main` currently runs major <!--v:postgres_major-->16<!--/v-->, which predates it — generate app-side on the fleet.
- Foreign keys must declare `ON DELETE` behaviour explicitly — `CASCADE` if children cannot exist without the parent, `RESTRICT` to protect audit trails. Never rely on the implicit default.
- This section owns the **canonical** engine, session, and `get_db`. `10-python.md` imports from here — never redefines its own.
- Database `AsyncSession` must be scoped to the route handler via `Depends()`. Never open sessions or transactions in global middleware — this holds connections during serialisation and I/O, exhausting the pool.
**BANNED as a server-side backing service** (dev, test, and prod alike):
**⚠️ SCOPE — this ban is about BACKING SERVICES, not client-local storage.** It does **NOT** apply to:
- **`desktop-app`** — SQLite is the **mandated** engine there (`desktop-app/72-desktop.md` § Local Persistence: `better-sqlite3` + SQLCipher; *"Production builds MUST encrypt the local SQLite file"*).
**12-Factor IV (Backing Services) — generalised:** swapping ANY attached backing service (DB, cache, object storage) is a **config change, never a code change**. The handle lives in `DATABASE_URL` / `REDIS_URL` / storage env — the code *reads* it, the code does not *decide* it. Never `if ENV == "prod":` branching to pick a host. (See § PostgreSQL Host Selection, which already mandates this for the DB.)
- [ ] All primary keys use UUIDv7 — stdlib `uuid.uuid7` on current Python (older pythons: `uuid_utils.compat.uuid7`, never direct `uuid_utils.uuid7()`); no `uuid4()`.

### core/30-ops.md
- the pinned release leaves full security support, never per-pack.
- All services deploy via `fabrik apply` (SSH + Docker Compose) on the `fabrik` network. Traefik routes external traffic — services do NOT bind host ports.
- **No `ports:` section.** All external traffic routes through Traefik. Never bind host ports. See Docker Port Security below. **12‑Factor VII (Port binding):** "the app is self‑contained and exports HTTP by binding to a port; it does not rely on runtime injection of a webserver" — which is exactly WHY no host `ports:`.
- **`container_name: <name>` is mandatory.** Same `_validate_compose()` gate refuses any service without it. Stable names are required so Gatus endpoints, inter-service URLs, and `docker exec`/`docker inspect` keys don't drift per redeploy. Use the bare service name (`browserless`, `gotenberg`, `meilisearch`, `glitchtip-web`, `site-provisioner`, etc.) — never UUID-suffixed names.
- gets one (ruling D-052) — see `core/60-watchdog.md`. Do not author a `watchdog: { enabled: false }` opt-out; if a project genuinely cannot host the sidecar, that is a ruling to obtain, not a default to flip.
- path before the flag goes in the spec, and assert target health (`/api/v1/targets` → `up`), never a bare `curl` of a path you assumed.
- VOLUME gets a plan pointed at a directory that never exists — a paper backup that reads green and archives nothing.  If the data is a volume, say so in the spec comment and rely on the global `docker-volumes` plan; never let a service-named plan be mistaken for the protection.
- health-enabled service can NEVER pass `up -d --wait` on a fresh database, and the deploy hangs to timeout.  An init the deploy cannot perform itself is a runbook step the plan MUST own.
- `fabrik redeploy <app>` SSHes to the VPS and runs `git pull` + `docker compose up -d --wait` against the **GitHub remote**, NOT the local `/opt/<app>` clone. Skipping `git push` redeploys the previous remote commit — the VPS never sees local changes.
**Mandate:** build → release → run are strictly separated. Releases are IMMUTABLE; the git SHA is the release ID. NEVER hot‑patch a running container (no `docker exec` to edit code/config in place, no in‑place code mutation on the VPS). Any change = a new build + a new release via `fabrik apply` / `fabrik redeploy`.
- Runtime database migrations that modify the app container (migrations MUST be run as separate deploy‑time steps)
**Place a service next to its data.** A spoke-hosted service reaches `postgres-main`/`redis-main` over the WireGuard mesh, and that hop is cross-Atlantic (Coventry ↔ LA) on EVERY query — a per-request chatty service pays it hundreds of times per page. So a DB-chatty service targets vps1; a spoke earns a service whose data traffic is light, batched or cached; a service PINNED to a spoke by hardware (GPU) batches or caches its data access — the data never moves off vps1. Measure before choosing (`ping 10.99.0.1` from the spoke, and the request's query count), never assume — the correctness rule ("container DNS, never localhost") says nothing about latency.
**Mandate:** WSL dev and the VPS run the SAME backing services (PostgreSQL + Redis), same major version. NEVER substitute a different backing service in dev (no SQLite standing in for Postgres, no in‑memory dict standing in for Redis). The same code must run unmodified in both environments.
- WSL runs PostgreSQL + Redis at the SAME MAJOR as the VPS containers — probe the live truth, never copy a tag from a doc: `ssh vps "sudo docker inspect postgres-main redis-main --format '{{.Config.Image}}'"` (2026-09-01: `postgres:16-alpine` · `redis:7-alpine` — upstream official images, outside OUR-image Alpine ban per § Banned Patterns)
**Invariant:** Never use `ports:` in compose.yaml to expose internal services to the host. All external traffic must go through Traefik.
**Health endpoints (`/health`, `/healthz`, `/metrics`, `/api/health`) bypass Authelia on all services** — required for Gatus and Prometheus monitoring. The bypass is **resource-based, not domain-bound** — applies on every domain routed through Authelia (hub direct + spokes via `authelia-vps1@file` middleware). Never protect these paths.
**CRITICAL:** Use `web`/`websecure` in Traefik labels — never `http`/`https` (those entrypoints do not exist). The scaffolder emits the correct entrypoint names; if you hand-write labels, match these exactly.
**Mandate:** migrations and admin tasks run as a ONE‑OFF process against the DEPLOYED image + env — identical environment to regular processes. NEVER run admin tasks from a laptop against prod, NEVER via `docker exec` into a live container, and **ABSOLUTELY NEVER auto-run migrations from app startup/`lifespan`** (concurrent replicas race the Alembic version table → wedged deploy).
- > **`fabrik run` and `.fabrik/hooks/post-deploy/` do NOT exist** — the real CLI answers `Error: No such command 'run'`, the hook path appears nowhere in the platform, and `_post_deploy_sync()` (`cli.py:64`) only refreshes `data/projects.yaml`; an agent following either ships a deploy where migrations never run. Do not re-add either without a `path:line` in `src/fabrik/` that executes it.
**Processes are share-nothing:** any state shared across requests MUST go to Redis (`redis-main`) with a TTL. A project using Redis for sessions MUST declare `shape.needs_cache: true` in `specs/services/<id>.yaml`, or `fabrik apply` skips the Redis registrar and the deploy is silently broken.
- "A twelve-factor app never relies on implicit existence of system-wide packages"
**Mandate:** any binary the app shells out to (ffmpeg, yt-dlp, poppler, tesseract…) MUST be `apt-get install`-ed in the Dockerfile, with a `shutil.which()` startup probe that fails fast. **The pinned base image is the version boundary** — exact `=version` apt pins are banned: they break on every Debian point release as old debs leave the mirrors (the "works then mysteriously breaks" class this section exists to prevent); the codename pin + image digest give the reproducibility. Never assume `curl`/ImageMagick/ffmpeg exist in the image — they don't by default.

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

### ai/00-ai-model-selection.md  (hit: docs/reference/agents/intel.md)
**Always the latest Claude models — select by ALIAS, never by an old ID.** Claude Code's aliases resolve to the newest model of each family and move with every release, so code that says `--model opus` never goes stale:
- A pinned ID in code or config is a stale model waiting to happen: when reproducibility genuinely matters, take the ID from the table above (its values are machine-owned in `.windsurf/rules/versions.yaml`) and record why the pin beats the alias. Fable is never an account default — it is always selected explicitly. `best` resolves to Fable where it is available, else Opus. **Where a category pack (`10`–`90`) or a sibling pack still names a Claude model by version, or routes an LLM step to a metered gateway only, THIS section wins** — select Claude by alias; those packs are corrected on their own turns.
**Vendor access:** `docs/reference/kilo/AI_VENDOR_ACCESS.md` is the single source of truth for which vendors the operator can call today. Rows with Status ✅ or ⚠️ are accessible (⚠️ = accessible but low balance — pick a ✅ peer if one is on the Pareto frontier).
- Operational stack (sysadmin, watchdog, bootstrap) uses **Claude Code CLI w/ subscription OAuth** — never `ANTHROPIC_API_KEY`. No fabrik code path reads that key (the `fabrik ai generate` utilities were removed 2026-06-16); a project that needs a metered LLM goes through OpenRouter. Per-LLM-call cost caps apply to paid APIs via `core/cost-budget.md`; they must not be placed on the operational diagnose loop.
- (`CLAUDE_CLI_MODEL`) is `opus` — set `haiku` for rung 1 below. ⚠️ `complete(model=…)` sets the OpenRouter model only; the `claude -p` leg always runs `CLAUDE_CLI_MODEL`, so choose the rung with a per-rung config — `complete(prompt, config=dataclasses.replace(LLMConfig.from_env(), claude_model="sonnet"))` (a bare `LLMConfig(...)` skips the environment: no OpenRouter key, default effort) — or `dispatch(ClaudeCall(prompt, model="sonnet"))`, which RAISES (`DispatchError`, or `ValueError` for an invalid `ClaudeCall`) and has no OpenRouter leg, so catch both yourself. The CLI leg runs at `CLAUDE_CLI_EFFORT=low` by default — raise it before judging that a rung measurably fell short.
- `claude -p` MUST declare **`shape.uses_claude_cli: true`** (+ `claude_cli_home`) so the deployer mounts the host's **rotated** `~/.claude` read-only into the container — auth follows the fleet account rotation;
**never** bake a static `CLAUDE_CODE_OAUTH_TOKEN` (it pins one account and dies at its weekly quota). Then select the rung — always by alias, so each rung is the latest model of its family:
- enough (task fails its quality gate / errors — a measured escalation, never a vibes one).
- be metered-isolated from the subscription). ⚠️ `complete()`/`complete_json()` take this leg whenever the `claude -p` leg yields no text — binary missing, auth failure, timeout, error, quota, an empty result, and also when YOUR `budget_check` refuses `claude-cli` (and `budget_check` fails OPEN if it raises); `dispatch()` and the session/agentic calls never fall back, and `complete_structured()` only through a `fallback=` you inject. The key is `KILO_API_KEY` before `OPENROUTER_API_KEY`, and `KILO_API_URL` overrides the endpoint — wherever the fleet's keys sit in the environment (the hub's, per D-182) they win. So unset both `KILO_*` vars and set the project's OWN `OPENROUTER_API_KEY`, guard the leg with `budget_check`, and alert on the dispatcher's … (wrapped further — read the pack)
**tested evidence, never assumption**: consult the selection MDs / `suggest_model.py`, or run a scored bake-off — lowest cost that meets the required capability; record the result in the project's decision ledger.
- above; never `ANTHROPIC_API_KEY`, never a vendor SDK — `core/57-external-data-sourcing.md` hard constraint). Every rung wraps in the `58-resilience` contract, and any unattended paid-LLM loop still carries watchdog + cost-budget. This ladder governs **in-code single-call/worker dispatch**; gradeable parallel fan-out (review finders, graders, doc reconcilers) runs NATIVE while the pool is OFF (D-181) per `core/62-using-subagents.md`.

### core/10-python.md  (hit: .claude/hooks/final_gate_stop.py, scripts/fabrik_synced_manifest.py, scripts/final_gate.py)
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

### core/40-documentation.md  (hit: CLAUDE.md, docs/development/reviews/2026-09-24-plan-2-work-tracking-review.md, docs/reference/agents/intel.md)
- > **⚠️ `docs/OPERATIONS.md` + `docs/DEPLOYMENT.md` are FLEET-AI INTERFACES, not just docs (D-065).**
- **Tier-1 (author → verify → converge; the author leg is NATIVE while the pool is OFF, D-181 — `scripts/doc_reconcile.py`'s pool author cannot dispatch):** for each **mechanically-detectable** doc whose Doc-Sync trigger fired (`docs/QUICKSTART.md` · `docs/CONFIGURATION.md` · `docs/data-contract.md` · `docs/SERVICES.md` · `docs/OPERATIONS.md` — the reliable-signal subset), `scripts/doc_reconcile.py` dispatches a cheap OpenRouter-pool author (`libs.subagents`, `pick_models("docs")`) to emit a **minimal structured patch**, **verifies it before applying** (a symbol cross-check catches invented endpoints; the orchestrator injects a higher-assurance native-Claude verify), and loops to a zero-edit round. Runs per phase in `/fabrik-execute-plan`; never blocks (fail-safe). The other docs (CHANGELOG, INDEX, FEATURES, RESILIENCE, PORTS, the READMEs, `db/schema.sql`, …) have no reliable mechanical content-signal → they rely on the touch-on-change backstop below + your own edit (force-update, not force-correct).
- The SSOT is the type-aware registry (`scripts/enforcement/_doc_registry.py::PROJECT_DOCS`) — this table is its project-facing rendering, kept in step, never a second truth. `/fabrik-plan-after-chat` (the plan set's spine + tickets — the ticket-format authority) injects these rows per ticket as its `Docs:` line.
- Standalone work (not plan execution) → `Agent-Role: primary`. Trailers go below a blank line, above `Co-Authored-By`. ⚠️ The trailer block must be its OWN paragraph with NO blank line inside it: git parses only the LAST paragraph, and only if it is all-trailers. A blank line before `Co-Authored-By:` demotes everything above it to prose; so does a prose line glued to the top of the block. Measured 2026-08-15: 200 of the last 200 hub commits carried `Agent-Role:` and only 10 parsed, because the old example here shipped the blank line.
- **⚠️ Link it or it is decoration.** *Measured:* requests for files that do NOT exist came ~zero from AI bots — agents never go looking. It follows (inference, not measurement) that a file only gets read when something points at it: reference it from the docs index or README.
- ⚠️ **In THIS repo `llms.txt` is GENERATED** (`scripts/generate_capability_index.py`, refreshed daily) — never hand-edit it; change the generator. A project writing one by hand owns it.
- either way. Cheap and reversible — never at the expense of `OPERATIONS.md`/`DEPLOYMENT.md`, which are the load-bearing agent interfaces (D-065).
- **No skipped heading levels** — `##` to `###`, never `##` to `####`
- **Fenced code blocks only** — never indented code (AI treats it inconsistently)

### core/45-testing-strategy.md  (hit: tests/test_claude_fleet.py, tests/test_final_gate_work_row.py, tests/test_synced_manifest.py)
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

### core/62-using-subagents.md  (hit: docs/reference/agents/intel.md)
- GOAL: One place that says which subagent runtime to use, what tools it gets, what NEVER goes to a subagent, and how tool access is a single-source change. AGENT USAGE: When a command dispatches subagents, pick the runtime + the tool scope from here. Design authority: docs/superpowers/specs/archived/2026-07-07-subagent-tool-parity-design.md (Claude Code side). The paused pool's contract: docs/reference/subagent-pool-contract.md. -->
- > **⚠️ STATUS — the OpenRouter pool, Kilo subagents and `ai-consult` are PAUSED** (operator: D-181 2026-09-07, mechanism D-182, re-confirmed 2026-09-22 — D-343). Their credentials stay provisioned, so a `fanout()` / `consult()` would still dispatch and SPEND: this pack and `scripts/enforcement/check_subagent_flywheel.py` (`_POOL_POLICY_ON = False`, fleet-synced; `FABRIK_POOL_POLICY=on` is its test seam and re-arms the gate — never set it in a run) are the control, and intel monitors `fabrik_analytics.subagent_runs` for any dispatch while the pause holds. **Every fan-out runs native Claude Task subagents.** This pack's pool-era contract is FROZEN verbatim in `docs/reference/subagent-pool-contract.md`; re-enabling is an operator ruling first, then a restore from that file — never a quiet uncomment.
**Never restate tool lists in a command brief — the access lives in the agent-type file.** Compose a subagent's brief per `docs/reference/MD/ai-prompt-templates.md` — a distilled system prompt (Part A) that enforces the agentic patterns (Part B: termination contract, evidence-before-assertion, path:line grounding, untrusted-input). Distil, don't dump the whole rulebook into the brief.
**The paused runtime — fabrik-lib `subagents` (OpenRouter models in a sandboxed worktree) — is not Claude, has no browser, and is not to be called.** Its `pick_models` still returns a dispatchable roster and `fanout` still spends; the only lever that refuses is this text (D-182). Do not "turn it off" by emptying `docs/reference/kilo/TASK_SUBAGENT_SELECTION.md` — `pick_models` falls through an empty section to the unrestricted vendored `_TABLE`.
| rendered-UI design review (`/design-review`) | `design-review` | an explicit allow-list — playwright browser tools + Read/Edit/Write/Bash + WebFetch/WebSearch (web AND edit in one type: never hand it sensitive context); `model: sonnet` |
- **Two cheap finders per slice — one Sonnet and one Haiku, each over the whole slice, candidates UNIONED, never voted — and NO Opus finder** (pilot D-344, 2026-09-22, superseding D-207's Opus-on-the-risky mix for the partitioned loops; the units-sized floor below is unchanged). The risky units — concurrency and locks, record and file formats, fleet-synced paths (`scripts/enforcement/`, `scripts/command_run.py`, the hooks, `templates/governance/`), auth, schema, migrations, secrets — are the slice's NAMED hunt priority in its brief. Opus and Fable earn their price EXECUTING and adjudicating, in the orchestrator.
- **At most ONE EXTRA Haiku class seat** across the whole surface — for a judgement-shaped inventory class the close-out hygiene script cannot express, and only when the brief NAMES it; the scriptable classes (stale phrases, table and fence shape, dead symbols, `{{` residue) are the script's from round 1's start, never a seat.
- **Fable** (Opus BY NAME when Fable refuses) orchestrates: it partitions, dispatches, adjudicates and EXECUTES every refutation and every confirmed reproduction. The orchestrating context is never a finder; the one reading seat Fable takes is a DISPATCHED Fable seat as the ROUND-ONE authoritative reader of a command's final validation (the last full-surface pass a command names — a plan's Finish review), substituting for the Opus seat there and then re-verifying its own slice in the closing pass like any round-one seat (constraint 5 below).
- **Round 1 is the ONLY full pass. Every later pass is the round-one seats re-verifying their OWN slices' claim ledgers (D-335, superseding D-229's delta sizing):** the surface of a later pass is the fix diff plus one hop of callers and callees (the hop bounds the EXTENT; what a later pass may COUNT is the fragments' bounded-hop rule — `term-edit`/`term-coverage`, D-230, which D-335 keeps; grep the changed symbols, or `find_referencing_symbols` where the language server is up), plus the tests that import a changed module, plus any sibling commit that landed on the surface since; a unit whose ledger holds no open claim is not re-dispatched, and the round-1 count is the ceiling. The class ledger PERSISTS across rounds: a later pass sweeps the classes its diff touches and CITES the rest as standing-clean from the last full pass, and the receipt says which — a round is never a re-scope, and there is no round CAP (D-330, superseding D-321) — the terminal is every slice verified inside the run's DECLARED budget (`command_run.py start --budget`, `round --slices A:12/12` records it), and a slice whose claims still fail after its THIRD pass, or a pass that would overrun the declared budget, is HANDED OFF with those claims named per `term-coverage.md` — never capped, never looped.
- **The closing pass is those same seats confirming every claim executed true** — never the orchestrating context's own re-read (§ Role separation; a dispatched Fable seat is a seat), never the hygiene script alone.
- **Quiet is zero CONFIRMED code or doc defects (D-206), never zero raised:** a candidate becomes CONFIRMED only when the orchestrator REPRODUCES it (probe, failing test, or a mutation on a pinned copy), and REFUTED only when it EXECUTES the refutation and the receipt row cites that command and its output; a candidate neither reproduced nor refuted is `RECORDED — unexecuted (<why>)`, one reproduced and kept on purpose is `RECORDED — by design (<owning row>, round N)`, and RECORDED and REFUTED rows never reopen the loop. The Pass Ledger row states the counters in that order — `found: F, new: N, confirmed: C, fixed: X, unexecuted: U` — and the loop closes on `confirmed: 0, fixed: 0` with `unexecuted: 0` or none; a round that FIXED something is never the closing row.
**UNITS-SIZED — every OTHER command** (`/fabrik-review-scoped`, the grounding and adjudication commands — the researcher floors — and the sweep and audit reviews): per INDEPENDENT unit of the surface — failure class · file · screen · doc · pack · journey · fact · behaviour — a Sonnet breadth seat plus a Haiku mechanical seat, all dispatched in a SINGLE message so they run in parallel, plus the Opus authoritative seat(s): a 3-unit surface with a mechanical angle is 7 seats (4 with `--mechanical 0`), never a token 1–2 (the executable number is (1) below). The CAP is independence OF THE SURFACE, not of the reader — partition so no unit's ground truth is another's; a unit you cannot brief distinctly is not a seat. ⚠️ **NEVER solo, never two — the FLOOR is three seats for every command that is NOT a partitioned review loop (D-208), and the floor binds ROUND 1 only: every later pass is the round-one seat that owns each open claim, re-verifying it (D-335).** Under a partition the floor stands DOWN — satisfied by construction, since every non-empty slice kind already keeps its own seat and the third angle there is the orchestrator's EXECUTION of every candidate rather than a third reader (D-218). Where it applies, a surface with fewer than three units still dispatches THREE seats on DIFFERENT angles over it. Deliberate DUPLICATE briefs over one small surface are a different technique (`/fabrik-review-scoped` § floor): they buy sampling variance, not coverage, and are budgeted as ONE unit.
- ⚠️ **Dispatch economics — five constraints, ONE executable number (D-189).** A partitioned loop sizes with `--slices` as above, however small the partition. A units-sized surface runs `--units <N> [--heavy] [--risky <R>] [--mechanical <M>]` before any fan-out wider than the floor and dispatches the `SEATS:` it prints — `min(units × angles + the Opus seat(s), CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS, box_cap, quota_cap)`, never below 3 unless a hard cap binds or the fleet is on HOLD; a later pass is sized by its open claims (D-335); a floor-sized units fan-out at ROUND 1 (1 unit = 3 seats = the floor) needs no script — stamp its three seats with `dispatch --seats 3`.
- 1. **Maximum (D-191)**: the BOX is the ceiling and the units are the PARTITION. Every unit gets one seat per ANGLE — a Sonnet breadth seat and a Haiku mechanical seat — plus the Opus authoritative seat(s), one per risky unit and at least one (a risky unit therefore carries THREE angles: authoritative, breadth, mechanical — cost 8); `dispatch_headroom.py` computes that as the WANTED count and trims it to what the box, the CLI cap and the quota allow for maximum unit COVERAGE — Haiku first, then the extra Opus seats, then Sonnet, never the last Opus seat. **The mechanical angle is grep-shaped and therefore GLOBAL:** `--mechanical <M>` is the number of grep-able classes the surface HAS (inventory · naming · format · links/anchors · counts); when the budget trims below one Haiku seat per unit, each remaining Haiku seat sweeps ONE class across every unit; and a grounding or adjudication surface has no mechanical angle at all (`--mechanical 0`) — a Haiku seat briefed on a judgement returns a claim you must refute, which is spend without recall. Dispatch ALL of what it prints, in ONE message, each seat a distinct unit × angle brief — and when the COST line says TRIMMED, dispatch the trimmed mix, never the per-unit sentence.
- 2. **Box, no OOMs**: a native seat runs inside its parent `claude` process, so its memory is its TOOL subprocesses — and a "read-only" finder still runs pytest through Bash, so the box bound applies to EVERY seat: 2 GB planned per `--heavy` seat (pytest/build/render), 1 GB per read-only seat, against `min(MemAvailable, CommitLimit − Committed_AS)` and one core per seat, MINUS the seats sibling sessions DISPATCHED in the last 25 minutes (`command_run.py dispatch --seats <n>`, stamped BEFORE the seats go out and accumulated within the round — a `round --seats` written at the round's close reserves nothing while the seats run; the caller's OWN record is never subtracted). Siblings RESERVE, they never starve: a session always gets the floor the box physically has room for, and the floor never overrides a hard cap — a box with room for two seats gets two, with the reason.
- 3. **Fastest**: every seat in ONE message (parallel), never one message apart; keep working while they run. Width is paid for (Anthropic measured multi-agent runs at ~15× the tokens of a chat, ~4× per agent): seats bill their OWN transcripts (`<sid>/subagents/agent-*.jsonl` — the parent's result line is one turn of it), so a wide round multiplies a run's tokens; `command_run.py` sums those transcripts into the ledger's `tok_seat_*` columns at every `round` — that is where the cost is read, never by opening a transcript. Wall-clock tracks ROUNDS, not seats — blocking on a single seat is how one round becomes many minutes of nothing.
- 5. **The right model per ROLE** — and the MECHANISM is the one-token per-dispatch override, `Agent(subagent_type=…, model="opus"|"sonnet"|"haiku"|"fable")`. Resolution order, first match wins (code.claude.com/docs/en/sub-agents): the per-dispatch token → the type file's `model:` (`fabrik-reviewer` is `sonnet`; `fabrik-researcher`/`fabrik-gui` are `inherit`) → the `CLAUDE_CODE_SUBAGENT_MODEL` env var (a DEFAULT for seats assigned no model — unset on this box) → the parent's model; so a role stated without the token IS the type's default, authoritative pass included. ⚠️ `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` (ANY value, `0` included — the binary tests the string) discards every type file's `model` and the token: seats then run on `CLAUDE_CODE_SUBAGENT_MODEL`, or — when that is unset, as here — on the PARENT's model, so every Haiku and Sonnet seat silently bills at the orchestrator's 5×/10× with no error and no line in the cost print. Never set it in any fleet settings. A per-dispatch token also sticks when the seat is later resumed by message. The four names, one job each: **Fable** = orchestrator/adjudicator and, dispatched as a round-one seat, the final validation's authoritative reader (substitutes for, never adds to, the Opus seat there; never a routine finder, never a coder) — ⚠️ **Fable is METERED usage credits, not a subscription window** (the quota probe cannot see it): check availability before a run that needs it, and a Fable seat that refuses falls back to Opus BY NAME with the fallback recorded, never silently · **Opus** = the authoritative pass — under a partition that is the orchestrator's own execution of every candidate (D-344, no Opus finder); ≥1 authoritative seat in a units-sized round — and design-heavy never-delegate coding · **Sonnet** = breadth, one seat per independent unit, and the default coder · **Haiku** = the mechanical seat — one per unit under units-sizing, at most one across a partition (grep-able classes, format, inventory), never codes. GUI stays `fabrik-gui`. Model is chosen by the seat's JOB, never by what is idle. **Price multipliers (operator ruling D-190): haiku 1× · sonnet 2× · opus 5× · fable 10×** — "affordable" is a NUMBER, `cost = Σ seats × multiplier` in haiku-units, and `dispatch_headroom.py` prints it (`--mix opus=1,sonnet=5` → 15). An Opus breadth seat costs 2.5× a Sonnet one — whether it buys more recall is UNMEASURED (the D-186 tripwire ledger, with `--seats` recorded, is where that answer will come from), and until it is measured the default is the cheaper seat; a Fable adjudicator costs 10 and is one seat per run, never per unit, printed beside the seat total, never inside it. The number is RELATIVE and dimensionless — it assumes equal tokens per seat, and the orchestrator's own reading (at its own multiplier, growing with every seat's report) is NOT counted: the quota band guards the seats, and nothing yet guards the orchestrator's own reading. ⚠️ The quota band of (4) is a SEAT band by design and cost stays advisory until `round --seats` rows let the band be re-cut in cost — three Opus seats (15) cost more than six Sonnet (12), and the band cannot see that yet.
**And record what you dispatched** — `python3 scripts/command_run.py round --seats <n> --findings <n> --confirmed <n> --own-fix <n> --slices <A:done/total,…> …` — because the D-186 tripwire is evaluated with seats unknown on every row that omits it. The ledger's token columns include the SEATS' own usage (`tok_seat_*`, summed from each seat's own transcript under `<sid>/subagents/` — synchronous and background seats alike), so the tripwire has a cost leg: findings per 100K seat-tokens per run, falling while seats rise, is the manufactured-seat signal. ⚠️ **The payoff claim is a HYPOTHESIS under test, not a measured result:** more findings in round 1 predicts MORE rounds and more wall-clock, and `check_ticket_breadth.py` carries a measured `rounds ≈ 1.0 × risk-class score` model — so a wider round may converge slower, not faster. TRIPWIRE (re-based at D-191 — the 20 rows count from 2026-09-08, and the variable that changed last is per-unit-per-ANGLE sizing, not per-unit): if `/fabrik-review`'s median rounds rises above 4 over those 20 ledger rows, seat inflation is inflating convergence and the rule reverts to a per-round class budget. ⚠️ **The unit count is what the SURFACE HAS — the rule scales itself and is not a quota to spend:** a one-file diff in a small synced project yields one or two units, not eight, and only the AUTHORITATIVE seat is Opus (breadth is Sonnet, the mechanical seat Haiku) — so the spend is bounded by the UNIT count (one unit = 3 seats = 8 haiku-units), never by how idle that project's box looks; native seats bill one shared subscription across ~46 repos, so more units means more seats, and a padded unit list means a wasted account.
- **Three documented limits bound a round** (`code.claude.com/docs/en/env-vars`, `/docs/en/sub-agents`; re-check the numbers on those two pages, not here; the installed binary confirms the refusal string and the tool-use default — `command grep -aoE 'Concurrent subagent limit reached.{0,120}|MAX_TOOL_USE_CONCURRENCY\?\?[0-9]+' "$(readlink -f "$(which claude)")"` — while the subagent cap's default sits behind a minified symbol): `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (default 20, per SESSION — three hub sessions each get their own) — ⚠️ past it a seat is **REFUSED, not queued** (`Concurrent subagent limit reached … Do not retry`; a refused seat is a FAILED seat and its absence is never a clean round; spawning succeeds again when the running count drops); `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY` (default 10 — read-only tools AND subagents that EXECUTE in parallel, so a 20-seat dispatch runs 10-wide); `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` (default 3 in the binary, and a remote feature flag can move it — a seat may spawn seats; ours must not: omit `Agent` from the type's `tools` list or add it to `disallowedTools` — the documented control — and brief a type without a `tools` allow-list as a leaf, since it inherits `Agent`). `dispatch_headroom.py` trims to the concurrency cap as a HARD cap it never exceeds; below it the binding constraint on width is the box and the subscription QUOTA, not concurrency — check headroom, not the cap. (The per-session total cap `CLAUDE_CODE_MAX_SUBAGENTS_PER_SESSION` was removed and is a no-op.)
- **A seat has its own context and its own compaction** (the main conversation's rules and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` apply to it), so a brief is the whole of what it knows: pin the surface (a copy under the scratchpad plus a per-file md5), name the question and never the expected answer, and forbid home-directory reads (a seat that opens `~/.claude*` stalls). **A seat a later pass must RESUME is dispatched `run_in_background: true` and its `agentId` (from the spawn result) recorded in the round row** — that id is what `SendMessage` continues with its context intact; a synchronous seat has no resumable id, and a resume is also refused for an oversized transcript or a worktree outside the session's isolation fences; a new `Agent` call starts fresh and is not that seat. When a resume is refused, the successor is a FRESH seat on the SAME model over the SAME slice (`term-coverage.md`), briefed with that slice's claim ledger and the previous seat's REFUTED list verbatim — never a fresh whole-artifact reader.
- **Never `TaskOutput` a running seat, never `tail` its `.output`, never read its transcript** — the result arrives as a notification; `<sid>/subagents/agent-*.jsonl` is for the token ledger, not for reading.
- The loop-closing round's **FINDER pass** runs in a context that did **not author the artifact** — the round-one seats re-verifying their own slices (D-335). A post-compaction session is still the author's session, and an author's own quiet round never closes a review loop: the context that shaped the artifact is the one least able to see its gaps (an author re-reads intentions, not text). **One sanctioned exception — the solo self-convergence loop:** a command whose loop dispatches NO seat that reads the artifact for defects — no finder, grounder, auditor or reconciler — anywhere; a seat that DRAFTS a section of it is none of those (an author self-convergence pass, e.g. `/fabrik-ui-design`'s own convergence, whose per-screen seats draft the contract) closes with its own full fresh read — independence there is deferred to the PAIRED review command that follows it (`/fabrik-ui-design-review`), never silently skipped. **Adjudication — decide/refute/merge — stays with the orchestrator** (CLAUDE.md § Subagent fan-out: "the decide/refute/merge you own"); this rule governs who HUNTS last, never who adjudicates. The loop fragments' fresh/independent-round language defers to THIS definition of independent.
- Auth/identity/session/crypto · schema/migrations · secrets/`.env`/keys · security controls (RLS, rate-limits, `final_gate`) · deploy/infra. These stay with the primary (human-supervised) agent — the ticket Complexity tier `check_plan_tickets.py` names `never-route`, and the coder `dispatch_headroom.py`'s tier text names the never-route coder; a seat may READ and REPORT on them (the Opus authoritative slice), never edit them. **Never web/MCP-enable a seat carrying sensitive context** — the model's output exfiltrates via a scraped URL; `fabrik-reviewer` gets the repo and no web by construction of its type file; `fabrik-researcher` gets the web AND `Read`/`Grep`/`Glob` on the tree (no Bash, no edits) — it can read any tracked file, so never brief it onto a path carrying secrets; `design-review` carries web and edit both, so it never receives sensitive context.
- The canonical MCP server list is a hub-owned standard-format file — `/opt/fabrik/mcp.json` (`{"mcpServers": {name: {type, command, args, env}}}`, keys via `${ENV}` expansion, never inline).
**Since the 2026-08-30 MCP split, MAIN-AGENT servers are per-repo:** each repo's `.mcp.json` (project scope — gitignored, because postgres-pro's env carries the repo's resolved `DATABASE_URL`) is EMITTED by the hub's `scripts/sysadmin/emit_mcp_project_config.py` from the roster-ruled sets in `docs/workstation/mcp-roster.md`; the user-level rosters carry only the universal 6. Never hand-edit an emitted `.mcp.json` — change the roster/ledger ruling, then re-run the emitter.
- Adding a tool touches exactly: the roster ruling + emitter table (main agents, per repo) → `mcpServers` in the relevant agent type under `commands/_agents/` (then re-render) → `/opt/fabrik/mcp.json` — never a command brief.
- When a project fixes a real bug in a **vendored `fabrik-lib` module** (e.g. `libs/subagents/`, `libs/health_probe/`), it MUST append the fix — symptom + fix + date — to `/opt/fabrik-lib/<module>/UPSTREAM_FEEDBACK.md`. That file is the **one write allowed back into `/opt/fabrik-lib`** (cross-repo HARD STOP otherwise); the module author reads + resolves it, so the fix isn't silently lost on the next re-vendor. Fixing a vendored module without the entry breaks the loop. The hub itself never edits `libs/subagents/` (D-137) — a wanted change is a mail to fabrik-lib.

# promote-to-check_*: tail elided (116 greppable mandate literals; the full mandates are above)
```

| # | Class | Verdict | Evidence (paths hunted) |
|---|---|---|---|
| 1 | FLOOR core/35-security-auth — secrets, auth, input handling | CLEAN | no secret, credential or auth surface in any of the 11 tickets; `work.py`'s git calls take argv lists and item ids validated by `W-[0-9a-f]{8}` (T01b); paths hunted: T01a–T10, spec § Shape / infra |
| 2 | FLOOR core/25-data-postgres — no database is introduced | CLEAN | no database, migration or SQL anywhere in File Scope (spec § Shape / infra); hunted all 11 tickets |
| 3 | FLOOR core/30-ops — no container, compose or port | CLEAN | no container, compose file, port or deploy step; hunted File Scope and T10's adoption steps |
| 4 | FLOOR 12-FACTOR (all twelve axes) — § Global Constraints | CLEAN | § Global Constraints states the 12 axes for repo tooling (XI stdout/stderr only, VIII no daemon — read-time lease expiry, X no backing service, III env + committed config) |
| 5 | MATCHED core/10-python — typed stdlib code, no file logging | CLEAN | T01b's API signatures are typed; no file logging (warnings to stderr/stdout, T04 step 4); hunted T01a, T01b, T02, T03, T04 |
| 6 | MATCHED core/40-documentation — rendered blocks, the doc landing sites | FIXED | pass 1: T09's verb-parity row got its own test (C-S3), intel's citation corrected to `:77-78` (C-S2); the BACKLOG block stays `render`'s alone (T03) |
| 7 | MATCHED core/45-testing-strategy — a test per behaviour, seen red | FIXED | pass 1: `set_next` row added to T04 (A-O12); T07 rows 2–3 got `tests/test_work_distribution.py` (C-S1); the V4 row now runs `done` from a linked worktree (A-O10); T02 gained the uncommitted-item row (A-O16) |
| 8 | MATCHED core/62-using-subagents — the dispatch policy | CLEAN | § Execution Discipline names native seats, `scripts/sysadmin/dispatch_headroom.py` (path corrected in pass 1) and the Opus/Sonnet coder split |
| 9 | MATCHED ai/00-ai-model-selection — no pinned model ID | CLEAN | T09's intel.md edit names no model ID; no ticket pins one |
| 10 | fail-open vs fail-closed on every gate/guard — hooks open, CLI loud, the gate row's flag | FIXED | pass 1: `has_store` gates every API call before the lock (A-O1, A-O17); T05 passes `--repo` only from a payload cwd (A-O14); WHERE YOU ARE keeps the slot line when the store lacks the item (A-O4); `done`/`claim` refused on awaiting items (A-O6); pass 2: the clear guard clears as today when no pre-pass ran (A-O21); `answer` writes a closed marker so a worktree's stale copy stops showing (A-O22); the cross-tree display and answer were DELETED in pass 4 (A-O15 → A-O23/26/27/31/33 each regenerated the class) and the limit recorded in § Residual unknowns |
| 11 | cost / quota / limit edges — the 2 s / 10 s lock waits inside the 5 s harvest; the READ budgets; the 7-day window | FIXED | pass 1: the Stop harvest makes ONE store call under one ≤ 2 s lock inside the 5 s subprocess timeout, decision item first (A-O2); the prompt path never writes the store but for the second chance (A-O3); T02's READ budget brought under 262 KB by quoting three signatures; pass 2: the second chance creates every missing slot in ONE `ensure_decision_items` call under one ≤ 2 s lock (A-O3); the marker prune runs last (A-O25) |
| 12 | boundary / sentinel / prefix — `W-` ids, digests, the BACKLOG markers, the sync regex alternation | FIXED | pass 1: the sync filter cited at its real line `:164` (A-O13); an empty session id refuses `claim` and a subagent acts as its parent (A-O8); pass 2: slots store and compare the `repo_root()` toplevel, never a raw cwd (A-O24) |
| 13 | behaviour without a test — every G/W/T row names its grader | FIXED | pass 1: A-O12, C-S1, C-S3 each gained a named test; every G/W/T row in the 55-row roll-up names a test file in its ticket's Touches; pass 2: T07 row 1 moved into `tests/test_work_distribution.py` (C-S1); T01b rows 6 and 8 now cover `answer`'s marker and the batched call's no-store case |

## Pass Ledger

| Pass | seats · axes re-checked (claims · gates · interfaces · completeness) | counters | method | set md5 (start → end) |
|---:|---|---|---|---|
| Pass 1 | opus×1 (A: spine rule/grammar sections + T01b, T04, T05) + sonnet×1 (B: T01a, T02, T03) + sonnet×1 (C: T06–T10) + 3 refuters · all nine classes | found: 25, new: 25, confirmed: 23, fixed: 23, unexecuted: 0, edits: 23 | method: citation — the full partitioned pass (Workflow run wf_dd9bc972-520); every candidate executed by its slice refuter, 2 refuted (A-O7, C-S4); the orchestrator re-ran the load-bearing ones (the filter at `.pre-commit-config.yaml:164`, intel `:77-78`, `resolve_agent_name` at `scripts/whoami_agent.py:259`, spec:153 on awaiting items, the Stop hook attributing only tool-edited files at `.claude/hooks/final_gate_stop.py:346`); roll-up 55 = 55; emit gate 11 tickets, 33 Touches, 43 Context Files, 0 findings | 8fc603a7 → f6e2de64 |
| Pass 2 | opus×1 (A) + sonnet×1 (B) + sonnet×1 (C), the round-1 slice owners, + refuters · their ledgers over the fix diff plus one hop | found: 8, new: 7, confirmed: 7, fixed: 8, unexecuted: 1, edits: 12 | method: re-derivation — 20 of 23 ledger claims re-executed NOW_FALSE, A-O3/A-O16/C-S1 STILL_TRUE; 5 new, all inside pass 1's own fix hunks (own-fix 7 of 7): the uncapped per-slot second chance, the clear guard with no pre-pass, `answer` without a marker, a worktree-only item unclosable from main, the raw-cwd slot repo; A-O25 unanswered by its refuter and fixed anyway (the prune runs last); A-O9's one-hop residue (T10, the spine's residual line) fixed | e934be2a → 5d7c0812 |
| Pass 3 | opus×1 (A) + sonnet×1 (C), the round-1 owners of the two slices with open claims, + refuters · their ledgers over the pass-2 fix diff plus one hop; slice B closed at pass 2 | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 9 | method: re-derivation — 8 of 8 ledger claims re-executed NOW_FALSE; the budget re-derived from primary sources (`scripts/thread_anchor.py:179-180`, `.claude/hooks/final_gate_stop.py:2648`, the 10 s prompt-hook timeouts): compact path 1 + 2 + 5 = 8 s < 10 s; 5 new, all inside pass 2's own fix hunks (own-fix 5 of 5); scope-growth stop fired (7/7 → 5/5); class rewrite — T01b's cross-worktree `answer` paragraph (the marker-apply step deleted: `answer` refuses an item held in another tree); A-O29 recorded as a named limit in § Residual unknowns; A-O30 corrected to D-271 | 7c9da240 → fa4fd4e3 |
| Pass 4 | opus×1 (A), the round-1 owner, + refuter · the fixed set only, under the scope-growth stop | found: 3, new: 3, confirmed: 3, fixed: 3, unexecuted: 0, edits: 5 | method: re-derivation — 5 of 5 ledger claims re-executed NOW_FALSE (D-271 checked at `docs/DECISIONS.md:399` and `scripts/whoami_agent.py:416`); 3 new, all inside pass 3's own rewrite (own-fix 3 of 3): the refusal's merge route, the V6 resolution step's missing reader, the reverse cross-tree direction; class rewrite — the cross-tree display and answer DELETED (T01b's `prompt_block` and `answer` bullets, row 6), the linked-worktree limit recorded once in § Residual unknowns with a concrete reader | 134b8d89 → 512241bd |
| Pass 5 | opus×1 (A), the round-1 owner, + refuter · the pass-4 deletion only, under the scope-growth stop | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 2 | method: re-derivation — 3 of 3 ledger claims re-executed NOW_FALSE; 0 dangling references to the deleted cross-tree mechanism in 12 of 12 files (`grep -rnEi` over the pin); the Residual-unknowns reader's commands exist (`scripts/thread_anchor.py:278`, `git worktree list --porcelain`, T02 `status`); 1 new inside pass 4's own bullet (own-fix 1 of 1): the V6 reader is a same-day sample — the overclaim deleted, the bullet now says so; the recorded unknown-id gap fixed in T01a | b6b00d98 → 57f1e333 |
| Pass 6 | opus×1 (A), the round-1 owner, + refuter · pass 5's two edited sentences only | found: 1, new: 1, confirmed: 1, fixed: 1, unexecuted: 0, edits: 3 | method: re-derivation — the ledger claim re-executed NOW_FALSE (the same-day-sample sentence matches T04's 7-day slot scan and the clear at `scripts/thread_anchor.py:535`); both sentences true and consistent with T01b's own-tree rule; 1 new inside pass 5's own sentence (own-fix 1 of 1): the unknown-id rule had no Behavior-Contract row — T01a row 8 added; the seat's recorded pointer (T10's V6 item did not name the linked-worktree reader) fixed | 215340b4 → 0116b1a0 |
| Pass 7 | opus×1 (A), the round-1 owner · pass 6's edits only (T01a row 8, T10 step 3, the regenerated roll-up), under the scope-growth stop | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the ledger claim re-executed NOW_FALSE; the roll-up EXECUTED: every `- **Given**` line of T01a..T10 in order (8, 8, 7, 5, 8, 5, 4, 3, 3, 2, 3 = 56) diffed against the spine's 56, identical; T01a row 8 testable by `tests/test_work.py`, within the 8-row cap; RECORDED, not counted: T01a's executor makes the unknown-id check run before the distributor check (row 8's Then names the id and tree, which tells the two refusals apart); checklist row 13's '55-row' is pass 1's historical count | 5d84eb5b → 5d84eb5b ✓ → **CONVERGED** |

## Residual unknowns

**Resolved:**
- The Task-tools env overrides the extension's forced `0` from a project `.claude/settings.json` (probe, § Evidence).
- The hub distributor is intel (D-395).
- `work.py` needs its own entry in the sync filter (T07).
- The spec's 253/36 is a stale snapshot; V2 re-derives the counts (T03).

**Open, each with its resolution step:**
- **Whether the one store lock stays uncontended.** Every wait over 0.1 s is recorded in `readings.jsonl` from day one (T01a). The spec § Lifecycle growth trigger governs; V6 reads it on 2026-10-08, and T10 creates that item.
- **The hub windows are unnamed** (`CLAUDE_AGENT` unset, no `whoami_agent.py` binding). Until each is named — `CLAUDE_AGENT` at launch, or `python3 scripts/whoami_agent.py --as <name>` in the live window, the resolver `work.py` uses (T01a) — `assign` cannot target a window, and `ready --mine` falls back to unassigned items. This is an operator action, named in T10.
- **A decision harvested in a linked worktree is shown and rescued only in that worktree.** `prompt_block` reads the caller's own tree (T01b), and the second chance keys slots by the resolved toplevel (T04 step 4), which for a linked worktree is that worktree's path. A deliberate deferral of spec § Validation V1's "every session in the repo" for linked worktrees: every cross-tree mechanism this review tried (pass 1 → pass 4) generated a new defect each round, and deleting it beat patching it. Resolution step, at the V6 reading on 2026-10-08 (T10's item): run `git worktree list --porcelain`, and for each linked tree `python3 scripts/work.py status` there plus a scan of its `.fabrik/work/` for `awaiting-operator` items and of the anchor dir for slots whose `repo` is that tree; if either finds one, re-key slots and `prompt_block` by the git common directory in a follow-up change. The reader is a same-day sample — it sees only worktrees still listed and slots not yet cleared that day — so an empty result does not prove the case never happened; it only finds a live one.
- **Existing account dirs lack the `tasks/` link until relinked.** The operator re-runs `claude_rotate.py --new-dir <slug> <email>` per account (T10). Until then, a rotation flip hides an in-session Task list, which is not the record.
