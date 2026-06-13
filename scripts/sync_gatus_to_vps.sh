#!/usr/bin/env bash
# Sync /opt/fabrik/configs/gatus/ → vps1's /opt/monitoring/configs/gatus/.
#
# Why this exists
# ---------------
# The Gatus container on vps1 (compose at /opt/gatus/compose.yaml) bind-mounts
# /opt/monitoring/configs/gatus/ as /config (ro). For the longest time, every
# *other* monitoring config (prometheus, alertmanager, loki, ...) lived in
# /opt/fabrik/configs/<service>/ source-controlled, but gatus's tree lived
# ONLY on vps1 disk. If vps1's disk died the files were in the Backrest
# snapshot but not in git — an audit asymmetry STRATEGIC_BACKLOG flagged for
# weeks. This script closes that gap from the push side.
#
# Three known sub-asymmetries it does NOT try to fix:
#  1. drivers/gatus.py::add_endpoint / add_aro_wake_endpoint write to vps1
#     LIVE, never to git. So a freshly added endpoint shows up in git only if
#     the operator manually `scp` + `git add`s after the driver call. The
#     drift-check (`--diff` flag below) catches this on the next sync.
#  2. drivers/prometheus.py has the same asymmetry — outside this script's
#     scope. Mentioned only so the gatus pattern can be replicated to
#     prometheus/alertmanager/loki later if the operator wants.
#  3. Real source of truth is a per-service spec writing its own gatus YAML
#     via the gatus driver — that's the ideal end state, beyond this script.
#
# Modes
# -----
#   --diff       Show drift between git and vps1; exit 1 if any. Read-only.
#   --push       Push git → vps1 (idempotent; only restarts gatus if any file
#                actually changed). Default.
#   --dry-run    Compose with --push to print what would change without
#                touching vps1.

set -euo pipefail

FABRIK_ROOT="${FABRIK_ROOT:-/opt/fabrik}"
LOCAL_DIR="${FABRIK_ROOT}/configs/gatus"
REMOTE_DIR="/opt/monitoring/configs/gatus"
SSH_HOST="${FABRIK_HUB_SSH_HOST:-vps}"

MODE="push"
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --diff) MODE="diff" ;;
        --push) MODE="push" ;;
        --dry-run) DRY_RUN=true ;;
        -h|--help)
            sed -n '/^# /,/^$/p' "$0" | head -50 | sed 's/^# \?//'
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

# Local file list (relative paths under configs/gatus/)
mapfile -t LOCAL_FILES < <(cd "${LOCAL_DIR}" && find . -type f -name '*.yaml' | sed 's|^\./||' | sort)

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
    # Files on vps1 not in git
    mapfile -t REMOTE_FILES < <(ssh "${SSH_HOST}" "sudo find '${REMOTE_DIR}' -type f -name '*.yaml' -printf '%P\n' 2>/dev/null | sort")
    for rel in "${REMOTE_FILES[@]}"; do
        if ! printf '%s\n' "${LOCAL_FILES[@]}" | grep -qxF "${rel}"; then
            echo "ORPHAN ${rel}  on vps1 but not in git"
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
    echo "[dry-run] no scp, no restart"
    exit 0
fi

# scp-to-/tmp-then-sudo-install pattern (matches the rest of the codebase;
# avoids remote-bash quote-nesting hazards).
tmpdir=$(ssh "${SSH_HOST}" 'mktemp -d -t fabrik-gatus-XXXX')
trap "ssh '${SSH_HOST}' \"rm -rf '${tmpdir}'\" 2>/dev/null || true" EXIT

for rel in "${changed[@]}"; do
    # Build the tmp subdir for nested files (apps/foo.yaml -> tmpdir/apps/foo.yaml)
    subdir=$(dirname "${rel}")
    ssh "${SSH_HOST}" "mkdir -p '${tmpdir}/${subdir}'"
    scp -q "${LOCAL_DIR}/${rel}" "${SSH_HOST}:${tmpdir}/${rel}"
    ssh "${SSH_HOST}" \
        "sudo mkdir -p '${REMOTE_DIR}/${subdir}' && \
         sudo install -m 644 -o root -g root '${tmpdir}/${rel}' '${REMOTE_DIR}/${rel}'"
done

# Restart gatus so it picks up the new endpoint set. The container name pattern
# `^gatus(-|$)` matches both the bare name (live since Coolify migration) and
# any legacy `-suffix` shape — same fix from PR1 c48f3c0.
ssh "${SSH_HOST}" "GATUS=\$(sudo docker ps --format '{{.Names}}' | grep -E '^gatus(-|\$)' | head -1); \
    [[ -n \"\${GATUS}\" ]] && sudo docker restart \"\${GATUS}\" || echo 'gatus container not running — skipped restart'"

echo "done — ${#changed[@]} file(s) pushed, gatus restarted"
