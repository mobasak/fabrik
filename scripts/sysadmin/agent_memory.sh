#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/cleanup-automation.md
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

# ⚠️ CRON PATH. cron runs with PATH=/usr/bin:/bin, and sysctl/swapoff/swapon live in /usr/sbin.
# What this actually fixes is the UNPRIVILEGED `sysctl -n` in cmd_status, which printed four EMPTY
# values under cron. It does NOT rescue the sudo calls: `sudo -l` shows a secure_path covering
# /usr/sbin, so those resolve either way — an earlier cut of this comment claimed otherwise and
# was corrected by a review seat that read `sudo -l` instead of assuming. Caught by executing the
# job under `env -i PATH=/usr/bin:/bin` rather than trusting an interactive shell, 2026-09-20.
PATH="/usr/sbin:/sbin:$PATH"

CONF="${AGENT_MEMORY_CONF:-/etc/sysctl.d/99-fabrik-agent-memory.conf}"
EXT=kilocode.kilo-code
# Test seams, production defaults. The privileged paths below are ungradeable otherwise, and they
# are exactly the ones that can damage the box.
SWAPS="${AGENT_MEMORY_SWAPS:-/proc/swaps}"
# ⚠️ `sysctl` needs its own seam: line 30 PREPENDS /usr/sbin to PATH, so a stub placed on PATH by a
# test can never win. Without this the drift check below is ungradeable, which is how it shipped
# with zero graders.
SYSCTL="${AGENT_MEMORY_SYSCTL:-sysctl}"
MEMINFO="${AGENT_MEMORY_MEMINFO:-/proc/meminfo}"

# The policy itself is kept HERE, and /etc is GENERATED from it, so there is exactly one source of
# truth: `install` writes /etc from this block and the daily `cron` job re-asserts it, which heals
# a hand-edit, a package-manager overwrite, or a file removed by someone tidying /etc/sysctl.d.
# ⚠️ NOT because a `wsl --export`/`--import` rebuild would lose it — an earlier cut of this comment
# claimed that and it is FALSE: cleanup-maintenance-backlog.md item A1 records that a full export
# tar "contains everything", and the only thing the rebuild resets is the default user. Corrected
# 2026-09-20 after a review seat checked the cited doc that the claim leaned on.
read -r -d '' POLICY <<'EOF' || true
# Managed by /opt/fabrik/scripts/sysadmin/agent_memory.sh — do not hand-edit; re-run `install`.
# Rationale and measurements: /opt/fabrik/docs/workstation/cleanup-automation.md (S G).
#
# swappiness 10: strongly prefer dropping page cache over swapping anon pages. NOT 0 — that makes
# the kernel OOM rather than swap under a genuine spike, and a 64 GB swap file exists to absorb
# those.
vm.swappiness = 10
# vfs_cache_pressure 200: reclaim the dentry/inode slab twice as eagerly. This box holds ~1.8M
# ext4_inode_cache SLAB OBJECTS (`awk '$1=="ext4_inode_cache"' /proc/slabinfo`, 1,838,339 on
# 2026-09-20 — NOT the same metric as /proc/sys/fs/inode-nr, which reads ~1.4M; naming it stops
# the next reader comparing against the wrong one) because it walks 46 repos and their worktrees
# constantly; making that metadata cheap to drop gives the kernel something to take that is NOT
# an agent.
vm.vfs_cache_pressure = 200
# min_free_kbytes 256 MB (was 44 MB, ~0.09% of a 48 GB VM): kswapd's floor.
vm.min_free_kbytes = 262144
# watermark_scale_factor 100: wake kswapd at 1% free (~480 MB) instead of 0.1% (~48 MB). Matters
# specifically for MANY-AGENT bursts: when 15 sessions allocate at once and background reclaim has
# not kept up, the allocating process enters DIRECT reclaim and stalls — felt as the whole box
# freezing for a moment rather than as a memory shortage.
vm.watermark_scale_factor = 100
EOF

# ⚠️ An ABSENT key must not print a confident 0.00 — that is indistinguishable from a true zero
# in the only human-readable output this cron job produces (the hub's denominator-honesty rule,
# applied to a status surface).
_gb() { if _is_num "${1:-}"; then awk -v v="$1" 'BEGIN{printf "%.2f", v/1048576}'; else printf '?'; fi; }
_meminfo() { awk -v k="$1" '$1==k":"{print $2}' "$MEMINFO"; }
# ⚠️ A set-but-EMPTY value is what `set -u` cannot catch, and it is how the ENOMEM guard below
# silently disabled itself: `[ "$used" -gt "" ]` makes `[` exit 2, `if` reads that as FALSE, and
# the else path is the swapoff. Validate numerically and fail CLOSED.
_is_num() { case "${1:-}" in "" | *[!0-9]*) return 1 ;; *) return 0 ;; esac; }

cmd_install() {
    # ⚠️ `tee` opens with O_TRUNC, so an ENOSPC write EMPTIES the policy file before failing — and
    # `sysctl -q -p` on an empty file returns 0 with no output, so neither step objects. The old
    # code then printed "installed" over a destroyed file that would silently revert the box to
    # swappiness 60 at the next boot. Write to a temp and move it into place atomically.
    if ! printf '%s\n' "$POLICY" | sudo tee "$CONF.tmp" >/dev/null; then
        echo "install FAILED: could not write $CONF.tmp" >&2
        sudo rm -f "$CONF.tmp"
        return 1
    fi
    if ! sudo mv "$CONF.tmp" "$CONF"; then
        echo "install FAILED: could not move $CONF.tmp into place" >&2
        sudo rm -f "$CONF.tmp"
        return 1
    fi
    if ! sudo sysctl -q -p "$CONF"; then
        echo "install FAILED: sysctl refused $CONF" >&2
        return 1
    fi
    echo "installed $CONF"
    cmd_status
}

cmd_status() {
    for k in vm.swappiness vm.vfs_cache_pressure vm.min_free_kbytes vm.watermark_scale_factor; do
        printf "  %-28s %s\n" "$k" "$("$SYSCTL" -n "$k" 2>/dev/null)"
    done
    local t f
    t=$(_meminfo SwapTotal); f=$(_meminfo SwapFree)
    # ⚠️ Guard BEFORE the subtraction: `$((t - f))` on two empty values yields a hard 0, and _gb
    # can no longer refuse it — printing the confident "0.00 GB in use" that this file's own
    # comment forbids, and that reads exactly like a swapless box.
    local u=""
    if _is_num "$t" && _is_num "$f"; then u=$((t - f)); fi
    printf "  %-28s %s GB in use of %s GB\n" "swap" "$(_gb "$u")" "$(_gb "$t")"
    printf "  %-28s %s GB\n" "anon (agents+apps)" "$(_gb "$(_meminfo AnonPages)")"
    printf "  %-28s %s GB\n" "page cache (reclaimable)" "$(_gb "$(_meminfo Cached)")"
    printf "  %-28s %s\n" "claude sessions live" "$(pgrep -x claude | wc -l)"
}

# Pull already-swapped agent pages back into RAM. The sysctl policy prevents FUTURE bad eviction;
# only a swapoff/swapon cycle undoes what is already out there.
cmd_reclaim() {
    local force=0
    case "${1:-}" in
        --force) force=1 ;;
        "") ;;
        # a typo'd flag silently read as non-force, so the operator saw "skipped" and could
        # reasonably conclude the guard was broken
        *) echo "unknown option '${1}' (did you mean --force?)" >&2; return 2 ;;
    esac
    local live; live=$(pgrep -x claude | wc -l)
    # GUARD: swapoff must fit every swapped page back into RAM at once and stalls the box for up
    # to a minute. This tree routinely runs 3+ concurrent agent sessions whose turns would freeze
    # mid-tool-call, so it refuses while any is alive.
    if [ "$live" -gt 0 ] && [ "$force" -eq 0 ]; then
        echo "skipped: $live claude session(s) live — a swapoff would stall every one of them"
        return 10
    fi
    local used avail total free
    total=$(_meminfo SwapTotal); free=$(_meminfo SwapFree); avail=$(_meminfo MemAvailable)
    if ! _is_num "$total" || ! _is_num "$free" || ! _is_num "$avail"; then
        echo "skipped: cannot read $MEMINFO (SwapTotal/SwapFree/MemAvailable) — refusing to act blind"
        return 10
    fi
    used=$(( total - free ))
    if [ "$used" -eq 0 ]; then echo "nothing swapped out"; return 0; fi
    # swapoff aborts with ENOMEM if the pages cannot fit, leaving swap partially off. Refuse up
    # front rather than churn the box for nothing.
    if [ "$used" -gt "$avail" ]; then
        echo "skipped: $(_gb "$used") GB swapped exceeds $(_gb "$avail") GB available — swapoff would fail"
        return 10
    fi
    # ⚠️ `swapoff -a` and `swapon -a` ARE NOT SYMMETRIC, and on this box the difference is the
    # whole ballgame. swapoff -a takes down every device in /proc/swaps; swapon -a activates only
    # devices marked swap in /etc/fstab — and this box's fstab has ZERO swap entries (swap is
    # /dev/sdc, brought up by WSL init, with no systemd .swap unit either). So `swapon -a` would
    # restore NOTHING and still exit 0: an rc check cannot catch it. Capture the devices FIRST and
    # restore each by name. Found by the authoritative review seat 2026-09-20; guarded by
    # tests/test_agent_memory.py::test_swap_is_restored_by_device_because_swapon_dash_a_reads_only_fstab
    local devs
    # ⚠️ The kernel ESCAPES the Filename column (seq_file_path with " \t\n\\"), so a swap file at
    # "/swap file" appears as "/swap\\040file" and `mapfile -t` does not interpret it — swapon would
    # be handed the literal token and fail ENOENT. Latent while swap is a partition; live the day a
    # swap file with a space is added.
    mapfile -t devs < <(awk 'NR>1 && $1!="" {gsub(/\\011/, "\t", $1); gsub(/\\012/, "\n", $1); gsub(/\\040/, " ", $1); gsub(/\\134/, "\\", $1); print $1}' "$SWAPS")
    if [ ! -r "$SWAPS" ]; then
        # distinguish "cannot read it" from "it is empty" — cmd_reclaim already does this for
        # $MEMINFO, and acting blind is what both refusals exist to prevent
        echo "skipped: cannot read $SWAPS — refusing to act blind"
        return 10
    fi
    if [ "${#devs[@]}" -eq 0 ]; then
        echo "skipped: $SWAPS lists no device to restore — refusing a swapoff I could not undo"
        return 10
    fi
    # ⚠️ Prove sudo is usable BEFORE the first privileged call. Without this, a cron-context sudo
    # failure ("a terminal is required to read the password") made swapoff fail, every device read
    # as still-active, and the run returned the benign rc 11 — so a job that could never work
    # stamped GREEN indefinitely.
    if ! sudo -n true 2>/dev/null; then
        echo "CRITICAL: sudo is not usable — the reclaim never ran" >&2
        return 1
    fi
    echo "reclaiming $(_gb "$used") GB from swap (may stall briefly)..."
    if sudo swapoff -a; then
        # ⚠️ swapon's rc is LOAD-BEARING. Unchecked, a failure here left the box running with NO
        # SWAP and ~15 GB of anon while this printed "reclaimed." and returned 0 — so
        # weekly_catchup.sh stamped the run and the `agent-memory-policy` liveness surface read
        # LIVE. The next spike OOM-kills something and nothing anywhere says why. Reproduced
        # 2026-09-20 with a stubbed sudo; guarded by
        # tests/test_agent_memory.py::test_a_failed_swapon_after_a_successful_swapoff_is_never_reported_as_success
        local failed=0 d
        for d in "${devs[@]}"; do
            sudo swapon "$d" || { echo "FAILED to re-enable $d" >&2; failed=1; }
        done
        # Verify against the KERNEL's own view, not the rc — the rc lied by construction above.
        local back
        back=$(awk 'NR>1 && $1!="" {n++} END{print n+0}' "$SWAPS" 2>/dev/null)
        _is_num "$back" || back=0   # an unreadable $SWAPS must not print "only /1" and a bash error
        if [ "$failed" -eq 0 ] && [ "$back" -eq "${#devs[@]}" ]; then
            echo "reclaimed. (${back}/${#devs[@]} swap device(s) restored)"
            return 0
        fi
        echo "CRITICAL: swapoff succeeded but only ${back}/${#devs[@]} swap device(s) came back —" >&2
        echo "CRITICAL: this box may be running WITHOUT SWAP. Restore by hand: sudo swapon $(printf '%q ' "${devs[@]}")" >&2
        echo "CRITICAL: then confirm with: swapon --show" >&2
        return 1
    fi
    # The SAFE failure: swapoff refused, so swap was never removed. Re-assert it anyway.
    # ⚠️ NOT necessarily "state unchanged": swapoff -a takes devices down one at a time and can
    # fail part-way (ENOMEM). But the common case is that NOTHING came down, and re-asserting a
    # device that is still active returns EBUSY — which an earlier cut reported as CRITICAL, gave
    # rc 1, withheld the stamp and sent the runner into an hourly retry on a perfectly healthy box.
    # So re-assert only what is genuinely ABSENT, and distinguish the two outcomes.
    echo "swapoff FAILED — checking whether anything came down" >&2
    # ⚠️ Compare against the SAME un-escaped list the capture produced, as a FIXED WHOLE-LINE
    # match. An earlier cut grepped the raw $SWAPS for the un-escaped name and interpolated it as
    # a BASIC REGEX, which broke in both directions: `/swap\040file` and any name containing a
    # regex metacharacter false-alarmed CRITICAL on an intact box, and `/swap.img` MATCHED the
    # surviving `/swapZimg` line — reporting "swap is intact" while a device stayed down, and
    # stamping the heartbeat green. -F kills the metacharacters, -x the partial match.
    local now_up still_down=0 restored=0
    now_up=$(awk 'NR>1 && $1!="" {gsub(/\\040/, " ", $1); print $1}' "$SWAPS" 2>/dev/null) || now_up=""
    for d in "${devs[@]}"; do
        printf '%s\n' "$now_up" | grep -qxF -- "$d" && continue   # still active: nothing to do
        if sudo swapon "$d" 2>/dev/null; then
            restored=$((restored + 1))
        else
            echo "CRITICAL: could not re-enable $d" >&2; still_down=1
        fi
    done
    if [ "$still_down" -eq 1 ]; then
        echo "CRITICAL: a swap device is down and would not come back: sudo swapon $(printf '%q ' "${devs[@]}")" >&2
        return 1
    fi
    if [ "$restored" -gt 0 ]; then
        # ⚠️ Say what actually happened. An earlier cut printed "nothing was taken down" on this
        # path too, which erased the only record of a genuine partial-swapoff near-miss — the very
        # event an operator would want to know about.
        echo "swap restored — $restored device(s) came down in a partial swapoff and were re-enabled" >&2
    else
        echo "swap is intact — nothing was taken down" >&2
    fi
    return 11   # benign: the swapoff refused and the box is unchanged
}

# Kilo Code runs on demand, not always (operator directive 2026-09-20). Its manifest declares
# "activationEvents": ["onStartupFinished", "onUri"], so it starts with EVERY window and there is
# no lazy trigger to configure — uninstall/install is the only lever the CLI can drive. Measured
# 2026-09-20: 8 processes, 2.29 GB, several of them sitting in swap.
# ⚠️ State changes take effect on the next window RELOAD, not instantly.
cmd_kilo() {
    case "${1:-status}" in
        off) command -v code >/dev/null 2>&1 || { echo "the 'code' CLI is not on PATH" >&2; return 1; }
             # no `pipefail` here, so `| tail` would mask the rc entirely — read PIPESTATUS
             code --uninstall-extension "$EXT" 2>&1 | tail -2
             [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "uninstall FAILED" >&2; return 1; }
             echo "Reload each VS Code window to free its processes." ;;
        on)  command -v code >/dev/null 2>&1 || { echo "the 'code' CLI is not on PATH" >&2; return 1; }
             code --install-extension "$EXT" 2>&1 | tail -2
             [ "${PIPESTATUS[0]}" -eq 0 ] || { echo "install FAILED" >&2; return 1; }
             echo "Reload the window you need it in." ;;
        *)   if ! command -v code >/dev/null 2>&1; then
                 # ⚠️ `code` lives only in the VS Code server's remote-cli dir, which is injected
                 # into the integrated terminal's PATH. Under cron or a plain ssh shell it is
                 # ABSENT, and `code --list-extensions 2>/dev/null | grep -qx` then reported
                 # "not installed" — a false negative on the exact question being asked, with the
                 # diagnostic deliberately suppressed.
                 echo "  kilo: UNKNOWN — the 'code' CLI is not on PATH (run this from a VS Code terminal)"
             elif code --list-extensions 2>/dev/null | grep -qx "$EXT"; then echo "  kilo: installed"
             else echo "  kilo: not installed"; fi
             ps -eo rss,args --no-headers | grep "[k]ilo" |
               awk '{s+=$1;n++} END {printf "  kilo: %d live process(es), %.2f GB\n", n+0, s/1048576}' ;;
    esac
}

# The DAILY cron entry point. Exit code is the CONTRACT, and it has two halves:
#   0  — success, or a benign SKIP (sessions live / the pages would not fit). weekly_catchup.sh
#        stamps, and the `agent-memory-policy` liveness surface stays LIVE. A skip is the EXPECTED
#        nightly outcome while the operator is working; treating it as failure would re-run the job
#        hourly and flip that surface DEAD every night.
#   1  — CRITICAL (above all: swapoff succeeded, swapon failed, so the box now has NO SWAP). The
#        stamp is deliberately withheld, because breaking the heartbeat is the only signal anyone
#        will ever see. `weekly_catchup.sh`'s OK_MAX=0 already yields exactly this.
# It re-asserts the policy first, so a hand-edit or a removed /etc file heals on the next run.
cmd_cron() {
    echo "agent-memory: $(date -Is)"
    if ! cmp -s <(printf '%s\n' "$POLICY") "$CONF" 2>/dev/null; then
        echo "  policy drifted or missing — reinstalling"
        # ⚠️ Call cmd_install rather than repeating its write. An earlier cut duplicated the
        # `tee "$CONF"` here and so did NOT inherit the atomic temp-then-move fix: an ENOSPC would
        # truncate the live policy file to empty (tee opens O_TRUNC), the `&&` would skip sysctl so
        # the RUNNING kernel values stayed correct, and the drift check below — which reads live
        # values, never the file — would see nothing wrong. The box would then revert to
        # swappiness 60 at the next boot with a fully green heartbeat in the meantime.
        cmd_install >/dev/null || { echo "  reinstall FAILED — see above" >&2; return 1; }
    fi
    # ⚠️ THE DAILY JOB DOES NOT RECLAIM. It asserts the policy and reports; it never touches swap.
    #
    # Decided after this change's own /fabrik-review found 41 defects in three rounds and EIGHT of
    # eight critical/high ones lived in the swap-mutation path — twice as a defect a FIX had just
    # introduced. That path is the only part of this script that changes system state, it runs
    # unattended at 03:11 with nobody watching, and its worst failure (a box left with no swap)
    # is invisible until the next allocation spike. Meanwhile it had never actually run: every
    # invocation refused because agent sessions were live, and ~/.claude/agent-memory.log was
    # still empty when the decision was made.
    #
    # What the operator asked for was "when agents stop, sudo swapoff -a && sudo swapon -a" — an
    # operator action. Automating it was mine, and it bought nothing: the reclaim cannot run while
    # the operator is working, which is exactly when the cron fires. The POLICY re-assert is the
    # half that delivers the RAM benefit, is idempotent, mutates nothing, and is graded.
    #
    # `reclaim` remains available and fully fixed — run it by hand when the box is idle. D-318.
    cmd_status
    # ⚠️ THE COBRA (D-253), and it is why this block exists. The cheapest way to satisfy this
    # heartbeat WITHOUT producing the outcome is exactly what an earlier cut did: print a date,
    # attempt four privileged operations, ignore every result, return 0. The stamp then measured
    # "the script was invoked", never "the policy is in effect" — and `sysctl -q -p` returns 0 even
    # on an EMPTY file, so the re-assert above cannot stand in for the check. Verify the live
    # values against the policy and unstamp on drift; the read is free, cmd_status just made it.
    local drift=0 k want got
    while IFS= read -r line; do
        line="${line#"${line%%[![:space:]]*}"}"   # an INDENTED vm.* line is still applied by
        case "$line" in vm.*) ;; *) continue ;; esac  # sysctl, so it must still be verified
        # ⚠️ Tolerate every VALID spelling. `${k%% }` strips ONE trailing space, so
        # `vm.swappiness  =  10` yielded the key "vm.swappiness " and `vm.swappiness=10` yielded
        # want="vm.swappiness=10" — a permanent false alarm, no stamp, hourly retry, from a
        # cosmetic edit to the heredoc.
        k=${line%%=*}; k="${k//[[:space:]]/}"
        want=${line#*=}
        want="${want#"${want%%[![:space:]]*}"}"; want="${want%"${want##*[![:space:]]}"}"
        got=$("$SYSCTL" -n "$k" 2>/dev/null || true)
        if [ "$got" != "$want" ]; then
            echo "agent-memory: POLICY NOT IN EFFECT — $k is '${got:-<unreadable>}', want '$want'" >&2
            drift=1
        fi
    done <<< "$POLICY"
    # ⚠️ Fail-CLOSED on every rc that is not explicitly benign. An earlier cut tested only
    # `-eq 1`, so rc 2 (unknown option) or a 127 from a missing binary stamped GREEN — in the very
    # block whose purpose is to stop the stamp meaning "the script was invoked".
    if [ "$drift" -eq 1 ]; then
        echo "agent-memory: NOT stamping — the policy is not in effect" >&2
        return 1
    fi
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
