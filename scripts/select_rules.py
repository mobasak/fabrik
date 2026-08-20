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
import contextlib
import fnmatch
import functools
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Kaizen M1 sensor (T04) — OBSERVATION ONLY. Additive, idempotent path append + a
# defensive import: this file is fleet-synced, and a project that never receives the
# box-local module must behave exactly as before (byte-compared in the T04 tests).
_KAIZEN_DIR = str(Path(__file__).resolve().parent / "sysadmin")
if _KAIZEN_DIR not in sys.path:
    sys.path.append(_KAIZEN_DIR)
try:
    import kaizen_events  # noqa: E402
except Exception:  # pragma: no cover - absence is the normal case in a project
    kaizen_events = None  # type: ignore[assignment]

# This script had no stderr channel before T04: the emitter's `_warn` (its only failure
# channel) must not become one. Muted at the call site only — every other caller of
# `kaizen_events` keeps the honest warning. `2.0` bounds exposure()'s git probes; the
# sensor fires after the packs are resolved, so `unknown` beats a hung git probe.
_KAIZEN_PROBE_TIMEOUT_S = 2.0

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
    ".tmp",  # subagent worktrees (full repo copies under .tmp/subagents/) — traversing them
    #          made rglob effectively HANG at the hub (~80 tree copies; proven live 2026-07-18)
}


def _expand_braces(pat: str) -> list[str]:
    """Expand a single `{a,b,c}` group (pathlib globs don't support brace expansion)."""
    m = re.search(r"\{([^}]*)\}", pat)
    if not m:
        return [pat]
    pre, post = pat[: m.start()], pat[m.end() :]
    return [pre + opt.strip() + post for opt in m.group(1).split(",") if opt.strip()]


@functools.lru_cache(maxsize=4)
def _tree_paths(root: Path) -> tuple[str, ...]:
    """Every file AND directory path under root (relative, posix), with `_EXCLUDE` dirs pruned
    DURING the walk. One pruned walk replaces per-glob `rglob` traversals: `rglob` cannot prune,
    so it re-walked the ENTIRE tree (incl. `.tmp/subagents/` worktree copies — ~80 full repo
    trees at the hub) once per glob per pack, which effectively hung the script (proven live
    2026-07-18: repeated 2-minute timeouts at `/opt/fabrik`)."""
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE]
        rel = os.path.relpath(dirpath, root)
        base = "" if rel == "." else rel.replace(os.sep, "/") + "/"
        out.extend(base + d for d in dirnames)
        out.extend(base + f for f in filenames)
    return tuple(out)


def _tail_matches(relpath: str, pat: str) -> bool:
    """rglob-equivalent match: do the TRAILING segments of relpath match pat segment-wise?
    (`root.rglob("a/b.py")` hits any path whose last two components match `a`/`b.py`.)"""
    psegs = [p for p in pat.replace("**/", "").replace("**", "*").split("/") if p]
    rsegs = relpath.split("/")
    if not psegs or len(psegs) > len(rsegs):
        return False
    return all(fnmatch.fnmatch(r, p) for r, p in zip(rsegs[-len(psegs) :], psegs, strict=True))


def _glob_has_match(root: Path, glob: str) -> bool:
    """Best-effort: does an existing file in the project's OWN source match this glob?"""
    pat = glob.strip().lstrip("/")
    if pat.startswith("**/"):
        pat = pat[3:]
    if pat.endswith("/**"):  # directory glob, e.g. **/uploads/**
        pat = pat[:-3]
    if not pat:
        return False
    try:
        paths = _tree_paths(root)
    except OSError:
        return False
    return any(_tail_matches(rel, expanded) for expanded in _expand_braces(pat) for rel in paths)


def _project_type(root: Path) -> str:
    py = root / "project.yaml"
    if not py.exists():
        return ""
    m = re.search(r"^type:\s*(\S+)", py.read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else ""


def collect(root: Path) -> dict[str, Any]:
    rules_dir = root / ".windsurf" / "rules"
    active: list[dict[str, Any]] = []
    available: list[dict[str, Any]] = []
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
    root = args.project_root.resolve()
    data = collect(root)

    # Kaizen sensor (T04) — OBSERVATION ONLY: which packs this INVOCATION activated, and
    # the glob that fired each (collect() short-circuits on the first hit, so the fired
    # set is recomputed here — off the cached tree walk — rather than by changing it).
    # Honest label: invocation-time, NOT per-edit; per-edit needs a PostToolUse surface (M2).
    if kaizen_events:
        _packs = [
            {"pack": e["pack"], "globs_fired": [g for g in e["globs"] if _glob_has_match(root, g)]}
            for e in data["active"]
        ]
        with contextlib.redirect_stderr(io.StringIO()):  # the sensor owns no stderr here
            kaizen_events.emit(
                "rule_activation",
                kind="select_rules",
                label="invocation-time",
                packs=_packs,
                probe_timeout_s=_KAIZEN_PROBE_TIMEOUT_S,
            )

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
