#!/usr/bin/env python3
# AFTER-EDIT: .windsurf/rules/versions.yaml, scripts/sysadmin/rules_currency_watch.py, tests/sysadmin/test_rules_render_versions.py | none
"""Version injection for the rules corpus (D-062 — no version literals in packs).

Packs never hand-carry a version number: each version-bearing spot is a marker
span ``<!--v:KEY-->LITERAL<!--/v-->`` whose LITERAL is owned by
``.windsurf/rules/versions.yaml``. This renderer rewrites every span in place
to the current value — the pack stays a single readable file (agents copy the
example verbatim, builds get a real pin), but the literal's PROVENANCE is the
machine source, so it cannot rot in prose.

Modes:
  (default)  inject current values into every span across .windsurf/rules/**
  --check    exit 1 if any span disagrees with versions.yaml (gate/CI use), and
             WARN on version-shaped literals OUTSIDE any span (the D-062 ban on
             new hand-written literals — advisory, promoted per the rollout law)

The weekly watcher calls inject after refreshing versions.yaml and commits the
result (the docs(auto) cron-commit precedent) — the update loop has no human
step; failure falls back to a mail to infra.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

RULES_ROOT = Path("/opt/fabrik/.windsurf/rules")
VERSIONS_FILE = RULES_ROOT / "versions.yaml"

_SPAN = re.compile(r"(<!--v:([a-z0-9_]+)-->)(.*?)(<!--/v-->)", re.S)
# version-shaped literals that should live in a span, not prose (advisory sweep)
_LOOSE = re.compile(
    r"\b(?:python:\d+\.\d+|node:\d+(?!\d)|FROM python:\d|FROM node:\d"
    # name-version prose ("Python 3.9+", "SQLAlchemy 2.0") — the shapes the docker-tag
    # sweep was blind to (operator re-ask 2026-09-01 exposed 4 in the already-passed
    # file 1; 20 measured corpus-wide). Dotted/plus forms for dotted-version tools;
    # bare majors only for tools whose versions are dotless — "FastAPI 500" (a status
    # code) must never fire.
    r"|(?:Python|SQLAlchemy|FastAPI|TypeScript|pydantic)\s+\d+\.\d+\+?"
    # 'PostgreSQL' spelled correctly (the original 'PostgresQL' alternation never matched
    # the real capital-S spelling — found at file 5, where 5 literals sailed through),
    # plus the PG18 / pgvector:pg16 shapes. \bPG\d{2}\b stays 2-digit so ports never fire.
    r"|(?:Node(?:\.js)?|Debian|Postgre(?:s|SQL)|Redis)\s+\d+(?:\.\d+)?\+?(?![\d-])"
    r"|\bPG\d{2}\b(?!\d)"
    r"|pgvector:pg\d+"
    r")"
)


def load_versions(path: Path = VERSIONS_FILE) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): str(v) for k, v in (data.get("versions") or {}).items()}


def inject_text(text: str, versions: dict[str, str]) -> tuple[str, int, list[str]]:
    """(new_text, spans_rewritten, unknown_keys)."""
    unknown: list[str] = []
    count = 0

    def sub(m: re.Match[str]) -> str:
        nonlocal count
        key = m.group(2)
        if key not in versions:
            unknown.append(key)
            return m.group(0)
        new = f"{m.group(1)}{versions[key]}{m.group(4)}"
        if new != m.group(0):
            count += 1
        return new

    return _SPAN.sub(sub, text), count, unknown


def run(check: bool) -> int:
    versions = load_versions()
    rc = 0
    changed_files: list[str] = []
    for f in sorted(RULES_ROOT.rglob("*.md")):
        text = f.read_text(encoding="utf-8", errors="replace")
        new, n, unknown = inject_text(text, versions)
        for k in unknown:
            print(f"ERROR: {f}: span key '{k}' missing from versions.yaml")
            rc = 1
        # spans must sit inside a file that the loose sweep then ignores:
        # strip spans BEFORE sweeping so only unmarked literals fire
        stripped = _SPAN.sub("", new)
        for m in _LOOSE.finditer(stripped):
            print(f"⚠ {f}: version-shaped literal outside a marker span: '{m.group(0)}' (D-062 — wrap as <!--v:key-->…<!--/v--> or move to versions.yaml)")
        if new != text:
            if check:
                print(f"ERROR: {f}: {n} span(s) disagree with versions.yaml — run rules_render_versions.py")
                rc = 1
            else:
                f.write_text(new, encoding="utf-8")
                changed_files.append(str(f))
    if changed_files:
        print(f"injected: {len(changed_files)} file(s) updated")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    return run(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
