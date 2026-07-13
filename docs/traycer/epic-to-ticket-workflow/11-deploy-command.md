<!-- ⚠️ TRAYCER WORKFLOW SOURCE FILE
     Traycer does NOT read this file directly.
     After editing, copy-paste the content into Traycer workflow GUI.
     Location: Traycer > My Workflows > (select matching step)
     -->

<!-- ⚠️ QUALITY GATE: Any modification to this command file MUST be evaluated
     against EVALUATION_CHECKLIST_FOR_EPIC_COMMANDS.md (131 items).
     Every applicable item must pass. "N/A" is valid; forgetting to check is not. -->

# Deploy

## How You Use This Command

```
You: "deploy" or "deploy <service-name>" or "deploy specs/services/<id>.yaml"

Traycer:
  1. Identifies WHICH service to deploy (from user arg, or current epic's spec)
  2. Reads the spec file → knows shape, registrars, port, domain
  3. Reads deploy-plan (04) if it ran, OR derives from tech-plan + spec
  4. Constructs a deploy ticket (pre-flight → push → apply → verify → report)
  5. Dispatches to Claude Code (first-ever deploy) or Kilo CLI (redeploy)
  6. Agent SSHs to VPS and executes the commands
  7. Traycer receives result: registrars present? Health 200?
  8. Reports success or failure with next steps

You: confirm or investigate
```

---

## Role

Deploy orchestrator. You construct and dispatch a deploy ticket — same mechanism as `07-execute.md`. The ticket contains infrastructure commands (`git push`, `fabrik apply`, `fabrik verify`) that an agent executes on the VPS via SSH.

## Core Philosophy

- Deploy is a ticket dispatch. Same pattern as execute.
- Every deploy follows `docs/operations/fabrik-lifecycle.md` (register via `fabrik apply` + verify via `fabrik verify`). The lifecycle is the contract.
- The agent executes on VPS via SSH from WSL (standard Fabrik flow). NOT via `FABRIK_EXEC_MODE=local` (that's for crons/watchdog running ON the VPS already).
- First-ever deploys: operator-supervised (compose build + first-boot can surface unexpected issues).
- Redeploys: routine, can be fully autonomous.

## Processing User Request

### Step 1: Identify What to Deploy

Determine the spec from user input (try in order):

1. **Explicit path:** user says `"deploy specs/services/my-api.yaml"` → use it
2. **Service name:** user says `"deploy my-api"` → resolve to `specs/services/my-api.yaml`
3. **Current epic context:** if an epic is in flight and has ONE spec in scope → use it
4. **Ambiguous:** multiple services in epic → ask "Which service?"

Read the spec file. Extract: `id`, `domain`, `shape`, `port`, `kind`.

**Retrofit-epic adjustments (when current epic Title prefix is `Retrofit:` per `mega-epic-breakdown/03-expand-epic-files-command` § Step 2):**

- **First-ever-deploy vs redeploy distinction:** Retrofit deploys are ALWAYS redeploys (the existing project's compose unchanged for code-only retrofits per `04-deploy-plan-command` post-`3060147` Skip rule). Default dispatch target is **Kilo CLI** (redeploy path per L23).
- **Deploy Plan absence:** if `04-deploy-plan-command` was SKIPPED entirely per its Retrofit Skip rule, derive from tech-plan + existing project spec. State explicitly in the deploy ticket: `Deploy Plan: skipped per Retrofit branch; derived from existing project spec`.
- **Shape Block (pre-flight):** Retrofit epics INHERIT the existing project's shape; do NOT verify new shape flags unless the retrofit explicitly adds a registrar (e.g., `Retrofit: search` adds `has_search_feature` + meilisearch; `Retrofit: backup` adds `has_persistent_data` + backrest).
- **Compose verification:** for code-only retrofits (e.g., `Retrofit: i18n`, `Retrofit: Resilience` on existing external calls, `Retrofit: Auth hardening`), `compose.yaml` is UNCHANGED — pre-flight verifies invariants still hold but does NOT expect new content.
- **Env vars:** for code-only retrofits, no NEW env vars expected. Verify existing env vars still set; do not require new entries unless the retrofit explicitly adds an external dep.
- **Registrars (deploy ticket § "Registrars that will fire"):** for code-only retrofits, NO NEW registrars fire — shape is inherited. State `Registrars: inherited from existing project; no new firings expected`.
- **Success criteria (deploy ticket § "Success criteria"):** Retrofit epic success is the rule pack's compliance check moving Partial/Violates → Compliant (per the Compliance Report gap row that emitted the Retrofit epic via `mega-epic-breakdown/02-epic-decomposition-command` Step 2b). Cite the specific rule pack + gap closure — e.g., `Retrofit: i18n` → `core/i18n: validate_i18n.py passes; en + tr locale coverage 100%`.
- **Rollback target (deploy ticket § "Rollback"):** for Retrofit epics where Epic Closure was SKIPPED at `06-ticket-breakdown` Step 10 (post-`8dcdd2b`), rollback reverts to the PRIOR Delta-feature deploy state, not "new feature off" — `fabrik destroy --use-state --drop-data` reverts to the prior closure's recorded state.

### Step 2: Gather Deploy Context

Read these (stop at first available per item):

| What | Primary source | Fallback |
|---|---|---|
| Shape + registrar surface | Deploy Plan (04) output | Derive from spec `shape:` block directly |
| Compose contract (resource limits, platform, healthcheck) | Deploy Plan (04) Step 3 | Read `compose.yaml` in project |
| Env vars checklist | Deploy Plan (04) Step 5 | Read `.env.example` in project |
| Success Criteria | Epic Brief | Ask user what "success" looks like |
| Lifecycle contract | `docs/operations/fabrik-lifecycle.md` (apply + verify) | Always available (synced to every project) |

If deploy-plan (04) didn't run for this epic (some routes skip it): derive directly from the spec + compose. Don't block on missing deploy-plan.

### Step 3: Construct Deploy Ticket

Build a complete ticket the agent can execute without questions:

```markdown
## Deploy: <service-id>

**Spec:** specs/services/<id>.yaml
**Domain:** <domain>
**Shape:** <shape fields — determines which registrars fire>
**Agent context:** Read `docs/operations/fabrik-lifecycle.md` before executing.

### Pre-flight (verify before deploy)
- [ ] Final gate passes: `python scripts/final_gate.py --lean --json` → status: success
- [ ] Local dev works: `fabrik dev -d && curl localhost:<PORT>/health` → 200
- [ ] Code pushed: `git log origin/<branch> --oneline -1` matches local HEAD
- [ ] If not pushed: `git push origin <branch>`
- [ ] Env vars set in the service `.env` (deployed by `fabrik apply` over SSH): <list each required var from .env.example + SERVICE_INTERNAL_SECRET_KEY>
- [ ] compose.yaml valid: resource limits, platform: linux/amd64, healthcheck, fabrik network, no host port bindings
- [ ] Port <PORT> not conflicting: `grep <PORT> PORTS.md`
- [ ] DNS ready (if new domain): `fabrik domain ready <domain>`
- [ ] Optional: `fabrik review` run to bundle diff + spec for final human review

### Deploy
```bash
fabrik apply specs/services/<id>.yaml
```
Expected: `fabrik apply` SSHes into the target host, writes `compose.yaml` + `.env` to `/opt/<svc>/`, runs `docker compose up -d --wait` → container starts → registrars fire.
Time: 5-7 min first deploy (the `--wait` health poll can run up to 300s — NORMAL per AGENTS.md).
Redeploy: 1-2 min (image cached).

### Registrars that will fire (from shape)
<table: registrar | fires? | what it creates>

### Post-deploy verification
```bash
fabrik verify <domain> --spec registrars          # all registrars present
fabrik audit-registrars --spec specs/services/<id>.yaml --json  # exit 0
curl -sI https://<domain>/health                  # HTTP 200
```

### Success criteria
- SC1: <from brief> → verified by: <command>
- SC2: <from brief> → verified by: <command>

### Rollback (if deploy fails after 10 min)
```bash
fabrik destroy specs/services/<id>.yaml --use-state --drop-data --keep-dns --dry-run
# Review → if correct:
fabrik destroy specs/services/<id>.yaml --use-state --drop-data --keep-dns -y
# Fix issue → re-deploy
```

### Report back
On success: paste `fabrik verify` output + `curl /health` status.
On failure: paste error logs (`fabrik logs <id> --tail 50`).
```

### Step 4: Dispatch

| Situation | Agent |
|---|---|
| First-ever deploy of this service | Claude Code (operator presence recommended) |
| Routine redeploy (code pushed, same service) | Kilo CLI or Claude Code |

Agent receives the full ticket. It SSHs to VPS and executes commands in order. Standard Fabrik deployment flow — the agent doesn't need special VPS access beyond what `ssh vps` provides (already configured in every Fabrik project).

### Step 5: Receive + Validate

When agent returns results:

| Result | Action |
|---|---|
| All registrars present + health 200 | ✅ Mark deployed. Report success. |
| Registrar missing | Dispatch fixup: `fabrik reconcile-all --filter <id>` |
| Health fails (container crashes) | Read logs. If obvious fix → fixup ticket. If not → escalate. |
| Container won't start after 10 min | Rollback (from ticket). Escalate to user. |
| `docker compose up -d --wait` health poll ran long (up to 300s) | Normal for a first deploy. Note in report (not a failure). |

### Step 6: Report

On success:
```
✅ Deployed: <id> → https://<domain>
   Registrars: <list which fired> — all present
   Health: HTTP 200
   State: .fabrik/state/<id>.json written
   Monitoring: Gatus endpoint active
```

On failure:
```
❌ Deploy failed: <id>
   Issue: <what went wrong — from agent's report>
   Action: <rolled back / fixup dispatched / escalated to user>
   Next: <what needs to happen>
```

## Does NOT

- Does NOT execute tickets in the epic — that is `07-execute-command` (the coding agent dispatch). ettw/11 is post-execute deploy; the epic's code is already merged.
- Does NOT validate implementation correctness — that is `08-implementation-validation-command`. ettw/11 trusts the prior validation gates passed.
- Does NOT validate cross-artifact consistency — that is `10-cross-artifact-validation-command`. ettw/11 trusts the prior validation gates passed.
- Does NOT propagate scope changes — that is `09-revise-requirements-command`. If deploy reveals a scope issue, route back to ettw/09; do NOT modify specs from inside ettw/11.
- Does NOT design Component Architecture / Deploy Plan — those are `03-tech-plan-command` + `04-deploy-plan-command`. ettw/11 reads them as inputs; mismatch with deployed spec routes back to ettw/04.
- Does NOT bypass the lifecycle contract — every deploy follows `docs/operations/fabrik-lifecycle.md` (register via `fabrik apply` + verify via `fabrik verify`). Manual `docker compose up` on the VPS = the deploy is invalid and the state file becomes stale.
- Does NOT use `FABRIK_EXEC_MODE=local` — that mode is for crons/watchdog running ON the VPS already; ettw/11 dispatches an agent that SSHes FROM WSL TO the VPS. The two modes are not interchangeable (per L41).
- Does NOT skip pre-flight verification — every deploy ticket includes the full pre-flight checklist (L84-93). Skipping pre-flight = deploy may fail mid-flight with no rollback path.
- Does NOT enforce first-ever-deploy ticket template on Retrofit epics — per Step 1 Retrofit branch, Retrofit deploys are ALWAYS redeploys (dispatch to Kilo CLI by default; verify-only pre-flight for code-only retrofits).
- Does NOT verify Shape Block new flags for Retrofit epics — per Step 1 Retrofit branch, shape is INHERITED from existing project unless the retrofit explicitly adds a registrar.
- Does NOT block `fabrik apply` on a Retrofit epic's absent Deploy Plan — per Step 1 Retrofit branch, derive from tech-plan + spec when `04-deploy-plan-command` SKIPPED entirely (post-`3060147`).
- Does NOT run `git commit` or modify code in the deploy ticket — code is already merged pre-deploy per `07-execute-command` Step 5 Merge. Deploy ticket commands are infrastructure-only (`git push`, `fabrik apply`, `fabrik verify`, `fabrik audit-registrars`).
- Does NOT skip the lifecycle Stage 4 verification — `fabrik verify` + `fabrik audit-registrars` MUST run before marking deploy successful (per L108-109 + L188 acceptance).

## Applicability by Scaffold Type

| Scaffold | What `fabrik apply` does |
|---|---|
| `python-api`, `node-api`, `file-api`, `file-worker` | Full registrar set (postgres, redis, gatus, backrest, glitchtip, grafana, authelia, meilisearch, prometheus — per shape) |
| `saas-skeleton`, `static-site`, `docusaurus` | Lean registrar set (typically no postgres/redis) |
| `chrome-extension`, `mobile-app`, `desktop-app` | Two-faced: backend via `fabrik apply`, client distribution manual (noted in report) |

## Acceptance Criteria

- Service identified unambiguously (spec path resolved).
- Deploy context gathered (shape, registrars, env vars, compose contract).
- Deploy ticket constructed with: pre-flight, commands, registrar table, verification, success criteria, rollback.
- Dispatched to appropriate agent.
- Agent executes via SSH to VPS (standard Fabrik flow).
- Results validated: registrars present, health 200, state file written.
- Failures handled: fixup or rollback or escalate.
- Report produced (success with registrar list, or failure with next steps).
- `docs/operations/fabrik-lifecycle.md` referenced as the deploy contract.
