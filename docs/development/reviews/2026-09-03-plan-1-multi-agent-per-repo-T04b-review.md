# Acceptance review — T04b (plan set 2026-09-03-plan-1-multi-agent-per-repo)

**Status:** IN-PROGRESS

**Surface:** the coder's worktree branch (worktree-agent-a81361228b7696d5d, head 5d6035cd) against its merge base 1abbc7dd — `commands/_sources/fabrik-plan-after-chat.md` +26/−1, `commands/_sources/fabrik-execute-plan.md` +47/−8. Coder: native Opus worktree (Execution Discipline: opus for T04b); Gate 1 red-before (0) → 2; `--check` from the worktree drifts exactly the two files; `check_command_corpus` green; 0 `plan-locks` references removed (D-117 honoured).

## Round 1
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 1.

### Adjudication (pool layer)
- gemini — CLEAN (no literal `master` merge target left; glob rules identical in both files and to T05a; `**Owner:**` unset case `—` and the spine grammar rows; the R6 probe's blocked outcome written; the nesting note superseded; its one [1] is a description, not a defect).
- deepseek — 1 raised: the R6 probe step states the action only for the BLOCKED outcome; the allowed outcome has no written continuation → carried to the native finder (a one-clause fix).
- qwen — 1 raised: "exactly TWO levels" vs an agent inside its own worktree dispatching a subagent that needs isolation (level three) — the ticket's own text says subagent worktrees nest inside an agent's worktree as ordinary git — carried to the native finder to settle against the spec § Live locks wording.
### Native finder (opus) — claims (b)(c)(d)(e)(h)(i) VERIFIED by execution (T15's `—` glyph agrees verbatim; 0 `plan-locks` lines deleted; refuse-and-continue matches the D-loop's 🔴/blocked-end rule; the R6 probe matches spec R6 clause for clause; `--check` drifts exactly the two files). 8 raised:
- [H] plan-after-chat :610-611 (mirror execute-plan :453-460): "SEEDS this section from the epic's `owned_paths`" writes GLOBS into `## File Scope`, whose grammar the same file states twice is literal-only (:284, :598) — executed on a fixture (File Scope = `src/a/**`): `check_plan_tickets` → 2 ERRORs (glob rejection :1132-1139 + collapsed containment); literal paths → 0 findings; a glob-seeded spine also mints a glob lock (execute-plan :398) → FIXUP (1): seed by EXPANDING to literal paths, globs stay the ceiling.
- [H] execute-plan :98-105 vs :118-120: the deleted "Don't nest a worktree … work in place" rule's ORCHESTRATOR half is stated nowhere; "Isolate concurrent runs" still applies unconditionally → three levels from an agent window → FIXUP (2).
- [M] § Finish (:1015, :1017, :1075) and :149-150 still assert the run's commits are on `master`, contradicting the BASE rule → FIXUP (3). [M] § Finish step 4's `git -C "$MAIN" worktree remove/prune` is the operation spec D12 (design.md:99) records as BLOCKED inside an isolated session → FIXUP (4). [M] the containment rule has no disposition for an unresolvable `Epic:` path / absent `owned_paths` (plan-after-chat :637-638 "breaks it" is not one; the corpus's own :301-302 records the fail-open class) → FIXUP (5). [M] § Isolation model's diagram (:680 "main worktree (orchestrator)") contradicts :98-100 which cites it → FIXUP (6).
- [L] glob rules match T05a except the `dir/` token (T05a: a File-Scope directory entry must match a `**` epic glob) → FIXUP (7). [L] Gate 2 red from the worktree by construction — the merge-time render (orchestrator; recorded for T16 as a plan-text defect).
- Pool carried items: the R6 allowed-outcome continuation → added to the fixup; qwen's three-level scenario → is finding (2).
Round 1 verdict: 8 raised → 7 fix classes routed (2 H, 4 M, 1 L) + 1 orchestrator note; pool 1 carried into (2), 1 folded into the fixup. Not the no-op round.

## Round 2 — over the FINAL head `1b61afd6` (23,301 B; the round-1 fixup: seven classes — literal seeding proven on the fixture (glob: 2 ERRORs; literal: 0), the third level closed, BASE through § Finish and the push, the D12 cleanup owed, BLOCKED on an unreadable epic, the diagram, `dir/` + the R6 pass outcome)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 2.
### Adjudication (pool layer)
- deepseek — CLEAN (4 rows; DO-NOTs; BLOCKED on both surfaces; two levels; both orchestrator positions in the diagram; cleanup OWED; R6 both outcomes; no literal `master` target; glob rule = T05a).
- qwen — CLEAN (every row located by line in both files; `BASE` at :95-98, :520-522, :852-854, :976-978, :1035-1038; nesting :90-107, :640-652; OWED cleanup :1068-1073).
- gemini — 3 raised: the D-loop pseudocode line (:374) shows only 🔴 where the prose (:425) names the ticket, the path and the epic → a wording nit carried to the native finder; "`—` for an unset `CLAUDE_AGENT` is semantically empty" — REFUTED: `—` is T15's own untagged rendering (verified verbatim by the round-1 native finder), and the rule's point is that the LINE is never absent; a third (truncated) about orphaned worktrees under a D12 block — the OWED report names the exact path and commands, which is the disposition.
### Native finder (opus) — all 7 round-1 fixes CONFIRMED FIXED with lines quoted; the fixture re-run: literal seeding → 0 findings, glob seeding → 3 ERRORs (the two predicted classes + the glob ERROR itself); the 11 `master` occurrences classified (5 the main-checkout value of BASE, 2 the prohibition, 4 non-target prose); `check_plan_lock_release.py` has no branch dependency; `check_plan_tickets`/`check_convergence` tolerate the new header lines. 5 raised:
- [H] a run that isolated ITSELF into a worktree (step 8) has no merge-back disposition: the diagram folds it into position (b), § Finish assigns the merge to a "merge owner" only for a named agent's window, and no merge owner exists for a self-made tree (spec :102/:238 define the role in the named-agent topology only) → the work is pushed to an isolation branch and abandoned → FIXUP (1).
- [M] § Inter-Phase Parallelism (:974) still gives each parallel phase its own worktree — the third level the new rule forbids (no hunk touched that section) → FIXUP (2).
- [M] step 4's ⚠️ orders a NAMED agent's window reported as OWED-for-removal at every Finish — the operator's launch created it and the spec retires it on the agent's last epic (:268, :54); step 4's own provenance guard forbids touching it → FIXUP (3).
- [L] the BASE enumeration lists two positions (:107-108, :1037-1038) where the diagram lists three → FIXUP (4).
- [L] both surfaces assert an emit-time containment gate in `check_plan_tickets` that T05a builds (0 `epic` hits on master) — plan-intended forward reference; RECORDED for T05a's merge, no fixup.
Round 2 verdict: 5 raised → 4 fix classes routed (1 H, 2 M, 1 L), 1 recorded; pool 2 CLEAN + gemini's nit carried into (4). Not the no-op round.

## Round 3 — over the FINAL head `537f75fe` (27,883 B; the round-2 fixup: § Finish's three positions with position (b) merging itself back in the main checkout, § Inter-Phase Parallelism under the two-level rule, the OWED clause narrowed, BASE as three positions)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 3.
### Adjudication (pool layer)
- gemini — CLEAN (10 checks by line across both files: seeding + header, Owner, lock directory, containment refusal, BASE propagation, two levels, parallelism, the three Finish positions, merge→verify→cleanup, the OWED clause).
- qwen — CLEAN (8 checks; "step 5's lock release works post-cleanup because the lock is in-repo").
- deepseek — 2 raised: "position (b)'s lock lives in the removed worktree, so step 5 cannot release it" — the lock file is TRACKED in this plan (`git ls-files .fabrik/plan-locks` lists it; not ignored), so it travels with the merge into `$MAIN` — carried to the native finder, which was briefed on exactly this check; "the Branch-model note still enumerates two positions" — checked by grep on the branch (below).
### Native finder (opus) — round-2 fixes: (1)(2)(3) FIXED with lines quoted; (4) NOT fixed at :154 (the Branch-model note). 8 raised:
- [H] position (b)'s "merges BASE back in the MAIN checkout ITSELF" promises the operation the harness refuses unconditionally from an isolated session (spec D12 :99, :115, R4 :331 "resolved by design: impossible; the merge owner lives in main"); the spec's mechanism `ExitWorktree` (:54/:247/:268) has 0 hits in the file → FIXUP (1): push BASE → ExitWorktree → merge in main → verify → remove → push; OWED only when headless.
- [H] "the plan file and its lock travel with the merge" — nothing commits the lock (9 `plan-locks` hits, none staged); `git worktree remove` refuses a tree with an uncommitted lock (proven in a scratch repo) → FIXUP (2): the lock is committed in every phase commit.
- [M] "cd $MAIN" is itself a blocked redirect (:115) → dropped in (1). [M] steps 5–7 have no home on the OWED path → FIXUP (4). [M] :153-154 two-position note (deepseek's pool item CONFIRMED) → FIXUP (5), the orchestrator's merge-time fixup withdrawn. [M] :1054 cites § EXIT, which defers plan runs to this § Finish → FIXUP (6). [M] "merge owner" defined twice → FIXUP (7). [M] three present-tense claims about gates that do not exist yet (T05a's containment check, T15's PLANS table) → FIXUP (8): phrase as the contract the sibling enforcement keys on.
- Mechanical: `--check` drifts exactly the two files (the third, fabrik-spec.md, is master's T04a); corpus check green; 0 lock references deleted; Part B/C clean; the D-loop pseudocode and prose agree on refuse → 🔴 → blocked-end.
Round 3 verdict: 8 raised → 8 routed (2 H, 6 M). Not the no-op round.

## Round 4 — over the FINAL head `ab29fc63` (30,597 B; the round-3 fixup: position (b) leaves isolation via `ExitWorktree` (keep) then merges in the main checkout; the lock committed with every phase commit; the OWED path homed; three positions everywhere; "merge owner" reserved; the § EXIT citation dropped; forward references phrased as the contract)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 4.
### Adjudication (pool layer)
- deepseek — CLEAN (4 rows; no fail-open; no `git -C`/`cd "$MAIN"`/literal master; the twelve terms consistent).
- gemini — CLEAN (rounds 1–3 classes; the merge-then-remove order satisfies git's own refusal; Owner/Epic interfaces).
- qwen — CLEAN (4 rows by line; the lock committed beside the plan file :904-913; refusal :414-415/:462-480; BASE everywhere).
### Native finder (opus) — all 8 round-3 items CONFIRMED FIXED (the `git worktree remove` refusal proven in a scratch repo; locks tracked, not ignored; the `action: "remove"` claim true to the tool contract; 5 "merge owner" occurrences all the main-checkout role; corpus check green; 0 lock lines deleted; Part B/C clean). 5 raised:
- [M] :1096 "ExitWorktree … refuses a tree carrying uncommitted work" is false for the `keep` action the same step mandates (only `remove` refuses) → FIXUP (1).
- [M] :122-123 names `isolation:"worktree"` — the Agent tool's dispatch parameter — as how THIS run isolates itself; `ExitWorktree` operates only on trees entered via `EnterWorktree` (0 hits in either file) → position (b)'s primary path is unreachable as written → FIXUP (2): `EnterWorktree` is the entry.
- [M] plan-after-chat :231-232 lists the `**Owner:**`/`Epic:` header lines under "gate-enforced grammar" — no enforcement script reads either today → FIXUP (3). [M] :637-639 asserts a live PLANS.md regeneration (generator retired 2026-07-20; T15 revives it) → FIXUP (4).
- [M] :1103-1105 the position-(b) merge in the main checkout has no clean-tree precondition and no conflict disposition, unlike the Merge Protocol (:914-923) — on a tree three sessions share, dirty is the expected state → FIXUP (5).
Round 4 verdict: 5 M → FIXUP routed; pool 3/3 CLEAN. Not the no-op round.

## Round 5 — over the FINAL head `208c40de` (32,442 B; the round-4 fixup: EnterWorktree as the run's own isolation, the `keep` contract, the header lines as contract, the PLANS phrasing, the shared-tree merge precondition with DEFER/abort → OWED)
Finders: pool deepseek/deepseek-v4-flash + google/gemini-3-flash-preview + qwen/qwen3-max + native opus×1 — round 5.
### Adjudication (pool layer)
- deepseek — CLEAN (4 rows; no fail-open: unreadable epic → BLOCKED, no ExitWorktree → OWED, dirty main → DEFER).
- gemini — CLEAN (4 of 4 rows; 2 of 2 files; 0 DO-NOT violations; glob-aware containment :425/:608).
- qwen — CLEAN on every class; its one residual ("nowhere does the diff implement the seeding logic in code") — REFUTED: the surface is a COMMAND source (prose the agent executes), not a script; the instruction IS the implementation.
### Native finder (opus) — all 5 round-4 items VERIFIED against the loaded `EnterWorktree`/`ExitWorktree` contracts and a live `git worktree remove` probe (refuses untracked; removes after commit; unmerged commits do not block it); § Finish (a)/(b)/(c) ≡ the diagram ≡ step 8; 9 lock references intact; the salvage `.diff` is gitignored so it cannot block removal; corpus check green; Part B/C clean; the four rows traceable. 2 raised:
- [M] plan-after-chat :232 "no check in this list reads them" is false for the `Epic:` half in either state (the containment check T05a builds lives inside `check_plan_tickets.py`, one of the list's named enforcers) → FIXUP (1): the checks do not VALIDATE the two lines' presence or shape.
- [L] execute-plan :482's BLOCKED example lacks the `searched:`/`missing:` clauses :182 mandates (the sibling passage has them) → FIXUP (2).
Round 5 verdict: 2 (1 M, 1 L) → FIXUP routed; pool 3/3 CLEAN. Not the no-op round.

