# Review — tryton-crm deployment readiness (pre-deploy gate)

Surface: the 8-step deploy runbook · `specs/services/tryton-crm.yaml` · staged Traefik
cloudflare-resolver files on vps1 · hub `.env` secrets handoff state · the verification battery.
Reviewed BEFORE the operator's "deploy". **Exit state: CLEAN after fixes** — 2 finders + the
authoritative pass raised 15 candidates; every one terminated FIXED / REFUTED / documented-residual;
confirming pass re-validated the corrected spec + runbook end-to-end. The runbook shipped to the
operator is **v2** (this review's output), not the version the finders attacked.

## Coverage Checklist

| Class | Verdict | Evidence |
|---|---|---|
| secrets flow (from_env order, generate, placeholder, RPC lifecycle) | FIXED | A1 (deploy-breaker) + A4 fixed in spec (9e117ad9); A5 guard added to runbook; A6/A7 refuted with evidence |
| compose env completeness | FIXED | A1's DATABASE_URL-key placeholder restores the derivation chain; EFATURA fail-soft accepted by design (A8) |
| staged traefik validity | CLEAN + hardened | B5/B6 refuted the yaml-nesting + env-var-name suspicions (lego source checked, v2.11 confirmed); B8 stale `network: coolify` fixed in the staged file |
| runbook ordering + issuance timing | FIXED | B2 restart-after-init added (step 3b — the stale-Pool 500s trap); B7 refuted issuance-timing risk (router-load at step 2 + the 10-min init gap); B9 chmod 600 confirmed present in step 1 |
| autoheal × init interaction | FIXED | B3: worst-case time-to-unhealthy ≈190s vs 8-10 min init → global `pause` mechanism added to fabrik-autoheal (2h staleness self-heal), fleet-deployed, E2E-proven (PAUSED log 13:50:13); runbook brackets step 3 with pause/unpause |
| RPC-login step correctness | FIXED | A2≡B1 (double-confirmed): in-container default `localhost:18000` is dev-only → runbook adds `-e TRYTOND_TEST_HOST=localhost:8000`; A3 (--write-env dead in-container) upstream-reported; steps 5-6 reworked — printed password → hub .env → second `fabrik apply` (env-sync) so bridge + hub agree |
| build/apply mechanics | FIXED | M1: 300s hard-coded build timeout → `FABRIK_BUILD_TIMEOUT` env-tunable (3466caa3); runbook exports 1200 |
| post-deploy monitoring (cert renewal) | FIXED (runbook step 7.5) | M2: zero tojlo.com endpoints + no cert checks in Gatus → post-verify Gatus endpoint with certificate-expiry condition (gatus driver verified additive) |
| verification-battery completeness | FIXED | B4: battery extended — CRM write probe (catches stale-Pool), ir_queue stuck-row check, gotenberg reachability, `/brand` same-origin router probe, ACME-log diagnostic before the TLS test |
| backup/DR mechanism truth | CORRECTED | M3: per-service Backrest plan vestigial (`/opt/<name>/data` unused); real cover = `docker-volumes` plan (paths live-verified); DR narrative corrected |

## Pass Ledger

```
Pass 1a — MY authoritative pass                       | found: 3  | M1 FIXED · M2 FIXED (7.5) · M3 CORRECTED
Pass 1b — finder A (spec + secrets flow), native      | raised: 8 | A1 FIXED (deploy-breaker) · A2 FIXED (runbook)
                                                                  | A3 upstream · A4 FIXED · A5 guard+upstream
                                                                  | A6 REFUTED (hub-env fallback works — cli dotenv)
                                                                  | A7 REFUTED for this deploy (unquoted JSON verified;
                                                                  |   parser divergence = fleet residual) · A8 by-design
Pass 1c — finder B (infra + runbook), native          | raised: 9 | B1≡A2 · B2 FIXED (step 3b) · B3 FIXED (pause, proven)
                                                                  | B4 FIXED (battery) · B5/B6/B7 REFUTED-by-finder
                                                                  | B8 FIXED (staged file) · B9 confirmed-present
Pass 2  — confirming (fresh read of fixed spec + runbook v2 against every finding) | found: 0
  (pool skipped: documented fanout empty-completion + live-SSH/context needs; advisory deviation noted)
```

## Residuals (named, bounded)

- `from_env` project-.env-first precedence (A5 mechanism) — safe today (guard step + verified value);
  precedence redesign is a hub decision, reported upstream.
- `.env`-parser quote-stripping divergence (A7) — fleet hygiene item, not tripped here.
- No loud deploy-time warning on `from_env` misses (A6 residual) — improvement candidate.
- `host-state` Backrest plan lacks `/usr/local/bin/fabrik-autoheal` — accepted; the sync script is
  the provisioner of record.
- Upstream (project AI): DEPLOYMENT.md step-4 port fix, `--write-env` dead path, restart-after-init
  missing from their own step list, battery additions worth mirroring.
