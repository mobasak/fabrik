#!/usr/bin/env bash
# AFTER-EDIT: docs/reference/repo-coordinator-rollout.md | tests/test_agents_up.py
# agents_up.sh [--print] <repo> — open a repo's builder agents side by side in one tmux window (D-1031).
#
# The per-repo form of ~/bin/hub-up, which stays as it is for the hub. The builders come from the repo's own
# registry, <repo>/.fabrik/session-agents.json ({"<session id>": "<agent name>"}), so a session-id change is one
# registry edit, never a launcher edit. The coordinator gets no pane (a name equal to `coordinator` or ending in
# `-coordinator`): the operator reaches it in VS Code, as hub-up states. Every pane starts at the repo root and resumes
# the agent's EXISTING session; closing the terminal leaves them running. --print reports the grid and launches nothing:
# a `session <name>` line, then per builder `pane <name> <sid> <repo root> <status>` and `run <name> <command>`.
#
# Names and session ids reach a shell command string, so the registry is validated first: a session id must be a
# lowercase UUID, a name must match [a-z0-9][a-z0-9-]{0,31}, no name may hold two session ids and no key may repeat;
# one bad row refuses the whole launch (exit 2) rather than silently leaving a builder out or resuming a stale session.
#
# A pane's status is `running` when a claude process already resumes that session — in either argv form, `--resume
# <sid>` (a terminal) or `--resume=<sid>` (the VS Code extension) — and that pane only says so, because two processes
# on one session id fuse the transcript and the hooks; `no-transcript` when no transcript for the session sits under
# the repo root's project folder (claude resumes by the folder it starts in; the user-level worktree_transcript_link.py
# hook links a worktree session's transcript there), which the pane still tries; otherwise `ok`.
#
# The environment goes INSIDE each pane's command, never via exports alone: a pane gets the tmux SERVER's environment,
# and a server started from a VS Code session carries that session's identity (CLAUDECODE, CLAUDE_CODE_SESSION_ID, its
# messaging socket), which every builder would otherwise inherit.
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
ROOT="$(cd "$1" && pwd -P)"
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
# claude stores a session under its start folder with every non-alphanumeric character as `-`
PROJ="$CLAUDE_CONFIG_DIR/projects/${ROOT//[^A-Za-z0-9]/-}"
RUNNING="$(ps -C claude -o args= 2>/dev/null)"

status_of() {  # $1 = session id
  if printf '%s\n' "$RUNNING" | /usr/bin/grep -qE -- "--resume[= ]$1( |\$)"; then
    echo running
  elif [ ! -f "$PROJ/$1.jsonl" ]; then
    echo no-transcript
  else
    echo ok
  fi
}

cmd_of() {  # $1 = name, $2 = session id, $3 = status; name and id are validated above
  local env
  env="env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_CODE_MESSAGING_SOCKET -u CLAUDE_PID -u CLAUDE_CODE_CHILD_SESSION"
  env="$env $(printf 'PATH=%q CLAUDE_CONFIG_DIR=%q CLAUDE_QUOTA_HOME=%q' "$PATH" "$CLAUDE_CONFIG_DIR" "$CLAUDE_QUOTA_HOME") CLAUDE_AGENT=$1"
  if [ "$3" = running ]; then
    echo "echo \"[$1 is already running elsewhere (session $2) — close it there, then run: CLAUDE_AGENT=$1 claude -n $1 --resume $2]\"; exec bash -l"
  else
    # the pane keeps a shell after claude exits, so a crash never closes the pane
    echo "$env claude -n $1 --resume $2; echo; echo \"[$1 exited — run: CLAUDE_AGENT=$1 claude -n $1 --resume $2]\"; exec bash -l"
  fi
}

if [ "$print" = 1 ]; then
  echo "session $S"
  while read -r name sid; do
    st="$(status_of "$sid")"
    echo "pane $name $sid $ROOT $st"
    echo "run $name $(cmd_of "$name" "$sid" "$st")"
  done <<< "$AGENTS"
  exit 0
fi

if ! tmux has-session -t "=$S" 2>/dev/null; then
  first=1
  while read -r name sid; do
    st="$(status_of "$sid")"
    [ "$st" = no-transcript ] && echo "agents_up: $name: no transcript for session $sid under $PROJ — the pane will try anyway" >&2
    cmd="$(cmd_of "$name" "$sid" "$st")"
    if [ "$first" = 1 ]; then
      tmux new-session -d -s "$S" -n "$W" -c "$ROOT" -x 240 -y 60 "$cmd" || exit 1
      first=0
    elif ! tmux split-window -t "=$S:$W" -c "$ROOT" "$cmd"; then
      echo "agents_up: no room for $name's pane — open it by hand: $cmd" >&2
      continue
    fi
    tmux select-layout -t "=$S:$W" even-horizontal >/dev/null
    tmux set -p -t "=$S:$W" @agent "$name"
  done <<< "$AGENTS"
  tmux select-pane -t "=$S:$W.0"
fi
tmux source-file "$HOME/.tmux.conf" 2>/dev/null
exec tmux attach -t "=$S"
