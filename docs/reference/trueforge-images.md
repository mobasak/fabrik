# TrueForge Container Images

**Total Images:** 120
**ARM64 Support:** 99/100 apps ✅ (only `deluge` is amd64-only)
**Registry:** `oci.trueforge.org/tccr/<name>`
**Source:** https://github.com/trueforge-org/containerforge
**Last Updated:** 2025-12-30

## Quick Commands

```bash
cd /opt/fabrik && source .venv/bin/activate

# List all images
python scripts/container_images.py trueforge list

# Check ARM64 support
python scripts/container_images.py check-arch oci.trueforge.org/tccr/<name>

# Pull an image
docker pull oci.trueforge.org/tccr/<name>:<tag>
```

## Complete Image Catalog

| Image | ARM64 | Registry URL | Category |
|-------|:-----:|--------------|----------|
| actions-runner | ✅ | oci.trueforge.org/tccr/actions-runner | CI/CD |
| adguardhome-sync | ✅ | oci.trueforge.org/tccr/adguardhome-sync | Network |
| airsonic-advanced | ✅ | oci.trueforge.org/tccr/airsonic-advanced | Media |
| alpine | ✅ | oci.trueforge.org/tccr/alpine | Base |
| apprise-api | ✅ | oci.trueforge.org/tccr/apprise-api | Notifications |
| autoscan | ✅ | oci.trueforge.org/tccr/autoscan | Media |
| balfolk-ics | ✅ | oci.trueforge.org/tccr/balfolk-ics | Utility |
| bazarr | ✅ | oci.trueforge.org/tccr/bazarr | Media (*arr) |
| build_cache | ⚠️ | oci.trueforge.org/tccr/build_cache | CI/CD |
| busybox | ⚠️ | oci.trueforge.org/tccr/busybox | Base |
| caddy | ✅ | oci.trueforge.org/tccr/caddy | Web Server |
| calibre-web | ✅ | oci.trueforge.org/tccr/calibre-web | Media |
| cloudflareddns | ✅ | oci.trueforge.org/tccr/cloudflareddns | DNS |
| cni-plugins | ✅ | oci.trueforge.org/tccr/cni-plugins | Kubernetes |
| code-server | ✅ | oci.trueforge.org/tccr/code-server | Development |
| davos | ⚠️ | oci.trueforge.org/tccr/davos | Download |
| db-wait-mariadb | ⚠️ | oci.trueforge.org/tccr/db-wait-mariadb | Database |
| db-wait-mongodb | ⚠️ | oci.trueforge.org/tccr/db-wait-mongodb | Database |
| db-wait-postgres | ⚠️ | oci.trueforge.org/tccr/db-wait-postgres | Database |
| db-wait-redis | ⚠️ | oci.trueforge.org/tccr/db-wait-redis | Database |
| deemix | ✅ | oci.trueforge.org/tccr/deemix | Media |
| deluge | ❌ | oci.trueforge.org/tccr/deluge | Download |
| devcontainer | ✅ | oci.trueforge.org/tccr/devcontainer | Development |
| doplarr | ✅ | oci.trueforge.org/tccr/doplarr | Media |
| duplicacy | ✅ | oci.trueforge.org/tccr/duplicacy | Backup |
| duplicati | ✅ | oci.trueforge.org/tccr/duplicati | Backup |
| emby | ✅ | oci.trueforge.org/tccr/emby | Media Server |
| esphome | ✅ | oci.trueforge.org/tccr/esphome | Home Automation |
| faster-whisper | ✅ | oci.trueforge.org/tccr/faster-whisper | AI/ML |
| flood | ✅ | oci.trueforge.org/tccr/flood | Download |
| foldingathome | ✅ | oci.trueforge.org/tccr/foldingathome | Science |
| gc | ⚠️ | oci.trueforge.org/tccr/gc | Utility |
| go-alpine | ⚠️ | oci.trueforge.org/tccr/go-alpine | Base |
| go-yq | ✅ | oci.trueforge.org/tccr/go-yq | Utility |
| golang | ✅ | oci.trueforge.org/tccr/golang | Base |
| hishtory-server | ✅ | oci.trueforge.org/tccr/hishtory-server | Development |
| home-assistant | ✅ | oci.trueforge.org/tccr/home-assistant | Home Automation |
| irqbalance | ✅ | oci.trueforge.org/tccr/irqbalance | System |
| it-tools | ✅ | oci.trueforge.org/tccr/it-tools | Utility |
| jackett | ✅ | oci.trueforge.org/tccr/jackett | Media (*arr) |
| java11 | ✅ | oci.trueforge.org/tccr/java11 | Base |
| java17 | ✅ | oci.trueforge.org/tccr/java17 | Base |
| java21 | ✅ | oci.trueforge.org/tccr/java21 | Base |
| java25 | ✅ | oci.trueforge.org/tccr/java25 | Base |
| java8 | ✅ | oci.trueforge.org/tccr/java8 | Base |
| jbops | ✅ | oci.trueforge.org/tccr/jbops | Media |
| jellyfin | ✅ | oci.trueforge.org/tccr/jellyfin | Media Server |
| jellyseer | ✅ | oci.trueforge.org/tccr/jellyseer | Media |
| jellyseerr | ⚠️ | oci.trueforge.org/tccr/jellyseerr | Media |
| k8s-sidecar | ✅ | oci.trueforge.org/tccr/k8s-sidecar | Kubernetes |
| kavita | ✅ | oci.trueforge.org/tccr/kavita | Media |
| kometa | ✅ | oci.trueforge.org/tccr/kometa | Media |
| kopia | ✅ | oci.trueforge.org/tccr/kopia | Backup |
| kube-sa-proxy | ✅ | oci.trueforge.org/tccr/kube-sa-proxy | Kubernetes |
| kubectl | ✅ | oci.trueforge.org/tccr/kubectl | Kubernetes |
| lazylibrarian | ✅ | oci.trueforge.org/tccr/lazylibrarian | Media |
| lidarr | ✅ | oci.trueforge.org/tccr/lidarr | Media (*arr) |
| lvm-disk-watcher | ✅ | oci.trueforge.org/tccr/lvm-disk-watcher | System |
| mariadb-client | ✅ | oci.trueforge.org/tccr/mariadb-client | Database |
| medusa | ✅ | oci.trueforge.org/tccr/medusa | Media |
| mergerfs | ✅ | oci.trueforge.org/tccr/mergerfs | Storage |
| minisatip | ✅ | oci.trueforge.org/tccr/minisatip | Media |
| mongosh | ✅ | oci.trueforge.org/tccr/mongosh | Database |
| nextcloud-fpm | ✅ | oci.trueforge.org/tccr/nextcloud-fpm | Cloud |
| nextcloud-imaginary | ✅ | oci.trueforge.org/tccr/nextcloud-imaginary | Cloud |
| nextcloud-notify-push | ✅ | oci.trueforge.org/tccr/nextcloud-notify-push | Cloud |
| nginx | ✅ | oci.trueforge.org/tccr/nginx | Web Server |
| node | ✅ | oci.trueforge.org/tccr/node | Base |
| nzbget | ✅ | oci.trueforge.org/tccr/nzbget | Download |
| nzbhydra2 | ✅ | oci.trueforge.org/tccr/nzbhydra2 | Download |
| ombi | ✅ | oci.trueforge.org/tccr/ombi | Media |
| opentofu-runner | ⚠️ | oci.trueforge.org/tccr/opentofu-runner | CI/CD |
| openvscode-server | ✅ | oci.trueforge.org/tccr/openvscode-server | Development |
| overseerr | ✅ | oci.trueforge.org/tccr/overseerr | Media |
| owntone | ⚠️ | oci.trueforge.org/tccr/owntone | Media |
| pairdrop | ⚠️ | oci.trueforge.org/tccr/pairdrop | File Sharing |
| piper | ✅ | oci.trueforge.org/tccr/piper | AI/ML |
| plex | ✅ | oci.trueforge.org/tccr/plex | Media Server |
| posterizarr | ⚠️ | oci.trueforge.org/tccr/posterizarr | Media |
| postgres-init | ⚠️ | oci.trueforge.org/tccr/postgres-init | Database |
| postgresql | ✅ | oci.trueforge.org/tccr/postgresql | Database |
| postgresql-client | ✅ | oci.trueforge.org/tccr/postgresql-client | Database |
| prowlarr | ✅ | oci.trueforge.org/tccr/prowlarr | Media (*arr) |
| pyload-ng | ✅ | oci.trueforge.org/tccr/pyload-ng | Download |
| python | ✅ | oci.trueforge.org/tccr/python | Base |
| python-alpine | ⚠️ | oci.trueforge.org/tccr/python-alpine | Base |
| python-node | ✅ | oci.trueforge.org/tccr/python-node | Base |
| qbitmanage | ✅ | oci.trueforge.org/tccr/qbitmanage | Download |
| qbittorrent | ✅ | oci.trueforge.org/tccr/qbittorrent | Download |
| qui | ✅ | oci.trueforge.org/tccr/qui | Utility |
| radarr | ✅ | oci.trueforge.org/tccr/radarr | Media (*arr) |
| readarr | ✅ | oci.trueforge.org/tccr/readarr | Media (*arr) |
| renovate | ✅ | oci.trueforge.org/tccr/renovate | CI/CD |
| requestrr | ✅ | oci.trueforge.org/tccr/requestrr | Media |
| resilio-sync | ✅ | oci.trueforge.org/tccr/resilio-sync | File Sync |
| rflood | ⚠️ | oci.trueforge.org/tccr/rflood | Download |
| sabnzbd | ✅ | oci.trueforge.org/tccr/sabnzbd | Download |
| scratch | ✅ | oci.trueforge.org/tccr/scratch | Base |
| seerr | ✅ | oci.trueforge.org/tccr/seerr | Media |
| shellcheck | ✅ | oci.trueforge.org/tccr/shellcheck | Development |
| smartctl-exporter | ✅ | oci.trueforge.org/tccr/smartctl-exporter | Monitoring |
| snapdrop | ✅ | oci.trueforge.org/tccr/snapdrop | File Sharing |
| sonarr | ✅ | oci.trueforge.org/tccr/sonarr | Media (*arr) |
| stash | ✅ | oci.trueforge.org/tccr/stash | Media |
| tautulli | ✅ | oci.trueforge.org/tccr/tautulli | Media |
| theme-park | ✅ | oci.trueforge.org/tccr/theme-park | Utility |
| tqm | ✅ | oci.trueforge.org/tccr/tqm | Utility |
| transmission | ✅ | oci.trueforge.org/tccr/transmission | Download |
| ubuntu | ✅ | oci.trueforge.org/tccr/ubuntu | Base |
| unifi-network-application | ✅ | oci.trueforge.org/tccr/unifi-network-application | Network |
| unpackerr | ✅ | oci.trueforge.org/tccr/unpackerr | Download |
| valkey-tools | ✅ | oci.trueforge.org/tccr/valkey-tools | Database |
| volsync | ⚠️ | oci.trueforge.org/tccr/volsync | Backup |
| vscode-tunnel | ⚠️ | oci.trueforge.org/tccr/vscode-tunnel | Development |
| watchtower | ✅ | oci.trueforge.org/tccr/watchtower | Container Mgmt |
| webhook | ✅ | oci.trueforge.org/tccr/webhook | Automation |
| whisparr | ✅ | oci.trueforge.org/tccr/whisparr | Media (*arr) |
| wud | ✅ | oci.trueforge.org/tccr/wud | Container Mgmt |
| wud-plus | ⚠️ | oci.trueforge.org/tccr/wud-plus | Container Mgmt |
| yq | ✅ | oci.trueforge.org/tccr/yq | Utility |

**Legend:**
- ✅ = ARM64 supported (verified from docker-bake.hcl)
- ❌ = AMD64 only
- ⚠️ = Not in apps/ folder (base images, verify before use)

## Fabrik-Relevant Images (ARM64 Ready)

| Image | Fabrik Use Case |
|-------|-----------------|
| **apprise-api** | ✅ Notification service for all Fabrik projects |
| **postgresql** | ✅ Supply-chain secure PostgreSQL for enterprise |
| **nginx** | ✅ Web server with attestations |
| **caddy** | ✅ Alternative web server with auto-HTTPS |
| **duplicati** | ✅ Backup solution (alternative to LinuxServer) |
| **code-server** | ✅ VS Code in browser for remote development |
| **faster-whisper** | ✅ Speech-to-text for transcription projects |
| **it-tools** | ✅ Developer utilities dashboard |
| **webhook** | ✅ Webhook receiver for automation |
| **renovate** | ✅ Dependency update automation |
| **home-assistant** | ✅ Home automation platform |
| **cloudflareddns** | ✅ Dynamic DNS updates for Cloudflare |

## Supply Chain Security Features

All TrueForge images include:
- **GitHub Actions attestations** - Verifiable build provenance
- **SBOM (Software Bill of Materials)** - Complete dependency inventory
- **Reproducible builds** - Consistent, auditable builds
- **Multi-arch support** - Most images support both amd64 and arm64
