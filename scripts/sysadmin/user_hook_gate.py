#!/usr/bin/env python3
# AFTER-EDIT: tests/test_user_hook_gate.py | docs/workstation/hooks-index.md
"""USER-level hook gate: run a hub hook for every window UNLESS the project already wires it.

Closes the sync-excluded gap (fabrik-lib had no MCP banner and no quota hold, 2026-09-06)
without editing a fleet-synced hook and without touching the exclusion ruling: the hub's
`.claude/hooks/mcp_watch.py` and `quota_stop.py` are registered at user level THROUGH this gate.
In the 42 synced repos the project's own copy fires and this exits silently — no double banner,
no double deny. In fabrik-lib, /opt itself, and any cwd with no project hooks, the hub copy fires.

    user_hook_gate.py /opt/fabrik/.claude/hooks/<hook>.py     (stdin: the hook payload, passed through)

DETECTION (review B2/B3, 2026-09-06): the project ROOT is `CLAUDE_PROJECT_DIR`, else the nearest
ancestor of the payload's cwd holding `.claude/settings.json` — a subdirectory cwd used to miss
the file and fire the hook a second time. Its `settings.json` (+ `settings.local.json`) is PARSED,
and the gate defers only when a hook entry under the SAME `hook_event_name` as the incoming
payload names this hook's basename in its command — a mention in `permissions.deny`, a wiring
under the wrong event, or a registration beside `"disableAllHooks": true` used to defer by
substring and silently strip the window of its hold. Unreadable settings → the hook RUNS
(fail-open toward coverage).

THE CONTRACT PRESERVED (B1): `quota_stop.py` denies by printing JSON on STDOUT
(`hookSpecificOutput.permissionDecision: "deny"`) and EXITS 0 — never a non-zero exit. The gate
therefore forwards stdout byte for byte and returns the child's exit code unchanged; a grader runs
the real hook through it and compares bytes. A hang is fail-OPEN with one line on stderr (B8); a
missing hook path is fail-OPEN with one line on stderr (B9) — never silence, which read as "ran
and allowed".
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_TIMEOUT_S = float(os.environ.get("USER_HOOK_GATE_TIMEOUT_S", "8"))  # below the registration's 10 s


def _project_root(cwd: str) -> Path | None:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and (Path(env) / ".claude").is_dir():
        return Path(env)
    p = Path(cwd)
    home = Path.home()
    for cand in (p, *p.parents):
        if cand == home or cand in home.parents:
            # `~/.claude/settings.json` is the USER level — the file holding this gate's own
            # registration. Climbing into it made the gate detect ITSELF as the project wiring
            # and defer for every cwd under $HOME (review P2-2).
            return None
        if (cand / ".claude" / "settings.json").is_file():
            return cand
    return None


def _matches(matcher: object, tool_name: str) -> bool:
    """A project entry wired under a `matcher` covers only the tools it names (Claude Code
    matches the tool name against it as a regex); a partial wiring must not strip the hub hold
    from the tools the project never covered (review P2-4). No tool name (a non-tool event)
    → the matcher is moot."""
    if not tool_name or matcher in (None, "", ".*", "*"):
        return True
    try:
        return re.fullmatch(str(matcher), tool_name) is not None
    except re.error:
        return str(matcher) == tool_name


def _project_wires(cwd: str, basename: str, event: str, tool_name: str = "") -> bool:
    root = _project_root(cwd)
    if root is None:
        return False
    wired = False
    for name in ("settings.json", "settings.local.json"):
        try:
            f = root / ".claude" / name
            if not f.is_file():
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(d, dict):
                continue
            if d.get("disableAllHooks") is True:
                return False  # a kill switch in ANY file silences every project hook (P2-5)
            hooks = d.get("hooks")
            if not isinstance(hooks, dict):
                continue  # a list-shaped `hooks` is not a wiring; the hub hook RUNS (P2-3)
            for entry in hooks.get(event) or []:
                if not isinstance(entry, dict):
                    continue
                for h in entry.get("hooks") or []:
                    if isinstance(h, dict) and basename in str(h.get("command", "")):
                        if _matches(entry.get("matcher"), tool_name):
                            wired = True
        except Exception:  # noqa: BLE001 — fail-open toward RUNNING the hook
            continue
    return wired


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "user_hook_gate: usage: user_hook_gate.py <hub-hook.py> — nothing run", file=sys.stderr
        )
        return 0
    hook = Path(argv[1])
    raw = sys.stdin.buffer.read()  # BYTES in, bytes out — never decoded on the way through (P2-6)
    try:
        payload = json.loads(raw.decode("utf-8", "replace") or "{}")
        cwd = str(payload.get("cwd") or os.getcwd())
        event = str(payload.get("hook_event_name") or "")
        tool = str(payload.get("tool_name") or "")
    except Exception:  # noqa: BLE001
        cwd, event, tool = os.getcwd(), "", ""
    if _project_wires(cwd, hook.name, event, tool):
        return 0
    if not hook.is_file():
        print(
            f"user_hook_gate: {hook} is missing — {hook.name} did NOT run for this window",
            file=sys.stderr,
        )
        return 0
    try:
        proc = subprocess.run(
            [sys.executable, str(hook)],
            input=raw,
            capture_output=True,
            timeout=_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        print(
            f"user_hook_gate: {hook.name} timed out after {_TIMEOUT_S:.0f}s — allowed (fail-open)",
            file=sys.stderr,
        )
        return 0
    # byte for byte: `text=True` translated newlines and raised on non-UTF-8 output, losing the
    # child's whole stdout — a deny payload, in the shape that matters (review P2-6)
    sys.stdout.buffer.write(proc.stdout)
    sys.stdout.flush()
    sys.stderr.buffer.write(proc.stderr)
    sys.stderr.flush()
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
