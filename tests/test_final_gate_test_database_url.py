# AFTER-EDIT: scripts/final_gate.py
"""The gate's pytest leg runs the DB-backed suite when the project names a disposable test DB.

`final_gate.py` ran `pytest tests/` with the ambient environment only, so every test gated on
TEST_DATABASE_URL skipped and the leg read green — 134 skipped in trade-intelligence's closing
gate on 2026-09-30, where two real DB failures escaped a green gate (mail 01M3S2A3, W-e93160e3).
The leg now takes the key from the environment, then the project's own `.env.local`, then `.env`;
a value read from a FILE must name a disposable database; the value never reaches the row or the
JSON; an opt-in sentinel makes a missing key red. Each test drives the real pytest leg
(`_run_pytest_suite`) against a throwaway project under tmp_path — never this repo's own suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import final_gate as fg  # noqa: E402

KEY = "TEST_DATABASE_URL"
SECRET = "s3cr3tPassw0rd"
GOOD = f"postgresql://tester:{SECRET}@localhost:5432/shop_test"

# A one-test suite that skips without the key and, with it, prints the URL and FAILS — so a
# passed value is observable (red, not skipped) and any echo of it is in pytest's output.
DB_TEST = f'''
import os, pytest
URL = os.getenv("{KEY}", "")

@pytest.mark.skipif(not URL, reason="needs {KEY}")
def test_db():
    print("connecting to", URL)
    raise AssertionError("connection refused: " + URL)
'''


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_db.py").write_text(DB_TEST, encoding="utf-8")
    monkeypatch.setattr(fg, "PROJECT_ROOT", root)
    monkeypatch.setattr(fg, "PYTHON", sys.executable)
    monkeypatch.delenv(KEY, raising=False)
    monkeypatch.chdir(root)
    return root


def _row() -> tuple[str, bool, str]:
    return fg._run_pytest_suite()


def test_the_pytest_leg_takes_test_database_url_from_env_files_in_order(project, monkeypatch):
    name, ok, text = _row()
    assert ok and "SKIPPED 1" in text, (name, text)  # no key anywhere: the old skip-green

    (project / ".env").write_text(f"{KEY}={GOOD}\n", encoding="utf-8")
    name, ok, text = _row()
    assert not ok and name == "pytest" and "from .env" in text, (name, text)
    assert "TEST_DATABASE_URL from .env (value redacted)." in text, (
        text
    )  # the one-key note, unchanged

    (project / ".env.local").write_text(
        f"{KEY}=postgresql://u:p@localhost/other_test\n", encoding="utf-8"
    )
    assert "from .env.local" in _row()[2]

    monkeypatch.setenv(KEY, "postgresql://env:x@localhost/env_test")
    name, ok, text = _row()
    assert "from the environment" in text, text


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://u:p@localhost/shop",  # a dev database
        "postgresql://u:p@localhost/shop_testing",  # suffix, not ending
    ],
)
def test_a_non_disposable_file_value_is_refused(project, value):
    (project / ".env").write_text(f"{KEY}={value}\n", encoding="utf-8")
    name, ok, text = _row()
    assert not ok and "REFUSED" in name, (name, text)
    assert value not in text and "p@localhost" not in text


def test_a_value_equal_to_the_files_database_url_is_refused(project):
    same = "postgresql://u:p@localhost/shop_test"
    (project / ".env").write_text(f"DATABASE_URL={same}\n{KEY}={same}\n", encoding="utf-8")
    name, ok, _ = _row()
    assert not ok and "REFUSED" in name, name


def test_dotenv_value_parses_one_key(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "\n"
        "OTHER=nope\n"
        f"{KEY}=first_test\n"
        f"export {KEY}='quoted # kept_test'\n"
        f'{KEY}="postgresql://u:p@h/db_test"  # trailing comment\n',
        encoding="utf-8",
    )
    assert fg._dotenv_value(env, KEY) == "postgresql://u:p@h/db_test"
    env.write_text(f"{KEY}=postgresql://u:p@h/x_test # local note\n", encoding="utf-8")
    assert fg._dotenv_value(env, KEY) == "postgresql://u:p@h/x_test"
    env.write_text(f"export {KEY}='a # b'\n", encoding="utf-8")
    assert fg._dotenv_value(env, KEY) == "a # b"
    env.write_text(f"{KEY}=\n", encoding="utf-8")
    assert fg._dotenv_value(env, KEY) is None
    assert fg._dotenv_value(tmp_path / "missing", KEY) is None


def test_the_url_is_redacted_from_the_row_and_json(project):
    (project / ".env").write_text(f"{KEY}={GOOD}\n", encoding="utf-8")
    name, ok, text = _row()
    assert not ok, (name, text)
    assert "<TEST_DATABASE_URL>" in text, text
    assert GOOD not in text and SECRET not in text, text
    clipped = fg.clip_output(text)
    assert SECRET not in str(clipped)


def test_the_sentinel_makes_a_missing_key_red(project):
    (project / ".fabrik").mkdir()
    (project / ".fabrik" / "require-test-database-url").touch()
    name, ok, text = _row()
    assert not ok and "DB SUITE NOT RUN" in name, (name, text)
    assert str(project / ".env.local") in text and str(project / ".env") in text


def test_the_skip_advisory_names_the_missing_key_only_for_db_gated_suites(project):
    _, ok, text = _row()
    assert ok and KEY in text and str(project / ".env") in text, text

    (project / "tests" / "test_db.py").write_text(
        'import pytest\n\n@pytest.mark.skip(reason="unrelated")\ndef test_x():\n    pass\n'
        "\n# docs mention TEST_DATABASE_URL here only\n",
        encoding="utf-8",
    )
    _, ok, text = _row()
    assert ok and "SKIPPED 1" in text and "set in neither" not in text, text


def test_a_bom_does_not_hide_the_key_on_line_one(tmp_path):
    env = tmp_path / ".env.local"
    env.write_bytes(f"﻿{KEY}=postgresql://u:p@h/x_test\n".encode())
    assert fg._dotenv_value(env, KEY) == "postgresql://u:p@h/x_test"


@pytest.mark.parametrize(
    "value",
    [
        "sqlite:///./data/x_test.db",
        "postgresql://u:p@h/shop_TEST",
        "sqlite:////tmp/run_scratch.sqlite3",
        "postgresql://u:p@h/a.b_test",
    ],
)
def test_sqlite_files_and_case_count_as_disposable(project, value):
    (project / ".env").write_text(f"{KEY}={value}\n", encoding="utf-8")
    tdb, source, refusal, _ = fg._resolve_test_database_url(project)
    assert (tdb, source, refusal) == (value, ".env", None)


def test_a_short_password_printed_alone_is_redacted(project):
    (project / ".env").write_text(f"{KEY}=postgresql://u:ab@localhost/x_test\n", encoding="utf-8")
    (project / "tests" / "test_db.py").write_text(
        "import os\nfrom urllib.parse import urlsplit\n\n"
        f"def test_pw():\n    assert urlsplit(os.environ['{KEY}']).password == 'zz'\n",
        encoding="utf-8",
    )
    name, ok, text = _row()
    assert not ok and "'ab'" not in text and "<password>" in text, text


def test_a_one_letter_password_does_not_mangle_an_unrelated_failure(project):
    (project / ".env").write_text(f"{KEY}=postgresql://u:e@localhost/x_test\n", encoding="utf-8")
    (project / "tests" / "test_db.py").write_text(
        "def test_something_unrelated():\n"
        "    assert 1 == 2, 'API did not return the expected message'\n",
        encoding="utf-8",
    )
    name, ok, text = _row()
    assert not ok and "API did not return the expected message" in text, text


@pytest.mark.parametrize("db", ["myapp_test.replica", "prod.x_test.bak"])
def test_a_dot_suffix_is_not_a_sqlite_extension(project, db):
    (project / ".env").write_text(f"{KEY}=postgresql://u:p@h/{db}\n", encoding="utf-8")
    assert fg._resolve_test_database_url(project)[2] is not None, db


def test_a_dotted_scratch_name_is_disposable(project):
    (project / ".env").write_text(f"{KEY}=postgresql://u:p@h/shop.scratch\n", encoding="utf-8")
    assert fg._resolve_test_database_url(project)[2] is None


def test_a_short_password_in_pytests_own_diff_line_is_redacted(project):
    (project / ".env").write_text(f"{KEY}=postgresql://u:ab@localhost/x_test\n", encoding="utf-8")
    (project / "tests" / "test_db.py").write_text(
        "import os\nfrom urllib.parse import urlsplit\n\n"
        f"def test_pw():\n    assert urlsplit(os.environ['{KEY}']).password == 'zz'\n",
        encoding="utf-8",
    )
    _, ok, text = _row()
    import re

    assert not ok and not re.search(r"[+-] ab$", text, re.MULTILINE), text


APP_KEY = "TEST_APP_DATABASE_URL"
APP_SECRET = "appR0lePassw0rd"
APP_GOOD = f"postgresql://app_user:{APP_SECRET}@localhost:5432/shop_test"
# An RLS-style suite: it connects as the app role and fails printing the URL, so a passed value is
# observable and any echo of it lands in pytest's output (brand-identiy-creator 01M473WBS4VSQPQ7)
APP_TEST = f'''
import os, pytest
URL = os.getenv("{APP_KEY}", "")

@pytest.mark.skipif(not URL, reason="needs {APP_KEY}")
def test_rls():
    print("connecting as the app role to", URL)
    raise AssertionError("rls: " + URL)
'''


@pytest.fixture
def rls_project(project, monkeypatch):
    (project / "tests" / "test_db.py").unlink()
    (project / "tests" / "test_rls.py").write_text(APP_TEST, encoding="utf-8")
    for k in (APP_KEY, "TEST_MIGRATION_DATABASE_URL", "TEST_REDIS_URL"):
        monkeypatch.delenv(k, raising=False)
    return project


def test_the_app_role_key_reaches_the_suite_from_an_env_file_redacted(rls_project):
    (rls_project / ".env").write_text(
        f"{APP_KEY}={APP_GOOD}\nTEST_REDIS_URL=redis://localhost:6379/9\n", encoding="utf-8"
    )
    name, ok, text = _row()
    assert not ok and name == "pytest" and "test_rls" in text, (name, text)  # ran, not skipped
    assert f"{APP_KEY} from .env" in text, text
    assert APP_GOOD not in text and APP_SECRET not in text, text
    assert "<TEST_APP_DATABASE_URL>" in text and "(value redacted)." in text, text  # its own label
    values, notes, refusal = fg._resolve_extra_test_database_urls(rls_project)
    assert refusal is None and set(values) == {APP_KEY}, (values, notes)  # TEST_REDIS_URL is not


def test_a_non_disposable_app_role_value_is_refused(rls_project):
    bad = "postgresql://app_user:p@localhost/shop"
    (rls_project / ".env").write_text(f"{APP_KEY}={bad}\n", encoding="utf-8")
    name, ok, text = _row()
    assert not ok and "REFUSED" in name and APP_KEY in text, (name, text)
    assert bad not in text and "p@localhost" not in text, text


def test_only_the_database_url_family_is_resolved():
    family = fg._TDB_FAMILY
    assert family.match(APP_KEY) and family.match("TEST_MIGRATION_DATABASE_URL")
    assert not family.match("TEST_DATABASE_URL")  # the primary key keeps its own path
    assert not family.match("TEST_REDIS_URL") and not family.match("TEST__DATABASE_URL")
