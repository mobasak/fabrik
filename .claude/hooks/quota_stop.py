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
# A lone `&` is bash's BACKGROUND separator — `git status & evil` runs both, and the whole-line
# hardening listed `&&` but never the single form: proven by execution (a held session's
# `git status & touch marker` was allowed and the marker appeared — review 2026-09-05, pass 13).
# `(?<![0-9>])&(?!&)`: not an fd-duplication (`2>&1`, `>&2`) and not the `&&` the first branch
# already catches.
# `<(` / `>(` is PROCESS SUBSTITUTION — bash runs the inner command: `git status <(touch m)` was
# allowed and the marker appeared (review 2026-09-05, pass 14, executed). No operator on the
# list, no quote to mask; the paren after `<`/`>` is the tell.
_UNSAFE_SHELL = re.compile(r"&&|\|\||;|\||\$\(|`|\n|(?<![0-9>])&(?!&)|[<>]\(")
# `(?!>)` after the optional second `>` and `>` in the lookbehind: without them `>>?` BACKTRACKED
# on `>> /dev/null` — the two-char match failed the /dev/null exemption, so the engine matched a
# single `>` whose lookahead saw `> /dev/null` and refused the very form the exemption names
# (review 2026-09-05, closing pass, found by execution; fail-closed, so it only over-refused).
_FILE_REDIRECT = re.compile(
    # The exemption is the DEVICE, not a prefix: `/dev/null` must be followed by whitespace,
    # end of line or a shell operator — `>/dev/nullx`, `>/dev/null/../x` and `>/dev/null.txt`
    # all matched the bare prefix and were allowed (review 2026-09-05, pass 12, executed).
    # `>&` is an fd DUPLICATION only when a digit or `-` follows (`2>&1`, `>&2`, `>&-`); `>&word`
    # is bash's "redirect stdout+stderr to FILE word" — proven by execution: `git log >&x` was
    # allowed and created `x` (review 2026-09-05, pass 12, native finder). The fd must be the
    # WHOLE token: `>&1x` opens a file named `1x`.
    r"(?<![0-9>])>>?(?!>)(?!\s*/dev/null(?![^\s;&|)]))(?!&(?:\d+|-)(?![\w.]))"
    r"|(?<!>)\d>>?(?!>)(?!\s*/dev/null(?![^\s;&|)]))(?!&(?:\d+|-)(?![\w.]))"
)


def _mask_quoted(command: str) -> str:
    """Blank shell-QUOTED spans so the vetoes above see OPERATORS, not DATA.

    They scan the raw line, so a `;` or `|` inside a quoted ARGUMENT reads as a control operator
    and refuses an otherwise-allowed command. Not hypothetical: the BLOCKED format CLAUDE.md
    mandates ("<what> - searched: <a>; <b> - missing: <need>") puts a semicolon in the `--reason`
    of the very `command_run.py blocked` call this hold's own message orders a held session to
    make, so the hold structurally refused its own graceful exit while the Stop hook blocked the
    turn for the record it could not close (trade-intelligence 01M1NTZJEHF9NY93JW8YZNDAVB;
    mechanism proven by fleet 01M1NTZZEZJGHKYR7VQF4PZAM2, who wrote the whole-line scan).

    Every existing tooth survives, because masking only removes characters the SHELL would not
    have acted on either:
      - single-quoted spans are masked whole - the shell expands nothing inside them;
      - double-quoted spans KEEP `$` and a backtick, which the shell still expands there, so
        `git status "$(rm -rf x)"` is still refused;
      - a backslash escape inside double quotes masks BOTH characters, since an escaped dollar
        or backtick is a literal rather than an expansion;
      - a newline is NEVER masked, quoted or not - a multi-line command stays refused;
      - an UNBALANCED quote returns the line untouched, so something that would not even parse
        meets the vetoes raw and fails closed.

    `shlex.split` is not a substitute: it returns ['git', 'status;evil'] for `git status;evil`,
    so a leading-word parse would ALLOW the chained bypass this masking still denies.
    """
    out: list[str] = []
    quote: str | None = None
    i, n = 0, len(command)
    while i < n:
        ch = command[i]
        if quote is None:
            if ch == "\\" and i + 1 < n:
                # OUTSIDE quotes a backslash makes the next character literal, whatever it is —
                # so `\'` is a quote CHARACTER, never a quote OPENER. Without this the first cut
                # of the masker toggled quote state on any bare quote, and a real operator
                # placed between two escaped single quotes was masked to data and ALLOWED:
                # `git status \'; rm -rf x\'` passed decide() and bash ran the second command
                # (review pass 1, native finder, proven by execution with a file side effect).
                # Both characters are kept visible: an escaped operator (`\;`) stays refused,
                # which is the pre-existing fail-closed the finder confirmed CLEAN.
                out.extend((ch, command[i + 1]))
                i += 2
                continue
            if ch in ("'", '"'):
                quote = ch
            out.append(ch)
            i += 1
        elif ch == quote:
            quote = None
            out.append(ch)
            i += 1
        elif ch == "\n":
            out.append(ch)  # a quoted newline is still a refused multi-line command
            i += 1
        elif quote == '"' and ch == "\\" and i + 1 < n:
            out.extend(("x", "x"))  # an escaped $ ` " or \ is a literal, not an expansion
            i += 2
        elif quote == '"' and ch in "$`":
            # the shell expands these INSIDE double quotes - keep them visible. The `(` of a
            # substitution rides along, because _UNSAFE_SHELL keys on the PAIR `$(`: masking the
            # paren alone let a double-quoted command substitution through, which this fix's own
            # test caught before it shipped.
            out.append(ch)
            i += 1
            if ch == "$" and i < n and command[i] == "(":
                out.append("(")
                i += 1
        else:
            out.append("x")
            i += 1
    return command if quote is not None else "".join(out)


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
        # the vetoes read the MASKED line (operators only); the allow-list reads the RAW line,
        # because the leading command word is never quoted in a command we would allow.
        masked = _mask_quoted(command) if command is not None else ""
        if (
            command is not None
            and not _UNSAFE_SHELL.search(masked)
            and not _FILE_REDIRECT.search(masked)
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
