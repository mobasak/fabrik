# Work tracking — one open-work record per repo, shared by its three agents

Status: CONVERGED (2026-09-24, /fabrik-spec-review — 4 passes, confirmed 30 → 9 → 5 → 0; see § Review — Pass Ledger)
Profile: full — the brief adds a new component (an item store and its CLI); most Intake items have no code behind them today.
Owner: infra
Date: 2026-09-24

## Personas

- **The operator (primary).** In their words: *"we have specs, plans, we have stragetic_backlog. while agents are working all must be synced and maintained and updated properly, in each repo 3 different agent is working. one agent is managing the distribution of tasks and responsibilities. next is good feature. so we need our own tracking system."* They want to see what is waiting for them without asking, and never have to chase an agent for a step it forgot.
- **The distributor agent** — one per repo. It decides who owns which item (`work.py assign`). By default this is the repo's merge owner: the last `MERGE OWNER:` row, read by `scripts/decisions.py --merge-owner` (`scripts/decisions.py:586`).
- **The worker agents** — the other sessions in the repo (three sessions share one working tree today). Each takes an item (`claim`), does it, and closes it with evidence (`done`).
- **Automated consumers:**
  - the prompt hooks (`scripts/thread_anchor.py line --hook`, SessionStart and UserPromptSubmit), which show a session its items;
  - the Stop hook's harvest (`thread_anchor.py harvest`), which turns an accepted DECISION block into an awaiting-operator item and renews the session's claims;
  - the completion gate, which runs `work.py sync --check`;
  - the daily pipeline, which renders `docs/STRATEGIC_BACKLOG.md`;
  - fleet repos' agents, which get `work.py` through the governance sync.

**Step budgets (frozen).**
- Operator: open any session in the repo → the prompt shows every item waiting for them, never folded (1) → answer in plain words (2). The agent that receives the answer closes the item with `work.py answer <id> --note "<the operator's words>"`, and the item is on its own prompt when it does.
- Worker: `work.py next` shows its highest-priority ready item (1) → `claim` (2) → the work, committed with the item id in the message → `done --evidence <sha>` (3).
- Distributor: `work.py status` shows unowned and drifting work (1) → `assign` (2).

Every feature below traces to one of these personas; untraceable ones were cut.

## Goal

Every repo has one open-work record its agents keep current while they work. Backlog rows, decisions waiting for the operator, and agents' next actions become **items**. Each item has:
- an owner, set by the distributor;
- a claim that expires on its own;
- a status from a closed vocabulary;
- evidence when done.

Specs and plans are not copied into it. Their state is read from the documents themselves, and a sync check reports where the documents and the items disagree.

## Why this exists

The motivating failure, measured 2026-09-24 in the hub. An operator decision awaited on `docs/superpowers/specs/2026-09-19-enforcement-git-decoder-design.md` was lost, in four ways:
1. `scripts/thread_anchor.py` keeps ONE decision slot. `state["decision"]` is overwritten at `:496` and cleared at `:535`, so a later DECISION block replaced it.
2. Its anchor, 107 h old, was folded into "5 older thread(s)" by the 72 h fold (`_FOLD_AGE_S`, `:128`), beside 4 dead anchors over 590 h old.
3. Its text was stale ("/fabrik-spec …" after the spec existed).
4. The agent then closed with `NEXT: none — terminal`.

The same weakness shows fleet-wide. Three seats measured it (read-only, 2026-09-24), and the lead re-ran the headline numbers:

| Surface | Measured |
|---|---|
| `docs/STRATEGIC_BACKLOG.md` (25 of 45 repos have one; 9 are the unfilled template) | Hub header says "16 open items" (Last Updated 2026-08-25); 253 open rows measured; 36 resolved rows still in the file; 1 of 15 sampled open rows already done before it was filed. Row formats differ per repo (four shapes in the hub file alone); some repos have 0 owner tags and 0 dates. |
| Plans (463 spines, 18 repos) | About 30 ad-hoc Status values. 34 plans CONVERGED with no `.fabrik/plan-locks` entry, 33 of them for more than 7 days (17–82 days); 8 IN-PROGRESS with no lock. Hub: 11 CONVERGED plans without a lock, 10 of them for more than 7 days. |
| Specs (226 before this spec, 14 repos) | 191 CONVERGED; **none carries an approved state** — approval lives only as a `docs/DECISIONS.md` row. 14 CONVERGED specs are named by no plan. |
| Operator decisions awaited | About 144 lines of prose ("awaiting", "operator decision", "approval owed") across 13 repos; 0 backlogs have a structured awaiting field. |
| Distribution | Agent-1 merges only (`docs/reference/multi-agent-operating-model.md:94-96`). `scripts/epic_order.py --assign` is a one-shot round-robin into epic frontmatter. The intel charter: "The epic/ticket dispatcher lane is DEFERRED until a real epic queue exists (recorded, not built)" (`docs/reference/agents/intel.md:77-78`). Plan locks carry no owner. Nothing links a backlog row to a spec or plan. |
| Per-session memory | 87 thread-anchor state files; 20 open anchors, 16 of them 7–30 days old. They are per session, so once a session ends nobody reads them. |

How the approach resolves it:
- A waiting decision becomes its own item, never a slot, so a second one can't overwrite the first.
- Items live in the repo, not in one session's state, so they outlive the session.
- The prompt shows awaiting items unfolded.
- Ownership and claims give the distributor something to assign and a worker something to take.
- The backlog becomes a rendered view of the items, so its header can no longer lie.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "we have specs, plans, we have stragetic_backlog. while agents are working all must be synced and maintained and updated properly" | IN | § Chosen approach — Sync check; Backlog becomes a view |
| I2 | "in each repo 3 different agent is working" | IN | § Chosen approach — Claims; § Constraints (shared tree) |
| I3 | "one agent is managing the distribution of tasks and responsibilities" | IN | § Personas — the distributor; § Chosen approach — Ownership |
| I4 | "next is good feature" | IN | § Chosen approach — NEXT and the register |
| I5 | "so we need our own tracking system" | IN | § Chosen approach (our own store); § Rejected alternatives (C, the native Task list) |
| I6 | "should we create a next ledger for all running agents so that they dont forget again as like you do now?" | IN | § Chosen approach — items outlive the session; awaiting items never fold |
| I7 | "1 yes we can enable task tools" (D-392) | IN | § Chosen approach — The native Task list (enabled as an in-session checklist, never the record) |
| I8 | "2 if you refuse next:none if there is nothing to be done, agent will start making up unnecessary tasks in next field, this is not what we want. we want to keep track of next items properly" (D-392) | IN | § Constraints — no NEXT gate; § Cobra |
| I9 | "3 no i will not do that" — keep `scripts/thread_anchor.py` (D-392) | IN | § Chosen approach — NEXT and the register (the register stays and feeds the store) |
| I10 | the lost decoder approval (single slot overwritten, 72 h fold, stale anchor text, "NEXT: none — terminal") | IN | § Why this exists; § Validation V1 replays it |
| I11 | "you forgot again. before implementing this you said this was the next" — the decoder spec's approval is still owed | IN | § Lifecycle — adoption seeds it as the hub's first awaiting-operator item |
| I12 | "are you sure this is the best practise?" | IN | § External dependencies and practice (live, 2026-09-24) |

Intake: 12 items — 12 IN, 0 OUT-OF-SCOPE, 0 ASK.

## What exists today (grounded)

- **Backlog.** Bullets `- **[tag] title (date)** — …` with tags `[infra] [fleet] [intel] [operator]` (`docs/STRATEGIC_BACKLOG.md:12-19`). Resolved rows are struck through or prefixed `[RESOLVED …]`. No checker validates the row format.
- **Plan state.** Spine `Status:` plus the `## Ticket Board` glyphs (⬜ 🔵 🟡 ✅ 🔴) and `.fabrik/plan-locks/<id>.json` (`{plan, owned_paths, branch, started_at, status}`). `docs_updater.py` renders the `AUTO-GENERATED:PLANS` block (`scripts/docs_updater.py:661`).
- **Spec state.** DRAFT → CONVERGED → IMPLEMENTED. Approval is a `docs/DECISIONS.md` row only.
- **Ownership.** Epic frontmatter `owner:` via `scripts/epic_order.py --assign`; a `**Owner:**` line on plans and specs; the merge owner row.
- **Thread anchors.** `scripts/thread_anchor.py`: per-session JSON under `~/.claude/state/threads/`, anchors, `last_next`, one `decision` slot. Caps `_MAX_SHOWN=4` (`:116`), `_MAX_ANCHORS=12`, `_MAX_FOLDED=50`, `_FOLD_AGE_S=72 h` (`:126-128`). The harvest is `cmd_harvest` (`:469`).
- **Cross-surface checks that exist.** A CONVERGED plan must cite a CONVERGED spec (`check_stage_artifacts.py`). An EXECUTED plan must not hold a lock (`check_plan_lock_release.py`, advisory). **None** links backlog rows, awaiting decisions or next actions to specs and plans.
- **Fleet distribution.** `scripts/thread_anchor.py`, `scripts/docs_updater.py`, `scripts/command_run.py` and `scripts/enforcement/` are fleet-synced (`scripts/fabrik_synced_manifest.py`). `epic_order.py` and `decisions.py` are hub-only.

## Chosen approach — derived plan/spec state, plus an item store for work that has no home

### Two kinds of state, two homes

| State | Home | Versioned? | Why there |
|---|---|---|---|
| **Durable item** — what the work is, who owns it, where it stands | `.fabrik/work/<id>.json` in the working tree | yes, committed with the code | outlives every session; git log of the file is its history |
| **Live claim** — who is doing it right now, until when | `$(git rev-parse --path-format=absolute --git-common-dir)/fabrik-work/claims/<id>.json` | no | the git common directory is shared by the main checkout and every worktree of the repo (executed 2026-09-24 with git 2.43: `/opt/fabrik/.git` from both), so all agents see one claim table without writing outside their own tree |
| **Gate readings** — one line per `sync --check` run | `$(git rev-parse --path-format=absolute --git-common-dir)/fabrik-work/readings.jsonl` | no | a shared-append file inside the tree would be a new merge-conflict ledger |

Worktree agents keep to the operating model's rule "never write a lock outside the tree you are in" (`docs/reference/multi-agent-operating-model.md:111-117`). They change durable items only in their own tree, and the item changes merge with their branch. The claim table is not a tree write.

### The durable item

One JSON file per item, pretty-printed with sorted keys and one field per line. Two branches that edit different fields of one item then merge cleanly line by line.

- **Id.** `W-` plus 8 hex characters of a hash of title, creator, creation time and a 4-hex random nonce. `add` creates the file with exclusive-create and retries with a new nonce if the name exists. Hash ids "prevent merge collisions in multi-agent/multi-branch workflows" (beads).
- **One file per item** follows ticks: "One JSON file per issue, versioned with your code". Three sessions never append to one shared file.
- **JSON over Markdown** follows Anthropic's harness: "the model is less likely to inappropriately change or overwrite JSON files compared to Markdown files".

Fields:

| Field | Meaning |
|---|---|
| `id`, `title` | identity |
| `kind` | `backlog` · `decision` (waiting for the operator) · `next` (an agent's owed next action) · `task` |
| `status` | closed vocabulary: `open` · `blocked` · `awaiting-operator` · `done` · `dropped`. **"Claimed" is not a stored status**: an item is claimed while a live claim file exists for it and its lease has not passed. So a crashed claimer's item becomes ready again by itself once its lease expires. |
| `priority` | 0 (urgent) to 3 (someday), default 2; set by the creator, changed by the distributor |
| `owner` | agent name, set by the distributor; empty means unassigned |
| `links` | `{spec, plan, decision}`: paths and D-ids the item tracks |
| `blocked_by` | item ids; an item is ready only when each is `done` or `dropped` |
| `next` | the concrete next action, one line |
| `evidence` | set by `done`: a commit SHA whose message names the item id |
| `legacy` | `true` only on items created by `migrate-backlog` from rows already resolved; exempt from the evidence rule |
| `question`, `ground`, `msg_digests`, `block_digest` | on `kind: decision`: the plain-words question, the DECISION ground, every message digest that created or refreshed the item, and the block digest (the identity keys, see below) |
| `note` | the last closing reason (`drop --why`, `answer --note`) |

Items are never deleted. They end `done` or `dropped` with a reason, matching the harness rule "It is unacceptable to remove or edit tests". There is no `history` field: `git log -p .fabrik/work/<id>.json` is the history, and it cannot be hand-edited the way a field can.

### Identity, the lock, the lease

- **Who is acting.** The session is `CLAUDE_CODE_SESSION_ID`, which is in an agent's shell environment (executed 2026-09-24; a different variable from `CLAUDE_SESSION_ID`, which does not exist). The agent name is `CLAUDE_AGENT`, set only when the operator names the window (e.g. `infra`). Measured 2026-09-24, it is unset in this hub session and in workflow subagents. Owners are agent names only: an unnamed session can claim and finish unassigned items, but `assign` cannot target it. For it, `ready --mine` lists unassigned ready items; its own live claims appear in the prompt block and in `status`.
- **One lock for every write.** Every write, from every verb and from the hooks, takes an exclusive `fcntl` lock on `$(git rev-parse --path-format=absolute --git-common-dir)/fabrik-work/.lock` and writes through a unique temp file plus rename. Read-modify-writes cannot interleave.
  - CLI verbs wait up to 10 s, then **fail loud** (non-zero exit, a named message); a lost write is never reported as success.
  - Hook calls wait up to 2 s and fail open, because they run inside the Stop hook.
  - Every lock wait longer than 0.1 s is recorded in `readings.jsonl` with its duration, which feeds the growth trigger.
- **The lease.**
  - A claim has `{agent, session, at, lease_s, token}`. The default lease is 2 h.
  - Any write by the claiming session renews it, and the Stop-hook harvest renews every live claim of the session at each turn end: a heartbeat that costs no extra verb.
  - `token` is a counter that increases each time the item is claimed.
  - `done` and `release` are refused unless the caller's session holds the live claim with the current token, or the item has no live claim. A session whose expired claim was taken over cannot overwrite the new claimer's result. This is the fencing token Kleppmann's lease requires.

### The CLI — `scripts/work.py` (stdlib only, fleet-synced)

| Verb | Who | What |
|---|---|---|
| `add` | anyone | create an item (`--kind --title --next --link --priority`); refuses `--kind decision` (those come only from DECISION blocks, below) |
| `ready [--mine]` | worker | `open`, unblocked items with no live claim, ordered by priority then age. `--mine` shows the caller's owned items first, then unassigned ones. |
| `next` | worker | the first item `ready --mine` would list |
| `claim <id>` / `release <id>` | worker | takes or gives up the live claim; a live claim by another session is refused |
| `done <id> --evidence <sha>` | worker | refused unless the SHA exists and its commit message names the item id. Besides changing the item in the caller's tree, it writes a closed marker (`closed/<id>.json` with the evidence) beside the claim table, so the main checkout's `ready` stops listing an item finished on an unmerged branch. `drop` writes one too. A marker is removed when the **main checkout's** committed item reads `done` or `dropped`. A marker older than 14 days is reported by `sync` (drift class 6) and stops hiding the item, because the branch was never merged. |
| `drop <id> --why <text>` | the owner, the distributor, or anyone for an unassigned item | ends an item that won't be done; refused on `awaiting-operator` items (only `answer` closes those) |
| `answer <id> --note <operator's words> [--decision D-NNN]` | the agent the operator answered | closes an awaiting item with the operator's words, and the ledger row where the repo has one |
| `assign <id> [--owner <agent>] [--priority 0-3]` | distributor | sets the owner and/or the priority |
| `status` | anyone | items by state, owner and age, plus spec/plan drift (below) and the last readings |
| `sync --check` | gate, pipeline | exits non-zero on drift classes 2–6 once blocking (class 1 and 7–8 are advisory); appends one reading line |
| `render` | pipeline, agents | regenerates the backlog's `AUTO-GENERATED:BACKLOG` block; the only writer of that block |
| `migrate-backlog` | once per repo | turns existing backlog rows into items |
| `init` | once per repo | creates `.fabrik/work/` and `config.json`; nothing else writes an item into a repo without it |

A repo without `.fabrik/work/` is untouched by every hook: no store is ever created implicitly.

### Ownership and the distributor

`.fabrik/work/config.json` names the distributor, set by `init --distributor <agent>`. Without the flag, `init` asks `python3 /opt/fabrik/scripts/decisions.py --merge-owner .` (hub-only, called by absolute path). Measured 2026-09-24, that prints `UNDECLARED` in the hub and in youtube: no repo has recorded a merge owner yet, so in practice the distributor is named at `init`. When the field is empty, `assign` is open to any agent, and `status` prints "no distributor named — set `distributor` in `.fabrik/work/config.json`".

- The distributor owns `assign` and sets owners up front. Self-claim alone lets agents take work they cannot do; the issue is titled "Agent teams: task self-claim has no role/tool-compatibility filter, so read-only teammates claim tasks they cannot do" (anthropics/claude-code#93668), and its workaround is pre-assigning owners.
- A worker's `ready --mine` lists its own items first, then unassigned ones. Any agent may claim an unassigned ready item; nothing blocks.
- This builds the dispatcher lane the intel charter deferred (`docs/reference/agents/intel.md:77-78`). The charter is updated in the same change.

### NEXT, DECISION blocks and the register (D-392: the register stays)

`scripts/thread_anchor.py` keeps harvesting `NEXT:` lines and anchors.

1. **A DECISION block becomes an item.**
   - Awaiting items come only from here. The Stop hook has already validated the block with `parse_decision_block` (`.claude/hooks/final_gate_stop.py:2332`), grounds and quotes included, before it passes `--decision-ok` to the harvest. There is no CLI path to park an item as awaiting, which is the cobra counter for parking.
   - The Stop hook passes `--repo <root>` to the harvest, so it knows which store to write. If that repo has no `.fabrik/work/`, nothing is written.
   - Two keys, both stored on the item:
     - `msg_digests`, the digests of every whole message that created or refreshed the item: the same digest the register's echo guard uses (`scripts/thread_anchor.py:476-495`);
     - `block_digest`, the digest of the DECISION block alone.
   - The harvest decides:
     - any item whose `msg_digests` holds this digest → do nothing, because this is the same message harvested again, and an answered item is never reopened;
     - otherwise, an OPEN item with this `block_digest` exists → refresh it and add this message's digest to its `msg_digests`, because the same question was asked again in a new message while still open;
     - otherwise → create a new item. A word-for-word re-ask after an answer is a new message, so it creates a new item.
   - A second, different block makes a second item.
2. **A second chance.** On the next UserPromptSubmit, `thread_anchor.py main` runs `cmd_clear_decision` before `cmd_line` (`:845-850`). So the second chance runs inside `cmd_clear_decision`, before it empties the slot. The Stop harvest records `--repo` in the stored slot beside the block. If that repo's store has no item for the block, `cmd_clear_decision` creates it there first. If that also fails, the prompt output carries one warning line, so a failed write is never silent.
3. **A NEXT naming an item id** (`W-xxxxxxxx`) updates that item's `next` field under the lock.

The prompt hook adds one block, **never folded**, at the top of `line --hook` output:
- every `awaiting-operator` item in the repo, from any session, with its question;
- this session's live claims;
- the count of ready items.

`NEXT: none` stays legal. There is no gate on it (D-392), and nothing counts or rewards items.

### Spec and plan state is derived, never copied

`work.py status` and `sync` read spec `Status:`, plan `Status:`, the Ticket Board and plan locks directly. Plan statuses are normalised first: `IN_PROGRESS` → `IN-PROGRESS`; `COMPLETE`, `DONE`, `SHIPPED` → `EXECUTED`; `PLANNED` → `DRAFT`. Any other value is reported under class 8.

Drift classes, each defined by a predicate `status` evaluates and lists by path:
1. **A CONVERGED spec that nothing carries forward.** No plan names it and no item links it. Specs marked SUPERSEDED or IMPLEMENTED are excluded. This covers the lost-decoder shape: the decoder spec is CONVERGED, no plan names it, and no item held its pending approval. A DECISIONS row naming the spec does not exclude it (D-311 names the decoder spec). Measured 2026-09-24: 14 fleet-wide.
2. **A plan CONVERGED more than 7 days** with no plan lock and no item linking it. Measured 2026-09-24: 33 fleet-wide, 10 in the hub.
3. **A plan IN-PROGRESS with no plan lock** (8 fleet-wide).
4. **A plan EXECUTED while an item linking it is still open.**
5. **An item file that doesn't parse, or a status outside the vocabulary.**
6. **An item marked `done` within the last 14 days whose evidence SHA doesn't exist or doesn't name the item.** Older items are exempt, since a deleted branch can be garbage-collected. `legacy` items are exempt. Also here: a closed marker older than 14 days whose item is still open in the main checkout (the branch was never merged).
7. Advisory: the backlog block is stale (`render` would change it).
8. Advisory: plan Status values outside the normalised set.

Classes 2–6 make `sync --check` exit non-zero once it is blocking. It joins the completion gate as an ADVISORY row first. It becomes blocking in a repo after that repo's migration, once `readings.jsonl` shows 7 consecutive days of clean readings for classes 2–6. Class 1 stays advisory, because many older converged specs will never have a plan, and the operator decides those one by one.

### The backlog becomes a view

`work.py migrate-backlog` reads the row shapes found in the fleet backlogs:
- `## [tag]` and `### [tag]` headings;
- `- **[tag] …**` and `- [ ] **[tag] …**` bullets;
- table rows under an Owner column.

Each row becomes an item:
- `kind: backlog`;
- owner from the tag;
- creation date from the row's date;
- the row's full text kept in `next` or `note`.

Rows marked resolved (struck through, `RESOLVED`, `✅`, `SHIPPED`) become `done` with `legacy: true`. A row it cannot parse becomes an item with the raw text kept and no owner, listed for the distributor. Nothing is dropped.

After migration, the item list in `docs/STRATEGIC_BACKLOG.md` is an `AUTO-GENERATED:BACKLOG` block. `work.py render` is its only writer and produces deterministic output with no timestamp, so the daily pipeline and agents never churn it. That is the same Tier-0 idea as the PLANS block ("the computable parts regenerate mechanically … No model, no drift", `.windsurf/rules/core/40-documentation.md:55`). Hand-written context above and below the block stays. New backlog work is `work.py add --kind backlog`, never an edit of the block.

### The native Task list (D-392 ruling 1)

Enabled box-wide through a settings `env` block (`CLAUDE_CODE_ENABLE_TASKS=1`, `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`). This overrides the VS Code extension's forced `CLAUDE_CODE_ENABLE_TASKS="0"`, as measured 2026-09-24. Lists are stored per account under `~/.claude-fleet/<account>/tasks/`. A new symlink shares `tasks/` across accounts, using the mechanism D-287 applies to `sessions/`, so a rotation flip doesn't hide a list.

It is an in-session checklist only. It is **not** the record, and `work.py` does not mirror it: two sources of truth are the drift this spec removes.

## Rejected alternatives

- **B — a derived view only, no store.** Two of three judges ranked B first. They weighted the cost, maintenance and reality-challenge rows above the operator's-needs rows; the brief listed those as a separate axis without saying which dominates. All three scored B as failing the operator's core asks:
  - it cannot keep things "synced and maintained", only display them;
  - it gives the distributor nothing to assign;
  - it gives three agents no claim.

  The chosen approach keeps B's strength for specs and plans, which are derived and not copied, and adds a store only for work that has no structured home.
- **A-full — every spec and plan also copied into items.** Rejected because it duplicates state the documents already hold (the panel's "fourth ledger" objection).
- **C — adopt beads or ticks.**
  - Neither models specs, plans, DECISIONS or an operator approval, and C would add a foreign tool to 46 repos.
  - beads' README says issues are now stored in Dolt, a version-controlled SQL database, rather than the JSONL-in-git design of its earlier versions. In beads issue #2489 a commenter wrote that "The JSONL model broke down badly in multi-agent scenarios where 5+ agents were updating issues simultaneously". That is a user's account, not the maintainers'.
  - ticks' one-file-per-issue layout is adopted here as a pattern, not a dependency.
- **fabrik-lib `job-queue/`** (a Postgres `FOR UPDATE SKIP LOCKED` queue). It fits a deployed worker service, not repo tooling: it needs a database in every repo's agent loop, and its jobs don't link to specs, plans or the backlog.
- **The native Task list as the record** (the D-392 direction). It can't link specs, plans or the backlog. It is per account on this box and lives outside the repo, so git never sees it. Superseded by this spec: a new D-row is minted at CONVERGED.
- **Claims inside the committed item** (a stored `claimed` status). A crashed claimer's item stays claimed forever, and worktree agents can't see each other's claims until merge. The live claim moves to the git common directory.
- **A single append-only `work.jsonl`.** Three sessions appending to one file is exactly the shared-append problem the private-index recipe exists for. One file per item avoids it.
- **The store under `~/.claude/state/`.** Machine-local and outside git. That is the property that lost the decoder decision when its session ended.
- **A lease reaper cron.** Replaced by read-time expiry plus renewal at every turn end.
- **An `await` CLI verb.** An agent could park any item as "waiting for the operator" without a validated DECISION block. Awaiting items come only from the Stop hook's accepted blocks.
- **A Stop-hook refusal of `NEXT: none`, or any item-count target.** Refused by the operator (D-392). It would teach agents to invent items.

## Lifecycle

- **Adoption.**
  1. Hub first: `work.py` and `thread_anchor.py` changes, `init --distributor <agent>` (the operator names the distributor, and names the hub windows with `CLAUDE_AGENT` so owners resolve), then `migrate-backlog` on the hub backlog (253 open, 36 resolved). The adopting agent then ends a turn with the DECISION block for the decoder spec's design approval (`docs/superpowers/specs/2026-09-19-enforcement-git-decoder-design.md`, I11), so the hub's first awaiting item comes through the same path every later one will.
  2. Then the fleet through the governance sync. Each repo's own agent runs `migrate-backlog` on a mailed request. The 9 unfilled template repos migrate to an empty store.
  3. `sync --check` is advisory everywhere at first. It becomes blocking in a repo after its migration, once `readings.jsonl` shows 7 consecutive days of clean readings for classes 2–6 (§ Chosen approach — drift classes).
- **Growth.**
  - Each item is a small file. `ready` and `status` read the whole directory.
  - Trigger: when a repo passes 2,000 item files, or `status` takes over 1 s (measured by the gate's own timer), `done`/`dropped` items older than 90 days move to `.fabrik/work/archive/`. They are moved, never deleted.
  - Trigger: when a repo's sessions exceed 3, or more than 10 lock waits over 1 s are recorded in `readings.jsonl` in one week, revisit the lock design. Not before.
- **Degradation.**
  - A `work.py` failure never blocks a Stop: the hooks call it fail-open, like `thread_anchor.py`. The one write that must not be lost, a DECISION block's item, gets a second chance on the next prompt and a printed warning if that also fails (§ NEXT, DECISION blocks and the register). CLI verbs fail loud.
  - A corrupt item file is reported by `sync` and skipped by `ready`.
  - A missing store reads as empty.
- **Retirement.** Items are plain JSON in git. Removing `work.py` leaves a readable archive, and the rendered backlog block can be frozen to plain text.

## External dependencies and practice (fetched 2026-09-24)

No runtime dependency: Python stdlib only. Practice consulted, each fetched this session:
- Anthropic, *Effective harnesses for long-running agents* — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents (exa fetch; WebFetch).
  - JSON feature list whose `passes` field agents flip.
  - "It is unacceptable to remove or edit tests".
  - JSON because "the model is less likely to inappropriately change or overwrite JSON files compared to Markdown files".
  - Each session first reads git logs, progress files and the feature list.
- Claude Code agent teams — https://code.claude.com/docs/en/agent-teams (brave search; exa fetch).
  - "Task claiming uses file locking to prevent race conditions".
  - Lead-assign vs self-claim.
  - "Task status can lag: teammates sometimes fail to mark tasks as completed" — no lease exists.
- anthropics/claude-code#93668 — https://github.com/anthropics/claude-code/issues/93668 (brave search). Title: "Agent teams: task self-claim has no role/tool-compatibility filter, so read-only teammates claim tasks they cannot do"; its workaround pre-assigns every task's owner at creation.
- beads — https://github.com/gastownhall/beads (exa search).
  - Hash ids.
  - `bd ready` = no open blockers.
  - `bd update --claim` is atomic.
  - Storage is now Dolt, a version-controlled SQL database, per the README. In issue #2489 a commenter wrote that "The JSONL model broke down badly in multi-agent scenarios where 5+ agents were updating issues simultaneously"; that is a user's account, not the maintainers'.
- ticks — https://ticks.sh/ (exa search): "One JSON file per issue, versioned with your code"; owner scoping.
- Kleppmann, *How to do distributed locking* — https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html (exa fetch): a lock should be a lease with a timeout, "otherwise a crashed client could end up holding a lock forever".
- Claude Code Task list and env vars — https://code.claude.com/docs/en/interactive-mode and https://code.claude.com/docs/en/env-vars (curl).
  - "Tasks persist across context compactions".
  - `CLAUDE_CODE_TASK_LIST_ID` "Share a task list across sessions".

## fabrik-lib verdict

| Capability | Verdict | Why |
|---|---|---|
| item store + CLI | BUILD | No module covers work tracking. The one near fit, `job-queue/` (`/opt/fabrik-lib/README.md:52`, a Postgres `FOR UPDATE SKIP LOCKED` queue), is for deployed worker services and needs a database; see § Rejected alternatives. The store is hub machinery distributed by the governance sync, not an app library, so it is not a fabrik-lib candidate. |
| store lock | reuse, with a different timeout policy | `thread_anchor.py`'s `fcntl` flock plus temp-and-rename pattern; the CLI waits 10 s and fails loud instead of the register's 1 s fail-open skip (`scripts/thread_anchor.py:180`) |
| DECISION validation | reuse | `.claude/hooks/final_gate_stop.py::parse_decision_block` (`:2332`) has already accepted the block before the harvest creates an item |
| rendered block | reuse | `docs_updater.py`'s `AUTO-GENERATED` block mechanism |

## Shape / infra

Not a deployed service. No `shape:` flags, no port, no database: repo files and a CLI. It is fleet-synced machinery, so every changed script is a governance-sync path, and each merge distributes to about 46 repos.

## Constraints

- **Shared tree.** Three concurrent sessions plus the daily pipeline share one working tree. Item files are per item, so pathspec commits never ship a sibling's hunk. The backlog's rendered block is regenerated rather than hand-appended.
- **No NEXT gate** (D-392). No item quota, score or reward.
- **Lean without loss** (D-331).
- **Constraints digest** (must-read packs from `scripts/review_rubric.py --changed scripts/work.py tests/test_work.py scripts/thread_anchor.py scripts/docs_updater.py docs/STRATEGIC_BACKLOG.md templates/governance/CLAUDE.md docs/reference/work-tracking.md`: the FLOOR core/10-python + 12-FACTOR; MATCHED core/40-documentation, core/45-testing-strategy):

| Rule (verbatim) | Source | Bearing |
|---|---|---|
| "every ticket enumerates its distinct **user-observable behaviors / acceptance criteria** and tests **each one**" | `.windsurf/rules/core/45-testing-strategy.md:20` | each verb and each drift class has a behaviour test |
| "a non-trivial behavior's test proves something only if it has been SEEN RED" | `.windsurf/rules/core/45-testing-strategy.md:22` | claim atomicity, lease expiry and evidence refusal are seen red |
| "the computable parts regenerate mechanically — `docs_updater.py` keeps … `AUTO-GENERATED:PLANS` block … No model, no drift." | `.windsurf/rules/core/40-documentation.md:55` | the backlog becomes a regenerated block |
| "**Format:** Entry under `## [Unreleased]` with `### Added\|Changed\|Fixed — Title (YYYY-MM-DD)`" | `.windsurf/rules/core/40-documentation.md:132` | every ticket's CHANGELOG entry |
| "VIII concurrency: scale out; never daemonize or write PID files" | the 12-FACTOR floor injected by `scripts/review_rubric.py` | no reaper daemon: read-time lease expiry |
| "X dev/prod parity: same backing services everywhere; no SQLite-for-Postgres" | the 12-FACTOR floor | unconstrained: tooling files, not an app backing service; no SQLite cache is introduced |

## Documentation landing sites

- `docs/reference/work-tracking.md` (new): the item schema, the verbs, the distributor, drift classes, adoption. Plus its `INDEX.md` row.
- `docs/workstation/hooks-index.md`: the prompt hook's new unfolded block, and the harvest writing decision items.
- `docs/reference/multi-agent-operating-model.md`: the distributor beside the merge owner.
- `docs/reference/agents/intel.md:77-78`: the dispatcher lane is built.
- `CLAUDE.md` + `templates/governance/CLAUDE.md` (both § FINAL OUTPUT copies): one short rule.
  - Next items and waiting decisions live in `.fabrik/work/`.
  - `NEXT:` names an item id when one exists.
  - A DECISION block creates an awaiting item.
- `docs/STRATEGIC_BACKLOG.md`: its header explains the rendered block.

## Validation

- **V1 — the lost-decoder replay.**
  1. Session A ends on a DECISION block.
  2. Session A (or B) ends on a second DECISION block.
  3. Both `awaiting-operator` items appear, unfolded, on every prompt of every session in the repo until each is answered or dropped.
  4. They survive a session ending and a compaction.
- **V2 — migration round-trip.** On the hub backlog, `migrate-backlog` then `render` yields the same open rows with owners: 253 open, 36 done, and each row's text preserved.
- **V3 — claim atomicity, expiry and fencing.**
  - Three processes claim one item at once; exactly one wins.
  - A claim past its lease reads as unclaimed and appears in `ready`.
  - After a takeover, the first claimer's `done` is refused (token mismatch).
  - A claim made from a worktree is visible to `ready` in the main checkout at once.
- **V4 — evidence.** `done` without evidence, with a SHA that doesn't resolve, or with a commit whose message doesn't name the item id, is refused.
- **V5 — drift report.** On the hub, `work.py status` lists, by path, exactly the plans and specs that the class predicates select. The test re-derives each class's set from the tree with its own plain reader at run time and compares; there is no frozen number.
- **V6 — two weeks after hub adoption.** Open items by age; drift classes 2–6 trending down; awaiting items answered vs outstanding. Read from `readings.jsonl` (one line per `sync --check` run).

## Cobra (D-253)

The cheapest way to satisfy each measure without the outcome, and its counter:
- **`done` with nothing done.** The evidence must be a commit whose message names the item id, and `sync` re-checks it. The residual path, a commit that names the id without doing the work, costs a real commit that the item's history points at, and a reviewer reading `git log --grep <id>` sees it.
- **Items invented to look busy.** Countered by no count, score or target on items anywhere, and no NEXT gate (D-392).
- **An item parked in `awaiting-operator` to stop working.** Only a DECISION block the Stop hook accepted creates one; there is no CLI path. The operator sees every such item unfolded.
- **An awaiting or inconvenient item dropped to clear it.** `drop` is refused on `awaiting-operator` items and allowed only to the owner, the distributor, or anyone for an unassigned item. Every drop keeps its `--why` in the item and in git.
- **An awaiting item closed with a made-up answer.** `answer` records the operator's words; the operator sees the item until it closes, and the item's git history shows who closed it.
- **Drift hidden by a status word outside the vocabulary.** Item statuses outside the vocabulary are drift class 5 (blocking). Plan statuses are normalised, and any other value is class 8, listed by path.

## Open / blocking unknowns

- **Resolved.** The native Task tools work on this box's models once the settings env override is set (probe 2026-09-24). Shared lists land under the account dir (probe 2026-09-24).
- **Resolved.** Agents in worktrees share the claim table through the git common directory (executed 2026-09-24), and `CLAUDE_CODE_SESSION_ID` is in the agent's shell (executed 2026-09-24).
- **Open, resolution step named.** Which agent distributes in the hub. The operator's words name the role ("one agent is managing the distribution of tasks and responsibilities"), not the agent, and `--merge-owner` is `UNDECLARED`. Resolution: the operator names it at design approval, and `init --distributor` records it.
- **Open, resolution step named.** Whether the one store lock stays uncontended with three sessions plus worktree agents. Resolution: every lock wait over 0.1 s is recorded in `readings.jsonl` from day one; the § Lifecycle growth trigger governs.
- **Open, resolution step named.** The fleet backlogs' row shapes differ (four in the hub alone). Resolution: `migrate-backlog` parses the shapes the seats found. A row it cannot parse becomes an item with `owner` empty and the raw text preserved, and it is listed for that repo's distributor. Nothing is dropped.

## Cost

Five pieces:
- `scripts/work.py` and its tests;
- `thread_anchor.py` changes (decision items, the unfolded block) and tests;
- `work.py render` owns the BACKLOG block (the only writer); `docs_updater.py` is unchanged;
- the settings env and the shared `tasks/` link;
- docs and both contracts.

Every script is on a governance-sync path, so the plan runs `/fabrik-review` per ticket, and merge order is adoption order: store and CLI, then the hooks, then the contracts.

## Decisions taken

- **Chosen: derived spec/plan state plus an item store for work with no structured home.** The judge panel ranked B first 2 to 1. Those two judges weighted the cost, maintenance and reality-challenge rows above the operator's-needs rows. The recommendation differs because all three judges scored B as failing the operator's sync and distribution asks. The split is carried to the operator's approval.
- **This supersedes D-392's "native Task list as the record" direction.** D-392's three rulings stand: tools enabled, no NEXT gate, the register stays.
- Durable items live in the working tree, one JSON file per item, never deleted. Live claims and gate readings live in the git common directory, never committed.
- "Claimed" is derived from a live claim, not stored. Claims expire when read, renew at every turn end, and carry a fencing token.
- Every write takes one store lock; CLI verbs fail loud, hooks fail open with a second chance for DECISION items.
- `done` requires a commit whose message names the item id.
- Awaiting-operator items come only from accepted DECISION blocks.
- The distributor defaults to the merge owner; with none recorded, `assign` is open to all.

## Review — Pass Ledger

| Pass | seats · axes re-checked | counters | method | spec md5 (start → end) |
|---|---|---|---|---|
| Pass 1 | opus×1 (A: the rules) + sonnet×2 (B: the rest; C: external quotes) + sonnet×3 refuters · all axes | found: 30, new: 30, confirmed: 30, fixed: 30, unexecuted: 0, edits: 30 | method: citation — full pass; every `path:line` opened, the track/ scripts re-run, each quote fetched live | 51f8529f → 30b146a8 |
| Pass 2 | opus×1 + sonnet×2 (the round-1 slice owners) + refuters · their ledgers over the fix diff plus one hop | found: 9, new: 9, confirmed: 9, fixed: 9, unexecuted: 0, edits: 9 | method: re-derivation — 30 of 30 ledger claims NOW_FALSE; 9 new inside the fix text | 30b146a8 → 1b74d661 |
| Pass 3 | opus×1 + sonnet×1 (the owners of A and B) + refuters · the pass-2 claims plus one hop | found: 5, new: 5, confirmed: 5, fixed: 5, unexecuted: 0, edits: 5 | method: re-derivation — 9 of 9 NOW_FALSE; 5 new inside the fix text; scope-growth stop fired | 1b74d661 → 3de0c559 |
| Pass 4 | opus×1 (the owner of A) · the five pass-3 claims only | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — 5 of 5 NOW_FALSE; one residue RECORDED, not counted (below) | 3de0c559 → 3de0c559 ✓ → **CONVERGED** |

RECORDED (scope-growth stop), destination: the plan's `thread_anchor.py` ticket. The second chance in `cmd_clear_decision` looks for "an item for the block", matched by `block_digest`, while the harvest decides by `msg_digests`. If a block is answered, then re-asked word for word in a new message, and the Stop harvest for that message fails, the second chance finds the answered item and creates nothing. Fix in the build: store the message digest in the slot beside `--repo`, and create the item when no item's `msg_digests` holds it.

Standing clean since pass 1: every other class. Slice C (external quotes) closed at pass 2 and slice B at pass 3. The later fixes touched only slice A's rules, plus the one Open-unknowns sentence A re-verified at pass 4.

