"""Onboarding regression: a DB-backed scaffold must document a WORKING TEST_DATABASE_URL.

transdoc filing 01M13G1B6B item 3 (routed to fleet via 01M143VYNT): the scaffolded docs call
`TEST_DATABASE_URL` non-optional — DB-backed tests `skipif` it is unset, and conftest's
`${TEST_DATABASE_URL:?}` guard blocks an all-SKIP "green" — yet nothing told the developer what to set
it to. The emitted `.env.local` + `.env.example` now carry it, pointed at a THROWAWAY `_test` database
(the name the `require_throwaway()` guard accepts, `_DISPOSABLE_NAME = /(_test|throwaway|scratch)$/`).
"""

import os

import pytest

from fabrik.scaffold import FABRIK_ROOT, create_project

requires_fabrik_env = pytest.mark.skipif(
    not FABRIK_ROOT.exists() or os.getenv("CI") == "true",
    reason="Requires full fabrik environment at /opt/fabrik",
)


@requires_fabrik_env
def test_db_backed_scaffold_documents_throwaway_test_database_url(tmp_path, monkeypatch):
    # Neuter the local DB auto-create (sudo -u postgres psql) so the test has no side effect and does
    # not depend on a live postgres — the .env writes we assert on happen independently of it.
    import fabrik.scaffold as scaffold_mod

    monkeypatch.setattr(
        scaffold_mod.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
    )

    create_project(
        name="tdb-check",
        project_type="python-api",
        description="TEST_DATABASE_URL onboarding regression",
        base=tmp_path,
        use_database=True,
        generate_spec=False,
    )
    proj = tmp_path / "tdb-check"

    local = (proj / ".env.local").read_text()
    assert "TEST_DATABASE_URL=" in local, ".env.local must give a working local TEST_DATABASE_URL"
    assert "tdb_check_test" in local, "local test DB must be the disposable _test database, not _dev"

    example = (proj / ".env.example").read_text()
    assert "TEST_DATABASE_URL=" in example, ".env.example must document TEST_DATABASE_URL"
    assert "tdb_check_test" in example, ".env.example test DB must end in _test (require_throwaway guard)"
