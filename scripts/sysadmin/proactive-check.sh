#!/bin/bash
# Two-stage proactive VPS health check.
#
# Stage 1: Pure bash — curl Prometheus for threshold checks. Zero Claude tokens.
#          95% of the time everything is fine → exit silently.
#
# Stage 2: Claude analyzes — only when Stage 1 detects an anomaly.
#          Fire-and-forget: claude -p, send result to Telegram via Apprise, exit.
#
# Cron: */15 * * * * root /opt/fabrik/scripts/sysadmin/proactive-check.sh
#
# Rate limit: max 5 Claude wakes per hour (file-based counter).

set -uo pipefail

# Prometheus runs inside Docker. Host can't resolve Docker DNS names.
# Use docker exec to query from inside the prometheus container.
prom_query() {
  sudo docker exec prometheus wget -qO- "http://localhost:9090/api/v1/query" --post-data="query=$1" 2>/dev/null
}
APPRISE_SEND() {
  # Apprise also runs inside Docker — use docker exec or direct container IP
  local title="$1" body="$2"
  local escaped_body
  escaped_body=$(echo "$body" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
  sudo docker run --rm --network coolify curlimages/curl:latest -sf -X POST \
    "http://apprise:8000/notify/alerts" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"$title\",\"body\":${escaped_body}}" 2>/dev/null
}
RATE_FILE="/tmp/sysadmin-proactive-rate"
RATE_LIMIT=5
PROJECT_DIR="/opt/fabrik"
SYSTEM_PROMPT_FILE="$PROJECT_DIR/scripts/sysadmin/system-prompt.txt"

# ── Stage 1: PromQL threshold checks (zero cost) ─────────────────────────

prom_check() {
  local query="$1"
  local result
  # Query Prometheus from INSIDE the container (host can't resolve Docker DNS)
  result=$(prom_query "$query")
  # If Prometheus is unreachable, result is empty — caller detects via PROM_REACHABLE
  if [ -z "$result" ]; then
    PROM_REACHABLE=false
    return 1
  fi
  # Non-empty result array = anomaly detected
  echo "$result" | jq -e '.data.result | length > 0' >/dev/null 2>&1
}

# As of 2026-05-31, Prometheus on vps1 scrapes vps2 + vps3 too, and every
# series carries a `host` label (vps1 / vps2 / vps3). prom_hosts() extracts
# the unique hosts from a query's result so callers can include them in
# the anomaly string.
prom_hosts() {
  local query="$1"
  prom_query "$query" 2>/dev/null \
    | jq -r '.data.result // [] | map(.metric.host // "?") | unique | join(",")' 2>/dev/null
}

ANOMALIES=""
PROM_REACHABLE=true

# Quick connectivity check — if Prometheus is down, flag it immediately
PROM_TEST=$(prom_query 'up' 2>/dev/null)
if [ -z "$PROM_TEST" ]; then
  ANOMALIES+="prometheus_unreachable "
  PROM_REACHABLE=false
fi

# Only run PromQL checks if Prometheus is reachable
if [ "$PROM_REACHABLE" = "true" ]; then

# All queries below cover all hosts in the mesh (vps1 + vps2 + vps3) because
# Prometheus on vps1 scrapes spoke node-exporter + cadvisor + promtail. When
# an anomaly fires, prom_hosts() reports which host(s) it came from so the
# alert string includes context (e.g. "cpu_high[vps2]" not just "cpu_high").

_q='deriv(container_memory_usage_bytes{name!=""}[1h])>5e6'
prom_check "$_q" && ANOMALIES+="memory_rising[$(prom_hosts "$_q")] "

_q='changes(container_start_time_seconds{name!=""}[15m])>0'
prom_check "$_q" && ANOMALIES+="container_restarted[$(prom_hosts "$_q")] "

_q='rate(container_cpu_usage_seconds_total{name!=""}[15m])*100>70'
prom_check "$_q" && ANOMALIES+="cpu_high[$(prom_hosts "$_q")] "

_q='(1-node_filesystem_avail_bytes{mountpoint="/"}/node_filesystem_size_bytes{mountpoint="/"})>0.75'
prom_check "$_q" && ANOMALIES+="disk_high[$(prom_hosts "$_q")] "

_q='(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)>0.80'
prom_check "$_q" && ANOMALIES+="host_memory_high[$(prom_hosts "$_q")] "

# Load: vps1 has 6 cores, vps2/vps3 have 4. Use per-host check (PromQL handles).
CPU_COUNT=$(nproc 2>/dev/null || echo 4)
prom_check "node_load5>$((CPU_COUNT * 2))" \
  && ANOMALIES+="load_high[$(prom_hosts "node_load5>$((CPU_COUNT * 2))")] "

_q='increase(container_oom_events_total[15m])>0'
prom_check "$_q" && ANOMALIES+="oom_kill[$(prom_hosts "$_q")] "

_q='predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h],7*86400)<0'
prom_check "$_q" && ANOMALIES+="disk_prediction_7d[$(prom_hosts "$_q")] "

_q='up==0'
prom_check "$_q" && ANOMALIES+="target_down[$(prom_hosts "$_q")] "

# Log pipeline dead (Loki receiving no lines = Promtail or pipeline broken)
prom_check 'rate(loki_distributor_lines_received_total[10m])==0' \
  && ANOMALIES+="log_pipeline_dead "

fi  # PROM_REACHABLE

# ── TLS certificate expiry check (no Prometheus needed) ──────────────────
#
# Stale subdomains removed 2026-06-01 W10: coolify.vps1 was deleted in
# residue cleanup (2026-05-31 evening) — would always fail check + add noise.
# Spoke apex + wildcard added; cert is issued on first tenant deploy (W4)
# and timeout indicates "no cert yet" which is intentional pre-W4.

DOMAINS="ocoron.com status.vps1.ocoron.com monitor.vps1.ocoron.com errors.vps1.ocoron.com"
for domain in $DOMAINS; do
  expiry=$(echo | timeout 5 openssl s_client -servername "$domain" -connect "$domain":443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  if [ -n "$expiry" ]; then
    expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null)
    now_epoch=$(date +%s)
    days_left=$(( (expiry_epoch - now_epoch) / 86400 ))
    if [ "$days_left" -lt 14 ]; then
      ANOMALIES+="cert_expiring:${domain}:${days_left}d "
    fi
  fi
done

# ── W10: Backup health (restic snapshot age across all 3 hosts' Backrest stacks) ──
#
# Each host's Backrest writes to a distinct restic repo. Hub at bucket root,
# spokes at /spokes/vpsN/ prefix. Stale = no snapshot for any plan in >36h.
# All 3 hosts: each Backrest's snapshots --json --last 1 per plan.
# Failure modes: Backrest container down → empty result; B2 unreachable →
# timeout. Both are themselves anomalies the bot should know about.
#
# Hub-only check here to keep proactive-check.sh fast (15-min cron); spokes'
# Backrest is monitored indirectly via the spoke-promtail-positions and via
# Backrest health probes (future W10.b — Gatus). The hub repo failing is the
# canonical "backups not happening" signal.

if command -v docker >/dev/null 2>&1 && sudo docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^backrest$'; then
    BACKREST_PW_FILE=/opt/backrest/.restic-password
    if [ -r "$BACKREST_PW_FILE" ] || sudo test -r "$BACKREST_PW_FILE"; then
        RESTIC_PW=$(sudo cat "$BACKREST_PW_FILE" 2>/dev/null)
    else
        # Fallback: hub stores password in config.json (legacy)
        RESTIC_PW=$(sudo python3 -c "import json; print(json.load(open('/opt/backrest/config/config.json'))['repos'][0]['password'])" 2>/dev/null)
    fi
    if [ -n "$RESTIC_PW" ]; then
        # 36h = 129600s
        STALE_THRESHOLD=$((36 * 3600))
        NOW_EPOCH=$(date +%s)
        for plan in postgres-dumps docker-volumes opt-configs host-state; do
            LATEST=$(sudo docker exec -e RESTIC_PASSWORD="$RESTIC_PW" backrest /bin/restic \
                -r s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups \
                snapshots --tag plan:${plan} --last --json 2>/dev/null \
                | python3 -c "import json,sys
d=json.load(sys.stdin)
print(d[-1]['time'] if d else '')" 2>/dev/null)
            if [ -z "$LATEST" ]; then
                ANOMALIES+="backup_missing[hub:${plan}] "
            else
                LATEST_EPOCH=$(date -d "$LATEST" +%s 2>/dev/null || echo 0)
                AGE=$((NOW_EPOCH - LATEST_EPOCH))
                if [ "$AGE" -gt "$STALE_THRESHOLD" ]; then
                    HOURS=$((AGE / 3600))
                    ANOMALIES+="backup_stale[hub:${plan}:${HOURS}h] "
                fi
            fi
        done
    fi
fi

# ── W10: Mesh health (wg handshake age per peer) ──────────────────────────
#
# Only run on the hub (the only host that has multi-peer view). On spokes
# this would only check the hub which is redundant. Hub age thresholds:
#   - <5 min: healthy
#   - 5-15 min: Tier B suspicion (was peer rebooting?)
#   - >15 min: Tier C critical (mesh broken to that peer)

if [ -e /etc/wireguard/wg0.conf ] && sudo wg show wg0 >/dev/null 2>&1; then
    NOW_EPOCH=$(date +%s)
    while read -r pubkey ts; do
        [ -z "$pubkey" ] && continue
        [ "$ts" = "0" ] && { ANOMALIES+="mesh_no_handshake[${pubkey:0:12}] "; continue; }
        AGE=$((NOW_EPOCH - ts))
        if   [ "$AGE" -gt 900 ];  then ANOMALIES+="mesh_broken[${pubkey:0:12}:$((AGE/60))m] "
        elif [ "$AGE" -gt 300 ];  then ANOMALIES+="mesh_degraded[${pubkey:0:12}:$((AGE/60))m] "
        fi
    done < <(sudo wg show wg0 latest-handshakes 2>/dev/null)
fi

# ── W10: DR store staleness (GitHub API last-commit age) ─────────────────
#
# W9 mirrors /opt/fabrik/.env continuously via inotify; if commits stop landing
# the dev WSL watcher is broken OR the dev WSL itself is down. Either is
# operator-relevant. Token from .env (scope: repo:read on mobasak/fabrik-dr-store).
# Threshold: >30d (env rarely changes; 30 days is "something is wrong").

# Token lookup: vps1 doesn't carry /opt/fabrik/.env (canonical lives on dev WSL,
# mirrored via W9). The sysadmin bot's own env file /opt/fabrik/.env.sysadmin
# DOES exist on vps1 and is root-readable — the right place for the GH token
# that drives this watcher. Check both for robustness.
GH_TOKEN=""
for env_file in /opt/fabrik/.env.sysadmin /opt/fabrik/.env; do
    if sudo test -r "$env_file"; then
        v=$(sudo grep -E '^(GITHUB_TOKEN|GH_TOKEN)=' "$env_file" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')
        [ -n "$v" ] && { GH_TOKEN="$v"; break; }
    fi
done

if true; then
    if [ -n "$GH_TOKEN" ]; then
        LATEST=$(timeout 8 curl -sS -H "Authorization: Bearer ${GH_TOKEN}" \
            "https://api.github.com/repos/mobasak/fabrik-dr-store/commits?per_page=1" 2>/dev/null \
            | python3 -c "import json,sys
d=json.load(sys.stdin)
print(d[0]['commit']['committer']['date'] if isinstance(d, list) and d else '')" 2>/dev/null)
        if [ -n "$LATEST" ]; then
            LATEST_EPOCH=$(date -d "$LATEST" +%s 2>/dev/null || echo 0)
            AGE=$(($(date +%s) - LATEST_EPOCH))
            if [ "$AGE" -gt $((30 * 86400)) ]; then
                ANOMALIES+="dr_store_stale[$((AGE / 86400))d] "
            fi
        fi
        # If LATEST is empty (auth fail, rate limit, or repo gone) we silently
        # skip — Tier C would be too noisy for transient API issues.
    else
        # Once-per-hour warning so the operator notices the watcher is dormant.
        # Stamp file prevents flooding /var/log/sysadmin-proactive.log.
        STAMP=/var/lib/sysadmin/.dr_store_dormant_warned
        sudo mkdir -p "$(dirname "$STAMP")" 2>/dev/null || true
        if [ ! -f "$STAMP" ] || [ "$(( $(date +%s) - $(stat -c %Y "$STAMP" 2>/dev/null || echo 0) ))" -gt 3600 ]; then
            echo "$(date -Iseconds) WARN: dr_store watcher dormant — GITHUB_TOKEN (or GH_TOKEN) not set in /opt/fabrik/.env.sysadmin or /opt/fabrik/.env. Add a fine-grained token with 'Contents: Read' on mobasak/fabrik-dr-store to enable. Until then, dev-WSL watcher loss won't be auto-detected by the bot." >&2
            sudo touch "$STAMP" 2>/dev/null || true
        fi
    fi
fi

# ── All clear? Exit silently. ─────────────────────────────────────────────

if [ -z "$ANOMALIES" ]; then
  exit 0
fi

echo "$(date -Iseconds) Anomalies detected: $ANOMALIES"

# ── Rate limit check ──────────────────────────────────────────────────────

CURRENT_HOUR=$(date +%Y%m%d%H)
RATE_HOUR=$(cat "${RATE_FILE}.hour" 2>/dev/null || echo "")
RATE_COUNT=$(cat "${RATE_FILE}.count" 2>/dev/null || echo "0")

if [ "$RATE_HOUR" != "$CURRENT_HOUR" ]; then
  # New hour — reset counter
  echo "$CURRENT_HOUR" > "${RATE_FILE}.hour"
  RATE_COUNT=0
fi

if [ "$RATE_COUNT" -ge "$RATE_LIMIT" ]; then
  echo "Rate limited ($RATE_COUNT/$RATE_LIMIT this hour). Skipping Claude."
  exit 0
fi

# Increment counter
echo $((RATE_COUNT + 1)) > "${RATE_FILE}.count"

# ── Stage 2: Collect context + wake Claude ────────────────────────────────

CONTEXT="Proactive check detected: $ANOMALIES

Quick system snapshot:
$(free -h | head -2)
$(df -h / | tail -1)
$(cat /proc/loadavg)

Container resource usage (top 10 by memory):
$(sudo docker stats --no-stream --format '{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' 2>/dev/null | sort -t$'\t' -k2 -rh | head -10)

Recent container events:
$(sudo docker events --since 15m --until now --filter event=die --filter event=oom --format '{{.Actor.Attributes.name}} {{.Action}}' 2>/dev/null | tail -10)"

# Load system prompt
SYS_PROMPT=""
[ -f "$SYSTEM_PROMPT_FILE" ] && SYS_PROMPT=$(cat "$SYSTEM_PROMPT_FILE")

RESULT=$(claude -p --model opus \
  "Proactive health check found anomalies. Analyze this data and act autonomously per your system prompt rules.

If the anomalies are benign (e.g. a scheduled restart, normal CPU spike), respond with exactly ALL_CLEAR.

If action is needed:
1. Take the action yourself (docker restart, docker update --memory, etc.) per your safety rules
2. Report what you found AND what you did in this format:

**Target:** [container]
**Issue:** [what went wrong]
**Action:** [what you ran]
**Result:** [outcome]

If you cannot act (critical-infra, monitoring, or needs owner approval), report the issue and say what you would do.

Remember: you run locally on this VPS. Use sudo docker commands directly." \
  --system-prompt "$SYS_PROMPT" \
  --permission-mode bypassPermissions \
  --no-session-persistence \
  <<< "$CONTEXT" 2>/dev/null)

# ── Send to Telegram if issues found ──────────────────────────────────────

if [ -z "$RESULT" ] || [ "$RESULT" = "ALL_CLEAR" ]; then
  echo "Claude says all clear despite triggers. Likely benign."
  exit 0
fi

# Send to Telegram via Apprise (inside Docker network)
APPRISE_SEND "🔍 Proactive Check" "$RESULT"

echo "Sent proactive alert to Telegram."
