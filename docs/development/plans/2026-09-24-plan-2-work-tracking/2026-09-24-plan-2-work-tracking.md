# Plan — work tracking: one open-work record per repo, shared by its three agents

Status: DRAFT
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
    slot's OPEN DECISION line prints only in a repo with no store (T04 step 5).
  - `tasks/` joins `_SHARED_DIR_LINKS` and `_SHARED_DIR_MKDIR` in `claude_rotate.py`; linking the
    existing account dirs is an operator action (T10).

## Ticket Board

| Ticket | Title | Depends | Parallel | State | Commit |
|---|---|---|---|---|---|
| T01a | Store core: init, items, lock, add/assign/ready/next | — | ⛓️ | ⬜ | |
| T01b | Claims, leases, closing verbs, hook-facing API | T01a | ⛓️ | ⬜ | |
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

## Interfaces

- **T01b → T04, T05 — the hook-facing API** in `scripts/work.py`: `ensure_decision_item(repo, *, block,
  msg_digest, session, lock_timeout=2.0) -> str | None`, `has_msg_digest(repo, msg_digest) -> bool`,
  `renew_claims(repo, session, lock_timeout=2.0) -> int`, `set_next(repo, item_id, text,
  lock_timeout=2.0) -> bool`, `prompt_block(repo, session) -> str`; all fail open. Seam tests:
  `tests/test_thread_anchor.py` (T04, in-process via the real script) and `tests/test_work_hook_seam.py`
  (T05, the real Stop hook end to end).
- **T04 → T05 — `thread_anchor.py harvest --repo <root>`**, the slot's `repo` field, and `line --hook`
  printing `prompt_block` first. Seam test: `tests/test_work_hook_seam.py` (T05).
- **T02 → T06 — `work.py sync --check`'s exit contract:** 0 when there is no store or the repo is not
  yet blocking; non-zero only when blocking and classes 2–6 drift. Seam test:
  `tests/test_final_gate_work_row.py` (T06).
- **T03 → T10 — `migrate-backlog` + `render`** on the hub backlog; checked by T10's V2 reading in the receipt.
- **T07 → T10 — `CORE_SCRIPTS` lists `work.py`**; the fleet broadcast in T10 relies on it having synced.

## Execution Discipline (binding on /fabrik-execute-plan)

- **Review floor** — "every ticket, on the coder's return, runs `/fabrik-review` on its changed
  surface to a coverage-adjudicated exit BEFORE its merge; no ticket merges on a first-pass green."
  Every ticket here is heavy by the lane table (a governance-sync path, a hook, the gate, or a new
  mechanism with concurrency), so the review is the full `/fabrik-review`, never the scoped one. A
  governance-sync merge (T04, T05, T06, T07, T08) distributes to ~46 repos AT MERGE, so its review
  closes before the merge, and a plumbing commit is followed by a hand-run
  `bash scripts/governance_sync_postcommit.sh`.
- **Dispatch policy** — native Claude seats for every fan-out (the pool is OFF, D-181/D-182):
  `dispatch_headroom.py` then `command_run.py dispatch --seats N` before each fan-out. Coders: Opus for
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
- **Given** one ready item, **When** three processes run `claim <id>` at the same instant, **Then** exactly one exits 0 and holds the claim, and the other two exit non-zero naming the holder (spec § Validation V3)
- **Given** a claim whose lease has passed, **When** `ready` runs, **Then** the item is listed as ready, and a new `claim` succeeds with a higher token (spec § Validation V3)
- **Given** session A's claim expired and session B took it over, **When** session A runs `done <id> --evidence <sha>`, **Then** it is refused for a token mismatch and the item is unchanged (spec § Validation V3)
- **Given** a linked worktree of the repo, **When** a claim is made from the worktree, **Then** `ready` in the main checkout stops listing that item at once (spec § Validation V3)
- **Given** a claimed item, **When** `done` runs with no evidence, with a SHA that does not resolve, or with a commit whose message does not name the id, **Then** each is refused; with a commit naming the id it succeeds and writes a closed marker, and the main checkout's `ready` no longer lists the item (spec § Validation V4)
- **Given** an `awaiting-operator` item, **When** `drop` runs, **Then** it is refused; **When** `answer <id> --note "<words>" --decision D-001` runs, **Then** the item is `done` with the note and the decision link (spec § Cobra)
- **Given** an item assigned to `fleet` and a distributor `intel`, **When** `drop <id> --why x` runs as `infra`, **Then** it is refused; as `fleet` or `intel` it succeeds and the reason is kept in `note` (spec § The CLI)
- **Given** a store and a DECISION block, **When** `ensure_decision_item` runs with a new message digest, then the same digest, then a new digest while the item is open, then a new digest after the item was answered, **Then** it creates one item, does nothing, adds the second digest to the same item, and creates a second item; on a repo with no store it returns `None` and writes nothing (spec § NEXT, DECISION blocks and the register)
- **Given** a fixture repo with one spec and one plan per drift class 1–8 plus one clean spec and plan, **When** `status` runs, **Then** each class lists exactly its fixture paths and the clean ones appear in none (spec § Spec and plan state is derived, never copied)
- **Given** plan spines with `Status: IN_PROGRESS`, `COMPLETE`, `PLANNED` and `WEIRD`, **When** `status` runs, **Then** the first three are read as `IN-PROGRESS`, `EXECUTED` and `DRAFT`, and only `WEIRD` is listed under class 8 (spec § Spec and plan state is derived, never copied)
- **Given** a `done` item from the last 14 days whose evidence SHA does not name it, a `legacy` one, and a closed marker older than 14 days whose item is still open, **When** `status` runs, **Then** the first and the marker are class 6 and the legacy item is not (spec § Spec and plan state is derived, never copied)
- **Given** an initialised repo with class-3 drift and no `migrated_at`, **When** `sync --check` runs, **Then** it exits 0, prints the drift, and appends one reading line holding the per-class counts (spec § Spec and plan state is derived, never copied)
- **Given** `migrated_at` and readings clean for classes 2–6 on 7 consecutive days after it, **When** `sync --check` runs on class-3 drift, **Then** it exits non-zero; with only 6 such days it exits 0 (spec § Lifecycle)
- **Given** a repo with no `.fabrik/work/`, **When** `sync --check` runs, **Then** it prints one line, exits 0 and creates nothing (spec § The CLI)
- **Given** a fixture backlog with one row of every shape above, open and resolved, **When** `migrate-backlog` runs, **Then** every row becomes exactly one item, resolved rows are `done` with `legacy: true`, the others `open` with the owner from the tag, and each row's full text is kept (spec § The backlog becomes a view)
- **Given** a row no shape matches, **When** `migrate-backlog` runs, **Then** it becomes an item with an empty owner and the raw text kept, and the run's output lists it for the distributor (spec § The backlog becomes a view)
- **Given** a migrated store, **When** `migrate-backlog` runs again, **Then** it creates no item (spec § The backlog becomes a view)
- **Given** a copy of the hub's `docs/STRATEGIC_BACKLOG.md`, **When** `migrate-backlog` then `render` run, **Then** the item count and the open/done split equal what the test's own independent reader counts in that copy, and every source row's text appears in its item (spec § Validation V2)
- **Given** a rendered backlog, **When** `render` runs again, **Then** the file is byte-identical, and hand-written text above and below the block is untouched (spec § The backlog becomes a view)
- **Given** an initialised temp repo, **When** `harvest --decision-ok --repo <repo>` runs on a message with a DECISION block, **Then** one `awaiting-operator` item exists holding the message digest and the slot stores `repo` (spec § NEXT, DECISION blocks and the register)
- **Given** that item, **When** a second message carrying a different DECISION block is harvested the same way, **Then** a second item exists and the first is unchanged (spec § Validation V1)
- **Given** a slot stored with `repo` whose Stop-side item write failed, **When** the next UserPromptSubmit `line --hook` runs, **Then** the item is created from the slot before it clears; if that write fails too, the prompt output carries one warning line (spec § NEXT, DECISION blocks and the register)
- **Given** a block answered and then re-asked word for word in a new message whose Stop-side write failed, **When** the next UserPromptSubmit runs, **Then** a new awaiting item is created, matched by the message digest (spec § Review — Pass Ledger, RECORDED)
- **Given** two awaiting items created by two different sessions, **When** a third session's `line --hook` runs on UserPromptSubmit and on SessionStart `source=compact`, **Then** both questions print at the top of its output, unfolded (spec § Validation V1)
- **Given** a claim held by the session, **When** a Stop harvest runs with `--repo` and the message has no `NEXT:` line, **Then** the claim's lease is renewed (spec § Identity, the lock, the lease)
- **Given** no `--repo` and no payload `cwd`, **When** any `thread_anchor.py` command runs from inside an initialised repo, **Then** no store is read or written (grounding risk 2)
- **Given** an initialised temp repo, **When** the real Stop hook runs on a final message ending in a valid DECISION block, **Then** the repo's store holds one `awaiting-operator` item for it (spec § Validation V1)
- **Given** that item, **When** a second Stop from another session ends on a different valid DECISION block, **Then** the store holds two awaiting items (spec § Validation V1)
- **Given** the two items, **When** a third session's `thread_anchor.py line --hook` runs on UserPromptSubmit and then on SessionStart `source=compact`, **Then** both questions print, unfolded, in both outputs, and they still print after that session's own state file is deleted (spec § Validation V1)
- **Given** a claim held by a session, **When** the Stop hook runs for that session on a message with no DECISION block, **Then** the claim's lease is renewed (spec § Identity, the lock, the lease)
- **Given** a repo whose `scripts/thread_anchor.py` does not know `--repo`, **When** the Stop hook runs, **Then** the harvest argv carries no `--repo` and the Stop is allowed as before (spec § Lifecycle — Degradation)
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
| Fleet-synced surfaces | `scripts/work.py` joins `CORE_SCRIPTS`; the hooks, gate, settings and template are sync triggers | `scripts/fabrik_synced_manifest.py:37-62`, `:261`; `.pre-commit-config.yaml:163` |

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
- templates/governance/CLAUDE.md
- CLAUDE.md
- tests/test_work_contract_rule.py
- docs/reference/work-tracking.md
- docs/workstation/hooks-index.md
- docs/reference/thread-anchors.md
- docs/reference/multi-agent-operating-model.md
- docs/reference/agents/intel.md
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
- T07 `scripts/fabrik_synced_manifest.py:37-62` (`CORE_SCRIPTS`), `.pre-commit-config.yaml:163`.
- T08 `CLAUDE.md:631`, `templates/governance/CLAUDE.md:629`, `:701`, `tests/test_governance_template_split.py:1122`.
- T09 `docs/workstation/hooks-index.md:171`, `docs/reference/thread-anchors.md:59-74`,
  `docs/reference/agents/intel.md:76-77`.
- T10 `scripts/sysadmin/claude_rotate.py:1431`, `:1436`, `:1912`, `:1929`, `tests/test_claude_fleet.py:828`.

The Task-tools probe (T07), a temp git repo, run with `CLAUDE_CODE_ENABLE_TASKS=0` exported, the
`system/init` event's tool list:

```
with-env tools= 106 ['Task', 'TaskCreate', 'TaskGet', 'TaskList', 'TaskStop', 'TaskUpdate']
no-env tools= 102 ['Task', 'TaskStop']
```

The governance-sync filter (`.pre-commit-config.yaml:163`), applied with Python `re`:

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
- `ensure_decision_item`, `has_msg_digest`, `renew_claims`, `set_next`, `prompt_block` are named identically in T01b (producer), T04 (consumer) and § Interfaces.
- `--repo` is named identically in T04 and T05.
- The `sync --check` exit contract reads the same in T02 and T06.

**Fixed point.** Not claimed here. Convergence is `/fabrik-plan-review`'s.

## Residual unknowns

**Resolved:**
- The Task-tools env overrides the extension's forced `0` from a project `.claude/settings.json` (probe, § Evidence).
- The hub distributor is intel (D-395).
- `work.py` needs its own entry in the sync filter (T07).
- The spec's 253/36 is a stale snapshot; V2 re-derives the counts (T03).

**Open, each with its resolution step:**
- **Whether the one store lock stays uncontended.** Every wait over 0.1 s is recorded in `readings.jsonl` from day one (T01a). The spec § Lifecycle growth trigger governs; V6 reads it on 2026-10-08, and T10 creates that item.
- **The hub windows are unnamed** (`CLAUDE_AGENT` unset). Until the operator names them, `assign` cannot target a window, and `ready --mine` falls back to unassigned items. This is an operator action, named in T10.
- **Existing account dirs lack the `tasks/` link until relinked.** The operator re-runs `claude_rotate.py --new-dir <slug> <email>` per account (T10). Until then, a rotation flip hides an in-session Task list, which is not the record.
