# Deploy

## How You Use This Command

```
You: "deploy"

Traycer:
  1. Reads implementation-validation results (must be clean)
  2. Reads deploy-plan (04) outputs (shape, compose, registrars, env vars)
  3. Constructs deploy ticket (pre-flight + fabrik apply + verify + rollback)
  4. Dispatches to Claude Code (critical — first deploy) or Kilo CLI (routine redeploy)
  5. Agent executes on VPS: pre-flight → fabrik apply → verify → report
  6. Traycer receives results, validates registrars present
  7. Reports: "✅ Deployed. All registrars present. /health 200."

You: confirm or investigate if issues
```

---

## Role

Deploy orchestrator. Same as `07-execute` but the ticket contains infrastructure commands (`fabrik apply`, `fabrik verify`) instead of code changes. You dispatch, receive, validate.

## Core Philosophy

- Deploy is just another ticket dispatch. Same mechanism as execute.
- The deploy ticket contains `fabrik apply` + verification commands.
- Agent runs it on VPS (requires `FABRIK_EXEC_MODE=local` or SSH access).
- Validate AFTER: registrars present? Health 200? State file written?
- Operator presence recommended for first-ever deploys (Coolify v4 quirks).
- Every deploy follows `docs/reference/fabrik-lifecycle.md` § Stage 3 (Registration) + § Stage 4 (Verification). The lifecycle is the contract — the deploy ticket executes stages 3+4.

## Processing User Request

### Step 1: Consume Upstream

- `implementation-validation` results — must be clean (no Blockers)
- Deploy Plan (04) — shape, compose contract, registrar surface, env vars
- INFRA-CHECK — Port, Scaffold, Shape
- Epic Brief — Success Criteria the deploy must satisfy
- `docs/reference/fabrik-lifecycle.md` § Stage 3 + 4 — the deploy contract (synced to every project via `sync_enforcement_to_projects.py`)

### Step 2: Construct Deploy Ticket

Build a full ticket (same structure as ticket-breakdown output):

**Scope:** Execute `fabrik apply` on VPS, verify registrars, confirm health.

**Pre-flight steps:**
- Code pushed to GitHub (`git push origin <default-branch>`)
- All env vars set in Coolify dashboard (list from deploy-plan env checklist)
- Shape block matches code
- Local dev works (`fabrik dev -d && curl localhost:<PORT>/health`)
- DNS provisioned (if new domain)

**Deploy steps:**
- `fabrik apply specs/services/<id>.yaml`
- Wait for container healthy (5-7 min first deploy, SSH fallback normal)

**Verification steps:**
- `fabrik verify <domain> --spec registrars` → all present
- `fabrik audit-registrars --spec specs/services/<id>.yaml --json` → exit 0
- `curl -sI https://<domain>/health` → HTTP 200
- Gatus green at `status.vps1.ocoron.com`
- `fabrik logs <id> --tail 20` → structured logs

**Rollback (if deploy fails):**
- `fabrik destroy specs/services/<id>.yaml --use-state --drop-data --keep-dns --dry-run`
- Review → if correct → drop `--dry-run`
- Fix issue → re-deploy

### Step 3: Dispatch

Send the deploy ticket to assigned agent:

| Situation | Agent | Why |
|---|---|---|
| First-ever deploy of a service | Claude Code (operator-supervised) | High signal for Lessons Learnt, Coolify v4 quirks |
| Routine redeploy (code change) | Kilo CLI or Claude Code | Lower risk, faster |

Agent receives full ticket. Works on VPS (either via SSH or `FABRIK_EXEC_MODE=local`).

### Step 4: Receive + Validate

When agent returns:

| Finding | Action |
|---|---|
| All registrars present + health 200 | ✅ Deploy successful |
| Registrar missing | Fixup: `fabrik reconcile-all --filter <id>` |
| Health check fails | Read logs (`fabrik logs <id>`), diagnose, fixup or escalate |
| Container won't start | Check Coolify dashboard, Dockerfile, compose. Rollback if > 10 min. |
| Coolify v4 SSH fallback fired | Normal (AGENTS.md documents this). Note in Lessons Learnt. |

### Step 5: Report

```
✅ Deployed: <id>.<domain>
   Registrars: all present (list which fired)
   Health: 200
   State: .fabrik/state/<id>.json written
   Monitoring: Gatus green
   Lessons: <N entries if Coolify quirks fired>
```

Or if failed:
```
❌ Deploy failed: <id>
   Issue: <what went wrong>
   Action taken: <rollback / fixup dispatched / escalated>
   Next: <what the user should do>
```

## Applicability by Scaffold Type

| Scaffold | Deploy path |
|---|---|
| `python-api`, `node-api`, `file-api`, `file-worker` | `fabrik apply` → full registrar set |
| `saas-skeleton`, `static-site`, `docusaurus` | `fabrik apply` → lean registrar set |
| `chrome-extension`, `mobile-app`, `desktop-app` | Two-faced: backend via `fabrik apply`, client distribution manual |

## Acceptance Criteria

- Implementation-validation clean before dispatch.
- Deploy ticket constructed with: pre-flight, commands, verification, rollback.
- Dispatched to appropriate agent (Claude Code for critical, Kilo for routine).
- Agent executes `fabrik apply` + verification commands.
- Results validated: registrars present, health 200, state file written.
- Failures handled: fixup or rollback or escalate.
- Deploy report produced (success or failure with next steps).
- Coolify v4 quirks captured as Lessons Learnt.
