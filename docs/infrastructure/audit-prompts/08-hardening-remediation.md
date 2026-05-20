# Post-Audit Hardening — Make VPS Production-Grade

> **DANGER — READ BEFORE EXECUTING ANYTHING**
>
> This is a live VPS. Loss of SSH access or boot failure is unrecoverable without hosting provider intervention.
>
> **NEVER touch:**
> - `/etc/docker/daemon.json` (Docker daemon config — restart kills all containers)
> - `iptables` / `nftables` / UFW rules (firewall — wrong rule locks you out)
> - `/etc/fstab` (boot config — bad entry prevents boot)
> - `/etc/netplan/` or `/etc/network/` (network config — wrong change = lost SSH)
> - `systemctl disable` on `docker`, `ssh`, `coolify`, `iptables-docker-user` (breaks everything)
> - Docker socket permissions or Docker group membership changes
>
> **ALWAYS:**
> - Back up any config file before editing: `cp <file> <file>.backup.$(date +%Y%m%d-%H%M%S)`
> - Test one change at a time, verify SSH still works after each
> - Use `docker update --memory` for live limits (no restart), not compose edits
> - Use Prometheus `/-/reload` for rule changes (no restart), not container restart
> - Gatus auto-reloads config within 30s — no restart needed

Execute after running audits 01-06. This prompt takes their findings and turns them into a prioritized remediation plan. The goal: a VPS that is secure, performant, resource-efficient, measurable, and recoverable.

## Design Principles

1. **Defense in depth** — every layer (network, container, application) enforces its own security. No single layer is trusted.
2. **Resource accounting** — every container has explicit CPU and memory limits. No container can OOM the host.
3. **Observable by default** — every service is monitored, every failure triggers an alert, every metric has a dashboard.
4. **Recoverable** — every stateful component is backed up with tested retention. Recovery time is documented.
5. **Minimal attack surface** — only required ports open, only required services running, only required privileges granted.
6. **Automated hygiene** — destroyed services leave zero residue. Drift is detected and alerted within 1 hour.

## Input: Audit Findings

Paste the unified report from audits 01-06 (or the individual reports). The AI will:
1. Categorize each finding as: security / performance / reliability / hygiene
2. Assess blast radius (host-level / container-level / cosmetic)
3. Order by: risk × ease-of-fix
4. Generate exact commands, grouped by execution phase

## Hardening Checklist

### A. Network Perimeter

- [ ] UFW active with explicit ALLOW for 22, 80, 443, 6001, 6002 and DENY for 8000
- [ ] DOCKER-USER iptables chain has 9 rules with catch-all DROP
- [ ] `iptables-docker-user.service` enabled and running (survives reboot)
- [ ] No container publishes ports to 0.0.0.0 outside Traefik
- [ ] Port 1194 (OpenVPN) documented if intentional, closed if not
- [ ] fail2ban installed and active for SSH

### B. Container Resource Limits

Every container must have explicit `deploy.resources.limits.memory` set. Recommended baseline:

| Category | Memory limit | CPU limit | Examples |
|----------|-------------|-----------|---------|
| Infrastructure (heavy) | 1-2g | 1.0 | postgres-main, n8n, browserless |
| Infrastructure (medium) | 512m | 0.5 | grafana, loki, prometheus, authelia, glitchtip-web |
| Infrastructure (light) | 256m | 0.25 | alertmanager, gatus, apprise, backrest, pushgateway |
| Monitoring agents | 512m | 0.5 | netdata (if kept), cadvisor |
| Exporters | 128m | 0.1 | node-exporter, postgres-exporter, redis-exporter, promtail |
| Application services | 512m | 0.5 | site-provisioner, image-broker, any fabrik-deployed app |
| WordPress stack | per-container | 0.5 | ocoron-com-wordpress 512m, ocoron-com-db 1g, ocoron-com-nginx 256m, ocoron-com-redis 256m |
| Coolify core | — | — | Managed by Coolify itself, don't override |

Verification: `docker stats --no-stream` — no container should show `/11.63GiB` as its limit.

### C. System Tuning

- [ ] `vm.swappiness=10` (persist in `/etc/sysctl.d/99-tuning.conf`)
- [ ] `net.core.somaxconn=65535` (connection queue for Traefik)
- [ ] `net.ipv4.tcp_tw_reuse=1` (reduce TIME_WAIT buildup)
- [ ] `fs.file-max=1048576` (file descriptor ceiling)
- [ ] `fs.inotify.max_user_watches=524288` (for Gatus, Promtail, file watchers)
- [ ] Journal capped: `SystemMaxUse=500M` in `/etc/systemd/journald.conf`
- [ ] Docker log rotation: `daemon.json` has `max-size: 10m`, `max-file: 3`, `tag: {{.Name}}`
- [ ] Root mount has `noatime` in fstab

### D. Monitoring Completeness

- [ ] All containers have a Gatus health endpoint OR are scraped by Prometheus
- [ ] Alert rules exist for: HostHighCPU, HostHighMemory, HostDiskFull, ContainerOOM, PromtailNotShipping, FabrikRegistrarDrift, BackupStale
- [ ] Grafana has datasources connected (Prometheus + Loki)
- [ ] Grafana has all expected dashboards (currently 8)
- [ ] GlitchTip projects exist for all deployed services, all have `firstEvent`
- [ ] Promtail noise filter working (5 containers excluded, container_name label populated)

### E. Backup & Recovery

- [ ] Backrest running with all plans on schedule
- [ ] Retention policy set on all plans: `keepDaily:7, keepWeekly:4, keepMonthly:6`
- [ ] Coverage: postgres-main, redis-main, WordPress volumes, Authelia config, monitoring configs
- [ ] Coolify state (`/data/coolify/`) added to backup plan
- [ ] WSL `.env` backed up locally in `backups/` dir
- [ ] Recovery tested: can restore a single postgres DB from latest snapshot
- [ ] RTO documented (estimated time to rebuild from scratch vs restore)

### F. Hygiene

- [ ] Zero dangling Docker volumes
- [ ] Zero dangling Docker images
- [ ] Zero orphan Docker networks
- [ ] Zero stale Created containers
- [ ] Zero zombie processes
- [ ] `fabrik vps-sync --verify` returns clean
- [ ] `fabrik audit-registrars` returns zero drift
- [ ] VPS inventory doc matches live state (`generate_vps_inventory.py --update`)

### G. Monitoring Stack Optimization

Evaluate whether the current monitoring stack is right-sized:

| Component | Current CPU | Current RAM | Question |
|-----------|-----------|-----------|---------|
| Netdata | ~10-16% | 382 MiB | Do we need Netdata AND Prometheus+cAdvisor+node-exporter? They overlap on host + container metrics. |
| cAdvisor | ~1% | 28 MiB | Needed — feeds container metrics to Prometheus. Keep. |
| Prometheus | ~0.6% | 120 MiB | Core metrics store. Keep. Verify retention (30d/5GB). |
| Grafana | ~0.9% | 93 MiB | Core dashboards. Keep. |
| Loki | ~0.5% | 81 MiB | Core log store. Keep. Verify retention (7d). |
| Promtail | ~1% | 40 MiB | Log shipper. Keep. |
| node-exporter | ~0.1% | 10 MiB | Host metrics. Keep. |
| postgres-exporter | ~0.1% | 17 MiB | DB metrics. Keep. |
| redis-exporter | ~0.1% | 17 MiB | Cache metrics. Keep. |
| Pushgateway | ~0% | 8 MiB | Drift alert push target. Keep. |

**Decision point:** Remove Netdata (saves ~10% CPU, 380 MiB) OR reduce its collection frequency from 1s to 5s and disable `apps.plugin`. Prometheus+cAdvisor+node-exporter cover all the same ground.

## Execution Phases

### Phase 1: Non-Intrusive (safe now, zero downtime)

Commands that tune the host, clean residue, and cap resources without restarting anything.

### Phase 2: Container Restarts (one-at-a-time, <30s per container)

Set memory limits, remove Netdata or reconfigure, restart containers that need config changes.

### Phase 3: Structural Changes (planned maintenance window)

Backup plan changes, alert rule additions, Gatus endpoint additions, monitoring stack reorganization.

## Output Format

For each finding from the audit reports:

1. **Finding** — what was reported
2. **Category** — security / performance / reliability / hygiene
3. **Blast radius** — host / container / cosmetic
4. **Phase** — 1 / 2 / 3
5. **Command** — exact command(s) to execute
6. **Verification** — how to confirm the fix worked
7. **Rollback** — how to undo if something breaks

End with a **completion checklist** — every item from sections A-G above, marked done/not-done with evidence.
