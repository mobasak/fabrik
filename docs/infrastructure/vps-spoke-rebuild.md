# VPS2 / VPS3 Spoke — How to Bring It Back

**Last Updated:** 2026-06-01 (W11 of fleet-hardening plan — spoke DR shipped)
**Last probe report:** [`probe-reports/infra-probe-2026-06-01T22-50Z.yaml`](probe-reports/infra-probe-2026-06-01T22-50Z.yaml)
**Status:** Scripted end-to-end. DR drill on a throwaway VPS pending — wall-clock target ≤ 30 min not yet measured.

This document is the definitive answer to "vps2 (or vps3) is gone — how do I get it back **with the same mesh identity**?" Companion to [`vps-hub-rebuild.md`](vps-hub-rebuild.md) but specialized for the spoke role.

## Scope

**Covers:**

- vps2 or vps3 disk loss / VPS rebuild / fresh-provision-and-restore.
- Preserving the spoke's Wireguard identity (private key + peer pubkey on hub) so the hub recognizes the rebuilt spoke immediately, no peer-table edit needed.
- Bringing back the 5 containers (monitoring-agent stack + spoke Traefik + spoke Backrest itself) so the next backup window fires normally.

**Does NOT cover:**

- vps1 (hub) outages — see [`vps-hub-rebuild.md`](vps-hub-rebuild.md).
- **Fresh spoke without prior history** — use [`scripts/bootstrap/bootstrap-vps.sh`](../../scripts/bootstrap/bootstrap-vps.sh) instead. That script generates a new WG keypair and registers the spoke as a new peer with the hub. Use it when adding vps4/vps5/... to the fleet, NOT when rebuilding an existing spoke.
- Loss of both the spoke AND the B2 bucket — out of scope (GitHub-only rebuild, hub configs intact, spoke needs to be re-bootstrapped via `bootstrap-vps.sh` with a new identity).

## Why this is separate from `bootstrap-vps.sh`

`bootstrap-vps.sh` makes a *new* spoke: fresh WG keypair, fresh peer registration with the hub. That's the right tool for adding capacity.

`bootstrap-spoke-restore.sh` makes the *same* spoke come back: preserves WG private key (restored from B2 snapshot), preserves iptables/UFW/sysctl tuning, preserves Postgres-less app state at `/opt/`. The hub's `wg0.conf` peer table is **unchanged** through the entire outage — the rebuilt spoke connects with the same pubkey the hub already trusts.

Without restore-with-identity, an outage of vps2 followed by `bootstrap-vps.sh` would:

1. Generate a NEW spoke pubkey → hub's `wg0.conf` needs editing to swap old pubkey for new.
2. Briefly fail to handshake with hub until the swap lands.
3. Lose tenant-state files at `/opt/<svc>/` (the W4 path is currently untested).
4. Lose any operator UFW rule changes accumulated since first bootstrap.

`bootstrap-spoke-restore.sh` avoids all four.

## Target wall-clock

≤ 30 min from "fresh VPS" to "spoke handshaking with hub + 5 containers up (monitoring-agent stack + Traefik + Backrest)." Much smaller than the hub's 90 min because:

- No Postgres restore (spokes don't run Postgres today).
- ~15 KB total host-state to restore (vs. hub's ~30 KB).
- 2 compose stacks to bring up (vs. hub's 15).
- No Let's Encrypt cert issuance during restore window (spoke Traefik has no live cert yet — W4 will exercise).

## Prerequisites — once, before disaster

| What | Where | How to verify any day |
|---|---|---|
| W9 DR-store cloned on dev WSL | `/opt/fabrik-dr-store/` | `ls /opt/fabrik-dr-store/env/vps{2,3}-restic-password-latest /opt/fabrik-dr-store/env/vps{2,3}-backrest-env-latest` |
| W9 watcher pulls spoke restic credentials nightly | extended `dr_env_backup.sh` since 2026-06-01 W11 | `cat /var/log/dr-env-backup.log \| tail -10` should show successful `vps2`/`vps3` pulls |
| Spoke Backrest cron writing snapshots to B2 nightly | vps2 + vps3 at `/spokes/vpsN/` paths in `vps1-ocoron-backups` | `ssh vpsN 'sudo bash -c "RESTIC_PW=$(cat /opt/backrest/.restic-password); docker exec -e RESTIC_PASSWORD=$RESTIC_PW backrest /bin/restic -r s3:.../spokes/vpsN snapshots"'` should show snapshots dated within ~24 h |
| Hub (vps1) reachable from dev WSL | via `ssh vps` alias | `ssh vps 'echo ok'` |

If any row is broken, fix it BEFORE you need a DR.

## The restore — 5 operator commands

```bash
# 1. Provision the new spoke VPS. GreenCloudVPS panel, Ubuntu 24.04 LTS,
#    your pubkey in /root/.ssh/authorized_keys. ~5 min manual.

# 2. Confirm reachability + W9 mirror has the spoke's creds.
ssh root@<new-ip> 'echo ok'
ls -la /opt/fabrik-dr-store/env/vps2-restic-password-latest \
       /opt/fabrik-dr-store/env/vps2-backrest-env-latest

# 3. Dry-run preflight. Confirms creds, B2 snapshot count, SSH target. ~30 s.
cd /opt/fabrik
./scripts/bootstrap/bootstrap-spoke-restore.sh --verify root@<new-ip> vps2

# 4. Real run. The second positional arg specifies which spoke identity to
#    restore — vps2 or vps3 — which picks the right W9 credentials and B2
#    bucket-prefix path. About 20-30 min.
./scripts/bootstrap/bootstrap-spoke-restore.sh root@<new-ip> vps2

# 5. After "✓ SPOKE vps2 RESTORED" prints, confirm hub-side that the spoke
#    reconnected with its preserved identity (NO peer-table edit needed).
ssh vps 'sudo wg show wg0 latest-handshakes | awk "(systime()-\$2) < 180 {print}"'
```

That's it. No Step 6.

## What `bootstrap-spoke-restore.sh` does, step by step

13 idempotent steps. Each prints `[ ok ]` on success, `[WARN]` on soft failure, `[FAIL]` + exit on hard failure.

| # | Step | What |
|---|---|---|
| 00 | create sudoer | `useradd ozgur` + install pubkey + `/etc/sudoers.d/90-ozgur` NOPASSWD |
| 01 | harden SSH | `PermitRootLogin no` + `PasswordAuthentication no` + drop-in |
| 02 | install OS packages | Docker (via `get.docker.com`), wireguard, iptables-persistent, ufw, fail2ban, python3, inotify-tools, jq |
| 03 | place Backrest creds | scp W9 mirror's `vpsN-restic-password-latest` → `/opt/backrest/.restic-password` and `vpsN-backrest-env-latest` → `/opt/backrest/.env` |
| 04 | restic restore host-state | `/etc/wireguard` (preserves spoke privkey!), `/etc/iptables`, `/etc/ufw/user*.rules`, `/etc/docker/daemon.json`, `/etc/sysctl.d/99-*`, `/etc/sudoers.d/90-ozgur`, `/root/.ssh/authorized_keys`, `/home/ozgur/.ssh/authorized_keys` |
| 05 | enable UFW + fail2ban | `ufw --force enable` (rules already restored in step 04) |
| 06 | bring up mesh | `wg-quick@wg0` — hub instantly handshakes because peer-table entry preserved across outage |
| 07 | enable netfilter-persistent | loads `rules.v4` + `v6` → DOCKER-USER chain back |
| 08 | docker network create fabrik | idempotent |
| 09 | restic restore `/opt/` | monitoring-agent + traefik + backrest scaffolding (compose.yaml + .env per service) |
| 10 | compose up: monitoring-agent + traefik | `docker compose up -d` in each `/opt/<svc>/` |
| 11 | compose up: backrest | restore the spoke's own backup chain — next scheduled backup fires normally |
| 12 | verify end-state | 7-check contract |

## End-state contract — must pass all 7

Step 12 verifies these automatically. Script exits non-zero on any failure.

1. `wg show wg0 latest-handshakes` → hub handshake within last 3 min (spoke identity preserved)
2. From hub: `ssh vps 'sudo wg show wg0 latest-handshakes'` → spoke listed in peer table with recent handshake (PROOF of identity preservation)
3. `docker ps | wc -l` ≥ 5 (matches spoke inventory: 4 monitoring/traefik + 1 backrest)
4. `sudo ufw status` → active (W1 firewall posture restored)
5. `sudo iptables -L DOCKER-USER -n` → ≥ 1 rule (DOCKER-USER chain rules back)
6. **Spoke Backrest can list ≥ 1 snapshot from its own repo** — closes the W11 loop: spoke backup chain still works POST-DR
7. Wall-clock ≤ 30 min

Anything short of all 7 = drill failed = `bootstrap-spoke-restore.sh` has a gap. Cross-reference [`../operations/spoke-restore-inventory.md`](../operations/spoke-restore-inventory.md) to find what's missing.

## What's auto-restored vs needs manual after-step

**Auto-restored by the script:**

- WG private key + pubkey + wg0.conf — **same identity as before the outage**.
- iptables rules.v4 / v6 (DOCKER-USER chain pattern from bootstrap-vps.sh step_10).
- UFW user.rules / user6.rules — W1 baseline (22/80/443/51820) + W8 mesh-allow (`from 10.99.0.0/24`) required for vps1 Prometheus to scrape spoke node-exporter/cadvisor/promtail. The bootstrap-vps.sh step_02 emits both since W8 ship (2026-06-01).
- /etc/sysctl.d/99-* tuning.
- /etc/docker/daemon.json (log rotation).
- /etc/sudoers.d/90-ozgur (NOPASSWD).
- Both `authorized_keys` files (root + ozgur).
- All `/opt/<svc>/` content (compose.yaml + .env + dynamic configs).
- Spoke Backrest stack (its own compose.yaml + config.json with 2 plans + .env + .restic-password).
- Mesh reconnect with hub.

**Needs one-time manual after-step:**

- **First tenant deploy** — if a tenant was running on the spoke at the moment of disaster, the volume restore won't recreate that tenant (tenant data is only in W11 scope when a `docker-volumes` plan exists; today's spoke plans don't include it because no tenants have landed yet). When the first tenant ships (W4), the `docker-volumes` plan needs to be added and this row becomes "tenant data auto-restored."
- **Let's Encrypt cert** — Traefik will request a fresh cert on first request after restore. No manual action needed; just expect a 30-second delay on first `https://*.vpsN.ocoron.com` hit while the cert issues.

## What is NOT covered

- **Data lost between last backup and disaster.** Spoke Backrest plans run at 02:00 (host-state) and 02:30 (opt-configs) local. Max data loss window: up to 24 h.
- **Spoke hardware-key state** (Wireguard spoke private key) is in the backup snapshot under `/etc/wireguard/spoke.privatekey`. If the snapshot is intact, the spoke comes back with the same mesh identity. If you ever rotate the spoke key out-of-band, take a fresh Backrest snapshot before the rotation.
- **Tenant runtime state** — currently zero tenants on spokes. When W4 ships the first tenant deploy, this section needs updating to describe tenant DR.
- **Hub outage during spoke restore** — `bootstrap-spoke-restore.sh` SSHes to the LIVE hub to verify the peer-table state in the end-state contract. If the hub is also down, step 12 check #2 will fail soft and the script will print a WARN. Bring the hub back first via `bootstrap-hub.sh`, then re-run the spoke restore's step 12 verify manually.

## Related docs

- [`vps-hub-rebuild.md`](vps-hub-rebuild.md) — the hub equivalent of this doc.
- [`vps-fleet-architecture.md`](vps-fleet-architecture.md) — single architectural picture of how vps1 + vps2 + vps3 fit together.
- [`vps-bootstrap-plan.md`](vps-bootstrap-plan.md) — the `bootstrap-vps.sh` fresh-spoke setup flow (use this when adding a NEW spoke, not when rebuilding an existing one).
- [`../operations/spoke-restore-inventory.md`](../operations/spoke-restore-inventory.md) — evidence-based path list this script restores.
- [`../operations/credential-recovery.md`](../operations/credential-recovery.md) — W9 mirror (extended for spoke restic passwords in W11.6).
- [`../operations/disaster-recovery.md`](../operations/disaster-recovery.md) — DR scenario overview.
- `scripts/bootstrap/bootstrap-spoke-restore.sh` — the script itself, 548 lines, run `--help` for full flag list.
- `scripts/bootstrap/bootstrap-config.sh` — shared constants (subnet, ports, sudoer user, hub alias).

## DR drill — pending

Provision a throwaway VPS, run `bootstrap-spoke-restore.sh` against it with `vps2` or `vps3` as the identity to restore, measure actual wall-clock against ≤ 30 min target, fix any gap that surfaces. Until that drill runs, the 30-min figure is a TARGET — drilled-clean means measured-clean.

When the drill happens, append measurements + fixes to this doc's "Drill log" section (which doesn't exist yet because no drills have happened).
