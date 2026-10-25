# T32 receipt — lean rewrite of `/fabrik-vision` (light form, D-1236 pilot)

Cloud worker run for the hub (operator P0 W-96f36043, cloud credits per D-1234). Branch `claude/lean-t32`, based on `origin/kaizen-lean-u01`.

## Start

- Start commit (baseline and frozen copy): `8ac547a6139658fed456bb3f3f069596856d6316`.
- Baseline: `commands/_rules/fabrik-vision.baseline.txt`, 615 unit keys, sha256 `4a50d432b69053cc40eb2d424eff42679102cf13374d26bd217803797319714b`, written by `command_rules.write_baseline(own_text(source))` at the start commit.

## Own-text words (`command_rules.own_text`, whitespace words)

| | words | share of baseline |
|---|---|---|
| before (start commit) | 13442 | 100% |
| after | 8280 | 61.6% |

Target was at most 50% (6721). **Not reached; the floor is named below.**

### The floor

The rewrite cut 38.4% and stopped where every further cut would delete an operative clause rather than narrative. What the 8,280 words hold, by what pins them:

- **Output grammar the downstream commands parse or the owner confirms** (the two Vision Summary templates, the Project Snapshot, the lock header, the compliance table): about 930 words in fences plus about 560 in tables. These are class `grammar`; `/fabrik-epics` consumes the section names.
- **The 20 constraints, the 12 factors, the architectural mandates and the shape model** (about 2,300 words): each is a distinct rule with its own number, token or path, and D-1236 keeps every backticked token, number, path and NEVER/MUST/only/refuse word.
- **The Guardrails (the `never` list, about 300 words)**, the STOP GENERATION clauses and the question-bar/close includes: class `ban`, verbatim.
- **The three EXISTING read enumerations and the epic-seed paragraph** that `tests/test_vision_reads_work_stores.py` pins by regex segment (about 450 words). The test also anchors on the `/opt/fabrik-lib/README.md` acting-set bullet, which the first rewrite had cut (see Tests).
- **The rule-pack index**: kept as a path list so every pack path survives; only the one-line "covers" descriptions went.

Rule count against words: 269 ledger entries over 8,280 words is about 31 words per live rule. At the 50% target that would be about 25 words per rule, with 197 of the entries already reworded. A floor D-row for the hub: 8,280 words, 61.6%, until the hub rules on the three candidate removals below.

Candidate removals that would need a D-row (kept, not cut, because D-1236 step 8 says a rule removed on purpose needs one): the rule-area evaluation table's Status vocabulary beyond one sentence; the 12-factor "mandate" quotations (kept only the Fabrik violation to catch); the per-pack "covers" descriptions.

## Ledger

`commands/_rules/fabrik-vision.yaml`: 269 entries.

| group | entries |
|---|---|
| generated verbatim by `generate_unchanged` (`u-L<n>`, `text` carrier = the baseline sentence) | 72 |
| reworded or merged, hand-built (`r-L<n>`) | 197 |

By class of the 197 reworded entries (carried as a `# class:` comment above each entry, because the loader on this branch refuses unknown keys and the D-1236 loader lints are not merged yet; `clauses:` lists are not recorded for the same reason):

| class | entries |
|---|---|
| ban | 32 |
| grammar | 20 |
| behavioural | 2 |
| prose | 143 |

Reworded / total: 197 / 269.

- Every ban clause the baseline held as a NEVER/refusal (checked with a case-insensitive scan for never / do not / must not / refuse / forbidden over all vanished baseline units) either survives verbatim in the new text or is a fragment of a sentence that does. After the scan I restored the clauses it flagged (`never from training memory`, `do not rely on fabrik apply`, `never import a vendor SDK`, `do not re-run the debate and do not silently reverse it`, `never auto-included`, `never treated as market-sizing`, and the others).
- Every backticked token in a baseline unit labelled `rule` survives somewhere in the new text (checked by script; two baseline tokens are not carried: `<!-- POOL OFF -->` in a comment, and a line-wrap artifact `65-rag-search.md § Epic ⏎ Decomposition`). Every number and every NEVER/MUST/ONLY/NOT/BLOCKING word survives.
- Carriers: each reworded entry carries the longest run of at least 6 normalised words shared with its baseline unit and unique in the file; ban entries add the ban clause. A fence unit has no `current` (the loader's unit match cannot see a fence that contains blank lines), so its carriers are graded against its whole section.
- Pins deleted: **none**. The step-2 scan printed only `tests/test_vision_reads_work_stores.py` pins (the PLANS.md / STRATEGIC_BACKLOG.md reads, `owner: beta`) which are regex-segment behavioural pins and stay; the other printed phrases belong to cross-file loops (`tests/test_research_tier_order.py`, `tests/test_skill_router_hook.py`, and similar) and stay. No `pins:` list is written.

## Vanished labels (author labels — audit owed)

525 of the 615 baseline units vanished (no exact surviving match). Labels in `vanished:`:

- `rule: [id]` for 494 lines (the unit's operative clause survives, reworded, in the named entry); 31 `narrative` (provenance pointers, incident wording, "agreed outputs" restatements the templates repeat, table headers of tables that were restructured, a dated example pointer).
- I labelled them myself: 517 of the 525 by an explicit line-to-unit map built after reading the full vanished list (a substring of the target unit per line or range), the other 8 by token coverage of at least 0.60 against the best new unit. The Sonnet + Haiku author-blind classification could not run in this clone. **The labels are mine alone; the author-blind audit pair owes a read of every reworded entry, old against new, and of the 31 `narrative` lines.**
- Judgment calls the audit should read first: the 12-factor table became one sentence (L94-L105 → `r-L94`); the rule-pack index lost its "covers" column (L212-L242 → one entry); the second (evaluation) table was merged into the applicability matrix as an Evidence column (L448-L478); the NEW-mode Acceptance bullets (L559-L595) are carried by three merged sentences.

## Tests and gates

Install: `python3 -m pip install -q pytest pyyaml` worked; `pip install -e .` fails here (`harbor>=0.18.0` has no distribution), so the suite ran with `PYTHONPATH=src:.` plus `hypothesis jinja2 pytest-timeout` and the runtime deps.

- `python3 -m pytest -q tests/test_command_rules.py -rP`: 32 passed, 3 skipped. PASSES section:
  `LEDGER fabrik-vision.yaml: 269 entries · vanished {'narrative': 31, 'rule': 494}`, with zero LOSS lines. (With `tests/test_vision_reads_work_stores.py` added: 38 passed, 4 skipped.)
- `python3 commands/assemble_commands.py --check`: exit 1, every DRIFT line `MISSING` (this box has no installed corpus); no `DIFFERS` line, no D-191 line, no LOSS, no ORPHAN. REPORT line: `fabrik-vision: shrank to 27171 words, ceiling 33303 — lowered by assemble_commands.py --ratchet at merge` (render with fragments; `commands/_size_ceiling.json` untouched).
- Reader-test run (spine § Global Constraints): the union of 39 test files (stem readers of `fabrik-vision` plus the corpus-glob tests), 2231 tests, run at the start commit and again at the end.
  - Start: 41 failed, 2179 passed, 11 skipped. The failure set is box-only (`/opt/fabrik/...` paths, a database, services): `tests/sysadmin/test_rules_render_versions.py` (2), `tests/test_agent_definitions.py` (1), `tests/test_assemble_dispatch_step.py` (1), `tests/test_check_command_corpus.py` (1), `tests/test_command_run.py` (1), `tests/test_conftest_isolation.py` (1), `tests/test_fabrik_deck.py` (15), `tests/test_generate_capability_index.py` (12), `tests/test_quota_dashboard.py` (7).
  - First end run: 42 failed. The new red was `tests/test_vision_reads_work_stores.py::test_vision_existing_read_list_names_both_work_stores`, a Touches miss: its regex ends the Phase 0 acting-set segment at the `- \`/opt/fabrik-lib/README.md\`` bullet, which my first rewrite had cut. Restored that bullet (one line); the test is green again and `tests/test_vision_reads_work_stores.py` was not edited.
  - Final end run (after the fix): 41 failed, 2179 passed, 11 skipped, the failure set identical to the start set (compared test id by test id). It did not grow.

## Files

- `commands/_sources/fabrik-vision.md` (rewritten)
- `commands/_rules/fabrik-vision.yaml` (new ledger)
- `commands/_rules/fabrik-vision.baseline.txt` (new baseline)
- this receipt

Not edited, as the dispatch order says: any fragment or seat definition, another command's source, the tooling files, `commands/_size_ceiling.json`.

## LEFT FOR THE HUB

1. The author-blind audit pair (Sonnet + Haiku) over every reworded entry old against new, and over the 31 `narrative` lines and the judgment calls listed above. Each receipt owes "reworded / total" beside the audit's weaker-count: reworded / total here is 197 / 269.
2. The review wave on the rewritten source (this run made no `/fabrik-review` pass; it is a cloud worker).
3. The ceiling ratchet (`assemble_commands.py --ratchet` at merge) and the merge-time render.
4. `CHANGELOG.md`, `INDEX.md` rows for the two new `commands/_rules/` files, and any D-row. In particular a floor D-row (8,280 words, 61.6%, about 31 words per live rule) or a ruling on the three candidate removals above.
5. Tooling: the ledger carries `# class:` comments only. Once the D-1236 loader lints land (class tag, clause coverage, 6-word minimum, uniqueness), convert the comments to the `class:` key and add `clauses:`; the carriers were chosen to satisfy those lints already (at least 6 words, unique), except the ban-class carriers that are shorter verbatim clauses (for example `Never write \`NO-POOL:\` for it` is the whole unit).
6. `commands/_sources/fabrik-vision.md` was changed by a cloud worker while the main checkout was frozen for this unit; the freeze check and the D-1236 "T01d is redone" follow-up are the coordinator's.
