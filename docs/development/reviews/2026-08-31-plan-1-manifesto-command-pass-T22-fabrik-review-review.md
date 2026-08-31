# T22 — /fabrik-review: 63b manifesto conformance + the seeded exit-vocabulary adjudication

Status: DONE

Surface: commands/_sources/fabrik-review.md (373 lines post-fix, wc-derived, read in full; grep-derived anchors) + commands/_fragments/term-coverage.md (27 lines — the ORCHESTRATOR-APPLIED fragment edit T22's ticket sanctions; blast radius: 5 consumer commands — fabrik-review, fabrik-conformance-review, fabrik-service-test, fabrik-user-test, fabrik-repo-review) + the RENDERED command `~/.claude/commands/fabrik-review.md` (504 lines at evaluation, pre-fix; re-rendered at merge). Side artifacts: docs/DECISIONS.md D-048 minted + the pre-existing duplicate D-047 renumbered to D-049 per `decisions.py --check`'s own instruction (checker now exit-0); docs/STRATEGIC_BACKLOG.md done-round-check row updated (ruling recorded, unblocked).
Outcome: the SEEDED finding adjudicated as a RULING (D-048), applied at the class root (the fragment) + 6 source edits + ledger hygiene.

## The seeded adjudication (63b intersection (a) — plan carry-item (g))

The tension, grounded: the command's exit example EXITed on `found: 1 | new: 0` (a standing DESIGN-GAP re-raise) while BOTH graders demand a quiet pair — `check_convergence.py` QUIET_PASS `found:\s*0…fixed:\s*0` (:150) on any review an EXECUTED plan cites, and `check_review_coverage.py`'s final ledger row must be found==0 unless BLOCKED/IN-PROGRESS (:466-469). Counting the re-raise made honest termination impossible (transdoc 2026-08-27); suppressing it hides a real observation.

**RULING (D-048): the graders' quiet exit is canonical. `found:` counts only candidates NEEDING adjudication — a re-raise of an already-adjudicated standing row is CITED in its disposition-ledger row, never counted. `new:` stays the stopped-learning signal.** Applied at the CLASS ROOT — commands/_fragments/term-coverage.md (:15-16 exit bullet with the two-correction history; :20 ledger `found:` definition; :24 breaker convergence clause) — so all 5 consumer commands inherit it in one edit, plus fabrik-review's own terminal statement (:13-15), description (:2), Reporting example + grader-naming note (:337-350), completion wording (:353-356), and both done-evidence strings (:29, :313). The run-record terminal `found:0 no-op round` (:18) is now consistent without an edit. Unblocks the parked command_run done-round-check (backlog row updated).

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | FIXED (the seeded ruling, applied at the fragment root) — the exit is mechanically gradeable AND honest across all 5 term-coverage consumers: `found: 0 · new: 0` with re-raises cited-not-counted (fragment :15-16, :20, :24; fabrik-review :13-15, :337-356); check_subagent_flywheel BLOCKS all-native substantial changes unless NO-POOL declared (:138); the round ledger is Stop-hook-enforced (:21-28); every-name-close prevents the nested close ending the caller (:30-32) |
| (b) ledger routing + one-way field block | FIXED — a deliberate design-decision disposition counted as FIXED now mints its `docs/DECISIONS.md` row staged in the fix commit; mechanical bug-fixes stay row-less (:245-249). The ruling itself minted D-048 (architecture-choice class, orchestrator's pen), and the duplicate-D-047 collision one row below it was renumbered to D-049 per the checker's instruction (id-only, truth-restoring; the fleet author informed via commit body). One-way field block N/A — review dispositions are reversible with regression guards |
| (c) rigor scales with irreversibility | CONFORMS — the ≥1-native-Opus floor is UNCONDITIONAL, "pool-only is not a valid review" (:142-146); high-risk classes get the native authoritative pass on top of pool breadth (:135-137); hub-side synced files reviewed HARDER through the fleet lens, two live saves cited (:73-82); "never degrade shared or paid infrastructure to manufacture a red" (:250-254) |
| (d) labeled verified/assumption evidence | CONFORMS — REFUTED requires quoting the guard, "proof, not a shrug" (:258-260); environment-cannot-express-failure (:249-251); shas MATERIALISED for finders so they never review a dirty sibling tree (:103-120); external shapes confirmed via official docs, never memory (:203-206); green necessary-not-sufficient (:281-282); empty passes without coverage evidence don't count (:337) |
| (e) captured disorder | CONFORMS — the per-finding disposition ledger, N FIXED + N REFUTED must sum (:358-362); "Residual risks is NOT a parking lot" (:364-368); a synced file in the diff is ITSELF a finding, never silently excluded (:67-69); REPRO-DEFECTIVE returns REFUTED-RIG (:89-95); the cited-not-counted re-raise keeps standing observations VISIBLE while terminating — disorder captured, not suppressed |
| (f) most-reversible default under ambiguity | CONFORMS — PLAUSIBLE is not a licence to skip (:262-267); no third noted/deferred state (:241-243); a finder's proposed fix is a suggestion to VERIFY (:269-278); "when unsure, surface it and discharge it" (:372-373); synced files in projects are context-never-target, list computed not hand-copied (:42-52) |

6/6 adjudicated: 4 CONFORMS, 2 FIXED (one the seeded ruling, D-048).

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 7 candidates: **4 CONFIRMED** (the term-coverage FRAGMENT still carried the OLD found-semantics in three places, contradicting my in-body ruling — the exact orchestrator-applied fragment obligation T01 seeded and T22's own ticket text mandates, silently dropped in my first pass; the obligation was documented, not discretionary; T34 is forbidden from fixing it — this was the only ticket positioned to; the duplicate D-047 collision sat unflagged one row below my fresh D-048 while decisions.py --check screamed) · **2 PLAUSIBLE adjudicated** (fragment blast radius across 5 consumers — ADOPTED, the class fix generalizes: all five share the same graders and the same termination bug; D-047/D-048 sequencing — REFUTED, normal immutable-append order with execution authorized between mints) · **1 PLAUSIBLE adopted** (done-evidence strings threaded to the found:0·new:0 pair). All fixed: 3 fragment edits + 2 evidence-string edits + D-049 renumber (checker exit-0 verified) | fragment + source edits; anchors re-derived post-edit |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — fragment :15-16/:20/:24 re-read post-edit (cited-not-counted present in all three), fabrik-review :29/:313 evidence strings re-grepped, decisions.py --check exit-0, all remaining anchors confirmed | TERMINAL no-op |

Verifier falsification streak: 22-for-22 — headline: my ruling fixed the command body while leaving the fragment (the actual class root, rendered into five commands) carrying the contradiction, and the ticket text had named that exact obligation.

## Per-finding disposition ledger

1. Fragment old-semantics contradiction (CONFIRMED ×3 sites) → orchestrator-applied fragment edit: exit bullet + two-correction history, found: definition, breaker clause (term-coverage.md:15-16, :20, :24).
2. Dropped T01-seeded obligation (CONFIRMED) → discharged by fix 1; recorded here as the plan's carry mechanism intends.
3. T34-cannot-fix urgency (CONFIRMED) → moot after fix 1.
4. Duplicate D-047 (CONFIRMED, pre-existing) → later-minted Gotenberg row renumbered D-049 per the checker's own instruction; decisions.py --check now exit-0; fleet author informed via commit body.
5. Fragment blast radius (PLAUSIBLE) → ADOPTED as the reason the fix belongs at the fragment root; all 5 consumers share the graders.
6. D-047/D-048 sequencing (PLAUSIBLE) → REFUTED: immutable append order; execution was authorized between the two mints.
7. done-evidence strings (PLAUSIBLE minor) → threaded to `found:0 · new:0` (:29, :313).
