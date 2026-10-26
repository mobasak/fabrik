# Receipt — T33 lean rewrite of /fabrik-epics (light form), D-1240 re-run

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
