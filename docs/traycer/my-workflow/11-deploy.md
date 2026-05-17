# Deploy

## Role

You are the deploy orchestrator. You construct the deploy ticket (pre-flight checks, commands, verification, rollback) and dispatch it to an AI agent (Claude Code or Kilo CLI) for execution — the same way `07-execute.md` dispatches coding tickets. For critical first-ever deploys, operator presence is recommended during execution.

## When to Run

After `implementation-validation` passes clean. All gates green. Code pushed to GitHub. This is the FINAL workflow command.

## What You Do

1. Construct the deploy ticket (pre-flight + commands + verification + rollback)
2. Dispatch it to the assigned agent (Claude Code for critical, Kilo for routine)
3. Receive results back
4. Validate: registrars present? Health 200? State file written?
5. Report success or escalate failure

Same dispatch mechanism as `07-execute.md` — agent works in isolated branch, returns results, Traycer validates.

## Applicability by Scaffold Type

| Scaffold | Deploy path | What `fabrik apply` does |
|---|---|---|
| `python-api`, `node-api`, `file-api`, `file-worker` | VPS via Coolify (compose + Dockerfile) | Full registrar set |
| `saas-skeleton`, `static-site`, `docusaurus` | VPS via Coolify (compose or static serve) | Lean registrar set |
| `wordpress` | Moved to `/opt/wpf/` — use `wpf` CLI | WordPress-specific flow |
| `chrome-extension` | Two-faced: backend → Coolify, extension → Chrome Web Store (manual) | Backend gets registrars |
| `mobile-app` | Two-faced: backend → VPS, client → App Store (manual) | Backend gets registrars |
| `desktop-app` | Two-faced: download server → Coolify, app → Electron build (local) | Server gets registrars |

## Processing User Request

### Step 1: Consume Upstream

Read:
- `implementation-validation` results (must be clean — no Blockers)
- Deploy Plan (04) outputs: shape, compose contract, registrar surface, env vars
- INFRA-CHECK from trigger-workflow: Port, Scaffold, Shape
- Epic Brief: Success Criteria that the deploy must satisfy

### Step 2: Generate Pre-Flight Checklist

Produce a checklist the executing agent/operator verifies BEFORE running `fabrik apply`:

```
PRE-FLIGHT:
- [ ] All implementation-validation Blockers resolved
- [ ] Code pushed to GitHub: `git push origin <default-branch>`
- [ ] .env values set in Coolify dashboard (list each required var)
- [ ] Shape block in spec matches code (verified in implementation-validation)
- [ ] Port registered in PORTS.md
- [ ] Local dev works: `fabrik dev -d && curl localhost:<PORT>/health`
- [ ] DNS provisioned (if new domain): `fabrik domain provision <domain>`
- [ ] Compose contract valid: resource limits, platform amd64, healthcheck, coolify network
- [ ] Destroy path verified: `fabrik destroy --use-state --dry-run` shows clean reversal
```

### Step 3: Generate Deploy Commands

Produce the exact commands:

```
DEPLOY:
1. git push origin <default-branch>
2. fabrik apply specs/services/<id>.yaml
   → Coolify creates/updates app
   → Registrars fire based on shape (list which will fire)
   → State file written to .fabrik/state/<id>.json
   
   Expected time: 5-7 min first deploy. Redeploys faster.
   If SSH fallback fires at 300s: NORMAL per AGENTS.md Coolify v4 workarounds.
```

### Step 4: Generate Post-Deploy Verification

```
VERIFY:
1. fabrik verify <domain> --spec registrars
2. fabrik audit-registrars --spec specs/services/<id>.yaml --json
3. curl -sI https://<domain>/health → HTTP 200
4. Gatus shows green at status.vps1.ocoron.com
5. GlitchTip project exists (SENTRY_DSN injected)
6. fabrik logs <id> --tail 20 → structured JSON logs (no print output)
```

### Step 5: Generate Rollback Procedure

```
ROLLBACK (only if deploy fails after 10-min envelope):
1. fabrik destroy specs/services/<id>.yaml --use-state --drop-data --keep-dns --dry-run
2. Review dry-run output
3. If correct: fabrik destroy ... -y (drop --dry-run)
4. Fix the issue
5. Re-run deploy from Step 3
```

### Step 6: State Success Criteria

Map each Epic Brief Success Criterion to a verification command. The executing agent confirms each after deploy:

```
SUCCESS CRITERIA:
- SC1: <criterion> → verified by: <command + expected output>
- SC2: <criterion> → verified by: <command + expected output>
...
```

### Step 7: Present Instructions

Output the complete deploy ticket in a format ready to dispatch:
- Agent can copy-paste and execute sequentially
- Every command is explicit (no "run the appropriate command")
- Every expected output is stated (agent knows what success looks like)
- Failure paths documented (agent knows when to stop and escalate)

## Acceptance Criteria

- Pre-flight checklist produced with all required checks.
- Deploy commands are exact (not vague — actual `fabrik apply` with spec path).
- Registrar surface stated (which 9 registrars will fire, which won't, per shape).
- Post-deploy verification commands listed with expected outputs.
- Rollback procedure documented (uses `fabrik destroy --use-state`).
- Success criteria mapped to verification commands.
- Output is dispatchable (agent can execute without questions).
- Two-faced types: VPS backend deploy covered; client distribution noted as manual.
- WordPress projects: directed to `/opt/wpf/` and `wpf` CLI.
- 4-layer VPS security acknowledged (iptables DOCKER-USER, Traefik, Authelia if admin, no host ports).
