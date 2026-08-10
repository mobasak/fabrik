---
description: Adversarially converge a DRAFT deployment plan to a fixed point — stage 2 of the deploy triad, the trust gate before any deploy. Grounds every claim against the live spec/compose/code/infra, runs the surface-conditioned coverage checklist (secrets flow · env completeness · staged-infra validity · ordering+timing · healing/rollout · battery · monitoring+DR truth), and flips Status: DRAFT → CONVERGED only on an md5-verified edit-free no-op round. TRIGGER — EN: "review the deployment plan", "converge the deploy plan"; TR: "dağıtım planını gözden geçir" — fires on an EXISTING deploy plan document. SKIP: authoring one (→ /fabrik-deploy-plan) · executing one (→ /fabrik-deploy) · a general implementation-plan review (→ /fabrik-plan-review). Stage: gate.
argument-hint: "<path to the deploy plan — docs/development/plans/YYYY-MM-DD-deploy-<service>.md>"
---

Converge this deployment plan to a fixed point — do not stop after one pass. The evidence base for this
command is a live review that found FOUR deploy-breakers in a plan its author believed ready: a set
placeholder silently defeating a compose `:-` fallback, an in-container dev-default port, a missing
restart-after-init, and a healer racing a migration window. Every one was invisible to a single
self-read. **Author-blindness is the point:** if this session authored the plan, the grounding passes
below still re-open every file — the author's memory of a file is not a read.

## ⚠️ Termination contract — READ FIRST (the rule agents skip)

This is a LOOP, not a one-shot. It ends — and you may flip `Status: DRAFT → CONVERGED` — **only when a
full, demonstrably-thorough round makes ZERO edits to the deploy plan** (a genuine no-op pass). Fixes open
new gaps, so **the pass in which you edited the plan is NEVER the last pass** — it MUST be followed by
another full round. **Minimum two passes, ALWAYS** — even an edit-free pass 1 must be confirmed by an
independent pass 2; accuracy outranks pass-count.

Anti-cheat (mechanical, not vibes): record the plan's `md5sum` at the **start and end of the final pass**.
Identical hash = a real no-op → CONVERGED. Different hash = you edited → run another pass. A no-op
asserted without matching hashes does not count. (The final `Status: DRAFT → CONVERGED` header flip is a
post-convergence write, exempt — it does not re-open the loop.)

Maintain a numbered **Pass Ledger** and reproduce it verbatim in your report — each row names what that
pass actually RE-CHECKED. You are done **only when the last row reads `edits: 0`** with
`md5(start) == md5(end)`. Any last row with `edits > 0` means you owe the next pass — **run it UNPROMPTED,
inside THIS invocation.** The final pass must also have **raised zero candidates** — a pass that raised 3
and refuted all 3 made no edits but is NOT quiet; log every candidate and run the next pass. **There is NO
pass ceiling.** The only non-quiet stop is a **BLOCKED escalation**: an axis stuck after 3 consecutive
reconcile attempts → pause it, surface it in the report's `## BLOCKED` section (axis + the 3 attempts),
keep converging the rest. Never self-exit with an "accepted risk". **Context is never a reason to stop:**
the harness auto-compacts and the run continues — keep going.

| Pass | axes re-checked (secrets · env · infra · ordering · healing/rollout · battery · monitoring/DR) | edits made | plan md5 (start → end) |
|-----:|---|---:|---|
| 1 | all | 4 | a1b2… → 9f8e… |
| 2 | all | **0** | 9f8e… → 9f8e… ✓ → **CONVERGED** |

## Phase 0 — Establish scope

The plan under review is `$ARGUMENTS`. Read its declared **surface** (vps · mobile · extension · desktop —
authored by `/fabrik-deploy-plan` Phase 0); the checklist below is conditioned on it. Verify the
precondition trail: the release-readiness evidence (or the recorded operator waiver) is present in the
plan's header — absent = a finding. Read the service's `specs/services/<id>.yaml`, repo compose, and
`.env`-relevant code paths — they are the ground truth every plan claim is checked against.

## Phase 1 — Grounding passes (adversarial, to a fixed point)

Treat every plan claim as unproven until verified against the real artifact — open the file, run the
probe, read the actual values:

- Every cited `path:line` → OPEN and READ those lines; every spec flag → re-derive it from the code, not
  the plan's assertion; every compose `${VAR}` → re-trace its source yourself.
- Live-infra claims (a resolver staged, a DNS record present, headroom on the target, a Backrest plan's
  path list) → re-probe over the fleet SSH path where this session can, and mark what only the deploy
  session can prove as an explicit runbook-verified item — never as silently assumed.
- Runbook steps → dry-read each command for executability (right host, right cwd, right env knobs, exec
  semantics inside vs outside the container), and each verification for decidability (a step whose
  "verify" cannot fail is not a verification).

**Canonical coverage checklist — every row gets a verdict every pass: CLEAN / FIXED / N/A-<surface> (with
the one-line why — a row is never silently dropped):**

| # | Class | What must hold (surface-conditioned) |
|---|---|---|
| 1 | Secrets flow | generate/from_env/registrar/init lifecycle coherent; precedence audited (project `.env` reads BEFORE hub env); placeholders ONLY under registrar-injected keys — a set non-empty placeholder defeats compose `:-` fallbacks forever; store surfaces: signing/credential custody named, never inlined |
| 2 | Env/config completeness | every compose var ↔ spec/secrets/registrar/code-default traced (VPS) · store metadata ↔ build profiles ↔ code consistent (stores) — nothing unresolved, nothing double-sourced |
| 3 | Staged-infra validity | staged resolver/DNS/config files re-read and valid; activation step present and ordered; registrar preview matches the shape |
| 4 | Runbook ordering + timing | every step verifiable + rollbackable; issuance/init/restart ordering sound (restart-after-init where pools go stale); in-container exec overrides explicit; heavy-step timeouts declared |
| 5 | Healing / rollout interactions | VPS: autoheal pause brackets every long-unhealthy window; watchdog + restart-policy posture named · stores: staged-rollout %, halt + rollback mechanics named |
| 6 | Battery completeness | includes a WRITE-path probe, queue-drain where workers exist, companion reachability, cert/ACME diagnostics, same-origin probes where routing is nontrivial · stores: artifact installability + first-run smoke |
| 7 | Monitoring + backup/DR truth | what ACTUALLY watches the surface (endpoint/scrape/alert verified, cert-expiry condition for new domains); which Backrest plan ACTUALLY covers the data — path lists read live, never assumed; honest RPO/RTO · stores: crash reporting + rollout-halt named |

Also hunt beyond the checklist: plan↔reality drift, unstated assumptions, steps whose verification is
vague or unrunnable, and any `OPERATOR-GATE` marker missing from a step only the human may take.

**Finder fan-out — pool-default, native for the live slices.** Decompose the pass into independent units
(one per checklist class, or per plan section) and dispatch the gradeable breadth to the OpenRouter pool —
`fanout("review", units, mode="read_only")` with the plan + the relevant ground-truth files inlined per
unit (auto-records to the flywheel; back-fill `set_quality` per unit). Reserve **native** finders for the
slices the pool cannot or must not run: anything needing live SSH probes, and the secrets-flow class
(secret-adjacent content never goes to pool APIs). Then YOU merge, dedupe by (section, failure-class), and
**refute-with-evidence** — a finding dies only by quoting the line/probe output that disproves it, and
survives only into a fix. **Prove-before-fix:** re-demonstrate each surviving finding against the real
file/probe before editing the plan for it.

## Phase 2 — No deferred questions survive (ask BEFORE, not DURING)

Sweep every residual / `[OPEN]` / "confirm at deploy" / "decide at step N" item. Each must terminate as
**RESOLVED** (surfaced to the operator in ONE batched turn during this review, answer recorded in the
plan) or **SELF-SERVICE** (the deploy session can settle it without stopping — the plan states the exact
probe/command/default). A deferred `[OPEN → at deploy]` item is a **DEFECT, not a residual**: `/fabrik-deploy`
executes runbooks, it does not adjudicate questions mid-deploy. A genuine dependency the deploy session
cannot satisfy alone is a named BLOCKING unknown → the plan stays `DRAFT` until its owner resolves it.

## Phase 3 — Flip + hand off

Only after the md5-verified no-op round: flip `Status: DRAFT → CONVERGED`, reproduce the Pass Ledger and
the checklist verdict table in your report, and name the next command. The flip is the LAST act — a plan
edited after its flip is `DRAFT` again in fact, whatever the header says; re-run the loop.

Next command: Gate 2 — human approval; on the operator's explicit go: /fabrik-deploy <plan>.
