# Deploy-plan review — 2026-08-28-plan-deploy-zitadel (surface: vps)

Adversarial convergence of the Zitadel v4 umbrella-IdP deploy plan. Author-blind: every ground-truth file was
re-opened (I authored the plan) and independent Opus finders were dispatched each round. The first round found a
blocking deploy-order defect (D1) + 8 others; D1 was resolved by a machinery fix and the second round hardened
it (3 further issues) to a clean, md5-verified no-op. Two rounds, three finder dispatches total.

## Phase verdicts

- **Phase 0 (surface)** — CLEAN: VPS inferred from `specs/services/zitadel.yaml`; hub-side; no `project.yaml`.
- **Phase 1 (target)** — CLEAN: `vps1` defended by live `free -h` (7.5Gi) + hub-only `postgres-main` locality.
- **Phase 2 (spec↔code↔compose)** — FIXED: every `${VAR}` traced; F1 masterkey re-mint grounded + mitigated;
  D4 LOG_LEVEL drift corrected; D3 no-safe-image-bump documented.
- **Phase 3 (infra prereqs)** — CLEAN: DNS S1 grounded (`auth.ocoron.com` unresolved → `172.93.160.197`); cert
  story + middleware verified.
- **Phase 4 (runbook)** — FIXED: D1 resolved (`deploy.db_before_boot` pre-provision before first boot); D2 (S5
  greps the resolved DSN); #4b re-run recovery; stable `S`-ids; S-RB first-deploy-only.
- **Phase 5 (healing)** — CLEAN (N/A-vps): `health.disabled` → no healthcheck → `vps-autoheal.sh:53`
  (unhealthy-only) never acts; grounded in the predicate, not assumed.
- **Phase 6 (battery)** — FIXED: F-D readiness≠write-proof corrected; write path = Console user-create.
- **Phase 7 (monitoring/DR)** — FIXED: F-A/F-B fixed at the spec (`health.path`/`monitoring.metrics_path`);
  F-C cert-expiry claim dropped; F-E → S-DR backup-coverage step; F4 paper-backup confirmed.
- **Phase 8 (first-days)** — CLEAN: watchdog off; alert expectations + rollback rule stated.

## Class verdicts

| # | Class | Verdict | Evidence |
|---|---|---|---|
| 1 | Secrets flow | CLEAN | F1 grounded `__init__.py:301-320`; `db_before_boot` DSN coexists with masterkey; plain `redeploy` safe |
| 2 | Env/config completeness | FIXED | D4 drift corrected; DATABASE_URL seeded + env_file interpolation verified live (`docker compose config`, 2.40.3) |
| 3 | Staged-infra validity | CLEAN | DNS S1, 6-registrar `fabrik plan` preview, cert story |
| 4 | Runbook ordering + timing | FIXED | D1 (`db_before_boot` step 2b `__init__.py:161`<`:170`), D2 (resolved-DSN grep), S-ids, S-RB/#4b |
| 5 | Healing / rollout | CLEAN | N/A-vps: `vps-autoheal.sh:53` unhealthy-only + `health.disabled` → no window |
| 6 | Battery completeness | FIXED | F-D write-proof corrected; ACME diag before TLS |
| 7 | Monitoring + backup/DR truth | FIXED | F-A/F-B spec `health.path`+`monitoring.metrics_path`; F-C dropped; F-E S-DR; F4 paper-backup |
| 8 | Standing recurrence sweep | FIXED | #3 db_name parity (`:302`==`infrastructure.py:413`); #4a orphan tracked; #6 interpolation grounded; opt-in byte-identical |

## Pass Ledger

| Pass | axes re-checked | found | fixed | plan md5 (start → end) |
|-----:|---|---:|---:|---|
| R1-1 | all — original grounding, 2 finders | 9 (D1 + F-A..F-E + D2/D3/D4) | 8 | 3fac3abb → b65efafe |
| — | (D1 machinery fix landed: `deploy.db_before_boot`, commit a47d5e20) | — | — | — |
| R2-1 | all + D1-fix (ordering/idempotency/parity/opt-in), 1 finder | 3 (#3, #4, #6) | 4 | c308edcb → 0369919f |
| R2-2 | all (confirming) | **0** | **0** | 0369919f → 0369919f ✓ |

Final round: found: 0, fixed: 0. The plan's class-sweep summary + `Status: CONVERGED` header writes follow the
verified no-op (post-convergence, exempt); final plan md5 `b6c659ed`.

## Gate

```
$ python scripts/final_gate.py --check --json
{"status": "success", "passed": 53, "failed": 0}
```

## BLOCKED: none
