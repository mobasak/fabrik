# Coolify alias watcher

Solves the problem that **Coolify drops friendly Docker network aliases on every redeploy**. Without this watcher, services like `meilisearch`, `gotenberg`, `browserless`, and `glitchtip-web` lose their stable DNS names after each Coolify deploy, breaking Prometheus scrapes, Gatus monitoring, and any microservice that depends on these aliases.

## How it works

1. Reconciles all known containers at startup (idempotent — only acts if alias missing)
2. Streams `docker events --filter event=start` (event-driven, no polling)
3. When a container matching one of the configured prefixes starts, waits ~2s for Coolify to finish its own network attach, then re-applies the friendly alias via `docker network disconnect/connect --alias`

Total reaction latency: **~2-3 seconds** after container start.

## Installation (already done on vps1.ocoron.com)

```bash
sudo mkdir -p /opt/coolify-alias-watcher
sudo cp watcher.sh /opt/coolify-alias-watcher/watcher.sh
sudo chmod +x /opt/coolify-alias-watcher/watcher.sh
sudo cp coolify-alias-watcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now coolify-alias-watcher.service
```

## Verification

```bash
sudo systemctl status coolify-alias-watcher.service
sudo tail -f /var/log/coolify-alias-watcher.log
```

## Adding a new service

Edit the `ALIASES` map in `watcher.sh` — key is the container name prefix Coolify uses (UUID for Applications, compose service name for Services), value is the desired alias. Then `sudo cp watcher.sh /opt/coolify-alias-watcher/ && sudo systemctl restart coolify-alias-watcher`.

## Why event-driven instead of polling

Polling every 60s leaves a 60s window where downstream services fail. Event-driven reaction is essentially instant. Docker events stream is cheap (single Unix socket read), uses ~10MB memory.

## Why not Coolify-native (compose alias / post_deploy_command)

- `custom_network_aliases` field in Coolify's API is read-only (PATCH returns HTTP 422).
- `custom_docker_run_options: --network-alias X` is accepted but Coolify doesn't pass it to the compose-up flow.
- `post_deployment_command` runs **inside** the deployed container, not on the host — has no docker socket access.

Watcher avoids all of those gotchas at the cost of one tiny systemd service.
