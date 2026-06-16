# 03 — Security Hardening (fleet-wide, per-host probes)

**Last Updated:** 2026-06-06 (procedure unchanged from 2026-06-02; today's posture changes auditors should EXPECT and NOT flag: (a) all 3 hosts have new UFW allow rules `from 10.0.0.0/8 to any port 8201 proto tcp` AND `from 10.99.0.0/24 to any port 8201 proto tcp` for aro-wake reachability (docker bridge + wg0 peer access); (b) vps1 has new routed-policy rule `Anywhere on wg0 ALLOW FWD Anywhere on wg0` enabling spoke↔spoke transit — UFW default-DROP routed policy remains, so this does NOT enable public-internet egress relay (verifiable via `curl --interface wg0 https://1.1.1.1` from a spoke → fails fast with exit 7); (c) `:8201` listener is intentional on all 3 hosts (aro-wake) — covered by UFW deny for public).
**Run mode:** **fleet-wide**. Probes run separately on each VPS; analysis treats the 3 hosts as one attack surface.
**Scope:** SSH posture, UFW + DOCKER-USER, mesh trust boundary, TLS, Authelia, fail2ban, secret hygiene, container isolation.
**Time budget:** ~10 min collection per host (30 min total) + ~20 min analysis.

---

## Stack context

```text
- 3-VPS fleet on a Wireguard mesh (10.99.0.0/24). Single-operator threat model:
  the mesh is fully trusted (no per-port filtering for 10.99.0.0/24).
- All 3 hosts: Ubuntu 24.04, root SSH disabled, password SSH disabled,
  ozgur user with NOPASSWD sudo + ed25519 key only.
- UFW active on all 3 (W1 ship 2026-05-31). Hub has 5 v4 ALLOW + 1 DENY rules
  (DENY on 8000 carries a stale "Coolify raw port" comment; defense-in-depth);
  spokes have 4 v4 ALLOW + 1 ALLOW from `10.99.0.0/24` for mesh observability
  (W8 fix 2026-06-01).
- fail2ban active on all 3. Hub takes the brunt (~hundreds of bans);
  spokes see passive scanner background (~tens).
- TLS: Let's Encrypt via per-host Traefik. Hub serves *.vps1.ocoron.com
  (production traffic). Spokes serve *.vpsN.ocoron.com (first spoke cert
  issued 2026-06-02 for canary.vps2 — W14/W15 verify).
- Authelia 2FA on vps1 protects all admin dashboards via Traefik forward-auth.
- Secrets: /opt/fabrik/.env on dev WSL is canonical; mirrored offsite to
  private GitHub mobasak/fabrik-dr-store (W9 2026-06-01) + .env.sysadmin
  on vps1 also mirrored. Restic passwords mirrored per-host (W11.6).
- Container isolation: `fabrik` Docker network is the shared bus. Mesh-only
  services bind 10.99.0.1 on hub; spoke agents push outbound to hub mesh IP.
```

---

## Data collection — RUN ON EACH HOST

```bash
ssh vps bash <<'EOF'    # repeat with vps2, vps3
echo "=== SSH POSTURE ==="
sudo grep -E "^(Permit|Password|Pubkey|AllowUsers|MaxAuth)" /etc/ssh/sshd_config
echo "(includes from /etc/ssh/sshd_config.d/ — Ubuntu cloud-init drops 50-cloud-init.conf here which can re-enable PasswordAuthentication; the *first* matching directive in alphabetical-glob order wins)"
sudo grep -EH "Password|Permit" /etc/ssh/sshd_config.d/*.conf 2>&1 | head -10
echo "(effective config via sshd -T — compare against the file content above; divergence = an include file is overriding)"
sudo sshd -T 2>&1 | grep -E "^(permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication)"
sudo find /home -name ".ssh" -exec ls -la {} \;
echo
echo "=== UFW STATE ==="
sudo ufw status verbose
sudo dpkg -l ufw 2>&1 | awk '/^(ii|rc)/'
echo
echo "=== DOCKER-USER CHAIN ==="
sudo iptables -L DOCKER-USER -n --line-numbers
sudo ip6tables -L DOCKER-USER -n --line-numbers 2>&1 | head -10
echo
echo "=== FAIL2BAN ==="
sudo systemctl is-active fail2ban
sudo fail2ban-client status
sudo fail2ban-client status sshd
sudo fail2ban-client banned 2>&1 | head -5
echo
echo "=== AUTHENTICATION LOGS ==="
sudo last -n 20
sudo journalctl -u sshd --since "1 day ago" 2>/dev/null | grep -iE "fail|invalid" | tail -20
sudo grep -E "Accepted|Failed" /var/log/auth.log 2>/dev/null | tail -10
echo
echo "=== LISTENING SOCKETS (with binding interface) ==="
sudo ss -tlnp 2>&1 | sort -k4
echo
echo "=== TLS CERTS ==="
ls -la /opt/traefik/acme.json 2>&1
sudo cat /opt/traefik/acme.json 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    le = d.get('letsencrypt', d.get('le', {}))
    certs = le.get('Certificates', [])
    print(f'  {len(certs)} certificate(s)')
    for c in certs:
        domain = c.get('domain', {}).get('main', '?')
        sans = c.get('domain', {}).get('sans', [])
        print(f'    - {domain}{(\" + \" + str(len(sans)) + \" SANs\") if sans else \"\"}')
except Exception as e:
    print(f'  (acme.json parse: {e})')
"
echo
echo "=== AUTHELIA (vps1 ONLY) — number of access-control rules ==="
[ "$(hostname)" = "vps1.ocoron.com" ] && sudo cat /opt/authelia/config/configuration.yml | python3 -c "
import yaml, sys
cfg = yaml.safe_load(sys.stdin)
rules = cfg.get('access_control', {}).get('rules', [])
print(f'  {len(rules)} rules (expected: 8 — verify against vps-complete-inventory.md)')
for i, r in enumerate(rules, 1):
    doms = r.get('domain', [])
    if isinstance(doms, str): doms = [doms]
    print(f'    #{i}: policy={r.get(\"policy\")}, n_domains={len(doms)}')
"
echo
echo "=== CONTAINER ISOLATION ==="
sudo docker network ls
sudo docker network inspect fabrik --format '{{.Driver}} (bridge), {{len .Containers}} containers'
sudo docker ps --format "{{.Names}}" | xargs -I{} sh -c 'p=$(sudo docker inspect --format="{{json .NetworkSettings.Ports}}" {} 2>/dev/null); echo "{} $p"' | grep -vE -- "(\"null\"$| \{\}$)" | head -20
# Also: any container with a HOST-bound port (-> in `docker ps -Ports`)?
# Use grep -E -- so the leading `-` in the pattern isn't read as an option.
sudo docker ps --format "{{.Names}}\t{{.Ports}}" | grep -E -- "->|0\.0\.0\.0:" | head -10 || echo "  (no host-bound ports — all routed via Traefik on fabrik net, as expected)"
echo
echo "=== SECRETS HYGIENE (file permissions on key paths) ==="
sudo ls -la /root/.ssh/ /home/ozgur/.ssh/ /etc/wireguard/ /opt/backrest/.restic-password 2>&1
sudo find /opt -name ".env" -exec stat -c "%a %U:%G %n" {} \; 2>&1 | head -10
EOF
```

---

## Analysis checklist

### 1. Network perimeter (each host)

- Public TCP listeners only on: `22` (SSH), `80` (HTTP redirect), `443` (HTTPS). Hub adds `1194` (OpenVPN); spokes nothing else.
- Mesh-only services on hub bind `10.99.0.1` (not `0.0.0.0`): `5432`, `6379`, `3100`, `8000`, `9091`. Probe from off-mesh node to confirm filtered/timeout.
- `wg0` UDP `51820` listening on all 3.
- No surprise listeners (promtail gRPC `*:<random>` is known but UFW-shielded — Lesson 72).

### 2. SSH posture (each host)

- `PermitRootLogin no`. `PasswordAuthentication no`. `PubkeyAuthentication yes`.
- **Cross-check `grep` against `sshd -T`** — divergence means an include file in `/etc/ssh/sshd_config.d/` is overriding. Specifically, Ubuntu cloud-init writes `50-cloud-init.conf` with `PasswordAuthentication yes`, and the **first matching directive in alphabetical-glob order wins** in sshd. Hub vs spokes are known to drift on this — the spokes' cloud-init was hardened during bootstrap, the hub's was not.
- `authorized_keys` files have correct mode 600, owned by user.
- `last` shows expected operator only; no surprise root sessions.
- `sshd` auth-fail volume reasonable (high = scanner background; fail2ban catching them = healthy).

### 3. Mesh trust boundary

- `wg show wg0` shows handshake age < 5 min on each peer.
- Hub `wg0` shows both spokes as peers; spokes show hub only.
- Spoke UFW rule `allow from 10.99.0.0/24` exists (W8 fix).
- Mesh-only services on hub: confirm bind to `10.99.0.1` not `0.0.0.0` via `ss -tlnp`.

### 4. TLS & certificate hygiene

- Hub `/opt/traefik/acme.json` populated with all `*.vps1.ocoron.com` certs.
- Spokes: `acme.json` may be empty (vps3) or have first cert (vps2 has canary.vps2.ocoron.com from 2026-06-02 W14/W15 verify).
- No cert expiring < 30 days without renewal in flight.

### 5. Authelia (vps1 only)

- 8 access-control rules (verify against `vps-complete-inventory.md`).
- `auth.vps1.ocoron.com` reachable; portal returns login form.
- Forward-auth middleware in Traefik dynamic config.
- 2FA enrolled for the operator account.

### 6. Container isolation

- Only the expected Docker networks: `fabrik` + `bridge` + `host` + `none` (+ tenant-internal nets like `ocoron-com_ocoron-com-internal`).
- No containers bind `0.0.0.0:<port>` for mesh-only services (port-binding bypasses UFW).
- `fabrik` network is a regular bridge; no privileged containers without justification.

### 7. Brute force & intrusion

- `fail2ban` jails active: `sshd` at minimum. Ban-count proportional to internet exposure.
- No bans against legitimate operator IP (would indicate misconfig).
- `auth.log` shows no successful logins from unexpected IPs.

### 8. Secret hygiene

- `/root/.ssh/`, `/home/ozgur/.ssh/`: mode 700; key files mode 600.
- `/etc/wireguard/` files mode 600.
- `/opt/backrest/.restic-password`: mode 600 root.
- `/opt/<svc>/.env` files: mode 600 (or 644 if no secrets — verify).
- Live `/opt/fabrik/.env` exists only on dev WSL (not on VPS); `.env.sysadmin` on vps1 only.

### 9. Fleet-aggregate concerns

- Hub and spokes have **identical UFW posture** (per the W1 + W8 ship). Any drift = remediate.
- Hub and spokes have **identical SSH config** (no root, no password). Any drift = remediate.
- Hub-only services (Authelia, Traefik dashboard) never exposed on spokes.

---

## Output format

```markdown
## Security Audit — Fleet (vps1 + vps2 + vps3) — <UTC date>

**Verdict:** GREEN / YELLOW / RED
**Summary:** one-paragraph

### Per-host findings
| Host | Worst severity | Key finding |
| :--- | :--- | :--- |
| vps1 | ... | ... |
| vps2 | ... | ... |
| vps3 | ... | ... |

### Fleet-level findings (drift, mesh, cross-host)
1. [severity] <description>
   - Evidence
   - Fix

### Aggregated remediation queue (ranked)
1. ...
```
