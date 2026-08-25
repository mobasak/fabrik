#!/usr/bin/env python3
# AFTER-EDIT: scripts/rules_match.py scripts/review_rubric.py tests/test_select_rules.py
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
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import rules_match  # noqa: E402 - the shared glob-pack matcher (any_path_matches, packs_for_paths)

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
            if any(rules_match.any_path_matches(root, g, empty_matches_all=False) for g in globs):
                active.append(entry)
            else:
                available.append(entry)
    return {"type": _project_type(root), "active": active, "available": available}


def main() -> int:
    ap = argparse.ArgumentParser(description="List applicable .windsurf/rules packs for planning.")
    ap.add_argument("--project-root", type=Path, default=Path.cwd())
    ap.add_argument("--json", action="store_true")
    ap.add_argument(
        "--changed",
        nargs="+",
        help=(
            "plan-stage routing: instead of the whole-project ACTIVE/AVAILABLE split, print "
            "only the packs whose glob matches one of these changed paths (routes through "
            "rules_match.packs_for_paths — the same GLOB question review_rubric.py --changed asks "
            "at review time)."
        ),
    )
    args = ap.parse_args()
    root = args.project_root.resolve()

    if args.changed:
        packs = rules_match.packs_for_paths(args.changed, root)
        if args.json:
            print(json.dumps({"changed": args.changed, "packs": packs}, indent=2))
        else:
            print(f"Packs matching {len(args.changed)} changed path(s) ({len(packs)}):")
            for p in packs:
                print(f"  • {p}")
        return 0

    data = collect(root)

    # Kaizen sensor (T04) — OBSERVATION ONLY: which packs this INVOCATION activated, and
    # the glob that fired each (collect() short-circuits on the first hit, so the fired
    # set is recomputed here — off the cached tree walk — rather than by changing it).
    # Honest label: invocation-time, NOT per-edit; per-edit needs a PostToolUse surface (M2).
    if kaizen_events:
        _packs = [
            {
                "pack": e["pack"],
                "globs_fired": [
                    g
                    for g in e["globs"]
                    if rules_match.any_path_matches(root, g, empty_matches_all=False)
                ],
            }
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
