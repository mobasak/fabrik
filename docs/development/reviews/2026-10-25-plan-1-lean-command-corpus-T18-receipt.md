# T18 receipt — /fabrik-catchup (light form, D-1236)

- Start commit: 8ac547a6139658fed456bb3f3f069596856d6316
- Own-text words: 2329 -> 1424 (61% of baseline; target 50% missed). Floor: three executable recipes (probe-1 parser one-liner, code-roots pipe, probe-7 grep) that kept tests run, the 7-probe list with their NEVER/report-only bans, the 7-row route table, the termination contract's gate/owner clauses and the output fence; every further cut deleted a ban or a recipe clause.
- Ledger: commands/_rules/fabrik-catchup.yaml, 49 entries total (5 generated unchanged + 44 hand-written, all 44 reworded). By class: ban 12, grammar 1, behavioural 3, prose 28 (classes recorded as `# class:` comments; the loader has no `class:` key yet).
- Vanished: 49 baseline lines labelled — 46 `rule: [ids]`, 3 narrative (L4, L24, L31). Author labels — audit owed (no Sonnet/Haiku seats in the clone).
- Pins deleted (tests/test_catchup_queue_pass.py, listed under `pins:`): termination_counts_a_mailed_item, phase_zero_runs_the_gate_first, probe_one_scopes_the_archived_rule, probe_two_derives_code_roots, phase_two_claims_items_in_the_store; plus output_line_counts_seven_probes (the output fence is unchanged, no ledger pin). Behavioural tests kept (probe-1, probe-7, code-roots recipes).
- Gates: tests/test_command_rules.py 32 passed, LEDGER line for fabrik-catchup.yaml, zero LOSS; assemble_commands.py --check exit 1 with only DIFFERS/MISSING drift.
- Reader-test failure set (37 files): start 53 failed / 2165 passed; end 53 failed / 2159 passed; identical set (comm -13 empty). The one catchup red (test_probe_one_reads_status_through_the_parser) is pre-existing (no /opt/fabrik/scripts in the clone).
- LEFT FOR THE HUB: author-blind audit of the 44 reworded entries and the vanished labels; ratchet commands/_size_ceiling.json at merge; CHANGELOG/INDEX rows; `class:` keys once the loader accepts them.
