#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/hooks-index.md
# claude-reboot-sweep.sh — resume-mesh Layer 4: after a boot, bring the BUILDERS back and tell the operator
# about every other session the boot cut mid-work. It RESUMES NOTHING with `claude -p` (W-6e656dac T04, spec L4).
#
# Plan: docs/development/plans/2026-08-10-plan-1-quota-health.md (Phase D); the builder leg and the end of the
# `claude -p` resume: docs/development/plans/2026-10-21-plan-1-hibernate-full-guarantee/ (T04). Tracked home:
# /opt/fabrik/scripts/sysadmin/mesh/; the live ~/.claude/bin copy is installed by scripts/sysadmin/install_mesh.sh.
# Operator problem it solves (verbatim): "if i restart the machine, i go each chat window one by
# one and type a command."
#
# Leg A — AUTONOMOUS markers (`<sid>.autonomous`, written by the ORIENT hook only when the launcher exported
# CLAUDE_MESH_AUTONOMOUS=1): each marker is CONSUMED with one log line saying whether its disposable worker was
# cut mid-work (the decider's `busy-*`/`stalled-api-error*` verdict, or a standing `errparked` record) — never
# resumed: a `claude -p --resume` of a session that is also open in a pane runs one session in two processes and
# forks it, and the old re-export of CLAUDE_MESH_AUTONOMOUS=1 re-marked the resumed session on every boot.
# Ordering matters: the sid's PRE-REBOOT `.reviving` is cleared FIRST — its mtime predates the boot, so the
# decider would read it as a dead reviver and invite a second writer.
#
# Builder leg — once per boot PER REPO (a persistent stamp, $state/.builders-boot, latches a repo only after its
# grid launched, so a failed leg's repos come back on a later sweep; --list's skip lines are noted
# `builders-skipped`), on a fresh boot, wait up to
# MESH_BUS_WAIT (120 s) for the user bus (MESH_BUS_SOCKET, default /run/user/<uid>/bus, re-checked every probe),
# then for every repo `agents_bat.py --list` prints read its grid's `pane <name> <sid> <folder> <status>` lines
# (`agents_up.sh --print`) and build the grid with `agents_up.sh --detach` (cron has no terminal); only a grid
# that launched records its sids in <lockdir>/.boot-relaunched (a failed --print builds nothing, a failed
# --detach records nothing, and its exit 4 — some builder got no pane — records only the sids that got one, noted
# `builder-grid-noroom`, and leaves the repo unlatched); a bus that never answers is noted `uncapped-boot` and the grids are built anyway
# (agents_up's boot path launches uncapped with D-1075's warning), so builders always come back.
#
# Leg B — one resume-by-hand notice per OTHER session the boot cut mid-work (see below); never for a sid in
# .boot-relaunched or one Leg A consumed.
set -u

# CRON REALITY (review findings): cron gives a minimal environment — HOME may be unset
# (which `set -u` turns into an instant crash) and PATH is typically just /usr/bin:/bin,
# where neither `claude` nor a user-installed python3 lives. Fix both before anything else.
HOME="${HOME:-$(getent passwd "$(id -u)" 2>/dev/null | cut -d: -f6)}"
HOME="${HOME:-/tmp}"
export HOME
# APPEND, never prepend: an inherited PATH (an operator shell, a test harness shim)
# must keep priority; the fallbacks exist only for cron's bare /usr/bin:/bin.
PATH="$PATH:$HOME/.local/bin:/usr/local/bin"
export PATH

locks="${CLAUDE_SOUND_LOCKDIR:-/tmp/claude-sound-locks-$(id -u)}"
# PERSISTENT marker home (plan 2026-08-13-plan-1): /tmp dies with the VM (the Modern
# Standby cut wiped every marker + errparked record 13 boots in a row); markers written
# here by session_orient.py survive any VM termination. Legacy lock-dir markers are
# still honored (transition + fixtures) — state-dir copy wins on a sid collision.
state="${MESH_STATE_DIR:-$HOME/.claude/state/autonomous}"
decider="${MESH_DECIDER_CMD:-$HOME/.claude/bin/claude-stop-decider.py}"
agents_bat="${MESH_AGENTS_BAT:-/opt/fabrik/scripts/sysadmin/agents_bat.py}"
agents_up="${MESH_AGENTS_UP:-/opt/fabrik/scripts/sysadmin/agents_up.sh}"
max_age="${MESH_SWEEP_MAX_AGE:-604800}"   # a marker older than a week is stale history
log="${MESH_SWEEP_LOG:-$HOME/.claude/sound-debug.log}"

note() {  # one line per decision — the sweep must never be a silent black box
  # a TAB or newline inside a field (a repo path may hold either) is written escaped, so a note is ONE line whose
  # fields split on spaces (T04 residue 5)
  local m="${2:-}"
  m="${m//$'\t'/\\t}"; m="${m//$'\n'/\\n}"
  printf '%s  arg=sweep     event=reboot        verdict=%-13s %s\n' \
    "$(date '+%F %T')" "$1" "$m" >> "$log" 2>/dev/null || true
}

command -v python3 >/dev/null 2>&1 || { note "abort-no-python3" "PATH=$PATH"; exit 0; }
# Self-lock (review F3): @reboot is not flocked, and a concurrent sweep (cron-daemon restart, manual
# run) would double-build the grids and double-notify — the second-writer failure.
# The state dir is defaulted-and-created FIRST: a box where no writer ever ran has none,
# and a failed `exec 9>` would otherwise abort the whole sweep.
mkdir -p -m 700 "$state" 2>/dev/null || true
if command -v flock >/dev/null 2>&1 && exec 9>"$state/.sweep.lock" 2>/dev/null; then
  flock -n 9 || { note "skip-concurrent" "another sweep holds $state/.sweep.lock"; exit 0; }
else
  # No flock binary, or the lock file is unopenable (ro/full state dir): degrade to the
  # pre-2026-08-13 unlocked behavior — but LOUDLY (review finding: a silent degrade hides
  # the exact window the lock exists for). The mv-claim still bounds the damage to one
  # consume per marker.
  note "flock-unavailable" "sweeping unlocked — $state/.sweep.lock unopenable or no flock"
fi

up_s=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || true)
case "$up_s" in ''|*[!0-9]*)
  # closing-round #2: an unreadable /proc/uptime (or awk missing from cron's PATH) must
  # degrade LOUDLY, never `set -u`-kill the whole mesh before the first note. boot=0 makes
  # every window empty (corpse-clear deletes nothing, Leg B scans nothing) — the lockdir
  # leg of the freshness gate still works.
  note "no-uptime" "/proc/uptime unreadable — boot-window features disabled this run"
  up_s="" ;;
esac
if [ -n "$up_s" ]; then boot=$(( $(date +%s) - up_s )); else boot=0; fi
lockdir_missing=0
if [ ! -d "$locks" ]; then
  # Every genuine boot starts /tmp-empty, so a missing lock dir alone is NORMAL — it stops
  # being an exit (markers are persistent now): note it, recreate, and keep sweeping.
  lockdir_missing=1
  note "no-lockdir" "$locks (recreated — markers are persistent, sweep continues)"
  mkdir -p -m 700 "$locks" 2>/dev/null || true
else
  # A fresh boot with the dir already recreated by a hook: pre-boot `.reviving` corpses
  # would otherwise survive a no-claude sweep (confirm-round minor ii) — clear any that
  # predate this boot; a live reviver's file is always younger than the boot.
  find "$locks" -maxdepth 1 -name '*.reviving' ! -newermt "@$boot" -delete 2>/dev/null || true
fi

# Gather markers from BOTH dirs into one list (review F2/F4: the old in-loop
# `[ -e ] || break` aborts on the first unmatched glob — a naive two-glob union would
# silently skip the legacy dir whenever the state dir is empty). State-dir copy wins a
# sid collision; the legacy twin is removed at claim time so each sid is consumed once.
markers=()
for m in "$state"/*.autonomous; do
  [ -e "$m" ] && markers+=("$m")
done
for m in "$locks"/*.autonomous; do
  [ -e "$m" ] || continue
  [ -e "$state/$(basename "$m")" ] || markers+=("$m")
done

# vm-cut classification, Leg A evidence: persistent markers survived a boot that wiped
# /tmp — the VM was terminated out from under marked sessions (standby cut, host kill).
if [ "$lockdir_missing" = "1" ] && [ "${#markers[@]}" -gt 0 ]; then
  note "vm-cut" "boot=$boot markers=${#markers[@]} — /tmp wiped under marked sessions"
fi

now=$(date +%s)
swept=0
consumed_sids=" "
for marker in "${markers[@]}"; do
  # ONE read: three separate parses could see three different states if the marker were
  # rewritten mid-loop, and cost 3 interpreter starts per session (review finding).
  fields=$(python3 -c "
import json,sys
try:
    d = json.load(open(sys.argv[1]))
    print(d.get('sid','')); print(d.get('cwd','')); print(d.get('transcript_path',''))
except Exception:
    print(''); print(''); print('')" "$marker" 2>/dev/null || printf '\n\n\n')
  sid=$(printf '%s' "$fields" | sed -n 1p)
  cwd=$(printf '%s' "$fields" | sed -n 2p)
  tpath=$(printf '%s' "$fields" | sed -n 3p)
  base=$(basename "$marker" .autonomous)
  [ -n "$sid" ] || sid="$base"
  safe=$(printf '%s' "$sid" | tr -c 'A-Za-z0-9_-' '_' | head -c 64)

  # Stale marker: the session it described is long gone.
  m_age=$(( now - $(stat -c %Y "$marker" 2>/dev/null || echo "$now") ))
  if [ "$m_age" -gt "$max_age" ]; then
    rm -f "$marker" "$locks/$safe.autonomous" "$state/$safe.autonomous" 2>/dev/null || true
    note "stale-marker" "sess=${safe:0:8} age=${m_age}s"
    continue
  fi

  # closing-round #1: the blanket .reviving delete is GONE — the boot-window clear above
  # owns pre-boot corpses, and deleting a FRESH .reviving here would destroy a live
  # reviver's second-writer interlock (cron-restart @reboot mid-uptime). A live reviver
  # also makes this sid INELIGIBLE for the sweep: two resumers on one session is the exact
  # failure the mesh exists to prevent.
  rev_mt=$(stat -c %Y "$locks/$safe.reviving" 2>/dev/null || echo 0)
  rev_live=0
  if [ "$rev_mt" -gt 0 ]; then
    # UNION of two individually-verified liveness signals (round-6: either alone fails
    # open somewhere). (1) RECENT (<2100s — sound.sh's own mesh_rev_fresh window): covers
    # no-uptime/boot=0 runs. (2) POST-BOOT (written this uptime): covers a live reviver
    # whose unbounded `claude -p` attempt has gone quiet >2100s mid-uptime. Corpse = BOTH
    # say dead; a leaked post-boot file blocks at most one uptime (/tmp dies at boot).
    [ $(( now - rev_mt )) -lt 2100 ] && rev_live=1
    [ "$boot" -gt 0 ] && [ "$rev_mt" -ge "$boot" ] && rev_live=1
  fi
  if [ "$rev_live" = "1" ]; then
    note "skip-reviver-pending" "sess=${safe:0:8} — live reviver holds this sid"
    continue
  fi
  rm -f "$locks/$safe.reviving" 2>/dev/null || true  # pre-boot AND stale: corpse

  # LIVENESS GATE (review finding): `@reboot` fires whenever the cron DAEMON restarts —
  # a package upgrade or `systemctl restart cron` triggers it while sibling sessions are
  # still alive. Resuming a live session is the second-writer failure this mesh exists to
  # prevent, so a transcript touched within the liveness window means "still running":
  # skip it and leave the marker for a genuine boot. (A live session appends constantly;
  # a session killed by a reboot cannot have touched its transcript since.)
  live_window="${MESH_SWEEP_LIVE_WINDOW:-300}"
  if [ -n "$tpath" ] && [ -f "$tpath" ]; then
    t_age=$(( now - $(stat -c %Y "$tpath" 2>/dev/null || echo 0) ))
    if [ "$t_age" -lt "$live_window" ]; then
      note "skip-still-live" "sess=${safe:0:8} transcript_age=${t_age}s"
      continue
    fi
  fi

  # Eligibility: real mid-work only. The decider is the authority on "busy".
  # NB `--check` evaluates with turn_dead=False by design here: post-reboot we WANT an
  # in-flight tool call to read as resumable mid-work rather than as a corpse.
  eligible=0
  reason=""
  if [ -f "$locks/$safe.errparked" ]; then
    eligible=1; reason="errparked"
  elif [ -n "$tpath" ] && [ -f "$tpath" ] && [ -f "$decider" ]; then
    verdict=$(printf '{"session_id":"%s","transcript_path":"%s","cwd":"%s"}' "$sid" "$tpath" "$cwd" \
      | timeout 20 python3 "$decider" --check 2>/dev/null || true)
    # busy* = interrupted mid-work; stalled-api-error* = the decider's DEATH classes
    # (mid-stream + connection-failure) — dead-mid-work IS resumable mid-work here, and
    # with /tmp wiped there is no errparked record left to say so (plan 2026-08-13-plan-1
    # Gap 2; the decider prints no other verdict starting "stalled").
    case "$verdict" in busy*|stalled-api-error*) eligible=1; reason="${verdict%%:*}" ;; esac
  fi

  if [ "$eligible" != "1" ]; then
    rm -f "$marker" "$locks/$safe.autonomous" "$state/$safe.autonomous" 2>/dev/null || true
    note "skip-not-midwork" "sess=${safe:0:8}"
    continue
  fi

  # ATOMIC claim (review F5/F6): `rm -f` can never be a claim — it succeeds on an already-deleted
  # file (two racing sweeps would both "consume") and a swallowed rm failure on an unremovable
  # PERSISTENT marker would come back on every boot. `mv` is atomic per marker: exactly one claimant
  # wins, and a failed claim (ro dir, full disk) is said and retried next boot.
  if ! mv "$marker" "$marker.claimed" 2>/dev/null; then
    note "consume-failed" "sess=${safe:0:8} — marker unclaimable, kept for the next boot"
    continue
  fi
  rm -f "$locks/$safe.autonomous" "$state/$safe.autonomous" 2>/dev/null || true  # twin copy
  rm -f "$marker.claimed" 2>/dev/null || true
  # CONSUMED, never resumed (W-6e656dac T04, spec L4): `claude -p --resume` forks a session a pane may
  # also hold, and its CLAUDE_MESH_AUTONOMOUS=1 re-export re-marked the session every boot. The worker
  # was disposable; the line says it was cut mid-work, and Leg B below sends no notice for it.
  consumed_sids="$consumed_sids$sid "
  swept=$(( swept + 1 ))
  note "autonomous-consumed" "sess=${safe:0:8} why=$reason — a disposable worker cut mid-work; never resumed"
done

# ── Builder leg (W-6e656dac T04, spec L4, Interface G): on a FRESH boot (the same two signals as Leg B's
# gate, computed here), bring every registered repo's builders back in a DETACHED tmux grid — the boot has
# no terminal. The repos are the ones `agents_bat.py --list` prints (the registry the .bat launchers are
# generated from, with no `--print` probe, so a bus that is not answering yet cannot empty it); each grid's
# `pane` lines are read first and their sids recorded in <lockdir>/.boot-relaunched, which Leg B skips —
# telling the operator to resume by hand a session agents_up just relaunched is the two-writer failure.
fresh_window="${MESH_SWEEP_FRESH_WINDOW:-900}"
legb_fresh=0
[ "$lockdir_missing" = "1" ] && legb_fresh=1
[ $(( $(date +%s) - boot )) -lt "$fresh_window" ] && legb_fresh=1
relaunched_file="$locks/.boot-relaunched"
# ONCE PER BOOT PER REPO (T04 F13, G6): the leg would otherwise re-run on any sweep in the fresh window or whenever
# the lock dir is missing (a cron restart, a pruned /tmp) and re-launch grids the operator closed — yet a repo whose
# grid did NOT launch (a failed or killed leg) must come back on a later sweep. The PERSISTENT stamp holds this
# boot's epoch on line 1 (boot is derived from uptime, so it matches within ±60 s), then one
# `repo<TAB><sids><TAB><path>` line appended only after that repo's --detach returned 0; a later sweep this boot
# skips only those repos, and Leg B reads their sids, so a lock dir pruned after the leg still skips them. boot=0
# (no uptime) cannot be told apart from another boot, so it never skips. The PATH is LAST and compared whole (the
# rest of the line after the second TAB), passed through ENVIRON, never `awk -v` (which rewrites backslash
# escapes): any path --list prints — spaces, TABs, backslashes — round-trips (T04 H2). Sids hold no TAB.
boot_stamp="$state/.builders-boot"
same_boot=0
stamp_boot=$(head -n 1 "$boot_stamp" 2>/dev/null)
case "$stamp_boot" in ''|*[!0123456789]*) stamp_boot="" ;; esac
if [ "$boot" -gt 0 ] && [ -n "$stamp_boot" ]; then
  d=$(( boot - stamp_boot )); [ "$d" -lt 0 ] && d=$(( -d ))
  [ "$d" -le 60 ] && same_boot=1
fi
latched() {  # latched <repo>: this boot's stamp says the repo's grid launched
  [ "$same_boot" = "1" ] && LATCH_P="$1" awk 'BEGIN {p = ENVIRON["LATCH_P"]}
    substr($0, 1, 5) == "repo\t" { r = substr($0, 6); i = index(r, "\t"); if (i && substr(r, i + 1) == p) f = 1 }
    END {exit !f}' "$boot_stamp" 2>/dev/null
}
relaunched_now=" "
if [ "$legb_fresh" = "1" ]; then
  if [ "$same_boot" != "1" ]; then
    : > "$relaunched_file" 2>/dev/null || true  # this boot's list; the last boot's is history
    if printf '%s\n' "$boot" > "$boot_stamp" 2>/dev/null; then
      [ "$boot" -gt 0 ] && same_boot=1  # the stamp now describes this boot
    else
      note "builders-stamp-failed" "$boot_stamp unwritable — a later sweep this boot may re-launch a grid"
    fi
  fi
  if [ ! -f "$agents_bat" ] || [ ! -f "$agents_up" ]; then
    note "no-agents-bat" "$agents_bat or $agents_up missing — builder leg SKIPPED"
  else
    # --list's stderr goes to a FILE, then one note per line (T04 G4): a folder it skipped (unreadable, a newline
    # in its name) gets no grid, and the sweep log must say which
    errf=$(mktemp "$locks/.builder-list.XXXXXX" 2>/dev/null || mktemp 2>/dev/null) || errf=/dev/null
    all_repos=$(timeout 60 python3 "$agents_bat" --list 2>"$errf" </dev/null 9>&- || true)
    if [ "$errf" != /dev/null ]; then
      # only a line ending `; skipped` names a skipped folder (agents_bat writes each on one line, a newline in a
      # name escaped); any other stderr line (a warning, a traceback) is noted under its own label (T04 residue 5)
      while IFS= read -r skipline; do
        case "$skipline" in
          '') ;;
          *'; skipped') note "builders-skipped" "$(printf '%s' "$skipline" | cut -c1-200)" ;;
          *) note "builders-list-stderr" "$(printf '%s' "$skipline" | cut -c1-200)" ;;
        esac
      done < "$errf"
      rm -f "$errf" 2>/dev/null
    fi
    repos=""
    n_latched=0
    while IFS= read -r repo; do
      [ -n "$repo" ] || continue
      if latched "$repo"; then n_latched=$(( n_latched + 1 )); continue; fi
      repos="$repos$repo
"
    done <<EOF_ALL
$all_repos
EOF_ALL
    if [ -z "$all_repos" ]; then
      note "builders-none" "agents_bat.py --list printed no repo"
    elif [ -z "$repos" ]; then
      note "builders-already-this-boot" "all $n_latched grid(s) launched at boot=$stamp_boot ($boot_stamp) — none re-launched"
    else
      [ "$n_latched" -gt 0 ] && note "builders-already-this-boot" "$n_latched grid(s) launched earlier this boot — only the rest are built"
      # the user bus: agents_up asks the same question (`systemctl --user show-environment`) to cap the
      # panes, and a boot reaches this line before the user manager answers. XDG_RUNTIME_DIR is derived INSIDE
      # each probe (T04 F11): a socket that appears during the wait must be seen by the next probe.
      bus_sock="${MESH_BUS_SOCKET:-/run/user/$(id -u)/bus}"
      bus_up() {
        if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -S "$bus_sock" ]; then
          XDG_RUNTIME_DIR=$(dirname "$bus_sock"); export XDG_RUNTIME_DIR
        fi
        systemctl --user show-environment >/dev/null 2>&1 </dev/null
      }
      bus_wait="${MESH_BUS_WAIT:-120}"
      case "$bus_wait" in ''|*[!0123456789]*) bus_wait=120 ;; esac
      bus_poll="${MESH_BUS_POLL:-5}"
      case "$bus_poll" in ''|*[!0123456789]*|0) bus_poll=5 ;; esac
      bus_t0=$(date +%s)
      until bus_up; do
        if [ $(( $(date +%s) - bus_t0 )) -ge "$bus_wait" ]; then
          note "uncapped-boot" "no user bus within ${bus_wait}s — agents_up --detach launches the panes UNCAPPED (D-1075's warning)"
          break
        fi
        sleep "$bus_poll"
      done
      # T04 F10: a sid is recorded as relaunched IFF the leg launched it — `--print` failing builds nothing for
      # that repo (its sessions stay notifiable); `--detach` failing records nothing; no session is both
      # launched and notified.
      while IFS= read -r repo; do
        case "$repo" in /*) ;; *) continue ;; esac
        # both outputs go to FILES, never a `$( )` pipe: the grid's tmux server (or anything else the launch
        # leaves running) holding the pipe's write end would hang the sweep for its lifetime; fd 9 closed: an
        # inherited sweep lock would make every later sweep skip-concurrent for that lifetime (closer F3)
        pf=$(mktemp "$locks/.builder-print.XXXXXX" 2>/dev/null || mktemp 2>/dev/null) || pf=""
        if [ -z "$pf" ]; then
          note "builder-print-failed" "repo=$repo — no temp file for its pane lines; grid NOT built, its sessions stay notifiable"
          continue
        fi
        timeout 60 bash "$agents_up" --print "$repo" </dev/null >"$pf" 2>/dev/null 9>&-
        prc=$?
        sids=$(awk '$1 == "pane" && $3 ~ /^[A-Za-z0-9_-]+$/ {print $3}' "$pf" 2>/dev/null)
        rm -f "$pf" 2>/dev/null
        if [ "$prc" != "0" ]; then
          note "builder-print-failed" "repo=$repo rc=$prc — agents_up --print failed; grid NOT built, its sessions stay notifiable"
          continue
        fi
        outf="$locks/.builder-grid.out"
        : > "$outf" 2>/dev/null || outf=/dev/null  # an unwritable lock dir must never skip the launch
        timeout 300 bash "$agents_up" --detach "$repo" </dev/null >"$outf" 2>&1 9>&-
        rc=$?
        if [ "$rc" = "0" ]; then
          note "builder-grid" "repo=$repo rc=0 $(tail -n 1 "$outf" 2>/dev/null | cut -c1-200)"
          # the per-repo latch, only now that the grid launched (G6)
          printf 'repo\t%s\t%s\n' "$(printf '%s' "$sids" | tr '\n' ' ')" "$repo" >> "$boot_stamp" 2>/dev/null
          if [ -n "$sids" ]; then
            printf '%s\n' "$sids" >> "$relaunched_file" 2>/dev/null
            relaunched_now="$relaunched_now$(printf '%s' "$sids" | tr '\n' ' ') "
          fi
        elif [ "$rc" = "4" ]; then
          # T04 residue 3: the grid is up but agents_up opened no pane for some builders ("no room for <name>'s pane
          # (session <sid>)"): those sids are NOT relaunched — Leg B notices them — and the repo is NOT latched, so a
          # later sweep this boot runs it again; only the sids that did get a pane are recorded relaunched
          skipped=$(sed -n "s/^agents_up: no room for [a-z0-9-]*'s pane (session \([A-Za-z0-9_-]*\)).*/\1/p" "$outf" 2>/dev/null)
          skipped_l=$(printf '%s' "$skipped" | tr '\n' ' ')
          placed=""
          for s in $sids; do
            case " $skipped_l " in *" $s "*) ;; *) placed="$placed$s
" ;; esac
          done
          [ -n "$skipped" ] || placed=""  # an unreadable skip list: record nothing, every session stays notifiable
          note "builder-grid-noroom" "repo=$repo rc=4 — no pane for ${skipped_l:-(unread)} — not latched, those sessions stay notifiable"
          if [ -n "$placed" ]; then
            printf '%s' "$placed" >> "$relaunched_file" 2>/dev/null
            relaunched_now="$relaunched_now$(printf '%s' "$placed" | tr '\n' ' ') "
          fi
        else
          note "builder-grid-failed" "repo=$repo rc=$rc — nothing recorded, its sessions stay notifiable $(tail -n 1 "$outf" 2>/dev/null | cut -c1-200)"
        fi
        [ "$outf" = /dev/null ] || rm -f "$outf" 2>/dev/null
      done <<EOF_REPOS
$repos
EOF_REPOS
    fi
  fi
fi
# this sweep's launches, the lock dir's list, and — for the same boot — the persistent stamp's sids
relaunched=" $(tr '\n' ' ' < "$relaunched_file" 2>/dev/null) $relaunched_now "
if [ "$same_boot" = "1" ]; then
  relaunched="$relaunched$(awk -F '\t' '$1 == "repo" {print $2}' "$boot_stamp" 2>/dev/null | tr '\n' ' ') "
fi

# ── Leg B: cut-mid-work NOTIFY for every session — interactive panes included (plan
# 2026-08-13-plan-1; the 2026-08-13 standby incident's population was ALL interactive,
# which the marker leg structurally excludes). A transcript last written BEFORE this boot
# whose decider verdict is still busy/stalled was cut by whatever killed the VM; auto-
# resuming a pane is forbidden (second-writer), so the operator gets one Telegram per cut
# session with the exact resume command, via the sound script's EXISTING mesh-notify mode
# (invoked, never edited). A persistent per-sid stamp bounds bounce-loop re-notifies.
# prune state litter (closer F16) — UNCONDITIONALLY (confirm-round: hygiene of the
# persistent dir must not depend on the notifier's existence or the boot's freshness)
find "$state" -maxdepth 1 -name '*.claimed' -mmin +1440 -delete 2>/dev/null || true
find "$state" -maxdepth 1 -name 'notified-*' -mtime +7 -delete 2>/dev/null || true

sound="$HOME/.claude/bin/claude-sound.sh"
# Gate (closer F4/F17): Leg B runs only on a FRESH boot — a cron-daemon-restart @reboot
# re-fire mid-uptime must not rescan a fixed [boot-48h, boot] window and re-notify day-old
# corpses. TWO signals, either suffices (confirm-round finding: the lockdir sentinel alone
# RACES — any session hook recreates /tmp/claude-sound-locks-* during the crontab's
# `sleep 120`, which would silently kill Leg B on exactly the incident class; uptime is
# race-immune): the VM booted within MESH_SWEEP_FRESH_WINDOW seconds, OR the lock dir was
# genuinely absent when we looked (`legb_fresh`, computed before the builder leg, which shares it).
if [ -f "$sound" ] && [ "$legb_fresh" = "1" ]; then
  cut_found=0
  # sidecar exclusion (closer F1/F2): subagent transcripts are not resumable sessions and
  # would otherwise both fill the head-N budget and generate bogus resume commands
  scan=$(find "$HOME/.claude/projects" -name '*.jsonl' -type f ! -path '*/subagents/*' \
           -newermt "@$(( boot - 172800 ))" ! -newermt "@$boot" 2>/dev/null \
         | while IFS= read -r f; do stat -c '%Y %n' "$f" 2>/dev/null; done \
         | sort -rn | head -20 | cut -d' ' -f2-)
  while IFS= read -r tp; do
    [ -n "$tp" ] && [ -f "$tp" ] || continue
    sid=$(basename "$tp" .jsonl)
    case "$consumed_sids" in *" $sid "*) continue ;; esac  # closer F6: Leg A consumed this
                # disposable worker's marker — it is never resumed, by the sweep or by hand
    case "$relaunched" in *" $sid "*)  # the builder leg relaunched it in its grid — a by-hand
      note "skip-relaunched" "sess=${sid:0:8} — the builder leg relaunched it"  # resume is the two-writer failure
      continue ;;
    esac
    safe=$(printf '%s' "$sid" | tr -c 'A-Za-z0-9_-' '_' | head -c 64)
    stamp="$state/notified-$safe"
    if [ -f "$stamp" ] && [ "$(( now - $(stat -c %Y "$stamp" 2>/dev/null || echo 0) ))" -lt 86400 ]; then
      continue   # already notified for this cut within 24h (bounce loops must not storm)
    fi
    # cwd: prefer the transcript's own records; fall back to decoding the project dir
    # name (-opt-foo → /opt/foo — project names keep their dashes verbatim, best-effort)
    cwd=$(tail -c 65536 "$tp" 2>/dev/null | python3 -c "
import json, sys
cwd = ''
for line in sys.stdin:
    try:
        c = json.loads(line).get('cwd')
    except Exception:
        continue
    if isinstance(c, str) and c:
        cwd = c
print(cwd)" 2>/dev/null || true)
    if [ -z "$cwd" ]; then
      pdir=$(basename "$(dirname "$tp")")
      case "$pdir" in -opt-*) cwd="/opt/${pdir#-opt-}" ;; esac
    fi
    if [ -z "$cwd" ]; then
      # a cut-mid-work candidate we cannot even cwd-resolve is still a LOG line, never a
      # silent skip (the sweep's no-silent-black-box contract)
      note "cut-no-cwd" "sess=${safe:0:8} tp=$tp"
      continue
    fi
    verdict=$(printf '{"session_id":"%s","transcript_path":"%s","cwd":"%s"}' "$sid" "$tp" "$cwd" \
      | timeout 20 python3 "$decider" --check 2>/dev/null || true)
    case "$verdict" in
      busy*|stalled-api-error*)
        # closing-round #3: mesh-notify hard-gates on /opt/* cwds with a silent exit 0 —
        # stamping + logging "notified" for a session it will drop is fail-silent theatre.
        # Non-/opt cut sessions get an honest log line (no stamp, so a future widening of
        # the notifier picks them up) instead of a false claim.
        case "$cwd" in
          /opt/*)
            bash "$sound" mesh-notify "$sid" "$cwd" "vm-cut" </dev/null >/dev/null 2>&1 || true
            touch "$stamp" 2>/dev/null || true
            cut_found=$(( cut_found + 1 ))
            note "cut-notify" "sess=${safe:0:8} why=${verdict%%:*} cwd=$cwd"
            ;;
          *)
            note "cut-unnotifiable" "sess=${safe:0:8} why=${verdict%%:*} cwd=$cwd — outside mesh-notify's /opt gate"
            ;;
        esac
        ;;
    esac
  done <<EOF_SCAN
$scan
EOF_SCAN
  [ "$cut_found" -gt 0 ] && note "vm-cut" "boot=$boot cut-mid-work=$cut_found notified"
fi

note "sweep-done" "consumed=$swept"
exit 0
