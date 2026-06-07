# 04 — Performance Bottleneck (per host)

**Last Updated:** 2026-06-06 (procedure unchanged; container counts now hub=31, spokes=5 each. Today's new host processes auditors should expect in `ps`/`top`: `uvicorn main:app --host 0.0.0.0 --port 8201` (aro-wake — ~32 MB RSS idle, 0% CPU when not waking) and `python3 /opt/fabrik/scripts/sysadmin/bot.py` (sysadmin bot — also idle most of the time). Neither is a bottleneck — both sleep until pushed. **New SLI metrics available for cost-bottleneck analysis**: query `sum(rate(aro_wake_cost_usd_total[1h])) by (host)` in Prometheus to see per-host Claude $ burn rate; `AroWakeCostBurnHigh` alert fires if > $5/h sustained (runaway-reasoning early-warning).)
**Run mode:** **per host**. Resource budgets differ (hub: 11.6 GiB / 6 cores; spokes: 7.7 GiB / 4 cores).
**Scope:** CPU, memory, disk I/O, network — identify what's slow, why, how to fix.
**Time budget:** ~10 min probes + ~15 min analysis per host.

---

## Stack context

```text
- Hub vps1: 11.6 GiB RAM, 6 vCores, 108 GB NVMe (LA). 29 containers.
  ~3-4 GiB RAM used typically. ~27% disk.
- Spokes vps2/vps3: 7.7 GiB RAM, 4 vCores, 58 GB NVMe RAID-10 (Coventry UK).
  5 containers each. ~850 MiB RAM used typically. ~11% disk.
- Compose `deploy.resources.limits.memory` enforced on every service
  (Fabrik invariant; validator enforces). CPU limits also recommended.
- Tenants land on spokes via `fabrik apply --target-vps vpsN` (W-Multi M4 /
  W3 / W14). Today: no real tenants on spokes (spoke-canary 2026-06-02 was
  a one-shot test). Hub carries the WordPress tenant + all shared infra.
```

---

## Data collection — RUN PER HOST

```bash
ssh vps bash <<'EOF'    # repeat for vps2, vps3
echo "=== CPU SNAPSHOT ==="
nproc; lscpu | grep -E "Model name|MHz"
top -bn1 | head -25
echo "---"
echo "Load avg:"; uptime
echo "---"
echo "Top 10 by CPU:"
ps aux --sort=-%cpu | head -11
echo
echo "=== MEMORY ==="
free -h
echo "---"
echo "Top 10 by RSS:"
ps aux --sort=-rss | head -11
echo "---"
echo "swap:"; swapon --show; cat /proc/swaps
echo "---"
echo "OOM history (last 7d):"
sudo dmesg --since '7 days ago' | grep -i 'oom-killer' | tail -10
echo
echo "=== DISK I/O ==="
df -h --total | grep -vE 'tmpfs|overlay'
echo "---"
echo "iostat (5s window):"
iostat -xz 1 5 2>/dev/null | tail -30 || echo "(install sysstat for iostat)"
echo "---"
echo "Top 10 dirs by size:"
sudo du -sh /var/lib/docker /opt/* 2>/dev/null | sort -hr | head -10
echo "---"
echo "Docker overlay2 + volume size:"
sudo du -sh /var/lib/docker/overlay2 /var/lib/docker/volumes 2>/dev/null
echo
echo "=== NETWORK ==="
ip -s link show ens3 2>/dev/null | head -10
ip -s link show wg0 2>/dev/null | head -10
echo "---"
echo "ss summary:"; ss -s
echo "---"
echo "conntrack pressure (sysctl — always present; the `conntrack` CLI is not installed on the fleet):"
sudo sysctl net.netfilter.nf_conntrack_count net.netfilter.nf_conntrack_max 2>&1
echo "established TCP conns:"
sudo ss -tn state established 2>/dev/null | wc -l
echo
echo "=== DOCKER CONTAINER RESOURCE STATS ==="
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}"
echo
echo "=== PER-CONTAINER MEMORY LIMITS ==="
sudo docker ps --format "{{.Names}}" | while read n; do
  lim_b=$(sudo docker inspect --format='{{.HostConfig.Memory}}' "$n")
  lim_mb=$((lim_b / 1024 / 1024))
  usage=$(sudo docker stats --no-stream --format '{{.MemUsage}}' "$n" 2>/dev/null | head -1)
  echo "$n: limit=${lim_mb}MB usage=$usage"
done | head -32
EOF
```

---

## Analysis checklist

### CPU bottleneck indicators

- 1m / 5m / 15m load averages vs `nproc`. Load > `nproc × 2` for 15m = real CPU pressure.
- Single process > 50% sustained = investigate (look at `ps aux`).
- `top` CPU% breakdown: high `wa` (I/O wait) → look at disk; high `us` → app code; high `sy` → syscalls (often docker, fork bombs).
- Identify processes hogging CPU and cross-reference with container (`ps aux` PID → `docker ps -q | xargs sudo docker inspect`).

### Memory bottleneck indicators

- `free -h`: used / total. > 90% used = pressure.
- swap usage > 0 = past pressure; sustained = current pressure.
- OOM history in `dmesg`: killed processes named?
- Per-container `MemPerc` > 80% of limit = OOM-imminent.
- Containers with `HostConfig.Memory: 0` = unlimited = OOM gambit (violates Fabrik invariant; should fail validator).

### Disk I/O indicators

- `df -h`: `/` > 80% = imminent failure (logs stop writing, builds break).
- `iostat`: `%util` > 80% sustained = disk-bound; `await` > 20ms = high latency.
- Top dirs: `/var/lib/docker/` typically largest. `/opt/backups/` grows nightly.
- Look for runaway log volume (single container > 1 GB log).

### Network indicators

- `ip -s link`: high `rx_dropped` or `tx_dropped` = NIC pressure (rare on VPS).
- High `tx_errors` on `wg0` = MTU issues or mesh instability.
- Established TCP count: normal hub ~10-50; spoke ~5-15. Sustained > 500 = leak or attack.
- conntrack: `nf_conntrack_count / nf_conntrack_max` > 70% = NAT pressure (kernel will drop new conns at 100%). Default `nf_conntrack_max` on the fleet is 262144; typical idle count is ~50-100.

### Container-specific patterns

- `postgres-main`: high CPU during backup window (postgres-dumps plan runs 02:00). Sustained high = query bloat or missing indexes.
- `redis-main`: should be low CPU + small RSS (< 50 MB typically).
- `prometheus`: steady CPU + steady RSS (scrape volume). Growth = retention not pruning.
- `traefik`: bursts on connection storms. Sustained high = upstream issue.
- `grafana`/`gatus`/`backrest` UIs: bursts on auth. Sustained = bot scanning.

### Spoke-only patterns

- Promtail steady ~30-60 MiB. Higher = log volume from sibling containers high.
- Backrest idle 99% of the time; spikes during backup window (typically 02:00-03:00).
- node-exporter / cadvisor steady < 30 MiB each.

---

## Output format

```markdown
## Performance Audit — <hostN> — <UTC date>

**Verdict:** GREEN / YELLOW / RED
**Primary bottleneck (if any):** CPU | MEMORY | DISK | NETWORK | NONE
**Summary:** one-paragraph

### Findings (ranked by impact)
1. [bottleneck-class] <component> — <quantified observation>
   - Evidence: <command excerpt>
   - Cause hypothesis: <best guess>
   - Fix or next step: <action>

### Quick-win remediations
1. ...

### What's healthy (verify-not-fix)
- ...
```
