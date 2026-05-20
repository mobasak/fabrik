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

# Memory rising >5MB/min on any container
prom_check 'deriv(container_memory_usage_bytes{name!=""}[1h])>5e6' \
  && ANOMALIES+="memory_rising "

# Container restarted in last 15 min (start_time changed = restart)
prom_check 'changes(container_start_time_seconds{name!=""}[15m])>0' \
  && ANOMALIES+="container_restarted "

# CPU >70% sustained on any container
prom_check 'rate(container_cpu_usage_seconds_total{name!=""}[15m])*100>70' \
  && ANOMALIES+="cpu_high "

# Disk >75%
prom_check '(1-node_filesystem_avail_bytes{mountpoint="/"}/node_filesystem_size_bytes{mountpoint="/"})>0.75' \
  && ANOMALIES+="disk_high "

# Host RAM >80%
prom_check '(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)>0.80' \
  && ANOMALIES+="host_memory_high "

# Load average > 2x CPU count (dynamic threshold)
CPU_COUNT=$(nproc 2>/dev/null || echo 4)
prom_check "node_load5>$((CPU_COUNT * 2))" \
  && ANOMALIES+="load_high "

# OOM kill detected (cAdvisor container_oom_events_total)
prom_check 'increase(container_oom_events_total[15m])>0' \
  && ANOMALIES+="oom_kill "

# Disk full prediction — will disk run out within 7 days at current rate?
prom_check 'predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h],7*86400)<0' \
  && ANOMALIES+="disk_prediction_7d "

# Prometheus target down
prom_check 'up==0' \
  && ANOMALIES+="target_down "

# Log pipeline dead (Loki receiving no lines = Promtail or pipeline broken)
prom_check 'rate(loki_distributor_lines_received_total[10m])==0' \
  && ANOMALIES+="log_pipeline_dead "

fi  # PROM_REACHABLE

# ── TLS certificate expiry check (no Prometheus needed) ──────────────────

DOMAINS="ocoron.com status.vps1.ocoron.com monitor.vps1.ocoron.com errors.vps1.ocoron.com coolify.vps1.ocoron.com"
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
