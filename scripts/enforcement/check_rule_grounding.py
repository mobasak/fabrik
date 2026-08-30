#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_rule_grounding.py
"""Rule-grounding gate — ADVISORY. A CONVERGED plan must PROVE its packs were open, not assert it.

THE MEASURED GAP (operator ruling 2026-08-30): the rule-grounding gate said "read every ACTIVE
pack, fresh reads only" and "self-assertion never counts" — and nothing verified any of it. The
author of two artifacts that day answered honestly: *"partially, not the full contract"*, and the
operator named the class: *"this is why ai agents are drifting they dont read relevant rules
fully."* An unfollowable duty (26 ACTIVE packs, 3 relevant) teaches skimming; a duty with no
grader at the flip cannot bind a session that read the contract hours ago.

THE COUNTABLE SUBSET this check owns, on CONVERGED plans named >= FLOOR_CUTOFF:
- **NO-DIGEST** — no `## Constraints Digest` section at all.
- **PACK-NOT-IN-DIGEST** (completeness) — a pack that `review_rubric.py --changed <the plan's File
  Scope>` MATCHES is never named in the digest. The MATCHED set is derived by SUBPROCESS of the
  repo's own rubric script (resolved from --root, so tests plant a controlled fake), never by
  re-implementing glob matching here.
- **QUOTE-NOT-FOUND** (integrity) — a digest row's quoted text does not exist in its cited file,
  after whitespace normalisation on BOTH sides (source lines wrap; a bare substring match flags a
  TRUE quote as fabricated — the inverse error, hit live on a martinfowler.com quote 2026-08-30).

WHAT IT CANNOT GRADE, stated so the blind spot is visible: whether the reading was comprehension or
transcription, whether the digest's implications are right, and whether packs beyond the MATCHED
set should have been consulted — /fabrik-plan-review's audit row owns all three.

NOT RETRO-GRADED: date-gated like its siblings (a day-one board-flooder is how an advisory earns
being skipped). DRAFT plans are never graded — incomplete is what DRAFT means.

ADVISORY BY CONTRACT. Registered `warn_only=True` and **always exits 0** — findings included.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PLANS_DIR = Path("docs") / "development" / "plans"

CONVERGED_RE = re.compile(r"^\**Status:?\**:?\s*\**\s*CONVERGED", re.IGNORECASE | re.M)
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
DIGEST_HEAD_RE = re.compile(r"^##\s+Constraints Digest\b", re.M | re.IGNORECASE)
FILESCOPE_HEAD_RE = re.compile(r"^##\s+File Scope\b", re.M | re.IGNORECASE)
SECTION_HEAD_RE = re.compile(r"^##\s+", re.M)
# The rubric's MATCHED emission — review_rubric.py:227 `### {rel}  (hit: …)`; that format already
# has a second programmatic consumer (the sensor inside review_rubric itself) and now this one.
MATCHED_LINE_RE = re.compile(r"^###\s+(\S+\.md)\s+\(hit:", re.M)
PATH_TOKEN_RE = re.compile(r"[\w./-]+")

FLOOR_CUTOFF = "2026-08-30"

ADVISORY_BUDGET = 500
MAX_LINE = 200
MAX_LINES = 10

REMEDY = (
    "quote one mandate verbatim per MATCHED pack (file:line) in the Constraints Digest - "
    "the quote is the proof the pack was open; run review_rubric.py --changed <File Scope> "
    "for the MATCHED set"
)


def _say(line: str) -> None:
    """Sibling of check_spec_convergence._say — the ASCII guarantee, so a filename can never turn
    this check's output into a swallowed UnicodeEncodeError that reads like a clean run."""
    print(line.encode("ascii", "backslashreplace").decode("ascii"))


class Finding:
    __slots__ = ("plan", "label", "detail")

    def __init__(self, plan: str, label: str, detail: str) -> None:
        self.plan, self.label, self.detail = plan, label, detail


def _norm(text: str) -> str:
    """Whitespace-collapse + markup-strip, both sides of every quote comparison."""
    text = text.replace("`", "").replace("**", "").replace("*", "")
    text = text.strip().strip('"').strip("“”").strip("'")
    return re.sub(r"\s+", " ", text)


def _section(text: str, head_re: re.Pattern[str]) -> str:
    m = head_re.search(text)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = SECTION_HEAD_RE.search(rest)
    return rest[: nxt.start()] if nxt else rest


def _digest_rows(section: str) -> list[tuple[str, str]]:
    """(quote, cited-path) per data row; header/separator rows skipped."""
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        quote = _norm(cells[0])
        if not quote or set(quote) <= {"-", ":", " "} or quote.lower().startswith("rule"):
            continue
        m = PATH_TOKEN_RE.search(cells[1].replace("`", ""))
        if not m:
            continue
        path = re.sub(r":\d+$", "", m.group(0))
        rows.append((quote, path))
    return rows


def _file_scope_paths(text: str) -> list[str]:
    paths = []
    for line in _section(text, FILESCOPE_HEAD_RE).splitlines():
        line = line.strip()
        if line.startswith("- "):
            m = PATH_TOKEN_RE.search(line[2:].replace("`", ""))
            if m:
                paths.append(m.group(0))
    return paths


def _matched_packs(root: Path, scope_paths: list[str]) -> list[str]:
    """The rubric's MATCHED set, by subprocess of the repo's own script — resolved from root."""
    rubric = root / "scripts" / "review_rubric.py"
    if not rubric.is_file() or not scope_paths:
        return []
    try:
        r = subprocess.run(
            [sys.executable, str(rubric), "--changed", *scope_paths],
            capture_output=True,
            text=True,
            cwd=str(root),
            timeout=120,
        )
    except Exception:
        return []  # a broken rubric never reds an advisory; completeness silently ungraded
    return MATCHED_LINE_RE.findall(r.stdout or "")


def _candidate_plans(root: Path) -> list[Path]:
    base = root / PLANS_DIR
    out: list[Path] = []
    try:
        for entry in sorted(base.iterdir()):
            if entry.is_file() and entry.suffix == ".md":
                out.append(entry)
            elif entry.is_dir():
                spine = entry / f"{entry.name}.md"
                if spine.is_file():
                    out.append(spine)
    except OSError:
        pass
    return out


def _audit(root: Path) -> tuple[int, list[Finding]]:
    examined = 0
    findings: list[Finding] = []
    for path in _candidate_plans(root):
        m = DATE_RE.match(path.name)
        if not m or m.group(1) < FLOOR_CUTOFF:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not CONVERGED_RE.search(text):
            continue
        examined += 1
        name = path.name

        digest = _section(text, DIGEST_HEAD_RE)
        if not digest.strip():
            findings.append(
                Finding(
                    name,
                    "NO-DIGEST",
                    "no '## Constraints Digest' section - a CONVERGED plan proves its packs were "
                    "open with per-pack verbatim quotes, never by self-assertion",
                )
            )
            continue

        rows = _digest_rows(digest)
        for quote, cited in rows:
            target = root / cited
            if not target.is_file():
                findings.append(
                    Finding(name, "QUOTE-NOT-FOUND", f"digest cites {cited} which does not exist")
                )
                continue
            try:
                source = _norm(target.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if quote not in source:
                findings.append(
                    Finding(
                        name,
                        "QUOTE-NOT-FOUND",
                        f"quoted text not found in {cited} (whitespace-normalised) - a quote "
                        "you cannot find is a pack that was not open",
                    )
                )

        digest_text = digest.lower()
        for pack in _matched_packs(root, _file_scope_paths(text)):
            if pack.lower() not in digest_text:
                findings.append(
                    Finding(
                        name,
                        "PACK-NOT-IN-DIGEST",
                        f"rubric MATCHES {pack} for this plan's File Scope but the digest never "
                        "names it - the computed read-set is the floor, not a suggestion",
                    )
                )
    return examined, findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Advisory: a CONVERGED plan proves its rule reading.")
    parser.add_argument("--root", default=".", help="repo root to audit (default: cwd)")
    # parse_KNOWN_args INSIDE the guard: argparse's SystemExit derives from BaseException — the
    # sibling checks' proven frame (a warn_only check may never exit non-zero).
    try:
        args, _unknown = parser.parse_known_args(argv)
        examined, findings = _audit(Path(args.root))
    except SystemExit:
        return 0
    except Exception as exc:
        try:
            _say(f"could not evaluate rule grounding: {type(exc).__name__}")
        except Exception:  # pragma: no cover - stdout itself is broken
            pass
        return 0

    if examined == 0:
        return 0

    census = (
        f"rule grounding: {examined} CONVERGED in-window plan(s) examined, "
        f"{len({f.plan for f in findings})} with findings (artifact-only; reading quality is the review's)"
    )
    _say(census)
    if not findings:
        return 0

    marker_cost = len(f"  ... {len(findings)} more finding(s) - run the check directly") + 1
    budget = ADVISORY_BUDGET - (len(census) + 1) - (len(REMEDY) + 6) - marker_cost
    emitted = 0
    for f in findings:
        line = f"  {f.label}: {f.plan} {f.detail}".rstrip()
        if len(line) > MAX_LINE:
            line = line[: MAX_LINE - 3] + "..."
        if (budget - len(line) < 0 or emitted >= MAX_LINES - 3) and emitted:
            break
        _say(line)
        budget -= len(line) + 1
        emitted += 1
    if emitted < len(findings):
        _say(f"  ... {len(findings) - emitted} more finding(s) - run the check directly")
    _say(f"  -> {REMEDY}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
