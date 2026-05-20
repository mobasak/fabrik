#!/bin/bash
# Full system audit data collection — runs ON the VPS via SSH.
# Usage: ssh vps 'bash -s' < scripts/audit/01-full-system.sh
set -uo pipefail

echo "========== SYSTEM IDENTITY =========="
uname -a
echo "---"
uptime
echo "---"
systemd-detect-virt 2>/dev/null || echo "bare-metal"
echo "---"
head -5 /etc/os-release

echo ""
echo "========== CPU & PROCESSES =========="
echo "--- load ---"
cat /proc/loadavg
echo "--- cpu info ---"
nproc
echo "--- vmstat (5 samples) ---"
vmstat 1 5
echo "--- top 15 by memory ---"
ps aux --sort=-%mem | head -16
echo "--- top 15 by cpu ---"
ps aux --sort=-%cpu | head -16
echo "--- zombies ---"
ps aux | awk '$8 ~ /Z/ {print}' | head -10 || echo "none"

echo ""
echo "========== MEMORY =========="
free -h
echo "---"
grep -E "MemTotal|MemFree|MemAvailable|Buffers|^Cached|SwapTotal|SwapFree|Dirty|Writeback|AnonPages|Shmem|SReclaimable" /proc/meminfo
echo "--- swappiness ---"
cat /proc/sys/vm/swappiness
echo "--- swap devices ---"
swapon --show 2>/dev/null || echo "no swap"
echo "--- oom kills (last 50 dmesg lines) ---"
sudo dmesg -T 2>/dev/null | grep -i "oom\|out of memory\|killed process" | tail -10 || echo "none"

echo ""
echo "========== DISK & I/O =========="
echo "--- space ---"
df -h
echo "--- inodes ---"
df -i
echo "--- block devices ---"
lsblk
echo "--- fstab ---"
cat /etc/fstab 2>/dev/null | grep -v "^#" | grep -v "^$"
echo "--- iostat (if available) ---"
iostat -xz 1 3 2>/dev/null || echo "sysstat not installed"
echo "--- pressure ---"
cat /proc/pressure/io 2>/dev/null || echo "PSI not available"
cat /proc/pressure/cpu 2>/dev/null || true
cat /proc/pressure/memory 2>/dev/null || true

echo ""
echo "========== NETWORK =========="
echo "--- socket summary ---"
ss -s
echo "--- TIME_WAIT count ---"
ss -tn state time-wait 2>/dev/null | wc -l
echo "--- CLOSE_WAIT count ---"
ss -tn state close-wait 2>/dev/null | wc -l
echo "--- listening ---"
ss -tulpn
echo "--- interface stats (primary only) ---"
PRIMARY_IF=$(ip route get 1.1.1.1 2>/dev/null | head -1 | awk '{for(i=1;i<=NF;i++) if($i=="dev") print $(i+1)}')
ip -s link show "$PRIMARY_IF" 2>/dev/null || ip -s link show eth0 2>/dev/null || echo "cannot detect primary interface"
echo "--- dns ---"
cat /etc/resolv.conf

echo ""
echo "========== SERVICES =========="
echo "--- failed units ---"
systemctl --failed 2>/dev/null || true
echo "--- running service count ---"
systemctl list-units --type=service --state=running 2>/dev/null | wc -l
echo "--- journal disk usage ---"
sudo journalctl --disk-usage 2>/dev/null || true
echo "--- /var/log size ---"
du -sh /var/log/ 2>/dev/null

echo ""
echo "========== SECURITY =========="
echo "--- ufw ---"
sudo ufw status verbose 2>/dev/null || echo "ufw not active"
echo "--- DOCKER-USER chain ---"
sudo iptables -L DOCKER-USER -n --line-numbers -v 2>/dev/null || echo "no DOCKER-USER chain"
echo "--- public listeners (not loopback/docker) ---"
ss -tlnp | grep -v "127.0.0.1\|::1\|10\.0\." | grep "0.0.0.0\|::\|" || echo "none"
echo "--- recent logins ---"
sudo last -10 2>/dev/null
echo "--- ssh failed (24h) ---"
sudo journalctl -u ssh --since "24 hours ago" 2>/dev/null | grep -c "Failed password" || echo "0"
echo "--- apparmor ---"
sudo aa-status 2>/dev/null | head -20 || echo "apparmor not available"

echo ""
echo "========== DOCKER =========="
echo "--- containers ---"
sudo docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | sort
echo "--- resource usage ---"
sudo docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | sort
echo "--- disk usage ---"
sudo docker system df
echo "--- unhealthy/restarting ---"
sudo docker ps --format "{{.Names}} {{.Status}}" | grep -iE "restarting|unhealthy|Exited" || echo "none"
echo "--- dangling volumes ---"
sudo docker volume ls -f dangling=true --format "{{.Name}}" || echo "none"
echo "--- dangling images ---"
sudo docker images -f dangling=true --format "{{.ID}} {{.Size}}" || echo "none"

echo ""
echo "========== END =========="
