#!/bin/bash
# Container health audit data collection — runs ON the VPS via SSH.
# Usage: ssh vps 'bash -s' < scripts/audit/02-container-health.sh
set -uo pipefail

echo "========== FLEET OVERVIEW =========="
echo "--- running ---"
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | sort
echo "--- exited/dead ---"
sudo docker ps -a --filter status=exited --filter status=dead --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" 2>/dev/null | sort || echo "none"

echo ""
echo "========== RESOURCE USAGE =========="
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}" | sort

echo ""
echo "========== MEMORY LIMITS vs ACTUAL =========="
for c in $(docker ps --format "{{.Names}}" | sort); do
  mem_limit=$(docker inspect "$c" --format "{{.HostConfig.Memory}}" 2>/dev/null)
  if [ "$mem_limit" = "0" ] || [ -z "$mem_limit" ]; then
    mem_h="UNLIMITED"
  elif [ "$mem_limit" -ge 1073741824 ]; then
    mem_h="$((mem_limit / 1073741824))g"
  else
    mem_h="$((mem_limit / 1048576))m"
  fi
  mem_usage=$(docker stats --no-stream --format "{{.MemUsage}}" "$c" 2>/dev/null | cut -d/ -f1 | tr -d ' ')
  echo "$c | limit=$mem_h | usage=$mem_usage"
done

echo ""
echo "========== CRASH LOOPS & RESTARTS =========="
echo "--- restart counts ---"
sudo docker inspect $(docker ps -q) --format "{{.Name}} restarts={{.RestartCount}}" 2>/dev/null | sed 's|/||' | sort -t= -k2 -rn | head -15
echo "--- recent die events (24h) ---"
sudo docker events --since 24h --until now --filter event=die --format "{{.Actor.Attributes.name}} exit={{.Actor.Attributes.exitCode}}" 2>/dev/null | tail -20 || echo "none"

echo ""
echo "========== HEALTH CHECK STATUS =========="
for c in $(docker ps --format "{{.Names}}" | sort); do
  health=$(docker inspect "$c" --format "{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}" 2>/dev/null)
  echo "$c: $health"
done

echo ""
echo "========== DISK USAGE =========="
sudo docker system df -v 2>/dev/null | head -80
echo "--- dangling volumes ---"
sudo docker volume ls -f dangling=true --format "{{.Name}}" || echo "none"
echo "--- dangling images ---"
sudo docker images -f dangling=true --format "{{.ID}} {{.Size}}" || echo "none"
echo "--- /var/lib/docker total ---"
du -sh /var/lib/docker/ 2>/dev/null

echo ""
echo "========== NETWORKING =========="
echo "--- networks ---"
sudo docker network ls
echo "--- coolify network containers + aliases ---"
for c in $(docker ps --format "{{.Names}}" | sort); do
  aliases=$(docker inspect "$c" --format "{{json .NetworkSettings.Networks.coolify.Aliases}}" 2>/dev/null)
  ip=$(docker inspect "$c" --format "{{.NetworkSettings.Networks.coolify.IPAddress}}" 2>/dev/null)
  if [ -n "$ip" ] && [ "$ip" != "<no value>" ]; then
    echo "$c | ip=$ip | aliases=$aliases"
  fi
done

echo ""
echo "========== LOG SIZES (top 15) =========="
for c in $(docker ps --format "{{.Names}}" | sort); do
  CID=$(docker inspect "$c" --format "{{.Id}}" 2>/dev/null)
  size=$(du -sh "/var/lib/docker/containers/${CID}/" 2>/dev/null | cut -f1)
  echo "$c: $size"
done | sort -t: -k2 -rh | head -15

echo ""
echo "========== END =========="
