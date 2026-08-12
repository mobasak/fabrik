#!/usr/bin/env python3
# AFTER-EDIT: tests/test_agent_role_hook.py, docs/reference/agents/, docs/workstation/hooks-index.md
"""SessionStart hook — inject the named agent's role charter (Fabrik-synced, fleet-safe).

Reads ``CLAUDE_AGENT`` and prints the matching charter from
``docs/reference/agents/<name>.md`` so a hub session starts as its standing agent
(infra/fleet/intel — hub-agent-roles spec r2). FLEET-SAFE BY CONSTRUCTION: this hook
syncs to every project, where ``CLAUDE_AGENT`` is unset and no charters exist — every
non-hub path is a SILENT no-op with exit 0 (a SessionStart hook that errors or chatters
would pollute ~46 repos' session starts). stdout only; never writes.
"""

from __future__ import annotations

import os
import re
import sys

_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
_MAX_CHARTER_BYTES = 32_768  # a charter is ~2KB; anything huge is not a charter


def main() -> int:
    name = os.environ.get("CLAUDE_AGENT", "").strip()
    if not name or not _NAME_RE.fullmatch(name):
        return 0  # unset or malformed → silent no-op (the fleet case)
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    path = os.path.join(root, "docs", "reference", "agents", f"{name}.md")
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            body = fh.read(_MAX_CHARTER_BYTES)
    except OSError:
        return 0  # no charter here → silent no-op (the fleet case)
    if not body.strip():
        return 0
    print(f"## AGENT ROLE: {name} (charter — binding overlay on CLAUDE.md)")
    print(body.rstrip())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # belt-and-suspenders fail-open: a role hook must never block a session
