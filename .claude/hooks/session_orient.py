#!/usr/bin/env python3
# AFTER-EDIT: tests/test_session_orient_hook.py
"""SessionStart orientation (Fabrik-synced, stdlib-only, fail-open).

Every session starts with an explicit orientation block so the agent is AWARE
of what is connected to it before any work: the governing CLAUDE.md (hub
contract in /opt/fabrik, synced template copy in projects — the text branches
on repo identity), the persistent MEMORY.md index, the session-recall MCP
tools, and the enforcement mesh (Stop hook, prompt router, final_gate).
CLAUDE.md and MEMORY.md are harness-auto-loaded — this hook does not re-read
them; it BINDS the agent to act on them and surfaces their state. Fail-open:
any error exits 0 (a broken orientation must never block a session).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Read at most this much of MEMORY.md when counting entries (bound reads by
# bytes — a pathological index must not spike every SessionStart).
_MEMORY_READ_BYTES = 256 * 1024


def _memory_line(cwd: str) -> str:
    # Harness project-key convention: '/' AND '.' become '-'
    # (ground truth: ~/.claude/projects/-opt-…--rec-…-jpg style keys).
    proj_key = cwd.replace("/", "-").replace(".", "-")
    idx = (
        Path(os.environ.get("HOME", str(Path.home())))
        / ".claude/projects"
        / proj_key
        / "memory/MEMORY.md"
    )
    try:
        if idx.is_file():
            with open(idx, encoding="utf-8", errors="replace") as f:
                head = f.read(_MEMORY_READ_BYTES)
            entries = sum(1 for line in head.splitlines() if line.lstrip().startswith("- "))
            more = "+" if len(head) == _MEMORY_READ_BYTES else ""
            return (
                f"- **Memory:** your MEMORY.md index is loaded ({entries}{more} entries). Recalled"
                " facts in system-reminders are background truth-at-write-time — verify named"
                " files/flags still exist. Save new durable facts per the memory contract; update,"
                " don't duplicate."
            )
    except OSError:
        pass
    return (
        "- **Memory:** no memory index yet for this project — when you learn a durable fact"
        " (operator preference, project constraint, feedback), write it per the memory contract."
    )


def _governance_line(cwd: str) -> str:
    # Repo identity is CONTENT-based (same discipline as /fabrik-upstream): the
    # hub is wherever the synced-manifest module sits at toplevel — never a
    # hardcoded path.
    if (Path(cwd) / "scripts/fabrik_synced_manifest.py").is_file():
        return (
            "- **Governance (HUB):** this is the platform repo — CLAUDE.md HERE is the hub"
            " agents' own contract: canonical and yours to edit (a synced-surface commit"
            " distributes fleet-wide; the project-facing template lives at"
            " templates/governance/CLAUDE.md). Obey it fully; every task-completing output owes"
            " the RULES ACTIVE line and ends with the 6-line FINAL OUTPUT block (incl."
            " DONE:/NEXT:)."
        )
    return (
        "- **Governance:** this project's CLAUDE.md is already loaded into your context. It is"
        " Fabrik-SYNCED (distributed from the hub's templates/governance/CLAUDE.md) — obey it"
        " fully; NEVER edit the local copy (the next sync overwrites it; changes go upstream via"
        " /fabrik-upstream). Every task-completing output owes the RULES ACTIVE line and ends"
        " with the 6-line FINAL OUTPUT block (incl. DONE:/NEXT:)."
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(errors="replace")  # C-locale must degrade, not swallow
    except Exception:
        pass
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    cwd = str(data.get("cwd") or os.getcwd())

    print(
        "## ORIENT (binding — read before acting)\n"
        + _governance_line(cwd)
        + "\n"
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
