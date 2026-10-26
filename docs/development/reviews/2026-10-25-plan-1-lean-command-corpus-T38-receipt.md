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
