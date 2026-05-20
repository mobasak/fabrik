# Performance Bottleneck Audit — CPU, Memory, Disk, Network

Deep-dive into performance bottlenecks on this Ubuntu 24.04 VPS. The system runs ~36 Docker containers on 6 vCores / 11GB RAM / 108GB disk. Identify what's slow, why, and how to fix it.

## Data Collection

**Automated:** `ssh vps 'sudo bash -s' < /opt/fabrik/scripts/audit/04-performance.sh`

**Or manual:**

```bash
# 1. Load overview (run during the problem window)
uptime
cat /proc/loadavg

# 2. CPU — per-core breakdown + steal time
mpstat -P ALL 1 5 2>/dev/null || echo "mpstat not installed — apt install sysstat"
vmstat 1 10

# 3. Memory — true pressure
free -h
cat /proc/meminfo | grep -E "MemTotal|MemAvailable|Buffers|^Cached|SwapTotal|SwapFree|Dirty|Writeback|AnonPages|Mapped|Shmem|SReclaimable"
cat /proc/sys/vm/swappiness
swapon --show

# 4. Memory pressure (cgroup v2)
cat /proc/pressure/memory
cat /proc/pressure/cpu
cat /proc/pressure/io

# 5. Disk I/O
iostat -xz 1 5 2>/dev/null || echo "iostat not installed"
iotop -boqn 3 2>/dev/null || echo "iotop not installed — apt install iotop-c"

# 6. Disk space + inodes
df -h
df -i
du -sh /var/lib/docker/ /var/log/ /data/coolify/ /opt/ 2>/dev/null

# 7. Network latency + throughput
ss -s
ss -tn state time-wait | wc -l
ss -tn state close-wait | wc -l
ip -s link show eth0 2>/dev/null || ip -s link
ping -c 5 1.1.1.1

# 8. Top processes by resource
ps aux --sort=-%mem | head -15
ps aux --sort=-%cpu | head -15
ps -eo pid,ppid,user,%mem,%cpu,rss,vsz,comm --sort=-rss | head -20

# 9. Container resource usage
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}" | sort -t$'\t' -k3 -rh | head -20

# 10. Kernel messages (OOM, I/O errors, hardware)
dmesg -T | tail -50
dmesg -T | grep -iE "oom|error|fail|warn|hung_task|blocked" | tail -20

# 11. Open file descriptors (system-wide)
cat /proc/sys/fs/file-nr
ulimit -n

# 12. Scheduler latency (if perf is available)
perf sched latency -s max 2>/dev/null | head -20 || echo "perf not installed"
```

## Analysis Focus

### CPU Bottleneck Indicators
- Load average > 6.0 (matches core count) = saturated
- Steal time > 5% = hypervisor throttling (contact hosting provider)
- `wa` (I/O wait) > 10% = disk-bound, not CPU-bound
- Context switches > 60k/s = excessive scheduling overhead

### Memory Bottleneck Indicators
- MemAvailable < 500MB on 11GB = danger zone
- Swap usage > 0 = memory pressure exists
- `some avg10` in /proc/pressure/memory > 10% = applications waiting for memory
- Dirty pages > 100MB = writes backing up

### Disk I/O Indicators
- `%util` > 80% = disk saturated
- `await` > 20ms on SSD = latency problem
- `avgqu-sz` > 4 = queue building up
- /var/lib/docker > 30GB = image/volume bloat

### Network Indicators
- TIME_WAIT > 5000 = connection churn (adjust `net.ipv4.tcp_tw_reuse`)
- CLOSE_WAIT > 100 = application-side connection leak
- Packet drops on interface = NIC or kernel buffer overflow

## Output Format

1. **BOTTLENECK SUMMARY** — which resource is the constraint: CPU / Memory / Disk / Network / None
2. **TOP 5 CONSUMERS** — ranked by impact, with container name and metric
3. **ROOT CAUSE ANALYSIS** — why the bottleneck exists (configuration, workload, hardware)
4. **REMEDIATION** — tuning commands, container limit adjustments, what to scale
