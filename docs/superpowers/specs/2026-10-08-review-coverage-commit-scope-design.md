# The review-coverage gate grades committed-but-unintegrated reviews

**Status:** DRAFT
**Profile:** delta
**Size:** small (≈180 lines, 2 files)

Work item W-f847a317 (from W-23b86f9e's `/fabrik-task` UPGRADE `tradeoffs`; tryton-crm mail 01M3YD067C). Research
ledger: `docs/reference/research/2026-10-08-review-coverage-commit-scope-ledger.md` (32 rows).

## Personas

- **PRIMARY — the agent session finishing a task in a project repo**, in the reporter's words: *"the check reads only
  UNCOMMITTED files, so committing first and gating afterwards passes it silently — the cheapest way to satisfy it
  without the outcome."* Its loop: (1) commit its review receipt, (2) run `final_gate.py --json`, (3) read the verdict.
  Step budget: 3 steps, unchanged by this delta. The delta makes step 3 a red when the committed receipt is not
  converged, where today it is green.
- **The merge owner** (agent-1 in the main checkout; infra in the hub) runs the same gate over the commits it merged
  but has not pushed. It owns merged content, so a red there is its to clear.
- **Worktree agents (2..N)** whose branches have no upstream: their range is their own branch's non-merge commits.
- **The daily pipeline** commits in the main checkout; it runs no review receipts today.
- **AUTOMATED consumers:** `scripts/final_gate.py` (passes `--base`, reads the exit code); the hub's pre-commit hook
  `review-coverage-staged` (explicit-path mode, unchanged); `scripts/sysadmin/liveness_audit.py` (asserts the check
  exists and is warn-free).

## Goal

A review artifact committed before the gate runs is graded by the gate's blocking battery exactly as an uncommitted
one is, without ever reddening a session for a commit it did not make in its own unintegrated range.

## Why this exists

`scripts/enforcement/check_review_coverage.py` builds its blocking set from `git status --porcelain` only (`_changed_md`,
:94-136). A committed review is clean in `git status`, so only the narrower advisory `_committed_nonquiet` sees it —
and that advisory missed a review that fails `_grade` three ways (design critique, Opus, 2026-10-08). The commit-time
hook that would catch it exists in 1 of 39 repos with a pre-commit config (the hub's `review-coverage-staged`), and
pre-commit config is per-stack and unsynced (`scripts/fabrik_synced_manifest.py:98-99`). So in every project,
commit-then-gate passes green. Measured 2026-10-08: 45 committed artifacts flagged by the advisory across 13 repos.

## What exists today

- `_changed_md(root, prefix)` — porcelain over `docs/development/reviews/`, archived and `-archive.md` excluded,
  untracked skipped with a NOTE (`check_review_coverage.py:94-136`). It strips quotes and never unescapes, so a
  non-ASCII review name (octal-escaped by `core.quotePath`, ledger rcs-6) is silently NOT graded.
- `_running_review_receipts(root)` joins a running review record's receipts (`main`, :3229-3233).
- `_committed_nonquiet(root, skip)` — the non-blocking advisory over committed files, mega reports graded with
  `live=False` (:2792-2860).
- `_grade(p, root)` — the full blocking battery; mega reports graded with `live=True` (:3145-3185).
- `scripts/final_gate.py` runs the check with no arguments (`run_optional_check`, :1729-1736) and owns the change-set
  base: `_diff_base()` (:2828-2846: upstream → `_linked_worktree_base()` (:3409-3431, D-442) → origin/master →
  origin/main).

## The delta

1. **`--base <ref>`** on `check_review_coverage.py` — the integration branch. `final_gate.py` passes its own
   integration ref: `_linked_worktree_base()` when non-empty, else `origin/master`, else `origin/main` (deliberately
   NOT the branch's upstream: pushing a worktree branch must not take its reviews out of scope before they are merged —
   the push-first cobra). A bare run without `--base` resolves the same three steps itself (one helper, one order).
2. **`_unintegrated_md(root, prefix, base)`** — review artifacts touched by NON-MERGE commits reachable from HEAD and
   from neither `<base>` nor `origin/<base-branch>`:
   `git log -z --no-merges --name-only --format= --diff-filter=d HEAD --not <base> [origin/<base-branch>] -- <prefix>`.
   Non-merge excludes the merge commit of a catch-up merge (ledger rcs-3); `--not origin/<branch>` excludes commits a
   worktree merged in from a remote ahead of its local integration branch; `--diff-filter=d` drops deletions (rcs-5);
   `-z` returns names unquoted (rcs-6/rcs-7). Same exclusions as `_changed_md`. A git failure (rc ≠ 0 — an orphan
   branch, no merge base, a shallow history: rc 128) returns empty plus one NOTE printed after the ⚠ block; never a
   traceback. No resolvable base → empty (today's behaviour).
3. **`main()` no-path scan:** unintegrated artifacts join the BLOCKING set (deduplicated on the resolved path). They
   join the committed scan's skip set unless they are `Status: IN-PROGRESS` — so a committed IN-PROGRESS receipt keeps
   its advisory and nothing is reported twice. A failure from this set prints `NOTE: <path> entered history in <sha>
   (<Agent-Name trailer or author>)`, so a merge owner sees whose commit it was.
4. **Mega reports in the unintegrated set are graded with `live=False`** — a committed report is not re-hashed against
   epics that legitimately moved after it (matches `_committed_nonquiet`).
5. **`_changed_md` reads `git status --porcelain -z`** — the non-ASCII skip closes for the working-tree scan too
   (rcs-8: no quoting under `-z`; rename entries reverse their field order under `-z`, handled).
6. The OK line's denominator names both sources: `N changed + M unintegrated review artifact(s)`.

## Contract deltas

None — no data contract, no UI. The check's CLI gains `--base` (additive; the explicit-path mode is untouched).

## Cost

≈180 code lines across `scripts/enforcement/check_review_coverage.py` and `scripts/final_gate.py`; one graders file.
Fleet: synced on merge (the governance-sync trigger covers `scripts/enforcement/`). Blast radius measured by the plan's
build step over every `/opt` repo before merge.

## Validation

Graders (a real git repo with a bare `origin`, a linked worktree, and a local integration branch):
- an unintegrated failing review reds the no-arg scan; the same review merged into the integration branch is advisory
  only;
- a worktree branch PUSHED to its own remote but not merged stays in scope (the push-first cobra);
- a catch-up merge of the integration branch into a feature branch adds none of its commits' reviews;
- a sibling's unpushed commit on the main checkout's branch does not enter a linked worktree's range;
- an orphan branch / no merge base → exit 0 with the NOTE, no traceback;
- an unintegrated IN-PROGRESS receipt → exit 0 and still advised, printed once;
- a non-ASCII review name is graded (both the working-tree and the unintegrated scans);
- a committed mega report is graded `live=False`;
- `final_gate.py` passes `--base` and a project whose checker predates `--base` is not reachable (they sync together).
Each grader is seen red first (`.windsurf/rules/core/45-testing-strategy.md:22`).

## Decisions taken

- **Chosen: (B) integration-base range, non-merge commits.** A three-seat judge panel (Sonnet ×3, handed the
  approaches without a recommendation) ranked (B) first unanimously: the only option that closes the bypass through the
  gate every repo already runs, with one base definition.
- **The main-checkout window is ACCEPTED and attributed, not excluded:** its unintegrated commits are the merge owner's
  and the pipeline's; the merge owner owns merged content, and the NOTE names the commit's author.
- **Item (a) of the mail is by design:** a cert report carrying a Coverage Checklist is also graded by `check_file`
  (`commands/_fragments/term-coverage.md:20`); routing has keyed on the checklist heading since round 27.

## Rejected alternatives

- **(A) Advisory widening** — the full battery as a ⚠ advisory on committed reviews: never reds the wrong session, but
  leaves commit-then-gate green; all three judges scored it as not closing the problem.
- **(C) Synced pre-push hook** — the field's standard place for committed-but-unpushed checks (pre-commit's pre-push
  stage, rcs-14; githooks rcs-9/rcs-10) but killed here: a second enforcement surface, and the one fleet hook installer
  (`scripts/install_post_commit_hook.sh`) refuses a set `core.hooksPath` rather than resolving it (four /opt repos set
  one), so the check would silently not run where it matters.
- **Upstream as the base** (final_gate's own first choice for ruff/mypy) — pushing a worktree branch would leave scope
  before merge: the push-first cobra.
- **`base...HEAD` diff (three-dot)** — includes merge commits' content brought in by catch-up merges (case B).
- **Attribution by session authorship** (the Stop hook's transcript parse) — final_gate has no session context; the
  range is the attribution.
- **A baseline/ratchet** (betterer, golangci-lint new-from-rev — rcs-29/rcs-30) — answers "don't regress", not "grade
  this change".
- **Syncing the commit-time hook to projects** — pre-commit config is per-stack by design (`fabrik_synced_manifest.py:98-99`).

## Lifecycle

Adoption: on merge the governance sync distributes the checker and `final_gate.py`; the next gate run in each repo
grades its unintegrated reviews. Growth: the range grows with unmerged commits; a worktree with hundreds of unmerged
commits costs one `git log` call. Degradation: no base or a git failure → today's porcelain-only scope plus a NOTE.
Retirement: superseded if the commit-time hook ever becomes part of the synced surface. Sibling: `check_convergence.py`
carries the same porcelain-only hole — W-699a271a.

## Grounding

- **G1** `git diff A...B` is `git diff $(git merge-base A B) B` — https://git-scm.com/docs/git-diff (2026-10-08; rcs-1).
- **G2** `--no-merges` = `--max-parents=1`; lowercase `--diff-filter=d` excludes deletions —
  https://git-scm.com/docs/git-log and https://raw.githubusercontent.com/git/git/master/Documentation/diff-options.adoc
  (2026-10-08; rcs-3, rcs-5).
- **G3** paths with bytes > 0x80 are octal-escaped unless `-z` — https://raw.githubusercontent.com/git/git/master/Documentation/config/core.adoc,
  https://git-scm.com/docs/git-status (2026-10-08; rcs-6, rcs-8).
- **G4** `@{u}` is the configured remote-tracking branch — https://git-scm.com/docs/gitrevisions (2026-10-08; rcs-11).
- **G5** changed-files gates take an explicit range against the integration branch: diff-cover compares to `origin/main`
  with `...` by default — https://github.com/Bachmann1234/diff-cover; lint-staged's branch recipe uses
  `git merge-base main HEAD` — https://github.com/lint-staged/lint-staged#filtering-files; pre-commit `--from-ref
  origin/HEAD --to-ref HEAD` — https://github.com/pre-commit/pre-commit.com/blob/main/sections/advanced.md (2026-10-08;
  rcs-13, rcs-17, rcs-19).
- **G6** trailers are the per-commit attribution channel when identities are shared —
  https://git-scm.com/docs/pretty-formats and https://docs.github.com/en/pull-requests/how-tos/commit-changes/creating-a-commit-with-multiple-authors
  (2026-10-08; rcs-25, rcs-26).

fabrik-lib verdict: BUILD inside the hub's own enforcement script — no module covers git range scoping; not a
fabrik-lib candidate (hub-specific gate plumbing).

## Constraints Digest

| Quote | Source |
|---|---|
| A test THIS change adds/modifies that was never seen red (no fail-first, no red-on-revert proof) | `.windsurf/rules/core/45-testing-strategy.md:200` |
| Watched-fail-first (for tests this change adds or modifies; trivia stays skipped per the Behavior Contract) | `.windsurf/rules/core/45-testing-strategy.md:22` |
| every ticket enumerates its distinct user-observable behaviors / acceptance criteria and tests each one | `.windsurf/rules/core/45-testing-strategy.md:20` |

## Documentation landing sites

The checker's module docstring (its `--help`); `INDEX.md`'s check_review_coverage row; `docs/workflows/FINAL_GATE_WORKFLOW.md`
(the check's row: blocking scope = working tree + unintegrated range); `CHANGELOG.md`; the D-row minted at approval.

## Residual unknowns

- **R1** `@{u}` with no upstream is not stated in gitrevisions (rcs-12) — irrelevant to the chosen base, which never
  reads the upstream.
- **R2** The main-checkout window grades merged-but-unpushed reviews against the merge owner, not their author — accepted
  (Decisions taken); measured blast radius today 0.
- **R3** A repo whose default integration branch is neither the main checkout's branch nor master/main falls back to
  porcelain-only — the plan measures how many /opt repos that is.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | "certification ledgers under reviews/ get review-report grammar" | OUT-OF-SCOPE | by design (term-coverage.md:20); replied in mail 01M4ECC9F8 |
| I2 | "committing first and gating afterwards passes it silently" | IN | The delta 1-3 |
| I3 | the linked-worktree base the first design omitted (critiques, both seats) | IN | The delta 1 |
| I4 | a base that resolves while the diff fails (rc 128) must not traceback | IN | The delta 2 |
| I5 | `core.quotePath` silently skips a non-ASCII review name | IN | The delta 2, 5 |
| I6 | a committed mega report re-hashed against moved epics (`live=True`) | IN | The delta 4 |
| I7 | double reporting of one file by the advisory and the battery | IN | The delta 3 |
| I8 | `check_convergence.py` has the same porcelain-only hole | OUT-OF-SCOPE | backlog W-699a271a |
| I9 | blocking on "unpushed" moves the cobra to push-first | IN | The delta 1 (integration base, not upstream) |
| I10 | the shared main checkout reds a session for a sibling's commit | IN | Decisions taken (accepted + attributed NOTE) |
| I11 | the cert commands never teach `Status: IN-PROGRESS` | OUT-OF-SCOPE | kaizen mail 01M4ECCQ2T |
