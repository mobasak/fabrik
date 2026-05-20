# ARO Brain — Project Plan v2

**Project:** Autonomous Resource Orchestrator (ARO Brain)
**Type:** `python-api` (Fabrik scaffold)
**Port:** 8017 (registered in PORTS.md)
**Repo:** `projects/aro-brain/`
**VPS URL:** `http://aro-brain:8017` (internal only — no public domain)
**Deploy:** Coolify, Docker Compose, `coolify` network

---

## 1. What ARO Brain Is

An AI-powered autonomous infrastructure manager. Deploys as a single container alongside any Docker/Coolify stack. Auto-discovers all running services, continuously monitors metrics and logs, reasons about problems using LLMs, takes safe autonomous actions, and notifies the operator via Telegram.

**One sentence:** "A tireless AI SRE that watches your VPS, understands what's wrong, fixes what it can, tells you about the rest — and you can talk to it over Telegram."

---

## 2. Why It Exists

| Problem | Current state | ARO solution |
|---------|---------------|--------------|
| Services crash at 3 AM | Nobody watching → OOM cascades | AI detects, reasons, restarts/scales within seconds |
| Memory leaks go unnoticed | Manual `docker stats` checks | Proactive trend detection every 15 min |
| Disk fills up silently | Alert fires, you read it hours later | AI acts immediately — identifies what's consuming space, notifies with specifics |
| New projects deployed, nobody updates monitoring | Monitoring config drift | Auto-discovery — new containers monitored automatically |
| Alert fatigue | Prometheus alerts spam Telegram | AI filters noise, only notifies on actionable events with reasoning |
| Idle services waste RAM | Manual pause/restart | Scheduler pauses idle services at night, wakes on demand |
| Can't act on alerts when away from laptop | SSH into VPS from phone is painful | Reply to ARO on Telegram: "restart it", "check the logs", "scale to 2G" |

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        VPS (coolify network)                │
│                                                             │
│  ┌─────────────┐   webhook    ┌──────────────────────────┐  │
│  │ Alertmanager │────────────▶│      ARO Brain :8017     │  │
│  │   :9093      │             │                          │  │
│  └─────────────┘             │  ┌──────────────────────┐ │  │
│                              │  │   Context Builder    │ │  │
│  ┌─────────────┐  PromQL     │  │ Prometheus + Loki +  │ │  │
│  │ Prometheus  │◀────────────│  │ Docker + Coolify API │ │  │
│  │   :9090     │             │  └──────────┬───────────┘ │  │
│  └─────────────┘             │             │             │  │
│                              │             ▼             │  │
│  ┌─────────────┐  LogQL      │  ┌──────────────────────┐ │  │
│  │    Loki     │◀────────────│  │   LLM Reasoner      │ │  │
│  │   :3100     │             │  │  Kilo Direct API ──────────▶ api.kilo.ai
│  └─────────────┘             │  └──────────┬───────────┘ │  │
│                              │             │             │  │
│  ┌─────────────┐  REST       │  ┌──────────────────────┐ │  │
│  │ Coolify API │◀────────────│  │  Action Executor     │ │  │
│  │   :8000     │             │  │ (built-in validation)│ │  │
│  └─────────────┘             │  └──────────┬───────────┘ │  │
│                              │             │             │  │
│  ┌─────────────┐  notify     │  ┌──────────────────────┐ │  │
│  │   Apprise   │◀────────────│  │  Notifier            │ │  │
│  │   :8000     │             │  │ + Action Log (JSONL) │ │  │
│  └─────────────┘             │  └──────────────────────┘ │  │
│                              │             ▲             │  │
│                              │             │ directives  │  │
│  ┌─────────────┐ long-poll   │  ┌──────────────────────┐ │  │
│  │  Telegram   │◀───────────▶│  │  Telegram Chat Bot   │ │  │
│  │  Bot API    │             │  │ 2-way conversation   │ │  │
│  └─────────────┘             │  └──────────────────────┘ │  │
│                              └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Four Operating Loops

| Loop | Trigger | Frequency | Purpose |
|------|---------|-----------|---------|
| **Reactive** | Alertmanager webhook to `/api/alerts` | On alert fire | Immediate response to critical events |
| **Proactive** | Internal cron (APScheduler) | Every 15 min | Two-stage: rule-based pre-filter (free) → LLM reasoning (only if anomaly detected) |
| **Scheduler** | Internal cron (APScheduler) | Hourly + daily | Pause idle services, wake on demand, resource optimization |
| **Conversational** | Telegram Bot API (long-polling) | On your message | Two-way chat — give directives, ask questions, approve/reject actions |

### Two Operating Modes

Controlled by env var `ARO_MODE=safe|auto` (default: `safe`).

| Action | safe | auto | Never |
|--------|------|------|-------|
| Restart container | ✅ | ✅ | |
| Scale memory/CPU **up** (capped at host limit) | ✅ | ✅ | |
| Scale memory/CPU **down** | ❌ | ✅ | |
| Wake a paused service | ✅ | ✅ | |
| Pause idle service (stop, not delete) | ❌ | ✅ | |
| Stop a misbehaving service | ❌ | ✅ | |
| Notify via Apprise/Telegram | ✅ always | ✅ always | |
| Silence/inhibit noisy alerts | ❌ | ✅ | |
| Delete container/volume/data | | | ❌ |
| Modify environment variables | | | ❌ |
| Change network configuration | | | ❌ |
| Touch persistent volumes/data | | | ❌ |
| Manage ARO itself | | | ❌ |

In safe mode, blocked actions generate a Telegram notification: _"I would have done X because Y, but safe mode prevented it. Switch to auto if you want me to handle this."_

---

## 4. Service Registry (Auto-Discovery)

ARO auto-discovers and classifies all containers. No manual configuration needed.

### Discovery Sources (merged every 5 min)

| Source | What it provides |
|--------|-----------------|
| Coolify API `GET /applications` | App UUIDs, names, status, resource limits, deploy config |
| Docker socket `/var/run/docker.sock` | ALL containers including non-Coolify (monitoring, Authelia) |
| Prometheus `up` metric | Which targets are being scraped + their health |

### Container Classification

Classification uses a priority chain: explicit Docker label → name pattern match → default to `application`.

**Priority 1: Docker labels (commercial-ready, works for any customer)**
```yaml
# Customer adds to their compose.yaml:
labels:
  - "aro.category=critical-infra"    # or: monitoring, platform, application, ignore
  - "aro.ignore=true"               # completely invisible to ARO
```

**Priority 2: Name pattern matching (works out of the box, no label required)**

| Category | Name patterns | ARO behavior | Your examples |
|----------|--------------|--------------|---------------|
| **critical-infra** | `coolify`, `traefik`, `postgres*`, `redis*`, `mysql*`, `mariadb*` | Monitor + notify only. **Never** restart/stop/scale. | `coolify`, `traefik`, `postgres-main`, `redis` |
| **monitoring** | `prometheus`, `grafana`, `loki`, `alertmanager`, `cadvisor`, `node-exporter`, `promtail`, `netdata`, `aro-brain` | Monitor + notify only. Touching these blinds ARO. | All your monitoring stack |
| **platform** | `authelia`, `apprise`, `n8n`, `uptime*`, `duplicati`, `gotenberg`, `meilisearch`, `browserless` | Monitor + notify. Restart only on critical. | `authelia`, `apprise`, `n8n`, `uptime-kuma`, `duplicati` |
| **application** | Everything else managed by Coolify | Full management per operating mode. | All Fabrik microservices, WordPress sites, future projects |
| **unknown** | New container not matching any pattern | Telegram: "New container detected: X" → auto-classified as `application` after 24h if no response. | Anything new |

**Priority 3: Manual override via Telegram**
```
You:  classify gotenberg as ignore
ARO:  ✅ gotenberg classified as ignore. I'll stop monitoring it.
```

Manual classifications persist in `/data/aro/registry.json` and survive restarts.

### Registry Data Model

```python
@dataclass
class ManagedService:
    container_name: str
    coolify_uuid: str | None        # None if not Coolify-managed
    category: str                   # critical-infra | monitoring | platform | application
    current_limits: ResourceLimits  # memory, cpu from Docker inspect
    last_metrics: MetricsSnapshot   # latest Prometheus values
    last_action: ActionRecord | None
    first_seen: datetime
    idle_since: datetime | None     # for scheduler — when it last had traffic
```

---

## 5. Context Builder

When an alert fires or the proactive loop runs, the Context Builder assembles a full picture for the LLM. **No artificial limits on context size** — send everything relevant.

### Context Assembly per Alert

```python
context = {
    # The alert itself
    "alert": alert_payload,                    # full Alertmanager webhook body
    
    # Container identity
    "service": registry.get(container_name),   # classification, limits, history
    
    # Metrics (Prometheus PromQL)
    "metrics": {
        "memory_usage_1h": query_range("container_memory_usage_bytes{name='X'}", "1h"),
        "cpu_usage_1h": query_range("rate(container_cpu_usage_seconds_total{name='X'}[5m])", "1h"),
        "restart_count_24h": query("increase(container_restart_count{name='X'}[24h])"),
        "network_rx_tx_1h": query_range("container_network_receive_bytes_total{name='X'}", "1h"),
    },
    
    # Logs (Loki LogQL)
    "recent_logs": query_loki('{container="X"}', limit=100, since="15m"),
    "error_logs": query_loki('{container="X"} |= "error" or "ERROR" or "Exception"', limit=50, since="1h"),
    
    # Host-level context
    "host": {
        "disk_usage": query("node_filesystem_avail_bytes{mountpoint='/'}"),
        "total_memory": query("node_memory_MemTotal_bytes"),
        "available_memory": query("node_memory_MemAvailable_bytes"),
        "load_avg": query("node_load5"),
        "running_containers": len(registry.all_services()),
    },
    
    # ARO's own history
    "recent_actions": action_log.get_recent(container_name, n=10),
    "recent_actions_all": action_log.get_recent(all=True, n=20),
    
    # Operating constraints
    "mode": settings.ARO_MODE,                 # safe | auto
    "allowed_actions": get_allowed_actions(settings.ARO_MODE),
    "forbidden_actions": ALWAYS_FORBIDDEN,
}
```

### Context Assembly for Proactive Scan (Two-Stage)

**Stage 1: Rule-based pre-filter (every 15 min, zero LLM cost)**

Pure Python checks against Prometheus/Loki. No LLM call. This is the 95% case — nothing is wrong.

```python
PREFILTER_CHECKS = {
    # Prometheus — numeric threshold checks
    "memory_rising":    ('deriv(container_memory_usage_bytes{name!=""}[1h]) > 5e6',     "Memory rising >5MB/min"),
    "restart_recent":   ('increase(container_restart_count{name!=""}[15m]) > 0',         "Container restarted"),
    "cpu_sustained":    ('rate(container_cpu_usage_seconds_total{name!=""}[15m]) * 100 > 70', "CPU >70% sustained"),
    "disk_danger":      ('(1 - node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) > 0.75', "Disk >75%"),
    "host_memory":      ('(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.80', "Host RAM >80%"),
    "host_load":        ('node_load5 > 5',                                                "Load avg >5 (6 cores)"),
}

PREFILTER_LOKI = {
    # Loki — error count checks (no LLM needed to count errors)
    "error_spike":      ('{level="error"}', 10, "15m",   ">10 errors in 15 min"),
    "fatal_any":        ('{level="fatal"}', 1,  "15m",   "Any fatal log"),
}

async def proactive_prefilter() -> list[str]:
    """Returns list of triggered check names. Empty = all clear, skip LLM."""
    triggered = []
    for name, (query, desc) in PREFILTER_CHECKS.items():
        result = await prometheus.query(query)
        if result:  # non-empty = something matched
            triggered.append(name)
    for name, (query, threshold, window, desc) in PREFILTER_LOKI.items():
        count = await loki.count(query, window)
        if count >= threshold:
            triggered.append(name)
    return triggered
```

If `proactive_prefilter()` returns empty → log "all clear", no LLM call, cost = $0.

**Stage 2: LLM reasoning (only when stage 1 flags something)**

Only runs when the pre-filter detected at least one anomaly. Now we build the full context for the LLM:

```python
proactive_context = {
    "scan_type": "proactive_15min",
    
    # Trend queries
    "trends": {
        "memory_rising": query('deriv(container_memory_usage_bytes{name!=""}[1h])'),
        "restart_recent": query('increase(container_restart_count{name!=""}[15m]) > 0'),
        "cpu_sustained_high": query('rate(container_cpu_usage_seconds_total{name!=""}[15m]) * 100 > 60'),
        "disk_prediction_24h": query('predict_linear(node_filesystem_avail_bytes{mountpoint="/"}[6h], 24*3600)'),
    },
    
    # Error spikes from logs
    "log_anomalies": {
        "error_counts_by_container": query_loki('sum by (container) (count_over_time({level="error"}[15m]))'),
        "fatal_any": query_loki('{level="fatal"}', limit=10, since="15m"),
    },
    
    # Full service registry snapshot
    "services": registry.snapshot(),
    
    # Host overview
    "host": { ... },  # same as above
    
    "mode": settings.ARO_MODE,
    "allowed_actions": get_allowed_actions(settings.ARO_MODE),
}
```

---

## 6. LLM Reasoner

### LLM Provider Abstraction

ARO needs a provider interface from day 1 — not just for commercial, but because Kilo serve's Docker availability is unconfirmed. The interface supports three backends:

```python
class LLMProvider(Protocol):
    """Interface for LLM calls. Implementations must be async."""
    async def complete(self, messages: list[dict], model: str, max_tokens: int = 2048) -> dict:
        """Returns {"content": str, "usage": {"prompt_tokens": int, "completion_tokens": int}}"""
        ...

class KiloServeProvider(LLMProvider):
    """Kilo serve HTTP API — session-based, unified billing."""
    # Uses POST /session/:id/message
    # Requires: KILO_SERVE_URL, kilo serve running as sidecar or host process
    
class KiloDirectProvider(LLMProvider):
    """Direct Kilo/OpenRouter API — stateless, same billing as Kilo CLI."""
    # Uses POST to Kilo API URL (same as llm_client.py in SEO module)
    # Requires: KILO_API_KEY, KILO_API_URL
    # Fallback if kilo serve is not available

class DirectAPIProvider(LLMProvider):
    """Direct Anthropic/OpenAI API — for commercial customers without Kilo."""
    # Uses POST to api.anthropic.com or api.openai.com
    # Requires: ANTHROPIC_API_KEY or OPENAI_API_KEY
    # For Phase 5 commercial release

class OllamaProvider(LLMProvider):
    """Local Ollama — for customers who want fully self-hosted LLM."""
    # Uses POST to localhost:11434/api/chat
    # Requires: OLLAMA_URL, model pulled locally
    # For Phase 5 commercial release
```

**For your build (Phase 1):** Start with `KiloDirectProvider` — same pattern as your SEO module's `llm_client.py`, proven, no sidecar needed. This removes the Kilo serve Docker image uncertainty entirely.

**If Kilo serve works as a Docker container:** Switch to `KiloServeProvider` for session continuity (useful for Telegram conversations). This is an optimization, not a requirement.

**For commercial:** Add `DirectAPIProvider` and `OllamaProvider`. Customers pick their provider via env var `LLM_PROVIDER=kilo|anthropic|openai|ollama`.

### Kilo Integration (Phase 1 — Direct API)

Uses the same httpx pattern as your SEO module. No sidecar container needed.

```python
class KiloDirectProvider(LLMProvider):
    """Direct Kilo API call — same as llm_client.py in SEO module."""
    
    def __init__(self):
        self.api_key = os.getenv("KILO_API_KEY", "")
        self.api_url = os.getenv("KILO_API_URL", "https://api.kilo.ai/v1/chat/completions")
    
    async def complete(self, messages: list[dict], model: str, max_tokens: int = 2048) -> dict:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.2},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "content": data["choices"][0]["message"]["content"],
                "usage": data.get("usage", {}),
            }
```

### System Prompt (Dynamic Template)

The system prompt is generated at runtime from actual host specs and configuration — not hardcoded. This makes it work for any VPS size and any customer's setup.

```python
def build_system_prompt(host_info: dict, mode: str, registry: ServiceRegistry) -> str:
    return f"""You are ARO Brain — an autonomous infrastructure manager for a Docker/Coolify VPS.

You receive monitoring context (metrics, logs, alerts, service registry) and must decide 
what action to take. You are the sole operator — there is no human watching right now.

## Host specifications
- Total RAM: {host_info['total_memory_gb']:.1f} GB
- CPUs: {host_info['cpu_count']} cores
- Disk: {host_info['disk_total_gb']:.0f} GB total, {host_info['disk_used_percent']:.0f}% used
- Running containers: {registry.count()}
- Operating mode: {mode}

## Your personality
- Conservative by default. When unsure, notify the operator instead of acting.
- Never panic. A single error log is not an emergency. A pattern of errors is.
- Think in root causes, not symptoms. High memory might be a leak (restart) or legitimate load (scale up). Check the logs to tell the difference.
- You are cost-aware. This VPS has {host_info['total_memory_gb']:.1f} GB RAM. Every MB matters.

## Decision format
Respond ONLY with JSON:
{{
  "assessment": "1-2 sentence summary of what you observe",
  "root_cause": "Your best guess at the root cause",
  "confidence": 0.0-1.0,
  "urgency": "critical|high|medium|low|info",
  "actions": [
    {{
      "type": "restart|scale_memory_up|scale_memory_down|scale_cpu_up|scale_cpu_down|pause|wake|stop|notify_only",
      "target": "container_name",
      "params": {{}},
      "reason": "Why this specific action"
    }}
  ],
  "notification": {{
    "send": true,
    "message": "Human-readable Telegram message explaining what happened and what ARO did/would do"
  }}
}}

## Rules
- NEVER suggest deleting containers, volumes, or data. This action does not exist.
- NEVER suggest modifying environment variables or network configuration.
- NEVER suggest actions on containers classified as critical-infra or monitoring.
- NEVER suggest managing aro-brain (yourself).
- Check the operating mode. In {mode} mode, only these actions are allowed: {get_allowed_actions(mode)}.
- If your confidence is below 0.6, set all actions to notify_only.
- If a container was already acted on in the last 5 minutes (check recent_actions), do NOT act again — notify_only.
- Memory scaling cap: never exceed {settings.MAX_MEMORY_PER_CONTAINER} per container or {settings.MAX_TOTAL_MEMORY_PERCENT}% of total host RAM across all containers.
- Always include a notification — the operator should know what you're doing.
- For proactive scans with no issues found, respond with urgency "info" and a brief all-clear message.
"""
```

### Dynamic Model Selection

ARO doesn't hardcode a single model. Kilo provides 330+ models — ARO picks the right one for the job based on urgency, cost, and task type. Model assignments are configurable via env vars so you can swap as Kilo's catalog evolves.

```python
class ModelRouter:
    """Select the optimal LLM model based on task urgency and type."""
    
    TIERS = {
        "premium":  os.getenv("KILO_MODEL_PREMIUM", "anthropic/claude-sonnet-4-20250514"),
        "mid":      os.getenv("KILO_MODEL_MID", "anthropic/claude-haiku-4-5-20251001"),
        "economy":  os.getenv("KILO_MODEL_ECONOMY", "qwen3-coder"),
        "free":     os.getenv("KILO_MODEL_FREE", "minimax"),
    }
    
    def select(self, urgency: str, task_type: str) -> str:
        if task_type == "conversation":
            # Telegram chat needs good natural language understanding
            return self.TIERS["mid"]
        
        if urgency == "critical":
            return self.TIERS["premium"]
        elif urgency == "high":
            return self.TIERS["mid"]
        elif urgency in ("medium", "warning"):
            return self.TIERS["economy"]
        else:
            # Low urgency, proactive anomaly triage, scheduler
            return self.TIERS["free"]
```

| Situation | Urgency | Model tier | Approx cost/call |
|-----------|---------|------------|-------------------|
| Critical alert (OOM, container down) | critical | Premium (Claude Sonnet) | ~$0.01-0.03 |
| Warning alert (high memory/CPU) | warning | Economy (qwen3) | Free/negligible |
| Proactive scan found anomaly | medium | Economy/Free | Free/negligible |
| Proactive scan all-clear | — | **No LLM call** | $0 |
| Telegram conversation | — | Mid (Claude Haiku) | ~$0.005 |
| Scheduler idle detection | low | Free (minimax) | Free |
| Complex multi-container cascade | critical | Premium | ~$0.03 |

---

## 7. Action Executor (with built-in validation)

The executor validates before executing. No separate validator layer — the safety rules are a `_validate()` method inside the executor, not a standalone class. This keeps the architecture flat while remaining fully testable.

```python
class ActionExecutor:
    """Validates and executes actions. Validation is built-in, not a separate layer."""
    
    ALWAYS_FORBIDDEN = {"delete", "modify_env", "modify_network", "modify_volume"}
    SAFE_MODE_BLOCKED = {"scale_memory_down", "scale_cpu_down", "pause", "stop", "silence_alert"}
    PROTECTED_CATEGORIES = {"critical-infra", "monitoring"}
    
    def _validate(self, action: dict, mode: str, registry: ServiceRegistry) -> tuple[bool, str, bool]:
        """Returns (allowed, reason, would_have_done). Built-in, not a separate class."""
        target = action["target"]
        action_type = action["type"]
        service = registry.get(target)
        
        if action_type in self.ALWAYS_FORBIDDEN:
            return False, "Permanently forbidden action", False
        if service and service.category in self.PROTECTED_CATEGORIES:
            return False, f"Cannot act on {service.category} service", False
        if target == "aro-brain":
            return False, "ARO cannot manage itself", False
        if mode == "safe" and action_type in self.SAFE_MODE_BLOCKED:
            return False, f"Action '{action_type}' blocked by safe mode", True
        if action_type == "scale_memory_up":
            new_limit = parse_memory(action["params"].get("new_limit", "0"))
            if new_limit > 4 * 1024**3:
                return False, "Exceeds 4GB per-container cap", False
        if action_log.in_cooldown(target, cooldown_seconds=300):
            return False, "Container in 5-min cooldown", False
        return True, "", False
    
    async def execute(self, action: dict, mode: str, registry: ServiceRegistry) -> ActionResult:
        allowed, reason, would_have = self._validate(action, mode, registry)
        if not allowed:
            return ActionResult(executed=False, reason=reason, would_have_done=would_have)
        # ... execute via Coolify/Docker API
```

| Action | API | Endpoint |
|--------|-----|----------|
| restart | Coolify | `GET /applications/{uuid}/restart` |
| scale_memory_up | Coolify | `PATCH /applications/{uuid}` → `{limits_memory: "1G"}` then restart |
| scale_memory_down | Coolify | Same as above with lower value |
| scale_cpu_up | Coolify | `PATCH /applications/{uuid}` → `{limits_cpu_shares: 1024}` then restart |
| scale_cpu_down | Coolify | Same as above with lower value |
| pause | Coolify | `GET /applications/{uuid}/stop` (stop, NOT delete) |
| wake | Coolify | `GET /applications/{uuid}/start` |
| stop | Coolify | `GET /applications/{uuid}/stop` |
| notify_only | Apprise | `POST /notify` with Telegram message |

### Non-Coolify Containers

For containers not managed by Coolify (monitoring stack, Authelia), ARO uses Docker API via socket:
- Read-only for metrics/status: `docker inspect`, `docker stats`
- Restart only: `docker restart {container_id}` (platform category, auto mode only)

---

## 8. Telegram Bot (Two-Way Conversation)

ARO isn't just a notification sender — it's a conversational AI you can talk to over Telegram. This is the interface for when you're away from your laptop, on your phone, or simply want to give a quick directive without SSH.

### How It Works

```
Telegram Bot API (long-polling from ARO)
    ↓
Message router: Is this a reply to an alert thread, or a new command?
    ↓
Context builder: Load relevant service state + alert history
    ↓
LLM reasoner: Interpret natural language directive
    ↓
Action validator: Same safety rules apply
    ↓
Execute + confirm back on Telegram
```

### Conversation Examples

**Reactive — ARO asks, you decide:**
```
ARO:  🤖 Container seo-module memory at 92%. Confidence 0.4 on root cause.
      Logs show both heavy traffic AND possible leak. 
      Should I restart, or scale memory to 2G first?

You:  check the request rate first

ARO:  📊 Request rate: 340 req/min (normal is ~50). This is a traffic spike, not a leak.
      Scaling memory to 2G would be safer than restarting during high traffic.

You:  do it

ARO:  ✅ Scaled seo-module memory: 1G → 2G. Redeploying now.
      Will monitor for 15 min and report back.
```

**Ad-hoc commands (you initiate):**
```
You:  status

ARO:  💚 All systems normal
      24 services monitored | Mode: safe
      CPU 15% | RAM 9.1/12GB (76%) | Disk 68%
      Last action: 3h ago (restarted translator)

You:  restart image-broker

ARO:  🔄 Restarting image-broker... done. Container healthy after 8s.

You:  switch to auto mode

ARO:  ⚠️ Switching to auto mode. I'll now be able to:
      - Scale memory/CPU down
      - Pause idle services  
      - Stop misbehaving containers
      Confirm? (yes/no)

You:  yes

ARO:  ✅ Mode switched to auto. I'll notify you of all actions taken.

You:  what's eating the most memory?

ARO:  📊 Top 5 by memory:
      1. postgres-main — 2.8GB (critical-infra, won't touch)
      2. loki — 1.9GB (monitoring, won't touch)
      3. seo-module — 1.2GB / 2GB limit
      4. n8n — 890MB
      5. grafana — 650MB
      Total: 9.1GB / 12GB host
```

### Implementation

- **Telegram Bot API** via `python-telegram-bot` library (async, **long-polling mode**)
- **Why long-polling, not webhook:** Long-polling doesn't need a public URL — ARO polls Telegram for updates every 1-2s from inside the container. No Traefik routing, no Authelia bypass, no SSL certificate for the webhook. Simpler and more secure. Latency is ~1-2s which is fine for a chat interface.
- **Background task:** Long-polling runs as an asyncio task inside the FastAPI lifespan, not a separate process.
- **Auth:** Only responds to your Telegram user ID (env var `TELEGRAM_OWNER_ID`)
- **Session:** Each alert thread gets a conversation context for continuity — the LLM remembers what you discussed about this specific alert
- **LLM context:** Your message + current service state + alert history → LLM → structured response + natural language reply
- **Dual notification path:** Bot sends interactive messages directly via Bot API. Apprise handles one-way notifications (heartbeat, proactive alerts) so they work even if the bot has issues.
- **`/api/telegram` endpoint removed** — not needed with long-polling. The bot listens directly via the `python-telegram-bot` polling loop.

### Env Vars

```env
TELEGRAM_BOT_TOKEN=                    # from @BotFather
TELEGRAM_OWNER_ID=                     # your Telegram numeric user ID (security: only you can command ARO)
```

### Security

- **Owner-only:** ARO only responds to messages from `TELEGRAM_OWNER_ID`. All other messages get ignored silently.
- **No sensitive data in chat:** ARO never sends API keys, passwords, or env var values over Telegram. If you ask for them, it refuses.
- **Action confirmation for dangerous ops:** In safe mode, any action that would modify infrastructure requires explicit "yes" confirmation in chat.

---

## 9. Notification System

Every action (executed or blocked) generates a Telegram notification via Apprise (one-way). The Telegram Bot (section 9) handles two-way conversation separately.

### Notification Channels

| Channel | Used for | Mechanism |
|---------|----------|-----------|
| Apprise → Telegram | One-way alerts, heartbeats, proactive findings | `POST apprise:8000/notify` with tag `telegram` |
| Telegram Bot API | Two-way conversation, command responses | Direct Bot API via `python-telegram-bot` |
| Both simultaneously | Never — bot messages go through bot, system alerts through Apprise | Prevents duplicate messages |

### Message Templates

**Action executed:**
```
🤖 ARO Brain — Action Taken

📦 Container: seo-module
⚠️ Alert: ContainerHighMemory (87%)
🔍 Root cause: Memory leak — RSS growing 15MB/min for 30 min, error logs show unclosed DB connections
✅ Action: Restarted container
📊 Confidence: 0.85

Memory before: 1.8GB / 2GB limit
Next scan in 15 min to verify fix.
```

**Action blocked (safe mode):**
```
🤖 ARO Brain — Action Blocked (Safe Mode)

📦 Container: image-broker  
⚠️ Alert: ContainerHighMemory (72%)
🔍 Assessment: Container allocated 2GB but only needs ~800MB based on 24h usage pattern
🚫 Would have done: Scale memory down to 1GB
💡 Reason: safe mode doesn't allow scale-down

Switch to ARO_MODE=auto if you want me to handle this.
```

**Proactive scan — issue found:**
```
🤖 ARO Brain — Trend Alert

📈 Disk usage trending: 73% → predicted 88% in 24h
📦 Top consumers: postgres-main (12GB), loki (8GB), duplicati-cache (3GB)
💡 Recommendation: Loki retention may need adjustment — 8GB of logs seems high
🔕 No action taken — notify only

Check: ssh vps "du -sh /var/lib/docker/volumes/*" | sort -rh | head
```

**Heartbeat (hourly):**
```
💚 ARO Brain — Heartbeat

Mode: safe | Uptime: 14h 32m
Services: 24 monitored (18 app, 3 platform, 3 infra)
Last 1h: 0 actions taken, 4 proactive scans (all clear)
Host: CPU 12% | RAM 8.4/12GB (70%) | Disk 67%
```

---

## 10. Self-Monitoring & Graceful Degradation

| Mechanism | How | Catches |
|-----------|-----|---------|
| `/health` endpoint | Tests Prometheus, Loki, Coolify API, LLM provider, Apprise, Telegram bot | Dependency failures |
| Uptime Kuma monitor | External ping to `http://aro-brain:8017/health` every 60s | ARO container crash |
| Hourly heartbeat | ARO → Apprise/Telegram every hour | Silent failures (ARO alive but not working) |
| Self-exclusion | Hardcoded: ARO never appears in its own action candidates | Infinite loop prevention |

### Degradation Hierarchy

When dependencies fail, ARO degrades gracefully instead of crashing or going silent:

| Dependency down | ARO behavior | Notification path |
|-----------------|-------------|-------------------|
| LLM provider (Kilo API) | **Rule-based fallback** for known alert types (ContainerDown→restart, OOM→scale+restart). Unknown alerts→notify only. | Apprise + Telegram bot |
| Prometheus | Can't build metrics context. **Notify only** — never act without data. | Apprise + Telegram bot |
| Loki | Partial context (metrics only, no logs). LLM reasons with what it has, lower confidence threshold. | Normal |
| Coolify API | Can reason but **can't execute**. Logs decision, notifies: "I decided X but can't reach Coolify." | Apprise + Telegram bot |
| Apprise | Notifications via **Telegram bot directly** (bot sends messages independently of Apprise). | Telegram bot only |
| Telegram bot | One-way notifications via **Apprise only**. No conversation, no commands. | Apprise only |
| Both Apprise + Telegram | **Write to action log only**. Retry both every 5 min. | Action log (file) |
| Everything except ARO | Write to action log, retry all connections every 5 min, self-heal when deps recover. | Action log (file) |

### Alert Rate Limiting

A noisy Alertmanager can fire 50+ alerts during a network partition (everything looks "down"). Without rate limiting, ARO would make 50 simultaneous LLM calls.

```python
class AlertRateLimiter:
    """Token bucket rate limiter for LLM calls."""
    
    MAX_LLM_CALLS_PER_MINUTE = 5        # max 5 LLM reasoning calls per minute
    MAX_ACTIONS_PER_HOUR = 20           # max 20 executed actions per hour
    BURST_DETECTION_THRESHOLD = 10      # 10+ alerts in 1 min = burst mode
    
    def on_burst_detected(self, alerts: list):
        """When burst detected, batch all alerts into single LLM call."""
        # Don't reason about each alert individually — 
        # send them all at once: "Here are 15 alerts that fired simultaneously.
        # This is likely a systemic issue, not 15 independent problems."
        pass
```

### First-Run Onboarding

When ARO starts for the first time (no `/data/aro/registry.json` exists):

```
1. Discover all containers (Coolify API + Docker socket)
2. Auto-classify based on labels/names (see classification rules below)
3. Query Prometheus for baseline metrics (last 1h snapshot)
4. Test all dependencies (Prometheus, Loki, Coolify, Apprise)
5. Send onboarding Telegram message:

🤖 ARO Brain — First Start

I've discovered 24 containers on this VPS:
  📦 3 critical-infra (coolify, traefik, postgres-main)
  📦 4 monitoring (prometheus, grafana, loki, alertmanager, ...)
  📦 3 platform (authelia, apprise, n8n)
  📦 14 application (seo-module, image-broker, ...)

Mode: safe (I'll notify but ask before acting)
Dependencies: ✅ Prometheus ✅ Loki ✅ Coolify ✅ Apprise

Reply /status anytime to check on me.
Reply /help to see all commands.
```

### Health Endpoint Detail

```python
@app.get("/health")
async def health():
    checks = {
        "prometheus": await check_prometheus(),   # GET prometheus:9090/-/healthy
        "loki": await check_loki(),               # GET loki:3100/ready
        "coolify_api": await check_coolify(),      # GET coolify:8000/api/v1/version
        "llm_provider": await check_llm(),         # Quick test call to Kilo API (or configured provider)
        "apprise": await check_apprise(),          # GET apprise:8000/status
        "telegram_bot": check_telegram(),          # Bot polling alive
        "action_log": check_action_log(),          # file writable
    }
    all_ok = all(v["status"] == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "mode": settings.ARO_MODE,
        "uptime_seconds": get_uptime(),
        "services_monitored": registry.count(),
        "checks": checks,
    }
```

---

## 11. Data Persistence

| Data | Storage | Retention |
|------|---------|-----------|
| Action log | `/data/aro/actions.jsonl` (append-only) | 30 days, auto-rotated |
| Service registry cache | `/data/aro/registry.json` | Refreshed every 5 min, persisted for restart recovery |
| LLM call log | `/data/aro/llm-calls.jsonl` | 7 days — prompt, response, tokens, cost, model |
| Config state | Environment variables only | No persistent config — 12-factor |

Volume: `aro-data` mounted at `/data/aro/` in Docker Compose.

---

## 12. Configuration (Environment Variables)

```env
# Operating mode
ARO_MODE=safe                          # safe | auto

# LLM provider
LLM_PROVIDER=kilo                      # kilo | anthropic | openai | ollama (future)

# Kilo LLM — direct API (same pattern as SEO module llm_client.py)
KILO_API_KEY=                          # from Kilo CLI settings
KILO_API_URL=https://api.kilo.ai/v1/chat/completions

# Dynamic model selection (4 tiers, all configurable)
KILO_MODEL_PREMIUM=anthropic/claude-sonnet-4-20250514   # critical alerts, complex cascades
KILO_MODEL_MID=anthropic/claude-haiku-4-5-20251001      # Telegram conversation, warning alerts
KILO_MODEL_ECONOMY=qwen3-coder                          # proactive anomaly triage
KILO_MODEL_FREE=minimax                                 # scheduler, low-urgency analysis

# Telegram Bot (two-way conversation)
TELEGRAM_BOT_TOKEN=                    # from @BotFather
TELEGRAM_OWNER_ID=                     # your numeric Telegram user ID (only you can command ARO)

# Infrastructure endpoints (all on coolify network)
PROMETHEUS_URL=http://prometheus:9090
LOKI_URL=http://loki:3100
COOLIFY_API_URL=http://coolify:8000/api/v1
COOLIFY_API_TOKEN=                      # from Coolify Settings > API Tokens
ALERTMANAGER_URL=http://alertmanager:9093
APPRISE_URL=http://apprise:8000

# Notification
APPRISE_NOTIFY_TAG=telegram             # which Apprise tag to use
HEARTBEAT_INTERVAL_MINUTES=60

# Timing
PROACTIVE_SCAN_INTERVAL_MINUTES=15
SCHEDULER_INTERVAL_MINUTES=60
REGISTRY_REFRESH_INTERVAL_MINUTES=5
COOLDOWN_SECONDS=300                    # min time between actions on same container

# Safety caps
MAX_MEMORY_PER_CONTAINER=4G
MAX_TOTAL_MEMORY_PERCENT=80             # of host RAM

# Logging
LOG_LEVEL=INFO
```

---

## 13. Docker Compose

```yaml
services:
  aro-brain:
    build: .
    container_name: aro-brain
    restart: unless-stopped
    ports:
      - "8017:8017"
    environment:
      - ARO_MODE=${ARO_MODE:-safe}
      - LLM_PROVIDER=${LLM_PROVIDER:-kilo}
      - KILO_API_KEY=${KILO_API_KEY}
      - KILO_API_URL=${KILO_API_URL:-https://api.kilo.ai/v1/chat/completions}
      - KILO_MODEL_PREMIUM=${KILO_MODEL_PREMIUM:-anthropic/claude-sonnet-4-20250514}
      - KILO_MODEL_MID=${KILO_MODEL_MID:-anthropic/claude-haiku-4-5-20251001}
      - KILO_MODEL_ECONOMY=${KILO_MODEL_ECONOMY:-qwen3-coder}
      - KILO_MODEL_FREE=${KILO_MODEL_FREE:-minimax}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_OWNER_ID=${TELEGRAM_OWNER_ID}
      - PROMETHEUS_URL=${PROMETHEUS_URL:-http://prometheus:9090}
      - LOKI_URL=${LOKI_URL:-http://loki:3100}
      - COOLIFY_API_URL=${COOLIFY_API_URL:-http://coolify:8000/api/v1}
      - COOLIFY_API_TOKEN=${COOLIFY_API_TOKEN}
      - ALERTMANAGER_URL=${ALERTMANAGER_URL:-http://alertmanager:9093}
      - APPRISE_URL=${APPRISE_URL:-http://apprise:8000}
      - APPRISE_NOTIFY_TAG=${APPRISE_NOTIFY_TAG:-telegram}
      - COOLDOWN_SECONDS=${COOLDOWN_SECONDS:-300}
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    volumes:
      - aro-data:/data/aro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - coolify
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8017/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 15s
    labels:
      - "coolify.managed=true"

volumes:
  aro-data:

networks:
  coolify:
    external: true
```

**Deployment:** Managed by Coolify as a Docker Compose resource (same as your Fabrik microservices). No sidecar — LLM calls go directly to Kilo API over the internet. Single container, simple lifecycle.

### Batch Alert Handling

Alertmanager groups alerts and sends them as a batch (multiple alerts in one webhook payload). ARO handles this by reasoning about all alerts together, not independently:

```python
@app.post("/api/alerts")
async def receive_alerts(request: Request):
    payload = await request.json()
    alerts = payload.get("alerts", [])
    
    if len(alerts) == 1:
        # Single alert — standard flow
        context = await context_builder.build_for_alert(alerts[0])
        decision = await llm_reasoner.reason(context)
    else:
        # Batch — could be a cascade. Reason about all together.
        context = await context_builder.build_for_batch(alerts)
        # LLM sees all alerts at once: "3 containers OOM'd simultaneously — 
        # this is probably a host memory issue, not 3 independent leaks"
        decision = await llm_reasoner.reason(context)
    
    results = await executor.execute_decision(decision)
    return {"processed": len(alerts), "results": results}
```

---

## 14. API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Full dependency health check |
| `POST` | `/api/alerts` | Alertmanager webhook receiver (reactive loop entry) |
| `GET` | `/api/services` | List all discovered services with classification |
| `GET` | `/api/actions` | View action log (last N actions) |
| `GET` | `/api/status` | ARO operational status (mode, uptime, stats) |
| `POST` | `/api/scan` | Trigger manual proactive scan |
| `POST` | `/api/classify` | Manually classify a container: `{container, category}` |
| `POST` | `/api/mode` | Switch operating mode: `{mode: "safe"|"auto"}` |

---

## 15. File Structure (Fabrik python-api scaffold)

```
projects/aro-brain/
├── src/
│   └── aro/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app, lifespan, route registration
│       ├── config.py               # Settings from env vars (pydantic-settings)
│       ├── logger.py               # Pre-scaffolded structured logger
│       ├── api/
│       │   ├── __init__.py
│       │   ├── alerts.py           # POST /api/alerts — Alertmanager webhook
│       │   ├── services.py         # GET /api/services, POST /api/classify
│       │   ├── actions.py          # GET /api/actions
│       │   └── control.py          # POST /api/scan, /api/mode, GET /api/status
│       ├── core/
│       │   ├── __init__.py
│       │   ├── context_builder.py  # Assembles full context from all sources
│       │   ├── llm_provider.py     # Provider interface + KiloDirectProvider (+ future: Anthropic, OpenAI, Ollama)
│       │   ├── llm_reasoner.py     # System prompt construction, JSON parsing, provider calls
│       │   ├── model_router.py     # Dynamic model selection (4 tiers by urgency)
│       │   ├── action_executor.py  # Built-in validation + Coolify API + Docker API execution
│       │   └── notifier.py         # Apprise notification formatting + sending
│       ├── telegram/
│       │   ├── __init__.py
│       │   ├── bot.py              # Telegram Bot setup, webhook registration
│       │   ├── handler.py          # Message routing, command parsing, conversation mgmt
│       │   └── commands.py         # Built-in commands: /status, /restart, /mode, etc.
│       ├── registry/
│       │   ├── __init__.py
│       │   ├── service_registry.py # Auto-discovery, classification, caching
│       │   ├── coolify_client.py   # Coolify REST API wrapper
│       │   ├── docker_client.py    # Docker socket read-only client
│       │   └── models.py           # ManagedService, ResourceLimits, etc.
│       ├── monitors/
│       │   ├── __init__.py
│       │   ├── prometheus_client.py # PromQL query wrapper
│       │   ├── loki_client.py      # LogQL query wrapper
│       │   └── queries.py          # Pre-defined PromQL/LogQL + prefilter thresholds
│       ├── scheduler/
│       │   ├── __init__.py
│       │   ├── proactive_scan.py   # Two-stage: prefilter (free) → LLM (if anomaly)
│       │   ├── idle_detector.py    # Idle detection (see definition below)
│       │   └── heartbeat.py        # Hourly heartbeat to Apprise
│       └── storage/
│           ├── __init__.py
│           └── action_log.py       # JSONL append-only log with rotation
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── .env.example
├── README.md
├── CHANGELOG.md
└── tests/
    ├── test_executor.py
    ├── test_context_builder.py
    └── test_registry.py
```

### Idle Detection Definition

"Idle" means different things for different container types. ARO uses a multi-signal approach:

| Signal | Source | Measures | Good for |
|--------|--------|----------|----------|
| Network RX bytes | Prometheus: `rate(container_network_receive_bytes_total[1h])` | Incoming traffic rate | Web-facing services (APIs, WordPress sites) |
| CPU usage | Prometheus: `rate(container_cpu_usage_seconds_total[1h])` | Processing activity | Background workers, cron jobs |
| Network TX bytes | Prometheus: `rate(container_network_transmit_bytes_total[1h])` | Outgoing traffic | Services that call external APIs |

**Idle criteria (all must be true for the idle window):**
```python
IDLE_THRESHOLDS = {
    "network_rx_bytes_per_sec": 100,      # < 100 bytes/sec inbound = no meaningful traffic
    "cpu_usage_percent": 1.0,              # < 1% CPU = not processing anything
    "idle_window_hours": 2,                # must be idle for 2+ continuous hours
}
```

**Containers that are NEVER considered idle:**
- Any container in `critical-infra` or `monitoring` category
- Containers with Docker label `aro.always-on=true`
- Containers with scheduled jobs (detected via cron-like CPU spikes at regular intervals)

**Wake trigger:** Uptime Kuma HTTP check returns non-200 → ARO wakes the container. This means paused services auto-wake when someone tries to access them — zero downtime from the user's perspective (just a cold-start delay).

---

## 16. Implementation Phases

### Phase 1 — Core Loop (MVP) — ~20h

Get the reactive loop working end-to-end on your VPS.

1. Scaffold project (Fabrik python-api)
2. `config.py` — all env vars via pydantic-settings
3. `coolify_client.py` — list apps, restart, update limits, stop, start
4. `docker_client.py` — read-only Docker socket for non-Coolify containers
5. `service_registry.py` — auto-discovery, classification, 5-min refresh
6. `prometheus_client.py` — PromQL query wrapper
7. `loki_client.py` — LogQL query wrapper
8. `context_builder.py` — assemble full context dict (single alert + batch)
9. `llm_provider.py` — provider interface + KiloDirectProvider (async httpx)
10. `model_router.py` — dynamic 4-tier model selection
11. `llm_reasoner.py` — system prompt, JSON parsing, provider calls
12. `action_executor.py` — built-in validation + execute via Coolify/Docker API
13. `notifier.py` — Apprise Telegram notifications (one-way)
14. `alerts.py` — POST /api/alerts webhook endpoint (handles batch alerts)
15. `action_log.py` — JSONL persistence
16. `main.py` — FastAPI app with lifespan, health check
17. Dockerfile + compose.yaml
18. Deploy to VPS via Coolify, wire Alertmanager webhook
19. Test with simulated alerts (single + batch) in dry run
20. Switch to safe mode, validate on live alerts

### Phase 2 — Telegram Bot — ~8h

21. Create Telegram bot via @BotFather, get token
22. `bot.py` — bot setup, long-polling as asyncio task in FastAPI lifespan
23. `handler.py` — message routing (alert reply vs new command vs natural language)
24. `commands.py` — built-in commands: /status, /restart, /mode, /services, /logs
25. Auth enforcement — only respond to TELEGRAM_OWNER_ID
26. Conversation context per alert thread (LLM remembers discussion history)
27. Test: send commands, reply to alert notifications, natural language directives
28. Test: confirm rejection of non-owner messages

### Phase 3 — Proactive + Scheduler — ~10h

29. `queries.py` — prefilter thresholds + trend PromQL + anomaly LogQL
30. `proactive_scan.py` — two-stage: rule-based prefilter → LLM only if anomaly
31. `idle_detector.py` — traffic analysis for pause/wake decisions
32. `heartbeat.py` — hourly Telegram heartbeat
33. `control.py` — manual scan trigger, mode switch API
34. `services.py` — manual classification endpoint
35. Test proactive loop for 48h, tune false positive rate
36. Verify zero LLM calls on quiet days

### Phase 4 — Hardening — ~8h

37. Action log rotation (30-day retention)
38. LLM call logging (7-day retention, cost tracking per model tier)
39. Uptime Kuma monitor for ARO health endpoint
40. Grafana dashboard for ARO actions/decisions (optional)
41. Daily cost summary in heartbeat message
42. Retry logic for transient Coolify API / Kilo API failures
43. LLM provider fallback — if primary model unavailable, downgrade tier (premium→mid→economy)
44. Integration tests with mock Prometheus/Loki/LLM responses

### Phase 5 — Commercial Preparation (future)

45. Extract Kilo dependency → support direct OpenAI/Anthropic API keys
46. Remove Fabrik-specific hardcoded container names → YAML config file
47. Web dashboard (Next.js) for non-CLI users
48. Multi-VPS support (agent per VPS, central dashboard)
49. Onboarding wizard (auto-detect stack, suggest config)
50. Stripe/Paddle billing for hosted dashboard tier
51. Documentation site, landing page
52. Telegram bot as optional add-on (works without it in headless mode)

---

## 17. Commercial Viability Notes

### Target Market
- Solo developers running Coolify (10k+ Coolify GitHub stars = active community)
- Small agencies managing 5-20 client sites on Docker VPS
- Indie hackers with side projects on Hetzner/DigitalOcean

### Pricing Model (future)
| Tier | Price | What |
|------|-------|------|
| **Core** | Free (self-hosted) | Single VPS, all features, bring your own LLM key |
| **Pro** | $19/mo | Cloud dashboard, multi-VPS fleet view, hosted LLM (no key needed) |
| **Team** | $49/mo | Multiple users, shared dashboard, Slack/Discord integration |

### Competitive Landscape
| Competitor | Price | Gap ARO fills |
|------------|-------|---------------|
| Datadog | $15/host/mo + per-metric | No autonomous actions, enterprise-focused |
| Better Uptime | $20/mo | Monitoring only, no remediation |
| Prometheus + Alertmanager | Free | No reasoning, static rules, no auto-remediation |
| Beszel | Free | Monitoring only, no AI, no actions |

**ARO's moat:** It doesn't just alert — it thinks and acts. No competitor in the self-hosted/Coolify space does autonomous AI-reasoned remediation.

---

## 18. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| LLM hallucinates a dangerous action | Validator hardcodes forbidden actions — LLM cannot bypass |
| LLM latency delays critical response | Timeout at 30s → fallback to rule-based decision for known alert types |
| Kilo API goes down | Health check detects → ARO enters degraded mode (notify-only via Apprise, no LLM reasoning). Rule-based fallback for known critical alerts (container down → restart). |
| Cascade: ARO restarts X, X comes back unhealthy, ARO restarts again | 5-min cooldown per container + max 3 actions/hour per container |
| ARO itself crashes | Uptime Kuma detects within 60s, notifies via its own Telegram integration |
| Cost overrun on LLM calls | Two-stage proactive scan (zero cost on quiet days). Free-tier models for routine. Daily cost tracking in heartbeat. |
| Docker socket access = security surface | Mounted read-only (`:ro`). ARO only uses `inspect` and `stats`. All mutations go through Coolify API. |
| Telegram bot hijacked (someone guesses bot token) | Owner-only auth via `TELEGRAM_OWNER_ID`. All non-owner messages silently ignored. |
| Telegram webhook needs public URL | Solved: using long-polling mode instead of webhook. No public URL needed, no Traefik routing, no Authelia bypass. |
| Natural language misinterpretation | LLM interprets "restart everything" literally → validator still enforces per-container cooldown + category blocks. Dangerous commands require explicit confirmation. |

---

## 19. Dependencies

```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
httpx>=0.28.0
pydantic>=2.11.0
pydantic-settings>=2.8.0
apscheduler>=3.10.0
docker>=7.0.0                # Docker SDK for Python (read-only socket access)
python-telegram-bot>=21.0    # Telegram Bot API (async, webhook mode)
```

---

## 20. Success Criteria

After Phase 1+2+3 deployed and running for 1 week:

- [ ] ARO correctly handles all 9 existing alert types
- [ ] No false positive actions (safe mode validated)
- [ ] Proactive scan catches at least 1 trend before it becomes an alert
- [ ] Proactive scan makes zero LLM calls on quiet days (two-stage working)
- [ ] Heartbeat messages arrive every hour without gaps
- [ ] New container deployed via Coolify auto-discovered within 5 min
- [ ] Telegram messages are clear, actionable, and not spammy
- [ ] Telegram bot responds to commands (/status, /restart, natural language)
- [ ] Telegram bot correctly refuses commands from non-owner user IDs
- [ ] LLM cost < $5/month for routine operations
- [ ] Model router correctly selects free tier for low-urgency, premium for critical
- [ ] ARO survives its own restart (action log + registry persist and reload)
