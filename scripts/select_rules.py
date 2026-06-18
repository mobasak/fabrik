#!/usr/bin/env python3
"""Select the .windsurf/rules packs applicable to this project — run BEFORE planning.

Glob-activation only fires once you *touch* a matching file, so at plan time an agent
must proactively choose its rules. This prints, from each pack's own frontmatter
(`globs` + `description`):

  ACTIVE    — a glob matches a file that already exists here → read it in full now.
  AVAILABLE — read it if your planned work will touch that domain (the description says when).

Selection is by each pack's own frontmatter (globs + description); also prints
project.yaml::type for context. Usage: python scripts/select_rules.py [--project-root DIR] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_FM = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_GLOBS = re.compile(r"^globs:\s*\[(.*?)\]", re.MULTILINE | re.DOTALL)
_DESC = re.compile(r"^description:\s*(.+)$", re.MULTILINE)


def _parse_frontmatter(text: str) -> tuple[list[str], str]:
    m = _FM.search(text)
    fm = m.group(1) if m else ""
    globs: list[str] = []
    gm = _GLOBS.search(fm)
    if gm:
        # Extract each QUOTED glob — don't split on ",", since brace globs like
        # "**/main.{js,ts,mjs,cjs}" contain commas inside the braces.
        globs = re.findall(r"[\"']([^\"']+)[\"']", gm.group(1))
    dm = _DESC.search(fm)
    return globs, (dm.group(1).strip() if dm else "")


# Noise dirs excluded from glob matching — they're deps or bundled reference copies,
# not the project's OWN source (e.g. templates/saas-skeleton ships .tsx, which would
# otherwise false-flag the TS/Node/Chrome packs as ACTIVE in a pure-Python project).
_EXCLUDE = {
    "node_modules",
    ".venv",
    "venv",  # non-dotted virtualenv (bundles deps like playwright's electron/ — false-flags packs)
    ".git",
    "templates",
    "dist",
    "build",
    "__pycache__",
    ".next",
    ".expo",
    "output",
    "backups",
    ".droid",
    "docs-site",
}


def _expand_braces(pat: str) -> list[str]:
    """Expand a single `{a,b,c}` group (pathlib globs don't support brace expansion)."""
    m = re.search(r"\{([^}]*)\}", pat)
    if not m:
        return [pat]
    pre, post = pat[: m.start()], pat[m.end() :]
    return [pre + opt.strip() + post for opt in m.group(1).split(",") if opt.strip()]


def _glob_has_match(root: Path, glob: str) -> bool:
    """Best-effort: does an existing file in the project's OWN source match this glob?"""
    pat = glob.strip().lstrip("/")
    if pat.startswith("**/"):
        pat = pat[3:]
    if pat.endswith("/**"):  # directory glob, e.g. **/uploads/**
        pat = pat[:-3]
    if not pat:
        return False
    for expanded in _expand_braces(pat):
        try:
            for hit in root.rglob(expanded):
                if not (set(hit.relative_to(root).parts) & _EXCLUDE):
                    return True
        except (ValueError, OSError):
            continue
    return False


def _project_type(root: Path) -> str:
    py = root / "project.yaml"
    if not py.exists():
        return ""
    m = re.search(r"^type:\s*(\S+)", py.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else ""


def collect(root: Path) -> dict:
    rules_dir = root / ".windsurf" / "rules"
    active: list[dict] = []
    available: list[dict] = []
    if rules_dir.exists():
        for pack in sorted(rules_dir.rglob("*.md")):
            globs, desc = _parse_frontmatter(pack.read_text(encoding="utf-8", errors="replace"))
            rel = pack.relative_to(rules_dir).as_posix()
            entry = {"pack": rel, "description": desc, "globs": globs}
            if any(_glob_has_match(root, g) for g in globs):
                active.append(entry)
            else:
                available.append(entry)
    return {"type": _project_type(root), "active": active, "available": available}


def main() -> int:
    ap = argparse.ArgumentParser(description="List applicable .windsurf/rules packs for planning.")
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    data = collect(args.project_root.resolve())

    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    print(f"Project type: {data['type'] or '(unknown)'}")
    print(f"\nACTIVE — read these in full now ({len(data['active'])}):")
    for e in data["active"]:
        print(f"  • {e['pack']} — {e['description']}")
    print(f"\nAVAILABLE — read if your planned work touches the domain ({len(data['available'])}):")
    for e in data["available"]:
        print(f"  • {e['pack']} — {e['description']}")
    print("\nGround every plan step / code change in the applicable packs above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
