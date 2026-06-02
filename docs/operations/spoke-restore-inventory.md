# Spoke Restore Inventory — what `bootstrap-spoke-restore.sh` must put back

**Created:** 2026-06-01 (W11 of fleet-hardening plan — symmetric DR)
**Purpose:** Evidence-based path list for spoke (vps2 / vps3) DR. Mirrors [`hub-restore-inventory.md`](hub-restore-inventory.md) but smaller because spokes carry less custom state.

Same audit rule as the hub doc: if a future workstream adds host-level state on a spoke that survives reboot, update this inventory and re-confirm Backrest scope.

## Why spokes need their own DR (not "just re-run bootstrap-vps.sh")

`bootstrap-vps.sh` recreates a spoke from scratch, generating a fresh Wireguard keypair and re-registering with the hub. That works, but means:

- New WG spoke identity each time → hub's `/etc/wireguard/wg0.conf` needs updating with new pubkey → at-rest backups encrypted to the old identity continue to work but the mesh has briefly-divergent state.
- Loss of `/etc/iptables/rules.v4` customizations beyond bootstrap defaults (currently none, but pattern matters).
- Loss of any tenant data when tenants land — the whole reason this doc exists.
- Loss of UFW `user.rules` history if W1 patches accumulated.
- Manual re-add of any operator-tuned `99-*.conf` in `/etc/sysctl.d/`.

Spoke DR via Backrest restore + `bootstrap-spoke-restore.sh` brings the spoke back **with the same identity** (same WG keys, same iptables state, same sysctl tuning). The hub sees the spoke reconnect with no peer table update needed.

## A. OS packages — installed by `apt` in bootstrap (NOT from backup)

Same list as the hub minus the hub-only bits (no `claude-code`, no `gh` if the spoke doesn't need outbound SSH to GitHub).

| Package | Source |
|---|---|
| Ubuntu 24.04.4 LTS | base OS |
| Docker 29.5.2 | `get.docker.com` |
| wireguard-tools 1.0.20210914 | apt |
| iptables-persistent | apt (provides `netfilter-persistent` service) |
| UFW 0.36.2 | apt |
| fail2ban 1.0.2 | apt |
| Python 3.12 + jq + curl | apt |

## B. Restored from restic — host-level state (~15 KB total)

| Path | Why |
|---|---|
| `/etc/wireguard/spoke.privatekey` (45 B) | spoke identity in the mesh — without this, spoke gets a new identity on rebuild |
| `/etc/wireguard/spoke.publickey` (45 B) | matches privkey; hub references this in its wg0.conf |
| `/etc/wireguard/wg0.conf` (560 B) | endpoint config pointing at hub |
| `/etc/iptables/rules.v4` (~3 KB) | DOCKER-USER chain rules from bootstrap-vps.sh step_10 |
| `/etc/iptables/rules.v6` (~2 KB) | IPv6 mirror |
| `/etc/ufw/user.rules` (~2 KB post-W8) | UFW IPv4 state (W1 baseline + W8 added `allow from 10.99.0.0/24` for mesh trust). Without the W8 rule, vps1's Prometheus cannot scrape spoke node-exporter / cadvisor / promtail — silent observability defect. |
| `/etc/ufw/user6.rules` (1669 B) | UFW IPv6 mirror |
| `/etc/docker/daemon.json` (~120 B) | log rotation; smaller than vps1's (no promtail tag yet — W4 pre-step) |
| `/etc/sysctl.d/99-cloudimg-ipv6.conf` | cloud-init injected — keep to preserve IPv6 posture |
| `/etc/sysctl.d/99-sysctl.conf` | OS-default + operator tuning |
| `/etc/sudoers.d/90-ozgur` | NOPASSWD line — without this, ozgur can't sudo after rebuild. **Path differs from hub** (`/etc/sudoers.d/ozgur`) because `bootstrap-vps.sh` step_00 uses the `90-` prefix for ordering clarity vs. potential future drop-ins. |
| `/root/.ssh/authorized_keys` | inbound root access (currently disabled but key preserved) |
| `/home/ozgur/.ssh/authorized_keys` | inbound ozgur access |

**Not included:** `/etc/systemd/system/*.service` (only OS-default `iptables.service` + `ip6tables.service` shims, come back with `apt install iptables-persistent`), `/etc/cron.d/` (only OS defaults), `/usr/local/bin/` (empty), `/etc/sysctl.d/10-*` (Ubuntu defaults).

## C. Restored from restic — `/opt/<svc>/` directories

| Dir | What | Action |
|---|---|---|
| `containerd` | Docker daemon state | exclude |
| `monitoring-agent` | node-exporter + cadvisor + promtail compose stack | restore |
| `traefik` | spoke Traefik compose stack + dynamic config | restore |

Future tenant directories land here too — automatic inclusion via `/opt/**` glob.

## D. Docker named volumes

| Volume | Restore-critical? |
|---|---|
| `monitoring-agent_promtail-positions` | NO — tail offsets regenerate from container restart |

**No `docker-volumes` Backrest plan needed today** — the only volume is regenerable. When tenants land with stateful volumes, add the plan then.

## E. W9 mirror additions (SHIPPED 2026-06-01 W11.6)

Each spoke gets its own restic password (independent from vps1's) so a single compromised key doesn't read all three hosts' backups. The DR-store mirror has **4 new files** (2 per spoke):

| Path in DR-store | Source | Bytes |
|---|---|---|
| `env/vps2-backrest-env-latest` | `vps2:/opt/backrest/.env` (B2 creds AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY) | 98 |
| `env/vps2-restic-password-latest` | `vps2:/opt/backrest/.restic-password` (64-char a-zA-Z0-9, independent per spoke) | 65 |
| `env/vps3-backrest-env-latest` | `vps3:/opt/backrest/.env` | 98 |
| `env/vps3-restic-password-latest` | `vps3:/opt/backrest/.restic-password` | 65 |

`dr_env_backup.sh` extended with `ssh_pull_and_mirror()` helper that drives these (and the existing sysadmin pull). Soft-required — pull failure logs WARN, doesn't abort main mirror.

## F. Per-spoke Backrest plans (SHIPPED 2026-06-01 W11.4)

Spokes get 2 plans (vs. hub's 4) because no Postgres + no real volumes today:

| Plan | Path | Schedule | Retention | First snapshot (per spoke) |
|---|---|---|---|---|
| `host-state` | 13 explicit paths from § B | `0 2 * * *` | daily 30 | ~9.3 KiB on B2 |
| `opt-configs` | `/opt` (excludes `containerd`, restic-cache, `/opt/backrest/{data,cache,tmp}`) | `30 2 * * *` | daily 30 | ~12.5–13.2 KiB on B2 |

Live state (2026-06-02 evening, post-W4-pre + W8 host-state re-triggers): vps2 repo `56b40b8c84` at `s3:.../spokes/vps2/`, **4 snapshots**, ~17 KiB on B2. vps3 repo `350e752618` at `s3:.../spokes/vps3/`, **4 snapshots**, ~16 KiB. Steady-state will be daily-30 retention per plan.

When tenants land:

- Add `docker-volumes` plan covering `/var/lib/docker/volumes/` with appropriate excludes.
- Add `postgres-dumps` plan if a tenant runs a per-spoke Postgres.

Schedule offset 1 h from vps1 (which runs 02:00 / 03:00) so B2 bandwidth doesn't contend during peak backup window.

## G. End-state contract — bootstrap-spoke-restore.sh is done when

1. `wg show wg0 latest-handshakes` on the rebuilt spoke → hub handshake within last 3 min
2. `ssh vps 'wg show wg0 peers'` → spoke pubkey still listed (proof identity preserved)
3. `docker ps | wc -l` ≥ 5 (monitoring-agent stack + spoke traefik + spoke Backrest as of W11)
4. `sudo ufw status` → active + 8 rules (matches W1 post-state)
5. `sudo iptables -L DOCKER-USER -n` → 2 rules (matches W1 post-state)
6. Spoke's Backrest can list ≥ 1 snapshot from its own repo (closes the spoke-DR loop)
7. Wall-clock from "fresh VPS" to here: target ≤ 30 min (smaller than hub's 90 because spokes carry far less data)

## H. Cross-references

- [`hub-restore-inventory.md`](hub-restore-inventory.md) — the hub equivalent of this doc.
- [`../infrastructure/vps-bootstrap-plan.md`](../infrastructure/vps-bootstrap-plan.md) — the bootstrap-vps.sh spoke setup flow.
- [`../infrastructure/vps-spoke-rebuild.md`](../infrastructure/vps-spoke-rebuild.md) — operator runbook for "vpsN is gone — how to bring it back" (the spoke equivalent of `vps-hub-rebuild.md`).
- [`scripts/bootstrap/bootstrap-vps.sh`](../../scripts/bootstrap/bootstrap-vps.sh) — fresh-spoke bootstrap (W-Multi M1).
- `scripts/bootstrap/bootstrap-spoke-restore.sh` — DR equivalent, restores from spoke's own B2 chain (W11).
