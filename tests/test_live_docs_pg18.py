"""T04a — the hub's live pins and current-state docs no longer cite PG16.

Spec: docs/superpowers/specs/2026-10-06-postgresql-18-fleet-upgrade-design.md
§ Documentation landing sites. Behavior Contract
(docs/development/plans/2026-10-06-plan-1-postgresql-18-upgrade/T04a-live-pins-and-docs.md):
given the files this ticket owns, when they are searched for ``PostgreSQL 16``,
``Postgres 16``, ``postgres:16`` or ``PG16``, none matches.

This file is deliberately excluded from its own search — it necessarily quotes
every banned string above.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# The five files T04a owns, excluding this test file itself (which quotes the
# banned strings by necessity).
OWNED_FILES = [
    "tests/test_app_role_real_pg.py",
    "scripts/container_images.py",
    "scripts/generate_vps_inventory.py",
    "README.md",
    "docs/workstation/session-recall.md",
]

BANNED_STRINGS = [
    "PostgreSQL 16",
    "Postgres 16",
    "postgres:16",
    "PG16",
]


@pytest.mark.parametrize("relpath", OWNED_FILES)
def test_owned_file_has_no_pg16_reference(relpath: str) -> None:
    path = REPO_ROOT / relpath
    text = path.read_text(encoding="utf-8")
    hits = [needle for needle in BANNED_STRINGS if needle in text]
    assert not hits, f"{relpath} still references PG16 via {hits!r}"
