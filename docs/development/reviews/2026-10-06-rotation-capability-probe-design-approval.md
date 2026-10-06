# Design approval — rotation capability probe (W-f8bfe7eb)

**Status:** APPROVED (panel, D-613) · decision row D-616
**Artifacts:** `docs/superpowers/specs/2026-10-06-rotation-capability-probe-design.md` (CONVERGED, md5 4521df82169b0e81378c4ae491604d7d) and `docs/development/plans/archived/2026-10-06-plan-2-rotation-capability-probe.md` (CONVERGED, md5 6d78a9f2b1a0aecc1382da1d9e284747), commit ebc9190d5.
**Review ledger:** the plan's § Pass Ledger — 7 passes; the joint loop closed at confirmed 0 in Pass 4, the panel's changes re-opened it for Passes 5-7, which closed at confirmed 0.

## Ask ↔ spec

Built from the spec's own § Intake Inventory (8 items).

| I# | The ask (anchored) | Where the spec answers it | Disposition |
|---|---|---|---|
| I1 | "Spec the prevention half" (W-f8bfe7eb) | § The delta D1-D7 | IN |
| I2 | "probe-on-flip vs per-tick" | § Chosen approach (probe on promote, plus the active account's own 30-minute window and D7), § Rejected alternatives (every standby every tick) | IN |
| I3 | "claude -p vs a minimal OAuth messages call (undocumented contract — ground it first)" | § External dependencies G2; § Rejected alternatives (the raw Messages call is cut) | IN |
| I4 | "the quota cost" | § Cost (≤64 one-word calls a day fleet-wide; a refused account costs two) | IN |
| I5 | "auto-park on the refusal" | § The delta D3 (confirmed by a second probe), D5 (the lock) | IN |
| I6 | "W-ffd390d2 (alert hook) is the detection half" | reused alert path only | OUT-OF-SCOPE (already built) |
| I7 | "every health probe that checks credentials rather than the capability … has this blind spot" | § Open unknowns U3 → a backlog row at execution | OUT-OF-SCOPE |
| I8 | "fires hooks" | § The delta D1 (headless env) and D6 (one more session on the dir) | IN |

## Panel

Two `fabrik-reviewer` seats, one `model: "opus"` and one `model: "fable"`, the same brief, neither shown the other's answer.

| Round | Opus | Fable |
|---|---|---|
| 1 (md5 676a9b49 / 34c75795) | `VERDICT: sound-with-changes` — 4 concerns: the active window, the free session signal, the active-probe timeout, the billing-first alert | `VERDICT: sound-with-changes` — the 6 h answer (D7) plus 4 concerns: the shared-dir sentence, a confirmed refusal, the alert key, the board reason |
| 2 (md5 6d78a9f2 / 4521df82) | `VERDICT: sound — docs/development/plans/archived/2026-10-06-plan-2-rotation-capability-probe.md`; "the D7 route satisfies it, and I prefer it to the new command I proposed" | `VERDICT: sound — docs/development/plans/archived/2026-10-06-plan-2-rotation-capability-probe.md`; the neutral reason string is "ACCEPTABLE" |

Every concern was ACCEPTED (Opus's second through the in-repo D7 route, Fable's fourth as a neutral reason string), applied to both documents, and re-checked by delta rounds 5-7 of the review's round-1 seats before the second panel read.

Panel: opus="VERDICT: sound — docs/development/plans/archived/2026-10-06-plan-2-rotation-capability-probe.md" fable="VERDICT: sound — docs/development/plans/archived/2026-10-06-plan-2-rotation-capability-probe.md" → both-approve

Recorded for execution, not a gate condition: Fable's note that the promote and ping confirmations keep the 150 s default and could also use the 45 s bound (the same class as today's 3-slot ping) — destination: Phase A's `/fabrik-review-scoped`.

## Per-phase verdicts

### Phase 1 — design approval of the spec and plan: APPROVED

Both panel seats returned `VERDICT: sound` on the revised artifacts; the review loop behind them closed at confirmed 0 (Pass 7). The plan's Phases A, B and C are approved for `/fabrik-execute-plan` as written.

## Gate

`python3 scripts/final_gate.py --check --json`, run in the worktree with D-616 staged (this receipt added afterwards). The keys below are verbatim from its envelope; the static tier skipped because the staged diff is markdown-only, and the hub's pytest leg is off by design.

```json
{
  "status": "success",
  "skipped_checks": [
    "static tier",
    "Rule-pack reachability"
  ]
}
```
