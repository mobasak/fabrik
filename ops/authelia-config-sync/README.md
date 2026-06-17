# Authelia config sync hook

Authelia's config is **bind-mounted** from `/opt/authelia/config/` into the container
(`/opt/authelia/config:/config`), so the working copy **is** the config Authelia reads —
there's no separate volume to mirror into. This watcher just **restarts the container**
when `configuration.yml` changes, so edits take effect without remembering a manual restart.

> **Never SIGHUP Authelia** — it *exits* on SIGHUP (see `docs/LESSONS_LEARNT.md`). The
> watcher always does `docker restart authelia`.

## How it works

1. `inotifywait` watches `/opt/authelia/config/` for `close_write` / `moved_to` / `create`
   events (event-driven, no polling).
2. When `configuration.yml` changes, waits ~1s, then `docker restart authelia`.
3. Reaction latency: **~1–2 s** after save.

The target container is the stable name **`authelia`** (Fabrik container-name convention
since the 2026-05-30 SSH + Docker Compose migration — no more Coolify UUID-suffix names).

## Installation (already live on vps1.ocoron.com — `authelia-config-sync.service`, active)

```bash
sudo apt-get install -y inotify-tools
sudo mkdir -p /opt/authelia-config-sync
sudo cp sync.sh /opt/authelia-config-sync/sync.sh
sudo chmod +x /opt/authelia-config-sync/sync.sh
sudo cp authelia-config-sync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now authelia-config-sync.service
```

## Status / logs

```bash
sudo systemctl status authelia-config-sync.service
sudo tail -f /var/log/authelia-config-sync.log
```
