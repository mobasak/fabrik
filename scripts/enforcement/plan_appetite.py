# AFTER-EDIT: tests/test_plan_appetite_size.py, scripts/enforcement/check_plan_tickets.py, scripts/enforcement/check_plan_quality.py
"""Two plan rules shared by the plan graders (spec 2026-10-02-fabrik-task-feature-lane, D10/D11).

- **Appetite (D11).** A plan dated on or after ``LANE_ROLLOUT_DATE`` declares
  ``Appetite: <positive integer minutes>`` in every phase (a monolith's ``## Phase <id>``
  sections) or in every ticket (a plan set's ``T##-<slug>.md`` files, graded by their own
  field line only). A spine declares none — its tickets carry it. Plans dated before the
  rollout (any leading ``YYYY-MM-DD-`` of the file or its directory) are never re-graded.
- **Size-small (D10).** A ``Profile: small`` plan is refused unless the spec it cites reads
  ``Status: CONVERGED`` or carries ``Size: small`` in its header — that line is what lets a
  small spec skip ``/fabrik-spec-review``. FAIL-CLOSED: a spec whose status cannot be read
  (no line, an unlisted value such as PROPOSED) counts as not converged, and so does a plan
  whose header cites no spec, or cites a file that does not exist (refused, naming which).

Both graders (``check_plan_tickets.py`` for sets, ``check_plan_quality.py`` per file) call
``lane_findings`` — one entry point grading one blockquote-stripped text (``lane_scan``) —
so they cannot disagree, and neither grader imports the other. ``PROFILE_RE`` lives here and
``check_plan_tickets`` re-exports it, so the profile both rules key on is one regex. The spec
CITATION is read from the raw header (a ``> **Spec:**`` line is a real citation form), while
``Profile:`` (``is_small_profile``, which ``check_plan_tickets`` also calls for its waiver) and a
ticket's ``Appetite:`` are read from the blockquote-stripped HEADER ZONE (``header_zone``: cut at
the first heading, then fences stripped) and a phase's ``Appetite:`` from ``lane_scan`` text — a
quoted one is an example.

COBRA (you get the behavior you measure): the cheapest way to satisfy the Appetite rule
without the outcome is a uniformly huge number (``Appetite: 9999``) — it passes the
grader and never trips the 2x re-plan order. The grader cannot see that; the
counter-measure is the over-appetite record at close (``over_appetite_phases``, D11),
whose meaning a padded appetite dilutes in plain sight, and plan-review reading the
number against the phase. The cheapest way past the Size rule is writing ``Size: small``
on a large spec; the counter-measure is D10's kill rule (a plan
larger than the estimate sends the spec back to ``/fabrik-spec-review``, and > 1 in 3 sent
back reverts D10).
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

LANE_ROLLOUT_DATE = "2026-10-03"

# `Profile: small` — the spine's opt-in to the INLINE execution profile. Bold-tolerant like the
# graders' Status regexes. The rules here search it on `lane_scan` text, where blockquoted lines
# are already gone, so its `>` tolerance matters only to check_plan_tickets' own callers.
PROFILE_RE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Profile\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*\*{0,2}(small)\*{0,2}"
    r"[^\S\n]*$",
    re.I | re.M,
)
# `Appetite: 60`, `**Appetite:** 45`, `- Appetite: 30 min` — the VALUE is graded separately so a
# present-but-invalid line (`Appetite: soon`, `Appetite: 0`, `Appetite: 60abc`) is named as such.
APPETITE_LINE_RE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?\*{0,2}Appetite\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}(?P<val>[^\n]*?)[^\S\n]*$",
    re.I | re.M,
)
_APPETITE_VALUE_RE = re.compile(r"^\*{0,2}(\d+)\*{0,2}(?:[^\S\n]*(?:min|mins|minutes))?$", re.I)
# `Size: small`, `**Size:** small`, `Size: small (≈300 lines, 4 files)` — `small` is the WHOLE
# value: only D10's own parenthesised estimate and trailing spaces may follow it, so
# `small-to-medium` or `small? no — large` never count. A spec HEADER field.
SIZE_SMALL_RE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?\*{0,2}Size\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*small\*{0,2}"
    r"(?:[^\S\n]+\([^)\n]*\))?[^\S\n]*$",
    re.I | re.M,
)
# A spec's Status in the four forms specs use: `Status: X`, `**Status:** X`, `> **Status:** X`
# and a `| Status | X |` table row. The first one in the header wins.
_SPEC_STATUS_RE = re.compile(
    r"^[ \t]*(?:>[ \t]*)?(?:[-*][ \t]+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*"
    r"(?:✅[^\S\n]*)?\*{0,2}[^\S\n]*(?P<v>[A-Za-z][\w-]*)"
    r"|^[ \t]*\|[^\S\n]*\*{0,2}Status\*{0,2}[^\S\n]*\|[^\S\n]*\*{0,2}[^\S\n]*(?P<t>[A-Za-z][\w-]*)",
    re.I | re.M,
)
# A plan's spec citation: `Spec:`, `Design spec:`, `Spec (source of truth):`, optionally
# blockquoted and bold. The value may be a repo-root path or a link relative to the plan.
_SPEC_FIELD_NAME = (
    r"\*{0,2}(?:Design spec|Spec)(?:[^\S\n]*\([^)\n]*\))?\*{0,2}"
    r"[^\S\n]*:\*{0,2}[^\S\n]*(?P<val>[^\n]*)$"
)
# The FIELD at a line start wins; only when there is none does a MID-line field count, and only
# after a ` · `, ` | `, `, ` or `; ` separator (`Date: 2026-10-05 · Spec: <path>`) with a
# path-like value — so prose such as `the older spec: old.md` is never read as the citation.
_SPEC_FIELD_RE = re.compile(r"^[ \t]*(?:>[ \t]*)?(?:[-*][ \t]+)?" + _SPEC_FIELD_NAME, re.I | re.M)
_SPEC_MIDLINE_RE = re.compile(
    r"(?:(?<= · )|(?<= \| )|(?<=, )|(?<=; ))" + _SPEC_FIELD_NAME, re.I | re.M
)
_PATHLIKE_RE = re.compile(r"\S*/\S*\.md\b")
_LINK_TARGET_RE = re.compile(r"\]\(\s*([^)\s]+?\.md)(?:#[^)\s]*)?\s*\)")
_PATH_RE = re.compile(r"(?<![\w./-])((?:/|(?:\.{1,2}/)*)[\w.-]+(?:/[\w.-]+)*\.md)\b")
_SPINE_MARKER_RE = re.compile(r"^##\s+Ticket Board\b", re.I | re.M)
# A monolith phase is `## Phase <id>` — any non-empty token after `Phase ` (`## Phase 1`,
# `## Phase A`, `## Phase Three — build`); `## Phase-out of X` and `## Phases` are not phases,
# and a `### Phase 1` sub-heading belongs to the `##` phase around it.
_PHASE_HEADING_RE = re.compile(r"^##[ \t]+(?P<title>Phase[ \t]+\S[^\n]*)$", re.M)
_SECTION_END_RE = re.compile(r"^#{1,2}[ \t]", re.M)
_BLOCKQUOTE_LINE_RE = re.compile(r"^[ \t]*>.*$", re.M)
_BACKTICK_FENCE_RE = re.compile(r"^[ \t]*`{3,}[^\n]*\n.*?^[ \t]*`{3,}[ \t]*$", re.M | re.S)
_TILDE_FENCE_RE = re.compile(r"^[ \t]*~{3,}[^\n]*\n.*?^[ \t]*~{3,}[ \t]*$", re.M | re.S)
_OPEN_FENCE_RE = re.compile(r"^[ \t]*(?:`{3,}|~{3,})[^\n]*$", re.M)
_FIRST_SECTION_RE = re.compile(r"^#{2,6}\s", re.M)
_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-")
_TICKET_NAME_RE = re.compile(r"^(T\d{2}[a-z]?)-[^/]*\.md$")


def strip_fences(text: str) -> str:
    """Remove fenced blocks; an UNCLOSED opener swallows the rest (fail-closed: a quoted
    `Appetite:` inside a dangling fence never satisfies a phase)."""
    text = _TILDE_FENCE_RE.sub("", _BACKTICK_FENCE_RE.sub("", text))
    dangling = _OPEN_FENCE_RE.search(text)
    return text[: dangling.start()] if dangling else text


def lane_scan(text: str) -> str:
    """The ONE text both graders grade: fences removed, blockquoted lines removed (a quoted
    `> Profile: small` or `> Appetite: 60` is an example, never a declaration). Idempotent."""
    return _BLOCKQUOTE_LINE_RE.sub("", strip_fences(text))


def header_zone(text: str) -> str:
    """Everything before the first `##` heading, fences removed — where header fields live.

    ORDER MATTERS: the zone is CUT first, then fences are stripped inside it. Stripping first let
    a fence opened in the header and closed past `## Ticket Board` swallow that heading, so the
    zone ran on into the body; cut first, the opener dangles inside the zone and absorbs to its
    end (fail-closed). The same rule makes a fenced `## example` heading END the zone. This is
    the ONE header zone both plan graders read (``check_plan_tickets`` via ``is_small_profile``).
    """
    m = _FIRST_SECTION_RE.search(text)
    return strip_fences(text[: m.start()] if m else text)


def is_small_profile(text: str) -> bool:
    """Does this plan's HEADER declare `Profile: small`? Blockquoted lines are examples, never
    the declaration. The ONE reading of the profile: ``check_plan_tickets`` (the READ-budget
    waiver) and the D10 rule here cannot disagree on a plan (T08-D7 C-O6)."""
    return PROFILE_RE.search(_BLOCKQUOTE_LINE_RE.sub("", header_zone(text))) is not None


def repo_root_of(path: Path) -> Path | None:
    """The repo a plan file lives in: the directory holding the innermost
    `docs/development/plans/` above it (a monolith, a set member, an archived set) — or None
    when the path is not under that layout. Read from the FILE, never from the cwd."""
    for d in Path(path).parents:
        if d.name == "plans" and d.parent.name == "development" and d.parent.parent.name == "docs":
            return d.parent.parent.parent
    return None


def plan_date_of(path: Path) -> str | None:
    """The leading `YYYY-MM-DD-` of a monolith (its file name) or a set member (its directory)."""
    for name in (path.stem, path.parent.name):
        m = _DATE_PREFIX_RE.match(name)
        if m:
            return m.group(1)
    return None


def is_graded(plan_date: str | date | None) -> bool:
    """True when the plan is dated on or after the rollout — older plans are not re-graded."""
    if plan_date is None:
        return False
    return str(plan_date) >= LANE_ROLLOUT_DATE


def _unit_finding(label: str, body: str) -> str | None:
    values = [m.group("val").strip() for m in APPETITE_LINE_RE.finditer(body)]
    if not values:
        return (
            f"{label}: no `Appetite: <minutes>` line — plans dated on or after "
            f"{LANE_ROLLOUT_DATE} declare one per phase or ticket (D11)"
        )
    for raw in values:
        m = _APPETITE_VALUE_RE.match(raw)
        if not m or int(m.group(1)) <= 0:
            return f"{label}: `Appetite: {raw}` is not a positive integer of minutes (D11)"
    return None


def appetite_findings(
    plan_text: str, plan_date: str | date | None, *, label: str = "plan", ticket: bool = False
) -> list[str]:
    """D11: the Appetite refusals for one plan file, empty when it complies or predates the rollout.

    A TICKET (`ticket=True`) is graded by its own `Appetite:` field line only — its header
    zone, before the first `##` heading — whatever its body or sub-headings say. A spine
    (`## Ticket Board`) owes none itself. A monolith with
    `## Phase <id>` headings owes one per phase, each finding naming the phase; a phase-less
    monolith owes one, named by `label`.
    """
    if not is_graded(plan_date):
        return []
    if ticket:
        found = _unit_finding(label, _BLOCKQUOTE_LINE_RE.sub("", header_zone(plan_text)))
        return [found] if found else []
    scan = lane_scan(plan_text)
    if _SPINE_MARKER_RE.search(scan):
        return []
    phases = list(_PHASE_HEADING_RE.finditer(scan))
    if not phases:
        found = _unit_finding(label, scan)
        return [found] if found else []
    findings: list[str] = []
    for ph in phases:
        nxt = _SECTION_END_RE.search(scan, ph.end())
        body = scan[ph.end() : nxt.start() if nxt else len(scan)]
        found = _unit_finding(ph.group("title").strip()[:80], body)
        if found:
            findings.append(found)
    return findings


def _spec_status(spec_text: str) -> str | None:
    m = _SPEC_STATUS_RE.search(header_zone(spec_text))
    if not m:
        return None
    return (m.group("v") or m.group("t")).upper()


def small_profile_findings(
    plan_text: str, spec_text: str | None, *, missing: str | None = None
) -> list[str]:
    """D10: refuse a `Profile: small` plan unless its spec reads CONVERGED or carries `Size: small`.

    FAIL-CLOSED on the spec too: `spec_text` None (no citation, or a citation to a file that
    does not exist) is refused, `missing` naming why.
    """
    if not is_small_profile(plan_text):
        return []
    if spec_text is None:
        why = missing or "its spec could not be read"
        return [
            f"`Profile: small` plan: {why} — only a CONVERGED spec, or one /fabrik-spec sized "
            "`Size: small`, may skip /fabrik-spec-review (D10); cite the spec in a header "
            "`Spec:` field, or plan it at full profile"
        ]
    status = _spec_status(spec_text)
    if status == "CONVERGED" or SIZE_SMALL_RE.search(header_zone(spec_text)):
        return []
    return [
        f"`Profile: small` plan cites a spec that is not CONVERGED (status: {status or 'unreadable'})"
        " and has no `Size: small` header line — only a spec /fabrik-spec sized small may skip "
        "/fabrik-spec-review (D10); converge the spec first, or plan it at full profile"
    ]


def spec_text_for(plan_text: str, root: Path, plan_dir: Path | None = None) -> str | None:
    """The text of the spec a plan's header `Spec:` field cites, or None (no field, no file).

    A `docs/…` path resolves against `root`; any other path (a relative link) against
    `plan_dir`, the plan file's directory, when given, then against `root`.
    """
    return resolve_spec(plan_text, root, plan_dir)[0]


def spec_citations(plan_text: str) -> list[str]:
    """The spec paths a plan's header `Spec:` field cites, in order, each once — a markdown
    link's target is also a bare path inside the same value, and is still ONE citation."""
    zone = header_zone(plan_text)
    m = _SPEC_FIELD_RE.search(zone)
    if m is None:
        m = next(
            (x for x in _SPEC_MIDLINE_RE.finditer(zone) if _PATHLIKE_RE.search(x.group("val"))),
            None,
        )
    if m is None:
        return []
    return list(
        dict.fromkeys(_LINK_TARGET_RE.findall(m.group("val")) + _PATH_RE.findall(m.group("val")))
    )


def _inside(cite: str, root: Path) -> str | None:
    """An ABSOLUTE cite relativised to `root` (as written or resolved), or None outside it."""
    target = Path(os.path.normpath(cite))
    for base in dict.fromkeys((Path(os.path.normpath(root)), Path(root).resolve())):
        try:
            return target.relative_to(base).as_posix()
        except ValueError:
            continue
    return None


def resolve_spec(
    plan_text: str, root: Path, plan_dir: Path | None = None
) -> tuple[str | None, str | None]:
    """`(spec text, None)`, or `(None, why it could not be read)` — the D10 reader. An absolute
    cite inside `root` reads as its repo-relative path; one outside `root` is never read."""
    cites = spec_citations(plan_text)
    if not cites:
        return None, "no spec citation in a header `Spec:` field"
    for cite in cites:
        if cite.startswith("/"):
            rel = _inside(cite, root)
            if rel is None:
                continue
            cite = rel
        bases = [root] if cite.startswith("docs/") else [*([plan_dir] if plan_dir else []), root]
        for base in bases:
            try:
                # normpath: a `../` link resolves lexically, as a markdown renderer does
                target = Path(os.path.normpath(base / cite))
                return target.read_text(encoding="utf-8", errors="replace"), None
            except OSError:
                continue
    return None, f"the cited spec {cites[0]} does not exist"


def lane_findings(text: str, path: Path, root: Path | None) -> list[str]:
    """Both D10/D11 rules for one plan file — the ONE entry point both graders call.

    Graded only when `path` is dated on or after the rollout. Inside a dated plan-set directory
    only the same-stem spine and the `T##[a-z]?-*.md` tickets are graded (a README or notes file
    there is skipped); a ticket is graded by its field line only, never by Profile. `root` is the
    repo the cited spec resolves against (None: the Size-small rule is skipped).
    """
    plan_date = plan_date_of(path)
    if not is_graded(plan_date):
        return []
    tm = _TICKET_NAME_RE.match(path.name)
    in_set = _DATE_PREFIX_RE.match(path.parent.name) is not None
    is_ticket = bool(tm) and in_set
    if in_set and not is_ticket and path.stem != path.parent.name:
        return []  # inside a plan set only the same-stem spine and the T## tickets are graded
    label = tm.group(1) if (tm and is_ticket) else "plan"
    found = appetite_findings(text, plan_date, label=label, ticket=is_ticket)
    if root is not None and not is_ticket:
        spec_text, missing = resolve_spec(text, root, path.parent)
        found += small_profile_findings(text, spec_text, missing=missing)
    return found
