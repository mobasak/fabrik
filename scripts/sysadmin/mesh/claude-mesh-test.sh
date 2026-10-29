#!/usr/bin/env bash
# Resume-mesh fixture harness (plan 2026-08-09-plan-2). Self-contained sandbox:
# copies claude-sound.sh + claude-stop-decider.py into a tmp HOME, shims
# claude_rotate.py / claude / curl / notify via PATH, overrides the lock dir via
# CLAUDE_SOUND_LOCKDIR — never touches the real log, locks, or sounds.
# Exit 0 = all green. Sections: A (layer-1), B (revivers incl. spawn gate),
# W (selfwatch), C (telegram), D (waker-loss timer bridge).
set -u

SRC="${MESH_TEST_SRC:-$HOME/.claude/bin}"  # MESH_TEST_SRC: run the suite on pinned or mutant copies (review W-5279e834)
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); }
bad()  { FAIL=$((FAIL+1)); echo "FAIL: $*"; }

T=$(mktemp -d /tmp/mesh-test.XXXXXX)
trap 'rm -rf "$T"' EXIT
export HOME_REAL="$HOME"
SBHOME="$T/home"; mkdir -p "$SBHOME/.claude/bin"
cp "$SRC/claude-sound.sh" "$SRC/claude-stop-decider.py" "$SBHOME/.claude/bin/"
for f in claude-autoresume.sh claude-selfwatch.sh claude-quota.py claude-reboot-sweep.sh; do
  [ -f "$SRC/$f" ] && cp "$SRC/$f" "$SBHOME/.claude/bin/"
done
LOCKS="$T/locks"; mkdir -p "$LOCKS"
SHIM="$T/shim"; mkdir -p "$SHIM"
cat > "$SHIM/claude_rotate.py" <<'EOF'
#!/usr/bin/env python3
import os,sys,time
open(os.environ["MESH_ROTLOG"],"a").write(f"{time.time()} {' '.join(sys.argv[1:])}\n")
EOF
chmod +x "$SHIM/claude_rotate.py"
export MESH_ROTLOG="$T/rotations.log"; : > "$MESH_ROTLOG"

# Quota-health sandbox for the failure-branch fixtures: the helper resolves accounts
# from CLAUDE_QUOTA_HOME — without this it would read (and record into) the OPERATOR'S
# real ~/.claude/manager-accounts. Two accounts, no walls → a healthy sibling exists, so
# the pre-quota Section-A rotation contract still holds.
QHOME="$T/qhome-fire"
mkdir -p "$QHOME/manager-accounts/acct-a" "$QHOME/manager-accounts/acct-b" "$QHOME/.claude-manager"
# A REALISTIC credential fixture. Every live snapshot carries accessToken + refreshToken +
# expiresAt + refreshTokenExpiresAt; a fixture with only accessToken models a shape that does
# not occur, and that gap let the rotation-target usability gate ship untested — a month-old
# snapshot was installed as the active account and logged the operator out (2026-08-10 14:37).
# $1 = token, $2 = hours until the access token expires (default +8, negative = already dead).
_creds() {
  local tok="$1" ah="${2:-8}"
  python3 - "$tok" "$ah" <<'PY'
import json, sys, time
tok, ah = sys.argv[1], float(sys.argv[2])
now = time.time()
print(json.dumps({"claudeAiOauth": {
    "accessToken": tok, "refreshToken": "refresh-" + tok,
    "expiresAt": int((now + ah * 3600) * 1000),
    "refreshTokenExpiresAt": int((now + 700 * 3600) * 1000)}}))
PY
}

_creds "fire-A" > "$QHOME/manager-accounts/acct-a/.credentials.json"
_creds "fire-B" > "$QHOME/manager-accounts/acct-b/.credentials.json"
_creds "fire-B" > "$QHOME/.credentials.json"
printf '{"rateLimits":{"fiveHour":null,"sevenDay":null}}' > "$QHOME/.claude-manager/statusline.json"
export CLAUDE_QUOTA_HOME="$QHOME"

fire() {  # $1=error class  $2=session id  [$3 extra env as K=V]  [+FIRE_EXTRA_ENV]
  printf '{"session_id":"%s","hook_event_name":"StopFailure","error":"%s","cwd":"%s","transcript_path":"%s/nope.jsonl"}' \
    "$2" "$1" "${FIRE_CWD:-$T}" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
      CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_DEBUG=1 CLAUDE_QUOTA_HOME="$QHOME" \
      MESH_ROTATE_CMD="$SHIM/claude_rotate.py" ${3:-MESH_NOOP=1} ${FIRE_EXTRA_ENV:-} \
      bash "$SBHOME/.claude/bin/claude-sound.sh" failure
}

# ── Section A: layer-1 heal-at-death ─────────────────────────────────────────
# A0: rotation is now DEFAULT-ON but HEALTH-AWARE (plan 2026-08-10-plan-1 Phase E — the
# operator's 2026-08-09 adjudication is satisfied: a switch happens ONLY when a sibling is
# genuinely unwalled, so the blind churn that invalidated open windows cannot recur).
# A0a: default (no env) + a healthy sibling → rotation fires.
fire rate_limit sessA0-default
for _w in 1 2 3 4 5 6; do [ -s "$MESH_ROTLOG" ] && break; sleep 0.5; done
[ -s "$MESH_ROTLOG" ] && ok || bad "A0a: default-ON rotation did not fire with a healthy sibling"
# A0b: the explicit escape hatch still suppresses it entirely.
: > "$MESH_ROTLOG"; echo 0 > "$LOCKS/rotation.last"
fire rate_limit sessA0-off CLAUDE_SOUND_AUTOROTATE=0
sleep 1
[ ! -s "$MESH_ROTLOG" ] && ok || bad "A0b: CLAUDE_SOUND_AUTOROTATE=0 did not suppress rotation"
grep -aq "rotation-skipped(opt-in off)" "$SBHOME/.claude/sound-debug.log" && ok || bad "A0b: escape-hatch skip not logged"
: > "$MESH_ROTLOG"; echo 0 > "$LOCKS/rotation.last"
ALL="rate_limit overloaded authentication_failed invalid_grant oauth_org_not_allowed billing_error invalid_request model_not_found server_error max_output_tokens unknown"
for e in $ALL; do
  fire "$e" "sessA-$e" CLAUDE_SOUND_AUTOROTATE=1
  if [ -f "$LOCKS/sessA-$e.errparked" ] && grep -q "^$e " "$LOCKS/sessA-$e.errparked"; then ok
  else bad "A: errparked missing/wrong for $e"; fi
done
# detached shim spawn: allow up to 3s for python startup (review: timing race)
for _w in 1 2 3 4 5 6; do [ -s "$MESH_ROTLOG" ] && break; sleep 0.5; done
rot=$(wc -l < "$MESH_ROTLOG")
# exactly ONE rotation: rate_limit fired first; authentication_failed within the 10-min limiter window
if [ "$rot" = "1" ]; then ok; else bad "A: rotation count=$rot (want 1: limiter box-wide)"; fi
grep -aq "delegated err=rate_limit" "$SBHOME/.claude/sound-debug.log" && ok || bad "A: delegation line missing"
# limiter expiry: age the marker, fire auth again → second rotation
if [ -f "$LOCKS/rotation.last" ]; then
  echo 0 > "$LOCKS/rotation.last"; fire authentication_failed sessA2 CLAUDE_SOUND_AUTOROTATE=1
  [ "$(wc -l < "$MESH_ROTLOG")" = "2" ] && ok || bad "A: aged limiter did not re-rotate"
else
  bad "A: rotation.last marker missing"
fi
# decider clears the marker on a normal Stop run
SB_TR="$T/tr.jsonl"; printf '{"type":"assistant","message":{"content":[{"type":"text","text":"hi"}]}}\n' > "$SB_TR"
printf '{"session_id":"sessA-server_error","transcript_path":"%s","cwd":"%s"}' "$SB_TR" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true
[ ! -f "$LOCKS/sessA-server_error.errparked" ] && ok || bad "A: Stop-path did not clear errparked"
# turn_dead run KEEPS the marker
fire server_error sessA-keep
printf '{"session_id":"sessA-keep","transcript_path":"%s","cwd":"%s"}' "$SB_TR" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_EVENT=StopFailure \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true
[ -f "$LOCKS/sessA-keep.errparked" ] && ok || bad "A: turn_dead run cleared errparked (must keep)"

# ── Section B: revivers (only when the scripts exist) ────────────────────────
if [ -f "$SBHOME/.claude/bin/claude-autoresume.sh" ]; then
  cat > "$SHIM/claude" <<'EOF'
#!/usr/bin/env bash
echo "$(date +%s.%N) norevive=${CLAUDE_SOUND_NO_REVIVE:-unset} headless=${CLAUDE_MESH_HEADLESS:-unset} $*" >> "$MESH_CLAUDELOG"
exit "${MESH_CLAUDE_RC:-0}"
EOF
  chmod +x "$SHIM/claude"
  cat > "$SHIM/curl" <<'EOF'
#!/usr/bin/env bash
[ -f "$MESH_NET" ] && exit 0 || exit 6
EOF
  chmod +x "$SHIM/curl"
  export MESH_CLAUDELOG="$T/claude.log"; : > "$MESH_CLAUDELOG"
  export MESH_NET="$T/net.up"; touch "$MESH_NET"
  AR() { env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" \
        MESH_CLAUDELOG="$MESH_CLAUDELOG" MESH_NET="$MESH_NET" MESH_JITTER_MAX="${MESH_JITTER_MAX:-1}" \
        MESH_BACKOFF_OVERRIDE="${MESH_BACKOFF_OVERRIDE:-0}" MESH_CEILING="${MESH_CEILING:-1800}" MESH_START_SPACING=1 \
        MESH_RETRY_WAIT=1 MESH_INITIAL_GRACE=0 MESH_CLAUDE_RC="${MESH_CLAUDE_RC:-0}" "$@"; }
  # B1: happy path — one resume, one attempt
  printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sB1.errparked"
  AR bash "$SBHOME/.claude/bin/claude-autoresume.sh" sB1 server_error
  grep -q -- "--resume sB1" "$MESH_CLAUDELOG" && ok || bad "B: resume not invoked"
  [ "$(cat "$LOCKS/sB1.attempts" 2>/dev/null)" = "1" ] && ok || bad "B: attempt count != 1"
  # B2: probe DOWN → no attempt; ceiling → NO_REVIVE re-fire (assert THIS session's
  # line + reviving cleared — the old any-line grep was vacuous, review finding)
  rm -f "$MESH_NET"; : > "$MESH_CLAUDELOG"
  printf 'server_error %s\n' "$(( $(date +%s) - 4000 ))" > "$LOCKS/sB2.errparked"
  printf '%s' "$(date +%s)" > "$LOCKS/sB2.reviving"
  MESH_CEILING=1 AR bash "$SBHOME/.claude/bin/claude-autoresume.sh" sB2 server_error
  [ ! -s "$MESH_CLAUDELOG" ] && ok || bad "B: offline attempt consumed"
  grep -aq "sess=sB2" "$SBHOME/.claude/sound-debug.log" && ok || bad "B: ceiling re-fire missing (sB2)"
  [ ! -f "$LOCKS/sB2.reviving" ] && ok || bad "B: ring did not clear .reviving"
  touch "$MESH_NET"
  # B3: human-only exits without resume
  : > "$MESH_CLAUDELOG"
  printf 'billing_error %s\n' "$(date +%s)" > "$LOCKS/sB3.errparked"
  AR bash "$SBHOME/.claude/bin/claude-autoresume.sh" sB3 billing_error
  [ ! -s "$MESH_CLAUDELOG" ] && ok || bad "B: human-only class resumed"
  # B4a: cross-process cap — attempts already 2 → no resume, ring re-fire
  : > "$MESH_CLAUDELOG"; printf 'unknown %s\n' "$(date +%s)" > "$LOCKS/sB4.errparked"
  echo 2 > "$LOCKS/sB4.attempts"
  AR bash "$SBHOME/.claude/bin/claude-autoresume.sh" sB4 unknown
  [ ! -s "$MESH_CLAUDELOG" ] && ok || bad "B: cap 2 not enforced"
  grep -aq "sess=sB4" "$SBHOME/.claude/sound-debug.log" && ok || bad "B: cap ring re-fire missing"
  # B4b: rc≠0 — two in-process attempts then ring (the untested leg, review finding)
  : > "$MESH_CLAUDELOG"; printf 'unknown %s\n' "$(date +%s)" > "$LOCKS/sBrc.errparked"
  MESH_CLAUDE_RC=1 AR bash "$SBHOME/.claude/bin/claude-autoresume.sh" sBrc unknown
  [ "$(grep -c -- '--resume sBrc' "$MESH_CLAUDELOG")" = "2" ] && ok || bad "B: rc-fail attempts != 2"
  [ "$(cat "$LOCKS/sBrc.attempts" 2>/dev/null)" = "2" ] && ok || bad "B: rc-fail counter != 2"
  grep -aq "sess=sBrc" "$SBHOME/.claude/sound-debug.log" && ok || bad "B: rc-fail final ring missing"
  # B6: cleared marker aborts (never a second writer on a survived session)
  : > "$MESH_CLAUDELOG"; rm -f "$LOCKS/sB6.errparked"
  printf '%s' "$(date +%s)" > "$LOCKS/sB6.reviving"
  AR bash "$SBHOME/.claude/bin/claude-autoresume.sh" sB6 server_error
  [ ! -s "$MESH_CLAUDELOG" ] && ok || bad "B: resumed despite cleared marker"
  [ ! -f "$LOCKS/sB6.reviving" ] && ok || bad "B: abort did not clear .reviving"
  # B5: storm — 5 revivers; starts serialized second-distinct (starts.log is
  # written inside the mutex critical section — deterministic, review finding)
  : > "$MESH_CLAUDELOG"; rm -f "$LOCKS/starts.log"
  for i in 1 2 3 4 5; do printf 'unknown %s\n' "$(date +%s)" > "$LOCKS/sS$i.errparked"; done
  for i in 1 2 3 4 5; do MESH_JITTER_MAX=3 AR bash "$SBHOME/.claude/bin/claude-autoresume.sh" "sS$i" unknown & done
  wait
  [ "$(wc -l < "$MESH_CLAUDELOG")" = "5" ] && ok || bad "B: storm resumes != 5"
  # Invariant = the mutex SERIALIZED them, measured as elapsed SPAN, not as "every second
  # distinct": under real box load (a sibling batch pipeline) two starts can legitimately
  # land in one second while still being mutex-ordered — that made this fixture flaky.
  span=$(( $(sort -n "$LOCKS/starts.log" | tail -1) - $(sort -n "$LOCKS/starts.log" | head -1) ))
  [ "$span" -ge 3 ] && ok || bad "B: 5 starts spanned ${span}s — mutex did not serialize them"
  # B7: decider stays SILENT while a fresh .reviving is pending (ring ⇒ truly dead)
  fire server_error sB7
  printf '%s' "$(date +%s)" > "$LOCKS/sB7.reviving"
  printf '{"session_id":"sB7","transcript_path":"%s","cwd":"%s"}' "$SB_TR" "$T" \
    | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
      CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_EVENT=StopFailure CLAUDE_SOUND_SETTLE=0 \
      python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true
  grep -aq "busy-reviving.*sB7\|sB7.*reviving" "$SBHOME/.claude/sound-debug.log" \
    || grep -aq "reviver pending" "$SBHOME/.claude/sound-debug.log" \
    && ok || bad "B: decider rang despite pending reviver"
  # B8: the REAL spawn gate — fire through claude-sound.sh with AUTORESUME=1 →
  # reviver spawned (was never tested; the gate could break invisibly)
  : > "$MESH_CLAUDELOG"
  FIRE_EXTRA_ENV="MESH_CLAUDELOG=$MESH_CLAUDELOG MESH_NET=$MESH_NET MESH_JITTER_MAX=1 MESH_BACKOFF_OVERRIDE=0 MESH_START_SPACING=1 MESH_RETRY_WAIT=1 MESH_INITIAL_GRACE=0" \
    fire unknown sB8 CLAUDE_SOUND_AUTORESUME=1
  for _w in $(seq 1 16); do grep -q -- "--resume sB8" "$MESH_CLAUDELOG" 2>/dev/null && break; sleep 0.5; done
  grep -q -- "--resume sB8" "$MESH_CLAUDELOG" && ok || bad "B8: spawn gate did not spawn reviver"
  # B8b: the reviver's claude child must carry NO_REVIVE=1 (its own death must not
  # spawn a second writer) and the headless marker (its SessionStart must not arm)
  grep -q "norevive=1 .*--resume sB8" "$MESH_CLAUDELOG" && ok || bad "B8b: child lacks NO_REVIVE=1"
  grep -q "headless=1 .*--resume sB8" "$MESH_CLAUDELOG" && ok || bad "B8b: child lacks CLAUDE_MESH_HEADLESS=1"
  # B9: NO_REVIVE=1 suppresses the spawn (the ring re-fire must not re-spawn)
  : > "$MESH_CLAUDELOG"
  FIRE_EXTRA_ENV="MESH_CLAUDELOG=$MESH_CLAUDELOG MESH_NET=$MESH_NET MESH_JITTER_MAX=1 MESH_BACKOFF_OVERRIDE=0 MESH_START_SPACING=1 MESH_RETRY_WAIT=1 MESH_INITIAL_GRACE=0 CLAUDE_SOUND_NO_REVIVE=1" \
    fire unknown sB9 CLAUDE_SOUND_AUTORESUME=1
  sleep 3
  grep -q -- "--resume sB9" "$MESH_CLAUDELOG" 2>/dev/null \
    && bad "B9: NO_REVIVE did not suppress spawn" || ok
  # B12: a FRESH .reviving suppresses a second spawn (a reviver is already
  # pending — a concurrent second writer must never be spawned; review finding)
  : > "$MESH_CLAUDELOG"
  printf '%s' "$(date +%s)" > "$LOCKS/sB12.reviving"
  FIRE_EXTRA_ENV="MESH_CLAUDELOG=$MESH_CLAUDELOG MESH_NET=$MESH_NET MESH_JITTER_MAX=1 MESH_BACKOFF_OVERRIDE=0 MESH_START_SPACING=1 MESH_RETRY_WAIT=1 MESH_INITIAL_GRACE=0" \
    fire unknown sB12 CLAUDE_SOUND_AUTORESUME=1
  sleep 3
  grep -q -- "--resume sB12" "$MESH_CLAUDELOG" 2>/dev/null \
    && bad "B12: fresh .reviving did not suppress second spawn" || ok
  # B10: F8 re-checked before EACH attempt — marker cleared mid-backoff aborts
  # (the session survived; the reviver must never barge into an alive session)
  : > "$MESH_CLAUDELOG"
  printf 'unknown %s\n' "$(date +%s)" > "$LOCKS/sB10.errparked"
  printf '%s' "$(date +%s)" > "$LOCKS/sB10.reviving"
  MESH_BACKOFF_OVERRIDE=3 AR bash "$SBHOME/.claude/bin/claude-autoresume.sh" sB10 unknown &
  b10pid=$!
  sleep 1; rm -f "$LOCKS/sB10.errparked"
  wait "$b10pid"
  [ ! -s "$MESH_CLAUDELOG" ] && ok || bad "B10: reviver barged in after mid-backoff survival"
  [ ! -f "$LOCKS/sB10.reviving" ] && ok || bad "B10: late abort did not clear .reviving"
  # B11: cap short-circuits BEFORE the backoff sleep (no dead wait when unwinnable)
  : > "$MESH_CLAUDELOG"; printf 'unknown %s\n' "$(date +%s)" > "$LOCKS/sB11.errparked"
  echo 2 > "$LOCKS/sB11.attempts"
  b11_t0=$SECONDS
  MESH_BACKOFF_OVERRIDE=6 MESH_JITTER_MAX=0 AR bash "$SBHOME/.claude/bin/claude-autoresume.sh" sB11 unknown
  [ $(( SECONDS - b11_t0 )) -lt 5 ] && ok || bad "B11: capped reviver still slept the backoff"
fi
if [ -f "$SBHOME/.claude/bin/claude-selfwatch.sh" ]; then
  SW() { env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" \
        MESH_NET="$MESH_NET" MESH_JITTER_MAX=1 MESH_BACKOFF_OVERRIDE="${MESH_BACKOFF_OVERRIDE:-0}" MESH_POLL=1 "$@"; }
  # W1: real-world shape — armed FIRST, death arrives later → exactly one RESUME,
  # and the fire CONSUMES the marker (one wake per death record)
  SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW1 > "$T/w1.out" &
  w1pid=$!
  sleep 2; printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sW1.errparked"
  wait "$w1pid"
  [ "$(grep -c '^RESUME:' "$T/w1.out")" = "1" ] && ok || bad "W1: RESUME count wrong: $(cat "$T/w1.out")"
  [ ! -f "$LOCKS/sW1.errparked" ] && ok || bad "W1: fire did not consume the marker"
  # W2: STALE marker at arm time (a healed pre-arm death) — consumed silently,
  # never fired into the live session that just armed the watch
  printf 'invalid_request %s\n' "$(( $(date +%s) - 600 ))" > "$LOCKS/sW2.errparked"
  SW timeout 8 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW2 > "$T/w2.out"
  w2rc=$?
  grep -q '^RESUME:' "$T/w2.out" && bad "W2: fired on a stale pre-arm marker" || ok
  [ ! -f "$LOCKS/sW2.errparked" ] && ok || bad "W2: stale marker not consumed at arm"
  # W-streak (W-5279e834): a flapping restore — the wake fires only after MESH_UP_STREAK (3)
  # CONSECUTIVE answers; one failed probe between answers restarts the count. The sequence
  # shim answers one line per probe (up/down), then up for good once the file is empty: the
  # RESUME may only appear after the whole sequence was consumed (the one-shot gate fired on
  # the first `up`, into a network that dropped again)
  mkdir -p "$T/seqshim"
  cat > "$T/seqshim/curl" <<'EOF'
#!/usr/bin/env bash
seq="$MESH_NET_SEQ"; first=$(head -n1 "$seq" 2>/dev/null); sed -i '1d' "$seq" 2>/dev/null
[ "$first" = "down" ] && exit 6 || exit 0
EOF
  chmod +x "$T/seqshim/curl"
  # up,down,up,down,up,up,up: a CUMULATIVE count reaches 3 at the fifth probe (two left unread);
  # only a consecutive count needs all seven (review W-5279e834: up,down,up,up could not tell them apart)
  printf 'up\ndown\nup\ndown\nup\nup\nup\n' > "$T/ws.seq"
  env HOME="$SBHOME" PATH="$T/seqshim:$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" \
      CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" MESH_NET_SEQ="$T/ws.seq" \
      MESH_JITTER_MAX=0 MESH_BACKOFF_OVERRIDE=0 MESH_POLL=1 MESH_UP_STREAK=3 \
      timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sWS > "$T/ws.out" &
  wspid=$!
  sleep 2; printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sWS.errparked"
  for _ in $(seq 1 25); do grep -q '^RESUME:' "$T/ws.out" && break; sleep 1; done
  left=$(grep -c . "$T/ws.seq" 2>/dev/null); left=${left:-0}  # grep -c prints 0 AND exits 1 on none
  kill "$wspid" 2>/dev/null; wait "$wspid" 2>/dev/null
  grep -q '^RESUME:' "$T/ws.out" && ok || bad "W-streak: never fired: $(cat "$T/ws.out")"
  [ "$left" = "0" ] && ok || bad "W-streak: fired with $left probe(s) of the flapping sequence unread"
  # W-fresh (W-5279e834): while the gate waits on a dead network, the death record is kept
  # fresh, so the decider's 2-h lock-dir prune cannot take it during a long outage
  printf 'down\ndown\ndown\ndown\ndown\ndown\ndown\ndown\n' > "$T/wf.seq"
  env HOME="$SBHOME" PATH="$T/seqshim:$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" \
      CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" MESH_NET_SEQ="$T/wf.seq" \
      MESH_JITTER_MAX=0 MESH_BACKOFF_OVERRIDE=0 MESH_POLL=1 MESH_UP_STREAK=3 \
      timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sWF > "$T/wf.out" &
  wfpid=$!
  sleep 2; printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sWF.errparked"
  sleep 2; touch -d '3 hours ago' "$LOCKS/sWF.errparked"
  sleep 3
  wf_age=$(( $(date +%s) - $(stat -c %Y "$LOCKS/sWF.errparked" 2>/dev/null || echo 0) ))
  kill "$wfpid" 2>/dev/null; wait "$wfpid" 2>/dev/null
  [ "$wf_age" -lt 60 ] && ok || bad "W-fresh: the death record aged ${wf_age}s while the gate waited"
  # W-clear (W-5279e834): a record the decider CLEARS mid-gate (the session revived) stays
  # cleared — the freshness touch never re-creates it — and no RESUME fires into the live session
  printf 'down\ndown\ndown\ndown\n' > "$T/wc.seq"
  env HOME="$SBHOME" PATH="$T/seqshim:$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" \
      CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" MESH_NET_SEQ="$T/wc.seq" \
      MESH_JITTER_MAX=0 MESH_BACKOFF_OVERRIDE=0 MESH_POLL=1 MESH_UP_STREAK=3 \
      timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sWC > "$T/wc.out" &
  wcpid=$!
  sleep 2; printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sWC.errparked"
  sleep 2; rm -f "$LOCKS/sWC.errparked"
  sleep 8
  kill "$wcpid" 2>/dev/null; wait "$wcpid" 2>/dev/null
  [ ! -f "$LOCKS/sWC.errparked" ] && ok || bad "W-clear: the gate re-created a record the decider cleared"
  grep -q '^RESUME:' "$T/wc.out" && bad "W-clear: fired a RESUME after the record was cleared" || ok
  # W-badstreak (W-5279e834): a garbage MESH_UP_STREAK falls back to 3 — never a gate that runs
  # no probe at all (fail-open into a dead network); `00` and a huge value too (closing-pass findings)
  for wbv in x 00 99999999999999999999 ٣; do  # ٣: a non-ASCII digit a locale glob range admits
    printf 'down\ndown\ndown\ndown\ndown\ndown\ndown\ndown\n' > "$T/wb.seq"
    env HOME="$SBHOME" PATH="$T/seqshim:$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" \
        CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" MESH_NET_SEQ="$T/wb.seq" \
        MESH_JITTER_MAX=0 MESH_BACKOFF_OVERRIDE=0 MESH_POLL=1 MESH_UP_STREAK="$wbv" LC_ALL=en_US.utf8 \
        timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sWB > "$T/wb.out" 2>&1 &
    wbpid=$!
    sleep 2; printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sWB.errparked"
    sleep 4
    kill "$wbpid" 2>/dev/null; wait "$wbpid" 2>/dev/null
    grep -q '^RESUME:' "$T/wb.out" && bad "W-badstreak: streak '$wbv' fired with the network down" || ok
    rm -f "$LOCKS/sWB.errparked"
  done
  # W-slicefresh (W-5279e834): a long per-class backoff (a quota wait) keeps the death record
  # fresh too — the 2-h prune cannot take it before the wake
  env HOME="$SBHOME" PATH="$T/seqshim:$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" \
      CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" MESH_NET_SEQ="$T/none.seq" \
      MESH_JITTER_MAX=0 MESH_BACKOFF_OVERRIDE=20 MESH_SLICE_MAX=1 MESH_POLL=1 \
      timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sWL > "$T/wl.out" &
  wlpid=$!
  sleep 2; printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sWL.errparked"
  sleep 2; touch -d '3 hours ago' "$LOCKS/sWL.errparked"
  sleep 3
  wl_age=$(( $(date +%s) - $(stat -c %Y "$LOCKS/sWL.errparked" 2>/dev/null || echo 0) ))
  kill "$wlpid" 2>/dev/null; wait "$wlpid" 2>/dev/null
  [ "$wl_age" -lt 60 ] && ok || bad "W-slicefresh: the death record aged ${wl_age}s during the backoff"
  rm -f "$LOCKS/sWF.errparked" "$LOCKS/sWS.errparked" "$LOCKS/sWC.errparked" "$LOCKS/sWB.errparked" "$LOCKS/sWL.errparked"
  # W4: marker cleared DURING the waits (decider busy-clear: the death was ruled
  # non-terminal) — the watch must NOT fire, and must keep watching for a real
  # future death (mirror of the autoresume per-attempt survival re-check).
  # Deterministic window: 4s backoff, marker removed 2s in.
  # (bounded by the watch's own timeout + plain wait — `kill $!` only killed the
  # job-wrapper subshell and orphaned the timeout/selfwatch tree; review finding)
  MESH_BACKOFF_OVERRIDE=4 SW timeout 12 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW4 > "$T/w4.out" &
  w4pid=$!
  sleep 1
  printf 'rate_limit %s\n' "$(date +%s)" > "$LOCKS/sW4.errparked"
  sleep 2; rm -f "$LOCKS/sW4.errparked"                             # healed mid-backoff
  sleep 5
  grep -q '^RESUME:' "$T/w4.out" && bad "W4: fired after mid-wait heal" || ok
  wait "$w4pid" 2>/dev/null
  # W5: human-only classes (auth/billing/org/model) — "the cause has been healed"
  # is FALSE by construction (rotation opt-in is off; nothing heals an account
  # wall). The watch consumes the record silently (the death already rang +
  # Telegramed) and keeps watching — mirror of the autoresume human-only filter.
  SW timeout 8 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW5 > "$T/w5.out" &
  w5pid=$!
  sleep 1
  printf 'authentication_failed %s\n' "$(date +%s)" > "$LOCKS/sW5.errparked"
  sleep 4
  grep -q '^RESUME:' "$T/w5.out" && bad "W5: fired for a human-only class" || ok
  [ ! -f "$LOCKS/sW5.errparked" ] && ok || bad "W5: human-only record not consumed"
  wait "$w5pid" 2>/dev/null
  # W3: network-shaped consistency — a death while OFFLINE must not fire until the
  # network heals, for EVERY class (mirror of the autoresume per-attempt gate)
  rm -f "$MESH_NET"
  SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW3 > "$T/w3.out" &
  w3pid=$!
  sleep 1; printf 'rate_limit %s\n' "$(date +%s)" > "$LOCKS/sW3.errparked"
  sleep 4
  grep -q '^RESUME:' "$T/w3.out" && bad "W3: fired into a dead network (rate_limit ungated)" || ok
  touch "$MESH_NET"
  wait "$w3pid"
  grep -q '^RESUME:' "$T/w3.out" && ok || bad "W3: no RESUME after network healed"
  # W6 (2026-09-03): a STANDING watch — the second death of a session, with NO re-arm in
  # between, is woken too (the one-wake-then-exit shape left it to a human "proceed";
  # 8 of 18 /opt sessions in one 529 storm)
  SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW6 > "$T/w6.out" &
  w6pid=$!
  sleep 2; printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sW6.errparked"
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f "$LOCKS/sW6.errparked" ] || break; sleep 1; done
  sleep 2; printf 'overloaded %s\n' "$(date +%s)" > "$LOCKS/sW6.errparked"
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f "$LOCKS/sW6.errparked" ] || break; sleep 1; done
  sleep 1
  [ "$(grep -c '^RESUME:' "$T/w6.out")" = "2" ] && ok || bad "W6: standing watch woke $(grep -c '^RESUME:' "$T/w6.out") of 2 deaths: $(cat "$T/w6.out")"
  kill "$w6pid" 2>/dev/null; wait "$w6pid" 2>/dev/null
  # W7: ONE watch per session — a duplicate arm exits at once and never double-fires
  SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW7 > "$T/w7.out" &
  w7pid=$!
  sleep 1
  SW timeout 10 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW7 > "$T/w7b.out"
  grep -q 'already armed' "$T/w7b.out" && ok || bad "W7: duplicate arm did not exit at once: $(cat "$T/w7b.out")"
  printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sW7.errparked"
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f "$LOCKS/sW7.errparked" ] || break; sleep 1; done
  sleep 1
  [ "$(cat "$T/w7.out" "$T/w7b.out" | grep -c '^RESUME:')" = "1" ] && ok || bad "W7b: duplicate arm double-fired"
  kill "$w7pid" 2>/dev/null; wait "$w7pid" 2>/dev/null
  # W10 (2026-09-07, plan 2026-09-07-plan-1-relief-wake): the RELIEF WAKE — a `.holdlifted` file
  # (the lift epoch) beside the death marker wakes the pane with ONE "LIFTED at <lift HH:MM>" line
  # naming where the session left off, consumes the file, and the watch stays armed (a later death
  # still wakes). The printed minute is the LIFT's (the file's epoch), never the wake's.
  SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW10 > "$T/w10.out" &
  w10pid=$!
  sleep 2; LIFT=$(( $(date +%s) - 120 )); printf '%s\n' "$LIFT" > "$LOCKS/sW10.holdlifted"
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f "$LOCKS/sW10.holdlifted" ] || break; sleep 1; done
  sleep 1
  [ "$(grep -c '^RESUME: the fleet-quota hold LIFTED at' "$T/w10.out")" = "1" ] && ok || bad "W10: lift did not wake exactly once: $(cat "$T/w10.out")"
  grep -q "LIFTED at $(date -d @"$LIFT" +%H:%M)" "$T/w10.out" && ok || bad "W10: the line does not carry the LIFT minute $(date -d @"$LIFT" +%H:%M): $(cat "$T/w10.out")"
  if [ "$(date -d @"$LIFT" +%H:%M)" != "$(date +%H:%M)" ]; then
    grep -q "LIFTED at $(date +%H:%M)" "$T/w10.out" && bad "W10: the line carries the WAKE minute, not the lift's" || ok
  else ok; fi
  grep -q 'thread_anchor.py line' "$T/w10.out" && grep -q 'closed BLOCKED' "$T/w10.out" && ok || bad "W10: the line does not say where the session left off: $(cat "$T/w10.out")"
  [ ! -f "$LOCKS/sW10.holdlifted" ] && ok || bad "W10: the lift file was not consumed"
  printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sW10.errparked"
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f "$LOCKS/sW10.errparked" ] || break; sleep 1; done
  sleep 1
  [ "$(grep -c '^RESUME:' "$T/w10.out")" = "2" ] && ok || bad "W10: the watch did not stay armed after the lift: $(grep -c '^RESUME:' "$T/w10.out") of 2"
  kill "$w10pid" 2>/dev/null; wait "$w10pid" 2>/dev/null
  # W10e (W-83a8ee68): the battery hold's lift names itself (`<epoch> battery`) — the line says the
  # BATTERY hold lifted on mains power, still carries the lift minute and where the session left off
  SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW10e > "$T/w10e.out" &
  w10epid=$!
  sleep 2; LIFT=$(( $(date +%s) - 120 )); printf '%s battery\n' "$LIFT" > "$LOCKS/sW10e.holdlifted"
  for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f "$LOCKS/sW10e.holdlifted" ] || break; sleep 1; done
  sleep 1
  kill "$w10epid" 2>/dev/null; wait "$w10epid" 2>/dev/null
  [ "$(grep -c "^RESUME: the battery hold LIFTED at $(date -d @"$LIFT" +%H:%M) (mains power is back)" "$T/w10e.out")" = "1" ] && ok || bad "W10e: the battery lift did not say so once: $(cat "$T/w10e.out")"
  grep -q 'fleet-quota' "$T/w10e.out" && bad "W10e: a battery lift named the quota hold" || ok
  grep -q 'thread_anchor.py line --session sW10e' "$T/w10e.out" && ok || bad "W10e: the line lost where the session left off: $(cat "$T/w10e.out")"
  # W10b: a lift file written BEFORE the arm is pre-arm history — deleted at arm, never fired
  printf '%s\n' "$(date +%s)" > "$LOCKS/sW10b.holdlifted"
  SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW10b > "$T/w10b.out" &
  w10bpid=$!
  sleep 5
  [ "$(grep -c '^RESUME:' "$T/w10b.out")" = "0" ] && ok || bad "W10b: a pre-arm lift fired: $(cat "$T/w10b.out")"
  [ ! -f "$LOCKS/sW10b.holdlifted" ] && ok || bad "W10b: the pre-arm lift file survived the arm"
  kill "$w10bpid" 2>/dev/null; wait "$w10bpid" 2>/dev/null
  # W10c: a death marker AND a lift file in the same second — two RESUME lines, the death's FIRST,
  # both files consumed
  SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW10c > "$T/w10c.out" &
  w10cpid=$!
  sleep 2; printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sW10c.errparked"; printf '%s\n' "$(date +%s)" > "$LOCKS/sW10c.holdlifted"
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do [ -f "$LOCKS/sW10c.errparked" ] || [ -f "$LOCKS/sW10c.holdlifted" ] || break; sleep 1; done
  sleep 1
  [ "$(grep -c '^RESUME:' "$T/w10c.out")" = "2" ] && ok || bad "W10c: expected 2 RESUME lines, got $(grep -c '^RESUME:' "$T/w10c.out"): $(cat "$T/w10c.out")"
  [ "$(grep '^RESUME:' "$T/w10c.out" | head -1 | grep -c 'died on server_error')" = "1" ] && ok || bad "W10c: the death did not wake FIRST: $(cat "$T/w10c.out")"
  [ ! -f "$LOCKS/sW10c.errparked" ] && [ ! -f "$LOCKS/sW10c.holdlifted" ] && ok || bad "W10c: a file was not consumed"
  kill "$w10cpid" 2>/dev/null; wait "$w10cpid" 2>/dev/null
  # W10d: an OFFLINE lift (W3/W9's shape) — the gate holds, the watch stays alive, and the LIFTED
  # line arrives once the network returns
  rm -f "$MESH_NET"
  SW timeout 30 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW10d > "$T/w10d.out" &
  w10dpid=$!
  sleep 2; printf '%s\n' "$(date +%s)" > "$LOCKS/sW10d.holdlifted"
  sleep 5
  [ "$(grep -c '^RESUME:' "$T/w10d.out")" = "0" ] && ok || bad "W10d: an offline lift fired: $(cat "$T/w10d.out")"
  kill -0 "$w10dpid" 2>/dev/null && ok || bad "W10d: the watch died on an offline lift"
  touch "$MESH_NET"
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do [ -f "$LOCKS/sW10d.holdlifted" ] || break; sleep 1; done
  sleep 1
  [ "$(grep -c '^RESUME: the fleet-quota hold LIFTED at' "$T/w10d.out")" = "1" ] && ok || bad "W10d: the lift did not fire once the network returned: $(cat "$T/w10d.out")"
  kill "$w10dpid" 2>/dev/null; wait "$w10dpid" 2>/dev/null
  # W11 (2026-09-07, heavy review R1): a watch whose LOCK FILE vanishes (the Stop decider's 2h mtime
  # prune, or a manual rm) must EXIT with one line — an orphan holding a deleted inode is invisible
  # to the tick's armed census and steals the next death marker from the re-armed watch.
  SW timeout 20 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW11 > "$T/w11.out" &
  w11pid=$!
  sleep 2; rm -f "$LOCKS/sW11.selfwatch.lock"
  for _ in 1 2 3 4 5 6; do kill -0 "$w11pid" 2>/dev/null || break; sleep 1; done
  ! kill -0 "$w11pid" 2>/dev/null && ok || bad "W11: the watch kept polling after its lock file vanished"
  [ "$(grep -c 'lock file vanished' "$T/w11.out")" = "1" ] && ok || bad "W11: no vanished-lock line: $(cat "$T/w11.out")"
  [ "$(grep -c '^RESUME:' "$T/w11.out")" = "0" ] && ok || bad "W11: the orphan fired a RESUME"
  kill "$w11pid" 2>/dev/null; wait "$w11pid" 2>/dev/null
  # W9 (2026-09-03): the offline CEILING restarts the cycle instead of ending the watch — the
  # wake fires the moment the network returns, however long it was gone (the old watch exited
  # at the ceiling and the pane was never woken)
  rm -f "$MESH_NET"
  MESH_CEILING=2 SW timeout 20 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sW9 > "$T/w9.out" &
  sleep 1; printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sW9.errparked"
  sleep 6                                                            # three ceilings pass offline
  grep -q '^RESUME:' "$T/w9.out" && bad "W9: fired into a dead network" || ok
  touch "$MESH_NET"
  for _ in $(seq 1 10); do grep -q '^RESUME:' "$T/w9.out" && break; sleep 1; done
  grep -q '^RESUME:' "$T/w9.out" && ok || bad "W9: watch ended at the offline ceiling — no RESUME after the network returned: $(cat "$T/w9.out")"
  wait  # the standing watch ends at its own timeout; never leave it alive into the next fixture
  # (the rate_limit re-ask fixture lives in Section BQ as BQ10: it needs the quota shim, which
  # the harness creates there)
fi

# ── Section C: telegram on ringing /opt parks ────────────────────────────────
if grep -q "MESH_NOTIFY_CMD\|apprise" "$SBHOME/.claude/bin/claude-sound.sh" 2>/dev/null; then
  cat > "$SHIM/mesh-notify" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$MESH_NOTELOG"
EOF
  chmod +x "$SHIM/mesh-notify"
  export MESH_NOTELOG="$T/note.log"; : > "$MESH_NOTELOG"
  # a ring is forced by decider-MISSING leg: remove the decider copy in a 2nd sandbox
  SB2="$T/home2"; mkdir -p "$SB2/.claude/bin"; cp "$SBHOME/.claude/bin/claude-sound.sh" "$SB2/.claude/bin/"
  ring() { printf '{"session_id":"%s","hook_event_name":"StopFailure","error":"server_error","cwd":"%s"}' "$1" "$2" \
    | env HOME="$SB2" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" CLAUDE_SOUND_LOCKDIR="$LOCKS" \
      MESH_NOTIFY_CMD="$SHIM/mesh-notify" MESH_NOTELOG="$MESH_NOTELOG" \
      bash "$SB2/.claude/bin/claude-sound.sh" failure; }
  _settle() { for _w in 1 2 3 4 5 6; do [ "$(wc -l < "$MESH_NOTELOG")" = "$1" ] && return 0; sleep 0.5; done; return 1; }
  ring sC1 /opt/someproj
  _settle 1 && ok || bad "C: /opt ring did not notify once ($(wc -l < "$MESH_NOTELOG"))"
  ring sC1 /opt/someproj
  sleep 1; [ "$(wc -l < "$MESH_NOTELOG")" = "1" ] && ok || bad "C: 30-min suppress failed"
  ring sC2 "$T"
  sleep 1; [ "$(wc -l < "$MESH_NOTELOG")" = "1" ] && ok || bad "C: non-/opt cwd notified"
fi

# ── Section D: waker-loss timer bridge (shape 3 — operator-observed) ─────────
# A Stop with a PENDING background task parks busy-SILENT and arms a re-check;
# when the task goes stale (waker lost), the re-check rings + writes waker_lost.
TS_OLD=$(python3 -c "import time;print(time.time()-7200)")   # dispatch 2h ago -> already past stale bound at recheck
DTR="$T/wl.jsonl"
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"wltask1"},"message":{"content":[]}}\n' \
  "$(date -u -d @${TS_OLD%.*} +%Y-%m-%dT%H:%M:%S.000Z)" > "$DTR"
printf '{"type":"assistant","message":{"content":[{"type":"text","text":"working"}]}}\n' >> "$DTR"
# fresh-dispatch variant: pending NOW -> busy-task + recheck armed
TS_NOW=$(date -u +%Y-%m-%dT%H:%M:%S.000Z)
FTR="$T/wl2.jsonl"
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"wltask2"},"message":{"content":[]}}\n' "$TS_NOW" > "$FTR"
printf '{"type":"assistant","message":{"content":[{"type":"text","text":"working"}]}}\n' >> "$FTR"
DEC() { env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
      CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_SETTLE=0 CLAUDE_SOUND_GRACE=1 CLAUDE_SOUND_RECHECK_DELAY=2 "$@"; }
printf '{"session_id":"sWL","transcript_path":"%s","cwd":"%s"}' "$FTR" "$T" \
  | DEC python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true
grep -aq "busy-task" "$SBHOME/.claude/sound-debug.log" && ok || bad "D: pending task not busy-silent"
grep -aq "recheck-armed" "$SBHOME/.claude/sound-debug.log" && ok || bad "D: recheck not armed"
[ -f "$LOCKS/sWL.recheck-busy-task" ] && ok || bad "D: class-scoped recheck dedup marker missing"
# the sleeper (2s) re-runs the decider; make the task STALE for the re-check by
# rewriting the dispatch timestamp into the past, then wait for the sleeper.
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"wltask2"},"message":{"content":[]}}\n' \
  "$(date -u -d @$(( $(date +%s) - 7200 )) +%Y-%m-%dT%H:%M:%S.000Z)" > "$FTR"
printf '{"type":"assistant","message":{"content":[{"type":"text","text":"working"}]}}\n' >> "$FTR"
for _w in $(seq 1 18); do [ -f "$LOCKS/sWL.errparked" ] && break; sleep 1; done
grep -q "^waker_lost " "$LOCKS/sWL.errparked" 2>/dev/null && ok || bad "D: waker_lost marker not written by recheck"
grep -aq "waker lost" "$SBHOME/.claude/sound-debug.log" && ok || bad "D: recheck ring not logged"

# D2: a NON-terminal StopFailure (busy verdict — a live waker exists) must CLEAR
# the death record: the waker revives the session, and a stale marker would make
# an armed self-watch fire a spurious RESUME into the revived session.
FTR2="$T/wl3.jsonl"
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"wltask3"},"message":{"content":[]}}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" > "$FTR2"
printf '{"type":"assistant","message":{"content":[{"type":"text","text":"working"}]}}\n' >> "$FTR2"
printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sD2.errparked"   # direct seed: fire() would
[ -f "$LOCKS/sD2.errparked" ] || bad "D2: precondition failed (no marker)"  # pollute the log with an async no-transcript decider
printf '{"session_id":"sD2","transcript_path":"%s","cwd":"%s"}' "$FTR2" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_EVENT=StopFailure CLAUDE_SOUND_SETTLE=0 CLAUDE_SOUND_GRACE=1 \
    CLAUDE_SOUND_RECHECK_DELAY=600 \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true
[ ! -f "$LOCKS/sD2.errparked" ] && ok || bad "D2: busy turn_dead kept the death record"

# D4: a recheck-detected waker-loss in an /opt project escalates to Telegram with
# the TRUE class (waker_lost), not the original death's class
cat > "$SHIM/mesh-notify2" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$MESH_NOTELOG2"
EOF
chmod +x "$SHIM/mesh-notify2"
export MESH_NOTELOG2="$T/note2.log"; : > "$MESH_NOTELOG2"
FTR3="$T/wl4.jsonl"
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"wltask4"},"message":{"content":[]}}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" > "$FTR3"
printf '{"type":"assistant","message":{"content":[{"type":"text","text":"working"}]}}\n' >> "$FTR3"
printf '{"session_id":"sD4","transcript_path":"%s","cwd":"/opt/mesh-test-fake"}' "$FTR3" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_SETTLE=0 CLAUDE_SOUND_GRACE=1 CLAUDE_SOUND_RECHECK_DELAY=2 \
    CLAUDE_SOUND_PARK_ERR=rate_limit MESH_NOTIFY_CMD="$SHIM/mesh-notify2" MESH_NOTELOG2="$MESH_NOTELOG2" \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"wltask4"},"message":{"content":[]}}\n' \
  "$(date -u -d @$(( $(date +%s) - 7200 )) +%Y-%m-%dT%H:%M:%S.000Z)" > "$FTR3"
printf '{"type":"assistant","message":{"content":[{"type":"text","text":"working"}]}}\n' >> "$FTR3"
for _w in $(seq 1 18); do [ -s "$MESH_NOTELOG2" ] && break; sleep 1; done
grep -q "waker_lost" "$MESH_NOTELOG2" 2>/dev/null && ok || bad "D4: Telegram missing/wrong class: $(cat "$MESH_NOTELOG2" 2>/dev/null)"

# D5: two DISTINCT deaths at the same transcript byte size both ring (the second
# death is a new incident — the dup-park guard must not swallow an error park).
# Markers seeded directly: fire()'s async decider would pollute the PARKED count.
D5DEC() { printf '{"session_id":"sD5","transcript_path":"%s","cwd":"%s"}' "$SB_TR" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_EVENT=StopFailure CLAUDE_SOUND_SETTLE=0 CLAUDE_SOUND_GRACE=1 \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true; }
printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sD5.errparked"
D5DEC
sleep 1
printf 'server_error %s\n' "$(date +%s)" > "$LOCKS/sD5.errparked"
D5DEC
d5=$(grep -a "sess=sD5" "$SBHOME/.claude/sound-debug.log" | grep -ac "PARKED")
[ "$d5" = "2" ] && ok || bad "D5: distinct same-size deaths rang $d5 times (want 2)"

# D6: TWO independently-lost wakers on a frozen transcript — the second recheck
# ring must NOT be swallowed by the dup-park guard (identity-scoped rung), and
# the death record must survive a duplicate re-announcement (recheck runs never
# entry-clear). Direct recheck-context injection (the sleeper's env shape).
D6TR="$T/wl6.jsonl"
TS_OLD6=$(date -u -d @$(( $(date +%s) - 7200 )) +%Y-%m-%dT%H:%M:%S.000Z)
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"t1lost"},"message":{"content":[]}}\n' "$TS_OLD6" > "$D6TR"
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"t2lost"},"message":{"content":[]}}\n' "$TS_OLD6" >> "$D6TR"
printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"end_turn","content":[{"type":"text","text":"working"}]}}\n' >> "$D6TR"
D6DEC() { printf '{"session_id":"sD6","transcript_path":"%s","cwd":"%s"}' "$D6TR" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_SETTLE=0 CLAUDE_SOUND_GRACE=1 \
    CLAUDE_SOUND_RECHECK=1 CLAUDE_RECHECK_WAKER="$1" \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true; }
D6DEC t1lost
sleep 1
D6DEC t2lost
d6=$(grep -a "sess=sD6" "$SBHOME/.claude/sound-debug.log" | grep -ac "waker lost")
[ "$d6" = "2" ] && ok || bad "D6: second lost waker swallowed ($d6 rings, want 2)"
grep -q "^waker_lost " "$LOCKS/sD6.errparked" 2>/dev/null && ok || bad "D6: death record missing after recheck rings"
# D6b: the waker list carries a COMPLETED id first + a lost id second — loss must
# still be proven (checking only the first-sorted id missed this — review finding)
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"t3done"},"message":{"content":[]}}\n' "$TS_OLD6" >> "$D6TR"
printf '{"type":"user","timestamp":"%s","message":{"role":"user","content":"<task-notification><task-id>t3done</task-id></task-notification>"}}\n' "$TS_OLD6" >> "$D6TR"
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"t4lost"},"message":{"content":[]}}\n' "$TS_OLD6" >> "$D6TR"
printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"end_turn","content":[{"type":"text","text":"acted on it"}]}}\n' >> "$D6TR"
D6DEC "t3done,t4lost"
d6b=$(grep -a "sess=sD6" "$SBHOME/.claude/sound-debug.log" | grep -ac "waker lost")
[ "$d6b" = "3" ] && ok || bad "D6b: completed-first waker list hid the lost one ($d6b, want 3)"

# D7: crashed compaction (PreCompact fired, PostCompact never did) — the stale
# .compacting marker IS the proof-of-loss; the recheck must classify waker_lost,
# never a clean tada finish.
D7TR="$T/wl7.jsonl"
printf '{"type":"user","message":{"role":"user","content":"hi"}}\n' > "$D7TR"
printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"end_turn","content":[{"type":"text","text":"done"}]}}\n' >> "$D7TR"
touch "$LOCKS/sD7.compacting"
old7=$(( $(date +%s) - 1800 ))
touch -d "@$old7" "$LOCKS/sD7.compacting" 2>/dev/null || python3 -c "import os;os.utime('$LOCKS/sD7.compacting',($old7,$old7))"
printf '{"session_id":"sD7","transcript_path":"%s","cwd":"%s"}' "$D7TR" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_SETTLE=0 CLAUDE_SOUND_GRACE=1 \
    CLAUDE_SOUND_RECHECK=1 CLAUDE_RECHECK_WAKER=compact \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true
grep -q "^waker_lost " "$LOCKS/sD7.errparked" 2>/dev/null && ok || bad "D7: crashed compaction not classified as waker_lost"

# D8: recheck dedup is CLASS-scoped — an armed busy-task sleeper must not
# swallow a later busy-subagent arm for a different waker (review finding,
# live-reproduced: single class-blind marker = one sleeper, second class lost)
D8T1="$T/wl8a.jsonl"
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"d8task"},"message":{"content":[]}}\n' "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" > "$D8T1"
printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"end_turn","content":[{"type":"text","text":"w"}]}}\n' >> "$D8T1"
D8DEC() { printf '{"session_id":"sD8","transcript_path":"%s","cwd":"%s"}' "$1" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_SETTLE=0 CLAUDE_SOUND_GRACE=1 CLAUDE_SOUND_RECHECK_DELAY=600 \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true; }
D8DEC "$D8T1"
D8T2="$T/wl8b.jsonl"
printf '{"type":"user","timestamp":"%s","message":{"role":"user","content":"hi"}}\n' "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" > "$D8T2"
printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"end_turn","content":[{"type":"text","text":"w"}]}}\n' >> "$D8T2"
mkdir -p "$T/sD8/subagents"
printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"tool_use","content":[{"type":"tool_use"}]}}\n' > "$T/sD8/subagents/agent-live1.jsonl"
D8DEC "$D8T2"
d8=$(grep -a "sess=sD8" "$SBHOME/.claude/sound-debug.log" | grep -ac "recheck-armed")
[ "$d8" = "2" ] && ok || bad "D8: class transition armed $d8 sleepers (want 2)"
[ -f "$LOCKS/sD8.recheck-busy-task" ] && [ -f "$LOCKS/sD8.recheck-busy-subagent" ] \
  && ok || bad "D8: class-scoped markers missing"

# D9: lost-SUBAGENT end-to-end — frozen assistant-mid tail + stale mid-stream
# sidechain: the recheck must classify waker_lost (dead-tail semantics), never
# read the corpse as busy-input and go permanently silent (review finding)
D9TR="$T/wl9.jsonl"
printf '{"type":"user","timestamp":"%s","message":{"role":"user","content":"go"}}\n' "$(date -u -d @$(( $(date +%s) - 7200 )) +%Y-%m-%dT%H:%M:%S.000Z)" > "$D9TR"
printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"tool_use","content":[{"type":"tool_use"}]}}\n' >> "$D9TR"
mkdir -p "$T/sD9/subagents"
printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"tool_use","content":[{"type":"tool_use"}]}}\n' > "$T/sD9/subagents/agent-dead1.jsonl"
old9=$(( $(date +%s) - 7200 ))
python3 -c "import os;os.utime('$T/sD9/subagents/agent-dead1.jsonl',($old9,$old9))"
printf '{"session_id":"sD9","transcript_path":"%s","cwd":"%s"}' "$D9TR" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_SETTLE=0 CLAUDE_SOUND_GRACE=1 \
    CLAUDE_SOUND_RECHECK=1 CLAUDE_RECHECK_WAKER="sub:agent-dead1.jsonl" CLAUDE_RECHECK_CLASS="busy-subagent" \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true
grep -q "^waker_lost " "$LOCKS/sD9.errparked" 2>/dev/null && ok || bad "D9: lost subagent not classified (frozen tail read as busy?)"

# D10: dead-tail semantics must SURVIVE the blocking-hook-wait retry — a live
# Stop hook at recheck fire time made the retry re-decide WITHOUT dead-tail
# semantics: frozen tail read busy-input → permanent silence (review finding,
# live-reproduced). A fake hook process (cmdline contains .claude/hooks/, cwd
# matches) forces the wait+retry path during a recheck.
D10TR="$T/wl10.jsonl"
printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"d10lost"},"message":{"content":[]}}\n' \
  "$(date -u -d @$(( $(date +%s) - 7200 )) +%Y-%m-%dT%H:%M:%S.000Z)" > "$D10TR"
printf '{"type":"user","timestamp":"%s","message":{"role":"user","content":[{"type":"tool_result","content":"out"}]}}\n' \
  "$(date -u -d @$(( $(date +%s) - 7200 )) +%Y-%m-%dT%H:%M:%S.000Z)" >> "$D10TR"
mkdir -p "$T/.claude/hooks"
printf 'import time\ntime.sleep(5)\n' > "$T/.claude/hooks/fake_hook.py"
( cd "$T" && setsid python3 "$T/.claude/hooks/fake_hook.py" >/dev/null 2>&1 & )
sleep 0.5
d10_t0=$SECONDS
printf '{"session_id":"sD10","transcript_path":"%s","cwd":"%s"}' "$D10TR" "$T" \
  | env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_SETTLE=0 CLAUDE_SOUND_GRACE=1 \
    CLAUDE_SOUND_RECHECK=1 CLAUDE_RECHECK_WAKER="d10lost" CLAUDE_RECHECK_CLASS="busy-task" \
    python3 "$SBHOME/.claude/bin/claude-stop-decider.py" >/dev/null 2>&1 || true
grep -q "^waker_lost " "$LOCKS/sD10.errparked" 2>/dev/null && ok || bad "D10: hook-wait retry dropped dead-tail semantics"
[ $(( SECONDS - d10_t0 )) -ge 3 ] && ok || bad "D10: wait loop never engaged (fixture rig defect)"

# ── Section Q: quota-health (plan 2026-08-10-plan-1, Phase A) ────────────────
# The helper is a peer of the decider; the sandbox gets its own CLAUDE_QUOTA_HOME so no
# fixture can read or write the operator's real accounts/state.
if [ ! -f "$SBHOME/.claude/bin/claude-quota.py" ]; then
  bad "Q: claude-quota.py missing from the sandbox — Section Q would have silently no-op'd"
else
  QH="$T/qhome"; mkdir -p "$QH/manager-accounts/acct-a" "$QH/manager-accounts/acct-b" "$QH/.claude-manager"
  _creds "tok-A" > "$QH/manager-accounts/acct-a/.credentials.json"
  _creds "tok-B" > "$QH/manager-accounts/acct-b/.credentials.json"
  _creds "tok-B" > "$QH/.credentials.json"
  QNOW=$(date +%s); QRESET=$(( QNOW + 3600 ))
  printf '{"rateLimits":{"fiveHour":{"usedPercent":99.2,"resetsAt":%s},"sevenDay":null}}' "$QRESET" \
    > "$QH/.claude-manager/statusline.json"
  Q() { env CLAUDE_QUOTA_HOME="$QH" python3 "$SBHOME/.claude/bin/claude-quota.py" "$@"; }
  # Q1: --record persists the ACTIVE account's wall from a StopFailure payload
  printf '{"session_id":"sQ1","error":"rate_limit","error_details":"429 rate limit"}' | Q --record
  grep -q '"acct-b"' "$QH/.claude-manager/wall-state.json" 2>/dev/null && ok || bad "Q1: wall-state not recorded for the active account"
  grep -q "\"resetsAt\": $QRESET" "$QH/.claude-manager/wall-state.json" 2>/dev/null && ok || bad "Q1b: structured resetsAt not persisted"
  # Q1c: the state file is 0600 (the security floor — no _secure_write reachable here)
  [ "$(stat -c %a "$QH/.claude-manager/wall-state.json")" = "600" ] && ok || bad "Q1c: wall-state not 0600"
  # Q2: the wait is bounded — [reset-now, reset-now+jitter_max] for five_hour
  qw=$(Q --wait-seconds rate_limit)
  case "$qw" in ''|*[!0-9]*) bad "Q2: wait not an integer: $qw" ;; *)
    # TIGHT: reset is QNOW+3600 and jitter<=120, so a real shortening bug cannot hide
    if [ "$qw" -ge 3570 ] && [ "$qw" -le 3720 ]; then ok; else bad "Q2: wait $qw outside [3570,3720]"; fi ;;
  esac
  # Q3: healthy sibling = the account with no live wall
  [ "$(Q --healthy-sibling)" = "acct-a" ] && ok || bad "Q3: healthy sibling wrong: $(Q --healthy-sibling)"
  # Q4: every account walled → exit 1, no name
  printf '{"acct-a":{"rateLimitType":"seven_day","resetsAt":%s,"recordedAt":%s},"acct-b":{"rateLimitType":"five_hour","resetsAt":%s,"recordedAt":%s}}' \
    "$(( QNOW + 9000 ))" "$QNOW" "$QRESET" "$QNOW" > "$QH/.claude-manager/wall-state.json"
  Q --healthy-sibling >/dev/null 2>&1 && bad "Q4: reported a sibling while all are walled" || ok
  # Q5: unknown/no wall → the legacy 90s (fail-open floor)
  printf '{}' > "$QH/.claude-manager/wall-state.json"
  printf '{"rateLimits":{"fiveHour":null,"sevenDay":null}}' > "$QH/.claude-manager/statusline.json"
  [ "$(Q --wait-seconds rate_limit)" = "90" ] && ok || bad "Q5: no-wall wait != 90"
  # Q6: a NON-quota class always takes the legacy path
  [ "$(Q --wait-seconds server_error)" = "90" ] && ok || bad "Q6: non-quota class != 90"
  # Q7: --status prints a row per live wall, and the fail-open line when empty
  Q --status | grep -q "no wall state recorded" && ok || bad "Q7: --status empty-state line missing"
fi

# ── Section BQ: quota-health mesh integration (plan 2026-08-10-plan-1, Phase B) ──
if [ -f "$SBHOME/.claude/bin/claude-quota.py" ]; then
  # a shim helper that answers a KNOWN wall, so waits are deterministic in fixtures
  cat > "$SHIM/quota-shim.py" <<'EOF'
#!/usr/bin/env python3
import os, sys
a = sys.argv[1] if len(sys.argv) > 1 else ""
if a == "--wait-seconds":
    w = os.environ.get("MESH_FAKE_WAIT", "5")
    f = os.environ.get("MESH_FAKE_WAIT_FILE")  # W8: an answer that CHANGES mid-wait
    if f and os.path.exists(f): w = open(f).read().strip() or w
    print(w); raise SystemExit(0)
if a == "--healthy-sibling":
    sib = os.environ.get("MESH_FAKE_SIBLING", "")
    if not sib: raise SystemExit(1)
    print(sib); raise SystemExit(0)
if a == "--record":
    sys.stdin.read()
    open(os.environ["MESH_RECLOG"], "a").write("recorded\n"); raise SystemExit(0)
raise SystemExit(2)
EOF
  chmod +x "$SHIM/quota-shim.py"
  export MESH_RECLOG="$T/records.log"; : > "$MESH_RECLOG"
  # BQ1: a rate_limit death RECORDS the wall through the helper
  FIRE_EXTRA_ENV="MESH_QUOTA_CMD=$SHIM/quota-shim.py MESH_RECLOG=$MESH_RECLOG"     fire rate_limit sBQ1
  [ -s "$MESH_RECLOG" ] && ok || bad "BQ1: death did not record the wall"
  # BQ2: AUTOROTATE on + a HEALTHY SIBLING → rotation spawned
  : > "$MESH_ROTLOG"; echo 0 > "$LOCKS/rotation.last"
  FIRE_EXTRA_ENV="MESH_QUOTA_CMD=$SHIM/quota-shim.py MESH_RECLOG=$MESH_RECLOG MESH_FAKE_SIBLING=acct-a"     fire rate_limit sBQ2 CLAUDE_SOUND_AUTOROTATE=1
  for _w in 1 2 3 4 5 6; do [ -s "$MESH_ROTLOG" ] && break; sleep 0.5; done
  [ -s "$MESH_ROTLOG" ] && ok || bad "BQ2: healthy sibling did not rotate"
  # the gate's ANSWER must be the rotation's TARGET — `--next` blind-picks and can
  # land on another walled account on a 3-account box (review finding, reproduced)
  grep -q -- "--switch acct-a" "$MESH_ROTLOG" && ok \
    || bad "BQ2b: rotated with [$(cat "$MESH_ROTLOG")] — expected --switch acct-a"
  grep -aq "rotation-spawned(acct-a)" "$SBHOME/.claude/sound-debug.log" && ok \
    || bad "BQ2c: targeted rotation not logged"
  # BQ3: AUTOROTATE on + NO healthy sibling → NO churn, and the wait is announced
  : > "$MESH_ROTLOG"; echo 0 > "$LOCKS/rotation.last"; : > "$MESH_NOTELOG2"
  FIRE_CWD=/opt/mesh-fake FIRE_EXTRA_ENV="MESH_QUOTA_CMD=$SHIM/quota-shim.py MESH_RECLOG=$MESH_RECLOG MESH_FAKE_WAIT=7200 MESH_NOTIFY_CMD=$SHIM/mesh-notify2 MESH_NOTELOG2=$MESH_NOTELOG2"     fire rate_limit sBQ3 CLAUDE_SOUND_AUTOROTATE=1
  sleep 2
  [ ! -s "$MESH_ROTLOG" ] && ok || bad "BQ3: rotated with NO healthy sibling (churn)"
  grep -aq "rotation-skipped(no healthy sibling)" "$SBHOME/.claude/sound-debug.log" && ok     || bad "BQ3b: no-sibling skip not logged"
  for _w in 1 2 3 4 5 6; do grep -q "revival scheduled" "$MESH_NOTELOG2" 2>/dev/null && break; sleep 0.5; done
  grep -q "revival scheduled" "$MESH_NOTELOG2" 2>/dev/null && ok || bad "BQ3c: wait not announced"
  unset FIRE_CWD
  # BQ4: the reviver's rate_limit wait comes from the HELPER (not the blind 90s) and
  # the sliced wait touches .reviving each slice (the 35-min staleness contract)
  : > "$MESH_CLAUDELOG"
  printf 'rate_limit %s
' "$(date +%s)" > "$LOCKS/sBQ4.errparked"
  printf '%s' "$(( $(date +%s) - 600 ))" > "$LOCKS/sBQ4.reviving"
  touch -d "@$(( $(date +%s) - 600 ))" "$LOCKS/sBQ4.reviving"
  before=$(stat -c %Y "$LOCKS/sBQ4.reviving")
  env MESH_QUOTA_CMD="$SHIM/quota-shim.py" MESH_FAKE_WAIT=3 MESH_BACKOFF_OVERRIDE=""     HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$LOCKS"     CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" MESH_CLAUDELOG="$MESH_CLAUDELOG"     MESH_NET="$MESH_NET" MESH_JITTER_MAX=1 MESH_START_SPACING=1 MESH_RETRY_WAIT=1 MESH_INITIAL_GRACE=0     bash "$SBHOME/.claude/bin/claude-autoresume.sh" sBQ4 rate_limit
  grep -q -- "--resume sBQ4" "$MESH_CLAUDELOG" && ok || bad "BQ4: reviver never resumed"
  after=$(stat -c %Y "$LOCKS/sBQ4.reviving" 2>/dev/null || echo "$before")
  [ "$after" -gt "$before" ] && ok || bad "BQ4b: .reviving not touched during the sliced wait"
  # BQ5: a mid-wait HEAL (marker cleared) aborts the reviver — no barging in
  : > "$MESH_CLAUDELOG"
  printf 'rate_limit %s
' "$(date +%s)" > "$LOCKS/sBQ5.errparked"
  ( sleep 2; rm -f "$LOCKS/sBQ5.errparked" ) &
  env MESH_QUOTA_CMD="$SHIM/quota-shim.py" MESH_FAKE_WAIT=5 MESH_BACKOFF_OVERRIDE=""     HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$LOCKS"     CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" MESH_CLAUDELOG="$MESH_CLAUDELOG"     MESH_NET="$MESH_NET" MESH_JITTER_MAX=1 MESH_START_SPACING=1 MESH_RETRY_WAIT=1 MESH_INITIAL_GRACE=0     bash "$SBHOME/.claude/bin/claude-autoresume.sh" sBQ5 rate_limit
  wait
  [ ! -s "$MESH_CLAUDELOG" ] && ok || bad "BQ5: reviver barged in after a mid-wait heal"
  # BQ6: the pane watch uses the helper too, and a mid-wait heal keeps it WATCHING
  printf 'rate_limit %s
' "$(date +%s)" > "$LOCKS/sBQ6.errparked"
  ( sleep 2; rm -f "$LOCKS/sBQ6.errparked" ) &
  env MESH_QUOTA_CMD="$SHIM/quota-shim.py" MESH_FAKE_WAIT=5 MESH_BACKOFF_OVERRIDE=""     HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$LOCKS" MESH_NET="$MESH_NET"     MESH_JITTER_MAX=1 MESH_POLL=1 timeout 12 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sBQ6 > "$T/bq6.out"
  wait
  grep -q '^RESUME:' "$T/bq6.out" && bad "BQ6: fired after a mid-wait heal" || ok
fi

# BQ7: the SLICE CAP is real — a wait longer than one slice must take MULTIPLE slices
# (a regression deleting the cap breaks the 35-min .reviving staleness contract for a
# real multi-hour quota wait; every earlier fixture used a sub-slice wait — review gap)
if [ -f "$SBHOME/.claude/bin/claude-quota.py" ]; then
  : > "$MESH_CLAUDELOG"
  printf 'rate_limit %s\n' "$(date +%s)" > "$LOCKS/sBQ7.errparked"
  printf '%s' "$(( $(date +%s) - 600 ))" > "$LOCKS/sBQ7.reviving"
  touch -d "@$(( $(date +%s) - 600 ))" "$LOCKS/sBQ7.reviving"
  bq7_t0=$SECONDS
  env MESH_QUOTA_CMD="$SHIM/quota-shim.py" MESH_FAKE_WAIT=6 MESH_SLICE_MAX=2 MESH_BACKOFF_OVERRIDE="" \
    HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$LOCKS" \
    CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
    MESH_NET="$MESH_NET" MESH_JITTER_MAX=1 MESH_START_SPACING=1 MESH_RETRY_WAIT=1 MESH_INITIAL_GRACE=0 \
    bash "$SBHOME/.claude/bin/claude-autoresume.sh" sBQ7 rate_limit
  bq7_el=$(( SECONDS - bq7_t0 ))
  # 6s of wait in 2s slices = 3 slices: elapsed must cover the FULL wait, not one slice
  [ "$bq7_el" -ge 5 ] && ok || bad "BQ7: multi-slice wait finished in ${bq7_el}s (cap ignored?)"
  grep -q -- "--resume sBQ7" "$MESH_CLAUDELOG" && ok || bad "BQ7b: multi-slice wait never resumed"
  # BQ10 (2026-09-03, the pane watch): a rate_limit wait RE-ASKS the quota helper every slice —
  # after a manual account switch the helper's answer drops (the active account has no wall)
  # and the watch fires within a slice instead of sleeping to the DEAD account's reset clock
  # (429 is in every one of the 17 human-rescued /opt sessions of the 2026-09-03 storm). Its own
  # sid — a lingering watch on a shared sid eats the next fixture's marker (found: BQ9 went red).
  printf '40' > "$T/bq10.wait"
  bq10_t0=$SECONDS
  env MESH_QUOTA_CMD="$SHIM/quota-shim.py" MESH_FAKE_WAIT_FILE="$T/bq10.wait" MESH_BACKOFF_OVERRIDE="" \
    HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$LOCKS" MESH_NET="$MESH_NET" \
    MESH_SLICE_MAX=2 MESH_JITTER_MAX=0 MESH_POLL=1 timeout 12 bash "$SBHOME/.claude/bin/claude-selfwatch.sh" sBQ10 > "$T/bq10.out" &
  sleep 1; printf 'rate_limit %s\n' "$(date +%s)" > "$LOCKS/sBQ10.errparked"
  sleep 3; printf '1' > "$T/bq10.wait"                               # the operator switched
  for _ in $(seq 1 20); do grep -q '^RESUME:' "$T/bq10.out" && break; sleep 1; done
  grep -q '^RESUME:' "$T/bq10.out" && [ $(( SECONDS - bq10_t0 )) -lt 20 ] && ok \
    || bad "BQ10: rate_limit wait ignored the account switch ($(( SECONDS - bq10_t0 ))s): $(cat "$T/bq10.out")"
  wait  # the standing watch ends at its own timeout; never leave it alive into the next fixture
  # BQ8: DEFAULT path — no MESH_QUOTA_CMD shim; the sandbox-installed REAL helper answers
  : > "$MESH_CLAUDELOG"
  printf 'rate_limit %s\n' "$(date +%s)" > "$LOCKS/sBQ8.errparked"
  env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_QUOTA_HOME="$QHOME" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    MESH_CLAUDELOG="$MESH_CLAUDELOG" MESH_NET="$MESH_NET" MESH_JITTER_MAX=1 MESH_START_SPACING=1 \
    MESH_RETRY_WAIT=1 MESH_INITIAL_GRACE=0 MESH_BACKOFF_OVERRIDE=1 \
    bash "$SBHOME/.claude/bin/claude-autoresume.sh" sBQ8 rate_limit
  grep -q -- "--resume sBQ8" "$MESH_CLAUDELOG" && ok || bad "BQ8: default (unshimmed) path failed"
  # BQ9: helper ABSENT → the wait degrades to the legacy class default, never breaks
  : > "$MESH_CLAUDELOG"
  printf 'rate_limit %s\n' "$(date +%s)" > "$LOCKS/sBQ9.errparked"
  env MESH_QUOTA_CMD="$T/no-such-helper.py" HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" \
    CLAUDE_SOUND_LOCKDIR="$LOCKS" CLAUDE_SOUND_MEDIA="$T/nomedia" CLAUDE_SOUND_PULSE="$T/nopulse" \
    MESH_CLAUDELOG="$MESH_CLAUDELOG" MESH_NET="$MESH_NET" MESH_JITTER_MAX=1 MESH_START_SPACING=1 \
    MESH_RETRY_WAIT=1 MESH_INITIAL_GRACE=0 MESH_BACKOFF_OVERRIDE=1 \
    bash "$SBHOME/.claude/bin/claude-autoresume.sh" sBQ9 rate_limit
  grep -q -- "--resume sBQ9" "$MESH_CLAUDELOG" && ok || bad "BQ9: absent helper broke the reviver"
fi

# ── Section R: reboot sweep (plan 2026-08-10-plan-1, Phase D) ────────────────
if [ -f "$SBHOME/.claude/bin/claude-reboot-sweep.sh" ]; then
  RLOCKS="$T/rlocks"; mkdir -p "$RLOCKS"
  RLOG="$T/sweep.log"; : > "$RLOG"
  : > "$MESH_CLAUDELOG"
  # a busy transcript (pending background task) and a cleanly-parked one
  RB="$T/r-busy.jsonl"
  printf '{"type":"user","timestamp":"%s","toolUseResult":{"backgroundTaskId":"rtask"},"message":{"content":[]}}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" > "$RB"
  printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"end_turn","content":[{"type":"text","text":"w"}]}}\n' >> "$RB"
  RP="$T/r-parked.jsonl"
  printf '{"type":"user","message":{"role":"user","content":"hi"}}\n' > "$RP"
  printf '{"type":"assistant","message":{"role":"assistant","stop_reason":"end_turn","content":[{"type":"text","text":"done"}]}}\n' >> "$RP"
  mk() { printf '{"sid":"%s","cwd":"%s","transcript_path":"%s","marked_at":%s}' "$1" "$T" "$2" "$(date +%s)" \
           > "$RLOCKS/$1.autonomous"; }
  # LIVE_WINDOW=0 for the base fixtures: their transcripts are created seconds earlier, so
  # the liveness gate (R9's subject) would correctly skip them all. R9 sets it explicitly.
  SWEEP() { env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 \
      MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"; }
  # R1: marked + mid-work → resumed, marker consumed, headless+no-revive env carried
  mk sR1 "$RB"
  # BOOT-RELATIVE, not absolute-age (round-7: an absolute 99999s age straddles boot on any
  # box up >27.7h and flips the guard's verdict — the fixture must pin its relation to boot)
  R1BOOT=$(( $(date +%s) - $(awk '{print int($1)}' /proc/uptime) ))
  printf '%s' "$(( R1BOOT - 100 ))" > "$RLOCKS/sR1.reviving"   # pre-reboot corpse
  touch -d "@$(( R1BOOT - 100 ))" "$RLOCKS/sR1.reviving"
  SWEEP; sleep 1
  grep -q -- "--resume sR1" "$MESH_CLAUDELOG" && ok || bad "R1: mid-work session not resumed"
  [ ! -f "$RLOCKS/sR1.autonomous" ] && ok || bad "R1b: marker not consumed"
  [ ! -f "$RLOCKS/sR1.reviving" ] && ok || bad "R1c: pre-reboot .reviving not cleared"
  grep -q "headless=1 .*--resume sR1" "$MESH_CLAUDELOG" && ok || bad "R1d: resume not headless-tagged"
  # R2: marked but cleanly PARKED → skipped (nothing was in flight), marker consumed
  : > "$MESH_CLAUDELOG"; mk sR2 "$RP"
  SWEEP; sleep 1
  grep -q -- "--resume sR2" "$MESH_CLAUDELOG" && bad "R2: parked session wrongly resumed" || ok
  [ ! -f "$RLOCKS/sR2.autonomous" ] && ok || bad "R2b: skip did not consume the marker"
  # R3: UNMARKED session (a pane) → never touched
  : > "$MESH_CLAUDELOG"
  printf 'unknown %s\n' "$(date +%s)" > "$RLOCKS/sR3.errparked"   # mid-work but unmarked
  SWEEP; sleep 1
  grep -q -- "--resume sR3" "$MESH_CLAUDELOG" && bad "R3: swept an unmarked (pane) session" || ok
  # R4: errparked marked session resumes even without a transcript
  : > "$MESH_CLAUDELOG"; mk sR4 "$T/nope.jsonl"
  printf 'rate_limit %s\n' "$(date +%s)" > "$RLOCKS/sR4.errparked"
  SWEEP; sleep 1
  grep -q -- "--resume sR4" "$MESH_CLAUDELOG" && ok || bad "R4: errparked session not resumed"
  # R5: a SECOND sweep is a no-op (markers already consumed — idempotent)
  : > "$MESH_CLAUDELOG"
  SWEEP; sleep 1
  [ ! -s "$MESH_CLAUDELOG" ] && ok || bad "R5: second sweep re-resumed consumed markers"
  # R6: a stale marker (older than the retention window) is dropped, never resumed
  : > "$MESH_CLAUDELOG"; mk sR6 "$RB"
  touch -d "@$(( $(date +%s) - 999999 ))" "$RLOCKS/sR6.autonomous"
  SWEEP; sleep 1
  grep -q -- "--resume sR6" "$MESH_CLAUDELOG" && bad "R6: stale marker resumed" || ok
  [ ! -f "$RLOCKS/sR6.autonomous" ] && ok || bad "R6b: stale marker not dropped"
  # R7: every decision is logged (the sweep is never a silent black box)
  # per-DECISION lines, not just the unconditional summary (the old assertion passed even
  # if every decision note were deleted — review finding)
  grep -q "resume-spawned" "$RLOG" && ok || bad "R7: no per-session resume decision logged"
  grep -q "skip-not-midwork" "$RLOG" && ok || bad "R7b: no per-session skip decision logged"
  grep -q "sweep-done" "$RLOG" && ok || bad "R7c: sweep did not log its summary"
  # R8: the plan-mandated SPACING fixture — two eligible markers in ONE sweep must start
  # staggered (the "does not stampede the API at boot" claim was entirely untested)
  : > "$MESH_CLAUDELOG"
  mk sR8a "$RB"; mk sR8b "$RB"
  printf 'unknown %s\n' "$(date +%s)" > "$RLOCKS/sR8a.errparked"
  printf 'unknown %s\n' "$(date +%s)" > "$RLOCKS/sR8b.errparked"
  r8_t0=$SECONDS
  env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" \
    MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=2 \
    MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
    bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  r8_el=$(( SECONDS - r8_t0 ))
  [ "$(grep -c -- "--resume sR8" "$MESH_CLAUDELOG")" = "2" ] && ok || bad "R8: both markers not resumed"
  [ "$r8_el" -ge 2 ] && ok || bad "R8b: starts not spaced (elapsed ${r8_el}s, spacing 2)"
  # R9: a STILL-LIVE session (transcript touched just now) is never resumed — @reboot also
  # fires on a cron-daemon restart, when siblings are alive (review finding)
  : > "$MESH_CLAUDELOG"
  RL="$T/r-live.jsonl"; cp "$RB" "$RL"; touch "$RL"
  mk sR9 "$RL"
  env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" \
    MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
    MESH_SWEEP_LIVE_WINDOW=300 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
    bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  grep -q -- "--resume sR9" "$MESH_CLAUDELOG" && bad "R9: resumed a STILL-LIVE session" || ok
  [ -f "$RLOCKS/sR9.autonomous" ] && ok || bad "R9b: live-skip consumed the marker (must keep it)"

  # ── Section RS: standby-survivable sweep (plan 2026-08-13-plan-1) ──────────
  # Persistent markers (MESH_STATE_DIR) + vm-cut + death-class eligibility + Leg B notify.
  RSTATE="$T/rstate"; mkdir -p "$RSTATE"
  mks() { printf '{"sid":"%s","cwd":"%s","transcript_path":"%s","marked_at":%s}' "$1" "$T" "$2" "$(date +%s)" \
           > "$RSTATE/$1.autonomous"; }
  # a stalled-tail transcript: the REAL death shape (mid-stream class) — the decider must
  # print stalled-api-error for it (deterministic; grounded by the plan-time probe)
  RSTALL="$T/rs-stall.jsonl"
  printf '{"type":"user","timestamp":"2026-08-13T00:00:00.000Z","message":{"role":"user","content":"hi"}}\n' > "$RSTALL"
  printf '{"type":"assistant","timestamp":"2026-08-13T00:00:01.000Z","isApiErrorMessage":true,"message":{"role":"assistant","stop_reason":"stop_sequence","content":[{"type":"text","text":"API Error: Response stalled mid-stream. The response above may be incomplete."}]}}\n' >> "$RSTALL"
  SWEEPS() { env HOME="$SBHOME" PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" \
      MESH_STATE_DIR="$RSTATE" \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 \
      MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"; }
  # RS1 (Gap 1): marker in the PERSISTENT dir, lock dir DELETED (the VM cut) → vm-cut
  # logged + the busy session still resumed. Today: no-lockdir exit, nothing spawned.
  : > "$MESH_CLAUDELOG"; : > "$RLOG"
  mks sRS1 "$RB"
  rm -rf "$RLOCKS"
  SWEEPS; sleep 1
  grep -q "vm-cut" "$RLOG" && ok || bad "RS1: vm-cut not classified (no-lockdir dead end?)"
  grep -q -- "--resume sRS1" "$MESH_CLAUDELOG" && ok || bad "RS1b: cut session not resumed"
  mkdir -p "$RLOCKS"
  # RS2 (Gap 2): stalled-api-error tail (REAL decider, synthetic death transcript) → eligible
  : > "$MESH_CLAUDELOG"; mks sRS2 "$RSTALL"
  SWEEPS; sleep 1
  grep -q -- "--resume sRS2" "$MESH_CLAUDELOG" && ok || bad "RS2: death-class tail not eligible"
  grep -q "why=stalled-api-error" "$RLOG" && ok || bad "RS2b: eligibility reason not logged"
  # RS3 (guard): cleanly-parked stays ineligible even via the persistent dir
  : > "$MESH_CLAUDELOG"; mks sRS3 "$RP"
  SWEEPS; sleep 1
  grep -q -- "--resume sRS3" "$MESH_CLAUDELOG" && bad "RS3: parked wrongly resumed" || ok
  # RS4 (compat): marker in the LEGACY lock dir only (persistent dir EMPTY — the glob-break
  # trap, pool F2/closer F4) → still swept
  : > "$MESH_CLAUDELOG"; mk sRS4 "$RB"
  SWEEPS; sleep 1
  grep -q -- "--resume sRS4" "$MESH_CLAUDELOG" && ok || bad "RS4: legacy-dir marker skipped (glob break?)"
  # RS5 (dedupe): same sid in BOTH dirs → exactly ONE spawn, both copies consumed
  : > "$MESH_CLAUDELOG"; mks sRS5 "$RB"; mk sRS5 "$RB"
  SWEEPS; sleep 1
  [ "$(grep -c -- "--resume sRS5" "$MESH_CLAUDELOG")" = "1" ] && ok || bad "RS5: dedupe failed"
  [ ! -f "$RSTATE/sRS5.autonomous" ] && [ ! -f "$RLOCKS/sRS5.autonomous" ] && ok || bad "RS5b: a copy survived"
  # RS5c (closer F14): an INELIGIBLE (parked) sid marked in BOTH dirs — both copies consumed
  : > "$MESH_CLAUDELOG"; mks sRS5c "$RP"; mk sRS5c "$RP"
  SWEEPS; sleep 1
  [ ! -f "$RSTATE/sRS5c.autonomous" ] && [ ! -f "$RLOCKS/sRS5c.autonomous" ] && ok || bad "RS5c: ineligible twin survived"
  # RS6 (true empty): no markers anywhere + no lock dir → the historical no-lockdir exit
  : > "$RLOG"; rm -rf "$RLOCKS"
  SWEEPS
  grep -q "no-lockdir" "$RLOG" && ok || bad "RS6: empty-state no-lockdir note gone"
  grep -q "resume-spawned\|cut-notified" "$RLOG" && bad "RS6b: empty sweep did WORK" || ok
  mkdir -p "$RLOCKS"
  # RS8: concurrent sweep excluded by the self-lock — and consumes NOTHING (closer F9)
  : > "$RLOG"; mks sRS8 "$RB"
  ( exec 9>"$RSTATE/.sweep.lock"; flock 9; sleep 3 ) &
  RSLOCKPID=$!
  sleep 1
  SWEEPS
  wait "$RSLOCKPID"
  grep -q "skip-concurrent" "$RLOG" && ok || bad "RS8: concurrent sweep not excluded"
  [ -f "$RSTATE/sRS8.autonomous" ] && ok || bad "RS8b: excluded sweep consumed a marker"
  rm -f "$RSTATE/sRS8.autonomous"
  # RS8c (closer F3): the backgrounded RESUME must not inherit the lock fd — a second sweep
  # during the resumed child's lifetime must run, not skip-concurrent
  SLOWSHIM="$T/slowshim"; mkdir -p "$SLOWSHIM"
  cat > "$SLOWSHIM/claude" <<'SLOW'
#!/usr/bin/env bash
printf 'headless=%s args: %s\n' "${CLAUDE_MESH_HEADLESS:-0}" "$*" >> "${MESH_CLAUDELOG:-/dev/null}"
sleep 4
SLOW
  chmod +x "$SLOWSHIM/claude"
  : > "$RLOG"; : > "$MESH_CLAUDELOG"; mks sRS8c "$RB"
  env HOME="$SBHOME" PATH="$SLOWSHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" \
      MESH_STATE_DIR="$RSTATE" \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  sleep 1   # the slow stub child (4s) is still alive holding whatever fds it inherited
  : > "$RLOG"
  SWEEPS
  grep -q "skip-concurrent" "$RLOG" && bad "RS8c: resumed child holds the sweep lock" || ok
  # RS9: unremovable marker → consume-failed, ZERO spawns (never a boot-loop of resumes)
  : > "$MESH_CLAUDELOG"; : > "$RLOG"; mks sRS9 "$RB"
  chmod 555 "$RSTATE"
  SWEEPS; sleep 1
  chmod 755 "$RSTATE"
  grep -q "consume-failed" "$RLOG" && ok || bad "RS9: unremovable marker not refused"
  grep -q -- "--resume sRS9" "$MESH_CLAUDELOG" && bad "RS9b: spawned despite failed claim" || ok
  # RS9c (closer F10): permissions restored → the SAME marker is processed next boot
  : > "$MESH_CLAUDELOG"
  SWEEPS; sleep 1
  grep -q -- "--resume sRS9" "$MESH_CLAUDELOG" && ok || bad "RS9c: refused marker not re-processed"
  # RS10 (Leg B): cut-mid-work transcripts in the projects tree → one notify each via the
  # MESH_NOTIFY_CMD seam; cleanly-parked neighbours stay silent
  RSPROJ="$SBHOME/.claude/projects/-opt-rstest"; mkdir -p "$RSPROJ"
  cp "$RSTALL" "$RSPROJ/aaaa1111.jsonl"; cp "$RP" "$RSPROJ/bbbb2222.jsonl"
  # F1/F2 (closer): subagent sidecar transcripts must be EXCLUDED from the scan — they are
  # not resumable sessions, and en masse they starve the head-N budget of the real ones
  mkdir -p "$RSPROJ/aaaa1111/subagents"
  for sub in 1 2 3; do
    # each sidecar CARRIES a cwd record — without it the cwd guard skips them and the
    # -path filter is untested (confirm-round: RS10d passed with the filter removed)
    printf '{"type":"user","cwd":"/opt/rstest","timestamp":"2026-08-13T00:00:00.000Z","message":{"role":"user","content":"x"}}\n' > "$RSPROJ/aaaa1111/subagents/agent-fake$sub.jsonl"
    tail -1 "$RSTALL" >> "$RSPROJ/aaaa1111/subagents/agent-fake$sub.jsonl"
  done
  # backdate to BEFORE this boot — Leg B's filter is mtime < boot (cut by the cut), and
  # now-3600 can still be AFTER a recent boot (live defect caught at fixture time)
  RSBOOT=$(( $(date +%s) - $(awk '{print int($1)}' /proc/uptime) ))
  touch -d "@$(( RSBOOT - 600 ))" "$RSPROJ/aaaa1111.jsonl" "$RSPROJ/bbbb2222.jsonl" \
        "$RSPROJ"/aaaa1111/subagents/agent-fake*.jsonl
  RSNOTES="$T/rs-notify.log"; : > "$RSNOTES"
  cat > "$T/rs-notify-stub" <<'STUB'
#!/usr/bin/env bash
printf '%s | %s\n' "$1" "$2" >> "${RS_NOTES_FILE}"
STUB
  chmod +x "$T/rs-notify-stub"
  : > "$RLOG"; rm -rf "$RLOCKS"   # a vm-cut boot is what arms the Leg B scan
  env RS_NOTES_FILE="$RSNOTES" MESH_NOTIFY_CMD="$T/rs-notify-stub" HOME="$SBHOME" \
      PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" MESH_STATE_DIR="$RSTATE" \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  mkdir -p "$RLOCKS"
  grep -q "claude --resume aaaa1111" "$RSNOTES" && ok || bad "RS10: cut session not notified"
  grep -q "bbbb2222" "$RSNOTES" && bad "RS10b: parked session wrongly notified" || ok
  grep -q "agent-fake" "$RSNOTES" && bad "RS10d: subagent sidecar wrongly notified" || ok
  # RS10c: the persistent per-sid stamp suppresses a re-notify (bounce loops must not
  # Telegram-storm — the incident had 13 bounces). The re-run is ANOTHER vm-cut boot
  # (lock dir wiped again — closer F11: with the fresh-boot gate, a lockdir-present rerun
  # would pass vacuously without exercising the stamp)
  : > "$RSNOTES"; rm -rf "$RLOCKS"
  env RS_NOTES_FILE="$RSNOTES" MESH_NOTIFY_CMD="$T/rs-notify-stub" HOME="$SBHOME" \
      PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" MESH_STATE_DIR="$RSTATE" \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  mkdir -p "$RLOCKS"
  [ -s "$RSNOTES" ] && bad "RS10c: bounce re-notify not suppressed" || ok
  # RS11 (pin fix 3): NON-fresh boot (lockdir present + fresh-window forced 0) → NO scan,
  # even with an un-notified cut transcript present
  cp "$RSTALL" "$RSPROJ/dddd4444.jsonl"; touch -d "@$(( RSBOOT - 600 ))" "$RSPROJ/dddd4444.jsonl"
  : > "$RSNOTES"; : > "$RLOG"
  env RS_NOTES_FILE="$RSNOTES" MESH_NOTIFY_CMD="$T/rs-notify-stub" HOME="$SBHOME" \
      PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" MESH_STATE_DIR="$RSTATE" \
      MESH_SWEEP_FRESH_WINDOW=0 \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  [ -s "$RSNOTES" ] && bad "RS11: non-fresh boot ran the Leg B scan" || ok
  # RS11b (the RACE half — red-on-revert vs the lockdir-only gate): lock dir PRESENT but
  # the boot is young (huge window) → the scan MUST run; this is the incident scenario
  # where a restored session recreated /tmp during the crontab's sleep 120
  : > "$RSNOTES"; : > "$RLOG"
  env RS_NOTES_FILE="$RSNOTES" MESH_NOTIFY_CMD="$T/rs-notify-stub" HOME="$SBHOME" \
      PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" MESH_STATE_DIR="$RSTATE" \
      MESH_SWEEP_FRESH_WINDOW=999999999 \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  grep -q "claude --resume aaaa1111" "$RSNOTES" && bad "RS11b-pre: stamp did not survive" || true
  grep -q "claude --resume dddd4444" "$RSNOTES" && ok || bad "RS11b: young-uptime boot with present lockdir did not scan"
  rm -f "$RSTATE/notified-dddd4444"
  # RS12 (pin fix 5): claude binary ABSENT → marker leg skipped LOUDLY, notify leg LIVES
  NOCLAUDE="$T/noclaude"; mkdir -p "$NOCLAUDE"
  cp "$SHIM"/* "$NOCLAUDE"/ 2>/dev/null || true; rm -f "$NOCLAUDE/claude"
  mks sRS12 "$RB"
  : > "$RSNOTES"; : > "$RLOG"; rm -rf "$RLOCKS"
  env RS_NOTES_FILE="$RSNOTES" MESH_NOTIFY_CMD="$T/rs-notify-stub" HOME="$SBHOME" \
      PATH="$NOCLAUDE:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" MESH_STATE_DIR="$RSTATE" \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  mkdir -p "$RLOCKS"
  grep -q "no-claude" "$RLOG" && ok || bad "RS12: missing claude not noted"
  [ -f "$RSTATE/sRS12.autonomous" ] && ok || bad "RS12b: marker consumed without claude"
  grep -q "claude --resume dddd4444" "$RSNOTES" && ok || bad "RS12c: notify leg died with claude"
  rm -f "$RSTATE/sRS12.autonomous" "$RSPROJ/dddd4444.jsonl"
  # RS13 (pin fix 6 stale half): a STALE sid marked in BOTH dirs → both copies consumed
  mks sRS13 "$RB"; mk sRS13 "$RB"
  touch -d "@$(( $(date +%s) - 999999 ))" "$RSTATE/sRS13.autonomous" "$RLOCKS/sRS13.autonomous"
  SWEEPS
  [ ! -f "$RSTATE/sRS13.autonomous" ] && [ ! -f "$RLOCKS/sRS13.autonomous" ] && ok || bad "RS13: stale twin survived"
  # RS14 (pin fix 4): a marker whose sid HAS a cut transcript in the projects tree —
  # Leg A resumes it, Leg B must NOT also notify it (the two-writer guard)
  cp "$RB" "$RSPROJ/cccc3333.jsonl"; touch -d "@$(( RSBOOT - 600 ))" "$RSPROJ/cccc3333.jsonl"
  printf '{"sid":"cccc3333","cwd":"%s","transcript_path":"%s","marked_at":%s}' "$T" "$RSPROJ/cccc3333.jsonl" "$(date +%s)" > "$RSTATE/cccc3333.autonomous"
  : > "$RSNOTES"; : > "$MESH_CLAUDELOG"; rm -rf "$RLOCKS"
  env RS_NOTES_FILE="$RSNOTES" MESH_NOTIFY_CMD="$T/rs-notify-stub" HOME="$SBHOME" \
      PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" MESH_STATE_DIR="$RSTATE" \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  mkdir -p "$RLOCKS"; sleep 1
  grep -q -- "--resume cccc3333" "$MESH_CLAUDELOG" && ok || bad "RS14: marked cut session not resumed"
  grep -q "cccc3333" "$RSNOTES" && bad "RS14b: Leg B notified a sid Leg A just resumed" || ok
  # RS15 (closing-round #1): a FRESH .reviving (live reviver) must SURVIVE the sweep and
  # make its sid ineligible — deleting it or double-spawning is the second-writer failure
  : > "$MESH_CLAUDELOG"; mks sRS15 "$RB"
  touch "$RLOCKS/sRS15.reviving"
  SWEEPS; sleep 1
  [ -f "$RLOCKS/sRS15.reviving" ] && ok || bad "RS15: fresh .reviving deleted by the sweep"
  grep -q -- "--resume sRS15" "$MESH_CLAUDELOG" && bad "RS15b: spawned despite a live reviver" || ok
  [ -f "$RSTATE/sRS15.autonomous" ] && ok || bad "RS15c: reviver-pending marker consumed"
  rm -f "$RLOCKS/sRS15.reviving" "$RSTATE/sRS15.autonomous"
  # RS15d (round-7 #2): the union's DISTINCT branch — post-boot AND stale (>2100s) → still
  # a live-reviver skip. Constructible only when uptime > ~2200s; guarded, else skipped.
  if [ "$(awk '{print int($1)}' /proc/uptime)" -gt 2200 ]; then
    : > "$MESH_CLAUDELOG"; mks sRS15d "$RB"
    R15BOOT=$(( $(date +%s) - $(awk '{print int($1)}' /proc/uptime) ))
    touch -d "@$(( R15BOOT + 10 ))" "$RLOCKS" 2>/dev/null || true
    printf x > "$RLOCKS/sRS15d.reviving"; touch -d "@$(( R15BOOT + 10 ))" "$RLOCKS/sRS15d.reviving"
    SWEEPS; sleep 1
    [ -f "$RLOCKS/sRS15d.reviving" ] && ok || bad "RS15d: post-boot stale reviving deleted (union leg 2 dead)"
    grep -q -- "--resume sRS15d" "$MESH_CLAUDELOG" && bad "RS15d-b: spawned over a post-boot reviver" || ok
    rm -f "$RLOCKS/sRS15d.reviving" "$RSTATE/sRS15d.autonomous"
  fi
  # RS16 (closing-round #3): a cut session OUTSIDE /opt is logged honestly, never falsely
  # stamped as notified
  RSPROJ2="$SBHOME/.claude/projects/-home-tester"; mkdir -p "$RSPROJ2"
  printf '{"type":"user","cwd":"/home/tester","timestamp":"2026-08-13T00:00:00.000Z","message":{"role":"user","content":"hi"}}\n' > "$RSPROJ2/eeee5555.jsonl"
  tail -1 "$RSTALL" >> "$RSPROJ2/eeee5555.jsonl"
  touch -d "@$(( RSBOOT - 1 ))" "$RSPROJ2/eeee5555.jsonl"   # newest-pre-boot: must never
  # fall off the head-20 budget behind earlier sections' backdated sandbox transcripts
  : > "$RSNOTES"; : > "$RLOG"; rm -rf "$RLOCKS"
  env RS_NOTES_FILE="$RSNOTES" MESH_NOTIFY_CMD="$T/rs-notify-stub" HOME="$SBHOME" \
      PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" MESH_STATE_DIR="$RSTATE" \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  mkdir -p "$RLOCKS"
  grep -q "eeee5555" "$RSNOTES" && bad "RS16: non-/opt session sent to the /opt-gated notifier" || ok
  grep -q "cut-unnotifiable" "$RLOG" && ok || bad "RS16b: non-/opt cut session not logged honestly | log: $(tr '\n' ';' < "$RLOG" | tail -c 400)"
  [ -f "$RSTATE/notified-eeee5555" ] && bad "RS16c: false stamp burned for an unnotifiable session" || ok
  # RS17 (round-5 #1): MULTIPLE cut sessions must ALL be notified — the notifier child
  # must never drain the scan loop's stdin (sound.sh's unconditional PAYLOAD=$(cat))
  cp "$RSTALL" "$RSPROJ/ffff6666.jsonl"; cp "$RSTALL" "$RSPROJ/gggg7777.jsonl"
  touch -d "@$(( RSBOOT - 2 ))" "$RSPROJ/ffff6666.jsonl" "$RSPROJ/gggg7777.jsonl"
  rm -f "$RSTATE"/notified-*
  : > "$RSNOTES"; : > "$RLOG"; rm -rf "$RLOCKS"
  env RS_NOTES_FILE="$RSNOTES" MESH_NOTIFY_CMD="$T/rs-notify-stub" HOME="$SBHOME" \
      PATH="$SHIM:/usr/bin:/bin" CLAUDE_SOUND_LOCKDIR="$RLOCKS" MESH_STATE_DIR="$RSTATE" \
      MESH_DECIDER_CMD="$SBHOME/.claude/bin/claude-stop-decider.py" MESH_START_SPACING=0 \
      MESH_SWEEP_LIVE_WINDOW=0 MESH_SWEEP_LOG="$RLOG" MESH_CLAUDELOG="$MESH_CLAUDELOG" \
      bash "$SBHOME/.claude/bin/claude-reboot-sweep.sh"
  mkdir -p "$RLOCKS"
  grep -q "claude --resume ffff6666" "$RSNOTES" && grep -q "claude --resume gggg7777" "$RSNOTES" \
    && ok || bad "RS17: multi-session notify drained (got: $(grep -c resume "$RSNOTES") of 2+)"
fi

echo "mesh-test: $PASS ok, $FAIL fail"
[ "$FAIL" = "0" ]
