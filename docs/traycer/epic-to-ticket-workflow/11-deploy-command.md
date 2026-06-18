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
