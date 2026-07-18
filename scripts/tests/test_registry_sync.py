#!/usr/bin/env python3
# AFTER-EDIT: scripts/registry_sync.py
"""Behavior-Contract tests for the Postgres registry sync (Phase B).

Uses the REAL local fabrik_services Postgres (never SQLite — 12-Factor X) with a throwaway
test provider it deletes on teardown. Skips cleanly if the local PG is unreachable.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent
TEST_PROVIDER = "test_zzz_regsync"
SECRET = "sk-super-secret-registry-test-value-1234567890"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rs = _load("registry_sync")
rdb = _load("registry_db")


@pytest.fixture
def fixture_env(tmp_path, monkeypatch):
    try:
        rdb.connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("local fabrik_services PG not reachable")
    f = tmp_path / "all-envs.env"
    f.write_text(
        "# " + "═" * 10 + " ai-llm " + "═" * 10 + "\n"
        f'#svc name={TEST_PROVIDER} category=ai-llm cost=paid capability="test" '
        "url=https://x.example status=active used_by=projA,projB\n"
        f"{TEST_PROVIDER.upper()}_API_KEY={SECRET}\n"
        "# " + "═" * 10 + " internal-config (NOT a service) " + "═" * 10 + "\n"
        "PORT=8000\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rs, "ALL_ENVS", f)
    yield f
    try:
        conn = rdb.connect()
        with conn, conn.cursor() as cur:
            cur.execute("DELETE FROM services WHERE provider=%s", (TEST_PROVIDER,))
        conn.close()
    except Exception:  # noqa: BLE001
        pass


def test_value_sha256_never_raw(fixture_env):
    """Given a fixture with a known secret, When synced, Then api_keys holds the SHA-256 (not
    the raw secret), and the internal-config PORT is not a service."""
    rs.sync_registry()
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT k.value_sha256, k.used_by_projects FROM api_keys k "
            "JOIN services s ON s.id=k.service_id WHERE s.provider=%s",
            (TEST_PROVIDER,),
        )
        rows = cur.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == hashlib.sha256(SECRET.encode()).hexdigest()
        assert set(rows[0][1]) == {"projA", "projB"}
        cur.execute("SELECT count(*) FROM api_keys WHERE value_sha256=%s", (SECRET,))
        assert cur.fetchone()[0] == 0  # raw secret NEVER stored
        cur.execute("SELECT count(*) FROM services WHERE provider='PORT'")
        assert cur.fetchone()[0] == 0  # internal-config excluded
    conn.close()


def test_sync_idempotent(fixture_env):
    """Given unchanged input, When synced twice, Then no duplicate api_keys row appears."""
    rs.sync_registry()
    rs.sync_registry()
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM api_keys k JOIN services s ON s.id=k.service_id "
            "WHERE s.provider=%s",
            (TEST_PROVIDER,),
        )
        assert cur.fetchone()[0] == 1
    conn.close()
