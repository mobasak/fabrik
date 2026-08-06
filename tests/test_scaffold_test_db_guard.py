"""Behavior Contract — the scaffold-emitted fail-closed test-DB guard.

Origin: a trade-intelligence agent pointed TEST_DATABASE_URL at the dev Postgres and ran
the full suite; the destructive tests (DROP SCHEMA public CASCADE) wiped it. The guard
makes that class of slip an error message instead of data loss, in every scaffolded
project. Behaviors covered:
  1. The emitted conftest refuses a non-disposable database name (fail closed).
  2. It allows names carrying the disposable marker (incl. ci_scaffold's ci_test).
  3. It allows CI (fresh service container) regardless of name.
  4. _write_test_conftest emits it, and the CI generator's DB name matches the marker.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from fabrik import scaffold
from fabrik.ci_scaffold import TEST_DB_NAME, CiConfig, render_ci_local, render_ci_workflow


def _emitted_guard(tmp_path: Path):
    """Write the conftest exactly as scaffold does, import it, return the module."""
    (tmp_path / "tests").mkdir()
    scaffold._write_test_conftest(tmp_path)
    spec = importlib.util.spec_from_file_location(
        "emitted_conftest", tmp_path / "tests" / "conftest.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["emitted_conftest"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_guard_refuses_dev_database(tmp_path, monkeypatch):
    """Behavior 1: a dev-named DB → RuntimeError BEFORE any connection is attempted."""
    monkeypatch.delenv("CI", raising=False)
    guard = _emitted_guard(tmp_path)
    with pytest.raises(RuntimeError, match="REFUSING destructive test"):
        guard.require_throwaway("postgresql://postgres:pw@localhost:54322/trade_intelligence")


def test_guard_allows_disposable_names(tmp_path, monkeypatch):
    """Behavior 2: _test / throwaway / scratch suffixes pass — including ci_test."""
    monkeypatch.delenv("CI", raising=False)
    guard = _emitted_guard(tmp_path)
    for name in (TEST_DB_NAME, "auth_test", "tmp_throwaway", "scratch"):
        guard.require_throwaway(f"postgresql://postgres:pw@localhost:5432/{name}")


def test_guard_allows_ci_environment(tmp_path, monkeypatch):
    """Behavior 3: CI=true (GitHub Actions, fresh service container) is always allowed."""
    monkeypatch.setenv("CI", "true")
    guard = _emitted_guard(tmp_path)
    guard.require_throwaway("postgresql://postgres:postgres@localhost:5432/postgres")


def test_ci_generator_db_name_matches_marker(tmp_path):
    """Behavior 4: both CI renderers target a disposable-marked DB, so the guard
    passes in CI/local-replica runs by NAME (not only via the CI escape hatch)."""
    guard = _emitted_guard(tmp_path)
    guard.require_throwaway(f"postgresql://x:x@localhost:5432/{TEST_DB_NAME}")  # marker check

    cfg = CiConfig(needs_database=True)
    wf, local = render_ci_workflow(cfg), render_ci_local(cfg)
    assert f"POSTGRES_DB: {TEST_DB_NAME}" in wf
    assert f"5432/{TEST_DB_NAME}" in wf  # TEST_DATABASE_URL path
    assert f"-e POSTGRES_DB={TEST_DB_NAME}" in local
    assert f"$PGPORT/{TEST_DB_NAME}" in local


def test_guard_ci_escape_is_localhost_only(tmp_path, monkeypatch):
    """Review fix: CI=true in a dev shell must NOT unlock a remote/tunneled DB —
    the escape is scoped to localhost service containers."""
    monkeypatch.setenv("CI", "true")
    guard = _emitted_guard(tmp_path)
    guard.require_throwaway("postgresql://postgres:pw@localhost:5432/postgres")  # CI + local: ok
    with pytest.raises(RuntimeError, match="REFUSING"):
        guard.require_throwaway("postgresql://postgres:pw@ti-dev-pg:54322/trade_intelligence")


def test_guard_marker_is_case_insensitive(tmp_path, monkeypatch):
    """Postgres unquoted names are case-insensitive: MY_TEST == my_test."""
    monkeypatch.delenv("CI", raising=False)
    guard = _emitted_guard(tmp_path)
    guard.require_throwaway("postgresql://u:p@localhost:5432/MY_TEST")


def test_guard_tolerates_trailing_slash(tmp_path, monkeypatch):
    """Review finding 8: a trailing slash must not defeat the disposable marker."""
    monkeypatch.delenv("CI", raising=False)
    guard = _emitted_guard(tmp_path)
    guard.require_throwaway("postgresql://u:p@localhost:5432/mydb_test/")


def test_guard_ci_escape_rejects_query_string_remote_host(tmp_path, monkeypatch):
    """Round-2 finding: libpq honors ?host= — an empty-netloc URL must not smuggle a
    remote host past the localhost-only CI escape."""
    monkeypatch.setenv("CI", "true")
    guard = _emitted_guard(tmp_path)
    guard.require_throwaway("postgresql:///postgres?host=localhost")  # local via query: ok
    with pytest.raises(RuntimeError, match="REFUSING"):
        guard.require_throwaway("postgresql:///postgres?host=ti-dev-pg")


def test_guard_refuses_dbname_query_override(tmp_path, monkeypatch):
    """Review finding: `.../anything_test?dbname=session_recall` connects to the REAL
    db (libpq honors ?dbname=) — the guard must resolve the effective name, not the path."""
    monkeypatch.delenv("CI", raising=False)
    guard = _emitted_guard(tmp_path)
    with pytest.raises(RuntimeError, match="REFUSING"):
        guard.require_throwaway(
            "postgresql://u:p@127.0.0.1:5432/anything_test?dbname=session_recall"
        )


def test_guard_refuses_keyword_dsn_remote_prod(tmp_path, monkeypatch):
    """A keyword-style DSN's whole string used to regex-match; a remote prod DB with a
    `_test`-suffixed something must not slip through."""
    monkeypatch.delenv("CI", raising=False)
    guard = _emitted_guard(tmp_path)
    with pytest.raises(RuntimeError, match="REFUSING"):
        guard.require_throwaway("host=10.99.0.1 port=5432 dbname=remote_prod")
