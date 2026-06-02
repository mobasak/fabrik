# VPS Fleet — Status Snapshot

**Last Updated:** 2026-06-01 evening (W2 + W11 SHIPPED — fleet-wide symmetric DR: 3 Backrest stacks → B2, `bootstrap-hub.sh` + `bootstrap-spoke-restore.sh` end-to-end)
**Snapshot taken:** 2026-06-01 19:02 UTC (live probe via `scripts/audit_infra_vs_docs.py` against all 3 hosts)
**Hosts:** vps1 (LA, hub) · vps2 (Coventry UK, spoke) · vps3 (Coventry UK, spoke)
**Deploy model:** SSH + Docker Compose (no Coolify — removed 2026-05-30)

> Companion docs: [`vps-complete-inventory.md`](vps-complete-inventory.md) for what runs where (architectural source of truth) · [`vps-urls.md`](vps-urls.md) for how to reach things. This file is a point-in-time *health* snapshot.

---

## Fleet at a glance

| Host | Role | Public IP | Mesh IP | RAM | Disk | Containers | Uptime |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| vps1 | Hub (LA) | 172.93.160.197 | 10.99.0.1 | 11.6 Gi (3.8 Gi used) | 108 GB (28 GB / 26 %) | 29 | 1 d 21 h 41 m |
| vps2 | Spoke (Coventry UK) | 96.9.214.128 | 10.99.0.2 | 7.7 Gi (867 Mi used) | 58 GB (5.8 GB / 11 %) | 5 | 1 d 7 h 30 m |
| vps3 | Spoke (Coventry UK) | 104.128.190.151 | 10.99.0.3 | 7.7 Gi (855 Mi used) | 58 GB (5.8 GB / 11 %) | 5 | 1 d 7 h 31 m |

| Health signal | State |
| :--- | :--- |
| Wireguard mesh | ✅ both spokes handshaking in the last ~2 min |
| Cross-Atlantic mesh RTT | ✅ 133–134 ms, 0 % loss |
| Prometheus scrape targets | ✅ 18 / 18 up across 15 jobs (12 vps1 + 3 spoke job-groups) |
| Mesh-bound shared infra on vps1 (`5432, 6379, 8000, 9091, 3100`) | ✅ all 5 listening on `10.99.0.1` |
| Spoke DNS resolving | ✅ `vps2.ocoron.com`, `*.vps2`, `vps3.ocoron.com`, `*.vps3` all return correct A records |
| Cloudflare API token in `/opt/fabrik/.env` | ✅ verified active (refreshed today) |
| Authelia access-control rules | 10 (live in `/opt/authelia/config/configuration.yml`) |
| site-provisioner | ⚠ running healthy on vps1, but **interim manual stand-up** — `fabrik apply` pipeline not yet ready |
| Backrest — vps1 hub | ✅ **4 active plans** (`postgres-dumps` 02:00, `docker-volumes` 03:00, `opt-configs` 03:00, `host-state` 03:30). Restic repo `a256277c45`. First snapshots: 117 MiB on B2 (612 MiB raw, 5.23×). |
| Backrest — vps2 spoke (W11) | ✅ **2 active plans** (`host-state` 02:00, `opt-configs` 02:30). Restic repo `56b40b8c84` at `vps1-ocoron-backups/spokes/vps2/`. First snapshots: 16.9 KiB on B2 (2.31×). Independent restic password mirrored via W9. |
| Backrest — vps3 spoke (W11) | ✅ **2 active plans** (same schedule as vps2). Restic repo `350e752618` at `vps1-ocoron-backups/spokes/vps3/`. First snapshots: 16.5 KiB on B2 (2.33×). |
| Hub disaster-recovery | ✅ **Scripted** via [`bootstrap-hub.sh`](../../scripts/bootstrap/bootstrap-hub.sh) — 18 idempotent steps, target wall-clock ≤ 90 min. **Drill pending.** Operator doc: [`vps-hub-rebuild.md`](vps-hub-rebuild.md). |
| Spoke disaster-recovery | ✅ **Scripted** via [`bootstrap-spoke-restore.sh`](../../scripts/bootstrap/bootstrap-spoke-restore.sh) — 13 steps, ≤ 30 min target, **preserves Wireguard identity** (hub peer-table unchanged through outage). **Drill pending.** Operator doc: [`vps-spoke-rebuild.md`](vps-spoke-rebuild.md). |
| Credential recovery (`/opt/fabrik/.env`) | ✅ **W9 shipped 2026-06-01.** Inotify + systemd watcher (`fabrik-dr-watcher.service`) pushes every change to private `mobasak/fabrik-dr-store` within seconds; daily safety-net cron + reboot catch-up + weekly self-test. **Sysadmin token added to scope** via SSH-pull (W9 extension, same day). See [`docs/operations/credential-recovery.md`](../operations/credential-recovery.md). |
| Backups | ✅ same as Backrest plans row — first real backup chain since the 2026-05-31 wipe. |

---

## 2026-06-02 evening — fleet hardening pass + image-broker retirement + T-P2 sidecar ships

End-to-end audit-prompt validation against live state surfaced + closed four fleet defects, plus shipped T-P2 sidecar artifacts 2-8 in `/opt/fabrik-lib/watchdog/sidecar/`.

**Live changes on vps1:**

- **SSH posture aligned with spokes.** `/etc/ssh/sshd_config.d/50-cloud-init.conf` had `PasswordAuthentication yes` (Ubuntu cloud-init drop-in) and was winning over the main `sshd_config` in alphabetical-glob order. Spokes already had `no`. Patched the drop-in to `no`, `sudo systemctl reload ssh`, verified `sshd -T` shows `passwordauthentication no` across all 3 hosts. Key-only auth verified in a fresh SSH session before relying on the change.
- **Hub Backrest `restic forget` lock contention fixed.** Three of four plans were failing the post-backup `forget` step nightly with "repository is already locked" — backups themselves ran fine but the pruning ran ~500ms after the backup lock was taken and conflicted. Added `--retry-lock=10m` to the `b2-vps1` repo `flags` in `/opt/backrest/config/config.json`; backrest container restarted. Confirmation deferred to next nightly window.
- **`.restic-password` mode 711 → 600** (spokes were already 600 — fleet-drift fix, single chmod).
- **Hub promtail now tags its own stream `host=vps1`.** Loki used to return only `["vps2","vps3"]` for the `host` label — hub stream was unlabelled because the static `host:` was missing from the `containers` scrape job. Added the label, restarted promtail, Loki now returns `["vps1","vps2","vps3"]`. Repo copy at `configs/promtail/promtail-config.yaml` synced (was drifted, also missing the Coolify-residue container-name drop rule).
- **`image-broker` spec retired.** Spec at `specs/services/image-broker.yaml` was orphaned — no `/opt/image-broker/`, no container, NXDOMAIN at Cloudflare; only the 2 Authelia rules survived from a prior registration. Removed the spec + `.fabrik/state/image-broker.json` + `infra/image-broker/` + 2 rows in PORTS.md + 3 script entries (`generate_vps_inventory.py`, `seed_real_ports.py`, `audit_all_projects.py`) + the 2 live Authelia rules. Authelia restarted via `docker restart authelia` → healthy. GlitchTip project id=66 left in place; safe to delete in the UI when convenient. LE cert in `acme.json` left to expire naturally (~90d).

**Audit-prompt fixes** — patched bugs in 6 of 8 prompts after live-run validation: 01 (false-negative hub `.env` probe), 03 (grep leading-dash, cloud-init override visibility), 04 (`conntrack` not installed → `sysctl`), 05 (Loki via wrong network, Grafana fake-Bearer auth, GlitchTip wget-in-python-image), 06 (B2 repo name singular), 07 (hub SSH alias mapping, heredoc python parse, Authelia all-matches reporter), 08 (hub promtail filename). See `docs/infrastructure/audit-prompts/` for the per-file patches.

**T-P2 watchdog platform — COMPLETE 2026-06-03. 15 / 15 artifacts shipped.** Three layers: (a) sidecar at `/opt/fabrik-lib/watchdog/sidecar/` (~2,134 lines: agent state machine, llm_client Claude Code primary + OpenRouter fallback, actions 6 Tier A + 3 Tier B + 1 Tier C handlers, state.py SQLite with 4 tables, PreToolUse.sh hook, claude-settings template with 10-capability v1 lock, vendored cost_budget.py); (b) orchestrator wiring at `src/fabrik/orchestrator/infrastructure.py` (`_register_watchdog` resolver + dispatch, +63 lines) + driver at `src/fabrik/drivers/watchdog.py` (387 lines: vendor + render + build + compose overlay + bring-up); (c) operator-facing surface — emitter library at `/opt/fabrik-lib/watchdog/emitter/`, rule pack at `.windsurf/rules/core/60-watchdog.md`, fabrik-lib README modules-table row, test spec at `specs/services/watchdog-test.yaml`. End-to-end verification via `spec_loader.load_spec` → `resolve_applicability` → `WatchdogDriver().provision(dry_run=True)` chain returns `{'status': 'dry-run', 'image_tag': 'fabrik/watchdog:watchdog-test'}` and the resolver prints `watchdog: RUNS (spec.watchdog.enabled=true)`. 40/40 orchestrator tests green. Cross-process emitter→sidecar contract verified by integration smoke. **Next: T-P3 (self-healing synthesis, 1 day, no subplan needed per parent plan).**

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

**Running:** ✅ container `site-provisioner` on vps1, healthy. Migrations applied. CF + DB connectivity ok. `/health` returns 200.

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
site-provisioner       healthy  (NEW today — interim manual; see § site-provisioner status)
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

**Last probe report:** [`probe-reports/infra-probe-2026-06-01T22-50Z.yaml`](probe-reports/infra-probe-2026-06-01T22-50Z.yaml) (post-W14 sweep)

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

### Prometheus — 18 / 18 targets up across 15 jobs (re-verified 2026-06-01T19:50Z post-W8)

vps1-local (12 jobs / 12 targets — verified against `/api/v1/targets`): `alertmanager`, `authelia`, `cadvisor`, `gatus`, `grafana`, `loki`, `meilisearch`, `node`, `postgres`, `prometheus`, `pushgateway`, `redis`.

Spokes (3 jobs / 6 targets): `node-spokes` (2), `cadvisor-spokes` (2), `promtail-spokes` (2). **Note: spoke scrapes were silently 0/6 from 2026-05-31 evening (W1 UFW ship) until 2026-06-01 evening (W8 found + fixed) — added `ufw allow from 10.99.0.0/24` on each spoke + into `bootstrap-vps.sh` step_02.** Trust-the-mesh rule, single-operator threat model.

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

- **Alertmanager → Apprise → Telegram** for vps1 alerts.
- **`spoke_health` rule group active** — `SpokeDown`, `SpokeHighCPU`, `SpokeHighRAM`. Group joins use `on(host)` to avoid the many-to-many trap that surfaced when the `host` label was added.
- **Discipline (Lesson 11):** silence the `ContainerDown` rule before any planned op that takes containers down > 2 min, or Telegram floods.

### GlitchTip

- Public UI: `https://errors.vps1.ocoron.com` (Authelia 2FA).
- Internal alias for SDKs: `http://glitchtip-web:8000/<project_id>` (Docker DNS on `fabrik` network).
- Mesh ingest for spoke tenants: `http://10.99.0.1:8000/<project_id>` (bound today).
- Storage: `glitchtip` DB on `postgres-main`; events retained 90 d.
- Project IDs unchanged from Coolify-era audit (captcha 65, translator 67, emailgateway 68, file-api 69, file-worker 70, site-provisioner 24). Project id=66 was for image-broker, orphaned after the spec removal 2026-06-02 — safe to delete in the GlitchTip UI.

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

**Live state:** Backrest config has **1 repo retained + 0 plans**. B2 bucket `vps1-ocoron-backups` is empty (preserved for reuse). Intentional, post-2026-05-31 cleanup.

| Item | Detail |
| :--- | :--- |
| Repo ID | `b2-vps1` |
| Repo URI | `s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups` |
| Repo flags | `--compression=auto` |
| Plans | 0 |
| Container | `backrest` (running, 512 MB limit) |
| Off-VPS creds in `/opt/fabrik/.env` | `BACKREST_RESTIC_PASSWORD` ✓, `B2_KEY_ID` ✓, `B2_APPLICATION_KEY` ✓ |

Closing the "credentials only on vps1" DR weakness means the dev WSL can stand backups back up from scratch.

**Credential off-site mirror (W9 shipped 2026-06-01).** The dev WSL was itself a single point of failure until W9: `/opt/fabrik/.env` (including the irrecoverable `BACKREST_RESTIC_PASSWORD`) existed only on disk there. Now mirrored to **`mobasak/fabrik-dr-store`** (private GitHub repo) within seconds of every change via `fabrik-dr-watcher.service` (inotify) + daily safety-net cron + `@reboot` catch-up + weekly recovery self-test. One-command recovery on a fresh WSL: `gh repo clone mobasak/fabrik-dr-store && sudo cp fabrik-dr-store/env/latest /opt/fabrik/.env`. Full runbook: [`docs/operations/credential-recovery.md`](../operations/credential-recovery.md).

When backups are reconfigured:

- Plans to recreate: `postgres-dumps` (`/opt/backups/pg_dump_*.sql`), `docker-volumes` (`/var/lib/docker/volumes/`), `opt-configs` (`/opt/<svc>/{compose.yaml,.env}`).
- Failure-hook URL: `http://apprise:8000/notify/<tag>` (the old `apprise-<uuid>:8000` hostname is broken; Issue 1 in inventory).
- Schedule postgres-dumps AFTER the host pg_dump cron, not concurrent (44 % race-condition failures previously).
- Spoke backups: defer until vps2/vps3 actually hold non-replicated data.

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
| 1 | Backrest failure-notification hook references the old Coolify-era apprise UUID hostname | Cosmetic until backup plans exist; backup-failure alerts wouldn't reach Telegram | Fix on next plan creation: replace `apprise-<uuid>` with `apprise` |
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

1. **T-P2 Watchdog Platform — 13 of 15 artifacts remaining.** Artifacts 1 (`WatchdogConfig` spec field, including the 3-field amendment locked during artifact 2 review: `deadman_timeout_seconds`, `external_docs_enabled`, `propose_fix_prs`) + 2 (`claude-settings.json.template` with the 10-capability v1 lock) both shipped 2026-06-02. Next: artifact 3 (`hooks/PreToolUse.sh`). Subplan + capability matrix: [`docs/development/plans/2026-05-30-ai-watchdog-platform-P2-subplan.md`](../development/plans/2026-05-30-ai-watchdog-platform-P2-subplan.md) § 4.6.
2. **Authelia rules for spoke admin dashboards** (when one exists — registrar is already FQDN-pattern-agnostic per W13 verify).
3. **Spoke tenant backups** (`docker-volumes-vpsN` + `postgres-dumps-vpsN` plans on spoke Backrest — gated on first actual tenant data landing).

---

## Verification log

### Probe report — 2026-06-01T22-50Z (post-W14)

Generated by `scripts/audit_infra_vs_docs.py`. Source YAML: [`probe-reports/infra-probe-2026-06-01T22-50Z.yaml`](probe-reports/infra-probe-2026-06-01T22-50Z.yaml). Captured after W14 shipped + spoke-canary live-verify on vps2 (deployed healthy, verifier 404 from W15 gap, rollback clean).

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

1. **vps1 `:8017` is `0.0.0.0`-bound, not loopback.** Prior inventory wording said "blocked from Docker via DOCKER-USER" — that's true for container→host traffic, false for internet→host. Reachable from the public net today; W5 of [`docs/development/plans/archived/2026-05-31-plan-fleet-hardening-and-doc-truth.md`](../development/plans/2026-05-31-plan-fleet-hardening-and-doc-truth.md) is the remediation.
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
