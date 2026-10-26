# T35 receipt — /fabrik-deploy (light form, D-1236 pilot)

Start commit (baseline, frozen copy): `8ac547a6139658fed456bb3f3f069596856d6316` (origin/kaizen-lean-u01). Branch: `claude/lean-t35`.

## Measures

| measure | value |
|---|---|
| own-text words (`command_rules.own_text`), before → after | 4898 → 2781 (56.8%; 43.2% cut) |
| target | ≤ 50% (2449) — **not met; floor named below** |
| baseline units | 114 |
| ledger entries total | 55 (10 generated unchanged `u-L*`, 45 hand-written) |
| entries reworded / total | 45 / 55 |
| hand-written entries by class | ban 20 · grammar 12 · prose 11 · behavioural 2 |
| vanished units | 94: 91 `rule`, 1 `duplicate-of` (L11 → `dp-gate-status`), 2 `narrative` (L66 backstop sentence, L89 Phase 3 heading) |
| pins deleted | none — every phrase test pinning this file is cross-file (`test_check_command_corpus.py`, `test_command_run.py`) or a kept behavioural test (`test_gate_decision_blocks.py`, `test_final_gate_stop_deferral.py`); all stay and all pass |

Classes are recorded as `# class:` YAML comments: the loader (`_ENTRY` in `commands/command_rules.py`) accepts no `class:` or `clauses:` key and the tooling file is out of bounds. Clause-level coverage of each `baseline` is by author judgment; clauses I dropped are explanatory reasons, incident/narrative parentheticals, or restatements of a kept rule. Backticked remedy strings and tokens in operative clauses all survive verbatim (a few over-cuts were restored after the first draft).

## Floor

2781 words. About 230 words are fenced grammar that must stay verbatim (two DECISION blocks, the FINAL OUTPUT block, the `ssh … pause.owner … touch` open command), and ~45 distinct refusal/`BLOCKED:` strings plus the status-route table are refusal clauses. Cutting below this needs a rule change (for example moving the healer-window protocol to a shared fragment), which T35 may not do.

## Gates

- `python3 -m pytest -q tests/test_command_rules.py -rP` → 32 passed, 3 skipped; `LEDGER fabrik-deploy.yaml: 55 entries · vanished {'duplicate-of': 1, 'narrative': 2, 'rule': 91}`; zero LOSS lines.
- `python3 commands/assemble_commands.py --check` → exit 1; every DRIFT line reads `DIFFERS from what this tree renders` or `MISSING`; no LOSS (4), no ceiling (5). `REPORT fabrik-deploy: shrank to 10514 words, ceiling 13010`.
- Reader-test run (spine § Global Constraints) over 38 test files: **52 failed / 2104 passed / 10 skipped at the start commit and the same 52 at the end** (set diff empty). All 52 are environment reds of this clone (`psycopg2`, `psutil`, `httpx`, `pydantic` missing, no `/opt/fabrik`, no systemd, `~/.claude/agents` absent); none names `fabrik-deploy`.

## Vanished labels

Author labels — audit owed. The Sonnet + Haiku author-blind classification could not run in this clone.

## LEFT FOR THE HUB

- The author-blind audit pair reading every reworded entry old against new, and the Sonnet + Haiku classification of the 94 vanished labels.
- The review wave over `commands/_sources/fabrik-deploy.md` and `commands/_rules/fabrik-deploy.yaml`.
- The ceiling ratchet for `commands/_size_ceiling.json` (not edited here).
- `CHANGELOG.md`, the `INDEX.md` rows for the two new `commands/_rules/fabrik-deploy.*` files and any D-row.
- Loader support for `class:` / `clauses:` so the class tags stop being comments.

## Fix round 1

Two author-blind audits (Sonnet: 30 findings; Haiku: 59) read the cut against `lean-baseline-2026-10-25`. Each finding was checked against the before-text.

- **Confirmed and fixed (all that named a real loss or weakening):** the ban clauses cut short (`dp-end-halted`, `dp-gate-dispatch`, `dp-win-conservative`, `dp-total-rule`, `dp-env-background`, `dp-win-expiry`, `dp-halt-protocol`, `dp-window-closed`), the dropped anchors (`fabrik apply`, `git pull`, `git log`, `OPERATOR-GATE`, `EXIT`/`stat`, `vps-autoheal.sh`, `adm`/`systemd-journal`, `/run` tmpfs, `deployer_ssh.py::_BUILD_TIMEOUT`, `✅ BATTERY`, `/fabrik-release`, 2026-09-03), the lost qualifiers ("full halt protocol", "LATEST run", "of any stem", "(total)", "ending there IS success", "closes it last"), the battery check list, the enumerated "ANY other outcome" cases, the three permitted removal sites, the Phase 0 OUR-stem close fallback, the no-resume rule, the `description:` trigger phrases. Four wrong `vanished:` labels were corrected: L11 is now `rule: dp-end-halted`, where the close-out-only successor and its "never re-runs the runbook" ban are carried again; L66 is now `rule: dp-win-close`; the rest (L9, L17, L36, L40, L51, L54, L62, L67, L77, L88, L104) now point at entries that really carry the rule.
- **Refuted:** finding 26/Haiku 59 reads the frontmatter as unlogged. It is outside the baseline units, so no ledger entry is owed, but the dropped trigger phrases were restored anyway. Haiku 28 (`dp-total-rule` "(EXECUTED)") and 41 (`dp-opgate` "that" vs "is what") were real wording drifts and are restored verbatim. Stem-count disputes on rewordings that now carry the full original clause are moot.
- **Invented rules:** none (both audits).
- **Gates:** `tests/test_command_rules.py` 32 passed, 3 skipped; `assemble_commands.py --check` exit 1 with only DIFFERS/MISSING drift, no LOSS.
- **Words (own text):** baseline 4898 → first cut 2781 → after fix 3950.

## Re-ledger round (canonical loader, W-96f36043)

- Base: origin/claude/lean-t35-fix; first commit is the loader swap (`commands/command_rules.py`, `tests/test_command_rules.py`, `docs/reference/command-corpus-check.md` from origin/master, W-9cd8653d merged), never edited after.
- Own-text words (`len(own_text.split())`, front matter included): baseline 4898 -> fix round 3950 -> now 4699 (95% of baseline). **Target 50% not met; the count went UP from the fix round by 749**: under the canonical loader every ban clause must stand word for word from its ban word to the end of its `;`/`—` clause (parentheticals, history and examples inside it included), and each clause needs ONE phrase holding all its anchors, so the fix round's rewordings (which the old loader accepted) had to be restored.
- Own-ledger LOSS: 46 -> 0 (`assemble_commands.py --check`; the remaining LOSS lines are all `_shared/*.yaml`, the shared-file unit's).
- Ledger rebuilt from the baseline: 106 entries (one per baseline rule unit), 102 reworded / 4 kept whole, real `class:` and `clauses:` keys, 0 `clauses:` label(s), every `text` phrase the smallest window the D-1240 reading covers (all anchors, >=70% of the first 8 stems, the ban word's next word, the whole ban span). Vanished labels: 50 lines.
- Floor (why not 50%): the protected windows alone are about 70% of the live text; they are forced by (a) ban spans verbatim to clause end, (b) clauses whose 4-9 backticked/numeric anchors must sit in ONE phrase, (c) history inside ban clauses that D-1238 point 1 forbids labelling narrative. I measured the pure-telegraphic floor (anchors + 6 stems + ban spans, nothing else) at 47-55% of the unit words; reaching it would leave text that no longer reads as instructions, so I stopped at the readable floor.
- Self-audit: one fresh Sonnet auditor read baseline, rewrite and ledger; its findings (LOST/WEAKER/WRONG-LABEL) were fixed in the rewrite (dropped qualifiers restored) and the ledger regenerated. Residual: see COUNTS in the hub summary; hub author-blind audit still owed.
- LEFT FOR THE HUB: policy call on D-1238 point 1 / D-1240 (they force history retention and make 50% unreachable for ban-dense commands); ratchet `_size_ceiling.json`; CHANGELOG/INDEX rows.

## Fix round 2 (hub audit)

Audit 1 (Sonnet, 19 findings) and Audit 2 (Haiku, none) were each checked against the before-text.

- **Confirmed and fixed (19 of 19):**
  - 1 and 2 (`cu-L44`): `pause` present restored in the outcome-3 bullet; the ledger phrase now points at that bullet, not at Phase 1 text.
  - 3 (`cu-L32`): "Store surfaces: the plan's build SHA is on the service repo's remote)" restored; the ledger phrase for `cu-L32` and the tail of `cu-L31` were repointed.
  - 4 (`cu-L64`): "still carries THIS plan's stem before removing" restored.
  - 5 (`cu-L67`): "before the sensitive work resumes" restored.
  - 6 (`cu-L102`): "of either file" restored.
  - 7 (`cu-L102`): the invented "never unwind" was removed from the L102 clause. L104 keeps its own "never unwind", and the `cu-L104` phrase now carries it itself.
  - 8 (`cu-L61`): "must show" back to "shows".
  - 9 (`cu-L50`): "runs the full halt protocol".
  - 10 (`cu-L75`): "(any surface)" and "the plan's battery FIRST as authored for the surface" restored.
  - 11 (`cu-L39`): "the triad writes ownership NEXT TO it" restored.
  - 12 (`cu-L52`): "an EVIDENCE RECORD for the review's re-entry audit" restored.
  - 13 (`cu-L27`): "you read during the deploy" restored.
  - 14 (`cu-L83`): "three attempts total".
  - 15 (`cu-L91`): "named rollback/retry path".
  - 16 (`cu-L48`/`cu-L47`): "Any pre-flight failure" and "the plan's own pre-flight guard steps" restored.
  - 17 (`cu-L8`): "the battery (the exit gate)", "maintenance window" and "the literal `Status: EXECUTED <date>`" restored.
  - 18 (`cu-L97`): the Phase 4 deferred-shape sentence is back in baseline order ("never repeat it; its content is defined per the convention … and proceed to Phase 5, the completion stamp recording …"), with the L98 in-session sentence after it.
  - 19 (`cu-L26`): the ledger phrase is now "Wrong repo → stop and say so."
- **Refuted:** none.
- **Words (own text):** baseline 4898 → re-ledger 4699 → now about 4755. This is an estimate: the rendered total moved 12432 → 12488 (+56). I could not run the own-text measure in this session (only the listed gate commands were allowed). Still far above the 50% target for the reasons in the re-ledger section, so no per-file floor table beyond the one above.
- **Gates:** `tests/test_command_rules.py` reports no `fabrik-deploy.yaml` LOSS (the one failing assertion lists only `_shared/*` ledgers, the same set as before the edits). Passing: the `test_review_queue_pass` group (141 tests). The `test_final_gate_stop_deferral` group was still running when this was written. `--check` exit 4; its output was truncated, so I could not confirm the deploy lines individually.
- **Fresh self-audit: NOT run.** No subagent can be dispatched in this lane. I did a line-by-line pass of every edit against the baseline text instead; it is not a fresh reader, so no zero-counts claim rests on it. The hub's author-blind audit pair covers that.
- Fresh passes run: 0.
- COUNTS: not claimed (no fresh pass). Own pass: edits read 19 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0, author re-check only.
