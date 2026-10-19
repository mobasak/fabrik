#!/usr/bin/env bash
# AFTER-EDIT: docs/reference/repo-coordinator-rollout.md | tests/test_agents_up.py
# agents_up.sh [--print] <repo> — open a repo's builder agents side by side in one tmux window (D-1031).
#
# The per-repo form of ~/bin/hub-up, which stays as it is for the hub. The builders come from the repo's own
# registry, <repo>/.fabrik/session-agents.json ({"<session id>": "<agent name>"}), so a session-id change is one
# registry edit, never a launcher edit. The coordinator gets no pane (a name equal to `coordinator` or ending in
# `-coordinator`): the operator reaches it in VS Code, as hub-up states. A pane starts in the builder's own worktree,
# `<repo>/.claude/worktrees/<name>`, when that folder is a git worktree in place — the main checkout is the coordinator's, and a builder
# resumed there would edit main's tree and read main's CLAUDE.md (W-6c7c3292) — and at the repo root otherwise; it
# resumes the agent's EXISTING session, and closing the terminal leaves them running. --print reports the grid and
# launches nothing: a `session <name>` line, then per builder `pane <name> <sid> <folder> <status>` and `run <name> <command>`.
#
# Names and session ids reach a shell command string, so the registry is validated first: a session id must be a
# lowercase UUID, a name must match [a-z0-9][a-z0-9-]{0,31}, no name may hold two session ids and no key may repeat;
# one bad row refuses the whole launch (exit 2) rather than silently leaving a builder out or resuming a stale session.
#
# A pane's status is `running` when a claude process already resumes that session — `--resume <sid>`, `-r <sid>` (a
# terminal) or `--resume=<sid>` (the VS Code extension) — and that pane only says so, because two processes on one
# session id fuse the transcript and the hooks; `no-transcript` when no transcript for the session sits under the
# project folder of the folder the pane starts in (claude resumes by that folder), which the pane still tries;
# otherwise `ok`.
#
# The environment goes INSIDE each pane's command, as an ALLOW-list (`env -i`): a pane gets the tmux SERVER's
# environment, and a server started from a VS Code session carries ~20 of that session's variables (CLAUDECODE, its
# session id, messaging socket and token, effort level, GIT_EDITOR, the VSCODE_* set) that every builder — and the
# shell a pane keeps after claude exits — would otherwise inherit; a deny-list missed most of them (review round 1).
set -u
export PATH="$HOME/.local/bin:$PATH"
export CLAUDE_CONFIG_DIR="$HOME/.claude-fleet/active"
export CLAUDE_QUOTA_HOME="$HOME/.claude-fleet/active"

print=0
if [ "${1:-}" = "--print" ]; then print=1; shift; fi
if [ $# -ne 1 ] || [ -z "$1" ]; then
  echo "usage: agents_up.sh [--print] <repo>" >&2
  exit 2
fi
if [ ! -d "$1" ]; then
  echo "agents_up: $1 is not a directory" >&2
  exit 2
fi
ROOT="$(cd -- "$1" && pwd -P)" || exit 2
REG="$ROOT/.fabrik/session-agents.json"
if [ ! -f "$REG" ]; then
  echo "agents_up: $REG does not exist — the repo names its agents there ({\"<session id>\": \"<name>\"}); the hub uses ~/bin/hub-up" >&2
  exit 2
fi

# "<name> <sid>" per builder, name-ordered; any malformed row refuses the launch
AGENTS="$(python3 - "$REG" <<'PY'
import json, re, sys

def no_repeats(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError(f"session id {key} appears twice")
        seen.add(key)
    return dict(pairs)

try:
    reg = json.load(open(sys.argv[1], encoding="utf-8"), object_pairs_hook=no_repeats)
except (OSError, ValueError) as exc:
    sys.exit(f"agents_up: {sys.argv[1]} is not a valid registry ({exc})")
if not isinstance(reg, dict):
    sys.exit(f"agents_up: {sys.argv[1]} must be an object of session id -> agent name")
rows = []
for sid, name in reg.items():
    if not re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", sid):
        sys.exit(f"agents_up: {sid!r} is not a session id (a lowercase UUID)")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", name):
        sys.exit(f"agents_up: {name!r} (session {sid}) is not an agent name ([a-z0-9][a-z0-9-]{{0,31}})")
    if name == "coordinator" or name.endswith("-coordinator"):
        continue
    rows.append((name, sid))
names = [n for n, _ in rows]
dup = sorted({n for n in names if names.count(n) > 1})
if dup:
    sys.exit(f"agents_up: {sys.argv[1]} gives {', '.join(dup)} more than one session id — remove the stale row")
if not rows:
    sys.exit(f"agents_up: {sys.argv[1]} names no builder (the coordinator gets no pane)")
for name, sid in sorted(rows):
    print(name, sid)
PY
)" || exit 2

# tmux reads `.`, `:` and glob characters in a target, so the session name keeps [A-Za-z0-9_-] only
base="$(basename "$ROOT")"
S="${base//[^A-Za-z0-9_-]/-}"
W=agents
# -ww: never cut at the terminal width — a VS Code process line runs to ~420 characters and `--resume=` sits past 280
RUNNING="$(ps -ww -C claude -o args= 2>/dev/null)"

# The builder's worktree only when it is a real one, in place: a git worktree (`.git` inside, so not a folder left behind
# by `git worktree remove`) whose physical path is exactly <root>/.claude/worktrees/<name>, so a symlink can neither take
# the pane out of the repo nor name a project folder claude never writes to. Anything else starts at the root.
dir_of() {  # $1 = name (validated: no `/` or `.`, so it names a folder directly under worktrees/)
  local d="$ROOT/.claude/worktrees/$1"
  if [ -d "$d" ] && [ -e "$d/.git" ] && [ "$(cd -- "$d" && pwd -P)" = "$d" ]; then echo "$d"; else echo "$ROOT"; fi
}

proj_of() {  # $1 = folder; claude stores a session under its start folder with every non-alphanumeric character as `-`
  echo "$CLAUDE_CONFIG_DIR/projects/${1//[^A-Za-z0-9]/-}"
}

status_of() {  # $1 = session id, $2 = the folder its pane starts in
  if printf '%s\n' "$RUNNING" | /usr/bin/grep -qE -- "(--resume[= ]|-r )$1( |\$)"; then
    echo running
  elif [ ! -f "$(proj_of "$2")/$1.jsonl" ]; then
    echo no-transcript
  else
    echo ok
  fi
}

cmd_of() {  # $1 = name, $2 = session id, $3 = status; name and id are validated above
  # HOME..LANG are read by the pane's own shell at run time (single-quoted here); the rest are fixed now
  local env
  env='env -i HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="$TERM" LANG="${LANG:-C.UTF-8}"'
  env="$env $(printf 'PATH=%q CLAUDE_CONFIG_DIR=%q CLAUDE_QUOTA_HOME=%q' "$PATH" "$CLAUDE_CONFIG_DIR" "$CLAUDE_QUOTA_HOME") CLAUDE_AGENT=$1"
  # the pane keeps a CLEAN shell after claude exits (or instead of it), so a crash never closes the pane and the
  # resume hint it prints runs with the pane's own environment, never the server's
  if [ "$3" = running ]; then
    echo "echo \"[$1 is already running elsewhere (session $2) — close it there, then run: claude -n $1 --resume $2]\"; exec $env bash -l"
  else
    echo "$env claude -n $1 --resume $2; echo; echo \"[$1 exited — run: claude -n $1 --resume $2]\"; exec $env bash -l"
  fi
}

if [ "$print" = 1 ]; then
  echo "session $S"
  while read -r name sid; do
    dir="$(dir_of "$name")"
    st="$(status_of "$sid" "$dir")"
    echo "pane $name $sid $dir $st"
    echo "run $name $(cmd_of "$name" "$sid" "$st")"
  done <<< "$AGENTS"
  exit 0
fi

# A session is named after the folder only, so a grid already up under this name must be THIS repo's. The root is
# recorded just after the session is created, so an empty owner may be a launch still building it: re-read once.
owned_here() {
  local owner
  owner="$(tmux show-options -t "=$S" -v @agents_up_root 2>/dev/null)"
  if [ -z "$owner" ]; then
    sleep 1
    owner="$(tmux show-options -t "=$S" -v @agents_up_root 2>/dev/null)"
  fi
  [ "$owner" = "$ROOT" ] && return 0
  echo "agents_up: tmux session $S belongs to ${owner:-something other than agents_up} — not attaching; kill or rename it first" >&2
  return 1
}

if tmux has-session -t "=$S" 2>/dev/null; then
  owned_here || exit 2
  echo "agents_up: the $S grid is already up — attaching as it is; a registry change takes effect after: tmux kill-session -t =$S" >&2
else
  first=1
  raced=0
  while read -r name sid; do
    dir="$(dir_of "$name")"
    st="$(status_of "$sid" "$dir")"
    [ "$st" = no-transcript ] && echo "agents_up: $name: no transcript for session $sid under $(proj_of "$dir") — the pane will try anyway" >&2
    cmd="$(cmd_of "$name" "$sid" "$st")"
    if [ "$first" = 1 ]; then
      if ! tmux new-session -d -s "$S" -n "$W" -c "$dir" -x 240 -y 60 "$cmd"; then
        # a second launch racing this one built the grid first: attach to it (if it is this repo's) rather than fail
        if tmux has-session -t "=$S" 2>/dev/null; then
          owned_here || exit 2
          raced=1
          break
        fi
        exit 1
      fi
      tmux set-option -t "=$S" @agents_up_root "$ROOT" >/dev/null ||
        echo "agents_up: could not record the root on $S — a relaunch will refuse this grid until it is killed" >&2
      first=0
    elif ! tmux split-window -t "=$S:$W" -c "$dir" "$cmd"; then
      echo "agents_up: no room for $name's pane — open it by hand: $cmd" >&2
      continue
    fi
    tmux select-layout -t "=$S:$W" even-horizontal >/dev/null
    tmux set -p -t "=$S:$W" @agent "$name"
  done <<< "$AGENTS"
  # a launch that lost the race leaves the other launch's grid as that launch arranges it
  [ "$raced" = 1 ] || tmux select-pane -t "=$S:$W.0"
fi
tmux source-file "$HOME/.tmux.conf" 2>/dev/null
# run from inside tmux (a hub pane), attaching would nest; switch the client instead
[ -n "${TMUX:-}" ] && exec tmux switch-client -t "=$S"
exec tmux attach -t "=$S"
