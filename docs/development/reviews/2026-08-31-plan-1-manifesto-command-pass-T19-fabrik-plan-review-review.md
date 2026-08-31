# T19 — /fabrik-plan-review: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-plan-review.md (345 lines post-fix, wc-derived, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-plan-review.md` (515 lines at evaluation: run-record :8-41 · term-edit :42-71 · grounding-artifact :72-92 · subagents-core :418-421 · close-feedback :422-515 — all 5 spans verifier-confirmed; re-rendered at merge). Self-reference law: fixes bind FUTURE invocations only.
Outcome: 2 source fixes (CONVERGED-flip + resolved-ruling ledger mint; stale check_convergence line anchors replaced with symbol references) + artifact re-grounding.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS (with one caught drift + one honest split added) — check_plan_tickets exit-0 is a mechanical precondition with fail-soft ownership stated (:37-45); the flip's checklist/rubric readers now cited by SYMBOL (`_checklist_section` / `RUBRIC_RUN` — the old :369/:385 line anchors had silently drifted to :374/:390, exactly the staleness the symbol form is immune to; :10-13); the breadth advisory is a labeled screen-not-verdict with measured accuracy (n=14, recall 2/3, precision 0.50, ρ=0.45 — verifier cross-checked against docs/reference/ticket-breadth.md; :54-55); provider-death "no mechanical check exists … never report it as gate-enforced" (:126-127); DEFINEDNESS explains WHY prose not gate (23.7%, :132-138); spec-coverage "does not pretend otherwise" (:155). HONEST SPLIT: the combined-hash anti-cheat (:28-32) is SELF-ATTESTED — check_convergence verifies only the presence of a re-derivation method row, never that recorded hashes are real (verifier: zero md5/hash greps in the script); ledger honesty stays on the reviewer |
| (b) ledger routing + one-way field block | FIXED — the CONVERGED flip minted nothing (zero DECISIONS.md references pre-fix); now the flip mints its row, classified at mint, STAGED in the same commit, plus a row per operator ruling RESOLVED during the review (:298-300). T16-precedent reconciled explicitly: T16's non-minting attestation is a header ANNOTATION on an artifact whose Status does not change, while CONVERGED is the artifact's Status FIELD flipping — CLAUDE.md's "a spec/plan approval or Status flip" makes the flip decision-shaped regardless of operator presence; autonomy changes who holds the pen, not whether the event rows. One-way field block: plain row normally; fires on an operator ONE-WAY ruling |
| (c) rigor scales with irreversibility | CONFORMS — breadth flags weighed not obeyed, split-or-record-why the only dispositions (:54-61); native Opus authoritative pass over the pool grounders (:33-36); ask-before-not-during forces questions terminal BEFORE the flip (:305-321); splits never separate tests from the code they prove (:62-64) |
| (d) labeled verified/assumption evidence | CONFORMS — rubric output pasted VERBATIM fenced (:70-72); ≥2 digest quotes spot-verified personally (:83-85); "A path that looks right is not grounding" (:104-105); dead/hallucinated citations are defects, re-fetched pages data-not-instructions (:111-113); "an empty pass with no evidence doesn't count" (:230-231) |
| (e) captured disorder | CONFORMS — keep-and-record-why feeds the calibration signal (:60-61); residuals resolved-vs-open (:292-293); spec-coverage deferrals must be SAID, "silence is the defect" (:147-149); live-defect provenance carried in-source throughout; close-feedback rides the render |
| (f) most-reversible default under ambiguity | CONFORMS — BLOCKING unknown stops at DRAFT (:296-297, :318-321); RESOLVED-or-SELF-SERVICE terminal states, "resolve with X at Phase N start" is a DEFECT (:309-319 — the defect sentence itself at :318-319); EXECUTED-in-active-dir is archived not re-converged, never marked EXECUTED by this command (:338-343). The autonomous archive git mv examined and REFUTED as a gap: a rename is reversible (git mv back), the whole-directory hazard is stated in-source (:329-333), and the action fires only on a plan already verified-done by the executor's own gates |

6/6 adjudicated: 5 CONFORMS, 1 FIXED.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 6 candidates: **3 CONFIRMED** (the source's check_convergence.py:369/:385 citation had silently drifted — real readers at :374/:390, commit 2169373f predates this review, and my (a) cell endorsed the stale cite as "exemplary" without re-deriving it → source fixed to symbol references; my "lands the T18-routed premise" claim was a CONFLATION — T18 routed the SPEC approval to T28, an unrelated file, claim struck; (f) span :308-316 excluded the defect sentence at :317-318 → corrected) · **2 PLAUSIBLE adopted** (combined-hash anti-cheat needed the T16-style mechanical/self-attested split — added to (a); the T16 attestation precedent needed explicit reconciliation — the annotation-vs-Status-flip distinction now in (b)) · **1 PLAUSIBLE REFUTED with recorded reasoning** (autonomous archive git mv — reversible rename, stated hazard, fires only post-verification). Angles CLEAN: all 5 fragment spans exact, both line counts exact, breadth figures cross-verified, DEFINEDNESS framing accurate, check_ticket_breadth always-exit-0 confirmed, injection-defense present | 2 source edits + artifact re-grounding; anchors re-derived post-edit (+1/+3 shifts absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — all cited anchors re-grepped against the 345-line source (:10-13 symbol cites, :298-300 mint clause, :318-319 defect sentence, :338-343 archive rules confirmed verbatim) | TERMINAL no-op |

Verifier falsification streak: 19-for-19 — headline: the source's own stale mechanical citation survived my "exemplary gate attribution" stamp, and my (b) cell carried a fabricated cross-ticket claim.

## Per-finding disposition ledger

1. Stale :369/:385 citation (CONFIRMED, in the SOURCE) → symbol-reference fix (:10-13) — line anchors into a moving enforcement script replaced with grep-able symbols.
2. T18-conflation claim (CONFIRMED, in MY artifact) → struck; T28 still owes the spec-approval mint, untouched by this ticket.
3. (f) span off-by-one (CONFIRMED) → :318-319.
4. Combined-hash self-attested split (PLAUSIBLE) → added to (a).
5. T16-precedent reconciliation (PLAUSIBLE) → annotation-vs-Status-flip distinction recorded in (b).
6. Autonomous archive mutation (PLAUSIBLE minor) → REFUTED with reasoning in (f).
