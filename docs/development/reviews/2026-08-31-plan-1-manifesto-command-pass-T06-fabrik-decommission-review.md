# T06 — /fabrik-decommission: 63b manifesto conformance

Status: CONVERGED — author fix falsified and re-fixed (two-row semantics); closing round new: 0

Surface: commands/_sources/fabrik-decommission.md (read in full; 182 lines pre-fix, 190 post-final-fix; SOURCE-relative grep-derived anchors) + rendered composition (run-record + grounding-artifact + close-feedback, T01-swept).
Outcome: the author's pre-applied fix was itself FALSIFIED (6th consecutive falsification): "that row grows" violated row immutability, had no owner, and classified a future act at mint. Re-fixed to two-row semantics: a REVERSIBLE retirement row at Phase 2; the destroy is a NEW decision whose executor mints the superseding ONE-WAY row. Z1 also caught the check-without-procedure gap — the bookkeeping steps now instruct the mint.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors) |
|---|---|
| (a) checkable gates | CONFORMS — the receipts table is the terminal condition, "a cell filled from memory instead of a fresh command is not a receipt" (:19-21); the two-form Output makes a paused run machine-PARSEABLE as distinct from an executed one (:133-136, :145-160) — verification of the correspondence rides the receipts law + the run record, per the rollout law (no decommission-specific checker exists; enforcement candidate only on measured need) |
| (b) ledger routing + one-way field block | FIXED — a decommission is the ledger's "retirement/adoption" trigger verbatim, yet the source never mentioned docs/DECISIONS.md (grep: 0 pre-fix). The receipts table now carries a Decision-ledger row minted in Phase 2's own change, classified REVERSIBLE at mint (nothing irreversible has happened); the destroy is a NEW decision — its executor mints the superseding ONE-WAY row with the § Binding block in THAT change (immutability preserved); the Phase-2 bookkeeping steps instruct the mint and the teardown citation carries the obligation (surface count 9 coherent) |
| (c) rigor scales with irreversibility | CONFORMS — the command IS Phase-0 triage in operational form: three outcomes ordered by irreversibility, the truly ONE-WAY act (the VPS-side wipe, `_destroy_compose` … `sudo rm -rf` cited at destroyer.py:338-340) explicitly named irreversible (:75-80) and NEVER executed here — always the operator's own act |
| (d) labeled verified/assumption evidence | CONFORMS — liveness only from a probe run THIS session; "never a catalog/PORTS/env row as evidence" (description :2); the captcha same-day retraction is the institutional lesson cited twice (:64, :103); grounding-artifact fragment (:29) |
| (e) captured disorder | CONFORMS — 9-surface receipts with per-cell evidence; the memory record separates archived-source from dead-service; the AWAITING form records the paused state honestly |
| (f) most-reversible default under ambiguity | CONFORMS — inconclusive liveness → re-probe, never a verdict either way (:44, echoed :159/:174); a consumer with no migration path → STOP as named outcome C (:66); the Phase-1.5 operator gate is the sanctioned irreversible-action ask, applied to ALL THREE outcomes (:84-89) |

6/6 adjudicated: 5 CONFORMS · 1 FIXED-after-falsification.

## Scoped verification review

| pass | finders | found | new | fixed | verdict |
|---|---|---|---|---|---|
| Pass 1 | 1 native author-blind verifier: the pre-applied fix + all anchors + destroyer.py ground-read + surface-count re-derivation | 6 | 6 | 5 | Z1 procedure gap FIXED · Z2 immutability/owner/timing unsoundness RE-FIXED (two-row semantics) · Z3 line count FIXED · Z4/Z5 anchors FIXED · Z6 (a) wording re-adjudicated (parseable ≠ verified; rollout law governs) |
| Pass 2 (closing, method: gate) | mechanical: both new clauses grep clean; no "grows" residue; 9-surface count re-verified; anchors re-derived | 0 | 0 | 0 | → EXIT |

## Per-finding disposition ledger

| # | finding | state |
|---|---|---|
| Z1 | the fix wired the CHECK (receipts row) but not the PROCEDURE (Phase-2 bookkeeping never instructed the mint) | FIXED — bookkeeping bullet added, minted in the same change |
| Z2 | "that row grows" = editing an immutable row, for an unowned future act, classified before it happened | FIXED — reversible row at Phase 2; the destroy's executor mints the superseding ONE-WAY row in the destroy's change; the teardown citation carries the obligation |
| Z3 | artifact line-count wrong (186 vs 183) | FIXED |
| Z4/Z5 | two (f) anchors mis-cited | FIXED (:66, :44) |
| Z6 | (a) claimed structural distinguishability where only parseability exists | FIXED — cell reworded; checker candidate deferred to the rollout law |
