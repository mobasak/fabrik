# T43 receipt — /fabrik-rules-review (light form, cloud worker)

- Start commit: 8ac547a6139658fed456bb3f3f069596856d6316 (origin/kaizen-lean-u01)
- Baseline: `commands/_rules/fabrik-rules-review.baseline.txt`, 78 units, sha256 158d1a5e09fe35af5a638f0a29578452399335f6f7680c38d04bfae8b398a45a
- Own-text words (`command_rules.own_text`): 2056 -> 1198 (58.3%). Target was <=50% (<=1028): **not met, floor named**. The remainder is the frontmatter description (~105 words, its TRIGGER phrases pinned by `tests/test_skill_router_hook.py`), the 4-item blast-radius checklist, the per-phase obligations, the `round` grammar line and the NEVER/READ-ONLY bans; each further cut dropped a clause that the ledger would have to label a rule. Live rules ~38 hand entries x ~20 words plus the unchanged units.
- Ledger entries: 52 total = 14 generated (`generate_unchanged`, class prose) + 38 hand-written (reworded). By class: prose 43, ban 6, behavioural 2, grammar 1 (recorded as `# class:` comments; the loader on this base has no `class:` key).
- Reworded / total entries: 38 / 52. D-1236 applied: ban, grammar and behavioural phrases verbatim; prose carriers reworded to operative clauses, each >=6 normalised words, with their backticked tokens, numbers, paths and NEVER/MUST/only/refuse words kept (reasons and example lists dropped).
- Vanished: 59 baseline lines, every one labelled `rule: [ids]` under `vanished:`; none labelled `narrative` (lines that are reason-only or examples are mapped to the rule they motivate). **Author labels — audit owed.**
- Pins deleted: none. No plain string-in-file presence pin on this command's text exists in the tests naming it (`tests/test_assemble_dispatch_step.py` and `tests/test_skill_router_hook.py` assert render counts and router regexes, not source text).
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped, prints `LEDGER fabrik-rules-review.yaml: 52 entries · vanished {'rule': 59}`, zero LOSS; `assemble_commands.py --check` exit 0 (only MISSING installed-skill drift; REPORT: rules-review shrank to 22399 words vs ceiling 23955).
- Reader-test run (tests naming the stem + corpus-globbing tests, 34+2 files): failure set at the start commit (clean worktree) = failure set at the end, identical diff (52 reds, all pre-existing box-service tests e.g. test_quota_dashboard, test_review_queue_pass); the set did not grow.
- LEFT FOR THE HUB: `commands/_size_ceiling.json` ratchet at merge; audit pair (Sonnet+Haiku) over the 59 vanished labels and the 38 reworded entries old-vs-new; decision whether 58.3% is an accepted floor.

## Fix round 1 (claude/lean-t43-fix)

- Findings: Sonnet audit 24 + Haiku audit 40, overlapping; checked each against `lean-baseline-2026-10-25` text. **Confirmed (real, fixed): 34 distinct** across 28 ledger units. **Refuted / not restored: 6** — reason-only or example-only lines the auditors themselves accept (L17, L22, L28's "Labels lie" kept anyway, the `r-which-packs` skip-example list, `r-hub-finder`/`r-hub-mode` reason clauses beyond the anchors), plus Haiku #32 ("only trace" invented) which is resolved by restoring the original "persisted trace" sentence.
- Restored: POOL OFF banner (D-182, `check_subagent_flywheel.py`, `_POOL_POLICY_ON = False`, `fabrik-gui`, author-blind rule, "native seat records nothing"); the `<!-- POOL OFF -->` pool-form comment and its lead-in sentence (L44); `scripts/review_rubric.py --changed <paths>` and "not per-commit"; "never fixed in place"; HUB mode `project.yaml` anchor and "optionally scoped"; Phase 0 hub-ledger clause; shape-flag list and "INTENTIONALLY on/off"; `exposes_metrics:false`; D-000 ledger sentence and the stack-mismatch-is-not-a-gap rule; "Observability Matrix"; "closed" + recipe pointer; finder-inputs parenthetical and "nothing else"; secrets carve-out verbatim (POOL unit's excerpts, NATIVE finder routing, "never go to pool APIs") — the invented "any seat's" widening is removed; "adversarially … before it reaches the table", "Only gaps that survive"; "do not let a finder's"; "full pass"; "Re-run the fan-out + merge/refute"; "A single pass … is not convergence"; the unprompted-pass anti-dodge clause; the round-record "TERMINAL verdict is reachable", chat-only/"writes no artifact" clause; "anything wrong with a PACK itself"; "volatile/uncertain items as such"; "each with its ADR/spec citation"; description frontmatter procedure summary, "blast-radius mode", "fires for".
- Ledger: `current` now a whole unit for every entry; multi-unit entries split (`r-pool-off-2`, `r-adr-deviations-2`, `r-which-packs-2`, `r-fanout-2`, `r-record-round-2`); vanished L2/L32/L37/L44/L69 relabelled to carriers that now hold them.
- Own-text words: baseline 2056 -> first cut 1198 -> after fix 1709. Floor rises because the auditors' ban/anchor findings could not be satisfied by shorter phrases.
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped, zero LOSS; `assemble_commands.py --check` rc 0.

## Re-ledger round (canonical loader, W-96f36043)

- Base: origin/claude/lean-t43-fix; first commit is the loader swap (`commands/command_rules.py`, `tests/test_command_rules.py`, `docs/reference/command-corpus-check.md` from origin/master, W-9cd8653d merged), never edited after.
- Own-text words (`len(own_text.split())`, front matter included): baseline 2056 -> fix round 1709 -> now 1975 (96% of baseline). **Target 50% not met; the count went UP from the fix round by 266**: under the canonical loader every ban clause must stand word for word from its ban word to the end of its `;`/`—` clause (parentheticals, history and examples inside it included), and each clause needs ONE phrase holding all its anchors, so the fix round's rewordings (which the old loader accepted) had to be restored.
- Own-ledger LOSS: 68 -> 0 (`assemble_commands.py --check`; the remaining LOSS lines are all `_shared/*.yaml`, the shared-file unit's).
- Ledger rebuilt from the baseline: 70 entries (one per baseline rule unit), 63 reworded / 7 kept whole, real `class:` and `clauses:` keys, 1 `clauses:` label(s), every `text` phrase the smallest window the D-1240 reading covers (all anchors, >=70% of the first 8 stems, the ban word's next word, the whole ban span). Vanished labels: 30 lines.
- Floor (why not 50%): the protected windows alone are about 70% of the live text; they are forced by (a) ban spans verbatim to clause end, (b) clauses whose 4-9 backticked/numeric anchors must sit in ONE phrase, (c) history inside ban clauses that D-1238 point 1 forbids labelling narrative. I measured the pure-telegraphic floor (anchors + 6 stems + ban spans, nothing else) at 47-55% of the unit words; reaching it would leave text that no longer reads as instructions, so I stopped at the readable floor.
- Self-audit: one fresh Sonnet auditor read baseline, rewrite and ledger; its findings (LOST/WEAKER/WRONG-LABEL) were fixed in the rewrite (dropped qualifiers restored) and the ledger regenerated. Residual: see COUNTS in the hub summary; hub author-blind audit still owed.
- LEFT FOR THE HUB: policy call on D-1238 point 1 / D-1240 (they force history retention and make 50% unreachable for ban-dense commands); ratchet `_size_ceiling.json`; CHANGELOG/INDEX rows.

## Fix round 2 (hub audit)

- Findings checked against the baseline units (`commands/_rules/fabrik-rules-review.baseline.txt`). The two reports overlap; pairs counted once.
- **Confirmed and fixed (10):**
  - Lost ban sentence in Phase 4 (Sonnet #1, `cu-L65`): "Do not stop after one pass." restored at the head of Phase 4 and added to the `cu-L65` phrase.
  - `cu-L68`: "to completeness; it does not fix the gaps" restored verbatim.
  - `cu-L25` scope (Sonnet #3): the baseline holds it as a separate top-level bullet after the includes (the assembler's grounding-artifact append says so), so it is restored as that bullet and the HUB bullet keeps only "Verify against `python scripts/select_rules.py`" (`cu-L24`).
  - `cu-L23` (both reports): "actually" and "A perfectly-worded rule in a pack whose glob never matches the offending file is theatre." restored.
  - `cu-L48`: "For EACH requirement … cites `path:line` from them — and explicitly flags" restored.
  - `cu-L69`: "in the run record" restored.
  - `cu-L12`: "project's code against its synced packs" restored.
  - `cu-L32`: "wherever" and "mismatch" restored.
  - `cu-L31`: "the project's ADR / architecture-decisions doc" and "ADR-accepted one" restored.
  - `cu-L1`: "in this command" restored.
  - Frontmatter: the invented "whole-surface" (Sonnet #8) removed and "a single diff's rules floor" restored (Haiku).
- **Refuted / no change (2):**
  - Haiku `cu-L45` "narrative" label: clause 1 is only the lead-in "Division of labor"; "build their prompts accordingly" sits in the text phrase verbatim.
  - Haiku headings L11, L26, L36, L42, L57, L64 with no entry: headings are carried verbatim, not rule units.
- Own-text words: baseline 2056 -> re-ledger 1975 -> now about 2045 (estimate, +about 70 restored words; this run had no permitted word counter, so it is not a tool count). Over the 50% floor for the reasons in the re-ledger section.
- Gates run: `tests/test_command_rules.py` prints zero `LOSS fabrik-rules-review` lines (the remaining LOSS lines are `_shared/*.yaml`); `assemble_commands.py --check` exit 4, LOSS lines all `_shared`; reader-test groups run did not grow the failure set.
- Self-audit: **no fresh subagent could be dispatched in this run, so the zero-counts pass was NOT a fresh subagent.** Every restored phrase was checked line by line against the baseline unit and the loader passes; the hub's author-blind audit pair covers the fresh pass. Fresh passes run: 0.
- COUNTS: entries read 70 / reworded 63 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0 (own line-by-line pass over the findings, not a fresh pass)
