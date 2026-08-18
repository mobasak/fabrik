#!/usr/bin/env python3
"""Coverage-checklist gate — run by final_gate via run_optional_check (non-zero = fail).

Companion to check_convergence.py for the coverage-adjudicated review commands
(/fabrik-review, /fabrik-repo-review). A review artifact that claims the exit must
prove FULL adjudication of its Coverage Checklist. Inspects only changed/untracked
files under docs/development/reviews/ (git status + regex; safe every tier).

A changed reviews/*.md containing a "Coverage Checklist" table:
  -> every checklist row must carry a verdict: CLEAN / FIXED / REFUTED.
  -> zero UNCHECKED rows. (There is NO cap-stop / "Declared residual" bypass —
     the Termination contract has no round ceiling; the only pause is a
     per-finding 3-attempts BLOCKED escalation. A prior docstring advertised a
     cap-stop the contract never allowed — a live run cited it to close a loop
     on a spot-verify round.)
  -> the standing recurrence classes must appear as rows (fail-open,
     cost/quota accounting, boundary/sentinel, behavior-without-a-test).
A changed reviews/*.md that names /fabrik-review or /fabrik-repo-review as its
command but has NO Coverage Checklist -> fail (the contract requires emitting it).

Ceiling (by design): enforces checklist *presence and complete adjudication* —
never that the hunting behind a CLEAN verdict was good. Artifacts from the
edit-convergence commands (spec/plan/contract reviews) carry no Coverage
Checklist and are not this gate's subject (check_convergence.py covers them).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REVIEWS_DIR = "docs/development/reviews/"

CHECKLIST_HEAD = re.compile(r"coverage checklist", re.I)
COMMAND_MARK = re.compile(r"/fabrik-(?:repo-)?review\b")
VERDICT = re.compile(r"\b(CLEAN|FIXED\s*\(?\d*\)?|REFUTED)\b")
UNCHECKED = re.compile(r"\bUNCHECKED\b")
BLOCKED_HEAD = re.compile(r"^#{2,4}\s*.*BLOCKED", re.M)
RECURRENCE = {
    "fail-open/fail-closed": re.compile(r"fail[- ]open", re.I),
    "cost/quota accounting": re.compile(r"\b(cost|quota|limit)\b", re.I),
    "boundary/sentinel/prefix": re.compile(r"\b(boundary|sentinel|prefix)\b", re.I),
    "behavior-without-a-test": re.compile(
        r"behavior[- ]without[- ]a[- ]test|untested behavior", re.I
    ),
}


def _changed_md(root: Path, prefix: str) -> list[Path]:
    """Changed/untracked .md under ``prefix`` (git status), excluding archived/."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", prefix],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    paths = []
    for line in out.splitlines():
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        if not (rel.endswith(".md") and "archived/" not in rel and (root / rel).is_file()):
            continue
        # Shared-master: '??' = untracked AND unstaged — a sibling session's (or a
        # not-yet-staged) in-flight draft. The checklist is enforced at the
        # staging/commit moment, never against another agent's mid-write scratch.
        if line[:2] == "??":
            print(f"NOTE: skip untracked in-flight draft (checked at staging): {rel}")
            continue
        paths.append(root / rel)
    return paths


def _table_rows(section: str) -> list[str]:
    """Data rows of the FIRST contiguous markdown table in ``section`` (skips
    header + rule). Stops at the first non-table line so a Pass Ledger emitted
    under the same heading is never mistaken for checklist rows."""
    rows: list[str] = []
    in_table = False
    for line in section.splitlines():
        if line.lstrip().startswith("|"):
            rows.append(line)
            in_table = True
        elif in_table:
            break
    return list(rows[2:]) if len(rows) >= 3 else []


def _checklist_section(text: str) -> str | None:
    m = None
    for h in re.finditer(r"^#{2,4} .*$", text, re.M):
        if CHECKLIST_HEAD.search(h.group(0)):
            m = h
            break
    if m is None:
        # table introduced without its own heading — fall back to the first
        # table that follows the phrase "Coverage Checklist" anywhere.
        i = text.lower().find("coverage checklist")
        return text[i:] if i != -1 else None
    nxt = re.search(r"^#{2,4} ", text[m.end() :], re.M)
    return text[m.start() : m.end() + (nxt.start() if nxt else len(text))]


# ⚠️ Bold-tolerant. This was `^Surface:\s*\S+`, which a markdown-natural `**Surface:** <hash>` does
# not match — and the failure text said "no `Surface:` hash line", i.e. ABSENT, when the line was
# right there. A checker that reports the wrong reason costs more than one that reports nothing.
# Leading whitespace stays disallowed on purpose: the contract wants this line at column 0, where a
# cross-run anchor is greppable.
SURFACE = re.compile(r"^\**Surface:\**\s*\S+", re.M)

# An honest IN-PROGRESS review. The /fabrik-review methodology requires the report to exist BEFORE
# pass 1 ("a review that exists only in chat does not exist"), while every other rule here treats a
# persisted report as one that must already be converged. Those two cannot both hold, and the gap
# was being worked around by holding the report uncommitted across passes — which is precisely the
# state this file cannot see. Declaring the status makes the in-progress case legal and VISIBLE,
# instead of hidden in someone's working tree.
IN_PROGRESS = re.compile(r"^\**Status:\**\s*IN-PROGRESS\b", re.M | re.I)
PASS2 = re.compile(r"\bPass\s*2\b")
RUBRIC_RUN = re.compile(r"review_rubric\.py")
_PATHISH = re.compile(r"[\w-]+[./][\w./-]+")


def check_file(p: Path) -> list[str]:
    errs: list[str] = []
    text = p.read_text(encoding="utf-8", errors="replace")
    section = _checklist_section(text)
    if section is None:
        if COMMAND_MARK.search(text):
            errs.append(
                "names /fabrik-review or /fabrik-repo-review but emits NO Coverage Checklist"
            )
        return errs
    # contract obligations recorded in the artifact itself
    if not SURFACE.search(text):
        errs.append(
            "no `Surface:` hash line (cross-run anchor) — record `git rev-parse HEAD` + diff md5"
        )
    if not RUBRIC_RUN.search(text):
        errs.append(
            "no review_rubric.py invocation recorded — checklist classes must derive from the rubric, not memory"
        )
    if not PASS2.search(text):
        errs.append(
            "no `Pass 2` in the ledger — minimum two rounds ALWAYS (a clean pass 1 still needs its confirming round)"
        )
    rows = _table_rows(section)
    if not rows:
        errs.append("Coverage Checklist has no table rows")
        return errs
    blocked_ok = bool(BLOCKED_HEAD.search(text)) and bool(
        re.search(r"3\b.{0,40}attempt|attempt.{0,40}\b3\b|three (?:consecutive|failed)", text, re.I)
    )
    unchecked = [r.strip() for r in rows if UNCHECKED.search(r)]
    noverdict = [r.strip() for r in rows if not UNCHECKED.search(r) and not VERDICT.search(r)]
    if unchecked and not blocked_ok:
        errs.append(
            f"{len(unchecked)} UNCHECKED row(s) with no ## BLOCKED escalation (finding + 3 failed attempts): {unchecked[:3]}"
        )
    if noverdict:
        errs.append(
            f"{len(noverdict)} row(s) without a CLEAN/FIXED/REFUTED verdict: {noverdict[:3]}"
        )
    bare = [
        r.strip()
        for r in rows
        if re.search(r"\bCLEAN\b", r) and not _PATHISH.search(r) and len(r.strip()) < 70
    ]
    if bare:
        errs.append(
            f"{len(bare)} CLEAN row(s) without evidence (name the files/paths hunted): {bare[:3]}"
        )
    # ⚠️ Read LEDGER ROWS, not every "found:" in the file. This was `findall(r"found:\s*(\d+)")`
    # taking the LAST match anywhere — so a prose line after the ledger ("cumulative found: 70",
    # or a quoted example) silently became "the final round", in either direction: it could
    # manufacture a failure, or mask a real non-quiet exit with a stray `found: 0`.
    # A ledger row always carries BOTH counters, which is what distinguishes it from prose.
    rows_with_both = re.findall(r"found:\s*(\d+)\s*(?:,|·|\|)?\s*fixed:\s*\d+", text)
    founds = rows_with_both or re.findall(r"found:\s*(\d+)", text)
    if founds and int(founds[-1]) != 0 and not blocked_ok and not IN_PROGRESS.search(text):
        errs.append(
            f"final ledger round raised {founds[-1]} (refuted counts as found) — the exit round must be quiet, or the stuck finding must be BLOCKED-escalated (named + 3 failed attempts), or the report must declare `Status: IN-PROGRESS`"
        )
    body = "\n".join(rows)
    missing = [name for name, pat in RECURRENCE.items() if not pat.search(body)]
    if missing:
        errs.append(f"standing recurrence class(es) missing from checklist: {missing}")
    return errs


# --- Certification disposition gate (user-test / service-test reports) ---------
# Grammar (defined in the gauntlets' "Report + chain" sections):
#   HANDOFF P<0-3> OPEN <desc> — repro: <path> — route: <command>
#   HANDOFF P<0-3> CLOSED <desc> — repro: <path> — proof: <green-run one-liner>
#   DESIGN-GAP <desc> — brief: <path>            (operator decision; may stay open)
# Rules (zero-false-positive by design — only rows using the grammar are parsed):
#   CLOSED without an existing repro path or without proof:  FAIL
#   OPEN routed to /fabrik-review (code-wrong) without evidence:  FAIL
#   any OPEN row  -> report must carry NOT-QUIET marker AND a ## RESUME section
#   NOT-QUIET marker -> ## RESUME required
CERT_REPORT = re.compile(r"-(user|service)-test-.*\.md$")

# --- Mega cross-epic validation reports (fab-mega-04-validate) ---------------------------------
# Third grammar. Until 2026-08-16 mega-04's report went ONLY to Telegram, so its exit was read by
# no gate at all. The first version of this grammar was itself reviewed (2026-08-18) and lost —
# every rule below carries the scar of a reproduced defeat:
#   * H1 anchored to the FILE START (`\A`), because an `re.M` content match routed ANY review file
#     that merely QUOTED the template (even in a fence) away from the checklist gate.
#   * Ledger rows are TABLE LINES ONLY, because a whole-text `found:` scan took a prose sentence
#     after the table as "the final round" — the exact LAST-match defect check_file() above had
#     already been fixed for, reintroduced one grammar over.
#   * Hashes are FULL (≥12 hex), CHAINED (round N's end == round N+1's start), ANCHORED
#     (`Surface:` == the final round's end) and — on the blocking, diff-scoped path — RECOMPUTED
#     against the live epic set, because a text-only grammar was defeated by typing any two
#     identical strings; `2026 -> 2026` (a year) passed as an "unmoved hash".
#   * `Status: IN-PROGRESS` counts only in the report's HEADER ZONE, because an unanchored match
#     accepted the escape hatch quoted inside a fence.
#   * Placeholders are hunted on FENCE-STRIPPED text, so a meta-report quoting the template does
#     not fail, while a real `[PASS]` on a lens line still does.
# Routing is two-keyed and FAIL-CLOSED: the H1 (which may carry a vision suffix — the natural
# title for a file named `…-mega-<vision-slug>-validation-review.md`) OR the reserved filename
# suffix. v2 demanded a byte-exact H1 as the file's first line, so `# Cross-Epic Validation
# Report — Project X` fell through EVERY gate (mega, checklist, cert) and exited green with a
# non-quiet ledger and live placeholders — reproduced. The filename key means a mega-shaped
# name can never route to a weaker grammar, whatever its title says.
MEGA_REPORT_H1 = re.compile(r"\A#\s+Cross-Epic Validation Report\b")
MEGA_FILENAME = re.compile(r"-validation-review\.md$")


def _is_mega_report(path: Path, text: str) -> bool:
    return bool(MEGA_REPORT_H1.match(text.lstrip("\ufeff\n"))) or bool(
        MEGA_FILENAME.search(path.name)
    )
_MEGA_PLACEHOLDERS = ("[PASS]", "[FAIL]", "[N]", "[M]", "[list]", "[none / list]")
_MEGA_HEX = r"[0-9a-fA-F]{32}"  # FULL md5, exactly — the doc mandates all 32; 12-char "full-ish" let truncation pass wherever the live recompute is skipped
_MEGA_HASH_PAIR = re.compile(rf"({_MEGA_HEX})\s*(?:→|->)\s*({_MEGA_HEX})")
# A ledger row is a markdown TABLE line carrying both counters — and the ledger is the FIRST
# contiguous table that contains any such row. v2 matched counter rows ANYWHERE, so a later
# `## Per-lens tally` table with a quiet row silently became "the final round", masking a
# non-quiet exit — the LAST-match defect's THIRD appearance in this file, one table over.
_MEGA_ROW = re.compile(r"^\s*\|.*?found:\s*(\d+).*?fixed:\s*(\d+).*$")


def _mega_ledger_rows(body: str) -> list[tuple[int, int, str]]:
    rows: list[tuple[int, int, str]] = []
    in_table = started = False
    for line in body.splitlines():
        if line.lstrip().startswith("|"):
            in_table = True
            m = _MEGA_ROW.match(line)
            if m:
                started = True
                rows.append((int(m.group(1)), int(m.group(2)), line))
        elif in_table:
            if started:
                break  # the ledger table ended; later tables are NOT the ledger
            in_table = False
    return rows
_MEGA_SURFACE = re.compile(rf"^\**Surface:\**\s*({_MEGA_HEX})\b", re.M)  # no $: a trailing annotation is not absence (the wrong-reason class, third sighting)
_FENCE = re.compile(r"^```.*?^```\s*$", re.M | re.S)


def _strip_fences(text: str) -> str:
    return _FENCE.sub("", text)


def epics_set_hash(root: Path) -> str | None:
    """The Step-3 anti-cheat hash, byte-identical to the doc's shell pipeline.

    `find docs/development/epics -name '*.md' -print0 | sort -z | xargs -0 md5sum | md5sum` —
    md5sum emits `<hex>  <path>\\n` (TWO spaces) per file with the path exactly as find printed
    it; the outer md5 is over that text. Reproducing the byte format matters: an approximated hash that
    "means the same" would never match what the agent recorded from the real command.
    """
    import hashlib  # noqa: PLC0415

    epics = root / "docs" / "development" / "epics"
    if not epics.is_dir():
        return None
    # BYTE order (LC_ALL=C), matching the doc's pipeline which now pins `LC_ALL=C sort -z`.
    # Locale collation diverges from codepoint order on case ('Alpha' vs 'alpha') and on
    # punctuation-vs-slash in nested paths ('sub/a.md' vs 'sub-x.md') — both reproduced turning
    # an HONEST report red with "the recorded hash was never computed", the most demoralizing
    # possible false accusation. Python str sort == byte sort for ASCII paths; epic naming is
    # gate-enforced ASCII kebab-case.
    files = sorted(
        str(p.relative_to(root)) for p in epics.rglob("*.md") if p.is_file()
    )
    if not files:
        return None  # an empty epic set validates nothing — no anchor, not a fabricated one
    lines = []
    for rel in files:
        h = hashlib.md5((root / rel).read_bytes()).hexdigest()  # noqa: S324 — integrity, not crypto
        lines.append(f"{h}  {rel}\n")
    return hashlib.md5("".join(lines).encode()).hexdigest()  # noqa: S324


def check_mega_validation(
    path: Path, root: Path, live: bool = True, scope: str = "full"
) -> list[str]:
    """The persisted mega-04 report must PROVE its adjudicated exit, not assert it.

    ``live=True`` (the blocking, diff-scoped path) additionally recomputes the epic-set hash from
    disk — the report just changed, so the tree IS the validation-time state and must match.
    ``live=False`` (the advisory committed scan) skips the recompute: epics legitimately drift
    during execution, and nagging every historical report forever is how an advisory gets muted.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    body = _strip_fences(text)
    # The sanctioned mid-loop state — declared in the HEADER ZONE (first 10 non-fence lines),
    # where the template puts Status, not quotable from anywhere in the body.
    header = "\n".join(body.splitlines()[:10])
    if IN_PROGRESS.search(header):
        return []
    errs: list[str] = []
    surface = _MEGA_SURFACE.search(body)
    if surface is None:
        errs.append(
            "no `Surface:` line carrying a FULL hash (≥12 hex) — record the final SET hash from "
            "the Step-3 anti-cheat (`find docs/development/epics -name '*.md' … | md5sum`), "
            "untruncated; `TBD`, prose, or a truncated stub do not anchor anything"
        )
    rows = _mega_ledger_rows(body)
    if len(rows) < 2:
        errs.append(
            f"ledger table records {len(rows)} round(s) — minimum two full rounds, ALWAYS, as "
            "TABLE rows carrying `found:` and `fixed:` (prose mentions do not count)"
        )
    if rows:
        f_found, f_fixed, f_line = rows[-1]
        if f_found != 0 or f_fixed != 0:
            errs.append(
                f"final ledger round reads found: {f_found}, fixed: {f_fixed} — the exit round "
                "must be quiet in BOTH counters (a fix in the final round means the round that "
                "changed the set called itself the no-op), or declare `Status: IN-PROGRESS` "
                "within the report's FIRST 10 LINES (the template's slot is line 3)"
            )
        pairs = [_MEGA_HASH_PAIR.search(line) for _, _, line in rows]
        if pairs[-1] is None:
            errs.append(
                "final ledger round carries no full `md5(start) → md5(end)` pair (≥12 hex each) "
                "— the hash equality IS the proof the exit round was edit-free"
            )
        else:
            start_h, end_h = pairs[-1].group(1).lower(), pairs[-1].group(2).lower()
            if start_h != end_h:
                errs.append(
                    f"final round's hashes moved ({start_h[:8]}… → {end_h[:8]}…) — the set was "
                    "edited in the round that claims to be the no-op; run the next round"
                )
            if surface is not None and surface.group(1).lower() != end_h:
                errs.append(
                    "`Surface:` does not equal the final round's md5(end) — the anchor must BE "
                    "the hash the exit round ended on, not an unrelated value"
                )
        # Adjacent-round chaining: round N ends where round N+1 starts, or a round's edits were
        # made off the books between reviews.
        for i in range(len(pairs) - 1):
            a, b = pairs[i], pairs[i + 1]
            if a is not None and b is not None and a.group(2).lower() != b.group(1).lower():
                errs.append(
                    f"round {i + 1} ended at {a.group(2).lower()[:8]}… but round {i + 2} started "
                    f"at {b.group(1).lower()[:8]}… — the set changed BETWEEN reviewed rounds"
                )
    if live and surface is not None:
        live_hash = epics_set_hash(root)
        if live_hash is not None and live_hash != surface.group(1).lower():
            errs.append(
                f"the epic set on disk hashes to {live_hash[:12]}… but the report anchors "
                f"{surface.group(1).lower()[:12]}… — the set changed after validation (your own "
                "follow-up, or a sibling session's edit — this tree runs several agents), or the "
                "hash was not computed. Re-run fab-mega-04-validate against the current set, or "
                "mark the report `Status: IN-PROGRESS` (first 10 lines) until you do"
            )
    leftover = [p for p in _MEGA_PLACEHOLDERS if p in body]
    if leftover:
        errs.append(
            f"template placeholder(s) survived into the persisted report: {leftover} — a "
            "placeholder is a lens nobody adjudicated wearing a verdict's clothes"
        )
    if scope == "exit":
        # The committed advisory scan's contract is NARROW by design (see _committed_nonquiet's
        # docstring): only the exit-round conditions. Everything else — Surface presence, hash
        # length, round minimums, placeholders — stays a blocking-path obligation, or the
        # advisory nags every historical report forever and gets muted.
        keep = ("final ledger round reads", "hashes moved")
        errs = [e for e in errs if any(k in e for k in keep)]
    return errs
HANDOFF_ROW = re.compile(r"^\s*[-*]?\s*HANDOFF\s+P([0-3])\s+(OPEN|CLOSED)\b(.*)$", re.M)
REPRO_IN_ROW = re.compile(r"repro:\s*([\w./-]+)")
PROOF_IN_ROW = re.compile(r"proof:\s*\S")
CODE_WRONG_ROUTE = re.compile(r"route:\s*/fabrik-review\b")
EVIDENCE_IN_ROW = re.compile(r"evidence:\s*\S")
NOT_QUIET = re.compile(r"NOT-QUIET")
RESUME_HEAD = re.compile(r"^##\s+RESUME\b", re.M)


def check_cert_dispositions(path: Path, root: Path) -> list[str]:
    """Disposition rows in a certification report must be provable, not prose."""
    text = path.read_text(encoding="utf-8", errors="replace")
    errs: list[str] = []
    rows = HANDOFF_ROW.findall(text)
    open_rows = [r for r in rows if r[1] == "OPEN"]
    for _sev, state, rest in rows:
        m = REPRO_IN_ROW.search(rest)
        if state == "CLOSED":
            if not m:
                errs.append(f"CLOSED HANDOFF row lacks a repro: path — {rest.strip()[:60]}")
            elif not (root / m.group(1)).is_file():
                errs.append(f"CLOSED HANDOFF cites a repro that does not exist: {m.group(1)}")
            if not PROOF_IN_ROW.search(rest):
                errs.append(f"CLOSED HANDOFF row lacks proof: — {rest.strip()[:60]}")
        elif CODE_WRONG_ROUTE.search(rest) and not EVIDENCE_IN_ROW.search(rest):
            errs.append(
                "OPEN code-wrong HANDOFF row lacks evidence: (wire/state proof of attribution — "
                f"a red repro alone can be rig-defective) — {rest.strip()[:60]}"
            )
    if open_rows:
        if not NOT_QUIET.search(text):
            errs.append(
                f"{len(open_rows)} OPEN HANDOFF row(s) but the ledger is not marked "
                "NOT-QUIET (routes outstanding) — a truncated run may never present itself as quiet"
            )
        if not RESUME_HEAD.search(text):
            errs.append(f"{len(open_rows)} OPEN HANDOFF row(s) but no ## RESUME section")
    if NOT_QUIET.search(text) and not RESUME_HEAD.search(text):
        errs.append("ledger marked NOT-QUIET but no ## RESUME section names the outstanding rows")
    return errs


def _committed_nonquiet(root: Path, skip: set[Path]) -> list[str]:
    """Reports that are COMMITTED and still record a non-quiet exit round.

    ⚠️ The hole this closes: every other obligation here is scoped to `git status`, which is right
    for the common case — re-proving every historical report on every gate run is noise nobody
    reads. But it means a report is only ever checked while UNCOMMITTED, and the documented
    workflow is write-report → commit-with-fixes → run-gate. By then it is invisible, so
    **committing an unconverged review was enough to pass the check that polices reviews** —
    green-by-absence inside the check whose whole job is refusing green-by-absence.

    Deliberately narrow: only the exit-round condition, never the full obligation set. Demanding a
    `Surface:` line or a rubric invocation from every report ever written would retro-grade history
    across ~46 synced repos and get this check disabled — and a disabled check protects nothing.
    Measured before shipping: 0 of 49 existing hub reports are flagged by this.
    """
    out: list[str] = []
    for p in sorted((root / REVIEWS_DIR).rglob("*.md")):
        if p in skip or "archived/" in str(p.relative_to(root)):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        # Mega validation reports have their OWN grammar and no Coverage Checklist — the
        # checklist filter below skipped them entirely, so a committed unconverged mega report
        # was invisible here, re-opening this function's founding hole one grammar over
        # (found 2026-08-18, the day the grammar shipped). live=False: epics legitimately
        # drift during execution, so the committed scan checks the TEXTUAL contract only.
        if _is_mega_report(p, text):
            # scope="exit" honors this function's documented narrowness: only the quiet-exit +
            # moved-hash conditions, never the full obligation set — demanding Surface/rounds/
            # placeholders of every historical report forever is the muting mechanism the
            # docstring above names (closing-sweep finding, 2026-08-19).
            for e in check_mega_validation(p, root, live=False, scope="exit"):
                out.append(f"{p.relative_to(root)}: COMMITTED mega report — {e}")
            continue
        if _checklist_section(text) is None or IN_PROGRESS.search(text):
            continue
        if BLOCKED_HEAD.search(text):
            continue
        rows = re.findall(r"found:\s*(\d+)\s*(?:,|·|\|)?\s*fixed:\s*\d+", text)
        if rows and int(rows[-1]) != 0:
            out.append(
                f"{p.relative_to(root)}: COMMITTED with a non-quiet exit round (found: {rows[-1]}) "
                "— committing a review does not converge it. Finish the loop, BLOCKED-escalate the "
                "stuck finding, or mark the report `Status: IN-PROGRESS`."
            )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    failures: list[str] = []
    changed = _changed_md(root, REVIEWS_DIR)
    # ⚠️ ADVISORY, not a failure — and the asymmetry is deliberate. The hole was that a committed
    # unconverged review was INVISIBLE; printing it fixes that. Hard-failing it would retro-grade
    # every historical report across ~46 synced repos on the next sync, on artifacts whose authors
    # may not even be active — and a gate that reds someone's unrelated commit is a gate that gets
    # switched off (the death this corpus has already seen once, with check_doc_sprawl).
    # The BLOCKING path stays where the author can still act: the report in their working tree.
    stale = _committed_nonquiet(root, skip=set(changed))
    if stale:
        print("check_review_coverage: ADVISORY — committed review(s) still recording a non-quiet exit:")
        for s in stale:
            print(f"  ⚠ {s}")
    for p in changed:
        # \A-anchored: the H1 must be the FILE'S FIRST LINE. A content-anywhere match let any
        # review file that merely QUOTED the template (even fenced) route here and skip the
        # checklist gate it actually owed — reproduced 2026-08-18.
        if _is_mega_report(p, p.read_text(encoding="utf-8", errors="replace")):
            for e in check_mega_validation(p, root, live=True):
                failures.append(f"{p.relative_to(root)}: {e}")
            continue  # a mega validation report is exit-proof-gated, not checklist-gated
        if CERT_REPORT.search(p.name):
            for e in check_cert_dispositions(p, root):
                failures.append(f"{p.relative_to(root)}: {e}")
            continue  # a certification report is disposition-gated, not checklist-gated
        for e in check_file(p):
            failures.append(f"{p.relative_to(root)}: {e}")
    if failures:
        print("Coverage-checklist gate FAILED:")
        for f in failures:
            print(f"  - {f}")
        print(
            "A coverage-adjudicated review exits only on a fully-adjudicated checklist "
            "— there is no cap-stop; a spot-verify of fixes is the re-check step, never the closing round."
        )
        return 1
    print("check_review_coverage: OK (no unproven coverage claims in changed review artifacts)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
