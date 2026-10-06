"""T04b — the two large current-state docs say 18, not 16.

`docs/infrastructure/vps-complete-inventory.md` and `docs/traycer/fabrik-workflow.md` are too
large to share T04a's read budget, so they get their own narrow grader: every statement of the
CURRENT Postgres major (prose `PostgreSQL 16`, image tag `postgres:16`, or the pgvector tag
`pgvector:pg16`) must read 18 instead. History the docs quote (dated entries, "was", changelog-
style lines, quoted past probes) is explicitly exempt via a tiny, commented allowlist keyed on a
distinctive SUBSTRING of the line — never a line number, which drifts as the file is edited.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DOCS = [
    REPO / "docs" / "infrastructure" / "vps-complete-inventory.md",
    REPO / "docs" / "traycer" / "fabrik-workflow.md",
]

# Patterns that mean "the CURRENT Postgres major is 16" — prose, hub image tag, pgvector tag.
STALE_PATTERNS = [
    re.compile(r"postgresql\s*16", re.IGNORECASE),
    re.compile(r"postgres:16"),
    re.compile(r"pgvector[:/].*?pg16"),
]

# Lines that are HISTORY (a dated entry, a "was", a quoted past probe) and are therefore never
# migrated to 18 even though they mention the old major. Keyed on a distinctive substring of the
# line's TEXT, never a line number (numbers drift). Keep this list tiny — a doc with a real history
# backlog needs more than one entry, but today neither doc has any such line for this pattern set.
HISTORY_ALLOWLIST: list[str] = [
    # (none yet — every current hit in these two docs states the CURRENT major, not history)
]


def _offending_lines(text: str) -> list[str]:
    offenders = []
    for line in text.splitlines():
        if any(pattern.search(line) for pattern in STALE_PATTERNS):
            if any(allowed in line for allowed in HISTORY_ALLOWLIST):
                continue
            offenders.append(line)
    return offenders


def test_docs_exist():
    for doc in DOCS:
        assert doc.is_file(), f"expected doc at {doc}"


def test_no_stale_postgres_16_claims():
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        offenders = _offending_lines(text)
        assert not offenders, (
            f"{doc.relative_to(REPO)} still states Postgres 16 as current "
            f"(not in HISTORY_ALLOWLIST): {offenders}"
        )


def test_pgvector_tag_is_fully_pinned_to_pg18():
    """The pgvector tag must become `pgvector/pgvector:0.8.6-pg18`, not a bare `:pg18`."""
    workflow = REPO / "docs" / "traycer" / "fabrik-workflow.md"
    text = workflow.read_text(encoding="utf-8")
    assert "pgvector/pgvector:0.8.6-pg18" in text
    assert "pgvector/pgvector:pg16" not in text
