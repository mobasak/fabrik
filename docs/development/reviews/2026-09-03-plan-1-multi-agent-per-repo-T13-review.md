# Acceptance review — T13 (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch (worktree-agent-aca08762aa41073a1, head 507df6ac) against its merge base 9c35928f — `scripts/wip_backup.sh` +79/−2, `tests/test_wip_backup.py` +118. Coder: native Sonnet worktree (the plan's Execution Discipline said pool for `complex`; the D6 record from T03a's rejected pool attempt made native the coding lane for every ticket); 9 passed (5 + 4); rows 1, 3, 4 red-first; row 2 honestly flagged green-on-both; shellcheck absent on the box, `bash -n` clean.

## Round 1
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 1.

### Native finder (opus) — verified: placement (worktree loop :99-114 above the main-tree `|| continue` at :117), 2 deletions both replaced by the prune widening, `KEEP_DAYS=7` and the main recipe untouched, index isolation proven (a file staged only in the worktree lands in the wt ref; a main-tree-only edit does not; the real worktree index/HEAD/stash unchanged). 10 raised:
- [H] `locked` worktrees are SKIPPED, and on this box `locked` means an agent is RUNNING (`locked claude agent agent-… (pid …)` on two live hub worktrees, one dirty) — the feature skips its own primary case; the recipe on a locked scratch worktree succeeds end to end. The ticket text itself prescribes the skip → ORCHESTRATOR DECISION (reversible; minted as a ledger row at merge): snapshot locked worktrees; skip only clean/missing/unenterable → FIXUP (1).
- [H] no dedup: 3 runs on an unchanged dirty worktree → 3 refs, 1 tree; at `*/15` = 96 refs/day/worktree; census 22 dirty `.claude/worktrees` worktrees across /opt (9 in the hub) → ~14,784 steady-state refs against 440 today → FIXUP (2): rolling `refs/wip/wt-<name>` + dated refs only on a tree change, mirroring `autobackup` + `bak-*`.
- [M] `git update-ref` exit unchecked; a basename git rejects (a space) logs "snapshotted" with no ref → FIXUP (3). [M] an unenterable (chmod 000) worktree is dropped with zero log lines → FIXUP (4). [M] the scope guard is a textual prefix; under a symlinked ROOT every worktree vanishes silently → FIXUP (5).
- [M] the `.claude/worktrees/` restriction leaves `/opt/youtube/.kilo/worktrees/frost-nightshade` (2,718 dirty paths, excluded from the main snapshot too) and the `.tmp/subagents/agent-*` worktrees uncovered → ORCHESTRATOR DECISION (reversible; ledger row at merge): any linked worktree under `$repo/` → FIXUP (6).
- [M] wt snapshots never leave the box (only `autobackup` is pushed, :146-150; the script header promises a push) → FIXUP (7): push the rolling refs like `autobackup`.
- [L] the prune's `${ref##*-}` deletes `wt-2020` blindly (tail sorts before the cutoff) → FIXUP (8): timestamp shape check; rolling refs exempt. [L] row-2 test passes with the feature absent (3 failed, 6 passed on the base script) → FIXUP (9): a dirty sibling in the same repo. [L] nothing enforces the precondition that the main tree ignores nested worktrees (hub: `.git/info/exclude:11`, not `.gitignore`; projects: T01a's synced line) — the fixture's `info/exclude` and the fleet's `.gitignore` line are equivalent for the snapshot → RECORDED, routed to T15's doc.
### Adjudication (pool layer)
- gemini — CLEAN (placement :100 above the main-tree check; isolated index in a subshell; `${ref##*-}` parse; skip paths; tests assert refs/content; quoting present; one [L] remark on `exit 0` inside the subshell vs `return 0` outside — consistent bash, no defect).
- qwen — CLEAN on placement, prune parse, malformed-ref `continue`, missing-dir log, locked skip (the last now overridden by decision (1)).
- deepseek — 1 raised: "the scope guard is built from the trailing-slash loop variable, so the pattern is `repo//.claude/worktrees/*` and no worktree is ever snapshotted" — REFUTED by execution: the suite's dirty-worktree test creates the ref (9 passed on the worktree; the native finder proved the ref's tree content by `cat-file`), so the guard matches; the textual-prefix fragility it points at is the native finder's finding (5), fixed by normalising both sides.
Round 1 verdict: 10 raised → 9 fix classes routed (2 H, 5 M, 2 L), 1 recorded/routed; pool 0 beyond the native set (1 refuted). Not the no-op round.

## Round 2 — over `9c35928f..666343d8` (23,819 B; the round-1 fixup: nine classes, 18 passed)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 2.
### Adjudication (pool layer)
- gemini — CLEAN (realpath normalisation; the tree-dedup; sanitisation + captured update-ref errors; the rolling ref pushed; the prune's explicit digit classes).
- qwen — 4 raised: the sanitised-name COLLISION (`a b`/`a-b` → one rolling ref) — CONFIRMED (also deepseek's) → FIXUP; one push per worktree per run — measured by the native finder: the dedup gate precedes the push, so only changed worktrees push (a one-off 23 × ~1.9 s first run) → folded into the fixup as a single batched push per repo; the `{8}` prune pattern — NOT a defect (explicit digit classes); the dangling-ref dedup — self-heals (the native finder proved it) → made explicit in the fixup.
- deepseek — the collision (same).
### Native finder (opus) — all 9 round-1 fixes FIXED by execution; the main-tree path byte-identical (39 lines) except the mandated widening; 13 of 13 T13 tests red against the base script. 5 raised + 1 out of scope:
- [M] the basename collision (sanitisation AND identical basenames under different parents — `.claude/worktrees/beta` vs `.tmp/subagents/beta` → one ref, the first worktree's WIP unrecoverable, both log "snapshotted"; 0 duplicates among 112 live worktrees today) → FIXUP (1: `<name>-<8 hex of sha1(realpath)>`).
- [M] four failure paths drop a dirty worktree with NO log line (unborn HEAD; one chmod-000 FILE loses the readable files too) → FIXUP (2). [M] the rolling ref is IMMORTAL for a removed worktree (locally and on origin; 17 live vs 30 ever-created hub worktrees) → FIXUP (3: a reaper). [L] `mktemp` failure leaks stderr and drops the worktree silently → FIXUP (4). [L] the isolated-index invariant unguarded on the worktree path → FIXUP (5: a test).
- [L] out of scope, pre-existing: `/opt/fabrik-lib{,-account,-review}` are one repo visited three times by the outer loop, each overwriting the shared autobackup → recorded for the backlog.
- Incident: a leaked `/tmp/wip-index-rn-kit-sandbox.*` found mid-review — the coder's runs were all under a scratch ROOT; the leak was the box's PRODUCTION cron (master's unfixed script, PID observed holding the lock) — evidence FOR the class, fixed by the trap in the fixup.
Round 2 verdict: 5 native + 3 pool → FIXUP routed (one batch, landed at 6feccf4e + 901fcb4b, 28 passed). Not the no-op round.

## Round 3 — over `9c35928f..901fcb4b` (55,086 B; 28 passed)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 3.
### Adjudication (pool layer)
- gemini — CLEAN (the reaper spares an unmounted-but-listed worktree via `wt_live_file` :77; the push file's lifetime under the trap; `--ignore-errors` captured as a "partial add" warning; realpath on both sides; quoting; `bash -n`).
- qwen — CLEAN (17 new tests; all failure paths log once; id8 collision prevention; batched push; traps).
- deepseek — 1 raised: when `mktemp` for `wt_live_file` fails the script falls back to `/dev/null`, so the reaper sees no worktree as live and could delete every rolling ref → carried to the native finder (its brief covers the reaper's false-orphan path; the quoted guard `[ "$wt_live_file" != "/dev/null" ] &&` suggests the reaper is skipped in that case — to be settled by execution).
### Native finder (opus) — 7 of 8 round-2/3 fixes VERIFIED by execution (collision ids; one batched push — `GIT_TRACE` shows 2 pushes: the worktree refspecs + autobackup; the dangling ref; the temp index gone on every path incl. a genuine SIGTERM mid-`git add` on a 95 MB tree, red-on-revert against master; one line per failure path; `--ignore-errors` cannot yield an empty tree — the index is seeded from HEAD; the reaper's happy path and the false-orphan probe (a prunable-but-listed worktree is recorded live before the `-d` check); the isolated-index invariant; the incident: the production cron runs master's script, byte-identical, with NO trap — the class confirmed and reproduced; no residue on the box now). 4 raised:
- [H] the reaper FAILS OPEN on an empty live-ids set — a linked worktree at ROOT level (`/opt/fabrik-lib-account`, `/opt/fabrik-lib-review` today, 2 of 57; fabrik-lib carries 7 live agent worktrees) enters the outer loop as a "repo" with no worktree beneath it, or `mktemp` fails for the live file → every `wt-<name>-<id8>` rolling ref of the SHARED store deleted locally and on origin (proven twice: a still-registered dirty worktree lost its only snapshot) → FIXUP (1): fail closed (empty/unavailable list → skip; never reap from a gitdir-file "repo").
- [H] the live-ids guard has zero coverage (the three-line guard deleted → 28 passed) → FIXUP (2).
- [M] the MAIN-tree `git add -A` has the same one-unreadable-file class, silently (no log line, no snapshot) — the ticket freezes main-tree semantics → RECORDED for the backlog (class completion after the plan).
- [L] the partial-add line embeds git's multi-line stderr → FIXUP (3).
Round 3 verdict: 4 raised → 3 fix classes routed (2 H, 1 L), 1 recorded; pool: deepseek's mktemp item CONFIRMED as trigger B. Not the no-op round.

## Round 4 — over `9c35928f..866c593a` (65,647 B; the round-3 fixup 866c593a: the reaper fails CLOSED on an empty/unavailable live-ids set and never reaps from a gitdir-file "repo"; the guard covered; the partial-add line single-line; 31 passed)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 4.
### Adjudication (pool layer)
- gemini — CLEAN (31 passed; the fail-closed reaper + the top-level-"repo" skip, the isolated-index invariant, push batching, collision ids, the widened scope; its three numbered items are confirmations — the accepted cost, the top-level worktree's own autobackup snapshot being correct under the shared ref-store, the lazily-quoted trap verified by `test_main_tree_temp_index_is_cleaned_up_on_signalled_interruption`).
- qwen — CLEAN (4/4 contract rows implemented and tested; DO-NOTs; Touches; the worktree snapshot placed above the main-tree dirty check).
- deepseek — 1 raised: a repo whose LAST linked worktree is removed keeps its orphan rolling ref pinned (the live-ids file is empty → reaper skipped) — this is the cost the round-3 fixup ACCEPTED by design (fail closed over greedy), stated in the script's own skip line; not a new class. Whether an enumeration that itself proves emptiness (`git worktree list` returning only the main tree, vs `mktemp` failing) may reap is put to the native finder.
Native finder (opus): PENDING — appended when it returns.

