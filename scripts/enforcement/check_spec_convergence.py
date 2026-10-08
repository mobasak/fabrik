#!/usr/bin/env python3
# AFTER-EDIT: tests/enforcement/test_spec_convergence.py
"""Spec-convergence gate — ADVISORY. A spec claiming CONVERGED must show it was actually converged.

THE MEASURED GAP. `/fabrik-spec` carries a **BLOCKING live-research gate for every external fact**
and `/fabrik-spec-review` flips `Status: DRAFT → CONVERGED` after an edit-free no-op round. Nothing
graded that claim. `check_convergence.py` scans `docs/development/plans/` + `docs/development/reviews/`
only, and `check_stage_artifacts.py` explicitly defers CONVERGED-claim grading to it while merely
checking that a plan's cited spec HAS a status. So the pipeline's front door was presence-checked and
never evidenced — the "contract with no grader" class, on the artifact every later stage inherits.

Measured on the hub 2026-08-27: 16 of 21 specs claim CONVERGED, and **nine cite zero external source
URLs while never saying why**. Zero citations is often correct — most infra specs have no vendor
facts — but silence makes "there were no external facts" and "I skipped the blocking research gate"
byte-identical, and only one of those is convergence. The one spec that DOES state it was produced
under a review that explicitly challenged the vacuous-satisfaction claim, which is what makes this
bar demonstrably achievable rather than aspirational.

WHAT IT CANNOT GRADE, stated because a grader that hides its blind spot rebuilds the defect one layer
down: it reads the artifact. It cannot re-fetch a cited URL, prove a quote is real, verify a date was
not invented, or know whether the no-op round actually happened. See `SCOPE_NOTE`.

NOT GRANDFATHERED. Every CONVERGED spec is graded, including pre-existing ones — the operator's
standing rollout ruling is "advisory fleet-wide on landing, promote to blocking after the fleet has
run it once; nothing grandfathered, nothing silently re-baselined." A DRAFT is never graded: being
incomplete is what DRAFT means, and punishing it would penalise the honest state.

ADVISORY BY CONTRACT. Registered `warn_only=True` and **always exits 0** — findings included. A
non-zero exit from a `warn_only` check is a BLOCKING red across ~46 governance-synced repos.

THREE WAYS TO RUN IT (W-7cdad5d5). No arguments — what final_gate runs — prints a census and as many
findings as fit `ADVISORY_BUDGET`, a house convention for one readable gate line (final_gate itself
shows 10 lines and clips `--json` at 1400+600 chars; it has no 500-char cut). `--all` prints every
finding. Naming spec files or directories grades only those, unbudgeted, with an "of N named"
denominator and a line for every named path that was not graded (NOT-FOUND, UNREADABLE,
NOT-CONVERGED) or was graded only partly (UNDATED) — the closing receipt's own-spec verdict, which
used to need a scratch `--root` (iterative_image_editor 01M40T050B; measured 2026-10-08: 10 of 14
repos truncated, 93 findings hidden).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SPECS_DIR = Path("docs") / "superpowers" / "specs"

# The convergence claim. Bold-or-plain, colon inside OR outside the bold — the same tolerance
# `check_convergence.py` already applies, so both call sites agree on what "CONVERGED" looks like.
CONVERGED_RE = re.compile(r"\*{0,2}Status:?\*{0,2}:?\s*\**\s*CONVERGED", re.IGNORECASE)

# An external source citation. A bare domain is not evidence; a fetchable URL is.
URL_RE = re.compile(r"https?://[^\s)\]>]+")

# The explicit "the 1a gate is vacuously satisfied" statement. Deliberately GENEROUS — the finding is
# for SILENCE, not for phrasing, and a check that demands one wording would just teach people that
# wording. Anything that plainly says "this design has no external facts" clears it.
NO_EXTERNAL_RE = re.compile(
    r"no\s+external\s+(facts?|dependenc\w+|claims?|APIs?|sources?)"
    r"|zero\s+external"
    r"|vacuous\w*\s+satisf\w+"
    r"|no\s+third[- ]party"
    r"|purely\s+internal"
    r"|1a[^.\n]{0,40}\b(n/?a|vacuous\w*|not\s+applicable)",
    re.IGNORECASE,
)

# The contract's own closing obligation: "Do not promise 100% accuracy - iterate to a fixed point,
# then enumerate residual unknowns / assumptions". A CONVERGED spec with none is claiming omniscience.
RESIDUAL_RE = re.compile(r"residual|unknown|assumption|open\s+question", re.IGNORECASE)

# Intake Inventory (chat-intake fragment, landed 2026-08-29): a spec is authored ON a conversation,
# and the conversation's items are its denominator. The live defect: a session finds 10 issues, the
# operator says spec it, the agent specs a subset and tells no one. DATE-GATED to specs named after
# the contract landed — retro-grading 21 pre-contract specs would put findings on every board on day
# one, which is how advisory output earns being skipped (fire rate on landing: 0, measured).
INTAKE_CUTOFF = "2026-08-30"

# The 1c APPROACH floor (2026-08-30): a CONVERGED spec needs >=2 DISTINCT cited URLs backing its
# approach — and the NO_EXTERNAL escape does NOT waive this one. That escape exists for 1a (facts:
# a design can truly have no vendor API); the approach space always exists, and "purely internal"
# is the exact self-exemption that shipped a decision-ledger spec on one summariser fetch the day
# this floor landed (the mandated search then overturned its row semantics in ten minutes).
# DATE-GATED like the intake rule: measured 2026-08-30, 14 of 20 historical CONVERGED specs would
# red on a blanket floor — a day-one board-flooder is how an advisory earns being skipped.
FLOOR_CUTOFF = "2026-08-30"
FLOOR_MIN_URLS = 2

# The interrogative floor (2026-08-30): WHO and WHEN are mandated SECTIONS, not style choices.
# Measured need: against a twice-converged spec the operator had to ask "does it take into account
# roles?" (WHO — automated consumers, every duty's role-holder) and "what will happen to the file
# if it grows too much?" (WHEN — lifecycle, growth triggers). Same date gate as the approach floor:
# only the countable subset (heading presence) is enforced here; /fabrik-spec-review's interrogative
# walk owns whether the sections actually ANSWER their questions.
PERSONAS_HEAD_RE = re.compile(r"^##\s+Personas\b", re.M)
LIFECYCLE_HEAD_RE = re.compile(r"^##\s+Lifecycle\b", re.M)
INTAKE_HEAD_RE = re.compile(r"^##\s+Intake Inventory\b", re.M)
INTAKE_ROW_RE = re.compile(r"^\|\s*I\d+\s*\|(.+)$", re.M)
INTAKE_DISPO_RE = re.compile(r"\b(IN|OUT-OF-SCOPE|ASK)\b")
SPEC_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")

SCOPE_NOTE = (
    "reads the artifact only; cannot re-fetch a cited URL, prove a quote is real, or know whether "
    "the no-op round happened"
)
CENSUS_NOTE = "artifact-only; citations not re-fetched"

ADVISORY_BUDGET = 500
MAX_LINE = 200
MAX_LINES = 10

REMEDY = (
    "run /fabrik-spec-review to a no-op; a spec with no external facts must SAY so, "
    "and a converged spec must enumerate its residual unknowns"
)

# The way out, NAMED: "run the check directly" sent a reader to the same truncated output (01M40T050B).
MARKER = "  ... {n} more finding(s) - rerun with --all, or name the spec(s)"


def _ascii(line: str) -> str:
    """The ASCII guarantee — a spec filename carrying a non-ASCII character must never turn this
    check's output into a swallowed `UnicodeEncodeError`, which reads exactly like a clean run. The
    budget is counted on THIS form: an em-dash costs six characters once escaped, and counting the
    raw line overran the budget (503-506 of 500 chars, found by the W-7cdad5d5 design critiques)."""
    return line.encode("ascii", "backslashreplace").decode("ascii")


def _say(line: str) -> None:
    """The ONLY print here."""
    print(_ascii(line))


class Finding:
    __slots__ = ("spec", "label", "detail")

    def __init__(self, spec: str, label: str, detail: str) -> None:
        self.spec, self.label, self.detail = spec, label, detail


def _grade(name: str, filename: str, text: str) -> list[Finding]:
    """The findings for ONE converged spec. `name` labels them; `filename` carries the date gate."""
    findings: list[Finding] = []
    if not URL_RE.search(text) and not NO_EXTERNAL_RE.search(text):
        findings.append(
            Finding(
                name,
                "SILENT-1a",
                "no cited source and no 'no external facts' statement - "
                "indistinguishable from skipping the research gate",
            )
        )
    if not RESIDUAL_RE.search(text):
        findings.append(
            Finding(name, "NO-RESIDUAL", "converged without enumerating residual unknowns")
        )

    m = SPEC_DATE_RE.match(filename)
    if m and m.group(1) >= FLOOR_CUTOFF:
        distinct_urls = set(URL_RE.findall(text))
        if len(distinct_urls) < FLOOR_MIN_URLS:
            findings.append(
                Finding(
                    name,
                    "APPROACH-FLOOR",
                    f"{len(distinct_urls)} distinct cited URL(s) < {FLOOR_MIN_URLS} — the 1c "
                    "approach floor. 'Purely internal' waives 1a facts, NEVER the approach "
                    "research: every design shape has a field practice to consult (the "
                    "self-exemption class, 2026-08-30)",
                )
            )
    if m and m.group(1) >= FLOOR_CUTOFF:
        if not PERSONAS_HEAD_RE.search(text):
            findings.append(
                Finding(
                    name,
                    "NO-PERSONAS",
                    "no '## Personas' - WHO consumes this (incl. automated actors) and which "
                    "role holds each duty is a mandated section (interrogative floor, "
                    "2026-08-30)",
                )
            )
        if not LIFECYCLE_HEAD_RE.search(text):
            findings.append(
                Finding(
                    name,
                    "NO-LIFECYCLE",
                    "no '## Lifecycle' - WHEN: adoption, growth with measured triggers, "
                    "retirement. The growth question operators always ask and specs never "
                    "answer (interrogative floor, 2026-08-30)",
                )
            )
    if m and m.group(1) >= INTAKE_CUTOFF:
        if not INTAKE_HEAD_RE.search(text):
            findings.append(
                Finding(
                    name,
                    "NO-INTAKE",
                    "no '## Intake Inventory' - the conversation's items are this spec's "
                    "denominator; without the table, silent subsetting is invisible "
                    "(chat-intake contract, 2026-08-29)",
                )
            )
        else:
            hollow = sum(
                1 for row in INTAKE_ROW_RE.findall(text) if not INTAKE_DISPO_RE.search(row)
            )
            if hollow:
                findings.append(
                    Finding(
                        name,
                        "HOLLOW-INTAKE",
                        f"{hollow} inventory row(s) with no IN/OUT-OF-SCOPE/ASK disposition - "
                        "an undecided row is a silent drop wearing a table",
                    )
                )
    return findings


def _audit(root: Path) -> tuple[int, list[Finding]]:
    """Return (CONVERGED specs examined, findings). Never raises for a per-file problem."""
    try:
        paths = sorted(p for p in (root / SPECS_DIR).glob("*.md") if p.is_file())
    except OSError:
        return 0, []

    examined = 0
    findings: list[Finding] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not CONVERGED_RE.search(text):
            continue  # DRAFT/PLANNED/absent: being incomplete is what those states MEAN
        examined += 1
        findings.extend(_grade(path.name, path.name, text))
    return examined, findings


def _audit_named(root: Path, named: list[str]) -> tuple[int, int, list[Finding], list[str]]:
    """Grade only the NAMED files (a directory expands to its `*.md`), each counted once by its
    resolved path. Returns (named, examined, findings, notes): every named path that was not graded
    — or graded without its date-gated rules — has a note, because a scoped run that drops a path
    silently reads like a clean verdict on it. Every probe is guarded PER PATH: one over-long
    argument (`OSError` from `is_dir`) is its own NOT-FOUND, never a lost census."""
    entries: list[tuple[str, Path]] = []
    seen: set[str] = set()
    notes: list[str] = []
    missing = 0

    def _add(label: str, path: Path) -> None:
        try:
            key = str(path.resolve())
        except (OSError, RuntimeError):
            key = str(path)
        if key not in seen:
            seen.add(key)
            entries.append((label, path))

    for arg in named:
        try:
            path = Path(arg)
            path = path if path.is_absolute() else root / path
            if path.is_dir():
                for f in sorted(x for x in path.glob("*.md") if x.is_file()):
                    _add(str(Path(arg) / f.name), f)
                continue
            if path.is_file():
                _add(arg, path)
                continue
            notes.append(f"NOT-FOUND: {arg}")
        except (OSError, ValueError) as exc:
            notes.append(f"NOT-FOUND: {arg[:80]} ({type(exc).__name__})")
        missing += 1

    examined = 0
    findings: list[Finding] = []
    for label, path in entries:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            notes.append(f"UNREADABLE: {label} ({type(exc).__name__})")
            continue
        if not CONVERGED_RE.search(text):
            notes.append(f"NOT-CONVERGED: {label} - a DRAFT is not graded")
            continue
        examined += 1
        if not SPEC_DATE_RE.match(path.name):
            notes.append(
                f"UNDATED: {label} - the date-gated rules were NOT applied; name the copy "
                "YYYY-MM-DD-<slug>.md like the spec it copies"
            )
        findings.extend(_grade(label, path.name, text))
    return len(entries) + missing, examined, findings, notes


def _emit(
    examined: int,
    findings: list[Finding],
    *,
    named: int | None,
    notes: list[str],
    unbudgeted: bool,
) -> None:
    """Print the census and the findings. `named` is None for the repo-wide audit, which says
    nothing at all when no CONVERGED spec exists; a scoped run always prints its census."""
    if named is None and examined == 0:
        return
    census = (
        f"spec convergence: {examined} CONVERGED spec(s) examined"
        + (f" of {named} named" if named is not None else "")
        + f", {len({f.spec for f in findings})} with findings ({CENSUS_NOTE})"
    )
    _say(census)
    for note in notes:
        _say(f"  {note}")
    if not findings:
        return
    if unbudgeted:
        for f in findings:
            _say(f"  {f.label}: {f.spec} {f.detail}".rstrip())
        _say(f"  -> {REMEDY}")
        return

    # The marker is CHARGED UP FRONT, at its largest (every finding hidden). Paying for it out of the
    # remainder is how a sibling check lost its REMEDY line mid-word. Every length below is counted
    # on the ASCII-escaped line `_say` actually prints, and the FIRST line is cut to the room left
    # instead of printed whole — both overran the budget before W-7cdad5d5.
    marker_cost = len(MARKER.format(n=len(findings))) + 1
    budget = ADVISORY_BUDGET - (len(_ascii(census)) + 1) - (len(REMEDY) + 6) - marker_cost
    emitted = 0
    for f in findings:
        if emitted >= MAX_LINES - 3:
            break
        line = _ascii(f"  {f.label}: {f.spec} {f.detail}".rstrip())
        if len(line) > MAX_LINE:
            line = line[: MAX_LINE - 3] + "..."  # exactly MAX_LINE, not MAX_LINE + 2
        if budget - (len(line) + 1) < 0:
            room = budget - 1
            if emitted or room < 8:
                break
            line = line[: room - 3] + "..."
        print(line)
        budget -= len(line) + 1
        emitted += 1
    if emitted < len(findings):
        _say(MARKER.format(n=len(findings) - emitted))
    _say(f"  -> {REMEDY}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Advisory: a CONVERGED spec must show its work.")
    parser.add_argument("--root", default=".", help="repo root to audit (default: cwd)")
    parser.add_argument(
        "--all", action="store_true", help="print every finding (no budget) for the whole repo"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="grade only these spec files or directories (unbudgeted, an 'of N named' census)",
    )
    # parse_KNOWN_args INSIDE the guard: argparse calls `sys.exit(2)` on a bad flag and `SystemExit`
    # derives from BaseException, so `except Exception` would not catch it — the exact hole that made
    # a sibling warn_only check exit 2 (fixed 2026-08-27). INTERMIXED, so `a.md --all b.md` keeps b.md.
    # The emit phase sits inside the guard too: `--all | head` closes stdout early, and a
    # BrokenPipeError traceback is a non-zero exit (W-7cdad5d5).
    try:
        args, unknown = parser.parse_known_intermixed_args(argv)
        root = Path(args.root)
        if args.paths:
            named, examined, findings, notes = _audit_named(root, args.paths)
            notes += [f"IGNORED: {tok[:80]}" for tok in unknown]
            _emit(examined, findings, named=named, notes=notes, unbudgeted=True)
        else:
            examined, findings = _audit(root)
            _emit(examined, findings, named=None, notes=[], unbudgeted=args.all)
    except SystemExit:
        return 0
    except Exception as exc:  # the CLASS, never an enumerated list of types
        try:
            _say(f"could not evaluate spec convergence: {type(exc).__name__}")
        except Exception:  # pragma: no cover - stdout itself is broken; stay silent, stay 0
            pass
        return 0
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
