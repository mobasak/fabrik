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
| — | (CONVERGED at 9c37553e; then a localized DNS correction 217e934f was committed WITHOUT the marker → /fabrik-deploy hard-gate-2 refused; re-convergence below) | — | — | — |
| R3-1 | DNS correction (S1 operator-gate → verification): `_provision_dns` auto-creates the A record via `DNSClient`/site-provisioner (`__init__.py:159`); rest unchanged | 0 | 0 | a290b9a0 → a290b9a0 ✓ |
| — | (deployed → S3 HALT: `start-from-init` 03_default_instance rejected the alphanumeric admin password on `PasswordComplexityPolicy.HasSymbol`; rolled back per S-RB, DB dropped) | — | — | — |
| R4-1 | BLOCKED re-entry: admin-password complexity fix (`ZITADEL_FIRSTINSTANCE_ORG_HUMAN_PASSWORD: "${ZITADEL_ADMIN_PASSWORD}Aa1!"`, interpolation verified on the box); survivor audit (DB dropped, container removed, DNS/.env harmless); ⛔ S3 row ADJUDICATED | 1 | 1 | (BLOCKED) → f1a25bd9 |
| R4-2 | confirming | 0 | 0 | f1a25bd9 → f1a25bd9 ✓ |
| — | (re-deploy RUN 2 → S3 HALT: `up -d --wait` false-fails on health.disabled — no healthcheck to --wait on; registrars skipped. Fixed in the deployer 43ced0d3) | — | — | — |
| R5-1 | deployer up--wait fix re-entry (plan/spec unchanged; `_compose_up` uses `up -d` + readiness poll for health.disabled); survivor audit clean (DB/container 0/0); RUN-2 ⛔ ADJUDICATED | 0 | 0 | 6a369c59 → 6a369c59 ✓ |
| — | (re-deploy RUN 3 → VERIFY HALT: `DeploymentVerifier.verify` ran an in-band HTTPS probe of the domain even for health.disabled; a DNS/ACME-timing transient raised VerificationError → rollback of a HEALTHY deploy incl. the DNS record. Fixed in the deployer 1c90bf81) | — | — | — |
| R6-1 | BLOCKED re-entry (verifier health.disabled fix 1c90bf81): adjudicate ⛔ RUN 3, correct finding #5 (the "Namecheap misroute" was a MISDIAGNOSIS — `DNSClient.add_subdomain`→Cloudflare via site-provisioner, `drivers/dns.py:294-316`; record deleted by rollback, not misrouted), add the machinery-findings resolved section; survivor audit RE-PROBED (DB absent, container absent, `.env` survivor — postgres rollback is a no-op, DB dropped out-of-band). 1 native-Opus finder raised 5 evidence-integrity defects | 5 | 5 | (BLOCKED) → 270e549c |
| R6-2 | confirming — stale-ref sweep (all body `path:line` re-grounded: `deployer_ssh.py:655/649/708`, `__init__.py:166/170/180/216/311/529`, `vps-autoheal.sh:53`, `zitadel.yaml:73-75`; hash `f1a25bd9`→`03265c1d`; rollback-wording corrected + DB-absence probe added to `## Evidence`), raised 0 new | **0** | **0** | 270e549c → 270e549c ✓ |

Final round: found: 0, fixed: 0. The RUN 3 verify halt was ONE deploy-machinery defect (the verifier's
in-band probe rolling back a healthy `health.disabled` deploy), fixed at the source (1c90bf81: `verify()`
skips the in-band probe when `health.disabled` is set, mirroring `_compose_up`; 2 red-on-revert tests). The
originally-logged "finding #5 DNS-provider misroute" was refuted as a MISDIAGNOSIS and corrected in the plan
(`DNSClient.add_subdomain` POSTs the Cloudflare subdomain endpoint via site-provisioner; the record was created
correctly and deleted by the verify-failure rollback — a rollback artifact, `__init__.py:591`). R6-1's finder
also surfaced evidence-integrity defects (a fabricated commit hash, a false "rollback removed everything"
mechanism, pervasive stale `path:line` grounding) — all fixed and re-verified against ground truth. All FOUR
machinery findings (D1 · password · up--wait · verifier) are landed on master; RUN 1-3 ⛔ rows adjudicated.
`Status: CONVERGED` re-flipped with the `deploy-plan-review` marker as the latest plan-touching commit.

## Gate

```
$ python scripts/final_gate.py --check --json
{"status": "success", "passed": 53, "failed": 0}
```

## BLOCKED: none
