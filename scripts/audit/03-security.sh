#!/bin/bash
# Security hardening audit data collection — runs ON the VPS via SSH.
# Usage: ssh vps 'bash -s' < scripts/audit/03-security.sh
set -uo pipefail

echo "========== LISTENING PORTS =========="
echo "--- tcp ---"
ss -tlnp | sort
echo "--- udp ---"
ss -ulnp | sort

echo ""
echo "========== FIREWALL =========="
echo "--- ufw ---"
sudo ufw status verbose 2>/dev/null || echo "ufw not active"
echo "--- DOCKER-USER chain (the real perimeter) ---"
sudo iptables -L DOCKER-USER -n --line-numbers -v 2>/dev/null || echo "no DOCKER-USER chain"

echo ""
echo "========== PUBLIC EXPOSURE =========="
echo "--- bound to 0.0.0.0 (excluding docker internals) ---"
ss -tlnp | grep "0.0.0.0\|::0\|:::" | grep -v "127.0.0.1\|10\.0\." || echo "none"

echo ""
echo "========== TLS CERTIFICATES =========="
# Check certs for known domains
for domain in ocoron.com www.ocoron.com status.vps1.ocoron.com monitor.vps1.ocoron.com errors.vps1.ocoron.com backup.vps1.ocoron.com coolify.vps1.ocoron.com images.vps1.ocoron.com search.vps1.ocoron.com auth.vps1.ocoron.com; do
  expiry=$(echo | timeout 5 openssl s_client -servername "$domain" -connect "$domain":443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  if [ -n "$expiry" ]; then
    echo "$domain: expires $expiry"
  else
    echo "$domain: CERT CHECK FAILED"
  fi
done

echo ""
echo "========== SSH SECURITY =========="
echo "--- sshd config ---"
sudo sshd -T 2>/dev/null | grep -E "passwordauthentication|permitrootlogin|pubkeyauthentication|maxauthtries|port" || echo "sshd -T failed"
echo "--- failed password attempts (7 days) ---"
sudo journalctl -u ssh --since "7 days ago" 2>/dev/null | grep -c "Failed password" || echo "0"
echo "--- top attacker IPs (7 days) ---"
sudo journalctl -u ssh --since "7 days ago" 2>/dev/null | grep "Failed password" | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn | head -10 || echo "none"
echo "--- recent logins ---"
sudo last -20 2>/dev/null

echo ""
echo "========== AUTHELIA ACCESS RULES =========="
CONFIG_VOL="/var/lib/docker/volumes/hks48k8sg8o4co4co08co00o_authelia-config/_data/configuration.yml"
if [ -f "$CONFIG_VOL" ]; then
  grep -A100 "access_control:" "$CONFIG_VOL" | head -80
else
  echo "authelia config not found at expected path"
fi

echo ""
echo "========== CONTAINER PRIVILEGES =========="
for c in $(docker ps --format "{{.Names}}" | sort); do
  priv=$(docker inspect "$c" --format "{{.HostConfig.Privileged}}" 2>/dev/null)
  caps=$(docker inspect "$c" --format "{{.HostConfig.CapAdd}}" 2>/dev/null)
  pid=$(docker inspect "$c" --format "{{.HostConfig.PidMode}}" 2>/dev/null)
  net=$(docker inspect "$c" --format "{{.HostConfig.NetworkMode}}" 2>/dev/null)
  seccomp=$(docker inspect "$c" --format "{{.HostConfig.SecurityOpt}}" 2>/dev/null)
  if [ "$priv" = "true" ] || [ "$caps" != "[]" ] && [ "$caps" != "<no value>" ] || [ "$pid" = "host" ] || [ "$net" = "host" ]; then
    echo "ELEVATED: $c priv=$priv caps=$caps pid=$pid net=$net"
  fi
done
echo "(only elevated-privilege containers shown above)"

echo ""
echo "========== DOCKER SOCKET EXPOSURE =========="
ls -la /var/run/docker.sock
echo "--- containers with docker socket mounted ---"
for c in $(docker ps --format "{{.Names}}" | sort); do
  mounts=$(docker inspect "$c" --format "{{range .Mounts}}{{.Source}} {{end}}" 2>/dev/null)
  if echo "$mounts" | grep -q "docker.sock"; then
    echo "SOCKET MOUNTED: $c"
  fi
done

echo ""
echo "========== APPARMOR =========="
sudo aa-status 2>/dev/null | head -30 || echo "apparmor not available"

echo ""
echo "========== SECRETS SCAN (env vars with sensitive names) =========="
for c in $(docker ps --format "{{.Names}}" | sort); do
  sudo docker inspect "$c" --format "{{range .Config.Env}}{{println .}}{{end}}" 2>/dev/null | grep -iE "password=|secret=|token=|api_key=" | grep -v "COOLIFY_\|SERVICE_INTERNAL_SECRET_KEY" | while read -r line; do
    key=$(echo "$line" | cut -d= -f1)
    echo "EXPOSED: $c → $key=<redacted>"
  done
done

echo ""
echo "========== END =========="
