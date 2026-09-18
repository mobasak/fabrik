# T01b — `--commit` on the close verbs, the own-commit re-measure, the two row fields: per-ticket review ledger

Surface: `scripts/command_run.py` (+376/−0) and `tests/test_command_run_fabrik_task.py` (+922/−0),
coder worktree `agent-a96a9bd977aac5988` at `e7ff4f62`, base `bd6e6cd7`. Pure inserts: zero deletions
in either file, which is also what proves the two pre-existing `ruff format` hunks at `:427`/`:440`
(from `8255198f0`, not this ticket) were not absorbed — a reformat would appear as deletions.

## Orchestrator's independent verification (before the review seats)

The coder's own report is a claim, not proof. Each of these was re-executed here.

| Claim | How it was re-checked | Result |
|---|---|---|
| 50 graders green | `pytest` in the coder's worktree | 50 passed |
| no regression | `tests/test_command_run.py` + the new file together | **302 passed** (252 pre-existing + 50) |
| pure inserts | `git diff --numstat bd6e6cd7..e7ff4f62` | `376 0` / `922 0` |
| byte-identity for non-`fabrik-task` records | 9 real lifecycles: 3 commands x 3 close verbs, pre-script vs post-script | 0 mismatches; no `oversized_mini`/`upgrade` key on any row |
| the D-294 field order | `_task_field` read at `:3028-3036` | `<n> · commit=<sha> · paths=<first three>` — count first, as D-294 requires |
| the headline rule has a grader | `test_a_fourth_declared_file_routes_to_the_spec_chain` `:664` | present — closes the gap T01a's mutation seat found |

**Two defects in the orchestrator's own probes, found and fixed before any number above was believed.**
1. The first byte-identity probe drove `/fabrik-review`, which has a persisted-report precondition, so
   `done` was REFUSED in both arms. stdout compared equal because both arms *failed identically*. Fixed by
   choosing commands that can actually close and asserting the ledger row count is non-zero.
2. The first comparator zipped 3 ledger rows against 0 and reported `MISMATCHES: 0` — the row count was
   printed but never gated on. This is the same vacuity class the coder caught in its own M16 grader.
   Fixed by making a row-count gate the comparator's first assertion.

**Falsifiability of the probe, executed.** The close-time lane guard at `:3212`
(`if (rec.get("command") or "") != _TASK_COMMAND:`) was mutated to a constant-false test on a scratch
copy (marker verified on disk, count=1). Under the mutant every non-`fabrik-task` close REFUSES with
`REFUSED — fabrik-task: done needs --commit`, producing 0 ledger rows against the control's 3 — the
corrected comparator reports the mismatch and the probe exits 1. The guard is load-bearing, and its
failure direction is a loud refusal rather than a silent field leak.

**Mutation spot-check by the orchestrator** (the coder ran 28; these three were re-run independently, in a
throwaway worktree, each marker-verified on disk before its grader ran, tree restored clean after each):

| # | Mutation | Grader | Verdict |
|---|---|---|---|
| O1 | `_TASK_MAX_FILES` 3 -> 99 (the lane's headline rule) | `test_a_fourth_declared_file_routes_to_the_spec_chain` | KILLED (rc 1) |
| O2 | `",".join(paths[:3])` -> `",".join(paths)` (the D-294 cap) | `test_only_the_first_three_paths_are_named` | KILLED (rc 1) |
| O3 | drop `-C` from the `--name-status -M -C -z` diff | `test_a_copy_and_a_rename_in_one_commit_are_split_on_three_fields` | KILLED (rc 1) |

A process note on O1-O3: the first harness piped `pytest` into `tail`, so the shell read *tail's* exit
status and reported all three mutants as SURVIVORS when all three had in fact been killed. The verdicts
above come from the corrected harness, which gates on `$?` captured from a subshell. Recorded rather than
hidden: it is the `cmd | tail` defect this repo's own memory warns about, committed while verifying a
ticket about not trusting proxies.

**Merge preconditions, checked in the same turn as the merge claim.** `master` had not moved
(`HEAD == origin/master == bd6e6cd7`, 0 behind); neither T01b path was dirty in the shared tree; 0 sibling
commits touched either path since the base; the plan lock is `active`, owns both paths, and no other
active lock names them. `final_gate.py --check --json` -> `success`, 63 checks, 0 failures, 2 warnings
(both pre-existing and not this ticket's: a 2026-08-10 committed review, and fabrik-lib vendored drift).
`bandit`, `semgrep` and `pytest` are listed in `skipped_checks` — skipped is not passed, and that green
asserts nothing about them.

**Provenance note (not a defect, recorded so the next reader does not re-derive it).** The Board's `Commit`
column holds the coder's worktree sha, which is not reachable from `master`. Under D5 the code, the Board
flip and the Deltas land in ONE commit, and a commit cannot contain its own sha — so the authored sha is
the only value writable at flip time. Attribution is independently preserved by the merge commit's own
`Agent-Task:` trailer (verified on `2fc8beefe` for T01a), and both coder worktrees classify `wt-dirty`,
which `scratch_sweep --apply` never removes.

**D-294's divergence, re-executed rather than accepted.** The plan declares the field order
`<n> · commit=<sha> · paths=<first three>` against the spec's paths-first grammar, on the grounds that
`_cap_field` truncates the TAIL. Verified here: `_LEDGER_FIELD_CAP = 2000` (`:1602`), and `_cap_field`
keeps `text[:CAP-1] + "…"`. With a three-path payload of 2,591 chars the count-first field preserves
`commit=<sha>` through the cap while the spec's paths-first field loses it entirely. The divergence is
correct and the plan's order is the one built.

## Round 1 — acceptance review (2026-09-18)

Partitioned by file per D4 and the ticket's step 8: Opus `fabrik-reviewer` on `scripts/command_run.py`,
Sonnet `fabrik-reviewer` on the graders. `dispatch_headroom.py --slices opus=1,sonnet=1`; stamped
`command_run.py dispatch --seats 2` before dispatch. Both seats carried the ticket's eight Behavior
Contract rows as the acceptance criteria and the settled-bar fence (D-294's field order, pool OFF, two row
fields only).

### Seat B — Sonnet, the graders (`tests/test_command_run_fabrik_task.py`)

Method: both files copied md5-verified into the seat's own scratch at their exact relative paths, baseline
confirmed 50/50 green, then 10 targeted source mutations run against the scratch copy only, restoring
between each. 50 of 50 graders read in full; 10 mutations across 9 source sites.

Headline: **0 of 50 graders are fully vacuous against their primary claim.** Six mutations were caught
correctly. Four survived the entire 50-test suite — each one a branch with no grader:

| # | Severity | Site | The uncovered branch | Mutation that survived |
|---|---|---|---|---|
| B1 | major | `command_run.py:3181` | `pat is not None` on the `UPGRADE: sync` refusal — the deliberate fail-open that stops an UNREADABLE sync filter from refuting a sync claim | dropped `and pat is not None`; 50/50 still passed |
| B2 | major | `command_run.py:3004-3006` | `_task_excluded`'s `<name>`-prefix branch (`docs/reference/`, `docs/workstation/` matching a whole directory) | reduced to `return path in excl`; 50/50 still passed |
| B3 | moderate | `command_run.py:3106-3110` | the `git cat-file -t` commit-resolution guard (garbage / foreign / tree-or-blob sha) | deleted the check; 50/50 still passed |
| B4 | minor | `command_run.py:3186` | `flag = "evidence" if args.cmd == "done" else "reason"` — which flag the refusal names on a `blocked`/`handoff` close | swapped the ternary; 50/50 still passed |

B2 carries a second half worth recording: `test_the_union_counts_a_sync_hit_that_excl_already_covered`
(`:1268`) calls `docs/reference/technology-stack-decision-guide.md` "a matrix EXCL PREFIX member" in its
own docstring, but that path is ALSO a literal sync-regex hit in the fixture config, so it lands in set B
unconditionally and the test's outcome is identical with the prefix branch fully disabled. The union half
is real; the "EXCL PREFIX" half is unfalsifiable by its own fixture — the decoy-fixture class.

B5 (brittleness, not vacuity): `test_the_matrix_parser_reads_every_row_of_the_live_contract` (`:1755`)
reads the worktree's own `CLAUDE.md` rather than a fixture, hard-coding 22 rows / 25 tokens. Verified
non-vacuous by mutation, but a legitimate Doc Sync Matrix edit by any sibling turns it red with no code
change.

### Seat A — Opus, `scripts/command_run.py`

Method: every probe against the pinned file (md5 verified equal to `git show e7ff4f62:`), 7 throwaway
git repos under the seat's own scratch, `COMMAND_RUN_DIR` redirected, no git verb that writes. It
confirmed **8 of 8 Behavior Contract rows GREEN as literally specified** — and then showed row 1's
underlying CLASS is defeated anyway.

| # | Severity | Site | Defect | Confidence |
|---|---|---|---|---|
| A1 | **major** | `:3166-3174` | An undeclared COPY destination inherits the declared source's membership, so `cp declared.py undeclared.py` ships a brand-new undeclared file and scores `oversized_mini: 0`. `-C` was added by this very change to tell `R` from `C`, and the membership step folds them back together. The lane's cheapest cobra path, and it leaves no doc-shaped trace. | CONFIRMED (reproduced) |
| A2 | **major** | `:3106-3135` | The resolve leg is fail-CLOSED on a non-zero rc, conflating "git could not answer" with "the commit is disqualified". `_task_git` is `check=False`, so `safe.directory` ownership, a half-written `.git/config`, a moved checkout and a pruned worktree all return rc 128 — every SHA then refuses, `done` mandates `--commit`, so NO argument closes the run: the record stays `running` and the Stop hook blocks the turn, in ~46 repos. The catch-all four lines below exists to prevent exactly this and says so verbatim. | CONFIRMED (reproduced twice, two causes) |
| A3 | minor | `:3243-3248` | The new mandatory `--commit` has no rollout cutover, unlike `_AXIS_REQUIRED_FROM` (`:1288-1291`) which was minted for this exact class. | CONFIRMED (mechanism) |
| A4 | minor | `:3255-3262` | Every exception is labelled `unmeasurable=no-git`, including a malformed record in a repo where git is healthy — a ledger reader cannot tell an outage from a corrupt record. | CONFIRMED |
| A5 | minor | `:3149` | `declared.files` as a STRING scalar becomes a set of CHARACTERS, so the declared file fails its own membership test and is scored oversized. | CONFIRMED |
| A6 | minor | `:3237-3241` | `UPGRADE: sync` — the lane's widest claim — is recorded unchallenged whenever `--commit` is absent, because the refutation arm is unreachable from there. | CONFIRMED |
| A7 | minor | `:3061`, `:3108-3136` | Up to 5 git subprocesses at `timeout=10` while holding the record flock (~50 s worst case) on a path that previously did no I/O. | PLAUSIBLE (read) |
| A8 | minor | `:3036` | `",".join(paths[:3])` does not escape, so a path containing a comma is ambiguous to any reader splitting on it. `text=True` also universal-newline-translates a `\r` path before it is compared to `declared`. | CONFIRMED / PLAUSIBLE |
| A9 | minor | `:4409-4412` | The event/row "mirror" comment can be false: the event spread is unconditional, the row is gated on `_usage_is_required`. | PLAUSIBLE (not reached) |
| A10 | latent | `:3070-3077` | A truncated 3-field diff entry falls through to the 2-field arm and mis-pairs, instead of taking the `break` its own comment promises. Unreachable from real `git diff -z`. | CONFIRMED by reading |

Seat A's denominators: 30 close invocations across 7 repos over 22 malformed record/argument shapes;
**0 escaping tracebacks, 0 new silent-rc-0 escapes**; 5 of 5 new git call sites `check=False` and
branching on `.returncode`; 0 new `subprocess.run` in the 376 inserted lines; 9 paths probed for the
EXCL substring bug (0 defects); the `-M`-alone mis-attribution independently reproduced.

### Adjudication — dispositions

FIXED in `280ff4c84` (each with a grader, each watched red first): **A1** (the splitter now carries the
status letter; only `kind == "R"` inherits), **A2** (a `_git_unusable()` probe distinguishes a
measurement failure from a disqualification and RAISES to the catch-all), **A4** (`unmeasurable=bad-record`
for record-shape errors, `no-git` kept for real git failures), **A5** (a non-list `files` refuses to
measure rather than publish a confident number from a record nothing can trust), **A6**
(`sync (unverified)`), **A10** (the R/C arm now breaks on a truncated tail — free alongside A1).

Also fixed: **B1**, **B2**, **B3**, **B4** — the four branches seat B proved uncovered — now carry
graders. B3's grader covers the BEHAVIOUR (a blob sha and an unresolvable sha are both refused); the
`cat-file` line itself turns out to be redundant with the `%p` arm, which is defence in depth rather
than a hole, and is recorded here rather than presented as a red-on-revert it does not have.

ROUTED to `docs/STRATEGIC_BACKLOG.md`, not fixed here: **A3** (the rollout window between T01a and T01b
is closed — the lane is unreachable until T03 ships the command source, so no in-flight `fabrik-task`
record can predate the gate; a dated constant would be born dead), **A7** (plausible, unreproduced —
needs a stalled git to measure), **A8** (the JSONL row is valid and parses; the ambiguity is in a
human-read sample field), **A9** (could not be reached; the feedback gate refuses first), and **B5**
(the live-doc dependency: the ticket's own Behavior Contract row 8 MANDATES the exact 22/25 numbers, so
changing the assertion shape is a ticket-scope decision, not a review fix).

One existing grader was CORRECTED rather than weakened: `test_a_copy_and_a_rename_in_one_commit_are_split_on_three_fields`
asserted `1 · … · paths=src/café.md` and its own comment said `src/copy.py` "derives from" the declared
`src/a.py`. That comment encoded A1. The expectation is now `2 · … · paths=src/café.md,src/copy.py`.

### Round 1 verification of the fixes

59 graders pass (was 50); **311** with the pre-existing `tests/test_command_run.py`. `ruff check` clean.
`ruff format` clean on the test file; `scripts/command_run.py` deliberately NOT formatted — its only two
pending hunks are at `:427`/`:440` from `8255198f0`, authored by the D-281 build and not by this ticket.
Byte-identity for every other command RE-VERIFIED after the fixes (6 lifecycles, row count gated
non-zero, 0 mismatches) because three of the six fixes sit inside `_task_close_fields`. Against `master`
the ticket is still `429/0` and `1130/0` — **pure inserts, no deletions**, since the 16 lines the fixes
removed were lines the coder had added.

## Round 2 — delta (2026-09-18)

One fresh Opus seat over `git diff e7ff4f62 280ff4c84` plus one hop (81 changed lines in
`scripts/command_run.py`, above D-229's 20-line single-seat budget). Stamped `dispatch --seats 1`. The
brief's highest-value question is adversarial by design: **fix A2 converts a REFUSAL into a successful
`unmeasurable` close**, which is the direction that would hide scope growth — so the seat is asked
whether `_git_unusable()` can be induced (a `GIT_DIR` env var, a `.git` file, a foreign `repo_root`) to
launder a bad commit.

**Verdict: 8 CONFIRMED, all of them inside round 1's own fix diff.** The seat's denominators: 282
insertions / 21 deletions read in full, ~560 lines of one-hop context, 59 graders examined, 14
mutations proven on disk, 33 end-to-end driven closes across 8 probe scripts.

| # | Severity | Site | Defect | Disposition |
|---|---|---|---|---|
| D1 | **high** | `:3285-3289` vs `:3300-3314`, `:3224` | `sync (unverified)` closed ONE of THREE arms where an `UPGRADE: sync` claim goes unrefuted — and fix A2 *widened* one of the two left open, by converting refusals into `unmeasurable` closes. ⚠️ Round 1's own grader B1 **pinned** the hole (`assert upgrade == "sync"`), contradicting its own docstring. | FIXED |
| D2 | **high** | `:3125` | `_git_unusable()` asked whether git worked, not whether it was answering about THIS repo. `_task_git` passed no `env=`, so an ambient `GIT_DIR` made `rev-parse --git-dir` return rc 0 from a different repository. **(a)** pointed at another real repo, the honest SHA resolved nowhere → refused, record `running` — the exact fail-closed wedge A2 existed to remove; **(b)** pointed at a decoy holding only the declared file, a two-file commit closed `oversized_mini: 0` — a VERIFIED-looking zero from one exported variable. | FIXED |
| D3 | medium | test `:2014-2045` | Grader B3 passed for the wrong reason: deleting the WHOLE `cat-file` guard left all 59 green, because a blob and a garbage sha are both caught by the parent-count leg two lines below. The guard is load-bearing for exactly one input — an ANNOTATED TAG, which resolves, peels, dates and diffs perfectly. B3's docstring asserted a red-on-revert it did not have. | FIXED (tag grader added; docstring corrected) |
| D4 | medium | `:3077-3079` | Fix 6 (the truncated `R`/`C` tail) shipped with ZERO graders — 0 of 59 reached the splitter. Reverting the `break` left all 59 green. | FIXED (grader added) |
| D5 | medium | `:3313` | `unmeasurable=bad-record` is a FOURTH reason against a grammar the ticket freezes at three, and against two statements in the changed file itself saying "NEVER a fourth" — shipped with no ticket edit, no D-row, no backlog route. | **REVERTED** |
| D6 | medium | `:3284`, `:3313`, `:3241` | Every `unmeasurable=` row drops the `commit=` token, so a failed or laundered close records no SHA — the cobra mirror of fix A2, which newly routes a whole class here. | ROUTED |
| D7 | low-med | `:3289` | `sync (unverified)` is a new grammar in a field T02's frozen ticket parses by equality (`upgrade: sync`). | ROUTED |
| D8 | low | `:3176-3178` | Fix A5 guarded the CONTAINER and not its elements: `[1, 2]` still published a confident count while the comment claimed the class closed. | FIXED |
| D9 | low | test `:1978`, `:2022`, `:2050` | Three of four `path:line` citations in the new graders were stale — written against `e7ff4f62` before the fix moved the code ~43 lines. | FIXED |

Swept clean by the same seat, executed: the rename path and set B across six constructions (including
a hand re-derivation of a four-shape mixed commit → 6); the corrected copy grader re-derived
independently and confirmed right; the fail-open/fail-closed partition across seven environments;
fix 4's blast radius (`_task_size_gate` always writes a list, so no current path turns a working
close into a refusal); mutation selectivity of the other 8 fix sites (1 red each, the right one);
and `_task_diff_pairs`' single caller, so the 2-tuple → 3-tuple change breaks no cross-file contract.

## Round 3 — the fixes for round 2 (2026-09-18)

Committed `7e7e9e3dc`. The git environment is now scrubbed in `_task_git` (a FILTER, so `HOME` and
`PATH` survive); `_task_measure` returns `(rc, field, sync_tested)` and one `_mark_unverified_sync`
helper marks every untested claim on all three arms; `bad-record` reverted; the element half of the
`declared.files` guard kept. Three graders added, each proven red by deleting the code it names —
decisively, under the seat's own M11 (whole `cat-file` guard deleted) the suite now goes 63 green →
**1 failed, 62 passed**, and the one failure is the annotated-tag grader.

63 graders pass, 315 with the pre-existing suite, `ruff check` clean, `command_run.py` back to
exactly the two foreign format hunks at `:427`/`:440`. Byte-identity re-verified after the env scrub
(6 lifecycles, row count gated non-zero, 0 mismatches).

Round recorded `--own-fix 8` — every defect this round fixed was in the previous round's own fix
diff. No scope-growth warning fired (1 of the last 3 rounds qualifies).

## Round 4 — delta (2026-09-18)

One fresh Opus seat over `git diff 280ff4c84 7e7e9e3dc` plus one hop, re-sweeping the SAME open
classes rather than re-scoping: `ambient-git-env` and `partial-arm-coverage`. Stamped
`dispatch --seats 1`.

⚠️ **Orchestrator finding, queued rather than applied** (editing a pinned surface while a seat reads
it is what makes a review lie): `_GIT_ENV_OVERRIDES` scrubs 8 vars and misses
`GIT_DISCOVERY_ACROSS_FILESYSTEM` and the `GIT_CONFIG_COUNT`/`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM`
injection channel. Neither is set in the live environment (0 of 12 checked) and neither is a
reproduced launder — the lane's four verbs are object-DB and tree operations — so if round 4 does not
reproduce one, this is defence-in-depth whose honest framing is "closing the class", not "closing a
hole".

**Verdict: 5 CONFIRMED, again all inside the previous round's own fix diff.** Denominators: 198
added / 39 removed lines read in full plus 9 enclosing functions, 63 graders examined, 16 mutations
of which 13 informative, 12 git environment variables probed (9 end-to-end).

| # | Severity | Site | Defect | Disposition |
|---|---|---|---|---|
| E1 | **high** | `:844-855` (`_repo_root`) | The scrub covered the CONSUMER and not the CHOOSER. `_repo_root` ran bare, and `GIT_WORK_TREE` moves `rev-parse --show-toplevel` — so the repository the whole re-measure is taken against was still picked by an env var. Executed: the start gate's dirty check silently skipped, `declared.sha` → `unavailable`, a five-file commit closing `unmeasurable=no-git` at `state: done`. | FIXED |
| E2 | **high** | `:2723-2732` | The list was incomplete AND the repo already enumerated this class in `tests/conftest.py` (incident-driven — a hand-exported `GIT_DIR` once committed a sibling's WIP to master). The two disagreed in BOTH directions. `GIT_CONFIG_COUNT=bogus` alone makes every git verb exit 128, laundering an honest `4 · commit=… · paths=…` to `unmeasurable` at rc 0. | FIXED + drift grader |
| E3 | medium | `:2746` | `--literal-pathspecs` is INCOMPATIBLE with the other global pathspec vars and git fails hard rather than ignoring them, so `GIT_ICASE_PATHSPECS=1` made a CLEAN declared path read as dirty — and the refusal told the agent to accuse a peer of WIP that does not exist. | FIXED |
| E4 | medium | `:3285`, `:3290`, `:3358` | The `sync (unverified)` marking had ONE of its four reach-points guarded. Deleting the call on the exception arm, and forcing `sync_tested` True on the count and zero arms, each left all 63 graders green. The previous commit's "each proven red" was true of its three new graders and not of the marking fix. | FIXED (one grader, four arms) |
| E5 | low | test `:2229-2278` | The ambient-`GIT_DIR` grader reds on the REFUSAL direction only; the launder direction its own commit subject names is unobserved. | ROUTED |
| E6 | low | `:3218` | An EMPTY `declared.files` passes the element guard (`all()` of empty is True) and publishes a confident count. | ROUTED |
| E7 | low | `:3221` | The element-guard's `TypeError` names neither the offending member nor its type, and it is the only record of the cause. | ROUTED |

Cleared by the same seat, with evidence: `HOME`/`PATH` survive (the scrub is a filter); `bad-record`
is fully removed (`git grep` at the pin matched **0 files** tree-wide); `_cap_field` ordering is safe
and no double-marking is reachable; all six `_task_measure` returns carry three elements and the one
caller unpacks three; `pat is not None` is the right predicate; and mypy shows the **identical 8**
pre-existing errors on this commit and its parent — not a regression.

## Round 4 exit — the D-278 scope-growth stop

| round | found | confirmed | own-fix | qualifies (≥⅔) |
|---|---|---|---|---|
| 1 — acceptance | 19 | 6 | 0 | no |
| 2 — delta | 9 | 8 | 8 | **yes** |
| 3 — delta | 7 | 5 | 5 | **yes** |

**Two of the last three qualify, so the stop fires**, and this round takes its exit rather than
opening a round five: the named set is fixed, the residue is routed to `docs/STRATEGIC_BACKLOG.md`
with its reasons, and the review closes on the original delta. Four rounds found 19 defects — 6 in
the coder's work and 13 in review fixes — which is the finder-is-fixer dynamic the fresh-seat rule
exists to break, and the reason each round used a new non-authoring seat rather than my own re-read.

Routed, with reasons recorded in the backlog: E5, E6, E7, and the two remaining bare git calls on
`command_run.py`'s SHARED close path (`git status --porcelain`, `git log -m`) — the same class at
lower severity, deliberately untouched because T01b's acceptance rests on byte-identity for every
other command and those calls are on the path every command takes.

## Final state (committed `f0a7b6a08`)

`scripts/command_run.py` **+518 / −1** and `tests/test_command_run_fabrik_task.py` **+1,470 / −0**
against master `022c7641c`. ⚠️ The single deletion is `_repo_root`'s one-line docstring, replaced by
a longer one explaining why that call is scrubbed — so the "pure inserts" property recorded for the
earlier SHAs above no longer holds for the final state, and this line supersedes it.

66 grader functions / **69 cases** pass; **321** with the pre-existing `tests/test_command_run.py`.
`ruff check` clean; `ruff format` clean on the test file and `scripts/command_run.py` carries exactly
the two pre-existing hunks at `:427`/`:440` from `8255198f0`, which are not this ticket's. Every
grader added across the four rounds was proven red by reverting the code it names, each mutation
marker-verified on disk and each restore md5-checked against a reference captured before the first
mutation. Byte-identity for every other command re-verified after each round's fixes — six
lifecycles, row count gated non-zero, 0 mismatches.




