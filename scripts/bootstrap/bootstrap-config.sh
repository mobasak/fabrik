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

# --- Generated keys storage ---
# Bootstrap writes generated WG keypairs here on the dev machine for safe-keeping
# (one source of truth for the mesh). Mode 600.
FABRIK_KEYS_DIR="${HOME}/.fabrik/keys/wireguard"
