# Review — tryton-crm deployment readiness (pre-deploy gate)

Surface: the 8-step deploy runbook · `specs/services/tryton-crm.yaml` · staged Traefik
cloudflare-resolver files on vps1 · hub `.env` secrets handoff state · the verification battery.
Reviewed BEFORE the operator's "deploy" — every finding here is a deploy that would have gone wrong.

Status: IN PROGRESS — finder passes running; ledger updates in place.

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| secrets flow (from_env order, generate, placeholder, RPC lifecycle) | PENDING finder A | |
| compose env completeness (every ${VAR:?} satisfied) | PENDING finder A | |
| staged traefik validity (v2.11 resolver, yaml nesting, mounts) | PENDING finder B | |
| runbook ordering + issuance timing | PENDING finder B | |
| autoheal × 8-min init interaction | PENDING finder B | |
| build/apply mechanics vs image weight | FIXED (M1) | deployer timeout=300 hard-coded ×3 vs tesseract+poppler+pip cold build → env-tunable `FABRIK_BUILD_TIMEOUT` (deployer_ssh.py:33; runbook applies with 1200) |
| post-deploy monitoring completeness (cert renewal!) | FOUND (M2, fix pending) | Gatus has ZERO tojlo.com endpoints and no cert checks (live grep) — wildcard RENEWAL failure ~60-90d out would surface as tenant complaints; fix: Gatus endpoint on a tenant subdomain with cert-expiry condition, post-apply |
| backup/DR mechanism truth | CORRECTED (M3) | per-service Backrest plan targets `/opt/tryton-crm/data` (infrastructure.py:716) — a path this stack never writes; REAL cover = standing `docker-volumes` plan → `/var/lib/docker/volumes` (live-read) which includes trytond-filestore. Outcome holds; my earlier mechanism claim was wrong. Residual: `host-state` plan lacks `/usr/local/bin/fabrik-autoheal` (sync-script re-provisioning accepted as the provisioner) |

## Pass Ledger

```
Pass 1a — MY authoritative pass | found: 3 | fixed: 1, fix-pending: 1, corrected-claim: 1
  M1 CONFIRMED: hard-coded 300s build timeout × cold heavy image → apply dies mid-build
     → _BUILD_TIMEOUT env-tunable (default unchanged), runbook step 2 exports 1200
  M2 CONFIRMED: no monitoring on *.tojlo.com, no cert-expiry checks anywhere in Gatus
     → fix queued: post-apply Gatus endpoint (tenant subdomain + certificate-expiry
       condition); gatus driver add_endpoint is additive per-service (verified) so a
       hand-added entry survives future applies
  M3 CORRECTED: per-service Backrest plan is vestigial for volume-based stacks — the
     standing docker-volumes plan is the real cover (paths verified live); DR narrative
     updated; no data at risk
Pass 1b — finder A (spec + secrets flow), native | IN FLIGHT
Pass 1c — finder B (infra path + runbook), native | IN FLIGHT
  (pool skipped: documented fanout empty-completion failure + finders need live SSH
   and session-grounded context; single-native-layer noted as advisory deviation)
```

## Disposition Ledger

(completed after finder merge — every candidate terminates FIXED or REFUTED with proof)
