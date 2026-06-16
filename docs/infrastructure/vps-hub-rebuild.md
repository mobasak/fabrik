# VPS1 Hub — How to Bring It Back

**Last Updated:** 2026-06-15 (**Hub DR now GREEN live** — drill #6 sweep on 2026-06-15 produced the first green hub drill `dr-drill-hub-20260615-111639` (9 drills, 6 bugs fixed) via `fabrik vultr drill hub`; DR-in-hours track shipped 2026-06-01; aro-wake + Phase 4 wire LIVE on vps1 since 2026-06-05 + Prometheus SLI metrics + 2 alert rules LIVE 2026-06-06; `bootstrap-hub.sh` step_07 gained spoke↔spoke wg0 routing backstop 2026-06-07 + safe-rerun preflight trap detecting `root@<ip>` after step_01 disabled root login — see [`90-bootstrap-scripts.md`](../../.windsurf/rules/core/90-bootstrap-scripts.md) Rule 1. G5: step_02 no longer installs `iptables-persistent`; step_09 enables `netfilter-persistent` only on legacy pre-G5 hubs.)
**Last probe report:** [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml)
**Status:** Scripted end-to-end **and live-proven** — Hub DR went GREEN 2026-06-15 via the disposable `fabrik vultr drill hub` (first green `dr-drill-hub-20260615-111639`). The drill runs under `--skip-services --skip-mesh` for isolation (so it never handshakes with the live spokes or starts services bound to live infra); under those flags the 7-check end-state contract (step_18) is **deliberately SKIPPED** — see note in the contract section below.

This document is the definitive answer to "vps1 is gone — how do I get it back?" It supersedes the prior advice in `vps-bootstrap-plan.md` § "What's still manual: the hub" (which said copy-and-customize the disaster-recovery runbook by hand).

> **Throwaway-VPS hub drill is `fabrik vultr drill hub`** (shipped 2026-06-08, **first GREEN 2026-06-15**). It provisions a Vultr droplet, runs `bootstrap-hub.sh --skip-services --skip-mesh` against the latest DR snapshot, then **always auto-destroys** (even on failure) — one command, cost-capped, drill report to `logs/dr-drill-history.jsonl`. The 2026-06-15 sweep (drill #6) ran 9 drills, fixed 6 bugs, and landed the first green run `dr-drill-hub-20260615-111639`. Operator-run (quarterly). The shared `step_00/01/02/14` paths are also drill-proven via `fabrik vultr drill spoke`. See the plan [`docs/archive/2026-06-07-fabrik-vultr-provisioning.md`](../archive/2026-06-07-fabrik-vultr-provisioning.md).

## Scope

**Covers:**

- vps1 disk loss / VPS rebuild / fresh-provision-and-restore.
- Both same-IP rebuild (provider gives you back the IP) and new-IP rebuild (CF DNS retag needed).
- Bringing back all 31 containers (29 platform + 2 T-P5 dogfood), the mesh hub, the AI sysadmin bot, and the backup chain itself.

**Does NOT cover:**

- vps2 / vps3 outages (those use [`vps-bootstrap-plan.md`](vps-bootstrap-plan.md) — spoke bootstrap is a separate path).
- Loss of both vps1 AND the B2 bucket — that's Path C in [`../operations/disaster-recovery.md`](../operations/disaster-recovery.md), unscripted.
- Loss of dev WSL alongside vps1 — recover the dev WSL first via [`../operations/credential-recovery.md`](../operations/credential-recovery.md), then come back here.

## Target wall-clock

≤ 90 min from "fresh VPS" to "Telegram bot answering, Gatus all green." Components:

- Provision new VPS (manual, GreenCloudVPS panel): ~5 min
- `bootstrap-hub.sh` preflight + OS install + restic restore: ~30–40 min
- `docker compose up -d` × 15 stacks + image pulls: ~15–25 min
- First Let's Encrypt cert issuance (Traefik): ~5 min
- Verify end-state contract: ~5 min

These are the **real-rebuild** budget. Note the disposable `fabrik vultr drill hub` runs under `--skip-services --skip-mesh`, so its measured wall-clock does NOT include the compose-up / cert-issuance phases above (those steps are skipped in drill mode).

## Prerequisites — once, before disaster

| What | Where | How to verify any day |
|---|---|---|
| W9 DR-store cloned on dev WSL | `/opt/fabrik-dr-store/` | `ls /opt/fabrik-dr-store/env/latest /opt/fabrik-dr-store/env/sysadmin-latest` |
| W9 watcher active on dev WSL | `fabrik-dr-watcher.service` | `systemctl is-active fabrik-dr-watcher.service` |
| `gh` CLI authenticated for `mobasak/fabrik-dr-store` | dev WSL user shell | `gh auth status` |
| Docker on dev WSL (used by `bootstrap-hub.sh` preflight for B2 reachability via `docker run restic`) | dev WSL | `docker version` |
| Backrest cron writing snapshots to B2 nightly | vps1 (or wherever the hub currently lives) | `ssh vps 'sudo docker exec backrest /bin/restic -r s3:... snapshots'` should show snapshots dated within ~24 h |

If any row is broken, fix it BEFORE you need a DR — that's the whole point of W9 and the daily Backrest cron.

## The rebuild — 5 operator commands

```bash
# 1. Provision the new VPS. GreenCloudVPS panel, Ubuntu 24.04 LTS, root SSH enabled,
#    your pubkey installed in /root/.ssh/authorized_keys. About 5 min.

# 2. Reachability + DR-store freshness check from dev WSL.
ssh root@<new-ip> 'echo ok'
ls -la /opt/fabrik-dr-store/env/latest /opt/fabrik-dr-store/env/sysadmin-latest

# 3. Dry-run preflight (no changes). Confirms env source, B2 creds, snapshot
#    count, target SSH reachability. About 30 s.
cd /opt/fabrik
./scripts/bootstrap/bootstrap-hub.sh --verify root@<new-ip>

# 4. Real run. Use --cf-rewrite-dns ONLY if the new VPS has a different
#    public IP than the dead vps1 (most providers reassign on disk-wipe
#    rebuild — assume yes if unsure, the script will skip records that
#    are already correct). About 60-80 min.
./scripts/bootstrap/bootstrap-hub.sh --cf-rewrite-dns <new-ip> root@<new-ip>

# 5. After "✓ HUB READY" prints, sanity check from your browser.
curl -fsS https://status.vps1.ocoron.com | head -5
```

That's it. There is no Step 6.

### ⚠ Re-run discipline — read before retrying the script

If the bootstrap fails partway and you need to re-run, the SSH login user changes after `step_01`:

| Run | Use this user | Why |
|---|---|---|
| First (fresh VPS) | `root@<new-ip>` | step_00 hasn't created `ozgur` yet |
| Any re-run after step_01 succeeded | **`ozgur@<new-ip>`** | step_01 has disabled root SSH |

**If you re-run with `root@<new-ip>` after step_01 ran, the SSH preflight fails — and three quick retries trip the target's fail2ban (default 3 failures / 10 min), locking you out for 10 minutes.** The script's preflight has a safe-rerun trap (added 2026-06-07) that auto-detects this and tells you to switch to `ozgur@<new-ip>` BEFORE attempting the SSH that would trigger the ban. If you somehow trip it anyway: wait 10 min, or reboot the VPS via the provider's web console to clear fail2ban state.

## What `bootstrap-hub.sh` does, step by step

The step functions run `step_00`..`step_18` plus drill-oriented sub-steps: `step_12b` (dry-validate the configs the drill skips), `step_12c` (start core services in drill mode), and `step_17b`/`step_17c` (LE/DNS-cutover validation, gated on `--drill-test-le-staging`). Each prints `[ ok ]` on success, `[WARN]` on soft failure, `[FAIL]` + exit on hard failure. Confirm the current set with `grep -nE '^step_' scripts/bootstrap/bootstrap-hub.sh`.

| # | Step | What | Notes |
|---|---|---|---|
| 00 | create sudoer | `useradd ozgur` + install pubkey + NOPASSWD sudo | Matches vps1 posture from spoke bootstrap |
| 01 | harden SSH | `PermitRootLogin no` + `PasswordAuthentication no` via drop-in **`00-fabrik-hardening.conf`** (NOT `99-`) | After 00 so we don't lock ourselves out. **First-match-wins trap (verified live 2026-06-02 on the existing hub):** Ubuntu cloud-init drops `50-cloud-init.conf` with `PasswordAuthentication yes`. sshd processes drop-ins in alphabetical-glob order and the **first** matching directive wins, so anything `99-*` loses to cloud-init's `50-*`. The Fabrik drop-in MUST sort BEFORE cloud-init's — use `00-fabrik-hardening.conf`, or edit `50-cloud-init.conf` in place. Always cross-check with `sshd -T` afterwards. |
| 02 | install OS packages | Docker via `get.docker.com`, wireguard, ufw, fail2ban, python3, inotify-tools, gh, jq | Noninteractive apt; gh repo set up if missing. **G5: NO `iptables-persistent` — on Ubuntu 24.04 it `Conflicts: ufw` and would silently remove ufw; DOCKER-USER + OpenVPN persistence is the systemd units in step 09.** |
| 03 | install Claude Code | `curl -fsSL https://claude.ai/install.sh \| bash` + symlink to `/usr/local/bin/claude` | Needed by `vps-sysadmin-bot` |
| 04 | scp W9 env | dev WSL `/opt/fabrik-dr-store/env/latest` → `/opt/fabrik/.env` (mode 600) + sysadmin equivalent | Source for steps 06+ B2 creds |
| 05 | write Docker `daemon.json` | Log rotation 10m × 3, promtail tag, address pool, DNS | Before any container start so first runs use it |
| 06 | restic restore host-state | `/etc/wireguard`, `/etc/iptables`, `/etc/ufw/user*.rules`, `/etc/sudoers.d/ozgur`, `/etc/sysctl.d/99-*`, `/etc/cron.d/vps-sysadmin`, custom systemd units, `/root/.ssh/*`, `/home/ozgur/.ssh/*`, `/usr/local/bin/zellij` | 24 explicit paths; `--target /host` so writes hit the host filesystem |
| 07 | enable UFW | `ufw --force enable` + `ufw reload` (rules already on disk from step 06) | Sanity-check **warns if fewer than 12 rules** present (expected range ~12–15: 6 IPv4 + 6 IPv6 mirrors per W5 audit, then 2026-06-06 added 2 aro-wake allows + 1 `ufw route allow in on wg0 out on wg0`) |
| 08 | bring up mesh | `systemctl enable --now wg-quick@wg0` | Spokes reconverge within ~3 min |
| 09 | apply iptables boot state | `iptables-docker-user.service` + `iptables-openvpn.service` (custom oneshot units); **`netfilter-persistent` only if its unit exists** (legacy pre-G5 hubs that still had `iptables-persistent`) | Post-G5 the host has no `iptables-persistent`, so the script probes for `netfilter-persistent.service` and enables it only when present; otherwise the DOCKER-USER + OpenVPN chains are reapplied at boot purely by the two custom units. Order: netfilter (if present) first, then chain rules |
| 10 | `fabrik` Docker network | `docker network create fabrik` (idempotent) | External network referenced by every stack |
| 11 | restic restore `/opt/` | All 19 service dirs minus `containerd`, `fabrik/.git`, `backups/coolify_env_*`, `*restic-cache*`, `manually_installed.txt` | The big-ish restore — ~16 MiB compressed |
| 12 | restic restore Docker volumes | 10 named volumes (postgres-data, redis_redis-data, monitoring_grafana-data, apprise-config, meilisearch-data, n8n-data, ocoron-com 4 tenant volumes, monitoring_alertmanager-data) | Excludes the regeneratable ones (prometheus-data, loki-data, promtail-positions, ocoron-com_redis_data) |
| 13 | `docker compose up -d` in dep order | postgres → redis → traefik → authelia → monitoring → apprise → backrest → gatus → glitchtip → browserless → gotenberg → meilisearch → n8n → site-provisioner → ocoron-com | `pg_isready` + Redis `PING` gates between deps |
| 14 | pg_dump restore fallback | Only fires if step 12's postgres-data volume came up empty — replays from latest `/opt/backups/pg_dump_*.sql` | Safety net for volume-corruption scenarios |
| 15 | enable custom systemd services | `vps-sysadmin-bot.service`, `authelia-config-sync.service` | iptables-docker-user + iptables-openvpn already enabled in step 09 |
| 16 | replay root crontab | `crontab -u root /opt/backups/root-crontab.txt` (dumped nightly by pre-backup.sh) | `/var/spool/cron/crontabs` cannot be bind-mounted into Backrest's image, so the crontab is dumped to a file instead |
| 17 | Cloudflare DNS rewrite (optional) | Only if `--cf-rewrite-dns <ip>` passed: PATCH every `vps1.ocoron.com`, `*.vps1.ocoron.com`, apex, and `www` A record to the new IP via CF API | Token from restored `.env`; safe to re-run (skips records already correct) |
| 18 | verify end-state | The 7-check contract below | Hard-fails if any check fails so the operator notices |

### Drill sub-steps (only run under the drill safety flags)

These exist so the disposable `fabrik vultr drill hub` (which runs `--skip-services --skip-mesh`) still proves the RESTORED configs for the skipped steps would parse + run. A genuine non-drill rebuild proves the same things by actually running steps 08/13/15/17 immediately after.

**`step_12b` — dry-validate the configs the drill skipped** (runs when `--skip-services` OR `--skip-mesh` is set). 7 c-dry checks:

| Check | What | Catches |
|---|---|---|
| `[c-dry/1]` | `wg-quick strip wg0` parses `/etc/wireguard/wg0.conf` without bringing the interface up (only under `--skip-mesh`) | malformed WG conf — missing privkey, bad peer entry |
| `[c-dry/2]` | `docker compose config -q` resolves every restored `/opt/*/compose.yaml` against its `.env` (only under `--skip-services`) | bad YAML, undefined env vars, malformed network refs |
| `[c-dry/3]` | `systemd-analyze verify` on the restored units `vps-sysadmin-bot.service` + `authelia-config-sync.service` | syntactically invalid restored unit files |
| `[c-dry/4]` | `python3 -m py_compile` on every `/opt/fabrik/scripts/sysadmin/*.py` | syntax errors from corrupted backup / version skew |
| `[c-dry/5]` | `/opt/fabrik/.env` has all 4 critical keys present + non-empty: `B2_KEY_ID`, `B2_APPLICATION_KEY`, `BACKREST_RESTIC_PASSWORD`, `CLOUDFLARE_API_TOKEN` | partial-restore / wrong-snapshot |
| `[c-dry/6]` | CF API smoke: `CLOUDFLARE_API_TOKEN` hits `GET /client/v4/zones` from the droplet (read-only, no mutations) | expired/revoked token, or no network egress to `api.cloudflare.com` — both required by step_17's DNS cutover |
| `[c-dry/7]` | WG identity self-consistency: the `[Interface]PrivateKey` derives a valid pubkey via `wg pubkey`, and every `[Peer]` entry carries `PublicKey` + `AllowedIPs` (hub is server-side, so `Endpoint` is not required) | cryptographic/structural corruption that `wg-quick strip` alone would miss |

**`step_12c` — drill-start core services** (`--drill-start-core-only`, only meaningful with `--skip-services`). Starts ONLY `postgres-main` + `redis-main` — pure local state, no B2/Telegram/Cloudflare writes. Under `--skip-mesh` it first creates a **dummy `wg0`** (`ip link add wg0 type dummy`, address `10.99.0.1/24`) so services that bind the mesh IP can come up (no WG protocol, no peer reach), torn down at the end. Then `pg_isready` + `redis-cli ping` prove the restored `postgres-data` + `redis_redis-data` volumes are bootable (and checks `glitchtip` + `site_provisioner` databases are present). The full `step_13` (all containers) and `step_18` (end-state contract) remain SKIPPED in drill mode.

**`step_17b` / `step_17c` — LE/DNS-cutover validation** (gated on `--drill-test-le-staging <hostname>`, runs after step_17's DNS rewrite). `step_17b` waits 30s for DNS propagation, verifies the hostname resolves to the droplet, installs `certbot`, runs `certbot certonly --standalone --staging --preferred-challenges http-01`, then verifies the issuer is the LE **staging** CA (`(STAGING) Pretend Pear`/`Artificial Amaranth` family) — proving the ACME HTTP-01 cutover chain works end-to-end (a production issuer would flag a credentials misconfig). `step_17c` then proves traefik's OWN ACME (Go/lego — a different code path than bare certbot) acquires a staging cert too.

## End-state contract — must pass all 7

Step 18 verifies these automatically on a **real rebuild**. The script exits non-zero on any failure.

> **Drill mode skips this contract.** When `--skip-services` OR `--skip-mesh` is set (both are mandatory for the disposable `fabrik vultr drill hub`, since the drill must NOT bring up the mesh with the restored vps1 key or start live-bound services), `step_18` short-circuits with an informative skip instead of emitting a fake "N of 7 FAILED". The drill instead relies on the dry-validation in `step_12b` (configs) and `step_12c` (optional core-services-only start). The 7 checks below apply to a genuine same-/new-IP rebuild without those flags.

1. `wg show wg0 latest-handshakes` → ≥ 2 peers handshaking within last 3 min (vps2 + vps3)
2. `docker ps | wc -l` ≥ 29 (matches vps1 inventory)
3. `curl -fsS https://status.vps1.ocoron.com` → HTTP 200 (Gatus reachable through Traefik with valid cert)
4. `psql -U postgres -l` lists `glitchtip` + `site_provisioner` databases
5. `curl -fsS http://127.0.0.1:8017/health` → `{"status": "ok", ...}` (vps-sysadmin-bot responding)
6. `restic snapshots` inside the new `backrest` container → ≥ 1 snapshot (closes the W2 loop: backup chain still works post-DR, so the NEXT DR remains possible)
7. Wall-clock ≤ 90 min

Anything short of all 7 = drill failed = `bootstrap-hub.sh` has a gap. Cross-reference [`../operations/hub-restore-inventory.md`](../operations/hub-restore-inventory.md) for the path list to find what's missing.

## Same-IP vs new-IP rebuild

The script is identical except for one flag.

- **Same IP** (some providers preserve IP on disk-wipe rebuild):
  - Skip `--cf-rewrite-dns`. DNS already correct.
- **New IP** (most providers reassign):
  - Pass `--cf-rewrite-dns <new-ip>`. Script rewrites every `*.vps1.ocoron.com` A record + apex + `www` via Cloudflare API using the token restored from `.env`.
  - Cloudflare propagation: < 5 min. Let's Encrypt re-issuance: ~30 s per cert.

If unsure, just pass `--cf-rewrite-dns <new-ip>` always — the script is idempotent and skips records that already match the new IP.

## What's auto-restored vs needs manual after-step

**Auto-restored by the script:**

- All containerized services (29 / 29 on vps1).
- Wireguard mesh hub config.
- All host-level systemd units, cron, sudoers, sysctl tuning.
- All `/opt/<svc>/` configs and per-service `.env` files.
- All meaningful Docker volumes.
- Postgres databases (via volume restore; pg_dumpall fallback if needed).
- Cloudflare DNS A records (with the `--cf-rewrite-dns` flag).
- Let's Encrypt certs (auto-issued by Traefik on first request; `acme.json` is in the `opt-configs` snapshot so re-issuance often skipped).
- Backrest snapshot chain itself (the new hub becomes the next backup source on the same B2 repo).

**Needs one-time manual after-step:**

- `claude auth login` on the new vps1 (the Claude Code CLI needs an auth flow that can't be scripted). After this, `vps-sysadmin-bot` + `aro-wake.service` can make real LLM calls. The bot will run with `claude --version` working but failing on actual LLM calls until you do this.
- **Re-apply UFW spoke↔spoke routing rule** (since 2026-06-06): `sudo ufw route allow in on wg0 out on wg0`. Without this, vps2↔vps3 direct mesh reach is broken (would have to re-discover the gap during the next cross-spoke consult). UFW's default-DROP routed policy remains untouched, so this doesn't open egress relaying.
- **Verify Prometheus aro-wake job** (since 2026-06-06): after monitoring stack comes back up, confirm all 3 aro-wake targets are `up` via `sudo docker exec prometheus wget -qO- http://localhost:9090/api/v1/targets | grep aro-wake`. If a spoke is still down at recovery time, its scrape target will be `down` until the spoke's aro-wake.service comes back.
- (Optional) Re-anchor any out-of-band integrations: external monitoring services pointing at vps1, third-party webhook destinations expecting our public IP, etc. None in current setup.

## What is NOT covered

- **Data lost between last backup and disaster.** Backrest plans run nightly (02:00–03:30 local). Max data loss window: up to 24 h on `docker-volumes` (the biggest blast radius), up to 24 h on `host-state` (rarely changes anyway), and up to 24 h on Postgres dumps. If a near-zero-RPO matters for a future tenant, replicate that tenant's data continuously to off-vps1 storage; this doc doesn't solve sub-daily RPO.
- **vps1 hardware-key state** (Wireguard hub private key) is in the backup snapshot under `/etc/wireguard/`. If the snapshot is intact, the mesh comes back with the same hub identity and spokes don't need to be re-keyed. If you ever rotate the hub key out-of-band, take a fresh Backrest snapshot before the rotation lands.
- **VirtFusion image** (Path A in `../operations/disaster-recovery.md`) — if you have one and it's recent, that's still faster than rebuild-from-restic for minor incidents. **But:** vendor confirmed 2026-06-01 (GreenCloud Senior Technician Tu Do Anh) that VirtFusion snapshots are **manual-only, no API**. The paid backup add-on also goes through their panel. Path D is the ONLY DR path that works without operator-recent-action — Path A is a bonus shortcut, never a commitment.

## Related docs

- [`hub-restore-inventory.md`](../operations/hub-restore-inventory.md) — the evidence-based path list this script is built from. If you find a gap during a drill, the missing path goes here first.
- [`../operations/disaster-recovery.md`](../operations/disaster-recovery.md) § "Full hub restore — Path D" — the operator runbook version of this doc with fewer narrative explanations.
- [`../operations/credential-recovery.md`](../operations/credential-recovery.md) — what `/opt/fabrik/.env` + `.env.sysadmin` are and how they're DR-mirrored to GitHub.
- [`vps-bootstrap-plan.md`](vps-bootstrap-plan.md) — spoke (vps2 / vps3) bootstrap. Different path; do not use that script for the hub.
- [`vps-complete-inventory.md`](vps-complete-inventory.md) — the source-of-truth for what's on vps1. The end-state contract's "≥ 31 containers" is anchored against this.
- [`vps-ai-sysadmin.md`](vps-ai-sysadmin.md) — the bot the script restarts in step 15.
- `scripts/bootstrap/bootstrap-hub.sh` — the script itself (run `wc -l` for current size); run `--help` for the full flag list.
- `scripts/bootstrap/bootstrap-config.sh` — locked constants (restic repo URI, CF zone ID, service start order, volume restore list).

## DR drill log

### 2026-06-15 — Drill #6 sweep — FIRST GREEN

Hub DR went green live via the disposable `fabrik vultr drill hub`. The sweep ran 9 drills and fixed 6 bugs before landing the first clean run: `dr-drill-hub-20260615-111639`. The drill provisions a Vultr droplet, runs `bootstrap-hub.sh --skip-services --skip-mesh` against the latest DR snapshot, then always auto-destroys.

- **Isolation flags:** `--skip-services --skip-mesh` are mandatory in drill mode so the throwaway never handshakes with vps2/vps3 using the restored vps1 WG key (which would overwrite the live spokes' peer endpoint) and never starts services bound to live infra. Under these flags the 7-check end-state contract (`step_18`) is SKIPPED by design; the drill relies on `step_12b` (config dry-validation) + `step_12c` (optional core-services-only start) instead.
- **Real-rebuild wall-clock** (compose-up + cert issuance phases) is still only measured during a genuine non-drill rebuild — the disposable drill skips those phases, so the ≤ 90 min figure above remains the target for an actual same-/new-IP rebuild.

### 2026-06-15 — LE/DNS cutover VALIDATED end-to-end

The CF DNS rewrite (`step_17`) and Let's Encrypt cert acquisition path that real same-/new-IP rebuilds depend on were previously the unmeasured part of the DR story. Both are now validated against a throwaway Cloudflare sandbox zone (`tojlo.com`) + a fresh Vultr droplet, with `--cf-zone-id`/`--cf-zone-name` overriding production `ocoron.com` so zero production records are touched:

| DR-validation row | Status | Run ID |
|---|---|---|
| CF DNS rewrite (`step_17`, `--cf-rewrite-dns`) | **VALIDATED 2026-06-15** — 3 records rewritten on the sandbox zone, reset on drill destroy | `dr-drill-hub-20260615-154530` |
| LE cert acquisition (`step_17b`/`step_17c`, `--drill-test-le-staging`) | **VALIDATED 2026-06-15** — ACME HTTP-01 staging cert acquired (bare certbot + traefik's own lego), issuer verified `(STAGING)` | `dr-drill-hub-20260615-160819` |

The LE/DNS cutover is no longer "deferred"/"not validated" — the full ACME HTTP-01 chain (rewrite DNS → resolve to droplet → :80 challenge → staging cert) ran green from a fresh droplet. Staging (not production) was used to avoid LE rate limits + account-DB pollution; the protocol path is identical, so a green staging acquisition proves the production path works.

Drill reports append to `logs/dr-drill-history.jsonl` (gitignored, local-only). See also [`vps-spoke-rebuild.md`](vps-spoke-rebuild.md) § "DR / provisioning validation status" for the fleet-wide green status.
