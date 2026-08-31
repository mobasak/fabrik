# T09 — /fabrik-deploy-plan-review: 63b manifesto conformance

Status: CONVERGED — fix's commit recipe mirrored (both triad files); closing round new: 0

Surface: commands/_sources/fabrik-deploy-plan-review.md (231 pre-fix / 235 post-fix lines, read in full; grep-derived anchors) + rendered composition (run-record + term-edit + close-feedback, T01-swept).
Outcome: 1 FIX, itself falsified once (ninth consecutive): the row-mint INSTRUCTION landed but the staging/commit RECIPE still enumerated only plan+artifact — a literal executor would strand the row. Recipe now names all three; the identical mirror gap in fabrik-deploy.md (T07, merged) fixed via the sanctioned D4 back-flip in this commit. Flip-backs explicitly scoped as incident records (no row). Closes T07's ROUTED A1 for real.

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors) |
|---|---|
| (a) checkable gates | CONFORMS — term-edit's md5-verified no-op governs the flip (:15); the two-gate-run bootstrap sequence makes the artifact's green "proven, not asserted" (:196-207); the quiet-pass marker appears ONLY on a CONVERGED ending (:190-192) |
| (b) ledger routing + one-way field block | FIXED (twice) — the flip never minted a row (grep: 0); step 1 now mints it AND step 3's recipe stages it — (a) plan+row, (f) all three — because the verifier proved instruction-without-recipe strands the row (no gate watches DECISIONS.md); flip-backs scoped as incident records, no row (stated in-source); the same mirror landed in fabrik-deploy.md step 4 via back-flip |
| (c) rigor scales with irreversibility | CONFORMS — the status guard tiers the response precisely by what is live: NEVER flip a complete live deploy to BLOCKED (:60); IN-PROGRESS refuses unless the ledger proves completion (:61-64); EXECUTED refuses as consumed (:67) |
| (d) labeled verified/assumption evidence | CONFORMS — committed evidence only ("a console BLOCKED print alone proves nothing later", :48-49); every claim grounded against the live spec/compose/code/infra (description :2); the RE-ENTRY AUDIT reads the ledger as evidence, never a resume protocol (:70) |
| (e) captured disorder | CONFORMS — every status flip-back commits IMMEDIATELY (:55-57 — "an uncommitted flip is what the next pre-commit stash cycle silently reverts"); the persisted artifact anatomy with per-phase verdicts + class table + Pass Ledger (:180-195) |
| (f) most-reversible default under ambiguity | CONFORMS — every status value has a named disposition with a route (:36-67, allowlist-not-denylist); a deferred `[OPEN → at deploy]` item is a DEFECT, not a residual (:167-169) — the stall bucket is banned by name |

6/6 adjudicated: 5 CONFORMS · 1 FIXED (seeded). Pending: scoped verification.

## Scoped verification review

| pass | finders | found | new | fixed | verdict |
|---|---|---|---|---|---|
| Pass 1 | 1 native author-blind verifier: full read + diff isolation + fabrik-deploy cross-read + gate greps (zero DECISIONS awareness in check_convergence/final_gate — the omission is unguarded) + 9 anchors re-derived (all landed) | 3 | 3 | 3 | C1 recipe gap FIXED (both staging steps name the row) · C2 T07 mirror FIXED (back-flip) · C3 flip-back scoping FIXED in-source (incident records, no row) · post-flip-guard collision + reflip-noise both examined-sound (:70-75 scopes to the plan path; no-op reflips already refused) |
| Pass 2 (closing, method: gate) | mechanical: all three clauses grep clean in both files; emit gate exit 0 | 0 | 0 | 0 | → EXIT |

## Per-finding disposition ledger

| # | finding | state |
|---|---|---|
| C1 | step 1 minted, step 3's recipe stranded the row (literal-executor failure; unguarded — no gate reads DECISIONS.md) | FIXED — (a) and (f) name the row |
| C2 | the identical instruction-vs-recipe gap in fabrik-deploy.md (T07, merged) | FIXED — sanctioned D4 back-flip; both artifacts record it |
| C3 | other status flips (flip-backs) mint nothing — unjustified scoping | FIXED — scoped in-source: flip-backs are incident/evidence records (the ⛔ ledger), not decisions |
