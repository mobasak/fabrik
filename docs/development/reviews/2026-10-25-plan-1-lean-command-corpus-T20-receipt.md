# T20 receipt — /fabrik-doc-converge (light form, cloud worker, D-1236)

- Start commit: `8ac547a6139658fed456bb3f3f069596856d6316` (kaizen-lean-u01). Branch `claude/lean-t20`.
- Own text (`command_rules.keys` unit words): 1540 -> 1316 (85%). **Floor, not 50%**: 743 of the 1540 words are the 13-row Convergence Contract table, each row a per-doc rule (ground truth + completeness clause); cutting them below ~620 words drops clauses, which D-1236 forbids. Narrative cut: the intro restatement, the `check_doc_sync` aside, the "same-change law" gloss, per-phase explanations.
- Entries: 43 total = 10 generated unchanged (`generate_unchanged`) + 32 reworded (`r-L<n>`) + 1 forbidden pin. Reworded/total: 32/43. By class (YAML `# class:` comments): see ledger; ban/grammar/prose tagged by heuristic.
- Vanished: 33 baseline lines, 32 `rule:` (mapped to the reworded entry), 1 `narrative` (L40, the `check_doc_sync` aside). **Author labels — audit owed** (no Sonnet/Haiku seats in a cloud clone). `# clauses:` comments list baseline clauses the heuristic found not covered by the new unit; read by the audit pair.
- Pins deleted: `tests/test_doc_converge_queue_pass.py` whole (6 plain string-in-file presence pins); its phrases are `text` carriers; the absence pin (`every capability claim maps to a FEATURES row`) is `forbidden:` entry `f-capability-claim-features-row`. Kept untouched: `tests/test_assemble_dispatch_step.py` (`project-local docs/reference/<name>.md` survives), `tests/test_skill_router_hook.py` (description untouched).
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped, LEDGER line `fabrik-doc-converge.yaml: 43 entries`, zero LOSS; `assemble_commands.py --check` exit 1, only DIFFERS/REPORT lines.
- Reader-test failure set: start 52 failed / 2223 passed; end 52 failed / 2217 passed (6 fewer = the deleted pins); failing set identical (pre-existing, box services/httpx absent).
- LEFT FOR THE HUB: ratchet `commands/_size_ceiling.json` (report: 22806 vs ceiling 23721) at merge; CHANGELOG/INDEX rows; Sonnet+Haiku audit of the `vanished:` labels and reworded entries (old vs new); tighten the `# class:` tags (no `class:` key in this loader).

## Fix round 1 (lean-t20-fix)

Two author-blind audits (Sonnet 18 findings, Haiku 17) checked against the baseline text; the overlapping pairs were treated as one.

- **Confirmed and fixed (all 24 distinct findings real):** ban word `Only` restored in the follow-up clause (r-L39); `history is never "converged against code"`, `per-allocation` and `none of these has a row, by design` restored (r-L6); RESILIENCE row — `(Beat/cron/queue registrations)`, `top-level`, `in code`, the billable-balance definition, and `never §2's own cost column` back at the clause end (r-L12); SERVICES row — `external` and the `check_compose_services.py only WARNs` fact (r-L11); `top-level`/`the spec's` in QUICKSTART (r-L15); `since the last pass` (r-L17); `actually`, `real`, `in the doc`, `what exists`, `consciously … not a decision`, `review residuals`, `(01M1V443)`, `(it is consumer-contract-hardened)`, `Operate on the current project (cwd)`, `One doc per run — depth over breadth`; the one-doc-guardrail carve-out and `own commit` / `OUTSIDE` (r-L38); the Phase 1 miss definition (r-L26); the honour-bound / mandatory commit-body clause, now its own carrier `r-L40` (vanished L40 was wrongly `narrative`, now `rule`); `r-L37` now carries `Ripples: a fix here may obligate a sibling doc`; `r-L43` carries `lists what it re-read` and the Bump sentence moved to `r-L43b`; `r-L36b` carries the CODE-defect-filing clause (L36 now maps to both).
- **Refuted:** none. Audit 2 #16 (`Operate on`) and #15 (`consumer-contract-hardened`) were low but cheap, so restored rather than argued.
- **Own words** (`command_rules.own_text`): baseline 1661 → first cut 1437 → after fix 1599 (96%). The restored text is rules, not narrative; the cut that remains is the duplicated framing and the ledger-only asides.
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped; `assemble_commands.py --check` zero LOSS lines (only MISSING/DIFFERS/REPORT drift). Ledger now 46 entries.

## Re-ledger round

Re-ledgered under the canonical loader (`_lint`, `_covered`, `_ban_span`, `_clauses`) on branch `claude/lean-t20-rl`.

- **Own-text words** (`command_rules.own_text`): baseline 1661 -> fix round 1599 (96%) -> now 1559 (94%). The 50% goal is not reachable here; see the receipt table.
- **LOSS (this ledger)**: 21 before -> 0 after (`assemble_commands.py --check | grep LOSS | grep -v _shared`). Reproduced at the start commit first.
- **Entries**: 43 total = 27 generated-unchanged (`generate_unchanged`, `class:` now a real key) + 15 reworded (`r-L<n>`) + 1 forbidden pin. Reworded/total: 15/43. 15 `vanished:` lines, each `rule:` to the entry that carries it (the `L40` narrative label is gone: L40 is unchanged and verbatim again).
- `COUNTS: entries read 43 / reworded 15 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0`
- **What earlier passes fixed**: the fix round wrote its entries for the old loader. Here: every `# class:` / `# clauses:` comment became a real key; ban clauses went back verbatim from the ban word to the end of their clause (Phase 0 `No row` sentence, DEPLOYMENT `a hub-side CLI`, OPERATIONS `the read-only ones`, BUSINESS_MODEL `and the set changes`, Phase 2 `ARTIFACT only — a sibling-doc ripple never re-opens the loop)`, the `(The only doc->doc rule ...)` aside, Phase 1 `RUN it`); split entries `r-L36`/`r-L36b` and `r-L42`/`r-L43b` became one unit per baseline line, so the entry's own `text` covers all its clauses; lines that were reworded for 1-2 words (L1, L5, L7, L15-L19, L45) went back to baseline wording, so they are unchanged units and need no `vanished:` label; the `vanished:` label on L40 (a ban line, never narrative) is gone.
- **Cut this round** (narrative / restated, none holds a ban word): intro `depth over breadth (...)` clause (L2 c2, narrative; routing stays in the description and Phase 0); `GitHub resolves a link's leading / ...` rationale (L33 c2, narrative); `a capability/var/job/service found ... exists to prevent` (L26 c2, narrative); `(01M1V443)` history id; `(an uncited drop is a miss, not a decision)` restates `WITH the drop cited`; `(it is consumer-contract-hardened)`; `(they're Fabrik-maintained)`; `(the bidirectional contract)`; the RESILIENCE parenthetical list that cell 2 already carries.
- **Tests**: `tests/test_command_rules.py` 53 passed, 3 skipped, 1 failed (`test_the_live_corpus_has_no_loss`, `_shared/review-probe-catalogue.yaml` LOSS lines only: another unit) at start and end; `test_assemble_dispatch_step.py` + `test_features_queue_pass.py` + `test_producing_command_fragments.py` 12 failed / 81 passed at start and end (identical set, installed-tree checks the clone lacks). No test file edited.

| Clause still over its minimum | Why it cannot shrink |
|---|---|
| L6 `No row ... by design)`, L11 SERVICES row, L14 OPERATIONS row, L16 DEPLOYMENT row, L21 `never hand-kept`, L22 BUSINESS_MODEL `never Stripe ... and the set changes)`, L27 `only commands ... RUN it`, L34 `only`, L38/L39/L40 ripple sentences, L49 | A ban clause is verbatim from its ban word to its clause end; when the ban word sits inside a parenthesis or a table cell the clause runs to the row end or the closing parenthesis, so the whole tail stays. 861 of the 1540 baseline unit words are in ban-bearing lines. |
| Front matter (104 words), headings (55) | Not a ledger unit; the description is the routing trigger. |
| Rows L13, L15, L17-L20, L23 | Each clause is a per-doc completeness rule, not narrative; the only words past the anchors and first 8 stems are the claim itself. Cutting them would keep a carrier and drop the rule. |
| L29, L30, L35, L37, L45-L47 | Short single rules with no narrative left; each is already near its anchors plus stems. |

- **LEFT FOR THE HUB**: ratchet `commands/_size_ceiling.json` (report: 22928 vs ceiling 23721) at merge; CHANGELOG/INDEX rows; an audit-pair read of the 15 reworded entries (old vs new); decide whether the 50% target applies to a command whose table and ban clauses are a rule floor of ~1020 words, or whether a ban clause's verbatim span should stop at the parenthesis it opens.

## Fix round 2 (hub audit)

Findings: the two hub audits (Sonnet, Haiku) overlapped; 11 distinct findings, all checked against the before-text (`lean-baseline-2026-10-25`).

- **Confirmed and fixed (11):** r-L2 (restored "depth over breadth (the whole-tree sweep is `/fabrik-docs-review`; …)"; the `narrative` label removed), r-L9 ("the bidirectional contract"), r-L12 ("every", the "—", the billable-balance parenthetical), r-L13 (defaults clause verbatim), r-L21 ("it documents —", `01M1V443`), r-L23 ("that", "an uncited drop is a miss, not a decision"), r-L25/r-L26 (the miss clause restored; the `narrative` label removed; the carrier is the merged sentence), r-L32 ("consumer-contract-hardened"), r-L33 (the `/` rationale; the `narrative` label removed), r-L36 ("the code's owning session" and "is raised … on it"), r-L48 ("Fabrik-maintained").
- **Refuted:** none. Audit 2's r-L12 "every→each" and r-L9 were restored too, though only marginal.
- Ledger: every restored entry now has `current` = baseline and no `clauses:` label. `pytest tests/test_command_rules.py -rP` prints zero LOSS lines for `fabrik-doc-converge.yaml` (the remaining LOSS lines are `_shared/*`, another unit's). `assemble_commands.py --check` was not run separately; the same check runs inside the test (DRIFT only on `fabrik-task.md`, not this unit).
- Own-text words: baseline 1661 → re-ledger 1559 → now 1647 (−0.8% against baseline, so no per-file floor table is owed).
- Fresh passes: 1 (a fresh subagent given only the baseline, rewrite and ledger).

COUNTS: entries read 49 / reworded 5 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0
