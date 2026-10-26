# T39 receipt — lean rewrite of /fabrik-repo-review (light form, D-1240)

- Start commit: `851b4b365` (branch base origin/kaizen-lean-u01)
- Own text, words: file 2900 -> 2706 (93%); unit words (baseline keys) 2592 -> 2399 (92%)
- Floor: not reached — 93% of the baseline against the 50% target. The text is rule-dense: about 570 words sit in ban clauses that stay verbatim (D-1240), every backticked token, path and number of a covered clause stays in one phrase, and the Phase 1 launch sentence, the failure-class bullets and the Phase 4 exit conditions are operative rules, three parts of them pinned by kept tests (test_review_loop_workflow, test_review_queue_pass, test_assemble_dispatch_step). Narrative removed: the SCAFFOLD_TYPES enumeration, dates and measured counts, the D-182 ruling history and the batch-clock rationale (14 baseline units reworded, 15 clauses labelled narrative). About 270 further words are the two POOL OFF block comments, left in place because the corpus keeps its POOL OFF comments (D-343; the frozen contract file `docs/reference/subagent-pool-contract.md` is the restore source) — deleting them is a hub decision. Floor D-row owed through Deltas: 68 live ledger entries.
- Entries: 68 total = 55 generated unchanged (`generate_unchanged`) + 13 hand-written (reworded/fence); reworded/total = 13/68
- Hand entries by class (recorded as `# class:` comments; the loader on this base has no `class` key): {'prose': 6, 'ban': 7}
- Vanished baseline lines: 14 of 76 — {'rule': 14}; labels are the author's ("author labels — audit owed"); the Sonnet + Haiku classification pair could not run in this clone
- Loader: `_ENTRY` lacks `class`/`clauses` on this base, so the class is a `# class:` comment on each hand entry and uncovered (narrative) clauses are `# clauses: {n: narrative}` comments on the vanished label; the hub converts them to keys when infra-3's loader lands
- Coverage was checked by a scratch tool outside the repo implementing D-1240 by hand: per baseline clause (split at `;`/`—`), ONE `text` phrase holds 100% of its anchors (backticked tokens, numbers, paths, ban words) and >=70% of its first 8 content stems; a ban clause is verbatim from its ban word to the end of its clause and the carrier holds the same ban token; no clause holding a ban word is labelled narrative. `commands/command_rules.py` and `tests/test_command_rules.py` are untouched.

## Reworded entries — clauses and how each is covered

| entry | class | baseline lines | clauses | covered by phrase | labelled narrative |
|---|---|---|---|---|---|
| r01 | prose | L1, L2 | 4 | 4 | 0 |
| r02 | prose | L11, L12 | 3 | 3 | 0 |
| r03 | ban | L15 | 2 | 2 | 0 |
| r04 | prose | L21 | 6 | 6 | 0 |
| r05 | ban | L24, L64 | 10 | 10 | 0 |
| r06 | prose | L74 | 1 | 1 | 0 |
| r07 | ban | L45 | 4 | 4 | 0 |
| r08 | ban | L24, L53 | 7 | 7 | 0 |
| r09 | ban | L56 | 3 | 3 | 0 |
| r10 | prose | L64 | 1 | 1 | 0 |
| r11 | prose | L62, L63 | 2 | 2 | 0 |
| r12 | ban | L64 | 3 | 3 | 0 |
| r13 | ban | L56, L74 | 12 | 12 | 0 |

## Clauses labelled narrative (14) — no ban word in any

- L1 clause(s) [2, 3, 4]: > ⚠️ POOL OFF — D-181 (operator, 2026-09-07). The OpenRouter subagent pool is OFF by operator ruling (D-181; m
- L11 clause(s) [2]: Read `project.yaml::type` (one of the real `SCAFFOLD_TYPES` — the live registry is `scaffold.py::SCAFFOLD_TYPE
- L12 clause(s) [1]: `office-extension`: python-api / python-api-gpu / saas-skeleton / node-api / file-api / file-worker / wordpres
- L15 clause(s) [3]: Partition the codebase into INDEPENDENT review units (by subsystem/dir so two units never share files) — fine-
- L21 clause(s) [3]: The repo is cut into DISJOINT slices by file and every file is read once (D-207): two cheap finders per slice 
- L24 clause(s) [10]: Batch the slices by risk tier, highest-blast-radius first — a slice batch IS a round: `dispatch_headroom.py --
- L45 clause(s) [4]: A CONFIRMED SECURITY finding budgeted OUT of this run is a risk-acceptance decision, never silent triage — sur
- L53 clause(s) [4]: CONSTRAINTS: if this is a SHARED multi-lane worktree, do NOT edit other lanes' files; do NOT touch deps files 
- L56 clause(s) [5]: Re-run `final_gate.py` after each fix cluster (`--lean` for fast mid-loop self-review only · `--json` the FULL
- L64 clause(s) [6]: `check_review_coverage.py` grades the review artifact, and the run record's round entries (`command_run.py rou
- L74 clause(s) [7, 12]: The coverage ledger; per-unit findings with verdicts; the fixes with their regression tests; a rule-pack & (wh

## Vanished labels

```
L1:
  rule:
  - r01
L11:
  rule:
  - r02
L12:
  rule:
  - r02
L15:
  rule:
  - r03
L2:
  rule:
  - r01
L21:
  rule:
  - r04
L24:
  rule:
  - r05
  - r08
L45:
  rule:
  - r07
L53:
  rule:
  - r08
L56:
  rule:
  - r09
  - r13
L62:
  rule:
  - r11
L63:
  rule:
  - r11
L64:
  rule:
  - r05
  - r10
  - r12
L74:
  rule:
  - r06
  - r13
```

## Pins deleted

- `tests/test_run_scratch_brief_wording.py::test_the_review_loops_d8_names_put_their_pins_under_scratch` — only the trailing block that pinned this command's batch launch (the `batch = _section(... "a slice batch IS a round", "contract and fallback")` lookup and its two `scratch_dir` / `pins_dir` presence asserts, plus the W-27a0dc32 comment above them). The cross-file asserts in that test (D8's command list, the includers set, the other loops' `loop` clause) stay. No other line changed.
- T38's pin deletion in the same file is in its own commit.

## Failure sets (reader-test run, spine § Global Constraints)

- Start commit 851b4b365: 30 failed, 1751 passed, 9 skipped. End of T39: 30 failed, 1750 passed, 9 skipped — the FAILED set is identical to the start set (the reds pre-exist: the clone lacks box services).
- `python3 -m pytest tests/test_command_rules.py -rP`: 32 passed, 3 skipped; prints `LEDGER fabrik-repo-review.yaml: 68 entries`.
- `python3 commands/assemble_commands.py --check`: exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING`; no LOSS, no ceiling failure (REPORT: fabrik-repo-review shrank to 24574 words, ceiling 25512 — the coordinator ratchets at merge).

## LEFT FOR THE HUB

- `commands/_size_ceiling.json` ratchet for `fabrik-repo-review` (not touched, per the brief).
- The Sonnet + Haiku classification audit of the 14 vanished labels and the author-blind old-vs-new read of the 13 hand entries.
- The floor D-row, the decision on deleting the two POOL OFF block comments (about 270 words, restore source `docs/reference/subagent-pool-contract.md`), and the conversion of the `# class:` / `# clauses:` comments to keys once infra-3's loader lands.
- CHANGELOG, INDEX rows for the new `commands/_rules/` files, D-rows (hub writes at merge).
