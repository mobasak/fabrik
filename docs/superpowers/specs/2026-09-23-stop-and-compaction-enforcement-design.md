# Premature stops and compaction survival — the stop bar, the decision block, and state that survives a compact

**Status:** CONVERGED — `/fabrik-spec-review` 2026-09-23, five passes on the review-loop workflow (round 1 partitioned by section; later passes the round-1 slice owners over the fix diff plus one hop), closed under the scope-growth stop on a quiet fourth pass at md5 `d121c165`, plus a fifth pass on the committed text that re-stated the two slices the fourth omitted; awaiting the operator's design approval.
**Review:** 38 → 12 → 6 → 0 → 0 confirmed (own-fix 0 → 9 → 6 → 0 → 0); four own-fix candidates of the fourth pass RECORDED to `docs/STRATEGIC_BACKLOG.md` as inputs the plan must take (§ Review — Pass Ledger).
**Profile:** delta — every Intake Inventory item maps to code that exists today: the Stop hook's stall lane (`.claude/hooks/final_gate_stop.py:1296-1756`), the SessionStart hooks (`.claude/settings.json`, `session_orient.py`, `scripts/thread_anchor.py`), the two CLAUDE.md contracts' operator-decision bar (`CLAUDE.md` § FINAL OUTPUT, D-054). No new component; `## Personas`, `## Lifecycle` and `## Intake Inventory` are written in full because the delta adds a new automated consumer (the compact-time reconstructor) and changes what every agent in ~46 repos may end a turn on.
**Owner:** infra (the unnamed hub window). **Date:** 2026-09-23.
**Emitted by:** `/fabrik-spec`, the first measured chain through the rebuilt commands (`docs/reference/command-loop-performance.md` § 5.3).

## Personas

**Primary — the operator, in their own words:** *"most of the time, i dont understand why they ask and what they ask to, and spend time to understand."* The operator is the RECEIVER of every stop. Their loop today, counted, for one false stop:

1. read the agent's final message, 2. find what is being asked, 3. work out whether it is theirs to decide, 4. discover the answer was already in the plan/rules/ledger, 5. type "proceed" (or explain why the agent should not have asked), 6. wait for the agent to pick the work back up.

**Frozen STEP BUDGET after this build: 0 steps for a derivable next step** (the agent continues; the operator is not involved) and **2 steps for a legitimate decision** (read one DECISION block that says what, why-yours, the options with their consequences and a recommendation · answer it). A downstream contract that adds a step forces a budget bump and says why.

**Other personas, each holding a named duty:**
- **The agent** (every interactive Claude Code session on the box — hub windows, ~46 project repos, fabrik-lib) — holds the duty to continue derivable work, to write a DECISION block when it legitimately needs the operator, and to act on the post-compact state block. It is the one being enforced against.
- **The Stop hook** (`.claude/hooks/final_gate_stop.py`, automated, fleet-synced) — holds the DEFERRAL check and parses the DECISION block. It blocks an end-of-turn that hands a derivable step to the operator, with the existing 3-attempt warn-through (`CAP = 3`, `:40`; `decide_stall`, `:1296`).
- **The compact-time reconstructor** (the existing `thread_anchor.py line --hook` SessionStart call, branching on `source=compact`, automated, fleet-synced) — holds the duty to inject the state that cannot go stale: the live run record, the last `NEXT:` line, an open DECISION block, and this session's own unpushed commits and dirty files.
- **`thread_anchor.py`** (automated) — keeps its NEXT harvest, adds the DECISION-block harvest (cleared at the next UserPromptSubmit), and folds anchors older than 72 h into one line instead of printing each.
- **The Claude Code summarizer** (the harness, automated) — reads the `# Compact instructions` section of the root `CLAUDE.md` (documented, § External dependencies) and is told what a summary must preserve.
- **The kaizen event stream** (`scripts/sysadmin/kaizen_events.py`, automated) — records every deferral block, warn-through and DECISION block with its ground, so the fire rate and the ground distribution are measured, never assumed.
- **Sibling sessions and the daily pipeline** — headless (`entrypoint: sdk-cli`) sessions have no operator to defer to; the deferral check does not apply to them (§ Chosen approach, scope).

Every mechanism below traces to one of these.

## Intake Inventory

| I# | Item (anchored to the operator's words, 2026-09-23) | Disposition | Where |
|---|---|---|---|
| I1 | *"agents are not compacting their chat mostly"* | IN — as a CHANGED item: an agent cannot run `/compact` (user-typed, or the harness's auto-compact; no tool or hook field lets a model request it — § External dependencies E3). What CAN be enforced is WHEN the harness compacts (the window setting) and that compaction loses nothing. | § Chosen approach C3, C4 |
| I2 | *"stop prematurely for asking something they should not ask"* | IN | § Chosen approach C1 |
| I3 | *"we need to enforce compacting where necessary"* | IN — the fleet auto-compact window (C4), measured first: sessions today compact at a median 1,001 K (auto) / 858 K (manual) tokens | § Chosen approach C4 |
| I4 | *"prevent this premature stops"* | IN | § Chosen approach C1, C2 |
| I5 | *"they must record important information so that compacting will not cause them to forget or diverge from the previous tasks"* | IN — as RECONSTRUCTION from records that cannot go stale, supplemented by the summarizer's instructions; agent-written notes are the supplement, never the source | § Chosen approach C3 |
| I6 | *"agents keep doing this by saying operator decision where there is nothing to decide, all inputs there, all rules there, all specs/plans there. and they make this an excuse to stop"* | IN | § Chosen approach C1 (the `NEXT:` line is one of the deferral shapes) |
| I7 | *"i dont understand why they ask and what they ask to, and spend time to understand"* | IN — the DECISION block: what, why it is yours (the ground), the options with what each changes, the recommendation, in plain words | § Chosen approach C2 |
| I8 | Session: "measure first" (my proposal, approved "yes, yes") | IN | § Why this exists (the measurement) |
| I9 | Session: verify from the docs whether hooks can shape compaction | IN | § External dependencies E1–E6 |
| I10 | Session: on `source=compact`, reconstruct state from durable records (run record, last `NEXT:`, commits, dirty files, pending decision) | IN — all five, dirty files included: no documented post-compaction re-injection of git status exists, and the session-start git status is a snapshot | § Chosen approach C3 |
| I11 | Session: the OPEN THREADS block shows 500 h+ stale anchors | IN — as CHANGED: anchors older than 72 h are folded into one line, never expired, because expiry would drop a standing thread paused behind tangents | § Chosen approach C3 item 5 |
| I12 | Constraint: the stall detector's precision-first design and its 3-attempt release valve stay | IN | § Constraints |
| I13 | Constraint: `.claude/hooks/` and `CLAUDE.md` are governance-sync paths — fleet-wide | IN | § Shape / infra; § Validation (the forced sync) |
| I14 | The operator ruling of 2026-09-22 — *"do not act without asking me"*; a yes covers the step it answers | IN — it is the SCOPE ground (G3) the DECISION block names; minted as a D-row with this spec (it has none today) | § Chosen approach C2; § Decisions taken |
| I15 | This run is the first measured chain through the rebuilt commands (§ 5.3) | OUT-OF-SCOPE of the spec's content — measured in this run's FEEDBACK line and a § 5.3 progress line in `docs/reference/command-loop-performance.md` | the close of this run |
| I16 | The git-output decoder chain (D-311) is the second measured chain | OUT-OF-SCOPE — its spec is CONVERGED and awaits design approval | `docs/superpowers/specs/2026-09-19-enforcement-git-decoder-design.md` |
| I17 | Found while running this chain: the Stop hook's run-record cause blocks a turn that ends while a dispatched background Workflow or Agent is still running (hit 3 times in this spec-review's round 1; 1,379 `cause=run-record outcome=warned_through` events in the 35-day stream (`stop-events-2026-09-23.json`)). A legitimate WAIT is read as abandonment — the mirror of this spec's problem | OUT-OF-SCOPE — a false BLOCK, not a premature stop; its own change | `docs/STRATEGIC_BACKLOG.md` row (written with this spec's CONVERGED commit) |

Intake: 17 items — 14 IN (two as CHANGED, I1 and I5), 3 OUT-OF-SCOPE (each named), 0 ASK.

## Goal

An agent ends its turn only when its work is done or a human is genuinely needed. When a human IS needed, the operator can answer in two steps without reconstructing the context. A compaction, automatic or manual, never costs the agent its place in the task.

## Why this exists (measured 2026-09-23, before any mechanism — the FIX DIRECTIVE's step 1)

**Method.** A read-only miner (`docs/reference/research/2026-09-23-stop-compaction/mine.py`) walks every top-level transcript on the box: 5,881 files under `~/.claude-fleet/active/projects/*/`, subagent transcripts excluded, entries from 2026-08-09 (the stall lane's first full week) to 2026-09-23. A TURN END is the last assistant text before the next real operator message. The run gives 25,412 interactive turn ends and 607 headless ones. Each shape is reservoir-sampled uniformly across the whole population (seed 20260923), and the judged samples are drawn from those reservoirs (seed 923). Three Sonnet seats judged them per record against the D-054 grounds. The per-record verdicts are committed next to the miner (`verdict-opdec.json`, `verdict-context.json`, `verdict-compact.json`, each quote ≤ 100 chars). `derive.py` recomputes every count below (§ Derivations). The raw transcript samples stay out of git because transcripts can hold secrets; `samples.sha256` pins them.

| Measure | Count | Denominator | Note |
|---|---|---|---|
| Turn ends whose last `NEXT:` defers to the operator (the miner's `OPDEC` vocabulary) | 5,442 (21%) | 25,412 interactive turn ends | fabrik 2,180 · web-ecommerce-factory 739 · youtube 652 · fabrik-lib 582 · trade-intelligence 279 |
| Of a uniform random 80 of those, judged FALSE (the next step was derivable) | 26 (32.5%) | 80 | ≈ 1,770 false stops in 45 days box-wide. The other 54 named a real ground: 30 gate · 17 owned · 7 underivable. In 25 of the 26 the operator's reply shows the stop was unneeded |
| The FALSE shapes | say-the-word / "on your go" 13 · menu 6 · a bare "awaiting your reply" after finished work 7 | 26 | the first two (19) are premature stops and D1–D3's target. The third is an end after DONE work, not a premature stop, and D1 excludes the bare footer by construction (C1) |
| Context-excuse stops (a random 40 of the 178 full-text regex hits, judged on a 1,500-char tail) | 8 real excuses · 2 advice · 9 false matches · 21 not visible in the tail | 40 | every real one left the agent's OWN work undone ("then a fresh session finishes the converge"). The false matches are house vocabulary: an MCP roster reload, a quota "session window", a quota hold |
| The operator's standing ruling on fresh sessions | *"i never use a fresh session, i always continue existing sessions, that is why i have developed session-recall and that is why we use /compact command."* | — | found by the first context judge in the 2026-08-10 transcript. It has no D-row, so this spec mints one |
| Compactions | 547: 257 manual (median 858 K tokens before), 290 auto (median 1,001 K) | 45 days | the operator compacts by hand, late; nobody compacts early |
| Post-compaction continuity (a random 40, judged) | auto 13 continued · 2 diverged · 1 unclear of 16 · manual 15 continued · **8 diverged** · 1 unclear of 24 | 40 | **0 of the 12 with a live command run diverged, against 9 of the 25 without one.** The divergences started work the summary said needed the operator's word, redid finished work, or dropped a named item |
| The Stop hook's own record of stall blocks (`cause=promise-stall`) | 88 blocked + 6 warned-through | every `stop_block`/`stop_pass` event in the box's kaizen event stream (it starts 2026-08-19, so 35 days), snapshotted 2026-09-23 as `stop-events-2026-09-23.json` | against 4,907 clean passes in the same window; the stall lane never sees a deferral (§ Derivations) |

**What breaks today, concretely.**
1. About one in three operator-deferrals hands the operator a step the agent could derive. The operator must read the message, find the question, work out whether it is theirs, and answer "proceed". That is 5 of the 6 steps in § Personas' loop, repeated ~40 times a day across the box.
2. The legitimate two-thirds are free prose, so each still costs the operator a reconstruction ("i dont understand why they ask and what they ask to").
3. Nothing enforces the bar. D-054 is prose, and the hook knows deferral words only as an exemption.
4. A compaction without a live command run diverges about one time in three (9/25). Nothing re-anchors the session to its last `NEXT:`, its open decision, or its uncommitted files. A live run already re-anchors it, because the Stop hook's run-record block does: 0 divergences in 12. The prompt-time thread list, the one mechanism meant for this, shows anchors up to 578 h stale beside the one useful `NEXT (latest)` line.

**How the chosen approach resolves exactly that.**
- A deferral stops being a free exit. Either the agent continues, or it writes one fixed-shape DECISION block the operator can answer cold.
- After every compaction, the agent is handed the records that cannot go stale, which gives every session the re-anchor a live run gives today.

## Derivations

Every judged count above is re-derived from the committed files in `docs/reference/research/2026-09-23-stop-compaction/`. The judged DRAW is reproducible: `draw.py` re-draws the samples from the reservoirs of the 2026-09-23 miner run (seed 923) and matches `samples.sha256` byte for byte. The MINE is not re-runnable to the same bytes, because it reads the live, growing transcript tree with no upper time bound. The reservoir files of that run stay box-local next to the raw samples, and a re-run from scratch is a new measurement (A-O37). The stall-block counts are a snapshot of the box-local kaizen event stream (`stop-events-2026-09-23.json`, aggregate counts only):

```
$ python3 docs/reference/research/2026-09-23-stop-compaction/derive.py
opdec 80 {'FALSE': 26, 'OWNED': 17, 'GATE': 30, 'UNDERIVABLE': 7}
opdec FALSE shapes {'say-the-word': 13, 'menu': 6, 'awaiting-nothing': 7} reply_unneeded YES 25
context 40 {'STOP-EXCUSE': 8, 'FALSE-MATCH': 9, 'NOT-VISIBLE': 21, 'ADVICE': 2}
compact auto 16 {'CONTINUED': 13, 'DIVERGED': 2, 'UNCLEAR': 1}
compact manual 24 {'CONTINUED': 15, 'DIVERGED': 8, 'UNCLEAR': 1}
compact run_live {('NO', 'CONTINUED'): 16, ('NO', 'DIVERGED'): 9, ('UNKNOWN', 'CONTINUED'): 1, ('YES', 'CONTINUED'): 11, ('UNKNOWN', 'DIVERGED'): 1, ('YES', 'UNCLEAR'): 1, ('UNKNOWN', 'UNCLEAR'): 1}
opdec repos {'-opt-fabrik': 40, '-opt-web-ecommerce-factory': 12, '-opt-fabrik-lib': 7, '-opt-trade-intelligence': 6, '-opt-youtube': 6}
stop events {'stop_pass|None|clean': 4907, 'stop_block|promise-stall|blocked': 88, 'stop_block|promise-stall|warned_through': 6}
```

The D4 prototype (C1's D4 row), run over the judged context records' deciding quotes and over seven ordinary sentences that merely mention a session or a context:

```
$ python3 docs/reference/research/2026-09-23-stop-compaction/d4_probe.py
STOP-EXCUSE 6/8 fire ['C01', 'C15', 'C22', 'C25', 'C29', 'C34']
FALSE-MATCH 0/9 fire []
ordinary prose 0/7 fire
```

## What exists today (grounded)

- **The stall lane** — `.claude/hooks/final_gate_stop.py`. `_detect_stall` (`:1631`) scans the last 600 chars of the final message for five shapes: a first-person promise with an action object (`_PROMISE_VERB_RE`, `:1321`), a passive obligation (`_OBLIGATION_RE`, `:1346`), a continuation claim (`:1377`), a `NEXT:` naming a numbered round (`_NEXT_ROUND_RE`, `:1388`) and a permission question (`_PERMISSION_RE`, `:1335` — `want me to|shall I|should I|would you like me to|do you want me to … ?`). **The permission shape blocks ONLY mid-run** (`_midrun_marker`, `:1566` — an active plan lock or an UNCHECKED review row the session authored; `:1744-1751`). **Nothing fires on a message whose only stall is a deferral**: a `NEXT: operator decision — …` line, an `(a)/(b)` menu, "let me know which…", "which do you prefer?", or a context excuse matches none of the five shapes, so it reaches `decide_stall` (`:1296`) as "no stall". The deferral vocabulary exists only as an EXEMPTION (`_GATE_EXEMPT_BARE_RE`, `:1422`, which since 2026-08-29 must share a line with a `_GATE_CLASS_RE` class, `:1433`), never as a trigger.
- **The warn-through** — `CAP = 3` (`:40`); `decide_stall` releases on the 4th consecutive blocked stop and emits `stop_block … outcome=warned_through`. There are six such counters (`_read_counters`: `g, c, s_att, p_att, r_att, v_att`), each warning through independently and then handing on to the next cause, so a session tripping several causes can reach Claude Code's own 8-block override (E1) before any one of ours releases.
- **The final message is read from the transcript** (`_final_turn`, `:1518`, 2 MB tail), with a skip-textless workaround in `_final_message_text` because the "harness can fire Stop before the final text entry is flushed" (`:1509-1512`). The docs name this exact race and the fix: `last_assistant_message` in the Stop input (E1). The hook's own header claims *"Claude Code exposes no stop_hook_active flag, verified against the docs"* (`:17`) — **false today** (E1).
- **The contract's bar** — `CLAUDE.md` § FINAL OUTPUT, "`NEXT: operator decision` HAS A BAR" (D-054, 2026-08-31): three grounds, menus and self-reliability never legitimate. Prose only; § Why this exists measures what prose bought.
- **Compaction** — no project `PreCompact` hook; the user-level `PreCompact`/`PostCompact` hooks only write/clear the sound mesh's `compacting` marker (`docs/workstation/hooks-index.md:98-99`, operator-owned, not touched here). `session_orient.py` runs on `source=compact` but emits the generic ORIENT block and skips the self-watch arm (`:424-429`); nothing injects the live command run record (`command_run.py`'s state under `~/.claude/state/command-runs/` — no hook reads it at SessionStart; `grep -l 'command_run\|command-runs'` over `.claude/hooks/*.py` hits `final_gate_stop.py` and `quota_stop.py` as readers and `session_orient.py` only in two comments). The root `CLAUDE.md` has no `# Compact instructions` section.
- **Thread anchors** — `scripts/thread_anchor.py` harvests every `NEXT:` at Stop and re-injects ≤ 4 anchors plus `NEXT (latest)` on every prompt and on SessionStart; an anchor closes only by `done --match` (`:1-30`). There is no expiry, so this session's block shows anchors 95 h, 518 h, 567 h and 578 h old. The `NEXT (latest)` slot is the one piece that worked across this session's compaction.

## The delta — Chosen approach

Five pieces (C1–C5). Each names the persona that holds it.

### C1 — DEFERRAL, a new shape in the stall lane (the Stop hook)

`_detect_stall` (`:1631`) already returns one of six causes: the five pattern shapes (promise · obligation · continuation · `NEXT:`-round · permission) and the incomplete FINAL OUTPUT block. It gains a seventh, DEFERRAL, checked after the others. DEFERRAL shares the stall lane's counter slot (`s_att`), so it adds no new counter and never lengthens the chain of blocks. It keeps the lane's protections:
- a quoted or in-quote match is skipped;
- `BLOCKED:` exempts globally;
- the `decide_stall` counter warns through at `CAP = 3` (K1).

It does NOT take the dispatch-kept exemption the pattern shapes have (`:1712-1751`). A turn that dispatched work and then ends on "which do you prefer?" still hands the operator a question. The exception is the bare wait footer, which D1 excludes.

It fires when the tail of the final message DEFERS to the operator in one of four shapes:

| Shape | Matches (red fixtures, drawn from the judged sample) | Must NOT match (green fixtures) |
|---|---|---|
| D1 deferral `NEXT:` | a `NEXT:` line carrying ONE closed vocabulary, `_DEFER_RE`. It is a new constant, defined once and imported by the miner so the baseline and the detector count the same set (A-O18): operator decision · your call · your go / on your yes·word·go·approval · say the word · if you want · you decide / yours to decide / yours to choose · await(ing) your or the operator's (decision · go · approval · call · word · direction) · human gate · operator-gated · yours to run | `NEXT: none — terminal` · `NEXT: /fabrik-spec-review <path>` · the contract's conversational footer: `NEXT:` + `awaiting your reply` with nothing after it, which is excluded by construction because `_DEFER_RE` names what is awaited and "reply" is not in the list |
| D2 menu | an `(a) … (b)` / `option A … option B` / numbered-choice list in the tail that hands the choice to the operator | a list of FINDINGS or STEPS the agent reports as done or dispatched |
| D3 offer-to-act | "say the word / say X and I'll …", "want me to …?", "shall I …?", "should I …?", "let me know if/which/whether …", "which do you prefer …?", "do you want …?" | a question inside a quote or a code span; a question followed in the same message by its own answer |
| D4 context excuse | the agent HANDS ITS OWN WORK to a later session: `(in\|open\|start\|use\|needs\|wants\|deserves\|requires) a (fresh\|new\|clean\|separate) (session\|window\|context\|chat)` (unless followed within 60 chars by MCP · roster · reload · quota · 5h · weekly · reset) · `a/the (fresh\|new…) session (finishes\|runs\|should\|must\|will\|checks\|does)` · `context (is) getting long/full/low/tight` · `compact first` · `this session is/has been (running) long`. The prototype and its runs are in § Derivations (`d4_probe.py`: 6 of 8 judged real excuses fire, 0 of 9 judged false matches, 0 of 7 ordinary sentences) | "quota window", "session window resets", "session-recall", "a fresh window would be needed for MCP-dependent work", "SessionStart fires on a new session", "the new context from the logs", "a fresh session is never the remedy" |

**The one behaviour that moves.** Today `_PERMISSION_RE` (`:1335`) blocks only mid-run: its loop returns a stall only under `_midrun_marker` (`:1744-1751`). D3 subsumes that shape and blocks it OUTSIDE a run too. That is the point of the change. `_PERMISSION_RE`'s loop is replaced by D3, never run beside it. The four other pattern shapes and the incomplete-block check keep their behaviour and their per-line exemption.

**The exemption is a well-formed DECISION block (C2), and otherwise only `BLOCKED:`.** Neither the per-line class exemption (`_line_exempt` with `_GATE_CLASS_RE`) nor named-gate wording (`_GATE_EXEMPT_NAMED_RE`: gate 1/2, human gate, plan approval, deploy approval, yours to run, operator-gated) exempts a deferral, in any of D1–D4. For the DEFERRAL shape alone this supersedes the hook's "human-gate wording is exempt" (K2, Decision 2), for two reasons: the operator wants the legitimate stops legible too (I7), and a named-gate phrase that exempts on sight is the cheapest way past D1 without producing the outcome. The contractual gates themselves (the spec approval, plan approval, `/fabrik-deploy`'s Gate 2, a release) are stated as `ground: gate` blocks. The five pattern shapes keep K2's exemptions unchanged.

**Scope.** Interactive sessions only. A session is headless when `CLAUDE_MESH_HEADLESS=1`, or when the transcript's last user entry carries `"entrypoint": "sdk-cli"`, the value the miner used to separate the 607 headless turn ends. No hook input field carries the entrypoint; the raw `hooks.md` has 0 occurrences.

**Inputs.**
- The final message comes from `last_assistant_message` in the Stop input when present. That is the documented fix (E1) for the transcript race `_final_message_text` works around (`:1509-1512`). The transcript read stays as the fallback, so an older harness behaves as today.
- The header claim that Claude Code exposes no `stop_hook_active` flag (`:17`) is corrected to cite E1.
- The claim that ours always fires before the platform's 8-block override is NOT made. The hook's six independent counters (`_read_counters`: `g, c, s_att, p_att, r_att, v_att`) chain, so a session tripping several causes can reach the platform's 8 first. DEFERRAL adds no counter, so it cannot make that worse.

**The block reasons.** DEFERRAL's reason is one paragraph:
- the shape matched, with its snippet;
- "the next step is yours if the plan, the rules, the ledger or the code decide it — do it now";
- "if a human is genuinely needed, end with a DECISION block (CLAUDE.md § FINAL OUTPUT)".

The EXISTING stall reason (`:2133-2140`) also changes: it tells agents to "name their human gate explicitly (design approval, Gate 2, operator decision, or a formatted BLOCKED: escalation)". Followed as written, every one of those phrases now trips D1. It is rewritten to name only the two exits that clear DEFERRAL: a `ground: gate` DECISION block, or `BLOCKED:` (C-O7, C-O10).

### C2 — the DECISION block (the one legitimate way to hand the operator a decision)

Its home is `CLAUDE.md` § FINAL OUTPUT in both contracts, and the hook's reason points there. `templates/governance/CLAUDE.md` carries § FINAL OUTPUT TWICE at the base SHA (`:629` and `:672`, and "HAS A BAR" three times). The build edits every copy and routes the duplication itself to a backlog row. The shape:

```
DECISION NEEDED (ground: gate|underivable|owned)
- Question: <one plain sentence, no internal ids without their meaning>
- Why it is yours: <gate → the class; underivable → what changes if the answer differs, and `searched:` what came back silent; owned → `asked:` the operator's earlier question still unanswered, or `scope:` the line of the operator's request this step goes past>
- Options: <A — what changes if chosen> · <B — what changes if chosen>
- Recommendation: <A or B, and the one-line reason>
```

The three grounds are D-054's, kept whole:
- (1) a contractual human gate → `gate`.
- (2) the answer materially changes the work AND cannot be resolved from the artifacts, code or ledger → `underivable`. Both halves are required fields.
- (3) the operator already owns that decision this turn and has not yet answered → `owned`, in one of two forms: `asked:` quotes the operator's own open question (D-054 ground 3, word for word), or `scope:` quotes the line of the operator's request that this step goes past (the 2026-09-22 ruling, D-row'd with this spec).

CLAUDE.md carries two short examples beside it (graft G-c): one legitimate (`ground: gate`, a deploy) and one refused (an (a)/(b) ordering of two agreed tasks).

**Where the hook looks.** Only the LAST `DECISION NEEDED (ground:` heading in the whole final message counts, and only outside a fenced code block. It is read with the four lines that follow it, wherever the block sits. The seven-line FINAL OUTPUT block that must close the message (≈ 300+ chars) pushes the block out of the 600-char tail the pattern shapes read, so the parser cannot use that window. A quoted example inside a fence never exempts.

**The checks:**
- `gate` needs a token from a new closed list, `_DECISION_GATE_RE`: deploy · destructive · irreversible · spend (real money, a `$` amount) · cross-repo · publish · credentials · design approval · plan approval · Gate 1/2 · production data. It is NOT `_GATE_CLASS_RE`, which lacks `credentials` and `design approval` and accepts the house words `policy`, `cost` and `quota` (A-O2, A-O3; executed on a copy of the hook at 989ad9f11).
- `underivable` needs a `searched:` clause naming at least one path, command or ledger id (graft G-b), plus what changes.
- `owned` with `scope:` is REFUSED while the session's command run record is `running`, read the way `_run_record` reads it (`:519`): the invoked command already grants its own scope. `owned` with `asked:` is allowed inside a run, because the operator's own unanswered question is D-054 ground 3 whatever is running. The hook VERIFIES it: the `asked:` quote (at least 12 characters) must occur verbatim in a real operator message of this session's transcript (a user entry that is not a tool result, a compaction summary or a hook-injected block). An invented question fails as malformed (A-O39). `_midrun_marker` is NOT the predicate: it also arms on any session-authored review doc with `| UNCHECKED` rows (`:1586-1589`).

A malformed block (a missing field, an unknown ground, a `gate` with no listed class, `owned` with neither `asked:` nor `scope:`, or `owned` with `scope:` inside a live run) is itself a DEFERRAL match, and the reason names what is missing. The turn's `NEXT:` reads `NEXT: operator decision — see DECISION NEEDED above`, and the well-formed block exempts it.

### C3 — compact-time reconstruction (records that cannot go stale)

The existing SessionStart entry already runs `thread_anchor.py line --hook` for every source, with an empty matcher, and it already parses the payload (`main`, `:241-251`). No settings entry is added: when the payload's `source` is `compact`, `line` prints a `## ⏮ WHERE YOU ARE` block INSTEAD of its usual block, so nothing prints twice (A-O10). The block is built only from records:
1. **The live command run** — the session's record whose `state` is `running`: command, `phase c/t (title)`, round, terminal and `--surface`. The Stop hook's instruction goes with it: run it to that terminal condition.
2. **The last `NEXT:`** before the compaction (`last_next`, already harvested).
3. **An open DECISION block.**
   - Harvested at Stop beside `last_next`, but ONLY when the Stop hook accepted it. The hook's harvest call runs before its block decision (`final_gate_stop.py:1825-1852`), so the hook parses the block first and passes its verdict to the harvest. A refused or malformed block is never stored (C-O8's twin, A-O30).
   - OPEN until the next UserPromptSubmit whose `prompt` does not begin with `/`: no slash command, built-in or custom, counts as the operator's answer. The UserPromptSubmit payload carries `prompt` (raw `hooks.md`, § UserPromptSubmit input), and whether a typed built-in such as `/compact` or `/context` fires UserPromptSubmit is undocumented, so the clear skips every slash command either way (A-O32, A-O38). The prompt-time `line --hook` call re-harvests the previous turn's message (`thread_anchor.py:273-278`), and that pass never stores a DECISION block: it only clears (C-O8). A compaction summary never passes through UserPromptSubmit, so it can never read as the operator's reply (A-O12).
4. **This session's unpushed commits and dirty files** — scoped to the files the session itself authored, the floor the Stop hook's push check already uses (`_ahead_of_upstream` with `_this_sessions_edits` and `_baseline_floor`, `:677`, `:1946`). A branch-wide `@{u}..HEAD` would show a sibling's commits as this session's (A-O11). Dirty files are included: no documented post-compaction re-injection of git status exists (C-O2), and the session-start git status is a snapshot. Bounded to 10 of each, 2 s timeouts, fail-silent.
5. **Open threads, collapsed.** Anchors are NOT expired: a standing thread paused behind days of tangents in one long session is the founding case `thread_anchor.py` exists for (A-O13), and the operator never opens fresh sessions. Instead, `line` shows anchors younger than 72 h in full and folds the older ones into one line: `N older thread(s), oldest <age> — close with thread_anchor.py done --match <substr>`. The 578 h wallpaper becomes one line, and nothing is lost.

### C4 — the summarizer's instructions (both contracts)

A `# Compact instructions` heading goes in the root `CLAUDE.md` and in `templates/governance/CLAUDE.md` (E5; the root CLAUDE.md is re-injected from disk after compaction, E4). It holds five lines telling the summary to carry, verbatim:
- the live command and its terminal condition;
- every file path and plan/spec path being worked;
- every operator ruling of the session, in the operator's words;
- the pending DECISION block, if any;
- the last `NEXT:`.

It also says: never summarise a pending operator question as settled.

### C5 — the compaction window (enforce compacting where necessary)

A fleet `autoCompactWindow` is NOT set in this build. Measurement first:
- Today's sessions compact at a median ~1 M tokens (auto) and ~858 K (manual). The cost of a long context is quota, per turn.
- The cost of compacting early is detail lost, a summarization pass, and a cache re-write.
- Neither has been measured against the other on this box.

V5 correlates `preTokens` (the transcript's `compact_boundary` record, which the miner already reads) with the judged post-compaction continuity. A window is set only on that measurement, as its own D-row. Until then, "where necessary" is the harness's own auto-compact plus C3 making every compaction survivable. The operator's `/compact` habit is unchanged.

### The judge panel (D-363) — how C was chosen

Three Sonnet seats each ranked the approaches from the same brief, blind: A (a Haiku `type: "prompt"` Stop hook on every stop), B (prose contract only) and C (this design). They got alphabetical order at equal depth, with no recommendation. The brief is `approaches-for-panel.md` in this run's scratch.

**Result: 3 of 3 ranked C first.**
- A failed precision, spend and the cobra check with all three judges. It is nondeterministic, blind to run and plan state, and costs one model call on each of ~25 K stops per 45 days.
- B failed quality and set-and-forget with all three: it is the status quo the false-stop share was measured under. The panel saw a first sample's 35%, drawn from two repos only. The uniform re-sample reads 32.5% (§ Why this exists), which changes no verdict: each judge ranked on mechanism, not on the rate.
- C's named risks were (i) the regex's recall gap and (ii) a DECISION block used as wallpaper, meaning a valid block with a false ground.

**Grafted from the panel:**
- **(G-a) a sampled offline audit** (all three judges). A model judge is kept, but only over a sample, never as the live gate. See V6.
- **(G-b)** `underivable`'s `searched:` clause must name a path, command or ledger id (judge 1). The audit cross-checks it against the turn's tool calls.
- **(G-c)** one good and one bad example beside the DECISION format in CLAUDE.md (judge 1). Kept to two short blocks.

No split verdict remains to carry to the approval.

## Contract deltas

- **`CLAUDE.md` + `templates/governance/CLAUDE.md` § FINAL OUTPUT** (every copy — the template carries the section twice at `:629` and `:672`). The "`NEXT: operator decision` HAS A BAR" paragraph gains the DECISION block (C2) with its two examples. D-054's three grounds are kept whole and mapped to the block's tokens (gate · underivable · owned, C2). The paragraph's prose about menus and self-reliability shrinks to one sentence, because the hook now enforces it (lean without loss, D-331: no rule is dropped, the story is). The `operator-decision-bar` bullet under § UNIVERSAL governance markers (`CLAUDE.md:383`) keeps its anchor and names the block. The existing stall reason string (`final_gate_stop.py:2133-2140`) is rewritten per C1.
- **Both contracts gain `# Compact instructions` (C4)** and one sentence: "Context is never a reason to stop, and a fresh session is never the remedy (operator ruling, D-row below)."
- **The command corpus.** Every command source whose own text ends at a human gate (the design approval in `/fabrik-spec-review`, plan approval, `/fabrik-deploy`'s Gate 2, `/fabrik-release`'s hand-off) states that gate as a `ground: gate` DECISION block. The build finds the set with one grep over `commands/_sources/` for the gate vocabulary and edits each, rendered and synced before the hook (§ Lifecycle, Adoption).
- **`/opt/fabrik-lib/CLAUDE.md`** is HAND-MAINTAINED on fabrik-lib's side (its line 1: "HAND-MAINTAINED since 2026-08-12 … Edit THIS file"). Editing it from the hub is a cross-repo HARD STOP, so the exact text of both deltas goes by mail to fabrik-lib, for its agent to apply.
- **No data contract, no UI contract.** The kaizen event stream gains fields (`cause=deferral`, `shape=D1..D4`) and a new `decision_block` event carrying `ground`. The new event is REGISTERED in `kaizen_events.EVENT_TYPES` (`scripts/sysadmin/kaizen_events.py:114-131`); an unregistered type makes `emit()` warn on every emit (`:559-560`). `docs/workstation/kaizen-event-stream.md` lists them.

## External dependencies

Every fact below was fetched live on 2026-09-23 in this run. The raw `hooks.md` (331,285 B, HTTP 200) was curled by the orchestrator and grepped; the other rows came from `fabrik-researcher` seats' raw fetches (exa `web_fetch_exa` / firecrawl with `maxAge: 0`) and their verbatim quotes.

| # | Fact the design rests on | Verbatim | Source (fetched 2026-09-23) |
|---|---|---|---|
| E1 | The Stop input carries `stop_hook_active` and `last_assistant_message`. Read the latter, not the transcript. Claude Code's own cap is 8 consecutive blocks. `decision: "block"` + `reason` makes Claude continue with the reason. | "Hooks that need the final assistant text of the current turn should use `last_assistant_message` on Stop and SubagentStop instead of reading the transcript" · "Check this value or process the transcript to avoid blocking on a condition that will never resolve. Claude Code overrides the hook and ends the turn after 8 consecutive blocks." · "`reason` \| Required when decision is "block". Tells Claude why it should continue" | https://code.claude.com/docs/en/hooks (raw `hooks.md`, curl; firecrawl) |
| E2 | A SessionStart hook with the `compact` matcher runs on auto AND manual compaction. Its stdout is added to the compacted context. Its input carries `source` (and, on resume, `context_tokens`). | "Use a SessionStart hook with a compact matcher to re-inject critical context after every compaction." · "SessionStart hooks that match the `compact` source \| Claude Code runs them and adds their output to the compacted context" · `"source": "resume", … "context_tokens": 182340` | https://code.claude.com/docs/en/hooks-guide · https://code.claude.com/docs/en/context-window · raw `hooks.md` |
| E3 | Neither a hook nor the model can trigger compaction. PreCompact can BLOCK one, but cannot change its instructions (its `systemMessage`/`continue` are discarded). PostCompact receives `compact_summary`. | "Exit with code 2 to block compaction." · "Claude Code discards a PreCompact hook's systemMessage and continue fields." · "The compact_summary field contains the conversation summary generated by the compact operation." | https://code.claude.com/docs/en/hooks (firecrawl, two sections); absence = "not found in the PreCompact/PostCompact/Stop sections, the event table, context-window, hooks-guide" |
| E4 | After compaction the harness re-injects the project-root CLAUDE.md and unscoped rules, auto memory and invoked skill bodies. Hook-added context is summarized away. The live "What survives compaction" table has NO git-status row (re-fetched live by the round-1 researcher). | "Context that hooks added earlier \| Summarized with the rest of the conversation" · "Invoked skill bodies — Re-injected, capped at 5,000 tokens per skill and 25,000 tokens total; oldest dropped first." | https://code.claude.com/docs/en/context-window |
| E5 | The summarizer honours a `# Compact instructions` section of CLAUDE.md. `/compact <text>` takes one-off instructions. | "# Compact instructions\n\nWhen you are using compact, please focus on test output and code changes" · "`/compact Focus on code samples and API usage` tells Claude what to preserve during summarization." | https://code.claude.com/docs/en/costs |
| E6 | The auto-compact window is configurable: `autoCompactWindow` (setting, written by `/autocompact <size>`) and `CLAUDE_CODE_AUTO_COMPACT_WINDOW` (env). `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` only LOWERS the trigger percentage. Native-1M models compact at ~967 K by default. | "Compact earlier: run `/autocompact` with a token count, like `/autocompact 500k`, to set how full the context window gets before the automatic pass runs." · "Models running with a native 1M window, such as Sonnet 5, the Fable models, and Opus 4.7 and later on the Anthropic API, compact before the window fills, at about 967K tokens by default." · "the variable can't raise the threshold" | https://code.claude.com/docs/en/context-window · https://code.claude.com/docs/en/model-config · https://code.claude.com/docs/en/env-vars |
| E7 | `type: "prompt"` Stop hooks send the hook input to a model (Haiku by default) and return `{ok, reason, impossible}`. `ok: false` continues the turn with the reason. `/goal` is a user-typed, session-scoped wrapper over one, with no settings key. | "Send the hook input and your prompt to a Claude model, Haiku by default" · "the reason is fed back to Claude as its next instruction and the turn continues, unless the response also sets impossible: true" · "`/goal` is a session-scoped shortcut: you type a condition and it's active for the current session only." | raw `hooks.md` (curl) · https://code.claude.com/docs/en/goal |
| E8 | Field practice (both vendors): default to proceeding under uncertainty; persist state in durable files and git rather than in the conversation. | Anthropic: "If the user's intent is unclear, infer the most useful likely action and proceed, using tools to discover any missing details instead of guessing." · OpenAI: "Never stop or hand back to the user when you encounter uncertainty — research or deduce the most reasonable approach and continue." · Anthropic: "a claude-progress.txt file that keeps a log of what agents have done, and an initial git commit" | https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices (WebSearch → fetch) · https://developers.openai.com/cookbook/examples/gpt-5/gpt-5_prompting_guide (fetch) · https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents (exa search → fetch) |
| E9 | A forcing Stop hook must honour `stop_hook_active` / a release valve, or it collides with the platform cap. This failure is documented in the field. | "Stop hook (persistent-mode.mjs) never honors stop_hook_active — Claude Code's 9-block safety override fires on every persistence mode" · the Ralph plugin: "Always use `--max-iterations` as a safety net to prevent infinite loops on impossible tasks" | https://github.com/Yeachan-Heo/oh-my-claudecode/issues/3138 (WebSearch → fetch) · https://github.com/anthropics/claude-code/blob/main/plugins/ralph-wiggum/README.md (fetch) |
| E10 | A decision put to a human carries the options, a recommendation and the counter-argument. | "Three to four options with tradeoffs... Recommendation + counter-argument... The counter-argument is load-bearing. Without it, the recommendation is unfalsifiable." | https://github.com/ai-sdlc-framework/ai-sdlc/blob/main/ai-sdlc-plugin/skills/decision-rubric/SKILL.md (exa search) |

Recorded discrepancy: the Ralph README says the platform cap is 9 blocks, while the hooks page says 8. The design depends on neither number: DEFERRAL adds no counter (C1).

## Constraints (the constraints digest — every row a verbatim quote)

| # | Rule | Verbatim | Source |
|---|---|---|---|
| K1 | A block must never trap a session | "warn-through at the cap so a misfire can never trap the session." | `.claude/hooks/final_gate_stop.py:1300-1301` |
| K2 | Precision first (for the DEFERRAL shape the named-gate half is superseded by Decision 2; the five pattern shapes keep it) | "Precision over recall throughout — indeterminate parses fail open, human-gate wording is exempt" | `.claude/hooks/final_gate_stop.py:1313-1314` |
| K3 | Measure the fire rate before adding a check | "a detector that fires on legitimate patterns is wallpaper. Rejecting a mechanism after measuring is a valid, recordable outcome." | `CLAUDE.md:225-226` (§ THE FIX DIRECTIVE 5) |
| K4 | The cobra check | "the cheapest way to satisfy it without producing the outcome is written down IN THE SAME CHANGE" | `CLAUDE.md:228` |
| K5 | The three grounds | "`NEXT: operator decision` HAS A BAR … legitimate on exactly three named grounds" | `docs/DECISIONS.md` D-054 |
| K6 | Fleet reach | "**What you edit here ships fleet-wide**: a synced-surface commit distributes to ~46 repos" | `CLAUDE.md:10-11`; `.claude/settings.json`, `.claude/hooks/` are governance-sync triggers (`.pre-commit-config.yaml`, the `governance-sync` files-filter) |
| K7 | The operator's sound/mesh hooks are not touched | "Do not touch the sound system — diagnose READ-ONLY" | operator ruling (memory `feedback_dont_touch_the_sound_system`); the user-level PreCompact/PostCompact hooks are `claude-sound.sh`'s (`docs/workstation/hooks-index.md:98-99`) |
| K8 | Python hooks: typed signatures | "Use type hints for all function signatures" | `.windsurf/rules/core/10-python.md:160` |
| K9 | Docs: fenced code only | "**Fenced code blocks only** — never indented code" | `.windsurf/rules/core/40-documentation.md:243` |
| K10 | The review loop is fixed, never cut, capped or operator-gated | "ending itself in one to three passes — not removed, not thinned, not gated on the operator" | `docs/DECISIONS.md` D-330 |

## fabrik-lib verdict table

| Capability | Verdict | Why |
|---|---|---|
| Stop-hook deferral check | BUILD (extend the hub's own hook) | the stall lane lives only in `.claude/hooks/final_gate_stop.py`; fabrik-lib ships no hook machinery (`/opt/fabrik-lib/README.md` module table: application modules only) |
| Compact-time state reconstruction | BUILD (extend `thread_anchor.py` / a SessionStart branch) | same, box-local governance machinery |
| Not a `🆕 fabrik-lib candidate` | — | project-agnostic governance tooling is distributed by the hub's sync, not vendored |

## Shape / infra implications

No scaffold type, no `shape:` flags, no service, no port. The surface is fleet-synced governance: `.claude/hooks/final_gate_stop.py`, `.claude/settings.json`, `scripts/thread_anchor.py`, `CLAUDE.md` + `templates/governance/CLAUDE.md`. Every one is a governance-sync trigger or rides one, so the build ends in ONE forced sync (`scripts/sync_enforcement_to_projects.py --force`) after a clean `--dry-run`. `/opt/fabrik-lib/CLAUDE.md` is HAND-MAINTAINED on their side (§ Contract deltas), so its copy of the contract changes by mail to fabrik-lib, never by a hub edit.

## Documentation landing sites

- `docs/workstation/hooks-index.md`: the Stop row gains the deferral shape and the DECISION exemption; a new SessionStart `compact` row names the reconstructor.
- `docs/reference/thread-anchors.md`: the 72 h fold rule, the DECISION-block harvest and the compact-time block.
- `CLAUDE.md` § FINAL OUTPUT and `templates/governance/CLAUDE.md` (same section): the DECISION block's format. This is its ONE home; the hook's refusal text points at it rather than restating it.
- `CLAUDE.md` `# Compact instructions` (new heading in both contracts, E5).
- `docs/workstation/kaizen-event-stream.md`: the new `stop_block cause=deferral` and `decision_block` event fields.
- `CHANGELOG.md`, `docs/DECISIONS.md` (the rows below), `INDEX.md` (no new file expected).

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| **A — a model judge on every stop** (a `type: "prompt"` Stop hook, E7) | 0 of 3 panel judges ranked it first. It is nondeterministic, so the same message passes then blocks. It is blind to the run record and plan state. Its valve is the platform's 8, not ours. It costs one model call per stop (~25 K / 45 days) for shapes a deterministic check covers. Kept only as the SAMPLED audit (V6). |
| **B — prose only** | The bar has been prose since 2026-08-31 (D-054), and the 32.5% false-stop share (uniform sample) is what prose produced. |
| **`/goal`** (E7) | User-typed and session-scoped, with no settings key. It cannot be a fleet rule. |
| **The per-line class exemption for deferrals** (extend `_line_exempt` instead of a block) | It exempts on a class token anywhere on the line, and it leaves the legitimate two-thirds in free prose. The operator's complaint I7 is about those too. |
| **Block every question mark** | It would fire on quoted operator questions, rhetorical questions, and legitimate gates alike. That is wallpaper by K3. |
| **A PreCompact hook that BLOCKS manual compaction until state is saved** (E3) | A blocked manual `/compact` fails the operator's own action. PreCompact cannot add instructions anyway (E3). Reconstruction after the fact (C3) needs no agent cooperation. |
| **Agent-written handoff notes before compaction** | This is the rotting-anchor class the 578 h threads prove, and an agent cannot know when auto-compaction will fire (E3). Records beat notes, so notes stay a supplement (the summary itself). |
| **Inject the run record on EVERY prompt** (UserPromptSubmit) instead of at compact | This is wallpaper on 25 K prompts. The loss happens at compaction, and E2 gives an event for exactly that moment. |
| **Expire anchors after 72 h** (the DRAFT's own first choice) | A standing thread paused behind days of tangents in one long session would vanish. That is the founding defect `thread_anchor.py` exists to fix, and the operator never opens fresh sessions (D-row below). Folding the old anchors into one line removes the wallpaper and loses nothing. |
| **Set a fleet `autoCompactWindow` now** (E6) | It trades quota per turn against detail lost per compaction, and neither side is measured. C5 measures first (V5), so the window becomes a D-row on data. |
| **A new standalone hook file for deferrals** | The stall lane already owns the counter, the valve, the event stream and the quote guards. A second Stop hook would double-block and split the counter. |

## Lifecycle

- **Adoption.** The command corpus goes first: every command whose own text ends at a human gate states that gate as a `ground: gate` DECISION block, rendered and synced BEFORE the hook change lands (a gate turn would otherwise be blocked until its command catches up). Then one forced sync lands the hook fleet-wide (K6). V1's backtest replays only the TEXT shapes: run state (a live record, a plan lock, a same-turn dispatch) is not recoverable from a transcript. So the first day's `stop_block cause=deferral` count is read against V1 for turns OUTSIDE a live run record, and should land within ±30% of it. A rate far above that is a false-fire leak, and the shape responsible is tightened before anything else ships.
- **As it grows.**
  - The deferral shapes are a closed list. A new shape is added only when the V6 audit finds a recurring false stop the list misses (≥ 3 in one sample), with red and green fixtures.
  - DECISION blocks per day are the second series. A rising `underivable` share with shrinking `searched:` evidence is the cobra signal, and it tightens the `searched:` check before anything else.
  - If the warn-through rate for `cause=deferral` exceeds 10% of deferral blocks in a week, agents are waiting out the valve instead of acting on the reason. The response is to reword the reason, never to raise CAP.
- **Degradation.** Every new path fails open, like the rest of the hook (K1, K2):
  - an unparseable Stop input falls back to the transcript read;
  - a detection exception is written to stderr and allows the stop;
  - a missing run record means the compact block omits that line;
  - a git timeout omits the unpushed list.
- **Supersession.** If Claude Code ships a native "ask the operator" primitive with structured fields, the DECISION block maps onto it and the D1–D4 shapes stay as the fallback. The anchor fold is permanent hygiene.

## Cost

Files, with rough line counts:
- `.claude/hooks/final_gate_stop.py`: +~170 lines (the four shapes and `_DEFER_RE`, `_DECISION_GATE_RE`, the block parser, `_PERMISSION_RE`'s loop replaced by D3, the rewritten stall reason, the `last_assistant_message` read, the header fix, the events).
- `scripts/thread_anchor.py`: +~100 (the `source=compact` branch of `line`, the DECISION-block harvest and its UserPromptSubmit clear, the 72 h fold, the session-floored unpushed/dirty lists).
- The gate-ending command sources under `commands/_sources/` (their gate stated as a DECISION block), rendered and checked (`assemble_commands.py`, `check_command_corpus.py`).
- `scripts/sysadmin/kaizen_events.py`: `decision_block` joins `EVENT_TYPES`. `.claude/settings.json`: unchanged (C3 rides the existing SessionStart entry).
- `CLAUDE.md` + `templates/governance/CLAUDE.md` (every § FINAL OUTPUT copy): the DECISION block with two examples, the `operator-decision-bar` bullet, and `# Compact instructions`. About +25 lines each, minus the prose the hook now enforces.
- Tests: `tests/test_final_gate_stop_deferral.py` (new) and `tests/test_thread_anchor.py` (extended).
- Docs: `docs/workstation/hooks-index.md`, `docs/reference/thread-anchors.md`, `docs/workstation/kaizen-event-stream.md`.
- The measurement tool: the miner (`docs/reference/research/2026-09-23-stop-compaction/mine.py`, committed with this spec) is promoted to `scripts/sysadmin/stop_mine.py`, sharing `_DEFER_RE` with the hook. It serves the backtest V1, the audit V6 and the window reading V5.
- One mail to fabrik-lib.

Governance-sync paths make this a full `/fabrik-review` and one forced sync. No runtime spend: the only model calls are the audit's sampled judge seats (V6), run as native seats by the infra agent on days 7 and 14.

## Validation

- **V1 — backtest before ship (the text shapes only; run-state rules are V2's).** Replay D1–D4 over every interactive turn end since 2026-08-09, each read WHOLE from its transcript by session id and timestamp, never from a sample's tail.
  - Report the fire rate, per shape and per repo.
  - Judge a random 60 fires: ≤ 5% may be turns that do NOT defer at all. A fire on a legitimate deferral is by design, since it owes a block.
  - Fire on ≥ 17 of the 19 premature FALSE records (shapes say-the-word and menu) in `docs/reference/research/2026-09-23-stop-compaction/verdict-opdec.json`, each read whole from its transcript. The 7 `awaiting-nothing` records are ends after finished work, which D1 is built NOT to fire on; firing on any of them is reported as a false fire.
  - D4 fires on ≥ 6 of the 8 STOP-EXCUSE records and on 0 of the 9 FALSE-MATCH records in `verdict-context.json`, each read whole from its transcript, and stays silent on the 7 ordinary sentences in `d4_probe.py`.
- **V2 — the fixture suite.** One red and one green fixture per shape and per block rule, drawn verbatim from the judged samples. Each RED fixture is proven red on the unmodified hook, then green. Each GREEN fixture is proven by mutation: widen its shape on a throwaway copy and watch the fixture fail. The mutated state is never committed.
- **V3 — the reconstructor.** Fixture tests plus one live dogfood:
  - A fixture transcript and a live `running` record yield the WHERE-YOU-ARE block with all five items. A stopped record yields no run line. A sibling's commit on the branch never appears in item 4. A DECISION block harvested at Stop shows until the next UserPromptSubmit and not after it.
  - Anchors of 73 h fold into the summary line and anchors of 71 h print in full. Nothing is deleted.
  - Dogfood: a manual `/compact` in a hub window mid-command. The first post-compact message names the run's phase and continues it.
- **V4 — the outcome, 14 days after the sync** (stop_mine plus judge seats):
  - the premature false-stop share of operator deferrals: FALSE records of the say-the-word and menu shapes, over all judged records, 19/80 (23.75%) → ≤ 8/80, measured like for like (the same miner `OPDEC` population, a fresh uniform random 80, the same judge brief). The `awaiting-nothing` records are ends after finished work and are reported beside it, never inside it (A-O18);
  - divergence after a compaction with no live command run, 9/25 → ≤ 3/25 (a fresh random 40 compactions, judged per record by the same brief);
  - `cause=deferral` warn-through ≤ 10% of its blocks.
- **V5 — the compaction window.** Correlate `preTokens` at compaction (the transcript's `compact_boundary` record) with the judged post-compaction continuity. Correlate the per-turn cost of a long context with the same: the sum of `input_tokens`, `cache_read_input_tokens` and `cache_creation_input_tokens` in each assistant entry's `message.usage`, which every transcript carries. A window value is proposed as a D-row only if the data separates. Otherwise C5 records "no window change, measured".
- **V6 — the cobra audit (grafts G-a, G-b).** On days 7 and 14, three native Sonnet seats judge a random 40 DECISION blocks (a false ground, or `searched:` claims absent from the turn's tool calls) and 40 allowed interactive turn ends (a false stop that D1–D4 missed). A recurring miss (≥ 3) becomes a new shape with fixtures.

## Decisions taken (minted with this spec's CONVERGED flip)

1. The deferral check is deterministic, in the existing stall lane, with the existing valve. Approach C won the panel 3/3. A model judge is kept as a sampled audit only.
2. The DECISION block is the one legitimate way to hand the operator a decision. Its home is CLAUDE.md § FINAL OUTPUT; the grounds are D-054's three, kept whole: gate · underivable · owned.
3. **The operator ruling of 2026-09-22 gets its row:** *"do not act without asking me"*. A yes covers the step it answers, so a step past the operator's named scope is an `owned` decision. It never applies inside a live command run.
4. **The operator ruling of 2026-08-10 gets its row:** *"i never use a fresh session, i always continue existing sessions … that is why we use /compact command"*. Context is never a reason to stop, and a fresh session is never the remedy.
5. Post-compact state is reconstructed from records (the run record, last NEXT, open DECISION block, this session's unpushed commits and dirty files), never from agent-written notes. Anchors older than 72 h are folded, never expired.
6. No fleet `autoCompactWindow` until V5 measures it. This is a rejected-for-now option, recorded so it is not re-proposed on instinct.

All are reversible (a hook edit and contract text, reverted by commit), so none needs a § Binding block.

## Open / blocking unknowns

- **U1 — `last_assistant_message` on this box's Claude Code version.** It is documented (E1), but the hook's header claimed otherwise, so it may predate the field. Resolution: at build, log the key's presence on 20 live Stops. The fallback read keeps behaviour either way.
- **U2 — SessionStart ordering after compaction.** It is documented that the output is "added to the compacted context", but not where relative to the summary (E2). Resolution: V3's dogfood reads the post-compact transcript.
- **U3 — D1 on the conversational footer.** Whether "awaiting your reply" with no question in the tail is always benign is measured by V1's judged fires. If it is not, the green fixture is revised.
- **U4 — the sample's size.** 32.5% is 26 of 80, a uniform random sample of 5,442 (seeded, reservoir-drawn, § Why this exists). At n = 80 its 95% interval is roughly ±10 points, so V4's ≤ 10% target is read against a fresh sample of the same size and method, and a reading between 10% and 20% is reported as inconclusive rather than as success.

No BLOCKING unknown remains. Every external fact the design rests on is grounded in E1–E10.

## Review — Pass Ledger

| Pass | seats · axes re-checked | counters | method | spec md5 (start → end) |
|-----:|---|---|---|---|
| Pass 1 | opus×2 + sonnet×2 finders (A rules · B the rest · C facts E1–E4/E7 · D facts E5–E10) + 4 refuters · all axes | found: 38, new: 38, confirmed: 38, fixed: 38, unexecuted: 0, edits: 38 | method: citation — full partitioned pass; every confirmed candidate re-executed by the orchestrator (the regexes on a copy of the hook, the sample repos, the template's two § FINAL OUTPUT copies, fabrik-lib's line 1, the live page for E8); round zero added the event-stream window. Sample bias (A-O14) forced a uniform re-sample and per-record re-judging | 153c8718 → 27cc1182 |
| Pass 2 | opus×2 + sonnet×1 (the round-1 slice owners) + refuters · the fix diff plus one hop | found: 12, new: 7, confirmed: 12, fixed: 12, unexecuted: 0, edits: 12 | method: re-derivation — `derive.py` re-counted every judged number from the committed verdict files; own-fix 9 | 27cc1182 → 763ab050 |
| Pass 3 | opus×2 + sonnet×1 (the round-1 slice owners) + refuters · the fix diff plus one hop | found: 7, new: 6, confirmed: 6, fixed: 6, unexecuted: 0, edits: 6 | method: re-derivation — `d4_probe.py` run on the judged quotes; own-fix 6 → the scope-growth stop fires (two of three rounds ≥ two-thirds own-fix); the six were fixed and became the fixed set | 763ab050 → d121c165 |
| Pass 4 | opus×2 (the round-1 owners of A and C) + refuters · the fixed set only | found: 4, new: 4, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — the fixed set re-executed (6 of 6 NOW_FALSE); the four new candidates A-O40–43 lie inside round 3's own hunks: RECORDED — measured (A-O40 executed: the D4 frame fires on 5 factual sentences) → `docs/STRATEGIC_BACKLOG.md`, the plan's mandatory inputs | d121c165 → d121c165 ✓ → **CONVERGED** |
| Pass 5 | sonnet×2 (the round-1 owners of B and D) + refuters · their own ledgers only, on the committed text (51098f062) | found: 0, new: 0, **confirmed: 0**, fixed: 0, unexecuted: 0, edits: 0 | method: re-derivation — B-S2 re-counted from `stop-events-2026-09-23.json` (88 · 6 · 4,907) and D-S1 re-fetched live (verbatim); pass 4 had verified these two slices but not re-stated them, which leaves them open (D-335), so this pass re-stated all four | 616c9726 → 616c9726 ✓ → **TERMINAL** |
