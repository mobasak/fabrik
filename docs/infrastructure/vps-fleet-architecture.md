# VPS Fleet — Architecture & Single-System Wiring

**Last Updated:** 2026-06-15 — live values re-verified (mesh RTT, Prometheus jobs/targets, Gatus endpoints, container counts, drill kinds). Prior baseline 2026-06-07 (Trio Phase 1+2+3+4 LIVE across the FULL FLEET since 2026-06-06; **Phase 5.1.a operator-reversal cron LIVE on full fleet 2026-06-07** via `detect_reversals.py` + `*/5 min` cron; **rate-limited 429 wakes now tracked**; **stale netdata scrape job removed**; **6 bootstrap defenses shipped** including preflight SSH-user-transition trap; **DR drill MEASURED end-to-end** 2026-06-07 — `bootstrap-vps.sh --skip-mesh --skip-dns` → 3m 13s wall-clock, 9.3× under target, 15/15 substantive checks.)
**Last probe report:** [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml)
**Purpose:** Single architectural picture of the 3-host fleet — what runs where, how they're wired together, what role each plays. Read this when onboarding new infra work, before designing anything that touches multiple hosts.

This doc answers: "we own 3 VPSes — what do we have, what's planned, and how is it one system?"

## Roles in one line

| Host | Public IP | Mesh IP | Role | Containers |
|---|---|---|---|---|
| **vps1** | 172.93.160.197 (LA) | 10.99.0.1 | **Hub** — mesh root + shared data plane + observability HQ + **two-layer AI ops** (host sysadmin + per-project watchdog) + backup destination for self + admin ingress | 31 (29 platform + 2 T-P5 dogfood) |
| **vps2** | 96.9.214.128 (Coventry UK) | 10.99.0.2 | **Spoke** — tenant compute + local Traefik + monitoring agents shipping to vps1 + own backup destination. **Own AI agent LIVE since 2026-06-06**: aro-wake.service + vps-sysadmin-bot.service (`@SysAdminVPS2` Telegram bot) + proactive-check + detect_reversals (Phase 5.1.a). | 5 |
| **vps3** | 104.128.190.151 (Coventry UK) | 10.99.0.3 | **Spoke** — same shape as vps2. **Own AI agent LIVE since 2026-06-06**: aro-wake.service + vps-sysadmin-bot.service (`@SysAdminVPS3` Telegram bot) + proactive-check + detect_reversals (Phase 5.1.a). | 5 |

**All 3 are fleet members:** W1 firewall posture, W11 backup chain (SHIPPED), W6 probe-audited posture, observability flow via mesh.

**Fleet size is settled at 3 (vps1+vps2+vps3).** No 4th permanent spoke is planned; the provisioning capability below is kept ready, not actively growing the fleet.

**On-demand fleet growth + DR drilling via `fabrik vultr`** (shipped + live-validated 2026-06-08): a 4th+ spoke is `fabrik vultr provision vps4 --region <r>` (deterministic mesh IP `10.99.0.N`, full `bootstrap-vps.sh`, `mode=permanent`; interactive confirm). Throwaway DR drills are `fabrik vultr drill {bare|spoke|hub|spoke-restore}` (auto-destroy, cost-capped; `drill spoke --g0-smoke` opt-in copies hub Claude creds to the throwaway to check immediate copied-creds auth; `drill spoke-restore` exercises the restic-restore-with-identity-preservation path via `bootstrap-spoke-restore.sh`). Covers every Vultr product line (Cloud Compute / High-Frequency / GPU / Bare Metal). Driver `src/fabrik/drivers/vultr.py`; state `data/vultr-instances.json` (gitignored); auth in `/opt/fabrik/.env.sysadmin`.

**PR3 (2026-06-13) — `provision` auto-installs the spoke's AI sysadmin**, collapsing the post-bootstrap manual finish from 5 steps to 1: it claims a per-host Telegram bot token from the DR-store pool (`/opt/fabrik-dr-store/env/sysadmin-bot-tokens.json`), writes `.env.sysadmin` (token + fleet-uniform owner/OpenRouter), enables `aro-wake.service` + `vps-sysadmin-bot.service`, and verifies aro-wake health + token validity. The peer map is fleet-derived so the new host renders real peers (not `unknown`). The **one** remaining manual step is the proven-safe `ssh <spoke> 'claude'` device-flow (copied-creds zero-touch is deferred on the OAuth refresh-token race). Empty token pool ⇒ bot cleanly skipped (never crash-loops). **Reviewed GREEN (5-axis) + merged `0dc92e3`; live-validated by `drill spoke` 2026-06-13/14** (bootstrap_rc=0, verify_rc=0, 0 orphans). The `--g0-smoke` run confirmed copying the hub's Claude creds to a fresh host authenticates *immediately* (no single-session rejection) — so the deferred zero-touch enhancement is viable, gated only on the ~4-day refresh race. Full reference: the plan [`docs/archive/2026-06-07-fabrik-vultr-provisioning.md`](../archive/2026-06-07-fabrik-vultr-provisioning.md) + PR3 plan [`docs/development/plans/archived/2026-06-13-pr3-spoke-sysadmin-autoprovision.md`](../development/plans/archived/2026-06-13-pr3-spoke-sysadmin-autoprovision.md).

---

## vps1 — hub services + mechanisms

### Application services (31 containers — 29 platform + 2 T-P5 dogfood)

| Layer | Services |
|---|---|
| Front door + auth | `traefik` (HTTPS, Let's Encrypt, all `*.vps1.ocoron.com`); `authelia` (forward-auth, TOTP, Redis-backed); `ocoron-com` tenant (WordPress) |
| Shared data plane (mesh-only) | `postgres-main` (`10.99.0.1:5432`), `redis-main` (`:6379`), `meilisearch` (`:7700`), `glitchtip-web` (`:8000` — Sentry DSN), `pushgateway` (`:9091`), `loki` (`:3100`) |
| Observability | `prometheus`, `grafana`, `loki`, `alertmanager`, `cadvisor`, `node-exporter`, `promtail`, `gatus` |
| Backups | `backrest` — 4 plans → B2 (see § Backups below) |
| Notification | `apprise` — Telegram routing for `alertmanager` |
| Workflow / utility | `n8n`, `glitchtip-worker`, `browserless`, `gotenberg` |
| Provisioning | `site-provisioner` — Cloudflare + Namecheap API gateway |
| **Per-project watchdog dogfood** | `watchdog-test` (nginx:alpine target) + `watchdog-test-watchdog` (Claude-driven sidecar). T-P5 dogfood live since 2026-06-03; self-heal verified end-to-end 2026-06-04. Sidecar pattern: 60s poll → rule detect → Claude Opus diagnose → Tier A `restart_container`. |

### Host-level mechanisms

| Mechanism | Where |
|---|---|
| AI sysadmin bot | `vps-sysadmin-bot.service` (systemd, NOT a container) — Telegram bot, spawns Claude Code per message. Pattern: `--model opus --permission-mode bypassPermissions --session-id <uuid> --system-prompt ...`. This is the production reference pattern that the watchdog sidecar's `llm_client.py` was rewritten to mirror in T-P5 (2026-06-04). |
| Proactive checks | `proactive-check.sh` cron — 15-min intervals, spoke-aware (W-Multi M2). Queries Prometheus across all 3 hosts; **acts via local `sudo docker` only** (no SSH-out to spokes) so vps2/vps3 issues this finds get reported but not auto-fixed. |
| Per-project watchdog driver | Deployed via `fabrik apply` for any spec with `watchdog.enabled: true` (default True). Driver at [`src/fabrik/drivers/watchdog.py`](../../src/fabrik/drivers/watchdog.py); detects host docker.sock GID, mounts `~/.claude` + `~/.claude.json` from `FABRIK_VPS_CLAUDE_HOME`, builds per-project image from `/opt/fabrik-lib/watchdog/sidecar/`, writes `compose.watchdog.yaml` overlay. |
| Mesh hub | `wg-quick@wg0` (Wireguard hub at `10.99.0.1`, UDP 51820) |
| iptables boot units | `iptables-docker-user.service` (DOCKER-USER ACCEPT-from-wg0 + DROP mesh-only-from-public); `iptables-openvpn.service` (operator's personal VPN forwards) |
| Firewall | UFW 16 numbered rules (verified 2026-06-07): 5 v4 ALLOW (22, 80, 443, 1194, 51820) + 1 v4 DENY (8000, stale-comment Coolify-era) + 2 v4 ALLOW aro-wake on 8201 (`from 10.0.0.0/8` + `from 10.99.0.0/24`, added 2026-06-05) + 1 v4 routed-ALLOW `wg0→wg0` (spoke↔spoke routing, added 2026-06-06) + 6 v6 mirrors + 1 v6 routed-ALLOW; fail2ban active (150 historical bans as of 2026-06-07T20:20Z probe — internet-facing target, counts drift continuously) |
| Cron | `pre-backup.sh` 01:30 nightly (pg_dumpall + crontab dump); `/etc/cron.d/vps-sysadmin` (proactive checks); 4 Backrest plan schedules |
| Custom binaries | `/usr/local/bin/zellij` (operator-installed) |

### DR

- **Script:** `scripts/bootstrap/bootstrap-hub.sh` (idempotent steps `step_00`–`step_18` plus `step_12b`/`12c` sub-steps; run `grep -oE 'step_[0-9]+[a-z]?' scripts/bootstrap/bootstrap-hub.sh | sort -uV` for the current list, `wc -l` for length). ✅ Shipped 2026-06-01.
- **Target wall-clock:** ≤ 90 min. **Hub DR validated GREEN 2026-06-15/16** via `fabrik vultr drill hub` (first green `dr-drill-hub-20260615-111639`; LE/DNS cutover proven against the `tojlo.com` sandbox zone — `step_17`/`17b`/`17c`). The restore-heavy path measured 5m46s on a `vc2-4c-8gb`; the ≤ 90 min budget covers the compose-up + cert-issuance phases.
- **Operator doc:** [`vps-hub-rebuild.md`](vps-hub-rebuild.md).
- **Inventory:** [`../operations/hub-restore-inventory.md`](../operations/hub-restore-inventory.md).

---

## vps2 + vps3 — spoke services + mechanisms

### Today (5 containers each — post-W11)

| Layer | Service |
|---|---|
| Monitoring agents | `node-exporter`, `cadvisor`, `promtail` (compose `/opt/monitoring-agent/`) — ship data to vps1 over mesh |
| Spoke ingress | `traefik` (`/opt/traefik/`) — Let's Encrypt-ready, untested in production (W4 will exercise) |
| Backups | `backrest` (compose `/opt/backrest/`, 256m RAM, no Traefik labels, no public UI exposure) — writes to own restic repo at `vps1-ocoron-backups/spokes/vpsN/` — added by W11 (2026-06-01) |

### Host-level state

| Mechanism | Where |
|---|---|
| Wireguard spoke | `wg-quick@wg0` (10.99.0.{2,3}, peer of vps1 hub) — own spoke privkey from `bootstrap-vps.sh` step_05 |
| iptables | DOCKER-USER chain persisted via `iptables-docker-user.service` — installed by `bootstrap-vps.sh` step_10 (G5; dropped `iptables-persistent` which `Conflicts: ufw` on Ubuntu 24.04) and regenerated by `bootstrap-spoke-restore.sh` step_07 (G5b); no OpenVPN. UFW remains the canonical spoke firewall. |
| Firewall | UFW 5 v4 + 4 v6 rules: public-port allows (22, 80, 443, 51820) + **mesh-allow `from 10.99.0.0/24`** (added by W8 2026-06-01, also pushed into `bootstrap-vps.sh` step_02 so future spokes get it on first bootstrap). Single-operator threat model: mesh is fully trusted. fail2ban active per host. |
| sysctl tuning | `99-cloudimg-ipv6.conf` (cloud-init) + `99-sysctl.conf` (OS default) |
| Sudoers | `/etc/sudoers.d/90-ozgur` (NOPASSWD line — `90-` prefix from `bootstrap-vps.sh` step_00; differs from hub's `/etc/sudoers.d/ozgur`) |
| SSH state | `authorized_keys` for root + ozgur (no outbound keys — spokes don't SSH outward) |

### Planned (workstream → ship state)

| What | Workstream | Status |
|---|---|---|
| Per-spoke Backrest stack (own restic repo at `vps1-ocoron-backups/spokes/vpsN/`) | W11.3+W11.4 | ✅ **SHIPPED 2026-06-01** |
| `restic init` for each spoke + first backups (2 plans each: host-state + opt-configs) | W11.5 | ✅ **SHIPPED** — 6 successful snapshots per spoke as of 2026-06-02 probe (host-state ×4, opt-configs ×2), via Backrest cron + manual re-triggers from W4-pre/W8 |
| W9 mirror extension for spoke `.env.backrest` + restic password | W11.6 | ✅ **SHIPPED** — 4 new files in DR-store |
| `scripts/bootstrap/bootstrap-spoke-restore.sh` — full spoke DR rebuild | W11.7 | ✅ **SHIPPED** — steps `step_00`–`step_12` (+ `09b`/`09c`/`12b` sub-steps); run `wc -l` / `grep -oE 'step_[0-9]+[a-z]?'` for current counts |
| `docs/infrastructure/vps-spoke-rebuild.md` — spoke DR operator runbook | W11.8 | ✅ **SHIPPED** |
| First real tenant on a spoke | W4 | pending (operator-gated; no tenant to deploy yet) |
| Add `docker-volumes` + `postgres-dumps` plans once tenants land with state | future | gated on W4 |
| AI sysadmin watchers for backup freshness + mesh handshake age + cert expiry + DR-store staleness | W10 | ✅ **SHIPPED 2026-06-01** |
| `fabrik destroy --target-vps` + `fabrik redeploy --target-vps` symmetry | W3 | ✅ **SHIPPED 2026-06-02** |
| Spoke `daemon.json` gains `tag: "{{.Name}}"` so promtail container_name labels work | W4 pre-step | ✅ **SHIPPED 2026-06-02** |
| Orchestrator `coolify` → `fabrik` network rename in code (was hardcoded in `_generate_docker_compose`) | W12 | ✅ **SHIPPED 2026-06-02** |
| Orchestrator healthcheck reads spec.health.path + uses wget (not hardcoded curl/health) | W12.b | ✅ **SHIPPED 2026-06-02** |
| Authelia registrar handles spoke subdomain rules | W13 | ✅ **VERIFIED 2026-06-02** (no code change needed; FQDN-pattern-agnostic) |
| `SSHDeployer.inject_env()` + compose-rollback honor `ctx.target_vps` (env-swap context manager `_target_vps_env`) | W14 | ✅ **SHIPPED 2026-06-02** — spoke deploy lands + rolls back on the correct host; hub-side registrars (gatus/postgres/authelia) stay on vps1 |
| Spoke Traefik defines the `gzip` middleware so orchestrator-emitted `gzip@docker` labels resolve | W15 | ✅ **SHIPPED 2026-06-02** — added `traefik.enable=true` + `traefik.http.middlewares.gzip.compress=true` to Traefik's own `labels:` block in `/opt/traefik/compose.yaml` on both spokes (needed both — spoke `traefik.yml` has `exposedByDefault: false`). First end-to-end spoke deploy verified live: `https://canary.vps2.ocoron.com` returned HTTP 200 with a Let's Encrypt cert (first LE issuance on a spoke ever). Fresh host-state Backrest snapshot 4 → 5 on each spoke so the change is in B2 DR scope. |
| Bake spoke Traefik compose (including the W15 `labels:` block) into `bootstrap-vps.sh` so future spokes get the middleware on first bootstrap | W16 | ✅ **SHIPPED 2026-06-02** — `step_12_install_spoke_traefik()` + 3 templates under `scripts/bootstrap/templates/traefik*.template`; `FABRIK_LE_EMAIL` constant; existing DNS step renumbered 13; `--verify` mode gained a Traefik row. Live idempotency verified on vps2 (re-run = no-op). |

### DR (shipped)

- **Script:** [`scripts/bootstrap/bootstrap-spoke-restore.sh`](../../scripts/bootstrap/bootstrap-spoke-restore.sh) — steps `step_00`–`step_12` (+ `09b`/`09c`/`12b`; run `wc -l` / `grep -oE 'step_[0-9]+[a-z]?'` for current counts), target wall-clock ≤ 30 min. Forward-install path (`bootstrap-vps.sh`) drilled clean 2026-06-07 (3m 13s); restic-restore-with-identity-preservation path validated 2026-06-15 via `fabrik vultr drill spoke-restore`.
- **Operator doc:** [`vps-spoke-rebuild.md`](vps-spoke-rebuild.md).
- **Inventory:** [`../operations/spoke-restore-inventory.md`](../operations/spoke-restore-inventory.md).

---

## How the fleet is one system

### 1. Wireguard mesh — the substrate

- Subnet `10.99.0.0/24`, UDP 51820, hub-and-spoke topology (spokes do NOT talk directly to each other, all through hub).
- vps1 = hub at `10.99.0.1`. Spokes at `10.99.0.2` (vps2), `10.99.0.3` (vps3). Spokes get sequential IPs.
- MTU 1420 with fallbacks to 1380 / 1300 (PMTU probed by `bootstrap-vps.sh` step_09).
- 25 s keepalive on spoke side.
- All cross-host services use mesh IPs. Nothing internal binds to public.
- Cross-Atlantic mesh RTT: ~135–136 ms with 0% loss (vps2 ~135.6 ms, vps3 ~136.6 ms; re-verified live 2026-06-15).

### 2. Observability — single pane on vps1

- `prometheus` on vps1 has 12 active jobs / 14 targets / 14 up (13 jobs configured in `prometheus.yml` — `fabrik-services` has no targets yet; re-verified live 2026-06-15). Spoke node/container metrics: ~~`node-spokes` / `cadvisor-spokes` / `promtail-spokes` jobs~~ — **NOT in `prometheus.yml` today** (spoke-side `node-exporter`/`cadvisor`/`promtail` agents ARE running at `/opt/monitoring-agent/` and the mesh is permissive; the scrape jobs were briefly live on 2026-05-31 but were dropped at some point). Spoke coverage currently flows via the `aro-wake` job (3 mesh targets: vps1:10.0.1.1:8201, vps2:10.99.0.2:8201, vps3:10.99.0.3:8201) exposing SLI counters; full node/container metrics from spokes are NOT in vps1 Prometheus today.
- vps1-local series carry `host=vps1` label. ~~Spoke alert rules `spoke_health` group~~ — **NOT in alerts.yml**. The 5 live rule groups: `aro_wake` (2), `container_health` (6), `host_health` (3), `service_health` (1), `fabrik-registrar-drift` (1, separate file). `host_health` matches on `host` label — for spokes the only series with that label are the `aro-wake` job's, so spoke-side host-level alerting is currently aro-wake-flavored only.
- `loki` receives logs from promtail on every host (promtail pushes to `10.99.0.1:3100` from spokes).
- `grafana` (vps1) shows fleet-wide dashboards. Both Prometheus + Loki as datasources.
- `alertmanager` routes via `apprise` → Telegram.
- `gatus` probes 31 endpoints (across 18 config files) via mesh (re-verified live 2026-06-17; was 33 before the `coolify`/`coolify-public` endpoints were removed).
- Total: **14/14 scrape targets up across 12 active jobs** (re-verified live 2026-06-15 via `/api/v1/targets`); 13 jobs are configured in `prometheus.yml` (the `fabrik-services` job has null targets so it isn't counted active). 12 active jobs = 11 vps1-local + `aro-wake` job (3 targets: vps1, vps2, vps3 over mesh). Was 18/15 briefly on 2026-05-31 when 3 spoke-side jobs were added; those jobs are no longer in `prometheus.yml`.

### 3. Backups (as of 2026-06-01, W11 shipped)

- Each host runs its own Backrest. Each writes to its own restic repo in the same B2 bucket:
  - vps1: `s3:.../vps1-ocoron-backups/` (root, existing)
  - vps2: `s3:.../vps1-ocoron-backups/spokes/vps2/` (new W11)
  - vps3: `s3:.../vps1-ocoron-backups/spokes/vps3/` (new W11)
- **Independent restic passwords per host** — compromise of one doesn't expose the others.
- **No cross-host dependency at backup time** — spoke backups continue even if vps1 is down.
- All 3 restic passwords + B2 keys mirrored via W9 to private GitHub `mobasak/fabrik-dr-store`.

### 4. DNS — Cloudflare, single zone

- Zone `ocoron.com` (Cloudflare zone ID `b3494f947c71683f94b6afe1331a1ba6`).
- vps1: `*.vps1.ocoron.com` + apex + `www`. 12 records, all → 172.93.160.197.
- vps2: wildcard A `*.vps2.ocoron.com` → 96.9.214.128.
- vps3: wildcard A `*.vps3.ocoron.com` → 104.128.190.151.
- `site-provisioner` on vps1 owns the CF API; `bootstrap-vps.sh` (spoke setup) and `fabrik apply --target-vps` call it.
- On hub DR with new IP, `bootstrap-hub.sh --cf-rewrite-dns <new-ip>` retags all `*.vps1.ocoron.com` records via API.

### 5. Deployment pipeline

- `fabrik apply --target-vps vps2 specs/services/foo.yaml` env-swaps `FABRIK_VPS_SSH_HOST=vps2` via the `_target_vps_env(ctx)` contextmanager around three windows: `SSHDeployer.deploy()` (W-Multi M4 shipped 2026-05-31), `SSHDeployer.inject_env()` (W14 shipped 2026-06-02 — DSN/URL writes on spoke apps land on the spoke), and compose rollback (W14 — `_rollback_compose` reads `target_vps` from the resource record). Hub-side registrars (postgres, redis, gatus, glitchtip, authelia, grafana, meilisearch) run **outside** the swap windows and stay on vps1.
- `--target-vps` for `destroy` + `redeploy` parity **shipped 2026-06-02 (W3)** — resolution order CLI flag > state-file > spec field > vps1.
- Per-spoke Let's Encrypt happens on first tenant deploy. First attempt 2026-06-02 (`spoke-canary` on vps2) deployed healthy but failed the verifier 404 because vps2's Traefik lacks the `gzip` middleware definition (W15 — see Planned table). Rollback was clean.
- Tenant containers on a spoke connect to shared infrastructure (Postgres, Redis, etc.) via mesh IP `10.99.0.1:<port>`, not public.

### 6. AI sysadmin oversight (three layers — all Phases 1+2+3+4 LIVE on the FULL FLEET as of 2026-06-06)

- **Layer 1 — Host-level AI sysadmin (LIVE on all 3 hosts — vps1 since 2026-05-20, vps2 + vps3 since 2026-06-06):**
  - `vps-sysadmin-bot.service` on each host — Telegram bot, spawns Claude Code on demand. Pattern: `--model opus --permission-mode bypassPermissions --session-id <uuid> --system-prompt <prompt>`. Each spoke has its own @BotFather bot (`SysAdminVPS2`, `SysAdminVPS3`) and tags every Telegram reply with `[vpsN]` prefix.
  - `proactive-check.sh` cron every 15 min — runs LOCALLY on each host with its own host's authority. Each host's cron acts locally on its own host (no cross-host SSH needed). Hash-stable cron staggering means vps1/vps2/vps3 fire at different minutes to avoid sync-storms.
  - 13 Prometheus alert rules — hub + spoke variants.
  - W10 shipped 2026-06-01: 4 watcher modules (backup health, cert expiry, mesh handshake age, DR-store staleness) — each with Tier A autonomous fix where safe.
  - Trio Phase 2 (2026-06-04) adds: OAuth keepalive cron (hourly, hash-stable minute per host — closes Lesson 75); aro-wake health check (mech #7); Backrest webhook hostname fix (Known Issue 1) baked into `bootstrap-vps.sh step_14`.
- **Layer 2 — Per-project watchdog sidecars (live on vps1; default-on for new specs):**
  - One sidecar container per opted-in project (`watchdog.enabled: true` in spec, default True via `WatchdogConfig`).
  - Today: 1 live (`watchdog-test-watchdog` on vps1).
  - 60s poll → rule detect → Claude Opus diagnose → Tier A action allow-list (`restart_container`, `clear_redis_cache`, `rotate_logs`) → state.db + cost_ledger.
  - Deadman bleed-stop: if Tier C escalation stays unacked for `deadman_timeout_seconds`, sidecar fires `docker restart <main>` as last resort.
  - **Trio Phase 1.3 (2026-06-04):** `llm_client.py` reverted to load the canonical veteran-sysadmin prompt from file at sidecar start + appends a watchdog-specific dispatch contract. Veteran reasoning preserved (yesterday's narrow `_WATCHDOG_SYS_PROMPT` produced no `reasoning` field; today's verifies with full 2-3 sentence audit-trail reasoning).
- **Layer 3 — aro-wake push-trigger endpoint (trio Phase 3 LIVE on the FULL FLEET since 2026-06-06; Phase 4 wire LIVE on vps1):**
  - FastAPI service on every host (vps1, vps2, vps3). Single `POST /wake` endpoint accepts three sources: `consult` (peer-protocol synchronous), `alertmanager` (Alertmanager webhook, async 202+background pattern), `manual` (operator curl). Also exposes `GET /health` + `GET /metrics`.
  - Binds `0.0.0.0:8201` (changed 2026-06-05 batch-6 from mesh-only because Alertmanager's docker container can't reach the host's wg0 IP from its network namespace). Public-internet protection: UFW default-deny + explicit allow-list (22/80/443/1194/51820 only — 8201 not exposed publicly) + two explicit allows: `from 10.0.0.0/8` (docker bridge for Alertmanager) and `from 10.99.0.0/24` (wg0 peer consults).
  - Calling convention: `--model opus --permission-mode bypassPermissions --session-id <uuid> --resume` (mirrors `bot.py::_run_claude` verbatim — the same production pattern proven on vps1 since 2026-05-29).
  - Thread-safe rate limiter (20/h per (source, topic)), per-(source,topic) Claude session reuse for warm cache, disk-backed pending queue (24h TTL, 1000-entry cap) for failed cross-host forwards with mesh-recovery drain.
  - **4 in-memory loop-prevention guards (2026-06-06):** (1) trace-id dedup 5-min LRU drops same-trace replays; (2) hop cap drops `len(seen_by) > fleet_size`; (3) forward-target intersection refuses to send to a host already in `seen_by` (the PRIMARY guard); (4) per-target storm breaker trips at 8 forwards / 10 min, logs ERROR + alerts on first trip. All state in-memory — restart = reset = safe default.
  - Peer protocol: `consult` is live; `propose`/`ack` deferred to Phase 5 (cross-host destructive actions bridge via operator Telegram `reply "go"` until then).
- **Three-veteran-sysadmin model — what's true after Phases 1+2+3 deploy:**
  - Each host owns its docker.sock + journald + local exporters + has full sysadmin authority over what runs on its host.
  - Knows the other two are addressable at `http://10.99.0.<peer>:8201/wake` over the wg0 mesh.
  - Uses peers as senior colleagues via `consult` ("what do you see from your side?") — diagnosis-only; consult responses NEVER authorize action on the recipient side.
  - Authorship rule: the host whose resource is affected AUTHORS the action; peers diagnose.
  - Partition tolerance: when a peer is unreachable, local AI keeps healing local issues and explicitly annotates "(peer X unreachable; acting on local view only)" in its Telegram report — no silent decisions.
- **Phase 4 SHIPPED 2026-06-05**: Alertmanager → aro-wake webhook wire applied on vps1. `aro-wake-routed` receiver added in `/opt/monitoring/configs/alertmanager/alertmanager.yml`; route entry matches `severity=~"critical|warning"` and has `continue: true` so the existing telegram fallback stays intact. Verified by amtool synthetic + REAL `ContainerHighMemory` alert both reaching aro-wake within seconds.
- **Spoke deploy SHIPPED 2026-06-06**: Phase 2 (sysadmin pack) + Phase 3 (aro-wake) deployed on vps2 + vps3 after operator delivered @BotFather tokens + ran `claude auth login` on each spoke. Cross-host consult verified end-to-end: vps2→vps1 and vps3→vps1 both returned rich diagnostic responses; vps3's queued forward from the prior day's outage auto-drained at the first drain tick after vps3's aro-wake came up.
- **Spoke↔spoke wg0 routing SHIPPED 2026-06-06**: Single `ufw route allow in on wg0 out on wg0` on vps1 lit up direct vps2↔vps3 peer reach at ~266ms via hub-hop (vps1 already had `net.ipv4.ip_forward=1`, spokes already had `AllowedIPs=10.99.0.0/24` so the kernel + spoke configs were ready — only the UFW routed-policy gate needed opening). UFW's default-DROP routed policy remains, so vps1 cannot be used as a public-internet egress relay for spokes (verified: `curl --interface wg0 https://1.1.1.1` from vps2 fails fast with exit 7).
- **Prometheus SLI metrics SHIPPED 2026-06-06**: aro-wake exposes 8 metrics at `/metrics` on every fleet host (counters: `aro_wake_requests_total{source,status}`, `aro_wake_cost_usd_total{source}`, `aro_wake_dedup_drops_total`, `aro_wake_hop_limit_exceeded_total`, `aro_wake_forward_suppressed_total{target_host,reason}`, `aro_wake_storm_breaker_trips_total{target_host}`; gauges: `aro_wake_pending_queue_size`, `aro_wake_active_sessions`). Prometheus scrape job `aro-wake` in `configs/prometheus/prometheus.yml` covers all 3 hosts: vps1 via docker-bridge gateway `10.0.1.1:8201` (1.4ms scrape), vps2/vps3 via wg0 mesh `10.99.0.{2,3}:8201` (~270ms scrape). Cross-mesh container→host NAT path verified via tcpdump: docker MASQUERADE on vps1 rewrites Prometheus container's source to vps1's wg0 IP `10.99.0.1`, which the spokes' `from 10.99.0.0/24 to any port 8201` UFW rule accepts. Two alert rules ship: `AroWakeLowSuccessRate` (<90% success over 10m, per-host via `by (host)`), `AroWakeCostBurnHigh` (>$5/h sustained, runaway-reasoning early-warning).
- **Remaining**: Phase 5 deferred items (Apprise pre-route, Loki ruler, propose/ack peer verbs); Grafana aro-wake dashboard (PromQL + Telegram alerts cover real use today — dashboard if/when ad-hoc PromQL gets tedious). See "Signal → AI wake-up matrix" in [`vps-complete-inventory.md`](vps-complete-inventory.md) for the per-mechanism row table.

### 7. DR — fleet-wide resilience claim

| Failure mode | Recovery |
|---|---|
| vps1 disk dies | `bootstrap-hub.sh` against fresh VPS → ≤ 90 min target |
| vps2 or vps3 disk dies | `bootstrap-spoke-restore.sh` against fresh VPS → ≤ 30 min target (W11, in progress) |
| vps1 down, spokes up | Spokes keep running locally; observability + tenants stay served from spokes; mesh reconverges when hub comes back |
| vps2/vps3 down, others up | Hub + other spoke unaffected; tenant on dead spoke redeployed via `fabrik apply --target-vps <other>` |
| Full fleet loss (all 3 + B2 wiped) | Out of scope. Path C in `../operations/disaster-recovery.md` — GitHub-only rebuild ~half day, secrets gone |
| Operator workstation (dev WSL) wiped | W9 DR-store on GitHub: `gh repo clone mobasak/fabrik-dr-store` → `cp env/latest /opt/fabrik/.env`. Done. |

### 8. Spoke-tenant independence (the point of the fleet)

The reason vps2 + vps3 exist is **independent tenant landing zones**. A tenant deployed to vps2 has:

- Its own public IP (96.9.214.128) — `tenant.vps2.ocoron.com` resolves there.
- Its own Traefik fronting it (cert issued via Let's Encrypt to that IP).
- Logs + metrics shipped to vps1's observability via mesh (no public exposure).
- Database + cache via mesh IP to vps1's `postgres-main` / `redis-main`.
- Backed up by vps2's own Backrest (after W11) — vps1 outage doesn't stop vps2 backups.

A second tenant can land on vps3 (or vps2 again) and is isolated from the first by being on a separate spoke compute environment, sharing only the mesh data plane.

When the fleet is sized up (not currently planned — settled at 3), the pattern extends: vps4, vps5, etc. all join as spokes via `fabrik vultr provision` (full `bootstrap-vps.sh` + PR3 auto-install of their own AI sysadmin), get added to W11's per-spoke Backrest pattern, and start receiving tenants via `fabrik apply --target-vps`.

---

## Cross-references

- [`vps-hub-rebuild.md`](vps-hub-rebuild.md) — vps1 DR runbook (the "if vps1 is gone" doc).
- [`vps-spoke-rebuild.md`](vps-spoke-rebuild.md) — planned (W11.8). vps2/vps3 DR runbook.
- [`vps-bootstrap-plan.md`](vps-bootstrap-plan.md) — spoke fresh-bootstrap (`bootstrap-vps.sh`).
- [`vps-complete-inventory.md`](vps-complete-inventory.md) — full container-by-container catalog of what runs where.
- [`vps-status.md`](vps-status.md) — point-in-time health snapshot.
- [`vps-urls.md`](vps-urls.md) — how to reach things from outside.
- [`vps-ai-sysadmin.md`](vps-ai-sysadmin.md) — bot reference.
- [`vps-residue-policy.md`](vps-residue-policy.md) — hygiene policy.
- [`../operations/disaster-recovery.md`](../operations/disaster-recovery.md) — DR scenarios A/B/C/D.
- [`../operations/credential-recovery.md`](../operations/credential-recovery.md) — W9 mirror.
- [`../operations/hub-restore-inventory.md`](../operations/hub-restore-inventory.md) — hub DR path list.
- [`../operations/spoke-restore-inventory.md`](../operations/spoke-restore-inventory.md) — spoke DR path list.
