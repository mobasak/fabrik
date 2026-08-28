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


# ── a landed DROP against a FROZEN contract (transdoc 2026-08-28, commit a059c29) ───────────────
def _repo(tmp: Path, migration: str, contract: str | None) -> Path:
    (tmp / "alembic" / "versions").mkdir(parents=True)
    (tmp / "alembic" / "versions" / "0007_drop.py").write_text(migration, encoding="utf-8")
    if contract is not None:
        (tmp / "docs").mkdir(exist_ok=True)
        (tmp / "docs" / "data-contract.md").write_text(contract, encoding="utf-8")
    return tmp


def test_alembic_drop_table_is_parsed(tmp_path):
    r = _repo(tmp_path, 'def upgrade():\n    op.drop_table("email_verify_tokens")\n', None)
    assert c._dropped_tables(["alembic/versions/0007_drop.py"], str(r)) == {"email_verify_tokens"}


def test_raw_sql_drop_table_is_parsed(tmp_path):
    r = _repo(tmp_path, 'op.execute("DROP TABLE IF EXISTS password_reset_tokens")\n', None)
    assert c._dropped_tables(["alembic/versions/0007_drop.py"], str(r)) == {
        "password_reset_tokens"
    }


def test_only_tables_the_contract_still_declares_are_returned(tmp_path):
    """The precision that keeps this narrow: a dropped table the contract never mentioned is not
    staleness — the contract is simply already correct about it."""
    r = _repo(tmp_path, "x", "Status: FROZEN v9\n- email_verify_tokens\n- users\n")
    got = c._contract_declares(str(r), {"email_verify_tokens", "password_reset_tokens"})
    assert got == {"email_verify_tokens"}


def test_a_substring_table_name_does_not_false_match(tmp_path):
    """`users` must not be matched by a contract mentioning `users_archive` alone — a false FAIL
    here blocks a correct commit, which is the expensive direction for a hard rule."""
    r = _repo(tmp_path, "x", "Status: FROZEN\n- users_archive\n")
    assert c._contract_declares(str(r), {"users"}) == set()


def test_a_non_migration_file_is_never_scanned(tmp_path):
    """Scope: only migration paths. A `drop_table` mentioned in a doc or a test is not a landed
    drop, and scanning everything would manufacture failures from prose."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.md").write_text('op.drop_table("users")', encoding="utf-8")
    assert c._dropped_tables(["docs/notes.md"], str(tmp_path)) == set()


def test_an_unreadable_migration_does_not_raise(tmp_path):
    """A blocking rule must not die on a missing file — that would fail a tree for the wrong reason."""
    assert c._dropped_tables(["alembic/versions/absent.py"], str(tmp_path)) == set()


def test_a_declared_and_dropped_table_actually_fails_the_check(tmp_path, monkeypatch, capsys):
    """THE WIRING — neutering the call site (`stale = set()`) left all 11 tests green, because they
    covered the two helpers and not the path that uses them. Fourth time this gap appeared today,
    which is why it gets its own test rather than a note."""
    import pytest

    (tmp_path / "alembic" / "versions").mkdir(parents=True)
    (tmp_path / "alembic" / "versions" / "0007_drop.py").write_text(
        'def upgrade():\n    op.drop_table("email_verify_tokens")\n', encoding="utf-8"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "data-contract.md").write_text(
        "Status: FROZEN v9\n- email_verify_tokens\n", encoding="utf-8"
    )
    monkeypatch.setattr(c, "_repo_root", lambda: str(tmp_path))
    with pytest.raises(SystemExit) as exc:
        c.warn_if_data_contract_stale(["alembic/versions/0007_drop.py"])
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "email_verify_tokens" in out, out
    assert "FAIL" in out, out


def test_an_additive_migration_still_only_warns(tmp_path, monkeypatch, capsys):
    """The narrowing that makes this safe to make hard: a contract legitimately LEADS the schema
    mid-plan (the pipeline order Fabrik prescribes), so a migration that adds — or drops something
    the contract never declared — must not fail. Only the landed-drop direction is unambiguous."""
    (tmp_path / "alembic" / "versions").mkdir(parents=True)
    (tmp_path / "alembic" / "versions" / "0008_add.py").write_text(
        'def upgrade():\n    op.create_table("new_thing")\n', encoding="utf-8"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "data-contract.md").write_text("Status: FROZEN v9\n- users\n", encoding="utf-8")
    monkeypatch.setattr(c, "_repo_root", lambda: str(tmp_path))
    c.warn_if_data_contract_stale(["alembic/versions/0008_add.py"])  # must NOT raise
    assert "WARN" in capsys.readouterr().out
