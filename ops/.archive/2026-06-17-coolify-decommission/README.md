# Archived 2026-06-17 — Coolify-decommission

## coolify-alias-watcher

Re-applied friendly Docker network aliases that **Coolify dropped on every redeploy**.
Coolify was decommissioned 2026-05-30 — deploys now run via SSH + Docker Compose
(`deployer_ssh.py`), where the compose declares `networks: [fabrik]` with stable
`container_name:` and aliases that survive redeploys, so the watcher's premise is moot.
It is **not deployed** on the live fleet (no `/opt/coolify-alias-watcher/`, no systemd
unit) and watched the now-removed `coolify` network. Archived (not deleted) for history.
