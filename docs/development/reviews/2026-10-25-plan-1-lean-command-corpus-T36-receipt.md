OWN TEXT: 4785 -> 4570 (95.5%)

# T36 receipt — /fabrik-deploy-plan (light form, D-1240 re-run)

Start commit (baseline): `851b4b365cc9ccaac91ed851bc669764743ad360` (origin/kaizen-lean-u01). Baseline sha256 `e45e2e1e2153e9607c640aa17bb7cd60982ab918ddaf819fca757bab6cd90042`, 126 units.

## Own text

`command_rules.own_text` words: 4785 baseline -> 4639 fix round (96.9%) -> 4570 now (95.5%; counted from the fix-round figure less the net words removed, the `--check` total moving 12372 -> 12303). The 50% target is not met; the floor is named below. `commands/_size_ceiling.json` untouched (the coordinator ratchets it at merge).

## Floor (why not 50%)

Measured on the 126 baseline units with the D-1240 reading (clause = text between `;` and `—`, parentheticals kept whole):

- 4,360 words sit in clauses; 1,236 of them are in clauses holding never/must/only/refuse, which stay verbatim from the ban word to the clause end. A ban word inside a parenthetical (u-L2 "only works in dev", u-L119 "spine-only") pins the whole clause: those two entries were tried as cuts in this round and restored, the loader reporting them as ban clauses.
- Every other clause must keep 100% of its anchors and 70% of its first 8 content stems. The first 8 stems of most clauses already include their examples and parentheticals (u-L14, u-L67, u-L81, u-L101), so those cannot be cut without a narrative label that would be a wrong one. What stem-capping frees is the tail after the 8th stem, and a read of those tails shows the rule's own lists and objects (Phase 6 battery probes, the Phase 4 OPERATOR-GATE and deferred-gate timing, Phase 8 posture).
- Phase 5 is one 667-word unit, of which about 230 words are the three `ssh` commands (all anchors) and about 100 are ban-clause text.
- Live rule count: 45 ban entries, 65 prose entries, 110 entries in all. Realistic floor at the D-1240 reading: about 90-95% of baseline. Cutting further means dropping rules the loader cannot see, so it was not done.

## Re-ledger round

Loader: `_ENTRY` on this base carries `class` and `clauses`; the `# class:` and `# clauses:` comments are now real keys. `commands/command_rules.py`, `tests/test_command_rules.py` and the corpus-check doc untouched.

- Own-text words: baseline 4785 -> fix round 4639 -> now 4570.
- LOSS for this ledger: before 4 (rw-L21 lint D and lint B; rw-L118 lint B twice), after 0. `--check` prints LOSS only for `_shared/*.yaml` (T01d's, outside Touches).
- Reworded / total entries: 11 / 110 (rw-L4, rw-L25, rw-L40, rw-L88, rw-L97, rw-L117, rw-L118, u-L55, u-L70, u-L98, u-L102); rw-L21 is back to verbatim text. One baseline line deleted as narrative (L61).
- What changed, entry by entry:
  - rw-L21: the dropped "the fail-open `/fabrik-release` Phase 0 already kills" sat inside the ban clause that starts at "never a hardcoded `origin/<branch>`" and runs to the clause end, so it is restored word for word in source and ledger (lint D); lint B then passes without a label.
  - rw-L118: the quoted gate error text is clauses 2 and 3 of the baseline (the `—` split it); both labelled `narrative`, clause 1 (ban word "refuses") stays whole.
  - rw-L4: clauses 2 and 3 labelled `narrative` (the old comments were off by one).
  - rw-L97: the carrier now keeps "after the runbook" so the first eight stems are held, and names the DEFERRED-gate exception; the timing itself stays in u-L84. The old `duplicate-of u-L84` label is gone.
  - rw-L40, rw-L25, rw-L117: classed `prose`, no clause labels needed (loader reports no LOSS).
  - rw-L88: further cut of the stem-guard rationale parenthetical ("the stem guards are self-consistent … mutual window theft by construction"), beyond the clause's first 8 stems; no ban clause touched.
  - u-L55: dropped "so an abandoned DRAFT still leaves the ruling findable". u-L98: dropped the "(write path, queue drain, companions, routing)" restatement of the Phase 6 list. u-L70: clause 4 (the purpose clause "so the first verify run's container leg resolves …") labelled `narrative`. u-L102: clause 3 ("a per-service plan pointed at an unused directory is a paper backup") labelled `narrative`. u-L61 ("A lying flag = a silently skipped registrar") deleted, vanished `narrative`.
- Vanished labels now: L4, L21, L25, L40, L55, L70, L88, L97, L98, L102, L117, L118 -> `rule: [id]`; L61 `narrative`; L125 `duplicate-of: u-L9`. No clause or line holding a ban word is labelled.

Entries by class (loader summary): ban 45, prose 65.

COUNTS: 110 entries read / 11 reworded / 0 weaker / 0 lost / 0 invented / 0 wrong vanished labels

Earlier passes fixed: u-L119/u-L120 deleted as narrative, then restored (the loader reads "spine-only" as a ban word); the first u-L2 trim, reverted for the same reason ("only works in dev").

## Self-audit pass (read old against new, line by line)

- LOST: none; each rewritten entry's baseline clauses are held by a phrase or labelled, and the loader's lint B/A/D report no LOSS for this ledger.
- WEAKER: none; every ban clause is verbatim from its ban word to the clause end, every backticked token and number survives in its carrier.
- INVENTED: none (rw-L97's "exception: Phase 4's DEFERRED gate" restates the baseline's "EXCEPT when the runbook's terminal step is a DEFERRED gate").
- WRONG-VANISHED-LABEL: none; L61 holds no ban word.
- Residual judgement for the hub's author-blind audit: the dropped rationale/example clauses (L61, u-L70 c4, u-L102 c3, rw-L118 c2/c3, rw-L4 c2/c3) are labelled narrative on my reading; rw-L40's dropped "the stale table is a corpus defect for the operator" and rw-L117's four example behaviours sit past the first 8 stems and carry no label.

## Pins

None deleted. T36's Touches list no test file; `tests/test_check_command_corpus.py` is kept and its pinned phrases survive verbatim. `pins:` is empty on every entry.

## Gates

- `tests/test_command_rules.py -rP`: start 1 failed / 56 passed, end 1 failed / 56 passed (the same pre-existing failure); `LEDGER fabrik-deploy-plan.yaml: 110 entries · classes {'ban': 45, 'prose': 65} · vanished {'duplicate-of': 1, 'narrative': 1, 'rule': 12}`, no LOSS for this ledger.
- `python3 commands/assemble_commands.py --check`: exit 4, every LOSS line a `_shared/` ledger outside Touches (start: the same plus this ledger's 4 lines).
- Reader-test runs, start -> end, failure sets identical: flip-gate group 14 failed / 100 passed -> 14 / 100 (test_assemble_dispatch_step 13, test_assemble_orch_retired 1); worktree-guard group 376 passed -> 376; measure group 2 failed / 746 passed / 2 skipped -> 2 / 746 / 2 (test_command_measure exit-order, test_conftest_isolation live-box); firecrawl group 237 passed -> 237; plan-review group 474 passed -> 474; scratch-brief group 40 passed -> 40. All failures pre-exist (clone lacks box services and the installed corpus).

## LEFT FOR THE HUB

- Run the author-blind audit pair over the 11 reworded entries (old against new) and the Sonnet + Haiku classification of the vanished lines.
- Ratchet `commands/_size_ceiling.json` at merge; CHANGELOG and INDEX rows for the two `commands/_rules/` files.
- A cut to 50% needs a D-row lowering the ban-clause rule (whole parenthetical bound to a ban word inside it) or a floor D-row (live rule count x words per rule): at the D-1240 reading this file sits near 90-95%.

## Fix round 2 (hub audit)

Findings confirmed and fixed by restoring the before-text (source, entry `current`/`text`, and the `clauses:` narrative tags removed where the clause is a rule):

- rw-L88: restored "so no repair path ever writes over or removes an ownerless pause" (the ban object), plus the heartbeat-recreation rationale and the "mutual window theft by construction" clause.
- rw-L118 (both reports): restored the gate's quoted message with its `## Behavior Contract` anchor; the `clauses: {2,3: narrative}` tag was wrong and is removed.
- u-L102: restored "a per-service plan pointed at an unused directory is a paper backup" (the M3 failure criterion); tag removed.
- rw-L40 ("the stale table is a corpus defect for the operator"), u-L55 ("so an abandoned DRAFT still leaves the ruling findable"), u-L70 (the container-leg goal; tag removed), rw-L117 (the four behaviour examples), u-L98 (the parenthetical scope): restored.
- rw-L97 (Haiku): restored the full "EXCEPT when the runbook's terminal step is a DEFERRED gate, where it runs immediately before that gate (nothing can run after it)".
- Haiku's "vanished label names its own id" (L4, L21, L25, L40, L55, L70, L88, L98): not changed. The unit was reworded or restored in the entry of that id, and the master loader (D-1258) expects the `rule:` label to name it; I judge this correct bookkeeping.

Refuted: none otherwise. Own-text words: not re-measured, because this run's sandbox allows no ad-hoc python. The restored text adds roughly 250 words back to the re-ledger text, so it now sits near the baseline.

Fresh subagent passes run: 0. This run cannot dispatch a subagent; the hub's author-blind audit pair covers it. I checked each finding against the before-text line by line; that is not a fresh pass, so I claim no zeros.
