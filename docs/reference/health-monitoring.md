# Health Monitoring

**Version:** 1.4.0
**Last Updated:** 2026-06-16 (monitoring stack stood up under Coolify 2026-04-17; the observability containers themselves still run but are no longer Coolify-managed post-2026-05 SSH+Compose migration — Coolify is now only a legacy Docker-network name. Verifier-key alignment fix [B23, Lesson 32] noted in `docs/reference/modules/deployment-orchestrator.md` (the `verifier.py` row) — this doc covers Fabrik's own `/health` endpoint and the observability stack, NOT the deploy verifier.)

---

## Monitoring Infrastructure Overview

### Stack Components

| Tool | Role | What it does |
|------|------|-------------|
| **node-exporter** | Host metrics exporter | Exposes CPU/RAM/disk/network host metrics for Prometheus to scrape (replaced Netdata, removed 2026-05-30). |
| **cAdvisor** | Container metrics exporter | Exposes per-container CPU/RAM/IO stats for Prometheus to scrape. |
| **Prometheus** | Metrics collector & storage | Scrapes metrics from node-exporter, cAdvisor, and apps/services and stores them as time-series data. Doesn't visualize — just collects and stores. |
| **Grafana** | Visualization layer | Connects to Prometheus and builds custom dashboards, alerts, and graphs. Best for "show me trends over the last 30 days." |
| **Loki** | Log aggregator | Collects logs from all containers/services into one searchable place. Prometheus but for logs instead of metrics. |
| **Promtail** | Log shipper | Reads Docker container logs and sends them to Loki. |
| **Gatus** | Uptime monitoring | External availability checks, status page, alerting. |

### Current Stack (Single VPS)

The full observability stack is deployed and operational. node-exporter + cAdvisor export host/container metrics to Prometheus (these replaced Netdata, removed 2026-05-30); Prometheus + Grafana handle alerting, dashboards, and long-term trend analysis; Loki + Promtail aggregate container logs.

**Live coverage (verified 2026-07-20, 3-host fleet):** Gatus = ~34 endpoints across 18 config files · Prometheus = 17 `job_name`s configured / 21 targets, 21 up (16 job_names carry real targets + the `pushgateway` job restored 2026-07-19; `fabrik-services` is a null placeholder with zero targets; the `aro-wake` job covers all 3 hosts) · 13 alert rules in 5 groups · Grafana 5 custom dashboards · Authelia 8 access-control rules.

> **Spoke coverage:** the two spoke hosts run `node-exporter` / `cadvisor` / `promtail` from `/opt/monitoring-agent/`, scraped by dedicated `node-spokes` / `cadvisor-spokes` / `promtail-spokes` jobs in `prometheus.yml` (targets `10.99.0.2/3` over the mesh), plus the `aro-wake` job (all 3 hosts) and push-based Loki log shipping.

**Pushgateway scrape (gap found + closed 2026-07-19):** `audit_all_registrars.py` pushes drift metrics to the `pushgateway` container hourly; the `pushgateway` scrape job (`honor_labels: true`) had drifted out of the live `prometheus.yml` — silently disabling `FabrikRegistrarDrift` — and is now restored in BOTH the repo mirror (`configs/prometheus/prometheus.yml`) and live vps1 (applied + SIGHUP 2026-07-19; verified: pushgateway target `up`, `fabrik_audit_drift_total` = 710 series in Prometheus).

### Deployed Services (Verified 2026-06-16)

| Service | URL | Status |
|---------|-----|--------|
| Gatus | status.vps1.ocoron.com | ✅ Running |
| Grafana | monitor.vps1.ocoron.com | ✅ Running |
| Prometheus | (internal :9090) | ✅ Running |
| Alertmanager | (internal :9093) | ✅ Running |
| Loki | (internal :3100) | ✅ Running |
| Promtail | (internal) | ✅ Running |
| cAdvisor | (internal :8080) | ✅ Running |
| node-exporter | (internal :9100) | ✅ Running |

**Compose file:** `/opt/monitoring/compose.yaml` (standalone Compose stack on vps1). Start/stop via `cd /opt/monitoring && sudo docker compose up -d` / `down`. (2026-04-17 → 2026-05-30 these services were Coolify-managed; reverted to standalone Compose on the 2026-05-30 SSH+Compose migration.)
**Local source:** `specs/infrastructure/monitoring-stack.yaml` + `configs/` in Fabrik (mirror; production state lives in `/opt/monitoring/` on vps1)

### Notification Chain

```
Prometheus (rules) → Alertmanager → Telegram (native telegram_configs)
```

> **Why not Apprise?** Apprise's stateless `/notify` endpoint expects `{body,title,type}`
> JSON and returns HTTP 400 on Alertmanager's native webhook schema. Alertmanager →
> Apprise is not a valid chain. Gatus → Apprise still works because Gatus posts the
> Apprise-compatible shape.
>
> **ARO Brain (planned):** LLM-based alert triage. When deployed, add as a primary
> receiver routed before `telegram`, with `telegram` as the fallback.

### Prometheus Alert Rules (13 total, 5 groups)

Source of truth: `configs/prometheus/rules/alerts.yml` (12 rules, 4 groups) + `configs/prometheus/rules/fabrik-drift.yml` (1 rule, group `fabrik-registrar-drift`). There are no Promtail/log-based alert rules.

| # | Alert | Group | Severity | Threshold | For |
| --- | --- | --- | --- | --- | --- |
| 1 | ContainerDown | container_health | critical | not seen >2min | 2m |
| 2 | ContainerHighCPU | container_health | warning | >80% | 5m |
| 3 | ContainerHighMemory | container_health | warning | >85% limit | 5m |
| 4 | ContainerMemoryHighOfHost | container_health | warning | high % of host RAM | 10m |
| 5 | ContainerOOMKilled | container_health | critical | any OOM in 5m | 0m |
| 6 | ContainerRestarting | container_health | critical | >3 in 15m | 0m |
| 7 | HostHighCPU | host_health | warning | >85% | 10m |
| 8 | HostHighMemory | host_health | critical | >90% | 5m |
| 9 | HostDiskFull | host_health | critical | >85% | 5m |
| 10 | ServiceUnhealthy | service_health | critical | `up == 0` | 2m |
| 11 | AroWakeLowSuccessRate | aro_wake | warning | low success rate | 15m |
| 12 | AroWakeCostBurnHigh | aro_wake | warning | cost burn >$5/h per host | 10m |
| 13 | FabrikRegistrarDrift | fabrik-registrar-drift | warning | `fabrik_audit_drift_total > 0` | 10m |

All applicable rules include `value` annotations for ARO Brain quantitative reasoning.

**Key config files (local mirror in Fabrik `configs/`):**
- `configs/alertmanager/alertmanager.yml` — routing, receivers, inhibit rules
- `configs/prometheus/prometheus.yml` — scrape targets, alerting config
- `configs/prometheus/rules/alerts.yml` — alert rules

---

## Purpose

Provide a dependency-aware health check surface that:

- returns non-200 when upstream dependencies are degraded (for external uptime monitors)
- exposes which dependency failed in a stable JSON shape
- supports command-line probing for automation (CI, cron, or ad-hoc debugging)

> **Legacy `coolify` check (decommissioned 2026-05-30).** `health_app.py` still has a `_check_coolify_sync()` branch and emits a `checks.coolify` key, but Coolify is decommissioned — this is a dead dependency that always reports unhealthy/unreachable and should be removed. The descriptions below document the code as it currently stands.

---

## Usage

### FastAPI `/health` endpoint

**Location:** `src/fabrik/health_app.py`

Run the minimal health app locally:

```bash
uvicorn fabrik.health_app:app --reload --port 8000
```

Probe the endpoint:

```bash
curl -fsS http://localhost:8000/health | python -m json.tool
```

**Response body shape** (always JSON):

```json
{
  "service": "fabrik",
  "status": "ok" | "degraded",
  "checks": {
    "coolify": {
      "status": "healthy" | "unhealthy",
      "details": { "status": "...", "...": "..." },
      "error": "..."
    },
    "dns": {
      "status": "healthy" | "unhealthy",
      "details": { "status": "...", "...": "..." },
      "error": "..."
    }
  }
}
```

Notes:

- `checks.coolify` and `checks.dns` always include a top-level `status`.
- `details` is present when the underlying dependency returns a structured payload.
- `error` is present when the dependency check raises an exception.

**HTTP status codes**:

- `200 OK` when **all** dependency checks report `status=healthy`
- `503 Service Unavailable` when **any** dependency check reports `status=unhealthy`

**Dependency checks**:

- Coolify (legacy/dead — decommissioned 2026-05-30): `CoolifyClient.health()` via `_check_coolify_sync()`
- DNS manager: `DNSClient.health()`

Each dependency payload is normalized by `_normalize_status()` to map common upstream statuses
(`ok`, `healthy`, `pass`, `success`) into `healthy`.

---

### `scripts/health_checker.py`

`scripts/health_checker.py` is a CLI utility for probing health and (optionally) database reachability.

Basic usage (HTTP health probe):

```bash
python scripts/health_checker.py --health-url http://localhost:8000/health
```

Database reachability probe (TCP connect to host:port):

```bash
# Uses DATABASE_URL if set, otherwise DB_HOST/DB_PORT
python scripts/health_checker.py --check-db
```

Run both checks:

```bash
python scripts/health_checker.py --health-url http://localhost:8000/health --check-db
```

**Exit codes**:

- `0` - all requested checks passed
- `1` - unexpected error (uncaught exception)
- `2` - configuration error (required inputs missing)
- `3` - HTTP health check failed (non-200, invalid JSON, or degraded status)
- `4` - database host/port unreachable (TCP connect failed)

---

## Configuration

`src/fabrik/health_app.py` depends on the Coolify and DNS client configuration (see their driver docs).

`scripts/health_checker.py` uses the following environment variables for database targeting:

- `DATABASE_URL` - preferred; parsed for host and port (e.g. `postgresql://user:pass@localhost:5432/dbname`)
- `DB_HOST` - used when `DATABASE_URL` is not set
- `DB_PORT` - used when `DATABASE_URL` is not set
- `DB_NAME` - optional (not required for TCP reachability)
- `DB_USER` - optional (not required for TCP reachability)
- `DB_PASSWORD` - optional (not required for TCP reachability)

---

## Registrar Coverage Audit (T2-02, 2026-05-15)

The HTTP `/health` endpoint covered by this doc verifies a SINGLE service's runtime liveness. T2-02 adds a complementary primitive that verifies the SETUP — every shape-applicable registrar (Postgres DB, Redis slot, Gatus endpoint, Backrest plan, GlitchTip project, Authelia rule, Meilisearch index, Prometheus scrape job) is actually live on the VPS:

```bash
fabrik audit-registrars                       # pivot table across all specs
fabrik audit-registrars --spec <path>         # one spec
fabrik audit-registrars --spec <path> --json  # machine-readable
```

Plus a postcondition gate that pairs cleanly with the HTTP `/health` check:

```bash
fabrik verify <domain> --spec deploy          # HTTP /health + SSL + container status (via SSH)
fabrik verify <domain> --spec registrars      # registrar coverage
```

Run both in sequence after `fabrik apply` to verify the full Stage 3/Stage 4 chain — service is up AND every auto-registration the orchestrator was supposed to perform actually landed. Exit codes propagate so shell `&&` chaining works:

```bash
fabrik apply <spec> \
  && fabrik verify <domain> --spec deploy \
  && fabrik verify <domain> --spec registrars
```

Implementation: `src/fabrik/audit.py` mirrors each driver's transport (10 audit functions in `_AUDIT_FUNCS` — SSH for most; `requests` for glitchtip; `n/a` for grafana which has no driftable state). State file persisted at `.fabrik/state/<spec.id>.json` (T2-01) feeds future state-aware destroy (T4-01).

## Weekly Authelia Drift Cron (T2-03 G-G4, 2026-05-15)

Companion to the on-demand `audit-registrars` check above — `scripts/audit_authelia_gates.py` runs every Monday 06:00 via WSL cron, hits the live Traefik API over SSH, and verifies every admin-dashboard router still has the `authelia-forward@docker` middleware attached (the policy-vs-enforcement drift class from Lesson 32 / the 2026-04-18 GlitchTip incident).

```cron
0 6 * * 1 PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_authelia_gates.py >> /var/log/fabrik-audit.log 2>&1
```

Log lives at `/var/log/fabrik-audit.log` (writable by `ozgur:ozgur`). Each run appends a block ending in `SUMMARY: N OK, M GAP, K MISSING`. Manual smoke: `PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_authelia_gates.py`.

**Known follow-up:** the script's expected inventory predates T2-08 Part A's decision to gate `errors.vps1.ocoron.com`. Every Monday's run prints `1 GAP` against `errors`; cosmetic (exit 0) until the inventory is updated.

## Hourly Per-Registrar Drift Alert (T4-04 G-G5, 2026-05-16)

Generalises the Authelia weekly cron to all 10 audited registrars at hourly cadence. `scripts/audit_all_registrars.py` walks every spec, calls `fabrik.audit.audit_all`, emits Prom-text `fabrik_audit_drift_total{spec_id, registrar}` gauge metrics, pushes via SSH to the VPS-local pushgateway (`prom/pushgateway:v1.9.0` at `127.0.0.1:9091`).

```cron
0 * * * * PYTHONPATH=/opt/fabrik/src /opt/fabrik/.venv/bin/python /opt/fabrik/scripts/audit_all_registrars.py >> /var/log/fabrik-audit-all.log 2>&1
```

**Alert chain:** prometheus scrapes pushgateway (`honor_labels: true`) → rule file `/opt/monitoring/configs/prometheus/rules/fabrik-drift.yml` (alert `FabrikRegistrarDrift`, `expr: fabrik_audit_drift_total > 0`, `for: 10m`, label `alert_class: registrar_drift`) → Alertmanager route under `route.routes:` matches that label → existing `telegram` receiver (no new receiver per pack v3.2 V2-S4).

**Detection latency:** ≤ 1h (cron interval) + 11min (for-window + group_wait) ≈ 71 minutes worst case. Matches Epic SC-4 "within ~1 hour".

**Roundtrip-verified live 2026-05-16:** synthetic drift fired Telegram in 11 minutes; resolution (`fabrik_audit_drift_total=0`) cleared the alert within 90 seconds via Alertmanager `send_resolved: true`.

**Pairs with:**

- `fabrik audit-registrars` (T2-02 G-G2) — operator-invoked on-demand version of the same audit.
- `audit_authelia_gates.py` (T2-03 G-G4) — registrar-specific deeper check (Authelia policy ↔ Traefik middleware) that fires from the same alert chain via the same `telegram` receiver.

## Stable Docker DNS Aliases (T2-04 G-J3, 2026-05-15) — LEGACY / not deployed

> **Decommissioned (2026-06):** This mechanism existed to work around Coolify renaming Application containers on every redeploy. Coolify has since been decommissioned (`coolify` is now only a legacy Docker-network name), so the per-redeploy rename problem no longer exists and the alias-watcher is **not running** — `/opt/coolify-alias-watcher/` is absent on the VPS. The repo files (`src/fabrik/orchestrator/coolify_alias.py` live; the former `ops/coolify-alias-watcher/` WSL mirror was archived to `ops/.archive/2026-06-17-coolify-decommission/coolify-alias-watcher/`) remain as a historical mirror. The description below documents the original design.

Adjacent to the audit/verify primitives above — the alias-watcher keeps friendly Docker DNS names alive for Gatus monitors and inter-service URLs that target Coolify Application containers. Coolify renames Application containers on every redeploy (`<24-char-uuid>-<10-digit-timestamp>`); without the watcher, `gatus:8080 → meilisearch:7700` resolution would break after each redeploy of the meilisearch container.

The watcher service (`/opt/coolify-alias-watcher/`) is event-driven (listens to `docker events --filter event=start`), reads the prefix→alias map from `/opt/coolify-alias-watcher/aliases.json`, and re-applies aliases within ~1s. WSL mirror in repo archived at `ops/.archive/2026-06-17-coolify-decommission/coolify-alias-watcher/`.

**Orchestrator integration:** new services that need stable DNS opt in by setting `coolify.alias: <name>` in their spec's `CoolifyConfig` block. `fabrik apply` calls `src/fabrik/orchestrator/coolify_alias.py::add_alias(ctx.coolify_uuid, alias)` after the Coolify create-app step, which writes atomically to aliases.json and restarts the watcher. Non-fatal: alias-watcher failure logs a warning but never aborts deploy.

**Why this matters for monitoring:** Gatus endpoint configs at `/opt/monitoring/configs/gatus/apps/<svc>.yaml` reference services by friendly name (`http://meilisearch:7700/health`). If a Coolify redeploy renames the underlying container and the watcher hasn't re-attached the alias yet, that Gatus check would 503 until the next watcher cycle (sub-second window). Across all 4 baseline aliases (meilisearch, gotenberg, browserless, glitchtip-web) this has been silent-correct since 2026-04-16.

---

## See also

- `src/fabrik/health_app.py` - FastAPI health endpoint implementation
- `src/fabrik/audit.py` - per-registrar audit module (T2-02)
- `scripts/audit_authelia_gates.py` - weekly Authelia-Traefik drift audit (T2-03 G-G4)
- `src/fabrik/orchestrator/coolify_alias.py` - Coolify alias-watcher write side (T2-04 G-J3)
- `ops/.archive/2026-06-17-coolify-decommission/coolify-alias-watcher/` - archived WSL mirror of the VPS-side `/opt/coolify-alias-watcher/`
- `docs/reference/modules/drivers.md` - driver API reference (registrar drivers + DNS/GPU providers)
- `.env.example` - authoritative environment variable reference

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/audit_all_registrars.py`
- `scripts/audit_authelia_gates.py`
<!-- END related-scripts -->
