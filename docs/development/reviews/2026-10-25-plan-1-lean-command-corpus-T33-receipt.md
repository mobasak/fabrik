OWN TEXT: 7715 -> 6825 words (88%)

# Receipt — T33 lean rewrite of /fabrik-epics (light form), D-1240 re-run

(Sections below up to "Re-ledger round" are the fix round's, written for the old comment-form loader; the re-ledger round at the end supersedes their counts and gates.)

Branch `claude/lean-t33`, base `origin/kaizen-lean-u01` (start commit `851b4b365cc9ccaac91ed851bc669764743ad360`). Baseline: 254 unit keys, sha256 `51f4fa5fa11214719a9f9cbe669e9dd9211c4d897c15811a95370e712928febf`.

## Size
Own text (`command_rules.own_text`, Python `split()`): **7715 -> 6885 words (89%)**. Target was <=50%; **floor reached: ~89%.** Why:
- Fences are 1,834 words and are output grammar the owner and downstream commands read: the parallel-gate lines, the 1h verdict line, the 23-field compact entry, the Infrastructure Decisions template, the ticket frontmatter (parsed by `scripts/epic_order.py`) and the ticket body. They were kept (unchanged fences cannot vanish).
- 79 of 254 baseline units hold a ban word (never/must/only/refuse). Under D-1240 each such clause is verbatim from its ban word to the end of its `;`/`—` clause or sentence, parentheticals included, and cannot be labelled narrative. A first pass cut to 79%, and the coverage check then forced restoring ban clauses and their parentheticals, which put the text back at ~89%.
- The remaining cuts were narrative, reasons and duplicates (intro purpose, POOL OFF history block and html comments, reasons after `—`, the compressed Phase 7 and Phase 3 prose).

## Entries
Ledger `commands/_rules/fabrik-epics.yaml`: **222 entries total** — 170 generated unchanged (`generate_unchanged`), **52 reworded** (hand-written `r-L<n>`), by class: ban 18 · grammar 3 · behavioural 0 · prose 31.
The loader on this base has no `class`/`clauses` keys (`_ENTRY` at `commands/command_rules.py:233`), so each hand entry carries `# class:` and `# clauses: {<n>: narrative}` YAML comments; the hub converts them to keys when the canonical loader lands.

Per reworded entry: clause count (baseline unit split at `;`/`—`) and coverage. Every clause not listed under "narrative" is covered by ONE `text` phrase holding all its anchors (backticked tokens, numbers, paths, ban words) and >=70% of its first 8 content-word stems, and a ban clause is verbatim from its ban word to the clause end. Checked by a scratch script (not in the tree) implementing D-1240 as the brief states it; the stoplist and stemmer (first 5 letters) are my own choice.

| entry | class | baseline clauses | carriers | uncovered clauses (labelled narrative) |
|---|---|---|---|---|
| r-L1 | prose | 3 | 2 phrase(s) | all covered |
| r-L3 | ban | 3 | 1 phrase(s) | {3: narrative} |
| r-L19 | prose | 2 | 1 phrase(s) | all covered |
| r-L26 | ban | 2 | 1 phrase(s) | {2: narrative} |
| r-L30 | prose | 1 | 1 phrase(s) | all covered |
| r-L33 | prose | 2 | 1 phrase(s) | {2: narrative} |
| r-L36 | prose | 1 | 1 phrase(s) | all covered |
| r-L39 | ban | 2 | 1 phrase(s) | {1: narrative} |
| r-L44 | ban | 4 | 2 phrase(s) | all covered |
| r-L45 | prose | 1 | 1 phrase(s) | all covered |
| r-L49 | ban | 5 | 1 phrase(s) | all covered |
| r-L54 | prose | 2 | 1 phrase(s) | all covered |
| r-L57 | prose | 2 | 1 phrase(s) | all covered |
| r-L64 | prose | 1 | 1 phrase(s) | all covered |
| r-L66 | prose | 2 | 1 phrase(s) | all covered |
| r-L68 | prose | 2 | 2 phrase(s) | all covered |
| r-L69 | prose | 2 | 1 phrase(s) | {2: narrative} |
| r-L82 | prose | 1 | 1 phrase(s) | all covered |
| r-L86 | ban | 2 | 1 phrase(s) | all covered |
| r-L87 | ban | 2 | 1 phrase(s) | all covered |
| r-L102 | grammar | 2 | 2 phrase(s) | all covered |
| r-L103 | grammar | 2 | 2 phrase(s) | all covered |
| r-L107 | grammar | 2 | 2 phrase(s) | all covered |
| r-L114 | prose | 5 | 2 phrase(s) | {3: narrative} |
| r-L133 | prose | 4 | 1 phrase(s) | {2: narrative, 3: narrative, 4: narrative} |
| r-L134 | prose | 3 | 1 phrase(s) | all covered |
| r-L137 | ban | 62 | 26 phrase(s) | {9: narrative, 12: narrative, 14: narrative, 15: narrative, 19: narrative, 35: narrative, 48: narrative, 49: narrative, 52: narrative, 54: narrative, 58: narrative} |
| r-L141 | prose | 1 | 1 phrase(s) | all covered |
| r-L142 | prose | 3 | 2 phrase(s) | all covered |
| r-L143 | prose | 3 | 2 phrase(s) | all covered |
| r-L144 | prose | 2 | 1 phrase(s) | all covered |
| r-L146 | prose | 4 | 1 phrase(s) | {4: narrative} |
| r-L153 | prose | 11 | 4 phrase(s) | all covered |
| r-L155 | prose | 2 | 1 phrase(s) | {2: narrative} |
| r-L156 | ban | 47 | 28 phrase(s) | {2: narrative, 11: narrative, 26: narrative} |
| r-L176 | prose | 1 | 1 phrase(s) | all covered |
| r-L180 | ban | 4 | 1 phrase(s) | {4: narrative} |
| r-L181 | ban | 2 | 1 phrase(s) | all covered |
| r-L191 | prose | 4 | 1 phrase(s) | {1: narrative, 3: narrative, 4: narrative} |
| r-L200 | ban | 3 | 1 phrase(s) | all covered |
| r-L208 | prose | 2 | 1 phrase(s) | all covered |
| r-L210 | ban | 95 | 59 phrase(s) | {26: narrative, 72: narrative, 73: narrative} |
| r-L219 | prose | 1 | 1 phrase(s) | all covered |
| r-L221 | prose | 2 | 1 phrase(s) | all covered |
| r-L222 | ban | 3 | 1 phrase(s) | all covered |
| r-L224 | prose | 5 | 3 phrase(s) | all covered |
| r-L231 | prose | 1 | 1 phrase(s) | all covered |
| r-L239 | ban | 3 | 2 phrase(s) | {3: narrative} |
| r-L245 | ban | 2 | 1 phrase(s) | all covered |
| r-L246 | ban | 6 | 4 phrase(s) | {6: narrative} |
| r-L248 | ban | 3 | 1 phrase(s) | all covered |
| r-L249 | prose | 1 | 1 phrase(s) | all covered |

## Vanished labels (author labels — audit owed; the Sonnet + Haiku pair could not run in the clone)
- 60 vanished baseline lines: 52 `rule: [r-L<n>]` · 7 `narrative` · 1 `duplicate-of`.
- narrative (no ban word; history, reason or restated elsewhere): L65, L73, L84, L151, L188, L251, L254.
- duplicate-of: L177->r-L176.
- Partial labels worth the audit pair's look (clauses labelled narrative inside a `rule` entry): L3 (the `owner:` clause, restated by the frontmatter `owner:` line), L39 (the PORTS.md/README/WatchdogConfig/`kind:` list, restated by the Never-quote-a-remembered-value guardrail), L73, L133 (POOL OFF ruling history; its operative clauses are carried by the new POOL OFF line), L188, L191, L251.
- Weaker-count: not measured (no audit run).

## Pins
None deleted. The only tests naming this command pin it behaviourally (`tests/test_check_command_corpus.py` audits it like any source; `tests/test_domain_pack_epic_headings.py` parses the overlay-merge table, kept byte-identical; `tests/test_skill_router_hook.py` pins the description trigger phrases, frontmatter untouched; `tests/test_producing_command_fragments.py` pins the include lines, all kept). `pins:` is empty.

## Gates
- `python3 -m pytest -q tests/test_command_rules.py -rP`: 32 passed, 3 skipped; `LEDGER fabrik-epics.yaml: 222 entries · vanished {'duplicate-of': 1, 'narrative': 7, 'rule': 52}`, zero LOSS.
- `python3 commands/assemble_commands.py --check`: exit 1, DRIFT lines all `DIFFERS`/`MISSING` (installed corpus not rendered); REPORT line: `fabrik-epics: shrank to 22967 words, ceiling 24511`.
- Reader-test run (23 test files naming `fabrik-epics` or globbing the corpus; `test_cli_orchestrator_hint.py` errors at collection at the start commit too): failure set at the start commit and at the end is **identical, 17 failures** (`tests/test_quota_dashboard.py` x7, `tests/test_check_command_corpus.py` x7, `tests/test_agent_definitions.py` x1, `tests/test_assemble_dispatch_step.py` x1, `tests/test_command_run.py` x1), all box-service or environment reds; 1251 passed at the start.
- `pip install -e .` fails in this clone (`harbor>=0.18.0` unavailable); `pytest`, `pyyaml`, `hypothesis` installed instead.

## LEFT FOR THE HUB
- Ratchet `commands/_size_ceiling.json` at merge (REPORT line above).
- Convert the `# class:` / `# clauses:` comments to keys when infra-3's loader lands; audit pair on the labels above.
- Decide whether a ~89% floor is acceptable for this unit or whether the fences (1,834 words) should be re-cut under a grammar-only reading.

## Re-ledger round (canonical loader, W-9cd8653d / D-1245, branch `claude/lean-t33-rl`)

**Own text: baseline 7715 -> fix round 6885 -> now 6825 words (88%).** Measured with `wc -w` over `commands/_sources/fabrik-epics.md` (the `own_text` `split()` count). The 50% target is **not reached; floor named below.**

**LOSS: 25 lines before (24 lint B, 1 lint D, all `fabrik-epics.yaml`) -> 0 after.** `assemble_commands.py --check` still prints `_shared/*` LOSS lines (T01d's); none is this ledger's.

**Entries: 52 reworded (`r-L<n>`) / 216 total** (164 unchanged `u-L<n>`). Classes as the loader reads them: ban 71 · prose 145 (the LEDGER line). All `# class:` / `# clauses:` comments are now real keys.

### What the conversion forced (every fix is in the live text or the labels, never in the loader)
- Old `# clauses:` numbers used the previous loader's clause count; every label was recomputed under `_clauses` (`;`/`—` outside code and parentheses, a fence at its lines). Labels now sit only on clauses with no ban word: r-L3 {3}, r-L26 {2}, r-L69 {2}, r-L114 {3}, r-L133 {2}, r-L146 {4}, r-L155 {2}, r-L175 {3}, r-L180 {4}, r-L182 {2}, r-L191 {3,4}, r-L239 {3}, r-L246 {3}. r-L137, r-L156, r-L210 carry no labels: every fence line is covered by a phrase.
- r-L39 was one clause holding `never`, so `{1: narrative}` was illegal. Restored verbatim in Phase 1 (five anchors: `PORTS.md`, `README.md`, `spec_loader.py::WatchdogConfig`, `kind:`, `templates/<type>/defaults.yaml`); the entry is gone, the unit survives.
- Table rows 4, 5, 9 were tagged `grammar` (every clause verbatim) and had been shortened; restored verbatim, entries r-L102/103/107 removed.
- r-L33 clause 2 and r-L224 clause 2 were uncovered, not narrative: the words went back into the live text (`the universal-category audit in Phase 1h`, `carried verbatim from Phase 1`). r-L146 and r-L191 phrases held too few stems or lacked `181`; `a cycle here leaves`, `Two native layers (the pool is OFF, D-181)` added.
- r-L210 clause 12 lacked `Stage-1/Stage-3`, clause 28 lacked `never a remembered count;` (lint D): both restored. r-L137 clauses 7/29 lacked the `#12`/`#5` anchors: the `**` around them sat where the fence parity reads it as code, so the bold was dropped. r-L156 clause 8 regained `from Technology Decisions`.
- r-L156's padded carriers (phrases for other entries' lines) were replaced by one phrase per clause.

### Cuts this round (net -60 words vs the fix round despite ~90 words the loader made me restore)
Narrative or tail removed, each with its label: L47 (`duplicate-of` the guardrail `u-L232`), L136 (pointer, narrative), L177 (rationale; the tail also left r-L176), L182 clause 2, L175 clause 3, L18/L205 tails, the Consumes examples, the self-healing failure-class list, the watchdog cap-name list, the Registrars qualifiers in the ticket body (the compact entry keeps them). L251 relabelled `duplicate-of: u-L189` (it restated `YOU keep the writing`).

### Floor table: why the file stops at ~88%
Live rule count: 254 baseline units = 36 headings/markers + 10 narrative/duplicate labelled (8 narrative, 2 duplicate-of) + 208 rule-bearing units, 79 of them holding a ban word. 6825 words / 208 rules is about 33 words per rule.

| block | words (approx.) | why it cannot shrink under zero LOSS |
|---|---|---|
| ticket body fence (L210) | 700 | 95 clauses; ban spans verbatim (`never invented`, `never fabricate`, `MUST include`, `only` in the 4-stage parenthetical, three `N/A only for a Retrofit`, Scaffold `never a remembered count; … never this pipeline`, `never Docker DNS`, Shape `never a remembered list or count; has_bearer_api …`, `never duplicate`); the rest are field lines of 5-12 words whose backticked tokens and paths are anchors |
| compact 23-field entry fence (L156) | 570 | 24 clauses, each a field line: anchors are the tokens (`agents-fabrik.md`, `scaffold.py::SCAFFOLD_TYPES`, `none`, `10.99.0.1`, `core/75-workers-jobs.md`, `src/fabrik/spec_loader.py::Shape`); ban spans on Scaffold, Owned paths, Shape, i18n; Registrars keeps its 7-name list as the canonical one |
| Infrastructure Decisions template fence (L137) | 500 | 35 clauses; 11 hold ban words (`migration-only`, `never inline >10s`, `only for kind: static` to line end, `never print/console.log`, `never a static 200`, `never import at runtime`, `never copy cap values`); the others are headings and one-line bullets |
| 1h table + overlay table | 330 | 14 rows are units of 8-30 words, anchors only; row 7 holds `only`, so it is verbatim from `only` to the row end; the overlay table is pinned by `tests/test_domain_pack_epic_headings.py` |
| Guardrails (24 bullets) | 480 | every bullet opens `Never`; each ban clause is verbatim to its `;`/`—` end, and clause 2 of five also holds `never`/`only` |
| Phase 0 reads + Phase 1b-1f | 1000 | ban spans plus input-contract lines whose first 8 stems and anchors already fill the sentence; the one long non-ban clause (L88, 60 words) is 3 clauses of 8-stem minimum |
| Phases 2-7 prose | 1300 | `MUST`/`never`/`only` clauses in the repair run, the flavour sentence, the token budget, 5a read-only dispatch, the owned-paths seam |

Where a non-ban clause still exceeds anchors + 6 of 8 stems, the tail is a short example or enumeration (L52's Retrofit field list, the 14-verdict closure list, L154's arithmetic): dropping it would drop a stem inside the first eight or an anchor, so those stay. No measure here is a D-row; the hub decides whether ~88% stands as this unit's floor.

### COUNTS (self-audit, line by line against `fabrik-epics.baseline.txt`, `fabrik-epics.yaml`, `commands/_sources/fabrik-epics.md`)
COUNTS: 216 entries read / 52 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels
- Pass 1 found and fixed: r-L146 phrase held 4 of 7 stems; r-L191 clause 1 lacked `181`; r-L210 clause 12 lacked the `Stage-1/Stage-3` anchor and clause 28 failed lint D; r-L137 clauses 7/29 lacked `12`/`5`; r-L224 clause 2 lacked `1`; table rows 4/5/9 (class grammar) not verbatim; L251's label was `narrative` for a restatement of `YOU keep the writing`; r-L156 carried other entries' phrases.
- Pass 2 found nothing against the four checks. Tails dropped beyond the first 8 stems, for the audit pair to judge: L18 ("read what actually arrived, the section is extensible"), L205 ("once assigned, by whichever agent claims the epic"), L156 Consumes ("tables, endpoints, env vars, middleware"), L137 self-healing ("OOM, queue backlog, …, code-level regression"), L137 watchdog ("daily_budget_usd, …, propose_fix_prs"), L210 Registrars ("(always)", "(shape.kind)", "(opt-OUT)", the `infra: {<name>: false}` force-disable, kept in the compact entry and in Phase 5 check 3).
- Partial labels worth the pair's look: L133 clause 2 (POOL OFF ruling with date and decision ids; its operative consequence is L134's native-seats line), L73, L84, L151, L188, L254 narrative.

### Gates (start -> end)
- `tests/test_command_rules.py -rP`: start 1 failed / 56 passed; end 1 failed / 56 passed. The one failure is `test_the_live_corpus_has_no_loss` (it fails on the `_shared/*` ledgers, T01d's); the PASSES section shows `LEDGER fabrik-epics.yaml: 216 entries · classes {'ban': 71, 'prose': 145} · vanished {'duplicate-of': 2, 'narrative': 8, 'rule': 52}` and no LOSS line of this ledger.
- `python3 commands/assemble_commands.py --check`: start 25 LOSS lines of this ledger (+ `_shared/*`), end 0 of this ledger; DRIFT only `DIFFERS`; `REPORT fabrik-epics: shrank to 22907 words, ceiling 24511`.
- Reader-test gates: enforcement group 14 failed / 100 passed both times, same 14 names; assemble/corpus group 343 passed both times; improve/measure group 2 failed / 573 passed both times (`test_command_measure.py::test_check_exit_order_loss_then_ceiling_then_drift`, `test_conftest_isolation.py::test_the_two_live_box_tests_pass_a_merge_check_on_a_drifted_box`: both fail on the `_shared/*` LOSS exit 4 and the missing `origin/master`); final-gate group 402 passed / 2 skipped both times; producing-fragments group 464 passed both times; skill-router group 278 passed both times.

### LEFT FOR THE HUB
- Ratchet `commands/_size_ceiling.json` at merge (22907 words now).
- The audit pair over the labels and tails above; kaizen's call on whether ~88% is this unit's floor or whether the fences need a grammar-only reading (D-row).
- `_shared/*` LOSS (T01d) is untouched.
