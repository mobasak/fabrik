# Fabrik bootstrap scripts

Sets up new GreenCloudVPS Ubuntu nodes as peers in the Fabrik multi-host mesh.

## Architecture (locked 2026-05-31)

- **Topology:** hub-and-spoke. vps1 is the hub. New VPSes (vps2, vps3, …) are spokes.
- **Mesh:** Wireguard, subnet `10.99.0.0/24`, port UDP `51820`, MTU `1420` (with PMTU probe + fallback).
- **Service pattern:** Pattern A — spokes are workload-only nodes. They reach `postgres-main`, `redis-main`, `glitchtip`, `meilisearch`, `authelia` on vps1 over the mesh (private IPs). No local databases on spokes.
- **DNS:** all DNS work goes through `site-provisioner` on vps1 (`provision.vps1.ocoron.com`). Bootstrap never touches Cloudflare/Namecheap APIs directly.
- **Auth:** subdomain-shaped SSO. Each VPS gets `auth.vpsN.ocoron.com` → vps1's Authelia. Cookies scoped to `*.vpsN.ocoron.com`.
- **Firewall:** three layers — bind services to mesh IP only + DOCKER-USER iptables chain + UFW for ports 22/80/443/51820.

## File map

```
scripts/bootstrap/
├── bootstrap-config.sh                # Shared variables (subnet, port, MTU, etc.)
├── templates/
│   ├── wg0.hub.conf.template          # vps1's Wireguard config
│   ├── wg0.spoke.conf.template        # spoke's Wireguard config
│   ├── wg-peer.append.template        # [Peer] block to append to hub on add-peer
│   └── iptables-mesh.sh.template      # DOCKER-USER chain ruleset
├── setup-wireguard-hub.sh             # M0c: vps1 hub setup (run from dev machine)
├── add-mesh-peer.sh                   # registers a new spoke with the hub
└── bootstrap-vps.sh                   # M1: spoke bootstrap, run from dev machine
```

(scripts marked M0c / M1 are written incrementally; see TodoWrite for current state.)

## Usage (future, once all scripts land)

```bash
# On the dev machine:
./scripts/bootstrap/bootstrap-vps.sh ozgur@vps2.greencloudvps.com vps2
# This will:
#   1. SSH into the new VPS
#   2. Install Docker + UFW + fail2ban + Wireguard
#   3. Generate a fresh WG keypair on the new VPS
#   4. Call vps1 (over your existing ssh vps alias) to register the peer
#   5. Pull peer config back, write /etc/wireguard/wg0.conf
#   6. Bring up wg0, verify mesh connectivity with PMTU probe
#   7. Install DOCKER-USER iptables rules
#   8. Drop minimal monitoring agents (promtail, node-exporter, cadvisor)
#   9. Print: "vps2 ready for `fabrik apply --target-vps vps2`"
```

## Safety modes

- `--dry-run` — prints every command without executing
- `--verify` — read-only checks only (no changes)
- All scripts are idempotent: re-running is safe.

## Testing protocol (M1b → M1d)

1. **Local multipass VMs** for tight iteration loop
2. **One throwaway GreenCloudVPS** for real-provider dry-run
3. **Actual vps2** only after #1 and #2 are clean

## Threat-model notes

The mesh is the trust boundary. Anything reachable on the mesh IP (postgres, redis, etc.) is implicitly trusted. The DOCKER-USER rules + bind-to-mesh-IP-only ensure the mesh is the *only* path from spokes to those services.

If a spoke's Wireguard private key is compromised, the attacker gains mesh access. Rotation procedure: regenerate the spoke's keypair, run `add-mesh-peer.sh --rotate` from the dev machine.

See `docs/operations/fabrik-lifecycle.md` § "Targeting a host — `--target-vps` (multi-host)" for the multi-host operations detail.
