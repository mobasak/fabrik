#!/usr/bin/env python3
# AFTER-EDIT: tests/test_session_orient_hook.py
"""SessionStart orientation (Fabrik-synced, stdlib-only, fail-open).

Every project session starts with an explicit orientation block so the agent is
AWARE of what is connected to it before any work: the synced CLAUDE.md
governance (binding, never edited locally), its persistent MEMORY.md index,
the session-recall MCP tools, and the enforcement mesh (Stop hook, prompt
router, final_gate). CLAUDE.md and MEMORY.md are harness-auto-loaded — this
hook does not re-read them; it BINDS the agent to act on them and surfaces
their state. Fail-open: any error exits 0 silently (a broken orientation must
never block a session).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _memory_line(cwd: str) -> str:
    proj_key = cwd.replace("/", "-")
    idx = Path(os.environ.get("HOME", str(Path.home()))) / ".claude/projects" / proj_key / "memory/MEMORY.md"
    try:
        if idx.is_file():
            entries = sum(
                1 for line in idx.read_text(encoding="utf-8", errors="replace").splitlines()
                if line.lstrip().startswith("- ")
            )
            return (
                f"- **Memory:** your MEMORY.md index is loaded ({entries} entries). Recalled facts in"
                " system-reminders are background truth-at-write-time — verify named files/flags still"
                " exist. Save new durable facts per the memory contract; update, don't duplicate."
            )
    except OSError:
        pass
    return (
        "- **Memory:** no memory index yet for this project — when you learn a durable fact"
        " (operator preference, project constraint, feedback), write it per the memory contract."
    )


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    cwd = str(data.get("cwd") or os.getcwd())

    print(
        "## ORIENT (binding — read before acting)\n"
        "- **Governance:** this project's CLAUDE.md is already loaded into your context. It is"
        " Fabrik-SYNCED (distributed from the hub's templates/governance/CLAUDE.md) — obey it fully;"
        " NEVER edit the local copy (the next sync overwrites it; changes go upstream via"
        " /fabrik-upstream). Your first task-completing output owes the RULES ACTIVE line; every"
        " task-completing response ends with the 6-line FINAL OUTPUT block (incl. DONE:/NEXT:).\n"
        + _memory_line(cwd)
        + "\n"
        "- **session-recall is CONNECTED:** `search_chats` (keyword) · `recent_chats` (recency) ·"
        " `get_chat` (read one). MANDATORY before answering when resuming work, when the user"
        " references a prior decision not in this conversation, or after compaction — never claim no"
        " previous conversation exists without searching first.\n"
        "- **Enforcement mesh wired to this session:** the Stop hook blocks unfinished exits (gate"
        " red on YOUR files · your work uncommitted · promise/permission stalls); the prompt router"
        " suggests the owning /fabrik-* skill; `python scripts/final_gate.py --json` is the"
        " completion gate. Work WITH them — they are the definition of done, not obstacles."
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # fail-open, always
