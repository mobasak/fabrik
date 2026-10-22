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
    for k in (KEY, "TEST_APP_DATABASE_URL", "TEST_MIGRATION_DATABASE_URL", "TEST_REDIS_URL"):
        monkeypatch.delenv(k, raising=False)  # the box environment never shapes a row (Bx-3)
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
    assert f"{project / '.env.local'}, {project / '.env'}" in text, text  # both paths, not a prefix


def test_the_skip_advisory_names_the_missing_key_only_for_db_gated_suites(project):
    _, ok, text = _row()
    assert ok and KEY in text, text
    # The exact sentence, graded: the exit-4 branch shares it through `_tdb_missing_hint`, and a
    # reword there must not drift this one (critique seats O5/F6c, W-f46bca45)
    where = f"{project / '.env.local'}, {project / '.env'}"
    assert (
        f"\u26a0 {KEY} is set in neither the environment nor {where}, and tests/ reads it \u2014 "
        "the skips above likely include the DB-backed suite. Add a disposable database URL (name "
        "ending `_test`, `throwaway` or `scratch`) to .env.local to run it here."
    ) in text, text

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


def test_two_keys_sharing_a_password_or_a_prefix_each_keep_their_label(rls_project, monkeypatch):
    """Review round 2: with a shared one-letter password, or one URL a prefix of the other, the
    first key's pass rewrote the second URL before its own replace ran — unlabeled or mislabeled."""
    tdb = "postgresql://u:p@localhost/test"
    app = "postgresql://u:p@localhost/test_app_test"
    monkeypatch.setenv(KEY, tdb)
    monkeypatch.setenv(APP_KEY, app)
    (rls_project / "tests" / "test_rls.py").write_text(
        "import os\n\ndef test_both():\n"
        f"    raise AssertionError('A=' + os.environ['{KEY}'] + ' B=' + os.environ['{APP_KEY}'])\n",
        encoding="utf-8",
    )
    name, ok, text = _row()
    assert not ok, (name, text)
    assert "A=<TEST_DATABASE_URL> B=<TEST_APP_DATABASE_URL>" in text, text
    assert "localhost/test" not in text, text


# A suite that REFUSES to run without the key — transdoc's conftest shape (01M171R8, W-f46bca45):
# pytest exit 4 at collection, a MULTI-LINE refusal that names the key on its FIRST line (transdoc's
# is 31 lines; the row's 15-line tail never shows that line), an `export` remedy for a shell and a
# database name the gate's disposable bar refuses. The row must put the gate's OWN channel
# (.env.local, D-597) first and keep the key-naming line in the quote.
REFUSAL_LINES = (
    [f"{KEY} is not set; this run collected 365 test(s) that need a real Postgres, and a"]
    + ["Postgres server IS reachable on this box.", ""]  # the headline wraps, then a blank line
    + [f"line {n} of the suite's own explanation" for n in range(4, 20)]
    + ["Remedy: createdb shop_test_$USER; export " + KEY + "=..."]
)
REFUSING_CONFTEST = f'''
import os, pytest

def pytest_collection_modifyitems(config, items):
    if not os.getenv("{KEY}", ""):
        raise pytest.UsageError({chr(10).join(REFUSAL_LINES)!r})
'''

# The same refusal, worded without the key: the gate cannot read cause from it. The conftest also
# PRINTS a line that mentions the key, which is not a refusal about it (review A-2).
SILENT_CONFTEST = f"""
import os, pytest

def pytest_collection_modifyitems(config, items):
    print("note: {KEY} is irrelevant to this refusal")
    if not os.getenv("TEST_DB_READY", ""):
        raise pytest.UsageError("the database fixture is not configured; refusing")
"""

HINT_TAIL = "Add a disposable database URL (name ending `_test`, `throwaway` or `scratch`) to .env.local to run it here."


@pytest.fixture
def refusing_project(project, monkeypatch):
    (project / "tests" / "conftest.py").write_text(REFUSING_CONFTEST, encoding="utf-8")
    monkeypatch.delenv("TEST_DB_READY", raising=False)  # SILENT_CONFTEST reads it
    return project


def _quote(text: str) -> str:
    return text.split("channel is the line above):", 1)[1]


def test_a_refusing_db_suite_is_told_the_gates_own_env_file_remedy(refusing_project):
    name, ok, text = _row()
    assert not ok and name == "pytest (SUITE REFUSED \u2014 usage error)", (name, text)
    where = f"{refusing_project / '.env.local'}, {refusing_project / '.env'}"
    causal = fg._tdb_missing_hint(
        where,
        "the suite refused to run without it \u2014 its message names the key \u2014 and it "
        "refuses here on every completion gate: an export typed in an agent's shell does not "
        "persist into the gate, which reads the key from .env.local (then .env), where the "
        "database name must end _test, throwaway or scratch (<project>_<you>_test, not "
        "<project>_test_<you>)",
    )
    assert causal in text, text  # the shared sentence, whole, through the one helper
    assert "\n" + causal + "\n" in text, text  # on its own line, like every other \u26a0 row
    assert "its export remedy is for a shell; the gate's channel is the line above):" in text, text
    assert text.index(HINT_TAIL) < text.index("Remedy: createdb"), text  # the gate's line first
    quote = _quote(text)
    assert "ERROR: " + REFUSAL_LINES[0] + "\n" + REFUSAL_LINES[1] + "\n\u2026" in quote, quote
    # the key-naming line AND its wrapped continuation (its paragraph), then the elision
    assert "line 4 of the suite" not in quote.split("\u2026")[0], (
        quote
    )  # the paragraph ends at the blank line
    assert "Remedy: createdb" in quote and "\u2026" in quote, quote  # the suite's own remedy too
    assert HINT_TAIL in fg.clip_output(text)["output"], text

    (refusing_project / ".env.local").write_text(f"{KEY}={GOOD}\n", encoding="utf-8")
    name, ok, text = _row()
    assert name == "pytest" and "from .env.local" in text, (name, text)  # the refusal is gone


def test_the_remedy_survives_a_row_long_enough_to_be_clipped(refusing_project):
    padded = REFUSAL_LINES[:1] + [f"padding line {n} " + "x" * 200 for n in range(30)]
    (refusing_project / "tests" / "conftest.py").write_text(
        REFUSING_CONFTEST.replace(repr(chr(10).join(REFUSAL_LINES)), repr(chr(10).join(padded))),
        encoding="utf-8",
    )
    where = f"{refusing_project / '.env.local'}, {refusing_project / '.env'}"
    assert len(where) < 300, (
        where
    )  # the premise: a hint with two short paths sits inside the 1400-char head
    _, ok, text = _row()
    clipped = fg.clip_output(text)
    assert not ok and clipped["truncated"], (len(text), clipped)
    assert HINT_TAIL in clipped["output"], clipped["output"]


def test_a_refusal_silent_about_the_key_gets_the_hedged_hint(refusing_project):
    (refusing_project / "tests" / "conftest.py").write_text(SILENT_CONFTEST, encoding="utf-8")
    name, ok, text = _row()  # tests/test_db.py still READS the key; the output mentions it
    assert not ok and "SUITE REFUSED" in name, (name, text)
    assert "a suite that refuses without it" in text and HINT_TAIL in text, text
    assert "does not persist into the gate" in text, text
    assert "its message names the key" not in text, text  # a printed mention is not a refusal
    assert "(when it is about the key, the gate's channel is the line above):" in text, text
    assert "its export remedy is for a shell" not in text, text


def test_a_refusal_unrelated_to_the_key_gets_no_env_file_hint(refusing_project):
    (refusing_project / "tests" / "conftest.py").write_text(SILENT_CONFTEST, encoding="utf-8")
    (refusing_project / "tests" / "test_db.py").write_text(
        "def test_x():\n    pass\n", encoding="utf-8"
    )  # nothing under tests/ reads the key and the refusal is not about it
    name, ok, text = _row()
    assert not ok and "SUITE REFUSED" in name, (name, text)
    assert HINT_TAIL not in text, text
    assert (  # byte for byte the pre-W-f46bca45 header: one line, then the quote
        "exit 4: the suite refused to run (conftest/usage error, not a failing test). "
        "The refusal message names the remedy:\n"
    ) in text, text


def test_a_resolved_key_gets_no_hint_even_when_the_refusal_names_the_key(refusing_project):
    (refusing_project / ".env.local").write_text(f"{KEY}={GOOD}\n", encoding="utf-8")
    (refusing_project / "tests" / "conftest.py").write_text(  # refuses whatever the key says
        f"import pytest\n\ndef pytest_collection_modifyitems(config, items):\n"
        f'    raise pytest.UsageError("{KEY} is set but the fixture role is wrong; refusing")\n',
        encoding="utf-8",
    )
    name, ok, text = _row()
    assert not ok and "SUITE REFUSED" in name, (name, text)
    assert HINT_TAIL not in text and "the line above" not in text, text  # the key IS resolved
    assert "not a failing test). The refusal message names the remedy:\n" in text, text
