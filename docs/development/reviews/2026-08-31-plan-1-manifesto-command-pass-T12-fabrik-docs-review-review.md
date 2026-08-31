# T12 — /fabrik-docs-review: 63b manifesto conformance

Status: DONE

Surface: commands/_sources/fabrik-docs-review.md (203 lines post-fix, read in full; grep-derived anchors) + the RENDERED command `~/.claude/commands/fabrik-docs-review.md` (315 lines at evaluation: grounding-artifact :10-30 · bespoke run-record block :31-48 · subagents-core :218-221 · close-feedback :222-315 — composition verified by section-heading grep, no drift vs source; re-rendered at merge).
Outcome: 2 source fixes (DEAD-retirement ledger routing; synced-docs denominator clause) + artifact re-grounding (3 wrong anchors, 1 ungrounded term, 1 loose range).

## 63b Verdict Table

| intersection | verdict (grep-derived SOURCE anchors, post-fix) |
|---|---|
| (a) checkable gates | CONFORMS — terminal = "an edit-free reconciliation pass with the doc-sync gate green" (:13); Pass Ledger last row `discrepancies: 0, edits: 0` + per-doc md5 recorded at final pass's start (:147, example :153); Phase 1's line-count-vs-claims-accounted reconciliation is a real denominator device ("if any line is unaccounted for, you skipped it — go back", :75-76) |
| (b) ledger routing + one-way field block | CONFORMS (after fix) — a DEAD sweep retiring a whole documented subsystem is now routed as a decision-shaped RETIREMENT minting its `docs/DECISIONS.md` row in the SAME change, while routine dead-line deletion stays doc hygiene (:171-174, this ticket's fix); ruling-shaped events additionally ride the rendered close-feedback decision line (rendered :222-315). One-way field block N/A — doc reconciliation mutates only prose, reversibly |
| (c) rigor scales with irreversibility | CONFORMS — the HUB lens reconciles synced docs HARDER because a wrong enumeration "will be copied into ~46 repos on the next sync" (:59-61) — blast-radius scaling stated; >100-claim ledgers may embed a representative subset WITH totals (:184-185 — the bound stated, not silent) |
| (d) labeled verified/assumption evidence | CONFORMS — five-verdict taxonomy (:106-110); live-checkable external claims are "VERIFIED-or-WRONG, never parked as UNVERIFIABLE" (:97-98); "The doc's own wording is never evidence for itself" (:87-88); DEAD audited "by real usage, not mere code-match" (:109); runnable examples RUN, not eyeballed (:85-86) |
| (e) captured disorder | CONFORMS — embedded claim ledger + per-verdict self-audit counts + zero-skipped-lines reconciliation (:184-189); residual risks the tooling can't catch explicitly listed (:194-198) |
| (f) most-reversible default under ambiguity | CONFORMS (after fix) — UNVERIFIABLE (internal-only, per the external VERIFIED-or-WRONG law) is a labeled residual with its why (:110), never a silent park; synced docs in a project are binding context, never reconciled, and now explicitly OUTSIDE Phase 1's claim-ledger denominator (in-denominator on the HUB, where they ARE reconciled) (:50-53, this ticket's fix) — the reversible posture toward surfaces the run must not mutate, with the denominator no longer undecidable |

6/6 adjudicated: 4 CONFORMS as-found, 2 CONFORMS-after-fix.

## Scoped verification review (nested /fabrik-review)

| round | findings | disposition |
|---|---|---|
| 1 — author-blind fabrik-reviewer verifier | 8 candidates: **4 CONFIRMED** (row (d) anchor :104→DEAD is :107 pre-edit; row (f) anchor :105→UNVERIFIABLE is :108 pre-edit; row (c) anchor :181-182→:179-180 pre-edit — systematic +3 miscount; row (b) stamped on "NOT-a-decision carve-out", a hub-CLAUDE.md term appearing NOWHERE in this command/manifesto, with zero anchors) · **3 PLAUSIBLE adopted** (DEAD-deletion-as-retirement unrouted to the ledger → source fix :171-174; synced-docs-as-context vs zero-skipped-lines denominator undecidable → source fix :50-53; rendered-command coverage asserted not evidenced → Surface line now carries rendered section anchors) · **1 minor adopted** (md5 range citation corrected to :147/:153) | 2 source edits + full artifact re-grounding; every anchor re-derived fresh via grep AFTER the edits (line shifts +2/+5 absorbed) |
| 2 — closing re-derivation sweep | found: 0, fixed: 0 — all 14 cited anchors re-grepped post-edit against the 203-line source + rendered section map re-verified | TERMINAL no-op |

Verifier falsification streak: 12-for-12 — the per-ticket author-blind floor remains measurably load-bearing.

## Per-finding disposition ledger

1. Row (d) wrong anchor (CONFIRMED) → fixed, :109 (post-edit).
2. Row (f) wrong anchor (CONFIRMED) → fixed, :110 (post-edit).
3. Row (c) wrong anchor (CONFIRMED) → fixed, :184-185 (post-edit).
4. Row (b) ungrounded term + zero anchors (CONFIRMED) → re-grounded on the new :171-174 clause + rendered close-feedback; the hub-CLAUDE.md carve-out vocabulary removed from the verdict.
5. DEAD-deletion retirement gap (PLAUSIBLE, adopted as REAL) → source fix: Phase 3 now routes subsystem-scale DEAD sweeps to `docs/DECISIONS.md` SAME-change (:171-174).
6. Rendered-coverage evidence gap (PLAUSIBLE, adopted) → Surface line now evidences the rendered composition with section anchors.
7. Synced-docs denominator ambiguity (PLAUSIBLE, adopted as REAL) → source fix: context-read synced docs excluded from the project-side claim-ledger denominator, in-denominator on the HUB (:50-53).
8. md5 range citation (minor, adopted) → :147/:153.
