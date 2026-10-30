# Multi-agent operating model — N named sessions, one worktree each, one merge owner

**What this covers:** how several Claude Code windows work one project at the same time without
absorbing each other's hunks: the launch recipe, the four artifacts the sync emits so a worktree can
run, the ownership surfaces (incl. adoption of an existing repo), the merge protocol, the plan-locks,
the shared database caveat, retirement, and the residual probes. Design specs: `docs/superpowers/specs/
2026-09-03-multi-agent-per-repo-design.md` (§ cited below) + `2026-09-06-multi-agent-adoption-design.md`;
decisions D-117, D-123 (the build plan), D-154/D-155 (adoption).

**The shape (§ Chosen approach):** agent-1 runs in the **main checkout, alone**; agents 2..N each
run in a **linked git worktree** under `.claude/worktrees/<name>`, on branch `worktree-<name>`, and
commit only to that branch. Conflicts move from the shared index to merge time, serialised by one
owner — a session cannot stage a file it does not have, and Claude Code's own isolation enforcement
blocks every route from a worktree into the main checkout (`git -C`, `GIT_DIR`, `cd`, and any
command shape it cannot trace). Projects adopted first; the hub now runs the model too, with its
own merge owner (§ Hub vs project, below).

## Launch recipe — one per window (§ Isolation, § Identity)

```bash
# agent-1 — the merge owner: the main checkout, NO --worktree
CLAUDE_AGENT=alpha claude -n alpha-<repo>

# agents 2..N — one linked worktree each
CLAUDE_AGENT=<name> claude --worktree <name> -n <name>-<repo>
```

⚠️ **A window that is ALREADY RUNNING does not need a relaunch** (D-271). `CLAUDE_AGENT` is
launch-time and a `/rename` never reaches it — measured, three windows named `agent-1/2/3` in the
UI all reported `CLAUDE_AGENT=<UNSET>` — so bind the live session instead, and keep its history:

```bash
python3 /opt/fabrik/scripts/whoami_agent.py --as alpha   # then --who to confirm
```

The env var still WINS where it is set, so a named launch never needs the command. Detail:
`docs/workstation/agent-identity.md`.

To reopen a repo's existing builders side by side, each resuming its own session, run
`scripts/sysadmin/agents_up.sh <repo>`. It reads the builders from `<repo>/.fabrik/session-agents.json` and gives the
coordinator no pane; each builder resumes its newest `whoami_agent.py` binding for the repo, so after a /clear the
re-bind is all it takes. The hub moves onto it once its registry is seeded (W-66e2f6a7, retiring `~/bin/hub-up`). Setup and rollout:
`docs/reference/repo-coordinator-rollout.md`.

⚠️ **A window that lands in the main checkout and is not the merge owner MOVES, it doesn't
relaunch** (spec 2026-09-29-hub-worktree-cutover-design.md § D5(a)): `EnterWorktree` into
`.claude/worktrees/<name>` carries the running conversation forward ("the transcript follows" — see
Resume, above), and a target already under `.claude/worktrees/` asks no approval. SessionStart's
move line (`.claude/hooks/session_orient.py::_model_line`) orders this — bind first
(`whoami_agent.py --as <name>`) when the session is unnamed, then move directly when it is already
named but not the owner — and lists the repo's live `whoami` bindings alongside it, so a name the
owner already holds is visible to whoever else binds it.

⚠️ **A worktree under a TRACKED `CLAUDE.md` (the hub, fabrik-lib) double-loads it.** Claude Code
loads `CLAUDE.md` from the working directory and every directory above it
(https://code.claude.com/docs/en/memory § How CLAUDE.md files load, v2.1.28x-era docs), so a
worktree at `<repo>/.claude/worktrees/<name>` also loads the main checkout's `<repo>/CLAUDE.md` as
an ancestor — a second copy that drifts stale until the worktree's branch catches up with master,
and double the context paid every turn. The condition is TRACKING, not "being the hub": a repo that
TRACKS `CLAUDE.md` (the hub, fabrik-lib, and any project that does — e.g. `ai-model-catalog`)
double-loads the same way; a project whose `CLAUDE.md` is instead gitignored and synced
per-worktree carries no second tracked copy to double. Remedy, one per
worktree, in its own untracked `.claude/settings.local.json` (never the tracked
`.claude/settings.json`, which would strip the main checkout's own contract too):
```json
{"claudeMdExcludes": ["<repo>/CLAUDE.md"]}
```
an absolute path — `claudeMdExcludes` matches glob patterns against absolute paths, at any settings
layer. The hub's T07 cut-over applies this for `fleet` and `intel`.

- **Two names, deliberately.** `CLAUDE_AGENT=<name>` is repo-local — what `owner:` fields, `**Owner:**`
  lines, `[tags]` and the `Agent-Name:` trailer carry (`agent_role.py` accepts any `[a-z0-9-]{1,32}`; a
  charter at `docs/reference/agents/<name>.md` is optional). The session name `-n <name>-<repo>` is
  **box-wide**: a bare `-n alpha` in a second repo is silently renamed and `@alpha` addressing breaks.
- **`--worktree` is the launch form for a NEW window; a RUNNING window moves with `EnterWorktree`.**
  Either way, check the gitignored set `.worktreeinclude` lists arrived and copy any missing path in
  from the main checkout (residual R1, below); an entry without it has no gate, no packs, no `.env`. A missing
  hook copy no longer blocks the prompt: every synced hook line but the two older silent guards (`agent_status.py`,
  `seat_guard.py`) checks its script is a readable regular file and, when it is not, prints `HOOK MISSING: <path>`
  with the remedy (copy the set from the main checkout, or have the hub re-run its sync) — on stdout at exit 0 for
  `UserPromptSubmit`/`SessionStart` (context Claude sees), on stderr at the non-blocking exit 1 for `Stop`
  (`final_gate_stop.py`) and `PreToolUse` (`quota_stop.py`), a transcript `hook error` notice on each — so the
  damaged checkout runs WITHOUT that hook, nagging on every prompt and tool call until the set is copied in
  (W-ed75e99d).
- Commit messages go through a file: write the message with the Write tool to the session
  scratchpad and run `git commit -F <scratch>/msg` — a heredoc, even quoted (`<<'EOF'`; an unquoted
  one is refused outright), is a compound shape the isolation check may refuse.
- **Inside a worktree, Bash is one plain command per call.** The isolation check refuses any compound
  shape it cannot trace — a quoted heredoc, a loop, brace expansion, a runtime `$var` or `$(…)`
  argument, the word `git` inside data — whatever the verb, usually wording the refusal as a git
  problem; write multi-line work with the Write tool to the session scratchpad and run it as one
  plain command, every git
  call staying on the command line (residual R8). A refusal naming auto mode is the permission
  classifier, not this check — retry it.
- Who is agent-1: the merge owner named by the ledger's `MERGE OWNER:` row (`python3
  scripts/decisions.py --merge-owner .`) — written by `/fabrik-epics-review` on the epic path (the
  first name in the epics' `owner:` set) or by `--adopt` on an existing repo (D-154).

## The four emitted artifacts (§ Lifecycle "Adoption", § Shape / infra implications)

T01a **declares** them in `scripts/fabrik_synced_manifest.py` (merged); T01b's
`scripts/sync_enforcement_to_projects.py` **emits** them into every synced project, beside the
`.gitignore` patch it already performs (T01b merged 2026-09-06 — rows 2 and 4 and the
mid-epic loop below land with it). Nothing is hand-edited in a project.

| # | Artifact | Source of truth |
|---|---|---|
| 1 | `.worktreeinclude` — the gitignored governance/enforcement/vendored set (+ `.env`, `.mcp.json`; − `.claude/settings.local.json`), copied into a worktree at creation | `worktreeinclude_text()` in `fabrik_synced_manifest.py`, rendered to `templates/governance/.worktreeinclude` (a `GOVERNANCE_TEMPLATES` pair) — on master |
| 2 | `.claude/settings.json` block `{"worktree": {"baseRef": "head", "symlinkDirectories": [".venv"]}}` — branch from local HEAD (repos carry unpushed master); one shared venv, 0 s | the hub's `.claude/settings.json`, the synced source (`AGENT_HOOK_FILES`) — on master (T01b, merged 2026-09-06) |
| 3 | `.gitignore` line `.claude/worktrees/` — Claude Code's per-worktree state dir, never tracked | `gitignore_block_text()`, the "Local state" group — on master |
| 4 | `git config --local push.autoSetupRemote true` + `rerere.enabled true` | `src/fabrik/scaffold.py` seeds NEW repos (on master); the sync's seeding for the ~46 existing repos on master (T01b, merged 2026-09-06) |

- **Mid-epic syncs** — on master (T01b, merged 2026-09-06): `.worktreeinclude` copies at CREATION only,
  so the sync's re-copy loop walks every `git worktree list --porcelain` entry under
  `.claude/worktrees/` and refreshes the set (residual R3). A secrets floor in the shared
  `info/exclude` keeps `.env`/`.mcp.json` ignored in every worktree before anything is copied.
- The shared venv is safe only while `uv.lock` is byte-identical across an epic's branches; a
  deps-changing ticket's `uv sync` or install lands in the repo's venv, so it is a serialising act
  (§ The shared runtime is NOT isolated). `.claude/hooks/seat_guard.py` refuses it from any session
  whose write would land in a worktree's shared venv (W-46d148b0); run on it as it is with `uv run
  --no-sync <cmd>`. The merge owner takes the act: an exact pin it approved runs as
  `FABRIK_SHARED_VENV_WRITE=1 uv pip install --python <main>/.venv/bin/python <pkg>==<version>`
  (the opt-in counts only when typed in the command, never inherited).

## Ownership surfaces (§ Ownership surfaces)

- **Epics** — frontmatter `owner:` + `status: 0|1|2` (TODO / in-progress / done, flipped by the
  owning agent). `python3 scripts/epic_order.py --assign a,b,c` hands each phase's epics out
  round-robin; `--check --owners a,b,c` proves one owner ∈ the set per epic.
- **Plans and specs** — the `**Owner:**` line, mandatory at creation (`/fabrik-plan-after-chat` emits `**Owner:** <CLAUDE_AGENT>`).
- **`docs/development/PLANS.md`** — the `AUTO-GENERATED:PLANS` block `| Epic/Plan | Owner | Status | Phase |`,
  regenerated by `python scripts/docs_updater.py --sync` (`--check` reports a stale block; Phase = the
  epic's `phased_order()` position or a plan's Board progress). `—` is an untagged row, filled by adoption.
- **Adoption** — `python scripts/docs_updater.py --adopt <name>[,<name>…]`, run ONCE by agent-1 in
  the main checkout (refuses below 2 live sessions unless `--single-window`; D-154, D-155; and refuses a
  first name the merge-owner readers would not read back as that owner — the un-adoption token `undeclared`, or a
  name opening with `-` — W-2118e9c9): seeds the
  PLANS markers, stamps `**Owner:**` on every open unowned plan round-robin, tags every untagged
  work-item row of `STRATEGIC_BACKLOG.md` in its own shape (the cell under a header opening
  `Owner`/`Tag` when it is empty — an occupied one, or an `Item` that already opens with a tag, is
  left alone · else the `Item` cell; never a bullet or a table with neither column — W-77e00147 — and
  never an `Item` that is only one bracketed phrase, as the template's placeholders are (`[Feature/Refactor]`)
  — W-e89d7983),
  appends the `MERGE OWNER: <first name>` ledger row (the
  row with the HIGHEST D-id whose `what` cell opens with `MERGE OWNER:`, optionally after a
  `supersedes D-NNN:` prefix — the label always the exact upper-case `MERGE OWNER:`, bold allowed (`**MERGE OWNER:**` or
  `**MERGE OWNER**:`; read by the hub's own readers at once, by a project's synced copies after its next sync; D-934) —
  wins wherever it sits in the file, and a winning `MERGE OWNER:
  UNDECLARED` row means nobody owns the repo — `python3 scripts/decisions.py --merge-owner .` reads
  it; a changed owner is a NEW row opening `supersedes D-NNN: MERGE OWNER: <name>`), and delegates the epic half to
  `epic_order.py --assign` where that hub-only script is present. The PLANS block's second header line
  then prints `<!-- Merge owner: <name> | source: D-NNN -->`.
- **The distributor — the coordinator** (`docs/reference/work-tracking.md`) is the SAME agent as the
  merge owner, in every repo (D-471, operator: *"in each repo the agent which is not on worktree must
  be merge owner and coordinator"*): the one agent in the main checkout merges branches into the base
  branch AND sets who owns which work item (`work.py assign`). `work.py init` records it in the repo's
  own `.fabrik/work/config.json`, defaulting to `python3 scripts/decisions.py --merge-owner .`;
  never pass a different `--distributor`. The two are still two fields, so a changed merge owner
  means changing `distributor` with it (the hub moved it from intel to infra under D-471, then to the
  `coordinator` under D-874). In a multi-window repo that agent coordinates and does nothing else (D-872):
  `templates/governance/CLAUDE.md` § The coordinator role.
- **Ledgers and ids across branches** (D-448) — each agent writes its own ledger rows
  (`CHANGELOG.md`, `docs/DECISIONS.md`, `docs/STRATEGIC_BACKLOG.md`) on its own branch; two
  branches that both prepend a row to the same table always conflict at merge — `rerere` only
  replays a resolution it has already recorded, so it helps with nothing new here — and
  `merge_request.py merge` keeps both sides when the conflict is a pure insertion, refusing any
  other (§ Merge protocol, below). Decision ids: mint
  with `python3 scripts/decisions.py --reserve-id .`, never `--next-id` alone — a flocked
  reservation keyed by the git common dir (so every worktree of a repo shares one file), and
  `--next-id` SKIPS a live reservation rather than reissuing it; a reservation is held until its id
  appears in the main checkout branch's ledger, not for a fixed TTL, so an id reserved on a
  long-lived worktree branch is never handed to a second agent while that branch is still unmerged.
- **The two advisories** — `docs_updater.py --check`'s single `ADVISORY:` line (never a finding) and
  the SessionStart line from `session_orient.py` fire only at ≥2 live `claude` sessions sharing the
  checkout with incomplete ownership; both never fire in a single-session repo or in the hub. The
  SessionStart line additionally never fires inside a worktree (its `/.claude/worktrees/`-in-`cwd`
  check); the `--check` advisory carries no such guard.

## Merge protocol — the merge owner only (§ Merge)

Finished work in a linked worktree is a MERGE REQUEST, and the merge owner merges it through ONE
script, `scripts/merge_request.py` (spec `docs/superpowers/specs/2026-09-30-merge-request-loop-design.md`).
This is INTEGRATION, not DISTRIBUTION: the merge owner decides merge order, never which agent owns
which work item — that is `work.py assign`, the distributor's verb (§ Ownership surfaces, above).

```bash
# 1. the finishing agent, INSIDE its worktree, on a branch pushed as itself:
python3 scripts/merge_request.py request --review <closing run record or review receipt> [--item W-xxxxxxxx]
#    → one `merge-request` mail (ack: required) to the merge owner, an `ack: no` copy to the
#      distributor when it is neither the owner nor the requester, and one `SendMessage to=<name>: …` doorbell line
#      per live recipient session (`mail.py who <agent>`) — send each with the native SendMessage tool
#    A branch cut before the script existed runs the main checkout's copy by absolute path
#    (`python3 <main checkout>/scripts/merge_request.py request …`): it finds mail.py, work.py and
#    whoami_agent.py beside itself, never in the branch. `--item` releases your claim on that item.
#    `--pretest` first runs the base's `.fabrik/merge-tests` on the merge the owner would build (a
#    throwaway at the local base) and sends only on green (a base with none is sent untested, with a
#    note), recording the merged tree in `<git common dir>/fabrik-merge/pretest/<head>.json`; the
#    merge then skips its own leg when its merged tree differs from that one only in CHANGELOG.md,
#    docs/DECISIONS.md, docs/LESSONS_LEARNT.md and work items, the same merge_request.py wrote the
#    record, and its leg ran at least a minute (W-1fb11ec8) — run it in place of a hand run of the
#    suite, never beside one.
# 2. the merge owner, in the main checkout:
python3 scripts/merge_request.py merge [<id>]   # the oldest request addressed to it, or <id>
python3 scripts/merge_request.py merge --queue [--jobs 1] [--max 4]
#    → builds the waiting requests (up to --max) as a STACKED chain in merge order (S0 the local
#      base, Sk request k merged onto S(k-1)) in pretest throwaways, runs each leg OUTSIDE the merge
#      lock in a forked child (at most --jobs at once, default 1, each at the owner script's own
#      width; a later leg forks only once the first request lands on a record or has no tree to
#      test, and only while it and a landing after it fit the wall — W-d5d1d394; the leg is budgeted
#      at 1.5 x the longest green leg the run already timed for that owner script (a changed
#      `.fabrik/merge-tests` starts again), at its declared limit until one is —
#      W-1fb11ec8), records
#      each green tree as --pretest does, then lands each request in order through the unchanged
#      locked `merge <id>`, which skips its leg on the matching tree. A request that will not build
#      is skipped and the chain continues; after each landing the rest is rebuilt on the new base and
#      every record that still matches is reused, so the requests stacked behind a REFUSED one are
#      rebuilt without it and tested again. A base with no `.fabrik/merge-tests` runs nothing outside
#      the lock: the queue lands in order. A landing starts only while its worst case still fits the
#      queue's own wall (QUEUE_WALL_S, 11100 s = a 7200 s worst-case landing + the 3600 s longest
#      leg a base may declare + 300 s: a 180 s chain build and a leg's 120 s setup and outer bound —
#      run it as `rund --timeout 11200 --
#      /opt/fabrik/scripts/capped_run.sh --timeout 11100 -- python3 scripts/merge_request.py merge
#      --queue`); past it the queue says so and stops — run it again. Exit: the worst landing's
#      (0 merged, 1 one refused, 4 one left partial, where it stops). One queue at a time
#      (`fabrik-merge/pretest/queue.lock`). W-0c8c43f1. Plain `merge` names the verb when 2+ wait.
python3 scripts/merge_request.py resume <id>    # a request left short of `replied` (exit 4)
python3 scripts/merge_request.py retry <id>     # re-run a REFUSED request whose branch is unchanged
```

`merge` holds `<git common dir>/fabrik-merge.lock`, resumes any stranded record in
`<git common dir>/fabrik-merge/` first, claims the request, and runs (a) a preflight in a throwaway
worktree with a snapshot of every merged path, (b) pure-insertion ledger conflicts and
`.fabrik/work/W-*.json` conflicts merged key-wise by `work.py merge-item` only, (c) the
owner's tests — one leg on the BOX at a time, every repo's: the leg (a merge's, a pretest's or a
queue child's) waits on the flock `~/.claude/state/merge-test-leg.lock`, saying who holds it, and a
wait that spends the run's test budget is "not a test verdict" (W-fbd1d4b9) — (`.fabrik/merge-tests`, read from base, with the throwaway's `src` first on
`PYTHONPATH`; with none, pytest over the touched `tests/` files under `<main>/.venv/bin/python` when
present, with the caller's `PYTHONPATH` dropped and the merged import root — `src`, or the tree's
root when `src/` is itself a package — placed after the stdlib and before site-packages; both legs
first get the base's `.worktreeinclude` set copied in from the main checkout, so a gitignored `.env`
is there as in a worktree, never over a file the tree tracks — D-610; the hub's own merge-tests runs
`scripts/merge_test_select.py`, W-4e756979: the tests that import a changed module (directly or
through the repo's own import graph), spell its file name or stem, or enumerate the directory it sits
in (a glob, `iterdir` or `listdir` on that directory) — never a folder a test merely mentions, and the
ledgers and work items select nothing (W-fbd1d4b9); a review receipt under `docs/development/reviews/`
by its file name only (D-1356) — plus every test whose text says `ls-files`, in 8 shards balanced by the
per-file seconds each merge leg records in `<git common dir>/fabrik-merge/merge-tests-durations.txt`
(no record: the round-robin split, W-c832e59f); it refuses a red that
is new against the base (green, absent, or failing with another crash line there) and a run it
could not finish, never one of master's own reds; a red green alone is re-run in its shard's order
only up to one test past it, every shard file still collected, and so on the base (W-c80361e4); outside a merge check it never checks out or
cleans the worktree and compares nothing; a rebuild of a branch head whose last green merge differs
from it only in the selector's SKIP set — ledgers and work items — re-tests nothing, W-347cd0c3), (d) a CAS
of the local base (up to three rebuilds; every owner-test leg of one invocation, rebuilds and the
catch-up included, draws on one budget of `MERGE_TEST_BUDGET_S` — a leg runs at most what is left,
none starts under `LEG_FLOOR_S` left, and a spent budget refuses as not a test verdict, naming
`retry <id>`, or `resume <id>` for a catch-up; a full leg is `TEST_TIMEOUT_S`, or the
`# merge-test-timeout: <seconds>` line the BASE's `.fabrik/merge-tests` declares, clamped to
`LEG_FLOOR_S`..`MERGE_TEST_BUDGET_S`, W-1fb11ec8; the leg's memory ceiling is capped_run's default
unless the base declares `# merge-test-mem: <n>M|<n>G` alone on its line, clamped to
`LEG_MEM_FLOOR_MIB`..`LEG_MEM_MAX_MIB` and passed as `--mem` — a declaration-shaped line outside that
grammar is named in the leg's verdict and ignored — and a leg capped_run stopped (exit 137 or 124) is
refused with capped_run's own last verdict line, on the merge and the pretest alike, W-e64a7b8e), (e) the carry into the main checkout — sibling WIP, untracked and staged files are never
overwritten; a path that changed is kept and listed in the reply — (f) a fast-forward push, (g) the
hub's governance sync, OWED and run by a background `sync-runner` outside the merge lock (its own
`<git common dir>/fabrik-merge/sync.lock`; a debt stays in `sync-owed.log` until a sync that started
after it succeeds; the run's end waits for it, `SYNC_TIMEOUT_S` in all, and prints `sync: ran`,
`sync: FAILED … --force`, `sync: still running in the background`, or `sync: unknown` when it cannot
read its state; a landing that cannot owe the sync says `sync: FAILED to owe or start` in its reply,
W-4f4ac600; the runner starts in its own transient user scope in `fabrik-agents.slice` — `--collect`,
`RuntimeMaxSec` `SYNC_RUNNER_MAX_S`, `MemoryMax` 4G — so capped_run stopping the merge's scope at exit
never takes it, bare where that exact scope will not start, and it starts no sync past
`SYNC_RUNNER_SOFT_S`, leaving the debt owed for the next kick — the drain's one rerun or a later
landing's, W-73d00b05), and (h) the reply to requester and distributor, then `mail.py ack done
--merge-sha`. Every merge commit it writes, a catch-up's included, ends in one Agent Provenance
Trailer block — `Agent-Role: orchestrator`, the owner's `Agent-Name` (left out, with a note, when the
owner is outside the agent-name grammar) and an `Agent-Context` (the request's names the branch,
request and item; a catch-up's names the remote/base and the request) — and no `Merged-From`: a
merge's parents already say what it took, and `scratch_sweep.py` reads that trailer on squash
commits only (D-1290). `merge` runs no `final_gate`: after `merged <id> as <sha>` it
prints that gating the merged result is the caller's duty, merge itself running only the owner tests,
with the request merge's owner-test summary, and the reply carries the duty line (W-e914202a). A refusal acks `blocked` with the refused step; the requester fixes and sends a new
request. When the reason is a conflict with the base, the requester brings the base in by MERGING it
into the branch (`git merge <base>`), never a rebase: the branch is already pushed, so a rebase could
only be republished with `--force`. A refusal that names the main checkout (a dirty,
staged or untracked owner file) is the owner's to clear and needs no change to the branch. An owner-tests
refusal of a request (never a catch-up) ends with what the same tests did, in one run, on the base the
failed run saw with nothing merged: red too (likely the base's fault), green (the failure needs the
branch's change, or is flaky), or not checked and why. A refusal the base caused is re-run by the OWNER
with `retry <id>` once the base is fixed, never re-sent by the requester. `retry` exits 1, changing
nothing, while another request for the same branch or head is open, when the head is already in the
base, or when the branch on the remote is gone or no longer points at the recorded head (the requester
superseded it); a remote it cannot reach is a refusal there too, never a deferral. Otherwise it
re-opens the mail (`mail.py requeue`, its `blocked` ack stripped), claims it again and runs every step
from (a), so a merge is acked `done --merge-sha`, and the reply carries a `retry: <n>` line naming the
refusal it supersedes (W-c751bca6). A remote the
run cannot reach (a fetch that times out or fails for any reason but a missing ref) is no refusal: the
request DEFERS — it stays claimed, nothing is replied, the next `merge` run retries it, and for the rest
of that run every request on the same remote defers without another fetch while requests on other
remotes are still served; after the merge the same outage stays resumable (exit 4) instead of parking (D-775). Mail is the durable record; the doorbell only wakes an idle session (best effort, D-463).
The Stop hook holds the owner's turn while a request waits unclaimed or a record is stranded
(`docs/workstation/hooks-index.md`). To keep a plan's epic order, merge by id in
`python3 scripts/epic_order.py` phase order. `/fabrik-execute-plan`'s § Finish (c) is the agent-side
half: a named agent's window merges nothing and removes nothing — push the branch and send the
request.

Reading a sibling's branch before or after a merge: the two-dot `git diff <base> <branch>` shows
every base commit the branch predates in reverse (added lines as DELETIONS), the same shape a silent
revert takes. Read what the branch itself changes with the three-dot `git diff <base>...<branch>`
(from the merge base), and what a merge did with `git diff <base before> <merge commit>`
(tryton-crm 01M3QJGF item 4).

A checkout with more than one writer has one more hazard. While its hooks run, pre-commit
(`staged_files_only.py`) resets every tracked file to the index (`git checkout -- .`), then
re-applies the unstaged changes from a patch in its cache (default `~/.cache/pre-commit/`). For
that window a sibling's unstaged edits are gone from disk. A sibling write to a tracked file inside
the window makes the commit fail (the hooks report modified files), and if the re-apply then
conflicts, EVERY tracked-file write made inside the window is discarded and only the patch survives
(tryton-crm 01M3QJGF item 3; W-7fd7c566). This is one more reason only the merge owner writes the
main checkout.

## Locks — `.fabrik/plan-locks/`, per working tree (§ Live locks, D-117)

The directory does **not** move. Each tree carries its own `.fabrik/plan-locks/`; step 7's overlap
scan sees the tree it runs in, which is the tree its own resume reads. A sibling agent's lock is
invisible from here and that is safe: agents commit to their own branches and only the merge owner
writes the base branch, so overlap surfaces as a git conflict at merge, not as lost work. Cross-tree
visibility is residual R7 — an additive READ of sibling trees — and is unbuilt; never write a lock
outside the tree you are in. `/fabrik-execute-plan` nests its subagent worktrees inside an agent's
worktree (two levels, ordinary git — `$GIT_COMMON_DIR` is shared) and merges into
`git branch --show-current`, never a named default. Lifecycle detail: `docs/reference/plan-lock-lifecycle.md`.

## The shared runtime is NOT isolated (§ Lifecycle)

Worktrees isolate FILES. The runtime is one per repo: one dev database, one app container, one
worker, one bind-mounted module — every worktree's code runs against it. So the scarce resource in
a repo with a stateful dev stack is not the files but the **serialising acts**: any act that changes
the runtime for every worktree at once — running a migration, reloading or upgrading a module
(`trytond-admin -u <module>`), restarting the app or worker, starting, stopping or resetting a
shared container, reseeding the dev database, syncing or installing into the repo's venv (a linked
worktree's `.venv` is a symlink to it — trade-intelligence lost it twice in one day, 01M3RYGETK). Measured in tryton-crm on the model's first real day
(01M3PM5H, D-442): 7 of 11 open items needed a module reload to APPLY.

- **Develop in parallel; take the act from the merge owner.** Reading, reproducing, writing code
  and running tests against the running stack are parallel — the serialisation is a mutex on the
  ACT, never on the item. Ask the merge owner (a peer message) before a serialising act, do it,
  and say when it is done; the merge owner grants one at a time, because another agent's in-flight
  test run reds under a reload it cannot attribute. Reading the runtime (a `docker ps`, a query)
  is anyone's.
- **The repo names its own acts.** List them under `## Serialising acts` in the repo's
  `docs/OPERATIONS.md`; the list above is the default when a repo names none.
- **The item carries it.** An item whose completion needs a serialising act gets the tag the repo
  uses for it (`work.py add|assign --tag runtime`), so the constraint travels with the item and
  `ready` prints it — not with the distributor's memory (§ Claim or assign, below).
- **Where the runtime mounts the main checkout, unmerged code is not what it runs.** It runs what
  the main checkout holds (a merge is live in the next fresh process, before any reload), so a
  worktree's tests against the stack exercise the BASE code: the red half of a seen-red can be
  watched there, the green half cannot. Prove the red-then-green pair by running the worktree's code
  in-process against a throwaway database clone (a clone the shared container serves still runs the
  main checkout), and budget the merge owner's reload window in the plan (tryton-crm 01M3QJNH F2).
- **Migrations have a stricter owner.** The epic schema's single-migration-owner rule —
  `epic_order.py --check` reports two epics of the same phase that both own `alembic/versions/**`
  or `db/schema.sql` ("at most one may") — still holds: one ticket owns any migration.

## Claim or assign (D-442)

The distributor is not a gate on every item — a worker that waits for an assignment while the store
already offers `claim` has turned one agent into a serialisation point. Since D-521 (D-512: "no agent
waits idle if there is work to be done") the distributor also keeps every present worker at the floor
of queued work (`work.py triage --apply`), a worker whose queue runs empty rings it, and the Stop hook
holds both sides to it (`docs/reference/work-tracking.md` § Ownership and the distributor). Between
top-ups, **self-service** still holds: an idle agent runs `work.py ready`, claims what it will do, and
says so — except in a repo whose committed config sets `coordinator_mode: true`, where a builder (a pool
worker, not the feedback owner) claims what the coordinator queued it: `next` and `ready`'s claimable list
show its own items only (D-873). The
distributor **assigns** where self-service would go wrong: items tagged for a serialising act
(above), items that must not run concurrently with another, and a queue the distributor has not
yet triaged (a migrated or polluted one) — say so to the other agents while it lasts, so they know
to wait for an assignment instead of claiming.

## The Agent-Name trailer is a claim (D-442)

No project repo installs a commit hook that checks `Agent-Name:` (the hub's guard is installed in the
hub only) — the trailer each agent writes is a CLAIM, verified by nothing but `git interpret-trailers --parse` confirming it parses. Bind the
session (`whoami_agent.py --as <name>`, § Launch recipe) so run records and `work.py` actions resolve the
same name; in the hub, `check_commit_trailers.py` compares the signed name against `CLAUDE_AGENT`
or that binding and warns on a mismatch (advisory, D-034).

## The tail (§ The tail)

Agent-1 runs the pipeline from `5-certify` once every branch is merged: `/fabrik-features` REFRESH →
`/fabrik-conformance-review` (E ≥ 2) → `/fabrik-user-test` | `/fabrik-service-test` →
`/fabrik-deploy-checklist` → `/fabrik-release` → Gate 2. "Ready to be deployed by the hub" IS
`/fabrik-release`'s definition; no new command.

## Retirement (§ Lifecycle)

- **A worktree:** on the agent's last epic, after its branch is merged — `ExitWorktree` (or the exit
  prompt) with `remove`, then `git worktree prune` (or `python3 /opt/fabrik/scripts/scratch_sweep.py --worktrees` — lists every registered worktree with its verdict and reason; `--apply` removes only the merged + clean + unlocked + unheld, and a HARNESS-created tree — which is what `EnterWorktree` makes, so it is what you have here — needs `--include-harness` on top and is still refused if it is dirty or unmerged; a tree registered by a session other than yours is refused too, unless `--foreign-older-than DURATION` lets the classifier judge it on its own state). A dead session leaves its worktree locked:
  `git worktree list` is the truth, `git worktree unlock` then `remove`. Resume an unfinished window
  with `claude --resume`, launched from the main checkout.
- **The model:** revert the four artifacts above; nothing else changes shape.

## Residual probes — results at build (§ Open / blocking unknowns)

| Probe | Question | Result |
|---|---|---|
| R1 | does `.worktreeinclude` fire on `EnterWorktree`? | **Observed both ways**: an early probe (T01b, scratch repo) carried only tracked files; at the hub cut-over (2026-09-30, Claude Code 2.1.280) both `EnterWorktree` moves (`fleet`, `intel`) received `.env` unaided, with no `WorktreeCreate` hook configured in the project or user settings. So after a move, check the gitignored set arrived and copy any missing path in from the main checkout. `--worktree` is the launch form for a NEW window, where `.worktreeinclude` fires |
| R2 | does the wip-net snapshot linked worktrees? | **On master (T13, merged 2026-09-06)**: `wip_backup.sh` snapshots each dirty worktree to `refs/wip/wt-<name>-<ts>`; on master today it walks the main trees only |
| R3 | fire rate + cost of the mid-epic re-copy loop | **Measured** (T01b): 3 of 45 synced projects carried worktrees (82 in all); zero cost where there are none |
| R6 | nested subagent worktrees from an isolated session | **Written as a once-per-repo step** in `/fabrik-execute-plan` step 8; default if blocked: subagents on branches inside the agent's worktree |
| R7 | may worktree A read B's `.fabrik/plan-locks/`? | **Unprobed, unbuilt**; default: per-tree visibility (sufficient — § Locks above) |
| R8 | does the isolation check refuse git-free compound shapes? | **Measured yes** in 5 repos: site-provisioner 2026-10-06 (01M4926XSB — five quoted, git-free shapes, ~10 retries across 5 agents), tryton-crm 2026-10-03 (01M41SCNE0), fabrik-lib (01M3W95RYB — the word `git` inside a mail body), trade-intelligence (01M3Z1CN), iterative_image_editor (01M3XRJF, 01M3QA5R); the working remedy in those mails was the Write tool for the file and one plain command to run it. Rule: § Launch recipe, "Inside a worktree, Bash is one plain command per call" |

## Hub vs project (§ Decisions derived (b))

Projects adopted first; the hub runs the same model now, cut over by
`docs/superpowers/specs/2026-09-29-hub-worktree-cutover-design.md` (D-447) once its two hub-only
hazards were closed. **The `coordinator` is agent-1** since 2026-10-15, the merge owner, alone in
`/opt/fabrik` — the `supersedes D-453: MERGE OWNER: coordinator` row (D-874), so
`python3 scripts/decisions.py --merge-owner .` reads `coordinator`; it is also the distributor
(`.fabrik/work/config.json`), so one agent holds both roles here as in every repo (§ Ownership surfaces,
above), and it builds nothing (D-872; charter `docs/reference/agents/coordinator.md`, launch
`CLAUDE_AGENT=coordinator claude -n coordinator-fabrik --model sonnet`). Infra (agent-1 from D-453 until
D-874), fleet and intel work in `.claude/worktrees/infra`, `.claude/worktrees/fleet` and
`.claude/worktrees/intel`. A fourth hub agent, **kaizen**, works in
`.claude/worktrees/kaizen` since 2026-10-06 and owns the feedback loop — every command-feedback
queue, a command's or rule's wording, ways-of-working mail — through the store's `feedback_owner`
key rather than by being the distributor; it is not a pool worker (`work.py::_workers` drops it),
so triage never routes general backlog to it. Launch: `CLAUDE_AGENT=kaizen claude --worktree kaizen
-n kaizen-fabrik`; its charter is `docs/reference/agents/kaizen.md`.

**Two acts stay main-checkout-only, both closed hazards the hub carried that projects never did:**
- **The corpus render.** `commands/assemble_commands.py` PRUNES every installed command/skill absent
  from the rendering tree's own `_sources/`, so only the main checkout may render box-wide;
  `main_checkout_refusal()` (`commands/assemble_commands.py:1369-1414`) names the reason, and
  `_guard_main_checkout()` (`:1417-1421`) — called before both a render and `--extract` — refuses
  from a linked worktree with `exit(3)`, fails CLOSED on any git error, and names the main checkout
  to render from after merging (`--check` and a `--dest` preview elsewhere stay available anywhere).
- **Governance distribution.** The post-commit sync (`scripts/governance_sync_postcommit.sh`) still
  runs only in the main checkout and syncs nothing from a worktree commit. A `.git/hooks/post-merge`
  hook (installed by `scripts/install_post_commit_hook.sh`) now runs the same sync in `post-merge`
  mode over `ORIG_HEAD..HEAD` — every path a fast-forward or `--no-ff` merge just brought in — so a
  merged branch's synced-surface commits distribute on the merge, not (as before) never; a
  conflicted merge concluded by `git commit` keeps reaching the sync through the ordinary
  post-commit path, whose first-parent read already lists what the merge brought in. The commits a `git pull
  --rebase` or `rebase` brings in, and a `reset --hard`, fire no hook (a rebase fires post-commit only for each local commit it replays) — the remedy is `scripts/sync_enforcement_to_projects.py --force`.

**The write-root rule (spec § D3).** Every hub script that writes a TRACKED file resolves its root
from the git toplevel of the tree its invoker runs in, never a hard-coded `/opt/fabrik` or a
caller-pinned `cwd`: `src/fabrik/config.py::_resolve_fabrik_root` (`:34-65`) returns `$FABRIK_ROOT`
when set, else — when the cwd is inside a linked worktree whose git common dir's parent is
`/opt/fabrik` — that worktree's own toplevel, else `/opt/fabrik`; the same function is replicated
(not imported — a worktree's `import fabrik` would still resolve against the main checkout, see
below) in `scripts/sync_projects.py:45-67`, `scripts/vps_sync.py:36-58` and
`scripts/command_feedback_report.py:46-68`. So a worktree agent's
`fabrik apply` bookkeeping (`data/projects.yaml`, `PORTS.md`, `docs/PROJECT_CATALOG.md`) lands on
that agent's own branch, attributed to it, never dirtying the main checkout. ⚠️ **The shared
`.venv`'s editable install still pins `import fabrik` to `/opt/fabrik/src`**
(`.venv/lib/python3.12/site-packages/_editable_impl_fabrik.pth` reads the literal path
`/opt/fabrik/src`, symlinked into every worktree per the settings block below) — a worktree's own
edits to `src/fabrik/` are invisible to a plain `import fabrik` in ANY worktree's Python process
until they are merged into the main checkout; only the write-root rule's subprocess/file-path
resolution is worktree-aware, not the import system.

**Hub identity from a worktree (spec § D4).** `scripts/final_gate.py::_is_hub` and
`scripts/enforcement/check_vendored_drift.py::_is_hub` treat a tree as the hub when it carries
`scripts/fabrik_synced_manifest.py` and its git common dir's parent is `/opt/fabrik`, so a hub worktree
gets the hub's self-exemptions and the vendored-drift check grades the worktree's OWN governance set;
any git failure reads as "not the hub". From any linked worktree, `scripts/enforcement/check_doc_links.py`
resolves a doc ref to a GITIGNORED path through the main checkout (a fresh worktree lacks generated
files); a tracked file missing from the worktree, or an in-repo `../` ref, is still a real break. In a
PROJECT it also exempts the Fabrik-synced docs named by `.fabrik/synced.lock` as SOURCES, and a linked
worktree without its own lock (`.worktreeinclude` never carries it) reads the main checkout's.

T01b's settings block ships from the hub because the hub's `.claude/settings.json` is the synced
source, and it is **not inert here**: on CLI 2.1.258 `baseRef: "head"` applies to `--worktree`,
`EnterWorktree` and agent isolation, and the hub has live worktrees. `.worktreeinclude` (new at the
cut-over, hub root) lists `.env` for the same reason projects' does — `.venv` needs no entry, it is
already a `symlinkDirectories` entry in `.claude/settings.json`.

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/merge_request.py`
- `scripts/merge_test_select.py`
<!-- END related-scripts -->
