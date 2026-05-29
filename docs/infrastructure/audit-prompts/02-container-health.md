# Container Health Audit — Docker + Coolify Diagnostics

Analyze the Docker container fleet on this Ubuntu 24.04 VPS managed by Coolify v4. Focus on container stability, resource usage, networking, and Coolify-specific operational issues.

## Stack Context

- Coolify v4 (beta.459) manages Services (stable names) and Applications (UUID-based names)
- Traefik v2.11 ingress, `coolify` Docker network (10.0.1.0/24)
- `coolify-alias-watcher` systemd service re-applies friendly DNS aliases on redeploy
- Docker daemon: `json-file` driver, `tag: {{.Name}}`, max 10m x 3 log files
- Memory limits set via `fabrik apply` (SSH + Docker Compose) or compose `deploy.resources.limits.memory`

## Data Collection

**Automated:** `ssh vps 'sudo bash -s' < /opt/fabrik/scripts/audit/02-container-health.sh`

**Or manual:**

```bash
# Container fleet overview
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | sort
sudo docker ps -a --filter status=exited --filter status=dead --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | sort

# Resource usage (live snapshot)
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}" | sort

# Memory limits vs actual usage
for c in $(sudo docker ps --format "{{.Names}}"); do
  mem_limit=$(sudo docker inspect $c --format "{{.HostConfig.Memory}}")
  mem_usage=$(sudo docker stats --no-stream --format "{{.MemUsage}}" $c | cut -d/ -f1)
  echo "$c | limit: $mem_limit | usage: $mem_usage"
done

# Crash loops / restarts
sudo docker ps --format "{{.Names}} {{.Status}}" | grep -iE "restarting|unhealthy|Exited"
sudo docker events --since 24h --until now --filter event=die --format "{{.Actor.Attributes.name}} exited {{.Actor.Attributes.exitCode}}" 2>/dev/null | tail -20

# Disk usage
sudo docker system df -v | head -60
sudo docker volume ls -f dangling=true
sudo docker images -f dangling=true --format "{{.ID}} {{.Size}}"
sudo du -sh /var/lib/docker/

# Networking
sudo docker network ls
sudo docker network inspect coolify --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}{{println}}{{end}}' | sort

# Alias health (Coolify single-image apps)
for c in $(sudo docker ps --format "{{.Names}}"); do
  aliases=$(sudo docker inspect $c --format "{{json .NetworkSettings.Networks.coolify.Aliases}}" 2>/dev/null)
  if [ "$aliases" != "null" ] && [ -n "$aliases" ]; then
    echo "$c → $aliases"
  fi
done

# Log sizes per container
for c in $(sudo docker ps --format "{{.Names}}"); do
  CID=$(sudo docker inspect $c --format "{{.Id}}")
  size=$(sudo du -sh /var/lib/docker/containers/${CID}/ 2>/dev/null | cut -f1)
  echo "$c: $size"
done | sort -t: -k2 -rh | head -15

# Health check status
sudo docker inspect $(sudo docker ps -q) --format "{{.Name}} health={{.State.Health.Status}} restarts={{.RestartCount}}" 2>/dev/null | sed 's|/||' | sort
```

## Analysis Checklist

### 1. Fleet Stability
- Any containers in restart loop (RestartCount > 3)?
- Any exited/dead containers that should be running?
- Any unhealthy containers?
- Event log: abnormal exit codes (non-zero = crash)

### 2. Resource Pressure
- Which containers use >80% of their memory limit? (OOM imminent)
- Which containers have NO memory limit set? (can OOM the host)
- Top 5 CPU consumers — is any monitoring agent (cAdvisor, Netdata, Prometheus) consuming more than the services it monitors?
- Total Docker disk usage vs VPS capacity

### 3. Networking
- Are all containers on the `coolify` network?
- Are DNS aliases intact for Coolify Applications (meilisearch, gotenberg, browserless, glitchtip-web)?
- Any IP address conflicts?

### 4. Log Hygiene
- Which containers produce the most log volume?
- Are logs being rotated (max-size 10m x 3)?
- Is Promtail's `container_name` label populated? (requires `daemon.json` tag)

### 5. Coolify-Specific
- Coolify core containers healthy (coolify, coolify-db, coolify-redis, coolify-realtime, coolify-sentinel)?
- Any Coolify service compose drift (disk file vs DB-stored compose)?
- Dangling volumes from destroyed services?
- Dangling images consuming disk?

### 6. Image Freshness
- Any images using `:latest` that haven't been pulled recently?
- Any images with known CVEs? (check image age as proxy)

## Output Format

1. **FLEET STATUS** — X running / Y unhealthy / Z exited
2. **CRITICAL** — containers about to OOM, crash-looping, or missing
3. **RESOURCE HOT SPOTS** — top consumers, limit violations
4. **CLEANUP ACTIONS** — dangling volumes/images to remove, stale containers to prune
5. **REMEDIATION** — specific `docker` commands, grouped by urgency
