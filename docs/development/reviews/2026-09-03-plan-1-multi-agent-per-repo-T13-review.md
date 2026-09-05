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
Round 1 verdict: 10 raised → 9 fix classes routed (2 H, 5 M, 2 L), 1 recorded/routed; pool layer pending. Not the no-op round.
