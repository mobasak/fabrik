## Phase 6: Advanced Monitoring — Complete Narrative

**Status: 🟡 Partially Started**

---

### Progress Tracker

| Step | Task | Status |
|------|------|--------|
| 1 | Basic uptime monitoring | ✅ Done (Uptime Kuma) |
| 2 | Loki log aggregation | ❌ Pending |
| 3 | Promtail agent | ❌ Pending |
| 4 | Prometheus metrics | ❌ Pending |
| 5 | Node Exporter | ❌ Pending |
| 6 | cAdvisor | ❌ Pending |
| 7 | Grafana dashboards | ❌ Pending |
| 8 | Alerting (Slack/email) | ❌ Pending |
| 9 | CLI log commands | ❌ Pending |

**Completion: 1/9 tasks (11%)**

---

### What We're Building in Phase 6

By the end of Phase 6, you will have:

1. **Loki** for centralized log aggregation from all containers
2. **Promtail** agent shipping logs to Loki
3. **Prometheus** collecting metrics from containers and services
4. **Node Exporter** for VPS system metrics (CPU, memory, disk)
5. **cAdvisor** for container-level metrics
6. **Grafana** for visualization dashboards
7. **Pre-built dashboards** for system, containers, WordPress, and APIs
8. **Alerting** via Slack/email when issues occur
9. **CLI commands** for quick log access and metrics queries

This transforms Fabrik from "deploy and hope" to "full visibility into everything running."

---

### Why Advanced Monitoring?

**Current State (Uptime Kuma only):**
- Know if site is up or down
- No visibility into why things fail
- No historical data for debugging
- No performance trends
- Reactive troubleshooting

**With Full Monitoring Stack:**
- See logs from all containers in one place
- Query logs by time, service, error level
- Track CPU/memory/disk trends
- Identify slow queries and bottlenecks
- Get alerted before users notice problems
- Debug issues with historical context

---

### Prerequisites

Before starting Phase 6, confirm:

```
[ ] Phase 1-5 complete
[ ] VPS has at least 1GB free RAM for monitoring stack
[ ] At least 10GB free disk space for log/metric storage
[ ] Coolify running and accessible
[ ] Domain available for Grafana (e.g., monitor.yourdomain.com)
```

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  YOUR APPLICATIONS                                              │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │WordPress │  │  API 1   │  │  API 2   │  │ Workers  │        │
│  │  Site 1  │  │          │  │          │  │          │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
│       └─────────────┴──────┬──────┴─────────────┘               │
│                            │                                    │
│                       Docker Logs                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  MONITORING STACK                                               │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Promtail (Log Shipper)                                 │    │
│  │  • Reads Docker container logs                          │    │
│  │  • Adds labels (container, service, level)              │    │
│  │  • Ships to Loki                                        │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                   │
│                             ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Loki (Log Storage)                                     │    │
│  │  • Indexes logs by labels                               │    │
│  │  • Stores compressed log data                           │    │
│  │  • Queryable via LogQL                                  │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                   │
│                             ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Grafana (Visualization)                                │    │
│  │  • Dashboards for logs and metrics                      │    │
│  │  • Alerting rules                                       │    │
│  │  • Query interface                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             ▲                                   │
│                             │                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Prometheus (Metrics Storage)                           │    │
│  │  • Scrapes metrics from exporters                       │    │
│  │  • Stores time-series data                              │    │
│  │  • Queryable via PromQL                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                             ▲                                   │
│              ┌──────────────┼──────────────┐                    │
│              │              │              │                    │
│  ┌───────────┴───┐  ┌───────┴───────┐  ┌───┴───────────┐       │
│  │ Node Exporter │  │   cAdvisor    │  │ App Metrics   │       │
│  │ (System)      │  │ (Containers)  │  │ (Custom)      │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 1: Deploy Loki

**Why:** Loki is the log aggregation system. It stores logs efficiently and makes them searchable.

**Create spec:**

```yaml
# specs/loki/spec.yaml

id: loki
kind: service
template: null
environment: production

domain: null  # Internal only, accessed via Grafana

source:
  type: docker
  image: grafana/loki:2.9.0

expose:
  http: false
  internal_only: true

env:
  # Loki config is via file, not env vars

resources:
  memory: 512M
  cpu: "0.5"

storage:
  - name: data
    path: /loki
    backup: false  # Logs are ephemeral, don't need backup

health:
  path: /ready
  interval: 30s
```

**Create Loki config:**

```yaml
# templates/monitoring/loki-config.yaml

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
  max_query_length: 721h
  max_query_parallelism: 32

chunk_store_config:
  max_look_back_period: 168h

table_manager:
  retention_deletes_enabled: true
  retention_period: 168h

analytics:
  reporting_enabled: false
```

**Deploy via Coolify:**

```bash
# Create compose file for Loki
cat > apps/loki/compose.yaml << 'EOF'
services:
  loki:
    image: grafana/loki:2.9.0
    command: -config.file=/etc/loki/local-config.yaml
    ports:
      - "3100:3100"
    volumes:
      - loki-data:/loki
      - ./loki-config.yaml:/etc/loki/local-config.yaml:ro
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    restart: unless-stopped
    networks:
      - monitoring

volumes:
  loki-data:

networks:
  monitoring:
    external: true
EOF

# Copy config
cp templates/monitoring/loki-config.yaml apps/loki/
```

**Deploy:**

```bash
# Create monitoring network first
ssh deploy@$VPS_IP 'docker network create monitoring || true'

# Deploy via Coolify or docker compose
fabrik apply loki
```

**Time:** 1 hour

---

### Step 2: Deploy Promtail

**Why:** Promtail is the log shipper. It reads Docker container logs and sends them to Loki.

**Create Promtail config:**

```yaml
# templates/monitoring/promtail-config.yaml

server:
  http_listen_port: 9080
  grpc_listen_port: 0

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  # Scrape Docker container logs
  - job_name: containers
    static_configs:
      - targets:
          - localhost
        labels:
          job: containerlogs
          __path__: /var/lib/docker/containers/*/*log

    pipeline_stages:
      # Parse Docker JSON log format
      - json:
          expressions:
            output: log
            stream: stream
            timestamp: time
            
      # Extract container name from path
      - regex:
          source: filename
          expression: '/var/lib/docker/containers/(?P<container_id>[^/]+)/.*'
          
      # Add container name label
      - labels:
          stream:
          container_id:
          
      # Use log content as the line
      - output:
          source: output

  # Scrape system logs
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: systemlogs
          __path__: /var/log/*.log
```

**Create compose file:**

```yaml
# apps/promtail/compose.yaml

services:
  promtail:
    image: grafana/promtail:2.9.0
    command: -config.file=/etc/promtail/config.yaml
    volumes:
      - ./promtail-config.yaml:/etc/promtail/config.yaml:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/log:/var/log:ro
      - promtail-positions:/tmp
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: '0.25'
    restart: unless-stopped
    networks:
      - monitoring

volumes:
  promtail-positions:

networks:
  monitoring:
    external: true
```

**Deploy:**

```bash
cp templates/monitoring/promtail-config.yaml apps/promtail/
fabrik apply promtail
```

**Time:** 30 minutes

---

### Step 3: Deploy Prometheus

**Why:** Prometheus collects and stores metrics. It scrapes exporters at regular intervals.

**Create Prometheus config:**

```yaml
# templates/monitoring/prometheus-config.yaml

global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files: []

scrape_configs:
  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Node Exporter (system metrics)
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  # cAdvisor (container metrics)
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  # Traefik metrics (if enabled)
  - job_name: 'traefik'
    static_configs:
      - targets: ['traefik:8082']

  # Custom application metrics
  # Add your apps here as they expose /metrics endpoints
  # - job_name: 'my-api'
  #   static_configs:
  #     - targets: ['my-api:8000']
```

**Create compose file:**

```yaml
# apps/prometheus/compose.yaml

services:
  prometheus:
    image: prom/prometheus:v2.47.0
    command:
      - '--config.file=/etc/prometheus/prometheus.yaml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=15d'
      - '--web.enable-lifecycle'
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus-config.yaml:/etc/prometheus/prometheus.yaml:ro
      - prometheus-data:/prometheus
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    restart: unless-stopped
    networks:
      - monitoring

volumes:
  prometheus-data:

networks:
  monitoring:
    external: true
```

**Deploy:**

```bash
cp templates/monitoring/prometheus-config.yaml apps/prometheus/
fabrik apply prometheus
```

**Time:** 30 minutes

---

### Step 4: Deploy Node Exporter

**Why:** Node Exporter provides system-level metrics — CPU, memory, disk, network.

**Create compose file:**

```yaml
# apps/node-exporter/compose.yaml

services:
  node-exporter:
    image: prom/node-exporter:v1.6.1
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    deploy:
      resources:
        limits:
          memory: 64M
          cpus: '0.1'
    restart: unless-stopped
    networks:
      - monitoring

networks:
  monitoring:
    external: true
```

**Deploy:**

```bash
fabrik apply node-exporter
```

**Time:** 15 minutes

---

### Step 5: Deploy cAdvisor

**Why:** cAdvisor provides container-level metrics — per-container CPU, memory, network, disk I/O.

**Create compose file:**

```yaml
# apps/cadvisor/compose.yaml

services:
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.47.2
    privileged: true
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk:ro
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.25'
    restart: unless-stopped
    networks:
      - monitoring

networks:
  monitoring:
    external: true
```

**Deploy:**

```bash
fabrik apply cadvisor
```

**Time:** 15 minutes

---

### Step 6: Deploy Grafana

**Why:** Grafana is the visualization layer. It connects to Loki and Prometheus to display dashboards.

**Create spec:**

```yaml
# specs/grafana/spec.yaml

id: grafana
kind: service
template: null
environment: production

domain: monitor.yourdomain.com

source:
  type: docker
  image: grafana/grafana:10.2.0

expose:
  http: true
  internal_only: false

env:
  GF_SECURITY_ADMIN_USER: admin
  GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
  GF_USERS_ALLOW_SIGN_UP: "false"
  GF_SERVER_ROOT_URL: https://monitor.yourdomain.com
  GF_INSTALL_PLUGINS: grafana-clock-panel,grafana-simple-json-datasource

resources:
  memory: 256M
  cpu: "0.5"

storage:
  - name: data
    path: /var/lib/grafana
    backup: true

dns:
  provider: cloudflare
  zone_id: ${CF_ZONE_YOURDOMAIN}
  proxy: true
  records:
    - type: A
      name: monitor
      content: ${VPS_IP}
      proxied: true
```

**Create compose file:**

```yaml
# apps/grafana/compose.yaml

services:
  grafana:
    image: grafana/grafana:10.2.0
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=https://monitor.yourdomain.com
      - GF_INSTALL_PLUGINS=grafana-clock-panel,grafana-simple-json-datasource
    volumes:
      - grafana-data:/var/lib/grafana
      - ./provisioning:/etc/grafana/provisioning:ro
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
    restart: unless-stopped
    networks:
      - monitoring
      - proxy  # For Traefik

volumes:
  grafana-data:

networks:
  monitoring:
    external: true
  proxy:
    external: true
```

**Create Grafana provisioning for data sources:**

```yaml
# apps/grafana/provisioning/datasources/datasources.yaml

apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false
    jsonData:
      maxLines: 1000
```

**Deploy:**

```bash
# Generate admin password
GRAFANA_PASSWORD=$(openssl rand -base64 24)
echo "GRAFANA_ADMIN_PASSWORD=$GRAFANA_PASSWORD" >> secrets/platform.env
echo "Grafana admin password: $GRAFANA_PASSWORD"

# Create provisioning directory
mkdir -p apps/grafana/provisioning/datasources
cp templates/monitoring/datasources.yaml apps/grafana/provisioning/datasources/

# Deploy
fabrik apply grafana
```

**Time:** 1 hour

---

### Step 7: Create System Dashboard

**Why:** Pre-built dashboard for VPS health — CPU, memory, disk, network.

**Create dashboard JSON:**

```json
// apps/grafana/provisioning/dashboards/system.json

{
  "annotations": {
    "list": []
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 70
              },
              {
                "color": "red",
                "value": 90
              }
            ]
          },
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "legend": {
          "calcs": ["mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "100 - (avg by(instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
          "legendFormat": "CPU Usage",
          "refId": "A"
        }
      ],
      "title": "CPU Usage",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 70
              },
              {
                "color": "red",
                "value": 90
              }
            ]
          },
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 0
      },
      "id": 2,
      "options": {
        "legend": {
          "calcs": ["mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
          "legendFormat": "Memory Usage",
          "refId": "A"
        }
      ],
      "title": "Memory Usage",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "max": 100,
          "min": 0,
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "yellow",
                "value": 70
              },
              {
                "color": "red",
                "value": 90
              }
            ]
          },
          "unit": "percent"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 8
      },
      "id": 3,
      "options": {
        "legend": {
          "calcs": ["mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "(1 - (node_filesystem_avail_bytes{mountpoint=\"/\"} / node_filesystem_size_bytes{mountpoint=\"/\"})) * 100",
          "legendFormat": "Disk Usage",
          "refId": "A"
        }
      ],
      "title": "Disk Usage",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          },
          "unit": "binBps"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 8
      },
      "id": 4,
      "options": {
        "legend": {
          "calcs": ["mean", "max"],
          "displayMode": "table",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(node_network_receive_bytes_total{device!=\"lo\"}[5m])",
          "legendFormat": "Receive {{ device }}",
          "refId": "A"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(node_network_transmit_bytes_total{device!=\"lo\"}[5m])",
          "legendFormat": "Transmit {{ device }}",
          "refId": "B"
        }
      ],
      "title": "Network I/O",
      "type": "timeseries"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["system", "node"],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "System Overview",
  "uid": "system-overview",
  "version": 1,
  "weekStart": ""
}
```

**Create dashboard provisioning:**

```yaml
# apps/grafana/provisioning/dashboards/dashboards.yaml

apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    folderUid: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

**Time:** 2 hours

---

### Step 8: Create Container Dashboard

**Why:** See resource usage per container — identify which services consume the most resources.

**Create dashboard JSON:**

```python
# compiler/monitoring/dashboards.py

import json
from pathlib import Path

def create_container_dashboard() -> dict:
    """Create cAdvisor-based container metrics dashboard."""
    
    return {
        "title": "Container Metrics",
        "uid": "container-metrics",
        "tags": ["containers", "docker"],
        "timezone": "",
        "schemaVersion": 38,
        "refresh": "30s",
        "time": {"from": "now-1h", "to": "now"},
        "panels": [
            {
                "id": 1,
                "title": "Container CPU Usage",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": 'rate(container_cpu_usage_seconds_total{name!=""}[5m]) * 100',
                        "legendFormat": "{{ name }}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percent",
                        "min": 0
                    }
                }
            },
            {
                "id": 2,
                "title": "Container Memory Usage",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": 'container_memory_usage_bytes{name!=""}',
                        "legendFormat": "{{ name }}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "bytes",
                        "min": 0
                    }
                }
            },
            {
                "id": 3,
                "title": "Container Network Receive",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": 'rate(container_network_receive_bytes_total{name!=""}[5m])',
                        "legendFormat": "{{ name }}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "binBps",
                        "min": 0
                    }
                }
            },
            {
                "id": 4,
                "title": "Container Network Transmit",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": 'rate(container_network_transmit_bytes_total{name!=""}[5m])',
                        "legendFormat": "{{ name }}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "binBps",
                        "min": 0
                    }
                }
            },
            {
                "id": 5,
                "title": "Container Count",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 16},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": 'count(container_last_seen{name!=""})',
                        "refId": "A"
                    }
                ]
            },
            {
                "id": 6,
                "title": "Total Container Memory",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 6, "y": 16},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": 'sum(container_memory_usage_bytes{name!=""})',
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "bytes"
                    }
                }
            }
        ]
    }

def create_logs_dashboard() -> dict:
    """Create Loki-based logs dashboard."""
    
    return {
        "title": "Application Logs",
        "uid": "app-logs",
        "tags": ["logs", "loki"],
        "timezone": "",
        "schemaVersion": 38,
        "refresh": "10s",
        "time": {"from": "now-1h", "to": "now"},
        "templating": {
            "list": [
                {
                    "name": "container",
                    "type": "query",
                    "datasource": {"type": "loki", "uid": "loki"},
                    "query": 'label_values(container)',
                    "refresh": 2,
                    "includeAll": True,
                    "multi": True
                },
                {
                    "name": "search",
                    "type": "textbox",
                    "current": {"value": ""}
                }
            ]
        },
        "panels": [
            {
                "id": 1,
                "title": "Log Stream",
                "type": "logs",
                "gridPos": {"h": 20, "w": 24, "x": 0, "y": 0},
                "datasource": {"type": "loki", "uid": "loki"},
                "targets": [
                    {
                        "expr": '{job="containerlogs"} |~ "$search"',
                        "refId": "A"
                    }
                ],
                "options": {
                    "showTime": True,
                    "showLabels": True,
                    "showCommonLabels": False,
                    "wrapLogMessage": True,
                    "prettifyLogMessage": False,
                    "enableLogDetails": True,
                    "dedupStrategy": "none",
                    "sortOrder": "Descending"
                }
            },
            {
                "id": 2,
                "title": "Error Rate",
                "type": "timeseries",
                "gridPos": {"h": 6, "w": 12, "x": 0, "y": 20},
                "datasource": {"type": "loki", "uid": "loki"},
                "targets": [
                    {
                        "expr": 'sum(rate({job="containerlogs"} |= "error" [5m]))',
                        "legendFormat": "Errors/s",
                        "refId": "A"
                    }
                ]
            },
            {
                "id": 3,
                "title": "Log Volume",
                "type": "timeseries",
                "gridPos": {"h": 6, "w": 12, "x": 12, "y": 20},
                "datasource": {"type": "loki", "uid": "loki"},
                "targets": [
                    {
                        "expr": 'sum(rate({job="containerlogs"}[5m])) by (container)',
                        "legendFormat": "{{ container }}",
                        "refId": "A"
                    }
                ]
            }
        ]
    }

def save_dashboard(dashboard: dict, path: str):
    """Save dashboard to JSON file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(dashboard, f, indent=2)

def generate_all_dashboards(output_dir: str = "apps/grafana/provisioning/dashboards"):
    """Generate all dashboard JSON files."""
    
    dashboards = {
        'containers.json': create_container_dashboard(),
        'logs.json': create_logs_dashboard(),
    }
    
    for filename, dashboard in dashboards.items():
        save_dashboard(dashboard, f"{output_dir}/{filename}")
        print(f"Created: {output_dir}/{filename}")
```

**Generate dashboards:**

```bash
python3 -c "
from compiler.monitoring.dashboards import generate_all_dashboards
generate_all_dashboards()
"
```

**Time:** 2 hours

---

### Step 9: Configure Alerting

**Why:** Get notified when things go wrong — before users notice.

**Create alert rules:**

```yaml
# apps/grafana/provisioning/alerting/alerts.yaml

apiVersion: 1

groups:
  - orgId: 1
    name: System Alerts
    folder: alerts
    interval: 1m
    rules:
      - uid: high-cpu
        title: High CPU Usage
        condition: A
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)
              refId: A
        execErrState: Error
        noDataState: NoData
        for: 5m
        annotations:
          summary: CPU usage is above 90%
          description: "CPU usage has been above 90% for 5 minutes"
        labels:
          severity: warning
        isPaused: false

      - uid: high-memory
        title: High Memory Usage
        condition: A
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100
              refId: A
        execErrState: Error
        noDataState: NoData
        for: 5m
        annotations:
          summary: Memory usage is above 90%
          description: "Memory usage has been above 90% for 5 minutes"
        labels:
          severity: warning
        isPaused: false

      - uid: high-disk
        title: High Disk Usage
        condition: A
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: (1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100
              refId: A
        execErrState: Error
        noDataState: NoData
        for: 5m
        annotations:
          summary: Disk usage is above 80%
          description: "Disk usage has been above 80% for 5 minutes"
        labels:
          severity: warning
        isPaused: false

      - uid: container-down
        title: Container Down
        condition: A
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: absent(container_last_seen{name=~".+"})
              refId: A
        execErrState: Error
        noDataState: NoData
        for: 2m
        annotations:
          summary: Container is not responding
          description: "A container has not been seen for 2 minutes"
        labels:
          severity: critical
        isPaused: false
```

**Configure notification channels:**

```yaml
# apps/grafana/provisioning/alerting/notifiers.yaml

apiVersion: 1

notifiers:
  - name: Slack
    type: slack
    uid: slack-notifier
    org_id: 1
    is_default: true
    send_reminder: true
    frequency: 1h
    disable_resolve_message: false
    settings:
      url: ${SLACK_WEBHOOK_URL}
      username: Fabrik Monitor
      icon_emoji: ":warning:"
      
  - name: Email
    type: email
    uid: email-notifier
    org_id: 1
    is_default: false
    settings:
      addresses: ${ALERT_EMAIL}
```

**Configure contact points (Grafana 9+):**

```yaml
# apps/grafana/provisioning/alerting/contactpoints.yaml

apiVersion: 1

contactPoints:
  - orgId: 1
    name: slack-alerts
    receivers:
      - uid: slack-receiver
        type: slack
        settings:
          url: ${SLACK_WEBHOOK_URL}
          username: Fabrik Monitor
          title: |
            {{ if gt (len .Alerts.Firing) 0 }}🔴 {{ len .Alerts.Firing }} Firing{{ end }}
            {{ if gt (len .Alerts.Resolved) 0 }}✅ {{ len .Alerts.Resolved }} Resolved{{ end }}
          text: |
            {{ range .Alerts }}
            *{{ .Labels.alertname }}*
            {{ .Annotations.summary }}
            {{ .Annotations.description }}
            {{ end }}
```

**Time:** 1 hour

---

### Step 10: CLI Commands for Monitoring

**Why:** Quick access to logs and metrics from the command line.

**Code:**

```python
# cli/monitor.py

import click
import os
from pathlib import Path
from datetime import datetime, timedelta
import httpx

def load_env():
    """Load environment."""
    env_file = Path("secrets/platform.env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    k, v = line.strip().split('=', 1)
                    os.environ[k] = v

@click.group()
def monitor():
    """Monitoring and logs commands."""
    load_env()

# ─────────────────────────────────────────────────────────────
# Logs
# ─────────────────────────────────────────────────────────────

@monitor.command('logs')
@click.argument('query', default='')
@click.option('--container', '-c', help='Filter by container name')
@click.option('--since', '-s', default='1h', help='Time range (e.g., 1h, 30m, 24h)')
@click.option('--limit', '-n', default=100, help='Max lines to return')
@click.option('--level', '-l', type=click.Choice(['error', 'warn', 'info', 'debug']), 
              help='Filter by log level')
def logs(query, container, since, limit, level):
    """Query logs from Loki."""
    
    loki_url = os.environ.get('LOKI_URL', 'http://localhost:3100')
    
    # Build LogQL query
    label_selectors = ['job="containerlogs"']
    
    if container:
        label_selectors.append(f'container=~".*{container}.*"')
    
    logql = '{' + ','.join(label_selectors) + '}'
    
    # Add line filters
    if level:
        level_filters = {
            'error': '|~ "(?i)error|exception|fatal"',
            'warn': '|~ "(?i)warn|warning"',
            'info': '|~ "(?i)info"',
            'debug': '|~ "(?i)debug"'
        }
        logql += f' {level_filters[level]}'
    
    if query:
        logql += f' |~ "{query}"'
    
    # Parse time range
    now = datetime.utcnow()
    
    time_units = {'m': 'minutes', 'h': 'hours', 'd': 'days'}
    unit = since[-1]
    value = int(since[:-1])
    
    if unit in time_units:
        delta = timedelta(**{time_units[unit]: value})
        start = now - delta
    else:
        start = now - timedelta(hours=1)
    
    # Query Loki
    params = {
        'query': logql,
        'start': int(start.timestamp() * 1e9),
        'end': int(now.timestamp() * 1e9),
        'limit': limit,
        'direction': 'backward'
    }
    
    try:
        resp = httpx.get(f'{loki_url}/loki/api/v1/query_range', params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        click.echo(f"Error querying Loki: {e}")
        raise click.Abort()
    
    # Display results
    results = data.get('data', {}).get('result', [])
    
    if not results:
        click.echo("No logs found matching query")
        return
    
    click.echo(f"\nLogs matching: {logql}")
    click.echo("-" * 80)
    
    for stream in results:
        labels = stream.get('stream', {})
        container_name = labels.get('container', labels.get('container_id', 'unknown')[:12])
        
        for ts, line in stream.get('values', []):
            # Parse timestamp
            ts_sec = int(ts) / 1e9
            time_str = datetime.fromtimestamp(ts_sec).strftime('%Y-%m-%d %H:%M:%S')
            
            # Truncate long lines
            if len(line) > 200:
                line = line[:200] + '...'
            
            click.echo(f"[{time_str}] [{container_name}] {line}")

@monitor.command('errors')
@click.option('--since', '-s', default='1h', help='Time range')
@click.option('--container', '-c', help='Filter by container')
def errors(since, container):
    """Show recent errors from all containers."""
    
    ctx = click.get_current_context()
    ctx.invoke(logs, query='', container=container, since=since, limit=50, level='error')

@monitor.command('tail')
@click.argument('container')
@click.option('--lines', '-n', default=50, help='Initial lines to show')
def tail(container, lines):
    """Tail logs from a specific container in real-time."""
    
    import subprocess
    
    vps_ip = os.environ.get('VPS_IP')
    ssh_user = os.environ.get('SSH_USER', 'deploy')
    
    # Find container
    find_cmd = f"ssh {ssh_user}@{vps_ip} 'docker ps --filter name={container} --format {{{{.Names}}}} | head -1'"
    result = subprocess.run(find_cmd, shell=True, capture_output=True, text=True)
    container_name = result.stdout.strip()
    
    if not container_name:
        click.echo(f"Container not found: {container}")
        raise click.Abort()
    
    click.echo(f"Tailing logs for: {container_name}")
    click.echo("-" * 60)
    
    # Stream logs
    tail_cmd = f"ssh {ssh_user}@{vps_ip} 'docker logs -f --tail {lines} {container_name}'"
    
    try:
        subprocess.run(tail_cmd, shell=True)
    except KeyboardInterrupt:
        click.echo("\nStopped tailing logs")

# ─────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────

@monitor.command('status')
def status():
    """Show current system status."""
    
    prometheus_url = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
    
    queries = {
        'CPU Usage': '100 - (avg(irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
        'Memory Usage': '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
        'Disk Usage': '(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100',
        'Containers': 'count(container_last_seen{name!=""})',
    }
    
    click.echo("\n" + "=" * 50)
    click.echo("  SYSTEM STATUS")
    click.echo("=" * 50)
    
    for name, query in queries.items():
        try:
            resp = httpx.get(
                f'{prometheus_url}/api/v1/query',
                params={'query': query},
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json()
            
            results = data.get('data', {}).get('result', [])
            if results:
                value = float(results[0]['value'][1])
                
                if 'Usage' in name:
                    # Show as percentage with color
                    if value > 90:
                        color = 'red'
                    elif value > 70:
                        color = 'yellow'
                    else:
                        color = 'green'
                    
                    click.echo(f"  {name:15} {click.style(f'{value:.1f}%', fg=color)}")
                else:
                    click.echo(f"  {name:15} {value:.0f}")
            else:
                click.echo(f"  {name:15} N/A")
                
        except Exception as e:
            click.echo(f"  {name:15} Error: {e}")
    
    click.echo("=" * 50 + "\n")

@monitor.command('containers')
def containers():
    """Show container resource usage."""
    
    prometheus_url = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
    
    # Get container CPU
    cpu_query = 'rate(container_cpu_usage_seconds_total{name!=""}[5m]) * 100'
    # Get container memory
    mem_query = 'container_memory_usage_bytes{name!=""}'
    
    try:
        cpu_resp = httpx.get(
            f'{prometheus_url}/api/v1/query',
            params={'query': cpu_query},
            timeout=10
        )
        cpu_data = cpu_resp.json().get('data', {}).get('result', [])
        
        mem_resp = httpx.get(
            f'{prometheus_url}/api/v1/query',
            params={'query': mem_query},
            timeout=10
        )
        mem_data = mem_resp.json().get('data', {}).get('result', [])
        
    except Exception as e:
        click.echo(f"Error querying Prometheus: {e}")
        raise click.Abort()
    
    # Combine data
    containers = {}
    
    for result in cpu_data:
        name = result['metric'].get('name', 'unknown')
        containers[name] = {'cpu': float(result['value'][1])}
    
    for result in mem_data:
        name = result['metric'].get('name', 'unknown')
        if name in containers:
            containers[name]['memory'] = float(result['value'][1])
        else:
            containers[name] = {'memory': float(result['value'][1]), 'cpu': 0}
    
    # Display
    click.echo("\n" + "=" * 70)
    click.echo(f"  {'CONTAINER':<30} {'CPU':>10} {'MEMORY':>15}")
    click.echo("=" * 70)
    
    for name, metrics in sorted(containers.items()):
        cpu = metrics.get('cpu', 0)
        mem = metrics.get('memory', 0)
        
        # Format memory
        if mem > 1024**3:
            mem_str = f"{mem/1024**3:.1f} GB"
        elif mem > 1024**2:
            mem_str = f"{mem/1024**2:.1f} MB"
        else:
            mem_str = f"{mem/1024:.1f} KB"
        
        click.echo(f"  {name:<30} {cpu:>9.1f}% {mem_str:>15}")
    
    click.echo("=" * 70 + "\n")

@monitor.command('alerts')
def alerts():
    """Show active alerts."""
    
    prometheus_url = os.environ.get('PROMETHEUS_URL', 'http://localhost:9090')
    
    try:
        resp = httpx.get(f'{prometheus_url}/api/v1/alerts', timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        click.echo(f"Error querying alerts: {e}")
        raise click.Abort()
    
    alerts_list = data.get('data', {}).get('alerts', [])
    
    if not alerts_list:
        click.echo("\n✓ No active alerts\n")
        return
    
    click.echo("\n" + "=" * 60)
    click.echo("  ACTIVE ALERTS")
    click.echo("=" * 60)
    
    for alert in alerts_list:
        state = alert.get('state', 'unknown')
        name = alert.get('labels', {}).get('alertname', 'unknown')
        severity = alert.get('labels', {}).get('severity', 'unknown')
        summary = alert.get('annotations', {}).get('summary', '')
        
        # Color by state
        if state == 'firing':
            state_color = 'red'
        elif state == 'pending':
            state_color = 'yellow'
        else:
            state_color = 'white'
        
        click.echo(f"\n  {click.style(state.upper(), fg=state_color)} - {name}")
        click.echo(f"  Severity: {severity}")
        click.echo(f"  {summary}")
    
    click.echo("\n" + "=" * 60 + "\n")

# ─────────────────────────────────────────────────────────────
# Dashboard Links
# ─────────────────────────────────────────────────────────────

@monitor.command('dashboard')
@click.option('--open', 'open_browser', is_flag=True, help='Open in browser')
def dashboard(open_browser):
    """Get Grafana dashboard URL."""
    
    grafana_url = os.environ.get('GRAFANA_URL', 'https://monitor.yourdomain.com')
    
    click.echo(f"\nGrafana Dashboard: {grafana_url}")
    click.echo(f"  System:     {grafana_url}/d/system-overview")
    click.echo(f"  Containers: {grafana_url}/d/container-metrics")
    click.echo(f"  Logs:       {grafana_url}/d/app-logs")
    
    if open_browser:
        import webbrowser
        webbrowser.open(grafana_url)

if __name__ == '__main__':
    monitor()
```

**Update main CLI:**

```python
# cli/main.py - add monitor commands

from cli.monitor import monitor

cli.add_command(monitor)
```

**Time:** 2 hours

---

### Step 11: WordPress-Specific Monitoring

**Why:** Monitor WordPress-specific metrics — response times, PHP errors, database queries.

**Add WordPress exporter (optional):**

```yaml
# If you want detailed WordPress metrics, deploy wp-exporter

# apps/wp-exporter/compose.yaml

services:
  wp-exporter:
    image: hipages/php-fpm_exporter:2
    ports:
      - "9253:9253"
    environment:
      - PHP_FPM_SCRAPE_URI=tcp://wordpress:9000/status
    networks:
      - monitoring
    restart: unless-stopped

networks:
  monitoring:
    external: true
```

**Create WordPress dashboard:**

```python
# compiler/monitoring/wordpress_dashboard.py

def create_wordpress_dashboard() -> dict:
    """Create WordPress-specific dashboard."""
    
    return {
        "title": "WordPress Sites",
        "uid": "wordpress-sites",
        "tags": ["wordpress", "sites"],
        "timezone": "",
        "schemaVersion": 38,
        "refresh": "30s",
        "time": {"from": "now-1h", "to": "now"},
        "panels": [
            {
                "id": 1,
                "title": "WordPress Error Logs",
                "type": "logs",
                "gridPos": {"h": 10, "w": 24, "x": 0, "y": 0},
                "datasource": {"type": "loki", "uid": "loki"},
                "targets": [
                    {
                        "expr": '{job="containerlogs"} |~ "(?i)php|wordpress" |~ "(?i)error|warning|fatal"',
                        "refId": "A"
                    }
                ],
                "options": {
                    "showTime": True,
                    "showLabels": True,
                    "wrapLogMessage": True,
                    "enableLogDetails": True,
                    "sortOrder": "Descending"
                }
            },
            {
                "id": 2,
                "title": "WordPress Container Memory",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 10},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": 'container_memory_usage_bytes{name=~".*wordpress.*|.*wp.*"}',
                        "legendFormat": "{{ name }}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "bytes",
                        "min": 0
                    }
                }
            },
            {
                "id": 3,
                "title": "WordPress Container CPU",
                "type": "timeseries",
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 10},
                "datasource": {"type": "prometheus", "uid": "prometheus"},
                "targets": [
                    {
                        "expr": 'rate(container_cpu_usage_seconds_total{name=~".*wordpress.*|.*wp.*"}[5m]) * 100',
                        "legendFormat": "{{ name }}",
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percent",
                        "min": 0
                    }
                }
            },
            {
                "id": 4,
                "title": "PHP Fatal Errors (last 24h)",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 18},
                "datasource": {"type": "loki", "uid": "loki"},
                "targets": [
                    {
                        "expr": 'count_over_time({job="containerlogs"} |~ "PHP Fatal" [24h])',
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 1},
                                {"color": "red", "value": 10}
                            ]
                        }
                    }
                }
            },
            {
                "id": 5,
                "title": "Database Errors (last 24h)",
                "type": "stat",
                "gridPos": {"h": 4, "w": 6, "x": 6, "y": 18},
                "datasource": {"type": "loki", "uid": "loki"},
                "targets": [
                    {
                        "expr": 'count_over_time({job="containerlogs"} |~ "(?i)mysql|database|wpdb" |~ "(?i)error" [24h])',
                        "refId": "A"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "thresholds": {
                            "mode": "absolute",
                            "steps": [
                                {"color": "green", "value": None},
                                {"color": "yellow", "value": 1},
                                {"color": "red", "value": 5}
                            ]
                        }
                    }
                }
            }
        ]
    }
```

**Time:** 1 hour

---

### Phase 6 Complete

After completing all steps, you have:

```
✓ Loki for log aggregation
✓ Promtail shipping container logs to Loki
✓ Prometheus collecting metrics
✓ Node Exporter for system metrics
✓ cAdvisor for container metrics
✓ Grafana for visualization
✓ Pre-built dashboards (System, Containers, Logs, WordPress)
✓ Alert rules for CPU, memory, disk, container health
✓ Slack/email notifications
✓ CLI commands for quick log/metric access
```

**New CLI commands:**

```bash
# Query logs
fabrik monitor logs "error"
fabrik monitor logs --container=wordpress --since=24h
fabrik monitor logs --level=error

# Show recent errors
fabrik monitor errors --since=1h

# Tail container logs
fabrik monitor tail wordpress

# System status
fabrik monitor status

# Container resource usage
fabrik monitor containers

# Active alerts
fabrik monitor alerts

# Get dashboard URLs
fabrik monitor dashboard --open
```

**Grafana Dashboards:**

```
https://monitor.yourdomain.com/d/system-overview     → CPU, Memory, Disk, Network
https://monitor.yourdomain.com/d/container-metrics   → Per-container resources
https://monitor.yourdomain.com/d/app-logs            → Searchable logs
https://monitor.yourdomain.com/d/wordpress-sites     → WordPress-specific
```

---

### Resource Requirements

| Component | Memory | CPU | Disk |
|-----------|--------|-----|------|
| Loki | 512 MB | 0.5 | 5 GB (logs) |
| Promtail | 128 MB | 0.25 | Minimal |
| Prometheus | 512 MB | 0.5 | 5 GB (metrics) |
| Node Exporter | 64 MB | 0.1 | Minimal |
| cAdvisor | 256 MB | 0.25 | Minimal |
| Grafana | 256 MB | 0.5 | 100 MB |
| **Total** | **~1.7 GB** | **~2.1** | **~10 GB** |

---

### Typical Workflow

```bash
# 1. Something's wrong with a site
# 2. Quick check system status
fabrik monitor status

# Output:
# ══════════════════════════════════════════════════
#   SYSTEM STATUS
# ══════════════════════════════════════════════════
#   CPU Usage       45.2%
#   Memory Usage    78.3%
#   Disk Usage      62.1%
#   Containers      12
# ══════════════════════════════════════════════════

# 3. Check container resources
fabrik monitor containers

# 4. Look at recent errors
fabrik monitor errors --since=1h

# 5. Search for specific error
fabrik monitor logs "database connection" --since=24h

# 6. Tail specific container
fabrik monitor tail client-site

# 7. Check Grafana for detailed analysis
fabrik monitor dashboard --open
```

---

### Phase 6 Summary

| Step | Task | Time |
|------|------|------|
| 1 | Deploy Loki | 1 hr |
| 2 | Deploy Promtail | 30 min |
| 3 | Deploy Prometheus | 30 min |
| 4 | Deploy Node Exporter | 15 min |
| 5 | Deploy cAdvisor | 15 min |
| 6 | Deploy Grafana | 1 hr |
| 7 | Create System Dashboard | 2 hrs |
| 8 | Create Container Dashboard | 2 hrs |
| 9 | Configure Alerting | 1 hr |
| 10 | CLI Commands | 2 hrs |
| 11 | WordPress Dashboard | 1 hr |

**Total: ~14 hours (2-3 days)**

---

### What's Next (Phase 7 Preview)

Phase 7 adds multi-server scaling:
- Add second VPS
- Distribute workloads
- Shared database access
- Load balancing considerations

---