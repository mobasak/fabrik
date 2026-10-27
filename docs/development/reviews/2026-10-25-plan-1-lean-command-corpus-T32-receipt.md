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

## Fix round 1 (task `lean-t32-fix`, branch `claude/lean-t32-fix`)

Two author-blind audits (Sonnet 32 findings, Haiku 25) compared the rewrite against `lean-baseline-2026-10-25`. I checked each finding against the before-text; the two reports overlap, so pairs were treated as one.

- **Confirmed and fixed: all of them.** None refuted. Where the audit named an ID that had drifted, the underlying text was checked against the baseline directly.
- Restored word for word from the baseline: the Project Snapshot fence, the NEW-mode template fence and the EXISTING-mode template fence (with its per-section brackets, Tech Decisions lines, Locked Decisions and Compliance Report examples); the section heading `### EXISTING mode — a superset (… extras add length)` follows the baseline.
- Ban clauses made verbatim again: the email two-stream `MUST`, "Never sacrifice quality to save money", "never generate Windows-style paths", the 12-factor VI/II/XI ban text, "read-once illustrative anchors, never pasted verbatim", the constraint 15(a) "no direct vendor APIs in that pipeline", and the `retain only the non-website scaffolds here` instruction.
- Qualifiers, numbers, paths and objects restored: constraints 2, 6, 12, 15, 16, 19 (estimated monthly cost, every component, if product sends email, OpenRouter API for embeddings, zero code changes, the chat example); i18n `en + tr minimum` and the 3-level validation; responsive `by default` and the place of record; read `FULLY`; the 7 overlap names and "Apply both"; "before anything else, whichever entry path or mode"; "all personas (named/implied)"; the `0-to-5` score scale; "before any epic starts its own corpus chain"; the three EXISTING `.env.example` / SSH-target / doc-hygiene rules; `used_by`; the True-when column of the shape table.
- Rules restored to the body: `docs/RESILIENCE.md` scaffold-time template; the Observability mandate (Gatus liveness for static artifacts, `/health` and `/metrics`); "3 permanent hosts", `30-ops.md` § Multi-host targeting, "Hub vs spoke is a Vision-level choice", `spoke-canary.yaml`; the CURRENT-VALUE live-reads and the `/opt/fabrik/mcp.json` LIVE-sources bullets in the acting set; the NEW/EXISTING routing lines; "guide the owner"; the five Phase 5 acceptance criteria; the lifecycle pointer (`fabrik preplan`, `core/62-using-subagents.md`, "no stage model"); `Canonical: 62-using-subagents.md § Dispatch policy`; the POOL OFF re-enable parenthetical.
- Invented rules removed or corrected: "open each pack the work touches" (the index is now stated as NOT exhaustive, pointing at § B); the scaffold→kind default is the baseline's explicit list again.
- Ledger: 48 `r-fix-NN` carrier entries added (317 entries total); the wrong `narrative` labels (L5, L57, L68, L70, L81, L82, L136, L137, L140, L188, L261, L518, L565 and others) now name a carrier; stale `current` units and text phrases of existing entries were re-pointed to the edited sentences. Ledger reads `vanished {'narrative': 18, 'rule': 507}`.
- Words (`own_text`): baseline 13,442 → first cut 8,280 → after the fix 9,627 (71.6% of baseline). The restored fences account for most of the difference; the floor in this receipt is therefore 9,627, not 8,280.
- Gates: `tests/test_command_rules.py` and `tests/test_vision_reads_work_stores.py` 38 passed, 4 skipped; `assemble_commands.py --check`: drift lines are `MISSING` only (no installed corpus on this box), no `DIFFERS`, no LOSS, no ORPHAN.


## Re-ledger round (task `lean-t32-rl`, branch `claude/lean-t32-rl`, also pushed as `claude/lean-t32-rl-run`)

Base `origin/claude/lean-t32-fix`; first commit is the loader swap from `origin/infra-3-d1236-lints` (commands/command_rules.py, tests/test_command_rules.py, docs/reference/command-corpus-check.md), not ticket work.

| | |
|---|---|
| own-text words (`own_text`) | baseline 13442 → fix round 9627 (71.6%) → now **12229 (91.0%)** |
| own-ledger LOSS | 312 → **0** (`assemble_commands.py --check` prints LOSS only for `_shared/*.yaml`, T01d's, ignored as ordered) |
| entries | 553 (ban 107, prose 446); reworded / total 187 / 553 |
| vanished labels | rule 187 · duplicate-of 25 · narrative 15; 13 clause labels (`clauses:`) |

**The target was not reached, and the size went UP from the fix round. Why:** the fix round's 9627 words passed the old loader only. Under the canonical D-1240 reading 201 clauses of that text missed anchors or under 70% of their first 8 stems (612 stems, 93 anchors, plus ~90 units with no carrier); repairing them lands at ~10.5-11k. I rebuilt the ledger from the full baseline instead of patching the old one, restoring baseline wording wherever a clause is a rule, then re-trimmed. A cut to ≤50% (6721) is not reachable under this reading without relabelling rule clauses narrative/duplicate, which the audit refutes.

**Floor (measured on the ledger, per kept clause: words in the carrier phrase vs the minimum of anchors + 6 of the first 8 stems, or the ban span to clause end):**

| category | kept clauses | words in carrier phrases | minimum (anchors + 6 of first 8 stems / ban span) |
|---|---|---|---|
| prose | 561 | 6084 | 3244 |
| template/snapshot fence line (output grammar) | 165 | 1938 | 956 |
| ban clause (verbatim to clause end) | 108 | 1585 | 1215 |
| table row | 127 | 1577 | 992 |
| anchor-dense clause (>=4 backticked/path/number anchors) | 33 | 846 | 696 |
| table row (ban clause) | 18 | 410 | 267 |
| test-pinned enumeration | 13 | 286 | 212 |
| total | 1025 | 12726 | 7582 |

The telegraphic minimum is 7582 words (56% of baseline) for the 1025 kept clauses before any glue; it needs every clause cut to a fragment ("from day 1", "Pre-flight checks"). I tried an automatic cut to those fragments: it saved 470 words and left sentences broken ("Every OTHER backticked path elsewhere in this — act on…"), so it was discarded. Why clauses cannot shrink: ban spans run to the end of the clause (1585 words in 108 clauses); anchors (paths, tokens, numbers) are 100% required and cluster in lists (846 words in 33 clauses); the Vision Summary / Snapshot templates and tables are output grammar whose every line is a clause (3925 words); the three EXISTING read enumerations are pinned by `tests/test_vision_reads_work_stores.py` (286 words). **Recommendation (floor D-row for the hub):** this command's floor under D-1240 is ~10.3k readable words (~77%), 7.6k only as unreadable fragments; or widen the loader's `clauses:` reading for rationale tails.

### Self-audit

Two author-blind passes (one Opus subagent each, given only baseline, rewrite and ledger). Pass 1: 2 lost, 4 weaker, 0 invented, 11 wrong labels. Fixed: the SPEND clause of L2 and "Same type and version" of factor X restored; the lock header `**Status:** LOCKED` restored in its fence and Phase 0 sentence restored; acceptance criteria for the external-facts gate, input-per-mode, ladder and NEW-adds restored; "Every backticked path … one of two things" restored; the `<!-- POOL OFF -->` suspended instructions restored (no longer labelled narrative); locked-because lines restored; labels L42, L561, L571, L584, v-L13#2, v-L329#4-5, v-L525#49 removed; Phase 2 "Auto-loaded (both modes)" pointer restored. Pass 2: 1 lost (L11, trivial), 6 weaker (minor), 0 invented, 5 wrong labels. Fixed: L46 and L310 (ban word, cannot be duplicate-of) and L211 restored as live text, v-L525#46 label removed, "cite URL + fetch date" restored in L338. Not changed (accepted, for the hub): L11 "Produces a fresh Vision Summary" dropped (implied by L9); L94 rationale sentence dropped; L24 "the rivals dossier" gloss dropped; bold markers stripped in the NEW-template and Snapshot fences (cosmetic, needed so fence carriers match the loader's whole-file normalise); ten ledger phrases for v-L81, v-L176, v-L183, v-L184, v-L212, v-L339, v-L349, v-L410, v-L576, v-L587 point at neighbouring text (short leads such as "Multiple files?"), the content being in the rewrite; L155 duplicate-of v-L25 is partly carried by v-L20.

COUNTS: 553 entries read / 187 reworded / 0 weaker (pass-2 findings above either fixed or accepted as listed) / 0 lost / 0 invented / 0 wrong vanished labels (pass 2 found 5; all fixed; no third pass was run)

### LEFT FOR THE HUB

1. A third author-blind pass over the fixes above, and the floor ruling (D-row) above.
2. Judgment labels to read first: narrative L38 L40(dup→v-L520) L44 L47 L48 L49 L56 L60 L71 L182 L213 L214 L318 L319 L340 L433; clause narratives in v-L55, v-L90, v-L96, v-L166, v-L167, v-L196, v-L320, v-L342, v-L604, v-L525; duplicate-of lines L23 L28 L39 L41 L45 L155 L158 L371 L502 L535 L562-L565 L572 L579 L583 L589 L591-L594 L596 L598.
3. Ceiling ratchet, merge-time render, CHANGELOG/INDEX/D-rows (untouched here).
4. The three loader files were swapped in from infra-3 and never edited.

### Gates

- `tests/test_command_rules.py -rP`: `LEDGER fabrik-vision.yaml: 553 entries · classes {'ban': 107, 'prose': 446} · vanished {'duplicate-of': 25, 'narrative': 15, 'rule': 187}`; zero LOSS lines for it. `test_the_live_corpus_has_no_loss` is red only on the `_shared/*.yaml` LOSS lines (T01d's unit, ordered ignored).
- Reader-test run (38 files, 2242 tests): start commit `origin/claude/lean-t32-fix` 25 failed; end 39 failed. The 14 new reds are all `--check` exit-code asserts that the `_shared` LOSS (exit 4) trips: 11 in `test_assemble_dispatch_step.py`, `test_command_measure.py::test_check_exit_order_loss_then_ceiling_then_drift`, `test_command_rules.py::test_the_live_corpus_has_no_loss`, `test_vision_reads_work_stores.py::test_assemble_commands_check_renders_cleanly_in_an_empty_home`. None touches this ticket's text; they clear when T01d lands. The other 25 are the box-only start set.

## Fix round 2 (hub audit) — `claude/lean-t32-rl-fixc`

Task `lean-t32-rl-fixc`, on `claude/lean-t32-rl`. The two hub audits (Sonnet 15 findings, Haiku 16) overlapped into 31 distinct items; I checked each against the before-text.

**Findings: 31 confirmed, 0 refuted.** Restored in source and ledger:
- The three `markdown` fences (Project Snapshot, NEW and EXISTING Vision Summary) and the `bash` lock-header fence, word for word from the baseline. The EXISTING fence, with its Compliance Report example rows and `Open Questions` / `Out of Scope` lines, is back as a fence instead of bullets.
- Phase 5 Acceptance (both modes, NEW adds, EXISTING adds) in full, including both rivals-gate outcomes, `Silence ≠ confirmation` at N-1, Phase 4 and Acceptance.
- Constraint 19 trigger and non-trigger examples. The wrong `narrative` labels on them (L318/L319), and on L56, L60, L598, L47-L49 and L340, are replaced by `rule` carriers; L45 and L39 are now carried by restored text instead of a false `duplicate-of`.
- `Role`, `Agreed outputs, NEW`, `Core principles` (goal, Planning SLOW, Execution FAST), the `$10/month`/2-weeks rule, the CI/CD sentence, `Produces a fresh Vision Summary`, the Phase 2 auto-load list, Path A numbering and Path B lead-in, 12F rationale (L94/L96), the responsive owner-exception examples, the L144 `302` clause, `politely accepting it`, `left in place`, `BEFORE any live research`, and `Blindly accept research`.
- Added by the fresh passes below: `features total` bands, `Enhance ≠ silent fork`, the two-env `Binds` qualifier, `vision-level` mandates, the filter examples (`Stripe`, `Pinecone`, OpenAI SDK), `Owner says NEW/EXISTING`, the `fabrik audit-registrars` auto-load purpose, and the acting-set bullets for `repo-first` and EXISTING research files. The pre-flight paragraph is again outside the lifecycle list, and the persisted-lock sentence is out of the Acting set.

**Not restored byte for byte.** 15 fence lines lack their `**` markers (Target host, Background processing, Other locked choices, Notifications, the Watchdog `accept-defaults` lines, `Domain structure`, the `wordpress` line, `#19`, the `i18n missing` row). The loader normalises emphasis inside a fenced block differently from a phrase, so a carrier cannot hold a clause split by a bold marker (D-1240 coverage). I stripped only those lines. This is a loader limitation to report upstream.

**Own-text words:** baseline 13442 → re-ledger 12229 (91.0%) → now 13202 (98.2%).

**Per-file floor table (own text over 50%):**

| file | baseline | now | share | why it cannot go lower |
|---|---|---|---|---|
| `fabrik-vision.md` | 13442 | 13202 | 98.2% | the audits showed the re-ledger's 91% cut rules; the restored text is fences, tables, ban clauses and Acceptance conditions that D-1236/D-1240 require verbatim or at 100% of anchors |

**Gates:** `tests/test_command_rules.py -rP`: `LEDGER fabrik-vision.yaml: 581 entries`, zero LOSS lines for this ledger (the one failing test is `_shared/*.yaml` LOSS, another unit's). `assemble_commands.py --check`: exit 4, only MISSING-install drift and `_shared` LOSS. Master's `command_rules.py`, `tests/test_command_rules.py` and `docs/reference/command-corpus-check.md` were used for the gates and left out of the commits.

**Self-audit by fresh readers:** seven fresh subagents ran, one per pass, each given only the baseline, the rewrite and the ledger. Findings per pass: 5, 3, 9 (stale carriers), 12, 4, 1 and then none. Every finding was fixed and the gates re-run before the next pass. The first pass also caught that the persisted-lock sentence had been moved into the Acting set.

COUNTS: entries read 581 / reworded 187 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0 — fresh pass 7 of 7, VERDICT: CLEAN.

## Nits round (hub) — `claude/lean-t32-rl-nits`

Base: `claude/lean-t32-rl-fixc` as-is. Only `commands/_sources/fabrik-vision.md` and `commands/_rules/fabrik-vision.yaml` changed.

1. Template fences, emphasis: restored. Both fences carry the baseline's `**` on every line it had (Notifications, the Watchdog label, options, `cost CAP`, `not` and `on by default`, Domain structure, the `wordpress` line, Target host, `**#19**`, and `**no**` in the `i18n missing` row). Each carrier is one phrase opened with a backtick from the line before, because the loader keeps a fence's `**` unless an odd backtick count precedes it. This also answers the earlier note that a carrier cannot hold a clause split by a bold marker.
2. v-L103 `Binds the two-env rule`: the words were already in the source and the ledger; the baseline's bold is restored (`⚠️ **Binds the two-env rule:**`). Restored.
3. v-L196 purpose clause: already verbatim in the source, and the `needed to interpret … (present/missing/drift/n/a/override/unknown)` text with both anchors is already in the ledger `text`. No change.
4. v-L400 `agents-fabrik.md` anchor: already in the source and in the ledger `text` (`run all 7 per `agents-fabrik.md` § MANDATORY ORCHESTRATOR PRE-FLIGHT`). No change.
5. v-L90 clause 3, `not the four we happen to remember`: carries no instruction (it restates ALL TWELVE), and stays labelled `narrative` (clause 3). Labelled narrative.
6. v-L78 `(lifecycle gaps, not separate from compliance)`: restored in the source and added to the ledger `text`. v-L24 `not scoped to one path`: already in the source and the ledger `text`; no change.
7. L342 `it will confidently recommend Stripe, Pinecone, or a direct OpenAI SDK`: already in the source and in v-L342's `text`; no change.

**Own-text words:** 13202 → 13208 (the six words of item 6; the `**` markers add none).

**Gates:** `tests/test_command_rules.py -rP`: zero LOSS lines for `fabrik-vision.yaml`; the one failing test is `_shared/*.yaml` LOSS (another unit's). `assemble_commands.py --check`: no `fabrik-vision` LOSS, DIFFERS drift only. I could not dispatch a subagent, so the zero-counts self-audit pass was NOT a fresh subagent; the hub's author-blind audit pair covers it.
