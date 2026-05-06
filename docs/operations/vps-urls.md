# VPS1 Service URLs

<!-- AUTO-UPDATE: Run `python3 scripts/snapshot_vps_state.py` to refresh -->

**Last Updated:** 2026-05-06 22:06 UTC
**VPS:** vps1.ocoron.com (172.93.160.197) — Los Angeles, CA

All services use HTTPS via Traefik (Coolify-managed). HTTP redirects to HTTPS automatically.

---

<!-- AUTO:coolify_apps -->
| Name | FQDN | Status |
|---|---|---|
| `alertmanager` | internal | ⚠️ running:healthy |
| `apprise` | internal | ⚠️ running:healthy |
| `authelia` | internal | ⚠️ running:healthy |
| `backrest` | internal | ⚠️ running:unknown |
| `browserless` | https://browser.vps1.ocoron.com | ⚠️ running:unknown |
| `cadvisor` | internal | ⚠️ running:healthy |
| `fabrik-captcha` | internal | ⚠️ running:healthy |
| `fabrik-emailgateway` | internal | ⚠️ running:unknown |
| `fabrik-file-api` | internal | ⚠️ running:unknown |
| `fabrik-file-worker` | internal | ⚠️ running:unknown |
| `fabrik-image-broker` | internal | ⚠️ running:healthy |
| `fabrik-proxy` | https://proxy.vps1.ocoron.com | ⚠️ running:healthy |
| `fabrik-translator` | internal | ⚠️ running:healthy |
| `gatus` | internal | ⚠️ running:unknown |
| `glitchtip-web` | internal | ⚠️ running:unknown |
| `glitchtip-worker-v10` | internal | ⚠️ running:unknown |
| `gotenberg` | https://pdf.vps1.ocoron.com | ⚠️ running:healthy |
| `grafana` | internal | ⚠️ running:healthy |
| `loki` | internal | ⚠️ running:healthy |
| `meilisearch` | https://search.vps1.ocoron.com | ⚠️ running:healthy |
| `n8n` | internal | ⚠️ running:healthy |
| `netdata` | internal | ⚠️ running:healthy |
| `node-exporter` | internal | ⚠️ running:unknown |
| `postgres-main` | internal | ⚠️ running:healthy |
| `promtail` | internal | ⚠️ running:unknown |
| `site-provisioner` | internal | ⚠️ running:healthy |
<!-- /AUTO -->

## Maintenance Commands

```bash
# After VPS reboot — reapply infra memory limits (docker update resets on reboot)
ssh vps "bash /opt/fabrik/scripts/vps_apply_limits.sh"

# Residue audit — verify no test artifacts remain
cd /opt/fabrik && python3 scripts/vps_sync.py --verify

# Deploy a new service
cd /opt/fabrik && fabrik apply specs/services/<name>.yaml

# Redeploy existing service (git commit + push first)
cd /opt/fabrik && fabrik redeploy fabrik-<name>

# Weekly disk cleanup
ssh vps "sudo docker image prune -f && sudo docker builder prune -f"
```

## Port Reference

| Port | Binding | Purpose |
|---|---|---|
| 80 | `0.0.0.0:80` | HTTP (Traefik — redirects to HTTPS) |
| 443 | `0.0.0.0:443` | HTTPS (Traefik) + OpenVPN |
| 1194 | `0.0.0.0:1194` | OpenVPN TCP |
| 6001-6002 | `0.0.0.0:6001-6002` | Coolify Realtime (Soketi WebSocket) |
| 8000 | **UFW DENY** | Coolify raw — blocked, use domain |
| 8080 | `127.0.0.1:8080` | Traefik dashboard (localhost only) |
