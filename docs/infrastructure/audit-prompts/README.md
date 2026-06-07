# VPS Audit Prompts — Fleet Edition

**Last Updated:** 2026-06-02 (full rewrite of all 8 prompts for the 3-VPS fleet; previous version was 2026-05-19 Coolify-era single-VPS vintage)

Structured prompts for comprehensive infrastructure auditing of the 3-VPS Fabrik fleet. Each prompt is a self-contained brief designed to be pasted into an AI assistant (Claude Code, ChatGPT, etc.) alongside the diagnostic output it requests.

## Quick-start

1. Pick the audit you need (table below).
2. Note the **run mode** — some audits are per-host, some are fleet-wide.
3. Run the listed commands and collect the output.
4. Paste the prompt body + your command output + the stack context block into Claude.
5. Apply the findings via prompt #08 (hardening remediation).

## The 8 prompts

| # | File | Run mode | Scope | When to use |
| :--- | :--- | :--- | :--- | :--- |
| 01 | [01-full-system-audit.md](01-full-system-audit.md) | **per host** | Identity, CPU, memory, disk, network, services, security overview | Monthly per host, after incidents, before going live |
| 02 | [02-container-health.md](02-container-health.md) | **per host** | Container fleet stability, resources, health, log hygiene, W15 spoke check | After deploys, when services slow/crash, during/after `fabrik apply` |
| 03 | [03-security-hardening.md](03-security-hardening.md) | **fleet-wide, per-host probes** | SSH, UFW, DOCKER-USER, mesh trust, TLS, Authelia, fail2ban, container isolation, secrets | Before production launch, quarterly review, after any access change |
| 04 | [04-performance-bottleneck.md](04-performance-bottleneck.md) | **per host** | CPU, memory, disk I/O, network — identify what's slow + why | When a host is slow, load is high, or users report latency |
| 05 | [05-observability-pipeline.md](05-observability-pipeline.md) | **fleet-wide, hub-rooted** | Prometheus + Grafana + Loki + Alertmanager + GlitchTip + Gatus end-to-end | When dashboards are empty, alerts aren't firing, logs missing, or after W8-style observability changes |
| 06 | [06-backup-disaster-recovery.md](06-backup-disaster-recovery.md) | **per host** for probes, fleet-wide for analysis | Backrest config + B2 reachability + snapshot freshness + DR scripts + DR-store mirror | Monthly, before major changes, before DR drill |
| 07 | [07-pre-production-checklist.md](07-pre-production-checklist.md) | **per spec** (`target_vps`-aware) | Go-live readiness for a new spec against the spec's target host | Before first real users hit a new service |
| 08 | [08-hardening-remediation.md](08-hardening-remediation.md) | **per host** | Execute fixes from audits 01-06; backup-before-destruct discipline | After running audits 01-06 to make the fleet production-grade |

## Run-mode legend

- **per host** — pick a host, run the prompt's data-collection commands against just that host, get a per-host report. To audit the whole fleet, run it 3× (once each for vps1/vps2/vps3) and compare reports.
- **fleet-wide, per-host probes** — collect data from all 3 hosts, analyze them together. The findings often surface as drift between hosts.
- **fleet-wide, hub-rooted** — most probes run on vps1 (the host that centralizes the data); spoke-side probes confirm agents are pushing.
- **per spec** — runs against the spec's `target_vps`, not a host you pick. The prompt parses the spec to determine the target.

## Fleet topology — share this with Claude

```text
- 3-VPS Wireguard mesh (10.99.0.0/24):
  - vps1 hub:  10.99.0.1 (LA, GreenCloudVPS, 172.93.160.197, 11.6 GiB / 6 cores)
  - vps2 spoke: 10.99.0.2 (Coventry UK, GreenCloudVPS, 96.9.214.128, 7.7 GiB / 4 cores)
  - vps3 spoke: 10.99.0.3 (Coventry UK, GreenCloudVPS, 104.128.190.151, 7.7 GiB / 4 cores)
- Single-operator threat model. Mesh is fully trusted.
- All hosts: Ubuntu 24.04 LTS; UFW + fail2ban + DOCKER-USER chain; root SSH disabled;
  password SSH disabled; `ozgur` user with NOPASSWD sudo + ed25519 key.
- Deploy mechanism: SSH + Docker Compose via `fabrik apply` since 2026-05-30
  (Coolify removed). Spec field `target_vps: vpsN` routes deploys.
- Network: containers use the `fabrik` Docker network (renamed from `coolify`
  on 2026-05-31; some compose files still reference `coolify` as a
  historical artifact — intentional per deploy invariants).
```

## Container counts (current)

```text
vps1: 29 containers — site-provisioner + authelia + glitchtip-web/worker +
      redis-main + postgres-main + postgres-exporter + redis-exporter +
      loki + promtail + prometheus + alertmanager + grafana + gatus +
      cadvisor + node-exporter + pushgateway + apprise + backrest + n8n +
      gotenberg + browserless + meilisearch + traefik + 5 ocoron-com tenant
vps2 + vps3: 5 containers each — traefik + node-exporter + cadvisor +
      promtail + backrest (per W11 ship 2026-06-01)
```

## Observability (centralized on vps1)

```text
Prometheus + Alertmanager + Grafana + Loki + Promtail + Gatus + GlitchTip
- Loki accepts mesh pushes at 10.99.0.1:3100; spokes' promtail uses it
- Prometheus scrapes 18 targets across 15 jobs (12 vps1 + 3 spoke job-groups)
- Every series has `host` label (vps1/vps2/vps3) for fleet filtering
- spoke_health rule group: SpokeDown / SpokeHighCPU / SpokeHighRAM
- AI sysadmin: vps-sysadmin-bot.service on vps1 ONLY
```

## Backups (Backrest → Backblaze B2 in us-west-004)

```text
vps1 hub: 4 plans (postgres-dumps, docker-volumes, opt-configs, host-state)
          repo: vps1-ocoron-backups (a256277c45) — first ship 2026-06-01 (W2)
vps2 + vps3 spokes: 2 plans each (host-state, opt-configs)
          repos at b2:vps1-ocoron-backups/spokes/vps{2,3}/
          first ship 2026-06-01 (W11)
DR scripts:
  scripts/bootstrap/bootstrap-hub.sh (18 steps, ≤90 min target, UNDRILLED)
  scripts/bootstrap/bootstrap-spoke-restore.sh (13 steps, ≤30 min, UNDRILLED)
DR-store mirror (W9, extended for W11): private GitHub mobasak/fabrik-dr-store
  carries /opt/fabrik/.env + .env.sysadmin + per-spoke restic passwords +
  per-spoke .env.backrest. Inotify watcher pushes within seconds.
```

## Latest probe report

Run `python3 scripts/audit_infra_vs_docs.py` to refresh. The script writes timestamped YAML to `docs/infrastructure/probe-reports/`.

**Most recent (cite this as ground truth in audit prompts):** [`../probe-reports/infra-probe-2026-06-06T22-39Z.yaml`](../probe-reports/infra-probe-2026-06-06T22-39Z.yaml) (post-W14 sweep). Counts: 29/5/5. UFW active on all 3. Mesh peers alive: vps1=2, vps2=1, vps3=1. fail2ban totals: 891/73/72.

## Lessons captured (relevant to auditing)

1. **Symptom-grep cannot find an absence.** Pre-W1 UFW state was `rc` (removed-with-config), not "never installed". Audits must probe for *presence* (3 probes — `dpkg -l`, `command -v`, `ufw status`), not just for *failure symptoms*. (Lesson 68)
2. **dev-WSL TCP probes lie.** Türk Telekom AS9121 has a middlebox that spoofs SYN-ACKs, making `nc -zv` report "succeeded" against ports that aren't actually open. Probe from a clean-AS off-mesh node (the other spokes work). (Lesson 72)
3. **Env-var verification uses `docker inspect`**, NEVER `docker exec printenv`. Distroless / scratch images have no shell. (Lesson 31)
4. **Health checks test real deps** (`SELECT 1`, Redis `PING`), not a static 200. (Lesson 30)
5. **Silence ContainerDown** before any planned op > 2 min, or Telegram floods. (Operator discipline; not a numbered Lesson but a hard-won habit.)
6. **`docker logs` is per-container.** Loki + Grafana queries are how you audit fleet-wide log behavior; raw `docker logs` is only useful when you already suspect a specific container.

## Cross-references

- Architecture: [`../vps-fleet-architecture.md`](../vps-fleet-architecture.md) — the "fleet as one system" picture
- Live inventory: [`../vps-complete-inventory.md`](../vps-complete-inventory.md) — source of truth for what runs where
- Status snapshot: [`../vps-status.md`](../vps-status.md) — point-in-time health
- URLs: [`../vps-urls.md`](../vps-urls.md) — how to reach things
- Bootstrap: [`../vps-bootstrap-plan.md`](../vps-bootstrap-plan.md) — provisioning a new VPS
- AI sysadmin (host-level): [`../vps-ai-sysadmin.md`](../vps-ai-sysadmin.md) — the second AI layer (per-project watchdog) is separately documented there
- Residue policy: [`../vps-residue-policy.md`](../vps-residue-policy.md) — what stays vs gets cleaned
- Lessons learnt: [`../../LESSONS_LEARNT.md`](../../LESSONS_LEARNT.md)
