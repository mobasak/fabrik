#!/usr/bin/env python3
"""epic_order.py — deterministic epic integrity + phased-ordering over the epic
artifacts written by mega-epic-breakdown/03-expand-epic-files-fabrik.

This is the CODE that replaces 05-dispatch's two prose jobs (north-star R8/D4:
control flow in code, not prose):
  1. Ticket-set integrity  (was 05 Step 1)  -> --check
  2. Phased execution order (was 05 Step 2)  -> default / --json

Reads docs/development/epics/*.md frontmatter (see EPIC-ARTIFACT-SCHEMA.md):
  epic_n, slug, title, depends_on[], parallel_with[], owned_paths[], status.

Pure stdlib. Project-agnostic: operates on --epics-dir under the current repo.

Exit codes: 0 = ok; 1 = integrity failure; 2 = usage/parse error.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

MIGRATION_GLOBS = ("alembic/versions/**", "db/schema.sql")


def _parse_frontmatter(text: str) -> dict | None:
    """Minimal flat-YAML frontmatter parser (scalars + inline [a, b] lists).
    Avoids a PyYAML dependency — the schema is intentionally flat."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    body = text[3:end].strip("\n")
    fm: dict = {}
    for line in body.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            items = [x.strip().strip("\"'") for x in inner.split(",")] if inner else []
            fm[key] = [x for x in items if x != ""]
        else:
            fm[key] = val.strip("\"'")
    return fm


def load_epics(epics_dir: str) -> list[dict]:
    epics = []
    for path in sorted(glob.glob(os.path.join(epics_dir, "*.md"))):
        with open(path, encoding="utf-8") as fh:
            fm = _parse_frontmatter(fh.read())
        if fm is None:
            epics.append({"_path": path, "_no_frontmatter": True})
            continue
        def _ints(v):
            out = []
            for x in v if isinstance(v, list) else [v]:
                m = re.search(r"\d+", str(x))
                if m:
                    out.append(int(m.group()))
            return out
        epics.append({
            "_path": path,
            "epic_n": int(re.search(r"\d+", str(fm.get("epic_n", ""))).group())
                      if re.search(r"\d+", str(fm.get("epic_n", ""))) else None,
            "slug": fm.get("slug", ""),
            "title": fm.get("title", ""),
            "status": fm.get("status", "0"),
            "depends_on": _ints(fm.get("depends_on", [])),
            "parallel_with": _ints(fm.get("parallel_with", [])),
            "owned_paths": fm.get("owned_paths", []) if isinstance(fm.get("owned_paths", []), list)
                           else [fm.get("owned_paths")],
        })
    return epics


def check_integrity(epics: list[dict], expected_count: int | None) -> list[str]:
    """Returns a list of finding strings; empty == PASS. (Was 05 Step 1.)"""
    findings: list[str] = []
    for e in epics:
        if e.get("_no_frontmatter"):
            findings.append(f"{e['_path']}: no frontmatter — cannot map to a graph node "
                            f"(03 must emit the epic-artifact schema).")
    good = [e for e in epics if not e.get("_no_frontmatter")]
    for e in good:
        if e["epic_n"] is None:
            findings.append(f"{e['_path']}: missing/invalid epic_n.")
        if not re.match(r"^Epic \d+ — .+", e["title"]):
            findings.append(f"{e['_path']}: title {e['title']!r} != 'Epic N — [Name]'.")
    nums = sorted(e["epic_n"] for e in good if e["epic_n"] is not None)
    if expected_count is not None and len(good) != expected_count:
        findings.append(f"count mismatch: {len(good)} epic files vs {expected_count} "
                        f"expected from 02's proposal (deficit or orphan).")
    dups = sorted({n for n in nums if nums.count(n) > 1})
    if dups:
        findings.append(f"duplicate epic numbers: {dups} (stale/redundant copy).")
    if nums:
        expect = list(range(1, max(nums) + 1))
        gaps = sorted(set(expect) - set(nums))
        if gaps:
            findings.append(f"non-contiguous epic numbers: missing {gaps} (deficit or mis-number).")
    # parallel disjointness + single-migration-owner (was 02 gate 2/3 + 3/3; re-proved here)
    by_n = {e["epic_n"]: e for e in good if e["epic_n"] is not None}
    for e in good:
        for other_n in e["parallel_with"]:
            o = by_n.get(other_n)
            if not o:
                continue
            shared = set(e["owned_paths"]) & set(o["owned_paths"])
            if shared:
                findings.append(f"parallel epics {e['epic_n']} & {other_n} share owned_paths "
                                f"{sorted(shared)} — concurrency-unsafe.")
            e_mig = any(g in MIGRATION_GLOBS for g in e["owned_paths"])
            o_mig = any(g in MIGRATION_GLOBS for g in o["owned_paths"])
            if e_mig and o_mig:
                findings.append(f"parallel epics {e['epic_n']} & {other_n} both own migrations "
                                f"— at most one may.")
    return findings


def phased_order(epics: list[dict]) -> list[list[int]]:
    """Kahn topological sort into phases (was 05 Step 2). Epics in the same
    phase have no mutual dependency (rendered ⚡ / dispatchable together)."""
    good = [e for e in epics if not e.get("_no_frontmatter") and e["epic_n"] is not None]
    deps = {e["epic_n"]: set(e["depends_on"]) for e in good}
    placed: set[int] = set()
    phases: list[list[int]] = []
    remaining = set(deps)
    while remaining:
        ready = sorted(n for n in remaining if deps[n] <= placed)
        if not ready:  # cycle
            raise ValueError(f"dependency cycle among epics {sorted(remaining)}")
        phases.append(ready)
        placed |= set(ready)
        remaining -= set(ready)
    return phases


def render_phases(epics: list[dict], phases: list[list[int]]) -> str:
    by_n = {e["epic_n"]: e for e in epics if not e.get("_no_frontmatter")}
    lines = []
    for i, phase in enumerate(phases, 1):
        names = " ⚡ ".join(f"Epic {n} — {by_n[n]['slug']}" for n in phase)
        when = "root — no upstream dependencies" if i == 1 else f"after Phase {i-1} completes"
        lines.append(f"Phase {i} ({when}): {names}")
    return "\n".join(lines) if lines else "(no epics found)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epics-dir", default="docs/development/epics")
    ap.add_argument("--expected-count", type=int, default=None,
                    help="epic count from 02's proposal (enables the count-match check)")
    ap.add_argument("--check", action="store_true", help="integrity only; exit 1 on any finding")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.epics_dir):
        print(f"epic_order: no such dir: {args.epics_dir}", file=sys.stderr)
        return 2
    epics = load_epics(args.epics_dir)
    findings = check_integrity(epics, args.expected_count)

    if args.check:
        if args.json:
            print(json.dumps({"ok": not findings, "findings": findings}, indent=2))
        else:
            print("INTEGRITY: PASS" if not findings else "INTEGRITY: FAIL")
            for f in findings:
                print(f"  - {f}")
        return 1 if findings else 0

    phases = phased_order(epics) if not findings else []
    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings, "phases": phases}, indent=2))
    else:
        if findings:
            print("INTEGRITY: FAIL (fix before ordering)")
            for f in findings:
                print(f"  - {f}")
            return 1
        print(render_phases(epics, phases))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
