#!/usr/bin/env bash
#
# bootstrap-hub.sh — Fabrik hub disaster-recovery bootstrap
#
# Turns a fresh Ubuntu 24.04 VPS into the rebuilt vps1 hub: full mesh,
# all containers running, Telegram bot answering, Gatus dashboard green.
# Input: a dead-vps1 backup chain (Backrest @ B2 + W9 .env mirror @ GitHub).
# Output: a working hub. Target wall-clock: ≤ 90 min on a 100 Mbit pipe.
#
# Companion to:
#   scripts/bootstrap/bootstrap-vps.sh — for spokes (W-Multi M1)
#   docs/operations/hub-restore-inventory.md — the path list this restores
#   docs/operations/credential-recovery.md — W9 mechanism this consumes
#   docs/operations/disaster-recovery.md — the operator runbook this serves
#
# Usage:
#   ./bootstrap-hub.sh [OPTIONS] root@<new-vps-ip-or-host>
#
# Examples:
#   ./bootstrap-hub.sh root@10.20.30.40
#   ./bootstrap-hub.sh --dry-run root@10.20.30.40
#   ./bootstrap-hub.sh --cf-rewrite-dns 10.20.30.40 root@10.20.30.40
#   ./bootstrap-hub.sh --snapshot 1a2b3c4d root@10.20.30.40   # specific snapshot, not latest
#
# Options:
#   --dry-run             Print every command that would run; make no changes.
#   --verify              Read-only mode: check current state, report missing pieces.
#   --snapshot ID         Use a specific restic snapshot ID (default: latest).
#   --env-from PATH       Override W9 env source (default: /opt/fabrik-dr-store/env/latest).
#   --sysadmin-env-from PATH Override W9 sysadmin env source (default: env/sysadmin-latest).
#   --cf-rewrite-dns IP   Rewrite every *.vps1.ocoron.com A record to the given IP.
#                         Use when the rebuilt VPS has a different public IP than
#                         the dead one. Skip if the provider gave you the same IP back.
#   --skip-services       Stop before docker-compose-up-d (step_13). Useful for
#                         verifying the restore steps alone.
#   --help                Show this message.
#
# Idempotency: every step checks current state before mutating. Safe to
# re-run after a partial failure.
#
# Manual prereqs (do these once before running the script):
#   - New VPS provisioned (GreenCloudVPS or equivalent), Ubuntu 24.04 LTS,
#     SSH access as root (provider's initial password emailed to you, then
#     drop your pubkey into /root/.ssh/authorized_keys before running this).
#   - The dev machine running this script:
#       * has /opt/fabrik-dr-store/ cloned from mobasak/fabrik-dr-store
#         (or pass --env-from <path> if it lives elsewhere)
#       * has Docker installed (used to run restic-via-docker for B2 ops)
#       * has gh CLI authenticated for mobasak/fabrik-dr-store HTTPS access
#   - You know whether the new VPS gets the SAME public IP as the dead vps1
#     or a NEW one. If new, pass --cf-rewrite-dns <new-ip>.
#
# What this script DOES (numbered to match the step_NN_ functions below):
#   00. Create sudoer 'ozgur' on the new VPS; install operator's pubkey.
#   01. Harden SSH (disable root login, disable password auth) AFTER 00 verified.
#   02. Install OS packages: Docker, WG, UFW, fail2ban, python3,
#       inotify-tools, gh, jq, curl. (G5-for-hub 2026-06-14: NO
#       iptables-persistent — `Conflicts: ufw` on Ubuntu 24.04 makes apt
#       refuse the install. DOCKER-USER persistence moves to the custom
#       iptables-docker-user.service in step 09.)
#   03. npm install -g @anthropic-ai/claude-code (for vps-sysadmin-bot).
#   04. Pull the W9 DR-store env mirror; place /opt/fabrik/.env + .env.sysadmin.
#   05. Write /etc/docker/daemon.json BEFORE starting any container (log rotation +
#       container tag for promtail).
#   06. restic restore host-level state: /etc/wireguard, /etc/iptables, /etc/ufw,
#       /etc/logrotate.d/vps-sysadmin-*, /etc/systemd/system/<fabrik-units>,
#       /etc/cron.d/vps-sysadmin, /root/.ssh/known_hosts, /home/ozgur/.ssh/*.
#   07. Apply UFW rules (rules already restored in step 06, just enable + reload).
#   08. systemctl enable --now wg-quick@wg0 (mesh comes back up to spokes).
#   09. systemctl enable --now iptables-docker-user iptables-openvpn
#       (DOCKER-USER chain + OpenVPN forwards). Also tries
#       netfilter-persistent IF the unit exists (legacy pre-G5 hubs);
#       post-G5 fresh installs don't have it and the custom units alone
#       are authoritative.
#   10. docker network create fabrik (idempotent).
#   11. restic restore /opt/ (everything except /opt/containerd, /opt/fabrik/.git,
#       /opt/backups/coolify_env_*, restic-cache subdirs).
#   12. restic restore Docker named volumes (postgres-data, redis_redis-data,
#       monitoring_grafana-data, apprise-config, meilisearch-data, n8n-data,
#       and the ocoron-com tenant volumes).
#   13. docker compose up -d in dep order (postgres-main, redis-main, traefik,
#       authelia, monitoring stack, then the rest).
#   14. Fallback: if postgres-data volume restore came up empty, psql restore
#       from /opt/backups/pg_dump_<latest>.sql.
#   15. systemctl enable --now vps-sysadmin-bot authelia-config-sync.
#   16. Install root crontab: 30 1 * * * /opt/backups/pre-backup.sh ...
#   17. (Optional) Cloudflare DNS rewrite if --cf-rewrite-dns was passed:
#       PATCH every *.vps1.ocoron.com A record to the new IP.
#   18. Verify the 6 end-state contract items from hub-restore-inventory.md § "End-state contract".
#
# What this script does NOT do:
#   - Provision the VPS itself (still a manual GreenCloudVPS panel click).
#   - Rebuild Backrest snapshots if the bucket is empty (this is the consumer,
#     not the producer; the producer is the daily Backrest cron on the OLD vps1).
#   - Bring back vps2/vps3 — they are independent hosts; they keep running
#     during the vps1 outage and re-establish mesh as soon as wg0 is up here.

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate ourselves (so the script can be run from anywhere)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/bootstrap-config.sh"

# ---------------------------------------------------------------------------
# Defaults (overridable via flags)
# ---------------------------------------------------------------------------
DRY_RUN=false
VERIFY_ONLY=false
SKIP_SERVICES=false
SKIP_MESH=false                # NEW 2026-06-14 — for `fabrik vultr drill hub`:
                               # skip step_08 wg-quick@wg0 bring-up so the
                               # drill droplet (which restored vps1's real
                               # private key) does NOT initiate handshakes
                               # to vps2/vps3 — that would update the live
                               # spokes' peer endpoint and break the mesh.
SKIP_LOCAL_B2_CHECK=false      # NEW 2026-06-14 — surfaced by Hub DR Drill #1:
                               # preflight check #6 runs `docker run restic
                               # snapshots` from the OPERATOR's machine to
                               # verify B2 access. But the actual restore
                               # runs on the TARGET (restic_remote() at
                               # line 211), which has a Vultr datacenter
                               # egress IP. So if the operator is on a
                               # network that can't reach the B2 regional
                               # S3 endpoint (geo-block, ISP-level TLS RST,
                               # etc. — verified: WSL on a Turkish ISP gets
                               # SSL_ERROR_SYSCALL on Client Hello to
                               # s3.us-west-004.backblazeb2.com, while
                               # vps2/3 + a fresh Vultr droplet have no
                               # problem), the preflight fails on a check
                               # that isn't actually predictive of restore
                               # success. This flag skips JUST check #6;
                               # all other preflight (env, SSH, freshness)
                               # still runs.
SNAPSHOT_ID="latest"
ENV_FROM="/opt/fabrik-dr-store/env/latest"
SYSADMIN_ENV_FROM="/opt/fabrik-dr-store/env/sysadmin-latest"
CF_REWRITE_TARGET=""   # empty = skip step 17
REMOTE=""              # set from positional arg
EFFECTIVE_REMOTE=""    # mutated by step_00 from root@ to ozgur@

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------
usage() {
    # Print the header comment block (lines 2..first non-comment line).
    # Earlier version used `^#$` as the stop pattern which truncated at the
    # first inter-section blank-comment line; this version stops only when
    # the line stops starting with '#'.
    awk 'NR>1 { if (/^[^#]/) exit; sub(/^# ?/,""); print }' "$0"
    exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --verify) VERIFY_ONLY=true; shift ;;
        --skip-services) SKIP_SERVICES=true; shift ;;
        --skip-mesh) SKIP_MESH=true; shift ;;
        --skip-local-b2-check) SKIP_LOCAL_B2_CHECK=true; shift ;;
        --snapshot) SNAPSHOT_ID="$2"; shift 2 ;;
        --env-from) ENV_FROM="$2"; shift 2 ;;
        --sysadmin-env-from) SYSADMIN_ENV_FROM="$2"; shift 2 ;;
        --cf-rewrite-dns) CF_REWRITE_TARGET="$2"; shift 2 ;;
        --help|-h) usage 0 ;;
        --*) echo "unknown flag: $1" >&2; usage 2 ;;
        *)
            if [[ -z "$REMOTE" ]]; then
                REMOTE="$1"
                shift
            else
                echo "unexpected positional arg: $1" >&2
                usage 2
            fi
            ;;
    esac
done

if [[ -z "$REMOTE" ]]; then
    echo "error: missing required positional arg: root@<new-vps-ip>" >&2
    usage 2
fi
EFFECTIVE_REMOTE="$REMOTE"

# ---------------------------------------------------------------------------
# Output helpers (verbatim style match with bootstrap-vps.sh)
# ---------------------------------------------------------------------------
c_reset='\033[0m'
c_dim='\033[2m'
c_red='\033[31m'
c_green='\033[32m'
c_yellow='\033[33m'
c_blue='\033[34m'
if [[ ! -t 1 ]]; then
    c_reset='' c_dim='' c_red='' c_green='' c_yellow='' c_blue=''
fi
log()   { echo -e "${c_blue}[bootstrap-hub]${c_reset} $*"; }
ok()    { echo -e "${c_green}[ ok ]${c_reset} $*"; }
warn()  { echo -e "${c_yellow}[WARN]${c_reset} $*"; }
err()   { echo -e "${c_red}[FAIL]${c_reset} $*" >&2; }
dim()   { echo -e "${c_dim}$*${c_reset}"; }

# ---------------------------------------------------------------------------
# Remote-execution helpers
# ---------------------------------------------------------------------------
# Run on the new VPS as the EFFECTIVE_REMOTE user.
remote() {
    local cmd="$*"
    if $DRY_RUN; then
        dim "    [dry-run] ssh ${EFFECTIVE_REMOTE} '${cmd}'"
        return 0
    fi
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${EFFECTIVE_REMOTE}" "${cmd}"
}

# Run on the new VPS as the INITIAL user (root). Step 00 only.
remote_as_initial() {
    local cmd="$*"
    if $DRY_RUN; then
        dim "    [dry-run] ssh ${REMOTE} '${cmd}'"
        return 0
    fi
    ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new "${REMOTE}" "${cmd}"
}

# Run a restic command via docker on the new VPS, against the B2 repo.
# Pulls B2 creds + RESTIC_PASSWORD from /opt/fabrik/.env (which step 04 placed).
#
# IMPORTANT — host-filesystem semantics:
#   The container mounts the host root at /host (rw). Any restore command
#   passed here MUST use `--target /host` so files land on the host
#   filesystem. Using bare `--target /` writes inside the ephemeral container
#   filesystem and silently no-ops.
restic_remote() {
    local cmd="$*"
    if $DRY_RUN; then
        dim "    [dry-run] restic_remote: ${cmd}"
        return 0
    fi
    # Read the 3 specific values we need from /opt/fabrik/.env via grep+cut
    # inside a sudo bash -c subshell. The .env file:
    #   - is 600 root:root (correct security; secrets MUST NOT be readable
    #     by non-root) — Bug #3 fix: don't try to source as ozgur.
    #   - contains MANY non-restic vars, some with shell-incompatible
    #     values (e.g. `GMAIL_QUERY=is:unread newer_than:2d
    #     subject:("Login" OR ...)`) — Bug #5 (Hub DR Drill #4 finding,
    #     2026-06-14): we CANNOT `source` the file because bash parses
    #     unquoted parens etc. as syntax errors. Cascades to Bug #6:
    #     restic 0.18.1 refuses to run with an empty RESTIC_PASSWORD.
    #
    # Fix (drill #5): extract only the 3 specific values we need with
    # grep+cut, never touching the bash parser on the file. The
    # remainder of the .env stays untouched. The sudo bash -c subshell
    # runs everything as root (so grep + docker run both have the right
    # perms in one wrapper).
    remote "sudo bash -c '
        B2_KEY=\$(grep \"^B2_KEY_ID=\" /opt/fabrik/.env | cut -d= -f2-)
        B2_SECRET=\$(grep \"^B2_APPLICATION_KEY=\" /opt/fabrik/.env | cut -d= -f2-)
        B2_PW=\$(grep \"^BACKREST_RESTIC_PASSWORD=\" /opt/fabrik/.env | cut -d= -f2-)
        if [[ -z \"\$B2_KEY\" || -z \"\$B2_SECRET\" || -z \"\$B2_PW\" ]]; then
            echo \"step_06/11/12: one of B2_KEY_ID / B2_APPLICATION_KEY / BACKREST_RESTIC_PASSWORD missing from /opt/fabrik/.env\" >&2
            exit 1
        fi
        docker run --rm \
            -e AWS_ACCESS_KEY_ID=\"\$B2_KEY\" \
            -e AWS_SECRET_ACCESS_KEY=\"\$B2_SECRET\" \
            -e RESTIC_PASSWORD=\"\$B2_PW\" \
            -e RESTIC_REPOSITORY=\"${FABRIK_RESTIC_REPO_URI}\" \
            -v /:/host \
            restic/restic:0.18.1 ${cmd}
    '"
}

# ---------------------------------------------------------------------------
# Pre-flight (numbered checks, all-or-nothing)
# ---------------------------------------------------------------------------
preflight() {
    log "preflight checks ..."

    # 1. Local: env source files exist
    if [[ ! -r "$ENV_FROM" ]]; then
        err "env source not readable: $ENV_FROM. Did you 'gh repo clone mobasak/fabrik-dr-store /opt/fabrik-dr-store'?"
        return 1
    fi
    ok "W9 env source present: $ENV_FROM"
    if [[ -r "$SYSADMIN_ENV_FROM" ]]; then
        ok "W9 sysadmin env source present: $SYSADMIN_ENV_FROM"
    else
        warn "sysadmin env source absent: $SYSADMIN_ENV_FROM (bot creds will be missing; recoverable but bot won't start)"
    fi

    # 2. Local: B2 creds + restic password parseable from env
    local b2_key b2_secret restic_pw
    b2_key=$(grep '^B2_KEY_ID=' "$ENV_FROM" | cut -d= -f2-)
    b2_secret=$(grep '^B2_APPLICATION_KEY=' "$ENV_FROM" | cut -d= -f2-)
    restic_pw=$(grep '^BACKREST_RESTIC_PASSWORD=' "$ENV_FROM" | cut -d= -f2-)
    if [[ -z "$b2_key" || -z "$b2_secret" || -z "$restic_pw" ]]; then
        err "W9 env is missing one of: B2_KEY_ID, B2_APPLICATION_KEY, BACKREST_RESTIC_PASSWORD"
        return 1
    fi
    ok "B2 creds + restic password parsed from env (len: key=${#b2_key}, secret=${#b2_secret}, pw=${#restic_pw})"

    # 3. Local: docker available for restic-via-docker pre-validation
    if ! command -v docker &>/dev/null; then
        err "docker not installed on dev machine — needed for local restic pre-flight against B2"
        return 1
    fi
    ok "local docker available"

    # 4. Remote: SSH works to the new VPS.
    #
    # SAFE-RERUN TRAP (added 2026-06-07 after first DR drill on bootstrap-vps.sh
    # tripped fail2ban on root@<ip> re-runs). On a freshly provisioned VPS the
    # script is called as root@<ip>. step_01 disables root login. On a re-run
    # with the same root@<ip> argv, the SSH preflight fails; three quick
    # retries trip fail2ban (default 3-failure threshold / 10min). Detect
    # this case BEFORE triggering the ban:
    #   a) try root@<host>
    #   b) on failure, try ozgur@<host> (the sudoer step_00 creates)
    #   c) if ozgur@ works, emit an actionable error telling the operator
    #      EXACTLY how to re-invoke, then exit cleanly before more failed
    #      auth attempts hit fail2ban.
    if ! ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
            -o BatchMode=yes "${REMOTE}" 'echo ok' &>/dev/null; then
        local host_part="${REMOTE#*@}"
        if [[ "${REMOTE%%@*}" == "root" ]] \
           && ssh -o ConnectTimeout=10 -o BatchMode=yes \
                  -o StrictHostKeyChecking=accept-new \
                  "ozgur@${host_part}" 'sudo -n id' &>/dev/null; then
            err "SSH to ${REMOTE} failed BUT ssh ozgur@${host_part} works."
            err "step_01 has already run on this host (root login disabled)."
            err ""
            err "Re-run as the sudoer:"
            err "  $0 ozgur@${host_part} [other-args]"
            err ""
            err "Stopping now — additional root@<ip> retries WILL trip fail2ban (default 3 failures / 10 min) and lock you out."
            return 1
        fi
        err "cannot SSH to ${REMOTE}. Confirm: (a) host reachable, (b) your pubkey in target's authorized_keys."
        return 1
    fi
    ok "SSH to ${REMOTE} works"

    # 5. Remote: target is fresh (no existing /opt/fabrik/)
    local existing
    existing=$(remote_as_initial 'test -d /opt/fabrik && echo dirty || echo fresh' 2>/dev/null || echo unknown)
    if [[ "$existing" == "dirty" ]]; then
        warn "target VPS already has /opt/fabrik/ — this run will re-apply over existing state (idempotent, but unusual)"
    else
        ok "target VPS is fresh (no existing /opt/fabrik)"
    fi

    # 6. Local: B2 bucket reachable + restic repo accessible (verify creds before SSHing further).
    # SKIPPED when --skip-local-b2-check is passed (Hub DR Drill #1 finding,
    # 2026-06-14): the actual restic restore runs on the TARGET (see
    # restic_remote()), so the only thing this check predicts is whether
    # the OPERATOR's machine can reach B2 — not whether the target can.
    # On networks where B2's regional S3 endpoint is unreachable (e.g.
    # WSL on a Turkish ISP — SSL_ERROR_SYSCALL during TLS Client Hello to
    # s3.us-west-004.backblazeb2.com), this check fails 10× before giving
    # up, while a `fabrik vultr drill hub` from the same operator would
    # have succeeded because the target droplet's Vultr datacenter IP
    # has no such block.
    if $SKIP_LOCAL_B2_CHECK; then
        warn "preflight check #6 SKIPPED (--skip-local-b2-check) — caller asserts target can reach B2"
        return 0
    fi
    local snapshots
    snapshots=$(docker run --rm \
        -e AWS_ACCESS_KEY_ID="$b2_key" \
        -e AWS_SECRET_ACCESS_KEY="$b2_secret" \
        -e RESTIC_PASSWORD="$restic_pw" \
        -e RESTIC_REPOSITORY="$FABRIK_RESTIC_REPO_URI" \
        restic/restic:0.18.1 snapshots --json 2>&1) || {
        err "restic could not list snapshots in $FABRIK_RESTIC_REPO_URI"
        err "  output: $snapshots"
        err ""
        err "  If your network can't reach the B2 regional S3 endpoint but"
        err "  you have other evidence the target droplet can, re-run with"
        err "  --skip-local-b2-check. The actual restore runs on the target."
        return 1
    }
    local snapshot_count
    snapshot_count=$(echo "$snapshots" | jq 'length' 2>/dev/null || echo 0)
    if [[ "$snapshot_count" -lt 1 ]]; then
        err "B2 repo has 0 snapshots — nothing to restore. Was the source vps1 actually being backed up?"
        return 1
    fi
    ok "B2 repo reachable; ${snapshot_count} snapshot(s) available"

    # 7. Sanity: target snapshot ID exists
    if [[ "$SNAPSHOT_ID" != "latest" ]]; then
        if ! echo "$snapshots" | jq -e ".[] | select(.short_id == \"$SNAPSHOT_ID\")" &>/dev/null; then
            err "snapshot $SNAPSHOT_ID not found in B2 repo"
            return 1
        fi
        ok "target snapshot $SNAPSHOT_ID exists"
    fi

    return 0
}

# ---------------------------------------------------------------------------
# Step blocks — every block is idempotent
# (this is the SKELETON: stubs only this turn; logic fills in step-by-step)
# ---------------------------------------------------------------------------

step_00_create_sudo_user() {
    # Match vps1's posture: create unprivileged sudoer with NOPASSWD, install
    # operator's pubkey, switch EFFECTIVE_REMOTE so subsequent steps run as
    # the sudoer. Mirrors bootstrap-vps.sh step_00 with the same SSH-key
    # candidate scan (ed25519 → ecdsa → rsa → ssh -G suggestions).
    local user="${FABRIK_SUDOER_USER}"
    log "step_00: create sudoer user '${user}' ($(elapsed))"

    local pubkey=""
    if ! $DRY_RUN; then
        local candidates=(
            "${HOME}/.ssh/id_ed25519.pub"
            "${HOME}/.ssh/id_ecdsa.pub"
            "${HOME}/.ssh/id_rsa.pub"
        )
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
            err "step_00: no public key found in: ${candidates[*]}"
            return 1
        fi
    fi

    # Idempotent: useradd guarded by id, key install uses grep before append,
    # sudoers entry written via 0440 install.
    remote_as_initial "sudo bash -c '
        if ! id ${user} >/dev/null 2>&1; then
            useradd -m -s /bin/bash ${user}
        fi
        mkdir -p /home/${user}/.ssh
        chmod 700 /home/${user}/.ssh
        touch /home/${user}/.ssh/authorized_keys
        chmod 600 /home/${user}/.ssh/authorized_keys
        chown -R ${user}:${user} /home/${user}/.ssh
        if ! grep -qxF \"${pubkey}\" /home/${user}/.ssh/authorized_keys; then
            echo \"${pubkey}\" >> /home/${user}/.ssh/authorized_keys
        fi
        echo \"${user} ALL=(ALL) NOPASSWD:ALL\" > /etc/sudoers.d/${user}
        chmod 0440 /etc/sudoers.d/${user}
        visudo -cf /etc/sudoers.d/${user} >/dev/null
    '"

    # Switch effective remote and verify it works before later steps depend on it.
    local host="${REMOTE#*@}"
    EFFECTIVE_REMOTE="${user}@${host}"
    if $DRY_RUN; then
        dim "    [dry-run] EFFECTIVE_REMOTE → ${EFFECTIVE_REMOTE}"
    else
        if remote 'sudo -n true' &>/dev/null; then
            ok "step_00 done — NOPASSWD sudo works as ${user}"
        else
            err "step_00: cannot sudo as ${user} after creation"
            return 1
        fi
    fi
}

step_01_harden_ssh() {
    log "step_01: harden SSH (PermitRootLogin no, PasswordAuthentication no) ($(elapsed))"
    # Only mutate if not already hardened. sed -E with idempotent replacements.
    remote 'sudo bash -c "
        sed -i -E \"s/^#?PermitRootLogin .*/PermitRootLogin no/\" /etc/ssh/sshd_config
        sed -i -E \"s/^#?PasswordAuthentication .*/PasswordAuthentication no/\" /etc/ssh/sshd_config
        # Drop-in for absolute certainty (sshd reads /etc/ssh/sshd_config.d/*.conf last)
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
    # Bug #8 (Hub DR Drill #6, 2026-06-15): Vultr's stock Ubuntu 24.04 image
    # runs `unattended-upgrades` at boot. If our step_02 apt calls arrive
    # while that's still holding /var/lib/dpkg/lock-frontend, apt exits
    # 100 with "Could not get lock". Drills #2-#5 won the race by luck
    # (~60-90s into boot); drill #6 lost it. Tell apt to wait up to 5 min
    # for the lock before failing — surgical fix that doesn't disable
    # unattended-upgrades (which is a genuinely useful default on a
    # production-restore target).
    local apt_lock_wait='-o DPkg::Lock::Timeout=300'

    # Docker via official one-liner (matches bootstrap-vps.sh step_03 + vps1's history).
    # get.docker.com's installer runs apt internally; it doesn't honor our
    # DPkg::Lock::Timeout flag. Wait for the lock to be free before invoking it.
    remote 'command -v docker >/dev/null || (
        while sudo fuser /var/lib/dpkg/lock-frontend &>/dev/null; do
            echo "waiting for dpkg lock (unattended-upgrades?)..." >&2
            sleep 5
        done
        curl -fsSL https://get.docker.com | sudo sh
    )'

    # System packages. NOTE (G5-for-hub, 2026-06-14): do NOT install
    # `iptables-persistent` here. On Ubuntu 24.04 noble it declares
    # `Conflicts: ufw`, and apt refuses to install both in the same
    # command — exits 100 with "E: Unable to correct problems, you have
    # held broken packages." (Verified live in Hub DR Drill #2: drill
    # surfaced this DR-blocker as the first measured live failure of
    # bootstrap-hub.sh on a fresh Ubuntu 24.04 droplet.)
    #
    # DOCKER-USER chain persistence is provided by
    # `iptables-docker-user.service` (custom oneshot unit, identical
    # shape to the spoke unit shipped in G5 / `c158ee2`). OpenVPN
    # forward-rule persistence is provided by `iptables-openvpn.service`.
    # Both units are restored from the host-state Backrest snapshot in
    # step_06. step_09 enables them and treats `netfilter-persistent`
    # (from this dropped package) as optional — present on pre-G5 hubs,
    # absent on post-G5 fresh installs, either way the custom units do
    # the work.
    remote "sudo bash -c '
        DEBIAN_FRONTEND=noninteractive apt-get ${apt_lock_wait} update -qq
        DEBIAN_FRONTEND=noninteractive apt-get ${apt_lock_wait} install -y -qq \
            wireguard wireguard-tools \
            ufw fail2ban \
            python3 python3-pip \
            inotify-tools \
            jq curl ca-certificates gnupg
    '"

    # gh CLI from its official apt repo (idempotent registration).
    remote "command -v gh >/dev/null || sudo bash -c '
        curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
        chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg
        echo \"deb [arch=\$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\" > /etc/apt/sources.list.d/github-cli.list
        apt-get ${apt_lock_wait} update -qq
        DEBIAN_FRONTEND=noninteractive apt-get ${apt_lock_wait} install -y -qq gh
    '"

    # Member of docker group so the new sudoer can run docker without sudo.
    remote "sudo usermod -aG docker ${FABRIK_SUDOER_USER}"
    ok "step_02 done"
}

step_03_install_claude_code() {
    log "step_03: install Claude Code CLI (for vps-sysadmin-bot) ($(elapsed))"
    # Official installer — standalone binary, no Node dependency.
    # Runs as the sudoer so the install lands under ~/.local/bin, then we
    # symlink to /usr/local/bin so systemd's default PATH picks it up.
    remote 'command -v claude >/dev/null || (
        curl -fsSL https://claude.ai/install.sh | bash &&
        sudo ln -sfn "$HOME/.local/bin/claude" /usr/local/bin/claude
    )'
    # Verify it runs without auth (auth happens later, post-restore, via
    # operator running `claude auth login` once).
    remote 'claude --version' || warn "step_03: claude --version failed; check install"
    ok "step_03 done"
}

step_04_clone_dr_store_env() {
    log "step_04: scp W9 env mirror onto new VPS ($(elapsed))"
    # Source files: $ENV_FROM (default /opt/fabrik-dr-store/env/latest) and
    # $SYSADMIN_ENV_FROM. Preflight already confirmed they're readable.
    # Atomic placement: scp to /tmp first, then sudo mv into /opt/fabrik/
    # with restrictive perms. /opt/fabrik must exist before scp.

    remote "sudo mkdir -p /opt/fabrik && sudo chown ${FABRIK_SUDOER_USER}:${FABRIK_SUDOER_USER} /opt/fabrik"

    if $DRY_RUN; then
        dim "    [dry-run] scp ${ENV_FROM} ${EFFECTIVE_REMOTE}:/tmp/.fabrik-env"
        dim "    [dry-run] scp ${SYSADMIN_ENV_FROM} ${EFFECTIVE_REMOTE}:/tmp/.fabrik-env-sysadmin"
    else
        scp -o ConnectTimeout=10 "${ENV_FROM}" "${EFFECTIVE_REMOTE}:/tmp/.fabrik-env"
        if [[ -r "$SYSADMIN_ENV_FROM" ]]; then
            scp -o ConnectTimeout=10 "${SYSADMIN_ENV_FROM}" "${EFFECTIVE_REMOTE}:/tmp/.fabrik-env-sysadmin"
        else
            warn "step_04: SYSADMIN_ENV_FROM absent; bot creds will be missing on restore"
        fi
    fi

    remote 'sudo bash -c "
        install -m 600 -o root -g root /tmp/.fabrik-env /opt/fabrik/.env
        rm -f /tmp/.fabrik-env
        if [ -f /tmp/.fabrik-env-sysadmin ]; then
            install -m 600 -o root -g root /tmp/.fabrik-env-sysadmin /opt/fabrik/.env.sysadmin
            rm -f /tmp/.fabrik-env-sysadmin
        fi
    "'

    # Sanity: required keys present.
    remote 'sudo grep -qE "^B2_KEY_ID=." /opt/fabrik/.env && \
            sudo grep -qE "^B2_APPLICATION_KEY=." /opt/fabrik/.env && \
            sudo grep -qE "^BACKREST_RESTIC_PASSWORD=." /opt/fabrik/.env' \
        || { err "step_04: /opt/fabrik/.env is missing one of B2_KEY_ID / B2_APPLICATION_KEY / BACKREST_RESTIC_PASSWORD"; return 1; }
    ok "step_04 done"
}

step_05_write_docker_daemon_json() {
    # NOTE: this writes the CURRENT vps1 daemon.json verbatim (per inventory § B).
    # Step 06's restic restore will overwrite it with whatever was backed up —
    # which should be byte-identical. The point of writing here is so the very
    # FIRST docker start (e.g. during step_02's install or step_10's network
    # create) uses our log rotation + promtail tag config, not Docker's defaults.
    log "step_05: write /etc/docker/daemon.json (log rotation + promtail tag) ($(elapsed))"
    remote 'sudo bash -c "
        mkdir -p /etc/docker
        cat > /etc/docker/daemon.json <<EOF
{
  \"log-driver\": \"json-file\",
  \"log-opts\": {
    \"max-size\": \"10m\",
    \"max-file\": \"3\",
    \"tag\": \"{{.Name}}\"
  },
  \"default-address-pools\": [
    {\"base\": \"10.0.0.0/8\", \"size\": 24}
  ],
  \"dns\": [\"1.1.1.1\", \"8.8.8.8\"]
}
EOF
        systemctl restart docker
    "'
    ok "step_05 done"
}

step_06_restic_pull_host_state() {
    log "step_06: restic restore host-level state from B2 ($(elapsed))"
    # Build the --include list from FABRIK_HOST_STATE_INCLUDES.
    #
    # Bug #4 (Hub DR Drill #3 finding, 2026-06-14): restic 0.18.1 errors
    # immediately with "Fatal: exclude and include patterns are mutually
    # exclusive" when --include and --exclude are passed together on
    # `restic restore`. The original code built both lists and passed
    # them in the same command, which never worked on 0.18.1. (Some
    # older restic versions allowed it; we don't pin to one of those.)
    #
    # Manual analysis 2026-06-14 confirmed no FABRIK_HOST_STATE_EXCLUDES
    # entry overlaps with any FABRIK_HOST_STATE_INCLUDES entry — the
    # INCLUDES list is a specific whitelist of files/dirs (no broad
    # `/etc` parent that could pull in `/etc/netplan/` or `/etc/hosts`).
    # So the EXCLUDES were effectively a no-op even on a restic version
    # that accepted them. We drop --exclude here; the EXCLUDES array
    # stays in bootstrap-config.sh as a SAFETY DOCUMENT — if INCLUDES
    # ever grows to a broader parent, revisit this step and either
    # (a) add a second `restic restore` call with --exclude only, OR
    # (b) restore-then-rm the excluded subpaths post-restore.
    local includes=""
    for p in "${FABRIK_HOST_STATE_INCLUDES[@]}"; do
        includes+=" --include ${p}"
    done

    # Bug #9 (Hub DR Drill #6c+#6d, 2026-06-15): the host-state plan includes
    # /home/ozgur/.ssh/authorized_keys and /root/.ssh/authorized_keys. restic
    # restore overwrites them wholesale with the snapshot's contents — losing
    # the operator's currently-active key unless the snapshot happens to
    # contain it. The very next ssh-as-ozgur call fails with "Permission
    # denied (publickey,password)" and bootstrap can't continue.
    #
    # The fix must run backup + restore + merge in ONE ssh session, because
    # a second SSH call AFTER the restore can't authenticate yet (drill #6d
    # confirmed this). Bundle everything into one `sudo bash -c` block:
    #   1. capture pre-restore authorized_keys for ozgur + root
    #   2. invoke restic restore directly (replicating restic_remote's body
    #      so it runs in the SAME shell — not a separate ssh call)
    #   3. merge pre-restore keys back, dedupe, fix ownership + perms
    # The connection was authenticated by step (1)'s ssh; restic's overwrite
    # in step (2) doesn't kill that already-open session, so step (3) runs.
    remote "sudo bash -c '
        set -e
        mkdir -p /tmp/preboot-keys
        cp /home/ozgur/.ssh/authorized_keys /tmp/preboot-keys/ozgur.authkeys 2>/dev/null || true
        cp /root/.ssh/authorized_keys      /tmp/preboot-keys/root.authkeys  2>/dev/null || true

        # restic restore (inlined restic_remote logic — must run in this
        # shell, NOT a separate remote() call).
        # Tag is plan:host-state (Backrest namespacing — drill #5 finding).
        B2_KEY=\$(grep \"^B2_KEY_ID=\" /opt/fabrik/.env | cut -d= -f2-)
        B2_SECRET=\$(grep \"^B2_APPLICATION_KEY=\" /opt/fabrik/.env | cut -d= -f2-)
        B2_PW=\$(grep \"^BACKREST_RESTIC_PASSWORD=\" /opt/fabrik/.env | cut -d= -f2-)
        if [[ -z \"\$B2_KEY\" || -z \"\$B2_SECRET\" || -z \"\$B2_PW\" ]]; then
            echo \"step_06: one of B2_KEY_ID / B2_APPLICATION_KEY / BACKREST_RESTIC_PASSWORD missing from /opt/fabrik/.env\" >&2
            exit 1
        fi
        docker run --rm \
            -e AWS_ACCESS_KEY_ID=\"\$B2_KEY\" \
            -e AWS_SECRET_ACCESS_KEY=\"\$B2_SECRET\" \
            -e RESTIC_PASSWORD=\"\$B2_PW\" \
            -e RESTIC_REPOSITORY=\"${FABRIK_RESTIC_REPO_URI}\" \
            -v /:/host \
            restic/restic:0.18.1 restore ${SNAPSHOT_ID} --target /host${includes} --tag plan:host-state

        # Merge pre-restore authorized_keys back in. dedupe non-empty lines
        # with awk so we do not duplicate keys the snapshot already had.
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

        # Fix ownership + perms — restic may have restored with the
        # snapshot UID/GID (vps1 ozgur uid may not match drill-droplet
        # ozgur uid) or with perms != 0600/0700, both of which make sshd
        # refuse the key.
        chown -R ozgur:ozgur /home/ozgur/.ssh
        chown -R root:root   /root/.ssh
        chmod 700 /home/ozgur/.ssh /root/.ssh
        chmod 600 /home/ozgur/.ssh/authorized_keys /root/.ssh/authorized_keys
        rm -rf /tmp/preboot-keys
    '"

    # Reload systemd so newly-restored unit files are picked up before later
    # steps try to enable them. (Separate ssh call — fine now, authkeys merged.)
    remote 'sudo systemctl daemon-reload'

    # Root crontab is NOT in the host-state plan (Backrest image symlink
    # conflict on /var/spool/cron/crontabs → /etc/crontabs). It's dumped
    # nightly by pre-backup.sh to /opt/backups/root-crontab.txt and gets
    # replayed in step_16 once /opt/ is restored.

    # Sanity: critical files are now present.
    # Bug #11 (Hub DR Drill #6f, 2026-06-15): /etc/wireguard is mode 0700
    # root:root on vps1 (and on the restored droplet). ozgur can't traverse
    # the dir → `test -f /etc/wireguard/wg0.conf` returns false even when
    # the file exists. Must run the check via sudo so the test runs as root.
    remote 'sudo test -f /etc/wireguard/wg0.conf && \
            sudo test -f /etc/iptables/add-docker-user-rules.sh && \
            sudo test -f /etc/systemd/system/vps-sysadmin-bot.service && \
            sudo test -f /etc/sudoers.d/ozgur' \
        || { err "step_06: one of wg0.conf / DOCKER-USER script / bot unit / sudoers.d missing post-restore"; return 1; }
    ok "step_06 done"
}

step_07_apply_ufw() {
    log "step_07: enable + reload UFW (user.rules/user6.rules restored in step_06) ($(elapsed))"
    # rules.v4/v6 + user.rules/user6.rules already on disk from step_06.
    # `ufw --force enable` is idempotent and doesn't prompt.
    remote 'sudo ufw --force enable && sudo ufw reload'
    remote 'sudo systemctl enable --now ufw fail2ban'

    # Defensive backstop: re-apply the spoke↔spoke wg0 routing rule (shipped
    # 2026-06-06). This is normally restored as part of /etc/ufw/user.rules,
    # but if the hub rebuild happens BEFORE the first Backrest snapshot that
    # includes the rule (the rule was applied 2026-06-06 ~21:00 UTC; nightly
    # backup at 02:00 UTC captured it after that), the restored user.rules
    # won't have it and vps2↔vps3 direct mesh reach silently breaks. Re-
    # applying here is idempotent — UFW deduplicates identical route rules.
    # vps1 already has net.ipv4.ip_forward=1 from the OpenVPN sysctl set
    # which is restored via /etc/sysctl.d/99-* in step_06.
    remote 'sudo ufw route allow in on wg0 out on wg0 2>&1 | tail -1'

    # Sanity: expect 12+ rules (vps1 had 6 IPv4 + 6 IPv6 mirrors per W5 audit;
    # 2026-06-06 added 2 aro-wake allow rules + 1 route rule = 12 → 15).
    local rule_count
    if ! $DRY_RUN; then
        rule_count=$(remote 'sudo ufw status numbered 2>/dev/null | grep -cE "^\["') || rule_count=0
        if (( rule_count < 12 )); then
            warn "step_07: only ${rule_count} UFW rules active (expected 12-15: 6 v4 + 6 v6 mirrors + post-2026-06-06 trio rules); restore may be incomplete"
        else
            ok "step_07 done — ${rule_count} UFW rules active"
        fi
    else
        ok "step_07 done (dry-run)"
    fi
}

step_08_bring_up_mesh() {
    if $SKIP_MESH; then
        log "step_08: SKIPPED (--skip-mesh — drill safety: would handshake with vps2/vps3 using restored vps1 key and overwrite live spokes' peer endpoint)"
        return 0
    fi
    log "step_08: bring up Wireguard mesh (wg-quick@wg0) ($(elapsed))"
    remote 'sudo systemctl enable --now wg-quick@wg0'
    # Give the kernel a moment to come up + spokes time to handshake (cross-Atlantic).
    if ! $DRY_RUN; then
        sleep 5
        local peers handshakes
        peers=$(remote 'sudo wg show wg0 peers 2>/dev/null | wc -l') || peers=0
        handshakes=$(remote 'sudo wg show wg0 latest-handshakes 2>/dev/null | awk "(systime()-\$2) < 180 {c++} END {print c+0}"') || handshakes=0
        log "  mesh peers configured: ${peers}, handshaking within last 3 min: ${handshakes}"
        if (( handshakes < 1 )); then
            warn "step_08: 0 peers handshaking — spokes may not have re-converged yet; continuing"
        fi
    fi
    ok "step_08 done"
}

step_09_apply_iptables_boot_state() {
    log "step_09: enable iptables boot units (netfilter-persistent? + docker-user + openvpn) ($(elapsed))"
    # Order matters:
    #  1. (optional) netfilter-persistent — loads /etc/iptables/rules.v4 + v6.
    #     Only present on pre-G5 hubs that still had `iptables-persistent`
    #     installed. Post-G5 fresh installs (step_02 no longer apt-installs
    #     the package because it `Conflicts: ufw` on Ubuntu 24.04 — see G5-
    #     for-hub note in step_02) won't have this unit, and the custom
    #     units below provide the actual DOCKER-USER + OpenVPN persistence.
    #  2. iptables-docker-user — applies DOCKER-USER chain rules (depends on wg0 from step_08)
    #  3. iptables-openvpn — applies OpenVPN forward rules (depends on wg0 + docker bridge)
    if remote 'systemctl list-unit-files netfilter-persistent.service 2>/dev/null | grep -q "^netfilter-persistent\.service"'; then
        remote 'sudo systemctl enable --now netfilter-persistent'
        ok "  netfilter-persistent enabled (legacy iptables-persistent path)"
    else
        log "  netfilter-persistent absent (post-G5 install) — skipped; DOCKER-USER + OpenVPN handled by custom units below"
    fi
    remote 'sudo systemctl enable --now iptables-docker-user iptables-openvpn'

    # Sanity: DOCKER-USER chain has rules.
    if ! $DRY_RUN; then
        local chain_rules
        chain_rules=$(remote 'sudo iptables -L DOCKER-USER -n 2>/dev/null | grep -cE "DROP|ACCEPT"') || chain_rules=0
        if (( chain_rules < 1 )); then
            warn "step_09: DOCKER-USER chain has 0 explicit rules — mesh ACCEPT + public DROP not applied"
        else
            ok "step_09 done — DOCKER-USER chain: ${chain_rules} rules"
        fi
    else
        ok "step_09 done (dry-run)"
    fi
}

step_10_create_fabrik_network() {
    log "step_10: docker network create fabrik (idempotent) ($(elapsed))"
    remote 'sudo docker network inspect fabrik >/dev/null 2>&1 || sudo docker network create fabrik'
    ok "step_10 done"
}

step_11_restic_pull_opt() {
    log "step_11: restic restore /opt/ from B2 ($(elapsed))"
    # Bug #4 also bites here (same root cause as step_06): restic 0.18.1
    # rejects --include + --exclude together. UNLIKE step_06 — where the
    # EXCLUDES were documentation-only safety — these EXCLUDES are
    # FUNCTIONAL and CANNOT be silently dropped. They prevent the
    # restored hub from inheriting:
    #   - /opt/containerd/** : the dead host's containerd state, which
    #     would corrupt the new Docker install (new Docker uses /var/lib/
    #     containerd; any restored /opt/containerd would be wrong-version
    #     state from the dead host).
    #   - /opt/fabrik/.git/** : not needed — regenerated from `gh repo
    #     clone mobasak/fabrik` in the DR runbook.
    #   - /opt/backups/coolify_env_*.env : Coolify-era secret leakage.
    #   - /opt/*restic-cache* : cache, regenerated on first use.
    #   - /opt/manually_installed.txt : human-edited marker file.
    #
    # FIX: do a single restore --include /opt, then rm the EXCLUDES
    # patterns post-restore. Restic restores everything; the explicit
    # rm cleans up what shouldn't survive. Semantically equivalent to
    # the original include+exclude intent, but actually works with
    # restic 0.18.1.
    # Tag is `plan:opt-configs` (Backrest namespacing — see step_06 note).
    restic_remote "restore ${SNAPSHOT_ID} --target /host --include /opt --tag plan:opt-configs"

    # Post-restore cleanup: rm paths the original FABRIK_OPT_RESTORE_EXCLUDES
    # was trying to prevent from restoring. Each maps to a glob below.
    # Failures non-fatal — `rm -f` and `rm -rf` already tolerate missing
    # paths; this just makes sure none of them survive into the new hub.
    remote 'sudo bash -c "
        rm -rf /opt/containerd
        rm -rf /opt/fabrik/.git
        rm -f  /opt/backups/coolify_env_*.env
        rm -rf /opt/*restic-cache*
        rm -f  /opt/manually_installed.txt
    "' || warn "step_11: post-restore cleanup of exclude paths returned non-zero (non-fatal)"

    # Sanity: at least the critical dirs landed.
    if ! $DRY_RUN; then
        local missing=()
        for svc in postgres redis traefik authelia monitoring backrest; do
            remote "test -d /opt/${svc}" || missing+=("/opt/${svc}")
        done
        if (( ${#missing[@]} > 0 )); then
            err "step_11: missing critical /opt dirs after restore: ${missing[*]}"
            return 1
        fi
        local dir_count
        dir_count=$(remote 'ls -1d /opt/*/ 2>/dev/null | wc -l') || dir_count=0
        ok "step_11 done — ${dir_count} /opt/<svc>/ dirs restored"
    else
        ok "step_11 done (dry-run)"
    fi
}

step_12_restic_pull_docker_volumes() {
    log "step_12: restic restore ${#FABRIK_HUB_VOLUMES_TO_RESTORE[@]} Docker named volumes ($(elapsed))"
    # Strategy: restic stores volume data at /var/lib/docker/volumes/<name>/_data/.
    # `docker volume create <name>` first (idempotent — creates the empty dir
    # if the volume doesn't already exist), then restic restore writes into
    # the _data subdir. Path-preserving bind mounts on the Backrest container
    # mean snapshot paths match host paths 1:1.
    local restored=0 skipped=0
    for vol in "${FABRIK_HUB_VOLUMES_TO_RESTORE[@]}"; do
        log "  restoring volume: ${vol}"
        # Idempotent volume create — Docker no-ops if it exists.
        remote "sudo docker volume create ${vol} >/dev/null"
        # Restore only this volume's path. Restic --include filters by path
        # prefix so this scopes the restore tightly.
        # Tag is `plan:docker-volumes` (Backrest namespacing — see step_06 note).
        restic_remote "restore ${SNAPSHOT_ID} --target /host \
            --include /var/lib/docker/volumes/${vol} \
            --tag plan:docker-volumes" && restored=$((restored+1)) || {
            warn "  volume ${vol} restore returned non-zero — may be empty in snapshot"
            skipped=$((skipped+1))
        }
    done
    ok "step_12 done — restored ${restored}/${#FABRIK_HUB_VOLUMES_TO_RESTORE[@]} (skipped ${skipped})"
}

step_13_compose_up_dep_order() {
    if $SKIP_SERVICES; then
        log "step_13: SKIPPED (--skip-services)"
        return 0
    fi
    log "step_13: docker compose up -d in dep order (${#FABRIK_HUB_SERVICE_START_ORDER[@]} services) ($(elapsed))"
    # For each service in dependency order: if /opt/<svc>/compose.yaml exists,
    # `docker compose up -d`. Wait for postgres-main + redis-main to be healthy
    # before later stacks try to dial them.
    local started=0 skipped=0
    for svc in "${FABRIK_HUB_SERVICE_START_ORDER[@]}"; do
        if ! remote "test -f /opt/${svc}/compose.yaml" 2>/dev/null; then
            warn "  ${svc}: no compose.yaml at /opt/${svc}/ — skipping"
            skipped=$((skipped+1))
            continue
        fi
        log "  ${svc}: docker compose up -d"
        # Long-running images (image pulls + start) can take minutes; allow it.
        remote "cd /opt/${svc} && sudo docker compose up -d"
        started=$((started+1))

        # Post-start health pause for data-store stacks; later stacks depend
        # on them being reachable at their container name.
        case "$svc" in
            postgres)
                log "    waiting for postgres-main to accept connections..."
                if ! $DRY_RUN; then
                    for i in $(seq 1 30); do
                        remote 'sudo docker exec postgres-main pg_isready -U postgres' &>/dev/null && break
                        sleep 2
                    done
                fi
                ;;
            redis)
                log "    waiting for redis-main to respond to PING..."
                if ! $DRY_RUN; then
                    for i in $(seq 1 15); do
                        remote 'sudo docker exec redis-main redis-cli ping' 2>/dev/null | grep -q PONG && break
                        sleep 2
                    done
                fi
                ;;
            traefik)
                # Brief pause for Traefik to bind 80/443 + read labels.
                $DRY_RUN || sleep 5
                ;;
        esac
    done
    if ! $DRY_RUN; then
        local container_count
        container_count=$(remote 'sudo docker ps --format "{{.Names}}" | wc -l') || container_count=0
        ok "step_13 done — ${started} stacks started, ${skipped} skipped (no compose.yaml); ${container_count} containers running"
    else
        ok "step_13 done (dry-run)"
    fi
}

step_14_pg_dump_restore_fallback() {
    log "step_14: pg_dump restore fallback (only if postgres-data volume came up empty) ($(elapsed))"
    if $SKIP_SERVICES; then
        log "  skipped — postgres-main not running (--skip-services)"
        return 0
    fi
    if $DRY_RUN; then
        ok "step_14 done (dry-run)"
        return 0
    fi
    # Probe whether the postgres-data volume restore actually delivered the
    # fleet's databases. If glitchtip + site_provisioner exist, the volume
    # restore worked — skip. If they don't, the volume is empty/fresh and we
    # must replay from /opt/backups/pg_dump_<latest>.sql.
    local dblist
    dblist=$(remote 'sudo docker exec postgres-main psql -U postgres -tAc "SELECT datname FROM pg_database WHERE datname IN (\"glitchtip\", \"site_provisioner\")"' 2>/dev/null || true)
    if echo "$dblist" | grep -qE "glitchtip|site_provisioner"; then
        ok "step_14 — volume restore intact (glitchtip + site_provisioner present), pg_dump fallback not needed"
        return 0
    fi
    log "  postgres-data volume came up empty — replaying from /opt/backups/pg_dump_*.sql"
    local latest_dump
    latest_dump=$(remote 'sudo ls -1t /opt/backups/pg_dump_*.sql 2>/dev/null | head -1')
    if [[ -z "$latest_dump" ]]; then
        err "step_14: no pg_dump_*.sql in /opt/backups/ — neither volume nor dump backup is recoverable"
        return 1
    fi
    log "  restoring from: ${latest_dump}"
    remote "sudo docker exec -i postgres-main psql -U postgres < ${latest_dump}"
    ok "step_14 done — replayed ${latest_dump}"
}

step_15_enable_custom_services() {
    log "step_15: enable custom systemd services (vps-sysadmin-bot + authelia-config-sync) ($(elapsed))"
    # iptables-docker-user + iptables-openvpn were enabled in step_09.
    # vps-sysadmin-bot needs /opt/fabrik/.env.sysadmin (placed in step_04) and
    # claude CLI (installed in step_03 + symlinked to /usr/local/bin/claude).
    # authelia-config-sync watches /opt/authelia/config/ which exists post-step_11.

    # Pre-check: required files exist.
    if ! $DRY_RUN; then
        remote 'test -f /opt/fabrik/.env.sysadmin' \
            || warn "step_15: /opt/fabrik/.env.sysadmin missing — vps-sysadmin-bot will not start"
        remote 'test -f /opt/authelia-config-sync/sync.sh' \
            || warn "step_15: /opt/authelia-config-sync/sync.sh missing — config watcher will not start"
    fi

    remote 'sudo systemctl enable --now vps-sysadmin-bot.service authelia-config-sync.service' || \
        warn "step_15: one of the custom services failed to start — check journalctl -u <unit>"

    ok "step_15 done"
}

step_16_install_root_crontab() {
    log "step_16: replay root crontab from /opt/backups/root-crontab.txt ($(elapsed))"
    # Root crontab is dumped nightly by pre-backup.sh to /opt/backups/root-crontab.txt
    # (W2 Step 5 workaround: the live /var/spool/cron/crontabs path cannot be
    # bind-mounted into the Backrest container due to an image-internal symlink
    # to /etc/crontabs that collides with our /etc:ro mount).
    if $DRY_RUN; then
        ok "step_16 done (dry-run)"
        return 0
    fi
    if remote 'test -f /opt/backups/root-crontab.txt'; then
        remote 'sudo crontab -u root /opt/backups/root-crontab.txt'
        if remote 'sudo crontab -u root -l 2>/dev/null | grep -q "/opt/backups/pre-backup.sh"'; then
            ok "step_16 done — root crontab replayed; pre-backup.sh line present"
        else
            warn "step_16: replayed but pre-backup.sh line missing — check root-crontab.txt content"
        fi
    else
        warn "step_16: /opt/backups/root-crontab.txt not found — no crontab to replay (was the backup taken before this file was added?)"
    fi
}

step_17_cf_rewrite_dns() {
    if [[ -z "$CF_REWRITE_TARGET" ]]; then
        log "step_17: SKIPPED (no --cf-rewrite-dns flag)"
        return 0
    fi
    log "step_17: rewrite *.vps1.ocoron.com A records → ${CF_REWRITE_TARGET} ($(elapsed))"
    # Read CF_TOKEN from the restored .env on the new host.
    local cf_token
    if ! $DRY_RUN; then
        cf_token=$(remote 'sudo grep "^CLOUDFLARE_API_TOKEN=" /opt/fabrik/.env | cut -d= -f2-')
        if [[ -z "$cf_token" ]]; then
            err "step_17: CLOUDFLARE_API_TOKEN missing in /opt/fabrik/.env — cannot rewrite DNS"
            return 1
        fi
    else
        cf_token="DRY_RUN_TOKEN_PLACEHOLDER"
    fi

    # List all A records in the zone whose name contains 'vps1' and has the
    # OLD IP (anything ≠ CF_REWRITE_TARGET). For each, PATCH to the new IP.
    if $DRY_RUN; then
        dim "    [dry-run] would list + PATCH *.vps1.${FABRIK_CF_ZONE_NAME} A records to ${CF_REWRITE_TARGET}"
        ok "step_17 done (dry-run)"
        return 0
    fi

    local records
    records=$(curl -fsSL -H "Authorization: Bearer ${cf_token}" \
        "https://api.cloudflare.com/client/v4/zones/${FABRIK_CF_ZONE_ID}/dns_records?per_page=200&type=A")
    local count_updated=0 count_skipped=0
    while IFS=$'\t' read -r rec_id rec_name rec_content; do
        [[ -z "$rec_id" ]] && continue
        # Only touch names containing 'vps1' OR the apex 'ocoron.com'.
        if [[ "$rec_name" == "vps1.${FABRIK_CF_ZONE_NAME}" ]] || \
           [[ "$rec_name" == *.vps1.${FABRIK_CF_ZONE_NAME} ]] || \
           [[ "$rec_name" == "${FABRIK_CF_ZONE_NAME}" ]] || \
           [[ "$rec_name" == "www.${FABRIK_CF_ZONE_NAME}" ]]; then
            if [[ "$rec_content" == "$CF_REWRITE_TARGET" ]]; then
                log "  ${rec_name} already → ${CF_REWRITE_TARGET}; skip"
                count_skipped=$((count_skipped+1))
                continue
            fi
            log "  ${rec_name}: ${rec_content} → ${CF_REWRITE_TARGET}"
            curl -fsS -X PATCH \
                -H "Authorization: Bearer ${cf_token}" \
                -H "Content-Type: application/json" \
                "https://api.cloudflare.com/client/v4/zones/${FABRIK_CF_ZONE_ID}/dns_records/${rec_id}" \
                --data "{\"content\":\"${CF_REWRITE_TARGET}\"}" >/dev/null
            count_updated=$((count_updated+1))
        fi
    done < <(echo "$records" | jq -r '.result[] | "\(.id)\t\(.name)\t\(.content)"')
    ok "step_17 done — ${count_updated} record(s) updated, ${count_skipped} already correct"
}

step_18_verify_end_state() {
    log "step_18: verify end-state contract (hub-restore-inventory.md § End-state contract) ($(elapsed))"
    if $DRY_RUN; then
        ok "step_18 done (dry-run)"
        return 0
    fi

    local fail=0

    # 1. WG mesh peers handshaking
    local handshakes
    handshakes=$(remote 'sudo wg show wg0 latest-handshakes 2>/dev/null | awk "(systime()-\$2) < 180 {c++} END {print c+0}"') || handshakes=0
    if (( handshakes >= 2 )); then
        ok "  [1/7] wg0 peers handshaking: ${handshakes} (≥2)"
    else
        err "  [1/7] wg0 peers handshaking: ${handshakes} (expected ≥2: vps2 + vps3)"
        fail=$((fail+1))
    fi

    # 2. Container count ≥ 29
    local containers
    containers=$(remote 'sudo docker ps --format "{{.Names}}" | wc -l') || containers=0
    if (( containers >= 29 )); then
        ok "  [2/7] containers running: ${containers} (≥29)"
    else
        err "  [2/7] containers running: ${containers} (expected ≥29)"
        fail=$((fail+1))
    fi

    # 3. Gatus dashboard responds
    if remote 'curl -fsS --max-time 10 -o /dev/null -w "%{http_code}" https://status.vps1.ocoron.com' 2>/dev/null | grep -q '^200$'; then
        ok "  [3/7] Gatus dashboard: HTTP 200"
    else
        err "  [3/7] Gatus dashboard: not 200 (DNS may not have propagated yet, or Traefik cert pending)"
        fail=$((fail+1))
    fi

    # 4. Postgres has glitchtip + site_provisioner
    local dblist
    dblist=$(remote 'sudo docker exec postgres-main psql -U postgres -tAc "SELECT datname FROM pg_database"' 2>/dev/null || echo "")
    if echo "$dblist" | grep -q glitchtip && echo "$dblist" | grep -q site_provisioner; then
        ok "  [4/7] Postgres has glitchtip + site_provisioner DBs"
    else
        err "  [4/7] Postgres missing one of glitchtip / site_provisioner — saw: $(echo "$dblist" | tr "\n" " ")"
        fail=$((fail+1))
    fi

    # 5. Sysadmin bot /health responds locally
    if remote 'curl -fsS --max-time 5 http://127.0.0.1:8017/health' 2>/dev/null | grep -q '"status": *"ok"'; then
        ok "  [5/7] Sysadmin bot health: ok"
    else
        err "  [5/7] Sysadmin bot health: no /health response (check journalctl -u vps-sysadmin-bot)"
        fail=$((fail+1))
    fi

    # 6. Backrest can list snapshots (W2 loop closure)
    local snap_count
    snap_count=$(remote 'sudo docker exec backrest /bin/restic -r '"${FABRIK_RESTIC_REPO_URI}"' snapshots --json 2>/dev/null | jq length 2>/dev/null') || snap_count=0
    if (( snap_count >= 1 )); then
        ok "  [6/7] Backrest can list snapshots: ${snap_count} found"
    else
        err "  [6/7] Backrest cannot list snapshots — W2 loop closure broken; next DR would fail"
        fail=$((fail+1))
    fi

    # 7. Wall-clock report (not a pass/fail, just informational)
    local total_secs=$(($(date +%s) - BOOT_START_TS))
    if (( total_secs <= 5400 )); then
        ok "  [7/7] wall-clock: $(elapsed) (≤ 90 min target)"
    else
        warn "  [7/7] wall-clock: $(elapsed) (>90 min — investigate which step took longest in ${BOOT_LOG_FILE})"
    fi

    if (( fail > 0 )); then
        err "step_18: ${fail} of 7 contract items FAILED — bootstrap-hub.sh has a gap"
        return 1
    fi
    ok "step_18 done — all 7 contract items PASS"
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
BOOT_START_TS=0
BOOT_LOG_FILE=""

elapsed() {
    local now=$(date +%s)
    local secs=$((now - BOOT_START_TS))
    printf "%dm%02ds" $((secs / 60)) $((secs % 60))
}

main() {
    BOOT_START_TS=$(date +%s)
    BOOT_LOG_FILE="/tmp/bootstrap-hub-$(date -u +%Y%m%dT%H%M%SZ).log"
    # Tee everything to a log file for post-run forensics. Lost on /tmp wipe
    # but that's fine — useful during/after a single run.
    exec > >(tee -a "$BOOT_LOG_FILE") 2>&1

    log "Fabrik hub bootstrap starting"
    log "  target:           ${REMOTE}"
    log "  snapshot:         ${SNAPSHOT_ID}"
    log "  env from:         ${ENV_FROM}"
    log "  sysadmin env:     ${SYSADMIN_ENV_FROM}"
    log "  log file:         ${BOOT_LOG_FILE}"
    if [[ -n "$CF_REWRITE_TARGET" ]]; then
        log "  CF DNS rewrite:   *.vps1.ocoron.com → ${CF_REWRITE_TARGET}"
    fi
    if $DRY_RUN; then log "  DRY-RUN mode (no changes)"; fi
    if $VERIFY_ONLY; then log "  VERIFY mode (read-only)"; fi
    if $SKIP_SERVICES; then log "  --skip-services: stop after step_12"; fi
    if $SKIP_MESH; then log "  --skip-mesh: skip step_08 wg-quick@wg0 bring-up"; fi
    echo

    preflight || { err "preflight failed; aborting"; exit 1; }
    echo

    if $VERIFY_ONLY; then
        ok "verify mode — preflight passed; not running step blocks."
        return 0
    fi

    step_00_create_sudo_user
    step_01_harden_ssh
    step_02_install_packages
    step_03_install_claude_code
    step_04_clone_dr_store_env
    step_05_write_docker_daemon_json
    step_06_restic_pull_host_state
    step_07_apply_ufw
    step_08_bring_up_mesh
    step_09_apply_iptables_boot_state
    step_10_create_fabrik_network
    step_11_restic_pull_opt
    step_12_restic_pull_docker_volumes
    step_13_compose_up_dep_order
    step_14_pg_dump_restore_fallback
    step_15_enable_custom_services
    step_16_install_root_crontab
    step_17_cf_rewrite_dns
    step_18_verify_end_state

    echo
    ok "✓ HUB READY ($(elapsed) elapsed) — verify Gatus dashboard at https://status.vps1.ocoron.com"
    ok "   log file: ${BOOT_LOG_FILE}"
}

main "$@"
