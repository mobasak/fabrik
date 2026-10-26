# T29 receipt — lean rewrite of `design-review` (light form, D-1236/D-1238/D-1240)

Run: cloud worker, branch `claude/lean-t23-grp`, TASK slug lean-t23-grp. Start commit: `18cc448 (T28 commit; this source is untouched by T23-T28, baseline text identical to 851b4b3)` (the baseline commit). Baseline sha256 `21e0043c50f853460370b92752fda59fc00384efeb497a0117177121560295b2` (39 keyed lines, `commands/_rules/design-review.baseline.txt`).

## Own text

- `commands/_sources/design-review.md`: 1348 words → 1262 words (93% of baseline; `wc -w` of `command_rules.own_text`, frontmatter included).
- Target ≤ 50% **not met.** Floor: what survives is (a) ban clauses (never/must/only/refuse), kept verbatim from the ban word to the end of their `;`/`—` clause, parentheticals included (D-1240); (b) backticked anchors, numbers and paths, which D-1240 keeps per clause; (c) lines a behavioural or after-text test reads (`assemble_commands.EXTRACT` after-text, the D-191 dispatch step, the `DECISION NEEDED` block); (d) the frontmatter (`description`/`allowed-tools`, ledgered by no unit). What was cut is narrative, incident ids/dates, analogy sentences and duplicated restatements; cutting further needs a rule removed on purpose (a `retired:` row + D-row), which this unit may not do. A D-row for the floor is the hub's.

## Ledger

- entries total 33: 30 generated unchanged (`generate_unchanged`: ban 11, prose 17, behavioural 2), 3 hand-written reworded (ban 2, prose 1, grammar 0, behavioural 0); reworded/total = 3/33
- vanished baseline lines 5: {'rule': 3, 'narrative': 2} (author labels — audit owed)

| entry | class | baseline lines | clauses | how each clause is covered |
|---|---|---|---|---|
| design-review-r1 | prose | L1 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 2 clause span(s) labelled narrative (skip list below) |
| design-review-r3 | ban | L18 | 9 | 9 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word); 1 clause span(s) labelled narrative (skip list below) |
| design-review-r4 | ban | L26 | 2 | 2 by the entry's one `text` phrase (whole new unit: anchors + stems measured per phrase; ban clauses verbatim from the ban word) |

Clause spans labelled narrative (none holds a ban word; checked):
- L1: `(D-181; mechanism revised by D-182 — the provider credentials stay provisioned, so a `fanout` would still dispatch and SPEND: this text is t`
- L1: `(left in place, or in `<!-- POOL OFF -->` comments, for re-enable)`
- L18: `(screens are independent — the same shape `/fabrik-ui-design`'s Build Verification Loop already uses for `fabrik-gui`)`

Coverage method (hand-applied D-1240, by a scratch checker that is not committed and not the loader): per baseline clause (split at `;` and ` — `), ONE `text` phrase holds every anchor (backticked token, number, path) and ≥70% of the clause's first 8 content-word stems (stemmed by suffix strip; stopwords dropped); a clause with a ban word is verbatim from the ban word to the clause end in the carrier; phrases are whole new units (≥6 words, unique in the file); no ban-word clause is labelled narrative/duplicate-of. The loader in this base has no `class`/`clauses` keys (`_ENTRY` lacks them), so each entry's class is a `# class:` YAML comment and the narrative clause spans are the skip list above plus `# clauses narrative:` comments on the `vanished:` rows — the hub converts them when the canonical loader lands. `commands/command_rules.py` and `tests/test_command_rules.py` untouched.

## Vanished labels (author labels — audit owed)

- L1: {"rule": ["design-review-r1"]}
- L6: narrative — persona framing
- L7: narrative — persona framing
- L18: {"rule": ["design-review-r3"]}
- L26: {"rule": ["design-review-r4"]}

## Pins deleted

- `tests/test_design_review_queue_pass.py`: deleted `test_a_login_gated_screen_is_reached_through_the_auth_harness` (its three phrases and the `(2) Check the frozen contracts` slice boundary are carriers of generated entries that list the test under `pins:`); the module keeps its docstring and constants and now collects no tests.
- `tests/test_frontend_design_routing.py` (cross-file route-to-pack loop), `tests/test_command_run.py`, `tests/test_assemble_dispatch_step.py`, `tests/test_skill_router_hook.py`: kept, unchanged text (the frontmatter `allowed-tools`/`description`, the D-191 dispatch step, the `report and nothing else` sentence).

## Failure sets

Reader-test union (spine § Global Constraints; 43 files) via `python3 -m pytest -q`, run in a clean worktree at the start commit and again with this ticket's changes overlaid on it (no `capped_run.sh` here):
- start: 52 failed / 2240 passed (the T28 end state; the same 52 node ids as the start commit)
- end: 52 failed / 2239 passed / 10 skipped — the identical 52 node ids (diffed); 1 fewer pass = the 1 pin test deleted


Gates: `python3 -m pytest -q tests/test_command_rules.py -rP` → 32 passed, 3 skipped, with the `LEDGER design-review.yaml` line and no LOSS; `python3 commands/assemble_commands.py --check` → exit 1, every DRIFT line `DIFFERS from what this tree renders` or `MISSING` (the installed corpus is not in this clone), none other.

## LEFT FOR THE HUB

- Ratchet `commands/_size_ceiling.json` at merge (the report line `shrank to … words` prints it); not edited here.
- `CHANGELOG.md`, `INDEX.md` rows for `commands/_rules/design-review.yaml`, `commands/_rules/design-review.baseline.txt` and this receipt, and any D-row (including the floor row above).
- The author-blind Sonnet + Haiku classification of the vanished lines and the audit pair over every reworded entry (old against new): labels above are the author's.
- Convert the `# class:` / `# clauses narrative:` comments to keys when the canonical loader lands; re-grade the ledger under it.
- Render the corpus at merge (never done in a worktree).
- Floor note specific to this command: the `allowed-tools` frontmatter line (a ~110-word MCP tool list) and the three `!`-fenced git blocks are unledgered runtime wiring and count in the words.