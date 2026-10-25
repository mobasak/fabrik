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
