"""check_schema_sync — the drift gate must see schemas and migrations at ANY depth.

Regression guard for the transdoc upstream proposal (2026-08-21): the saas-skeleton
scaffold itself emits server/db/schema.sql, and the exact-membership test silently
disarmed the gate on the scaffold's own layout.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "enforcement"))

import check_schema_sync as c  # noqa: E402


def test_schema_under_a_subdirectory_is_detected() -> None:
    """saas-skeleton emits server/db/schema.sql — an equality test missed it."""
    assert c.schema_file_updated(["server/db/schema.sql"])
    assert c.schema_file_updated(["api/db/schema.sql"])
    assert c.schema_file_updated(["services/core/db/schema.sql"])


def test_canonical_schema_shapes_still_match() -> None:
    """Strictly widening — every previously-true input stays true."""
    for p in c.SCHEMA_FILES:
        assert c.schema_file_updated([p]), p


def test_no_new_schema_false_positives() -> None:
    """The separator anchor keeps near-misses out."""
    assert not c.schema_file_updated(["my_schema.sql"])
    assert not c.schema_file_updated(["not_a_db/schema.sql.bak"])
    assert not c.schema_file_updated(["docs/schema.sql.md"])


def test_migration_under_a_subdirectory_is_detected() -> None:
    """The twin bug: startswith missed server/migrations/…"""
    assert c.migration_added(["server/migrations/0001_init.py"])
    assert c.migration_added(["api/alembic/versions/abc123_add.py"])
    assert c.migration_added(["migrations/0001_init.py"])  # canonical still works


def test_migration_no_false_positives() -> None:
    assert not c.migration_added(["server/migrations/notes.md"])
    assert not c.migration_added(["mymigrations/0001.py"])
