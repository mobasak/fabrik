#!/usr/bin/env bash
#
# bootstrap-vps.sh — Fabrik W-Multi M1
#
# Turns a fresh Ubuntu 24.04 VPS into a Fabrik mesh spoke ready for
# `fabrik apply --target-vps <name>`.
#
# Usage:
#   ./bootstrap-vps.sh [OPTIONS] root@<new-vps-ip-or-host> <spoke-name>
#
# Examples:
#   ./bootstrap-vps.sh root@10.20.30.40 vps2
#   ./bootstrap-vps.sh --dry-run root@10.20.30.40 vps2
#   ./bootstrap-vps.sh --verify ozgur@vps2.greencloudvps.com vps2
#
# Options:
#   --dry-run   Print every command that would run; make no changes.
#   --verify    Read-only mode: check current state, report missing pieces.
#   --skip-mesh Skip Wireguard mesh setup (test pre-mesh steps only).
#   --skip-dns  Skip DNS work (assumes you'll create *.vpsN.ocoron.com
#               records out-of-band; bootstrap will not call site-provisioner).
#   --help      Show this message.
#
# Idempotency: every step checks current state before mutating. Safe to
# re-run after a partial failure.
#
# Manual prereqs (do these once before running the script):
#   - GreenCloudVPS instance provisioned, Ubuntu 24.04 LTS
#   - You can SSH in as root or a sudoer (use the password the provider emails,
#     then drop your pubkey into ~/.ssh/authorized_keys manually)
#   - Your dev machine has a working `ssh vps` alias to vps1 (the hub)
#   - vps1 has Wireguard running (M0c done — verified by preflight)
#
# What this script DOES (numbered to match the step_NN_ functions below):
#   01. Harden SSH on the spoke (disable root login, disable password auth)
#   02. Install UFW + fail2ban; open 22/80/443/51820
#   03. Install Docker; configure log rotation; create the 'fabrik' Docker network
#   04. Install Wireguard + iptables-persistent
#   05. Generate a fresh Wireguard keypair on the spoke (private key never leaves)
#   06. Register the spoke as a [Peer] on the hub's /etc/wireguard/wg0.conf
#   07. Render the spoke's /etc/wireguard/wg0.conf with the hub's endpoint
#   08. Bring up wg-quick@wg0 on the spoke
#   09. PMTU probe; fall back to MTU=1380 then 1300 if 1420 fails
#   10. Apply DOCKER-USER iptables chain rules (mesh-allow + public-block)
#   11. [STUB] Install lightweight monitoring agents — implemented in M1b
#   12. [STUB] Create *.<spoke>.ocoron.com DNS via site-provisioner — M1b
#
# What this script does NOT do:
#   - Create the user account / copy SSH keys (assumed done; see Manual prereqs)
#   - Deploy any tenant workloads (use `fabrik apply --target-vps` for that)
#   - Migrate data from another host
#   - Configure tenant-specific secrets

set -euo pipefail

# ---------------------------------------------------------------------------
# Pre-flight — locate ourselves + load shared config
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./bootstrap-config.sh
source "${SCRIPT_DIR}/bootstrap-config.sh"

# ---------------------------------------------------------------------------
# Flag parsing
# ---------------------------------------------------------------------------

DRY_RUN=false
VERIFY=false
SKIP_MESH=false
SKIP_DNS=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)   DRY_RUN=true; shift ;;
        --verify)    VERIFY=true; shift ;;
        --skip-mesh) SKIP_MESH=true; shift ;;
        --skip-dns)  SKIP_DNS=true; shift ;;
        --help|-h)
            sed -n '/^# Usage:/,/^# What this script does NOT do:/p' "${BASH_SOURCE[0]}" \
                | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        --*)
            echo "ERROR: unknown flag '$1'. Use --help for usage." >&2
            exit 2
            ;;
        *)
            break
            ;;
    esac
done

if [[ $# -ne 2 ]]; then
    echo "ERROR: expected exactly 2 positional args: <user@host> <spoke-name>" >&2
    echo "Run with --help for usage." >&2
    exit 2
fi

REMOTE="$1"        # e.g. root@10.20.30.40 or ozgur@vps2.greencloudvps.com
SPOKE_NAME="$2"    # e.g. vps2

# Spoke-name validation: lowercase alphanum + dashes, starts with 'vps' followed by digits
if [[ ! "$SPOKE_NAME" =~ ^vps[0-9]+$ ]]; then
    echo "ERROR: spoke name must match ^vps[0-9]+$ (e.g. vps2, vps10). Got: $SPOKE_NAME" >&2
    exit 2
fi

SPOKE_NUM="${SPOKE_NAME#vps}"
SPOKE_MESH_IP="10.99.0.${SPOKE_NUM}"

if [[ "$SPOKE_NUM" -lt 2 || "$SPOKE_NUM" -gt 254 ]]; then
    echo "ERROR: spoke number must be 2..254 (vps1 is the hub, 0/255 are reserved)" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

c_reset='\033[0m'
c_dim='\033[2m'
c_red='\033[31m'
c_green='\033[32m'
c_yellow='\033[33m'
c_blue='\033[34m'

# Strip colors if stdout isn't a TTY (CI / pipe).
if [[ ! -t 1 ]]; then
    c_reset='' c_dim='' c_red='' c_green='' c_yellow='' c_blue=''
fi

log()   { echo -e "${c_blue}[bootstrap]${c_reset} $*"; }
ok()    { echo -e "${c_green}[ ok ]${c_reset} $*"; }
warn()  { echo -e "${c_yellow}[WARN]${c_reset} $*"; }
err()   { echo -e "${c_red}[FAIL]${c_reset} $*" >&2; }
dim()   { echo -e "${c_dim}$*${c_reset}"; }

# Effective SSH target. Starts as ${REMOTE} (typically root@<ip> on a freshly
# provisioned VPS). Step 00 creates the unprivileged sudoer user matching
# vps1's posture (default 'ozgur') and switches EFFECTIVE_REMOTE to that user.
# All subsequent steps run as the sudoer, not as root.
EFFECTIVE_REMOTE="${REMOTE}"

# Run a command on the remote VPS. In dry-run, print only.
# In verify, only allow read-only commands (best-effort; not enforced strictly).
remote() {
    local cmd="$*"
    if $DRY_RUN; then
        dim "    [dry-run] ssh ${EFFECTIVE_REMOTE} '${cmd}'"
        return 0
    fi
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${EFFECTIVE_REMOTE}" "${cmd}"
}

# Run a command on the remote VPS as the INITIAL user (root). Used by step 00
# only — before we've created the sudoer.
remote_as_initial() {
    local cmd="$*"
    if $DRY_RUN; then
        dim "    [dry-run] ssh ${REMOTE} '${cmd}'"
        return 0
    fi
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${REMOTE}" "${cmd}"
}

# Run a command on the hub (vps1) via the local `ssh vps` alias.
hub() {
    local cmd="$*"
    if $DRY_RUN; then
        dim "    [dry-run] ssh ${FABRIK_HUB_SSH_HOST} '${cmd}'"
        return 0
    fi
    ssh -o ConnectTimeout=10 "${FABRIK_HUB_SSH_HOST}" "${cmd}"
}

# ---------------------------------------------------------------------------
# Pre-flight checks (always run, even in --verify)
# ---------------------------------------------------------------------------

preflight() {
    log "preflight checks ..."

    # 1. We can reach the remote VPS via SSH
    if ! ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
            -o BatchMode=yes "${REMOTE}" 'echo ok' &>/dev/null; then
        err "cannot SSH to ${REMOTE}. Confirm: (a) the host is reachable, (b) your SSH key is in the new VPS's authorized_keys, (c) the user exists."
        return 1
    fi
    ok "SSH to ${REMOTE} works"

    # 2. We can reach the hub (vps1)
    if ! hub 'echo ok' &>/dev/null; then
        err "cannot SSH to hub (${FABRIK_HUB_SSH_HOST}). Need this to register the spoke as a Wireguard peer."
        return 1
    fi
    ok "SSH to hub (${FABRIK_HUB_SSH_HOST}) works"

    # 3. Hub has Wireguard running
    local hub_state
    hub_state=$(hub 'sudo systemctl is-active wg-quick@wg0' 2>/dev/null || echo 'inactive')
    if [[ "$hub_state" != "active" ]]; then
        err "hub's wg-quick@wg0 is '${hub_state}', expected 'active'. Run M0c (setup-wireguard-hub) on vps1 first."
        return 1
    fi
    ok "hub's Wireguard is active"

    # 4. Spoke IP doesn't collide with existing peer
    if hub "sudo grep -q 'AllowedIPs = ${SPOKE_MESH_IP}/32' /etc/wireguard/wg0.conf 2>/dev/null"; then
        warn "spoke IP ${SPOKE_MESH_IP} is already registered on the hub. Idempotent rerun will reuse it."
    fi

    # 5. Spoke name doesn't collide
    if hub "sudo grep -q '# === peer: ${SPOKE_NAME} ' /etc/wireguard/wg0.conf 2>/dev/null"; then
        warn "spoke name ${SPOKE_NAME} already has a peer block on the hub. Idempotent rerun will update it."
    fi

    return 0
}

# ---------------------------------------------------------------------------
# Step blocks — each block is idempotent
# ---------------------------------------------------------------------------

step_00_create_sudo_user() {
    # Match vps1's posture: no root SSH, no password SSH, all work via an
    # unprivileged sudoer (default: 'ozgur') with NOPASSWD. This step runs
    # FIRST as root, creates the user, copies the SSH key, adds sudoers entry,
    # and switches EFFECTIVE_REMOTE so subsequent steps run as the sudoer.
    local user="${FABRIK_SUDOER_USER}"
    log "step 00: create sudoer user '${user}' (matches vps1 posture)"

    # Determine the public key to install for the sudoer.
    # Strategy: scan common pubkey paths in modern→legacy order and pick the
    # first existing one. SSH itself may have many IdentityFile candidates;
    # we just need ONE working pubkey to install. (Earlier we tried ssh -G's
    # first identityfile, which on Ubuntu defaults to id_rsa even when the
    # user actually uses id_ed25519 — wrong.)
    local pubkey=""
    if ! $DRY_RUN; then
        local candidates=(
            "${HOME}/.ssh/id_ed25519.pub"
            "${HOME}/.ssh/id_ecdsa.pub"
            "${HOME}/.ssh/id_rsa.pub"
        )
        # Also probe whatever ssh -G says, in case the user has a custom key
        local ssh_g_identity
        ssh_g_identity=$(ssh -G "${REMOTE}" 2>/dev/null | awk '/^identityfile / {print $2}' | head -3)
        while IFS= read -r f; do
            f="${f/#\~/$HOME}"
            [[ -n "$f" ]] && candidates+=("${f}.pub")
        done <<<"$ssh_g_identity"

        for candidate in "${candidates[@]}"; do
            if [[ -f "$candidate" ]]; then
                pubkey=$(cat "$candidate")
                log "  using key: ${candidate}"
                break
            fi
        done

        if [[ -z "$pubkey" ]]; then
            err "step 00: cannot find any public key in:"
            printf '         %s\n' "${candidates[@]}" >&2
            return 1
        fi
    fi

    # Create the user, install the SSH key, grant NOPASSWD sudo. Idempotent.
    remote_as_initial "sudo bash -c '
        if ! id ${user} >/dev/null 2>&1; then
            useradd -m -s /bin/bash ${user}
        fi
        mkdir -p /home/${user}/.ssh
        # Append key if not already present (idempotent)
        grep -qxF \"${pubkey}\" /home/${user}/.ssh/authorized_keys 2>/dev/null || \
            echo \"${pubkey}\" >> /home/${user}/.ssh/authorized_keys
        chown -R ${user}:${user} /home/${user}/.ssh
        chmod 700 /home/${user}/.ssh
        chmod 600 /home/${user}/.ssh/authorized_keys
        # NOPASSWD sudoers entry (in /etc/sudoers.d/ to avoid editing main file)
        echo \"${user} ALL=(ALL) NOPASSWD:ALL\" > /etc/sudoers.d/90-${user}
        chmod 440 /etc/sudoers.d/90-${user}
    '"

    # Verify the new user works with SSH + sudo
    if ! $DRY_RUN; then
        local host="${REMOTE#*@}"
        local sudo_check
        sudo_check=$(ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
            "${user}@${host}" "sudo -n whoami" 2>&1 || echo FAIL)
        if [[ "$sudo_check" != "root" ]]; then
            err "step 00: sudoer ${user}@${host} cannot run sudo without password"
            err "         got: ${sudo_check}"
            return 1
        fi
    fi

    # Switch EFFECTIVE_REMOTE so all subsequent steps run as the sudoer
    local host="${REMOTE#*@}"
    EFFECTIVE_REMOTE="${user}@${host}"
    ok "step 00 done — subsequent steps run as ${EFFECTIVE_REMOTE}"
}

step_01_harden_ssh() {
    log "step 01: harden SSH (no root login, no password auth) — matches vps1"
    # SAFE NOW: step 00 created '${FABRIK_SUDOER_USER}' with key + NOPASSWD sudo
    # AND verified it works. So disabling root SSH entirely (matching vps1's
    # posture) is safe — we always have the sudoer to fall back on. This is
    # the correct, strict posture: 'PermitRootLogin no' (not prohibit-password).
    remote "sudo sed -i \
        -e 's/^#*PermitRootLogin.*/PermitRootLogin no/' \
        -e 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' \
        /etc/ssh/sshd_config && \
        sudo systemctl reload ssh 2>/dev/null || sudo systemctl reload sshd"
    ok "step 01 done — root SSH disabled, password auth disabled"
}

step_02_install_firewall_fail2ban() {
    log "step 02: install UFW + fail2ban; open public ports"
    remote 'sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq && \
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ufw fail2ban'
    # Lesson 68 hardening: a prior `apt remove ufw` (without --purge) leaves the
    # package in `rc` state (config files remain, binary purged). `apt install`
    # normally brings it back to `ii`, but if `ufw` is still missing from PATH,
    # the install was incomplete — force a reinstall.
    remote 'STATUS=$(dpkg -l ufw 2>/dev/null | awk "/^(ii|rc)/ {print \$1; exit}")
        if [ "$STATUS" = "rc" ] || ! command -v ufw >/dev/null; then
            sudo DEBIAN_FRONTEND=noninteractive apt-get install --reinstall -y -qq ufw
        fi
        command -v ufw >/dev/null || { echo "ERR: ufw binary missing after reinstall"; exit 1; }
        sudo systemctl is-active ufw >/dev/null 2>&1 || sudo systemctl enable ufw'
    for port in "${FABRIK_PUBLIC_PORTS_TCP[@]}"; do
        remote "sudo ufw allow ${port}/tcp 2>&1 | tail -1"
    done
    for port in "${FABRIK_PUBLIC_PORTS_UDP[@]}"; do
        remote "sudo ufw allow ${port}/udp 2>&1 | tail -1"
    done
    # Allow ANY port inbound from the WG mesh subnet (10.99.0.0/24).
    # Without this, vps1's Prometheus cannot scrape spoke node-exporter:9100 /
    # cadvisor:8080 / promtail:9080 — UFW default-deny silently breaks spoke
    # observability. Single-operator threat model: mesh is trusted; no per-port
    # filtering needed for cross-host traffic. (W8 finding 2026-06-01: this gap
    # silently broke spoke scrape targets for ~24h after W1 enabled UFW.)
    remote "sudo ufw allow from ${FABRIK_WG_SUBNET} comment 'mesh — fleet observability + cross-host calls' 2>&1 | tail -1"
    remote 'echo y | sudo ufw enable 2>&1 | tail -1'
    remote 'sudo systemctl enable --now fail2ban'
    # Self-verify (Lesson 68): both must be true at end of step.
    remote 'command -v ufw >/dev/null && [ "$(dpkg -l ufw | awk "/^ii/ {print \$2}")" = "ufw" ]' \
        || { err "step 02: ufw not properly installed (rc-state or binary missing)"; return 1; }
    remote 'sudo systemctl is-active ufw >/dev/null && sudo ufw status | grep -q "Status: active"' \
        || { err "step 02: ufw service or status not active"; return 1; }
    ok "step 02 done"
}

step_03_install_docker() {
    log "step 03: install Docker + log rotation + create 'fabrik' network"
    remote 'if ! command -v docker >/dev/null; then \
        curl -fsSL https://get.docker.com | sudo sh; \
        fi'
    # Log rotation policy matches vps1 (10m × 3 files)
    # daemon.json — log rotation + container tag for promtail's container_name
    # label extraction. The `tag` field was missing pre-W4 (2026-06-02) which
    # left spoke logs in Loki without container_name, breaking per-container
    # log queries. Bootstrap now emits it always.
    remote 'sudo tee /etc/docker/daemon.json >/dev/null <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3",
    "tag": "{{.Name}}"
  }
}
EOF
    sudo systemctl restart docker'
    # Create fabrik network if missing
    remote 'sudo docker network inspect fabrik >/dev/null 2>&1 || sudo docker network create fabrik'
    # Pre-seed github.com host key for root (fabrik SSH deployer git-clones as root).
    # Without this, every first git-source deploy fails with "Host key verification failed".
    remote 'sudo bash -c "mkdir -p /root/.ssh && chmod 700 /root/.ssh && \
        touch /root/.ssh/known_hosts && chmod 644 /root/.ssh/known_hosts && \
        grep -q \"^github.com \" /root/.ssh/known_hosts || \
        ssh-keyscan -t ed25519,rsa github.com 2>/dev/null >> /root/.ssh/known_hosts"'
    ok "step 03 done"
}

step_04_install_wireguard() {
    log "step 04: install Wireguard + iptables-persistent on the spoke"
    remote 'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq wireguard iptables-persistent'
    ok "step 04 done"
}

step_05_generate_spoke_keypair() {
    log "step 05: generate Wireguard keypair on the spoke (private key never leaves)"
    remote '
        sudo bash -c "
            umask 077
            mkdir -p /etc/wireguard
            cd /etc/wireguard
            if [ ! -f spoke.privatekey ]; then
                wg genkey > spoke.privatekey
                chmod 600 spoke.privatekey
            fi
            if [ ! -f spoke.publickey ]; then
                cat spoke.privatekey | wg pubkey > spoke.publickey
                chmod 644 spoke.publickey
            fi
        "
    '
    ok "step 05 done"
}

step_06_register_with_hub() {
    log "step 06: register this spoke with the hub"
    local spoke_pubkey
    if $DRY_RUN; then
        spoke_pubkey='<spoke-public-key-fetched-at-runtime>'
    else
        spoke_pubkey=$(remote 'sudo cat /etc/wireguard/spoke.publickey')
    fi
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Build the peer block locally
    local peer_block="
# === peer: ${SPOKE_NAME} (added ${timestamp}) ===
[Peer]
PublicKey = ${spoke_pubkey}
AllowedIPs = ${SPOKE_MESH_IP}/32
PersistentKeepalive = ${FABRIK_WG_KEEPALIVE}
"

    if $DRY_RUN; then
        dim "    [dry-run] would append the following block to hub's /etc/wireguard/wg0.conf:"
        echo "$peer_block" | sed 's/^/        /'
    else
        # Idempotency: if the peer block for this spoke already exists, replace it.
        # Strategy: use a marker comment ('# === peer: <name> ') and delete from marker
        # to the next '# === peer:' marker or EOF, then append the new block.
        hub "sudo python3 -c \"
import re, sys
with open('/etc/wireguard/wg0.conf') as f: c = f.read()
marker = '# === peer: ${SPOKE_NAME} '
if marker in c:
    pattern = r'\\n# === peer: ${SPOKE_NAME} .*?(?=\\n# === peer:|\\Z)'
    c = re.sub(pattern, '', c, flags=re.DOTALL)
peer_block = '''${peer_block}'''
c = c.rstrip() + peer_block
with open('/etc/wireguard/wg0.conf', 'w') as f: f.write(c)
print('hub config updated')
\""
        # Reload the hub's wg interface. Use a tempfile instead of process
        # substitution because <(...) doesn't survive single-quote wrapping
        # through the SSH command chain. (Confirmed by vps2 bootstrap 2026-05-31:
        # fopen failed with "No such file or directory" on /dev/fd/<N>.)
        hub 'sudo bash -c "wg-quick strip wg0 > /run/wg0.stripped.tmp && \
            wg syncconf wg0 /run/wg0.stripped.tmp; rc=\$?; \
            rm -f /run/wg0.stripped.tmp; exit \$rc"'
    fi
    ok "step 06 done"
}

step_07_render_spoke_wg_config() {
    log "step 07: render the spoke's wg0.conf"

    local hub_pubkey
    if $DRY_RUN; then
        hub_pubkey='<hub-public-key>'
    else
        hub_pubkey=$(hub 'sudo cat /etc/wireguard/hub.publickey')
    fi
    local hub_public_ip
    if $DRY_RUN; then
        hub_public_ip='<hub-public-ip>'
    else
        hub_public_ip=$(hub "ip route get 1.1.1.1 | awk '/src/ {print \$7; exit}'")
    fi

    remote "sudo bash -c \"cat > /etc/wireguard/wg0.conf <<WGEOF
# Spoke Wireguard configuration for ${SPOKE_NAME}.
# Rendered $(date -u +%Y-%m-%dT%H:%M:%SZ) by bootstrap-vps.sh
[Interface]
PrivateKey = \\\$(cat /etc/wireguard/spoke.privatekey)
Address = ${SPOKE_MESH_IP}/24
MTU = ${FABRIK_WG_MTU}
PostUp = iptables -t mangle -A FORWARD -o %i -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
PostDown = iptables -t mangle -D FORWARD -o %i -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu

[Peer]
PublicKey = ${hub_pubkey}
Endpoint = ${hub_public_ip}:${FABRIK_WG_PORT}
AllowedIPs = ${FABRIK_WG_SUBNET}
PersistentKeepalive = ${FABRIK_WG_KEEPALIVE}
WGEOF
chmod 600 /etc/wireguard/wg0.conf\""
    ok "step 07 done"
}

step_08_bring_up_mesh() {
    log "step 08: bring up wg-quick@wg0 on the spoke"
    remote 'sudo systemctl enable --now wg-quick@wg0'
    # Sleep briefly to let the first handshake happen
    if ! $DRY_RUN; then sleep 4; fi
    ok "step 08 done"
}

step_09_verify_mesh_with_pmtu_probe() {
    log "step 09: PMTU probe and MTU fallback if needed"
    if $DRY_RUN; then
        dim "    [dry-run] would ping -M do -s 1392 ${FABRIK_WG_HUB_IP} from spoke; on fail, drop MTU to ${FABRIK_WG_MTU_FALLBACKS[*]}"
        return 0
    fi

    local mtus=("$FABRIK_WG_MTU" "${FABRIK_WG_MTU_FALLBACKS[@]}")
    local success_mtu=""
    for try_mtu in "${mtus[@]}"; do
        # Payload size for ping -s = MTU - 28 (IPv4 header + ICMP header)
        local payload=$(( try_mtu - 28 ))
        if remote "ping -M do -s ${payload} -c 2 -W 3 ${FABRIK_WG_HUB_IP}" &>/dev/null; then
            success_mtu="$try_mtu"
            break
        fi
        warn "MTU ${try_mtu} failed PMTU probe; trying next"
        # Drop MTU on the interface and retry
        remote "sudo ip link set dev wg0 mtu ${try_mtu}"
    done

    if [[ -z "$success_mtu" ]]; then
        err "all MTU values failed PMTU probe. Check upstream firewall / Wireguard handshake."
        remote 'sudo wg show'
        return 1
    fi

    if [[ "$success_mtu" != "$FABRIK_WG_MTU" ]]; then
        warn "MTU fell back to ${success_mtu} (configured: ${FABRIK_WG_MTU}). Updating /etc/wireguard/wg0.conf"
        remote "sudo sed -i 's/^MTU = .*/MTU = ${success_mtu}/' /etc/wireguard/wg0.conf"
    fi

    ok "PMTU probe passed at MTU=${success_mtu}"
}

step_10_apply_firewall_rules() {
    log "step 10: apply DOCKER-USER iptables chain rules"
    local public_iface
    if $DRY_RUN; then
        public_iface='<auto-detected>'
    else
        public_iface=$(remote "ip route get 1.1.1.1 | awk '/dev/ {print \$5; exit}'")
        if [[ -z "$public_iface" ]]; then
            warn "could not auto-detect public interface; falling back to ${FABRIK_PUBLIC_IFACE_DEFAULT}"
            public_iface="$FABRIK_PUBLIC_IFACE_DEFAULT"
        fi
    fi

    local mesh_ports="${FABRIK_MESH_ONLY_PORTS[*]}"
    local mesh_ports_csv="${mesh_ports// /,}"

    remote "sudo bash -c '
        # Allow everything from wg0
        iptables -C DOCKER-USER -i ${FABRIK_MESH_IFACE} -j ACCEPT 2>/dev/null || \
            iptables -I DOCKER-USER -i ${FABRIK_MESH_IFACE} -j ACCEPT

        # Block mesh-only ports from public iface
        iptables -C DOCKER-USER -i ${public_iface} -p tcp -m multiport --dports ${mesh_ports_csv} -j DROP 2>/dev/null || \
            iptables -I DOCKER-USER -i ${public_iface} -p tcp -m multiport --dports ${mesh_ports_csv} -j DROP

        mkdir -p /etc/iptables
        iptables-save > /etc/iptables/rules.v4
        systemctl enable netfilter-persistent >/dev/null 2>&1 || true
    '"
    ok "step 10 done"
}

step_11_install_monitoring_agents() {
    log "step 11: install monitoring agents shipping to vps1 over mesh"
    if $DRY_RUN; then
        dim "    [dry-run] would scp 2 templates to /opt/monitoring-agent/ and docker compose up -d"
        return 0
    fi

    # Render the compose + promtail config locally with the spoke's mesh IP,
    # spoke name, hub mesh IP. Push via /tmp then sudo mv to /opt/monitoring-agent/.
    local tmpdir
    tmpdir=$(mktemp -d -t fabrik-monitoring-agent-XXXX)
    trap "rm -rf '$tmpdir'" RETURN

    # Substitute templates (envsubst would also work; using sed for portability)
    sed \
        -e "s|{{SPOKE_NAME}}|${SPOKE_NAME}|g" \
        -e "s|{{SPOKE_MESH_IP}}|${SPOKE_MESH_IP}|g" \
        -e "s|{{HUB_MESH_IP}}|${FABRIK_WG_HUB_IP}|g" \
        "${SCRIPT_DIR}/templates/monitoring-agent.compose.yaml.template" \
        > "${tmpdir}/compose.yaml"
    sed \
        -e "s|{{SPOKE_NAME}}|${SPOKE_NAME}|g" \
        -e "s|{{SPOKE_MESH_IP}}|${SPOKE_MESH_IP}|g" \
        -e "s|{{HUB_MESH_IP}}|${FABRIK_WG_HUB_IP}|g" \
        "${SCRIPT_DIR}/templates/promtail.yaml.template" \
        > "${tmpdir}/promtail.yaml"

    # scp to /tmp on the spoke, then sudo mv into place
    scp -q "${tmpdir}/compose.yaml" "${tmpdir}/promtail.yaml" \
        "${EFFECTIVE_REMOTE}:/tmp/"
    remote "sudo mkdir -p /opt/monitoring-agent && \
        sudo mv /tmp/compose.yaml /opt/monitoring-agent/compose.yaml && \
        sudo mv /tmp/promtail.yaml /opt/monitoring-agent/promtail.yaml && \
        sudo chown -R root:root /opt/monitoring-agent && \
        sudo chmod 644 /opt/monitoring-agent/*.yaml"

    # Bring up the stack
    remote "cd /opt/monitoring-agent && sudo docker compose up -d --remove-orphans"

    # Verify all 3 containers up
    sleep 4
    remote 'sudo docker ps --filter name=node-exporter --filter name=cadvisor --filter name=promtail --format "{{.Names}} {{.Status}}"'

    ok "step 11 done — monitoring agents shipping to vps1's Loki + ready to be scraped"
}

step_12_install_spoke_traefik() {
    log "step 12: install spoke Traefik (TLS termination + Let's Encrypt + W15 gzip middleware)"
    if $DRY_RUN; then
        dim "    [dry-run] would scp 3 templates to /opt/traefik/ and docker compose up -d"
        return 0
    fi

    # Bootstrapped from W16 (2026-06-02). Replaces the prior manual step
    # documented in vps-bootstrap-plan.md. Bakes in the W15 labels block
    # from the live vps2/vps3 fix so future spokes get the `gzip@docker`
    # middleware definition on first bootstrap — no post-bootstrap edit
    # required.

    local tmpdir
    tmpdir=$(mktemp -d -t fabrik-spoke-traefik-XXXX)
    trap "rm -rf '$tmpdir'" RETURN

    # Render templates. compose.yaml has no substitutions (W15 labels are
    # static); traefik.yml needs the LE email; authelia.yml needs the hub
    # mesh IP + domain root for the forward-auth address.
    cp "${SCRIPT_DIR}/templates/traefik.compose.yaml.template" \
       "${tmpdir}/compose.yaml"

    sed \
        -e "s|{{LE_EMAIL}}|${FABRIK_LE_EMAIL}|g" \
        "${SCRIPT_DIR}/templates/traefik.yml.template" \
        > "${tmpdir}/traefik.yml"

    sed \
        -e "s|{{HUB_MESH_IP}}|${FABRIK_WG_HUB_IP}|g" \
        -e "s|{{FABRIK_DOMAIN_ROOT}}|${FABRIK_DOMAIN_ROOT}|g" \
        "${SCRIPT_DIR}/templates/traefik-dynamic-authelia.yml.template" \
        > "${tmpdir}/authelia.yml"

    # scp to /tmp on the spoke, then sudo mv into /opt/traefik/.
    scp -q "${tmpdir}/compose.yaml" \
           "${tmpdir}/traefik.yml" \
           "${tmpdir}/authelia.yml" \
        "${EFFECTIVE_REMOTE}:/tmp/"

    remote "sudo mkdir -p /opt/traefik/dynamic && \
        sudo mv /tmp/compose.yaml /opt/traefik/compose.yaml && \
        sudo mv /tmp/traefik.yml /opt/traefik/traefik.yml && \
        sudo mv /tmp/authelia.yml /opt/traefik/dynamic/authelia.yml && \
        sudo touch /opt/traefik/acme.json && \
        sudo chmod 600 /opt/traefik/acme.json && \
        sudo chown -R root:root /opt/traefik && \
        sudo chmod 644 /opt/traefik/compose.yaml /opt/traefik/traefik.yml /opt/traefik/dynamic/authelia.yml"

    # Bring up the stack.
    remote "cd /opt/traefik && sudo docker compose up -d"

    # Verify.
    sleep 3
    remote 'sudo docker ps --filter name=traefik --format "{{.Names}} {{.Status}}"'

    ok "step 12 done — Traefik up; gzip@docker middleware published; ready for fabrik apply"
}

step_13_create_dns_records() {
    log "step 13: create DNS records (apex + wildcard) via site-provisioner"
    if $SKIP_DNS; then
        warn "step 13 skipped (--skip-dns)"
        return 0
    fi
    if $DRY_RUN; then
        dim "    [dry-run] would call site-provisioner to ensure:"
        dim "      ${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT}   A → <spoke public IP>"
        dim "      *.${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT} A → <spoke public IP>"
        return 0
    fi

    # Wired by W16 part 2 (2026-06-02). Calls site-provisioner from vps1
    # because (a) vps1's public IP is in the Traefik IP allowlist, and (b)
    # the production API_KEY lives in /opt/site-provisioner/.env on vps1
    # — never travels to the dev machine. The /subdomain endpoint uses
    # ensure_record() which is idempotent: re-running returns
    # `action: unchanged` instead of touching Cloudflare.

    # Discover the spoke's public IPv4. The mesh IP (10.99.0.x) is internal
    # and would not satisfy Let's Encrypt's HTTP-01 challenge (which must
    # reach the spoke from the public internet). Use ifconfig.me with an
    # icanhazip.com fallback.
    local spoke_pub_ip
    spoke_pub_ip=$(remote 'curl -4 -fsS -m 10 https://ifconfig.me 2>/dev/null || curl -4 -fsS -m 10 https://ipv4.icanhazip.com 2>/dev/null' | tr -d '[:space:]')
    if [[ -z "${spoke_pub_ip}" ]]; then
        err "step 13: could not discover ${SPOKE_NAME} public IPv4 — both ifconfig.me and icanhazip.com failed"
        return 1
    fi
    log "    ${SPOKE_NAME} public IP: ${spoke_pub_ip}"

    # Call site-provisioner from vps1. The /subdomain endpoint takes the
    # bare subdomain label (`vps4` or `*.vps4`) and the spoke's public IP;
    # ensure_record composes `<subdomain>.<FABRIK_DOMAIN_ROOT>` and either
    # creates or no-ops the A record. Two calls: apex + wildcard.
    local cf_endpoint="https://provision.vps1.ocoron.com/api/cloudflare/dns/${FABRIK_DOMAIN_ROOT}/subdomain"

    for sd in "${SPOKE_NAME}" "*.${SPOKE_NAME}"; do
        local fqdn="${sd}.${FABRIK_DOMAIN_ROOT}"
        # POST body. Quoting: outer single-quotes hold the remote shell
        # script; inside, $API_KEY expands on vps1, $sd / $spoke_pub_ip
        # expand here on the dev machine.
        local response
        response=$(ssh "${FABRIK_HUB_SSH_HOST}" "API=\$(sudo grep '^API_KEY=' /opt/site-provisioner/.env | cut -d= -f2- | tr -d '\"'); curl -fsS -X POST -H \"X-API-Key: \$API\" -H 'Content-Type: application/json' -d '{\"subdomain\":\"${sd}\",\"ip\":\"${spoke_pub_ip}\",\"proxied\":false}' '${cf_endpoint}'") || {
            err "step 13: site-provisioner call failed for ${fqdn}"
            return 1
        }
        # Surface created vs unchanged for operator visibility
        local action
        action=$(echo "${response}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("result",{}).get("action","?"))' 2>/dev/null || echo "?")
        ok "    ${fqdn} → ${spoke_pub_ip} (${action})"
    done

    ok "step 13 done — DNS A records ensured for ${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT} + *.${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT}"
}

# ---------------------------------------------------------------------------
# Verify mode — read-only inspection of current spoke state
# ---------------------------------------------------------------------------

run_verify() {
    log "verify mode: read-only inspection of ${REMOTE} (${SPOKE_NAME} at ${SPOKE_MESH_IP})"

    echo "--- SSH posture ---"
    remote 'grep -E "^(PermitRootLogin|PasswordAuthentication)" /etc/ssh/sshd_config' || true

    echo "--- UFW status ---"
    remote 'sudo ufw status' 2>/dev/null || warn "UFW not installed"

    echo "--- fail2ban ---"
    remote 'sudo systemctl is-active fail2ban' 2>/dev/null || warn "fail2ban not active"

    echo "--- Docker ---"
    remote 'docker --version && sudo docker network inspect fabrik --format "{{.Name}}: {{len .Containers}} containers"' 2>/dev/null || warn "Docker or fabrik network missing"

    echo "--- Wireguard ---"
    remote 'sudo systemctl is-active wg-quick@wg0 && sudo wg show' 2>/dev/null || warn "Wireguard not active"

    echo "--- Mesh connectivity (ping hub) ---"
    remote "ping -c 2 -W 3 ${FABRIK_WG_HUB_IP}" 2>/dev/null || warn "cannot ping hub via mesh"

    echo "--- DOCKER-USER chain ---"
    remote 'sudo iptables -L DOCKER-USER -n --line-numbers' 2>/dev/null || warn "DOCKER-USER chain missing"

    echo "--- Traefik (W16) ---"
    remote 'sudo docker ps --filter name=traefik --format "{{.Names}} {{.Status}}" | grep traefik || echo MISSING' 2>/dev/null || warn "Traefik not running"
    remote 'sudo docker inspect traefik --format "{{range \$k,\$v := .Config.Labels}}{{\$k}}={{\$v}}{{println}}{{end}}" 2>/dev/null | grep "middlewares.gzip" || echo "W15 gzip middleware label MISSING (W16 not run, or live edit reverted)"' 2>/dev/null || true

    echo "--- DNS (apex + wildcard) ---"
    # Public-resolver dig so we see what Let's Encrypt would see during HTTP-01
    local apex="${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT}"
    local wildcard_test="${SPOKE_NAME}-verify-probe.${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT}"
    local apex_ip wildcard_ip
    apex_ip=$(dig +short "${apex}" @1.1.1.1 2>/dev/null | head -1)
    wildcard_ip=$(dig +short "${wildcard_test}" @1.1.1.1 2>/dev/null | head -1)
    if [[ -z "${apex_ip}" ]]; then
        echo "${apex} → MISSING (step 13 not run or DNS not propagated)"
    else
        echo "${apex} → ${apex_ip}"
    fi
    if [[ -z "${wildcard_ip}" ]]; then
        echo "*.${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT} → MISSING"
    else
        echo "*.${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT} → ${wildcard_ip} (via wildcard match on ${wildcard_test})"
    fi

    echo
    log "verify complete"
}

step_14_install_sysadmin_pack() {
    # Trio plan Phase 2 (2026-06-04) — symmetric AI ops across vps1+vps2+vps3.
    # Each host runs its own veteran-sysadmin Claude (systemd) + cron pack +
    # peer-protocol-aware /wake endpoint (Phase 3). This step installs the
    # systemd unit, cron file, scripts, env template, and the rendered
    # canonical sysadmin prompt with this host's substitutions baked in.
    log "step 14: install AI sysadmin pack (systemd unit + cron + scripts)"
    if $DRY_RUN; then
        dim "    [dry-run] would scp bot.py + 5 cron scripts + system-prompt.txt + peer-protocol.md to spoke,"
        dim "             write rendered systemd unit + cron file + .env.sysadmin template"
        return 0
    fi

    # Compute deterministic cron-minute slots from a SHA1 hash of the host
    # name (trio plan r5 #35/#36). Avoids concurrent Claude API hits across
    # 3 hosts and extends cleanly to a 4th/5th spoke without touching this
    # script.
    local host_hash digest_minute keepalive_minute
    host_hash=$(echo -n "${SPOKE_NAME}" | sha1sum | head -c 8)
    digest_minute=$(( 16#${host_hash} % 30 ))            # 0–29
    keepalive_minute=$(( (16#${host_hash#?} ) % 60 ))    # 0–59 (different bits)

    # Resolve peer-host string for the system prompt substitution. Hub is
    # always vps1 at FABRIK_WG_HUB_IP; the other spoke is whichever fleet
    # member isn't us.
    local peer_hosts
    case "${SPOKE_NAME}" in
        vps2) peer_hosts="vps1 (${FABRIK_WG_HUB_IP}), vps3 (10.99.0.3)" ;;
        vps3) peer_hosts="vps1 (${FABRIK_WG_HUB_IP}), vps2 (10.99.0.2)" ;;
        *)    peer_hosts="vps1 (${FABRIK_WG_HUB_IP}) and other fleet members" ;;
    esac

    local tmpdir
    tmpdir=$(mktemp -d -t fabrik-sysadmin-pack-XXXX)
    trap "rm -rf '$tmpdir'" RETURN

    # Render systemd unit + cron file + .env template with host-specific
    # values. The system prompt itself is rendered by the watchdog driver
    # at fabrik apply time (see src/fabrik/drivers/watchdog.py); here we
    # ship the un-rendered source-of-truth at /opt/fabrik/scripts/sysadmin/
    # so other consumers (proactive-check.sh, morning-report.sh, future
    # aro-wake) can read + render it themselves with the same host values.
    sed \
        -e "s|{{HOST_NAME}}|${SPOKE_NAME}|g" \
        -e "s|{{HOST_ROLE}}|spoke|g" \
        -e "s|{{HOST_IP}}|${SPOKE_MESH_IP}|g" \
        "${SCRIPT_DIR}/templates/vps-sysadmin-bot.service.template" \
        > "${tmpdir}/vps-sysadmin-bot.service"

    sed \
        -e "s|{{HOST_NAME}}|${SPOKE_NAME}|g" \
        -e "s|{{DIGEST_MINUTE}}|${digest_minute}|g" \
        -e "s|{{KEEPALIVE_MINUTE}}|${keepalive_minute}|g" \
        "${SCRIPT_DIR}/templates/sysadmin-cron.template" \
        > "${tmpdir}/vps-sysadmin-cron"

    sed \
        -e "s|{{HOST_NAME}}|${SPOKE_NAME}|g" \
        -e "s|{{HOST_ROLE}}|spoke|g" \
        -e "s|{{HOST_IP}}|${SPOKE_MESH_IP}|g" \
        -e "s|{{PEER_HOSTS}}|${peer_hosts}|g" \
        "${SCRIPT_DIR}/templates/env.sysadmin.template" \
        > "${tmpdir}/.env.sysadmin"

    # Ship the sysadmin source tree (scripts + canonical prompt + peer protocol).
    # Excludes __pycache__ and any local-only artifacts.
    rsync -a --exclude __pycache__ --exclude '*.pyc' \
        "${SYSADMIN_SOURCE:-/opt/fabrik/scripts/sysadmin/}" \
        "${tmpdir}/sysadmin/"

    # scp the rendered files + the sysadmin tree to /tmp on the spoke,
    # then sudo-move into place with correct ownership/mode.
    scp -q -r "${tmpdir}/vps-sysadmin-bot.service" \
              "${tmpdir}/vps-sysadmin-cron" \
              "${tmpdir}/.env.sysadmin" \
              "${tmpdir}/sysadmin" \
        "${EFFECTIVE_REMOTE}:/tmp/"

    remote "sudo mkdir -p /opt/fabrik/scripts /opt/fabrik/logs /var/log && \
        sudo cp -R /tmp/sysadmin /opt/fabrik/scripts/sysadmin && \
        sudo chown -R ozgur:ozgur /opt/fabrik/scripts/sysadmin && \
        sudo chmod 755 /opt/fabrik/scripts/sysadmin/*.sh /opt/fabrik/scripts/sysadmin/bot.py 2>/dev/null || true && \
        sudo install -m 644 -o root -g root /tmp/vps-sysadmin-bot.service /etc/systemd/system/vps-sysadmin-bot.service && \
        sudo install -m 644 -o root -g root /tmp/vps-sysadmin-cron /etc/cron.d/vps-sysadmin && \
        sudo install -m 600 -o ozgur -g ozgur /tmp/.env.sysadmin /opt/fabrik/.env.sysadmin && \
        sudo touch /opt/fabrik/logs/sysadmin-actions.jsonl && \
        sudo chown ozgur:ozgur /opt/fabrik/logs/sysadmin-actions.jsonl && \
        sudo chmod 644 /opt/fabrik/logs/sysadmin-actions.jsonl && \
        sudo systemctl daemon-reload && \
        rm -rf /tmp/sysadmin /tmp/vps-sysadmin-bot.service /tmp/vps-sysadmin-cron /tmp/.env.sysadmin"

    # Known Issue 1 hostname fix (trio plan §2.5 + vps-complete-inventory):
    # Backrest plan-failure webhook hooks reference the Coolify-UUID-suffix
    # `apprise-lcocgs4gs8ksg4g08w40ows8` instead of the stable `apprise`.
    # One-shot sed fix at install time so future plan failures actually
    # reach Telegram via the Apprise hook path.
    remote 'if sudo test -f /opt/backrest/config/config.json && \
            sudo grep -q "apprise-lcocgs4gs8ksg4g08w40ows8" /opt/backrest/config/config.json; then \
            sudo cp /opt/backrest/config/config.json /opt/backrest/config/config.json.bak.$(date +%Y%m%d-%H%M%S) && \
            sudo sed -i "s|apprise-lcocgs4gs8ksg4g08w40ows8|apprise|g" /opt/backrest/config/config.json && \
            sudo docker restart backrest >/dev/null && \
            echo "Backrest hostname fix applied"; \
        else \
            echo "Backrest hostname fix not needed (no stale UUID found)"; \
        fi'

    # Verify: files in place, systemd recognizes the unit, cron file syntax OK.
    remote 'systemctl cat vps-sysadmin-bot.service >/dev/null && \
        sudo crontab -T /etc/cron.d/vps-sysadmin 2>/dev/null; \
        ls -la /opt/fabrik/scripts/sysadmin/system-prompt.txt \
               /opt/fabrik/scripts/sysadmin/peer-protocol.md \
               /opt/fabrik/scripts/sysadmin/bot.py \
               /opt/fabrik/.env.sysadmin 2>&1 | head -5'

    ok "step 14 done — sysadmin pack installed; operator action required to activate (see post-bootstrap message)"
    log "    cron slots assigned for ${SPOKE_NAME}: digest=09:${digest_minute} UTC, keepalive=:${keepalive_minute} hourly"
}

step_15_install_aro_wake() {
    # Trio plan Phase 3 (2026-06-04). aro-wake is the push-trigger entry
    # point for this host's sysadmin AI — a tiny FastAPI service that
    # receives consult/wake calls (over wg0 mesh from peers, or locally
    # from Alertmanager in Phase 4), spawns Claude via the same calling
    # convention as bot.py + llm_client.py, and returns the result.
    #
    # Bound to the host's mesh IP only (never 0.0.0.0). Peers reach it at
    # http://10.99.0.<N>:8002/wake. systemd-managed, Restart=always.
    log "step 15: install aro-wake push-trigger service (peer consult endpoint)"
    if $DRY_RUN; then
        dim "    [dry-run] would scp aro-wake source + create venv + render systemd unit"
        return 0
    fi

    # Resolve peer hosts as JSON for the ARO_WAKE_PEER_HOSTS env var.
    local peer_hosts_json
    case "${SPOKE_NAME}" in
        vps2) peer_hosts_json='{"vps1":"'${FABRIK_WG_HUB_IP}'","vps3":"10.99.0.3"}' ;;
        vps3) peer_hosts_json='{"vps1":"'${FABRIK_WG_HUB_IP}'","vps2":"10.99.0.2"}' ;;
        *)    peer_hosts_json='{}' ;;
    esac

    local tmpdir
    tmpdir=$(mktemp -d -t fabrik-aro-wake-XXXX)
    trap "rm -rf '$tmpdir'" RETURN

    # Render systemd unit
    sed \
        -e "s|{{HOST_NAME}}|${SPOKE_NAME}|g" \
        -e "s|{{HOST_ROLE}}|spoke|g" \
        -e "s|{{HOST_IP}}|${SPOKE_MESH_IP}|g" \
        -e "s|{{BIND_HOST}}|${SPOKE_MESH_IP}|g" \
        -e "s|{{PEER_HOSTS_JSON}}|${peer_hosts_json}|g" \
        "${SCRIPT_DIR}/../aro-wake/templates/aro-wake.service.template" \
        > "${tmpdir}/aro-wake.service"

    # Ship the aro-wake source tree (excluding the templates subdir; the
    # rendered unit is the only template artifact that lands on the spoke).
    rsync -a --exclude __pycache__ --exclude '*.pyc' --exclude templates \
        "${SCRIPT_DIR}/../aro-wake/" \
        "${tmpdir}/aro-wake/"

    scp -q -r "${tmpdir}/aro-wake.service" \
              "${tmpdir}/aro-wake" \
        "${EFFECTIVE_REMOTE}:/tmp/"

    remote 'sudo mkdir -p /opt/fabrik/scripts /opt/fabrik /var/lib/aro-wake && \
        sudo cp -R /tmp/aro-wake /opt/fabrik/scripts/aro-wake && \
        sudo chown -R ozgur:ozgur /opt/fabrik/scripts/aro-wake && \
        sudo chmod 755 /opt/fabrik/scripts/aro-wake && \
        sudo chown ozgur:ozgur /var/lib/aro-wake && \
        sudo chmod 750 /var/lib/aro-wake && \
        \
        if [ ! -d /opt/fabrik/.venv-aro-wake ]; then \
            sudo -u ozgur python3 -m venv /opt/fabrik/.venv-aro-wake; \
        fi && \
        sudo -u ozgur /opt/fabrik/.venv-aro-wake/bin/pip install --quiet --upgrade pip && \
        sudo -u ozgur /opt/fabrik/.venv-aro-wake/bin/pip install --quiet -r /opt/fabrik/scripts/aro-wake/requirements.txt && \
        \
        sudo install -m 644 -o root -g root /tmp/aro-wake.service /etc/systemd/system/aro-wake.service && \
        sudo touch /var/log/aro-wake.log && \
        sudo chown ozgur:ozgur /var/log/aro-wake.log && \
        sudo systemctl daemon-reload && \
        rm -rf /tmp/aro-wake /tmp/aro-wake.service'

    remote 'systemctl cat aro-wake.service >/dev/null && echo "unit installed OK"; \
        ls -la /opt/fabrik/scripts/aro-wake/main.py /opt/fabrik/.venv-aro-wake/bin/uvicorn 2>&1 | head -3'

    ok "step 15 done — aro-wake installed; enable + verify with: sudo systemctl enable --now aro-wake.service && curl http://${SPOKE_MESH_IP}:8002/health"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
    log "Fabrik bootstrap-vps.sh starting"
    log "  remote: ${REMOTE}"
    log "  spoke:  ${SPOKE_NAME} → ${SPOKE_MESH_IP}"
    log "  flags:  dry-run=${DRY_RUN} verify=${VERIFY} skip-mesh=${SKIP_MESH} skip-dns=${SKIP_DNS}"
    echo

    preflight || { err "preflight failed; aborting"; exit 1; }

    if $VERIFY; then
        run_verify
        exit 0
    fi

    step_00_create_sudo_user
    step_01_harden_ssh
    step_02_install_firewall_fail2ban
    step_03_install_docker
    if ! $SKIP_MESH; then
        step_04_install_wireguard
        step_05_generate_spoke_keypair
        step_06_register_with_hub
        step_07_render_spoke_wg_config
        step_08_bring_up_mesh
        step_09_verify_mesh_with_pmtu_probe
        step_10_apply_firewall_rules
    else
        warn "skipping mesh setup (--skip-mesh)"
    fi
    step_11_install_monitoring_agents
    step_12_install_spoke_traefik
    step_13_create_dns_records
    step_14_install_sysadmin_pack
    step_15_install_aro_wake

    echo
    ok "bootstrap complete for ${SPOKE_NAME}"
    log "next: from your dev machine, run:"
    log "    fabrik apply specs/services/<your-service>.yaml --target-vps ${SPOKE_NAME}"
    log ""
    log "manual finish required (operator action, can't be automated):"
    log "    1. fill in TELEGRAM_BOT_TOKEN + TELEGRAM_OWNER_ID in /opt/fabrik/.env.sysadmin"
    log "    2. ssh ${SPOKE_NAME} 'claude' on the spoke (device-flow OAuth handshake)"
    log "    3. ssh ${SPOKE_NAME} 'sudo systemctl enable --now vps-sysadmin-bot.service aro-wake.service'"
    log "    4. send a test Telegram message; expect a [${SPOKE_NAME}] reply"
    log "    5. from the hub, curl http://10.99.0.\${spoke_ip_last_octet}:8002/health → expect 200"
}

main "$@"
