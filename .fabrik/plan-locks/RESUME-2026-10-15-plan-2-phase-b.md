## RESUME

**UPDATE 2026-10-22 07:40 — Phase B step 1 (the whole-plan /fabrik-review) ran round 1 and parked.** Seven seats,
45 candidates, 21 code defects confirmed by execution (two loosen the git rule against the pre-plan hook, one
makes the hook fail open), plus test and doc findings. All are listed in
docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md § Round 1 findings. The run
parked because the fleet's weekly quota was at its wall: every account but ob at 99%, ob at 81% of a 95 cap.

Before any more patching, answer the foundation question with the Opus + Fable panel (CLAUDE.md § Autonomy)
or a spec amendment (/fabrik-spec, Profile: delta). The question: keep growing a hand-written shell grammar, or
change approach? Candidates:
(a) fail closed: a seat's command holding any construct the scanner does not model refuses — heredoc to a shell,
    eval/source, `$'…'`, `((`/`[[`, an unknown wrapper, a conditional cd — and the false-red cost is measured by
    the replay;
(b) narrow scratch to seat folders only (`seat-*` under the run scratch) and drop the repo `.tmp` rule;
(c) the spec's approach D or a filesystem-level fence.
Then fix per the decision, run the replay, and run round 2 with the same seven seats re-verifying their own
slices.

The W-72dfd448 branch must NOT be merged before this; the hook change is only live for this worktree's own seats.

Item: W-72dfd448 (review seats may write only inside their own scratch folder).
Plan: docs/development/plans/2026-10-15-plan-2-review-seat-write-isolation.md (Phase A EXECUTED 2026-10-22).
Branch: worktree-intel, last commit = the Phase A EXECUTED commit (after dc904d604). Lock:
.fabrik/plan-locks/2026-10-15-plan-2-review-seat-write-isolation.json (active).
Parked at the 5-hour quota checkpoint (D-1113: past 90%, commit, push, seed, start nothing new).

First: `command_run.py step --phase 2` is refused until a Phase A review receipt exists. Write
docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-phase-A-review.md from the scoped run's
ledger (the plan's Evidence § Step 8 rounds 1-5 and the close's evidence: confirmed 11 → 10 → 9 → 1 → 0, readers,
neuters, replay), then step to phase 2.

Next: Phase B — Finish, from step 1.
1. The whole-plan /fabrik-review (D7 floor: the whole-plan diff by file, a Sonnet and a Haiku finder per slice as
   Agent-tool seats, D-961), receipt docs/development/reviews/2026-10-15-plan-2-review-seat-write-isolation-review.md.
   The surface is .claude/hooks/seat_guard.py, tests/test_seat_guard.py, docs/workstation/hooks-index.md, the plan,
   the spec's as-built note. Range: 9fa2aef1f..HEAD.
2. CHANGELOG.md `### Changed — review seats cannot write outside their scratch (<commit date>)`; a docs/DECISIONS.md
   row IS owed: the build took decisions the spec did not — a repo's .tmp/ (parent holds .git) is scratch;
   variables resolve for write destinations and cd only; a cd into a missing dir leaves the cwd unknown past its &&
   chain unless a mkdir on the line made it; a glob is judged by one listing of its directory (never a walk, the
   hook has 5 s). Mint the id inside the commit shell (scripts/decisions.py --reserve-id .).
3. After the merge, re-run step 7b's live probe against the merged hook in the main checkout's session; paste it
   in the receipt (D-1116 condition 3).
4. final_gate.py --check --json; commit by pathspec; push; merge_request.py request --review <receipt>
   --item W-72dfd448.
Then: plan Status EXECUTED, release the lock, close the run with done + FEEDBACK.

Queued after it: W-f365c610 (P1, the other Status readers that ignore inline code spans, use
_fences.status_candidates as in D-1114), W-ddb716ca (P3, three spellings missing from the Firecrawl proxy grader),
W-9013addb (backlog, this review's recorded heredoc variant). Infra still owes the scrape-server install
(W-f59fe72b) before plan 3's ledger U1-U7.
