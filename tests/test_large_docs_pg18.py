"""T04b — the two large current-state docs say 18, not 16.

`docs/infrastructure/vps-complete-inventory.md` and `docs/traycer/fabrik-workflow.md` are too
large to share T04a's read budget, so they get their own narrow grader: every statement of the
CURRENT Postgres major (prose `PostgreSQL 16`, image tag `postgres:16`, or the pgvector tag
`pgvector:pg16`) must read 18 instead. History the docs quote (dated entries, "was", changelog-
style lines, quoted past probes) is explicitly exempt via a tiny, commented allowlist keyed on a
distinctive SUBSTRING of the line — never a line number, which drifts as the file is edited.

Wave-2 review D1 (CONFIRMED by mutation): the first cut of STALE_PATTERNS matched only the exact
spellings `PostgreSQL 16` / `postgres:16` / `pgvector:pg16`, so a respelling — `postgres 16`,
`pg16`, `PG16`, `postgres-16`, `PostgreSQL-16` — sailed through ungraded. The patterns below are
spelling-blind (case-insensitive, separator-insensitive between the word and the digits) and are
themselves proven red-on-mutation for each of the six respellings below, on a scratch copy of each
doc, before the fix (the broadened patterns) is trusted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

DOCS = [
    REPO / "docs" / "infrastructure" / "vps-complete-inventory.md",
    REPO / "docs" / "traycer" / "fabrik-workflow.md",
]

# Patterns that mean "the CURRENT Postgres major is 16" — prose (any spelling/separator between
# the word and the digits: space, colon, dash, underscore, or none) and the pgvector tag. Each is
# case-insensitive and word-boundary-anchored so it never fires on an unrelated "16" (a count, a
# date fragment, a checklist item number) that merely sits near the word "postgres" or "pg".
STALE_PATTERNS = [
    # PostgreSQL 16 / Postgres 16 / postgres-16 / PostgreSQL_16 / postgres:16 / PostgreSQL16 ...
    re.compile(r"\bpostgres(?:ql)?[\s:_-]*16\b", re.IGNORECASE),
    # pg16 / PG16 / pg-16 / pg_16 / pg 16 (but not e.g. "pg_isready" ... "16" elsewhere on the line)
    re.compile(r"\bpg[\s_-]?16\b", re.IGNORECASE),
    # pgvector/pgvector:pg16, pgvector:0.8.6-pg16, pgvector/pgvector:PG16, …
    re.compile(r"pgvector[:/][^\s|`]*pg16\b", re.IGNORECASE),
]

# Lines that are HISTORY (a dated entry, a "was", a quoted past probe) and are therefore never
# migrated to 18 even though they mention the old major. Keyed on a distinctive substring of the
# line's TEXT, never a line number (numbers drift). Keep this list tiny — a doc with a real history
# backlog needs more than one entry, but today neither doc has any such line for this pattern set.
HISTORY_ALLOWLIST: list[str] = [
    # (none yet — every current hit in these two docs states the CURRENT major, not history)
]

# The six respellings wave-2 review D1 confirmed slipped past the first (exact-spelling) cut of
# STALE_PATTERNS. Each must be caught regardless of which doc it lands in or what surrounds it.
RESPELLING_MUTATIONS = [
    "Postgres 16",
    "postgres 16",
    "pg16",
    "PG16",
    "postgres-16",
    "PostgreSQL-16",
]


def _offending_lines(text: str) -> list[str]:
    offenders = []
    for line in text.splitlines():
        if any(pattern.search(line) for pattern in STALE_PATTERNS):
            if any(allowed in line for allowed in HISTORY_ALLOWLIST):
                continue
            offenders.append(line)
    return offenders


def _offending_lines_in_file(path: Path) -> list[str]:
    return _offending_lines(path.read_text(encoding="utf-8"))


def test_docs_exist():
    for doc in DOCS:
        assert doc.is_file(), f"expected doc at {doc}"


def test_no_stale_postgres_16_claims():
    for doc in DOCS:
        offenders = _offending_lines_in_file(doc)
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


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
@pytest.mark.parametrize("mutation", RESPELLING_MUTATIONS)
def test_respelling_mutation_is_caught_on_a_scratch_copy(mutation, doc, tmp_path):
    """Red-on-mutation proof: each of the six respellings, appended to a SCRATCH copy of the real
    doc (never the tracked file), must trip the grader. This is the regression guard for D1 — a
    grader that only matched the exact phrase `PostgreSQL 16` passed green while these six sailed
    through untouched."""
    scratch = tmp_path / doc.name
    original = doc.read_text(encoding="utf-8")
    scratch.write_text(f"{original}\n{mutation} injected by the D1 regression probe\n", encoding="utf-8")

    offenders = _offending_lines_in_file(scratch)

    assert offenders, f"{doc.name}: mutation {mutation!r} was NOT caught — grader is still spelling-blind-blind"
    assert any(mutation.lower() in o.lower() for o in offenders)


def test_broadened_patterns_do_not_false_positive_on_unrelated_16s():
    """The two docs are full of unrelated "16"s (compose-stack counts, Prometheus job counts,
    checklist item numbers, dates like 2026-06-15/16). None of those sit next to "postgres" or
    "pg" closely enough to trip the spelling-blind patterns above — this test proves the
    broadening in this change didn't trade false negatives for false positives."""
    for doc in DOCS:
        offenders = _offending_lines_in_file(doc)
        assert not offenders, (
            f"{doc.relative_to(REPO)}: broadened STALE_PATTERNS now false-positive on an "
            f"unrelated '16': {offenders}"
        )
