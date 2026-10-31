# Plan — the ledger merge driver (W-53360407)

Status: DRAFT
Profile: small
**Owner:** infra-2
**Spec:** `docs/superpowers/specs/2026-10-30-ledger-merge-driver-design.md` (CONVERGED, D-1386; review receipt `docs/development/reviews/2026-10-30-ledger-merge-driver-spec-review.md`). The spec cites code at `51716046f`. This plan cites it at `b938c583e`, after master was merged in. The resolver functions are byte-identical between the two; only their line numbers moved (§ Evidence E2).
**Base:** `b938c583e` (branch `w-53360407-entry-files`). Code files: `scripts/merge_request.py`, `scripts/install_post_commit_hook.sh`, `.gitattributes`. New test: `tests/test_merge_ledger_driver.py`. Docs: `docs/reference/multi-agent-operating-model.md`, `docs/workstation/hooks-index.md`, `CHANGELOG.md`, `docs/LESSONS_LEARNT.md`, `INDEX.md`.
**Prototype (executed):** `.tmp/runs/b61d3ce0-aa4e-4a4f-8800-4588107e6a30/fabrik-plan-after-chat-2026-10-31T00-45-06-0300/proto/` holds three files:
- `verb.py`, 22 lines: the verb's body;
- `test_merge_ledger_driver.py`: the draft tests;
- `d5.py`: the spec's D5 replay.

## What this plan is

The spec's delta, built in two code phases and a Finish:
- **Phase A:** the `merge-ledger` verb and its tests.
- **Phase B:** the installer's driver registration and the anchored `.gitattributes` lines, plus docs.
- **Phase C:** the whole-plan review, the replay grader, the ledgers and the merge request.

About 60 code lines over 3 code files, executed inline by the orchestrator (`/fabrik-plan-after-chat`'s `Profile: small`). Operator 2026-10-31: *"ok now i want the perfect merge implementation for all repos now. implement tonight"*. The coordinator added that small MRs which land tonight beat one big one.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § The delta 1-3: the verb, the driver string, `.gitattributes` | IN | Phases A, B |
| I2 | spec § Validation, each test leg: red-first with its rebase leg, DECISIONS order, refusal, duplicate-id, bootstrap, no-regression | IN | Phase A steps 3-4 |
| I3 | spec § Validation replay grader (D5, at least 58 builder merges cleared, no duplicated line) | IN | Phase C step 2 |
| I4 | spec § Validation tripwire (counter, threshold above 6, check date 14 days after landing, owner the coordinator) | IN | Phase C step 5 hands it to the coordinator with the landing date |
| I5 | spec § Validation Counter B pass (lift D5's builder filter and clean skip) | OUT-OF-SCOPE | W-6614b62e (its next line names the pass) |
| I6 | spec § The delta 4: the readers left unchanged (`check_convergence`, `decisions.py --reserve-id`, the changelog gate) | IN | Phase C step 4 runs the gate and the decisions check over the built tree |
| I7 | spec § Documentation landing sites (the op-model "always conflict" sentence, the hooks-index row) | IN | Phase B step 3 |
| I8 | spec Intake I7: `.fabrik/work` same-item conflicts | OUT-OF-SCOPE | W-7a1411b3 |
| I9 | operator: "implement tonight"; coordinator: "small MRs that land tonight" | IN | Phase C step 5, the merge request |
| I10 | rollout to project repos ("all repos") | OUT-OF-SCOPE | W-480cdb61. The verb ships fleet-wide with the sync, so the rollout is installer-only |

## Global Constraints (every phase inherits these)

- `scripts/merge_request.py` is fleet-synced (`scripts/fabrik_synced_manifest.py:52`). The new verb is inert in a repo with no `merge=ledger` attribute, and nothing else in the file changes.
- Tests run through `/opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest …` (D-935), never bare.
- Commit with explicit pathspecs and Agent Provenance Trailers. Never `--amend`. Push after each phase.
- A hub worktree commit distributes nothing; the change ships when the coordinator merges it.

## Constraints Digest (verbatim rows from the MUST-READ packs)

| Quote | Source |
|---|---|
| Every code-shipping ticket must produce exactly one entry. | `.windsurf/rules/core/40-documentation.md:134` |
| Format: Entry under ## [Unreleased] | `.windsurf/rules/core/40-documentation.md:132` |

## Phase A — the `merge-ledger` verb

Appetite: 40

**Produces:** `scripts/merge_request.py`'s `merge-ledger` subcommand. Phase B's driver string calls it as `python3 scripts/merge_request.py merge-ledger %O %A %B %P`.

**Steps** (sequential):
1. Add `_merge_ledger(base, ours, theirs, path)` beside `_merge3` (`scripts/merge_request.py:1048`), from `proto/verb.py`:
   - read the three files as bytes through `_decode` (`:778`);
   - run `_merge3`;
   - for `DECISIONS` (`:545`), refuse when `_dup_ids(result) - _dup_ids(ours)` is non-empty (`_dup_ids`, `:1266`). This is the spec's "a D-id twice that ours did not already hold twice", the same check `_build` applies at landing. The prototype's `proto/verb.py:9` subtracted theirs's duplicates too; that looser form is NOT carried over, and the Phase A duplicate-id tests exercise the spec's form;
   - write through `tempfile.mkstemp(dir=<dir of ours>, prefix=".merge-ledger-")` and `os.replace`, unlinking the temp on any exception.
2. Register the subparser beside `sync-runner`'s (`:4184`) and dispatch it before the verb table (`:4213`), as `after-merge-runner` (`:4188`) and `sync-runner` (`:4200`) are, so `main()`'s `try`/`finally` drain never runs after the rename. On any `Exception`, print `merge_request: REFUSED — <reason>` to stderr and return 1; on success return 0.
3. Add `tests/test_merge_ledger_driver.py` from the prototype, with these changes:
   - drop its placeholder `test_the_driver_runs_at_the_worktree_top`;
   - add a `git rebase` leg to the red-first test, asserting the rebase is clean;
   - rewrite the no-regression test so BOTH sides change the SAME ledger at far-apart lines: git calls a driver only for a file changed on both sides, and plain git merges such edits cleanly. Log the driver's own exit (a wrapper script that appends `$?` to a file) and assert that exit was 0, the merged blob is byte-identical to the same merge with no driver configured, and the merge exited 0;
   - rewrite the refusal test's fixture so the edit of a landed row sits next to the other side's insertion (ours edits `| D-2 |` and appends a row, theirs appends a row after `| D-2 |`). The prototype's fixture put the edit two lines from the insertion, so `git merge-file` took it cleanly and the verb exited 0; and merge the same pair through git with the driver registered, asserting the merge exits non-zero and the file holds markers with both sides;
   - add to the duplicate-id test the verb's own exit 1 with `%A` byte-identical, run directly as the refusal test does;
   - add a test that patches `os.replace` to raise, then asserts `%A` is untouched and no `.merge-ledger-` temp file is left (the only path that unlinks one).
4. RED then GREEN, using the prototype tests against `b938c583e` with no verb (§ Evidence E1):
   - 5 tests fail on `invalid choice: 'merge-ledger'`;
   - the control and the bootstrap leg pass by design (the bootstrap leg runs its own pre-verb script and proves the driver ran by its `invalid choice` stderr);
   - step 3's rewritten no-regression, refusal and temp-file tests are watched red against the verb-less tree too.
   After step 2, all pass.
5. Gate: `/opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest tests/test_merge_ledger_driver.py tests/test_merge_request_merge.py -q`, then `/opt/fabrik/.venv/bin/python -m ruff check` and `-m mypy` on `scripts/merge_request.py`.

**Behavior Contract (Phase A):**
- Concurrent insertions in CHANGELOG and DECISIONS merge clean through git with the driver, by merge and by rebase (red without it).
- DECISIONS puts the higher D-id first whichever side is ours.
- An edit of a landed row next to the other side's insertion returns rc 1 with ours byte-identical, and through git the merge leaves markers.
- A failure after the temp file is made leaves ours untouched and no temp file behind.
- A duplicate D-id refuses, and git leaves markers with both rows when the rows conflict as text.
- A tree whose `merge_request.py` predates the verb falls back to markers, with `invalid choice` on stderr.
- A merge clean without the driver stays clean and byte-identical, and the driver itself exited 0.

## Phase B — registration, attributes, docs

Appetite: 30

**Consumes:** Phase A's verb.

**Steps** (sequential):
1. `scripts/install_post_commit_hook.sh`:
   - add `LEDGER_DRIVER='python3 scripts/merge_request.py merge-ledger %O %A %B %P || git merge-file --marker-size %L -L ours -L base -L theirs %A %O %B'` and two `set_config` calls beside `:86-87`;
   - make the failure message at `:84` name the key it failed on instead of "the work-item merge driver";
   - widen the mirror regex at `:98` to `merge=(workitem|ledger)`;
   - keep `BEGIN_MARK`/`END_MARK` (`:94-95`) byte-identical.
2. `.gitattributes`: add five root-anchored lines:
   - `/CHANGELOG.md merge=ledger`
   - `/docs/DECISIONS.md merge=ledger`
   - `/INDEX.md merge=ledger`
   - `/docs/STRATEGIC_BACKLOG.md merge=ledger`
   - `/docs/LESSONS_LEARNT.md merge=ledger`

   Put them under a comment naming W-53360407 and the spec.
3. Docs:
   - `docs/reference/multi-agent-operating-model.md` § Ledgers and ids across branches (`:162-166` at the spec's base; re-anchor at build): correct the "always conflict at merge" sentence and add the driver's paragraph;
   - `docs/workstation/hooks-index.md`, in the installer's row: add the second driver.
4. Add an installer test beside `tests/test_merge_sync.py`'s, through the installer's own seam (`GOVERNANCE_SYNC_TEST=1` with `GOVERNANCE_SYNC_ROOT=<scratch repo>`, `scripts/install_post_commit_hook.sh:16-18`). Never run the installer against the shared config before landing: `ROOT=/opt/fabrik` (`:14`) is the main checkout. The test asserts:
   - the scratch repo's config holds `merge.ledger.driver` with the Phase B string;
   - its `info/attributes` mirror holds the five `merge=ledger` lines inside the unchanged work-item BEGIN/END block;
   - `git check-attr merge sub/CHANGELOG.md` prints `unspecified`.

   Then run that test and the installer tests named in its `AFTER-EDIT` header (`tests/enforcement/test_governance_sync_postcommit.py`, `tests/test_merge_sync.py`) under `/opt/fabrik/scripts/capped_run.sh`.

**Behavior Contract (Phase B):**
- The installer registers `merge.ledger.*` and mirrors the ledger lines into `info/attributes` without orphaning the work-item block.
- A nested `sub/CHANGELOG.md` gets no `merge=ledger`.

## Phase C — Finish

Appetite: 45

**Steps** (sequential):
1. Run the one heavy review (`Profile: small`'s D7 floor): `/fabrik-review` over the whole-plan diff, one receipt.
2. Run the replay grader on a fresh `git clone --shared` of the hub at the Phase C tip. In the clone:
   - write the five `merge=ledger` lines into `.git/info/attributes`;
   - set `merge.ledger.driver` to the Phase B string, but naming the BUILT script by absolute path (`python3 /opt/fabrik/.claude/worktrees/infra-2/scripts/merge_request.py merge-ledger …`). D5 checks out each historical parent, and those trees have no verb, so the tree-relative string would fall back everywhere;
   - register the work-item driver as the installer does.

   Then run `proto/d5.py <clone> /opt/fabrik "2026-10-17 00:00" "2026-10-31 00:00"` and record its output in the receipt. Expected: `driver-clears` ≥ 58 and no `dup` line.
3. Ledgers:
   - `CHANGELOG.md`: one `### Added — ledger merge driver (2026-10-31)` entry;
   - `docs/LESSONS_LEARNT.md`: the replica-versus-real-git lesson;
   - `INDEX.md`: the new test file;
   - no new D-row, because D-1386 holds the decision.
4. Run `final_gate.py --check --json` green over the built tree. It carries the changelog gate and the Decision Ledger check, the spec's unchanged readers (I6). Then push.
5. Run `python3 scripts/merge_request.py request --review <the /fabrik-review receipt> --item W-53360407` and send the `SendMessage` lines it prints. The coordinator's session holds SendMessage, so mail them if that is held. The report to the coordinator names the landing as the tripwire's start, its check date 14 days later, the counter, and the threshold above 6 (I4).

## Evidence

**E1. Prototype tests against `b938c583e`, no verb** (run 2026-10-31 under `capped_run.sh`, copy in `.tmp/runs/b61d3ce0-aa4e-4a4f-8800-4588107e6a30/fabrik-plan-review-2026-10-31T00-46-42-0300/red/`):

```text
FAILED tests/test_merge_ledger_driver.py::test_the_driver_merges_both_insertions_clean
FAILED tests/test_merge_ledger_driver.py::test_decisions_puts_the_higher_id_first_whichever_side_is_ours[| D-1390 | o |-| D-1391 | t |]
FAILED tests/test_merge_ledger_driver.py::test_decisions_puts_the_higher_id_first_whichever_side_is_ours[| D-1391 | o |-| D-1390 | t |]
FAILED tests/test_merge_ledger_driver.py::test_a_duplicate_id_refuses_and_leaves_both_rows_in_markers
FAILED tests/test_merge_ledger_driver.py::test_an_edit_of_a_landed_row_refuses_with_rc_1_and_ours_untouched
5 failed, 3 passed in 6.43s
```

**E2. The resolver is unchanged since the spec's base**, so the spec's behaviour claims carry over. The anchors moved:

```text
$ diff <(git show 51716046f:scripts/merge_request.py | sed -n '/^def _resolve_insertions/,/^# --- (a)-(d)/p') <(sed -n '/^def _resolve_insertions/,/^# --- (a)-(d)/p' scripts/merge_request.py) && echo "resolver+merge3 UNCHANGED"
resolver+merge3 UNCHANGED
```

The current anchors at `b938c583e`: `_decode` `scripts/merge_request.py:778`, `_merge3` `:1048`, `_dup_ids` `:1266`, the `sync-runner` parser `:4184`, the verb table `:4213`.

**E3.** The prototype verb, run in a scratch repo on 2026-10-31:
- it merged two conflicting insertions clean, with D-1391 above D-1390;
- it refused a duplicate D-1391 and left markers;
- it refused an edit of a landed row;
- it left no temp file behind.

## Self-audit

- 3 code files and about 60 code lines, so `Profile: small` holds. The test-line budget runs over the ~1.5× target (about 130 lines), accepted because each test is one spec § Validation leg.
- Every spec § Validation leg maps to a test: Phase A's for the verb, the rebase leg included, and Phase B's for the installer. Two legs have no test of their own. One is `_build` raising no `ConflictError` on a merge that is clean without the driver: it follows from the no-regression test, because `_build` enters its conflict path only when its `git merge` exits non-zero (`scripts/merge_request.py:1223`), and that test asserts the merge exits 0 with the driver registered. The other is the Counter B pass (I5, W-6614b62e).
