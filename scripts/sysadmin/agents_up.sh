#!/usr/bin/env bash
# AFTER-EDIT: docs/reference/repo-coordinator-rollout.md | tests/test_agents_up.py
# agents_up.sh [--print] <repo> — open a repo's builder agents side by side in one tmux window (D-1031).
#
# Every repo's launcher — the hub's too once its registry is seeded (W-66e2f6a7 retires ~/bin/hub-up). The builders come
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
# The session id each builder resumes (W-66e2f6a7) comes from the identity store ($AGENT_IDENTITY_FILE, else
# ~/.claude/state/agent-identity.jsonl), read the way whoami_agent.py reads it: a regular file only, every row with a
# session id, and a session belongs to the name on its LAST row anywhere in the store (`resolve_agent_name`). A
# builder's binding is the LAST line, in file order, naming it in this repo's scope (`toplevel` = the git common dir)
# whose session still belongs to it. The binding replaces the registry's id unless that session was active after the
# binding was written (its transcript's mtime is later than the binding's `at` — the store trims rows after 30 days
# and never sees a session the launcher started, so absence from the store is no evidence of age), or the registry's
# id is itself the binding. With no binding, no readable store or no git scope, the registry's id stands; each case is
# said on stderr. A name the registry lists twice with no binding refuses, and so does any session that would serve
# two panes — the coordinator's sessions included.
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
SELF="$(cd -- "$(dirname -- "$0")" && pwd -P)/$(basename -- "$0")"
REG="$ROOT/.fabrik/session-agents.json"
if [ ! -f "$REG" ]; then
  echo "agents_up: $REG does not exist — the repo names its agents there ({\"<session id>\": \"<name>\"}), once; each builder's session comes from its whoami binding" >&2
  exit 2
fi

# "agent <name> <sid>" per builder, name-ordered, then "known <sid>" for every session the registry or the store gives
# this repo (the newer-transcript warning skips those); any malformed registry row refuses the launch. The scope query
# runs with git's own location variables unset, so a GIT_DIR inherited from a hook or an IDE cannot redirect it.
SCOPE="$(env -u GIT_DIR -u GIT_COMMON_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || SCOPE=""
STORE="${AGENT_IDENTITY_FILE:-$HOME/.claude/state/agent-identity.jsonl}"
case "$STORE" in /*) ;; *) STORE="$PWD/$STORE" ;; esac
RESOLVED="$(python3 - "$REG" "$SCOPE" "$STORE" "$ROOT" "$CLAUDE_CONFIG_DIR" <<'PY'
import json, os, re, sys

SID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
WHOAMI_NAME = re.compile(r"[a-z0-9-]{1,32}")  # whoami_agent.py::_NAME_RE — the names its reader honours
reg_path, scope, store, root, config = sys.argv[1:6]

def note(msg):
    print(f"agents_up: {msg}", file=sys.stderr)

def coordinator(name):
    return name == "coordinator" or name.endswith("-coordinator")

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
ids, coord_ids = {}, set()  # builder name -> its registry session ids (file order); the coordinator's ids
for sid, name in reg.items():
    if not SID.fullmatch(sid):
        sys.exit(f"agents_up: {sid!r} is not a session id (a lowercase UUID)")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        sys.exit(f"agents_up: {name!r} (session {sid}) is not an agent name ([a-z0-9][a-z0-9-]{{0,31}})")
    if coordinator(name):
        coord_ids.add(sid)
        continue
    ids.setdefault(name, []).append(sid)
if not ids:
    sys.exit(f"agents_up: {reg_path} names no builder (the coordinator gets no pane)")

def at_of(row):  # whoami_agent.py::_at — never raises; an uncoercible time is 0
    try:
        return int(row.get("at") or 0)
    except (TypeError, ValueError, OverflowError):
        return 0

rows = []  # whoami_agent.py::_rows — every parseable row with a session id, file order
if not scope:
    note(f"{root} has no git scope — the identity store is not read; the registry's ids stand")
elif os.path.lexists(store) and not os.path.isfile(store):
    note(f"the identity store {store} is not a regular file — the registry's ids stand")
elif os.path.isfile(store):
    try:
        with open(store, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("session_id"):
                    rows.append(r)
    except OSError as exc:
        note(f"the identity store {store} could not be read ({exc.strerror or exc}) — the registry's ids stand")
        rows = []
owner = {}  # session id -> the name on its LAST row anywhere in the store (whoami_agent.py::resolve_agent_name)
for r in rows:
    sid, name = str(r.get("session_id")), str(r.get("name") or "")
    if WHOAMI_NAME.fullmatch(name):
        owner[sid] = name
binding = {}  # builder name -> (sid, at) of the LAST line naming it in this scope whose session it still owns
for r in rows:
    sid, name = r.get("session_id"), r.get("name")
    if r.get("toplevel") != scope or not isinstance(sid, str) or not SID.fullmatch(sid):
        continue
    if isinstance(name, str) and owner.get(sid) == name:
        binding[name] = (sid, at_of(r))

def proj(folder):  # claude files a session under its start folder with every non-alphanumeric character as `-`
    return os.path.join(config, "projects", re.sub(r"[^A-Za-z0-9]", "-", folder))

def active_at(name, sid):  # the newest mtime of the session's transcript under the folders its pane can start in
    best = None
    for folder in (root, os.path.join(root, ".claude", "worktrees", name)):
        try:
            m = os.stat(os.path.join(proj(folder), sid + ".jsonl")).st_mtime
        except OSError:
            continue
        best = m if best is None or m > best else best
    return best

chosen = {}
for name in sorted(ids):
    regs, b = ids[name], binding.get(name)
    if b is None:
        if len(regs) > 1:
            sys.exit(f"agents_up: {reg_path} gives {name} more than one session id and the identity store names none — remove the stale row")
        if scope and owner.get(regs[0], name) != name:
            note(f"{name}: the registry's {regs[0]} is bound to {owner[regs[0]]} — resuming it anyway (no binding for {name})")
        elif scope:
            note(f"{name}: no whoami binding in {scope} — resuming the registry's {regs[0]}")
        chosen[name] = regs[0]
        continue
    new, new_at = b
    if new in regs and len(regs) == 1:
        chosen[name] = new
        continue
    if len(regs) == 1 and owner.get(regs[0], name) == name:
        seen_at = active_at(name, regs[0])
        if seen_at is not None and seen_at > new_at:
            note(f"{name}: the registry's {regs[0]} was active after its binding {new} — resuming {regs[0]}")
            chosen[name] = regs[0]
            continue
    note(f"{name}: resuming {new}, its newest whoami binding, not the registry's {' or '.join(r for r in regs if r != new)}")
    chosen[name] = new
holders = {sid: ["coordinator"] for sid in coord_ids}
for name, sid in chosen.items():
    holders.setdefault(sid, []).append(name)
for sid, names in sorted(holders.items()):
    if len(names) > 1:
        sys.exit(f"agents_up: session {sid} would serve {' and '.join(sorted(names))} — two processes on one session fuse it; fix the registry or re-bind")
for name in sorted(chosen):
    print("agent", name, chosen[name])
for sid in sorted(set(reg) | {str(r.get("session_id")) for r in rows}):
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
  newest="$(ls -t -- "$proj"/*.jsonl 2>/dev/null | /usr/bin/grep -E -m 1 '/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.jsonl$')"
  [ -n "$newest" ] || return 0
  base="$(basename -- "$newest" .jsonl)"
  [ "$base" = "$2" ] && return 0
  printf '%s\n' "$KNOWN" | /usr/bin/grep -qxF -- "$base" && return 0
  echo "agents_up: $1: a newer session $base is in $proj — if it is $1's, run there: python3 /opt/fabrik/scripts/whoami_agent.py --as $1 --force" >&2
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
  [ -n "${AGENT_IDENTITY_FILE:-}" ] && env="$env $(printf 'AGENT_IDENTITY_FILE=%q' "$STORE")"
  # the pane keeps a CLEAN shell after claude exits (or instead of it), so a crash never closes the pane and the
  # resume hint it prints runs with the pane's own environment, never the server's
  if [ "$3" = running ]; then
    echo "echo \"[$1 is already running elsewhere (session $2) — close it there, then run: claude -n $1 --resume $2]\"; exec $env bash -l"
  else
    echo "$env claude -n $1 --resume $2; echo; echo \"[$1 exited — run: claude -n $1 --resume $2 (after a /clear: whoami_agent.py --as $1 --force, then $SELF $ROOT)]\"; exec $env bash -l"
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
