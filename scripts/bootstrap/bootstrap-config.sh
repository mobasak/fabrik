#!/usr/bin/env bash
# Shared configuration for Fabrik multi-host bootstrap.
# Sourced by bootstrap-vps.sh and template-rendering helpers.
# Single source of truth for Wireguard mesh + firewall parameters.

# --- Wireguard mesh ---
# Hub-and-spoke topology. vps1 is the hub (10.99.0.1).
# Spokes get sequential IPs (vps2 = .2, vps3 = .3, ...).
# Subnet chosen to avoid common collisions:
#   - 10.0.0.0/24 used by Docker default bridge in many setups
#   - 10.8.0.0/24 commonly used by OpenVPN
#   - 192.168.0.0/16 commonly used by home LANs / WSL
#   - 10.99.0.0/24 is clean.
FABRIK_WG_SUBNET="10.99.0.0/24"
FABRIK_WG_HUB_IP="10.99.0.1"
FABRIK_WG_PORT="51820"

# MTU for the Wireguard interface.
# Standard ethernet MTU is 1500. Wireguard adds ~80 bytes (UDP+crypto headers),
# so the WG interface MTU must be <= 1420 to avoid fragmentation.
# Bootstrap script verifies with `ping -M do -s 1392 <peer>` and falls back
# to 1380 or 1300 if PMTU on the underlying network is lower.
FABRIK_WG_MTU=1420
FABRIK_WG_MTU_FALLBACKS=(1380 1300)

# Keepalive interval (seconds). 0 = off. 25s is the standard recommendation
# to keep NAT mappings alive on the spoke side; harmless on the hub side too.
FABRIK_WG_KEEPALIVE=25

# --- Public interfaces ---
# vps1 uses ens3 (verified 2026-05-31). Most GreenCloudVPS Ubuntu nodes use
# ens3 or eth0. Bootstrap script auto-detects and validates.
FABRIK_PUBLIC_IFACE_DEFAULT="ens3"
FABRIK_MESH_IFACE="wg0"

# --- Firewall: which ports are mesh-only (never public) ---
# Used by DOCKER-USER chain rules: ACCEPT from wg0, DROP from public iface.
# Add new ports here when new mesh-only services are introduced.
FABRIK_MESH_ONLY_PORTS=(
    5432    # postgres-main
    6379    # redis-main
    9090    # prometheus (scrape endpoint)
    9091    # authelia forward-auth
    9100    # node-exporter
    8080    # cadvisor + traefik internal API
    3100    # loki push API
    7700    # meilisearch
    8000    # glitchtip
)

# --- Public ports (must stay open to the internet) ---
FABRIK_PUBLIC_PORTS_TCP=(22 80 443)
FABRIK_PUBLIC_PORTS_UDP=("$FABRIK_WG_PORT")

# --- DNS ---
# Site-provisioner is the gateway for all DNS operations. Bootstrap calls it
# via HTTPS, never touches Cloudflare/Namecheap APIs directly.
FABRIK_SITE_PROVISIONER_URL="https://provision.vps1.ocoron.com"

# --- Let's Encrypt ---
# Email Traefik registers with the ACME endpoint when requesting certs on a spoke.
# Matches vps1's live config; verified 2026-06-02 against vps2's traefik.yml after
# the first successful issuance for canary.vps2.ocoron.com.
FABRIK_LE_EMAIL="ob@ocoron.com"

# --- Domain pattern ---
# Each VPS gets a wildcard subdomain. vps1 = *.vps1.ocoron.com (already in place),
# vps2 = *.vps2.ocoron.com, etc. Authelia subdomain shape: auth.vpsN.ocoron.com.
FABRIK_DOMAIN_ROOT="ocoron.com"
FABRIK_VPS_SUBDOMAIN_PATTERN="vps{N}.${FABRIK_DOMAIN_ROOT}"

# --- vps1 access (used to register new peers with the hub) ---
# Bootstrap script SSHes to vps1 from the dev machine running it, to append
# the new spoke's [Peer] block to /etc/wireguard/wg0.conf and reload.
# Uses the dev machine's existing `ssh vps` Host alias from ~/.ssh/config.
FABRIK_HUB_SSH_HOST="vps"

# --- Sudoer user on each VPS (matches vps1's posture) ---
# vps1 disables root SSH + password SSH and does all work via this user
# with NOPASSWD sudo. Bootstrap creates this user on each spoke as step 00,
# then disables root + password SSH after the user is verified to work.
FABRIK_SUDOER_USER="ozgur"

# --- Generated keys storage ---
# Bootstrap writes generated WG keypairs here on the dev machine for safe-keeping
# (one source of truth for the mesh). Mode 600.
FABRIK_KEYS_DIR="${HOME}/.fabrik/keys/wireguard"

# --- Hub-bootstrap (DR) constants ---
# Used by bootstrap-hub.sh to rebuild vps1 from scratch after disk loss.
# All of these are infrastructure constants, not secrets — the secrets
# come from the W9 GitHub DR mirror (mobasak/fabrik-dr-store) at runtime.

# Backblaze B2 bucket where Backrest stores restic snapshots.
# Endpoint format: s3:https://s3.<region>.backblazeb2.com/<bucket>
# Verified live 2026-06-01 against vps1's backrest container config.json.
FABRIK_RESTIC_REPO_URI="s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups"

# Cloudflare zone ID for ocoron.com. Used by --cf-rewrite-dns to retag every
# *.vps1.ocoron.com A record to the new VPS IP when the rebuild lands on a
# different public IP than the dead vps1.
# Verified live 2026-05-31 via the API; pinned here to avoid a runtime zone-list call.
FABRIK_CF_ZONE_ID="b3494f947c71683f94b6afe1331a1ba6"
FABRIK_CF_ZONE_NAME="ocoron.com"

# W9 DR-store layout. bootstrap-hub.sh clones this first thing to recover the
# fleet .env (without which restic cannot decrypt the snapshots).
FABRIK_DR_STORE_REPO="mobasak/fabrik-dr-store"
FABRIK_DR_STORE_ENV_LATEST="env/latest"            # → /opt/fabrik/.env
FABRIK_DR_STORE_SYSADMIN_LATEST="env/sysadmin-latest"  # → /opt/fabrik/.env.sysadmin

# Service start dependency order. Hub bootstrap walks this list end-to-end after
# /opt/ + Docker volumes are restored. Skips any /opt/<svc>/ that doesn't have
# a compose.yaml (covered by hub-restore-inventory.md § C).
FABRIK_HUB_SERVICE_START_ORDER=(
    postgres       # postgres-main — primary DB, no deps
    redis          # redis-main — sessions/auth state, no deps
    traefik        # public ingress + ACME, no deps
    authelia       # forward-auth, depends on redis
    monitoring     # prometheus + grafana + loki + alertmanager + cadvisor + node-exporter + promtail
    apprise        # notifier, no deps
    backrest       # backup engine, no deps
    gatus          # uptime probes, depends on traefik for cert
    glitchtip      # error tracking, depends on postgres + redis
    browserless    # headless chrome, no deps
    gotenberg      # PDF service, no deps
    meilisearch    # search engine, no deps
    n8n            # automation, depends on postgres
    site-provisioner  # DNS gateway, depends on postgres
    ocoron-com     # WordPress tenant, last
)

# /opt/<svc>/ dirs to EXCLUDE from the opt-configs Backrest plan + bootstrap restore.
# containerd = Docker daemon state (managed by Docker, not us)
# fabrik/.git = huge + regeneratable from GitHub
# backups/coolify_env_* = legacy Coolify-era dumps (W1 Phase C residue)
# */*restic-cache* = restic's own cache, not source data
FABRIK_OPT_RESTORE_EXCLUDES=(
    # NOTE: paths assume path-preserving bind mounts on the backrest container,
    # i.e. /opt:/opt:ro (not /opt:/backup-opt:ro). The W2 plan originally specified
    # /backup-opt naming, but that forces restore-time path mangling. Step 5 of
    # the DR-in-hours track changes the bind mounts to path-preserving — when
    # that lands, these excludes match restic snapshot paths 1:1.
    "/opt/containerd/**"
    "/opt/fabrik/.git/**"
    "/opt/backups/coolify_env_*.env"
    "/opt/*restic-cache*"
    "/opt/manually_installed.txt"  # human-edited marker file, not infra
)

# Host-state paths backed up by the new `host-state` Backrest plan (Step 5 of
# DR-in-hours track). Built from docs/operations/hub-restore-inventory.md § B.
# Path-preserving bind mounts (/etc:/etc:ro, /usr/local/bin:/usr/local/bin:ro,
# /root/.ssh:/root/.ssh:ro, /home/ozgur/.ssh:/home/ozgur/.ssh:ro,
# /var/spool/cron/crontabs:/var/spool/cron/crontabs:ro).
FABRIK_HOST_STATE_INCLUDES=(
    /etc/wireguard
    /etc/iptables
    /etc/ufw/user.rules
    /etc/ufw/user6.rules
    /etc/docker/daemon.json
    /etc/logrotate.d/vps-sysadmin-bot
    /etc/logrotate.d/vps-sysadmin-proactive
    /etc/systemd/system/vps-sysadmin-bot.service
    /etc/systemd/system/authelia-config-sync.service
    /etc/systemd/system/iptables-docker-user.service
    /etc/systemd/system/iptables-openvpn.service
    /etc/sudoers.d/ozgur
    /etc/sysctl.d/99-tuning.conf
    /etc/sysctl.d/99-openvpn.conf
    /etc/sysctl.conf
    /etc/cron.d/vps-sysadmin
    # NOTE: /var/spool/cron/crontabs/root is NOT in this list because the path
    # cannot be bind-mounted into the Backrest container (image symlink to
    # /etc/crontabs conflicts with our /etc:ro mount). Instead, pre-backup.sh
    # dumps `crontab -u root -l` to /opt/backups/root-crontab.txt nightly,
    # which is covered by the postgres-dumps plan. bootstrap-hub.sh step_16
    # reads that file and replays via `crontab -u root <file>`.
    /usr/local/bin/zellij
    /root/.ssh/authorized_keys
    /root/.ssh/known_hosts
    /home/ozgur/.ssh/authorized_keys
    /home/ozgur/.ssh/config
    /home/ozgur/.ssh/id_ed25519
    /home/ozgur/.ssh/id_ed25519.pub
    /home/ozgur/.ssh/known_hosts
)

# Host-state paths to NEVER restore (would clobber new-VPS-specific config).
# Critical safety list — these are network/identity facts of the NEW host,
# not the dead one.
FABRIK_HOST_STATE_EXCLUDES=(
    /etc/netplan/    # cloud-init writes new-VPS network config; restoring would lock us out
    /etc/hosts       # stock Ubuntu on vps1; new VPS may have provider-injected entries
    /etc/sysctl.d/10-*.conf  # Ubuntu defaults, come back via apt
)

# Docker named volumes to RESTORE (the rest regenerate from compose).
# Order matches dep order: data-stores first, then config-volumes.
FABRIK_HUB_VOLUMES_TO_RESTORE=(
    postgres-data                       # CRITICAL — Postgres master data
    redis_redis-data                    # CRITICAL — Redis main
    monitoring_grafana-data             # user dashboards
    monitoring_alertmanager-data        # silence state (small, OK)
    apprise-config                      # notifier config
    meilisearch-data                    # search indexes
    n8n-data                            # workflow defs + creds
    ocoron-com_db_data                  # WordPress MySQL
    ocoron-com_wp_html                  # WordPress files
    ocoron-com_backup_data              # tenant backups
)

# Docker volumes to EXCLUDE from backup AND restore (regenerate).
FABRIK_HUB_VOLUMES_TO_EXCLUDE=(
    monitoring_prometheus-data          # 15d retention, scrapes resume from new hub
    monitoring_loki-data                # regenerates from container stdout
    monitoring_promtail-positions       # tail offsets, recomputes
    ocoron-com_redis_data               # tenant session cache, ephemeral
)
