#!/usr/bin/env bash
#
# bootstrap-spoke-restore.sh — Fabrik spoke disaster-recovery bootstrap
#
# Turns a fresh Ubuntu 24.04 VPS into the rebuilt spoke (vps2 or vps3) with
# THE SAME Wireguard identity it had before the disk loss. The hub recognises
# the spoke immediately because its peer table entry is unchanged.
#
# Companion to:
#   scripts/bootstrap/bootstrap-vps.sh — for FRESH spokes (new WG identity)
#   scripts/bootstrap/bootstrap-hub.sh — for the hub role (vps1)
#   docs/operations/spoke-restore-inventory.md — the path list this restores
#   docs/operations/credential-recovery.md — W9 mechanism this consumes
#
# Usage:
#   ./bootstrap-spoke-restore.sh [OPTIONS] root@<new-vps-ip> <spoke-name>
#
# <spoke-name> must be vps2 or vps3 — the script looks up the spoke's restic
# password and B2 creds from the W9 mirror at /opt/fabrik-dr-store/env/.
#
# Examples:
#   ./bootstrap-spoke-restore.sh root@<new-ip> vps2
#   ./bootstrap-spoke-restore.sh --dry-run root@<new-ip> vps3
#   ./bootstrap-spoke-restore.sh --snapshot 1a2b root@<new-ip> vps2
#
# Options:
#   --dry-run        Print every command, change nothing.
#   --verify         Read-only preflight: confirm env source, B2 reachability,
#                    spoke creds present, target SSH works.
#   --snapshot ID    Use a specific restic snapshot (default: latest).
#   --env-from PATH  Override /opt/fabrik-dr-store/env/ source dir.
#   --help           Show this message.
#
# Idempotency: every step checks current state before mutating. Safe to
# re-run after a partial failure.
#
# Manual prereqs (before running):
#   - New VPS provisioned (GreenCloudVPS or similar), Ubuntu 24.04 LTS,
#     SSH access as root with your pubkey in /root/.ssh/authorized_keys.
#   - Dev machine running this script:
#       * has /opt/fabrik-dr-store/ cloned (or pass --env-from <path>)
#       * has Docker installed (used for restic-via-docker B2 preflight)
#       * has a working `ssh vps` alias to the LIVE hub (vps1)
#
# What this script DOES (numbered to match step_NN_ functions):
#   00. Create sudoer 'ozgur' + install pubkey + NOPASSWD sudo (mirror spoke bootstrap step_00).
#   01. Harden SSH (no root login, no password auth).
#   02. apt install OS packages: Docker, WG, ufw, fail2ban,
#       python3, inotify-tools, jq, curl. (NO iptables-persistent — ufw conflict, G5b)
#   03. scp spoke's restic password + Backrest .env from W9 mirror → /opt/backrest/
#   04. restic restore host-state from B2 (spoke's own repo at /spokes/<name>/):
#       /etc/wireguard/{spoke.privatekey,spoke.publickey,wg0.conf},
#       /etc/iptables/rules.v4 + rules.v6, /etc/ufw/user*.rules,
#       /etc/docker/daemon.json, /etc/sysctl.d/99-*, /etc/sudoers.d/90-ozgur,
#       /root/.ssh/authorized_keys, /home/ozgur/.ssh/authorized_keys
#   05. systemctl enable --now ufw + fail2ban (rules already on disk).
#   06. systemctl enable --now wg-quick@wg0 — mesh reconverges to hub with
#       SAME identity (hub's peer table entry unchanged).
#   07. Regenerate DOCKER-USER chain + persist via iptables-docker-user.service (G5b).
#   08. docker network create fabrik (idempotent).
#   09. restic restore /opt/ (monitoring-agent + traefik + backrest scaffolding).
#   10. docker compose up -d for /opt/monitoring-agent/ + /opt/traefik/.
#   11. docker compose up -d for /opt/backrest/ (restore the spoke's own backup chain).
#   12. Verify end-state contract (7 checks from spoke-restore-inventory.md § G).
#
# What this script does NOT do:
#   - Provision the VPS (still manual via provider panel).
#   - Touch the hub's wg0.conf (peer table unchanged — that's the whole point).
#   - Re-issue Let's Encrypt certs (Traefik does that on first request).
#   - Restore tenants on the spoke — when tenants land (W4+) the docker-volumes
#     + opt-configs scope covers them automatically.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/bootstrap-config.sh"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DRY_RUN=false
VERIFY_ONLY=false
SNAPSHOT_ID="latest"
ENV_FROM_DIR="/opt/fabrik-dr-store/env"
REMOTE=""
SPOKE_NAME=""
EFFECTIVE_REMOTE=""
BOOT_START_TS=0
BOOT_LOG_FILE=""

usage() {
    awk 'NR>1 { if (/^[^#]/) exit; sub(/^# ?/,""); print }' "$0"
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --verify) VERIFY_ONLY=true; shift ;;
        --snapshot) SNAPSHOT_ID="$2"; shift 2 ;;
        --env-from) ENV_FROM_DIR="$2"; shift 2 ;;
        --help|-h) usage 0 ;;
        --*) echo "unknown flag: $1" >&2; usage 2 ;;
        *)
            if [[ -z "$REMOTE" ]]; then
                REMOTE="$1"; shift
            elif [[ -z "$SPOKE_NAME" ]]; then
                SPOKE_NAME="$1"; shift
            else
                echo "unexpected positional arg: $1" >&2; usage 2
            fi
            ;;
    esac
done

[[ -z "$REMOTE" ]] && { echo "error: missing root@<new-vps-ip>" >&2; usage 2; }
[[ -z "$SPOKE_NAME" ]] && { echo "error: missing spoke-name (vps2 or vps3)" >&2; usage 2; }
[[ "$SPOKE_NAME" =~ ^vps[2-9]$ ]] || { echo "error: spoke-name must match ^vps[2-9]$, got: $SPOKE_NAME" >&2; usage 2; }
EFFECTIVE_REMOTE="$REMOTE"

# Spoke-specific paths in the W9 mirror.
ENV_LATEST="$ENV_FROM_DIR/latest"
SPOKE_RESTIC_PW_FROM="$ENV_FROM_DIR/${SPOKE_NAME}-restic-password-latest"
SPOKE_BACKREST_ENV_FROM="$ENV_FROM_DIR/${SPOKE_NAME}-backrest-env-latest"

RESTIC_REPO_URI="s3:https://s3.us-west-004.backblazeb2.com/vps1-ocoron-backups/spokes/${SPOKE_NAME}"

# ---------------------------------------------------------------------------
# Output helpers (verbatim match with bootstrap-vps.sh / bootstrap-hub.sh)
# ---------------------------------------------------------------------------
c_reset='\033[0m'; c_dim='\033[2m'; c_red='\033[31m'; c_green='\033[32m'
c_yellow='\033[33m'; c_blue='\033[34m'
[[ ! -t 1 ]] && c_reset='' c_dim='' c_red='' c_green='' c_yellow='' c_blue=''
log()  { echo -e "${c_blue}[spoke-restore]${c_reset} $*"; }
ok()   { echo -e "${c_green}[ ok ]${c_reset} $*"; }
warn() { echo -e "${c_yellow}[WARN]${c_reset} $*"; }
err()  { echo -e "${c_red}[FAIL]${c_reset} $*" >&2; }
dim()  { echo -e "${c_dim}$*${c_reset}"; }

remote() {
    local cmd="$*"
    $DRY_RUN && { dim "    [dry-run] ssh ${EFFECTIVE_REMOTE} '${cmd}'"; return 0; }
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${EFFECTIVE_REMOTE}" "${cmd}"
}

remote_as_initial() {
    local cmd="$*"
    $DRY_RUN && { dim "    [dry-run] ssh ${REMOTE} '${cmd}'"; return 0; }
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${REMOTE}" "${cmd}"
}

# restic via docker on the spoke, against the spoke's bucket-prefix path.
# Mounts host root at /host so restores write to host fs at /host/<path> → host /<path>.
restic_remote() {
    local cmd="$*"
    $DRY_RUN && { dim "    [dry-run] restic_remote: ${cmd}"; return 0; }
    remote "set -a; source /opt/backrest/.env; set +a; \
        sudo docker run --rm \
            -e AWS_ACCESS_KEY_ID=\"\$AWS_ACCESS_KEY_ID\" \
            -e AWS_SECRET_ACCESS_KEY=\"\$AWS_SECRET_ACCESS_KEY\" \
            -e RESTIC_PASSWORD=\"\$(cat /opt/backrest/.restic-password)\" \
            -e RESTIC_REPOSITORY=\"${RESTIC_REPO_URI}\" \
            -v /:/host \
            restic/restic:0.18.1 ${cmd}"
}

elapsed() {
    local secs=$(($(date +%s) - BOOT_START_TS))
    printf "%dm%02ds" $((secs / 60)) $((secs % 60))
}

# ---------------------------------------------------------------------------
# Preflight — all-or-nothing
# ---------------------------------------------------------------------------
preflight() {
    log "preflight checks ..."

    # 1. Spoke's W9 credentials present locally
    for f in "$SPOKE_RESTIC_PW_FROM" "$SPOKE_BACKREST_ENV_FROM"; do
        if [[ ! -r "$f" ]]; then
            err "spoke credential missing: $f. Did W9 mirror pull it? Run scripts/dr_env_backup.sh first."
            return 1
        fi
    done
    ok "spoke creds present: ${SPOKE_NAME}-restic-password-latest + ${SPOKE_NAME}-backrest-env-latest"

    # 2. Main env (for sanity — though spoke restore doesn't strictly need /opt/fabrik/.env)
    if [[ -r "$ENV_LATEST" ]]; then
        ok "W9 main env present (used as fallback for B2 creds if needed)"
    else
        warn "W9 main env absent ($ENV_LATEST) — spoke restore can still proceed using spoke-specific Backrest env"
    fi

    # 3. Local docker available
    if ! command -v docker &>/dev/null; then
        err "docker not installed on dev machine — needed for B2 preflight"
        return 1
    fi
    ok "local docker available"

    # 4. Target SSH
    if ! ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
            -o BatchMode=yes "${REMOTE}" 'echo ok' &>/dev/null; then
        err "cannot SSH to ${REMOTE}"
        return 1
    fi
    ok "SSH to ${REMOTE} works"

    # 5. B2 reachable + spoke's restic repo exists with the stored password
    local b2_key b2_secret restic_pw
    b2_key=$(grep '^AWS_ACCESS_KEY_ID=' "$SPOKE_BACKREST_ENV_FROM" | cut -d= -f2-)
    b2_secret=$(grep '^AWS_SECRET_ACCESS_KEY=' "$SPOKE_BACKREST_ENV_FROM" | cut -d= -f2-)
    restic_pw=$(cat "$SPOKE_RESTIC_PW_FROM")
    if [[ -z "$b2_key" || -z "$b2_secret" || -z "$restic_pw" ]]; then
        err "spoke creds incomplete (key/secret/password length: ${#b2_key}/${#b2_secret}/${#restic_pw})"
        return 1
    fi
    local snap_count
    snap_count=$(docker run --rm \
        -e AWS_ACCESS_KEY_ID="$b2_key" \
        -e AWS_SECRET_ACCESS_KEY="$b2_secret" \
        -e RESTIC_PASSWORD="$restic_pw" \
        -e RESTIC_REPOSITORY="$RESTIC_REPO_URI" \
        restic/restic:0.18.1 snapshots --json 2>/dev/null \
        | jq 'length' 2>/dev/null || echo 0)
    if [[ "$snap_count" -lt 1 ]]; then
        err "spoke restic repo $RESTIC_REPO_URI has 0 snapshots — nothing to restore"
        return 1
    fi
    ok "spoke restic repo reachable; ${snap_count} snapshot(s) available"

    # 6. Target is fresh (no existing /opt/backrest)
    local existing
    existing=$(remote_as_initial 'test -d /opt/backrest && echo dirty || echo fresh' 2>/dev/null || echo unknown)
    if [[ "$existing" == "dirty" ]]; then
        warn "target VPS already has /opt/backrest/ — re-apply over existing state (idempotent, unusual)"
    else
        ok "target VPS is fresh (no existing /opt/backrest)"
    fi

    return 0
}

# ---------------------------------------------------------------------------
# Step blocks
# ---------------------------------------------------------------------------

step_00_create_sudo_user() {
    local user="${FABRIK_SUDOER_USER}"
    log "step_00: create sudoer '${user}' ($(elapsed))"
    local pubkey=""
    if ! $DRY_RUN; then
        local candidates=( "${HOME}/.ssh/id_ed25519.pub" "${HOME}/.ssh/id_ecdsa.pub" "${HOME}/.ssh/id_rsa.pub" )
        local ssh_g_identity
        ssh_g_identity=$(ssh -G "${REMOTE}" 2>/dev/null | awk '/^identityfile / {print $2}' | head -3)
        while IFS= read -r f; do f="${f/#\~/$HOME}"; [[ -n "$f" ]] && candidates+=("${f}.pub"); done <<<"$ssh_g_identity"
        for c in "${candidates[@]}"; do
            [[ -f "$c" ]] && { pubkey=$(cat "$c"); log "  using key: $c"; break; }
        done
        [[ -z "$pubkey" ]] && { err "step_00: no public key found"; return 1; }
    fi
    remote_as_initial "sudo bash -c '
        if ! id ${user} >/dev/null 2>&1; then useradd -m -s /bin/bash ${user}; fi
        mkdir -p /home/${user}/.ssh && chmod 700 /home/${user}/.ssh
        touch /home/${user}/.ssh/authorized_keys && chmod 600 /home/${user}/.ssh/authorized_keys
        chown -R ${user}:${user} /home/${user}/.ssh
        if ! grep -qxF \"${pubkey}\" /home/${user}/.ssh/authorized_keys; then
            echo \"${pubkey}\" >> /home/${user}/.ssh/authorized_keys
        fi
        # Spokes use the 90- prefix convention (different from hub's plain ozgur).
        echo \"${user} ALL=(ALL) NOPASSWD:ALL\" > /etc/sudoers.d/90-${user}
        chmod 0440 /etc/sudoers.d/90-${user}
        visudo -cf /etc/sudoers.d/90-${user} >/dev/null
    '"
    local host="${REMOTE#*@}"
    EFFECTIVE_REMOTE="${user}@${host}"
    if $DRY_RUN; then dim "    [dry-run] EFFECTIVE_REMOTE → ${EFFECTIVE_REMOTE}"
    else remote 'sudo -n true' &>/dev/null \
        && ok "step_00 done — NOPASSWD sudo works as ${user}" \
        || { err "step_00: cannot sudo as ${user}"; return 1; }
    fi
}

step_01_harden_ssh() {
    log "step_01: harden SSH ($(elapsed))"
    remote 'sudo bash -c "
        mkdir -p /etc/ssh/sshd_config.d
        cat > /etc/ssh/sshd_config.d/99-fabrik-hardening.conf <<EOF
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
EOF
        chmod 644 /etc/ssh/sshd_config.d/99-fabrik-hardening.conf
        sshd -t && systemctl reload ssh
    "'
    ok "step_01 done"
}

step_02_install_packages() {
    log "step_02: install OS packages ($(elapsed))"
    # Bug #8 (Hub DR Drill #6, 2026-06-15): same dpkg lock race as the hub —
    # Vultr stock Ubuntu 24.04 runs unattended-upgrades at boot. Wait for the
    # lock instead of failing at 0s. Identical fix to bootstrap-hub.sh step_02.
    local apt_lock_wait='-o DPkg::Lock::Timeout=300'
    remote 'command -v docker >/dev/null || (
        while sudo fuser /var/lib/dpkg/lock-frontend &>/dev/null; do
            echo "waiting for dpkg lock (unattended-upgrades?)..." >&2
            sleep 5
        done
        curl -fsSL https://get.docker.com | sudo sh
    )'
    # NOTE: do NOT install iptables-persistent here. On Ubuntu 24.04 it declares
    # Conflicts: ufw, so apt-get install iptables-persistent silently REMOVES ufw
    # and step_05 ufw --force enable then fails. DOCKER-USER persistence is
    # instead provided by iptables-docker-user.service (regenerated in step_07),
    # matching the vps1 hub and the fresh-spoke bootstrap (bootstrap-vps.sh
    # step_10, G5). (G5b)
    remote "sudo bash -c '
        DEBIAN_FRONTEND=noninteractive apt-get ${apt_lock_wait} update -qq
        DEBIAN_FRONTEND=noninteractive apt-get ${apt_lock_wait} install -y -qq \
            wireguard wireguard-tools \
            ufw fail2ban \
            python3 python3-pip \
            inotify-tools \
            jq curl ca-certificates
    '"
    remote "sudo usermod -aG docker ${FABRIK_SUDOER_USER}"
    ok "step_02 done"
}

step_03_place_backrest_creds() {
    log "step_03: scp spoke restic password + Backrest env from W9 mirror ($(elapsed))"
    remote "sudo mkdir -p /opt/backrest/{config,data,cache,tmp}"
    if $DRY_RUN; then
        dim "    [dry-run] scp ${SPOKE_RESTIC_PW_FROM} ${EFFECTIVE_REMOTE}:/tmp/.restic-password"
        dim "    [dry-run] scp ${SPOKE_BACKREST_ENV_FROM} ${EFFECTIVE_REMOTE}:/tmp/.backrest-env"
    else
        scp -o ConnectTimeout=10 "$SPOKE_RESTIC_PW_FROM" "${EFFECTIVE_REMOTE}:/tmp/.restic-password"
        scp -o ConnectTimeout=10 "$SPOKE_BACKREST_ENV_FROM" "${EFFECTIVE_REMOTE}:/tmp/.backrest-env"
    fi
    remote 'sudo bash -c "
        install -m 600 -o root -g root /tmp/.restic-password /opt/backrest/.restic-password
        install -m 600 -o root -g root /tmp/.backrest-env /opt/backrest/.env
        rm -f /tmp/.restic-password /tmp/.backrest-env
    "'
    remote 'sudo grep -qE "^AWS_ACCESS_KEY_ID=." /opt/backrest/.env' \
        || { err "step_03: B2 creds missing from /opt/backrest/.env"; return 1; }
    ok "step_03 done"
}

step_04_restic_pull_host_state() {
    log "step_04: restic restore host-state from B2 ($(elapsed))"
    # Includes from spoke-restore-inventory § B. --target /host → host fs at root.
    local includes=""
    for p in \
        /etc/wireguard \
        /etc/iptables \
        /etc/ufw/user.rules \
        /etc/ufw/user6.rules \
        /etc/docker/daemon.json \
        /etc/sysctl.d/99-cloudimg-ipv6.conf \
        /etc/sysctl.d/99-sysctl.conf \
        /etc/sudoers.d/90-ozgur \
        /root/.ssh/authorized_keys \
        /home/ozgur/.ssh/authorized_keys ; do
        includes+=" --include ${p}"
    done

    # Bug #9 (Hub DR Drill #6, 2026-06-15) — see bootstrap-hub.sh step_06 for
    # the full writeup. Same shape here: restic overwrites /root/.ssh/authorized_keys
    # and /home/ozgur/.ssh/authorized_keys, losing the access key currently in use.
    # Fix: backup pre-restore + inline restic + merge in ONE ssh session.
    # Bug #7: Backrest writes snapshots tagged plan:<id>, not the bare id.
    remote "sudo bash -c '
        set -e
        mkdir -p /tmp/preboot-keys
        cp /home/ozgur/.ssh/authorized_keys /tmp/preboot-keys/ozgur.authkeys 2>/dev/null || true
        cp /root/.ssh/authorized_keys      /tmp/preboot-keys/root.authkeys  2>/dev/null || true

        B2_KEY=\$(grep \"^B2_KEY_ID=\" /opt/fabrik/.env | cut -d= -f2-)
        B2_SECRET=\$(grep \"^B2_APPLICATION_KEY=\" /opt/fabrik/.env | cut -d= -f2-)
        B2_PW=\$(grep \"^BACKREST_RESTIC_PASSWORD=\" /opt/fabrik/.env | cut -d= -f2-)
        if [[ -z \"\$B2_KEY\" || -z \"\$B2_SECRET\" || -z \"\$B2_PW\" ]]; then
            echo \"step_04: B2_KEY_ID / B2_APPLICATION_KEY / BACKREST_RESTIC_PASSWORD missing from /opt/fabrik/.env\" >&2
            exit 1
        fi
        docker run --rm \
            -e AWS_ACCESS_KEY_ID=\"\$B2_KEY\" \
            -e AWS_SECRET_ACCESS_KEY=\"\$B2_SECRET\" \
            -e RESTIC_PASSWORD=\"\$B2_PW\" \
            -e RESTIC_REPOSITORY=\"${FABRIK_RESTIC_REPO_URI}\" \
            -v /:/host \
            restic/restic:0.18.1 restore ${SNAPSHOT_ID} --target /host${includes} --tag plan:host-state

        if [ -s /tmp/preboot-keys/ozgur.authkeys ]; then
            cat /home/ozgur/.ssh/authorized_keys /tmp/preboot-keys/ozgur.authkeys 2>/dev/null \
                | awk \"NF && !seen[\\\$0]++\" \
                > /home/ozgur/.ssh/authorized_keys.merged
            mv /home/ozgur/.ssh/authorized_keys.merged /home/ozgur/.ssh/authorized_keys
        fi
        if [ -s /tmp/preboot-keys/root.authkeys ]; then
            cat /root/.ssh/authorized_keys /tmp/preboot-keys/root.authkeys 2>/dev/null \
                | awk \"NF && !seen[\\\$0]++\" \
                > /root/.ssh/authorized_keys.merged
            mv /root/.ssh/authorized_keys.merged /root/.ssh/authorized_keys
        fi
        chown -R ozgur:ozgur /home/ozgur/.ssh
        chown -R root:root   /root/.ssh
        chmod 700 /home/ozgur/.ssh /root/.ssh
        chmod 600 /home/ozgur/.ssh/authorized_keys /root/.ssh/authorized_keys
        rm -rf /tmp/preboot-keys
    '"

    remote 'sudo systemctl daemon-reload'
    # NOTE: do NOT assert /etc/iptables/rules.v4 — post-G5 backups do not carry it
    # (DOCKER-USER persistence moved to iptables-docker-user.service). The chain is
    # regenerated from config in step_07, not restored from the saved table. (G5b)
    # Bug #11 (Hub DR Drill #6f, 2026-06-15): /etc/wireguard is 0700 root:root.
    # ozgur cannot traverse the dir → test -f fails. Use sudo test -f.
    remote 'sudo test -f /etc/wireguard/wg0.conf && sudo test -f /etc/sudoers.d/90-ozgur' \
        || { err "step_04: critical host-state file missing post-restore"; return 1; }
    ok "step_04 done"
}

step_05_apply_ufw() {
    log "step_05: enable UFW + fail2ban (rules already on disk) ($(elapsed))"
    remote 'sudo ufw --force enable && sudo ufw reload'
    remote 'sudo systemctl enable --now ufw fail2ban'
    if ! $DRY_RUN; then
        local n; n=$(remote 'sudo ufw status numbered 2>/dev/null | grep -cE "^\["') || n=0
        (( n >= 8 )) && ok "step_05 done — ${n} UFW rules active" \
                     || warn "step_05: ${n} UFW rules (expected ≥ 8); may be incomplete"
    else ok "step_05 done (dry-run)"
    fi
}

step_06_bring_up_mesh() {
    log "step_06: enable wg-quick@wg0 — mesh reconverges with PRESERVED spoke identity ($(elapsed))"
    remote 'sudo systemctl enable --now wg-quick@wg0'
    if ! $DRY_RUN; then
        sleep 8
        local handshake_age
        handshake_age=$(remote 'sudo wg show wg0 latest-handshakes 2>/dev/null | awk "(systime()-\$2) < 300 {c++} END {print c+0}"') || handshake_age=0
        (( handshake_age >= 1 )) \
            && ok "step_06 done — hub handshake within last 5 min (peer table preserved — same spoke identity)" \
            || warn "step_06: 0 recent handshakes — check hub's wg0.conf has this spoke's pubkey"
    else ok "step_06 done (dry-run)"
    fi
}

step_07_apply_iptables() {
    log "step_07: DOCKER-USER chain + persist via iptables-docker-user.service (hub-matching) ($(elapsed))"
    if $DRY_RUN; then
        dim "    [dry-run] would scp /etc/iptables/{add,rm}-docker-user-rules.sh + iptables-docker-user.service, then enable --now"
        ok "step_07 done (dry-run)"
        return 0
    fi

    # DOCKER-USER persistence is provided by a oneshot systemd unit identical in
    # shape to vps1's and the fresh-spoke bootstrap (bootstrap-vps.sh step_10, G5)
    # — NOT netfilter-persistent loading a saved rules.v4. The firewall policy is
    # deterministic and fleet-uniform, so we regenerate it from config rather than
    # trust the restored table (restoring a full save can clobber Docker's live
    # chains on a Docker host). Works for pre-G5 AND post-G5 backups. (G5b)
    local public_iface
    public_iface=$(remote "ip route get 1.1.1.1 | awk '/dev/ {print \$5; exit}'")
    if [[ -z "$public_iface" ]]; then
        warn "could not auto-detect public interface; falling back to ${FABRIK_PUBLIC_IFACE_DEFAULT}"
        public_iface="$FABRIK_PUBLIC_IFACE_DEFAULT"
    fi

    local mesh_ports="${FABRIK_MESH_ONLY_PORTS[*]}"
    local mesh_ports_csv="${mesh_ports// /,}"

    # Build add/rm scripts + the unit locally, then scp + sudo install — the
    # scp-to-/tmp pattern avoids the remote-bash quote-nesting hazard (Rule 2).
    local tmpdir
    tmpdir=$(mktemp -d -t fabrik-iptables-XXXX)

    cat > "${tmpdir}/add-docker-user-rules.sh" <<EOF
#!/bin/bash
# Spoke DOCKER-USER rules — regenerated by bootstrap-spoke-restore.sh step_07.
# Run at boot by iptables-docker-user.service (After=docker.service). Idempotent.
iptables -C DOCKER-USER -i ${FABRIK_MESH_IFACE} -j ACCEPT 2>/dev/null || iptables -I DOCKER-USER -i ${FABRIK_MESH_IFACE} -j ACCEPT
iptables -C DOCKER-USER -i ${public_iface} -p tcp -m multiport --dports ${mesh_ports_csv} -j DROP 2>/dev/null || iptables -I DOCKER-USER -i ${public_iface} -p tcp -m multiport --dports ${mesh_ports_csv} -j DROP
EOF

    cat > "${tmpdir}/rm-docker-user-rules.sh" <<EOF
#!/bin/bash
iptables -D DOCKER-USER -i ${FABRIK_MESH_IFACE} -j ACCEPT 2>/dev/null || true
iptables -D DOCKER-USER -i ${public_iface} -p tcp -m multiport --dports ${mesh_ports_csv} -j DROP 2>/dev/null || true
EOF

    cat > "${tmpdir}/iptables-docker-user.service" <<'EOF'
[Unit]
Description=Docker-User iptables rules (block external access to internal ports)
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/etc/iptables/add-docker-user-rules.sh
ExecStop=/etc/iptables/rm-docker-user-rules.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    scp -q -o StrictHostKeyChecking=accept-new \
        "${tmpdir}/add-docker-user-rules.sh" \
        "${tmpdir}/rm-docker-user-rules.sh" \
        "${tmpdir}/iptables-docker-user.service" \
        "${EFFECTIVE_REMOTE}:/tmp/"

    remote 'sudo mkdir -p /etc/iptables && \
        sudo install -m 755 -o root -g root /tmp/add-docker-user-rules.sh /etc/iptables/add-docker-user-rules.sh && \
        sudo install -m 755 -o root -g root /tmp/rm-docker-user-rules.sh /etc/iptables/rm-docker-user-rules.sh && \
        sudo install -m 644 -o root -g root /tmp/iptables-docker-user.service /etc/systemd/system/iptables-docker-user.service && \
        sudo systemctl daemon-reload && \
        sudo systemctl enable --now iptables-docker-user.service && \
        rm -f /tmp/add-docker-user-rules.sh /tmp/rm-docker-user-rules.sh /tmp/iptables-docker-user.service'

    rm -rf "${tmpdir}"

    local r; r=$(remote 'sudo iptables -L DOCKER-USER -n 2>/dev/null | grep -cE "DROP|ACCEPT"') || r=0
    (( r >= 1 )) && ok "step_07 done — DOCKER-USER chain: ${r} rules (via iptables-docker-user.service)" \
                 || warn "step_07: DOCKER-USER chain empty — unit may not have applied"
}

step_08_create_fabrik_network() {
    log "step_08: docker network create fabrik (idempotent) ($(elapsed))"
    remote 'sudo docker network inspect fabrik >/dev/null 2>&1 || sudo docker network create fabrik'
    ok "step_08 done"
}

step_09_restic_pull_opt() {
    log "step_09: restic restore /opt/ from B2 ($(elapsed))"
    # Bug #7 (Hub DR Drill #5, 2026-06-14): Backrest tags snapshots plan:<id>.
    restic_remote "restore ${SNAPSHOT_ID} --target /host --include /opt --tag plan:opt-configs"
    if ! $DRY_RUN; then
        for d in monitoring-agent traefik backrest; do
            remote "test -d /opt/${d}" \
                || warn "step_09: /opt/${d} missing post-restore (may be OK if backrest was not in this snapshot)"
        done
        ok "step_09 done"
    else
        ok "step_09 done (dry-run)"
    fi
}

step_10_compose_up_services() {
    log "step_10: docker compose up -d on /opt/monitoring-agent + /opt/traefik ($(elapsed))"
    for svc in monitoring-agent traefik; do
        if remote "test -f /opt/${svc}/compose.yaml"; then
            log "  ${svc}: docker compose up -d"
            remote "cd /opt/${svc} && sudo docker compose up -d"
        else
            warn "  ${svc}: no compose.yaml — skipping (may need re-deploy via fabrik apply)"
        fi
    done
    ok "step_10 done"
}

step_11_compose_up_backrest() {
    log "step_11: docker compose up -d on /opt/backrest (restore spoke's own backup chain) ($(elapsed))"
    if remote 'test -f /opt/backrest/compose.yaml'; then
        remote 'cd /opt/backrest && sudo docker compose up -d'
        if ! $DRY_RUN; then
            sleep 5
            remote 'sudo docker ps --format "{{.Names}}" | grep -q "^backrest$"' \
                && ok "step_11 done — Backrest running; spoke's next scheduled backup will fire normally" \
                || warn "step_11: Backrest not running after compose up — check logs"
        else ok "step_11 done (dry-run)"
        fi
    else
        warn "step_11: /opt/backrest/compose.yaml absent — restore may have been incomplete; spoke has no future backups until fixed"
    fi
}

step_12_verify_end_state() {
    log "step_12: verify end-state contract (spoke-restore-inventory.md § G) ($(elapsed))"
    if $DRY_RUN; then ok "step_12 done (dry-run)"; return 0; fi
    local fail=0

    # 1. WG handshake to hub
    local h; h=$(remote 'sudo wg show wg0 latest-handshakes 2>/dev/null | awk "(systime()-\$2) < 180 {c++} END {print c+0}"') || h=0
    (( h >= 1 )) && ok "  [1/7] wg0 hub handshake fresh: ${h}" || { err "  [1/7] no recent wg0 handshake"; fail=$((fail+1)); }

    # 2. Hub still has this spoke in its peer table (proves identity preservation)
    local hub_peers
    hub_peers=$(ssh -o BatchMode=yes vps "sudo wg show wg0 latest-handshakes | awk '(systime()-\$2) < 180 {print \$1}'" 2>/dev/null | wc -l)
    (( hub_peers >= 2 )) && ok "  [2/7] hub sees ≥2 fresh peers (including this spoke)" \
                         || warn "  [2/7] hub sees ${hub_peers} fresh peers — manual confirmation that this spoke is one of them"

    # 3. Container count
    local cc; cc=$(remote 'sudo docker ps --format "{{.Names}}" | wc -l') || cc=0
    (( cc >= 5 )) && ok "  [3/7] containers running: ${cc} (≥5)" \
                  || { err "  [3/7] containers running: ${cc} (expected ≥5)"; fail=$((fail+1)); }

    # 4. UFW active
    remote 'sudo ufw status 2>/dev/null | grep -q "Status: active"' \
        && ok "  [4/7] UFW: active" \
        || { err "  [4/7] UFW not active"; fail=$((fail+1)); }

    # 5. DOCKER-USER chain
    local du; du=$(remote 'sudo iptables -L DOCKER-USER -n 2>/dev/null | grep -cE "DROP|ACCEPT"') || du=0
    (( du >= 1 )) && ok "  [5/7] DOCKER-USER chain: ${du} rules" \
                  || { err "  [5/7] DOCKER-USER chain empty"; fail=$((fail+1)); }

    # 6. Spoke Backrest can list ≥1 snapshot
    local snap_count
    snap_count=$(remote "sudo bash -c '
        RESTIC_PW=\$(cat /opt/backrest/.restic-password 2>/dev/null)
        docker exec -e RESTIC_PASSWORD=\"\$RESTIC_PW\" backrest /bin/restic \
            -r ${RESTIC_REPO_URI} snapshots --json 2>/dev/null \
            | python3 -c \"import json,sys; print(len(json.load(sys.stdin)))\" 2>/dev/null
    '" 2>/dev/null) || snap_count=0
    (( snap_count >= 1 )) && ok "  [6/7] spoke Backrest sees ${snap_count} snapshot(s) in its repo" \
                          || { err "  [6/7] spoke Backrest cannot list snapshots — DR loop broken"; fail=$((fail+1)); }

    # 7. Wall-clock
    local total=$(($(date +%s) - BOOT_START_TS))
    if (( total <= 1800 )); then
        ok "  [7/7] wall-clock: $(elapsed) (≤30 min target)"
    else
        warn "  [7/7] wall-clock: $(elapsed) (>30 min target; check ${BOOT_LOG_FILE})"
    fi

    if (( fail > 0 )); then
        err "step_12: ${fail} of 7 contract items FAILED"
        return 1
    fi
    ok "step_12 done — all 7 contract items PASS"
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
main() {
    BOOT_START_TS=$(date +%s)
    BOOT_LOG_FILE="/tmp/bootstrap-spoke-restore-${SPOKE_NAME}-$(date -u +%Y%m%dT%H%M%SZ).log"
    exec > >(tee -a "$BOOT_LOG_FILE") 2>&1

    log "Fabrik spoke restore starting"
    log "  target VPS:         ${REMOTE}"
    log "  spoke identity:     ${SPOKE_NAME} (preserved from B2 host-state snapshot)"
    log "  restic repo:        ${RESTIC_REPO_URI}"
    log "  snapshot:           ${SNAPSHOT_ID}"
    log "  W9 env source:      ${ENV_FROM_DIR}/"
    log "  log file:           ${BOOT_LOG_FILE}"
    $DRY_RUN && log "  DRY-RUN mode (no changes)"
    $VERIFY_ONLY && log "  VERIFY mode (read-only)"
    echo

    preflight || { err "preflight failed; aborting"; exit 1; }
    echo
    $VERIFY_ONLY && { ok "verify mode — preflight passed; not running step blocks."; return 0; }

    step_00_create_sudo_user
    step_01_harden_ssh
    step_02_install_packages
    step_03_place_backrest_creds
    step_04_restic_pull_host_state
    step_05_apply_ufw
    step_06_bring_up_mesh
    step_07_apply_iptables
    step_08_create_fabrik_network
    step_09_restic_pull_opt
    step_10_compose_up_services
    step_11_compose_up_backrest
    step_12_verify_end_state

    echo
    ok "✓ SPOKE ${SPOKE_NAME} RESTORED ($(elapsed) elapsed)"
    ok "   log file: ${BOOT_LOG_FILE}"
    ok "   hub recognises spoke by preserved Wireguard identity — no peer-table edit needed."
}

main "$@"
