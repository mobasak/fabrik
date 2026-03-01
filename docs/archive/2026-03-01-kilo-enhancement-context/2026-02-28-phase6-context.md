# Phase 6: Deploy Monitoring Stack

## Goal
Deploy Loki/Promtail/Prometheus/Grafana monitoring stack to VPS1.

## DONE WHEN
- [ ] Loki running (internal, port 3100)
- [ ] Promtail shipping container logs to Loki
- [ ] Prometheus scraping metrics (internal, port 9090)
- [ ] Node Exporter providing system metrics
- [ ] cAdvisor providing container metrics
- [ ] Grafana accessible at monitor.vps1.ocoron.com
- [ ] System dashboard created (CPU, memory, disk)
- [ ] Container dashboard created
- [ ] Alert rules configured → Apprise → Slack
- [ ] CLI commands: fabrik logs <service>
- [ ] PORTS.md updated
- [ ] SERVICES.md updated
- [ ] CHANGELOG.md updated

## Out of Scope
- Custom application dashboards (trading-core, youtube)
- Complex alerting pipelines

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
- Port: 3100 (internal only)
- Volume: loki-data:/loki

### 2. Promtail (Log shipper)
- Image: grafana/promtail:2.9.0
- Mounts: /var/log, /var/lib/docker/containers

### 3. Prometheus (Metrics)
- Image: prom/prometheus:v2.47.0
- Port: 9090 (internal only)
- Volume: prometheus-data:/prometheus

### 4. Node Exporter (System metrics)
- Image: prom/node-exporter:v1.6.1
- Port: 9100 (internal only)

### 5. cAdvisor (Container metrics)
- Image: gcr.io/cadvisor/cadvisor:v0.47.0
- Port: 8080 (internal only)
- Mounts: /var/run/docker.sock, /sys, /var/lib/docker

### 6. Grafana (Dashboards)
- Image: grafana/grafana:10.1.0
- Port: 3002
- Domain: monitor.vps1.ocoron.com
- Volume: grafana-data:/var/lib/grafana

## Execution Steps

### Step 1: Verify ARM64 Support
```bash
cd /opt/fabrik && source .venv/bin/activate
python scripts/container_images.py check-arch grafana/loki:2.9.0
python scripts/container_images.py check-arch grafana/promtail:2.9.0
python scripts/container_images.py check-arch prom/prometheus:v2.47.0
python scripts/container_images.py check-arch prom/node-exporter:v1.6.1
python scripts/container_images.py check-arch gcr.io/cadvisor/cadvisor:v0.47.0
python scripts/container_images.py check-arch grafana/grafana:10.1.0
```

### Step 2: Create Config Directories
```bash
mkdir -p /opt/fabrik/configs/{loki,promtail,prometheus,grafana}
```

### Step 3: Create Loki Config
File: `/opt/fabrik/configs/loki/loki-config.yaml`
```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096

common:
  instance_addr: 127.0.0.1
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
        max_size_mb: 100

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

ruler:
  alertmanager_url: http://localhost:9093

limits_config:
  retention_period: 168h  # 7 days
```

### Step 4: Create Promtail Config
File: `/opt/fabrik/configs/promtail/promtail-config.yaml`
```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: containers
    static_configs:
      - targets:
          - localhost
        labels:
          job: containerlogs
          __path__: /var/lib/docker/containers/*/*log

    pipeline_stages:
      - json:
          expressions:
            output: log
            stream: stream
            attrs:
      - json:
          expressions:
            tag:
          source: attrs
      - regex:
          expression: (?P<container_name>(?:[a-zA-Z0-9][a-zA-Z0-9_.-]+))
          source: tag
      - labels:
          container_name:
          stream:
      - output:
          source: output
```

### Step 5: Create Prometheus Config
File: `/opt/fabrik/configs/prometheus/prometheus.yml`
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files: []

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: 'loki'
    static_configs:
      - targets: ['loki:3100']
```

### Step 6: Create Docker Compose Stack
File: `/opt/fabrik/specs/infrastructure/monitoring-stack.yaml`
```yaml
version: "3.8"

services:
  loki:
    image: grafana/loki:2.9.0
    container_name: loki
    ports:
      - "3100:3100"
    volumes:
      - /opt/fabrik/configs/loki:/etc/loki
      - loki-data:/loki
    command: -config.file=/etc/loki/loki-config.yaml
    networks:
      - coolify
    restart: unless-stopped

  promtail:
    image: grafana/promtail:2.9.0
    container_name: promtail
    volumes:
      - /opt/fabrik/configs/promtail:/etc/promtail
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    command: -config.file=/etc/promtail/promtail-config.yaml
    networks:
      - coolify
    restart: unless-stopped
    depends_on:
      - loki

  prometheus:
    image: prom/prometheus:v2.47.0
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - /opt/fabrik/configs/prometheus:/etc/prometheus
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'
    networks:
      - coolify
    restart: unless-stopped

  node-exporter:
    image: prom/node-exporter:v1.6.1
    container_name: node-exporter
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--path.rootfs=/rootfs'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    networks:
      - coolify
    restart: unless-stopped

  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.0
    container_name: cadvisor
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    privileged: true
    networks:
      - coolify
    restart: unless-stopped

  grafana:
    image: grafana/grafana:10.1.0
    container_name: grafana
    ports:
      - "3002:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana-data:/var/lib/grafana
    networks:
      - coolify
    restart: unless-stopped
    depends_on:
      - loki
      - prometheus

volumes:
  loki-data:
  prometheus-data:
  grafana-data:

networks:
  coolify:
    external: true
```

### Step 7: Generate Grafana Password
```bash
python -c "import secrets; print(f'GRAFANA_ADMIN_PASSWORD={secrets.token_urlsafe(24)}')"
```
Add to /opt/fabrik/.env

### Step 8: Deploy via Coolify

### Step 9: Configure Grafana Data Sources
After deployment, in Grafana UI:
1. Add Loki data source: `http://loki:3100`
2. Add Prometheus data source: `http://prometheus:9090`

### Step 10: Import Dashboards
- Node Exporter Full: Dashboard ID 1860
- Docker Containers: Dashboard ID 893

### Step 11: Create Alert Rules
In Grafana, create alerts for:
- Container restart > 3 in 5 min
- CPU > 90% for 5 min
- Disk > 85%
- Memory > 90%

Configure notification channel → Apprise (notify.vps1.ocoron.com)

### Step 12: Add CLI Commands
Add to `/opt/fabrik/src/fabrik/cli.py`:

```python
@cli.command()
@click.argument("service")
@click.option("--tail", "-n", default=100, help="Number of lines")
@click.option("--since", default="1h", help="Time range (1h, 24h, 7d)")
def logs(service: str, tail: int, since: str):
    """View logs for a service from Loki."""
    import httpx

    loki_url = os.getenv("LOKI_URL", "http://localhost:3100")
    query = f'{{container_name=~".*{service}.*"}}'

    response = httpx.get(
        f"{loki_url}/loki/api/v1/query_range",
        params={
            "query": query,
            "limit": tail,
            "since": since,
        }
    )

    if response.status_code == 200:
        data = response.json()
        for result in data.get("data", {}).get("result", []):
            for value in result.get("values", []):
                click.echo(value[1])
    else:
        click.echo(f"Error: {response.status_code}")
```

### Step 13: Update Documentation
- PORTS.md - Add monitoring ports
- docs/SERVICES.md - Add monitoring services
- CHANGELOG.md - Add Phase 6 entry

## Reference Files
- /opt/fabrik/docs/development/plans/previously-planned-fabrik-phases/Phase6.md

## Constraints
- All images MUST support linux/arm64
- Grafana MUST be password protected
- Logs retention: 7 days
- Metrics retention: 15 days
- Follow 9-step workflow
