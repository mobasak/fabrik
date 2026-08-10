---
description: Author a per-service DEPLOYMENT PLAN — stage 1 of the deploy triad. Resolves the deploy surface from project.yaml::type (all 12 scaffold types; unknown types inferred from artifacts — never refused), then authors docs/development/plans/YYYY-MM-DD-deploy-<service>.md (Status: DRAFT): target evidence, spec↔code↔compose reconciliation, a runbook with per-step verification + rollback, healing-window interactions, verification battery, monitoring/backup/DR truth. Authors only — never converges, never deploys. TRIGGER — EN: "plan the deployment", "write the deploy plan"; TR: "dağıtımı planla" — fires when a release-ready service needs its deploy planned. SKIP: converging the plan (→ /fabrik-deploy-plan-review) · executing it (→ /fabrik-deploy) · pre-deploy readiness (→ /fabrik-release). Stage: 6-release.
argument-hint: "<service id or specs/services/<id>.yaml> [surface override: vps | mobile | extension | desktop — wins over project.yaml::type]"
---

Author this service's **deployment plan** — the document `/fabrik-deploy` will later execute step-by-step.
Every deploy-breaker the triad exists to catch (a placeholder that silently defeats a compose fallback, an
in-container port that only works in dev, a healer restarting a mid-migration container) is cheapest to
catch HERE, on paper, before anything runs. This command **authors only**: no `fabrik apply`, no SSH
mutation, no store upload — and no convergence claim (`/fabrik-deploy-plan-review` owns that).

## ⚠️ Termination contract

You are done when `docs/development/plans/YYYY-MM-DD-deploy-<service>.md` exists with `Status: DRAFT` and
EVERY mandatory section for the resolved surface carries **grounded content — a `path:line`, a fenced
command output, or an explicit `N/A-<surface>` with the one-line why** — and you have named the next
command. A section filled from memory (a spec flag recalled, a Backrest path assumed, a store profile
quoted unread) is not authored, it is guessed — open the file, run the probe. You never flip the plan
beyond `DRAFT` — the review command's md5-verified no-op is what earns `CONVERGED`. **Context is never a
reason to stop:** the harness auto-compacts and the run continues — keep going. If a required input is
genuinely missing after a real search, stop with `BLOCKED: <what> — searched: <where> — missing: <need>`.

## ⚠️ Precondition — release readiness first

`/fabrik-release` must have run for this service with every checklist item PASS (read its Gate-2 handoff /
report), OR the operator explicitly waived it THIS turn (record the waiver verbatim in the plan's header).
A deploy plan for a service that never passed release readiness plans the deployment of unverified code —
report `BLOCKED: /fabrik-release not green — run it first` and stop.

## Phase 0 — SURFACE RESOLUTION (universality contract — never refuse a type)

1. Read `project.yaml::type` and dispatch against the LIVE registry (`scaffold.py::SCAFFOLD_TYPES` — 12
   types; if the registry and this table ever disagree, the registry wins and the divergence is a defect
   to report upstream):

   | `type` | Surface | Plan shape |
   |---|---|---|
   | `python-api` · `python-api-gpu` · `node-api` · `file-api` · `file-worker` · `saas-skeleton` · `static-site` · `docusaurus` | **VPS** | the full VPS contract (Phases 1–8 below) |
   | `mobile-app` | **MOBILE** | EAS/store plan: build profile (`eas.json`), submission track + first ring, staged-rollout %, store-listing deltas, signing/credentials state |
   | `chrome-extension` | **EXTENSION** | Web Store plan: zip provenance (built from a pushed SHA), listing/privacy deltas, review-trap checklist, staged rollout |
   | `desktop-app` | **DESKTOP** | release-artifact plan: build matrix, signing/notarization, update channel, GitHub Release cut |
   | `wordpress` | **LEGACY** | WordPress is out of fabrik (`/opt/wpf` archived 2026-08-07) — print that and stop; no deploy plan is authored |

2. **Unknown / absent / unregistered type → INFER the surface from artifacts, never refuse:**
   `specs/services/<id>.yaml` exists → VPS · `eas.json` → mobile · an MV3 `manifest.json` → extension ·
   an electron config (`electron-builder`/`forge` in `package.json`) → desktop. Multiple or none matching
   → present the evidence and ask the operator **ONCE** (a single batched surface question is the
   sanctioned ask). An explicit surface argument always wins over both the type and the inference.
3. Non-VPS surfaces emit **their surface's analogue of every numbered class below** — reconciliation
   (store metadata ↔ build config ↔ code), runbook (build → upload → rollout steps with per-step
   verification), battery (installability / smoke on the artifact), monitoring/rollback truth (crash
   reporting wired, staged-rollout halt mechanics) — swapping the mechanics, never dropping the class.
   Mark a genuinely inapplicable item `N/A-<surface>` with the one-line why; never silently omit it.
4. Where each phase runs: `[anywhere]` = readable from the project tree; `[hub-side]` = needs `/opt/fabrik`
   or the fleet SSH path (`fabrik plan`, live `free -h`). From a project, ground hub-side facts by READING
   (the spec's `shape:`, the flag→registrar mapping) and mark the live probe as a hub-side runbook step —
   never shell out to `fabrik` from a project (it is not on a project's PATH).

## Phase 1 — Target decision with evidence `[hub-side probes, [anywhere] reasoning]` (VPS)

Name the target VPS and defend it with data, not vibes: current memory headroom on each candidate (live
`free -h` / container count via the fleet SSH path), shared-infra locality (a service on `postgres-main` /
`redis-main` wants vps1 — a spoke pays the WireGuard round-trip per query), latency to its users, and the
service's own `resources.memory` claim against what remains. Record the decision as `target_vps: <vps>` +
the evidence block. A spoke target must note the mesh addressing consequence (`10.99.0.1:<port>`, never
`postgres-main`).

## Phase 2 — Spec ↔ code ↔ compose reconciliation `[anywhere]` (VPS)

The section that catches deploy-breakers. For `specs/services/<id>.yaml` + the repo compose + the code:

- **Every `shape:` flag re-verified at `path:line`** — a DB call ⇒ `needs_database`, `/metrics` route ⇒
  `exposes_metrics`, Redis use ⇒ `needs_cache`, admin UI ⇒ `is_admin_dashboard`. A lying flag = a silently
  skipped registrar.
- **Every compose `${VAR}` traced to its source** — spec `env:`, `secrets.generate`, `secrets.from_env`, a
  registrar injection, or a code default. An untraceable var is a finding, not a hope.
- **Placeholder-key semantics** (the A1 class, live 2026-08-10): compose `${VAR:-fallback}` falls through
  ONLY when `VAR` is unset/empty — a **set, non-empty placeholder wins forever** and the real value never
  arrives. Place placeholders ONLY under the key the registrar actually injects (e.g. `DATABASE_URL` — the
  postgres registrar's key, protected by `_build_env_content`'s placeholder-aware merge); leave derived
  keys ABSENT.
- **`from_env` precedence audit** (the A5 class): `from_env` resolution reads the project's
  `/opt/<project>/.env` BEFORE the hub process env — name where each `from_env` value actually lives
  today and add a runbook guard step that prints (masked) what will be injected.
- **Secrets lifecycle**: which values are minted (`secrets.generate`), which flow (`from_env`), which are
  created at init by a script — and the exact handoff order so the bridge/app and the hub agree.

## Phase 3 — Infra prerequisites `[hub-side]` (VPS)

Resolvers and cert story (a new base domain needs its resolver/DNS-01 path staged BEFORE first router
load), DNS records, registrar preview — `fabrik plan specs/services/<id>.yaml` output embedded (or, from a
project, the `shape:`→registrar mapping read and listed), Traefik network/middleware expectations, and any
staged config files with their activation step.

## Phase 4 — Ordered runbook: exact commands, per-step verification, per-step rollback (all surfaces)

The core artifact — a numbered table/list where EVERY step carries: the exact command (env knobs inline —
e.g. `FABRIK_BUILD_TIMEOUT=1200 fabrik apply …` for a heavy image, per `deployer_ssh.py::_BUILD_TIMEOUT`),
the verification that proves the step landed (a command + expected output, fenced), and the rollback if it
didn't. In-container exec semantics are spelled out (the B1 class: an in-container default port/host is
dev-shaped — pass the explicit `-e` override). Long-running init steps state their expected duration.
Steps only the operator may take (the store submit click, a paid account action) are marked
`OPERATOR-GATE` — the runbook prepares up to them, never through them.

## Phase 5 — Maintenance-window interactions (the healing layer) `[anywhere]` (VPS)

Any step that leaves a container legitimately unhealthy longer than its healthcheck tolerates (migrations,
module init — the B3 class: autoheal's worst-case time-to-unhealthy is minutes, an init can be 8–10) MUST
be bracketed: `touch /run/fabrik-autoheal/pause` on the target before the window, `rm` after, with the
runbook noting the pause file's 2h staleness self-heal. Also name watchdog posture and restart-policy
interactions for first boot.

## Phase 6 — Verification battery (the deploy's exit gate) (all surfaces)

Read-only checks are not enough. The battery MUST include: a **WRITE-path probe** (the B2 class — a create
call through the real API proving pools/queues are live post-init), a queue-drain / stuck-row check where
the service has workers, companion-service reachability (each compose sibling probed from the app
container), ACME/cert diagnostics for a new domain (the acme log read BEFORE the TLS test, so a
cert-pending state isn't misread as a routing failure), and same-origin routing probes where routing is
nontrivial. Store surfaces: artifact installability + a first-run smoke on the built artifact.

## Phase 7 — Monitoring / backup / DR truth check (all surfaces)

Not "monitoring exists" — WHAT actually watches this surface, verified: the Gatus endpoint (with a
certificate-expiry condition for a new cert domain — the M2 class), the Prometheus scrape, alert routes.
And the M3 class for data: which Backrest plan ACTUALLY covers this service's volumes — read the plan's
real path list live; a per-service plan pointed at an unused directory is a paper backup. State RPO/RTO
honestly. Store surfaces: crash reporting wired + rollout-halt mechanics named.

## Phase 8 — First-days posture (all surfaces)

Watchdog enable decision (+ when to flip it), which alerts are expected to fire in the first hours and
which mean rollback, the rollback decision rule (what observation triggers it, who decides), and the
first-week review hook.

## Question bar — decide, don't drip

Resolve everything from the spec, the code, the rules packs, and the docs first. Genuine operator
decisions (target VPS with two defensible answers, domain choice, rollout %, a release-readiness waiver)
are batched into ONE question set, asked once — never dripped mid-authoring, and never deferred into the
plan as an `[OPEN]` item (the review command treats a deferred question as a defect).

## Output

`docs/development/plans/YYYY-MM-DD-deploy-<service>.md` with a header (`Status: DRAFT` · service · surface
· target · date · the release-readiness evidence or waiver) and the surface's mandatory sections above,
every claim grounded. End by naming the next command.

Next command: /fabrik-deploy-plan-review — adversarially converge the deploy plan before it is trusted.
