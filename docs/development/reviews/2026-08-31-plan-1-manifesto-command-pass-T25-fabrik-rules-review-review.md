# T25 — /fabrik-rules-review: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-rules-review.md (159 lines post-fix, wc-derived, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-rules-review.md` (300 lines at evaluation, PRE-fix render — the merge render carries all four fixes, ~+13 lines).
Outcome: 4 source fixes (Phase-0 decision-ledger read; HUB-mode scope contradiction resolved — steps 3–4 apply there; T21-class secrets carve-out for pool excerpts; D-048 counting semantics for the round ledger) + artifact anchor corrections.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | FIXED — the bare `--findings <n>` was D-048-ambiguous: this command's deliverable is a PERSISTENT never-fixed gap table, so reading `<n>` as table size made command_run's TERMINAL (`findings == 0` on the final round) unreachable for any project with a real standing gap; `<n>` now counts gaps NEW or RECLASSIFIED this pass — a standing gap re-listed is CITED, not counted (D-048) — so the stable pass records `--findings 0` honestly while real gaps stand (:132-137). The exit remains the identical-to-prior no-op pass (:121-127); the chat-only honesty statement stands ("a run whose rounds are unrecorded has no evidence it converged", :130-137); the unprompted-next-pass duty pre-empts the fair-challenge dodge (:139-144) |
| (b) ledger routing + one-way field block | N/A for mints (READ-ONLY; "propose nothing as fixed/done until I say so" :9), FIXED on the READ side in BOTH modes: Phase 0 greps `docs/DECISIONS.md` alongside the ADR (:52-60 — the grep target exists fleet-wide, verifier-confirmed scaffold.py:284 seeds it), and the HUB-mode heading no longer blankets step 3 as N/A — steps 3–4 apply there, because the hub's own ledger (D-048/D-050…) records accepted deviations too (:43). Rulings received ride close-feedback. One-way field block N/A — nothing mutates |
| (c) rigor scales with irreversibility | FIXED — the T21-class secrets carve-out was missing: a pool unit auditing a NON-secrets pack (deployment, 12-factor) could receive an inlined `.env`/compose excerpt carrying a literal secret; pool excerpts now exclude secret-material content, the needing pack gets the NATIVE finder, unavoidable excerpts are redacted (:82-89). Otherwise conformed: HUB mode reviews packs "harder than product code" with the theatre-glob check (:25-37); native finders for authoritative/high-risk packs (:76-77); "a rule that cries wolf gets ignored — that is how a rule dies" (:34) |
| (d) labeled verified/assumption evidence | CONFORMS — `UNVERIFIABLE-FROM-EXCERPTS` flags are finder QUESTIONS never findings (:88-92, :113-115); every flag AND citation verified "exhaustively, not a sample; a fabricated citation survives exactly as long as nobody opens it" (:92-94); "Labels lie; the code is truth" (:45-46); ✅ COMPLIANT never stands without a spot-checked path:line (:117-118); honesty rules ban unproven compliance and invented gaps (:158-159) |
| (e) captured disorder | CONFORMS — every GAP notes where already tracked (:96-99); pack defects filed upstream, never fixed in place (:22-24, :156-157); volatile items marked, residual-risk notes (:158-159); skipped packs STATED with why (:70-71); close-feedback rides |
| (f) most-reversible default under ambiguity | CONFORMS — READ-ONLY end to end; the audit converges COMPLETENESS, "fixing is a separate, user-authorized step" (:127-128); "do NOT edit anything unless I say so" (:161); spec-consistent-off is not a gap (:48-51); refuted gaps reclassify to 🟡 on evidence (:115-117) |

6/6 adjudicated: 3 CONFORMS, 2 FIXED, 1 N/A-with-read-side-fix.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 5 candidates: **3 CONFIRMED** (the HUB-mode Phase-0 heading blanketed step 3 — including my fresh ledger-read fix — as N/A, contradicting the :26-27 prose and skipping the ledger exactly where D-048/D-050 live → heading fixed; the T21 secrets carve-out absent from pool-excerpt inlining — a non-secrets pack's unit could ship a literal secret to a pool API → carve-out added :82-89; three anchors drifted 2-3 lines → corrected) · **1 PLAUSIBLE-high ADOPTED** (bare `--findings <n>` made TERMINAL unreachable for standing-gap projects — the D-048 class, unfixed for the audit loop; counting semantics added :132-137; the sibling design-review shares the ambiguity — noted for its ticket) · **1 CONFIRMED noted** (render staleness — the merge render carries the fixes; --check's HAND-EDITED flag is the expected mid-ticket state). Angles CLEAN: scaffold seeds DECISIONS.md fleet-wide (:284), close-feedback auto-append confirmed, table arithmetic + line count correct, ~24 anchors verified | 3 further source edits + artifact re-grounding; anchors re-derived post-edit (+11 net shift absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — :43 heading, :52-60, :82-89, :132-137 re-read post-edit; drifted anchors re-derived (:92-94, :70-71, :127-128) | TERMINAL no-op |

Verifier falsification streak: 25-for-25 — headline: my fresh fix was scoped OUT of HUB mode by a heading I had read past, and the audit loop carried the exact TERMINAL-unreachability class D-048 had just fixed for reviews.

## Per-finding disposition ledger

1. HUB-mode scope contradiction (CONFIRMED) → heading fix: steps 3–4 apply in HUB mode (:43).
2. Missing secrets carve-out (CONFIRMED, T21 class) → pool-excerpt carve-out + redaction rule (:82-89).
3. Anchor drift ×3 (CONFIRMED minor) → corrected (:92-94, :70-71, :127-128).
4. TERMINAL-unreachability ambiguity (PLAUSIBLE-high, D-048 class) → counting semantics fixed (:132-137); design-review's shared ambiguity noted for its own surface (already merged T02 — recorded here as a standing observation for T34's receipt, not a re-open: the D-048 fragment fix already governs its rendered term- semantics via the corpus rules; design-review's bespoke round line is chat-plus-record and its rounds feed the same command_run).
5. Render staleness (CONFIRMED expected) → merge render carries the fixes.
