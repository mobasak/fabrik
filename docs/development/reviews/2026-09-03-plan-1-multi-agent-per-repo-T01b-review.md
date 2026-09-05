# Acceptance review — T01b (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch (worktree-agent-ae36d1bbd7a83c091, head b79c918b) against its merge base 7b71c336 — 3 files (`scripts/sync_enforcement_to_projects.py` +152, `tests/test_sync_worktree_adoption.py` +169 new, `.claude/settings.json` +4). Coder: native Sonnet worktree; 6 passed; both R1 probes recorded (plain `.worktreeinclude` and the 5-`#`-header variant both copy the gitignored file — comment lines are inert, the T01a-routed finding is CLOSED); fire rate measured by one `--dry-run`: 3 of 45 projects carry linked worktrees (seo 28, trade-intelligence 23, web-ecommerce-factory 31 = 82), so the R3 loop ships (FIX DIRECTIVE 5).

## Round 1
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 1.

### Adjudication (pool layer)
- gemini — CLEAN over the 3 Touches (seed: local scope, idempotent, key order matches scaffold, silent on non-git; resync: porcelain parse, `is_dir` on each entry, dry-run early return; settings block exact; tests assert real git state).
- qwen — 3 raised: (1) `git config --local --get` non-zero conflates "unset" (rc 1) with "error" (rc ≥2) so a corrupt config skips seeding — carried to the native finder as an evidence item (best-effort semantics are documented in the docstring: "unwritable: silently skip"); (2) the "Re-syncing worktree artifacts into N linked worktree(s)" line prints under `--dry-run` — NOT a defect: the ticket says "print the count" and dry-run's job is to report; (3) copytree-from-a-stale-main speculation without a failing input — no finding.
- deepseek — 7 raised, 5 self-refuted in its own text (dry-run branch, pruned entries, count-once, dry-run writes, capsys order — all "actually correct"); 2 stand: `tests/test_sync_worktree_adoption.py:161` pins the baseline as the hardcoded sha `7b71c336` via `git show` (fails on any checkout without that object; a hub-only test, so bounded, but the sha is a magic constant), and `:168-169` compares `hooks`/`permissions` as PARSED JSON while the ticket says byte-identical — a reflow or key reorder passes. Both CONFIRMED by the orchestrator's read of the test (quoted lines 150–169).

### Native finder (opus) — 12 raised (every check executed against the branch worktree)
- [H] `resync_worktree_artifacts` (~:315-331) copies `.mcp.json` — plaintext API keys in every project — into linked worktrees that do NOT ignore it: the sync patches only the MAIN checkout's tracked `.gitignore`, a worktree's copy comes from its older branch. Measured: 82 of 82 live worktrees unignored (`git check-ignore -v .mcp.json` → no rule; main checkout → `.gitignore:173`); `.env` 0 of 82 by branch age only. → FIXUP (1): seed the essentials into the shared `info/exclude` or refuse the copy; real-invariant test.
- [M] docstring (~:301) records a fire rate of ZERO as the keep-justification — false: 3 of 45, 82 worktrees, seo alone 267 files × 28 per sync → FIXUP (2).
- [M] the R3 premise is wrong: `.fabrik/synced.lock` is not among the 56 `worktreeinclude_text()` patterns, so a worktree has no lock and `check_synced_unmodified.py:68-71` SKIPS (never "green against a stale copy"); the resync call (:809) precedes the lock write (:897) → FIXUP (3): move the call after the lock, copy the lock, test byte-equality; rewrite both docstrings.
- [M] `tests/…:161,168` pins `git show 7b71c336:` — a simulated SessionEnd hook addition reds it; 8 hooks/permissions commits since 2026-08-01 → FIXUP (4): durable invariant, no SHA.
- [M] "R1 probe has no receipt" — REFUTED as delivered: the receipt is THIS artifact (D4); both probe outputs are recorded verbatim below.
- [L] key order reversed vs `scaffold.py:5991` → FIXUP (5). [L] orphans never pruned → FIXUP (6, mirror the main sync or state it does not prune). [L] `--backup`/`--force` not threaded → FIXUP (7). [L] count line printed before any copy and swallowed by `tail -3` in production → FIXUP (8). [L] `ruff format --check` would reformat the test → FIXUP (9). [L] `--dry-run` "Would set" ×82 is one-off → no change.
- [L] `.claude/settings.json:137` `baseRef: "head"` is NOT inert on the hub (CLI 2.1.258 schema: applies to `--worktree`, EnterWorktree and agent isolation; the hub has 9 live worktrees; no delta today only because `origin/master == master`) — the plan's Global Constraint "the settings block is inert on the hub" is FALSE → recorded for the whole-plan review (T16), no code change.
- [L] the branch conflicts with current master (`git merge-tree`: CONFLICT in the script at the insertion point, c22bd91c) → FIXUP (first step: merge master).
Coder claims verified: (a) seed semantics ✓ except key order; (b) resync edge cases ✓ (non-git, prunable, outside-anchor, missing source, symlinked path); (c) settings ✓ — `hooks`/`permissions` md5-identical, old text a byte-exact prefix of the new, schema-valid; (d) 6 red-first by revert ✓ (the weak "attribute absent" red); (e) fire rate ✓ exactly (3 of 45; 82 = 28+23+31; 12 of 45 repos have worktrees somewhere, only 3 under the anchor). Both changed files are governance-sync triggers (`.pre-commit-config.yaml:143`); the worktree commit did not fire it (`governance_sync_postcommit.sh` pwd guard), the main-checkout merge will — and that run is the one that would write `.mcp.json` into 82 worktrees, which is why (1) merges before it.

### R1 probe receipts (verbatim from the coder's run; the ticket's "receipt")
- plain `.worktreeinclude` naming `carried.txt` (gitignored, untracked): `claude -p --worktree probe-agent … "git branch --show-current; cat carried.txt"` → `"result":"worktree-probe-agent\nSECRET_CARRIED_VALUE_12345"` — the gitignored file was copied in.
- the same with the tracked template's 5 `#` header lines above the entry → `"result":"worktree-probe-agent2\nSECRET_CARRIED_VALUE_67890"` — comment lines are inert (T01a-routed question CLOSED; no manifest/template change).

Round 1 verdict: 12 raised → 10 fix classes routed to the coder (1 H, 3 M, 6 L), 1 refuted-as-delivered, 1 recorded for T16. Not the no-op round.

## Round 2 — over `5fd58526..16b59ddd` (36,454 B; the round-1 fixup: master merged at 90d568a3, ten classes, 12 passed + 40 neighbours)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 2.
### Adjudication (pool layer)
- gemini — CLEAN over the 8 behaviours (config seeding, worktree discovery, secrets-exclude seeding via the git-common-dir, check-ignore verification, dir mirroring with pruning, `--backup/--force`, lock syncing after the lock write, settings durability).
- qwen — CLEAN; the info/exclude seeding judged safe for 45 repos because `.env`/`.mcp.json` are already in the synced `.gitignore` block (a repo-wide safety net, not a behaviour change).
- deepseek — 1 raised: `_project_worktree_dirs` returns ALL linked worktrees, not only those under `.claude/worktrees/`, contradicting its docstring — the round-1 native finder proved the opposite by probe on b79c918b ("worktree outside `.claude/worktrees/` → skipped via `relative_to`"); whether the fixup changed that is carried to the native finder (a docstring-vs-code check).
Native finder (opus): PENDING — appended when it returns.
