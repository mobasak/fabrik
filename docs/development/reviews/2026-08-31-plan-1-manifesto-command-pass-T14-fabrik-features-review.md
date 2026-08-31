# T14 — /fabrik-features: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-features.md (113 lines post-fix, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-features.md` (279 lines at evaluation: run-record :17-50 · term-edit :51-75 · grounding-artifact :76-96 · subagents-core :182-185 · close-feedback :186-279 — composition heading-grep-verified by the author-blind pass; re-rendered at merge).
Outcome: 3 source fixes (EARLY-pinning ledger provenance; operator-disposition routing; mode-ambiguity guard) + artifact re-grounding.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS (honestly characterized) — the Phase 3 terminal ("one demonstrably-thorough pass makes zero edits" :88; "edit-free, md5-verified no-op round" :101) is CONTRACTUAL, machine-traced through the rendered run-record fragment's round ledger (`command_run.py round` — the only machine-read trace of this loop), not enforcement-script-gated: `check_convergence.py`/`check_review_coverage.py` scan plans+reviews, never a project's FEATURES.md. The one true mechanical gate cited (:11-13, `check_certification_coverage.py`) protects the DOWNSTREAM denominator misuse (it gates user-test/service-test per its AFTER-EDIT header), and the verdict claims no more than that |
| (b) ledger routing + one-way field block | FIXED (two fixes) — the source called the EARLY row write "the product decision" with zero DECISIONS.md reference anywhere in the file (siblings fabrik-data-contract.md/fabrik-spec.md carry explicit pointers); now: the pinning's provenance is stated — the decision was MINTED by the spec approval's row at /fabrik-spec-review, rows transcribe it (:27-28) — and an operator disposition received on surfaced un-shipped scope / scope-creep (drop / keep-planned / adopt) is a RECEIVED decision minting its row same-change (:36-39). Remaining edit classes are truth-restoring (deprecation markers reflect code state :81-82; "cut or rewrite" is exercisability hygiene :80). One-way field block N/A — the unwind cost of pinned scope is borne at the downstream freezes (flows/data-contract/ui-design), each of which mints its own ledger row; this command's own edits stay reversible |
| (c) rigor scales with irreversibility | N/A because the command's product is uniformly low-irreversibility (a reversible doc table) — stakes are borne downstream by certification, which is pointed at the LIVE REGISTRY denominator, never this doc (:11-15). The one differential-rigor rule present scales with row recency, not stakes: "spot-check ALL new rows, sample the old" (:93). No stakes-scaled mechanism exists or is needed here; the prior CONFORMS repurposed (a)'s anchors |
| (d) labeled verified/assumption evidence | CONFORMS — "enumerate what you READ (files × surfaces), not what you remember" (:68); "a path that looks right is not grounding" — open it (:73-74); "memory is not discovery" (:106); md5-verified no-op (:101) |
| (e) captured disorder | CONFORMS — a removed feature is stated in the run report, "the operator may be tracking it" (:108); vapor README/QUICKSTART claims are findings, not decoration (:109); state honesty markers for beta/deprecated/flagged rows (:81-82); close-feedback's filing duties ride the render |
| (f) most-reversible default under ambiguity | FIXED — un-shipped Planned scope was already surface-don't-delete (:35) and silent deletion banned (:108), but two live ambiguity modes had no stated default: no FEATURES.md on disk, and EARLY invoked where code already ships. Now: mode ambiguity resolves reversibly — seed from the template first; EARLY-with-shipped-code → say so and run REFRESH, the code outranks the spec once it exists (:40-42). Handoff while non-quiet stays banned (:110-111) |

6/6 adjudicated: 3 CONFORMS, 2 FIXED, 1 re-adjudicated to N/A.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 7 candidates, ALL adopted: **3 CONFIRMED** (source is 105 lines, artifact claimed 106 — the denominator class; (a) conflated a downstream gate with this command's own unenforced loop — check_certification_coverage's AFTER-EDIT header names user-test/service-test, and no enforcement script covers a project's FEATURES.md convergence; (d) anchor :66 actually spans :65-66) · **3 PLAUSIBLE adopted as REAL source gaps** (EARLY "product decision" with zero in-file DECISIONS.md reference while sibling commands carry explicit pointers → provenance clause :27-28; operator-disposition routing absent → received-decision clause :36-39; two unhandled mode-ambiguity failure modes → reversible-default guard :40-42) · **1 PLAUSIBLE adopted as re-adjudication** ((c)'s citations showed temporal/categorical rules, not stakes-scaling → honest N/A-because-X; the one-way N/A rewritten to address decision-unwind cost, not diff size). Angles CLEAN: rendered composition exactly as claimed; all remaining anchors quote-accurate | 3 source edits + full artifact re-grounding; every anchor re-derived fresh via grep AFTER the edits (+3/+4/+1 line shifts absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — all cited anchors re-grepped post-edit against the 113-line source (:27-28, :35-39, :40-42, :68, :73-74, :81-82, :88, :93, :101, :106, :108-111 confirmed verbatim) | TERMINAL no-op |

Verifier falsification streak: 14-for-14 — including this ticket's all-CONFORM initial stamp, which was exactly the claim the verifier dismantled.

## Per-finding disposition ledger

1. Line count 106 vs 105 (CONFIRMED) → fixed: 113 post-edit, wc-derived.
2. EARLY-pinning ledger gap (PLAUSIBLE→REAL) → source fix: provenance clause — minted at /fabrik-spec-review, rows transcribe (:27-28).
3. (a) mechanical-checkability overstatement (CONFIRMED) → artifact relabeled: contractual terminal + round-ledger trace; the downstream gate credited only for what it gates.
4. (c) not stakes-scaled (PLAUSIBLE) → re-adjudicated N/A because the product is uniformly reversible; recency-sampling noted honestly.
5. Mode-ambiguity failure modes (PLAUSIBLE→REAL) → source fix: reversible defaults for missing-doc and EARLY-with-code (:40-42).
6. One-way N/A conflation (PLAUSIBLE) → artifact rewritten: unwind cost borne at downstream freezes which mint their own rows.
7. :66 anchor imprecision (CONFIRMED minor) → :73-74 post-edit, span-corrected.
