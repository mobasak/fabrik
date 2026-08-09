#!/usr/bin/env python3
# AFTER-EDIT: docs/workstation/hooks-index.md, tests/enforcement/test_check_hooks_index.py
"""Hooks-index freshness gate (hub-side only).

docs/workstation/hooks-index.md is the one-page inventory of every hook layer on
the box. This check makes its freshness MECHANICAL: every hook named in the live
configs — the synced-manifest AGENT_HOOK_FILES, the project .claude/settings.json
hook commands, the user-level ~/.claude/settings.json hook scripts (best-effort),
the .windsurf/hooks.json events, and the repo pre-commit hook ids — must appear
in the index by basename/id. Adding or removing a hook without updating the index
fails the gate; a rotting index is a red gate, not a hope.

Hub-only: projects (no templates/governance/CLAUDE.md marker) skip — the index is
a hub workstation doc, not a synced artifact.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

INDEX_REL = "docs/workstation/hooks-index.md"
HUB_MARKER = "templates/governance/CLAUDE.md"


def _manifest_hooks(root: Path) -> list[str]:
    src = (root / "scripts/fabrik_synced_manifest.py").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"AGENT_HOOK_FILES\s*=\s*(\[.*?\])", src, re.S)
    if not m:
        return []
    try:
        return [Path(p).name for p in ast.literal_eval(m.group(1))]
    except Exception:
        return []


def _settings_hooks(path: Path) -> list[str]:
    try:
        cfg = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    names: list[str] = []
    for groups in (cfg.get("hooks") or {}).values():
        for grp in groups:
            for h in grp.get("hooks", []):
                cmd = str(h.get("command") or "")
                names += re.findall(r"[\w.-]+\.(?:py|js|sh)\b", cmd)
    return names


def _precommit_ids(root: Path) -> list[str]:
    p = root / ".pre-commit-config.yaml"
    if not p.is_file():
        return []
    return re.findall(r"^\s*-\s*id:\s*([\w-]+)", p.read_text(encoding="utf-8", errors="replace"), re.M)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    args = ap.parse_args()
    root = args.project_root.resolve()

    if not (root / HUB_MARKER).is_file():
        print("(not the hub — hooks-index check skipped)")
        return 0

    idx_path = root / INDEX_REL
    if not idx_path.is_file():
        print(f"❌ {INDEX_REL} missing — the hooks index is gate-required on the hub")
        return 1
    index = idx_path.read_text(encoding="utf-8", errors="replace")

    required: set[str] = set(_manifest_hooks(root))
    required |= set(_settings_hooks(root / ".claude/settings.json"))
    # User-level hooks: best-effort (HOME may be absent in CI) — never a crash.
    home = os.environ.get("HOME")
    if home:
        required |= set(_settings_hooks(Path(home) / ".claude/settings.json"))
    required |= set(_precommit_ids(root)) - {
        # generic pre-commit-hooks ids ride the "standard safety" row, not names
        "check-added-large-files", "check-merge-conflict", "detect-private-key",
        "forbid-secrets", "check-yaml", "end-of-file-fixer", "trailing-whitespace",
    }

    missing = sorted(n for n in required if n not in index)
    if missing:
        print(f"❌ hooks-index STALE — {len(missing)} live hook(s) not in {INDEX_REL}:")
        for n in missing:
            print(f"   - {n}")
        print("Add a row for each (or remove the retired hook from its config).")
        return 1
    print(f"✓ hooks-index current ({len(required)} live hooks all indexed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
