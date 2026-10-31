#!/usr/bin/env bash
# AFTER-EDIT: docs/reference/repo-coordinator-rollout.md | tests/test_agents_up.py
# agents_up.sh [--print] [--detach] [--tab] <repo> — open a repo's builder agents side by side, four per tmux window (D-1031). Also: agents_up.sh [--tab] --window <n> <repo>. Also: agents_up.sh rotate-session <name> [--compact FOCUS | --move] [--trigger T] (W-f975fee0, W-e38f8ee7).
#
# Every repo's launcher (W-66e2f6a7 retired ~/bin/hub-up). The builders come from the repo's own registry,
# <repo>/.fabrik/session-agents.json ({"<session id>": "<agent name>"}), when it has one, and otherwise from the identity
# store `whoami_agent.py` keeps (below): every name bound in this repo's git scope (W-89474fc1 — 7 of 9 agent repos
# never wrote a registry). Each one's session id comes from its binding, so a /clear followed by the documented
# re-bind (`whoami_agent.py --as <name> --force`) needs no registry or launcher edit. The coordinator gets no pane: a
# name equal to `coordinator` or ending in `-coordinator`, or the repo's declared merge owner (`decisions.py
# --merge-owner`, read from the repo's own ledger, never from position); the operator reaches it in VS Code. A pane
# starts ONLY in a linked git worktree in place under `<repo>/.claude/worktrees/` — the main checkout is the
# coordinator's, and a builder resumed there would edit main's tree and read main's CLAUDE.md (W-6c7c3292): the one
# worktree whose claude project folder holds the builder's session (W-456aa02a: Claude Code keeps the folder a pane
# STARTED in as its CLAUDE_PROJECT_DIR — hooks, settings, permissions — after the session moves into another worktree,
# so a pane started by name ran a stale tree's hooks), else `<name>`; a name with neither gets no pane (said on stderr),
# and no builder left refuses (exit 3, nothing to launch). It resumes the agent's EXISTING session, and closing the terminal leaves them running. --print reports
# the grid and launches nothing: a `session <name>` line, a `slice <name> MemoryHigh=<v> MemoryMax=<v>` line, then per
# builder `pane <name> <sid> <folder> <status>`, `cap <name> <TasksMax>` (or `cap <name> uncapped`) and `run <name>
# <command>`. --detach builds the grid (or finds it up) and never attaches (the boot sweep and cron have no terminal);
# a caller with no terminal on stdin/stdout detaches the same way and says so (W-1961cc42). --tab is the desktop
# launcher's form (W-df2e24ed): a Windows Terminal tab closes when its command exits 0, so under --tab a missing terminal
# is exit 1 (4 when a builder got no pane) with the reason, never the silent detach, and any non-zero exit before the
# attach — an argument error or a signal (128+signal) included — prints one "stopped" line; the attach itself is an exec,
# so a failing attach shows tmux's (or bash's) own error instead; it takes none of --print, --detach and --pane-cmd.
#
# Window layout (W-b9ad80ae D4): four panes per window — `agents` holds the first four builders, `agents-2` the next four,
# `agents-3` the next, and so on (a pane that cannot be created is said and the next builder takes its slot). Each
# overflow window `agents-<k>` is shown in its own tmux session `<S>+<k>`, grouped with the base session `<S>`, so a
# separate terminal tab can attach it; `+` is outside the base-name alphabet, so such a session is this repo's by
# construction. A new grid start, once its own session exists, kills every stale `<S>+<k>`, and makes no overflow session while another stale session holds the group name `<S>` (it says which, and the kill-session that frees it). `agents_up.sh --window <n> <repo>` (n >= 2) waits
# (FABRIK_AGENTS_WINDOW_WAIT_S, 120 s) while the grid is absent or a live builder is still building it
# (`@agents_up_building` holds that builder's `<pid>:<start time>`), then attaches `=<S>+<n>`; with no window `agents-<n>` it says so and
# attaches `=<S>` and creates nothing (it kills a stale `<S>+<n>` left for the vanished window).
#
# Every pane runs WHOLE — claude, its exit hint and the shell it keeps — in its own `systemd-run --user --scope` in
# fabrik-agents.slice, with MemorySwapMax=0 and TasksMax ($FABRIK_AGENT_TASKS_MAX, 1024) and NO MemoryMax of its own
# ($FABRIK_AGENT_MEM_MAX is retired: warned about, ignored; a pane OOM-killed at 3G lost a review's seats). The parent
# slice is the one ceiling, re-asserted at each new grid, never by --print: MemoryHigh = MemTotal - max(4G, floor) and
# MemoryMax = MemTotal - max(2G, floor - 2G), whole G, floor = $FABRIK_AGENT_NONAGENT_FLOOR (12G; W-0b8a0fba), MemTotal
# read from $FABRIK_PROC_ROOT/meminfo (/proc); under 8G or unreadable keeps D-1075's 16G
# MemoryMax and says so (a floor that leaves nothing uses the minimum margins MemTotal-4G / MemTotal-2G instead); $FABRIK_AGENT_SLICE_MAX still overrides the derived MemoryMax. The slice sits under fabrik.slice
# and fabrik-agents-tests.slice (capped_run.sh) nests under it by the dashed name. No reachable user manager: the
# interactive path REFUSES (exit 2) unless FABRIK_AGENTS_UNCAPPED=1, and --detach (the boot path) launches uncapped
# with D-1075's warning on stderr AND inside each pane; a manager that answers but refuses the ceiling refuses the
# launch (exit 2), as capped_run.sh does. Each pane runs `claude -n <name> --permission-mode bypassPermissions --resume
# <sid> "<wake prompt>"` with CLAUDE_CODE_RETRY_WATCHDOG=1 and oom_score_adj 200 (W-6e656dac L1/L4/L5); the mode is passed
# because a --resume keeps the session's saved mode (operator ruling 2026-10-30). Cobra (D-253): the cheapest pass is a pane that only LOOKS capped, or an
# FABRIK_AGENTS_UNCAPPED=1 left in a profile; the test stub records the systemd-run argv the pane really runs, and the
# override is said on stderr at every launch that uses it.
#
# Exit codes: 0 done; 1 tmux failed (no session made, or no window and pane id for the first pane); 2 a refusal (a
# malformed registry row, an unreadable ledger or identity store, a refused ceiling, a worktree gone before launch); 3
# NOTHING TO LAUNCH — a registry naming only a coordinator, or bindings with no builder worktree (W-b9ad80ae D4) — so a
# caller can tell an empty repo from a refusal; 4 SOME PANE NOT OPENED — the grid is up but at least one builder got no
# pane ("no room for <name>'s pane (session <sid>)" on stderr, one line each), so the boot sweep never records that
# session relaunched (T04 residue 3). An interactive attach still attaches after saying so; every other path exits 4.
#
# Every claude call carries --settings '{"skillOverrides":{"auto-mode-setup":"off"},"spinnerTipsEnabled":false}' and every pane's
# env CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1: no "Teach auto mode" dialog, no spinner tips, no survey (probed live on
# claude 2.1.312; spec D3). A spawner-bound session (T01's `whoami_agent.py --spawned` row, `spawned: true`) with no
# transcript in ANY project folder launches `claude -n <name> --permission-mode bypassPermissions --session-id <sid> --settings … "<first prompt>"`
# instead of --resume (the resolver's 4th field). `agents_up.sh --pane-cmd <repo> <name> <sid> [--new] [--coordinator <name>]
# [--item <W-id>]` prints that one pane command (the same cmd_of the grid runs) and launches nothing; its form `--pane-cmd
# <repo> <name> <sid> --into <folder> --from <old sid> --replacing <pid>` prints the FRESH `--session-id` launch
# `rotate-session --move` respawns a builder's pane with, in the worktree it works in (W-e38f8ee7); FABRIK_SPAWN_NAME /
# _COORDINATOR / _ITEM name the coordinator and item in the first prompt of a builder a --detach start launches.
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
# terminal) or `--resume=<sid>` (the VS Code extension) — or runs `-n <name>` with its cwd in the pane's folder (a
# --session-id launch carries no --resume), and that pane only says so, because two processes on one
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

# `agents_up.sh rotate-session <name> [--compact FOCUS | --move] [--trigger T]` (W-f975fee0, D-1135): the coordinator's
# verb — rotate_session.py checks the pane and writes one request; the fabrik-rotate user unit types it (`--move`,
# W-e38f8ee7: respawns the pane with a fresh session in the worktree the builder works in). Dispatched before the
# grid's own arguments; the repo is the caller's git toplevel.
if [ "${1:-}" = "rotate-session" ]; then
  shift
  exec python3 "$(cd "$(dirname "$0")" && pwd)/rotate_session.py" request "$@"
fi
# `agents_up.sh add <repo> <name> [--role <role>] [--item <W-id>]` (W-b9ad80ae D1, D2): the coordinator's spawn verb —
# agents_spawn.py makes the builder's worktree, binding and item under the repo's agents lock. Dispatched the same way.
if [ "${1:-}" = "add" ]; then
  shift
  exec python3 "$(cd "$(dirname "$0")" && pwd)/agents_spawn.py" add "$@"
fi
# `agents_up.sh remove <repo> <name>` (W-b9ad80ae D7): the retire verb — agents_spawn.py checks nothing would be lost,
# then kills the pane, removes the worktree and drops the registry row under the same lock. Dispatched the same way.
if [ "${1:-}" = "remove" ]; then
  shift
  exec python3 "$(cd "$(dirname "$0")" && pwd)/agents_spawn.py" remove "$@"
fi

print=0
detach=0
tab=0
panecmd=0
# ONE exit handler (bash keeps a single EXIT trap), installed before the flags are read so an argument error counts too:
# start_grid's building-flag cleanup while BUILDING=1, and under --tab the line that keeps a failed tab readable. The
# attach and switch-client are execs, so the handler never runs for them, whether they succeed or fail (tmux, or bash
# when tmux cannot be run, then prints its own error).
BUILDING=0
on_exit() {
  local rc=$?
  [ "$BUILDING" = 1 ] && tmux set-option -t "=$S:" -u @agents_up_building >/dev/null 2>&1
  if [ "$tab" = 1 ] && [ "$rc" != 0 ]; then
    echo "agents_up: stopped (exit $rc) before attaching — the reason is above; this tab stays open" >&2
  fi
  return 0
}
trap on_exit EXIT
winn=""
# --tab is seen wherever it stands, so an argument error before it (or a --tab after the repo) still prints the line
for a in "$@"; do [ "$a" = --tab ] && tab=1; done
while [ $# -gt 0 ]; do
  case "$1" in
    --print) print=1; shift ;;
    --detach) detach=1; shift ;;
    --tab) tab=1; shift ;;
    --pane-cmd) panecmd=1; shift ;;
    --window)
      if [ -n "$winn" ]; then echo "usage: agents_up.sh --window <n> <repo>   (--window is given once)" >&2; exit 2; fi
      # n is an integer >= 2: window 1 is `agents` itself, attached by a plain launch (W-b9ad80ae D5)
      if [ $# -lt 2 ] || ! [[ "$2" =~ ^[0-9]{1,6}$ ]] || [ "$((10#$2))" -lt 2 ]; then
        echo "usage: agents_up.sh --window <n> <repo>   (n is an integer, 2 or more)" >&2
        exit 2
      fi
      winn="$((10#$2))"; shift 2 ;;
    *) break ;;
  esac
done
if [ -n "$winn" ] && { [ "$print" = 1 ] || [ "$detach" = 1 ] || [ "$panecmd" = 1 ]; }; then
  echo "agents_up: --window is its own mode: it takes none of --print, --detach and --pane-cmd" >&2
  exit 2
fi
if [ "$tab" = 1 ] && { [ "$print" = 1 ] || [ "$detach" = 1 ] || [ "$panecmd" = 1 ]; }; then
  echo "agents_up: --tab is the launcher's attach form: it takes none of --print, --detach and --pane-cmd" >&2
  exit 2
fi
# under --tab a signal ends the run with 128+signal, so the stopped line names it (bash would hand the EXIT trap the
# last command's status); without --tab a signal is left to bash, as before
if [ "$tab" = 1 ]; then
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
fi
# the name a pane may carry, and the ids a first prompt may name (all reach a shell command string)
NAME_RE='^[a-z0-9][a-z0-9-]{0,31}$'
SID_RE='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
ITEM_RE='^W-[0-9a-f]{8}$'
bad_arg() { echo "agents_up: $1" >&2; exit 2; }
# the first prompt's coordinator and item sentences name ONE builder (W-b9ad80ae PO1, PO2): --pane-cmd's flags, or the
# FABRIK_SPAWN_* variables a caller that cannot pass flags (a cold start through --detach) sets. check_spawn_vars (over
# the resolved set, only the new=1 row FABRIK_SPAWN_NAME names) runs at exactly three places, each where a first prompt
# can be built and before that path's first output line or side effect: the top of the --print block, the new-grid branch
# (before slice_ceiling and the first tmux call) and --pane-cmd (before slice_ceiling). Never on the grid-already-up
# attach path, which builds no pane: a stale malformed variable stops nothing else.
SP_NAME="${FABRIK_SPAWN_NAME:-}"
SP_COORD="${FABRIK_SPAWN_COORDINATOR:-}"
SP_ITEM="${FABRIK_SPAWN_ITEM:-}"
pane_new=0
SP_INTO="" pane_from="" pane_replacing=""
if [ "$panecmd" = 1 ]; then
  [ "$print" = 0 ] && [ "$detach" = 0 ] || bad_arg "--pane-cmd is its own mode: it takes neither --print nor --detach"
  usage="usage: agents_up.sh --pane-cmd <repo> <name> <sid> [--new] [--coordinator <name>] [--item <W-id>]   |   --pane-cmd <repo> <name> <sid> --into <folder> --from <old sid> --replacing <pid>"
  [ $# -ge 3 ] || bad_arg "$usage"
  pane_repo="$1" SP_NAME="$2" pane_sid="$3"
  shift 3
  SP_COORD="" SP_ITEM=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --new) pane_new=1; shift ;;
      --coordinator)
        [ $# -ge 2 ] || bad_arg "$usage"
        [[ "$2" =~ $NAME_RE ]] || bad_arg "the coordinator '$2' is not an agent name ([a-z0-9][a-z0-9-]{0,31})"
        SP_COORD="$2"; shift 2 ;;
      --item)
        [ $# -ge 2 ] || bad_arg "$usage"
        [[ "$2" =~ $ITEM_RE ]] || bad_arg "the item '$2' is not a work item id (W- and 8 lowercase hex)"
        SP_ITEM="$2"; shift 2 ;;
      # W-e38f8ee7 (rotate-session --move): a FRESH session for <name> in another of its worktrees, replacing the pane's
      # claude <pid> that runs <old sid>; the three come together and take none of the spawn flags
      --into)
        [ $# -ge 2 ] || bad_arg "$usage"
        [ -z "$SP_INTO" ] || bad_arg "--into is given once"
        [[ "$2" =~ $NAME_RE ]] || bad_arg "'$2' is not a worktree folder name ([a-z0-9][a-z0-9-]{0,31})"
        SP_INTO="$2"; shift 2 ;;
      --from)
        [ $# -ge 2 ] || bad_arg "$usage"
        [ -z "$pane_from" ] || bad_arg "--from is given once"
        [[ "$2" =~ $SID_RE ]] || bad_arg "--from '$2' is not a session id (a lowercase UUID)"
        pane_from="$2"; shift 2 ;;
      --replacing)
        [ $# -ge 2 ] || bad_arg "$usage"
        [ -z "$pane_replacing" ] || bad_arg "--replacing is given once"
        [[ "$2" =~ ^[1-9][0-9]{0,9}$ ]] || bad_arg "--replacing '$2' is not a process id"
        pane_replacing="$2"; shift 2 ;;
      *) bad_arg "$usage" ;;
    esac
  done
  [[ "$SP_NAME" =~ $NAME_RE ]] || bad_arg "'$SP_NAME' is not an agent name ([a-z0-9][a-z0-9-]{0,31})"
  [[ "$pane_sid" =~ $SID_RE ]] || bad_arg "'$pane_sid' is not a session id (a lowercase UUID)"
  if [ -n "$SP_INTO$pane_from$pane_replacing" ]; then
    [ -n "$SP_INTO" ] && [ -n "$pane_from" ] && [ -n "$pane_replacing" ] || bad_arg "--into, --from and --replacing come together"
    [ "$pane_new" = 0 ] && [ -z "$SP_COORD" ] && [ -z "$SP_ITEM" ] || bad_arg "--into takes none of --new, --coordinator and --item"
  fi
  set -- "$pane_repo"
fi
if [ $# -ne 1 ] || [ -z "$1" ]; then
  echo "usage: agents_up.sh [--print] [--detach] [--tab] <repo>   |   agents_up.sh [--tab] --window <n> <repo>" >&2
  exit 2
fi
if [ ! -d "$1" ]; then
  echo "agents_up: $1 is not a directory" >&2
  exit 2
fi
ROOT="$(cd -- "$1" && pwd -P)" || exit 2
SELF="$(cd -- "$(dirname -- "$0")" && pwd -P)/$(basename -- "$0")"
HUB="$(cd -- "$(dirname -- "$SELF")/../.." && pwd -P)"  # the checkout this launcher runs from: its scripts/ are the panes' tools
REG="$ROOT/.fabrik/session-agents.json"

# The repo's coordinator by its own ledger: exit 0 prints a name, 3 is UNDECLARED; a ledger that is absent declares
# nobody; any other answer refuses, since a coordinator mistaken for a builder would get a pane.
OWNER=""
DECISIONS="$(cd -- "$(dirname -- "$SELF")/.." && pwd -P)/decisions.py"
if [ -f "$ROOT/docs/DECISIONS.md" ]; then
  OWNER="$(python3 "$DECISIONS" --merge-owner "$ROOT" 2>/dev/null)"
  case $? in
    0) ;;
    3) OWNER="" ;;
    *) echo "agents_up: could not read the merge owner of $ROOT ($DECISIONS --merge-owner failed) — not launching" >&2; exit 2 ;;
  esac
fi

# "agent <name> <sid> <folder> <new>" per builder (the worktree its pane starts in; <new> is 1 for a spawner-bound session
# with no transcript anywhere, which launches with --session-id), name-ordered, then "known <sid>" for every session the registry or the store gives
# this repo (the newer-transcript warning skips those); any malformed registry row refuses the launch. The scope query
# runs with git's own location variables unset, so a GIT_DIR inherited from a hook or an IDE cannot redirect it.
SCOPE="$(env -u GIT_DIR -u GIT_COMMON_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || SCOPE=""
STORE="${AGENT_IDENTITY_FILE:-$HOME/.claude/state/agent-identity.jsonl}"
case "$STORE" in /*) ;; *) STORE="$PWD/$STORE" ;; esac
RESOLVED="$(python3 - "$REG" "$SCOPE" "$STORE" "$ROOT" "$CLAUDE_CONFIG_DIR" "$OWNER" <<'PY'
import glob, json, os, re, sys

SID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
WHOAMI_NAME = re.compile(r"[a-z0-9-]{1,32}")  # whoami_agent.py::_NAME_RE — the names its reader honours
reg_path, scope, store, root, config, merge_owner = sys.argv[1:7]

def note(msg):
    print(f"agents_up: {msg}", file=sys.stderr)

def die(msg, code=2):  # exit 3 is "nothing to launch" (an empty repo); every other refusal exits 2
    print(msg, file=sys.stderr)
    sys.exit(code)

def coordinator(name):
    return name == "coordinator" or name.endswith("-coordinator")

def no_repeats(pairs):
    seen = set()
    for key, _ in pairs:
        if key in seen:
            raise ValueError(f"session id {key} appears twice")
        seen.add(key)
    return dict(pairs)

has_reg = os.path.lexists(reg_path)
reg = {}
if has_reg:
    try:
        reg = json.load(open(reg_path, encoding="utf-8"), object_pairs_hook=no_repeats)
    except (OSError, ValueError) as exc:
        sys.exit(f"agents_up: {reg_path} is not a valid registry ({exc})")
    if not isinstance(reg, dict):
        sys.exit(f"agents_up: {reg_path} must be an object of session id -> agent name")
elif not scope:
    die(f"agents_up: {root} has no registry ({reg_path}) and no git scope to read its whoami bindings from — nothing to launch")
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
if has_reg and not ids:
    die(f"agents_up: {reg_path} names no builder (the coordinator gets no pane)", 3)

def at_of(row):  # whoami_agent.py::_at — never raises; an uncoercible time is 0
    try:
        return int(row.get("at") or 0)
    except (TypeError, ValueError, OverflowError):
        return 0

rows = []  # whoami_agent.py::_rows — every parseable row with a session id, file order
if not scope:
    note(f"{root} has no git scope — the identity store is not read; the registry's ids stand")
elif os.path.lexists(store) and not os.path.isfile(store):
    if not has_reg:  # the store is the only source of builders here: reading none would look like an empty repo
        die(f"agents_up: the identity store {store} cannot be read (not a regular file) — refusing rather than reading no builders")
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
        if not has_reg:
            die(f"agents_up: the identity store {store} cannot be read ({exc.strerror or exc}) — refusing rather than reading no builders")
        note(f"the identity store {store} could not be read ({exc.strerror or exc}) — the registry's ids stand")
        rows = []
owner = {}  # session id -> the name on its LAST row anywhere in the store (whoami_agent.py::resolve_agent_name)
for r in rows:
    sid, name = str(r.get("session_id")), str(r.get("name") or "")
    if WHOAMI_NAME.fullmatch(name):
        owner[sid] = name
binding = {}  # builder name -> (sid, at) of the LAST line naming it in this scope whose session it still owns
last_in_scope = {}  # session id -> the LAST row naming it in this scope (it must still name the builder, for <new>)
spawned_in_scope = set()  # (session id, name) of every `spawned: true` row in this scope (T10 F1)
for r in rows:
    sid, name = r.get("session_id"), r.get("name")
    if r.get("toplevel") != scope or not isinstance(sid, str) or not SID.fullmatch(sid):
        continue
    last_in_scope[sid] = r
    if r.get("spawned") is True and isinstance(name, str):  # T10 F18: a non-string name is unhashable — skip it
        spawned_in_scope.add((sid, name))
    if isinstance(name, str) and owner.get(sid) == name:
        binding[name] = (sid, at_of(r))
if not has_reg:  # no registry: the builders are the names bound in this repo's scope
    ids = {n: [] for n in binding if NAME.fullmatch(n) and not coordinator(n)}

owner_name = merge_owner.strip()
if owner_name and not NAME.fullmatch(owner_name):
    note(f"the merge owner {owner_name!r} is not an agent name ([a-z0-9][a-z0-9-]{{0,31}}) — matched lowercased")
owner_name = owner_name.lower()
if owner_name in ids:
    note(f"{owner_name}: the repo's merge owner (its coordinator) — no pane")
    coord_ids.update(ids.pop(owner_name))
    if owner_name in binding:
        coord_ids.add(binding[owner_name][0])

def linked(name):  # a linked git worktree in place: a `.git` FILE, and the physical path is exactly the expected one
    d = os.path.join(root, ".claude", "worktrees", name)
    return os.path.isdir(d) and os.path.isfile(os.path.join(d, ".git")) and os.path.realpath(d) == d

def no_worktree(name):
    why = "" if owner_name else " (no merge owner is declared, so it is taken as the coordinator)"
    note(f"{name}: .claude/worktrees/{name} is not a linked git worktree in place — no pane; it works in the main checkout{why}")

def proj(folder):  # claude files a session under its start folder with every non-alphanumeric character as `-`
    return os.path.join(config, "projects", re.sub(r"[^A-Za-z0-9]", "-", folder))

# W-456aa02a: the worktrees a pane may start in. Claude Code keeps the folder a pane STARTED in as the window's project
# folder (CLAUDE_PROJECT_DIR — its hooks, settings and permissions) after the session moves into another worktree, and
# files the session's transcript under the folder it works in; so the linked worktree whose project folder holds the
# session is the agent's tree. A candidate's folder name must be an agent name: the mangling above is then one-to-one
# over the candidates, and a folder name can never break the shell's `read` of the line printed below. The
# coordinator's trees (a coordinator name, the merge owner) are never a builder's.
wtroot = os.path.join(root, ".claude", "worktrees")
try:
    cands = sorted(
        f for f in os.listdir(wtroot) if NAME.fullmatch(f) and not coordinator(f) and f != owner_name and linked(f)
    )
except OSError:
    cands = []

def holds(folder, sid):
    return os.path.isfile(os.path.join(proj(os.path.join(wtroot, folder)), sid + ".jsonl"))

# A name without its own worktree keeps a pane only in a repo that declares its merge owner (with none it is taken as
# the coordinator) AND only when a candidate holds one of its sessions; any other is dropped here, before its rows
# are read, as before W-456aa02a.
for name in sorted(ids):
    if linked(name):
        continue
    sids = [*ids[name], *([binding[name][0]] if name in binding else [])]
    # the same rule as the folder choice below: another builder's own-named tree is never this name's
    if not owner_name or not any(holds(f, s) for f in cands if f not in ids for s in sids):
        no_worktree(name)
        del ids[name]

def active_at(name, sid):  # the newest mtime of the session's transcript under the folders its pane can start in
    best = None
    for folder in (root, *(os.path.join(wtroot, f) for f in cands)):
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
    if not regs or (new in regs and len(regs) == 1):
        chosen[name] = new
        continue
    if len(regs) == 1 and owner.get(regs[0], name) == name:
        # an undated binding (`at` 0) proves no age: its own transcript's activity is the floor the registry's must pass
        seen_at, floor = active_at(name, regs[0]), max(new_at, active_at(name, new) or 0)
        if seen_at is not None and floor > 0 and seen_at > floor:
            note(f"{name}: the registry's {regs[0]} was active after its binding {new} — resuming {regs[0]}")
            chosen[name] = regs[0]
            continue
    note(f"{name}: resuming {new}, its newest whoami binding, not the registry's {' or '.join(r for r in regs if r != new)}")
    chosen[name] = new
holders = {sid: ["coordinator"] for sid in coord_ids | {s for s, n in owner.items() if coordinator(n)}}
for name, sid in chosen.items():
    holders.setdefault(sid, []).append(name)
for sid, names in sorted(holders.items()):
    if len(names) > 1:
        sys.exit(f"agents_up: session {sid} would serve {' and '.join(sorted(names))} — two processes on one session fuse it; fix the registry or re-bind")
# Each builder's folder: the one candidate holding its session — never another builder's own-named tree — else its
# own-named tree. Two builders found in one folder each keep their own-named tree (two panes in one tree would edit one
# index), and the rest of the grid launches.
folder = {}
for name in sorted(chosen):
    hits = [f for f in cands if (f == name or f not in chosen) and holds(f, chosen[name])]
    if len(hits) == 1:
        folder[name] = hits[0]
    else:
        if len(hits) > 1:
            note(f"{name}: session {chosen[name]} sits in more than one worktree ({', '.join(hits)}) — its pane keeps .claude/worktrees/{name}")
        folder[name] = name
shared = {}
for name in sorted(folder):
    if folder[name] != name:
        shared.setdefault(folder[name], []).append(name)
for f, names in sorted(shared.items()):
    if len(names) > 1:
        note(f"{', '.join(names)}: sessions {', '.join(chosen[n] for n in names)} both sit in .claude/worktrees/{f} — each starts in its own-named tree")
        for n in names:
            folder[n] = n
for name in sorted(folder):
    if not linked(folder[name]):
        no_worktree(name)
        del chosen[name], folder[name]
    elif folder[name] != name:
        flag = " — a Claude Code subagent tree, which Claude Code may remove" if folder[name].startswith("agent-") else ""
        note(f"{name}: starts in .claude/worktrees/{folder[name]}, where its session {chosen[name]} lives{flag}")
if not chosen:
    die(f"agents_up: {root} has no builder with its own worktree — nothing to launch (the coordinator gets no pane)", 3)

def fresh(name, sid):  # 1: a spawner-bound session that no project folder has a transcript of
    # spawner-bound: ANY row here binds it to the name `spawned: true` AND its LAST row here still names the builder —
    # never the last row's flag alone, since whoami's refresh() appends an unflagged row at every SessionStart (T10 F1)
    r = last_in_scope.get(sid)
    if not r or r.get("name") != name or (sid, name) not in spawned_in_scope:
        return 0
    # ANY project folder, wider than active_at's walk: a session that moved anywhere is never given --session-id on a used id
    return 0 if glob.glob(os.path.join(glob.escape(config), "projects", "*", sid + ".jsonl")) else 1

for name in sorted(chosen):
    print("agent", name, chosen[name], folder[name], fresh(name, chosen[name]))
for sid in sorted(set(reg) | {str(r.get("session_id")) for r in rows}):
    if SID.fullmatch(sid):  # a newline in a store row's id would forge an `agent` line below
        print("known", sid)
PY
)"
# 3 = nothing to launch (a registry naming no builder, bindings with no worktree); every other refusal is 2
case $? in 0) ;; 3) exit 3 ;; *) exit 2 ;; esac
AGENTS="$(printf '%s\n' "$RESOLVED" | sed -n 's/^agent //p')"
# each agent line reaches a shell command string: re-check its shape here, whatever the resolver printed
AGENT_RE="^[a-z0-9][a-z0-9-]{0,31} [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12} [a-z0-9][a-z0-9-]{0,31} [01]$"
while IFS= read -r line; do
  [[ "$line" =~ $AGENT_RE ]] || { echo "agents_up: the resolver printed a malformed builder line — not launching" >&2; exit 2; }
done <<< "$AGENTS"
KNOWN="$(printf '%s\n' "$RESOLVED" | sed -n 's/^known //p')"

# tmux reads `.`, `:` and glob characters in a target, so the session name keeps [A-Za-z0-9_-] only
base="$(basename "$ROOT")"
S="${base//[^A-Za-z0-9_-]/-}"
W=agents
# -ww: never cut at the terminal width — a VS Code process line runs to ~420 characters and `--resume=` sits past 280
# pid= leads each line: a pane started by name carries no --resume, so the process is matched by its -n <name> AND its cwd
RUNNING="$(ps -ww -C claude -o pid=,args= 2>/dev/null)"

# The builder's worktree, a linked git worktree in place: a `.git` FILE inside (the shape `git worktree add` makes, so
# neither a folder left behind by `git worktree remove` nor a nested clone) and a physical path exactly
# <root>/.claude/worktrees/<name>, so a symlink anywhere on it can neither take the pane out of the repo nor name a
# project folder claude never writes to. The resolver already dropped every name without one; a worktree removed
# since prints nothing here and that pane is skipped — never started at the root, the coordinator's checkout.
dir_of() {  # $1 = the builder's folder: an agent name the resolver printed (no `/` or `.`, so directly under worktrees/)
  local d="$ROOT/.claude/worktrees/$1"
  if [ -d "$d" ] && [ -f "$d/.git" ] && [ "$(cd -- "$d" && pwd -P)" = "$d" ]; then
    echo "$d"
  else
    echo "agents_up: $1: .claude/worktrees/$1 is no longer a linked git worktree in place — no pane" >&2
  fi
}

# The caps (W-56b3f90d). A size is <digits><K|M|G>, 1M to 999999999G, and a task count 1 to 999999 — capped_run.sh's
# grammar: 0 would be a ceiling that kills everything, and a longer number overflows systemd's parser.
size_ok() {
  case "$1" in *[!0-9KMG]* | "") return 1 ;; esac
  local n=${1%[KMG]} unit=${1##*[0-9]}
  [ -n "$unit" ] && [ "$n" = "${1%?}" ] || return 1
  case "$n" in "" | 0* | *[!0-9]* | ??????????*) return 1 ;; esac
  case "$unit" in K) [ "$n" -ge 1024 ] ;; M | G) [ "$n" -ge 1 ] ;; *) return 1 ;; esac
}
TASKS_MAX=${FABRIK_AGENT_TASKS_MAX:-1024}
SLICE=fabrik-agents.slice
case "$TASKS_MAX" in "" | 0* | *[!0-9]* | ???????*) echo "agents_up: bad FABRIK_AGENT_TASKS_MAX '$TASKS_MAX' (1 to 999999)" >&2; exit 2 ;; esac
if [ -n "${FABRIK_AGENT_MEM_MAX:-}" ]; then
  echo "agents_up: FABRIK_AGENT_MEM_MAX is retired (no pane gets a MemoryMax of its own; the $SLICE ceiling bounds them all) — ignored" >&2
fi
# The slice ceiling (W-6e656dac L5, refined by W-0b8a0fba): MemoryHigh = MemTotal - max(4G, floor) and MemoryMax =
# MemTotal - max(2G, floor - 2G), in whole G, where floor ($FABRIK_AGENT_NONAGENT_FLOOR, 12G) is what the box's
# non-agent processes (Windows, VS Code, the system) keep. MemTotal is read through the FABRIK_PROC_ROOT seam; under 8G,
# unreadable keeps D-1075's 16G MemoryMax (and says so); a floor that leaves nothing uses the minimum margins. FABRIK_AGENT_SLICE_MAX still
# overrides the derived MemoryMax; whichever way, MemoryHigh is re-asserted so no stale runtime value outlives it.
PROC_ROOT=${FABRIK_PROC_ROOT:-/proc}
FLOOR_RAW=${FABRIK_AGENT_NONAGENT_FLOOR:-12G}
FLOOR_G=${FLOOR_RAW%G}
case "$FLOOR_G" in "" | *[!0-9]* | ????*) echo "agents_up: bad FABRIK_AGENT_NONAGENT_FLOOR '$FLOOR_RAW' (whole G, 0 to 999: e.g. 12G)" >&2; exit 2 ;; esac
FLOOR_G=$((10#$FLOOR_G))
SLICE_HIGH=infinity
SLICE_MAX=16G
CEILING_NOTE=""
MARGIN_NOTE=""
MEMTOTAL_KB="$(awk '/^MemTotal:/ { print $2; exit }' "$PROC_ROOT/meminfo" 2>/dev/null)"
case "$MEMTOTAL_KB" in
  "" | *[!0-9]*) CEILING_NOTE="MemTotal is unreadable ($PROC_ROOT/meminfo)" ;;
  *)
    TOTAL_G=$((MEMTOTAL_KB / 1048576))
    if [ "$TOTAL_G" -lt 8 ]; then
      CEILING_NOTE="MemTotal is ${TOTAL_G}G, under 8G"
    else
      HIGH_G=$((TOTAL_G - (FLOOR_G > 4 ? FLOOR_G : 4)))
      MAXG=$((TOTAL_G - (FLOOR_G - 2 > 2 ? FLOOR_G - 2 : 2)))
      if [ "$HIGH_G" -lt 1 ]; then
        # a floor that leaves nothing must never LOOSEN the cap (16G would exceed an 8-16G box): fall to the minimum margins
        MARGIN_NOTE="a non-agent floor of ${FLOOR_G}G leaves nothing of MemTotal ${TOTAL_G}G — using the minimum margins (MemoryHigh=MemTotal-4G, MemoryMax=MemTotal-2G)"
        SLICE_HIGH="$((TOTAL_G - 4))G"
        SLICE_MAX="$((TOTAL_G - 2))G"
      else
        SLICE_HIGH="${HIGH_G}G"
        SLICE_MAX="${MAXG}G"
      fi
    fi
    ;;
esac
if [ -n "${FABRIK_AGENT_SLICE_MAX:-}" ]; then
  size_ok "$FABRIK_AGENT_SLICE_MAX" || { echo "agents_up: bad FABRIK_AGENT_SLICE_MAX '$FABRIK_AGENT_SLICE_MAX' (e.g. 16G; 1M to 999999999G)" >&2; exit 2; }
  SLICE_MAX="$FABRIK_AGENT_SLICE_MAX"
  SLICE_HIGH=infinity
elif [ -n "$CEILING_NOTE" ]; then
  echo "agents_up: $CEILING_NOTE — keeping D-1075's 16G ceiling" >&2
elif [ -n "$MARGIN_NOTE" ]; then
  echo "agents_up: $MARGIN_NOTE" >&2
fi
# A launch from a .bat (`wsl.exe --exec bash -l`) carries no XDG_RUNTIME_DIR, and without it every systemctl/systemd-run
# answers "Failed to connect to bus" — so set it when the user bus is there, as capped_run.sh does.
if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -S "/run/user/$(id -u)/bus" ]; then
  export XDG_RUNTIME_DIR="/run/user/$(id -u)"
fi
CAPPED=0
if command -v systemd-run >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
  CAPPED=1
else
  echo "agents_up: WARNING — no systemd-run on PATH, or no systemd user manager answers (XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-unset}); the panes run UNCAPPED, with no memory or task bound" >&2
fi

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
  echo "agents_up: $1: a newer session $base is in $proj — if it is $1's, run there: python3 \"$HUB/scripts/whoami_agent.py\" --as $1 --force" >&2
}

# a claude process started by NAME (`-n <name>`, no --resume: a spawned pane's --session-id launch) in the pane's folder
# or below it is the same builder running; `-n infra` never matches `-n infra-2`, which grep -w would (`-` is a boundary).
# The pid it found is printed; $3, when given, is a pid never counted (the claude a --move replaces, W-e38f8ee7).
named_running() {  # $1 = name, $2 = the folder its pane starts in, $3 = a pid to skip
  local pid args cwd
  while read -r pid args; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    [ "$pid" = "${3:-}" ] && continue
    [[ " $args " == *" -n $1 "* || " $args " == *" --name $1 "* || " $args " == *" --name=$1 "* ]] || continue
    cwd="$(readlink "$PROC_ROOT/$pid/cwd" 2>/dev/null)"
    case "$cwd" in "$2" | "$2"/*) echo "$pid"; return 0 ;; esac
  done <<< "$RUNNING"
  return 1
}

status_of() {  # $1 = session id, $2 = the folder its pane starts in, $3 = the builder's name
  if printf '%s\n' "$RUNNING" | /usr/bin/grep -qE -- "(^| )(--resume[= ]|-r |--session-id[= ])$1( |\$)" || named_running "$3" "$2" >/dev/null; then
    echo running
  elif [ ! -f "$(proj_of "$2")/$1.jsonl" ]; then
    echo no-transcript
  else
    echo ok
  fi
}

squote() {  # $1 as ONE POSIX single-quoted word, read alike by every pane shell and locale
  printf "'%s'" "${1//\'/\'\\\'\'}"
}

# The suppression (spec D3, probed live 2026-10-28 on claude 2.1.312: no "Teach auto mode" dialog, spinner tips off):
# one constant, on EVERY claude call this script builds, beside CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1 in every pane's env
SETTINGS_JSON='{"skillOverrides":{"auto-mode-setup":"off"},"spinnerTipsEnabled":false}'

spawn_vars_ok() {  # $1 = name, $2 = new: the FABRIK_SPAWN_* values matter only to the new builder they name
  [ "$2" = 1 ] && [ "$1" = "$SP_NAME" ] || return 0
  [ -z "$SP_COORD" ] || [[ "$SP_COORD" =~ $NAME_RE ]] || bad_arg "FABRIK_SPAWN_COORDINATOR '$SP_COORD' is not an agent name ([a-z0-9][a-z0-9-]{0,31})"
  [ -z "$SP_ITEM" ] || [[ "$SP_ITEM" =~ $ITEM_RE ]] || bad_arg "FABRIK_SPAWN_ITEM '$SP_ITEM' is not a work item id (W- and 8 lowercase hex)"
}

check_spawn_vars() {  # the whole resolved set; see the call sites in the header comment
  local name sid folder new
  while read -r name sid folder new; do spawn_vars_ok "$name" "$new"; done <<< "$AGENTS"
}

first_prompt() {  # $1 = name, $2 = session id: a spawned builder's first turn, ONE line, nothing in it for a shell to read
  local coord item
  coord="the repo's merge owner (\`decisions.py --merge-owner\`)"
  [ "$1" = "$SP_NAME" ] && [ -n "$SP_COORD" ] && coord="$SP_COORD"
  item=""
  [ "$1" = "$SP_NAME" ] && [ -n "$SP_ITEM" ] && item=" Your item is $SP_ITEM."
  printf '%s' "You were started by agents_up as $1 (\$CLAUDE_AGENT), session $2, in your own worktree. First arm your self-watch: run bash \"$HUB/scripts/sysadmin/selfwatch_arm.sh\" $2 in the background. Then re-bind: run python3 \"$HUB/scripts/whoami_agent.py\" --as $1 --force. Then read your charter (the SessionStart hook printed it; else docs/reference/agents/builder.md). Your coordinator is $coord.$item Run python3 scripts/work.py next and claim your item; when next shows nothing, message your coordinator and wait. Merge the repo's base branch only when the store or your coordinator says your item is committed there, then claim it. \"Every question goes to your coordinator by SendMessage - never to the operator.\""
}

# W-e38f8ee7: a moved builder's first turn — where it now starts, then rotate_session.resume_prompt's text with the id
# filled in and this checkout's paths (tests/test_agents_up.py pins the two equal); ONE line, nothing for a shell to read
move_prompt() {  # $1 = name, $2 = session id; the folder is SP_INTO
  printf '%s' "You were moved by agents_up into .claude/worktrees/$SP_INTO as a fresh session $2, so your hooks load from the tree you work in. You were rotated at an item boundary (D-1119). First re-arm your self-watch: run bash \"$HUB/scripts/sysadmin/selfwatch_arm.sh\" $2 in the background. Then run python3 \"$HUB/scripts/whoami_agent.py\" --as $1 --force. Then read only your memory notes, python3 scripts/work.py next and your run's seed if one is named there — never the previous transcript — and carry on. Read your memory notes and seed with the Read tool, not cat; run each command, git included, as a separate Bash call (the self-watch arm stays in the background); open any output the harness saved to a file with the Read tool (offset and limit) — never give sed, awk or head a shell variable or \$( ), in the file name or the expression."
}

cmd_of() {  # $1 = name, $2 = session id, $3 = status, $4 = new (1: spawned, 2: moved — both --session-id launches); name and id are validated above
  # HOME..LANG are read by the pane's own shell at run time (single-quoted here); the rest are fixed now. PATH is
  # fixed ONCE: a capped pane's outer `env -i` sets it, and the commands inside the scope read it back at run time
  # (`PATH="$PATH"`) — three fixed copies of a WSL PATH (4 KB here) brought a pane command to ~14 KB, near the size
  # tmux takes in one message (review round 1).
  local env base inner path_now
  base='env -i HOME="$HOME" USER="$USER" LOGNAME="$LOGNAME" SHELL="$SHELL" TERM="$TERM" LANG="${LANG:-C.UTF-8}" CLAUDE_CODE_RETRY_WATCHDOG=1 CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY=1'
  path_now="$(printf 'PATH=%q' "$PATH")"
  env="$base $(printf 'CLAUDE_CONFIG_DIR=%q CLAUDE_QUOTA_HOME=%q' "$CLAUDE_CONFIG_DIR" "$CLAUDE_QUOTA_HOME") CLAUDE_AGENT=$1"
  # the store the launcher read: the panes' whoami must write the same one, or the next launch never sees the re-bind
  [ -n "${AGENT_IDENTITY_FILE:-}" ] && env="$env $(printf 'AGENT_IDENTITY_FILE=%q' "$STORE")"
  # the user bus, so a capped_run.sh or systemctl call from the agent finds its manager
  [ -n "${XDG_RUNTIME_DIR:-}" ] && env="$env $(printf 'XDG_RUNTIME_DIR=%q' "$XDG_RUNTIME_DIR")"
  local penv killed
  if [ "$CAPPED" = 1 ]; then
    penv="$env PATH=\"\$PATH\""  # inside the scope: the PATH the outer env -i set
    killed="[$1 was killed (exit 137, SIGKILL) — in this capped pane most likely at the $SLICE memory ceiling (MemoryMax=$SLICE_MAX)]"
  else
    penv="$env $path_now"
    killed="[$1 was killed (exit 137, SIGKILL)]"
  fi
  # the pane keeps a CLEAN shell after claude exits (or instead of it), so a crash never closes the pane and the
  # resume hint it prints runs with the pane's own environment, never the server's
  # a session with no transcript cannot be resumed: its hint and message name --session-id. For a spawned pane (new=1)
  # the flag is picked when the text is PRINTED (T10 F14): `--resume` once any project folder holds the session's
  # transcript (fresh()'s glob), else `--session-id` — a launch-time flag goes stale the moment claude writes one
  # every launch and every printed relaunch line carries the permission mode (operator ruling 2026-10-30, W-b9b6472e):
  # a `--resume` keeps the session's SAVED mode and ignores settings' permissions.defaultMode, so a relaunch without
  # the flag came back in auto
  local perm="--permission-mode bypassPermissions"
  local flag=--resume
  [ "${4:-0}" != 0 ] && flag="\$(for t in $(squote "$CLAUDE_CONFIG_DIR")/projects/*/$2.jsonl; do [ -e \"\$t\" ] && { echo --resume; exit; }; done; echo --session-id)"
  if [ "$3" = running ]; then
    inner="echo \"[$1 is already running elsewhere (session $2) — close it there, then run: claude -n $1 $perm $flag $2]\"; exec $penv bash -l"
  else
    # the paths are %q-escaped so the printed command pastes back safely, and the whole hint is single-quoted (POSIX,
    # read alike by every pane shell and locale) for the pane's printf, so a `$(...)`, a backtick or a `$NAME` in a
    # folder name is printed, never run or expanded
    # (a spawned pane's flag is the one unquoted `"$(…)"` between two quoted halves, run when the hint prints)
    local hint
    hint="$(squote "[$1 exited — run: claude -n $1 $perm ")\"$flag\"$(squote " $2 (after a /clear: whoami_agent.py --as $1 --force, then $(printf %q "$SELF") $(printf %q "$ROOT"))]")"
    # the relaunch's first turn (L4): re-arm the self-watch (background tasks are not restored), then `woke`, resuming
    # only on exit 0 — so a daily relaunch outside any pause just carries on. The permission mode is passed ($perm,
    # above): a resumed session would otherwise keep its saved mode. oom_score_adj 200 (raising needs no privilege) ranks a builder pane
    # above the coordinators in the kernel's OOM order.
    local wake claude
    if [ "${4:-0}" = 1 ]; then
      # a spawner-bound session with no transcript yet: --resume of it would drop to the kept shell
      wake="$(first_prompt "$1" "$2")"
      claude="claude -n $1 $perm --session-id $2"
    elif [ "${4:-0}" = 2 ]; then
      # W-e38f8ee7: a FRESH session the rotation started in the worktree the builder works in
      wake="$(move_prompt "$1" "$2")"
      claude="claude -n $1 $perm --session-id $2"
    else
      wake="You were relaunched by agents_up. First re-arm your self-watch: run bash \"$HUB/scripts/sysadmin/selfwatch_arm.sh\" $2 in the background. Then run python3 \"$HUB/scripts/sysadmin/hibernate.py\" woke --self $2 and, only if it exits 0, resume your item from the seed it prints; on exit 1 carry on as usual; on exit 2 stay paused and tell your coordinator."
      claude="claude -n $1 $perm --resume $2"
    fi
    inner="echo 200 > /proc/self/oom_score_adj 2>/dev/null; $penv $claude --settings $(squote "$SETTINGS_JSON") $(squote "$wake"); rc=\$?; echo; [ \"\$rc\" = 137 ] && printf '%s\\n' $(squote "$killed"); printf '%s\\n' $hint; exec $penv bash -l"
  fi
  if [ "$CAPPED" = 1 ]; then
    # the WHOLE pane in one scope, so the shell it keeps — and whatever is re-run there — stays inside the cap; a
    # scope that cannot be made leaves a pane that says so, never one that closes without a word. It opens NO shell:
    # the same branch runs when the kept shell itself exits non-zero, and a shell here would be outside the cap
    # (review round 2), so it only waits for Enter
    echo "$env $path_now systemd-run --user --scope --quiet --slice=$SLICE -p MemorySwapMax=0 -p TasksMax=$TASKS_MAX -- bash -c $(squote "$inner") || { echo \"[$1: the capped scope ended with exit \$? — if nothing ran above, systemd-run could not start it; press Enter to close this pane]\"; read -r _; }"
  else
    echo "echo '[UNCAPPED: no systemd user manager answered at launch — this pane has no memory or task bound]'; $inner"
  fi
}

cap_of() {  # $1 = name
  if [ "$CAPPED" = 1 ]; then echo "cap $1 $TASKS_MAX"; else echo "cap $1 uncapped"; fi
}

if [ "$print" = 1 ]; then
  check_spawn_vars
  echo "session $S"
  [ "$CAPPED" = 1 ] && echo "slice $SLICE MemoryHigh=$SLICE_HIGH MemoryMax=$SLICE_MAX"
  while read -r name sid folder new; do
    dir="$(dir_of "$folder")"
    [ -n "$dir" ] || continue
    st="$(status_of "$sid" "$dir" "$name")"
    newer_unbound "$name" "$sid" "$dir"
    echo "pane $name $sid $dir $st"
    cap_of "$name"
    echo "run $name $(cmd_of "$name" "$sid" "$st" "$new")"
  done <<< "$AGENTS"
  exit 0
fi

# The slice's own ceiling, re-asserted before every NEW grid and RUNTIME-only (it lives in /run and goes with the
# manager); reattaching to a running grid starts nothing, so it never needs it. A manager that answers but refuses it
# is an error, never a silent fall-through to an unbounded total.
slice_ceiling() {
  if [ "$CAPPED" != 1 ]; then
    # the .bat path never starts a pane with no bound unless the operator said so; the boot path (--detach) always
    # comes back, with the warning already printed above (D-1075)
    if [ "$detach" = 1 ] || [ "${FABRIK_AGENTS_UNCAPPED:-}" = 1 ]; then return 0; fi
    echo "agents_up: no systemd user manager answers, so the panes would have no memory or task bound — not launching; start the user manager, or set FABRIK_AGENTS_UNCAPPED=1 to launch uncapped anyway" >&2
    exit 2
  fi
  systemctl --user set-property --runtime "$SLICE" "MemoryHigh=$SLICE_HIGH" "MemoryMax=$SLICE_MAX" MemorySwapMax=infinity >/dev/null 2>&1 && return 0
  echo "agents_up: the user manager refused the $SLICE ceiling (MemoryHigh=$SLICE_HIGH MemoryMax=$SLICE_MAX) — not launching" >&2
  exit 2
}

# --pane-cmd: the one command the grid would run for ONE builder, through the same resolver and cmd_of, so a pane the
# spawner launches differs from a relaunched one only in its session flag and prompt. --new asserts the resolver's own
# <new> (a spawner-bound session with no transcript anywhere); nothing prints on a refusal.
# --pane-cmd --into (W-e38f8ee7, rotate-session --move): the command that starts <name> as a FRESH session <sid> in
# .claude/worktrees/<folder>, the tree it works in. The resolver must still give <name> the session the pane runs
# (<old sid>); <sid> is no id this repo knows and has no transcript; <folder> is a linked worktree in place that is
# neither a coordinator's tree nor another builder's (own-named or resolved); and no OTHER claude by that name runs
# there — the pane's own claude (<pid>) is the one respawn-pane replaces, so it is skipped and the status is `ok`.
if [ "$panecmd" = 1 ] && [ -n "$SP_INTO" ]; then
  chosen_sid=""
  while read -r name sid folder new; do
    [ "$name" = "$SP_NAME" ] && chosen_sid="$sid"
  done <<< "$AGENTS"
  [ -n "$chosen_sid" ] || bad_arg "$SP_NAME is not a builder the resolver gives $ROOT"
  [ "$chosen_sid" = "$pane_from" ] || bad_arg "$SP_NAME's session is $chosen_sid, not $pane_from — the pane changed since the request"
  printf '%s\n' "$KNOWN" | /usr/bin/grep -qxF -- "$pane_sid" && bad_arg "$pane_sid is a session this repo already knows — not a fresh session"
  if compgen -G "$CLAUDE_CONFIG_DIR/projects/*/$pane_sid.jsonl" >/dev/null; then
    bad_arg "$pane_sid has a transcript — not a fresh session"
  fi
  case "$SP_INTO" in coordinator | *-coordinator) bad_arg "$SP_INTO is the coordinator's tree" ;; esac
  [ -n "$OWNER" ] && [ "$SP_INTO" = "$(printf '%s' "$OWNER" | tr '[:upper:]' '[:lower:]')" ] && bad_arg "$SP_INTO is the coordinator's tree (the merge owner)"
  while read -r name sid folder new; do
    [ "$name" = "$SP_NAME" ] && continue
    [ "$SP_INTO" = "$name" ] || [ "$SP_INTO" = "$folder" ] && bad_arg "$SP_INTO is $name's tree"
  done <<< "$AGENTS"
  dir="$(dir_of "$SP_INTO")"
  [ -n "$dir" ] || exit 2
  if other="$(named_running "$SP_NAME" "$dir" "$pane_replacing")"; then
    bad_arg "another claude -n $SP_NAME (pid $other) already runs in .claude/worktrees/$SP_INTO — not starting a second"
  fi
  # the pid skipped above must BE this builder's claude (started `-n <name>`, as every grid pane is), or a wrong pid
  # would disarm that refusal (review pass 1, B4); a pane launched without a name is refused, never guessed at
  rep_args="$(printf '%s\n' "$RUNNING" | /usr/bin/awk -v p="$pane_replacing" '$1 == p { $1 = ""; print; exit }')"
  [[ " $rep_args " == *" -n $SP_NAME "* || " $rep_args " == *" --name $SP_NAME "* || " $rep_args " == *" --name=$SP_NAME "* ]] \
    || bad_arg "--replacing $pane_replacing is not a running claude -n $SP_NAME"
  pane_line="$(cmd_of "$SP_NAME" "$pane_sid" ok 2)"
  slice_ceiling
  printf '%s\n' "$pane_line"
  exit 0
fi

if [ "$panecmd" = 1 ]; then
  found=0
  pane_line=""
  while read -r name sid folder new; do
    [ "$name" = "$SP_NAME" ] && [ "$sid" = "$pane_sid" ] || continue
    found=1
    if [ "$pane_new" = 1 ] && [ "$new" != 1 ]; then
      if compgen -G "$CLAUDE_CONFIG_DIR/projects/*/$sid.jsonl" >/dev/null; then
        bad_arg "$sid has a transcript — not a new session"
      fi
      bad_arg "$sid is not a spawner-bound session"
    fi
    dir="$(dir_of "$folder")"
    [ -n "$dir" ] || exit 2
    st="$(status_of "$sid" "$dir" "$name")"
    pane_line="$(cmd_of "$name" "$sid" "$st" "$new")"
  done <<< "$AGENTS"
  [ "$found" = 1 ] || bad_arg "$SP_NAME with session $pane_sid is not a builder the resolver gives $ROOT"
  # the same cap rules as the grid, last: a refused request never writes the slice property
  check_spawn_vars
  slice_ceiling
  printf '%s\n' "$pane_line"
  exit 0
fi

# tmux 3.4 answers `no such session: =<name>` to an OPTION command (show-options / set-option) given the bare exact
# target `=<name>` while has-session, list-panes and attach accept it (measured on a scratch `tmux -L` server, W-1961cc42);
# the trailing colon (`=<name>:`) names the same session and every command accepts it, so options use it.
# A session is named after the folder only, so a grid already up under this name is attached unless it records a
# DIFFERENT root (D-1108); one recording no root is adopted or attached with a warning. The root is
# recorded just after the session is created, so an empty owner may be a launch still building it: re-read once.
owned_here() {
  local owner
  owner="$(tmux show-options -t "=$S:" -v @agents_up_root 2>/dev/null)"
  if [ -z "$owner" ]; then
    sleep 1
    owner="$(tmux show-options -t "=$S:" -v @agents_up_root 2>/dev/null)"
  fi
  [ "$owner" = "$ROOT" ] && return 0
  # only a DEFINITE other owner (a non-empty root that is not ours) refuses; a grid that is up is attached whatever
  # the read returned (W-e841ac37), so an empty owner below attaches with a warning
  if [ -n "$owner" ]; then
    echo "agents_up: tmux session $S belongs to $owner — not attaching; kill or rename it first" >&2
    return 1
  fi
  # a grid a hand-built launcher made (fabrik-lib's ~/bin/fabrik-lib-up) records no root but tags each pane with its
  # agent: adopt it when every pane is one of THIS repo's builders, so moving to the generated launcher never shows an
  # error pane; any other unrecorded session is attached with a warning (W-e841ac37)
  if adoptable; then
    tmux set-option -t "=$S:" @agents_up_root "$ROOT" >/dev/null
    echo "agents_up: adopted the $S grid a hand-built launcher made — every pane is one of this repo's builders" >&2
    # its panes were started without this script's env allow-list, so they may carry the VS Code session's variables
    echo "agents_up: those panes keep the environment they started with; for clean panes: tmux kill-session -t =$S, then launch again" >&2
    return 0
  fi
  echo "agents_up: could not confirm that tmux session $S is this repo's (it records no root and not every pane is one of this repo's builders) — attaching to it anyway" >&2
  return 0
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


# --- windows of four and the grouped overflow sessions (W-b9ad80ae D4, D5) ---------------------------------------------
# A grid holds four panes per window: `agents`, then `agents-2`, `agents-3`, ... Every window this script creates is
# captured by its id (`-P -F '#{window_id}'`), never found again by name: tmux resolves a window NAME target loosely, so
# with only `agents-2` present both `-t =s:agents` and `-t =s:=agents` select `agents-2`. An existing window is found by
# an EXACT name match over list-windows. The overflow window `agents-<k>` is shown in its own session `<S>+<k>`, grouped
# with `<S>` (`new-session -t`), so each Windows Terminal tab attaches its own session. `+` is outside the base-name
# alphabet [A-Za-z0-9_-], so `<S>+<k>` is this repo's by construction and can never be another repo's base session.
PER_WINDOW=4
tmux_group() {  # $1 = session name: its group, empty when it has none (a session is grouped once a member joins it)
  tmux display-message -p -t "=$1:" '#{session_group}' 2>/dev/null
}
find_window() {  # $1 = exact window name: its id, or nothing
  # the id never holds a space, so the WHOLE rest of the line is the name: a window renamed `agents-2 old` is not `agents-2`
  # (tmux prints a tab in a format as `\011`, so a tab cannot be the separator)
  tmux list-windows -t "=$S" -F '#{window_id} #{window_name}' 2>/dev/null |
    awk -v n="$1" '{ i = index($0, " "); if (substr($0, i + 1) == n) { print substr($0, 1, i - 1); exit } }'
}
proc_start() {  # $1 = pid: field 22 of /proc/<pid>/stat (the process's start time), empty when it is not there
  local s
  s="$(cat "/proc/$1/stat" 2>/dev/null)" || return 0
  s="${s##*) }"  # the comm field may hold spaces and parentheses: fields resume after its LAST `) `
  # shellcheck disable=SC2086
  set -- $s
  printf '%s' "${20:-}"
}
# `@agents_up_building` holds `<pid>:<start time>` of the builder. It counts only while that PID is alive AND its start
# time is still the stored one: a builder SIGKILLed mid-build never runs its EXIT trap, and a later process that takes the
# PID must not read as a builder. Anything malformed (empty, `0`, `0123`, a bare PID) reads "not building".
building_live() {  # $1 = the option's value
  local pid st
  [[ "$1" =~ ^([1-9][0-9]*):([0-9]+)$ ]] || return 1
  pid="${BASH_REMATCH[1]}" st="${BASH_REMATCH[2]}"
  kill -0 "$pid" 2>/dev/null || return 1
  [ "$(proc_start "$pid")" = "$st" ]
}
# A stale member of an old group keeps old windows and claude processes alive (a member survives the killing of its base)
# and, grouped under the name <S>, would be JOINED by the first `new-session -t =<S>` — dragging <S> into the old group,
# where the next change on the stale side replaces the grid's windows. stale_group_members is READ-ONLY: every session other
# than <S> and than a `<S>+<digits>` whose group is <S>. Such a session is NOT ours to kill (it may be another repo's or the
# operator's). The split is on the LAST `|~|`: a session name may hold one, <S> cannot.
stale_group_members() {
  local n g line
  # only while <S> itself is ungrouped (a new base beside an old group): once <S> is in its group, that group is its own and
  # a viewer or hand-made member of it is live, not stale
  [ -z "$(tmux_group "$S")" ] || return 0
  while IFS= read -r line; do
    n="${line%|~|*}" g="${line##*|~|}"
    [ "$n" != "$S" ] || continue
    [[ "$n" == "$S+"* && "${n#"$S+"}" =~ ^[0-9]+$ ]] && continue
    [ "$g" = "$S" ] && printf '%s\n' "$n"
  done < <(tmux list-sessions -F '#{session_name}|~|#{session_group}' 2>/dev/null)
  return 0
}
# After THIS launch's own new-session (so a launch that lost the race kills nothing): a leftover `<S>+<digits>` is killed;
# any stale member (above) is said, naming the kill that frees the group, and no overflow session is made.
clear_stale_group() {
  local n
  while IFS= read -r n; do tmux kill-session -t "=$n" >/dev/null 2>&1; done < <(overflow_sessions)
  stale_members="$(stale_group_members)"
  while IFS= read -r n; do
    [ -n "$n" ] || continue
    echo "agents_up: the tmux session $n is still grouped under the name $S (left by an older grid) — not creating overflow sessions; free the group with: tmux kill-session -t =$n" >&2
    grouped_stale=1
  done <<< "$stale_members"
}
overflow_sessions() {  # every session named <S>+<digits>
  local n
  while IFS= read -r n; do
    [[ "$n" == "$S+"* && "${n#"$S+"}" =~ ^[0-9]+$ ]] && printf '%s\n' "$n"
  done < <(tmux list-sessions -F '#{session_name}' 2>/dev/null)
  return 0
}
ensure_overflow() {  # $1 = k, $2 = the id of window agents-<k>: <S>+<k> in <S>'s group, its current window agents-<k>
  local name="$S+$1" base og m created=0
  if tmux has-session -t "=$name" 2>/dev/null; then
    og="$(tmux_group "$name")"
    base="$(tmux_group "$S")"  # read AFTER og: a concurrent run that groups <S> in between must not get its session killed
    if [ -z "$og" ] || [ "$og" != "$base" ]; then tmux kill-session -t "=$name" >/dev/null 2>&1; fi
  fi
  if ! tmux has-session -t "=$name" 2>/dev/null; then
    # never `new-session -t =<S>` while a stale session holds the group name <S>: it would join that group
    while IFS= read -r m; do
      [ -n "$m" ] || continue
      echo "agents_up: the tmux session $m is still grouped under the name $S (left by an older grid) — not creating $name; free the group with: tmux kill-session -t =$m" >&2
      created=-1
    done < <(stale_group_members)
    [ "$created" = -1 ] && return 1
    if tmux new-session -d -t "=$S" -s "$name"; then
      created=1
    else
      # a second --window run created it first: use it when it is grouped with <S>
      base="$(tmux_group "$S")"
      og="$(tmux_group "$name")"
      if [ -z "$og" ] || [ "$og" != "$base" ]; then
        echo "agents_up: could not create the tmux session $name for window agents-$1" >&2
        return 1
      fi
    fi
  fi
  # the session must really show window $2
  if ! tmux list-windows -t "=$name" -F '#{window_id}' 2>/dev/null | /usr/bin/grep -qxF -- "$2" ||
    ! tmux select-window -t "=$name:$2" >/dev/null 2>&1; then
    echo "agents_up: the tmux session $name shows other windows than window agents-$1 ($2) — not using it" >&2
    [ "$created" = 1 ] && tmux kill-session -t "=$name" >/dev/null 2>&1
    return 1
  fi
}
kill_hint() {  # the relaunch hint: the base session and every overflow session
  local h="tmux kill-session -t =$S" n
  while IFS= read -r n; do [ -n "$n" ] && h="$h; tmux kill-session -t =$n"; done < <(overflow_sessions)
  printf '%s' "$h"
}

# D-1376 (W-8209a305): a grid this launch built brings windows "All Agents (tabbed).bat" must list, so the launch
# refreshes it through agents_bat.py --tabbed (the remembered desktop) — detached, because one run probes every repo
# (~2.6 s for 13) and the launch attaches at once, and COALESCED, because a boot sweep or a cold .bat click builds a
# dozen grids at once: the child holds agents-bat-refresh.pending while it waits on agents-bat-refresh.run, so one
# refresh runs, one waits (it starts after every grid that queued it, so it reads the newest windows) and the rest
# exit. Each appends one header and its outcome to agents-bat-refresh.log. The remembered file is read as
# agents_bat.py::_remembered reads it (whole, stripped, a folder); with none the generator would probe every repo only
# to print, so nothing starts. Every skip and failed start is SAID, never the launch's failure (fail-open: a stale
# .bat is the lesser error). Cobra (D-253): the cheapest pass is a refresh started where the tests look and nowhere
# else — the boot sweep and an `add` cold start reach start_grid through --detach, so the call sits in start_grid.
refresh_bat() {
  local cfg="$HOME/.config/fabrik" desk="" why="" bat="${FABRIK_AGENTS_BAT:-${SELF%/*}/agents_bat.py}" hand
  local log="$HOME/.config/fabrik/agents-bat-refresh.log"
  hand="python3 $(printf %q "$bat") --tabbed"
  [ -r "$HOME/.config/fabrik/agents-desktop" ] && { { IFS= read -r -d '' desk < "$HOME/.config/fabrik/agents-desktop"; } 2>/dev/null || :; }
  desk="${desk#"${desk%%[![:space:]]*}"}"
  desk="${desk%"${desk##*[![:space:]]}"}"
  if [ -z "$desk" ]; then
    echo "agents_up: no desktop remembered, so All Agents (tabbed).bat was not refreshed — once: $hand --desktop <the Windows desktop folder>" >&2
    return 0
  fi
  if [ ! -d "$desk" ]; then
    echo "agents_up: the remembered desktop $desk is not a folder, so All Agents (tabbed).bat was not refreshed — once: $hand --desktop <the Windows desktop folder>" >&2
    return 0
  fi
  [ -f "$bat" ] || why="$bat is not a file"
  command -v setsid >/dev/null || why="setsid is missing"
  command -v flock >/dev/null || why="flock is missing"
  # shellcheck disable=SC2016  # the child's script is single-quoted on purpose: its $1..$3 are its own arguments
  if [ -z "$why" ] && { setsid -f bash -c '
      printf "agents_up: refresh %s %s pid %s\n" "$(date "+%F %T")" "$3" "$$"
      { exec 8>"$1/agents-bat-refresh.pending" && flock -n 8; } || { echo "agents_up: a refresh is already waiting; it reads this grid too"; exit 0; }
      echo "agents_up: queued; waiting for any running refresh"
      { exec 9>"$1/agents-bat-refresh.run" && flock 9; } || exit 1
      flock -u 8
      exec 8>&-
      exec python3 "$2" --tabbed' agents_up-refresh "$cfg" "$bat" "$S" </dev/null >>"$log" 2>&1; } 2>/dev/null; then
    echo "agents_up: All Agents (tabbed).bat refresh started in the background; its outcome goes to $log" >&2
  else
    echo "agents_up: could not start the All Agents (tabbed).bat refresh${why:+ ($why)} — run by hand: $hand" >&2
  fi
}

# The new grid. For four builders or fewer it is one window `agents`, even-horizontal, @agent on each pane. `@agents_up_building`
# holds this process's PID from the new-session (chained with `\;` in the SAME tmux invocation, before the root is
# recorded) to the end, so a `--window` poll never sees the session without it; it is unset at the end AND by an EXIT trap,
# and counts only while the PID is alive. Cobra (D-253): the cheapest way past it is a flag that never clears — the PID
# test makes a builder that died mid-build read "not building".
start_grid() {
  local name sid folder new dir st cmd out wid pid k placed=0 raced=0 pane0="" grouped_stale=0 stale_members=""
  local bflag="$$:$(proc_start "$$")"
  local -a wins=()
  check_spawn_vars
  slice_ceiling
  while read -r name sid folder new; do
    dir="$(dir_of "$folder")"
    [ -n "$dir" ] || continue
    st="$(status_of "$sid" "$dir" "$name")"
    newer_unbound "$name" "$sid" "$dir"
    [ "$st" = no-transcript ] && [ "$new" != 1 ] && echo "agents_up: $name: no transcript for session $sid under $(proj_of "$dir") — the pane will try anyway" >&2
    cmd="$(cmd_of "$name" "$sid" "$st" "$new")"
    if [ "$placed" = 0 ]; then
      if ! out="$(tmux new-session -d -s "$S" -n "$W" -c "$dir" -x 240 -y 60 -P -F '#{window_id} #{pane_id}' "$cmd" \; set-option -t "=$S:" @agents_up_building "$bflag")"; then
        # a second launch racing this one built the grid first: attach to it (if it is this repo's) rather than fail
        if tmux has-session -t "=$S" 2>/dev/null; then
          owned_here || exit 2
          raced=1
          break
        fi
        exit 1
      fi
      BUILDING=1  # on_exit unsets @agents_up_building on any exit from here on
      read -r wid pid <<< "$out"
      if ! [[ "$wid" =~ ^@[0-9]+$ && "$pid" =~ ^%[0-9]+$ ]]; then
        echo "agents_up: tmux gave no window and pane id for $S's first pane ('$out') — not continuing" >&2
        exit 1
      fi
      wins+=("$wid")
      pane0="$pid"
      clear_stale_group
      tmux set-option -t "=$S:" @agents_up_root "$ROOT" >/dev/null ||
        echo "agents_up: could not record the root on $S — a relaunch cannot confirm this grid is this repo's and will attach it with a warning" >&2
    elif [ $((placed % PER_WINDOW)) = 0 ]; then
      k=$((placed / PER_WINDOW + 1))
      out="$(tmux new-window -d -t "=$S:" -n "agents-$k" -c "$dir" -P -F '#{window_id} #{pane_id}' "$cmd")" || out=""
      read -r wid pid <<< "$out"
      if ! [[ "$wid" =~ ^@[0-9]+$ && "$pid" =~ ^%[0-9]+$ ]]; then
        echo "agents_up: no room for $name's pane (session $sid) — open it by hand: $cmd" >&2
        NO_ROOM=1
        continue
      fi
      wins+=("$wid")
    else
      wid="${wins[$((${#wins[@]} - 1))]}"
      pid="$(tmux split-window -t "$wid" -c "$dir" -P -F '#{pane_id}' "$cmd")" || pid=""
      if ! [[ "$pid" =~ ^%[0-9]+$ ]]; then
        echo "agents_up: no room for $name's pane (session $sid) — open it by hand: $cmd" >&2
        NO_ROOM=1
        continue
      fi
    fi
    wid="${wins[$((${#wins[@]} - 1))]}"
    tmux select-layout -t "$wid" even-horizontal >/dev/null
    tmux set -p -t "$pid" @agent "$name"
    placed=$((placed + 1))
  done <<< "$AGENTS"
  # every resolved worktree went away between the resolve and here: no session was made, so there is nothing to select or attach
  if [ "$placed" = 0 ] && [ "$raced" = 0 ]; then
    echo "agents_up: every builder's worktree went away between resolve and launch — nothing launched" >&2
    exit 2
  fi
  # a launch that lost the race leaves the other launch's grid as that launch arranges it
  [ "$raced" = 1 ] && return 0
  for ((k = 2; k <= ${#wins[@]}; k++)); do
    if [ "$grouped_stale" = 1 ]; then
      echo "agents_up: window agents-$k stays in $S — free the group first (the kill-session above), then: $SELF --window $k $ROOT" >&2
    else
      ensure_overflow "$k" "${wins[$((k - 1))]}" || echo "agents_up: window agents-$k stays in $S (attach it with: $SELF --window $k $ROOT)" >&2
    fi
  done
  # <S>'s own current window is tab 1's `agents`, whatever the overflow sessions selected
  tmux select-window -t "=$S:${wins[0]}" >/dev/null
  tmux select-pane -t "$pane0"
  tmux set-option -t "=$S:" -u @agents_up_building >/dev/null 2>&1
  BUILDING=0
  refresh_bat
}

# --window <n> <repo>: attach the session showing window agents-<n>. Waits (every 2 s, up to FABRIK_AGENTS_WINDOW_WAIT_S,
# 120) while the grid is absent or a LIVE builder is still building it; a flag whose PID is dead, or no flag, is a grid
# that is not being built.
window_mode() {
  local wait_s="${FABRIK_AGENTS_WINDOW_WAIT_S:-120}" waited=0 b wid
  [[ "$wait_s" =~ ^[0-9]{1,6}$ ]] || bad_arg "bad FABRIK_AGENTS_WINDOW_WAIT_S '$wait_s' (whole seconds)"
  while :; do
    if tmux has-session -t "=$S" 2>/dev/null; then
      b="$(tmux show-options -t "=$S:" -v @agents_up_building 2>/dev/null)"
      building_live "$b" || break
    fi
    if [ "$waited" -ge "$((10#$wait_s))" ]; then
      echo "agents_up: the $S grid was not ready within $wait_s s" >&2
      exit 2
    fi
    # a --tab is black while it waits: say so once, before the first sleep
    [ "$tab" = 1 ] && [ "$waited" = 0 ] && echo "agents_up: waiting up to $wait_s s for the $S grid to be built" >&2
    sleep 2
    waited=$((waited + 2))
  done
  owned_here || exit 2
  wid="$(find_window "agents-$winn")"
  if [ -n "$wid" ]; then
    ensure_overflow "$winn" "$wid" || exit 2
    ATT="$S+$winn"
  else
    echo "agents_up: the $S grid has no window agents-$winn now — showing its current window" >&2
    if tmux has-session -t "=$S+$winn" 2>/dev/null; then tmux kill-session -t "=$S+$winn" >/dev/null 2>&1; fi
  fi
}

ATT="$S"
NO_ROOM=0  # start_grid sets 1 when a builder got no pane: exit 4 on every path that does not attach
if [ -n "$winn" ]; then
  window_mode
elif tmux has-session -t "=$S" 2>/dev/null; then
  owned_here || exit 2
  echo "agents_up: the $S grid is already up — leaving it as it is; a registry change takes effect after: $(kill_hint)" >&2
else
  start_grid
fi
tmux source-file "$HOME/.tmux.conf" 2>/dev/null
# --detach (the boot sweep, cron: no terminal) stops here; so does any caller with no terminal, which says so
if [ "$detach" = 1 ]; then
  echo "agents_up: --detach — the $S grid is up, not attaching (attach with: tmux attach -t =$ATT)" >&2
  [ "$NO_ROOM" = 1 ] && exit 4
  exit 0
fi
# under --tab a missing terminal is said before anything else: never the switch-client exec (a leaked TMUX), whose
# exit 0 would close the tab with no reason
if { [ ! -t 0 ] || [ ! -t 1 ]; } && [ "$tab" = 1 ]; then
  echo "agents_up: --tab but no terminal on stdin/stdout — the $S grid is up, nothing to attach here (attach with: tmux attach -t =$ATT)" >&2
  [ "$NO_ROOM" = 1 ] && exit 4
  exit 1
fi
# run from inside tmux (a hub pane), attaching would nest; switch the client instead
[ -n "${TMUX:-}" ] && exec tmux switch-client -t "=$ATT"
if [ ! -t 0 ] || [ ! -t 1 ]; then
  echo "agents_up: no terminal on stdin/stdout, so there is nothing to attach — the $S grid is up and left detached (attach with: tmux attach -t =$ATT)" >&2
  [ "$NO_ROOM" = 1 ] && exit 4
  exit 0
fi
exec tmux attach -t "=$ATT"
