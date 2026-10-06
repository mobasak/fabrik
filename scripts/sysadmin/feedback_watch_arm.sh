#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/hooks-index.md | tests/test_kaizen_agent_wiring.py | scripts/sysadmin/selfwatch_check.py | docs/reference/agents/kaizen.md
# feedback_watch_arm.sh <session_id> — the kaizen window's ONE-WAKE feedback watch (the selfwatch_arm.sh shape).
#
# Arm: Bash(run_in_background: true, command: "bash /opt/fabrik/scripts/sysadmin/feedback_watch_arm.sh <sid>")
# Holds <lockdir>/<safe-sid>.feedbackwatch.lock for its life (a duplicate arm exits at once), snapshots the
# SUM of the command-feedback queue depths and the hub inbox, then blocks on inotifywait (poll fallback)
# over the ledger, the kaizen series dir and the inbox. It wakes — prints ONE line and exits — only when a
# queue's depth ROSE (naming each risen command's `/fabrik-command-improve`), a NEW inbox file is addressed
# to kaizen with `ack: required` (naming the id to claim), or a series file changed. A `change: none` row,
# another beat's mail and a removal never wake it. The wake line IS the order: the Stop hook's feedback rung
# exhausts a subject after CAP blocks per session, so a long-running window would otherwise never be told.
# FEEDBACK_WATCH_MIN_S (default 600) holds a wake that arrives within that many seconds of the arm.
set -u
main() {
sid="${1:?session id}"
safe="$(printf '%s' "$sid" | tr -c 'A-Za-z0-9_-' '_' | head -c 64)"
locks="${CLAUDE_SOUND_LOCKDIR:-/tmp/claude-sound-locks-$(id -u)}"
ledger="${FEEDBACK_LEDGER:-$HOME/.claude/state/command-feedback.jsonl}"
series="${KAIZEN_SERIES_DIR:-$HOME/.claude/state/kaizen/series}"
inbox="${FABRIK_HUB_INBOX:-${FABRIK_MAIL_ROOT:-/opt/fabrik-mail}/fabrik/inbox}"  # mail.py's own root knob; FABRIK_HUB_INBOX is the test override
report="${FEEDBACK_REPORT:-/opt/fabrik/scripts/command_feedback_report.py}"
poll="${FEEDBACK_WATCH_POLL:-30}"
min_s="${FEEDBACK_WATCH_MIN_S:-600}"
mkdir -p "$locks" 2>/dev/null || true
if ! exec 9>"$locks/$safe.feedbackwatch.lock"; then
  printf 'feedback-watch NOT armed: cannot open %s/%s.feedbackwatch.lock\n' "$locks" "$safe"; exit 1
fi
if ! flock -n 9; then
  printf 'feedback-watch already armed for %s — this duplicate exits; the standing watch stays\n' "$safe"; exit 0
fi
depths() {  # one JSON object {command: depth}; {} on any failure — FAIL-OPEN: an unreadable ledger shows no rise, so this watch wakes nobody for it; the per-prompt check and the Stop ladder are the backstop
  python3 "$report" --ledger "$ledger" --depths 2>/dev/null || printf '{}'
}
risen() {  # commands whose depth rose from $1 to $2, one per line
  python3 - "$1" "$2" <<'PY'
import json, sys
try:
    a, b = json.loads(sys.argv[1] or "{}"), json.loads(sys.argv[2] or "{}")
except ValueError:
    sys.exit(0)
for cmd in sorted(b):
    if int(b.get(cmd, 0)) > int(a.get(cmd, 0)):
        print(cmd)
PY
}
kaizen_mail() {  # for each inbox file not yet judged ($1 = names already judged): `WAKE <id>` when it is
  # addressed to kaizen with ack: required, `SEEN <name>` once its frontmatter is complete and it is not —
  # a file still being written (no closing `---` yet) is left unjudged so the next event re-reads it
  for f in "$inbox"/*.md; do
    [ -f "$f" ] || continue
    case " $1 " in *" ${f##*/} "*) continue ;; esac
    [ "$(grep -c '^---$' "$f" 2>/dev/null)" -ge 2 ] || continue
    if grep -q '^agent: kaizen$' "$f" && grep -q '^ack: required$' "$f"; then
      printf 'WAKE %s\n' "$(basename "$f" .md)"
    else
      printf 'SEEN %s\n' "${f##*/}"
    fi
  done
}
series_sig() { ls -l --time-style=+%s "$series" 2>/dev/null | md5sum | cut -c1-32; }
base_depths="$(depths)"
base_series="$(series_sig)"
judged=" "  # inbox files already judged not-for-kaizen; a wake exits, so a woken id is never re-judged
# files present at arm time are judged now and never wake: the arm is the kaizen window's own act,
# so whatever already sits in the inbox is on its ladder, not news
while IFS=' ' read -r verdict name; do [ "$verdict" = "SEEN" ] || [ "$verdict" = "WAKE" ] && judged="$judged$name "; [ "$verdict" = "WAKE" ] && judged="$judged$name.md "; done <<EOF_J
$(kaizen_mail "$judged")
EOF_J
armed_at=$(date +%s)
: > "$locks/$safe.feedbackwatch.ready"  # the snapshot is taken: from here on a change is news (a test waits on this)
while :; do
  # watch only the paths that EXIST: inotifywait exits in milliseconds on a missing path and the
  # loop would spin (pass 1, C-S1); with none present, or no inotifywait, plain sleep paces it
  watch=()
  for w in "$ledger" "$series" "$inbox"; do [ -e "$w" ] && watch+=("$w"); done
  if command -v inotifywait >/dev/null 2>&1 && [ "${#watch[@]}" -gt 0 ]; then
    inotifywait -q -q -t "$poll" -e modify -e create -e moved_to -e close_write "${watch[@]}" >/dev/null 2>&1
    rc=$?
    [ "$rc" -eq 0 ] || [ "$rc" -eq 2 ] || sleep "$poll"  # an error exit must not become a spin
  else
    sleep "$poll"
  fi
  [ "$locks/$safe.feedbackwatch.lock" -ef /proc/$$/fd/9 ] || { printf 'feedback-watch for %s: its lock file vanished — this watch EXITS; re-arm it\n' "$safe"; exit 0; }
  now_depths="$(depths)"
  up="$(risen "$base_depths" "$now_depths")"
  mail=""
  while IFS=' ' read -r verdict name; do
    [ -n "$verdict" ] || continue
    if [ "$verdict" = "WAKE" ]; then mail="$mail$name "; else judged="$judged$name "; fi
  done <<EOF_J
$(kaizen_mail "$judged")
EOF_J
  # judged is pruned to the files still in the inbox: a claim or ack removes its file, so the
  # list is bounded by the inbox, never by the watch's lifetime (pass 1, C-S6)
  kept=" "
  for f in "$inbox"/*.md; do [ -f "$f" ] || continue; case "$judged" in *" ${f##*/} "*) kept="$kept${f##*/} " ;; esac; done
  judged="$kept"
  now_series="$(series_sig)"
  if [ -z "$up" ] && [ -z "$mail" ] && [ "$now_series" = "$base_series" ]; then
    continue  # removals, other beats' mail and `change: none` rows never wake
  fi
  wait_s=$(( armed_at + min_s - $(date +%s) ))
  [ "$wait_s" -gt 0 ] && sleep "$wait_s"
  line="FEEDBACK WAKE:"
  for c in $up; do line="$line run \`/fabrik-command-improve $c\` (its queue rose) ·"; done
  for m in $mail; do line="$line mail addressed to you: \`python3 scripts/mail.py claim $m\` then handle it ·"; done
  [ "$now_series" != "$base_series" ] && line="$line the kaizen series changed — read today's row ·"
  rm -f "$locks/$safe.feedbackwatch.ready" 2>/dev/null
  printf '%s\n' "${line% ·}"
  printf 'This wake ENDED the watch (one wake per arm) — re-arm it: Bash(run_in_background: true, command: "bash /opt/fabrik/scripts/sysadmin/feedback_watch_arm.sh %s")\n' "$sid"
  exit 0
done
}
main "$@"; exit $?
