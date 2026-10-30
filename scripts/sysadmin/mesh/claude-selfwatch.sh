#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/hooks-index.md
# claude-selfwatch.sh <session_id> — resume-mesh Layer 2b (interactive pane self-watch).
# Tracked home: /opt/fabrik/scripts/sysadmin/mesh/ (W-6e656dac T04); the live copy in ~/.claude/bin is installed
# from it by scripts/sysadmin/install_mesh.sh, never hand-edited. `.holdlifted` field 2: (none) quota · battery ·
# hibernate (the hibernate pause lifted, its line names the marker's lift_path) · resume (the box resumed from sleep).
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

rm -f "$marker" "$lift" "$lift.claimed" 2>/dev/null || true  # pre-arm history: never fire into the live arming session

qcmd="${MESH_QUOTA_CMD:-$HOME/.claude/bin/claude-quota.py}"
# W-5279e834 (D-897): a RESUME into a network or API that drops again dies with no watch left, so the
# death wake — and the hibernate/resume wake (W-6e656dac T04) — need MESH_UP_STREAK CONSECUTIVE answers. A
# MESH_UP_STREAK outside 1..99 (garbage, zero, huge) falls back to 3 — never a gate that runs no probe at all.
up_streak="${MESH_UP_STREAK:-3}"
# an allowlist: 1..99 only — spelled-out digit sets, never `[1-9]`: a glob RANGE collates by
# locale, and under UTF-8 it admits non-ASCII digits (٣) that `[ -lt ]` cannot read
case "$up_streak" in [123456789]|[123456789][0123456789]) ;; *) up_streak=3 ;; esac
# net_gate <answers> <file to keep fresh, or ''>: returns 0 after that many CONSECUTIVE API answers (ANY HTTP
# response = up; one failed probe restarts the count), 1 once the network has been down MESH_CEILING seconds
# counted from $death. Each probe `touch -c`es the file, so a > 2 h outage cannot let the decider's 2-h lock-dir
# prune take it (`-c` never re-creates one the decider cleared).
net_gate() {
  local need="$1" keep="$2" streak=0
  while [ "$streak" -lt "$need" ]; do
    [ -n "$keep" ] && touch -c "$keep" 2>/dev/null
    if curl -s -o /dev/null --max-time 5 https://api.anthropic.com; then
      streak=$(( streak + 1 ))
    else
      streak=0
      [ $(( $(date +%s) - death )) -ge "${MESH_CEILING:-1800}" ] && return 1
    fi
    [ "$streak" -ge "$need" ] || sleep "${MESH_POLL:-10}"
  done
  return 0
}
# lift_why: the marker's lift_path (Interface M — $ROTATE_STATE_DIR/hibernate.json, else <passwd home>/.claude/
# state/hibernate.json, $HOME only when the uid has no passwd entry), `unknown` on any error or a value that is
# not a plain word
lift_why() {
  local w
  w=$(python3 -c 'import json,os,pwd
try:
    try: h = pwd.getpwuid(os.getuid()).pw_dir
    except KeyError: h = os.path.expanduser("~")
    v = json.load(open(os.path.join(os.environ.get("ROTATE_STATE_DIR") or os.path.join(h, ".claude", "state"), "hibernate.json"))).get("lift_path")
    print(v if isinstance(v, str) else "unknown")
except Exception: print("unknown")' 2>/dev/null)
  case "$w" in ''|*[!A-Za-z0-9_-]*) w=unknown ;; esac
  printf '%s' "$w"
}
empty_since=""  # when this watch first claimed the current lift still EMPTY (T04 G1)
empty_wait="${MESH_EMPTY_WAIT:-3}"
case "$empty_wait" in [123456789]|[123456789][0123456789]) ;; *) empty_wait=3 ;; esac
while :; do
  while [ ! -f "$marker" ] && [ ! -f "$lift" ]; do sleep "${MESH_POLL:-10}"; [ "$locks/$safe.selfwatch.lock" -ef /proc/$$/fd/9 ] || { printf 'self-watch for %s: its lock file vanished (the Stop decider prunes lock-dir files older than 2h by mtime — fixed 2026-09-07 — or a manual rm); this watch EXITS so the tick and the arm nag see the truth — re-arm it\n' "$safe"; exit 0; }; done  # orphan guard (heavy review R1)
  if [ ! -f "$marker" ] && [ -f "$lift" ]; then
    # The LIFT branch: no backoff (nothing to heal). Field 2 names the hold: `battery` (W-83a8ee68),
    # `hibernate` (the hibernate pause lifted) or `resume` (the box resumed from sleep — W-6e656dac T04,
    # W-b01aa1ec); a quota lift writes one field, and anything else reads as the quota's. A quota or battery
    # lift is one probe and no jitter (a handful of panes, not a storm); a hibernate or resume wake reaches
    # EVERY paused agent at once off a network that just came back, so it takes the death branch's
    # MESH_UP_STREAK answers and storm jitter (spec L3, D-897). `death` is the gate's ceiling clock (`set
    # -u`: it must be set here). On the ceiling the file stays and the cycle restarts (W9's shape); a death
    # marker arriving meanwhile wins the next poll and the lift follows it on the iteration after.
    case "$(awk '{print $2; exit}' "$lift" 2>/dev/null || true)" in
      hibernate|resume) need=$up_streak; jitter=1 ;;
      *) need=1; jitter=0 ;;
    esac
    death=$(date +%s)
    net_gate "$need" "$lift" || continue
    [ "$jitter" = "1" ] && sleep "$(( RANDOM % ( ${MESH_JITTER_MAX:-45} + 1 ) ))"
    # CLAIM the lift atomically (T04 F14, the sweep's mv-claim): three reads then an `rm` could delete a lift the
    # tick wrote in between, unwoken. A failed mv means it was consumed or cleaned meanwhile (a fresh arm).
    claimed="$lift.claimed"
    mv -f "$lift" "$claimed" 2>/dev/null || { empty_since=""; continue; }
    # read the CLAIMED file AFTER the gate (routed I13): a hibernate lift's fan-out replaces a pending `resume` wake
    # while the gate waits, and the line must carry the replacing kind and its epoch — the LIFT epoch, so
    # the line names when the hold went, not when the wake landed
    lift_at=$(awk '{print $1; exit}' "$claimed" 2>/dev/null || true)
    lift_kind=$(awk '{print $2; exit}' "$claimed" 2>/dev/null || true)
    # put the lift back and gate again (T04 F9) when the gate it passed was SHORTER than the kind now printed needs:
    # a one-field (quota) or still-EMPTY file read before the gate (the tick creates it O_EXCL, then writes) that
    # now says hibernate/resume — the hibernate line is printed only after MESH_UP_STREAK answers and the jitter.
    # A file still EMPTY may be the tick mid-write: back it goes too, for at most MESH_EMPTY_WAIT (3) seconds
    # counted from when THIS watch first saw it empty (T04 G1 — never from its mtime: net_gate `touch -c`es the file
    # on every probe, so an mtime clock never runs out); one that stays empty is then consumed as a quota wake.
    # `mv -n` never overwrites a NEWER lift written meanwhile; the claimed copy then goes (the newer one wins, as
    # the tick's fan-out does).
    # the empty-wait clock describes only a file that has STAYED empty (T04 H1): a non-empty claim resets it,
    # whether it is consumed or re-gated on a kind upgrade
    [ -n "$lift_at" ] && empty_since=""
    regate=0
    case "$lift_kind" in hibernate|resume) [ "$need" -lt "$up_streak" ] && regate=1 ;; esac
    if [ -z "$lift_at" ]; then
      [ -n "$empty_since" ] || empty_since=$(date +%s)
      [ $(( $(date +%s) - empty_since )) -lt "$empty_wait" ] && regate=1
    fi
    [ "$regate" = "1" ] || empty_since=""
    if [ "$regate" = "1" ]; then
      mv -n "$claimed" "$lift" 2>/dev/null
      rm -f "$claimed" 2>/dev/null
      sleep 1
      continue
    fi
    rm -f "$claimed" 2>/dev/null || true  # consume: one wake per lift
    # 1..10 digits only (to the year 2286): a longer all-digit value passes a digits-only guard yet `date -d @`
    # refuses it and the line would print an empty time (T04 residue 5); a date that still fails falls back the same
    case "$lift_at" in ''|*[!0123456789]*|???????????*) lift_at=$(date +%s) ;; esac
    at=$(date -d @"$lift_at" +%H:%M 2>/dev/null) || at=$(date +%H:%M)
    case "$lift_kind" in
      hibernate)
        # the condition agents_up's relaunch prompt carries (agents_up.sh): `woke` exits 1 for a migration lift
        # and a lift a day old, and then there is nothing to resume (T04 F12)
        printf 'RESUME: the hibernate pause ended at %s (%s) — run python3 /opt/fabrik/scripts/sysadmin/hibernate.py woke --self %s and, only if it exits 0, resume your item from the seed it prints; on exit 1 carry on as usual; on exit 2 stay paused and tell your coordinator' "$at" "$(lift_why)" "$sid" ;;
      resume)
        printf 'RESUME: the box RESUMED from sleep at %s. If you stopped for it, resume the run you closed BLOCKED — its record (`python3 scripts/command_run.py line`) and `python3 scripts/thread_anchor.py line --session %s` carry where you left off; if you are mid-task, ignore this line' "$at" "$sid" ;;
      battery)
        printf 'RESUME: the battery hold LIFTED at %s (mains power is back). If you stopped for it, resume the run you closed BLOCKED — its record (`python3 scripts/command_run.py line`) and `python3 scripts/thread_anchor.py line --session %s` carry where you left off; if you are mid-task, ignore this line' "$at" "$sid" ;;
      *)
        printf 'RESUME: the fleet-quota hold LIFTED at %s (the rotation tick saw relief). If you stopped for it, resume the run you closed BLOCKED — its record (`python3 scripts/command_run.py line`) and `python3 scripts/thread_anchor.py line --session %s` carry where you left off; if you are mid-task, ignore this line' "$at" "$sid" ;;
    esac
    # every RESUME line ends in this clause: selfwatch_arm.sh cuts the line at it (scripts/sysadmin/selfwatch_arm.sh)
    printf ' — this self-watch STAYS ARMED (do NOT re-arm; a duplicate arm exits at once)\n'
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
  # arm is one wake per arm, D-356); and each poll keeps the death record fresh (the sliced
  # backoff above touches it too), so a > 2 h outage or quota wait cannot let the decider's
  # 2-h lock-dir prune take it (net_gate, above).
  net_gate "$up_streak" "$marker" || continue

  sleep "$(( RANDOM % ( ${MESH_JITTER_MAX:-45} + 1 ) ))"  # share the storm jitter
  # Post-wait re-check (mirror of the autoresume per-attempt survival check): the
  # decider may have CLEARED the marker mid-wait (busy verdict — the death was
  # non-terminal). Firing then would inject a false RESUME into a live session;
  # instead keep watching for a real future death.
  [ -f "$marker" ] || continue
  rm -f "$marker" 2>/dev/null || true  # consume: one wake per death record
  printf 'RESUME: this session died on %s; the cause has been healed; resume the interrupted task — this self-watch STAYS ARMED (standing watch: do NOT re-arm; a duplicate arm exits at once)\n' "$err"
done
