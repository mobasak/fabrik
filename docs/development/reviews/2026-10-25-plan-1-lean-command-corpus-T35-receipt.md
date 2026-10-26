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
