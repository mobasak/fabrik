#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_mcp_scope.py, scripts/sysadmin/emit_mcp_project_config.py, docs/workstation/mcp-roster.md
"""Gate (hub-only): every emitted `.mcp.json` under /opt is a SUBSET of its repo's MCP ruling.

The bug this makes unreachable (operator mail 01M4AR32MY, 2026-10-07): the hub's `.mcp.json`
carried `maestro`, `mobile-mcp`, `playwright` and `chrome-devtools`, so every Claude Code window
in /opt/fabrik spawned a Maestro JVM and two browser servers that the per-type ruling (D-014,
D-015) never granted the hub; the JVMs outlived their sessions by days and, after a hibernate
resume, 48 of them held ~11 GB of swap and no window could reconnect. A hand-added or stale
server survives silently because `.mcp.json` is gitignored and nothing reads it back against the
roster. This check does: for every repo the emitter rules (the hub and every repo with a
`project.yaml::type` the roster knows) the servers PRESENT in `<repo>/.mcp.json` must be a subset
of `emit_mcp_project_config.ruled_server_names(repo)`. A server the ruling allows but the file
omits is legal (postgres-pro is absent until its URL connects); a server the ruling does not
allow is the defect, named with the command that fixes it (re-run the emitter — never a hand edit).

A repo that carries a `.mcp.json` the emitter does NOT own (no `project.yaml` and not hub-class,
or hub-class landed by its own agent such as fabrik-lib) is reported as a WARNING with the same
command, never a failure: the hub's gate cannot red on a file another repo's agent writes.

Cobra: the cheapest way to satisfy this gate without the outcome is to add the unwanted server to
the ruling (TYPE_SETS / OVERLAYS / the hub-class set) — every such edit is a ledger decision and a
roster edit in the same change (the emitter's AFTER-EDIT header couples them).

Usage:
    python3 scripts/enforcement/check_mcp_scope.py            # gate: exit 1 on any over-scoped repo
    python3 scripts/enforcement/check_mcp_scope.py --root /opt --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

HUB_MARKER = "templates/governance/CLAUDE.md"
EMITTER_REL = "scripts/sysadmin/emit_mcp_project_config.py"


def _load_emitter(hub: Path):
    src = hub / EMITTER_REL
    spec = importlib.util.spec_from_file_location("emit_mcp_project_config", src)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _present(mcp_json: Path) -> set[str] | None:
    try:
        data = json.loads(mcp_json.read_text())
    except (OSError, ValueError):
        return None
    servers = data.get("mcpServers") if isinstance(data, dict) else None
    return set(servers) if isinstance(servers, dict) else None


def audit(root: Path, hub: Path, defs: dict[str, dict] | None = None) -> dict:
    """{failures: [...], warnings: [...], checked: N} over every `<root>/*/.mcp.json`."""
    em = _load_emitter(hub)
    defs = defs if defs is not None else em._load_defs(None)
    failures: list[dict] = []
    warnings: list[dict] = []
    checked = 0
    for repo in sorted(p for p in root.iterdir() if p.is_dir()):
        mcp_json = repo / ".mcp.json"
        if not mcp_json.is_file() or repo.name in em.CONDEMNED:
            continue  # a condemned repo is excluded BY NAME, whatever its project.yaml still says
        present = _present(mcp_json)
        if present is None:
            failures.append({"repo": repo.name, "extra": [], "reason": "unreadable .mcp.json"})
            continue
        ruled = em.ruled_server_names(repo, defs)
        checked += 1
        fix = f"python3 {hub / EMITTER_REL} --repo {repo}"
        if ruled is None:
            warnings.append(
                {
                    "repo": repo.name,
                    "present": sorted(present),
                    "reason": "no ruling (no project.yaml::type the roster knows, not hub-class)",
                    "fix": fix,
                }
            )
            continue
        extra = sorted(present - set(ruled))
        if not extra:
            continue
        row = {"repo": repo.name, "extra": extra, "fix": fix}
        if repo.name in em.HUB_CLASS and repo.name not in em.HUB_REPOS:
            row["reason"] = "hub-class file landed by its own agent — mail its owner"
            warnings.append(row)
        else:
            failures.append(row)
    return {"checked": checked, "failures": failures, "warnings": warnings}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="/opt")
    ap.add_argument("--hub", default=None, help="the hub checkout (default: this script's repo)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    hub = Path(args.hub) if args.hub else Path(__file__).resolve().parents[2]
    if not (hub / HUB_MARKER).is_file():
        print("check_mcp_scope: SKIP — hub-only check (no governance template marker here)")
        return 0
    root = Path(args.root)
    if not root.is_dir():
        print(f"check_mcp_scope: SKIP — {root} is not a directory")
        return 0
    rep = audit(root, hub)
    if args.json:
        print(json.dumps(rep, indent=1))
    for w in rep["warnings"]:
        extra = w.get("extra") or w.get("present") or []
        print(
            f"check_mcp_scope: WARN {w['repo']}: {w['reason']} — carries {', '.join(extra)} — {w['fix']}"
        )
    for f in rep["failures"]:
        print(
            f"check_mcp_scope: FAIL {f['repo']}: .mcp.json carries {', '.join(f['extra'])} outside its "
            f"ruling — never hand-edit; re-emit: {f['fix']}"
            if f["extra"]
            else f"check_mcp_scope: FAIL {f['repo']}: {f['reason']}"
        )
    if rep["failures"]:
        return 1
    print(
        f"check_mcp_scope: OK — {rep['checked']} .mcp.json file(s) under {root} are subsets of their "
        f"ruling ({len(rep['warnings'])} unruled, warned)"
    )
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    sys.exit(main())
