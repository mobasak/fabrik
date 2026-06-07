# VPS Bootstrap Automation

**Last Updated:** 2026-06-07 (Trio Phase 2+3 LIVE on full fleet since 2026-06-06; **4 spoke deps now BAKED INTO `bootstrap-vps.sh` 2026-06-07** — step_02 apt installs `python3-venv` + `python3-pip`, step_14a installs Node.js 22 + `@anthropic-ai/claude-code` via npm, step_14b installs `python-telegram-bot==22.7` via pip, step_14 mkdir block adds `chown ozgur:ozgur /opt/fabrik /opt/fabrik/scripts /opt/fabrik/logs`. All 4 deps validated end-to-end via DR drill #2 on Vultr 2026-06-07: 3m 13s wall-clock, 9.3× under the ≤30 min target, 15/15 substantive end-state checks. Both `bootstrap-vps.sh` + `bootstrap-hub.sh` preflights gained a **safe-rerun trap** that detects `root@<ip>` failing while `ozgur@<ip>` succeeds and emits an actionable "re-run as ozgur@" error BEFORE the 3rd-retry would trigger fail2ban — encoded in rule pack `.windsurf/rules/core/90-bootstrap-scripts.md` Rule 1.)
**Last probe report:** [`probe-reports/infra-probe-2026-06-07T20-20Z.yaml`](probe-reports/infra-probe-2026-06-07T20-20Z.yaml)
**Status:** Spoke bootstrap **shipped + verified on vps2 + vps3**; hub bootstrap remains manual (documented below)

## What's actually done

The bootstrap automation that was planned in 2026-05 is now real for spokes. The single command:

```bash
./scripts/bootstrap/bootstrap-vps.sh ozgur@<new-vps> vpsN
```

takes a fresh GreenCloudVPS Ubuntu 24.04 instance to a state where it's a fully-joined Fabrik mesh spoke. Verified against vps2 + vps3 on 2026-05-31 (commits `c838a03`, `f853a50`).

Full reference: [`scripts/bootstrap/README.md`](../../scripts/bootstrap/README.md).

### What `bootstrap-vps.sh` does (13 steps, post-W16)

1. Create `ozgur` user, install SSH key, grant NOPASSWD sudo — verified working before disabling root SSH
2. Harden SSH (PermitRootLogin no, PasswordAuthentication no) — drop-in must be `00-fabrik-hardening.conf` (NOT `99-`), since Ubuntu cloud-init's `50-cloud-init.conf` wins in first-match-wins order. The script verifies effectiveness via `sshd -T` post-edit to catch the override silently. (Trap surfaced live on the hub 2026-06-02 — fleet drift fixed in the same session.)
3. Install UFW + fail2ban; open 22/80/443/51820 (hardened 2026-05-31 for Lesson 68 — explicitly handles the `rc`-state edge case where a prior `apt remove ufw` leaves config files but no binary; self-verifies `command -v ufw` + `dpkg ii` + `ufw status: active` before returning)
4. Install Docker + log rotation; create `fabrik` external network
5. Install Wireguard + iptables-persistent
6. Generate Wireguard keypair on the spoke (private key never leaves)
7. Register the spoke as a peer on vps1's `wg0.conf` (over the dev machine's `ssh vps` alias to the hub)
8. Render the spoke's `wg0.conf` with the hub's endpoint
9. Bring up `wg-quick@wg0`
10. PMTU probe (fallback MTU=1380 then 1300 if 1420 fails)
11. Apply DOCKER-USER iptables chain rules
12. Deploy monitoring agents — `node-exporter` + `cadvisor` + `promtail` configured to ship to vps1's Prometheus + Loki over mesh
13. **(NEW, W16 2026-06-02)** Deploy spoke Traefik — renders 3 templates into `/opt/traefik/{compose.yaml,traefik.yml,dynamic/authelia.yml}` and brings up the stack. The compose template carries the **W15 `labels:` block** (`traefik.enable=true` + `traefik.http.middlewares.gzip.compress=true`) so the `gzip@docker` middleware that the Fabrik orchestrator emits on every router is defined on the spoke from minute one. Templates diffed byte-perfect against the live state on vps2 + vps3.
14. **(NEW, W16-DNS 2026-06-02)** Create DNS records via site-provisioner — probes the spoke's public IPv4 (`curl -4 ifconfig.me`, `ipv4.icanhazip.com` fallback), then SSHes to vps1 and `curl POST`s `https://provision.vps1.ocoron.com/api/cloudflare/dns/ocoron.com/subdomain` twice (apex + wildcard). Calls go through `ensure_record()` so re-runs return `action: unchanged` instead of touching Cloudflare. The call goes via vps1 because (a) site-provisioner's IP allowlist includes vps1's public IP but not dev-WSL's, and (b) the production `API_KEY` lives in `/opt/site-provisioner/.env` on vps1 and never travels.
15. **(Trio Phase 2 — code in `step_14_install_sysadmin_pack`, LIVE on vps2 + vps3 since 2026-06-06 + BAKED INTO SCRIPT 2026-06-07)** Install the per-host AI sysadmin pack: `vps-sysadmin-bot.service` + `/etc/cron.d/vps-sysadmin` (hash-staggered minutes per host via sha1sum-of-HOST_NAME modulo). Operator-gated on `claude auth login` + @BotFather token in `/opt/fabrik/.env.sysadmin`. Now also installs Node.js 22 + Claude Code CLI (step_14a) and `python-telegram-bot==22.7` (step_14b) — see "Spoke deps baked into bootstrap" block below.
16. **(Trio Phase 3 — code in `step_15_install_aro_wake`, LIVE on vps2 + vps3 since 2026-06-06)** Install `aro-wake.service` (FastAPI on `0.0.0.0:8201`) with `_dedup`/`_HOP_LIMIT`/`_FWD_SUPPR`/`_STORM_BREAKER` loop guards + Prometheus `/metrics` exposition. `ARO_WAKE_PEER_HOSTS` rendered as CSV (NOT JSON — systemd strips embedded quotes).

**Spoke deps BAKED INTO `bootstrap-vps.sh` 2026-06-07 (all validated live via DR drill #2 in 3m 13s):**

- **step_02** apt install (NEW): `python3-venv` + `python3-pip` — needed by step_15 (`python3 -m venv` requires `ensurepip` from python3-venv) + step_14b (system pip for `python-telegram-bot`)
- **step_14a** (NEW): Node.js 22 + `@anthropic-ai/claude-code` via npm — `curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && apt-get install -y nodejs && npm install -g @anthropic-ai/claude-code`. Idempotent — skips if `command -v claude` succeeds.
- **step_14b** (NEW): `python-telegram-bot==22.7` via `sudo pip install --break-system-packages` (Ubuntu 24.04 PEP 668). Idempotent — skips if `python3 -c "import telegram"` succeeds.
- **step_14 mkdir block** (NEW): `sudo chown ozgur:ozgur /opt/fabrik /opt/fabrik/scripts /opt/fabrik/logs` so step_15's `sudo -u ozgur python3 -m venv /opt/fabrik/.venv-aro-wake` can write to `/opt/fabrik/`.

**Preflight safe-rerun trap added 2026-06-07** (both `bootstrap-vps.sh` + `bootstrap-hub.sh`): detects when SSH to `root@HOST` fails AND `ozgur@HOST` works (meaning step_01 has already run on this host), aborts the script BEFORE the 3rd-retry trips fail2ban, and emits an actionable "Re-run as the sudoer: $0 ozgur@HOST ..." error. Walking past this trap was the #1 source of DR-drill failure in Drill #1 — encoded in rule pack [`.windsurf/rules/core/90-bootstrap-scripts.md`](../../.windsurf/rules/core/90-bootstrap-scripts.md) Rule 1.

### What's NOT in the script (deferred / out of scope)

- ~~**DNS records** for `*.vps<N>.ocoron.com` — stubbed at step 14~~ — ✅ shipped at step 14 (W16-DNS 2026-06-02). Idempotent via `ensure_record()`; re-runs return `action: unchanged`.
- ~~**Tenant Traefik** on each spoke is deployed manually~~ — ✅ shipped at step 13 (W16, 2026-06-02). The "manual one-time Traefik deploy" prerequisite is retired.
- **`fabrik apply --target-vps vps2 specs/services/foo.yaml`** — ✅ shipped 2026-05-31 (W-Multi M4) + 2026-06-02 (W3 + W14 + W15). Full spoke-deploy round-trip verified live against vps2.

## Hub (vps1) — now scripted (2026-06-01)

**The hub IS reproducible from a single script** as of 2026-06-01. Until then it was a copy-and-customize manual runbook (the prior paragraph here said `docs/operations/disaster-recovery.md § Path B`); now it's `scripts/bootstrap/bootstrap-hub.sh` — 18 idempotent steps + numbered preflight, target wall-clock ≤ 90 min from fresh VPS to "all 31 containers running, Telegram bot answering, Gatus all green."

**Single-source operator doc:** [`vps-hub-rebuild.md`](vps-hub-rebuild.md). That doc holds the 5-command operator runbook, the per-step walkthrough, the 7-check end-state contract, and the same-IP vs new-IP decision.

The hub script and the spoke script share `bootstrap-config.sh` (locked WG/firewall constants) but have different step counts (12 for spoke, 18 for hub) because the hub also restores from Backrest + W9 and handles the Cloudflare DNS rewrite. The script does what the manual paragraph used to describe — install Docker, create `fabrik` network, bring up `/opt/<svc>/compose.yaml` stacks in dependency order, restore from B2, install Wireguard hub + open UDP 51820 — but verifies each step instead of trusting the operator to remember.

## Operating notes (for now)

### Provisioning a new spoke

1. Buy a GreenCloudVPS instance (see `docs/infrastructure/vps-complete-inventory.md` § vps2 / vps3 for spec patterns; `BudgetKVMCUK-3` for budget hosts in UK).
2. Install Ubuntu 24.04 LTS in VirtFusion with your SSH key attached, swap = 2 GB, VNC disabled, DNS = `1.1.1.1` + `8.8.8.8`.
3. Confirm `ssh root@<new-ip>` works (key-only). Add a `Host vps<N>` block to `~/.ssh/config` on the dev machine.
4. Run `./scripts/bootstrap/bootstrap-vps.sh root@<new-ip> vps<N>` — ~5–10 min.
5. Verify mesh: `ssh vps<N> ping -c 3 10.99.0.1` (expect 130–150 ms RTT cross-region).
6. Verify Prometheus picks up the new spoke: `ssh vps 'sudo docker exec prometheus wget -qO- http://localhost:9090/api/v1/label/host/values'` should include `vps<N>`. If not, edit `/opt/monitoring/configs/prometheus/prometheus.yml` to add the new spoke's `10.99.0.<N>:<port>` targets to the spoke jobs.
7. ~~Manual one-time: deploy Traefik on the new spoke~~ — **NO LONGER NEEDED.** As of W16 (2026-06-02), step 13 of `bootstrap-vps.sh` deploys Traefik automatically using the 3 templates under `scripts/bootstrap/templates/traefik*.template`. The new spoke is ready for `fabrik apply` immediately after the script returns.

### Bootstrap script idempotency

Safe to re-run after partial failures:

- Step 00 (`ozgur` user creation) — `useradd` guarded by `id` check; key install uses `grep -qxF` before append
- Step 06 (peer registration) — uses a regex marker on hub-side wg0.conf; idempotent replace
- Step 11 (monitoring agents) — `docker compose up -d --remove-orphans`

If a step fails partway, fix it, then re-run the script with the same arguments. Earlier successful steps detect existing state and short-circuit.

## File manifest

| Path | Purpose |
| :--- | :--- |
| [`scripts/bootstrap/bootstrap-vps.sh`](../../scripts/bootstrap/bootstrap-vps.sh) | The actual script (522 lines) |
| [`scripts/bootstrap/bootstrap-config.sh`](../../scripts/bootstrap/bootstrap-config.sh) | Locked params (subnet, port, MTU, mesh-only port list, sudoer username) |
| [`scripts/bootstrap/templates/wg0.spoke.conf.template`](../../scripts/bootstrap/templates/wg0.spoke.conf.template) | Spoke Wireguard config |
| [`scripts/bootstrap/templates/wg-peer.append.template`](../../scripts/bootstrap/templates/wg-peer.append.template) | `[Peer]` block appended to hub on peer-add |
| [`scripts/bootstrap/templates/iptables-mesh.sh.template`](../../scripts/bootstrap/templates/iptables-mesh.sh.template) | DOCKER-USER chain rules |
| [`scripts/bootstrap/templates/monitoring-agent.compose.yaml.template`](../../scripts/bootstrap/templates/monitoring-agent.compose.yaml.template) | Spoke node-exporter + cadvisor + promtail |
| [`scripts/bootstrap/templates/promtail.yaml.template`](../../scripts/bootstrap/templates/promtail.yaml.template) | Spoke promtail config — pushes to `10.99.0.1:3100` |
| [`scripts/bootstrap/README.md`](../../scripts/bootstrap/README.md) | Architecture map + future usage |

## Lessons captured (from the bootstrap shipping process)

- **Lesson 65** — three bugs surfaced during vps2/vps3 bootstrap: `PermitRootLogin no` locked us out before sudoer existed (now: create user first, verify, then disable root); `ssh -G` returns `id_rsa.pub` even when `id_ed25519` is in use (now: scan candidate list); `wg syncconf <(...)` process substitution doesn't survive SSH single-quote wrapping (now: tempfile in `/run/`). Full writeup: `docs/LESSONS_LEARNT.md § Lesson 65`.
- **Lesson 11** — silence the `ContainerDown` alert rule before any planned downtime > 2 min (otherwise Telegram floods).
- **Single-operator threat model** — don't add CIS-checklist security hardening (perm tightening, rotation theater) without naming a realistic attacker.

## Pending follow-ups for the bootstrap pipeline

1. ~~**Define the `gzip` Traefik middleware on each spoke (W15).**~~ — ✅ **SHIPPED 2026-06-02.** Added a `labels:` block to the Traefik service in `/opt/traefik/compose.yaml` on both spokes declaring `traefik.enable=true` (required because spoke `traefik.yml` has `providers.docker.exposedByDefault: false`) **and** `traefik.http.middlewares.gzip.compress=true`. Recreate Traefik (~5 s downtime). First end-to-end spoke deploy succeeded immediately afterwards: `https://canary.vps2.ocoron.com` returned HTTP 200 with a fresh Let's Encrypt cert (first LE issuance on a spoke). New `compose.yaml` snapshotted into B2 via host-state plan on both spokes (count 4 → 5).
2. ~~**Bake the full spoke Traefik compose into the script.**~~ — ✅ **SHIPPED 2026-06-02 (W16).** Added `step_12_install_spoke_traefik()` in `bootstrap-vps.sh` driving 3 new templates (`traefik.compose.yaml.template`, `traefik.yml.template`, `traefik-dynamic-authelia.yml.template`). New `FABRIK_LE_EMAIL` constant in `bootstrap-config.sh`. Existing DNS step renamed step 13. `--verify` mode gained a Traefik row that reports container state + gzip-middleware-label presence. Idempotency verified live on vps2 (re-run produced `Container traefik Running`, no recreate, uptime preserved).
3. ~~**Add `tag: "{{.Name}}"` to spoke `daemon.json`**~~ — ✅ **SHIPPED 2026-06-02 (W4-pre).** `bootstrap-vps.sh` step_03 emits the field; vps2 + vps3 had docker restarted to apply it live; future spokes inherit on first bootstrap.
4. ~~**Wire DNS step (now step 13) to call site-provisioner.**~~ — ✅ **SHIPPED 2026-06-02 (W16-DNS).** Probes spoke's public IPv4, then SSHes to vps1 and calls `https://provision.vps1.ocoron.com/api/cloudflare/dns/ocoron.com/subdomain` twice (apex + wildcard). Idempotent via `ensure_record()` — re-runs return `action: unchanged`. Live-verified against vps2 + vps3.
5. **Hub bootstrap (W-Multi M0)** — multi-hour ticket; deferred until first vps1 rebuild. ([`scripts/bootstrap/bootstrap-hub.sh`](../../scripts/bootstrap/bootstrap-hub.sh) shipped 2026-06-01 as part of the DR-in-hours track, but it has not been drilled against a fresh VPS — see [`vps-hub-rebuild.md`](vps-hub-rebuild.md).)
6. ~~**Bake the 4 spoke deps discovered 2026-06-06 into `bootstrap-vps.sh`**~~ — ✅ **SHIPPED 2026-06-07** (commit `175ea69`). `bootstrap-vps.sh` step_02 now installs `python3-venv` + `python3-pip`; new step_14a installs Node.js 22 + `@anthropic-ai/claude-code` (idempotent via `command -v claude`); new step_14b installs `python-telegram-bot==22.7` (idempotent via `python3 -c "import telegram"`); step_14 mkdir block now chowns `/opt/fabrik /opt/fabrik/scripts /opt/fabrik/logs` to `ozgur:ozgur`. Drilled clean end-to-end 2026-06-07 on a Vultr droplet (3m 13s wall-clock, 15/15 substantive checks).
7. ~~**Bake the spoke↔spoke wg0 routing rule** into hub bootstrap or post-bootstrap step~~ — ✅ **SHIPPED 2026-06-07** (commit `175ea69`). `bootstrap-hub.sh` step_07 now runs `sudo ufw route allow in on wg0 out on wg0` as a backstop, so spoke↔spoke routing works after a hub rebuild without a manual after-step.

---

## Original 2026-05-20 plan (archived for reference)

The original plan from `vps-captured-state-20260520.txt` proposed a single end-to-end script. Most of it materialized; the parts that didn't are listed above as "Pending follow-ups". The plan-era doc has been superseded — no longer maintained.

State capture from that era: `docs/infrastructure/vps-captured-state-20260520.txt` (737 lines, vps1 only, Coolify-era — historical reference).
