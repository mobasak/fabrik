#!/usr/bin/env bash
# AFTER-EDIT: docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md | docs/STRATEGIC_BACKLOG.md
# vps_apply_limits.sh — assert Docker MEMORY ceilings on vps1 containers that did
# not arrive through `fabrik apply`, and report every container that has none.
#
# WHY THIS EXISTS
#   `deploy.resources.limits.memory` is a Fabrik invariant enforced by
#   deployer_ssh._validate_compose() and auto-emitted by the scaffolder — but only
#   for containers that pass through `fabrik apply`. The hand-composed monitoring
#   and ingress stack never does, so it is unguarded. Measured 2026-09-04:
#   10 of 32 containers on vps1 ran with HostConfig.Memory == 0.
#
# THE CEILINGS ARE NOT FREEHAND. Every value below is derived and reviewed in
#   docs/superpowers/specs/2026-09-04-vps1-container-memory-limits-design.md
#   (CONVERGED, 7 review rounds). Change a number THERE first, then here.
#
# SAFETY RULES, each learned from a defect in the version this replaces
#   (last touched 2026-05-30, never run since; every hazard below was live in it):
#   * NEVER LOWERS. A target at or below the live ceiling is a no-op, not a call.
#     The old script would have cut prometheus from 1.5GiB to 1g.
#   * DRY RUN BY DEFAULT. Mutating requires an explicit --apply.
#   * MEMORY ONLY. The old script passed --cpus for loki/glitchtip, which are
#     live-unlimited today — proof those calls never landed. CPU ceilings are a
#     separate, out-of-scope decision (STRATEGIC_BACKLOG, 2026-09-04 row).
#   * NO NETWORK MUTATION. The old script disconnected/reconnected containers on
#     the `coolify` network, renamed to `fabrik` on 2026-05-31; the three UUID
#     container prefixes it targeted no longer exist and all three services now
#     carry stable names. Dead code that mutates networking is not defense.
#   * IDEMPOTENT under an intermittent link (spec C5): it reads each live limit
#     and issues a call only where one is actually needed, so a dropped SSH
#     connection costs a re-run, never a partial or doubled application.
#
# USAGE (runs ON the VPS; pipe it in — it depends on nothing from the hub)
#   ssh vps 'bash -s'            < scripts/vps_apply_limits.sh   # dry run (default)
#   ssh vps 'bash -s -- --apply' < scripts/vps_apply_limits.sh   # mutate
#   ssh vps 'bash -s -- --check' < scripts/vps_apply_limits.sh   # exit 1 if any
#                                                                # container is unbounded

set -uo pipefail

MODE=report
case "${1:-}" in
  --apply) MODE=apply ;;
  --check) MODE=check ;;
  --dry-run|"") MODE=report ;;
  *) echo "unknown argument: $1" >&2; exit 64 ;;
esac

D="sudo docker"

# ── The ceiling table ──────────────────────────────────────────────────────────
# container            MiB    measured 2026-09-04 (docker stats, steady state)
CEILINGS="
cadvisor              512    # 244.7 MiB — largest of the ten
loki                  512    # 131.6 MiB — page-cache heavy, ingest bursts
promtail              256    # 134.4 MiB — page-cache heavy (tails logs)
grafana               256    # 86.6 MiB  — dashboard rendering spikes
traefik               256    # 52.8 MiB  — ingress; generous, failing it fails all
alertmanager          128    # 33.1 MiB  — small, stable
postgres-exporter      64    # 17.6 MiB  — scrape-only
node-exporter          64    # 16.3 MiB  — scrape-only
redis-exporter         64    # 13.8 MiB  — scrape-only
redis-main            640    # 5.2 MiB   — it FORKS; see below
"
# redis-main is the one a careless ceiling would kill. It self-caps at
# maxmemory 256M/allkeys-lru, but has appendonly yes AND save points, so BGSAVE
# and AOF rewrite fork. The kernel enforces RSS while Redis tracks logical
# used_memory: a fork over a full 256M dataset can approach twice that resident
# under worst-case copy-on-write. 640 = 256 data + 256 COW + 128 fragmentation.
# A ceiling at maxmemory+128 would turn graceful LRU eviction into a hard kill.

managed=""
applied=0; raised=0; ok=0; missing=0; failed=0

echo "=== vps memory ceilings — mode: $MODE ==="

while read -r name mib _rest; do
  [ -z "${name:-}" ] && continue
  managed="$managed $name"
  target=$(( mib * 1024 * 1024 ))

  if ! $D inspect "$name" >/dev/null 2>&1; then
    printf '  MISSING   %-20s (no such container)\n' "$name"
    missing=$(( missing + 1 )); continue
  fi

  live=$($D inspect -f '{{.HostConfig.Memory}}' "$name")

  # FAIL CLOSED on an unreadable limit. `[ "" -ge N ]` does not return false — it ERRORS
  # (exit 2, "integer expression expected"), so both guard tests below fail, `verb` stays SET,
  # and the script would issue an update at the table's target. If that target were BELOW the
  # container's real ceiling, the never-lower rule — the entire safety argument — would have
  # LOWERED it. The read can fail for real: the container can be removed between the existence
  # check one line above and this call, and this link has measured intermittency (spec C5).
  # Docker itself offers no never-lower guarantee (it refuses only a decrease below CURRENT
  # USAGE, which is far weaker), so this comparison is the ONLY thing standing between the
  # table and a live ceiling. It does not get to be skipped by an error.
  case "$live" in
    ''|*[!0-9]*)
      printf '  UNREADABLE %-19s limit read returned %s — SKIPPED (refusing to act blind)\n' \
        "$name" "${live:-<empty>}"
      failed=$(( failed + 1 )); continue ;;
  esac

  if [ "$live" -ge "$target" ] && [ "$live" -ne 0 ]; then
    printf '  OK        %-20s %s MiB already ≥ target %s MiB — no call\n' \
      "$name" "$(( live / 1024 / 1024 ))" "$mib"
    ok=$(( ok + 1 )); continue
  fi

  verb=SET; [ "$live" -ne 0 ] && verb=RAISE
  if [ "$MODE" != apply ]; then
    printf '  would %-5s %-20s %s MiB → %s MiB\n' "$verb" "$name" \
      "$(( live / 1024 / 1024 ))" "$mib"
    continue
  fi

  # --memory-swap equal to --memory: left unset, the total memory+swap allowance
  # silently becomes TWICE the ceiling.
  # Capture stderr instead of discarding it: the failure line below used to ASSERT the cause
  # ("a decrease below current usage is refused") without ever reading Docker's own message.
  # A plausible invented mechanism is the harder defect to catch, because it reads as diagnosis.
  err=$($D update --memory "${mib}m" --memory-swap "${mib}m" "$name" 2>&1 >/dev/null); rc=$?
  # Branch on the EXIT CODE, never on "did it write to stderr". Docker warns and succeeds all the
  # time — "WARNING: Your kernel does not support swap limit capabilities" is the common one, and
  # `--memory-swap` is exactly what provokes it. Reading a non-empty stderr as failure would turn
  # every successful apply on such a kernel into a red run. (Found reviewing the fix that added
  # this capture: the fix for an invented diagnosis shipped its own mirror.)
  if [ "$rc" -eq 0 ]; then
    [ -n "$err" ] && printf '  note      %-20s %s\n' "$name" "$err"
    now=$($D inspect -f '{{.HostConfig.Memory}}' "$name")
    if [ "$now" -eq "$target" ]; then
      printf '  %-9s %-20s %s MiB → %s MiB  ✅\n' "$verb" "$name" \
        "$(( live / 1024 / 1024 ))" "$mib"
      [ "$verb" = SET ] && applied=$(( applied + 1 )) || raised=$(( raised + 1 ))
    else
      printf '  MISMATCH  %-20s command exited 0 but limit is %s, not %s ❌\n' \
        "$name" "$now" "$target"
      failed=$(( failed + 1 ))
    fi
  else
    printf '  FAILED    %-9s %-20s ❌ %s\n' "$verb" "$name" "$err"
    failed=$(( failed + 1 ))
  fi
done <<< "$(echo "$CEILINGS" | sed 's/#.*//' | grep -v '^[[:space:]]*$')"

# ── Every DEFINED container with no ceiling — `-a`, not just running ───────────
# A stopped-but-defined container keeps HostConfig.Memory across a restart, so a
# check reading only the running set reports green while an unbounded container
# waits to start. Today both counts are 32, which is exactly why the narrower
# query would have been easy to write and never notice.
echo
echo "--- unbounded containers (HostConfig.Memory == 0, all defined) ---"
unbounded=0
for id in $($D ps -aq); do
  [ "$($D inspect -f '{{.HostConfig.Memory}}' "$id")" = "0" ] || continue
  n=$($D inspect -f '{{.Name}}' "$id"); n="${n#/}"
  case " $managed " in
    *" $n "*) tag="MANAGED-BUT-STILL-ZERO" ;;
    *)        tag="UNMANAGED (arrived off the apply path)" ;;
  esac
  printf '  ⚠️  %-24s %s\n' "$n" "$tag"
  unbounded=$(( unbounded + 1 ))
done
[ "$unbounded" -eq 0 ] && echo "  none — every defined container has a memory ceiling"

total=$($D ps -aq | wc -l)
echo
echo "=== $unbounded of $total containers unbounded · set=$applied raised=$raised ok=$ok missing=$missing failed=$failed ==="

[ "$failed" -gt 0 ] && exit 1
[ "$MODE" = check ] && [ "$unbounded" -gt 0 ] && exit 1
exit 0
