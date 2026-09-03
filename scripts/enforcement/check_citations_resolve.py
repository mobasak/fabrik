#!/usr/bin/env python3
"""check_citations_resolve — do a document's `path:line` citations LAND? (ADVISORY, exit 0 always)

Every other class of claim in a spec/plan/review has an executable check (a probe, the gate,
check_convergence, check_rule_grounding). A `path:line` citation had NONE: its only verifier was a
human re-opening the file — so a plausible-looking anchor was strictly better than no citation for
passing review and strictly worse for the reader. Measured before this existed (2026-09-02/03):
10 anchors on blank lines / `---` rules / unrelated content in ONE converged plan set that four
plan-review passes stamped "every citation opened" (web-ecommerce-factory 01M1GNGS); 4 wrong ranges in
one converged spec (fabrik-lib 01M1J2TP); 8 stale anchors in one 13-row doc block while the link
checker said 0 broken (web-ecommerce-factory 01M1JF7Y).

What it grades, per citation `path:LINE` or `path:LINE-LINE` on a file that EXISTS in the repo:
  BEYOND-EOF    — the line (or the range's end) is past the file's last line
  BLANK-TARGET  — the cited line is blank, a `---` rule, or a fence marker (never a legitimate target)
A path that does not exist here is NOT graded: measured on the hub at landing, 500+ of 1600 citations
were old plans citing ANOTHER repo's files (transdoc, fabrik-lib modules) — a legitimate pattern, and
flagging it would have made this check wallpaper on day one (FIX DIRECTIVE 5, measured, rejected).
Sources: docs/superpowers/specs/**, docs/development/plans/** (incl. archived), docs/development/reviews/**,
docs/reference/**. Fenced code blocks are skipped (a citation inside an example is not a claim).
Never blocks. The gate runs it with `--changed` (the author's unstaged + staged + unpushed docs — the
moment a citation is cheap to fix); a bare run sweeps every dated artifact of the last 30 days plus
the undated reference docs (`--since-days N` widens; `--root <repo>` for another tree).

# AFTER-EDIT: tests/enforcement/test_check_citations_resolve.py | scripts/final_gate.py (registration, warn_only) | docs/workstation/hooks-index.md
"""

from __future__ import annotations

import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_GLOBS = (
    "docs/superpowers/specs/**/*.md",
    "docs/development/plans/**/*.md",
    "docs/development/reviews/**/*.md",
    "docs/reference/**/*.md",
)
# `scripts/x.py:123`, `scripts/x.py:120-130`, `.windsurf/rules/core/10-python.md:249` — a path-shaped
# token (a `/` somewhere, or a known extension) followed by :N or :N-M. Trailing `:` in prose is
# not consumed. The `(?<![\w:/])` guard keeps `https://host:8000` and `12:30` out.
CITE_RE = re.compile(
    r"(?<![\w:/])((?:[\w.-]+/)+[\w.-]+|[\w.-]+\.(?:py|md|yaml|yml|sh|toml|json|ts|js|mjs|txt))"
    r":(\d{1,6})(?:-(\d{1,6}))?(?![\w-])"
)
BLANKISH = re.compile(r"^\s*(?:|---+|\*\*\*+|```.*)\s*$")


def _strip_fences(text: str) -> str:
    out, fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fence = not fence
            out.append("")
            continue
        out.append("" if fence else line)
    return "\n".join(out)


def check_text(text: str, repo: Path) -> tuple[int, list[str]]:
    """(citations examined, findings) for one document's text."""
    findings: list[str] = []
    seen = 0
    cache: dict[str, list[str] | None] = {}
    for m in CITE_RE.finditer(_strip_fences(text)):
        path, a, b = m.group(1), int(m.group(2)), m.group(3)
        if "/" not in path:
            # A BARE filename (`compose.yaml:60`, `AGENTS.md:73`) is ambiguous: a deploy plan cites the
            # SERVICE repo's compose, which happens to share a name with the hub's 32-line one
            # (review of 66aa32a5: 11 of 30 hits were this shape). Only a slashed path is a claim
            # about THIS tree.
            continue
        target = repo / path
        if path not in cache:
            try:
                cache[path] = (
                    target.read_text(encoding="utf-8", errors="replace").splitlines()
                    if target.is_file()
                    else None
                )
            except OSError:
                cache[path] = None
        lines = cache[path]
        if lines is None:
            continue  # another repo's file, or a renamed one — not this check's claim (see header)
        seen += 1
        end = int(b) if b else a
        if a < 1 or end > len(lines) or end < a:
            findings.append(
                f"BEYOND-EOF {path}:{a}{'-' + b if b else ''} (file has {len(lines)} lines)"
            )
            continue
        if a > 1 and BLANKISH.match(
            lines[a - 1]
        ):  # line 1 = a frontmatter `---` is a legitimate target
            findings.append(f"BLANK-TARGET {path}:{a} → {lines[a - 1].strip()[:40]!r}")
    return seen, findings


DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-")
DEFAULT_SINCE_DAYS = 30  # a dated artifact older than this is HISTORY — its anchors drift by design


def _in_window(doc: Path, since_days: int) -> bool:
    """Dated artifacts (YYYY-MM-DD-…) older than the window are history: measured on the hub at
    landing, 154 of 1197 citations did not land and nearly all sat in plans from June–August whose
    targets have since moved — true, and not actionable. Undated docs (docs/reference) are current
    by definition and always graded."""
    m = DATE_RE.match(doc.name) or DATE_RE.match(doc.parent.name)
    if not m:
        return True
    try:
        d = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return True
    return (_dt.date.today() - d).days <= since_days


def _changed_docs(repo: Path) -> set[Path]:
    """The docs THIS author is changing: unstaged + staged + unpushed. The gate grades those — the
    moment a citation is written is the moment it is cheap to fix; a repo-wide sweep (`--all`)
    measured 115 stale anchors across 834 citations in 30-day-old plans on the hub, true and
    unactionable as a per-run advisory."""
    out: set[Path] = set()
    cmds = [["git", "diff", "--name-only", "HEAD"], ["git", "diff", "--cached", "--name-only"]]
    try:
        up = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "@{u}"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if up.returncode == 0 and up.stdout.strip():
            cmds.append(["git", "diff", "--name-only", f"{up.stdout.strip()}..HEAD"])
    except OSError:
        return out
    for cmd in cmds:
        try:
            res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
        except OSError:
            continue
        for line in res.stdout.splitlines():
            if line.endswith(".md"):
                out.add(repo / line.strip())
    return out


def check_repo(
    repo: Path, since_days: int = DEFAULT_SINCE_DAYS, only: set[Path] | None = None
) -> tuple[int, int, list[str]]:
    docs = sorted(
        {
            p
            for g in SOURCE_GLOBS
            for p in repo.glob(g)
            if p.is_file() and _in_window(p, since_days) and (only is None or p in only)
        }
    )
    total, findings = 0, []
    for doc in docs:
        n, f = check_text(doc.read_text(encoding="utf-8", errors="replace"), repo)
        total += n
        findings += [f"{doc.relative_to(repo)}: {x}" for x in f]
    return len(docs), total, findings


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in args
    repo = REPO
    if "--root" in args:
        repo = Path(args[args.index("--root") + 1]).resolve()
    since = DEFAULT_SINCE_DAYS
    if "--since-days" in args:
        since = int(args[args.index("--since-days") + 1])
    only = _changed_docs(repo) if "--changed" in args else None
    ndocs, ncites, findings = check_repo(repo, since_days=since, only=only)
    if findings:
        print(
            f"⚠ check_citations_resolve ADVISORY — {len(findings)} citation(s) do not land, of "
            f"{ncites} examined across {ndocs} docs (a wrong `path:line` reads as verified and is not):"
        )
        for f in findings[:60]:
            print(f"   - {f}")
        if len(findings) > 60:
            print(f"   … {len(findings) - 60} more")
    elif not quiet:
        print(
            f"✓ citations resolve — {ncites} `path:line` citation(s) across {ndocs} docs all land"
        )
    return 0  # advisory by contract; the findings are the product


if __name__ == "__main__":
    sys.exit(main())
