# Weekend Blitz: Complete All Fabrik Phases

**Status:** REFERENCE ONLY (Superseded by actual implementations)
**Date:** 2026-02-28 to 2026-03-01
**Goal:** Complete Phases 3, 6, 8, 9 in 2 days with parallel AI coders

**Note:** This was a planning document. Actual implementation happened incrementally.
Phase priorities and implementations differ from this plan.

**READY TO ARCHIVE**

---

## Execution Overview

| Track | Phase | Coder | Day 1 | Day 2 |
|-------|-------|-------|-------|-------|
| **A** | Phase 9 | Coder 1 | Deploy services | Verify + docs |
| **B** | Phase 6 | Coder 2 | Deploy monitoring stack | Dashboards + alerts |
| **C** | Phase 3 | Coder 3 | Build LLMClient | CLI + integration |
| **D** | Phase 8 | Coder 4 | Deploy n8n | Build workflows |

**Skip:** Phase 5 (staging), Phase 7 (multi-server) - not needed now

---

## TRACK A: Phase 9 - Infrastructure Services

### Context for Coder 1

```markdown
# Phase 9: Deploy Infrastructure Services

## Goal
Deploy 5 pre-built Docker services to VPS1 via Coolify.

## DONE WHEN
- [ ] browserless accessible at browser.vps1.ocoron.com
- [ ] gotenberg accessible at pdf.vps1.ocoron.com/health
- [ ] minio accessible at s3.vps1.ocoron.com/minio/health/live
- [ ] apprise accessible at notify.vps1.ocoron.com
- [ ] meilisearch accessible at search.vps1.ocoron.com/health
- [ ] Specs created in /opt/fabrik/specs/infrastructure/
- [ ] Credentials in /opt/fabrik/.env
- [ ] PORTS.md updated
- [ ] SERVICES.md updated

## Out of Scope
- n8n deployment (Phase 8)
- Monitoring (Phase 6)
- Custom code integration

## Services

### 1. browserless/chrome
- Image: browserless/chrome:latest
- Port: 3000
- Domain: browser.vps1.ocoron.com
- Env: MAX_CONCURRENT_SESSIONS=10, CONNECTION_TIMEOUT=60000, PREBOOT_CHROME=true

### 2. gotenberg/gotenberg
- Image: gotenberg/gotenberg:8
- Port: 3001 (internal 3000)
- Domain: pdf.vps1.ocoron.com
- Health: /health

### 3. minio/minio
- Image: minio/minio:latest
- Ports: 9000 (API), 9001 (Console)
- Domain: s3.vps1.ocoron.com
- Env: MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
- Volume: minio-data:/data

### 4. caronc/apprise
- Image: caronc/apprise:latest
- Port: 8005 (8000 conflicts with Translator/Captcha)
- Domain: notify.vps1.ocoron.com

### 5. getmeili/meilisearch
- Image: getmeili/meilisearch:latest
- Port: 7700
- Domain: search.vps1.ocoron.com
- Env: MEILI_MASTER_KEY
- Volume: meilisearch-data:/meili_data

## Steps

1. Verify ARM64 support:
   ```bash
   cd /opt/fabrik && source .venv/bin/activate
   python scripts/container_images.py check-arch browserless/chrome:latest
   python scripts/container_images.py check-arch gotenberg/gotenberg:8
   python scripts/container_images.py check-arch minio/minio:latest
   python scripts/container_images.py check-arch caronc/apprise:latest
   python scripts/container_images.py check-arch getmeili/meilisearch:latest
   ```

2. Create specs in /opt/fabrik/specs/infrastructure/:
   - browserless.yaml
   - gotenberg.yaml
   - minio.yaml
   - apprise.yaml
   - meilisearch.yaml

3. Generate credentials:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. Add to /opt/fabrik/.env:
   - MINIO_ROOT_USER
   - MINIO_ROOT_PASSWORD
   - MEILI_MASTER_KEY

5. Deploy via Coolify (manual - provide instructions)

6. Update docs:
   - PORTS.md
   - docs/SERVICES.md
   - CHANGELOG.md

## Reference Files
- /opt/fabrik/docs/development/plans/previously-planned-fabrik-phases/phase9.md
- /opt/fabrik/docs/reference/prebuilt-app-containers.md

## Constraints
- All images MUST support linux/arm64 (VPS1 is ARM64)
- Use coolify external network
- Follow 9-step workflow
```

**Estimated time:** 4-6 hours

---

## TRACK B: Phase 6 - Monitoring Stack

### Context for Coder 2

```markdown
# Phase 6: Deploy Monitoring Stack

## Goal
Deploy Loki/Promtail/Prometheus/Grafana monitoring stack to VPS1.

## DONE WHEN
- [ ] Loki running at loki.vps1.ocoron.com (internal)
- [ ] Promtail shipping container logs to Loki
- [ ] Prometheus scraping metrics at prometheus.vps1.ocoron.com (internal)
- [ ] Node Exporter providing system metrics
- [ ] cAdvisor providing container metrics
- [ ] Grafana accessible at monitor.vps1.ocoron.com
- [ ] System dashboard created
- [ ] Container dashboard created
- [ ] Alert rules configured → Apprise → Slack
- [ ] CLI commands: fabrik logs <service>

## Out of Scope
- Custom application dashboards
- Trading-core specific alerts (later)

## Architecture

```
Services → Docker logs → Promtail → Loki ← Grafana
         → /metrics → Prometheus ← Grafana
                          ↑
              Node Exporter + cAdvisor
                          ↓
                    Alert Rules → Apprise
```

## Services to Deploy

### 1. Loki (Log aggregation)
- Image: grafana/loki:2.9.0
- Port: 3100 (internal)
- Volume: loki-data:/loki
- Config: /opt/fabrik/configs/loki/loki-config.yaml

### 2. Promtail (Log shipper)
- Image: grafana/promtail:2.9.0
- Mounts: /var/log, /var/lib/docker/containers
- Config: /opt/fabrik/configs/promtail/promtail-config.yaml

### 3. Prometheus (Metrics)
- Image: prom/prometheus:v2.47.0
- Port: 9090 (internal)
- Volume: prometheus-data:/prometheus
- Config: /opt/fabrik/configs/prometheus/prometheus.yml

### 4. Node Exporter (System metrics)
- Image: prom/node-exporter:v1.6.1
- Port: 9100 (internal)

### 5. cAdvisor (Container metrics)
- Image: gcr.io/cadvisor/cadvisor:v0.47.0
- Port: 8080 (internal)
- Mounts: /var/run/docker.sock, /sys, /var/lib/docker

### 6. Grafana (Dashboards)
- Image: grafana/grafana:10.1.0
- Port: 3002
- Domain: monitor.vps1.ocoron.com
- Volume: grafana-data:/var/lib/grafana
- Env: GF_SECURITY_ADMIN_PASSWORD

## Steps

1. Create config directory:
   ```bash
   mkdir -p /opt/fabrik/configs/{loki,promtail,prometheus,grafana}
   ```

2. Create Loki config (loki-config.yaml)

3. Create Promtail config (promtail-config.yaml)

4. Create Prometheus config (prometheus.yml)

5. Create compose file: /opt/fabrik/specs/infrastructure/monitoring-stack.yaml

6. Deploy via Coolify

7. Configure Grafana:
   - Add Loki data source
   - Add Prometheus data source
   - Import dashboards (Node Exporter Full: 1860, Docker: 893)

8. Create alert rules:
   - Container restart > 3 in 5 min
   - CPU > 90% for 5 min
   - Disk > 85%
   - Memory > 90%

9. Configure alerting → Apprise

10. Add CLI commands to /opt/fabrik/src/fabrik/cli.py:
    - fabrik logs <service> [--tail N] [--since 1h]
    - fabrik metrics <service>

## Reference Files
- /opt/fabrik/docs/development/plans/previously-planned-fabrik-phases/Phase6.md

## Constraints
- All images MUST support linux/arm64
- Grafana must be password protected
- Logs retention: 7 days
- Metrics retention: 15 days
```

**Estimated time:** 6-8 hours

---

## TRACK C: Phase 3 - AI Content Integration

### Context for Coder 3

```markdown
# Phase 3: AI Content Integration

## Goal
Build provider-agnostic LLM client with CLI and cost tracking.

## DONE WHEN
- [ ] src/fabrik/ai/client.py exists with LLMClient class
- [ ] Supports Claude (primary) and OpenAI (fallback)
- [ ] Token usage tracking in SQLite
- [ ] fabrik ai generate "prompt" works
- [ ] fabrik ai revise <file> "instructions" works
- [ ] fabrik ai usage --month shows costs
- [ ] Prompt templates in /opt/fabrik/templates/prompts/

## Out of Scope
- WordPress content generation (Phase 2 integration)
- Bulk generation
- SEO optimization

## Architecture

```python
# src/fabrik/ai/__init__.py
from .client import LLMClient, LLMProvider, LLMResponse

# src/fabrik/ai/client.py
class LLMProvider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"

class LLMResponse:
    content: str
    tokens_in: int
    tokens_out: int
    cost: float
    model: str
    provider: LLMProvider

class LLMClient:
    def __init__(self, provider: LLMProvider = LLMProvider.CLAUDE):
        ...

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate content with retry and cost tracking."""
        ...

    def generate_structured(self, prompt: str, schema: dict) -> dict:
        """Generate JSON matching schema."""
        ...

    def revise(self, content: str, instructions: str) -> str:
        """Revise existing content."""
        ...

# src/fabrik/ai/tracker.py
class UsageTracker:
    def __init__(self, db_path: str = "~/.fabrik/ai_usage.db"):
        ...

    def record(self, response: LLMResponse, project: str = None):
        ...

    def get_usage(self, month: str = None, project: str = None) -> dict:
        ...
```

## Files to Create

1. `src/fabrik/ai/__init__.py`
2. `src/fabrik/ai/client.py` - Main LLMClient
3. `src/fabrik/ai/tracker.py` - SQLite usage tracking
4. `src/fabrik/ai/providers/` - Provider implementations
5. `templates/prompts/` - Prompt templates

## CLI Commands (add to cli.py)

```python
@cli.group()
def ai():
    """AI content generation commands."""
    pass

@ai.command()
@click.argument("prompt")
@click.option("--provider", type=click.Choice(["claude", "openai"]), default="claude")
@click.option("--model", default=None)
def generate(prompt: str, provider: str, model: str):
    """Generate content from prompt."""
    ...

@ai.command()
@click.argument("file", type=click.Path(exists=True))
@click.argument("instructions")
def revise(file: str, instructions: str):
    """Revise content in file based on instructions."""
    ...

@ai.command()
@click.option("--month", default=None, help="Month in YYYY-MM format")
@click.option("--project", default=None)
def usage(month: str, project: str):
    """Show AI usage and costs."""
    ...
```

## Environment Variables

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Cost Tracking Schema

```sql
CREATE TABLE ai_usage (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    provider TEXT,
    model TEXT,
    tokens_in INTEGER,
    tokens_out INTEGER,
    cost_usd REAL,
    project TEXT,
    prompt_hash TEXT
);
```

## Pricing (store in code)

```python
PRICING = {
    "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},  # per 1M tokens
    "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}
```

## Reference Files
- /opt/fabrik/docs/development/plans/previously-planned-fabrik-phases/Phase3.md
- /opt/fabrik/src/fabrik/cli.py (existing CLI structure)

## Constraints
- Use httpx for API calls
- Retry with exponential backoff
- Follow existing Fabrik code style
- Tests in tests/test_ai_client.py
```

**Estimated time:** 6-8 hours

---

## TRACK D: Phase 8 - n8n Automation

### Context for Coder 4

```markdown
# Phase 8: n8n Business Automation

## Goal
Deploy n8n and create core workflow templates.

## DONE WHEN
- [ ] n8n accessible at auto.vps1.ocoron.com
- [ ] Admin credentials secured
- [ ] Backup workflow: scheduled DB backup → notify
- [ ] Alert workflow: Uptime Kuma → Slack
- [ ] Example content workflow template
- [ ] Webhook endpoint documented
- [ ] Integration with Apprise for notifications

## Out of Scope
- Project-specific workflows (triggered-content, ComplianceOps)
- Complex multi-step pipelines

## Service Deployment

### n8n
- Image: n8nio/n8n:latest
- Port: 5678
- Domain: auto.vps1.ocoron.com
- Volume: n8n-data:/home/node/.n8n
- Env:
  - N8N_BASIC_AUTH_ACTIVE=true
  - N8N_BASIC_AUTH_USER
  - N8N_BASIC_AUTH_PASSWORD
  - N8N_HOST=auto.vps1.ocoron.com
  - N8N_PROTOCOL=https
  - WEBHOOK_URL=https://auto.vps1.ocoron.com
  - GENERIC_TIMEZONE=UTC

## Spec File

```yaml
# /opt/fabrik/specs/infrastructure/n8n.yaml
name: n8n
type: docker
domain: auto.vps1.ocoron.com
image: n8nio/n8n:latest
environment:
  N8N_BASIC_AUTH_ACTIVE: "true"
  N8N_BASIC_AUTH_USER: ${N8N_USER}
  N8N_BASIC_AUTH_PASSWORD: ${N8N_PASSWORD}
  N8N_HOST: auto.vps1.ocoron.com
  N8N_PROTOCOL: https
  WEBHOOK_URL: https://auto.vps1.ocoron.com
  GENERIC_TIMEZONE: UTC
volumes:
  - n8n-data:/home/node/.n8n
ports:
  - 5678:5678
healthcheck:
  path: /healthz
```

## Workflows to Create

### 1. System Backup Notification
```
Trigger: Cron (daily 3am)
    ↓
HTTP Request → Check backup status API
    ↓
IF success → Apprise → "Backup complete"
IF failure → Apprise → "ALERT: Backup failed"
```

### 2. Uptime Alert Pipeline
```
Trigger: Webhook (from Uptime Kuma)
    ↓
Switch on status
    ↓
DOWN → Apprise → Slack/Email alert
UP → Apprise → Recovery notification
```

### 3. Webhook Test Endpoint
```
Trigger: Webhook
    ↓
Respond with JSON: {"received": true, "timestamp": now}
```

## Steps

1. Verify ARM64 support:
   ```bash
   python scripts/container_images.py check-arch n8nio/n8n:latest
   ```

2. Create spec: /opt/fabrik/specs/infrastructure/n8n.yaml

3. Generate credentials:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(24))"
   ```

4. Add to /opt/fabrik/.env:
   - N8N_USER
   - N8N_PASSWORD

5. Deploy via Coolify

6. Access n8n UI, create workflows

7. Export workflows to /opt/fabrik/configs/n8n/workflows/

8. Document webhook endpoints

9. Update PORTS.md, SERVICES.md, CHANGELOG.md

## Reference Files
- /opt/fabrik/docs/development/plans/previously-planned-fabrik-phases/Phase8.md

## Constraints
- n8n MUST be password protected
- Webhook URLs must use HTTPS
- Export all workflows as JSON for version control
```

**Estimated time:** 4-6 hours

---

## Execution Schedule

### Day 1 (Saturday)

| Time | Track A (Phase 9) | Track B (Phase 6) | Track C (Phase 3) | Track D (Phase 8) |
|------|-------------------|-------------------|-------------------|-------------------|
| Morning | ARM64 checks, create specs | Create configs | Build LLMClient | ARM64 check, deploy |
| Afternoon | Deploy services | Deploy stack | Add CLI commands | Create workflows |
| Evening | Verify health | Configure Grafana | Usage tracking | Export workflows |

### Day 2 (Sunday)

| Time | Track A | Track B | Track C | Track D |
|------|---------|---------|---------|---------|
| Morning | Fix issues, docs | Create dashboards | Tests, docs | Test webhooks |
| Afternoon | Integration test | Alert rules | Integration | Integration |
| Evening | Final verification | Final verification | Final verification | Final verification |

---

## Dependencies

```
Phase 9 (Apprise) ←── Phase 6 (alerting)
                 ←── Phase 8 (notifications)

No blocking dependencies between tracks - can run in parallel.
```

---

## Verification Checklist

### Phase 9 ✅
```bash
curl -sf https://browser.vps1.ocoron.com/
curl -sf https://pdf.vps1.ocoron.com/health
curl -sf https://s3.vps1.ocoron.com/minio/health/live
curl -sf https://notify.vps1.ocoron.com/
curl -sf https://search.vps1.ocoron.com/health
```

### Phase 6 ✅
```bash
curl -sf https://monitor.vps1.ocoron.com/api/health
# Login to Grafana, verify dashboards
fabrik logs youtube --tail 10
```

### Phase 3 ✅
```bash
fabrik ai generate "Write a test paragraph"
fabrik ai usage
python -c "from fabrik.ai import LLMClient; print(LLMClient)"
```

### Phase 8 ✅
```bash
curl -sf https://auto.vps1.ocoron.com/healthz
# Login to n8n, verify workflows active
curl -X POST https://auto.vps1.ocoron.com/webhook-test/test
```

---

## Rollback Plan

If any phase fails:
1. Document the failure point
2. Continue with other tracks
3. Revisit failed phase after weekend

Each phase is independent - partial completion is acceptable.
