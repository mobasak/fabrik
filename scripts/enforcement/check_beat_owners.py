#!/usr/bin/env python3
# AFTER-EDIT: docs/workflows/FINAL_GATE_WORKFLOW.md, docs/reference/fabrik-mail.md
"""Validate the hub's mail ownership map, ``.fabrik/beat-owners.json``.

Spec: docs/superpowers/specs/2026-10-13-mail-routing-design.md § The delta D2.

The map is read by every sender's synced ``scripts/mail.py``, so a broken map routes
mail wrongly box-wide. Refused (exit 1), one line per defect:

- an owner outside ``mail.HUB_BEATS``;
- a rule missing ``owner`` or ``source``;
- a malformed pattern (``mail._glob_re`` cannot compile it, it climbs out with ``..``, or it
  is only slashes);
- a catch-all owner — one beat whose rules TOGETHER match every tracked file, however they
  are spelled or split (``**``, ``*``, ``["/*", "*/**"]`` in one rule or across two rules of
  the same owner …), judged by the effect on ``git ls-files``, never by the text;
- a dead pattern (it matches no tracked file — ``git ls-files``);
- a rule fully shadowed: every tracked file it matches is also matched by a LATER rule
  with a different owner, so with last-match-wins it never decides anything;
- an unknown or non-boolean switch.

Reported, never a failure: the tracked paths no rule owns, with the count and its
denominator (``unowned: N of M tracked``). Self-skips at exit 0 where the map does not
exist — every project repo this check is synced to.

⚠️ COBRA (D-253): the cheapest way to green the unowned report is a catch-all rule, which
owns everything for ONE beat and routes nothing usefully — so one owner matching every
tracked file is refused, however its rules are split. Rules of DIFFERENT owners that between
them own every file are a complete map, which is the goal, and stay legal. What this check cannot see is a rule owning all files BUT one, which
it cannot tell from an honest broad rule; a reviewer of a map change reads the rules, not the
count.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path


def _mail():
    src = Path(__file__).resolve().parents[1] / "mail.py"
    spec = importlib.util.spec_from_file_location("_beat_owners_mail", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tracked(root: Path) -> list[str] | None:
    """Tracked paths, each once, or None when git cannot answer (missing, timed out, not a repo) — the
    dead-pattern and shadow checks cannot run then, which is a defect, never a pass."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            text=True,
            errors="surrogateescape",  # a non-UTF-8 filename stays a path, never a crash
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    # one entry per PATH: an unmerged path is listed once per index stage, which would inflate
    # every count compared against this list (the denominator and the catch-all test)
    return sorted({p for p in out.stdout.split("\0") if p})


def check(root: Path) -> tuple[list[str], str]:
    """(defects, report line) for the map under ``root``."""
    mail = _mail()
    path = root / ".fabrik" / "beat-owners.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"unreadable map: {exc}"], ""
    if not isinstance(data, dict) or type(data.get("version")) is not int:
        return ['map needs an integer "version"'], ""
    defects: list[str] = []
    switches = data.get("switches", {})
    if not isinstance(switches, dict):
        defects.append('"switches" is not an object')
        switches = {}
    for name, value in switches.items():
        if name not in mail.MAP_SWITCHES:
            defects.append(f"unknown switch {name!r} (known: {', '.join(mail.MAP_SWITCHES)})")
        elif not isinstance(value, bool):
            defects.append(f"switch {name!r} is not true/false")
    rules = data.get("rules")
    if not isinstance(rules, list):
        return [*defects, '"rules" is not a list'], ""
    files = _tracked(root)
    if files is None:
        return [*defects, "git ls-files failed — dead and shadowed rules cannot be checked"], ""
    matched: list[set[str]] = []
    for i, rule in enumerate(rules, 1):
        hits: set[str] = set()
        matched.append(hits)
        if not isinstance(rule, dict):
            defects.append(f"rule {i}: not an object")
            continue
        owner = rule.get("owner")
        if not owner:
            defects.append(f"rule {i}: missing owner")
        elif not isinstance(owner, str):
            defects.append(f"rule {i}: owner must be one beat name, not {type(owner).__name__}")
        elif owner not in mail.HUB_BEATS:
            defects.append(
                f"rule {i}: unknown owner {owner!r} (hub beats: {', '.join(mail.HUB_BEATS)})"
            )
        if not str(rule.get("source") or "").strip():
            defects.append(f"rule {i}: missing source (a D-id or a charter line)")
        for key in ("paths", "topics"):
            value = rule.get(key)
            if value is not None and (
                not isinstance(value, list) or not all(isinstance(v, str) and v for v in value)
            ):
                defects.append(f"rule {i}: malformed {key} — a list of non-empty strings")
        paths = rule.get("paths") if isinstance(rule.get("paths"), list) else ()
        for pattern in paths:
            if not isinstance(pattern, str) or not pattern.strip("/") or ".." in pattern.split("/"):
                defects.append(f"rule {i}: malformed pattern {pattern!r}")
                continue
            try:
                mail._glob_re(pattern)
            except re.error as exc:
                defects.append(f"rule {i}: malformed pattern {pattern!r} ({exc})")
                continue
            got = {f for f in files if mail._pattern_matches(pattern, f)}
            if not got:
                defects.append(f"rule {i}: dead pattern {pattern!r} matches no tracked file")
            hits |= got
    for i, hits in enumerate(matched):
        if not hits:
            continue
        owner = rules[i].get("owner") if isinstance(rules[i], dict) else None
        later = set().union(
            *(
                matched[j]
                for j in range(i + 1, len(rules))
                if isinstance(rules[j], dict) and rules[j].get("owner") != owner
            )
        )
        if hits <= later:
            defects.append(
                f"rule {i + 1}: shadowed — every file it matches is owned by a later rule"
            )
    by_owner: dict[str, set[str]] = {}
    for rule, hits in zip(rules, matched, strict=True):
        if isinstance(rule, dict) and isinstance(rule.get("owner"), str):
            by_owner.setdefault(rule["owner"], set()).update(hits)
    for owner, hits in sorted(by_owner.items()):
        if len(files) > 1 and len(hits) == len(files):
            defects.append(f"catch-all owner {owner!r} — its rules match every tracked file")
    owned = set().union(*matched) if matched else set()
    unowned = [f for f in files if f not in owned]
    report = f"unowned: {len(unowned)} of {len(files)} tracked"
    return defects, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".", help="the repo holding .fabrik/beat-owners.json")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not (root / ".fabrik" / "beat-owners.json").is_file():
        print("check_beat_owners: no .fabrik/beat-owners.json here — skipped (not the hub)")
        return 0
    defects, report = check(root)
    for d in defects:
        print(f"✗ {d}")
    if report:
        print(f"check_beat_owners: {report}")
    if defects:
        print(f"check_beat_owners: {len(defects)} defect(s) in .fabrik/beat-owners.json")
        return 1
    print("check_beat_owners: map OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
