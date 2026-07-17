<!-- ⚠️ FABRIK FACTORY WORKFLOW — DEPLOY (our own, tool-capable twin of 11-deploy-command).
     Run by our orchestrator agent (Opus 4.8, via the driver) — never pasted into a planner GUI.
     ⚠️ THIS IS THE DEPLOY-OUT **HUMAN GATE** — R14's second gate `[canonical: north star § Requirements —
     R14: "Exactly two gates: plan approval in, deploy approval out (deploy = manual `fabrik apply`)"]`.
     UNLIKE `07`–`10`, THIS COMMAND IS **NOT AUTONOMOUS**: the driver PREPARES the deploy (identify the
     spec, gather context, run every pre-flight it can, build the ticket) and **STOPS**; the **OPERATOR**
     runs `fabrik apply` from the hub; the driver then VERIFIES and reports. It never auto-deploys.
     ⚠️ `fabrik` is a **HUB CLI** — it is NOT on a project's PATH `[canonical: CLAUDE.md § Spec contract
     awareness — "`fabrik` is not on a project's PATH"]`, so every `fabrik …` command below is run by the
     operator from `/opt/fabrik`, not by an agent inside the project.

     Reads (open NOTHING else to act — every other citation below is `[canonical: …]` provenance you act on
     from the inline decision, or `(deeper, optional: …)` you may skip):
       · `specs/services/<id>.yaml` — the spec: `id`, `domain`, `kind`, `port`, the `shape:` block
       · the Deploy Plan (`04-deploy-plan-fabrik` output) when it ran — registrar surface map, compose
         contract, env vars; ELSE derive from the spec + `compose.yaml` + `.env.example` (do not block)
       · the Epic Brief (`01-epic-brief-fabrik`) — Success Criteria, for the ticket's verification lines
       · the Tech Plan (`03-tech-plan-fabrik` output) — **Retrofit branch only**, when the Deploy Plan was
         skipped and the registrar/compose context must be derived
       · **Retrofit branch only:** the retrofit's target rule pack + the Compliance-Report row that emitted
         the epic — the Vision Summary's `## Compliance Report` section produced by `mega-epic-breakdown/00-trigger-fabrik` (EXISTING mode); `02` CONSUMES it to emit the Retrofit epic — for the success criterion
       · `compose.yaml` · `compose.dev.yaml` · `.env` + `.env.example` · `PORTS.md` (port-conflict check)
       · `docs/operations/fabrik-lifecycle.md` — the deploy contract (register via `fabrik apply` → verify
         via `fabrik verify`)
       · the operator's returned `fabrik apply` / `fabrik verify` output (post-gate)
     -->

<!-- ⚠️ QUALITY GATE: any modification MUST pass EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md
     (every applicable item — N/A is valid; forgetting to check is not). No hard-coded item count here. -->

# Deploy

## Role

The **deploy preparer + verifier at the human gate** — Opus 4.8, running the driver's loop `[canonical: docs/superpowers/specs/2026-07-15-autonomous-factory-driver-design.md]`. The epic's code is already merged (`07-execute-fabrik` Step 5) and validated (`08`/`10`). This command builds a complete, executable **deploy ticket**, runs every pre-flight it can from inside the project, and **hands it to the operator** — who runs `fabrik apply` from the hub. The driver then verifies the result and reports.

**Why this one is NOT autonomous:** the chain from the plan-in gate through `10` runs without a human step; **deploy is where that stops** `[canonical: north star — Gate 2: "Telegram digest → review branches in VS Code Source Control diff → merge → manual `fabrik apply`"]`. Deploying is the operator's decision, and the tooling enforces it: `fabrik` lives on the hub, and a project has no fleet credentials by design.

## Core Philosophy

- **The lifecycle IS the contract** `[canonical: docs/operations/fabrik-lifecycle.md]` — register via `fabrik apply`, verify via `fabrik verify`. A manual `docker compose up` on the VPS makes the deploy invalid and the state file stale.
- **Prepare everything; decide nothing.** Every question the operator would have to answer (which spec, which registrars fire, what "success" means, how to roll back) is answered *in the ticket* before they read it.
- **Pre-flight the driver CAN run is the driver's; anything needing `fabrik` (hub-side) is the operator's — as is `apply`.** The driver runs only what a project can run **without `fabrik`** (the Tier-2 gate; a `docker compose -f compose.dev.yaml up -d` + `/health` sanity check — exactly what `fabrik dev` shells out to; push status; compose invariants; the port check). It never runs **any** `fabrik` command — they are all hub-side.
- **First-ever deploy vs redeploy** — a first deploy is operator-supervised (compose build + first boot surface surprises); a redeploy is routine. Either way the gate is the operator's.

## Processing User Request

### Step 1: Identify What to Deploy

From the argument, in order: an explicit path (`deploy specs/services/my-api.yaml`) → a service name (`deploy my-api` → `specs/services/my-api.yaml`) → the current epic's single in-scope spec → **ambiguous (several services): ask which**. Read the spec; extract `id`, `domain`, `kind`, `port`, `shape`.

**Retrofit-epic adjustments** (Title prefix `Retrofit:` `[canonical: mega-epic-breakdown/03-expand-epic-files-fabrik § Step 2 — Retrofit detected from the Title prefix]`):

- **Always a redeploy** — a code-only retrofit leaves `compose.yaml` unchanged, so there is no first-ever-deploy path.
- **Deploy Plan absent** — if `04-deploy-plan-fabrik` was SKIPPED per its Retrofit branch `[canonical: 04-deploy-plan-fabrik § Step 1 — Epic Flavor: Retrofit skip rule]`, derive from the Tech Plan + the existing spec; state `Deploy Plan: skipped per Retrofit branch; derived from existing project spec`. Do NOT block.
- **Shape inherited** — do not verify new shape flags unless the retrofit explicitly adds a registrar (`Retrofit: search` → `has_search_feature` + meilisearch; `Retrofit: backup` → `has_persistent_data` + backrest).
- **No new registrars / env vars** for a code-only retrofit — state `Registrars: inherited; no new firings expected`; verify existing env vars still set rather than requiring new ones.
- **Success = the rule pack's gap closing** (Partial/Violates → Compliant) — cite the pack + the Compliance-Report row that emitted the epic.
- **Rollback target** — where Epic Closure was skipped at `06`, rollback reverts to the **prior Delta-feature deploy state**, not "new feature off".

### Step 2: Gather Deploy Context

Stop at the first available per row; never block on a missing Deploy Plan:

| What | Primary | Fallback |
|---|---|---|
| Shape + registrar surface (**all 10 registrars**, each fires/doesn't) | Deploy Plan (`04`) | derive: **7 are shape-flag-driven** — `needs_database`→postgres · `needs_cache`→redis · `has_persistent_data`→backrest · `has_search_feature`→meilisearch · **`is_public` AND `spec.domain` set**→gatus · **`is_admin_dashboard` AND `spec.domain`**→authelia (+ the `^/api/` bypass first if `has_bearer_api`) · **`exposes_metrics` AND `spec.domain`**→prometheus. The other **3 are NOT shape-flag-derived**: **glitchtip** fires on `shape.kind ∈ {service, worker, wordpress}`; **grafana ALWAYS**; **watchdog** unless the spec sets `watchdog: {enabled: false}` (opt-OUT). ⚠️ `has_bearer_api` drives **no standalone registrar** — only the Authelia bypass `[canonical: src/fabrik/orchestrator/infrastructure.py — the applicability matrix]` |
| Compose contract (memory limits, `platform: linux/amd64`, healthcheck `start_period`, `fabrik` network, Traefik labels, **no host `ports:`**) | Deploy Plan `04` | read `compose.yaml` |
| Env vars | Deploy Plan `04` | read `.env.example` |
| Success Criteria | Epic Brief (`01`) | ask the operator |
| Lifecycle contract | `docs/operations/fabrik-lifecycle.md` | always present (synced) |

### Step 3: Construct the Deploy Ticket

A complete ticket the operator executes without asking anything:

```markdown
## Deploy: <service-id>
**Spec:** specs/services/<id>.yaml · **Domain:** <domain> · **Shape:** <true flags>
**Contract:** docs/operations/fabrik-lifecycle.md   **Run from:** /opt/fabrik (the hub)

### Pre-flight — `[x]` = already run by the driver (evidence attached); `[ ]` = the operator must clear it before apply (hub-side unless noted)
- [x] Tier-2 gate: `python scripts/final_gate.py --json` → status:"success"   ⚠️ never `--lean` for a deploy
- [x] Local dev: `docker compose -f compose.dev.yaml up -d` + `curl localhost:<PORT>/health` → 200   ⚠️ NOT `fabrik dev` — `fabrik` is hub-side; this is what it shells out to anyway
- [ ] Pushed: `git log origin/<branch> --oneline -1` == local HEAD   ← **operator, in the PROJECT repo (not the hub)**: the merge/push must land BEFORE apply. The driver only REPORTS the status it observed — it never pushes `[canonical: 07-execute-fabrik § Does NOT — "Run `git commit`/`push`" is a driver Does-NOT]`.   ⚠️ the VPS pulls from GitHub, not /opt
- [x] compose.yaml: memory limits · platform: linux/amd64 · healthcheck start_period · fabrik network · no host ports:
- [x] Port <PORT> free: `grep <PORT> PORTS.md`
- [x] Env vars present in .env (+ SERVICE_INTERNAL_SECRET_KEY): <list from .env.example>
- [ ] DNS (new domain only): `fabrik domain ready <domain>`   ← operator, hub-side

### Deploy — OPERATOR RUNS THIS (the R14 gate)
    fabrik apply specs/services/<id>.yaml
SSHes to the target host, writes compose.yaml + .env to /opt/<svc>/, `docker compose up -d --wait`,
fires the registrars. First deploy 5–7 min (a --wait health poll up to 300s is NORMAL); redeploy 1–2 min.

### Registrars that will fire (per the applicability matrix)
<table: registrar | fires? | what it creates>

### Post-deploy verification (hub-side)
    fabrik verify <domain> --spec registrars
    fabrik audit-registrars --spec specs/services/<id>.yaml --json   # exit 0
    curl -sI https://<domain>/health                                  # 200

### Success criteria
- SC<n>: <from the Epic Brief> → verified by: <command>

### Rollback (deploy failing past ~10 min)
    fabrik destroy specs/services/<id>.yaml --use-state --drop-data --keep-dns --dry-run   # review first
    fabrik destroy specs/services/<id>.yaml --use-state --drop-data --keep-dns -y
```

### Step 4: The Human Gate — hand off, do NOT apply

Post the ticket + the pre-flight evidence to the operator (Telegram digest + the branch diff in VS Code Source Control) and **STOP**. The operator reviews, merges if needed, and runs `fabrik apply` from `/opt/fabrik`. **The driver never runs `fabrik apply`** — R14's second gate, and `fabrik` is not on the project's PATH anyway. ⚠️ For a **git-sourced app, `git push` must land before the operator applies/redeploys** — the VPS `git pull`s from the GitHub remote, not from `/opt` `[canonical: CLAUDE.md § HARD STOPS — `fabrik redeploy` on a git-sourced app without `git push` first]`.

### Step 5: Receive + Validate

The operator returns the `fabrik apply` / `fabrik verify` output:

| Result | Action |
|---|---|
| Registrars present + health 200 + state file written | ✅ deployed — report |
| A registrar missing | fixup: `fabrik reconcile-all --filter <id>` (hub-side, operator) |
| Health fails / container crashes | read `fabrik logs <id> --tail 50` (hub-side — the operator returns the output); obvious fix → a scoped fixup ticket re-dispatched through `07-execute-fabrik`; else escalate |
| `--wait` poll ran long (≤300 s) on a first deploy | **normal** — note it, not a failure |
| Still down past ~10 min | rollback per the ticket; escalate to the operator |

### Step 6: Report

**Success:** `✅ Deployed: <id> → https://<domain>` + which registrars fired (all present) · health 200 · `.fabrik/state/<id>.json` written · Gatus endpoint active.
**Failure:** `❌ Deploy failed: <id>` + the issue, the action taken (rolled back / fixup dispatched / escalated), and what must happen next.

## Does NOT

- **Run `fabrik apply` (or any `fabrik` command) itself** — deploy is R14's operator gate, and `fabrik` is hub-side, not on the project's PATH. The driver prepares + verifies; the operator applies.
- **Skip pre-flight** — a deploy that fails mid-flight with no rollback path is the failure this checklist prevents. `--lean` is never a deploy gate.
- **Bypass the lifecycle** `[canonical: docs/operations/fabrik-lifecycle.md]` — a manual `docker compose up` on the VPS invalidates the deploy and **stales** the state file.
- **Execute the epic's tickets** — that is `07-execute-fabrik`; the code is already merged and validated before this runs.
- **Validate implementation or cross-artifact consistency** — `08-implementation-validation-fabrik` / `10-cross-artifact-validation-fabrik` already did; `11` trusts those gates.
- **Propagate a scope change** — if the deploy reveals one, route to `09-revise-requirements-fabrik`; never edit specs from here.
- **Design the Deploy Plan** — that is `04-deploy-plan-fabrik`; a mismatch between it and the deployed spec routes back to `04`.
- **Run `git commit`** — the ticket's **operator-run** commands are infrastructure-only (`fabrik apply` / `verify` / `audit-registrars` / `destroy` / `domain ready`, `curl`) — it only *checks* push status (`git log origin/<branch>`), it never pushes; code was merged at `07` Step 5 and the operator pushes before applying.
- **Block on an absent Deploy Plan, or expect new registrars/env vars/shape flags on a code-only Retrofit** — per the Step-1 Retrofit branch.
- **Mark deployed without `fabrik verify` + `fabrik audit-registrars`** — lifecycle Stage 4 is not optional.

## Applicability by scaffold type

| Scaffold | What `fabrik apply` does |
|---|---|
| `python-api` · `node-api` · `file-api` · `file-worker` | **7 per shape** (postgres, redis, gatus, backrest, authelia, meilisearch, prometheus) **+ glitchtip (`shape.kind`) + grafana (always) + watchdog (opt-OUT)** |
| `saas-skeleton` · `static-site` · `docusaurus` | lean set (typically no postgres/redis) |
| `chrome-extension` · `mobile-app` · `desktop-app` | two-faced: backend via `fabrik apply`; client distribution is manual (note it in the report) |

## Acceptance Criteria

- Spec resolved unambiguously; `id`/`domain`/`kind`/`port`/`shape` extracted.
- Context gathered (registrar surface across all 10, compose contract, env vars, Success Criteria), never blocked by a missing Deploy Plan.
- Ticket complete: pre-flight (driver-run items carry evidence; the `[ ]` items are marked operator) · the operator's `fabrik apply` line · registrar table · hub-side verification · success criteria · rollback.
- **Handed to the operator at the gate — the driver did NOT deploy** (R14); push status **reported** at the gate, and the operator confirms it landed before applying (a git-sourced app pulls from GitHub).
- Result validated from the operator's output (registrars present, health 200, state written); failures → fixup via `07`, rollback, or escalation.
- Report produced (success with the registrar list, or failure with next steps).

---

**Next:** `11` is the **end of the ettw chain** — the epic is deployed. There is no paired review: `11` is a human gate, converged instead by a grounding+consistency pass `[canonical: docs/superpowers/specs/2026-07-16-traycer-fabrik-twins-design.md § Success criteria]`. A deploy that surfaces a scope change routes to `09-revise-requirements-fabrik`; a registrar/compose mismatch routes to `04-deploy-plan-fabrik`. The next epic re-enters at `00-trigger-fabrik`. *(Downstream refs point to the live Traycer `-command` source and flip to `-fabrik` as each twin lands.)*
