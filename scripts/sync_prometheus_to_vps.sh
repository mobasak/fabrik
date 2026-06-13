#!/usr/bin/env bash
# Sync /opt/fabrik/configs/prometheus/ → vps1's /opt/monitoring/configs/prometheus/.
#
# Why this exists (companion to sync_gatus_to_vps.sh, 2026-06-13)
# ---------------------------------------------------------------
# The prometheus container on vps1 bind-mounts /opt/monitoring/configs/prometheus/
# as /etc/prometheus (ro). Until 2026-06-13, prometheus.yml had silently drifted
# between git and vps1 — drivers/prometheus.py::add_scrape_target writes live,
# never git. This script + the matching driver change (also 2026-06-13, write
# to both git AND vps1 atomically) closes the drift gap on both ends.
#
# Secrets
# -------
# prometheus.yml uses `credentials_file:` (NOT inline `credentials:`) for all
# Bearer tokens. Secret values live ONLY on vps1 under
# `/opt/monitoring/configs/prometheus/secrets/` (mode 0640 root:nogroup so the
# `nobody`-running container can read them). They are NEVER snapshotted to git.
# A `--verify-secrets` sub-mode confirms every `credentials_file:` referenced
# in the synced config has an actual file present on vps1.
#
# Modes
#   --diff             Show drift between git and vps1; exit 1 if any. RO.
#   --push             Push git → vps1 (idempotent). Reloads prometheus only
#                      if any tracked file actually changed.
#   --dry-run          Compose with --push to print without scp'ing.
#   --verify-secrets   Read prometheus.yml, list every credentials_file path,
#                      check each one exists + is readable inside the container.

set -euo pipefail

FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
LOCAL_DIR="${FABRIK_ROOT}/configs/prometheus"
REMOTE_DIR="/opt/monitoring/configs/prometheus"
SSH_HOST="${FABRIK_HUB_SSH_HOST:-vps}"

MODE="push"
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --diff) MODE="diff" ;;
        --push) MODE="push" ;;
        --dry-run) DRY_RUN=true ;;
        --verify-secrets) MODE="verify-secrets" ;;
        -h|--help)
            sed -n '/^# /,/^$/p' "$0" | head -45 | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "unknown flag: $1" >&2; exit 2 ;;
    esac
    shift
done

if [[ ! -d "${LOCAL_DIR}" ]]; then
    echo "ERR: ${LOCAL_DIR} not found — wrong FABRIK_ROOT?" >&2
    exit 1
fi

# Files we track. Backups (`*.bak-*`) are intentionally NOT tracked — they're
# operator-side artifacts on vps1 that don't belong in git.
mapfile -t LOCAL_FILES < <(cd "${LOCAL_DIR}" && find . -type f -name '*.yml' -o -name '*.yaml' | sed 's|^\./||' | grep -vE '\.bak-' | sort)

# --- verify-secrets mode -----------------------------------------------------
if [[ "${MODE}" == "verify-secrets" ]]; then
    fail=0
    # Extract every credentials_file path from local prometheus.yml
    mapfile -t SECRET_PATHS < <(grep -E '^\s*credentials_file:' "${LOCAL_DIR}/prometheus.yml" | awk '{print $2}')
    if (( ${#SECRET_PATHS[@]} == 0 )); then
        echo "no credentials_file: paths declared — nothing to verify"
        exit 0
    fi
    for in_container_path in "${SECRET_PATHS[@]}"; do
        # Translate /etc/prometheus/... → /opt/monitoring/configs/prometheus/...
        on_host_path="${in_container_path//\/etc\/prometheus/${REMOTE_DIR}}"
        readable_inside=$(ssh "${SSH_HOST}" "sudo docker exec prometheus test -r '${in_container_path}' && echo READABLE || echo MISSING" 2>&1)
        exists_on_host=$(ssh "${SSH_HOST}" "sudo test -f '${on_host_path}' && echo EXISTS || echo MISSING" 2>&1)
        echo "  ${in_container_path}"
        echo "    host:      ${exists_on_host} (${on_host_path})"
        echo "    container: ${readable_inside}"
        [[ "${readable_inside}" == "READABLE" ]] || fail=1
    done
    if (( fail == 0 )); then
        echo "all secrets present + readable"
    fi
    exit "${fail}"
fi

# --- diff mode ---------------------------------------------------------------
if [[ "${MODE}" == "diff" ]]; then
    drift=0
    for rel in "${LOCAL_FILES[@]}"; do
        local_md5=$(md5sum "${LOCAL_DIR}/${rel}" | awk '{print $1}')
        remote_md5=$(ssh "${SSH_HOST}" "sudo md5sum '${REMOTE_DIR}/${rel}' 2>/dev/null | awk '{print \$1}'" || echo "MISSING")
        if [[ "${local_md5}" != "${remote_md5}" ]]; then
            echo "DRIFT  ${rel}  local=${local_md5}  vps1=${remote_md5}"
            drift=1
        fi
    done
    if (( drift == 0 )); then
        echo "in sync (${#LOCAL_FILES[@]} files)"
    fi
    exit "${drift}"
fi

# --- push mode ---------------------------------------------------------------
changed=()
for rel in "${LOCAL_FILES[@]}"; do
    local_md5=$(md5sum "${LOCAL_DIR}/${rel}" | awk '{print $1}')
    remote_md5=$(ssh "${SSH_HOST}" "sudo md5sum '${REMOTE_DIR}/${rel}' 2>/dev/null | awk '{print \$1}'" || echo "MISSING")
    if [[ "${local_md5}" != "${remote_md5}" ]]; then
        changed+=("${rel}")
    fi
done

if (( ${#changed[@]} == 0 )); then
    echo "no changes (${#LOCAL_FILES[@]} files in sync)"
    exit 0
fi

echo "pushing ${#changed[@]} changed file(s):"
for rel in "${changed[@]}"; do echo "  ${rel}"; done

if $DRY_RUN; then
    echo "[dry-run] no scp, no reload"
    exit 0
fi

tmpdir=$(ssh "${SSH_HOST}" 'mktemp -d -t fabrik-prom-XXXX')
trap "ssh '${SSH_HOST}' \"rm -rf '${tmpdir}'\" 2>/dev/null || true" EXIT

for rel in "${changed[@]}"; do
    subdir=$(dirname "${rel}")
    ssh "${SSH_HOST}" "mkdir -p '${tmpdir}/${subdir}'"
    scp -q "${LOCAL_DIR}/${rel}" "${SSH_HOST}:${tmpdir}/${rel}"
    ssh "${SSH_HOST}" \
        "sudo mkdir -p '${REMOTE_DIR}/${subdir}' && \
         sudo install -m 644 -o root -g root '${tmpdir}/${rel}' '${REMOTE_DIR}/${rel}'"
done

# Reload via POST /-/reload. The driver's `_reload_prometheus()` does this too
# (with a container-restart fallback); we mirror the happy-path call here.
# Run from inside alertmanager since it shares the monitoring net + has wget.
# Container name pattern `^alertmanager(-|$)` matches both bare-name (post-
# Coolify) and any legacy `-suffix` shape — same fix as PR1 c48f3c0.
echo "reloading prometheus..."
reload_rc=$(ssh "${SSH_HOST}" "AM=\$(sudo docker ps --format '{{.Names}}' | grep -E '^alertmanager(-|\$)' | head -1); \
    [[ -n \"\${AM}\" ]] && sudo docker exec \"\${AM}\" wget -qO- --post-data='' http://prometheus:9090/-/reload >/dev/null 2>&1 && echo OK || echo FAIL")
if [[ "${reload_rc}" == "OK" ]]; then
    echo "done — ${#changed[@]} file(s) pushed, prometheus reloaded"
else
    echo "WARN: prometheus reload returned non-zero — config is on disk + will load on next restart, but in-memory still on previous config"
    exit 1
fi
