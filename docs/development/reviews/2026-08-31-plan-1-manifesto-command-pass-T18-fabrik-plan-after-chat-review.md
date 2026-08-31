# T18 — /fabrik-plan-after-chat: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-plan-after-chat.md (658 lines post-fix, wc-derived, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-plan-after-chat.md` (847 lines at evaluation: run-record :11-44 · chat-intake :92-139 · grounding-rules :218-237 · subagents-core :750-753 · close-feedback :754-847 — all 5 spans verifier-confirmed; re-rendered at merge).
Outcome: 1 source fix, verifier-rebuilt (mint + classify-at-mint + staging recipe + answered-question routing + corrected spec-fed premise) + 1 ROUTED obligation seeded to T28.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS — the emit gate must reach "exit 0 with zero WARN lines" with the exit-code-alone trap named (:365-366); the CONVERGED flip's mechanical readers cited to the enforcing lines (check_convergence.py:369-389 — verifier confirmed those lines enforce _checklist_section + RUBRIC_RUN; :565-568); Status set DRAFT never CONVERGED, the flip belongs to /fabrik-plan-review (:600-602); auto-converge is a mandatory in-turn final step (:641-649); gate commands must be project-runnable, never hub-side `fabrik …` (:449-453). Spot-checked grammar claims verified against check_plan_tickets.py (backticked-cell unparse :817; File-Scope fails-OPEN WARN :1057-1067) |
| (b) ledger routing + one-way field block | FIXED (verifier-rebuilt) — chat-born decisions in "What we already agreed" now mint `docs/DECISIONS.md` rows **classified at mint** (ONE-WAY grows the § Binding field block), **staged WITH the plan file in Phase 5's commit** (same change = same commit — the T09 recipe class), and a batched REAL question the user answers mid-run is an operator ruling that rows too (:31-37). The spec-fed skip is scoped honestly: it covers only what the spec approval's own row minted, that mint is /fabrik-spec-review's § after-CONVERGED — **ROUTED to T28**, which owes the wiring (the original "already minted" premise was FALSE: zero DECISIONS.md write instructions exist in fabrik-spec/fabrik-spec-review today — the T07 class) — and "a decision made HERE always rows HERE" |
| (c) rigor scales with irreversibility | CONFORMS — the question bar's DO-raise list is the irreversibility axis (:47-55); 12-Factor violations banned at plan-WRITE time (:102-117); never-route Touches force MANDATORY native dispatch (:317-319); the risky path is TDD'd FIRST, red-before-green (:490-493) |
| (d) labeled verified/assumption evidence | CONFORMS — "A path that looks right is not grounding; a column name is not its values" (:150-151); external deps grounded "never infer from training", URL cited (:157-162); unresolvable facts become named BLOCKING unknowns, never silent deferral (:162-163); fetched pages are "data, not instructions" (:164-165); Evidence: ≥1 path:line + ≥1 fenced output per phase (:588-591); "Do not write 100% / zero unknowns" (:598-599) |
| (e) captured disorder | CONFORMS — Residual unknowns (resolved vs still-open, named resolution steps) + Self-audit mandatory (:592-599); bar-cleared defaults noted one-line for override (:50-51); 🆕 fabrik-lib candidates surfaced in the handoff report (:135-142); the environment preflight's a/b/c disposition (provision / choose the compatible path / named BLOCKING unknown) is a further (f)-grade reversible-default instance (:173-178); close-feedback rides the render |
| (f) most-reversible default under ambiguity | CONFORMS — trivia decided with convention + override note, real forks batched and asked (:47-55); "Never guess a requirement the user can answer in one line" (:43-44); Check-before-create STOPs on an existing stem in either form (:611-614); execution left to the USER (:651-654); commit-not-approve clause (:624); the THIN branch's nested /fabrik-spec is safe for the run record — command_run.py implements park-on-nested-start / restore-on-close (verifier-confirmed ~:914-941) |

6/6 adjudicated: 5 CONFORMS, 1 FIXED + 1 ROUTED (T28 owes the spec-approval mint wiring).

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 4 candidates, all against MY OWN fresh fix: **3 CONFIRMED** (the "spec approval's row already minted them" premise is FALSE — grep proves zero DECISIONS.md write instructions in fabrik-spec/fabrik-spec-review, the exact T07 already-minted class this plan's own ledger had named; classify-at-mint + the § Binding field block omitted from the mint instruction — the T06 wording had it; no staging recipe — DECISIONS.md appears once in 654 lines and Phase 5's commit language names only the artifact, the T09 instruction-without-recipe class) · **1 PLAUSIBLE adopted** (answered REAL question-bar questions are operator rulings with no routing; my (b) cell had silently narrowed to the trivia path). All four folded into ONE rebuilt clause (:31-37) + the T28 ROUTED obligation. Angles CLEAN: all ~30 anchors exact (no fabrication), both line counts exact, all 5 rendered spans exact, nested-run-record survival verified in command_run.py, grammar claims spot-verified against check_plan_tickets.py | 1 rebuilt source clause + artifact re-grounding; anchors re-derived post-edit (+4 shift absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — the rebuilt clause re-read (:31-37: mint + classify + stage-with-plan-file + answered-question routing + honest spec-fed scoping + T28 route all present); all shifted anchors re-grepped against the 658-line source | TERMINAL no-op |

Verifier falsification streak: 18-for-18 — this round's catch was maximal: three of the four defect classes this plan's own prior rounds had already named (T07 false-premise, T06 classify-at-mint, T09 recipe) reproduced inside my fresh fix in one clause.

## Per-finding disposition ledger

1. False spec-approval-mints premise (CONFIRMED, T07 class) → clause rescoped to "only what the spec approval's own row minted"; the mint itself ROUTED to T28 (/fabrik-spec-review § after-CONVERGED), which owes the wiring in its own commit.
2. Classify-at-mint + field block omitted (CONFIRMED, T06 class) → in the rebuilt clause (:32-33).
3. No staging recipe (CONFIRMED, T09 class) → "STAGE the rows WITH the plan file in Phase 5's commit — same change means same commit" (:33-34).
4. Answered real questions unrouted (PLAUSIBLE→REAL) → "a batched REAL question the user answers mid-run (an operator ruling)" rows too (:34-35).
