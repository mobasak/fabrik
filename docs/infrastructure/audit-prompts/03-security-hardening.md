# Security Hardening Audit — Attack Surface & Access Control

Analyze the security posture of this Ubuntu 24.04 VPS. Focus on attack surface reduction, authentication, encryption, and defense-in-depth. This VPS will serve real users — every unnecessary exposure is a liability.

## Stack Context

- Traefik v2.11 terminates HTTPS (Let's Encrypt), routes to containers on `fabrik` network
- Authelia provides 2FA forward-auth for admin dashboards (Grafana, Coolify UI, Netdata, Backrest, GlitchTip)
- M2M auth: `X-Internal-Token` header with shared `SERVICE_INTERNAL_SECRET_KEY`
- API services (image-broker, site-provisioner) bypass Authelia, use app-layer token auth
- Health endpoints (`/health`, `/healthz`, `/metrics`) bypass Authelia via wildcard rule
- Two-layer firewall: **UFW** (host-level — controls SSH + direct host services) + **DOCKER-USER iptables chain** (container-level — controls Docker traffic via the FORWARD chain). UFW shipped on spokes 2026-05-31 (W1). **Lesson 68:** verify UFW with all 3 of `dpkg -l ufw \| awk '/^ii/'`, `command -v ufw`, `sudo ufw status` — single-probe checks miss the `rc`-state pitfall.
- SSH: Ed25519 key only, root login disabled, port 22

## Data Collection

**Automated:** `ssh vps 'sudo bash -s' < /opt/fabrik/scripts/audit/03-security.sh`

**Or manual:**

```bash
# 1. Listening ports — what's exposed
sudo ss -tlnp | sort
sudo ss -ulnp | sort

# 2. UFW — verify all 3 (Lesson 68: any single probe can mislead)
dpkg -l ufw 2>/dev/null | awk '/^(ii|rc)/ {print $1, $2}'  # ii = installed, rc = removed-with-config
command -v ufw                                             # binary in PATH?
sudo ufw status verbose                                    # rules + default policy

# 3. DOCKER-USER chain (Docker traffic perimeter — Docker bypasses UFW's INPUT chain)
sudo iptables -L DOCKER-USER -n --line-numbers -v
sudo update-alternatives --display iptables | grep currently  # nft vs legacy — must be consistent

# 4. Traefik middlewares (what's protected)
sudo docker exec traefik wget -qO- http://localhost:8080/api/http/middlewares 2>/dev/null | python3 -m json.tool | head -80
sudo docker exec traefik wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | python3 -m json.tool | head -120

# 5. Authelia config (access rules)
sudo cat /var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml | grep -A50 "access_control:"

# 6. TLS certificates
for domain in $(sudo docker exec traefik wget -qO- http://localhost:8080/api/http/routers 2>/dev/null | python3 -c "import json,sys; [print(r.get('rule','').split('\`')[1]) for r in json.load(sys.stdin) if 'Host' in r.get('rule','')]" 2>/dev/null | sort -u); do
  expiry=$(echo | openssl s_client -servername "$domain" -connect "$domain":443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null)
  echo "$domain: $expiry"
done

# 7. SSH security
sudo sshd -T 2>/dev/null | grep -E "passwordauthentication|permitrootlogin|pubkeyauthentication|maxauthtries|allowusers|port"
sudo journalctl -u ssh --since "7 days ago" | grep -c "Failed password"
sudo journalctl -u ssh --since "7 days ago" | grep "Failed password" | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -10
last -20

# 8. Publicly reachable ports (from outside Docker network)
sudo ss -tlnp | grep -v "127.0.0.1\|::1\|10\.0\." | grep "0.0.0.0\|::0"

# 9. Container privilege audit
for c in $(sudo docker ps --format "{{.Names}}"); do
  priv=$(sudo docker inspect $c --format "{{.HostConfig.Privileged}}")
  caps=$(sudo docker inspect $c --format "{{.HostConfig.CapAdd}}")
  pid=$(sudo docker inspect $c --format "{{.HostConfig.PidMode}}")
  net=$(sudo docker inspect $c --format "{{.HostConfig.NetworkMode}}")
  if [ "$priv" = "true" ] || [ "$caps" != "[]" ] || [ "$pid" = "host" ] || [ "$net" = "host" ]; then
    echo "ELEVATED: $c priv=$priv caps=$caps pid=$pid net=$net"
  fi
done

# 10. AppArmor
sudo aa-status 2>/dev/null | head -30

# 11. Secrets exposure check
sudo docker inspect $(sudo docker ps -q) --format "{{.Name}}={{range .Config.Env}}{{println .}}{{end}}" 2>/dev/null | grep -iE "password|secret|token|key|api_key" | grep -v "SERVICE_INTERNAL_SECRET_KEY\|COOLIFY_\|SENTRY_DSN" | head -20

# 12. Docker socket exposure
ls -la /var/run/docker.sock
sudo docker ps --format "{{.Names}}" -f "volume=/var/run/docker.sock"
```

## Analysis Checklist

### 1. Network Perimeter
- What ports are bound to 0.0.0.0? (Only 22, 80, 443, 6001, 6002 should be)
- Is DOCKER-USER chain complete (9 rules: ESTABLISHED, 3x private ranges, 80, 443, 6001, 6002, DROP)?
- Any container publishing ports directly to host (bypassing Traefik)?

### 2. TLS Health
- All domains have valid Let's Encrypt certs?
- Any cert expiring within 14 days?
- TLS version: is TLS 1.2+ enforced? Any TLS 1.0/1.1?

### 3. Authentication Layers
- Authelia: all admin dashboards protected with 2FA?
- Health/metrics endpoints: bypassed correctly (not exposing data)?
- M2M: SERVICE_INTERNAL_SECRET_KEY rotated recently? (32+ chars, alphanumeric)
- SSH: key-only, no passwords, root disabled?

### 4. Brute Force & Intrusion
- SSH failed login count in 7 days
- Top attacker IPs
- Any successful logins from unexpected sources?
- fail2ban installed? (should be for SSH)

### 5. Container Isolation
- Any privileged containers? (should be only cAdvisor + Netdata)
- Any containers with `--cap-add`?
- Any containers with host PID/network mode?
- Docker socket mounted to any non-Coolify container?

### 6. Secret Hygiene
- Any secrets visible in container env vars that should be in .env files?
- Any hardcoded passwords (not from env)?

## Output Format

1. **SECURITY POSTURE** — Green / Yellow / Red with evidence
2. **CRITICAL VULNERABILITIES** — exploitable now
3. **HARDENING GAPS** — not exploitable but increase risk
4. **COMPLIANCE** — TLS, auth, secrets management status
5. **REMEDIATION** — ordered by severity, with exact commands
