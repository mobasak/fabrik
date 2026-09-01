#!/usr/bin/env python3
# AFTER-EDIT: scripts/enforcement/check_convergence.py | tests/enforcement/test_mega_validation_reports.py | tests/enforcement/test_review_exit_contract.py | tests/test_check_review_coverage_rederivation.py
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

# Anchored to the heading's START (round 29): a bare substring made `## Non-coverage checklist
# items` a subject. A heading that BEGINS "Coverage Checklist" — including "(deferred)" variants —
# is gated on purpose: deferring the checklist is precisely what the gate refuses.
CHECKLIST_HEAD = re.compile(r"^#{1,4}\s+\**coverage checklist\b", re.I)
# RETIRED as a subject test (round 27) — kept only as documentation of what NOT to reintroduce:
# a command-name substring is a proxy for "is this a review report" that fails both directions
# (prose explaining the process trips it; a paraphrasing report escapes it). Subject-ness is the
# checklist HEADING; artifact-emission enforcement is the run-record's moment.
COMMAND_MARK = re.compile(r"/fabrik-(?:repo-)?review\b")  # noqa: F841 — retired, see above
# ROUTED(n) (trade-intelligence feedback 01M0Q4ZJFEAMNABM7RZ5KQPW4E, first live
# /fabrik-conformance-review run): gate-stage commands whose Phase-3 contract is
# ROUTE-not-fix had no honest terminal token — authors were forced to write
# "FIXED(n, via routing)" to parse. A routed finding is adjudicated, not open.
VERDICT = re.compile(r"\b(CLEAN|FIXED\s*\(?\d*\)?|REFUTED|ROUTED\s*\(?\d*\)?)\b")
UNCHECKED = re.compile(r"\bUNCHECKED\b")
BLOCKED_HEAD = re.compile(r"^#{2,4}\s*.*BLOCKED", re.M)
RECURRENCE = {
    "fail-open/fail-closed": re.compile(r"fail[- ]open", re.I),
    "cost/quota accounting": re.compile(r"\b(cost|quota|limit)\b", re.I),
    # DELIBERATELY a bare-word match, and it must stay that way — measured 2026-09-01.
    # An author-blind finder proposed anchoring this on the slashed class label
    # ("boundary/sentinel") to close a theoretical fail-open where a finding's rationale
    # ("the fix moves a boundary") could certify a class nobody hunted. A corpus sweep of
    # the review archive REFUTED the fix: 8 of 39 reports mentioning the class label it
    # legitimately as "Boundary / incomplete-validation" or "Fail-open/fail-closed +
    # boundary", and the stricter regex fails all 8. The theoretical exploit also needs a
    # FINDING row misfiled into the Coverage-Checklist section (this scans `_table_rows`
    # of that section only) — a different, more visible defect. Bare word stays.
    "boundary/sentinel/prefix": re.compile(r"\b(boundary|sentinel|prefix)\b", re.I),
    "behavior-without-a-test": re.compile(
        r"behavior[- ]without[- ]a[- ]test|untested behavior", re.I
    ),
}


def _changed_md(root: Path, prefix: str) -> tuple[list[Path], list[str], list[Path]]:
    """Changed/untracked .md under ``prefix`` (git status), excluding archived/.

    Returns (paths, notes) — NOTE lines are RETURNED, not printed: round 25 reproduced a NOTE
    printing before the ⚠-first advisory header, which broke final_gate's startswith("⚠")
    opt-in and silently re-hid the whole advisory payload from --json whenever an untracked
    draft co-occurred with a committed advisory. Print order is part of the emitter protocol;
    only main() may decide it.
    """
    notes: list[str] = []
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", prefix],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [], notes, []
    paths = []
    untracked: list[Path] = []
    for line in out.splitlines():
        rel = line[3:].split(" -> ")[-1].strip().strip('"')
        if not (rel.endswith(".md") and "archived/" not in rel and (root / rel).is_file()):
            continue
        # Shared-master: '??' = untracked AND unstaged — a sibling session's (or a
        # not-yet-staged) in-flight draft. The checklist is enforced at the
        # staging/commit moment, never against another agent's mid-write scratch.
        if line[:2] == "??":
            notes.append(f"NOTE: skip untracked in-flight draft (checked at staging): {rel}")
            untracked.append(root / rel)
            continue
        paths.append(root / rel)
    return paths, notes, untracked


def _table_rows(section: str) -> list[str]:
    """ALL visible data rows in the checklist section (round 85).

    The first-contiguous-run contract predated the blanking rule: a quoted region (fence or
    comment) inside the table becomes blank lines, and the old break-at-first-non-pipe
    truncated extraction there — every row AFTER the seam (UNCHECKED ones included) went
    silently uncounted, a clean fail-open bypass. The SECTION is the contract, not the run:
    every pipe-row under the checklist heading counts, with separator rows skipped anywhere
    and a header row skipped structurally (a row whose next pipe-row is its separator). A
    second same-section table (a Pass Ledger missing its own heading) now false-fires LOUD
    verdict errors instead of being silently confused — the remedy is its mandated heading.
    """
    # PHYSICAL adjacency for the header test (round 87): looking ahead in the FILTERED pipe
    # list let a stray separator-shaped line anywhere later in the section (a stale template
    # artifact, prose to a renderer) erase whichever row preceded it in pipe-order — a
    # no-nesting fail-open the parity and refusal nets never see. A row is a header only if
    # its separator is the literally next line.
    phys = section.splitlines()

    def _is_separator(row: str) -> bool:
        # The REAL GFM delimiter-row grammar, per cell (round 97): each cell is `:?-+:?`
        # with at least one hyphen — the coarse character-class test accepted `|::|::|`,
        # `| : | : |` and blank cells, forming a phantom header pair no renderer forms and
        # swallowing the row above. The rule is closed and fully specified; enforcing it
        # precisely ends the separator sub-chase definitionally.
        # Per-cell validation ONLY (round 101): GFM puts the pipe requirement on the HEADER
        # row, not the delimiter — a bare `---` IS a valid separator under a 1-column
        # pipe-bounded header (renderer-verified), and round 100's pipe-presence gate here
        # false-failed exactly that honest shape. The setext/thematic ambiguity is carried
        # structurally by the callers: candidate rows are pipe-filtered before the
        # anywhere-skip, and the header pair only forms under a pipe-bounded header with
        # matching cell counts (`Title\n---` never pairs — Title carries no pipe).
        r = re.sub(r"\\\|", "\x00", row.strip())
        if r.startswith("|"):
            r = r[1:]
        if r.endswith("|"):
            r = r[:-1]
        cells = r.split("|")
        return bool(cells) and all(re.fullmatch(r"\s*:?-+:?\s*", c) for c in cells)

    def _cells(row: str) -> int:
        # GFM-faithful cell count (round 95): exactly ONE optional boundary pipe strips per
        # side — Python's strip("|") ate a DOUBLED leading pipe, collapsing a 3-cell typo'd
        # row onto a 2-cell separator ("match") and swallowing a live UNCHECKED row as a
        # header of a table no renderer forms; and `\|` is an ESCAPED pipe (content, not a
        # delimiter), whose naive split false-failed an honest vocabulary header.
        r = re.sub(r"\\\|", "\x00", row.strip())
        if r.startswith("|"):
            r = r[1:]
        if r.endswith("|"):
            r = r[:-1]
        return len(r.split("|"))

    out: list[str] = []
    for i, ln in enumerate(phys):
        if not ln.lstrip().startswith("|"):
            continue
        if _is_separator(ln):
            continue
        nxt = phys[i + 1].strip() if i + 1 < len(phys) else ""
        run_initial = i == 0 or not phys[i - 1].lstrip().startswith("|")
        if (
            run_initial
            and _is_separator(nxt)
            # GFM: the delimiter row must MATCH the header's cell count, or the whole block
            # is a plain PARAGRAPH — round 93 reproduced a 2-cell UNCHECKED row over a
            # 1-cell `|---|` being skipped as "the header" of a table no renderer sees,
            # silently exempting visible obligation text. Cell counts must agree for the
            # pair to be a real header.
            and _cells(ln) == _cells(nxt)
            # PIPED separators only (round 105): a bare `---` under a pipe-row is
            # AMBIGUOUS (setext underline / thematic-break divider / 1-column table
            # separator — GFM forms a real zero-body-row table, so round 104's
            # "requires continuation" premise was false, and a multi-item checklist
            # split by house-style `---` dividers silently dropped every item but the
            # last). The ambiguity is refused loudly by _indented_grammar_error before
            # any gate parses; here the pairing simply never forms without a pipe.
            and "|" in phys[i + 1]
        ):
            # The run's ONE header row — first pipe-row of its physical run, separator
            # literally next (round 89: adjacency alone let a stray separator swallow the
            # DATA row above it, chainably; run-initial kills the chain because every stray
            # separator is itself a pipe-row). The header's CONTENT is not judged (round 91):
            # an honest header naming the verdict vocabulary (`| Class | Verdict (CLEAN, …,
            # UNCHECKED) |`) false-failed converged reports, while an obligation deliberately
            # restructured INTO a header row is forgery — out of threat model, and visible to
            # the operator in the rendered table anyway. Two adjudicated residuals: that
            # forgery shape, and a pipe-row caption above the header (both rows then count
            # as data and fail LOUD noverdict errors — remedy: drop the caption).
            continue
        out.append(ln)
    return out


def _checklist_section(text: str) -> str | None:
    # FENCE-STRIPPED AT THE DEFINITION (round 41): round 39 patched ONE call site while the
    # three older, busier ones kept reading raw text — a fenced documentation example quoting
    # the heading false-BLOCKED an honest how-to doc with five fabricated obligations through
    # check_file. Per-call-site patching is the same per-reader-hardening root the breaker
    # named twice; stripping HERE means every caller (present and future) inherits, and the
    # returned section slice comes from stripped text, so fenced example rows inside a real
    # checklist are excluded from _table_rows as well.
    text = _strip_fences(text)
    m = None
    # #{1,4}: H1 included (round 29) — a report titling its checklist `# Coverage Checklist`
    # escaped every obligation, and no command source ever told authors which level to use.
    for h in re.finditer(r"^#{1,4} .*$", text, re.M):
        if CHECKLIST_HEAD.match(h.group(0)):
            m = h
            break
    if m is None:
        # HEADING-ONLY (round 27): the prose fallback ("coverage checklist" anywhere) was an
        # independent subject path — a convergence note merely DISCUSSING the concept was
        # hard-failed with four obligations it never owed. A checklist without its heading is
        # not a checklist; the /fabrik-review skeleton mandates the heading from pass 0.
        return None
    nxt = re.search(r"^#{2,4} ", text[m.end() :], re.M)
    return text[m.start() : m.end() + (nxt.start() if nxt else len(text))]


# ⚠️ Bold-tolerant. This was `^Surface:\s*\S+`, which a markdown-natural `**Surface:** <hash>` does
# not match — and the failure text said "no `Surface:` hash line", i.e. ABSENT, when the line was
# right there. A checker that reports the wrong reason costs more than one that reports nothing.
# Leading whitespace stays disallowed on purpose: the contract wants this line at column 0, where a
# cross-run anchor is greppable.
SURFACE = re.compile(r"^\**Surface:\**\s*\S+", re.M)

# ⚠️ ...and the SAME class again, one wrapper over: the bold fix above did not cover a markdown
# CODE SPAN, so `**Surface:** \`<40-hex>\`` — the most natural way to write a hash in markdown, and
# the form the contract's own guidance encourages — read as ABSENT to every hash-shaped matcher
# below. Measured 2026-09-01 on this repo's own corpus: 5 of 181 review artifacts were being
# misread that way, including one written the same day by the session that then "measured" a 20/181
# conformance rate and nearly reported it as agent drift. Fixing the location (bold) and leaving the
# class (any quoting of the hash) is what made this recur; the tolerance now lives in ONE constant
# that every hash-anchored Surface matcher composes.
# ⚠️ THIRD attempt at this class, and the first two each fixed a LOCATION. Recorded so the fourth
# does not repeat them:
#   attempt 1 tolerated bold on the LABEL (`**Surface:**`) but not on the VALUE;
#   attempt 2 tolerated a code span on the value but not bold/italic, and removed the TRAILING
#             `\s*` while leaving the LEADING one — so `**Surface:**\n<32hex>` still reached
#             forward and silently anchored a mega report on an unrelated later line (rc=0 where
#             the gate should have refused; reproduced end-to-end 2026-09-01).
# Hence two constants, composed by EVERY hash-anchored matcher in this file:
#   _MD_DECOR — the markdown decorations a hash actually wears here: code span, quotes, bold,
#               italic. Underscore is included, which is why the hash terminator below is a
#               negative lookahead and NOT `\b`: `_` is a word character, so `\b` fails between
#               `<hex>` and a closing `_`.
#   _HSP      — horizontal space ONLY. `\s` matches newline; every use of `\s` in a Surface/hash
#               matcher is a reach-forward waiting to happen.
_MD_DECOR = r"[`'\"*_]*"
_HSP = r"[^\S\n]*"
_SURFACE_QUOTE = rf"{_MD_DECOR}{_HSP}"
# Terminator for a fixed-width hash: "not followed by more hex" says exactly what `\b` was reaching
# for, and stays correct when the next character is a word-char decoration like `_`.
_HEX_END = r"(?![0-9a-fA-F])"

# An honest IN-PROGRESS review. The /fabrik-review methodology requires the report to exist BEFORE
# pass 1 ("a review that exists only in chat does not exist"), while every other rule here treats a
# persisted report as one that must already be converged. Those two cannot both hold, and the gap
# was being worked around by holding the report uncommitted across passes — which is precisely the
# state this file cannot see. Declaring the status makes the in-progress case legal and VISIBLE,
# instead of hidden in someone's working tree.
IN_PROGRESS = re.compile(r"^\**Status:\**\s*IN-PROGRESS\b", re.M | re.I)
PASS2 = re.compile(r"\bPass\s*2\b")
# The proof of a rubric RUN is the script's own generated output header — a prose
# mention is not an invocation (trade-intelligence 01M17Z7Q: a thrice-converged plan
# carried `review_rubric.py --changed <the paths this plan will touch>`, placeholder
# never expanded, and the bare-filename form credited it; the two packs its estimate
# missed each produced a HIGH finding within minutes of actually being swept).
# check_convergence imports THIS definition — one law, both graders. Searched on RAW
# text, never fence-stripped: the pasted output's natural home is a fenced block
# (the circular trap check_convergence:383-389 documents).
RUBRIC_RUN = re.compile(r"REVIEW RUBRIC\b[^\n]*generated by review_rubric\.py")
_PATHISH = re.compile(r"[\w-]+[./][\w./-]+")
# Twin of check_convergence._REDERIVATION_ROW — keep in lockstep (see the check below).
# D-053 (amended): method-cell-anchored, same-line, any gap — lockstep with the twin.
_REDERIVATION_ROW = re.compile(
    r"\b(?:pass|round)\b[^\n]*\bmethod\W{0,4}\s*:?\s*\*{0,2}\s*re-?deriv", re.I)


def _in_progress(text: str) -> bool:
    """Header-zone IN-PROGRESS — the ONE definition every reader uses.

    Round 15 reproduced body-deep escapes in the everyday readers: an appendix sentence
    documenting the escape hatch ("mark the report:\nStatus: IN-PROGRESS") exempted a committed
    non-quiet report entirely. The mega grammar was header-zoned in round 7; the everyday
    readers were not — the same per-reader-hardening root the first breaker firing named for
    the ledger, recurring for the escapes. Scoped to the first 10 fence-stripped lines, where
    the template slots Status.
    """
    # RAW first-10-lines slice, stripped WITHIN the slice (round 55): the zone was sliced
    # from the stripped text, so blank-line-preceded indented filler above a body-deep Status
    # shrank the document and pulled the line into the zone — a whole-grammar exemption by
    # indentation. The raw slice pins the zone to physical position; stripping within it
    # still defeats a fenced/indented example QUOTING the Status line inside the zone.
    header = "".join(text.splitlines(keepends=True)[:10])
    return bool(IN_PROGRESS.search(_strip_fences(header)))


def _blocked_sections(text: str) -> int:
    """How many BLOCKED sections carry their own in-section 3-attempts evidence.

    ⚠️ THE HONEST BOUNDARY (adjudicated round 21, ending three rounds of window tuning):
    BLOCKED evidence is DECLARATIVE, not provable. A forger who writes the attempts phrase
    inside their decoy section defeats any window; the window only ever defended against
    ACCIDENTAL harvest of pre-existing prose (the EOF-bleed). Form is checkable; sincerity is
    not — the real backstop is the operator reading the Telegram escalation the contract
    requires. The same undecidability holds for one escalation honestly covering two related
    rows (the 1:1 minimum false-fails it; authors split the section). Both residuals are
    accepted HERE, once, rather than re-tuned per round.

    Round 19: the cardinality check counted BARE headings (findall), so N-1 empty decoy
    headings plus one real escalation waived N unchecked rows — a pure headcount wearing a
    correlation's clothes. Only EVIDENCED sections count now.

    Window: the full section when a next heading bounds it (round 19 measured the repo's own
    committed escalation style at 2048 chars of repro history before the attempts phrase — a
    600-char cap false-failed real corpus data); the 600-char cap applies ONLY to a section
    running to EOF, where round 17 reproduced a bare heading harvesting unrelated trailing
    prose.
    """
    body = _strip_fences(text)
    attempts = re.compile(
        r"3\b.{0,40}(?:attempt|failure)|(?:attempt|failure).{0,40}\b3\b"
        r"|three (?:consecutive|failed)",
        re.I | re.S,
    )
    n = 0
    for m in BLOCKED_HEAD.finditer(body):
        nxt = re.search(r"^#{1,4}\s", body[m.end() :], re.M)
        section = body[m.end() : m.end() + nxt.start()] if nxt else body[m.end() : m.end() + 600]
        if attempts.search(section):
            n += 1
    return n


def _blocked_ok(text: str) -> bool:
    """At least one evidenced BLOCKED escalation exists — see _blocked_sections."""
    return _blocked_sections(text) >= 1


def _fence_parity_error(text: str) -> str | None:
    """ODD fence-marker count = the document's structure is unverifiable. One rule, no floors.

    Round 47 ended the fence arms race by proving it undecidable: regex pairing mis-paired a
    true unclosed opener with a later balanced pair's opener (erasing a real checklist and a
    real HANDOFF row — fail-open in BOTH floors, the cert one latent since round 40), and the
    round-45 and round-47 fixtures are STRUCTURALLY IDENTICAL — only the author's intent about
    which fence went unclosed differs, which no parser can know. What IS decidable: a finished
    markdown document has matching fences. A dangling opener (per the sequential, flavor-aware
    scan in _fence_regions — round 51 killed raw per-flavor counting, which a cross-flavor
    quote both defeats and false-fires) → one loud structural error naming the one-keystroke
    fix, in every grammar, before any other obligation is judged.
    """
    _fences, _comments, dangling, c_dangling = _block_regions(text)
    if dangling is not None:
        return (
            "UNCLOSED code fence (a ``` or ~~~ fence is opened and never closed): a dangling "
            "fence makes every obligation after it unverifiable (it can swallow or fabricate "
            "checklists, ledgers and dispositions). Close the fence."
        )
    if c_dangling is not None:
        # Round 61: absorb-to-EOF alone was SILENT — a forgotten `-->` swallowed the
        # checklist heading (or every HANDOFF row), de-subjected the report, and the gate
        # passed clean. The dangling comment gets the same loud treatment as a dangling
        # fence: one structural error naming the one-keystroke fix, before any obligation.
        return (
            "UNCLOSED HTML comment (`<!--` opened and never closed): it absorbs everything "
            "after it, swallowing checklists, ledgers and dispositions. Close it with `-->`."
        )
    return None


def check_file(p: Path) -> list[str]:
    errs: list[str] = []
    text = p.read_text(encoding="utf-8", errors="replace")
    # IN-PROGRESS before parity (round 49): the sanctioned mid-loop state may legitimately
    # carry a dangling appendix fence — the blocking gate was refusing to let the author ever
    # COMMIT the exact document the committed advisory would then accept as mid-loop. Parity
    # binds at the flip; the standing IN-PROGRESS advisory keeps the pressure on meanwhile.
    if _in_progress(text):
        return errs
    pe = _fence_parity_error(text) or _indented_grammar_error(text)
    if pe:
        return [pe]
    section = _checklist_section(text)
    if section is None:
        # SUBJECT-BY-STRUCTURE (round 27, retiring two rounds of substring tuning): the
        # command-name sniff was a literal-substring proxy for "is this a review report" and
        # failed BOTH ways — prose explaining the review process hard-failed (quoting the
        # command + the rubric filename), while a real report paraphrasing either token
        # escaped entirely, so the sniff provided only theater. A doc is this gate's subject
        # when it carries the checklist HEADING (the skeleton mandates it from pass 0);
        # "did the command emit its artifact at all" is the run-record + Stop hook's moment,
        # not a text-matching one.
        return errs
    # contract obligations recorded in the artifact itself — searched on STRIPPED text
    # (round 43): these three were the last raw-text seam, and a FENCED example quoting
    # "Surface: <hash>" satisfied the cross-run-anchor obligation while every sibling check
    # in this same function had long since gone fence-safe
    text_s = _strip_fences(text)
    if not SURFACE.search(text_s):
        errs.append(
            "no `Surface:` hash line (cross-run anchor) — record `git rev-parse HEAD` + diff md5"
        )
    # RAW text, not text_s: the pasted rubric output lives inside a fenced block by the
    # command's own mandate — fence-stripping made the one legitimate proof invisible.
    if not RUBRIC_RUN.search(text):
        errs.append(
            "no pasted review_rubric.py OUTPUT (its generated `# REVIEW RUBRIC` header) — "
            "run it on the real changed paths and paste the verbatim output; a prose "
            "mention or an unexpanded placeholder is not an invocation"
        )
    if not PASS2.search(text_s):
        errs.append(
            "no `Pass 2` row in the ledger. Minimum two rounds ALWAYS (a clean pass 1 still needs "
            "its confirming round) — but if you DID run it, this is a FORMATTING rule, not a "
            "missing round: rows must be labelled `| Pass 2 |`, not a bare `| 2 |`. Relabel the "
            "cell; never add a round you did not run to satisfy a parser"
        )
    # Review-side twin of check_convergence's re-derivation flip gate (tryton-crm 01M17KHT:
    # eleven citation rounds indistinguishable from a loop that re-derived; six defects
    # survived a CONVERGED stamp). Scoped to CHANGED review artifacts by this checker's own
    # construction, so zero legacy reds on landing — the deferral's fire-rate concern,
    # measured away. Keep the regex in lockstep with check_convergence._REDERIVATION_ROW
    # (a one-line twin; a shared import would invert that module's existing one-way dep).
    # A sanctioned BLOCKED exit is exempt: it claims a STUCK loop, not a converged truth —
    # the re-derivation demand guards the truth claim (over-fire caught by the mega-report
    # fixture battery on landing day, not in the field).
    if not _REDERIVATION_ROW.search(text_s) and not _blocked_ok(text):
        errs.append(
            "no re-derivation ledger row — the CLOSING pass must RE-DERIVE every count/"
            "enumeration/anchor from its primary source and the ledger must say so (a Pass/"
            "Round row naming `method: re-derivation`); citation rounds alone are "
            "method-stability, not truth"
        )
    rows = _table_rows(section)
    if not rows:
        errs.append("Coverage Checklist has no table rows")
        return errs
    blocked_ok = _blocked_ok(text)
    unchecked = [r.strip() for r in rows if UNCHECKED.search(r)]
    if unchecked and blocked_ok:
        # cheap cardinality correlation (round 17): ONE unrelated BLOCKED section was waiving
        # EVERY unchecked row. The contract pauses THAT finding, not the document — at minimum
        # each unchecked row needs its own evidenced BLOCKED section.
        if _blocked_sections(text) < len(unchecked):
            blocked_ok = False
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
    # LEDGER-SHAPED LINES ONLY — a table row (`| …`) or a Pass-labelled line. The whole-text
    # scan this replaces was defeated by a prose sentence merely QUOTING the exit contract
    # ("the exit round must read found: 0, fixed: 0") anywhere after the ledger — the same
    # LAST-match class the mega grammar was hardened against three times, alive in the
    # everyday grammar next door (round-7 closing sweep, reproduced against check_file).
    # ONE extraction contract with the mega grammar (_ledger_shapes): fence-stripped, and only
    # LEDGER-SHAPED lines count — a cell-anchored counter row or a Pass-labelled line. Round 9
    # defeated the previous scan three ways (a checklist evidence cell "audit found: 0, fixed: 0"
    # after the ledger; a FENCED example Pass-line; the same two against the committed scan) —
    # all because this path and the mega path were hardened separately. They no longer are.
    bad_rows = _unparsed_pass_lines(text)
    if bad_rows:
        errs.append(
            f"{len(bad_rows)} Pass-shaped ledger line(s) do not parse ({bad_rows[0][:70]!r}): "
            "a count trailed by a word (or a missing counter) is ambiguous — punctuate the "
            "counts (`found: N, fixed: M`) if the row is live, or fence it if quoted"
        )
    ev_tables, ev_prose, ordered_rows = _ledger_shapes(text)
    groups = len(ev_tables) + len(ev_prose)
    if groups > 1 and not _in_progress(text) and not blocked_ok:
        errs.append(
            f"counter rows appear in {groups} separate groups (tables/prose runs) — the ledger "
            "must be ONE group, because the exit check reads the LAST row and a decoy group "
            "after the real ledger becomes the exit round (round-13, reproduced with an "
            "appendix example row). Quote examples inside code fences"
        )
    founds = [str(f) for f, _x, _ln in ordered_rows]
    if founds and int(founds[-1]) != 0 and not blocked_ok and not _in_progress(text):
        errs.append(
            f"final ledger round raised {founds[-1]} (a FRESH candidate counts even when refuted; a re-raise of an already-adjudicated standing row is cited in its disposition row, not counted — D-048) — the exit round must be quiet, or the stuck finding must be BLOCKED-escalated (named + 3 failed attempts), or the report must declare `Status: IN-PROGRESS`"
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
# re.I (round 111): routing by filename must not be defeatable by casing — a `-User-Test-`
# name silently skipped BOTH the blocking and committed cert checks (fail-open by rename).
CERT_REPORT = re.compile(r"-(user|service)-test-.*\.md$", re.I)

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
MEGA_FILENAME = re.compile(
    r"\bmega-(?:.*-)?validation-review\.md$"
)  # the doc reserves …-mega-<slug>-validation-review.md; a bare suffix would force FUTURE non-mega reports (e.g. ettw-10) into the wrong grammar


def _is_mega_report(path: Path, text: str) -> bool:
    return bool(MEGA_REPORT_H1.match(text.lstrip("\ufeff \n"))) or bool(
        MEGA_FILENAME.search(path.name)
    )


_MEGA_PLACEHOLDERS = ("[PASS]", "[FAIL]", "[N]", "[M]", "[list]", "[none / list]")
_MEGA_HEX = r"[0-9a-fA-F]{32}"  # FULL md5, exactly — the doc mandates all 32; 12-char "full-ish" let truncation pass wherever the live recompute is skipped
# ⚠️ Quote-tolerant for the SAME reason `_MEGA_SURFACE` is, and it was missed on the first pass —
# which made the fix WORSE than no fix for one author. A report that code-spans its hashes
# consistently (`**Surface:** `<h>`` and `| … | `<h>` → `<h>` |`) used to fail BOTH halves, which at
# least agreed; after the Surface half was made tolerant and this one was not, presence PASSES and
# the pair FAILS, pointing the operator at the wrong half with "final ledger round carries no full
# md5(start) → md5(end) pair" when the pair is right there in code spans. Fixing the location and
# not the class is what this file has now paid for three times (:230, :238, here).
# MIRROR (named, per the contract): this widens the matcher, so an unfenced prose sentence like
# `<h>` -> `<h>` becomes matchable where it was not. Bounded — the matcher was already unanchored
# and runs on fence-stripped text, so the only added surface is quote characters, and the gap is
# horizontal-only (`[^\S\n]`) so it still cannot span lines.
_HASH_GAP = rf"{_MD_DECOR}{_HSP}"
_MEGA_HASH_PAIR = re.compile(
    rf"({_MEGA_HEX}){_HEX_END}{_HASH_GAP}(?:→|->){_HSP}{_HASH_GAP}({_MEGA_HEX}){_HEX_END}"
)
# A ledger row is a markdown TABLE line carrying both counters — and the ledger is the FIRST
# contiguous table that contains any such row. v2 matched counter rows ANYWHERE, so a later
# `## Per-lens tally` table with a quiet row silently became "the final round", masking a
# non-quiet exit — the LAST-match defect's THIRD appearance in this file, one table over.
_MEGA_SURFACE = re.compile(
    rf"^\**Surface:\**{_HSP}{_SURFACE_QUOTE}({_MEGA_HEX}){_HEX_END}", re.M
)  # no $: a trailing annotation is not absence (the wrong-reason class, third sighting)


# A fence delimiter line, either GFM flavor, 0–3 leading spaces (valid CommonMark — editor
# auto-indent and list-quoting produce these routinely).
_FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


# A block-level HTML comment opener: line-leading (0–3 spaces). A mid-paragraph `<!--` is
# INLINE HTML to a renderer, not a block comment — round 59 reproduced the fence-unaware
# blanking regex letting a prose `<!--` eat a real fence opener through a `-->` quoted
# INSIDE the fence, false-firing UNCLOSED on an unambiguous document.
_COMMENT_OPEN = re.compile(r"^ {0,3}<!--(.*)$")


def _block_regions(
    text: str,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], int | None, int | None]:
    """ONE sequential block scanner: fences and HTML comments, mutually exclusive.

    A renderer reads block structure sequentially — a `<!--` inside an open fence is fence
    content; a fence marker inside an open comment is comment content (HTML block type 2 runs
    until a line containing `-->`, and fences do not interrupt it); a mid-paragraph `<!--` is
    inline, never a block comment. Round 58 blanked comments with a position-blind regex and
    round 59 reproduced both cross-contaminations. An unclosed block comment absorbs to EOF,
    matching renderer behavior. Returns (fence regions, comment regions, dangling fence
    opener index, dangling comment opener index) as inclusive line-index pairs — the dangling
    comment is surfaced explicitly because absorb-to-EOF alone is NOT fail-closed: round 61
    reproduced a forgotten `-->` swallowing the checklist heading, de-subjecting the whole
    report into a clean pass. The parity precondition reports it loudly instead.
    """
    fences: list[tuple[int, int]] = []
    comments: list[tuple[int, int]] = []
    open_at: int | None = None
    open_marker = ""
    c_open: int | None = None
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if c_open is not None:
            if "-->" in ln:
                comments.append((c_open, i))
                c_open = None
            continue
        if open_at is None:
            mc = _COMMENT_OPEN.match(ln)
            if mc:
                if "-->" in mc.group(1):
                    comments.append((i, i))
                else:
                    c_open = i
                continue
        m = _FENCE_LINE.match(ln)
        if not m:
            continue
        marker, rest = m.group(1), m.group(2)
        if open_at is None:
            if marker[0] == "`" and "`" in rest:
                # CommonMark: a backtick fence's info string may not contain a backtick —
                # a one-line ```demo``` illustration is a PARAGRAPH to a renderer, and
                # reading it as a dangling opener false-fired UNCLOSED on honest prose
                # (round 53). Tilde info strings may contain anything, including tildes.
                continue
            open_at, open_marker = i, marker
        elif marker[0] == open_marker[0] and len(marker) >= len(open_marker) and not rest.strip():
            fences.append((open_at, i))
            open_at = None
    if c_open is not None:
        comments.append((c_open, len(lines) - 1))
    return fences, comments, open_at, c_open


def _kept_lines(text: str) -> list[str]:
    """The ONE live-line constructor every structural reader shares (round 59).

    Round 58 blanked comments in _strip_fences but _indented_grammar_error rebuilt its lines
    from RAW text — the two walks disagreed, and the very next sweep reproduced both wrong
    verdicts that divergence permits. One constructor, no siblings to drift.

    EVERYTHING quoted is BLANKED, never dropped (round 83): fenced regions, comment regions,
    and a dangling opener's tail all become bare blank lines. Dropping fences destroyed
    physical line adjacency while comment-blanking preserved it, and the adjacency-sensitive
    consumers (the setext `live[idx+1]` check, `_ledger_shapes`' prev_nonblank boundary)
    false-fired on the seam: a title + fence + `---` sequence read as a setext heading, and
    a fence between prose ledger rows split one honest quiet run into two "groups". Blanking
    also matches the renderer at every boundary: the enclosing block ends there, so an
    indented line after a quoted region is a code block (the blank-preceded rule holds).
    """
    fences, comments, dangling = _block_regions(text)[:3]
    lines = text.splitlines(keepends=True)
    blank: set[int] = set()
    for a, b in fences:
        blank.update(range(a, b + 1))
    for a, b in comments:
        blank.update(range(a, b + 1))
    if dangling is not None:
        # the round-11 fail-closed contract: content below a dangling opener is quoted
        blank.update(range(dangling, len(lines)))
    return ["\n" if i in blank else ln for i, ln in enumerate(lines)]


def _strip_fences(text: str) -> str:
    live, _quoted = _split_indented(_kept_lines(text))
    return "".join(live)


_INDENTED_LINE = re.compile(r"^(?: {4,}|\t)")


def _split_indented(kept: list[str]) -> tuple[list[str], list[str]]:
    """Split fence-stripped lines into (live, indented-code-block content).

    CommonMark INDENTED code blocks (4+ spaces or a tab, preceded by a blank line) are QUOTED
    content to a renderer, exactly like a fenced block — round 53 reproduced a fake quiet Pass
    row inside a plain indented appendix masking a real non-quiet final round. The blank-line
    precondition is CommonMark's own paragraph-continuation rule: an indented line directly
    under prose is a lazy continuation, still live. Container-relative indent (a fence nested
    under list bullets) is the accepted residual — review reports do not nest their ledgers in
    lists, and the divergence there fails CLOSED, never open. The quoted half is returned, not
    discarded, so _indented_grammar_error can refuse the ambiguous constructions (round 55).
    """
    live: list[str] = []
    quoted: list[str] = []
    prev_blank = True
    i = 0
    while i < len(kept):
        ln = kept[i]
        if prev_blank and ln.strip() and _INDENTED_LINE.match(ln):
            while i < len(kept) and (not kept[i].strip() or _INDENTED_LINE.match(kept[i])):
                quoted.append(kept[i])
                i += 1
            prev_blank = True
            continue
        live.append(ln)
        prev_blank = not ln.strip()
        i += 1
    return live, quoted


def _grammar_shaped(dedented: str) -> bool:
    """Does a line LOOK load-bearing to this file's grammars? (table row, Pass-counter line,
    HANDOFF row, Status/Surface declaration, checklist/BLOCKED heading)."""
    return bool(
        dedented.startswith("|")
        or _pass_counters(dedented) is not None
        or HANDOFF_ROW.match(dedented)
        or re.match(r"\**(?:Status|Surface):", dedented, re.I)
        or CHECKLIST_HEAD.match(dedented)
        or (dedented.startswith("#") and "BLOCKED" in dedented)
    )


_BLOCKQUOTE = re.compile(r"^ {0,3}>")
# A list-item wrapper (`- ## Coverage Checklist`, `1. # Appendix`) renders its content as a
# REAL heading nested in the list item — round 77 found the list-marker hardening (rounds
# 65-69) and the heading hardening (rounds 57-76) were never cross-applied, so a wrapped
# checklist heading silently de-subjected a whole report and a wrapped divider defeated the
# run boundary. Narrow by design: only heading/declaration shapes are refused — bulleted
# Pass/HANDOFF ROWS are sanctioned LIVE rows (the _LIST_MARK tolerance), and `- #123 fixed`
# prose is not a heading (# must be followed by whitespace or EOL).
_LIST_WRAP = re.compile(r"^ {0,3}(?:[-*+]|\d+[.)])\s+")
# Declaration shapes match the ACTUAL anchors, not any English "Status:/Surface:" bullet —
# round 79 reproduced `- Surface: 3 new endpoints added this round` (ordinary review prose)
# hard-blocking an honest converged report. A wrapped declaration is only refusable when it
# would have BEEN an anchor unwrapped: Status: IN-PROGRESS, or Surface: carrying a hash.
_WRAPPED_HEADINGISH = re.compile(
    r"#{1,6}(?:\s|$)"
    r"|\**Status:\**\s*IN-PROGRESS\b"
    rf"|\**Surface:\**{_HSP}{_SURFACE_QUOTE}[0-9a-fA-F]{{12,}}",
    re.I,
)
# One container-prefix consumer for the normalization loop (round 79: containers COMPOSE —
# `- > ## …`, `> - ## …`, nested lists — and per-costume elif branches test exactly one
# level, so every composition revived the bypass one nesting deeper. Strip to a fixpoint,
# judge the residual once).
_CONTAINER = re.compile(r"^ {0,3}(?:(>) ?|([-*+]|\d+[.)])\s+)")
_SETEXT_UNDERLINE = re.compile(r"^ {0,3}(=+|-+)\s*$")
_SETEXT_TITLE = re.compile(
    r"^ {0,3}\**\s*(coverage checklist|cross-epic validation report)\b", re.I
)


def _indented_grammar_error(text: str) -> str | None:
    """An INDENTED, BLOCKQUOTED, or SETEXT-headed grammar-shaped line is refused loudly (r55/57).

    Round 54 stripped indented code blocks silently (a renderer quotes them), and the very
    next sweep reproduced the mirror failure THREE ways: a live UNCHECKED checklist row, an
    OPEN HANDOFF row, and enough indented filler to shrink a body-deep Status: IN-PROGRESS
    into the header zone — each accidentally (or deliberately) indented, each silently
    VANISHING from its grammar, cleanly bypassing the gate. Quoted-as-live fails open one way;
    stripped-as-quoted fails open the other. What is decidable: the ambiguity itself. Same
    adjudication as fence parity — one loud error naming the one-keystroke fix, before any
    obligation is judged. Fenced quoting stays free: a FENCED example may quote anything.

    Round 57 generalized the class (the breaker's third firing): BLOCKQUOTED grammar lines
    (`> ## Coverage Checklist`, `> HANDOFF P1 OPEN …`) render as fully-visible, load-bearing
    content but were invisible to every column-0-anchored regex — a de-subjecting/vanishing
    escape identical in effect to the indent one; and a SETEXT-style title (`Coverage
    Checklist` over a `---` underline) renders as a real heading the ATX-only anchor never
    sees. All three costumes of one root (hand-rolled fragments of markdown block structure)
    get the one refusal: out-dent/ATX it if live, fence it if quoted.
    """
    live, quoted = _split_indented(_kept_lines(text))
    for ln in quoted:
        content = ln.strip()
        if content and _grammar_shaped(content):
            return (
                f"INDENTED grammar-shaped line ({content[:70]!r}): a renderer reads 4-space-"
                "indented blocks as quoted code, but this line looks load-bearing — out-dent "
                "it if it is live, or put it in a ``` fence if it is a quoted example"
            )

    def _peel(line: str) -> tuple[str, int, int]:
        content, n_quote, n_list = line, 0, 0
        while True:
            m = _CONTAINER.match(content)
            if not m:
                return content.strip(), n_quote, n_list
            if m.group(1):
                n_quote += 1
            else:
                n_list += 1
            content = content[m.end() :]

    for idx, ln in enumerate(live):
        content, n_quote, n_list = _peel(ln)
        if not content:
            continue
        wrapped = n_quote + n_list > 0
        # A single list marker is the SANCTIONED live-row tolerance (_LIST_MARK, rounds
        # 65-70) — bulleted Pass/HANDOFF rows parse as live and are never refused. Any
        # blockquote, and any second container level, puts the residual beyond every
        # anchor's reach: grammar-shaped residuals there are refused.
        if (n_quote >= 1 or n_list >= 2) and _grammar_shaped(content):
            flavor = "BLOCKQUOTED" if n_list == 0 else "CONTAINER-WRAPPED"
            return (
                f"{flavor} grammar-shaped line ({content[:70]!r}): it renders as "
                "visible content but is invisible to this gate's anchors — un-quote it "
                "if it is live, or put it in a ``` fence if it is a quoted example"
            )
        if (
            n_list == 1
            and n_quote == 0
            and content.startswith("|")
            and (
                UNCHECKED.search(content)
                or VERDICT.search(content)
                or _pass_counters(content) is not None
                or _MEGA_ROW.match(content)
                or HANDOFF_ROW.match(content)
            )
        ):
            # A LIST-WRAPPED pipe row (round 133): `- | class | UNCHECKED |` renders as a
            # BULLET carrying pipe text — not a table row — so it parses in neither row
            # extractor, and the single-list-marker tolerance only sanctions the PARSING
            # bulleted forms (Pass/HANDOFF prose lines). Visible to a human, invisible to
            # every anchor → the costume refusal, with the one-keystroke remedies.
            # OBLIGATION-BEARING content ONLY (rounds 135/137): the pipe-BOUNDED proxy
            # still false-fired on prose that merely sits between two pipes ("- | this
            # text sits between two pipe characters |", renderer-verified non-table).
            # Only content carrying grammar tokens (a verdict, counters, a mega row, a
            # HANDOFF) is refused — loud with the fence remedy; token-free pipe prose
            # passes. The bulleted MEGA round row joined the token set (its shape parses
            # via _MEGA_ROW, not _pass_counters).
            return (
                f"LIST-WRAPPED pipe row ({content[:70]!r}): it renders as a bullet, not a "
                "table row, and no extractor can read it — un-wrap it if it is live, or "
                "put it in a ``` fence if it is a quoted example"
            )
        if wrapped and _WRAPPED_HEADINGISH.match(content):
            flavor = (
                "BLOCKQUOTED"
                if n_list == 0
                else ("LIST-WRAPPED" if n_quote == 0 else "CONTAINER-WRAPPED")
            )
            return (
                f"{flavor} heading/declaration ({content[:70]!r}): it renders as a "
                "real heading but is invisible to this gate's anchors — un-wrap it if it "
                "is live, or put it in a ``` fence if it is a quoted example"
            )
        if (
            ln.lstrip().startswith("|")
            # RUN-INITIAL only (round 107): a pipe-row deeper in an established table is
            # unambiguous — `| a |\n|---|\n| b |\n---` renders as a table then a thematic
            # break, and refusing the table's TAIL row false-failed honest converged
            # reports using the house-style divider. Only the FIRST pipe-row of a physical
            # run can be the 1-column phantom-header candidate this refusal exists for —
            # the same scope _table_rows gives its own header pairing.
            and (idx == 0 or not live[idx - 1].lstrip().startswith("|"))
            and idx + 1 < len(live)
            and re.fullmatch(r" {0,3}-+\s*", live[idx + 1].rstrip("\n"))
        ):
            # A bare `---` DIRECTLY under a pipe-row is undecidable (round 105): GFM
            # forms a 1-column table whose header is the row above (its obligation text
            # visible in a <th> but invisible to every anchor), while the author
            # plausibly meant a section divider. Same adjudication as fence parity —
            # refuse with the one-keystroke remedies. A blank-line-separated `---`
            # stays an unambiguous thematic break.
            return (
                f"AMBIGUOUS bare `---` directly under a pipe row ({ln.strip()[:60]!r}): "
                "write `|---|` if it is a table separator, or put a blank line before "
                "`---` if it is a section divider"
            )
        if _SETEXT_TITLE.match(content) and idx + 1 < len(live):
            raw_next = live[idx + 1]
            nxt, q2, l2 = _peel(raw_next)
            # SAME container context required (round 81): per CommonMark a setext underline
            # binds its title only within one block context — a quoted/wrapped title over a
            # bare `---` is a paragraph plus a thematic break, NOT a heading, and the
            # depth-blind check false-fired on honest prose mentioning the title above a
            # divider. Quote depth must match exactly; a list-wrapped title's underline is
            # marker-less but continuation-indented (≥2 spaces).
            indent = len(raw_next) - len(raw_next.lstrip(" "))
            if (
                re.fullmatch(r"(=+|-+)", nxt)
                and q2 == n_quote
                and l2 == 0
                and (n_list == 0 or indent >= 2)
            ):
                return (
                    f"SETEXT-style heading ({content[:70]!r} over an underline): it renders "
                    "as a real heading but the gate anchors on ATX only — write it as an ATX "
                    "heading (## …)"
                )
    return None


# CELL-ANCHORED: the counters must be their own table cells (`| found: N | fixed: M |`), exactly
# as the template writes them. A prose phrase inside ONE evidence cell ("review found: 3 issues,
# fixed: 3 before merge") no longer reads as a counter row — that false-positive rejected an
# honest converged report as "ambiguous" (round-9 closing sweep, reproduced).
_MEGA_ROW = re.compile(r"^\s*\|.*?\|\s*found:\s*(\d+)\s*\|\s*fixed:\s*(\d+)\s*\|")
# A Pass-ANCHORED counter line ("Pass 2: found: 0, fixed: 0" / "| Pass 1 | … |"). The counters
# are TOKEN-anchored, not lazily scanned: round-11 reproduced both failure directions of the
# lazy version — a narrative phrase "sample found: 0 clean" earlier in the cell masked the real
# "found: 4" (quiet-forgery), and "previously found: 6 stray" flagged a genuinely quiet round
# (false-fail); "attempted-fixed: 2" swapped the fixed count. A token must stand alone
# (no word/hyphen prefix; a separator or EOL after the number), and a line with more than one
# strict token of either kind is not an honest single-round row — it is IGNORED, so a crafted
# decoy goes inert instead of winning the parse.
# THE list-marker fragment, defined ONCE (round 69): rounds 65→67→69 each found the next
# marker variant missing from one grammar (`-` then `1.` then `+`/`1)`), because the
# tolerance was re-typed per regex. CommonMark's marker set is CLOSED — bullets `-`/`+`/`*`,
# ordinals `digits.`/`digits)` — so one shared fragment ends the variant chase definitionally
# and the two ledger-row grammars can never drift again.
_LIST_MARK = r"(?:[-*+]|\d+[.)])?"
_PASS_HEAD = re.compile(r"^\s*" + _LIST_MARK + r"\s*\|?\s*\**Pass\s*\d", re.I)
# The separator is "anything that is not a word": round-13 measured the whitelist version
# against the repo's own committed corpus and whole ledgers evaporated — `fixed: 0.` (period),
# `found: 0\`` (backtick), `fixed: 0 → EXIT` (arrow), `fixed: 2 (seams…)` (paren) all went
# inert, and an inert FINAL row shifts ordered[-1] to the previous round: the fail-open
# direction, reproduced with a "BLOCKED next round" report that passed as quiet. `(?!\s*\w)`
# keeps the round-11 defense intact ("found: 0 clean" continues into a word → still rejected)
# while accepting every punctuation the corpus actually writes.
_FOUND_TOK = re.compile(r"(?<![\w-])found:\s*(\d+)(?!\s*\w)", re.M)
_FIXED_TOK = re.compile(r"(?<![\w-])fixed:\s*(\d+)(?!\s*\w)", re.M)


def _unparsed_pass_lines(text: str) -> list[str]:
    """Pass-shaped ledger lines that carry counter tokens but do NOT parse (round 121).

    Round 120 refused these in the GLOBAL precondition — over-broad (it hard-blocked
    non-subject narrative docs, against the round-27 doctrine) and under-broad (a line with
    only ONE loose token kind still vanished silently: `Pass 1: found: 12 new issues, still
    triaging` dropped its round entirely, and the prose branch — unlike the table branch —
    has no fail-closed ambiguity split). The check now lives with the SUBJECT-scoped ledger
    consumers: any Pass-headed line with a loose counter token that `_pass_counters` cannot
    parse is reported loudly there with the punctuation/fencing remedy. Unlike the
    multi-group and non-quiet-exit checks, this one is NOT blocked_ok-gated (round 123):
    structural LEGIBILITY binds regardless of BLOCKED — an escalated report's found:
    history matters most — matching parity and the costume refusals, which also run
    unconditionally. Multi-strict lines stay INERT (the round-11 decoy contract).
    """
    out: list[str] = []
    # A ROW claims its number with a delimiter (`Pass 1:` / `Pass 1 (WIDE) —` / `| Pass 1 |`);
    # a possessive or bare narrative (`Pass 2's found: 0 close did NOT survive…`, live
    # corpus) is prose — round 121's first cut retro-nagged a historical report on it.
    row_shaped = re.compile(
        r"^\s*(?:[-*+]|\d+[.)])?\s*\|?\s*\**Pass\s*\d+[a-z]?\**\s*[:—\-–(|·]", re.I
    )
    for ln in _strip_fences(text).splitlines():
        if not row_shaped.match(ln) or _pass_counters(ln) is not None:
            continue
        loose = re.findall(r"(?<![\w-])(?:found|fixed):\s*\d+", ln)
        if loose and len(_FOUND_TOK.findall(ln)) <= 1 and len(_FIXED_TOK.findall(ln)) <= 1:
            out.append(ln.strip())
    return out


def _pass_counters(line: str) -> tuple[int, int] | None:
    if not _PASS_HEAD.match(line):
        return None
    founds = _FOUND_TOK.findall(line)
    fixeds = _FIXED_TOK.findall(line)
    if len(founds) != 1 or len(fixeds) != 1:
        return None
    return int(founds[0]), int(fixeds[0])


def _ledger_shapes(
    text: str,
) -> tuple[
    list[list[tuple[int, int, str]]], list[tuple[int, int, str]], list[tuple[int, int, str]]
]:
    """ONE extraction contract for every ledger reader in this file.

    Returns (counter TABLES, prose PASS-line RUNS, document-order rows) from fence-stripped
    text. Nine review rounds of
    this file's own history are condensed here: THREE parallel ledger-reading implementations
    (the mega grammar, check_file, the committed advisory) were each hardened separately, and
    every closing sweep found the newest hardening absent from a sibling path — the loop's
    stall circuit-breaker finally named the triple implementation itself as the foundation
    error. Every reader now consumes THIS function; a hardening lands once or not at all.

    Shapes: a counter TABLE is a contiguous run of cell-anchored rows (separator rows skipped
    in-table; any other line ends it). A PASS-line is a Pass-anchored line carrying both
    counters — matched even when written as a table row (`| Pass 1 | … |`), in which case it is
    counted in its table, not double-counted as prose.
    """
    body = _strip_fences(text)
    tables: list[list[tuple[int, int, str]]] = []
    # Prose runs are POSITIONAL groups like tables (round 71: a flat prose list made every
    # prose Pass-line in the document ONE group, so a retro sentence in a later SECTION that
    # parsed as a counter silently became the final round with NO multi-group refusal — the
    # only decoy shape the guard could not see). The run boundary is STRUCTURAL — a heading —
    # not arbitrary prose: honest prose ledgers wrap rows with continuation lines (the
    # 2026-08-04 corpus report does; breaking on any prose false-fired it), but a ledger
    # lives in ONE section, so a counter line past the next heading is a separate group.
    prose_runs: list[list[tuple[int, int, str]]] = []
    ordered: list[tuple[int, int, str]] = []
    current: list[tuple[int, int, str]] = []
    p_run: list[tuple[int, int, str]] = []
    # A run boundary is ANY renderer-heading form (round 73: the ATX-only regex let a
    # blockquoted `> ## Appendix` or a setext underline — both real heading elements to a
    # renderer — fail to close the run, reviving the round-71 decoy bypass one syntax over):
    # ATX with optional blockquote prefixes, or a setext underline directly under a non-blank
    # line (an underline after a blank is a thematic break, not a heading — same-section,
    # the adjudicated author-declares-exit residual).
    # (?:\s|$): CommonMark accepts a BARE `#` at end-of-line as a valid empty ATX heading
    # (round 75 — the required-trailing-space form let a lone `#` divider fail to bound the
    # run, reviving the decoy bypass one syntax over yet again).
    atx_boundary = re.compile(r"^ {0,3}(?:>\s*)*#{1,6}(?:\s|$)")
    setext_underline = re.compile(r"^ {0,3}(?:>\s*)*(=+|-+)\s*$")
    prev_nonblank = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            if p_run:
                prose_runs.append(p_run)
                p_run = []
            if re.fullmatch(r"[|\-: ]+", stripped):
                continue  # separator row — never data, never a boundary
            m = _MEGA_ROW.match(line)
            pc = _pass_counters(line) if m is None else None
            if m or pc:
                pair = (int(m.group(1)), int(m.group(2))) if m else pc
                row = (pair[0], pair[1], line)
                current.append(row)
                ordered.append(row)
                continue
            if current:
                tables.append(current)
                current = []
        else:
            if current:
                tables.append(current)
                current = []
            pc = _pass_counters(line)
            if pc:
                row = (pc[0], pc[1], line)
                p_run.append(row)
                ordered.append(row)
            elif p_run and (
                atx_boundary.match(line) or (setext_underline.match(line) and prev_nonblank)
            ):
                prose_runs.append(p_run)
                p_run = []
        prev_nonblank = bool(stripped)
    if current:
        tables.append(current)
    if p_run:
        prose_runs.append(p_run)
    return tables, prose_runs, ordered


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
    files = sorted(str(p.relative_to(root)) for p in epics.rglob("*.md") if p.is_file())
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
    if _in_progress(text):
        return []  # the sanctioned mid-loop state — parity binds at the flip (round 49)
    pe = _fence_parity_error(text) or _indented_grammar_error(text)
    if pe:
        return [pe]
    body = _strip_fences(text)
    errs: list[str] = []
    # RETRO-GRADE errors (round 129, replacing the substring keep-filter): classified at
    # EMISSION, not filtered after — three keep-tuple rounds in a row (127/128/129) each
    # found another structural error the substring filter silently dropped on the committed
    # path, because every new error had to be manually re-registered. Now a new error lands
    # in `errs` (structural — survives every scope, the fail-closed default) unless it is
    # explicitly retro-grade: the set that would nag every historical report forever and get
    # the advisory muted (Surface presence, round minimums, placeholders).
    retro: list[str] = []
    # The THIRD ledger consumer (round 125): the unparsed-row legibility check reached
    # check_file and the committed scan in rounds 121-124 but never this grammar — a
    # trailing `Pass 3: found: 7 issues remain, still triaging` after a quiet table
    # vanished (it parses as neither a counter row nor prose_rows, so the mixed-shape
    # cross-check never fired) and a non-quiet mega exit read as converged. Structural,
    # so unconditional per the round-124 architecture rule.
    for bad in _unparsed_pass_lines(text)[:1]:
        errs.append(
            f"Pass-shaped ledger line does not parse ({bad[:70]!r}) — punctuate the "
            "counts (`found: N, fixed: M`) if the row is live, or fence it if quoted"
        )
    surface = _MEGA_SURFACE.search(body)
    if surface is None:
        retro.append(
            "no `Surface:` line carrying a FULL hash (≥12 hex) — record the final SET hash from "
            "the Step-3 anti-cheat (`find docs/development/epics -name '*.md' … | md5sum`), "
            "untruncated; `TBD`, prose, or a truncated stub do not anchor anything"
        )
    tables, prose_rows, _ = _ledger_shapes(text)
    rows: list[tuple[int, int, str]] | None
    if prose_rows and tables:
        errs.append(
            "counter lines exist OUTSIDE the ledger table (Pass-style prose alongside a table) — "
            "in a mega report the table is the ONLY sanctioned ledger shape, and prose counters "
            "next to it are how a real non-quiet history hides behind a quiet decoy table"
        )
        rows = []
    elif len(tables) > 1:
        rows = None
    elif prose_rows and not tables:
        errs.append(
            "the ledger exists only as Pass-style prose — counter lines OUTSIDE the ledger table "
            "are not a ledger. In a mega report the TABLE is the only sanctioned shape (prose is "
            "exempt from cell-anchoring by construction, which is exactly where the decoy lives)"
        )
        rows = []
    else:
        rows = tables[0] if tables else []
    if rows is None:
        # NOT an early return: that bypassed the scope filter below, so the committed advisory
        # leaked full-obligation errors for ambiguous reports (narrowness breach) — and routing
        # through the filter requires the ambiguity to be IN its keep-set, because an ambiguous
        # ledger can hide a non-quiet exit and is therefore exit-condition-grade.
        errs.append(
            "the report contains MORE THAN ONE found:/fixed: counter table — the round ledger "
            "must be the report's ONLY one (rename other tables' columns; the pair is reserved). "
            "Ambiguity is refused rather than resolved, because every selection heuristic is a "
            "decoy target — three were defeated in this grammar's own review"
        )
        rows = []
    if len(rows) < 2 and not any(
        "MORE THAN ONE" in e or "OUTSIDE the ledger table" in e for e in errs
    ):
        retro.append(
            f"ledger table records {len(rows)} round(s) — minimum two full rounds, ALWAYS, as "
            "TABLE rows carrying `found:` and `fixed:` (prose mentions do not count)"
        )
    if rows:
        f_found, f_fixed, f_line = rows[-1]
        # _blocked_ok: the mega command's own doc promises the BLOCKED escalation as the ONLY
        # sanctioned non-quiet stop — round 17 found the grammar never consumed it, so a
        # properly escalated report's only recourse was the document-wide IN-PROGRESS flag,
        # a strictly worse contract than the one documented.
        # Round 19 reverted round 18 here: gating this by _blocked_ok was the WRONG design —
        # the hash-moved and Surface checks below are the anti-cheat and cannot be BLOCKED-gated
        # (that would let a forged BLOCKED section bypass the hash proof), so a half-gated exit
        # was inconsistent AND a bypass seed. The mega contract's real shape: a BLOCKED
        # escalation pauses a finding MID-RUN, and a mid-run report persists as
        # Status: IN-PROGRESS with its ## BLOCKED section. BLOCKED never converts a non-quiet
        # exit into a done one.
        if f_found != 0 or f_fixed != 0:
            errs.append(
                f"final ledger round reads found: {f_found}, fixed: {f_fixed} — the exit round "
                "must be quiet in BOTH counters (a fix in the final round means the round that "
                "changed the set called itself the no-op), or declare `Status: IN-PROGRESS` "
                "within the report's FIRST 10 LINES (the template's slot is line 3). A "
                "BLOCKED escalation mid-run persists as IN-PROGRESS + its `## BLOCKED` section "
                "— BLOCKED never converts a non-quiet exit into a done one"
            )
        pairs = [_MEGA_HASH_PAIR.search(line) for _, _, line in rows]
        # EVERY round owes its pair (round 131): only the final row was checked, and the
        # chain-gap comparison silently skips None sides — a non-quiet earlier round with
        # NO pair at all carried zero proof of its claimed history and passed both paths.
        # Structural (anti-cheat), so it survives the committed scope like its siblings.
        for i, pr in enumerate(pairs[:-1]):
            if pr is None:
                errs.append(
                    f"round {i + 1} carries no full `md5(start) → md5(end)` pair (≥12 hex "
                    "each) — every round's claimed history needs its proof, not only the "
                    "exit's"
                )
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
        if live_hash is None:
            # Round 23, fail-open reproduced: with no epics dir a fully FABRICATED hash chain
            # passed the blocking gate — the recompute IS the anti-cheat, and skipping it on
            # absence is worse than the typed-identical-strings defeat it was built against.
            # A mega report claims to have validated an epic set; against NOTHING the claim is
            # unverifiable — fail loudly, don't shrug.
            errs.append(
                "the epic set at docs/development/epics is absent or empty — a mega validation "
                "report cannot be verified against nothing. If the epics were archived after "
                "the run, mark the report IN-PROGRESS or gate from the pre-archive tree"
            )
        if live_hash is not None and live_hash != surface.group(1).lower():
            errs.append(
                f"the epic set on disk hashes to {live_hash[:12]}… but the report anchors "
                f"{surface.group(1).lower()[:12]}… — the set changed after validation (your own "
                "follow-up, or a sibling session's edit — this tree runs several agents), or the "
                "hash was not computed. Re-run fab-mega-04-validate against the current set, or "
                "mark the report `Status: IN-PROGRESS` (first 10 lines) until you do"
            )
    leftover = [p for p in _MEGA_PLACEHOLDERS if p in body]
    # the template's Status line uses an ANGLE-bracket placeholder the square-bracket list
    # missed (round 37): a shipped literal "Status: <omit when converged; …>" read as fully
    # adjudicated. Header-zone scoped, like Status itself.
    header10 = "\n".join(body.splitlines()[:10])
    if re.search(r"^\**Status:\**\s*<", header10, re.M):
        leftover.append("Status: <template boilerplate>")
    if leftover:
        retro.append(
            f"template placeholder(s) survived into the persisted report: {leftover} — a "
            "placeholder is a lens nobody adjudicated wearing a verdict's clothes"
        )
    if scope == "exit":
        # The committed advisory keeps every STRUCTURAL error (classified at emission —
        # see the `retro` note above); only the retro-grade set is blocking-path-only.
        return errs
    return errs + retro


# Shares _LIST_MARK with _PASS_HEAD (rounds 67/69: each grammar re-typing its own marker
# tolerance is how a renderer-visible `1. HANDOFF …` / `1) HANDOFF …` kept vanishing from
# findall AND from _grammar_shaped's refusal net, waiving every downstream obligation).
HANDOFF_ROW = re.compile(
    r"^\s*" + _LIST_MARK + r"\s*HANDOFF\s+P([0-3])\s+(OPEN|CLOSED)\b(.*)$", re.M
)
REPRO_IN_ROW = re.compile(r"repro:\s*([\w./-]+)")
PROOF_IN_ROW = re.compile(r"proof:\s*\S")
CODE_WRONG_ROUTE = re.compile(r"route:\s*/fabrik-review\b")
EVIDENCE_IN_ROW = re.compile(r"evidence:\s*\S")
# LINE-INITIAL (round 113): the marker is a DECLARATION on its own line (the template's
# shape, incl. the truncation defense a zero-row NOT-QUIET report still owes) — a
# mid-sentence prose mention ("the NOT-QUIET marker exists so…") in a cert-NAMED retro
# false-failed on both paths once round 112's re.I widened the filename space.
# …and END-anchored (round 115): leading alone let a discursive sentence that merely
# STARTS with the marker ("**NOT-QUIET rows must name a RESUME…**") satisfy the
# obligation a real declaration exists to carry — fail-open, the mirror of round 113's
# false-fail. A declaration is the marker plus at most a parenthetical and punctuation;
# a sentence that continues with prose is discussion.
# Wrappers admit backticks (round 117): the command sources' own canonical instruction is
# the bold+code-span form ``ledger: **`NOT-QUIET (routes outstanding)`**`` — the anchor must
# accept what the canon instructs. The tail stays parenthetical-only; an em-dash tail fails
# CLOSED with the accepted form named in the message (right-message, not wrong-ish).
NOT_QUIET = re.compile(
    r"^\s*(?:[-*+]|\d+[.)])?\s*[*`]*(?:ledger:\s*)?[*`]*NOT-QUIET\b\s*"
    r"(?:\([^)\n]*\))?[\s*`.!]*$",
    re.M | re.I,
)
RESUME_HEAD = re.compile(r"^##\s+RESUME\b", re.M)


def check_cert_dispositions(path: Path, root: Path) -> list[str]:
    """Disposition rows in a certification report must be provable, not prose.

    Fence-stripped like every sibling grammar (round 37): this was the ONE grammar never
    brought under the discipline, and a fenced documentation example of the HANDOFF grammar
    produced false BLOCKING failures on an honest, fully-closed report — the fourth time a
    fenced example defeated a reader in this file's history.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    if _in_progress(raw):
        # The ONE escape hatch every reader honors (round 61 closed the asymmetry: cert was
        # the single grammar without it, hard-blocking a legitimately mid-loop cert report
        # that the workflow explicitly sanctions committing). Parity binds at the flip; the
        # committed scan keeps the standing IN-PROGRESS advisory on cert files too.
        return []
    text = _strip_fences(raw)
    # PRESENCE FLOOR (round 39): fence-stripping with no floor made an unclosed fence erase
    # every real HANDOFF/NOT-QUIET/RESUME row below it — the one reader whose siblings all
    # error loud on emptiness returned [] and PASSED. Balanced fences stay legitimate quoting;
    # grammar content that exists in the RAW text but not after stripping can only mean the
    # fenced-to-EOF truncation ate it — fail with the one-line fix, never silently pass.
    pe = _fence_parity_error(raw) or _indented_grammar_error(raw)
    if pe:
        return [pe]
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
                "NOT-QUIET (routes outstanding) — a truncated run may never present itself "
                "as quiet. Write the declaration as its own line: "
                "`ledger: NOT-QUIET (routes outstanding)`"
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
            if _in_progress(text):
                # same cloak-closure as the checklist branch below: the sanctioned mid-loop
                # state stays sanctioned but VISIBLE on every run
                out.append(
                    f"{p.relative_to(root)}: COMMITTED as Status: IN-PROGRESS — the loop that "
                    "opened it has not closed; finish it, or this line stands forever"
                )
                continue
            # scope="exit" honors this function's documented narrowness: only the quiet-exit +
            # moved-hash conditions, never the full obligation set — demanding Surface/rounds/
            # placeholders of every historical report forever is the muting mechanism the
            # docstring above names (closing-sweep finding, 2026-08-19).
            for e in check_mega_validation(p, root, live=False, scope="exit"):
                out.append(f"{p.relative_to(root)}: COMMITTED mega report — {e}")
            continue
        subject = _checklist_section(text) is not None
        if (subject or CERT_REPORT.search(p.name)) and _in_progress(text):
            # The sanctioned mid-loop state stays sanctioned but VISIBLE on every run — an
            # advisory that only quiets when the loop actually finishes (never a cloak that
            # exempts the report from every check). Checked BEFORE parity: a mid-loop report
            # with a dangling appendix fence gets THIS line, not a wrong-reason structural
            # one — the parity obligation binds at the flip. Subject-gated: non-subject
            # docs (spec/plan convergence artifacts) are never nagged.
            out.append(
                f"{p.relative_to(root)}: COMMITTED as Status: IN-PROGRESS — the loop that "
                "opened it has not closed; finish it, or this line stands forever"
            )
            continue
        pe = _fence_parity_error(text) or _indented_grammar_error(text)
        if pe:
            # NOT subject-gated: a dangling fence (or a vanishing indented grammar line)
            # defeats subject-detection itself — the swallowed-heading case — so gating on
            # subject-ness would silence exactly the docs these rules exist to catch. Both are
            # one-keystroke fixes; corpus measured at 0 flagged committed files — no retro-nag.
            out.append(f"{p.relative_to(root)}: COMMITTED with an {pe}")
            continue
        if CERT_REPORT.search(p.name):
            # Cert reports get the SAME committed-path coverage the mega grammar got the
            # day its hole was found (round 109: _committed_nonquiet never ran the cert
            # dispositions, so a committed OPEN HANDOFF row missing NOT-QUIET/RESUME — or
            # a CLOSED row citing a fabricated repro — went permanently invisible the
            # instant it was committed: green-by-absence, this function's founding enemy).
            # IN-PROGRESS cert reports were exempted-and-nagged above; corpus measured at
            # 0 flagged committed cert reports — no retro-nag.
            for e in check_cert_dispositions(p, root):
                out.append(f"{p.relative_to(root)}: COMMITTED cert report — {e}")
            if not subject:
                continue
        if not subject:
            # not this gate's subject (spec/plan convergence artifacts carry no checklist) —
            # round 23: the IN-PROGRESS advisory was firing on EVERY reviews/*.md with a
            # Status line, misattributing docs the module docstring explicitly exempts
            continue
        for bad in _unparsed_pass_lines(text)[:1]:
            # BEFORE the blocked_ok skip (round 123): structural LEGIBILITY binds regardless
            # of BLOCKED — the found: history matters MOST when escalating, and the live
            # gate already enforces this unconditionally (the two paths disagreed, with the
            # advisory silently waiving what the blocking gate refuses).
            out.append(
                f"{p.relative_to(root)}: COMMITTED with a Pass-shaped ledger line that does "
                f"not parse ({bad[:70]!r}) — punctuate the counts or fence the quote"
            )
        if _blocked_ok(text):
            # the SAME contract as every other reader — round 17 found this call site still
            # raw-matching BLOCKED_HEAD (no fence-strip, no evidence), one commit after the
            # centralization claimed "every reader"; a claim is only as true as its grep
            continue
        c_tables, c_prose, ordered_rows = _ledger_shapes(text)
        if len(c_tables) + len(c_prose) > 1:
            out.append(
                f"{p.relative_to(root)}: COMMITTED with counter rows in multiple groups — the "
                "exit round is forgeable by a decoy group; consolidate to ONE ledger"
            )
            # NO continue (round-15 finding 4): the non-quiet check below still runs, so a
            # decoy-group report that is ALSO non-quiet surfaces both facts, not just one.
        # The exit the CONTRACT states — D-048 (2026-08-31) re-keyed it: a re-raise of an
        # already-adjudicated standing row is CITED in its disposition row, never counted, so
        # `found:` counts only candidates NEEDING adjudication and the honest converged round
        # reads `found: 0`. The 2026-08-27 `new:`-preference this clause used to carry solved
        # the pre-D-048 unreachable-termination problem (transdoc) but diverged from the
        # BLOCKING reader at check_file, which grades `founds[-1]` only — the same report was
        # refused uncommitted and accepted committed, this function's own founding enemy.
        # Both readers now grade the same counter. Measured before landing, WITH the sync
        # denominator (this file distributes to ~46 repos): 13 /opt repos carry review corpora;
        # 24 advisories old -> 25 new — ONE newly-firing report (/opt/youtube
        # 2026-08-29-speed-multikey-mixed-review.md, an honest close under the pre-D-048
        # contract binding that day). Advisory-only — no retro-red; the hub itself is 11 -> 11.
        rows = [str(f) for f, _x, _ln in ordered_rows]
        quiet = True
        if rows:
            quiet = int(rows[-1]) == 0
        if not quiet:
            out.append(
                f"{p.relative_to(root)}: COMMITTED with a non-quiet exit round (found: {rows[-1]}) "
                "— committing a review does not converge it. Finish the loop, BLOCKED-escalate the "
                "stuck finding, or mark the report `Status: IN-PROGRESS`."
            )
    return out


def _grade(p: Path, root: Path) -> list[str]:
    """Full blocking battery for ONE review artifact — the routing main() always applied.

    Factored out (2026-08-30) so the commit-moment path (explicit paths from the pre-commit
    hook) grades with the SAME battery as the working-tree scan: a second, weaker grader for
    staged files would be the exact two-graders drift tryton-crm's 01M17KHT closed.
    """
    errs: list[str] = []
    try:
        rel = p.relative_to(root)
    except ValueError:
        rel = p
    # \A-anchored: the H1 must be the FILE'S FIRST LINE. A content-anywhere match let any
    # review file that merely QUOTED the template (even fenced) route here and skip the
    # checklist gate it actually owed — reproduced 2026-08-18.
    body = p.read_text(encoding="utf-8", errors="replace")
    if _is_mega_report(p, body):
        # a mega validation report is exit-proof-gated, not checklist-gated
        return [f"{rel}: {e}" for e in check_mega_validation(p, root, live=True)]
    if CERT_REPORT.search(p.name):
        errs.extend(f"{rel}: {e}" for e in check_cert_dispositions(p, root))
        # NO `continue` past a present checklist (round 37): the filename substring routed
        # a checklist-obligated report — real UNCHECKED rows and all — to the looser cert
        # grammar and exited green. The corpus already holds an organic precedent name
        # ("…-fabrik-user-test-first-run-feedback.md"), so this is not adversarial-only.
        # A filename is a routing HINT; the checklist heading is an OBLIGATION — a report
        # carrying both shapes answers to both gates.
        # STRIPPED text for the routing decision (round 39): the raw-text detector routed
        # an honest cert report into check_file's full obligation set because a FENCED
        # documentation example quoted the checklist heading — the mirror image of the
        # class the same commit closed for the HANDOFF grammar, one call site over.
        if _checklist_section(body) is None:  # strips at the definition since round 41
            return errs
    errs.extend(f"{rel}: {e}" for e in check_file(p))
    return errs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".", help="repo root (default: cwd)")
    ap.add_argument(
        "paths",
        nargs="*",
        help="explicit review artifacts to grade (the commit-moment path: the pre-commit "
        "hook passes the STAGED reviews/*.md here — a review committed without a gate run "
        "while dirty otherwise escapes the blocking scan forever, observed live 2026-08-30)",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()
    failures: list[str] = []
    if args.paths:
        for raw in args.paths:
            p = Path(raw).resolve()
            if not p.is_file():
                failures.append(f"{raw}: not a file (staged path vanished?)")
                continue
            failures.extend(_grade(p, root))
        if failures:
            print("Coverage-checklist gate FAILED (staged review artifacts):")
            for f in failures:
                print(f"  - {f}")
            print(
                "A review artifact enters history only fully adjudicated — fix it, finish "
                "the loop, or mark it `Status: IN-PROGRESS` (never invent a round to "
                "satisfy the parser)."
            )
            return 1
        print(
            "check_review_coverage: OK — 0 unproven coverage claims across "
            f"{len(args.paths)} staged review artifact(s)"
        )
        return 0
    changed, skip_notes, untracked = _changed_md(root, REVIEWS_DIR)
    # ⚠️ ADVISORY, not a failure — and the asymmetry is deliberate. The hole was that a committed
    # unconverged review was INVISIBLE; printing it fixes that. Hard-failing it would retro-grade
    # every historical report across ~46 synced repos on the next sync, on artifacts whose authors
    # may not even be active — and a gate that reds someone's unrelated commit is a gate that gets
    # switched off (the death this corpus has already seen once, with check_doc_sprawl).
    # The BLOCKING path stays where the author can still act: the report in their working tree.
    # untracked joins the skip set (round 121): an untracked file is neither changed nor
    # COMMITTED — the rglob scanned it anyway and labeled a sibling's mid-write scratch
    # "COMMITTED", the exact shared-tree misattribution the '??' carve-out exists to avoid.
    stale = _committed_nonquiet(root, skip=set(changed) | set(untracked))
    if stale:
        # ⚠ FIRST character matters: final_gate's --json ships a passing check's stdout only
        # when it STARTS with ⚠ (the opt-in the emitter documents). Round 23-25: the advisory
        # was invisible through the documented gate path because this header spoke first —
        # the emitter was correct all along; this check never spoke its protocol.
        print("⚠ check_review_coverage ADVISORY — committed review(s) needing attention:")
        for s in stale:
            print(f"  ⚠ {s}")
    for note in skip_notes:
        # AFTER the ⚠ block, never before it — a NOTE printing first broke the emitter's
        # startswith("⚠") opt-in and re-hid the advisory whenever an untracked draft
        # co-occurred with a committed advisory (round 25, reproduced end-to-end)
        print(note)
    for p in changed:
        failures.extend(_grade(p, root))
    if failures:
        print("Coverage-checklist gate FAILED:")
        for f in failures:
            print(f"  - {f}")
        print(
            "A coverage-adjudicated review exits only on a fully-adjudicated checklist "
            "— there is no cap-stop; a spot-verify of fixes is the re-check step, never the closing round."
        )
        return 1
    # DENOMINATOR: this check is DIFF-SCOPED, so on most runs there is simply nothing changed
    # to inspect — and a bare OK reads as "your reviews are proven" rather than "I looked at
    # nothing". See docs/reference/enforcement-battery-audit.md.
    print(
        "check_review_coverage: OK — 0 unproven coverage claims across "
        f"{len(changed)} changed review artifact(s)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
