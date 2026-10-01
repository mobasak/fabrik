# AFTER-EDIT: tests/test_plan_appetite_size.py, scripts/enforcement/check_plan_tickets.py, scripts/enforcement/check_plan_quality.py
"""Two plan rules shared by the plan graders (spec 2026-10-02-fabrik-task-feature-lane, D10/D11).

- **Appetite (D11).** A plan dated on or after ``LANE_ROLLOUT_DATE`` declares
  ``Appetite: <positive integer minutes>`` in every phase (a monolith's ``## Phase …``
  sections) or in every ticket (a plan set's ``T##-<slug>.md`` files). A spine declares
  none — its tickets carry it. Plans dated before the rollout are never re-graded.
- **Size-small (D10).** A ``Profile: small`` plan whose spec is ``Status: DRAFT`` (or its
  synonym PLANNED) must have a spec carrying ``Size: small`` in its header: that line is
  what lets a small spec skip ``/fabrik-spec-review``. A CONVERGED spec passes either way.

Both graders (``check_plan_tickets.py`` for sets, ``check_plan_quality.py`` per file) call
these functions, so neither grader imports the other. ``PROFILE_RE`` lives here and
``check_plan_tickets`` re-exports it, so the profile both rules key on is one regex.

The rules are pure text functions; ``plan_date_of`` and ``spec_text_for`` are the two
small readers the graders use to feed them.

COBRA (you get the behavior you measure): the cheapest way to satisfy the Appetite rule
without the outcome is a uniformly huge number (``Appetite: 9999``) — it passes the
grader and never trips the 2x re-plan order. The grader cannot see that; the
counter-measure is the over-appetite record at close (``over_appetite_phases``, D11),
whose meaning a padded appetite dilutes in plain sight, and plan-review reading the
number against the phase. The cheapest way past the Size rule is writing ``Size: small``
on a large spec; the counter-measure is D10's kill rule (a plan larger than the estimate
sends the spec back to ``/fabrik-spec-review``, and > 1 in 3 sent back reverts D10).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

LANE_ROLLOUT_DATE = "2026-10-03"

# `Profile: small` — the spine's opt-in to the INLINE execution profile. Bold-tolerant like
# the graders' Status regexes; callers search it on a header zone only (see `header_zone`).
PROFILE_RE = re.compile(
    r"^\s*(?:[-*>]\s+)?\*{0,2}Profile\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*\*{0,2}(small)\*{0,2}"
    r"[^\S\n]*$",
    re.I | re.M,
)
# `Appetite: 60`, `**Appetite:** 45`, `- Appetite: 30 min` — the VALUE is graded separately so
# a present-but-invalid line (`Appetite: soon`, `Appetite: 0`) is named as such. A blockquoted
# line never counts (a quoted example is not a declaration).
APPETITE_LINE_RE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+)?\*{0,2}Appetite\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}(?P<val>[^\n]*?)[^\S\n]*$",
    re.I | re.M,
)
_APPETITE_VALUE_RE = re.compile(r"^\*{0,2}(\d+)\*{0,2}(?:[^\S\n]*(?:min|mins|minutes))?$", re.I)
# `Size: small` / `Size: small (≈300 lines, 4 files)` — a spec HEADER field (D10).
SIZE_SMALL_RE = re.compile(
    r"^\s*(?:[-*]\s+)?\*{0,2}Size\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*small\b", re.I | re.M
)
_SPEC_STATUS_RE = re.compile(
    r"^\s*(?:[-*]\s+)?\*{0,2}Status\*{0,2}[^\S\n]*:[^\S\n]*\*{0,2}[^\S\n]*(?:✅[^\S\n]*)?"
    r"\*{0,2}[^\S\n]*(DRAFT|PLANNED|CONVERGED|IN-PROGRESS|EXECUTED|BLOCKED)\b",
    re.I | re.M,
)
_SPEC_FIELD_RE = re.compile(
    r"^\s*(?:[-*]\s+)?\*{0,2}(?:Design spec|Spec)\*{0,2}[^\S\n]*:[^\S\n]*(?P<val>[^\n]*)$",
    re.I | re.M,
)
_SPEC_CITE_RE = re.compile(r"docs/superpowers/specs/[\w./-]+\.md")
_SPINE_MARKER_RE = re.compile(r"^##\s+Ticket Board\b", re.I | re.M)
_PHASE_HEADING_RE = re.compile(r"^(?P<hashes>#{2,3})[ \t]+(?P<title>Phase\b[^\n]*)$", re.I | re.M)
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})[ \t]", re.M)
_BACKTICK_FENCE_RE = re.compile(r"^[ \t]*`{3,}[^\n]*\n.*?^[ \t]*`{3,}[ \t]*$", re.M | re.S)
_TILDE_FENCE_RE = re.compile(r"^[ \t]*~{3,}[^\n]*\n.*?^[ \t]*~{3,}[ \t]*$", re.M | re.S)
_OPEN_FENCE_RE = re.compile(r"^[ \t]*(?:`{3,}|~{3,})[^\n]*$", re.M)
_FIRST_SECTION_RE = re.compile(r"^#{2,6}\s", re.M)
_DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-plan")


def strip_fences(text: str) -> str:
    """Remove fenced blocks; an UNCLOSED opener swallows the rest (fail-closed: a quoted
    `Appetite:` inside a dangling fence never satisfies a phase)."""
    text = _TILDE_FENCE_RE.sub("", _BACKTICK_FENCE_RE.sub("", text))
    dangling = _OPEN_FENCE_RE.search(text)
    return text[: dangling.start()] if dangling else text


def header_zone(text: str) -> str:
    """Everything before the first `##` heading, fences removed — where header fields live."""
    m = _FIRST_SECTION_RE.search(text)
    return strip_fences(text[: m.start()] if m else text)


def plan_date_of(path: Path) -> str | None:
    """The `YYYY-MM-DD` of a monolith (its file name) or of a set member (its directory)."""
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
    plan_text: str, plan_date: str | date | None, *, label: str = "plan"
) -> list[str]:
    """D11: the Appetite refusals for one plan file, empty when it complies or predates the rollout.

    A spine (`## Ticket Board`) owes none itself. A monolith with `## Phase …` headings owes one
    per phase, each finding naming the phase. Any other file — a ticket, or a phase-less
    monolith — owes one, named by `label` (the ticket id).
    """
    if not is_graded(plan_date):
        return []
    scan = strip_fences(plan_text)
    if _SPINE_MARKER_RE.search(scan):
        return []
    phases = list(_PHASE_HEADING_RE.finditer(scan))
    if not phases:
        found = _unit_finding(label, scan)
        return [found] if found else []
    findings: list[str] = []
    for ph in phases:
        level = len(ph.group("hashes"))
        end = len(scan)
        for h in _HEADING_RE.finditer(scan, ph.end()):
            if len(h.group("hashes")) <= level:
                end = h.start()
                break
        found = _unit_finding(ph.group("title").strip()[:80], scan[ph.end() : end])
        if found:
            findings.append(found)
    return findings


def small_profile_findings(plan_text: str, spec_text: str | None) -> list[str]:
    """D10: refuse a `Profile: small` plan whose spec is DRAFT/PLANNED without `Size: small`.

    `spec_text` is None when the plan cites no spec or the spec is unreadable — nothing to
    grade here (a missing spec is other gates' finding).
    """
    if spec_text is None or not PROFILE_RE.search(header_zone(plan_text)):
        return []
    spec_header = header_zone(spec_text)
    status = _SPEC_STATUS_RE.search(spec_header)
    if not status or status.group(1).upper() not in ("DRAFT", "PLANNED"):
        return []
    if SIZE_SMALL_RE.search(spec_header):
        return []
    return [
        "`Profile: small` plan cites a DRAFT spec without a `Size: small` header line — only a "
        "spec /fabrik-spec sized small may skip /fabrik-spec-review (D10); converge the spec "
        "first, or plan it at full profile"
    ]


def spec_text_for(plan_text: str, root: Path) -> str | None:
    """The text of the spec a plan's `Spec:` header field cites, or None (no field, no file)."""
    m = _SPEC_FIELD_RE.search(header_zone(plan_text))
    if not m:
        return None
    cite = _SPEC_CITE_RE.search(m.group("val"))
    if not cite:
        return None
    path = root / cite.group(0)
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
