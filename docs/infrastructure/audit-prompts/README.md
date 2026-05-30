# VPS Audit Prompts

> **⚠️ Pre-migration vintage.** All eight audit prompts in this directory
> were authored during the Coolify-orchestrated era. They reference Coolify
> containers, the Coolify UI, and Coolify deployment workflows. The audit
> *intent* (security, observability, backups, container health, etc.) is
> still valid post-migration — but specific check commands need to be
> rewritten: `sudo docker compose -f /opt/<app>/compose.yaml ps` instead
> of "Coolify dashboard", `/opt/<app>/.env` instead of "Coolify env vars",
> etc. Re-run audits with these substitutions in mind, or rewrite the
> prompts for the SSH+Compose era as needed.

Structured prompts for comprehensive VPS health auditing. Each file is a self-contained prompt designed to be pasted into an AI assistant (Claude Code, ChatGPT, etc.) alongside the diagnostic output it requests.

## Usage

1. Pick the audit you need
2. SSH to VPS and run the listed commands
3. Paste the prompt + command output into your AI assistant
4. Follow the remediation roadmap

## Prompts

| File | Scope | When to use |
|------|-------|-------------|
| [01-full-system-audit.md](01-full-system-audit.md) | Complete 8-domain VPS health check | Monthly, after incidents, before going live |
| [02-container-health.md](02-container-health.md) | Docker/Coolify container diagnostics | After deploys, when services are slow/crashing |
| [03-security-hardening.md](03-security-hardening.md) | Firewall, auth, TLS, attack surface | Before production launch, quarterly review |
| [04-performance-bottleneck.md](04-performance-bottleneck.md) | CPU, memory, disk I/O, network deep-dive | When VPS is slow, load is high, or users report latency |
| [05-observability-pipeline.md](05-observability-pipeline.md) | Prometheus, Loki, Grafana, GlitchTip, Gatus | When dashboards are empty, alerts aren't firing, logs are missing |
| [06-backup-disaster-recovery.md](06-backup-disaster-recovery.md) | Backrest, B2, volume integrity, recovery testing | Monthly, before major changes, after data incidents |
| [07-pre-production-checklist.md](07-pre-production-checklist.md) | Go-live readiness for a new service deployment | Before first real users hit the VPS |
| [08-hardening-remediation.md](08-hardening-remediation.md) | Post-audit hardening — execute fixes from audit findings | After running audits 01-06, to make VPS production-grade |

## Lessons Learned (2026-05-19 first run)

1. **All scripts must use `sudo`** for: docker, ufw, iptables, dmesg, journalctl, sshd, aa-status, last, and any file under `/var/lib/docker/volumes/`. SSH user is not root and not in docker group.
2. **Scripts that read `/opt/fabrik/.env`** must account for the fact that `.env` lives on WSL, not VPS. Tokens for Grafana/GlitchTip need to be passed as env vars or read from VPS-local paths.
3. **Time-series commands** (`vmstat 1 5`, `iostat -x 1 3`) add 3-15s per script. Acceptable for parallel execution but not for sequential.
4. **`ip -s link`** without a specific interface dumps all Docker bridges. Always detect primary interface first.
5. **Container names** on Coolify are UUID-based. Scripts must use `docker ps --filter name=<pattern>` not exact names.

## Stack Context (paste into any prompt if needed)

```
VPS: Ubuntu 24.04 LTS, 6 vCores (x86_64), 11GB RAM, 108GB disk
Orchestration: Coolify v4 (beta.459), Traefik v2.11
Data: PostgreSQL 16 (shared, postgres-main), Redis 7 (shared, redis-main)
Observability: Prometheus + Alertmanager + Grafana + Loki + Promtail + Gatus + GlitchTip + Netdata
Backups: Backrest -> Backblaze B2
Docker: ~36 containers, coolify network (10.0.1.0/24), daemon.json log tag enabled
Deployment: /data/coolify/services/ (Coolify Services) + /data/coolify/applications/ (Coolify Apps)
Monitoring configs: /opt/monitoring/configs/ (prometheus, alertmanager, grafana, loki, promtail, gatus)
```
