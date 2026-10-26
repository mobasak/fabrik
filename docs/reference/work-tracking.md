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
would fork `config.json`). Without `--distributor`, it runs `<the current interpreter>
/opt/fabrik/scripts/decisions.py --merge-owner <the resolved absolute repo root>` (hub-only, 30 s
timeout); a name that isn't a valid agent name is warned about on stderr and dropped. With no name
recorded either way, the store's `distributor` field is left empty and `assign` is open to any agent.
A second, optional key, `feedback_owner` (set by hand, like `autonomy`), names the agent whose Stop
ladder walks the command-feedback queues — the hub's fourth agent, `kaizen`, since 2026-10-06; absent,
the distributor walks them as before. A feedback owner that is not the distributor is not a pool
worker: `_workers` drops its worktree, so triage never routes general backlog to it, and its feedback
candidates come right after its mail on the autonomy ladder.

## Two homes

| State | Home | Versioned? | Why there |
|---|---|---|---|
| **Durable item** — what the work is, who owns it, where it stands | `.fabrik/work/<id>.json`, one pretty-printed JSON file per item, sorted keys | yes, committed | outlives every session; `git log -p` on the file is its history — items are never deleted, only ended `done`/`dropped` |
| **Live claim, closed markers, readings** | `$(git rev-parse --path-format=absolute --git-common-dir)/fabrik-work/` | no (this lives inside `.git` itself, which git never tracks as content — no `.gitignore` covers it or could; the only `.gitignore` this mechanism writes is `.fabrik/work/.gitignore`, in the COMMITTED store, covering its own stray `*.tmp` files) | the git common directory is shared by the main checkout and every worktree, so all agents see one claim table without a worktree writing outside its own tree (`docs/reference/multi-agent-operating-model.md` § Locks — `.fabrik/plan-locks/`, per working tree — "never write a lock outside the tree you are in") |

## The item

Fields on every item (`W-` plus 8 hex characters, minted from a hash of title/creator/creation-time
plus a random nonce, exclusive-created so a collision just retries with a fresh nonce):

| Field | Meaning |
|---|---|
| `id`, `title`, `creator`, `created` | identity |
| `kind` | `backlog` · `decision` (awaiting the operator — created only by the Stop-hook harvest, never by `add`) · `mail` (a mail claim — created only by `mail.py claim`, closed NORMALLY only by `ack`/`requeue`) · `feedback` (a command's feedback queue, one item per command — created only by `command_feedback_report.py --take`, closed NORMALLY only by `--mark-answered`) · `next` (the session's current free-text NEXT — created only by the Stop harvest, closed NORMALLY only by its own supersede/idle rules, § NEXT, DECISION blocks and the register) · `task`. **`add` refuses `decision`/`mail`/`feedback`/`next` by kind, and `done` refuses to close a `mail`/`feedback` item BY HAND** (`_LINKED_CLOSE`, `cmd_done`, `scripts/work.py:2919-2941`) **— but `drop --why` carries NO kind guard at all** (`cmd_drop`, `scripts/work.py:3015-3041`) **and closes a `mail`, `feedback` or `next` item by hand just as readily as a `backlog`/`task` one**, bypassing its normal close path |
| `status` | closed vocabulary: `open` · `blocked` · `awaiting-operator` · `done` · `dropped`. **"Claimed" is never a stored status** — an item is claimed only while a live claim file exists in the shared dir and its lease has not passed, so a crashed claimer's item becomes ready again by itself. `blocked` genuinely gates readiness when set (`ready`'s `_is_ready` excludes anything but `open`; `claim` refuses a `blocked` item by name) — but no verb ever WRITES it today; see `blocked_by`. |
| `priority` | 0 (urgent) to 3 (someday), default 2 |
| `owner` | agent name (`[a-z0-9-]{1,32}`, `whoami_agent.py`'s rule), set by the distributor; empty means unassigned |
| `tags` | written only when non-empty: sorted labels (`[a-z0-9][a-z0-9-]{0,31}`, `TAG_RULE`) for a constraint that must travel WITH the item — e.g. `runtime` for "applying this needs a serialising act" (`docs/reference/multi-agent-operating-model.md` § The shared runtime, D-442). Set by `add --tag`, edited by `assign --tag/--untag`, printed as `[tags: a,b]` at the end of every `ready` line; `--untag` removes any stored value, and one call naming a tag in both is refused; a label, never a gate — nothing refuses or orders on it |
| `links` | `{spec, plan, decision}` on every item, paths and D-ids the item tracks; plus, written only when non-empty, `mail` (the message id, `kind: mail`), `command` (the command name, `kind: feedback`), `session` (the session id, `kind: next`) |
| `blocked_by` | item ids that, if present, would gate `ready` and `claim` until each reads `done`/`dropped` (here, or closed by a marker elsewhere) — genuinely READ by both (`_is_ready`, `_refuse_blocked`). In practice it never blocks anything today: `add` has no `--blocked-by` flag and every item is minted with `blocked_by: []`, so nothing currently WRITES this field. |
| `next` | the item's own concrete next action, written by `add --next` or `migrate-backlog` in full (a migrated item's whole body lives here) — a Stop harvest never rewrites it: a NEXT that qualifies under rule 2 (§ NEXT, DECISION blocks and the register, below) only CLAIMS the item. A `kind: next` item's own `next` is its session's current free-text NEXT, clipped to 300 characters (`LINE_MAX`) — the same 300 characters the register (`thread_anchor.py`) judges a NEXT by |
| `next_at` | `kind: next` only: the time this item's `next`/title text was last set — a Stop harvest closes the item `dropped` `idle 7 days` once this reads more than 7 days old |
| `evidence` | set by `done`: a commit SHA whose message names the item id — or, for an item closed `--resolved-by`, the cited item's own recorded evidence, whose commit names the `resolved_by` root (the cited item itself, or the item at the end of its chain) |
| `resolved_by` | set by `done --resolved-by`: the ROOT item whose recorded fix also resolved this one (a chain records its root, not the link it was cited through); copied onto the closed marker so another tree can follow the chain (W-f154f3f3) |
| `legacy` | `true` only on items `migrate-backlog` created from rows already resolved; exempt from the evidence rule |
| `note` | free text; on a `decision` closed by `answer` it holds the operator's words, which exempts that item from the evidence rule (it has no commit by design, D-542) |
| `question`, `ground`, `msg_digests`, `block_digest` | `kind: decision` only: the plain-words question, the DECISION block's `ground:` token, every message digest that created or refreshed the item, and the block's own digest |
| `alt_block_digests`, `alt_ids` | `kind: decision` (awaiting) only: the block digests and item ids of every duplicate `drop --duplicate-of` folded into this item, so a later message re-asking any of those words refreshes this item instead of opening a third |
| `note` | the last closing reason (`drop --why`, `answer --note`, `drop --duplicate-of` — `duplicate of <keep>`, a mail ack — `mail ack: <disposition>`, a mail requeue — `requeued`, a feedback close — `answered by <sha prefix>`, a `kind: next` item's own closes — `superseded` or `idle 7 days`, `_close_next`), or (on a migrated row) `migrated-digest:<12 hex>` |

## Identity, the lock, the lease

- **Who is acting.** The agent name is `whoami_agent.py`'s resolved name, else `CLAUDE_AGENT` (both
  validated against the same `[a-z0-9-]{1,32}` rule; `scripts/work.py::_agent_name`), else — only for a
  hook handed its session in the payload while `CLAUDE_CODE_SESSION_ID` is empty — that session's
  identity-store binding; so a session with `CLAUDE_AGENT` unset is still named when the identity store
  binds it. When none of the three resolves the name is empty: an unnamed session, and such a session
  cannot be `assign`'s TARGET (owners are agent names only), but that is its only limit: `claim`,
  `release`, `done` and `answer` fence on SESSION identity alone and never check `owner` (§ Ownership
  is not identity-enforced, below), so an unnamed session can claim, release, finish or answer ANY
  item — assigned to someone else or not (executed: an unnamed session claimed, then finished, an
  item owned by `infra`; rc 0 both times, `owner` unchanged). The session is `CLAUDE_CODE_SESSION_ID`.
- **One lock for every write.** An exclusive `fcntl` flock on `fabrik-work/.lock`, re-entrant within
  one thread, guards every write through a unique temp file plus `os.replace`. CLI verbs wait 10 s
  then **fail loud** (non-zero exit, a named message, e.g. `the store lock (…/.lock) was held for
  over 10 s — nothing was written; retry`); hook-facing calls wait 2 s and **fail open**. Every wait
  over 0.1 s is appended to `fabrik-work/readings.jsonl`.
- **The lease.** A claim is `{agent, session, at, lease_s, token}`; the default lease is 2 h. Any
  write by the claiming session renews it, and the Stop-hook harvest renews every live claim of the
  session on **every** Stop — including a blocked one — so a normal turn's heartbeat costs no extra
  verb. `token` is a counter recorded on the claim, bumped by one on every new claim (including a
  takeover) — it is never supplied by the caller (no verb has a `--token` flag) and the fence never
  compares it. The fence itself (`_fence`) compares SESSION identity only: `done`/`release`/`answer`/
  `drop` are refused unless the caller's session matches the live claim's session, or there is none — a
  session whose expired claim was taken over cannot overwrite the new claimer's result (executed: a
  second session's `claim` on an already-held item is refused by name — `claim W-… refused: it is
  held by session …, token …, lease until …`).
- **Closing across worktrees.** `done`, `drop` and `answer` write the item in the caller's own tree
  only, plus a closed marker in `fabrik-work/closed/`, so another tree of the repo stops listing an
  item finished on an unmerged branch. A marker is DELETED only once the store's recorded base branch
  (`config.json`'s `base_branch`, read as a ref — never whatever a checkout happens to have checked
  out) reads the item `done`/`dropped` (or it is this tree's own crash residue). Age never deletes a
  marker: past 14 days it merely STOPS hiding its item — `ready`/`status` see the item again — while
  the marker file itself stays on disk. Drift class 6 relies on exactly that: a marker still present
  past 14 days, next to an item its base branch still reads open, is what class 6 reports. Class 6's
  other half reads the items themselves: an item marked `done` in the last 14 days whose `evidence`
  SHA does not resolve or does not name the item (its `resolved_by` root when it has one) — except `legacy` items, `mail`/`feedback` items,
  and a `decision` closed by `answer` (D-542).

## The CLI — `scripts/work.py`

Executed against the merged script (`work.py --help`, then `work.py <verb> --help`, 2026-10-05) — 17
verbs:

| Verb | Who | What |
|---|---|---|
| `init [--distributor <agent>]` | once per repo | create `.fabrik/work/` and `config.json`; nothing else writes an item into a repo without it |
| `add --kind {backlog,decision,feedback,mail,next,task} --title <t> [--next <t>] [--link key=value] [--priority 0-3] [--tag <t>]…` | anyone | create an item; `--kind decision`, `--kind mail`, `--kind feedback` and `--kind next` are all refused — each comes only from its own mechanism (an accepted DECISION block, a mail claim, taking a feedback queue, the Stop harvest's NEXT rules), never from `add` |
| `assign <id> [--owner <agent>] [--priority 0-3] [--tag <t>]… [--untag <t>]… [--impact high\|low] [--effort high\|low] [--why <t>] [--blocked-by <id>]… [--unblock <id>]…` | distributor | set owner, priority and/or tags; SCORE an item (§ Scores and holds) or hold it behind another id |
| `edit <id> [--title <t>] [--next <t>] [--link key=value]… [--unlink spec\|plan\|decision]…` | anyone | change what `add` wrote — title, next, the spec/plan/decision links — under the store lock, in the caller's own tree; refused on `decision`, `next`, `mail` and `feedback` items (their title and links come from their mechanism), on a call naming no field, an empty title, a key both linked and unlinked, and a `decision=` that is not a ledger id; `--next ""` clears next; a `spec=`/`plan=` value that does not name a regular file inside the repo is applied with a warning; a `--link`/`--unlink` refuses an item whose stored spec, plan or decision link is not a string, naming each, while a title or next edit leaves `links` exactly as stored. The backlog block lists owner, title and id only, so a link or next edit needs no render. In a linked worktree the edited item merges with the branch: when the main checkout holds an uncommitted write to the same item, `commit-items` there first or the merge refuses. An open item linked to an `EXECUTED` or archived plan reads drift class 4 until it is closed (mail 01M55ZNVH7) |
| `queue [--json] [--stop --session <id> --cwd <path>]` | anyone, read-only | each window's queued work against the floor, routable and waiting-backlog counts, plans not executed; `--stop` prints the Stop hook's one action (§ Ownership and the distributor) |
| `triage [--apply]` | distributor (`--apply`) | plan the top-up of every present worker below the floor; `--apply` assigns it and prints the SendMessage lines; also prints `unscored <n>: <ids>` and any `major in flight:` line, and plans at most one major project per run (§ Scores and holds) |
| `ready [--mine] [--all]` | worker | spec D4's crisp default: the obligation lines (§ The view), this session's claims, items this agent owns, awaiting items, then the top 10 remaining ready items (and how many more `--all` would show); `--mine` puts the caller's own first among those remaining, then unassigned ones; `--all` is the OLD default — every `open`, unblocked, unclaimed item by priority then age. In a coordinator-mode repo a BUILDER's default `ready` lists only its own items among the remaining ones; `--all` (and `--all --mine`) is unfiltered |
| `next` | worker | the first item `ready --all --mine` would list — `_ready_items(mine=True)`'s ordering (open, unblocked, no live claim; this agent's own first, then unassigned; never an item owned by someone else), NOT the crisp `ready` default above. In a coordinator-mode repo a BUILDER's `next` offers only its own items |
| `claim <id> [--session <s>]` | worker | take (or renew) the live claim; refused when another session holds a live claim, or the item is `blocked`/has an unresolved `blocked_by`. In a linked worktree an item MISSING from this tree's store is read from the main checkout's (the claim is shared state, and an item the coordinator made there reaches a branch only with a merge), and its `blocked_by` is checked in that store (W-98204c50) |
| `release <id> [--session <s>]` | worker | give up this session's live claim (fenced the same way as `done`); finds a main-store-only item from a linked worktree as `claim` does, so `merge_request.py request --item` releases it |
| `done <id> --evidence <sha> [--session <s>]` | worker | refused without `--evidence`, with a SHA that does not resolve, or whose commit message does not name the item id; refused BY HAND on a `mail`/`feedback` item — those close only through `mail.py ack`/`close_linked` |
| `done <id> --resolved-by <W-id> [--evidence <sha>] [--session <s>]` | worker | close an item another item's commit already fixed: the cited item must read `done` in this tree, on the base branch or in a closed marker, and record evidence; this item carries that evidence and records `resolved_by`. A given `--evidence` must equal the cited item's, so a fresh commit that merely names the cited item is refused (W-f154f3f3) |
| `drop <id> (--why <text> \| --duplicate-of <keep>) [--session <s>]` | `--why`: the owner, the distributor, or anyone for an unassigned item · `--duplicate-of`: the distributor, or a caller whose agent name or session id is the `creator` of BOTH items | end an item that won't be done (`--why`, refused on `awaiting-operator` items); or retire an open `awaiting-operator` `<id>` into another open `awaiting-operator` `<keep>` (`--duplicate-of`, D5) — `<keep>` absorbs `<id>`'s block digest and id so a later re-ask of either wording refreshes `<keep>` instead of opening a third item |
| `answer <id> --note <text> [--decision D-NNN] [--session <s>]` | the agent the operator answered | close an awaiting-operator item with the operator's own words |
| `status` | anyone | the obligation lines and the distributor's lines (§ The view), items by state, uncommitted item files, plan-board ticket counts, and the eight drift classes below (read-only, no lock) |
| `pause [<name>] [--why <t>] [--by <label>]` | the distributor, the named agent itself, or the operator (a caller with no agent name AND no Claude session id; `--by` names it, default `operator`) | mark an agent PAUSED in this repo (W-da4bc702): a marker `<git common dir>/fabrik-work/paused/<name>.json` every tree sees at once. A paused caller's `queue --stop` action is null (only the main checkout's `commit-items` survives) — no held claim is pushed on, nothing is lost; the floor rung and `triage` skip a paused worker; a worker's doorbell skips a paused coordinator; `queue` marks it; its prompt block says PAUSED and drops the ready line; its `NEXT:` claims nothing. The caller's own rungs match the window's resolved agent name OR its worker tree's name; the floor, `triage` and `queue` count worker trees, so they honour a pause by the tree's name. With no name, lists the pauses. An unnamed Claude session is refused; an unknown name is warned about; re-pausing over another's pause is refused unless the caller is the distributor or the operator. Presence is the pause: an unreadable marker still pauses, and an entry that is no regular file (a directory, a FIFO) is never read and is removed by hand |
| `verdict [--text <t>] [--by <label>] -- <id> accept\|reject\|comment` | the operator only (no agent name AND no Claude session id — stricter than `pause`, which admits a named agent; an audit rule, not a security boundary) | the operator's call on one item, from the dashboard's Repos tab or a shell (W-e1f1a1bd). Every call appends `{at, by: operator, via: <--by or cli>, action, text}` to the item's `comments` list (the text one printable line, at most 200 characters). `accept` answers an awaiting decision (note `accepted[: <text>]`) and on any other open item adds the informational tag `operator-accepted` and removes the `waits-operator-review` hold (it never assigns an owner); `reject` answers an awaiting decision (`rejected: <text>`) and drops any other open item (`rejected by the operator: <text>`); `comment` only appends. `reject` and `comment` need `--text`. An awaiting item that is no decision takes comments only; another session's live claim refuses accept and reject; a resolved item is refused. A reject reaches every tree at once (the closed marker); an accept's tags and every comment live in the main checkout's item file until `commit-items` and a merge carry them |
| `resume <name>` | whoever set the pause (by agent name), the distributor, or the operator | lift a pause; a paused agent cannot lift a pause someone else set, and a pause the operator set is lifted only by the distributor or the operator (the check reads the marker's `actor`, never its `--by` label). The hook's merge-owner cause never reads a pause: a paused merge owner still owes merges |
| `commit-items` | the MAIN checkout's session | commit every uncommitted, valid item file of the main store in ONE plumbing commit on the current branch (`Agent-Role`/`Agent-Context` trailers), built in a private index from HEAD, so no other dirty or staged file rides along; a path another session STAGED and a file that is not a valid item are skipped and named; a sibling commit landing meanwhile is never overwritten (compare-and-swap, one rebuild). Refused in a linked worktree and on a detached HEAD. It never pushes. While committable files remain, `queue --stop` hands the main checkout's session this verb: FIRST on the autonomy ladder (re-armed after each store commit and each doubling of the backlog), LAST on the classic path and never while the session holds a claim; when the checkout's state refuses the verb it names that state instead. A deleted item file is never committed by it (W-4238b6ec) |
| `merge-item <base> <ours> <theirs>` | `merge_request.py merge`, and the `workitem` merge driver on a HAND merge, rebase or cherry-pick in any hub worktree | the key-wise 3-way merge of ONE item file (W-5f3617e6). The side that changed a key against the base wins; a change both sides made identically merges; an object value (`links`) merges per sub-key, against `{}` when both sides added it; `tags` and `blocked_by` merge as sets (the base, plus what either side added, minus what either side removed) and any other list (`comments`) merges when both sides only appended to it; the result is written into `<ours>` in the store's own format, exit 0. A key both sides changed to different values, or deleted on one side and changed on the other, leaves `<ours>` untouched, names every such key on stderr and exits 3, so it never picks a side; an unreadable or non-object side exits 1. An empty base (both sides added the item) merges against `{}`. It needs no repository. `merge_request.py` refuses a merged item whose `id` is not its file name. Needed because the store writes one key per line in sorted order, so DISJOINT keys that sort side by side (`effort`/`evidence`, `score_reason`/`status`) collide in git's line merge. **As a merge driver** (W-c230cb2e): the hub's `.gitattributes` maps `.fabrik/work/W-*.json` to `merge=workitem`, and `scripts/install_post_commit_hook.sh` registers `python3 scripts/work.py merge-item %O %A %B` (the merging tree's own copy) with `merge-file` as its fallback: ANY non-zero exit falls back to the text merge, so a conflict keeps its markers (labelled `ours`/`theirs` — in a rebase `ours` is the branch being rebased onto, as in git) and the file stays unmerged. Read the `work: merge-item: both sides changed <key>` line, not the hunk count: the fallback marks the whole file's line conflict. `-X ours`/`-X theirs` reach no custom driver, so they no longer resolve an item-file key conflict — resolve it by hand. A clone without the config merges as text. |
| `sync --check` | gate, pipeline | the same drift report, plus one `readings.jsonl` line; exits non-zero only when a listed class is both `(blocking)` in its output **and** the repo has passed its blocking window (below) |
| `render [--here]` | pipeline, agents, in the main checkout | regenerate the backlog's `AUTO-GENERATED:BACKLOG` block — its only writer. The block is the main checkout's view of the main store, so `render` refuses in a linked worktree and when `--repo` names a tree the caller is not in (a worktree render once rewrote 433 rows of a block its branch then merges); a branch's item edits reach the block when the main checkout renders at merge. `--here` renders the caller's own store anyway in a linked worktree and says not to commit the result; it never writes a tree the caller is not in, so `--repo` naming another tree is refused with or without it (mail 01M55ZNVH7) |
| `migrate-backlog` | once per repo | turn existing `docs/STRATEGIC_BACKLOG.md` rows into items; once `migrated_at` is set, a run creates nothing |

`--repo <path>` (any path inside the repo, default cwd) is a TOP-LEVEL option and must come BEFORE the
verb — `work.py --repo <path> ready`, never `work.py ready --repo <path>` (after the verb it is an
unrecognized argument, exit 2). `done`/`drop`/`claim`/`release`/`answer` default `--session` to
`CLAUDE_CODE_SESSION_ID`.

**Ownership is not identity-enforced for every verb.** `drop` checks `owner`/`distributor`, and
`assign` checks `distributor` alone (when one is named) — an unnamed session cannot be `assign`'s
TARGET, since owners are agent names only; `claim`, `done`, `release` and `answer` check neither —
they fence on SESSION identity alone (§ Identity, the lock, the lease, above), never on the item's
`owner` field. So "the owner, the distributor, or anyone for an unassigned item" (`drop`'s row) and
`assign`'s "distributor" are enforced rules, while "worker" (`claim`/`done`/`release`) and "the agent
the operator answered" (`answer`'s row) above are conventions the CLI does not check — ANY session,
named or not, can claim, release, finish and answer ANY item, regardless of who it is assigned to
(executed: an unnamed session claimed, then finished, an item owned by `infra`; rc 0 both times,
`owner` unchanged).

## Ownership and the distributor

`config.json`'s `distributor` field names the one agent `assign` is reserved to; `init` sets it from
`--distributor`, or from the merge owner (`docs/reference/multi-agent-operating-model.md:80-86`) when
omitted. It is the **same agent** as the merge owner in every repo — the one agent in the main
checkout (D-471): the merge owner integrates branches into the base branch (§ Merge protocol there)
and, as distributor, sets item owners and priorities (`work.py assign`) so a worker's `ready --mine`
and a claim never collide over who should be doing what. Never pass `--distributor` naming anyone
else; in the hub that agent is infra (D-471 superseded D-395's intel). Since D-521 (operator
ruling D-512: "no agent waits idle if there is work to be done") the distributor keeps every PRESENT
worker — a registered `.claude/worktrees/<name>` with a live `claude` process — at the floor (3,
`queue_floor` in `config.json`) of QUEUED work: an owned `task`, or owned backlog promoted with the
`queued` tag (backlog is a list, not an order). A worker's queued count is read from the MAIN checkout's store (the store of record for assignment, D-516) plus the items only its own tree holds — main's file wins for an id both hold — so an assignment counts the moment the distributor writes it, before the worker merges. `work.py queue` shows each window against the floor,
the routable and waiting-backlog counts and the plans not yet executed; `work.py triage` plans the
top-up (it prints each item's tags — the coordinator judges role fit) and `--apply` assigns it, never
promoting, dropping or creating anything; items tagged `runtime`, `hold` or `waits-*` are never
assigned automatically. `hold` and `waits-*` also PARK an item — not doable now: no claim, owned or
held-claim rung pushes it, `work.py next` skips it, and a session holding its claim is told to
release it. `waits-<slug>` (an event: `waits-tojlo`) parks until the tag is removed;
`waits-YYYY-MM-DD` parks until that UTC date and is live again on it, and a dated tag that is not a
real date is refused when written. `runtime` is never parked: assigned by hand it is due work.
Parking an existing item is the distributor's call (`work.py assign <id> --tag …`); `add --tag`
sets the tags of a new item. `queue` counts each agent's OWNED parked items (a worker's from its own tree), and the Stop result
counts the parked items the agent owns or this session has claimed. The Stop hook enforces both sides through `work.py queue --stop`: a window
with queued work and no claim is told to claim it, a worker whose tree lacks items main already assigns it is told to merge the base branch and then claim, a worker whose queue is empty rings the
coordinator, the distributor is told to triage while a present worker sits below the floor and
work waits (routable or backlog items, or its own queue above the floor), and a
one-window repo (or one with no distributor) is its own coordinator. A repo whose `config.json` carries
`"autonomy": true` — set by hand by the merge owner, the one key `init` does not write (the hub,
operator ruling 2026-10-04, D-558) — gets the AUTONOMY LADDER instead: `queue --stop` returns ordered
`candidates`, one per subject — a claim this session holds, `ack: required` mail for the agent,
queued work, the coordinator rungs above, the agent's other owned ready items, and for the
distributor the command-feedback queues (for a `feedback_owner` that is not the distributor, its
queues come right after its mail instead — § above) — and the Stop hook blocks on each subject in turn, three
times at most, so holding a claim no longer silences it. Self-service claiming from
`ready` stays the fallback — `docs/reference/multi-agent-operating-model.md` § Claim or assign —
except for a BUILDER in a coordinator-mode repo (below), who claims what the coordinator queued it
and serves itself only while the coordinator has no live window.

### Scores and holds (the coordinator role, D-871)

The coordinator scores every item on two fields, set with `assign` and always with `--why` (the
one-line reason is stored as `score_reason`): `impact` (`high`/`low`) and `effort` (`high`/`low`, the
quota it will spend). Once an item carries both, its `priority` is DERIVED — high/low → 1 (quick
win), high/high → 2 (major project), low/low → 3 (fill-in) — and every check runs on the item as it
will be written, so a score split across two calls is judged as one. Low impact with high effort is
a time sink: `assign` refuses it and names `work.py drop --why`. On a scored item `--priority 0`
sets the incident override; any other `--priority` is refused (the priority is derived), and a
re-score without `--priority 0` ends the override and says so (`P0 override cleared`). A P0 set
before an item's FIRST full score survives that score (`P0 kept`). An item that is not fully scored
— never scored, or half-scored — keeps today's `priority` (default 2) and today's `--priority`;
`--why` without a score is refused.

`assign --blocked-by <id>` holds an item behind another (`ready` and `claim` already skip an item
with an open blocker); `--unblock <id>` releases it. Refused: an unknown id, the item itself, a hold
that would close a cycle, `--unblock` of an id the item is not blocked by, and the same id in both
flags. `triage` lists every open item that lacks a score (`unscored <n>: …`, `kind: next` and items
closed elsewhere excluded), never plans a second high/high item while one is in flight (owned or
claimed, `open` or `blocked` — it prints the slot holder), and plans at most one high/high item per
run. A high/high item held behind another in-flight one with `assign --blocked-by` waits rather
than flies: triage prints it as `major held: <id> behind <id>`; one waiting on anything else (a
prerequisite task, an unknown id) still holds the slot.

**Coordinator mode** is opt-in per repo: `"coordinator_mode": true` in the main checkout's
`config.json`. `work.py` is fleet-synced, so the behaviours that change what a builder sees act only
there — and, for a builder, only once its own branch carries the key too (until it merges the flip
it keeps today's view, and its Stop doorbell says so: one predicate decides both). A BUILDER is a pool worker (`_workers`; the feedback owner's tree is not one) that is not the
distributor, named by its worker tree — the tree test the Stop hook's worker check makes — else the way the Stop hook names it. A builder's `next`, default `ready` and prompt
`ready` count show only its own items;
`triage` plans scored items before unscored ones; and when the coordinator has no live window, the
Stop doorbell points a builder with an empty queue at `work.py ready --all --mine` (its own items,
then unassigned ones) instead of `next`. Scoring, holds and the unscored listing work in every repo.
COBRA (D-253): the cheapest way to look prioritised is to score everything a quick win — every
score carries its reason, and `triage` keeps the unscored count in view.

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
  This `--decision-ok` re-run happens ONLY at a Stop the hook ALLOWS (a pass-through, the quota hold,
  or a non-fabrik project) — never at a Stop it blocks. On a blocked Stop the accepted block becomes
  neither a per-session slot entry nor a work-store item; it is genuinely lost unless a LATER, allowed
  Stop re-judges the same text.
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
- **The pending file — when the slot write was skipped too (W-e64aa44a, D7 W4-O3).** The slot write
  runs under the per-session lock (≤ 1 s) and the store write under the store lock (≤ 2 s), each
  fail-open; with both busy at one Stop the block was in neither place and the second chance had
  nothing to read. Now, when the slot write was skipped (the lock busy, or a save that did not land)
  and the block is not an echo, the Stop side first lands the block in a
  lock-free file beside the slot — `~/.claude/state/threads/<session>.pending-<digest16>.json`, the
  slot's `decision` shape plus `session` — BEFORE the store wait, so even a Stop hook killed at its
  5 s budget leaves it on disk; the store taking the block unlinks it at once. The second chance
  lists pending files by their own glob (they never take a slot's place in the slot scan's 50-newest
  window, and the listing has no mtime filter of its own), rescues each live one for this repo with
  its own session as the item's creator, unlinks them once every entry is in the store, keeps them
  while the store is busy or momentarily unreadable, skips (unread, kept) one over the size cap,
  and sweeps — without rescuing — any file older than 7 days (its mtime, or its `ts`), without a
  session, or whose name does not carry its message digest — before the store check, so a
  store-less repo's leftovers age out too.
  The operator's answer settles a pending block exactly as it settles a slot block: the answering
  prompt's rescue mints the item when the store is free, and the clear that follows drops exactly
  the pending files that rescue collected for this session — never one a later Stop wrote, and
  nothing when no rescue ran — so a question answered while the store was busy is never minted
  later and an unread block survives the answer.
- **The NEXT rules (spec D3).** The Stop harvest and `scripts/sysadmin/next_census.py`'s fleet
  measurement sort a NEXT's text with the SAME function, `work.classify_next` (T05a) — but they answer
  different questions with it, never one shared verdict: the harvest classifies only the turn's LAST
  captured NEXT (clipped to the register's 300-character cap), while the census classifies EVERY NEXT
  value of every assistant text row, read with the harvest's own `thread_anchor._next_values` (bold,
  bulleted and quoted footers included; never inside a closed fenced block or a subagent's sidechain
  rows), at full length. `classify_next` itself: `"hold"` when
  the line starts (after any markdown run) with `none`/`BLOCKED`, or carries `operator decision(s)`
  anywhere; `"names-item"` when it names a `W-` id outside a path or URL (`?item=W-…`, `x/W-…` and
  `W-….json` name nothing); else `"free-text"`. The harvest applies the FIRST rule that matches — never
  for an empty or `nosession` session, whatever the text:
  1. **`hold`** (`none — terminal`, an operator decision, `BLOCKED:`) — no claim and no thread item,
     whatever the line names.
  2. **`names-item`** — the FIRST named id that is open, unblocked, not itself a `next` item and not
     held live by another session gets the claim — and nothing else: the item's file is never
     written, because its `next` is its own authored next action (a migrated item's whole body
     lives there) and the NEXT line is already kept by the register (D-425); no other named id is
     touched, and an id that qualifies nothing leaves nothing claimed.
  3. **`free-text` the register accepts** (`_is_anchor`) — but only when the register itself WROTE the
     anchor (`next_anchored`; a busy session lock makes this false even for accepted text) — the
     session's own `next` item carries it (below).
  4. **Anything else** — nothing.

  **The session's `next` item, as one rule.** While a session's last NEXT is free text the register
  accepts, the session has exactly one open `kind: next` item (`links.session` the session id) whose
  `next`/`title` and `next_at` are that text and the time it was set — created on the session's first
  such NEXT. **A later rule-3 NEXT never closes it**: `_keep_next` rewrites that SAME item's
  `next`/`title`/`next_at` in place, so there is only ever one item, never a close-then-reopen. Only a
  hold (rule 1) or a NEXT that names an item (rule 2) closes the session's prior open `next` item —
  `dropped` `superseded` — and rule 2 closes it AFTER its own claim attempt runs, whatever that
  attempt's outcome (`_apply_next_rules` calls `_claim_named` first, then unconditionally
  `_supersede_next`). Any Stop harvest in the repo — any session's — also closes `dropped` `idle 7
  days` every `next` item whose `next_at` is more than 7 days old, falling back to `created` when
  `next_at` is missing or unparseable (`_close_idle_next`). The register itself is untouched by any of
  this (D-392).

There is no `await` CLI verb and no other way to create an `awaiting-operator` item — only an accepted
DECISION block does. `NEXT: none` stays legal; nothing counts or scores items (D-392).

## The view

One open place every session and the distributor read, live, never copied into the store (spec D1,
D4, D6):

- **The obligation lines (D1), `work.obligations(repo)`.** At most two lines, read fresh on every
  call: the count of `ack: required` mail STILL IN this repo's inbox — i.e. not yet claimed, never a
  read/unread distinction — with the oldest one's age — `mail: 3 need an answer (oldest 4 d) — python3
  scripts/mail.py list`; and, only in the repo holding
  `commands/_sources/` (the hub), the three deepest command-feedback queues — `feedback queues:
  fabrik-execute-plan 36 · … — /fabrik-command-improve <command>`. Either line fails open to nothing on
  any error, with one stderr warning — an unreadable inbox WARNS rather than silently reading as no
  mail. `ack: no` mail is information and is never counted. `ready` and `status` print these lines
  first, bare; the prompt block prints them too, each prefixed `work: `.
- **The prompt block (D1, D4, D6).** Ahead of the usual anchor block: the unnamed-window line, only
  when `_agent_name(session=…)` resolves nothing — the `whoami_agent.py` resolver, then `CLAUDE_AGENT`,
  then (only when `CLAUDE_CODE_SESSION_ID` is empty) the session's own whoami binding, none of them
  giving a name — `work: this window has no agent name — owned items cannot reach it; run python3
  scripts/whoami_agent.py --as <name>`; the obligation lines above; every
  `awaiting-operator` item with its question (and, once retired by D5, `(also asked as <id>)`); this
  session's own live claims — the first three by priority (the Stop hook's order) as `work: your claim —
  <id>: <title> (token …, lease until …)`, then `work: … and N more of your claims` naming
  `work.py ready` (D-583; one session held 117 claims, a 29 KB block on every prompt), and
  `work: your claims on items not in this tree — <ids>` for any claim `ready` cannot list; one `on it:`
  line per OTHER session holding a live claim, so every live claim in the repo is counted for every
  session — `work: on it: <session short id> (<agent or "unnamed">) — W-xxxx, W-yyyy`;
  and the ready count.
- **`status`'s distributor lines (D4).** `UNOWNED` — open items with no owner (a `next` item is never
  counted; it is nobody's to own); `CLAIMS` — one line per session holding a live claim, flagged `— over
  5`; `STALE NEXT` — an open `next` item whose `next_at` PARSES and is more than 6 days old (a day
  before the Stop harvest would close it) — an item with no `next_at`, or one that doesn't parse, is
  SKIPPED here, unlike the idle close above, which falls back to `created`; `AGED MAIL` — open `kind:
  mail` items created more than 14 days ago, flagged `— over 50`. Every count reads `status == "open"`
  items only, so a closed or resolved item never inflates one.
- **`ready`'s crisp default (D4)** is the obligation lines above, this session's claims, items this
  agent owns, awaiting items, then the top 10 remaining ready items (and how many more `--all` would
  show); `--all` is the OLD default, unchanged.

**Validation reading.** `python3 scripts/sysadmin/next_census.py --since 7 --repo .` classifies every
NEXT: line of the fleet's transcripts with the SAME `classify_next` function the harvest calls (§ NEXT,
DECISION blocks and the register, above, states the scope each actually reads), reports the
class/distinct/per-repo-session counts of spec § Why this exists, and — with `--repo` — prints this
repo's Validation V5 verdict: PASS when its open `next` items whose `next_at` was SET between 1 day in
the future (clock skew) and 7 days in the past number no more than the qualifying sessions counted for
it, AND it shows more than 0 live claims. A qualifying session ended at least one turn on a free-text
NEXT the register accepts — judged, as the Stop harvest judges it, on each turn's final text (a turn ends
where Stop fired; an interrupted turn is never judged). Both sides cover the main checkout and its worker
trees under `.claude/worktrees/`: items are read from each tree's store — an id counts once, is closed
when any tree's copy is closed, and is in the window by its freshest `next_at` — and sessions from each
tree's project directory, so `--repo` at a worktree reads the same verdict as at the main checkout
(when git cannot list the trees, `--repo`'s own tree is read as the main checkout — the census is
advisory). The session denominator counts transcripts with an assistant text row of their own. Line
totals from before 2026-10-04 used a stricter literal-`NEXT:` reader and are not comparable. The PASS
line prints its bound (`V5: PASS — <items> open next item(s) <=
<sessions> qualifying session(s), <claims> live claim(s)`), so a vacuous 0 <= 0 reads differently from a
real one.

**Reading 2026-10-09** (V5 on its due date, 13 days after the T08 adoption commit `36ea99199`; W-aa89df9f):
`next_census.py --since 7 --repo /opt/fabrik` printed `V5: PASS — 0 open next item(s) <= 3 qualifying session(s),
6 live claim(s)`, and the classes line `next: 18742 lines over 4680 sessions — names-item 3126 · none 263 ·
operator-decision 1121 · blocked 8 · free-text 14224` (9183 distinct free-text; 20 accepted-free-text sessions
fleet-wide). What it settles about the spec's open unknown (whether `_is_anchor` is the right filter for the
session's `next` item): `_is_anchor` is KEPT (D-724), on narrower grounds than "proven right". The 3 qualifying
sessions show the filter accepts some free-text NEXTs; the open-item side cannot show its width either way — one
`next` item per session at most, and the supersede and 7-day idle closes above empty it independently of what
the filter admitted. No over- or under-admission has been reported; the first report re-opens it.

## Spec and plan state is derived, never copied

`status` and `sync --check` read spec `Status:` lines, plan `Status:` lines, Ticket Boards and plan
locks directly — nothing about a spec or plan is copied into an item. Plan statuses are normalised
first (`IN_PROGRESS`→`IN-PROGRESS`; `COMPLETE`/`DONE`/`SHIPPED`→`EXECUTED`; `PLANNED`→`DRAFT`); any
other value is drift class 8. Both readers prefer the calling repo's own
`scripts/enforcement/check_convergence.py`/`check_plan_tickets.py`/`check_stage_artifacts.py`
(imported by path), falling back to an equivalent local regex — with one stderr line — when that
repo's copy is missing or fails to import, so the drift report is never silently empty because a
sibling script drifted.

Eight drift classes (`status`/`sync` print `DRIFT <n> (blocking|advisory)  <path>`, class 8 with its reason after the path):

| # | Class | Always |
|---|---|---|
| 1 | A CONVERGED spec no plan names and no item links (SUPERSEDED/IMPLEMENTED excluded; a plan under `plans/archived/` still names its spec) | advisory |
| 2 | A plan CONVERGED more than 7 days with no plan lock and no item linking it | blocking\* |
| 3 | A plan IN-PROGRESS with no plan lock (a lock clears it); or BLOCKED (`ON-HOLD`, `PAUSED`, `WAITING` alike) with nothing it waits on — clear it with a linked item that is `awaiting-operator` (or `blocked` by an open item), an awaiting item its Status line names by id, or an awaiting operator question naming the plan's dated stem; a plan lock does not clear it | blocking\* |
| 4 | A plan EXECUTED while an item linking it is still open (archived plans included — a plan is archived at EXECUTED) | blocking\* |
| 5 | An item file that doesn't parse, or a status outside the vocabulary | blocking\* |
| 6 | A `done` item within the last 14 days whose evidence SHA doesn't exist or doesn't name it (or its `resolved_by` root); or a closed marker over 14 days old whose item is still open in the base branch (never merged) | blocking\* |
| 7 | The backlog block is stale (`render` would change it) | advisory |
| 8 | A plan `Status:` value outside the normalised set — its line goes on to name the value it read (`unreadable (<the header>)` when the parser cannot read the header, `missing (no Status: line)` when there is none), the five statuses, check_convergence's EXECUTED precondition (the plan cites a whole-plan review under `docs/development/reviews/` named by its stem, with a quiet Pass row), and the archive as a superseded plan's remedy | advisory |

Classes 2, 3 and 8 read the live plans only: a plan under `plans/archived/` is settled history.

\* Classes 2–6 only turn `sync --check`'s exit code non-zero once the repo is **past its migration
window**: `config.json`'s `migrated_at` is set (by `migrate-backlog`, once) and `readings.jsonl` shows
7 consecutive clean calendar days after it (every `sync` reading that day showing zero for classes
2–6), re-derived from the readings on every run — never a stored flag. Before that, and always for
classes 1/7/8, drift is printed but the exit code stays 0. **On the completion gate**, this is the
`Work items (sync)` row (`scripts/final_gate.py`): it reds on exactly that same
`exit 1` + a `DRIFT <n> (blocking)` line combination — never on advisory drift, which passes with a
`⚠` line the JSON `warnings` carries — and a broken tool is reported without ever reddening, in one
of two SHAPES: a MISSING `work.py` prints the plain `Work items (sync)` row with `⚠ check not
present, skipping: scripts/work.py`; a `work.py` that exists but times out, crashes, or predates the
`sync` verb prints the DECORATED `Work items (sync) (NOT RUN — <reason>)` row instead — a different
row name (`skipped_checks` sees the decorated one, never the plain one), both passing. A repo that
never `init`s a store is not penalised, but the `⚠` lines keep a skip visible rather than silently
green.

## The backlog becomes a view

`migrate-backlog` reads `docs/STRATEGIC_BACKLOG.md` and turns every ROW into a `kind: backlog` item,
once per repo: after `migrated_at` is set a run creates nothing, since the adopted file's kept context
would otherwise read as fresh rows (a digest of each row's text plus its occurrence number is kept in
the item's `note`). A row starts only at a tagged entry shape (D-407): any
`## ` heading; a `### ` heading carrying a bracket tag or a resolved marker; a bullet led by a bracket
tag, a checkbox, or a strikethrough; or a row of a table with a Tag/Owner column. Every other line —
an untagged bullet, a narrative sub-header, prose, a fenced block — is body text of the row above it,
kept in full in the item's `next`. A row-start line that still fails to parse further (no tag found)
becomes an item with an empty `owner`, listed by `migrate-backlog` as needing the distributor. One
exception (D-566): a row whose body holds nothing but blank lines, `---`, comments, table separators and
the scaffold template's own placeholder lines is structure, not work, and is skipped when it is an
untagged, unresolved `## ` section heading or a template placeholder row — so a scaffolded backlog's
"Later", "Activation" and `[Item]` rows never become open items. A heading with any real body line is
still an item; nothing with content is dropped. A resolved row — a `[x]` checkbox or a leading strikethrough (either sufficient on its
own), or `✅`/RESOLVED/CLOSED/DONE/LANDED/MOOT/DRILLED/SHIPPED sitting in a STATUS POSITION (right
after the tag, as the first word of an untagged title with no checkbox, followed by `—`, `:`, `(`, a comma, a date or nothing — a leading `✅` on its own (D-566), after an em dash,
immediately before a date/D-id, or — in a table row — as a cell's first token), UNLESS negated by an immediately preceding PARTIALLY/PARTLY/NOT or a following
stays/still/remains-open phrase that is not itself past tense — becomes `done` with `legacy: true`,
exempt from the evidence rule.

After migration, `render` regenerates `docs/STRATEGIC_BACKLOG.md`'s `AUTO-GENERATED:BACKLOG` block —
byte-deterministic, no timestamp, so the daily pipeline and agents never churn it — listing every
`kind: backlog` item whose status is not `done`/`dropped` (so a `blocked` item lists too, not only an
`open` one) as `- **[owner or "unassigned"]** title (\`id\`)`, sorted by priority then owner then id.
It is the block's only writer; new backlog work is `work.py add --kind backlog`, never a hand edit of
the block. The adopting agent then deletes the migrated rows from the file and keeps its hand-written
context, since each row lives in full in its item (D-413). A repo with no `docs/STRATEGIC_BACKLOG.md` at all still gets `migrated_at` recorded by
`migrate-backlog` — nothing to migrate, but the repo enters the migration window like any other — and
`render` there is a no-op rather than a failure, the shape the fleet's unfilled template repos need.

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
`sync`/`status` and skipped by `ready`. A missing store reads as empty only through the hook-facing
API (`has_store`, `on_harvest`, `ensure_decision_item[s]`, `has_msg_digest`, `prompt_block`) and
through `sync` (one line, exit 0); every OTHER CLI verb — `add`, `assign`, `edit`, `ready`, `next`, `claim`,
`release`, `done`, `drop`, `answer`, `status`, `queue`, `triage`, `commit-items`, `render`, `migrate-backlog` — exits 1 with the `init`
refusal instead.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/command_feedback_report.py`
- `scripts/mail.py`
- `scripts/sysadmin/next_census.py`
- `scripts/work.py`
<!-- END related-scripts -->
