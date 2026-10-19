#!/usr/bin/env bash
# AFTER-EDIT: docs/reference/repo-coordinator-rollout.md | tests/test_agents_up.py
# agents_up.sh [--print] <repo> — open a repo's builder agents side by side in one tmux window (D-1031).
#
# Every repo's launcher, the hub's included (W-66e2f6a7 retires the hub's hand-made ~/bin/hub-up). The builders come
# from the repo's own registry, <repo>/.fabrik/session-agents.json ({"<session id>": "<agent name>"}), and each one's
# session id from the identity store `whoami_agent.py` keeps (below), so a /clear followed by the documented re-bind
# (`whoami_agent.py --as <name> --force`) needs no registry or launcher edit. The coordinator gets no pane (a name equal
# to `coordinator` or ending in `-coordinator`): the operator reaches it in VS Code. A pane starts in the builder's own worktree,
# `<repo>/.claude/worktrees/<name>`, when that folder is a git worktree in place — the main checkout is the coordinator's, and a builder
# resumed there would edit main's tree and read main's CLAUDE.md (W-6c7c3292) — and at the repo root otherwise; it
# resumes the agent's EXISTING session, and closing the terminal leaves them running. --print reports the grid and
# launches nothing: a `session <name>` line, then per builder `pane <name> <sid> <folder> <status>` and `run <name> <command>`.
#
# Names and session ids reach a shell command string, so the registry is validated first: a session id must be a
# lowercase UUID, a name must match [a-z0-9][a-z0-9-]{0,31} and no key may repeat; one bad row refuses the whole launch
# (exit 2) rather than silently leaving a builder out or resuming a stale session.
#
# The session id each builder resumes (W-66e2f6a7): the newest binding of its name in the identity store
# ($AGENT_IDENTITY_FILE, else ~/.claude/state/agent-identity.jsonl — whoami_agent.py::store_path) whose `toplevel` is
# this repo's git common dir, counting only a row that is still the LAST row for its session (whoami's own reader:
# a session re-bound to another name is that other name's), ties on `at` going to the later line. It replaces the
# registry's id when that id is an older binding of the name, or when the registry lists the name twice; a registry id
# the store does not know stands (it is newer than anything the store saw), and so does the registry when the store
# has no binding, cannot be read, or the repo has no git scope — each said on stderr. A name listed twice with no
# binding still refuses, and two builders resolving to one session refuse, as a repeated key does.
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
  echo "agents_up: $REG does not exist — the repo names its agents there ({\"<session id>\": \"<name>\"}), once; each builder's session comes from its whoami binding" >&2
  exit 2
fi

# "<name> <sid>" per builder, name-ordered, then "known <sid>" for every session the registry or the store gives this
# repo (the newer-transcript warning skips those); any malformed registry row refuses the launch
SCOPE="$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || SCOPE=""
STORE="${AGENT_IDENTITY_FILE:-$HOME/.claude/state/agent-identity.jsonl}"
RESOLVED="$(python3 - "$REG" "$SCOPE" "$STORE" <<'PY'
import json, re, sys

SID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
reg_path, scope, store = sys.argv[1], sys.argv[2], sys.argv[3]

def note(msg):
    print(f"agents_up: {msg}", file=sys.stderr)

def no_repeats(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError(f"session id {key} appears twice")
        seen.add(key)
    return dict(pairs)

try:
    reg = json.load(open(reg_path, encoding="utf-8"), object_pairs_hook=no_repeats)
except (OSError, ValueError) as exc:
    sys.exit(f"agents_up: {reg_path} is not a valid registry ({exc})")
if not isinstance(reg, dict):
    sys.exit(f"agents_up: {reg_path} must be an object of session id -> agent name")
ids = {}  # builder name -> its registry session ids, in file order
for sid, name in reg.items():
    if not SID.fullmatch(sid):
        sys.exit(f"agents_up: {sid!r} is not a session id (a lowercase UUID)")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        sys.exit(f"agents_up: {name!r} (session {sid}) is not an agent name ([a-z0-9][a-z0-9-]{{0,31}})")
    if name == "coordinator" or name.endswith("-coordinator"):
        continue
    ids.setdefault(name, []).append(sid)
if not ids:
    sys.exit(f"agents_up: {reg_path} names no builder (the coordinator gets no pane)")

def coerce_at(v):  # whoami_agent.py::_at — a non-bool int or a digit string; anything else is no time
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.isdigit():
        return int(v)
    return None

rows = []  # (line no, sid, name, at) of this scope's well-formed rows, file order
if not scope:
    note(f"{reg_path.rsplit('/.fabrik/', 1)[0]} has no git scope — the identity store is not read; the registry's ids stand")
else:
    try:
        with open(store, encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(r, dict) or r.get("toplevel") != scope:
                    continue
                sid, name, at = r.get("session_id"), r.get("name"), coerce_at(r.get("at"))
                if isinstance(sid, str) and SID.fullmatch(sid) and isinstance(name, str) and NAME.fullmatch(name) and at is not None:
                    rows.append((i, sid, name, at))
    except Exception as exc:  # a store that cannot be read is no store: the registry stands
        if not isinstance(exc, FileNotFoundError):
            note(f"the identity store {store} could not be read ({type(exc).__name__}) — the registry's ids stand")
        rows = []
last_name = {}  # session id -> the name of its LAST row: whoami's own reader
for _, sid, name, _ in rows:
    last_name[sid] = name
bound = {}  # builder name -> (at, line, sid) of its newest counted row
seen = {}  # builder name -> every session id this scope ever bound it to
for i, sid, name, at in rows:
    seen.setdefault(name, set()).add(sid)
    if last_name[sid] != name:
        continue  # re-bound to another name since: never this name's
    if name not in bound or (at, i) >= bound[name][:2]:
        bound[name] = (at, i, sid)
chosen = {}
for name in sorted(ids):
    regs, b = ids[name], bound.get(name)
    if b is None:
        if len(regs) > 1:
            sys.exit(f"agents_up: {reg_path} gives {name} more than one session id and the identity store names none — remove the stale row")
        if scope:
            note(f"{name}: no whoami binding in {scope} — resuming the registry's {regs[0]}")
        chosen[name] = regs[0]
        continue
    new = b[2]
    if len(regs) > 1 or regs[0] == new or regs[0] in seen.get(name, set()):
        if new not in regs or len(regs) > 1:
            note(f"{name}: resuming {new}, its newest whoami binding, not the registry's {' or '.join(r for r in regs if r != new)}")
        chosen[name] = new
    else:
        note(f"{name}: the registry's {regs[0]} is not in the identity store — resuming it, not the binding {new}")
        chosen[name] = regs[0]
holders = {}
for name, sid in chosen.items():
    holders.setdefault(sid, []).append(name)
clash = sorted((sid, names) for sid, names in holders.items() if len(names) > 1)
if clash:
    sid, names = clash[0]
    sys.exit(f"agents_up: session {sid} would serve {' and '.join(sorted(names))} — two panes on one session fuse it; fix the registry or re-bind")
for name in sorted(chosen):
    print("agent", name, chosen[name])
for sid in sorted(set(reg) | {sid for _, sid, _, _ in rows}):
    print("known", sid)
PY
)" || exit 2
AGENTS="$(printf '%s\n' "$RESOLVED" | sed -n 's/^agent //p')"
KNOWN="$(printf '%s\n' "$RESOLVED" | sed -n 's/^known //p')"

# tmux reads `.`, `:` and glob characters in a target, so the session name keeps [A-Za-z0-9_-] only
base="$(basename "$ROOT")"
S="${base//[^A-Za-z0-9_-]/-}"
W=agents
# -ww: never cut at the terminal width — a VS Code process line runs to ~420 characters and `--resume=` sits past 280
RUNNING="$(ps -ww -C claude -o args= 2>/dev/null)"

# The builder's worktree only when it is a linked git worktree in place: a `.git` FILE inside (the shape `git worktree
# add` makes, so neither a folder left behind by `git worktree remove` nor a nested clone) and a physical path exactly
# <root>/.claude/worktrees/<name>, so a symlink anywhere on it can neither take the pane out of the repo nor name a
# project folder claude never writes to. Anything else starts at the root — said on stderr when something by that name
# is there, because a builder resumed at the root works in the coordinator's checkout.
dir_of() {  # $1 = name (validated: no `/` or `.`, so it names a folder directly under worktrees/)
  local d="$ROOT/.claude/worktrees/$1"
  if [ -d "$d" ] && [ -f "$d/.git" ] && [ "$(cd -- "$d" && pwd -P)" = "$d" ]; then
    echo "$d"
    return
  fi
  if [ -e "$d" ] || [ -L "$d" ]; then
    echo "agents_up: $1: .claude/worktrees/$1 is not a linked git worktree in place — its pane starts at the repo root, the main checkout" >&2
  fi
  echo "$ROOT"
}

proj_of() {  # $1 = folder; claude stores a session under its start folder with every non-alphanumeric character as `-`
  echo "$CLAUDE_CONFIG_DIR/projects/${1//[^A-Za-z0-9]/-}"
}

newer_unbound() {  # $1 = name, $2 = session id, $3 = the folder its pane starts in: a /clear without the re-bind
  local proj newest base
  proj="$(proj_of "$3")"
  [ -f "$proj/$2.jsonl" ] || return 0
  newest="$(ls -t -- "$proj"/*.jsonl 2>/dev/null | head -n 1)"
  [ -n "$newest" ] || return 0
  base="$(basename -- "$newest" .jsonl)"
  [ "$base" = "$2" ] && return 0
  printf '%s\n' "$KNOWN" | /usr/bin/grep -qxF -- "$base" && return 0
  echo "agents_up: $1: a newer session $base is in $proj — if it is $1's, run whoami_agent.py --as $1 there" >&2
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
  # the store the launcher read: the panes' whoami must write the same one, or the next launch never sees the re-bind
  [ -n "${AGENT_IDENTITY_FILE:-}" ] && env="$env $(printf 'AGENT_IDENTITY_FILE=%q' "$AGENT_IDENTITY_FILE")"
  # the pane keeps a CLEAN shell after claude exits (or instead of it), so a crash never closes the pane and the
  # resume hint it prints runs with the pane's own environment, never the server's
  if [ "$3" = running ]; then
    echo "echo \"[$1 is already running elsewhere (session $2) — close it there, then run: claude -n $1 --resume $2]\"; exec $env bash -l"
  else
    echo "$env claude -n $1 --resume $2; echo; echo \"[$1 exited — run: claude -n $1 --resume $2 (after a /clear, run $(printf %q "$0") $(printf %q "$ROOT") again)]\"; exec $env bash -l"
  fi
}

if [ "$print" = 1 ]; then
  echo "session $S"
  while read -r name sid; do
    dir="$(dir_of "$name")"
    st="$(status_of "$sid" "$dir")"
    newer_unbound "$name" "$sid" "$dir"
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
  # a grid a hand-built launcher made (fabrik-lib's ~/bin/fabrik-lib-up) records no root but tags each pane with its
  # agent: adopt it when every pane is one of THIS repo's builders, so moving to the generated launcher never shows an
  # error pane; any other unrecorded session is still refused (W-bb6c9d9a)
  if [ -z "$owner" ] && adoptable; then
    tmux set-option -t "=$S" @agents_up_root "$ROOT" >/dev/null
    echo "agents_up: adopted the $S grid a hand-built launcher made — every pane is one of this repo's builders" >&2
    # its panes were started without this script's env allow-list, so they may carry the VS Code session's variables
    echo "agents_up: those panes keep the environment they started with; for clean panes: tmux kill-session -t =$S, then launch again" >&2
    return 0
  fi
  echo "agents_up: tmux session $S belongs to ${owner:-something other than agents_up} — not attaching; kill or rename it first" >&2
  return 1
}

adoptable() {  # every pane of the session carries an @agent that names one of this repo's builders
  local panes id p
  # the pane id leads each line: `$(...)` drops trailing empty lines, so a bare tag list would lose an untagged pane
  panes="$(tmux list-panes -s -t "=$S" -F '#{pane_id} #{@agent}' 2>/dev/null)" || return 1
  [ -n "$panes" ] || return 1
  while read -r id p; do
    # names are validated [a-z0-9-] above, so a pane tag outside that set is never a builder
    [[ "$p" =~ ^[a-z0-9][a-z0-9-]*$ ]] || return 1
    printf '%s\n' "$AGENTS" | /usr/bin/grep -q -- "^$p " || return 1
  done <<< "$panes"
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
    newer_unbound "$name" "$sid" "$dir"
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
