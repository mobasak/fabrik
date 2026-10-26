# T45 receipt — /fabrik-workflow-review (light form, D-1236)

- Start commit: 8ac547a6139658fed456bb3f3f069596856d6316 (origin/kaizen-lean-u01)
- Own text (`command_rules.own_text`): 1342 words -> 797 (59%). **Target 50% missed; floor named:** the rest is the Phase 0 table, the seven finder classes (each a distinct checked failure class), the ban clauses, and the paths/commands the rule test requires verbatim; further cuts would drop a live rule.
- Entries: 36 total = 12 generated unchanged (`generate_unchanged`) + 24 hand-written reworded entries (24/36 reworded). Hand entries by class: ban 6 · grammar 1 · prose 17 · behavioural 0 (class kept as `# class:` YAML comments).
- Pins deleted: none (no string-in-file presence pin on this command's text exists in the Touches tests; the skill-router description phrases are behavioural and the front matter is untouched).
- Vanished labels: 37 baseline lines vanished; 35 `rule: [ids]`, 2 `narrative` (L5, L7) — author labels, audit owed (no Sonnet/Haiku seats in the clone); no weaker-count available.
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped, LEDGER line printed for fabrik-workflow-review, zero LOSS. `assemble_commands.py --check` rc 1, only DIFFERS/MISSING drift.
- Reader tests (test_trigger_routing, test_producing_command_fragments, test_skill_router_hook, test_assemble_dispatch_step, test_final_gate_stop_hook): end commit 1 failed / 493 passed (`test_the_gate_reports_a_malformed_orphan_position_instead_of_crashing[a broken symlink]`); start-commit set: identical (same 1 failure, pre-existing: broken-symlink case; the set did not grow).
- LEFT FOR THE HUB: ceiling ratchet for `commands/_size_ceiling.json`; Sonnet+Haiku audit of the 35 rule labels and of the 24 reworded entries old-vs-new; CHANGELOG/INDEX rows for the two new `commands/_rules/` files.

## Fix round 1

Two author-blind audits (Sonnet 14 findings, Haiku 31, overlapping) checked against the before-text.

- **Confirmed and fixed (all substantive items):** pool-off banner (five tokens, SUSPENDED/re-enable, author-blind, `NO-POOL:` ban restored to sentence end with `check_subagent_flywheel.py` / `_POOL_POLICY_ON = False` / D-182); Reads ban (never by an item count, interview inputs, upstream mapping, "do not open it to review"); Phase 0 ("Load the matching…", "counts drift", and the lost `only the type argument selects the yardstick` — L7 was wrongly `narrative`, now `rule: p0-yardstick-no-item-count`); Phase 1 seats (artifact + criteria + yardstick input set, independent, native, authoritative pass, `/fabrik-review` § Breadth seats, `≥1`, item numbers drift, classes THIS artifact can fail); field completeness (Path A/B, nothing silently dropped); trigger-vs-value ("not a pass"); hollow and dangling citation split back into two, with `must`, "archived", "before accepting it"; grounding condition (when the artifact touches a vendor); refute "line/anchor"; "in the ledger"; closing round "via" ban verbatim plus the unchanged-pass case; Phase 3 routing (trigger, per-doer mapping, "when it must change", "routing is not convergence"); autonomous-return, neither-human-gate (R25 tag, `type`, "already passed", "operator's explicit go"), epics-review "NOT a type here", em dash, and `Converge here.`
- **Wrong `vanished:` labels fixed:** L7 (`narrative` → `rule`). L6 ("separate, fresh-context pass that forces the closing round") is now carried in `p2-closing-round-md5`; L55 is now carried by `ac-converge-here`, which includes `Converge here.`.
- **Refuted:** none outright; the 70%-stem-pass items (grounding, citations) were restored anyway as cheap.
- **Invented rules:** none found.
- **Own-text words:** baseline 1342 → first cut 797 → after fix 1124.
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped; `assemble_commands.py --check` exit 0.
