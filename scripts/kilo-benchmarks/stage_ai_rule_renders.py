#!/usr/bin/env python3
# AFTER-EDIT: autocommit_pipeline_outputs.sh (consumes --list) | tests/test_stage_ai_rule_renders.py
"""Marker-scoped stage-list feeder for the ai-model-catalog engine's rule-pack renders.

The Phase-D cutover (2026-08-15) moved block injection for ``.windsurf/rules/ai/**`` to the
ai-model-catalog engine and removed the packs from the pipeline autocommit stage list — for the
right reason (whole-file staging can bundle a SIBLING's hand-edit into an auto-pushed fleet-synced
commit) — but left the engine publishing renders nothing commits: the dirty packs then red every
concurrent session's diff-scoped gates (routed to intel 2026-08-29, 01M17CKG).

This helper restores the COMMIT HALF safely: a pack qualifies for staging ONLY when its ENTIRE
worktree-vs-HEAD diff lies inside the engine's write surface —

  * lines within ``<!-- NAME:START ... -->`` … ``<!-- NAME:END -->`` regions (inclusive; the
    START line itself carries the refresh date), or
  * the ``Last content verification: YYYY-MM-DD`` header line.

ANY changed line outside that surface disqualifies the file LOUDLY (stderr) — a sibling's
hand-edit is never bundled; they commit their own work. ``--list`` prints qualifying repo-relative
paths (one per line) for the autocommit script to append to its stage array. Always exits 0
(pipeline contract: a helper hiccup must never abort the refresh).
"""

from __future__ import annotations

import difflib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("/opt/fabrik")
GLOB = ".windsurf/rules/ai/*.md"
# START qualifies ONLY with the engine's own self-description — every live engine marker
# carries "(auto-managed by <script>)" on its START line; a human's START-shaped comment
# must never open an allowed region (false-qualify auto-publishes fleet-wide).
_MARKER_START = re.compile(r"<!--\s*[A-Z_0-9]+:START\b.*auto-managed by")
_MARKER_END = re.compile(r"<!--\s*[A-Z_0-9]+:END\s*-->")
_DATE_LINE = re.compile(r"^Last content verification: \d{4}-\d{2}-\d{2}\s*$")


def allowed_lines(lines: list[str]) -> set[int]:
    """0-based indices of lines the ENGINE owns (marker regions inclusive + the date line)."""
    allowed: set[int] = set()
    depth = 0
    for i, line in enumerate(lines):
        if _MARKER_START.search(line):
            depth += 1
            allowed.add(i)
            continue
        if _MARKER_END.search(line):
            # an END closes (and belongs to) an engine region ONLY if one is open — a stray
            # END inserted in prose is a hand-edit, not an engine line
            if depth > 0:
                allowed.add(i)
                depth -= 1
            continue
        if depth > 0 or _DATE_LINE.match(line):
            allowed.add(i)
    return allowed


def diff_is_engine_only(old: str, new: str) -> tuple[bool, str]:
    """(qualifies, first_offending_line). Every changed line on BOTH sides must be allowed."""
    old_lines, new_lines = old.splitlines(), new.splitlines()
    ok_old, ok_new = allowed_lines(old_lines), allowed_lines(new_lines)
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        for i in range(i1, i2):
            if i not in ok_old:
                return False, old_lines[i]
        for j in range(j1, j2):
            if j not in ok_new:
                return False, new_lines[j]
    return True, ""


def qualifying_paths(repo: Path = REPO) -> list[str]:
    out: list[str] = []
    try:
        dirty = subprocess.run(
            ["git", "-C", str(repo), "diff", "--name-only", "--", GLOB],
            capture_output=True, text=True, timeout=30,
        ).stdout.split()
    except Exception as exc:
        print(f"[stage-ai-renders] git diff failed: {exc}", file=sys.stderr)
        return []
    for rel in dirty:
        try:
            old = subprocess.run(
                ["git", "-C", str(repo), "show", f"HEAD:{rel}"],
                capture_output=True, text=True, timeout=30,
            ).stdout
            new = (repo / rel).read_text(encoding="utf-8")
        except Exception as exc:
            print(f"[stage-ai-renders] SKIP {rel}: unreadable ({exc})", file=sys.stderr)
            continue
        if old == new:
            # mode-only/metadata dirt — content identical; staging would auto-commit a chmod
            print(f"[stage-ai-renders] SKIP {rel}: content identical (mode-only change?)", file=sys.stderr)
            continue
        ok, offender = diff_is_engine_only(old, new)
        if ok:
            out.append(rel)
        else:
            print(
                f"[stage-ai-renders] SKIP {rel}: change outside the engine's write surface "
                f"(a sibling's hand-edit? first offending line: {offender[:100]!r})",
                file=sys.stderr,
            )
    return out


if __name__ == "__main__":
    for p in qualifying_paths():
        print(p)
    raise SystemExit(0)
