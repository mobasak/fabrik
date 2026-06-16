# VPS Disaster Recovery Guide

**Last Updated:** 2026-06-15 (Hub DR drill GREEN — RTO now MEASURED, not just targeted; LE/DNS cutover validated end-to-end via `fabrik vultr drill hub`)
**Previous version:** 2025-12-22 (Duplicati/Coolify era — archived in git history)
**Recovery Time Objective (RTO):** ≤90 min via Path D (`bootstrap-hub.sh`) — **now MEASURED, not just targeted:** Hub DR went GREEN on 2026-06-15 via the disposable `fabrik vultr drill hub` (first green `dr-drill-hub-20260615-111639`; drill #6 sweep ran 9 drills, fixed 6 bugs). The drill's restore-heavy path (provision → restic restore of host-state + /opt + all volumes) ran in 5m46s on a `vc2-4c-8gb`; the full ≤90 min budget still covers the compose-up + cert-issuance phases the drill skips. Path A (VirtFusion image) ~60 min IF a recent manual snapshot exists.
**Recovery Point Objective (RPO):** up to 24 h on Path D (Backrest plans run nightly 02:00–03:30). Path A RPO = time since last manual snapshot.
**Credential prerequisite for every path:** `BACKREST_RESTIC_PASSWORD` (and the rest of `/opt/fabrik/.env`) recoverable from the GitHub DR mirror — see [`credential-recovery.md`](credential-recovery.md). One-command recovery if dev WSL is gone: `gh repo clone mobasak/fabrik-dr-store /opt/fabrik-dr-store && sudo cp /opt/fabrik-dr-store/env/latest /opt/fabrik/.env`. Mirror is continuous via inotify + systemd (`fabrik-dr-watcher.service`).

> **CURRENT STATE (2026-06-15):** 4 Backrest plans live on B2 (`postgres-dumps`, `docker-volumes`, `opt-configs`, `host-state`) since the DR-in-hours track shipped. First snapshots: 117 MiB compressed on B2 (612 MiB raw). Path D is the primary DR path. `bootstrap-hub.sh` is **drilled GREEN** on a throwaway Vultr droplet via `fabrik vultr drill hub` (first green `dr-drill-hub-20260615-111639`) — RTO is now MEASURED, no longer just a target. The drill runs `--skip-services --skip-mesh` for isolation; it additionally validates the restored configs the drill skips (`step_12b`), boots `postgres-main`+`redis-main` from the restored volumes (`step_12c`), and validates the CF-DNS-rewrite + LE-staging cert cutover against a sandbox zone (`step_17`/`17b`/`17c`).
>
> **Path A (VirtFusion) caveat — vendor confirmed 2026-06-01:** GreenCloud Senior Technician Tu Do Anh confirmed that VirtFusion **has no API for automated or scheduled snapshots** ("Your VPS currently only includes manual backup, which needs to be triggered through the control panel"). The paid backup add-on still goes through their panel for setup. **Path A is only available if the operator has manually clicked "snapshot" in the panel recently** — it's not a drilled or automated DR path. Treat Path A as a bonus shortcut for incidents that happen to fall after a manual snapshot, not as a reliable RPO/RTO commitment. **Path D is the only DR path that works without operator-recent-action.**

---

## Recovery scenarios — pick one

- **Path A — VirtFusion restore (~60 min).** VPS booted into bad state (kernel panic, fs corruption, accidental wipe) but a VirtFusion image exists. Minimal data loss. **Only works if the operator has manually clicked "snapshot" in the GreenCloud panel recently** — vendor confirmed 2026-06-01 there is no API to automate this. Treat as a bonus shortcut, not a reliable path.
- **Path B — B2 cold restore (~2–3 h).** VPS lost or unrecoverable, but B2 backups intact and a fresh VPS provisioned. Up to 24 h of changes lost since last Backrest run. **DEPRECATED 2026-06-01 in favor of Path D, which automates the whole process.**
- **Path C — GitHub-only rebuild (~half day).** Both VPS and B2 lost. Possible because all `compose.yaml` are checked into `mobasak/fabrik`; secrets are gone. Out of scope for this doc.
- **Path D — `bootstrap-hub.sh` scripted full restore (≤90 min target).** VPS lost or unrecoverable, fresh VPS provisioned (any IP). Single command does everything Path B did manually. **PRIMARY DR PATH AS OF 2026-06-01.** See [§ Full hub restore — Path D](#full-hub-restore--path-d-bootstrap-hubsh) below.

**Path D is the primary DR path** because it's the only one that works without operator-recent-action (Path A needs a recent manual snapshot; Path B is deprecated; Path C is unscripted). Use Path A as a bonus shortcut if and only if you happen to have a fresh manual snapshot.

---

## What's currently being backed up

Verified against current Backrest state (28 containers, 3 active plans).

### Backup System (current state)

- **Backup tool:** Backrest (restic-based) — migrated from Duplicati on 2026-04-17.
- **UI:** <https://backup.vps1.ocoron.com> (Authelia 2FA required).
- **Repository password:** stored in `/opt/backrest/config/config.json` AND in `/opt/fabrik/.env` on the dev machine as `BACKREST_RESTIC_PASSWORD` (saved 2026-05-31 — closes the "only-on-vps1" DR weakness).
- **B2 credentials:** `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` in `/opt/backrest/.env` on the VPS AND in `/opt/fabrik/.env` on the dev machine as `B2_KEY_ID` / `B2_APPLICATION_KEY` (already there before today).
- **Storage backend:** Backblaze B2 (S3-compatible endpoint `s3.us-west-004.backblazeb2.com`).
- **Bucket:** `vps1-ocoron-backups` — **EMPTY as of 2026-05-31 01:15 UTC** (intentional wipe; bucket itself preserved for reuse).
- **Repository layout:** single restic repo `b2-vps1` defined in Backrest config; bucket contents wiped, so the repo is structurally absent on B2 and would need a `restic init` before next use.
- **Active plans:** **0** (all 8 prior plans deleted — 3 active + 5 stale test plans).

### Active backup plans

**None.** All plans were deleted on 2026-05-31. When backups are reconfigured, the previous design (kept here for reference) was:

- **`postgres-dumps`** — source: `/opt/backups/pg_dump_*.sql` (nightly pg_dump on the host) — daily 02:00.
- **`docker-volumes`** — source: all named Docker volumes in `/var/lib/docker/volumes/` — daily 03:30.
- **`opt-configs`** — source: `/opt/<svc>/compose.yaml` + `/opt/<svc>/.env` for every service — daily 03:00.
- **`_system_`** — Backrest housekeeping (prune/check) — daily 04:00.

Known issues with that design (to fix when reconfiguring):

- Apprise failure-notification webhook used the old Coolify-era UUID-suffix hostname `apprise-lcocgs4gs8ksg4g08w40ows8:8000` — broken after the W1 container-rename. Failure alerts never reached Telegram. **Fix:** use `apprise:8000` in the new hooks.
- `postgres-dumps` had a 44 % failure rate over 30 d (32 fail / 40 ok). Likely race with the host's nightly `pg_dump` cron. **Fix:** ensure pg_dump cron completes before 02:00, or trigger the Backrest snapshot from a post-dump hook instead of a separate cron.
- 5 stale test plans (`fabrik-e2e-test-data`, `fabrik-smoke-test-data`, etc.) ran on schedule against deleted data and dragged the success rate down. They were deleted in the 2026-05-31 wipe.

### What is NOT backed up (deliberately)

- `**/node_modules/`, `**/__pycache__/`, `**/.venv/`, `**/venv/` — rebuilt at deploy
- `**/.git/` — already on GitHub
- `**/*.log` — ephemeral, in Loki anyway
- Cloudflare DNS records — re-issued by the Fabrik DNS driver on first `fabrik apply`
- Let's Encrypt certs in `/opt/traefik/acme.json` — regenerated by Traefik on first start (slow path, but works)
- `/etc/`, `/var/log/`, kernel — handled at the OS-image level, not in Backrest

---

## Current service inventory (what you must restore)

28 containers across 9 logical groups. Order matters during restore (dependencies first).

### Layer 1 — Front door + auth (start FIRST)

- `traefik` (`/opt/traefik`) — HTTPS termination, Let's Encrypt, routing
- `authelia` (`/opt/authelia`) — SSO/forward-auth

### Layer 2 — Shared infrastructure

- `postgres-main` (`/opt/postgres`) — Postgres 16. Volume: `postgres-data`
- `redis-main` (`/opt/redis`) — Redis 7. Volume: `redis_redis-data`
- `meilisearch` (`/opt/meilisearch`) — search engine. Volume: `meilisearch-data`

### Layer 3 — Observability (full monitoring stack via `/opt/monitoring`)

- `prometheus`, `grafana`, `loki`, `promtail`, `cadvisor`, `node-exporter`, `postgres-exporter`, `redis-exporter`, `alertmanager`, `pushgateway`
- Volumes: `monitoring_prometheus-data`, `monitoring_grafana-data`, `monitoring_loki-data`, `monitoring_alertmanager-data`, `monitoring_promtail-positions`

### Layer 4 — Health + alerting

- `gatus` (`/opt/gatus`) — synthetic checks
- `apprise` (`/opt/apprise`) — notification dispatcher (Telegram). Volume: `apprise-config`

### Layer 5 — Backups

- `backrest` (`/opt/backrest`) — the very tool restoring this VPS. Bring it up after restore so future schedules resume.

### Layer 6 — Error tracking

- `glitchtip-web`, `glitchtip-worker` (`/opt/glitchtip`) — Sentry-compatible

### Layer 7 — Workflow + utilities

- `n8n` (`/opt/n8n`) — automation. Volume: `n8n-data`
- `browserless` (`/opt/browserless`) — headless Chrome
- `gotenberg` (`/opt/gotenberg`) — PDF/Office converter

### Layer 8 — Tenants

- `ocoron-com` (`/opt/ocoron-com`) — WordPress site. 5 containers: wordpress, nginx, mariadb, redis, backup-sidecar. Volumes: `ocoron-com_wp_html`, `ocoron-com_db_data`, `ocoron-com_redis_data`, `ocoron-com_backup_data`

### Volumes that are NOT to be restored (legacy / orphan)

`coolify-db` (98 MB), `coolify-redis`, and 2 SHA256-named anonymous volumes are leftover from pre-migration / removed containers. Skip them. The VirtFusion image still carries them; a future cleanup pass should `docker volume prune` them.

---

## Path A — VirtFusion image restore (~60 min)

**Use when:** VPS is in a bad state but the VirtFusion image slot is populated (currently: image `pre-golden-20260530` exists).

**Risk:** the image is bound to the same VPS slot in VirtFusion. You cannot restore it to a *different* GreenCloudVPS instance without a support ticket.

1. **VirtFusion UI → Overview tab → Shutdown** (graceful). Wait for state = Stopped.
2. **VirtFusion UI → Backups tab → Restore** on the `pre-golden-*` entry. Wait ~10–30 min.
3. **Overview tab → Power On**. Wait ~60–90 sec.
4. **Verify on the host** (from your dev machine):

   ```bash
   ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}' | wc -l"   # expect 29 (header + 28)
   ssh vps "sudo docker ps --filter status=exited --format '{{.Names}}'"  # expect empty
   ssh vps "sudo systemctl is-active fail2ban docker sshd"                # expect: active active active
   ssh vps "sudo docker exec prometheus wget -qO- http://localhost:9090/-/healthy"
   ```

5. **Re-arm Backrest schedule** — open the Backrest UI, confirm next run time.

Done. RTO ~60 min. RPO = the moment of the image (typically your most recent shutdown).

---

## Path B — B2 cold restore onto a fresh VPS (~2–3 h)

> **⚠️ NOT CURRENTLY AVAILABLE (2026-05-31):** Bucket `vps1-ocoron-backups` is empty. This path will become available again once backup plans are reconfigured and at least one successful run completes. The procedure below is retained for that future state.

**Use when:** vps1 is gone. You have a fresh GreenCloudVPS Ubuntu node (or any Ubuntu 24.04 host with internet + SSH).

You also need:

- The B2 access key + secret (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from `/opt/backrest/.env` — copy these to your password manager NOW if you haven't)
- The restic repository password (from the old `/opt/backrest/config/config.json` — copy this too)
- DNS / Cloudflare credentials (`CLOUDFLARE_API_TOKEN` in `/opt/fabrik/.env` on your dev machine)

If you don't have those three sets of credentials elsewhere, **the recovery cannot proceed** — they live on the lost VPS. This is the single point of failure most worth fixing now (see "Hardening the DR path" at the bottom).

### Step 1 — Provision the new VPS (~15 min)

Order an Ubuntu 24.04 VPS. Minimum spec: 4 vCPU / 8 GB RAM / 60 GB SSD. (Match or exceed vps1's 11.6 GB / 6 cpu / 108 GB if budget allows.) Note the new IP as `NEW_VPS_IP`.

### Step 2 — Initial access + hardening (~20 min)

```bash
ssh root@$NEW_VPS_IP
apt update && apt upgrade -y

# Create deploy user
useradd -m -s /bin/bash ozgur
mkdir -p /home/ozgur/.ssh
cp ~/.ssh/authorized_keys /home/ozgur/.ssh/   # or paste your public key
chown -R ozgur:ozgur /home/ozgur/.ssh
chmod 700 /home/ozgur/.ssh
chmod 600 /home/ozgur/.ssh/authorized_keys
echo "ozgur ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Harden SSH (matches vps1 posture: key-only, no root)
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# Firewall (UFW)
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# fail2ban
apt install -y fail2ban
systemctl enable --now fail2ban
```

### Step 3 — Install Docker (~10 min)

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker ozgur

# Log rotation (vps1 standard)
cat > /etc/docker/daemon.json <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {"max-size": "10m", "max-file": "3"}
}
EOF
systemctl restart docker

# Create the shared bridge network Fabrik expects
docker network create coolify   # named "coolify" for historical compat; pure Docker bridge now
```

### Step 4 — (Coolify install — REMOVED. Step intentionally blank to keep step numbering stable with prior versions of this doc.)

Coolify is no longer part of the stack as of 2026-05. Continue to Step 5.

### Step 5 — Install restic + rclone, configure B2 (~10 min)

```bash
# restic for actual restore
apt install -y restic

# rclone for repo listing + sanity checks
curl https://rclone.org/install.sh | sudo bash

# Configure B2 access
export AWS_ACCESS_KEY_ID='<from password manager>'
export AWS_SECRET_ACCESS_KEY='<from password manager>'
export RESTIC_REPOSITORY='s3:s3.us-west-004.backblazeb2.com/vps1-ocoron-backups'
export RESTIC_PASSWORD='<from password manager>'

# Verify
restic snapshots | head -20   # expect ~27 snapshots
```

### Step 6 — Restore `/opt/*` configs (~15 min)

```bash
# Make a working area
mkdir -p /var/restore && cd /var/restore

# Find the most recent snapshot for each active plan
restic snapshots --tag opt-configs | tail -3
restic snapshots --tag docker-volumes | tail -3
restic snapshots --tag postgres-dumps | tail -3

# Restore opt-configs to /var/restore/opt-configs/
restic restore latest --tag opt-configs --target /var/restore

# Move into place (root-owned, like the original)
sudo cp -a /var/restore/opt/. /opt/
sudo find /opt -name '.env' -exec chmod 600 {} \;
sudo find /opt -name '.env' -exec chown root:root {} \;
```

### Step 7 — Restore Docker volumes (~30 min, depends on size)

Restic stores volumes as filesystem trees under `/var/lib/docker/volumes/`.

```bash
# Find the docker-volumes snapshot
SNAPSHOT_ID=$(restic snapshots --tag docker-volumes --json | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d[-1]["id"])')

# Restore to /var/restore/docker-volumes
restic restore $SNAPSHOT_ID --target /var/restore

# Recreate volumes + copy data in (SKIP the legacy/orphan ones)
SKIP="coolify-db coolify-redis"
for vol in postgres-data redis_redis-data meilisearch-data n8n-data apprise-config \
           monitoring_prometheus-data monitoring_grafana-data monitoring_loki-data \
           monitoring_alertmanager-data monitoring_promtail-positions \
           ocoron-com_wp_html ocoron-com_db_data ocoron-com_redis_data ocoron-com_backup_data; do
  sudo docker volume create "$vol"
  sudo docker run --rm \
    -v "$vol":/dst \
    -v "/var/restore/var/lib/docker/volumes/$vol/_data":/src:ro \
    debian:bookworm-slim cp -a /src/. /dst/
done
```

### Step 8 — Restore postgres logical dumps (sanity layer)

The `postgres-dumps` plan is an extra safety net on top of the postgres-data volume (volume restore can fail; dump restore almost never does).

```bash
restic restore latest --tag postgres-dumps --target /var/restore
ls /var/restore/opt/backups/pg_dump_*.sql

# After bringing postgres-main up in Step 9, if its volume restore is bad:
# sudo docker exec -i postgres-main psql -U postgres < /var/restore/opt/backups/pg_dump_<latest>.sql
```

### Step 9 — Start services in dependency order (~15 min)

```bash
# Layer 1 — front door
cd /opt/traefik && sudo docker compose up -d

# Layer 2 — shared infra (postgres + redis must come up before anything that depends on them)
cd /opt/postgres && sudo docker compose up -d
cd /opt/redis && sudo docker compose up -d
cd /opt/meilisearch && sudo docker compose up -d

# Layer 3 — observability stack (all under /opt/monitoring/compose.yaml)
cd /opt/monitoring && sudo docker compose up -d

# Layer 4 — health + alerting
cd /opt/gatus && sudo docker compose up -d
cd /opt/apprise && sudo docker compose up -d

# Layer 5 — backups (so future schedules resume)
cd /opt/backrest && sudo docker compose up -d

# Layer 6 — auth (after shared infra so it can write its session store)
cd /opt/authelia && sudo docker compose up -d

# Layer 7 — error tracking, automation, utilities
cd /opt/glitchtip && sudo docker compose up -d
cd /opt/n8n && sudo docker compose up -d
cd /opt/browserless && sudo docker compose up -d
cd /opt/gotenberg && sudo docker compose up -d

# Layer 8 — tenants
cd /opt/ocoron-com && sudo docker compose up -d
```

### Step 10 — DNS cutover (~10 min)

If the new VPS has a new IP, update the A record for `vps1.ocoron.com`. The wildcard `*.vps1.ocoron.com` points at it via CNAME, so the wildcard follows automatically — you only need to change one record.

**Note:** Fabrik does not currently expose a `fabrik dns update` CLI subcommand. The `cloudflare.py` driver is used internally by `fabrik apply` registrars. For DR, use one of:

**Option 1 — Cloudflare UI** (simplest):
Cloudflare dashboard → `ocoron.com` zone → DNS → Records → edit `vps1.ocoron.com` A record → set content to `$NEW_VPS_IP` → Save.

**Option 2 — Cloudflare API via curl** (scriptable):

```bash
export CF_API_TOKEN='<from /opt/fabrik/.env on dev machine>'
export CF_ZONE_ID='<from Cloudflare dashboard → ocoron.com → API → Zone ID>'
RECORD_ID=$(curl -s -H "Authorization: Bearer $CF_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/dns_records?name=vps1.ocoron.com&type=A" \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["result"][0]["id"])')

curl -X PATCH -H "Authorization: Bearer $CF_API_TOKEN" -H "Content-Type: application/json" \
  "https://api.cloudflare.com/client/v4/zones/$CF_ZONE_ID/dns_records/$RECORD_ID" \
  -d "{\"content\":\"$NEW_VPS_IP\"}"
```

**Option 3 — Python via the Fabrik driver** (if you have `/opt/fabrik/` checked out on a recovery machine):

```bash
cd /opt/fabrik
python3 -c "
from fabrik.drivers.cloudflare import CloudflareClient
import os
cf = CloudflareClient(api_token=os.environ['CF_API_TOKEN'])
cf.ensure_record(domain='vps1.ocoron.com', record_type='A', content=os.environ['NEW_VPS_IP'])
"
```

### Step 11 — Verify (~10 min)

```bash
ssh vps "sudo docker ps --format '{{.Names}}\t{{.Status}}' | wc -l"  # expect ~29
ssh vps "sudo docker exec prometheus wget -qO- http://localhost:9090/-/healthy"
ssh vps "sudo docker exec postgres-main pg_isready -U postgres"
ssh vps "sudo docker exec redis-main redis-cli ping"
curl -sI https://gatus.vps1.ocoron.com | head -3   # Authelia 302 = correctly protected
curl -sI https://errors.vps1.ocoron.com | head -3  # GlitchTip 200 = up
```

Open the Backrest UI, confirm the next scheduled run; run a manual snapshot to prove writes still work.

---

## Quick recovery checklist

```text
PATH A (VirtFusion image):
[ ] Shutdown via UI
[ ] Restore image
[ ] Power On
[ ] ssh vps && verify 28 containers
[ ] Confirm Backrest schedule

PATH B (B2 cold restore):
[ ] New VPS provisioned
[ ] SSH hardened (no root, no password)
[ ] UFW + fail2ban enabled
[ ] Docker + `fabrik` bridge network created (renamed from `coolify` 2026-05-31)
[ ] restic + rclone installed, B2 configured
[ ] B2 access key + secret + restic password recovered from your password manager
[ ] /opt/* configs restored from `opt-configs` snapshot
[ ] Docker volumes restored from `docker-volumes` snapshot (skip coolify-db/coolify-redis)
[ ] postgres-dumps snapshot restored (safety layer)
[ ] All layers started in order (traefik → infra → monitoring → alerting → backrest → auth → apps → tenants)
[ ] Cloudflare A record updated to NEW_VPS_IP
[ ] Smoke tests pass
[ ] Backrest schedule confirmed
```

---

## Hardening the DR path (gaps to close)

These are real gaps in DR posture — not theater.

- **RESOLVED: Restic password + B2 keys are now stored off-VPS** in `/opt/fabrik/.env` on the dev machine (`BACKREST_RESTIC_PASSWORD`, `B2_KEY_ID`, `B2_APPLICATION_KEY` — saved 2026-05-31). The original single-point-of-failure ("only on vps1") is closed. **No rotation planned:** this is a single-operator dev environment; the credentials being copy-pasted into a private Claude Code session is not a realistic attack vector given the threat model (no third-party adversary, no shared account, agent acting on owner's behalf).
- **HIGH: Cloudflare API token lives only on your dev machine** in `/opt/fabrik/.env`. Without it, can't update DNS during cutover. **Fix:** already off-vps (good); ensure your dev machine itself is backed up.
- **RESOLVED: DR is now drilled.** v1 of this doc claimed "Testing Recovery: recommended quarterly" but no drill had ever been run. As of 2026-06-15 Hub DR is GREEN via the disposable `fabrik vultr drill hub` — provisions a throwaway Vultr droplet, runs `bootstrap-hub.sh --skip-services --skip-mesh` against the latest DR snapshot, then always auto-destroys (one command, cost-capped, report to `logs/dr-drill-history.jsonl`). Operator-run quarterly. The CF-DNS + LE-staging cutover is drilled against a `tojlo.com` sandbox zone so no production records are touched. See [`../infrastructure/vps-hub-rebuild.md` § DR drill log](../infrastructure/vps-hub-rebuild.md).
- **LOW: No second-region B2 bucket.** Single-region means a B2 us-west outage during a vps1 disaster = no restore. B2 multi-region failures are rare. **Fix:** W-DR D4 adds `rclone sync` to an eu-central B2 bucket weekly.
- **LOW: DNS still on Cloudflare only.** If Cloudflare goes down, traffic can't move. Out of scope for this doc; covered in network-redundancy plans.
- **NOT A REAL RISK: 3 world-readable `.env` files** on the host (browserless, gotenberg, meilisearch). Single-operator VPS, no other users. Cosmetic only. See W-Sec in the Platform-to-A+ plan; deprioritized after threat-model review.

---

## Full hub restore — Path D (bootstrap-hub.sh)

**Status:** Primary DR path. Replaces Path B's manual sequence. **Drilled GREEN 2026-06-15** via the disposable `fabrik vultr drill hub` — see [`hub-restore-inventory.md` § Drill safety contract](hub-restore-inventory.md) and [`../infrastructure/vps-hub-rebuild.md` § DR drill log](../infrastructure/vps-hub-rebuild.md). The CF-DNS-rewrite + Let's Encrypt cert cutover (`step_17`/`17b`/`17c`) is validated against a sandbox zone, so the new-IP DR path is no longer the unmeasured part of the story.

**Target wall-clock:** ≤ 90 min on a 100 Mbit pipe between dev WSL and the new VPS. Most of the time is image pulls (step 13) + B2 bandwidth for the docker-volumes snapshot (~599 MiB) + initial Let's Encrypt cert issuance.

**Inputs (all already in place on dev WSL):**

1. `/opt/fabrik-dr-store/env/latest` — fleet `.env` (W9 mirror). Has `B2_KEY_ID`, `B2_APPLICATION_KEY`, `BACKREST_RESTIC_PASSWORD`, `CLOUDFLARE_API_TOKEN`.
2. `/opt/fabrik-dr-store/env/sysadmin-latest` — Telegram bot creds (W9 extension).
3. `gh` CLI authenticated for `mobasak/fabrik-dr-store` HTTPS access.
4. Local Docker (used by `bootstrap-hub.sh` preflight to verify B2 reachability via `docker run restic`).
5. The bootstrap-hub script itself at `scripts/bootstrap/bootstrap-hub.sh` (this repo).

**Operator commands (5 steps):**

```bash
# 1. Provision the new VPS — GreenCloudVPS panel, Ubuntu 24.04 LTS, root SSH enabled,
#    your pubkey in /root/.ssh/authorized_keys. ~5 min manual.

# 2. Confirm reachability + W9 mirror is fresh.
ssh root@<new-ip> 'echo ok'
ls -la /opt/fabrik-dr-store/env/latest /opt/fabrik-dr-store/env/sysadmin-latest

# 3. Dry-run preflight (no changes). Confirms env source, B2 creds, snapshot count.
cd /opt/fabrik
./scripts/bootstrap/bootstrap-hub.sh --verify root@<new-ip>

# 4. Real run. Add --cf-rewrite-dns ONLY if the new VPS has a different public IP
#    than the dead vps1 (most providers reassign on disk-wipe rebuild).
./scripts/bootstrap/bootstrap-hub.sh --cf-rewrite-dns <new-ip> root@<new-ip>
#    or, same-IP rebuild:
./scripts/bootstrap/bootstrap-hub.sh root@<new-ip>

# 5. After "✓ HUB READY" prints, confirm by hitting Gatus.
curl -fsS https://status.vps1.ocoron.com | head -5
```

**What the script does, condensed:** create sudoer → harden SSH → install Docker/WG/UFW/fail2ban/gh/inotify/jq → install Claude Code → place `/opt/fabrik/.env` + `.env.sysadmin` from W9 mirror → write Docker `daemon.json` → restic restore host-state (25 KB of `/etc/*`, `/root/.ssh/*`, `/home/ozgur/.ssh/*`, `/usr/local/bin/zellij`) → enable UFW + Wireguard + iptables boot units → create `fabrik` Docker network → restic restore `/opt/` (excludes `containerd`, `fabrik/.git`, `backups/coolify_env_*`) → restic restore 10 named Docker volumes → `docker compose up -d` in dep order (postgres → redis → traefik → authelia → monitoring → apprise → backrest → gatus → glitchtip → browserless → gotenberg → meilisearch → n8n → site-provisioner → ocoron-com) with pg_isready/PING gates → pg_dump fallback if `postgres-data` volume came up empty → enable `vps-sysadmin-bot` + `authelia-config-sync` → replay root crontab from `/opt/backups/root-crontab.txt` → (optional) rewrite Cloudflare A records to new IP → run 7-check end-state contract.

**End-state contract (must pass all 7):**

1. `wg show wg0` → 2 peers handshaking (vps2 + vps3)
2. `docker ps | wc -l` ≥ 29
3. `curl -s https://status.vps1.ocoron.com` → HTTP 200
4. `psql -U postgres -l` lists `glitchtip` + `site_provisioner`
5. `curl -s http://127.0.0.1:8017/health` → `{"status":"ok",...}`
6. `restic snapshots` from inside the new `backrest` container → ≥ 1 snapshot (W2 loop closure: backup chain still works post-DR)
7. Wall-clock ≤ 90 min

Failure of any item = drill failed = bootstrap-hub.sh has a gap. Re-open against `hub-restore-inventory.md` to find what's missing.

**Idempotency:** every step checks current state before mutating. Safe to re-run after a partial failure (network blip, missing image, etc.) — already-completed steps detect their done-state and short-circuit.

**Flags worth knowing:**

| Flag | When |
|---|---|
| `--dry-run` | Print every command, change nothing. Use during DR drill planning. |
| `--verify` | Read-only preflight only. Confirms env source, B2 reachability, target SSH. |
| `--snapshot <ID>` | Use a specific restic snapshot (default `latest`). For point-in-time restores. |
| `--env-from <path>` | Override `/opt/fabrik-dr-store/env/latest`. For test runs with a synthetic env. |
| `--cf-rewrite-dns <new-ip>` | Update every `*.vps1.ocoron.com` A record (+ apex + `www`). Skip if same IP. Also the DR DNS cutover that `step_17b`/`17c` validate. |
| `--skip-services` | Stop before `docker compose up -d` (step_13) — host + configs restored, no app containers started. Drill-isolation (Backrest must not write to the live B2 chain) + debugging restore steps. |
| `--skip-mesh` | Skip `wg-quick@wg0` bring-up (step_08). Drill-isolation: bringing the mesh up with the restored vps1 key would make vps2/vps3 re-point their peer endpoint at the drill IP and break the live mesh on destroy. |
| `--skip-local-b2-check` | Skip preflight #6's operator-side `restic snapshots` query. From a network where B2's us-west-004 endpoint is blocked (e.g. Turkish ISPs), this saves ~10 min of retries — the actual restore runs on the target droplet, which has unblocked routing. |
| `--drill-start-core-only` | (Drill, with `--skip-services`) start ONLY `postgres-main` + `redis-main` to prove the restored volumes are bootable (`step_12c`). Under `--skip-mesh` it creates a dummy `wg0` so mesh-IP binds succeed. |
| `--drill-test-le-staging <hostname>` | (Drill, after `--cf-rewrite-dns`) run `step_17b`/`17c`: acquire an ACME HTTP-01 **staging** cert (bare certbot + traefik's own lego) for the rewritten hostname and verify the `(STAGING)` issuer — validates the LE/DNS cutover chain end-to-end. |

> The five drill flags above are how the disposable `fabrik vultr drill hub` invokes `bootstrap-hub.sh` safely; a real same-/new-IP rebuild uses none of them (it runs every step for real). Confirm the full set with `bootstrap-hub.sh --help`.

**Logging:** script tees the full run to `/tmp/bootstrap-hub-<TS>.log` on the dev machine. Keep this file from each drill — it's the only way to find which step took longest.

**What the script does NOT do:**

- Provision the VPS (still manual via GreenCloudVPS panel — ~5 min).
- Re-issue Let's Encrypt certs (handled automatically by Traefik on first request to `https://*.vps1.ocoron.com` after start; ~5 min for first cert, rate-limit safe because `acme.json` IS in the `opt-configs` snapshot so re-issuance is usually skipped). The ACME HTTP-01 cutover chain itself (after a `--cf-rewrite-dns` to a new IP) is validated in drill mode by `step_17b`/`17c` against LE **staging**.
- Bring back spokes (vps2 + vps3 keep running through the hub outage; mesh reconverges automatically once `wg-quick@wg0` comes up on the rebuilt hub).
- Authenticate Claude Code (manual: `claude auth login` once, post-bootstrap, before the sysadmin bot can make real LLM calls).

---

## Emergency contacts

- **GreenCloudVPS** — client area support ticket.
- **Backblaze B2** — <support@backblaze.com>.
- **Cloudflare** — dashboard support.
- **Namecheap (domain registrar)** — client area support ticket.

---

## Version history

- **2026-05-31 (post-wipe)** — Second revision same day. Reflects: all Backrest plans deleted, B2 bucket emptied (bucket preserved, repo definition preserved). Path B marked unavailable until plans are reconfigured. Restic password + B2 keys saved off-VPS in `/opt/fabrik/.env`. Rationale: nothing material to back up today; intentional defer until real tenants land.
- **2026-05-31** — Full rewrite. Reflects: SSH+Compose deploy path (no Coolify), Backrest backup tool (replaced Duplicati 2026-04-17), current 28-container inventory, VirtFusion image as Path A, B2 cold-restore as Path B, hardening gap register, K4 discovery (restic password lives in `/opt/backrest/config/config.json`).
- **2025-12-22** — Initial document — Coolify era, Duplicati backup tool, service list of captcha/emailgateway/translator/dns-manager/proxy/redis/netdata/duplicati.
