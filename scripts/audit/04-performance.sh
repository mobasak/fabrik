#!/bin/bash
# Performance bottleneck audit data collection — runs ON the VPS via SSH.
# Usage: ssh vps 'bash -s' < scripts/audit/04-performance.sh
set -uo pipefail

echo "========== LOAD & CPU =========="
echo "--- load ---"
uptime
cat /proc/loadavg
echo "--- cores ---"
nproc
echo "--- vmstat (10 samples, 1s interval) ---"
vmstat 1 10
echo "--- pressure ---"
echo "cpu:" && cat /proc/pressure/cpu 2>/dev/null || echo "N/A"
echo "memory:" && cat /proc/pressure/memory 2>/dev/null || echo "N/A"
echo "io:" && cat /proc/pressure/io 2>/dev/null || echo "N/A"

echo ""
echo "========== MEMORY DEEP DIVE =========="
free -h
echo "---"
grep -E "MemTotal|MemFree|MemAvailable|Buffers|^Cached|SwapTotal|SwapFree|Dirty|Writeback|AnonPages|Mapped|Shmem|SReclaimable|SUnreclaim|KernelStack|PageTables|CommitLimit|Committed_AS" /proc/meminfo
echo "--- swappiness ---"
cat /proc/sys/vm/swappiness
echo "--- swap ---"
swapon --show 2>/dev/null || echo "no swap"
echo "--- oom kills ---"
sudo dmesg -T 2>/dev/null | grep -i "oom\|out of memory\|killed process" | tail -10 || echo "none"

echo ""
echo "========== DISK I/O =========="
echo "--- iostat (3 samples) ---"
iostat -xz 1 3 2>/dev/null || echo "sysstat not installed (apt install sysstat)"
echo "--- top I/O processes ---"
iotop -boqn 3 2>/dev/null || echo "iotop not installed"

echo ""
echo "========== DISK SPACE =========="
df -h
echo "--- big directories ---"
du -sh /var/lib/docker/ /var/log/ /data/coolify/ /opt/ /tmp/ 2>/dev/null | sort -rh

echo ""
echo "========== NETWORK =========="
echo "--- socket summary ---"
ss -s
echo "--- TIME_WAIT ---"
ss -tn state time-wait 2>/dev/null | wc -l
echo "--- CLOSE_WAIT ---"
ss -tn state close-wait 2>/dev/null | wc -l
echo "--- interface errors (primary) ---"
PRIMARY_IF=$(ip route get 1.1.1.1 2>/dev/null | head -1 | awk '{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1)}')
ip -s link show "$PRIMARY_IF" 2>/dev/null || echo "cannot detect"
echo "--- latency to 1.1.1.1 ---"
ping -c 5 -q 1.1.1.1 2>/dev/null | tail -2

echo ""
echo "========== TOP PROCESSES =========="
echo "--- by RSS memory ---"
ps -eo pid,ppid,user,%mem,%cpu,rss,comm --sort=-rss | head -20
echo "--- by CPU ---"
ps -eo pid,ppid,user,%mem,%cpu,rss,comm --sort=-%cpu | head -20

echo ""
echo "========== CONTAINER RESOURCE USAGE =========="
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}" | sort -t$'\t' -k4 -rh | head -20

echo ""
echo "========== FILE DESCRIPTORS =========="
cat /proc/sys/fs/file-nr
echo "ulimit: $(ulimit -n)"

echo ""
echo "========== KERNEL WARNINGS =========="
sudo dmesg -T 2>/dev/null | grep -iE "error|fail|warn|hung_task|blocked|hardware" | tail -20 || echo "none"

echo ""
echo "========== END =========="
