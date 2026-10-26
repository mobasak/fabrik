OWN TEXT: 4330 -> 3730 (86%)

# T38 receipt — lean rewrite of /fabrik-deploy-plan-review (light form, D-1240)

- Start commit: `851b4b365` (branch base origin/kaizen-lean-u01)
- Own text, words: file 4330 -> 3619 (83%); unit words (baseline keys) 4194 -> 3483 (83%)
- Floor: not reached — 83% of the baseline against the 50% target. The text is rule-dense: about 530 words sit in ban clauses that stay verbatim from the ban word to the clause end (D-1240); every backticked token, path and number of a covered clause stays in one phrase; the 10-row class checklist, the Phase 0 status guard, the Phase 3 gate sequence and the fenced Output and DECISION blocks are operative rules (the DECISION fence and the review-loop launch sentence are pinned by kept tests). What went was narrative: 36 baseline units were reworded or dropped (34 re-carried by a reworded entry, 2 labelled narrative) plus 40-odd clauses labelled narrative. Floor D-row owed through Deltas: 83 live ledger entries; going lower means cutting a clause that holds anchors or a ban word, which is a rule change.
- Entries: 83 total = 45 generated unchanged (`generate_unchanged`) + 38 hand-written (reworded/fence); reworded/total = 38/83
- Hand entries by class (recorded as `# class:` comments; the loader on this base has no `class` key): {'prose': 16, 'ban': 21, 'grammar': 1}
- Vanished baseline lines: 36 of 89 — {'rule': 34, 'narrative': 2}; labels are the author's ("author labels — audit owed"); the Sonnet + Haiku classification pair could not run in this clone
- Loader: `_ENTRY` lacks `class`/`clauses` on this base, so the class is a `# class:` comment on each hand entry and uncovered (narrative) clauses are `# clauses: {n: narrative}` comments on the vanished label; the hub converts them to keys when infra-3's loader lands
- Coverage was checked by a scratch tool outside the repo implementing D-1240 by hand: per baseline clause (split at `;`/`—`), ONE `text` phrase holds 100% of its anchors (backticked tokens, numbers, paths, ban words) and >=70% of its first 8 content stems; a ban clause is verbatim from its ban word to the end of its clause and the carrier holds the same ban token; no clause holding a ban word is labelled narrative. `commands/command_rules.py` and `tests/test_command_rules.py` are untouched.

## Reworded entries — clauses and how each is covered

| entry | class | baseline lines | clauses | covered by phrase | labelled narrative |
|---|---|---|---|---|---|
| r01 | prose | L1, L2 | 4 | 4 | 0 |
| r02 | ban | L5 | 2 | 2 | 0 |
| r03 | ban | L29 | 1 | 1 | 0 |
| r04 | prose | L12 | 2 | 2 | 0 |
| r05 | prose | L13 | 2 | 2 | 0 |
| r06 | ban | L17, L70 | 3 | 3 | 0 |
| r07 | prose | L17 | 1 | 1 | 0 |
| r08 | prose | L18 | 2 | 2 | 0 |
| r09 | ban | L20 | 3 | 3 | 0 |
| r10 | prose | L17, L23 | 2 | 2 | 0 |
| r11 | ban | L24 | 3 | 3 | 0 |
| r12 | ban | L25 | 3 | 3 | 0 |
| r13 | ban | L26 | 1 | 1 | 0 |
| r14 | ban | L29 | 10 | 10 | 0 |
| r15 | ban | L20 | 1 | 1 | 0 |
| r16 | prose | L31 | 2 | 2 | 0 |
| r17 | ban | L33 | 1 | 1 | 0 |
| r18 | prose | L34 | 1 | 1 | 0 |
| r19 | ban | L35 | 1 | 1 | 0 |
| r20 | ban | L35, L36 | 3 | 3 | 0 |
| r21 | ban | L38 | 3 | 3 | 0 |
| r22 | prose | L17 | 1 | 1 | 0 |
| r23 | ban | L50 | 15 | 15 | 0 |
| r24 | ban | L51 | 14 | 14 | 0 |
| r25 | prose | L54 | 2 | 2 | 0 |
| r26 | prose | L56 | 1 | 1 | 0 |
| r27 | ban | L57 | 3 | 3 | 0 |
| r28 | ban | L59 | 6 | 6 | 0 |
| r29 | ban | L70 | 1 | 1 | 0 |
| r30 | prose | L71 | 2 | 2 | 0 |
| r31 | prose | L72 | 2 | 2 | 0 |
| r32 | ban | L74, L77 | 6 | 6 | 0 |
| r33 | prose | L76 | 1 | 1 | 0 |
| r34 | prose | L77 | 3 | 3 | 0 |
| r35 | ban | L79 | 1 | 1 | 0 |
| r36 | prose | L80 | 1 | 1 | 0 |
| r37 | ban | L82 | 13 | 13 | 0 |
| f-decision | grammar | (fence entry, unchanged) | 0 | 0 | 0 |

## Clauses labelled narrative (48) — no ban word in any

- L1 clause(s) [2, 3, 4]: > ⚠️ POOL OFF — D-181 (operator, 2026-09-07). The OpenRouter subagent pool is OFF by operator ruling (D-181; m
- L5 clause(s) [2]: Dispatch step (D-191): run `python3 /opt/fabrik/scripts/sysadmin/dispatch_headroom.py --units <N> [--heavy] [-
- L7 clause(s) [1, 2, 3, 4]: This command exists because a deploy plan's characteristic defects — a set placeholder silently defeating a co
- L12 clause(s) [2]: Same split as `/fabrik-deploy-plan`: VPS surfaces → hub-side (`/opt/fabrik`) — the spec, the fleet SSH path fo
- L17 clause(s) [5, 6]: Status guard — this command's PRODUCT is the `DRAFT → CONVERGED` flip. (Status-literal convention, document-wi
- L20 clause(s) [3]: Otherwise: inputs changed (the spec, compose, or code moved under it — it is `DRAFT` in fact), or carrying a `
- L23 clause(s) [2]: Every status flip-back this guard performs commits IMMEDIATELY (explicit pathspec, the `deploy-plan-review` ma
- L26 clause(s) [2]: Status absent/unrecognized → refuse: not a deploy plan — nothing here to converge (route to `/fabrik-deploy-pl
- L29 clause(s) [2, 7]: RE-ENTRY AUDIT (the BLOCKED case's extra duty — the ledger is evidence, not a resume protocol): read the ledge
- L33 clause(s) [2, 3, 4]: And a MONOLITH deploy plan flipping CONVERGED must itself carry `## Coverage Checklist` + an embedded `review_
- L34 clause(s) [2]: Verify all of it BEFORE the flip — a missing section or an under-cited phase is a finding to fix, not a style 
- L38 clause(s) [2]: Untrusted input: every artifact you re-read to ground a claim — compose files, fetched vendor pages, store lis
- L50 clause(s) [5, 6]: | 4 | Runbook ordering + timing | every step verifiable + rollbackable; stable `S`-prefixed step ids present (
- L51 clause(s) [2, 6, 7, 8, 13, 18, 19]: | 5 | Healing / rollout interactions | VPS: autoheal pause brackets every long-unhealthy window as labeled `wi
- L54 clause(s) [2, 3]: | 9 | COLD START | the plan NAMES every first-boot init the service needs (DB schema/module init, first-run mi
- L57 clause(s) [3]: Rubric injection (corpus review-time contract): at the start of Phase 1 run `python scripts/review_rubric.py -
- L70 clause(s) [3]: Write the literal `Status: CONVERGED` (arrows describe transitions; the FILE carries only the target literal —
- L71 clause(s) [2]: The flip is the LAST content act — a plan edited after its flip is `DRAFT` again in fact, whatever the header 
- L72 clause(s) [2, 3, 5, 6]: The flip is a Status flip — mint its `docs/DECISIONS.md` row in the SAME flip commit (the ledger duty's trigge
- L74 clause(s) [4, 5]: This is an EDIT-CONVERGENCE review artifact — `check_convergence.py`'s review branch covers it (`check_review_
- L76 clause(s) [2]: the header line + a `## Phase verdicts` section — one verdict line per plan Phase (the per-phase adjudication 
- L77 clause(s) [5]: the class-verdict table — row tokens CLEAN / FIXED (a class whose finding was fixed shows FIXED), every row ca
- L79 clause(s) [1]: the Pass Ledger verbatim, the final round reading `found: 0, fixed: 0` (the quiet-pass marker the later `EXECU
- L80 clause(s) [2]: a fenced `python scripts/final_gate.py --check --json` output showing `"status": "success"` (the step-3 pre-ar
- L82 clause(s) [2, 3]: Two gate runs break the bootstrap circularity — the anatomy is proven, not asserted: (a) stage the flipped PLA
- L83 clause(s) [1]: An uncommitted flip is what the next pre-commit stash cycle silently reverts

## Vanished labels

```
L1:
  rule:
  - r01
L12:
  rule:
  - r04
L13:
  rule:
  - r05
L17:
  rule:
  - r06
  - r07
  - r10
  - r22
L18:
  rule:
  - r08
L2:
  rule:
  - r01
L20:
  rule:
  - r09
  - r15
L23:
  rule:
  - r10
L24:
  rule:
  - r11
L25:
  rule:
  - r12
L26:
  rule:
  - r13
L29:
  rule:
  - r03
  - r14
L31:
  rule:
  - r16
L33:
  rule:
  - r17
L34:
  rule:
  - r18
L35:
  rule:
  - r19
  - r20
L36:
  rule:
  - r20
L38:
  rule:
  - r21
L5:
  rule:
  - r02
L50:
  rule:
  - r23
L51:
  rule:
  - r24
L54:
  rule:
  - r25
L56:
  rule:
  - r26
L57:
  rule:
  - r27
L59:
  rule:
  - r28
L7: narrative
L70:
  rule:
  - r06
  - r29
L71:
  rule:
  - r30
L72:
  rule:
  - r31
L74:
  rule:
  - r32
L76:
  rule:
  - r33
L77:
  rule:
  - r32
  - r34
L79:
  rule:
  - r35
L80:
  rule:
  - r36
L82:
  rule:
  - r37
L83: narrative
```

## Pins deleted

- `tests/test_run_scratch_brief_wording.py::test_deploy_plan_review_names_scratch_dir_and_the_pins_root` — a plain string-in-file presence pin on this command's text, whole function removed; its two phrases (the `scratch_dir` wording and the `pins_dir` root) are text carriers of entries `r*` in the ledger. No other line of the file changed.

## Failure sets (reader-test run, spine § Global Constraints; 33 test files = stem readers of both T38/T39 sources + corpus-glob tests)

- Start commit 851b4b365 (detached worktree): 30 failed, 1751 passed, 9 skipped.
- End of T38: 30 failed, 1750 passed, 9 skipped — the failure set is IDENTICAL (diff of the FAILED lines empty); the one passed test fewer is the deleted pin. The reds pre-exist (the clone lacks box services: test_generate_capability_index, test_conftest_isolation, test_review_queue_pass::test_a_cwd_rooted_tool_runs_after_an_os_chdir, ...).
- `python3 -m pytest tests/test_command_rules.py -rP`: 32 passed, 3 skipped; prints `LEDGER fabrik-deploy-plan-review.yaml: 83 entries`.
- `python3 commands/assemble_commands.py --check`: exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING`; no LOSS, no ceiling failure (REPORT: fabrik-deploy-plan-review shrank to 20471 words, ceiling 21818 — the coordinator ratchets at merge).

## LEFT FOR THE HUB

- `commands/_size_ceiling.json` ratchet for `fabrik-deploy-plan-review` (not touched, per the brief).
- The Sonnet + Haiku classification audit of the 36 vanished labels and the author-blind old-vs-new read of the 38 hand entries.
- The floor D-row (83% reached against the 50% target) and the conversion of the `# class:` / `# clauses:` comments to keys once infra-3's loader lands.
- CHANGELOG, INDEX rows for the new `commands/_rules/` files, D-rows (hub writes at merge).

## Re-ledger round (API-key write lane, W-96f36043; D-1245 canonical loader, master 545817887)

Branch `claude/lean-t38-rl` = `claude/lean-t38-t39-rlbase` + the loader-swap commit. Edited only this ticket's Touches (source, ledger; the baseline and `commands/_size_ceiling.json` untouched; the presence pin in `tests/test_run_scratch_brief_wording.py` was already deleted by the fix round, nothing left there) plus this receipt.

- Own text, words (source file, the `wc` basis the fix receipt uses): baseline 4330 -> fix round 3619 (83%) -> now ~3730 (86%). The fix round was under the old loader and cut by dropping text inside ban clauses; under the canonical loader that text is verbatim-bound, so it went back (~+110 words net after this round's cuts). The render word count, `--check` REPORT: 20471 -> 20582 (+111), so the file figure is 3619 + 111. Hand-estimated, no `wc` on this lane.
- LOSS, my ledger: 56 lines at the start (lint A 10, B 37, D 9) -> 0 after. `python3 commands/assemble_commands.py --check` prints only `_shared/*.yaml` LOSS lines (T01d's, outside Touches) plus the existing `fabrik-task.md` DIFFERS drift; no `fabrik-deploy-plan-review` or ceiling line.
- Entries: 80 total = 46 unchanged units (`u-L<n>`) + 33 reworded (`c<n>`) + 1 fence (`f-decision`); reworded/total = 33/80. Classes (loader summary): ban 36, grammar 1, prose 43. Every `# class:`/`# clauses:` comment is now a real `class:`/`clauses:` key. Vanished lines: 35 labels = 33 `rule: [id]` + 2 `narrative` (L7, L83).
- Clauses labelled `narrative` (all without a ban word, loader-checked): L1 c2 (the 2026-09-07 ruling story), L8 c2, L12 c2, L17 c3+c4 (lifecycle restating the BLOCKED/CONVERGED bullets), L23 c2, L28 c2, L38 c2 (example list), L51 c2, L54 c2 (tryton-crm incident), L55 c2, L77 c4. No `duplicate-of` label.
- What came out beyond the fix round: the leftover sentence "A deploy plan's characteristic defects are invisible to the author's own re-read" (a residue of narrative L7, not a baseline unit); L12/L13/L8/L23/L28/L38/L54/L55/L77 glosses; L9's `per-axis`; L43's gloss `(a step whose "verify" cannot fail …)` (row 8 and L58 carry the same check); L42's two examples; L20's `(the committed evidence …)`; row 8's two example lists; the L60 `chunk 6b`, `across a WSL shutdown` and `the breadth went to the OpenRouter pool`; L57's `that is what …` kept, its second half reworded to the same rule.
- What went back in (ban spans verbatim, D-1240): L17 (`only the target literal … regex.) The plan lifecycle it serves is simple by design`), L25 (unchanged baseline), L29 (clause 2, 5, 6 spans), L33 (the whole parenthetical), L35/L36 (unchanged), L44 (unchanged), row 4 (`never renumbered; list ordinals are not ids — the deploy ledger joins on them)`), row 5 (clause 3 from `only while` to `the close never writes`, the `simulate it` and `a fake sudo` parentheticals included), L70, L74 (from `must not opt itself in` to the end), L79 (`EXECUTED` token), L82 clause 2 and `(b)'s run`. Also restored operative actions the fix round had cut: L2 `same unit split, same author-blind rule`, L9 `record the answers and continue the loop in the same invocation`, L20 `and converge again` and `in the re-convergence commit`, L29 `the loop converges the other axes meanwhile, that step's amendment finalizing on the answer`, L60 `or nothing`.
- Anchors the loader found missing and the rewrite now holds: `decide/refute/merge` (L2), `incident/evidence` (L72), `EXECUTED` (L79), `D-186` (L5), `N/A-<surface>` (L34), step `1` (L82).

### Self-audit (line by line against the baseline file, the source and the ledger; no subagent on this lane)

Pass 1 found and fixed: 5 operative actions cut inside clauses the loader counts as covered (listed above); 1 invented sentence (the L7 residue); f-decision under `class: grammar` needed one whole-fence phrase (a `text` phrase there carries ` ⏎ ` joins); 3 anchors missing (above). Pass 2 re-read every `c` entry old against new and every `u-` unit against the source and found nothing more.

COUNTS: 80 entries read / 33 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels

Caveat the hub's author-blind audit should weigh: a handful of reworded clauses drop only words past the first 8 content stems (L9's parenthetical was restored, L43's gloss and row 8's examples were not); that is the loader's covered-clause reading (D-1240), and every dropped phrase is a gloss, example or a restatement carried by another unit.

### Floor — why this file cannot reach 50%

Target 2165 words (50% of 4330); now ~3730 (86%). By hand count the strict D-1240 floor, with every non-ban clause also cut to its anchors plus 6 of its first 8 stems, is about 2700 words (62%): the ban-clause spans alone are about 1450 words (34% of the baseline), the headings, the table header and the two fences about 320 more, and about 90 non-ban clauses at anchors-plus-6 about 900. Reaching even 62% means deleting distinct checks from operative lists (rows 1-3, 6-10 and the L32/L37/L41/L43 lists), which the loader accepts but which are rules a deploy plan is judged on; this round kept them. Live rule count: 80 ledger entries (36 ban-class).

| unit (baseline line) | ~words now | why it cannot shrink |
|---|---|---|
| POOL OFF + dispatch (L1-L5) | 175 | L3 is one ban clause whole; `c5` holds 4 command tokens, `SEATS:`, 191, 186 and `only the partition`; the `Dispatch step (D-191)` literal is what `assemble_commands.py` greps; `c1`/`c2` hold 8 backticked tokens and the `decide/refute/merge` path |
| L9 sanctioned endings | 75 | clause 2 is verbatim from the first `refusal` to `stop)`; anchors `/fabrik-deploy`, 0 and 2 |
| L10 chain line | 28 | pinned by `tests/test_check_command_corpus.py` (`You are at step 4 of the chain`) |
| L17 status guard | 62 | `only the target literal … simple by design` is one ban span (the baseline's parenthesis never closes, so the span runs to the clause end) |
| L19, L24, L25, L26, L27, L28 status bullets | 190 | each a ban clause; L25's two spans run to the clause end (`never got to unwind), write the literal … BLOCKED case`) |
| L29 re-entry audit | 220 | spans of clauses 2, 5, 6 (33, 22, 14 words) verbatim; clauses 3, 4, 7, 8, 9 at anchors-plus-6 |
| L32 gate-required shape | 80 | 11 backticked anchors and `1` in two clauses, whose first-8 stems include `name the RIGHT gate for each demand` |
| L33 monolith | 74 | the ban clause is one parenthesis, verbatim from `must` to its close |
| L35, L36 precondition trail | 64 | two ban clauses (`must embed … mandates`, `only record`, `must not survive`); anchor `2` |
| L44 class checklist | 45 | `never silently dropped; … row verdict):` verbatim |
| rows 1, 7 | 105 | `only from values …`, `never inlined`, `never assumed` clauses verbatim; the rest are path anchors |
| rows 2, 3, 6, 9, 10, 8 | 230 | each clause already at or near anchors-plus-6 once the glosses went; the remaining words are the per-surface checks (operative) |
| row 4 | 190 | `never renumbered; … joins on them)` verbatim; 9 non-ban clauses with 8 backticked anchors |
| row 5 | 520 | clause 3 (`only while …` to `the close never writes`) is one ban span of ~330 words because the baseline's first `(` never closes; clause 6 span 12 more; the rest are anchors |
| L59 fan-out | 105 | `never a token 1–2; D-191) with the plan …` verbatim; 9 anchors |
| L60 Opus + Workflow paragraph | 375 | clause 1 is a ~140-word span (`never the main checkout … the riskiest unit`); clause 5 a 30-word span; clause 4 holds 14 backticked tokens, 181 and 836; pinned by `tests/test_review_loop_workflow.py` (script path, `cannot load the script`, `pins_dir`/`pin_manifest`, `SCRATCH:` forms) |
| L61, L65, L69, L70, L78, L79 | 190 | ban clauses verbatim |
| L74 edit-convergence artifact | 130 | one parenthesis, verbatim from `must not opt itself in` (~110 words) |
| L82 two gate runs | 215 | span `must touch the PLAN … after)`; clauses (a)-(f) at anchors-plus-6 with 7 backticked tokens |
| Output fence + DECISION block + `Next command` | 245 | grammar fences and a kept test pin (`tests/test_gate_decision_blocks.py`, `tests/test_final_gate_stop_deferral.py`); the fence lines hold `only` twice, so a change needs a ban entry too |

### Gates (start -> end; the clone lacks box services, so the reds pre-exist)

1. `tests/test_command_rules.py -rP`: start 1 failed / 56 passed, end 1 failed / 56 passed (`test_generate_unchanged_ledgers_pass_on_the_live_corpus`, red on the `_shared` LOSS lines); the PASSES section prints `LEDGER fabrik-deploy-plan-review.yaml: 80 entries · classes {'ban': 36, 'grammar': 1, 'prose': 43} · vanished {'narrative': 2, 'rule': 33}`.
2. `--check`: exit 4 only from `_shared/*.yaml` LOSS lines (T01d); zero LOSS lines for this ledger.
3. flip-gate / agent-definition group: start 14 failed / 100 passed, end 14 failed / 100 passed, same set (`test_assemble_dispatch_step.py` ×13, `test_assemble_orch_retired.py::test_git_grep_for_retired_tokens_prints_nothing`).
4. worktree-guard / corpus group: 376 passed -> 376 passed.
5. measure / run group: 2 failed, 746 passed -> 2 failed, 746 passed (`test_command_measure.py::test_check_exit_order_loss_then_ceiling_then_drift`, `test_conftest_isolation.py::test_the_two_live_box_tests_pass_a_merge_check_on_a_drifted_box`).
6. firecrawl group: 237 passed -> 237 passed.
7. producing-fragments group (with `test_run_scratch_brief_wording.py`): 463 passed -> 463 passed.
8. spec-plan-lane group: 33 passed -> 33 passed.

## LEFT FOR THE HUB (re-ledger round)

- A floor D-row for this command (86% against the 50% target; strict floor ~62%, see above) through Deltas; `commands/_size_ceiling.json` ratchet at the text-measure merge.
- The author-blind old-vs-new audit of the 33 reworded entries and of the 35 vanished labels; the Sonnet + Haiku pair could not run on this lane.
- The `_shared/*.yaml` LOSS lines (T01d's unit) that keep gate 1's `test_generate_unchanged_ledgers_pass_on_the_live_corpus` and the `--check` exit at red/4.
- CHANGELOG, INDEX rows for the new `commands/_rules/` files, D-rows.
