# VPS Fleet — Status Snapshot

**Last Updated:** 2026-08-31 21:43 UTC
**Snapshot taken:** 2026-06-07 20:20 UTC (live probe via `scripts/audit_infra_vs_docs.py --hosts vps,vps2,vps3` + `ssh` + `docker ps` + Prometheus `/api/v1/targets` + per-spoke `curl :8201/metrics` + Vultr API `/v2/instances` for drill-instance cleanup). **Current-state sections (Fleet at a glance + health table) re-verified live 2026-06-15** (vps1 31 ctr, RAM 4.1/11 Gi, disk 32/108 GB 30 %, uptime ~2 w 1 d, UFW 16, Authelia 8; vps2/vps3 5 ctr each, UFW 11; mesh RTT ~135–136 ms; Prometheus 12 active/14 targets/14 up; Gatus 31 endpoints (was 33 until `coolify`/`coolify-public` removed 2026-06-17); DR drills green).
**Hosts:** vps1 (LA, hub) · vps2 (Coventry UK, spoke) · vps3 (Coventry UK, spoke)
**Deploy model:** SSH + Docker Compose (no Coolify — removed 2026-05-30)

> Companion docs: [`vps-complete-inventory.md`](vps-complete-inventory.md) for what runs where (architectural source of truth) · [`vps-urls.md`](vps-urls.md) for how to reach things. This file is a point-in-time *health* snapshot.

## Tooling/code changes since this 2026-06-07 health probe (not yet re-probed live)

- **2026-08-10 — fleet-wide container auto-heal LIVE (operator directive: unhealthy-but-alive must auto-restart, all project types).** `/usr/local/bin/fabrik-autoheal` (source: `scripts/vps-autoheal.sh`) on vps1+vps2+vps3, root cron every minute: `docker ps --filter health=unhealthy` → `docker restart`, storm-capped (max 3 restarts/container/30min, then HOLD-DOWN so Gatus/Prometheus alerting fires instead of being masked), per-container opt-out via compose label `fabrik.autoheal=false`, logs to syslog tag `fabrik-autoheal`. Spoke template `sysadmin-cron.template` extended for future installs. E2E-verified on vps1 with a deliberately failing-healthcheck container. Known interaction: site-provisioner's flapping healthcheck (row below) now earns bounded restarts on flap — fix its probe timeout upstream or label it out if noisy.

- **2026-08-04 morning: fleet-wide OAuth exhaustion — rotation worked as designed, the WINDOW was the bug.**
  All 3 hosts' keepalives went `KEEPALIVE_FAIL:401_auth` (~06:00–08:37 UTC+1): rotation correctly walked
  every account (actives ended ob/mob/mob) but **every VPS-side copy was dead**, so it exhausted + alerted
  (the operator's "🔍 Proactive Check / OAuth session expired" Telegram messages). **Root cause:** OAuth
  refresh tokens are SINGLE-USE and 4 boxes (WSL + 3 VPS) refresh the SAME 3 accounts — any refresh on one
  box invalidates the others' copies (vps2+vps3 were even both active on `mob`, killing each other hourly).
  A 6-hour snapshot-sync window cannot outrun that churn. **Mitigations landed:** WSL sync cron bumped
  **6h → hourly** (`5 * * * *` — bounds any dead-standby window to ≤1h, matching the keepalive cadence);
  recovery = `SYNC_ACTIVE=1` re-sync (all 3 `KEEPALIVE_OK` 08:37 UTC+1). **Proactive alerts now host-tagged**
  (`🔍 Proactive Check [vpsN]`) — the incident alerts were anonymous, deployed fleet-wide. **Honest residual:**
  hourly sync is a mitigation, not a cure — the multi-writer refresh-token conflict is architectural; the cure
  would be per-box dedicated accounts or routing all VPS claude calls through one credential owner. Revisit if
  exhaustion recurs at the hourly cadence. **UPDATE (same day, ~22:50): it DID recur — hourly snapshot-sync
  still failed because the manager-account SNAPSHOTS themselves go stale within hours (they only update on a
  WSL account switch; mob/ob snapshots were 31h old — the sync was faithfully distributing corpses). CURE
  IMPLEMENTED: the single-refresh-owner model — the WSL cron now runs `SYNC_ACTIVE=auto` hourly, pushing the
  WSL ACTIVE creds (in constant use → always fresh) to every host's active; VPS boxes hold a <1h-old token and
  never self-refresh, so nothing mutually invalidates. `auto` is org-guarded with an allow-unless-PROVABLY-
  foreign posture (real fleet creds often lack organizationUuid — a require-match guard blocked the cure,
  live-hit). Verified: recovery ran THROUGH the auto path, all 3 KEEPALIVE_OK 22:52. +2 tests (17 pass).**

- **Full fleet infra audit — 2026-08-03 (live probe: [`infra-probe-2026-08-03T18-37Z.yaml`](probe-reports/infra-probe-2026-08-03T18-37Z.yaml)).**
  **Verdict: fleet healthy.** Containers 31/5/5 all Up, **zero unhealthy**; UFW + fail2ban active ×3; wg mesh
  alive (hub 2 peers, spokes 1); `fabrik` docker net ×3; disk 38/14/14 %; Prometheus **0 targets down**;
  Traefik 20/20 routers enabled; Loki ingesting (~5.8 lines/s); Backrest snapshots fresh (host-aware
  proactive-check passes on all 3); postgres-main/redis-main healthy; watchdog-test dogfood + ocoron-com WP
  stack healthy; aro-wake :8201 ×3; OpenVPN on vps1 confirmed documented. **Two Gatus reds found + fixed →
  34/34 green:** (1) `site-provisioner` — its `provision.vps1.ocoron.com` **A record had been deleted at
  Cloudflare** (authoritative-NS-verified; cause unknown, deleted within ~2 days) → restored via
  `CloudflareClient.ensure_record` (DNS-only, `172.93.160.197`); the Gatus path returns 200 (hairpinned hub
  IP is allowlisted). (2) `spoke-canary` — stale endpoint for a long-removed vps2 canary app (external 404,
  no container) → removed from `configs/gatus/apps/` + vps1 (the sync script never deletes — removed on both
  sides by hand). **Notes:** spokes' `*:45191`/`*:33755` public listeners = promtail's ephemeral gRPC port
  (UFW default-deny blocks them; harmless — pin `grpc_listen_address: 127.0.0.1` if it ever matters).

- **claude-code fleet update → Node 22 + 2.1.220 everywhere + lean auto-update (2026-08-03, LIVE-verified).**
  All 3 hosts now run **Node.js 22 + Claude Code `2.1.220`** (npm-global at `/usr/bin/claude`, unified `/usr`
  prefix). **vps1 was migrated Node 18 → 22** (NodeSource): its ONLY host-level Node consumer was claude
  itself — `n8n` is containerized (`n8nio/n8n:latest`, own Node) and `node-exporter` is a Go binary — so the
  bump had zero blast radius (n8n container stayed `Up`). The Node-22 wall for claude is at **2.1.200**
  (`engines.node >=22`); before this, the fleet was drifted (vps1 `2.1.144`/Node 18; spokes `2.1.165`→`2.1.199`),
  and vps1 also carried a stale `/usr/local` install shadowing the `/usr` one — both consolidated.
  **Lean auto-update:** one root cron per host, staggered for a rollout window —
  `0 {4,5,6} * * 0 /usr/bin/npm i -g @anthropic-ai/claude-code@latest >/var/log/claude-code-update.log 2>&1`
  (Sun 04:00/05:00/06:00 UTC on vps1/vps2/vps3). Now that all hosts are Node 22 the cron is uncapped `@latest`;
  a Node-18 host would instead need a `<2.1.200` *range* (npm range installs are engine-aware).
- **Claude fleet credential rotation — the loop is now CLOSED (2026-08-03).** Symptom found during the
  version update: host `claude -p` was 401-ing fleet-wide, creds ~10 days stale. Root cause was a **missing
  schedule**, not the version. The full mechanism now:
  1. **WSL `claude-manager`** keeps the 3 accounts fresh (`{mob,ob,can}-ocoron-com-s-organization`).
  2. **WSL cron (NEW — the missing piece):** `0 */6 * * * scripts/sysadmin/sync-claude-accounts-to-fleet.sh`
     (snapshots-only) pushes the fresh account snapshots to every host's `~/.claude/manager-accounts/`.
     Agent-free SSH (cron-safe). Without this, host standby snapshots went stale, so rotation landed on dead
     accounts → the 401 storm.
  3. **Per-host keepalive cron (already deployed, all 3):** `/etc/cron.d/vps-sysadmin` runs
     `claude-keepalive-rotate.sh` hourly (staggered :27/:11/:44) → pings claude through `claude_rotate.py`,
     which **auto-rotates the active to a fresh standby on a quota-limit OR a 401** (bounded by account count;
     a 401 also fires a debounced Telegram alert).
  Verified live: all 3 `claude -p` auth OK (vps/vps2 active `can`, vps3 active `mob` — each rotates
  independently). The containerized watchdog uses its own mounted creds (separate path).
- **Sysadmin config audit — 5 defects fixed fleet-wide (2026-08-03, live-verified).**
  1. **Rotation blind spot:** the CLI's expired-OAuth render ("OAuth session expired and could not be
     refreshed") carries no "401", so `claude_rotate.py` never rotated on it — the keepalive stayed stuck
     FAIL (live-hit when the `can` re-login revoked the fleet's copied refresh token). `is_auth_401` now
     treats it as dead-creds → rotate + alert; fixed in BOTH copies (sysadmin + aro-wake twin) + the
     keepalive classifier; +regression tests; deployed to all 3 hosts, bot/aro-wake restarted.
  2. **Spoke false-alarm storm (~7 300 log errors/host over weeks):** `proactive-check.sh` is hub-centric
     but was cron'd unmodified on the spokes — `prometheus_unreachable` (no prometheus container there;
     the hub's PromQL battery already covers the fleet via host labels → now hub-gated) and
     `backup_missing[hub:*]` (spoke queried the HUB's restic repo with the SPOKE's password → now
     host-aware: own repo `/spokes/<host>/`, own plan set). Spokes now run silent-clean (rc=0).
  3. **Silent alert delivery on spokes:** `APPRISE_SEND` targets the hub-only `apprise` container → every
     spoke alert failed for weeks. Added a direct-Telegram fallback (same `TELEGRAM_*` vars as
     `claude_rotate`). **⚠ OPERATOR ACTION REQUIRED:** the spoke bots @SysAdminVPS2/@SysAdminVPS3 were
     never `/start`-ed — Telegram returns "chat not found", so even the fallback (and `bot.py`'s proactive
     sends) can't deliver from spokes until the operator opens each bot and presses Start. vps1 verified
     delivering (test message sent). Residual: morning-report/daily-digest/weekly-*/monthly-* still use
     apprise-only send — add the same fallback once the spoke bots are started.
  4. **vps1 `.env.sysadmin` was 0664** (world-readable bot token/keys) → 0600.
  5. **vps1 was missing the `daily-digest` cron** (template drift; spokes had it) → added at the canonical
     hash-slot minute (`17 9 * * *`); vps1 now matches the 8-job template.
- **Fleet size settled at 3** (vps1+vps2+vps3) — no 4th permanent spoke planned.
- **`fabrik vultr` hardening:** PR1 (provision/destroy symmetry), PR2 (G6 SAFE-RERUN-TRAP auto-retry + G3 wg0-peer removal that persists to `wg0.conf`), and **PR3 — `provision` auto-installs a new spoke's AI sysadmin** (token pool + enable + verify; 5 manual steps → 1). PR3 reviewed GREEN (5-axis) and **merged** (`0dc92e3`).
- **LIVE DR drill validated (2026-06-13/14):** `fabrik vultr drill spoke --g0-smoke` against a real Vultr droplet → `bootstrap_rc=0`, `verify_rc=0`, **0 orphans**, 528s, ~$0.015. Live-proved G5's `iptables-docker-user.service` on a fresh bootstrap. **G0 copied-creds result:** copying the hub's Claude OAuth creds to a fresh host authenticates *immediately* (`immediate_auth_ok=True`, no rotation on first use) — single-session rejection ruled out; copied-creds zero-touch is viable pending only the ~4-day refresh-token race.
- **Spoke iptables (G5/G5b):** `bootstrap-vps.sh` + `bootstrap-spoke-restore.sh` moved DOCKER-USER persistence to `iptables-docker-user.service` (dropped `iptables-persistent`, which `Conflicts: ufw` on Ubuntu 24.04). Hub unchanged (still `netfilter-persistent`).
- **Observability source-control (peer AI):** Gatus configs pulled into git + sync helper; Prometheus config-drift fix (secret extraction to `credentials_file:`, dual-write driver) — fixed two live vps1 perm bugs (`prometheus.yml` 0600, `secrets/` dir 0750).
- **CI + milestone gate:** `duplicate-check` fixed (generated-data/backup excludes + pinned `jscpd@5.0.9`); stale `KILO_CLI_RULES.md` expectation removed; **milestone-tier `final_gate --json` now GREEN (34/0)** — bandit B104/B108 false positives nosec'd, structure check allows `README.md` anywhere + runtime `.md` under `scripts/sysadmin/`, rule-size guard exempts the 3 non-auto-loaded reference catalogs.
- **Supabase:** paused `fabrik` project restored + twice-weekly GitHub Actions keep-alive (`supabase-keepalive.yml`; operator sets `SUPABASE_FABRIK_ANON_KEY`). `trade-intelligence` active (left); `ComplianceDesk` left paused.
- **Vultr API key ACL** opened to `0.0.0.0/0` (2026-06-13) so drills run from any operator host; the key alone now gates access.

---

## Fleet at a glance

| Host | Role | Public IP | Mesh IP | RAM | Disk | Containers | Uptime |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| vps1 | Hub (LA) | 172.93.160.197 | 10.99.0.1 | 11 Gi (4.1 Gi used) | 108 GB (32 GB / 30 %) | 31 (29 platform + 2 T-P5 dogfood) | ~2 w 1 d |
| vps2 | Spoke (Coventry UK) | 96.9.214.128 | 10.99.0.2 | 7.7 Gi | 58 GB | 5 | — |
| vps3 | Spoke (Coventry UK) | 104.128.190.151 | 10.99.0.3 | 7.7 Gi | 58 GB | 5 | — |

| Health signal | State |
| :--- | :--- |
| Wireguard mesh | ✅ both spokes handshaking in the last ~2 min |
| Cross-Atlantic mesh RTT | ✅ ~135–136 ms, 0 % loss (vps2 ~135.6 ms, vps3 ~136.6 ms; re-verified live 2026-06-15) |
| Prometheus scrape targets | ✅ 17 `job_name`s configured / 16 active (`fabrik-services` null-target; `pushgateway` restored `b8071f40` 2026-07-19; repo re-verified 2026-07-20; prior live probe 2026-07-12: 20/20 targets up). `node-spokes` / `cadvisor-spokes` / `promtail-spokes` ARE live (2 targets each, `prometheus.yml:46,58,70`) |
| Mesh-bound shared infra on vps1 (`5432, 6379, 8000, 9091, 3100`) | ✅ all 5 listening on `10.99.0.1` |
| Spoke DNS resolving | ✅ `vps2.ocoron.com`, `*.vps2`, `vps3.ocoron.com`, `*.vps3` all return correct A records |
| Cloudflare API token in `/opt/fabrik/.env` | ✅ verified active (refreshed today) |
| Authelia access-control rules | **8** (live in `/opt/authelia/config/configuration.yml`, verified 2026-06-07T20:20Z via `yaml.safe_load`; was 10 pre-2026-06-02 cleanup that removed 2 image-broker rules) |
| site-provisioner | ⚠ up on vps1 (running, RestartCount=1) but healthcheck **flaps** — `/health` runs live Cloudflare+Postgres+Namecheap checks that occasionally exceed the 10s timeout, so it intermittently reads unhealthy then self-recovers (no restart). App also logs `RuntimeError: No response returned` ~36×/24h — a `mobasak/site-provisioner`-repo concern, not fabrik-infra. Still **interim manual stand-up** — `fabrik apply` pipeline not yet ready |
| Backrest — vps1 hub | ✅ **4 active plans** (`postgres-dumps` 02:00, `docker-volumes` 03:00, `opt-configs` 03:00, `host-state` 03:30). Restic repo `a256277c45`. First snapshots: 117 MiB on B2 (612 MiB raw, 5.23×). |
| Backrest — vps2 spoke (W11) | ✅ **2 active plans** (`host-state` 02:00, `opt-configs` 02:30). Restic repo `56b40b8c84` at `vps1-ocoron-backups/spokes/vps2/`. First snapshots: 16.9 KiB on B2 (2.31×). Independent restic password mirrored via W9. |
| Backrest — vps3 spoke (W11) | ✅ **2 active plans** (same schedule as vps2). Restic repo `350e752618` at `vps1-ocoron-backups/spokes/vps3/`. First snapshots: 16.5 KiB on B2 (2.33×). |
| Hub disaster-recovery | ✅ **Scripted** via [`bootstrap-hub.sh`](../../scripts/bootstrap/bootstrap-hub.sh) — idempotent steps `step_00`–`step_18` (+ `12b`/`12c`; run `wc -l`/`grep -oE 'step_[0-9]+[a-z]?'` for current counts), target wall-clock ≤ 90 min. **Validated 2026-06-15/16** via `fabrik vultr drill hub`. **LE/DNS cutover validated end-to-end** against the `tojlo.com` sandbox zone: `step_17` DNS rewrite (`dr-drill-hub-20260615-154530`), `step_17b` certbot (`-160819`), `step_17c` traefik-lego (`dr-drill-hub-20260616-113524`, issuer `(STAGING) Ersatz Emmer YR2`). Operator doc: [`vps-hub-rebuild.md`](vps-hub-rebuild.md). |
| Spoke disaster-recovery | ✅ **Scripted** via [`bootstrap-spoke-restore.sh`](../../scripts/bootstrap/bootstrap-spoke-restore.sh) — steps `step_00`–`step_12` (+ `09b`/`09c`/`11b`/`12b`; run `wc -l`/`grep -oE 'step_[0-9]+[a-z]?'` for current counts), ≤ 30 min target, **preserves Wireguard identity** (hub peer-table unchanged through outage). **Validated 2026-06-15/16:** spoke fresh-install (`fabrik vultr drill spoke`) and restic-restore path (`fabrik vultr drill spoke-restore`) both green. Operator doc: [`vps-spoke-rebuild.md`](vps-spoke-rebuild.md). |
| Credential recovery (`/opt/fabrik/.env`) | ✅ **W9 shipped 2026-06-01.** Inotify + systemd watcher (`fabrik-dr-watcher.service`) pushes every change to private `mobasak/fabrik-dr-store` within seconds; daily safety-net cron + reboot catch-up + weekly self-test. **Sysadmin token added to scope** via SSH-pull (W9 extension, same day). See [`docs/operations/credential-recovery.md`](../operations/credential-recovery.md). |
| Backups | ✅ same as Backrest plans row — first real backup chain since the 2026-05-31 wipe. |

---

## 2026-06-07 — iteration discipline day: Phase 5.1.a LIVE + SLI gap closed + netdata cleanup + bootstrap defenses + first measured DR drill

Day-after consolidation. Yesterday's fleet rollout shipped 10 commits' worth of substrate; today consolidated five gaps, measured one target, and codified the operator-discipline traps surfaced along the way.

### A — Stale `netdata` scrape job removed (cause of overnight Telegram flood)

24 spurious Telegram messages between 2026-06-06 21:00 and 2026-06-07 11:47 — every 30 min for ~12h. Root cause: `netdata` container was retired 2026-05-30 (backup file `prometheus.yml.bak-netdata-removal-20260530-223414` confirms intent) but the `netdata` scrape job in `configs/prometheus/prometheus.yml` was left behind. `up{job="netdata"} == 0` from then on, triggering `ServiceUnhealthy`. The 2026-06-05 Phase 4 wire routes every `severity=~"critical|warning"` alert to BOTH aro-wake AND Telegram (`continue: true`), and the receiver's `repeat_interval: 30m` cycled the message until alert state cleared. Fix: silenced active alert via `amtool` for immediate relief, removed the job from `prometheus.yml` with a 6-line comment explaining, SIGHUP-reloaded Prometheus, verified 14/14 remaining targets up + 0 active alerts. Commit `f5c6e48`.

### B — Spoke-bootstrap deps baked into `bootstrap-vps.sh` + Gatus endpoints + UFW route backstop

Three follow-ups from 2026-06-06's spoke rollout shipped in commit `175ea69`:

- **`bootstrap-vps.sh` step_02** now installs `python3-venv` + `python3-pip` apt packages (needed by step_15's aro-wake venv create and step_14b's pip install)
- **`bootstrap-vps.sh` step_14a (NEW)** installs Node.js 22 + `@anthropic-ai/claude-code` via npm (idempotent: skips if `command -v claude` succeeds)
- **`bootstrap-vps.sh` step_14b (NEW)** installs `python-telegram-bot==22.7` via `sudo pip install --break-system-packages` (idempotent: skips if `python3 -c "import telegram"` succeeds)
- **`bootstrap-vps.sh` step_14 mkdir block** adds `sudo chown ozgur:ozgur /opt/fabrik /opt/fabrik/scripts /opt/fabrik/logs` so step_15's `sudo -u ozgur python3 -m venv` can write
- **`bootstrap-hub.sh` step_07** adds defensive `sudo ufw route allow in on wg0 out on wg0` as backstop for the spoke↔spoke routing rule (idempotent — UFW dedupes; covers the case where hub rebuild happens before the 2026-06-07 02:00 Backrest snapshot captures the rule in `user.rules`)
- **Gatus** gains an `aro-wake.yaml` config file at `/opt/monitoring/configs/gatus/apps/` on vps1 — 3 endpoints in the `trio-aro-wake` group (vps1 via docker-bridge `10.0.1.1:8201`, vps2/vps3 via wg0 `10.99.0.{2,3}:8201`), all `success=True` on first poll. (Gatus configs not yet in source control — separate follow-up tracked in `docs/STRATEGIC_BACKLOG.md`.)

### C — Rate-limited 429 wakes now tracked (SLI gap closed)

Yesterday's acknowledged SLI gap closed in commit `febc475`. Two `M_REQUESTS.labels(source=source, status="rate_limited").inc()` calls added — one in the alertmanager-path rate-limit branch (`main.py` ~L856 as of that date; the calls sit at ~L956/L1033 in the current 1148-line file), one in the main-path rate-limit branch. `aro_wake_requests_total` counter now has three status values: `success`, `failure`, `rate_limited`. `AroWakeLowSuccessRate` alert denominator updated from `aro_wake_requests_total` to `aro_wake_requests_total{status!="rate_limited"}` so rate-limited drops (refused at the gate before Claude ran) don't unfairly lower the LLM success-rate SLI. Smoke-verified live with `ARO_WAKE_RATE_LIMIT=1` drop-in: counter went `{status="rate_limited"} 1.0` after the second wake; drop-in cleaned up after.

### D — Phase 5.1.a operator-reversal detection cron LIVE on FULL fleet

Per trio plan Phase 5.1.a. New `/opt/fabrik/scripts/sysadmin/detect_reversals.py` correlates AI actions (watchdog sidecar `state.db` + `sysadmin-actions.jsonl`) against subsequent operator-issued docker commands within a 5-minute window. Matches go to `/opt/fabrik/logs/lessons-pending.jsonl` for weekly review. Reversal classes detected today: `restart_container → docker (restart|stop|kill|rm|up) <same_name>`. Classes scaffolded for future expansion: `clear_redis_cache`, `rotate_logs`.

Idempotency by `(ai_source, ai_ts, operator_ts)` tuple: pre-existing entries deduplicated, re-running 2× after a match produces 0 new entries (verified live). Defensive design (cron-grade): 10–15s subprocess timeouts; state.db read fail → single-line WARN to stderr, continue; SQL parse error → skip row. Never crashes a cron job over an observability gap.

End-to-end test verified live on vps1: `docker kill watchdog-test` → 90s wait → sidecar autonomous `restart_container` lands in state.db → `sudo docker restart watchdog-test` simulates operator reversal → detector wrote 1 entry to `lessons-pending.jsonl` with class=restart_container, delta_seconds=41.6. Cron entries added to `/etc/cron.d/vps-sysadmin` on vps1+vps2+vps3 (appended; existing routines untouched). `bootstrap-vps.sh templates/sysadmin-cron.template` also updated for future spoke installs. Commit `08d257e`.

### E — `STRATEGIC_BACKLOG.md` created from scaffold template

Until today, every Fabrik scaffolded project had a `docs/STRATEGIC_BACKLOG.md` but the Fabrik repo itself didn't. Created from `templates/scaffold/docs/STRATEGIC_BACKLOG_TEMPLATE.md` per `src/fabrik/scaffold.py:196` mapping. Populated with 10 deferred items across Now (2)/Later (8)/Context (7 lessons + invariants) tiers. Each "Later" item names its triggering condition explicitly so future-you doesn't re-derive why an item was deferred. INDEX.md updated with the docs/ row per CLAUDE.md doc-sync matrix. Commit `9759f9e`.

### F — 6 bootstrap defenses (caught by first DR drill 2026-06-07 evening)

First DR drill on a Vultr throwaway droplet (`vc2-1c-2gb`, region `lax`, $0.02) caught two real bugs in today's bootstrap-vps.sh edits AND surfaced one operator-discipline trap. All three closed with code + docs + rule pack so the next person doesn't re-discover them:

| # | Defense | Where |
|---|---|---|
| 1 | `bootstrap-vps.sh` preflight auto-detects `root@` failure when `ozgur@` works; aborts with actionable error BEFORE the 3rd-retry fail2ban trigger | `scripts/bootstrap/bootstrap-vps.sh` preflight (~50 lines) |
| 2 | `bootstrap-hub.sh` preflight: same hardening, same error message | `scripts/bootstrap/bootstrap-hub.sh` (~28 lines) |
| 3 | step_14a + step_14b: dropped the cosmetic version-print on the "already installed" branch (eliminated nested `$(...)` inside `echo "..."` inside `remote '...'` that crashed on remote bash with a "syntax error near unexpected token" on the Python dunder version attribute) | `scripts/bootstrap/bootstrap-vps.sh` step_14a + step_14b |
| 4 | `vps-spoke-rebuild.md` + `vps-hub-rebuild.md`: new "Re-run discipline" section with the SSH user-transition table | both rebuild docs |
| 5 | NEW rule pack `.windsurf/rules/core/90-bootstrap-scripts.md` (force-added through gitignore): 6 numbered rules triggered by globs on `scripts/bootstrap/**/*.sh` + the rebuild docs | rule pack |
| 6 | `AFCL.md`: 2 new rows under "Identified Constraints" — Operator Discipline + Quote Escaping, both High severity | AFCL |

Commits `ae5f20f` (defenses) + `11efe1c` (rule pack force-add).

### G — fabrik-vultr-provisioning plan SAVED (now at [`docs/archive/2026-06-07-fabrik-vultr-provisioning.md`](../archive/2026-06-07-fabrik-vultr-provisioning.md))

New plan covering on-demand VPS provisioning (permanent fleet members AND disposable drills) via Vultr API v2. Two modes documented: `fabrik vultr provision <name>` for permanent fleet members (auto-runs bootstrap, mesh+DNS+Backrest+observability registration) and `fabrik vultr drill <kind>` for throwaway drills (auto-destroyed, drill report written to `logs/dr-drill-history.jsonl`). 7 phases of implementation work, ~4-5 days focused. Plan extended by operator/linter to cover all 7 Vultr compute product lines (`vc2`/`vdc`/`vhf`/`vhp`/`voc`/`vcg` Cloud GPU + `vbm` Bare Metal). Commits `accb2b5` + `675f7a3`.

### H — DR drill MEASURED end-to-end (Drill #2)

First measured drill of the spoke-bootstrap path. The ≤30 min wall-clock target is no longer aspirational.

| Metric | Value |
|---|---|
| Provider | Vultr Cloud Compute, `vc2-1c-2gb`, region `lax`, Ubuntu 24.04 LTS x64 |
| Invocation | `bootstrap-vps.sh --skip-mesh --skip-dns root@149.28.70.237 vps4` |
| Wall-clock | **3m 13s (193s)** — 9.3× under the ≤30 min target |
| End-state contract | **15/15 substantive checks passed** |
| Open finding | `sshd PasswordAuthentication=yes` despite step_01 hardening attempt (investigate next drill) |
| Total cost | $0.04 (instance up ~30 min between provisioning and destroy) |
| Cleanup | `DELETE /v2/instances/<id>` → HTTP 204, 0 instances remaining |

**Today's 4 new bootstrap edits — all validated live**:

- `python3-venv` 3.12.3-0ubuntu2.1 + `python3-pip` 24.0+dfsg-1ubuntu1.3 installed ✓
- Node.js v22.22.3 + `claude --version` returns `2.1.168 (Claude Code)` ✓
- `python-telegram-bot` 22.7 importable in system Python ✓
- `/opt/fabrik` ownership = `ozgur:ozgur` (recursive) ✓

**Today's quote-escape fix validated**: Drill #1 crashed at step_14b on the bash syntax error in the now-removed nested `$()` cosmetic version-print. Drill #2 ran clean through step_14b → step_15.

Drill report at `/opt/fabrik/logs/dr-drill-history.jsonl` (gitignored). The future `fabrik vultr drill spoke` command will append entries to this same file.

### Vultr API integration confirmed working

- `VULTR_API_KEY` saved to `/opt/fabrik/.env.sysadmin` mode 600 (also `VULTR_SSHKEY_ID=fff13c0e-de4a-4027-aee1-68efad7e53ae`)
- `.env.sysadmin` was NOT in `.gitignore` before today — explicitly added in commit `675f7a3` (would have leaked the API key on next `git add -A`)
- `/v2/account` auth probe ✓
- `/v2/instances` enumeration ✓
- `/v2/ssh-keys` lookup ✓
- `DELETE /v2/instances/<id>` returns HTTP 204 ✓

**Trio plan status:** Phase 1 LIVE ✓ · Phase 2 LIVE on full fleet ✓ · Phase 3 LIVE on full fleet ✓ · Phase 4 LIVE on vps1 ✓ · **Phase 5.1.a operator-reversal cron LIVE on full fleet ✓** · Phase 5 remaining items (propose/ack peer verbs, Apprise pre-route, Loki ruler, repeated-flag-no-action detector) explicitly deferred until incident-driven per `docs/STRATEGIC_BACKLOG.md` Later tier.

---

## 2026-06-06 — full-fleet rollout day: aro-wake LIVE on spokes + spoke↔spoke routing + loop guards + Prometheus SLI metrics

**Trio plan crossed the "all 3 hosts running the same AI" line.** Yesterday vps1 was the only host with aro-wake. Today all three hosts run identical aro-wake code with the same loop guards and the same metric exposition. Two real cross-host consults (vps2→vps1, vps3→vps1) returned rich diagnostic responses end-to-end.

### A — Phase 2 + Phase 3 spoke deploys SHIPPED (vps2 + vps3)

Operator delivered prerequisites: `claude auth login` on each spoke, `@BotFather` token for `SysAdminVPS2` + `SysAdminVPS3`. Deploy inlined `bootstrap-vps.sh step_14` (sysadmin pack) + `step_15` (aro-wake) bypassing the full bootstrap because the rest of the spoke is already running. Gaps discovered + fixed live:

1. **Node.js 22 + Claude Code CLI missing** on spokes — installed via NodeSource + `npm install -g @anthropic-ai/claude-code`; both spokes now run Claude 2.1.165 at `/usr/bin/claude`.
2. **`python3-venv` apt package missing** on Ubuntu spokes (`ensurepip` error) — `sudo apt-get install -y python3.12-venv` on both spokes.
3. **`/opt/fabrik/` was root-owned on spokes** — `sudo chown -R ozgur:ozgur /opt/fabrik/` after venv creation under sudo.
4. **`python-telegram-bot==22.7` library missing** — `vps-sysadmin-bot.service` was failing on `ModuleNotFoundError: No module named 'telegram'`. Fixed via `sudo pip install --break-system-packages python-telegram-bot==22.7` on both spokes.

After fixes: `vps-sysadmin-bot.service` and `aro-wake.service` both `active` on both spokes. `/health` from hub over wg0 mesh returned `{"ok":true,"host":"vps2","role":"spoke",...}` and same for vps3. Yesterday's queued vps3 forward auto-drained at the first drain tick post-aro-wake (vps1 logs show `aro-wake HTTP Request: POST http://10.99.0.3:8201/wake "HTTP/1.1 202 Accepted"` once vps3 became reachable).

**Real cross-host consults — first time the trio actually talked to each other:**

- vps2→vps1: vps1 responded with mesh handshake age (50s), Prometheus `up=1` on all 3 spoke scrape jobs, Loki ingesting 25 lines/5m for `host="vps2"`, zero active alerts referencing vps2, plus a real follow-up flag ("I don't see vps2 endpoints registered in Gatus yet"). 133ms RTT (cross-region) confirmed.
- vps3→vps1: vps1 correlated against the vps2 consult ("identical shape. Both spokes are mesh-up + log-shipping but hold zero sessions on hub postgres/redis. That's the expected baseline — no tenant workloads deployed on spokes yet"). Pointed to `pg_stat_activity` as the follow-up signal.

### B — Spoke↔spoke wg0 routing SHIPPED

Single UFW rule on vps1 opened the path: `sudo ufw route allow in on wg0 out on wg0`. vps1 already had `net.ipv4.ip_forward=1` (from OpenVPN setup); spokes already had `AllowedIPs=10.99.0.0/24` (routing the full mesh subnet via hub). The only missing piece was UFW's default-DROP routed-policy gate.

After: `ssh vps2 ping 10.99.0.3` → 0% loss, 266ms via hub-hop (vs 133ms hub↔spoke — the doubled latency is the extra hop). vps3↔vps2 symmetric. **`curl --interface wg0 https://1.1.1.1` from vps2 still fails fast with exit 7** — UFW's default-DROP routed policy remains, so vps1 cannot be used as a public-internet egress relay (verified by tcpdump that the routed allow is strictly wg0→wg0, not wg0→eth0).

### C — 4 loop-prevention guards in aro-wake

With direct spoke↔spoke reach now possible, the protocol needed hardened cycle prevention. `scripts/aro-wake/main.py` added ~100 lines covering 4 in-memory guards:

| Layer | Where it trips | Tunable env vars |
|---|---|---|
| 1. Trace-id dedup | Same `trace_id` arriving twice on this host within 5 min — returns 200 `reason:"duplicate"` without running Claude | `ARO_WAKE_DEDUP_TTL`, `ARO_WAKE_DEDUP_MAX` |
| 2. Hop cap (backstop) | `len(seen_by) > fleet_size + 1` (default 3) — drops with `reason:"hop_limit_exceeded"` | `ARO_WAKE_HOP_LIMIT` |
| 3. Forward-target intersection *(PRIMARY)* | `_try_forward` refuses to send to a host already in `payload.seen_by`; the alertmanager handler ALSO pre-checks before the forward call (the pre-check is the optimized path, both emit `M_FWD_SUPPR{reason="seen_by"}`) | n/a |
| 4. Storm breaker | Per-target rolling-10-min cap on outbound forwards (default 8) — first trip logs ERROR "operator should investigate runaway origin", subsequent trips inside window are deduped | `ARO_WAKE_STORM_THRESHOLD`, `ARO_WAKE_STORM_WINDOW` |

All state in-memory; restart = reset = safe default. Verified live with 6 adversarial tests (hop cap on 4-entry seen_by; dedup returns "duplicate" in 33ms; forward-target seen_by suppress; storm breaker; cycle pre-check falls through to local 202 without queue spam; failure-path `status="failure"` synthesized via `WAKE_TIMEOUT=1`).

### D — Prometheus SLI metrics SHIPPED on full fleet

aro-wake exposes 9 metrics at `/metrics` on every host (counters: `aro_wake_requests_total{source,status}`, `aro_wake_cost_usd_total{source}`, `aro_wake_dedup_drops_total`, `aro_wake_hop_limit_exceeded_total`, `aro_wake_forward_suppressed_total{target_host,reason}`, `aro_wake_storm_breaker_trips_total{target_host}`, `aro_wake_digest_input_total{from_host}` — the last added 2026-06-17; gauges: `aro_wake_pending_queue_size`, `aro_wake_active_sessions`). Reuses port 8201 — no new port allocated.

Prometheus scrape job `aro-wake` in `configs/prometheus/prometheus.yml` covers all 3 hosts. vps1 via docker-bridge gateway `10.0.1.1:8201` (1.4ms scrape); vps2/vps3 via wg0 mesh `10.99.0.{2,3}:8201` (~270ms scrape). Cross-mesh container→host NAT path verified via tcpdump on vps2's wg0: Prometheus container's outbound SYN arrived with source `10.99.0.1.<port>` — docker MASQUERADE rewrites the source to vps1's wg0 IP, which the spokes' existing `from 10.99.0.0/24 to any port 8201` UFW rule already permits.

Two alert rules in the new `aro_wake` group at `configs/prometheus/rules/alerts.yml`, both evaluated per-host via `by (host)`:

- **`AroWakeLowSuccessRate`** — warning at <90% success rate over 10m for 15m
- **`AroWakeCostBurnHigh`** — warning at >$5/h sustained 10m (runaway-reasoning early-warning)

Both `inactive` at end of day (success rate 100%, cost rate ~$0/h on all 3 hosts). Hallucination Rate + Tool Call Accuracy SLIs from the source doc explicitly skipped (no ground-truth eval data); rate-limited 429 wakes not currently tracked (acknowledged follow-up, low priority).

### E — Spoke bootstrap gaps captured for tomorrow's `bootstrap-vps.sh` commit

The four spoke gaps discovered today must be baked into bootstrap for future spoke installs:

1. Install Node.js 22 + Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
2. Install `python3-venv` apt package (Ubuntu 24.04 needs `python3.12-venv`)
3. Install `python-telegram-bot==22.7` via `sudo pip install --break-system-packages`
4. Pre-create `/opt/fabrik/` ownership = `ozgur:ozgur` before venv steps

**Open security follow-up**: operator should rotate the two bot tokens that were pasted in chat history (`/revoke` → `/token` in `@BotFather`).

**Trio plan status:** Phase 1 LIVE ✓ · Phase 2 LIVE on full fleet ✓ · Phase 3 LIVE on full fleet ✓ · Phase 4 LIVE on vps1 ✓ · Phase 5 deferred (propose/ack peer verbs, Apprise pre-route, Loki ruler).

---

## 2026-06-05 — aro-wake LIVE on vps1 + Phase 4 code shipped (Alertmanager → aro-wake)

**aro-wake.service ACTIVE on vps1** (hub) — first cross-host comms primitive in the fleet is now operational. Today's session moved from "all code-shipped, none enabled" to "Phase 3 verified live; Phase 4 code shipped, config gate remaining."

**A — Live deploy on vps1 (`Option A` from today's choice):**

- Refreshed `/opt/fabrik/scripts/sysadmin/system-prompt.txt` on vps1 from 232 → 354 lines (trio Phase 1.1 prompt). `bot.py` restarted to pick up new prompt. `peer-protocol.md` copied to `/opt/fabrik/scripts/sysadmin/peer-protocol.md`.
- Installed aro-wake source tree at `/opt/fabrik/scripts/aro-wake/`, venv at `/opt/fabrik/.venv-aro-wake/` (FastAPI 0.115 + uvicorn[standard] 0.32 + httpx 0.27), systemd unit at `/etc/systemd/system/aro-wake.service`.
- `systemctl enable --now aro-wake.service` → active in 4s, idle ~32MB RAM, 0% CPU.
- Live verification: `curl http://10.99.0.1:8201/health` → `{"ok":true,"host":"vps1","role":"hub","pending_queue_count":0,"active_sessions":0}`.
- All five batch-3 fixes verified in production: port 8201 (no conflict), CSV env var (no JSON quote-strip crash), lifespan handler (clean startup), log file owned ozgur (writable), bind initially mesh-only (no public exposure).

**A2 — Synthetic consult posing as vps3 (real Claude spawn, full E2E):**

```
POST /wake source=consult from_host=vps3 seen_by=[vps3] topic=mesh_handshake_check
  payload: { my_view: "vps3→vps1 handshake 22s old", asking: "any hub-side blip 22:00-22:30 UTC?" }
```

Claude's response (verbatim shape, peer-protocol.md §2.1 compliant):

```json
{
  "ok": true,
  "from_host": "vps1",
  "trace_id": "3c5306c7-...",
  "seen_by": ["vps3", "vps1"],
  "view": "CONSULT RESPONSE to vps3 (trace_id=3c5306c7)\n\n**Time check:** current is 19:31 UTC; the 22:00–22:30 window you reference is ~21h ago...\n\n**Hub view, 22:00–22:30 UTC 2026-06-04:**\n- ALERTS at 22:30 UTC: `ContainerHighMemory` firing, severity=warning, on **prometheus** container (MONITORING tier — local self-pressure, not mesh-side)...\n\n**Correlation:** I don't see a mesh signal that would correlate with degraded perf you'd notice from vps3...",
  "correlation": "",
  "no_action": true
}
```

What Claude did autonomously:
1. Caught the time mismatch in my synthetic payload (current 19:31 UTC vs reference window 21h ago)
2. Actually queried Prometheus + Alertmanager for the requested window
3. Found a real `ContainerHighMemory` alert and correctly classified it as MONITORING-tier self-pressure
4. Checked wg0 handshakes — confirmed peer's claim of 22s old
5. Drew a correlation: hub-side issue would affect query reliability, not mesh
6. Honored consult contract: `No action taken (consult-only per peer-protocol §3.3)`
7. Invited follow-up

**This is the trio plan working in production.** Cost: $0.39 cold-cache manual selftest + $0.15 cold-cache consult = ~$0.54 of subscription burn for full E2E proof.

**B — Phase 4 code shipped (Alertmanager → aro-wake):**

`main.py` gains a `source=alertmanager` branch in the `/wake` handler:

- `_extract_alertmanager_host()` parses Alertmanager v4 webhook body → finds `host` label from `commonLabels` first, then per-alert `labels.host`, then `labels.instance` (stripped to hostname). Returns `None` if no host can be resolved → local processing with `low_quality_alert` warning for operator review.
- Host-routing: if `host` is a peer in `PEER_HOSTS`, forward to that peer's `aro-wake` via the existing `_try_forward()`; on success return 200 with `{forwarded_to: <peer>}`; on failure queue in `/var/lib/aro-wake/pending.jsonl` (24h TTL) and return 503 so Alertmanager's `continue: true` route falls through to telegram fallback.
- Local processing: pack alert summary into payload, prompt Claude with explicit incident-playbook reminder + deconfliction rule (`*-watchdog` sidecar check before any restart).
- Smoke tests verified live:
  - `host=vps3` (unreachable peer) → 503 + queued → drain retries every 30s as designed. Verified in `/var/lib/aro-wake/pending.jsonl`: entry with `intended_for=vps3`, `attempts=N`, `ttl_until=+24h`.
  - `host=vps1` (local) → spawns Claude with playbook-aware prompt → Claude correctly refused to act on MONITORING-tier prometheus container, returned proper Target/Issue/Action/Result format.

**B Phase 4 — bind + UFW posture changes:**

- aro-wake systemd unit `--host` changed from `10.99.0.1` (mesh-only) → `0.0.0.0`. Reason: Alertmanager runs in a docker container on the `fabrik` network and cannot reach the host's wg0 IP from inside its network namespace (verified: container→10.99.0.1:8201 times out). Binding 0.0.0.0 + UFW protection covers all access patterns.
- UFW posture verified on vps1: default-deny incoming + explicit allow-list (22/80/443/1194/51820); port 8201 not in allow-list so PUBLIC ingress is blocked (`exit=000 time=3.002` from off-host probe).
- New UFW rules added (vps1 + future spokes via `bootstrap-vps.sh step_15`):
  - `ufw allow from 10.0.0.0/8 to any port 8201 proto tcp` — docker bridge (Alertmanager + other containers)
  - `ufw allow from 10.99.0.0/24 to any port 8201 proto tcp` — wg0 peer consults
- Reachability matrix verified after rule add:

| From | Probe | Result |
|---|---|---|
| Container on `fabrik` net | `wget http://10.0.1.1:8201/health` | ✓ 200 OK |
| Host (loopback) | `curl http://10.99.0.1:8201/health` | ✓ 200 OK |
| Public internet | `curl http://<vps1-public-ip>:8201/health` | ✗ timeout (UFW deny) |
| Peer over wg0 (future) | `curl http://10.99.0.1:8201/health` | ✓ allowed by rule |

**B Phase 4 — operator action remaining (NOT applied today):**

Alertmanager config edit at `/opt/monitoring/configs/alertmanager/alertmanager.yml` to add the aro-wake receiver + route. Snippet shipped at `scripts/aro-wake/templates/alertmanager-aro-wake-snippet.yaml` documents the exact `webhook_configs` block + the `continue: true` route entry (preserves telegram fallback so we never lose visibility if aro-wake is down). Operator applies + `docker kill -s HUP alertmanager` to reload.

**Trio plan status:** Phase 1 live ✓ · Phase 2 code-shipped, operator-gated · Phase 3 LIVE ✓ · Phase 4 code-shipped, Alertmanager config gate remaining · Phase 5 deferred to iteration.

---

## 2026-06-04 evening (batch 3) — third deep review pass: 5 more bugs fixed before any production enable

The third review pass found a class of bugs invisible to syntax checks and module-import smokes: **systemd's `Environment=` directive strips embedded JSON double-quotes**, which would have crashed uvicorn at startup on every spoke. Plus 4 quieter bugs in the same review.

| # | Bug | Symptom | Verification | Fix |
|---|---|---|---|---|
| 1 | systemd strips bare JSON quotes from `Environment=` value | aro-wake's `ARO_WAKE_PEER_HOSTS={"vps1":"10.99.0.1"}` arrived at Python as `{vps1:10.99.0.1}` — invalid JSON → `json.loads()` throws → uvicorn lifespan startup fails → systemd restarts endlessly | systemd unit round-trip on host: `Environment=` → ExecStart-visible value showed quotes stripped | Switched to CSV format `vps1:10.99.0.1,vps3:10.99.0.3` — no quoting hazard. `main.py::_parse_peer_hosts()` accepts either CSV (preferred) or JSON (backward compat). Bootstrap step_15 now renders CSV via `PEER_HOSTS_CSV` placeholder. |
| 2 | `_set_session` stored local `sid` before parsing Claude's envelope | If Claude returned a different `session_id` than the one we passed via `--session-id`, future `--resume` would target the wrong session | source-code inspection of `_run_claude` | Moved `_set_session` to AFTER envelope parse; uses `envelope.get("session_id", sid)` so the effective sid is stored |
| 3 | `_sessions.pop` in resume-failure path skipped `_sessions_lock` | Race: concurrent `/wake` on same (source, topic) could observe stale sid mid-pop and resume against a session we just dropped | source-code inspection | Wrapped the pop in `with _sessions_lock:` |
| 4 | aro-wake assumed Claude envelope is always a dict | Some Claude versions stream a list of events; `envelope.get("result")` would `AttributeError` | source-code inspection (`fabrik-lib/watchdog/watchdog_sidecar/llm_client.py` — the defensive parse, at ~L509 in the current file; ~L392 as of the entry date) | Defensive parse: if `envelope is list`, take the last dict element that carries a `result`; if not a dict at all, return error |
| 5 | OAuth keepalive cron runs as `ozgur` but `/var/log/claude-keepalive.log` doesn't exist (default-root in `/var/log`) | Cron would silently fail with permission denied; token would silently go stale; AI would fall back to OpenRouter / rule-only mode after ~4 days | live `proactive-check.sh` `oauth_keepalive_stale` rule would catch it eventually | `step_14` now pre-creates `/var/log/claude-keepalive.log` + `/var/log/sysadmin-proactive.log` + `/var/log/vps-sysadmin-bot.log` with correct ownership |

**Verification:**

```text
=== systemd-managed CSV round-trip ===
Value as seen by ExecStart: <<<vps1:10.99.0.1,vps3:10.99.0.3>>>   ✓

=== module re-smoke ===
PEER_HOSTS parsed from CSV: {'vps1': '10.99.0.1', 'vps3': '10.99.0.3'}   ✓
JSON backward-compat ✓
session_id from envelope used (Bug A) ✓
_sessions.pop guarded by lock (Bug B) ✓
list envelope defensive parse (Bug C) ✓
```

All 5 fixes land BEFORE any host enables `aro-wake.service` or runs the OAuth keepalive cron, so no in-flight state is affected.

**OpenRouter dispatch contract verified (Bug F from review notes — false alarm):** both `_invoke_claude_code` (now ~L436) AND `_invoke_openrouter` in `fabrik-lib/watchdog/watchdog_sidecar/llm_client.py` correctly append `_WATCHDOG_DISPATCH_CONTRACT` after the canonical prompt. Not a bug.

---

## 2026-06-04 evening — Trio Phase 1+2+3 SHIPPED: code-side complete, three-veteran-sysadmin model deployable to spokes

Three commits land in `mobasak/fabrik` + one in `mobasak/fabrik-lib`, bringing the symmetric AI-ops layer from plan to deployable code. Live deploy on spokes is gated on operator action (three @BotFather tokens + `claude auth login` per spoke).

**`mobasak/fabrik`:**

- `434d70b` — trio Phase 1 + T-P5 close: canonical veteran-sysadmin prompt restored to watchdog + peer-protocol primitive defined.
- `d83bfb0` — trio Phase 2 code: bootstrap `step_14_install_sysadmin_pack` + OAuth keepalive heartbeat in proactive-check.
- `ed24f78` — trio Phase 3 code: aro-wake push-trigger service per host (consult verb live; propose/ack deferred to Phase 5).

**`mobasak/fabrik-lib`:**

- `d48c2df` — watchdog/sidecar: revert narrow `_WATCHDOG_SYS_PROMPT`, load canonical prompt + append dispatch contract.

**What's live on vps1 right now:**

- `watchdog-test-watchdog` sidecar runs the canonical 353-line veteran-sysadmin prompt + the watchdog dispatch contract addendum. Functional verification: `docker kill watchdog-test` → detection 60s → Claude Opus diagnose → Tier A `restart_container` → resolved in 6s end-to-end. Reasoning: *"Container watchdog-test has exited with 0 restarts, indicating a clean failure. Container is marked unhealthy. Standard auto-heal protocol for clean exit is immediate container restart to restore service state."* — veteran-shaped (correlates two pieces of evidence + names the protocol), vs yesterday's narrow prompt which produced no reasoning at all.
- vps1's `bot.py` + `proactive-check.sh` continue to use the same prompt (no regression).

**Trio Phase 2/3 code shipped but NOT yet deployed on spokes (operator action gates):**

| Gate | Owner |
|---|---|
| Three @BotFather Telegram bots (or one shared with prefix routing per §7 Q1) | operator |
| `claude auth login` device-flow handshake on vps2 + vps3 | operator (browser) |
| `./scripts/bootstrap/bootstrap-vps.sh --spoke vps2` runs `step_14` + `step_15` cleanly | code-ready; needs operator-provided tokens |
| `ssh vps2 'sudo systemctl enable --now vps-sysadmin-bot.service aro-wake.service'` | post-bootstrap operator step |
| `curl http://10.99.0.2:8201/health` from hub | smoke test |

**Cron-slot allocation (hash-stable, computed at install time so vps4/vps5 join cleanly):**

- vps2: daily digest 09:09 UTC, OAuth keepalive every hour at :11
- vps3: daily digest 09:24 UTC, OAuth keepalive every hour at :44

**Port allocation (added to PORTS.md):**

- 8201 — aro-wake push-trigger AI endpoint. Range 8200-8299 ("Management tools"; 8200 was retired Duplicati 2026-04-17). Each host binds its wg0 IP only.

**Issues found and fixed in the same review pass:**

1. **Port conflict** — initial code used `8002` which collides with `fabrik-claim-validator` per PORTS.md. Renamed across 7 files (main.py + service template + bootstrap step + proactive-check + peer-protocol.md + trio plan + system-prompt.txt).
2. **aro-wake race conditions** — `_sessions` dict, rate-limiter buckets, and pending.jsonl writes were unprotected against concurrent `/wake` requests. Added `threading.Lock` for the synchronous structures + `asyncio.Lock` for the file. Hammer test: 30 concurrent calls against a 20/h cap allowed exactly 20.
3. **FastAPI `@app.on_event` deprecation** — replaced with `asynccontextmanager` lifespan handler (`lifespan` param on FastAPI 0.115).
4. **`daily-digest.sh` missing** (referenced in cron template but didn't exist) — created the script with full health-heartbeat output; Apprise-routed to Telegram on hosts where Apprise is reachable (vps1); spokes log-only until §7 Q1 routing lands.

---

## 2026-06-04 — T-P5 dogfood Step 6 SHIPPED: watchdog self-heals via Claude Code Opus end-to-end

**Live evidence (2026-06-04):**

```text
incident:  container_not_running urgent  (rule: container-state pass)
  detected at:  T+34s after `docker kill watchdog-test`
  resolved at:  T+37s  (auto)

action:    restart_container   tier=A   result=success

nginx:     Status=running RestartCount=0   StartedAt=T+37s
```

The first end-to-end per-project watchdog → Claude Code Opus → Tier A self-heal in the platform's history. Spec: [`specs/services/watchdog-test.yaml`](../../specs/services/watchdog-test.yaml). Sub-plan: [`2026-06-03-watchdog-P5-subplan.md`](../development/plans/archived/2026-06-03-watchdog-P5-subplan.md). Container count on vps1: 29 → 31.

**What got there in the end** — Step 6 surfaced **five** silent-failure modes in the sidecar's docker-probe + Claude subprocess paths, all root-caused and committed. The full table is in [`vps-complete-inventory.md`](vps-complete-inventory.md#per-project-watchdog-sidecars-t-p2--complete-2026-06-03-all-15-artifacts-shipped); summary:

| # | Failure | Fix |
| :--- | :--- | :--- |
| 1 | `gather_snapshot()` returned `{container, ts}` only — docker.sock GID mismatch (sidecar UID 1000 vs sock GID 988) | Driver `_detect_docker_sock_gid()` injects `group_add: [<gid>]` into compose overlay (auto-detected via `stat -c %g` at apply time) |
| 2 | `docker inspect` exit 1: "client version 1.41 is too old. Minimum supported API version is 1.44" | `Dockerfile`: `ENV DOCKER_API_VERSION=1.44` |
| 3 | Claude exit 1: "sandbox required but unavailable: bubblewrap (bwrap) not installed, socat not installed" | `Dockerfile`: install `bubblewrap` + `socat` |
| 4 | Claude exit 1: "Claude configuration file not found at: /home/watchdog/.claude.json" | Driver adds second bind-mount: `{VPS_CLAUDE_HOME}.json:/home/watchdog/.claude.json:ro` |
| 5 | Claude exit 1 / silent rc=0 empty stdout / "envelope missing/malformed result" — **`--max-budget-usd` was the recurring killer**, Opus session-init cost alone exceeds any sane per-call cap | Drop `--max-budget-usd`. Drop `--effort` (silent rc=0 with `-p` in 2.1.144). Drop `--json-schema` (Claude puts structured output elsewhere). Rewrite `_invoke_claude_code` to mirror production sysadmin pattern at `scripts/sysadmin/bot.py::_run_claude` (`--model opus`, `--permission-mode bypassPermissions`, session-id + resume for warm cache, defensive JSON parse). |

**Operator directive captured** (memory + Lessons #14–17): no per-call $ caps on sysadmin-class agents — subscription is the budget; daily-cap + invocations-cap via the WAL kill-switch remain as soft circuit-breakers.

**Doc surface changes:**

- [`vps-complete-inventory.md`](vps-complete-inventory.md): container count 29 → 31; new "Signal → AI wake-up matrix" section documenting **which signals do/don't trigger AI today**, verified live (Prometheus via cron-fired `proactive-check.sh` is currently the only Alertmanager-style signal source wired to AI; Loki / Gatus / GlitchTip / Apprise / Backrest all route to Telegram-for-humans).
- [`vps-fleet-architecture.md`](vps-fleet-architecture.md): two-layer AI ops described (host sysadmin + per-project watchdog); gap explicitly flagged that **AI auto-action is vps1-only today** (no AI on spokes; no AI receiver in Alertmanager).
- [`vps-ai-sysadmin.md`](vps-ai-sysadmin.md): T-P5 row updated to "live end-to-end on vps1".

---

## 2026-06-02 evening — fleet hardening pass + image-broker retirement + T-P2 sidecar ships

End-to-end audit-prompt validation against live state surfaced + closed four fleet defects, plus shipped T-P2 sidecar artifacts 2-8 in `/opt/fabrik-lib/watchdog/sidecar/`.

**Live changes on vps1:**

- **SSH posture aligned with spokes.** `/etc/ssh/sshd_config.d/50-cloud-init.conf` had `PasswordAuthentication yes` (Ubuntu cloud-init drop-in) and was winning over the main `sshd_config` in alphabetical-glob order. Spokes already had `no`. Patched the drop-in to `no`, `sudo systemctl reload ssh`, verified `sshd -T` shows `passwordauthentication no` across all 3 hosts. Key-only auth verified in a fresh SSH session before relying on the change.
- **Hub Backrest `restic forget` lock contention fixed.** Three of four plans were failing the post-backup `forget` step nightly with "repository is already locked" — backups themselves ran fine but the pruning ran ~500ms after the backup lock was taken and conflicted. Added `--retry-lock=10m` to the `b2-vps1` repo `flags` in `/opt/backrest/config/config.json`; backrest container restarted. Confirmation deferred to next nightly window.
- **`.restic-password` mode 711 → 600** (spokes were already 600 — fleet-drift fix, single chmod).
- **Hub promtail now tags its own stream `host=vps1`.** Loki used to return only `["vps2","vps3"]` for the `host` label — hub stream was unlabelled because the static `host:` was missing from the `containers` scrape job. Added the label, restarted promtail, Loki now returns `["vps1","vps2","vps3"]`. Repo copy at `configs/promtail/promtail-config.yaml` synced (was drifted, also missing the Coolify-residue container-name drop rule).
- **`image-broker` spec retired.** Spec at `specs/services/image-broker.yaml` was orphaned — no `/opt/image-broker/`, no container, NXDOMAIN at Cloudflare; only the 2 Authelia rules survived from a prior registration. Removed the spec + `.fabrik/state/image-broker.json` + `infra/image-broker/` + 2 rows in PORTS.md + 3 script entries (`generate_vps_inventory.py`, `seed_real_ports.py`, `audit_all_projects.py`) + the 2 live Authelia rules. Authelia restarted via `docker restart authelia` → healthy. GlitchTip project id=66 left in place; safe to delete in the UI when convenient. LE cert in `acme.json` left to expire naturally (~90d). *(Current note 2026-07-20: `specs/services/image-broker.yaml` was later REGENERATED by `5caaa23b` — the spec exists again.)*

**Audit-prompt fixes** — patched bugs in 6 of 8 prompts after live-run validation: 01 (false-negative hub `.env` probe), 03 (grep leading-dash, cloud-init override visibility), 04 (`conntrack` not installed → `sysctl`), 05 (Loki via wrong network, Grafana fake-Bearer auth, GlitchTip wget-in-python-image), 06 (B2 repo name singular), 07 (hub SSH alias mapping, heredoc python parse, Authelia all-matches reporter), 08 (hub promtail filename). See `docs/infrastructure/audit-prompts/` for the per-file patches.

**T-P1 + T-P2 + T-P3 of the watchdog platform — COMPLETE 2026-06-03.** T-P2 (15/15 artifacts) ships in three layers: (a) sidecar at `/opt/fabrik-lib/watchdog/sidecar/` (~2,134 lines: agent state machine, llm_client Claude Code primary + OpenRouter fallback, actions 6 Tier A + 3 Tier B + 1 Tier C handlers, state.py SQLite with 4 tables, PreToolUse.sh hook, claude-settings template with 10-capability v1 lock, vendored cost_budget.py); (b) orchestrator wiring at `src/fabrik/orchestrator/infrastructure.py` (`_register_watchdog` resolver + dispatch, +63 lines) + driver at `src/fabrik/drivers/watchdog.py` (387 lines: vendor + render + build + compose overlay + bring-up); (c) operator-facing surface — emitter library at `/opt/fabrik-lib/watchdog/emitter/`, rule pack at `.windsurf/rules/core/60-watchdog.md`, fabrik-lib README modules-table row, test spec at `specs/services/watchdog-test.yaml`. T-P3 ships `.windsurf/rules/core/self-healing.md` (100 lines — 8-row escalation ladder + 5 anti-patterns + signup-flood worked example; lint MD060+MD032 clean). End-to-end verification via `spec_loader.load_spec` → `resolve_applicability` → `WatchdogDriver().provision(dry_run=True)` chain returns `{'status': 'dry-run', 'image_tag': 'fabrik/watchdog:watchdog-test'}`. 40/40 orchestrator tests green. **T-P5 sub-plan staged 2026-06-03** at [`do../development/plans/archived/2026-06-03-watchdog-P5-subplan.md`](../development/plans/archived/2026-06-03-watchdog-P5-subplan.md) — defensive sub-plan (parent plan said none needed; owner asked for one anyway since T-P5 touches live hub infra). r1 captures owner answers (`af2832a`): Sub-goal A (Traycer dogfood Steps 1–4) deferred, Step 9 postgres-main outage green-lit (no operational data at risk), `WATCHDOG_OPENROUTER_KEY` to land in `/opt/<project>/.env`, hub OOM risk retracted. Pre-T-P5 dependency surfaced in sub-plan §14: driver code-fix to add `env_file: ['.env']` to the watchdog service block in `_push_overlay` so operator-supplied vars in `/opt/<project>/.env` propagate to the sidecar container. **T-P4 COMPLETE 2026-06-03 — 13 / 13 P4.B edits shipped (subplan archived).** Universal-coverage overlay integrated into `02-epic-decomposition-command.md` (~84 inserted lines across E1+E13/E3/E4/E5/E6/E7/E8/E9/E10/E11/E12) and `03-expand-epic-files-command.md` (1 inserted line E14). Net edit ledger: sub-step 2h Universal Coverage Check + 14-row citation map + overlay-merge rule (`dc57f79`); pointers into Step 3 § External Services + § Auth Strategy (`5c82ec1`, `6fbf3b1`); 4 new Step 3 sub-sections — Self-Healing Ladder / Watchdog Wiring / Observability Defaults / Cost Guardrails (`5714917`, `b1dc651`, `f76fe21`, `d0c9d4d`); E6 self-review correction (`ce07ed6`); compact-entry shape +6 metadata + Universal categories (`fe0a822`); Output Contract item #6 (`1ff54c8`); 3 new Does NOT rows (`054d845`); 6 new Acceptance Criteria rows (`319eae1`); 1-line edit to 03 Metadata block closes the 02↔03 contract (`f3e34f7`). E2 dropped as no-op (pre-existing Step 3 § Database Strategy already covered category 3). Subplan archived to [`docs/development/plans/archived/2026-06-03-watchdog-P4-subplan.md`](../development/plans/archived/2026-06-03-watchdog-P4-subplan.md). **Watchdog program phases: T-P1 + T-P2 + T-P3 + T-P4 ✅ complete; T-P5 (dogfood E2E, 3 days, no sub-plan needed) ⏳ remaining.**

---

## 2026-06-02 — first end-to-end spoke deploy (W14 + W15 SHIPPED)

W14 fixed the deployer's env-routing so `inject_env` + compose rollback honor `ctx.target_vps`. W15 then defined the `gzip` Traefik middleware on each spoke (it had only ever existed on vps1, via a label on `meilisearch`). Together: the first-ever end-to-end spoke deploy succeeded.

**Live evidence (2026-06-02):**

- `fabrik apply specs/services/spoke-canary.yaml --target-vps vps2` → `✅ Deployment complete: https://canary.vps2.ocoron.com`.
- `curl -sS canary.vps2.ocoron.com` → HTTP 200.
- TLS chain: `Subject CN=canary.vps2.ocoron.com`, `Issuer=Let's Encrypt YR2`, `notAfter Aug 30 20:44:57 2026 GMT` — **first Let's Encrypt issuance on a spoke ever** (vps2's `/opt/traefik/acme.json` populated for the first time).
- `fabrik destroy --target-vps vps2` cleaned the container + compose dir; CF DNS A record deleted directly via CF API (DNS deprovision tripped on a pre-existing site-provisioner SSH-proxy bug).
- New `/opt/traefik/compose.yaml` on both spokes snapshotted into B2 via the host-state plan (count 4 → 5 per spoke).

**Spoke Traefik labels block now** (live state on both vps2 + vps3, in `/opt/traefik/compose.yaml`):

```yaml
services:
  traefik:
    # ... existing config ...
    container_name: traefik
    labels:
      - "traefik.enable=true"                                  # required because providers.docker.exposedByDefault=false
      - "traefik.http.middlewares.gzip.compress=true"          # publishes gzip@docker for orchestrator-emitted routers
    # ... rest unchanged ...
```

**W16 SHIPPED later the same day (2026-06-02), in two passes.**

- **Pass 1 — Traefik:** `bootstrap-vps.sh` gained `step_12_install_spoke_traefik()` driving 3 new templates under `scripts/bootstrap/templates/traefik*.template`. The compose template carries this exact `labels:` block; the existing DNS step renumbered to step 13. New `FABRIK_LE_EMAIL` constant in `bootstrap-config.sh`. `--verify` mode gained a Traefik row. Idempotency verified live by re-running step 12 against vps2: `Container traefik Running` (no recreate), uptime preserved.
- **Pass 2 — DNS:** `step_13_create_dns_records()` rewritten from stub to live caller. Probes the spoke's public IPv4 (`curl -4`), then SSHes to vps1 and POSTs `/api/cloudflare/dns/${FABRIK_DOMAIN_ROOT}/subdomain` twice (apex + wildcard). Idempotent via `ensure_record()` — re-runs return `action: unchanged`. The call goes via vps1 because (a) site-provisioner's IP allowlist includes vps1's public IP but not dev-WSL's, and (b) the production `API_KEY` stays on the VPS. `--verify` mode gained a DNS row that `dig`s the apex + a wildcard-probe FQDN against `1.1.1.1`. Live-verified against vps2 + vps3: all 4 calls returned `unchanged`.

A fresh `./scripts/bootstrap/bootstrap-vps.sh root@<new-ip> vpsN` now produces a spoke ready for `fabrik apply --target-vps vpsN` end-to-end: monitoring agents, Traefik with the W15 labels, public DNS, no `--skip-dns`.

---

## Today's significant changes (2026-05-31, full day)

### Afternoon batch

1. **Cloudflare API token refreshed** in `/opt/fabrik/.env` by syncing from the local site-provisioner's `.env` (pre-edit backup at `backups/.env.backup.20260531-155948`). Verified active via `https://api.cloudflare.com/client/v4/user/tokens/verify`.
2. **Spoke DNS records created** on Cloudflare (zone `ocoron.com`):
   - `vps2.ocoron.com` `A` 96.9.214.128
   - `*.vps2.ocoron.com` `A` 96.9.214.128
   - `vps3.ocoron.com` `A` 104.128.190.151
   - `*.vps3.ocoron.com` `A` 104.128.190.151
3. **site-provisioner interim stand-up** on vps1 — alembic migrations applied, `/health` 200, CF + Postgres connectivity verified.
4. **GitHub host-key trust** added to vps1's `/root/.ssh/known_hosts` (was missing — the Coolify removal cleanup wiped it).
5. **Permanent fixes in code:**
   - [`src/fabrik/orchestrator/deployer_ssh.py`](../../src/fabrik/orchestrator/deployer_ssh.py) — new `_extract_git_host()` + `ssh-keyscan` pre-step inside `_deploy_git()`. First-ever git-source deploy on a fresh host no longer trips on missing trust.
   - [`scripts/bootstrap/bootstrap-vps.sh`](../../scripts/bootstrap/bootstrap-vps.sh) — step_03 (after Docker install) now pre-seeds `github.com` into `/root/.ssh/known_hosts` on every new spoke.
6. **site-provisioner spec updated:** [`specs/services/site-provisioner.yaml`](../../specs/services/site-provisioner.yaml) now declares all 21 `${VAR}` references its upstream `compose.yaml` interpolates (13 env literals incl. `DATABASE_URL` placeholder + 9 from-env secrets). Was 13 → 22 declared vars.
7. **`/opt/fabrik/.env` secrets sync:** added `BING_WEBMASTER_API_KEY`; `API_KEY` overwritten with vps1's live value (preserves existing callers). Pre-edit backup at `backups/.env.backup.20260531-163701`.
8. **Postgres user `site_provisioner` password rotated** (32-char a-zA-Z0-9 via `secrets.choice`) — was unknown (not in fabrik state); now reflected in vps1's `/opt/site-provisioner/.env` and `DATABASE_URL`.

### Evening batch (residue cleanup + spoke-routing ship)

1. **Dry-run validate of `fabrik apply specs/services/site-provisioner.yaml`** — clean. State file shows 3 applicable registrars (`postgres`, `gatus`, `glitchtip`) all `status: "dry_run"`; container untouched; shape-gated registrars (`backrest`, `authelia`, `meilisearch`, `redis`, `prometheus`) correctly skipped. Pipeline is wired for site-provisioner.
2. **Residue cleanup pass** — `ContainerDown` alert silenced first (Lesson 11), 30-min sweep:
    - 6 stale CF A records deleted: `coolify`, `control`, `dns`, `fabrik-e2e-timing`, `images`, `netdata`.vps1.ocoron.com
    - 1 missing CF A record created: `provision.vps1.ocoron.com` (site-provisioner had a Traefik router but had never been in CF)
    - Authelia rule #6 trimmed from 10 hosts to 4 alive; rule #7 dropped `coolify.vps1`. Backup at `/opt/authelia/config/configuration.yml.bak.20260531-171950`. Authelia restarted via watcher in ~7 s.
    - Postgres orphan role `proxy_user` dropped.
    - Filesystem: `rm -rf /opt/prometheus`, `rm /opt/opt.code-workspace`.
    - UFW: deleted ports `6001/tcp` + `6002/tcp` (Coolify Realtime).
    - fabrik state: moved 6 orphan/test state files to `.fabrik/state/_destroyed/`.
    - Gatus: deleted 2 stale `.bak` config files.
3. **`fabrik apply --target-vps` shipped** (W-Multi M4). 5 source files + 2 test files:
    - [`src/fabrik/spec_loader.py`](../../src/fabrik/spec_loader.py) — new optional `target_vps: str | None` field on `Spec` (regex `^vps[1-9][0-9]?$`)
    - [`src/fabrik/orchestrator/context.py`](../../src/fabrik/orchestrator/context.py) — new `target_vps: str = "vps1"` on `DeploymentContext`
    - [`src/fabrik/orchestrator/__init__.py`](../../src/fabrik/orchestrator/__init__.py) — `deploy()` accepts `target_vps` kwarg (CLI > spec > "vps1"); `_provision_dns` resolves IP via `VPS_IPS = {"vps1": "172.93.160.197", "vps2": "96.9.214.128", "vps3": "104.128.190.151"}`. `target_vps` wins over the legacy `VPS_IP` env var.
    - [`src/fabrik/orchestrator/deployer_ssh.py`](../../src/fabrik/orchestrator/deployer_ssh.py) — `_target_vps_env(ctx)` contextmanager env-swaps `FABRIK_VPS_SSH_HOST` when `target_vps != "vps1"`, restoring on exit. Applied around (1) `SSHDeployer.deploy()` (W-Multi M4 2026-05-31), (2) `SSHDeployer.inject_env()` so post-deploy DSN / Redis-URL writes on spoke apps land on the spoke (W14 2026-06-02), and (3) `RollbackManager._rollback_compose()` via `resource.metadata["target_vps"]` so a failed verify on a spoke tears the container down on the spoke (W14 2026-06-02). Hub-side registrars (gatus, postgres-main, authelia on vps1) run **outside** this scope on purpose and keep talking to vps1.
    - [`src/fabrik/cli.py`](../../src/fabrik/cli.py) — new `--target-vps [vps1|vps2|vps3]` option on `apply`, threaded into orchestrator.
    - [`tests/orchestrator/test_deployer_ssh.py`](../../tests/orchestrator/test_deployer_ssh.py) — 3 new tests for env-swap behavior; 3 fixes for pre-existing-test drift (rename + ssh-keyscan).
    - [`tests/orchestrator/test_integration.py`](../../tests/orchestrator/test_integration.py) — DNS test updated for new VPS_IPS map precedence.
    - **103/103** deployer/spec tests pass.

---

## site-provisioner status

**Running:** container `site-provisioner` on vps1, up (RestartCount=1 since the 2026-07-08 reboot). Migrations applied; CF + DB connectivity ok. `/health` returns 200 **when it completes**, but its live Cloudflare+Postgres+Namecheap checks occasionally exceed the 10s healthcheck timeout, so Docker health **flaps** unhealthy→healthy without restarting (verified live 2026-07-13). App-level `RuntimeError: No response returned` (~36×/24h) is tracked in the `mobasak/site-provisioner` repo, not here.

**But not pipeline-ready.** This is an interim manual stand-up done specifically to unblock today's spoke DNS work. Gaps remaining:

| Gap | Today's mitigation | What's still needed |
| :--- | :--- | :--- |
| Upstream `mobasak/site-provisioner@main` `compose.yaml` `coolify` → `fabrik` network rename | **RESOLVED 2026-05-31 evening** (commit `fa32d61`, pushed to `main`). Verified live on vps1 2026-06-02: `compose.yaml` declares `networks: [fabrik]`, no `coolify` references. | none |
| Spec was missing 3 secrets + 5 env literals | Updated, parses cleanly | One clean `fabrik apply` end-to-end after the push above to confirm |
| Postgres user password not in fabrik state | Manually set + reflected in live `.env`; `DATABASE_URL` works | The postgres registrar will overwrite this cleanly on the next full `fabrik apply` cycle |

**Safe restart** (does NOT exercise the pending end-to-end pipeline gate):

```bash
ssh vps "cd /opt/site-provisioner && sudo docker compose up -d"
```

A full `fabrik redeploy site-provisioner` would now `git pull` a `fabrik`-network compose cleanly (rename pushed 2026-05-31 evening), but the round-trip itself has not yet been exercised against state — gated on operator authorization since the postgres registrar would rotate the DB password.

---

## Containers — per host

### vps1 (29 running)

```text
site-provisioner       up/flapping  (interim manual; healthcheck intermittently times out then self-recovers — see § site-provisioner status)
authelia               healthy
glitchtip-web          running  (bound to 10.99.0.1:8000 for spoke ingest)
glitchtip-worker       running
redis-main             healthy  (bound to 10.99.0.1:6379)
postgres-main          healthy  (bound to 10.99.0.1:5432)
postgres-exporter      healthy
redis-exporter         running
loki                   healthy  (bound to 10.99.0.1:3100)
promtail               running
prometheus             healthy
alertmanager           healthy
grafana                healthy
gatus                  running
cadvisor               healthy
node-exporter          running
pushgateway            healthy
apprise                healthy
backrest               running  (4 plans live: postgres-dumps + docker-volumes + opt-configs + host-state; first snapshot 2026-06-01, W2)
n8n                    running
gotenberg              running
browserless            running
meilisearch            running
traefik                running
ocoron-com-nginx-1     running    (WP tenant)
ocoron-com-wordpress-1 running    (WP tenant)
ocoron-com-db-1        healthy    (WP tenant — MariaDB)
ocoron-com-redis-1     healthy    (WP tenant)
ocoron-com-backup-1    running    (WP tenant — nightly mysqldump sidecar)
```

### vps2 (5 running)

```text
traefik                running  (public 80+443; authelia-vps1@file middleware ready)
node-exporter          running  (10.99.0.2:9100)
cadvisor               healthy  (10.99.0.2:8080)
promtail               running  (10.99.0.2:9080 → pushes to 10.99.0.1:3100)
backrest               running  (W11 — own restic repo at b2:vps1-ocoron-backups/spokes/vps2/; 2 plans: host-state + opt-configs)
```

### vps3 (5 running)

```text
traefik                running
node-exporter          running  (10.99.0.3:9100)
cadvisor               healthy  (10.99.0.3:8080)
promtail               running  (10.99.0.3:9080)
backrest               running  (W11 — own restic repo at b2:vps1-ocoron-backups/spokes/vps3/; 2 plans: host-state + opt-configs)
```

---

## Network posture (per host)

### vps1

| Layer | Status |
| :--- | :--- |
| SSH | ✅ `ozgur` user, Ed25519 key only, root disabled, password disabled, fail2ban active |
| UFW | ✅ active; 22 / 80 / 443 / 1194 ALLOW; 51820/udp ALLOW; 8000 DENY (stale Coolify comment) |
| Mesh-only ports | ✅ `10.99.0.1:5432,6379,8000,9091,3100` listening on wg0 only |
| DOCKER-USER iptables chain | ✅ accepts `wg0`, drops mesh-only port list from public iface |
| Traefik dashboard | ✅ `127.0.0.1:8080` localhost only |
| Authelia | ✅ forward-auth on `*.vps1.ocoron.com` admin dashboards; TOTP 2FA; Redis-backed sessions (`redis-main:6379/3`) |
| M2M auth | 🟡 pattern intact (`X-Internal-Token` + `SERVICE_INTERNAL_SECRET_KEY`); **no live service consuming it** today — the 6 microservices that used it are not currently deployed (the 7th, image-broker, was retired 2026-06-02) |
| GitHub host-key trust for root SSH | ✅ added today (`/root/.ssh/known_hosts`) — deployer + bootstrap now keep this in place automatically |
| Resource limits | ✅ enforced via compose `deploy.resources.limits.memory` on every service; gate validates |

### vps2 / vps3 (identical posture)

**Last probe report:** [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml) (post-W14 sweep)

| Layer | Status |
| :--- | :--- |
| SSH | ✅ matches vps1 (no root, no password, `ozgur` key only) — Lesson 65 takeaway |
| UFW | ✅ installed (`dpkg ii`) + active; 8 ALLOW rules (22/80/443/51820 IPv4+IPv6); default policy `deny (incoming) / allow (outgoing) / deny (routed)` — shipped by W1 2026-05-31 evening; pre-W1 was `rc` state (Lesson 68) |
| Mesh-only ports | ✅ `10.99.0.<N>:9100,8080,9080` listening on wg0 only; mesh-only port DROP verified via tcpdump (SYN arrives, no SYN-ACK) |
| Promtail gRPC | 🟡 binds `*:<random>` (`promtail.yaml: grpc_listen_port: 0`) — observed `*:38969` (vps2) / `*:44987` (vps3) at 2026-06-01T00-14Z probe. **UFW shields it** (default deny on 1–65535 except 22/80/443/51820), so not internet-reachable. Pin to a known port or `127.0.0.1` if a future audit needs determinism. |
| DOCKER-USER chain | ✅ applied by bootstrap step_10; unchanged by W1 (probe: 2 rules each host) |
| Traefik | ✅ public 80 + 443, `authelia-vps1@file` middleware in `dynamic/authelia.yml` |
| Tenants | None yet (DNS ready) |

---

## Observability snapshot

### Prometheus — 17 `job_name`s configured / 16 active (`fabrik-services` null-target; `pushgateway` restored `b8071f40` 2026-07-19; repo re-verified 2026-07-20; prior live probe 2026-07-12: 20/20 targets up) ( Spoke federation `node-spokes` / `cadvisor-spokes` / `promtail-spokes` IS live — 2 targets each)

vps1-local (11 jobs / 11 targets — re-verified against `/api/v1/targets` 2026-07-12): `alertmanager`, `authelia`, `cadvisor`, `gatus`, `grafana`, `loki`, `meilisearch`, `node`, `postgres`, `prometheus`, `redis`. (`pushgateway` runs as a container but is NOT a scrape job; `fabrik-services` is configured with null targets — a placeholder.) Plus `aro-wake` (3 targets) and the spoke federation `node-spokes` / `cadvisor-spokes` / `promtail-spokes` (2 targets each). So 16 job_names configured → 15 active at that probe. **Current repo config (2026-07-20): 17 `job_name`s / 16 active — `pushgateway` scrape RESTORED `b8071f40` 2026-07-19** (it is no longer an unscraped container).

Spoke scrape jobs (`node-spokes`, `cadvisor-spokes`, `promtail-spokes`) — **live in `prometheus.yml`** (`:46,:58,:70`; re-verified 2026-07-12 via `/api/v1/targets`: 2 targets each, all up). They scrape the spoke-side `node-exporter`/`cadvisor`/`promtail` agents at `/opt/monitoring-agent/` over the mesh (the `ufw allow from 10.99.0.0/24` rule from W8 is in place via `bootstrap-vps.sh` step_02). The `aro-wake` job (3 targets: vps1:10.0.1.1:8201, vps2:10.99.0.2:8201, vps3:10.99.0.3:8201) adds SLI/health metrics on top. Loki side: promtail push-based ingest works — Loki has `host=vps1|vps2|vps3` log streams (verified 2026-06-07T20:20Z).

Not scraped: `traefik` (no metrics scrape job — health observed via Gatus + Loki), `glitchtip-web` (django-prometheus not bundled). Every active series carries a `host` label (`vps1`, `vps2`, or `vps3`). Reload: `ssh vps "sudo docker kill -s HUP prometheus"`.

### Retention

| Datastore | Retention | Configured via |
| :--- | :--- | :--- |
| Prometheus | 30 d or 5 GB | `--storage.tsdb.retention.time=30d --storage.tsdb.retention.size=5GB` |
| Loki | 7 d (168 h) | `limits_config.retention_period: 168h` + compactor enabled |
| Alertmanager | minutes | — |

### Loki — multi-host ingest

- Bound to `10.99.0.1:3100` on vps1 (mesh ingest).
- Both spokes' promtail successfully pushing — `host` label values `["vps1","vps2","vps3"]` visible in Grafana's Loki explore.

### Grafana

- 5 Fabrik-folder dashboards (overview, databases, containers, authelia, meilisearch) — all carry a `$host` template variable (regex `/^vps/`) so you can scope spoke vs hub.
- Datasources provisioned from `/opt/monitoring/configs/grafana/provisioning/datasources/fabrik.yaml`.

### Alerting

- **Alertmanager → Telegram (native `telegram_configs`)** + webhook → `aro-wake` for vps1 alerts. Apprise is **not** in Alertmanager's path (it serves Gatus + the sysadmin scripts).
- ~~`spoke_health` rule group active — `SpokeDown`, `SpokeHighCPU`, `SpokeHighRAM`~~ — **NOT in `alerts.yml` as of 2026-06-07T20:20Z probe**. The 5 actual live groups: `aro_wake` (2 rules), `container_health` (6), `host_health` (3), `service_health` (1), `fabrik-registrar-drift` (1, lives in separate `rules/fabrik-drift.yml`). `host_health` does fire on `host=vps2|vps3` labels so spoke-level CPU/RAM/down alerting still works through those rules; the dedicated spoke-named group never landed.
- **Discipline (Lesson 11):** silence the `ContainerDown` rule before any planned op that takes containers down > 2 min, or Telegram floods.

### GlitchTip

- Public UI: `https://errors.vps1.ocoron.com` (Authelia 2FA).
- Internal alias for SDKs: `http://glitchtip-web:8000/<project_id>` (Docker DNS on `fabrik` network).
- Mesh ingest for spoke tenants: `http://10.99.0.1:8000/<project_id>` (bound today).
- Storage: `glitchtip` DB on `postgres-main`; events retained 90 d.
- Project IDs unchanged from Coolify-era audit (captcha 65, translator 67, emailgateway 68, file-api 69, file-worker 70, site-provisioner 24). Project id=66 was for image-broker, orphaned after the 2026-06-02 spec removal (spec since regenerated by `5caaa23b`) — the GlitchTip project remains deletable in the UI.

### Gatus

- Status page: `https://status.vps1.ocoron.com` (public, no auth).
- Config tree at `/opt/monitoring/configs/gatus/` (volume-mounted, auto-reloads ~30 s).
- Stable container names everywhere — no more UUID-alias maintenance.
- Alerter: native `failure-threshold: 3`, `success-threshold: 2`, `send-on-resolved: true` → Apprise → Telegram.

---

## Authelia — 8 access-control rules (live, verified via `yaml.safe_load` 2026-06-02 evening)

| # | Policy | Domain(s) | Resources |
| :--- | :--- | :--- | :--- |
| 1 | bypass | `ocoron.com` | (all) |
| 2 | bypass | `www.ocoron.com` | (all) |
| 3 | bypass | `wp-test.vps1.ocoron.com` | (all) |
| 4 | bypass | `status.vps1.ocoron.com` | (all) |
| 5 | bypass | `*.vps1.ocoron.com` | `^/health$`, `^/healthz$`, `^/metrics$`, `^/api/health$` |
| 6 | bypass | `pdf`, `browser`, `search`, `errors`.vps1.ocoron.com (4 hosts) | (all) |
| 7 | bypass | `monitor.vps1.ocoron.com` | `^/api/` only |
| 8 | two_factor | `*.vps1.ocoron.com` | (catch-all for everything else) |

**Cleanup history:**

- 2026-05-31 evening — rule #6 went 10 hosts → 4 hosts (dropped dead microservice subdomains + stale `dns` alias); rule #7 dropped `coolify.vps1.ocoron.com` (Coolify removed 2026-05-30).
- 2026-06-02 evening — removed the 2 `images.vps1.ocoron.com` rules (bypass `^/api/` + 2FA catch-all) after the image-broker spec was retired. Rule count 10 → 8.

**Cosmetic-but-noteworthy:**

- Rule #6 includes `errors.vps1.ocoron.com` — GlitchTip UI is reachable without Authelia. A prior session note claimed T2-08 Part A removed it; the change never landed and after review it stays (GlitchTip is a public error-report UI used cross-tenant). Move it out of #6 into the `two_factor` catch-all later if you want 2FA in front of it.
- `provision.vps1.ocoron.com` (site-provisioner) is NOT in this list — it's protected at the Traefik layer by IP allowlist + at the app layer by bearer `API_KEY`, never reaches Authelia.

**Critical:** Authelia **exits** on SIGHUP — it does NOT hot-reload. The systemd watcher `authelia-config-sync.service` saves config to the named volume and `docker restart authelia` automatically on edit. Manual restart: `ssh vps "sudo docker restart authelia"`.

**Cross-host SSO for spoke admin dashboards** (when they exist): spoke Traefik uses the `authelia-vps1@file` middleware to forward-auth via mesh (`http://10.99.0.1:9091/api/verify`). Cookie-domain plumbing for true SSO across hosts is W-Multi M7 backlog.

---

## Backups

**Live state (re-verified 2026-06-15/16):** the fleet runs an active backup chain — **vps1 hub has 4 plans, vps2 + vps3 spokes have 2 plans each** (matches the "Fleet at a glance" Backrest rows above). B2 bucket `vps1-ocoron-backups` is **NOT empty** — first snapshots total ~117 MiB compressed. First real backup chain since the 2026-05-31 wipe.

| Host | Repo ID | Repo URI / path | Plans |
| :--- | :--- | :--- | :--- |
| vps1 (hub) | `b2-vps1` | `s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups` | **4** — `postgres-dumps` (02:00), `docker-volumes` (03:00), `opt-configs` (03:00), `host-state` (03:30) |
| vps2 (spoke) | `b2-vps2` | `vps1-ocoron-backups/spokes/vps2/` | **2** — `host-state` (02:00), `opt-configs` (02:30) |
| vps3 (spoke) | `b2-vps3` | `vps1-ocoron-backups/spokes/vps3/` | **2** — `host-state`, `opt-configs` (same schedule as vps2) |

| Item | Detail |
| :--- | :--- |
| Repo flags | `--compression=auto` |
| Container | `backrest` (running, 512 MB limit) |
| Off-VPS creds in `/opt/fabrik/.env` | `BACKREST_RESTIC_PASSWORD` ✓, `B2_KEY_ID` ✓, `B2_APPLICATION_KEY` ✓ |

Closing the "credentials only on vps1" DR weakness means the dev WSL can stand backups back up from scratch.

**Credential off-site mirror (W9 shipped 2026-06-01).** The dev WSL was itself a single point of failure until W9: `/opt/fabrik/.env` (including the irrecoverable `BACKREST_RESTIC_PASSWORD`) existed only on disk there. Now mirrored to **`mobasak/fabrik-dr-store`** (private GitHub repo) within seconds of every change via `fabrik-dr-watcher.service` (inotify) + daily safety-net cron + `@reboot` catch-up + weekly recovery self-test. One-command recovery on a fresh WSL: `gh repo clone mobasak/fabrik-dr-store && sudo cp fabrik-dr-store/env/latest /opt/fabrik/.env`. Full runbook: [`docs/operations/credential-recovery.md`](../operations/credential-recovery.md).

Operating notes (recorded when the chain was stood up):

- vps1 plans in place: `postgres-dumps` (`/opt/backups/pg_dump_*.sql`), `docker-volumes` (`/var/lib/docker/volumes/`), `opt-configs` (`/opt/<svc>/{compose.yaml,.env}`), `host-state`. Spoke plans: `host-state` + `opt-configs`.
- Failure-hook URL: `http://apprise:8000/notify/alerts` — Apprise's **stateful** endpoint (config key `alerts`), emitted by `src/fabrik/drivers/backrest.py`. There is no `/notify/<tag>` convention; the bare stateless `/notify` (`APPRISE_STATELESS_URLS`) is used only by n8n. The Coolify-era `apprise-<uuid>` hostname is gone from live configs (verified 2026-07-12).
- `postgres-dumps` runs AFTER the host pg_dump cron, not concurrent (44 % race-condition failures previously).
- Spoke backups now cover `host-state` + `opt-configs`; broaden only if vps2/vps3 start holding non-replicated data.

---

## Recent maintenance & lessons (active)

| # | Source | Rule |
| :--- | :--- | :--- |
| 11 | Lesson 11 | Silence `ContainerDown` before any planned downtime > 2 min on vps1, otherwise Telegram floods |
| 22 | Lesson 22 | Container names are stable across all hosts (`container_name:` in every compose) — no UUID-alias maintenance |
| 31 | Lesson 31 | Env-var verification on distroless images uses `docker inspect`, never `docker exec printenv` |
| 36 | Lesson 36 | git-source `fabrik redeploy` pulls from the GitHub remote, not your local `/opt/`. Push first, then redeploy. |
| 50 | Lesson 50 | `SourceType.LOCAL` exists in 13 production specs — the SSH deployer handles it explicitly (was being silently coerced to TEMPLATE under Coolify) |
| 62 | Lesson 62 | Coolify had 3 deployment types with different fix paths; SSH deployer has 1 (compose). Confirmed simplification. |
| 64 | Lesson 64 | Live-state probes are authoritative — re-verify on the actual VPS after implementation, don't trust paper-correct |
| 65 | Lesson 65 | bootstrap-vps.sh bugs from initial vps2/vps3 deploys — create sudoer first, scan multiple SSH key candidates, no process substitution over SSH |
| — | Today | Spec-vs-upstream `compose.yaml` interpolation: every `${VAR}` in the upstream compose must be declared in the spec's `env` or `secrets.from_env` — otherwise `docker compose up` fails before the container starts |
| — | Today | First-ever git-source deploy on a fresh host needs the git host in `/root/.ssh/known_hosts`. Deployer + bootstrap now keep this in place; not something to handle manually anymore. |

Full log: [`docs/LESSONS_LEARNT.md`](../LESSONS_LEARNT.md).

---

## Maintenance commands

```bash
# Full health + residue audit
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# After VPS reboot — reapply memory limits
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Restart Authelia after config edit (NEVER SIGHUP)
ssh vps "sudo docker restart authelia"

# Reload Prometheus config
ssh vps "sudo docker kill -s HUP prometheus"

# Spoke health snapshot
for host in vps vps2 vps3; do
  echo "=== $host ==="
  ssh "$host" 'sudo docker ps --format "{{.Names}}\t{{.Status}}" | head -10; uptime; df -h / | tail -1'
done

# Weekly disk cleanup per host
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"
```

---

## Known issues / residue (active)

After the evening cleanup batch, the active list is short. The struck-through rows are kept for one snapshot so a reader sees what was just fixed.

| # | Issue | Impact | Fix path |
| :--- | :--- | :--- | :--- |
| 1 | ~~Backrest failure hook references the old Coolify-era apprise UUID hostname~~ — **RESOLVED 2026-07-12** | Live hooks use `http://apprise:8000/notify/alerts`. A deeper break (Apprise had no `alerts` stateful config → `204` silent-drop of ALL alerts) was also fixed 2026-07-12 | None — verified delivering (`200`) |
| 2 | `errors.vps1.ocoron.com` remains in Authelia bypass rule #6 (intentional — GlitchTip is the cross-tenant error UI) | GlitchTip UI is reachable without 2FA | Accepted as intentional; move to `two_factor` if/when this changes |
| ~~3~~ | ~~`/opt/prometheus/` on vps1~~ | **RESOLVED** evening | `rm -rf` |
| ~~4~~ | ~~site-provisioner upstream `compose.yaml` says `coolify` network~~ | **RESOLVED** | `fa32d61` pushed to `mobasak/site-provisioner@main` |
| ~~5~~ | ~~Stale UFW 6001, 6002 (Coolify Realtime)~~ | **RESOLVED** evening | `ufw delete allow {6001,6002}/tcp`; 8000 DENY rule kept as belt-and-suspenders |
| ~~6~~ | ~~6 stale `*.vps1` DNS A records~~ | **RESOLVED** evening | Deleted via CF API |
| ~~7~~ | ~~Authelia rule #6 lists 5 dead microservice domains + `dns`~~ | **RESOLVED** evening | Trimmed to 4 alive (`pdf`, `browser`, `search`, `errors`) |
| ~~8~~ | ~~Authelia rule #7 bypasses `coolify.vps1`~~ | **RESOLVED** evening | Dropped; rule #7 now only `monitor.vps1` |
| ~~9~~ | ~~Orphan Postgres role `proxy_user`~~ | **RESOLVED** evening | `DROP USER` done |
| ~~10~~ | ~~Stray `/opt/opt.code-workspace`~~ | **RESOLVED** evening | Deleted |
| ~~11~~ | ~~6 orphan fabrik state files~~ | **RESOLVED** evening | Moved to `.fabrik/state/_destroyed/` |
| ~~12~~ | ~~2 stale `.bak` Gatus configs~~ | **RESOLVED** evening | Deleted |

(Issue 4 — Cloudflare token invalid — from earlier docs is RESOLVED. The struck-through rows will drop from this table in the next snapshot.)

---

## Pending work (high-level)

The full table lives in [`vps-complete-inventory.md` § Pending actions](vps-complete-inventory.md). Current top of stack after today's evening batch:

1. **T-P2 Watchdog Platform — 13 of 15 artifacts remaining.** Artifacts 1 (`WatchdogConfig` spec field, including the 3-field amendment locked during artifact 2 review: `deadman_timeout_seconds`, `external_docs_enabled`, `propose_fix_prs`) + 2 (`claude-settings.json.template` with the 10-capability v1 lock) both shipped 2026-06-02. Next: artifact 3 (`hooks/PreToolUse.sh`). Subplan + capability matrix: [`do../development/plans/archived/2026-05-30-ai-watchdog-platform-P2-subplan.md`](../development/plans/archived/2026-05-30-ai-watchdog-platform-P2-subplan.md) § 4.6.
2. **Authelia rules for spoke admin dashboards** (when one exists — registrar is already FQDN-pattern-agnostic per W13 verify).
3. **Spoke tenant backups** (`docker-volumes-vpsN` + `postgres-dumps-vpsN` plans on spoke Backrest — gated on first actual tenant data landing).

---

## Verification log

### Probe report — 2026-06-07T20-20Z (end-of-iteration-day)

Generated by `scripts/audit_infra_vs_docs.py --hosts vps,vps2,vps3` after the 2026-06-07 work landed. Source YAML: [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml).

| Probe | vps1 | vps2 | vps3 |
| :--- | :--- | :--- | :--- |
| container_count | 31 (29 platform + 2 T-P5 dogfood) | 5 | 5 |
| ufw_installed | ufw | ufw | ufw |
| ufw_active | active | active | active |
| ufw_rule_count_v4 | 7 (5 baseline + 2 aro-wake `8201` allows since 2026-06-05 + 1 wg0→wg0 routed-allow since 2026-06-06) | 6 (4 baseline + 2 aro-wake `8201` allows) | 6 (same as vps2) |
| ufw_rule_count_numbered (v4+v6) | 16 | 11 | 11 |
| fail2ban_active | active | active | active |
| fail2ban_total_ban | 150 | 158 | 99 |
| listening_public | `0.0.0.0:1194,:22,:443,:80,:8201` | `*:33245,0.0.0.0:22,:443,:80,:8201` | `*:37509,0.0.0.0:22,:443,:80,:8201` |
| listening_mesh | `10.99.0.1:3100,:5432,:6379,:80,...` (truncated in YAML) | `10.99.0.2:8080,:9080,:9100` | `10.99.0.3:8080,:9080,:9100` |
| docker_user_rules | 1 | 2 | 2 |
| iptables_backend | iptables-nft | iptables-nft | iptables-nft |
| wg_peers_alive | 2 | 1 | 1 |
| kernel | 6.8.0-117-generic | 6.8.0-63-generic | 6.8.0-63-generic |
| uptime_s | 687590 (~8 days) | 636557 (~7.4 days) | 636596 (~7.4 days) |
| disk_root_pct | 29 | 13 | 13 |
| ram_used_mb / total | 4068 / 11913 | 1261 / 7894 | 1207 / 7894 |
| docker_network_fabrik | fabrik | fabrik | fabrik |

Notable deltas since the 2026-06-06T22-39Z probe (24h before):

- All container counts stable (31/5/5) — no new services landed today.
- vps1 UFW gained `8201/tcp ALLOW IN 10.0.0.0/8` + `8201/tcp ALLOW IN 10.99.0.0/24` rules (2026-06-05 retroactive — these were added when aro-wake's Phase 4 wire shipped). Live ufw_rule_count_numbered=16 reflects: 7 v4 + 1 routed v4 + 6 v6 mirrors + 1 v6 routed + 1 IPv6 forward rule.
- vps1 RAM: 4068 / 11913 MiB (35% used) — up slightly from 4019 prior, normal drift.
- vps1 disk: 29% used — up slightly from 27% (slow growth from container logs + observability data).
- fail2ban total bans: 150/158/99 — slowly climbing on all 3 hosts (background internet scanner noise).

### Probe report — 2026-06-01T22-50Z (post-W14) — HISTORICAL SNAPSHOT

Generated by `scripts/audit_infra_vs_docs.py`. Captured after W14 shipped + spoke-canary live-verify on vps2 (deployed healthy, verifier 404 from W15 gap, rollback clean). Kept here for the historical-delta chain.

| Probe | vps1 | vps2 | vps3 |
| :--- | :--- | :--- | :--- |
| container_count | 29 | 5 | 5 |
| ufw_installed | ufw | ufw | ufw |
| ufw_active | active | active | active |
| ufw_rule_count_v4 | 5 | 4 | 4 |
| fail2ban_active | active | active | active |
| fail2ban_total_ban | 891 | 73 | 72 |
| listening_public | `0.0.0.0:1194,:22,:443,:80` | `*:33245,0.0.0.0:22,:443,:80` | `*:37509,0.0.0.0:22,:443,:80` |
| listening_mesh | `10.99.0.1:3100,:5432,:6379,:80,...` (truncated in YAML) | `10.99.0.2:8080,:9080,:9100` | `10.99.0.3:8080,:9080,:9100` |
| docker_user_rules | 1 | 2 | 2 |
| iptables_backend | iptables-nft | iptables-nft | iptables-nft |
| wg_peers_alive | 2 | 1 | 1 |
| kernel | 6.8.0-117-generic | 6.8.0-63-generic | 6.8.0-63-generic |
| disk_root_pct | 27 | 11 | 11 |
| ram_used_mb / total | 3936 / 11913 | 876 / 7894 | 851 / 7894 |
| docker_network_fabrik | fabrik | fabrik | fabrik |

Notable deltas since the 21-59Z probe earlier the same day:

- vps2 + vps3 container counts rose 4 → 5 — `backrest` per spoke (W11 first verified live here).
- vps1 dropped `:8017` from `listening_public` permanently — W5 remediation now durable across reboots.
- fail2ban totals climbed (493 → 891 hub; 17 → 73 / 25 → 72 on spokes) — passive scanner background, no platform impact.

> The earlier "fail2ban_total_ban: 891" peak on 2026-06-01 has since RESET (current 2026-06-07 = 150) — likely due to vps1 hub reboot or fail2ban service restart that cleared the in-memory counter. fail2ban's banned-IP history is not persisted.

### Probe report — 2026-06-01T00-14Z

### External-exposure probe — 2026-06-01T00:43Z (W5)

Run from off-mesh source `vps2` (Coventry UK) because the dev-WSL exit (Türk Telekom AS9121, IP `176.219.28.59`) returned **false-positive TCP "succeeded" reads on `:8017`** when the bind was already `127.0.0.1` only. Cross-checked against vps3: timeouts. **Lesson 72:** never trust TTNet for TCP-state probes — confirmed SYN-ACK middlebox on assorted ports. Use a clean-AS off-mesh node (vps2 / vps3 / GitHub Actions) for authoritative external probing.

#### `:8017` (vps1 sysadmin-bot health) — remediated

Pre-remediation: bound `0.0.0.0:8017`, externally TCP-reachable. Patched [`scripts/sysadmin/bot.py`](../../scripts/sysadmin/bot.py) to honor a new `SYSADMIN_HEALTH_HOST` env var (default `127.0.0.1`). Mirrored on vps1 (backed up to `/opt/fabrik/backups/bot.py.backup.20260601-033756` first), service restarted, post-remediation socket:

```text
$ ssh vps 'sudo ss -tnlp | grep ":8017"'
LISTEN 0  5  127.0.0.1:8017  0.0.0.0:*  users:(("python3",pid=1509156,fd=3))
```

External re-probe from vps2 + vps3 (clean AS, off-mesh):

```text
# from vps2 (96.9.214.128 → 172.93.160.197:8017)
$ timeout 5 nc -zv 172.93.160.197 8017 2>&1 | head -1
nc: connect to 172.93.160.197 port 8017 (tcp) failed: Connection timed out

# from vps3 (104.128.190.151 → 172.93.160.197:8017)
$ timeout 5 nc -zv 172.93.160.197 8017 → exit 124 (timed out, no output)

# from vps1 to its OWN public IP (kernel routes via lo, hits no listener)
$ curl -sS -m 5 http://172.93.160.197:8017/health
curl: (7) Failed to connect to 172.93.160.197 port 8017 after 0 ms: Couldn't connect to server
```

Local-loopback from vps1 itself still returns `{"status": "ok", ...}` ✅. No Gatus endpoint, Prometheus job, or `/etc/cron.d/` entry depended on the public bind (the "for Gatus monitoring" comment in bot.py was aspirational, never wired — `/opt/monitoring/configs/gatus/` searched: 0 hits; `/etc/cron.d/` searched: 0 hits).

#### Tcpdump forensic — Lesson 72 confirmed at 2026-06-01T04:00:42Z

Captured on vps1 (`tcpdump -i any -nn 'tcp port 8017 and host 176.219.28.59'`) while the dev-WSL ran `nc -zv` + `curl` in the same second:

```text
04:00:42.750325 ens3  In  IP 176.219.28.59.12701 > 172.93.160.197.8017: Flags [S], seq 340446579, win 65535
04:00:42.813219 ens3  In  IP 176.219.28.59.12639 > 172.93.160.197.8017: Flags [S], seq 4162728737, win 65535
```

**Two inbound SYNs, zero outbound SYN-ACK from vps1.** The kernel correctly refused (no listener on the public IP). Yet dev-WSL's `nc` reported `Connection ... succeeded!`. The SYN-ACK that nc saw **cannot have come from vps1** — it was injected by an upstream middlebox on the TTNet path. This is the forensic basis of Lesson 72.

#### Mesh-only ports — externally unreachable on all 3 hosts

Paced probe (3 s timeout, 0.5 s inter-port, 1 s inter-host) from vps2 against 9 ports × 3 hosts = **27 probes; 0 connects.** Raw per-host breakdown:

```text
=== W5 step 3 mesh-port probe — 2026-06-01T00:43:42Z — source: vps2.ocoron.com ===
--- vps1 (172.93.160.197) ---     all 9 ports: timed out (filtered)   ← DROP at DOCKER-USER + UFW deny
  :5432, :6379, :8000, :9091, :3100, :9090, :9100, :8080, :7700  →  timed out
--- vps2 (96.9.214.128) ---       all 9 ports: refused (RST from own kernel — no listener on public IP)
  :5432, :6379, :8000, :9091, :3100, :9090, :9100, :8080, :7700  →  Connection refused
--- vps3 (104.128.190.151) ---    all 9 ports: timed out (filtered)
  :5432, :6379, :8000, :9091, :3100, :9090, :9100, :8080, :7700  →  timed out
Summary: 0 connect(s) — expect 0
```

Any future regression that surfaces a "succeeded" line here is a security defect — re-run [`/tmp/w5_mesh_probe.sh`](../../scripts/audit_infra_vs_docs.py) (script body archived in convergence log v3.6 → v3.7) from vps2 to reproduce.

#### UFW IPv4/IPv6 rule mirror — port-by-port match

```text
vps1:  v4 = {22, 80, 443, 1194, 8000-DENY, 51820}    v6 = {22, 80, 443, 1194, 8000-DENY, 51820}    MATCH (6/6)
vps2:  v4 = {22, 80, 443, 51820}                     v6 = {22, 80, 443, 51820}                     MATCH (4/4)
vps3:  v4 = {22, 80, 443, 51820}                     v6 = {22, 80, 443, 51820}                     MATCH (4/4)
```

vps1's v6 row for `443/tcp` carries the comment `# HTTPS+OpenVPN`; the "+OpenVPN" is a stale annotation (port 443 is HTTPS only — OpenVPN binds 1194). Comment-only drift; rule is correct.

#### Fail2ban hygiene

Probe-source IP `176.219.28.59` not banned on any host post-probe:

```text
ssh vps  'sudo fail2ban-client status sshd | grep 176.219.28.59 || echo clean'   → clean
ssh vps2 'sudo fail2ban-client status sshd | grep 176.219.28.59 || echo clean'   → clean
ssh vps3 'sudo fail2ban-client status sshd | grep 176.219.28.59 || echo clean'   → clean
```

Pacing (0.5 s inter-port, 1 s inter-host) held under all three jails' default `findtime`/`maxretry` thresholds.

#### Plan-letter divergences (recorded for honesty)

1. **Plan §step1 said "edit the systemd unit file"** to apply the bind change. The bind lives in `bot.py`, not the unit — replaced with `SYSADMIN_HEALTH_HOST` env var + bot.py source patch. No `systemctl daemon-reload` needed (only `restart`). Convergence log v3.6 → v3.7.
2. **Plan §3 said "run from the dev WSL".** Used vps2 + vps3 as authoritative sources after Lesson 72 surfaced. The dev-WSL probe was attempted (for compliance with the literal instruction) and produced the false-positive that drove Lesson 72 — preserved above as evidence.

---

**Findings the probe surfaced** (folded into the inventory + posture tables above):

1. **vps1 `:8017` is `0.0.0.0`-bound, not loopback.** Prior inventory wording said "blocked from Docker via DOCKER-USER" — that's true for container→host traffic, false for internet→host. Reachable from the public net today; W5 of [`docs/development/plans/archived/2026-05-31-plan-fleet-hardening-and-doc-truth.md`](../development/plans/archived/2026-05-31-plan-fleet-hardening-and-doc-truth.md) is the remediation.
2. **Promtail's gRPC server on spokes binds `*:<random>`** (`grpc_listen_port: 0` in `promtail.yaml`). UFW shields it — not externally reachable — but it's an undeterministic surface. Pin to a known port or `127.0.0.1` if a future audit needs reproducibility.
3. **vps1 has 5 IPv4 UFW ALLOW rules** vs spokes' 4: extra slot is `1194/tcp` (operator's OpenVPN, documented in [`vps-urls.md`](vps-urls.md) § Port reference). Not platform infra.
4. **vps1 UFW rule #5 still carries a stale Coolify-era comment** (`8000/tcp DENY` with comment "Coolify raw port"). Coolify is removed; the DENY itself is still useful (defense-in-depth against any future bind on :8000), but the comment should be retitled in the next cleanup pass.
5. **fail2ban active bans:** vps1 = 493, vps2 = 17, vps3 = 25. Confirms vps1 is the internet-facing target; spokes are largely invisible.

---

## Cross-references

- Architectural inventory: [`vps-complete-inventory.md`](vps-complete-inventory.md)
- Service URLs: [`vps-urls.md`](vps-urls.md)
- Deployment mechanics: `docs/operations/deployment.md`
- Disaster recovery: `docs/operations/disaster-recovery.md`
- AI sysadmin reference: [`vps-ai-sysadmin.md`](vps-ai-sysadmin.md)
- Bootstrap a new spoke: [`vps-bootstrap-plan.md`](vps-bootstrap-plan.md)
- Residue policy: [`vps-residue-policy.md`](vps-residue-policy.md)
- Lessons learnt: [`../LESSONS_LEARNT.md`](../LESSONS_LEARNT.md)
