# Work tracking — one open-work record per repo, shared by its agents

**What:** `scripts/work.py` (stdlib only, fleet-synced via `CORE_SCRIPTS`) plus a `scripts/thread_anchor.py`
wiring. Every repo may hold one item store, `.fabrik/work/`, committed with the code: backlog rows,
operator decisions awaiting an answer, and agents' next actions become **items** with an owner, a
claim that expires on its own, a status from a closed vocabulary, and evidence when done. Design spec:
`docs/superpowers/specs/2026-09-24-work-tracking-design.md`.

**Why (measured, 2026-09-24):** an operator decision awaiting on a spec's design approval was lost —
`thread_anchor.py` kept it in one slot, a later DECISION block overwrote it, its anchor folded into
"5 older thread(s)" at 107 h old, and the agent closed with `NEXT: none — terminal`. Items live in the
repo, not in one session's transcript state, so they outlive the session; an `awaiting-operator` item
is never folded on the prompt.

## No implicit store

A repo without `.fabrik/work/config.json` is untouched by every hook and every verb but `init`:
nothing is created anywhere until `work.py init` runs once. `init` takes no lock — `config.json` is
written by an exclusive link (one winner) — and refuses if another working tree of the same
repository already has a store (every worktree shares one git common directory, so a second `init`
would fork `config.json`). Without `--distributor`, it asks
`python3 /opt/fabrik/scripts/decisions.py --merge-owner .` (hub-only, absolute path); with none
recorded, the store's `distributor` field is left empty and `assign` is open to any agent.

## Two homes

| State | Home | Versioned? | Why there |
|---|---|---|---|
| **Durable item** — what the work is, who owns it, where it stands | `.fabrik/work/<id>.json`, one pretty-printed JSON file per item, sorted keys | yes, committed | outlives every session; `git log -p` on the file is its history — items are never deleted, only ended `done`/`dropped` |
| **Live claim, closed markers, readings** | `$(git rev-parse --path-format=absolute --git-common-dir)/fabrik-work/` | no (the store's own `.gitignore` covers stray temp files) | the git common directory is shared by the main checkout and every worktree, so all agents see one claim table without a worktree writing outside its own tree (`docs/reference/multi-agent-operating-model.md:111-117`) |

## The item

Fields on every item (`W-` plus 8 hex characters, minted from a hash of title/creator/creation-time
plus a random nonce, exclusive-created so a collision just retries with a fresh nonce):

| Field | Meaning |
|---|---|
| `id`, `title`, `creator`, `created` | identity |
| `kind` | `backlog` · `decision` (awaiting the operator — created only by the Stop-hook harvest, never by `add`) · `next` · `task` |
| `status` | closed vocabulary: `open` · `blocked` · `awaiting-operator` · `done` · `dropped`. **"Claimed" is never a stored status** — an item is claimed only while a live claim file exists in the shared dir and its lease has not passed, so a crashed claimer's item becomes ready again by itself. |
| `priority` | 0 (urgent) to 3 (someday), default 2 |
| `owner` | agent name (`[a-z0-9-]{1,32}`, `whoami_agent.py`'s rule), set by the distributor; empty means unassigned |
| `links` | `{spec, plan, decision}` — paths and D-ids the item tracks |
| `blocked_by` | item ids; `claim`/`ready` treat the item as blocked until each one reads `done` or `dropped` (here, or closed by a marker elsewhere) — this, not the `blocked` status value, is what actually gates readiness today |
| `next` | the concrete next action, one line (max 300 characters); a `NEXT:` line naming an item id updates this field |
| `evidence` | set by `done`: a commit SHA whose message names the item id |
| `legacy` | `true` only on items `migrate-backlog` created from rows already resolved; exempt from the evidence rule |
| `question`, `ground`, `msg_digests`, `block_digest` | `kind: decision` only: the plain-words question, the DECISION block's `ground:` token, every message digest that created or refreshed the item, and the block's own digest |
| `note` | the last closing reason (`drop --why`, `answer --note`), or (on a migrated row) `migrated-digest:<12 hex>` |

## Identity, the lock, the lease

- **Who is acting.** The agent name is `CLAUDE_AGENT` (validated against the same `[a-z0-9-]{1,32}`
  rule, resolved by `whoami_agent.py` when present), unset in an unnamed session — such a session can
  claim and finish unassigned items, but `assign` cannot target it. The session is
  `CLAUDE_CODE_SESSION_ID`.
- **One lock for every write.** An exclusive `fcntl` flock on `fabrik-work/.lock`, re-entrant within
  one thread, guards every write through a unique temp file plus `os.replace`. CLI verbs wait 10 s
  then **fail loud** (non-zero exit, a named message, e.g. `the store lock (…/.lock) was held for
  over 10 s — nothing was written; retry`); hook-facing calls wait 2 s and **fail open**. Every wait
  over 0.1 s is appended to `fabrik-work/readings.jsonl`.
- **The lease.** A claim is `{agent, session, at, lease_s, token}`; the default lease is 2 h. Any
  write by the claiming session renews it, and the Stop-hook harvest renews every live claim of the
  session on **every** Stop — including a blocked one — so a normal turn's heartbeat costs no extra
  verb. `token` only ever grows: `done`/`release` are refused unless the caller's session holds the
  live claim at its current token, or there is none — a session whose expired claim was taken over
  cannot overwrite the new claimer's result (executed: a second session's `claim` on an already-held
  item is refused by name — `claim W-… refused: it is held by session …, token …, lease until …`).
- **Closing across worktrees.** `done`, `drop` and `answer` write the item in the caller's own tree
  only, plus a closed marker in `fabrik-work/closed/`, so another tree of the repo stops listing an
  item finished on an unmerged branch. A marker is pruned once the store's recorded base branch
  (`config.json`'s `base_branch`, read as a ref — never whatever a checkout happens to have checked
  out) reads the item `done`/`dropped`, or after 14 days (the branch was never merged), whichever
  first.

## The CLI — `scripts/work.py`

Executed against the merged script (`work.py --help`, then `work.py <verb> --help`, 2026-09-24) — 14
verbs:

| Verb | Who | What |
|---|---|---|
| `init [--distributor <agent>]` | once per repo | create `.fabrik/work/` and `config.json`; nothing else writes an item into a repo without it |
| `add --kind {backlog,decision,next,task} --title <t> [--next <t>] [--link key=value] [--priority 0-3]` | anyone | create an item; `--kind decision` is refused (those come only from an accepted DECISION block) |
| `assign <id> [--owner <agent>] [--priority 0-3]` | distributor | set owner and/or priority |
| `ready [--mine]` | worker | `open`, unblocked, unclaimed items by priority then age; `--mine` puts the caller's own first, then unassigned ones |
| `next` | worker | the first item `ready --mine` would list |
| `claim <id> [--session <s>]` | worker | take (or renew) the live claim; refused when another session holds a live claim, or the item is `blocked`/has an unresolved `blocked_by` |
| `release <id> [--session <s>]` | worker | give up this session's live claim (fenced the same way as `done`) |
| `done <id> --evidence <sha> [--session <s>]` | worker | refused without `--evidence`, with a SHA that does not resolve, or whose commit message does not name the item id |
| `drop <id> --why <text> [--session <s>]` | the owner, the distributor, or anyone for an unassigned item | end an item that won't be done; refused on `awaiting-operator` items |
| `answer <id> --note <text> [--decision D-NNN] [--session <s>]` | the agent the operator answered | close an awaiting-operator item with the operator's own words |
| `status` | anyone | items by state, uncommitted item files, plan-board ticket counts, and the eight drift classes below (read-only, no lock) |
| `sync --check` | gate, pipeline | the same drift report, plus one `readings.jsonl` line; exits non-zero only when a listed class is both `(blocking)` in its output **and** the repo has passed its blocking window (below) |
| `render` | pipeline, agents | regenerate the backlog's `AUTO-GENERATED:BACKLOG` block — its only writer |
| `migrate-backlog` | once per repo | turn existing `docs/STRATEGIC_BACKLOG.md` rows into items, idempotently (re-running adds nothing already migrated) |

`--repo <path>` (any path inside the repo, default cwd) is common to every verb. `done`/`drop`/`claim`/
`release`/`answer` default `--session` to `CLAUDE_CODE_SESSION_ID`.

## Ownership and the distributor

`config.json`'s `distributor` field names the one agent `assign` is reserved to; `init` sets it from
`--distributor`, or from the merge owner (`docs/reference/multi-agent-operating-model.md:80-86`) when
omitted. This is a **second** role beside the merge owner, not the same one: the merge owner
integrates branches into the base branch (§ Merge protocol there); the distributor sets item owners
and priorities (`work.py assign`) so a worker's `ready --mine` and a claim never collide over who
should be doing what. The two may be the same agent or different ones — `init` merely defaults to the
former when nothing else is named. In the hub, intel is the distributor (D-395), which is the
dispatcher lane `docs/reference/agents/intel.md` used to record as deferred.

## NEXT, DECISION blocks and the register

`scripts/thread_anchor.py` still keeps harvesting `NEXT:` lines and anchors exactly as
`docs/reference/thread-anchors.md` describes (D-392: the register stays). What changed is what a Stop
also does, when the repo has a store:

- **A DECISION block becomes an item.** The Stop hook passes `--repo <the payload's absolute cwd>` to
  the harvest only when it can (a script that does not yet know `--repo` is left untouched); with it,
  `harvest --decision-ok` is re-run on an ACCEPTED block only — never a refused or malformed one — and
  `work.py`'s `on_harvest` creates or refreshes a `kind: decision` item under one lock. The three
  rules: a message already stored (its digest is in some item's `msg_digests`) does nothing; failing
  that, an OPEN awaiting item with the same block digest is refreshed (its `msg_digests` grows); failing
  that, a new item is created. An answered item is never reopened by the same message harvested again;
  a word-for-word re-ask **after** an answer arrives in a genuinely new message and starts a new item.
- **Every Stop, blocked ones included, renews claims.** The plain harvest (never `--decision-ok`) runs
  on every Stop with `--repo` when the payload carries one — even when no text reached it (the
  end-of-turn flush race), it still calls `on_harvest`, which renews every live claim of the session.
  A blocked Stop still gets this heartbeat.
- **The second chance.** On the next `UserPromptSubmit`, before `thread_anchor.py`'s
  `cmd_clear_decision` empties its per-session slot, it scans every session's stored DECISION slot for
  this repo (at most 7 days old, among the newest state files) and, in one `ensure_decision_items`
  call, creates an item for any slot whose **message** digest no item already holds — never the
  block's digest, so a block answered and then re-asked word for word in a new message whose Stop
  write failed still gets its item. A write that still fails prints one warning line naming the count,
  so a lost write is never silent.
- **A NEXT naming an item id** (`W-xxxxxxxx`) updates that item's `next` field, unless another
  session's live claim holds it.

There is no `await` CLI verb and no other way to create an `awaiting-operator` item — only an accepted
DECISION block does. `NEXT: none` stays legal; nothing counts or scores items (D-392).

## Spec and plan state is derived, never copied

`status` and `sync --check` read spec `Status:` lines, plan `Status:` lines, Ticket Boards and plan
locks directly — nothing about a spec or plan is copied into an item. Plan statuses are normalised
first (`IN_PROGRESS`→`IN-PROGRESS`; `COMPLETE`/`DONE`/`SHIPPED`→`EXECUTED`; `PLANNED`→`DRAFT`); any
other value is drift class 8. Both readers prefer the calling repo's own
`scripts/enforcement/check_convergence.py`/`check_plan_tickets.py`/`check_stage_artifacts.py`
(imported by path), falling back to an equivalent local regex — with one stderr line — when that
repo's copy is missing or fails to import, so the drift report is never silently empty because a
sibling script drifted.

Eight drift classes (`status`/`sync` print `DRIFT <n> (blocking|advisory)  <path>`):

| # | Class | Always |
|---|---|---|
| 1 | A CONVERGED spec no plan names and no item links (SUPERSEDED/IMPLEMENTED excluded) | advisory |
| 2 | A plan CONVERGED more than 7 days with no plan lock and no item linking it | blocking\* |
| 3 | A plan IN-PROGRESS with no plan lock | blocking\* |
| 4 | A plan EXECUTED while an item linking it is still open | blocking\* |
| 5 | An item file that doesn't parse, or a status outside the vocabulary | blocking\* |
| 6 | A `done` item within the last 14 days whose evidence SHA doesn't exist or doesn't name it; or a closed marker over 14 days old whose item is still open in the base branch (never merged) | blocking\* |
| 7 | The backlog block is stale (`render` would change it) | advisory |
| 8 | A plan `Status:` value outside the normalised set | advisory |

\* Classes 2–6 only turn `sync --check`'s exit code non-zero once the repo is **past its migration
window**: `config.json`'s `migrated_at` is set (by `migrate-backlog`, once) and `readings.jsonl` shows
7 consecutive clean calendar days after it (every `sync` reading that day showing zero for classes
2–6), re-derived from the readings on every run — never a stored flag. Before that, and always for
classes 1/7/8, drift is printed but the exit code stays 0. **On the completion gate**, this is the
`Work items (sync)` row (`scripts/final_gate.py`): it reds on exactly that same
`exit 1` + a `DRIFT <n> (blocking)` line combination — never on advisory drift, which passes with a
`⚠` line the JSON `warnings` carries — and a broken tool (`work.py` missing, a timeout, an old copy
with no `sync` verb, a crash) is reported as a named skip that still passes, never a red: a repo that
never `init`s a store is not penalised, but the `⚠` lines keep a skip visible rather than silently
green.

## The backlog becomes a view

`migrate-backlog` reads `docs/STRATEGIC_BACKLOG.md` and turns every ROW into a `kind: backlog` item,
idempotently (a digest of each row's text plus its occurrence number, kept in the item's `note`, so
re-running adds nothing already migrated). A row starts only at a tagged entry shape (D-407): any
`## ` heading; a `### ` heading carrying a bracket tag or a resolved marker; a bullet led by a bracket
tag, a checkbox, or a strikethrough; or a row of a table with a Tag/Owner column. Every other line —
an untagged bullet, a narrative sub-header, prose, a fenced block — is body text of the row above it,
kept in full in the item's `next`. A row-start line that still fails to parse further (no tag found)
becomes an item with an empty `owner`, listed by `migrate-backlog` as needing the distributor — nothing
is dropped. A resolved row (a `[x]` checkbox, a leading strikethrough, or a RESOLVED/CLOSED/DONE/
LANDED/MOOT/SHIPPED marker in status position) becomes `done` with `legacy: true`, exempt from the
evidence rule.

After migration, `render` regenerates `docs/STRATEGIC_BACKLOG.md`'s `AUTO-GENERATED:BACKLOG` block —
byte-deterministic, no timestamp, so the daily pipeline and agents never churn it — listing every open
`kind: backlog` item as `- **[owner or "unassigned"]** title (\`id\`)`, sorted by priority then owner
then id. It is the block's only writer; new backlog work is `work.py add --kind backlog`, never a hand
edit of the block.

## The native Task list

The settings `env` block enabling Claude Code's native Task tools
(`CLAUDE_CODE_ENABLE_TASKS`/`CLAUDE_CODE_ENABLE_TODO_TOOLS`, both `"1"`) rides in the fleet-synced
`.claude/settings.json` (D-397). It is an in-session checklist only — `work.py` does not read or write
it, and it is not the record: two sources of truth is exactly the drift this store removes. Sharing
the per-account `tasks/` directory across accounts (the way `sessions/` and `projects/` already are,
D-287) is separate, not-yet-merged work.

## Adoption

Once a repo runs `work.py init` (naming its distributor) and `work.py migrate-backlog` followed by
`render`, `sync --check` starts as an advisory row on the completion gate and becomes blocking only
after the 7-clean-calendar-day window above. A repo with no `.fabrik/work/` is unaffected by every
hook and every gate row: this is opt-in per repo, distributed to the fleet through the ordinary
governance sync once `scripts/work.py` merges.

## Degradation

A `work.py` failure never blocks a Stop — every hook-facing call fails open, like
`thread_anchor.py`'s own calls. The one write that must not be lost, a DECISION block's item, gets the
second chance above and a printed warning if that also fails. A corrupt item file is reported by
`sync`/`status` and skipped by `ready`. A missing store reads as empty everywhere.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/work.py`
<!-- END related-scripts -->
