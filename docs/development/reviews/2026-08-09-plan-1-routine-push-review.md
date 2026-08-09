# Whole-plan validation — 2026-08-09-plan-1-routine-push

Surface: `f5c71bde` (Stop-hook 4th cause) + `cef3be75` (governance sweep) + the adjudication fixes this
round + the live-FP fix `1df51065` (conditional-offer exemption, caught when the guard fired on its own
author mid-run). Native finder seat + orchestrator adjudication (NO-POOL: hooks + governance).

## Coverage Checklist

| class | verdict |
|---|---|
| Hook correctness (counter slots, cause scoping, warn-through) | FIXED(1): p-slot reset-when-false on gate/commit block writes (the stranded-counter class, probe-proven mis-numbering) — multi-stop red-first test added (the old harness unlinked counters between stops and could never see it) |
| Governance coherence (one ladder, every surface) | FIXED(3): execute-plan loop-summary still offered push/hold (stale menu, same file as the new §Finish) · routing-doc human-gates row still taught push-is-operator-authorized + control-loop framing listed push as irreversible actuation · .windsurfrules ladder lacked the conflict-abort leg |
| Ladder truth vs git reality | FIXED(1): `pull --rebase` LINEARIZES the Merge Protocol's own `--no-ff` merge commits (probe: `git log --merges` empty after rebase) — corrected to `git pull --rebase=merges` on all six surfaces, probe-proven to preserve the merge commit through divergence and push clean |
| Safety (force ban, never-bundle, deploy law) | CLEAN — probe/grep verified: no push-triggered deploy exists in CI; force ban + refs/wip exception intact on every surface; never-bundle verbatim |
| Live incident folded in | FIXED(1): promise-guard fired on its own author's "say the word and I'll run it" — conditional-offer vocabulary added to the line-scoped exemptions, red-first with the verbatim sentence (`1df51065`) |

## Residuals (accepted, documented)

- Divergent-remote + permanently-dirty tree (the hub when siblings are mid-work): the correctly-deferring
  agent re-enters a bounded 3-block/warn-through cycle at each task end until someone pushes — this
  nagging is the operator-intended pressure; never traps (cap holds, probe-verified).
- A worktree resumed on an upstream-tracking branch IS push-blocked mid-plan (benign: pushing one's own
  ticket branch, never force) — the plan's "worktrees exempt by construction" holds only for the
  `--detach` creations execute-plan itself makes.
- Force-push to one's OWN unshared branch is no longer covered by any ban (deliberate narrowing; shared
  branches + foreign branches remain hard-stopped).

## Round ledger

- Round 1 (native finder, 4 classes, sandbox probes): found: 7 (4 CONFIRMED, 3 PLAUSIBLE) + 1 live FP
  mid-run = 8.
- Round 2 (fixes): fixed: 6 · accepted-residual: 2.
- Round 3 (confirming, fresh): 67 stop-hook tests green (incl. the new multi-stop strand test and the
  verbatim-FP test) · corpus `--check` OK · `--rebase=merges` probe (merge commit survives divergence,
  push OK) · fresh full gate: **found: 0 · fixed: 0** — quiet.

## Gate (verbatim, this round)

```
$ python scripts/final_gate.py --check --json
{"status": "success", "tier": 2, "passed": 45, "failed": 0}
```

## Phase verdicts

- **Phase A** (hook): cause fires only on upstream-ahead; indeterminate (no upstream/detached/deleted
  origin) allows — probe-verified; 4-slot counters backward-compatible; warn-through + re-arm proven.
  Live self-demonstration: the cause's first firing was on its own author's commit, and the push cleared it.
- **Phase B** (prose): one law on six surfaces, ladder identical everywhere (post-fix); the stale
  .windsurfrules commit ban died; deploy remains trigger-not-execute, operator-run.

reviewed — sign-off.
