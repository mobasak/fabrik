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
    rs.sync_registry(prune=False)  # partial fixture — must NOT wipe the real registry
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
    rs.sync_registry(prune=False)
    rs.sync_registry(prune=False)
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM api_keys k JOIN services s ON s.id=k.service_id "
            "WHERE s.provider=%s",
            (TEST_PROVIDER,),
        )
        assert cur.fetchone()[0] == 1
    conn.close()


def test_empty_parse_never_prunes(tmp_path, monkeypatch):
    """Given an EMPTY all-envs.env (corrupt/truncated gather), When synced with prune=True,
    Then NOTHING is deleted — the empty-parse guard is what stands between a bad gather run
    and a full registry wipe."""
    try:
        rdb.connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("local fabrik_services PG not reachable")
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM services")
        before = cur.fetchone()[0]
    conn.close()
    if before == 0:
        pytest.skip("registry empty — wipe guard unobservable")
    empty = tmp_path / "all-envs.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr(rs, "ALL_ENVS", empty)
    stats = rs.sync_registry()  # prune=True default — MUST NOT delete anything
    assert stats["pruned"] == 0
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM services")
        assert cur.fetchone()[0] == before  # registry intact
    conn.close()


def test_bounded_prune_refuses_mass_delete(tmp_path, monkeypatch):
    """Given a truncated file that would prune >20% of the registry (a corrupted gather, NOT a
    real recatalog), When synced with prune=True, Then the sync RAISES and NOTHING is deleted —
    silent mass cascade-deletion of credit history is the failure this bound exists to stop."""
    try:
        rdb.connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("local fabrik_services PG not reachable")
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM services")
        before = cur.fetchone()[0]
    conn.close()
    if before < 10:
        pytest.skip("registry too small for the 20% bound to be meaningful")
    # A one-provider file: pruning would delete before-1 services (≫ 20%).
    f = tmp_path / "all-envs.env"
    f.write_text(
        "# " + "═" * 10 + " ai-llm " + "═" * 10 + "\n"
        '#svc name=test_zzz_bound category=ai-llm cost=paid capability="t" '
        "url=https://x.example status=active used_by=-\n"
        "TEST_ZZZ_BOUND_API_KEY=sk-bound-test-1234567890abcdef\n",
        encoding="utf-8",
    )
    # SELF-HEAL GUARD: this test's non-destructiveness depends on the txn rollback in the code
    # under test. If a future refactor breaks that rollback, the registry (rebuildable) AND the
    # credit_snapshots history (irreplaceable) would be wiped — so snapshot the history in memory
    # first and, on catastrophic wipe, rebuild the registry + restore the history before failing.
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "SELECT s.provider, cs.balance, cs.unit, cs.fetched_at FROM credit_snapshots cs "
            "JOIN services s ON s.id = cs.service_id"
        )
        snapshot_backup = cur.fetchall()
    conn.close()
    monkeypatch.setattr(rs, "ALL_ENVS", f)
    try:
        with pytest.raises(RuntimeError, match="bounded prune"):
            rs.sync_registry()  # prune=True default
        conn = rdb.connect()
        with conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM services")
            assert cur.fetchone()[0] == before  # rolled back — nothing deleted, upsert included
            cur.execute("SELECT count(*) FROM services WHERE provider='test_zzz_bound'")
            assert cur.fetchone()[0] == 0  # the txn aborted atomically
        conn.close()
    except BaseException:
        # Rollback machinery may have regressed → the registry may be wiped. Rebuild from the
        # real file (registry is derived state) and restore the snapshot history, THEN re-raise.
        monkeypatch.setattr(rs, "ALL_ENVS", rs.REPO / "secrets" / "all-envs.env")
        try:
            rs.sync_registry(prune=False)  # rebuild services/api_keys; never prune during heal
            conn = rdb.connect()
            with conn, conn.cursor() as cur:
                for provider, balance, unit, fetched_at in snapshot_backup:
                    cur.execute(
                        "INSERT INTO credit_snapshots (service_id, balance, unit, fetched_at) "
                        "SELECT id, %s, %s, %s FROM services WHERE provider=%s "
                        "ON CONFLICT DO NOTHING",
                        (balance, unit, fetched_at, provider),
                    )
            conn.close()
        except Exception:  # noqa: BLE001 - healing is best-effort; the original failure surfaces
            pass
        raise


def test_prune_force_rejects_falsy_strings(tmp_path, monkeypatch):
    """Given REGISTRY_PRUNE_FORCE set to a conventional 'off' value ('0'), When a mass delete
    trips the bound, Then the guard STILL fires — only explicit '1'/'true'/'yes' may disable a
    data-loss guard (bare non-empty truthiness would silently accept '0'/'false'/'no')."""
    try:
        rdb.connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("local fabrik_services PG not reachable")
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM services")
        before = cur.fetchone()[0]
    conn.close()
    if before < 10:
        pytest.skip("registry too small for the bound to trip")
    f = tmp_path / "all-envs.env"
    f.write_text(
        "# " + "═" * 10 + " ai-llm " + "═" * 10 + "\n"
        '#svc name=test_zzz_force category=ai-llm cost=paid capability="t" '
        "url=https://x.example status=active used_by=-\n"
        "TEST_ZZZ_FORCE_API_KEY=sk-force-test-1234567890abcdef\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rs, "ALL_ENVS", f)
    monkeypatch.setenv("REGISTRY_PRUNE_FORCE", "0")  # conventional 'off' — must NOT bypass
    with pytest.raises(RuntimeError, match="bounded prune"):
        rs.sync_registry()
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM services")
        assert cur.fetchone()[0] == before  # nothing deleted
    conn.close()


def test_prune_removes_orphans():
    """Given an orphan service absent from all-envs.env, When synced with prune=True (the CLI
    default, against the REAL file), Then the orphan is deleted and the real registry survives.

    Uses the real ALL_ENVS (not the one-provider fixture) precisely because a global prune against
    a partial file would wipe everything — the guard this test also proves is load-bearing.
    """
    try:
        rdb.connect().close()
    except Exception:  # noqa: BLE001
        pytest.skip("local fabrik_services PG not reachable")
    if not rs.ALL_ENVS.exists():
        pytest.skip("secrets/all-envs.env not present — run gather_envs.py --apply first")
    orphan = "test_zzz_orphan_prune"
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO services (provider, category, cost_tier, url, status) "
            "VALUES (%s,'?','?','?','?') ON CONFLICT (provider) DO NOTHING",
            (orphan,),
        )
    conn.close()
    stats = rs.sync_registry()  # prune=True default, REAL file → all real providers preserved
    assert stats["pruned"] >= 1
    conn = rdb.connect()
    with conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM services WHERE provider=%s", (orphan,))
        assert cur.fetchone()[0] == 0  # orphan pruned
        cur.execute("SELECT count(*) FROM services")
        # Exact, future-proof: after a full sync the registry mirrors the file's provider set
        # (no magic ">= 50" that breaks when the fleet's provider count legitimately changes).
        expected = len({p["meta"]["name"] for p in rs.parse(rs.ALL_ENVS)})
        assert cur.fetchone()[0] == expected  # real registry intact — NOT wiped by the global prune
    conn.close()
