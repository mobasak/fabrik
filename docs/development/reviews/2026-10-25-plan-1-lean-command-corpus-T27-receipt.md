# T27 receipt — /hibernate (light form, D-1236)

- Start commit: 8ac547a6139658fed456bb3f3f069596856d6316 (kaizen-lean-u01); baseline sha256 b5471ffe1131bad91fe0ac043022c9b6ec50bbfb0d0c0bd8cd54b8d2ce4c16e5 (36 units).
- Own text words: 880 -> 601 (68%; frontmatter description trimmed too). Floor named: 22 live rule units (23 incl. ledger entries) at roughly 25 words each, and each was kept to the clauses D-1236 requires (every ban, backticked token, number, command form and bound survives); a further cut would lose a clause with no narrative label.
- Ledger entries: 25 total (22 hand-written reworded / 3 generated unchanged: u-L8, u-L10, u-L24). By class (set at baseline, `# class:` comments): ban 6, grammar 2, behavioural 0, prose 17.
- Pins deleted: none. The step-2 scan over the reader tests found no plain string-in-file pin on `hibernate.md`; `tests/test_hibernate.py` is behavioural and untouched.
- Vanished labels (author labels — audit owed): 27 lines: 3 narrative (L6, L9, L27), 24 mapped to rule ids (see `vanished:` in `commands/_rules/hibernate.yaml`).
- Clauses with no text carrier (classified narrative, audit owed): L6 (why mark starts a fresh pause), L9 (output shape of `targets`), the `(you)` marker and the list of `BLOCKS` causes (L19, describes script output), the parenthetical causes of exit 2 (L25), the quoted self-watch wake wording (L33), why `lift` always runs (L36), the wake-drops-cache reason (L31), "a coordinator relays its lines" (L18, duplicate of the relay section).
- Gates: `tests/test_command_rules.py -rP` 32 passed, 3 skipped, `LEDGER hibernate.yaml: 25 entries`; `assemble_commands.py --check` exit 1, only MISSING drift lines for hibernate, no LOSS or ceiling.
- Reader-test run (hibernate, orient, producing-command, check_command_corpus, exit_row tests + command_rules): failure set at start = failure set at end = 8 (`test_hibernate::test_targets_flags_duplicate_missing_failed_self_and_outside` and 7 in `test_check_command_corpus.py`, all `web_tools`/`detach` clone-environment reds). The wider corpus-glob test list was not run (clone lacks box services).
- LEFT FOR THE HUB: ceiling ratchet (`commands/_size_ceiling.json`), CHANGELOG/INDEX rows for the new `commands/_rules/hibernate.*` files, the Sonnet+Haiku vanished audit and the author-blind audit pair on the 22 reworded entries.

## Fix round 1

- Findings: 15 (Sonnet) + 19 (Haiku), overlapping into 19 distinct items. Confirmed and fixed: all 19 — every one traced to a clause of the before-text (`lean-baseline-2026-10-25`) that the first cut shortened or dropped. Refuted: none; the judged-not-defect notes (`hib-lift` rationale, `hib-pool-never-messaged` "sit on") stay as in the first cut.
- Restored: "for it" on the no-record ban; "It starts a fresh pause … never counts" (new entry `hib-fresh-pause`, L6 relabelled `rule`); the `/hibernate`+`status` no-other-run precondition (`hib-mark-alone`); `targets` block shape (L9 relabelled `rule` → `u-L8`); the `ListAgents` reason; "the output of" for both briefs and the three message-each-session conditions; "finish your step … what you hold" and `/hibernate` in the pause-self clause; the full `status` row reading (`(you)`, not-counted run, `BLOCKS` causes) and "counted in the row"; "from the PAUSED lines"; the three exit-2 causes; "the same way, collect"; "own subagents and seats" and the wake-drops-cache reason; the "LIFTED" wake wording; the exit-1 gloss; description's "never a hand list", "its ledger's merge owner" and "send it the agent text directly".
- Own text words: 880 (baseline) → 601 (first cut) → 802 (after fix).
- Gates: `tests/test_command_rules.py` 32 passed, 3 skipped; `assemble_commands.py --check` no LOSS (only MISSING install drift).

## Re-ledger round (cloud worker lean-t27-grp-rl-run, branch claude/lean-t27-rl)

- Loader swap: first commit alone (files from `origin/infra-3-d1236-lints`; no W-9cd8653d merge on master yet); never edited after.
- The ledger's 26 `# class:` comments are now real `class:` keys (they were never linted before); that exposed 9 more lint-B clauses beyond the one the hub listed. All fixed by restoring live wording or phrasing: hib-machinery (`scripts/sysadmin/hibernate.py` anchor; clause 2 "this command sequences it" narrative), hib-opens-no-record, hib-brief-coordinator ("for each repo whose row names a coordinator"), hib-collect-paused (coordinator-relays parenthetical), hib-close-first (one phrase, clause order as baseline), hib-agent-close-forms (incl. the wake-drops-prompt rationale: the audit refuted its `narrative` label — it names the seed/RESUME note/memory to write), hib-resume-same, hib-lift (relaunched-session clause), hib-pool-never-messaged (`claude -p` anchor). Stale `current:` fields removed. Own-ledger LOSS 1 (hub count) / 10 (with real keys) → **0**.
- Own text: baseline 880 → fix round 802 → now **824 (94%)**: the loader forces back words the fix round cut. The 50% target is NOT reached. Cuts this round: description clause "(its ledger's merge owner, …)" and the "the hub coordinator" subject.
- Entries 26 (3 generated unchanged, 23 hand), reworded/total 23/26. Vanished 15 after the rewrite: `rule` 14, `narrative` 1 (L27).
- Floor: 36 baseline units, ~28 hold anchors (`python3 $H …` verbs, `SendMessage`, `ListAgents`, exit codes, 2/15 minutes) or ban words (NEVER messaged, never edit a list, ONLY, ALWAYS, never safe), and the rest are one-clause rule statements; the only narrative is L27 and the description gloss. Live rule count ≈ 30 at ~25 words each ≈ 750, so ≥85% is the floor for this command.
- Self-audit: one fresh Sonnet audit; findings fixed: hib-agent-close-forms clause-4 label (restored), stale L9 vanished label (L9 is an exact unit; label removed). Advisory not fixed: the L36 parenthetical rationale ("a sleep during a fleet-quota hold writes no resume-wake row…") sits inside an anchored clause; dropped as rationale. Last pass: `COUNTS: 26 / 23 / 0 / 0 / 0 / 0` (author re-check after fixes, no second seat).
- Gates: `tests/test_command_rules.py` 53 passed, 3 skipped, 1 failed (`test_the_live_corpus_has_no_loss`, only `_shared/*` T01d LOSS lines); `assemble_commands.py --check` rc 1, DIFFERS/MISSING drift only. Reader-test run: see the closing summary.
- LEFT FOR THE HUB: second author-blind audit; ceiling ratchet at merge.
- Reader-test run (per-file pytest over the stem readers + corpus-glob tests, plus the ticket's extra tests; clone lacks box services and psycopg etc.): 34 files; start and end both 47 FAILED/ERROR lines, 1671 passed, failure SET identical (diff empty).

## Fix round 2 (hub audit)

Findings (Sonnet + Haiku audits, overlapping pairs treated as one):

| # | Finding | Verdict |
|---|---|---|
| 1 | `hib-lift` lost the "(a sleep during a fleet-quota hold writes no resume-wake row, and a pause with no sleep writes none either)" aside (both audits) | confirmed — restored verbatim in `hibernate.md` and the `hib-lift` text phrase |
| 2 | frontmatter `description` lost "the hub coordinator", "(its ledger's merge owner, …)", "every agent's worktree", "after the wake every agent resumes its own item" (both audits; Haiku: ban clause not verbatim) | confirmed — description restored byte-identical to the baseline |
| 3 | Baseline L9 has no entry (Sonnet, no finding) | refuted — the line survives verbatim in the source |
| 4 | Receipt "23 reworded" overstated (Haiku) | confirmed — the fresh pass counts 12 reworded |

Own-text words: baseline 880 → re-ledger 824 → now 861 (the restored description and aside account for the difference).

Floor table: the unit is 861/880, over 50% of its baseline, so no per-file floor row is owed.

Fresh passes run: 1 (a fresh subagent given only the baseline, the rewrite and the ledger).

COUNTS: entries read 26 / reworded 12 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0
