#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/cleanup-automation.md | none
#
# Agent-workstation MEMORY policy — the RAM counterpart to cache-prune.sh's disk cleanup.
#
# WHY THIS EXISTS. Every cleaner on this box was disk-only (cleanup-automation.md § A-F:
# caches, logs, spools, scratch, worktrees). Nothing governed RAM, and measured 2026-09-20 the
# kernel was making exactly the wrong trade: vm.swappiness at its default 60 had pushed 13.9 GB
# out to swap, and the processes sitting in swap were MCP servers, VS Code extension hosts and
# the Kilo extension — the dev infra — while 28 GB of freely-droppable page cache stayed
# resident. The box was never short of memory (15.5 GB anon against a 48 GB cap); it was losing
# an argument with the page-cache heuristic.
#
# The operator's goal is the opposite of a general-purpose server's: reserve the maximum for
# Claude sessions, their MCP servers and their subagents, and let the CACHE be what gets
# reclaimed. These four knobs encode that, and nothing else on this box sets them (verified:
# cache-prune.sh has zero sysctl lines, and scripts/audit/04-performance.sh only READS
# swappiness and runs on the VPS over SSH, not here).
#
# SCOPE: this local WSL2 box only. Not the VPS fleet, not fleet-synced (scripts/sysadmin/ is
# absent from fabrik_synced_manifest.py).
set -u

# ⚠️ CRON PATH. cron runs with PATH=/usr/bin:/bin, and every privileged tool this script needs —
# sysctl, swapoff, swapon — lives in /usr/sbin. Without this the status block printed four EMPTY
# values and `reclaim` would have died with "command not found" on the one night the box was
# actually idle enough to run it. Caught by executing the job under `env -i PATH=/usr/bin:/bin`
# rather than trusting an interactive shell, 2026-09-20.
PATH="/usr/sbin:/sbin:$PATH"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONF=/etc/sysctl.d/99-fabrik-agent-memory.conf
EXT=kilocode.kilo-code

# The policy itself. Kept HERE rather than only in /etc so a WSL export/import rebuild — which
# cleanup-automation.md § C names as the only real disk-shrink lever — does not silently lose it:
# `install` rewrites /etc from this, and the daily `cron` job re-asserts it.
read -r -d '' POLICY <<'EOF' || true
# Managed by /opt/fabrik/scripts/sysadmin/agent_memory.sh — do not hand-edit; re-run `install`.
# Rationale and measurements: /opt/fabrik/docs/workstation/cleanup-automation.md (S G).
#
# swappiness 10: strongly prefer dropping page cache over swapping anon pages. NOT 0 — that makes
# the kernel OOM rather than swap under a genuine spike, and a 64 GB swap file exists to absorb
# those.
vm.swappiness = 10
# vfs_cache_pressure 200: reclaim the dentry/inode slab twice as eagerly. This box caches ~1.8M
# ext4 inodes because it walks 46 repos and their worktrees constantly; making that metadata
# cheap to drop gives the kernel something to take that is NOT an agent.
vm.vfs_cache_pressure = 200
# min_free_kbytes 256 MB (was 44 MB, ~0.09% of a 48 GB VM): kswapd's floor.
vm.min_free_kbytes = 262144
# watermark_scale_factor 100: wake kswapd at 1% free (~480 MB) instead of 0.1% (~48 MB). Matters
# specifically for MANY-AGENT bursts: when 15 sessions allocate at once and background reclaim has
# not kept up, the allocating process enters DIRECT reclaim and stalls — felt as the whole box
# freezing for a moment rather than as a memory shortage.
vm.watermark_scale_factor = 100
EOF

_gb() { awk -v v="$1" 'BEGIN{printf "%.2f", v/1048576}'; }
_meminfo() { awk -v k="$1" '$1==k":"{print $2}' /proc/meminfo; }

cmd_install() {
    printf '%s\n' "$POLICY" | sudo tee "$CONF" >/dev/null
    sudo sysctl -q -p "$CONF"
    echo "installed $CONF"
    cmd_status
}

cmd_status() {
    for k in vm.swappiness vm.vfs_cache_pressure vm.min_free_kbytes vm.watermark_scale_factor; do
        printf "  %-28s %s\n" "$k" "$(sysctl -n "$k" 2>/dev/null)"
    done
    local t f
    t=$(_meminfo SwapTotal); f=$(_meminfo SwapFree)
    printf "  %-28s %s GB in use of %s GB\n" "swap" "$(_gb $((t - f)))" "$(_gb "$t")"
    printf "  %-28s %s GB\n" "anon (agents+apps)" "$(_gb "$(_meminfo AnonPages)")"
    printf "  %-28s %s GB\n" "page cache (reclaimable)" "$(_gb "$(_meminfo Cached)")"
    printf "  %-28s %s\n" "claude sessions live" "$(pgrep -x claude | wc -l)"
}

# Pull already-swapped agent pages back into RAM. The sysctl policy prevents FUTURE bad eviction;
# only a swapoff/swapon cycle undoes what is already out there.
cmd_reclaim() {
    local force=0
    [ "${1:-}" = "--force" ] && force=1
    local live; live=$(pgrep -x claude | wc -l)
    # GUARD: swapoff must fit every swapped page back into RAM at once and stalls the box for up
    # to a minute. This tree routinely runs 3+ concurrent agent sessions whose turns would freeze
    # mid-tool-call, so it refuses while any is alive.
    if [ "$live" -gt 0 ] && [ "$force" -eq 0 ]; then
        echo "skipped: $live claude session(s) live — a swapoff would stall every one of them"
        return 10
    fi
    local used avail
    used=$(( $(_meminfo SwapTotal) - $(_meminfo SwapFree) ))
    avail=$(_meminfo MemAvailable)
    if [ "$used" -eq 0 ]; then echo "nothing swapped out"; return 0; fi
    # swapoff aborts with ENOMEM if the pages cannot fit, leaving swap partially off. Refuse up
    # front rather than churn the box for nothing.
    if [ "$used" -gt "$avail" ]; then
        echo "skipped: $(_gb "$used") GB swapped exceeds $(_gb "$avail") GB available — swapoff would fail"
        return 10
    fi
    echo "reclaiming $(_gb "$used") GB from swap (may stall briefly)..."
    if sudo swapoff -a; then sudo swapon -a; echo "reclaimed."; return 0; fi
    echo "swapoff FAILED — re-enabling swap, state unchanged" >&2
    sudo swapon -a
    return 1
}

# Kilo Code runs on demand, not always (operator directive 2026-09-20). Its manifest declares
# "activationEvents": ["onStartupFinished", "onUri"], so it starts with EVERY window and there is
# no lazy trigger to configure — uninstall/install is the only lever the CLI can drive. Measured
# 2026-09-20: 8 processes, 2.29 GB, several of them sitting in swap.
# ⚠️ State changes take effect on the next window RELOAD, not instantly.
cmd_kilo() {
    case "${1:-status}" in
        off) code --uninstall-extension "$EXT" 2>&1 | tail -2
             echo "Reload each VS Code window to free its processes." ;;
        on)  code --install-extension "$EXT" 2>&1 | tail -2
             echo "Reload the window you need it in." ;;
        *)   if code --list-extensions 2>/dev/null | grep -qx "$EXT"; then echo "  kilo: installed"; else echo "  kilo: not installed"; fi
             ps -eo rss,args --no-headers | grep "[k]ilo" |
               awk '{s+=$1;n++} END {printf "  kilo: %d live process(es), %.2f GB\n", n+0, s/1048576}' ;;
    esac
}

# The DAILY cron entry point. Always exits 0 so weekly_catchup.sh stamps it and the liveness
# heartbeat stays meaningful — a refused reclaim (agents live) is the EXPECTED nightly outcome,
# not a failure. Re-asserts the policy first, which is what makes a WSL rebuild self-heal.
cmd_cron() {
    echo "agent-memory: $(date -Is)"
    if ! cmp -s <(printf '%s\n' "$POLICY") "$CONF" 2>/dev/null; then
        echo "  policy drifted or missing — reinstalling"
        printf '%s\n' "$POLICY" | sudo tee "$CONF" >/dev/null && sudo sysctl -q -p "$CONF"
    fi
    cmd_reclaim || true
    cmd_status
    return 0
}

case "${1:-status}" in
    install) cmd_install ;;
    status)  cmd_status; cmd_kilo status ;;
    reclaim) shift; cmd_reclaim "$@" ;;
    kilo)    shift; cmd_kilo "$@" ;;
    cron)    cmd_cron ;;
    *) echo "usage: agent_memory.sh [install|status|reclaim [--force]|kilo on|off|status|cron]"; exit 2 ;;
esac
