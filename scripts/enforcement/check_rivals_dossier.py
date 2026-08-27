#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_rivals_dossier.py
"""Rivals-dossier gate — ADVISORY. A competitive dossier must satisfy its own terminal contract.

THE MEASURED GAP. `/fabrik-rivals` shipped with a five-condition termination contract
(`commands/_sources/fabrik-rivals.md` § Termination contract) and **no grader whatsoever** — an
audit on 2026-08-27 found `grep -rln rivals scripts/enforcement/` returned nothing. That is the same
"contract stated in prose, graded by the agent it constrains" class that `/fabrik-user-test` had just
had removed, and it matters more here because the artifact this command produces is what a product
spec gets decided on: a zero-rival scan reads as "this market has no competitors" rather than "the
scan failed", and a budget-truncated run reads as a complete one.

Four of the five conditions are decidable straight off the artifact the driver already writes:
`competitors` non-empty, `truncated` False, the dossier on disk, and its `INDEX.md` row.

WHAT IT DOES NOT GRADE, stated because a grader that hides its blind spot rebuilds the very defect
one layer down: it reads the dossier's own renderer-emitted header. It cannot re-ground a BEAT card
(Tier-C by construction — the engine never held the raw review page), cannot prove a named rival is
real, and cannot tell a genuinely dry discovery round from one that never re-ran. See `SCOPE_NOTE`.

ADVISORY BY CONTRACT. Registered `warn_only=True` and **always exits 0** — findings included.
`final_gate.py` turns any non-zero exit from a `warn_only` check into a BLOCKING red ("its contract
changed"), which on a governance-synced check means ~46 repos. Every failure path returns 0 with an
honest line; the exception guard catches the CLASS, never an enumerated list of types.

SILENT WHERE THERE IS NOTHING TO SAY. Most of the fleet has never run a scan, and an advisory line
in a repo with no `docs/reference/rivals/` is pure noise that trains readers to skip advisory output.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# The dossier tree `/fabrik-rivals` Phase 3 writes into. Relative to the repo root, and already
# inside the gate-enforced `.md` allowlist (`check_doc_sprawl.py`: `^docs/reference/.+\.md$`).
DOSSIER_DIR = Path("docs") / "reference" / "rivals"

# The renderer's single machine-readable line (`rivals_run.py::render_dossier_md`). Parsing the
# header rather than a sibling JSON is deliberate: the JSON is written only when `--out` is passed,
# so a dossier can legitimately exist without one, and the markdown is the artifact under contract.
RIVALS_RE = re.compile(r"\*\*rivals:\*\*\s*(\d+)")
PARTIAL_RE = re.compile(r"\*\*partial:\*\*\s*(True|False)", re.IGNORECASE)
TRUNCATED_RE = re.compile(r"\*\*truncated:\*\*\s*(True|False)", re.IGNORECASE)

SCOPE_NOTE = (
    "grades self-reported provenance only (renderer header); cannot re-ground Tier-C BEAT cards "
    "or prove a rival is real"
)
# What the CENSUS carries. `SCOPE_NOTE` in full is 118 chars — nearly a quarter of the advisory
# budget spent before the first finding — so the census carries the short form and the full note
# stays the module's documented contract (and what the docstring + tests pin).
CENSUS_NOTE = "self-reported provenance only"

# `final_gate` prints ten lines of advisory output and truncates the stream at 500 chars with NO
# ellipsis, so the census must come FIRST and every later line must be charged against a budget.
ADVISORY_BUDGET = 500
MAX_LINE = 220
MAX_LINES = 10

REMEDY = (
    "re-run the scan (--rediscover rounds, then a final round without it); "
    "a zero-rival or truncated dossier is a FAILED scan, never an empty market"
)


def _say(line: str) -> None:
    """The ONLY print in this module, and the ASCII guarantee's home.

    Coercing here makes every emitted byte ASCII **by construction** — provable without a
    subprocess and independent of whatever stream `final_gate` has wrapped stdout in. A market name
    or rival carrying a non-ASCII character must never turn this check's output into a
    `UnicodeEncodeError` swallowed by the guard, which reads exactly like a clean run.
    """
    print(line.encode("ascii", "backslashreplace").decode("ascii"))


class Finding:
    """One condition a dossier fails. `label` is the class; `detail` names the evidence."""

    __slots__ = ("dossier", "label", "detail")

    def __init__(self, dossier: str, label: str, detail: str) -> None:
        self.dossier, self.label, self.detail = dossier, label, detail


def _index_mentions(root: Path, rel: str) -> bool:
    """Terminal condition 5's INDEX row. Absence of INDEX.md itself is NOT a rivals finding — that
    is a different check's business, and reporting it here would fire in every repo that has no
    INDEX.md for reasons having nothing to do with a dossier."""
    index = root / "INDEX.md"
    try:
        return not index.is_file() or rel in index.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True  # unreadable INDEX: fail SOFT, this check does not own that failure


def _audit(root: Path) -> tuple[int, list[Finding]]:
    """Return (dossiers examined, findings). Never raises for a per-file problem."""
    try:
        paths = sorted(p for p in (root / DOSSIER_DIR).glob("*.md") if p.is_file())
    except OSError:
        return 0, []

    findings: list[Finding] = []
    for path in paths:
        name = path.name
        rel = f"{DOSSIER_DIR.as_posix()}/{name}"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(Finding(name, "UNREADABLE", f"({type(exc).__name__})"))
            continue

        rivals = RIVALS_RE.search(text)
        if rivals is None:
            # No renderer header => nothing below is checkable. Report THAT, and do not also emit
            # three derived findings whose real cause is this one.
            findings.append(
                Finding(name, "NO-HEADER", "not produced by rivals_run.render_dossier_md")
            )
        else:
            if int(rivals.group(1)) == 0:
                findings.append(Finding(name, "FAILED-SCAN", "zero rivals - not an empty market"))
            trunc = TRUNCATED_RE.search(text)
            if trunc and trunc.group(1).lower() == "true":
                findings.append(
                    Finding(
                        name, "TRUNCATED", "the money ceiling BOUND this run - partial by budget"
                    )
                )
            part = PARTIAL_RE.search(text)
            if part and part.group(1).lower() == "true":
                findings.append(Finding(name, "PARTIAL", "a leg degraded - see degrade_causes"))

        if not _index_mentions(root, rel):
            findings.append(Finding(name, "UNINDEXED", f"no INDEX.md row for {rel}"))

    return len(paths), findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repo root to audit (default: cwd)")
    try:
        args = parser.parse_args(argv)
        examined, findings = _audit(Path(args.root))
    except Exception as exc:  # the CLASS, never an enumerated list of types
        try:
            _say(f"could not evaluate rivals dossiers: {type(exc).__name__}")
        except Exception:  # pragma: no cover - stdout itself is broken; stay silent, stay 0
            pass
        return 0

    if examined == 0:
        return 0  # no dossiers in this repo - say nothing at all

    census = (
        f"rivals dossiers: {examined} examined, "
        f"{len({f.dossier for f in findings})} with findings ({CENSUS_NOTE})"
    )
    _say(census)  # FIRST, always: final_gate truncates this stream at 500 chars with NO ellipsis
    if not findings:
        return 0

    # ⚠️ The '... N more' marker is CHARGED UP FRONT, not paid for out of whatever is left when the
    # budget runs dry. Measured on this check's own first draft: 5 dossiers x 3 findings emitted
    # 544 chars and the REMEDY — the only line telling the reader what to DO — was cut mid-word by
    # final_gate. Over-reserving can only cost one finding we already name in the marker;
    # under-reserving silently truncates the trailer, which reads exactly like a shorter clean run.
    marker_cost = len(f"  ... {len(findings)} more finding(s) - run the check directly") + 1
    budget = ADVISORY_BUDGET - (len(census) + 1) - (len(REMEDY) + 6) - marker_cost
    emitted = 0
    for f in findings:
        line = f"  {f.label}: {f.dossier} {f.detail}".rstrip()
        if len(line) > MAX_LINE:  # never let ONE finding eat the whole budget
            line = line[: MAX_LINE - 1] + "..."
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
