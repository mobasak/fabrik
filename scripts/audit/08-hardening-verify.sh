#!/bin/bash
# Post-hardening verification — runs ON the VPS via SSH.
# Usage: ssh vps 'sudo bash -s' < scripts/audit/08-hardening-verify.sh
# NOTE: Must run with sudo (learned from first audit run 2026-05-19).
set -uo pipefail

echo "========== A. NETWORK PERIMETER =========="
echo "--- ufw ---"
sudo ufw status verbose
echo "--- DOCKER-USER chain ---"
sudo iptables -L DOCKER-USER -n --line-numbers -v 2>/dev/null || echo "MISSING"
echo "--- iptables-docker-user service ---"
systemctl is-enabled iptables-docker-user.service 2>/dev/null
systemctl is-active iptables-docker-user.service 2>/dev/null
echo "--- ports on 0.0.0.0 ---"
sudo ss -tlnp | grep "0.0.0.0" | awk '{print $4, $6}' | sort
echo "--- fail2ban ---"
sudo fail2ban-client status sshd 2>/dev/null || echo "fail2ban not installed or sshd jail not active"

echo ""
echo "========== B. CONTAINER MEMORY LIMITS =========="
echo "--- containers WITHOUT memory limit (shows host max) ---"
UNLIMITED=0
for c in $(sudo docker ps --format "{{.Names}}" | sort); do
  mem=$(sudo docker inspect "$c" --format "{{.HostConfig.Memory}}" 2>/dev/null)
  if [ "$mem" = "0" ] || [ -z "$mem" ]; then
    usage=$(sudo docker stats --no-stream --format "{{.MemUsage}}" "$c" 2>/dev/null | cut -d/ -f1 | tr -d ' ')
    echo "  UNLIMITED: $c (using $usage)"
    UNLIMITED=$((UNLIMITED+1))
  fi
done
echo "Total unlimited: $UNLIMITED"
echo ""
echo "--- all container limits ---"
for c in $(sudo docker ps --format "{{.Names}}" | sort); do
  mem=$(sudo docker inspect "$c" --format "{{.HostConfig.Memory}}" 2>/dev/null)
  if [ "$mem" != "0" ] && [ -n "$mem" ]; then
    if [ "$mem" -ge 1073741824 ]; then
      mem_h="$((mem / 1073741824))g"
    else
      mem_h="$((mem / 1048576))m"
    fi
    usage=$(sudo docker stats --no-stream --format "{{.MemPerc}}" "$c" 2>/dev/null)
    echo "  $c: limit=$mem_h usage=$usage"
  fi
done

echo ""
echo "========== C. SYSTEM TUNING =========="
echo "swappiness: $(cat /proc/sys/vm/swappiness)"
echo "somaxconn: $(cat /proc/sys/net/core/somaxconn)"
echo "tcp_tw_reuse: $(cat /proc/sys/net/ipv4/tcp_tw_reuse)"
echo "file-max: $(cat /proc/sys/fs/file-max)"
echo "inotify max_user_watches: $(cat /proc/sys/fs/inotify/max_user_watches)"
echo "--- journal ---"
sudo journalctl --disk-usage 2>/dev/null
echo "--- /var/log ---"
sudo du -sh /var/log/
echo "--- daemon.json ---"
cat /etc/docker/daemon.json
echo "--- fstab noatime ---"
grep "noatime" /etc/fstab && echo "noatime: present" || echo "noatime: MISSING"
echo "--- swap ---"
swapon --show 2>/dev/null
free -h | grep Swap

echo ""
echo "========== D. MONITORING COMPLETENESS =========="
echo "--- prometheus targets ---"
sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/targets?state=any" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    up=sum(1 for t in d['data']['activeTargets'] if t['health']=='up')
    down=sum(1 for t in d['data']['activeTargets'] if t['health']!='up')
    print(f'targets: {up} up, {down} down')
    for t in d['data']['activeTargets']:
        if t['health'] != 'up':
            print(f'  DOWN: {t[\"labels\"][\"job\"]} {t[\"scrapeUrl\"]}')
except: print('FAILED to query prometheus')
"
echo "--- alert rules ---"
sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/rules" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    rules=[r for g in d['data']['groups'] for r in g['rules']]
    firing=[r for r in rules if r.get('state')=='firing']
    print(f'rules: {len(rules)} total, {len(firing)} firing')
    for r in firing:
        print(f'  FIRING: {r[\"name\"]}')
except: print('FAILED')
"
echo "--- loki labels ---"
sudo docker run --rm --network coolify curlimages/curl:latest -sS "http://loki:3100/loki/api/v1/label/container_name/values" 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    filtered=['coolify-db','coolify-redis','coolify-realtime','coolify-sentinel','ocoron-com-backup-1']
    labels=d.get('data',[])
    leaked=[v for v in labels if v in filtered]
    print(f'loki: {len(labels)} container labels')
    if leaked: print(f'  NOISE LEAK: {leaked}')
    else: print('  noise filter: OK')
except: print('FAILED')
"
echo "--- gatus endpoints ---"
sudo docker run --rm --network coolify curlimages/curl:latest -sS "http://gatus:8080/api/v1/endpoints/statuses" 2>/dev/null | python3 -c "
import json,sys
try:
    data=json.load(sys.stdin)
    up=sum(1 for ep in data if ep.get('results',[-1])[-1].get('success'))
    down=sum(1 for ep in data if not ep.get('results',[-1])[-1].get('success'))
    print(f'gatus: {up} up, {down} down')
    for ep in data:
        r=ep.get('results',[{}])[-1]
        if not r.get('success'):
            print(f'  DOWN: {ep.get(\"group\",\"?\")}/{ep.get(\"name\",\"?\")}')
except: print('FAILED')
"

echo ""
echo "========== E. BACKUP =========="
echo "--- backrest running ---"
sudo docker ps --filter name=backrest --format "{{.Names}} {{.Status}}"
echo "--- plans ---"
if [ -f /opt/backrest/config/config.json ]; then
  python3 -c "
import json
cfg=json.load(open('/opt/backrest/config/config.json'))
for p in cfg.get('plans',[]):
    ret=p.get('retention',{})
    has_ret='YES' if ret else 'NO'
    print(f\"  {p.get('id','?'):30s} retention={has_ret} schedule={p.get('schedule',{}).get('cron','none')}\")
  " 2>/dev/null
else
  echo "  config not found"
fi

echo ""
echo "========== F. HYGIENE =========="
echo "--- dangling volumes ---"
count=$(sudo docker volume ls -f dangling=true --format "{{.Name}}" | wc -l)
echo "dangling volumes: $count"
echo "--- dangling images ---"
count=$(sudo docker images -f dangling=true --format "{{.ID}}" | wc -l)
echo "dangling images: $count"
echo "--- stale containers (created/exited) ---"
count=$(sudo docker ps -a --filter status=created --filter status=exited --format "{{.Names}}" | wc -l)
echo "stale containers: $count"
sudo docker ps -a --filter status=created --filter status=exited --format "{{.Names}} {{.Status}}" 2>/dev/null || true
echo "--- zombie processes ---"
zombies=$(ps aux | awk '$8 ~ /Z/' | wc -l)
echo "zombies: $zombies"

echo ""
echo "========== SCORE =========="
PASS=0
FAIL=0

# A. Perimeter
sudo ufw status 2>/dev/null | grep -q "Status: active" && PASS=$((PASS+1)) || FAIL=$((FAIL+1))
sudo iptables -L DOCKER-USER -n 2>/dev/null | grep -q "DROP" && PASS=$((PASS+1)) || FAIL=$((FAIL+1))

# C. Tuning
[ "$(cat /proc/sys/vm/swappiness)" -le 10 ] && PASS=$((PASS+1)) || FAIL=$((FAIL+1))
grep -q "noatime" /etc/fstab 2>/dev/null && PASS=$((PASS+1)) || FAIL=$((FAIL+1))

# F. Hygiene
[ "$(sudo docker volume ls -f dangling=true --format '{{.Name}}' | wc -l)" -eq 0 ] && PASS=$((PASS+1)) || FAIL=$((FAIL+1))
[ "$(sudo docker images -f dangling=true --format '{{.ID}}' | wc -l)" -eq 0 ] && PASS=$((PASS+1)) || FAIL=$((FAIL+1))

echo ""
echo "HARDENING SCORE: $PASS passed, $FAIL failed out of $((PASS+FAIL)) checks"

echo ""
echo "========== END =========="
