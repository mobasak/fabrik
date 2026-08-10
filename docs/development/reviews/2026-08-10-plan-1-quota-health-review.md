# Review receipt — plan 2026-08-10-plan-1-quota-health (all 5 phases)

Plan: `docs/development/plans/2026-08-10-plan-1-quota-health.md` (CONVERGED → EXECUTED)
Spec: `docs/superpowers/specs/2026-08-10-quota-health-design.md` (CONVERGED, operator-approved)
Surface: `~/.claude/bin/{claude-quota.py,claude-sound.sh,claude-selfwatch.sh,claude-autoresume.sh,claude-reboot-sweep.sh,claude-mesh-test.sh}` (box, DR-versioned) + `scripts/sysadmin/claude_rotate.py` + `scripts/aro-wake/claude_rotate.py` + `.claude/hooks/session_orient.py` + `tests/{test_claude_rotate_capture.py,test_session_orient_hook.py}` + `docs/workstation/{hooks-index.md,claude-configuration-inventory.md}`

## Whole-plan gate (verbatim, this run)

```
FULL GATE: success 35 / 0
convergence_rc=0
mesh-test: 114 ok, 0 fail
claude-quota.py --self-test: all green (39 fixtures)
pytest tests/test_claude_rotate_capture.py: 19 passed
pytest tests/test_session_orient_hook.py: 17 passed
```

Green is necessary, not sufficient — the proof is the per-phase evidence below.

## Per-phase verdict

| Phase | Delivered | Review rounds | Defects fixed | Gate |
|---|---|---:|---:|---|
| A — `claude-quota.py` | wall parse ladder, per-account state (0600, atomic, bounded history), the ONE wait computation, 5 subcommands | 4 | 14 | `mesh-test: 80 ok, 0 fail` |
| B — mesh integration | record-at-death, health-aware switch-or-wait, announce, sliced clock-waits in both revival layers | 3 | 10 | `mesh-test: 95 ok, 0 fail` |
| C — token re-capture | `--capture-current` / `--drift-check` + 3 triggers | 2 | 6 | 19 tests, lean 25/0 |
| D — reboot sweep | `claude-reboot-sweep.sh` + fleet-synced autonomous marker | 2 | 8 | `mesh-test: 113 ok, 0 fail` |
| E — flip + docs + receipt | AUTOROTATE default-ON, docs, this receipt | — | — | FULL 35/0 |

**36 defects found and fixed by the phase reviews.** The ones that would have shipped silently:

1. **The manager tap reports AMBIENT usage, not exhaustion** (Phase A, native) — a transient 429 at 40% utilization would have scheduled an hours-long sleep. Fixed with an exhaustion threshold; then the fix's own priority inversion (a 100%-used 5-hour window outranking a 99%-used weekly one, waking straight into the weekly wall) was caught by the confirming round and fixed: among exhausted windows the LATEST reset binds.
2. **Rotation verified the healthy sibling, then blind-picked `--next`** (Phase B, native, reproduced against the operator's real 3-account layout) — it could rotate INTO another walled account, defeating the entire feature. Now targets `--switch <verified>`.
3. **Drift-check compared only the ACCESS token** (Phase C, pool) — but the live incident was a stale REFRESH token, which rotates independently; an unchanged access token would have hidden exactly the defect this phase exists to prevent. Now byte-compares the whole credential.
4. **The hourly drift-check cron never ran** (Phase C, native, empirically reproduced) — it logged to `/var/log`, which this user cannot create, so the shell failed before the command. Now `~/.claude/drift-check.log`, verified end-to-end through cron's exact command line.
5. **`@reboot` also fires on a cron-daemon restart** (Phase D, native) — with no liveness check the sweep would resume sessions whose original writer is still alive (the second-writer failure). Now gated on transcript-liveness.
6. **The offline ceiling was measured from the original death** (Phase B, native) — after a multi-hour quota wait, the first network hiccup would ring instantly. Re-baselined after the wait.

Two defects were caught by the harness itself rather than a finder: fixtures reading the operator's **live** accounts (missing `CLAUDE_QUOTA_HOME` isolation), and a PATH-order regression where a real `claude` binary shadowed the test shim.

## Live effect (verified on the box, not asserted)

- **The 12:05 login failure's root cause is closed.** mob@'s stored snapshot was 1.5 days stale; the drift-check captured the freshly-authenticated credentials and live↔snapshot is now **byte-identical** (verified by comparison, no token bytes shown).
- Rotation is default-ON but can only switch to a verified unwalled account; `CLAUDE_SOUND_AUTOROTATE=0` is the escape hatch.
- A quota wall now schedules revival at the reset clock and Telegrams "revival scheduled in Nm".
- `@reboot` resumes autonomous-marked, mid-work, not-still-live sessions — panes stay manual by construction.

## Residuals (accepted, documented)

- **Marker-resolved identity** (Phase C): when a refreshed token matches no snapshot, identity falls back to `.active-account`, and a legitimate refresh is indistinguishable from an out-of-band login as another account. Refusing those captures would block the primary use case, so capture proceeds with `.prev` as the one-generation recovery. Revisit if the CLI ever exposes an account id inside the credential blob.
- **Consume-before-spawn** (Phase D): a marker is consumed before the resume starts, trading "a crashed resume is lost" for "no marker re-resumes on every boot". Deliberate; stated in the script header.
- **`overage` delivery channel** (Phase A): no grounded channel delivers `overageStatus` to the hook payload, so it is pinned conservatively (wall only with a parseable reset). Resolves at the first live overage via the payload capture.
- **INDEX.md**: the drift the FULL gate flagged belonged to a sibling's 06:30 fleet-audit report, not this plan; the missing line was appended (a shared-append governance surface), not edited into their file.

## Self-audit

Every phase ran its blocking `/fabrik-review` to a coverage-adjudicated exit (native + pool finders, refute-then-fix, re-verified gate, confirming round). Every fix carries a fixture that was watched RED first or is proven red-on-revert by construction. All box files are DR-versioned (7 snapshots across the run); all repo files are committed with provenance trailers and pushed. The plan's own File Scope was respected; no sibling's file was edited.
