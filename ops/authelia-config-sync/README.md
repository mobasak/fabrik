# Authelia config sync hook

Solves the problem that **Authelia loads its config from a Docker named volume, not from `/opt/authelia/config/`**. The directory at `/opt/authelia/config/` is just a working copy / convention. Editing it directly does nothing until the file is also synced to the volume — which is a manual step that's easy to forget and was the source of multiple wasted hours of debugging in 2026-05.

This hook makes that drift impossible.

## How it works

1. Resolves the actual volume mount path at runtime via `docker inspect` (handles volume UUID changes if Authelia is ever recreated).
2. Watches `/opt/authelia/config/` directory for `close_write` / `moved_to` / `create` events using `inotifywait` (event-driven, not polling).
3. When `configuration.yml` changes, copies it into the volume, sets `chmod 600`, and **restarts the Authelia container** (never SIGHUP — Authelia exits on SIGHUP).
4. Reaction latency: **~1-2 seconds** after save.

## Installation (already done on vps1.ocoron.com)

```bash
sudo apt-get install -y inotify-tools
sudo mkdir -p /opt/authelia-config-sync
sudo cp sync.sh /opt/authelia-config-sync/sync.sh
sudo chmod +x /opt/authelia-config-sync/sync.sh
sudo cp authelia-config-sync.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now authelia-config-sync.service
```

## Verification

```bash
sudo systemctl status authelia-config-sync.service
sudo tail -f /var/log/authelia-config-sync.log
```

End-to-end test: append a comment to `/opt/authelia/config/configuration.yml` and within ~2 seconds you should see in the log:
```
DETECTED change to configuration.yml
syncing /opt/authelia/config/... → /var/lib/docker/volumes/.../configuration.yml
restarting Authelia container (NEVER SIGHUP)
sync + restart complete
```

## Edit workflow going forward

```bash
sudo nano /opt/authelia/config/configuration.yml   # edit directly
# Save and exit. Within 2 seconds:
#  - file is copied to the volume
#  - Authelia container restarts
#  - new config is loaded
# Verify with: sudo docker logs --tail 5 authelia-...
```

No more manual `sudo cp` to the volume path. No more `docker restart`. The script does it.

## Limitations

- Only watches `configuration.yml`. If you ever add other configs (e.g. `users_database.yml`) you'll need to add them to the script.
- The container name is hardcoded (`authelia-hks48k8sg8o4co4co08co00o`). If Coolify ever recreates the Authelia Service from scratch, the new container name will differ and the script needs updating. (Coolify normally preserves UUIDs on redeploy; only Service deletion+recreation changes them.)
- Volume mount path is resolved dynamically at every sync, so volume UUID drift is handled.
- Hook restarts Authelia on every config write. If Authelia is critical for an active session, brief auth interruption (~3-5 seconds) is expected. To avoid this, edit during low-traffic windows.

## Why not bind mount the working dir directly?

Cleanest theoretical fix: change the Coolify Service compose to bind-mount `/opt/authelia/config` instead of using a named volume. Then the working copy IS the loaded config. But:
- Requires editing the Coolify Service's `docker_compose_raw`.
- Risk: if the bind-mount path is wrong on container start, Authelia exits and auth breaks for everything (including Coolify itself, which is behind Authelia).
- Migration step (copy data from named volume to bind dir) is non-zero risk.

The watcher is lower-risk because it leaves the working compose untouched and only adds an external sync layer. Volume can still be backed up the normal way; nothing in Coolify's lifecycle changes.
