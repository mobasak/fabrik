---
description: Execute a CONVERGED deployment plan — stage 3 of the deploy triad. OPERATOR-DISPATCHED ONLY (Gate-2: runs only on the operator's explicit invocation THIS turn — never self-triggered or auto-chained). Hard-refuses any plan not Status: CONVERGED. Runs the runbook step-by-step with per-step verification, maintenance-window (autoheal-pause) bracketing, and the plan's battery as the exit gate; store surfaces execute up to THEIR human publish gate and stop. TRIGGER — EN: "deploy it", "run the deploy plan"; TR: "dağıt", "deploy planını çalıştır" — an explicit operator dispatch, never an inferred one. SKIP: authoring the plan (→ /fabrik-deploy-plan) · converging it (→ /fabrik-deploy-plan-review) · post-deploy certification (→ /fabrik-deploy-verify). Stage: 6-release.
argument-hint: "<path to the CONVERGED deploy plan — docs/development/plans/YYYY-MM-DD-deploy-<service>.md>"
---

Execute this service's **converged deployment plan** — the runbook IS the authority; this command carries
it out and proves each step, it does not redesign mid-flight. A step that fails does not get improvised
around: the plan's own rollback column is the response, and an unplanned situation is a `BLOCKED`, never
an invention.

## ⚠️ Hard gates — check BOTH before any action

1. **Operator dispatch (Gate 2, inherited from `/fabrik-release` R14).** This command runs ONLY when the
   operator explicitly dispatched it THIS turn. It is never self-triggered, never auto-chained from the
   plan review, never run "since the plan converged anyway". If you arrived here any other way, stop and
   hand the decision back.
2. **`Status: CONVERGED` only.** Read the plan's header. Anything else — `DRAFT`, `IN-PROGRESS`, absent —
   → refuse: `BLOCKED: plan not CONVERGED — run /fabrik-deploy-plan-review first`. This echoes the
   data-contract FROZEN gate: nothing executes against an unconverged artifact. A plan edited AFTER its
   convergence flip is `DRAFT` in fact — if the file's mtime/git log contradicts the header, refuse the
   same way.

## ⚠️ Termination contract

You are done when EVERY runbook step has run with its verification **PASS (fenced output, this run)**, the
plan's battery (its exit gate) is green, the maintenance window is provably closed (unpause verified), the
plan is flipped `CONVERGED → EXECUTED <date>` and archived, and the 6-line FINAL OUTPUT block is printed —
OR you have stopped at a `BLOCKED` with rollback state honestly reported. Store surfaces are done at their
**human publish gate**: prepared, verified, handed off — ending there IS success, not an incomplete run.
**Context is never a reason to stop:** the harness auto-compacts and the run continues — keep going.

## Phase 0 — Resolve + pre-flight

1. Read the plan fully: surface, target, runbook, battery, rollback columns, `OPERATOR-GATE` markers.
2. Verify the code state the plan deploys is real: committed AND pushed (`git log origin/<branch>..HEAD`
   empty for the service repo) — a VPS deploy runs `git pull` from the remote; local-only commits deploy
   nothing (the same reason `fabrik redeploy` without a push is a HARD STOP).
3. Run the plan's own pre-flight guard steps (secrets-injection preview, headroom check, staged-config
   validation) — each with fenced output. Any pre-flight failure → stop BEFORE mutating anything:
   `BLOCKED: pre-flight <step> — <evidence> — nothing deployed`.
4. Honor the plan's env knobs verbatim (e.g. `FABRIK_BUILD_TIMEOUT=1200` for heavy images — the deployer
   reads it per `deployer_ssh.py::_BUILD_TIMEOUT`). Background any step likely >30s and monitor it —
   never block the session on a long build, never abandon it either.

## Phase 1 — Maintenance window open (VPS surfaces with a healing-sensitive step)

If the plan brackets a window (migrations, module init — any step a healthcheck outlives): open it FIRST
and arm the safety net so an aborted run can never leave healing disabled:

```bash
ssh <target_vps> 'mkdir -p /run/fabrik-autoheal && touch /run/fabrik-autoheal/pause'
trap 'ssh <target_vps> rm -f /run/fabrik-autoheal/pause' EXIT
```

Verify the pause took (the healer logs `PAUSED` on its next tick — or `stat` the file). The pause file
self-heals after 2h staleness, but the trap is the contract: no exit path leaves the window open.

## Phase 2 — Execute the runbook, step by step

For each step, in the plan's order:

1. Run the step's exact command (an `OPERATOR-GATE` step is NEVER run — see Phase 4).
2. Run its verification; the fenced output must show the plan's expected result BEFORE the next step
   starts. A verification you didn't run is a step that didn't happen.
3. On failure: apply the step's rollback column, then retry ONCE if the plan says the step is retryable.
   **3 failures on the same step → stop**: execute the plan's rollback for every completed step that
   requires it, then report `BLOCKED: <step> — <evidence> — <rollback taken>`. No improvisation: a
   situation the plan didn't anticipate is a plan defect — stop, report, route back to
   `/fabrik-deploy-plan-review`; never redesign the deploy mid-run.

Close the maintenance window at the point the plan says (verify the `rm` landed and the healer resumed) —
not "at the end" if the plan closes it earlier.

## Phase 3 — Battery: the exit gate

Run the plan's verification battery in full — write-path probe, queue-drain, companion reachability,
cert/ACME diagnostics, same-origin probes, per the plan — each item PASS with fenced output. **The battery
is the deploy's exit gate:** any FAIL means the deploy is NOT done — fix via the plan's named rollback/
retry path or stop at `BLOCKED` with the battery table printed. Never report a deploy complete on a
partial battery.

## Phase 4 — Store surfaces: stop at the human gate

Mobile / extension / desktop runbooks execute up to — never through — the publish act: build the artifact
from the pushed SHA, verify it (the plan's battery analogue), upload a DRAFT where the plan sanctions it,
prepare listing/rollout content. **The submit click (`eas submit`, the Web Store "Submit for Review", the
release publish) is the operator's** — print the handoff exactly as `/fabrik-release` R14 mandates: the
artifact, the verdicts, and the one action only the human takes. Ending at the handoff IS this surface's
completion.

## Phase 5 — Close out

1. Flip the plan `Status: CONVERGED → EXECUTED <date>` + a one-line completion stamp (what shipped, the
   battery verdict), and archive it per the plan lifecycle
   (`git mv docs/development/plans/<plan>.md docs/development/plans/archived/<plan>.md`) — a finished
   deploy plan left active misleads the next agent into treating it as open work.
2. Confirm the maintenance window is closed (fenced `stat`/log evidence) even though the trap should have
   done it — verify, don't trust.
3. Hand off: the next command is `/fabrik-deploy-verify` (VPS surfaces — fresh-probe certification of the
   live service) or the operator's publish act (store surfaces).
4. Print the 6-line FINAL OUTPUT block (GATE / DOCS UPDATED / CHANGELOG / LESSONS LEARNT / DONE / NEXT)
   per `CLAUDE.md` — `DONE:` states what actually deployed (SHA, target, battery verdict), `NEXT:` names
   `/fabrik-deploy-verify` or the operator gate precisely.

Next command: /fabrik-deploy-verify — prove the deployed service against its live checklist.
