#!/usr/bin/env bash
# claude-selfwatch.sh <session_id> — resume-mesh Layer 2b (interactive pane self-watch).
# Armed BY THE AGENT via the ORIENT order in every session: Monitor(persistent: true, command: "bash ~/.claude/bin/claude-selfwatch.sh <sid>", description: "resume-mesh self-watch").
# Zero API cost while silent. Consumes TWO files: `.errparked` (a death, below) and `.holdlifted` (the relief wake — the LIFT branch; plan 2026-09-07-plan-1-relief-wake, D-178).
# A marker already present at ARM time is history — the arming session is alive by
# construction (an agent inside a running turn armed us), so it is consumed WITHOUT
# firing. Then, as a STANDING watch (2026-09-03 — the one-wake-then-exit shape left every
# second death un-woken whenever the agent had not re-armed yet: in one day's 429/529 storm
# 17 of the 18 /opt sessions that died carried a typed "proceed"): wait for a NEW death marker → per-class remedy
# wait, re-asking the quota helper every slice for rate_limit (a manual account switch
# ends the wait within one slice instead of sleeping to the DEAD account's reset clock)
# → connectivity gate (every class: waking into a dead network just dies again) → storm
# jitter → CONSUME the marker → print ONE wake line → keep watching. One wake per death
# record, any number of records per arm. ONE watch per session: a second arm for the
# same sid exits at once under the per-sid flock, so a re-arm can never double-fire.
set -u
sid="${1:?session id}"
locks="${CLAUDE_SOUND_LOCKDIR:-/tmp/claude-sound-locks-$(id -u)}"
safe=$(printf '%s' "$sid" | tr -c 'A-Za-z0-9_-' '_' | head -c 64)
marker="$locks/$safe.errparked"
lift="$locks/$safe.holdlifted"  # the RELIEF WAKE (plan 2026-09-07-plan-1-relief-wake, D-178): the
# rotation tick writes the lift epoch here when the fleet-quota hold lifts — a file of its OWN,
# never the death record: the decider clears `.errparked` on every normal Stop, which is the
# graceful-stop turn a held session is inside, so a lift written there vanished before this
# watch could consume it
mkdir -p "$locks" 2>/dev/null || true

# Duplicate-arm guard: the lock lives for this process's lifetime (fd 9). A second watch
# for the same sid would race the first for the marker; it exits with one line instead.
if ! exec 9>"$locks/$safe.selfwatch.lock"; then
  printf 'self-watch NOT armed: cannot open %s/%s.selfwatch.lock — fix the lock dir and re-arm\n' "$locks" "$safe"
  exit 1
fi
if ! flock -n 9; then
  printf 'self-watch already armed for %s — this duplicate exits; the standing watch stays\n' "$safe"
  exit 0
fi

rm -f "$marker" "$lift" 2>/dev/null || true  # pre-arm history: never fire into the live arming session

qcmd="${MESH_QUOTA_CMD:-$HOME/.claude/bin/claude-quota.py}"
while :; do
  while [ ! -f "$marker" ] && [ ! -f "$lift" ]; do sleep "${MESH_POLL:-10}"; [ "$locks/$safe.selfwatch.lock" -ef /proc/$$/fd/9 ] || { printf 'self-watch for %s: its lock file vanished (the Stop decider prunes lock-dir files older than 2h by mtime — fixed 2026-09-07 — or a manual rm); this watch EXITS so the tick and the arm nag see the truth — re-arm it\n' "$safe"; exit 0; }; done  # orphan guard (heavy review R1)
  if [ ! -f "$marker" ] && [ -f "$lift" ]; then
    # The LIFT branch: no backoff (nothing to heal), no jitter (one fleet-wide event for a
    # handful of panes, not a storm); the same connectivity gate as a death — `death` is the
    # gate's ceiling clock (`set -u`: it must be set here), the LIFT epoch stays in `lift_at`
    # so the line names when the hold went, not when the wake landed. On the ceiling the file
    # stays and the cycle restarts (W9's shape); a death marker arriving meanwhile wins the
    # next poll and the lift follows it on the iteration after.
    lift_at=$(awk '{print $1; exit}' "$lift" 2>/dev/null || true)
    case "$lift_at" in ''|*[!0123456789]*) lift_at=$(date +%s) ;; esac
    # field 2 names the hold (W-83a8ee68): `battery` for the battery hold's lift; a quota lift
    # writes one field, and anything else reads as the quota's
    lift_kind=$(awk '{print $2; exit}' "$lift" 2>/dev/null || true)
    case "$lift_kind" in
      battery) lift_what='the battery hold LIFTED at %s (mains power is back)' ;;
      *) lift_what='the fleet-quota hold LIFTED at %s (the rotation tick saw relief)' ;;
    esac
    death=$(date +%s)
    ceiling_hit=0
    until curl -s -o /dev/null --max-time 5 https://api.anthropic.com; do
      [ $(( $(date +%s) - death )) -ge "${MESH_CEILING:-1800}" ] && { ceiling_hit=1; break; }
      sleep "${MESH_POLL:-10}"
    done
    [ "$ceiling_hit" = "1" ] && continue
    [ -f "$lift" ] || continue  # consumed or cleaned meanwhile (a fresh arm) — keep watching
    rm -f "$lift" 2>/dev/null || true  # consume: one wake per lift
    # shellcheck disable=SC2059 — lift_what is one of the two fixed formats chosen above
    printf "RESUME: $lift_what" "$(date -d @"$lift_at" +%H:%M)"
    printf '. If you stopped for it, resume the run you closed BLOCKED — its record (`python3 scripts/command_run.py line`) and `python3 scripts/thread_anchor.py line --session %s` carry where you left off; if you are mid-task, ignore this line — this self-watch STAYS ARMED (do NOT re-arm; a duplicate arm exits at once)\n' "$sid"
    continue
  fi
  err=$(awk '{print $1; exit}' "$marker" 2>/dev/null || echo unknown)
  death=$(awk '{print $2; exit}' "$marker" 2>/dev/null || true)
  case "$death" in ''|*[!0123456789]*) death=$(date +%s) ;; esac

  case "$err" in  # human-only classes: nothing heals an account/config wall (the
    # reviver excludes them too) — "the cause has been healed" would be a false
    # claim. The death already rang in its error voice + Telegramed; consume the
    # record silently and keep watching.
    authentication_failed|invalid_grant|oauth_org_not_allowed|billing_error|model_not_found)
      rm -f "$marker" 2>/dev/null || true
      continue ;;
  esac

  case "$err" in  # per-class remedy wait (rotation for account classes, cool-off for load)
    rate_limit) bo=90 ;; overloaded) bo=60 ;; server_error) bo=30 ;; *) bo=0 ;;
  esac
  # QUOTA-HEALTH (plan 2026-08-10-plan-1): a rate_limit death is usually a WALL with a
  # known reset — ask the one helper for the bounded wait instead of the blind 90s.
  if [ "$err" = "rate_limit" ] && [ -f "$qcmd" ]; then
    qw=$(timeout 10 python3 "$qcmd" --wait-seconds rate_limit 2>/dev/null || echo "$bo")
    case "$qw" in ''|*[!0123456789]*) qw=$bo ;; esac
    bo=$qw
  fi
  # SLICED wait (<=60s slices): a multi-hour quota wait must still notice a mid-wait
  # heal — the decider clears the marker when a live waker exists — so re-check every
  # slice and go back to watching instead of firing into a revived session.
  MESH_SLICE_MAX="${MESH_SLICE_MAX:-60}"
  case "$MESH_SLICE_MAX" in ''|*[!0123456789]*|0) MESH_SLICE_MAX=60 ;; esac
  remaining="${MESH_BACKOFF_OVERRIDE:-$bo}"
  case "$remaining" in ''|*[!0123456789]*) remaining=$bo ;; esac  # garbage override → the class default
  case "$remaining" in ''|*[!0123456789]*) remaining=0 ;; esac
  healed=0
  while [ "$remaining" -gt 0 ]; do
    [ -f "$marker" ] || { healed=1; break; }   # heal check FIRST — never eat a slice
    touch -c "$marker" 2>/dev/null || true     # a > 2 h quota wait keeps its record from the 2-h prune (W-5279e834)
    slice=$(( remaining > MESH_SLICE_MAX ? MESH_SLICE_MAX : remaining ))
    sleep "$slice"
    remaining=$(( remaining - slice ))
    [ -f "$marker" ] || { healed=1; break; }
    # RE-ASK the helper each slice (rate_limit, no fixture override): the wall it answered
    # belongs to the account that DIED; after a manual switch the ACTIVE account has no
    # wall and the helper answers its legacy default, so the wait shrinks to that. Take
    # the smaller value only — a wait never grows mid-flight.
    if [ "$err" = "rate_limit" ] && [ -z "${MESH_BACKOFF_OVERRIDE:-}" ] && [ -f "$qcmd" ] \
       && [ "$remaining" -gt 0 ]; then
      qw=$(timeout 10 python3 "$qcmd" --wait-seconds rate_limit 2>/dev/null || echo "$remaining")
      case "$qw" in ''|*[!0123456789]*) qw=$remaining ;; esac
      [ "$qw" -lt "$remaining" ] && remaining=$qw
    fi
  done
  [ "$healed" = "1" ] && continue
  death=$(date +%s)  # ceiling bounds a dead NETWORK, not the quota wall (review finding)

  # Connectivity gate for EVERY class (mirrors the autoresume per-attempt gate):
  # a RESUME is only useful if the API is reachable; when it is, this costs one
  # instant probe. ANY HTTP response = up. Past the offline ceiling the marker is LEFT
  # (the decider's stale bounds ring) and the cycle restarts — a standing watch never
  # exits on a dead network; it fires the moment the network returns.
  # W-5279e834 (D-897): the RESUME needs MESH_UP_STREAK CONSECUTIVE answers — a restore
  # often flaps, and a wake into a network that drops again dies with no watch left (the
  # arm is one wake per arm, D-356); and each poll keeps the death record fresh (`touch -c`
  # never re-creates one the decider cleared; the sliced backoff above touches it too), so a
  # > 2 h outage or quota wait cannot let the decider's 2-h lock-dir prune take it. A MESH_UP_STREAK
  # outside 1..99 (garbage, zero, huge) falls back to 3 — never a gate that runs no probe at all.
  up_streak="${MESH_UP_STREAK:-3}"
  # an allowlist: 1..99 only — spelled-out digit sets, never `[1-9]`: a glob RANGE collates by
  # locale, and under UTF-8 it admits non-ASCII digits (٣) that `[ -lt ]` cannot read
  case "$up_streak" in [123456789]|[123456789][0123456789]) ;; *) up_streak=3 ;; esac
  ceiling_hit=0
  streak=0
  while [ "$streak" -lt "$up_streak" ]; do
    touch -c "$marker" 2>/dev/null || true
    if curl -s -o /dev/null --max-time 5 https://api.anthropic.com; then
      streak=$(( streak + 1 ))
    else
      streak=0
      [ $(( $(date +%s) - death )) -ge "${MESH_CEILING:-1800}" ] && { ceiling_hit=1; break; }
    fi
    [ "$streak" -ge "$up_streak" ] || sleep "${MESH_POLL:-10}"
  done
  [ "$ceiling_hit" = "1" ] && continue

  sleep "$(( RANDOM % ( ${MESH_JITTER_MAX:-45} + 1 ) ))"  # share the storm jitter
  # Post-wait re-check (mirror of the autoresume per-attempt survival check): the
  # decider may have CLEARED the marker mid-wait (busy verdict — the death was
  # non-terminal). Firing then would inject a false RESUME into a live session;
  # instead keep watching for a real future death.
  [ -f "$marker" ] || continue
  rm -f "$marker" 2>/dev/null || true  # consume: one wake per death record
  printf 'RESUME: this session died on %s; the cause has been healed; resume the interrupted task — this self-watch STAYS ARMED (standing watch: do NOT re-arm; a duplicate arm exits at once)\n' "$err"
done
