#!/usr/bin/env bash
# AFTER-EDIT: docs/workstation/claude-tab-router.md | tests/test_claude_tab_router.py
# claude-agent-wrapper.sh — VS Code `claudeCode.claudeProcessWrapper` (W-ea993618). Installed by copy at
# ~/.claude/bin/claude-agent-wrapper.sh (docs/workstation/claude-tab-router.md § Install); this file is its source.
#
# Contract (measured in the extension's own code, extension.js `Zk`, claude-code 2.1.301): with the setting, the
# extension runs THIS file as the executable with the bundled native binary as its FIRST argument, then the CLI args
# — so `exec "$@"` launches exactly what the extension would have launched without a wrapper.
#
# It must NEVER fail a launch: every chat tab on the box goes through it, this one included. So nothing below may
# exit; a log that cannot be written is skipped, and if $1 is not an executable (the extension found no bundled
# binary) the claude on PATH runs the same args. stdout and stderr belong to the extension (it speaks stream-json over
# them): the wrapper writes to neither, and the router's output is captured, never passed through.
#
# Stage 2 — the tab ROUTER: a stream-json chat launch asks scripts/sysadmin/claude_tab_router.py where and as whom
# the tab runs (a picker; a restored foreign tab is re-rooted silently). Router exit 0 = its NUL-separated answer
# (cwd, CLAUDE_AGENT, argv) is applied; anything else — cancel, refusal, timeout, error — launches as today. The
# extension's config probe (CLAUDE_CODE_CONFIG_PROBE, also a stream-json launch) never reaches the router. The router
# reads no stdin (the extension's initialize message stays in the pipe for the CLI) and writes nothing to stderr. The
# extension fails a chat whose process has not initialised within 60 s: the picker's deadline is 30 s and the router
# runs under `timeout -k 2 35`; it is handed this wrapper's pid and closes when the wrapper dies.
# Kill switch: CLAUDE_TAB_ROUTER=off (claudeCode.environmentVariables) skips the router entirely.
#
# The log takes argv, the cwd and the NAMES of the CLAUDE_* variables, with values only for an allow-list that holds
# no secret (a token may sit in a CLAUDE_* variable).
log="${CLAUDE_AGENT_WRAPPER_LOG:-$HOME/.claude/state/wrapper-launch.log}"
router="${CLAUDE_TAB_ROUTER_CMD:-/opt/fabrik/scripts/sysadmin/claude_tab_router.py}"
{ : >> "$log"; } 2>/dev/null && {
  printf '%s pid=%s ppid=%s cwd=%s\n' "$(date '+%F %T')" "$$" "$PPID" "$PWD"
  printf '  argv:'
  printf ' %q' "$@"
  printf '\n  env:'
  for v in $(compgen -e | grep '^CLAUDE' || true); do
    case "$v" in
      CLAUDE_AGENT | CLAUDE_CONFIG_DIR | CLAUDE_QUOTA_HOME | CLAUDE_CODE_ENTRYPOINT | CLAUDECODE) printf ' %s=%q' "$v" "${!v}" ;;
      *) printf ' %s' "$v" ;;
    esac
  done
  printf '\n'
} >> "$log" 2>/dev/null || true

routed=()
case " $* " in
  *" --input-format stream-json "* | *" --input-format=stream-json "*)
    if [ "${CLAUDE_TAB_ROUTER:-on}" != "off" ] && [ -z "${CLAUDE_CODE_CONFIG_PROBE:-}" ] && [ -f "$router" ]; then
      mapfile -d '' -t routed < <(timeout -k 2 35 python3 "$router" route --cwd "$PWD" --wrapper-pid "$$" -- "$@" </dev/null 2>/dev/null; printf '\0%s' "$?") || routed=()
    fi
    ;;
esac
# the last element is the router's exit status (appended after its NUL-separated answer)
if [ "${#routed[@]}" -ge 4 ] && [ "${routed[-1]}" = "0" ]; then
  unset 'routed[-1]'
  new_cwd="${routed[0]}"
  new_agent="${routed[1]}"
  if cd "$new_cwd" 2>/dev/null; then
    { printf '  router: cwd=%s agent=%s argv:' "$new_cwd" "$new_agent"; printf ' %q' "${routed[@]:2}"; printf '\n'; } >> "$log" 2>/dev/null || true
    # a role-less pick (New session in <repo>, a re-root with no role) must not inherit the window's own agent
    if [ -n "$new_agent" ]; then export CLAUDE_AGENT="$new_agent"; else unset CLAUDE_AGENT; fi
    set -- "${routed[@]:2}"
  fi
fi

if [ -n "${1:-}" ] && [ -x "$1" ]; then
  exec "$@"
fi
exec claude "$@"
