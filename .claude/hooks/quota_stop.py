#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/hooks-index.md, docs/workstation/claude-account-rotation.md, scripts/fabrik_synced_manifest.py, tests/test_quota_stop_hook.py
"""PreToolUse — the fleet-wide GRACEFUL STOP when the quota is exhausted with nothing to rotate to.

Operator rule (2026-09-02): broadcast only when there is NO account left to rotate to and agents
are about to hit the wall — and then every agent must stop gracefully, losing no work, ready to be
restarted. Mail reaches a session only at its next prompt; this hook reaches it at its next TOOL
CALL, which is the only moment a mid-turn agent can be stopped.

Signal: the rotation tick's exhaustion stamp (`<state>/fleet-exhausted`), written by
`claude_rotate.py::_fleet_active_wall_advisory` exactly when the ACTIVE account is walled and the
picker found no successor (or the operator paused rotation), and unlinked by the same tick the
moment relief arrives (a flip or a reset). No other writer, no other reader with authority.

While the stamp stands the rule is DEFAULT-DENY: every tool that can change the world is held —
Edit/Write/MultiEdit/NotebookEdit, MCP editors (serena replace/insert/rename, browser clicks),
Agent/Workflow dispatch, and any Bash that is not ONE simple checkpoint or read command — with one instruction — commit + push your own work with
explicit pathspecs, close your run record, stop. Reads (Read/Grep/Glob/LS), git checkpointing,
`command_run.py`, `mail.py` and `thread_anchor.py` stay allowed, so a session can finish cleanly
and the Stop hook's commit-and-push law can be met. The block lifts by itself when the tick clears
the stamp; a session that already ended is restarted by the operator (or the resume mesh).

FAIL-OPEN, deliberately: no stamp → allow; unreadable state → allow; a stamp older than the tick
could have refreshed (the tick log has not moved for QUOTA_STOP_TICK_STALE_S, default 900s) →
allow with a one-line warning, because a dead cron must never freeze the fleet behind a stale
flag. ROTATE_STATE_DIR is honored (the tick's own override) so tests never touch the real stamp.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# While the stamp stands the matcher is `.*` and the rule is DEFAULT-DENY for anything that can
# change the world: an edit through an MCP tool (serena replace/insert/rename, a browser click, an
# Agent/Workflow dispatch) is an edit. Reads stay open so a session can orient and checkpoint.
_READ_TOOLS = {
    "Read",
    "Grep",
    "Glob",
    "LS",
    "ToolSearch",
    "AskUserQuestion",
    "TaskOutput",
    "Monitor",
    "ListMcpResourcesTool",
    "ReadMcpResourceTool",
    "ReadMcpResourceDirTool",
    "ListAgents",
}
_READ_MCP = re.compile(
    r"^mcp__(session-recall__|serena__(find_|get_|read_memory|list_memories|initial_instructions|onboarding))"
)
# Bash commands a stopping session still needs: checkpoint, close records, read. ONE simple
# command per call — the allow-list is matched against the WHOLE line, and a line carrying a
# control operator, a substitution or a file redirection is refused outright (review finding:
# `git push && python3 evil.py` passed a first-segment match).
_ALLOWED_BASH = re.compile(
    r"^\s*(git\s+(add|commit|push|status|diff|log|fetch|show|rev-parse|branch)\b"
    r"|git\s+reset\s+(-q\s+)?HEAD\b"  # index realign only — never --hard/--merge/--keep
    r"|python3?\s+\S*command_run\.py\b"
    r"|python3?\s+\S*mail\.py\b"
    r"|python3?\s+\S*thread_anchor\.py\b"
    r"|(cat|head|tail|grep|rg|ls|wc|md5sum|readlink|date|echo|pwd|find|stat)\b"
    r"|sed\s+-n\b(?!.*\s-i\b))"
)
_UNSAFE_SHELL = re.compile(r"&&|\|\||;|\||\$\(|`|\n")
_FILE_REDIRECT = re.compile(r"(?<![0-9])>>?(?!\s*/dev/null)(?!&)|\d>>?(?!\s*/dev/null)(?!&\d)")


def _state_dir() -> Path:
    return Path(os.environ.get("ROTATE_STATE_DIR") or Path.home() / ".claude" / "state")


def _stamp() -> Path:
    return _state_dir() / "fleet-exhausted"


def _tick_log() -> Path:
    return Path(
        os.environ.get("QUOTA_STOP_TICK_LOG") or Path.home() / ".claude" / "rotate-tick.log"
    )


def decide(
    tool: str,
    command: str | None,
    *,
    stamp_exists: bool,
    tick_age_s: float | None,
    now: float | None = None,
) -> tuple[str, str]:
    """Pure decision. Returns (action, reason) with action ∈ {"allow", "deny", "allow_warn"}."""
    if not stamp_exists:
        return "allow", ""
    stale_after = float(os.environ.get("QUOTA_STOP_TICK_STALE_S", "900"))
    if tick_age_s is None or tick_age_s > stale_after:
        return "allow_warn", (
            "quota-stop: the fleet-exhausted stamp exists but the rotation tick has not run for "
            f"{'unknown' if tick_age_s is None else f'{tick_age_s / 60:.0f}m'} — a stale flag never "
            "freezes the fleet; check `crontab -l` and ~/.claude/rotate-tick.log"
        )
    if tool == "Bash":
        if (
            command is not None
            and not _UNSAFE_SHELL.search(command)
            and not _FILE_REDIRECT.search(command)
            and _ALLOWED_BASH.match(command)
        ):
            return "allow", ""
        return "deny", _reason("Bash")
    if tool in _READ_TOOLS or _READ_MCP.match(tool):
        return "allow", ""
    return "deny", _reason(tool or "tool")


def _reason(tool: str) -> str:
    return (
        f"FLEET QUOTA EXHAUSTED — no account left to rotate to (the tick's fleet-exhausted stamp is "
        f"set). {tool} is held. STOP GRACEFULLY NOW: commit your own work with explicit pathspecs "
        "(`git commit -- <paths>`), `git push`, close your run record (`command_run.py done|blocked`), "
        "then end the turn — no new edits, no new phases. Reads, git, command_run.py, mail.py and "
        "thread_anchor.py stay allowed. The hold lifts by itself when the tick sees relief (a reset "
        "or a new account); a session that ended is restarted by the operator."
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # unreadable payload — never block on our own defect
    if not isinstance(payload, dict):
        return 0  # a non-object payload is not ours to judge — fail open (pass-2 probe: it raised)
    tool = str(payload.get("tool_name") or "")
    cmd = (
        (payload.get("tool_input") or {}).get("command")
        if isinstance(payload.get("tool_input"), dict)
        else None
    )
    try:
        exists = _stamp().exists()
    except OSError:
        exists = False
    age: float | None
    try:
        age = time.time() - _tick_log().stat().st_mtime
    except OSError:
        age = None
    action, reason = decide(
        tool, cmd if isinstance(cmd, str) else None, stamp_exists=exists, tick_age_s=age
    )
    if action == "deny":
        # ONLY the current PreToolUse contract: the installed CLI (2.1.258) deprecates the legacy
        # `decision` key here — "PreToolUse, use hookSpecificOutput.permissionDecision instead".
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": reason,
                    },
                }
            )
        )
    elif action == "allow_warn":
        sys.stderr.write(reason + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
