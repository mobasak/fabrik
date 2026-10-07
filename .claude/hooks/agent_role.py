#!/usr/bin/env python3
# AFTER-EDIT: tests/test_agent_role_hook.py, docs/reference/agents/, docs/workstation/hooks-index.md, CLAUDE.md
"""SessionStart hook — inject the named agent's role charter, if one exists (Fabrik-synced, fleet-safe).

Reads ``CLAUDE_AGENT`` (else the session's whoami binding) and, when it matches ``[a-z0-9-]{1,32}``, looks up
``docs/reference/agents/<name>.md`` and prints it ONLY when that file's first line
IS ``# Agent charter`` or STARTS WITH ``# Agent charter`` followed by whitespace
(e.g. ``# Agent charter — infra``) — any other file there, including a look-alike
first line (``# Agent charter-obsolete``, ``# Agent chartering``) or a non-charter
document (a kaizen log, a stray note), is silently skipped exactly like a missing
file, so a non-charter document can never be injected as a "binding overlay on
CLAUDE.md" just because its name matches an agent (hub-agent-roles spec r2, relaxed
by multi-agent-per-repo I2: any project-local agent name, not a fixed enum). The
charter is OPTIONAL — present-and-marked → injected; absent, unmarked, unset, or
malformed name → silent no-op, same as every project with no charters at all.
FLEET-SAFE BY CONSTRUCTION: a project that names agents but never writes charters
still injects nothing. stdout only; never writes; never reads outside
``docs/reference/agents/`` (realpath-contained, symlinks included).
"""

from __future__ import annotations

import os
import re
import sys

# Any project-local agent name — hub-agent-roles spec r2 relaxed the fixed
# ("infra", "fleet", "intel") enum to this shape (multi-agent-per-repo I2); a name
# matching it is a CANDIDATE regardless of whether a charter file exists for it, and
# regardless of whether that file is actually a charter (see _CHARTER_MARKER below).
# docs/workstation/hooks-index.md documents the same pattern (AFTER-EDIT above);
# CLAUDE.md's Agent-Name row states this same [a-z0-9-]{1,32} rule (the hub's three role names are its own practice, not a gate).
_NAME_RE = re.compile(r"[a-z0-9-]{1,32}")
_MAX_BYTES = 32_768  # a charter is ~2KB; anything bigger is cut LOUDLY below
# A file in docs/reference/agents/ is a CHARTER only if its first line IS this marker
# or STARTS WITH it followed by whitespace (see _has_charter_marker) — the dir also
# holds non-charter documents (e.g. kaizen logs) whose filename can coincidentally
# match an accepted agent name; those must never be injected as a "binding overlay on
# CLAUDE.md" (T02a acceptance review, findings 1 and its round-2 follow-up: a bare
# prefix match also let "# Agent charter-obsolete" or "# Agent chartering" through).
_CHARTER_MARKER = b"# Agent charter"


def _has_charter_marker(first_line: bytes) -> bool:
    if not first_line.startswith(_CHARTER_MARKER):
        return False
    rest = first_line[len(_CHARTER_MARKER) :]
    return rest == b"" or rest[:1].isspace()  # delimiter: end-of-line or whitespace only


def _bound_name(root: str) -> str:
    """The session's whoami binding (``scripts/whoami_agent.py --as <name>``) when
    ``CLAUDE_AGENT`` is unset — the route the ORIENT block offers an unnamed window, which
    otherwise got its items and mail but never its charter (kaizen 01M4C0VN6A). Uses the one
    resolver every reader shares (env first, then the session's LAST binding).

    Loaded BY FILE PATH, never by putting the project's ``scripts/`` on ``sys.path``: this hook
    runs in every synced repo, and a project-local module named like a stdlib one (a
    ``scripts/json.py``) would otherwise shadow what the resolver imports and could bind the
    wrong name (review 2026-10-08, A-S1). A project without the synced script, an older copy
    without ``resolve_agent_name``, or any error yields "" — the silent no-op stays the fleet case.
    """
    path = os.path.join(root, "scripts", "whoami_agent.py")
    if not os.path.isfile(path):
        return ""
    try:
        import importlib.util  # noqa: PLC0415 — only on the fallback path

        spec = importlib.util.spec_from_file_location("_fabrik_whoami_agent", path)
        if spec is None or spec.loader is None:
            return ""
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        resolve = getattr(mod, "resolve_agent_name", None)
        return str(resolve() or "") if callable(resolve) else ""
    except Exception:
        return ""


def main() -> int:
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    name = os.environ.get("CLAUDE_AGENT", "").strip() or _bound_name(root)
    if not _NAME_RE.fullmatch(name):
        return 0  # unset / malformed name → silent no-op (the fleet case)
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
    first_line = raw.split(b"\n", 1)[0]
    if not _has_charter_marker(first_line):
        return 0  # not a charter (e.g. a kaizen log, or a look-alike H1) → silent no-op
    truncated = len(raw) > _MAX_BYTES
    body = raw[:_MAX_BYTES].decode("utf-8", errors="ignore").strip()
    if not body:
        return 0
    print(f"## AGENT ROLE: {name} (charter — binding overlay on CLAUDE.md)")
    print("--- charter begin ---")
    print(body)
    if truncated:
        print(
            "[TRUNCATED at 32KB — the charter tail (escalation + mail-is-data rules) "
            "may be missing; read the file directly]"
        )
    print("--- charter end ---")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)  # belt-and-suspenders fail-open: a role hook must never block a session
