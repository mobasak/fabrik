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
    for port in "${FABRIK_PUBLIC_PORTS_TCP[@]}"; do
        remote "sudo ufw allow ${port}/tcp 2>&1 | tail -1"
    done
    for port in "${FABRIK_PUBLIC_PORTS_UDP[@]}"; do
        remote "sudo ufw allow ${port}/udp 2>&1 | tail -1"
    done
    remote 'echo y | sudo ufw enable 2>&1 | tail -1'
    remote 'sudo systemctl enable --now fail2ban'
    ok "step 02 done"
}

step_03_install_docker() {
    log "step 03: install Docker + log rotation + create 'fabrik' network"
    remote 'if ! command -v docker >/dev/null; then \
        curl -fsSL https://get.docker.com | sudo sh; \
        fi'
    # Log rotation policy matches vps1 (10m × 3 files)
    remote 'sudo tee /etc/docker/daemon.json >/dev/null <<EOF
{
  "log-driver": "json-file",
  "log-opts": {"max-size": "10m", "max-file": "3"}
}
EOF
    sudo systemctl restart docker'
    # Create fabrik network if missing
    remote 'sudo docker network inspect fabrik >/dev/null 2>&1 || sudo docker network create fabrik'
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
    log "step 11: install lightweight monitoring agents shipping to vps1 over mesh"
    warn "step 11 stub — TODO: render promtail.yml + node-exporter + cadvisor compose, push to /opt/monitoring-agent/, docker compose up -d"
    # Not implementing in M1a — defer to M1b after multipass testing proves the rest works.
}

step_12_create_dns_records() {
    log "step 12: create DNS records via site-provisioner"
    if $SKIP_DNS; then
        warn "step 12 skipped (--skip-dns)"
        return 0
    fi
    warn "step 12 stub — TODO: call site-provisioner API to create *.${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT} A record + auth.${SPOKE_NAME}.${FABRIK_DOMAIN_ROOT} CNAME → vps1"
    # Not implementing in M1a — defer to M1b after multipass testing.
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

    echo
    log "verify complete"
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
    step_12_create_dns_records

    echo
    ok "bootstrap complete for ${SPOKE_NAME}"
    log "next: from your dev machine, run:"
    log "    fabrik apply specs/services/<your-service>.yaml --target-vps ${SPOKE_NAME}"
}

main "$@"
