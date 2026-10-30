# Plan — the ledger merge driver (W-53360407)

Status: DRAFT
Profile: small
**Owner:** infra-2
**Spec:** `docs/superpowers/specs/2026-10-30-ledger-merge-driver-design.md` (CONVERGED, D-1386; review receipt `docs/development/reviews/2026-10-30-ledger-merge-driver-spec-review.md`)
**Surface:** base `0c165f5ad`. Code files: `scripts/merge_request.py`, `scripts/install_post_commit_hook.sh`, `.gitattributes`. New test: `tests/test_merge_ledger_driver.py`. Docs: `docs/reference/multi-agent-operating-model.md`, `docs/workstation/hooks-index.md`, `CHANGELOG.md`.
**Prototype (executed, in scratch):** `.tmp/runs/b61d3ce0-aa4e-4a4f-8800-4588107e6a30/fabrik-plan-after-chat-2026-10-31T00-45-06-0300/proto/` holds `verb.py`, `test_merge_ledger_driver.py` and `d5.py`. The verb merged two conflicting insertions clean with D-1391 above D-1390, refused a duplicate D-1391 with markers left, refused an edit of a landed row, and left no temp file.

## What this plan is

The spec's delta, built in two code phases and a Finish:
- **Phase A:** the `merge-ledger` verb and its tests.
- **Phase B:** the installer's driver registration and the anchored `.gitattributes` lines, plus docs.
- **Phase C:** the whole-plan review, the ledgers and the merge request.

About 60 code lines over 3 code files: inline execution by the orchestrator, per this command's `Profile: small`. Operator 2026-10-31: *"ok now i want the perfect merge implementation for all repos now. implement tonight"*. The coordinator added that small MRs which land tonight beat one big one.

## Intake Inventory

| I# | Item (anchored) | Disposition | Where |
|---|---|---|---|
| I1 | spec § The delta 1-3 (the verb, the driver string, `.gitattributes`) | IN | Phases A, B |
| I2 | spec § Validation (red-first, DECISIONS order, refusal, duplicate-id, bootstrap, no-regression tests) | IN | Phase A steps 2-3 |
| I3 | spec § Validation replay grader (D5, at least 58 builder merges cleared, no duplicated line) | IN | Phase C step 2 |
| I4 | spec § Validation Counter B pass (the pass that lifts D5's builder filter and clean skip) | OUT-OF-SCOPE | W-6614b62e (its next line names the pass) |
| I5 | spec § Documentation landing sites (the op-model "always conflict" sentence, the hooks-index row) | IN | Phase B step 3 |
| I6 | operator: "implement tonight", coordinator: "small MRs that land tonight" | IN | Phase C step 5, the merge request |
| I7 | rollout to project repos ("all repos") | OUT-OF-SCOPE | W-480cdb61; the verb ships fleet-wide with the sync, so the rollout is installer-only |

## Global Constraints (every phase inherits these)

- `scripts/merge_request.py` is fleet-synced (`scripts/fabrik_synced_manifest.py:52`). The new verb is inert in a repo with no `merge=ledger` attribute, and nothing else in the file changes.
- Tests run through `/opt/fabrik/scripts/capped_run.sh -- /opt/fabrik/.venv/bin/python -m pytest …` (D-935), never bare.
- Commit with explicit pathspecs and Agent Provenance Trailers; never `--amend`; push after each phase.
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
1. Add `_merge_ledger(base, ours, theirs, path)` beside `_merge3` (`scripts/merge_request.py:998-1012`), taken from `proto/verb.py`:
   - read the three files as bytes through `_decode` (`:728-733`);
   - run `_merge3`;
   - for `DECISIONS`, refuse when `_dup_ids(result) - (_dup_ids(ours) | _dup_ids(theirs))` is non-empty. That is the spec's "not already twice in ours" with theirs added, which is stricter and still never fires on a duplicate already present on one side;
   - write through `tempfile.mkstemp(dir=<dir of ours>, prefix=".merge-ledger-")` and `os.replace`, unlinking the temp on any exception.
2. Register the subparser after `sync-runner`'s (`:3775-3777`) and dispatch it before the verb table, as `sync-runner` is (`:3779-3790`). On any `Exception`, print `merge_request: REFUSED — <reason>` to stderr and return 1; on success return 0.
3. Add `tests/test_merge_ledger_driver.py` from `proto/test_merge_ledger_driver.py`, dropping its last placeholder test. It holds one test per spec § Validation leg: the control conflicts, the driver merges clean, DECISIONS order in both directions, duplicate-id refusal, refusal with rc 1 and `%A` untouched, bootstrap via a pre-verb script, and no regression with the driver's own exit logged.
4. Watch each test RED before the verb exists (the verb's absence makes every driver leg fall back to markers or `invalid choice`), then GREEN after step 2.
5. Gate: `capped_run.sh -- .venv/bin/python -m pytest tests/test_merge_ledger_driver.py tests/test_merge_request_merge.py -q`, then `ruff check` and `mypy` on `scripts/merge_request.py`.

**Behavior Contract (Phase A):**
- Concurrent insertions in CHANGELOG and DECISIONS merge clean through git with the driver (red without it).
- DECISIONS puts the higher D-id first whichever side is ours.
- An edit of a landed row returns rc 1 with ours byte-identical and no temp file left behind.
- A duplicate D-id refuses, and git leaves markers with both rows.
- A tree whose `merge_request.py` predates the verb falls back to markers, with `invalid choice` on stderr.
- A merge that is clean without the driver stays clean, and the driver itself exited 0.

## Phase B — registration, attributes, docs

Appetite: 30

**Consumes:** Phase A's verb.

**Steps** (sequential):
1. `scripts/install_post_commit_hook.sh`:
   - add `LEDGER_DRIVER='python3 scripts/merge_request.py merge-ledger %O %A %B %P || git merge-file --marker-size %L -L ours -L base -L theirs %A %O %B'` and two `set_config` calls beside `:86-87`;
   - make the `set_config` failure message (`:84`) name the key it failed on instead of "the work-item merge driver";
   - widen the mirror regex at `:98` to `merge=(workitem|ledger)`;
   - keep `BEGIN_MARK`/`END_MARK` (`:94-95`) byte-identical.
2. `.gitattributes`: add five root-anchored lines, `/CHANGELOG.md merge=ledger`, `/docs/DECISIONS.md merge=ledger`, `/INDEX.md merge=ledger`, `/docs/STRATEGIC_BACKLOG.md merge=ledger` and `/docs/LESSONS_LEARNT.md merge=ledger`, under a comment naming W-53360407 and the spec.
3. Docs:
   - `docs/reference/multi-agent-operating-model.md` § Ledgers and ids across branches (`:162-166`): correct the "always conflict at merge" sentence and add the driver's paragraph;
   - `docs/workstation/hooks-index.md`'s installer row: add the second driver.
4. Run the installer once in this worktree, then check that `git config merge.ledger.driver` prints the string and `git check-attr merge CHANGELOG.md` prints `ledger`. Run the existing installer tests named in its `AFTER-EDIT` header (`tests/enforcement/test_governance_sync_postcommit.py`, `tests/test_merge_sync.py`) under `capped_run.sh`.

**Behavior Contract (Phase B):**
- The installer registers `merge.ledger.*` and mirrors the ledger lines into `info/attributes` without orphaning the work-item block.
- A nested `sub/CHANGELOG.md` gets no `merge=ledger`.

## Phase C — Finish

Appetite: 45

**Steps** (sequential):
1. The ONE heavy review (this command's `Profile: small` D7 floor): `/fabrik-review` over the whole-plan diff, one receipt.
2. The replay grader: run `proto/d5.py <clone> /opt/fabrik "2026-10-17 00:00" "2026-10-31 00:00"` on a fresh `git clone --shared` with the built driver registered. Record its output in the receipt. Expected `driver-clears` ≥ 58 and no `dup` line.
3. Ledgers:
   - `CHANGELOG.md`: one `### Added — ledger merge driver (2026-10-31)` entry;
   - `docs/LESSONS_LEARNT.md`: the replica-vs-real-git lesson;
   - `INDEX.md`: the new test file and this plan;
   - no new D-row, because D-1386 holds the decision.
4. `final_gate.py --check --json` green, then push.
5. `python3 scripts/merge_request.py request --review <the /fabrik-review receipt> --item W-53360407`, sending the printed `SendMessage` lines (the coordinator's session holds SendMessage, so mail it if held), and report to the coordinator.

## Evidence

- The spec's anchors were re-verified by the review's seats at `51716046f`/`5bb3e7a34` (receipt Passes 1-8).
- The prototype ran in a scratch repo on 2026-10-31: insertions clean with D-1391 first, the duplicate refused, the landed-row edit refused, no temp left.

## Self-audit

- Code files 3, code lines about 60: `Profile: small` holds.
- Every spec § Validation leg maps to a Phase A test, except the Counter B pass (I4, W-6614b62e).
