# 02 — Container Health (per host)

**Last Updated:** 2026-06-06 (procedure unchanged; container counts now: hub=31 (29 platform + 2 T-P5 watchdog dogfood), spokes=5 each. Note: `aro-wake.service` and `vps-sysadmin-bot.service` run as systemd UNITS, not containers — they will NOT show in `docker ps` output. Auditors should still check them via `sudo systemctl status aro-wake vps-sysadmin-bot` after the container probes.)
**Run mode:** **per host**. The container fleet differs (hub: 31; spokes: 5 each), so run separately and compare.
**Scope:** Docker container fleet stability, resource usage, networking, log hygiene.
**Time budget:** ~10 min collection + ~10 min analysis per host.

---

## Stack context

```text
- Deploy: SSH + Docker Compose via `fabrik apply`. All containers stable-named
  (no UUID suffix). Network: `fabrik` (renamed from `coolify` 2026-05-31).
- Hub (vps1): 31 containers (29 platform + 2 T-P5 watchdog dogfood). Mix of shared infra (postgres-main, redis-main,
  authelia, glitchtip-{web,worker}, loki, traefik), monitoring (prometheus,
  grafana, alertmanager, gatus, cadvisor, node-exporter, promtail, pushgateway,
  postgres-exporter, redis-exporter), utility (n8n, browserless, gotenberg,
  meilisearch, apprise, backrest), tenant (5 ocoron-com-*), provisioner
  (site-provisioner).
- Spoke (vps2/vps3): 5 containers — traefik, node-exporter, cadvisor,
  promtail, backrest.
- Memory limits enforced via compose `deploy.resources.limits.memory` on every
  service (Fabrik invariant; validator enforces). Spoke containers use small
  limits (256m typical).
- Health checks: each compose has HEALTHCHECK (Lesson 30); `/health` endpoint
  on app services tests real deps (Lesson 31).
- W15: spoke `traefik` container has labels `traefik.enable=true` +
  `traefik.http.middlewares.gzip.compress=true` (publishes gzip@docker for
  spoke deploys).
```

---

## Data collection — HUB (vps1)

```bash
ssh vps bash <<'EOF'
echo "=== INVENTORY (expect 31) ==="
sudo docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}"
echo "container count: $(sudo docker ps -q | wc -l)"
echo
echo "=== HEALTH STATUS ==="
sudo docker ps --format "{{.Names}}" | xargs -I{} sh -c 'h=$(sudo docker inspect --format="{{.State.Health.Status}}" {} 2>/dev/null); echo "{} $h"' | sort -k2
echo
echo "=== RESOURCE USAGE ==="
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | head -32
echo
echo "=== MEMORY LIMIT POSTURE (expect every service has a limit) ==="
sudo docker ps --format "{{.Names}}" | xargs -I{} sh -c 'l=$(sudo docker inspect --format="{{.HostConfig.Memory}}" {}); echo "{} $l"' | awk '$2==0 {print "NO LIMIT: " $1}'
echo
echo "=== RESTARTS (look for restart loops) ==="
sudo docker ps -a --format "{{.Names}}\t{{.Status}}" | grep -iE "restart|exited" | head -20
sudo docker ps --format "{{.Names}}" | xargs -I{} sh -c 'r=$(sudo docker inspect --format="{{.RestartCount}}" {}); echo "{} $r"' | sort -k2 -n -r | head -10
echo
echo "=== NETWORK ==="
sudo docker network ls
sudo docker network inspect fabrik --format '{{range $k,$v := .Containers}}{{$v.Name}} {{$v.IPv4Address}}{{println}}{{end}}'
echo
echo "=== LOG VOLUME (top 10 by size) ==="
sudo docker ps -q | xargs -I{} sh -c 'p=$(sudo docker inspect --format="{{.LogPath}}" {}); n=$(sudo docker inspect --format="{{.Name}}" {} | sed "s|/||"); s=$(sudo du -m "$p" 2>/dev/null | cut -f1); echo "$s MB $n"' | sort -rn | head -10
echo
echo "=== IMAGES + DANGLING ==="
sudo docker images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}" | head -20
sudo docker images -f "dangling=true" --format "{{.ID}}" | wc -l | xargs echo "dangling images:"
EOF
```

## Data collection — SPOKE (vps2 or vps3)

```bash
ssh vps2 bash <<'EOF'    # repeat for vps3
echo "=== INVENTORY (expect 5: traefik + node-exporter + cadvisor + promtail + backrest) ==="
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}"
echo
echo "=== HEALTH STATUS ==="
sudo docker ps --format "{{.Names}}" | xargs -I{} sh -c 'h=$(sudo docker inspect --format="{{.State.Health.Status}}" {} 2>/dev/null); echo "{} $h"'
echo
echo "=== RESOURCE USAGE ==="
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
echo
echo "=== W15 LABELS on traefik (expect both labels) ==="
sudo docker inspect traefik --format '{{range $k,$v := .Config.Labels}}{{$k}}={{$v}}{{println}}{{end}}' | grep -E "traefik\\.enable|gzip\\.compress"
echo
echo "=== BACKREST STATE ==="
sudo cat /opt/backrest/config/config.json | python3 -c "import json,sys; d=json.load(sys.stdin); print('plans:', [p['id'] for p in d.get('plans',[])]); print('repos:', [r['id'] for r in d.get('repos',[])])"
echo
echo "=== MESH OBSERVABILITY OUTBOUND ==="
ss -tnp 2>&1 | grep -E "10\\.99\\.0\\.1:(3100|9090|9091)" | head -5
echo
echo "=== NETWORK ==="
sudo docker network inspect fabrik --format '{{range $k,$v := .Containers}}{{$v.Name}} {{$v.IPv4Address}}{{println}}{{end}}'
echo
echo "=== LOG VOLUME ==="
sudo docker ps -q | xargs -I{} sh -c 'p=$(sudo docker inspect --format="{{.LogPath}}" {}); n=$(sudo docker inspect --format="{{.Name}}" {} | sed "s|/||"); s=$(sudo du -m "$p" 2>/dev/null | cut -f1); echo "$s MB $n"' | sort -rn
EOF
```

---

## Analysis checklist

### 1. Fleet stability

- Expected count matches actual (hub 31; spoke 5).
- Every container `Up` (none `Exited`, `Restarting`, `Dead`).
- RestartCount low (< 5 over container lifetime); a high RestartCount = restart loop.
- Container uptime aligns with last apply / planned downtime.

### 2. Health status

- Containers with HEALTHCHECK report `healthy` (not `starting` past start_period, not `unhealthy`).
- Containers without HEALTHCHECK explicit: confirm they shouldn't have one (per Lesson 30, distroless images may opt out via `healthcheck: disable: true`).
- W15 (spokes only): `traefik` container has `traefik.enable=true` AND `traefik.http.middlewares.gzip.compress=true` labels. Missing label = next spoke deploy will 404 at the verifier.

### 3. Resource pressure

- Memory %: any container > 80% of its limit → investigate (OOM coming).
- CPU %: any container sustained > 50% → investigate.
- Per-service limit is set (no `HostConfig.Memory: 0`). Unset = OOM gambit on the shared host.

### 4. Networking

- All **tenant** containers on `fabrik` network (or their own compose-internal network plus `fabrik`).
- **Monitoring agents typically use `network_mode: host`** (`node-exporter` needs full host visibility for `/proc`+`/sys` metrics; `cadvisor` mounts `/sys`+`/var/lib/docker`; `promtail` does host log tailing). They will be **absent** from `docker network inspect fabrik` output — that's correct, not a defect. Verify with `docker inspect <name> --format '{{.HostConfig.NetworkMode}}'` before flagging.
- IP addresses unique; no rogue containers on default `bridge`.
- Mesh-only services on hub bind `10.99.0.1` (not `0.0.0.0`) — `postgres-main`, `redis-main`, `loki`, `glitchtip-web`, `pushgateway`, `authelia`.
- Spokes' monitoring agents push to hub mesh IP (`10.99.0.1:3100` for Loki, etc.); outbound conns visible in `ss -tn`.

### 5. Log hygiene

- No single container log > 1 GB (rotate at `max-size: 10m`, `max-file: 3` is the standard).
- High-volume containers (promtail, prometheus, traefik) within reasonable bounds.
- Empty-log containers = check whether the app is actually running.

### 6. Image freshness

- No images > 1 year old without a reason.
- Dangling images: 0 (pruned periodically).
- No `latest` tags on production services without a digest pin (image drift risk).

### 7. Hub-only checks

- WordPress tenant containers (`ocoron-com-{nginx,wordpress,db,redis,backup}`) all healthy.
- `glitchtip-web` + `glitchtip-worker` both running (separate processes).
- `authelia-config-sync` watcher running (inotify-based config reload).
- `site-provisioner` running and healthy at `/health` (interim manual stand-up — see vps-status.md).

### 8. Spoke-only checks

- `backrest` container has `host-state` + `opt-configs` plans in config.
- Mesh push conns to vps1:3100 (Loki) and vps1:9100 (node-exporter scrape) visible.

---

## Output format

```markdown
## Container Health Audit — <hostN> — <UTC date>

**Verdict:** GREEN / YELLOW / RED
**Summary:** one-paragraph

### Findings (most severe first)
1. [severity] <container> — <issue>
   - Evidence: <docker inspect / stats / logs excerpt>
   - Root cause: <best guess>
   - Fix: <command or doc link>

### W15 spoke check (spokes only)
- `traefik.enable=true`: [present | MISSING]
- `traefik.http.middlewares.gzip.compress=true`: [present | MISSING]

### Trends to watch
- ...
```
