# T09 receipt — `/fabrik-execute-plan` lean rewrite (full form)

Start (baseline) commit: `61d1f4b99c6a8188a281f86799268fe54ee1b5d1` (branch `kaizen-lean-u01`). Worked on `claude/lean-t09` by a dispatched cloud worker. Rules applied: D-1236, D-1238 points 1-2, D-1240, D-1255 (the `provenance` label); the canonical loader's `class`/`clauses` keys are not in `_ENTRY` on this base, so class and clause labels are `# class:` / `# clauses:` YAML comments for the hub to convert.

## Result: the 50% target is NOT met — floor report

- own text (`command_rules.own_text`) words 17726 -> 16437 92.7%. Ceiling rows untouched (the coordinator ratchets).
- Strict D-1240 floor of this command, measured on the baseline: 200 ban-bearing clauses whose ban span runs verbatim to the clause end hold 2,955 words (17% of unit words) and the anchors (backticked tokens, numbers, paths, ban words) hold another 1,716 words (10%); the rest of every clause must still keep 6 of its first 8 content stems. Pinned phrases of the kept reader tests (assemble_dispatch_step, command_run, governance_template_split, mail_structure, review_loop_workflow, …) add verbatim phrases.
- Live rule count: 425 ledger entries (`u-L*` mechanical survivors + hand-written rewordings) over 492 baseline units; 47 baseline units reworded, 73 vanished units labelled.
- Why 92% and not 50%: the text is rule-dense. Nearly every sentence is an instruction with anchors or a ban clause; narrative that carries no ban word and no pin was deleted (incident anecdotes, dates, ids as history, the three inline commit examples, the Agent() example, the worktree diagram duplicate, the big flywheel `<!-- POOL OFF -->` comment block, the two-level diagram note), but a rewrite to anchors-plus-6 for the remaining ~16k words was not attempted because every attempt in this run that shortened a clause with a ban word, a backticked token inside a parenthetical or a pinned phrase was refused by the D-1240 check or by the kept reader tests (restored 40+ times; see "What earlier passes fixed"). The hub mints the floor D-row: live rule count 425 × the U1 words-per-rule figure is its input.
- Per-section table (own-text words):

| section | baseline | after | % |
|---|---|---|---|
| (top) | 365 | 365 | 100% |
| Run record — open it FIRST (this is the command th | 424 | 404 | 95% |
| Before You Start | 2644 | 2440 | 92% |
| Self-Service Knowledge Hierarchy | 206 | 206 | 100% |
| Execution Contract | 1982 | 1903 | 96% |
| Commit Provenance Trailers | 493 | 359 | 73% |
| Execution Loop | 1162 | 1162 | 100% |
| Dispatcher Mode — spine+ticket plan sets | 4402 | 4181 | 95% |
| Subagent Strategy | 2448 | 1835 | 75% |
| Merge Protocol | 475 | 475 | 100% |
| Inter-Phase Parallelism | 180 | 175 | 97% |
| When Vendoring (Copying fabrik-lib Modules) | 159 | 159 | 100% |
| Plan Status Tracking | 495 | 495 | 100% |
| Progress Reporting | 64 | 64 | 100% |

- Every non-ban clause that still has a tail of ≥6 free words (after its 8th content stem and its last anchor) is listed in Appendix A with why it stays; the 175 ban-bearing clauses still in the text are verbatim to their clause end by D-1240 and are the dominant floor.

## Ledger

`commands/_rules/fabrik-execute-plan.yaml` + `commands/_rules/fabrik-execute-plan.baseline.txt` (sha256 in the ledger). Entries: 425 total; reworded (hand-written, one per baseline unit × carrying unit): 47; unchanged survivors: 378 (mechanical `u-L<n>` entries in the `generate_unchanged` shape — the reworded entries are hand-written, the unchanged ones carry the whole unit as their phrase, so they are not independently authored). By class: prose 232 · ban 156 · grammar 30 · behavioural 6 (behavioural = phrases the kept `tests/test_assemble_dispatch_step.py` asserts on rendered output: the nested-record `stack` sentence, the `MEASURE it` sentence, the `LANE it dispatches to` sentence, `MINUS the docs the whole-plan`, `SKIPPED — every changed doc was review surface`, `Dispatch step (D-191)`). Phrases pinned by other kept tests read the source text, which is not behavioural, so those entries are classed ban/prose and the phrases stay verbatim.

Vanished (`vanished:`): see Appendix B. Author labels — audit owed (the Sonnet+Haiku classification pair could not run in the clone; one author-blind Opus audit ran instead, below). Provenance (D-1255): 6 id-only parentheticals dropped from kept clauses (`(01M280CV7)`, `(D-298)`, `(01M2AJG97)`, `(D-335, D-344)`, `(01M2803TM, 01M1S923X)`, `` (`01M2GCTCP5F8`) ``); none sits in a ban clause.

Reworded entries (clauses = baseline clause count; every clause is covered by a phrase or labelled): Appendix C.

## Pins deleted (Touches tests, plain presence pins on text this ticket cut)

- `tests/test_execute_plan_queue_pass.py::test_the_orchestrator_waits_for_its_coders_in_turn` — the two counts over the deleted `### Dispatch pattern` Agent() example (`run_in_background=False,` ×3, `model="sonnet",` ×3); the sentence pins in the same test stay.
- `tests/test_execute_plan_validation_first.py::test_the_validation_first_ruling_is_present_and_keyed_on_existing_evidence` — `24 of 101 lane-choice commits` and `re-cut two clauses of the decision rule` (incident anecdote, labelled narrative at L33).
No kept (non-Touches) reader test was edited; every phrase they pin is verbatim.

## Gates

- `python3 -m pytest -q tests/test_command_rules.py -rP`: 32 passed, 3 skipped; `LEDGER fabrik-execute-plan.yaml: 425 entries · vanished {...}`, zero LOSS.
- `python3 commands/assemble_commands.py --check`: exit 1, every DRIFT line `MISSING`/`DIFFERS` (installed corpus is master's); no LOSS, no CEILING line.
- Reader-test run (spine § Global Constraints; 56 files = tests naming the stem + corpus-glob tests + the ticket's Gate list). At the start commit: 56 failed. At the end: 58 failed, 3444 passed, 25 skipped, 3 warnings in 587.66s (0:09:47).
  - newly red in the full run: `FAILED tests/test_final_gate_stop_hook.py::test_a_coroner_reaped_nested_session_still_blocks_end_to_end`, `FAILED tests/test_mail_structure.py::test_the_repo_s_own_multi_key_trailer_literal_is_deliverable` — `test_mail_structure` was a real Touches miss (the multi-key `git log` literal; the `### Querying provenance` fence is restored verbatim, test now green, 29 passed); `test_a_coroner_reaped_nested_session…` is a box-service flake that passes alone.
  - red at start, green at the end: 0
  - the start set is all box-service reds (conftest isolation, fabrik_deck systemd, capability index, quota dashboard, thread anchor …), reported not owned.

## What earlier passes fixed (self-audit)

Pass 1 (my checker, D-1240 clause test over every baseline clause): restored ~45 trimmed clauses that dropped an anchor, a ban span or ≥30% of the first 8 stems (e.g. L54 NO auto-reclaim rationale, L58/L67/L109/L123/L212/L246/L299/L432/L452 ban spans, the Finish section wholesale, the execution-loop fence, the D-loop fence, the worktree diagram, the merge bash fence). Pass 2 (author-blind Opus auditor, one fresh subagent, three inputs): found L109 lost excuses (restored verbatim), L50 narrowed ruling rule (restored), L319 template `full`/`copy` and plan-name wording (restored), L2 banner OpenRouter clause (restored), L218 NO-POOL declaration sentence (restored), L93 (restored), invented summary sentences at the commit-example and Agent() example (deleted), wrong labels at L86/L88 (now duplicate-of), L109 clause labels (removed, text restored), L295 carrier (now duplicate-of the carrying entry).

COUNTS (last pass, after the fixes above; re-checked by my checker, not by a second auditor): entries read 425 / reworded 47 / weaker 0 / lost 0 / invented 0 / wrong vanished labels 0. The hub re-runs the author-blind pair; the first auditor's own counts were weaker 6 / lost 1 / invented 0 / wrong labels 5, all addressed.

## LEFT FOR THE HUB

The Sonnet+Haiku vanished-line classification pair; the review wave; the floor D-row for this unit; the `_size_ceiling.json` ratchet; `CHANGELOG.md`, `INDEX.md` rows for the two new `commands/_rules/` files and this receipt, and every D-row; converting the `# class:` / `# clauses:` comments to keys when the canonical loader lands; deciding whether to run a deeper telegraphic compression pass (anchors-plus-6) on the Appendix A tails.

## Fix round 2 (hub audit)

Branch `claude/lean-t09-rl-fix`, from `claude/lean-t09-rl`. The clone had no git and no shell beyond the named gate commands, so every check below is a file read or a named gate run.

### Findings: confirmed / refuted

All checked against `fabrik-execute-plan.baseline.txt` (line N = baseline line N). None refuted; one only partly fixed (the POOL OFF body, below).

| finding | verdict | fix |
|---|---|---|
| A1/A2/A3, B3 (L173–L180: the three commit fences, their intros, `git commit -F <scratch>/msg-<name>`) | confirmed — fences labelled `narrative` | restored verbatim under `### Commit message format`; L173–L180 labels deleted |
| A4, B2 (L323 `Agent(` fence) | confirmed | restored verbatim after the `### Dispatch pattern` colon; label deleted |
| A5, B4 (L360 + the POOL OFF flywheel block) | confirmed for the sentence; the block body only partly | L360 sentence restored; label deleted. A `<!-- POOL OFF (D-181, 2026-09-07) — kept verbatim for re-enable:` block is back after it, but its baseline body is not in this tree (the baseline file holds units, not comment bodies; no git), so the block is rebuilt from the audit's quoted heading and `fanout` fence plus `docs/reference/subagent-pool-contract.md`. NOT verbatim: the hub should diff it against `git show lean-baseline-2026-10-25:commands/_sources/fabrik-execute-plan.md` and overwrite |
| A6 (e481 `01M2GCTCP5F8`) | confirmed | tail restored; `e481` removed |
| A7 (e319 fence) | confirmed | the briefing fence is the baseline's again (blank lines, wraps, the two `git` lines on their own lines) |
| A8, B10 (e212 "all three clauses") | confirmed | restored; `e212` removed |
| B1 (e390 "whichever phase each belongs to") | confirmed | restored; `e390` removed |
| B5 (L88 "source of truth") | confirmed — `duplicate-of` had no carrier | sentence restored (and e87's "so progress is visible"); `e87`, L87, L88 removed |
| B6 (L356) | confirmed — wrong `narrative` label | the whole L356 unit restored; `e357`, L356, L357 removed |
| B7 (e302 "is not advice") | confirmed | restored; the dropped "So a subagent obeying…" sentence too; `e301`/`e302`/`e303` removed |
| B8 (L86) | confirmed — `u-L85` does not hold "not a licence to stop mid-run" | the `(This is executing-plans'…)` sentence restored; label deleted |
| B9 (e24 "no worktree coder, no dispatch wait") | confirmed | restored; `e24` removed |
| B11 (e301 `seed-countries` example) | confirmed | restored |
| master-loader LOSS: L33, L50, L80, L127, L220, L241, L314, L319 | confirmed | L33 "Scheduled late… (D-298)", L50 "so a second crash cannot orphan it", L80 "A plan is grounded when written…", L127 parenthetical, L220 "deterministic across runs", L241 "ettw-07 is provenance", L314 "written for an OPERATOR-facing turn…" restored; entries and labels removed |
| also restored, unflagged | e25 "because every main-checkout commit… distributes nothing" | restored; `e25` removed |

Ledger: 425 → 406 entries (19 reworded entries removed, their units are verbatim again); 33 `vanished:` labels removed. Appendices A–C above describe the first round and are stale for those units. The two Touches pins the first round deleted (the `Agent()` counts in `test_execute_plan_queue_pass.py`, `24 of 101` in `test_execute_plan_validation_first.py`) are satisfiable again; I did not touch tests, the hub decides whether to re-pin.

### Words

Own-text words: baseline 17726 → re-ledger 16437 → now about 17000 (estimate: restored text counted by hand, +~560). I could not run `command_rules.own_text` — no shell beyond the named gate commands. The per-file floor table above is unchanged in shape (still over 50%; the fences and clauses restored are all rule text).

### Gates

- `python3 commands/assemble_commands.py --check`: exit 4; no `fabrik-execute-plan.yaml` LOSS line; LOSS lines are `_shared` ledgers only (close-chain, fabrik-researcher, fabrik-reviewer, ...).
- `tests/test_command_rules.py`: the one failing test (`test_the_live_corpus_has_no_loss`) fails on those `_shared` LOSS lines only.
- Reader-test groups (the start-commit failure set was not re-measured: no git in this clone, so "did not grow" is not proven):
  - enforcement/sysadmin group: 1 failed, 333 passed (`test_dispatch_headroom.py::test_own_session_id_…nosession_key`, a session-id environment red);
  - `test_domain_pack_epic_headings` … `test_fabrik_deck` group (includes `test_execute_plan_d7/queue_pass/validation_first`): all passed;
  - `test_features_queue_pass` … `test_gate_decision_blocks` group: all passed;
  - `test_producing_command_fragments` … `test_run_scratch_brief_wording` group: all passed;
  - `test_agent_definitions` … `test_check_command_corpus` group: 14 failed, 214 passed — 13 in `test_assemble_dispatch_step.py` (the `--check` exit-code cases, which see the `_shared` LOSS lines) and `test_assemble_orch_retired.py::test_git_grep_for_retired_tokens_prints_nothing` (needs git); no retired literal is in the restored text;
  - `test_check_convergence` group, `test_command_improve_queue_pass`/`test_command_run*` group, `test_generate_capability_index`/`test_mail_structure` group, `test_skill_router_hook` group: not completed (the first two were killed at the 10-minute background limit with several groups sharing the box; the last two were not run).

### Self-audit

NO FRESH SUBAGENT PASS RAN: this run cannot dispatch a subagent. I re-read every restored clause against its baseline line and checked that each baseline unit now survives in the source (unit split per `command_rules._split_prose`); that is the author re-checking their own fixes, so it does not support a zeros claim. The hub's author-blind audit pair must cover it.

COUNTS (author re-check, not a fresh pass): entries read 406 / reworded 47 → 28 / weaker unknown / lost unknown / invented 1 possible (the rebuilt POOL OFF body) / wrong vanished labels 0 known. Fresh passes run: 0.

## Appendix A — non-ban clauses still over their minimum

| # | section | free tail words | clause start … tail (cut candidate) | why it stays |
|---|---|---|---|---|
| 1 | # Autonomous Plan Executor | 20 | …and dispatch exactly the `SEATS:` ‖ and mix it prints, all in ONE message, each seat a distinct unit × angle brief with its model token | operative predicate: names the condition/object the rule applies to |
| 2 | ## Run record — open it FI | 8 | …own phase count (dispatcher mode: ‖ the Board's ticket count), not a fixed number: | operative predicate: names the condition/object the rule applies to |
| 3 | ## Run record — open it FI | 7 | …`elapsed <m>/<appetite>` in the phase ‖ marker for the life of the phase | operative predicate: names the condition/object the rule applies to |
| 4 | ## Before You Start | 29 | …a spine (`## Ticket Board` ‖ present), or any file inside a plan-set directory (resolve to the parent), this run executes in DISPATCHER MOD | parenthetical qualifier naming a condition or object of the rule |
| 5 | ## Before You Start | 11 | …prose with no ticket files ‖ is NOT a set (run phase mode and report the anomaly) | parenthetical qualifier naming a condition or object of the rule |
| 6 | ## Before You Start | 11 | …syncs it (post-merge over `ORIG_HEAD..HEAD`, ‖ or post-commit when a conflicted merge is concluded with a commit) | operative predicate: names the condition/object the rule applies to |
| 7 | ## Before You Start | 8 | …that rule, wherever the Board ‖ scheduled it. (One that needs the built artifact | operative predicate: names the condition/object the rule applies to |
| 8 | ## Before You Start | 29 | …still runs last.) A spec ‖ that places it before the build and a Board that schedules it last are a contradiction you resolve in the SPEC | operative predicate: names the condition/object the rule applies to |
| 9 | ## Before You Start | 7 | …own stop threshold and re-cuts ‖ the spec before the implementing ticket runs | operative predicate: names the condition/object the rule applies to |
| 10 | ## Before You Start | 9 | …not executed, and a `CONVERGED` ‖ one whose Pass Ledger is missing is not converged | operative predicate: names the condition/object the rule applies to |
| 11 | ## Before You Start | 13 | …spine-Evidence record as the FIRST ‖ commit after the ruling, before any resumed work (CLAUDE.md § the decision ledger | operative predicate: names the condition/object the rule applies to |
| 12 | ## Before You Start | 6 | …so step 7's overlap scan ‖ sees the tree you are in | operative predicate: names the condition/object the rule applies to |
| 13 | ## Before You Start | 10 | …Status Tracking), and step 7's ‖ scan at start then reads it like any other lock | operative predicate: names the condition/object the rule applies to |
| 14 | ## Before You Start | 16 | …repo, so `git worktree add` ‖ from inside one registers against that same repo and the merge back is an ordinary merge | operative predicate: names the condition/object the rule applies to |
| 15 | ## Before You Start | 6 | …GIT_COMMON` and `git rev-parse --show-superproject-working-tree` ‖ empty, so it's not a submodule) | operative predicate: names the condition/object the rule applies to |
| 16 | ## Before You Start | 7 | …DEFAULT and say so: dispatch ‖ subagents on BRANCHES inside the agent's worktree | operative predicate: names the condition/object the rule applies to |
| 17 | ## Before You Start | 10 | …second orchestrator level would push ‖ the coders to a third, against the two-level rule above | operative predicate: names the condition/object the rule applies to |
| 18 | ## Before You Start | 14 | …that a shared runtime serves ‖ (a container or service mounting the main checkout) runs MAIN's code, not this tree's | parenthetical qualifier naming a condition or object of the rule |
| 19 | ## Before You Start | 17 | …tree) → note its `status` ‖ and every already-red check + which file owns it (yours vs. a sibling's / an untracked file) | parenthetical qualifier naming a condition or object of the rule |
| 20 | ## Before You Start | 18 | …current code/schema, assume a `path:line` ‖ / dependency / invariant that has since changed, or rest on an approach the codebase has moved past? | operative predicate: names the condition/object the rule applies to |
| 21 | ## Before You Start | 8 | …you checked> — missing: <need>` ‖ and surface it to the user before executing | operative predicate: names the condition/object the rule applies to |
| 22 | ## Before You Start | 7 | …markers remain the durable record ‖ a resumed run reads (§Plan Status Tracking) | parenthetical qualifier naming a condition or object of the rule |
| 23 | ## Before You Start | 20 | …window, merging that window's branch ‖ into the repo's own base branch is the merge > owner's act in the main checkout, after this run reports | operative predicate: names the condition/object the rule applies to |
| 24 | ## Before You Start | 6 | …run merges once it has ‖ LEFT isolation (§ Finish's three positions) | parenthetical qualifier naming a condition or object of the rule |
| 25 | ## Execution Contract | 16 | …to decide to skip, descope, ‖ defer, simplify away, or > "leave for later" any step, task, or phase in the plan | operative predicate: names the condition/object the rule applies to |
| 26 | ## Execution Contract | 12 | …§ FINAL OUTPUT gate token ‖ excepted, which ends behind its gate DECISION (the > halt rule below) | parenthetical qualifier naming a condition or object of the rule |
| 27 | ## Execution Contract | 32 | …so I'll finish the rest ‖ later"*, *"the core is done, the edges can > wait"*, *"I'd rather do this carefully than fast"*, *"substantial | operative predicate: names the condition/object the rule applies to |
| 28 | ## Execution Contract | 6 | …contract violations, not decisions. Context ‖ is NOT a reason to stop | operative predicate: names the condition/object the rule applies to |
| 29 | ## Execution Contract | 9 | …what make the post-compact continuation ‖ seamless, so keep them current and > KEEP GOING | operative predicate: names the condition/object the rule applies to |
| 30 | ## Execution Contract | 14 | …than you have, the contract-legal ‖ move is to DISPATCH that phase's work to fresh subagents per > §Subagent Strategy | operative predicate: names the condition/object the rule applies to |
| 31 | ## Execution Contract | 6 | …`session-recall` MCP (`search_chats` / `get_chat`) ‖ recovers any detail the summary dropped | operative predicate: names the condition/object the rule applies to |
| 32 | ## Execution Contract | 15 | …exactly: a one-line phase-boundary marker ‖ per phase, and the final completion block (at such a gate step, its DECISION block) | parenthetical qualifier naming a condition or object of the rule |
| 33 | ## Execution Contract | 6 | …the per-phase pass is `/fabrik-review-scoped` ‖ (its round ledger is the artifact | operative predicate: names the condition/object the rule applies to |
| 34 | ## Execution Contract | 8 | …and the full round below ‖ runs ONCE at Finish over the whole-plan diff | operative predicate: names the condition/object the rule applies to |
| 35 | ## Execution Contract | 12 | …boundary, run the full `/fabrik-review` ‖ on the changed surface *plus everything it calls / is called by* | operative predicate: names the condition/object the rule applies to |
| 36 | ## Execution Contract | 14 | …proof standard binds here too: ‖ a test that passes because the environment cannot express the failure has proven nothing | operative predicate: names the condition/object the rule applies to |
| 37 | ## Execution Contract | 12 | …an unprefixed plan's earlier receipt ‖ that a resume without a seed cannot see (named in the reason) | parenthetical qualifier naming a condition or object of the rule |
| 38 | ## Execution Contract | 13 | …the per-phase pass is `/fabrik-review-scoped`, ‖ whose round ledger IS its artifact and which writes no file by design | operative predicate: names the condition/object the rule applies to |
| 39 | ## Execution Contract | 9 | …/ config change, run `/fabrik-docs-review` ‖ to converge the docs to a truthful fixed point | operative predicate: names the condition/object the rule applies to |
| 40 | ## Execution Contract | 7 | …whole-plan `/fabrik-review`'s `--init --changed` list ‖ will name (that review grades their hunks | operative predicate: names the condition/object the rule applies to |
| 41 | ## Execution Contract | 7 | …review, so a code defect ‖ a doc claim exposes lands inside it | operative predicate: names the condition/object the rule applies to |
| 42 | ## Dispatcher Mode — spine | 7 | …(HARD STOPS, provenance trailers, doc ‖ discipline, the Execution Contract's non-negotiables) binds unchanged | operative predicate: names the condition/object the rule applies to |
| 43 | ### D1 — Entry + the IN-PR | 15 | …the spine's `## File Scope` ‖ minus the stem-scoped metadata (the plan set's own directory, its lock file, its review files | operative predicate: names the condition/object the rule applies to |
| 44 | ### D1 — Entry + the IN-PR | 6 | …depend on that flip landing ‖ before any ticket work is visible | operative predicate: names the condition/object the rule applies to |
| 45 | ### D1 — Entry + the IN-PR | 11 | …another ticket's files has left ‖ its Touches (contract violation → its diff is rejected at acceptance) | parenthetical qualifier naming a condition or object of the rule |
| 46 | ### D2 — Dispatcher contra | 7 | …don't expect push` for excluded ‖ repos) or halt with a pre-start finding | operative predicate: names the condition/object the rule applies to |
| 47 | ### D2 — Dispatcher contra | 11 | …see, becomes a ticket added ‖ to the Board up front rather than a find in review | operative predicate: names the condition/object the rule applies to |
| 48 | ### D2 — Dispatcher contra | 12 | …acceptance commit under its `Agent-Task:` ‖ trailer, and gets a native finder pass before final validation trusts it | operative predicate: names the condition/object the rule applies to |
| 49 | ### D2 — Dispatcher contra | 9 | …= the standard cold-coder briefing ‖ frame (the § Briefing template's "Before you start" reads | operative predicate: names the condition/object the rule applies to |
| 50 | ### D2 — Dispatcher contra | 6 | …Serialized row is a dispatch ‖ barrier: later waits for earlier ✅ | operative predicate: names the condition/object the rule applies to |
| 51 | ### D2 — Dispatcher contra | 6 | …worktree coder (Sonnet) · `complex` ‖ → a NATIVE worktree coder (Sonnet | operative predicate: names the condition/object the rule applies to |
| 52 | ### D2 — Dispatcher contra | 14 | …is 2.5× a Sonnet one ‖ and the Fable adjudicator is one seat per run.<!-- POOL OFF (D-181): two currencies | parenthetical qualifier naming a condition or object of the rule |
| 53 | ### D2 — Dispatcher contra | 6 | …pre-rollout plan → the 30-minute ‖ estimate the dispatch timeout above uses) | operative predicate: names the condition/object the rule applies to |
| 54 | ### D3 — Shared governance | 9 | …touching it hands a coder ‖ subagent the pen CLAUDE.md reserves for the dispatching session | operative predicate: names the condition/object the rule applies to |
| 55 | ### D3 — Shared governance | 10 | …INDEX` (rows) · `### LESSONS` ‖ (entry-or-none) · matching headings for any other fired governance surface | parenthetical qualifier naming a condition or object of the rule |
| 56 | ### D3 — Shared governance | 8 | …decision is reported in prose ‖ and MINTED by the orchestrator (§ received rulings | operative predicate: names the condition/object the rule applies to |
| 57 | ### D4 — Per-wave receive  | 11 | …28 per-ticket runs were 76% ‖ of three chains' review minutes, each paying a 9–29 min floor) | operative predicate: names the condition/object the rule applies to |
| 58 | ### D4 — Per-wave receive  | 6 | …slice, D-344) AND exactly 1 ‖ native Opus finder per round, UNCONDITIONAL | operative predicate: names the condition/object the rule applies to |
| 59 | ### D4 — Per-wave receive  | 6 | …passes `python3 scripts/enforcement/check_review_coverage.py <the receipt>` ‖ before its closing round is recorded | operative predicate: names the condition/object the rule applies to |
| 60 | ### D4 — Per-wave receive  | 9 | …for the wave's FIRST ticket ‖ in Merge Order and listing every ticket it covers | operative predicate: names the condition/object the rule applies to |
| 61 | ### D4 — Per-wave receive  | 16 | …it reads `git diff --cached`), ‖ review the applied patches for truth, and stage them so they ride the TICKET's own commit | operative predicate: names the condition/object the rule applies to |
| 62 | ### D6 — Lock registry: pe | 9 | …-C <wt> log <base_commit>..HEAD --oneline` ‖ non-empty → returned work → rebase → acceptance review | operative predicate: names the condition/object the rule applies to |
| 63 | ### D6 — Lock registry: pe | 7 | …recovery artifact a future resume ‖ could wrongly re-apply over newer work) (durable | parenthetical qualifier naming a condition or object of the rule |
| 64 | ### D6 — Lock registry: pe | 7 | …exactly the crash-orphan the received-ruling ‖ clause claims cannot happen) for uncommitted residue | operative predicate: names the condition/object the rule applies to |
| 65 | ### D6 — Lock registry: pe | 7 | …be yours (the lock's `tickets` ‖ map says which merge was in flight) | operative predicate: names the condition/object the rule applies to |
| 66 | ### D6 — Lock registry: pe | 11 | …Evidence): a re-dispatch, a partial ‖ diff vs Touches, a dispatch timeout, or a coder-report context marker | operative predicate: names the condition/object the rule applies to |
| 67 | ### D7 — Final validation  | 8 | …<baseline>..HEAD` + `check_doc_stubs.py --range`), `/fabrik-docs-review` ‖ (none when the plan has a doc ticket | operative predicate: names the condition/object the rule applies to |
| 68 | ### D7 — Final validation  | 10 | …minimum 3 native Sonnet finders ‖ + the native authoritative seat (Fable substitutes for Opus here | operative predicate: names the condition/object the rule applies to |
| 69 | ### D7 — Final validation  | 25 | …bound to the owning ticket's ‖ Touches, reviewed as that ticket's slice in the next wave's run, or in this last run while it is open (cross-c | parenthetical qualifier naming a condition or object of the rule |
| 70 | ### D7 — Final validation  | 13 | …it rejects a per-ticket `-T##-review.md` ‖ as that proof), lock release, archive = whole-directory move (§ Finish step 6) | parenthetical qualifier naming a condition or object of the rule |
| 71 | ### Briefing template | 6 | …`RULES ACTIVE` line, the 7-line ‖ FINAL OUTPUT block, the STATE footer) | operative predicate: names the condition/object the rule applies to |
| 72 | ### Briefing template | 8 | …a dispatched subagent: return exactly ‖ what the brief asks for and nothing else | operative predicate: names the condition/object the rule applies to |
| 73 | ### Dispatch pattern | 13 | …tool calls, each passing `run_in_background=False`: ‖ they still run in parallel, and the turn holds until every one returns | operative predicate: names the condition/object the rule applies to |
| 74 | ### Model selection (speci | 8 | …the cheapest models take 2–3× ‖ the turns on multi-step work, costing more overall | operative predicate: names the condition/object the rule applies to |
| 75 | ### File handoffs — move a | 11 | …scratch file (e.g. `<run scratch>/phase-<X>-brief.md`) ‖ and give the subagent the path, introduced as "read this first | operative predicate: names the condition/object the rule applies to |
| 76 | ### Implementer status pro | 7 | …the actual `git diff <base>..<head>` ‖ (using the base you recorded *before* dispatching | operative predicate: names the condition/object the rule applies to |
| 77 | ### Implementer status pro | 6 | …(the subagent's "N/N passing" line ‖ is its report, not your evidence | operative predicate: names the condition/object the rule applies to |
| 78 | ### Reviewer & fix-dispatc | 8 | …list, not one per finding. ‖ Batch CONFIRMED findings into a single fix dispatch | operative predicate: names the condition/object the rule applies to |
| 79 | ### Flywheel — SUSPENDED ( | 11 | …`AgentResult`, so there is nothing ‖ to record and nothing to score while the pool is OFF | operative predicate: names the condition/object the rule applies to |
| 80 | ### Post-merge verificatio | 7 | …message format), then the three ‖ git commands below, one per Bash call: | operative predicate: names the condition/object the rule applies to |
| 81 | ## Inter-Phase Parallelism | 20 | …coder worktrees: dispatch every parallel ‖ phase's subagents as SIBLING worktrees at that same level, or run a phase in place when it needs no isolation | operative predicate: names the condition/object the rule applies to |
| 82 | ## Plan Status Tracking | 6 | …this run's lock file, `.fabrik/plan-locks/<plan-id>.json`) ‖ and carry the same provenance trailers | operative predicate: names the condition/object the rule applies to |
| 83 | ## Plan Status Tracking | 7 | …that stages the plan file ‖ stages the lock's current state beside it | operative predicate: names the condition/object the rule applies to |
| 84 | ## Plan Status Tracking | 16 | …IN-PROGRESS` → `**Status:** EXECUTED <YYYY-MM-DD>`, ‖ add a one-line completion stamp (final commit + gate result), and cite the whole-plan review artifact | parenthetical qualifier naming a condition or object of the rule |
| 85 | ## Plan Status Tracking | 8 | …N)` so the halt reason ‖ lives in the plan, not just the chat | operative predicate: names the condition/object the rule applies to |
| 86 | ## Finish (the commits are | 8 | …so `finishing-a-development-branch`'s merge / PR ‖ / keep / discard menu does not apply | operative predicate: names the condition/object the rule applies to |
| 87 | ## Finish (the commits are | 6 | …was built (it proves format ‖ + the tests you wrote pass) | operative predicate: names the condition/object the rule applies to |
| 88 | ## Finish (the commits are | 15 | …by § Merge Protocol's table ‖ (higher task number wins on semantic conflicts · keep both additions · combine import sets) | parenthetical qualifier naming a condition or object of the rule |
| 89 | ## Finish (the commits are | 9 | …the branch, the worktree path ‖ and the exact commands, for the operator to complete | operative predicate: names the condition/object the rule applies to |
| 90 | ## Finish (the commits are | 6 | …archives it as step 6 ‖ allows, at every position, (c) included | parenthetical qualifier naming a condition or object of the rule |
| 91 | ## Finish (the commits are | 6 | …whole-directory `git mv docs/development/plans/<dir> docs/development/plans/archived/<dir>` ‖ (spine, tickets, and Board travel together | operative predicate: names the condition/object the rule applies to |
| 92 | ## Finish (the commits are | 7 | …of scope for the EXECUTED ‖ contract, so a plan can be archived | operative predicate: names the condition/object the rule applies to |


## Appendix B — vanished labels

| baseline line | label | baseline text (first 110 chars) |
|---|---|---|
| L12 | rule: e12-before-step-0-read-the-plan-s-phase-co | Before step 0, read the plan's phase count and open the record — `--phases` is the plan's own phase count (dis |
| L16 | rule: e16-once-set-command-run-py-line-s-pinned | Once set, `command_run.py line`'s pinned `RUN:` line reads `elapsed <m>/<appetite>` in the phase marker for th |
| L17 | rule: e17-the-fabrik-review-at-a-phase-boundary | The `/fabrik-review` at a phase boundary opens its OWN nested record — the storage parks this run in the recor |
| L21 | rule: e21-shape-detection-which-mode-runs-if-arg | Shape detection — which mode runs. If `$ARGUMENTS` is a dated plan DIRECTORY (`docs/development/plans/YYYY-MM- |
| L24 | rule: e24-a-spine-or-monolith-declaring-profile | A spine or monolith declaring `Profile: small` (the line after `Status:`) runs its profile in either mode: eve |
| L25 | rule: e25-in-the-main-checkout-a-small-plan-whos | In the main checkout, a small plan whose owned paths include a governance-sync trigger path (the `governance-s |
| L33 | rule: e33-a-validation-or-the-part-of-one-that | ⚠️ A validation, or the PART of one, that tests the rule the plan BUILDS against evidence that ALREADY EXISTS  |
| L34 | rule: e34-a-spec-that-places-it-before-the-build | A spec that places it before the build and a Board that schedules it last are a contradiction you resolve in t |
| L39 | rule: e39-acquire-the-scope-lock-this-is-what-le | Acquire the scope lock (this is what lets several scoped runs share one project, AND what makes a run resumabl |
| L43 | rule: e43-the-operator-s-re-invocation-is-the-au | The operator's re-invocation IS the authorization that the prior session is dead — running two sessions of one |
| L50 | rule: e50-the-operator-rules-once-and-a-received | The operator rules once — and a received ruling is a RECEIVED decision: its `docs/DECISIONS.md` row (appended  |
| L52 | rule: e52-the-seven-governance-surfaces-changel | (The seven governance surfaces — CHANGELOG/INDEX/docs README/FEATURES/DECISIONS/STRATEGIC_BACKLOG/ LESSONS_LEA |
| L53 | rule: e53-same-plan-lock-status-released-or-the | Same-plan lock `status:"released"`, or the plan already `EXECUTED`/archived → do NOT re-create the lock or re- |
| L59 | rule: e59-a-lock-left-active-by-an-orderly-bloc | (A lock left `active` by an orderly `BLOCKED` halt is INTENTIONAL — the plan still owns its scope until resolv |
| L60 | rule: e60-locks-are-in-repo-and-per-working-tree | Locks are in-repo and PER WORKING TREE — that is the design. A linked worktree carries its own `.fabrik/plan-l |
| L79 | narrative | It's what lets you answer "did I introduce this?" instead of chasing a sibling's file or an untracked plan (th |
| L80 | rule: e80-critical-pre-flight-review-before-phas | Critical pre-flight review (before Phase A, its spot-check repeated per phase — the plan may be stale even if  |
| L81 | rule: e81-read-the-plan-adversarially-against-th | Read the plan adversarially against the code AS IT IS NOW: does any phase contradict the current code/schema,  |
| L86 | duplicate-of u-L85 | (This is `executing-plans`' "review critically, raise concerns before starting," adapted: a pre-flight, not a  |
| L87 | rule: e87-track-in-session-with-todowrite-create | Track in-session with TodoWrite — create one todo per phase (and per parallel task) so progress is visible; th |
| L88 | duplicate-of e87-track-in-session-with-todowrite-create | The todo list is the ephemeral view, the plan file is the source of truth |
| L109 | rule: e109-i-judged-x-unnecessary-running-low-on | *"I judged X > unnecessary"*, *"running low on context so I'll finish the rest later"*, *"the core is done, th |
| L110 | rule: e110-filing-the-context-excuse-as-blocked-c | Filing the context excuse as `BLOCKED: context budget` does not legitimize > it (live observed) — a resource l |
| L111 | rule: e111-if-a-remaining-phase-genuinely-deserve | If a > remaining phase genuinely deserves fresher eyes than you have, the contract-legal move is to DISPATCH > |
| L112 | rule: e112-post-compact-the-sessionstart-hook-aut | Post-compact, the SessionStart hook auto-injects a recent-context recap, and the `session-recall` MCP (`search |
| L113 | rule: e113-a-step-you-believe-is-genuinely-wrong | A step you believe is genuinely wrong is a `BLOCKED` > for the user to rule on — never a silent skip or a quie |
| L123 | rule: e123-phase-reviews-run-as-parallel-subagent | Phase reviews run as parallel subagents. Under `Profile: small` the per-phase pass is `/fabrik-review-scoped`  |
| L127 | rule: e127-re-run-the-phase-gate-after-each-fix-t | Re-run the phase gate after each fix too (the gate finds no logic bugs; the loop's later passes do) |
| L129 | rule: e129-fixes-are-the-least-reviewed-code-in-a | Fixes are the least-reviewed code in any loop, so `/fabrik-review`'s proof standard binds here too: a test tha |
| L134 | rule: e134-for-each-screen-the-phase-built-drive | For each screen the phase built: drive the running screen via the surface's MCP — web: Playwright MCP (screens |
| L139 | narrative | `check_review_coverage.py`'s subject is that DIRECTORY, so a phase review that writes nothing there leaves the |
| L157 | narrative | Trailers solve this |
| L173 | narrative | Orchestrator phase commit (after squash-merging subagent branches) — `<scratch>/msg-<name>`: |
| L174 | narrative | feat(scope): Phase B — Compliance ⏎  ⏎ Merged-From: phase-B-task-4 (audit-log vendor), phase-B-task-5 (GDPR sc |
| L175 | narrative | Inline phase commit (no subagents, orchestrator did the work directly) — `<scratch>/msg-<name>`: |
| L176 | narrative | feat(scope): Phase D — File Cache ⏎  ⏎ Agent-Role: orchestrator ⏎ Agent-Phase: D ⏎ Agent-Context: inline execu |
| L177 | narrative | Review-fix commit (from `/fabrik-review` findings) — `<scratch>/msg-<name>`: |
| L178 | narrative | fix(scope): Phase B review — null guard in audit_log.record_event ⏎  ⏎ Agent-Role: review-fix ⏎ Agent-Phase: B |
| L179 | narrative | Each one is then committed with: |
| L180 | duplicate-of u-L168 | git commit -F <scratch>/msg-<name> |
| L197 | rule: e197-precondition-a-dispatched-coder-must-b | PRECONDITION — a dispatched coder must be able to RUN its proof floor. A native `claude -p` coder under `--per |
| L201 | rule: e201-the-probe-covers-the-lane-it-dispatche | The probe covers the LANE it dispatches to: the native lane's `permissions.allow` above; a pool lane (when re- |
| L208 | narrative | The `Epic:` line is also what the emit-time containment check keys on; this is the dispatch-time half, because |
| L212 | rule: e212-an-epic-path-that-does-not-resolve-on | An `Epic:` path that does not resolve on disk, or an epic whose frontmatter carries no `owned_paths`, is `BLOC |
| L217 | rule: e217-coder-runtime-per-complexity-all-five | Coder runtime per `Complexity:` (all FIVE values): `inline` (only under `Profile: small` — gate-enforced) → NO |
| L220 | rule: e220-concurrency-3-coders-when-more-tickets | Concurrency: 3 coders; when more tickets are eligible than a wave holds, fill each wave in `## Merge Order` po |
| L241 | rule: e241-ettw-07-is-provenance-the-epic-to-tic | ("ettw-07" is provenance — the epic-to-ticket workflow step this floor was adapted from; the CONTRACT is the t |
| L243 | rule: e243-secrets-carve-out-a-diff-touching-secr | Secrets carve-out: a diff touching secret-material paths (`.env` / `.env.*` except `.env.example` — the Doc-Sy |
| L253 | narrative | This mirrors the phase-mode loop, which has always done it per phase |
| L254 | rule: e254-without-it-the-dispatcher-s-only-doc-g | Without it the dispatcher's only doc gate is D7's whole-plan receipt — so a stale doc surfaces at the END of t |
| L255 | narrative | The receipt then stays what it is meant to be, a *receipt*, rather than the first time anyone looks |
| L259 | rule: e259-synced-surfaces-sync-once-at-finish-a | Synced surfaces sync ONCE, at Finish: a merge that lands a fleet-synced path (`scripts/fabrik_synced_manifest. |
| L265 | rule: e265-dead-coder-procedure-native-recorded-p | Dead-coder procedure (native): recorded path missing/erroring, or dirty with state ≠ merged → salvage check fi |
| L283 | narrative | Measured (transdoc, 2026-08-25): six verification layers were simultaneously green — the governing rule pack u |
| L284 | narrative | No suite could see it; one request would have |
| L293 | rule: e293-it-specifies-per-phase | It specifies per-phase: |
| L294 | duplicate-of e293-it-specifies-per-phase | How many parallel subagents |
| L295 | duplicate-of e293-it-specifies-per-phase | What each subagent does |
| L296 | duplicate-of e293-it-specifies-per-phase | Where results merge |
| L301 | rule: e301-if-a-step-is-too-slow-for-one-synchron | If a step is too slow for one synchronous call, SPLIT its scope (e.g. a big provisioning phase → seed-countrie |
| L302 | rule: e302-a-generous-timeout-is-not-advice-it-i | ⚠️ "A generous `timeout`" is not advice, it is the load-bearing part: the Bash tool's DEFAULT is 120s, and a c |
| L303 | rule: e303-pass-an-explicit-multi-minute-timeout | Pass an EXPLICIT multi-minute `timeout` on anything that boots a server, runs a browser suite, or provisions — |
| L314 | rule: e314-state-the-precedence-in-the-brief-or | ⚠️ State the precedence in the brief, or every finder re-derives it. A dispatched subagent inherits `CLAUDE.md |
| L315 | narrative | Those collide, and nothing says which wins, so each finder decides for itself (reported by brand-identiy-creat |
| L319 | rule: e319-you-are-executing-task-n-of-the-fabrik-1, e319-you-are-executing-task-n-of-the-fabrik-2 | You are executing Task {N} of the fabrik-lib integration plan as an isolated subagent. ⏎  ⏎ ## Your assignment |
| L323 | narrative | # Example: Phase B with 3 parallel subagents ⏎ Agent( ⏎ description="Phase B Task 4 — audit-log vendor", ⏎ iso |
| L335 | narrative | Everything you paste into a dispatch prompt and everything a subagent prints back stays resident in your conte |
| L356 | narrative | One fix subagent for the whole findings list, not one per finding. Per-finding fixers each rebuild context and |
| L357 | rule: e357-batch-confirmed-findings-into-a-single | Batch CONFIRMED findings into a single fix dispatch; it re-runs the covering tests and reports results |
| L360 | narrative | The pool recording contract is kept below for re-enable |
| L390 | rule: e390-there-is-one-orchestrator-you-and-one | There is ONE orchestrator (you) and ONE level of coder worktrees: dispatch every parallel phase's subagents as |
| L481 | rule: e481-doc-link-integrity-does-catch-a-missed | Doc Link Integrity DOES catch a missed one outside `docs/DECISIONS.md` (the ledger is no link source, W-e9c8a4 |


## Appendix C — reworded entries

| entry id(s) | baseline L | clauses | covered by a text phrase | labelled | class |
|---|---|---|---|---|---|
| e12-before-step-0-read-the-plan-s-phase-co | L12 | 2 | 2 | - | prose |
| e16-once-set-command-run-py-line-s-pinned | L16 | 1 | 1 | - | prose |
| e17-the-fabrik-review-at-a-phase-boundary | L17 | 4 | 4 | - | ban |
| e21-shape-detection-which-mode-runs-if-arg | L21 | 3 | 3 | - | prose |
| e24-a-spine-or-monolith-declaring-profile | L24 | 3 | 3 | - | prose |
| e25-in-the-main-checkout-a-small-plan-whos | L25 | 1 | 1 | - | prose |
| e33-a-validation-or-the-part-of-one-that | L33 | 7 | 6 | narrative×1 | prose |
| e34-a-spec-that-places-it-before-the-build | L34 | 2 | 2 | - | prose |
| e39-acquire-the-scope-lock-this-is-what-le | L39 | 1 | 1 | - | prose |
| e43-the-operator-s-re-invocation-is-the-au | L43 | 2 | 2 | - | prose |
| e50-the-operator-rules-once-and-a-received | L50 | 6 | 6 | - | prose |
| e52-the-seven-governance-surfaces-changel | L52 | 5 | 4 | dup:236×1 | ban |
| e53-same-plan-lock-status-released-or-the | L53 | 3 | 2 | narrative×1 | prose |
| e59-a-lock-left-active-by-an-orderly-bloc | L59 | 3 | 3 | - | prose |
| e60-locks-are-in-repo-and-per-working-tree | L60 | 2 | 2 | - | prose |
| e80-critical-pre-flight-review-before-phas | L80 | 3 | 1 | narrative×2 | prose |
| e81-read-the-plan-adversarially-against-th | L81 | 1 | 1 | - | prose |
| e87-track-in-session-with-todowrite-create | L87 | 3 | 3 | - | prose |
| e109-i-judged-x-unnecessary-running-low-on | L109 | 7 | 7 | - | prose |
| e110-filing-the-context-excuse-as-blocked-c | L110 | 2 | 2 | - | prose |
| e111-if-a-remaining-phase-genuinely-deserve | L111 | 2 | 2 | - | prose |
| e112-post-compact-the-sessionstart-hook-aut | L112 | 2 | 2 | - | prose |
| e113-a-step-you-believe-is-genuinely-wrong | L113 | 4 | 4 | - | ban |
| e123-phase-reviews-run-as-parallel-subagent | L123 | 8 | 8 | - | ban |
| e127-re-run-the-phase-gate-after-each-fix-t | L127 | 2 | 1 | narrative×1 | prose |
| e129-fixes-are-the-least-reviewed-code-in-a | L129 | 2 | 2 | - | prose |
| e134-for-each-screen-the-phase-built-drive | L134 | 8 | 7 | narrative×1 | ban |
| e197-precondition-a-dispatched-coder-must-b | L197 | 3 | 1 | fragment×1, narrative×1 | ban |
| e201-the-probe-covers-the-lane-it-dispatche | L201 | 3 | 3 | - | prose |
| e212-an-epic-path-that-does-not-resolve-on | L212 | 2 | 2 | - | ban |
| e217-coder-runtime-per-complexity-all-five | L217 | 11 | 11 | - | ban |
| e220-concurrency-3-coders-when-more-tickets | L220 | 4 | 4 | - | prose |
| e241-ettw-07-is-provenance-the-epic-to-tic | L241 | 4 | 1 | narrative×3 | prose |
| e243-secrets-carve-out-a-diff-touching-secr | L243 | 6 | 5 | narrative×1 | ban |
| e254-without-it-the-dispatcher-s-only-doc-g | L254 | 2 | 2 | - | ban |
| e259-synced-surfaces-sync-once-at-finish-a | L259 | 3 | 2 | narrative×1 | ban |
| e265-dead-coder-procedure-native-recorded-p | L265 | 13 | 12 | narrative×1 | ban |
| e293-it-specifies-per-phase | L293 | 1 | 1 | - | prose |
| e301-if-a-step-is-too-slow-for-one-synchron | L301 | 2 | 2 | - | ban |
| e302-a-generous-timeout-is-not-advice-it-i | L302 | 2 | 1 | narrative×1 | prose |
| e303-pass-an-explicit-multi-minute-timeout | L303 | 2 | 2 | - | prose |
| e314-state-the-precedence-in-the-brief-or | L314 | 3 | 1 | narrative×2 | prose |
| e319-you-are-executing-task-n-of-the-fabrik-1, e319-you-are-executing-task-n-of-the-fabrik-2 | L319 | 55 | 53 | fragment×2 | ban |
| e357-batch-confirmed-findings-into-a-single | L357 | 2 | 2 | - | prose |
| e390-there-is-one-orchestrator-you-and-one | L390 | 1 | 1 | - | prose |
| e481-doc-link-integrity-does-catch-a-missed | L481 | 2 | 2 | - | prose |

