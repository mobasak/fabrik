# VPS Bootstrap Automation

**Last Updated:** 2026-05-31 (replaces the 2026-05-20 Coolify-era plan; the spoke-bootstrap script is now live and tested)
**Status:** Spoke bootstrap **shipped + verified on vps2 + vps3**; hub bootstrap remains manual (documented below)

## What's actually done

The bootstrap automation that was planned in 2026-05 is now real for spokes. The single command:

```bash
./scripts/bootstrap/bootstrap-vps.sh ozgur@<new-vps> vpsN
```

takes a fresh GreenCloudVPS Ubuntu 24.04 instance to a state where it's a fully-joined Fabrik mesh spoke. Verified against vps2 + vps3 on 2026-05-31 (commits `c838a03`, `f853a50`).

Full reference: [`scripts/bootstrap/README.md`](../../scripts/bootstrap/README.md).

### What `bootstrap-vps.sh` does (12 steps)

1. Create `ozgur` user, install SSH key, grant NOPASSWD sudo — verified working before disabling root SSH
2. Harden SSH (PermitRootLogin no, PasswordAuthentication no)
3. Install UFW + fail2ban; open 22/80/443/51820
4. Install Docker + log rotation; create `fabrik` external network
5. Install Wireguard + iptables-persistent
6. Generate Wireguard keypair on the spoke (private key never leaves)
7. Register the spoke as a peer on vps1's `wg0.conf` (over the dev machine's `ssh vps` alias to the hub)
8. Render the spoke's `wg0.conf` with the hub's endpoint
9. Bring up `wg-quick@wg0`
10. PMTU probe (fallback MTU=1380 then 1300 if 1420 fails)
11. Apply DOCKER-USER iptables chain rules
12. (step 11 in code) Deploy monitoring agents — `node-exporter` + `cadvisor` + `promtail` configured to ship to vps1's Prometheus + Loki over mesh

### What's NOT in the script (deferred / out of scope)

- **DNS records** for `*.vps<N>.ocoron.com` — blocked on Cloudflare API token refresh + site-provisioner redeploy
- **Tenant Traefik** on each spoke is **now deployed manually** (see `docs/infrastructure/vps-complete-inventory.md` § vps2 inventory) — pending: bake it into a bootstrap step
- **`fabrik apply --target-vps vps2 specs/services/foo.yaml`** — needs spec model + CLI changes (~2-3 h code change); tracked as W-Multi M4 / M5

## What's still manual: the hub (vps1)

The hub itself (vps1) was built incrementally over months and the current state is not reproducible from a single script. The "hub bootstrap" would need to:

- Install Docker + create `fabrik` network
- Bring up postgres-main, redis-main, traefik, authelia, monitoring stack, etc. — each `/opt/<svc>/compose.yaml`
- Restore data from B2 or a fresh provision
- Install Wireguard hub + open UDP 51820

For now, hub recovery is a copy-and-customize of `docs/operations/disaster-recovery.md § Path B — B2 cold restore`. Writing a true hub bootstrap script is on the platform-to-A+ plan as W-Multi M0 (~4 h work).

## Operating notes (for now)

### Provisioning a new spoke

1. Buy a GreenCloudVPS instance (see `docs/infrastructure/vps-complete-inventory.md` § vps2 / vps3 for spec patterns; `BudgetKVMCUK-3` for budget hosts in UK).
2. Install Ubuntu 24.04 LTS in VirtFusion with your SSH key attached, swap = 2 GB, VNC disabled, DNS = `1.1.1.1` + `8.8.8.8`.
3. Confirm `ssh root@<new-ip>` works (key-only). Add a `Host vps<N>` block to `~/.ssh/config` on the dev machine.
4. Run `./scripts/bootstrap/bootstrap-vps.sh root@<new-ip> vps<N>` — ~5–10 min.
5. Verify mesh: `ssh vps<N> ping -c 3 10.99.0.1` (expect 130–150 ms RTT cross-region).
6. Verify Prometheus picks up the new spoke: `ssh vps 'sudo docker exec prometheus wget -qO- http://localhost:9090/api/v1/label/host/values'` should include `vps<N>`. If not, edit `/opt/monitoring/configs/prometheus/prometheus.yml` to add the new spoke's `10.99.0.<N>:<port>` targets to the spoke jobs.
7. **Manual one-time:** deploy Traefik on the new spoke (`/opt/traefik/compose.yaml` + `traefik.yml` + `dynamic/authelia.yml`) — same pattern used for vps2 + vps3. Templates documented in `docs/infrastructure/vps-complete-inventory.md` and lifted from vps1's working config.

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

1. **Bake spoke Traefik into step 11 or a new step 11.5.** Currently manual. ~30 min to template + add to script.
2. **Add `tag: "{{.Name}}"` to spoke `daemon.json`** so promtail extracts `container_name` labels. ~5 min.
3. **Add DNS step (12)** once Cloudflare API token is refreshed + site-provisioner is redeployed.
4. **Hub bootstrap (W-Multi M0)** — multi-hour ticket; deferred until first vps1 rebuild.

---

## Original 2026-05-20 plan (archived for reference)

The original plan from `vps-captured-state-20260520.txt` proposed a single end-to-end script. Most of it materialized; the parts that didn't are listed above as "Pending follow-ups". The plan-era doc has been superseded — no longer maintained.

State capture from that era: `docs/infrastructure/vps-captured-state-20260520.txt` (737 lines, vps1 only, Coolify-era — historical reference).
