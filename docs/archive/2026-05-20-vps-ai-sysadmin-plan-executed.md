# VPS AI System Administrator — Plan

**Status:** Planned
**Created:** 2026-05-20
**Replaces:** `old-draft-aro-brain-plan-v3.md`

---

## Core Design

Claude Code is installed on the VPS (`/usr/local/bin/claude`, v2.1.144). It runs locally — direct access to Docker, files, Prometheus, Loki, everything. It reads CLAUDE.md for rules. It's already the AI SRE. We just need triggers and a communication channel.

**On-demand, not persistent.** Claude Code is dormant 99% of the time. Zero tokens unless triggered. A session starts when you message, ends when you say "done" or after 10 minutes of silence.

```
You message → bot spawns claude --session-id {uuid}
Claude responds
You follow up → same session
You: "done" (or 10min silence) → bot kills process → dormant
... zero cost ...
New message → new session
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  VPS (all local, no SSH, no external LLM API)                │
│                                                              │
│  PATH 1: You initiate                                        │
│  ┌──────────┐  message  ┌───────────────────────────────┐   │
│  │ Telegram  │─────────▶│  sysadmin-bot.py (systemd)    │   │
│  │ (phone)   │◀─────────│  spawns claude on demand      │   │
│  └──────────┘  response │  kills after "done" / timeout │   │
│                          └──────────────┬────────────────┘   │
│                                         │                     │
│  PATH 2: Alert fires                    │                     │
│  ┌──────────────┐  already   ┌─────────▼─────────┐          │
│  │ Alertmanager │──works────▶│ Apprise→Telegram   │          │
│  │              │            │ (you see alert)    │          │
│  └──────────────┘            └───────────────────┘          │
│  You decide to investigate → message bot (Path 1)            │
│                                                              │
│  PATH 3: Proactive cron (every 15 min)                       │
│  ┌───────────────────────────────────────────┐               │
│  │  proactive-check.sh (bash, zero tokens)   │               │
│  │                                            │               │
│  │  Stage 1: curl Prometheus for thresholds   │               │
│  │  - memory rising >5MB/min?                 │               │
│  │  - container restarted?                    │               │
│  │  - CPU >70% sustained?                     │               │
│  │  - disk >75%?                              │               │
│  │  - host RAM >80%?                          │               │
│  │  - load >5 (6 cores)?                      │               │
│  │                                            │               │
│  │  All clear? → exit 0, silent, zero cost    │               │
│  │                                            │               │
│  │  Anomaly? → Stage 2:                       │               │
│  │    claude -p "analyze this" < context.txt  │               │
│  │    → send to Telegram via Apprise          │               │
│  │    → session ends immediately              │               │
│  └───────────────────────────────────────────┘               │
│                                                              │
│  Claude Code runs LOCALLY when triggered:                    │
│  - reads /opt/fabrik/CLAUDE.md (rules)                       │
│  - runs sudo docker stats/logs/restart/inspect               │
│  - runs sudo bash scripts/audit/*.sh                         │
│  - curls Prometheus, Loki, Gatus, GlitchTip APIs            │
│  - reads docs/infrastructure/*.md                            │
│  - Max subscription (no API key cost)                        │
└─────────────────────────────────────────────────────────────┘
```

## Three Trigger Paths

### Path 1: Conversational — You Message the Bot

You send a Telegram message. Bot spawns Claude Code. Claude runs commands, analyzes, responds. You can follow up in the same session. Say "done" or go silent for 10 min → session ends.

```
You:  status
Claude:  36 containers, all healthy. 31GB disk (29%), 7.1GB RAM free.
         No alerts in 24h.

You:  what's eating memory?
Claude:  (runs docker stats --no-stream locally)
         Top 5: postgres-main 130MB, grafana 93MB, loki 81MB...

You:  restart image-broker
Claude:  (runs docker restart image-broker-... locally)
         Restarted. Container healthy after 6s.

You:  done
Bot:  Session ended. ✅
```

### Path 2: Reactive — Alert Fires, You Investigate

Alertmanager → Apprise → Telegram (already working, unchanged). You see the alert on your phone. You decide whether to investigate:

```
Alert on Telegram:
  🔥 ContainerHighMemory: glitchtip-web at 89%

You:  analyze the glitchtip memory issue

Claude:  glitchtip-web at 456MB / 512MB limit (89%).
         Logs: no errors, normal event ingestion.
         Memory grew steadily over 4 weeks (no restart since May 19).
         This is expected Django behavior — processes accumulate.

         Recommendation: restart glitchtip-web (safe, <10s downtime).
         Shall I?

You:  do it

Claude:  ✅ Restarted. Now at 89MB (17% of limit).
         Will check again at next proactive scan (15 min).

You:  done
```

### Path 3: Proactive Cron — Zero Tokens When Healthy

Every 15 minutes, a bash script checks Prometheus thresholds. Pure `curl` + `jq` — no Claude, no tokens.

**Stage 1 (bash, every 15 min, zero cost):**

```bash
# PromQL threshold checks — curl Prometheus directly
CHECKS=(
  'deriv(container_memory_usage_bytes{name!=""}[1h]) > 5e6'          # memory rising
  'increase(container_restart_count{name!=""}[15m]) > 0'             # restart
  'rate(container_cpu_usage_seconds_total{name!=""}[15m]) * 100 > 70' # CPU >70%
  '(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) > 0.75'  # disk >75%
  '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.80'  # RAM >80%
  'node_load5 > 5'                                                    # load >5
)
```

All clear (95% of the time) → exit silently. Zero tokens. Zero cost.

**Stage 2 (Claude, only when anomaly detected):**

Pre-filter triggered → collect context (metrics + logs for affected containers) → `claude -p "Analyze this anomaly. Report concisely for Telegram."` → send to Telegram → session ends immediately (fire-and-forget, no conversation).

If you want to investigate further, message the bot. You don't need to copy-paste — just say "tell me more about the proactive alert" and Claude will re-query the live state.

**Rate limit:** Max 5 Claude wake-ups per hour from proactive checks. If threshold exceeded, send a single "multiple anomalies detected, investigate manually" message via Apprise directly (no Claude).

## Container Classification

Carried from ARO plan. Claude must respect these categories when deciding what to act on.

| Category | Containers | What Claude can do |
|----------|-----------|-------------------|
| **critical-infra** | coolify, traefik, postgres-main, redis-main, coolify-db, coolify-redis, coolify-realtime, coolify-sentinel | Read-only. Diagnose + notify. NEVER restart/stop/scale. |
| **monitoring** | prometheus, grafana, loki, promtail, alertmanager, cadvisor, node-exporter, netdata, gatus, pushgateway, exporters | Read-only. Diagnose + notify. Touching these blinds Claude. |
| **platform** | authelia, apprise, backrest, n8n, glitchtip-web, glitchtip-worker, meilisearch, gotenberg, browserless | Diagnose + notify. Restart ONLY with owner approval ("shall I?"). |
| **application** | image-broker, site-provisioner, ocoron-com-*, any future fabrik-deployed service | Full management per operating mode. |

## Operating Modes

Default: **autonomous**. Acts first, reports after. Asks only when genuinely unsure or when action is in the "ask first" category.

| Action | Autonomous | Ask first | NEVER |
|--------|-----------|-----------|-------|
| Restart application container | ✅ act + report | | |
| Restart platform container | ✅ act + report | | |
| Scale memory UP (capped at 4GB) | ✅ act + report | | |
| Scale memory DOWN | | ✅ | |
| Stop a misbehaving container | | ✅ | |
| Notify via Telegram | ✅ always | | |
| Delete container/volume/data | | | ❌ |
| Modify environment variables | | | ❌ |
| Change network/firewall/boot config | | | ❌ |
| Touch Docker daemon or fstab | | | ❌ |
| Manage the sysadmin bot itself | | | ❌ |

Claude acts autonomously on routine operations (restart, scale up, diagnose) and reports what it did. Only asks for stop/scale-down/anything destructive-adjacent.

## Notification Templates

Adopted from ARO plan. Claude should format Telegram messages like this:

**When Claude takes action:**
```
🤖 Action Taken

📦 Container: glitchtip-web
⚠️ Trigger: ContainerHighMemory (89%)
🔍 Root cause: Django process accumulation over 4 weeks, no restart
✅ Action: Restarted container
📊 Result: Memory 456MB → 89MB

Next check in 15 min.
```

**When Claude would act but safe mode prevents it:**
```
🤖 Action Blocked (Safe Mode)

📦 Container: n8n
⚠️ Issue: Memory at 412MB with no limit set
🔍 Assessment: Large JSON workflow accumulating in memory
🚫 Would do: Set memory limit to 512MB
💡 Say "do it" to approve, or "switch to auto" for future auto-handling.
```

**Proactive scan — issue found:**
```
🔍 Proactive Check

📈 Disk trending: 29% → predicted 45% in 7 days
📦 Top consumers: overlay2 28GB, Netdata cache 2.3GB
💡 Netdata cache exceeds DBENGINE_DISK_SPACE_MB=512 setting
🔕 No action taken — informational only.
```

## What Claude Code Has Access To (locally)

| Capability | How |
|---|---|
| Docker commands | `sudo docker ps/stats/logs/restart/update/inspect` |
| Prometheus metrics | `curl http://prometheus:9090/api/v1/query` |
| Loki logs | `curl http://loki:3100/loki/api/v1/query_range` |
| Gatus uptime | `curl http://gatus:8080/api/v1/endpoints/statuses` |
| GlitchTip errors | `curl http://glitchtip-web:8000/api/0/...` |
| System state | `/proc/meminfo`, `df`, `vmstat`, `ps` — all local |
| Fabrik commands | `fabrik audit-registrars`, `fabrik verify` |
| Audit scripts | `sudo bash scripts/audit/*.sh` |
| All docs | `docs/infrastructure/*.md` (inventory, audit prompts, hardening) |
| Rules | CLAUDE.md |

## What Needs Building

### 1. Telegram Bot — `scripts/sysadmin/bot.py` (~150 lines)

**Session lifecycle — each message is a separate `claude -p` call but within the same session:**

```
Message 1: "status"
  → claude -p "status" --session-id {new_uuid} --system-prompt "{sysadmin_role}"
  → response sent to Telegram
  → session_id saved, last_activity = now

Message 2: "restart image-broker" (within 10 min)
  → claude -p "restart image-broker" --resume {same_uuid}
  → Claude has context from message 1
  → response sent to Telegram
  → last_activity = now

Message 3: "done" (or 10 min silence)
  → session_id cleared
  → "Session ended. ✅" sent to Telegram

Message 4: "check disk" (new conversation)
  → claude -p "check disk" --session-id {new_uuid} --system-prompt "{sysadmin_role}"
  → fresh session, no history from previous conversation
```

**Key design choices:**

- `claude -p` (print mode) — not interactive. Each message is a subprocess call. No PTY needed, no stdin pipe complexity.
- `--resume {session-id}` — follow-up messages resume the same session. Claude remembers context.
- `--system-prompt` — injects the sysadmin role per-session. Keeps CLAUDE.md clean for development use (the VPS copy of fabrik is a deployment target, not a dev workspace).
- `--permission-mode bypassPermissions` — Claude runs `docker restart` etc. without asking for tool permission (you already approved via Telegram).
- One session at a time — if you message while a previous `claude -p` is still running, bot queues it.

**Implementation:**

- `python-telegram-bot` library (async, long-polling)
- No public URL needed (long-polling from inside VPS)
- Owner-only: rejects all non-`TELEGRAM_OWNER_ID` messages silently
- Message splitting: Telegram max 4096 chars → split into chunks if needed
- Timeout: 10 min idle → session cleared
- Subprocess timeout: 120s per `claude -p` call → if exceeded, kill + notify "timed out"

### 2. Proactive Check — `scripts/sysadmin/proactive-check.sh` (~80 lines)

Two-stage bash script. Stage 1 curls Prometheus with PromQL, zero tokens. Stage 2 wakes Claude only if anomaly detected.

```bash
# Stage 1: PromQL threshold checks (free)
ANOMALIES=""
for check in "${CHECKS[@]}"; do
  result=$(curl -s "http://prometheus:9090/api/v1/query?query=${check}")
  if echo "$result" | jq -e '.data.result | length > 0' >/dev/null 2>&1; then
    ANOMALIES+="$check\n"
  fi
done

# All clear? Exit silently.
[ -z "$ANOMALIES" ] && exit 0

# Rate limit: max 5 Claude wakes per hour
WAKE_COUNT=$(cat /tmp/sysadmin-wake-count 2>/dev/null || echo 0)
[ "$WAKE_COUNT" -ge 5 ] && echo "rate limited" && exit 0

# Stage 2: Wake Claude (only when anomaly detected)
# Collect context for affected containers
CONTEXT=$(collect_context "$ANOMALIES")
RESULT=$(claude -p "Proactive check found anomalies. Analyze concisely for Telegram. If not serious, say ALL_CLEAR." <<< "$CONTEXT" 2>/dev/null)

[ "$RESULT" = "ALL_CLEAR" ] && exit 0

# Send to Telegram via Apprise
curl -s -X POST "http://apprise:8000/notify/alerts" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"🔍 Proactive Check\",\"body\":\"$RESULT\"}"
```

### 3. System Prompt — `scripts/sysadmin/system-prompt.txt`

Injected via `--system-prompt` flag per session. NOT added to CLAUDE.md (which stays clean for development use on WSL). Stored as a text file the bot reads at startup.

```text
You are the on-demand system administrator for this VPS. You run LOCALLY — direct access to Docker, files, Prometheus, Loki, everything. No SSH needed.

Respond concisely. The owner reads your messages on a phone screen via Telegram.

### What you are
- On-demand system administrator for this VPS
- You run LOCALLY on the VPS — no SSH needed, direct access to everything
- You are spawned per-conversation, not persistent

### What to read first
- docs/infrastructure/vps-complete-inventory.md — current containers and stack
- docs/infrastructure/audit-prompts/*.md — analysis checklists
- scripts/audit/*.sh — diagnostic scripts (run with sudo)

### Container classification
- critical-infra (coolify, traefik, postgres, redis): READ ONLY, never act
- monitoring (prometheus, grafana, loki, etc.): READ ONLY, never act
- platform (authelia, apprise, glitchtip, etc.): ask owner before acting
- application (everything else): act per operating mode

### Safety — NEVER
- Delete containers, volumes, images, or data
- Modify /etc/docker/daemon.json, /etc/fstab, /etc/netplan/, iptables
- Stop or restart critical-infra or monitoring containers
- Run docker system prune, docker volume prune
- Execute anything that could break SSH or prevent boot

### Safety — SAFE without asking
- docker restart on application containers
- docker update --memory to INCREASE limits (never decrease)
- docker logs, docker stats, docker inspect
- Read any file, run any audit script
- Query Prometheus, Loki, Gatus (read-only)

### Safety — ASK FIRST
- Restart platform containers
- Scale memory down
- Stop any container
- Anything you're unsure about

### Communication style
- Concise, technical, actionable
- Use notification templates (see plan doc)
- When taking action: state what, why, result
- When blocked: state what you would do and why you can't
```

### 4. Systemd Service — `ops/vps-sysadmin-bot.service`

```ini
[Unit]
Description=VPS AI Sysadmin Telegram Bot
After=network.target docker.service

[Service]
Type=simple
User=ozgur
WorkingDirectory=/opt/fabrik
ExecStart=/usr/bin/python3 /opt/fabrik/scripts/sysadmin/bot.py
Restart=always
RestartSec=30
Environment=TELEGRAM_BOT_TOKEN=...
Environment=TELEGRAM_OWNER_ID=...
StandardOutput=append:/var/log/vps-sysadmin-bot.log
StandardError=append:/var/log/vps-sysadmin-bot.log

[Install]
WantedBy=multi-user.target
```

### 5. Cron Entry

```cron
*/15 * * * * root /opt/fabrik/scripts/sysadmin/proactive-check.sh >> /var/log/sysadmin-proactive.log 2>&1
```

## Environment Variables

```env
TELEGRAM_BOT_TOKEN=           # from @BotFather
TELEGRAM_OWNER_ID=            # your numeric Telegram user ID
# Claude Code auth: already done via `claude auth login` (Max subscription)
```

## Token Economics

| Scenario | Claude wakes? | Token cost |
|----------|--------------|------------|
| Quiet day, no messages, proactive all-clear | No | $0 |
| Proactive detects anomaly (1-2x per day typical) | Yes, fire-and-forget `-p` | ~$0.01-0.05 per call |
| You message "status" | Yes, session until "done" | ~$0.02-0.10 per conversation |
| You investigate an alert (multi-turn) | Yes, session until "done" | ~$0.05-0.20 per conversation |
| Full audit on demand ("run full security audit") | Yes, long session | ~$0.20-0.50 |
| **Monthly estimate (typical)** | | **$5-15** (included in Max subscription) |

## Deployment Steps

1. Create Telegram bot via @BotFather, get token
2. Get your Telegram user ID (message @userinfobot)
3. `mkdir -p /opt/fabrik/scripts/sysadmin/`
4. Deploy `bot.py` + `proactive-check.sh`
5. Install systemd service for bot
6. Install cron for proactive checks
7. Add sysadmin section to CLAUDE.md
8. Test: send "status" on Telegram → verify response
9. Test: send "run security audit" → verify full audit runs
10. Test: let proactive check run for 1 hour → verify silence on clean system
11. Test: artificially spike a container's memory → verify proactive detects and notifies

## Build Estimate

| Component | Effort |
|---|---|
| bot.py (Telegram + session management) | 3 hours |
| proactive-check.sh (two-stage) | 1 hour |
| CLAUDE.md sysadmin section | 30 min |
| Systemd + cron | 30 min |
| End-to-end testing | 2 hours |
| **Total** | **~7 hours** |

## What We Did NOT Build (vs old ARO Brain)

| Old component | Why not needed |
|---|---|
| Custom FastAPI service (1176 lines planned) | Claude Code IS the service |
| LLM provider abstraction (Kilo, OpenAI, Ollama) | Max subscription via claude.ai |
| Model router (4 tiers) | One model, no routing |
| Service registry + auto-discovery | `docker ps` directly |
| Context builder | Claude reads metrics/logs directly |
| Action executor + validator | CLAUDE.md rules + Claude's judgment |
| Health endpoint + self-monitoring | Gatus monitors systemd service |
| Docker Compose + Dockerfile | No container — host process |
| Session management server | Bot manages session lifecycle |
| JSONL action log | Claude's conversation history |
| 46 hours across 5 phases | 7 hours, one phase |

## Future Enhancements (v2, not needed now)

- **Morning summary:** Cron at 08:00 runs full audit, Claude sends daily report
- **Weekly security audit:** Monday cron runs 03-security.sh
- **Auto-restart on OOM:** Proactive script detects OOM → wakes Claude → auto-restart (safe mode approved)
- **Slash commands:** `/audit`, `/security`, `/backup`, `/performance` for on-demand targeted audits
- **Multi-VPS:** Same bot, Claude uses SSH to reach other VPS instances
- **Claude Code Channels:** When the Telegram channel plugin stabilizes, replace custom bot with native `claude --channels plugin:telegram@claude-plugins-official`
- **Scheduled Tasks:** Replace proactive cron with Claude Code's built-in scheduled tasks feature
