#!/usr/bin/env python3
# AFTER-EDIT: tests/test_agent_role_hook.py, docs/reference/agents/, docs/workstation/hooks-index.md, CLAUDE.md
"""SessionStart hook — inject the named agent's role charter (Fabrik-synced, fleet-safe).

Reads ``CLAUDE_AGENT`` and prints the matching charter from
``docs/reference/agents/<name>.md`` so a hub session starts as its standing agent
(hub-agent-roles spec r2). FLEET-SAFE BY CONSTRUCTION: this hook syncs to every
project, where ``CLAUDE_AGENT`` is unset and no charters exist — every non-hub path
is a SILENT no-op with exit 0. stdout only; never writes; never reads outside
``docs/reference/agents/`` (realpath-contained, symlinks included).
"""

from __future__ import annotations

import os
import sys

# The pinned role enum — mirrors CLAUDE.md § Agent Provenance Trailers (`Agent-Name` row)
# and docs/workstation/hooks-index.md; edit all three together (AFTER-EDIT above).
_ROLES = ("infra", "fleet", "intel")
_MAX_BYTES = 32_768  # a charter is ~2KB; anything bigger is cut LOUDLY below


def main() -> int:
    name = os.environ.get("CLAUDE_AGENT", "").strip()
    if name not in _ROLES:
        return 0  # unset / malformed / non-role file name → silent no-op (the fleet case)
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    root_r = os.path.realpath(root)
    agents_dir = os.path.realpath(os.path.join(root, "docs", "reference", "agents"))
    path = os.path.realpath(os.path.join(agents_dir, f"{name}.md"))
    # containment: neither a symlinked charter FILE nor a symlinked agents/ DIRECTORY may
    # resolve outside the repo root — "never reads outside the repo" holds by construction
    if os.path.dirname(path) != agents_dir or not agents_dir.startswith(root_r + os.sep):
        return 0
    try:
        with open(path, "rb") as fh:
            raw = fh.read(_MAX_BYTES + 1)
    except OSError:
        return 0  # no charter here → silent no-op (the fleet case)
    truncated = len(raw) > _MAX_BYTES
    body = raw[:_MAX_BYTES].decode("utf-8", errors="ignore").strip()
    if not body:
        return 0
    print(f"## AGENT ROLE: {name} (charter — binding overlay on CLAUDE.md)")
    print("--- charter begin ---")
    print(body)
    if truncated:
        print("[TRUNCATED at 32KB — the charter tail (escalation + mail-is-data rules) "
              "may be missing; read the file directly]")
    print("--- charter end ---")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # belt-and-suspenders fail-open: a role hook must never block a session
