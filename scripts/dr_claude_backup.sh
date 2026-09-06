#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/claude-config-backup-restore.md docs/workstation/claude-configuration-inventory.md
# dr_claude_backup.sh — DR mirror of this box's CLAUDE CONFIG to the private GitHub DR store.
#
# Sibling of dr_env_backup.sh (credentials) — same store, same discipline, different data class.
# Git IS the versioning: every change is a commit, so no backup ever overwrites its predecessor
# and any prior state is recoverable with `git checkout <sha> -- <path>`.
#
# WHAT IS MIRRORED (small, hand-maintained, NOT regenerable from any other repo):
#   ~/.claude.json                          main config: MCP servers, project registry
#   ~/.claude/settings.json                 permissions, hooks, statusLine, model, plugins
#   ~/.claude/agents/*.md                   custom subagent definitions (4) — exist ONLY here
#   ~/.claude/bin/**                        hand-built hook helpers (claude-sound.sh, claude-stop-decider.py) — exist ONLY here
#   ~/.claude/.credentials.json             OAuth tokens (secret)
#   ~/.claude/manager-accounts/**           the 3 rotated account credential snapshots (secret)
#   ~/.claude/.claude-manager/*.{json,js}   rotation engine taps + statusline config
#   ~/.claude/plugins/*.json                which plugins/marketplaces are enabled
#   ~/.claude-youtube-headless/{.claude.json,settings.json}   the 2nd (headless) profile's config
#   ~/.claude-fleet/<acct>/.claude.json     per-account rosters the rotator mutates (plan-3)
#   Windows Claude Desktop claude_desktop_config.json         Desktop MCP roster
#
# NOT mirrored (deliberate — regenerable or huge):
#   commands/ + skills/fab-*   rendered from /opt/fabrik/commands/_sources (already in git)
#   projects/ file-history/ session-env/ telemetry/ sessions/   ~9 GB of session state
#   plugins/marketplaces/      git clones, re-fetchable
#   caches, logs, *.lock, *.bak, *.tmp.*
#
# RUNS: daily cron + @reboot catch-up (see docs/workstation/claude-config-backup-restore.md).
# RESTORE: this script --restore [--from <git-sha>]   (see the doc for the full runbook)
set -euo pipefail

REPO="${REPO:-/opt/fabrik-dr-store}"
DEST="${DEST:-$REPO/claude-config}"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
HEADLESS_DIR="${HEADLESS_DIR:-$HOME/.claude-youtube-headless}"
WIN_DESKTOP_CFG="${WIN_DESKTOP_CFG:-/mnt/c/Users/user/AppData/Roaming/Claude/claude_desktop_config.json}"
TS=$(date -u +%Y%m%dT%H%M%SZ)
MODE="${1:-backup}"

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }

# --- copy one path into the mirror, preserving its relative shape -------------
mirror() {   # mirror <src-abs> <dest-rel>
  local src="$1" rel="$2" dst="$DEST/$2"
  [ -e "$src" ] || { log "skip (absent): $src"; return 0; }
  mkdir -p "$(dirname "$dst")"
  if [ -d "$src" ]; then
    rsync -a --delete \
      --exclude='*.lock' --exclude='*.tmp.*' --exclude='*.bak*' --exclude='__pycache__' \
      "$src/" "$dst/"
  else
    cp -p "$src" "$dst"
  fi
}

# --- normalize a .claude.json: sort keys, drop volatile counters ---------------
# Keeps the backup meaningful (diffs = real config change) and idempotent.
norm_json() {   # norm_json <src> <dst>
  local src="$1" dst="$2"
  [ -e "$src" ] || { log "skip (absent): $src"; return 0; }
  mkdir -p "$(dirname "$dst")"
  python3 - "$src" "$dst" <<'PYEOF'
import json, sys
VOLATILE = {"usageCount","lastUsedAt","lastCost","lastAPIDuration","lastDuration",
            "numStartups","promptQueueUseCount","lastSessionId","firstStartTime",
            "lastReleaseNotesSeen","subscriptionNoticeCount","recommendedSubscription",
            "cachedChangelog","changelogLastFetched","fallbackAvailableWarningThreshold"}
def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k not in VOLATILE}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o
try:
    d = json.load(open(sys.argv[1]))
except Exception as e:
    sys.exit(f"normalize failed: {e}")
json.dump(strip(d), open(sys.argv[2], "w"), indent=2, sort_keys=True)
PYEOF
}

do_backup() {
  [ -d "$REPO/.git" ] || { log "FATAL: DR store $REPO is not a git repo"; exit 1; }
  mkdir -p "$DEST"

  # .claude.json is rewritten constantly with volatile counters + reordered keys; normalize so a
  # diff shows only REAL config change (and back-to-back runs are true no-ops)
  norm_json "$HOME/.claude.json"          "$DEST/claude.json"
  mirror "$CLAUDE_DIR/settings.json"               "claude/settings.json"
  mirror "$CLAUDE_DIR/agents"                      "claude/agents"
  mirror "$CLAUDE_DIR/bin"                         "claude/bin"
  mirror "$CLAUDE_DIR/.credentials.json"           "claude/credentials.json"
  mirror "$CLAUDE_DIR/manager-accounts"            "claude/manager-accounts"
  norm_json "$HEADLESS_DIR/.claude.json"   "$DEST/claude-youtube-headless/claude.json"
  mirror "$HEADLESS_DIR/settings.json"             "claude-youtube-headless/settings.json"
  # fleet account rosters (plan-3 B4 precondition: the trim's DR claim was unfounded
  # while only the ad-hoc ~/.claude.json was mirrored — these are what the rotator mutates)
  for acct in "$HOME"/.claude-fleet/*/; do
    [ -L "${acct%/}" ] && continue   # skip the 'active' symlink (its target is mirrored)
    [ -f "$acct/.claude.json" ] || continue
    norm_json "$acct/.claude.json" "$DEST/claude-fleet/$(basename "$acct")/claude.json"
  done
  # ⚠️ caps.json lives at the fleet ROOT, not inside an account dir, so the loop above has never
  # touched it — found 2026-09-06 while raising sarp@'s weekly cap 90 → 95. It is the operator's
  # per-account browser-reserve policy (`_account_caps()` in claude_rotate.py), hand-maintained
  # and regenerable from nothing: losing it silently drops every cap back to the built-in default,
  # which is exactly the "small, hand-maintained, NOT regenerable" class this script exists for.
  mirror "$HOME/.claude-fleet/caps.json"           "claude-fleet/caps.json"
  mirror "$WIN_DESKTOP_CFG"                        "windows/claude_desktop_config.json"

  # selective file sets (dirs carry state we don't want)
  mkdir -p "$DEST/claude/.claude-manager" "$DEST/claude/plugins"
  for f in "$CLAUDE_DIR"/.claude-manager/*.json "$CLAUDE_DIR"/.claude-manager/*.js; do
    # active-sessions.json is ephemeral live state — mirroring it makes every run a noise commit
    case "$(basename "$f")" in active-sessions.json) continue ;; esac
    [ -e "$f" ] && cp -p "$f" "$DEST/claude/.claude-manager/" || true
  done
  for f in "$CLAUDE_DIR"/plugins/*.json; do
    [ -e "$f" ] && cp -p "$f" "$DEST/claude/plugins/" || true
  done

  # provenance manifest — what a restorer needs to know about this snapshot
  {
    echo "# Claude config DR snapshot (capture time = the git commit date)"
    echo "host: $(hostname)"
    echo "claude_version: $(claude --version 2>/dev/null | head -1 || echo unknown)"
    echo "mcp_servers_cli: $(python3 -c "import json;print(len(json.load(open('$HOME/.claude.json')).get('mcpServers',{})))" 2>/dev/null || echo '?')"
    echo "agents: $(ls -1 "$CLAUDE_DIR"/agents/*.md 2>/dev/null | wc -l)"
    echo "accounts: $(ls -1d "$CLAUDE_DIR"/manager-accounts/*/ 2>/dev/null | wc -l)"
  } > "$DEST/MANIFEST.txt"

  cd "$REPO"
  git add -A -- claude-config
  if git diff --cached --quiet -- claude-config; then
    log "no change — nothing to commit (previous snapshot stands)"
    exit 0
  fi
  git -c user.name="fabrik-dr" -c user.email="dr@fabrik.local" \
      commit -q -m "dr-claude: $TS" -- claude-config
  if git push -q origin HEAD 2>/dev/null; then
    log "committed + pushed: dr-claude: $TS"
  else
    log "committed locally; push FAILED (will retry next run)"
  fi
}

do_restore() {
  local from="${2:-HEAD}"
  [ -d "$DEST" ] || { log "FATAL: no mirror at $DEST"; exit 1; }
  cd "$REPO"
  log "restoring Claude config from $from"
  git checkout "$from" -- claude-config 2>/dev/null || true

  local BK="$HOME/.claude-restore-backup-$TS"; mkdir -p "$BK"
  # never clobber blind: stash what is there now, then restore
  for pair in \
    "claude.json:$HOME/.claude.json" \
    "claude/settings.json:$CLAUDE_DIR/settings.json" \
    "claude/credentials.json:$CLAUDE_DIR/.credentials.json" \
    "claude-youtube-headless/claude.json:$HEADLESS_DIR/.claude.json" \
    "claude-youtube-headless/settings.json:$HEADLESS_DIR/settings.json" \
    "windows/claude_desktop_config.json:$WIN_DESKTOP_CFG" ; do
    src="$DEST/${pair%%:*}"; dst="${pair#*:}"
    [ -e "$src" ] || continue
    [ -e "$dst" ] && cp -p "$dst" "$BK/$(echo "${pair%%:*}" | tr / _)" || true
    mkdir -p "$(dirname "$dst")"; cp -p "$src" "$dst"; log "restored $dst"
  done
  for d in "agents:$CLAUDE_DIR/agents" "bin:$CLAUDE_DIR/bin" \
           "manager-accounts:$CLAUDE_DIR/manager-accounts" \
           ".claude-manager:$CLAUDE_DIR/.claude-manager" "plugins:$CLAUDE_DIR/plugins"; do
    src="$DEST/claude/${d%%:*}"; dst="${d#*:}"
    [ -d "$src" ] || continue
    [ -d "$dst" ] && cp -a "$dst" "$BK/$(echo "${d%%:*}" | tr / _)" || true
    mkdir -p "$dst"; cp -a "$src"/. "$dst"/; log "restored $dst"
  done
  chmod 600 "$CLAUDE_DIR/.credentials.json" 2>/dev/null || true
  log "DONE. Pre-restore state saved to $BK"
  log "Restart Claude Code (and Claude Desktop if its config changed) to load the restored config."
}

case "$MODE" in
  backup)  do_backup ;;
  --restore|restore) do_restore "$@" ;;
  *) echo "usage: $0 [backup | --restore [--from <git-sha>]]"; exit 2 ;;
esac
