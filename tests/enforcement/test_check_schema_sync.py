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
    assert c._dropped_tables(["alembic/versions/0007_drop.py"], str(r)) == {"password_reset_tokens"}


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
    (tmp_path / "docs" / "data-contract.md").write_text(
        "Status: FROZEN v9\n- users\n", encoding="utf-8"
    )
    monkeypatch.setattr(c, "_repo_root", lambda: str(tmp_path))
    c.warn_if_data_contract_stale(["alembic/versions/0008_add.py"])  # must NOT raise
    assert "WARN" in capsys.readouterr().out


def test_a_sql_migration_counts(  # youtube 01M180Z9: reproduced with 3 staged .sql migrations
) -> None:
    """The .py suffix gate hardcoded one language's extension for a check whose own
    MIGRATION_DIRS already generalizes the directory — a project on plain .sql
    migrations (youtube: migrations/044-046.sql, `users` gaining 7 real columns while
    data-contract.md asserted one 'does not exist') never tripped the staleness WARN."""
    assert c.migration_added(["migrations/044_add_consent.sql"])
    assert c.migration_added(["server/migrations/0002_users.sql"])
    assert not c.migration_added(["migrations/notes.md"])  # still no false positives


# ── iterative_image_editor 01M3WW5PFN (W-62875be3): a table-declaring module is a model by CONTENT, and a change
# is a change of the table STRUCTURE, never a regex over diff lines ─────────────────────────────────────────────
import subprocess  # noqa: E402

import pytest  # noqa: E402

DB_PY = """from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pydantic import BaseModel


class Base(DeclarativeBase):
    pass


class Broll(Base):
    __tablename__ = "broll"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    def label(self) -> str:
        return self.provider


class Other(Base):
    __tablename__ = "other"
    id: Mapped[int] = mapped_column(primary_key=True)


class BrollOut(BaseModel):
    provider: str
"""


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A real repository: the gate reads the index and HEAD, so nothing short of git exercises it."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "src" / "media").mkdir(parents=True)
    (tmp_path / "src" / "media" / "db.py").write_text(DB_PY, encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _stage(repo: Path, rel: str, text: str | None) -> int:
    p = repo / rel
    if text is None:
        _git(repo, "rm", "-q", rel)
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        _git(repo, "add", rel)
    return c.main()


def test_a_table_added_to_a_db_module_without_a_migration_fails(repo):
    text = (
        DB_PY
        + '\n\nclass New(Base):\n    __tablename__ = "new"\n    id: Mapped[int] = mapped_column(primary_key=True)\n'
    )
    assert _stage(repo, "src/media/db.py", text) == 1


def test_a_pydantic_class_in_a_table_declaring_module_passes(repo):
    text = DB_PY + "\n\nclass BrollIn(BaseModel):\n    provider: str\n    note: str\n"
    assert _stage(repo, "src/media/db.py", text) == 0


def test_a_rewrapped_column_passes(repo):
    text = DB_PY.replace(
        "mapped_column(\n        String(20),\n        nullable=False,\n    )",
        "mapped_column(String(20), nullable=False)",
    )
    assert text != DB_PY
    assert _stage(repo, "src/media/db.py", text) == 0


def test_a_type_change_on_a_wrapped_line_fails(repo):
    text = DB_PY.replace("        String(20),\n", "        String(40),\n")
    assert _stage(repo, "src/media/db.py", text) == 1


def test_a_column_moved_between_adjacent_classes_fails(repo):
    """Removed from one table and added, byte-identical, to the next — a whitespace-equal hunk, a real move."""
    base = DB_PY.replace(
        "    def label(self) -> str:\n        return self.provider\n\n\nclass Other(Base):\n",
        "    def label(self) -> str:\n        return self.provider\n    extra: Mapped[str] = mapped_column(String(5))\n\n\nclass Other(Base):\n",
    )
    _stage(repo, "src/media/db.py", base)
    _git(repo, "commit", "-q", "-m", "extra on broll")
    moved = base.replace(
        "    extra: Mapped[str] = mapped_column(String(5))\n\n\nclass Other(Base):\n",
        "\n\nclass Other(Base):\n    extra: Mapped[str] = mapped_column(String(5))\n",
    )
    assert moved != base
    assert _stage(repo, "src/media/db.py", moved) == 1


def test_renaming_a_model_whose_table_name_derives_from_it_fails(repo):
    """Flask-SQLAlchemy and SQLModel name the table after the class: the same fields under a new class name are a new
    table."""
    flask = "from flask_sqlalchemy import SQLAlchemy\ndb = SQLAlchemy()\n\n\nclass User(db.Model):\n    id = db.Column(db.Integer, primary_key=True)\n"
    _stage(repo, "src/app/models.py", flask)
    _git(repo, "commit", "-q", "-m", "user")
    assert _stage(repo, "src/app/models.py", flask.replace("class User(", "class Account(")) == 1


def test_table_args_gaining_an_index_fails(repo):
    text = DB_PY.replace(
        '    __tablename__ = "other"\n',
        '    __tablename__ = "other"\n    __table_args__ = (Index("ix_other_id", "id"),)\n',
    )
    assert _stage(repo, "src/media/db.py", text) == 1


def test_a_method_edit_inside_a_model_passes(repo):
    text = DB_PY.replace("return self.provider", "return self.provider.upper()")
    assert _stage(repo, "src/media/db.py", text) == 0


def test_deleting_a_table_declaring_module_fails(repo):
    assert _stage(repo, "src/media/db.py", None) == 1


def test_a_test_file_declaring_a_table_is_not_admitted(repo):
    assert _stage(repo, "tests/test_models.py", DB_PY) == 0


def test_a_flask_style_model_in_models_py_still_fails(repo):
    text = "from flask_sqlalchemy import SQLAlchemy\ndb = SQLAlchemy()\n\n\nclass User(db.Model):\n    id = db.Column(db.Integer, primary_key=True)\n"
    assert _stage(repo, "src/app/models.py", text) == 1


def test_an_unparseable_model_file_falls_back_to_the_diff_regex(repo):
    broken = DB_PY + "\n\nclass Broken(Base:\n    x = Column(Integer)\n"
    assert _stage(repo, "src/media/db.py", broken) == 1


def test_declares_table_and_schema_signature_are_pure():
    assert c.declares_table(DB_PY)
    assert not c.declares_table(
        "from pydantic import BaseModel\n\nclass X(BaseModel):\n    a: int\n"
    )
    assert not c.declares_table('__tablename__ = "x"\n')  # no ORM import
    assert c.schema_signature(DB_PY) == c.schema_signature(
        DB_PY.replace("        nullable=False,\n", "        nullable=False,  # kept\n")
    )
    assert c.schema_signature("def (:\n") is None


def test_a_pure_rename_of_a_model_module_passes(repo):
    """Review round 1 A-S3: HEAD has no blob at the new path, so the old side read as empty and a `git mv` with no
    edit failed as a brand-new table; the rename source is the old side."""
    _git(repo, "mv", "src/media/db.py", "src/media/orm.py")
    assert c.main() == 0


def test_a_rename_with_a_column_change_still_fails(repo):
    _git(repo, "mv", "src/media/db.py", "src/media/orm.py")
    text = DB_PY.replace("        String(20),\n", "        String(40),\n")
    assert _stage(repo, "src/media/orm.py", text) == 1


def test_a_model_class_inside_a_try_block_is_compared(repo):
    """Review round 1 A-S2: only module-level statements were read, so a class under try/except was invisible."""
    guarded = (
        DB_PY
        + '\n\ntry:\n    class Guarded(Base):\n        __tablename__ = "guarded"\n        id: Mapped[int] = mapped_column(primary_key=True)\nexcept ImportError:\n    pass\n'
    )
    _stage(repo, "src/media/db.py", guarded)
    _git(repo, "commit", "-q", "-m", "guarded")
    changed = guarded.replace(
        '        __tablename__ = "guarded"\n',
        '        __tablename__ = "guarded"\n        note: Mapped[str] = mapped_column(String(9))\n',
    )
    assert _stage(repo, "src/media/db.py", changed) == 1


def test_a_per_app_tests_module_is_not_admitted(repo):
    """Review round 1 A-S4: Django's per-app `tests.py` and a `conftest.py` are test files whatever their directory."""
    assert _stage(repo, "src/app/tests.py", DB_PY) == 0
    assert _stage(repo, "src/app/conftest.py", DB_PY) == 0


def test_a_pure_rename_passes_when_git_lists_both_paths(repo):
    """With `diff.renames=false` the staged list carries the old path as a deletion beside the new one; the rename
    source's deletion is no change, or a `git mv` with no edit would still fail through the old path."""
    _git(repo, "config", "diff.renames", "false")
    _git(repo, "mv", "src/media/db.py", "src/media/orm.py")
    assert "src/media/db.py" in c.get_staged_files()
    assert c.main() == 0


# --- intel 01M4TJJDC3: schema.sql alone must not satisfy a model whose project applies migrations ---

_NEW_TABLE = '\n\nclass Added(Base):\n    __tablename__ = "added"\n    id: Mapped[int] = mapped_column(primary_key=True)\n'


def _commit(repo: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "setup")


def _model_and_schema(repo: Path) -> None:
    (repo / "src" / "media" / "db.py").write_text(DB_PY + _NEW_TABLE, encoding="utf-8")
    (repo / "db").mkdir(exist_ok=True)
    (repo / "db" / "schema.sql").write_text("CREATE TABLE added (id int);\n", encoding="utf-8")
    _git(repo, "add", "src/media/db.py", "db/schema.sql")


def test_schema_sql_alone_fails_where_migrations_govern(repo, capsys):
    _commit(repo, {"alembic/versions/0001_init.py": "# init\n"})
    _model_and_schema(repo)
    assert c.main() == 1
    assert "alembic/versions/" in capsys.readouterr().out


def test_only_an_added_migration_under_the_governing_dir_satisfies(repo, capsys):
    _commit(
        repo,
        {
            "alembic/versions/0001_init.py": "# init\n",
            "other/migrations/0001_x.py": "# other project\n",
            "migrations/env.py": "# alembic env\n",
        },
    )
    _model_and_schema(repo)
    (repo / "other" / "migrations" / "0002_y.py").write_text("# y\n", encoding="utf-8")
    (repo / "migrations" / "env.py").write_text("# touched\n", encoding="utf-8")
    _git(repo, "add", "other/migrations/0002_y.py", "migrations/env.py")
    assert c.main() == 1, "another project's migration and env.py do not count"
    (repo / "alembic" / "versions" / "0002_added.py").write_text("# adds\n", encoding="utf-8")
    _git(repo, "add", "alembic/versions/0002_added.py")
    capsys.readouterr()
    assert c.main() == 0


def test_amending_a_migration_under_the_governing_dir_satisfies(repo):
    """Amending a not-yet-shipped migration in the same feature is common (seo 42d7000); the gate cannot
    tell it from an edit to an applied one, so an edit counts (D-row names the dodge)."""
    _commit(repo, {"alembic/versions/0001_init.py": "# init\n"})
    _model_and_schema(repo)
    (repo / "alembic" / "versions" / "0001_init.py").write_text("# amended\n", encoding="utf-8")
    _git(repo, "add", "alembic/versions/0001_init.py")
    assert c.main() == 0


def test_a_db_migrations_dir_governs_the_repo_root(repo):
    _commit(repo, {"db/migrations/versions/0001_init.py": "# init\n"})
    _model_and_schema(repo)
    assert c.main() == 1


def test_an_ungoverned_model_warns_and_passes(repo, capsys):
    _commit(
        repo,
        {
            "web/db/migrations/0001.sql": "-- web\n",
            "node_modules/x/migrations/0001.py": "# vendored\n",
        },
    )
    _model_and_schema(repo)
    assert c.main() == 0
    out = capsys.readouterr().out
    assert "WARN" in out and "web/db/migrations/" in out and "node_modules" not in out, out


def test_a_vendored_migration_dir_alone_changes_nothing(repo, capsys):
    _commit(repo, {"node_modules/x/migrations/0001.py": "# vendored\n"})
    _model_and_schema(repo)
    capsys.readouterr()
    assert c.main() == 0
    assert "migration" not in capsys.readouterr().out.lower()


def test_schema_sql_still_suffices_without_migrations(repo, capsys):
    _model_and_schema(repo)
    capsys.readouterr()
    assert c.main() == 0
    assert "migration" not in capsys.readouterr().out.lower()


def test_removing_a_dead_migration_dir_restores_the_schema_sql_pass(repo):
    _commit(repo, {"alembic/versions/0001_init.py": "# init\n"})
    _git(repo, "rm", "-q", "-r", "alembic")
    _model_and_schema(repo)
    assert c.main() == 0


def test_an_unrelated_migration_never_silences_the_ungoverned_warn(repo, capsys):
    """Another project's migration in the same commit is not this model's: the WARN still names the dirs."""
    _commit(repo, {"web/db/migrations/0001.sql": "-- web\n"})
    _model_and_schema(repo)
    (repo / "web" / "db" / "migrations" / "0002.sql").write_text("-- web 2\n", encoding="utf-8")
    _git(repo, "add", "web/db/migrations/0002.sql")
    assert c.main() == 0
    out = capsys.readouterr().out
    assert "WARN" in out and "web/db/migrations/" in out and "src/media/db.py" in out, out


def test_a_migration_renamed_into_the_governing_dir_satisfies(repo):
    """git reports a moved draft as R, not A or M; it is still a new file under the governing dir."""
    draft = "# draft migration\nrevision = '0002'\ndown_revision = '0001'\n"
    _commit(repo, {"alembic/versions/0001_init.py": "# init\n", "drafts/0002_added.py": draft})
    _model_and_schema(repo)
    _git(repo, "mv", "drafts/0002_added.py", "alembic/versions/0002_added.py")
    assert c.main() == 0


def test_a_non_ascii_model_path_is_still_checked(repo, capsys):
    """git quotes a non-ASCII path in plain output; read unquoted, the model change reaches the check."""
    _commit(repo, {"src café/db.py": DB_PY})
    assert _stage(repo, "src café/db.py", DB_PY + _NEW_TABLE) == 1
    assert "src café/db.py" in capsys.readouterr().out
