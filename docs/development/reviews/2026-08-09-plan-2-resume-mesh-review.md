# Whole-plan validation — 2026-08-09-plan-2-resume-mesh

Surface: the five workstation files (`~/.claude/bin/`: claude-sound.sh failure-branch mesh block +
mesh-notify, claude-stop-decider.py clear/interlock/prune/Telegram-spawn, claude-autoresume.sh,
claude-selfwatch.sh, claude-mesh-test.sh) + repo docs. Native finder seat (read all five fully, ran
the harness 4×, three ad-hoc empirical probes incl. a neutered-ring vacuity proof) + orchestrator
adjudication (NO-POOL: hooks/workstation shell).

## Coverage Checklist

| class | verdict |
|---|---|
| Shell correctness (set -u, quoting, injection) | CLEAN post-sweep — no injection (case-match/printf only, --data-urlencode); arithmetic guards everywhere; one documented residual (spacey-path MESH_ROTATE_CMD split) |
| Concurrency | FIXED(3): the K=2 held-slot design was DISPROVEN (slot held across a full resumed run + 5-min steal dismantles the guard mid-storm; TOCTOU steal race) → replaced by a serialized-start mutex (≥15s spacing, 60s stale steal, spec-amended); wedged start.lock now stale-stolen; the decider's prune no longer aborts on directory locks (IsADirectoryError → rmdir — the mesh introduced the first dirs into a files-only janitor) |
| Semantics vs spec | FIXED(5): production Telegram keys were read from a file that has none on this box (VPS pattern vendored blind — keys verified by name in `/opt/fabrik/.env`, `TELEGRAM_CHAT_ID` not `OWNER_ID`); the ring re-fire now carries the ORIGINAL transcript+cwd (the no-transcript branch was bypassing notify on the headless-exhaustion case — the mesh's flagship target); ring ⇒ truly-dead now holds on the 2a path (`.reviving` interlock: fresh flag → decider silent, stale 35-min flag → ring); cleared-marker abort (never a second writer on a survived session); attempts/reviving cleared on survival (fresh cap per future death) |
| Reliability | FIXED(1): rc≠0 on attempt 1 no longer stalls silently — two in-process attempts 60s apart, then ring |
| Harness quality | FIXED(3): the vacuous ceiling-ring assert (proven by a neutered-ring 28/28 pass) is session-scoped; the rc-fail leg has coverage; storm determinism moved to the mutex-critical-section `starts.log`; the tautological ≤2-slots assert died with the slots; rotation-shim settle wait |
| Regression | CLEAN: decider 34-fixture self-test green throughout; done/attention branches untouched; the one interaction (prune-vs-directories) found and fixed |

## Round ledger

- Round 1 (finder, 6 classes, empirical probes): found: 11 (7 CONFIRMED, 4 PLAUSIBLE) + minor notes
  (notify stamp burn, sync notify stall) — all accepted.
- Round 2 (fixes): fixed: 11 + both minor notes (stamp-on-success; async decider-MISSING notify);
  1 design amendment recorded in the spec (held-slots → serialized starts).
- Round 3 (confirming, fresh): mesh-test **35/35 twice** (determinism), decider self-test green,
  key-name verification for the Telegram file, gate below: **found: 0 · fixed: 0** — quiet.

## Build-session live notes

- The self-watch is armed on the build session itself (first real 2b consumer) — the spec's one
  extrapolated residual (Monitor-wake into a dead pane) confirms at the next genuine StopFailure;
  failure mode is today's ring, no regression.
- Mid-build incident, operator-reported: the first harness version rang REAL sounds (absolute-path
  media/Pulse escaped the sandbox HOME) — fixed by pointing both at dead paths; the harness has been
  silent since.

## Gate (verbatim, this round)

```
$ python scripts/final_gate.py --check --json
{"status": "success", "tier": 2, "passed": 44, "failed": 0}
```

reviewed — sign-off.
