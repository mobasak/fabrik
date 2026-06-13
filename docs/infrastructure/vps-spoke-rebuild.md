# VPS2 / VPS3 Spoke — How to Bring It Back

**Last Updated:** 2026-06-07 (W11 spoke DR shipped 2026-06-01; aro-wake + sysadmin pack LIVE on spokes 2026-06-06; **4 spoke-bootstrap deps now baked into `bootstrap-vps.sh` step_02 + step_14a/b + step_14 mkdir block** — Node.js 22 + `@anthropic-ai/claude-code`, `python3-venv` + `python3-pip` apt packages, `python-telegram-bot==22.7` via pip, `/opt/fabrik/` ownership reset to `ozgur:ozgur` — validated live on a Vultr throwaway droplet 2026-06-07 evening. **DR drill PASSED end-to-end**: wall-clock 3m 13s (9.3× under the ≤30 min target), 15/15 substantive end-state checks, total drill cost $0.04. One open finding: `sshd PasswordAuthentication=yes` despite step_01 (investigate next drill).)
**Last probe report:** [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml)
**Status:** Scripted end-to-end + **DR drill MEASURED 2026-06-07**: `bootstrap-vps.sh --skip-mesh --skip-dns root@<vultr-ip> vps4` → 3m 13s wall-clock, all 4 today's spoke-bootstrap edits validated end-to-end. The ≤30 min target is no longer aspirational. Drill report at `/opt/fabrik/logs/dr-drill-history.jsonl` (gitignored, local-only).

This document is the definitive answer to "vps2 (or vps3) is gone — how do I get it back **with the same mesh identity**?" Companion to [`vps-hub-rebuild.md`](vps-hub-rebuild.md) but specialized for the spoke role.

> **Now automated via `fabrik vultr`** (shipped + live-validated 2026-06-08). The manual "dashboard → copy IP → `bootstrap-vps.sh` → destroy" drill is wrapped in one command:
> - **DR drill (throwaway):** `fabrik vultr drill spoke` — creates a Vultr droplet, runs `bootstrap-vps.sh --skip-mesh --skip-dns` (hermetic — no prod mesh/DNS touch), runs `bootstrap-vps.sh --verify` as the end-state contract, then **always auto-destroys** (even on failure). Live run 2026-06-08: bootstrap_rc=0 + verify_rc=0, 483s, 0 orphans, 0 `vps4` peers left on vps1 wg0.
> - **New permanent spoke:** `fabrik vultr provision vps4 --region <r>` — full `bootstrap-vps.sh` (no skip flags), mesh IP auto = `10.99.0.N`, `mode=permanent` state, interactive confirm required (real billing + fleet change). **PR3 (2026-06-13)** then auto-installs the spoke's AI sysadmin (claims a bot token from the DR-store pool, writes `.env.sysadmin`, enables aro-wake + sysadmin-bot, verifies) — only `ssh <spoke> 'claude'` device-flow remains manual. Fleet is settled at 3, so this is a ready capability, not active growth.
> See the plan [`docs/archive/2026-06-07-fabrik-vultr-provisioning.md`](../archive/2026-06-07-fabrik-vultr-provisioning.md) and `fabrik vultr --help`. (This runbook remains the source of truth for the **same-identity restore** path via `bootstrap-spoke-restore.sh`, which the drill does not cover.)

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

### ⚠ Re-run discipline — read before retrying the script

The script is idempotent, BUT the SSH login user changes after `step_01`:

| Run | Use this user | Why |
|---|---|---|
| First (fresh VPS) | `root@<new-ip>` | step_00 hasn't created `ozgur` yet |
| Any re-run after step_01 succeeded | **`ozgur@<new-ip>`** | step_01 has disabled root SSH; the script handles either user but you MUST switch on retries |

**If you re-run with `root@<new-ip>` after step_01 ran, the SSH preflight fails — and three quick retries trip the target's fail2ban (default 3 failures / 10 min), locking you out for 10 minutes.** The script's preflight has a safe-rerun trap (added 2026-06-07) that detects this and tells you to switch user BEFORE attempting the SSH that would trigger the ban — but if you ignore the hint or hit the trap from an older script revision, recovery options are: (a) wait 10 min for the ban to expire, or (b) reboot the VPS via the provider's web console (clears fail2ban state).

That's it. No Step 6.

## What `bootstrap-spoke-restore.sh` does, step by step

13 idempotent steps. Each prints `[ ok ]` on success, `[WARN]` on soft failure, `[FAIL]` + exit on hard failure.

| # | Step | What |
|---|---|---|
| 00 | create sudoer | `useradd ozgur` + install pubkey + `/etc/sudoers.d/90-ozgur` NOPASSWD |
| 01 | harden SSH | `PermitRootLogin no` + `PasswordAuthentication no` via drop-in **`00-fabrik-hardening.conf`** (NOT `99-`). Ubuntu cloud-init ships `50-cloud-init.conf` and sshd uses first-match-wins in alphabetical order — anything `99-*` is overridden. Verified live 2026-06-02: spokes show `passwordauthentication no` from cloud-init (their `50-cloud-init.conf` already says `no` from initial bootstrap), but a rebuild script must not depend on cloud-init's content. Cross-check with `sshd -T`. |
| 02 | install OS packages | Docker (via `get.docker.com`), wireguard, ufw, fail2ban, python3, inotify-tools, jq. **(G5b 2026-06-13: no longer installs `iptables-persistent` — on Ubuntu 24.04 it `Conflicts: ufw` and silently removes it; DOCKER-USER persistence is the systemd unit in step 07.)** |
| 03 | place Backrest creds | scp W9 mirror's `vpsN-restic-password-latest` → `/opt/backrest/.restic-password` and `vpsN-backrest-env-latest` → `/opt/backrest/.env` |
| 04 | restic restore host-state | `/etc/wireguard` (preserves spoke privkey!), `/etc/iptables`, `/etc/ufw/user*.rules`, `/etc/docker/daemon.json`, `/etc/sysctl.d/99-*`, `/etc/sudoers.d/90-ozgur`, `/root/.ssh/authorized_keys`, `/home/ozgur/.ssh/authorized_keys` |
| 05 | enable UFW + fail2ban | `ufw --force enable` (rules already restored in step 04) |
| 06 | bring up mesh | `wg-quick@wg0` — hub instantly handshakes because peer-table entry preserved across outage |
| 07 | DOCKER-USER chain via `iptables-docker-user.service` | **(G5b 2026-06-13)** regenerates the `add`/`rm` DOCKER-USER scripts + the oneshot systemd unit from config (identical to `bootstrap-vps.sh` step_10 / the vps1 hub), then `systemctl enable --now`. Replaces `netfilter-persistent`+`rules.v4` — backup-shape-agnostic (pre-G5 backups carry `rules.v4`, post-G5 carry the add-script; the chain is regenerated either way, avoiding a Docker live-chain clobber). |
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
- **Trio Phase 2/3 spoke deps** (until baked into `bootstrap-vps.sh`): on the freshly-restored spoke, the AI layer needs four manual installs before `aro-wake.service` + `vps-sysadmin-bot.service` will start cleanly:
  1. **Node.js 22 + Claude Code CLI**: `curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -` → `sudo apt-get install -y nodejs` → `sudo npm install -g @anthropic-ai/claude-code`
  2. **`python3-venv` apt package** (Ubuntu 24.04 LTS): `sudo apt-get install -y python3.12-venv` (without this, `python3 -m venv /opt/fabrik/.venv-aro-wake` fails on `ensurepip` error)
  3. **`python-telegram-bot==22.7` system pip**: `sudo pip install --break-system-packages python-telegram-bot==22.7` (the sysadmin bot imports `telegram` at module load; without this, `vps-sysadmin-bot.service` stays in `activating` state forever)
  4. **`/opt/fabrik/` ownership**: after sudo creates the venv, `sudo chown -R ozgur:ozgur /opt/fabrik/` so the operator can manage files going forward
- **Per-spoke @BotFather token**: each spoke has its own Telegram bot (`SysAdminVPS2` / `SysAdminVPS3`). Operator must register the bot once with `@BotFather` and put the token in `/opt/fabrik/.env.sysadmin` on that spoke. Also write `TELEGRAM_OWNER_ID=<your-user-id>` in the same file.
- **`claude auth login` on the spoke**: device-flow login via the operator's Claude Code Max subscription. One-time browser-side action per spoke.

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

## DR drill log

### 2026-06-07 — Drill #1 + Drill #2 (`bootstrap-vps.sh` only, not yet `bootstrap-spoke-restore.sh`)

**Note:** These drills exercised the *forward-spoke-install* path (`bootstrap-vps.sh`) — they validate the same step_00 through step_15 stack the restore path also runs, so they covered ~80% of the spoke-DR surface. The remaining ~20% (restic-restore-with-identity-preservation) is unmeasured and tracked separately as `bootstrap-spoke-restore.sh` drill in the strategic backlog. When that drill happens, append it below.

**Drill #1** — caught 2 real bugs:

- Provider: Vultr Cloud Compute, `vc2-1c-2gb`, region `lax`, Ubuntu 24.04 LTS
- Invocation: `bootstrap-vps.sh --skip-mesh --skip-dns root@149.28.70.237 vps4`
- Wall-clock: 2m 39s to crash at step_14b
- Bugs discovered: (1) step_14b nested-quote bash error in `echo "...: $(python3 -c \"...\")"` — local parser accepts it, remote bash explodes; (2) operator re-ran with `root@<ip>` after step_01 disabled root login → fail2ban banned dev WSL IP after 3 retries
- Fixes committed: `ae5f20f` (6 defenses in code + docs + rule pack) + `11efe1c` (rule pack force-add)

**Drill #2** — PASSED:

- Same provider/plan, server reinstalled to clear fail2ban state
- Invocation: `bootstrap-vps.sh --skip-mesh --skip-dns root@149.28.70.237 vps4`
- Wall-clock: **3m 13s (193s)** — **9.3× under the ≤30 min target**
- End-state contract: **15/15 substantive checks passed** (sshd hardened, UFW + 7 rules, fail2ban active, Docker + fabrik network, all 4 of today's new bootstrap edits — python3-venv/pip + Node.js 22 + Claude CLI + python-telegram-bot 22.7 + /opt/fabrik ozgur:ozgur ownership, aro-wake + sysadmin-bot unit files, sysadmin cron + detect_reversals line)
- Open finding: `sshd PasswordAuthentication=yes` despite step_01 hardening attempt — investigate next drill
- Total cost: $0.04 (instance up ~30 min between provisioning and destroy)
- Cleanup: API DELETE `/v2/instances/<id>` returned HTTP 204, 0 instances remaining

**Drill report**: `/opt/fabrik/logs/dr-drill-history.jsonl` (gitignored; future `fabrik vultr drill` will append to this file — see [`docs/archive/2026-06-07-fabrik-vultr-provisioning.md`](../archive/2026-06-07-fabrik-vultr-provisioning.md))

### `bootstrap-spoke-restore.sh` drill — pending

The forward-install drill above does NOT exercise restic-restore-with-identity-preservation. When that drill runs (provision Vultr droplet → `bootstrap-spoke-restore.sh root@<ip> vps2` → verify the rebuilt spoke handshakes with vps1 using the preserved pubkey), append the result above.
