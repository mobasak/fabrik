# Archived 2026-06-17 — Coolify-era / retired-tool scripts

These one-time/migration scripts target tools that no longer exist on the fleet.
They were not imported by any live code, not invoked by CI/Makefile/cron/startup
hooks, and only referenced from `docs/archive/**` + CHANGELOG history. Archived
(not deleted) to preserve the record.

| Script | Why retired |
|--------|-------------|
| `setup_duplicati_backup.py` / `duplicati-vps-backup.json` | Duplicati was replaced by **Backrest** (restic) on 2026-04-17. |
| `setup_uptime_kuma.py` / `delete_uptime_kuma.py` | Uptime Kuma was replaced by **Gatus** (config-file driven). |
| `coolify_services_f5.py` | Coolify-specific helper; **Coolify decommissioned 2026-05-30** (deploy is SSH + Docker Compose via `fabrik apply`). |
| `migrate-authelia-to-coolify.sh` | One-time migration **into** Coolify — reversed by the SSH+Compose migration; Coolify is gone. |

Current equivalents: Backrest (backup), Gatus (uptime), `deployer_ssh.py` (deploy),
node-exporter + cAdvisor → Prometheus → Grafana (metrics).
