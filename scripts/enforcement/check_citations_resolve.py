#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_check_citations_resolve.py | scripts/final_gate.py (registration, warn_only) | docs/workstation/hooks-index.md
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
A BARE filename (`tool.py:43`) is graded against the one TRACKED file its basename names (`git ls-files`,
W-191404c0) unless that file is root-level, under templates/, commands/_sources/ or commands/_agents/ (the
rendered command is cited, not its source), or the doc spells another path ending in it (`/opt/seo/…/config.py`)
— those count `ambiguous`; no tracked match counts `bare`. A finding names the cited token and the resolved
path. Measured 2026-10-08 (hub window, 700 docs): 1,396 bare citations — 1,096 unique non-root, 72 root, 163
several, 65 none; 150 of the unique ones sit in commands/_sources/.
Sources: docs/superpowers/specs/**, docs/development/plans/** (incl. archived), docs/development/reviews/**,
docs/reference/** — or exactly the files named by `--doc <path>` (repeatable: a pin, a scratch design note),
which bypass the globs and the window and are listed in the output. Fenced code blocks are skipped (a
citation inside an example is not a claim). A run that GRADED 0 never prints the ✓: citations found and none
graded is `⚠ … NOTHING GRADED` (under --quiet too), docs without a citation `0 citations found`.
COBRA (D-253): the cheapest dodge is a root-level, templates/ or ambiguous bare name — every one is counted
in the tally, and a doc that grades 0 prints NOTHING GRADED even quietly.
Never blocks. The gate runs it with `--changed` (the author's unstaged + staged + unpushed docs — the
moment a citation is cheap to fix); a bare run sweeps every dated artifact of the last 30 days plus
the undated reference docs (`--since-days N` widens; `--root <repo>` for another tree).

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
    seen, _bare, _ambiguous, _outside, findings = check_text_full(text, repo)
    return seen, findings


# W-191404c0: a bare basename is resolved against the repo's TRACKED files. Built lazily (the first bare
# citation pays one `git ls-files -z`, cwd = the root) and cached per resolved root; a root that is not a
# repository yields an empty index, so a bare name there stays ungraded exactly as before.
_INDEX: dict[Path, dict[str, list[str]]] = {}
# A unique match is still NOT graded when it sits where a same-named file elsewhere is the likelier
# referent (measured 2026-10-08, the design critiques): a ROOT-level file (17 of 28 hub root basenames
# are hub-unique, but AGENTS.md, CHANGELOG.md, INDEX.md, PORTS.md recur in 38-47 repos), anything under
# templates/ (emitted into a project, then edited there), and commands/_sources/ or commands/_agents/ —
# docs cite the RENDERED command, whose include-expanded line numbers are not the source's (150 of 1,096
# unique window hits). Those are counted `ambiguous`, like a basename naming several files.
_RENDERED_ELSEWHERE = ("templates/", "commands/_sources/", "commands/_agents/")


def _basename_index(repo: Path) -> dict[str, list[str]]:
    key = repo.resolve()
    if key not in _INDEX:
        index: dict[str, list[str]] = {}
        try:
            res = subprocess.run(
                ["git", "ls-files", "-z"], cwd=key, capture_output=True, check=False
            )
            names = res.stdout.decode("utf-8", "replace").split("\0") if res.returncode == 0 else []
        except OSError:
            names = []
        for rel in filter(None, names):
            index.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)
        _INDEX[key] = index
    return _INDEX[key]


def _spelled_elsewhere(text: str, base: str, resolved: str) -> bool:
    """The doc ALSO spells a path ending in `/<base>` that is not the resolved file — an `/opt/<repo>/…`
    or `~/.claude/…` path, or another repo-relative one: the bare citation is then shorthand for THAT."""
    for m in re.finditer(rf"[\w.~-]*(?:/[\w.~-]+)*/{re.escape(base)}(?![\w.-])", text):
        spelled = m.group(0).lstrip("~.")
        if not (resolved.endswith(spelled.lstrip("/")) or spelled.endswith("/" + resolved)):
            return True
    return False


def check_text_full(text: str, repo: Path) -> tuple[int, int, int, int, list[str]]:
    """(citations examined, bare filenames left ungraded, bare filenames counted ambiguous, citations
    whose path is not a file under ``repo``, findings). Every skipped bucket is COUNTED, so a run that
    graded nothing can say so instead of reading as a clean zero (01M3PNG4)."""
    findings: list[str] = []
    seen = bare = ambiguous = outside = 0
    cache: dict[str, list[str] | None] = {}
    for m in CITE_RE.finditer(_strip_fences(text)):
        cited, a, b = m.group(1), int(m.group(2)), m.group(3)
        path, shown = cited, cited
        if "/" not in cited:
            # A BARE filename is graded only when it names ONE tracked file outside the excluded
            # places and the doc spells no other path to it (66aa32a5: a deploy plan citing another
            # repo's compose.yaml — 27 tracked copies on the hub, so it is ambiguous here).
            hits = _basename_index(repo).get(cited, [])
            if not hits:
                bare += 1
                continue
            only = hits[0]
            if (
                len(hits) > 1
                or "/" not in only
                or only.startswith(_RENDERED_ELSEWHERE)
                or _spelled_elsewhere(text, cited, only)
            ):
                ambiguous += 1
                continue
            path, shown = only, f"{cited}:{a}{'-' + b if b else ''} (→ {only})"
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
            outside += 1  # another repo's file, a renamed one, or tracked but deleted — counted
            continue
        seen += 1
        end = int(b) if b else a
        where = shown if shown != cited else f"{path}:{a}{'-' + b if b else ''}"
        if a < 1 or end > len(lines) or end < a:
            findings.append(f"BEYOND-EOF {where} (file has {len(lines)} lines)")
            continue
        if a > 1 and BLANKISH.match(
            lines[a - 1]
        ):  # line 1 = a frontmatter `---` is a legitimate target
            target_line = f"{path}:{a}" if shown == cited else f"{cited}:{a} (→ {path})"
            findings.append(f"BLANK-TARGET {target_line} → {lines[a - 1].strip()[:40]!r}")
    return seen, bare, ambiguous, outside, findings


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
    ndocs, total, _bare, _ambiguous, _outside, findings = check_repo_full(repo, since_days, only)
    return ndocs, total, findings


def check_repo_full(
    repo: Path,
    since_days: int = DEFAULT_SINCE_DAYS,
    only: set[Path] | None = None,
    docs_given: list[Path] | None = None,
) -> tuple[int, int, int, int, int, list[str]]:
    """``check_repo`` plus the three skipped counts of ``check_text_full``, summed over the docs.
    ``docs_given`` (``--doc``) grades exactly those files — a pin, or an artifact outside the
    source globs such as a scratch design note — bypassing globs, window and ``only``."""
    if docs_given is not None:
        docs = sorted({p.resolve() for p in docs_given if p.is_file()})
    else:
        docs = sorted(
            {
                p
                for g in SOURCE_GLOBS
                for p in repo.glob(g)
                if p.is_file() and _in_window(p, since_days) and (only is None or p in only)
            }
        )
    total, bare, ambiguous, outside, findings = 0, 0, 0, 0, []
    for doc in docs:
        n, b, am, o, f = check_text_full(doc.read_text(encoding="utf-8", errors="replace"), repo)
        total, bare, ambiguous, outside = total + n, bare + b, ambiguous + am, outside + o
        name = doc.relative_to(repo) if doc.is_relative_to(repo) else doc
        findings += [f"{name}: {x}" for x in f]
    return len(docs), total, bare, ambiguous, outside, findings


def _cwd_toplevel() -> Path | None:
    """The git toplevel of the directory the check was RUN from, or None outside a repo."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
        )
    except OSError:
        return None
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 and r.stdout.strip() else None


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    quiet = "--quiet" in args
    repo = REPO
    if "--root" in args:
        repo = Path(args[args.index("--root") + 1]).resolve()
    else:
        here = _cwd_toplevel()
        if here is not None and here != repo.resolve():
            # the measured case (01M3PNG4): another repo's copy run from here grades ITS OWN docs
            print(
                f"⚠ check_citations_resolve graded {repo}, not the repo it was run from ({here}) "
                f"— pass --root {here}"
            )
    since = DEFAULT_SINCE_DAYS
    if "--since-days" in args:
        since = int(args[args.index("--since-days") + 1])
    only = _changed_docs(repo) if "--changed" in args else None
    given = [Path(args[i + 1]) for i, a in enumerate(args[:-1]) if a == "--doc"] or None
    ndocs, ncites, bare, ambiguous, outside, findings = check_repo_full(
        repo, since_days=since, only=only, docs_given=given
    )
    found = ncites + bare + ambiguous + outside
    tally = (
        f"{ncites} graded of {found} found ({bare} bare filename, {ambiguous} ambiguous, "
        f"{outside} not under root {repo})"
    )
    if given is not None:
        # --doc names its own scope, so the run says which files it examined (term-edit.md: a gate run
        # counts only when the artifact is shown to be in the examined set)
        print(f"citations: --doc examined {ndocs} file(s): {', '.join(str(p) for p in given)}")
    if findings:
        print(
            f"⚠ check_citations_resolve ADVISORY — {len(findings)} citation(s) do not land, of "
            f"{ncites} examined across {ndocs} docs (a wrong `path:line` reads as verified and is not)"
            f" — {tally}:"
        )
        for f in findings[:60]:
            print(f"   - {f}")
        if len(findings) > 60:
            print(f"   … {len(findings) - 60} more")
    elif found and not ncites:
        # printed under --quiet too (the gate's mode): citations were found and NONE graded — never a
        # clean zero. Since W-191404c0 a bare filename is a claim whenever it can resolve, so a doc of
        # bare, ambiguous or foreign citations says so too.
        print(f"⚠ check_citations_resolve NOTHING GRADED across {ndocs} docs — {tally}")
    elif not quiet and not ndocs:
        print(f"citations: nothing in scope — 0 docs under {repo} match the source families")
    elif not quiet and not found:
        print(f"citations: 0 citations found across {ndocs} docs — nothing to grade")
    elif not quiet:
        print(
            f"✓ citations resolve — {ncites} `path:line` citation(s) across {ndocs} docs all land"
            f" — {tally}"
        )
    return 0  # advisory by contract; the findings are the product


if __name__ == "__main__":
    sys.exit(main())
