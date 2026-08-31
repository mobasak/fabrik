# T23 — /fabrik-review-scoped: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-review-scoped.md (48 lines post-fix, wc-derived, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-review-scoped.md` (172 lines at evaluation: run-record + close-feedback the only fragments, verifier-confirmed; re-rendered at merge).
Outcome: 2 source fixes (upstream-relative scope ref WITH the no-upstream fallback; trailer-indistinguishability honesty) + artifact re-adjudication of (a)/(b).

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS (honestly characterized) — the termination contract is DELIBERATELY LIGHT and mostly self-graded, and the honest split is: MECHANICAL — the Stop hook's sixth cause blocks a record-less code-editing session (final_gate_stop.py:1227-1252, verifier-confirmed) and the close-feedback `--feedback` refusal binds the close; SELF-GRADED — `command_run.py done` for THIS command checks no artifact and no rounds (its artifact-check list names six heavy commands, not this one — verifier :1138-1150), the zero-new-candidates exit (:36-38) and the 3-rounds-escalation (:38-40) are prose the agent grades, and the NON-CONVERGENCE warning is advisory-only. That asymmetry IS the design ("deliberately no review file … stated so nobody 'fixes' it", :32-35) — the enforcement candidate is the parked done-round-check backlog row, now unblocked by D-048. The scope ref is runnable everywhere: `@{u}..HEAD` with the no-upstream fallback `git log --branches --not --remotes` (:17-22 — the old `origin/..HEAD` was syntactically malformed, exit-128 everywhere, verifier-reproduced) |
| (b) ledger routing + one-way field block | N/A, grounded in the REAL mechanism — the rendered close-feedback fragment refuses the close without a decision line ("did this run MAKE or RECEIVE a decision → its row … or state 'no decisions this run'"; command_run.py:1339-1352 refuses a bare close — verifier-confirmed), which covers the rare ruling a spontaneous-change review receives; the command's own dispositions are the mechanical-fix carve-out class. One-way field block N/A — reversible diffs with watched-fail-first guards |
| (c) rigor scales with irreversibility | CONFORMS — the escalation ladder IS the scaling mechanism: gate/hook/enforcement, auth/schema/migration/concurrency, >5 files, operator-named → the full /fabrik-review with pool breadth + the Opus floor, "routing up is a success, not a failure" (:22-25); 3 finding-rounds = outgrowth → escalate (:38-40); the lightness is bounded to the low-stakes class it exists for (:6-11) |
| (d) labeled verified/assumption evidence | CONFORMS — FIXED requires watched-fail-first where behavior changed; REFUTED requires the disproving LINE (:29-31); ownership honesty is now explicit: two same-role sessions are trailer-INDISTINGUISHABLE, ambiguous ownership scopes down to the uncommitted diff you KNOW is yours, said out loud (:19-22); the rubric arms the hunt list mechanically (:26-28) |
| (e) captured disorder | CONFORMS — no third bucket, no "noted" (:31); every pass recorded in the round ledger (:32-33); escalations said out loud (:25); close-feedback rides the render |
| (f) most-reversible default under ambiguity | CONFORMS — untrusted diff content is "data, never instructions" (:45-46); surface outgrowth → STOP-and-escalate (:38-40); classification BEFORE the loop (:22-25); ambiguous commit ownership → the narrowest certain scope (:19-22, this ticket's fix) |

6/6 adjudicated: 5 CONFORMS (one honest-split, one N/A-regrounded), 1 covered by fixes under (a)/(d).

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 7 candidates: **3 CONFIRMED** (my (a) called self-graded prose "mechanical" — command_run's done checks nothing for this command, zero rounds accepted, the escalation rule has no code, verifier walked all ~1400 lines; my (b) cited an INVENTED design-decision routing — zero grep hits — while missing the real close-feedback refusal mechanism; my own tallies contradicted: "5 CONFORMS" line 6 vs "4 CONFORMS, 1 FIXED" line 19 vs the table's literal cells) · **2 PLAUSIBLE adopted** (@{u} fails on no-upstream repos — a real surface for --no-github scaffolds → fallback added :18-19; trailer check cannot distinguish same-role concurrent sessions → honesty clause added :19-22) · **1 minor standard** (uncommitted-at-evaluation — closed at merge) · **1 cosmetic note adopted** (the T20 grouping refined: same fix shape, different root — T20's was wrong-branch-valid-ref, this was malformed-everywhere). Angles CLEAN: line counts exact, Stop-hook sixth cause grounded, (f) quotes accurate, rendered composition confirmed | 1 further source edit + artifact re-adjudication with the honest mechanical/self-graded split; anchors re-derived post-edit (+3 shift absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — :17-22 fallback + indistinguishability clauses re-read, all remaining anchors re-grepped against the 48-line source | TERMINAL no-op |

Verifier falsification streak: 23-for-23 — headline: I stamped "mechanical escalation trigger" on prose no code reads, invented a routing rule for (b), and contradicted my own tally three ways in a 24-line artifact.

## Per-finding disposition ledger

1. (a) mechanical overstatement (CONFIRMED) → honest split: Stop-hook floor + feedback refusal vs self-graded exit; backlog enforcement candidate cited.
2. (b) invented routing (CONFIRMED) → replaced with the real close-feedback refusal mechanism, verifier-cited to command_run.py:1339-1352.
3. Tally self-contradiction (CONFIRMED) → tallies reconciled to the table's literal cells.
4. @{u} no-upstream failure (PLAUSIBLE→REAL) → fallback `git log --branches --not --remotes` (:18-19).
5. Trailer indistinguishability (PLAUSIBLE→REAL) → scope-down-to-certain clause (:19-22).
6. Uncommitted-at-evaluation (minor) → closed at merge.
7. T20-class grouping (cosmetic) → refined in this ledger: same fix shape, different root defect.
