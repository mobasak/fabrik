# T45 receipt — /fabrik-workflow-review (light form, D-1236)

- Start commit: 8ac547a6139658fed456bb3f3f069596856d6316 (origin/kaizen-lean-u01)
- Own text (`command_rules.own_text`): 1342 words -> 797 (59%). **Target 50% missed; floor named:** the rest is the Phase 0 table, the seven finder classes (each a distinct checked failure class), the ban clauses, and the paths/commands the rule test requires verbatim; further cuts would drop a live rule.
- Entries: 36 total = 12 generated unchanged (`generate_unchanged`) + 24 hand-written reworded entries (24/36 reworded). Hand entries by class: ban 6 · grammar 1 · prose 17 · behavioural 0 (class kept as `# class:` YAML comments).
- Pins deleted: none (no string-in-file presence pin on this command's text exists in the Touches tests; the skill-router description phrases are behavioural and the front matter is untouched).
- Vanished labels: 37 baseline lines vanished; 35 `rule: [ids]`, 2 `narrative` (L5, L7) — author labels, audit owed (no Sonnet/Haiku seats in the clone); no weaker-count available.
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped, LEDGER line printed for fabrik-workflow-review, zero LOSS. `assemble_commands.py --check` rc 1, only DIFFERS/MISSING drift.
- Reader tests (test_trigger_routing, test_producing_command_fragments, test_skill_router_hook, test_assemble_dispatch_step, test_final_gate_stop_hook): end commit 1 failed / 493 passed (`test_the_gate_reports_a_malformed_orphan_position_instead_of_crashing[a broken symlink]`); start-commit set: identical (same 1 failure, pre-existing: broken-symlink case; the set did not grow).
- LEFT FOR THE HUB: ceiling ratchet for `commands/_size_ceiling.json`; Sonnet+Haiku audit of the 35 rule labels and of the 24 reworded entries old-vs-new; CHANGELOG/INDEX rows for the two new `commands/_rules/` files.
