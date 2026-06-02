# Hub Restore Inventory — what `bootstrap-hub.sh` must put back

**Created:** 2026-06-01 (Step 1 of Option B — DR-in-hours track)
**Purpose:** Evidence-based path list of everything on vps1 that must be restored from backup before services can come up. Built from live probes of running vps1, not from memory or assumption. Drives both:

- Backrest plan scope (which paths the `host-state` + `opt-configs` plans must cover)
- `scripts/bootstrap/bootstrap-hub.sh` restore steps

**Audit rule:** if a future workstream adds a host-level thing on vps1 that survives reboot, this inventory MUST be updated and the Backrest scope re-confirmed against it. Otherwise it'll silently drop out of DR scope.

---

## A. OS packages — installed by `apt` in bootstrap (NOT from backup)

Verified live on vps1 (2026-06-01):

| Package | Version | Source |
|---|---|---|
| Ubuntu | 24.04.3 LTS | base OS |
| Kernel | 6.8.0-117-generic | base OS |
| Docker | 29.0.2 | apt `docker-ce` |
| Docker Compose | v2.40.3 | apt `docker-compose-plugin` |
| wireguard-tools | 1.0.20210914 | apt `wireguard` |
| iptables | 1.8.10 (nft backend) | apt (default on 24.04) |
| iptables-persistent | — | apt (provides `netfilter-persistent`) |
| UFW | 0.36.2 | apt |
| fail2ban | 1.0.2 | apt |
| Python | 3.12.3 | apt (default on 24.04) |
| inotify-tools | 3.22.6.0 | apt |
| gh (GitHub CLI) | 2.83.1 | apt (via gh repo) |
| Claude Code | v2.1.144 | `npm i -g @anthropic-ai/claude-code` (for AI sysadmin) |

---

## B. Restored from restic — host-level state (~25 KB total, fits in one snapshot)

| Bucket | Path | Size | Why |
|---|---|---|---|
| **Wireguard** | `/etc/wireguard/wg0.conf` | 1100 B | hub mesh config — peers, port |
| | `/etc/wireguard/hub.privatekey` | 45 B | mesh privkey (referenced inline in wg0.conf) |
| | `/etc/wireguard/hub.publickey` | 45 B | mesh pubkey |
| **Docker daemon** | `/etc/docker/daemon.json` | ~250 B | log rotation, container tag for promtail, address pool, DNS |
| **iptables scripts** | `/etc/iptables/add-docker-user-rules.sh` | 1680 B | DOCKER-USER chain rules (drops mesh-only ports from public iface) |
| | `/etc/iptables/rm-docker-user-rules.sh` | 304 B | reverse |
| | `/etc/iptables/add-openvpn-rules.sh` | 271 B | OpenVPN forward rules (operator's personal VPN, out-of-platform-scope but actively used) |
| | `/etc/iptables/rm-openvpn-rules.sh` | 261 B | reverse |
| | `/etc/iptables/rules.v4` | 6329 B | netfilter-persistent state |
| | `/etc/iptables/rules.v6` | 2197 B | netfilter-persistent state |
| **UFW** | `/etc/ufw/user.rules` | 2120 B | UFW IPv4 rule list (22/80/443/1194/8000-DENY/51820) |
| | `/etc/ufw/user6.rules` | 2083 B | UFW IPv6 mirror |
| **systemd units** | `/etc/systemd/system/vps-sysadmin-bot.service` | small | Telegram bot |
| | `/etc/systemd/system/authelia-config-sync.service` | small | config watcher |
| | `/etc/systemd/system/iptables-docker-user.service` | small | re-applies DOCKER-USER on boot |
| | `/etc/systemd/system/iptables-openvpn.service` | small | re-applies OpenVPN rules on boot |
| **Sudoers** | `/etc/sudoers.d/ozgur` | 30 B | NOPASSWD line for `ozgur` — without this, `vps-sysadmin-bot` can't run sudo commands |
| **Kernel tuning** | `/etc/sysctl.d/99-tuning.conf` | small | operator-customized (`vm.swappiness=10`, `vm.max_map_count=1048576`, `net.ipv4.ip_forward=1`, `rp_filter=2`) |
| | `/etc/sysctl.d/99-openvpn.conf` | small | operator's personal VPN forwarding rules |
| | `/etc/sysctl.conf` | small | base file (operator may have appended) |
| **Cron** | `/etc/cron.d/vps-sysadmin` | 1008 B | sysadmin proactive checks |
| | `/var/spool/cron/crontabs/root` | 249 B | root crontab containing `30 1 * * * /opt/backups/pre-backup.sh ...` — the actual file, restored verbatim (no `crontab -u root` re-install needed) |
| **Custom binaries** | `/usr/local/bin/zellij` | 51 MB | operator's preferred terminal multiplexer; restoring avoids a separate install step |
| **Logrotate** | `/etc/logrotate.d/vps-sysadmin-bot` | small | bot log rotation |
| | `/etc/logrotate.d/vps-sysadmin-proactive` | small | proactive log rotation |
| **SSH** | `/root/.ssh/authorized_keys` | 189 B | inbound root access (currently disabled but key preserved) |
| | `/root/.ssh/known_hosts` | 878 B | known_hosts for outbound (github.com etc.) |
| | `/home/ozgur/.ssh/authorized_keys` | 181 B | inbound ozgur access |
| | `/home/ozgur/.ssh/config` | 160 B | ssh client config (vps2/vps3 aliases) |
| | `/home/ozgur/.ssh/id_ed25519` + `.pub` | 419 + 110 B | outbound key (for ssh vps2/vps3 / GitHub) |
| | `/home/ozgur/.ssh/known_hosts` | 2098 B | outbound known_hosts |

**Total: < 30 KB.** Goes in the new `host-state` Backrest plan.

---

## C. Restored from restic — `/opt/<svc>/` directories

Verified live: 19 dirs under `/opt/`, classified:

| Category | Dirs | Pattern |
|---|---|---|
| **Standard** (has `compose.yaml` + `.env`) | `apprise`, `backrest`, `browserless`, `glitchtip`, `gotenberg`, `meilisearch`, `monitoring`, `n8n`, `postgres`, `site-provisioner` | back up whole dir |
| **Compose-only** (has `compose.yaml`, no `.env` because container takes its config from `/config` bind mount) | `authelia`, `gatus`, `ocoron-com`, `redis`, `traefik` | back up whole dir |
| **Special-shape** | `authelia-config-sync` (script + sync.sh, no compose), `backups` (script + pg_dumps + log), `fabrik` (orchestrator's own repo — `.git` excluded; covered separately by W9 for `.env`), `monitoring` (extra `gatus-compose.yaml`) | back up whole dir, except `fabrik/.git/**` |
| **Skip** | `containerd` (Docker daemon state, not ours), `manually_installed.txt` (text marker) | exclude |

Goes in the existing `opt-configs` Backrest plan, **scope widened** from `*/compose.yaml + */.env` to `/backup-opt/**` with the exclusions above + `*-restic-cache*` + `/backup-opt/fabrik/.git/**`.

---

## D. Restored from restic — Docker named volumes

Verified live: 12 named volumes (the important ones). 4 UUID-anonymous volumes (2 used by apprise, 2 orphans) recreate automatically on `docker compose up -d` — exclude.

| Volume | Bytes (approx) | Source | Restore-critical? |
|---|---|---|---|
| `postgres-data` | TBD | postgres-main container | **YES** — primary DB; alternative is `psql < pg_dump_latest.sql` from `/opt/backups/` |
| `redis_redis-data` | TBD | redis-main container | **YES** — sessions, auth state |
| `monitoring_prometheus-data` | LARGE | prometheus | NO (15d retention, regeneratable on restart) — EXCLUDE from backup |
| `monitoring_loki-data` | LARGE | loki | NO (regenerates from logs) — EXCLUDE |
| `monitoring_grafana-data` | small | grafana dashboards + db | **YES** — user dashboards |
| `monitoring_alertmanager-data` | tiny | alertmanager silences | **YES** — small, low cost; preserving in-flight silences during a DR event is operationally valuable |
| `monitoring_promtail-positions` | tiny | promtail tail offsets | NO (regenerates) — EXCLUDE |
| `apprise-config` | tiny | apprise notification config | **YES** |
| `meilisearch-data` | TBD | meilisearch indexes | **YES** if active indexes exist |
| `n8n-data` | TBD | n8n workflow definitions + creds | **YES** — workflows are non-trivial to re-create |
| `ocoron-com_db_data` | TBD | ocoron.com WordPress MySQL | **YES** — tenant data |
| `ocoron-com_wp_html` | TBD | ocoron.com WordPress files | **YES** — tenant data |
| `ocoron-com_backup_data` | TBD | tenant backup volume | partial |
| `ocoron-com_redis_data` | TBD | tenant Redis | regeneratable |

Goes in the existing `docker-volumes` Backrest plan (scope: `/var/lib/docker/volumes/`), excludes match the "NO" rows above.

---

## E. Restored from W9 GitHub mirror (NOT restic)

These two files are mirrored continuously to `mobasak/fabrik-dr-store` and recovered via `gh repo clone` first thing in the bootstrap. Avoids the chicken-and-egg of "restic needs `BACKREST_RESTIC_PASSWORD` from `.env` before it can pull `.env` from restic."

| Path | Source in DR store | Bytes |
|---|---|---|
| `/opt/fabrik/.env` | `env/latest` | ~15 KB |
| `/opt/fabrik/.env.sysadmin` | `env/sysadmin-latest` | ~95 B |

---

## F. Generated by bootstrap (NOT restored — re-created fresh)

| What | Why |
|---|---|
| Docker `fabrik` external network | one `docker network create fabrik` line, no state to preserve |
| Let's Encrypt certs (`/opt/traefik/acme.json`) | re-issued on first request; ~5 min if not in scope, but **acme.json IS captured in `opt-configs`** so this is a fallback |
| Cron `@reboot` triggers | once cron file is in place, systemd cron re-fires them on boot |
| Wireguard mesh peer handshakes | come up automatically once `wg-quick@wg0` starts with restored wg0.conf |

## G. Explicit EXCLUDES — must NOT restore

| Path | Reason |
|---|---|
| `/etc/netplan/*.yaml` | Auto-generated from cloud-init on the NEW VPS with its NEW public IP + gateway. Restoring the dead vps1's netplan would clobber the new VPS's working network config — instant lockout. |
| `/etc/hosts` | Stock Ubuntu (`127.0.0.1 localhost` + `::1 ip6-*`) — no custom entries on vps1. Skip to avoid clobbering any new-VPS-specific entries the provider injected. |
| `/etc/sysctl.d/10-*.conf` | Ubuntu defaults; come back with `apt install` of base packages. Only restore the `99-*` operator-customized files. |
| `/var/spool/cron/crontabs/ozgur` | Doesn't exist on current vps1 (ozgur has no user crontab). If a future ozgur cron is added, update this row. |

---

## Audit notes (things to fix later, NOT bootstrap blockers)

1. `/opt/backups/pre-backup.sh` lines 18-21 still have stale Coolify export logic (`cp /data/coolify/source/.env ...`). Guarded by `|| true`, harmless, but should be removed in a future cleanup.
2. `/etc/fail2ban/jail.d/` has only Ubuntu defaults (`defaults-debian.conf`). No custom jails to back up — defaults install with the `apt install fail2ban` line.
3. UFW rule #5 (`8000/tcp DENY # Coolify raw port`) carries a stale comment. The DENY itself is defensible (defense-in-depth) but the comment should retitle.

---

## End-state contract — bootstrap-hub.sh is done when

1. `wg show wg0` shows 2 peers handshaking (vps2 + vps3)
2. `docker ps | wc -l` ≥ 29 (matches vps1 inventory)
3. `curl -s https://status.vps1.ocoron.com` returns the Gatus dashboard
4. `psql -h localhost -U postgres -c '\l'` lists `glitchtip`, `site_provisioner`
5. Telegram bot replies to a probe message (`/status` or similar)
6. **Backrest can list ≥ 1 snapshot from the new hub** (`docker exec backrest /bin/restic snapshots | wc -l` ≥ 2 incl. header) — closes the W2 loop: backup chain still works POST-DR, so the next DR remains possible.
7. Wall-clock from "fresh VPS" to here: target ≤ 90 min on a 100 Mbit link.

Anything short of all 7 = drill failed = bootstrap-hub.sh has a gap.
