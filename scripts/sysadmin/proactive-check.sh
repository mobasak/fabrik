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
  # printf '%s' (NOT echo) — echo mangles backslash sequences (\n, \t) in Claude's output,
  # silently corrupting the alert body before python json-encodes it.
  escaped_body=$(printf '%s' "$body" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
  # Exit-check + log so a delivery failure (Apprise down, network gone) is OBSERVABLE — the
  # empty-RESULT escalation below relies on this actually reaching the operator, so a silent
  # drop would defeat "fail-closed". Logs to stderr → the cron's proactive log.
  if ! sudo docker run --rm --network fabrik curlimages/curl:latest -sf -X POST \
    "http://apprise:8000/notify/alerts" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"$title\",\"body\":${escaped_body}}" 2>/dev/null; then
    # Fallback: direct Telegram (same vars/file claude_rotate.py::_notify_telegram uses).
    # Apprise is a HUB-ONLY container — on spokes the fabrik-network send above ALWAYS
    # fails (no `apprise` DNS name), which left spoke alerts silently undelivered for
    # weeks (live-found 2026-08-03). Also covers hub-apprise-down. Token never echoed.
    local tok chat
    tok=$(sudo grep -E '^TELEGRAM_BOT_TOKEN=' /opt/fabrik/.env.sysadmin 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')  # noqa — grep PATTERN for the env file, not a hardcoded credential
    chat=$(sudo grep -E '^TELEGRAM_OWNER_ID=' /opt/fabrik/.env.sysadmin 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')
    if [ -n "$tok" ] && [ -n "$chat" ]; then
      local text
      text=$(printf '%s\n\n%s' "$title" "$body" | head -c 4000)
      if curl -sf -o /dev/null -m 15 -X POST "https://api.telegram.org/bot${tok}/sendMessage" \
        --data-urlencode "chat_id=${chat}" --data-urlencode "text=${text}" 2>/dev/null; then
        return 0
      fi
    fi
    echo "$(date -Is) APPRISE_SEND FAILED to deliver via fabrik network AND telegram fallback: ${title}" >&2
    return 1
  fi
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

# The whole PromQL battery is HUB-ONLY by design: Prometheus runs only on vps1 and
# scrapes the spokes (host-labelled series), so these checks cover the entire fleet
# from the hub. On a spoke there is no `prometheus` container — running the stage
# there fired a false `prometheus_unreachable` every 15 min for weeks (live-found
# 2026-08-03). Hostname gate (not container-presence): the hub must still flag
# prometheus_unreachable when its own container dies.
IS_HUB=0
[ "$(hostname -s)" = "vps1" ] && IS_HUB=1

if [ "$IS_HUB" = "1" ]; then

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

# SUSTAINED down, not an instantaneous blip. The spoke targets are scraped from LA across the
# transatlantic WireGuard mesh (~133 ms base, measured scrape durations 0.15–2.7 s with congestion
# spikes), so a bare `up==0` fires on a single slow scrape — 2026-08-07 saw target_down[vps2]/[vps3]
# alerts while every target was actually up and TCP scrapes ran 6/6. `max_over_time(up[10m])==0`
# means the target was NEVER up across 10 minutes = genuinely down, not mesh jitter. (NOT
# min_over_time — that matches "down at least once", i.e. MORE flap-sensitive; empirically 7 hits
# vs 0 for max_over_time on a healthy fleet.)
_q='max_over_time(up[10m])==0'
prom_check "$_q" && ANOMALIES+="target_down[$(prom_hosts "$_q")] "

# Log pipeline dead (Loki receiving no lines = Promtail or pipeline broken)
prom_check 'rate(loki_distributor_lines_received_total[10m])==0' \
  && ANOMALIES+="log_pipeline_dead "

fi  # PROM_REACHABLE

fi  # IS_HUB — end of the hub-only PromQL battery

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
        # HOST-AWARE repo + plan set. Each host's Backrest writes to ITS OWN repo with
        # ITS OWN password: hub at the bucket root (4 plans), spokes at /spokes/<host>/
        # (2 plans). The old hardcoded hub-root+hub-plans loop, run on a spoke with the
        # SPOKE's password, could never see a snapshot → four false
        # `backup_missing[hub:*]` every 15 min for weeks (live-found 2026-08-03).
        HOST_TAG=$(hostname -s)
        if [ "$HOST_TAG" = "vps1" ]; then
            RESTIC_REPO="s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups"
            BACKUP_PLANS="postgres-dumps docker-volumes opt-configs host-state"
        else
            RESTIC_REPO="s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups/spokes/${HOST_TAG}"
            BACKUP_PLANS="host-state opt-configs"
        fi
        # 36h = 129600s
        STALE_THRESHOLD=$((36 * 3600))
        NOW_EPOCH=$(date +%s)
        for plan in $BACKUP_PLANS; do
            # Classify TRANSPORT failure apart from "genuinely no snapshots". The restic call can
            # fail transiently (B2 blip, repo lock held by a running backup/prune, container busy)
            # — the old code swallowed stderr and read an empty result as backup_missing, crying
            # wolf about backups that were fine (live false-positive: backup_missing[vps2:host-state]
            # 2026-08-07 03:00 while host-state had snapshotted at 02:00). A backup alert that
            # cries wolf is worse than none: it trains the operator to ignore the real one.
            RESTIC_OUT=$(sudo docker exec -e RESTIC_PASSWORD="$RESTIC_PW" backrest /bin/restic \
                -r "$RESTIC_REPO" \
                snapshots --tag plan:${plan} --last --json 2>/dev/null)
            RESTIC_RC=$?
            if [ "$RESTIC_RC" -ne 0 ]; then
                # Couldn't ask — say THAT, don't claim the backup is missing.
                ANOMALIES+="backup_check_failed[${HOST_TAG}:${plan}:rc${RESTIC_RC}] "
                continue
            fi
            LATEST=$(printf '%s' "$RESTIC_OUT" | python3 -c "import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    sys.exit(3)          # unparseable → transport/format problem, NOT 'no snapshots'
print(d[-1]['time'] if d else '')")
            PARSE_RC=$?
            if [ "$PARSE_RC" -ne 0 ]; then
                ANOMALIES+="backup_check_failed[${HOST_TAG}:${plan}:parse] "
            elif [ -z "$LATEST" ]; then
                # Valid, EMPTY snapshot list — the repo genuinely holds no snapshot for this plan.
                ANOMALIES+="backup_missing[${HOST_TAG}:${plan}] "
            else
                LATEST_EPOCH=$(date -d "$LATEST" +%s 2>/dev/null || echo 0)
                AGE=$((NOW_EPOCH - LATEST_EPOCH))
                if [ "$AGE" -gt "$STALE_THRESHOLD" ]; then
                    HOURS=$((AGE / 3600))
                    ANOMALIES+="backup_stale[${HOST_TAG}:${plan}:${HOURS}h] "
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

# ── aro-wake health (trio plan §3 — push-trigger service per host) ───────
#
# aro-wake is the push-trigger entry point: Alertmanager webhook + peer
# consult land here. If it's down, peers can't reach us and Alertmanager
# rules fall through to telegram_configs (the existing fallback). Both
# safe; both visible to operator. But we want to know.
#
# Source of SYSADMIN_HOST_IP: aro-wake binds the host's wg0 mesh IP
# (10.99.0.<N>), NOT loopback. Cron runs as root with a minimal env, so
# the systemd Environment= we set on vps-sysadmin-bot.service doesn't
# propagate here. Load .env.sysadmin (created by bootstrap step_14)
# directly. On dev WSL or pre-step_14 hosts the file is absent — we
# fall back to deriving the wg0 IP from `wg show` so the check still
# works pre-bootstrap; only if BOTH fail do we default to 127.0.0.1
# (which will mis-flag aro-wake as down, but that's a true positive
# since aro-wake isn't enabled in that case).
if [ -r /opt/fabrik/.env.sysadmin ]; then
    # shellcheck disable=SC1091
    set -a; . /opt/fabrik/.env.sysadmin 2>/dev/null; set +a
fi
ARO_WAKE_HOST="${SYSADMIN_HOST_IP:-}"
if [ -z "${ARO_WAKE_HOST}" ]; then
    # Derive the wg0 IP from `ip addr` — works on pre-bootstrap hosts that
    # don't have /opt/fabrik/.env.sysadmin yet. Returns empty on dev WSL
    # (no wg0 interface); we then fall through to 127.0.0.1.
    ARO_WAKE_HOST=$(ip -4 -o addr show wg0 2>/dev/null \
        | awk '{print $4}' | cut -d/ -f1 | head -1)
fi
ARO_WAKE_HOST="${ARO_WAKE_HOST:-127.0.0.1}"
if systemctl is-enabled --quiet aro-wake.service 2>/dev/null; then
    if ! curl -sf --max-time 5 "http://${ARO_WAKE_HOST}:8201/health" >/dev/null 2>&1; then
        ANOMALIES+="aro_wake_unhealthy[${ARO_WAKE_HOST}] "
    fi
fi

# ── OAuth keepalive heartbeat (trio plan §2.5 + Lesson 75) ────────────────
#
# /etc/cron.d/vps-sysadmin runs claude-keepalive-rotate.sh once per hour to probe this
# host's Claude auth/quota health and write a CONTENT token (KEEPALIVE_OK /
# KEEPALIVE_FAIL:<reason>) to the log. Since 2026-08-30 it is a HEALTH probe only — a free
# `claude_rotate.py --probe-current --json` metadata GET; the `claude -p ping` that used to
# also keep the token warm was retired (it burned the quota the governor conserves), so this
# watcher no longer implies token freshness. Two failure modes, both escalated: (a) mtime >
# 90 min → the cron itself is dead; (b) a fresh mtime but a FAIL/401/usage-limit token → the
# probe runs but auth/quota is broken (the mtime-only check reported "fresh" straight through
# a month-long 401 outage — the bug this fixes).
KEEPALIVE_LOG=/var/log/claude-keepalive.log
if [ ! -e "$KEEPALIVE_LOG" ]; then
    # File doesn't exist yet — first-boot or cron never fired. Allow 2h grace.
    if [ -e /etc/cron.d/vps-sysadmin ] && [ "$(stat -c %Y /etc/cron.d/vps-sysadmin 2>/dev/null)" -lt "$(($(date +%s) - 7200))" ]; then
        ANOMALIES+="oauth_keepalive_never_ran "
    fi
else
    KEEPALIVE_AGE=$(( $(date +%s) - $(stat -c %Y "$KEEPALIVE_LOG") ))
    if [ "$KEEPALIVE_AGE" -gt 5400 ]; then  # 90 minutes → cron dead
        ANOMALIES+="oauth_keepalive_stale[${KEEPALIVE_AGE}s] "
    fi
    # CONTENT check — a fresh mtime does NOT mean healthy; parse the keepalive token.
    _ka_reason=""
    if [ -f "$(dirname "$0")/keepalive-status.sh" ]; then
        # shellcheck source=scripts/sysadmin/keepalive-status.sh
        . "$(dirname "$0")/keepalive-status.sh"
        _ka_reason="$(keepalive_reason "$KEEPALIVE_LOG")"
    else
        # Fail-CLOSED: without the classifier we're blind to a real auth/quota break (the very
        # bug this check fixes), so a broken/partial deploy must page, not silently pass.
        ANOMALIES+="oauth_keepalive_classifier_missing "
    fi
    [ -n "$_ka_reason" ] && ANOMALIES+="oauth_keepalive_broken[${_ka_reason}] "
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

# ── Authelia + GlitchTip health (auth-free, hub-only) ────────────────────
#
# Both services are deployed only on the hub (vps1) — spokes have neither
# Authelia nor GlitchTip in the current fleet shape. We probe via apprise,
# the only container on the fabrik docker network that ships curl.
# (sysadmin-bot is a systemd unit, not a container; promtail uses
# network_mode: host and has no curl — both are unsuitable as probes.)
# Auth-free endpoints:
#   - Authelia: GET http://authelia:9091/api/health → {"status":"OK"}
#   - GlitchTip: GET http://glitchtip-web:8000/_health/ → "ok"
# A 5xx / connection refusal = service down; that's Tier B (auth/error
# pipeline degraded) — wake Claude to investigate. On spokes the whole
# block is a no-op (neither `authelia` nor `glitchtip-web` container exists,
# so the inner blocks short-circuit and no probe container is needed).

if command -v docker >/dev/null 2>&1; then
    HAS_AUTHELIA=0
    HAS_GLITCHTIP=0
    sudo docker ps --format '{{.Names}}' | grep -q '^authelia$' && HAS_AUTHELIA=1
    sudo docker ps --format '{{.Names}}' | grep -q '^glitchtip-web$' && HAS_GLITCHTIP=1

    if [ "$HAS_AUTHELIA" = "1" ] || [ "$HAS_GLITCHTIP" = "1" ]; then
        # Pick a probe container with curl on the fabrik network. Today that's
        # apprise; the loop leaves room for future additions without code change.
        NET_PROBE_CONTAINER=""
        for cand in apprise; do
            if sudo docker inspect "$cand" --format '{{.State.Status}}' 2>/dev/null | grep -q running; then
                NET_PROBE_CONTAINER="$cand"; break
            fi
        done

        if [ -z "$NET_PROBE_CONTAINER" ]; then
            # We have services that need probing but no working probe container.
            # That's itself an anomaly — don't silently skip monitoring.
            ANOMALIES+="health_probe_container_missing "
        else
            if [ "$HAS_AUTHELIA" = "1" ]; then
                if ! sudo docker exec "$NET_PROBE_CONTAINER" curl -sf --max-time 5 \
                     http://authelia:9091/api/health 2>/dev/null | grep -q '"status":"OK"'; then
                    ANOMALIES+="authelia_health_failed "
                fi
            fi
            if [ "$HAS_GLITCHTIP" = "1" ]; then
                if ! sudo docker exec "$NET_PROBE_CONTAINER" curl -sf --max-time 5 \
                     http://glitchtip-web:8000/_health/ 2>/dev/null | grep -q '^ok'; then
                    ANOMALIES+="glitchtip_health_failed "
                fi
                # glitchtip-worker is the error-queue processor; if it's stopped,
                # errors pile up but never reach Telegram.
                if ! sudo docker inspect glitchtip-worker --format '{{.State.Status}}' 2>/dev/null | grep -q running; then
                    ANOMALIES+="glitchtip_worker_not_running "
                fi
            fi
        fi
    fi
fi

# ── Unbounded containers (the memory-limit invariant, off the apply path) ──
# `deploy.resources.limits.memory` is mandatory on every service — enforced by
# deployer_ssh._validate_compose() and auto-emitted by the scaffolder, but ONLY for
# containers that pass through `fabrik apply`. The hand-composed monitoring/ingress
# stack never does, so nothing was watching it: measured 2026-09-04, TEN of vps1's 32
# containers ran with no ceiling at all, some since 2026-07-08. An unbounded container
# that runs away takes an arbitrary subset of the box with it instead of only itself.
#
# `docker ps -aq`, not `-q`: a stopped-but-defined container keeps HostConfig.Memory
# across a restart, so reading only the RUNNING set reports green while an unbounded
# container sits waiting to start. Today both counts are equal, which is exactly why
# the narrower query would have been easy to write and never notice.
#
# Fire rate, measured before shipping: 10/32 before the ceilings were applied, 0/32
# after. It fires only on a genuine regression — a container arriving off the apply
# path — which is signal, not wallpaper.
#
# Ceilings + derivation: docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md
# Applier:               scripts/vps_apply_limits.sh --apply   (--check for this same verdict)
if command -v docker >/dev/null 2>&1; then
    # A DEAD daemon must not read as a clean bill of health. `docker ps -aq` on an unreachable
    # daemon returns empty and exits nonzero — identical output to "no containers" — so an
    # unguarded loop reports GREEN on a host whose Docker is gone. Nothing else in this file
    # detects that (every other docker call here treats failure as "feature absent"), so the
    # blind spot would be real: this check's silence is meant to MEAN something.
    if ! _ids=$(sudo docker ps -aq 2>/dev/null); then
        ANOMALIES+="docker_daemon_unreachable[$(hostname -s)] "
        _ids=""
    fi
    _unbounded=""
    for _cid in $_ids; do
        if [ "$(sudo docker inspect -f '{{.HostConfig.Memory}}' "$_cid" 2>/dev/null)" = "0" ]; then
            _n=$(sudo docker inspect -f '{{.Name}}' "$_cid" 2>/dev/null)
            _unbounded="${_unbounded}${_n#/},"
        fi
    done
    [ -n "$_unbounded" ] \
      && ANOMALIES+="container_no_memory_limit[$(hostname -s):${_unbounded%,}] "
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
  # New hour — reset counter ON DISK too. The increment moved after the claude call (audit
  # 2026-08-30), so a shed first-run of a new hour would otherwise exit before ever writing
  # .count — leaving LAST hour's count live and falsely rate-limiting the whole new hour
  # (native-review finding 1, reproduced by simulation).
  echo "$CURRENT_HOUR" > "${RATE_FILE}.hour"
  echo 0 > "${RATE_FILE}.count"
  RATE_COUNT=0
fi

if [ "$RATE_COUNT" -ge "$RATE_LIMIT" ]; then
  echo "Rate limited ($RATE_COUNT/$RATE_LIMIT this hour). Skipping Claude."
  exit 0
fi
# NOTE: the counter increments AFTER the claude call, and only when the governor did NOT shed
# (a shed run wakes nothing — pre-incrementing let 5 sheds exhaust the hourly wake budget with
# zero analyses; found in the 2026-08-30 way-of-working audit).

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

RESULT=$("$PROJECT_DIR/scripts/sysadmin/claude-run.sh" -p --model "${CLAUDE_SYSADMIN_MODEL:-opus}" \
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

GOV_RC=$?  # exit status of the claude-run.sh call above (75 = governor quota-conservation shed)
if [ "$GOV_RC" -eq 75 ]; then exit 0; fi  # routine shed — skip this best-effort run silently, no false alarm
# A REAL wake happened (claude ran, successfully or not) — consume one of the hourly wake slots.
echo $((RATE_COUNT + 1)) > "${RATE_FILE}.count"
if [ -z "$RESULT" ]; then
  # Empty result = Claude FAILED to analyze (auth/quota/timeout/crash), NOT a benign verdict.
  # Fail CLOSED: do not treat unreviewed anomalies as all-clear — escalate so a real problem
  # isn't silently swallowed behind a claude failure.
  if APPRISE_SEND "⚠️ Proactive Check [$(hostname -s)] — Claude analysis FAILED" "Anomalies were detected but Claude returned NO analysis (auth/quota/timeout?). Review manually. Anomalies: ${ANOMALIES:-unknown}"; then
    echo "Claude analysis failed (empty result) — escalated unreviewed anomalies."
  else
    echo "Claude analysis failed AND the escalation alert could NOT be delivered — check Apprise/fabrik network."
  fi
  exit 1
fi
if [ "$RESULT" = "ALL_CLEAR" ]; then
  echo "Claude says all clear despite triggers. Likely benign."
  exit 0
fi

# Send to Telegram via Apprise (inside Docker network). Gate the success line on actual
# delivery — an unconditional "Sent" after a failed APPRISE_SEND is a self-contradictory log
# and hides a dropped alert (Claude found a real issue but the operator never heard).
if APPRISE_SEND "🔍 Proactive Check [$(hostname -s)]" "$RESULT"; then
  echo "Sent proactive alert to Telegram."
else
  echo "Proactive alert FAILED to send (see APPRISE_SEND FAILED above)."
  exit 1
fi
