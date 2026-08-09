#!/usr/bin/env python3
# AFTER-EDIT: tests/test_release_cut.py, commands/_sources/fabrik-release.md
"""Cut a release: graduate CHANGELOG's [Unreleased] into a semver section,
commit, tag, and (unless suppressed) push + create the GitHub Release.

Bump law (derived from the entries being graduated):
  - any entry title containing "BREAKING"      -> major
  - else any "### Added" entry                 -> minor
  - else ("### Fixed"/"### Changed"/other)     -> patch
Current version = highest existing v* tag (semver sort); no tags -> 0.0.0.
Empty [Unreleased] -> exit 1 (nothing to release — never cut a hollow version).

Invoked by /fabrik-release at its READY verdict (dry-run shown in the report,
--execute on the cut). Works in any repo with a Keep-a-Changelog CHANGELOG.md.

Usage:
  release_cut.py --dry-run                 # show version plan, change nothing
  release_cut.py --execute                 # graduate + commit + tag + push + gh release
  release_cut.py --execute --no-push --no-gh-release   # local-only (tests)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

UNRELEASED_RE = re.compile(r"^## \[Unreleased\]\s*$", re.M)
SECTION_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.M)
ENTRY_RE = re.compile(r"^### (Added|Changed|Fixed|Removed|Deprecated|Security)\b(.*)$", re.M)
TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def _git(*args: str, cwd: Path) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def _current_version(cwd: Path) -> tuple[int, int, int]:
    out = subprocess.run(
        ["git", "tag", "--list", "v*"], cwd=cwd, capture_output=True, text=True, timeout=30
    ).stdout
    best = (0, 0, 0)
    for line in out.splitlines():
        m = TAG_RE.match(line.strip())
        if m:
            best = max(best, tuple(int(x) for x in m.groups()))  # type: ignore[assignment]
    return best


def _unreleased_body(text: str) -> str | None:
    m = UNRELEASED_RE.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = SECTION_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _bump(entries: list[tuple[str, str]]) -> str:
    if any("BREAKING" in title.upper() for _kind, title in entries):
        return "major"
    if any(kind == "Added" for kind, _title in entries):
        return "minor"
    return "patch"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--execute", action="store_true")
    ap.add_argument("--no-push", action="store_true", help="skip git push (tests/offline)")
    ap.add_argument("--no-gh-release", action="store_true", help="skip gh release create")
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    args = ap.parse_args()
    cwd = args.repo.resolve()

    cl_path = cwd / "CHANGELOG.md"
    if not cl_path.is_file():
        print("no CHANGELOG.md here")
        return 1
    text = cl_path.read_text(encoding="utf-8")
    body = _unreleased_body(text)
    if body is None:
        print("no [Unreleased] section")
        return 1
    entries = [(m.group(1), m.group(2)) for m in ENTRY_RE.finditer(body)]
    if not entries:
        print("nothing to release — [Unreleased] is empty")
        return 1

    cur = _current_version(cwd)
    bump = _bump(entries)
    nxt = {
        "major": (cur[0] + 1, 0, 0),
        "minor": (cur[0], cur[1] + 1, 0),
        "patch": (cur[0], cur[1], cur[2] + 1),
    }[bump]
    version = ".".join(map(str, nxt))
    today = date.today().isoformat()
    print(
        f"release plan: v{'.'.join(map(str, cur))} -> v{version} ({bump}; "
        f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'} graduate, dated {today})"
    )
    for kind, title in entries:
        print(f"  - {kind}{title.strip() and ' ' + title.strip('— -')}")
    if args.dry_run:
        return 0

    # Graduate: empty [Unreleased] stays atop; the moved body becomes the new section.
    new_section = f"## [{version}] — {today}\n{body.rstrip()}\n\n"
    m = UNRELEASED_RE.search(text)
    assert m is not None
    rest = text[m.end():]
    nxt_m = SECTION_RE.search(rest)
    tail = rest[nxt_m.start():] if nxt_m else rest.lstrip("\n")
    cl_path.write_text(text[: m.end()] + "\n\n" + new_section + tail, encoding="utf-8")

    _git("add", "--", "CHANGELOG.md", cwd=cwd)
    _git(
        "commit", "-q",
        "-m", f"release: v{version}",
        "-m", "Agent-Role: primary",
        "-m", f"Agent-Context: release cut — [Unreleased] graduated to v{version} by scripts/release_cut.py",
        "-m", "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>",
        "--", "CHANGELOG.md", cwd=cwd,
    )
    _git("tag", "-a", f"v{version}", "-m", f"v{version}", cwd=cwd)
    print(f"cut v{version} (CHANGELOG graduated, tag created)")

    if not args.no_push:
        _git("push", cwd=cwd)
        _git("push", "origin", f"v{version}", cwd=cwd)
        print("pushed branch + tag")
    if not args.no_gh_release:
        try:
            r = subprocess.run(
                ["gh", "release", "create", f"v{version}", "--title", f"v{version}",
                 "--notes", body.strip()],
                cwd=cwd, capture_output=True, text=True, timeout=120,
            )
            print("GitHub Release created" if r.returncode == 0
                  else f"gh release failed (non-fatal): {r.stderr.strip()[:120]}")
        except (OSError, subprocess.SubprocessError) as e:
            # gh not installed (projects) — the cut itself already succeeded.
            print(f"gh unavailable (non-fatal): {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
