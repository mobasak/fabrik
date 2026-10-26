# T25 receipt — /fabrik-flows (light form, cloud worker lean-t25)

- Start commit: `8ac547a6139658fed456bb3f3f069596856d6316` (origin/kaizen-lean-u01); baseline sha256 `2f4dfef8c9704421ce770b73049146784c8f37e3bd1f0c7f0d938bef65bf67b3` (92 units).
- Own text (`command_rules.units`, front matter excluded): **2690 → 1616 words (60%)**. The 50% target was NOT reached: floor named below.
- Ledger `commands/_rules/fabrik-flows.yaml`: 53 entries — 11 generated-unchanged (`generate_unchanged`), 42 hand-written, of which reworded 42 / 53 total. Classes (YAML `# class:` comments): ban 11, grammar 2, prose 29, behavioural 0 (no behavioural test asserts on this command's emitted output). Each hand entry's uncarried clauses are in its `# clauses:` comment.
- Vanished: 73 labelled by the author (**author labels — audit owed**, no Sonnet/Haiku seats in the clone): 68 `rule:`, 5 `narrative` (L5 example, L27 and L79 reworded headings, L66 cert-time anecdote, L86 gate-WARN aside).
- Pins deleted: the SRC presence asserts of `tests/test_flows_queue_pass.py::test_the_draft_is_committed_at_first_write_with_its_index_rows` (renamed `test_the_index_row_rule_quotes_the_checkers_own_messages`; its asserts on `check_doc_index.py`'s own message strings stay). Listed under `pins:` nowhere: the loader on this base has no per-carrier `pins:` use here.
- Gates: `tests/test_command_rules.py` + `tests/test_flows_queue_pass.py` 34 passed, 3 skipped, `LEDGER fabrik-flows.yaml: 53 entries`, zero LOSS; `assemble_commands.py --check` rc 1 with only `DIFFERS`/`MISSING` drift (fabrik-task DIFFERS and uninstalled skills MISSING, pre-existing), the flows ceiling REPORT says shrank 22477 vs 24261.
- Reader-test run (27 files: stem readers + corpus-glob tests): start 14 failed / 1330 passed / 1 collection error; end 14 failed / 1330 passed / 1 collection error; failure SET identical (clone lacks box services, `pydantic`):
  - FAILED tests/test_thread_anchor.py::test_the_register_writes_the_same_anchor_state_as_before_the_ticket
  - FAILED tests/test_command_run.py::test_surface_add_refuses_when_the_record_cannot_be_written
  - FAILED tests/sysadmin/test_rules_render_versions.py::test_live_corpus_cleaned_packs_round_trip
  - FAILED tests/sysadmin/test_rules_render_versions.py::test_cleaned_packs_carry_zero_unmarked_version_literals
  - FAILED tests/test_agent_definitions.py::test_the_live_box_matches_the_repo_sources
  - FAILED tests/test_assemble_dispatch_step.py::test_the_gate_reports_a_malformed_orphan_position_instead_of_crashing[a broken symlink]
  - FAILED tests/test_check_command_corpus.py::test_a_truncated_web_tools_literal_is_said
  - FAILED tests/test_check_command_corpus.py::test_the_selftest_never_grades_the_live_agent_definitions
  - FAILED tests/test_check_command_corpus.py::test_provider_name_in_web_tools_is_caught
  - FAILED tests/test_check_command_corpus.py::test_the_selftest_is_not_vacuous
  - FAILED tests/test_check_command_corpus.py::test_the_import_probe_neither_loads_the_cwd_env_nor_lets_a_module_print
  - FAILED tests/test_check_command_corpus.py::test_the_selftest_counts_the_emitter_lines_it_executed
  - FAILED tests/test_check_command_corpus.py::test_the_cli_survives_a_detached_original_and_a_wrapper_that_owns_the_fd
  - FAILED tests/test_review_queue_pass.py::test_a_cwd_rooted_tool_runs_after_an_os_chdir
  - ERROR tests/test_scaffold_office_extension.py

- Floor: ~45 live rules remain (11 ban, the HARD GATES, 11 gate items, the primary-path counting rule, freeze law, re-freeze table, second-actor, step budget, seat dispatch); at ~35 words/rule that is ~1,600. Going lower removes rules, not narrative.

## LEFT FOR THE HUB
- Audit pair (Sonnet + Haiku) over the 73 vanished labels and old-vs-new for the 42 reworded entries; weaker-count not run.
- Dropped by this cut, derivable elsewhere: the per-type UI pack paths in Phase 0 inputs (`saas/60-saas-ui.md`, `chrome-ext/70-chrome-ext.md`, `mobile-app/80-mobile.md`, `desktop-app/72-desktop.md`); the "Classify at mint" sentence (CLAUDE.md § decision ledger); "warns in the lean run" (its pin deleted).
- `commands/_size_ceiling.json`, CHANGELOG.md, INDEX.md rows for the two new `commands/_rules/` files: coordinator at merge.
- The assembler PARAMS axes for `fabrik-flows` (test_assemble_axes_match_source) were not touched; the Phase 6 gate list keeps their order.

## Fix round 1 (cloud worker lean-t25-fix)

Two author-blind audits (Sonnet 27 findings, Haiku 39; overlapping) checked against the baseline text by hand.

- **Confirmed and fixed (all but the refuted below):** ban clauses restored verbatim (`fl-no-retro-queue` "retroactively", `fl-never-solo` "over it", `fl-freeze-row` "to the old one" + CLAUDE.md pointer, `fl-refreeze-next` "pipeline", `fl-refreeze-impact` "an omitted one" + "in the closing report", `fl-per-flow` "label only … cross-check", `fl-converge` "whole artifact", `fl-commit` "Do not commit unless the user says so this turn (`git add` is fine)" + "superseded where it conflicts"); lost rules restored (L30 planned-feature coverage, "Classify at mint … same COMMIT, not same run", `fl-personas-denominator` coverage defect, `fl-inputs` pack paths + ocoron pointer, `fl-hard-exclusions` consumer-doc paths + reviewer-misapplies sentence, `fl-spec-wide` "one" counts + `/fabrik-data-contract`, `fl-next-review` consumers + `confirmed: 0`, L92 "resolve before consumed", `fl-gate-items` decisions/errors, never trimmed, not-just-involuntary, when applicable, `fl-alignment` placement/affordances + developer disjunct + "selectively", `fl-i18n` locale-sensitive elements, `fl-consumer-reader` onboard/obtain + versioning + denominator wording, `fl-receiver-persona` four contexts + invite link, `fl-headless-personas` "production", `fl-intro` "complete", and the weaker anchors in fl-resilience, fl-async-gap, fl-two-faced, fl-mode, fl-seats, fl-per-persona, fl-success-criteria, fl-frozen-not-attested, fl-wordpress, fl-refreeze-why).
- **Relabelled:** L12 → new entry `fl-self-convergence` (the AUTHOR'S self-convergence vs INDEPENDENT pass split, restored as a sentence); L27 and L79 `narrative` → `rule` (carriers fl-success-criteria, fl-refreeze-why); L49 and L70 now genuinely carried by fl-contract-inputs-shape and fl-freeze-row.
- **Refuted / reworded away:** audit 1 #25 (fl-commit "invented" widening) — the original supersession is restored with its "where it conflicts" scope, so the finding is closed by wording rather than disputed; audit 1 #22 `current:` copy of fl-step-budget was real and is fixed (own `current`).
- **Ledger:** 54 entries; `fl-freeze-row` carries no `current` (its two sentences are checked as text phrases); gates: `tests/test_command_rules.py` + `tests/test_flows_queue_pass.py` 34 passed / 3 skipped, zero LOSS; `assemble_commands.py --check` rc 1 with only DIFFERS/MISSING drift.
- **Words** (`own_text`, whole-file count): baseline 2838 → first cut 1761 → after fix 2154 (all three by `command_rules.own_text`).

## Re-ledger round (cloud worker lean-t25-grp-rl-run, branch claude/lean-t25-rl)

- Loader swap: first commit alone (`commands/command_rules.py`, `tests/test_command_rules.py`, `docs/reference/command-corpus-check.md` from `origin/infra-3-d1236-lints`; no W-9cd8653d merge on master yet). Never edited after.
- Ledger rebuilt with real `class:`/`clauses:` keys, one entry per reworded baseline line holding the REAL baseline text (the fix round's entries cited paraphrased or other-line baselines). Own-ledger LOSS 16 → **0** (`assemble_commands.py --check`; `_shared/*` LOSS lines belong to T01d and are ignored).
- Own text (`command_rules.own_text`, whole file incl. front matter): baseline 2838 → fix round 2154 → now **2333 (82%)**. It rose against the fix round because the canonical loader forces back what that round cut: ban clauses verbatim to their clause end (`fl-gate-*` list, `fl-per-flow` tail, `fl-commit`, freeze clauses), the second clause of each reworded baseline line, anchors in the same phrase (dates, `check_doc_index.py`, pack paths). The 50% target is NOT reached.
- Reworded/total entries 30/80 (50 generated unchanged). Vanished 35: `rule` 29, `narrative` 5 (L5, L27, L66, L88, L90), `duplicate-of` 1 (L3 → u-L89). Narrative clauses inside entries: fl-epic 1,3; fl-ordering 2; fl-step-budget 3; fl-never-solo 2; fl-async-gap 2; fl-exempt 2,3; fl-no-consumer 2,3; fl-refreeze-only-you 1.
- Cuts this round: front-matter sentence and argument-hint; chain fence (L3, duplicate of `## Next`); "what the user sees when slow or down" in the intro (duplicate of the Resilience bullet); examples in L21/L46/L47/L51; L23 gloss; L35/L41/L47/L61/L63/L66/L77(c2 restored after audit)/L86/L88/L90/L91 narrative.
- Floor (why not 50%): 7 ban entries whose ban clause runs to the end of a `;`/`—` clause hold ~290 verbatim words (fl-gate list 100+, fl-per-flow tail 60, fl-receiver, fl-commit, freeze row, refreeze impact/next, i18n, never-solo); 50 unchanged units (~900 words) are exact-text rules with no narrative left (HARD GATES, persona/consumer/reader lists, Phase 4, re-freeze steps, freeze law); the remaining 30 reworded entries are each trimmed to anchors plus the first-8-stem minimum except where listed: fl-inputs 60w (12 pack/doc path anchors in one clause), fl-seats 88w (4 anchored tokens + D-191 clause), fl-intro 43w (anchors + 6 of 8 stems), fl-personas-denominator 43w (date anchor 2026-08-29), fl-primary-path-rule 59w (verbatim marker rule), fl-commit 90w (anchors `check_doc_index.py`, `INDEX.md`, `docs/README.md` in one clause), fl-sc-extract 39w (numbers 5, 12 + stems), fl-receiver-persona 57w (ban clause + examples-free second sentence). About 78 live rules at ~30 words/rule is ~2300.
- Self-audit: one fresh Sonnet audit (3 inputs). Pass 1 found fl-ordering weaker (8-stem coverage), fl-commit c2 mislabelled narrative, fl-exempt c3 label (kept narrative: the clause is the "live case" anecdote; a self duplicate-of is refused by the loader), L12 restored as `fl-self-convergence`, intro "complete", seats "walks its path"; all fixed. Last pass line:
  `COUNTS: 80 / 30 / 0 / 0 / 0 / 0` (entries read / reworded / weaker / lost / invented / wrong vanished labels; after-fix, author re-check of the two flagged items, not re-run through a second seat).
- Gates: `tests/test_command_rules.py` 53 passed, 3 skipped, 1 failed (`test_the_live_corpus_has_no_loss`, only `_shared/*` LOSS from T01d); `assemble_commands.py --check` rc 1 with only DIFFERS/MISSING drift; reader-test run: see the closing summary.
- LEFT FOR THE HUB: author-blind second audit; ceiling ratchet at merge; the hub-side decision whether the canonical loader's per-clause anchors (dates, ids inside parentheses) should bind history parentheticals.
