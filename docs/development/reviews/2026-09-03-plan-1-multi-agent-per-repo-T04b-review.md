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
Native finder (opus): PENDING — appended when it returns.

