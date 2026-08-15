# Whole-plan validation review — login-once credentials (2026-08-15-plan-1)

Plan: `docs/development/plans/2026-08-15-plan-1-login-once-credentials/` · Spec:
`docs/superpowers/specs/2026-08-15-login-once-credentials-design.md` (CONVERGED, 2 cycles) ·
Baseline: 6250ada3 (lock-recorded; lean gate ZERO reds at start) · Range: 6250ada3..HEAD ·
Date: 2026-08-15.

## Per-ticket verdicts

| Ticket | Merged | Rounds | Verdict | Ledger |
|---|---|---|---|---|
| T01 disarm + pause gate | fa2cb7fb (tip 095942b9) | 8 | CLEAN close | `-T01-review.md` |
| T02b fleet gitignore carrier | a4446e4a (tip 0f7b6401) | 1 + acceptance fixes | CLEAN | `-T02b-review.md` |
| T02a fleet-dir scaffolder | 713699eb (tip 398e672d) | 3 (F36–F53) | CLEAN, 2 accepted residuals | `-T02a-review.md` |
| T03 fleet telemetry + keepalive | 35dbfffb (tip ccfd5357) | 2 (F54–F58) | CLEAN, 1 accepted residual | `-T03-review.md` |
| T04 runbook rewrite | 81427be0 (tip b4376f2a) | 1 + 8 acceptance fixes | CLEAN (claim-table ~90 TRUE) | `-T04-review.md` |

34 total review rounds/fix items across the plan (18 fixes T02a, 5 T03, 8 T04 acceptance, plus
T01's 34 fixups over 8 rounds); every round ran pool breadth (2–3 recorded finders) + ≥1 native
Opus-class authoritative leg, per-round scores back-filled to the flywheel.

## T05 integration receipt

- `check_doc_sync.py --range 6250ada3..HEAD` → rc 0 (2 WARNs adjudicated: the INDEX rows are
  added in this closing commit; `docs/RESILIENCE.md` does not exist in the hub — project-repo
  matrix row, and the new cron is documented in `docs/workstation/claude-account-rotation.md`).
- `check_doc_stubs.py --range 6250ada3..HEAD` → rc 0.
- `check_convergence.py` → rc 0.
- Cross-ticket seam (T02a→T03 assignments/fleet-root interface): the merged four suites on
  master — 182/182, twins md5-identical (5c239113…).
- Full Tier-2 gate, verbatim (run this session on the merged master; the one advisory warning
  is a sibling's untracked file, not this plan's):

```json
{
 "status": "success",
 "tier": 2,
 "passed": 46,
 "failed": 0,
 "failures": [],
 "warnings": [
  {
   "check": "untracked sources (advisory)",
   "output": "⚠ 1 untracked source file(s) NOT in gate scope (unstaged → unscanned): .serena/project.yml — if yours: `git add` them and RE-RUN the gate (they ship unlinted otherwise); if a sibling's: leave them."
  }
 ]
}
```

## Docs-review convergence (Pass Ledger)

Scope: `docs/workstation/claude-account-rotation.md` + `docs/workstation/hooks-index.md` +
the plan's six CHANGELOG entries.

```
Pass 1 — T04 native claim-verify (~90 claims) + pool consistency | discrepancies: 8 | edits: 8 (acceptance fixes, 81427be0)
Pass 2 — pool (minimax-m3, deepseek-v4-pro) + native opus verifier | discrepancies: 6 | edits: 6 (df7a9251 + 6a6cd43d)
Pass 3 — orchestrator full fresh re-read vs established code facts | discrepancies: 0 | edits: 0 | → CONVERGED
```

md5 at convergence: `4b70257c…` (claude-account-rotation.md) · `bde6e038…` (hooks-index.md).
Pass-2 REALs (both residue of pass-1 fixes, both code/execution-confirmed by the native leg):
the `--sync-mcp` absent-root rc (1, not 0) and the refusal-#2 recovery step missing the
`identity` reset. `docs_updater.py --check` residual: docs/CONFIGURATION.md age-staleness
(111 days — pre-existing, untouched by this plan).

## D7 whole-plan validation — found: 0

Finders: 3 pool lenses (credential-safety: 0 REAL; integration seams: 0 confirmed —
`run_claude`'s legacy 401-retry naming on a fleet box is the DESIGNED legacy path, pause-gated
and swept at M4; test-contract: CLEAN, full coverage) + the native authoritative seat:
**VALIDATED, 0 REAL/blocking**. Requirements-coverage table complete (zero-recurring-logins
posture, successor-free fleet tick, 4-account telemetry, keepalive, carrier+occupancy monitor,
M2/M3 runbook + abort signal, M3–M5 correctly deferred). Live box state verified this session:
both cron lines present, drift-check cron+hook gone, switch-paused marker armed, fleet root
absent (pre-M3), legacy `--status` live with `"pause":"marker"`.

Closing quiet round (D7): found: 0, fixed: 0 — no edit was made in response to the D7 sweep;
its NIT-level observations are recorded under Residuals below.

## Residuals (named, accepted)

1. T02a: `_new_dir_locked` compares resolved `repo` vs the row's raw `bound` (fail-closed
   false refusal on hand-edited/symlink-aliased rows only) + the F44 sync mtime-recheck
   microsecond window. Both re-confirmed by D7's ledger-honesty check.
2. T03: the real unmocked `_mailbox_repos()` is never exercised end-to-end (every test
   monkeypatches it; production default unchanged).
3. 4 new mypy-visible type-narrowing false positives in `claude_rotate.py` (:1742, :2605,
   :2825×2) — mypy does not run against `scripts/` in the gate; each traced to provably
   unreachable None-paths, no functional bug.
4. The spine's Behavior-Contract rows cite plan-time line anchors that drifted as ~1600 lines
   landed; the per-ticket ledgers and this receipt carry current cites. The spine is the
   plan-as-approved record — left as written.
5. Pre-existing, out of plan scope: `_is_live_store` dead since before baseline;
   docs/CONFIGURATION.md age-staleness.

## Successor-plan pointers (recorded during execution)

M4 retirement sweep (sound-system mesh legs as a named owned step; cost-model repoints; DR
exclude-credentials), M5 thinning, VPS follow-up (M4+30d deadline), worktree carrier copy
helper, saas/static scaffolder .gitignore clobber, ledger append-leg fail-open, corrupt-ledger
growth cap, stale fleet-sync doc lines (docs/operations/wsl-environment.md:41,
docs/infrastructure/vps-complete-inventory.md:12), spec-vs-code notes (identity pins at first
status/tick; hub is env-only by design).

## Self-audit

Every ticket merged via squash-apply with `Agent-Role: orchestrator` + `Agent-Task` trailers;
explicit pathspecs on every commit; each merge re-ran the four suites on the MERGED tree
before committing; every gate/suite claim in this receipt was run in the session that wrote
it. Operator-facing next step: the M3 login rounds (guided batches per the runbook §M3).
