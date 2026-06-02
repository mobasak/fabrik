# Fleet Hardening + Doc Truth Pass

**Date created:** 2026-05-31 (evening)
**Author:** Özgür Mobasak + Claude
**Plan version:** v3.21 (closed 2026-06-02 — all 16 workstreams + 4 second-order workstreams shipped; first end-to-end spoke deploy proven live with LE cert)
**Status:** ✅ **CLOSED 2026-06-02**

## Closing summary (2026-06-02)

Shipped workstreams (in convergence order; full details inline in § Convergence log above):

| WS | Title | Ship date |
| :--- | :--- | :--- |
| W1 | UFW + fail2ban on spokes | 2026-05-31 evening (external-AI ran it) |
| W2 | Backrest 4 plans on hub + first snapshot | 2026-06-01 (DR-in-hours track) |
| W3 | `fabrik destroy --target-vps` + `fabrik redeploy --target-vps` | 2026-06-02 |
| W4-pre | Spoke `daemon.json` `tag: "{{.Name}}"` | 2026-06-02 |
| W5 | `:8017` rebound to `127.0.0.1` | 2026-06-01 |
| W6 | Probe-vs-doc script (`audit_infra_vs_docs.py`) | 2026-06-01 |
| W8 | Sysadmin smoke + spoke UFW mesh-allow | 2026-06-01 |
| W9 | `/opt/fabrik/.env` + `.env.sysadmin` DR mirror to GitHub | 2026-06-01 |
| W10 | AI sysadmin watchers (backup / mesh / dr_store / cert) | 2026-06-01 |
| W11 | Per-spoke Backrest stack + spoke restore runbook | 2026-06-01 |
| W12 + W12.b | Orchestrator network rename `coolify` → `fabrik` + spec-driven healthcheck | 2026-06-02 |
| W13 | Authelia spoke subdomain verification (no code change) | 2026-06-02 |
| W14 | `SSHDeployer.inject_env` + compose-rollback honor `target_vps` | 2026-06-02 |
| W15 | Spoke Traefik `gzip@docker` middleware | 2026-06-02 |
| W16 | Spoke Traefik baked into `bootstrap-vps.sh` step_12 + DNS via site-provisioner step_13 | 2026-06-02 |

Bundled DR-in-hours work (shipped during W2 + W11): `bootstrap-hub.sh` + `bootstrap-spoke-restore.sh` + `vps-hub-rebuild.md` + `vps-spoke-rebuild.md` + `vps-fleet-architecture.md`.

**The original trigger** (the doc-truth audit that found UFW was not installed on spokes despite docs claiming it was) is fully resolved: probe-driven evidence is now the source of truth (`scripts/audit_infra_vs_docs.py` writes timestamped YAML to `docs/infrastructure/probe-reports/`; every infra doc cites the most recent probe report by date).

**Live evidence of end-to-end success:** `fabrik apply specs/services/spoke-canary.yaml` (target_vps=vps2) on 2026-06-02 returned `✅ Deployment complete: https://canary.vps2.ocoron.com`; `curl` returned HTTP 200; TLS chain showed `Issuer: Let's Encrypt YR2` — **first Let's Encrypt issuance on a spoke ever**.

**Remaining items NOT in scope for this plan** (each has its own home or follow-up):

- W4 (first real tenant on a spoke) — operator-gated; pipeline proven.
- Authelia rules for spoke admin dashboards — gated on a live spoke dashboard existing.
- Spoke tenant backups (`docker-volumes-vpsN` + `postgres-dumps-vpsN`) — gated on actual tenant data.
- DR drill against a fresh throwaway VPS — undrilled by design; needs operator-provisioned VM.
- One clean end-to-end `fabrik apply site-provisioner` round-trip — operator-gated on accepting the postgres-password rotation.

These do not block fleet operations; they're follow-on validation work.
**Estimated total effort:** 8–10 h active across 3 sessions (was 6h in v2 — v2 was optimistic)
**Trigger:** The 2026-05-31 evening doc-truth audit said UFW was active on vps2/vps3 with a "verified live" tag. `dpkg -l ufw` returned empty on both spokes. UFW is **not installed**. The front-line firewall on spokes is actually the DOCKER-USER iptables chain (functionally adequate but not what was documented). Three prior verification passes missed this because each grepped for *failure symptoms* (stale port allows, dead Coolify references) instead of *probing for presence*. Symptom-grep cannot find an absence. This plan fixes that posture, closes adjacent gaps surfaced in the same audit, makes the DR chain whole, and installs a process guardrail.

## 0. Convergence log

| Version | What changed |
| :--- | :--- |
| v1 → v2 | Added W9 (env offsite recovery — the DR keystone). Added W8 (sysadmin smoke). Replaced W6's regex linter with a probe-vs-doc script. Resolved 2 open questions inline. Sequencing fix: W7 snapshot before W2. Hardened acceptance with exact commands. |
| v3.19 → v3.20 | **DNS wiring SHIPPED 2026-06-02 (W16 second pass).** Operator correction: `--skip-dns` workaround was wrong; site-provisioner already exposes all the endpoints needed. `step_13_create_dns_records()` rewritten from stub to live caller. **Path:** SSH to `${FABRIK_HUB_SSH_HOST}` (= vps1) and `curl POST` against the `/api/cloudflare/dns/<root>/subdomain` endpoint on `provision.vps1.ocoron.com`, twice — once for `subdomain="${SPOKE_NAME}"` (apex) and once for `subdomain="*.${SPOKE_NAME}"` (wildcard). Both use ensure_record() under the hood, which returns `action: "unchanged"` when the record already matches. **Why call from vps1:** site-provisioner's Traefik IP allowlist is `172.16.0.0/12, 10.0.0.0/8, 192.168.0.0/16, 172.93.160.197/32, 31.206.44.18/32`. Dev WSL's exit IP varies (W5 saw `176.219.28.59` from TTNet; current run from `46.221.24.2`) — neither is allowlisted. vps1's public IP (172.93.160.197/32) is. The production `API_KEY` lives in `/opt/site-provisioner/.env` on vps1 — never travels to the dev machine. **Spoke public-IP discovery:** `curl -4 -fsS https://ifconfig.me` with `https://ipv4.icanhazip.com` as fallback. The `-4` flag is mandatory — the first attempt without it returned the spoke's IPv6 (`2a0c:b840:2:216::a`) and site-provisioner's `CloudflareSubdomainCreate` model `ip` field has `pattern=r"^\d+\.\d+\.\d+\.\d+$"`, which 422'd. **Live verification:** ran step_13 against vps2 + vps3 — both records returned `action: unchanged` (apex + wildcard, 4 calls total). **`--verify` mode** gained a DNS row that dig's the apex + a wildcard-probe FQDN (`<spoke>-verify-probe.<spoke>.ocoron.com`) against `1.1.1.1` and surfaces what Let's Encrypt would resolve during an HTTP-01 challenge. **Net:** bootstrap pipeline is now fully end-to-end — `./scripts/bootstrap/bootstrap-vps.sh root@<new-ip> vps4` would take a fresh VPS to "ready for `fabrik apply --target-vps vps4`" without `--skip-dns`. |
| v3.18 → v3.19 | **W16 SHIPPED 2026-06-02.** The W15 fix (spoke Traefik `labels:` block) lived only in the live `/opt/traefik/compose.yaml` on vps2 + vps3 — a freshly-bootstrapped spoke would have come up missing it. W16 templates the live state into the bootstrap script so future spokes inherit it on first run. **Files added:** `scripts/bootstrap/templates/traefik.compose.yaml.template` (carries the W15 `traefik.enable=true` + `traefik.http.middlewares.gzip.compress=true` labels — diffed byte-perfect against live vps2 modulo an explainer comment block), `scripts/bootstrap/templates/traefik.yml.template` (LE_EMAIL substitution; rendered output diffed zero against live), `scripts/bootstrap/templates/traefik-dynamic-authelia.yml.template` (HUB_MESH_IP + FABRIK_DOMAIN_ROOT substitutions; rendered output diffed zero against live). **bootstrap-config.sh:** new `FABRIK_LE_EMAIL` constant (default `ob@ocoron.com`, matching live). **bootstrap-vps.sh:** new `step_12_install_spoke_traefik()` between monitoring agents and DNS; old DNS step renamed `step_13_create_dns_records`; `main()` driver updated; `--verify` mode gained a "Traefik (W16)" row that reports container status + presence of the gzip middleware label. **Live idempotency proven** by re-running just step_12 against vps2 — Docker reported `Container traefik Running` (no recreate), uptime preserved, label intact. **Net effect:** a single end-to-end `./scripts/bootstrap/bootstrap-vps.sh root@<new-ip> vpsN` now produces a spoke ready for `fabrik apply --target-vps vpsN` without any post-bootstrap manual edits. |
| v3.17 → v3.18 | **W15 SHIPPED 2026-06-02.** Root cause more nuanced than first thought: spoke Traefik's `traefik.yml` has `providers.docker.exposedByDefault: false`, so adding the `traefik.http.middlewares.gzip.compress=true` label to the Traefik container alone is silently dropped — the docker provider only reads labels from containers with `traefik.enable=true`. **Fix:** add BOTH labels (`traefik.enable=true` and `traefik.http.middlewares.gzip.compress=true`) to the Traefik container's `labels:` block in `/opt/traefik/compose.yaml` on each spoke. Recreate Traefik (sub-5s downtime per spoke). The Traefik container ends up with `traefik.enable=true` but no router labels of its own, so it doesn't try to route to itself — it just publishes the middleware definition. **Live verification:** `fabrik apply specs/services/spoke-canary.yaml --target-vps vps2` ran clean — `✅ Deployment complete: https://canary.vps2.ocoron.com`. `curl` returned HTTP 200; TLS cert chain shows `Issuer: Let's Encrypt YR2`, `notAfter: Aug 30 2026 GMT` — **first Let's Encrypt issuance on a spoke ever**. Container `Up (healthy)` on vps2; hub-side registrars stayed on vps1; gatus + DNS de-provisioning ran on cleanup. Backup symmetry: fresh `host-state` snapshot triggered on both spokes via Backrest API (`/v1.Backrest/Backup` with plan_id selector), host-state count 4 → 5 on each spoke, so the new `/opt/traefik/compose.yaml` is in B2 DR scope. **Folded follow-up into vps-bootstrap-plan.md:** when item 2 (bake spoke Traefik into the bootstrap script) ships, the labels block must come with it so future spokes get the middleware on first bootstrap. Cleanup: ran `fabrik destroy --target-vps vps2` on spoke-canary; compose removed cleanly. CF DNS A record left over (gatus/DNS deprovision tripped on the site-provisioner SSH-proxy bug, pre-existing) — deleted directly via Cloudflare API. |
| v3.16 → v3.17 | **W14 SHIPPED 2026-06-02 (final scope).** First-pass W14 hoisted the env-swap from `SSHDeployer.deploy()` up to `DeploymentOrchestrator.deploy()` to wrap the whole pipeline. That broke hub-side registrars (gatus, postgres-main, authelia all live on vps1) — they started SSHing to the spoke and erroring with "No such container: postgres-main" / "mv: cannot move ... to /opt/monitoring/configs/gatus/apps/...: No such file or directory". **Revert + re-scope:** env-swap is now a `contextlib.contextmanager` `_target_vps_env(ctx)` defined in `deployer_ssh.py`, applied **only** around (1) `SSHDeployer.deploy()`'s inner body (W-Multi M4 contract restored), (2) `SSHDeployer.inject_env()`'s body (W14 motivation — GlitchTip DSN / Redis URL injection on spoke apps now lands on the right host), and (3) `RollbackManager._rollback_compose()` reading `resource.metadata["target_vps"]` (so a failed verify on a spoke deploy tears the container down on the spoke, not the hub). Resource records gained `target_vps` metadata in `ctx.add_resource("compose", ..., target_vps=ctx.target_vps or "vps1")`. Test suite: 108 deployer+integration tests + 22 rollback tests = 130/130 pass. **Live verification:** spoke-canary apply to vps2 — deploy lands on vps2 (`Up About a minute (healthy)`), hub-side registrars stay on vps1 (no more cross-host noise), and after the verifier 404 the rollback correctly removes `/opt/spoke-canary` on vps2 (no "compose rollback failed" message). The 404 itself is a separate vps2-Traefik config gap (W15). **W15 ADDED.** During W14 live verification, the verifier returned 404 from `canary.vps2.ocoron.com/` despite the container being healthy. Root cause: vps2's Traefik logs `middleware "gzip@docker" does not exist` for `routerName=spoke-canary@docker entryPointName=websecure`. The scaffold's `_generate_docker_compose` emits `traefik.http.routers.<svc>.middlewares=gzip@docker` unconditionally on all service deploys; on vps1 the middleware is defined by a label on the `meilisearch` container (`traefik.http.middlewares.gzip.compress=true`), but no spoke-side container defines it, so Traefik on vps2/vps3 has no `gzip` middleware in its dynamic config and rejects the router. Two viable fixes: (a) add `traefik.http.middlewares.gzip.compress=true` to the Traefik container itself in `bootstrap-vps.sh` step_03 (one label, idempotent, future-proof — works regardless of which service ships on the spoke first); or (b) emit the `gzip.compress=true` label on every service the orchestrator deploys (self-defining). Option (a) preferred (one place to fix, no ongoing scaffold-emit duplication). Estimated 15 min. **Blocking effect:** without W15, no spoke deploy can pass the verifier health check, so every spoke-targeted `fabrik apply` rolls back at step 5 even though the deploy + registrars are healthy. |
| v2 → v3 | **Backrest password canonicalization** — direction of reconciliation specified (config.json is canonical at init; copy → .env), plus Lesson 67 about restic password immutability post-init. **W4 fixed:** `template: python-api` (not `docker` — wouldn't validate), Let's Encrypt **staging first** before production cert, spoke daemon.json tag prereq, vps3 uses a separate spec. **W2 hardened:** pg_dump completion marker prevents mid-write snapshots, postgres-dumps path excludes the Coolify-era subdir, failure-hook test now uses `on_snapshot_success` (always-fires, no break-things). **W5 :8017** prefers service rebind over iptables drop; pace probes to avoid fail2ban banning our own dev IP. **W9** scoped to the irrecoverable key + age-encrypted bulk backup. **Pre-mortem section** (§4.5). **Cost analysis** (§4.6). **Daily execution checklist** (§5). **W1** adds iptables backend consistency check. **W3** adds state-file atomic-write verification + missing/corrupt handling. **W8** adds spoke-anomaly safety probe. |
| v3.15 → v3.16 | **W14 ADDED 2026-06-02.** Defect surfaced during W12 verify (deploy spoke-canary to vps2): `SSHDeployer.deploy()` correctly env-swaps `FABRIK_VPS_SSH_HOST=vps2` for the deploy block, so the compose stack creates on vps2. But the `DeploymentOrchestrator.deploy()` call sequence is `_provision_dns → SSHDeployer.deploy → InfrastructureProvisioner.provision`. The env-swap is scoped inside `SSHDeployer.deploy()` only — by the time `InfrastructureProvisioner.provision(ctx)` runs (which dispatches to `GlitchTip.inject_env`, `Redis.inject_env`, `Authelia.add_access_rule`, `Gatus.upsert_endpoint`, etc.), `FABRIK_VPS_SSH_HOST` is back to default vps1. Registrars that need to write to the app's `.env` on the target host (`inject_env`) try `mv /tmp/...env /opt/<app>/.env` on vps1, which has no `/opt/<app>/`. Concrete failure: `mv: cannot move '/tmp/fabrik-1786301-.env' to '/opt/spoke-canary/.env': No such file or directory`. The deploy itself succeeded (container healthy on vps2) but the orchestrator marks it 'rolled back' because the provisioning step errored. **Fix**: hoist the env-swap from `SSHDeployer.deploy()` up to `DeploymentOrchestrator.deploy()` so it wraps the entire dispatch sequence (DNS + deploy + infrastructure + verify + rollback paths all run with `FABRIK_VPS_SSH_HOST` pointed at `ctx.target_vps`). Estimated 20 min. **Verification**: re-deploy spoke-canary to vps2 — must produce a clean SUCCESS (not 'rolled back') with registrars running against vps2. **Blocking effect**: without W14, every W4 attempt to put a real tenant on vps2 or vps3 will hit the same failure mode. |
| v3.14 → v3.15 | **W4-pre + W12 + W13 + W3 ALL SHIPPED 2026-06-02.** Four deploy-tooling gaps closed in one batch: **W4-pre** — spoke `daemon.json` gained `tag: "{{.Name}}"` field on both vps2 + vps3, docker restarted, fresh `host-state` Backrest snapshot triggered so the new daemon.json lands in B2 / DR scope. **W12** — `src/fabrik/orchestrator/deployer_ssh.py::_generate_docker_compose` was emitting `networks: [coolify]` + top-level `coolify:` block; renamed both to `fabrik` (the post-2026-05-31 network name). Also added rejection in `_validate_compose` for legacy `coolify` references with a clear deprecation message so future un-migrated user composes fail loudly with the rename hint. **W12.b** (surfaced during W12 verify): same generator hardcoded `["CMD", "curl", ...]` health probe but `nginx:alpine` (and many other slim images) ships without curl, and the spec's `health.path`/`interval`/`timeout`/`retries` fields were ignored. Replaced with `["CMD-SHELL", "wget -q --spider ..."]` reading from spec. **W13** — Authelia registrar (`src/fabrik/drivers/authelia.py`) inspected: `_validate_domain` accepts arbitrary FQDN, `_domain_shadows("*.vps1", "canary.vps2")` correctly returns False (no cross-spoke shadowing), `add_access_rule(domain="canary.vps2.ocoron.com", dry_run=True)` succeeds. **No code change needed** — registrar is FQDN-pattern-agnostic. Optional follow-up: operator can pre-add `*.vps2`/`*.vps3` wildcard rules for vps1-style policy fan-out; not required. **W3** — `fabrik destroy --target-vps [vps1|vps2|vps3]` + `fabrik redeploy --target-vps ...` flags added with resolution order CLI flag > state file > spec field > vps1. `state.save()` gained `target_vps` field; `_persist_state()` writes `ctx.target_vps`. Env-swap of `FABRIK_VPS_SSH_HOST` wraps both commands so every nested SSH call resolves the right alias. **Live verification on vps2:** deploy canary → destroy with `--target-vps vps2` → compose removed from vps2 (`✅ compose removed app spoke-canary`), vps2 `/opt/spoke-canary` gone, state file gone; vps1 still has 29 containers untouched (CONTROL passed). **Test suite:** 96/96 deployer tests pass after fixture rename `coolify` → `fabrik` in YAML strings (Python field `coolify_uuid` kept by design for back-compat). **Known remaining defects not in scope:** (a) site-provisioner DNS gateway template parsing bug (interim manual stand-up issue, pre-existing); (b) post-deploy registrars don't honor target_vps for env injection (Gatus + DNS still try vps1 — env-swap only covers the SSHDeployer block, not InfrastructureProvisioner). Both fold into future cleanup; neither blocks first-tenant deploy because the deploy itself + cleanup symmetry now work. |
| v3.13 → v3.14 | **W12 + W13 ADDED 2026-06-02.** Spoke-canary deploy attempt exposed 2 deploy-tooling gaps that the wiring layer never had: **W12** — fabrik orchestrator (`src/fabrik/orchestrator/`) hardcodes `network: coolify` in the docker-source compose template generator. Every `fabrik apply` to any target fails at `docker compose up` with `network coolify declared as external, but could not be found` because the network was renamed to `fabrik` on 2026-05-31 but the code generator was missed. Estimated 30-45 min to find + fix (probably one or two strings in the template or `_deploy_docker`). **W13** — Authelia registrar (likely `src/fabrik/drivers/authelia.py`) covers `*.vps1.ocoron.com` rules but spoke-targeted deploys (`*.vps2.ocoron.com`, `*.vps3.ocoron.com`) have never been exercised, so rule-pattern coverage on spokes is unverified. Estimated 30 min to inspect + extend if needed. **Sequencing update:** insert as ship order W4-pre → W12 → W13 → W3 before any real W4 deploy attempt. Without W12, no tenant `apply` works on any host. Without W13, Authelia-gated admin endpoints on spoke tenants wouldn't get rules. Without W3, destroy hits wrong host. |
| v3.12 → v3.13 | **W10 SHIPPED 2026-06-01.** `scripts/sysadmin/proactive-check.sh` extended with 4 watcher blocks: (1) `backup_health` — restic snapshot age per hub plan, threshold 36 h, anomaly `backup_stale[hub:<plan>:<h>h]` or `backup_missing[hub:<plan>]`; (2) `mesh_health` — hub-side `wg show wg0 latest-handshakes` per peer, 5 m / 15 m thresholds, anomalies `mesh_degraded`/`mesh_broken`/`mesh_no_handshake`; (3) `dr_store` — GitHub API `commits?per_page=1` on `mobasak/fabrik-dr-store`, 30-day staleness threshold; reads token from `.env.sysadmin` first, then `.env` (since vps1 doesn't carry `/opt/fabrik/.env` — that file lives only on dev WSL per W9). (4) Cleaned cert-expiry domain list: dropped stale `coolify.vps1.ocoron.com` (deleted in residue cleanup), kept `ocoron.com`/`status/monitor/errors.vps1.ocoron.com`. **Live-test acceptance:** all watchers green at ship — backups 2h-old (well under 36h), mesh handshakes <1m (well under 5m), dr_store dormant with operator-visible WARN logged to `/var/log/sysadmin-proactive.log` (no `GITHUB_TOKEN` in env yet — graceful no-op, not failure). Wall-clock: 6.1 s total. **Tier-A action handlers + persistent cooldown dir (plan §6+§7):** intentionally NOT implemented this pass — the bot has been escalation-only since 2026-05-20 deployment (no autonomous actions ever logged, confirmed via absent action log file), and the W8 safety probe verified that escalation-only IS the correct posture for now. Action handlers can be wired later once spoke-targeted SSH paths exist and have been drilled. **Token onboarding doc:** added to `vps-ai-sysadmin.md` § Layer 4 — operator adds `GITHUB_TOKEN=ghp_xxx` to `/opt/fabrik/.env.sysadmin`, next cron tick activates dr_store watcher. **Outcome:** closes the second half of the operator's 2026-05-31 directive ("everything automated, AI sysadmin watched and fixed") in its surveillance form; auto-remediation form (action handlers) explicitly deferred for safety. |
| v3.11 → v3.12 | **W8 SHIPPED 2026-06-01.** Sanity gate post-W2/W11 Backrest changes. **7/8 acceptance checks PASS:** bot service active, proactive-check.sh exits 0, `:8017/health` ok, `spoke_health` rule group loaded, action-log absence confirms bot has never autonomously acted (safe default since 2026-05-20 deployment), real-anomaly safety verified (the `target_down` finding below triggered escalation to Claude → 'all clear, benign' classification → no autonomous `ssh vps2 docker restart` attempted). 1 informational note: shift notes file untouched since May 20 — bot hasn't been writing them, W10 should add. **Major bonus W8 surfaced:** spoke observability has been silently broken since W1 enabled UFW on spokes (2026-05-31 evening). Spoke node-exporter:9100 / cadvisor:8080 / promtail:9080 unreachable from vps1's Prometheus because UFW default-deny on spokes never had a mesh-allow rule. 12/18 Prometheus targets were DOWN (docs claimed 18/18 because the docs were never re-verified post-W1 ship). **Fixed:** `ufw allow from 10.99.0.0/24` added on both spokes + into `bootstrap-vps.sh` step_02 so future spokes don't repeat. Fresh `host-state` snapshot triggered on both spokes so the new rule is in B2 / DR scope. Post-fix: 18/18 targets up, observability restored. **Lesson worth distilling later:** UFW default-deny + multi-host fleet = need explicit mesh-allow rule for cross-host scrapes; single-operator threat model treats the mesh as fully trusted (no per-port filtering for 10.99.0.0/24). Prior "18/18" claim in vps-status.md was stale-by-omission since W1 — would have surfaced sooner if W6 probe-audit had scraped Prometheus health. |
| v3.10 → v3.11 | **W11 SHIPPED 2026-06-01.** Triggered by operator's call-out: hub-only DR (v3.9) defeated the multi-host fleet's reason to exist. Per-spoke Backrest stack deployed on vps2 + vps3 with **path-preserving mounts** (`/opt`, `/etc`, `/root/.ssh`, `/home/ozgur/.ssh`, `/opt/backrest/.restic-password`). Each spoke writes to its own restic repo at the same B2 bucket but different prefix: `vps1-ocoron-backups/spokes/vps2/` and `/spokes/vps3/`. Independent restic passwords per spoke. **2 plans per spoke** (`host-state` + `opt-configs`); `postgres-dumps` + `docker-volumes` deferred until tenants land (W4). **First snapshots committed:** vps2 = 2 snapshots, 16.9 KiB on B2 (2.31× compression); vps3 = 2 snapshots, 16.5 KiB on B2 (2.33× compression). **W9 mirror extended** to pull 4 new files (`vpsN-backrest-env-latest` + `vpsN-restic-password-latest` per spoke) — protects Lesson 67 (lose the password, lose the chain). **`scripts/bootstrap/bootstrap-spoke-restore.sh`** written (548 lines, 13 steps, mirrors `bootstrap-hub.sh` style + smaller scope: no PG fallback, no claude install, no CF DNS rewrite — spoke DNS unchanged by spoke outage). Key design choice: spoke restore PRESERVES the WG private key from snapshot → hub's `wg0.conf` peer table is unchanged through the outage → rebuilt spoke reconnects with same identity, no peer-table edit. **Two infra docs added:** `vps-fleet-architecture.md` (the 'fleet-as-one-system' picture across all 3 hosts) + `vps-spoke-rebuild.md` (operator runbook). **Spoke-side wiring-gap register update:** the 3 smaller holes (W4 daemon.json tag pre-step, W3 `--target-vps` for destroy/redeploy, W10 spoke-aware AI sysadmin watchers) remain unshipped but explicit. **Mid-ship findings folded back:** (a) Backrest 1.13.0 requires `guid` per repo OR `autoInitialize: true` — used the latter (Lesson worthy for W2/W11 of any future restic-Backrest plan). (b) `/etc/sudoers.d/ozgur` on hub vs `/etc/sudoers.d/90-ozgur` on spokes — inventory miss caught at first backup run, fixed both spoke config.json + spoke-restore-inventory.md. (c) `/var/spool/cron/crontabs` cannot be bind-mounted into the Backrest image (same as hub — Lesson 5/W2 carries over). |
| v3.9 → v3.10 | **W11 ADDED 2026-06-01.** Hub-only DR (today's v3.9 ship) leaves vps2/vps3 unbacked-up — defeats the multi-host fleet's reason to exist (operator bought spokes specifically for fleet resilience). W11 = per-spoke Backrest stack + restic init at bucket-prefix paths (`vps1-ocoron-backups/spokes/vpsN/`) + W9 extension to mirror spoke `.env.backrest` + `bootstrap-spoke-restore.sh` + `vps-spoke-rebuild.md`. Sequenced **before W4** so spoke backups exist at the moment first tenant data lands. **Spoke-side wiring-gap register (consolidated):** (a) W4 pre-step — spoke `daemon.json` missing `tag: "{{.Name}}"` field, promtail container-name labels in Loki broken on spokes (5 min fix). (b) W3 — `fabrik destroy --target-vps` + `fabrik redeploy --target-vps` not symmetric to `apply` (code-only, ~2 h, no urgency until W4 ships a real tenant). (c) W10 — AI sysadmin proactive-check has no auto-action handlers scoped to spokes (currently mesh-aware in Prometheus queries but escalates rather than acts). All three smaller holes were already-in-plan but not framed as 'spoke wiring gaps'; this convergence row makes that framing explicit. Re-sequencing: W8 → W10 → W11 → W4 → W3 → drills. |
| v3.8 → v3.9 | **DR-in-hours track SHIPPED 2026-06-01.** Triggered by deep-review honesty: original plan would have given application-data recovery but NOT a scripted hub rebuild — "few hours" goal unreachable. Built `scripts/bootstrap/bootstrap-hub.sh` (996 lines, 18 idempotent steps, mirrors operator's bootstrap-vps.sh style). Extended Backrest scope: 4 path-preserving bind mounts replaced the original `/backup-*` mangling convention + 5 new mounts for `/etc`, `/usr/local/bin`, `/root/.ssh`, `/home/ozgur/.ssh` (crontab path dropped due to image-internal symlink collision; root crontab dumped via pre-backup.sh to /opt/backups/root-crontab.txt). Added 4th Backrest plan `host-state` (24 paths). W2 of original plan **shipped in scope-extended form:** `restic init` against B2 (repo `a256277c45`); first backups of all 4 plans completed in ~80s — 612 MiB uncompressed → 117 MiB on B2 (5.23× compression). Disaster-recovery.md gained `Path D` (scripted full hub restore, 5 operator commands, 7-check end-state contract). hub-restore-inventory.md created as evidence-based path list. Lessons surfaced: (a) `/var/spool/cron/crontabs` cannot be bind-mounted into many container images due to `/etc/crontabs` symlink — use dump-via-pre-backup.sh instead; (b) Backrest's localhost API requires auth even from inside the container — temporary `auth.disabled: true` flip is the operational pattern for one-shot CLI triggers; (c) `usage()` regex `sed -n '2,/^#$/p'` truncates at first blank-comment line (use awk instead); (d) restic `--target /host` is the only correct target when restoring through a docker-mounted host filesystem. Remaining: DR drill on throwaway VPS to measure actual wall-clock — needs operator-provisioned test VPS. |
| v3.7 → v3.8 | **W9 extended 2026-06-01.** Deep cross-workstream review (`W1+W5+W6+W9`) surfaced a real DR gap: original W9 mirrored only `/opt/fabrik/.env` (dev-WSL canonical). The sysadmin bot's creds (`TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_ID`) live in `vps1:/opt/fabrik/.env.sysadmin`, which was outside DR scope — vps1 disk loss would have meant a BotFather token reissue + manual user-ID lookup. Fix: `scripts/dr_env_backup.sh` refactored to mirror BOTH files in one atomic git commit. `.env` continues to use `env/latest` + `env/fabrik-env-${TS}` (no breaking change for the recovery test). `.env.sysadmin` is SSH-pulled from vps1 (`ssh -o BatchMode=yes -o ConnectTimeout=8 vps 'sudo cat ...'`) and stored at `env/sysadmin-latest` + `env/fabrik-env-sysadmin-${TS}`. Pull failure logs a WARN but does not abort the main mirror — sysadmin file is soft-required. Watcher unchanged (still local-only); sysadmin file is caught on the cron paths (daily 03:30 + @reboot) — ~24 h max latency, acceptable for a file that changes <once/yr. **Live end-to-end test:** first run pushed commit `20260601T012810Z`; `env/sysadmin-latest` (95 B) cmp-clean vs `vps:/opt/fabrik/.env.sysadmin`; immediate re-run reported `no change` (idempotent). Recovery runbook `docs/operations/credential-recovery.md` gained a new section + an updated mermaid block. |
| v3.6 → v3.7 | **W5 SHIPPED 2026-06-01.** All 5 acceptance criteria green. **Step 1+2:** `:8017` was bound `0.0.0.0` (W6 finding) — `scripts/sysadmin/bot.py` patched to honor new `SYSADMIN_HEALTH_HOST` env var (default `127.0.0.1`); patch mirrored on vps1 + local repo; service restarted; backup at `/opt/fabrik/backups/bot.py.backup.20260601-033756`. Post-bind: external probe from vps2 + vps3 = `timed out (filtered)`, local loopback returns `{"status":"ok",...}`. No Gatus/Prometheus consumer broken (the "for Gatus monitoring" comment was aspirational, never wired). **Step 3:** mesh-port sweep — 9 ports (5432, 6379, 8000, 9091, 3100, 9090, 9100, 8080, 7700) × 3 hosts from off-mesh source vps2 = 0 of 27 connects (18 timed out, 9 refused self-source). **Step 4:** UFW v4/v6 rule mirror — vps1 6/6, vps2 4/4, vps3 4/4, balanced. **Step 5:** Verification log appended to `docs/infrastructure/vps-status.md` with timestamps. Dev-WSL exit IP `176.219.28.59` not in any fail2ban jail post-probe. **Probing-methodology discovery → Lesson 72:** dev-WSL `nc`/`/dev/tcp` reported `:8017` as "succeeded" while the bind was already `127.0.0.1` — Türk Telekom AS9121 transparent middlebox spoofing SYN-ACKs. Cross-checked against vps2 + vps3 (clean AS) for ground truth. Future external-exposure probes must NOT trust dev-WSL TCP-state reads. |
| v3.5 → v3.6 | **W6 SHIPPED 2026-06-01.** All 7 acceptance criteria green. Three navigation-time divergences from spec, recorded here for honesty: **(D1) Report path:** plan said `data/`; shipped at `docs/infrastructure/probe-reports/` so YAML + the docs that cite it travel in the same diff. Pre-flight `mkdir -p /opt/fabrik/data/` no longer applicable. **(D2) Probe set:** plan listed 13 probes; ship has 17 — added `ufw_rule_count_v4`, `ram_used_mb`, `ram_total_mb`, `docker_network_fabrik`; replaced `wg_handshake_age` (per-peer string) with `wg_peers_alive` (integer, easier diff). **(D3) Doc coverage:** plan listed 4 docs in scope; extended `INFRA_DOCS` linter list to 6 (added `vps-ai-sysadmin.md`, `vps-residue-policy.md`) — both make provenance claims about live state. **Bundled-SSH demuxer optimization** (Lessons 70/71): 51 sequential SSH calls (75 s) → 3 bundled-probe calls (6.2 s, well under plan's <10 s target). **W6 doc-truth findings folded into infra docs:** (a) `vps-status.md` Verification log section added with probe table + 5 findings; (b) `vps-complete-inventory.md` sysadmin `:8017` row corrected — was misleadingly "blocked from Docker via DOCKER-USER"; probe shows `0.0.0.0:8017` bind, which `DOCKER-USER` does NOT cover; W5 is the remediation; (c) `vps-status.md` spoke posture row gained a `Promtail gRPC` line documenting the `*:<random>` bind (UFW-shielded but undocumented before W6). |
| v3.4 → v3.5 | **W1 SHIPPED 2026-05-31 evening.** External AI executed W1 unauthorized during what was meant to be a review pass. Verified after the fact: UFW installed (`dpkg ii`) and active on vps2 + vps3; 8 ALLOW rules each (22/80/443/51820 IPv4 + IPv6); DOCKER-USER chain unchanged (2 rules); iptables backend matches vps1 (`iptables-nft`); fail2ban active; mesh handshakes alive; mesh-only ports verified blocked via tcpdump (only SYNs arrive, no SYN-ACK leaves). Container counts unchanged 29/4/4. All 7 W1 acceptance criteria pass per probe report `data/infra-probe-2026-05-31T22-36Z.yaml`. **Lesson 68 captured:** pre-W1 UFW state was package status `rc` (removed-with-config), not "never installed" — `dpkg -l ufw \| awk '/^ii/'` returned empty because the filter required `ii`, but the init script + `/etc/ufw/user.rules` still existed from a prior install. `apt-get install ufw` re-brought it to `ii`; no `purge` needed. |
| v3.3 → v3.4 | **External-AI review (2026-05-31 evening) found 6 verified defects; all 6 fixed inline.** B1: W9 recovery test rewritten to route restic through Backrest's in-container `/bin/restic` via SSH (host-side restic NOT installed on WSL — `command -v restic` returned empty). B2: W9 step 1 switched from `git clone git@github.com:...` (SSH) to `gh repo clone` (HTTPS, matching `gh auth status` protocol). B3: W3 step 4 atomic-write claim corrected — `_persist_state` delegates to `state.py::save()` which already has temp-file + `os.replace()` AND per-PID-suffix concurrency protection at `state.py:164-168`. Plan now reads "already done, confirm by reading those lines." B4: W3 destroyer instructions rewritten — destroyer.py uses module-level functions (`_destroy_compose`, `destroy_deployment`, `destroy_from_state`) with no `ctx`; threading `target_vps` requires 3 signature changes, not a copy-paste wrap. B5: W10 dr-store watcher language fixed — "anonymous-API with token" was a contradiction; now uses `Authorization: Bearer ${GITHUB_TOKEN}` (token already in `.env` per pre-flight #11). B6: W4 acceptance table — removed unreachable "Staging cert chain shows Fake LE Intermediate X1" row since v3.2 dropped staging-first (staging is now a fallback only if first prod issuance fails). |
| v3.2 → v3.3 | **Veteran-review blockers B3–B8 resolved with verification (not assumption):** B3 — `_persist_state` grep-confirmed at line 364 of `orchestrator/__init__.py`. B4 — `templates/python-api/` confirmed exists (`ls templates/` shows 16 templates incl. `file-worker`, `file-api`, `node-api`, `saas-skeleton`). B5 — W8 induced spike uses `nohup bash -c ... </dev/null >/dev/null 2>&1 &` (survives SSH teardown). B6 — W9 backup uses `cmp -s` content check before writing the timestamped file (no commit noise). B7 — W10 cooldowns moved from `/var/run/` (tmpfs) to `/var/lib/sysadmin/cooldowns/` (persistent). B8 — `action_restart_wg_hub` gated by `SYSADMIN_AUTONOMOUS_WG_RESTART=false` opt-in default. **W2 paths corrected:** plan-creation uses Backrest's container-internal mount points (`/backup-opt`, `/backup-postgres`, `/backup-volumes`) verified via `docker inspect backrest`. Restic password held in 3 synced locations (host `/opt/backrest/.restic-password` file → container `/restic-password`, plus `.env` and `config.json` for compat). **W9 rewritten for WSL transience:** inotify file-watcher (change-driven push within seconds) + daily cron safety net + `@reboot sleep 60` catch-up. AI sysadmin alert threshold = 30 days (env rarely changes). **3 open assertions documented** with explicit fallback paths (Backrest plan JSON schema, hook event name, REST API trigger path) — verify at execution time, not assumption-time. |
| v3 → v3.2 | **Operator directives applied:** "no manual GUI work" + "no extra encryption (Backrest restic encryption is structural and stays)" + "AI sysadmin watches + fixes infra." **W7 DROPPED** — GreenCloud doesn't expose VirtFusion API; provider snapshots removed from plan; rollback for W2 is config.json git diff + restic forget. **W9 rewritten** — no password manager, no paper, no `age` layer. Simple: `/opt/fabrik/.env` mirrored to a private GitHub repo (`mobasak/fabrik-dr-store`) via nightly cron; private-repo privacy IS the security boundary (same threat model as the main code repo). Weekly DR self-test cron runs `restic snapshots` with recovered creds. **W10 NEW** — extends `proactive-check.sh` with 4 watchers (backup snapshot age, cert expiry, Wireguard mesh handshake age, DR-store last-commit age) + Tier A action handlers (force backup, restart traefik, restart wg-quick) + cooldown system. **W2 simplified** — no Backrest UI step; plans created by editing `config.json` directly + `docker restart backrest`. **Pre-flight log** (§10) — 8 probes run pre-execution, findings folded back into W2/W4. Key findings: passwords already match (W2 step 3 is no-op); spoke Traefik has no caServer line so prod is the default (W4 staging-first dropped); restic lives at `/bin/restic` inside backrest container. |

---

## 1. Goals (outcomes)

1. The documented firewall posture matches reality on every host.
2. A vps1 root-disk loss does not equal data loss — backups land in B2, with a tested restore path, and a Gatus probe so silent failures are alertable.
3. The dev WSL is not a single point of failure for credential recovery.
4. `fabrik` has full lifecycle parity for spoke deploys (`apply` + `destroy` + `redeploy` all support `--target-vps`).
5. At least one real spoke deploy has been exercised end-to-end including Let's Encrypt issuance.
6. Every "verified live" claim in `docs/infrastructure/` is traceable to a probe log entry from the actual host.
7. The AI sysadmin bot has a known, safe behavior when it observes spoke anomalies (won't autonomously act on hosts it can't reliably reach).

Non-goals: credential rotation, scope-tightening the CF token, watchdog plan P2, microservice redeploys.

---

## 2. Workstreams

Each is independently shippable. Sequencing in §3. Pre-mortem (§4.5) lists likely failure modes and the response per workstream.

### W1 — ✅ SHIPPED 2026-05-31 evening — Spoke firewall parity (defense-in-depth)

**Status:** Done, end-to-end verified 2026-06-01. UFW installed + active + correctly configured on vps2 + vps3. All 7 acceptance criteria pass per `docs/infrastructure/probe-reports/infra-probe-2026-05-31T23-07Z.yaml`. **Bootstrap patch verified through the actual `remote` SSH wrapper** by replaying step_02 line-by-line against vps2 + vps3: apt install no-op (already at `ii`), Lesson 68 rc-state detector correctly skipped reinstall, ufw allow loops idempotent ("Skipping adding existing rule"), ufw enable confirmed "Firewall is active," both self-verify lines returned PASS, no container/mesh disruption (29/4/4 unchanged, mesh handshakes <3 min). Initial install was executed unauthorized by an external AI during what was meant to be a review pass; verified after the fact and accepted because the work was operationally correct.

**Key finding folded back into Lesson 68:** the pre-W1 state was UFW **package status `rc`** ("removed but config files remain"), not "never installed." That's why `dpkg -l ufw` returned empty in pre-flight (filter was `/^ii/`) while `systemctl is-active ufw` returned "active" (init script still present from prior install). The `ufw` binary was missing, so existing `user.rules` were never applied. The fix that worked: `apt-get install ufw` brings the package back from `rc → ii`, then `ufw --force enable` applies the existing rules. No `purge` was needed.

**Problem.** `dpkg -l ufw` on vps2 + vps3 returns empty. fail2ban is active. DOCKER-USER chain has `DROP -i ens3 multiport dports 5432,6379,9090,9091,9100,8080,3100,7700,8000` + `ACCEPT -i wg0`. Functionally adequate, but docs claim UFW is active, defense-in-depth wanted, and the bootstrap script's `step_02` ran `apt-get install ufw fail2ban` yet UFW didn't stick — root cause unknown.

**Plan of action.**

1. Read `step_02_install_firewall_fail2ban()` in `scripts/bootstrap/bootstrap-vps.sh`. Capture the exact command.
2. On vps2: `sudo grep -E 'ufw|fail2ban' /var/log/apt/history.log /var/log/apt/term.log 2>/dev/null | head -40` — did UFW install ever appear? Was it removed?
3. **iptables backend consistency check** (Ubuntu 24.04 has both legacy + nft):

   ```bash
   ssh vps2 'sudo update-alternatives --display iptables 2>&1 | grep "currently points"'
   # Expect: "currently points to /usr/sbin/iptables-nft" OR "...iptables-legacy"
   # IMPORTANT: UFW + Docker must both use the same backend; otherwise rules don't compose.
   # If Docker is using iptables-nft (default on 24.04) and UFW would default to legacy, force consistency:
   ssh vps2 'sudo update-alternatives --set iptables /usr/sbin/iptables-nft'
   ```

4. Reinstall + configure UFW on each spoke (idempotent):

   ```bash
   for h in vps2 vps3; do
     ssh "$h" 'sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq && \
       sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ufw && \
       sudo sed -i "s/^IPV6=.*/IPV6=yes/" /etc/default/ufw && \
       sudo ufw default deny incoming && \
       sudo ufw default allow outgoing && \
       sudo ufw allow 22/tcp comment "SSH" && \
       sudo ufw allow 80/tcp comment "HTTP" && \
       sudo ufw allow 443/tcp comment "HTTPS" && \
       sudo ufw allow 51820/udp comment "Wireguard mesh" && \
       sudo ufw --force enable'
   done
   ```

5. Patch `bootstrap-vps.sh` if root-cause from step 2 reveals a bug (e.g., race with systemd, package set wrong, etc.). Add a self-verify at the end of `step_02`:

   ```bash
   command -v ufw >/dev/null || { err "step_02: ufw command missing post-install"; return 1; }
   sudo systemctl is-active ufw >/dev/null || { err "step_02: ufw service not active"; return 1; }
   ```

6. Sanity-check that adding UFW didn't break DOCKER-USER:

   ```bash
   ssh vps2 'sudo iptables -L DOCKER-USER -n -v'
   # Expect: still 2 rules: DROP on ens3 for mesh ports, ACCEPT on wg0.
   ```

**Acceptance:**

| Command | Expected |
| :--- | :--- |
| `ssh vps2 'sudo ufw status \| head -1'` | `Status: active` |
| `ssh vps3 'sudo ufw status \| head -1'` | `Status: active` |
| `ssh vps2 'sudo ufw status \| grep -c "ALLOW"'` | `8` (4 IPv4 + 4 IPv6) |
| `ssh vps2 'dpkg -l ufw \| awk "/^ii/ {print \$2}"'` | `ufw` |
| `ssh vps2 'sudo iptables -L DOCKER-USER -n \| grep -c -E "DROP\|ACCEPT"'` | `2` (unchanged from pre-W1) |
| `ssh vps2 'sudo update-alternatives --display iptables \| grep currently'` | matches `ssh vps`'s value (consistent backend) |
| `ssh vps2 'sudo fail2ban-client status sshd \| grep "Currently failed"'` | non-empty |

**Silence Telegram alerts?** Yes, briefly — UFW reload may flap a 1-2 s gap. `amtool silence add alertname=ContainerDown --duration=5m --comment="W1 ufw install"`.

**Risk.** Low. UFW default-deny + allow list is functionally equivalent to the current state. Worst case: rule ordering issue between UFW and DOCKER-USER blocks Traefik port 80/443 — rollback: `sudo ufw disable` (DOCKER-USER survives, traffic restored).

**Estimate.** 45 min (was 30 in v2 — added backend check + root-cause time).

---

### W2 — Backrest reactivation against B2

**Status:** SHIPPED 2026-06-01 in scope-extended form (DR-in-hours track). Original 3-plan W2 became 4-plan (`postgres-dumps` + `docker-volumes` + `opt-configs` + `host-state`) with path-preserving bind mounts. `restic init` against B2 succeeded (repo `a256277c45`). First backups: 4 snapshots, 612 MiB → 117 MiB on B2. See CHANGELOG entry "DR-in-hours track" for full detail.

**Problem.** Backrest config has 1 repo (`b2-vps1` → `s3://vps1-ocoron-backups`), 0 plans. `restic snapshots` against the URI fails — the bucket was never `restic init`'d at restic level. pg_dump cron (`30 1 * * *` → `/opt/backups/pre-backup.sh`) still runs but dumps stay disk-local. **Real restore from B2 today would fail.**

**Plan of action.**

1. **Pre-flight rollback record** (W7 dropped — no provider snapshot available). Capture pre-W2 state in git-trackable form:

   ```bash
   ssh vps 'sudo cp /opt/backrest/config/config.json /opt/backrest/config/config.json.pre-w2.bak'
   cp /opt/fabrik/.env /opt/fabrik/backups/.env.pre-w2.$(date +%Y%m%d-%H%M%S)
   # Backrest config is also covered once the opt-configs plan runs; this is the explicit pre-state.
   ```

2. Verify Backrest container's bind mounts:

   ```bash
   ssh vps 'sudo docker inspect backrest --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}"'
   # Expect: /opt/backups, /var/lib/docker/volumes, /opt/backrest/config, /opt (ro), /var/run/docker.sock
   ```

3. **Canonicalize the restic password** (Lesson 67). Pre-flight 2026-05-31 confirmed: `config.json` password and `/opt/fabrik/.env::BACKREST_RESTIC_PASSWORD` already match (both 64 chars, both start with `229665`). Re-verify and proceed:

   ```bash
   BACKREST_PW=$(ssh vps 'sudo python3 -c "import json; print(json.load(open(\"/opt/backrest/config/config.json\"))[\"repos\"][0][\"password\"])"')
   ENV_PW=$(grep '^BACKREST_RESTIC_PASSWORD=' /opt/fabrik/.env | cut -d= -f2-)
   [ "$BACKREST_PW" = "$ENV_PW" ] && echo "OK: passwords match" || {
     echo "DIVERGED — config.json is canonical; reconciling .env"
     cp /opt/fabrik/.env /opt/fabrik/backups/.env.backup.$(date +%Y%m%d-%H%M%S)
     sed -i "s|^BACKREST_RESTIC_PASSWORD=.*|BACKREST_RESTIC_PASSWORD=${BACKREST_PW}|" /opt/fabrik/.env
   }
   ```

4. `restic init` — idempotent. **Use `/bin/restic`** (pre-flight 2026-05-31 confirmed: `restic` is not in PATH inside the container, but `/bin/restic` v0.18.1 is the correct path):

   ```bash
   RESTIC_PW=$(ssh vps 'sudo python3 -c "import json; print(json.load(open(\"/opt/backrest/config/config.json\"))[\"repos\"][0][\"password\"])"')
   ssh vps "sudo docker exec -e RESTIC_PASSWORD='${RESTIC_PW}' \
     -e AWS_ACCESS_KEY_ID='$(grep '^B2_KEY_ID=' /opt/fabrik/.env | cut -d= -f2-)' \
     -e AWS_SECRET_ACCESS_KEY='$(grep '^B2_APPLICATION_KEY=' /opt/fabrik/.env | cut -d= -f2-)' \
     backrest /bin/restic -r s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups init"
   # Expect: "created restic repository ..." OR (if re-run) "Fatal: repository already exists" (both = success)
   ```

5. **pg_dump race-window assessment.** v3 originally proposed a `.pg_dump_complete` marker. After review: site_provisioner is 8 MB, glitchtip is 80 MB — pg_dump finishes in <10 s. Backrest's `postgres-dumps` plan runs at 02:00, 30 min after pre-backup.sh kicks off at 01:30. Race window is structurally absent. **Skip the marker.** Optional: confirm by reading the last 100 lines of `/opt/backups/pre-backup.log` and noting the dump-completion timestamp vs the next-day's Backrest snapshot timestamp once W2 is live.

6. Create 3 plans by editing `/opt/backrest/config/config.json` directly (per operator's no-GUI directive) — Backrest reads from disk on restart. **Paths below use container-internal mount points** (pre-flight 2026-05-31 verified the bind mounts: `/opt` → `/backup-opt` ro, `/opt/backups` → `/backup-postgres` rw, `/var/lib/docker/volumes` → `/backup-volumes` ro). **Plan JSON schema must be discovered at execution time** (assertion O1 in §10) — use the proto source at `github.com/garethgeorge/backrest/internal/api/v1alpha1/*.proto` OR capture a XHR from the UI by opening `https://backup.vps1.ocoron.com` once in a browser.

   | Plan ID | Container path | Excludes | Schedule | Retention |
   | :--- | :--- | :--- | :--- | :--- |
   | `postgres-dumps` | `/backup-postgres/pg_dump_*.sql.gz` | `/backup-postgres/coolify-env-backups/**` | `0 2 * * *` (after 01:30 pre-backup.sh) | keep-daily 7, keep-weekly 4, keep-monthly 6 |
   | `docker-volumes` | `/backup-volumes/` | `*-restic-cache*`, `monitoring_prometheus_data/**`, `monitoring_loki_data/**` | `0 3 * * *` | keep-daily 3, keep-weekly 2 |
   | `opt-configs` | `/backup-opt/*/compose.yaml`, `/backup-opt/*/.env`, `/backup-opt/authelia/config/`, `/backup-opt/monitoring/configs/` | `/backup-opt/backups/**` (Coolify-era) | `0 3 * * *` | keep-daily 30 (small) |

   The `postgres-dumps` plan implicitly covers all current + future DBs on `postgres-main` (`glitchtip`, `site_provisioner`, and any future `cost_ledger` / watchdog-platform DBs that land on the shared instance).

7. Failure-hook URL on every plan: `http://apprise:8000/notify/alerts` (NOT the old `apprise-<uuid>:8000` per Issue 1 in `vps-complete-inventory.md`).
8. **Failure-hook test via the `on_snapshot_success` hook** (always-fires; falls back to `on_error` + a deliberately-broken plan if your Backrest version doesn't support success hooks):
   - Edit `config.json`: add a `hooks` entry on the `opt-configs` plan with `conditions: ["CONDITION_SNAPSHOT_SUCCESS"]` + `webhookUrl: http://apprise:8000/notify/test`.
   - `docker restart backrest`.
   - Trigger an immediate `opt-configs` backup: `curl -X POST http://backrest:9898/v1/plans/opt-configs/backup-now` (verify the actual endpoint via `docker exec backrest backrest --help` first).
   - Verify Telegram receives the test alert within 2 min.
   - Remove the test hook from config.json + restart Backrest.
9. Run the production `opt-configs` backup; verify `restic snapshots` lists it:

   ```bash
   ssh vps 'sudo docker exec backrest restic -r s3:... snapshots | tail -5'
   # Expect: at least 1 snapshot with paths matching the plan.
   ```

10. Add Gatus probe (if absent) — `http://backrest:9898/healthz` so a Backrest crash itself is alertable:

    ```bash
    ssh vps 'sudo ls /opt/monitoring/configs/gatus/apps/backrest.yaml'
    # If exists, verify it probes /healthz; else write it.
    ```

11. Update `docs/operations/disaster-recovery.md`: remove the "currently aspirational" caveats; document the exact restore command path including the canonical password source.
12. **Add Lesson 67** to `docs/LESSONS_LEARNT.md`:

    > **Lesson 67 — restic repository password is set at init and is effectively immutable.**
    >
    > **Context (2026-05-31):** Backrest stores the restic password in its `config.json`. `/opt/fabrik/.env` holds the DR copy. They diverged silently. If `restic init` runs against B2 with password A and `.env` later says password B, the off-VPS copy decrypts nothing. restic supports `key add` / `key passwd` but those require an already-readable repo — useless during DR.
    >
    > **Rule:** Decide the canonical restic password BEFORE running `restic init`. The password is held in **three** places that must stay synced: `/opt/backrest/.restic-password` on the host (mounted into Backrest's container as `/restic-password`), `/opt/fabrik/.env::BACKREST_RESTIC_PASSWORD` (DR copy, mirrored to W9 GitHub store), and Backrest's own `config.json::repos[0].password` (legacy field, kept for backward compat). All three currently hold the same 64-char value (verified 2026-05-31). After init, never change the password except via the live `restic key passwd` workflow on a healthy repo. Treat post-init password changes as a full DR-key-rotation event.
    >
    > **How to apply:** Any plan that adds or reactivates a restic-backed backup must canonicalize the password first. The doc `docs/operations/disaster-recovery.md` § Path B (B2 cold restore) is the source-of-truth for which env var the password lives in.

**Acceptance:**

| Check | Expected |
| :--- | :--- |
| `BACKREST_PW == ENV_PW` after step 3 | yes |
| `ssh vps 'sudo docker exec backrest restic snapshots'` | At least 1 snapshot listed |
| `curl -sS http://backrest:9898/v1/plans` (from inside fabrik network) returns 3 plans | yes |
| `restic forget --dry-run` for each plan reports its retention applies | yes |
| Telegram receives the `on_snapshot_success` test alert within 2 min | yes |
| Backblaze console: `vps1-ocoron-backups` bucket bytes > 0 | yes |
| `.pg_dump_complete` marker file appears after the 01:30 cron, before the 02:00 plan run | yes |
| Gatus probe for Backrest exists | yes |
| Lesson 67 in `docs/LESSONS_LEARNT.md` | yes |
| `docs/operations/disaster-recovery.md` § Path B has step-by-step restore using `BACKREST_RESTIC_PASSWORD` + `B2_KEY_ID` from `/opt/fabrik/.env` | yes |

**Silence Telegram alerts?** Yes — Backrest container restart during plan creation may flap ContainerDown for ~30 s. 10-min silence covers the whole workstream.

**Risk.** Medium. Wrong password direction in step 3 would orphan future snapshots from the DR copy. Mitigation: backup of `/opt/fabrik/.env` taken first. Plan misconfiguration cannot harm production data — only adds B2 storage charges (negligible at our scale).

**Estimate.** 75 min (was 60 — added canonicalization + marker file).

---

### W3 — Symmetric `--target-vps` lifecycle (M5)

**Problem.** `fabrik apply --target-vps` shipped today (M4). `destroy` and `redeploy` still hit vps1 unconditionally — the env-swap wrapper exists only on `SSHDeployer.deploy()`.

**Plan of action.**

1. **`fabrik destroy --target-vps`** — extend `src/fabrik/cli.py::destroy` with the Click option. **The destroyer is NOT a class method — it's module-level functions with no `ctx` (external-AI review B4 fix).** Signatures today (verified 2026-05-31):
   - `_destroy_compose(name: str, dry_run: bool, drop_data: bool = False)` at `destroyer.py:314`
   - `destroy_deployment(...)` at `destroyer.py:472`
   - `destroy_from_state(...)` at `destroyer.py:616`

   So the work is **threading the value through 3 function signatures**, not a copy-paste of `SSHDeployer.deploy()`'s `try/finally`. Concrete change:
   - Add `target_vps: str = "vps1"` kwarg to `_destroy_compose`, `destroy_deployment`, `destroy_from_state`
   - Resolve at the CLI layer: CLI flag > state file (`.fabrik/state/<id>.json::target_vps`) > spec field > "vps1"
   - Apply the env-swap at `_destroy_compose` (the only layer that owns the actual SSH calls — the higher functions only orchestrate)

2. **`fabrik redeploy --target-vps`** — same on `src/fabrik/cli.py::redeploy`. The redeploy command is simpler (it's a single SSH session for git pull + compose up), so the env-swap can wrap the SSH block directly without a signature change. Read `redeploy()` first to confirm shape before patching.
3. **State-file annotation** — `SSHDeployer.deploy()` writes `target_vps` into `.fabrik/state/<id>.json` on success. Update `src/fabrik/orchestrator/__init__.py::_persist_state` (verified at line 364 per pre-flight 2026-05-31). **Always write the field** (even when `vps1`) so the file is self-describing.
4. **Atomic write — ALREADY DONE (external-AI review B3 fix).** `_persist_state` in `__init__.py:364` only assembles the payload then delegates to `src/fabrik/state.py::save()`. The atomic write already lives at `state.py:164-168` and is *better* than what an earlier draft of this plan proposed — it uses a per-PID-suffixed temp file (`.tmp.{os.getpid()}`) + `file_lock()` + `os.replace()`, which protects against both crashes *and* concurrent applies. Nothing to fix here. Confirm by reading those lines once before writing W3 code.

5. **Missing/corrupt state-file handling** — both new commands MUST default to vps1 + emit `WARN: state file missing or has no target_vps key; defaulting to vps1`. Never refuse to operate.
6. **Cross-host registrar cleanup research** (record finding, don't fix here): does the current `destroy_deployment()` clean up Authelia rules / Gatus probes / postgres DBs when the target service was on a spoke? If those resources were registered against the hub (which they were — registrars all run on vps1), the destroy already cleans them up by hitting vps1 directly. Verify with a grep — confirm none of the registrar destroy paths require ssh-ing to the spoke. Add finding to plan execution log.
7. Tests (6 new):
   - `test_destroy_target_vps_vps2_sets_env`
   - `test_destroy_target_vps_vps1_does_not_swap`
   - `test_destroy_env_restored_after_destroy`
   - `test_redeploy_target_vps_vps2_sets_env`
   - `test_redeploy_target_vps_vps1_does_not_swap`
   - `test_redeploy_env_restored_after_redeploy`
8. Doc updates:
   - `docs/operations/deployment.md` — `--target-vps` on destroy + redeploy CLI reference sections.
   - `docs/infrastructure/vps-urls.md` § Maintenance commands — destroy + redeploy spoke examples.
9. CHANGELOG entry: `### Added — fabrik destroy/redeploy --target-vps (W-Multi M5) (2026-05-31)`.

**Acceptance:**

| Check | Expected |
| :--- | :--- |
| `.venv/bin/fabrik destroy --help \| grep target-vps` | non-empty |
| `.venv/bin/fabrik redeploy --help \| grep target-vps` | non-empty |
| Pre-check: `.venv/bin/python -c "from fabrik.spec_loader import CoolifyConfig"` either succeeds OR `test_destroyer.py` is patched to remove the import | yes (decide before running pytest) |
| `.venv/bin/pytest tests/orchestrator/test_destroyer.py tests/orchestrator/test_deployer_ssh.py -q` | 0 failures |
| State file after `--target-vps vps2` apply has `"target_vps": "vps2"` | yes |
| State file after default apply has `"target_vps": "vps1"` (explicit) | yes |
| Destroying a service with no flag reads target_vps from state → routes there | yes |
| Destroying a pre-2026-05-31 state file (no `target_vps`) emits WARN and routes to vps1 | yes |
| `_persist_state` uses temp-file + `os.replace()` | yes |
| Cross-host registrar cleanup research finding documented | yes |

**Silence Telegram alerts?** No — code change only, no live container mutation.

**Risk.** Medium-low. Identical pattern to M4. State file lock contention is the subtle one; mitigated by atomic write.

**Estimate.** 2 h (unchanged from v2).

---

### W4 — First real spoke deploy (validation)

**Problem.** Spoke Traefik has never requested a Let's Encrypt cert. `/opt/traefik/acme.json` on each spoke is 0 bytes. Mesh + DNS + Authelia + observability wiring all exist on paper but have never carried a real service.

**Pre-step (5 min, MUST run before any spoke deploy):** spoke `daemon.json` is missing the `tag: "{{.Name}}"` directive that promtail relies on for `container_name` log labels. Without it, Loki logs from spokes don't have the `container_name` label — verification step 3 (Loki query) would fail not because the service isn't logging but because the label isn't populated.

Use a script file (avoids 4-level nested-quote escaping which is fragile):

```bash
# On dev WSL — create the patcher locally:
cat > /tmp/patch_daemon_json.py <<'PYEOF'
import json
import sys

path = "/etc/docker/daemon.json"
with open(path) as f:
    d = json.load(f)
log_opts = d.setdefault("log-opts", {})
if log_opts.get("tag") == "{{.Name}}":
    print("already patched")
    sys.exit(0)
log_opts["tag"] = "{{.Name}}"
with open(path, "w") as f:
    json.dump(d, f, indent=2)
print("patched")
PYEOF

# Push + run on each spoke:
for h in vps2 vps3; do
  scp /tmp/patch_daemon_json.py "$h":/tmp/patch_daemon_json.py
  ssh "$h" 'sudo python3 /tmp/patch_daemon_json.py && \
            sudo systemctl restart docker && \
            rm /tmp/patch_daemon_json.py'
done
rm /tmp/patch_daemon_json.py
```

**Plan of action — commit to a specific spec.**

1. Create `specs/services/spoke-canary.yaml`:

   ```yaml
   id: spoke-canary
   kind: service
   # NOTE: source.type=docker uses _deploy_docker which generates compose
   # without consulting the template. template field is REQUIRED by the schema
   # but unused at deploy time. python-api is a known-good value.
   template: python-api
   domain: spoke-canary.vps2.ocoron.com
   target_vps: vps2
   shape:
     kind: service
     is_public: true
     is_admin_dashboard: false
     needs_database: false
     needs_cache: false
     has_persistent_data: false
     has_search_feature: false
     exposes_metrics: false
   source:
     type: docker
     image: nginx:alpine
     image_port: 80
   env:
     NGINX_HOST: spoke-canary.vps2.ocoron.com
   resources:
     memory: 64M
     cpu: "0.1"
   health:
     path: /
     interval: 30s
     timeout: 5s
     retries: 3
   ```

2. **Deploy directly to LE production** (pre-flight 2026-05-31 found spoke traefik.yml has NO `caServer` line at all — defaults to LE prod, matching vps1's working config. Staging-first would require inserting a new line; the rate-limit math is generous enough to skip it):

   ```bash
   .venv/bin/fabrik apply specs/services/spoke-canary.yaml --yes 2>&1 | tee /tmp/spoke-canary-deploy.log
   # Wait ~60s for cert issuance:
   sleep 90
   curl -vS https://spoke-canary.vps2.ocoron.com/ 2>&1 | grep -E "issuer:.*Let's Encrypt"
   ```

3. **If cert issuance fails** (HTTP-01 challenge timing): inspect `acme.json` for the error, restart Traefik once, retry. If still failing after 2 attempts, fall back to staging-first by inserting `caServer: https://acme-staging-v02.api.letsencrypt.org/directory` into the `acme:` block — fix the underlying issue, then revert.

   ```bash
   # Inspect the actual error (acme.json is JSON):
   ssh vps2 'sudo python3 -c "import json; d=json.load(open(\"/opt/traefik/acme.json\")); print(json.dumps(d, indent=2))" | head -30'
   ```

4. Verify the rest of the pipeline:
   - DNS: `dig +short @lex.ns.cloudflare.com spoke-canary.vps2.ocoron.com` → `96.9.214.128`
   - Container: `ssh vps2 'sudo docker ps --filter name=spoke-canary --format "{{.Status}}"'` → `Up X seconds (healthy)`
   - acme.json: `ssh vps2 'sudo wc -c /opt/traefik/acme.json'` → `> 1000` (was 0)
   - External: `curl -sS -o /dev/null -w "%{http_code}" https://spoke-canary.vps2.ocoron.com/` → `200`
   - Gatus: probe `spoke-canary` appears in UI, green within 90 s
   - Loki: `{host="vps2", container_name="spoke-canary"}` returns lines from the past 5 min (requires the daemon.json prereq above)
   - Prometheus: `node-spokes` job for vps2 still up (no regression)
5. **Repeat on vps3** — create `specs/services/spoke-canary-vps3.yaml` (separate spec — domain must match target):

   ```yaml
   # Identical to spoke-canary.yaml except:
   id: spoke-canary-vps3
   domain: spoke-canary.vps3.ocoron.com
   target_vps: vps3
   ```

   Deploy + run the same staging-then-prod cert flow on vps3.
6. **Destroy** (requires W3 done):

   ```bash
   .venv/bin/fabrik destroy specs/services/spoke-canary.yaml --drop-data --yes
   .venv/bin/fabrik destroy specs/services/spoke-canary-vps3.yaml --drop-data --yes
   ```

7. Post-destroy verify: containers gone, `/opt/spoke-canary/` and `/opt/spoke-canary-vps3/` gone, DNS A records removed, Gatus probes removed, `fabrik vps-sync --verify` exits 0 on every host.
8. Capture the session: `docs/operations/first-spoke-deploy-log-2026-05-3X.md` with timestamps + each verify command's output.

**Acceptance:**

| Check | Expected |
| :--- | :--- |
| Production cert chain shows `Let's Encrypt` (not Fake) | yes |
| `curl https://spoke-canary.vps2.ocoron.com/` returns `200` | yes |
| `ssh vps2 'sudo wc -c /opt/traefik/acme.json'` > 1000 | yes |
| Same on vps3 after second deploy | yes |
| Gatus shows `spoke-canary` + `spoke-canary-vps3` both green within 90 s of deploy | yes |
| Loki returns `{host="vps2", container_name="spoke-canary"}` lines | yes |
| Loki returns `{host="vps3", container_name="spoke-canary-vps3"}` lines | yes |
| Post-destroy: `fabrik vps-sync --verify` returns 0 on all 3 hosts | yes |
| `docs/operations/first-spoke-deploy-log-2026-05-3X.md` exists with timestamps | yes |
| (Staging cert chain row removed per external-AI review B6 — v3.2 dropped staging-first; staging is a step-3 fallback only if first prod issuance fails) | n/a |

**Let's Encrypt accounting.** Current week's prod cert usage on `ocoron.com`: ~12 active (renewals, don't count against new-issuance limit). This plan adds: 2 new prod certs (vps2 + vps3 canary) + their staging precursors. Far below the 50/week limit. Staging has no rate limit.

**Silence Telegram alerts?** Yes for the destroy step (ContainerDown will fire briefly). 5-min silence per spoke.

**Risk.** Medium. First-time LE issuance can fail due to HTTP-01 challenge timing (port 80 must be reachable, DNS must have propagated). Staging-first reduces this risk to near-zero. If prod fails on first try: wait 60 s, restart spoke Traefik, retry once. If still failing, check `acme.json` content for the actual error.

**Estimate.** 90 min (was 60 — added staging step + per-host spec + safety net).

---

### W5 — External-exposure probing

**Status:** SHIPPED 2026-06-01. All 5 acceptance criteria pass; see `docs/infrastructure/vps-status.md` § Verification log entry `2026-06-01T00:43Z (W5)`.

**Problem.** Two host-level exposures are inferred-safe but not externally verified.

**Plan of action.** Run from the dev WSL (exits via Türk Telekom — definitively not on the mesh).

1. **AI sysadmin `:8017` (vps1)**:

   ```bash
   timeout 5 curl -sS -m 5 http://172.93.160.197:8017/health 2>&1 | head -3
   # Expect: "Couldn't connect" / "Connection refused" / timeout
   ```

   **Remediation if externally reachable** — prefer **rebind to 127.0.0.1**:

   ```bash
   # Edit /etc/systemd/system/vps-sysadmin-bot.service to bind 127.0.0.1:8017 not 0.0.0.0:8017
   ssh vps 'sudo grep -E "ExecStart|Listen|HOST" /etc/systemd/system/vps-sysadmin-bot.service'
   # Apply the bind change, then:
   ssh vps 'sudo systemctl daemon-reload && sudo systemctl restart vps-sysadmin-bot.service'
   # Re-probe externally → expect refused.
   ```

   iptables DROP is the fallback if rebind isn't feasible (e.g., service depends on listening on `0.0.0.0` for legitimate reasons).
2. **OpenVPN `:1194/tcp` (vps1)** — keep, document. It's Özgür's personal VPN, intentional. Add a comment to `vps-complete-inventory.md` § vps1 UFW and `vps-urls.md` § Port reference marking it `out-of-platform-scope (operator's personal VPN)`. No probe needed.
3. **Mesh-only ports must be unreachable from public** — pace the probes (3 s timeout, 1 s sleep between hosts) to stay under fail2ban thresholds:

   ```bash
   for h in 172.93.160.197 96.9.214.128 104.128.190.151; do
     echo "--- $h ---"
     for port in 5432 6379 8000 9091 3100 9090 9100 8080 7700; do
       timeout 3 nc -zv "$h" "$port" 2>&1 | head -1
       sleep 0.5
     done
     sleep 1
   done
   # Expect: every line ends "refused" or "timed out". Any "succeeded" → security regression.
   ```

4. **IPv6 mirror coverage** — `ssh vps 'sudo ufw status | grep "v6"'` should mirror every IPv4 rule. Same for vps2/vps3 after W1.
5. Append all probe outputs to `docs/infrastructure/vps-status.md` § Verification log with timestamps.

**Acceptance:**

| Check | Expected |
| :--- | :--- |
| `:8017` external probe | refused/timeout (else: remediated via rebind + re-probed) |
| All mesh-only ports on all 3 hosts unreachable from non-mesh source | yes (0 `succeeded` lines) |
| UFW IPv4/IPv6 rule counts match per host | yes |
| Probe log appended to `vps-status.md` with timestamps | yes |
| Dev WSL's exit IP NOT in fail2ban after probing | yes (`ssh vps 'sudo fail2ban-client status sshd \| grep <YOUR_IP>'` empty) |

**Silence Telegram alerts?** No — read-only probes.

**Risk.** Nil. Pure observation.

**Estimate.** 25 min (was 20 — added pacing + rebind option).

---

### W6 — Probe-audit script + doc truth pass + Lesson 69

> **Lesson slot note:** plan originally reserved Lesson 66; that slot was taken by the validators-must-fail-loud lesson from the crowdlex incident before W6 ran. The W6 rule landed as **Lesson 69 — Presence-probing vs symptom-grep**.

**Problem.** Three doc passes today missed the spoke UFW reality because each used symptom-grep instead of presence-probe. Grep cannot find an absence.

**Plan of action.**

0. **Pre-flight:** `mkdir -p /opt/fabrik/data/` (the report writer fails if the dir doesn't exist).
1. **`scripts/audit_infra_vs_docs.py`** (new). Runs presence-probes against vps1/vps2/vps3 via SSH and emits **both** YAML (machine-readable, committed to `data/`) and Markdown (paste-ready for doc appendix). The probe dict below uses Docker `{{.Names}}` format strings — keep the dict values as plain Python strings (not f-strings) so the curly braces pass through to docker unmodified. Probe set (full set in script):

   ```python
   PROBES = {
       "container_count":     "sudo docker ps --format '{{.Names}}' | wc -l",
       "ufw_installed":       "dpkg -l ufw 2>/dev/null | awk '/^ii/ {print $2}' || true",
       "ufw_active":          "sudo systemctl is-active ufw 2>/dev/null || echo not-installed",
       "fail2ban_active":     "sudo systemctl is-active fail2ban",
       "fail2ban_total_ban":  "sudo fail2ban-client status sshd 2>/dev/null | awk '/Total banned/ {print $NF}'",
       "listening_public":    "sudo ss -tnlp | awk 'NR>1 {print $4}' | grep -E '^(0\\.0\\.0\\.0|\\*):' | sort -u",
       "listening_mesh":      "sudo ss -tnlp | awk 'NR>1 {print $4}' | grep '^10\\.99\\.' | sort -u",
       "docker_user_rules":   "sudo iptables -L DOCKER-USER -n | grep -cE 'DROP|ACCEPT'",
       "iptables_backend":    "sudo update-alternatives --display iptables 2>&1 | grep currently | awk '{print $NF}'",
       "wg_handshake_age":    "sudo wg show wg0 latest-handshakes 2>/dev/null | awk '{print $1, systime()-$2\"s\"}'",
       "kernel":              "uname -r",
       "uptime_s":            "cut -d. -f1 /proc/uptime",
       "disk_root_pct":       "df / | awk 'NR==2 {gsub(\"%\",\"\"); print $5}'",
   }
   HOSTS = ["vps", "vps2", "vps3"]
   # Output:
   # 1. data/infra-probe-YYYY-MM-DDTHHMM.yaml (full data, gitignored or committed)
   # 2. stdout: Markdown table grouped by host (paste into vps-status.md § Verification log)
   ```

2. **Run it now, save the report** in `data/infra-probe-2026-05-3X-XXXX.yaml`.
3. **Update 4 docs once, post-W1** (so they describe the final state with UFW active):
   - `docs/infrastructure/vps-complete-inventory.md` § Firewall → spoke UFW table updated; verification appendix replaces in place
   - `docs/infrastructure/vps-status.md` § Network posture → spoke UFW row updated, "Last probe report" line at top of file
   - `docs/infrastructure/vps-urls.md` § Port reference → spoke UFW column updated
   - `docs/infrastructure/vps-bootstrap-plan.md` → step_02 root-cause finding from W1 documented
4. Each of the 4 docs gets a one-line header near the top:

   ```markdown
   **Last probe report:** [`data/infra-probe-2026-05-3X-XXXX.yaml`](../../data/infra-probe-2026-05-3X-XXXX.yaml)
   ```

5. **Lesson 69** added to `docs/LESSONS_LEARNT.md`:

   > **Lesson 69 — "Verified live" requires presence-probing, not symptom-grep.**
   >
   > **Context (2026-05-31):** Three doc-audit passes claimed UFW was active on vps2/vps3. Each pass grepped for failure symptoms (stale port allows, dead Coolify references). None ran `dpkg -l ufw` or `systemctl is-active ufw`. UFW was completely uninstalled — produces no symptoms to grep for. The docs shipped wrong three times in one day.
   >
   > **Rule:** Before tagging anything "verified live" in `docs/infrastructure/`, run `scripts/audit_infra_vs_docs.py`, commit the resulting `data/infra-probe-*.yaml`, and link it from the doc's header. Symptom-grep can confirm "this stale thing is gone" but cannot confirm "this expected thing is present".
   >
   > **How to apply:** Doc edits to `vps-complete-inventory.md`, `vps-status.md`, `vps-urls.md` should land in the same commit as the probe report. CI lint (advisory): `scripts/audit_infra_vs_docs.py --check` verifies each of those files has a `Last probe report:` line pointing to a real file in `data/`. If absent → warning.

6. **CHANGELOG**:

   ```markdown
   ### Added — Probe-audit script + Lesson 69 (2026-06-01)
   `scripts/audit_infra_vs_docs.py` runs presence-probes against the fleet and emits a YAML + Markdown report. Infrastructure docs now link the latest report at their header.
   ```

**Acceptance:**

| Check | Expected |
| :--- | :--- |
| `scripts/audit_infra_vs_docs.py` exists, executable, runs end-to-end < 10 s | yes |
| `data/infra-probe-2026-05-3X-XXXX.yaml` committed and references all 3 hosts | yes |
| 4 doc edits land in the same commit as the probe report | yes |
| Each of the 4 docs has a `Last probe report:` header line | yes |
| Lesson 69 in `docs/LESSONS_LEARNT.md` | yes |
| CHANGELOG entry under `## [Unreleased]` | yes |
| `scripts/audit_infra_vs_docs.py --check` on the updated docs returns 0 warnings | yes |

**Silence Telegram alerts?** No.

**Risk.** Process change adoption. Mitigated by the simplicity of the `--check` rule (one header line, easy to follow).

**Estimate.** 2 h (script ~45 min, doc updates ~45 min, Lesson + CHANGELOG ~30 min).

---

### ~~W7~~ — DROPPED (VirtFusion snapshot)

**Decision (2026-05-31):** dropped. GreenCloud's published docs ([green.cloud/docs/](https://green.cloud/docs/)) list zero API/automation content for VirtFusion. The [EZSCALE Terraform provider](https://github.com/EZSCALE/terraform-provider-virtfusion) covers VM lifecycle but NOT snapshots — suggesting snapshot ops are admin-only at the VirtFusion installation level GreenCloud runs. Per the operator's "no manual GUI work" rule, a step that requires logging into the provider panel is non-starter.

**Vendor-confirmed (2026-06-01):** Tu Do Anh, Senior Technician at GreenCloud, replied to a direct ticket:

> "Your VPS currently only includes manual backup, which needs to be triggered through the control panel. We do not have an API available for automated or scheduled backups. If you would like to set up scheduled backups, you would need to purchase our backup add-on."

The original drop was inferred from missing docs; this confirms it. The paid add-on still goes through the panel for setup (their phrasing "scheduled backups" reads as provider-managed schedule, not customer-controlled API), so it doesn't satisfy "no manual GUI work" either and isn't worth the spend. W7 stays dropped. The DR strategy that actually works automatically is `bootstrap-hub.sh` (DR-in-hours track, v3.9) + Backrest → B2 + W9 GitHub mirror — no GreenCloud API surface required.

**Rollback for W2 instead:** W2 mutates only (a) `/opt/backrest/config/config.json` (git-backed via `opt-configs` plan once it exists; pre-edit backup taken inline), and (b) restic state in the B2 bucket (which can be `restic forget --keep-last 0 && restic prune` to wipe and start over). No VM-level snapshot needed.

**Catastrophic failure (vps1 disk dies) DR path:** new VM + Backrest cold restore from B2 + creds from W9. Same with or without VirtFusion snapshots.

This frees ~25 min from Day 1 and removes the only GUI step from the plan.

---

### W8 — AI sysadmin smoke test + spoke-anomaly safety probe

**Problem.** The bot wasn't exercised after today's mesh/spoke/registrar changes. `proactive-check.sh` was updated to be spoke-aware (`prom_hosts()` query). But the action handlers don't know how to SSH to vps2/vps3 — if the bot decides to autonomously act on a spoke anomaly, it could fail in unpredictable ways. Need to verify it escalates instead.

**Plan of action.**

1. Service health:

   ```bash
   ssh vps 'sudo systemctl is-active vps-sysadmin-bot.service'
   ssh vps 'sudo journalctl -u vps-sysadmin-bot --since "1 hour ago" --no-pager | tail -30'
   ```

2. Cron registered + parses cleanly:

   ```bash
   ssh vps 'sudo cat /etc/cron.d/vps-sysadmin'
   ```

3. Manual proactive-check:

   ```bash
   ssh vps 'sudo /opt/fabrik/scripts/sysadmin/proactive-check.sh 2>&1 | tail -30'
   # Look for per-host tagging: "cpu_high[vps2]" or "no anomalies"
   ```

4. Local health endpoint (rebind from W5 step 1 means `127.0.0.1:8017` only):

   ```bash
   ssh vps 'curl -sS http://127.0.0.1:8017/health'
   # Expect: HTTP 200 / JSON status.
   ```

5. `spoke_health` rule group loaded:

   ```bash
   ssh vps 'sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/rules"' \
     | python3 -c "import json,sys; d=json.load(sys.stdin); print([g['name'] for g in d['data']['groups']])"
   # Expect: list contains "spoke_health"
   ```

6. **Spoke-anomaly safety probe** — induce a spoke anomaly and verify the bot ESCALATES (Telegram) rather than autonomously ACTS:

   ```bash
   # Trigger temporary high CPU on vps2 (B5 fix: nohup form survives SSH-session teardown):
   ssh vps2 'nohup bash -c "timeout 60 yes > /dev/null" </dev/null >/dev/null 2>&1 &'  # one CPU pegged for 60s
   # Wait for the next proactive-check cron tick (≤ 5 min) OR run manually:
   ssh vps 'sudo /opt/fabrik/scripts/sysadmin/proactive-check.sh'
   # Verify:
   #   - The action log shows "cpu_high[vps2]" detected
   #   - The bot did NOT run "ssh vps2 docker restart <X>" (safer: no autonomous spoke actions until W3+W4 prove it works)
   #   - A Telegram message was sent (or, if Tier B/C policy, an escalation request)
   ssh vps 'sudo tail -20 /opt/fabrik/logs/sysadmin-actions.jsonl'
   ```

7. If step 6 shows the bot trying to autonomously act on a spoke → file an immediate finding in `docs/infrastructure/vps-ai-sysadmin.md` and add a guard:
   - Either: pin `proactive-check.sh` to only emit anomalies for `host=vps1` until spoke-safe actions exist.
   - Or: update action handlers to route to the right host (more work — out of scope for W8).

**Acceptance:**

| Check | Expected |
| :--- | :--- |
| `vps-sysadmin-bot.service` is `active` | yes |
| `proactive-check.sh` exits 0 | yes |
| Per-host anomaly tagging present in output (or "no anomalies") | yes |
| `127.0.0.1:8017/health` returns 200 from inside vps1 | yes |
| `spoke_health` rule group loaded in Prometheus | yes |
| **Induced spoke anomaly → bot escalates, does NOT autonomously act on vps2** | yes |
| Latest shift note `/opt/fabrik/logs/sysadmin-shift-notes.md` written within 24h | yes |
| Any safety finding documented + guarded | yes |

**Silence Telegram alerts?** Yes for step 6 — the Telegram message IS the verification, but additional ContainerDown noise should be muted.

**Risk.** Low. The `yes > /dev/null` stress is bounded (60 s). The bot's worst case is sending an unwanted Telegram message.

**Estimate.** 25 min (was 15 — added the spoke-anomaly safety probe).

---

### W9 — `/opt/fabrik/.env` offsite recovery — FULLY AUTOMATED, NO EXTRA ENCRYPTION

**Problem.** `/opt/fabrik/.env` on the dev WSL holds the only copies of: `BACKREST_RESTIC_PASSWORD` (irrecoverable — encrypts B2 repo at the restic layer), `B2_KEY_ID` + `B2_APPLICATION_KEY`, `CLOUDFLARE_API_TOKEN`, `API_KEY`, all current + future service secrets. It's gitignored from the main `fabrik` repo. If WSL dies AND vps1 dies, the chain breaks: no creds → no B2 restore → no recovery.

**Constraint (operator directive 2026-05-31):** no manual steps. No `age` / passphrase / paper backup layer — the **private GitHub repo IS the security boundary** (same threat-model logic accepted for the main code repo). Single-operator dev environment; no realistic attacker model named.

**WSL transience (operator directive 2026-05-31):** dev WSL is NOT always up. The design accepts this: env can only change when WSL is up (env file lives ON the WSL), so missed cron ticks during WSL downtime are not data loss. Design uses **inotify file-watcher for change-driven push** + **cron daily as a safety net** + AI sysadmin alert (W10) if GitHub commit age exceeds 30 days (env rarely changes; this is a real-staleness signal, not a missed-tick signal).

**Plan of action.**

1. Create the private GitHub DR repo (gh CLI is pre-authenticated as `mobasak` per pre-flight 2026-05-31; full `repo` + `delete_repo` scopes):

   ```bash
   # External-AI review B2 fix: use `gh repo clone` not `git clone git@github.com:...`
   # — pre-flight 2026-05-31 confirmed gh auth protocol = HTTPS (not SSH), so the
   # SSH-form clone would fail if no SSH key is registered on the GitHub account.
   gh repo create mobasak/fabrik-dr-store --private --description "DR mirror: /opt/fabrik/.env"
   gh repo clone mobasak/fabrik-dr-store /opt/fabrik-dr-store
   cd /opt/fabrik-dr-store
   printf '# Fabrik DR Store\n\nPlain mirror of /opt/fabrik/.env (private repo = security boundary).\n\nRecovery: gh repo clone mobasak/fabrik-dr-store && cp fabrik-dr-store/env/latest /opt/fabrik/.env\n' > README.md
   echo "*.tmp" > .gitignore
   git add . && git commit -m "init" && git push -u origin main
   ```

2. Write `scripts/dr_env_backup.sh` (dev WSL) — **B6 fix: only commit when env content actually changed** (uses `cmp -s` not `git diff`, so timestamp-only differences don't create noise commits):

   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   ENV_PATH="${ENV_PATH:-/opt/fabrik/.env}"
   REPO="${REPO:-/opt/fabrik-dr-store}"
   TS=$(date -u +%Y%m%dT%H%M%SZ)

   mkdir -p "$REPO/env"

   # Skip if content hasn't changed since last successful backup (B6 fix).
   if [ -f "$REPO/env/latest" ] && cmp -s "$ENV_PATH" "$REPO/env/latest"; then
     echo "$(date -u +%FT%TZ) no change"
     exit 0
   fi

   cp "$ENV_PATH" "$REPO/env/latest"
   cp "$ENV_PATH" "$REPO/env/fabrik-env-${TS}"

   # Rotate: keep last 60 timestamped snapshots (older still in git history)
   ls -1t "$REPO/env/fabrik-env-"* 2>/dev/null | tail -n +61 | xargs -r rm -f

   cd "$REPO"
   git add env/
   git commit -m "dr-env: ${TS}"
   git push origin main
   echo "$(date -u +%FT%TZ) OK: pushed ${TS}"
   ```

3. **Inotify watcher** — change-driven push (handles WSL-up-but-env-just-changed within seconds):

   ```bash
   # Install inotify-tools if absent:
   command -v inotifywait >/dev/null || sudo apt-get install -y -qq inotify-tools

   # systemd user service: /etc/systemd/system/fabrik-dr-watcher.service
   sudo tee /etc/systemd/system/fabrik-dr-watcher.service >/dev/null <<'EOF'
   [Unit]
   Description=Fabrik DR env watcher (push to GitHub on change)
   After=network-online.target

   [Service]
   User=ozgur
   ExecStart=/bin/bash -c 'inotifywait -m -e close_write /opt/fabrik/.env | while read; do /opt/fabrik/scripts/dr_env_backup.sh; sleep 5; done'
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   EOF
   sudo systemctl daemon-reload
   sudo systemctl enable --now fabrik-dr-watcher.service
   ```

4. **Cron safety-net** — daily 03:30 + 1-minute boot delay (catches any missed push after WSL was down):

   ```bash
   chmod +x /opt/fabrik/scripts/dr_env_backup.sh
   (crontab -l 2>/dev/null; cat <<'EOF'
   30 3 * * * /opt/fabrik/scripts/dr_env_backup.sh >> /var/log/dr-env-backup.log 2>&1
   @reboot sleep 60 && /opt/fabrik/scripts/dr_env_backup.sh >> /var/log/dr-env-backup.log 2>&1
   EOF
   ) | crontab -
   ```

5. **DR self-test** — `scripts/dr_env_recovery_test.sh` (weekly cron):

   ```bash
   #!/usr/bin/env bash
   # External-AI review B1 fix: restic is NOT installed on WSL; route through
   # the Backrest container's /bin/restic via SSH to vps1 (consistent with W2
   # step 4). This proves recovered creds work end-to-end against the live B2
   # repo without depending on a host-side restic install.
   set -euo pipefail
   LATEST="/opt/fabrik-dr-store/env/latest"

   [ -f "$LATEST" ] || { echo "FAIL: no DR snapshot present"; exit 1; }

   RESTIC_PW=$(grep '^BACKREST_RESTIC_PASSWORD=' "$LATEST" | cut -d= -f2-)
   B2_KEY=$(grep '^B2_KEY_ID=' "$LATEST" | cut -d= -f2-)
   B2_SECRET=$(grep '^B2_APPLICATION_KEY=' "$LATEST" | cut -d= -f2-)

   # Verify recovered creds can read the B2 restic repo through Backrest's in-container restic:
   COUNT=$(ssh vps "sudo docker exec \
     -e RESTIC_PASSWORD='${RESTIC_PW}' \
     -e AWS_ACCESS_KEY_ID='${B2_KEY}' \
     -e AWS_SECRET_ACCESS_KEY='${B2_SECRET}' \
     backrest /bin/restic -r s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups snapshots --json 2>/dev/null" \
     | python3 -c "import json,sys; print(len(json.load(sys.stdin)))")

   echo "$(date -u +%FT%TZ) OK: ${COUNT} snapshots readable with recovered creds"
   ```

6. Wire to weekly cron:

   ```bash
   chmod +x /opt/fabrik/scripts/dr_env_recovery_test.sh
   (crontab -l 2>/dev/null; echo "0 4 * * 0 /opt/fabrik/scripts/dr_env_recovery_test.sh >> /var/log/dr-env-recovery-test.log 2>&1") | crontab -
   ```

7. Documentation — `docs/operations/credential-recovery.md` (new):
   - What's in `/opt/fabrik/.env` and which keys are irrecoverable vs reissuable
   - Backup mechanism: nightly cron → `/opt/fabrik-dr-store/env/*` → `git push origin main`
   - Security model: **private GitHub repo IS the boundary**; no extra encryption layer (consistent with the operator's threat model — single-operator dev env, no realistic attacker named)
   - Recovery flow: `gh repo clone mobasak/fabrik-dr-store /opt/fabrik-dr-store && cp /opt/fabrik-dr-store/env/latest /opt/fabrik/.env`
   - Lost-GitHub-access contingency: re-authenticate via `gh auth login`; if the GitHub account itself is lost, all reissuable creds can be reissued and only `BACKREST_RESTIC_PASSWORD` is unrecoverable (B2 backups become unreadable; vps1 disk + live data still intact)
   - Hardening note: never add collaborators or GitHub Actions to `mobasak/fabrik-dr-store`; never make it public; otherwise the security boundary breaks

8. Add to `docs/operations/disaster-recovery.md`:

   > **Prerequisite:** All DR paths require `BACKREST_RESTIC_PASSWORD` recovery — see [`credential-recovery.md`](credential-recovery.md). Recovery is one command: `gh repo clone mobasak/fabrik-dr-store && cp fabrik-dr-store/env/latest /opt/fabrik/.env`.

9. **AI sysadmin watches it** (cross-reference to W10): if `/opt/fabrik-dr-store/env/latest` hasn't been touched in **30 days** (env rarely changes when stable), fire an alert. Inotify-driven push happens within seconds of every change, so 30d is the real-staleness signal.

**Acceptance:**

| Check | Expected |
| :--- | :--- |
| `mobasak/fabrik-dr-store` exists as a private repo | yes |
| `scripts/dr_env_backup.sh` exists, executable | yes |
| First commit (manual run): `env/latest` and `env/fabrik-env-YYYYMMDDTHHMMSSZ` pushed | yes |
| `scripts/dr_env_recovery_test.sh` exists, executable | yes |
| Both cron entries present in `crontab -l` on dev WSL | yes |
| `docs/operations/credential-recovery.md` followable from scratch | yes |
| `docs/operations/disaster-recovery.md` cross-references it | yes |
| **DR self-test:** rename `/opt/fabrik/.env` → restore from cloned DR store → `fabrik apply --dry-run` succeeds | yes |
| Weekly cron logs an "OK: N snapshots readable" line | yes |

**Silence Telegram alerts?** No — local WSL + git operations.

**Risk.** Low. The actual residual risk is "lose GitHub access AND lose vps1 disk simultaneously." Realistic mitigation: GitHub access is the same risk that already applies to the main `fabrik` code repo — accepted.

**Estimate.** 40 min (script + repo + cron + docs; simpler than the age-layered version).

---

### W10 — Extend AI sysadmin to watch the automated chain (NEW per operator directive)

**Problem.** Operator directive (2026-05-31): "everything automated, AI sysadmin watched and fixed." Today's bot (`vps-sysadmin-bot.service` + `proactive-check.sh` + cron) monitors container/CPU/RAM anomalies and has spoke-awareness from this morning's work, but it does NOT yet check: backup health (stale snapshots), cert expiry, mesh degradation, or DR-store staleness. These are silent-failure surfaces — they don't crash anything, they just stop working.

**Plan of action.** Extend `scripts/sysadmin/proactive-check.sh` with 4 new check modules. Each follows the existing Tier A (autonomous fix) / Tier B (ask) / Tier C (escalate) ladder.

1. **Backup health** (`check_backup_health`):
   - Run from inside vps1's Backrest container: `restic snapshots --json --last 1` for each plan.
   - For each plan: if `time > 36h` ago → Tier C alert (`backup_stale[<plan-id>]`).
   - If all 3 plans missing for >7d → Tier C critical alert.
   - Tier A autonomous fix on staleness: run `restic check --read-data-subset=1%` to confirm repo health; if OK, trigger a manual snapshot via Backrest API (`POST /v1/plans/<id>/backup-now`).

2. **Cert expiry** (`check_cert_expiry`):
   - Parse `/opt/traefik/acme.json` on each host; for each cert, compute days-to-expiry.
   - Tier C alert at <14 days; critical at <5 days.
   - Tier A autonomous fix: `docker restart traefik` (forces renewal attempt) — bounded to 1 attempt per host per 24h.

3. **Mesh health** (`check_mesh_health`):
   - On vps1: `wg show wg0 latest-handshakes` for each peer; if age > 5 min → Tier B (was bot already aware?), if > 15 min → Tier C critical (mesh broken).
   - Tier A autonomous fix: `sudo systemctl restart wg-quick@wg0` on vps1 (re-establishes hub); bounded to 1 attempt per 30 min.
   - On spokes (queried over mesh from vps1): `wg show wg0 latest-handshakes | awk` — same logic.

4. **DR store staleness** (`check_dr_store`):
   - From vps1's sysadmin context, this runs against the dev WSL via SSH back-channel — or simpler, the dev WSL exposes a `GET /dr-status` endpoint on `127.0.0.1` over Wireguard reverse tunnel.
   - **Simpler v1 approach:** the dev WSL's `dr_env_backup.sh` writes a heartbeat file to `/opt/fabrik-dr-store/.last-success` on every successful run. A GitHub-Actions cron (15 min cadence on the `fabrik-dr-store` repo) checks the file timestamp and fails if >36h old. The failure surfaces as a GitHub email notification + (optionally) a webhook to apprise.
   - Even simpler (external-AI review B5 fix — anonymous-API on a private repo returns 404, full stop): `proactive-check.sh` polls `https://api.github.com/repos/mobasak/fabrik-dr-store/commits` **with `Authorization: Bearer ${GITHUB_TOKEN}`** (token already in `/opt/fabrik/.env` per pre-flight #11; scope `repo:read` on `mobasak/fabrik-dr-store` only). Alerts if the latest commit is >30 days old (env rarely changes when stable).

5. **Wire all 4 into `proactive-check.sh`:**
   - Append calls after the existing CPU/RAM checks.
   - Each writes its result to `/opt/fabrik/logs/sysadmin-actions.jsonl` for audit.
   - Each respects the existing `kill-switch` env var (`SYSADMIN_AUTONOMOUS=false` halts Tier A actions).

6. **Action handlers** — add to whatever module `proactive-check.sh` imports for actions (likely `scripts/sysadmin/actions.sh` or inline):
   - `action_force_backup <plan-id>` → `curl -X POST http://backrest:9898/v1/plans/<id>/backup-now`
   - `action_restart_traefik <host>` → `ssh <host> 'sudo docker restart traefik'` (gated by per-host cooldown file in `/var/lib/sysadmin/cooldowns/`)
   - `action_restart_wg_hub` → `sudo systemctl restart wg-quick@wg0` (gated by 30-min cooldown **AND** by `SYSADMIN_AUTONOMOUS_WG_RESTART=false` default — B8 fix: opt-in only because restarting wg-quick could disconnect an operator currently SSH'd in over mesh)

7. **Cooldown / state files** — `/var/lib/sysadmin/cooldowns/<action>-<target>` (B7 fix: persistent across reboots; `/var/run/` is tmpfs and would wipe cooldowns, causing action storms post-reboot). Modtime checked before each action; > cooldown threshold → action allowed + file touched. **First-run handling:** if cooldown file doesn't exist, allow + create.

8. **CHANGELOG entry:**

   ```markdown
   ### Added — AI sysadmin watchers: backup, cert, mesh, DR store (W10, 2026-05-31)
   `proactive-check.sh` now monitors backup snapshot age, Let's Encrypt cert expiry,
   Wireguard mesh handshake age, and the DR-store last-commit time. Bounded
   autonomous remediation per Tier A; escalates to Telegram per Tier C.
   ```

**Acceptance:**

| Check | Expected |
| :--- | :--- |
| `proactive-check.sh --check backup_health` returns 0 with current snapshot ages | yes (after W2 init) |
| `proactive-check.sh --check cert_expiry` returns 0 with days-to-expiry per cert | yes |
| `proactive-check.sh --check mesh_health` returns 0 with handshake ages | yes |
| `proactive-check.sh --check dr_store` returns 0 with last-commit age | yes (after W9 init) |
| Simulated failure: `restic forget --keep-last 0` on test data → next proactive-check fires `backup_stale` Tier C | yes |
| Simulated failure: temporarily edit acme.json to show expiry < 10d → next check fires `cert_expiry` Tier C | yes |
| Cooldown file prevents repeated `docker restart traefik` within 24h | yes |
| All actions logged to `sysadmin-actions.jsonl` | yes |
| `SYSADMIN_AUTONOMOUS=false` halts Tier A actions (escalation still fires) | yes |

**Silence Telegram alerts?** No — the alert pipeline IS what we're testing.

**Risk.** Medium-low. False positives (cert-expiry computed wrong) cause Telegram noise, not damage. The cooldown system prevents action loops. The kill-switch (`SYSADMIN_AUTONOMOUS=false`) is a hard stop.

**Estimate.** 90 min (4 check modules + action handlers + cooldown system + tests).

---

## 3. Sequencing (post v3 amendments — W7 dropped, W10 added, W9 simplified)

| Session | Order | Workstream | Why |
| :--- | :--- | :--- | :--- |
| **Day 1 (~40 min)** | 1 | **W9** DR-store automation (private GitHub mirror + cron) | DR keystone; takes <1 h |
| **Day 2 (~4 h)** | 2 | **W1** Spoke UFW + bootstrap fix | Touches spoke state; rollback `ufw disable` |
| | 3 | **W6** Probe-audit script + doc updates + Lesson 69 | Captures W1 outcome with first probe report |
| | 4 | **W5** External-exposure probing | Cheap; results land in same `vps-status.md` updates as W6 |
| | 5 | **W2** Backrest reactivation (config.json edit, no UI) | Biggest DR win; rollback = git revert of config.json |
| **Day 3 (~8 h, was ~5 h before W11)** | 6 | **W8** AI sysadmin smoke + safety probe | Pre-W10 sanity after today's Backrest changes |
| | 7 | **W10** AI sysadmin watchers (backup/cert/mesh/DR) | Closes "automated + watched" goal; bot gains spoke-aware action handlers |
| | 8 | **W11** Spoke DR symmetry (per-spoke Backrest + bootstrap-spoke-restore.sh + W9 ext) | Spokes get DR before tenant data lands (~3 h) |
| | 9 | **W4** First real spoke deploy + destroy (incl. `daemon.json` tag pre-step) | Tenants land; pre-step fixes promtail label gap |
| | 10 | **W3** `--target-vps` for destroy + redeploy | Code-only; symmetric lifecycle after W4 validates the path |
| | 11 | **DR drills** (hub + each spoke against throwaway VPSes) | Real wall-clock measurement; final "is it real" gate |

**Realistic total active time:** ~10.5 h active (sum of workstream estimates: W1 45 + W2 75 + W3 120 + W4 90 + W5 25 + W6 120 + W8 25 + W9 40 + W10 90 = 630 min). Wall-clock with breaks: ~13 h, fits three sessions. Compresses to a single ~7 h focused session if you skip W6 docs and run W2 + W3 + W10 in parallel with `tmux`.

---

## 4. Out-of-scope (with rationale)

| Item | Why deferred |
| :--- | :--- |
| Watchdog plan P2/P3/P4/P5 | Separate plan; P2 needs multi-host scoping decision first |
| Credential rotation | Single-operator threat model — no realistic attacker beyond ourselves |
| CF token scope tightening | Same |
| Authelia rule #6 inclusion of `errors.vps1` | Accepted intentional; revisit needs its own decision |
| Removing OpenVPN `:1194` | Operator's personal VPN; marked out-of-platform-scope in W5 |
| HA observability (Prometheus/Loki on spokes) | Single-point-of-failure on vps1 is a deliberate cost trade-off; separate plan |
| Spoke-side Backrest install | Currently no spoke data warrants it; revisit when first tenant lands |
| `--target-vps` for `fabrik reconcile-all` / `fabrik audit-registrars` | Lower priority; M5 covers the lifecycle-critical commands |

## 4.5. Pre-mortem (most likely failure modes)

| # | Failure mode | Probability | Detection | Response |
| :--- | :--- | :--- | :--- | :--- |
| P1 | Backrest config edit silently fails to register plans (typo, schema mismatch in 1.12.1) | Medium | After step 6 restart, `restic snapshots` is empty after the test backup runs; Backrest logs show parse error | `docker logs backrest` shows the error; fix typo; restart |
| P2 | B2 bucket region/key mismatch (key is account-master but bucket is region-locked) | Low | `restic init` returns auth error | Re-issue an app key scoped to the bucket; update `B2_KEY_ID` + `B2_APPLICATION_KEY` in `.env` and Backrest config |
| P3 | First-time Let's Encrypt issuance fails (HTTP-01 timing / DNS propagation) | Medium | `acme.json` stays 0 bytes after 90 s | Wait 60 s, `docker restart traefik` on the spoke, retry once. If still failing, inspect `acme.json` for the actual error and fall back to staging-INSERT |
| P4 | `fabrik destroy --target-vps vps2` leaves Authelia rules behind on vps1 | Medium-low | `fabrik vps-sync --verify` reports orphan Authelia rule | W3 step 6 research catches this; either fix in same workstream or file follow-up |
| P5 | State file write race between concurrent applies | Low | State file becomes corrupted JSON | W3 step 4 atomic-write fix prevents this; if it happens despite fix, restore from `.fabrik/state/_destroyed/` |
| P6 | dev WSL's IP gets fail2ban'd during W5 probing | Low | `ssh vps` hangs/refuses after the probe loop | Wait 10 min (default fail2ban bantime) OR connect via mobile hotspot to `ssh vps 'sudo fail2ban-client unban <YOUR_IP>'` |
| P7 | Bot autonomously restarts a spoke container during W8 induced anomaly | Low (current action handlers are vps1-only) | Action log shows `ssh vps2 docker restart` line | Add a guard in `proactive-check.sh` to filter anomalies to `host=vps1` for autonomous actions; document as Lesson 68 |
| P8 | W10 cooldown system fires on first invocation (no prior `mtime` to compare against) | Low | First Tier A action skipped silently | First-run handling: if cooldown file doesn't exist, allow + create. Tested in W10 acceptance. |
| P9 | GitHub push from W9 cron fails (network blip, gh auth expired) | Medium | `git push` exits non-zero; cron log shows error | W10 dr-store watcher detects last-commit age > 36h; alerts. Recovery: `gh auth status` + re-auth. |

## 4.6. Cost analysis (real numbers)

- **B2 storage:** $0.005/GB/month. Expected steady-state ~50–100 GB after `docker-volumes` + `postgres-dumps` + `opt-configs` plans are running. Monthly cost: **$0.25–0.50**.
- **B2 egress (download for restore):** $0.01/GB. Full vps1 restore (~50 GB): **~$0.50, one-time**.
- **GitHub private repo (`mobasak/fabrik-dr-store`) for W9 env mirror:** free tier.
- **Let's Encrypt certificates:** free (50 new certs/week per registered domain — far above our 14 active).
- **Cloudflare DNS:** free tier.
- **VirtFusion snapshots:** dropped from plan (W7) — not available via API in GreenCloud's panel; no cost incurred.
- **Engineering time:** ~9 h active.

**Marginal monetary cost of executing this plan: under $5/year.** Time is the only real cost.

---

## 5. Daily execution checklist

A one-line copy-paste set for tracking. Tick as you go.

### Day 1 — DR foundation (~40 min)

- [ ] W9 step 1 — `mobasak/fabrik-dr-store` created as private GitHub repo + cloned to `/opt/fabrik-dr-store`
- [ ] W9 step 2 — `scripts/dr_env_backup.sh` written + executable
- [ ] W9 step 3 — Nightly cron entry added on dev WSL (`30 3 * * *`)
- [ ] W9 step 4 — `scripts/dr_env_recovery_test.sh` written + executable
- [ ] W9 step 5 — Weekly cron entry added on dev WSL (`0 4 * * 0`)
- [ ] W9 step 6 — `docs/operations/credential-recovery.md` written
- [ ] W9 step 7 — `docs/operations/disaster-recovery.md` cross-references it
- [ ] W9 DR self-test — rename `/opt/fabrik/.env` → restore from cloned DR store → `fabrik apply --dry-run` succeeds

### Day 2 — Fleet hardening (~4 h)

- [ ] Telegram silenced for the W2 window (W1 already done as of 2026-05-31 evening — no silence needed retroactively)
- [x] W1 step 3 — iptables backend confirmed consistent on vps2/vps3 (`iptables-nft` on all 3 hosts) — DONE
- [x] W1 step 4 — UFW installed + enabled on vps2, vps3 (8 ALLOW rules each) — DONE
- [x] W1 step 5 — Bootstrap script patched to handle `rc`-state edge case (Lesson 68) — DONE (commit `4e8e9c9`; step_02 now uses `apt install --reinstall` on `rc`-state OR missing binary, then self-verifies `command -v ufw` + `dpkg ii` + `ufw status: active` before returning success)
- [ ] W6 step 1 — `scripts/audit_infra_vs_docs.py` written + executable
- [ ] W6 step 2 — `data/infra-probe-YYYYMMDD-HHMM.yaml` committed
- [ ] W6 step 3-4 — 4 infra docs updated with `Last probe report:` header
- [x] W6 step 5 — Lesson 69 added (originally reserved as Lesson 66; slot taken by crowdlex validators lesson)
- [ ] W5 step 1 — `:8017` externally probed (and rebound if reachable)
- [ ] W5 step 3 — All mesh ports verified unreachable from public
- [ ] W5 step 5 — Probe log appended to `vps-status.md`
- [ ] W2 step 1 — Pre-W2 rollback record: `config.json.pre-w2.bak` + `/opt/fabrik/.env` backup
- [ ] W2 step 3 — Restic password match verified (pre-flight confirmed it already matches — no-op)
- [ ] W2 step 4 — `restic init` against B2 succeeded (via `/bin/restic` inside container)
- [ ] W2 step 6 — 3 Backrest plans created (via `config.json` edit + restart, no UI)
- [ ] W2 step 8 — Failure-hook test fired Telegram alert (`CONDITION_SNAPSHOT_SUCCESS` on Backrest 1.12.1)
- [ ] W2 step 9 — First production `opt-configs` backup snapshot visible in `restic snapshots`
- [ ] W2 step 10 — Gatus probe for Backrest `:9898/healthz` in place
- [ ] W2 step 11 — `docs/operations/disaster-recovery.md` updated (Path B no longer aspirational)
- [ ] W2 step 12 — Lesson 67 added
- [ ] Telegram unsilenced

### Day 3 — Spoke integration (~5 h)

- [ ] W3 — `CoolifyConfig` import error in `test_destroyer.py` fixed (pre-flight blocker)
- [ ] W3 — `--target-vps` Click option on destroy + redeploy
- [ ] W3 — State file `_persist_state` atomic write verified
- [ ] W3 — 6 new tests pass + previously-failing tests now pass
- [ ] W3 — Doc updates landed (`docs/operations/deployment.md`, `vps-urls.md`)
- [ ] W8 — Bot active, cron registered, proactive-check exits 0
- [ ] W8 step 6 — Spoke-anomaly safety probe confirms no autonomous spoke action
- [ ] W8 — Safety finding (if any) documented
- [ ] W10 — `proactive-check.sh` extended with 4 watchers (backup, cert, mesh, dr-store)
- [ ] W10 — Cooldown system written + tested
- [ ] W10 — Simulated failure tests fire Tier C alerts
- [ ] Telegram silenced for the W4 window
- [ ] W4 pre-step — Spoke daemon.json `tag` directive applied on vps2 + vps3
- [ ] W4 step 1 — `spoke-canary.yaml` + `spoke-canary-vps3.yaml` written
- [ ] W4 step 2 — `fabrik apply --target-vps vps2` succeeded; production LE cert issued
- [ ] W4 step 4 — All 7 pipeline verifications pass
- [ ] W4 step 5 — Same flow completed on vps3
- [ ] W4 step 6 — Both spoke-canaries destroyed via `fabrik destroy --target-vps vpsN`
- [ ] W4 step 7 — `fabrik vps-sync --verify` exits 0 on all 3 hosts
- [ ] W4 step 8 — `first-spoke-deploy-log-2026-05-3X.md` written
- [ ] Telegram unsilenced

---

## 6. Whole-plan acceptance

Plan is "done" when every command in every workstream's acceptance table produces its expected output, AND:

```bash
# 1. Probe-vs-doc audit clean:
.venv/bin/python scripts/audit_infra_vs_docs.py --check
# Expect: exit 0, zero warnings.

# 2. No OPEN rows remain for items addressed:
grep -E '^\| (1|9|22|23) \|.*\*\*OPEN\*\*' docs/infrastructure/vps-complete-inventory.md
# Expect: empty.

# 3. Test suite green:
.venv/bin/python -m pytest tests/orchestrator/test_deployer_ssh.py \
                          tests/orchestrator/test_destroyer.py \
                          tests/test_spec_loader.py -q
# Expect: 0 failures.

# 4. DR self-test (combines W9 + W2 — no manual steps):
mv /opt/fabrik/.env /opt/fabrik/.env.tmp
cd /tmp && gh repo clone mobasak/fabrik-dr-store fresh-dr-store
cp /tmp/fresh-dr-store/env/latest /opt/fabrik/.env
RESTIC_PW=$(grep '^BACKREST_RESTIC_PASSWORD=' /opt/fabrik/.env | cut -d= -f2-)
RESTIC_PASSWORD="$RESTIC_PW" \
  AWS_ACCESS_KEY_ID=$(grep '^B2_KEY_ID=' /opt/fabrik/.env | cut -d= -f2-) \
  AWS_SECRET_ACCESS_KEY=$(grep '^B2_APPLICATION_KEY=' /opt/fabrik/.env | cut -d= -f2-) \
  restic -r s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups snapshots
# Expect: at least 1 snapshot (proves recovered creds can read the B2 repo).
rm -rf /tmp/fresh-dr-store
mv /opt/fabrik/.env.tmp /opt/fabrik/.env

# 5. Spoke parity self-test (deploy + verify + destroy on vps2 + vps3):
.venv/bin/fabrik apply specs/services/spoke-canary.yaml --yes
curl -sS -o /dev/null -w "%{http_code}\n" https://spoke-canary.vps2.ocoron.com/  # expect 200
.venv/bin/fabrik destroy specs/services/spoke-canary.yaml --drop-data --yes
```

---

## 7. Post-plan recovery story (the "vps1 dies tomorrow" walkthrough)

After this plan ships, the recovery flow from a total vps1 loss is:

1. New VPS provisioned (CF DNS updated to new IP if different from 172.93.160.197).
2. SSH to new host as root, run the rebuild branch of `bootstrap-vps.sh`.
3. From dev WSL (or a fresh WSL): `gh repo clone mobasak/fabrik-dr-store /opt/fabrik-dr-store && cp /opt/fabrik-dr-store/env/latest /opt/fabrik/.env`.
4. `restic -r s3:... snapshots` lists what we have (uses recovered `BACKREST_RESTIC_PASSWORD` from step 3's `.env`).
5. `restic restore latest --target /` (after preparing the disk).
6. Restart Docker; containers come up; mesh re-handshakes from spoke side.

Approximate downtime: 2–4 hours. Data loss: < 24 h (last successful backup).

Without this plan: data loss = whatever was on the dying disk + everything since the manual pg_dump. No B2 restore is possible because `BACKREST_RESTIC_PASSWORD` lives only on the dying disk.

**Single point of failure remaining:** loss of GitHub access. Mitigated by: (a) `mobasak/fabrik-dr-store` is a private repo, no collaborators, no Actions — same risk surface as the main `fabrik` code repo, which is already accepted; (b) recovery still works as long as you can authenticate with GitHub from anywhere; (c) `restic snapshots` themselves remain decryptable from any environment with the password — GitHub is just the password-delivery mechanism.

---

## 8. CHANGELOG entries this plan produces

Listed for traceability — all land under `## [Unreleased]`:

- `### Added — fabrik destroy/redeploy --target-vps (W-Multi M5) (2026-05-31)` (W3)
- `### Added — Probe-audit script + Lesson 69 (2026-06-01)` (W6)
- `### Added — Backrest reactivation against B2 + Lesson 67 + Gatus probe (2026-05-31)` (W2)
- `### Added — credential-recovery.md (2026-05-31)` (W9)
- `### Added — First spoke deploy validation (W4 / first-spoke-deploy-log-2026-05-3X.md) (2026-05-31)` (W4)
- `### Fixed — UFW reinstalled on vps2 + vps3; bootstrap step_02 hardened (2026-05-31)` (W1)
- `### Fixed — AI sysadmin :8017 rebound to localhost (if W5 found it externally reachable) (2026-05-31)` (W5)

---

## 9. References

- [`docs/infrastructure/vps-complete-inventory.md`](../infrastructure/vps-complete-inventory.md)
- [`docs/infrastructure/vps-status.md`](../infrastructure/vps-status.md)
- [`docs/infrastructure/vps-urls.md`](../infrastructure/vps-urls.md)
- [`docs/infrastructure/vps-bootstrap-plan.md`](../infrastructure/vps-bootstrap-plan.md)
- [`docs/infrastructure/vps-ai-sysadmin.md`](../infrastructure/vps-ai-sysadmin.md)
- [`docs/operations/disaster-recovery.md`](../operations/disaster-recovery.md)
- [`docs/operations/backup-strategy.md`](../operations/backup-strategy.md)
- [`docs/LESSONS_LEARNT.md`](../LESSONS_LEARNT.md)
- [`scripts/bootstrap/bootstrap-vps.sh`](../../scripts/bootstrap/bootstrap-vps.sh) (W1 target)
- [`scripts/sysadmin/proactive-check.sh`](../../scripts/sysadmin/proactive-check.sh) (W8 target)
- [`src/fabrik/orchestrator/deployer_ssh.py`](../../src/fabrik/orchestrator/deployer_ssh.py) (M4 reference, M5 target)
- [`src/fabrik/orchestrator/destroyer.py`](../../src/fabrik/orchestrator/destroyer.py) (W3 target)
- [`src/fabrik/orchestrator/__init__.py`](../../src/fabrik/orchestrator/__init__.py) (`VPS_IPS` map; `_persist_state`)
- [`/opt/fabrik/.env`](../../.env) — DR-critical, gitignored, W9 target

---

## 10. Pre-flight probe log (2026-05-31 evening, before Day 1) — ALL FINDINGS

Probes run against vps1/vps2/vps3 + local code/configs before execution. Every assertion in this plan is grounded in one of these probes.

### First batch (before v3.2)

| # | Probe | Finding | Plan-edit applied |
| :--- | :--- | :--- | :--- |
| 1 | `cat /opt/backrest/config/config.json \| jq '.plans \| length'` | 0 plans, 1 repo (b2-vps1) | confirms W2 starting state |
| 2 | `.venv/bin/python -c "from fabrik.spec_loader import CoolifyConfig"` | ImportError | W3 acceptance now requires fixing test, not excluding |
| 3 | `grep -c acme-v02 /opt/traefik/traefik.yml` on vps2 + vps3 | **0** — no caServer line at all; spokes default to LE prod | W4 staging-first removed; deploy directly to prod with fallback to staging-INSERT if first issuance fails |
| 4 | Compare `BACKREST_RESTIC_PASSWORD` in config.json vs .env | Both 64 chars, first 6 = `229665` — already match | W2 step 3 reconciliation now a no-op verification |
| 5 | `/opt/fabrik/data/` existence | exists | W6 unblocked |
| 6 | `docker exec apprise wget ...` | wget not in apprise (distroless). Probed via `--network fabrik alpine wget` instead — HTTP 200 from `apprise:8000` | W2 failure-hook test path confirmed |
| 7 | `docker exec backrest backrest --help` | `backrest` binary not in PATH; container runs `/backrest` as PID 1 via tini. `/bin/restic` (v0.18.1) IS in PATH. | All W2 `docker exec ... restic` commands updated to `/bin/restic` |
| 8 | Backrest version | 1.12.1 | W2 step 8 happy path |

### Second batch (v3.2 → v3.3, addressing veteran-review blockers)

| # | Probe | Finding | Plan-edit applied |
| :--- | :--- | :--- | :--- |
| 9 | `grep "_persist_state" src/fabrik/orchestrator/__init__.py` | ✅ Found at line 364 (B3 cleared) | W3 step 3 confirms the real function name; patch instructions are correct |
| 10 | `ls /opt/fabrik/templates/` | 16 templates including `python-api`, `node-api`, `file-worker`, `file-api`, `saas-skeleton` (B4 cleared) | W4 `template: python-api` confirmed valid |
| 11 | `gh auth status` + `.env` grep | `mobasak` active with `repo` + `delete_repo` scopes; `GITHUB_TOKEN` + `GITHUB_USERNAME` already in `/opt/fabrik/.env` (Q1 cleared) | W9 step 1 can create `mobasak/fabrik-dr-store` immediately |
| 12 | `docker inspect backrest --format '{{range .Mounts}}...'` | Pre-existing bind mounts: `/opt`→`/backup-opt` (ro), `/var/lib/docker/volumes`→`/backup-volumes` (ro), `/opt/backups`→`/backup-postgres` (rw), `/opt/backrest/.restic-password`→`/restic-password` (ro) | W2 plan paths use container-internal mount points (`/backup-opt/...` not `/opt/...`) |
| 13 | `ls -la /restic-password` inside backrest | 65-byte file, content matches config.json password (`229665...`) | Backrest reads password from this file, not env. Lesson 67 updated. |
| 14 | `cat /opt/backrest/config/config.json` top-level structure | keys: `modno, version, instance, repos, plans, auth, sync`. `plans` is `[]`. | W2 step 6 will edit `plans` array directly |
| 15 | `wget http://backrest:9898/v1/config` | 404 on that path; root returns 200 HTML. Backrest exposes a gRPC/Connect-style API under `/v1.Backrest/*` namespace. | W2 step 8 hook test will use direct config.json edit (UI is the only documented schema source for plans; API path requires inspecting frontend XHR at execution time) |

### Open assertions — ALL RESOLVED (2026-05-31 evening, via GitHub proto fetch)

| # | Was | Resolution |
| :--- | :--- | :--- |
| O1 | Backrest plan JSON schema | ✅ **RESOLVED.** Fetched `proto/v1/config.proto` from `garethgeorge/backrest` GitHub repo. `Plan` message fields: `id`, `repo`, `paths[]`, `excludes[]`, `iexcludes[]`, `schedule` (Schedule), `retention` (RetentionPolicy), `hooks[]` (Hook), `backup_flags[]`, `skip_if_unchanged`. `Schedule` has `cron` (string, e.g. `"0 2 * * *"`) and `clock` (`CLOCK_LOCAL` / `CLOCK_LAST_RUN_TIME` / `CLOCK_UTC`). `RetentionPolicy` is a `oneof`: `policyKeepLastN` (int) / `policyTimeBucketed` (object with `hourly`/`daily`/`weekly`/`monthly`/`yearly`/`keepLastN`) / `policyKeepAll` (bool). |
| O2 | Hook event name | ✅ **RESOLVED.** `CONDITION_SNAPSHOT_SUCCESS = 6` confirmed in the proto enum. Full set: `CONDITION_ANY_ERROR (1)`, `CONDITION_SNAPSHOT_START (2)`, `CONDITION_SNAPSHOT_END (3)`, `CONDITION_SNAPSHOT_ERROR (4)`, `CONDITION_SNAPSHOT_WARNING (5)`, `CONDITION_SNAPSHOT_SUCCESS (6)`, `CONDITION_SNAPSHOT_SKIPPED (7)`, plus prune/check/forget variants. |
| O3 | REST API trigger path | ✅ **RESOLVED.** Backrest exposes Connect-RPC at `POST /v1.Backrest/<Method>`: `Backup(BackupRequest)`, `SetConfig(Config)`, `Forget(ForgetRequest)`, `Cancel(int64)`. Auth via `POST /v1.Authentication/Login` → JWT token → `Authorization: Bearer <token>`. **For W2 we don't need the API** — config.json edit + `docker restart backrest` is sufficient. Keep the API path as a fallback for "trigger backup now" tests if needed. |

### Concrete `Plan` JSON to inject into `config.json::plans[]` (from proto field names)

```json
{
  "id": "opt-configs",
  "repo": "b2-vps1",
  "paths": [
    "/backup-opt"
  ],
  "excludes": [
    "/backup-opt/backups/**",
    "/backup-opt/.archive/**",
    "/backup-opt/containerd/**"
  ],
  "schedule": {
    "cron": "0 3 * * *",
    "clock": "CLOCK_LOCAL"
  },
  "retention": {
    "policyTimeBucketed": {
      "daily": 30
    }
  },
  "hooks": [
    {
      "conditions": ["CONDITION_ANY_ERROR"],
      "onError": "ON_ERROR_IGNORE",
      "actionWebhook": {
        "webhookUrl": "http://apprise:8000/notify/alerts",
        "method": "POST"
      }
    }
  ]
}
```

Three plans (`postgres-dumps`, `docker-volumes`, `opt-configs`) follow the same shape with different paths/excludes/retention. Detailed field-by-field schema captured 2026-05-31 evening from `proto/v1/config.proto` at the `v1.12.1` tag.

Net plan corrections from this round: W3 reference confirmed, W4 template confirmed, W9 GitHub creds confirmed, W2 paths corrected to use container-internal mount points + password-file mechanism documented. Three open assertions remain; each has an explicit fallback path so execution doesn't stall.
