# T15 — /fabrik-flows: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-flows.md (216 lines post-fix, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-flows.md` (367 lines at evaluation, pre-edit render: run-record :38-71 · term-edit :72-99 · questionbar :236-238 · subagents-core :270-273 · close-feedback :274-367 — every boundary grep-confirmed to the line by the author-blind pass; re-rendered at merge, boundaries after Phase 6 shift +5).
Outcome: 2 source fixes (freeze-ledger routing with classify-at-mint + same-COMMIT staging) + artifact re-adjudication of (a)/(b).

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS (honestly split) — two distinct layers, neither overstated: the frozen-chain stale-PIN check is MECHANICAL but WARN-only (`check_frozen_chain.py` — synced, wired at final_gate.py:1208 with warn_only=True, "the findings are the product"; it checks cross-artifact pin drift, never this file's own convergence :186); the md5-identical before/after convergence proof (:169-170) is SELF-ATTESTED prose, machine-traced only through the run-record round ledger — no enforcement script verifies it. The Phase 6 validation gate is an enumerated walk (:156-168); term-edit supplies the edit-count termination contract |
| (b) ledger routing + one-way field block | FIXED — the freeze is a Status flip and the file carried zero `docs/DECISIONS.md` reference; now: the freeze mints its row SAME-change, a re-freeze bump N→N+1 is a NEW row, **classified at mint** — normally reversible-by-re-freeze so the plain row suffices unless the operator rules otherwise (mirrors T05's shipped wording at fabrik-data-contract.md:166-169) — and the row is staged WITH the artifact in the :182 commit: same-change means same COMMIT, not same run (:171-175). Field block fires only on an operator ONE-WAY ruling, consistent with (c): downstream rework is expensive, not impossible to unwind — versioned supersede is the unwind path |
| (c) rigor scales with irreversibility | CONFORMS — Phase 4 exists because "surfacing assumptions is cheap, fixing frozen artifacts is expensive" (:118-119); the freeze law bans in-place edits, forcing version-bumped re-freezes (:178-180); FROZEN ≠ attested — the independent author-blind review must run before any consumer freezes against it (:176, :207-214); the ordering law itself prevents the costliest failure, a scope-ceiling contract (:20-27) |
| (d) labeled verified/assumption evidence | CONFORMS — md5-identical hashes as the stated convergence proof (:169-170); the spec's Personas section is the stated DENOMINATOR (:82-84); "State which packs were read" (:64); "Zero hits is a stated result, never an omitted one" in the Downstream impact table (:196-197); the PRIMARY-PATH counting rule stated verbatim so no reader re-invents it (:148-152) |
| (e) captured disorder | CONFORMS — criterion/journey mismatches are "a finding — surfaced, never dropped" (:77-78); backfill grandfathers gaps with a ⚠ note IN the artifact (:65-66 — recorded, not silent); contract inputs "never trimmed" (:24, :159); the step-budget collision is "a FINDING against whichever contract is wrong" (:85-88); close-feedback's filing duties ride the render |
| (f) most-reversible default under ambiguity | CONFORMS — "resolve gaps in conversation, never hand off with known gaps" (:156); committing a DRAFT/FROZEN artifact is NOT approving it (:182); the freeze is presented and stands unless redirected (:176); unreconcilable review findings route back before consumption (:213-214); fresh mode → "minimal stub, say so" (:66). Phase 4's alignment step has no no-operator fallback — REFUTED as a defect: this command is a 2-contract interactive design stage (its § Next hands to a human-gated review), and the rendered questionbar fragment governs the question discipline for exactly this step |

6/6 adjudicated: 4 CONFORMS, 1 FIXED, 1 CONFORMS-after-honest-split.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 5 candidates: **1 CONFIRMED** ((b)'s one-way N/A contradicted the same table's (c) cell and reproduced the exact conflation T14 caught in itself — "versioned supersede" is the universal ledger mechanism, not a reversibility signal) · **2 PLAUSIBLE adopted** ((a) blended a WARN-only mechanical check with self-attested md5 prose under one CONFORMS without T14's honest split; the SAME-change mint had no staging recipe — :182's COMMIT instruction named only the artifact, the T03-established atomicity class) · **1 open-item verified-closed at merge** (pre-edit render lacked the fix — re-rendered in the merge commit) · **1 low-confidence REFUTED** (Phase 4 alignment: interactive-by-design stage + questionbar fragment governs; refutation recorded in the (f) cell). Angles CLEAN: both line-count denominators exact; all 18 anchors span-accurate; check_frozen_chain coverage of flows.md confirmed real; mint placement covers the re-freeze path via re-invocation | 1 further source edit (classify-at-mint mirroring T05's shipped wording + same-COMMIT staging) + (a)/(b) cells re-adjudicated; every anchor re-derived fresh post-edit (+3 shift below :171 absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — all cited anchors re-grepped against the 216-line source (:171-175 clause, :176, :178-180, :182, :196-197, :207-214 confirmed verbatim; T05 mirror wording cross-checked at fabrik-data-contract.md:166-169) | TERMINAL no-op |

Verifier falsification streak: 15-for-15 — this round's headline catch was the plan's own established defect class (T14's one-way conflation) reproduced by the ticket meant to apply the lesson.

## Per-finding disposition ledger

1. (b)/(c) one-way contradiction (CONFIRMED) → re-adjudicated: classify-at-mint clause added to source (:171-175); field block fires on operator ONE-WAY ruling; expensive-rework ≠ impossible-unwind, the versioned supersede IS the unwind path.
2. (a) mechanical/self-attested blend (PLAUSIBLE) → artifact split honestly: WARN-only pin gate vs self-attested md5 + round-ledger trace.
3. SAME-change staging gap (PLAUSIBLE→REAL, T03 class) → source fix: "stage the row WITH the artifact in the commit below — same-change means same COMMIT, not same run" (:172-175).
4. Stale render (open item) → closed at merge: re-rendered, --check green.
5. Phase 4 no-operator default (low-confidence) → REFUTED: interactive 2-contract stage, questionbar governs; recorded in (f).
